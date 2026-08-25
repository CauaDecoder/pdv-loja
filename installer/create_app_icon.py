"""Gera ícone ICO do Caixa Basílica sem dependências externas."""

from __future__ import annotations

import struct
import sys
from pathlib import Path


def icon_pixels(size: int) -> bytes:
    """Desenha ícone verde e dourado em pixels BGRA.

    Args:
        size (int): Largura e altura do ícone em pixels.

    Returns:
        (bytes): Pixels no formato BGRA.
    """
    pixels = bytearray(size * size * 4)
    center = (size - 1) / 2
    radius = size * 0.44
    for y in range(size):
        for x in range(size):
            offset = (y * size + x) * 4
            distance = ((x - center) ** 2 + (y - center) ** 2) ** 0.5
            if distance > radius:
                continue
            blue, green, red = (43, 91, 24)
            if abs(x - center) < size * 0.07 or abs(y - center) < size * 0.07:
                blue, green, red = (36, 167, 212)
            pixels[offset:offset + 4] = bytes((blue, green, red, 255))
    return bytes(pixels)


def write_icon(destination: Path) -> None:
    """Escreve arquivo ICO multiresolução.

    Args:
        destination (Path): Caminho do arquivo ICO gerado.
    """
    sizes = (16, 32, 48, 64, 128, 256)
    images = []
    for size in sizes:
        bitmap_header = struct.pack(
            "<IIIHHIIIIII",
            40,
            size,
            size * 2,
            1,
            32,
            0,
            size * size * 4,
            0,
            0,
            0,
            0,
        )
        images.append(bitmap_header + icon_pixels(size) + bytes(((size + 31) // 32) * 4 * size))

    directory_size = 6 + len(images) * 16
    offset = directory_size
    entries = []
    for size, image in zip(sizes, images):
        entries.append(struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0, 0, 0, 1, 32, len(image), offset))
        offset += len(image)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + b"".join(images))


if __name__ == "__main__":
    write_icon(Path(sys.argv[1]))
