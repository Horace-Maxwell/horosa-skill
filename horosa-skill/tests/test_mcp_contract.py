"""MCP wire-contract tests — assert what the CLIENT actually sees, via list_tools()/call_tool().

Why this file exists: `test_mcp_server.py` exercises the helper functions directly and never goes
through `srv.call_tool`, so an entire class of defects was invisible to CI — `horosa_tool_run` shipped
with a `{"kwargs": {"type": "string"}}` schema (uncallable, and it is the ONLY route to every technique
under HOROSA_MCP_COMPACT=1), four facade tools shipped with empty descriptions, and no tool had a title.
Every assertion here maps to one of those regressions.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from horosa_skill.config import Settings
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import _SERVER_INSTRUCTIONS, create_mcp_server


def _server(*, compact: bool = False):
    settings = Settings.from_env()
    settings.mcp_compact = compact
    return create_mcp_server(HorosaSkillService(settings), settings)


def _payload(result) -> dict:
    content = result[0] if not isinstance(result, tuple) else result[0][0]
    return json.loads(content.text)


@pytest.mark.parametrize("compact", [False, True])
def test_every_tool_is_discoverable_and_callable_shaped(compact: bool) -> None:
    tools = asyncio.run(_server(compact=compact).list_tools())
    assert tools, "server exposed zero tools"
    missing_description = [t.name for t in tools if not (t.description or "").strip()]
    missing_title = [t.name for t in tools if not (t.title or "").strip()]
    assert missing_description == [], f"tools with no description (invisible to model): {missing_description}"
    assert missing_title == [], f"tools with no title (client shows the raw id): {missing_title}"
    for tool in tools:
        properties = tool.inputSchema.get("properties", {})
        assert "kwargs" not in properties, (
            f"{tool.name} advertises a raw `kwargs` param — its __signature__ is missing, so FastMCP "
            "introspected **kwargs and the tool is effectively uncallable"
        )
        assert tool.annotations is not None, f"{tool.name} has no annotations"
        assert tool.annotations.openWorldHint is False, f"{tool.name} must be local-first (openWorld=False)"


def test_compact_mode_exposes_a_usable_universal_runner() -> None:
    tools = asyncio.run(_server(compact=True).list_tools())
    runner = next(t for t in tools if t.name == "horosa_tool_run")
    properties = runner.inputSchema.get("properties", {})
    assert "tool_name" in properties and "request" in properties
    # 公共起盘字段必须直接可填，否则每次调用都得包一层 request
    for field in ("date", "time", "zone", "lat", "lon"):
        assert field in properties, f"horosa_tool_run should accept {field} directly"


def test_compact_tool_run_reaches_a_technique_through_call_tool() -> None:
    server = _server(compact=True)
    result = asyncio.run(
        server.call_tool("horosa_tool_run", {"tool_name": "export_registry", "request": {"technique": "qimen"}})
    )
    body = _payload(result)
    assert body.get("ok") is True, body
    assert body.get("tool") == "export_registry"


def test_tool_run_keeps_the_clarification_gate_and_recovery_contract() -> None:
    server = _server(compact=True)
    result = asyncio.run(
        server.call_tool(
            "horosa_tool_run",
            {
                "tool_name": "qimen",
                "date": "2028-04-06",
                "time": "09:33:00",
                "zone": "+08:00",
                "lat": "31n13",
                "lon": "121e28",
            },
        )
    )
    body = _payload(result)
    assert body["code"] == "agent_guidance.required"
    assert body["details"]["agent_recovery"]["prompt_to_user"]


def test_tool_run_rejects_unknown_tool_names_structurally() -> None:
    body = _payload(asyncio.run(_server(compact=True).call_tool("horosa_tool_run", {"tool_name": "nope"})))
    assert body["code"] == "tool.unknown"


def test_entry_point_tools_are_marked_always_load() -> None:
    tools = asyncio.run(_server().list_tools())
    marked = {t.name for t in tools if (t.meta or {}).get("anthropic/alwaysLoad")}
    assert {"horosa_dispatch", "horosa_agent_guidance"} <= marked


def test_server_instructions_fit_the_client_budget() -> None:
    # 客户端约 2KB 截断；超了关键的「何时来搜我」会被砍掉。
    assert 0 < len(_SERVER_INSTRUCTIONS.encode("utf-8")) <= 2048


def test_advertised_schema_is_faithful_but_validation_is_loose() -> None:
    """广告保真、校验放松：字段描述/必填标记照登，但没有一个参数是 MCP 层必填。

    必填留在 MCP 层会做三件坏事：`request={…}` 逃生通道永远走不到、`{"lat": 39.9}` 在归一化之前
    就被拒、以及两者都绕过 agent_recovery 契约回一条裸 pydantic 错误。
    """
    tools = asyncio.run(_server().list_tools())
    qimen = next(t for t in tools if t.name == "horosa_cn_qimen")
    schema = qimen.inputSchema
    assert not schema.get("required"), "MCP 层不应有必填参数（必填语义走 [required] 标记 + 内层校验）"
    assert schema["properties"]["date"]["description"].startswith("[required]")
    assert schema["properties"]["lat"]["type"] == ["string", "number"], "归一化能吸收的键要放宽广告类型"
    assert "$ref" not in json.dumps(schema), "残留 $ref 会让 pydantic 构不出 arg model"


def test_numeric_coordinates_reach_normalization_instead_of_being_rejected() -> None:
    result = asyncio.run(
        _server().call_tool(
            "horosa_cn_qimen",
            {
                "date": "2028-04-06",
                "time": "09:33:00",
                "zone": "+08:00",
                "lat": 39.9,
                "lon": 116.4,
                "defaults_accepted": True,
            },
        )
    )
    body = _payload(result)
    assert body["ok"] is True, body
    assert body["input_normalized"]["lat"] == "39n54", "数字经纬度应被 normalize_request_payload 吸收"


def test_request_escape_hatch_works_over_the_wire() -> None:
    result = asyncio.run(
        _server().call_tool(
            "horosa_cn_qimen",
            {
                "request": {
                    "date": "2028-04-06",
                    "time": "09:33:00",
                    "zone": "+08:00",
                    "lat": "31n13",
                    "lon": "121e28",
                    "defaults_accepted": True,
                }
            },
        )
    )
    assert _payload(result)["ok"] is True


def test_error_paths_return_a_conformant_envelope() -> None:
    """错误也必须是信封：否则一旦声明 outputSchema，出参校验会把澄清闸打成协议级 ToolError。"""
    gate = _payload(
        asyncio.run(
            _server().call_tool(
                "horosa_cn_qimen",
                {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
            )
        )
    )
    for key in ("ok", "tool", "version", "input_normalized", "error"):
        assert key in gate, f"gate error missing envelope key {key}: {gate}"
    assert gate["ok"] is False and gate["tool"] == "qimen"
    # 顶层镜像键保持向后兼容（旧调用方按 code/message/details 读）
    assert gate["code"] == gate["error"]["code"] == "agent_guidance.required"


def test_structured_output_is_opt_in_and_keeps_the_gate_working(monkeypatch: pytest.MonkeyPatch) -> None:
    default_tools = asyncio.run(_server().list_tools())
    assert all(t.outputSchema is None for t in default_tools), (
        "outputSchema 默认必须关闭——claude-code#25081（带 outputSchema 时工具列表静默消失）未确认修复"
    )
    monkeypatch.setenv("HOROSA_OUTPUT_SCHEMA", "1")
    server = _server()
    opted_in = asyncio.run(server.list_tools())
    assert any(t.outputSchema for t in opted_in)
    gate = _payload(
        asyncio.run(
            server.call_tool(
                "horosa_cn_qimen",
                {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
            )
        )
    )
    assert gate["code"] == "agent_guidance.required", "开了结构化输出后澄清闸仍须原样工作"


def test_toolsets_env_filters_technique_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    full = len(asyncio.run(_server().list_tools()))
    monkeypatch.setenv("HOROSA_TOOLSETS", "astro")
    filtered = asyncio.run(_server().list_tools())
    assert 0 < len(filtered) < full
    # 门面工具不受分组过滤影响（否则用户开了白名单就再也问不到路）
    assert {"horosa_dispatch", "horosa_agent_guidance"} <= {t.name for t in filtered}
