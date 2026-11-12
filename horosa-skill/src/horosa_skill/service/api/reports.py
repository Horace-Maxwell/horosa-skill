"""记忆与报告 API（ReportsAPI）：record_ai_answer、query/show_memory、报告模板 / 渲染 / from-tool、技法依据报告。"""
from __future__ import annotations

import copy
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from horosa_skill import winpaths
from horosa_skill.agent_guidance import build_validation_recovery
from horosa_skill.engine.registry import resolve_tool_name
from horosa_skill.errors import ToolValidationError, bilingual, validation_errors
from horosa_skill.reports import output_path as output_paths
from horosa_skill.reports import render_report
from horosa_skill.reports.calendar_ics import CALENDAR_TOOLS, extract_calendar, render_ics
from horosa_skill.reports.chart_png import PngFontUnavailable, render_figure_pngs
from horosa_skill.reports.renderers import _labeler, write_artifact
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
from horosa_skill.service import _clock
from horosa_skill.service.export import TOOL_EXPORT_TECHNIQUE_MAP
from horosa_skill.textscript import REPORT_LANGUAGE, TRADITIONAL_HK, parse_script
from horosa_skill.textscript.localize import localize_document

# 查规则库的工具（不起盘）：导出段有标题但内容是「无」，出成「完整排盘报告」只是一份空壳（v0.43 第二轮评审）。
_RULE_LOOKUP_TOOLS = frozenset({"ziwei_rules"})



# 只含引擎数据、不要 AI 解读的两种格式：PNG = 盘图本身，ICS = 结果里现成日期的日历（v0.48.0）。
_ENGINE_ONLY_FORMATS = frozenset({"png", "ics"})
_REPORT_FORMATS = ("json", "docx", "pdf", "png", "ics")
_TECHNIQUE_REPORT_FORMATS = ("markdown", "json", "docx", "pdf")
_FORMAT_NOUNS = {"png": "PNG 盘图", "ics": "ICS 日历"}

_REPORT_MIME = {
    "pdf": "application/pdf",
    "png": "image/png",
    "ics": "text/calendar",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "json": "application/json",
    "md": "text/markdown",
    "markdown": "text/markdown",
    "txt": "text/plain",
}


def _file_card(path: Any, format_name: str | None = None) -> dict[str, Any] | None:
    """报告落盘后的文件卡：绝对路径 + file:// URI + MIME + 字节数 + sha256。

    MCP 层据它给新版客户端附一个 `resource_link` 内容块（不把 PDF 以 base64 塞进结果：claude.ai 单次结果约 15 万字、
    Claude Code 约 25k token）；老客户端照样从这里读路径。"""
    import hashlib

    if not path:
        return None
    target = Path(str(path)).expanduser().resolve()
    if not target.is_file():
        return None
    data = target.read_bytes()
    kind = (format_name or target.suffix.lstrip(".")).lower()
    return {"path": str(target), "uri": target.as_uri(), "name": target.name,
            "mime": _REPORT_MIME.get(kind, "application/octet-stream"),
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

def _run_stamp(run: dict[str, Any]) -> datetime:
    """ICS 的 DTSTAMP：存档里这条 run 的创建时刻（同一条结果重导出，文件逐字节相同）；读不出来才用当前时刻。"""
    try:
        stamp = datetime.fromisoformat(str(run.get("created_at") or ""))
    except ValueError:
        return _clock.now(timezone.utc)
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def _render_outcome_fields(rendered: dict[str, Any]) -> dict[str, Any]:
    """render_report 如实报告的「没按要求写成」：降级成 TXT / 目标被占用另存。此前这里全部丢弃，调用方只看到「已生成 PDF」和一个 .txt 路径。"""
    return {key: rendered[key] for key in ("degraded_from", "degrade_reason", "requested_output_path") if key in rendered}


def _render_outcome_notes(rendered: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if rendered.get("degraded_from"):
        notes.append(f"未能生成 {str(rendered['degraded_from']).upper()}，已退化为纯文本（全文都在）：{rendered.get('degrade_reason')}")
    if rendered.get("requested_output_path"):
        notes.append(f"{rendered['requested_output_path']} 正被别的程序占用（多半开着上一版），新报告另存为 {rendered['path']}；旧文件没动。")
    return notes


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
                errors = validation_errors(exc)
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
                errors = validation_errors(exc)
                raise ToolValidationError(
                    "Invalid payload for memory query.",
                    code="memory.query.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="memory_query", errors=errors),
                    },
                ) from exc

            scan: dict[str, Any] = {}
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
                scan_report=scan,
            )
            trace["result_count"] = len(results)
            not_scanned = int(scan.get("not_scanned") or 0)
            summary = [f"已检索到 {len(results)} 条本地 run 记录。"]
            if not_scanned:
                summary.append(
                    f"另有 {not_scanned} 条较早的记录只按问题与答案检索过，盘面正文没有搜；"
                    "用 after / before / tool / entity 缩小范围后可以搜到。"
                )
            return {
                "ok": True,
                "count": len(results),
                "results": results,
                "not_scanned": not_scanned,
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
                "summary": summary,
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
                errors = validation_errors(exc)
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

    def _report_style(self, request: Any) -> str:
        style = str(getattr(request, "style", "") or "analysis").strip().lower()
        if style not in {"analysis", "chart"}:
            raise ToolValidationError(
                bilingual(f"不认识的报告样式：{style}（可选 analysis / chart）", f"Unknown report style: {style} (analysis / chart)"),
                code="report.invalid_style",
                details={"style": style, "allowed": ["analysis", "chart"]},
            )
        return style

    def _report_language(self, request: Any) -> str:
        """报告语言：调用方写了就用它，没写跟全局输出文字走（繁体时是 zh-TW / zh-HK，模板据此让 AI 用繁体写）。"""
        if request.language:
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
                errors = validation_errors(exc)
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
        `report.output_path_not_allowed`（不写任何文件）。

        Windows 上字符串闸在 `resolve()` **之前**（v0.47.2-dev）：resolve 一个 UNC 路径就会向对方发起 SMB 连接并带上用户的 NTLM 凭据，
        被拒绝之前凭据已经送出去了；NUL / CON、NTFS 备用数据流这类路径则「成功」却看不到文件。见 winpaths.py。"""
        if requested is None or f"{requested}".strip() == "":
            return default
        roots = self._report_output_roots()
        text = f"{requested}".strip()

        def refuse(reason_cn: str, reason_en: str, resolved: str | None = None) -> ToolValidationError:
            return ToolValidationError(
                bilingual(f"output_path 不可用：{reason_cn}（给的是 {text}）。改用输出目录内的普通相对路径。",
                          f"output_path cannot be used: {reason_en} (got {text}). Use a plain relative path inside the output directory."),
                code="report.output_path_not_allowed",
                details={"requested": text, "resolved": resolved, "reason": reason_en, "allowed_roots": [str(r) for r in roots]},
            )

        if os.name == "nt":
            if winpaths.is_network_or_device_path(text) and not winpaths.is_under_network_root(text, [str(r) for r in roots]):
                raise refuse("网络路径 / 设备路径不在白名单内（只有 HOROSA_REPORT_OUTPUT_ROOTS 配过的共享可写）",
                             "network or device path outside the allow-list (only shares configured in HOROSA_REPORT_OUTPUT_ROOTS are writable)")
            problem = winpaths.path_problem(text)
            if problem is not None:
                raise refuse(*problem)
        candidate = Path(text).expanduser()
        if not candidate.is_absolute():
            base = roots[0] if roots else Path(default).parent
            candidate = base / candidate
        try:
            resolved = candidate.resolve()
        except (OSError, ValueError) as exc:  # 路径过长、含 NUL 字节等：不是合法路径，别让裸异常穿出错误信封
            raise refuse(f"不是合法路径（{type(exc).__name__}）", f"not a usable path ({type(exc).__name__})") from exc
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

    def _output_request(self, requested: str | None, format_name: str) -> output_paths.OutputRequest:
        """`output_path` 的事前检查（没有副作用，起盘 / 写回之前就能做）：过输出根的闸，再看它是目录还是文件、扩展名和 format
        对不对得上、名字是否过长、所在位置写不写得进去。问题一律 `report.output_path_not_allowed` / `report.output_path_unusable`。"""
        text = "" if requested is None else f"{requested}".strip()
        if not text:
            return output_paths.OutputRequest("default")
        resolved = self._report_output_path(text, default=Path(self.store.output_dir) / "report")
        output_paths.check_names(resolved, requested=text)  # 先看名字（纯字符串），再碰文件系统
        protected = self._store_areas()
        output_paths.check_not_store_area(resolved, protected=protected, requested=text)
        if output_paths.names_a_directory(text, resolved):
            output_paths.check_writable(resolved / "report", requested=text)
            return output_paths.OutputRequest("directory", resolved, {"requested": text, "reason": "directory"})
        path, adjustment = output_paths.with_format_suffix(resolved, format_name, requested=text)
        output_paths.check_names(path, requested=text)
        output_paths.check_not_store_area(path, protected=protected, requested=text)
        output_paths.check_writable(path, requested=text)
        output_paths.check_replaceable(path, may_replace=self._is_recorded_report, requested=text)
        return output_paths.OutputRequest("file", path, adjustment, requested=text)

    def _store_areas(self) -> list[Path]:
        """报告不能写进去的存储区（output_path.check_not_store_area）：记忆库文件及其 -wal / -shm / -journal、trace、档案、
        自备知识库、runtime。存档目录 `<data>/runs` 本身就是报告输出根，那里的存档与 manifest 靠「已有文件只替换报告」护着。"""
        from horosa_skill.profiles import profiles_dir

        settings = self.settings
        areas: list[Path] = []
        db_path = getattr(self.store, "db_path", None) or settings.db_path
        if db_path is not None:
            db = Path(db_path).expanduser()
            areas += [db, *(db.with_name(db.name + suffix) for suffix in ("-wal", "-shm", "-journal"))]
        for directory in (settings.trace_dir, profiles_dir(settings), settings.user_knowledge_dir, settings.runtime_root):
            if directory is not None:
                areas.append(Path(directory).expanduser())
        resolved: list[Path] = []
        for area in areas:
            try:
                resolved.append(area.resolve())
            except (OSError, ValueError):
                resolved.append(area.absolute())
        return resolved

    def _is_recorded_report(self, path: Path) -> bool:
        """这个文件是不是报告自己写的（记忆库 artifacts 表里有一条 report_* 记着这个路径）。读不了记忆库就当不是。"""
        try:
            with self.store.connect() as conn:
                row = conn.execute(
                    "SELECT 1 FROM artifacts WHERE path = ? AND kind LIKE 'report\\_%' ESCAPE '\\' LIMIT 1", (str(path),)
                ).fetchone()
        except Exception:  # noqa: BLE001 — 记忆库坏了 / 被锁：保守地不替换
            return False
        return row is not None

    def _claim_output(
        self, request: output_paths.OutputRequest, default: Path, count: int = 1
    ) -> tuple[list[Path], list[Path]]:
        """落盘路径（`count` 张图各一个文件）。调用方点名的文件：没有就原子地占住；已有的只替换报告自己写过的。缺省名 /
        目录里的缺省名：整组占住一个没人用的名字（同一秒内两次调用各得各的）。返回（路径, 占位文件）；占位文件由调用方在
        finally 里逐个 `output_paths.release`。"""
        if request.kind == "file" and request.path is not None:
            targets = output_paths.numbered(request.path, count)
            placeholders = output_paths.claim_exact(targets, may_replace=self._is_recorded_report, requested=request.requested)
            return targets, placeholders
        target = default if request.kind == "default" or request.path is None else request.path / default.name
        reserved = output_paths.reserve_set(target, count)
        return reserved, list(reserved)

    @staticmethod
    def _output_adjustment_fields(request: output_paths.OutputRequest, path: Any) -> dict[str, Any]:
        return {"output_path_adjustment": request.adjustment} if request.adjustment else {}

    @staticmethod
    def _output_adjustment_notes(request: output_paths.OutputRequest, path: Any) -> list[str]:
        if not request.adjustment:
            return []
        if request.adjustment["reason"] == "directory":
            return [f"output_path 给的是目录（{request.adjustment['requested']}），报告以缺省文件名写在其中：{path}"]
        return [f"output_path 没有写 {request.adjustment['extension']} 扩展名，已补上：{path}"]

    @staticmethod
    def _write_failed(exc: OSError, path: Any) -> ToolValidationError:
        """写盘时才暴露的问题（磁盘满、目标被占用且旁边没有空名字、事前检查没覆盖到的文件系统限制）：不让裸 OSError 穿出信封。"""
        reason = f"{type(exc).__name__}: {exc.strerror or exc}"
        return output_paths.unusable(
            "write_failed",
            f"报告写不到 {path}（{reason}）。换一个 output_path，或不写 output_path 用缺省位置。",
            f"the report could not be written to {path} ({reason}). Choose another output_path, or omit it to use the default location.",
            path=str(path), errno=exc.errno,
        )

    def report_render(self, payload: dict[str, Any]) -> dict[str, Any]:
        """次序（v0.50.0）：校验参数 → 格式 / 样式 → 取 run → `output_path` 事前检查 → 排文档 → 渲染落盘 → **之后**才把这次的
        AI 解读写回 run。此前写回在路径检查之前：路径被拒，解读却已经记在 run 上，下一次不带答案的调用就把它印成了报告。
        run 取到之后抛出的每个错误都带 `details.run_id`。"""
        with self.tracer.span(
            workflow_name="report.render",
            metadata={"entrypoint": "report.render", "payload": payload},
        ) as trace:
            try:
                request = ReportRenderInput.model_validate(payload)
            except ValidationError as exc:
                trace["error_code"] = "report.render.invalid_payload"
                errors = validation_errors(exc)
                raise ToolValidationError(
                    "Invalid payload for report render.",
                    code="report.render.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="report_render", errors=errors),
                    },
                ) from exc
            reserved: list[Path] = []
            run_loaded = False
            try:
                normalized_format = self._normalize_report_format(request.format)
                engine_only = normalized_format in _ENGINE_ONLY_FORMATS
                chart_style = not engine_only and self._report_style(request) == "chart"
                run, source_artifact = self._load_report_source(request.run_id, request.tool_name)
                run_loaded = True
                output_request = self._output_request(request.output_path, normalized_format)
                if engine_only:
                    result = self._render_engine_only(request, run, source_artifact, normalized_format, trace, output_request)
                    trace["run_id"] = request.run_id
                    trace["artifact_path"] = result["artifact_path"]
                    trace["success"] = True
                    return result
                source_tool_name = str(source_artifact.get("tool_name") or request.tool_name or "")
                normalized_ai_report = self._normalize_report_ai_payload(
                    ai_report=request.ai_report,
                    ai_answer_text=request.ai_answer_text,
                )
                answer_text = self._report_ai_answer_text(normalized_ai_report) if normalized_ai_report else ""
                stored_answer = self._run_has_report_ai(run)
                if not chart_style and not normalized_ai_report and not stored_answer:
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
                answer_source = "request" if answer_text else "stored" if stored_answer else None
                # 文档按「写回之后 run 的样子」来排（写回是整份替换，不是合并），写回本身留到产物落盘之后。
                run_view = run if not answer_text else {
                    **run,
                    "user_question": run.get("user_question") or run.get("query_text"),
                    "ai_answer_text": answer_text,
                    "ai_answer_structured": copy.deepcopy(normalized_ai_report),
                }
                language = self._report_language(request)
                script = self._report_script(language)
                document = self.report_builder.build_document(
                    run=run_view,
                    source_artifact=source_artifact,
                    language=language,
                    title=request.title,
                    ai_report=normalized_ai_report,
                    include_raw_json=request.include_raw_json,
                    style="chart" if chart_style else "analysis",
                )
                tool_name = str(document["source"]["tool_name"])
                if chart_style and (tool_name in _RULE_LOOKUP_TOOLS or not document.get("figures") and not any(
                    section.get("group") == "chart" for section in document.get("sections") or []
                )):
                    # 解析 / 注册表 / 知识检索这类工具没有盘面：此前照样出一份只有封面的「完整排盘报告」。
                    raise ToolValidationError(
                        bilingual(
                            f"`{tool_name}` 没有盘面可排成完整排盘报告（它返回的是解析结果 / 清单 / 知识条目）。"
                            "直接读工具结果，或对起盘类技法出报告。",
                            f"`{tool_name}` has no chart to lay out as a complete chart report (it returns parsed text / "
                            "a registry / knowledge entries). Read the tool result directly, or report on a charting technique.",
                        ),
                        code="report.no_chart_content",
                        details={"tool_name": tool_name, "style": "chart"},
                    )
                # 盘图换成星阙 app 原版画法（reports/app_charts.py）；在转文字之前配，app 图里的字跟正文一起转。
                document["figures"], figure_gaps = self._report_figures(document.get("figures") or [], run, source_artifact)
                if figure_gaps:
                    document["figure_gaps"] = figure_gaps
                # 报告是给人读的整份文本：存档里仍是简体原文，只有落盘的这一份按设置转文字。
                document = localize_document(document, script)
                # 缺省名带上样式：同一条 run 的排盘版与解读版一眼分得开，也不会同一秒内互相盖掉。
                [output_path], reserved = self._claim_output(output_request, self.store.default_report_path(
                    run_id=request.run_id,
                    tool_name=f"{tool_name}_{'chart' if chart_style else 'analysis'}",
                    format_name=normalized_format,
                ))
                try:
                    rendered = render_report(document, output_path=output_path, format_name=normalized_format, script=script)
                except OSError as exc:
                    raise self._write_failed(exc, output_path) from exc
                artifact = self.store.record_report_artifact(
                    run_id=request.run_id,
                    tool_name=tool_name,
                    format_name=rendered["format"],
                    path=Path(rendered["path"]),
                    trace_id=trace["trace_id"],
                    group_id=trace["group_id"],
                )
                # 产物已经在盘上，这时才把这次的解读记到 run 上。
                answer_writeback = self._record_report_ai_if_present(
                    run=run,
                    tool_name=source_tool_name,
                    ai_report=normalized_ai_report,
                    format_name=normalized_format,
                )
            except ToolValidationError as exc:
                if run_loaded:
                    exc.details.setdefault("run_id", request.run_id)
                trace["error_code"] = exc.code
                raise
            except ValueError as exc:
                trace["error_code"] = "report.render.failed"
                raise ToolValidationError(
                    str(exc),
                    code="report.render.failed",
                    details={"payload": payload, **({"run_id": request.run_id} if run_loaded else {})},
                ) from exc
            finally:
                for placeholder in reserved:
                    output_paths.release(placeholder)

            answer_notes = []
            if answer_source == "stored" and (request.ai_answer_text is not None or request.ai_report):
                answer_notes.append("这次传入的 ai_answer_text / ai_report 里没有可用的正文，报告印的是存档里已有的那份解读（answer_source=stored）。")
            result = {
                **artifact,
                "file": _file_card(artifact.get("artifact_path"), rendered["format"]),
                "document_schema": document["schema"],
                "title": document["title"],
                "source": document["source"],
                "answer_source": answer_source,
                "answer_writeback": answer_writeback,
                **_render_outcome_fields(rendered),
                **self._output_adjustment_fields(output_request, rendered["path"]),
                # 缺了哪张盘图、为什么：三种产物（PDF / DOCX / PNG）与失败时的 details 都叫 figure_gaps。
                **({"figure_gaps": list(document["figure_gaps"])} if document.get("figure_gaps") else {}),
                "summary": [f"已生成 {rendered['format'].upper()} 结构化报告：{artifact['artifact_path']}", *_render_outcome_notes(rendered),
                            *self._output_adjustment_notes(output_request, rendered["path"]), *answer_notes,
                            *document.get("figure_gaps", [])],
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
            except ValidationError as exc:
                trace["error_code"] = "report.from_tool.invalid_payload"
                errors = validation_errors(exc)
                raise ToolValidationError(
                    "Invalid payload for report from tool.",
                    code="report.from_tool.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="report_from_tool", errors=errors),
                    },
                ) from exc

            # 起盘之前把能查的都查完（v0.50.0）：格式、样式、output_path。此前这些在起盘并存档之后才查，被拒的调用白跑一次技法、
            # 多存一条 run，错误里还没有那条 run 的 id。
            try:
                normalized_format = self._normalize_report_format(request.format)
                report_style = "analysis" if normalized_format in _ENGINE_ONLY_FORMATS else self._report_style(request)
                self._output_request(request.output_path, normalized_format)
            except ToolValidationError as exc:
                trace["error_code"] = exc.code
                raise
            # 两种写法都收（chart / horosa_astro_chart）；后面按注册表键取存档与模板，所以先归一。
            request.tool_name = resolve_tool_name(request.tool_name) or request.tool_name
            if normalized_format == "ics" and request.tool_name not in CALENDAR_TOOLS:
                # 这个技法的结果从来不带可写进日历的日期：不白起一次盘、不白存一条记录。
                trace["error_code"] = "report.no_calendar_content"
                raise self._no_calendar_content(request.tool_name, [])
            result = self.run_tool(
                request.tool_name,
                request.payload,
                save_result=True,
                query_text=request.question,
                group_id=trace["group_id"],
            )
            if not result.ok:
                # 起盘失败就报起盘失败。往下走只会在「导出契约缺失」上再失败一次，真正的错误码与恢复说明全丢。
                trace["error_code"] = result.code
                return {
                    "ok": False,
                    "tool": result.tool,
                    "code": result.code,
                    "message": result.message,
                    "details": result.details,
                    "error": result.error.model_dump(mode="json") if result.error else None,
                    "summary": result.summary,
                    "warnings": result.warnings,
                    "memory_ref": result.memory_ref.model_dump(mode="json") if result.memory_ref else None,
                    "trace_id": result.trace_id,
                    "group_id": result.group_id,
                }
            if not result.memory_ref:
                raise ToolValidationError(
                    "Tool result was not saved and cannot be rendered as a report.",
                    code="report.from_tool.unsaved_result",
                    details={"tool_name": request.tool_name, "warnings": list(result.warnings)},
                )
            normalized_ai_report = self._normalize_report_ai_payload(
                ai_report=request.ai_report,
                ai_answer_text=request.ai_answer_text,
            )
            if not normalized_ai_report and report_style != "chart" and normalized_format not in _ENGINE_ONLY_FORMATS:
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
                    "style": report_style,
                    # 只转发调用方真写了的 language：缺省值转过去会被当成「显式 zh-CN」，盖掉全局的繁体设置。
                    **({"language": request.language} if request.language else {}),
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
                f"已调用 `{request.tool_name}` 并生成 {_FORMAT_NOUNS.get(normalized_format) or normalized_format.upper() + ' 结构化报告'}。",
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
        if normalized not in _REPORT_FORMATS:
            raise ToolValidationError(
                bilingual(f"不认识的报告格式：{value}（可选 {' / '.join(_REPORT_FORMATS)}）",
                          f"Unknown report format: {value} (choose one of {', '.join(_REPORT_FORMATS)})"),
                code="report.invalid_format",
                details={"format": f"{value}", "allowed": list(_REPORT_FORMATS)},
            )
        return normalized

    def _render_engine_only(
        self, request: Any, run: dict[str, Any], source_artifact: dict[str, Any], format_name: str, trace: dict[str, Any],
        output_request: output_paths.OutputRequest,
    ) -> dict[str, Any]:
        """PNG 盘图 / ICS 日历：只含引擎数据，不需要也不使用 ai_report（给了也不写回记忆，结果里如实说明）。"""
        chart = self.report_builder.chart_source(run=run, source_artifact=source_artifact)
        script = self._report_script(self._report_language(request))
        tool_name = chart["tool_name"]
        default = self.store.default_report_path(run_id=request.run_id, tool_name=tool_name, format_name=format_name)
        claimed: list[Path] = []
        try:
            if format_name == "png":
                outputs, extra = self._png_outputs(request, run, source_artifact, chart, script, default, output_request, claimed)
            else:
                outputs, extra = self._ics_outputs(request, run, chart, script, default, output_request, claimed)
        except OSError as exc:
            raise self._write_failed(exc, claimed[0] if claimed else default) from exc
        finally:
            for placeholder in claimed:
                output_paths.release(placeholder)
        artifacts, cards = [], []
        for rendered in outputs:
            artifact = self.store.record_report_artifact(
                run_id=request.run_id, tool_name=tool_name, format_name=format_name, path=Path(rendered["path"]),
                trace_id=trace["trace_id"], group_id=trace["group_id"],
            )
            artifacts.append(artifact)
            cards.append(_file_card(artifact["artifact_path"], format_name))
        notes = [note for rendered in outputs for note in _render_outcome_notes(rendered)]
        warnings = list(extra.pop("warnings", []))
        headline = extra.pop("headline")
        if request.ai_report or request.ai_answer_text:
            warnings.append(f"{format_name.upper()} 只含引擎数据，ai_report / ai_answer_text 未使用，也没有写回记忆；要出解读报告用 format=pdf / docx。")
        return {
            **artifacts[0],
            "file": cards[0],
            "files": cards,
            **extra,
            "source": chart["source"],
            "answer_writeback": None,
            **_render_outcome_fields(outputs[0]),
            **self._output_adjustment_fields(output_request, outputs[0]["path"]),
            "summary": [headline, *notes, *self._output_adjustment_notes(output_request, outputs[0]["path"])],
            **({"warnings": warnings} if warnings else {}),
            "trace_id": trace["trace_id"],
            "group_id": trace["group_id"],
        }

    def _report_figures(
        self, figures: list[dict[str, Any]], run: dict[str, Any], source_artifact: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """出报告用的盘图：①结果里没有、app 却画着的那张盘，此刻经真引擎补算（reports/aux_charts.py）；②能用星阙 app 原版
        画法的配上 app 的 SVG（一次 Node 调用），配不上的照旧画，规格里写 renderer 与原因。返回（盘图, 说明）：说明 = 补算或
        出图没成的那张缺了什么、为什么，印在盘图节下。"""
        from horosa_skill.reports import aux_charts
        from horosa_skill.reports.app_charts import attach_app_svgs

        chart = self.report_builder.chart_source(run=run, source_artifact=source_artifact)
        tool_name, data = str(chart["tool_name"]), chart["data"]
        notes: list[str] = []
        if aux_charts.wanted(tool_name, data):
            spec, note = self._aux_figure(tool_name, data, chart["input_normalized"])
            if spec is not None:
                figures = aux_charts.merge(tool_name, figures, spec)
            if note:
                notes.append(note)
        if not figures:
            return figures, notes
        undrawn: list[dict[str, Any]] = []
        figures, settle_notes = aux_charts.settle(attach_app_svgs(figures, tool_name, data, self.js_client, undrawn=undrawn))
        return figures, notes + settle_notes + [aux_charts.app_only_note(spec) for spec in undrawn]

    def _aux_figure(self, tool_name: str, data: dict[str, Any], payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        """补算一张盘图（不存档：runner 走 run_tool(save_result=False) 或直接打端点）。不会因此启动 runtime——引擎没在跑
        就照原样出报告并说明。任何失败都只换来一句说明，报告照出。"""
        from horosa_skill.reports import app_charts, aux_charts

        kind = aux_charts.engine(tool_name)
        if kind == "qizheng_moira" and not app_charts.enabled():
            return None, aux_charts.failure_note(tool_name, "星阙 app 画法已关闭（HOROSA_APP_CHARTS=0），这张盘没有自绘版")
        if not self._aux_engine_running(kind):
            return None, aux_charts.failure_note(tool_name, "排盘引擎没有在运行；出报告不会去启动它，引擎起来后重出报告即可")
        try:
            return aux_charts.build(tool_name, self._aux_engine_charts(tool_name, kind, data, payload)), None
        except Exception as exc:  # noqa: BLE001 — 补算是旁路：说清缺了哪张、为什么，报告照出
            return None, aux_charts.failure_note(tool_name, f"{type(exc).__name__}: {exc}")

    def _aux_engine_running(self, kind: str) -> bool:
        """补算只用已经在跑的引擎（_call_remote 探不到会去启动 runtime，出报告不该有这个副作用）。七政 Moira 规则在 Java 侧。"""
        if not self.chart_client.probe("/healthz"):
            return False
        return kind != "qizheng_moira" or self.client.probe("/common/time")

    def _aux_engine_charts(self, tool_name: str, kind: str, data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        if kind == "directed":
            return self._aux_directed_figure_charts(payload, tool_name, data)
        if kind == "progression":
            return self._aux_progression_charts(payload, tool_name, data)
        if kind == "tianxing":
            return self._aux_tianxing_moment_chart(payload, data)
        if kind == "syzygy":
            return self._aux_prenatal_syzygy_chart(payload, data)
        if tool_name == "guolao_chart":
            return self._aux_guolao_chart_moira(payload, data)
        return self._aux_qizhengzeri_moira(payload, data)

    def _png_outputs(
        self, request: Any, run: dict[str, Any], source_artifact: dict[str, Any], chart: dict[str, Any], script: str, default: Path,
        output_request: output_paths.OutputRequest, claimed: list[Path],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        figures, figure_gaps = self._report_figures(self.report_builder.build_figures(run=run, source_artifact=source_artifact), run, source_artifact)
        figures = localize_document(figures, script)
        figure_gaps = localize_document(figure_gaps, script)
        try:
            images = render_figure_pngs(figures, script=script, t=_labeler(script)) if figures else []
        except PngFontUnavailable:
            images = None  # 缺字体：下面照旧按字体问题报
        if (not figures or images == []) and figure_gaps:
            # 这个技法有盘，只是这次没画成（补算要的引擎没在跑、app 画法不可用）：先说缺了什么，不说「这个技法没有盘式」。
            from horosa_skill.reports import aux_charts

            gaps = [aux_charts.standing_alone(note) for note in figure_gaps]
            raise ToolValidationError(
                bilingual(
                    f"{' '.join(gaps)}`{chart['tool_name']}` 的 PNG 就是这张图，所以这次一个文件都没有写——不是这个技法没有盘式。"
                    "排除上面的原因后重出；或改出 PDF 排盘报告：正文照出，缺的那张会写明。",
                    f"The chart figure of `{chart['tool_name']}` could not be drawn this time (details.figure_gaps says which "
                    "figure and why), so no PNG was written. The technique does have a chart: fix the cause and render again, "
                    "or render a PDF chart report, which keeps the full text and states which figure is missing.",
                ),
                code="report.chart_figure_unavailable",
                details={"tool_name": chart["tool_name"], "format": "png", "figure_gaps": gaps, "fallback_format": "pdf"},
            )
        if not figures or images == []:  # 没有盘式 / 正文与数据对不上整张不画
            raise ToolValidationError(
                bilingual(
                    f"`{chart['tool_name']}` 这次结果里没有能画的盘图（这个技法没有盘式，或正文与数据对不上、整张不画）。"
                    "直接读工具结果，或出 PDF 排盘报告。",
                    f"`{chart['tool_name']}` has no chart figure in this result (the technique has no chart layout, or the "
                    "text and the data disagree so the figure is skipped). Read the tool result directly, or render a PDF chart report.",
                ),
                code="report.no_chart_content",
                details={"tool_name": chart["tool_name"], "format": "png"},
            )
        try:
            if images is None:  # 第一次因缺字体失败：重来一次，让下面按字体问题给出可操作的报错
                images = render_figure_pngs(figures, script=script, t=_labeler(script))
        except PngFontUnavailable as exc:
            missing = "".join(exc.missing[:40])
            raise ToolValidationError(
                bilingual(
                    "本机没有能画中文的 TrueType 字体" + (f"（所选字体缺这些字：{missing}）" if missing else "")
                    + "，画不出不带方块字的 PNG 盘图。改出 PDF（自带回退字体），或装中文字体（如 Noto Sans CJK）后重试。",
                    "No TrueType CJK font is available" + (f" (the chosen font lacks: {missing})" if missing else "")
                    + ", so the PNG chart cannot be drawn without tofu. Render a PDF instead (it has a built-in fallback font), "
                    "or install a CJK font such as Noto Sans CJK and retry.",
                ),
                code="report.png_font_unavailable",
                details={"tool_name": chart["tool_name"], "missing_characters": exc.missing[:40], "fallback_format": "pdf"},
            ) from exc
        paths, reserved = self._claim_output(output_request, default, len(images))
        claimed.extend(reserved)
        outputs = [write_artifact(image["png"], output_path=path, format_name="png") for image, path in zip(images, paths)]
        figure_list = [{"title": image["title"], "kind": image["kind"], "width": image["width"], "height": image["height"],
                        "path": rendered["path"]} for image, rendered in zip(images, outputs)]
        return outputs, {"title": f"{chart['label']} · 盘图", "figures": figure_list,
                         "headline": f"已生成 PNG 盘图 {len(outputs)} 张：{'、'.join(r['path'] for r in outputs)}",
                         **({"figure_gaps": figure_gaps, "warnings": list(figure_gaps)} if figure_gaps else {})}

    def _ics_outputs(
        self, request: Any, run: dict[str, Any], chart: dict[str, Any], script: str, default: Path,
        output_request: output_paths.OutputRequest, claimed: list[Path],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        extraction = extract_calendar(chart["tool_name"], chart["data"], input_normalized=chart["input_normalized"],
                                      label=chart["label"], run_id=str(request.run_id))
        if not extraction.events:
            raise self._no_calendar_content(chart["tool_name"], extraction.skipped)
        text = render_ics(extraction.events, run_id=str(request.run_id), dtstamp=_run_stamp(run),
                          calendar_name=f"{chart['label']} · 星阙 Horosa", text=_labeler(script))
        [output_path], reserved = self._claim_output(output_request, default)
        claimed.extend(reserved)
        rendered = write_artifact(text.encode("utf-8"), output_path=output_path, format_name="ics")
        skipped = extraction.skipped
        extra: dict[str, Any] = {"title": f"{chart['label']} · 日历", "event_count": len(extraction.events),
                                 "headline": f"已生成 ICS 日历（{len(extraction.events)} 个事件）：{rendered['path']}"}
        if skipped:
            extra["warnings"] = [f"有 {len(skipped)} 条日期没写进日历：", *skipped[:20]]
        return [rendered], extra

    def _no_calendar_content(self, tool_name: str, skipped: list[str]) -> ToolValidationError:
        return ToolValidationError(
            bilingual(
                f"`{tool_name}` 的结果里没有能写进日历的日期（日历只收择日的命中时段 / 候选时刻、推运各期与星历事件这些结果里写着的日期，"
                "不推算新日期）。" + (f"结果里的日期都写不进去：{'；'.join(skipped[:3])}" if skipped else ""),
                f"`{tool_name}` has no dates that can go into a calendar (only election hits / candidate moments, predictive "
                "periods and ephemeris events stated in the result are exported; no new dates are computed)."
                + (" Every date in the result was unusable." if skipped else ""),
            ),
            code="report.no_calendar_content",
            details={"tool_name": tool_name, "format": "ics", "calendar_tools": sorted(CALENDAR_TOOLS), "skipped": skipped[:20]},
        )

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
                errors = validation_errors(exc)
                raise ToolValidationError(
                    "Invalid payload for technique report.",
                    code="report.technique.invalid_payload",
                    details={
                        "errors": errors,
                        "agent_recovery": build_validation_recovery(operation_name="technique_report", errors=errors),
                    },
                ) from exc

            normalized_format = str(request.format or "markdown").lower().strip()
            if normalized_format not in _TECHNIQUE_REPORT_FORMATS:
                raise ToolValidationError(
                    bilingual(f"不认识的技法依据报告格式：{request.format}（可选 {' / '.join(_TECHNIQUE_REPORT_FORMATS)}）",
                              f"Unknown technique report format: {request.format} (choose one of {', '.join(_TECHNIQUE_REPORT_FORMATS)})"),
                    code="report.technique.invalid_format",
                    details={"format": request.format, "allowed": list(_TECHNIQUE_REPORT_FORMATS)},
                )
            output_request = self._output_request(request.output_path, normalized_format)

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
            [output_path], reserved = self._claim_output(output_request, base.with_suffix(f".{suffix}"))
            script = self.settings.output_script
            try:
                # 技法依据报告交简体原文：渲染器生成人读版 / markdown 后整体转一次（模板标签也要转，见 render_report）。
                rendered = render_report(document, output_path=output_path, format_name=normalized_format, script=script)
            except ValueError as exc:
                raise ToolValidationError(
                    str(exc), code="report.technique.render_failed", details={"format": normalized_format}
                ) from exc
            except OSError as exc:
                raise self._write_failed(exc, output_path) from exc
            finally:
                for placeholder in reserved:
                    output_paths.release(placeholder)
            document = localize_document(document, script)

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
                "file": _file_card(rendered["path"], rendered["format"]),
                **_render_outcome_fields(rendered),
                **self._output_adjustment_fields(output_request, rendered["path"]),
                "document": document,
                "summary": [
                    f"已生成技法依据报告（{document['technique_count']} 个技法）：{rendered['path']}",
                    *_render_outcome_notes(rendered),
                    *self._output_adjustment_notes(output_request, rendered["path"]),
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
                bilingual(
                    f"找不到这条运行记录：{run_id}" + (f"（工具 {tool_name}）" if tool_name else "")
                    + "。用 horosa_memory_query 查到要导出的那条记录，再用它的 run_id 重试。",
                    f"Run not found: {run_id}" + (f" (tool {tool_name})" if tool_name else "")
                    + ". Use horosa_memory_query to find the run you want to export, then retry with its run_id.",
                ),
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
                bilingual(
                    f"这条运行记录（{run_id}）里没有可以出报告的技法结果" + (f"（没有 {tool_name} 的结果）" if tool_name else "")
                    + "。用 horosa_memory_show 看它存了哪些工具的结果，或重新起盘。",
                    f"Run {run_id} holds no technique result that can be reported" + (f" (nothing from {tool_name})" if tool_name else "")
                    + ". Use horosa_memory_show to see which tool results it holds, or run the technique again.",
                ),
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
                bilingual(
                    f"这条运行记录里 {source_tool} 的结果没有完整的导出文本（多半是起盘失败时存下的），出不了报告。重新起盘后再出。",
                    f"The stored {source_tool} result in this run has no complete export text (most likely saved from a failed "
                    "run), so it cannot be reported. Run the technique again, then render.",
                ),
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
