import asyncio
import atexit
import io
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}


class OcrError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.status_code = status_code


@lru_cache
def _semaphore() -> asyncio.Semaphore:
    return asyncio.Semaphore(get_settings().ocr_max_concurrency)


@lru_cache
def _decode_executor() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(
        max_workers=get_settings().ocr_max_concurrency,
        thread_name_prefix="poe2-ocr-decode",
    )


def _shutdown_decode_executor() -> None:
    if _decode_executor.cache_info().currsize:
        _decode_executor().shutdown(wait=False, cancel_futures=True)


atexit.register(_shutdown_decode_executor)


def _prepare_image(data: bytes) -> bytes:
    settings = get_settings()
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ALLOWED_FORMATS:
                raise OcrError("unsupported_image_type", "Unterstützt werden PNG, JPEG und WebP.")
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > settings.ocr_max_pixels:
                raise OcrError("image_too_large", "Das Bild hat zu viele Pixel.", 413)
            image.load()
            converted = image.convert("RGB")
            output = io.BytesIO()
            converted.save(output, format="PNG", optimize=True)
            return output.getvalue()
    except OcrError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise OcrError("invalid_image", "Die Datei ist kein unterstütztes Bild.") from exc


async def _decode_image(data: bytes) -> bytes:
    decode = asyncio.get_running_loop().run_in_executor(
        _decode_executor(), _prepare_image, data
    )
    try:
        return await decode
    except BaseException:
        # Queued work is removed; already-running work remains bounded by max_workers.
        decode.cancel()
        raise


async def _run_tesseract(png: bytes, timeout: float) -> str:
    try:
        process = await asyncio.create_subprocess_exec(
            "tesseract", "stdin", "stdout", "-l", "deu+eng", "--psm", "6",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise OcrError("ocr_unavailable", "Die lokale Texterkennung ist nicht verfügbar.", 503) from exc
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(png), timeout)
    except BaseException as exc:
        if process.returncode is None:
            process.kill()
        await process.wait()
        if isinstance(exc, TimeoutError):
            raise OcrError("ocr_timeout", "Die Texterkennung hat zu lange gedauert.", 504) from exc
        raise
    if process.returncode != 0:
        raise OcrError("ocr_failed", "Der Text konnte nicht lokal erkannt werden.")
    return stdout.decode("utf-8", errors="replace").strip()


async def recognize(data: bytes, content_type: str | None) -> str:
    settings = get_settings()
    if content_type not in ALLOWED_TYPES:
        raise OcrError("unsupported_image_type", "Unterstützt werden PNG, JPEG und WebP.")
    if not data:
        raise OcrError("empty_image", "Das Bild ist leer.")
    if len(data) > settings.ocr_max_bytes:
        raise OcrError("image_too_large", "Das Bild ist zu groß.", 413)
    async def run_bounded() -> str:
        async with _semaphore():
            png = await _decode_image(data)
            return await _run_tesseract(png, settings.ocr_timeout_seconds)

    try:
        text = await asyncio.wait_for(run_bounded(), settings.ocr_timeout_seconds)
    except TimeoutError as exc:
        raise OcrError("ocr_timeout", "Die Texterkennung hat zu lange gedauert.", 504) from exc
    if not text:
        raise OcrError("no_text_found", "Im Bild wurde kein Text erkannt.")
    return text
