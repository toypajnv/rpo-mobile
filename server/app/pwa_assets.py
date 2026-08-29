from __future__ import annotations

import struct
import zlib


def _chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def make_icon_png(size: int) -> bytes:
    """Create a simple square RPO safety icon using only the Python standard library."""
    if size not in {180, 192, 512}:
        raise ValueError("Unsupported PWA icon size")

    navy = (7, 60, 119)
    blue = (13, 99, 230)
    white = (255, 255, 255)
    green = (27, 158, 80)

    pixels = [list(navy) for _ in range(size * size)]

    def paint_rect(x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int]) -> None:
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(size, x2), min(size, y2)
        for y in range(y1, y2):
            start = y * size
            for x in range(x1, x2):
                pixels[start + x] = list(color)

    margin = max(12, size // 9)
    paint_rect(margin, margin, size - margin, size - margin, blue)

    # White safety shield / permit sheet pictogram.
    left = size * 29 // 100
    right = size * 71 // 100
    top = size * 23 // 100
    bottom = size * 76 // 100
    paint_rect(left, top, right, bottom, white)
    inset = max(5, size // 40)
    paint_rect(left + inset, top + inset, right - inset, bottom - inset, blue)

    # Three white permit lines.
    line_left = size * 37 // 100
    line_right = size * 63 // 100
    h = max(4, size // 34)
    for y_pct in (37, 48, 59):
        y = size * y_pct // 100
        paint_rect(line_left, y, line_right, y + h, white)

    # Green approval mark.
    mark = size * 10 // 100
    cx, cy = size * 66 // 100, size * 68 // 100
    paint_rect(cx - mark // 2, cy - mark // 2, cx + mark // 2, cy + mark // 2, green)
    stroke = max(3, size // 64)
    for i in range(mark // 2):
        x = cx - mark // 4 + i
        y = cy + i // 2
        paint_rect(x, y, x + stroke, y + stroke, white)
    for i in range(mark):
        x = cx - mark // 12 + i // 2
        y = cy + mark // 4 - i // 2
        paint_rect(x, y, x + stroke, y + stroke, white)

    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            raw.extend(pixels[y * size + x])

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _chunk(b"IEND", b"")
