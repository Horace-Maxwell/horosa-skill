"""MCP elicitation：闸门缺设置时在客户端里弹表单问用户（星阙默认 / 我来补 / 取消），并把选择回填进请求；任何失败都不变成新的失败。"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Literal

import anyio
from mcp import types as mcp_types
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, create_model

logger = logging.getLogger("horosa_skill.surfaces.mcp_server")  # 拆分前的日志名，不变


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


def _elicit_timeout_seconds() -> float:
    """`elicitation/create` 的等待预算（秒），0 或负数 = 不设超时。

    🔴 `ctx.elicit()` 本身**没有超时**：客户端声明了 elicitation 能力却把表单丢给一个已经走开的
    用户（或干脆不回应答），这次 tools/call 就永远挂着——占着一个并发名额、一个 JS 子进程配额，
    而调用方那头只看到工具无响应。120 秒够真人读完并回答一张确认表，也远短于各家客户端自己的
    工具超时（Codex 默认 60 秒、Cursor/VS Code 各有默认），所以超时后我们还来得及把**结构化闸门**
    交回去，让 agent 走「问用户」的常规路径，而不是把整个会话拖死。
    """
    raw = os.environ.get("HOROSA_MCP_ELICIT_TIMEOUT_SECONDS", "120").strip()
    try:
        value = float(raw)
    except ValueError:
        return 120.0
    return value


_ELICIT_MAX_QUESTIONS = 6


def _form_field_name(field: Any) -> str:
    name = re.sub(r"[^0-9A-Za-z_]+", "_", f"{field or ''}").strip("_")
    if not name:
        return ""
    if name[0].isdigit():
        name = f"q_{name}"
    return name if name not in {"decision", "notes"} else f"q_{name}"


def _gate_questions(gate_error: dict[str, Any] | None) -> list[dict[str, Any]]:
    details = (gate_error or {}).get("details") or {}
    items = details.get("ask_if_missing") or (details.get("agent_recovery") or {}).get("ask_if_missing") or []
    return [item for item in items if isinstance(item, dict)]


def _gate_elicitation_schema(gate_error: dict[str, Any] | None = None) -> type[BaseModel]:
    """闸门表单（v0.36.0 B3）：三选一 + 每个带 options 的闸问题一个枚举字段（≤6）+ 备注。

    字段只从策略声明的 options 生成，答案也只允许写回策略声明过的 values——表单不是新的自由输入口。
    """
    fields: dict[str, Any] = {
        "decision": (
            Literal[_ELICIT_DEFAULTS, _ELICIT_PROVIDE, _ELICIT_CANCEL],  # type: ignore[valid-type]
            _ELICIT_DEFAULTS,
        ),
    }
    for item in _gate_questions(gate_error):
        options = [str(option) for option in (item.get("options") or []) if str(option).strip()]
        name = _form_field_name(item.get("field"))
        if not options or not name or name in fields:
            continue
        if len(fields) - 1 >= _ELICIT_MAX_QUESTIONS:
            break
        fields[name] = (
            str,
            Field(default="", description=str(item.get("question") or item.get("field") or ""), json_schema_extra={"enum": [*options, ""]}),
        )
    fields["notes"] = (str, "")
    return create_model("HorosaGateDecision", **fields)


def _note_elicitation(gate_error: dict[str, Any], status: str, **extra: Any) -> None:
    """把 elicitation 的去向写进 details.elicitation：agent 看得到「问过没有、为什么没问成」。"""
    details = gate_error.setdefault("details", {})
    if isinstance(details, dict):
        details["elicitation"] = {"status": status, **extra}


def _apply_gate_answers(
    gate_error: dict[str, Any], answers: dict[str, Any] | None
) -> tuple[dict[str, Any], list[str]]:
    """表单逐题答案 → (可写回载荷的字段值, 人话记录)。只认策略声明过的 option；有 values 才写值。"""
    applied: dict[str, Any] = {}
    noted: list[str] = []
    if not answers:
        return applied, noted
    by_name = {_form_field_name(item.get("field")): item for item in _gate_questions(gate_error)}
    for key, answer in answers.items():
        text = f"{answer or ''}".strip()
        item = by_name.get(str(key))
        if not text or item is None:
            continue
        options = [str(option) for option in (item.get("options") or [])]
        if text not in options:
            continue
        field = str(item.get("field") or "")
        noted.append(f"{field}={text}")
        values = item.get("values")
        if isinstance(values, list) and len(values) == len(options) and field and "/" not in field:
            value = values[options.index(text)]
            if value is not None:
                applied[field] = value
    return applied, noted


def _apply_gate_decision(
    payload: dict[str, Any], gate_error: dict[str, Any], decision: str, notes: str, answers: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """纯函数：把表单答案落到载荷（接受默认 / 逐题作答）或闸门错误（用户备注），不碰传输层，可离线测。"""
    applied, noted = _apply_gate_answers(gate_error, answers)
    if decision == _ELICIT_DEFAULTS:
        updated = dict(payload)
        updated.update(applied)
        updated["defaults_accepted"] = True
        note = "user accepted Xingque defaults via MCP elicitation form"
        if noted:
            note += "; answered: " + "; ".join(noted)
        updated["clarification_notes"] = f"{note}; user notes: {notes}" if notes else note
        return updated
    if decision == _ELICIT_PROVIDE and noted:
        # 用户在表单里逐题选了具体设置：这就是确认，写回声明过的值后带 agent_confirmed_settings 重试
        updated = dict(payload)
        updated.update(applied)
        updated["agent_confirmed_settings"] = True
        note = "user answered the clarification form via MCP elicitation: " + "; ".join(noted)
        updated["clarification_notes"] = f"{note}; user notes: {notes}" if notes else note
        return updated
    if notes:
        # 用户选了「补充设置」并给了备注：不代答具体参数，把原话带回给 agent 追问闭环。
        gate_error.setdefault("details", {})["user_notes"] = notes
        recovery = gate_error.get("details", {}).get("agent_recovery")
        if isinstance(recovery, dict):
            recovery["user_notes"] = notes
    return None


async def _maybe_elicit_gate(
    mcp: FastMCP, tool_name: str, payload: dict[str, Any], gate_error: dict[str, Any]
) -> dict[str, Any] | None:
    """Try resolving a tripped clarification gate via native MCP elicitation.

    Returns an updated payload to proceed with, or None to fall back to the structured
    gate error (which may be enriched with the user's form answer in details.user_notes).
    Every exit leaves ``details.elicitation.status`` behind (disabled / unsupported / declined /
    cancelled / answered / defaults / failed): a swallowed exception used to look exactly like
    "the client never supported elicitation" (v0.36.0 A2).
    """
    if not _elicitation_enabled():
        _note_elicitation(gate_error, "disabled")
        return None
    try:
        ctx = mcp.get_context()
        session = ctx.session
        if not session.check_client_capability(
            mcp_types.ClientCapabilities(elicitation=mcp_types.ElicitationCapability())
        ):
            _note_elicitation(gate_error, "unsupported")
            return None
        prompt = (
            gate_error.get("details", {}).get("agent_recovery", {}).get("prompt_to_user")
            or f"调用 {tool_name} 前需要确认会影响结果的设置。"
        )
        budget = _elicit_timeout_seconds()
        result = None
        if budget > 0:
            with anyio.move_on_after(budget):
                result = await ctx.elicit(message=prompt, schema=_gate_elicitation_schema(gate_error))
            if result is None:
                # 超时 = 没人在那头。把结构化闸门原样交回，agent 照常「先问后调」。
                _note_elicitation(gate_error, "timeout", timeout_seconds=f"{budget:g}")
                return None
        else:
            result = await ctx.elicit(message=prompt, schema=_gate_elicitation_schema(gate_error))
        if result.action != "accept" or result.data is None:
            _note_elicitation(gate_error, "declined", action=f"{result.action}")
            return None
        decision = f"{getattr(result.data, 'decision', '') or ''}"
        notes = str(getattr(result.data, "notes", "") or "").strip()
        data_fields = getattr(result.data, "model_dump", None)
        raw_answers = data_fields() if callable(data_fields) else dict(getattr(result.data, "__dict__", {}) or {})
        answers = {k: v for k, v in raw_answers.items() if k not in {"decision", "notes"}}
        updated = _apply_gate_decision(payload, gate_error, decision, notes, answers=answers)
        if updated is not None:
            status = "defaults" if decision == _ELICIT_DEFAULTS else "answered_form"
        else:
            status = "cancelled" if decision == _ELICIT_CANCEL else "answered"
        _note_elicitation(gate_error, status, decision=decision)
        return updated
    except Exception as exc:  # noqa: BLE001 — elicitation must never become a new failure mode
        # 记进 details 就是给调用方的交代；日志用 info（包内 logger.warning 只留给未上抛的真降级）。
        logger.info("MCP elicitation for %s failed: %s", tool_name, exc)
        _note_elicitation(gate_error, "failed", error=f"{type(exc).__name__}: {exc}")
        return None
