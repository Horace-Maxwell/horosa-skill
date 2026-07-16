from __future__ import annotations

import json
import os
from inspect import Parameter, Signature
from typing import Any, Literal

from mcp import types as mcp_types
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ValidationError, create_model

from horosa_skill.agent_guidance import (
    build_agent_guidance,
    build_technique_catalog,
    build_tool_docstring,
    build_validation_recovery,
    validate_agent_preflight,
)
from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import ToolValidationError
from horosa_skill.exports.registry import build_export_registry
from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.schemas.common import DispatchEnvelope, ToolEnvelope
from horosa_skill.schemas.tools import (
    AgentGuidanceInput,
    DispatchInput,
    MemoryAnswerInput,
    MemoryQueryInput,
    MemoryShowInput,
    ReportFromToolInput,
    ReportRenderInput,
    ReportTemplateInput,
)
from horosa_skill.service import HorosaSkillService

# 太极图 SVG（data URI，离线友好）：server 级图标，客户端渲染刚起步、成本近零先埋。
_SERVER_ICON = mcp_types.Icon(
    src=(
        "data:image/svg+xml;utf8,"
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
        "<circle cx='32' cy='32' r='30' fill='%23111827'/>"
        "<path d='M32 2a30 30 0 000 60 15 15 0 010-30 15 15 0 000-30z' fill='%23f9fafb'/>"
        "<circle cx='32' cy='17' r='5' fill='%23111827'/>"
        "<circle cx='32' cy='47' r='5' fill='%23f9fafb'/></svg>"
    ),
    mimeType="image/svg+xml",
    sizes=["64x64"],
)

# Tool annotations（MCP 2025-11-25）：客户端用它决定确认摩擦/自动放行；目录审核要求标注准确。
# 判定口径（如实标注，见 AGENTS.md §4 / LESSONS）：
# - 全部工具 openWorldHint=False（local-first：只打本机 runtime，不出网）。
# - 查询类（registry/knowledge/guidance/memory 读、报告模板）readOnlyHint=True + idempotent=True。
# - 技法计算类 readOnlyHint=False（默认会写一条本地 run 记录，memory_query 可见）、
#   destructiveHint=False（只追加、不改不删）、idempotentHint=False（重复调用会追加新 run 行）。
# - 报告渲染 readOnly=False + idempotent=True（同 run_id+format 原子覆盖同一产物）；
#   report_from_tool 会重新起盘+新 run → idempotent=False。
_ANN_QUERY = mcp_types.ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
_ANN_CALC = mcp_types.ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)
_ANN_RENDER = mcp_types.ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)

_READONLY_TOOL_NAMES = {
    "export_registry",
    "export_parse",
    "knowledge_registry",
    "knowledge_read",
    "ziwei_rules",
    "gua_desc",
    "gua_meiyi",
    "astrodata",
}


def _tool_annotations(tool_name: str) -> mcp_types.ToolAnnotations:
    if tool_name in _READONLY_TOOL_NAMES:
        return _ANN_QUERY
    return _ANN_CALC


def _normalize_mcp_request(raw_request: Any, model: type[BaseModel]) -> dict[str, Any]:
    payload = raw_request
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(exclude_none=True)

    if payload is None:
        payload = {}

    if isinstance(payload, str):
        text = payload.strip()
        payload = {} if not text else json.loads(text)

    if not isinstance(payload, dict):
        raise ValueError("request must be an object or a JSON object string")

    payload = normalize_request_payload(payload)
    normalized = model.model_validate(payload)
    return normalized.model_dump(exclude_none=True)


def _signature_for_input_model(model: type[BaseModel]) -> Signature:
    parameters: list[Parameter] = [
        Parameter(
            "request",
            kind=Parameter.KEYWORD_ONLY,
            default=None,
            annotation=dict[str, Any] | str | None,
        )
    ]

    for field_name, field in model.model_fields.items():
        default = Parameter.empty
        if not field.is_required():
            if field.default_factory is not None:
                default = field.default_factory()
            else:
                default = field.default
        parameters.append(
            Parameter(
                field_name,
                kind=Parameter.KEYWORD_ONLY,
                default=default,
                annotation=field.annotation,
            )
        )

    return Signature(parameters=parameters)


def _merge_mcp_arguments(kwargs: dict[str, Any]) -> dict[str, Any] | str | None:
    request = kwargs.pop("request", None)
    if request is not None:
        return request
    return kwargs


def _mcp_error_payload(exc: ToolValidationError) -> dict[str, Any]:
    return {
        "ok": False,
        "code": exc.code,
        "message": str(exc),
        "details": exc.details,
        "error": {
            "code": exc.code,
            "message": str(exc),
            "details": exc.details,
        },
    }


def _mcp_internal_error_payload(exc: Exception) -> dict[str, Any]:
    # Last-resort structured error so an unexpected failure (e.g. a DOCX/PDF renderer or disk
    # I/O error during report generation) returns cleanly instead of breaking the MCP session.
    message = str(exc) or exc.__class__.__name__
    details = {"exception_type": type(exc).__name__}
    return {
        "ok": False,
        "code": "tool.internal_error",
        "message": message,
        "details": details,
        "error": {"code": "tool.internal_error", "message": message, "details": details},
    }


def _mcp_validation_error_payload(operation_name: str, tool_name: str | None, exc: ValidationError) -> dict[str, Any]:
    # 已确认但载荷畸形（类型错/字段形状错）→ 与闸门同形的「可转问用户」恢复契约，
    # 而不是让 pydantic 文本裸奔（agent_guidance.build_validation_recovery 是同一套机读结构）。
    errors = [
        {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
        for err in exc.errors(include_url=False)
    ]
    recovery = build_validation_recovery(operation_name=operation_name, errors=errors, tool_name=tool_name)
    details = {"validation_errors": errors, "agent_recovery": recovery}
    message = f"{operation_name} payload failed validation; see details.agent_recovery."
    return {
        "ok": False,
        "code": "tool.invalid_payload",
        "message": message,
        "details": details,
        "error": {"code": "tool.invalid_payload", "message": message, "details": details},
    }


def _agent_preflight_error(tool_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    preflight = validate_agent_preflight(tool_name, payload)
    if preflight.get("ok"):
        return None
    return _mcp_error_payload(ToolValidationError(preflight["message"], code=preflight["code"], details=preflight))


# ---------------------------------------------------------------------------
# MCP elicitation（双轨澄清闸）
#
# 客户端声明 elicitation 能力（Claude Code ≥2.1.76 / Cursor / VS Code）时，闸门拦截不再只回
# 结构化错误，而是先用原生表单问一次用户：
#   - 「按星阙默认继续」→ 直接以 defaults_accepted=true 重跑（最常见的快路径一跳闭环）；
#   - 「我在对话里补充设置」/取消 → 回落到既有 agent_guidance.required 错误往返（agent 照
#     SKILL.md 在聊天里追问并自行构造载荷——表单答案只进 clarification_notes，绝不静默替用户
#     选具体术数参数）。
# 不支持 elicitation 的客户端（Claude Desktop / Codex / Open WebUI / OpenClaw / CLI）行为与
# 从前逐字节一致。HOROSA_MCP_ELICIT=0 可整体关闭。任何异常都吞掉并回落——elicitation 永远
# 只能是增强，不能成为新的失败点。
# ---------------------------------------------------------------------------

_ELICIT_DEFAULTS = "按星阙默认继续 (use Xingque defaults)"
_ELICIT_PROVIDE = "我在对话里补充设置 (I will provide settings in chat)"
_ELICIT_CANCEL = "取消 (cancel)"


def _elicitation_enabled() -> bool:
    return os.environ.get("HOROSA_MCP_ELICIT", "1").strip().lower() not in {"0", "false", "off"}


async def _maybe_elicit_gate(
    mcp: FastMCP, tool_name: str, payload: dict[str, Any], gate_error: dict[str, Any]
) -> dict[str, Any] | None:
    """Try resolving a tripped clarification gate via native MCP elicitation.

    Returns an updated payload to proceed with, or None to fall back to the structured
    gate error (which may be enriched with the user's form answer in details.user_notes).
    """
    if not _elicitation_enabled():
        return None
    try:
        ctx = mcp.get_context()
        session = ctx.session
        if not session.check_client_capability(
            mcp_types.ClientCapabilities(elicitation=mcp_types.ElicitationCapability())
        ):
            return None
        prompt = (
            gate_error.get("details", {}).get("agent_recovery", {}).get("prompt_to_user")
            or f"调用 {tool_name} 前需要确认会影响结果的设置。"
        )
        schema = create_model(
            "HorosaGateDecision",
            decision=(
                Literal[_ELICIT_DEFAULTS, _ELICIT_PROVIDE, _ELICIT_CANCEL],  # type: ignore[valid-type]
                _ELICIT_DEFAULTS,
            ),
            notes=(str, ""),
        )
        result = await ctx.elicit(message=prompt, schema=schema)
        if result.action != "accept" or result.data is None:
            return None
        decision = getattr(result.data, "decision", "")
        notes = str(getattr(result.data, "notes", "") or "").strip()
        if decision == _ELICIT_DEFAULTS:
            updated = dict(payload)
            updated["defaults_accepted"] = True
            note = "user accepted Xingque defaults via MCP elicitation form"
            updated["clarification_notes"] = f"{note}; user notes: {notes}" if notes else note
            return updated
        if notes:
            # 用户选了「补充设置」并给了备注：不代答具体参数，把原话带回给 agent 追问闭环。
            gate_error.setdefault("details", {})["user_notes"] = notes
            recovery = gate_error.get("details", {}).get("agent_recovery")
            if isinstance(recovery, dict):
                recovery["user_notes"] = notes
        return None
    except Exception:  # noqa: BLE001 — elicitation must never become a new failure mode
        return None


def create_mcp_server(service: HorosaSkillService, settings: Settings) -> FastMCP:
    mcp = FastMCP(
        "Horosa Skill",
        instructions=(
            "Use Horosa tools to compute structured metaphysical outputs. "
            "Prefer horosa_dispatch for natural-language requests, and atomic tools for direct, schema-driven calls."
        ),
        website_url="https://github.com/Horace-Maxwell/horosa-skill",
        icons=[_SERVER_ICON],
        host=settings.host,
        port=settings.port,
        streamable_http_path="/mcp",
        mount_path="/",
        log_level=settings.log_level,
    )

    async def horosa_dispatch(**kwargs: Any) -> DispatchEnvelope:
        raw_payload = _merge_mcp_arguments(kwargs)
        if isinstance(raw_payload, dict):
            error = _agent_preflight_error("dispatch", raw_payload)
            if error is not None:
                updated = await _maybe_elicit_gate(mcp, "dispatch", raw_payload, error)
                if updated is None:
                    return error
                raw_payload = updated
        try:
            return service.dispatch(_normalize_mcp_request(raw_payload, DispatchInput))
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
        except ValidationError as exc:
            return _mcp_validation_error_payload("horosa_dispatch", "dispatch", exc)
    dispatch_doc = (
        "Route a natural-language 术数/占星 request to the right Horosa technique tools and run them. "
        "Results are saved to local memory by default (save_result=false to disable)."
    )
    if settings.mcp_compact:
        dispatch_doc += "\n\n" + build_technique_catalog()
    horosa_dispatch.__doc__ = dispatch_doc
    horosa_dispatch.__signature__ = _signature_for_input_model(DispatchInput)
    horosa_dispatch.__annotations__ = {"return": DispatchEnvelope}
    mcp.tool(name="horosa_dispatch", annotations=_ANN_CALC)(horosa_dispatch)

    def horosa_agent_guidance(**kwargs: Any) -> dict[str, Any]:
        payload = _normalize_mcp_request(_merge_mcp_arguments(kwargs), AgentGuidanceInput)
        return build_agent_guidance(
            tool_name=payload.get("tool_name"),
            intent=payload.get("intent"),
            include_all=payload.get("include_all", False),
        )
    horosa_agent_guidance.__doc__ = (
        "Return machine-readable guidance for agents before calling Horosa tools. "
        "Use this to decide which user settings must be clarified instead of silently defaulted."
    )
    horosa_agent_guidance.__signature__ = _signature_for_input_model(AgentGuidanceInput)
    horosa_agent_guidance.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_agent_guidance", annotations=_ANN_QUERY)(horosa_agent_guidance)

    def horosa_memory_record_answer(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.record_ai_answer(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), MemoryAnswerInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
    horosa_memory_record_answer.__signature__ = _signature_for_input_model(MemoryAnswerInput)
    horosa_memory_record_answer.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_memory_record_answer", annotations=_ANN_RENDER)(horosa_memory_record_answer)

    def horosa_memory_query(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.query_memory(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), MemoryQueryInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
    horosa_memory_query.__signature__ = _signature_for_input_model(MemoryQueryInput)
    horosa_memory_query.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_memory_query", annotations=_ANN_QUERY)(horosa_memory_query)

    def horosa_memory_show(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.show_memory(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), MemoryShowInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
    horosa_memory_show.__signature__ = _signature_for_input_model(MemoryShowInput)
    horosa_memory_show.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_memory_show", annotations=_ANN_QUERY)(horosa_memory_show)

    def horosa_report_template(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.report_template(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), ReportTemplateInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
        except Exception as exc:  # noqa: BLE001 - never break the MCP session on a report/IO error
            return _mcp_internal_error_payload(exc)
    horosa_report_template.__signature__ = _signature_for_input_model(ReportTemplateInput)
    horosa_report_template.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_report_template", annotations=_ANN_QUERY)(horosa_report_template)

    def horosa_report_render(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.report_render(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), ReportRenderInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
        except Exception as exc:  # noqa: BLE001 - never break the MCP session on a report/IO error
            return _mcp_internal_error_payload(exc)
    horosa_report_render.__doc__ = (
        "Render a stored run into a DOCX/PDF/JSON report. Preferred when you already have a run_id "
        "(from a prior tool call): pass run_id + format + your ai_report; the ai_report is auto "
        "written back to memory (no separate memory_record_answer call needed)."
    )
    horosa_report_render.__signature__ = _signature_for_input_model(ReportRenderInput)
    horosa_report_render.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_report_render", annotations=_ANN_RENDER)(horosa_report_render)

    # horosa_report_from_run 已下线：与 horosa_report_render 逐行同义（同一 ReportRenderInput
    # → service.report_render），两个同义工具挤占 tools/list 并造成「该用哪个」歧义。

    async def horosa_report_from_tool(**kwargs: Any) -> dict[str, Any]:
        raw_payload = _merge_mcp_arguments(kwargs)
        if isinstance(raw_payload, dict):
            tool_name = raw_payload.get("tool_name")
            payload = raw_payload.get("payload")
            if isinstance(tool_name, str) and isinstance(payload, dict):
                error = _agent_preflight_error(tool_name, payload)
                if error is not None:
                    updated = await _maybe_elicit_gate(mcp, tool_name, payload, error)
                    if updated is None:
                        return error
                    raw_payload = dict(raw_payload)
                    raw_payload["payload"] = updated
        try:
            return service.report_from_tool(
                _normalize_mcp_request(raw_payload, ReportFromToolInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
        except ValidationError as exc:
            return _mcp_validation_error_payload("horosa_report_from_tool", None, exc)
        except Exception as exc:  # noqa: BLE001 - never break the MCP session on a report/IO error
            return _mcp_internal_error_payload(exc)
    horosa_report_from_tool.__doc__ = (
        "One-shot: run a technique tool AND prepare its report. NOTE this re-casts the chart — if you "
        "already called the tool and hold a run_id, use horosa_report_render instead (avoids a duplicate "
        "backend call and a duplicate stored run)."
    )
    horosa_report_from_tool.__signature__ = _signature_for_input_model(ReportFromToolInput)
    horosa_report_from_tool.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_report_from_tool", annotations=_ANN_CALC)(horosa_report_from_tool)

    # ------------------------------------------------------------------
    # MCP resources：只读目录以资源形态暴露（客户端可 @ 引用，不占 tools/list）。
    # ------------------------------------------------------------------

    @mcp.resource(
        "horosa://catalog/techniques",
        name="horosa-technique-catalog",
        title="Horosa 技法目录 / technique catalog",
        description="All callable Horosa technique tools with one-line bilingual descriptions.",
        mime_type="text/markdown",
    )
    def technique_catalog_resource() -> str:
        return build_technique_catalog()

    @mcp.resource(
        "horosa://catalog/export-registry",
        name="horosa-export-registry",
        title="Horosa 导出契约注册表 / export contract registry",
        description="Machine-readable export contract (per-technique snapshot sections) mirrored from Xingque aiExport.",
        mime_type="application/json",
    )
    def export_registry_resource() -> str:
        return json.dumps(build_export_registry(), ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # MCP prompts：高频工作流按钮化（Claude Code 里成为 /mcp__horosa__… 斜杠命令）。
    # ------------------------------------------------------------------

    @mcp.prompt(
        name="quick_cast",
        title="快速起盘并解读 / quick cast & read",
        description="Cast one Horosa technique for a moment/birth and explain from the export snapshot.",
    )
    def prompt_quick_cast(technique: str = "", question: str = "") -> str:
        target = technique or "（按用户意图选择技法）"
        asked = question or "（用户尚未给出具体问题）"
        return (
            f"请用 Horosa 工具起一个「{target}」盘并解读。用户的问题：{asked}。\n"
            "流程：1) 若时间/地点/性别/流派等会改变结果的设置缺失，先按 horosa_agent_guidance 问我；"
            "2) 调用对应技法工具（用户确认后带 agent_confirmed_settings/defaults_accepted）；"
            "3) 只根据返回的 export_snapshot.export_text 分段解读——先结论、再证据段、再机会/风险/时机/建议；"
            "4) 不要手算任何术数结果。"
        )

    @mcp.prompt(
        name="annual_fortune",
        title="流年运势报告 / annual fortune report",
        description="Run the right predictive tools for a target year and produce a structured reading.",
    )
    def prompt_annual_fortune(year: str = "", birth: str = "") -> str:
        return (
            f"请为我做{year or '目标年份'}的流年运势分析（出生信息：{birth or '待我提供'}）。\n"
            "要求：1) 先确认目标年份、出生数据、地点时区等必需设置（缺了就问我）；"
            "2) 选择合适的推运工具（如 profection/solarreturn/bazi_direct/liureng_runyear），"
            "预测类必须带目标 datetime/dirZone 等字段；3) 每个结论都引用返回快照里的具体段落；"
            "4) 最后按 机会/风险/时机/建议 汇总。"
        )

    @mcp.prompt(
        name="export_report",
        title="导出正式报告 / export a formal report",
        description="Render the latest run into a DOCX/PDF consulting report with the AI analysis written back.",
    )
    def prompt_export_report(format: str = "docx") -> str:
        return (
            f"请把刚才的分析导出为 {format or 'docx'} 报告。\n"
            "流程：用已有 run_id 调 horosa_report_render（format + ai_report，分析会自动写回记忆；"
            "不要用 horosa_report_from_tool 重复起盘）。报告正文要像咨询报告：直接结论开头、"
            "引用盘面证据、机会/风险/时机/建议分列、保留「排盘规则」行；不要出现 run_id/JSON 等机器元数据。"
        )

    if settings.mcp_compact:
        # 精简模式（8 门面 + tool_run = 9 工具）：技法工具不平铺，注册一个按名直呼的通用工具（dispatch 关键词路由只覆盖部分技法，
        # 直呼通道保证 78 技法全部可达）；澄清闸照常生效。
        async def horosa_tool_run(**kwargs: Any) -> ToolEnvelope:
            raw_payload = _merge_mcp_arguments(kwargs)
            if not isinstance(raw_payload, dict):
                raw_payload = {}
            tool_name = str(raw_payload.pop("tool_name", "") or "")
            request = raw_payload.pop("request", None)
            payload = request if isinstance(request, dict) else raw_payload
            if tool_name not in TOOL_DEFINITIONS:
                return _mcp_error_payload(
                    ToolValidationError(
                        f"Unknown tool: {tool_name or '(missing tool_name)'}",
                        code="tool.unknown",
                        details={"tool_name": tool_name, "hint": "See the technique catalog in this tool's description."},
                    )
                )
            error = _agent_preflight_error(tool_name, payload)
            if error is not None:
                updated = await _maybe_elicit_gate(mcp, tool_name, payload, error)
                if updated is None:
                    return error
                payload = updated
            try:
                return service.run_tool(
                    tool_name,
                    _normalize_mcp_request(payload, TOOL_DEFINITIONS[tool_name].input_model),
                )
            except ToolValidationError as exc:
                return _mcp_error_payload(exc)
            except ValidationError as exc:
                return _mcp_validation_error_payload("horosa_tool_run", tool_name, exc)

        horosa_tool_run.__doc__ = (
            "Run any Horosa technique tool by name: pass tool_name plus the tool's input fields "
            "(flat or under `request`). Same clarification gate and envelope as the dedicated tools.\n\n"
            + build_technique_catalog()
        )
        horosa_tool_run.__annotations__ = {"return": ToolEnvelope}
        mcp.tool(name="horosa_tool_run", annotations=_ANN_CALC)(horosa_tool_run)
        return mcp

    for definition in TOOL_DEFINITIONS.values():
        input_model = definition.input_model

        def _factory(tool_name: str, model: Any) -> Any:
            async def _tool(**kwargs: Any) -> ToolEnvelope:
                raw_payload = _merge_mcp_arguments(kwargs)
                if isinstance(raw_payload, dict):
                    error = _agent_preflight_error(tool_name, raw_payload)
                    if error is not None:
                        updated = await _maybe_elicit_gate(mcp, tool_name, raw_payload, error)
                        if updated is None:
                            return error
                        raw_payload = updated
                try:
                    return service.run_tool(
                        tool_name,
                        _normalize_mcp_request(raw_payload, model),
                    )
                except ToolValidationError as exc:
                    return _mcp_error_payload(exc)
                except ValidationError as exc:
                    return _mcp_validation_error_payload(tool_name, tool_name, exc)

            _tool.__name__ = TOOL_DEFINITIONS[tool_name].mcp_name
            _tool.__doc__ = build_tool_docstring(tool_name)
            _tool.__signature__ = _signature_for_input_model(model)
            _tool.__annotations__ = {"return": ToolEnvelope}
            return mcp.tool(
                name=TOOL_DEFINITIONS[tool_name].mcp_name,
                annotations=_tool_annotations(tool_name),
            )(_tool)

        _factory(definition.name, input_model)

    return mcp


def run_mcp_server(settings: Settings, *, transport: str, service: HorosaSkillService | None = None) -> None:
    service = service or HorosaSkillService(settings)
    server = create_mcp_server(service, settings)
    server.run(transport=transport)
