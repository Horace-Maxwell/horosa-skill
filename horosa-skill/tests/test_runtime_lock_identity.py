"""启动锁的两类误判（E-08）：目录写不了被读成「有人持锁」；pid 被回收给无关进程后锁永远收不回。

台账：docs/LESSONS.md v0.50.0-dev「锁目录不可写被当成有人在启动」。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from horosa_skill.errors import RuntimeInstallError
from horosa_skill.runtime import pidlock, procs
from test_runtime_manager import _endpoints, _install_fake_spawn, _managed_mode, _manager_with_runtime  # noqa: F401 - autouse fixture

LOCK = ".runtime-start.lock"
posix_only = pytest.mark.skipif(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                                reason="chmod 只读目录对 Windows / root 不生效")


def _write_lock(path: Path, *, owner: str, pid: int, token: str | None) -> None:
    payload = {"pid": pid, "owner": owner, "created_at": datetime.now(timezone.utc).isoformat()}
    if token is not None:
        payload["start_token"] = token
    path.write_text(json.dumps(payload), encoding="utf-8")


# ------------------------------------------------------------------ 进程身份

def test_start_token_is_stable_for_one_process_and_differs_between_processes() -> None:
    mine = procs.process_start_token(os.getpid())
    if mine is None:
        pytest.skip("本平台取不到进程启动时刻")
    assert mine == procs.process_start_token(os.getpid())
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        other = procs.process_start_token(child.pid)
        assert other is not None and other != mine
    finally:
        child.kill()
        child.wait()
    assert procs.process_start_token(child.pid) is None  # 已回收的 pid：没有这个进程


def test_start_token_of_a_bad_pid_is_none() -> None:
    assert procs.process_start_token(None) is None
    assert procs.process_start_token(-5) is None
    assert procs.process_start_token("12") is None


# ------------------------------------------------------------------ 回收

def test_a_new_lock_records_who_created_it(tmp_path: Path) -> None:
    lock = tmp_path / "x.lock"
    assert pidlock.try_pid_lock(lock, owner="runtime-start") is True
    info = json.loads(lock.read_text(encoding="utf-8"))
    assert info["pid"] == os.getpid()
    assert info.get("start_token") == procs.process_start_token(os.getpid())


@pytest.mark.parametrize("owner", ["runtime-start", "evaluation", "runtime-state", pidlock.LAUNCHER_OWNER])
def test_a_live_pid_that_is_not_the_recorded_process_is_reclaimed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, owner: str) -> None:
    """pid 还活着，但启动时刻对不上：系统把这个 pid 发给了别的进程。此前 `runtime-start` 的锁在这种情况下永远收不回，
    每次调用都回 `starting`，直到那个无关进程退出。"""
    lock = tmp_path / "x.lock"
    monkeypatch.setattr(pidlock, "process_start_token", lambda pid: "t:now")
    _write_lock(lock, owner=owner, pid=os.getpid(), token="t:earlier")

    assert pidlock.reclaim_if_stale(lock, stale_after_seconds=3600.0) is True
    assert not lock.exists()


@pytest.mark.parametrize("owner", ["runtime-start", "evaluation", "runtime-state"])
def test_the_real_live_holder_is_never_reclaimed(tmp_path: Path, owner: str) -> None:
    """真的还在启动的那个进程（启动时刻对得上）不论多久都不能被抢锁：首次启动可达 15 分钟。"""
    lock = tmp_path / "x.lock"
    token = procs.process_start_token(os.getpid())
    if token is None:
        pytest.skip("本平台取不到进程启动时刻")
    _write_lock(lock, owner=owner, pid=os.getpid(), token=token)

    assert pidlock.reclaim_if_stale(lock, stale_after_seconds=0.0) is False
    assert pidlock.try_pid_lock(lock, stale_after_seconds=0.0, owner=owner) is False
    assert lock.exists()


def test_an_unknowable_identity_is_never_taken_as_reuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """现在问不出那个进程的启动时刻（别的用户的进程、平台不支持）= 不知道，不能当成「换人了」。"""
    lock = tmp_path / "x.lock"
    monkeypatch.setattr(pidlock, "process_start_token", lambda pid: None)
    _write_lock(lock, owner="runtime-start", pid=os.getpid(), token="t:earlier")

    assert pidlock.reclaim_if_stale(lock, stale_after_seconds=0.0) is False


def test_tokens_taken_by_different_methods_are_not_compared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """两种取法的值没有可比性（升级后换了取法、同一 runtime 根被两个平台的进程共用）：前缀不同就当不知道。"""
    lock = tmp_path / "x.lock"
    monkeypatch.setattr(pidlock, "process_start_token", lambda pid: "b:123")
    _write_lock(lock, owner="runtime-start", pid=os.getpid(), token="a:123")

    assert pidlock.reclaim_if_stale(lock, stale_after_seconds=0.0) is False


def test_handing_the_lock_to_the_launcher_records_the_launchers_identity(tmp_path: Path) -> None:
    from horosa_skill.runtime.manager import _hand_lock_to

    lock = tmp_path / "x.lock"
    assert pidlock.try_pid_lock(lock, owner="runtime-start") is True
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        _hand_lock_to(lock, child.pid)
        info = json.loads(lock.read_text(encoding="utf-8"))
        assert info["pid"] == child.pid and info["owner"] == pidlock.LAUNCHER_OWNER
        assert info.get("start_token") == procs.process_start_token(child.pid)
        assert info.get("start_token") != procs.process_start_token(os.getpid()) or info.get("start_token") is None
    finally:
        child.kill()
        child.wait()


def test_start_gets_past_a_start_lock_left_on_a_recycled_pid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """审计复现（r1_lock）：`runtime-start` 的锁记着一个活着的无关 pid → 每次 start 都回 starting / started_by_other_process。"""
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours", reachable=False))
    monkeypatch.setattr(manager, "_service_status", lambda: _endpoints(verdict="ours", reachable=False))
    spawned: list[str] = []
    _install_fake_spawn(manager, on_spawn=lambda: spawned.append("spawn"))
    if procs.process_start_token(os.getpid()) is None:
        pytest.skip("本平台取不到进程启动时刻")
    _write_lock(manager.runtime_root / LOCK, owner="runtime-start", pid=os.getpid(), token="stale:someone-else")
    # 记录的取法前缀要与本平台一致才可比：用本进程的前缀拼一个不同的值
    mine = procs.process_start_token(os.getpid())
    _write_lock(manager.runtime_root / LOCK, owner="runtime-start", pid=os.getpid(), token=mine.split(":", 1)[0] + ":0")

    try:
        manager.start_local_services(wait_seconds=0.2)
    except Exception:  # noqa: BLE001 - 假启动器不会让服务就绪；这里只看它有没有被起
        pass

    assert spawned == ["spawn"]


# ------------------------------------------------------------------ 目录写不了

@posix_only
def test_an_unwritable_lock_dir_is_an_error_not_a_held_lock(tmp_path: Path) -> None:
    """建不了锁文件不等于有人持锁：此前任何 OSError 都返回 False，调用方于是去等一个不存在的启动者。"""
    root = tmp_path / "ro"
    root.mkdir()
    root.chmod(0o555)
    try:
        with pytest.raises(pidlock.LockDirNotWritableError) as excinfo:
            pidlock.try_pid_lock(root / "x.lock", owner="runtime-start")
        assert excinfo.value.directory == root
        with pytest.raises(pidlock.LockDirNotWritableError):
            with pidlock.pid_lock(root / "x.lock", timeout_seconds=5.0):
                pass
    finally:
        root.chmod(0o755)


@posix_only
def test_a_lock_dir_that_cannot_be_created_is_the_same_error(tmp_path: Path) -> None:
    parent = tmp_path / "ro"
    parent.mkdir()
    parent.chmod(0o555)
    try:
        with pytest.raises(pidlock.LockDirNotWritableError):
            pidlock.try_pid_lock(parent / "missing" / "x.lock")
    finally:
        parent.chmod(0o755)


def test_a_transient_create_failure_in_a_writable_dir_still_reads_as_held(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows 上锁文件处于 delete-pending 时 O_EXCL 创建报 PermissionError：目录本身可写，这是「稍后再试」，不是「写不了」。"""
    real_open = os.open

    def flaky_open(path, flags, *args, **kwargs):
        if str(path).endswith("x.lock"):
            raise PermissionError(13, "Access is denied")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(pidlock.os, "open", flaky_open)
    assert pidlock.try_pid_lock(tmp_path / "x.lock") is False


@posix_only
def test_start_on_an_unwritable_runtime_root_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """审计复现：runtime 根只读时 start 回 `starting / started_by_other_process`，launcher 为 None —— 让人去等一个不存在的启动。"""
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours", reachable=False))
    monkeypatch.setattr(manager, "_service_status", lambda: _endpoints(verdict="ours", reachable=False))
    spawned: list[str] = []
    _install_fake_spawn(manager, on_spawn=lambda: spawned.append("spawn"))
    manager.runtime_root.chmod(0o555)
    try:
        with pytest.raises(RuntimeInstallError) as excinfo:
            manager.start_local_services(wait_seconds=0.2)
    finally:
        manager.runtime_root.chmod(0o755)

    assert excinfo.value.code == "runtime.root_not_writable"
    assert excinfo.value.details["runtime_root"] == str(manager.runtime_root)
    assert "HOROSA_RUNTIME_ROOT" in excinfo.value.details["next_action"]
    assert spawned == []


@posix_only
def test_install_into_an_unwritable_runtime_root_says_so(tmp_path: Path) -> None:
    from horosa_skill.config import Settings
    from horosa_skill.runtime import HorosaRuntimeManager
    from test_runtime_manager import create_runtime_archive

    archive = create_runtime_archive(tmp_path)
    root = tmp_path / "ro-root"
    root.mkdir()
    root.chmod(0o555)
    manager = HorosaRuntimeManager(Settings(runtime_root=root, db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs"))
    try:
        with pytest.raises(RuntimeInstallError) as excinfo:
            manager.install(archive=str(archive))
    finally:
        root.chmod(0o755)
    assert excinfo.value.code == "runtime.root_not_writable"
