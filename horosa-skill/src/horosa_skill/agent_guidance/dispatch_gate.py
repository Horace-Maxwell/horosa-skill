"""dispatch / hecan 的澄清闸（v0.50.0-dev）：先路由、再按选中技法实际会收到的载荷问问题的并集。

v0.49 之前 dispatch / hecan 的闸门是写死的四问（用哪种技法 / 当前还是指定时间 / 地点 / 问什么），与这次请求
选中哪个技法、载荷里已经有什么无关；带上确认标记就一律放行。于是「手相」先被问四个起盘问题、再拿到路由未命中；
「我和他合不合」确认之后照样起一张单人本命盘。

现在：
1. 载荷不合法 → 放行给校验（校验错误逐字段报，比问卷准）。
2. 路由拒绝（超出范围 / 需要用户挑技法 / 没对上 / 目录里没有）→ 放行给 dispatch 自己的结构化拒绝。
3. 按 engine/dispatch_plan 规划每个技法的载荷 → 缺的事实（起课时刻、第二个人、要推的年份、卦名、性别……）
   无论确认与否都拦；未确认时再加上各技法在**自己那份载荷**上还开着的设置问题。什么都不缺 → 放行。
"""
from __future__ import annotations

from typing import Any, Callable

from pydantic import ValidationError

from horosa_skill.agent_guidance import questions as gate_questions
from horosa_skill.agent_guidance.base import PREFLIGHT_EXEMPT_TOOLS
from horosa_skill.agent_guidance.tool_table import TOOL_GUIDANCE

_MOMENT_KEYS = frozenset({"date", "time", "zone", "lat", "lon", "gpsLat", "gpsLon", "place", "location"})


def _validated(model: Any, payload: dict[str, Any]) -> Any | None:
    from horosa_skill.input_normalization import normalize_request_payload

    try:
        return model.model_validate(payload)
    except ValidationError:
        try:
            return model.model_validate(normalize_request_payload(payload))
        except ValidationError:
            return None
    except Exception:  # noqa: BLE001 - 闸门判定不许因为奇形载荷崩；交给校验去报
        return None


def _moment_only(tool: str, item: dict[str, Any]) -> bool:
    """只问时间 / 地点的问题：由载荷规划的事实缺口（birth_data / question_moment …）统一问，不重复。"""
    groups = gate_questions.answer_groups(tool, str(item.get("field") or ""))
    if not groups:
        return False
    keys = {key.lstrip("@") for group in groups for key in group}
    return keys <= (_MOMENT_KEYS | {"location"})


def dispatch_gate(
    tool_name: str,
    payload: dict[str, Any],
    *,
    flagged: bool,
    mode: str,
    is_hecan: bool,
    block: Callable[..., dict[str, Any]],
    open_questions: Callable[..., list[dict[str, Any]]],
) -> dict[str, Any]:
    from horosa_skill.engine.dispatch_plan import inputs_from_request, missing_facts_recovery, plan_all
    from horosa_skill.engine.registry import resolve_tool_name
    from horosa_skill.engine.router import route
    from horosa_skill.errors import DispatchResolutionError
    from horosa_skill.schemas.tools import DispatchInput, HecanInput

    model = HecanInput if is_hecan else DispatchInput
    request = _validated(model, payload)
    if request is None:
        return {"ok": True, "tool_name": tool_name, "enforced": True, "mode": "deferred_to_validation"}
    explicit = [resolve_tool_name(name) or name for name in (getattr(request, "tools", None) or []) if name]
    if is_hecan and explicit:
        tools = explicit[: max(1, min(int(getattr(request, "max_tools", None) or 5), 8))]
    else:
        try:
            tools = route(request).tools
        except DispatchResolutionError:
            # 超出范围 / 需要挑技法 / 没对上：dispatch 自己给结构化拒绝（带候选与双语追问），先问起盘问题没有意义。
            return {"ok": True, "tool_name": tool_name, "enforced": True, "mode": "routing_refusal"}

    # 闸门只认用户真给了的字段：出生模型的缺省值（timeAlg=0、ziwei 的 gender=True …）不算回答。
    subject = getattr(request, "subject", None)
    birth_model = request.birth or (subject.birth if subject is not None else None)
    explicit_birth = birth_model.model_dump(exclude_none=True, exclude_unset=True) if birth_model is not None else {}
    inputs = inputs_from_request(request, birth_for_run=explicit_birth)
    inputs.birth_fields = explicit_birth
    plans, _warnings = plan_all(tools, inputs)
    facts = missing_facts_recovery(plans)
    items: list[dict[str, Any]] = list(facts["ask_if_missing"]) if facts else []
    seen = {(str(item.get("field")), str(item.get("question"))) for item in items}
    safe_defaults: list[dict[str, Any]] = []
    do_not_assume: list[str] = [
        "Do not substitute birth data for the question's moment, or the server clock for the user's 'now'.",
    ]
    for plan in plans:
        if plan.tool not in TOOL_GUIDANCE or plan.tool in PREFLIGHT_EXEMPT_TOOLS:
            continue
        # 用户原话就是「问什么事」的答案（技法模型没声明 question 字段时，规划不会转发它，但闸门不该再问）。
        view = {**plan.payload, "question": plan.payload.get("question") or inputs.query} if inputs.query else plan.payload
        for item in open_questions(plan.tool, view, confirmed=flagged):
            if _moment_only(plan.tool, item):
                continue
            key = (str(item.get("field")), str(item.get("question")))
            if key in seen:
                for existing in items:
                    if (str(existing.get("field")), str(existing.get("question"))) == key:
                        existing.setdefault("tools", [])
                        if plan.tool not in existing["tools"]:
                            existing["tools"].append(plan.tool)
                continue
            seen.add(key)
            items.append({**item, "tools": [plan.tool]})
        if not flagged:
            policy = TOOL_GUIDANCE[plan.tool]
            safe_defaults.extend(policy.get("safe_defaults", [])[:3])
    if not items:
        return {"ok": True, "tool_name": tool_name, "enforced": True, "mode": mode, "selected_tools": tools}
    has_facts = any(item.get("fact") for item in items)
    extra: dict[str, Any] = {"selected_tools": tools}
    if facts:
        extra["missing_facts"] = facts["missing_facts"]
        extra["example_payload"] = facts["example_payload"]
    return block(
        tool_name, items, safe_defaults[:6], do_not_assume,
        reason="missing_required_facts" if (flagged or (has_facts and all(i.get("fact") for i in items))) else "missing_agent_confirmation",
        extra=extra,
    )
