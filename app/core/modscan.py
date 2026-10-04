# -*- coding: utf-8 -*-
"""模组扫描：解析 jar 元数据、命名空间、语言文件与图标。

设计要点：
- 只用标准库（zipfile / json / re / pathlib / tomllib）+ PySide6(QPixmap)。
- 支持 Fabric / Quilt / Forge / NeoForge / LiteLoader 五类元数据。
- 单个 jar 出错只写入 ``error`` 字段，绝不向调用方抛异常。
- 结果带缓存 ``{(jar_path, mtime_ns, size): result}``，切页不重复解压。
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

try:  # Python 3.11+ 自带
    import tomllib  # type: ignore
except ImportError:  # pragma: no cover - 兜底，不引入第三方包
    tomllib = None  # type: ignore

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap

# ------------------------------------------------------------------ 常量 / 正则

#: 合法命名空间：仅小写字母、数字、下划线、点、连字符
_NS_RE = re.compile(r"^[a-z0-9_.-]+$")

#: 匹配 zip 内 ``assets/<ns>/`` 前缀
_ASSET_RE = re.compile(r"^assets/([^/]+)(?:/|$)")

#: 文件名末尾的版本号后缀（如 ``-1.2.3`` / ``_1.20.1`` / ``+v2``）
_VERSION_SUFFIX_RE = re.compile(r"[-_+][vV]?\d[\w.+\-]*$")

#: 版本号提取（用于从依赖范围里捞出第一个版本）
_VER_RE = re.compile(r"\d+\.\d+(?:\.\d+)?")

#: 图标缩放目标尺寸
_ICON_SIZE = 64

#: 内置常用模组名对照表（没有中文语言文件时兜底）
_KNOWN_CN: dict[str, str] = {
    # —— 需求中点名的一批 ——
    "jei": "JEI 物品管理器",
    "create": "机械动力",
    "botania": "植物魔法",
    "twilightforest": "暮色森林",
    "appliedenergistics2": "应用能源2",
    "ae2": "应用能源2",
    "thermal": "热力膨胀",
    "immersiveengineering": "沉浸工程",
    "mekanism": "通用机械",
    "farmersdelight": "农夫乐事",
    "sodium": "钠",
    "iris": "鸢尾",
    "xaeros_minimap": "Xaero的小地图",
    # —— 补充约 35 条 ——
    "xaerosworldmap": "Xaero的世界地图",
    "roughlyenoughitems": "REI 物品管理器",
    "rei": "REI 物品管理器",
    "journeymap": "旅行地图",
    "modmenu": "模组菜单",
    "clothconfig": "Cloth Config API",
    "architectury": "Architectury API",
    "geckolib": "GeckoLib",
    "appleskin": "苹果皮",
    "wthit": "WTHIT 信息显示",
    "hwyla": "HWYLA 信息显示",
    "jade": "Jade 信息显示",
    "tconstruct": "匠魂",
    "mysticalagriculture": "神秘农业",
    "industrialforegoing": "工业先锋",
    "immersivepetroleum": "沉浸石油",
    "enderio": "末影接口",
    "extrautilities": "更多实用设备",
    "ironchest": "铁箱子",
    "storagedrawers": "储物抽屉",
    "curios": "饰品栏",
    "baubles": "饰品栏",
    "railcraft": "铁路工艺",
    "buildcraft": "建筑工艺",
    "forestry": "林业",
    "ic2": "工业时代2",
    "industrialcraft": "工业时代2",
    "galacticraftcore": "星系",
    "bloodmagic": "血魔法",
    "thaumcraft": "神秘时代",
    "ars_nouveau": "新生魔艺",
    "projecte": "等价交换",
    "harvestcraft": "潘马斯农场",
    "pamhc2": "潘马斯农场",
    "simplyjetpacks": "简易喷气背包",
    "yungsbettercaves": "更美的洞穴",
    "yungsbettermineshafts": "更美的废弃矿井",
    "quark": "夸克",
    "engineersdecor": "工程师装饰",
    "computercraft": "电脑模组",
    "opencomputers": "开放式电脑",
    "cofhcore": "CoFH 核心",
}

# ------------------------------------------------------------------ 模块级缓存

#: 缓存键：(jar 绝对路径, mtime_ns, size)；值：扫描结果 dict
_CACHE: dict[tuple, dict] = {}


def clear_cache() -> None:
    """清空扫描缓存。"""
    _CACHE.clear()


# ------------------------------------------------------------------ 对外接口


def scan_mods(mod_dirs: list[Path]) -> list[dict]:
    """扫描一批模组目录，返回模组信息列表（永不抛异常）。"""
    results: list[dict] = []
    try:
        dirs = list(mod_dirs or [])
    except TypeError:
        return results

    seen: set[str] = set()
    for d in dirs:
        try:
            base = Path(d)
            if not base.is_dir():
                continue
            jars = [p for p in base.iterdir() if _is_mod_jar(p)]
            jars.sort(key=lambda p: p.name.lower())
        except OSError:
            continue

        for jar in jars:
            try:
                key_path = str(jar.resolve())
            except OSError:
                key_path = str(jar)
            low = key_path.lower()
            if low in seen:
                continue
            seen.add(low)
            results.append(_scan_cached(jar, key_path))

    # 稳定排序：英文名 -> 路径
    results.sort(key=lambda m: (str(m.get("en_name", "")).lower(),
                                str(m.get("path", "")).lower()))
    return results


def read_lang_entries(jar_path: str | Path, entry: str) -> dict[str, str]:
    """读取 jar 内某个语言文件的 key-value；失败返回空 dict。"""
    try:
        with zipfile.ZipFile(jar_path) as zf:
            names = zf.namelist()
            lower = {n.lower(): n for n in names}
            real = entry if entry in names else lower.get(str(entry).lower(), entry)
            raw = zf.read(real)
    except Exception:
        return {}

    try:
        if str(entry).lower().endswith(".lang"):
            return _parse_lang_text(raw)
        return _parse_json_lang(raw)
    except Exception:
        return {}


# ------------------------------------------------------------------ 单文件扫描


def _is_mod_jar(p: Path) -> bool:
    """只认 ``*.jar``；自然排除 ``.jar.disabled`` / ``*.jar.txt`` / 目录。"""
    try:
        return p.is_file() and p.suffix.lower() == ".jar"
    except OSError:
        return False


def _scan_cached(jar: Path, key_path: str) -> dict:
    """带缓存地扫描单个 jar。"""
    try:
        st = jar.stat()
        mtime_ns, size = st.st_mtime_ns, st.st_size
    except OSError:
        mtime_ns, size = 0, 0

    key = (key_path, mtime_ns, size)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit  # 缓存里同时持有 QPixmap，保证不被 GC

    try:
        entry = _scan_one(jar, key_path)
    except Exception as exc:  # 兜底：理论上 _scan_one 内部已捕获
        entry = _blank(key_path)
        entry["error"] = f"{type(exc).__name__}: {exc}"
        _fallback_names(entry, jar)

    _CACHE[key] = entry
    return entry


def _blank(path_str: str) -> dict:
    """返回结构完整的空白条目。"""
    return {
        "id": path_str,
        "modid": "",
        "namespaces": [],
        "cn_name": "",
        "en_name": "",
        "path": path_str,
        "icon": None,
        "loader": "unknown",
        "mc_version": "",
        "lang_files": [],
        "translatable": False,
        "error": "",
    }


def _scan_one(jar: Path, path_str: str) -> dict:
    """解析单个 jar；任何异常写入 error 并回落文件名。"""
    info = _blank(path_str)
    try:
        with zipfile.ZipFile(jar) as zf:
            _fill(info, zf, jar)
    except Exception as exc:
        info["error"] = f"{type(exc).__name__}: {exc}"
        _fallback_names(info, jar)
    return info


def _fill(info: dict, zf: zipfile.ZipFile, jar: Path) -> None:
    """真正解析逻辑（可能抛异常，由 _scan_one 捕获）。"""
    names = zf.namelist()
    names_set = set(names)
    lower_map: dict[str, str] = {}
    for n in names:
        lower_map.setdefault(n.lower(), n)

    # ---- 元数据 ----
    meta = _parse_metadata(zf, names_set, lower_map)
    info["loader"] = meta.get("loader", "unknown") or "unknown"
    info["mc_version"] = meta.get("mc_version", "") or ""
    meta_name = (meta.get("name") or "").strip()

    # ---- 命名空间：元数据 id + assets 目录名 ----
    asset_ns: list[str] = []
    for n in names:
        m = _ASSET_RE.match(n)
        if m:
            ns = m.group(1)
            if _NS_RE.match(ns) and ns not in asset_ns:
                asset_ns.append(ns)

    namespaces: list[str] = []
    for x in list(meta.get("ids", [])) + asset_ns:
        if isinstance(x, str) and _NS_RE.match(x) and x not in namespaces:
            namespaces.append(x)

    modid = namespaces[0] if namespaces else _modid_from_filename(jar)
    if modid and modid not in namespaces:
        namespaces.insert(0, modid)
    if not namespaces and modid:
        namespaces = [modid]

    info["namespaces"] = namespaces
    info["modid"] = modid

    # ---- 语言文件 ----
    lang_files: list[dict] = []
    for ns in namespaces:
        for lang, fmt in (("en_us.json", "json"), ("en_us.lang", "lang")):
            entry = f"assets/{ns}/lang/{lang}"
            real = _resolve(names_set, lower_map, entry)
            if real:
                lang_files.append({
                    "namespace": ns,
                    "lang": "en_us",
                    "entry": real,
                    "format": fmt,
                })
    info["lang_files"] = lang_files
    info["translatable"] = bool(lang_files)

    # ---- 名称 ----
    en_name, cn_name = _resolve_names(
        zf, names_set, lower_map, namespaces, modid, meta_name, jar)
    info["en_name"] = en_name
    info["cn_name"] = cn_name or en_name

    # ---- 图标 ----
    info["icon"] = _load_icon(zf, names_set, lower_map, namespaces)


# ------------------------------------------------------------------ 元数据解析


def _parse_metadata(zf: zipfile.ZipFile, names_set: set[str],
                    lower_map: dict[str, str]) -> dict:
    """按加载器优先级解析元数据，返回 {loader, ids, name, mc_version}。"""
    meta: dict = {"loader": "unknown", "ids": [], "name": "", "mc_version": ""}

    # ---- Fabric ----
    e = _resolve(names_set, lower_map, "fabric.mod.json")
    if e:
        data = _load_json_bytes(_zip_read_bytes(zf, e))
        if isinstance(data, dict):
            meta["loader"] = "fabric"
            _add_id(meta["ids"], data.get("id"))
            nm = data.get("name")
            if isinstance(nm, str) and nm.strip():
                meta["name"] = nm.strip()
            prov = data.get("provides")
            if isinstance(prov, list):
                for x in prov:
                    _add_id(meta["ids"], x)
            elif isinstance(prov, str):
                _add_id(meta["ids"], prov)
            meta["mc_version"] = _mc_from_fabric_depends(data.get("depends"))
            return meta

    # ---- Quilt ----
    e = _resolve(names_set, lower_map, "quilt.mod.json")
    if e:
        data = _load_json_bytes(_zip_read_bytes(zf, e))
        if isinstance(data, dict):
            meta["loader"] = "quilt"
            ql = data.get("quilt_loader")
            if isinstance(ql, dict):
                _add_id(meta["ids"], ql.get("id"))
                md = ql.get("metadata")
                if isinstance(md, dict):
                    nm = md.get("name")
                    if isinstance(nm, str) and nm.strip():
                        meta["name"] = nm.strip()
                prov = ql.get("provides")
                if isinstance(prov, list):
                    for x in prov:
                        _add_id(meta["ids"], x.get("id") if isinstance(x, dict) else x)
                dep = ql.get("depends")
                if isinstance(dep, list):
                    for d in dep:
                        if isinstance(d, dict) and d.get("id") == "minecraft":
                            vs = d.get("versions")
                            if vs:
                                meta["mc_version"] = _extract_version(str(vs))
            return meta

    # ---- Forge / NeoForge（TOML）----
    for fn in ("META-INF/neoforge.mods.toml", "META-INF/mods.toml"):
        e = _resolve(names_set, lower_map, fn)
        if not e:
            continue
        data = _load_toml_bytes(_zip_read_bytes(zf, e))
        if isinstance(data, dict):
            meta["loader"] = _forge_kind(data, fn)
            mods = data.get("mods")
            if isinstance(mods, list):
                for m in mods:
                    if isinstance(m, dict):
                        _add_id(meta["ids"], m.get("modId"))
                        if not meta["name"]:
                            dn = m.get("displayName")
                            if isinstance(dn, str) and dn.strip():
                                meta["name"] = dn.strip()
            meta["mc_version"] = _mc_from_forge_depends(data.get("dependencies"))
            return meta

    # ---- mcmod.info（旧版 Forge）----
    e = _resolve(names_set, lower_map, "mcmod.info")
    if e:
        data = _load_json_bytes(_zip_read_bytes(zf, e))
        entries = data
        if isinstance(data, dict):
            entries = data.get("modList")
        if isinstance(entries, list):
            meta["loader"] = "forge"
            for m in entries:
                if not isinstance(m, dict):
                    continue
                _add_id(meta["ids"], m.get("modid") or m.get("modId"))
                if not meta["name"]:
                    nm = m.get("name")
                    if isinstance(nm, str) and nm.strip():
                        meta["name"] = nm.strip()
                if not meta["mc_version"]:
                    mv = m.get("mcversion") or m.get("mcVersion")
                    if isinstance(mv, str) and mv.strip():
                        meta["mc_version"] = mv.strip()
            return meta

    # ---- LiteLoader ----
    e = _resolve(names_set, lower_map, "litemod.json")
    if e:
        data = _load_json_bytes(_zip_read_bytes(zf, e))
        if isinstance(data, dict):
            meta["loader"] = "liteloader"
            nm = data.get("name") or data.get("id")
            if isinstance(nm, str) and nm.strip():
                meta["name"] = nm.strip()
                _add_id(meta["ids"], _sanitize_ns(nm))
            mv = data.get("mcversion")
            if isinstance(mv, str) and mv.strip():
                meta["mc_version"] = mv.strip()
            return meta

    return meta


def _forge_kind(data: dict, filename: str) -> str:
    """区分 forge / neoforge。"""
    if "neoforge" in filename.lower():
        return "neoforge"
    if "neoforge" in str(data.get("modLoader", "")).lower():
        return "neoforge"
    return "forge"


def _mc_from_fabric_depends(dep) -> str:
    if isinstance(dep, dict):
        v = dep.get("minecraft")
        if isinstance(v, str):
            return _extract_version(v)
        if isinstance(v, list) and v:
            return _extract_version(str(v[0]))
    return ""


def _mc_from_forge_depends(deps) -> str:
    if isinstance(deps, dict):
        for v in deps.values():
            if not isinstance(v, list):
                continue
            for d in v:
                if not isinstance(d, dict):
                    continue
                if str(d.get("modId", "")).lower() == "minecraft":
                    rng = d.get("versionRange")
                    if rng:
                        return _extract_version(str(rng))
    return ""


def _extract_version(text: str) -> str:
    """从 ``[1.16.5,1.17)`` 之类文本里捞出第一个版本号。"""
    if not isinstance(text, str):
        return ""
    m = _VER_RE.search(text)
    return m.group(0) if m else text.strip()


# ------------------------------------------------------------------ 名称解析


def _resolve_names(zf: zipfile.ZipFile, names_set: set[str],
                   lower_map: dict[str, str], namespaces: list[str],
                   modid: str, meta_name: str, jar: Path) -> tuple[str, str]:
    """返回 (en_name, cn_name)；cn_name 可能为空（由调用方回落 en_name）。"""
    en_name = ""
    name_key = ""

    # 英文名优先：en_us.json / en_us.lang 里的 mod.<ns>.name 之类
    for ns in namespaces:
        entries = _read_ns_lang(zf, names_set, lower_map, ns, "en_us")
        if not entries:
            continue
        key = _pick_name_key(entries, ns)
        if key:
            en_name = entries[key].strip()
            name_key = key
            break

    # 回落：元数据 name -> jar 文件名
    if not en_name:
        en_name = meta_name
    if not en_name:
        en_name = _clean_filename(jar.stem) or jar.stem

    # 中文名优先：zh_cn 里同名键
    cn_name = ""
    if name_key:
        for ns in namespaces:
            zh = _read_ns_lang(zf, names_set, lower_map, ns, "zh_cn")
            v = zh.get(name_key, "")
            if isinstance(v, str) and v.strip():
                cn_name = v.strip()
                break

    # 再试 zh_cn 里的常见键
    if not cn_name:
        for ns in namespaces:
            zh = _read_ns_lang(zf, names_set, lower_map, ns, "zh_cn")
            if not zh:
                continue
            key = _pick_name_key(zh, ns)
            if key and zh[key].strip():
                cn_name = zh[key].strip()
                break

    # 内置对照表
    if not cn_name:
        cn_name = _KNOWN_CN.get(modid, "")

    return en_name, cn_name


def _pick_name_key(entries: dict[str, str], ns: str) -> str:
    """在一张语言表里挑出最像「模组名」的键。"""
    candidates = (
        f"mod.{ns}.name",
        f"itemGroup.{ns}",
        f"itemGroup.{ns}.name",
        f"pack.{ns}.name",
        f"{ns}.name",
        f"{ns}.title",
    )
    for c in candidates:
        v = entries.get(c)
        if isinstance(v, str) and v.strip():
            return c
    # 宽松：以 mod.<ns> 开头且以 .name 结尾
    for k in entries:
        if k.startswith(f"mod.{ns}") and k.endswith(".name") and entries[k].strip():
            return k
    return ""


def _read_ns_lang(zf: zipfile.ZipFile, names_set: set[str],
                  lower_map: dict[str, str], ns: str, lang: str) -> dict[str, str]:
    """读取 ``assets/<ns>/lang/<lang>.json|.lang``。"""
    for fn, is_json in ((f"{lang}.json", True), (f"{lang}.lang", False)):
        entry = f"assets/{ns}/lang/{fn}"
        real = _resolve(names_set, lower_map, entry)
        if not real:
            continue
        raw = _zip_read_bytes(zf, real)
        if raw is None:
            continue
        return _parse_json_lang(raw) if is_json else _parse_lang_text(raw)
    return {}


# ------------------------------------------------------------------ 图标


def _load_icon(zf: zipfile.ZipFile, names_set: set[str],
               lower_map: dict[str, str], namespaces: list[str]) -> QPixmap | None:
    """按固定顺序找图标，缩放到 64x64；找不到返回 None。"""
    candidates: list[str] = []
    for ns in namespaces:
        candidates.append(f"assets/{ns}/icon.png")
        candidates.append(f"assets/{ns}/logo.png")
    candidates += ["icon.png", "logo.png", "pack.png"]
    for ns in namespaces:
        candidates.append(f"assets/{ns}/icon.jpg")

    for c in candidates:
        real = _resolve(names_set, lower_map, c)
        if not real:
            continue
        raw = _zip_read_bytes(zf, real)
        if not raw:
            continue
        pm = QPixmap()
        if pm.loadFromData(raw) and not pm.isNull():
            return _fit_icon(pm)
    return None


def _fit_icon(pm: QPixmap) -> QPixmap:
    """保持比例缩放到 64x64，居中绘制在透明底图上。"""
    canvas = QPixmap(_ICON_SIZE, _ICON_SIZE)
    canvas.fill(Qt.transparent)
    scaled = pm.scaled(_ICON_SIZE, _ICON_SIZE,
                       Qt.KeepAspectRatio, Qt.SmoothTransformation)
    p = QPainter(canvas)
    try:
        x = (_ICON_SIZE - scaled.width()) // 2
        y = (_ICON_SIZE - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)
    finally:
        p.end()
    return canvas


# ------------------------------------------------------------------ 语言解析


def _parse_json_lang(raw: bytes) -> dict[str, str]:
    """解析 JSON 语言文件（容忍 BOM 与 // /* */ 注释），扁平化嵌套字典。"""
    text = _decode(raw)
    text = _strip_json_comments(text)
    try:
        data = json.loads(text)
    except Exception:
        return {}
    out: dict[str, str] = {}
    _flatten(data, "", out)
    return out


def _parse_lang_text(raw: bytes) -> dict[str, str]:
    """解析 1.13 以前的 ``key=value`` 纯文本语言文件。"""
    text = _decode(raw)
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if k:
            out[k] = v.strip()
    return out


def _flatten(obj, prefix: str, out: dict[str, str]) -> None:
    """把嵌套 dict 扁平化为 ``a.b.c -> str``；跳过 list 与非字符串值。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, str):
                out[key] = v
            elif isinstance(v, dict):
                _flatten(v, key, out)
    elif isinstance(obj, str) and prefix:
        out[prefix] = obj


def _strip_json_comments(text: str) -> str:
    """去除 ``//`` 行注释与 ``/* */`` 块注释（不误伤字符串内内容）。"""
    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            if j == -1:
                break
            i = j
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            if j == -1:
                break
            i = j + 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


# ------------------------------------------------------------------ 通用工具


def _zip_read_bytes(zf: zipfile.ZipFile, name: str | None) -> bytes | None:
    if not name:
        return None
    try:
        return zf.read(name)
    except Exception:
        return None


def _resolve(names_set: set[str], lower_map: dict[str, str], candidate: str) -> str:
    """先精确匹配 zip 条目名，再退化为大小写不敏感匹配。"""
    if candidate in names_set:
        return candidate
    return lower_map.get(candidate.lower(), "")


def _load_json_bytes(raw: bytes | None):
    if raw is None:
        return None
    try:
        return json.loads(_strip_json_comments(_decode(raw)))
    except Exception:
        return None


def _load_toml_bytes(raw: bytes | None):
    if raw is None or tomllib is None:
        return None
    try:
        return tomllib.loads(_decode(raw))
    except Exception:
        return None


def _decode(raw: bytes) -> str:
    """UTF-8(去 BOM) 优先，失败退 latin-1。"""
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _add_id(ids: list, value) -> None:
    if isinstance(value, str):
        v = value.strip()
        if v and v not in ids:
            ids.append(v)


def _sanitize_ns(text: str) -> str:
    """把任意文本转为合法命名空间。"""
    s = re.sub(r"[^a-z0-9_.\-]", "_", text.strip().lower())
    return s.strip("_") or ""


def _clean_filename(stem: str) -> str:
    """去掉文件名末尾的版本号后缀（可连去多段）。"""
    s = stem
    for _ in range(3):
        s2 = _VERSION_SUFFIX_RE.sub("", s)
        if s2 == s or not s2:
            break
        s = s2
    return s.strip(" _-+") or stem


def _modid_from_filename(jar: Path) -> str:
    """从 jar 文件名推导合法 modid。"""
    clean = _clean_filename(jar.stem).lower()
    s = re.sub(r"[^a-z0-9_.\-]", "_", clean)
    return s.strip("_-.") or "mod"


def _fallback_names(info: dict, jar: Path) -> None:
    """异常/无元数据时的名称回落。"""
    stem = jar.stem
    en = _clean_filename(stem) or stem
    modid = _modid_from_filename(jar)
    info["modid"] = modid
    info["namespaces"] = [modid] if modid else []
    info["en_name"] = en
    info["cn_name"] = _KNOWN_CN.get(modid, "") or en
