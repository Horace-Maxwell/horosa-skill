"""Streamable HTTP 的传输安全（Host / Origin 白名单）与静态 bearer token 校验。"""
from __future__ import annotations

import os
from typing import Any


def build_transport_security(host: str, port: int) -> Any:
    """DNS-rebinding 防护的允许 Host 列表。

    🔴 SDK 的缺省只在 host 是回环时开启，且允许列表**只有**回环三种写法。两个后果：
      · Docker Desktop 里的客户端（Open WebUI / n8n / Dify）发的是 `Host: host.docker.internal:8765`
        → 一律 421，症状是「服务明明在跑，容器里就是连不上」；
      · 绑到 `0.0.0.0` 时 SDK **完全不开**防护 —— 恰恰是最需要它的那种绑法。
    这里两边都补上：把实际绑定的 host、回环、以及 Docker 的宿主别名都放行，并允许用
    HOROSA_MCP_ALLOWED_HOSTS 追加（逗号分隔）。
    """
    from mcp.server.transport_security import TransportSecuritySettings

    extra = [
        item.strip()
        for item in (os.environ.get("HOROSA_MCP_ALLOWED_HOSTS", "") or "").split(",")
        if item.strip()
    ]
    hosts = [
        f"{host}:*", "127.0.0.1:*", "localhost:*", "[::1]:*", "host.docker.internal:*", *extra
    ]
    origins = [f"http://{item}" for item in hosts] + [f"https://{item}" for item in hosts]
    # 去重但保序（列表进日志/报错时可读）
    seen: set[str] = set()
    hosts = [h for h in hosts if not (h in seen or seen.add(h))]
    seen = set()
    origins = [o for o in origins if not (o in seen or seen.add(o))]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=origins
    )


class StaticTokenVerifier:
    """单个共享 Bearer token 的校验器（`--token` / HOROSA_MCP_TOKEN）。

    不是 OAuth，也不假装是：非回环绑定时至少要有**一道**门，而共享 token 是唯一能让
    Open WebUI / n8n / Dify 这类只会填一个 Authorization 头的客户端用起来的形式。
    比较走 `hmac.compare_digest`，不给计时侧信道。
    """

    def __init__(self, token: str) -> None:
        self._token = token

    async def verify_token(self, token: str) -> Any:
        import hmac

        from mcp.server.auth.provider import AccessToken

        if not token or not hmac.compare_digest(token, self._token):
            return None
        return AccessToken(token=token, client_id="horosa-skill", scopes=[], expires_at=None)


def build_auth_settings(host: str, port: int, token: str | None) -> Any:
    """有 token 时构造 AuthSettings（SDK 据此给 401 + WWW-Authenticate）。"""
    if not token:
        return None
    from mcp.server.auth.settings import AuthSettings

    base = f"http://{'127.0.0.1' if host in {'0.0.0.0', '::'} else host}:{port}"
    return AuthSettings(issuer_url=base, resource_server_url=None)
