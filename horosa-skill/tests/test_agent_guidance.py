from __future__ import annotations

from horosa_skill.agent_guidance import (
    PREFLIGHT_EXEMPT_TOOLS,
    TOOL_GUIDANCE,
    assert_guidance_covers_registered_tools,
    build_tool_docstring,
    build_tool_input_contract,
    build_validation_recovery,
    build_agent_guidance,
    validate_agent_preflight,
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
    assert guidance["tools"]["solarreturn"]["input_contract"]["required_for_real_call"] == [
        "date",
        "time",
        "zone",
        "lat",
        "lon",
        "datetime",
        "dirZone",
        "dirLat",
        "dirLon",
    ]


def test_all_enforced_tools_have_user_questions() -> None:
    guidance = build_agent_guidance(include_all=True)

    missing = [
        tool_name
        for tool_name, policy in guidance["tools"].items()
        if tool_name not in PREFLIGHT_EXEMPT_TOOLS and not policy["ask_if_missing"]
    ]
    assert missing == []


def test_agent_preflight_blocks_unconfirmed_calculation_tools() -> None:
    gate = validate_agent_preflight("liureng_gods", {"date": "2026-05-18"})

    assert gate["ok"] is False
    assert gate["code"] == "agent_guidance.required"
    assert "agent_confirmed_settings" in gate["confirmation_fields"]
    assert any(item["field"] == "guirengType" for item in gate["ask_if_missing"])
    assert gate["agent_recovery"]["must_ask_user"] is True
    assert "调用 `liureng_gods` 前需要先确认" in gate["agent_recovery"]["prompt_to_user"]


def test_predictive_input_contracts_are_explicit_for_agents() -> None:
    solarreturn = build_tool_input_contract("solarreturn")
    pd = build_tool_input_contract("pd")
    pdchart_doc = build_tool_docstring("pdchart")

    assert solarreturn["schema"] == "horosa.skill.input_contract.v1"
    assert solarreturn["confirmation_required"] is True
    assert {"datetime", "dirZone", "dirLat", "dirLon"} <= set(solarreturn["required_for_real_call"])
    assert "返照盘星与虚点" in solarreturn["output_contract"]
    assert solarreturn["example_payload"]["agent_confirmed_settings"] is True

    assert {"pdtype", "pdMethod", "pdTimeKey", "pdaspects"} <= set(pd["required_for_real_call"])
    assert "主限表格" in pd["output_contract"]
    assert "Required input for a real call" in pdchart_doc
    assert "主限法盘星体表格" in pdchart_doc


def test_agent_preflight_allows_confirmed_calculation_tools() -> None:
    gate = validate_agent_preflight("qimen", {"agent_confirmed_settings": True})

    assert gate["ok"] is True
    assert gate["mode"] == "agent_confirmed_settings"


def test_agent_preflight_exempts_registry_tools() -> None:
    gate = validate_agent_preflight("knowledge_registry", {})

    assert gate["ok"] is True
    assert gate["enforced"] is False


def test_agent_preflight_blocks_unconfirmed_dispatch() -> None:
    gate = validate_agent_preflight("dispatch", {"query": "帮我起一个盘"})

    assert gate["ok"] is False
    assert gate["code"] == "agent_guidance.required"
    assert any(item["field"] == "target technique" for item in gate["ask_if_missing"])


def test_validation_recovery_returns_prompt_for_incomplete_payload() -> None:
    recovery = build_validation_recovery(
        operation_name="tool.chart",
        tool_name="chart",
        errors=[{"loc": ("date",), "msg": "Field required", "type": "missing"}],
    )

    assert recovery["must_ask_user"] is True
    assert "调用 `chart` 前需要先确认" in recovery["prompt_to_user"]
    assert any(item["field"] == "date/time/place" for item in recovery["ask_if_missing"])
