from __future__ import annotations

import json
from inspect import Parameter, Signature
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from horosa_skill.agent_guidance import build_agent_guidance
from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
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
        return service.dispatch(_normalize_mcp_request(_merge_mcp_arguments(kwargs), DispatchInput))
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
        return service.record_ai_answer(
            _normalize_mcp_request(_merge_mcp_arguments(kwargs), MemoryAnswerInput)
        )
    horosa_memory_record_answer.__signature__ = _signature_for_input_model(MemoryAnswerInput)
    horosa_memory_record_answer.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_memory_record_answer")(horosa_memory_record_answer)

    def horosa_memory_query(**kwargs: Any) -> dict[str, Any]:
        return service.query_memory(
            _normalize_mcp_request(_merge_mcp_arguments(kwargs), MemoryQueryInput)
        )
    horosa_memory_query.__signature__ = _signature_for_input_model(MemoryQueryInput)
    horosa_memory_query.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_memory_query")(horosa_memory_query)

    def horosa_memory_show(**kwargs: Any) -> dict[str, Any]:
        return service.show_memory(
            _normalize_mcp_request(_merge_mcp_arguments(kwargs), MemoryShowInput)
        )
    horosa_memory_show.__signature__ = _signature_for_input_model(MemoryShowInput)
    horosa_memory_show.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_memory_show")(horosa_memory_show)

    def horosa_report_template(**kwargs: Any) -> dict[str, Any]:
        return service.report_template(
            _normalize_mcp_request(_merge_mcp_arguments(kwargs), ReportTemplateInput)
        )
    horosa_report_template.__signature__ = _signature_for_input_model(ReportTemplateInput)
    horosa_report_template.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_report_template")(horosa_report_template)

    def horosa_report_render(**kwargs: Any) -> dict[str, Any]:
        return service.report_render(
            _normalize_mcp_request(_merge_mcp_arguments(kwargs), ReportRenderInput)
        )
    horosa_report_render.__signature__ = _signature_for_input_model(ReportRenderInput)
    horosa_report_render.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_report_render")(horosa_report_render)

    def horosa_report_from_run(**kwargs: Any) -> dict[str, Any]:
        return service.report_render(
            _normalize_mcp_request(_merge_mcp_arguments(kwargs), ReportRenderInput)
        )
    horosa_report_from_run.__signature__ = _signature_for_input_model(ReportRenderInput)
    horosa_report_from_run.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_report_from_run")(horosa_report_from_run)

    def horosa_report_from_tool(**kwargs: Any) -> dict[str, Any]:
        return service.report_from_tool(
            _normalize_mcp_request(_merge_mcp_arguments(kwargs), ReportFromToolInput)
        )
    horosa_report_from_tool.__signature__ = _signature_for_input_model(ReportFromToolInput)
    horosa_report_from_tool.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_report_from_tool")(horosa_report_from_tool)

    for definition in TOOL_DEFINITIONS.values():
        input_model = definition.input_model

        def _factory(tool_name: str, model: Any) -> Any:
            def _tool(**kwargs: Any) -> ToolEnvelope:
                return service.run_tool(
                    tool_name,
                    _normalize_mcp_request(_merge_mcp_arguments(kwargs), model),
                )

            _tool.__name__ = TOOL_DEFINITIONS[tool_name].mcp_name
            _tool.__doc__ = TOOL_DEFINITIONS[tool_name].description
            _tool.__signature__ = _signature_for_input_model(model)
            _tool.__annotations__ = {"return": ToolEnvelope}
            return mcp.tool(name=TOOL_DEFINITIONS[tool_name].mcp_name)(_tool)

        _factory(definition.name, input_model)

    return mcp


def run_mcp_server(settings: Settings, *, transport: str, service: HorosaSkillService | None = None) -> None:
    service = service or HorosaSkillService(settings)
    server = create_mcp_server(service, settings)
    server.run(transport=transport)
