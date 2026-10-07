# -*- coding: utf-8 -*-
"""设置界面。

包含五块内容：翻译模型选择、翻译选项（强化翻译）、个性化（付费门禁）、赞助、
杂项（千万别点 + 回声洞）。整个页面放在 ``QScrollArea`` 里，窗口变小时可滚动。
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QUrl
from PySide6.QtGui import (QBrush, QColor, QDesktopServices, QFont, QFontMetrics,
                           QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QFileDialog, QFrame,
                               QHBoxLayout, QLineEdit, QMessageBox, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from .. import icons, paths
from ..core import translator
from ..state import APP_VERSION, DEFAULT_TRANSLATOR_TITLE, STATE
from ..theme import C
from ..widgets import Card, IconButton, icon_label, label, toast


class CaveBox(QFrame):
    """回声洞：双击随机显示一条冷知识。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CaveBox")
        self.setStyleSheet(
            f"#CaveBox {{ background:{C.CARD_ALT}; border-radius:8px; }}")
        self.setMinimumHeight(76)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("双击我，听一句冷知识")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(icon_label("cave", C.BLUE_LIGHT, 20))
        head.addWidget(label("回声洞", bold=True))
        head.addStretch(1)
        lay.addLayout(head)

        self.text_label = label("双击此处，随机显示一条冷知识", obj="CaveText", wrap=True)
        lay.addWidget(self.text_label)

    def mouseDoubleClickEvent(self, e):
        self.text_label.setText(STATE.random_lengzhishi())
        super().mouseDoubleClickEvent(e)


class CheckOption(QCheckBox):
    """自绘复选框：蓝底 + 白色矢量对勾。

    为什么不用原生 indicator：QSS 里 ``QCheckBox::indicator:checked`` 只能画出一块
    纯蓝方块（QSS 的 ``image`` 需要图片文件，而本项目零图片资源），勾选态辨识度差。
    这里直接复用 ``icons`` 的矢量对勾，与 ``ModCard`` / ``PackRow`` 的勾选视觉一致。
    """

    BOX = 18   # 方框边长
    GAP = 8    # 方框与文字的间距

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Microsoft YaHei UI", 12))
        self.setMinimumHeight(28)
        self._hover = False

    def sizeHint(self) -> QSize:  # noqa: N802
        fm = QFontMetrics(self.font())
        return QSize(self.BOX + self.GAP + fm.horizontalAdvance(self.text()) + 6,
                     max(28, self.BOX + 10))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        top = (self.height() - self.BOX) / 2
        rect = QRectF(0.5, top + 0.5, self.BOX - 1, self.BOX - 1)
        path = QPainterPath()
        path.addRoundedRect(rect, 5, 5)

        if self.isChecked():
            p.fillPath(path, QBrush(QColor(C.BLUE)))
            p.setPen(QPen(QColor(C.BLUE), 1.4))
            p.drawPath(path)
            p.drawPixmap(int(rect.x()) + 2, int(rect.y()) + 2,
                         icons.pixmap("check", "#FFFFFF", self.BOX - 4))
        else:
            p.fillPath(path, QBrush(QColor("#FFFFFF")))
            p.setPen(QPen(QColor(C.BLUE_LIGHT if self._hover else C.BORDER), 1.4))
            p.drawPath(path)

        p.setPen(QPen(QColor(C.TEXT)))
        p.setFont(self.font())
        p.drawText(QRectF(self.BOX + self.GAP, 0,
                          max(0, self.width() - self.BOX - self.GAP), self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()


class SettingsPage(QWidget):
    """设置页面。"""

    def __init__(self, router, parent=None):
        super().__init__(parent)
        self.router = router

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        host = QWidget()
        scroll.setWidget(host)
        root = QVBoxLayout(host)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(14)

        # ---------------------------------------------------- 1) 标题
        root.addWidget(label("设置", obj="PageTitle"))
        root.addWidget(label(f"版本 {APP_VERSION}", obj="PageSub"))

        # ---------------------------------------------------- 2) 翻译模型
        model_card = Card(title="翻译模型")
        mrow = QHBoxLayout()
        mrow.setSpacing(8)
        mrow.addWidget(icon_label("model", C.BLUE, 20))
        self.model_name_label = label("", obj="ModelName")
        self.model_none_label = label("未选择翻译模型", obj="ModelNone")
        mrow.addWidget(self.model_name_label)
        mrow.addWidget(self.model_none_label)
        mrow.addStretch(1)
        model_card.add(mrow)

        self.model_info_label = label("", obj="Hint", wrap=True)
        model_card.add(self.model_info_label)

        brow = QHBoxLayout()
        brow.setSpacing(8)
        pick_btn = IconButton("选择模型", "model", primary=True)
        pick_btn.clicked.connect(self._pick_model)
        clear_btn = IconButton("清除模型", "close")
        clear_btn.clicked.connect(self._clear_model)
        brow.addWidget(pick_btn)
        brow.addWidget(clear_btn)
        brow.addStretch(1)
        model_card.add(brow)
        root.addWidget(model_card)

        # ---------------------------------------------------- 3) 翻译选项
        t_card = Card(title="翻译选项")
        self.enhanced_check = CheckOption("强化翻译")
        self.enhanced_check.setToolTip(
            "勾选后，模型每翻译完一条都会检查译文是否通顺；\n"
            f"判定不通顺则自动重新翻译，最多重试 {translator.ENHANCED_MAX_RETRIES} 次。\n"
            "开启后会需要更长时间进行翻译。")
        self.enhanced_check.toggled.connect(self._on_enhanced_toggled)
        t_card.add(self.enhanced_check)
        t_card.add(label(
            "逐条检查译文的通顺性：判定不通顺就自动重译，直到满足要求或达到重试上限"
            f"（最多 {translator.ENHANCED_MAX_RETRIES} 次）。默认关闭；"
            "开启后会需要更长时间进行翻译。",
            obj="Hint", wrap=True))
        root.addWidget(t_card)

        # ---------------------------------------------------- 4) 个性化（付费门禁）
        p_card = Card(title="个性化")
        self.border_btn = self._color_button(STATE.border_color)
        self.border_btn.clicked.connect(self._pick_border)
        p_card.add(self._setting_row("边框颜色", "翻译器与卡片的描边颜色", self.border_btn))

        self.accent_btn = self._color_button(STATE.accent_color)
        self.accent_btn.clicked.connect(self._pick_accent)
        p_card.add(self._setting_row("翻译器颜色", "强调色 / 主色调", self.accent_btn))

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("默认：MC 模组汉化工具")
        self.title_edit.setFixedWidth(220)
        self.title_edit.editingFinished.connect(self._on_title_edited)
        p_card.add(self._setting_row("翻译器右上角文字", "显示在翻译器窗口右上角的自定义文字",
                                     self.title_edit))

        self.lock_box = QWidget()
        lock_row = QHBoxLayout(self.lock_box)
        lock_row.setContentsMargins(0, 0, 0, 0)
        lock_row.setSpacing(6)
        lock_row.addWidget(icon_label("lock", C.WARN, 16))
        lock_row.addWidget(label("该功能需付费解锁，敬请期待", obj="Hint"))
        lock_row.addStretch(1)
        p_card.add(self.lock_box)

        save_row = QHBoxLayout()
        save_row.setSpacing(8)
        save_row.addStretch(1)
        save_btn = IconButton("保存", "check", primary=True)
        save_btn.clicked.connect(self._save_personalize)
        save_row.addWidget(save_btn)
        p_card.add(save_row)
        root.addWidget(p_card)

        # ---------------------------------------------------- 5) 赞助
        s_card = Card(title="赞助")
        sp_row = QHBoxLayout()
        sp_row.setSpacing(8)
        sp_btn = IconButton("赞助翻译器", "heart", primary=True)
        sp_btn.clicked.connect(self._open_sponsor)
        sp_row.addWidget(sp_btn)
        sp_row.addStretch(1)
        s_card.add(sp_row)

        sp_head = QHBoxLayout()
        sp_head.setSpacing(6)
        sp_head.addWidget(icon_label("sponsor", C.ERR, 16))
        sp_head.addWidget(label("赞助者：", obj="CardTitle"))
        sp_head.addStretch(1)
        s_card.add(sp_head)

        self.sponsor_label = label("", obj="SponsorText", wrap=True)
        s_card.add(self.sponsor_label)
        root.addWidget(s_card)

        # ---------------------------------------------------- 6) 杂项
        misc_card = Card(title="杂项")
        dnc_row = QHBoxLayout()
        dnc_row.setSpacing(8)
        dnc_btn = IconButton("千万别点", "warning")
        dnc_btn.clicked.connect(self._dont_click)
        dnc_row.addWidget(dnc_btn)
        dnc_row.addStretch(1)
        misc_card.add(dnc_row)

        self.cave = CaveBox()
        misc_card.add(self.cave)
        root.addWidget(misc_card)

        root.addStretch(1)

        # ---------------------------------------------------- 信号订阅
        STATE.modelChanged.connect(self._refresh_model)
        STATE.sponsorsChanged.connect(self._refresh_sponsors)
        STATE.enhancedTranslateChanged.connect(self._refresh_enhanced)

        self.refresh()

    # ================================================================ 通用小组件

    def _color_button(self, color: str) -> QPushButton:
        b = QPushButton()
        b.setFixedSize(32, 32)
        b.setCursor(Qt.PointingHandCursor)
        self._paint_color_btn(b, color)
        return b

    def _paint_color_btn(self, btn: QPushButton, color: str) -> None:
        btn.setStyleSheet(
            f"background:{color};border-radius:6px;border:1px solid {C.BORDER};")

    def _setting_row(self, title: str, desc: str, widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(label(title, bold=True))
        left.addWidget(label(desc, obj="Hint", wrap=True))
        row.addLayout(left, 1)
        row.addWidget(widget, 0, Qt.AlignVCenter)
        return row

    # ================================================================ 刷新

    def refresh(self) -> None:
        """刷新模型 / 赞助 / 个性化 / 翻译选项四块。"""
        self._refresh_model()
        self._refresh_sponsors()
        self._refresh_personalize()
        self._refresh_enhanced()

    def _refresh_model(self) -> None:
        has = STATE.has_model()
        self.model_name_label.setText(STATE.model_name)
        self.model_name_label.setVisible(has)
        self.model_none_label.setVisible(not has)

        if has:
            info = STATE.model_info or {}
            parts = [f"路径：{STATE.model_path}"]
            if info.get("entries") is not None:
                parts.append(f"条目：{info.get('entries')}")
            if info.get("version"):
                parts.append(f"版本：{info.get('version')}")
            if info.get("type"):
                parts.append(f"类型：{info.get('type')}")
            self.model_info_label.setText(" · ".join(parts))
        else:
            self.model_info_label.setText("支持 .zip 格式的离线词表/模型包")

    def _refresh_sponsors(self) -> None:
        self.sponsor_label.setText(STATE.sponsors_text())

    def _refresh_personalize(self) -> None:
        unlocked = STATE.personalize_unlocked
        self._paint_color_btn(self.border_btn, STATE.border_color)
        self._paint_color_btn(self.accent_btn, STATE.accent_color)
        if STATE.translator_title == DEFAULT_TRANSLATOR_TITLE:
            self.title_edit.setText("")
        else:
            self.title_edit.setText(STATE.translator_title)
        for w in (self.border_btn, self.accent_btn, self.title_edit):
            w.setEnabled(unlocked)
        self.lock_box.setVisible(not unlocked)

    def _refresh_enhanced(self) -> None:
        """把 STATE 里的开关同步到复选框（外部改状态时也走这里）。"""
        self.enhanced_check.setChecked(bool(STATE.enhanced_translate))

    # ================================================================ 翻译选项动作

    def _on_enhanced_toggled(self, on: bool) -> None:
        """复选框被点击：写回 STATE（落盘 + 发信号）。

        ``setChecked`` 也会触发本槽，因此值没变时直接返回，避免信号回环。
        """
        if bool(STATE.enhanced_translate) == bool(on):
            return
        STATE.set_enhanced_translate(bool(on))
        toast(self, "已开启强化翻译" if on else "已关闭强化翻译")

    # ================================================================ 模型动作

    def _pick_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择翻译模型", str(paths.app_dir()),
            "翻译模型 (*.zip);;所有文件 (*)")
        if not path:
            return
        try:
            name, info = translator.load_model(path)
        except translator.ModelError as e:
            QMessageBox.warning(self, "模型加载失败", str(e))
            return
        STATE.set_model(path, name, info)
        toast(self, f"已加载模型：{name}")

    def _clear_model(self) -> None:
        STATE.clear_model()
        toast(self, "已清除翻译模型")

    # ================================================================ 个性化动作

    def _pick_border(self) -> None:
        col = QColorDialog.getColor(QColor(STATE.border_color), self, "选择边框颜色")
        if col.isValid():
            STATE.border_color = col.name()
            self._paint_color_btn(self.border_btn, col.name())

    def _pick_accent(self) -> None:
        col = QColorDialog.getColor(QColor(STATE.accent_color), self, "选择翻译器颜色")
        if col.isValid():
            STATE.accent_color = col.name()
            self._paint_color_btn(self.accent_btn, col.name())

    def _on_title_edited(self) -> None:
        STATE.translator_title = self.title_edit.text().strip() or DEFAULT_TRANSLATOR_TITLE

    def _save_personalize(self) -> None:
        title = self.title_edit.text().strip()
        STATE.set_personalize(STATE.accent_color, STATE.border_color, title)
        toast(self, "个性化已保存")

    def _unlock(self) -> None:
        """后续接入付费流程时调用，解锁个性化设置。"""
        STATE.personalize_unlocked = True
        STATE.save()
        self.refresh()

    # ================================================================ 赞助 / 杂项

    def _open_sponsor(self) -> None:
        url = STATE.sponsor_url()
        if not url:
            toast(self, "暂未配置赞助网址（缺少 wangzhi.txt）", 3000)
        else:
            QDesktopServices.openUrl(QUrl(url))

    def _dont_click(self) -> None:
        # TODO: 功能预留
        toast(self, "都说了千万别点啦 (´･ω･`)", 3000)
