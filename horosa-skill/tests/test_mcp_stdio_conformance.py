"""通过**真 stdio 传输**跑一遍协议：起子进程、握手、列工具、调工具。

**为什么旧检查抓不到**：整仓的 MCP 测试都在**进程内**调 `create_mcp_server(...).call_tool(...)`。
那条路绕开了传输层，于是三类问题永远看不见：
  · 任何写到 stdout 的杂字节（一句 print、一条 warning、一个进度条）都会污染 JSON-RPC 帧流 ——
    进程内测试根本不看 stdout；
  · 启动期异常（import 顺序、env 读取、runtime 探测）在进程内被 fixture 绕过去了；
  · initialize 的 instructions / serverInfo / capabilities 是握手时才产生的。

⚠️ 实测纠正一个想当然：**握手成功并不证明 stdout 干净**。Python SDK 的客户端遇到解析不了的
行只记一条日志就跳过，照样握手成功 —— 本文件第一版就是这么写的，负向对照（注入一句
`print('starting horosa...')`）证明它抓不到。所以 stdout 干净由
`test_stdout_carries_only_json_rpc_frames` 逐行断言，不靠握手。
（别的客户端不一定这么宽容：Go/TS 实现见到坏行会直接断连。）

CI 可跑（`--skip-runtime-start`，不需要离线 runtime）。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anyio

PKG_ROOT = Path(__file__).resolve().parents[1]
INSTRUCTIONS_BUDGET_BYTES = 2048


def _server_params(tmp_path: Path, **env_extra: str):
    from mcp import StdioServerParameters

    env = {
        **os.environ,
        "HOROSA_RUNTIME_ROOT": str(tmp_path / "runtime"),
        "HOROSA_SKILL_DATA_DIR": str(tmp_path / "data"),
        "HOROSA_SERVER_ROOT": "http://127.0.0.1:9",
        "HOROSA_CHART_SERVER_ROOT": "http://127.0.0.1:9",
        "HOROSA_TRACE_ENABLED": "0",
        **env_extra,
    }
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "horosa_skill.surfaces.cli", "serve", "--transport", "stdio", "--skip-runtime-start"],
        env=env,
        cwd=str(PKG_ROOT),
    )


async def _with_session(params, body):
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            return await body(session, init)


def test_stdio_handshake_lists_every_tool(tmp_path) -> None:
    from horosa_skill import __version__
    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.surfaces.mcp_server import FACADE_TOOL_COUNT

    async def body(session, init):
        tools = await session.list_tools()
        return init, tools.tools

    init, tools = anyio.run(_with_session, _server_params(tmp_path), body)

    # 握手成功 = stdout 里没有一个杂字节（多一个字节帧就解析不了）。
    assert init.serverInfo.name == "Horosa Skill"
    assert init.serverInfo.version == __version__, "serverInfo 报的必须是我们的版本，不是 MCP SDK 的"
    assert init.instructions and len(init.instructions.encode("utf-8")) <= INSTRUCTIONS_BUDGET_BYTES
    assert init.capabilities.tools is not None
    assert len(tools) == FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS)


def test_stdio_tools_all_pass_the_cross_client_audit(tmp_path) -> None:
    """真传输取回的工具表，逐个过 verify_mcp_client_compat 的同一把尺子。"""
    sys.path.insert(0, str(PKG_ROOT / "scripts"))
    from verify_mcp_client_compat import audit_tool  # type: ignore[import-not-found]

    async def body(session, init):
        return (await session.list_tools()).tools

    tools = anyio.run(_with_session, _server_params(tmp_path), body)
    problems: list[str] = []
    for tool in tools:
        problems.extend(
            audit_tool(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "title": tool.title,
                    "annotations": tool.annotations.model_dump() if tool.annotations else None,
                    "inputSchema": tool.inputSchema,
                }
            )
        )
    assert problems == [], problems[:10]


def test_stdio_gate_returns_a_structured_envelope(tmp_path) -> None:
    """闸门触发时回的是结构化信封，而不是 isError 裸文本。"""
    async def body(session, init):
        return await session.call_tool("horosa_cn_liureng_gods", {"date": "2026-05-18"})

    result = anyio.run(_with_session, _server_params(tmp_path), body)
    payload = json.loads(result.content[0].text)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "agent_guidance.required"
    assert payload["details"]["agent_recovery"]["must_ask_user"] is True


def test_stdio_bad_request_is_recoverable_not_iserror(tmp_path) -> None:
    """把参数字符串化的客户端（Gemini CLI、旧版 Cursor、n8n/Dify 模板）传坏一次 JSON 时的表现。"""
    async def body(session, init):
        return await session.call_tool("horosa_knowledge_registry", {"request": "{bad json"})

    result = anyio.run(_with_session, _server_params(tmp_path), body)
    assert result.isError is not True, "坏 payload 必须是信封，不能变 isError 裸文本"
    payload = json.loads(result.content[0].text)
    assert payload["ok"] is False
    assert payload["code"] == "tool.invalid_payload"
    assert "agent_recovery" in payload["details"] or "next_action" in payload["details"]


def test_stdio_compact_surface_is_reachable(tmp_path) -> None:
    """精简面下 11 个门面工具，全部技法仍可经 horosa_tool_run 到达。"""
    from horosa_skill.surfaces.mcp_server import COMPACT_SURFACE_TOOL_COUNT

    async def body(session, init):
        return (await session.list_tools()).tools

    tools = anyio.run(_with_session, _server_params(tmp_path, HOROSA_MCP_COMPACT="1"), body)
    names = {tool.name for tool in tools}
    assert len(names) == COMPACT_SURFACE_TOOL_COUNT
    assert "horosa_tool_run" in names


def test_stdout_carries_only_json_rpc_frames(tmp_path) -> None:
    """stdout 的**每一行**都必须是 JSON。

    这条不靠握手来证明（见模块顶部说明）：直接把 initialize 帧喂给子进程，然后逐行检查它的
    stdout。一句 print、一条 warnings.warn(file=sys.stdout)、一个进度条都会在这里现形。
    """
    import subprocess

    params = _server_params(tmp_path)
    frames = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "conformance", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    stdin_text = "".join(json.dumps(frame) + "\n" for frame in frames)
    completed = subprocess.run(
        [params.command, *params.args],
        input=stdin_text, capture_output=True, text=True, timeout=180,
        env=params.env, cwd=params.cwd, check=False,
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert lines, f"stdout 一行都没有；stderr:\n{completed.stderr[-2000:]}"
    for index, line in enumerate(lines, 1):
        try:
            json.loads(line)
        except ValueError as exc:  # noqa: PERF203 - 报错要指出是哪一行
            raise AssertionError(
                f"stdout 第 {index} 行不是 JSON-RPC 帧（stdio 传输被污染）：{line[:200]!r} ({exc})"
            ) from exc
