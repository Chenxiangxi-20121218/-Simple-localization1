# -*- coding: utf-8 -*-
"""离线机器翻译引擎（可插拔）。

本模块实现「离线、确定性、不联网」的翻译能力，对外只暴露 5 个符号：

- :class:`ModelError`     —— 加载模型失败时抛出的异常
- :func:`load_model`      —— 加载 .zip 模型，返回 (模型名, 信息 dict)
- :class:`TranslateModel` —— 翻译模型对象，提供 ``translate`` / ``translate_batch``
- :func:`get_model`       —— 取当前 STATE 对应的模型单例（绝不抛异常）
- :func:`estimate_seconds`—— 粗略估算翻译耗时（纯函数）

设计目标：**可插拔**。当前用「整句词典 → 术语替换 → 未命中保留原文」的
确定性策略产出中文，并内置一份足够大的 Minecraft 术语表兜底；未来接入真实
NMT 模型时，只要替换 :class:`TranslateModel` 的内部实现即可，对外接口不变。

依赖：仅标准库（zipfile / json / re / csv / io / pathlib / functools）。
本模块**不在导入期**依赖 PySide6；只有 :func:`get_model` 内部才延迟导入
``..state``，因此纯翻译逻辑可在无 Qt 环境下使用。
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path

__all__ = [
    "ModelError",
    "load_model",
    "TranslateModel",
    "get_model",
    "estimate_seconds",
    "BUILTIN_TERMS",
]


class ModelError(Exception):
    """模型加载失败（文件不存在 / 不是 zip / 内容为空 / 已损坏）。"""


# ====================================================================== 内置术语表
#
# 说明：键为英文原文（匹配时大小写不敏感），值为简体中文。
# 这份词表保证「无模型」或「模型很小」时仍能产出可读的中文。
# 注意：dict 字面量中不得出现重复键（重复会静默覆盖）。

BUILTIN_TERMS: dict[str, str] = {
    # ---- 方块 / 基础材料 ----
    "Stone": "石头",
    "Cobblestone": "圆石",
    "Dirt": "泥土",
    "Grass Block": "草方块",
    "Sand": "沙子",
    "Gravel": "沙砾",
    "Oak Log": "橡木原木",
    "Log": "原木",
    "Planks": "木板",
    "Sapling": "树苗",
    "Leaves": "树叶",
    "Flower": "花",
    "Mushroom": "蘑菇",
    "Glass": "玻璃",
    "Wool": "羊毛",
    "Brick": "砖块",
    "Obsidian": "黑曜石",
    "Bedrock": "基岩",
    "Clay": "黏土",
    "Snow": "雪",
    "Ice": "冰",
    "Water": "水",
    "Lava": "岩浆",
    "Fire": "火",
    "Air": "空气",
    "Crafting Table": "工作台",
    "Furnace": "熔炉",
    "Chest": "箱子",
    "Ender Chest": "末影箱",
    "Torch": "火把",
    "Bed": "床",
    "Door": "门",
    "Ladder": "梯子",
    "Bucket": "桶",
    "Water Bucket": "水桶",
    "Lava Bucket": "岩浆桶",
    # ---- 矿物 / 材料 ----
    "Diamond": "钻石",
    "Emerald": "绿宝石",
    "Gold Ingot": "金锭",
    "Iron Ingot": "铁锭",
    "Netherite Ingot": "下界合金锭",
    "Coal": "煤炭",
    "Redstone": "红石",
    "Lapis Lazuli": "青金石",
    "Quartz": "石英",
    # ---- 工具 / 盔甲 / 武器 ----
    "Pickaxe": "镐",
    "Axe": "斧",
    "Shovel": "锹",
    "Sword": "剑",
    "Hoe": "锄",
    "Helmet": "头盔",
    "Chestplate": "胸甲",
    "Leggings": "护腿",
    "Boots": "靴子",
    "Shield": "盾牌",
    "Bow": "弓",
    "Arrow": "箭",
    # ---- 状态 / 机制 ----
    "Health": "生命值",
    "Hunger": "饥饿值",
    "Experience": "经验",
    "Inventory": "物品栏",
    "Item": "物品",
    "Block": "方块",
    "Entity": "实体",
    "Mob": "生物",
    "Spawn": "生成",
    "Biome": "生物群系",
    "Dimension": "维度",
    "Nether": "下界",
    "The End": "末地",
    "Overworld": "主世界",
    "Village": "村庄",
    "Villager": "村民",
    # ---- 生物 ----
    "Zombie": "僵尸",
    "Skeleton": "骷髅",
    "Creeper": "苦力怕",
    "Enderman": "末影人",
    "Spider": "蜘蛛",
    "Slime": "史莱姆",
    "Witch": "女巫",
    "Wither": "凋灵",
    "Ender Dragon": "末影龙",
    # ---- 附魔 / 效果 ----
    "Enchantment": "附魔",
    "Potion": "药水",
    "Recipe": "配方",
    "Crafting": "合成",
    "Smelting": "烧炼",
    "Upgrade": "升级",
    "Durability": "耐久度",
    "Damage": "伤害",
    "Speed": "速度",
    "Strength": "力量",
    "Regeneration": "生命恢复",
    "Fire Resistance": "抗火",
    "Night Vision": "夜视",
    # ---- 界面通用 ----
    "Configuration": "配置",
    "Config": "配置",
    "Settings": "设置",
    "Options": "选项",
    "Enabled": "已启用",
    "Disabled": "已禁用",
    "On": "开",
    "Off": "关",
    "Yes": "是",
    "No": "否",
    "Default": "默认",
    "Custom": "自定义",
    "Search": "搜索",
    "Sort": "排序",
    "Filter": "筛选",
    "Add": "添加",
    "Remove": "移除",
    "Delete": "删除",
    "Edit": "编辑",
    "Save": "保存",
    "Cancel": "取消",
    "Confirm": "确认",
    "Close": "关闭",
    "Open": "打开",
    "Back": "返回",
    "Next": "下一步",
    "Done": "完成",
    "Reset": "重置",
    "Apply": "应用",
    "Refresh": "刷新",
    "Loading": "加载中",
    "Error": "错误",
    "Warning": "警告",
    "Info": "信息",
    "Success": "成功",
    "Failed": "失败",
    "Unknown": "未知",
    "Empty": "空",
    "Full": "满",
    "Amount": "数量",
    "Count": "数量",
    "Total": "总计",
    "Max": "最大",
    "Min": "最小",
    "Mode": "模式",
    "Type": "类型",
    "Name": "名称",
    "Description": "描述",
    "Tooltip": "提示",
    "Cooldown": "冷却",
    "Range": "范围",
    "Radius": "半径",
    "Chance": "概率",
    "Level": "等级",
    "Tier": "等级",
    "Progress": "进度",
    "Time": "时间",
    "Seconds": "秒",
    "Minutes": "分钟",
    "Ticks": "刻",
    "Chunk": "区块",
    "Coordinates": "坐标",
    "Distance": "距离",
    "Direction": "方向",
    "North": "北",
    "South": "南",
    "East": "东",
    "West": "西",
    "Up": "上",
    "Down": "下",
    "Left": "左",
    "Right": "右",
    # ---- 世界 / 服务器 ----
    "Player": "玩家",
    "Server": "服务器",
    "World": "世界",
    "Seed": "种子",
    "Difficulty": "难度",
    "Peaceful": "和平",
    "Easy": "简单",
    "Normal": "普通",
    "Hard": "困难",
    "Creative": "创造",
    "Survival": "生存",
    "Adventure": "冒险",
    "Spectator": "旁观",
    # ---- 分类 ----
    "Tool": "工具",
    "Armor": "盔甲",
    "Weapon": "武器",
    "Food": "食物",
    "Fuel": "燃料",
    "Storage": "存储",
    "Energy": "能量",
    "Power": "功率",
    "Machine": "机器",
    "Module": "模块",
    "Fluid": "流体",
    "Tank": "储罐",
    "Pipe": "管道",
    "Cable": "线缆",
    "Wrench": "扳手",
    "Hammer": "锤子",
    "Guide": "指南",
    "Manual": "手册",
    "Compat": "兼容",
    # ---- 食物 / 其他常用 ----
    "Apple": "苹果",
    "Bread": "面包",
    "Wheat": "小麦",
    "Potato": "土豆",
    "Carrot": "胡萝卜",
    "Egg": "鸡蛋",
    "Milk": "牛奶",
    "Sugar": "糖",
}

#: 内置兜底模型名
_BUILTIN_NAME = "内置基础词表"

# ====================================================================== 占位符保护
#
# 翻译前把下列片段抽出，替换为哨兵 ``\x00{i}\x00``，翻译后再按原顺序还原。
# 顺序很重要：先匹配更具体的模式（双花括号 → 带序号格式符 → 通用格式符 → …）。

_PLACEHOLDER_RE = re.compile(
    r"\{\{.*?\}\}"                                        # {{...}} 双花括号（如 translate 组件的转义）
    r"|%[0-9]+\$[sdif]"                                   # %1$s %2$d 带序号格式符
    r"|%(?:[0-9]+\$)?[-#+ 0,(]*[0-9]*(?:\.[0-9]+)?[sdfegxXo%]"  # %s %d %.2f %% 等
    r"|%n"                                                # %n 换行
    r"|\\[ntr]"                                           # 字面 \n \t \r
    r"|§[0-9a-fk-orA-FK-OR]"                              # § 颜色码（§ 即 \u00a7）
    r"|&[0-9a-fk-orA-FK-OR]"                              # & 颜色码
    r"|\{[^{}]*\}"                                        # {0} {name} {}
)

#: 哨兵：\x00 + 序号 + \x00
_SENTINEL_RE = re.compile(r"\x00(\d+)\x00")

#: 术语替换后，去掉两个中文字符之间残留的多余空格（「石头 剑」→「石头剑」）
_CJK_SPACE_RE = re.compile(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])")

#: 构建术语替换正则时最多使用的词条数（防止超大词典把正则撑爆）
_MAX_PATTERN_TERMS = 60000

# ====================================================================== zip 解析

#: 元信息文件名（小写）
_META_FILES = {"model.json", "config.json", "meta.json"}
#: 词典文件名（小写）
_DICT_FILES = {
    "dict.json", "glossary.json", "terms.json", "phrases.json",
    "translations.json", "dictionary.json",
}
#: csv/tsv 表头识别（用于跳过表头行）
_HEADER_KEYS = {"en", "key", "src", "source", "english", "id", "name"}
_HEADER_VALS = {"zh", "value", "dst", "target", "chinese", "translation", "cn"}


def _decode_bytes(raw: bytes) -> str | None:
    """按 utf-8 → utf-8-sig → gbk 顺序尝试解码，全部失败返回 None。"""
    for enc in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def _safe_json(text: str) -> object | None:
    """容错 JSON 解析，失败返回 None。"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def _parse_dict_obj(obj: object) -> dict[str, str]:
    """把多种结构统一成 ``{英文: 中文}``。

    支持：
    - 扁平映射 ``{"en": "zh"}``
    - 数组 ``[{"src": "..", "dst": ".."}]`` / ``[{"en": "..", "zh": ".."}]``
    - 二元数组 ``[["en", "zh"]]``
    """
    out: dict[str, str] = {}
    if isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(val, str):
                if key:
                    out[str(key)] = val
            elif isinstance(val, dict):
                # 嵌套结构 {"en": {"zh": "..."}} 之类
                for tk in ("zh", "dst", "target", "translation", "value", "cn"):
                    tv = val.get(tk)
                    if isinstance(tv, str):
                        out[str(key)] = tv
                        break
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                src = (item.get("src") or item.get("en") or item.get("source")
                       or item.get("key") or item.get("k"))
                dst = (item.get("dst") or item.get("zh") or item.get("target")
                       or item.get("translation") or item.get("value")
                       or item.get("v") or item.get("cn"))
                if isinstance(src, str) and isinstance(dst, str) and src:
                    out[src] = dst
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                a, b = item[0], item[1]
                if isinstance(a, str) and isinstance(b, str) and a:
                    out[a] = b
    return out


def _parse_table(text: str) -> dict[str, str]:
    """解析两列 tsv/csv（第一列英文、第二列中文）。"""
    out: dict[str, str] = {}
    rows_text = [ln for ln in text.splitlines() if ln.strip()]
    if not rows_text:
        return out
    # 优先制表符；否则用逗号（csv 模块能正确处理引号包裹的逗号）
    delim = "\t" if "\t" in rows_text[0] else ","
    try:
        reader = csv.reader(io.StringIO(text), delimiter=delim)
        rows = list(reader)
    except (csv.Error, ValueError):
        return out
    for idx, row in enumerate(rows):
        if len(row) < 2:
            continue
        src = (row[0] or "").strip()
        dst = (row[1] or "").strip()
        if not src or not dst:
            continue
        if idx == 0 and src.lower() in _HEADER_KEYS and dst.lower() in _HEADER_VALS:
            continue  # 跳过表头
        out[src] = dst
    return out


def _load_zip(zip_path: str) -> tuple[str, dict, dict[str, str]]:
    """解析模型 zip，返回 ``(模型名, 信息 dict, 词典 dict)``。

    失败（不存在 / 不是 zip / 内容为空 / 损坏）抛 :class:`ModelError`；
    单个文件解析失败则跳过，绝不中断。
    """
    p = Path(zip_path)
    if not p.is_file():
        raise ModelError(f"模型文件不存在：{zip_path}")
    try:
        if not zipfile.is_zipfile(p):
            raise ModelError(f"不是有效的 zip 模型文件：{zip_path}")
    except OSError as exc:
        raise ModelError(f"无法打开模型文件：{exc}") from exc

    entries: dict[str, str] = {}
    meta: dict = {}
    try:
        with zipfile.ZipFile(p) as zf:
            infos = zf.infolist()
            if not infos:
                raise ModelError(f"模型文件内容为空：{zip_path}")
            for info in infos:
                if info.is_dir():
                    continue
                base = info.filename.rsplit("/", 1)[-1].lower()
                try:
                    raw = zf.read(info)
                except (KeyError, OSError, zipfile.BadZipFile, RuntimeError):
                    continue
                text = _decode_bytes(raw)
                if text is None:
                    continue
                # --- 元信息 ---
                if base in _META_FILES:
                    obj = _safe_json(text)
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if isinstance(v, (str, int, float)) and not meta.get(k):
                                meta[k] = v
                    continue
                # --- 已知词典文件 ---
                if base in _DICT_FILES:
                    entries.update(_parse_dict_obj(_safe_json(text)))
                    continue
                # --- 任意扁平 json ---
                if base.endswith(".json"):
                    flat = _parse_dict_obj(_safe_json(text))
                    if flat:
                        entries.update(flat)
                    continue
                # --- 两列表格 ---
                if base.endswith(".tsv") or base.endswith(".csv"):
                    entries.update(_parse_table(text))
                    continue
    except ModelError:
        raise
    except zipfile.BadZipFile as exc:
        raise ModelError(f"模型文件已损坏：{exc}") from exc
    except OSError as exc:
        raise ModelError(f"读取模型文件失败：{exc}") from exc

    # --- 模型名：优先元信息 name，其次 zip 文件名 ---
    name = ""
    for key in ("name", "model_name", "title", "displayName", "display_name"):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            name = val.strip()
            break
    if not name:
        name = p.stem

    info = {
        "name": name,
        "version": str(meta.get("version", "") or ""),
        "author": str(meta.get("author", "") or ""),
        "type": str(meta.get("type", "") or "dictionary"),
        "entries": len(entries),
        "source": "zip",
        "path": str(p.resolve()),
    }
    return name, info, entries


def load_model(zip_path: str) -> tuple[str, dict]:
    """加载 .zip 翻译模型，返回 ``(模型名, 模型信息 dict)``。失败抛 :class:`ModelError`。"""
    name, info, _entries = _load_zip(zip_path)
    return name, info


# ====================================================================== 翻译模型


class TranslateModel:
    """离线翻译模型。

    ``zip_path`` 为空 / None 时，退化为「内置基础词表」模型（仍可翻译）。
    """

    def __init__(self, zip_path: str | None = None) -> None:
        self._path: str = str(zip_path) if zip_path else ""
        self._entries: dict[str, str] = {}
        self._cache: dict[str, str] = {}

        if self._path:
            name, info, entries = _load_zip(self._path)
            self._name: str = name
            self._info: dict = info
            self._entries = entries
        else:
            self._name = _BUILTIN_NAME
            self._info = {
                "name": _BUILTIN_NAME,
                "version": "1.0",
                "author": "内置",
                "type": "builtin",
                "entries": len(BUILTIN_TERMS),
                "source": "builtin",
                "path": "",
            }

        self._build_lookup()

    # ------------------------------------------------------------ 属性

    @property
    def name(self) -> str:
        return self._name

    @property
    def info(self) -> dict:
        return self._info

    # ------------------------------------------------------------ 词典构建

    def _build_lookup(self) -> None:
        """合并「内置词表 + 模型词典」，构建整句词典与术语替换正则。"""
        # 内置兜底在前，模型词典覆盖同名条目
        merged: dict[str, str] = dict(BUILTIN_TERMS)
        merged.update(self._entries)

        # 大小写不敏感查找表
        lower: dict[str, str] = {}
        for k, v in merged.items():
            if k:
                lower[k.lower()] = v
        # 简单复数兜底：Diamond -> Diamonds、Crafting Table -> Crafting Tables
        for k, v in list(merged.items()):
            if not k:
                continue
            if not k.lower().endswith("s"):
                pk = (k + "s").lower()
                if pk not in lower:
                    lower[pk] = v

        self._exact: dict[str, str] = merged
        self._lower: dict[str, str] = lower

        # 术语替换正则：按词长从长到短，保留 \b 边界，大小写不敏感
        keys = sorted((k for k in lower if k), key=len, reverse=True)[:_MAX_PATTERN_TERMS]
        if keys:
            pattern = r"\b(?:" + "|".join(re.escape(k) for k in keys) + r")\b"
            try:
                self._pattern = re.compile(pattern, re.IGNORECASE)
            except re.error:
                self._pattern = None
        else:
            self._pattern = None

    # ------------------------------------------------------------ 占位符

    @staticmethod
    def _protect(text: str) -> tuple[str, list[str]]:
        """把占位符 / 格式符 / 颜色码抽成哨兵，返回 (受保护文本, 原文片段列表)。"""
        tokens: list[str] = []

        def repl(m: re.Match) -> str:
            tokens.append(m.group(0))
            return f"\x00{len(tokens) - 1}\x00"

        return _PLACEHOLDER_RE.sub(repl, text), tokens

    @staticmethod
    def _restore(text: str, tokens: list[str], original: str) -> str:
        """还原哨兵。数量或顺序对不上则放弃本次翻译、返回原文（更安全）。"""
        if not tokens:
            return text
        found = _SENTINEL_RE.findall(text)
        expected = [str(i) for i in range(len(tokens))]
        if found != expected:
            return original
        return _SENTINEL_RE.sub(lambda m: tokens[int(m.group(1))], text)

    # ------------------------------------------------------------ 翻译

    def _replace_terms(self, text: str) -> str:
        """术语替换（长词优先、大小写不敏感、保留边界），并清理多余空格。"""
        if self._pattern is None:
            return text
        out = self._pattern.sub(lambda m: self._lower.get(m.group(0).lower(), m.group(0)), text)
        return _CJK_SPACE_RE.sub("", out)

    def _translate_uncached(self, text: str) -> str:
        # 1) 整句词典命中（精确 → 大小写不敏感）
        if text in self._exact:
            return self._exact[text]
        low = text.lower()
        if low in self._lower:
            return self._lower[low]
        # 2) 保护占位符
        protected, tokens = self._protect(text)
        # 3) 术语替换（未命中的英文片段原样保留）
        translated = self._replace_terms(protected)
        # 4) 还原占位符
        return self._restore(translated, tokens, text)

    def translate(self, text: str | None) -> str:
        """翻译单条文本；``None`` / 空串返回 ``""``。同一输入必返回同一输出。"""
        if not text:
            return ""
        text = str(text)
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        result = self._translate_uncached(text)
        self._cache[text] = result
        return result

    def translate_batch(self, texts: list[str]) -> list[str]:
        """批量翻译，逐条调用 :meth:`translate`。"""
        return [self.translate(t) for t in texts]

    # ------------------------------------------------------------ 其他

    def clear_cache(self) -> None:
        """清空翻译缓存（模型热更新后可调用）。"""
        self._cache.clear()


# ====================================================================== 单例


#: 当前缓存的模型单例与其来源路径（"" 表示内置兜底模型）
_model_singleton: TranslateModel | None = None
_model_path_cache: str = ""


def get_model() -> TranslateModel | None:
    """返回当前 STATE 对应的模型单例（未加载 / 路径变了则重新加载）。

    - STATE 未选择模型（或文件已被删除）→ 返回内置兜底模型（``name`` 为「内置基础词表」）。
    - 加载失败 → 记录日志并回落到内置兜底模型。
    **绝不向调用方抛异常。**
    """
    global _model_singleton, _model_path_cache

    try:
        from ..state import STATE  # 延迟导入：模块导入期不依赖 PySide6
        path = STATE.model_path or ""
    except Exception:
        path = ""

    exists = bool(path) and Path(path).is_file()

    if not exists:
        # 内置兜底模型
        if _model_singleton is None or _model_path_cache != "":
            _model_singleton = TranslateModel(None)
            _model_path_cache = ""
        return _model_singleton

    if _model_singleton is not None and _model_path_cache == path:
        return _model_singleton

    try:
        model = TranslateModel(path)
        _model_singleton = model
        _model_path_cache = path
        return model
    except Exception:
        # 加载失败：回落到内置兜底模型，并记录
        _model_singleton = TranslateModel(None)
        _model_path_cache = ""
        try:
            from ..state import STATE
            STATE.log(f"模型加载失败，已回落到内置词表：{path}")
        except Exception:
            pass
        return _model_singleton


# ====================================================================== 耗时估算


def estimate_seconds(text_count: int) -> float:
    """粗略估算翻译耗时（秒）。纯函数、无副作用。"""
    try:
        n = int(text_count)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return 1.0
    return max(1.0, n * 0.012)
