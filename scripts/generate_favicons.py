"""Generate the raster favicon fallbacks without third-party dependencies."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"


def _inside_diamond(x: float, y: float, radius: float) -> bool:
    return abs(x) + abs(y) <= radius


def _render(size: int) -> bytes:
    scale = 4
    pixels = bytearray()
    for py in range(size):
        pixels.append(0)
        for px in range(size):
            samples = []
            for sy in range(scale):
                for sx in range(scale):
                    x = (px + (sx + 0.5) / scale) / size * 64
                    y = (py + (sy + 0.5) / scale) / size * 64
                    dx, dy = x - 32, y - 32
                    if _inside_diamond(dx, dy, 27):
                        if _inside_diamond(dx, dy, 24):
                            t = max(0.0, min(1.0, (x + y - 20) / 88))
                            color = (
                                round(41 * (1 - t) + 17 * t),
                                round(34 * (1 - t) + 17 * t),
                                round(24 * (1 - t) + 20 * t),
                                255,
                            )
                        else:
                            color = (210, 168, 95, 255)
                    elif 0 <= x < 64 and 0 <= y < 64:
                        color = (11, 11, 13, 255)
                    else:
                        color = (0, 0, 0, 0)
                    if (21 <= y <= 43) and (
                        (21.5 <= x <= 26.5) or (37.5 <= x <= 42.5)
                    ):
                        color = (235, 199, 127, 255)
                    samples.append(color)
            pixels.extend(
                round(sum(sample[channel] for sample in samples) / len(samples))
                for channel in range(4)
            )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(pixels), 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    images = [(size, _render(size)) for size in (16, 32, 48)]
    (PUBLIC / "favicon-32.png").write_bytes(images[1][1])

    offset = 6 + 16 * len(images)
    directory = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    payload = bytearray()
    for size, image in images:
        directory.extend(
            struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(image), offset)
        )
        payload.extend(image)
        offset += len(image)
    (PUBLIC / "favicon.ico").write_bytes(directory + payload)


if __name__ == "__main__":
    main()
