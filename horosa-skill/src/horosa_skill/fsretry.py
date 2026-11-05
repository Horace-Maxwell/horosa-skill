"""Windows 上「别的进程正开着这个文件」的瞬时失败：短暂重试，别把它当真错误。

Python 的 `open()` 不带 FILE_SHARE_DELETE，所以只要有人正读着目标：`os.replace` / `unlink` 抛 PermissionError（WinError 5 / 32），
而替换进行中的读也可能 PermissionError。POSIX 没有这回事（替换的是目录项，读者继续读旧 inode）。

2026-11-05 维护机实测（10 进程 15 秒写读同一份 runtime-state.json）：87% 的写抛 PermissionError、11.5% 的读返回「没有状态」——调用方当成
runtime 没在跑；锁文件 unlink 失败更糟，异常从 finally 冒出去、锁留在盘上（持有者还活着，别人只能等满超时）。
只重试共享冲突（5 / 32 / 33），预算默认 2 秒；真拿不到（比如文件开在 Acrobat 里）照常抛，调用方决定怎么办。
"""

from __future__ import annotations

import errno
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

_T = TypeVar("_T")
_SHARING_WINERRORS = frozenset({5, 32, 33})  # ACCESS_DENIED（删除待决 / 目标开着）、SHARING_VIOLATION、LOCK_VIOLATION
DEFAULT_BUDGET_SECONDS = 2.0


def _on_windows() -> bool:
    return os.name == "nt"


def is_sharing_violation(exc: BaseException) -> bool:
    if not isinstance(exc, PermissionError) or not _on_windows():
        return False
    winerror = getattr(exc, "winerror", None)
    # `open()` 走 CRT，失败只带 errno 13、winerror 是 None；os.replace / unlink 才带 winerror。
    return winerror in _SHARING_WINERRORS or (winerror is None and exc.errno == errno.EACCES)


def _retrying(operation: Callable[[], _T], budget_seconds: float) -> _T:
    deadline = time.monotonic() + budget_seconds
    delay = 0.002
    while True:
        try:
            return operation()
        except PermissionError as exc:
            if not is_sharing_violation(exc) or time.monotonic() >= deadline:
                raise
        time.sleep(delay)
        delay = min(delay * 2, 0.05)


def replace(src: str | Path, dst: str | Path, *, budget_seconds: float = DEFAULT_BUDGET_SECONDS) -> None:
    """`os.replace`，碰到共享冲突短暂重试。"""
    _retrying(lambda: os.replace(src, dst), budget_seconds)


def unlink(path: str | Path, *, budget_seconds: float = DEFAULT_BUDGET_SECONDS) -> None:
    """删文件；不存在不算错，共享冲突短暂重试。"""

    def _unlink() -> None:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    _retrying(_unlink, budget_seconds)


def read_text(path: str | Path, *, budget_seconds: float = DEFAULT_BUDGET_SECONDS) -> str:
    """读 UTF-8 文本，碰到「正被替换」的共享冲突短暂重试。"""
    return _retrying(lambda: Path(path).read_text(encoding="utf-8"), budget_seconds)
