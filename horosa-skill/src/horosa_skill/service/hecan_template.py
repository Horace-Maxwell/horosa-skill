"""合参模板（horosa_hecan 的结果形状）：逐技法证据 + 口径一致性 + 综合槽。纯函数，不碰服务。

v0.50.0（深审 H-1 / H-2 / H-3 / F16）：
- 每个技法带**有上限的正文节选**（`evidence`：按段从头放，放不下的段列名 + 续读调用）。v0.49 之前只有段名与一个
  「去 memory_show 取全量」的指针，CLI 与存档里没有任何盘面事实，AI 要再读一份 336 KB 的存档才能填模板。
- 少于两个技法算成功时不是交叉印证：`consistency.all_clear = null`、`cross_validation: false`，警告与摘要都明说。
- 每个技法记自己的 `run_id`（新算的 = 本次合参的 run；复用的 = 原来那次），`child_runs` 列全，memory_show 打开合参 run 时据此带上子结果。
- 摘要与 `synthesis_contract.instructions` 中英双语（与其余提示一致）。
"""
from __future__ import annotations

from typing import Any

from horosa_skill.errors import bilingual

HECAN_SCHEMA = "horosa.skill.hecan.v1"
# 每个技法正文节选的上限（字符）。整份正文在存档里；节选只为让模板自带可引用的事实（大小与取舍见 LESSONS v0.50.0-dev 合参条）。
EVIDENCE_CHARS = 4000
MIN_TECHNIQUES = 2

INSTRUCTIONS: tuple[tuple[str, str], ...] = (
    ("先读每个技法的导出正文（techniques[].evidence 是节选；MCP 的 results.<tool> 是阅读视图；没读到的段按 evidence.read_rest 续读），"
     "再填 cross_validation：每技法一条结论，必须绑定该技法真实段落里的事实，不许引用未导出的内容。",
     "Read each technique's exported text first (techniques[].evidence is an excerpt; over MCP results.<tool> is the reading view; "
     "continue unread sections with evidence.read_rest), then fill cross_validation: one conclusion per technique, each tied to facts "
     "in that technique's real sections; never cite content that was not exported."),
    ("convergence 只写多技法**独立**得出的共同判断；一个技法的结论不算共识。",
     "convergence holds only judgements several techniques reach independently; one technique's conclusion is not a consensus."),
    ("divergence 必须逐条披露（哪两个技法、各说什么、可能因口径差异还是体系差异）——**分歧不许平均、不许只挑一边**；无法调和就写无法调和。",
     "divergence must be disclosed item by item (which two techniques, what each says, whether settings or systems explain it); "
     "never average a disagreement or silently pick a side; if it cannot be reconciled, say so."),
    ("consistency.setting_conflicts 非空时，先声明口径冲突再谈结论可比性。",
     "If consistency.setting_conflicts is not empty, state the setting conflict before comparing conclusions."),
    ("cross_validation 为 false（算成的技法少于两个）时，这不是合参：照单技法解读作答，并明说没有交叉印证。",
     "If cross_validation is false (fewer than two techniques succeeded), this is not a cross-check: answer as a single-technique "
     "reading and say plainly that nothing was cross-validated."),
    ("final_answer 先直答用户问题，再给依据与边界；引用口径、教义按 SKILL.md 带出处。",
     "final_answer answers the user's question first, then gives the grounds and limits; cite settings / doctrine with sources per SKILL.md."),
)


def instructions() -> list[str]:
    return [bilingual(zh, en) for zh, en in INSTRUCTIONS]


def _sections(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
    export = data.get("export_snapshot") if isinstance(data.get("export_snapshot"), dict) else {}
    rows = [
        {"index": row.get("index", pos + 1), "title": str(row.get("title") or ""), "body": str(row.get("body") or "")}
        for pos, row in enumerate(export.get("sections") or []) if isinstance(row, dict)
    ]
    if rows:
        return rows
    whole = export.get("export_text") or data.get("snapshot_text")
    if isinstance(whole, str) and whole.strip():
        label = (export.get("technique") or {}).get("label") if isinstance(export.get("technique"), dict) else None
        return [{"index": 1, "title": str(label or envelope.get("tool") or ""), "body": whole}]
    return []


def evidence(envelope: dict[str, Any], *, run_id: str | None, limit: int = EVIDENCE_CHARS) -> dict[str, Any] | None:
    """正文节选：按段从头放，放到上限为止；第一段就超了就截它的前 `limit` 字。放不下的段列出来并给续读调用。"""
    sections = _sections(envelope)
    if not envelope.get("ok") or not sections:
        return None
    tool = str(envelope.get("tool") or "")
    parts: list[str] = []
    shown: list[str] = []
    used = 0
    partial: str | None = None
    for section in sections:
        block = f"[{section['title']}]\n{section['body']}".rstrip()
        if used + len(block) <= limit:
            parts.append(block)
            shown.append(section["title"])
            used += len(block) + 2
            continue
        if not parts:
            parts.append(block[:limit].rstrip() + "…")
            partial = section["title"]
            used = limit
        break
    omitted = [s for s in sections if s["title"] not in shown]
    total = sum(len(s["body"]) for s in sections)
    excerpt: dict[str, Any] = {
        "text": "\n\n".join(parts),
        "complete": not omitted,
        "sections_shown": shown + ([partial] if partial else []),
        "sections_total": len(sections),
        "chars_total": total,
    }
    if omitted:
        indexes = [s["index"] for s in omitted]
        excerpt["sections_not_shown"] = [s["title"] for s in omitted if s["title"] != partial]
        excerpt["note"] = bilingual(
            f"节选：{len(sections)} 段里放了 {len(shown)} 段" + (f"（「{partial}」只放了开头）" if partial else "")
            + f"，上限 {limit} 字；其余段没有放进来，下结论前按 read_rest 读。",
            f"Excerpt: {len(shown)} of {len(sections)} sections" + (f" ('{partial}' only its beginning)" if partial else "")
            + f", capped at {limit} characters; read the rest with read_rest before concluding.",
        )
        if run_id:
            excerpt["read_rest"] = (
                f'horosa_memory_show(run_id="{run_id}", response_tool="{tool}", response_sections={indexes})'
                f" · CLI: horosa-skill memory show {run_id}"
            )
    return excerpt


def headline(envelope: dict[str, Any]) -> str | None:
    summary = [line for line in envelope.get("summary") or [] if isinstance(line, str) and line.strip()]
    return summary[0] if summary else None


def technique_row(name: str, envelope: dict[str, Any], *, run_id: str | None, reused: bool) -> dict[str, Any]:
    data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
    export = data.get("export_snapshot") if isinstance(data.get("export_snapshot"), dict) else {}
    info = export.get("technique") if isinstance(export.get("technique"), dict) else {}
    row: dict[str, Any] = {
        "tool": name,
        "ok": bool(envelope.get("ok")),
        "technique": {"key": info.get("key"), "label": info.get("label")},
        "run_id": run_id,
        "reused": reused,
        "headline": headline(envelope),
        "summary": list(envelope.get("summary") or [])[:4],
        "section_titles": [s.get("title") for s in export.get("sections") or [] if isinstance(s, dict) and s.get("title")],
        "sections_health": {
            "missing_selected_sections": export.get("missing_selected_sections") or [],
            "unknown_detected_sections": export.get("unknown_detected_sections") or [],
        },
        "error": envelope.get("error"),
        "evidence": evidence(envelope, run_id=run_id),
        "evidence_pointer": {"run_id": run_id, "read_with": "horosa_memory_show"},
    }
    return row


def not_cross_validated_warning(succeeded: list[str]) -> str:
    if succeeded:
        return bilingual(
            f"只有 {len(succeeded)} 个技法算成（{'、'.join(succeeded)}）：这不是交叉印证，consistency.all_clear 为 null。"
            "要合参请在 tools 里点名至少两种技法，或补上缺的信息后重试。",
            f"Only {len(succeeded)} technique succeeded ({', '.join(succeeded)}): this is not a cross-check and consistency.all_clear "
            "is null. Name at least two techniques in `tools`, or supply what is missing and retry.",
        )
    return bilingual(
        "没有一个技法算成：这不是交叉印证，consistency.all_clear 为 null；错误见 techniques[].error。",
        "No technique succeeded: this is not a cross-check and consistency.all_clear is null; see techniques[].error.",
    )


def summary_lines(selected: list[str], *, reused: list[str], cross_validation: bool, failed: list[str]) -> list[str]:
    names = "、".join(selected)
    lines = [bilingual(
        f"合参起了 {len(selected)} 个技法（{names}）" + (f"，其中复用此前的运行：{'、'.join(reused)}" if reused else "") + "。",
        f"The cross-check ran {len(selected)} technique{'s' if len(selected) != 1 else ''} ({', '.join(selected)})" + (f"; reused earlier runs: {', '.join(reused)}" if reused else "") + ".",
    )]
    if failed:
        lines.append(bilingual(f"没有算成：{'、'.join(failed)}（见 techniques[].error）。", f"Not computed: {', '.join(failed)} (see techniques[].error)."))
    if cross_validation:
        lines.append(bilingual(
            "这是合参模板，不是终稿：按 synthesis_contract 填写后给出结论，分歧必须披露。",
            "This is a cross-check template, not a finished reading: fill synthesis_contract, then answer; disclose every divergence.",
        ))
    else:
        lines.append(bilingual(
            "算成的技法少于两个，这不是交叉印证：按单技法解读作答，并明说没有交叉印证。",
            "Fewer than two techniques succeeded, so this is not a cross-check: answer as a single-technique reading and say so.",
        ))
    return lines


def results_view_without_duplicates(template: dict[str, Any]) -> dict[str, Any]:
    """MCP：results.<tool> 已是那个技法的阅读视图（正文在里面），techniques[].evidence 的节选正文就不再重复一份。"""
    results = template.get("results") if isinstance(template.get("results"), dict) else {}
    rows = []
    for row in template.get("techniques") or []:
        if isinstance(row, dict) and row.get("tool") in results and isinstance(row.get("evidence"), dict):
            row = {**row, "evidence": {key: value for key, value in row["evidence"].items() if key != "text"}
                   | {"text_in": f"results.{row['tool']}"}}
        rows.append(row)
    return {**template, "techniques": rows}
