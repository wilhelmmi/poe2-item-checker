import asyncio
import io
from concurrent.futures import Executor, Future

import pytest
from PIL import Image

from app.ocr import service


def image_bytes(width: int = 32, height: int = 32) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (width, height), "black").save(output, "PNG")
    return output.getvalue()


def test_ocr_runs_tesseract_in_memory_without_temp_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    async def run(png, timeout):
        captured["input"] = png
        captured["timeout"] = timeout
        return "Gegenstandsklasse: Zauberstäbe"

    monkeypatch.setattr(service, "_run_tesseract", run)
    async def decode(data):
        return service._prepare_image(data)
    monkeypatch.setattr(service, "_decode_image", decode)
    text = asyncio.run(service.recognize(image_bytes(), "image/png"))

    assert text == "Gegenstandsklasse: Zauberstäbe"
    assert isinstance(captured["input"], bytes)


def test_ocr_rejects_non_image_before_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    async def run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(service, "_run_tesseract", run)
    async def decode(data):
        return service._prepare_image(data)
    monkeypatch.setattr(service, "_decode_image", decode)
    with pytest.raises(service.OcrError, match="invalid_image"):
        asyncio.run(service.recognize(b"not an image", "image/png"))
    assert not called


def test_ocr_rejects_unsupported_content_type() -> None:
    with pytest.raises(service.OcrError, match="unsupported_image_type"):
        asyncio.run(service.recognize(image_bytes(), "image/gif"))


def test_ocr_rejects_actual_format_even_when_mime_claims_png(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "black").save(output, "BMP")
    async def decode(data):
        return service._prepare_image(data)
    monkeypatch.setattr(service, "_decode_image", decode)
    with pytest.raises(service.OcrError, match="unsupported_image_type"):
        asyncio.run(service.recognize(output.getvalue(), "image/png"))


def test_tesseract_process_is_reaped_on_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    class Process:
        returncode = None
        killed = False
        waited = False

        async def communicate(self, data):
            await asyncio.Future()

        def kill(self):
            self.killed = True
            self.returncode = -9

        async def wait(self):
            self.waited = True

    process = Process()

    async def create(*args, **kwargs):
        return process

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", create)

    async def cancel() -> None:
        task = asyncio.create_task(service._run_tesseract(b"png", 30))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel())
    assert process.killed
    assert process.waited


def test_cancelled_queued_decode_never_starts_after_worker_is_released(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bytes] = []

    class SingleWorkerExecutor(Executor):
        def __init__(self) -> None:
            self.running: tuple[Future[bytes], object, tuple[bytes, ...]] | None = None
            self.queued: list[tuple[Future[bytes], object, tuple[bytes, ...]]] = []

        def submit(self, function, /, *args, **kwargs):
            future: Future[bytes] = Future()
            entry = (future, function, args)
            if self.running is None:
                assert future.set_running_or_notify_cancel()
                self.running = entry
            else:
                self.queued.append(entry)
            return future

        def finish_running(self) -> None:
            assert self.running is not None
            future, function, args = self.running
            future.set_result(function(*args))
            self.running = None
            while self.queued:
                queued, function, args = self.queued.pop(0)
                if queued.set_running_or_notify_cancel():
                    queued.set_result(function(*args))
                    break

    executor = SingleWorkerExecutor()
    def decode(data: bytes) -> bytes:
        calls.append(data)
        return data
    monkeypatch.setattr(service, "_decode_executor", lambda: executor)
    monkeypatch.setattr(service, "_prepare_image", decode)

    async def exercise() -> None:
        first = asyncio.create_task(service._decode_image(b"first"))
        await asyncio.sleep(0)

        queued = asyncio.create_task(service._decode_image(b"queued"))
        await asyncio.sleep(0)
        queued.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued

        assert calls == []
        executor.finish_running()
        assert await first == b"first"
        await asyncio.sleep(0.01)
        assert calls == [b"first"]

    asyncio.run(exercise())
