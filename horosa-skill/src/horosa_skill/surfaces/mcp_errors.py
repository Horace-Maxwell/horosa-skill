"""MCP 侧的错误与闸门信封：校验失败、闸门拦截、内部错误都变成带 agent_recovery 的结构化结果，而不是裸 isError。"""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from horosa_skill import __version__
from horosa_skill.agent_guidance import (
    build_validation_recovery,
    validate_agent_preflight,
)
from horosa_skill.errors import ToolValidationError, recovery_for
from horosa_skill.schemas.common import DispatchEnvelope, ErrorInfo, ToolEnvelope


def _validation_error(operation_name: str, tool_name: str | None, exc: ValidationError) -> ToolValidationError:
    """pydantic 校验失败 → 与闸门同形的、可直接转问用户的结构化错误。"""
    errors = [
        {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
        for err in exc.errors(include_url=False)
    ]
    recovery = build_validation_recovery(operation_name=operation_name, errors=errors, tool_name=tool_name)
    return ToolValidationError(
        f"{operation_name} payload failed validation; see details.agent_recovery.",
        code="tool.invalid_payload",
        details={"validation_errors": errors, "agent_recovery": recovery},
    )


def _mcp_error_envelope(exc: ToolValidationError, *, tool_name: str) -> ToolEnvelope:
    """错误也返回一个合规 ToolEnvelope（顶层 code/message/details 镜像保持向后兼容）。

    技法工具/dispatch/tool_run 的返回类型是信封；错误路径若返回裸 dict，一旦声明 outputSchema，
    server 与 client 两侧的出参校验都会失败并被包成协议级 ToolError——整个澄清闸会当场报废。
    """
    details = recovery_for(exc.code, exc.details)  # MCP 面与 run_tool 同一套恢复码表（v0.36.0 B4）
    return ToolEnvelope(
        ok=False,
        tool=tool_name,
        version=__version__,
        input_normalized={},
        error=ErrorInfo(code=exc.code, message=str(exc), details=details),
        code=exc.code,
        message=str(exc),
        details=details,
    )


def _gate_to_envelope(error: dict[str, Any], *, tool_name: str) -> ToolEnvelope:
    """闸门/恢复类错误 dict → 合规 ToolEnvelope（顶层 code/message/details 原样镜像）。

    闸门是最常见的首次返回；它若不合返回类型，声明 outputSchema 后会被两侧出参校验打成协议级
    ToolError，澄清闸直接报废。转换保证「错误也是信封」，同时不动 details.agent_recovery 的内容。
    """
    details = dict(error.get("details") or {})
    code = str(error.get("code") or "tool.error")
    message = str(error.get("message") or "")
    return ToolEnvelope(
        ok=False,
        tool=tool_name,
        version=__version__,
        input_normalized={},
        error=ErrorInfo(code=code, message=message, details=details),
        code=code,
        message=message,
        details=details,
    )


def _gate_to_dispatch_envelope(error: dict[str, Any]) -> DispatchEnvelope:
    details = dict(error.get("details") or {})
    code = str(error.get("code") or "tool.error")
    message = str(error.get("message") or "")
    return DispatchEnvelope(
        ok=False,
        version=__version__,
        error=ErrorInfo(code=code, message=message, details=details),
        code=code,
        message=message,
        details=details,
    )


def _mcp_error_payload(exc: ToolValidationError) -> dict[str, Any]:
    details = recovery_for(exc.code, exc.details)
    return {
        "ok": False,
        "code": exc.code,
        "message": str(exc),
        "details": details,
        "error": {
            "code": exc.code,
            "message": str(exc),
            "details": details,
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
