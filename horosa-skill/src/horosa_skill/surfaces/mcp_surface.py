"""MCP 工具面的「外观」：图标、工具注解（只读 / 计算 / 写报告）、alwaysLoad 元数据、结构化输出开关、HOROSA_TOOLSETS 分组与服务器档案、工具标题。"""
from __future__ import annotations

import logging
import os
import re
from inspect import Signature
from typing import Any

from mcp import types as mcp_types

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS

logger = logging.getLogger("horosa_skill.surfaces.mcp_server")  # 拆分前的日志名，不变


# 太极图 SVG（data URI，离线友好）：server 级图标，客户端渲染刚起步、成本近零先埋。
_SERVER_ICON = mcp_types.Icon(
    src=(
        "data:image/svg+xml;utf8,"
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
        "<circle cx='32' cy='32' r='30' fill='%23111827'/>"
        "<path d='M32 2a30 30 0 000 60 15 15 0 010-30 15 15 0 000-30z' fill='%23f9fafb'/>"
        "<circle cx='32' cy='17' r='5' fill='%23111827'/>"
        "<circle cx='32' cy='47' r='5' fill='%23f9fafb'/></svg>"
    ),
    mimeType="image/svg+xml",
    sizes=["64x64"],
)

# Tool annotations（MCP 2025-11-25）：客户端用它决定确认摩擦/自动放行；目录审核要求标注准确。
# 判定口径（如实标注，见 AGENTS.md §4 / LESSONS）：
# - 全部工具 openWorldHint=False（local-first：只打本机 runtime，不出网）。
# - 查询类（registry/knowledge/guidance/memory 读、报告模板）readOnlyHint=True + idempotent=True。
# - 技法计算类 readOnlyHint=False（默认会写一条本地 run 记录，memory_query 可见）、
#   destructiveHint=False（只追加、不改不删）、idempotentHint=False（重复调用会追加新 run 行）。
# - 报告渲染 readOnly=False + idempotent=True（同 run_id+format 原子覆盖同一产物）；
#   report_from_tool 会重新起盘+新 run → idempotent=False。
# - v0.40.0 P0：三个报告类工具会按 output_path **覆盖**磁盘文件（虽已限定在输出目录 / 白名单根内）→ destructiveHint=True，
#   如实标注让客户端对它们保留确认摩擦；memory_record_answer 只追加记录，仍非 destructive。
_ANN_QUERY = mcp_types.ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
_ANN_CALC = mcp_types.ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)
_ANN_RENDER = mcp_types.ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
_ANN_REPORT_WRITE = mcp_types.ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False
)
_ANN_REPORT_FROM_TOOL = mcp_types.ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False
)

_READONLY_TOOL_NAMES = {
    "export_registry",
    "export_parse",
    "knowledge_registry",
    "knowledge_read",
    "ziwei_rules",
    "gua_desc",
    "gua_meiyi",
    "astrodata",
}


def _tool_annotations(tool_name: str) -> mcp_types.ToolAnnotations:
    if tool_name in _READONLY_TOOL_NAMES:
        return _ANN_QUERY
    return _ANN_CALC


# 入口型工具：即使客户端把 MCP 工具全部 deferred（Claude Code 的工具搜索默认行为），这几个也常驻，
# 保证模型永远看得见「怎么问路」和「有哪些技法」。键名是 Claude Code 侧的 _meta 约定。
_ALWAYS_LOAD_TOOLS = {"horosa_agent_guidance", "horosa_dispatch", "horosa_tool_run", "horosa_knowledge_search"}
_ALWAYS_LOAD_META = {"anthropic/alwaysLoad": True}


def _tool_meta(mcp_name: str) -> dict[str, Any] | None:
    return dict(_ALWAYS_LOAD_META) if mcp_name in _ALWAYS_LOAD_TOOLS else None


def _structured_output_enabled() -> bool:
    """是否给工具声明 `outputSchema`（→ 客户端拿到 `structuredContent`）。**默认关**。

    规范鼓励它，但 Claude Code 有过 anthropics/claude-code#25081：服务器带 outputSchema 时**整个
    工具列表静默消失**——该 issue 至今 stale-closed、未确认修复。工具全体消失对本产品是灾难级故障，
    而收益只是「结构化副本」（正文 JSON 一直都在 content 里）。因此默认不开，`HOROSA_OUTPUT_SCHEMA=1`
    给已在自己客户端验证过 `/mcp` 工具计数不掉的用户使用。
    """
    return os.environ.get("HOROSA_OUTPUT_SCHEMA", "0").strip().lower() in {"1", "true", "on"}


def _return_type(annotation: Any) -> Any:
    return annotation if _structured_output_enabled() else Signature.empty


def _selected_toolsets() -> set[str] | None:
    """`HOROSA_TOOLSETS=astro,cn` → 只平铺这些 domain 的技法工具（门面工具永远注册）。

    动机：Claude Code 已用工具搜索解决了全量技法工具的上下文膨胀，但 Cursor 一类客户端仍有较紧的工具数
    上限，全量平铺会被静默截断。分组白名单是注册期过滤，不触碰 service 层。
    `HOROSA_TOOLSETS=none` == 精简模式（等价 HOROSA_MCP_COMPACT=1 的技法面）。
    """
    return _resolve_toolsets(os.environ.get("HOROSA_TOOLSETS", ""))["effective"]


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
    """`HOROSA_TOOLSETS` 文本 → {requested, effective(set|None), unknown}；未知 token 告警丢弃，全空回落全量。"""
    tokens = [part.strip().lower() for part in f"{raw or ''}".split(",") if part.strip()]
    if not tokens:
        return {"requested": [], "effective": None, "unknown": []}
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
    if unknown:
        # 启动期配置通知，无工具调用可告知——不是降级点（verify_silent_degrades 只盯 logger.warning）。
        logger.log(
            logging.WARNING,
            "HOROSA_TOOLSETS 含未知 token %s（合法：%s + 别名 %s）——已忽略；%s",
            unknown, sorted(_TOOLSET_DOMAINS), sorted(_TOOLSET_ALIASES),
            "回落全量平铺" if not effective and not saw_none else "只平铺已识别的域",
        )
    if not effective and not saw_none:
        return {"requested": tokens, "effective": None, "unknown": unknown}
    return {"requested": tokens, "effective": effective, "unknown": unknown}


def _user_knowledge_profile(settings: Settings) -> dict[str, Any]:
    from horosa_skill.knowledge import user as user_knowledge

    summary = user_knowledge.overview(settings, limit=50)
    return {
        "count": summary["count"],
        "entries": [entry["id"] for entry in summary["entries"]],
        "problems": len(summary["problems"]),
        "use": "knowledge=[条目 id / 标题 / #标签 / auto / ?检索词] 传给任一技法，正文在 data.knowledge_context；"
               "查资料用 horosa_knowledge_search，精读用 horosa_knowledge_read(domain=\"user\", key, from_line)",
        "search_index": summary.get("search_index"),
    }


def _server_profile(settings: Settings) -> dict[str, Any]:
    """本进程实际暴露了什么（经 horosa_agent_guidance 可查；_SERVER_INSTRUCTIONS 没预算放它）。"""
    resolved = _resolve_toolsets(os.environ.get("HOROSA_TOOLSETS", ""))
    effective = resolved["effective"]
    compact = bool(settings.mcp_compact)
    registered = (
        0 if compact else sum(1 for d in TOOL_DEFINITIONS.values() if effective is None or d.domain.lower() in effective)
    )
    return {
        "compact": compact,
        "toolsets_requested": resolved["requested"],
        "toolsets_effective": None if effective is None else sorted(effective),
        "toolsets_unknown": resolved["unknown"],
        "technique_tools_registered": registered,
        "tool_run_registered": compact or effective is not None,
        # 结果里给人读的字段用哪种文字（zh-Hans / zh-Hant / zh-Hant-HK）；选项、设置值、段名入参始终是简体。
        "output_script": settings.output_script,
        # 自备知识库：有几条、在哪；计算时传 knowledge=[条目 / #标签 / auto] 才会带进结果（缺省不带）。
        "user_knowledge": _user_knowledge_profile(settings),
        "hint": "技法工具未平铺时用 horosa_tool_run(tool_name=…) 直呼；HOROSA_TOOLSETS 合法域见 toolsets_effective。",
    }


_TITLE_TAIL_PAREN = re.compile(r"[（(][^（()）]*[)）]\s*$")


def _tool_title(tool_name: str) -> str | None:
    """人类可读的工具标题（客户端工具选择器显示它，而不是 `horosa_cn_xiaochengtu` 这种 raw id）。

    工具描述是「中文首句（补充）。English sentence.」的双语形态（registry.py），取中文首句、去掉
    结尾括注即得一个准确的技法名——中文技法名是本产品最大的可读性资产，不该丢在 raw id 后面。
    """
    definition = TOOL_DEFINITIONS.get(tool_name)
    if definition is None:
        return None
    head = str(definition.description or "").split("。", 1)[0].strip()
    if not head:
        return None
    head = _TITLE_TAIL_PAREN.sub("", head).strip()
    if not head or head.isascii():  # 纯英文描述 → 交回 FastMCP 默认（用 name）
        return None
    return head[:24]

