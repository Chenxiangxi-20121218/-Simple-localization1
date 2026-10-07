# -*- coding: utf-8 -*-
"""翻译主界面。

自上而下依次为：

1. 顶部模型条（当前翻译模型 + 去设置）
2. 「自动筛选文件夹」卡片（游戏目录 / 重新筛选 / 更换目录 / 概览提示）
3. 欢迎语 + 单行日志卡片
4. 进度卡片（默认隐藏，开始翻译后显示）
5. 底部操作区（开始翻译 / 版本选择 / 汉化包管理）

页面自身订阅 ``STATE`` 的信号完成刷新，``refresh()`` 只在路由切换时被外部调用。
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QProgressBar,
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from .. import paths
from ..core import packager
from ..core.worker import TranslateWorker
from ..state import STATE
from ..theme import C
from ..widgets import (BigButton, Card, IconButton, Separator, icon_label,
                       label, toast)


class TranslatePage(QWidget):
    """翻译主界面。"""

    def __init__(self, router, parent=None):
        super().__init__(parent)
        self.router = router
        #: 当前后台翻译线程（空闲时为 None）
        self.worker: TranslateWorker | None = None
        self._log_text = STATE.last_log

        # 外层滚动区，保证窗口缩小时内容不被挤坏
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

        root.addWidget(self._build_model_card())
        root.addWidget(self._build_folder_card())
        root.addWidget(self._build_welcome_card())
        root.addWidget(self._build_progress_card())
        root.addStretch(1)
        root.addWidget(self._build_actions())

        self._connect_state()
        self.refresh()

    # ------------------------------------------------------------ 构建界面

    def _build_model_card(self) -> Card:
        """顶部模型条：内容在刷新时整体重建。"""
        card = Card(padding=14)
        self._model_row = QHBoxLayout()
        self._model_row.setSpacing(8)
        card.add(self._model_row)
        return card

    def _build_folder_card(self) -> Card:
        card = Card(title="自动筛选文件夹")

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(icon_label("folder", C.BLUE, 18))
        row1.addWidget(label("文件夹位置："))
        self._path_label = label(str(STATE.game_dir), obj="PathText", wrap=True)
        self._path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row1.addWidget(self._path_label, 1)
        card.add(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        btn_reselect = IconButton("重新筛选", "refresh")
        btn_reselect.clicked.connect(self._on_reselect)
        btn_dir = IconButton("更换目录", "folder")
        btn_dir.clicked.connect(self._on_change_dir)
        row2.addWidget(btn_reselect)
        row2.addWidget(btn_dir)
        row2.addStretch(1)
        card.add(row2)

        self._folder_hint = label("", obj="Hint")
        card.add(self._folder_hint)
        return card

    def _build_welcome_card(self) -> Card:
        card = Card()
        self._welcome_label = label(STATE.welcome_text, size=17, bold=True, wrap=True)
        card.add(self._welcome_label)
        card.add(Separator())

        # 日志只显示一行：超长用省略号截断（见 _update_log）
        self._log_label = label("", obj="LogLine")
        self._log_label.setWordWrap(False)
        self._log_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._log_label.installEventFilter(self)
        card.add(self._log_label)
        return card

    def _build_progress_card(self) -> Card:
        card = Card()

        head = QHBoxLayout()
        head.addWidget(label("翻译进度"))
        head.addStretch(1)
        self._time_label = label("", obj="Hint")
        head.addWidget(self._time_label)
        card.add(head)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        # 百分比统一放在标题行右侧，避免蓝色进度条上的深色文字看不清
        self._progress_bar.setTextVisible(False)
        card.add(self._progress_bar)

        # 每 5 分钟推来的冷知识
        self._leng_label = label("", obj="Hint", wrap=True)
        card.add(self._leng_label)

        # 完成提示语（worker.done 的文本）
        self._done_label = label("", obj="Hint", wrap=True)
        card.add(self._done_label)

        row = QHBoxLayout()
        btn_cancel = IconButton("取消翻译", "close")
        btn_cancel.clicked.connect(self._on_cancel)
        row.addWidget(btn_cancel)
        row.addStretch(1)
        card.add(row)

        self._progress_card = card
        card.setVisible(False)
        return card

    def _build_actions(self) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._start_btn = BigButton("开始翻译", "play")
        self._start_btn.clicked.connect(self._on_start)
        lay.addWidget(self._start_btn)

        row = QHBoxLayout()
        row.setSpacing(10)
        btn_version = IconButton("版本选择", "list")
        btn_version.clicked.connect(self._go_modselect)
        btn_packs = IconButton("汉化包管理", "package")
        btn_packs.clicked.connect(self._go_packs)
        row.addWidget(btn_version, 1)
        row.addWidget(btn_packs, 1)
        lay.addLayout(row)
        return box

    # ------------------------------------------------------------ 信号订阅

    def _connect_state(self) -> None:
        """只在 __init__ 连接一次。"""
        STATE.modelChanged.connect(self._on_model_changed)
        STATE.gameDirChanged.connect(self._on_game_dir_changed)
        STATE.modsChanged.connect(self._update_start_enabled)
        STATE.versionChanged.connect(self._update_start_enabled)
        STATE.logChanged.connect(self._on_log_changed)
        STATE.progressChanged.connect(self._on_progress)

    # ------------------------------------------------------------ 刷新

    def refresh(self) -> None:
        self._rebuild_model_row()
        self._refresh_folder()
        self._welcome_label.setText(STATE.welcome_text)
        self._log_text = STATE.last_log
        self._update_log()
        self._update_start_enabled()

    def _on_model_changed(self) -> None:
        self._rebuild_model_row()
        self._update_start_enabled()

    def _on_game_dir_changed(self) -> None:
        self._refresh_folder()

    def _on_log_changed(self, text: str) -> None:
        self._log_text = text
        self._update_log()

    def _rebuild_model_row(self) -> None:
        """清空并重建模型条内容。"""
        while self._model_row.count():
            item = self._model_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        self._model_row.addWidget(icon_label("model", C.BLUE, 22))
        self._model_row.addWidget(label("当前翻译模型："))
        if STATE.has_model():
            self._model_row.addWidget(label(STATE.model_name, obj="ModelName"))
        else:
            self._model_row.addWidget(label("未选择翻译模型，请从设置选择", obj="ModelNone"))
        self._model_row.addStretch(1)

        btn = IconButton("去设置", "settings")
        btn.clicked.connect(self._go_settings)
        self._model_row.addWidget(btn)

    def _refresh_folder(self) -> None:
        """刷新游戏目录路径与概览提示（只数 jar 个数，不跑 scan_mods）。"""
        self._path_label.setText(str(STATE.game_dir))

        mod_count = 0
        for d in paths.mods_dirs(STATE.game_path(), STATE.current_version):
            try:
                mod_count += sum(1 for _ in d.glob("*.jar"))
            except OSError:
                pass
        try:
            ver_count = len(paths.list_versions(STATE.game_path()))
        except OSError:
            ver_count = 0
        self._folder_hint.setText(f"检测到 {mod_count} 个可翻译模组 · {ver_count} 个版本")

    def _update_log(self) -> None:
        """单行日志：按当前宽度做省略号截断。"""
        fm = QFontMetrics(self._log_label.font())
        width = max(20, self._log_label.width())
        text = fm.elidedText(self._log_text, Qt.ElideRight, width)
        if text != self._log_label.text():
            self._log_label.setText(text)

    def _update_start_enabled(self) -> None:
        """开始翻译：至少选一个模组且已选模型才可点击。"""
        ok = STATE.can_translate()
        self._start_btn.setEnabled(ok)
        self._start_btn.setToolTip(
            "" if ok else "请先选择翻译模型，并在「版本选择」中至少勾选一个模组"
        )

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self._log_label and event.type() == QEvent.Resize:
            self._update_log()
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------ 目录操作

    def _on_reselect(self, *_) -> None:
        found = paths.detect_game_dirs()
        if found:
            STATE.set_game_dir(str(found[0]))
            toast(self, f"已重新筛选：{found[0]}")
        else:
            toast(self, "未自动发现 .minecraft 目录，请手动选择")

    def _on_change_dir(self, *_) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择 .minecraft 目录", str(STATE.game_dir))
        if d:
            STATE.set_game_dir(d)

    # ------------------------------------------------------------ 导航

    def _go_settings(self, *_) -> None:
        self.router.go("settings")

    def _go_modselect(self, *_) -> None:
        self.router.go("modselect")

    def _go_packs(self, *_) -> None:
        self.router.go("packs")

    # ------------------------------------------------------------ 翻译流程

    def _on_progress(self, percent: int, text: str) -> None:
        # 只要有进度推进就保证卡片可见（需求：翻译开始后显示预计时间与进度条）
        if not self._progress_card.isVisible():
            self._progress_card.setVisible(True)
        self._progress_bar.setValue(percent)
        self._time_label.setText(f"{percent}%   {text}".rstrip() if text else f"{percent}%")

    def _on_cancel(self, *_) -> None:
        if self.worker is not None:
            self.worker.cancel()

    def _on_start(self, *_) -> None:
        if not STATE.can_translate():
            toast(self, "请先选择模型并勾选模组")
            return

        # 让界面立刻反馈：先建一次汉化包目录（worker 内也会做）
        try:
            paths.hanhuabao_root(STATE.game_path(), STATE.current_version)
        except OSError:
            pass

        self._progress_card.setVisible(True)
        self._progress_bar.setValue(0)
        self._time_label.setText("")
        self._leng_label.setText("")
        self._done_label.setText("")
        self._start_btn.setEnabled(False)

        self.worker = TranslateWorker(
            str(STATE.game_path()),
            STATE.current_version,
            STATE.selected_mod_list(),
            self,
        )
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.log.connect(self._on_worker_log)
        self.worker.lengzhishi.connect(self._on_worker_lengzhishi)
        self.worker.done.connect(self._on_worker_done)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_progress(self, percent: int, text: str) -> None:
        STATE.progressChanged.emit(percent, text)

    def _on_worker_log(self, text: str) -> None:
        STATE.log(text)

    def _on_worker_lengzhishi(self, text: str) -> None:
        self._leng_label.setText(text)
        toast(self, text, 6000)

    def _on_worker_done(self, text: str) -> None:
        STATE.log(text)
        toast(self, text, 5000)
        self._progress_card.setVisible(True)
        self._progress_bar.setValue(100)
        self._done_label.setText(text)
        self._start_btn.setEnabled(STATE.can_translate())
        try:
            STATE.set_packs(packager.list_packs(STATE.game_path(),
                                                STATE.current_version))
        except Exception:
            pass

    def _on_worker_failed(self, text: str) -> None:
        STATE.log(text)
        toast(self, text, 5000)
        self._progress_card.setVisible(False)
        self._start_btn.setEnabled(STATE.can_translate())

    def _on_worker_finished(self) -> None:
        self.worker = None
