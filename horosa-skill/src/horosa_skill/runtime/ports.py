"""端口占用查询：谁在监听、还能不能绑。纯只读，不杀任何进程。

三个平台各一条路，都**不依赖 lsof**：macOS 上 lsof 对别的用户的进程要 root，装了安全软件的
机器上还常常挂住十几秒，而 `netstat -anv -p tcp` 是系统自带、无权限门槛、格式稳定的。
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
from typing import Any

# macOS `netstat -anv -p tcp` 的 process:pid 列，例如 `python3.12:6123`、`java:88104`。
# 本地地址列用点分端口（`*.8899` / `127.0.0.1.8899` / `::1.8899`），不会误命中这条正则。
_MAC_PROCESS_PID = re.compile(r"^(?P<name>[^\s:]+):(?P<pid>\d+)$")
# Linux `ss -lntpH` 的 users:(("java",pid=1234,fd=7))
_SS_PID = re.compile(r"pid=(\d+)")
# Windows `netstat -ano` 的 LISTENING 行，末列是 pid
_WIN_LISTEN = re.compile(r"^\s*TCP\s+(?P<local>\S+)\s+\S+\s+LISTENING\s+(?P<pid>\d+)\s*$", re.I)


# 15 s，不是 5 s：托管 macOS runner 在全量 pytest 的负载下 `netstat -anv` 曾超过 5 s → 返回空串 → `listener_pids` 空 →
# 「端口上明明有监听进程，却一个持有者都查不出来」（v0.38.0 A5 矩阵首跑）；同一教训 v0.37.0 在 Windows 的
# `process_command`（PowerShell 冷启动 > 4 s）上踩过一次。
def _run(cmd: list[str], timeout: float = 15.0) -> str:
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout or ""


def listener_pids(port: int) -> list[int]:
    """在 `port` 上监听的进程 PID。查不到（无权限 / 工具缺席 / 平台不支持）返回空列表。

    🔴 空列表**只表示查不到**，绝不能被读成「端口空着」—— 端口是否可用要问 `port_bindable`。
    把「查不到持有者」当成「没人持有」正是「静默采用一个陌生后端」那类事故的起点。
    """
    if os.name == "nt":
        return _listener_pids_windows(port)
    if _uname() == "darwin":
        return _listener_pids_darwin(port)
    return _listener_pids_linux(port)


def _uname() -> str:
    try:
        return os.uname().sysname.lower()  # type: ignore[attr-defined]
    except AttributeError:
        return ""


def _listener_pids_darwin(port: int) -> list[int]:
    pids: list[int] = []
    suffix = f".{port}"
    for line in _run(["netstat", "-anv", "-p", "tcp"]).splitlines():
        if "LISTEN" not in line:
            continue
        fields = line.split()
        if not any(f.endswith(suffix) for f in fields[:4]):
            continue
        for field in fields:
            m = _MAC_PROCESS_PID.match(field)
            if m:
                pids.append(int(m.group("pid")))
                break
    return sorted(set(pids))


def _listener_pids_linux(port: int) -> list[int]:
    text = _run(["ss", "-lntpH"]) or _run(["ss", "-lntp"])
    pids: list[int] = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        if not any(f.rsplit(":", 1)[-1] == str(port) for f in fields[:5]):
            continue
        pids.extend(int(p) for p in _SS_PID.findall(line))
    return sorted(set(pids))


def _listener_pids_windows(port: int) -> list[int]:
    pids: list[int] = []
    for line in _run(["netstat", "-ano", "-p", "TCP"]).splitlines():
        m = _WIN_LISTEN.match(line)
        if not m:
            continue
        if m.group("local").rsplit(":", 1)[-1] != str(port):
            continue
        pids.append(int(m.group("pid")))
    return sorted(set(pids))


# --- listener scope: which interfaces a listener is bound to (v0.38.0 B1) ---------------------
# The Windows launcher used to start Java without --server.address, i.e. on 0.0.0.0: a Firewall prompt
# on first start and a backend reachable from the LAN. doctor reports the bound addresses so an
# already-installed runtime that still runs the old template is visible instead of silent.

_LOOPBACK_ADDRESSES = {"127.0.0.1", "::1", "localhost"}


def listener_bindings(port: int) -> list[dict[str, Any]]:
    """`[{"local_address": "0.0.0.0", "pid": 1234}, …]` for every LISTEN socket on `port`.

    Empty means **could not tell** (tool missing / no permission), never "nothing listens" —
    same discipline as `listener_pids`. Addresses are reported as printed by the OS tool with
    brackets stripped (`0.0.0.0`, `127.0.0.1`, `::`, `::1`, `*`).
    """
    if os.name == "nt":
        return _bindings_windows(port)
    if _uname() == "darwin":
        return _bindings_darwin(port)
    return _bindings_linux(port)


def loopback_only(bindings: list[dict[str, Any]]) -> bool | None:
    """True = every binding is a loopback address; False = at least one wildcard/LAN address; None = unknown."""
    if not bindings:
        return None
    return all(str(entry.get("local_address")) in _LOOPBACK_ADDRESSES for entry in bindings)


def _bindings_windows(port: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    # `-p TCP` lists IPv4 only; a dual-stack Java listener shows up under TCPv6 as [::]:port.
    for proto in ("TCP", "TCPv6"):
        for line in _run(["netstat", "-ano", "-p", proto]).splitlines():
            m = _WIN_LISTEN.match(line)
            if not m:
                continue
            host, _, local_port = m.group("local").rpartition(":")
            if local_port != str(port):
                continue
            out.append({"local_address": host.strip("[]"), "pid": int(m.group("pid"))})
    return out


def _bindings_darwin(port: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in _run(["netstat", "-anv", "-p", "tcp"]).splitlines():
        if "LISTEN" not in line:
            continue
        fields = line.split()
        if len(fields) < 4:
            continue
        host, _, local_port = fields[3].rpartition(".")
        if local_port != str(port):
            continue
        pid = None
        for field in fields:
            m = _MAC_PROCESS_PID.match(field)
            if m:
                pid = int(m.group("pid"))
                break
        out.append({"local_address": host, "pid": pid})
    return out


def _bindings_linux(port: int) -> list[dict[str, Any]]:
    text = _run(["ss", "-lntpH"]) or _run(["ss", "-lntp"])
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        local = fields[3] if fields[0] in {"LISTEN", "tcp"} or ":" in fields[3] else fields[2]
        host, _, local_port = local.rpartition(":")
        if local_port != str(port):
            continue
        pids = [int(p) for p in _SS_PID.findall(line)]
        out.append({"local_address": host.strip("[]"), "pid": pids[0] if pids else None})
    return out


def port_bindable(port: int, host: str = "127.0.0.1") -> bool:
    """这个端口现在还能绑吗。**不设 SO_REUSEADDR** —— 那会让已被监听的端口在某些平台上也报可绑。"""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
        return True
    except OSError:
        return False


def find_free_port(preferred: int, *, span: int = 100, host: str = "127.0.0.1") -> int:
    """从 `preferred` 起向上找一个能绑的端口；`span` 个都不行就交给内核选（返回 ephemeral）。"""
    for candidate in range(preferred, preferred + max(span, 1)):
        if 0 < candidate < 65536 and port_bindable(candidate, host):
            return candidate
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def port_holders(port: int) -> list[dict[str, Any]]:
    """端口持有者的 {pid, command} 列表（尽力而为，用于错误信息里点名）。"""
    from horosa_skill.runtime.procs import process_command

    return [{"pid": pid, "command": process_command(pid)} for pid in listener_pids(port)]
