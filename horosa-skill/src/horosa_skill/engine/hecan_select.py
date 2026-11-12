"""合参（horosa_hecan）选技法：一次合参至少要两种技法；没点名时按问题领域缺省配一对，而不是借用 dispatch 的单技法路由。

v0.49 之前合参没给 `tools` 就直接用 dispatch 的路由：「看看我的命」路由只给一个技法，合参照样回 `all_clear: true` 的
「合参模板」——一个技法的结论被包装成交叉印证。这里是纯函数（不碰服务），闸门（agent_guidance/dispatch_gate）与
服务（service/api/dispatch.hecan）共用同一份选择：

- 问句点名了两个以上技法 → 用它们。
- 点名了一个 → 按它所在的领域（engine/intents 的意图类，优先问句也命中的那一类）补上该领域缺省对里的另一个，披露。
- 一个都没点名、路由要用户挑（起课 / 命理 / 运势 / 卜卦）→ 该领域的缺省对（`IntentClass.hecan_pair`），披露。
- 择日、超出范围、目录里没有、没对上 → 照 dispatch 的结构化拒绝（择日法各有各的条件词表，不替用户配对）。
- 配不出第二个（合盘、节气这类只有一种技法的领域）→ 只给一个，由合参在结果里明说「这不是交叉印证」。

`tools` 里也可以写此前某次运行的 run_id（32 位十六进制）：那次的结果原样复用，不重算。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from horosa_skill.engine import intents
from horosa_skill.engine.query_text import normalize_query
from horosa_skill.engine.synonyms import display_name
from horosa_skill.errors import DispatchResolutionError, bilingual

RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
# 补位时按这个顺序找「这个技法属于哪个领域」（一个技法可能在几类候选里，如紫微：命理 / 运势）。
_DOMAIN_ORDER: tuple[intents.IntentClass, ...] = (intents.NATAL_CHOICE, intents.DIVINATION, intents.LIFE_TIMING, intents.BUGUA)
MIN_TECHNIQUES = 2


def is_run_id(value: Any) -> bool:
    return isinstance(value, str) and RUN_ID_PATTERN.match(value.strip().lower()) is not None


def split_tools(items: list[str] | None) -> tuple[list[str], list[str]]:
    """`tools` → (技法名, run_id)。顺序各自保留，重复去掉。"""
    names: list[str] = []
    run_ids: list[str] = []
    for item in items or []:
        text = str(item).strip()
        if is_run_id(text):
            if text.lower() not in run_ids:
                run_ids.append(text.lower())
        elif text and text not in names:
            names.append(text)
    return names, run_ids


@dataclass
class HecanSelection:
    tools: list[str]
    warnings: list[str] = field(default_factory=list)
    domain: str | None = None


def _class_for_refusal(exc: DispatchResolutionError) -> intents.IntentClass | None:
    details = exc.details or {}
    candidates = list(details.get("candidates") or [])
    for intent in (*intents.CHOICE_CLASSES, intents.BUGUA):
        if intent.key == details.get("intent_class") and list(intent.candidates) == candidates:
            return intent
    return None


def _domain_for(tool: str, text: str) -> intents.IntentClass | None:
    owning = [intent for intent in _DOMAIN_ORDER if tool in intent.candidates and intent.hecan_pair]
    for intent in owning:
        if intent.matches(text):
            return intent
    return owning[0] if owning else None


def _pair_note(intent: intents.IntentClass, chosen: list[str], *, added: list[str]) -> str:
    names_zh = " + ".join(f"{display_name(tool)}（{tool}）" for tool in chosen)
    names_en = " + ".join(chosen)
    if added and len(added) < len(chosen):
        extra_zh = "、".join(f"{display_name(tool)}（{tool}）" for tool in added)
        return bilingual(
            f"合参至少要两种技法；问句只点名了一种，按「{intent.label_zh}」缺省补上 {extra_zh}，合参组合为 {names_zh}。要别的组合请在 tools 里点名。",
            f"A cross-check needs at least two techniques; the query named one, so {', '.join(added)} was added as the "
            f"{intent.label_en} default ({names_en}). Name the techniques in `tools` to use another combination.",
        )
    return bilingual(
        f"问句没有点名技法，合参按「{intent.label_zh}」缺省选了 {names_zh}。要别的组合请在 tools 里点名。",
        f"The query names no technique; the cross-check uses the {intent.label_en} default: {names_en}. "
        "Name the techniques in `tools` to use another combination.",
    )


def select(request: Any, *, max_tools: int) -> HecanSelection:
    """没给 `tools` 时的合参选择。路由拒绝里配不出缺省对的，原样抛（DispatchResolutionError）。"""
    from horosa_skill.engine.router import route

    text = normalize_query(getattr(request, "query", "") or "")
    try:
        routed = route(request)
    except DispatchResolutionError as exc:
        intent = _class_for_refusal(exc) if exc.code == intents.CODE_CHOICE else None
        if intent is None or not intent.hecan_pair:
            raise
        chosen = list(intent.hecan_pair)[:max_tools]
        return HecanSelection(chosen, [_pair_note(intent, chosen, added=chosen)], intent.key)
    tools = list(routed.tools)[:max_tools]
    warnings = list(routed.warnings)
    if len(tools) >= MIN_TECHNIQUES or max_tools < MIN_TECHNIQUES or not tools:
        return HecanSelection(tools, warnings, routed.intent_class)
    intent = _domain_for(tools[0], text)
    if intent is None:
        return HecanSelection(tools, warnings, routed.intent_class)
    partner = next((tool for tool in intent.hecan_pair if tool not in tools), None)
    if partner is None:
        return HecanSelection(tools, warnings, intent.key)
    chosen = [*tools, partner]
    # 路由自己的「缺省选了 X」说明被合参的说明取代（合参的说明点名了整个组合）；路由本就是缺省选的（带说明）→ 整对都算缺省。
    return HecanSelection(chosen, [_pair_note(intent, chosen, added=chosen if warnings else [partner])], intent.key)
