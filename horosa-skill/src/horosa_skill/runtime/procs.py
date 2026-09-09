"""进程存活与命令行查询（跨平台，只读，绝不发信号）。

为什么单独一个模块：端口冲突的处理要回答两个问题 —— 「占着这个端口的进程还活着吗」与
「它是谁」。两个问题在三个平台上答法完全不同，混在 manager 里会让那份已经很长的文件再难读；
更重要的是，**这里一行都不许出现杀进程的代码**：本工具对不属于自己的进程只报告、不处置
（v0.37.0 起 mac 启动器里那句按命令行子串 `kill -9` 已经被补丁掉，见 manager._patch_mac_launcher）。
"""
from __future__ import annotations

import os
import subprocess
from typing import Literal

Liveness = Literal["alive", "dead", "unknown"]

_WIN_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_WIN_SYNCHRONIZE = 0x00100000
_WIN_STILL_ACTIVE = 259
_WIN_ERROR_INVALID_PARAMETER = 87


def pid_alive(pid: object) -> Liveness:
    """`alive` / `dead` / `unknown`。绝不终止目标进程。

    POSIX：`os.kill(pid, 0)` 是标准的空探针。
    Windows：**决不能**用 os.kill —— 它在 Windows 上没有「信号 0」语义，对任何非 CTRL 信号都
    直接调 TerminateProcess，也就是会把目标**杀掉**而不是探测。改用 ctypes 的 OpenProcess +
    GetExitCodeProcess（只要 PROCESS_QUERY_LIMITED_INFORMATION 权限，Vista 起就有）。这比旧的
    「Windows 一律 unknown、只能按时长回收锁」严格：崩溃留下的锁在 Windows 上也能立刻回收。
    """
    if not isinstance(pid, int) or pid <= 0:
        return "unknown"
    if os.name == "nt":
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "dead"
    except PermissionError:
        return "alive"  # 存在，只是属于别的用户
    except OSError:
        return "unknown"
    return "alive"


def _pid_alive_windows(pid: int) -> Liveness:
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:  # noqa: BLE001 - 拿不到 ctypes 就老实说不知道
        return "unknown"
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        handle = kernel32.OpenProcess(
            _WIN_PROCESS_QUERY_LIMITED_INFORMATION | _WIN_SYNCHRONIZE, False, pid
        )
        if not handle:
            err = ctypes.get_last_error()
            if err == _WIN_ERROR_INVALID_PARAMETER:
                return "dead"          # 没有这个 pid
            return "unknown"           # ACCESS_DENIED 等：存在与否无法断言
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return "unknown"
            return "alive" if code.value == _WIN_STILL_ACTIVE else "dead"
        finally:
            kernel32.CloseHandle(handle)
    except Exception:  # noqa: BLE001
        return "unknown"


def process_command(pid: object) -> str | None:
    """进程的完整命令行；取不到返回 None。只读，超时即放弃。"""
    if not isinstance(pid, int) or pid <= 0:
        return None
    if os.name == "nt":
        cmd = [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine",
        ]
    else:
        cmd = ["ps", "-o", "command=", "-p", str(pid)]
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=4.0, check=False,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = (out.stdout or "").strip()
    return text or None
