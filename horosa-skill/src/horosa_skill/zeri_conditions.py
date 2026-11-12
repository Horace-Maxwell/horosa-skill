"""择日十技法的条件词表说明与「条件按此理解」回显（深审 F5）。

v0.49 前：黄历择吉的 `chong_shengxiao` 自带判法（缺省 without = 不冲所选肖），客户端再加 `negate: true` 想「避开冲马」，
拿到的正是冲马的日子——schema 与 guidance 都没写条件的极性，结果里也看不到引擎把条件读成了什么。

- 说明表 `data/zeri_condition_meanings.json` 是**生成件**：`scripts/gen_zeri_condition_meanings.py` 跑 horosa-core-js 的
  `zeri_conditions` catalog（只读上游十张注册表的 label / category / defaults / fields / summary），每类一行中英说明 + negate 的规则。
  手改即红（`tests/test_zeri_conditions.py` 有 node 时重生成比对）。guidance 的 `condition_types` 读它。
- 回显：每次择日结果都带 `data.condition_echo`（引擎读法的逐行人话：每叶的 summary、取反、连接词）与 summary 里的一行。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from horosa_skill.errors import bilingual

DATA_PATH = Path(__file__).resolve().parent / "data" / "zeri_condition_meanings.json"
# 说明里逐条列出的自带判法：选项不超过这么多（判法 / 极性 / 模式）；更长的是值域（相位角、星座…），见 agent_guidance 的条件说明。
MAX_LISTED_CHOICES = 4
NEGATE_RULE = (
    "negate: true 把这一项（或整组）取反：不满足它的才算命中。条件自带判法时（如冲煞生肖的 mode：without = 不冲所选肖，缺省；"
    "with = 冲所选肖）先按判法读，再看 negate——「避开冲马」写 mode 缺省、不加 negate；两者都加等于双重否定。连接词 joiner 写在后一项上，"
    "从上到下依次结合（A 或 B 且 C = (A 或 B) 且 C）。",
    "negate: true inverts a leaf (or a whole group): it matches only where the condition fails. When a condition has its own mode "
    "(e.g. chong_shengxiao mode: without = the day does not clash the chosen signs, the default; with = it does), read the mode first, "
    "then negate — to avoid days clashing 马 keep the default mode and no negate; using both is a double negative. A joiner sits on the "
    "later item and items combine top to bottom (A OR B AND C = (A OR B) AND C).",
)


def meaning_lines(entry: dict[str, Any]) -> tuple[str, str]:
    """catalog 的一项 → (中文一行, 英文一行)。"""
    label, category, reads = entry.get("label") or entry["type"], entry.get("category") or "", entry.get("default_reads") or ""
    choices = [c for c in entry.get("choices") or [] if 1 < len(c.get("options") or []) <= MAX_LISTED_CHOICES]
    zh = f"{entry['type']}「{label}」" + (f"（{category}）" if category else "") + "：按参数判定这一天 / 这一刻是否满足"
    en = f"{entry['type']} '{label}'" + (f" ({category})" if category else "") + ": passes when the day / moment meets it as set by params"
    if reads:
        zh += f"；缺省设定读作「{reads}」"
        en += f"; the default params read '{reads}'"
    for choice in choices:
        options_zh = " / ".join(
            f"{o['value']}={o['label']}" + ("（缺省）" if o["value"] == choice.get("default") else "") for o in choice["options"])
        options_en = " / ".join(
            f"{o['value']}={o['label']}" + (" (default)" if o["value"] == choice.get("default") else "") for o in choice["options"])
        zh += f"；{choice['label']} {choice['key']}：{options_zh}"
        en += f"; {choice['key']} ({choice['label']}): {options_en}"
    return zh + "。negate:true = 取反。", en + ". negate:true inverts it."


def build_meanings(catalog: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "_generated_by": "scripts/gen_zeri_condition_meanings.py (horosa-core-js zeri_conditions catalog)",
        "negate_rule": {"zh": NEGATE_RULE[0], "en": NEGATE_RULE[1]},
        "techniques": {
            technique: [{"type": entry["type"], "zh": meaning_lines(entry)[0], "en": meaning_lines(entry)[1]} for entry in entries]
            for technique, entries in sorted(catalog.items())
        },
    }


@lru_cache(maxsize=1)
def meanings() -> dict[str, Any]:
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"techniques": {}}


def zeri_tools() -> tuple[str, ...]:
    return tuple(meanings().get("techniques") or {})


def guidance_block(tool_name: str) -> dict[str, Any] | None:
    rows = (meanings().get("techniques") or {}).get(tool_name)
    if not rows:
        return None
    rule = meanings().get("negate_rule") or {}
    return {
        "negate_rule": bilingual(rule.get("zh", ""), rule.get("en", "")),
        "types": {row["type"]: bilingual(row["zh"], row["en"]) for row in rows},
    }


def echo_summary_line(lines: list[dict[str, Any]], *, limit: int = 360) -> str:
    zh = "；".join(str(line.get("zh") or "").strip() for line in lines)
    en = "; ".join(str(line.get("en") or "").strip() for line in lines)
    if len(zh) > limit:
        zh = zh[:limit] + "…（全文见 data.condition_echo）"
    if len(en) > limit * 2:
        en = en[: limit * 2] + "… (full text in data.condition_echo)"
    return bilingual(f"条件按此理解：{zh}", f"Conditions as read: {en}")
