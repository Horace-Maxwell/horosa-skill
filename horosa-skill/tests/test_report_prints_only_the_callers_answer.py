"""人读版（PDF / DOCX）只印调用方自己写的（v0.47.2）。

页面写着「以下是 AI 依据上方盘面所作的解读」，所以这个标题下不能站机器写的回填：实测八字报告里 AI 写 2 段 69 字，
机器写 16 段 3084 字。审计第一次的结论「回填只进机器 JSON」就错在只试了四种 `ai_report` 形状，这里每个字段都走一遍。
机器版 JSON 的回填不动，它要覆盖全部章节。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fakes import FakeClient, FakeJsClient, sample_final_ai_report
from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.reports.layout import body_blocks
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads

MARK = "调用方自己写的句子"
SHAPES = {
    "answer_text": {"answer_text": MARK},
    "direct_answer": {"direct_answer": MARK},
    "executive_summary": {"executive_summary": MARK},
    "analysis_sections": {"analysis_sections": [{"title": "事业", "body": MARK}]},
    "recommendations": {"recommendations": [MARK]},
    "limitations": {"limitations": [MARK]},
    "evidence": {"evidence": [MARK]},
    "analysis_focus": {"analysis_focus": MARK},
    "reading_steps": {"reading_steps": [MARK]},
    "consultation_basis": {"consultation_basis": MARK},
    "follow_up_questions": {"follow_up_questions": [MARK]},
}
TOOLS = ("bazi_birth", "qimen", "chart")


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _document(service: HorosaSkillService, tool: str, ai_report: dict | None, **extra: object) -> dict:
    """分析报告没有任何 AI 内容时服务直接要求先写解读（`report_render` 不出文件），「没有答案」只有 `style:"chart"` 这一条路。"""
    env = service.run_tool(tool, build_sample_payloads()[tool], query_text="我今年该不该换工作？")
    render = {"run_id": env.memory_ref.run_id, "tool_name": tool, "format": "json", **extra}
    if ai_report is not None:
        render["ai_report"] = ai_report
    return json.loads(Path(service.report_render(render)["artifact_path"]).read_text(encoding="utf-8"))


def _machine_sentences(document: dict, caller: dict | None) -> list[str]:
    """机器版 JSON 里有、调用方没写的句子：这些都不许印出来。"""
    report = document["ai_report"]
    written = json.dumps(caller or {}, ensure_ascii=False)
    found: list[str] = []
    for key in ("direct_answer", "executive_summary", "consultation_basis"):
        found.append(str(report.get(key) or ""))
    for key in ("reading_steps", "recommendations", "limitations"):
        found.extend(str(item) for item in report.get(key) or [])
    for section in report.get("analysis_sections") or []:
        found.append(str(section.get("body") or "") if isinstance(section, dict) else str(section))
    return [text for text in found if text.strip() and text not in written]


def _printed(document: dict) -> str:
    """除盘面章节以外，人读版印出来的全部文字。"""
    return "\n".join(f"{block.text}\n{block.body}" for block in body_blocks(document) if block.kind != "section")


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_no_machine_sentence_is_printed_as_the_ais_reading(tmp_path: Path, tool: str, shape: str) -> None:
    caller = SHAPES[shape]
    document = _document(_service(tmp_path), tool, caller)
    machine = _machine_sentences(document, caller)
    assert machine, "没有机器回填的话这条什么也没测"
    printed = _printed(document)
    assert [text[:40] for text in machine if text in printed] == []


@pytest.mark.parametrize("field", ["answer_text", "direct_answer", "executive_summary", "analysis_sections", "recommendations",
                                   "limitations", "reading_steps", "consultation_basis", "analysis_focus"])
def test_what_the_caller_wrote_is_printed(tmp_path: Path, field: str) -> None:
    assert MARK in _printed(_document(_service(tmp_path), "bazi_birth", SHAPES[field]))


def test_a_report_with_no_answer_has_no_ai_part(tmp_path: Path) -> None:
    printed = _printed(_document(_service(tmp_path), "bazi_birth", None, style="chart"))
    assert "AI 解读" not in printed and "核心结论" not in printed and "总览摘要" not in printed


def test_the_users_question_is_not_printed_as_a_conclusion(tmp_path: Path) -> None:
    """`analysis_focus` 的缺省值是用户的问题：答案只写了别的字段时，曾经印在「核心结论」卡片里。"""
    printed = _printed(_document(_service(tmp_path), "bazi_birth", SHAPES["recommendations"]))
    assert "核心结论" not in printed and "我今年该不该换工作" not in printed


def test_the_full_template_answer_prints_exactly_its_own_sections(tmp_path: Path) -> None:
    caller = sample_final_ai_report("我今年该不该换工作？")
    document = _document(_service(tmp_path), "bazi_birth", caller)
    headings = [block.text for block in body_blocks(document) if block.role == "ai_section"]
    assert headings == [str(section["title"]) for section in caller["analysis_sections"]]


def test_the_machine_json_keeps_its_coverage_backfill(tmp_path: Path) -> None:
    """闸与覆盖矩阵靠这份回填对齐全部章节：只是不印出来。"""
    caller = SHAPES["analysis_sections"]
    document = _document(_service(tmp_path), "bazi_birth", caller)
    assert len(document["ai_report"]["analysis_sections"]) > len(caller["analysis_sections"])
    assert len(document["ai_report"]["human_analysis_sections"]) == 1


@pytest.mark.parametrize("fmt", ["docx", "pdf"])
def test_the_real_files_are_shorter_and_still_render(tmp_path: Path, fmt: str) -> None:
    service = _service(tmp_path)
    env = service.run_tool("bazi_birth", build_sample_payloads()["bazi_birth"], query_text="q")
    out = service.report_render({"run_id": env.memory_ref.run_id, "tool_name": "bazi_birth", "format": fmt, "ai_report": SHAPES["analysis_sections"]})
    assert out["file"]["bytes"] > 1000 and "degraded_from" not in out


def test_the_docx_really_lacks_the_machine_prose(tmp_path: Path) -> None:
    from docx import Document

    service = _service(tmp_path)
    caller = SHAPES["analysis_sections"]
    env = service.run_tool("bazi_birth", build_sample_payloads()["bazi_birth"], query_text="q")
    out = service.report_render({"run_id": env.memory_ref.run_id, "tool_name": "bazi_birth", "format": "docx", "ai_report": caller})
    text = "\n".join(paragraph.text for paragraph in Document(out["artifact_path"]).paragraphs)
    document = _document(service, "bazi_birth", caller)
    assert MARK in text
    leaked = [sentence[:40] for sentence in _machine_sentences(document, caller) if sentence in text]
    assert leaked == []
