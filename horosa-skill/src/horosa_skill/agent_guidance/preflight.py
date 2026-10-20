"""澄清闸：validate_agent_preflight 判定缺什么、该问用户还是 agent 自己能补（agent_recovery），以及敏感设置表自测。"""
from __future__ import annotations

from typing import Any

from horosa_skill.agent_guidance.base import (
    CONFIRMATION_FIELDS,
    GATE_FAILURE_CODE,
    PREFLIGHT_EXEMPT_TOOLS,
    SENSITIVE_SETTINGS,
    _clarify_override,
)
from horosa_skill.agent_guidance.catalog import build_agent_guidance
from horosa_skill.agent_guidance.tool_table import TOOL_GUIDANCE
from horosa_skill.engine.registry import TOOL_DEFINITIONS, resolve_tool_name
from horosa_skill.errors import bilingual


def run_sensitive_settings_selftests() -> dict[str, Any]:
    """跑闸表自带的 self_tests（match/not_match 行为例）+ coverage 不变量（每个注册工具必须
    有 guidance 策略或在豁免表——新工具漏登记=红）。pytest 与 benchmark 共用本执行器。"""
    failures: list[str] = []
    for case in SENSITIVE_SETTINGS.get("self_tests", []):
        verdict = validate_agent_preflight(str(case["tool"]), dict(case.get("payload") or {}))
        actual = "pass" if verdict.get("ok") else "block"
        if actual != case["expect"]:
            failures.append(f"{case['name']}: expect {case['expect']}, got {actual}")
    unclassified = sorted(set(TOOL_DEFINITIONS) - set(TOOL_GUIDANCE) - PREFLIGHT_EXEMPT_TOOLS)
    if unclassified:
        failures.append(f"未分类工具（既无 guidance 策略也不在豁免表）：{unclassified}")
    return {"ok": not failures, "failures": failures, "cases": len(SENSITIVE_SETTINGS.get("self_tests", []))}


def _prompt_from_guidance(tool_name: str, ask_if_missing: list[dict[str, Any]], safe_defaults: list[dict[str, Any]]) -> str:
    """闸门追问文案（**双语**）。

    这段文本会被 agent 原样转给用户，在支持 elicitation 的客户端还会直接变成原生表单的标题——
    单中文会让非中文用户面对一整块看不懂的表单。技法名词保持中文（它们本就是专名），但每条指引
    都配英文，使任何语言的用户都知道「要我确认什么、怎么快速继续」。
    """
    if not ask_if_missing:
        return (
            "我还缺少这次调用所需的关键参数。请补充必要输入，或明确说明是否按星阙默认设置继续。\n"
            "I still need the key inputs for this call — please provide them, or say to continue with "
            "Xingque defaults."
        )
    lines = [
        f"调用 `{tool_name}` 前需要先确认这些会影响结果的设置：",
        f"Before running `{tool_name}`, please confirm these result-changing settings:",
    ]
    for index, item in enumerate(ask_if_missing[:6], start=1):
        question = str(item.get("question") or item.get("field") or "请补充这个参数。")
        options = item.get("options")
        if isinstance(options, list) and options:
            question = f"{question} 可选 / options：{' / '.join(str(option) for option in options)}"
        lines.append(f"{index}. {question}")
    if safe_defaults:
        defaults = "; ".join(f"{item.get('field')}={item.get('value')}" for item in safe_defaults[:5])
        lines.append(f"如果你想快速继续，也可以明确说“按星阙默认”，我会使用：{defaults}。")
        lines.append(f"To continue immediately, say “use Xingque defaults” and I will use: {defaults}.")
    return "\n".join(lines)


def _agent_recovery(
    *,
    tool_name: str,
    ask_if_missing: list[dict[str, Any]],
    safe_defaults: list[dict[str, Any]],
    do_not_assume: list[str],
    reason: str,
) -> dict[str, Any]:
    return {
        "must_ask_user": True,
        "reason": reason,
        "prompt_to_user": _prompt_from_guidance(tool_name, ask_if_missing, safe_defaults),
        "ask_if_missing": ask_if_missing,
        "safe_defaults": safe_defaults,
        "do_not_assume": do_not_assume,
        "retry_requires_one_of": [
            {"agent_confirmed_settings": True, "meaning": "Use after the user explicitly answered the clarification."},
            {"defaults_accepted": True, "meaning": "Use only after the user explicitly accepted Horosa/Xingque defaults."},
        ],
        "retry_should_include": ["clarification_notes"],
    }


def _filter_provided_questions(ask_if_missing: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    """闸问题按 payload 已提供字段过滤：用户已给的信息不再重复追问。

    条目 field 形如 "date/time" 或 "after23NewDay/timeAlg"（斜杠=同组多字段）；组内字段全部
    已显式提供（非 None）才略过该问。别名 location≈lat/lon，birth/date≈date。
    """
    provided = {key for key, value in payload.items() if value is not None}
    alias_groups = {
        "location": {"lat", "lon", "gpsLat", "gpsLon", "location"},
        "place": {"lat", "lon", "gpsLat", "gpsLon", "location"},
        "birth": {"date"},
    }
    filtered: list[dict[str, Any]] = []
    for item in ask_if_missing:
        if not isinstance(item, dict):
            filtered.append(item)
            continue
        fields = [part.strip() for part in str(item.get("field") or "").split("/") if part.strip()]
        if not fields:
            filtered.append(item)
            continue
        def _has(field: str) -> bool:
            if field in provided:
                return True
            aliases = alias_groups.get(field)
            return bool(aliases and aliases & provided)
        if all(_has(field) for field in fields):
            continue
        filtered.append(item)
    return filtered


def validate_agent_preflight(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Return a structured gate result before a calculation tool is allowed to run."""

    # MCP 名（horosa_astro_chart）先归一到注册表键：下面「不认识的名字放行」只该放行真·非技法名，
    # 否则换个写法就能绕过闸门。
    tool_name = resolve_tool_name(tool_name) or tool_name
    if tool_name in PREFLIGHT_EXEMPT_TOOLS:
        return {"ok": True, "tool_name": tool_name, "enforced": False}
    override = _clarify_override(tool_name)
    if override is not None:
        return {"ok": True, "tool_name": tool_name, "enforced": False, "mode": override}
    is_dispatch = tool_name in {"dispatch", "horosa_dispatch"}
    if tool_name not in TOOL_GUIDANCE and not is_dispatch:
        return {"ok": True, "tool_name": tool_name, "enforced": False}

    confirmed = payload.get("agent_confirmed_settings") is True
    defaults_accepted = payload.get("defaults_accepted") is True
    if confirmed or defaults_accepted:
        return {
            "ok": True,
            "tool_name": tool_name,
            "enforced": True,
            "mode": "agent_confirmed_settings" if confirmed else "defaults_accepted",
        }

    if is_dispatch:
        ask_if_missing = [
            {"field": "target technique", "question": "你想调用哪一种技法？", "options": ["星盘", "大六壬", "奇门", "八字", "紫微", "其他"]},
            {"field": "date/time", "question": "使用当前时间，还是指定时间？"},
            {"field": "location", "question": "地点、经纬度、时区用哪里？"},
            {"field": "question", "question": "这次要问的具体事情是什么？"},
        ]
        safe_defaults = [{"field": "routing", "value": "dispatch selection", "meaning": "仅在用户确认目标和默认设置后自动选择工具"}]
        do_not_assume = ["Do not dispatch to a calculation tool before confirming result-changing settings."]
    else:
        guidance = build_agent_guidance(tool_name=tool_name)
        policy = guidance["tools"][tool_name]
        ask_if_missing = _filter_provided_questions(policy.get("ask_if_missing", []), payload)
        safe_defaults = policy.get("safe_defaults", [])
        do_not_assume = policy.get("do_not_assume", [])
    return {
        "ok": False,
        "tool_name": tool_name,
        "enforced": True,
        "code": GATE_FAILURE_CODE,
        "message": (
            "This Horosa tool is protected by the agent guidance gate. "
            "Ask the user for missing result-changing settings first, or pass "
            "`agent_confirmed_settings: true` / `defaults_accepted: true` after explicit confirmation."
        ),
        "ask_if_missing": ask_if_missing,
        "safe_defaults": safe_defaults,
        "do_not_assume": do_not_assume,
        "confirmation_fields": CONFIRMATION_FIELDS,
        "agent_recovery": _agent_recovery(
            tool_name=tool_name,
            ask_if_missing=ask_if_missing,
            safe_defaults=safe_defaults,
            do_not_assume=do_not_assume,
            reason="missing_agent_confirmation",
        ),
    }


# 记忆 / 报告门面的入参是调用方（AI）自己产的：run_id、ai_answer、format、ai_report……缺了或填错只能 AI 自己补。
# 旧行为一律给 must_ask_user=true + 「请先确认会影响结果的设置：请补充 `ai_answer`」——SKILL.md 又规定见到
# agent_recovery 就停下问用户，于是 agent 会去问用户要它自己该写的解读正文。技法 / dispatch / hecan 的缺参
# 仍然是用户数据（时间、地点、口径），照旧问用户。
AGENT_OWNED_OPERATIONS = frozenset({
    "memory_record_answer", "memory_query", "memory_show",
    "report_template", "report_render", "report_from_tool", "technique_report",
})


def _agent_fixable_recovery(operation: str, errors: list[dict[str, Any]]) -> dict[str, Any]:
    fix_fields: list[dict[str, Any]] = []
    for error in errors:
        if not isinstance(error, dict):
            continue
        loc = error.get("loc")
        field = ".".join(str(part) for part in loc) if isinstance(loc, (list, tuple)) and loc else "(payload)"
        fix_fields.append({"field": field, "problem": str(error.get("msg") or error.get("type") or "invalid")})
    return {
        "must_ask_user": False,
        "kind": "input",
        "reason": "invalid_agent_payload",
        "next_action": "fix_payload_fields_and_retry",
        "fix_fields": fix_fields[:8],
        "agent_note": bilingual(
            f"`{operation}` 的这些字段由调用方（AI）提供：按 fix_fields 补齐或改正后重试，不要拿去问用户。",
            f"These `{operation}` fields are supplied by the caller (the AI): fix them per fix_fields and retry; do not ask the user for them.",
        ),
        "prompt_to_user": "",
        "ask_if_missing": [],
        "safe_defaults": [],
        "do_not_assume": ["Do not invent run IDs or file paths: look them up with horosa_memory_query / `horosa-skill memory query`."],
    }


def build_validation_recovery(
    *,
    operation_name: str,
    errors: list[dict[str, Any]],
    tool_name: str | None = None,
) -> dict[str, Any]:
    """Build a recovery contract for incomplete or invalid payloads.

    Technique / dispatch / hecan inputs are user data (ask the user); memory and report facades take
    caller-owned fields, so their recovery says `must_ask_user: false` and lists what to fix.
    """

    operation = (operation_name or "").removeprefix("horosa_")
    if not tool_name and operation in AGENT_OWNED_OPERATIONS:
        return _agent_fixable_recovery(operation, errors)
    target = tool_name or operation_name
    if tool_name in TOOL_GUIDANCE or tool_name in {"dispatch", "horosa_dispatch"}:
        gate = validate_agent_preflight(tool_name, {})
        ask_if_missing = gate.get("ask_if_missing", [])
        safe_defaults = gate.get("safe_defaults", [])
        do_not_assume = gate.get("do_not_assume", [])
    else:
        missing_fields = []
        for error in errors:
            if not isinstance(error, dict):
                continue
            loc = error.get("loc")
            if isinstance(loc, (list, tuple)) and loc:
                missing_fields.append(".".join(str(part) for part in loc))
        ask_if_missing = [
            {
                "field": field,
                "question": f"请补充 `{field}`，这是 `{operation_name}` 继续执行所需的参数。",
            }
            for field in missing_fields[:8]
        ]
        safe_defaults = []
        do_not_assume = ["Do not invent missing IDs, file paths, run IDs, or user questions."]
    return _agent_recovery(
        tool_name=target,
        ask_if_missing=ask_if_missing,
        safe_defaults=safe_defaults,
        do_not_assume=do_not_assume,
        reason="invalid_or_incomplete_payload",
    )
