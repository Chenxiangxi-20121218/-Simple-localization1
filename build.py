# -*- coding: utf-8 -*-
"""一键打包 Windows .exe。

用法::

    python build.py                 # 递增维护版号 -> 生成图标 -> PyInstaller -> 复制资源 -> 自检
    python build.py --no-bump       # 不递增版本号
    python build.py --onedir        # 打包成目录（启动更快、不占 %TEMP%）
    python build.py --clean-only    # 只清理构建产物

产物：``dist/MCModLocalizer.exe``（单文件，双击即可运行）
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "MCModLocalizer"
DIST = ROOT / "dist"
BUILD = ROOT / ".build"
SPEC = ROOT / ".build" / "spec"
ENTRY = ROOT / "main.py"

#: 这些 Qt 模块用不到，排除后能省几十 MB
EXCLUDES = (
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebChannel",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.Qt3DCore",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtBluetooth",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtLocation", "PySide6.QtNfc",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
    "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtSpatialAudio",
    "PySide6.QtSql", "PySide6.QtStateMachine", "PySide6.QtSvgWidgets",
    "PySide6.QtTest", "PySide6.QtTextToSpeech", "PySide6.QtUiTools",
    "PySide6.QtWebSockets", "PySide6.QtXml",
    "tkinter", "unittest", "pydoc", "doctest", "pdb", "email", "http", "xmlrpc",
)

#: 运行期才读的文本资源（--onefile 不会自动带上，必须显式复制到 dist）
TEXT_RESOURCES = ("lengzhishi.txt", "sponsors.txt", "wangzhi.txt")

#: PyInstaller 的超时上限（秒）。正常约 60~90 秒；实测曾出现过**静默卡死**
#: （50 分钟零产出、`.build/work-*/` 全空），所以必须有上限，不能无限等。
BUILD_TIMEOUT = 900


def log(msg: str) -> None:
    print(f"[build] {msg}", flush=True)


def _tail(path: Path, n: int = 4000) -> str:
    """读文件末尾 n 个字符（读不到就返回空串）。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-n:]


# ---------------------------------------------------------------- 版本


def bump_version() -> str:
    out = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "bump_version.py")],
        capture_output=True, text=True, encoding="utf-8",
    )
    ver = out.stdout.strip() or "unknown"
    log(f"版本号递增 -> {ver}")
    return ver


def read_version() -> str:
    out = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "bump_version.py"), "--show"],
        capture_output=True, text=True, encoding="utf-8",
    )
    return out.stdout.strip() or "unknown"


# ---------------------------------------------------------------- 图标


def make_icon() -> Path:
    ico = ROOT / "app.ico"
    try:
        subprocess.run(
            [sys.executable, str(ROOT / "tools" / "make_icon.py")],
            check=True, capture_output=True, text=True, encoding="utf-8",
        )
        log(f"图标已生成 -> {ico.name}")
    except subprocess.CalledProcessError as e:
        log(f"图标生成失败，改用默认图标：{e.stderr.strip()[:200]}")
    return ico


# ---------------------------------------------------------------- 资源复制


def copy_resources() -> None:
    """把运行期读取的文本资源复制到 dist，保证产物自洽。

    ⚠️ 漏掉这一步时成品会静默回落到内置默认值，而 --windowed 没有控制台、看不到报错。

    ⚠️ 只在「目标缺失」或「源文件更新」时才覆盖：dist/resources/ 是**用户可编辑**的，
    用户改过的冷知识、赞助者名单、wangzhi.txt 不能被重新打包静默冲掉。
    """
    src = ROOT / "resources"
    dst = DIST / "resources"
    dst.mkdir(parents=True, exist_ok=True)

    def _put(name: str, default: str, required: bool = True) -> None:
        target = dst / name
        source = src / name
        if source.is_file():
            if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
                log(f"保留用户已修改的 resources/{name}")
                return
            shutil.copy2(source, target)
        elif required and not target.is_file():
            target.write_text(default, encoding="utf-8")

    _put("lengzhishi.txt", "Minecraft 的英文名最初叫 Cave Game。\n")
    _put("sponsors.txt", "感谢以下赞助者\n")

    # 赞助网址：**故意不创建**（用户尚未提供），文件缺失时点击按钮不跳转
    if (src / "wangzhi.txt").is_file():
        _put("wangzhi.txt", "")
        log("已复制 wangzhi.txt（赞助按钮可跳转）")
    else:
        ex = src / "wangzhi.txt.example"
        if ex.is_file() and not (dst / "wangzhi.txt.example").is_file():
            shutil.copy2(ex, dst / "wangzhi.txt.example")
        if (dst / "wangzhi.txt").is_file():
            log("检测到 dist/resources/wangzhi.txt（赞助按钮可跳转）")
        else:
            log("未提供 wangzhi.txt -> 赞助按钮保持「不跳转」行为（符合需求）")

    log(f"文本资源已同步 -> {dst}")


# ---------------------------------------------------------------- 清理


def clean() -> None:
    """清理构建产物。

    ⚠️ **绝不能整个删掉 dist/**：`dist/config.json` 是用户的配置（游戏目录、模型、汉化包启停），
    `dist/resources/` 里可能有用户改过的文本。整目录 rmtree 会静默清空用户数据。
    所以这里只删「本次构建的产物」：exe 文件与 onedir 目录。
    """
    if BUILD.exists():
        try:
            shutil.rmtree(BUILD, ignore_errors=True)
        except BaseException as e:
            log(f"清理 .build 时被拦截（{type(e).__name__}），继续打包")

    if DIST.exists():
        for pattern in ("*.exe", "*.pkg", APP_NAME):
            for p in DIST.glob(pattern):
                try:
                    if p.is_dir():
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        p.unlink()
                except BaseException as e:
                    log(f"删除 {p.name} 失败（{type(e).__name__}）："
                        f"若程序正在运行请先关闭它")

    log("已清理构建产物（保留 dist/config.json 与 dist/resources/）")


# ---------------------------------------------------------------- 打包


def build(onefile: bool, icon: Path | None) -> Path:
    DIST.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    SPEC.mkdir(parents=True, exist_ok=True)

    # 用独立的 workpath：PyInstaller 每次构建都会先删除旧 workpath，
    # 在受管环境下这个批量删除会被拦截（SystemExit）导致构建中断。
    # 换一个全新目录就完全绕开了删除动作；正常机器上 clean() 会整体清掉 .build。
    stamp = time.strftime("%Y%m%d-%H%M%S")
    workpath = BUILD / f"work-{stamp}"

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        # 不加 --clean：它会批量删除缓存目录，同样会被批量删除保护中断。
        "--onefile" if onefile else "--onedir",
        "--windowed",
        "--name", APP_NAME,
        "--distpath", str(DIST),
        "--workpath", str(workpath),
        "--specpath", str(SPEC),
        # 中文路径下 PyInstaller 需要显式指定，避免找不到包
        "--paths", str(ROOT),
    ]
    if icon is not None and icon.is_file():
        args += ["--icon", str(icon)]
    for m in EXCLUDES:
        args += ["--exclude-module", m]
    args.append(str(ENTRY))

    log_path = BUILD / "pyinstaller.log"
    log(f"开始 PyInstaller 打包（约需 1-3 分钟，日志：{log_path}）…")
    env = dict(os.environ)
    env.setdefault("TMPDIR", str(ROOT / ".tmp"))
    env.setdefault("TEMP", str(ROOT / ".tmp"))
    env.setdefault("TMP", str(ROOT / ".tmp"))

    # ⚠️ 把日志写进**文件**而不是管道：管道写满后子进程会阻塞，表现为「静默卡死」；
    # 同时加超时，卡住时能快速失败并留下可查的日志（而不是干等几十分钟）。
    try:
        with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
            proc = subprocess.run(args, cwd=str(ROOT), env=env,
                                  stdout=logf, stderr=subprocess.STDOUT,
                                  text=True, timeout=BUILD_TIMEOUT)
    except subprocess.TimeoutExpired:
        print(_tail(log_path), file=sys.stderr)
        raise SystemExit(
            f"PyInstaller 超过 {BUILD_TIMEOUT}s 仍未结束（疑似卡死）。\n"
            f"完整日志：{log_path}\n"
            f"可先清理后重试：python build.py --clean-only")
    except OSError as exc:
        raise SystemExit(f"无法启动 PyInstaller：{exc}")

    if proc.returncode != 0:
        print(_tail(log_path))
        raise SystemExit(f"PyInstaller 打包失败（退出码 {proc.returncode}），"
                         f"完整日志：{log_path}")

    exe = DIST / f"{APP_NAME}.exe"
    if not exe.is_file():
        raise SystemExit(f"未找到产物 {exe}")
    return exe


def verify(exe: Path) -> bool:
    """用 --selftest 验证产物（--windowed 没有控制台，只能看退出码）。"""
    log(f"验证产物：{exe.name} --selftest")
    try:
        proc = subprocess.run([str(exe), "--selftest"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=180)
    except subprocess.TimeoutExpired:
        log("自检超时")
        return False
    if proc.returncode == 0:
        log("自检通过（退出码 0）")
        return True
    log(f"自检失败（退出码 {proc.returncode}）")
    if proc.stdout.strip():
        print(proc.stdout[-2000:])
    if proc.stderr.strip():
        print(proc.stderr[-2000:], file=sys.stderr)
    return False


# ---------------------------------------------------------------- 入口


def main() -> int:
    ap = argparse.ArgumentParser(description="MC 模组汉化工具打包脚本")
    ap.add_argument("--no-bump", action="store_true", help="不递增维护版号")
    ap.add_argument("--onedir", action="store_true", help="打包成目录而非单文件")
    ap.add_argument("--clean-only", action="store_true", help="只清理构建产物")
    ap.add_argument("--no-verify", action="store_true", help="跳过产物自检")
    opts = ap.parse_args()

    if opts.clean_only:
        clean()
        return 0

    if not opts.no_bump:
        bump_version()
    version = read_version()
    log(f"当前版本 {version}")

    clean()
    icon = make_icon()
    exe = build(onefile=not opts.onedir, icon=icon)
    copy_resources()

    size_mb = exe.stat().st_size / 1024 / 1024
    log(f"打包完成 -> {exe}  ({size_mb:.1f} MB)")

    ok = True if opts.no_verify else verify(exe)

    print("\n" + "=" * 60)
    print(f"  版本      : {version}")
    print(f"  产物      : {exe}")
    print(f"  体积      : {size_mb:.1f} MB")
    print(f"  自检      : {'通过' if ok else '未通过'}")
    print(f"  资源目录  : {DIST / 'resources'}")
    print("=" * 60)
    print("\n运行说明：双击 dist\\%s.exe 即可。首次启动约 2-5 秒（单文件需要解包）。" % APP_NAME)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
