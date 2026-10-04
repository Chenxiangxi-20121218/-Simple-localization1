# -*- coding: utf-8 -*-
"""生成 Windows 图标 ``app.ico``（多尺寸，纯 PNG 内嵌，无需 Pillow）。

用法::

    python tools/make_icon.py
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, Qt          # noqa: E402
from PySide6.QtWidgets import QApplication                  # noqa: E402

from app import icons                                       # noqa: E402
from app.theme import C                                     # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)


def _png_bytes(size: int) -> bytes:
    """把矢量图标渲染成指定尺寸的 PNG 字节流。"""
    pm = icons.pixmap("logo", C.BLUE, size)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    pm.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def build_ico(out: Path) -> Path:
    """手工拼装 ICO 容器（每个尺寸一段 PNG）。"""
    images = [(s, _png_bytes(s)) for s in SIZES]

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)

    entries = b""
    payload = b""
    for size, data in images:
        w = 0 if size >= 256 else size
        h = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        payload += data
        offset += len(data)

    out.write_bytes(header + entries + payload)
    return out


def main() -> int:
    app = QApplication(sys.argv)   # noqa: F841 - QPixmap 需要 QApplication
    out = ROOT / "app.ico"
    build_ico(out)
    print(f"OK -> {out}  ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
