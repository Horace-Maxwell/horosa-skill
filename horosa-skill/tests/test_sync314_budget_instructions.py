"""initialize 说明书压版式不丢信息（sync 3.14.0 budget 批：1 999 → 1 848 B，2 048 的预算里腾出 200 B）。

压掉的是版式与同义重复（续行缩进、「· 」、`, ` 分隔的并列技法名、「WHEN TO REACH FOR THIS SERVER / Any request to」、
「local-first」「(offline)」这两个与下一句同义的词）。旧说明书里的每个事实——触发词、技法名、工具名、字段路径、规则句——
逐条列在 `FACTS`，新说明书必须一条不少；任何开关组合 × 任何工具面都不许超过客户端的 2 048 字节截断线。

负向对照（实跑过）：从 `_SERVER_INSTRUCTIONS` 删掉「邵子参评数/」→ test_every_fact_of_the_old_instructions_is_still_there 红在
`['邵子参评数']`；把 `_JEV_CLAIM` 加长 200 B → test_every_flag_combination_on_every_surface_fits_the_client_budget 红在
JEV 开、OTLP 关的全部 9 个工具面（2 057 B 全量 … 2 084 B `toolsets=western`）。
"""
from __future__ import annotations

import itertools
import re

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine.registry import COMPACT_SURFACE_TOOL_COUNT, FULL_SURFACE_TOOL_COUNT
from horosa_skill.surfaces.mcp_server import _SERVER_INSTRUCTIONS, _server_instructions
from horosa_skill.surfaces.toolsets import surface_plan

CLIENT_BUDGET_BYTES = 2048
FULL_TOOLS = FULL_SURFACE_TOOL_COUNT

# v0.50.1 说明书（瘦身前）里的事实，按原文顺序。多词短语按「空白压成一个空格」之后的文本找（折行不算改动）。
FACTS: tuple[str, ...] = (
    "Horosa (星阙)", "术数/占星 computation", "All engines run on this machine", "nothing is sent to a remote service",
    "起盘", "排盘", "起课", "起卦", "算命", "看运势", "合盘", "择日", "卜卦", "explain", "store", "report such a chart",
    "农历/节气/黄历 conversion", "celebrity birth data",
    f"WHAT IT COVERS ({FULL_TOOLS} tools)",
    "Western: natal + derived charts", "20+ predictive systems", "horary 卜卦", "astrocartography", "midpoints",
    "Chinese:", "八字", "紫微斗数", "大六壬", "奇门遁甲", "太乙", "金口诀", "三式合一", "六爻", "河洛理数", "邵子参评数", "一掌经", "小六壬",
    "灵棋经 …",
    "择日 ×10: condition-tree window search (天星/奇门/黄历/八字/太乙/紫微/六壬/三式/七政/印度)",
    "神数 ×14 + 神数正传 (5 schools)", "天文地占", "tarot",
    "Unsure? horosa_agent_guidance(intent=<user's words>) / horosa_dispatch",
    "horosa_hecan runs 2+ techniques on one question → cross-validation (divergence disclosed, never averaged)",
    'Pass place:"上海" (→ coordinates + that date\'s zone)',
    "Cast techniques (奇门/六壬/六爻/塔罗) need the question's moment", "give its date/time/place (dispatch/hecan: context)",
    "agent_guidance.required → ask via details.agent_recovery.prompt_to_user",
    "Settings: retry with agent_confirmed_settings=true (or defaults_accepted=true)",
    "Facts (gender, time, moment, other person) go in the payload; no flag replaces them", "Never self-confirm",
    "Explain ONLY from data.export_snapshot.export_text", "never hand-calculate",
    "Text cut? warnings give the horosa_memory_show call for the rest; read it first",
    "Technique results carry data.technique_card", "quote it after your answer",
    "Runs are stored (horosa_memory_query)", "horosa_report_render writes DOCX/PDF",
    f"HOROSA_MCP_COMPACT=1: {COMPACT_SURFACE_TOOL_COUNT} facade tools instead of {FULL_TOOLS}",
    "horosa_tool_run runs any technique by name", "HOROSA_TOOLSETS=astro,cn limits the groups",
)


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_every_fact_of_the_old_instructions_is_still_there() -> None:
    text = _flat(_SERVER_INSTRUCTIONS)
    missing = [fact for fact in FACTS if fact not in text]
    assert not missing, f"说明书丢了信息：{missing}"


def _plans(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict | None]:
    plans: dict[str, dict | None] = {"full": None, "compact": None}
    for toolsets in ("western", "cn", "astro", "astro,cn,predict,chart", "astro,cn,predict,chart,shenshu", "none", "astr"):
        monkeypatch.setenv("HOROSA_TOOLSETS", toolsets)
        plans[f"toolsets={toolsets}"] = surface_plan(Settings(db_path=None, output_dir=None))
    monkeypatch.delenv("HOROSA_TOOLSETS")
    return plans


def test_every_flag_combination_on_every_surface_fits_the_client_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """既有守卫锁的是「四种开关 × 全量 / 精简」与「工具子集 × 开关全关」；这里补上乘积——子集面的说明书最长，开关一开更长。"""
    sizes = [
        (len(_server_instructions(decision_layer_on=jev, compact=label == "compact", plan=plan, trace_export_on=otlp).encode("utf-8")),
         label, jev, otlp)
        for label, plan in _plans(monkeypatch).items()
        for jev, otlp in itertools.product((False, True), repeat=2)
    ]
    assert len(sizes) == 36
    over = sorted(row for row in sizes if row[0] > CLIENT_BUDGET_BYTES)
    assert not over, f"说明书超出客户端截断线 {CLIENT_BUDGET_BYTES} B：{over}"


def test_numbered_steps_are_single_lines_and_cost_no_indent() -> None:
    """编号条目不折行：续行缩进（`\\n   `）每处白付 3 B，旧版式有 7 处。"""
    assert "\n " not in _SERVER_INSTRUCTIONS
    steps = [line for line in _SERVER_INSTRUCTIONS.splitlines() if re.match(r"\d\. ", line)]
    assert [line[0] for line in steps] == ["1", "2", "3", "4", "5"]


def test_every_variant_anchor_still_matches_the_base_text() -> None:
    """各变体靠 `str.replace` 改写基础说明书：锚点对不上时 replace 静默什么也不做——开着决策层却还说「nothing is sent」，
    或精简面还写全量的工具数。改版式时最容易漏的就是这些锚点。负向对照（实跑过）：把 `_JEV_TRIMS` 第二条的旧文本前面加回「· 」→ 红。"""
    from horosa_skill.surfaces import mcp_server

    anchors = [mcp_server._OFFLINE_CLAIM, mcp_server._FULL_COVERS, mcp_server._FULL_TAIL, *(old for old, _new in mcp_server._JEV_TRIMS)]
    stale = [anchor for anchor in anchors if _SERVER_INSTRUCTIONS.count(anchor) != 1]
    assert not stale, f"锚点在基础说明书里不是恰好出现一次：{stale}"
    shorter = [(old, new) for old, new in mcp_server._JEV_TRIMS if len(new.encode("utf-8")) >= len(old.encode("utf-8"))]
    assert not shorter, f"开着决策层时的裁剪必须真的变短：{shorter}"
