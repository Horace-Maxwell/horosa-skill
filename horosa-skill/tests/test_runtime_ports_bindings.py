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
