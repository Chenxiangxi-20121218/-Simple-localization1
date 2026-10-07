# -*- coding: utf-8 -*-
"""路径与目录管理。

所有路径工具集中在这里，保证「打包后」与「源码运行」行为一致。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "MC 模组汉化工具"
APP_ID = "MCLocalizer"

# ---------------------------------------------------------------- 基础目录


def is_frozen() -> bool:
    """是否运行在 PyInstaller 打包后的 exe 中。"""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """程序数据目录。

    - 打包后：exe 所在目录（配置 / 用户可编辑 txt 都在这里）
    - 源码运行：项目根目录
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundle_dir() -> Path:
    """只读内置资源目录（PyInstaller 解包后的 _MEIPASS）。"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", app_dir()))
    return app_dir()


def resource_dir() -> Path:
    """用户可编辑文本资源目录（lengzhishi.txt / wangzhi.txt / sponsors.txt）。"""
    d = app_dir() / "resources"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_file() -> Path:
    return app_dir() / "config.json"


# ---------------------------------------------------------------- 游戏目录

#: 常见启动器的 .minecraft 位置
_GAME_CANDIDATES = (
    r"%APPDATA%\.minecraft",
    r"%APPDATA%\..\Local\.minecraft",
    r"%USERPROFILE%\.minecraft",
    r"%USERPROFILE%\AppData\Roaming\.minecraft",
    r"%USERPROFILE%\Documents\.minecraft",
    r"D:\.minecraft",
    r"E:\.minecraft",
    r"%APPDATA%\PCL\..\.minecraft",
    r"%APPDATA%\HMCL\.minecraft",
)


def _expand(p: str) -> Path:
    return Path(os.path.expandvars(p)).expanduser()


def detect_game_dirs() -> list[Path]:
    """返回所有探测到的、看起来像 .minecraft 的目录（去重、按存在性排序）。"""
    found: list[Path] = []
    seen: set[str] = set()

    def _push(p: Path) -> None:
        try:
            key = str(p.resolve()).lower()
        except OSError:
            return
        if key in seen:
            return
        seen.add(key)
        found.append(p)

    for raw in _GAME_CANDIDATES:
        p = _expand(raw)
        if p.is_dir():
            _push(p)

    # exe 同级 / 上一级目录下的 .minecraft（便携版整合包常见布局）
    for base in (app_dir(), app_dir().parent):
        for name in (".minecraft", "minecraft"):
            p = base / name
            if p.is_dir():
                _push(p)

    return found


def default_game_dir() -> Path:
    """自动筛选出的游戏目录；找不到时回落到 app_dir()/minecraft。"""
    found = detect_game_dirs()
    if found:
        return found[0]
    return app_dir() / "minecraft"


def looks_like_game_dir(p: Path) -> bool:
    """判断目录是否像一个 Minecraft 游戏目录。"""
    if not p or not p.is_dir():
        return False
    for mark in ("versions", ".versions", "mods", "resourcepacks", "options.txt",
                 "launcher_profiles.json", "config"):
        if (p / mark).exists():
            return True
    return False


# ---------------------------------------------------------------- 版本 / 汉化包


def versions_dir(game_dir: Path) -> Path:
    """版本目录：优先 .versions，其次 versions。"""
    gd = Path(game_dir)
    if (gd / ".versions").is_dir():
        return gd / ".versions"
    if (gd / "versions").is_dir():
        return gd / "versions"
    return gd / ".versions"


def list_versions(game_dir: Path) -> list[str]:
    """列出当前游戏目录下可用的版本名（只认目录，排除汉化包与压缩包）。"""
    out: list[str] = []
    for base in (Path(game_dir) / ".versions", Path(game_dir) / "versions"):
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir(), key=lambda x: x.name.lower()):
            if not child.is_dir():
                continue      # 排除 *.zip 等「同名压缩包」脏条目
            if child.name == "汉化包":
                continue
            # 版本目录里通常有 <name>.jar 或 <name>.json
            has_meta = any(child.glob("*.json")) or any(child.glob("*.jar"))
            if has_meta or (child / "mods").is_dir():
                out.append(child.name)
    # 去重保序
    seen: set[str] = set()
    uniq: list[str] = []
    for v in out:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def mods_dirs(game_dir: Path, version: str | None = None) -> list[Path]:
    """返回需要扫描的模组目录列表。

    严格按版本隔离：只扫 ``<版本>/mods``，**不再回落游戏根目录的全局 ``mods/``**。

    原因：根目录 ``mods/`` 里的 jar 是给「非版本隔离」启动方式用的，往往属于
    另一个整合包 / 另一个 MC 版本。若一并扫描，选中一个没有装模组的版本也会
    把其它版本的模组列出来并翻译（跨版本污染）。版本启动器（PCL2 等）开启版本
    隔离后，实际生效的模组只来自 ``<版本>/mods``。
    """
    gd = Path(game_dir)
    dirs: list[Path] = []
    if version:
        for base in (gd / ".versions", gd / "versions"):
            d = base / version / "mods"
            if d.is_dir():
                dirs.append(d)
    else:
        # 未选版本时才回落到全局 mods/，保证「没选版本」也有东西可扫
        d = gd / "mods"
        if d.is_dir():
            dirs.append(d)
    return dirs


def hanhuabao_root(game_dir: Path) -> Path:
    """汉化包根目录：<游戏目录>/.versions/汉化包。

    需求 1：点击「开始翻译」后在 .versions 下创建名为「汉化包」的文件夹，
    当前版本的所有汉化包文件统一存放在此。
    """
    root = versions_dir(game_dir) / "汉化包"
    root.mkdir(parents=True, exist_ok=True)
    return root


def hanhuabao_version_dir(game_dir: Path, version: str) -> Path:
    """某个版本的汉化包目录：<游戏目录>/.versions/汉化包/<版本>。"""
    d = hanhuabao_root(game_dir) / (version or "_default")
    d.mkdir(parents=True, exist_ok=True)
    return d


def resourcepacks_dir(game_dir: Path) -> Path:
    """游戏资源包目录（汉化包启用时复制到这里）。"""
    d = Path(game_dir) / "resourcepacks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def options_txt(game_dir: Path) -> Path:
    return Path(game_dir) / "options.txt"
