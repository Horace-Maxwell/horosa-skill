"""基准/自检任务的互斥锁 —— 现在是 `runtime.pidlock` 的薄包装。

保留这个模块名与签名是为了不动既有调用点与测试；实现（O_EXCL 创建、活持有者永不回收、
死持有者立刻回收、损坏/无法判定时按时长兜底）统一到 `runtime/pidlock.py`，那里同时服务于
运行时启动锁。合并顺带修好一处：Windows 上的存活判定从「一律 unknown、只能等满时长」
升级为 ctypes OpenProcess，崩溃留下的锁在 Windows 上也能立刻回收（仍然**不**调 os.kill —— 它
在 Windows 上没有信号 0 语义，会把目标杀掉）。
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from horosa_skill.config import Settings
from horosa_skill.runtime.pidlock import pid_lock


@contextmanager
def acquire_evaluation_lock(
    settings: Settings,
    *,
    timeout_seconds: float = 60.0,
    stale_after_seconds: float = 3600.0,
) -> Iterator[Path]:
    """Prevent concurrent benchmark/self-check jobs from racing the shared local runtime.

    Recovers a stale lock left behind by a crashed / `kill -9`'d / OOM-killed run — otherwise the
    lock file would persist forever and every future evaluation would stall for ``timeout_seconds``
    and then fail until someone manually deleted it. A *live* owner is never reclaimed, so a
    legitimately long-running evaluation is always respected.
    """
    with pid_lock(
        settings.runtime_root / ".evaluation.lock",
        timeout_seconds=timeout_seconds,
        stale_after_seconds=stale_after_seconds,
        owner="evaluation",
    ) as path:
        yield path
