"""进程存活、映像路径与命令行查询（跨平台，只读，绝不发信号）。

为什么单独一个模块：端口冲突的处理要回答两个问题 —— 「占着这个端口的进程还活着吗」与
「它是谁」。两个问题在三个平台上答法完全不同，混在 manager 里会让那份已经很长的文件再难读；
更重要的是，**这里一行都不许出现杀进程的代码**：本工具对不属于自己的进程只报告、不处置
（v0.37.0 起 mac 启动器里那句按命令行子串 `kill -9` 已经被补丁掉，见 manager._patch_mac_launcher）。

🔴 Windows 上的「它是谁」有三级答法，按**不经代码页**的程度排序（v0.38.1）：
  1. `process_image_path()` —— ctypes `QueryFullProcessImageNameW`，无子进程、无编码问题。
     载荷的 python.exe / java.exe 就住在 `<runtime_root>/current/runtime/windows/…` 下，映像路径
     本身就是最强的归属证据。
  2. `process_command()` 的 PowerShell 路 —— 让 PowerShell 把命令行**以 UTF-8 字节的 base64** 吐出来，
     Python 侧解码。此前直接读它的文本输出并按 UTF-8 解：Windows PowerShell 5.1 往管道写的是 **OEM
     代码页**（en-US 是 cp437，zh-CN 是 cp936），`C:\\Users\\张三\\…` 回来要么是 `????` 要么是被 UTF-8
     解坏的 GBK 字节 —— 与 Python 侧的 Unicode 路径做子串比对永远不等，于是用户名带中文/重音的
     **健康**机器被判成 `port_conflict_foreign` / `stop_refused_foreign`。
  3. `tasklist` 退路只有映像名，按 `oem` 解码，够在报错里点名。
"""
from __future__ import annotations

import base64
import os
import subprocess
from typing import Literal

from horosa_skill.runtime import budget

Liveness = Literal["alive", "dead", "unknown"]

_WIN_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_WIN_SYNCHRONIZE = 0x00100000
_WIN_STILL_ACTIVE = 259
_WIN_ERROR_INVALID_PARAMETER = 87

# PowerShell 冷启动在 CI runner / 装了安全软件的机器上常常 3–6 s；8 s 够它，也不至于让 doctor 卡死。
POWERSHELL_TIMEOUT_SECONDS = 8.0
TASKLIST_TIMEOUT_SECONDS = 5.0
PS_TIMEOUT_SECONDS = 4.0


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


def _kernel32():
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    return ctypes, wintypes, kernel32


def _pid_alive_windows(pid: int) -> Liveness:
    try:
        ctypes, wintypes, kernel32 = _kernel32()
    except Exception:  # noqa: BLE001 - 拿不到 ctypes 就老实说不知道
        return "unknown"
    try:
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


def process_image_path(pid: object) -> str | None:
    """进程可执行文件的完整路径；取不到返回 None。

    Windows 走 ctypes `QueryFullProcessImageNameW`：不起子进程、不经任何代码页，路径里的中文/重音
    原样回来。这是归属判定在 Windows 上的**首选**证据（映像在 runtime 根下 = 我们的）。
    POSIX 上返回 None —— 那边 `ps -o command=` 本来就是 UTF-8，`process_command` 足够。
    """
    if not isinstance(pid, int) or pid <= 0 or os.name != "nt":
        return None
    try:
        ctypes, wintypes, kernel32 = _kernel32()
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        )
        handle = kernel32.OpenProcess(_WIN_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            size = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return None
            return buffer.value[: size.value] or None
        finally:
            kernel32.CloseHandle(handle)
    except Exception:  # noqa: BLE001 - 查不到就查不到，绝不抛到归属判定里
        return None


def _run_text(cmd: list[str], timeout: float, *, encoding: str = "utf-8") -> str:
    clamped = budget.clamp(timeout, cmd[0])
    if clamped is None:
        return ""
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=clamped, check=False,
            encoding=encoding, errors="replace",
        )
    except (OSError, subprocess.SubprocessError, LookupError):
        return ""
    return (out.stdout or "").strip()


def _powershell_command_line(pid: int) -> str | None:
    """PowerShell 只负责搬运**字节**：命令行 → UTF-8 → base64 → 我们这边解码。控制台代码页管不着它。"""
    script = (
        f"$c=(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine; "
        "if($c){[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes([string]$c))}"
    )
    encoded = _run_text(
        ["powershell", "-NoProfile", "-NonInteractive", "-NoLogo", "-Command", script],
        POWERSHELL_TIMEOUT_SECONDS,
        encoding="ascii",
    )
    if not encoded:
        return None
    try:
        return base64.b64decode(encoded, validate=False).decode("utf-8", errors="replace").strip() or None
    except (ValueError, UnicodeDecodeError):
        return None


def _tasklist_image_name(pid: int) -> str | None:
    """退路：映像名不含参数，但足以在「端口被谁占着」的报错里点名。`tasklist` 写的是 OEM 代码页。"""
    rows = _run_text(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], TASKLIST_TIMEOUT_SECONDS, encoding="oem"
    )
    for row in rows.splitlines():
        parts = [item.strip('"') for item in row.split('","')]
        if len(parts) >= 2 and parts[1].strip('"') == str(pid):
            return parts[0].strip('"') or None
    return None


def process_command(pid: object) -> str | None:
    """进程的完整命令行；取不到返回 None。只读，超时即放弃。

    Windows 上依次：PowerShell（base64 搬字节，见模块说明）→ `tasklist` 映像名。
    🔴 历史：v0.37.0 前这条**恒返回空**（4 s 超时短于 PowerShell 冷启动），v0.38.0 前按 UTF-8 解
    OEM 代码页的输出（非 ASCII 路径全部错判）。两次都让归属判定的第二级证据整个失效。
    """
    if not isinstance(pid, int) or pid <= 0:
        return None
    if os.name != "nt":
        return _run_text(["ps", "-o", "command=", "-p", str(pid)], PS_TIMEOUT_SECONDS) or None
    return _powershell_command_line(pid) or _tasklist_image_name(pid)
