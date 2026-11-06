"""运行时在崩溃、PID 回收、并发升级之后不用人动手就能恢复。

台账：docs/LESSONS.md v0.47.2-dev「启动锁撞上回收的 PID」「install 不防并发也不防崩溃」。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from horosa_skill.errors import RuntimeInstallError, RuntimeValidationError
from horosa_skill.runtime import HorosaRuntimeManager, pidlock
from horosa_skill.config import Settings
from horosa_skill.runtime.manager import INSTALL_TEMP_OWNER
from test_runtime_manager import _archive_of, _endpoints, _install_fake_spawn, _managed_mode, _manager_with_runtime  # noqa: F401 - _managed_mode 是 autouse fixture

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


# ------------------------------------------------------------------ 升级与别的客户端的启动互斥

def test_a_client_start_during_the_swap_is_told_to_wait(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """2026-11-06 强制交错复现：stop 与换目录之间另一个会话的调用从旧树起了启动器，随后旧树被删，install 仍报 ok、warnings 为空。
    这正是 v0.38.1 R3 要消灭的形状（旧进程从已删路径服务、新载荷永远不启动）。"""
    manager = _manager_with_runtime(tmp_path)
    other_client = HorosaRuntimeManager(manager.settings)
    monkeypatch.setattr(other_client, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours", reachable=False))
    monkeypatch.setattr(other_client, "_service_status", lambda: _endpoints(verdict="ours", reachable=False))
    spawned: list[str] = []
    _install_fake_spawn(other_client, on_spawn=lambda: spawned.append("spawn"))
    seen: dict[str, object] = {}

    def stop_then_get_called_from_another_session(*, ignore_clients: bool = False) -> dict[str, object]:
        seen.update(other_client.start_local_services(wait_seconds=0.1))
        return {"ok": True}

    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours"))
    monkeypatch.setattr(manager, "stop_local_services", stop_then_get_called_from_another_session)
    monkeypatch.setattr(manager, "start_local_services", lambda **_: {"ok": True})

    manager.install(archive=_archive_of(tmp_path), force=True)

    assert spawned == [], "换目录期间不许起启动器"
    assert seen["starting"] is True
    assert not (manager.runtime_root / LOCK).exists(), "换完放锁，否则 install 自己的重启会被挡住"


def test_the_swap_lock_is_released_when_the_swap_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="foreign"))
    monkeypatch.setattr("horosa_skill.runtime.manager.holders_outside_runtime_root", lambda port, root: [])
    with pytest.raises(RuntimeInstallError) as excinfo:
        manager.install(archive=_archive_of(tmp_path), force=True)
    assert excinfo.value.code == "runtime.install_refused_running_foreign"
    assert not (manager.runtime_root / LOCK).exists()


def test_install_does_not_swap_under_a_start_in_flight(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """启动器正在从 current/ 起服务时换目录，等于把它脚下的文件搬走：等它，等不到就说清楚，current/ 不动。"""
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours", reachable=False))
    marker = manager.current_dir / "MARKER"
    marker.write_text("keep", encoding="utf-8")
    _write_lock(manager.runtime_root / LOCK, owner="runtime-start")

    with pytest.raises(RuntimeInstallError) as excinfo:
        manager.install(archive=_archive_of(tmp_path), force=True)

    assert excinfo.value.code == "runtime.install_start_in_progress"
    assert marker.exists()
    assert (manager.runtime_root / LOCK).exists(), "别人的锁不归我们放"


# ------------------------------------------------------------------ 崩溃留下的临时目录

def _leftover(manager: HorosaRuntimeManager, name: str, *, owner_pid: int | None, age_hours: float = 0.0) -> Path:
    path = manager.runtime_root / name
    (path / "x").mkdir(parents=True)
    (path / "x" / "archive.bin").write_bytes(b"0" * 16)
    stamp = time.time() - age_hours * 3600
    if owner_pid is not None:
        (path / INSTALL_TEMP_OWNER).write_text(str(owner_pid), encoding="utf-8")
        os.utime(path / INSTALL_TEMP_OWNER, (stamp, stamp))
    os.utime(path, (stamp, stamp))
    return path


def test_a_crashed_install_temp_is_swept_by_the_next_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """被杀的 install 留下归档 + 解开的树（真载荷约 2 GB）。清理不等「重试成功」：下一次 install 一进来就清，否则磁盘预检先拦住它。"""
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours", reachable=False))
    crashed = _leftover(manager, ".hi-crashed", owner_pid=999999)

    manager.install(archive=_archive_of(tmp_path), force=True)

    assert not crashed.exists()


def test_a_running_install_temp_is_left_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours", reachable=False))
    running = _leftover(manager, ".hi-running", owner_pid=os.getpid())

    manager.install(archive=_archive_of(tmp_path), force=True)

    assert running.exists()


def test_an_install_temp_on_a_recycled_pid_is_swept_once_it_is_old(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours", reachable=False))
    recycled = _leftover(manager, ".hi-recycled", owner_pid=os.getpid(), age_hours=7)

    manager.install(archive=_archive_of(tmp_path), force=True)

    assert not recycled.exists()


def test_unmarked_temps_are_swept_by_age(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """升级前的版本留下的 `.hi-*` 没有属主标记：老的清掉，刚建的可能还没写标记，不动。"""
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours", reachable=False))
    old = _leftover(manager, ".hi-old", owner_pid=None, age_hours=2)
    fresh = _leftover(manager, ".hi-fresh", owner_pid=None)

    manager.install(archive=_archive_of(tmp_path), force=True)

    assert not old.exists() and fresh.exists()


def test_install_temps_are_in_the_uninstall_plan(tmp_path: Path) -> None:
    manager = _manager_with_runtime(tmp_path)
    leak = _leftover(manager, ".hi-leak", owner_pid=999999)
    assert str(leak) in manager.uninstall()["would_remove"]


# ------------------------------------------------------------------ 只剩 previous/ 的现场

def _crash_between_the_renames(manager: HorosaRuntimeManager) -> Path:
    """current/ 已挪成 previous/、新载荷还没进来时进程没了。补齐本平台的必需路径（测试归档只带 mac 布局）。"""
    previous = manager.runtime_root / "previous"
    manifest = manager.load_installed_manifest()
    for _, relative, kind in manager._required_paths(manifest):
        path = manager.current_dir / relative
        if kind == "dir":
            path.mkdir(parents=True, exist_ok=True)
        elif not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
    manager.current_dir.replace(previous)
    return previous


def _no_services(manager: HorosaRuntimeManager, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours", reachable=False))
    monkeypatch.setattr(manager, "_service_status", lambda: _endpoints(verdict="ours", reachable=False))
    _install_fake_spawn(manager, returncode=None)


def test_start_restores_a_complete_previous(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """2026-11-06 复现：这个现场下工具一律 runtime.not_installed，离线重装失败，好副本就在旁边没人管。"""
    manager = _manager_with_runtime(tmp_path)
    _no_services(manager, monkeypatch)
    _crash_between_the_renames(manager)

    assert manager.start_local_services(wait_seconds=0.1)["starting"] is True

    assert manager.current_dir.is_dir() and not (manager.runtime_root / "previous").exists()


def test_an_incomplete_previous_is_not_restored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager_with_runtime(tmp_path)
    _no_services(manager, monkeypatch)
    previous = _crash_between_the_renames(manager)
    (previous / "runtime-manifest.json").unlink()

    with pytest.raises(RuntimeValidationError) as excinfo:
        manager.start_local_services(wait_seconds=0.1)

    # 没有载荷的平台（Linux CI）同一处报 runtime.platform_unsupported；这里只看 previous/ 没被动过。
    assert excinfo.value.code in {"runtime.not_installed", "runtime.platform_unsupported"}
    assert previous.exists() and not manager.current_dir.exists()


def test_a_previous_is_left_alone_while_a_swap_holds_the_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """install 两次改名之间同样只有 previous/：这时挪回去，新载荷会被 `shutil.move` 搬进 current/ 里面。"""
    manager = _manager_with_runtime(tmp_path)
    _no_services(manager, monkeypatch)
    previous = _crash_between_the_renames(manager)
    _write_lock(manager.runtime_root / LOCK, owner="runtime-install")

    with pytest.raises(RuntimeValidationError):
        manager.start_local_services(wait_seconds=0.1)

    assert previous.exists() and not manager.current_dir.exists()


def test_install_puts_a_complete_previous_back_first_so_rollback_still_works(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """只剩 previous/ 时 install 先删它再换入：这一步再失败就什么都没了（install 的注释写的就是这个）。"""
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _endpoints(verdict="ours", reachable=False))
    _crash_between_the_renames(manager)
    monkeypatch.setattr("horosa_skill.runtime.manager.shutil.move", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))

    with pytest.raises(OSError):
        manager.install(archive=_archive_of(tmp_path), force=True)

    assert (manager.current_dir / "runtime-manifest.json").is_file(), "换入失败后回滚到旧副本"


def test_uninstall_does_not_bring_previous_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """卸载的停服务路径也调 `_require_runtime`：恢复放在那里会把要删的东西挪回 current/，卸完还剩一份。"""
    manager = _manager_with_runtime(tmp_path)
    _no_services(manager, monkeypatch)
    _crash_between_the_renames(manager)

    manager.uninstall(yes=True)

    assert not manager.current_dir.exists() and not (manager.runtime_root / "previous").exists()


# ------------------------------------------------------------------ 下载：416 与镜像

ARCHIVE = b"archive-bytes" * 100
ARCHIVE_SHA = hashlib.sha256(ARCHIVE).hexdigest()
ORIGINAL = "https://github.com/o/r/releases/download/v1/payload.tar.gz"
MANIFEST_URL = "https://github.com/o/r/releases/latest/download/runtime-manifest.json"


def _transport(monkeypatch: pytest.MonkeyPatch, handler: Any) -> list[tuple[str, str | None]]:
    seen: list[tuple[str, str | None]] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), request.headers.get("range")))
        return handler(request)

    real_client = httpx.Client

    def patched(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(recording)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", patched)
    monkeypatch.setattr("horosa_skill.runtime.manager.time.sleep", lambda seconds: None)
    return seen


def _ranged(request: httpx.Request, body: bytes = ARCHIVE) -> httpx.Response:
    header = request.headers.get("range")
    if not header:
        return httpx.Response(200, content=body)
    start = int(header.split("=")[1].rstrip("-"))
    if start >= len(body):
        return httpx.Response(416, headers={"Content-Range": f"bytes */{len(body)}"})
    return httpx.Response(206, content=body[start:])


def _downloader(tmp_path: Path, *, part: bytes | None = None) -> tuple[HorosaRuntimeManager, Path]:
    settings = Settings(runtime_root=tmp_path / "rt", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    manager = HorosaRuntimeManager(settings)
    downloads = settings.runtime_root / "downloads"
    downloads.mkdir(parents=True)
    part_path = downloads / "payload.tar.gz.part"
    if part is not None:
        part_path.write_bytes(part)
    manager._last_download = None
    return manager, part_path


def test_a_complete_part_is_finished_not_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """2026-11-06 复现：最后一个字节落盘后、挪走之前崩溃，之后每次重试都是 HTTP 416，错误还说「重试会续传」，只能手删 downloads/。"""
    seen = _transport(monkeypatch, _ranged)
    manager, part = _downloader(tmp_path, part=ARCHIVE)

    target = manager._download_with_resume(ORIGINAL, tmp_path, expected_sha256=ARCHIVE_SHA)

    assert target.read_bytes() == ARCHIVE and len(seen) == 1 and not part.exists()


def test_a_part_longer_than_the_file_starts_over(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """同名资产重新打包变小（repack）时 `.part` 比对方的文件还长。"""
    seen = _transport(monkeypatch, _ranged)
    manager, _ = _downloader(tmp_path, part=ARCHIVE + b"stale tail")

    target = manager._download_with_resume(ORIGINAL, tmp_path, expected_sha256=ARCHIVE_SHA)

    assert target.read_bytes() == ARCHIVE
    assert [rng is not None for _, rng in seen] == [True, False], "丢掉 .part 后从头下，不再带 Range"


def test_a_416_without_a_total_starts_over_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(416) if request.headers.get("range") else httpx.Response(200, content=ARCHIVE)

    _transport(monkeypatch, handler)
    manager, _ = _downloader(tmp_path, part=ARCHIVE)
    assert manager._download_with_resume(ORIGINAL, tmp_path, expected_sha256=ARCHIVE_SHA).read_bytes() == ARCHIVE


@pytest.mark.parametrize("bad", [
    httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>quota exceeded</html>"),
    httpx.Response(200, json={"message": "rate limited"}),
    httpx.Response(200, json=["not", "a", "manifest"]),
], ids=["html", "json-without-platforms", "json-array"])
def test_a_bad_manifest_from_a_mirror_moves_on_to_the_next_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: httpx.Response) -> None:
    """2026-11-06 复现：镜像回 200 + HTML 时 JSONDecodeError 直接冒出去，好好的原始 URL 根本没试。"""
    def handler(request: httpx.Request) -> httpx.Response:
        if "mirror.example" in str(request.url):
            return httpx.Response(bad.status_code, headers=bad.headers, content=bad.content)
        return httpx.Response(200, json={"version": "9.9.9", "platforms": {}})

    monkeypatch.setenv("HOROSA_RUNTIME_MIRROR", "https://mirror.example/gh")
    _transport(monkeypatch, handler)
    manager, _ = _downloader(tmp_path)

    assert manager._read_json_location(MANIFEST_URL)["version"] == "9.9.9"


def test_a_bad_manifest_everywhere_is_a_structured_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _transport(monkeypatch, lambda request: httpx.Response(200, content=b"<html>"))
    manager, _ = _downloader(tmp_path)
    with pytest.raises(RuntimeInstallError) as excinfo:
        manager._read_json_location(MANIFEST_URL)
    assert excinfo.value.code == "runtime.install_manifest_fetch_failed"


def test_a_bad_archive_from_a_mirror_moves_on_to_the_next_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>quota exceeded</html>") if "mirror.example" in str(request.url) else _ranged(request)

    monkeypatch.setenv("HOROSA_RUNTIME_MIRROR", "https://mirror.example/gh")
    seen = _transport(monkeypatch, handler)
    manager, part = _downloader(tmp_path)

    target = manager._download_with_resume(ORIGINAL, tmp_path, expected_sha256=ARCHIVE_SHA)

    assert target.read_bytes() == ARCHIVE
    assert manager._last_download["url"] == ORIGINAL and manager._last_download["mirror_used"] is False
    assert seen[-1] == (ORIGINAL, None), "镜像的坏字节不能当成断点续传的前半截"
    assert not part.exists()


def test_a_bad_checksum_everywhere_keeps_its_error_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """全部候选都对不上 sha：错误码不变（`runtime.install_sha256_mismatch`），不留坏的 `.part` 给下一次续传。"""
    _transport(monkeypatch, lambda request: httpx.Response(200, content=b"wrong bytes"))
    manager, part = _downloader(tmp_path)
    with pytest.raises(RuntimeValidationError) as excinfo:
        manager._download_with_resume(ORIGINAL, tmp_path, expected_sha256=ARCHIVE_SHA)
    assert excinfo.value.code == "runtime.install_sha256_mismatch"
    assert not part.exists()
