# -*- coding: utf-8 -*-
"""矢量图标：全部用 QPainter 现场绘制，零外部图片资源。

好处：``--onefile`` 打包不会踩 ``sys._MEIPASS`` 的资源路径坑，且可任意换色/换尺寸不失真。
每个图标都在 64x64 的逻辑坐标里画，最后统一 ``p.scale()`` 到目标尺寸。
"""
from __future__ import annotations

import math
import os

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QFontMetricsF,
                           QIcon, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap, QPolygonF, QRadialGradient)

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


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    """在两个颜色之间线性插值（t=0 取 a，t=1 取 b）。"""
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


#: 品牌色兜底值（与 ``theme.C.BRAND`` 保持一致）。传入色非法时用它
_LOGO_FALLBACK = "#1565C0"
#: 小于该像素尺寸时不再画文字 —— 三个字符会糊成一团，只留剪影更干净
_LOGO_TEXT_MIN_PX = 40

#: 主 logo（八边形）：外接圆半径 / 圆角 / 垂直中心
_OCTA_R = 26.0
#: 圆角不能给太大 —— 超过斜切边长的一半就把 45° 角磨圆了，整体会读成
#: 「圆角正方形」而不是八边形。4.0 是「够软且角仍在」的临界值
_OCTA_CORNER = 4.0
_OCTA_CY = 32.5

#: 对比版 logo（七边形）：半径按外接盒与八边形对齐，cy 让边界盒垂直居中
_HEPTA_R = 25.0
_HEPTA_CORNER = 4.0
_HEPTA_CY = 33.2


def _polygon_points(cx: float, cy: float, r: float, n: int,
                    start_deg: float = -90.0) -> QPolygonF:
    """正 n 边形顶点表。``start_deg`` 是 ``at(0)`` 的极角（度，顺时针为正）。"""
    pts = []
    for i in range(n):
        a = math.radians(start_deg + i * 360.0 / n)
        pts.append(QPointF(cx + r * math.cos(a), cy + r * math.sin(a)))
    return QPolygonF(pts)


def _octagon_points(cx: float, cy: float, r: float) -> QPolygonF:
    """切角正方形（flat-top）正八边形 —— 仿 PCL2 启动器图标。

    上下左右是四条平边，四个角做 45° 斜切。``at(0)`` 起于左上顶点、顺时针排：
    ``0/1`` 顶边两端、``2/3`` 右边两端、``4/5`` 底边两端、``6/7`` 左边两端。
    """
    return _polygon_points(cx, cy, r, 8, -112.5)


def _heptagon_points(cx: float, cy: float, r: float) -> QPolygonF:
    """顶点朝上的正七边形（对比版）。``at(0)`` 是正上方的尖顶。"""
    return _polygon_points(cx, cy, r, 7, -90.0)


def _rounded_path(pts: QPolygonF, radius: float, closed: bool = True) -> QPainterPath:
    """给多边形 / 折线倒圆角，返回真实轮廓路径。

    比「粗描边 + RoundJoin」那种取巧写法更好用：描边法拿不到轮廓，
    而这里的路径可以直接 ``setClipPath``，才能做「高光只出现在图形内部」这种效果。
    """
    n = pts.count()
    path = QPainterPath()

    def corner(v: QPointF, pv: QPointF, nv: QPointF, move: bool) -> None:
        vp = (pv.x() - v.x(), pv.y() - v.y())
        vn = (nv.x() - v.x(), nv.y() - v.y())
        lp = math.hypot(*vp) or 1.0
        ln = math.hypot(*vn) or 1.0
        rr = min(radius, lp * 0.5, ln * 0.5)
        a = QPointF(v.x() + vp[0] / lp * rr, v.y() + vp[1] / lp * rr)
        b = QPointF(v.x() + vn[0] / ln * rr, v.y() + vn[1] / ln * rr)
        path.moveTo(a) if move else path.lineTo(a)
        path.quadTo(v, b)

    if closed:
        for i in range(n):
            corner(pts.at(i), pts.at((i - 1) % n), pts.at((i + 1) % n), i == 0)
        path.closeSubpath()
    else:
        path.moveTo(pts.at(0))
        for i in range(1, n - 1):
            corner(pts.at(i), pts.at(i - 1), pts.at(i + 1), False)
        path.lineTo(pts.at(n - 1))
    return path


#: 图标文字用的「微软标准英文字体」（Segoe UI）。按优先级尝试手动加载字体文件 ——
#: 离屏 / 无桌面环境里 ``QFontDatabase.families()`` 实测为 0（返回 0 个家族），
#: 此时直接 ``drawText`` 会静默渲染成「豆腐块」方框并写进交付文件（不报错、不崩溃）；
#: 只有显式 ``addApplicationFont`` 加载 ttf，才能拿到真正可用的家族名。
_FONT_CANDIDATES = (
    "C:/Windows/Fonts/segoeuib.ttf",   # Segoe UI Bold
    "C:/Windows/Fonts/seguisb.ttf",    # Segoe UI Semibold
    "C:/Windows/Fonts/segoeui.ttf",    # Segoe UI Regular
    "C:/Windows/Fonts/arialbd.ttf",    # 最后的兜底
)
_latin_family: str | None = None


def _latin_font_family() -> str:
    """返回可用的拉丁字体家族名（首次调用时加载并缓存）；全失败则返回空串。"""
    global _latin_family
    if _latin_family is None:
        _latin_family = ""
        for path in _FONT_CANDIDATES:
            if not os.path.isfile(path):
                continue
            fid = QFontDatabase.addApplicationFont(path)
            if fid == -1:
                continue
            fams = QFontDatabase.applicationFontFamilies(fid)
            if fams:
                _latin_family = fams[0]
                break
    return _latin_family


def _draw_sl1(p: QPainter, color: str = "#FFFFFF",
              offset: tuple[float, float] = (0.0, 0.0),
              alpha: int = 255, scale: float = 1.0) -> None:
    """用微软标准英文字体（Segoe UI）绘制「SL1」。

    字体经 ``_latin_font_family`` 显式加载；万一一个都加载不到，就回退到
    ``_draw_sl1_vector`` 的矢量描边 —— 宁可字形与预期有出入，也绝不能把
    「豆腐块」方框写进交付的图标里。
    """
    family = _latin_font_family()
    if not family:
        _draw_sl1_vector(p, color, offset, alpha, scale)
        return

    col = QColor(color)
    col.setAlpha(alpha)

    dev = p.device()
    px = dev.width() if dev is not None else 64

    f = QFont(family)
    # 20px 时「SL1」实测宽 33 / 大写高 14 个逻辑单位，与原矢量字
    # （宽 32.5 / 高 15）的占位基本一致 —— 再大就会把八边形的留白吃光
    f.setPixelSize(20)
    f.setBold(True)
    if px < 64:
        # 小尺寸下笔画会被抗锯齿吃掉，用更重的字重顶住（与矢量版的反向加粗同理）
        f.setWeight(QFont.Weight.ExtraBold)
    fm = QFontMetricsF(f)

    text = "SL1"
    w = fm.horizontalAdvance(text)
    cap = fm.capHeight()

    dx, dy = offset
    p.save()
    p.translate(dx, dy)
    if scale != 1.0:
        # 以文字中心为基准缩放，留出更舒展的四周留白（现代图标讲究留白）
        p.translate(32.0, 32.5)
        p.scale(scale, scale)
        p.translate(-32.0, -32.5)
    p.setFont(f)
    p.setPen(QPen(col))
    p.setBrush(Qt.NoBrush)
    # 按「大写字母高度」垂直居中：baseline = 中心 + capHeight / 2
    p.drawText(QPointF(32.0 - w / 2.0, 32.5 + cap / 2.0), text)
    p.restore()


def _draw_sl1_vector(p: QPainter, color: str = "#FFFFFF",
                     offset: tuple[float, float] = (0.0, 0.0),
                     alpha: int = 255, scale: float = 1.0) -> None:
    """矢量描边版「SL1」—— 字体加载失败时的兜底，零字体依赖。

    字形用直线 + 三次贝塞尔手工拼，任何机器上都是同一个样子，
    代价是不如真字体标准。
    """
    y_top, y_bot = 25.0, 40.0          # 垂直居中于八边形中心（cy = 32.5）
    y_mid = (y_top + y_bot) / 2.0

    col = QColor(color)
    col.setAlpha(alpha)
    # 小尺寸下三个字符的笔画间隙会被抗锯齿填满、糊成一团：
    # 按 64px 基准反向加粗，把「S / L / 1」的形状保住（上限 1.9 倍，再粗就糊实了）
    dev = p.device()
    px = dev.width() if dev is not None else 64
    lw = 2.4 * max(1.0, min(1.9, 64.0 / max(px, 20)))
    pen = QPen(col, lw)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    dx, dy = offset
    p.save()
    p.translate(dx, dy)
    if scale != 1.0:
        # 以文字中心为基准缩放，留出更舒展的四周留白（现代图标讲究留白）
        p.translate(32.0, 32.5)
        p.scale(scale, scale)
        p.translate(-32.0, -32.5)

    # S：上弧 → 左上竖 → 中段 S 弯 → 右下竖 → 下弧
    # 拐角要带弧度，纯直角会读成「5」
    r = 3.2
    path = QPainterPath()
    path.moveTo(24.5, y_top + r)
    path.cubicTo(24.5, y_top, 15.5, y_top, 15.5, y_top + r)
    path.lineTo(15.5, y_mid - r)
    path.cubicTo(15.5, y_mid, 24.5, y_mid, 24.5, y_mid + r)
    path.lineTo(24.5, y_bot - r)
    path.cubicTo(24.5, y_bot, 15.5, y_bot, 15.5, y_bot - r)
    p.drawPath(path)

    # L：左竖 + 下横
    path = QPainterPath()
    path.moveTo(28.5, y_top)
    path.lineTo(28.5, y_bot)
    path.lineTo(37.5, y_bot)
    p.drawPath(path)

    # 1：左上斜旗 + 竖 + 底座
    path = QPainterPath()
    path.moveTo(41.5, y_top + 4.0)
    path.lineTo(45.0, y_top)
    path.lineTo(45.0, y_bot)
    path.moveTo(41.5, y_bot)
    path.lineTo(48.0, y_bot)
    p.drawPath(path)

    p.restore()


def _logo_core(p: QPainter, c: str, pts_func, r: float, corner: float,
               cy: float) -> None:
    """logo 的公共绘制：主渐变 → 内部光影 → 「SL1」文字。

    ``pts_func`` 决定轮廓（八边形 / 七边形共用同一套上色与文字逻辑），
    两个版本除形状外完全一致，对比时才不会被光影差异干扰。

    刻意**不做外投影**：烘死在 ico 里的阴影在浅色桌面上会糊成一圈灰边，
    而且 Windows 自己会给图标加阴影，重复叠加只会显旧。
    """
    base = QColor(c)
    if not base.isValid():
        base = QColor(_LOGO_FALLBACK)

    cx = 32.0
    outer = pts_func(cx, cy, r)
    n = outer.count()
    shape = _rounded_path(outer, corner)

    dev = p.device()
    px = dev.width() if dev is not None else 64

    # 1) 主渐变：左上亮青蓝 → 品牌色 → 右下深色。
    #    高光色必须与品牌色同调 —— 冷色底混暖色（原先写死的橘红 #FF8A6B）
    #    是互补色相混，会直接糊成灰紫色。
    grad = QLinearGradient(13.0, 7.0, 51.0, 58.0)
    grad.setColorAt(0.00, _mix(base, QColor("#6FD8FF"), 0.50))
    grad.setColorAt(0.46, base)
    grad.setColorAt(1.00, _mix(base, QColor("#000000"), 0.42))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(grad))
    p.drawPath(shape)

    # 2) 内部光影：左上柔光 + 底部压深 + 顶部贴边细亮线。
    #    全部裁剪在轮廓内 —— 描边有一半宽度在路径外侧，不裁剪会溢出。
    p.save()
    p.setClipPath(shape)

    glow = QRadialGradient(QPointF(21.0, 12.0), 38.0)
    glow.setColorAt(0.0, QColor(255, 255, 255, 52))
    glow.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setBrush(QBrush(glow))
    p.drawPath(shape)

    deep = _mix(base, QColor("#000000"), 0.55)
    deep.setAlpha(78)
    shade = QLinearGradient(0.0, 32.0, 0.0, 58.0)
    shade.setColorAt(0.0, QColor(0, 0, 0, 0))
    shade.setColorAt(1.0, deep)
    p.setBrush(QBrush(shade))
    p.drawPath(shape)

    # 只画顶部三段（前一条边 / 顶边 / 后一条边），不画整圈 ——
    # 整圈会变成「描边感」，一眼就是旧风格
    inner = pts_func(cx, cy, r - 1.3)
    top = _rounded_path(QPolygonF([inner.at(n - 1), inner.at(0), inner.at(1)]),
                        max(corner - 1.0, 1.0), closed=False)
    top_pen = QPen(QColor(255, 255, 255, 92), 1.5)
    top_pen.setCapStyle(Qt.RoundCap)
    top_pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(top_pen)
    p.setBrush(Qt.NoBrush)
    p.drawPath(top)
    p.restore()

    # 3) 文字：小尺寸下省略，避免糊成一团
    if px < _LOGO_TEXT_MIN_PX:
        return
    # 文字投影同样由品牌色推导 —— 原先写死暗红 #5A0A10，换冷色底后同样会发脏
    _draw_sl1(p, _mix(base, QColor("#000000"), 0.72).name(), (0.0, 0.8), 45, 1.0)
    _draw_sl1(p)


def _ic_logo(p: QPainter, c: str) -> None:
    """品牌标识：圆角八边形 + 「SL1」字样（冷调蓝）。

    形状仿 PCL2 启动器图标 —— 切角正方形，四条平边 + 四个 45° 斜角。
    颜色由传入的 ``c`` 推导（亮 → 本色 → 深色三段），
    但调用方传的是固定的 ``C.BRAND``，所以它**不随界面强调色变化**。
    """
    _logo_core(p, c, _octagon_points, _OCTA_R, _OCTA_CORNER, _OCTA_CY)


def _ic_logo_heptagon(p: QPainter, c: str) -> None:
    """对比版：圆角七边形 + 「SL1」字样，除轮廓外与 ``_ic_logo`` 完全一致。"""
    _logo_core(p, c, _heptagon_points, _HEPTA_R, _HEPTA_CORNER, _HEPTA_CY)


def _ic_logo_mono(p: QPainter, c: str) -> None:
    """单色剪影版 logo（标题栏用）。

    标题栏是「小尺寸 + 深色底」的场景：渐变和内部光影在这个尺度下只会糊成
    一个白球，反而看不出八边形。这里只保留轮廓本身，剪影更清楚。
    """
    shape = _rounded_path(_octagon_points(32.0, 32.5, _OCTA_R), _OCTA_CORNER)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(c)))
    p.drawPath(shape)


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
    "logo_mono": _ic_logo_mono,
    "logo_heptagon": _ic_logo_heptagon,
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
