"""端口查询的成本与双栈正确性（v0.38.1 A2 / A20）+ 诊断时间预算（runtime/budget.py）。

A2 事故形状：一次 doctor 为两个端口 × 两个地址族问四次 `netstat -ano`（Windows 上每次 2–15 s），加上
`runtime status` / `endpoint_identities` 再问 —— 最坏 ~165 s，而 MCP 客户端 60 s 就掐工具。
A20：Windows 上只听 `[::]:9999` 的服务不占 `127.0.0.1:9999`，只探 v4 会把它当空闲端口发给 HOROSA_PORTS=auto。
"""
from __future__ import annotations

import socket

import pytest

from horosa_skill.runtime import budget, ports

NETSTAT_ANO = """
Active Connections

  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:8899           0.0.0.0:0              LISTENING       111
  TCP    127.0.0.1:49152        127.0.0.1:8899         ESTABLISHED     333
  TCP    [::]:9999              [::]:0                 LISTENING       222
  TCP    [::1]:8899             [::]:0                 LISTENING       111
  UDP    0.0.0.0:5353           *:*                                    444
"""


@pytest.fixture(autouse=True)
def _fresh_cache():
    ports.clear_run_cache()
    yield
    ports.clear_run_cache()


def _count_netstat(monkeypatch: pytest.MonkeyPatch, stdout: str = NETSTAT_ANO) -> list[list[str]]:
    calls: list[list[str]] = []

    class _Done:
        def __init__(self) -> None:
            self.stdout = stdout

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        calls.append(list(cmd))
        return _Done()

    monkeypatch.setattr(ports.subprocess, "run", fake_run)
    return calls


def _one_doctor_round() -> None:
    ports._listener_pids_windows(8899)
    ports._bindings_windows(8899)
    ports._listener_pids_windows(9999)
    ports._bindings_windows(9999)


def test_one_doctor_round_runs_netstat_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _count_netstat(monkeypatch)
    _one_doctor_round()
    assert calls == [["netstat", "-ano"]]


def test_without_the_cache_the_same_round_spawns_four_times(monkeypatch: pytest.MonkeyPatch) -> None:
    """负向对照：关掉 memoize 就回到旧成本。"""
    calls = _count_netstat(monkeypatch)
    monkeypatch.setattr(ports, "RUN_CACHE_TTL_SECONDS", 0.0)
    _one_doctor_round()
    assert len(calls) == 4


def test_windows_parse_sees_ipv6_only_listeners(monkeypatch: pytest.MonkeyPatch) -> None:
    _count_netstat(monkeypatch)
    assert ports._listener_pids_windows(9999) == [222], "`[::]:9999` 这类双栈 Java 监听此前被 `-p TCP` 过滤掉"
    assert ports._listener_pids_windows(8899) == [111]
    assert {b["local_address"] for b in ports._bindings_windows(9999)} == {"::"}
    assert {b["local_address"] for b in ports._bindings_windows(8899)} == {"0.0.0.0", "::1"}
    assert ports.loopback_only(ports._bindings_windows(8899)) is False
    assert ports._listener_pids_windows(5353) == [], "UDP 行不是监听"


def test_windows_queries_never_filter_by_protocol_family() -> None:
    """`netstat -ano -p TCP` 只列 IPv4；两个 Windows 查询函数发出的必须是裸 `netstat -ano`（且是同一条 → 共用缓存）。"""
    import inspect
    import re

    source = inspect.getsource(ports._listener_pids_windows) + inspect.getsource(ports._bindings_windows)
    calls = re.findall(r"_run\(\[(.*?)\]\)", source)
    assert calls == ['"netstat", "-ano"', '"netstat", "-ano"'], calls


def test_cache_never_stores_an_empty_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _count_netstat(monkeypatch, stdout="")
    ports._run(["netstat", "-ano"])
    ports._run(["netstat", "-ano"])
    assert len(calls) == 2, "空输出 = 查不到，不能被缓存成「没人监听」"


def test_cache_expires_after_the_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _count_netstat(monkeypatch)
    clock = {"now": 1000.0}
    monkeypatch.setattr(ports.time, "monotonic", lambda: clock["now"])
    ports._run(["netstat", "-ano"])
    clock["now"] += ports.RUN_CACHE_TTL_SECONDS + 0.1
    ports._run(["netstat", "-ano"])
    assert len(calls) == 2


# ---------------------------------------------------------------- budget


def test_clamp_without_a_scope_returns_the_timeout_unchanged() -> None:
    assert budget.current() is None
    assert budget.clamp(15.0, "netstat") == 15.0


def test_clamp_inside_a_scope_shrinks_then_skips() -> None:
    with budget.scope(0.2) as scope:
        assert budget.clamp(15.0, "netstat") <= 0.2
        scope.started -= 1.0  # 预算已过
        assert budget.clamp(15.0, "netstat") is None
        assert budget.clamp(15.0, "netstat") is None
        assert scope.skipped == ["netstat"]
        snapshot = scope.as_dict()
    assert snapshot["seconds"] == 0.2 and snapshot["skipped"] == ["netstat"]
    assert budget.current() is None


def test_run_does_not_spawn_once_the_budget_is_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):  # noqa: ANN001, ANN002
        raise AssertionError("must not spawn a subprocess after the budget is exhausted")

    monkeypatch.setattr(ports.subprocess, "run", boom)
    with budget.scope(1.0) as scope:
        scope.started -= 5.0
        assert ports._run(["netstat", "-ano"]) == ""
    assert "netstat -ano" in scope.skipped


def test_timed_records_phase_durations() -> None:
    with budget.scope(5.0) as scope:
        with budget.timed("phase"):
            pass
        with budget.timed("phase"):
            pass
    assert set(scope.timings) == {"phase"} and scope.timings["phase"] >= 0.0


# ---------------------------------------------------------------- dual stack


def _ipv6_loopback_available() -> bool:
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
            sock.bind(("::1", 0))
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _ipv6_loopback_available(), reason="no IPv6 loopback on this host")
def test_port_bindable_sees_an_ipv6_only_listener() -> None:
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
        try:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        except OSError:
            pass
        sock.bind(("::1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]
        assert ports._bindable_on("127.0.0.1", port) is True, "v4 侧确实空着 —— 这正是旧实现（只探 v4）误判为空闲的原因"
        assert ports.port_bindable(port) is False
        assert ports.find_free_port(port) != port


def test_port_bindable_is_true_when_both_families_are_free() -> None:
    port = ports.find_free_port(41000)
    assert ports.port_bindable(port) is True


def test_bindable_on_reports_a_missing_family_as_no_evidence() -> None:
    assert ports._bindable_on("::1", 0) in {True, None}
