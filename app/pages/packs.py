# -*- coding: utf-8 -*-
"""汉化包管理界面。

逐个列出汉化包并支持全选 / 反选 / 全不选，勾选状态立即写入 ``STATE.pack_enabled``，
点击「完成」时由 ``packager.apply_enabled`` 批量复制到 resourcepacks 并同步 options.txt。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from .. import paths
from ..core import packager
from ..state import STATE
from ..theme import C
from ..widgets import (Card, EmptyHint, IconButton, PackRow, icon_label, label,
                       toast)


class PacksPage(QWidget):
    """汉化包管理页面。"""

    def __init__(self, router, parent=None):
        super().__init__(parent)
        self.router = router
        #: 重建列表时的重入保护（set_packs / set_pack_enabled 都会 emit packsChanged）
        self._building = False

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(14)

        # ---------------------------------------------------- 1) 顶部标题行
        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        back_btn = IconButton("返回", "back")
        back_btn.clicked.connect(self.router.back)
        title_row.addWidget(back_btn)

        title_txt = QVBoxLayout()
        title_txt.setSpacing(2)
        title_txt.addWidget(label("汉化包管理", obj="PageTitle"))
        title_txt.addWidget(label("勾选表示启用，取消勾选表示禁用；点击「完成」应用更改",
                                  obj="PageSub"))
        title_row.addLayout(title_txt)
        title_row.addStretch(1)
        root.addLayout(title_row)

        # ---------------------------------------------------- 2) 目录提示
        dir_card = Card(padding=12)
        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        dir_row.addWidget(icon_label("folder", C.BLUE, 18))
        dir_row.addWidget(label("汉化包目录："))
        self.path_label = label("", obj="PathText", wrap=True)
        dir_row.addWidget(self.path_label, 1)
        open_btn = IconButton("打开目录", "folder")
        open_btn.clicked.connect(self._open_dir)
        dir_row.addWidget(open_btn)
        dir_card.add(dir_row)
        root.addWidget(dir_card)

        # ---------------------------------------------------- 3) 工具条
        bar = QHBoxLayout()
        bar.setSpacing(8)
        all_btn = IconButton("全选", "check")
        all_btn.clicked.connect(self._select_all)
        inv_btn = IconButton("反选", "refresh")
        inv_btn.clicked.connect(self._invert)
        none_btn = IconButton("全不选", "close")
        none_btn.clicked.connect(self._select_none)
        for b in (all_btn, inv_btn, none_btn):
            bar.addWidget(b)
        bar.addStretch(1)
        self.count_label = label("", obj="Hint")
        bar.addWidget(self.count_label)
        root.addLayout(bar)

        # ---------------------------------------------------- 4) 列表
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.list_host = QWidget()
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(8)
        self.scroll.setWidget(self.list_host)
        root.addWidget(self.scroll, 1)

        # ---------------------------------------------------- 5) 底部
        foot = QHBoxLayout()
        foot.setSpacing(12)
        foot.addWidget(label("提示：启用的汉化包会被复制到 resourcepacks 并置于加载顺序末尾",
                             obj="Hint", wrap=True), 1)
        done_btn = IconButton("完成", "check", primary=True)
        done_btn.clicked.connect(self._finish)
        foot.addWidget(done_btn)
        root.addLayout(foot)

        # ---------------------------------------------------- 信号订阅
        STATE.packsChanged.connect(self._on_packs_changed)
        STATE.gameDirChanged.connect(self.refresh)

        self.refresh()

    # ================================================================ 刷新

    def refresh(self) -> None:
        """重新扫描汉化包目录并重建列表。"""
        root = paths.hanhuabao_root(STATE.game_path())
        self.path_label.setText(str(root))
        self._building = True
        try:
            STATE.set_packs(packager.list_packs(root))
        finally:
            self._building = False
        self._rebuild()

    def _on_packs_changed(self) -> None:
        """packsChanged → 重建列表（重建期间直接返回，避免递归）。"""
        if self._building:
            return
        self._rebuild()

    # ================================================================ 列表构建

    def _clear_list(self) -> None:
        while self.list_lay.count():
            item = self.list_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _rebuild(self) -> None:
        self._building = True
        try:
            self._clear_list()
            packs = STATE.packs
            if not packs:
                self.list_lay.addWidget(
                    EmptyHint("暂无汉化包，请先在翻译界面完成一次翻译"))
            else:
                for pack in packs:
                    row = PackRow(pack["id"], pack["name"], pack["detail"])
                    row.set_checked(STATE.pack_enabled.get(pack["id"], False))
                    row.toggled.connect(STATE.set_pack_enabled)
                    self.list_lay.addWidget(row)
            self.list_lay.addStretch(1)

            n = len(packs)
            k = sum(1 for p in packs if STATE.pack_enabled.get(p["id"], False))
            self.count_label.setText(f"共 {n} 个汉化包 · 已启用 {k} 个")
        finally:
            self._building = False

    # ================================================================ 工具条动作

    def _apply_all(self, fn) -> None:
        """对全部汉化包套用规则并一次性持久化（避免信号风暴）。"""
        for p in STATE.packs:
            STATE.pack_enabled[p["id"]] = bool(fn(p))
        STATE.save()
        self._rebuild()

    def _select_all(self) -> None:
        self._apply_all(lambda p: True)

    def _select_none(self) -> None:
        self._apply_all(lambda p: False)

    def _invert(self) -> None:
        self._apply_all(lambda p: not STATE.pack_enabled.get(p["id"], False))

    # ================================================================ 其他动作

    def _open_dir(self) -> None:
        d = paths.hanhuabao_root(STATE.game_path())
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))

    def _finish(self) -> None:
        """应用勾选结果，然后返回上一页。"""
        packager.apply_enabled(STATE.game_path())
        k = sum(1 for p in STATE.packs if STATE.pack_enabled.get(p["id"], False))
        toast(self, f"已应用：启用 {k} 个汉化包")
        self.router.back()
