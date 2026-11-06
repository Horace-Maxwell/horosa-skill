"""`serve` 的流程：传输与绑定校验 → 端口预检 → 启动横幅 → 起 runtime → 跑 MCP server → 退出时收尾。"""
from __future__ import annotations

import os
import sys
import threading

import typer

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import RuntimeError
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces import runtime_helpers
from horosa_skill.surfaces.refusals import _emit_refusal, _refuse

_TRANSPORT_ALIASES = {
    "http": "streamable-http",
    "streamable_http": "streamable-http",
    "streamablehttp": "streamable-http",
    "shttp": "streamable-http",
}
_TRANSPORTS = {"streamable-http", "stdio", "sse"}


def _normalized_transport(value: str) -> str:
    text = (value or "").strip().lower()
    text = _TRANSPORT_ALIASES.get(text, text)
    if text not in _TRANSPORTS:
        raise typer.BadParameter(
            f"未知传输 `{value}`。可选：streamable-http（默认）、stdio、sse（legacy）。"
            "注意 `http` 是 Claude Code 注册命令里的说法，这里请写 streamable-http。"
        )
    return text


def _mask_token(token: str | None) -> str:
    if not token:
        return ""
    return f"{token[:4]}…{token[-2:]}" if len(token) > 8 else "****"


def _start_stdio_runtime_warmup(manager: HorosaRuntimeManager) -> None:
    def _warmup() -> None:
        try:
            manager.start_local_services()
        except RuntimeError as exc:
            # 预热失败推迟不了问题只会掩盖它：stderr 一行警告（stdio 协议流在 stdout，不受影响）。
            sys.stderr.write(f"[horosa] runtime 预热失败（首次调用时会重试）：{exc.code} {exc}\n")
            sys.stderr.flush()

    threading.Thread(target=_warmup, name="horosa-stdio-runtime-warmup", daemon=True).start()


def _run_serve(
    *,
    transport: str,
    host: str | None,
    port: int | None,
    token: str | None,
    allow_unauthenticated: bool,
    skip_runtime_start: bool,
    stop_runtime_on_exit: bool,
) -> None:
    settings = Settings.from_env()
    # 🔴 `--transport http` 是最常见的手误（Claude Code 的 `claude mcp add --transport http` 用的
    # 就是这个词）。旧实现把未知值原样传给 SDK，得到的是一句不知所云的内部报错。
    transport = _normalized_transport(transport)
    # host/port 缺省来自 env（旧实现把 typer 的字面默认写死，于是 docker-compose 里设的
    # HOROSA_SKILL_HOST/PORT 永远不生效 —— 容器只监听 127.0.0.1，宿主怎么连都连不上）。
    if host is not None:
        settings.host = host
    if port is not None:
        settings.port = port
    host, port = settings.host, settings.port
    token = (token or os.environ.get("HOROSA_MCP_TOKEN", "") or "").strip() or None
    if token:
        os.environ["HOROSA_MCP_TOKEN"] = token
    if transport != "stdio" and host not in {"127.0.0.1", "localhost", "::1"}:
        if not token and not allow_unauthenticated:
            _emit_refusal(
                "serve.token_required",
                f"绑定到非回环地址 {host} 而没有设置访问令牌 —— 已拒绝启动。",
                {
                    "host": host,
                    "next_action": (
                        "设 --token <随机串>（或 HOROSA_MCP_TOKEN），客户端在 Authorization: Bearer "
                        "头里带上它；确实想裸奔请显式加 --allow-unauthenticated。"
                    ),
                    "why": (
                        "本 server 能读写本机记忆库、生成文件、驱动本地 runtime。"
                        "对外绑定且无鉴权 = 同网段任何人都能做这些事。"
                    ),
                },
            )
        if not token:
            typer.echo(
                f"⚠️  正在以**无鉴权**方式绑定 {host}:{port}，且没有 TLS。"
                "同网段的任何人都能调用本机的 Horosa 工具、读你的记忆库。仅在可信网络里这么做。",
                err=True,
            )
    manager = runtime_helpers._runtime_manager(settings)
    # 🔴 端口先探再起：8765 被占时旧实现让 uvicorn 抛裸 traceback（OSError: [Errno 48]），
    # 而这是**最常见**的一次失败 —— 用户在两个终端里各起一个 serve。
    if transport != "stdio":
        from horosa_skill.runtime.ports import port_bindable, port_holders

        if not port_bindable(port, host if host not in {"0.0.0.0", "::"} else "127.0.0.1"):
            holders = port_holders(port)
            _emit_refusal(
                "serve.port_in_use",
                f"端口 {port} 已被占用，MCP server 无法监听。",
                {
                    "host": host,
                    "port": port,
                    "holders": holders,
                    "next_action": (
                        f"换端口：`--port <其它端口>` 或设 HOROSA_SKILL_PORT；"
                        "或关掉上面点名的进程（本工具不会代为终止）。"
                    ),
                },
            )
    service = HorosaSkillService(settings, runtime_manager=manager)
    # 🔴 横幅必须在启动 runtime **之前**打印：start_local_services 可以阻塞到 45 秒
    # （首次更久），期间用户盯着一个没有任何输出的终端，无从判断是卡住了还是在装。
    if transport != "stdio":
        path = "/sse" if transport == "sse" else "/mcp"
        typer.echo(
            f"Horosa Skill MCP 正在 http://{host}:{port}{path} 监听"
            f"（{transport}{'（legacy）' if transport == 'sse' else ''}，{len(TOOL_DEFINITIONS)} 个技法工具）。\n"
            + (f"访问令牌：已启用（Authorization: Bearer {_mask_token(token)}）。\n" if token else "")
            + f"接入 Claude Code：claude mcp add horosa --transport http http://{host}:{port}{path}\n"
            f"其他客户端：uv run horosa-skill client config --format <client>（见 README「接入 AI 客户端」）。\n"
            + ("正在启动本机 runtime（首次可能要几分钟）……" if not skip_runtime_start else ""),
            err=True,
        )
    started_now = False
    if not skip_runtime_start:
        if transport == "stdio":
            _start_stdio_runtime_warmup(manager)
        else:
            try:
                start_result = manager.start_local_services()
                started_now = not start_result.get("already_running", False)
            except RuntimeError as exc:
                _refuse(exc)
    from horosa_skill.runtime import registry as _registry

    try:
        _registry.attach_client(settings.runtime_state_path, pid=os.getpid(), transport=transport)
    except OSError:
        pass
    try:
        # 只有 serve 用得到 MCP SDK，而它占 CLI 启动的三成：放在这里 import（tests/test_layering.py 锁）。
        from horosa_skill.surfaces.mcp_server import run_mcp_server

        run_mcp_server(settings, transport=transport, service=service)
    finally:
        try:
            _registry.detach_client(settings.runtime_state_path, pid=os.getpid())
        except OSError:
            pass
        # 🔴 默认**保温**。旧行为是「这次 serve 起的就在退出时停掉」——而 runtime 是**共享**的：
        # Claude Desktop 与 Cursor 同时挂着时，关掉其中一个会把另一个的后端一起停掉；
        # 而重启一次要几十秒到几分钟。要恢复旧行为请显式加 --stop-runtime-on-exit。
        if stop_runtime_on_exit and started_now and transport != "stdio":
            others = _registry.live_clients(manager.load_runtime_state(), exclude_pid=os.getpid())
            if others:
                typer.echo(
                    f"还有 {len(others)} 个客户端挂在这份 runtime 上，未停止（--stop-runtime-on-exit 让位于它们）。",
                    err=True,
                )
            else:
                try:
                    manager.stop_local_services()
                except RuntimeError:
                    pass
