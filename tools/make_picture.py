# -*- coding: utf-8 -*-
"""导出品牌图标 PNG 到 ``picture/``（供 README / 商店页 / 宣传素材使用）。

图标本体仍是 ``app.icons`` 里那套 QPainter 矢量绘制 —— 这里只是把它
渲染成不同尺寸的 PNG 落盘，保证「应用内 logo」与「导出的图片」永远同源。

目前导出两套形状（除轮廓外渐变 / 光影 / 文字完全一致，便于对比）：

* ``sl1_icon_*``     —— 八边形（应用内实际使用的版本，仿 PCL2 切角正方形）
* ``sl1_heptagon_*`` —— 七边形（对比版）
* ``sl1_compare_7v8.png`` —— 两版并排对比图

用法::

    python tools/make_picture.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QRectF, Qt   # noqa: E402
from PySide6.QtGui import (QColor, QFont, QFontDatabase,     # noqa: E402
                           QPainter, QPixmap)
from PySide6.QtWidgets import QApplication                   # noqa: E402

from app import icons                                        # noqa: E402
from app.theme import C                                      # noqa: E402

OUT = ROOT / "picture"

#: 单独落盘的主尺寸（透明背景，可直接用于各类文档 / 商店页）
EXPORT_SIZES = (256, 512, 1024)
#: 对照图里并排展示的尺寸，用来确认小尺寸下是否还认得出
SHEET_SIZES = (16, 24, 32, 48, 64, 128, 256)

#: (图标名, 文件名前缀, 对比图上的标题)
VARIANTS = (
    ("logo", "sl1_icon", "八边形（应用内）"),
    ("logo_heptagon", "sl1_heptagon", "七边形（对比版）"),
)

#: 沙箱 / 无桌面环境里 QFontDatabase.families() 可能为空，对照图的尺寸标签
#: 会变成方块，所以手动加载系统字体（图标本体不依赖字体，见 icons._draw_sl1）
_FONT_FILES = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
)

#: 展示图底色。刻意用冷调浅蓝（而不是近白的 #F2F5F9）：
#: 一来「冷底 + 暖红图标」的冷暖对比能把图标衬得更跳，
#: 二来浅蓝比中性白更像「展示台」，不会跟透明底的主图混淆。
_BG = "#DCE9F7"


def _ui_font_family() -> str:
    for path in _FONT_FILES:
        if not Path(path).exists():
            continue
        fid = QFontDatabase.addApplicationFont(path)
        if fid != -1:
            fams = QFontDatabase.applicationFontFamilies(fid)
            if fams:
                return fams[0]
    return ""


def _font(size: int, bold: bool = False) -> QFont:
    family = _ui_font_family()
    f = QFont(family) if family else QFont()
    f.setPixelSize(size)
    f.setBold(bold)
    return f


def _png_bytes(icon_name: str, size: int) -> bytes:
    pm = icons.pixmap(icon_name, C.BRAND, size)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    pm.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def write_sizes(out_dir: Path, icon_name: str, prefix: str) -> list[Path]:
    """把某个形状按主尺寸逐个落盘（透明背景）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for size in EXPORT_SIZES:
        path = out_dir / f"{prefix}_{size}.png"
        path.write_bytes(_png_bytes(icon_name, size))
        written.append(path)
    return written


def write_sheet(out_dir: Path, icon_name: str, prefix: str) -> Path:
    """把某个形状的所有尺寸并排画到一张浅色底图上，方便一眼确认可读性。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    pad, band, cap = 22, 256, 30
    width = sum(s + pad for s in SHEET_SIZES) + pad
    sheet = QPixmap(width, band + pad * 2 + cap)
    sheet.fill(QColor(_BG))

    p = QPainter(sheet)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    p.setFont(_font(14))

    x = pad
    for size in SHEET_SIZES:
        p.drawPixmap(x, pad + (band - size) // 2,
                     icons.pixmap(icon_name, C.BRAND, size))
        p.setPen(QColor("#5A6472"))
        p.drawText(QRectF(x - 14, pad + band + 6, size + 28, 20),
                   Qt.AlignCenter, str(size))
        x += size + pad
    p.end()

    path = out_dir / f"{prefix}_sizes.png"
    sheet.save(str(path))
    return path


def write_compare(out_dir: Path) -> Path:
    """八边形 vs 七边形并排对比：大图 + 全尺寸小图，共用同一底色与版式。"""
    out_dir.mkdir(parents=True, exist_ok=True)

    small = (16, 24, 32, 48, 64, 128)
    pad, gap, big = 20, 36, 256
    step, gap_s = 12, 22            # 小图间距 / 大图与小图行的间距
    row_w = sum(s + step for s in small) + step
    col_w = max(big, row_w) + pad * 2
    title_h, label_h = 34, 22
    row_h = max(small)

    width = col_w * len(VARIANTS) + gap * (len(VARIANTS) - 1)
    height = pad + title_h + gap_s + big + gap_s + row_h + label_h + pad

    sheet = QPixmap(width, height)
    sheet.fill(QColor(_BG))

    p = QPainter(sheet)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)

    for idx, (icon_name, _prefix, caption) in enumerate(VARIANTS):
        x0 = pad + idx * (col_w + gap)

        p.setFont(_font(15, bold=True))
        p.setPen(QColor("#2B2F36"))
        p.drawText(QRectF(x0, pad, col_w, title_h), Qt.AlignCenter, caption)

        # 大图
        p.drawPixmap(x0 + (col_w - big) // 2, pad + title_h + gap_s,
                     icons.pixmap(icon_name, C.BRAND, big))

        # 小尺寸行（底对齐 + 下方标注像素数）
        y = pad + title_h + gap_s + big + gap_s
        p.setFont(_font(12))
        x = x0 + (col_w - row_w) // 2 + step
        for s in small:
            p.drawPixmap(x, y + (row_h - s) // 2, icons.pixmap(icon_name, C.BRAND, s))
            p.setPen(QColor("#7C838C"))
            p.drawText(QRectF(x - 10, y + row_h + 2, s + 20, label_h),
                       Qt.AlignCenter, str(s))
            x += s + step
    p.end()

    path = out_dir / "sl1_compare_7v8.png"
    sheet.save(str(path))
    return path


def main() -> int:
    app = QApplication(sys.argv)   # noqa: F841 - QPixmap 需要 QApplication
    for icon_name, prefix, _caption in VARIANTS:
        for png in write_sizes(OUT, icon_name, prefix):
            print(f"OK -> {png}  ({png.stat().st_size} bytes)")
        sheet = write_sheet(OUT, icon_name, prefix)
        print(f"OK -> {sheet}  ({sheet.stat().st_size} bytes)")
    compare = write_compare(OUT)
    print(f"OK -> {compare}  ({compare.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
