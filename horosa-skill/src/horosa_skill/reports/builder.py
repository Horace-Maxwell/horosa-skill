"""组装报告文档。读存档、默认解读、质量闸、索引各在自己的模块里，这里只管顺序和章节清单。"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from horosa_skill.reports.default_report import merge_ai_report
from horosa_skill.reports.gates import (
    build_ai_coverage,
    build_coverage_contract,
    build_coverage_matrix,
    build_delivery_checklist,
    build_report_quality,
    caller_answer_view,
    format_coverage,
    format_delivery_checklist,
    format_report_quality,
    format_section_coverage_matrix,
)
from horosa_skill.reports.question import analyze_question, build_targeted_contract, format_question_analysis, format_targeting
from horosa_skill.reports.search_index import build_content_outline, build_plain_text, build_search_index, index_checks
from horosa_skill.reports.source import (
    appendix_sections,
    chart_basis_section,
    document_sections_from_export_format,
    read_export_format,
    read_export_sections,
    read_export_text,
    read_payload,
    read_provenance,
    read_source_meta,
    read_user_question,
    report_technique_name,
)
from horosa_skill.reports.template import build_template as _build_template

REPORT_DOCUMENT_SCHEMA = "horosa.skill.report.v1"

def _format_report_metadata(
    *,
    run: dict[str, Any],
    source: dict[str, Any],
    language: str,
    generated_at: str,
    user_question: str,
) -> str:
    return "\n".join(
        [
            f"- 报告生成时间：{generated_at}",
            f"- Run ID：{run.get('run_id')}",
            f"- 工具名：{source.get('tool_name')}",
            f"- 技法标识：{source.get('technique') or '无'}",
            f"- 技法名称：{source.get('technique_label') or source.get('technique') or source.get('tool_name')}",
            f"- 语言：{language}",
            f"- 用户问题：{user_question or '无'}",
            f"- Trace ID：{source.get('trace_id') or '无'}",
            f"- Group ID：{source.get('group_id') or '无'}",
        ]
    )

def _format_ai_report(ai_report: dict[str, Any]) -> str:
    lines: list[str] = []
    if ai_report.get("analysis_focus"):
        lines.append(f"[分析焦点]\n{ai_report.get('analysis_focus')}")
    if ai_report.get("direct_answer"):
        lines.append(f"[直接回答]\n{ai_report.get('direct_answer')}")
    if ai_report.get("executive_summary"):
        lines.append(f"[总览摘要]\n{ai_report.get('executive_summary')}")
    if ai_report.get("answer_text"):
        lines.append(f"[AI 原始回答]\n{ai_report.get('answer_text')}")
    sections = ai_report.get("analysis_sections") if isinstance(ai_report.get("analysis_sections"), list) else []
    if sections:
        section_lines = []
        for index, section in enumerate(sections, start=1):
            if isinstance(section, dict):
                title = section.get("title") or section.get("source_section_title") or f"分析 {index}"
                body = section.get("body") or section.get("content") or ""
                relevance = section.get("relevance_to_question")
                evidence_lines = section.get("evidence_lines") if isinstance(section.get("evidence_lines"), list) else []
                parts = [f"{index}. {title}", str(body)]
                if relevance:
                    parts.append(f"与问题关系：{relevance}")
                if evidence_lines:
                    parts.append("证据线索：" + "；".join(str(item) for item in evidence_lines))
                section_lines.append("\n".join(part for part in parts if part))
            else:
                section_lines.append(f"{index}. {section}")
        lines.append("[分节分析]\n" + "\n\n".join(section_lines))
    evidence = ai_report.get("evidence") if isinstance(ai_report.get("evidence"), list) else []
    if evidence:
        lines.append("[证据引用]\n" + "\n".join(f"- {item}" for item in evidence))
    return "\n\n".join(lines) if lines else "待 AI 根据模板填写针对性解盘。"

def _format_recommendations_limitations(ai_report: dict[str, Any]) -> str:
    recommendations = ai_report.get("recommendations") if isinstance(ai_report.get("recommendations"), list) else []
    limitations = ai_report.get("limitations") if isinstance(ai_report.get("limitations"), list) else []
    followups = ai_report.get("follow_up_questions") if isinstance(ai_report.get("follow_up_questions"), list) else []
    lines = ["[建议]"]
    lines.extend([f"- {item}" for item in recommendations] if recommendations else ["- 待 AI 根据用户问题补充建议。"])
    lines.extend(["", "[限制]"])
    lines.extend([f"- {item}" for item in limitations] if limitations else ["- 如果未提供 AI 分析，本报告仅代表结构化计算与导出结果。"])
    lines.extend(["", "[可继续追问]"])
    lines.extend([f"- {item}" for item in followups] if followups else ["- 可继续要求 AI 基于本报告做专项追问或复盘。"])
    return "\n".join(lines)

def _format_mapping(payload: dict[str, Any]) -> str:
    if not payload:
        return "无"
    return "\n".join(f"- {key}: {value}" for key, value in payload.items())


class ReportBuilder:
    def build_template(self, *, run: dict[str, Any], source_artifact: dict[str, Any], language: str) -> dict[str, Any]:
        return _build_template(run=run, source_artifact=source_artifact, language=language)

    def build_document(
        self,
        *,
        run: dict[str, Any],
        source_artifact: dict[str, Any],
        language: str,
        title: str | None = None,
        ai_report: dict[str, Any] | None = None,
        include_raw_json: bool = False,
        style: str = "analysis",
    ) -> dict[str, Any]:
        """style="analysis"（缺省）= AI 解盘报告；style="chart" = 完整排盘报告（不要 AI 答复也能出，只放真实盘面）。

        两种都把技法的**全部**导出段作为「完整盘面」收进人读版（此前人读版一段盘面都没有），并附技法依据 / 自备参考资料 / 来源。
        """
        payload = read_payload(source_artifact)
        data = payload.get("data") if isinstance(payload, dict) else {}
        source = read_source_meta(run=run, source_artifact=source_artifact, payload=payload)
        raw_export_snapshot = data.get("export_snapshot") if isinstance(data, dict) else {}
        export_snapshot = raw_export_snapshot if isinstance(raw_export_snapshot, dict) else {}
        export_format = read_export_format(payload)
        input_normalized = payload.get("input_normalized") if isinstance(payload, dict) else {}
        summary = payload.get("summary") if isinstance(payload, dict) else []
        export_text = read_export_text(export_snapshot=export_snapshot, export_format=export_format, payload=payload)
        export_sections = read_export_sections(export_format, include_body=True)
        merged_ai_report = merge_ai_report(
            run=run,
            ai_report=ai_report,
            source=source,
            input_normalized=input_normalized if isinstance(input_normalized, dict) else {},
            summary=summary if isinstance(summary, list) else [str(summary)] if summary else [],
            export_sections=export_sections,
            export_text=export_text,
        )
        coverage = build_coverage_contract(export_sections=export_sections, export_text=export_text, source=source)
        user_question = read_user_question(run)
        question_analysis = analyze_question(user_question)
        targeted_contract = build_targeted_contract(
            user_question=user_question,
            question_analysis=question_analysis,
            coverage=coverage,
        )
        # 下面这些闸量的是调用方自己写的答案。merged_ai_report 含确定性回填（为覆盖全部章节而补），拿它量永远是绿的。
        caller_answer = caller_answer_view(run=run, ai_report=ai_report)
        ai_coverage = build_ai_coverage(coverage=coverage, ai_report=caller_answer)
        coverage_matrix = build_coverage_matrix(export_sections=export_sections, ai_report=caller_answer)
        provenance = read_provenance(export_snapshot=export_snapshot, export_format=export_format, source=source)
        report_quality = build_report_quality(
            input_normalized=input_normalized if isinstance(input_normalized, dict) else {},
            export_text=export_text,
            export_sections=export_sections,
            ai_report=caller_answer,
            ai_coverage=ai_coverage,
            provenance=provenance,
        )

        generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        technique_title = source.get("technique_label") or source.get("technique") or source.get("tool_name")
        chart_style = style == "chart"
        if chart_style:
            technique_title = report_technique_name(str(source.get("tool_name") or ""), str(technique_title or ""))
        report_title = title or (f"{technique_title} · 完整排盘报告" if chart_style else f"结构化咨询报告 · {technique_title}")
        has_caller_answer = bool(
            run.get("ai_answer_text")
            or isinstance(run.get("ai_answer_structured"), dict) and run.get("ai_answer_structured")
            or (ai_report and any(v not in (None, "", [], {}) for v in ai_report.values()))
        )
        head_sections = [
            {
                "id": "report_metadata",
                "title": "报告元信息",
                "body": _format_report_metadata(
                    run=run,
                    source=source,
                    language=language,
                    generated_at=generated_at,
                    user_question=user_question,
                ),
                "items": {
                    "run_id": run["run_id"],
                    "tool_name": source.get("tool_name"),
                    "technique": source.get("technique"),
                    "technique_label": source.get("technique_label"),
                    "generated_at": generated_at,
                    "language": language,
                    "user_question": user_question,
                    "trace_id": source.get("trace_id"),
                    "group_id": source.get("group_id"),
                },
            },
            {
                "id": "report_quality",
                "title": "报告质量检查",
                "body": format_report_quality(report_quality),
                "items": report_quality,
            },
        ]
        tail_sections = [
            {
                "id": "coverage_contract",
                "title": "AI 解释覆盖清单",
                "body": format_coverage(coverage),
                "items": coverage,
            },
            {
                "id": "section_coverage_matrix",
                "title": "逐章解释覆盖矩阵",
                "body": format_section_coverage_matrix(coverage_matrix),
                "items": coverage_matrix,
            },
            {
                "id": "targeted_analysis_contract",
                "title": "针对性解盘要求",
                "body": format_targeting(targeted_contract),
                "items": targeted_contract,
            },
            {
                "id": "question_analysis",
                "title": "用户问题拆解",
                "body": format_question_analysis(question_analysis),
                "items": question_analysis,
            },
            {
                "id": "input_overview",
                "title": "输入信息",
                "body": _format_mapping(input_normalized if isinstance(input_normalized, dict) else {}),
                "items": input_normalized if isinstance(input_normalized, dict) else {},
            },
            {
                "id": "technique_summary",
                "title": "工具摘要",
                "body": "\n".join(str(item) for item in summary) if isinstance(summary, list) else str(summary or ""),
                "items": summary if isinstance(summary, list) else [],
            },
            {
                "id": "ai_interpretation",
                "title": "AI 解盘正文",
                "body": _format_ai_report(merged_ai_report),
                "items": merged_ai_report,
            },
            {
                "id": "recommendations_limitations",
                "title": "建议、限制与追问",
                "body": _format_recommendations_limitations(merged_ai_report),
                "items": {
                    "recommendations": merged_ai_report.get("recommendations", []),
                    "limitations": merged_ai_report.get("limitations", []),
                    "follow_up_questions": merged_ai_report.get("follow_up_questions", []),
                },
            },
            {
                "id": "xingque_export_text",
                "title": "星阙 AI 导出正文",
                "body": export_text,
                "items": {},
            },
        ]
        tail_sections.append(chart_basis_section(
            input_normalized if isinstance(input_normalized, dict) else {}, source,
            card=data.get("technique_card") if isinstance(data, dict) and isinstance(data.get("technique_card"), dict) else {},
        ))
        chart_sections = document_sections_from_export_format(export_format)
        tail_sections.extend(chart_sections)
        tail_sections.extend(appendix_sections(
            data if isinstance(data, dict) else {}, source=source, provenance=provenance,
            unproduced=[str(section["title"]) for section in chart_sections if section.get("placeholder")],
        ))
        tail_sections.append(
            {
                "id": "provenance",
                "title": "来源追溯",
                "body": _format_mapping(provenance),
                "items": provenance,
            }
        )
        # 交付清单自己也是被索引的章节：先定清单，章节才齐，索引只建这一次。
        delivery_checklist = build_delivery_checklist(
            sections=[*head_sections, *tail_sections],
            coverage=coverage,
            coverage_matrix=coverage_matrix,
            report_quality=report_quality,
            question_analysis=question_analysis,
            targeted_contract=targeted_contract,
            ai_report=caller_answer,
            ai_required=style != "chart",
            provenance=provenance,
            index_checks=index_checks(sections=[*head_sections, *tail_sections], run=run, source=source),
        )
        sections = [
            *head_sections,
            {
                "id": "delivery_checklist",
                "title": "交付检查清单",
                "body": format_delivery_checklist(delivery_checklist),
                "items": delivery_checklist,
            },
            *tail_sections,
        ]
        content_outline = build_content_outline(sections)
        plain_text = build_plain_text(title=report_title, generated_at=generated_at, sections=sections)
        search_index = build_search_index(
            run=run,
            source=source,
            user_question=user_question,
            question_analysis=question_analysis,
            targeted_contract=targeted_contract,
            export_sections=export_sections,
            ai_report=merged_ai_report,
            provenance=provenance,
            plain_text=plain_text,
        )

        presentation: dict[str, Any] = {}
        if chart_style:
            when = " ".join(str(input_normalized.get(k)) for k in ("date", "time") if isinstance(input_normalized, dict) and input_normalized.get(k))
            presentation = {
                "cover_label": "完整排盘报告",
                "footer_meta": when,
                # 封面大标题只写技法名（「完整排盘报告」已是封面小标签），元信息不再第三次重复技法名。
                "cover_title": str(technique_title or ""),
                "cover_meta": " · ".join(part for part in (when, "星阙 Horosa") if part),
                "intro_heading": "报告说明",
                "intro_text": (
                    "本报告由星阙引擎的排盘结果直接生成：收录全部盘面段落与技法依据，"
                    + ("并附 AI 解读。" if has_caller_answer else "不含 AI 解读；需要解读时，把本盘交给 AI 出解读报告即可。")
                    + (f"\n所问：{user_question}" if user_question else "")
                ),
            }
        from horosa_skill.reports.figures import extract_figures

        figures = extract_figures(str(source.get("tool_name") or ""), data if isinstance(data, dict) else {},
                                  str(technique_title or ""))
        return {
            "schema": REPORT_DOCUMENT_SCHEMA,
            "style": "chart" if chart_style else "analysis",
            "figures": figures,
            "show_ai": (not chart_style) or has_caller_answer,
            **presentation,
            "title": report_title,
            "language": language,
            "generated_at": generated_at,
            "content_outline": content_outline,
            "plain_text": plain_text,
            "search_index": search_index,
            "report_index": {
                "run_id": run["run_id"],
                "tool_name": source["tool_name"],
                "technique": source["technique"],
                "user_question": user_question,
                "question_analysis": question_analysis,
                "answer_plan": targeted_contract["answer_plan"],
                "targeted_answer_requirements": targeted_contract["targeted_answer_requirements"],
                "analysis_focus": merged_ai_report.get("analysis_focus") or user_question,
                "has_ai_answer": bool(caller_answer.get("answer_text") or caller_answer.get("direct_answer") or caller_answer.get("executive_summary")),
                "coverage_status": ai_coverage["status"],
                "ready_to_deliver": delivery_checklist.get("ready_to_deliver"),
                "delivery_missing": delivery_checklist.get("missing", []),
                "delivery_checks": delivery_checklist.get("checks", {}),
                "storage": {
                    "managed_by": "horosa_skill.memory",
                    "artifact_kind": "report",
                    "source_artifact_path": source_artifact.get("path"),
                },
            },
            "run": {
                "id": run["run_id"],
                "entrypoint": run.get("entrypoint"),
                "query_text": run.get("query_text"),
                "user_question": run.get("user_question"),
                "created_at": run.get("created_at"),
                "updated_at": run.get("updated_at"),
                "group_id": run.get("group_id"),
            },
            "source": source,
            "user_question": run.get("user_question") or run.get("query_text"),
            "input_normalized": input_normalized if isinstance(input_normalized, dict) else {},
            "summary": summary if isinstance(summary, list) else [str(summary)] if summary else [],
            "ai_report": merged_ai_report,
            "coverage": coverage,
            "ai_coverage_status": ai_coverage,
            "section_coverage_matrix": coverage_matrix,
            "report_quality": report_quality,
            "delivery_checklist": delivery_checklist,
            "question_analysis": question_analysis,
            "targeted_analysis_contract": targeted_contract,
            "sections": sections,
            "provenance": provenance,
            "appendix": {
                "raw_artifact_path": source_artifact.get("path"),
                "raw_json_included": include_raw_json,
                "raw_envelope": copy.deepcopy(payload) if include_raw_json else None,
            },
        }
