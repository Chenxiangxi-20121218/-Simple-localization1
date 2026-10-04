# 接口契约（并行开发必须严格遵守）

> 本文件是「多个子 AI 并行开发」的契约。所有模块必须严格按此签名实现，不得自行改名、改参数、改返回结构。
> 项目根目录：`D:/汉化（1）`。Python 解释器：`D:/汉化（1）/.venv/Scripts/python.exe`。

## 0. 项目结构

```
D:/汉化（1）/
├── main.py                    入口（主窗口 + 无边框 + --selftest）
├── build.py                   一键打包 exe
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── paths.py               [已完成] 路径管理
│   ├── theme.py               [已完成] 配色 + QSS
│   ├── icons.py               [已完成] 矢量图标
│   ├── widgets.py             [已完成] 通用控件
│   ├── state.py               [已完成] 全局状态单例
│   ├── router.py              [已完成] 页面路由
│   ├── core/
│   │   ├── __init__.py
│   │   ├── modscan.py         模组扫描
│   │   ├── translator.py      离线翻译引擎
│   │   ├── packager.py        汉化包生成 / 启用
│   │   └── worker.py          后台翻译线程
│   └── pages/
│       ├── __init__.py
│       ├── translate.py       翻译主界面
│       ├── modselect.py       版本选择 / 模组选择
│       ├── packs.py           汉化包管理
│       └── settings.py        设置界面
├── tools/
│   ├── make_icon.py
│   ├── bump_version.py
│   ├── render_preview.py
│   └── smoke_test.py
└── resources/
    ├── lengzhishi.txt
    ├── wangzhi.txt
    └── sponsors.txt
```

## 1. 已完成模块的 API（直接调用，不要重写）

### `app.theme`
```python
from ..theme import C, apply_accent, qss, mix, lighten, darken
# C.BLUE / C.BLUE_DARK / C.BLUE_LIGHT / C.BLUE_PALE / C.TITLE_TOP / C.TITLE_BOTTOM
# C.BG / C.BG_SIDE / C.CARD / C.CARD_ALT
# C.TEXT / C.TEXT_SUB / C.TEXT_ON_BLUE / C.BORDER / C.BORDER_SOFT
# C.OK / C.WARN / C.ERR / C.DIS_BG / C.DIS_TEXT / C.HOVER / C.HOVER_BLUE
# C.PROGRESS_BG / C.SHADOW
```

### `app.icons`
```python
from ..icons import pixmap, icon
pixmap(name: str, color: str, size: int = 24) -> QPixmap
icon(name: str, color: str, size: int = 24) -> QIcon
# name ∈ {translate, settings, folder, package, play, model, heart, sponsor,
#         warning, cave, check, close, min, max, restore, back, refresh, list,
#         brush, logo, clock, lock, star, text}
```

### `app.widgets`
```python
Card(title: str = "", shadow: bool = True, padding: int = 16)
    .add(widget_or_qlayout)  .add_stretch(n=1)  .add_header_widget(w)
    .title_label  .header  .body

Separator()

EmptyHint(text: str, icon_name: str = "package")     # 居中灰字空状态
    .set_icon_text(text, icon_name)

BigButton(text: str, icon_name: str = "play")        # 自绘：灰(不可用) -> 白(可用)
    .setEnabled(bool)  .set_icon_name(name)  .clicked

IconButton(text: str, icon_name: str, color: str | None = None, primary: bool = False)

NavItem(key: str, text: str, icon_name: str)  .set_active(bool)

FlowLayout(parent=None, margin=0, hspacing=12, vspacing=12)   # 标准 QLayout

ModCard(mod_id: str, cn_name: str, en_name: str, icon_pm: QPixmap | None = None)
    .set_selected(bool)  .is_selected()  .toggled(str, bool)
    .mod_id  .cn_name  .en_name   # 只读属性
    # 固定尺寸 150x172

PackRow(pack_id: str, name: str, detail: str)
    .set_checked(bool)  .is_checked()  .toggled(str, bool)
    # 固定高度 54

Toast(parent: QWidget, text: str, msec: int = 2200)
toast(parent: QWidget, text: str, msec: int = 2200) -> Toast

TitleBar(title: str, brand_icon: str = "logo")

label(text, obj="", size=13, bold=False, color=None, wrap=False) -> QLabel
icon_label(name, color, size=18) -> QLabel
```

### `app.paths`
```python
APP_NAME, APP_ID
app_dir() -> Path              # 打包后=exe 目录；源码运行=项目根
bundle_dir() -> Path
resource_dir() -> Path         # <app_dir>/resources
config_file() -> Path
detect_game_dirs() -> list[Path]
default_game_dir() -> Path
looks_like_game_dir(p: Path) -> bool
versions_dir(game_dir: Path) -> Path
list_versions(game_dir: Path) -> list[str]
mods_dirs(game_dir: Path, version: str | None = None) -> list[Path]
hanhuabao_root(game_dir: Path) -> Path            # <game>/.versions/汉化包
hanhuabao_version_dir(game_dir, version) -> Path
resourcepacks_dir(game_dir) -> Path
options_txt(game_dir) -> Path
```

### `app.state`
```python
from ..state import STATE, APP_VERSION, DEFAULT_WELCOME, DEFAULT_TRANSLATOR_TITLE

STATE.model_path / .model_name / .model_info / .has_model() / .set_model(path,name,info) / .clear_model()
STATE.game_dir / .set_game_dir(d) / .game_path()
STATE.current_version / .set_version(v)
STATE.mods: list[dict] / .set_mods(list) / .selected_mods: set[str]
STATE.toggle_mod(id, bool) / .selected_mod_list() / .can_translate() -> bool
STATE.packs: list[dict] / .set_packs(list) / .pack_enabled: dict[str,bool] / .set_pack_enabled(id, bool)
STATE.welcome_text / .set_welcome(t)
STATE.accent_color / .border_color / .translator_title / .set_personalize(accent, border, title)
STATE.personalize_unlocked: bool
STATE.sponsors / .sponsors_text() / .sponsor_url() -> str
STATE.lengzhishi_lines() -> list[str] / .random_lengzhishi() -> str
STATE.last_log / .log(text) / .save()

# 信号（QObject Signal）
modelChanged()  gameDirChanged()  versionChanged()  modsChanged()  packsChanged()
logChanged(str)  themeChanged()  sponsorsChanged()
progressChanged(int, str)   # 百分比, 预计剩余文案
finished(str)               # 完成提示语
```

### `app.router`
```python
class Router:
    def go(self, key: str) -> None      # key ∈ {"translate","modselect","packs","settings"}
    def back(self) -> None              # 返回上一页
    def current(self) -> str
```

## 2. 待实现模块的接口（必须完全一致）

### 2.1 `app/core/modscan.py`

```python
from pathlib import Path
from PySide6.QtGui import QPixmap

def scan_mods(mod_dirs: list[Path]) -> list[dict]: ...
def read_lang_entries(jar_path: str | Path, entry: str) -> dict[str, str]: ...
def clear_cache() -> None: ...
```

`scan_mods` 返回的每个 dict 必须包含：

```python
{
  "id": str,            # 唯一标识，用 jar 绝对路径（保证唯一、可复现）
  "modid": str,         # 主命名空间
  "namespaces": list[str],   # 全部命名空间（多 modid 都要）
  "cn_name": str,       # 中文名；取不到时回落到 en_name
  "en_name": str,       # 英文名；取不到时回落到 jar 文件名（去扩展名）
  "path": str,          # jar 绝对路径
  "icon": QPixmap|None, # 已缩放为 64x64 的图标
  "loader": str,        # "fabric"|"forge"|"neoforge"|"quilt"|"liteloader"|"unknown"
  "mc_version": str,    # 可为 ""
  "lang_files": list[dict],  # 见下
  "translatable": bool,      # lang_files 非空即 True
  "error": str,              # 正常为 ""
}
```

`lang_files` 元素：
```python
{"namespace": str, "lang": "en_us", "entry": "assets/<ns>/lang/en_us.json", "format": "json"}
# format ∈ {"json", "lang"}；.lang 为 1.13 以前的纯文本格式
```

要求：
- 支持 Fabric(`fabric.mod.json`)、Forge/NeoForge(`META-INF/mods.toml` 或 `mcmod.info`)、Quilt(`quilt.mod.json`)、LiteLoader(`litemod.json`)。
- 解析 `fabric.mod.json` 的 `id`、`name`、`description`；`mods.toml` 的 `modId`、`displayName`。
- 命名空间来源：元数据 id + jar 内 `assets/*/lang/` 目录名，合并去重。
- 语言文件：只收集 `assets/<ns>/lang/en_us.json` 与 `assets/<ns>/lang/en_us.lang`。
- 图标：`assets/<ns>/icon.png`、`icon.png`、`logo.png`、`pack.png` 任取第一个存在的，缩放到 64x64（保持比例、居中、透明填充）。
- 必须带缓存：`{(jar_path, mtime, size): result}`，避免切页时反复解压。`clear_cache()` 清空。
- **绝不允许抛异常给调用方**：单个 jar 失败就填 `error` 并返回该条目。
- 只读操作，不得修改任何 jar。

### 2.2 `app/core/translator.py`

```python
class ModelError(Exception): ...

def load_model(zip_path: str) -> tuple[str, dict]:
    """加载 .zip 翻译模型，返回 (模型名, 模型信息 dict)。失败抛 ModelError。"""

class TranslateModel:
    def __init__(self, zip_path: str): ...
    @property
    def name(self) -> str: ...
    @property
    def info(self) -> dict: ...
    def translate(self, text: str) -> str: ...
    def translate_batch(self, texts: list[str]) -> list[str]: ...

def get_model() -> TranslateModel | None:
    """返回当前 STATE 已加载的模型单例（未加载/路径变了则重新加载）。"""

def estimate_seconds(text_count: int) -> float:
    """粗略估算翻译耗时（秒）。"""
```

要求：
- 模型 zip 内可能包含：`model.json`/`config.json`（元信息，字段 `name`/`version`/`type`/`author`）、
  `dict.json`/`glossary.json`/`terms.json`/`phrases.json`（`{"en": "zh"}` 或 `[{"src":..,"dst":..}]`）、
  `*.tsv`/`*.csv`（两列 en<TAB>zh）、以及任意扁平 `*.json`。
  **要能容错地全部读进来合并成一张词典**；一个都读不到也要能用（内置词表兜底），不得抛异常。
- 必须内置一份 Minecraft 常用术语词表（如 `Stone`→`石头`、`Crafting Table`→`工作台`、
  `Diamond`→`钻石`、`Pickaxe`→`镐`、`Health`→`生命值`、`Inventory`→`物品栏` …至少 120 条），
  保证「无模型」或「模型很小」时仍能产出可读的中文。
- **必须保护占位符与格式符**：`%s` `%1$s` `%d` `%.2f` `%n`、`\n`、`§a` 等 `§` 颜色码、
  `{0}` `{name}` `{{...}}`、`&` 颜色码，翻译后原样保留且顺序不错乱。
- 翻译策略（离线、确定性、不联网）：先整句词典命中 → 再术语替换 + 未命中片段保留原文。
  同一输入必须返回同一输出（可缓存）。
- `translate("")` 返回 `""`；`None` 视为 `""`。
- 绝不联网、绝不 import 任何非标准库/非 PySide6 的第三方包。

### 2.3 `app/core/packager.py`

```python
from pathlib import Path

def create_pack(root: Path, version: str, mod: dict,
                translated: dict[str, dict[str, str]],
                names: dict[str, dict[str, str]]) -> dict:
    """生成一个汉化包目录。

    root       : 汉化包根目录（= paths.hanhuabao_root(game_dir)）
    version    : MC 版本名
    mod        : modscan.scan_mods() 返回的元素
    translated : {namespace: {key: 中文}}
    names      : {namespace: {"cn": 中文名, "en": 英文名}}
    返回 pack 信息 dict（结构见下）
    """

def list_packs(root: Path) -> list[dict]: ...
def enable_pack(game_dir: Path, pack: dict) -> bool: ...
def disable_pack(game_dir: Path, pack: dict) -> bool: ...
def apply_enabled(game_dir: Path) -> None:
    """按 STATE.pack_enabled 批量启用/禁用，并同步 options.txt。"""
```

pack 信息 dict（必须与 `app.pages.packs` 约定一致）：
```python
{
  "id": str,        # 唯一 id = pack 目录名
  "name": str,      # 展示名，如 "JEI 汉化包"
  "detail": str,    # 副标题，如 "1 个命名空间 · 128 条译文 · 2026-10-01"
  "dir": str,       # pack 目录绝对路径
  "version": str,   # MC 版本
  "modid": str,
  "enabled": bool,  # 是否已启用
  "count": int,     # 译文条数
}
```

汉化包目录结构（**必须**）：
```
<root>/<pack_dir_name>/
├── pack.mcmeta
├── README.txt
└── assets/<namespace>/lang/zh_cn.json
    assets/<namespace>/lang/zh_cn.lang     # 1.13 以前版本兼容
```

- `pack.mcmeta`：`{"pack": {"pack_format": 1, "description": "...", "supported_formats": {"min_inclusive": 1, "max_inclusive": 99}}}`，
  保证 MC 全版本通用。
- `zh_cn.json` 用 `json.dumps(..., ensure_ascii=False, indent=2)`。
- `zh_cn.lang` 为 `key=value` 逐行文本（1.13 以前的格式）。
- 目录名需过滤 Windows 非法字符 `\\ / : * ? " < > |`，并限制长度。

启用机制：
- 把 pack 目录复制到 `<game_dir>/resourcepacks/<pack_dir_name>/`。
- 在 `options.txt` 的 `resourcePacks:[...]` 列表**末尾追加** `"file/<pack_dir_name>"`（需求：置于加载顺序末尾以覆盖原文）。
- `options.txt` 不存在时创建；解析要容错（该行可能不存在、可能是 `resourcePacks:[]`）。
- 禁用：从 `resourcePacks` 列表移除该条目，并删除 `resourcepacks/<name>/` 目录。
- 所有文件操作必须容错，返回 bool 而不是抛异常。

### 2.4 `app/core/worker.py`

```python
from PySide6.QtCore import QThread, Signal

class TranslateWorker(QThread):
    progress = Signal(int, str)        # percent, 预计剩余文案
    log = Signal(str)
    lengzhishi = Signal(str)           # 每 5 分钟一条冷知识
    done = Signal(str)                 # 完成提示语
    failed = Signal(str)

    def __init__(self, game_dir: str, version: str, mods: list[dict], parent=None): ...
    def run(self) -> None: ...
    def cancel(self) -> None: ...
```

要求：
- `run()` 里：为每个 mod 读取 `lang_files` 的英文原文 → `translator.translate_batch` → `packager.create_pack`。
- 每个 mod 完成后 emit `progress(percent, "预计剩余 X 分 Y 秒")`。
- 用 `QTimer`/循环内计时，每满 **300 秒** emit 一条 `STATE.random_lengzhishi()`（遇空格跳过）。
- 完成 emit `done("已翻译完成，详见汉化包目录")`。
- 单个 mod 失败只记录 `log`，不中断整体。
- 支持 `cancel()`，循环内检查标志位。

### 2.5 页面模块

四个页面统一构造签名与刷新方法：

```python
class TranslatePage(QWidget):
    def __init__(self, router, parent=None): ...
    def refresh(self) -> None: ...

class ModSelectPage(QWidget):
    def __init__(self, router, parent=None): ...
    def refresh(self) -> None: ...

class PacksPage(QWidget):
    def __init__(self, router, parent=None): ...
    def refresh(self) -> None: ...

class SettingsPage(QWidget):
    def __init__(self, router, parent=None): ...
    def refresh(self) -> None: ...
```

**页面必须订阅 `STATE` 的信号自行刷新**，不要依赖外部调用 `refresh()`（`refresh()` 只在路由切换时被调用）。

## 3. 编码规范

- 每个文件顶部 `# -*- coding: utf-8 -*-`。
- 用 `from __future__ import annotations`。
- 页面内引用用相对导入：`from ..widgets import Card, BigButton`、`from ..state import STATE`、
  `from ..core import modscan`。
- 禁止 import 任何第三方包（只有 PySide6 可用，标准库随便用）。
- 所有面向用户的文案使用简体中文。
- 不要写 `if __name__ == "__main__"` 到模块文件里。
- 不要修改 `theme.py / icons.py / widgets.py / state.py / paths.py / router.py`（已完成）。
