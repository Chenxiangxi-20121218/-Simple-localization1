# -*- coding: utf-8 -*-
"""通用自绘控件库。

PCL2 质感的几个关键点都在这里：
* ``BigButton``：灰→白 状态切换用自绘 ``paintEvent``，不依赖 QSS 的 ``:disabled``。
* ``TitleBar``：无边框窗口 + 原生 ``startSystemMove`` 拖动 + 渐变标题栏。
* ``FlowLayout``：模组卡片网格，比 ``QListWidget`` 的 IconMode 灵活得多。
"""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRect,
                            QRectF, QSize, Qt, QTimer, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient,
                           QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                               QLabel, QLayout, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget, QWidgetItem)

from . import icons
from .theme import C


# ================================================================== 基础容器


class Card(QFrame):
    """白色圆角卡片，可选标题与阴影。"""

    def __init__(self, title: str = "", parent: QWidget | None = None,
                 shadow: bool = True, padding: int = 16):
        super().__init__(parent)
        self.setObjectName("Card")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(padding, padding, padding, padding)
        self._outer.setSpacing(10)

        self.header = QHBoxLayout()
        self.header.setSpacing(8)
        self._outer.addLayout(self.header)

        self.title_label: QLabel | None = None
        if title:
            self.title_label = QLabel(title)
            self.title_label.setObjectName("CardTitle")
            self.header.addWidget(self.title_label)
        self.header.addStretch(1)

        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        self._outer.addLayout(self.body)

        if shadow:
            eff = QGraphicsDropShadowEffect(self)
            eff.setBlurRadius(18)
            eff.setOffset(0, 3)
            eff.setColor(QColor(0, 0, 0, 26))
            self.setGraphicsEffect(eff)

    def add(self, w) -> None:
        if isinstance(w, QLayout):
            self.body.addLayout(w)
        else:
            self.body.addWidget(w)

    def add_stretch(self, n: int = 1) -> None:
        self.body.addStretch(n)

    def add_header_widget(self, w) -> None:
        self.header.addWidget(w)


class Separator(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background:{C.BORDER_SOFT};border:none;")


class EmptyHint(QLabel):
    """空状态提示（居中灰字）。"""

    def __init__(self, text: str, icon_name: str = "package", parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(150)
        self.setStyleSheet(f"color:{C.TEXT_SUB};font-size:13px;")
        self.set_icon_text(text, icon_name)

    def set_icon_text(self, text: str, icon_name: str = "package") -> None:
        self.setText(f"\n\n{text}")


# ================================================================== 大按钮


class BigButton(QPushButton):
    """主操作大按钮：不可用=灰色，可用=白色，悬停=白底蓝框。

    自绘而不是套 QSS —— ``QPushButton:disabled`` 在不同 Qt 版本表现不一致。
    """

    def __init__(self, text: str, icon_name: str = "play", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.ForbiddenCursor)
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._hover = False
        self._pressed = False
        self._icon_name = icon_name
        self.setFont(QFont("Microsoft YaHei UI", 15, QFont.DemiBold))
        self.setEnabled(False)

    def set_icon_name(self, name: str) -> None:
        self._icon_name = name
        self.update()

    # -------- 状态 --------
    def setEnabled(self, on: bool) -> None:  # noqa: N802
        super().setEnabled(on)
        self.setCursor(Qt.PointingHandCursor if on else Qt.ForbiddenCursor)
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._pressed = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if self.isEnabled():
            self._pressed = True
            self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        if not self.isEnabled():
            bg, fg, border = C.DIS_BG, C.DIS_TEXT, C.DIS_BG
        else:
            bg = "#FFFFFF"
            fg = C.BLUE
            border = C.BLUE if (self._hover or self._pressed) else C.BORDER
            if self._pressed:
                bg = C.BLUE_PALE

        path = QPainterPath()
        path.addRoundedRect(r, 10, 10)
        p.fillPath(path, QBrush(QColor(bg)))
        p.setPen(QPen(QColor(border), 1.4))
        p.drawPath(path)

        # 图标 + 文字
        txt = self.text()
        fm = QFontMetrics(self.font())
        tw = fm.horizontalAdvance(txt)
        gap = 10
        iw = 22
        total = tw + gap + iw
        x0 = (self.width() - total) / 2
        pm = icons.pixmap(self._icon_name, fg, 22)
        p.drawPixmap(int(x0), int((self.height() - 22) / 2), pm)
        p.setPen(QPen(QColor(fg)))
        p.setFont(self.font())
        p.drawText(QRectF(x0 + iw + gap, 0, tw + 4, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, txt)
        p.end()


# ================================================================== 普通按钮


class IconButton(QPushButton):
    """带矢量图标的小按钮。"""

    def __init__(self, text: str, icon_name: str, color: str | None = None,
                 parent=None, primary: bool = False):
        super().__init__(text, parent)
        self._icon_name = icon_name
        self._color = color or C.TEXT
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(34)
        self.setIconSize(QSize(16, 16))
        self.setIcon(icons.icon(icon_name, "#FFFFFF" if primary else self._color, 16))
        if primary:
            self.setObjectName("Primary")

    def recolor(self) -> None:
        self.setIcon(icons.icon(self._icon_name, self._color, 16))


class NavItem(QPushButton):
    """侧边栏导航项（自绘选中态）。"""

    def __init__(self, key: str, text: str, icon_name: str, parent=None):
        super().__init__(text, parent)
        self.key = key
        self._icon_name = icon_name
        self._active = False
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)
        self.setFont(QFont("Microsoft YaHei UI", 12))
        self.setCheckable(False)

    def set_active(self, on: bool) -> None:
        self._active = on
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(6, 2, -6, -2)
        path = QPainterPath()
        path.addRoundedRect(r, 8, 8)
        if self._active:
            p.fillPath(path, QBrush(QColor(C.BLUE_PALE)))
        elif self._hover:
            p.fillPath(path, QBrush(QColor(C.HOVER)))

        if self._active:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(C.BLUE)))
            p.drawRoundedRect(QRectF(2, r.top() + 8, 3, r.height() - 16), 1.5, 1.5)

        color = C.BLUE if self._active else C.TEXT_SUB
        pm = icons.pixmap(self._icon_name, color, 20)
        p.drawPixmap(18, int((self.height() - 20) / 2), pm)
        p.setPen(QPen(QColor(color)))
        f = QFont("Microsoft YaHei UI", 12)
        f.setBold(self._active)
        p.setFont(f)
        p.drawText(QRectF(48, 0, self.width() - 56, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()


# ================================================================== FlowLayout


class FlowLayout(QLayout):
    """自动换行的流式布局（模组卡片网格）。"""

    def __init__(self, parent=None, margin: int = 0, hspacing: int = 12, vspacing: int = 12):
        super().__init__(parent)
        self._items: list[QWidgetItem] = []
        self._h = hspacing
        self._v = vspacing
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item):  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, i):  # noqa: N802
        if 0 <= i < len(self._items):
            return self._items[i]
        return None

    def takeAt(self, i):  # noqa: N802
        if 0 <= i < len(self._items):
            return self._items.pop(i)
        return None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for it in self._items:
            size = size.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        eff = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = eff.x(), eff.y(), 0
        for it in self._items:
            w = it.sizeHint().width()
            h = it.sizeHint().height()
            if x + w > eff.right() + 1 and line_h > 0:
                x = eff.x()
                y += line_h + self._v
                line_h = 0
            if not test_only:
                it.setGeometry(QRect(QPoint(x, y), QSize(w, h)))
            x += w + self._h
            line_h = max(line_h, h)
        return y + line_h - rect.y() + m.bottom()


# ================================================================== 模组卡片


class ModCard(QFrame):
    """模组卡片：图标 + 中文名 + 英文名，右上角勾选角标。"""

    toggled = Signal(str, bool)

    W, H = 150, 172

    def __init__(self, mod_id: str, cn_name: str, en_name: str,
                 icon_pm=None, parent=None):
        super().__init__(parent)
        self.mod_id = mod_id
        self.cn_name = cn_name
        self.en_name = en_name
        self._icon_pm = icon_pm
        self._selected = False
        self._hover = False
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{cn_name}\n{en_name}\n{mod_id}")

    def set_selected(self, on: bool) -> None:
        if self._selected != on:
            self._selected = on
            self.update()

    def is_selected(self) -> bool:
        return self._selected

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._selected = not self._selected
            self.update()
            self.toggled.emit(self.mod_id, self._selected)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 10, 10)

        if self._selected:
            p.fillPath(path, QBrush(QColor(C.BLUE_PALE)))
            p.setPen(QPen(QColor(C.BLUE), 1.6))
        elif self._hover:
            p.fillPath(path, QBrush(QColor("#FFFFFF")))
            p.setPen(QPen(QColor(C.BLUE_LIGHT), 1.2))
        else:
            p.fillPath(path, QBrush(QColor("#FFFFFF")))
            p.setPen(QPen(QColor(C.BORDER), 1.0))
        p.drawPath(path)

        # 图标
        ix = int((self.W - 64) / 2)
        if self._icon_pm is not None and not self._icon_pm.isNull():
            p.drawPixmap(ix, 16, 64, 64, self._icon_pm)
        else:
            p.drawPixmap(ix, 16, icons.pixmap("package", C.BLUE_LIGHT, 64))

        # 中文名
        f = QFont("Microsoft YaHei UI", 11)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(QColor(C.TEXT)))
        cn_rect = QRectF(8, 90, self.W - 16, 34)
        fm = QFontMetrics(f)
        p.drawText(cn_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
                   fm.elidedText(self.cn_name, Qt.ElideRight, (self.W - 16) * 2))

        # 英文名
        f2 = QFont("Segoe UI", 9)
        p.setFont(f2)
        p.setPen(QPen(QColor(C.TEXT_SUB)))
        fm2 = QFontMetrics(f2)
        p.drawText(QRectF(8, 130, self.W - 16, 16), Qt.AlignHCenter | Qt.AlignTop,
                   fm2.elidedText(self.en_name, Qt.ElideRight, self.W - 16))

        # 勾选角标
        bx, by = self.W - 30, 8
        if self._selected:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(C.BLUE)))
            p.drawEllipse(QRectF(bx, by, 22, 22))
            p.drawPixmap(bx + 3, by + 3, icons.pixmap("check", "#FFFFFF", 16))
        else:
            p.setPen(QPen(QColor(C.BORDER), 1.4))
            p.setBrush(QBrush(QColor("#FFFFFF")))
            p.drawEllipse(QRectF(bx, by, 22, 22))
        p.end()


# ================================================================== 汉化包行


class PackRow(QFrame):
    """汉化包管理列表中的一行（自绘复选框）。"""

    toggled = Signal(str, bool)

    def __init__(self, pack_id: str, name: str, detail: str, parent=None):
        super().__init__(parent)
        self.pack_id = pack_id
        self._name = name
        self._detail = detail
        self._checked = False
        self._hover = False
        self.setFixedHeight(54)
        self.setCursor(Qt.PointingHandCursor)

    def set_checked(self, on: bool) -> None:
        self._checked = on
        self.update()

    def is_checked(self) -> bool:
        return self._checked

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._checked = not self._checked
            self.update()
            self.toggled.emit(self.pack_id, self._checked)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 8, 8)
        p.fillPath(path, QBrush(QColor(C.HOVER if self._hover else "#FFFFFF")))
        p.setPen(QPen(QColor(C.BORDER_SOFT), 1))
        p.drawPath(path)

        # 勾选框
        bx, by = 14, (self.height() - 20) / 2
        if self._checked:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(C.BLUE)))
            p.drawRoundedRect(QRectF(bx, by, 20, 20), 5, 5)
            p.drawPixmap(int(bx) + 3, int(by) + 3, icons.pixmap("check", "#FFFFFF", 14))
        else:
            p.setPen(QPen(QColor(C.BORDER), 1.4))
            p.setBrush(QBrush(QColor("#FFFFFF")))
            p.drawRoundedRect(QRectF(bx, by, 20, 20), 5, 5)

        p.drawPixmap(46, int((self.height() - 22) / 2), icons.pixmap("package", C.BLUE_LIGHT, 22))

        f = QFont("Microsoft YaHei UI", 11)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(QColor(C.TEXT)))
        p.drawText(QRectF(78, 8, self.width() - 240, 20), Qt.AlignVCenter | Qt.AlignLeft, self._name)

        f2 = QFont("Microsoft YaHei UI", 9)
        p.setFont(f2)
        p.setPen(QPen(QColor(C.TEXT_SUB)))
        p.drawText(QRectF(78, 28, self.width() - 240, 18), Qt.AlignVCenter | Qt.AlignLeft, self._detail)

        # 状态徽标
        badge = "已启用" if self._checked else "已禁用"
        col = C.OK if self._checked else C.TEXT_SUB
        f3 = QFont("Microsoft YaHei UI", 10)
        p.setFont(f3)
        fm = QFontMetrics(f3)
        bw = fm.horizontalAdvance(badge) + 20
        br = QRectF(self.width() - bw - 16, (self.height() - 24) / 2, bw, 24)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(C.OK if self._checked else C.DIS_BG)))
        if not self._checked:
            p.setBrush(QBrush(QColor("#EDF0F3")))
        p.drawRoundedRect(br, 12, 12)
        p.setPen(QPen(QColor("#FFFFFF" if self._checked else C.TEXT_SUB)))
        p.drawText(br, Qt.AlignCenter, badge)
        p.end()


# ================================================================== Toast


class Toast(QLabel):
    """右下角浮层提示。"""

    def __init__(self, parent: QWidget, text: str, msec: int = 2200):
        super().__init__(text, parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(False)
        self.adjustSize()
        self.setFixedHeight(max(38, self.height() + 16))
        self.setMinimumWidth(self.width() + 28)
        self._reposition()
        self.show()
        self.raise_()
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(220)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()
        QTimer.singleShot(msec, self._fade_out)

    def _reposition(self) -> None:
        par = self.parentWidget()
        if par is None:
            return
        x = par.width() - self.width() - 28
        y = par.height() - self.height() - 28
        self.move(max(0, x), max(0, y))

    def _fade_out(self) -> None:
        self._anim2 = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim2.setDuration(300)
        self._anim2.setStartValue(1.0)
        self._anim2.setEndValue(0.0)
        self._anim2.finished.connect(self.deleteLater)
        self._anim2.start()


def toast(parent: QWidget, text: str, msec: int = 2200) -> Toast:
    return Toast(parent, text, msec)


# ================================================================== 标题栏


class TitleBar(QWidget):
    """无边框窗口标题栏：左侧图标+标题，右侧最小化/最大化/关闭。"""

    def __init__(self, title: str, parent=None, brand_icon: str = "logo_mono"):
        super().__init__(parent)
        self.setFixedHeight(38)
        self._title = title
        self._brand = brand_icon
        self._hover_btn: QPushButton | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 6, 0)
        lay.setSpacing(2)
        lay.addStretch(1)

        self.btn_min = self._mk("min")
        self.btn_max = self._mk("max")
        self.btn_close = self._mk("close")
        self.btn_close.setObjectName("TitleClose")
        self.btn_min.clicked.connect(lambda: self.window().showMinimized())
        self.btn_max.clicked.connect(self._toggle_max)
        self.btn_close.clicked.connect(lambda: self.window().close())
        for b in (self.btn_min, self.btn_max, self.btn_close):
            lay.addWidget(b)

    def _mk(self, name: str) -> QPushButton:
        b = QPushButton(self)
        b.setObjectName("TitleBtn")
        b.setFixedSize(44, 38)
        b.setIcon(icons.icon(name, "#FFFFFF", 15))
        b.setCursor(Qt.PointingHandCursor)
        b.setFlat(True)
        return b

    def _toggle_max(self) -> None:
        w = self.window()
        if w.isMaximized():
            w.showNormal()
            self.btn_max.setIcon(icons.icon("max", "#FFFFFF", 15))
        else:
            w.showMaximized()
            self.btn_max.setIcon(icons.icon("restore", "#FFFFFF", 15))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0.0, QColor(C.TITLE_TOP))
        g.setColorAt(1.0, QColor(C.TITLE_BOTTOM))
        p.fillRect(self.rect(), QBrush(g))

        # 26px 是「八边形斜角还看得出来」的下限；再小就糊成白色圆球了
        p.drawPixmap(12, int((self.height() - 26) / 2), icons.pixmap(self._brand, "#FFFFFF", 26))
        p.setPen(QPen(QColor("#FFFFFF")))
        f = QFont("Microsoft YaHei UI", 11)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(46, 0, self.width() - 200, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self._title)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            h = self.window().windowHandle()
            if h:
                h.startSystemMove()

    def mouseDoubleClickEvent(self, e):
        self._toggle_max()


# ================================================================== 工具函数


def hline() -> Separator:
    return Separator()


def label(text: str, obj: str = "", size: int = 13, bold: bool = False,
          color: str | None = None, wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    if obj:
        lb.setObjectName(obj)
    f = QFont("Microsoft YaHei UI", size)
    f.setBold(bold)
    lb.setFont(f)
    if color:
        lb.setStyleSheet(f"color:{color};")
    lb.setWordWrap(wrap)
    return lb


def icon_label(name: str, color: str, size: int = 18) -> QLabel:
    lb = QLabel()
    lb.setPixmap(icons.pixmap(name, color, size))
    lb.setFixedSize(size, size)
    return lb
