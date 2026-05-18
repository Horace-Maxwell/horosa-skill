from __future__ import annotations

from horosa_skill.agent_guidance import (
    TOOL_GUIDANCE,
    assert_guidance_covers_registered_tools,
    build_agent_guidance,
)
from horosa_skill.engine.registry import TOOL_DEFINITIONS


def test_agent_guidance_covers_every_registered_tool() -> None:
    assert_guidance_covers_registered_tools()
    assert set(TOOL_GUIDANCE) == set(TOOL_DEFINITIONS)


def test_liureng_guidance_requires_clarification_before_call() -> None:
    guidance = build_agent_guidance(tool_name="liureng_gods")
    policy = guidance["tools"]["liureng_gods"]

    fields = {item["field"] for item in policy["ask_if_missing"]}
    assert {"date/time", "location", "question", "guirengType", "isDiurnal"} <= fields
    assert any(default["field"] == "guirengType" and default["value"] == 2 for default in policy["safe_defaults"])
    assert any("Do not hand-calculate" in rule for rule in guidance["global_rules"])
    assert "horosa_cn_liureng_gods" == policy["mcp_name"]


def test_guidance_accepts_mcp_tool_name_alias() -> None:
    guidance = build_agent_guidance(tool_name="horosa_cn_qimen")

    assert guidance["ok"] is True
    assert list(guidance["tools"]) == ["qimen"]
    assert any(item["field"] == "question" for item in guidance["tools"]["qimen"]["ask_if_missing"])


def test_guidance_all_includes_all_tools_and_report_memory_notes() -> None:
    guidance = build_agent_guidance(include_all=True)

    assert guidance["ok"] is True
    assert set(guidance["tools"]) == set(TOOL_DEFINITIONS)
    assert "horosa_report_render" in guidance["report_and_memory"]
    assert "horosa_memory_query" in guidance["report_and_memory"]
