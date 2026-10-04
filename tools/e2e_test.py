# -*- coding: utf-8 -*-
"""端到端验证：真实跑一遍「扫描 -> 翻译 -> 生成汉化包」，不打桩。"""
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

from PySide6.QtCore import QEventLoop, QTimer          # noqa: E402
from PySide6.QtWidgets import QApplication             # noqa: E402


def _safe_rmtree(p) -> None:
    """删除临时目录。某些受管环境会拦截批量删除，此处吞掉异常避免中断流程。"""
    try:
        shutil.rmtree(p, ignore_errors=True)
    except BaseException:
        pass

GAME = ROOT / ".tmp" / "e2e_game"
MODEL = ROOT / ".tmp" / "e2e_model.zip"

EN = {
    "block.demo.stone": "Stone Block",
    "item.demo.pickaxe": "Pickaxe",
    "gui.demo.title": "Welcome %s to %1$d worlds",
    "mod.demo.name": "Demo Mod",
    "msg.demo.color": "§aSuccess",
}
ZH = {
    "Stone Block": "石头方块",
    "Pickaxe": "镐子",
    "Welcome %s to %1$d worlds": "欢迎 %s 来到 %1$d 个世界",
    "Demo Mod": "演示模组",
    "§aSuccess": "§a成功",
}


def setup() -> None:
    if GAME.exists():
        _safe_rmtree(GAME)
    for v in ("1.20.1", "1.16.5"):
        (GAME / ".versions" / v / "mods").mkdir(parents=True, exist_ok=True)
    (GAME / "mods").mkdir(parents=True, exist_ok=True)
    (GAME / "options.txt").write_text(
        'version:1.20.1\nresourcePacks:["vanilla","fabric"]\nfov:0.0\n', encoding="utf-8")

    for name, modid in (("demo-1.0.0.jar", "demo"), ("extra-2.0.jar", "extra")):
        with zipfile.ZipFile(GAME / ".versions" / "1.20.1" / "mods" / name, "w") as z:
            z.writestr("fabric.mod.json", json.dumps(
                {"schemaVersion": 1, "id": modid, "name": f"{modid.title()} Mod",
                 "version": "1.0.0"}))
            z.writestr(f"assets/{modid}/lang/en_us.json",
                       json.dumps(EN if modid == "demo" else
                                  {"block.extra.a": "Stone Block"}, ensure_ascii=False))

    with zipfile.ZipFile(MODEL, "w") as z:
        z.writestr("model.json", json.dumps(
            {"name": "E2E 测试模型", "version": "1.0"}, ensure_ascii=False))
        z.writestr("dict.json", json.dumps(ZH, ensure_ascii=False))


def main() -> int:
    setup()
    app = QApplication(sys.argv)

    from app import paths
    from app.core import modscan, packager, translator
    from app.core.worker import TranslateWorker
    from app.state import STATE

    STATE.set_game_dir(str(GAME))
    STATE.set_version("1.20.1")
    STATE.set_model(str(MODEL), "E2E 测试模型", {})

    mods = [m for m in modscan.scan_mods(paths.mods_dirs(GAME, "1.20.1"))
            if m["translatable"]]
    print(f"扫描到可翻译模组 {len(mods)} 个：{[m['modid'] for m in mods]}")
    assert len(mods) == 2, "应有 2 个可翻译模组"
    STATE.set_mods(mods)

    root = paths.hanhuabao_root(GAME)
    print(f"汉化包根目录：{root}")
    assert root.name == "汉化包" and root.parent.name == ".versions"

    res = {"progress": [], "log": [], "leng": [], "done": None, "failed": None}
    loop = QEventLoop()

    w = TranslateWorker(str(GAME), "1.20.1", mods)
    # 真实翻译只需几十毫秒，把 5 分钟间隔改小才能验证「进度刷新时按计时器推送」的机制
    w.LENGZHISHI_INTERVAL = 0.0
    w.progress.connect(lambda p, t: res["progress"].append(p))
    w.log.connect(lambda t: res["log"].append(t))
    w.lengzhishi.connect(lambda t: res["leng"].append(t))
    w.done.connect(lambda t: (res.__setitem__("done", t), loop.quit()))
    w.failed.connect(lambda t: (res.__setitem__("failed", t), loop.quit()))
    w.finished.connect(loop.quit)

    QTimer.singleShot(90000, loop.quit)
    w.start()
    loop.exec()

    print(f"\ndone   = {res['done']!r}")
    print(f"failed = {res['failed']!r}")
    print(f"progress = {res['progress']}")
    print(f"冷知识条数 = {len(res['leng'])}  例：{res['leng'][:1]}")
    print("日志：")
    for line in res["log"]:
        print(f"   - {line}")

    assert res["failed"] is None, f"不应失败：{res['failed']}"
    assert res["done"] == "已翻译完成，详见汉化包目录", "完成提示语不符"
    assert res["progress"] and res["progress"][-1] == 100, "进度未到 100"
    assert all(a <= b for a, b in zip(res["progress"], res["progress"][1:])), "进度不单调"
    assert len(res["leng"]) >= 1, "冷知识未触发"

    packs = packager.list_packs(root)
    print(f"\n生成汉化包 {len(packs)} 个：")
    for p in packs:
        print(f"   - {p['name']}  ({p['count']} 条)  {p['dir']}")
    assert len(packs) == 2, "应生成 2 个汉化包"

    # 检查 demo 包内容
    demo = next(p for p in packs if "demo" in p["id"].lower() or "Demo" in p["id"])
    d = Path(demo["dir"])
    assert (d / "pack.mcmeta").is_file(), "缺少 pack.mcmeta"
    assert (d / "README.txt").is_file(), "缺少 README.txt"
    zj = d / "assets" / "demo" / "lang" / "zh_cn.json"
    zl = d / "assets" / "demo" / "lang" / "zh_cn.lang"
    assert zj.is_file(), "缺少 zh_cn.json"
    assert zl.is_file(), "缺少 zh_cn.lang"
    data = json.loads(zj.read_text(encoding="utf-8"))
    print(f"\nzh_cn.json 内容：{json.dumps(data, ensure_ascii=False)}")
    assert data["block.demo.stone"] == "石头方块", "整句词表未命中"
    assert data["item.demo.pickaxe"] == "镐子", "整句词表未命中"
    assert "%s" in data["gui.demo.title"] and "%1$d" in data["gui.demo.title"], "占位符丢失"
    assert "欢迎" in data["gui.demo.title"], "带占位符的句子未翻译"
    assert data["msg.demo.color"].startswith("§a"), "§ 颜色码丢失"
    assert "成功" in data["msg.demo.color"], "§ 颜色码句子未翻译"

    meta = json.loads((d / "pack.mcmeta").read_text(encoding="utf-8"))
    assert "supported_formats" in meta["pack"], "未声明全版本兼容"

    lang_txt = zl.read_text(encoding="utf-8")
    assert "block.demo.stone=石头方块" in lang_txt, ".lang 格式不正确"

    # 启用一次，确认 options.txt
    packager.enable_pack(GAME, demo)
    options = (GAME / "options.txt").read_text(encoding="utf-8")
    rp_line = options.split("resourcePacks:", 1)[1].split("\n", 1)[0]
    rp = json.loads(rp_line)
    assert rp[-1] == f"file/{demo['id']}", f"未置于加载顺序末尾：{rp}"
    assert "fov:0.0" in options, "options.txt 其它行被破坏"
    print(f"options.txt resourcePacks = {rp}")

    _safe_rmtree(GAME)
    MODEL.unlink(missing_ok=True)
    print("\n" + "=" * 56)
    print("端到端验证全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
