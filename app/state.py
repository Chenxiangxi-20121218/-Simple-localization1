# -*- coding: utf-8 -*-
"""全局状态单例 + 配置持久化。

所有页面都通过 ``STATE`` 读写数据、监听信号，避免页面之间互相耦合。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from . import paths
from .theme import C, apply_accent

#: 程序版本号 x.y.z —— x 大版本 / y 小更新 / z 维护版（每次更新递增，见 tools/bump_version.py）
APP_VERSION = "1.0.10"

DEFAULT_WELCOME = "欢迎使用 minecraft 模组汉化工具"
DEFAULT_TRANSLATOR_TITLE = "MC 模组汉化工具"

#: 内置冷知识（resources/lengzhishi.txt 不存在时使用）
FALLBACK_LENGZHISHI = [
    "冷知识：Minecraft 的英文名最初叫 Cave Game。",
    "冷知识：苦力怕其实是猪的模型写错了尺寸产生的。",
    "冷知识：Java 版 1.13 之前的语言文件是 .lang 纯文本格式。",
    "冷知识：资源包可以覆盖模组自带的语言文件，这是汉化包能生效的原理。",
    "冷知识：Notch 在 2009 年 5 月 17 日发布了第一个公开版本。",
    "冷知识：末影人的音效是把人说「hi」的录音倒放并降调得到的。",
    "冷知识：中文译名「我的世界」由玩家社区投票确定。",
    "冷知识：一个模组可以有多个 modid，扫描时都要覆盖到。",
    "冷知识：主菜单的闪烁标语里藏着一句「Also try Terraria!」。",
    "冷知识：恶魂的哭声其实是拿猫的叫声加工出来的。",
    "冷知识：附魔台最多需要 15 个书架环绕，才能达到最高附魔等级。",
    "冷知识：幻翼会在玩家连续三个游戏日没睡觉后开始生成。",
    "冷知识：精准采集和时运是互斥附魔，不能同时生效。",
    "冷知识：末影箱的内容按玩家独立存储，共用同一个箱子也不会串。",
    "冷知识：下界合金锭由下界合金碎片加金锭合成，碎片来自远古残骸。",
    "冷知识：末地传送门需要 12 个末影之眼才能激活。",
    "冷知识：语言文件里的键名区分大小写，改错大小写会让翻译失效。",
    "冷知识：语言文件必须存为 UTF-8，否则中文会显示成乱码。",
    "冷知识：汉化资源包要排在资源包列表最上方，才能覆盖其他包的同名键。",
    "冷知识：被硬编码进代码的文本无法用资源包汉化，只能改源码。",
]

FALLBACK_SPONSORS = "感谢以下赞助者"


class State(QObject):
    """全局状态。"""

    modelChanged = Signal()
    gameDirChanged = Signal()
    versionChanged = Signal()
    modsChanged = Signal()
    packsChanged = Signal()
    logChanged = Signal(str)
    themeChanged = Signal()
    sponsorsChanged = Signal()
    enhancedTranslateChanged = Signal(bool)   # 强化翻译开关
    progressChanged = Signal(int, str)   # percent, 预计剩余文案
    finished = Signal(str)               # 完成提示语

    def __init__(self) -> None:
        super().__init__()
        # --- 模型 ---
        self.model_path: str = ""
        self.model_name: str = ""
        self.model_info: dict = {}

        # --- 目录 / 版本 ---
        self.game_dir: str = str(paths.default_game_dir())
        self.current_version: str = ""
        self.auto_filter: bool = True

        # --- 翻译选项 ---
        #: 强化翻译：每次翻译后做通顺性检查，不通顺则自动重译（默认关闭）
        self.enhanced_translate: bool = False

        # --- 模组 / 汉化包 ---
        self.mods: list[dict] = []            # 扫描结果
        self.selected_mods: set[str] = set()
        self.packs: list[dict] = []           # 汉化包列表
        self.pack_enabled: dict[str, bool] = {}

        # --- 个性化 ---
        self.welcome_text: str = DEFAULT_WELCOME
        self.accent_color: str = C.BLUE
        self.border_color: str = C.BORDER
        self.translator_title: str = DEFAULT_TRANSLATOR_TITLE
        self.personalize_unlocked: bool = False   # 付费解锁

        # --- 其他 ---
        self.sponsors: str = FALLBACK_SPONSORS
        self.last_log: str = "就绪，等待开始。"
        self.last_translate_time: str = ""

        self.load()

    # ------------------------------------------------------------ 配置读写

    def to_dict(self) -> dict:
        return {
            "app_version": APP_VERSION,
            "model_path": self.model_path,
            "model_name": self.model_name,
            "game_dir": self.game_dir,
            "current_version": self.current_version,
            "auto_filter": self.auto_filter,
            "enhanced_translate": self.enhanced_translate,
            "welcome_text": self.welcome_text,
            "accent_color": self.accent_color,
            "border_color": self.border_color,
            "translator_title": self.translator_title,
            "personalize_unlocked": self.personalize_unlocked,
            "pack_enabled": self.pack_enabled,
            "last_translate_time": self.last_translate_time,
        }

    def load(self) -> None:
        f = paths.config_file()
        if not f.is_file():
            return
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for key in ("model_path", "model_name", "game_dir", "current_version",
                    "welcome_text", "accent_color", "border_color",
                    "translator_title", "last_translate_time"):
            if isinstance(data.get(key), str) and data.get(key):
                setattr(self, key, data[key])
        if isinstance(data.get("auto_filter"), bool):
            self.auto_filter = data["auto_filter"]
        if isinstance(data.get("enhanced_translate"), bool):
            self.enhanced_translate = data["enhanced_translate"]
        if isinstance(data.get("personalize_unlocked"), bool):
            self.personalize_unlocked = data["personalize_unlocked"]
        if isinstance(data.get("pack_enabled"), dict):
            self.pack_enabled = {str(k): bool(v) for k, v in data["pack_enabled"].items()}
        # 模型文件被删掉了 -> 视为未选择
        if self.model_path and not Path(self.model_path).is_file():
            self.model_path = ""
            self.model_name = ""
        apply_accent(self.accent_color, self.border_color)

    def save(self) -> None:
        try:
            paths.config_file().write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    # ------------------------------------------------------------ 模型

    def set_model(self, path: str, name: str, info: dict | None = None) -> None:
        self.model_path = path
        self.model_name = name
        self.model_info = info or {}
        self.save()
        self.modelChanged.emit()

    def clear_model(self) -> None:
        self.model_path = ""
        self.model_name = ""
        self.model_info = {}
        self.save()
        self.modelChanged.emit()

    def has_model(self) -> bool:
        return bool(self.model_path) and Path(self.model_path).is_file()

    # ------------------------------------------------------------ 目录 / 版本

    def set_game_dir(self, d: str) -> None:
        self.game_dir = d
        self.save()
        self.gameDirChanged.emit()

    def game_path(self) -> Path:
        return Path(self.game_dir)

    def set_version(self, v: str) -> None:
        if self.current_version != v:
            self.current_version = v
            self.selected_mods.clear()
            self.save()
            self.versionChanged.emit()

    # ------------------------------------------------------------ 模组

    def set_mods(self, mods: list[dict]) -> None:
        self.mods = mods
        valid = {m["id"] for m in mods}
        self.selected_mods &= valid
        self.modsChanged.emit()

    def toggle_mod(self, mod_id: str, on: bool) -> None:
        if on:
            self.selected_mods.add(mod_id)
        else:
            self.selected_mods.discard(mod_id)
        self.modsChanged.emit()

    def selected_mod_list(self) -> list[dict]:
        return [m for m in self.mods if m["id"] in self.selected_mods]

    def can_translate(self) -> bool:
        """至少选中一个模组且已选择模型。"""
        return bool(self.selected_mods) and self.has_model()

    # ------------------------------------------------------------ 汉化包

    def set_packs(self, packs: list[dict]) -> None:
        self.packs = packs
        for p in packs:
            self.pack_enabled.setdefault(p["id"], False)
        self.packsChanged.emit()

    def set_pack_enabled(self, pack_id: str, on: bool) -> None:
        self.pack_enabled[pack_id] = on
        self.save()
        self.packsChanged.emit()

    # ------------------------------------------------------------ 翻译选项

    def set_enhanced_translate(self, on: bool) -> None:
        """开关「强化翻译」。值未变化时不落盘、不发信号。"""
        on = bool(on)
        if self.enhanced_translate == on:
            return
        self.enhanced_translate = on
        self.save()
        self.enhancedTranslateChanged.emit(on)

    # ------------------------------------------------------------ 个性化 / 日志

    def set_welcome(self, text: str) -> None:
        self.welcome_text = text or DEFAULT_WELCOME
        self.save()

    def set_personalize(self, accent: str, border: str, title: str) -> None:
        self.accent_color = accent
        self.border_color = border
        self.translator_title = title or DEFAULT_TRANSLATOR_TITLE
        apply_accent(accent, border)
        self.save()
        self.themeChanged.emit()

    def log(self, text: str) -> None:
        """只保留一行主要日志。"""
        self.last_log = text
        self.logChanged.emit(text)

    # ------------------------------------------------------------ 文本资源

    def lengzhishi_lines(self) -> list[str]:
        """读取 resources/lengzhishi.txt，按行返回（过滤空行）。"""
        f = paths.resource_dir() / "lengzhishi.txt"
        if f.is_file():
            try:
                lines = [ln.strip() for ln in f.read_text(encoding="utf-8").splitlines()]
                lines = [ln for ln in lines if ln]
                if lines:
                    return lines
            except OSError:
                pass
        return list(FALLBACK_LENGZHISHI)

    def random_lengzhishi(self) -> str:
        """随机一条冷知识；遇到空格则跳过（空格分隔时取非空片段）。"""
        lines = self.lengzhishi_lines()
        for _ in range(20):
            line = random.choice(lines)
            line = line.strip()
            if not line or line.isspace():
                continue
            parts = [p for p in line.split(" ") if p.strip()]
            if not parts:
                continue
            return line
        return lines[0] if lines else ""

    def sponsor_url(self) -> str:
        """读取 resources/wangzhi.txt 中的赞助网址；文件不存在返回空串（不跳转）。"""
        f = paths.resource_dir() / "wangzhi.txt"
        if not f.is_file():
            return ""
        try:
            for ln in f.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    return ln
        except OSError:
            return ""
        return ""

    def sponsors_text(self) -> str:
        """赞助者名单（空格分隔）。

        读取 resources/sponsors.txt，跳过 ``#`` 注释行，
        所有名字统一用单个空格连接后原样展示。
        """
        f = paths.resource_dir() / "sponsors.txt"
        if f.is_file():
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
                lines = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
                names: list[str] = []
                for ln in lines:
                    names.extend(ln.split())
                if names:
                    return " ".join(names)
            except OSError:
                pass
        return " ".join(self.sponsors.split())


#: 全局单例
STATE = State()
