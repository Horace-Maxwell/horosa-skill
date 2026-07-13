from __future__ import annotations

import pytest

from horosa_skill.schemas.tools import AgentGuidanceInput, BirthInput, DispatchInput, KnowledgeReadInput, KnowledgeRegistryInput, MemoryQueryInput, ReportRenderInput
from horosa_skill.surfaces.mcp_server import _agent_preflight_error, _merge_mcp_arguments, _normalize_mcp_request


def test_normalize_mcp_request_accepts_json_string_for_empty_request() -> None:
    payload = _normalize_mcp_request("{}", KnowledgeRegistryInput)
    assert payload == {}


def test_normalize_mcp_request_accepts_json_string_for_structured_request() -> None:
    payload = _normalize_mcp_request(
        '{"domain":"qimen","category":"door","key":"休门"}',
        KnowledgeReadInput,
    )
    assert payload == {"domain": "qimen", "category": "door", "key": "休门"}


def test_normalize_mcp_request_accepts_plain_dict() -> None:
    payload = _normalize_mcp_request({"query": "起一张当前星盘"}, DispatchInput)
    assert payload["query"] == "起一张当前星盘"
    assert payload["save_result"] is True


def test_normalize_mcp_request_rejects_non_object_payload() -> None:
    with pytest.raises(ValueError, match="request must be an object"):
        _normalize_mcp_request('["not","an","object"]', KnowledgeRegistryInput)


def test_merge_mcp_arguments_prefers_request_when_present() -> None:
    merged = _merge_mcp_arguments({"request": {"run_id": "abc"}, "tool": "chart"})
    assert merged == {"run_id": "abc"}


def test_normalize_mcp_request_accepts_flattened_memory_query_fields() -> None:
    payload = _normalize_mcp_request(
        _merge_mcp_arguments({"tool": "chart", "entity": "Horosa Smoke", "text": "事业", "artifact_kind": "report_pdf", "limit": 5}),
        MemoryQueryInput,
    )
    assert payload == {
        "tool": "chart",
        "entity": "Horosa Smoke",
        "text": "事业",
        "artifact_kind": "report_pdf",
        "limit": 5,
        "offset": 0,
        "include_payload": True,
    }


def test_normalize_mcp_request_coerces_human_friendly_birth_fields() -> None:
    payload = _normalize_mcp_request(
        {
            "date": "1995-06-03",
            "time": "5:30",
            "zone": 8,
            "lat": 31.2167,
            "lon": 121.4667,
            "ad": 1,
        },
        BirthInput,
    )

    assert payload["zone"] == "+08:00"
    assert payload["lat"] == "31n13"
    assert payload["lon"] == "121e28"
    assert payload["gpsLat"] == pytest.approx(31.2167)
    assert payload["gpsLon"] == pytest.approx(121.4667)


def test_normalize_mcp_request_accepts_report_render_fields() -> None:
    payload = _normalize_mcp_request(
        _merge_mcp_arguments(
            {
                "run_id": "run-1",
                "tool_name": "chart",
                "format": "pdf",
                "ai_report": {"executive_summary": "摘要"},
            }
        ),
        ReportRenderInput,
    )

    assert payload["run_id"] == "run-1"
    assert payload["tool_name"] == "chart"
    assert payload["format"] == "pdf"
    assert payload["ai_report"]["executive_summary"] == "摘要"


def test_normalize_mcp_request_accepts_agent_guidance_fields() -> None:
    payload = _normalize_mcp_request(
        {"tool_name": "horosa_cn_liureng_gods", "intent": "当前时间起大六壬", "include_all": False},
        AgentGuidanceInput,
    )

    assert payload == {
        "tool_name": "horosa_cn_liureng_gods",
        "intent": "当前时间起大六壬",
        "include_all": False,
    }


def test_mcp_agent_preflight_blocks_unconfirmed_calculation_tool() -> None:
    error = _agent_preflight_error("liureng_gods", {"date": "2026-05-18"})

    assert error is not None
    assert error["code"] == "agent_guidance.required"
    assert error["details"]["agent_recovery"]["must_ask_user"] is True
    assert any(item["field"] == "guirengType" for item in error["details"]["ask_if_missing"])


def test_mcp_agent_preflight_allows_confirmed_calculation_tool() -> None:
    assert _agent_preflight_error("liureng_gods", {"agent_confirmed_settings": True}) is None


def test_mcp_agent_preflight_blocks_unconfirmed_dispatch() -> None:
    error = _agent_preflight_error("dispatch", {"query": "帮我起一个盘"})

    assert error is not None
    assert error["code"] == "agent_guidance.required"
    assert error["details"]["agent_recovery"]["must_ask_user"] is True


def _make_service(tmp_path):
    from horosa_skill.config import Settings
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService

    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    return settings, HorosaSkillService(settings, store=MemoryStore(settings))


def test_mcp_full_mode_exposes_all_technique_tools(tmp_path) -> None:
    import asyncio

    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings, service = _make_service(tmp_path)
    tools = asyncio.run(create_mcp_server(service, settings).list_tools())
    names = {tool.name for tool in tools}
    # 9 个门面 + 全部技法平铺。
    assert len(names) == 9 + len(TOOL_DEFINITIONS)
    assert "horosa_cn_qimen" in names
    assert "horosa_tool_run" not in names


def test_mcp_compact_mode_exposes_facade_plus_tool_run(tmp_path) -> None:
    import asyncio

    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings, service = _make_service(tmp_path)
    settings.mcp_compact = True
    tools = asyncio.run(create_mcp_server(service, settings).list_tools())
    names = {tool.name for tool in tools}
    assert len(names) == 10
    assert "horosa_tool_run" in names and "horosa_cn_qimen" not in names
    # 技法目录随 docstring 在场（dispatch 与 tool_run 均可发现全部技法）。
    by_name = {tool.name: tool for tool in tools}
    assert "yizhangjing" in (by_name["horosa_tool_run"].description or "")
    assert "yizhangjing" in (by_name["horosa_dispatch"].description or "")


def test_mcp_compact_tool_run_executes_and_keeps_gate(tmp_path) -> None:
    from horosa_skill.surfaces.mcp_server import _agent_preflight_error

    settings, service = _make_service(tmp_path)
    # 直呼本地无网工具：export_registry。
    result = service.run_tool("export_registry", {"technique": "qimen"}, save_result=False)
    assert result.ok is True
    # 澄清闸在直呼通道不失守：未确认设置的 qimen 仍被拦。
    gate = _agent_preflight_error("qimen", {"date": "2028-04-06"})
    assert gate is not None and gate["code"] == "agent_guidance.required"
