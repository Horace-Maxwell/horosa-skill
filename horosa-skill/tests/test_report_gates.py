"""JSON 报告的质量闸要量调用方自己写的答案，不能量机器回填（`_merge_ai_report` 为覆盖而补的段落）。

台账：docs/LESSONS.md v0.47.2-dev「JSON 报告的闸永远是绿的」。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fakes import FakeClient, FakeJsClient, sample_final_ai_report
from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads

TOOL = "bazi_birth"


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _report(service: HorosaSkillService, **render: object) -> dict:
    env = service.run_tool(TOOL, build_sample_payloads()[TOOL], query_text="我今年该不该换工作？")
    out = service.report_render({"run_id": env.memory_ref.run_id, "tool_name": TOOL, "format": "json", **render})
    return json.loads(Path(out["artifact_path"]).read_text(encoding="utf-8"))


def test_a_chart_report_with_no_ai_does_not_claim_an_ai_answer(tmp_path: Path) -> None:
    """2026-11-06 实测：`style:"chart"` 完全没有 AI 时，JSON 仍写 `has_ai_answer: True`、`ai_analysis_complete: True`。"""
    doc = _report(_service(tmp_path), style="chart")

    assert doc["report_index"]["has_ai_answer"] is False
    assert doc["report_quality"]["ai_analysis_complete"] is False
    assert doc["ai_coverage_status"]["status"] == "needs_ai_analysis"
    assert doc["ai_coverage_status"]["has_direct_answer"] is False


def test_a_chart_report_needs_no_ai_to_be_ready(tmp_path: Path) -> None:
    """完整排盘报告本来就不要 AI 解读，没有解读不能算「交付前需要补齐」。"""
    doc = _report(_service(tmp_path), style="chart")
    assert doc["delivery_checklist"]["ready_to_deliver"] is True, doc["delivery_checklist"]["missing"]
    assert "AI 解盘" not in doc["delivery_checklist"]["completion_hint"]


def test_a_one_word_answer_is_not_ready_to_deliver(tmp_path: Path) -> None:
    """2026-11-06 实测：AI 只写「好。」，JSON 却是 16 段分析、覆盖率 1.0、`ready_to_deliver: True`。"""
    doc = _report(_service(tmp_path), ai_report={"answer_text": "好。"})

    assert doc["delivery_checklist"]["ready_to_deliver"] is False
    assert doc["report_index"]["ready_to_deliver"] is False
    assert doc["report_quality"]["ai_analysis_complete"] is False
    assert doc["section_coverage_matrix"]["coverage_ratio"] == 0
    assert doc["report_index"]["has_ai_answer"] is True, "AI 确实答了，只是答得不够"


def test_a_real_answer_covering_every_section_is_ready(tmp_path: Path) -> None:
    service = _service(tmp_path)
    env = service.run_tool(TOOL, build_sample_payloads()[TOOL], query_text="我今年该不该换工作？")
    template = service.report_template({"run_id": env.memory_ref.run_id, "tool_name": TOOL})
    report = sample_final_ai_report("我今年该不该换工作？")
    report["analysis_sections"] = [
        {"title": section["title"], "body": f"{section['title']} 的解读。", "evidence_lines": [section["title"]]}
        for section in template["source_export_sections"]
    ]

    out = service.report_render({"run_id": env.memory_ref.run_id, "tool_name": TOOL, "format": "json", "ai_report": report})
    doc = json.loads(Path(out["artifact_path"]).read_text(encoding="utf-8"))

    assert doc["delivery_checklist"]["ready_to_deliver"] is True, doc["delivery_checklist"]["missing"]
    assert doc["report_quality"]["ai_analysis_complete"] is True
    assert doc["ai_coverage_status"]["status"] == "complete"


def test_a_targeted_answer_is_deliverable_and_its_coverage_is_reported_honestly(tmp_path: Path) -> None:
    """定向解读不必每章都答（`_complete_analysis_sections` 的设计）：能交付，但覆盖率写实数，不把回填算成 AI 写的。"""
    service = _service(tmp_path)
    env = service.run_tool(TOOL, build_sample_payloads()[TOOL], query_text="我今年该不该换工作？")
    source_title = service.report_template({"run_id": env.memory_ref.run_id, "tool_name": TOOL})["source_export_sections"][0]["title"]

    out = service.report_render({"run_id": env.memory_ref.run_id, "tool_name": TOOL, "format": "json",
                                 "ai_report": sample_final_ai_report("我今年该不该换工作？", source_title=source_title)})
    doc = json.loads(Path(out["artifact_path"]).read_text(encoding="utf-8"))

    assert doc["delivery_checklist"]["ready_to_deliver"] is True, doc["delivery_checklist"]["missing"]
    matrix = doc["section_coverage_matrix"]
    assert matrix["all_sections_covered"] is False and 0 < matrix["coverage_ratio"] < 1
    assert doc["delivery_checklist"]["checks"]["source_sections_covered"] is False, "这项如实报 False，只是不拦交付"
    assert "逐章覆盖" not in doc["delivery_checklist"]["completion_hint"].split("；")[0]
    assert len(doc["ai_report"]["analysis_sections"]) > 2, "回填还在：机器 JSON 的覆盖段落是有意保留的"


@pytest.mark.parametrize("fmt", ["pdf", "docx"])
def test_human_output_does_not_change_with_the_gates(tmp_path: Path, fmt: str) -> None:
    """闸只影响 JSON 里的机器字段：人读版的章节不进这些判定。"""
    service = _service(tmp_path)
    env = service.run_tool(TOOL, build_sample_payloads()[TOOL], query_text="q")
    out = service.report_render({"run_id": env.memory_ref.run_id, "tool_name": TOOL, "format": fmt, "style": "chart"})
    assert out["file"]["bytes"] > 1000 and "degraded_from" not in out
