"""MCP 结果的 isError 分两类（审计待决项 1(c)）；不存在的工具名回结构化 tool.unknown（S-29）；卦义工具的 name 广告成卦名（S-22）。

- 真失败（模型自己能改的入参错、runtime / 内部错误…）isError:true；在问用户的（闸门、缺只有用户知道的事实、地名歧义）不标。
- 以前不存在的工具名是 SDK 的裸「Unknown tool: …」；horosa_cn_bazi_direct 现在不单独广告，要点名替代写法。
负向对照（实跑过）：_mark_error 直接返回 converted → 第一个用例红；call_tool 遇未知名回落 super() → 第二个用例红。
"""
from __future__ import annotations

import asyncio
import json

import pytest

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import create_mcp_server

BIRTH = {"date": "1990-05-03", "time": "08:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}


@pytest.fixture()
def mcp(tmp_path):
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    return create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)


def _call(mcp, name, args):
    return asyncio.run(mcp.call_tool(name, args))


def test_real_failures_are_marked_and_questions_are_not(mcp, monkeypatch) -> None:
    monkeypatch.delenv("HOROSA_MCP_ISERROR", raising=False)
    assert _call(mcp, "horosa_astro_chart", {**BIRTH, "hsyss": 3, "defaults_accepted": True}).is_error is True   # 写错键名：模型自己改
    assert not _call(mcp, "horosa_cn_bazi_birth", BIRTH).is_error                                            # 闸门在问
    assert not _call(mcp, "horosa_cn_bazi_birth", {**BIRTH, "defaults_accepted": True}).is_error             # 缺性别：要问用户
    assert not _call(mcp, "horosa_knowledge_registry", {}).is_error
    monkeypatch.setenv("HOROSA_MCP_ISERROR", "0")
    assert not _call(mcp, "horosa_astro_chart", {**BIRTH, "hsyss": 3, "defaults_accepted": True}).is_error   # 关回旧行为


def test_an_unknown_tool_name_gets_a_structured_answer(mcp) -> None:
    result = _call(mcp, "horosa_cn_bazi_direct", {})
    body = json.loads(result.content[0].text)
    assert result.is_error and body["code"] == "tool.unknown" and body["details"]["replacement"] == "horosa_cn_bazi_birth"
    body = json.loads(_call(mcp, "horosa_nope", {}).content[0].text)
    assert body["code"] == "tool.unknown" and "agent_recovery" in body["details"]


def test_hexagram_name_is_advertised_as_a_list_of_names(mcp) -> None:
    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
    for name in ("horosa_cn_gua_desc", "horosa_cn_gua_meiyi"):
        prop = tools[name].input_schema["properties"]["name"] if hasattr(tools[name], "input_schema") else tools[name].inputSchema["properties"]["name"]
        assert prop["type"] == "array" and "当事人" not in prop["description"]
