"""报告的 language 只决定中文简 / 繁；别的值写明未生效，不再静默按中文出（审计 O-04）。

修前：language:"en" / "fr" → ok、无 warnings，PDF 与中文版逐字节同大小，模板只多一个 "language":"en" 字段。
负向对照（实跑过）：_note_language 直接 return result → 前两个用例红。
"""
from __future__ import annotations

import pytest

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads


@pytest.fixture()
def run(tmp_path):
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    result = service.run_tool("tarot", build_sample_payloads()["tarot"])   # 本地 JS，离线可跑
    assert result.ok, result.error
    return service, result.memory_ref.run_id


@pytest.mark.parametrize("language", ["fr", "de"])
def test_template_says_an_unsupported_language_had_no_effect(run, language) -> None:
    service, run_id = run
    warnings = service.report_template({"run_id": run_id, "language": language}).get("warnings") or []
    assert any(f"language='{language}' 未生效" in line for line in warnings), warnings


def test_render_says_it_too(run) -> None:
    service, run_id = run
    rendered = service.report_render({"run_id": run_id, "format": "json", "style": "chart", "language": "fr"})
    assert any("language='fr' 未生效" in line for line in rendered.get("warnings") or []), rendered.get("warnings")


def test_english_is_an_interface_not_a_warning(run, tmp_path) -> None:
    """审计待决项 1：en = 英文界面 + 原文盘面。负向对照（实跑过）：reports.py 不调 english_frame → 断言红。"""
    import json
    from pathlib import Path

    service, run_id = run
    rendered = service.report_render({"run_id": run_id, "format": "json", "style": "chart", "language": "en"})
    assert not any("未生效" in line for line in rendered.get("warnings") or [])
    assert any("report frame" in line for line in rendered["summary"])
    doc = json.loads(Path(rendered["artifact_path"]).read_text(encoding="utf-8"))
    assert doc["interface"] == "en" and doc["title"].endswith("Full chart report") and doc["intro_text"].startswith("Chart data is printed")
    basis = next(s for s in doc["sections"] if s.get("group") == "basis")
    assert basis["title"] == "Basic information" and "| Item | Value |" in basis["body"] and "| Date |" in basis["body"]
    chart = [s for s in doc["sections"] if s.get("group") == "chart"]
    assert chart and all("Chart data" not in s["title"] for s in chart)   # 盘面段一字不动
    template = service.report_template({"run_id": run_id, "language": "en"})
    assert any("in English" in line for line in template["ai_instructions"])


@pytest.mark.parametrize("language", ["zh-CN", "zh-TW", "zh-HK", None])
def test_chinese_tags_are_quiet(run, language) -> None:
    service, run_id = run
    payload = {"run_id": run_id, **({"language": language} if language else {})}
    assert not any("未生效" in line for line in service.report_template(payload).get("warnings") or [])


def test_english_docx_and_pdf_render(run) -> None:
    import re
    import zipfile

    service, run_id = run
    ai = {"direct_answer": "The cards favour waiting.", "executive_summary": "Summary in English.",
          "analysis_sections": [{"title": "Cards", "body": "Read slowly."}], "recommendations": ["Wait."]}
    docx = service.report_render({"run_id": run_id, "format": "docx", "language": "en", "ai_report": ai})
    text = re.sub(r"<[^>]+>", "", zipfile.ZipFile(docx["artifact_path"]).read("word/document.xml").decode("utf-8"))
    for word in ("Contents", "Key conclusion", "Reading", "Chart data", "Basic information", "Chart data is printed"):
        assert word in text, word
    assert "完整盘面" not in text and "核心结论" not in text
    pdf = service.report_render({"run_id": run_id, "format": "pdf", "language": "en", "ai_report": ai})
    assert pdf["format"] == "pdf" and "degraded_from" not in pdf
