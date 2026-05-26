from __future__ import annotations

import json
from inspect import Parameter, Signature
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from horosa_skill.agent_guidance import build_agent_guidance, build_tool_docstring, validate_agent_preflight
from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import ToolValidationError
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


def _agent_preflight_error(tool_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    preflight = validate_agent_preflight(tool_name, payload)
    if preflight.get("ok"):
        return None
    return _mcp_error_payload(ToolValidationError(preflight["message"], code=preflight["code"], details=preflight))


def create_mcp_server(service: HorosaSkillService, settings: Settings) -> FastMCP:
    mcp = FastMCP(
        "Horosa Skill",
        instructions=(
            "Use Horosa tools to compute structured metaphysical outputs. "
            "Prefer horosa_dispatch for natural-language requests, and atomic tools for direct, schema-driven calls."
        ),
        host=settings.host,
        port=settings.port,
        streamable_http_path="/mcp",
        mount_path="/",
        log_level=settings.log_level,
    )

    def horosa_dispatch(**kwargs: Any) -> DispatchEnvelope:
        raw_payload = _merge_mcp_arguments(kwargs)
        if isinstance(raw_payload, dict):
            error = _agent_preflight_error("dispatch", raw_payload)
            if error is not None:
                return error
        try:
            return service.dispatch(_normalize_mcp_request(raw_payload, DispatchInput))
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
    horosa_dispatch.__signature__ = _signature_for_input_model(DispatchInput)
    horosa_dispatch.__annotations__ = {"return": DispatchEnvelope}
    mcp.tool(name="horosa_dispatch")(horosa_dispatch)

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
    mcp.tool(name="horosa_agent_guidance")(horosa_agent_guidance)

    def horosa_memory_record_answer(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.record_ai_answer(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), MemoryAnswerInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
    horosa_memory_record_answer.__signature__ = _signature_for_input_model(MemoryAnswerInput)
    horosa_memory_record_answer.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_memory_record_answer")(horosa_memory_record_answer)

    def horosa_memory_query(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.query_memory(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), MemoryQueryInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
    horosa_memory_query.__signature__ = _signature_for_input_model(MemoryQueryInput)
    horosa_memory_query.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_memory_query")(horosa_memory_query)

    def horosa_memory_show(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.show_memory(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), MemoryShowInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
    horosa_memory_show.__signature__ = _signature_for_input_model(MemoryShowInput)
    horosa_memory_show.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_memory_show")(horosa_memory_show)

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
    mcp.tool(name="horosa_report_template")(horosa_report_template)

    def horosa_report_render(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.report_render(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), ReportRenderInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
        except Exception as exc:  # noqa: BLE001 - never break the MCP session on a report/IO error
            return _mcp_internal_error_payload(exc)
    horosa_report_render.__signature__ = _signature_for_input_model(ReportRenderInput)
    horosa_report_render.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_report_render")(horosa_report_render)

    def horosa_report_from_run(**kwargs: Any) -> dict[str, Any]:
        try:
            return service.report_render(
                _normalize_mcp_request(_merge_mcp_arguments(kwargs), ReportRenderInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
        except Exception as exc:  # noqa: BLE001 - never break the MCP session on a report/IO error
            return _mcp_internal_error_payload(exc)
    horosa_report_from_run.__signature__ = _signature_for_input_model(ReportRenderInput)
    horosa_report_from_run.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_report_from_run")(horosa_report_from_run)

    def horosa_report_from_tool(**kwargs: Any) -> dict[str, Any]:
        raw_payload = _merge_mcp_arguments(kwargs)
        if isinstance(raw_payload, dict):
            tool_name = raw_payload.get("tool_name")
            payload = raw_payload.get("payload")
            if isinstance(tool_name, str) and isinstance(payload, dict):
                error = _agent_preflight_error(tool_name, payload)
                if error is not None:
                    return error
        try:
            return service.report_from_tool(
                _normalize_mcp_request(raw_payload, ReportFromToolInput)
            )
        except ToolValidationError as exc:
            return _mcp_error_payload(exc)
        except Exception as exc:  # noqa: BLE001 - never break the MCP session on a report/IO error
            return _mcp_internal_error_payload(exc)
    horosa_report_from_tool.__signature__ = _signature_for_input_model(ReportFromToolInput)
    horosa_report_from_tool.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_report_from_tool")(horosa_report_from_tool)

    for definition in TOOL_DEFINITIONS.values():
        input_model = definition.input_model

        def _factory(tool_name: str, model: Any) -> Any:
            def _tool(**kwargs: Any) -> ToolEnvelope:
                raw_payload = _merge_mcp_arguments(kwargs)
                if isinstance(raw_payload, dict):
                    error = _agent_preflight_error(tool_name, raw_payload)
                    if error is not None:
                        return error
                try:
                    return service.run_tool(
                        tool_name,
                        _normalize_mcp_request(raw_payload, model),
                    )
                except ToolValidationError as exc:
                    return _mcp_error_payload(exc)

            _tool.__name__ = TOOL_DEFINITIONS[tool_name].mcp_name
            _tool.__doc__ = build_tool_docstring(tool_name)
            _tool.__signature__ = _signature_for_input_model(model)
            _tool.__annotations__ = {"return": ToolEnvelope}
            return mcp.tool(name=TOOL_DEFINITIONS[tool_name].mcp_name)(_tool)

        _factory(definition.name, input_model)

    return mcp


def run_mcp_server(settings: Settings, *, transport: str, service: HorosaSkillService | None = None) -> None:
    service = service or HorosaSkillService(settings)
    server = create_mcp_server(service, settings)
    server.run(transport=transport)
