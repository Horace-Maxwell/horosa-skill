from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.evaluation_lock import acquire_evaluation_lock


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )


def _write_lock(settings: Settings, payload: dict) -> Path:
    lock_path = settings.runtime_root / ".evaluation.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(payload), encoding="utf-8")
    return lock_path


def test_acquire_then_release_cleans_up(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with acquire_evaluation_lock(settings) as lock_path:
        assert lock_path.exists()
    assert not lock_path.exists()


@pytest.mark.skipif(
    os.name == "nt",
    reason="PID-liveness reclaim is POSIX-only (os.kill(pid,0) is a probe on POSIX but TerminateProcess "
    "on Windows); Windows reclaims stale locks by the age threshold, covered by the age test below.",
)
def test_reclaims_stale_lock_from_dead_pid(tmp_path: Path) -> None:
    # A recorded PID that is (effectively) never alive must be reclaimed immediately, not waited out.
    settings = _settings(tmp_path)
    _write_lock(settings, {"pid": 2_000_000_000, "created_at": datetime.now(timezone.utc).isoformat()})
    with acquire_evaluation_lock(settings, timeout_seconds=2.0) as lock_path:
        assert lock_path.exists()
    assert not lock_path.exists()


def test_reclaims_stale_lock_by_age_when_pid_unknown(tmp_path: Path) -> None:
    # Corrupt/unparseable PID -> fall back to the age threshold (cross-platform path).
    settings = _settings(tmp_path)
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    _write_lock(settings, {"pid": "not-an-int", "created_at": old})
    with acquire_evaluation_lock(settings, timeout_seconds=2.0, stale_after_seconds=3600.0) as lock_path:
        assert lock_path.exists()
    assert not lock_path.exists()


def test_does_not_reclaim_a_live_lock(tmp_path: Path) -> None:
    # A lock owned by THIS (alive) process must never be reclaimed, even though we want it.
    settings = _settings(tmp_path)
    lock_path = _write_lock(settings, {"pid": os.getpid(), "created_at": datetime.now(timezone.utc).isoformat()})
    with pytest.raises(TimeoutError):
        with acquire_evaluation_lock(settings, timeout_seconds=0.5):
            pass
    assert lock_path.exists()  # the live owner's lock survived
    lock_path.unlink()
