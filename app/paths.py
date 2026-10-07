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


def version_bases(game_dir: Path) -> list[Path]:
    """版本根目录候选（只返回真实存在的；都不存在时给出默认的 .versions）。"""
    gd = Path(game_dir)
    out: list[Path] = []
    for name in (".versions", "versions"):
        d = gd / name
        if d.is_dir():
            out.append(d)
    return out or [gd / ".versions"]


def version_instance_path(game_dir: Path, version: str | None) -> Path | None:
    """版本实例目录的路径（只计算，不创建）；找不到返回 None。"""
    if not version:
        return None
    for base in version_bases(game_dir):
        d = base / version
        if d.is_dir():
            return d
    return None


def _is_isolated_instance(d: Path) -> bool:
    """判断版本目录是否是一个「版本隔离」实例目录。

    PCL2 / HMCL 开启版本隔离后，游戏的工作目录就是版本目录：``options.txt``、
    ``saves``、``logs``、``mods`` 都落在里面。未开启隔离时这些东西只在游戏根目录，
    版本目录里只有 ``<版本>.jar`` / ``<版本>.json``。

    ⚠️ 不能只看 ``resourcepacks`` —— 启动器/整合包会预建这个空目录，
    它不能证明隔离已开启。
    """
    for mark in ("options.txt", "saves", "logs"):
        if (d / mark).exists():
            return True
    mods = d / "mods"
    if mods.is_dir():
        try:
            if any(mods.iterdir()):
                return True
        except OSError:
            return False
    return False


def instance_dir(game_dir: Path, version: str | None = None) -> Path:
    """该版本**实际生效**的游戏目录（版本隔离感知）。

    开启版本隔离时返回 ``<游戏目录>/versions/<版本>/``；未开启（或版本目录不存在、
    不像实例目录）时回落到游戏根目录。
    """
    gd = Path(game_dir)
    d = version_instance_path(gd, version)
    if d is not None and _is_isolated_instance(d):
        return d
    return gd


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


def hanhuabao_root_path(game_dir: Path, version: str | None = None) -> Path:
    """汉化包目录的路径（只计算，不创建）。

    - 指定版本 -> ``<游戏目录>/versions/<版本>/汉化包``（与实例一一对应）
    - 未指定   -> ``<游戏目录>/versions/汉化包``（历史共享目录，仅用于兼容读取）
    """
    gd = Path(game_dir)
    if version:
        d = version_instance_path(gd, version)
        if d is not None:
            return d / "汉化包"
        # 该版本还没安装：仍按 <版本>/汉化包 布局给出路径
        return version_bases(gd)[0] / version / "汉化包"
    return version_bases(gd)[0] / "汉化包"


def hanhuabao_root(game_dir: Path, version: str | None = None) -> Path:
    """汉化包目录（会创建）。

    需求 1 的修订：汉化包要放进**所选版本对应的实例目录**，即
    ``<游戏目录>/versions/<版本>/汉化包``，而不是所有版本共用一个目录。
    版本目录不存在时（未安装该版本）仍按 ``versions/<版本>/汉化包`` 创建。
    """
    d = hanhuabao_root_path(game_dir, version)
    d.mkdir(parents=True, exist_ok=True)
    return d


def resourcepacks_dir(game_dir: Path, version: str | None = None) -> Path:
    """游戏资源包目录（汉化包启用时复制到这里）。

    版本隔离时位于 ``<版本实例>/resourcepacks`` —— 游戏只读这一份，
    写到游戏根目录是无效的。
    """
    d = instance_dir(game_dir, version) / "resourcepacks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def options_txt(game_dir: Path, version: str | None = None) -> Path:
    """options.txt 路径（版本隔离时位于版本实例目录内）。"""
    return instance_dir(game_dir, version) / "options.txt"
