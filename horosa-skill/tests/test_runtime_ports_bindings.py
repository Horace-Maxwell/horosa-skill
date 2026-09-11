"""Listener scope: which interfaces a port's listener is bound to (v0.38.0 B1).

The Windows launcher used to start Java on 0.0.0.0 (no --server.address). doctor now reports the bound
addresses per service so an installed runtime still running the old template is visible; a wildcard
binding is a warning, loopback-only is clean, and "could not tell" is None — never read as clean.
"""

from __future__ import annotations

import pytest

from horosa_skill.runtime import ports

_WIN_TCP = """
Active Connections

  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:9999           0.0.0.0:0              LISTENING       4321
  TCP    127.0.0.1:8899         0.0.0.0:0              LISTENING       1234
  TCP    127.0.0.1:9999         127.0.0.1:50212        ESTABLISHED     4321
"""
_WIN_TCP6 = """
  Proto  Local Address          Foreign Address        State           PID
  TCP    [::]:9999              [::]:0                 LISTENING       4321
  TCP    [::1]:8899             [::]:0                 LISTENING       1234
"""
_MAC = """
Active Internet connections (including servers)
Proto Recv-Q Send-Q  Local Address          Foreign Address        (state)      rhiwat shiwat    pid   epid  state    options
tcp4       0      0  127.0.0.1.8899         *.*                    LISTEN      131072 131072   6123      0 0x0100 0x00000106 python3.12:6123
tcp46      0      0  *.9999                 *.*                    LISTEN      131072 131072  88104      0 0x0100 0x00000106 java:88104
tcp6       0      0  ::1.7777               *.*                    LISTEN      131072 131072    999      0 0x0100 0x00000106 node:999
"""
_LINUX = """
LISTEN 0      4096       127.0.0.1:8899       0.0.0.0:*    users:(("python3",pid=6123,fd=7))
LISTEN 0      4096               *:9999             *:*    users:(("java",pid=88104,fd=12))
LISTEN 0      128             [::]:7777          [::]:*    users:(("node",pid=999,fd=3))
"""


def _canned(outputs: dict[str, str]):
    def run(cmd, timeout=5.0):
        for key, text in outputs.items():
            if key in " ".join(cmd):
                return text
        return ""
    return run


def test_windows_bindings_merge_ipv4_and_ipv6(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ports, "_run", _canned({"TCPv6": _WIN_TCP6, "TCP": _WIN_TCP}))
    java = ports._bindings_windows(9999)
    assert java == [{"local_address": "0.0.0.0", "pid": 4321}, {"local_address": "::", "pid": 4321}]
    assert ports.loopback_only(java) is False
    chart = ports._bindings_windows(8899)
    assert {b["local_address"] for b in chart} == {"127.0.0.1", "::1"}
    assert ports.loopback_only(chart) is True


def test_darwin_bindings_read_the_local_column(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ports, "_run", _canned({"netstat": _MAC}))
    assert ports._bindings_darwin(8899) == [{"local_address": "127.0.0.1", "pid": 6123}]
    assert ports._bindings_darwin(9999) == [{"local_address": "*", "pid": 88104}]
    assert ports._bindings_darwin(7777) == [{"local_address": "::1", "pid": 999}]
    assert ports.loopback_only(ports._bindings_darwin(9999)) is False
    assert ports.loopback_only(ports._bindings_darwin(7777)) is True


def test_linux_bindings_read_ss_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ports, "_run", _canned({"ss": _LINUX}))
    assert ports._bindings_linux(8899) == [{"local_address": "127.0.0.1", "pid": 6123}]
    assert ports._bindings_linux(9999) == [{"local_address": "*", "pid": 88104}]
    assert ports._bindings_linux(7777) == [{"local_address": "::", "pid": 999}]


def test_unknown_bindings_are_none_not_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative control: an empty answer (tool missing / no permission) must not read as loopback-only."""
    monkeypatch.setattr(ports, "_run", lambda cmd, timeout=5.0: "")
    assert ports.listener_bindings(9999) == []
    assert ports.loopback_only([]) is None


def test_darwin_listener_detection_does_not_trust_the_state_column(monkeypatch: pytest.MonkeyPatch) -> None:
    """托管 macOS 26 runner 把别的进程的监听 socket 打成 CLOSED（矩阵首跑抓到）；已连接的 socket 永远带具体外端地址。"""
    text = (
        "Proto Recv-Q Send-Q  Local Address          Foreign Address        (state)   rxbytes txbytes rhiwat shiwat process:pid\n"
        "tcp4       0      0  127.0.0.1.49683        *.*                    CLOSED      0       0    131072 131072  Python:22808\n"
        "tcp4       0      0  127.0.0.1.49683        127.0.0.1.50001        ESTABLISHED 0       0    131072 131072  Python:22808\n"
        "tcp4       0      0  127.0.0.1.8899         *.*                    LISTEN      0       0    131072 131072  python3.12:6123\n"
    )
    monkeypatch.setattr(ports, "_run", lambda cmd, timeout=15.0: text)
    assert ports._listener_pids_darwin(49683) == [22808], "CLOSED 状态列不可信：外端 *.* 才是监听的签名"
    assert ports._bindings_darwin(49683) == [{"local_address": "127.0.0.1", "pid": 22808}]
    assert ports._listener_pids_darwin(8899) == [6123]
    assert ports._listener_pids_darwin(50001) == [], "已连接的对端不是监听者"
