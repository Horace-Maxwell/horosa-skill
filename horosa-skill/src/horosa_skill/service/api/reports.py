"""记忆与报告 API（ReportsAPI）：record_ai_answer、query/show_memory、报告模板 / 渲染 / from-tool、技法依据报告。"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from horosa_skill.agent_guidance import build_validation_recovery
from horosa_skill.engine.registry import resolve_tool_name
from horosa_skill.errors import ToolValidationError, bilingual
from horosa_skill.reports import render_report
from horosa_skill.reports.technique_card import build_technique_report
from horosa_skill.schemas.tools import (
    MemoryAnswerInput,
    MemoryQueryInput,
    MemoryShowInput,
    ReportFromToolInput,
    ReportRenderInput,
    ReportTemplateInput,
    TechniqueReportInput,
)
from horosa_skill.service.export import TOOL_EXPORT_TECHNIQUE_MAP
from horosa_skill.textscript import REPORT_LANGUAGE, TRADITIONAL_HK, parse_script
from horosa_skill.textscript.localize import localize_document


class ReportsAPI:
    def record_ai_answer(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.tracer.span(
            workflow_name="memory.answer",
            metadata={"entrypoint": "memory.answer", "payload": payload},
        ) as trace:
            try:
                request = MemoryAnswerInput.model_validate(payload)
            except ValidationError as exc:
                trace["error_code"] = "memory.answer.invalid_payload"
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for memory answer record.",
                    code="memory.answer.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="memory_record_answer", errors=errors),
                    },
                ) from exc

            result = self.store.attach_ai_response(
                run_id=request.run_id,
                user_question=request.user_question,
                ai_answer=request.ai_answer,
                ai_answer_structured=request.ai_answer_structured,
                answer_meta=request.answer_meta,
            )
            result["summary"] = ["已将 AI 回答写回对应 run 记录，并同步更新本地 manifest 与 artifact。"]
            result["trace_id"] = trace["trace_id"]
            result["group_id"] = trace["group_id"]
            trace["run_id"] = request.run_id
            return result

    def query_memory(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.tracer.span(
            workflow_name="memory.query",
            metadata={"entrypoint": "memory.query", "payload": payload},
        ) as trace:
            try:
                request = MemoryQueryInput.model_validate(payload)
            except ValidationError as exc:
                trace["error_code"] = "memory.query.invalid_payload"
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for memory query.",
                    code="memory.query.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="memory_query", errors=errors),
                    },
                ) from exc

            results = self.store.query_runs(
                run_id=request.run_id,
                tool=request.tool,
                entity=request.entity,
                text=request.text,
                artifact_kind=request.artifact_kind,
                after=request.after,
                before=request.before,
                limit=max(1, request.limit),
                offset=max(0, getattr(request, "offset", 0) or 0),
                include_payload=request.include_payload,
            )
            trace["result_count"] = len(results)
            return {
                "ok": True,
                "count": len(results),
                "results": results,
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
                "summary": [f"已检索到 {len(results)} 条本地 run 记录。"],
            }

    def show_memory(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.tracer.span(
            workflow_name="memory.show",
            metadata={"entrypoint": "memory.show", "payload": payload},
        ) as trace:
            try:
                request = MemoryShowInput.model_validate(payload)
            except ValidationError as exc:
                trace["error_code"] = "memory.show.invalid_payload"
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for memory show.",
                    code="memory.show.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="memory_show", errors=errors),
                    },
                ) from exc

            results = self.store.query_runs(
                run_id=request.run_id,
                limit=1,
                include_payload=request.include_payload,
            )
            if not results:
                trace["error_code"] = "memory.run.not_found"
                return {
                    "ok": False,
                    "code": "memory.run.not_found",
                    "message": f"Run not found: {request.run_id}",
                    "details": {},
                    "trace_id": trace["trace_id"],
                    "group_id": trace["group_id"],
                }

            trace["run_id"] = request.run_id
            return {
                "ok": True,
                "result": results[0],
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
                "summary": ["已读取对应 run 的本地完整记录。"],
            }

    def _report_language(self, request: Any) -> str:
        """报告语言：调用方写了就用它，没写跟全局输出文字走（繁体时是 zh-TW / zh-HK，模板据此让 AI 用繁体写）。"""
        if "language" in request.model_fields_set and request.language:
            return str(request.language)
        return REPORT_LANGUAGE[self.settings.output_script]

    def _report_script(self, language: str) -> str:
        """报告落盘用的文字：zh-TW / zh-HK / zh-CN 这类语言标签直接决定；其它语言（如 en）跟全局设置。"""
        script = parse_script(language) if str(language).strip() else None
        if script is None and str(language).strip().lower() in {"zh-mo", "zh-hant-mo"}:
            script = TRADITIONAL_HK
        return script or self.settings.output_script

    def report_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.tracer.span(
            workflow_name="report.template",
            metadata={"entrypoint": "report.template", "payload": payload},
        ) as trace:
            try:
                request = ReportTemplateInput.model_validate(payload)
                run, source_artifact = self._load_report_source(request.run_id, request.tool_name)
            except ValidationError as exc:
                trace["error_code"] = "report.template.invalid_payload"
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for report template.",
                    code="report.template.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="report_template", errors=errors),
                    },
                ) from exc
            template = self.report_builder.build_template(
                run=run,
                source_artifact=source_artifact,
                language=self._report_language(request),
            )
            template["trace_id"] = trace["trace_id"]
            template["group_id"] = trace["group_id"]
            trace["run_id"] = request.run_id
            trace["tool_name"] = template.get("tool_name")
            return template

    def _report_output_roots(self) -> list[Path]:
        """报告可写的根：输出目录 + `HOROSA_REPORT_OUTPUT_ROOTS`（os.pathsep 分隔）白名单。"""
        roots: list[Path] = []
        if self.settings.output_dir is not None:
            roots.append(Path(self.settings.output_dir).expanduser().resolve())
        for extra in self.settings.report_output_roots:
            roots.append(Path(extra).expanduser().resolve())
        return roots

    def _report_output_path(self, requested: str | None, *, default: Path) -> Path:
        """报告类工具的 `output_path` 闸（v0.40.0 P0）：MCP 工具可被提示注入调用，此前 `Path(output_path).resolve()` 后
        直接 `os.replace` —— 一次被注入的调用就能覆盖用户任意文件。现在：缺省 → 存储层的缺省产物路径；给了 →
        相对路径按输出目录解析，绝对路径必须落在输出目录或 `HOROSA_REPORT_OUTPUT_ROOTS` 白名单根之内，否则
        `report.output_path_not_allowed`（不写任何文件）。"""
        if requested is None or f"{requested}".strip() == "":
            return default
        roots = self._report_output_roots()
        candidate = Path(f"{requested}".strip()).expanduser()
        if not candidate.is_absolute():
            base = roots[0] if roots else Path(default).parent
            candidate = base / candidate
        resolved = candidate.resolve()
        if not any(resolved == root or root in resolved.parents for root in roots):
            raise ToolValidationError(
                bilingual(
                    f"output_path 只能落在报告输出目录内（{'、'.join(str(r) for r in roots) or '（未配置）'}）；"
                    f"给的是 {resolved}。用相对路径，或把目标目录加进 HOROSA_REPORT_OUTPUT_ROOTS。",
                    f"output_path must stay inside the report output directory ({', '.join(str(r) for r in roots) or 'none configured'}); "
                    f"got {resolved}. Use a relative path, or add the directory to HOROSA_REPORT_OUTPUT_ROOTS.",
                ),
                code="report.output_path_not_allowed",
                details={"requested": f"{requested}", "resolved": str(resolved), "allowed_roots": [str(r) for r in roots]},
            )
        return resolved

    def report_render(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.tracer.span(
            workflow_name="report.render",
            metadata={"entrypoint": "report.render", "payload": payload},
        ) as trace:
            try:
                request = ReportRenderInput.model_validate(payload)
                normalized_format = self._normalize_report_format(request.format)
                run, source_artifact = self._load_report_source(request.run_id, request.tool_name)
                source_tool_name = str(source_artifact.get("tool_name") or request.tool_name or "")
                normalized_ai_report = self._normalize_report_ai_payload(
                    ai_report=request.ai_report,
                    ai_answer_text=request.ai_answer_text,
                )
                if not normalized_ai_report and not self._run_has_report_ai(run):
                    template = self.report_builder.build_template(
                        run=run,
                        source_artifact=source_artifact,
                        language=self._report_language(request),
                    )
                    trace["run_id"] = request.run_id
                    trace["tool_name"] = source_tool_name
                    trace["success"] = True
                    return self._report_ai_required_response(
                        run_id=request.run_id,
                        tool_name=source_tool_name,
                        format_name=normalized_format,
                        template=template,
                        tool_result=None,
                        trace_id=trace["trace_id"],
                        group_id=trace["group_id"],
                    )
                answer_writeback = self._record_report_ai_if_present(
                    run=run,
                    tool_name=source_tool_name,
                    ai_report=normalized_ai_report,
                    format_name=normalized_format,
                )
                if answer_writeback:
                    run, source_artifact = self._load_report_source(request.run_id, request.tool_name)
                language = self._report_language(request)
                script = self._report_script(language)
                document = self.report_builder.build_document(
                    run=run,
                    source_artifact=source_artifact,
                    language=language,
                    title=request.title,
                    ai_report=normalized_ai_report,
                    include_raw_json=request.include_raw_json,
                )
                tool_name = str(document["source"]["tool_name"])
                output_path = self._report_output_path(
                    request.output_path,
                    default=self.store.default_report_path(
                        run_id=request.run_id,
                        tool_name=tool_name,
                        format_name=normalized_format,
                    ),
                )
                # 报告是给人读的整份文本：存档里仍是简体原文，只有落盘的这一份按设置转文字。
                document = localize_document(document, script)
                rendered = render_report(document, output_path=output_path, format_name=normalized_format, script=script)
                artifact = self.store.record_report_artifact(
                    run_id=request.run_id,
                    tool_name=tool_name,
                    format_name=normalized_format,
                    path=Path(rendered["path"]),
                    trace_id=trace["trace_id"],
                    group_id=trace["group_id"],
                )
            except ValidationError as exc:
                trace["error_code"] = "report.render.invalid_payload"
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for report render.",
                    code="report.render.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="report_render", errors=errors),
                    },
                ) from exc
            except ValueError as exc:
                trace["error_code"] = "report.render.failed"
                raise ToolValidationError(
                    str(exc),
                    code="report.render.failed",
                    details={"payload": payload},
                ) from exc

            result = {
                **artifact,
                "document_schema": document["schema"],
                "title": document["title"],
                "source": document["source"],
                "answer_writeback": answer_writeback,
                "summary": [f"已生成 {normalized_format.upper()} 结构化报告：{artifact['artifact_path']}"],
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
            }
            trace["run_id"] = request.run_id
            trace["artifact_path"] = artifact["artifact_path"]
            trace["success"] = True
            return result

    def report_from_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.tracer.span(
            workflow_name="report.from_tool",
            metadata={"entrypoint": "report.from_tool", "payload": payload},
        ) as trace:
            try:
                request = ReportFromToolInput.model_validate(payload)
                normalized_format = self._normalize_report_format(request.format)
            except ValidationError as exc:
                trace["error_code"] = "report.from_tool.invalid_payload"
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for report from tool.",
                    code="report.from_tool.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="report_from_tool", errors=errors),
                    },
                ) from exc

            # 两种写法都收（chart / horosa_astro_chart）；后面按注册表键取存档与模板，所以先归一。
            request.tool_name = resolve_tool_name(request.tool_name) or request.tool_name
            result = self.run_tool(
                request.tool_name,
                request.payload,
                save_result=True,
                query_text=request.question,
                group_id=trace["group_id"],
            )
            if not result.memory_ref:
                raise ToolValidationError(
                    "Tool result was not saved and cannot be rendered as a report.",
                    code="report.from_tool.unsaved_result",
                    details={"tool_name": request.tool_name},
                )
            normalized_ai_report = self._normalize_report_ai_payload(
                ai_report=request.ai_report,
                ai_answer_text=request.ai_answer_text,
            )
            if not normalized_ai_report:
                run, source_artifact = self._load_report_source(result.memory_ref.run_id, request.tool_name)
                template = self.report_builder.build_template(
                    run=run,
                    source_artifact=source_artifact,
                    language=self._report_language(request),
                )
                trace["run_id"] = result.memory_ref.run_id
                trace["tool_name"] = request.tool_name
                trace["success"] = True
                return self._report_ai_required_response(
                    run_id=result.memory_ref.run_id,
                    tool_name=request.tool_name,
                    format_name=normalized_format,
                    template=template,
                    tool_result={
                        "ok": result.ok,
                        "tool": result.tool,
                        "input_normalized": result.input_normalized,
                        "summary": result.summary,
                        "memory_ref": result.memory_ref.model_dump(mode="json") if result.memory_ref else None,
                        "trace_id": result.trace_id,
                        "group_id": result.group_id,
                    },
                    trace_id=trace["trace_id"],
                    group_id=trace["group_id"],
                )
            rendered = self.report_render(
                {
                    "run_id": result.memory_ref.run_id,
                    "tool_name": request.tool_name,
                    "format": normalized_format,
                    # 只转发调用方真写了的 language：缺省值转过去会被当成「显式 zh-CN」，盖掉全局的繁体设置。
                    **({"language": request.language} if "language" in request.model_fields_set else {}),
                    "title": request.title,
                    "ai_report": normalized_ai_report,
                    "include_raw_json": request.include_raw_json,
                    "output_path": request.output_path,
                }
            )
            rendered["tool_result"] = {
                "ok": result.ok,
                "tool": result.tool,
                "input_normalized": result.input_normalized,
                "summary": result.summary,
                "memory_ref": result.memory_ref.model_dump(mode="json") if result.memory_ref else None,
                "trace_id": result.trace_id,
                "group_id": result.group_id,
            }
            rendered["summary"] = [
                f"已调用 `{request.tool_name}` 并生成 {normalized_format.upper()} 结构化报告。",
                *rendered.get("summary", []),
            ]
            trace["run_id"] = result.memory_ref.run_id
            trace["artifact_path"] = rendered.get("artifact_path")
            trace["success"] = True
            return rendered

    def _report_ai_required_response(
        self,
        *,
        run_id: str,
        tool_name: str,
        format_name: str,
        template: dict[str, Any],
        tool_result: dict[str, Any] | None,
        trace_id: str,
        group_id: str,
    ) -> dict[str, Any]:
        ai_fillable = template.get("ai_fillable") if isinstance(template.get("ai_fillable"), dict) else {}
        conversation_brief = template.get("conversation_brief") if isinstance(template.get("conversation_brief"), dict) else {}
        return {
            "ok": True,
            "mode": "analysis_required",
            "needs_ai_analysis": True,
            "final_report_generated": False,
            "artifact_path": None,
            "format": format_name,
            "run_id": run_id,
            "tool_name": tool_name,
            "tool_result": tool_result,
            "report_template": template,
            "ai_process": {
                "schema": "horosa.skill.report.ai_process.v1",
                "input": "用户的时间、地点、事情和工具 payload 已保存到本地 run。",
                "conversation_brief": conversation_brief,
                "process": [
                    "读取 conversation_brief，明确用户问题、盘面上下文、解盘方法和输出口吻。",
                    "阅读 report_template.source_context.export_text/export_sections 中的真实起盘结果。",
                    "像在 AI 对话窗口里正式解盘一样，先给结论，再给盘面依据、推理过程、风险边界和建议。",
                    "把完整正文写入 ai_report.answer_text，同时填写 direct_answer、executive_summary、analysis_sections、recommendations、limitations、evidence。",
                    "最后调用 horosa_report_render 或 horosa_report_from_tool，并把 ai_report 一起传入，生成最终 JSON/DOCX/PDF 和 memory。",
                ],
                "output": "最终报告必须来自 AI 对真实盘结果和用户问题的分析；未填写 ai_report 时不会生成假装完成的最终解读报告。",
                "ai_report_skeleton": {
                    "analysis_focus": ai_fillable.get("analysis_focus", ""),
                    "answer_text": ai_fillable.get("answer_text", ""),
                    "direct_answer": ai_fillable.get("direct_answer", ""),
                    "executive_summary": ai_fillable.get("executive_summary", ""),
                    "analysis_sections": ai_fillable.get("analysis_sections", []),
                    "recommendations": ai_fillable.get("recommendations", []),
                    "limitations": ai_fillable.get("limitations", []),
                    "evidence": ai_fillable.get("evidence", []),
                    "follow_up_questions": ai_fillable.get("follow_up_questions", []),
                },
                "next_call": {
                    "tool": "horosa_report_render",
                    "payload": {
                        "run_id": run_id,
                        "tool_name": tool_name,
                        "format": format_name,
                        "ai_report": "<AI fills this object from ai_report_skeleton>",
                    },
                },
            },
            "summary": [
                "已完成起盘和本地保存；尚未生成最终报告，因为缺少 AI 对真实盘结果和用户问题的解读。",
                "请让接入的 AI 按 report_template 填写 ai_report 后，再调用 horosa_report_render 生成 PDF/DOCX/JSON 与 memory。",
            ],
            "trace_id": trace_id,
            "group_id": group_id,
        }

    def _normalize_report_format(self, value: str) -> str:
        normalized = str(value or "").lower().strip()
        if normalized not in {"json", "docx", "pdf"}:
            raise ValueError("format must be one of: json, docx, pdf")
        return normalized

    def _normalize_report_ai_payload(
        self,
        *,
        ai_report: dict[str, Any],
        ai_answer_text: str | None,
    ) -> dict[str, Any]:
        normalized = copy.deepcopy(ai_report) if isinstance(ai_report, dict) else {}
        answer_text = str(ai_answer_text or "").strip()
        if answer_text and not normalized.get("answer_text"):
            normalized["answer_text"] = answer_text
        if answer_text and not normalized.get("direct_answer"):
            normalized["direct_answer"] = self._first_nonempty_line(answer_text)
        return normalized

    def _first_nonempty_line(self, text: str) -> str:
        for line in str(text or "").splitlines():
            stripped = line.strip(" #*-：:")
            if stripped:
                return stripped[:240]
        return str(text or "").strip()[:240]

    def _run_has_report_ai(self, run: dict[str, Any]) -> bool:
        structured = run.get("ai_answer_structured")
        if isinstance(structured, dict) and self._report_ai_answer_text(structured):
            return True
        answer = run.get("ai_answer_text")
        return isinstance(answer, str) and bool(answer.strip())

    def _record_report_ai_if_present(
        self,
        *,
        run: dict[str, Any],
        tool_name: str,
        ai_report: dict[str, Any],
        format_name: str,
    ) -> dict[str, Any] | None:
        if not ai_report:
            return None
        answer_text = self._report_ai_answer_text(ai_report)
        if not answer_text:
            return None
        result = self.store.attach_ai_response(
            run_id=run["run_id"],
            user_question=run.get("user_question") or run.get("query_text"),
            ai_answer=answer_text,
            ai_answer_structured=ai_report,
            answer_meta={
                "source": "report_render",
                "tool_name": tool_name,
                "format": format_name,
                "schema": "horosa.skill.report.answer_writeback.v1",
            },
        )
        return {
            "ok": result["ok"],
            "run_id": result["run_id"],
            "source": "report_render",
            "tool_name": tool_name,
            "format": format_name,
            "answer_text_chars": len(answer_text),
            "manifest_path": result.get("manifest_path"),
        }

    def _report_ai_answer_text(self, ai_report: dict[str, Any]) -> str:
        for key in ("answer_text", "direct_answer", "executive_summary", "summary", "answer"):
            value = ai_report.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        sections = ai_report.get("analysis_sections")
        if isinstance(sections, list):
            for section in sections:
                if isinstance(section, dict):
                    value = section.get("body") or section.get("content")
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                elif isinstance(section, str) and section.strip():
                    return section.strip()
        return ""

    def technique_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        """技法依据报告：把已存运行的技法卡渲染成 markdown / json / docx / pdf。

        与 `report_render` 的分工：那份是 **AI 写正文的咨询报告**（没有 ai_report 就拒绝出终稿）；
        这份是**确定性元数据**——用了什么技法、什么口径、谁算的、段落全不全、版本链——所以随时能出，
        不需要也不接受 AI 正文。两者不混：`references/reports.md` 明令咨询报告正文不带机器元数据。
        """
        with self.tracer.span(
            workflow_name="report.technique",
            metadata={"entrypoint": "report.technique", "payload": payload},
        ) as trace:
            try:
                request = TechniqueReportInput.model_validate(payload)
            except ValidationError as exc:
                trace["error_code"] = "report.technique.invalid_payload"
                errors = exc.errors()
                raise ToolValidationError(
                    "Invalid payload for technique report.",
                    code="report.technique.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="technique_report", errors=errors),
                    },
                ) from exc

            normalized_format = str(request.format or "markdown").lower().strip()
            if normalized_format not in {"markdown", "json", "docx", "pdf"}:
                raise ToolValidationError(
                    "format must be one of: markdown, json, docx, pdf",
                    code="report.technique.invalid_format",
                    details={"format": request.format},
                )

            scope = "group" if request.group_id else "run"
            cards, source_runs = self._collect_technique_cards(
                run_id=request.run_id, group_id=request.group_id
            )
            if not cards:
                raise ToolValidationError(
                    "No stored run carries a technique card yet — run a technique tool first "
                    "(cards are attached to every successful technique call).",
                    code="report.technique.no_cards",
                    details={"run_id": request.run_id, "group_id": request.group_id},
                )
            document = build_technique_report(
                cards=cards,
                scope=scope,
                scope_id=request.group_id or request.run_id or (source_runs[0] if source_runs else None),
                title=request.title,
            )
            if request.include_sections is False:
                for card in document.get("cards", []):
                    (card.get("sections") or {}).pop("titles", None)

            scope_id = document["scope_id"] or "latest"
            suffix = "md" if normalized_format == "markdown" else normalized_format
            base = self.store.default_report_path(run_id=str(scope_id), tool_name="technique", format_name="json")
            output_path = self._report_output_path(request.output_path, default=base.with_suffix(f".{suffix}"))
            script = self.settings.output_script
            document = localize_document(document, script)
            try:
                rendered = render_report(document, output_path=output_path, format_name=normalized_format, script=script)
            except ValueError as exc:
                raise ToolValidationError(
                    str(exc), code="report.technique.render_failed", details={"format": normalized_format}
                ) from exc

            result = {
                "ok": True,
                "schema": document["schema"],
                "scope": scope,
                "scope_id": document["scope_id"],
                "technique_count": document["technique_count"],
                "consistency": document["consistency"],
                "artifact_path": rendered["path"],
                "format": rendered["format"],
                "file_size": rendered.get("file_size"),
                "document": document,
                "summary": [
                    f"已生成技法依据报告（{document['technique_count']} 个技法）：{rendered['path']}",
                    *(
                        []
                        if document["consistency"]["all_clear"]
                        else ["⚠️ 报告含一致性告警，请阅读「一致性检查」一节后再引用结论。"]
                    ),
                ],
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
            }
            trace["artifact_path"] = rendered["path"]
            trace["success"] = True
            return result

    def _collect_technique_cards(
        self, *, run_id: str | None, group_id: str | None
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """取出目标运行的技法卡（按调用先后）。都不给时取最近一次带卡的运行。"""
        if group_id:
            runs = self.store.query_runs(group_id=group_id, include_payload=True, limit=200)
        elif run_id:
            runs = self.store.query_runs(run_id=run_id, include_payload=True, limit=1)
        else:
            runs = self.store.query_runs(include_payload=True, limit=20)
        cards: list[dict[str, Any]] = []
        seen_runs: list[str] = []
        for run in sorted(runs, key=lambda item: str(item.get("created_at") or "")):
            for artifact in run.get("artifacts") or []:
                if artifact.get("kind") != "tool_result":
                    continue
                payload = artifact.get("payload")
                if not isinstance(payload, dict):
                    continue
                card = (payload.get("data") or {}).get("technique_card")
                if isinstance(card, dict):
                    cards.append(card)
                    # query_runs 的键是 `run_id`（不是 `id`）。读错键 + `str(None)` = 报告标题和
                    # 文件名里出现字面 "None" —— f-string None 陷阱的同族（AGENTS §5 步骤 10）：
                    # 先取值判空，别把 None 直接格式化。
                    identifier = run.get("run_id")
                    if isinstance(identifier, str) and identifier and identifier not in seen_runs:
                        seen_runs.append(identifier)
            # 无 group 无 run 时只要最近的一份，多取会把不相干的历史运行混进同一份报告。
            if cards and not group_id and not run_id:
                break
        return cards, seen_runs

    def _load_report_source(self, run_id: str, tool_name: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
        runs = self.store.query_runs(run_id=run_id, tool=tool_name, include_payload=True, limit=1)
        if not runs:
            raise ToolValidationError(
                f"Run not found: {run_id}",
                code="report.run_not_found",
                details={"run_id": run_id, "tool_name": tool_name},
            )
        run = runs[0]
        artifacts = run.get("artifacts") if isinstance(run.get("artifacts"), list) else []
        candidates = [
            artifact
            for artifact in artifacts
            if artifact.get("kind") == "tool_result"
            and isinstance(artifact.get("payload"), dict)
            and (tool_name is None or artifact.get("tool_name") == tool_name)
        ]
        if not candidates and tool_name is None:
            candidates = [
                artifact
                for artifact in artifacts
                if artifact.get("kind") == "dispatch_result"
                and isinstance(artifact.get("payload"), dict)
            ]
        if not candidates:
            raise ToolValidationError(
                "No reportable tool artifact found for this run.",
                code="report.source_not_found",
                details={"run_id": run_id, "tool_name": tool_name},
            )
        def has_complete_export_contract(artifact: dict[str, Any]) -> bool:
            payload = artifact.get("payload")
            data = payload.get("data") if isinstance(payload, dict) else {}
            source_tool = str(artifact.get("tool_name") or "")
            if artifact.get("kind") != "tool_result" or source_tool not in TOOL_EXPORT_TECHNIQUE_MAP:
                return True
            # 只要求 export_snapshot（唯一导出契约）；旧归档带 export_format 双字段的天然满足 → 向后兼容。
            return isinstance(data, dict) and isinstance(data.get("export_snapshot"), dict)

        source = next((artifact for artifact in candidates if has_complete_export_contract(artifact)), candidates[0])
        payload = source.get("payload")
        data = payload.get("data") if isinstance(payload, dict) else {}
        source_tool = str(source.get("tool_name") or "")
        if source.get("kind") == "tool_result" and source_tool in TOOL_EXPORT_TECHNIQUE_MAP and not (
            isinstance(data, dict)
            and isinstance(data.get("export_snapshot"), dict)
        ):
            raise ToolValidationError(
                "Selected artifact does not contain a complete export contract.",
                code="report.export_contract_missing",
                details={
                    "run_id": run_id,
                    "tool_name": source.get("tool_name"),
                    "artifact_count": len(candidates),
                    "source_ok": payload.get("ok") if isinstance(payload, dict) else None,
                    "source_error": payload.get("error") if isinstance(payload, dict) else None,
                },
            )
        return run, source
