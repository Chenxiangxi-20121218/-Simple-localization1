# -*- coding: utf-8 -*-
"""真实窗口下的交互冒烟测试（不依赖离屏截图，纯断言）。

覆盖：按钮启用态、汉化包目录创建、资源包启用/禁用与 options.txt、
模组扫描、离线翻译占位符保护、配置持久化、冷知识与赞助者文本。

用法::

    python tools/smoke_test.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFontDatabase                          # noqa: E402
from PySide6.QtWidgets import QApplication                       # noqa: E402


def _safe_rmtree(p) -> None:
    """删除临时目录。某些受管环境会拦截批量删除，此处吞掉异常避免中断流程。"""
    try:
        shutil.rmtree(p, ignore_errors=True)
    except BaseException:
        pass

TMP = ROOT / ".tmp" / "smoke_game"
CONFIG = ROOT / "config.json"
CONFIG_BAK = ROOT / "config.json.smoke-bak"

_failures: list[str] = []
_passed = 0


def check(cond: bool, msg: str) -> None:
    global _passed
    if cond:
        _passed += 1
        print(f"  [OK]   {msg}")
    else:
        _failures.append(msg)
        print(f"  [FAIL] {msg}")


# ---------------------------------------------------------------- 造测试数据


def make_game_dir() -> Path:
    if TMP.exists():
        _safe_rmtree(TMP)
    for v in ("1.20.1", "1.16.5"):
        (TMP / ".versions" / v / "mods").mkdir(parents=True, exist_ok=True)
    (TMP / "mods").mkdir(parents=True, exist_ok=True)
    (TMP / "resourcepacks").mkdir(parents=True, exist_ok=True)
    (TMP / "options.txt").write_text(
        'version:1.20.1\nresourcePacks:["vanilla","fabric"]\nfov:0.0\n', encoding="utf-8")
    # 造两个真实的模组 jar（一个 fabric、一个 forge 风格）
    make_jar(TMP / ".versions" / "1.20.1" / "mods" / "demo-1.0.0.jar", "demo", "Demo Mod")
    make_jar(TMP / ".versions" / "1.16.5" / "mods" / "legacy-2.0.jar", "legacy", "Legacy Mod")
    (TMP / ".versions" / "1.20.1" / "mods" / "broken.jar").write_bytes(b"not a zip at all")
    return TMP


def make_jar(path: Path, modid: str, name: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("fabric.mod.json", json.dumps({
            "schemaVersion": 1, "id": modid, "name": name, "version": "1.0.0",
            "description": "test mod",
        }))
        z.writestr(f"assets/{modid}/lang/en_us.json", json.dumps({
            f"block.{modid}.stone": "Stone Block",
            f"item.{modid}.pickaxe": "Pickaxe",
            f"gui.{modid}.title": "Welcome %s",
            f"mod.{modid}.name": name,
        }, ensure_ascii=False))
    return path


def make_model_zip(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("model.json", json.dumps(
            {"name": "冒烟测试模型", "version": "1.0", "author": "t"}, ensure_ascii=False))
        z.writestr("dict.json", json.dumps(
            {"Stone Block": "石头方块", "Pickaxe": "镐子"}, ensure_ascii=False))
        z.writestr("terms.tsv", "Welcome\t欢迎\n")
    return path


# ---------------------------------------------------------------- 测试主体


def main() -> int:
    if CONFIG.is_file():
        shutil.copy2(CONFIG, CONFIG_BAK)

    app = QApplication(sys.argv)          # noqa: F841
    for f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        if os.path.isfile(f):
            QFontDatabase.addApplicationFont(f)

    from app import paths
    from app.core import modscan, packager, translator
    from app.state import STATE
    from app.theme import qss
    from main import MainWindow

    app.setStyleSheet(qss())
    game = make_game_dir()

    # ---------- 1. 主窗口与页面 ----------
    print("\n[1] 主窗口 / 页面")
    win = MainWindow()
    win.resize(1180, 760)
    win.show()
    app.processEvents()
    check(set(win.pages) == {"translate", "modselect", "packs", "settings"},
          "四个页面全部创建：translate / modselect / packs / settings")
    for key in ("translate", "modselect", "packs", "settings"):
        win.router.go(key)
        app.processEvents()
    check(True, "路由遍历四个页面无异常")
    check(win.router.sidebar_key() == "settings", "二级页面之外的侧边栏高亮正确")

    # ---------- 2. 「开始翻译」启用规则 ----------
    print("\n[2] 开始翻译按钮启用规则")
    from app.widgets import BigButton
    big = win.pages["translate"].findChild(BigButton)
    check(big is not None, "翻译页存在 BigButton")
    STATE.clear_model()
    STATE.selected_mods.clear()
    STATE.set_mods([])
    app.processEvents()
    check(not big.isEnabled(), "无模型且无模组 -> 按钮为灰（不可点击）")

    STATE.set_model(str(make_model_zip(ROOT / ".tmp" / "smoke_model.zip")),
                    "冒烟测试模型", {"entries": 3})
    app.processEvents()
    check(not big.isEnabled(), "仅有模型、未选模组 -> 按钮仍为灰")

    raw = modscan.scan_mods([game / ".versions" / "1.20.1" / "mods"])
    check(len(raw) >= 2, f"扫描到 {len(raw)} 个 jar（含 1 个损坏 jar）")
    check(any(m["error"] for m in raw), "损坏的 jar 被写入 error 字段而不是抛异常")
    mods = [m for m in raw if m["translatable"]]
    check(len(mods) == 1, f"其中可翻译模组 {len(mods)} 个（含 en_us 语言文件）")
    STATE.set_mods(mods)
    STATE.toggle_mod(mods[0]["id"], True)
    app.processEvents()
    check(big.isEnabled(), "已选模型 + 至少一个模组 -> 按钮变白（可点击）")

    # ---------- 3. 模组扫描字段 ----------
    print("\n[3] 模组扫描")
    m = mods[0]
    for field in ("id", "modid", "namespaces", "cn_name", "en_name", "path",
                  "icon", "loader", "mc_version", "lang_files", "translatable", "error"):
        check(field in m, f"模组条目包含字段 {field}")
    check(m["loader"] == "fabric", f"loader 解析为 fabric（实际 {m['loader']}）")
    check(m["en_name"] != "", f"英文名非空：{m['en_name']}")
    entries = modscan.read_lang_entries(m["path"], m["lang_files"][0]["entry"])
    check(entries.get(f"item.{m['modid']}.pickaxe") == "Pickaxe",
          "read_lang_entries 正确读出英文原文")

    # ---------- 4. 离线翻译 + 占位符保护 ----------
    print("\n[4] 离线翻译引擎")
    name, info = translator.load_model(str(ROOT / ".tmp" / "smoke_model.zip"))
    check(name == "冒烟测试模型", f"模型名解析正确：{name}")
    model = translator.TranslateModel(str(ROOT / ".tmp" / "smoke_model.zip"))
    check(model.translate("Pickaxe") == "镐子", "模型词表命中：Pickaxe -> 镐子")
    check(model.translate("Stone") == "石头", "内置词表兜底：Stone -> 石头")
    check(model.translate("") == "", "空串返回空串")
    check(model.translate(None) == "", "None 返回空串")
    t = model.translate("Welcome %s to %1$d places")
    check("%s" in t and "%1$d" in t, f"占位符 %s / %1$d 被保留：{t}")
    t2 = model.translate("§aHello")
    check("§a" in t2, f"§ 颜色码被保留：{t2}")
    try:
        translator.load_model(str(ROOT / ".tmp" / "not_exist.zip"))
        check(False, "不存在的模型应抛 ModelError")
    except translator.ModelError:
        check(True, "不存在的模型抛出 ModelError")
    check(translator.estimate_seconds(1000) > 0, "estimate_seconds 返回正数")

    # ---------- 5. 汉化包目录创建（需求 1） ----------
    print("\n[5] 汉化包目录")
    STATE.set_game_dir(str(game))
    root = paths.hanhuabao_root(game)
    check(root.is_dir() and root.name == "汉化包", f".versions 下创建「汉化包」目录：{root}")
    check(root.parent.name in (".versions", "versions"), "汉化包目录位于 .versions 之下")

    # ---------- 6. 生成汉化包 + 启用/禁用 ----------
    print("\n[6] 汉化包生成 / 启用 / 禁用")
    translated = {m["modid"]: {k: model.translate(v) for k, v in entries.items()}}
    names = {m["modid"]: {"cn": m["cn_name"], "en": m["en_name"]}}
    pack = packager.create_pack(root, "1.20.1", m, translated, names)
    check("error" not in pack, f"create_pack 成功：{pack.get('name')}")
    pdir = Path(pack["dir"])
    check((pdir / "pack.mcmeta").is_file(), "生成 pack.mcmeta")
    check((pdir / "assets" / m["modid"] / "lang" / "zh_cn.json").is_file(), "生成 zh_cn.json")
    check((pdir / "assets" / m["modid"] / "lang" / "zh_cn.lang").is_file(),
          "生成 zh_cn.lang（1.13 以前版本兼容）")
    meta = json.loads((pdir / "pack.mcmeta").read_text(encoding="utf-8"))
    check("supported_formats" in meta["pack"], "pack.mcmeta 声明 supported_formats（全版本通用）")

    listed = packager.list_packs(root)
    check(any(p["id"] == pack["id"] for p in listed), "list_packs 能列出刚生成的包")

    check(packager.enable_pack(game, pack), "enable_pack 返回 True")
    options = (game / "options.txt").read_text(encoding="utf-8")
    check(f"file/{pack['id']}" in options, "options.txt 中已写入 file/<包名>")
    rp = json.loads(options.split("resourcePacks:", 1)[1].split("\n", 1)[0])
    check(rp[-1] == f"file/{pack['id']}", "汉化包被置于 resourcePacks 列表末尾（覆盖原文）")
    check((game / "resourcepacks" / pack["id"] / "pack.mcmeta").is_file(),
          "汉化包已复制到 resourcepacks")
    check("fov:0.0" in options, "options.txt 其它行未被破坏")

    packager.enable_pack(game, pack)          # 重复启用不应产生重复项
    options = (game / "options.txt").read_text(encoding="utf-8")
    rp = json.loads(options.split("resourcePacks:", 1)[1].split("\n", 1)[0])
    check(rp.count(f"file/{pack['id']}") == 1, "重复启用不会产生重复条目")

    check(packager.disable_pack(game, pack), "disable_pack 返回 True")
    options = (game / "options.txt").read_text(encoding="utf-8")
    check(f"file/{pack['id']}" not in options, "禁用后 options.txt 已移除该条目")
    check(not (game / "resourcepacks" / pack["id"]).exists(), "禁用后 resourcepacks 目录已清理")

    # ---------- 7. 目录名非法字符过滤 ----------
    print("\n[7] 目录名安全")
    bad_mod = dict(m)
    bad_mod["cn_name"] = 'A/B:C*D?E"F<G>H|I'
    p2 = packager.create_pack(root, "1.20.1", bad_mod, translated,
                              {m["modid"]: {"cn": bad_mod["cn_name"], "en": m["en_name"]}})
    check("error" not in p2, "含非法字符的名字也能生成汉化包")
    if "error" not in p2:
        check(not any(ch in Path(p2["dir"]).name for ch in '\\/:*?"<>|'),
              f"非法字符已过滤：{Path(p2['dir']).name}")

    # ---------- 8. 文本资源 ----------
    print("\n[8] 文本资源")
    check(len(STATE.lengzhishi_lines()) > 0, "lengzhishi.txt 可读")
    check(STATE.random_lengzhishi().strip() != "", "随机冷知识非空")
    check(isinstance(STATE.sponsor_url(), str), "sponsor_url 返回字符串（文件缺失时为空串）")
    sp = STATE.sponsors_text()
    check("#" not in sp and sp.strip() != "", f"赞助者文本已过滤注释行：{sp[:40]}")

    # ---------- 9. 配置持久化 ----------
    print("\n[9] 配置持久化")
    STATE.set_welcome("自定义欢迎语")
    STATE.save()
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    check(data["welcome_text"] == "自定义欢迎语", "welcome_text 已写入 config.json")
    check(data["model_name"] == "冒烟测试模型", "model_name 已写入 config.json")

    # ---------- 收尾（先出结论，再做清理，避免清理失败吞掉结果） ----------
    print("\n" + "=" * 56)
    if _failures:
        print(f"失败 {len(_failures)} 项 / 通过 {_passed} 项")
        for f in _failures:
            print(f"  - {f}")
        code = 1
    else:
        print(f"全部通过（{_passed} 项断言）")
        code = 0

    try:
        win.close()
        _safe_rmtree(TMP)
        if CONFIG_BAK.is_file():
            shutil.copy2(CONFIG_BAK, CONFIG)
            CONFIG_BAK.unlink()
        else:
            CONFIG.unlink(missing_ok=True)
    except BaseException as e:  # 清理失败不影响测试结论
        print(f"（清理临时文件时被拦截，可忽略：{type(e).__name__}）")
    return code


if __name__ == "__main__":
    sys.exit(main())
