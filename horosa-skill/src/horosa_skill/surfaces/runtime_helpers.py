"""CLI 与 setup 流程共用的三件小事：取 runtime manager、源码树里 horosa-skill 包目录、下载进度打印到 stderr。测试替换 manager 或包目录就 patch 这里（一个 patch 点覆盖全部调用方）。"""
from __future__ import annotations

import sys
from pathlib import Path

from horosa_skill.config import Settings
from horosa_skill.runtime import HorosaRuntimeManager


def _runtime_manager(settings: Settings | None = None) -> HorosaRuntimeManager:
    return HorosaRuntimeManager(settings or Settings.from_env())


def _package_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _install_progress_printer():
    """stderr 下载进度（stdout 保持纯 JSON 契约）：TTY 用行内百分比，非 TTY 每 ~50MB 一行。"""
    state = {"last": 0}
    is_tty = sys.stderr.isatty()

    def _progress(done: int, total: int | None) -> None:
        if is_tty:
            if total:
                pct = done * 100 // total
                sys.stderr.write(f"\r下载 runtime：{done // (1024*1024)}MB / {total // (1024*1024)}MB（{pct}%）")
            else:
                sys.stderr.write(f"\r下载 runtime：{done // (1024*1024)}MB")
            sys.stderr.flush()
            if total and done >= total:
                sys.stderr.write("\n")
        else:
            if done - state["last"] >= 50 * 1024 * 1024:
                state["last"] = done
                suffix = f" / {total // (1024*1024)}MB" if total else ""
                sys.stderr.write(f"下载 runtime：{done // (1024*1024)}MB{suffix}\n")
                sys.stderr.flush()

    return _progress
