"""回环目标必须绕开用户的 HTTP 代理。

实测过的症状（v0.37.0 修复前）：同一台机器、同一组健康后端，只要设上
`HTTPS_PROXY=http://127.0.0.1:1`，`horosa-skill doctor` 立刻从 `ok:true / issues:[]`
变成 `ok:false / ['services:not_running']` —— 两个端点都报不可达。

根因：httpx **没有**隐式的 localhost 代理豁免（只认显式 NO_PROXY 条目）。
Clash/VPN 用户（本产品的主要市场）默认就是这个状态。shell 层早就修过
（`start_horosa_local.sh` 的 `curl --noproxy '*'` 与 urllib 的 `ProxyHandler({})`），
Python 层一直没跟上 —— 这条测试就是让它不能再掉队。
"""

from __future__ import annotations

import http.server
import threading

import httpx
import pytest

from horosa_skill.engine.client import (
    HorosaPlainJsonClient,
    is_loopback_url,
    loopback_httpx_client,
)


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib naming
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, *args):  # 静音，别污染 pytest 输出
        return


@pytest.fixture()
def loopback_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://127.0.0.1:8899", True),
        ("http://127.0.0.2:8899", True),  # 整个 127.0.0.0/8 都是回环
        ("http://localhost:9999/common/time", True),
        ("http://[::1]:8765/mcp", True),
        ("http://192.168.1.10:8899", False),  # 网关模式：确实该走代理
        ("https://github.com/x", False),
    ],
)
def test_loopback_detection(url: str, expected: bool) -> None:
    assert is_loopback_url(url) is expected


def test_probe_succeeds_through_a_poisoned_proxy(loopback_server, monkeypatch) -> None:
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.setenv(var, "http://127.0.0.1:1")  # 端口 1 必然连不上
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    assert HorosaPlainJsonClient(loopback_server, timeout=3.0).probe() is True

    # 负向对照：不关 trust_env 的同一个请求必须失败 —— 证明代理**真的**在生效，
    # 否则这条测试会在「代理根本没被读取」的情况下假绿。
    with httpx.Client(timeout=3.0, trust_env=True) as poisoned:
        with pytest.raises(httpx.HTTPError):
            poisoned.get(loopback_server)


def test_non_loopback_keeps_trust_env(monkeypatch) -> None:
    """网关模式指向另一台机器时必须仍然尊重代理设置。"""
    with loopback_httpx_client("http://example.invalid:8899", timeout=1.0) as client:
        assert client.trust_env is True
    with loopback_httpx_client("http://127.0.0.1:8899", timeout=1.0) as client:
        assert client.trust_env is False
