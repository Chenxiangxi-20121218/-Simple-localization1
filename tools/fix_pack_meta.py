# -*- coding: utf-8 -*-
"""修复已生成汉化包的 ``pack.mcmeta``（把资源包格式号改成目标 MC 版本的正确值）。

历史 bug：早期版本把 ``pack_format`` 写死为 1（那是 MC 1.6.1~1.8.9 的格式号），
在 1.20.1 里会被游戏判为「不兼容」并显示成**红色**。本脚本就地重写 pack.mcmeta，
格式号按包所属版本实例的 jar（``version.json`` -> ``pack_version``）自动探测。

用法::

    python tools/fix_pack_meta.py <游戏目录>            # 就地修复
    python tools/fix_pack_meta.py <游戏目录> --dry-run  # 只看会改什么

扫描四处：``versions/<版本>/汉化包``、``versions/<版本>/resourcepacks``、
``versions/汉化包``（历史共享）、``resourcepacks``（未开版本隔离时的旧布局）。
只改 ``pack.mcmeta`` 一个文件，不动语言文件、README 与 options.txt。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import paths                       # noqa: E402
from app.core import packager               # noqa: E402


def find_pack_dirs(game: Path) -> list[Path]:
    """找出所有**本工具生成**的汉化包目录（去重、稳定排序）。

    ⚠️ 只认目录名以「汉化包」结尾、且带 README.txt 的包 —— 整合包/玩家自带的
    第三方资源包（如 ``Homestead GUI``）绝不能被本脚本改写。
    """
    cands: list[Path] = []
    for base in paths.version_bases(game):
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir() or child.name == "汉化包":
                continue
            cands.append(child / "汉化包")
            cands.append(child / "resourcepacks")
        cands.append(base / "汉化包")
    cands.append(game / "resourcepacks")

    out: list[Path] = []
    seen: set[str] = set()
    for parent in cands:
        if not parent.is_dir():
            continue
        for child in sorted(parent.iterdir()):
            try:
                if not child.is_dir():
                    continue
                if not child.name.endswith("汉化包"):
                    continue
                if not (child / "pack.mcmeta").is_file():
                    continue
                if not (child / "README.txt").is_file():
                    continue
                key = str(child.resolve()).lower()
            except OSError:
                continue
            if key in seen:
                continue
            seen.add(key)
            out.append(child)
    return out


def resolve(game: Path, pack_dir: Path) -> tuple[Path | None, str]:
    """定位包所属的版本实例与版本名（用于探测格式号）。"""
    inst = packager.instance_of_pack(pack_dir)
    hint = ""
    readme = pack_dir / "README.txt"
    if readme.is_file():
        try:
            hint = str(packager._parse_readme(
                readme.read_text(encoding="utf-8", errors="replace")).get("version") or "")
        except OSError:
            hint = ""
    if inst is None and hint:
        inst = paths.version_instance_path(game, hint)
    if inst is not None and not hint:
        hint = inst.name
    return inst, hint


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("-")]
    dry = "--dry-run" in argv
    if not args:
        print(__doc__)
        print("错误：请给出游戏目录（.minecraft）路径。")
        return 2

    game = Path(args[0])
    if not game.is_dir():
        print(f"错误：目录不存在：{game}")
        return 2

    packs = find_pack_dirs(game)
    if not packs:
        print(f"没在 {game} 下找到任何汉化包（含 pack.mcmeta 的目录）。")
        return 0

    print(f"游戏目录：{game}")
    print(f"找到 {len(packs)} 个汉化包{'（--dry-run，不写入）' if dry else ''}\n")

    fixed = unchanged = failed = 0
    for pack_dir in packs:
        inst, hint = resolve(game, pack_dir)
        fmt = packager.detect_pack_format(inst, hint)
        meta_path = pack_dir / "pack.mcmeta"
        try:
            old = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            old = {}
        desc = ""
        if isinstance(old, dict):
            desc = str((old.get("pack") or {}).get("description") or "")
        if not desc:
            desc = f"§b{pack_dir.name} §7| by MC 模组汉化工具"

        new = packager.build_pack_mcmeta(desc, fmt)
        new_text = json.dumps(new, ensure_ascii=False, indent=2)

        try:
            cur_text = meta_path.read_text(encoding="utf-8")
        except OSError:
            cur_text = ""

        rel = pack_dir.relative_to(game)
        tag = f"{hint or '?'} -> {fmt[0]}.{fmt[1]}"
        if cur_text.strip() == new_text.strip():
            unchanged += 1
            print(f"  [跳过] {rel}  （已是 {tag}）")
            continue
        if dry:
            fixed += 1
            print(f"  [待改] {rel}  {tag}")
            print(f"         {new['pack']}")
            continue
        try:
            meta_path.write_text(new_text, encoding="utf-8")
            fixed += 1
            print(f"  [已改] {rel}  {tag}")
        except OSError as exc:
            failed += 1
            print(f"  [失败] {rel}  {exc}")

    print(f"\n完成：修改 {fixed} 个，无需修改 {unchanged} 个，失败 {failed} 个。")
    if fixed and not dry:
        print("回到游戏：选项 → 资源包，红色应该变成正常颜色了。")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
