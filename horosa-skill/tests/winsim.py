"""在 macOS / Linux 上模拟 Windows 的文件共享规则（v0.50.1-dev，main CI windows-smoke 红 13 条之后）。

Windows 上**打开着**的文件不能改名、不能删：SQLite 与 Python 的 `open()` 打开文件时都不带 `FILE_SHARE_DELETE`，
`os.replace` / `os.unlink` 撞上就是 `PermissionError: [WinError 32]`；含打开文件的目录同样删不掉、挪不动。
POSIX 没有这条规则：连接没关就去隔离坏库、删 `-shm`，本机照样绿，Windows 用户那边坏库永远隔离不了。

`windows_sharing(monkeypatch)` 把 `os.replace / rename / unlink / remove / rmdir` 换成「先看本进程有没有开着这个路径
（或它下面的文件），开着就按 Windows 那样拒绝」。只认本进程的文件描述符（SQLite 的 -wal / -shm 也是描述符），
够抓「自己忘了关连接」这一类。tests/conftest.py 让**每条用例**都在它下面跑（`posix_file_semantics` 标记的除外：
那是 Windows 上本就跳过、专测 POSIX 语义的用例）。Windows 上不装（真规则在生效）；拿不到描述符路径的平台也不装。

例外：`tempfile` 模块自己「开着就删」——那是 TemporaryFile 的 POSIX 写法，Windows 上走的是另一条（O_TEMPORARY），不会这么删。
"""
from __future__ import annotations

import errno
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

WINERROR_SHARING_VIOLATION = 32


def _fd_path(fd: int) -> str | None:
    try:
        if sys.platform == "darwin":
            import fcntl

            raw = fcntl.fcntl(fd, fcntl.F_GETPATH, bytes(1024))
            return os.fsdecode(raw.split(b"\0", 1)[0]) or None
        target = os.readlink(f"/proc/self/fd/{fd}")
        return target if target.startswith("/") else None
    except OSError:
        return None


def supported() -> bool:
    return sys.platform == "darwin" or Path("/proc/self/fd").is_dir()


def open_paths() -> set[str]:
    """本进程此刻开着的文件（规范化的绝对路径）。"""
    listing = "/dev/fd" if sys.platform == "darwin" else "/proc/self/fd"
    paths: set[str] = set()
    for name in os.listdir(listing):
        if name.isdigit() and (path := _fd_path(int(name))):
            paths.add(os.path.realpath(path))
    return paths


def holders(path: Any) -> list[str]:
    """开着的、等于 `path` 或在 `path` 之下的文件。"""
    target = os.path.realpath(os.fspath(path))
    prefix = target.rstrip(os.sep) + os.sep
    return sorted(p for p in open_paths() if p == target or p.startswith(prefix))


def active() -> bool:
    """这台机器上模拟能不能装（Windows 上不需要，真规则在生效）。"""
    return os.name != "nt" and supported()


def windows_sharing(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """装上模拟；返回一个列表，每次被拒绝都记一条（测试可以断言它为空，也可以看拒绝了什么）。已经装过就返回同一个列表。"""
    existing = getattr(os.replace, "_winsim_refused", None)
    if existing is not None:
        return existing
    refused: list[str] = []
    if not active():
        return refused

    def guard(real: Callable[..., Any], name: str, arity: int) -> Callable[..., Any]:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            if sys._getframe(1).f_globals.get("__name__") == "tempfile":
                return real(*args, **kwargs)
            for path in args[:arity]:
                if isinstance(path, int):
                    continue
                held = holders(path)
                if held:
                    refused.append(f"{name}({os.fspath(path)}) while open: {held}")
                    error = PermissionError(
                        errno.EACCES,
                        "[WinError 32] The process cannot access the file because it is being used by another process "
                        "(simulated by tests/winsim.py)",
                        os.fspath(path),
                    )
                    error.winerror = WINERROR_SHARING_VIOLATION  # type: ignore[attr-defined]
                    raise error
            return real(*args, **kwargs)

        wrapped._winsim_refused = refused  # type: ignore[attr-defined]
        return wrapped

    for name, arity in (("replace", 2), ("rename", 2), ("unlink", 1), ("remove", 1), ("rmdir", 1)):
        monkeypatch.setattr(os, name, guard(getattr(os, name), name, arity))
    return refused


__all__ = ["active", "holders", "open_paths", "supported", "windows_sharing"]
