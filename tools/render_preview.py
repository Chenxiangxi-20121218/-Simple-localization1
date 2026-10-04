# -*- coding: utf-8 -*-
"""离屏渲染各页面截图到 ``preview/``，用于人工确认视觉效果。

⚠️ 截图严格按「状态演进顺序」输出：先截空状态，再注入数据截后续状态。
反过来会产出文件名与画面不符的预览，那种预览比不截还糟。

用法::

    python tools/render_preview.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt                                    # noqa: E402
from PySide6.QtGui import QColor, QFontDatabase, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication                       # noqa: E402


def _safe_rmtree(p) -> None:
    """删除临时目录。某些受管环境会拦截批量删除，此处吞掉异常避免中断流程。"""
    try:
        shutil.rmtree(p, ignore_errors=True)
    except BaseException:
        pass

OUT = ROOT / "preview"
TMP = ROOT / ".tmp" / "preview_game"
CONFIG = ROOT / "config.json"
CONFIG_BAK = ROOT / "config.json.preview-bak"

#: 沙箱里 QFontDatabase.families() 可能为空 -> 中文全变方块，必须手动加载系统字体
FONT_FILES = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
)


def _make_mod_icon(color: str) -> QPixmap:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(2, 2, 60, 60, 12, 12)
    p.setBrush(QColor("#FFFFFF"))
    p.drawEllipse(20, 20, 24, 24)
    p.end()
    return pm


FAKE_MODS = [
    ("jei", "JEI 物品管理器", "Just Enough Items", "#3A7CC3"),
    ("create", "机械动力", "Create", "#D08A2E"),
    ("botania", "植物魔法", "Botania", "#4CAF6E"),
    ("twilightforest", "暮色森林", "The Twilight Forest", "#5B7FBF"),
    ("ae2", "应用能源2", "Applied Energistics 2", "#8E6FC4"),
    ("mekanism", "通用机械", "Mekanism", "#C4553D"),
    ("farmersdelight", "农夫乐事", "Farmer's Delight", "#7AA83C"),
    ("immersiveengineering", "沉浸工程", "Immersive Engineering", "#6E7B8B"),
    ("sodium", "钠", "Sodium", "#2FA8A0"),
    ("iris", "鸢尾", "Iris Shaders", "#4B6FB5"),
    ("xaeros_minimap", "Xaero的小地图", "Xaero's Minimap", "#B58B3A"),
    ("curios", "饰品栏", "Curios API", "#A05FA8"),
]


def _build_fake_mods():
    mods = []
    for modid, cn, en, color in FAKE_MODS:
        mods.append({
            "id": str(ROOT / ".tmp" / "mods" / f"{modid}.jar"),
            "modid": modid,
            "namespaces": [modid],
            "cn_name": cn,
            "en_name": en,
            "path": str(ROOT / ".tmp" / "mods" / f"{modid}.jar"),
            "icon": _make_mod_icon(color),
            "loader": "fabric",
            "mc_version": "1.20.1",
            "lang_files": [{"namespace": modid, "lang": "en_us",
                            "entry": f"assets/{modid}/lang/en_us.json", "format": "json"}],
            "translatable": True,
            "error": "",
        })
    return mods


def _prepare_game_dir() -> Path:
    if TMP.exists():
        _safe_rmtree(TMP)
    for v in ("1.20.1", "1.19.2", "1.16.5"):
        (TMP / ".versions" / v / "mods").mkdir(parents=True, exist_ok=True)
    (TMP / "mods").mkdir(parents=True, exist_ok=True)
    (TMP / "resourcepacks").mkdir(parents=True, exist_ok=True)
    (TMP / "options.txt").write_text(
        'version:1.20.1\nresourcePacks:["vanilla","fabric"]\n', encoding="utf-8"
    )
    return TMP


def _make_real_packs(game: Path, mods: list[dict]) -> list[dict]:
    """用真实的 packager 生成 3 个汉化包，保证预览与产物一致。"""
    from app import paths
    from app.core import packager

    root = paths.hanhuabao_root(game)
    for m in mods[:3]:
        ns = m["modid"]
        translated = {
            ns: {
                f"block.{ns}.stone": "石头方块",
                f"item.{ns}.pickaxe": "镐子",
                f"gui.{ns}.title": "欢迎使用 %s",
                f"mod.{ns}.name": m["cn_name"],
            }
        }
        names = {ns: {"cn": m["cn_name"], "en": m["en_name"]}}
        packager.create_pack(root, "1.20.1", m, translated, names)
    return packager.list_packs(root)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if CONFIG.is_file():
        shutil.copy2(CONFIG, CONFIG_BAK)

    app = QApplication(sys.argv)
    for f in FONT_FILES:                      # 必须在 QApplication 之后加载
        if os.path.isfile(f):
            QFontDatabase.addApplicationFont(f)

    from app.state import STATE
    from app.theme import qss
    from main import MainWindow

    app.setStyleSheet(qss())
    game = _prepare_game_dir()

    win = MainWindow()
    win.resize(1180, 760)
    win.show()
    app.processEvents()

    def shot(name: str) -> None:
        for _ in range(3):
            app.processEvents()
        path = OUT / name
        win.grab().save(str(path))
        print(f"  -> {name}")

    # ================= 1. 空状态（必须在注入数据之前） =================
    STATE.clear_model()
    STATE.selected_mods.clear()
    STATE.set_mods([])
    STATE.set_game_dir(str(game))
    STATE.set_version("1.20.1")
    STATE.log("就绪，等待开始。")

    win.router.go("translate"); shot("01_translate_empty.png")
    win.router.go("modselect"); shot("02_modselect_empty.png")
    win.router.go("packs"); shot("03_packs_empty.png")
    win.resize(1180, 1020)                 # 设置页内容较长，用高窗口截全
    win.router.go("settings"); shot("04_settings_default.png")

    # ================= 2. 注入模型 =================
    fake_zip = ROOT / ".tmp" / "fake_model.zip"
    fake_zip.parent.mkdir(parents=True, exist_ok=True)
    fake_zip.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    STATE.set_model(str(fake_zip), "MC 通用离线词表 v2", {"entries": 128460, "version": "2.0"})
    win.router.go("settings"); shot("05_settings_model.png")

    # ================= 3. 注入模组列表 =================
    STATE.set_mods(_build_fake_mods())
    STATE.selected_mods = {m["id"] for m in STATE.mods[:5]}
    win.resize(1180, 760)
    win.router.go("modselect"); shot("06_modselect_list.png")

    # ================= 4. 已选模型 + 已选模组 -> 开始翻译变白 =================
    STATE.log("已选择 5 个模组，可以开始翻译。")
    win.router.go("translate"); shot("07_translate_ready.png")

    # ================= 5. 翻译进行中 =================
    STATE.progressChanged.emit(62, "预计剩余 1 分 24 秒")
    STATE.log("正在翻译：机械动力（1284/2048）")
    shot("08_translate_progress.png")

    # ================= 6. 汉化包列表（用真实 packager 生成） =================
    packs = _make_real_packs(game, STATE.mods)
    STATE.set_packs(packs)
    if packs:
        STATE.pack_enabled[packs[0]["id"]] = True
    win.router.go("packs"); shot("09_packs_list.png")

    # ================= 7. 个性化解锁后 =================
    STATE.personalize_unlocked = True
    STATE.set_personalize("#2E6DB4", "#DCE1E8", "MC 模组汉化工具")
    win.resize(1180, 1020)
    win.router.go("settings"); shot("10_settings_personalize.png")

    # ================= 收尾 =================
    STATE.personalize_unlocked = False
    STATE.save()
    if CONFIG_BAK.is_file():
        shutil.copy2(CONFIG_BAK, CONFIG)
        CONFIG_BAK.unlink()
    _safe_rmtree(TMP)
    print(f"\n共生成 {len(list(OUT.glob('*.png')))} 张预览图 -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
