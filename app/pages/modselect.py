# -*- coding: utf-8 -*-
"""版本选择 / 模组选择页面。

上半部分是版本下拉框与扫描按钮，下半部分是模组卡片网格（``FlowLayout``）。
勾选结果直接写入 ``STATE.selected_mods``，回到翻译界面即可点击「开始翻译」。

扫描策略：结果带缓存，``refresh()`` 不会无条件重扫 —— 只有「版本变了」或
「当前没有任何模组」时才重新扫描，避免来回切页时卡顿。
"""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from .. import paths
from ..core import modscan
from ..state import STATE
from ..widgets import (Card, EmptyHint, FlowLayout, IconButton, ModCard,
                       label)


class ModSelectPage(QWidget):
    """版本选择 + 模组勾选。"""

    #: 没有任何版本时下拉框的占位项
    _EMPTY_ITEM = "未发现版本"

    def __init__(self, router, parent=None):
        super().__init__(parent)
        self.router = router
        #: 上次扫描对应的版本（None 表示还没扫描过）
        self._scanned_version: str | None = None
        #: 当前网格里已构建的模组 id 列表，用于判断是否需要重建卡片
        self._grid_ids: list[str] = []
        self._scanning = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        root = QVBoxLayout(content)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(14)

        root.addLayout(self._build_title())
        root.addWidget(self._build_version_card())
        root.addLayout(self._build_toolbar())

        self._scan_label = label("正在扫描模组…", obj="Hint")
        self._scan_label.setVisible(False)
        root.addWidget(self._scan_label)

        root.addWidget(self._build_grid())
        root.addLayout(self._build_bottom())

        self._connect_state()
        self.refresh()

    # ------------------------------------------------------------ 构建界面

    def _build_title(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        btn_back = IconButton("返回", "back")
        btn_back.clicked.connect(self._go_back)
        row.addWidget(btn_back)

        # 标题块用 QWidget 包住，避免空状态时被 QVBoxLayout 纵向拉伸
        holder = QWidget()
        col = QVBoxLayout(holder)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        col.addWidget(label("版本选择", obj="PageTitle"))
        col.addWidget(label("选择要翻译的 Minecraft 版本，并勾选需要汉化的模组", obj="PageSub"))
        row.addWidget(holder)
        row.addStretch(1)
        return row

    def _build_version_card(self) -> Card:
        card = Card(title="选择版本")
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(label("Minecraft 版本"))

        self._combo = QComboBox()
        self._combo.setMinimumWidth(180)
        self._combo.currentTextChanged.connect(self._on_version_picked)
        row.addWidget(self._combo)

        btn_scan = IconButton("扫描模组", "refresh")
        btn_scan.clicked.connect(self._on_manual_scan)
        row.addWidget(btn_scan)
        row.addStretch(1)
        card.add(row)
        return card

    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        # 三个批量操作按钮放在同一个容器里，扫描时可整体禁用
        self._btn_box = QWidget()
        box = QHBoxLayout(self._btn_box)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(8)
        for text, icon, slot in (("全选", "check", self._select_all),
                                 ("反选", "refresh", self._invert),
                                 ("全不选", "close", self._select_none)):
            btn = IconButton(text, icon)
            btn.clicked.connect(slot)
            box.addWidget(btn)
        row.addWidget(self._btn_box)

        row.addStretch(1)
        self._count_label = label("已选 0 / 共 0", obj="Hint")
        row.addWidget(self._count_label)
        return row

    def _build_grid(self) -> QWidget:
        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(True)
        self._grid_scroll.setFrameShape(QFrame.NoFrame)
        self._grid_scroll.setMinimumHeight(320)

        host = QWidget()
        # FlowLayout 直接作为 host 的布局；底部 20px 由 contentsMargins 留出
        self._flow = FlowLayout(host, margin=4, hspacing=12, vspacing=12)
        self._flow.setContentsMargins(4, 4, 4, 20)
        self._grid_scroll.setWidget(host)

        self._empty = EmptyHint("未发现可以翻译的模组")

        # 容器吃掉所有多余纵向空间，保证其余控件不被拉伸
        wrap = QWidget()
        wrap.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)
        wl.addWidget(self._grid_scroll, 1)
        wl.addWidget(self._empty, 1)
        return wrap

    def _build_bottom(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(label("提示：勾选后回到翻译界面点击「开始翻译」", obj="Hint"))
        row.addStretch(1)
        btn_ok = IconButton("确定", "check", primary=True)
        btn_ok.clicked.connect(self._go_back)
        row.addWidget(btn_ok)
        return row

    # ------------------------------------------------------------ 信号订阅

    def _connect_state(self) -> None:
        """只在 __init__ 连接一次。"""
        STATE.versionChanged.connect(self._on_version_changed)
        STATE.modsChanged.connect(self._on_mods_changed)
        STATE.gameDirChanged.connect(self._on_game_dir_changed)

    # ------------------------------------------------------------ 刷新

    def refresh(self) -> None:
        self._fill_versions()
        # 若外部（或其它页面）已经填好了模组数据，就直接复用，不重扫
        if self._scanned_version is None and STATE.mods:
            self._scanned_version = STATE.current_version
        if (not STATE.mods) or (self._scanned_version != STATE.current_version):
            self._scan(force=True)
        else:
            self._rebuild_grid()
        self._update_count()

    def _fill_versions(self) -> None:
        """重建版本下拉框，默认选中 STATE.current_version。"""
        versions = paths.list_versions(STATE.game_path())
        pending = ""
        self._combo.blockSignals(True)
        self._combo.clear()
        if versions:
            self._combo.addItems(versions)
            idx = self._combo.findText(STATE.current_version)
            # 从未选过版本、也没扫描结果时，默认落到第一个版本
            if idx < 0 and not STATE.current_version and not STATE.mods:
                idx = 0
                pending = versions[0]
            self._combo.setCurrentIndex(max(0, idx))
            self._combo.setEnabled(True)
        else:
            self._combo.addItem(self._EMPTY_ITEM)
            self._combo.setEnabled(False)
        self._combo.blockSignals(False)
        if pending:
            STATE.set_version(pending)

    def _on_version_changed(self) -> None:
        self._scan(force=True)

    def _on_game_dir_changed(self) -> None:
        self._fill_versions()
        self._scan(force=True)

    def _on_version_picked(self, name: str) -> None:
        if not name or name == self._EMPTY_ITEM:
            return
        before = STATE.current_version
        STATE.set_version(name)
        # set_version 只有变化时才发信号；同名时手动补一次扫描
        if STATE.current_version == before:
            self._scan(force=True)

    def _on_manual_scan(self, *_) -> None:
        modscan.clear_cache()
        self._scan(force=True)

    # ------------------------------------------------------------ 扫描

    def _scan(self, force: bool = False) -> None:
        """请求扫描；已在扫描中或结果仍然有效时直接跳过。"""
        if self._scanning:
            return
        if not force and STATE.mods and self._scanned_version == STATE.current_version:
            return
        self._scanning = True
        self._scan_label.setVisible(True)
        self._btn_box.setEnabled(False)
        self._combo.setEnabled(False)
        self._apply_visibility()
        # 交给事件循环跑一次，先让「正在扫描…」画出来
        QTimer.singleShot(0, self._do_scan)

    def _do_scan(self) -> None:
        try:
            version = STATE.current_version
            mods = modscan.scan_mods(paths.mods_dirs(STATE.game_path(), version))
            # 只保留「可以翻译」的模组（含 en_us 语言文件的）
            mods = [m for m in mods if m.get("translatable")]
            self._scanned_version = version
            STATE.set_mods(mods)
        except Exception:
            self._scanned_version = STATE.current_version
        finally:
            self._scanning = False
            self._scan_label.setVisible(False)
            self._btn_box.setEnabled(True)
            self._combo.setEnabled(bool(paths.list_versions(STATE.game_path())))
            self._apply_visibility()
            self._update_count()

    # ------------------------------------------------------------ 网格

    def _rebuild_grid(self) -> None:
        """按 STATE.mods 重建全部模组卡片。"""
        while self._flow.count():
            item = self._flow.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        for mod in STATE.mods:
            card = ModCard(
                mod["id"],
                mod.get("cn_name") or mod.get("en_name") or "",
                mod.get("en_name") or "",
                mod.get("icon"),
            )
            card.set_selected(mod["id"] in STATE.selected_mods)
            card.toggled.connect(STATE.toggle_mod)
            self._flow.addWidget(card)

        self._grid_ids = [m["id"] for m in STATE.mods]
        self._flow.invalidate()
        self._apply_visibility()

    def _sync_cards(self) -> None:
        """把卡片选中态同步为 STATE.selected_mods。"""
        for i in range(self._flow.count()):
            item = self._flow.itemAt(i)
            w = item.widget() if item is not None else None
            if isinstance(w, ModCard):
                w.set_selected(w.mod_id in STATE.selected_mods)

    def _apply_visibility(self) -> None:
        has = bool(self._grid_ids)
        self._grid_scroll.setVisible(has and not self._scanning)
        self._empty.setVisible((not has) and not self._scanning)

    def _on_mods_changed(self) -> None:
        ids = [m["id"] for m in STATE.mods]
        if ids != self._grid_ids:
            self._rebuild_grid()
        else:
            self._sync_cards()
        self._update_count()

    def _update_count(self) -> None:
        all_ids = {m["id"] for m in STATE.mods}
        chosen = len(STATE.selected_mods & all_ids)
        self._count_label.setText(f"已选 {chosen} / 共 {len(STATE.mods)}")

    # ------------------------------------------------------------ 批量勾选

    def _select_all(self, *_) -> None:
        STATE.selected_mods = {m["id"] for m in STATE.mods}
        STATE.modsChanged.emit()

    def _invert(self, *_) -> None:
        all_ids = {m["id"] for m in STATE.mods}
        STATE.selected_mods = all_ids - set(STATE.selected_mods)
        STATE.modsChanged.emit()

    def _select_none(self, *_) -> None:
        STATE.selected_mods.clear()
        STATE.modsChanged.emit()

    # ------------------------------------------------------------ 导航

    def _go_back(self, *_) -> None:
        self.router.back()
