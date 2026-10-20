"""测试永不连桌面版的 8899 / 9999（tests/conftest.py 的会话级护栏）。

**为什么旧检查抓不到**：`run_ci_gates.py` 把两个后端钉到不可达的 :9，CI 里那两个端口上也没人——所以「测试打到了桌面版」
在 CI 永远不可见；只在维护机直接 `uv run pytest` 且桌面版开着时发生（2026-10-20 审计：34 处直接用默认端口构造 Settings，
`test_uninstall_dry_run_then_execute` 一条就探了 20 s）。负向对照：去掉 conftest 的护栏，本文件第一条在维护机上连得上桌面版即红。
"""

from __future__ import annotations

import os
import socket

import pytest

from conftest import DESKTOP_REFUSAL


@pytest.mark.parametrize("port", [8899, 9999])
def test_connecting_to_a_desktop_port_is_refused_by_the_guard(port: int) -> None:
    with pytest.raises(ConnectionRefusedError, match="desktop app"):
        socket.create_connection(("127.0.0.1", port), timeout=1)
    probe = socket.socket()
    try:
        assert probe.connect_ex(("127.0.0.1", port)) != 0
    finally:
        probe.close()
    assert "8899/9999" in DESKTOP_REFUSAL


def test_both_backends_default_to_the_unreachable_ci_address() -> None:
    for var in ("HOROSA_SERVER_ROOT", "HOROSA_CHART_SERVER_ROOT"):
        value = os.environ.get(var, "")
        assert value, var
        assert ":8899" not in value and ":9999" not in value, f"{var}={value} points at the desktop app"


def test_other_loopback_ports_still_connect() -> None:
    """护栏只拦那两个端口：测试自己起的监听照常能连。"""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        client = socket.create_connection(server.getsockname(), timeout=2)
        client.close()
    finally:
        server.close()
