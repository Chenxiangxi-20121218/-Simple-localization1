# MC 模组汉化工具

《我的世界》Java 版 **离线模组汉化工具**。界面仿 PCL2 启动器风格，纯 Python + PySide6 实现，
可打包为免安装的 Windows `.exe`。

- **全版本通用**：产出的是 **资源包（resource pack）**，不是模组。同时生成 `zh_cn.json`（1.13+）
  与 `zh_cn.lang`（1.13 以前）两种语言文件，`pack.mcmeta` 声明 `supported_formats: 1~99`，
  从远古版本到最新快照都能加载。
- **完全离线**：不联网、不调用任何在线接口，翻译由本地 `.zip` 词表/模型包完成。
- **支持所有主流加载器**：Fabric / Quilt / Forge / NeoForge / LiteLoader。

---

## 一、快速开始

### 方式 A：直接运行 exe（推荐）

```
双击 dist\MCModLocalizer.exe
```

首次启动约 2-5 秒（单文件模式需要先解包到 `%TEMP%`）。

> ⚠️ **C 盘空间不足时**：单文件 exe 运行时会把内容解包到 `%TEMP%`（默认在 C 盘）。
> 如果 C 盘已满，请改用 `python build.py --onedir` 打包成目录版，双击 `dist\MCModLocalizer\MCModLocalizer.exe` 运行。

### 方式 B：源码运行

```bash
# 1. 建虚拟环境（建议建在非 C 盘）
python -m venv D:\proj\.venv

# 2. 装依赖
D:\proj\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. 启动
D:\proj\.venv\Scripts\python.exe main.py
```

---

## 二、打包成 .exe

```bash
# 默认：维护版号 +1 → 生成图标 → 打包 → 复制资源 → 自检
python build.py

# 其它常用参数
python build.py --no-bump     # 不递增版本号
python build.py --onedir      # 打包成目录版（启动更快，不占 %TEMP%）
python build.py --clean-only  # 只清理 dist/ 与 .build/
python build.py --no-verify   # 跳过产物自检
```

产物：`dist\MCModLocalizer.exe`（单文件，约 45-60 MB）。

> ⚠️ **重新打包前请先关闭正在运行的 `MCModLocalizer.exe`**。
> Windows 会锁定运行中的 exe，PyInstaller 覆盖不了旧文件，会直接报错退出。
> 若不确定是否还在运行，可在任务管理器里确认，或先删掉 `dist\MCModLocalizer.exe` 再打包。

> 💾 **重新打包不会清空你的数据**。`dist\config.json`（游戏目录、模型、汉化包启停）
> 与 `dist\resources\` 里你改过的文本都会被保留 —— `build.py` 只删本次的构建产物（exe/pkg），
> 并且只有当项目里的源文件更新时才会覆盖 `dist\resources\` 里的同名文件。

**打包脚本做了什么**

| 步骤 | 说明 |
| --- | --- |
| 1. 递增版本号 | 调 `tools/bump_version.py`，`z` 维护版 +1 |
| 2. 生成图标 | 调 `tools/make_icon.py`，用矢量绘制生成多尺寸 `app.ico`（无需 Pillow） |
| 3. PyInstaller | `--onefile --windowed`，排除 QtQml/QtQuick/QtWebEngine/tkinter 等无关模块 |
| 4. 复制资源 | 把 `resources\*.txt` 复制到 `dist\resources\`（**这步不能省**，见下方说明） |
| 5. 自检 | 运行 `dist\MCModLocalizer.exe --selftest`，退出码 0 即通过 |

> **为什么必须复制资源**：`--onefile` 不会自动带上「运行期才读的文本资源」。
> 漏掉这步，成品会**静默回落到内置默认值**，而 `--windowed` 没有控制台，看不到任何报错。
> 另外构建路径（`--workpath` / `--specpath` / `--distpath`）全部指向项目盘，避免占用 C 盘。

---

## 三、功能说明

### 翻译界面

| 区域 | 说明 |
| --- | --- |
| 顶部模型条 | 显示当前翻译模型名；未选择时显示红色「未选择翻译模型，请从设置选择」 |
| 自动筛选文件夹 | 显示自动探测到的 `.minecraft` 目录位置，支持「重新筛选」「更换目录」 |
| 欢迎语 | 默认「欢迎使用 minecraft 模组汉化工具」，可在设置里自定义 |
| 日志 | 只显示一行主要日志，超长自动省略号截断 |
| 开始翻译 | 大按钮。**未选模型或未勾选模组时为灰色不可点；两者都满足时变白可点** |
| 版本选择 | 进入版本选择 + 模组勾选区（全选 / 反选 / 全不选） |
| 汉化包管理 | 进入汉化包列表（全选 / 反选 / 全不选 + 完成） |
| 进度 | 开始后显示进度条 + 预计剩余时间 + 「取消翻译」 |

**工作流程**：读取启动器模组 → 采集英文文本 → 离线机器翻译 → 生成汉化包并置于加载顺序末尾以覆盖原文。

点击「开始翻译」后会在 `.versions\` 下创建名为 **`汉化包`** 的文件夹，当前版本的所有汉化包统一存放在此：

```
.minecraft/
├── .versions/
│   ├── 1.20.1/
│   └── 汉化包/                          ← 点击「开始翻译」时自动创建
│       ├── JEI 物品管理器 汉化包/
│       │   ├── pack.mcmeta
│       │   ├── README.txt
│       │   └── assets/jei/lang/
│       │       ├── zh_cn.json           ← 1.13 及以后
│       │       └── zh_cn.lang           ← 1.13 以前
│       └── 机械动力 汉化包/
├── resourcepacks/                       ← 启用时复制到这里
└── options.txt                          ← 启用时写入 resourcePacks 列表末尾
```

### 版本选择 / 模组选择

- 下拉框选择 Minecraft 版本，点「扫描模组」重新扫描。
- 模组以 **图标 + 中文名 + 英文名** 的卡片形式展示，点击卡片切换勾选。
- 没有任何含 `en_us` 语言文件的模组时，显示「**未发现可以翻译的模组**」。

### 汉化包管理

- 逐个列出汉化包，带「已启用 / 已禁用」徽标。
- 全选 / 反选 / 全不选，点「**完成**」应用更改：
  - **启用**：复制到 `resourcepacks\`，并把 `file/<包名>` **追加到 `options.txt` 的 `resourcePacks` 列表末尾**（置于加载顺序末尾以覆盖原文）；
  - **禁用**：从列表移除并删除 `resourcepacks\` 下的副本。
- 写入时会保留 `options.txt` 的其它所有行，不破坏原有配置。

### 设置界面

| 栏目 | 说明 |
| --- | --- |
| 翻译模型 | 「选择模型」弹出 `.zip` 文件选择框，选完在主界面和设置界面都显示模型名；支持「清除模型」 |
| 个性化 | 调整**边框颜色**、**翻译器颜色**、**翻译器右上角文字**。默认锁定，需付费解锁（`personalize_unlocked`） |
| 赞助 | 「赞助翻译器」跳转到 `wangzhi.txt` 里的网址；**文件不存在则不跳转**，只提示。赞助者栏目以空格分隔展示名字 |
| 杂项 | 「千万别点」按钮（功能预留）；「**回声洞**」双击随机显示一条 `lengzhishi.txt` 里的文字 |

翻译过程中每 **5 分钟**会推送一条 `lengzhishi.txt` 的文字（遇空格跳过），显示在进度卡片并弹提示。

---

## 四、资源文件（可在 exe 同级 `resources\` 目录里改）

| 文件 | 作用 | 缺失时的行为 |
| --- | --- | --- |
| `lengzhishi.txt` | 冷知识文本库，每行一条 | 回落到内置的 8 条默认冷知识 |
| `wangzhi.txt` | 「赞助翻译器」跳转的网址，取第一个非 `#` 开头的行 | **不跳转**，只弹提示（这是默认状态，等你补齐） |
| `wangzhi.txt.example` | 网址配置说明模板 | — |
| `sponsors.txt` | 赞助者名单，空格分隔，`#` 开头为注释 | 回落到内置默认文案 |

把 `wangzhi.txt.example` 重命名为 `wangzhi.txt` 并写入一行网址，「赞助翻译器」按钮即可跳转。

---

## 五、翻译模型 `.zip` 格式

「选择模型」选中的 `.zip` 会被容错解析，**能读多少读多少**，读不到就用内置词表兜底：

```
my-model.zip
├── model.json        # 可选：{"name": "模型名", "version": "1.0", "author": "作者"}
├── dict.json         # 词典，任意以下格式之一：
│                     #   {"Stone": "石头", "Pickaxe": "镐"}
│                     #   [{"src":"Stone","dst":"石头"}]
│                     #   [{"en":"Stone","zh":"石头"}]
│                     #   [["Stone","石头"]]
├── terms.tsv         # 两列制表符：Stone<TAB>石头
├── glossary.csv      # 两列逗号：Stone,石头
└── phrases.json      # 短语级词表，格式同 dict.json
```

内置了 **200+ 条 Minecraft 常用术语**，所以即使选一个几乎空的 zip，也能产出可读的中文。

**占位符保护**：翻译前后会自动保护并原样还原 `%s` `%1$d` `%.2f` `\n` `§a` 颜色码 `&a` 颜色码
`{0}` `{name}` `{{...}}` 等格式符。若还原时数量对不上，直接放弃该次翻译返回原文，避免游戏内显示错乱。

---

## 六、版本号规则

格式 `x.y.z`（定义在 `app/state.py` 的 `APP_VERSION`）：

- `x` **大版本** —— 用 `python tools/bump_version.py --major` 手动递增
- `y` **小更新** —— 一般不变，用 `--minor` 手动递增
- `z` **维护版** —— **每次更新自动递增**，`build.py` 默认就会执行

```bash
python tools/bump_version.py --show     # 查看当前版本
python tools/bump_version.py            # z + 1
python tools/bump_version.py --minor    # y + 1, z = 0
python tools/bump_version.py --major    # x + 1, y = 0, z = 0
```

---

## 七、开发与验证

```bash
# 全量编译检查
.venv\Scripts\python.exe -m compileall -q app main.py tools

# 离屏渲染各页面截图到 preview/（按状态演进顺序输出）
.venv\Scripts\python.exe tools\render_preview.py

# 功能冒烟测试（59 项断言：按钮启用态、目录创建、资源包启停、占位符保护、持久化…）
.venv\Scripts\python.exe tools\smoke_test.py

# 打包产物自检
dist\MCModLocalizer.exe --selftest
```

### 项目结构

```
├── main.py                入口：无边框主窗口 + 渐变标题栏 + 侧边栏 + 页面路由 + --selftest
├── build.py               一键打包
├── requirements.txt
├── INTERFACES.md          模块接口契约（并行开发用）
├── app/
│   ├── theme.py           配色常量 + QSS（string.Template）
│   ├── icons.py           24 个矢量图标，QPainter 现场绘制，零图片资源
│   ├── widgets.py         Card / BigButton / NavItem / ModCard / PackRow / FlowLayout / Toast / TitleBar
│   ├── state.py           全局状态单例 + config.json 持久化 + 文本资源读取
│   ├── paths.py           路径与目录管理（含 .minecraft 自动探测）
│   ├── router.py          页面路由
│   ├── core/
│   │   ├── modscan.py     模组扫描（四种加载器元数据 + 语言文件 + 图标，带缓存）
│   │   ├── translator.py  离线翻译引擎（zip 模型解析 + 内置词表 + 占位符保护）
│   │   ├── packager.py    汉化包生成 / 启用 / 禁用 / options.txt 同步
│   │   └── worker.py      后台翻译线程（进度、冷知识定时、可取消）
│   └── pages/
│       ├── translate.py   翻译主界面
│       ├── modselect.py   版本选择 / 模组选择
│       ├── packs.py       汉化包管理
│       └── settings.py    设置界面
├── tools/
│   ├── make_icon.py       生成多尺寸 app.ico
│   ├── bump_version.py    版本号管理
│   ├── render_preview.py  离屏渲染预览图
│   └── smoke_test.py      冒烟测试
└── resources/             可编辑文本资源
```

---

## 八、已知限制

1. **翻译质量取决于词表**。内置的是术语级词典 + 规则替换，未命中的英文片段原样保留，不会乱翻。
   要接入真实 NMT 模型，替换 `app/core/translator.py` 里 `TranslateModel.translate()` 的内部实现即可，
   对外接口不用改。
2. **只扫描含 `en_us` 语言文件的模组**。没有英文语言文件的模组不参与翻译（在模组选择区不显示）。
3. **模组扫描是同步的**。模组数量极多（数百个）时首次扫描会有短暂卡顿，之后走缓存会快很多。
4. **`options.txt` 修改需游戏未运行**。游戏运行时改 `options.txt` 会在退出时被覆盖。
5. **单文件 exe 会解包到 `%TEMP%`**。C 盘紧张请用 `--onedir`。
6. **付费功能仅预留门禁**。个性化栏目已实现锁定/解锁逻辑（`STATE.personalize_unlocked`），
   尚未接入真实支付。
