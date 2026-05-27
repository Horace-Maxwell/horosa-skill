from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any


REPORT_TEMPLATE_SCHEMA = "horosa.skill.report.template.v1"
REPORT_DOCUMENT_SCHEMA = "horosa.skill.report.v1"
REQUIRED_SECTIONS = [
    "executive_summary",
    "input_overview",
    "technique_result",
    "ai_analysis",
    "recommendations",
    "provenance",
]


class ReportBuilder:
    def build_template(
        self,
        *,
        run: dict[str, Any],
        source_artifact: dict[str, Any],
        language: str,
    ) -> dict[str, Any]:
        payload = self._payload(source_artifact)
        source = self._source_meta(run=run, source_artifact=source_artifact, payload=payload)
        export_format = self._export_format(payload)
        data = payload.get("data") if isinstance(payload, dict) else {}
        raw_export_snapshot = data.get("export_snapshot") if isinstance(data, dict) else {}
        export_snapshot = raw_export_snapshot if isinstance(raw_export_snapshot, dict) else {}
        export_sections = self._source_export_sections(export_format, include_body=True)
        coverage_contract = self._coverage_contract(
            export_sections=export_sections,
            export_text=self._export_text(export_snapshot=export_snapshot, export_format=export_format),
            source=source,
        )
        user_question = self._user_question(run)
        question_analysis = self._question_analysis(user_question)
        targeted_contract = self._targeted_analysis_contract(
            user_question=user_question,
            question_analysis=question_analysis,
            coverage=coverage_contract,
        )
        conversation_brief = self._conversation_brief(
            source=source,
            user_question=user_question,
            question_analysis=question_analysis,
            coverage=coverage_contract,
            export_sections=export_sections,
            input_normalized=payload.get("input_normalized") if isinstance(payload.get("input_normalized"), dict) else {},
        )
        return {
            "schema": REPORT_TEMPLATE_SCHEMA,
            "run_id": run["run_id"],
            "tool_name": source["tool_name"],
            "technique": source["technique"],
            "language": language,
            "user_question": user_question,
            "question_analysis": question_analysis,
            "required_sections": list(REQUIRED_SECTIONS),
            "ai_instructions": [
                "你是在任意 AI 对话窗口里为用户解盘：先读 source_context 的真实盘面结果，再回答 user_question。",
                "输出应像一次完整咨询后的结论，而不是字段解释、技术日志或模板说明。",
                "必须先直接回答用户问的事情，再说明盘面依据、推理步骤、风险边界和下一步建议。",
                "每个关键判断都尽量绑定 evidence 或 source_section_title；不要脱离盘面编造结论。",
            ],
            "conversation_brief": conversation_brief,
            "coverage_contract": coverage_contract,
            "targeted_analysis_contract": targeted_contract,
            "source_context": {
                "input_normalized": payload.get("input_normalized") if isinstance(payload.get("input_normalized"), dict) else {},
                "summary": payload.get("summary") if isinstance(payload.get("summary"), list) else [],
                "export_text": self._export_text(export_snapshot=export_snapshot, export_format=export_format),
                "export_sections": export_sections,
                "provenance": self._provenance(export_snapshot=export_snapshot, export_format=export_format, source=source),
            },
            "source_export_sections": [
                {key: value for key, value in section.items() if key not in {"body", "lines"}}
                for section in export_sections
            ],
            "ai_fillable": {
                "analysis_focus": user_question,
                "question_analysis": question_analysis,
                "answer_plan": targeted_contract["answer_plan"],
                "targeted_answer_requirements": targeted_contract["targeted_answer_requirements"],
                "direct_answer": "",
                "executive_summary": "",
                "answer_text": "",
                "analysis_sections": [
                    {
                        "title": section["title"],
                        "body": "",
                        "evidence_lines": [],
                        "relevance_to_question": "",
                        "confidence": "medium",
                    }
                    for section in export_sections
                ],
                "recommendations": [],
                "limitations": [],
                "evidence": [],
                "follow_up_questions": [],
            },
            "source": source,
        }

    def _conversation_brief(
        self,
        *,
        source: dict[str, Any],
        user_question: str,
        question_analysis: dict[str, Any],
        coverage: dict[str, Any],
        export_sections: list[dict[str, Any]],
        input_normalized: dict[str, Any],
    ) -> dict[str, Any]:
        section_titles = [str(section.get("title")) for section in export_sections if section.get("title")]
        return {
            "schema": "horosa.skill.report.conversation_brief.v1",
            "role": "你是接入 Horosa Skill 的 AI 解盘助手，正在根据本地离线算法算出的真实盘面回答用户。",
            "user_context": {
                "question": user_question or "用户没有给出明确问题，请做整体综合解盘。",
                "input_normalized": input_normalized,
                "focus_domains": question_analysis.get("focus_domains", []),
                "needs_timing": question_analysis.get("needs_timing"),
                "needs_decision_support": question_analysis.get("needs_decision_support"),
            },
            "plate_context": {
                "tool_name": source.get("tool_name"),
                "technique": source.get("technique"),
                "technique_label": source.get("technique_label"),
                "source_sections": section_titles,
                "must_read": [
                    "source_context.export_text",
                    "source_context.export_sections",
                    "source_context.input_normalized",
                    "targeted_analysis_contract",
                ],
            },
            "interpretation_method": [
                "先用一句话回答用户的问题，明确能不能、该不该、风险在哪里或整体主题是什么。",
                "再说明你看了哪些盘面信息：起盘信息、核心结构、关键章节、特殊征象、时间/阶段线索。",
                "把盘面线索翻译成人能听懂的现实含义，不要只重复术语。",
                "如果问题涉及时间窗口、选择、风险或财务，必须给出阶段判断和保守/进取边界。",
                "如果盘面材料不足以判断，直接说明不足，不要硬编。",
                "不要把空字段或缺失章节解释成需要 MongoDB、7897 端口、星阙桌面应用、远程数据库或外部服务；Horosa Skill 的公开能力以本地离线 runtime 为准。",
            ],
            "output_style": [
                "像在 AI 对话窗口中完成一次认真解盘后给出的最终回复。",
                "中文、自然、有结论、有依据、有行动建议。",
                "不要输出代码、JSON 字段名、schema、run_id、内部路径或机器日志。",
                "不要说“待 AI 分析”“模板要求”“根据框架应当”，要直接给用户可读结论。",
                "如果工具返回错误或材料不足，只说明本次本地工具返回不足，并建议重新运行 doctor/openclaw-check 或补齐输入；不要臆造 MongoDB/桌面端依赖。",
            ],
            "final_ai_report_contract": {
                "answer_text": "完整对话式解盘正文，适合作为报告主体。",
                "direct_answer": "一句话直接结论。",
                "executive_summary": "3-6 条摘要。",
                "analysis_sections": "按问题和盘面分节解释，每节绑定证据线索。",
                "recommendations": "可执行建议。",
                "limitations": "限制、风险和不可判断处。",
                "evidence": "关键判断对应的盘面章节或原文线索。",
            },
            "coverage_required": coverage.get("must_explain_sections", []),
        }

    def build_document(
        self,
        *,
        run: dict[str, Any],
        source_artifact: dict[str, Any],
        language: str,
        title: str | None = None,
        ai_report: dict[str, Any] | None = None,
        include_raw_json: bool = False,
    ) -> dict[str, Any]:
        payload = self._payload(source_artifact)
        data = payload.get("data") if isinstance(payload, dict) else {}
        source = self._source_meta(run=run, source_artifact=source_artifact, payload=payload)
        raw_export_snapshot = data.get("export_snapshot") if isinstance(data, dict) else {}
        export_snapshot = raw_export_snapshot if isinstance(raw_export_snapshot, dict) else {}
        export_format = self._export_format(payload)
        input_normalized = payload.get("input_normalized") if isinstance(payload, dict) else {}
        summary = payload.get("summary") if isinstance(payload, dict) else []
        export_text = self._export_text(export_snapshot=export_snapshot, export_format=export_format)
        export_sections = self._source_export_sections(export_format, include_body=True)
        merged_ai_report = self._merge_ai_report(
            run=run,
            ai_report=ai_report,
            source=source,
            input_normalized=input_normalized if isinstance(input_normalized, dict) else {},
            summary=summary if isinstance(summary, list) else [str(summary)] if summary else [],
            export_sections=export_sections,
            export_text=export_text,
        )
        coverage = self._coverage_contract(export_sections=export_sections, export_text=export_text, source=source)
        user_question = self._user_question(run)
        question_analysis = self._question_analysis(user_question)
        targeted_contract = self._targeted_analysis_contract(
            user_question=user_question,
            question_analysis=question_analysis,
            coverage=coverage,
        )
        ai_coverage = self._ai_coverage_status(coverage=coverage, ai_report=merged_ai_report)
        coverage_matrix = self._section_coverage_matrix(export_sections=export_sections, ai_report=merged_ai_report)
        provenance = self._provenance(export_snapshot=export_snapshot, export_format=export_format, source=source)
        report_quality = self._report_quality(
            input_normalized=input_normalized if isinstance(input_normalized, dict) else {},
            export_text=export_text,
            export_sections=export_sections,
            ai_report=merged_ai_report,
            ai_coverage=ai_coverage,
            provenance=provenance,
        )

        generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        technique_title = source.get("technique_label") or source.get("technique") or source.get("tool_name")
        report_title = title or f"结构化咨询报告 · {technique_title}"
        sections = [
            {
                "id": "report_metadata",
                "title": "报告元信息",
                "body": self._format_report_metadata(
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
                "body": self._format_report_quality(report_quality),
                "items": report_quality,
            },
            {
                "id": "delivery_checklist",
                "title": "交付检查清单",
                "body": "",
                "items": {},
            },
            {
                "id": "coverage_contract",
                "title": "AI 解释覆盖清单",
                "body": self._format_coverage(coverage),
                "items": coverage,
            },
            {
                "id": "section_coverage_matrix",
                "title": "逐章解释覆盖矩阵",
                "body": self._format_section_coverage_matrix(coverage_matrix),
                "items": coverage_matrix,
            },
            {
                "id": "targeted_analysis_contract",
                "title": "针对性解盘要求",
                "body": self._format_targeting(targeted_contract),
                "items": targeted_contract,
            },
            {
                "id": "question_analysis",
                "title": "用户问题拆解",
                "body": self._format_question_analysis(question_analysis),
                "items": question_analysis,
            },
            {
                "id": "input_overview",
                "title": "输入信息",
                "body": self._format_mapping(input_normalized if isinstance(input_normalized, dict) else {}),
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
                "body": self._format_ai_report(merged_ai_report),
                "items": merged_ai_report,
            },
            {
                "id": "recommendations_limitations",
                "title": "建议、限制与追问",
                "body": self._format_recommendations_limitations(merged_ai_report),
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
        sections.extend(self._document_sections_from_export_format(export_format))
        sections.append(
            {
                "id": "provenance",
                "title": "来源追溯",
                "body": self._format_mapping(provenance),
                "items": provenance,
            }
        )
        content_outline = self._content_outline(sections)
        plain_text = self._plain_text_report(title=report_title, generated_at=generated_at, sections=sections)
        search_index = self._search_index(
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
        delivery_checklist = self._delivery_checklist(
            sections=sections,
            coverage=coverage,
            coverage_matrix=coverage_matrix,
            report_quality=report_quality,
            question_analysis=question_analysis,
            targeted_contract=targeted_contract,
            ai_report=merged_ai_report,
            provenance=provenance,
            content_outline=content_outline,
            plain_text=plain_text,
            search_index=search_index,
        )
        sections[2]["body"] = self._format_delivery_checklist(delivery_checklist)
        sections[2]["items"] = delivery_checklist
        content_outline = self._content_outline(sections)
        plain_text = self._plain_text_report(title=report_title, generated_at=generated_at, sections=sections)
        search_index = self._search_index(
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

        return {
            "schema": REPORT_DOCUMENT_SCHEMA,
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
                "has_ai_answer": bool(merged_ai_report.get("answer_text") or merged_ai_report.get("executive_summary")),
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

    def _payload(self, source_artifact: dict[str, Any]) -> dict[str, Any]:
        payload = source_artifact.get("payload")
        return payload if isinstance(payload, dict) else {}

    def _export_format(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = payload.get("data") if isinstance(payload, dict) else {}
        export_format = data.get("export_format") if isinstance(data, dict) else {}
        return export_format if isinstance(export_format, dict) else {}

    def _source_meta(
        self,
        *,
        run: dict[str, Any],
        source_artifact: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        data = payload.get("data") if isinstance(payload, dict) else {}
        export_snapshot = data.get("export_snapshot") if isinstance(data, dict) else {}
        technique = export_snapshot.get("technique") if isinstance(export_snapshot, dict) else {}
        record_meta = payload.get("record_meta") if isinstance(payload, dict) else {}
        return {
            "tool_name": payload.get("tool") or source_artifact.get("tool_name"),
            "technique": technique.get("key") if isinstance(technique, dict) else None,
            "technique_label": technique.get("label") if isinstance(technique, dict) else None,
            "artifact_path": source_artifact.get("path"),
            "artifact_kind": source_artifact.get("kind"),
            "trace_id": payload.get("trace_id") or (record_meta or {}).get("trace_id"),
            "group_id": payload.get("group_id") or run.get("group_id") or (record_meta or {}).get("group_id"),
        }

    def _source_export_sections(self, export_format: dict[str, Any], *, include_body: bool = False) -> list[dict[str, Any]]:
        sections = export_format.get("sections")
        if not isinstance(sections, list):
            return []
        result: list[dict[str, Any]] = []
        for index, section in enumerate(sections, start=1):
            if not isinstance(section, dict):
                continue
            lines = section.get("lines") if isinstance(section.get("lines"), list) else []
            body = section.get("body")
            if not body and lines:
                body = "\n".join(str(line) for line in lines)
            section_payload = {
                "id": section.get("id") or f"section_{index}",
                "title": str(section.get("title") or f"Section {index}"),
                "line_count": len(lines),
            }
            if include_body:
                section_payload["body"] = str(body or "")
                section_payload["lines"] = [str(line) for line in lines]
            result.append(section_payload)
        return result

    def _document_sections_from_export_format(self, export_format: dict[str, Any]) -> list[dict[str, Any]]:
        sections = export_format.get("sections")
        if not isinstance(sections, list):
            return []
        result: list[dict[str, Any]] = []
        for index, section in enumerate(sections, start=1):
            if not isinstance(section, dict):
                continue
            lines = section.get("lines")
            body = section.get("body")
            if not body and isinstance(lines, list):
                body = "\n".join(str(line) for line in lines)
            result.append(
                {
                    "id": section.get("id") or f"export_section_{index}",
                    "title": str(section.get("title") or f"导出章节 {index}"),
                    "body": str(body or ""),
                    "items": section,
                }
            )
        return result

    def _merge_ai_report(
        self,
        *,
        run: dict[str, Any],
        ai_report: dict[str, Any] | None,
        source: dict[str, Any],
        input_normalized: dict[str, Any],
        summary: list[Any],
        export_sections: list[dict[str, Any]],
        export_text: str,
    ) -> dict[str, Any]:
        answer_structured = run.get("ai_answer_structured")
        if isinstance(answer_structured, dict):
            base = copy.deepcopy(answer_structured)
        else:
            base = {}
        if run.get("ai_answer_text") and "answer_text" not in base:
            base["answer_text"] = run.get("ai_answer_text")
        if ai_report:
            base.update(copy.deepcopy(ai_report))
        base_has_answer_text = bool(str(base.get("answer_text") or "").strip())
        base_has_executive_summary = bool(str(base.get("executive_summary") or base.get("summary") or "").strip())
        base_has_consultation_basis = bool(base.get("consultation_basis"))
        base_has_reading_steps = bool(base.get("reading_steps"))
        base_has_analysis_sections = isinstance(base.get("analysis_sections"), list) and bool(base.get("analysis_sections"))
        base_has_recommendations = isinstance(base.get("recommendations"), list) and bool(base.get("recommendations"))
        base_has_limitations = isinstance(base.get("limitations"), list) and bool(base.get("limitations"))
        default_report = self._default_ai_report(
            run=run,
            source=source,
            input_normalized=input_normalized,
            summary=summary,
            export_sections=export_sections,
            export_text=export_text,
        )
        merged = copy.deepcopy(default_report)
        for key, value in base.items():
            if value not in (None, "", [], {}):
                merged[key] = value
        merged["analysis_sections"] = self._complete_analysis_sections(
            analysis_sections=merged.get("analysis_sections") if isinstance(merged.get("analysis_sections"), list) else [],
            default_sections=default_report.get("analysis_sections") if isinstance(default_report.get("analysis_sections"), list) else [],
            export_sections=export_sections,
        )
        # Machine JSON keeps deterministic coverage backfills. Human DOCX/PDF should not
        # turn those backfills into "AI-written" prose when the client supplied a single
        # natural-language answer_text, which is the common path for Cursor/OpenClaw/etc.
        if base_has_answer_text and not base_has_analysis_sections:
            human_analysis_sections: list[Any] = []
        else:
            human_analysis_sections = merged.get("analysis_sections") if isinstance(merged.get("analysis_sections"), list) else []
        if base_has_answer_text and not base_has_recommendations:
            human_recommendations: list[Any] = []
        else:
            human_recommendations = merged.get("recommendations") if isinstance(merged.get("recommendations"), list) else []
        if base_has_answer_text and not base_has_limitations:
            human_limitations: list[Any] = []
        else:
            human_limitations = merged.get("limitations") if isinstance(merged.get("limitations"), list) else []
        human_executive_summary = (
            merged.get("executive_summary") or merged.get("summary") or ""
            if base_has_executive_summary or not base_has_answer_text
            else ""
        )
        human_consultation_basis = merged.get("consultation_basis") or "" if base_has_consultation_basis or not base_has_answer_text else ""
        human_reading_steps = (
            merged.get("reading_steps")
            if isinstance(merged.get("reading_steps"), list) and (base_has_reading_steps or not base_has_answer_text)
            else []
        )
        return {
            "analysis_focus": merged.get("analysis_focus") or "",
            "direct_answer": merged.get("direct_answer") or merged.get("answer") or "",
            "consultation_basis": merged.get("consultation_basis") or "",
            "reading_steps": merged.get("reading_steps") if isinstance(merged.get("reading_steps"), list) else [],
            "executive_summary": merged.get("executive_summary") or merged.get("summary") or "",
            "analysis_sections": merged.get("analysis_sections") if isinstance(merged.get("analysis_sections"), list) else [],
            "recommendations": merged.get("recommendations") if isinstance(merged.get("recommendations"), list) else [],
            "limitations": merged.get("limitations") if isinstance(merged.get("limitations"), list) else [],
            "evidence": merged.get("evidence") if isinstance(merged.get("evidence"), list) else [],
            "follow_up_questions": merged.get("follow_up_questions") if isinstance(merged.get("follow_up_questions"), list) else [],
            "answer_text": merged.get("answer_text") or "",
            "human_executive_summary": human_executive_summary,
            "human_consultation_basis": human_consultation_basis,
            "human_reading_steps": human_reading_steps,
            "human_analysis_sections": human_analysis_sections,
            "human_recommendations": human_recommendations,
            "human_limitations": human_limitations,
            "raw": merged,
        }

    def _complete_analysis_sections(
        self,
        *,
        analysis_sections: list[Any],
        default_sections: list[Any],
        export_sections: list[dict[str, Any]],
    ) -> list[Any]:
        """Preserve the AI's targeted answer while backfilling source-section coverage."""
        completed = copy.deepcopy(analysis_sections)
        if not export_sections:
            return completed or copy.deepcopy(default_sections)
        for index, source_section in enumerate(export_sections, start=1):
            source_title = str(source_section.get("title") or f"导出章节 {index}")
            if any(self._analysis_section_matches_source(section, source_title) for section in completed):
                continue
            default_match = next(
                (
                    section
                    for section in default_sections
                    if self._analysis_section_matches_source(section, source_title)
                ),
                None,
            )
            if default_match:
                completed.append(copy.deepcopy(default_match))
        existing_titles = {
            str(section.get("title") or section.get("source_section_title") or "").strip()
            for section in completed
            if isinstance(section, dict)
        }
        for default_section in default_sections:
            if not isinstance(default_section, dict):
                continue
            default_title = str(default_section.get("title") or default_section.get("source_section_title") or "").strip()
            if default_title and default_title not in existing_titles:
                completed.append(copy.deepcopy(default_section))
                existing_titles.add(default_title)
        return completed

    def _analysis_section_matches_source(self, section: Any, source_title: str) -> bool:
        if not isinstance(section, dict):
            return False
        ai_title = str(section.get("source_section_title") or section.get("title") or "")
        evidence_lines = section.get("evidence_lines") if isinstance(section.get("evidence_lines"), list) else []
        evidence_text = " ".join(str(item) for item in evidence_lines)
        return bool(
            ai_title == source_title
            or (source_title and source_title in ai_title)
            or (ai_title and ai_title in source_title)
            or (source_title and source_title in evidence_text)
        )

    def _default_ai_report(
        self,
        *,
        run: dict[str, Any],
        source: dict[str, Any],
        input_normalized: dict[str, Any],
        summary: list[Any],
        export_sections: list[dict[str, Any]],
        export_text: str,
    ) -> dict[str, Any]:
        question = self._consultation_question(self._user_question(run))
        technique = str(source.get("technique") or source.get("tool_name") or "")
        if technique in {"bazi", "bazi_birth", "bazi_direct"} or str(source.get("tool_name") or "").startswith("bazi"):
            return self._default_bazi_report(
                question=question,
                source=source,
                input_normalized=input_normalized,
                export_sections=export_sections,
                export_text=export_text,
            )
        return self._default_generic_report(
            question=question,
            source=source,
            input_normalized=input_normalized,
            summary=summary,
            export_sections=export_sections,
            export_text=export_text,
        )

    def _default_generic_report(
        self,
        *,
        question: str,
        source: dict[str, Any],
        input_normalized: dict[str, Any],
        summary: list[Any],
        export_sections: list[dict[str, Any]],
        export_text: str,
    ) -> dict[str, Any]:
        technique_label = source.get("technique_label") or source.get("technique") or source.get("tool_name") or "当前技法"
        profile = self._technique_report_profile(source)
        source_titles = [str(section.get("title")) for section in export_sections if section.get("title")]
        focus_text = self._focus_text(question)
        consultation_basis = self._generic_consultation_basis(
            input_normalized=input_normalized,
            technique_label=str(technique_label),
        )
        analysis_sections = [
            {
                "title": "整体结论",
                "source_section_title": source_titles[0] if source_titles else "工具摘要",
                "body": self._generic_overview_text(
                    technique_label=str(technique_label),
                    question=question,
                    summary=summary,
                    export_sections=export_sections,
                    profile=profile,
                ),
                "evidence_lines": self._evidence_from_sections(export_sections, limit=4) or [str(item) for item in summary[:3]],
                "relevance_to_question": "直接回应本次咨询主题，先给读者一个可落地的判断框架。",
                "confidence": "medium",
            }
        ]
        for section in export_sections:
            title = str(section.get("title") or "导出章节")
            analysis_sections.append(
                {
                    "title": title,
                    "source_section_title": title,
                    "body": self._section_reading_body(section, profile=profile),
                    "evidence_lines": self._clean_lines(section.get("lines") if isinstance(section.get("lines"), list) else [], limit=5),
                    "relevance_to_question": "把原始导出章节翻译成读者能理解的现实含义。",
                    "confidence": "medium",
                }
            )
        return {
            "analysis_focus": question,
            "consultation_basis": consultation_basis,
            "reading_steps": self._generic_reading_steps(profile=profile, question=question),
            "direct_answer": self._generic_direct_answer(
                question=question,
                technique_label=str(technique_label),
                profile=profile,
                focus_text=focus_text,
            ),
            "executive_summary": "\n".join(
                [
                    f"本次咨询主题：{question}。",
                    f"采用技法：{technique_label}；阅读重心是{profile['basis']}。",
                    f"报告会把盘面线索转化为{focus_text}，并按{profile['decision_style']}给出可读结论。",
                ]
            ),
            "analysis_sections": analysis_sections,
            "recommendations": [
                f"先阅读“整体结论”，再按{profile['evidence_name']}核对原始盘面线索。",
                "如果用于真实决策，请补充具体问题、时间范围、背景约束与已知事实。",
                f"可继续要求 AI 按{profile['recommended_followup']}做专项展开。",
            ],
            "limitations": [
                "本报告基于本地工具输出进行解释，不替代专业法律、医疗、财务意见。",
                "未提供现实背景时，判断会偏向盘面结构解读，具体落点需要二次追问校准。",
            ],
            "evidence": self._evidence_from_sections(export_sections, limit=10) or [export_text[:300]] if export_text else [],
            "follow_up_questions": [
                "你最想优先分析事业、关系、财务还是阶段运势？",
                "这次报告是用于复盘过去、判断当下，还是规划未来？",
            ],
        }

    def _default_bazi_report(
        self,
        *,
        question: str,
        source: dict[str, Any],
        input_normalized: dict[str, Any],
        export_sections: list[dict[str, Any]],
        export_text: str,
    ) -> dict[str, Any]:
        question = self._consultation_question(question)
        pillars = self._extract_bazi_pillars(export_text)
        day_master = self._day_master_text(pillars.get("日柱"))
        element_counts = self._bazi_element_counts(pillars)
        element_text = "、".join(f"{name}{count}" for name, count in element_counts.items() if count)
        strongest = max(element_counts, key=element_counts.get) if element_counts else ""
        weakest = min(element_counts, key=element_counts.get) if element_counts else ""
        focus_text = self._focus_text(question)
        subject_profile = self._bazi_subject_profile(input_normalized=input_normalized, pillars=pillars, day_master=day_master)
        consultation_basis = self._bazi_consultation_basis(
            input_normalized=input_normalized,
            pillars=pillars,
            day_master=day_master,
        )
        decision_hint = self._bazi_decision_hint(question=question, day_master=day_master, counts=element_counts)
        core_lines = [
            f"四柱为：{self._format_pillars(pillars)}。" if pillars else "四柱信息已从星阙导出中读取。",
            f"日主为{day_master}，报告会以日主承载力、月令环境、五行流动和神煞提示为主线。" if day_master else "报告会以四柱结构、五行流动和神煞提示为主线。",
            f"从明面干支粗略计数看，五行分布为：{element_text}；其中{strongest}相对突出，{weakest}相对需要被留意。" if element_counts else "五行强弱需要结合藏干、月令、大运流年继续细化。",
        ]
        evidence = self._evidence_from_sections(export_sections, limit=12)
        start_info = self._section_by_title(export_sections, "起盘信息")
        pillars_info = self._section_by_title(export_sections, "四柱")
        direction_info = self._section_by_title(export_sections, "流年")
        gods_info = self._section_by_title(export_sections, "神煞")
        analysis_sections = [
            {
                "title": "个案档案",
                "source_section_title": "起盘信息",
                "body": subject_profile,
                "evidence_lines": self._clean_lines(start_info.get("lines", []) if start_info else [], limit=6),
                "relevance_to_question": "先固定这个人的出生资料、四柱与日主，确保后续解读围绕同一个个案。",
                "confidence": "high",
            },
            {
                "title": "本次问题定向判断",
                "source_section_title": "综合解读",
                "body": self._bazi_targeted_reading(
                    question=question,
                    day_master=day_master,
                    counts=element_counts,
                    decision_hint=decision_hint,
                ),
                "evidence_lines": [f"咨询主题：{question}", f"五行粗略计数：{element_text}"] if element_text else [f"咨询主题：{question}"],
                "relevance_to_question": "把命局结构直接落到本次具体问题，避免只做泛泛命盘说明。",
                "confidence": "medium",
            },
            {
                "title": "命盘核心结论",
                "source_section_title": "四柱与三元",
                "body": "\n".join(
                    [
                        "这张八字的阅读重点不应停留在“列出四柱”，而要看它呈现出的性格驱动力、资源调度方式和人生议题。",
                        *core_lines,
                        "整体上，它更适合被解读为一张需要在自我主张、现实秩序、资源压力与行动节奏之间找到平衡的命盘。",
                    ]
                ),
                "evidence_lines": self._clean_lines(pillars_info.get("lines", []) if pillars_info else [], limit=6),
                "relevance_to_question": "回应用户要一份能直接看的最终解读，而不是原始字段堆叠。",
                "confidence": "medium",
            },
            {
                "title": "起盘信息与时间可靠性",
                "source_section_title": "起盘信息",
                "body": self._bazi_starting_context(start_info, input_normalized),
                "evidence_lines": self._clean_lines(start_info.get("lines", []) if start_info else [], limit=8),
                "relevance_to_question": "确认报告使用的时间、地点、真太阳时等基础信息，避免后续判断失根。",
                "confidence": "high",
            },
            {
                "title": "日主与命局气势",
                "source_section_title": "四柱与三元",
                "body": self._bazi_day_master_reading(pillars, day_master, element_counts),
                "evidence_lines": self._clean_lines(pillars_info.get("lines", []) if pillars_info else [], limit=8),
                "relevance_to_question": "把四柱翻译成可理解的人格与行动结构。",
                "confidence": "medium",
            },
            {
                "title": "五行流动与现实议题",
                "source_section_title": "四柱与三元",
                "body": self._bazi_element_reading(element_counts),
                "evidence_lines": [f"五行粗略计数：{element_text}"] if element_text else [],
                "relevance_to_question": "解释命盘中不同力量如何落到工作、资源、表达和压力管理。",
                "confidence": "medium",
            },
            {
                "title": "大运流年与阶段判断",
                "source_section_title": "流年行运概略",
                "body": self._bazi_liunian_reading(direction_info, question=question),
                "evidence_lines": self._section_lines(direction_info, limit=12),
                "relevance_to_question": "把八字从静态命局推进到阶段运势，尤其用于事业、财务、关系和时间窗口问题。",
                "confidence": "medium",
            },
            {
                "title": "神煞提示与事件倾向",
                "source_section_title": "神煞（四柱与三元）",
                "body": self._bazi_shensha_reading(gods_info),
                "evidence_lines": self._clean_lines(gods_info.get("lines", []) if gods_info else [], limit=10),
                "relevance_to_question": "将神煞从名单翻译为可读的提醒，而不是机械堆砌。",
                "confidence": "medium",
            },
            {
                "title": "事业、关系与财务建议",
                "source_section_title": "综合解读",
                "body": self._bazi_life_advice(day_master, element_counts),
                "evidence_lines": evidence[:6],
                "relevance_to_question": "把盘面信息落到可操作的生活和决策建议。",
                "confidence": "medium",
            },
        ]
        covered_titles = {
            str(section.get("source_section_title") or section.get("title") or "")
            for section in analysis_sections
            if isinstance(section, dict)
        }
        for section in export_sections:
            title = str(section.get("title") or "")
            if not title or title in covered_titles:
                continue
            analysis_sections.append(
                {
                    "title": title,
                    "source_section_title": title,
                    "body": self._section_reading_body(section),
                    "evidence_lines": self._clean_lines(section.get("lines") if isinstance(section.get("lines"), list) else [], limit=6),
                    "relevance_to_question": "保留并解释星阙导出的完整章节，避免最终报告缺漏。",
                    "confidence": "medium",
                }
            )
        return {
            "analysis_focus": question,
            "consultation_basis": consultation_basis,
            "reading_steps": self._bazi_reading_steps(question),
            "direct_answer": f"就「{question}」来看，结论上：{decision_hint} 这张八字的主线是以{day_master or '日主'}为中心，在自我主张、现实秩序、资源压力与行动节奏之间找平衡；具体判断应优先落到{focus_text}，并用大运流年继续校准时间点。",
            "executive_summary": "\n".join(
                [
                    f"个案主线：{self._format_pillars(pillars) or '四柱信息已读取'}；日主：{day_master or '未明'}。",
                    f"本次咨询重点：{question}；报告会把命局结构转译为{focus_text}。",
                    "结论先行：这张盘适合从长期积累、资源调度、规则边界和执行节奏入手解读；短期事件和具体年份仍需叠加大运流年。",
                ]
            ),
            "analysis_sections": analysis_sections,
            "recommendations": [
                "如果要继续精读，优先补充大运、流年和当前最关心的问题，这会显著提高判断针对性。",
                "把报告中的“强项”用于职业定位和资源配置，把“压力点”用于制定边界、节奏和风险预案。",
                "涉及关系、投资、健康等现实决策时，把八字结论作为观察框架，不要替代事实核查与专业意见。",
            ],
            "limitations": [
                "本报告采用本地八字工具输出与确定性解释模板生成，未调用外部 AI API。",
                "五行计数是基于明面干支的阅读辅助，不等于完整旺衰定格；完整判断仍需结合藏干、月令、通根、调候、大运流年。",
                "神煞只作为提示线索，不宜单独作为吉凶断语。",
            ],
            "evidence": evidence,
            "follow_up_questions": [
                "要不要继续生成大运流年版，把事业、财务、关系分年份展开？",
                "你更想看性格结构、职业路径、感情关系，还是未来三年的阶段重点？",
                "出生时间是否确定到分钟？如果不确定，可以比较相邻时辰差异。",
            ],
        }

    def _generic_overview_text(
        self,
        *,
        technique_label: str,
        question: str,
        summary: list[Any],
        export_sections: list[dict[str, Any]],
        profile: dict[str, str],
    ) -> str:
        summary_text = "；".join(str(item) for item in summary[:4] if str(item).strip())
        section_text = "、".join(str(section.get("title")) for section in export_sections[:6] if section.get("title"))
        lines = [
            f"本次咨询使用 {technique_label} 处理「{question}」。",
            f"这类技法的阅读重点是{profile['basis']}；报告会优先把它翻译成{profile['decision_style']}。",
            f"盘面返回的核心摘要为：{summary_text}。" if summary_text else "",
            f"可用于判断的主要章节包括：{section_text}。" if section_text else "",
            f"阅读顺序建议：先看整体结论，再按{profile['evidence_name']}核对依据，最后看建议与限制。",
        ]
        return "\n".join(line for line in lines if line)

    def _generic_reading_steps(self, *, profile: dict[str, str], question: str) -> list[str]:
        steps = [
            f"先确认起盘依据：时间、地点、参数和本技法所需输入是否完整。",
            f"再抓主线：优先看{profile['basis']}，不要从单个词或单个字段直接下断语。",
            f"然后按问题落点拆解：把盘面线索转成{profile['decision_style']}。",
            f"最后给行动建议：明确可推进事项、风险边界、需要补充的信息和下一步追问方向。",
        ]
        if question == "综合命局咨询":
            steps[2] = f"然后做整体综合解盘：把盘面线索转成{profile['decision_style']}，同时覆盖机会、压力和风险边界。"
        return steps

    def _generic_consultation_basis(self, *, input_normalized: dict[str, Any], technique_label: str) -> str:
        date = input_normalized.get("date") or input_normalized.get("birth_date")
        time = input_normalized.get("time") or input_normalized.get("birth_time")
        zone = input_normalized.get("zone") or input_normalized.get("timezone")
        lat = input_normalized.get("lat") or input_normalized.get("gpsLat")
        lon = input_normalized.get("lon") or input_normalized.get("gpsLon")
        parts: list[str] = []
        if date or time:
            parts.append(f"起盘时间：{date or '未提供日期'} {time or '未提供时间'}")
        if zone:
            parts.append(f"时区：{zone}")
        if lon or lat:
            parts.append(f"地点：经度 {lon or '未提供'}，纬度 {lat or '未提供'}")
        if not parts:
            return f"本报告基于 {technique_label} 的本地起盘结果生成；若要进一步校准，请补充时间、地点与问题背景。"
        return "；".join(parts) + "。"

    def _bazi_consultation_basis(
        self,
        *,
        input_normalized: dict[str, Any],
        pillars: dict[str, str],
        day_master: str,
    ) -> str:
        parts = [self._generic_consultation_basis(input_normalized=input_normalized, technique_label="八字").rstrip("。")]
        formatted = self._format_pillars(pillars)
        if formatted:
            parts.append(f"四柱：{formatted}")
        if day_master:
            parts.append(f"日主：{day_master}")
        return "；".join(part for part in parts if part) + "。"

    def _generic_direct_answer(
        self,
        *,
        question: str,
        technique_label: str,
        profile: dict[str, str],
        focus_text: str,
    ) -> str:
        if question == "综合命局咨询":
            return (
                f"在没有指定单一问题时，这份{technique_label}报告会按整体全面解读处理：先看{profile['basis']}，"
                f"再提炼主要机会、压力、风险边界和后续可追问方向；阅读重点放在{profile['decision_style']}。"
            )
        decision_hint = self._generic_decision_hint(question)
        return (
            f"就「{question}」来看，结论上：{decision_hint}"
            f"{technique_label}的判断重点是先看{profile['basis']}，再把关键章节落到{focus_text}；"
            f"后续解释应按{profile['decision_style']}展开，"
            "不要只看单个字段或孤立吉凶。"
        )

    def _generic_decision_hint(self, question: str) -> str:
        analysis = self._question_analysis(question)
        domains = set(analysis.get("focus_domains") if isinstance(analysis.get("focus_domains"), list) else [])
        hints: list[str] = []
        if "career" in domains:
            hints.append("事业上应先判断当前环境是否能持续积累能力、信用和资源，不宜只被短期机会牵动")
        if "wealth" in domains:
            hints.append("财务上应把现金流、风险上限和可复盘机制放在收益想象之前，高杠杆或边界不清的选择要谨慎")
        if "relationship" in domains:
            hints.append("关系上应先分清双方责任、互动节奏和真实需求，再判断推进或收缩")
        if "health" in domains:
            hints.append("健康相关只给趋势提醒，具体诊断应交给专业医疗判断")
        if "study" in domains:
            hints.append("学习申请上应把准备节奏、资源支持和关键时间点拆开评估")
        if "relocation" in domains:
            hints.append("迁移远行上应同时评估环境收益、成本、手续和后续承接能力")
        if analysis.get("needs_timing"):
            hints.append("时间上先按阶段顺序判断，具体年月需要结合对应推运或应期材料再细化")
        if analysis.get("needs_decision_support"):
            hints.append("决策上优先选择下行风险可控、证据更充分、能长期累积的方案")
        if not hints:
            hints.append("先做整体结构判断，再把机会、压力、风险边界和下一步追问拆开看")
        return "；".join(hints) + "。"

    def _technique_report_profile(self, source: dict[str, Any]) -> dict[str, str]:
        tool = str(source.get("tool_name") or "")
        technique = str(source.get("technique") or "")
        label = str(source.get("technique_label") or "")
        key = f"{tool} {technique} {label}"
        profiles: list[tuple[tuple[str, ...], dict[str, str]]] = [
            (
                ("qimen", "奇门"),
                {
                    "basis": "起局时间、值符值使、门星神仪、宫位关系和演卦变化",
                    "decision_style": "当下局势、可用路径、行动窗口与避险方向",
                    "evidence_name": "门、星、神、宫与演卦",
                    "recommended_followup": "用神、宫位、门星组合、时间窗口或行动方案",
                },
            ),
            (
                ("liureng", "六壬"),
                {
                    "basis": "课传、四课三传、天将神煞、日辰关系和发用线索",
                    "decision_style": "事情来龙去脉、应期倾向、成败条件和风险点",
                    "evidence_name": "课传、天将、日辰与神煞",
                    "recommended_followup": "发用、三传、应期、关系人或具体事件路径",
                },
            ),
            (
                ("jinkou", "金口诀"),
                {
                    "basis": "地分、贵神、将神、人元、旺衰与五动关系",
                    "decision_style": "事件吉凶、主动/被动关系、资源阻力和行动取舍",
                    "evidence_name": "地分、贵神、将神、人元与旺衰",
                    "recommended_followup": "用神、旺衰、五动、成败条件或应期",
                },
            ),
            (
                ("taiyi", "太乙"),
                {
                    "basis": "太乙局数、主客算、宫神分布和局势攻守",
                    "decision_style": "大势判断、攻守策略、风险等级和时局取向",
                    "evidence_name": "局数、主客算、宫位和神将",
                    "recommended_followup": "主客、局数、宫位、时局趋势或策略建议",
                },
            ),
            (
                ("sixyao", "gua", "易卦", "六爻"),
                {
                    "basis": "本卦、变卦、动爻、六亲六神和卦辞爻辞",
                    "decision_style": "问题成败、关系结构、变化方向和可执行建议",
                    "evidence_name": "卦象、动爻、六亲、六神和卦辞",
                    "recommended_followup": "用神、世应、动爻、变卦或具体选择",
                },
            ),
            (
                ("ziwei", "紫微"),
                {
                    "basis": "命身宫、十二宫、主星辅曜、四化和大限流年",
                    "decision_style": "性格结构、人生主题、阶段运势和现实选择",
                    "evidence_name": "命宫、身宫、十二宫、星曜和四化",
                    "recommended_followup": "命宫、事业宫、财帛宫、夫妻宫、大限或流年",
                },
            ),
            (
                ("chart", "astro", "星盘", "hellen", "india", "guolao", "relative", "germany"),
                {
                    "basis": "行星落座落宫、宫主关系、相位、接纳和关键虚点",
                    "decision_style": "性格动力、事件主题、关系结构、资源压力与时间线索",
                    "evidence_name": "星体、宫位、相位、宫主和接纳",
                    "recommended_followup": "事业、关系、财务、推运时间点或某个宫位主题",
                },
            ),
            (
                ("solarreturn", "lunarreturn", "solararc", "givenyear", "profection", "primarydirect", "pd", "zr", "firdaria", "decennials", "推运"),
                {
                    "basis": "本命基础与推运盘、返照盘、年限、主限或阶段主星之间的对应",
                    "decision_style": "阶段主题、时间窗口、事件触发点和行动优先级",
                    "evidence_name": "推运参数、时限、主星、宫位和触发相位",
                    "recommended_followup": "具体年份、月份、事业/关系/财务主题或关键触发点",
                },
            ),
            (
                ("suzhan", "宿占"),
                {
                    "basis": "宿度、值宿、形局、斗柄和宿曜关系",
                    "decision_style": "当下气象、人物倾向、事件性质和趋避建议",
                    "evidence_name": "宿度、值宿、形局和宿曜关系",
                    "recommended_followup": "值宿、形局、人物关系或事件吉凶",
                },
            ),
            (
                ("tongshefa", "统摄"),
                {
                    "basis": "阴阳四象、左右卦、潜藏、亲和与主关系",
                    "decision_style": "内外关系、主客力量、变化方向和统摄策略",
                    "evidence_name": "左右卦、潜藏、亲和和主关系",
                    "recommended_followup": "本卦、变卦、潜藏、亲和或主客策略",
                },
            ),
            (
                ("canping", "参评", "金锁银匙"),
                {
                    "basis": "年纳音定部、四柱起数、本命/大运/流年的顺逆歲運条文",
                    "decision_style": "命格定位、运势节律、各运吉凶倾向和趋避建议",
                    "evidence_name": "年纳音部、日宫支命宫、本命与大运/流年歲運条文",
                    "recommended_followup": "本命条文、某段大运、流年走势或趋避策略",
                },
            ),
            (
                ("heluo", "河洛"),
                {
                    "basis": "天地数起先天/后天卦与元堂、命运篇判断、大限·岁运与元堂爻辞",
                    "decision_style": "命卦定位、卦气化工、各大限吉凶节律和趋避建议",
                    "evidence_name": "先天/后天卦、元堂爻辞、命运篇判格和大限岁运",
                    "recommended_followup": "先天/后天爻辞、命运篇判格、某段大限或岁运走势",
                },
            ),
            (
                ("harmonic", "调波"),
                {
                    "basis": "本命各点黄经×调波数得调波位置、同频(合相)关系",
                    "decision_style": "调波主题、同频聚合、强调点和共振议题",
                    "evidence_name": "调波数、各点调波位置和同频合相",
                    "recommended_followup": "某调波数主题、同频组合或某点调波落点",
                },
            ),
            (
                ("sanshi", "三式"),
                {
                    "basis": "奇门、六壬、太乙三式之间的交叉验证",
                    "decision_style": "多体系共振、分歧点、主线结论和稳健建议",
                    "evidence_name": "三式子结果、共振点和分歧点",
                    "recommended_followup": "三式共振、某一式细节、时间窗口或行动方案",
                },
            ),
            (
                ("jieqi", "节气", "nongli", "农历"),
                {
                    "basis": "节气时间、农历转换、太阳节点和年度节律",
                    "decision_style": "时间校准、节律判断、起盘边界和后续排盘依据",
                    "evidence_name": "节气、农历、时间和地点参数",
                    "recommended_followup": "节气节点、农历时间、起盘校准或年度节律",
                },
            ),
        ]
        for markers, profile in profiles:
            if any(marker in key for marker in markers):
                return profile
        return {
            "basis": "起盘输入、工具摘要、导出章节和关键字段之间的关系",
            "decision_style": "整体判断、风险提示、机会线索和后续追问方向",
            "evidence_name": "导出章节和关键字段",
            "recommended_followup": "事业、关系、财务、时间窗口或具体行动方案",
        }

    def _section_reading_body(self, section: dict[str, Any], *, profile: dict[str, str] | None = None) -> str:
        title = str(section.get("title") or "本章节")
        lines = self._clean_lines(section.get("lines") if isinstance(section.get("lines"), list) else [], limit=8)
        if not lines:
            body = str(section.get("body") or "").strip()
            lines = [item.strip() for item in body.splitlines() if item.strip()][:8]
        if not lines:
            return f"{title} 暂无可展开正文；建议回到原始工具输出确认该章节是否为空。"
        profile = profile or self._technique_report_profile({})
        return "\n".join(
            [
                f"{title} 是本次判断的直接依据之一。",
                f"可读解读：这一组信息应放回{profile['basis']}中理解，重点看它如何支持{profile['decision_style']}，而不是被当成孤立吉凶字段。",
                "关键线索：" + "；".join(lines[:5]),
            ]
        )

    def _consultation_question(self, question: str) -> str:
        cleaned = str(question or "").strip()
        if not cleaned:
            return "综合命局咨询"
        if any(marker in cleaned for marker in ["这个人", "此人", "本人", "客户", "咨询", "判断", "是否", "适合"]):
            return cleaned
        if ("生成" in cleaned or "输出" in cleaned) and "报告" in cleaned:
            focus = self._focus_text(cleaned)
            if focus == "综合判断、风险提示与后续追问方向":
                return "综合命局咨询"
            return f"{focus}专项咨询"
        return cleaned

    def _focus_text(self, question: str) -> str:
        analysis = self._question_analysis(question)
        domains = analysis.get("focus_domains") if isinstance(analysis.get("focus_domains"), list) else []
        labels = {
            "career": "事业发展与工作选择",
            "wealth": "财务资源与风险管理",
            "relationship": "关系互动与边界",
            "health": "身心节奏与健康注意事项",
            "study": "学习考试与申请推进",
            "relocation": "迁移远行与环境变化",
            "timing": "时间窗口与阶段节奏",
            "decision": "决策取舍与行动优先级",
            "general_reading": "综合判断、风险提示与后续追问方向",
        }
        ordered = [labels[item] for item in domains if item in labels]
        if not ordered:
            ordered = [labels["general_reading"]]
        if analysis.get("needs_timing") and labels["timing"] not in ordered:
            ordered.append(labels["timing"])
        if analysis.get("needs_decision_support") and labels["decision"] not in ordered:
            ordered.append(labels["decision"])
        return "、".join(ordered)

    def _bazi_subject_profile(self, *, input_normalized: dict[str, Any], pillars: dict[str, str], day_master: str) -> str:
        date = input_normalized.get("date") or "未提供"
        time = input_normalized.get("time") or "未提供"
        zone = input_normalized.get("zone") or "未提供"
        lat = input_normalized.get("lat") or input_normalized.get("gpsLat") or "未提供"
        lon = input_normalized.get("lon") or input_normalized.get("gpsLon") or "未提供"
        gender = input_normalized.get("gender")
        gender_text = "男命/阳顺规则输入" if gender is True else "女命/阴逆规则输入" if gender is False else "未指定"
        return "\n".join(
            [
                f"出生资料：{date} {time}，时区 {zone}，经纬度 {lon} / {lat}。",
                f"性别/顺逆输入：{gender_text}。",
                f"四柱结构：{self._format_pillars(pillars) or '未能从导出正文中提取完整四柱'}。",
                f"日主定位：{day_master or '未明'}。后续所有判断都围绕日主如何承接环境、资源、压力与行动节奏展开。",
            ]
        )

    def _bazi_reading_steps(self, question: str) -> list[str]:
        steps = [
            "先核对起盘：公历时间、时区、经纬度、真太阳时、性别/顺逆和四柱是否一致。",
            "再定日主：以日柱天干为中心，观察月令环境、四柱结构、五行流动和十神压力。",
            "再看阶段：结合大运、流年和当前问题，把静态命局推进到具体时间窗口。",
            "最后落现实：分别给出事业、财务、关系、风险边界和后续追问方向。",
        ]
        if question != "综合命局咨询":
            steps[3] = "最后针对用户问题给结论：先回答能不能/要不要/怎么做，再说明风险边界和需要补充的行运材料。"
        return steps

    def _bazi_targeted_reading(
        self,
        *,
        question: str,
        day_master: str,
        counts: dict[str, int],
        decision_hint: str,
    ) -> str:
        focus = self._focus_text(question)
        analysis = self._question_analysis(question)
        lines = [
            f"本次问题聚焦：{focus}。",
            f"直接判断：{decision_hint}",
            f"命局阅读中心为{day_master or '日主'}；判断时要先看这个人如何处理自我驱动力、规则压力、资源分配和实际执行。",
        ]
        if "career" in analysis.get("focus_domains", []) or "事业" in focus:
            lines.append("事业层面：更适合看长期积累、专业输出、组织规则与执行节奏是否匹配；若环境只给短期刺激但不给稳定资源，消耗会变大。")
        if "wealth" in analysis.get("focus_domains", []) or "财务" in focus:
            lines.append("财务层面：重点不是一时收益，而是现金流、储备、风险上限和资源调度；适合做可追踪预算与阶段性复盘。")
        if "relationship" in analysis.get("focus_domains", []) or "关系" in focus:
            lines.append("关系层面：要注意边界、责任分配和沟通节奏；压力大时容易把外部事务带入关系，需要提前拆分问题。")
        if analysis.get("needs_timing"):
            lines.append("时间层面：当前命局报告只给结构判断；若要具体到年份、月份或转折点，需要叠加大运、流年或对应推运技法。")
        if analysis.get("needs_decision_support"):
            lines.append("决策层面：优先选择能长期累积能力、资源与信用的路径；对高杠杆、高消耗、边界不清的选项应提高门槛。")
        if len(lines) == 2:
            lines.append("综合层面：这张盘更适合从长期稳定、资源管理和行动节奏来规划，而不是用单一吉凶标签判断。")
        return "\n".join(lines)

    def _bazi_decision_hint(self, *, question: str, day_master: str, counts: dict[str, int]) -> str:
        analysis = self._question_analysis(question)
        focus_domains = set(analysis.get("focus_domains") if isinstance(analysis.get("focus_domains"), list) else [])
        parts: list[str] = []
        if "career" in focus_domains or any(word in question for word in ["工作", "事业", "跳槽", "换工作", "职业"]):
            parts.append("换工作可以进入准备和筛选阶段，但不宜为了短期刺激仓促裸辞；更适合选择能长期积累专业、信用和资源的岗位")
        if "wealth" in focus_domains or any(word in question for word in ["财务", "投资", "钱", "收益", "风险"]):
            parts.append("财务上不建议高杠杆或激进投资；更适合把现金流、储备、止损线和复盘机制先建立起来")
        if analysis.get("needs_timing") or any(word in question for word in ["未来三年", "几年", "时间", "什么时候"]):
            parts.append("未来三年应按“先稳住资源与能力，再择机推进”的节奏处理，具体月份和年份需要再叠加大运流年")
        if analysis.get("needs_decision_support") or any(word in question for word in ["是否", "适合", "应该", "选择"]):
            parts.append("决策上优先选下行风险可控、边界清晰、可持续累积的方案")
        if not parts:
            parts.append(f"以{day_master or '日主'}为核心，先看长期稳定性、资源调度和执行节奏，再判断具体行动")
        return "；".join(parts) + "。"

    def _extract_bazi_pillars(self, export_text: str) -> dict[str, str]:
        stems = "甲乙丙丁戊己庚辛壬癸"
        branches = "子丑寅卯辰巳午未申酉戌亥"
        result: dict[str, str] = {}
        for label in ["年柱", "月柱", "日柱", "时柱", "胎元", "命宫", "身宫"]:
            match = re.search(rf"{label}\s*[：:]\s*([{stems}][{branches}])", export_text)
            if match:
                result[label] = match.group(1)
        return result

    def _day_master_text(self, day_pillar: str | None) -> str:
        if not day_pillar:
            return ""
        stem = day_pillar[0]
        element = {
            "甲": "阳木",
            "乙": "阴木",
            "丙": "阳火",
            "丁": "阴火",
            "戊": "阳土",
            "己": "阴土",
            "庚": "阳金",
            "辛": "阴金",
            "壬": "阳水",
            "癸": "阴水",
        }.get(stem, stem)
        return f"{stem}（{element}）"

    def _bazi_element_counts(self, pillars: dict[str, str]) -> dict[str, int]:
        element_map = {
            "甲": "木",
            "乙": "木",
            "丙": "火",
            "丁": "火",
            "戊": "土",
            "己": "土",
            "庚": "金",
            "辛": "金",
            "壬": "水",
            "癸": "水",
            "子": "水",
            "丑": "土",
            "寅": "木",
            "卯": "木",
            "辰": "土",
            "巳": "火",
            "午": "火",
            "未": "土",
            "申": "金",
            "酉": "金",
            "戌": "土",
            "亥": "水",
        }
        counts = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
        for label in ["年柱", "月柱", "日柱", "时柱"]:
            for char in pillars.get(label, ""):
                element = element_map.get(char)
                if element:
                    counts[element] += 1
        return counts

    def _format_pillars(self, pillars: dict[str, str]) -> str:
        labels = ["年柱", "月柱", "日柱", "时柱"]
        return "，".join(f"{label}{pillars[label]}" for label in labels if pillars.get(label))

    def _section_by_title(self, sections: list[dict[str, Any]], needle: str) -> dict[str, Any] | None:
        for section in sections:
            if needle in str(section.get("title") or ""):
                return section
        return None

    def _bazi_starting_context(self, start_info: dict[str, Any] | None, input_normalized: dict[str, Any]) -> str:
        lines = self._clean_lines(start_info.get("lines", []) if start_info else [], limit=10)
        if not lines and input_normalized:
            lines = [f"{key}: {value}" for key, value in input_normalized.items()]
        return "\n".join(
            [
                "起盘信息决定后面所有判断的边界。本报告已保留公历时间、时区、经纬度、真太阳时和农历信息，适合后续复核。",
                "如果出生时间或地点存在误差，优先复查时辰；八字中时柱对后半生议题、子女/晚年/执行方式等解释影响较大。",
                "本次关键起盘线索：" + ("；".join(lines[:6]) if lines else "未读取到详细起盘线索。"),
            ]
        )

    def _bazi_day_master_reading(self, pillars: dict[str, str], day_master: str, counts: dict[str, int]) -> str:
        month = pillars.get("月柱", "")
        day = pillars.get("日柱", "")
        hour = pillars.get("时柱", "")
        return "\n".join(
            [
                f"日柱为{day or '未明'}，日主{day_master or '未明'}是整张盘的阅读中心。",
                f"月柱{month or '未明'}代表出生季节与外部环境，决定日主面对的压力、资源与规则感；时柱{hour or '未明'}则更偏向执行方式、后续发展和落地能力。",
                "从四柱结构看，判断重点不是单独说某一柱吉凶，而是观察日主如何在环境、资源、约束和行动之间取得平衡。",
                "如果后续加入大运流年，可以进一步判断哪些年份会放大资源、压力、财务或关系议题。",
            ]
        )

    def _bazi_element_reading(self, counts: dict[str, int]) -> str:
        if not counts:
            return "五行信息不足，建议回到原始八字输出补齐四柱与藏干后再判断。"
        sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        strongest = "、".join(name for name, count in sorted_counts if count == sorted_counts[0][1])
        weakest_count = sorted_counts[-1][1]
        weakest = "、".join(name for name, count in sorted_counts if count == weakest_count)
        return "\n".join(
            [
                "五行不是简单的多就好、少就坏，而是看它们是否形成可用的流动。",
                "明面干支计数：" + "，".join(f"{name}{count}" for name, count in counts.items()) + "。",
                f"相对突出的元素是{strongest}，通常表示这类主题更容易被感知、被动员，或在现实中更常成为主线。",
                f"相对需要留意的是{weakest}，它可能表现为需要后天补足的能力、节奏或外部支持。",
                "完整旺衰还要看月令、藏干、通根、合冲刑害与大运流年；本段先作为最终报告的阅读地图。",
            ]
        )

    def _bazi_liunian_reading(self, direction_info: dict[str, Any] | None, *, question: str) -> str:
        lines = self._section_lines(direction_info, limit=18)
        if not lines or lines == ["无"]:
            return "\n".join(
                [
                    "当前八字导出没有提供可展开的大运/流年明细，因此本段只做方法说明，不强行编造年份判断。",
                    "如果问题涉及未来几年、换工作、投资、婚恋或迁移，建议重新调用带大运流年输出的八字工具，或补充流年/大运表后再生成专项报告。",
                    "在没有流年明细时，本报告只把命局结构作为长期倾向，具体年份与月份应保持开放。",
                ]
            )
        current = []
        upcoming = []
        for line in lines:
            if any(token in line for token in ["2026", "2027", "2028", "2029", "2030", "未来", "流年"]):
                upcoming.append(line)
            else:
                current.append(line)
        parts = [
            "大运与流年用于把静态命局推进到阶段判断：同一张命盘，在不同运限里会呈现不同的压力、机会和触发点。",
            "本次可读取的行运线索：" + "；".join(lines[:8]) + "。",
        ]
        if upcoming:
            parts.append("与未来阶段直接相关的线索：" + "；".join(upcoming[:8]) + "。这些年份更适合拿来细看事业节奏、财务风险和行动窗口。")
        if current:
            parts.append("背景运限线索：" + "；".join(current[:5]) + "。它们用于理解这个人长期面对的环境主题和资源调度方式。")
        if any(word in question for word in ["事业", "工作", "职业", "换工作", "跳槽"]):
            parts.append("事业判断上，流年不宜只看“有机会”或“有压力”，要看机会是否能沉淀为职位、能力、信用和可持续资源。")
        if any(word in question for word in ["财", "投资", "钱", "风险", "收益"]):
            parts.append("财务判断上，遇到流年触发时要先看现金流、储备和止损线；高杠杆或高波动选择需要更严格的现实验证。")
        if any(word in question for word in ["未来", "几年", "时间", "什么时候"]):
            parts.append("时间判断上，本段能给阶段顺序；若要精确到月份或事件点，还需要叠加更细的流月、流日或对应技法。")
        return "\n".join(parts)

    def _section_lines(self, section: dict[str, Any] | None, *, limit: int) -> list[str]:
        if not section:
            return []
        lines = section.get("lines")
        if isinstance(lines, list) and lines:
            return self._clean_lines(lines, limit=limit)
        body = str(section.get("body") or "").strip()
        if not body:
            return []
        return self._clean_lines(body.splitlines(), limit=limit)

    def _bazi_shensha_reading(self, gods_info: dict[str, Any] | None) -> str:
        lines = self._clean_lines(gods_info.get("lines", []) if gods_info else [], limit=16)
        if not lines:
            return "神煞章节为空；本报告不强行扩展不存在的材料。"
        helpful = [line for line in lines if any(word in line for word in ["天德", "天乙", "贵人", "国印", "词馆", "禄"])]
        pressure = [line for line in lines if any(word in line for word in ["岁破", "月破", "大耗", "血", "吊客", "五鬼", "官符", "丧门"])]
        parts = [
            "神煞适合用作提示，不适合单独当成绝对吉凶。本报告把它们翻译成“可观察倾向”。",
        ]
        if helpful:
            parts.append("支持性线索：" + "；".join(helpful[:5]) + "。这些更适合理解为学习、贵人、资质、制度资源或被看见的机会。")
        if pressure:
            parts.append("压力性线索：" + "；".join(pressure[:6]) + "。这些更适合提醒风险管理、情绪消耗、规则冲突或突发成本。")
        parts.append("实际使用时，应把神煞放回四柱和行运中验证，避免只凭名字下结论。")
        return "\n".join(parts)

    def _bazi_life_advice(self, day_master: str, counts: dict[str, int]) -> str:
        return "\n".join(
            [
                f"事业上，{day_master or '日主'}更需要找到能长期积累、能稳定输出的环境；不要只追求短期刺激，要看资源、规则和执行节奏是否匹配。",
                "关系上，建议把边界、沟通节奏和现实责任说清楚；如果盘面压力元素被触发，容易把外部压力带入亲密关系或合作关系。",
                "财务上，适合建立可追踪的预算、储备与风险上限；命盘提示可用来观察资源流动，但投资决策仍要回到事实、现金流和风险控制。",
                "身心节奏上，避免长期把自己放在高压和高消耗环境里；越是需要承担责任，越要保留恢复、学习和调整的空间。",
            ]
        )

    def _clean_lines(self, lines: list[Any], *, limit: int) -> list[str]:
        output: list[str] = []
        for line in lines:
            text = str(line or "").strip()
            if not text:
                continue
            output.append(text)
            if len(output) >= limit:
                break
        return output

    def _evidence_from_sections(self, sections: list[dict[str, Any]], *, limit: int) -> list[str]:
        evidence: list[str] = []
        for section in sections:
            title = str(section.get("title") or "导出章节")
            lines = self._clean_lines(section.get("lines") if isinstance(section.get("lines"), list) else [], limit=3)
            if not lines:
                body = str(section.get("body") or "").strip()
                lines = [item.strip() for item in body.splitlines() if item.strip()][:3]
            for line in lines:
                evidence.append(f"{title}: {line}")
                if len(evidence) >= limit:
                    return evidence
        return evidence

    def _provenance(self, *, export_snapshot: Any, export_format: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
        snapshot_provenance = export_snapshot.get("provenance") if isinstance(export_snapshot, dict) else {}
        format_provenance = export_format.get("provenance") if isinstance(export_format, dict) else {}
        snapshot_bundle = export_snapshot.get("bundle_version") if isinstance(export_snapshot, dict) else None
        snapshot_citation = export_snapshot.get("citation") if isinstance(export_snapshot, dict) else None
        return {
            "source_domain": (snapshot_provenance or {}).get("source_domain") or (format_provenance or {}).get("source_domain"),
            "bundle_version": export_format.get("bundle_version") or snapshot_bundle,
            "citation": export_format.get("citation") or snapshot_citation,
            "technique": source.get("technique"),
            "artifact_path": source.get("artifact_path"),
            "trace_id": source.get("trace_id"),
            "group_id": source.get("group_id"),
        }

    def _export_text(self, *, export_snapshot: dict[str, Any], export_format: dict[str, Any]) -> str:
        return str(export_snapshot.get("export_text") or export_format.get("snapshot_text") or "")

    def _coverage_contract(self, *, export_sections: list[dict[str, Any]], export_text: str, source: dict[str, Any]) -> dict[str, Any]:
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

    def _format_coverage(self, coverage: dict[str, Any]) -> str:
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

    def _format_report_metadata(
        self,
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

    def _user_question(self, run: dict[str, Any]) -> str:
        return str(run.get("user_question") or run.get("query_text") or "").strip()

    def _question_analysis(self, user_question: str) -> dict[str, Any]:
        question = user_question.strip()
        focus_catalog = {
            "relationship": ["感情", "关系", "婚姻", "伴侣", "复合", "桃花"],
            "career": ["事业", "工作", "职业", "升职", "项目", "合作"],
            "wealth": ["财", "钱", "收入", "投资", "生意", "盈利"],
            "timing": ["什么时候", "何时", "多久", "时间", "时间窗口", "阶段", "节点", "月份", "年份", "未来", "接下来"],
            "decision": ["是否", "能不能", "要不要", "可不可以", "适不适合", "选择", "决策", "建议", "行动", "取舍"],
            "health": ["健康", "身体", "疾病", "恢复"],
            "study": ["考试", "学习", "论文", "学校", "申请"],
            "relocation": ["搬家", "迁移", "出国", "旅行", "远行"],
        }
        matched_focus = [
            domain
            for domain, keywords in focus_catalog.items()
            if any(keyword in question for keyword in keywords)
        ]
        return {
            "schema": "horosa.skill.report.question_analysis.v1",
            "raw_question": question,
            "has_question": bool(question),
            "focus_domains": matched_focus or (["general_reading"] if question else []),
            "primary_focus": (matched_focus or (["general_reading"] if question else []))[0] if question else None,
            "keywords_detected": [
                keyword
                for keywords in focus_catalog.values()
                for keyword in keywords
                if keyword in question
            ],
            "needs_prediction": any(keyword in question for keyword in ["未来", "接下来", "走势", "会不会", "能否", "是否"]),
            "needs_timing": any(keyword in question for keyword in ["什么时候", "何时", "多久", "时间", "时间窗口", "阶段", "节点", "月份", "年份"]),
            "needs_decision_support": any(keyword in question for keyword in ["是否", "能不能", "要不要", "适不适合", "选择", "决策", "建议", "行动", "取舍"]),
            "recommended_response_style": "answer_first_then_evidence",
        }

    def _targeted_analysis_contract(
        self,
        *,
        user_question: str,
        question_analysis: dict[str, Any],
        coverage: dict[str, Any],
    ) -> dict[str, Any]:
        targeted_requirements = self._targeted_answer_requirements(question_analysis)
        return {
            "schema": "horosa.skill.report.targeted_analysis.v1",
            "user_question": user_question,
            "question_analysis": question_analysis,
            "answer_priority": "directly_answer_user_question_first",
            "answer_plan": [
                "先用 direct_answer 用一句话回答用户核心问题。",
                "再用 executive_summary 给出 3-5 条总览结论。",
                "逐项解释 must_explain_sections 中的所有星阙导出章节。",
                "每个关键判断都绑定 source_section_title、source_line、字段名或原始导出线索。",
                "最后给出 recommendations、limitations 和必要的 follow_up_questions。",
            ],
            "targeted_answer_requirements": targeted_requirements,
            "required_ai_fields": [
                "analysis_focus",
                "question_analysis",
                "answer_plan",
                "direct_answer",
                "executive_summary",
                "analysis_sections",
                "recommendations",
                "limitations",
                "evidence",
            ],
            "section_policy": "Each analysis section should map to a source export section when possible.",
            "evidence_policy": "Every important conclusion should cite a source_section_title, source_line, field name, or original export clue.",
            "memory_policy": "The final report artifact is stored in Horosa memory and can be retrieved later for comparison or experience improvement.",
            "dependency_hallucination_policy": "Never claim that Horosa Skill requires MongoDB, port 7897, Xingque Desktop, or an external database for Liureng/Qimen/Sanshi output. If a field is missing, report it as a local tool/result issue with the run context.",
            "must_explain_sections": coverage.get("must_explain_sections", []),
        }

    def _targeted_answer_requirements(self, question_analysis: dict[str, Any]) -> list[dict[str, Any]]:
        focus_domains = question_analysis.get("focus_domains") if isinstance(question_analysis.get("focus_domains"), list) else []
        requirements: list[dict[str, Any]] = [
            {
                "id": "direct_answer",
                "label": "直接回答",
                "instruction": "先给出一句明确结论，避免只复述盘面。",
                "required": True,
            },
            {
                "id": "evidence_linking",
                "label": "证据绑定",
                "instruction": "每个关键判断都要绑定导出章节、字段或原文线索。",
                "required": True,
            },
        ]
        focus_instructions = {
            "career": ("事业/工作", "必须说明事业、工作、项目或合作层面的具体含义。"),
            "wealth": ("财务/收益", "必须说明收入、投资、生意或资源流动层面的具体含义。"),
            "relationship": ("关系/感情", "必须说明关系状态、互动模式或感情决策层面的具体含义。"),
            "health": ("健康/身体", "必须只做趋势与注意事项提示，并保留非医疗诊断限制。"),
            "study": ("学习/考试", "必须说明学习、考试、申请或研究推进层面的具体含义。"),
            "relocation": ("迁移/远行", "必须说明出行、搬迁、远方事务或环境变化层面的具体含义。"),
        }
        for domain, (label, instruction) in focus_instructions.items():
            if domain in focus_domains:
                requirements.append({"id": f"focus_{domain}", "label": label, "instruction": instruction, "required": True})
        if question_analysis.get("needs_timing"):
            requirements.append(
                {
                    "id": "timing_window",
                    "label": "时间窗口",
                    "instruction": "必须给出时间窗口、阶段顺序或明确说明无法从当前材料判断时间。",
                    "required": True,
                }
            )
        if question_analysis.get("needs_decision_support"):
            requirements.append(
                {
                    "id": "decision_support",
                    "label": "决策建议",
                    "instruction": "必须给出可执行选项、风险点和建议优先级。",
                    "required": True,
                }
            )
        if not focus_domains or focus_domains == ["general_reading"]:
            requirements.append(
                {
                    "id": "general_synthesis",
                    "label": "综合解盘",
                    "instruction": "按盘面重点提炼核心主题、机会、风险和下一步可追问方向。",
                    "required": True,
                }
            )
        return requirements

    def _format_targeting(self, contract: dict[str, Any]) -> str:
        question_analysis = contract.get("question_analysis") if isinstance(contract.get("question_analysis"), dict) else {}
        focus_domains = question_analysis.get("focus_domains") if isinstance(question_analysis.get("focus_domains"), list) else []
        targeted_requirements = contract.get("targeted_answer_requirements") if isinstance(contract.get("targeted_answer_requirements"), list) else []
        return "\n".join(
            [
                f"- 用户问题：{contract.get('user_question') or '无'}",
                f"- 问题焦点：{'、'.join(str(item) for item in focus_domains) if focus_domains else '未指定'}",
                f"- 需要时间判断：{question_analysis.get('needs_timing')}",
                f"- 需要决策建议：{question_analysis.get('needs_decision_support')}",
                f"- 回答优先级：{contract.get('answer_priority')}",
                f"- 章节策略：{contract.get('section_policy')}",
                f"- 证据策略：{contract.get('evidence_policy')}",
                f"- 存储策略：{contract.get('memory_policy')}",
                "- 定向要求：" + ("；".join(str(item.get("label") or item.get("id")) for item in targeted_requirements if isinstance(item, dict)) if targeted_requirements else "无"),
            ]
        )

    def _report_quality(
        self,
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

    def _format_report_quality(self, quality: dict[str, Any]) -> str:
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

    def _delivery_checklist(
        self,
        *,
        sections: list[dict[str, Any]],
        coverage: dict[str, Any],
        coverage_matrix: dict[str, Any],
        report_quality: dict[str, Any],
        question_analysis: dict[str, Any],
        targeted_contract: dict[str, Any],
        ai_report: dict[str, Any],
        provenance: dict[str, Any],
        content_outline: list[dict[str, Any]],
        plain_text: str,
        search_index: dict[str, Any],
    ) -> dict[str, Any]:
        section_ids = {
            str(section.get("id"))
            for section in sections
            if isinstance(section, dict) and section.get("id")
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
            "has_content_outline": bool(content_outline),
            "has_plain_text": bool(plain_text.strip()),
            "has_search_index": bool(search_index.get("keywords")) and bool(search_index.get("search_text")),
            "source_quality_ready": (not source_requires_sections) or report_quality.get("source_complete") is True,
            "ai_quality_ready": report_quality.get("ai_analysis_complete") is True
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
        missing = [
            name
            for name, ok in checks.items()
            if not ok and (source_requires_sections or name not in optional_when_no_source_sections)
        ]
        return {
            "schema": "horosa.skill.report.delivery_checklist.v1",
            "all_required_blocks_present": required_section_ids.issubset(section_ids),
            "ready_to_deliver": not missing,
            "source_requires_sections": source_requires_sections,
            "checks": checks,
            "missing": missing,
            "completion_hint": (
                "报告已包含源数据、逐章覆盖、AI 解盘、建议、证据、来源追溯和检索索引，可以交付。"
                if not missing
                else "交付前需要补齐：" + "、".join(missing)
            ),
        }

    def _format_delivery_checklist(self, checklist: dict[str, Any]) -> str:
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

    def _section_coverage_matrix(self, *, export_sections: list[dict[str, Any]], ai_report: dict[str, Any]) -> dict[str, Any]:
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

    def _format_section_coverage_matrix(self, matrix: dict[str, Any]) -> str:
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

    def _content_outline(self, sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "index": index,
                "id": section.get("id"),
                "title": section.get("title"),
                "body_chars": len(str(section.get("body") or "")),
                "has_items": bool(section.get("items")),
            }
            for index, section in enumerate(sections, start=1)
            if isinstance(section, dict)
        ]

    def _plain_text_report(self, *, title: str, generated_at: str, sections: list[dict[str, Any]]) -> str:
        parts = [
            f"# {title}",
            f"生成时间：{generated_at}",
            "",
            "## 目录",
        ]
        for index, section in enumerate(sections, start=1):
            if isinstance(section, dict):
                parts.append(f"{index}. {section.get('title') or section.get('id') or '章节'}")
        for index, section in enumerate(sections, start=1):
            if not isinstance(section, dict):
                continue
            title_text = section.get("title") or section.get("id") or f"章节 {index}"
            body = str(section.get("body") or "无")
            parts.extend(["", f"## {index}. {title_text}", body])
        return "\n".join(parts).strip() + "\n"

    def _search_index(
        self,
        *,
        run: dict[str, Any],
        source: dict[str, Any],
        user_question: str,
        question_analysis: dict[str, Any],
        targeted_contract: dict[str, Any],
        export_sections: list[dict[str, Any]],
        ai_report: dict[str, Any],
        provenance: dict[str, Any],
        plain_text: str,
    ) -> dict[str, Any]:
        section_titles = [str(section.get("title")) for section in export_sections if section.get("title")]
        ai_sections = ai_report.get("analysis_sections") if isinstance(ai_report.get("analysis_sections"), list) else []
        ai_titles = [
            str(section.get("title") or section.get("source_section_title"))
            for section in ai_sections
            if isinstance(section, dict) and (section.get("title") or section.get("source_section_title"))
        ]
        recommendations = [str(item) for item in ai_report.get("recommendations", [])] if isinstance(ai_report.get("recommendations"), list) else []
        evidence = [str(item) for item in ai_report.get("evidence", [])] if isinstance(ai_report.get("evidence"), list) else []
        focus_domains = question_analysis.get("focus_domains") if isinstance(question_analysis.get("focus_domains"), list) else []
        detected_keywords = question_analysis.get("keywords_detected") if isinstance(question_analysis.get("keywords_detected"), list) else []
        targeted_requirements = targeted_contract.get("targeted_answer_requirements") if isinstance(targeted_contract.get("targeted_answer_requirements"), list) else []
        requirement_terms = [
            str(item.get("label") or item.get("id") or item.get("instruction") or "")
            for item in targeted_requirements
            if isinstance(item, dict)
        ]
        key_phrases = self._extract_consultation_key_phrases(
            "\n".join(
                str(item or "")
                for item in [
                    user_question,
                    ai_report.get("analysis_focus"),
                    ai_report.get("direct_answer"),
                    ai_report.get("executive_summary"),
                    ai_report.get("answer_text"),
                    plain_text,
                ]
            )
        )
        keywords = self._dedupe_strings(
            [
                run.get("run_id"),
                source.get("tool_name"),
                source.get("technique"),
                source.get("technique_label"),
                user_question,
                ai_report.get("analysis_focus"),
                ai_report.get("direct_answer"),
                ai_report.get("executive_summary"),
                ai_report.get("answer_text"),
                provenance.get("bundle_version"),
                provenance.get("source_domain"),
                *focus_domains,
                *detected_keywords,
                *key_phrases,
                *requirement_terms,
                *section_titles,
                *ai_titles,
                *recommendations,
                *evidence,
            ]
        )
        return {
            "schema": "horosa.skill.report.search_index.v1",
            "run_id": run.get("run_id"),
            "tool_name": source.get("tool_name"),
            "technique": source.get("technique"),
            "technique_label": source.get("technique_label"),
            "user_question": user_question,
            "focus_domains": focus_domains,
            "section_titles": section_titles,
            "ai_section_titles": ai_titles,
            "recommendations": recommendations,
            "evidence": evidence,
            "keywords": keywords,
            "plain_text_chars": len(plain_text),
            "search_text": "\n".join(keywords + [plain_text]),
        }

    def _extract_consultation_key_phrases(self, text: str) -> list[str]:
        phrase_catalog = [
            "换工作",
            "跳槽",
            "裸辞",
            "高杠杆",
            "激进投资",
            "投资风险",
            "财务风险",
            "事业策略",
            "行动窗口",
            "时间窗口",
            "决策风险",
            "事业走势",
            "感情关系",
            "婚姻关系",
            "复合",
            "桃花",
            "健康风险",
            "考试",
            "搬家",
            "迁移",
            "出国",
            "合作",
            "创业",
            "升职",
            "offer",
        ]
        return [phrase for phrase in phrase_catalog if phrase and phrase in text]

    def _dedupe_strings(self, values: list[Any]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            output.append(text)
        return output

    def _format_question_analysis(self, question_analysis: dict[str, Any]) -> str:
        focus_domains = question_analysis.get("focus_domains") if isinstance(question_analysis.get("focus_domains"), list) else []
        return "\n".join(
            [
                f"- 原始问题：{question_analysis.get('raw_question') or '无'}",
                f"- 有明确问题：{question_analysis.get('has_question')}",
                f"- 关注领域：{'、'.join(str(item) for item in focus_domains) if focus_domains else '无'}",
                f"- 需要趋势判断：{question_analysis.get('needs_prediction')}",
                f"- 需要时间判断：{question_analysis.get('needs_timing')}",
                f"- 需要决策支持：{question_analysis.get('needs_decision_support')}",
                f"- 推荐回答方式：{question_analysis.get('recommended_response_style')}",
            ]
        )

    def _format_ai_report(self, ai_report: dict[str, Any]) -> str:
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

    def _format_recommendations_limitations(self, ai_report: dict[str, Any]) -> str:
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

    def _ai_coverage_status(self, *, coverage: dict[str, Any], ai_report: dict[str, Any]) -> dict[str, Any]:
        required = [str(item) for item in coverage.get("must_explain_sections", []) or []]
        sections = ai_report.get("analysis_sections") if isinstance(ai_report.get("analysis_sections"), list) else []
        missing = [
            title
            for title in required
            if not any(self._analysis_section_matches_source(section, title) for section in sections)
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

    def _format_mapping(self, payload: dict[str, Any]) -> str:
        if not payload:
            return "无"
        return "\n".join(f"- {key}: {value}" for key, value in payload.items())
