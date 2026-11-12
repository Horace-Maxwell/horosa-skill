"""HTTP 传输的「哪些地址真的能连上」：横幅、421 回包与 DNS-rebinding 白名单说同一件事（MCP-09）。

🔴 `serve --host 0.0.0.0` 监听所有网卡，但 Host 白名单只有绑定地址本身、回环与 Docker 的宿主别名
（mcp_auth.build_transport_security）。同网段机器用 `http://192.168.1.5:8765/mcp` 来连，Host 头是 `192.168.1.5:8765`
→ 421。旧横幅却印着 `http://0.0.0.0:8765/mcp` 与一条照抄 0.0.0.0 的 `claude mcp add`——一个连不上的地址，
而且从头到尾不提 HOROSA_MCP_ALLOWED_HOSTS。防护本身不动（白名单就是它的意义）；这里只负责把规则说出来：
哪些地址现在就能用、哪些要先加进白名单、要加的那一行原样是什么。
"""
from __future__ import annotations

import ipaddress
import socket
import threading
from typing import Any

WILDCARD_HOSTS = frozenset({"0.0.0.0", "::", ""})
_LOOPBACK_NAMES = ("127.0.0.1", "localhost")


def _url_host(host: str) -> str:
    """URL / Host 头里的写法：IPv6 字面量要加方括号。"""
    try:
        return f"[{host}]" if ipaddress.ip_address(host).version == 6 else host
    except ValueError:
        return host


def _matches(host_header: str, allowed: list[str]) -> bool:
    """与 SDK 的 TransportSecurityMiddleware._validate_host 同一判据（精确匹配，或 `name:*` 匹配任意端口）。"""
    if host_header in allowed:
        return True
    return any(item.endswith(":*") and host_header.startswith(item[:-2] + ":") for item in allowed)


def local_interface_addresses(timeout: float = 1.0) -> list[str]:
    """本机网卡上的非回环 IPv4 地址（只查本机：主机名解析在本机 hosts / mDNS 内完成，超时就当没有）。"""
    found: list[str] = []

    def lookup() -> None:
        try:
            infos = socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET)
        except OSError:
            return
        for info in infos:
            address = str(info[4][0])
            try:
                parsed = ipaddress.ip_address(address)
            except ValueError:
                continue
            if not parsed.is_loopback and not parsed.is_link_local and address not in found:
                found.append(address)

    worker = threading.Thread(target=lookup, name="horosa-serve-interfaces", daemon=True)
    worker.start()
    worker.join(timeout)
    return list(found)


def describe_bind(
    host: str, port: int, path: str, allowed_hosts: list[str], *,
    user_extra: list[str] | None = None, interfaces: list[str] | None = None, hostname: str | None = None,
) -> dict[str, Any]:
    """绑定 `host:port` 后：能直接连上的 URL、需要先放行的 URL，以及要加的那一行环境变量。

    `answering`：Host 头在白名单里的地址（回环、Docker 宿主别名、具体的绑定地址）——现在就能用；
    `blocked`：会被 421 拒掉的局域网地址（只在绑定到 0.0.0.0 / :: 时存在）；
    `allowed_hosts_line`：把 `blocked` 全部放行的那一行（已有的 HOROSA_MCP_ALLOWED_HOSTS 值会并进去）。
    """
    wildcard = host in WILDCARD_HOSTS
    loopback_bind = host in {"127.0.0.1", "localhost", "::1"}
    candidates: list[str] = []
    if wildcard or loopback_bind:
        candidates += list(_LOOPBACK_NAMES)
    if not wildcard and host not in candidates:
        candidates.append(host)
    if wildcard:
        candidates.append("host.docker.internal")  # 只在容器里有意义；容器里的客户端用它连宿主
    answering = [f"http://{_url_host(item)}:{port}{path}" for item in candidates if _matches(f"{_url_host(item)}:{port}", allowed_hosts)]
    blocked_hosts: list[str] = []
    if wildcard:
        names = [*(interfaces if interfaces is not None else local_interface_addresses())]
        hostname = (socket.gethostname() if hostname is None else hostname).strip()
        if hostname and hostname not in names and hostname != "localhost":
            names.append(hostname)
        blocked_hosts = [item for item in names if not _matches(f"{_url_host(item)}:{port}", allowed_hosts)]
    line = None
    if blocked_hosts:
        # 已经设着的 HOROSA_MCP_ALLOWED_HOSTS 要并进去：照抄这一行不能把用户原有的放行项冲掉。
        line = "HOROSA_MCP_ALLOWED_HOSTS=" + ",".join([*(user_extra or []), *(f"{_url_host(item)}:*" for item in blocked_hosts)])
    return {
        "answering": answering,
        "blocked": [f"http://{_url_host(item)}:{port}{path}" for item in blocked_hosts],
        "allowed_hosts": list(allowed_hosts),
        "allowed_hosts_line": line,
    }


def rejection_text(host_header: str | None, allowed_hosts: list[str]) -> str:
    """421 的回包正文：被拒的 Host、白名单、以及要加的那一行（双语，客户端日志里能直接看懂）。"""
    shown = (host_header or "").strip() or "(none)"
    name = shown.rsplit(":", 1)[0] if shown.count(":") == 1 or shown.startswith("[") else shown
    add = f"{name}:*" if shown != "(none)" else "<host>:*"
    return (
        f"Invalid Host header: {shown}\n"
        f"Host 头 {shown} 不在白名单里（DNS-rebinding 防护）。允许的 Host / allowed hosts: {', '.join(allowed_hosts)}\n"
        f"在启动 serve 的环境里加上 / add to the environment that starts `serve`, then restart it:\n"
        f"HOROSA_MCP_ALLOWED_HOSTS={add}\n"
    )


class HostGuidanceMiddleware:
    """ASGI 外层：Host 不在白名单 → 421 + `rejection_text`；其余原样交给 SDK（SDK 自己的校验照旧在里面跑一遍）。

    判据与 SDK 完全相同（`_matches` 抄的就是它），所以这层不会放进 SDK 会拒的请求，也不会拒 SDK 会放的请求，
    只是把「Invalid Host header」那一句换成能照着做的说明。
    """

    def __init__(self, app: Any, allowed_hosts: list[str]) -> None:
        self.app = app
        self.allowed_hosts = list(allowed_hosts)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            host = next((value.decode("latin-1") for key, value in scope.get("headers") or [] if key == b"host"), None)
            if not host or not _matches(host, self.allowed_hosts):
                body = rejection_text(host, self.allowed_hosts).encode("utf-8")
                await send({"type": "http.response.start", "status": 421,
                            "headers": [(b"content-type", b"text/plain; charset=utf-8"), (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)
