# -*- coding: utf-8 -*-
"""主题与配色（PCL2 风格）。

设计要点：
1. 颜色统一走 ``C`` 常量类，支持「个性化」里用户自定义强调色 / 边框色。
2. QSS 使用 ``string.Template``（``$VAR`` 占位）而不是 f-string，避免 ``{}`` 转义地狱。
"""
from __future__ import annotations

from string import Template

# ---------------------------------------------------------------- 颜色常量


class C:
    """全局配色。"""

    # 品牌色（只给 logo 用）—— 2026-10-04 按用户要求由暖红改为冷调蓝。
    # 与界面强调色 C.BLUE 解耦：apply_accent 刻意不碰它，
    # 否则 config.json 里的 accent_color 会在启动时把 logo 顶成另一个颜色。
    BRAND = "#1565C0"

    # 品牌蓝（可被用户个性化覆盖，见 apply_accent）
    BLUE = "#2E6DB4"
    BLUE_DARK = "#1B4A80"
    BLUE_LIGHT = "#4A8FD4"
    BLUE_PALE = "#E8F1FB"

    # 标题栏渐变
    TITLE_TOP = "#3A7CC3"
    TITLE_BOTTOM = "#1E4E86"

    # 背景 / 卡片
    BG = "#EEF1F5"
    BG_SIDE = "#F7F9FC"
    CARD = "#FFFFFF"
    CARD_ALT = "#F5F7FA"

    # 文字
    TEXT = "#2B2F36"
    TEXT_SUB = "#7C838C"
    TEXT_ON_BLUE = "#FFFFFF"

    # 边框
    BORDER = "#DCE1E8"
    BORDER_SOFT = "#EAEEF3"

    # 状态
    OK = "#2FA84F"
    WARN = "#E8A33D"
    ERR = "#D9534F"

    # 禁用态（灰按钮）
    DIS_BG = "#E3E7EC"
    DIS_TEXT = "#A9B0B8"

    # 悬停
    HOVER = "#F0F4F9"
    HOVER_BLUE = "#F4F9FF"

    # 进度条
    PROGRESS_BG = "#E3E7EC"

    # 阴影
    SHADOW = "#C9D2DC"


#: 边框色 / 强调色 可在设置里改，运行时通过 apply_accent 更新
BORDER_COLOR = C.BORDER
ACCENT_COLOR = C.BLUE


def apply_accent(accent: str | None = None, border: str | None = None) -> None:
    """应用用户个性化配色（强调色 + 边框色）。"""
    global BORDER_COLOR, ACCENT_COLOR
    if accent:
        C.BLUE = accent
        ACCENT_COLOR = accent
    if border:
        C.BORDER = border
        BORDER_COLOR = border


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 46, 109, 180


def mix(color: str, other: str, ratio: float) -> str:
    """按比例混合两个十六进制颜色（ratio=0 返回 color）。"""
    r1, g1, b1 = _hex_to_rgb(color)
    r2, g2, b2 = _hex_to_rgb(other)
    r = round(r1 + (r2 - r1) * ratio)
    g = round(g1 + (g2 - g1) * ratio)
    b = round(b1 + (b2 - b1) * ratio)
    return "#%02X%02X%02X" % (r, g, b)


def lighten(color: str, ratio: float = 0.2) -> str:
    return mix(color, "#FFFFFF", ratio)


def darken(color: str, ratio: float = 0.2) -> str:
    return mix(color, "#000000", ratio)


# ---------------------------------------------------------------- QSS


_QSS = Template(
    """
* { outline: none; }

QWidget {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: $TEXT;
}

#Root {
    background: $BG;
    border: 1px solid $BORDER;
    border-radius: 10px;
}

/* ---------------- 侧边栏 ---------------- */
#Sidebar {
    background: $BG_SIDE;
    border-right: 1px solid $BORDER_SOFT;
}

#SidebarBrand {
    color: $BLUE_DARK;
    font-size: 15px;
    font-weight: 600;
}

#SidebarVer {
    color: $TEXT_SUB;
    font-size: 11px;
}

/* ---------------- 内容区 ---------------- */
#PageTitle {
    font-size: 20px;
    font-weight: 600;
    color: $TEXT;
}

#PageSub {
    color: $TEXT_SUB;
    font-size: 12px;
}

#CardTitle {
    font-size: 14px;
    font-weight: 600;
    color: $TEXT;
}

#Card {
    background: $CARD;
    border: 1px solid $BORDER;
    border-radius: 10px;
}

#CardFlat {
    background: $CARD;
    border-radius: 10px;
}

#Hint {
    color: $TEXT_SUB;
    font-size: 12px;
}

#LogLine {
    color: $TEXT_SUB;
    font-size: 12px;
    font-family: "Consolas", "Microsoft YaHei UI", monospace;
}

#ModelName {
    font-size: 15px;
    font-weight: 600;
    color: $BLUE;
}

#ModelNone {
    font-size: 13px;
    color: $ERR;
}

#PathText {
    color: $TEXT_SUB;
    font-size: 12px;
    font-family: "Consolas", monospace;
}

#SponsorText {
    color: $TEXT_SUB;
    font-size: 12px;
}

#CaveText {
    color: $TEXT_SUB;
    font-size: 12px;
}

/* ---------------- 普通按钮 ---------------- */
QPushButton {
    background: $CARD;
    border: 1px solid $BORDER;
    border-radius: 7px;
    padding: 6px 14px;
    color: $TEXT;
}
QPushButton:hover {
    background: $HOVER_BLUE;
    border-color: $BLUE_LIGHT;
    color: $BLUE;
}
QPushButton:pressed {
    background: $BLUE_PALE;
}
QPushButton:disabled {
    background: $DIS_BG;
    color: $DIS_TEXT;
    border-color: $BORDER_SOFT;
}

QPushButton#Primary {
    background: $BLUE;
    border: 1px solid $BLUE;
    color: #FFFFFF;
    font-weight: 600;
}
QPushButton#Primary:hover {
    background: $BLUE_LIGHT;
    border-color: $BLUE_LIGHT;
    color: #FFFFFF;
}
QPushButton#Primary:pressed {
    background: $BLUE_DARK;
}

QPushButton#Ghost {
    background: transparent;
    border: none;
    color: $TEXT_SUB;
    padding: 4px 8px;
}
QPushButton#Ghost:hover {
    color: $BLUE;
    background: $HOVER_BLUE;
}

/* 标题栏按钮。
   ⚠️ 关闭按钮的 objectName 是 TitleClose 而不是 TitleBtn（Qt 一个控件只能有一个 objectName），
   所以基础规则必须把两个 #id 都列上，否则关闭按钮会掉进通用 QPushButton 样式变成「白底灰框」，
   而白色 X 画在白底上等于隐形。 */
QPushButton#TitleBtn, QPushButton#TitleClose {
    background: transparent;
    border: none;
    color: #FFFFFF;
    border-radius: 0px;
    padding: 0px;
}
QPushButton#TitleBtn:hover, QPushButton#TitleClose:hover {
    background: rgba(255, 255, 255, 0.18);
}
/* 必须放在上面那条之后：同优先级下后写的生效 */
QPushButton#TitleClose:hover {
    background: #E03B3B;
}

/* ---------------- 输入框 ---------------- */
QLineEdit, QComboBox, QSpinBox {
    background: $CARD;
    border: 1px solid $BORDER;
    border-radius: 7px;
    padding: 6px 10px;
    selection-background-color: $BLUE;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: $BLUE_LIGHT;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background: $CARD;
    border: 1px solid $BORDER;
    selection-background-color: $BLUE_PALE;
    selection-color: $TEXT;
    outline: none;
}

/* ---------------- 滚动条 ---------------- */
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #C6CFDA;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: $BLUE_LIGHT;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #C6CFDA;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* ---------------- 进度条 ---------------- */
QProgressBar {
    background: $PROGRESS_BG;
    border: none;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    color: $TEXT_SUB;
    font-size: 11px;
}
QProgressBar::chunk {
    background: $BLUE;
    border-radius: 6px;
}

/* ---------------- 复选框 ---------------- */
QCheckBox {
    spacing: 7px;
    color: $TEXT;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid $BORDER;
    border-radius: 4px;
    background: $CARD;
}
QCheckBox::indicator:hover {
    border-color: $BLUE_LIGHT;
}
QCheckBox::indicator:checked {
    background: $BLUE;
    border-color: $BLUE;
}

/* ---------------- 提示 ---------------- */
QToolTip {
    background: #33383F;
    color: #FFFFFF;
    border: none;
    border-radius: 5px;
    padding: 5px 8px;
}

#Toast {
    background: rgba(43, 47, 54, 0.94);
    color: #FFFFFF;
    border-radius: 8px;
    padding: 9px 16px;
    font-size: 13px;
}
"""
)


def qss() -> str:
    """生成当前配色的全局样式表。"""
    data = {k: v for k, v in vars(C).items() if isinstance(v, str)}
    data["BORDER"] = C.BORDER
    return _QSS.substitute(data)
