"""跨进程互斥锁：O_EXCL 创建 + PID 存活回收 + 过期兜底。

🔴 为什么需要它：`start_local_services` 只有一把**进程内**的 `threading.Lock`。两个 MCP
客户端（Claude Desktop 与 Cursor，或者一个 serve 与一次 `doctor`）同时冷启动时，两边各起一次
启动器：抢同一个端口、互相覆盖 pid 文件、后到的那个看见「pid files already exist」于是先
stop 再 start —— 把先到的那个刚起好的服务停掉。这把锁让**恰好一个**进程去启动，其余的只轮询
就绪状态。

从 `evaluation_lock.py` 泛化而来（那边保留为薄包装，四个旧测试不动），两处升级：
  · 存活判定走 `runtime.procs.pid_alive`，Windows 也能立刻回收崩溃留下的锁（旧实现在 Windows
    上一律 unknown，只能等满 stale 时长）；
  · 锁文件里多记 `owner` 与 `created_at`，`describe_lock()` 让 `runtime status` 能说出「谁在启动」。
"""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from horosa_skill.runtime.procs import pid_alive


@contextmanager
def pid_lock(
    lock_path: Path,
    *,
    timeout_seconds: float = 60.0,
    stale_after_seconds: float = 3600.0,
    owner: str = "",
) -> Iterator[Path]:
    """持有 `lock_path` 直到退出。拿不到就等，超时抛 TimeoutError。"""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    while True:
        if _try_create(lock_path, owner=owner):
            break
        if reclaim_if_stale(lock_path, stale_after_seconds=stale_after_seconds):
            continue
        if time.monotonic() - started >= timeout_seconds:
            holder = describe_lock(lock_path)
            raise TimeoutError(
                f"Timed out waiting for lock {lock_path} (holder={holder})"
            )
        time.sleep(0.2)
    try:
        yield lock_path
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def try_pid_lock(lock_path: Path, *, stale_after_seconds: float = 3600.0, owner: str = "") -> bool:
    """非阻塞地试一次。True = 拿到了（调用方负责 `release`）。"""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if _try_create(lock_path, owner=owner):
        return True
    if reclaim_if_stale(lock_path, stale_after_seconds=stale_after_seconds):
        return _try_create(lock_path, owner=owner)
    return False


def release(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except (FileNotFoundError, OSError):
        pass


def _try_create(lock_path: Path, *, owner: str) -> bool:
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except OSError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "pid": os.getpid(),
                "owner": owner,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            handle,
            ensure_ascii=False,
        )
    return True


def describe_lock(lock_path: Path) -> dict[str, Any] | None:
    """锁当前持有者（供 `runtime status` 显示）。锁不存在返回 None。"""
    info = _read_lock(lock_path)
    if info is None:
        return None
    pid = info.get("pid")
    return {
        "pid": pid,
        "owner": info.get("owner") or None,
        "created_at": info.get("created_at"),
        "liveness": pid_alive(pid),
        "age_seconds": _age_seconds(info.get("created_at"), lock_path),
    }


def reclaim_if_stale(lock_path: Path, *, stale_after_seconds: float) -> bool:
    """持有者已死或锁太老就删掉它。True = 已删/本就不存在，调用方可以重试创建。

    **活着的持有者永远不回收**，不论多老 —— 一次合法的长启动（首次 CDS 训练可达 15 分钟）
    必须被尊重。
    """
    info = _read_lock(lock_path)
    if info is None:
        return not lock_path.exists()
    liveness = pid_alive(info.get("pid"))
    if liveness == "alive":
        return False
    if liveness == "dead":
        stale = True
    else:  # unknown：无法断言存活 → 退回按时长
        age = _age_seconds(info.get("created_at"), lock_path)
        stale = age is not None and age >= stale_after_seconds
    if not stale:
        return False
    try:
        lock_path.unlink()
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def _read_lock(lock_path: Path) -> dict[str, Any] | None:
    try:
        raw = lock_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return {}
    try:
        info = json.loads(raw)
    except ValueError:
        return {}  # 写到一半就崩了 → 无 pid，按时长回收
    return info if isinstance(info, dict) else {}


def _age_seconds(created_at: Any, lock_path: Path) -> float | None:
    if isinstance(created_at, str):
        try:
            ts = datetime.fromisoformat(created_at)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds())
        except ValueError:
            pass
    try:
        return max(0.0, time.time() - lock_path.stat().st_mtime)
    except OSError:
        return None
