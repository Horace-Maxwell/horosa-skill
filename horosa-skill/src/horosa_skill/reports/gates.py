"""JSON 报告的质量闸：覆盖、质量、交付清单。一律量调用方自己写的答案（`caller_answer_view`），不量 `merge_ai_report` 的回填。"""

from __future__ import annotations

from typing import Any

from horosa_skill.reports.source import analysis_section_matches_source, read_caller_answer


def caller_answer_view(*, run: dict[str, Any], ai_report: dict[str, Any] | None) -> dict[str, Any]:
    """质量闸读的形状，字段名与 merged_ai_report 对齐（`answer` / `summary` 是调用方可用的别名）。"""
    base = read_caller_answer(run=run, ai_report=ai_report)
    lists = {key: base[key] if isinstance(base.get(key), list) else [] for key in ("analysis_sections", "recommendations", "evidence")}
    return {
        "answer_text": base.get("answer_text") or "",
        "direct_answer": base.get("direct_answer") or base.get("answer") or "",
        "executive_summary": base.get("executive_summary") or base.get("summary") or "",
        **lists,
    }


def build_coverage_contract(*, export_sections: list[dict[str, Any]], export_text: str, source: dict[str, Any]) -> dict[str, Any]:
    must_explain_sections = [str(section.get("title")) for section in export_sections if section.get("title")]
    return {
        "schema": "horosa.skill.report.coverage.v1",
        "tool_name": source.get("tool_name"),
        "technique": source.get("technique"),
        "all_source_export_sections_required": bool(must_explain_sections),
        "must_explain_sections": must_explain_sections,
        "source_export_section_count": len(export_sections),
        "source_export_text_chars": len(export_text),
        "source_section_line_count": sum(int(section.get("line_count") or 0) for section in export_sections),
        "missing_section_policy": "If a section cannot be interpreted, keep its title and explain the limitation explicitly.",
        "storage_policy": "Rendered reports are stored as memory artifacts and remain discoverable through memory_show/memory_query.",
    }


def format_coverage(coverage: dict[str, Any]) -> str:
    sections = coverage.get("must_explain_sections") if isinstance(coverage.get("must_explain_sections"), list) else []
    lines = [
        f"- 工具：{coverage.get('tool_name')}",
        f"- 技法：{coverage.get('technique')}",
        f"- 必须解释全部导出章节：{coverage.get('all_source_export_sections_required')}",
        f"- 导出章节数量：{coverage.get('source_export_section_count')}",
        f"- 导出正文字符数：{coverage.get('source_export_text_chars')}",
        f"- 原始章节行数：{coverage.get('source_section_line_count')}",
    ]
    if sections:
        lines.append("- 必须覆盖章节：" + "、".join(str(item) for item in sections))
    return "\n".join(lines)


def build_ai_coverage(*, coverage: dict[str, Any], ai_report: dict[str, Any]) -> dict[str, Any]:
    required = [str(item) for item in coverage.get("must_explain_sections", []) or []]
    sections = ai_report.get("analysis_sections") if isinstance(ai_report.get("analysis_sections"), list) else []
    missing = [
        title
        for title in required
        if not any(analysis_section_matches_source(section, title) for section in sections)
    ]
    return {
        "schema": "horosa.skill.report.ai_coverage.v1",
        "status": "complete" if required and not missing else "needs_ai_analysis" if required else "not_applicable",
        "required_section_count": len(required),
        "covered_section_count": len(required) - len(missing),
        "missing_sections": missing,
        "has_direct_answer": bool(ai_report.get("direct_answer") or ai_report.get("answer_text")),
        "has_evidence": bool(ai_report.get("evidence")),
    }


def build_report_quality(
    *,
    input_normalized: dict[str, Any],
    export_text: str,
    export_sections: list[dict[str, Any]],
    ai_report: dict[str, Any],
    ai_coverage: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    has_ai_summary = bool(ai_report.get("direct_answer") or ai_report.get("executive_summary") or ai_report.get("answer_text"))
    has_ai_sections = bool(ai_report.get("analysis_sections"))
    has_recommendations = bool(ai_report.get("recommendations"))
    has_evidence = bool(ai_report.get("evidence"))
    source_complete = bool(export_text) and bool(export_sections)
    ai_complete = (
        has_ai_summary
        and has_ai_sections
        and has_recommendations
        and ai_coverage.get("status") in {"complete", "not_applicable"}
    )
    missing: list[str] = []
    if not export_text:
        missing.append("export_text")
    if not export_sections:
        missing.append("export_sections")
    if not has_ai_summary:
        missing.append("ai_summary_or_direct_answer")
    if not has_ai_sections:
        missing.append("ai_analysis_sections")
    if not has_recommendations:
        missing.append("recommendations")
    if not has_evidence:
        missing.append("evidence")
    if not provenance:
        missing.append("provenance")
    return {
        "schema": "horosa.skill.report.quality.v1",
        "source_complete": source_complete,
        "ai_analysis_complete": ai_complete,
        "ready_for_human_reading": source_complete and has_ai_summary,
        "ready_for_ai_review": source_complete and bool(ai_report),
        "export_section_count": len(export_sections),
        "export_text_chars": len(export_text),
        "has_input": bool(input_normalized),
        "has_ai_summary": has_ai_summary,
        "has_ai_analysis_sections": has_ai_sections,
        "has_recommendations": has_recommendations,
        "has_evidence": has_evidence,
        "coverage_status": ai_coverage.get("status"),
        "missing_or_incomplete": missing,
        "completion_hint": "AI should fill direct_answer, executive_summary, analysis_sections, evidence, recommendations, and limitations before final delivery."
        if missing
        else "Report contains source data, AI analysis, recommendations, evidence, and provenance.",
    }


def format_report_quality(quality: dict[str, Any]) -> str:
    missing = quality.get("missing_or_incomplete") if isinstance(quality.get("missing_or_incomplete"), list) else []
    lines = [
        f"- 源数据完整：{quality.get('source_complete')}",
        f"- AI 分析完整：{quality.get('ai_analysis_complete')}",
        f"- 适合人工阅读：{quality.get('ready_for_human_reading')}",
        f"- 适合 AI 复盘：{quality.get('ready_for_ai_review')}",
        f"- 导出章节数：{quality.get('export_section_count')}",
        f"- 导出正文字符数：{quality.get('export_text_chars')}",
        f"- 覆盖状态：{quality.get('coverage_status')}",
    ]
    lines.append("- 缺失/待补：" + ("、".join(str(item) for item in missing) if missing else "无"))
    lines.append(f"- 完成提示：{quality.get('completion_hint')}")
    return "\n".join(lines)


def build_delivery_checklist(
    *,
    sections: list[dict[str, Any]],
    coverage: dict[str, Any],
    coverage_matrix: dict[str, Any],
    report_quality: dict[str, Any],
    question_analysis: dict[str, Any],
    targeted_contract: dict[str, Any],
    ai_report: dict[str, Any],
    ai_required: bool,
    provenance: dict[str, Any],
    index_checks: dict[str, bool],
) -> dict[str, Any]:
    """`sections` 是清单以外的全部章节。`ai_report` 是调用方自己写的答案。逐章覆盖如实报，但不拦交付：定向解读不必每章都答（见 `_complete_analysis_sections`）。"""
    section_ids = {
        "delivery_checklist",
        *(str(section.get("id")) for section in sections if isinstance(section, dict) and section.get("id")),
    }
    required_section_ids = {
        "report_metadata",
        "report_quality",
        "delivery_checklist",
        "coverage_contract",
        "section_coverage_matrix",
        "targeted_analysis_contract",
        "question_analysis",
        "input_overview",
        "technique_summary",
        "ai_interpretation",
        "recommendations_limitations",
        "xingque_export_text",
        "provenance",
    }
    source_requires_sections = bool(coverage.get("all_source_export_sections_required"))
    source_sections_ok = (
        not source_requires_sections
        or (
            int(coverage.get("source_export_section_count") or 0) > 0
            and int(coverage.get("source_export_text_chars") or 0) > 0
            and coverage_matrix.get("all_sections_covered") is True
        )
    )
    checks = {
        "has_required_report_sections": required_section_ids.issubset(section_ids),
        "has_user_question": question_analysis.get("has_question") is True,
        "has_targeted_requirements": bool(targeted_contract.get("targeted_answer_requirements")),
        "has_source_export_text": int(coverage.get("source_export_text_chars") or 0) > 0,
        "has_source_export_sections": int(coverage.get("source_export_section_count") or 0) > 0,
        "source_sections_covered": source_sections_ok,
        "has_ai_direct_answer": bool(ai_report.get("direct_answer") or ai_report.get("answer_text")),
        "has_ai_summary": bool(ai_report.get("executive_summary") or ai_report.get("answer_text")),
        "has_ai_section_analysis": bool(ai_report.get("analysis_sections")),
        "has_recommendations": bool(ai_report.get("recommendations")),
        "has_evidence": bool(ai_report.get("evidence")),
        "has_provenance": any(value not in (None, "", [], {}) for value in provenance.values()),
        **index_checks,
        "source_quality_ready": (not source_requires_sections) or report_quality.get("source_complete") is True,
        "ai_quality_ready": bool(
            report_quality.get("has_ai_summary")
            and report_quality.get("has_ai_analysis_sections")
            and report_quality.get("has_recommendations")
        )
        or (not source_requires_sections and bool(ai_report.get("direct_answer") or ai_report.get("executive_summary") or ai_report.get("answer_text"))),
        "human_readable_ready": report_quality.get("ready_for_human_reading") is True
        or bool(ai_report.get("direct_answer") or ai_report.get("executive_summary") or ai_report.get("answer_text")),
    }
    optional_when_no_source_sections = {
        "has_source_export_text",
        "has_source_export_sections",
        "source_sections_covered",
        "has_ai_section_analysis",
    }
    # 完整排盘报告（style=chart）本来就不要 AI 解读：没有解读不算缺。
    ai_checks = {
        "has_ai_direct_answer", "has_ai_summary", "has_ai_section_analysis", "has_recommendations", "has_evidence",
        "ai_quality_ready", "human_readable_ready",
    }
    not_blocking = {"source_sections_covered"} | (ai_checks if not ai_required else set())
    missing = [
        name
        for name, ok in checks.items()
        if not ok and name not in not_blocking and (source_requires_sections or name not in optional_when_no_source_sections)
    ]
    all_covered = coverage_matrix.get("all_sections_covered") is True
    return {
        "schema": "horosa.skill.report.delivery_checklist.v1",
        "all_required_blocks_present": required_section_ids.issubset(section_ids),
        "ready_to_deliver": not missing,
        "source_requires_sections": source_requires_sections,
        "checks": checks,
        "missing": missing,
        "completion_hint": (
            ("报告已包含源数据、逐章覆盖、AI 解盘、建议、证据、来源追溯和检索索引，可以交付。" if all_covered and ai_required
             else "报告可以交付；未逐章解释的章节见 section_coverage_matrix。")
            if not missing
            else "交付前需要补齐：" + "、".join(missing)
        ),
    }


def format_delivery_checklist(checklist: dict[str, Any]) -> str:
    checks = checklist.get("checks") if isinstance(checklist.get("checks"), dict) else {}
    lines = [
        f"- 可交付：{checklist.get('ready_to_deliver')}",
        f"- 必要报告块齐全：{checklist.get('all_required_blocks_present')}",
        f"- 源技法章节要求：{checklist.get('source_requires_sections')}",
    ]
    for key, value in checks.items():
        lines.append(f"- {key}: {'通过' if value else '待补'}")
    missing = checklist.get("missing") if isinstance(checklist.get("missing"), list) else []
    lines.append("- 待补项：" + ("、".join(str(item) for item in missing) if missing else "无"))
    lines.append(f"- 完成提示：{checklist.get('completion_hint')}")
    return "\n".join(lines)


def build_coverage_matrix(*, export_sections: list[dict[str, Any]], ai_report: dict[str, Any]) -> dict[str, Any]:
    ai_sections = ai_report.get("analysis_sections") if isinstance(ai_report.get("analysis_sections"), list) else []
    rows: list[dict[str, Any]] = []
    for index, source_section in enumerate(export_sections, start=1):
        title = str(source_section.get("title") or f"导出章节 {index}")
        matching_sections = []
        for ai_index, ai_section in enumerate(ai_sections, start=1):
            if not isinstance(ai_section, dict):
                continue
            ai_title = str(ai_section.get("source_section_title") or ai_section.get("title") or "")
            evidence_lines = ai_section.get("evidence_lines") if isinstance(ai_section.get("evidence_lines"), list) else []
            if ai_title == title or title in ai_title or ai_title in title or title in " ".join(str(item) for item in evidence_lines):
                matching_sections.append(
                    {
                        "analysis_index": ai_index,
                        "title": ai_title,
                        "body_chars": len(str(ai_section.get("body") or ai_section.get("content") or "")),
                        "has_evidence": bool(evidence_lines),
                        "relevance_to_question": ai_section.get("relevance_to_question") or "",
                    }
                )
        rows.append(
            {
                "source_index": index,
                "source_section_id": source_section.get("id"),
                "source_section_title": title,
                "source_line_count": source_section.get("line_count", 0),
                "covered": bool(matching_sections),
                "matching_analysis_sections": matching_sections,
            }
        )
    missing_titles = [row["source_section_title"] for row in rows if not row["covered"]]
    return {
        "schema": "horosa.skill.report.section_coverage_matrix.v1",
        "source_section_count": len(rows),
        "covered_section_count": len(rows) - len(missing_titles),
        "coverage_ratio": (len(rows) - len(missing_titles)) / len(rows) if rows else None,
        "all_sections_covered": bool(rows) and not missing_titles,
        "missing_section_titles": missing_titles,
        "rows": rows,
    }


def format_section_coverage_matrix(matrix: dict[str, Any]) -> str:
    rows = matrix.get("rows") if isinstance(matrix.get("rows"), list) else []
    lines = [
        f"- 源章节数：{matrix.get('source_section_count')}",
        f"- 已覆盖章节数：{matrix.get('covered_section_count')}",
        f"- 全部覆盖：{matrix.get('all_sections_covered')}",
    ]
    missing = matrix.get("missing_section_titles") if isinstance(matrix.get("missing_section_titles"), list) else []
    lines.append("- 未覆盖章节：" + ("、".join(str(item) for item in missing) if missing else "无"))
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"- {row.get('source_section_title')}: {'已覆盖' if row.get('covered') else '未覆盖'}"
        )
    return "\n".join(lines)
