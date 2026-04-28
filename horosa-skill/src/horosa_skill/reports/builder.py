from __future__ import annotations

import copy
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
                "请基于 source_context 中的完整输入、工具摘要、星阙导出正文和每个导出章节生成报告。",
                "必须逐项覆盖 coverage_contract.must_explain_sections；如果某章节无法解释，请在 limitations 中说明原因。",
                "不要丢弃 source_context.export_sections 中的原始章节标题；analysis_sections 建议与这些标题一一对应。",
                "必须优先回答 user_question；每个判断都尽量绑定 evidence 或 source_section_title，避免只给泛泛建议。",
            ],
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
        merged_ai_report = self._merge_ai_report(run=run, ai_report=ai_report)
        input_normalized = payload.get("input_normalized") if isinstance(payload, dict) else {}
        summary = payload.get("summary") if isinstance(payload, dict) else []
        export_text = self._export_text(export_snapshot=export_snapshot, export_format=export_format)
        export_sections = self._source_export_sections(export_format, include_body=True)
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
        report_title = title or f"Horosa Skill 结构化报告 · {technique_title}"
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

    def _merge_ai_report(self, *, run: dict[str, Any], ai_report: dict[str, Any] | None) -> dict[str, Any]:
        answer_structured = run.get("ai_answer_structured")
        if isinstance(answer_structured, dict):
            base = copy.deepcopy(answer_structured)
        else:
            base = {}
        if run.get("ai_answer_text") and "answer_text" not in base:
            base["answer_text"] = run.get("ai_answer_text")
        if ai_report:
            base.update(copy.deepcopy(ai_report))
        return {
            "analysis_focus": base.get("analysis_focus") or "",
            "direct_answer": base.get("direct_answer") or base.get("answer") or "",
            "executive_summary": base.get("executive_summary") or base.get("summary") or "",
            "analysis_sections": base.get("analysis_sections") if isinstance(base.get("analysis_sections"), list) else [],
            "recommendations": base.get("recommendations") if isinstance(base.get("recommendations"), list) else [],
            "limitations": base.get("limitations") if isinstance(base.get("limitations"), list) else [],
            "evidence": base.get("evidence") if isinstance(base.get("evidence"), list) else [],
            "follow_up_questions": base.get("follow_up_questions") if isinstance(base.get("follow_up_questions"), list) else [],
            "answer_text": base.get("answer_text") or "",
            "raw": base,
        }

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
        covered_titles: set[str] = set()
        for section in sections:
            if isinstance(section, dict):
                title = str(section.get("source_section_title") or section.get("title") or "")
                if title:
                    covered_titles.add(title)
        missing = [title for title in required if title not in covered_titles]
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
