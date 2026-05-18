from __future__ import annotations

import pytest

from horosa_skill.schemas.tools import AgentGuidanceInput, BirthInput, DispatchInput, KnowledgeReadInput, KnowledgeRegistryInput, MemoryQueryInput, ReportRenderInput
from horosa_skill.surfaces.mcp_server import _merge_mcp_arguments, _normalize_mcp_request


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
