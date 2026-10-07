# -*- coding: utf-8 -*-
"""真实窗口下的交互冒烟测试（不依赖离屏截图，纯断言）。

覆盖：按钮启用态、汉化包目录创建、资源包启用/禁用与 options.txt、
模组扫描、离线翻译占位符保护、强化翻译（通顺性检查 + 有界重译）、
配置持久化、冷知识与赞助者文本。

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
        # 模拟「版本隔离」实例：每个版本目录自带 options.txt 与 resourcepacks
        (TMP / ".versions" / v / "options.txt").write_text(
            f'version:{v}\nresourcePacks:["vanilla"]\nfov:0.0\n', encoding="utf-8")
        (TMP / ".versions" / v / "resourcepacks").mkdir(parents=True, exist_ok=True)
    (TMP / "mods").mkdir(parents=True, exist_ok=True)
    (TMP / "resourcepacks").mkdir(parents=True, exist_ok=True)
    (TMP / "options.txt").write_text(
        'version:1.20.1\nresourcePacks:["vanilla","fabric"]\nfov:0.0\n', encoding="utf-8")
    # 造两个真实的模组 jar（一个 fabric、一个 forge 风格）
    make_jar(TMP / ".versions" / "1.20.1" / "mods" / "demo-1.0.0.jar", "demo", "Demo Mod")
    make_jar(TMP / ".versions" / "1.16.5" / "mods" / "legacy-2.0.jar", "legacy", "Legacy Mod")
    (TMP / ".versions" / "1.20.1" / "mods" / "broken.jar").write_bytes(b"not a zip at all")
    # 版本实例 jar：里面 version.json 的 pack_version 是资源包格式号最权威的来源
    make_version_jar(TMP / ".versions" / "1.16.5", "1.16.5", 6)
    return TMP


def make_version_jar(inst: Path, name: str, pack_format: int) -> Path:
    """造一个「版本实例 jar」，只含 version.json（模拟原版客户端 jar）。"""
    inst.mkdir(parents=True, exist_ok=True)
    path = inst / f"{name}.jar"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("version.json", json.dumps({
            "id": name, "world_version": 0,
            "pack_version": {"resource": pack_format, "data": pack_format},
        }))
    return path


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


def make_extra_jar(path: Path, modid: str, name: str) -> Path:
    """造一个含「结构 + 成就」的 jar，用于验证附加键采集。

    - ``glacial_hut``   ：被结构集引用     -> 应补 ``structure.<modid>.glacial_hut``
    - ``zpointer/taiga``：未被结构集引用   -> **不应**补（否则指南针出现找不到的条目）
    - ``named_tower``   ：模组自带名字键   -> 不应覆盖
    - 成就 ``root``     ：title 是英文句子 -> 应补同键（YUNG 系模组的写法）
    - 成就 ``find``     ：用正规键且 en_us 已有 -> 不应生成
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("fabric.mod.json", json.dumps({
            "schemaVersion": 1, "id": modid, "name": name, "version": "1.0.0",
            "description": "extra test mod",
        }))
        z.writestr(f"assets/{modid}/lang/en_us.json", json.dumps({
            f"mod.{modid}.name": name,
            f"structure.{modid}.named_tower": "Named Tower",
            f"advancements.{modid}.find.title": "Find It",
            f"advancements.{modid}.find.description": "Find the thing",
        }, ensure_ascii=False))
        for p, pool in (("glacial_hut", "hut"), ("zpointer/taiga", "nothing"),
                        ("named_tower", "tower")):
            z.writestr(f"data/{modid}/worldgen/structure/{p}.json", json.dumps(
                {"type": "minecraft:jigsaw", "start_pool": f"{modid}:{pool}"}))
        # 结构集：只引用 glacial_hut 与 named_tower（zpointer/taiga 故意不引用）
        z.writestr(f"data/{modid}/worldgen/structure_set/main.json", json.dumps({
            "placement": {"type": "minecraft:random_spread", "spacing": 32, "separation": 8},
            "structures": [{"structure": f"{modid}:glacial_hut", "weight": 1},
                           {"structure": f"{modid}:named_tower", "weight": 1}],
        }))
        z.writestr(f"data/{modid}/advancements/root.json", json.dumps({
            "display": {"title": {"translate": "An Ancient Tomb"},
                        "description": {"translate": "Find the tomb"},
                        "icon": {"item": "minecraft:stone"}},
        }))
        z.writestr(f"data/{modid}/advancements/find.json", json.dumps({
            "display": {"title": {"translate": f"advancements.{modid}.find.title"},
                        "description": {"translate": f"advancements.{modid}.find.description"},
                        "icon": {"item": "minecraft:stone"}},
        }))
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

    #: 在任何 save() 之前记录「强化翻译」的出厂默认值（config.json 里应无该字段）
    enhanced_default = STATE.enhanced_translate

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
                  "icon", "loader", "mc_version", "lang_files", "translatable", "error",
                  "extra_entries", "extra_structures", "extra_advancements"):
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

    # ---------- 5. 汉化包目录创建（按版本隔离） ----------
    print("\n[5] 汉化包目录")
    STATE.set_game_dir(str(game))
    STATE.set_version("1.20.1")
    root = paths.hanhuabao_root(game, "1.20.1")
    check(root.is_dir() and root.name == "汉化包", f"创建「汉化包」目录：{root}")
    check(root.parent.name == "1.20.1",
          "汉化包目录位于所选版本实例之下（versions/1.20.1/汉化包）")
    check(paths.hanhuabao_root(game).parent.name in (".versions", "versions"),
          "不传版本时回落到版本根目录下的共享「汉化包」（兼容旧数据）")

    # ---------- 6. 生成汉化包 + 启用/禁用（版本隔离） ----------
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
    check(meta["pack"].get("pack_format") == 15,
          f"pack.mcmeta 的 pack_format 按 1.20.1 写入 15（实际 {meta['pack'].get('pack_format')}）")
    check(meta["pack"].get("supported_formats")
          == {"min_inclusive": 1, "max_inclusive": 64},
          "pack.mcmeta 用 supported_formats 覆盖 1.0~1.21.8（旧字段上界=1.21.8）")
    check(meta["pack"].get("min_format") == 1 and meta["pack"].get("max_format") == 999,
          "pack.mcmeta 同时声明 min_format / max_format（跨 1.21.9 时代）")

    # pack.mcmeta 的格式号必须随目标版本走，否则游戏里会显示为「不兼容」（红色）
    inst165 = TMP / ".versions" / "1.16.5"
    check(packager.detect_pack_format(inst165, "1.16.5") == (6, 0),
          "detect_pack_format 读实例 jar 的 version.json（1.16.5 -> 6）")
    p165 = packager.create_pack(paths.hanhuabao_root(game, "1.16.5"), "1.16.5",
                                m, translated, names)
    if "error" not in p165:
        m165 = json.loads((Path(p165["dir"]) / "pack.mcmeta").read_text(encoding="utf-8"))
        check(m165["pack"].get("pack_format") == 6,
              f"1.16.5 的包写 pack_format 6（实际 {m165['pack'].get('pack_format')}）")
    p_new = packager.create_pack(paths.hanhuabao_root(game, "1.21.11"), "1.21.11",
                                 m, translated, names)
    if "error" not in p_new:
        m_new = json.loads((Path(p_new["dir"]) / "pack.mcmeta").read_text(encoding="utf-8"))
        check("pack_format" not in m_new["pack"] and "supported_formats" not in m_new["pack"],
              "1.21.9+ 的包不写 pack_format / supported_formats（写了会报错）")
        check(m_new["pack"].get("min_format") == [65, 0]
              and m_new["pack"].get("max_format") == 999,
              "1.21.9+ 的包改用 min_format / max_format")
    check(packager.detect_pack_format(None, "26.1.1") == (65, 0),
          "detect_pack_format：26.1.1 走年份版本 -> 新时代")
    check(packager.detect_pack_format(None, "1.20.1-Forge_47.4.16") == (15, 0),
          "detect_pack_format：从 '1.20.1-Forge_47.4.16' 里认出 1.20.1")
    check(packager.detect_pack_format(None, "Construction & Exploration v1.1.0") == (15, 0),
          "detect_pack_format：整合包名里的 v1.1.0 不被误认，回落兜底 15")

    listed = packager.list_packs(game, "1.20.1")
    check(any(p["id"] == pack["id"] for p in listed), "list_packs 能列出刚生成的包")

    # 版本隔离：启用目标必须是版本实例目录，而不是游戏根目录
    inst = game / ".versions" / "1.20.1"
    check(paths.instance_dir(game, "1.20.1") == inst,
          "instance_dir 识别出版本隔离实例目录")
    check(paths.options_txt(game, "1.20.1") == inst / "options.txt",
          "options_txt 指向版本实例的 options.txt（游戏真正读取的那份）")

    check(packager.enable_pack(game, pack), "enable_pack 返回 True")
    options = (inst / "options.txt").read_text(encoding="utf-8")
    check(f"file/{pack['id']}" in options,
          "版本实例 options.txt 中已写入 file/<包名>（游戏能读到）")
    rp = json.loads(options.split("resourcePacks:", 1)[1].split("\n", 1)[0])
    check(rp[-1] == f"file/{pack['id']}", "汉化包被置于 resourcePacks 列表末尾（覆盖原文）")
    check((inst / "resourcepacks" / pack["id"] / "pack.mcmeta").is_file(),
          "汉化包已复制到版本实例的 resourcepacks")
    check("fov:0.0" in options, "options.txt 其它行未被破坏")
    root_options = (game / "options.txt").read_text(encoding="utf-8")
    check(f"file/{pack['id']}" not in root_options,
          "隔离实例下不污染游戏根目录 options.txt（避免跨版本串包）")

    packager.enable_pack(game, pack)          # 重复启用不应产生重复项
    options = (inst / "options.txt").read_text(encoding="utf-8")
    rp = json.loads(options.split("resourcePacks:", 1)[1].split("\n", 1)[0])
    check(rp.count(f"file/{pack['id']}") == 1, "重复启用不会产生重复条目")

    check(packager.disable_pack(game, pack), "disable_pack 返回 True")
    options = (inst / "options.txt").read_text(encoding="utf-8")
    check(f"file/{pack['id']}" not in options, "禁用后 options.txt 已移除该条目")
    check(not (inst / "resourcepacks" / pack["id"]).exists(),
          "禁用后版本实例的 resourcepacks 目录已清理")

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

    # ---------- 10. 强化翻译 ----------
    print("\n[10] 强化翻译")
    check(enhanced_default is False, "出厂默认不勾选（STATE.enhanced_translate 为 False）")
    check(isinstance(translator.ENHANCED_MAX_RETRIES, int)
          and translator.ENHANCED_MAX_RETRIES >= 1,
          f"重试上限为合理正整数：{translator.ENHANCED_MAX_RETRIES}")

    # --- 通顺性判定 ---
    check(model.is_fluent("石头方块"), "干净的中文译文 -> 判定通顺")
    check(not model.is_fluent("红石 Comparator Signal Strength Emitter"),
          "大段连续未翻译英文 -> 判定不通顺")
    check(not model.is_fluent("坏\x00文"), "哨兵残留 -> 判定不通顺")
    check(model.fluency_score("石头  剑") < model.fluency_score("石头剑"),
          "中文之间残留空格会降低通顺性得分")
    check(model.fluency_score("石头方块") > model.fluency_score("a b c d e"),
          "通顺译文得分高于不通顺译文")

    # --- 重译：有界、绝不返回空 ---
    out1, tries1, fluent1 = model.translate_enhanced_ex("Pickaxe")
    check(out1 == "镐子" and fluent1 and tries1 == 1,
          f"通顺译文一次即通过（attempts={tries1}）")
    out2, tries2, _ = model.translate_enhanced_ex(
        "Zzqx Alpha Beta Gamma Delta Emitter", max_retries=2)
    check(tries2 <= 3, f"重译次数不超过上限 1+2=3（attempts={tries2}）")
    check(out2 != "", "始终不通顺时仍返回非空结果（取最高分候选）")
    check(model.translate_enhanced("") == "", "强化翻译空串 -> 空串")
    check(model.translate_enhanced(None) == "", "强化翻译 None -> 空串")
    tp = model.translate_enhanced("Welcome %s to %1$d places")
    check("%s" in tp and "%1$d" in tp, f"强化翻译路径仍保护占位符：{tp}")

    # --- 状态读写 + 持久化 + 重新加载 ---
    STATE.set_enhanced_translate(True)
    check(STATE.enhanced_translate is True, "set_enhanced_translate(True) 生效")
    STATE.save()
    check(json.loads(CONFIG.read_text(encoding="utf-8")).get("enhanced_translate") is True,
          "enhanced_translate=True 已写入 config.json")
    from app.state import State as _State
    check(_State().enhanced_translate is True, "新建 State 能从 config.json 读回 True")
    STATE.load()
    check(STATE.enhanced_translate is True, "STATE.load() 能读回 True")

    # --- 设置界面复选框与 STATE 双向绑定 ---
    settings = win.pages["settings"]
    check(hasattr(settings, "enhanced_check"), "设置页存在强化翻译复选框")
    win.router.go("settings")
    app.processEvents()
    check(settings.enhanced_check.isChecked() is True, "刷新后复选框反映 STATE（已勾选）")
    settings.enhanced_check.setChecked(False)          # 模拟用户取消勾选
    app.processEvents()
    check(STATE.enhanced_translate is False, "取消勾选后写回 STATE")
    check(json.loads(CONFIG.read_text(encoding="utf-8")).get("enhanced_translate") is False,
          "取消勾选已持久化")

    # --- 翻译线程中实际生效 ---
    from app.core.worker import TranslateWorker
    STATE.set_enhanced_translate(True)
    logs: list[str] = []
    failed_logs: list[str] = []
    worker = TranslateWorker(str(game), "1.20.1", [mods[0]])
    worker.log.connect(logs.append)
    worker.failed.connect(failed_logs.append)
    worker.run()                                       # 同步执行，不启线程
    check(not failed_logs, f"开启强化翻译后 worker 正常完成：{failed_logs}")
    check(any("强化翻译" in t for t in logs),
          f"worker 在强化翻译开启时输出提示日志：{[t for t in logs if '强化翻译' in t]}")

    # ---------- 11. 结构与成就附加键 ----------
    print("\n[11] 结构与成就附加键")
    from app.core.worker import TranslateWorker

    extra_dir = TMP / "extra_mods"
    extra_dir.mkdir(parents=True, exist_ok=True)
    make_extra_jar(extra_dir / "extra-1.0.jar", "extramod", "Extra Mod")
    modscan.clear_cache()
    emods = modscan.scan_mods([extra_dir])
    em = next((x for x in emods if x.get("modid") == "extramod"), None)
    check(em is not None, "能扫到含结构与成就的模组")
    if em is not None:
        table = (em.get("extra_entries") or {}).get("extramod", {})
        check(table.get("structure.extramod.glacial_hut") == "Glacial Hut",
              "被结构集引用的结构补出名字键 structure.extramod.glacial_hut")
        check("structure.extramod.zpointer.taiga" not in table,
              "未被结构集引用的结构不补名字键（指南针不会出现找不到的条目）")
        check("structure.extramod.named_tower" not in table,
              "模组已提供名字的结构键不被覆盖")
        check(table.get("An Ancient Tomb") == "An Ancient Tomb",
              "成就里误写成 translate 的英文句子补出同键")
        check(table.get("Find the tomb") == "Find the tomb",
              "成就描述同样补出")
        check("advancements.extramod.find.title" not in table,
              "指向正规键的成就不生成（原版键不该被覆盖）")
        check(em.get("extra_structures") == 1,
              f"结构计数正确（实际 {em.get('extra_structures')}）")
        check(em.get("extra_advancements") == 2,
              f"成就计数正确（实际 {em.get('extra_advancements')}）")

        entries2 = TranslateWorker._read_mod_entries(modscan, em)
        got = entries2.get("extramod", {})
        check("structure.extramod.glacial_hut" in got,
              "附加键被并入 worker 的待翻译条目")
        check(got.get("structure.extramod.named_tower") == "Named Tower",
              "worker 并入时保留模组自带的原文")

        translated2 = {ns: {k: "【译】" + v for k, v in t.items()}
                       for ns, t in entries2.items()}
        pack2 = packager.create_pack(
            TMP / ".versions" / "汉化包", "1.20.1", em, translated2,
            {"extramod": {"cn": "附加键模组", "en": "Extra Mod"}})
        check(not pack2.get("error"), f"含附加键的汉化包生成成功：{pack2.get('error', '')}")
        if not pack2.get("error"):
            pdir = Path(pack2["dir"])
            fj = pdir / "assets" / "extramod" / "lang" / "zh_cn.json"
            fl = pdir / "assets" / "extramod" / "lang" / "zh_cn.lang"
            data2 = json.loads(fj.read_text(encoding="utf-8")) if fj.is_file() else {}
            lang2: dict[str, str] = {}
            if fl.is_file():
                for line in fl.read_text(encoding="utf-8").splitlines():
                    if "=" in line:
                        k2, v2 = line.split("=", 1)
                        lang2[k2] = v2
            check(data2.get("structure.extramod.glacial_hut") == "【译】Glacial Hut",
                  "zh_cn.json 里结构名键与译文正确")
            check(lang2.get("structure.extramod.glacial_hut") == "【译】Glacial Hut",
                  "zh_cn.lang 里结构名键与译文正确")
            check(data2.get("An Ancient Tomb") == "【译】An Ancient Tomb",
                  "zh_cn.json 里成就句子键与译文正确")

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
