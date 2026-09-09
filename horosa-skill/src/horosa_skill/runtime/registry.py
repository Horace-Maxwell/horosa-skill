"""运行时状态文件的原子读写与并发安全更新。

🔴 为什么必须原子：`runtime-state.json` 旧实现是一次 `write_text` —— 两个进程同时冷启动时，
读者会读到写了一半的 JSON（`json.JSONDecodeError` → `load_runtime_state` 静默返回 None →
调用方以为「没在跑」→ 再起一次），而写者互相覆盖，最后文件里记的是**输的那一方**的 pid。
写临时文件再 `os.replace` 是 POSIX 与 Windows 上都原子的重命名；读改写整体持一把短锁。

schema v2 在 v1 的全部键之上补：mode / ports / endpoints / launch_nonce / launcher / service_pids /
clients。老状态文件（无 schema_version）读出来照样能用，缺的键按缺省补齐 —— 升级不能让用户的
「正在跑」变成「没在跑」。
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from horosa_skill.runtime.pidlock import pid_lock

SCHEMA_VERSION = 2
_LOCK_SUFFIX = ".write.lock"
_V2_DEFAULTS: dict[str, Any] = {
    "mode": None,            # "managed" | "external" | None
    "ports": {},             # {"backend": 9999, "chart": 8899}
    "endpoints": [],         # _service_status 的最后一份快照（含 identity）
    "launch_nonce": None,    # 交给启动器的一次性身份口令
    "launcher": {},          # {"pid":…, "log":…, "started_at":…}
    "service_pids": [],      # 我方起的服务进程 pid（尽力而为）
    "clients": {},           # {pid: {"transport":…, "since":…, "last_call_at":…}}
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_state(path: Path) -> dict[str, Any] | None:
    """读状态文件。不存在 / 坏掉 / 不是对象 → None。缺的 v2 键按缺省补齐。"""
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    return _with_defaults(payload)


def _with_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(payload)
    merged.setdefault("schema_version", 1)
    for key, default in _V2_DEFAULTS.items():
        merged.setdefault(key, json.loads(json.dumps(default)))
    return merged


def write_state(path: Path, payload: dict[str, Any]) -> None:
    """整份覆盖写，原子。中途失败不留残片（临时文件与目标同目录，保证同一文件系统）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["schema_version"] = SCHEMA_VERSION
    body.setdefault("updated_at", utc_now())
    text = json.dumps(body, ensure_ascii=False, indent=2) + "\n"
    # 🔴 全程用 str，不要 `Path(tmp_name)` 再 `str()` 转一圈：`pathlib.Path` 是在 `os.name` 上
    # 决定 PosixPath / WindowsPath 的，而这份代码会在把 os.name 打成 "nt" 的 Windows 模拟测试里
    # 跑到 —— 转一圈的结果是 macOS 上拿到一个反斜杠路径，os.replace 直接 FileNotFoundError。
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".runtime-state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, str(path))
    except BaseException:
        # os.replace 抛错时临时文件还在 —— 必须清掉，否则 runtime 根下会攒满 .tmp 残片。
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def update_state(
    path: Path,
    mutate: Callable[[dict[str, Any]], dict[str, Any] | None],
    *,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """读-改-写，整体持锁。`mutate` 原地改并可返回新字典；返回落盘后的状态。

    拿不到锁时**不放弃写入**：状态文件比锁更重要，超时后直接原子覆盖（最坏结果是与另一个
    写者竞争最后一次 replace，而 replace 本身是原子的，不会产生半个文件）。
    """
    lock_path = path.with_name(path.name + _LOCK_SUFFIX)
    try:
        with pid_lock(lock_path, timeout_seconds=timeout_seconds, stale_after_seconds=120.0,
                      owner="runtime-state"):
            return _apply(path, mutate)
    except TimeoutError:
        return _apply(path, mutate)


def _apply(path: Path, mutate: Callable[[dict[str, Any]], dict[str, Any] | None]) -> dict[str, Any]:
    current = read_state(path) or _with_defaults({})
    result = mutate(current)
    payload = result if isinstance(result, dict) else current
    payload["updated_at"] = utc_now()
    write_state(path, payload)
    return payload


def clear_state(path: Path) -> None:
    path.unlink(missing_ok=True)
    path.with_name(path.name + _LOCK_SUFFIX).unlink(missing_ok=True)


def attach_client(path: Path, *, pid: int, transport: str) -> dict[str, Any]:
    """登记一个挂在这份 runtime 上的客户端（`serve` 起来时调）。"""
    def _mutate(state: dict[str, Any]) -> dict[str, Any]:
        clients = dict(state.get("clients") or {})
        clients[str(pid)] = {"transport": transport, "since": utc_now(), "last_call_at": None}
        state["clients"] = clients
        return state
    return update_state(path, _mutate)


def detach_client(path: Path, *, pid: int) -> dict[str, Any]:
    def _mutate(state: dict[str, Any]) -> dict[str, Any]:
        clients = dict(state.get("clients") or {})
        clients.pop(str(pid), None)
        state["clients"] = clients
        return state
    return update_state(path, _mutate)


def live_clients(state: dict[str, Any] | None, *, exclude_pid: int | None = None) -> dict[str, Any]:
    """状态里登记过、且**进程仍存活**的客户端。死掉的登记不算数（崩溃的客户端不该拦住 stop）。"""
    from horosa_skill.runtime.procs import pid_alive

    result: dict[str, Any] = {}
    for raw_pid, info in ((state or {}).get("clients") or {}).items():
        try:
            pid = int(raw_pid)
        except (TypeError, ValueError):
            continue
        if exclude_pid is not None and pid == exclude_pid:
            continue
        if pid_alive(pid) == "alive":
            result[str(pid)] = info
    return result
