"""HTTP 探针看不见的端口占用者（docs/LESSONS.md v0.50.0-dev「不说 HTTP 的监听者让 start 等满预算」）。

旧行为：Java 端口上有个不应答 HTTP 的监听者 → 端点「不可达」、身份判定不跑 → 照样起启动器 → Java 绑不上 →
用户等满启动预算，拿到 `runtime.start_timeout` 且 `conflicts` 为空，doctor 也一声不吭。

本文件只在 18805–18812 上开自己的监听 socket（先确认空闲，不空闲就跳过），永不碰 8899 / 9999。
"""
from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from horosa_skill.errors import RuntimeInstallError, recovery_for
from horosa_skill.runtime import ports
from test_runtime_manager import _install_fake_spawn, _managed_mode, _manager_with_runtime  # noqa: F401 - _managed_mode 是 autouse fixture

_RANGE = range(18805, 18813)


def _free_pair() -> tuple[int, int]:
    free = [port for port in _RANGE if ports.port_bindable(port) and not ports._accepting(port)]
    if len(free) < 2:
        pytest.skip("[host] no free test ports in 18805-18812")
    return free[0], free[1]


@contextmanager
def _silent_listener(port: int) -> Iterator[socket.socket]:
    """只 listen、从不 accept 也从不说 HTTP 的监听者。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        sock.listen(8)
        yield sock
    finally:
        sock.close()


def _unreachable(backend: int, chart: int) -> list[dict[str, object]]:
    return [
        {"label": "java_backend", "url": f"http://127.0.0.1:{backend}", "reachable": False, "identity": None},
        {"label": "python_chart", "url": f"http://127.0.0.1:{chart}", "reachable": False, "identity": None},
    ]


def _manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backend: int, chart: int):
    manager = _manager_with_runtime(tmp_path)
    manager.settings.local_backend_port = backend
    manager.settings.local_chart_port = chart
    monkeypatch.setattr("horosa_skill.runtime.manager.port_taken", ports.port_taken)  # autouse 把它钉成 None；这里要真的
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: _unreachable(backend, chart))
    monkeypatch.setattr(manager, "_service_status", lambda: _unreachable(backend, chart))
    return manager


def test_port_taken_sees_a_listener_and_names_it() -> None:
    backend, _ = _free_pair()
    assert ports.port_taken(backend) is None
    with _silent_listener(backend):
        taken = ports.port_taken(backend)
    assert taken is not None and taken["port"] == backend and taken["accepting"] is True
    if taken["holders"]:  # 点名是尽力而为（netstat / lsof 不可用的机器上为空）
        assert os.getpid() in {h["pid"] for h in taken["holders"]}


def test_start_refuses_before_spawning_when_a_silent_listener_holds_a_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend, chart = _free_pair()
    manager = _manager(tmp_path, monkeypatch, backend, chart)
    spawned: list[bool] = []
    _install_fake_spawn(manager, on_spawn=lambda: spawned.append(True))

    with _silent_listener(backend), pytest.raises(RuntimeInstallError) as excinfo:
        manager.start_local_services(wait_seconds=0.2)

    error = excinfo.value
    assert error.code == "runtime.port_taken" and spawned == []
    taker = error.details["port_takers"][0]
    assert taker["label"] == "java_backend" and taker["port"] == backend and taker["accepting"] is True
    assert f":{backend}" in str(error) and " / " in str(error)
    assert recovery_for(error.code, error.details)["agent_recovery"]["next_action"] == "free_the_port_or_set_horosa_ports_auto"
    assert not (manager.runtime_root / ".runtime-start.lock").exists(), "拒绝也要放锁"


def test_our_own_half_started_service_is_not_called_foreign(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """注册表里记着的 service_pids 占着端口 = 自家启动到一半的服务，交给启动器自己的恢复，不拒。"""
    backend, chart = _free_pair()
    manager = _manager(tmp_path, monkeypatch, backend, chart)
    with _silent_listener(backend):
        if not ports.port_holders(backend):
            pytest.skip("[host] listener pids are not visible on this machine")
        manager._write_runtime_state({"managed": True, "status": "starting", "service_pids": [os.getpid()]})
        assert manager._ports_taken_by_others(_unreachable(backend, chart)) == []


def test_a_start_timeout_names_whoever_took_the_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """启动器起来之后才被抢走的端口：超时的报错里点名，而不是 conflicts 为空。"""
    backend, chart = _free_pair()
    manager = _manager(tmp_path, monkeypatch, backend, chart)
    listener: list[socket.socket] = []

    def grab() -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", chart))
        sock.listen(1)
        listener.append(sock)

    _install_fake_spawn(manager, returncode=0, on_spawn=grab)
    try:
        with pytest.raises(RuntimeInstallError) as excinfo:
            manager.start_local_services()
    finally:
        for sock in listener:
            sock.close()

    error = excinfo.value
    assert error.code == "runtime.start_timeout"
    assert [t["port"] for t in error.details["port_takers"]] == [chart]
    assert f":{chart}" in str(error)


def test_doctor_reports_the_silent_listener_as_a_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill.surfaces import doctor

    backend, chart = _free_pair()
    manager = _manager(tmp_path, monkeypatch, backend, chart)
    with _silent_listener(backend):
        report = {"mode": "managed", "endpoints": _unreachable(backend, chart)}
        report["port_takers"] = manager._ports_taken_by_others(report["endpoints"])
        conflicts = doctor._doctor_port_holders(report)
        probe = doctor._probe_port(backend)
    assert [(c["port"], c["verdict"]) for c in conflicts] == [(backend, "silent_listener")]
    assert probe["occupied"] is True and probe["accepting"] is True
    summary = doctor._doctor_summary({**report, "installed": True, "port_conflicts": conflicts, "issues": []})
    assert summary["status"] == "needs_attention" and str(backend) in summary["user_summary"]
