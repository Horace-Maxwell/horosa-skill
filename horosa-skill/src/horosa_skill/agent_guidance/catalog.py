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
from horosa_skill.engine.registry import TOOL_DEFINITIONS, resolve_tool_name
from horosa_skill.engine.synonyms import TOOL_SYNONYMS, display_name, synonym_scores

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
        "地名：horosa_place_search(query, date) 返回星阙城市库候选（lat/lon/zone，按日期含夏令时）；技法载荷也可直接传 place（唯一命中才自动补，有歧义会拒绝并给候选，让用户选）。CLI：horosa-skill place search 上海 --date 1990-05-18。",
        "省 token：MCP 结果缺省就是阅读视图（正文一遍 + 段索引 + 依据卡），太长时按段裁、warnings 写明 horosa_memory_show 续读调用；response_view='titles' / 'sections' / 'full'（带原始树）。完整结果始终已存档。",
    ],
    "boundaries": [
        "本产品 local-first：结果全部来自本机运行时，不依赖远程数据库或外部服务；缺字段先怀疑本地输入/运行时而非网络服务。",
        "禁止手算这些技法（shell/Python/记忆公式都不行）——只以工具返回的 export_snapshot 为准。",
    ],
}


def technique_index() -> dict[str, dict[str, str]]:
    """技法名索引：{domain: {tool_name: 中文名}}。约 4 KB。

    用在 `tool.unknown` 的 details 里做**自愈式报错**：模型点错名字时当场拿到全部合法名字，
    不必回头去读某个工具的描述。这让 `horosa_tool_run` 的描述得以从 4145 字符降到 1024 以内
    （OpenAI 的 function 描述上限；超了会被拒或截断，而它是精简面下抵达全部技法的唯一通道）。
    带中文名（审计 S-10）：只有注册键时，七政四余 = guolao_chart、邵子参评数 = canping（旁边就是 shaozi 邵子神数），照拼音猜会选错。
    """
    groups: dict[str, dict[str, str]] = {}
    for name, definition in TOOL_DEFINITIONS.items():
        groups.setdefault(str(definition.domain), {})[name] = display_name(name)
    return {domain: dict(sorted(names.items())) for domain, names in sorted(groups.items())}


def _fold(text: object) -> str:
    from horosa_skill.memory.search import normalize

    return normalize(text).strip().lower()


def _summary(name: str, chars: int = 40) -> str:
    first = str(TOOL_DEFINITIONS[name].description or "").split(". ")[0].split("。")[0].strip()
    return first if len(first) <= chars else first[: chars - 1] + "…"


def _named_exactly(text: str) -> list[str]:
    """叫这个名字的技法：同义词表（「八字」「小六壬」「七政四余」，繁简折叠后整词相等）优先，其次导出注册表 / 报告里的中文名。"""
    from horosa_skill.memory.search import tools_named

    wanted = _fold(text)
    if not wanted:
        return []
    hits = sorted(name for name, words in TOOL_SYNONYMS.items()
                  if name in TOOL_DEFINITIONS and any(_fold(word) == wanted for word in (name, *words)))
    return hits or [name for name in tools_named(text) if name in TOOL_DEFINITIONS]


def resolve_technique(name: object) -> tuple[str | None, tuple[str, str] | None]:
    """技法名的宽松解析（审计 S-10）：注册键 / MCP 名之外，也认中文名与同义词（`八字` → bazi_birth、`小六壬` → xiaoliuren）。

    唯一命中才用，并回一条说明 (zh, en)（run_tool 写进 warnings）；多个命中或没有命中返回 (None, None)，由 `tool.unknown` 给候选——
    不替用户在两个技法里挑。"""
    exact = resolve_tool_name(name)
    if exact is not None or not isinstance(name, str):
        return exact, None
    hits = _named_exactly(name)
    if len(hits) != 1:
        return None, None
    key = hits[0]
    return key, (
        f"技法名「{name.strip()}」按 {key}（{display_name(key)}）跑；下次可直接写 {key}。",
        f"Technique name {name.strip()!r} was run as {key} ({display_name(key)}); you can pass {key} directly next time.",
    )


def technique_candidates(name: object, *, limit: int = 5) -> list[dict[str, str]]:
    """点错名字时的候选（最多 5 个，各带中文名与一句话）：整词同名（多义时全列）→ 同义词互含 → 键名近似。"""
    import difflib

    text = str(name or "").strip()
    if not text:
        return []
    picked: list[str] = list(_named_exactly(text))
    picked += [tool for _, tool in synonym_scores(text) if tool in TOOL_DEFINITIONS]
    folded = _fold(text)
    if len(folded) >= 2:
        picked += [tool for tool, words in TOOL_SYNONYMS.items()
                   if tool in TOOL_DEFINITIONS and any(folded in _fold(word) for word in words)]
    bare = text.lower().removeprefix("horosa_")
    picked += difflib.get_close_matches(bare, list(TOOL_DEFINITIONS), n=limit, cutoff=0.6)
    out: list[dict[str, str]] = []
    for tool in dict.fromkeys(picked):
        out.append({"tool_name": tool, "name": display_name(tool), "summary": _summary(tool)})
        if len(out) >= limit:
            break
    return out


def unknown_tool_details(tool_name: object) -> dict[str, Any]:
    """`tool.unknown` 的统一 details（CLI / MCP / service 三处同形）：先给最像的几个候选（带中文名），再给全部合法名字。"""
    candidates = technique_candidates(tool_name)
    details: dict[str, Any] = {"tool_name": tool_name}
    if candidates:
        details["candidates"] = candidates
    details.update({
        "catalog": technique_index(),
        "accepted_forms": "registry key (chart), MCP name (horosa_astro_chart), or an unambiguous Chinese name (八字 / 小六壬)",
        "hint": (
            ("details.candidates 是最像的几个技法；" if candidates else "")
            + "details.catalog 按域列出全部合法技法名（键 → 中文名）；也可跑 `horosa-skill tool list`，或读资源 horosa://catalog/techniques。"
            + (" / details.candidates are the closest techniques;" if candidates else " /")
            + " details.catalog lists every valid technique by domain (key → Chinese name); `horosa-skill tool list` and the"
            " horosa://catalog/techniques resource list them too."
        ),
    })
    return details


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

    result = {
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
    if intent and not include_all and not tool_name:
        # 「先问我」那一调只回随问题变的部分（审计 S-19：以前 6.9 KB 里随问题变的只有 suggested_tools 约 1.6 KB，其余每次照发
        # 9 条 global_rules、安装说明、default_workflow）。全套规则与软件用法在不带参数 / include_all 时给。
        return {
            "ok": True,
            "schema": GUIDANCE_SCHEMA,
            "intent": intent,
            "suggested_tools": suggest_tools_for_intent(intent),
            "next_step": ("挑一个技法后调 horosa_agent_guidance(tool_name=…) 看它要的字段与要问用户的设置，或直接调该技法（闸门会把要问的问出来）；"
                          "拿不准用 horosa_dispatch。全套规则：不带参数调本工具。 / Pick a technique, then call horosa_agent_guidance(tool_name=…) "
                          "for its fields and the settings to ask about, or call it directly (the gate asks what is needed); unsure → horosa_dispatch."),
        }
    if tool_name and not include_all:
        result.pop("usage_help", None)   # 装机 / 用法帮助与单个技法的契约无关（审计 S-19）
        result.pop("default_workflow", None)
    return result


def suggest_tools_for_intent(intent: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """[dispatch 批 v0.50 F2] `intent`（用户原话）→ 最相关的几种技法：一句话说明 + 各自要的字段（几 KB）。

    与 dispatch 同一个确定性路由：点名了技法就是那几个；没点名就是意图类的候选；都没有就按同义词打分。
    v0.49 之前 `intent` 只被原样回显，未命中的 hint 却让客户端去拉 1.4 MB 的 include_all。"""
    from horosa_skill.engine import intents as intent_table
    from horosa_skill.engine.router import route
    from horosa_skill.engine.time_roles import time_role
    from horosa_skill.errors import DispatchResolutionError
    from horosa_skill.schemas.tools import DispatchInput

    try:
        names = route(DispatchInput(query=str(intent))).tools
        reason = "named_or_default"
    except DispatchResolutionError as exc:
        names = list((exc.details or {}).get("candidates") or [])
        reason = str((exc.details or {}).get("reason") or exc.code)
    rows: list[dict[str, Any]] = []
    for row in intent_table.candidate_details(names[:limit]):
        definition = TOOL_DEFINITIONS[row["tool"]]
        required = sorted(name for name, info in definition.input_model.model_fields.items() if info.is_required())
        if {"zone", "lat", "lon"} <= set(required):
            # 地点首选 place（审计 S-06）：一个地名补齐坐标与当日时区；列成必填的 zone / lat / lon 会把模型引去自填。
            required = [name for name in required if name not in {"zone", "lat", "lon"}] + ["place | zone+lat+lon"]
        policy = TOOL_GUIDANCE.get(row["tool"], {})
        rows.append({
            **row,
            "time_role": time_role(row["tool"]),
            "required_fields": required,
            "must_have_context": list(policy.get("must_have_context", []))[:6],
            "match": reason,
        })
    return rows


def assert_guidance_covers_registered_tools() -> None:
    missing = sorted(set(TOOL_DEFINITIONS) - set(TOOL_GUIDANCE))
    extra = sorted(set(TOOL_GUIDANCE) - set(TOOL_DEFINITIONS))
    if missing or extra:
        raise AssertionError(f"agent guidance mismatch: missing={missing}, extra={extra}")
