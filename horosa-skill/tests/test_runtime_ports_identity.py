"""端口归属与进程存活：谁在监听、是不是我们的、能不能停它。

**为什么旧检查抓不到这些**：v0.36.0 之前根本没有「归属」这个概念 —— `_service_status` 只问
「HTTP 响应码 < 500 吗」，于是既有的 runtime 测试全部只在「可达 / 不可达」两个值上打转。
一个 `python -m http.server` 顶着 8899 端口时，那些断言**全绿**，而产品会把它当成 chart 后端
采用（症状：排盘失败但 statusCode 200），或者更糟，让停脚本按端口去关掉用户自己开着的星阙桌面端。
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from horosa_skill.runtime import pidlock, registry
from horosa_skill.runtime.identity import EndpointIdentity, classify_endpoint
from horosa_skill.runtime.ports import find_free_port, listener_pids, port_bindable
from horosa_skill.runtime.procs import pid_alive, process_command


@pytest.fixture()
def listening_server():
    """一个真的、不属于我们的监听进程。"""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and port_bindable(port):
        time.sleep(0.1)
    # v0.38.1：`ports._run` 有 2 s 结果缓存 —— 监听刚起来时别让上一条用例的 netstat 快照顶掉它。
    from horosa_skill.runtime.ports import clear_run_cache

    clear_run_cache()
    try:
        yield port, proc
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# ------------------------------------------------------------------ procs

def test_pid_alive_never_signals_the_target() -> None:
    assert pid_alive(os.getpid()) == "alive"
    assert pid_alive(999999) == "dead"
    assert pid_alive("not-a-pid") == "unknown"
    assert pid_alive(-1) == "unknown"
    assert pid_alive(0) == "unknown"


def test_process_command_reads_the_command_line() -> None:
    command = process_command(os.getpid()) or ""
    assert "python" in command.lower()
    assert process_command(999999) is None


# ------------------------------------------------------------------ ports

def _listener_lookup_available() -> bool:
    """本平台的监听查询工具在不在（Linux 需要 iproute2 的 `ss`，某些精简镜像里没有）。"""
    if os.name == "nt":
        return shutil.which("netstat") is not None
    if sys.platform == "darwin":
        return shutil.which("netstat") is not None
    return shutil.which("ss") is not None


def _listener_pids_with_patience(port: int, attempts: int = 4) -> list[int]:
    """托管 runner 在满负载下 netstat 可能慢/暂时空：给几次机会，别把一次抖动当成「查不到持有者」。"""
    pids: list[int] = []
    for _ in range(attempts):
        pids = listener_pids(port)
        if pids:
            return pids
        time.sleep(1.0)
    return pids


def _listener_diagnostics(port: int) -> str:
    from horosa_skill.runtime import ports as _ports

    tool = "netstat" if (os.name == "nt" or sys.platform == "darwin") else "ss"
    raw = _ports._run(["netstat", "-anv", "-p", "tcp"] if sys.platform == "darwin" else (["netstat", "-ano", "-p", "TCP"] if os.name == "nt" else ["ss", "-lntp"]))
    matching = [line for line in raw.splitlines() if f".{port}" in line or f":{port}" in line]
    return f"tool={tool} on PATH={shutil.which(tool)} output_lines={len(raw.splitlines())} lines_with_port={matching[:3]}"


def test_listener_pids_finds_a_real_listener(listening_server) -> None:
    """🔴 这条要真跑到才有意义。

    查不到持有者与「端口空着」必须区分开 —— `listener_pids` 返回空列表**只表示查不到**。
    工具缺席时 skip 而不是把空列表当成通过：那样这条守卫会在最需要它的环境里静默失效。
    """
    if not _listener_lookup_available():
        pytest.skip("本平台的监听查询工具不可用（Linux 需 iproute2 的 ss）")
    port, proc = listening_server
    pids = _listener_pids_with_patience(port)
    assert pids, f"端口上明明有监听进程，却一个持有者都查不出来（{_listener_diagnostics(port)}）"
    # 🔴 断言的是「查得出持有者」，不是「持有者 pid == 我们 spawn 的那个」：Windows 上
    # venv 的 python.exe 可能是个 shim，真正监听的是它 spawn 的子进程（CI 实测 8792 vs 1764）。
    # 产品侧要的能力是「端口上有人、且能拿到它的命令行」，pid 的父子关系不在契约里。
    if proc.pid not in pids:
        from horosa_skill.runtime.procs import process_command

        commands = [process_command(pid) or "" for pid in pids]
        # 命令行取不到时不在这里判死：`process_command` 的可用性由它自己的用例守，
        # 这条守的是「端口上有人时查得出持有者」。
        if any(commands):
            assert any("http.server" in c or "python" in c.lower() for c in commands), (
                f"持有者 {pids} 的命令行看不出是我们起的那个监听进程：{commands}"
            )


def test_port_bindable_distinguishes_held_from_free(listening_server) -> None:
    port, _proc = listening_server
    assert port_bindable(port) is False
    assert port_bindable(find_free_port(port + 1)) is True


def test_find_free_port_skips_the_held_one(listening_server) -> None:
    port, _proc = listening_server
    assert find_free_port(port) != port


def test_empty_listener_pids_must_not_be_read_as_free() -> None:
    """查不到持有者 ≠ 端口空着。这条区分正是「静默采用陌生后端」的起点。"""
    assert listener_pids(1) == []            # 特权端口，通常无权查
    # 端口可用性只能问 port_bindable：
    assert isinstance(port_bindable(1), bool)


# ------------------------------------------------------------------ identity

def test_a_stranger_on_our_port_is_classified_foreign(listening_server, tmp_path) -> None:
    """真起一个陌生监听进程，判定必须是 foreign（而不是「HTTP 200 即可达」）。

    工具缺席时 skip：没有监听查询就退到第三级证据，那条另有用例（`no_evidence_at_all`）。
    """
    if not _listener_lookup_available():
        pytest.skip("本平台的监听查询工具不可用（Linux 需 iproute2 的 ss）")
    # 托管 runner 满负载下第一次查询可能空：先耐心确认查得到持有者，再判归属（否则 unknown 会被误当成 foreign 失败）
    assert _listener_pids_with_patience(listening_server[0]), f"监听查询空手而归（{_listener_diagnostics(listening_server[0])}）"
    port, _proc = listening_server
    verdict = classify_endpoint(f"http://127.0.0.1:{port}", runtime_root=tmp_path / "runtime")
    assert verdict.verdict == "foreign"
    assert verdict.evidence == "process.command_is_not_ours"
    # 判据是「查得出持有者、且它的命令行不是我方 runtime」；具体 pid 是谁不在契约里（见上一条）。
    assert verdict.holders, "查得出持有者是这条判定的前提"
    assert verdict.started_by_us is False


def test_identity_nonce_match_is_ours_and_stoppable(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "horosa_skill.runtime.identity.probe_identity",
        lambda url: {"app": "horosa-chart", "proto": 2, "nonce": "n1"},
    )
    verdict = classify_endpoint("http://127.0.0.1:8899", runtime_root=tmp_path, launch_nonce="n1")
    assert verdict.verdict == "ours" and verdict.started_by_us is True


def test_identity_nonce_mismatch_is_foreign(monkeypatch, tmp_path) -> None:
    """同一个 app 标记、同一个默认端口，但不是**这次**启动的那一份 —— 用户自己开着的桌面端。"""
    monkeypatch.setattr(
        "horosa_skill.runtime.identity.probe_identity",
        lambda url: {"app": "horosa-chart", "nonce": "someone-else"},
    )
    verdict = classify_endpoint("http://127.0.0.1:8899", runtime_root=tmp_path, launch_nonce="n1")
    assert verdict.verdict == "foreign" and verdict.nonce_match is False


def test_app_marker_alone_is_usable_but_not_stoppable(monkeypatch, tmp_path) -> None:
    """只有 app 标记：可以当后端用，但**不许**对它执行停/重启。

    「能用它」与「能停它」是两件事。混为一谈的后果是一次 restart 关掉用户正在用的桌面端。
    """
    monkeypatch.setattr(
        "horosa_skill.runtime.identity.probe_identity",
        lambda url: {"app": "horosa-backend", "proto": 2, "nonce": ""},
    )
    verdict = classify_endpoint("http://127.0.0.1:9999", runtime_root=tmp_path)
    assert verdict.verdict == "ours"
    assert verdict.started_by_us is False


def test_identity_endpoint_absent_falls_through_instead_of_judging_foreign(monkeypatch, tmp_path) -> None:
    """`/horosaIdentity` 只在新载荷上存在。404 必须落到下一级证据，不能当成反面证据。"""
    monkeypatch.setattr("horosa_skill.runtime.identity.probe_identity", lambda url: None)
    monkeypatch.setattr("horosa_skill.runtime.identity.listener_pids", lambda port: [4242])
    monkeypatch.setattr(
        "horosa_skill.runtime.identity.process_command",
        lambda pid: f"/usr/bin/java -Dhorosa.runtime.root={tmp_path} -jar boot.jar",
    )
    verdict = classify_endpoint("http://127.0.0.1:9999", runtime_root=tmp_path)
    assert verdict.verdict == "ours"
    assert verdict.evidence == "process.command_matches_runtime_root"
    assert verdict.started_by_us is True


def test_no_evidence_at_all_is_unknown_not_ours(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("horosa_skill.runtime.identity.probe_identity", lambda url: None)
    monkeypatch.setattr("horosa_skill.runtime.identity.listener_pids", lambda port: [])
    verdict = classify_endpoint("http://127.0.0.1:9999", runtime_root=tmp_path)
    assert verdict.verdict == "unknown"
    assert verdict.started_by_us is False


def test_registry_service_pid_is_the_last_resort(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("horosa_skill.runtime.identity.probe_identity", lambda url: None)
    monkeypatch.setattr("horosa_skill.runtime.identity.listener_pids", lambda port: [])
    verdict = classify_endpoint(
        "http://127.0.0.1:9999", runtime_root=tmp_path, service_pids=[os.getpid()]
    )
    assert verdict.verdict == "ours" and verdict.evidence == "registry.service_pid_alive"


# ------------------------------------------------------------------ pidlock

def test_a_live_holder_is_never_reclaimed_however_old(tmp_path) -> None:
    """合法的长启动（首次 CDS 训练可达 15 分钟）必须被尊重。"""
    lock = tmp_path / "x.lock"
    lock.write_text(json.dumps({"pid": os.getpid(), "created_at": "2000-01-01T00:00:00+00:00"}))
    assert pidlock.try_pid_lock(lock, stale_after_seconds=0.0) is False
    assert pidlock.reclaim_if_stale(lock, stale_after_seconds=0.0) is False


def test_a_dead_holder_is_reclaimed_immediately(tmp_path) -> None:
    lock = tmp_path / "x.lock"
    lock.write_text(json.dumps({"pid": 999999, "created_at": "2026-01-01T00:00:00+00:00"}))
    assert pidlock.try_pid_lock(lock) is True


def test_a_corrupt_lock_falls_back_to_age(tmp_path) -> None:
    lock = tmp_path / "x.lock"
    lock.write_text("{half writ")
    os.utime(lock, (time.time() - 10_000, time.time() - 10_000))
    assert pidlock.try_pid_lock(lock, stale_after_seconds=3600.0) is True


def test_blocking_lock_times_out_with_the_holder_named(tmp_path) -> None:
    lock = tmp_path / "x.lock"
    assert pidlock.try_pid_lock(lock, owner="first") is True
    with pytest.raises(TimeoutError) as excinfo:
        with pidlock.pid_lock(lock, timeout_seconds=0.3):
            pass
    assert "first" in str(excinfo.value)


# ------------------------------------------------------------------ registry

def test_state_write_is_atomic_and_leaves_no_debris(tmp_path, monkeypatch) -> None:
    """`os.replace` 抛错时不许留下 .tmp 残片（否则 runtime 根会越攒越多）。"""
    path = tmp_path / "runtime-state.json"
    registry.write_state(path, {"status": "running"})
    before = set(os.listdir(tmp_path))
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError):
        registry.write_state(path, {"status": "x"})
    assert set(os.listdir(tmp_path)) == before
    assert (registry.read_state(path) or {})["status"] == "running"


def test_half_written_state_reads_as_absent_not_as_garbage(tmp_path) -> None:
    path = tmp_path / "runtime-state.json"
    path.write_text("{half writ", encoding="utf-8")
    assert registry.read_state(path) is None


def test_v1_state_still_loads_with_v2_defaults(tmp_path) -> None:
    """升级不能让用户的「正在跑」变成「没在跑」。"""
    path = tmp_path / "runtime-state.json"
    path.write_text(json.dumps({"managed": True, "status": "running"}), encoding="utf-8")
    state = registry.read_state(path)
    assert state["status"] == "running"
    assert state["mode"] is None and state["clients"] == {}


def test_dead_clients_do_not_block_a_stop(tmp_path) -> None:
    path = tmp_path / "runtime-state.json"
    registry.attach_client(path, pid=os.getpid(), transport="stdio")
    registry.attach_client(path, pid=999999, transport="http")
    state = registry.read_state(path)
    assert list(registry.live_clients(state)) == [str(os.getpid())]
    assert registry.live_clients(state, exclude_pid=os.getpid()) == {}


def test_full_overwrite_keeps_long_lived_v2_fields(tmp_path) -> None:
    """一次 start/stop 的整份覆盖不该把别的进程写进来的 launch_nonce / clients 抹掉。"""
    from horosa_skill.config import Settings
    from horosa_skill.runtime.manager import HorosaRuntimeManager

    settings = Settings(runtime_root=tmp_path / "rt", db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs")
    manager = HorosaRuntimeManager(settings)
    manager._write_runtime_state({"status": "running", "launch_nonce": "n1"})
    registry.attach_client(settings.runtime_state_path, pid=os.getpid(), transport="stdio")
    manager._write_runtime_state({"status": "running_with_warnings"})
    state = manager.load_runtime_state() or {}
    assert state["status"] == "running_with_warnings"
    assert state["launch_nonce"] == "n1"
    assert str(os.getpid()) in state["clients"]

def test_app_marker_does_not_shadow_the_command_line_evidence(monkeypatch, tmp_path) -> None:
    """app 标记（弱）不许挡住命令行（强）—— 否则 `stop` 停不掉自己启动的 runtime。

    实测（Windows 构建机）：服务**没报 nonce** 时（直接跑 payload 自带的启动器、或状态里的 nonce
    已被后一次启动覆盖），第 1 级的 app-marker 短路命中、`started_by_us` 恒为 False，于是
    `horosa-skill stop` 对**跑在我们 runtime 根下的** chart+java 报 `runtime.stop_refused_foreign`，
    用户只能按 PID 手杀。修法是只允许「弱 ours → 强 ours」的升级（绝不降级为 foreign，那会打掉
    外部模式：用用户自己开着的桌面端当后端）。
    """
    monkeypatch.setattr(
        "horosa_skill.runtime.identity.probe_identity",
        lambda url: {"app": "horosa-chart", "proto": 2, "nonce": ""},
    )
    monkeypatch.setattr("horosa_skill.runtime.identity.listener_pids", lambda port: [4242])
    monkeypatch.setattr(
        "horosa_skill.runtime.identity.process_command",
        lambda pid: f'"{tmp_path}/current/runtime/windows/python/python.exe" webchartsrv.py',
    )
    verdict = classify_endpoint("http://127.0.0.1:8899", runtime_root=tmp_path)
    assert verdict.verdict == "ours"
    assert verdict.evidence == "process.command_matches_runtime_root"
    assert verdict.started_by_us is True, "命令行证明它就在我们的 runtime 根下，必须可停"


def test_app_marker_is_upgraded_by_the_registry_pid_too(monkeypatch, tmp_path) -> None:
    """命令行查不到时，我方注册表里记的活 pid 同样是强证据（同一条升级路径的第二条腿）。"""
    monkeypatch.setattr(
        "horosa_skill.runtime.identity.probe_identity",
        lambda url: {"app": "horosa-backend", "proto": 2, "nonce": ""},
    )
    monkeypatch.setattr("horosa_skill.runtime.identity.listener_pids", lambda port: [])
    monkeypatch.setattr("horosa_skill.runtime.identity.pid_alive", lambda pid: "alive")
    verdict = classify_endpoint("http://127.0.0.1:9999", runtime_root=tmp_path, service_pids=[321])
    assert verdict.evidence == "registry.service_pid_alive"
    assert verdict.started_by_us is True


def test_app_marker_with_a_stranger_command_stays_weak_not_foreign(monkeypatch, tmp_path) -> None:
    """反向不许发生：对面已自报星阙协议，命令行不在我们根下时只能停在**弱 ours**。

    判成 foreign 会连「外部模式：用用户自己开着的桌面端当后端」一起打掉；弱 ours 恰好是
    「能用它、但不许停它」——正是 EndpointIdentity 那段注释要的语义。
    """
    monkeypatch.setattr(
        "horosa_skill.runtime.identity.probe_identity",
        lambda url: {"app": "horosa-chart", "proto": 2, "nonce": ""},
    )
    monkeypatch.setattr("horosa_skill.runtime.identity.listener_pids", lambda port: [999])
    monkeypatch.setattr(
        "horosa_skill.runtime.identity.process_command",
        lambda pid: r'"C:\Program Files\Horosa Desktop\horosa.exe" --serve',
    )
    verdict = classify_endpoint("http://127.0.0.1:8899", runtime_root=tmp_path)
    assert verdict.verdict == "ours", "自报星阙协议的对面不该被判 foreign"
    assert verdict.evidence == "identity.app_marker"
    assert verdict.started_by_us is False, "不是我们起的，就不许停它"
