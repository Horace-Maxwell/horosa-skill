"""阅读视图超预算时按优先表放段、单段封顶 35%（审计 O-07：星盘「相位」2 万字整段给，随后「行星」「古典格局」等 11 段一段不给）。

负向对照（实跑过）：_order 恒返回原顺序且去掉封顶 → 两条都红。
"""
from __future__ import annotations

from horosa_skill.result_view import READING, Budget, ViewRequest, shape_result


def _chart():
    rows = [("起盘信息", "日期：2026-01-01\n" * 5), ("宫位宫头", "第1宫：白羊\n" * 12), ("相位", "日合月 0°12′\n" * 1100),
            ("行星", "太阳：本质尊贵\n" * 300), ("古典格局", "格局：日月夹命\n" * 60), ("寿命格局", "寿主：木星\n" * 40)]
    sections = [{"index": i + 1, "title": t, "body": b} for i, (t, b) in enumerate(rows)]
    text = "\n\n".join(f"[{t}]\n{b}" for t, b in rows)
    return {"ok": True, "tool": "chart", "run_id": "r9", "warnings": [], "summary": [],
            "data": {"export_snapshot": {"technique": {"key": "astrochart", "label": "星盘"}, "export_text": text, "sections": sections}}}


BUDGET = Budget(max_chars=24000, max_tokens=16000)


def test_priority_sections_go_in_and_the_huge_table_is_capped() -> None:
    out = shape_result(_chart(), ViewRequest(view=READING), BUDGET)
    snap = out["data"]["export_snapshot"]
    shown = {row["title"]: row.get("shown") for row in snap["sections"]}
    assert shown["行星"] == shown["古典格局"] == shown["寿命格局"] == "full", shown
    assert shown["相位"] in {"partial", "none"}
    text = snap["export_text"]
    assert text.index("[起盘信息]") < text.index("[相位]") < text.index("[行星]")    # 输出仍按文档顺序
    note = " ".join(out["warnings"])
    assert "response_sections=[3], response_offset=" in note


def test_named_sections_are_not_reordered_or_capped() -> None:
    out = shape_result(_chart(), ViewRequest(view=READING, sections=(3,)), BUDGET)
    rows = {row["title"]: row.get("shown") for row in out["data"]["export_snapshot"]["sections"]}
    assert rows["相位"] == "full"     # 点名的段不封顶：超过 35% 照样整段给
