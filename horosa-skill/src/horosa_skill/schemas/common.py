from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class MemoryRef(BaseModel):
    run_id: str
    tool_name: str
    artifact_path: str
    tool_call_id: int | None = None
    artifact_id: int | None = None


class ToolEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    tool: str
    version: str
    input_normalized: dict[str, Any]
    data: dict[str, Any] = Field(default_factory=dict)
    summary: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    memory_ref: MemoryRef | None = None
    error: ErrorInfo | None = None


class DispatchEnvelope(BaseModel):
    ok: bool
    tool: str = "horosa_dispatch"
    version: str
    selected_tools: list[str] = Field(default_factory=list)
    normalized_inputs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    results: dict[str, ToolEnvelope] = Field(default_factory=dict)
    summary: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    memory_ref: MemoryRef | None = None
    error: ErrorInfo | None = None

