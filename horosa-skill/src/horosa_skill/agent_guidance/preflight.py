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
from horosa_skill.agent_guidance import questions as gate_questions
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
    单中文会让非中文用户面对一整块看不懂的表单。每个问题都是「中文 / English」（data/gate_questions_en.json），
    技法用中文正名（不念注册表键）；长选项表不逐条列（见 questions.present）。
    """
    if not ask_if_missing:
        return (
            "我还缺少这次调用所需的关键参数。请补充必要输入，或明确说明是否按星阙默认设置继续。\n"
            "I still need the key inputs for this call — please provide them, or say to continue with "
            "Xingque defaults."
        )
    label = _tool_label(tool_name)
    facts = [item for item in ask_if_missing if item.get("fact")]
    settings = [item for item in ask_if_missing if not item.get("fact")]
    lines: list[str] = []
    if settings:
        lines += [
            f"调用{label}前需要先确认这些会影响结果的设置：",
            f"Before running {label}, please confirm these result-changing settings:",
        ]
    if facts:
        lines += [
            f"{label}还缺这些只有用户知道的信息（确认默认设置代替不了它们）：",
            f"{label} still needs these facts only the user knows (accepting defaults cannot stand in for them):",
        ]
    for index, item in enumerate([*facts, *settings][:8], start=1):
        question = str(item.get("question") or item.get("field") or "请补充这个参数。")
        options = item.get("options")
        if isinstance(options, list) and options:
            question = f"{question} 可选 / options：{' / '.join(str(option) for option in options)}"
        elif item.get("how_to_change"):
            question = f"{question} {item['how_to_change']}"
        lines.append(f"{index}. {question}")
    if safe_defaults and settings:
        defaults = "; ".join(f"{item.get('field')}={item.get('value')}" for item in safe_defaults[:5])
        lines.append(f"如果你想快速继续，也可以明确说“按星阙默认”，我会使用：{defaults}。")
        lines.append(f"To continue immediately, say “use Xingque defaults” and I will use: {defaults}.")
    return "\n".join(lines)


def _tool_label(tool_name: str) -> str:
    from horosa_skill.engine.synonyms import display_name

    if tool_name in {"dispatch", "horosa_dispatch"}:
        return "自动选技法（dispatch）"
    if tool_name in {"hecan", "horosa_hecan"}:
        return "合参（hecan）"
    name = resolve_tool_name(tool_name) or tool_name
    shown = display_name(name)
    return f"「{shown}」" if shown != name else f"`{name}`"


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


def open_questions(tool_name: str, payload: dict[str, Any], *, confirmed: bool) -> list[dict[str, Any]]:
    """这个技法对这份载荷还开着的问题（已呈现：双语 / 精简选项 / fact 标记）。

    未确认：已答的不问、谓词不成立的不问。已确认：只剩事实（确认标记回答了设置，回答不了事实）。"""
    guidance = build_agent_guidance(tool_name=tool_name)
    policy = guidance["tools"][tool_name]
    items: list[dict[str, Any]] = []
    for question in policy.get("ask_if_missing", []):
        if not isinstance(question, dict):
            continue
        if not gate_questions.applies(tool_name, question, payload) or gate_questions.answered(tool_name, question, payload):
            continue
        if confirmed and not gate_questions.is_fact(tool_name, question):
            continue
        items.append(gate_questions.present(tool_name, question, payload))
    return items


def _filter_provided_questions(ask_if_missing: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    """兼容旧调用点：按载荷过滤（不分技法覆盖）。新代码用 open_questions。"""
    return [
        item for item in ask_if_missing
        if not isinstance(item, dict) or not gate_questions.answered("", item, payload)
    ]


def _block(tool_name: str, ask_if_missing: list[dict[str, Any]], safe_defaults: list[dict[str, Any]],
           do_not_assume: list[str], *, reason: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "ok": False,
        "tool_name": tool_name,
        "enforced": True,
        "code": GATE_FAILURE_CODE,
        "message": (
            "This Horosa tool is protected by the agent guidance gate. "
            "Ask the user for missing result-changing settings first, or pass "
            "`agent_confirmed_settings: true` / `defaults_accepted: true` after explicit confirmation."
            if reason == "missing_agent_confirmation"
            else "Facts only the user knows are missing; a confirmation flag cannot stand in for them. "
            "Ask the user for each item in ask_if_missing and retry with the values."
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
            reason=reason,
        ),
    }
    if extra:
        result.update(extra)
        result["agent_recovery"].update({k: v for k, v in extra.items() if k in ("missing_facts", "example_payload")})
    return result


def validate_agent_preflight(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Return a structured gate result before a calculation tool is allowed to run.

    v0.50：问题逐条按载荷判定（questions.py）——已答的不问、不适用的不问、什么都不缺就放行（mode=nothing_to_confirm）；
    确认标记回答设置，回答不了事实（结果依赖的性别、起课时刻、第二个人、要推的年份）。dispatch / hecan 先路由、
    再按选中技法实际会收到的载荷取问题的并集。
    """

    # MCP 名（horosa_astro_chart）先归一到注册表键：下面「不认识的名字放行」只该放行真·非技法名，
    # 否则换个写法就能绕过闸门。
    tool_name = resolve_tool_name(tool_name) or tool_name
    if tool_name in PREFLIGHT_EXEMPT_TOOLS:
        return {"ok": True, "tool_name": tool_name, "enforced": False}
    override = _clarify_override(tool_name)
    if override is not None:
        return {"ok": True, "tool_name": tool_name, "enforced": False, "mode": override}
    is_hecan = tool_name in {"hecan", "horosa_hecan"}
    # 合参逐技法起盘，走的是 dispatch 同一道闸：一次确认覆盖这次选中的全部技法。
    is_dispatch = is_hecan or tool_name in {"dispatch", "horosa_dispatch"}
    if tool_name not in TOOL_GUIDANCE and not is_dispatch:
        return {"ok": True, "tool_name": tool_name, "enforced": False}

    confirmed = payload.get("agent_confirmed_settings") is True
    defaults_accepted = payload.get("defaults_accepted") is True
    flagged = confirmed or defaults_accepted
    mode = "agent_confirmed_settings" if confirmed else ("defaults_accepted" if defaults_accepted else "nothing_to_confirm")

    if is_dispatch:
        from horosa_skill.agent_guidance.dispatch_gate import dispatch_gate

        return dispatch_gate(tool_name, payload, flagged=flagged, mode=mode, is_hecan=is_hecan, block=_block,
                             open_questions=open_questions)

    open_items = open_questions(tool_name, payload, confirmed=flagged)
    if not open_items:
        return {"ok": True, "tool_name": tool_name, "enforced": True, "mode": mode}
    guidance = build_agent_guidance(tool_name=tool_name)
    policy = guidance["tools"][tool_name]
    return _block(
        tool_name, open_items, [] if flagged else policy.get("safe_defaults", []), policy.get("do_not_assume", []),
        reason="missing_required_facts" if flagged else "missing_agent_confirmation",
    )


def build_clarification_recovery(
    *,
    tool_name: str,
    ask_if_missing: list[dict[str, Any]],
    do_not_assume: list[str],
    reason: str,
) -> dict[str, Any]:
    """闸门之后才发现的「必须问用户」（v0.48.0：地名有歧义 / 找不到）：与闸门同一份 agent_recovery 形状
    （must_ask_user、双语 prompt_to_user、带 options 的 ask_if_missing、retry 三件），只是不给「按星阙默认」——地点没有默认值。"""
    return _agent_recovery(
        tool_name=tool_name, ask_if_missing=ask_if_missing, safe_defaults=[], do_not_assume=do_not_assume, reason=reason,
    )


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


def _validation_questions(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for error in errors:
        if not isinstance(error, dict):
            continue
        loc = error.get("loc")
        field = ".".join(str(part) for part in loc) if isinstance(loc, (list, tuple)) and loc else "(payload)"
        if field in seen:
            continue
        seen.add(field)
        problem = str(error.get("msg") or error.get("type") or "invalid")
        out.append({
            "field": field,
            "question": bilingual(f"`{field}` 缺失或不合法（{problem}）：请提供 / 改正。", f"`{field}` is missing or invalid ({problem}): please provide / fix it."),
            "fact": True,  # 缺的是数据本身：确认标记补不了它
        })
    return out[:8]


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
    if tool_name in TOOL_GUIDANCE or tool_name in {"dispatch", "horosa_dispatch", "hecan", "horosa_hecan"}:
        # v0.50：只问校验真正卡住的字段——旧做法拿空载荷重放整份闸门问卷（用户给过的也重问，17 KB 起）。
        ask_if_missing = _validation_questions(errors)
        safe_defaults = []
        do_not_assume = ["Do not invent the missing values; ask the user for exactly these fields."]
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
