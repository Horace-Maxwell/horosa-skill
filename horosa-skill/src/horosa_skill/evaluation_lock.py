from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from horosa_skill.config import Settings


@contextmanager
def acquire_evaluation_lock(settings: Settings, *, timeout_seconds: float = 60.0) -> Iterator[Path]:
    """Prevent concurrent benchmark/self-check jobs from racing the shared local runtime."""

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
