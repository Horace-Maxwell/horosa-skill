"""审计 outputs 的小项：O-22 检索固定文字、O-26 段数一致与长行截在分隔符、O-28 export_parse 正文不给两遍。

负向对照（实跑过）：O-22 _not_indexed_once 恒原样返回 → 第一条红；O-26 去掉 rfind 退回 → 第三条红、headline 不计占位 → 第二条红；
O-28 不剥 content → 第四条红。
"""
from __future__ import annotations

from pathlib import Path

from test_knowledge_retrieval import _put, _settings

from horosa_skill.exports.contract import missing_detail_text
from horosa_skill.result_view import READING, Budget, ViewRequest, shape_result
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.envelope import export_headline


def test_knowledge_search_fixed_text_is_said_once(tmp_path: Path) -> None:
    _put(tmp_path, "七杀.md", "七杀：月令透七杀。")
    (tmp_path / "data" / "knowledge" / "书.pdf").write_bytes(b"%PDF-1.4")
    service = HorosaSkillService(_settings(tmp_path))
    first = service.knowledge_search({"query": "七杀"})
    second = service.knowledge_search({"query": "七杀"})
    assert "how_to_read" not in first and first["matches"]
    assert any("没有读入" in w and "PDF" in w for w in first["warnings"])
    assert any("仍有 1 个文件没读入" in w for w in second["warnings"]) and not any("PDF" in w for w in second["warnings"])
    assert len(first.get("untrusted_notice", "")) < 260


def test_headline_counts_match_the_section_index() -> None:
    data = {"export_snapshot": {"technique": {"label": "星盘"}, "sections": [
        {"title": "起盘信息", "body": "日期：2026"}, {"title": "古典格局", "body": missing_detail_text("古典格局")},
        {"title": "相位", "body": "日合月"}]}}
    assert export_headline(data).startswith("已生成星盘（2 段，另 1 段未返回）")


def test_a_one_line_section_is_cut_after_a_delimiter() -> None:
    line = "关键岁数（精确穿越岁数）：" + "；".join(f"{n}.94岁六合·左土(20{n:02d}-03-01)" for n in range(400))
    env = {"ok": True, "tool": "agepoint", "run_id": "r", "warnings": [], "summary": [],
           "data": {"export_snapshot": {"technique": {"key": "agepoint"}, "export_text": f"[关键岁数]\n{line}",
                                        "sections": [{"index": 1, "title": "关键岁数", "body": line}]}}}
    out = shape_result(env, ViewRequest(view=READING), Budget(max_chars=8000, max_tokens=6000))
    row = out["data"]["export_snapshot"]["sections"][0]
    assert row["shown"] == "partial" and line[row["to"] - 1] == "；", line[row["to"] - 10:row["to"]]


def test_export_parse_gives_each_body_once(tmp_path: Path) -> None:
    service = HorosaSkillService(_settings(tmp_path))
    result = service.run_tool("export_parse", {"technique": "bazi", "content": "[起盘信息]\n日期：x\n\n[大运]\n甲子"}, save_result=False)
    assert result.ok and all("content" not in row and row["body"] for row in result.data["sections"])


def test_report_template_is_a_skeleton_not_a_second_copy(tmp_path: Path) -> None:
    """审计 O-23：模板 15.4 KB——正文再给一遍、question_analysis 两遍、必讲段清单三遍，还要求「逐项解释全部章节」。
    负向对照（实跑过）：ReportTemplateInput.include_text 缺省改回 True → 第一个断言红。"""
    import json

    from test_user_knowledge_and_chart_report import _chart_run, _service

    service = _service(tmp_path)
    run_id = _chart_run(service).memory_ref.run_id
    slim = service.report_template({"run_id": run_id, "tool_name": "chart"})
    full = service.report_template({"run_id": run_id, "tool_name": "chart", "include_text": True})
    assert "export_text" not in slim["source_context"] and slim["source_context"]["text_with"].startswith("horosa_memory_show(")
    assert len(json.dumps(slim, ensure_ascii=False)) < len(json.dumps(full, ensure_ascii=False)) / 2
    text = json.dumps(slim, ensure_ascii=False)
    assert "all_source_export_sections_required" not in text and "conversation_brief" not in text
    assert full["source_context"]["export_text"]


def test_runs_with_only_failed_calls_are_not_listed_by_default(tmp_path: Path) -> None:
    """审计 O-10：失败调用也各落一个 run、排在 memory_query 最前。缺省不列；点名 run_id / tool 照列。
    负向对照（实跑过）：memory.py 里 hide_failed=False → 第一个断言红。"""
    from test_result_view_catalogue import offline_service

    from horosa_skill.testing_payloads import build_sample_payloads

    from horosa_skill.memory.store import MemoryStore

    service = offline_service(tmp_path)                                    # 假引擎：起盘成功
    good = service.run_tool("sixyao", build_sample_payloads()["sixyao"], save_result=True).memory_ref.run_id
    unreachable = HorosaSkillService(service.settings, store=MemoryStore(service.settings))   # 同一个库，引擎不可达：失败
    bad_result = unreachable.run_tool("sixyao", build_sample_payloads()["sixyao"], save_result=True)
    assert not bad_result.ok and bad_result.memory_ref is not None
    bad = bad_result.memory_ref.run_id
    listed = {row["run_id"] for row in service.query_memory({})["results"]}
    assert good in listed and bad not in listed, listed
    assert bad in {row["run_id"] for row in service.query_memory({"run_id": bad})["results"]}
    assert bad in {row["run_id"] for row in service.query_memory({"tool": "sixyao"})["results"]}
