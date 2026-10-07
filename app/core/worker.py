# -*- coding: utf-8 -*-
"""后台翻译线程。

需求流程：读取启动器模组 → 采集英文文本 → 离线机器翻译 → 生成汉化包并置于加载顺序末尾以覆盖原文。

本模块把上述流程放进一个 :class:`QThread` 执行，避免阻塞 UI 线程。
线程与界面层的所有交互都通过信号完成，worker 自身绝不触碰任何 Qt 控件：

    progress(int, str)   百分比 + 预计剩余文案
    log(str)             过程日志
    lengzhishi(str)      每 5 分钟一条冷知识
    done(str)            全部完成提示语
    failed(str)          出错提示语

依赖：仅标准库 + PySide6。``modscan`` / ``translator`` / ``packager`` 三个模块在 ``run()``
内延迟导入，因此它们可以与本文件并行开发，且缺失时也不影响本模块的编译。
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..state import STATE


class TranslateWorker(QThread):
    """离线翻译后台线程（信号契约见 INTERFACES.md 第 2.4 节）。"""

    progress = Signal(int, str)      # percent, 预计剩余文案
    log = Signal(str)                # 过程日志
    lengzhishi = Signal(str)         # 每 5 分钟一条冷知识
    done = Signal(str)               # 完成提示语
    failed = Signal(str)             # 出错提示语

    #: 冷知识提示间隔（秒）。做成类属性，便于测试时改小。
    LENGZHISHI_INTERVAL = 300.0

    #: 每处理多少条文本刷新一次进度（避免信号过密）。
    PROGRESS_EVERY = 20

    def __init__(self, game_dir: str, version: str, mods: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.game_dir = game_dir
        self.version = version
        self.mods = list(mods or [])
        #: 取消标志。用 Event 以便跨线程安全读写。
        self._cancelled = threading.Event()
        #: 上一次推送冷知识的时间（单调时钟），由 _tick_lengzhishi 维护
        self._last_tip = time.monotonic()

    # ---------------------------------------------------------------- 对外控制

    def cancel(self) -> None:
        """请求取消：置位标志，``run()`` 会在循环内尽快退出（不再发 done）。"""
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        """是否已被请求取消。"""
        return self._cancelled.is_set()

    # ---------------------------------------------------------------- 主流程

    def run(self) -> None:
        """线程主体：读取模组 → 翻译 → 生成汉化包。异常一律转为 failed 信号。"""
        from .. import paths
        from . import modscan, packager, translator

        try:
            # --- 0) 创建汉化包根目录（.versions/汉化包）---
            root = paths.hanhuabao_root(Path(self.game_dir))
            self.log.emit("已创建汉化包目录：" + str(root))

            # --- 1) 取翻译模型 ---
            model = translator.get_model()
            if model is None:
                self.failed.emit("未选择翻译模型，请从设置选择")
                return

            # --- 1.5) 强化翻译开关：开始时快照一次，运行中改设置不影响本次任务 ---
            enhanced = bool(getattr(STATE, "enhanced_translate", False))
            if enhanced:
                self.log.emit(
                    "已启用强化翻译：译文不通顺时最多重译 "
                    f"{translator.ENHANCED_MAX_RETRIES} 次")
            enh_retried = 0      # 触发过重译的条目数
            enh_unresolved = 0   # 重译到上限仍不通顺的条目数

            # --- 2) 一次性读出所有模组的英文原文，避免重复解压 ---
            self.progress.emit(0, "正在读取模组文本…")
            collected: list[tuple[dict, dict[str, dict[str, str]]]] = []
            total = 0
            for mod in self.mods:
                if self._cancelled.is_set():
                    self.log.emit("已取消")
                    return
                entries = self._read_mod_entries(modscan, mod)
                collected.append((mod, entries))
                total += sum(len(kv) for kv in entries.values())

            done_count = 0
            t0 = time.time()
            self._last_tip = time.monotonic()

            # --- 3) 逐个模组翻译并生成汉化包 ---
            for mod, entries in collected:
                if self._cancelled.is_set():
                    self.log.emit("已取消")
                    return

                mod_name = mod.get("en_name") or mod.get("id") or "未知模组"
                # 扫描阶段就失败的模组：只记日志，不中断整体
                if mod.get("error"):
                    self.log.emit(f"{mod_name} 翻译失败：{mod['error']}")
                    self._emit_progress(done_count, total, t0)
                    continue

                translated: dict[str, dict[str, str]] = {}
                names: dict[str, dict[str, str]] = {}
                try:
                    for ns, kv in entries.items():
                        out: dict[str, str] = {}
                        for key, en in kv.items():
                            if self._cancelled.is_set():
                                self.log.emit("已取消")
                                return
                            if enhanced:
                                # 翻译 → 通顺性检查 → 不通顺则自动重译（有上限）
                                out[key], attempts, fluent = model.translate_enhanced_ex(en)
                                if attempts > 1:
                                    enh_retried += 1
                                if not fluent:
                                    enh_unresolved += 1
                            else:
                                out[key] = model.translate(en)
                            done_count += 1
                            # 每 20 条刷新一次进度（冷知识计时在 _emit_progress 内统一检查）
                            if done_count % self.PROGRESS_EVERY == 0:
                                self._emit_progress(done_count, total, t0)
                        translated[ns] = out
                        names[ns] = {
                            "cn": mod.get("cn_name") or mod_name,
                            "en": mod.get("en_name") or mod_name,
                        }
                    pack = packager.create_pack(root, self.version, mod, translated, names)
                except Exception as e:  # 单个模组失败不中断整体
                    self.log.emit(f"{mod_name} 翻译失败：{e}")
                else:
                    if not isinstance(pack, dict):
                        self.log.emit(f"{mod_name} 翻译失败：汉化包生成返回异常")
                    elif pack.get("error"):
                        self.log.emit(f"{mod_name} 翻译失败：{pack['error']}")
                    else:
                        self.log.emit(
                            f"已生成汉化包：{pack.get('name', '')}（{pack.get('count', 0)} 条）"
                        )

                self._emit_progress(done_count, total, t0)

            # --- 3.5) 强化翻译统计（让用户能看出这次重译了多少条）---
            if enhanced and (enh_retried or enh_unresolved):
                self.log.emit(
                    f"强化翻译：{enh_retried} 条触发重译，"
                    f"其中 {enh_unresolved} 条仍未达通顺阈值")

            # --- 4) 全部完成 ---
            self.progress.emit(100, "已完成")
            self.done.emit("已翻译完成，详见汉化包目录")

        except Exception as e:  # 绝不把异常抛到 Qt 线程外
            self.failed.emit(f"翻译失败：{e}")

    # ---------------------------------------------------------------- 内部工具

    @staticmethod
    def _read_mod_entries(modscan, mod: dict) -> dict[str, dict[str, str]]:
        """读取一个模组全部 lang_files 的英文条目，返回 ``{namespace: {key: en}}``。"""
        entries: dict[str, dict[str, str]] = {}
        for lf in mod.get("lang_files") or []:
            ns = lf.get("namespace") or mod.get("modid") or ""
            try:
                data = modscan.read_lang_entries(mod.get("path", ""), lf.get("entry", ""))
            except Exception:
                data = {}
            if not data:
                continue
            entries.setdefault(ns, {}).update(data)
        return entries

    def _emit_progress(self, done_count: int, total: int, t0: float) -> None:
        """按已用时间线性外推剩余时间，发出进度信号；顺带检查冷知识计时。"""
        percent = int(done_count / max(1, total) * 100)
        percent = max(0, min(100, percent))
        elapsed = time.time() - t0
        if done_count > 0 and elapsed > 0:
            remain = elapsed / done_count * max(0, total - done_count)
        else:
            remain = 0.0
        self.progress.emit(percent, self._remain_text(remain))
        self._tick_lengzhishi()

    def _tick_lengzhishi(self) -> None:
        """每满 LENGZHISHI_INTERVAL 秒推送一条冷知识。

        必须在**每一次**进度刷新时都检查：模组语言条目普遍很少（往往 <20 条），
        如果只在「每 20 条」分支里检查，跑满 5 分钟也可能一次都不触发。
        """
        now = time.monotonic()
        if now - self._last_tip >= self.LENGZHISHI_INTERVAL:
            self._last_tip = now
            tip = STATE.random_lengzhishi()
            if tip:
                self.lengzhishi.emit(tip)

    @staticmethod
    def _remain_text(seconds: float) -> str:
        """把剩余秒数转成「预计剩余 X 分 Y 秒」/「预计剩余 Z 秒」文案。"""
        sec = int(seconds + 0.5)
        if sec < 60:
            return f"预计剩余 {sec} 秒"
        minutes, sec = divmod(sec, 60)
        return f"预计剩余 {minutes} 分 {sec} 秒"
