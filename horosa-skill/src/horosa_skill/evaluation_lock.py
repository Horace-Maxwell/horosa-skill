from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from horosa_skill.config import Settings


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
    and then fail until someone manually deleted it. A lock is reclaimed when its recorded PID is
    dead (reliable on POSIX) or, when liveness can't be determined (Windows / corrupt lock), when it
    is older than ``stale_after_seconds``. A *live* owner is never reclaimed, so a legitimately
    long-running evaluation is always respected.
    """

    lock_path = settings.runtime_root / ".evaluation.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "pid": os.getpid(),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                    handle,
                    ensure_ascii=False,
                )
            break
        except FileExistsError:
            # Reclaiming is best-effort; the O_EXCL create above is the real mutex, so even if two
            # waiters both reclaim a stale lock only one wins the subsequent create.
            if _reclaim_if_stale(lock_path, stale_after_seconds=stale_after_seconds):
                continue
            if time.monotonic() - started >= timeout_seconds:
                raise TimeoutError(f"Timed out waiting for evaluation lock: {lock_path}")
            time.sleep(0.2)

    try:
        yield lock_path
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _reclaim_if_stale(lock_path: Path, *, stale_after_seconds: float) -> bool:
    """Remove the lock if its owner is dead or it is too old. Return True if it was removed/vanished."""
    try:
        raw = lock_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return True  # already gone — let the caller retry the create
    except OSError:
        return False

    pid: Any = None
    created_at: Any = None
    try:
        info = json.loads(raw)
        if isinstance(info, dict):
            pid = info.get("pid")
            created_at = info.get("created_at")
    except ValueError:
        pass  # corrupt/partial lock (writer crashed mid-write) -> fall back to age

    liveness = _pid_liveness(pid)
    if liveness == "alive":
        return False  # a live owner is never reclaimed, regardless of age
    if liveness == "dead":
        stale = True
    else:  # "unknown": Windows, unsupported, or unparseable pid -> age-based fallback
        age = _lock_age_seconds(created_at, lock_path)
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


def _pid_liveness(pid: Any) -> str:
    """Return 'alive' | 'dead' | 'unknown' for a recorded PID.

    POSIX only: ``os.kill(pid, 0)`` is a safe no-op liveness probe on POSIX. On Windows ``os.kill``
    has NO signal-0 semantics — for any non-CTRL signal it calls ``TerminateProcess``, i.e. it would
    *kill* the target rather than probe it. So on Windows we never call it and return ``unknown``;
    a crashed-run lock there is reclaimed by the age threshold instead of by PID liveness.
    """
    if not isinstance(pid, int) or pid <= 0:
        return "unknown"
    if os.name == "nt":
        return "unknown"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "dead"
    except PermissionError:
        return "alive"  # exists but owned by another user
    except OSError:
        return "unknown"
    return "alive"


def _lock_age_seconds(created_at: Any, lock_path: Path) -> float | None:
    """Age of the lock in seconds — from the recorded timestamp, falling back to file mtime."""
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
