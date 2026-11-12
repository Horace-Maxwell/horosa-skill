"""HOROSA_TOOLSETS：合法域与别名、解析（含出错时往安全一边倒）、以及本进程将要注册的工具面计划。

不 import MCP SDK：serve 之外（doctor、client config）也读这里，而 SDK 占 CLI 启动时间的三成（tests/test_layering.py）。
"""
from __future__ import annotations

import os
from typing import Any

from horosa_skill.config import Settings
from horosa_skill.engine.registry import FACADE_TOOL_COUNT, TOOL_DEFINITIONS
from horosa_skill.errors import bilingual

# HOROSA_TOOLSETS 合法域 + 别名（v0.36.0 B2：此前拼错一个 token = 零技法且无 tool_run 直呼，客户端只剩门面）。
# 🔴 从注册表派生，不手抄：手抄那份漏了 `export` 与 `knowledge` 两个域，于是 5 个工具
# （export_registry / export_parse / knowledge_registry / knowledge_read / knowledge_xuanshi）
# 经**任何** HOROSA_TOOLSETS 取值都到不了，而 `all` 只给 112 个而非 116 ——「all」不是 all。
# 未知 token 的告警路径也永远不会为它们触发（它们是**合法**域，只是不在白名单里）。
_TOOLSET_DOMAINS: frozenset[str] = frozenset(
    str(definition.domain).lower() for definition in TOOL_DEFINITIONS.values()
)
_TOOLSET_ALIASES: dict[str, frozenset[str]] = {
    "western": frozenset({"astro", "predict", "chart"}),
    "chinese": frozenset({"cn", "shenshu"}),
    "reference": frozenset({"export", "knowledge"}),
    "all": _TOOLSET_DOMAINS,
    "none": frozenset(),
}


def _resolve_toolsets(raw: str) -> dict[str, Any]:
    """`HOROSA_TOOLSETS` 文本 → {requested, effective(set|None), unknown, problem}。

    - 没设 / 点名了全部域（`all`）→ effective=None：完整目录本身，不额外注册 horosa_tool_run；
    - 有合法域 → 只平铺这些域（其余经 horosa_tool_run 可达）；未知 token 丢弃并写进 problem；
    - 🔴 MCP-07：**一个合法 token 都没有** → effective=set()（零平铺技法 + horosa_tool_run），problem 说明原因。
      旧实现在这里回落「全量平铺」：白名单拼错一个字 = 悄悄全开（127 个工具全进上下文），而这正是设白名单想避免的。
      失败往安全的一边倒（精简面），可达性不丢（tool_run 能到任何技法），问题在 stderr / doctor / horosa_agent_guidance 三处可见。
    """
    tokens = [part.strip().lower() for part in f"{raw or ''}".split(",") if part.strip()]
    if not tokens:
        return {"requested": [], "effective": None, "unknown": [], "problem": None}
    effective: set[str] = set()
    unknown: list[str] = []
    saw_none = False
    for token in tokens:
        if token in _TOOLSET_ALIASES:
            effective |= _TOOLSET_ALIASES[token]
            saw_none = saw_none or token == "none"
        elif token in _TOOLSET_DOMAINS:
            effective.add(token)
        else:
            unknown.append(token)
    problem = None
    if unknown:
        fallback = (
            "一个合法值都没有：只注册门面工具 + horosa_tool_run（按名直呼任何技法）"
            if not effective and not saw_none else f"只平铺已识别的域 {sorted(effective)}"
        )
        problem = bilingual(
            f"HOROSA_TOOLSETS 里有不认识的值 {unknown}，已忽略；{fallback}。合法值：{sorted(_TOOLSET_DOMAINS)}，"
            f"别名：{sorted(_TOOLSET_ALIASES)}。",
            f"HOROSA_TOOLSETS has unknown values {unknown} (ignored); "
            + ("none is valid, so only the facade tools + horosa_tool_run are registered" if not effective and not saw_none
               else f"only {sorted(effective)} are listed")
            + f". Valid: {sorted(_TOOLSET_DOMAINS)}; aliases: {sorted(_TOOLSET_ALIASES)}.",
        )
    if effective == set(_TOOLSET_DOMAINS):
        effective_out: set[str] | None = None  # 点名了全部域 = 完整目录（`all` 曾多出一个 tool_run：128）
    else:
        effective_out = effective
    return {"requested": tokens, "effective": effective_out, "unknown": unknown, "problem": problem}


def toolsets_problem() -> str | None:
    """当前进程的 HOROSA_TOOLSETS 有没有问题（给 stderr / doctor / server_profile 用的同一句话）。"""
    return _resolve_toolsets(os.environ.get("HOROSA_TOOLSETS", ""))["problem"]


def surface_plan(settings: Settings) -> dict[str, Any]:
    """本进程将要注册的工具面：注册代码、initialize 说明书与 server_profile 都从这一份算（MCP-07）。"""
    resolved = _resolve_toolsets(os.environ.get("HOROSA_TOOLSETS", ""))
    effective = resolved["effective"]
    compact = bool(settings.mcp_compact)
    listed = [
        name for name, definition in TOOL_DEFINITIONS.items()
        if not compact and (effective is None or definition.domain.lower() in effective)
    ]
    tool_run = compact or effective is not None
    domains = sorted({TOOL_DEFINITIONS[name].domain.lower() for name in listed})
    return {
        "compact": compact,
        "resolved": resolved,
        "technique_tools": listed,
        "tool_run": tool_run,
        "domains": domains,
        "total_tools": FACADE_TOOL_COUNT + len(listed) + (1 if tool_run else 0),
    }


def doctor_warnings() -> list[dict[str, str]]:
    """doctor 的同一句话（码 `config:toolsets_invalid`）：用户在终端里体检时也看得到 HOROSA_TOOLSETS 写错了。"""
    problem = toolsets_problem()
    if not problem:
        return []
    return [{
        "code": "config:toolsets_invalid",
        "detail": problem,
        "fix": "改正 HOROSA_TOOLSETS（或删掉它＝全量）后重启客户端；在那之前技法照样经 horosa_tool_run 可达。",
    }]
