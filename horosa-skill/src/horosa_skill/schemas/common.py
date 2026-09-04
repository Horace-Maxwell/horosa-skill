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
    trace_id: str | None = None
    group_id: str | None = None


# tool envelope 的 schema 版本。**独立于包版本**（docs/DATA_CONTRACTS.md 的「版本面」）。
# v0.7.0（v0.27.0）：每个技法响应的 `data` 里恒定多一个 `technique_card`（技法依据卡：算源 / 口径 /
#   段落健康度 / 版本链）。加键是向后兼容的，但下游可以据此**依赖**它存在，所以要升次版本号。
# 以前这个数字只活在文档里、没人能对它做断言；现在它是常量，verify_docs_sync 逐字核对两边一致。
# v0.8.0（v0.36.0）：`export_snapshot.sections[*]` **不再带 `data` 键**——此前每段都复制整份引擎对象
#   （qimen 5 MB / india_chart 101 MB，正文仅几 KB）。引擎对象只在 `data.<key>`（pan/chart/liureng…）
#   出现一次；段形状固定为 {index, raw_title, title, included, body}。删键是破坏性变更 → 升次版本号。
TOOL_ENVELOPE_SCHEMA_VERSION = "0.8.0"


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
    trace_id: str | None = None
    group_id: str | None = None
    error: ErrorInfo | None = None
    # 顶层错误镜像（可选，仅错误时出现）：MCP 侧的失败载荷历史上是一个 5 键裸 dict，与本信封不同形，
    # 客户端要按两种形状分别解析，也让 outputSchema 无法启用。现在错误也返回本信封，同时保留这三个
    # 顶层键，使既有按 `code`/`message`/`details` 读的调用方（CLI、旧 agent 提示词）零改动。
    code: str | None = None
    message: str | None = None
    details: dict[str, Any] | None = None


class DispatchEnvelope(BaseModel):
    ok: bool
    tool: str = "horosa_dispatch"
    version: str
    selected_tools: list[str] = Field(default_factory=list)
    normalized_inputs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    results: dict[str, ToolEnvelope] = Field(default_factory=dict)
    result_export_contracts: dict[str, dict[str, Any]] = Field(default_factory=dict)
    summary: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    memory_ref: MemoryRef | None = None
    trace_id: str | None = None
    group_id: str | None = None
    error: ErrorInfo | None = None
    # 顶层错误镜像，与 ToolEnvelope 同义（见那里的说明）。
    code: str | None = None
    message: str | None = None
    details: dict[str, Any] | None = None
