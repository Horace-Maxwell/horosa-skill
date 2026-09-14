"""诊断命令的整体时间预算（v0.38.1 A2）。

🔴 为什么需要它：`doctor` / `runtime status` 里每个子进程探针各自有 5–15 s 的超时，单看都合理，
加起来却没人管 —— Windows 上最坏路径（两个端口 × 两个地址族的 netstat + 每个持有者一次
PowerShell + tasklist + uv/node 探针）实测可达 ~165 s，而 MCP 客户端 60 s 就掐工具。
用户看到的症状是「doctor 挂了」，恰恰出现在他最需要它的时候。

用法：外层 `with scope(25.0) as b:`；每个会起子进程的地方用 `clamp(timeout, label)` 把自己的
超时压到剩余预算之内，预算耗尽返回 None（调用方按「查不到」处理，并被记进 `b.skipped`）。
`timed(label)` 记录各阶段耗时进 `b.timings`。没有外层 scope 时一切照旧（clamp 原样返回 timeout）。
"""
from __future__ import annotations

import contextvars
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class Budget:
    seconds: float
    started: float
    timings: dict[str, float] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)

    @property
    def remaining(self) -> float:
        return self.seconds - (time.monotonic() - self.started)

    def as_dict(self) -> dict[str, Any]:
        return {
            "seconds": self.seconds,
            "elapsed": round(time.monotonic() - self.started, 2),
            "timings": {k: round(v, 2) for k, v in self.timings.items()},
            "skipped": list(self.skipped),
        }


_CURRENT: contextvars.ContextVar[Budget | None] = contextvars.ContextVar("horosa_budget", default=None)


def current() -> Budget | None:
    return _CURRENT.get()


@contextmanager
def scope(seconds: float) -> Iterator[Budget]:
    budget = Budget(seconds=float(seconds), started=time.monotonic())
    token = _CURRENT.set(budget)
    try:
        yield budget
    finally:
        _CURRENT.reset(token)


def clamp(timeout: float, label: str) -> float | None:
    """把一次子进程调用的超时压进剩余预算。None = 预算已尽，别再起进程了。"""
    budget = _CURRENT.get()
    if budget is None:
        return timeout
    remaining = budget.remaining
    if remaining <= 0.05:
        if label not in budget.skipped:
            budget.skipped.append(label)
        return None
    return min(timeout, remaining)


@contextmanager
def timed(label: str) -> Iterator[None]:
    budget = _CURRENT.get()
    started = time.monotonic()
    try:
        yield
    finally:
        if budget is not None:
            budget.timings[label] = budget.timings.get(label, 0.0) + (time.monotonic() - started)
