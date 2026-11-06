"""运行时在崩溃、PID 回收、并发升级之后不用人动手就能恢复。

台账：docs/LESSONS.md v0.47.2-dev「启动锁撞上回收的 PID」「install 不防并发也不防崩溃」。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from horosa_skill.runtime import pidlock
from test_runtime_manager import _endpoints, _install_fake_spawn, _managed_mode, _manager_with_runtime  # noqa: F401 - _managed_mode 是 autouse fixture

LOCK = ".runtime-start.lock"


def _write_lock(path: Path, *, owner: str, age_days: float = 0.0, pid: int | None = None) -> None:
    created = datetime.now(timezone.utc) - timedelta(days=age_days)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pid": os.getpid() if pid is None else pid, "owner": owner, "created_at": created.isoformat()}), encoding="utf-8")


# ------------------------------------------------------------------ 启动锁

def test_an_old_launcher_lock_is_reclaimed_even_though_its_pid_is_alive(tmp_path: Path) -> None:
    """启动器的 pid 被系统回收给别的进程：存活判定说「活着」，其实那已经不是启动器。一次启动有上限，超过上限的启动器锁只可能是这种情况。"""
    lock = tmp_path / "x.lock"
    _write_lock(lock, owner=pidlock.LAUNCHER_OWNER, age_days=30)
    assert pidlock.reclaim_if_stale(lock, stale_after_seconds=960.0) is True
    assert not lock.exists()


def test_a_launcher_inside_the_start_cap_is_respected(tmp_path: Path) -> None:
    """首次 CDS 训练可达 15 分钟，上限（960 s）之内的启动器锁不能动。"""
    lock = tmp_path / "x.lock"
    _write_lock(lock, owner=pidlock.LAUNCHER_OWNER, age_days=900 / 86400)
    assert pidlock.reclaim_if_stale(lock, stale_after_seconds=960.0) is False
    assert lock.exists()


@pytest.mark.parametrize("owner", ["runtime-start", "evaluation", "runtime-state", ""])
def test_other_live_holders_are_never_reclaimed_by_age(tmp_path: Path, owner: str) -> None:
    """别的锁的 pid 是持锁进程自己：活着就是活着，不论多老。"""
    lock = tmp_path / "x.lock"
    _write_lock(lock, owner=owner, age_days=30)
    assert pidlock.reclaim_if_stale(lock, stale_after_seconds=0.0) is False


def test_start_gets_past_a_launcher_lock_left_on_a_recycled_pid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """2026-11-06 实测：这种锁让每次调用都回 `starting`，启动脚本一次都没跑，直到那个无关进程退出。"""
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours", reachable=False))
    monkeypatch.setattr(manager, "_service_status", lambda: _endpoints(verdict="ours", reachable=False))
    spawned: list[str] = []
    _install_fake_spawn(manager, on_spawn=lambda: spawned.append("spawn"))
    _write_lock(manager.runtime_root / LOCK, owner=pidlock.LAUNCHER_OWNER, age_days=30)

    try:
        manager.start_local_services(wait_seconds=0.2)
    except Exception:  # noqa: BLE001 - 假启动器不会让服务就绪；这里只看它有没有被起
        pass

    assert spawned == ["spawn"]


def test_finding_services_up_collects_the_launcher_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """交给启动器的锁没人释放，会在盘上留到下一次启动。服务都起来了，这把锁就该收回。"""
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours"))
    _write_lock(manager.runtime_root / LOCK, owner=pidlock.LAUNCHER_OWNER)

    assert manager.start_local_services(wait_seconds=0.1)["already_running"] is True

    assert not (manager.runtime_root / LOCK).exists()


def test_waiting_out_another_start_collects_the_launcher_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours", reachable=False))
    monkeypatch.setattr(manager, "_wait_for_service_state",
                        lambda **_: {"ready": True, "endpoints": _endpoints(verdict="ours")})
    _write_lock(manager.runtime_root / LOCK, owner=pidlock.LAUNCHER_OWNER)

    assert manager.start_local_services(wait_seconds=0.1)["started_by_other_process"] is True

    assert not (manager.runtime_root / LOCK).exists()


def test_services_up_leaves_a_live_start_in_another_process_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`runtime-start` 是别的进程正拿着的锁，它自己会放，这里不能抢。"""
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours"))
    _write_lock(manager.runtime_root / LOCK, owner="runtime-start")

    manager.start_local_services(wait_seconds=0.1)

    assert (manager.runtime_root / LOCK).exists()


def test_stop_collects_the_launcher_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager_with_runtime(tmp_path)
    states = iter([_endpoints(verdict="ours")])
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: next(states))
    monkeypatch.setattr(manager, "_wait_for_service_state",
                        lambda **_: {"ready": True, "endpoints": _endpoints(verdict="ours", reachable=False)})
    _write_lock(manager.runtime_root / LOCK, owner=pidlock.LAUNCHER_OWNER)

    assert manager.stop_local_services(force=True)["ok"] is True

    assert not (manager.runtime_root / LOCK).exists()
