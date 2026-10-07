# -*- coding: utf-8 -*-
"""汉化包生成 / 启用。

汉化包的载体是 **Minecraft 资源包（resource pack）**：
模组自带的语言文件位于 ``assets/<namespace>/lang/``，而资源包的加载层级高于
模组内置资源，因此只要在资源包里放同路径的 ``zh_cn`` 语言文件即可覆盖原文。

为兼容 MC 全版本，同时生成两种语言文件：

- ``zh_cn.json``  —— 1.13 及以后（JSON 键值对）
- ``zh_cn.lang``  —— 1.13 以前（每行 ``key=value`` 纯文本）

``pack.mcmeta`` 使用低 ``pack_format``（1）并声明 ``supported_formats`` 为 1~99：
老版本会忽略不认识的字段，新版本也能正常读取，从而 1.0 ~ 最新快照通用。

启用机制：把 pack 目录复制到**版本实例**的 ``resourcepacks/<pack_id>/``，
并在该实例的 ``options.txt`` 的 ``resourcePacks:[...]`` 列表**末尾追加**
``"file/<pack_id>"``，使其位于加载顺序末尾、优先级最高，从而覆盖模组原文。

⚠️ **版本隔离**：PCL2 / HMCL 等启动器开启版本隔离后，游戏的工作目录是
``<游戏目录>/versions/<版本>/`` —— ``options.txt``、``resourcepacks``、
``mods``、``saves`` 全在里面，游戏**只读那一份**。因此启用必须写到实例目录；
写到游戏根目录是无效的（游戏根本不会加载）。
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from .. import paths

# ---------------------------------------------------------------- 常量

#: Windows 非法文件名字符 + ASCII 控制字符
_ILLEGAL_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')

#: pack 目录名最大长度
_MAX_NAME_LEN = 60

#: 资源包描述（§ 为 MC 颜色码，§b 青色 / §7 灰色）
_DESC_SUFFIX = "§7| by MC 模组汉化工具"

#: README.txt 里的字段格式（list_packs 会按此正则读回）
_RE_MODID = re.compile(r"^模组ID:\s*(.*)$")
_RE_MCVER = re.compile(r"^MC版本:\s*(.*)$")
_RE_COUNT = re.compile(r"^译文条数:\s*(\d+)$")
_RE_NAMESPACES = re.compile(r"^命名空间:\s*(.*)$")
_RE_MODNAME = re.compile(r"^模组名称:\s*(.*)$")


# ---------------------------------------------------------------- 工具函数


def _safe_name(text: str) -> str:
    """过滤 Windows 非法字符与控制字符，去掉首尾空格/点，并限制长度。"""
    s = _ILLEGAL_RE.sub("_", str(text or ""))
    # 去掉首尾空格和点（Windows 目录名不能以空格或点结尾）
    s = s.strip(" .")
    if len(s) > _MAX_NAME_LEN:
        s = s[:_MAX_NAME_LEN]
    s = s.strip(" .")
    return s or "汉化包"


def _rmtree_quiet(p: Path) -> None:
    """安静地删除目录（不存在或失败都不抛异常）。"""
    try:
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    except OSError:
        pass


def _write_text(path: Path, text: str) -> None:
    """以 UTF-8 写入文本（自动创建父目录）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _escape_lang_value(value: str) -> str:
    """把值里的换行转义为 ``\\n``（.lang 为单行 key=value 格式）。"""
    return str(value).replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


def _pick_cn_name(mod: dict, names: dict) -> str:
    """取模组中文名：names[modid]["cn"] -> mod["cn_name"] -> mod["en_name"] -> modid。"""
    modid = str((mod or {}).get("modid") or "")
    info = names.get(modid) if isinstance(names, dict) else None
    if isinstance(info, dict):
        cn = str(info.get("cn") or "").strip()
        if cn:
            return cn
    cn = str((mod or {}).get("cn_name") or "").strip()
    if cn:
        return cn
    en = str((mod or {}).get("en_name") or "").strip()
    if en:
        return en
    return modid or "未知模组"


def _nonempty_ns(translated: dict) -> dict[str, dict[str, str]]:
    """筛出译文非空的命名空间。"""
    out: dict[str, dict[str, str]] = {}
    if not isinstance(translated, dict):
        return out
    for ns, table in translated.items():
        if isinstance(table, dict) and table:
            out[str(ns)] = table
    return out


# ---------------------------------------------------------------- 生成汉化包


def create_pack(root: Path, version: str, mod: dict,
                translated: dict[str, dict[str, str]],
                names: dict[str, dict[str, str]]) -> dict:
    """生成一个汉化包目录。

    root       : 汉化包目录（= ``paths.hanhuabao_root(game_dir, version)``；
                 版本隔离下即 ``<游戏目录>/versions/<版本>/汉化包``）
    version    : MC 版本名
    mod        : modscan.scan_mods() 返回的元素
    translated : {namespace: {key: 中文}}
    names      : {namespace: {"cn": 中文名, "en": 英文名}}
    返回 pack 信息 dict；任何异常都容错，失败时返回 ``{"error": "..."}``。
    """
    try:
        mod = mod or {}
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)

        cn_name = _pick_cn_name(mod, names)
        modid = str(mod.get("modid") or "")
        en_name = str(mod.get("en_name") or modid or cn_name)

        # 目录名：<中文名>汉化包，过滤非法字符
        dir_name = _safe_name(f"{cn_name}汉化包")
        pack_dir = root / dir_name

        # 已存在则直接覆盖重建
        _rmtree_quiet(pack_dir)
        pack_dir.mkdir(parents=True, exist_ok=True)

        ns_map = _nonempty_ns(translated)
        namespaces = sorted(ns_map.keys())
        count = sum(len(t) for t in ns_map.values())

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%Y-%m-%d %H:%M:%S")

        # 1) pack.mcmeta —— 低 pack_format + supported_formats，保证全版本通用
        mcmeta = {
            "pack": {
                "pack_format": 1,
                "description": f"§b{cn_name} 汉化包 {_DESC_SUFFIX}",
                "supported_formats": {"min_inclusive": 1, "max_inclusive": 99},
            }
        }
        _write_text(pack_dir / "pack.mcmeta",
                    json.dumps(mcmeta, ensure_ascii=False, indent=2))

        # 2) 语言文件（每个命名空间两种格式）
        for ns, table in ns_map.items():
            lang_dir = pack_dir / "assets" / ns / "lang"
            # 1.13+ JSON
            _write_text(lang_dir / "zh_cn.json",
                        json.dumps(table, ensure_ascii=False, indent=2))
            # 1.13 以前纯文本：key 排序，逐行 key=value
            lines = [f"{k}={_escape_lang_value(v)}"
                     for k, v in sorted(table.items(), key=lambda kv: str(kv[0]))]
            _write_text(lang_dir / "zh_cn.lang", "\n".join(lines) + "\n")

        # 3) README.txt —— 中文说明，字段供 list_packs 读回
        ns_text = ", ".join(namespaces) if namespaces else "(无)"
        readme = (
            "========================================\n"
            f"  {cn_name} 汉化包\n"
            "========================================\n\n"
            f"模组名称: {cn_name} ({en_name})\n"
            f"模组ID: {modid}\n"
            f"MC版本: {version or ''}\n"
            f"命名空间: {ns_text}\n"
            f"译文条数: {count}\n"
            f"生成时间: {time_str}\n\n"
            "说明\n"
            "----------------------------------------\n"
            "本汉化包由「MC 模组汉化工具」自动生成，\n"
            "同时提供 zh_cn.json 与 zh_cn.lang 两种语言文件，\n"
            "兼容 Minecraft 1.0 ~ 最新快照。\n\n"
            "如何在游戏内启用\n"
            "----------------------------------------\n"
            "1. 打开游戏，进入「选项 → 资源包」。\n"
            f"2. 在左侧列表中找到「{cn_name} 汉化包」，点击箭头把它移到右侧「已选资源包」。\n"
            "3. 确保它排在其它资源包之后（加载顺序靠后优先级更高），点击「完成」即可。\n"
        )
        _write_text(pack_dir / "README.txt", readme)

        return {
            "id": dir_name,
            "name": f"{cn_name} 汉化包",
            "detail": f"{len(namespaces)} 个命名空间 · {count} 条译文 · {date_str}",
            "dir": str(pack_dir),
            "version": str(version or ""),
            "modid": modid,
            "enabled": False,
            "count": count,
        }
    except Exception as exc:  # noqa: BLE001 —— 契约要求绝不抛异常
        return {"error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------- 扫描汉化包


def _parse_readme(text: str) -> dict:
    """从 README.txt 里读回字段（读不到就留空）。"""
    info = {"modid": "", "version": "", "count": 0, "namespaces": [], "cn": ""}
    for line in text.splitlines():
        line = line.strip()
        m = _RE_MODID.match(line)
        if m:
            info["modid"] = m.group(1).strip()
            continue
        m = _RE_MCVER.match(line)
        if m:
            info["version"] = m.group(1).strip()
            continue
        m = _RE_COUNT.match(line)
        if m:
            try:
                info["count"] = int(m.group(1))
            except ValueError:
                info["count"] = 0
            continue
        m = _RE_NAMESPACES.match(line)
        if m:
            raw = m.group(1).strip()
            info["namespaces"] = [p.strip() for p in raw.split(",") if p.strip()] \
                if raw and raw != "(无)" else []
            continue
        m = _RE_MODNAME.match(line)
        if m:
            raw = m.group(1).strip()
            # 形如 "中文名 (English Name)" -> 取括号前的中文名
            cn = raw.split("(")[0].strip() if "(" in raw else raw
            info["cn"] = cn
            continue
    return info


def _read_resource_packs(game_dir: Path, version: str | None = None) -> list[str]:
    """读取 options.txt 里的 resourcePacks 列表（失败返回空表）。

    ⚠️ 版本隔离时必须读**版本实例目录**下的 options.txt：游戏只读那一份，
    游戏根目录那份是无效的。
    """
    try:
        path = paths.options_txt(game_dir, version)
        if not path.is_file():
            return []
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            m = re.match(r"^resourcePacks:(.*)$", line.strip())
            if m:
                return _parse_list(m.group(1))
    except OSError:
        pass
    return []


def list_packs(game_dir: Path, version: str | None = None) -> list[dict]:
    """扫描汉化包目录，凡含 pack.mcmeta 的子目录都算一个汉化包。

    扫描两处：

    - ``versions/<版本>/汉化包``（新布局，与版本实例一一对应）
    - ``versions/汉化包``（历史共享目录，兼容此前生成的数据）

    每个包的「是否已启用」按它自己的 ``MC版本`` 去对应实例的 options.txt 里查 ——
    版本隔离下每个实例有独立的 options.txt，不能只看游戏根目录那一份。
    """
    packs: list[dict] = []
    try:
        gd = Path(game_dir)
        roots: list[Path] = []
        if version:
            roots.append(paths.hanhuabao_root_path(gd, version))
        legacy = paths.hanhuabao_root_path(gd, None)
        if legacy not in roots:
            roots.append(legacy)

        enabled_cache: dict[str, list[str]] = {}

        def _enabled_for(ver: str) -> list[str]:
            if ver not in enabled_cache:
                enabled_cache[ver] = _read_resource_packs(gd, ver or None)
            return enabled_cache[ver]

        for root in roots:
            if not root.is_dir():
                continue
            for child in root.iterdir():
                try:
                    if not child.is_dir():
                        continue
                    if not (child / "pack.mcmeta").is_file():
                        continue

                    info = {"modid": "", "version": "", "count": 0,
                            "namespaces": [], "cn": ""}
                    readme = child / "README.txt"
                    if readme.is_file():
                        try:
                            info = _parse_readme(readme.read_text(
                                encoding="utf-8", errors="replace"))
                        except OSError:
                            pass

                    pack_id = child.name
                    ns_count = len(info["namespaces"])
                    count = int(info["count"] or 0)
                    try:
                        date_str = datetime.fromtimestamp(
                            (child / "pack.mcmeta").stat().st_mtime).strftime("%Y-%m-%d")
                    except OSError:
                        date_str = ""

                    # 启用状态按该包自己的 MC 版本查对应实例的 options.txt
                    ver = str(info["version"] or version or "")
                    enabled_list = _enabled_for(ver)
                    enabled = ((f"file/{pack_id}" in enabled_list)
                               or (pack_id in enabled_list))

                    display = f"{info['cn']} 汉化包" if info["cn"] else pack_id

                    packs.append({
                        "id": pack_id,
                        "name": display,
                        "detail": f"{ns_count} 个命名空间 · {count} 条译文 · {date_str}",
                        "dir": str(child),
                        "version": info["version"],
                        "modid": info["modid"],
                        "enabled": bool(enabled),
                        "count": count,
                    })
                except Exception:  # noqa: BLE001 —— 单个目录失败不影响整体
                    continue
    except Exception:  # noqa: BLE001
        return packs

    packs.sort(key=lambda p: p["id"])
    return packs


# ---------------------------------------------------------------- options.txt


def _parse_list(text: str) -> list[str]:
    """解析 ``["a","b"]`` 形式的内容；解析失败则退回手动拆分。"""
    text = (text or "").strip()
    if not text:
        return []
    try:
        val = json.loads(text)
        if isinstance(val, list):
            return [str(x) for x in val]
    except (ValueError, TypeError):
        pass
    # 手动容错拆分
    s = text
    if s.startswith("["):
        s = s[1:]
    if s.endswith("]"):
        s = s[:-1]
    out: list[str] = []
    for part in s.split(","):
        p = part.strip().strip('"').strip("'").strip()
        if p:
            out.append(p)
    return out


def _dump_list(entries: list[str]) -> str:
    """按 ``["a","b"]`` 紧凑格式序列化（无空格，符合 options.txt 习惯）。"""
    return json.dumps(entries, ensure_ascii=False, separators=(",", ":"))


def _edit_resource_packs(path: Path, pack_id: str, add: bool) -> bool:
    """在指定 options.txt 的 resourcePacks 列表中增删 ``file/<pack_id>``。

    - add=True ：先移除已存在项，再追加到列表末尾（保证加载顺序靠后）。
    - add=False：仅移除该项（含裸 pack_id 形式）。
    逐行处理、保留其它行原样（含 CRLF）。返回是否成功。

    直接接收 options.txt 路径（而非游戏目录）：版本隔离下每个实例各有一份
    options.txt，调用方需要能精确指定写哪一份。
    """
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.is_file():
            with open(path, "r", encoding="utf-8", newline="") as f:
                content = f.read()
        else:
            content = ""

        lines = content.splitlines(keepends=True)
        target_file = f"file/{pack_id}"
        found = False
        out: list[str] = []

        for line in lines:
            raw = line.rstrip("\r\n")
            ending = line[len(raw):] or "\n"
            m = re.match(r"^resourcePacks:(.*)$", raw)
            if m and not found:
                found = True
                entries = [e for e in _parse_list(m.group(1))
                           if e not in (target_file, pack_id)]
                if add:
                    entries.append(target_file)
                out.append("resourcePacks:" + _dump_list(entries) + ending)
            else:
                out.append(line)

        if not found and add:
            prefix = ""
            if out and not out[-1].endswith(("\n", "\r")):
                prefix = "\n"
            default = ["vanilla", "fabric", target_file]
            out.append(prefix + "resourcePacks:" + _dump_list(default) + "\n")

        new_content = "".join(out)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(new_content)
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- 启用 / 禁用


def _pack_targets(game_dir: Path, version: str | None) -> list[Path]:
    """该汉化包应当生效的目标目录列表（去重、保持顺序）。

    1. **版本实例目录** ``<游戏目录>/versions/<版本>/`` —— 开启版本隔离时，
       游戏的工作目录就是它，options.txt 与 resourcepacks 只认这一份。
    2. **游戏根目录** —— 仅当版本目录存在但**不像隔离实例**时补上，兼容
       「没开隔离」的老式布局（此时两处都写，哪种布局都能加载）。

    判定为隔离实例时**不写**游戏根目录，避免把某个版本的汉化包串到别的版本上。
    """
    gd = Path(game_dir)
    out: list[Path] = []
    vd = paths.version_instance_path(gd, version)
    if vd is not None:
        out.append(vd)
    if paths.instance_dir(gd, version) == gd:
        out.append(gd)
    return out or [gd]


def enable_pack(game_dir: Path, pack: dict) -> bool:
    """把 pack 复制到目标实例的 resourcepacks，并在其 options.txt 末尾启用。

    目标实例由 pack 自己的 ``MC版本`` 决定（见 :func:`_pack_targets`）。
    """
    try:
        pack = pack or {}
        pack_id = str(pack.get("id") or "")
        src = Path(str(pack.get("dir") or ""))
        version = str(pack.get("version") or "") or None
        if not pack_id or not src.is_dir():
            return False

        ok = False
        for target in _pack_targets(game_dir, version):
            dest = target / "resourcepacks" / pack_id
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dest, dirs_exist_ok=True)
            if _edit_resource_packs(target / "options.txt", pack_id, add=True):
                ok = True
        return ok
    except Exception:  # noqa: BLE001
        return False


def disable_pack(game_dir: Path, pack: dict) -> bool:
    """从目标实例的 options.txt 移除该 pack，并删除 resourcepacks 里的副本。

    同时清理游戏根目录里的同名残留 —— 旧实现把包写到了根目录，这里顺手纠正。
    """
    try:
        pack = pack or {}
        pack_id = str(pack.get("id") or "")
        version = str(pack.get("version") or "") or None
        if not pack_id:
            return False

        targets = _pack_targets(game_dir, version)
        gd = Path(game_dir)
        if gd not in targets:
            targets.append(gd)          # 清理旧的根目录残留

        ok = False
        for target in targets:
            if _edit_resource_packs(target / "options.txt", pack_id, add=False):
                ok = True
            try:
                shutil.rmtree(target / "resourcepacks" / pack_id, ignore_errors=True)
            except OSError:
                pass
        return bool(ok)
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- 批量同步


def apply_enabled(game_dir: Path, version: str | None = None) -> None:
    """按 STATE.pack_enabled 批量启用/禁用，并同步 options.txt。

    每个包按其自身的 ``MC版本`` 落到对应实例目录（版本隔离下每个实例各有
    一份 options.txt），因此这里必须按版本枚举汉化包。

    为避免信号风暴，这里直接改 ``STATE.pack_enabled`` 字典，最后只 ``save()`` 一次，
    不逐条 emit ``packsChanged``。
    """
    from ..state import STATE

    try:
        for pack in list_packs(game_dir, version):
            pid = pack["id"]
            want = bool(STATE.pack_enabled.get(pid, False))
            if want:
                ok = enable_pack(game_dir, pack)
                STATE.pack_enabled[pid] = bool(ok)
            else:
                disable_pack(game_dir, pack)
                STATE.pack_enabled[pid] = False
        STATE.save()
    except Exception:  # noqa: BLE001 —— 批量同步失败也不抛异常
        try:
            STATE.save()
        except Exception:  # noqa: BLE001
            pass
