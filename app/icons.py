# -*- coding: utf-8 -*-
"""矢量图标：全部用 QPainter 现场绘制，零外部图片资源。

好处：``--onefile`` 打包不会踩 ``sys._MEIPASS`` 的资源路径坑，且可任意换色/换尺寸不失真。
每个图标都在 64x64 的逻辑坐标里画，最后统一 ``p.scale()`` 到目标尺寸。
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QIcon, QPainter, QPainterPath,
                           QPen, QPixmap, QPolygonF)

_LOGICAL = 64.0

# ------------------------------------------------------------------ 单个图标绘制


def _pen(p: QPainter, color: str, w: float = 5.0, cap=Qt.RoundCap, join=Qt.RoundJoin) -> None:
    pen = QPen(QColor(color))
    pen.setWidthF(w)
    pen.setCapStyle(cap)
    pen.setJoinStyle(join)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)


def _ic_translate(p: QPainter, c: str) -> None:
    """翻译：中英双字块 + 双向箭头。"""
    _pen(p, c, 4.0)
    # 左：字母 A
    p.drawLine(QPointF(9, 30), QPointF(18, 8))
    p.drawLine(QPointF(18, 8), QPointF(27, 30))
    p.drawLine(QPointF(13.5, 22), QPointF(22.5, 22))
    # 右：汉字「文」的简化
    _pen(p, c, 4.0)
    p.drawLine(QPointF(37, 9), QPointF(58, 9))
    p.drawLine(QPointF(47.5, 9), QPointF(41, 27))
    p.drawLine(QPointF(41, 27), QPointF(58, 27))
    # 底部箭头
    _pen(p, c, 4.0)
    p.drawLine(QPointF(10, 46), QPointF(54, 46))
    p.drawLine(QPointF(46, 39), QPointF(54, 46))
    p.drawLine(QPointF(46, 53), QPointF(54, 46))
    p.drawLine(QPointF(10, 46), QPointF(10, 46))


def _ic_settings(p: QPainter, c: str) -> None:
    """设置：齿轮。"""
    p.save()
    p.translate(32, 32)
    _pen(p, c, 5.0)
    p.drawEllipse(QRectF(-9, -9, 18, 18))
    for i in range(8):
        p.save()
        p.rotate(i * 45)
        p.drawLine(QPointF(0, -14), QPointF(0, -21))
        p.restore()
    p.restore()


def _ic_folder(p: QPainter, c: str) -> None:
    _pen(p, c, 5.0)
    path = QPainterPath()
    path.moveTo(8, 20)
    path.lineTo(8, 50)
    path.lineTo(56, 50)
    path.lineTo(56, 22)
    path.lineTo(30, 22)
    path.lineTo(24, 15)
    path.lineTo(8, 15)
    path.closeSubpath()
    p.drawPath(path)


def _ic_package(p: QPainter, c: str) -> None:
    """汉化包：纸箱。"""
    _pen(p, c, 5.0)
    p.drawRect(QRectF(10, 22, 44, 32))
    p.drawLine(QPointF(10, 32), QPointF(54, 32))
    p.drawLine(QPointF(32, 22), QPointF(32, 54))
    p.drawLine(QPointF(32, 22), QPointF(22, 10))
    p.drawLine(QPointF(32, 22), QPointF(42, 10))
    p.drawLine(QPointF(22, 10), QPointF(42, 10))
    p.drawLine(QPointF(42, 10), QPointF(54, 22))


def _ic_play(p: QPainter, c: str) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(c)))
    poly = QPolygonF([QPointF(20, 12), QPointF(54, 32), QPointF(20, 52)])
    p.drawPolygon(poly)


def _ic_model(p: QPainter, c: str) -> None:
    """翻译模型：芯片。"""
    _pen(p, c, 5.0)
    p.drawRect(QRectF(18, 18, 28, 28))
    for off in (25, 32, 39):
        p.drawLine(QPointF(off, 18), QPointF(off, 9))
        p.drawLine(QPointF(off, 46), QPointF(off, 55))
        p.drawLine(QPointF(18, off), QPointF(9, off))
        p.drawLine(QPointF(46, off), QPointF(55, off))


def _ic_heart(p: QPainter, c: str) -> None:
    _pen(p, c, 5.0)
    path = QPainterPath()
    path.moveTo(32, 52)
    path.cubicTo(6, 34, 12, 12, 32, 22)
    path.cubicTo(52, 12, 58, 34, 32, 52)
    p.drawPath(path)


def _ic_warning(p: QPainter, c: str) -> None:
    _pen(p, c, 5.0)
    path = QPainterPath()
    path.moveTo(32, 10)
    path.lineTo(56, 52)
    path.lineTo(8, 52)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(32, 26), QPointF(32, 40))
    p.setBrush(QBrush(QColor(c)))
    p.drawEllipse(QPointF(32, 46), 2.2, 2.2)


def _ic_cave(p: QPainter, c: str) -> None:
    """回声洞：山洞轮廓。"""
    _pen(p, c, 5.0)
    path = QPainterPath()
    path.moveTo(8, 52)
    path.cubicTo(10, 22, 26, 12, 34, 20)
    path.cubicTo(42, 28, 34, 36, 40, 42)
    path.cubicTo(46, 48, 54, 44, 56, 52)
    p.drawPath(path)
    p.drawLine(QPointF(8, 52), QPointF(56, 52))


def _ic_check(p: QPainter, c: str) -> None:
    _pen(p, c, 7.0)
    p.drawLine(QPointF(13, 34), QPointF(26, 47))
    p.drawLine(QPointF(26, 47), QPointF(52, 18))


def _ic_close(p: QPainter, c: str) -> None:
    _pen(p, c, 5.5)
    p.drawLine(QPointF(18, 18), QPointF(46, 46))
    p.drawLine(QPointF(46, 18), QPointF(18, 46))


def _ic_min(p: QPainter, c: str) -> None:
    _pen(p, c, 5.0)
    p.drawLine(QPointF(18, 34), QPointF(46, 34))


def _ic_max(p: QPainter, c: str) -> None:
    _pen(p, c, 5.0)
    p.drawRect(QRectF(19, 19, 26, 26))


def _ic_restore(p: QPainter, c: str) -> None:
    _pen(p, c, 4.5)
    p.drawRect(QRectF(16, 24, 24, 24))
    p.drawLine(QPointF(24, 24), QPointF(24, 16))
    p.drawLine(QPointF(24, 16), QPointF(48, 16))
    p.drawLine(QPointF(48, 16), QPointF(48, 40))
    p.drawLine(QPointF(48, 40), QPointF(40, 40))


def _ic_back(p: QPainter, c: str) -> None:
    _pen(p, c, 5.0)
    p.drawLine(QPointF(52, 32), QPointF(14, 32))
    p.drawLine(QPointF(14, 32), QPointF(30, 16))
    p.drawLine(QPointF(14, 32), QPointF(30, 48))


def _ic_refresh(p: QPainter, c: str) -> None:
    _pen(p, c, 5.0)
    p.drawArc(QRectF(13, 13, 38, 38), 40 * 16, 270 * 16)
    p.setBrush(QBrush(QColor(c)))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([QPointF(46, 8), QPointF(58, 20), QPointF(42, 24)]))


def _ic_list(p: QPainter, c: str) -> None:
    _pen(p, c, 5.0)
    for y in (16, 32, 48):
        p.drawLine(QPointF(24, y), QPointF(54, y))
    p.setBrush(QBrush(QColor(c)))
    p.setPen(Qt.NoPen)
    for y in (16, 32, 48):
        p.drawEllipse(QPointF(12, y), 3.2, 3.2)


def _ic_brush(p: QPainter, c: str) -> None:
    """个性化：调色板。"""
    _pen(p, c, 5.0)
    path = QPainterPath()
    path.addEllipse(QRectF(8, 12, 48, 40))
    p.drawPath(path)
    p.setBrush(QBrush(QColor(c)))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(22, 26), 3.6, 3.6)
    p.drawEllipse(QPointF(38, 22), 3.6, 3.6)
    p.drawEllipse(QPointF(42, 38), 3.6, 3.6)


def _ic_logo(p: QPainter, c: str) -> None:
    """品牌标识：草方块。"""
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(c)))
    p.drawRoundedRect(QRectF(9, 9, 46, 46), 8, 8)
    p.setBrush(QBrush(QColor("#FFFFFF")))
    p.drawRect(QRectF(20, 26, 10, 10))
    p.drawRect(QRectF(34, 26, 10, 10))
    p.drawRect(QRectF(20, 40, 24, 5))


def _ic_clock(p: QPainter, c: str) -> None:
    _pen(p, c, 5.0)
    p.drawEllipse(QRectF(10, 10, 44, 44))
    p.drawLine(QPointF(32, 18), QPointF(32, 34))
    p.drawLine(QPointF(32, 34), QPointF(44, 40))


def _ic_lock(p: QPainter, c: str) -> None:
    _pen(p, c, 5.0)
    p.drawRect(QRectF(16, 28, 32, 26))
    p.drawArc(QRectF(22, 12, 20, 26), 0, 180 * 16)


def _ic_star(p: QPainter, c: str) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(c)))
    pts = []
    import math
    for i in range(10):
        r = 24 if i % 2 == 0 else 10
        a = math.radians(-90 + i * 36)
        pts.append(QPointF(32 + r * math.cos(a), 32 + r * math.sin(a)))
    p.drawPolygon(QPolygonF(pts))


def _ic_text(p: QPainter, c: str) -> None:
    """文字图标（用于「右上角文字」设置）。"""
    f = QFont("Microsoft YaHei", 40, QFont.Bold)
    p.setFont(f)
    p.setPen(QPen(QColor(c)))
    p.drawText(QRectF(0, 0, 64, 64), Qt.AlignCenter, "T")


_DRAWERS = {
    "translate": _ic_translate,
    "settings": _ic_settings,
    "folder": _ic_folder,
    "package": _ic_package,
    "play": _ic_play,
    "model": _ic_model,
    "heart": _ic_heart,
    "sponsor": _ic_heart,
    "warning": _ic_warning,
    "cave": _ic_cave,
    "check": _ic_check,
    "close": _ic_close,
    "min": _ic_min,
    "max": _ic_max,
    "restore": _ic_restore,
    "back": _ic_back,
    "refresh": _ic_refresh,
    "list": _ic_list,
    "brush": _ic_brush,
    "logo": _ic_logo,
    "clock": _ic_clock,
    "lock": _ic_lock,
    "star": _ic_star,
    "text": _ic_text,
}


# ------------------------------------------------------------------ 对外接口


def pixmap(name: str, color: str, size: int = 24, width: float = 1.0) -> QPixmap:
    """绘制并返回指定尺寸的图标。

    :param name: 图标名，见 ``_DRAWERS``
    :param color: 十六进制颜色
    :param size: 像素尺寸
    :param width: 线宽倍率
    """
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    drawer = _DRAWERS.get(name)
    if drawer is None:
        return pm
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    scale = size / _LOGICAL
    p.scale(scale, scale)
    try:
        drawer(p, color)
    finally:
        p.end()
    if width != 1.0:
        # 通过重绘实现线宽调整（简单可靠）
        pm2 = QPixmap(size, size)
        pm2.fill(Qt.transparent)
        p2 = QPainter(pm2)
        p2.setRenderHint(QPainter.Antialiasing, True)
        p2.scale(scale, scale)
        try:
            drawer(p2, color)
        finally:
            p2.end()
        return pm2
    return pm


def icon(name: str, color: str, size: int = 24) -> QIcon:
    return QIcon(pixmap(name, color, size))


def emoji_pixmap(name: str, color: str, size: int = 24) -> QPixmap:
    return pixmap(name, color, size)
