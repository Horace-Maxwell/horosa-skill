from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.schemas.common import DispatchEnvelope, ToolEnvelope
from horosa_skill.schemas.tools import DispatchInput
from horosa_skill.service import HorosaSkillService


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

    @mcp.tool(name="horosa_dispatch")
    def horosa_dispatch(request: DispatchInput) -> DispatchEnvelope:
        return service.dispatch(request.model_dump(exclude_none=True))

    for definition in TOOL_DEFINITIONS.values():
        input_model = definition.input_model

        def _factory(tool_name: str, model: Any) -> Any:
            def _tool(request: Any) -> ToolEnvelope:
                return service.run_tool(tool_name, request.model_dump(exclude_none=True))

            _tool.__name__ = TOOL_DEFINITIONS[tool_name].mcp_name
            _tool.__doc__ = TOOL_DEFINITIONS[tool_name].description
            _tool.__annotations__ = {"request": model, "return": ToolEnvelope}
            return mcp.tool(name=TOOL_DEFINITIONS[tool_name].mcp_name)(_tool)

        _factory(definition.name, input_model)

    return mcp


def run_mcp_server(settings: Settings, *, transport: str) -> None:
    service = HorosaSkillService(settings)
    server = create_mcp_server(service, settings)
    server.run(transport=transport)
