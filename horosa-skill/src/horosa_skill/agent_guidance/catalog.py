"""技法索引 / 目录、未知工具名的提示，以及汇总一切的 build_agent_guidance。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from horosa_skill.agent_guidance.base import GLOBAL_AGENT_RULES, GUIDANCE_SCHEMA
from horosa_skill.agent_guidance.contracts import _with_common_fields
from horosa_skill.agent_guidance.tool_table import (
    REPORT_AND_MEMORY_GUIDANCE,
    TOOL_GUIDANCE,
)
from horosa_skill.engine.registry import TOOL_DEFINITIONS

# 软件用法帮助语料：随 guidance 返回，供 agent 据实回答「怎么装/怎么用/怎么出报告」类问题。
SOFTWARE_USAGE_HELP: dict[str, list[str]] = {
    "install": [
        "安装：仓库目录执行 `uv run horosa-skill install`（约 730MB 下载，支持断点续传与 HOROSA_RUNTIME_MIRROR 镜像）。",
        "升级：`uv run horosa-skill upgrade`（已最新则秒退不重下）；卸载：`uv run horosa-skill uninstall`（默认只打印将删清单）。",
        "体检：`uv run horosa-skill doctor`（环境/磁盘/端口/文件）；活体验证：`uv run horosa-skill selfcheck`（起盘→存→读回）。",
    ],
    "workflow": [
        "起盘：直接调技法工具（如 horosa_cn_qimen），结果读 data.export_snapshot.export_text 与 sections。",
        "出报告：已有 run_id 时用 horosa_report_render(run_id, format, ai_report)——ai_report 会自动写回记忆；一步到位用 horosa_report_from_tool（注意会重新起盘）。",
        "找历史：horosa_memory_query 按人名/技法/日期/全文组合检索（limit/offset 分页），horosa_memory_show(run_id) 取完整记录。",
        "省 token：技法工具可传 response_view='titles'（只回段标题）或 'sections'（段标题+正文），完整结果始终已存档。",
    ],
    "boundaries": [
        "本产品 local-first：结果全部来自本机运行时，不依赖远程数据库或外部服务；缺字段先怀疑本地输入/运行时而非网络服务。",
        "禁止手算这些技法（shell/Python/记忆公式都不行）——只以工具返回的 export_snapshot 为准。",
    ],
}


def technique_index() -> dict[str, list[str]]:
    """技法名索引：{domain: [tool_name, …]}。约 2.5 KB，只有名字没有描述。

    用在 `tool.unknown` 的 details 里做**自愈式报错**：模型点错名字时当场拿到全部合法名字，
    不必回头去读某个工具的描述。这让 `horosa_tool_run` 的描述得以从 4145 字符降到 1024 以内
    （OpenAI 的 function 描述上限；超了会被拒或截断，而它是精简面下抵达全部技法的唯一通道）。
    """
    groups: dict[str, list[str]] = {}
    for name, definition in TOOL_DEFINITIONS.items():
        groups.setdefault(str(definition.domain), []).append(name)
    return {domain: sorted(names) for domain, names in sorted(groups.items())}


def unknown_tool_details(tool_name: object) -> dict[str, Any]:
    """`tool.unknown` 的统一 details（CLI / MCP / service 三处同形）：当场给出全部合法名字与两种写法的说明。"""
    return {
        "tool_name": tool_name,
        "catalog": technique_index(),
        "accepted_forms": "registry key (chart) or MCP name (horosa_astro_chart)",
        "hint": (
            "details.catalog 按域列出全部合法技法名；也可跑 `horosa-skill tool list`，或读资源 horosa://catalog/techniques。"
            " / details.catalog lists every valid technique by domain; `horosa-skill tool list` and the"
            " horosa://catalog/techniques resource list them too."
        ),
    }


def build_technique_catalog(*, label_chars: int = 72) -> str:
    """技法一行索引（按 domain 分组）——精简 MCP 模式下拼进 tool_run 的 docstring，资源面给全文。

    每行 `name — 描述首句`（截到 label_chars 字），完整输入契约经 horosa_agent_guidance 获取。
    精简面预算 ≤30 KB（verify_mcp_list_budget）：tool_run 用 label_chars=28（约 6 KB），资源用 72。
    """
    groups: dict[str, list[str]] = {}
    for definition in TOOL_DEFINITIONS.values():
        first_sentence = str(definition.description or "").split(". ")[0].split("。")[0].strip()
        if len(first_sentence) > label_chars:
            first_sentence = first_sentence[: label_chars - 1] + "…"
        groups.setdefault(definition.domain, []).append(f"  {definition.name} — {first_sentence}")
    lines = ["Available techniques (call by tool_name; full input contract via horosa_agent_guidance):"]
    for domain in sorted(groups):
        lines.append(f"[{domain}]")
        lines.extend(sorted(groups[domain]))
    return "\n".join(lines)


def build_agent_guidance(
    *,
    tool_name: str | None = None,
    intent: str | None = None,
    include_all: bool = False,
) -> dict[str, Any]:
    """Return machine-readable guidance for agents before they call tools."""

    if include_all:
        tools = {name: _with_common_fields(name, TOOL_GUIDANCE[name]) for name in sorted(TOOL_GUIDANCE)}
    elif tool_name:
        if tool_name not in TOOL_GUIDANCE:
            aliases = {definition.mcp_name: name for name, definition in TOOL_DEFINITIONS.items()}
            mapped = aliases.get(tool_name)
            if mapped is None:
                return {
                    "ok": False,
                    "schema": GUIDANCE_SCHEMA,
                    "error": {
                        "code": "agent_guidance.unknown_tool",
                        "message": f"Unknown tool for guidance: {tool_name}",
                    },
                    "known_tools": sorted(TOOL_GUIDANCE),
                }
            tool_name = mapped
        tools = {tool_name: _with_common_fields(tool_name, TOOL_GUIDANCE[tool_name])}
    else:
        tools = {}

    return {
        "ok": True,
        "schema": GUIDANCE_SCHEMA,
        "intent": intent,
        "global_rules": GLOBAL_AGENT_RULES,
        "default_workflow": [
            "Classify user intent and choose candidate tool.",
            "Call horosa_agent_guidance for that tool when settings are unclear.",
            "Ask the user one concise clarification question with concrete options when guidance says ask_if_missing.",
            "Only call the calculation tool after required context and result-changing settings are clear.",
            "Explain from returned export sections, then store/report if requested.",
        ],
        "tools": tools,
        "report_and_memory": deepcopy(REPORT_AND_MEMORY_GUIDANCE) if include_all else {},
        # 软件用法帮助（防编造语料）：agent 回答「这套工具怎么用/怎么装/怎么出报告」时据此作答，
        # 不要凭通用知识虚构不存在的命令或功能。
        "usage_help": SOFTWARE_USAGE_HELP,
    }


def assert_guidance_covers_registered_tools() -> None:
    missing = sorted(set(TOOL_DEFINITIONS) - set(TOOL_GUIDANCE))
    extra = sorted(set(TOOL_GUIDANCE) - set(TOOL_DEFINITIONS))
    if missing or extra:
        raise AssertionError(f"agent guidance mismatch: missing={missing}, extra={extra}")
