# -*- coding: utf-8 -*-
"""极简页面路由。"""
from __future__ import annotations

from typing import Callable

#: 一级页面（侧边栏可见）
PRIMARY = ("translate", "settings")
#: 二级页面（属于翻译流程，侧边栏高亮 translate）
SECONDARY = ("modselect", "packs")


class Router:
    def __init__(self, navigate: Callable[[str], None] | None = None):
        self._navigate = navigate
        self._history: list[str] = []
        self._current = "translate"

    def bind(self, fn: Callable[[str], None]) -> None:
        self._navigate = fn

    def go(self, key: str) -> None:
        if key == self._current:
            return
        self._history.append(self._current)
        self._current = key
        if self._navigate:
            self._navigate(key)

    def back(self) -> None:
        prev = self._history.pop() if self._history else "translate"
        self._current = prev
        if self._navigate:
            self._navigate(prev)

    def current(self) -> str:
        return self._current

    def sidebar_key(self) -> str:
        """当前页面对应的侧边栏高亮项。"""
        return "translate" if self._current in SECONDARY else self._current
