"""跨进程安全地把一整行追加到文件末尾（trace / 决策台账这类多个 MCP 会话共写的 .jsonl）。

POSIX：`O_APPEND` 让每次 write(2) 先原子地移到文件末尾再写——多进程并发追加不会互相覆盖。

Windows：`os.open(..., O_APPEND)` / `open(path, "a")` 的 O_APPEND 是 **CRT 模拟**的——句柄拿的是普通写权限，CRT 每次写前
自己 seek 到末尾，「定位 + 写」两步之间别的进程插进来就互相盖。2026-10-31 维护机实测：8 进程 × 200 行，每轮只剩
1215–1245 / 1600 行能解析（v0.43.0 起 CI 也打脸过：4 进程 × 60 次写只剩 191/213 行）。
内核本身有原子追加：句柄**只**申请 `FILE_APPEND_DATA`（不带 `FILE_WRITE_DATA`）时，NtWriteFile 忽略偏移、每次写都落在
当前文件末尾（Rust `OpenOptions::append` 在 Windows 上就是这么开的）。同一台机器同样负载下 1600 / 1600、16 进程 ×
80–240 KB 行 960 / 960。所以 Windows 上直接用 CreateFileW + WriteFile，不加跨进程锁。
"""

from __future__ import annotations

import os
from pathlib import Path

from horosa_skill.errors import bilingual


def append_line(path: Path | str, line: bytes) -> None:
    """把 `line`（调用方保证以 b"\\n" 结尾的一整条记录）一次追加到 `path`；文件不存在就建。失败抛 OSError。"""
    if os.name == "nt":
        _append_windows(str(path), line)
        return
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        # `os.write` 可以短写：不看返回值，那一行就没有结尾的 \n，下一条记录接在它后面、两条并成一行。
        written = 0
        while written < len(line):
            written += os.write(fd, line[written:])
    finally:
        os.close(fd)


_FILE_APPEND_DATA = 0x0004
_SYNCHRONIZE = 0x00100000
_FILE_SHARE_READ_WRITE_DELETE = 0x1 | 0x2 | 0x4  # 读者（tail / memory show）与别的写者都不被挡
_OPEN_ALWAYS = 4
_FILE_ATTRIBUTE_NORMAL = 0x80


def _append_windows(path: str, line: bytes) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                     wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                                   ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.CreateFileW(path, _FILE_APPEND_DATA | _SYNCHRONIZE, _FILE_SHARE_READ_WRITE_DELETE, None,
                                  _OPEN_ALWAYS, _FILE_ATTRIBUTE_NORMAL, None)
    if handle in (None, ctypes.c_void_p(-1).value):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        # 一次 WriteFile 交整行：每次调用各自原子地落到末尾，所以绝不能拆成多次（拆开的两段之间可能插进别人的行）。
        # 同步句柄上的 WriteFile 对普通文件要么写完、要么报错；短写按错误处理，不续写半行。
        done = wintypes.DWORD(0)
        if not kernel32.WriteFile(handle, line, len(line), ctypes.byref(done), None):
            raise ctypes.WinError(ctypes.get_last_error())
        if done.value != len(line):
            raise OSError(bilingual(
                f"追加写入不完整：{path}（{done.value}/{len(line)} 字节）",
                f"short append to {path}: {done.value}/{len(line)} bytes",
            ))
    finally:
        kernel32.CloseHandle(handle)
