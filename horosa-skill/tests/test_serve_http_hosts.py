"""MCP-09 / C-21：HTTP 传输说出真话——横幅、421 回包、令牌比对与掩码。

- `serve --host 0.0.0.0`：横幅只把**真能连上**的地址当连接地址给出，局域网地址单列为「需先放行」，并给出原样可抄的
  `HOROSA_MCP_ALLOWED_HOSTS=…` 一行；421 回包说同样的话。DNS-rebinding 防护本身不变（判据与 SDK 逐条一致）。
- 非 ASCII 的 Bearer 头不再是 HTTP 500（`hmac.compare_digest` 对含非 ASCII 的 str 抛 TypeError）。
- 令牌掩码不再露出 9 位令牌里的 6 位。
"""
from __future__ import annotations

import asyncio

import pytest

from horosa_skill.surfaces import mcp_auth, mcp_hosts, serve_flow


def _allowed(host: str, monkeypatch: pytest.MonkeyPatch, extra: str = "") -> list[str]:
    monkeypatch.setenv("HOROSA_MCP_ALLOWED_HOSTS", extra)
    return list(mcp_auth.build_transport_security(host, 8765).allowed_hosts)


def _sdk_accepts(allowed: list[str], host_header: str) -> bool:
    from mcp.server.transport_security import TransportSecurityMiddleware, TransportSecuritySettings

    middleware = TransportSecurityMiddleware(TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=allowed))
    return middleware._validate_host(host_header)


def test_wildcard_bind_lists_only_answering_addresses_and_the_exact_line_for_the_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = _allowed("0.0.0.0", monkeypatch)
    view = mcp_hosts.describe_bind("0.0.0.0", 8765, "/mcp", allowed, interfaces=["192.168.1.5"])

    assert "http://127.0.0.1:8765/mcp" in view["answering"] and "http://localhost:8765/mcp" in view["answering"]
    assert not any("0.0.0.0" in url for url in view["answering"]), "0.0.0.0 不是一个能连的地址"
    assert "http://192.168.1.5:8765/mcp" in view["blocked"]
    line = view["allowed_hosts_line"]
    assert line.startswith("HOROSA_MCP_ALLOWED_HOSTS=") and "192.168.1.5:*" in line.split("=", 1)[1].split(",")
    # 每一条「能连上」都是 SDK 真放行的；每一条「被拦」都是 SDK 真会拒的——说明与防护同一判据
    for url in view["answering"]:
        assert _sdk_accepts(allowed, url.split("//", 1)[1].split("/", 1)[0]), url
    for url in view["blocked"]:
        assert not _sdk_accepts(allowed, url.split("//", 1)[1].split("/", 1)[0]), url
    # 照抄那一行之后，被拦的地址就放行了
    after = _allowed("0.0.0.0", monkeypatch, line.split("=", 1)[1])
    assert all(_sdk_accepts(after, url.split("//", 1)[1].split("/", 1)[0]) for url in view["blocked"])


def test_the_line_keeps_what_the_user_already_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = _allowed("0.0.0.0", monkeypatch, "mybox.lan:*")
    view = mcp_hosts.describe_bind("0.0.0.0", 8765, "/mcp", allowed, user_extra=["mybox.lan:*"], interfaces=["10.0.0.7"], hostname="")
    assert view["allowed_hosts_line"] == "HOROSA_MCP_ALLOWED_HOSTS=mybox.lan:*,10.0.0.7:*"


def test_specific_and_loopback_binds_have_nothing_to_add(monkeypatch: pytest.MonkeyPatch) -> None:
    for host in ("127.0.0.1", "192.168.1.5"):
        view = mcp_hosts.describe_bind(host, 8765, "/mcp", _allowed(host, monkeypatch), interfaces=["192.168.1.5"])
        assert view["blocked"] == [] and view["allowed_hosts_line"] is None
        assert f"http://{host}:8765/mcp" in view["answering"]


def test_the_421_body_says_what_to_add_and_the_guard_matches_the_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = _allowed("0.0.0.0", monkeypatch)
    sent: list[dict] = []
    passed: list[str] = []

    async def inner(scope, receive, send):  # noqa: ANN001
        passed.append(dict(scope["headers"])[b"host"].decode())

    async def send(message):  # noqa: ANN001
        sent.append(message)

    app = mcp_hosts.HostGuidanceMiddleware(inner, allowed)
    for host in ("192.168.1.5:8765", "127.0.0.1:8765", "host.docker.internal:8765", "evil.example:8765"):
        asyncio.run(app({"type": "http", "headers": [(b"host", host.encode())]}, None, send))
        assert (host in passed) == _sdk_accepts(allowed, host), host
    bodies = [m["body"].decode("utf-8") for m in sent if m["type"] == "http.response.body"]
    statuses = [m["status"] for m in sent if m["type"] == "http.response.start"]
    assert statuses == [421, 421]
    assert "HOROSA_MCP_ALLOWED_HOSTS=192.168.1.5:*" in bodies[0] and "127.0.0.1:*" in bodies[0]


def test_serve_banner_on_a_wildcard_bind_names_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOROSA_MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.setattr(mcp_hosts, "local_interface_addresses", lambda timeout=1.0: ["192.168.1.5"])
    text = serve_flow._serve_banner(host="0.0.0.0", port=8765, transport="streamable-http", token="x" * 32, skip_runtime_start=True)
    assert "HOROSA_MCP_ALLOWED_HOSTS=" in text and "192.168.1.5:*" in text
    assert "claude mcp add horosa --transport http http://0.0.0.0" not in text
    assert "http://127.0.0.1:8765/mcp" in text


@pytest.mark.parametrize("presented", ["wröng", "令牌", "", "probe-token-0123456789x"])
def test_bearer_comparison_never_raises(presented: str) -> None:
    verifier = mcp_auth.StaticTokenVerifier("probe-token-0123456789")
    assert asyncio.run(verifier.verify_token(presented)) is None


def test_bearer_comparison_accepts_the_right_token_even_when_it_is_not_ascii() -> None:
    assert asyncio.run(mcp_auth.StaticTokenVerifier("probe-token-0123456789").verify_token("probe-token-0123456789")) is not None
    assert asyncio.run(mcp_auth.StaticTokenVerifier("令牌-0123456789").verify_token("令牌-0123456789")) is not None


@pytest.mark.parametrize("token", ["abcdefghi", "0123456789abcdef", "x" * 64, "短"])
def test_token_mask_never_shows_more_than_a_quarter(token: str) -> None:
    shown = serve_flow._mask_token(token).replace("…", "").replace("*", "")
    assert len(shown) * 4 <= len(token), (token, serve_flow._mask_token(token))
