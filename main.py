# -*- coding: utf-8 -*-
"""程序入口：无边框主窗口 + 渐变标题栏 + 侧边栏 + 页面路由。

支持 ``--selftest``：离屏创建全部页面后退出，用于验证打包产物是否可用
（``--windowed`` 打包后没有控制台，只能靠退出码判断）。
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                               QStackedWidget, QVBoxLayout, QWidget)

from app import icons, paths
from app.pages.modselect import ModSelectPage
from app.pages.packs import PacksPage
from app.pages.settings import SettingsPage
from app.pages.translate import TranslatePage
from app.router import Router
from app.state import APP_VERSION, STATE
from app.theme import C, qss
from app.widgets import NavItem, TitleBar, label

#: 无边框窗口的外圈留白，用于边缘缩放
BORDER = 6
#: 可缩放的边缘判定宽度
EDGE = BORDER + 2

#: 侧边栏导航项（key, 显示名, 图标）
NAV_ITEMS = (
    ("translate", "翻译", "translate"),
    ("settings", "设置", "settings"),
)


class MainWindow(QWidget):
    """主窗口（无边框，自绘标题栏与侧边栏）。"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle(paths.APP_NAME)
        self.setWindowIcon(icons.icon("logo", C.BLUE, 64))
        self.setMinimumSize(940, 640)
        self.resize(1180, 760)

        # ---- 外层：留 6px 用于边缘缩放 ----
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(BORDER, BORDER, BORDER, BORDER)
        self._outer.setSpacing(0)

        self.root = QFrame()
        self.root.setObjectName("Root")
        self._outer.addWidget(self.root)

        root_lay = QVBoxLayout(self.root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ---- 标题栏 ----
        self.titlebar = TitleBar(f"{paths.APP_NAME}   v{APP_VERSION}")
        root_lay.addWidget(self.titlebar)

        # ---- 主体：侧边栏 + 内容区 ----
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root_lay.addLayout(body, 1)

        self.sidebar, self.nav_items = self._build_sidebar()
        body.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)

        # ---- 路由与页面 ----
        self.router = Router(self._on_navigate)
        self.pages: dict[str, QWidget] = {
            "translate": TranslatePage(self.router),
            "modselect": ModSelectPage(self.router),
            "packs": PacksPage(self.router),
            "settings": SettingsPage(self.router),
        }
        for key, page in self.pages.items():
            self.stack.addWidget(page)

        # ---- 订阅 ----
        STATE.themeChanged.connect(self._apply_theme)

        self._on_navigate("translate")
        self._center_on_screen()

    # ------------------------------------------------------------ 构建

    def _build_sidebar(self):
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(196)

        lay = QVBoxLayout(side)
        lay.setContentsMargins(10, 16, 10, 14)
        lay.setSpacing(4)

        # 品牌区
        brand = QHBoxLayout()
        brand.setContentsMargins(8, 0, 0, 0)
        brand.setSpacing(9)
        logo = QLabel()
        logo.setPixmap(icons.pixmap("logo", C.BLUE, 30))
        logo.setFixedSize(30, 30)
        brand.addWidget(logo)

        col = QVBoxLayout()
        col.setSpacing(0)
        name = label("模组汉化工具", obj="SidebarBrand")
        ver = label(f"v{APP_VERSION}", obj="SidebarVer")
        col.addWidget(name)
        col.addWidget(ver)
        brand.addLayout(col)
        brand.addStretch(1)
        lay.addLayout(brand)
        lay.addSpacing(16)

        # 导航项
        items: dict[str, NavItem] = {}
        for key, text, icon_name in NAV_ITEMS:
            item = NavItem(key, text, icon_name)
            item.clicked.connect(lambda _=False, k=key: self.router.go(k))
            lay.addWidget(item)
            items[key] = item

        lay.addStretch(1)

        tip = label("离线翻译 · 全版本通用", obj="Hint")
        tip.setAlignment(Qt.AlignCenter)
        lay.addWidget(tip)
        return side, items

    # ------------------------------------------------------------ 路由

    def _on_navigate(self, key: str) -> None:
        page = self.pages.get(key)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        # 侧边栏高亮
        active = self.router.sidebar_key()
        for k, item in self.nav_items.items():
            item.set_active(k == active)
        # 二级页面归属「翻译」
        if key in ("modselect", "packs"):
            self.nav_items["translate"].set_active(True)
        # 切页时刷新
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:  # noqa: BLE001 - 单页刷新失败不应拖垮主界面
                pass

    # ------------------------------------------------------------ 主题

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss())
        self.titlebar.update()
        self.update()

    # ------------------------------------------------------------ 窗口行为

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(geo.center().x() - self.width() // 2,
                  geo.center().y() - self.height() // 2)

    def _edges_at(self, pos):
        """判断鼠标位置是否落在可缩放边缘上。"""
        if self.isMaximized() or self.isFullScreen():
            return None
        r = self.rect()
        edges = Qt.Edge(0)
        if pos.x() <= EDGE:
            edges |= Qt.Edge.LeftEdge
        if pos.x() >= r.width() - EDGE:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= EDGE:
            edges |= Qt.Edge.TopEdge
        if pos.y() >= r.height() - EDGE:
            edges |= Qt.Edge.BottomEdge
        return edges if int(edges) else None

    def mouseMoveEvent(self, e):
        edges = self._edges_at(e.position().toPoint())
        if edges is None:
            self.unsetCursor()
        elif (edges & Qt.Edge.LeftEdge and edges & Qt.Edge.TopEdge) or \
                (edges & Qt.Edge.RightEdge and edges & Qt.Edge.BottomEdge):
            self.setCursor(Qt.SizeFDiagCursor)
        elif (edges & Qt.Edge.RightEdge and edges & Qt.Edge.TopEdge) or \
                (edges & Qt.Edge.LeftEdge and edges & Qt.Edge.BottomEdge):
            self.setCursor(Qt.SizeBDiagCursor)
        elif edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.SizeVerCursor)
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            edges = self._edges_at(e.position().toPoint())
            if edges is not None:
                h = self.windowHandle()
                if h:
                    h.startSystemResize(edges)
                    return
        super().mousePressEvent(e)

    def changeEvent(self, e):
        # ⚠️ changeEvent 可能早于 __init__ 完成（setWindowTitle/show 都会触发），必须守卫
        super().changeEvent(e)
        if not hasattr(self, "_outer"):
            return
        if e.type() == e.Type.WindowStateChange:
            maxed = self.isMaximized() or self.isFullScreen()
            m = 0 if maxed else BORDER
            self._outer.setContentsMargins(m, m, m, m)
            if hasattr(self, "titlebar"):
                self.titlebar.btn_max.setIcon(
                    icons.icon("restore" if maxed else "max", "#FFFFFF", 15)
                )

    def closeEvent(self, e):
        STATE.save()
        super().closeEvent(e)


# ---------------------------------------------------------------- 自检


def run_selftest(win: "MainWindow", app: QApplication) -> int:
    """离屏遍历所有页面，返回退出码（0 表示正常）。"""
    codes = 0
    try:
        for key in ("translate", "modselect", "packs", "settings"):
            win.router.go(key)
            app.processEvents()
            page = win.pages.get(key)
            if page is None:
                codes = 2
    except Exception as exc:  # noqa: BLE001
        print(f"SELFTEST FAILED: {exc}", file=sys.stderr)
        return 1
    return codes


# ---------------------------------------------------------------- 入口


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv)
    selftest = "--selftest" in argv
    if selftest:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    # 高 DPI 下保持矢量图标清晰
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(argv)
    app.setApplicationName(paths.APP_NAME)
    app.setOrganizationName(paths.APP_ID)
    app.setStyleSheet(qss())

    win = MainWindow()

    if selftest:
        return run_selftest(win, app)

    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
