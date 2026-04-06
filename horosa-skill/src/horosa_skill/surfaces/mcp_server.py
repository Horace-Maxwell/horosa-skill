from __future__ import annotations

import json
from inspect import Parameter, Signature
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.schemas.common import DispatchEnvelope, ToolEnvelope
from horosa_skill.schemas.tools import DispatchInput, MemoryAnswerInput
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

    def horosa_memory_record_answer(**kwargs: Any) -> dict[str, Any]:
        return service.record_ai_answer(
            _normalize_mcp_request(_merge_mcp_arguments(kwargs), MemoryAnswerInput)
        )
    horosa_memory_record_answer.__signature__ = _signature_for_input_model(MemoryAnswerInput)
    horosa_memory_record_answer.__annotations__ = {"return": dict[str, Any]}
    mcp.tool(name="horosa_memory_record_answer")(horosa_memory_record_answer)

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


def run_mcp_server(settings: Settings, *, transport: str) -> None:
    service = HorosaSkillService(settings)
    server = create_mcp_server(service, settings)
    server.run(transport=transport)
