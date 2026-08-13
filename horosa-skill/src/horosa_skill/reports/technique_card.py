"""技法依据卡 —— 每次技法响应内联的「这一盘是怎么来的」。

与 `reports/builder.py` 的**咨询报告**是两种文档，不要混：
  * 咨询报告 = AI 写正文的解盘结论，`references/reports.md` 明令正文里不许出现 run_id / schema /
    算源这类机器元数据；没有 `ai_report` 时服务端拒绝出终稿（防「假装完成的解读」）。
  * 技法依据卡 = **确定性**的方法与出处：用了什么技法、什么口径、谁算的、产了哪些段、契约干不干净、
    版本链是什么。零 AI 成分，所以可以随每次输出直接给出。

算源口径（唯一容易做错的地方）：**运行期实测优先于声明**。`contracts/technique_provenance.json` 说的是
「这个工具**应该**由谁算」，而 `pan.source` / `jinkou.source` / `data.compute_sources` 是这一次**实际**
由谁算的。ken 端点失败也回 HTTP 200（AGENTS §4），静默回退本地脚手架正是「声明与实测不一致」的形状——
所以两者都记，不一致时如实标 `matches_declaration: false`，不替任何一边圆场。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

TECHNIQUE_CARD_SCHEMA = "horosa.skill.technique_card.v1"

_PROVENANCE_PATH = Path(__file__).resolve().parents[3] / "contracts" / "technique_provenance.json"

# 结果敏感设置：改了它们结论就变，所以必须逐条回显给用户看。
# 键 → (标签, 适用的工具 domain)。`None` = 所有 domain 都适用。
#
# ⚠ 为什么要按 domain 收窄：`BirthInput` 是共享基类，`tradition`/`predictive`/`zodiacal`/`hsys`
# 这些西占字段对**每个**继承它的技法都会带着默认值出现在 `input_normalized` 里——照单全印，
# 会给灵棋经这种纯干支技法印出「黄道制=0；分宫制=1」，读者会以为这盘真按那个口径算过。
# 卡片的全部价值就是「如实说明这一盘是怎么来的」，印一条没参与计算的口径比不印更糟。
#
# 晚子时双开关只在 hour == 23 生效，但对中式技法**照样回显**——用户换过开关时报告里没有这一行，
# 等于把「为什么两次结果不同」这个问题藏起来（AGENTS §10）。
_CN_DOMAINS = frozenset({"cn", "shenshu"})
_ASTRO_DOMAINS = frozenset({"astro", "predict", "chart"})
_RESULT_SENSITIVE_FIELDS: tuple[tuple[str, str, frozenset[str] | None], ...] = (
    ("after23NewDay", "晚子时·日柱开关", _CN_DOMAINS),
    ("lateZiHourUseNextDay", "晚子时·时干开关", _CN_DOMAINS),
    ("guirengType", "贵人法", _CN_DOMAINS),
    ("timeAlg", "时间算法", None),
    ("pdMethod", "主限法", _ASTRO_DOMAINS),
    ("tradition", "古典口径", _ASTRO_DOMAINS),
    ("predictive", "预测数据", _ASTRO_DOMAINS),
    ("zodiacal", "黄道制", _ASTRO_DOMAINS),
    ("hsys", "分宫制", _ASTRO_DOMAINS),
    ("gender", "性别", None),
    ("school", "流派", None),
    ("profile", "传本", None),
)
# 闸门状态：调用方声称「设置已与用户确认」还是「接受默认」，是报告里最该留痕的一项。
_GATE_FIELDS: tuple[tuple[str, str], ...] = (
    ("agent_confirmed_settings", "已与用户确认设置"),
    ("defaults_accepted", "用户接受默认值"),
    ("clarification_notes", "澄清备注"),
)


@lru_cache(maxsize=1)
def load_provenance_table() -> dict[str, Any]:
    try:
        return json.loads(_PROVENANCE_PATH.read_text(encoding="utf-8")).get("tools") or {}
    except (OSError, json.JSONDecodeError, ValueError):
        # 声明表读不到不是致命错：卡片退到「只报实测」，绝不因为一份元数据文件让技法调用失败。
        return {}


def _measured_compute(response_data: dict[str, Any]) -> dict[str, Any]:
    """从**这一次的响应**里读真实算源。声明表说应该是谁，这里说实际是谁。"""
    measured: dict[str, str] = {}
    pan = response_data.get("pan")
    if isinstance(pan, dict) and isinstance(pan.get("source"), str):
        measured["pan"] = pan["source"]
    jinkou = response_data.get("jinkou")
    if isinstance(jinkou, dict) and isinstance(jinkou.get("source"), str):
        measured["jinkou"] = jinkou["source"]
    sources = response_data.get("compute_sources")
    if isinstance(sources, dict):
        for key, value in sources.items():
            if isinstance(value, str):
                measured[str(key)] = value
    return measured


def _settings_used(
    input_normalized: dict[str, Any], response_data: dict[str, Any], domain: str | None
) -> dict[str, Any]:
    used: dict[str, Any] = {}
    for field, label, domains in _RESULT_SENSITIVE_FIELDS:
        if domains is not None and (domain or "") not in domains:
            continue
        if field in input_normalized and input_normalized[field] is not None:
            used[field] = {"label": label, "value": input_normalized[field]}
    # 岁差/恒星黄道：西占与印占**字段名不同**（AGENTS §4），必须分别读，且不许硬编码岁差名。
    chart = response_data.get("chart") if isinstance(response_data.get("chart"), dict) else {}
    if isinstance(chart.get("siderealAyanamsa"), (str, int, float)):
        used["siderealAyanamsa"] = {"label": "岁差（西占）", "value": chart["siderealAyanamsa"]}
    if isinstance(chart.get("siderealModeKey"), (str, int, float)):
        used["siderealModeKey"] = {"label": "岁差模式（印占）", "value": chart["siderealModeKey"]}
        if chart.get("ayanamsaValue") is not None:
            used["ayanamsaValue"] = {"label": "岁差值（印占）", "value": chart["ayanamsaValue"]}
    return used


def _gate_state(input_normalized: dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for field, label in _GATE_FIELDS:
        if field in input_normalized and input_normalized[field] not in (None, ""):
            state[field] = {"label": label, "value": input_normalized[field]}
    return state


def _sections_health(export_snapshot: dict[str, Any]) -> dict[str, Any]:
    detected = export_snapshot.get("section_titles_detected")
    selected = export_snapshot.get("selected_sections")
    missing = export_snapshot.get("missing_selected_sections") or []
    unknown = export_snapshot.get("unknown_detected_sections") or []
    return {
        "selected_count": len(selected) if isinstance(selected, list) else 0,
        "detected_count": len(detected) if isinstance(detected, list) else 0,
        "titles": list(detected) if isinstance(detected, list) else [],
        "missing_selected_sections": list(missing),
        "unknown_detected_sections": list(unknown),
        # 「干净」= 该出的都出了、出的都认识。这是导出契约的验收判据（AGENTS §8）。
        "contract_clean": not missing and not unknown,
        "format_source": export_snapshot.get("format_source"),
    }


def build_technique_card(
    *,
    tool_name: str,
    technique_key: str | None,
    input_normalized: dict[str, Any],
    response_data: dict[str, Any],
    skill_version: str,
    envelope_schema: str,
    domain: str | None = None,
    runtime_version: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """构造技法依据卡。纯函数：只读入参，不发请求、不算盘。"""
    from horosa_skill.exports.registry import get_technique_info

    export_snapshot = response_data.get("export_snapshot")
    export_snapshot = export_snapshot if isinstance(export_snapshot, dict) else {}
    technique_info = get_technique_info(technique_key) if technique_key else None

    declared = load_provenance_table().get(tool_name) or {}
    measured = _measured_compute(response_data)
    declared_engines = list(declared.get("engines") or [])
    # 一致性判据：声明了引擎名就要在实测值里出现；实测为空（如离线/无该字段）不算矛盾，标 unknown。
    if not measured:
        matches: bool | None = None
    elif declared_engines:
        matches = any(value in declared_engines for value in measured.values())
    else:
        matches = None

    return {
        "schema": TECHNIQUE_CARD_SCHEMA,
        "tool": tool_name,
        "technique": {
            "key": technique_key,
            "label": (technique_info or {}).get("label") if technique_info else None,
        },
        "compute": {
            "declared_class": declared.get("compute_class"),
            "declared_engines": declared_engines,
            "declared_endpoints": list(declared.get("endpoints") or []),
            "measured": measured,
            "matches_declaration": matches,
            "notes": declared.get("notes"),
        },
        "settings": _settings_used(input_normalized, response_data, domain),
        "gate": _gate_state(input_normalized),
        "sections": _sections_health(export_snapshot),
        "versions": {
            "skill": skill_version,
            "tool_envelope_schema": envelope_schema,
            "export_settings": export_snapshot.get("bundle_version"),
            "runtime": runtime_version,
        },
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def render_technique_card_markdown(card: dict[str, Any]) -> str:
    """把卡片渲染成一段可直接贴进回答尾部的 Markdown。"""
    technique = card.get("technique") or {}
    label = technique.get("label") or technique.get("key") or card.get("tool")
    compute = card.get("compute") or {}
    sections = card.get("sections") or {}
    versions = card.get("versions") or {}

    measured = compute.get("measured") or {}
    if measured:
        engines = "、".join(f"{key}={value}" for key, value in sorted(measured.items()))
    else:
        engines = "、".join(compute.get("declared_engines") or []) or (compute.get("declared_class") or "未标注")
    lines = [
        f"**本次所用技法**：{label}（`{card.get('tool')}`）",
        f"- 算源：{engines}"
        + ("" if compute.get("matches_declaration") is not False else "　⚠️ 与声明不一致，请核对"),
    ]
    settings = card.get("settings") or {}
    if settings:
        rendered = "；".join(f"{item['label']}={item['value']}" for item in settings.values())
        lines.append(f"- 口径：{rendered}")
    gate = card.get("gate") or {}
    if gate:
        rendered = "；".join(f"{item['label']}={item['value']}" for item in gate.values())
        lines.append(f"- 设置确认：{rendered}")
    health = "干净" if sections.get("contract_clean") else "有缺口"
    detail = ""
    if sections.get("missing_selected_sections"):
        detail += f"，缺 {'/'.join(sections['missing_selected_sections'])}"
    if sections.get("unknown_detected_sections"):
        detail += f"，多出 {'/'.join(sections['unknown_detected_sections'])}"
    lines.append(f"- 段落：{sections.get('detected_count', 0)} 段，导出契约{health}{detail}")
    version_bits = [f"skill {versions.get('skill')}"]
    if versions.get("export_settings") is not None:
        version_bits.append(f"导出契约 v{versions['export_settings']}")
    if versions.get("runtime"):
        version_bits.append(f"runtime {versions['runtime']}")
    lines.append(f"- 版本：{'　·　'.join(version_bits)}")
    refs = card.get("refs") or {}
    if refs.get("run_id"):
        lines.append(f"- 本次运行：`{refs['run_id']}`")
    return "\n".join(lines)


TECHNIQUE_REPORT_SCHEMA = "horosa.skill.technique_report.v1"
# 会话里最值得报出来的一致性问题：同一次问答跨技法用了**不同**的口径。
# 晚子时开关不同 = 两张盘的日柱/时干可能就不是同一天，结论根本不可比——而这在多技法交叉时
# 完全不会有任何报错，只会安静地给出两套说法。
_CROSS_RUN_CRITICAL_FIELDS = ("after23NewDay", "lateZiHourUseNextDay", "guirengType", "timeAlg")


def build_technique_report(
    *,
    cards: list[dict[str, Any]],
    scope: str,
    scope_id: str | None,
    title: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """把一张或多张技法卡汇总成一份可渲染的技法依据报告。

    `scope` = "run"（单次调用）或 "group"（整个会话）。会话态额外做**口径冲突**检查。
    """
    conflicts: list[dict[str, Any]] = []
    if len(cards) > 1:
        for field in _CROSS_RUN_CRITICAL_FIELDS:
            seen: dict[str, list[str]] = {}
            for card in cards:
                item = (card.get("settings") or {}).get(field)
                if not item:
                    continue
                seen.setdefault(f"{item.get('value')}", []).append(str(card.get("tool")))
            if len(seen) > 1:
                label = next(
                    ((c.get("settings") or {})[field]["label"] for c in cards if (c.get("settings") or {}).get(field)),
                    field,
                )
                conflicts.append({
                    "field": field,
                    "label": label,
                    "values": {value: tools for value, tools in sorted(seen.items())},
                    "why_it_matters": "同一会话内该口径不一致 —— 各技法的结论建立在不同前提上，不可直接互证。",
                })

    techniques = [
        {
            "tool": card.get("tool"),
            "technique": card.get("technique"),
            "compute": card.get("compute"),
            "sections": {
                key: value for key, value in (card.get("sections") or {}).items() if key != "titles"
            },
            "settings": card.get("settings"),
            "gate": card.get("gate"),
            "refs": card.get("refs"),
        }
        for card in cards
    ]
    unclean = [t["tool"] for t in techniques if not (t["sections"] or {}).get("contract_clean")]
    mismatched = [t["tool"] for t in techniques if (t["compute"] or {}).get("matches_declaration") is False]
    return {
        "schema": TECHNIQUE_REPORT_SCHEMA,
        "title": title or ("会话技法依据报告" if scope == "group" else "技法依据报告"),
        "scope": scope,
        "scope_id": scope_id,
        "technique_count": len(techniques),
        "techniques": techniques,
        "cards": cards,
        "consistency": {
            "setting_conflicts": conflicts,
            "export_contract_unclean": unclean,
            "compute_mismatched": mismatched,
            # 「全绿」只有在三项都空时才成立——别把「没检查」说成「没问题」。
            "all_clear": not conflicts and not unclean and not mismatched,
        },
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def render_technique_report_markdown(report: dict[str, Any]) -> str:
    lines = [f"# {report.get('title')}", ""]
    scope = report.get("scope")
    lines.append(
        f"- 范围：{'整个会话' if scope == 'group' else '单次运行'}"
        + (f"（`{report.get('scope_id')}`）" if report.get("scope_id") else "")
    )
    lines.append(f"- 技法数：{report.get('technique_count')}")
    lines.append(f"- 生成时间：{report.get('generated_at')}")
    lines.append("")

    consistency = report.get("consistency") or {}
    lines.append("## 一致性检查")
    lines.append("")
    if consistency.get("all_clear"):
        lines.append("本报告涵盖的技法口径一致，导出契约干净，算源与声明相符。")
    else:
        for conflict in consistency.get("setting_conflicts") or []:
            detail = "；".join(f"{value} ← {'、'.join(tools)}" for value, tools in conflict["values"].items())
            lines.append(f"- ⚠️ **{conflict['label']} 口径不一致**：{detail}。{conflict['why_it_matters']}")
        if consistency.get("export_contract_unclean"):
            lines.append(f"- ⚠️ 导出契约有缺口：{'、'.join(consistency['export_contract_unclean'])}")
        if consistency.get("compute_mismatched"):
            lines.append(f"- ⚠️ 实测算源与声明不符：{'、'.join(consistency['compute_mismatched'])}")
    lines.append("")

    lines.append("## 技法一览")
    lines.append("")
    lines.append("| 技法 | 工具 | 算源 | 段数 | 导出契约 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in report.get("techniques") or []:
        technique = item.get("technique") or {}
        compute = item.get("compute") or {}
        sections = item.get("sections") or {}
        measured = compute.get("measured") or {}
        engines = "、".join(sorted(measured.values())) or "、".join(compute.get("declared_engines") or []) \
            or (compute.get("declared_class") or "—")
        clean = "干净" if sections.get("contract_clean") else "有缺口"
        lines.append(
            f"| {technique.get('label') or technique.get('key') or '—'} | `{item.get('tool')}` | "
            f"{engines} | {sections.get('detected_count', 0)} | {clean} |"
        )
    lines.append("")

    for card in report.get("cards") or []:
        technique = card.get("technique") or {}
        lines.append(f"## {technique.get('label') or technique.get('key') or card.get('tool')}")
        lines.append("")
        lines.append(render_technique_card_markdown(card))
        compute = card.get("compute") or {}
        if compute.get("notes"):
            lines.append(f"- 算源说明：{compute['notes']}")
        titles = (card.get("sections") or {}).get("titles") or []
        if titles:
            lines.append(f"- 产出段目录：{'、'.join(titles)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
