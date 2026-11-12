"""MCP 结果的阅读视图与模型预算（v0.50.0-dev，horosa_skill/result_view.py）：纯函数层。

台账：docs/LESSONS.md v0.50.0-dev「MCP 结果把原始引擎树当正文交给模型」。整张技法表的体积守卫在
tests/test_result_view_catalogue.py；这里锁规则本身：正文只出现一次、裁剪按段、告警里的续读调用照抄就能用。
"""

from __future__ import annotations

import json
import re

import pytest

from horosa_skill.result_view import (
    FULL,
    READING,
    SECTIONS,
    TITLES,
    Budget,
    ViewRequest,
    cap_free_text,
    compact_json,
    estimate_tokens,
    guidance_index,
    shape_result,
    take_view_request,
)

BIG = Budget(max_tokens=10_000_000, max_chars=10_000_000)
SMALL = Budget(max_tokens=3_000, max_chars=48_000)


def envelope(sections: list[tuple[str, str]], *, run_id: str | None = "run-1", tool: str = "bazi_birth") -> dict:
    rows = [{"index": n + 1, "raw_title": title, "title": title, "included": True, "body": body}
            for n, (title, body) in enumerate(sections)]
    text = "\n\n".join(f"[{title}]\n{body}" for title, body in sections)
    return {
        "ok": True, "tool": tool, "version": "0.50.0", "input_normalized": {"date": "1995-06-03", "clarification_notes": "已确认"},
        "data": {
            "bazi": {"direction": ["大运"] * 5_000},
            "gender": 1,
            "snapshot_text": text,
            "export_snapshot": {"technique": {"key": "bazi", "label": "八字", "preset_sections": ["x"] * 50},
                                "settings_used": {"v": 1}, "sections": rows, "export_text": text,
                                "selected_sections": [t for t, _ in sections], "citation": "c"},
            "technique_card": {"tool": tool, "gate": {"clarification_notes": {"label": "澄清备注", "value": "已确认"}}},
        },
        "summary": ["工具 `bazi_birth` 已返回结构化结果。", "顶层字段：bazi, export_snapshot", "结果包含八字结构。"],
        "warnings": [],
        "memory_ref": {"run_id": run_id} if run_id else None,
    }


def readable_text(result: dict) -> str:
    return result["data"]["export_snapshot"]["export_text"]


def test_reading_view_gives_the_text_once_and_no_raw_tree() -> None:
    raw = envelope([("起盘信息", "日期：1995"), ("四柱", "甲子 乙丑")])
    out = shape_result(raw, ViewRequest(view=READING), SMALL)
    assert readable_text(out) == raw["data"]["export_snapshot"]["export_text"]   # 逐字
    assert "snapshot_text" not in out["data"] and "bazi" not in out["data"]
    assert out["data"]["gender"] == 1                                             # 小值留着
    assert out["data"]["response_view"]["raw_fields_omitted"] == ["bazi"]
    assert 'response_view="full"' in out["data"]["response_view"]["full"]
    assert [row["title"] for row in out["data"]["export_snapshot"]["sections"]] == ["起盘信息", "四柱"]
    assert all("body" not in row for row in out["data"]["export_snapshot"]["sections"])
    assert "preset_sections" not in out["data"]["export_snapshot"]["technique"]
    assert not any(line.startswith("顶层字段") for line in out["summary"])
    # 澄清备注只回显一次（技法卡的闸门记录里有）。
    assert "clarification_notes" not in out["input_normalized"]
    assert out["warnings"] == []
    assert raw["data"]["bazi"], "入参不许被改"


def test_sections_and_titles_views() -> None:
    raw = envelope([("起盘信息", "日期"), ("四柱", "甲子")])
    sections = shape_result(raw, ViewRequest(view=SECTIONS), SMALL)["data"]["export_snapshot"]
    assert "export_text" not in sections and [row["body"] for row in sections["sections"]] == ["日期", "甲子"]
    titles = shape_result(raw, ViewRequest(view=TITLES), SMALL)["data"]["export_snapshot"]
    assert titles["sections"] == [{"index": 1, "title": "起盘信息", "chars": 2}, {"index": 2, "title": "四柱", "chars": 2}]
    assert "export_text" not in titles


def test_full_view_is_the_raw_result() -> None:
    raw = envelope([("起盘信息", "日期")])
    assert shape_result(raw, ViewRequest(view=FULL), SMALL) is raw


def test_cut_by_sections_names_the_exact_follow_up_and_the_follow_up_works() -> None:
    """负向对照：_TextSlot.render 不看额度（整篇都给）→ 估算 token 超预算，第一条断言红（实跑过）。"""
    bodies = [("起盘信息", "日期\n" * 50), ("大运", "大运一行明细\n" * 900), ("流年", "流年一行\n" * 2_000), ("尾段", "结语")]
    raw = envelope(bodies)
    out = shape_result(raw, ViewRequest(view=READING), SMALL)
    text = compact_json(out)
    assert estimate_tokens(text) <= SMALL.max_tokens
    rows = {row["index"]: row for row in out["data"]["export_snapshot"]["sections"]}
    assert rows[1]["shown"] == "full" and rows[4]["shown"] == "full"   # 放得下的整段给（含排在后面的小段）
    assert rows[2]["shown"] == "partial" and rows[3]["shown"] == "none"
    note = next(w for w in out["warnings"] if "模型预算" in w)
    call = re.search(r'horosa_memory_show\(run_id="run-1", response_tool="bazi_birth", response_sections=\[2, 3\], response_offset=(\d+)\)', note)
    assert call, note
    # 照抄续读：从第 2 段的断点接着给，接上的正文与原文逐字一致。
    offset = int(call.group(1))
    more = shape_result(raw, ViewRequest(view=READING, sections=(2, 3), offset=offset), SMALL)
    first_part = readable_text(out).split("[大运]\n", 1)[1].split("\n…（本段未完")[0]
    second_part = readable_text(more).split("[大运]\n", 1)[1].split("\n…（本段未完")[0].split("\n\n[流年]")[0]
    assert first_part + "\n" + second_part.rstrip("\n") == bodies[1][1].rstrip("\n")[: len(first_part) + 1 + len(second_part.rstrip("\n"))]
    assert rows[2]["to"] == offset


def test_select_sections_by_title_including_traditional_script() -> None:
    raw = envelope([("起盘信息", "日期"), ("流年行运", "甲子年")])
    out = shape_result(raw, ViewRequest(view=READING, sections=("流年行運",)), SMALL)
    assert readable_text(out) == "[流年行运]\n甲子年"
    out = shape_result(raw, ViewRequest(view=READING, sections=(9,)), SMALL)
    assert any("没有这些段" in w for w in out["warnings"]) and readable_text(out) == ""


def test_dispatch_results_share_one_budget_and_drop_duplicate_copies() -> None:
    a = envelope([("起盘信息", "八字正文\n" * 1_500)], run_id=None)
    b = envelope([("命盘", "紫微正文\n" * 300)], run_id=None, tool="ziwei_birth")
    raw = {"ok": True, "tool": "horosa_dispatch", "selected_tools": ["bazi_birth", "ziwei_birth"],
           "normalized_inputs": {"bazi_birth": {"x": 1}}, "results": {"bazi_birth": a, "ziwei_birth": b},
           "result_export_contracts": {"bazi_birth": {"sections": ["x"] * 100}}, "summary": [], "warnings": [],
           "memory_ref": {"run_id": "disp-1"}}
    budget = Budget(max_tokens=8_000, max_chars=48_000)
    out = shape_result(raw, ViewRequest(view=READING), budget)
    assert estimate_tokens(compact_json(out)) <= budget.max_tokens
    assert out["normalized_inputs"] == raw["normalized_inputs"] and out["result_export_contracts"] == {}
    # 小的那份整篇给到，大的那份裁，续读指向调度的 run_id。
    assert readable_text(out["results"]["ziwei_birth"]) == b["data"]["export_snapshot"]["export_text"]
    note = next(w for w in out["results"]["bazi_birth"]["warnings"] if "模型预算" in w)
    assert 'horosa_memory_show(run_id="disp-1", response_tool="bazi_birth"' in note


def test_memory_show_reading_view_pages_the_stored_envelope() -> None:
    stored = envelope([("起盘信息", "日期"), ("四柱", "甲子")], run_id=None)
    raw = {"ok": True, "result": {"run_id": "run-9", "artifacts": [
        {"kind": "run_manifest", "tool_name": "_run", "payload": {"tool_calls": ["x"] * 100}},
        {"kind": "tool_result", "tool_name": "bazi_birth", "payload": stored},
        {"kind": "dispatch_result", "tool_name": "horosa_dispatch", "payload": {"results": {"bazi_birth": stored}}},
    ]}, "warnings": []}
    out = shape_result(raw, ViewRequest(view=READING, sections=(2,), tool="bazi_birth"), SMALL)
    manifest, tool_result, dispatch = out["result"]["artifacts"]
    assert "payload" not in manifest
    assert readable_text(tool_result["payload"]) == "[四柱]\n甲子"
    assert dispatch["payload"]["results"]["bazi_birth"]["ok"] is True and "data" not in dispatch["payload"]["results"]["bazi_birth"]
    missing = shape_result(raw, ViewRequest(view=READING, tool="qimen"), SMALL)
    assert any("qimen" in w for w in missing["warnings"])


def test_results_without_reader_text_fall_back_to_a_generic_fit() -> None:
    raw = {"ok": True, "schema": "x", "items": [{"name": "甲", "blob": "长" * 6_000} for _ in range(10)], "warnings": []}
    out = shape_result(raw, ViewRequest(view=READING), SMALL)
    assert estimate_tokens(compact_json(out)) <= SMALL.max_tokens
    assert any('response_view="full"' in w for w in out["warnings"])
    small = {"ok": True, "items": [1, 2]}
    assert shape_result(small, ViewRequest(view=READING), SMALL) == small


def test_failed_envelopes_pass_through() -> None:
    failed = {"ok": False, "tool": "bazi_birth", "data": {}, "code": "x", "warnings": []}
    assert shape_result(failed, ViewRequest(view=READING), SMALL) == failed


def test_view_knobs_are_taken_out_of_every_carrier() -> None:
    args = {"date": "1", "response_view": "titles", "request": json.dumps({"response_sections": [1, "四柱"], "time": "2"}),
            "payload": {"response_offset": "40", "response_tool": "qimen", "x": 1}}
    cleaned, request = take_view_request(args, default_view=READING)
    assert cleaned == {"date": "1", "request": {"time": "2"}, "payload": {"x": 1}}
    assert request == ViewRequest(view=TITLES, sections=(1, "四柱"), offset=40, tool="qimen")
    _, raw_alias = take_view_request({"response_view": "RAW"}, default_view=READING)
    assert raw_alias.view == FULL
    untouched = {"date": "1"}
    assert take_view_request(untouched, default_view=READING)[0] is untouched
    _, bad = take_view_request({"response_view": "everything"}, default_view=READING)
    assert bad.view == READING and "reading / sections / titles / full" in bad.notes[0]


def test_free_text_is_capped_with_a_note() -> None:
    args = {"clarification_notes": "备" * 5_000, "request": {"query": "问" * 9_000, "date": "1"}}
    capped, notes = cap_free_text(args)
    assert len(capped["clarification_notes"]) == 2_000 and len(capped["request"]["query"]) == 4_000
    assert len(notes) == 2 and "5000" in notes[0] and "/" in notes[0]       # 中英两半
    assert len(args["clarification_notes"]) == 5_000                         # 入参不改
    same = {"query": "短"}
    assert cap_free_text(same) == (same, [])


def test_token_estimate_is_conservative_for_cjk() -> None:
    assert estimate_tokens("八字" * 100) == 300
    assert estimate_tokens("abc" * 100) == 100


def test_guidance_index_keeps_what_is_needed_to_pick_a_tool() -> None:
    from horosa_skill.agent_guidance import build_agent_guidance
    from horosa_skill.engine.registry import TOOL_DEFINITIONS

    full = build_agent_guidance(include_all=True)
    index = guidance_index(full)
    assert {row["tool"] for row in index["tools"]} == set(TOOL_DEFINITIONS)
    qimen = next(row for row in index["tools"] if row["tool"] == "qimen")
    assert qimen["mcp_name"] == "horosa_cn_qimen" and qimen["gated"] is True
    assert "qijuMethod" in qimen["settings"] and qimen["confirm"]
    assert 'tool_name=' in index["next"]
    assert estimate_tokens(compact_json(index)) < 20_000 < estimate_tokens(compact_json(full))


@pytest.mark.parametrize("view", [READING, SECTIONS])
def test_one_line_section_is_cut_by_characters(view: str) -> None:
    raw = envelope([("长表", "表" * 20_000)])
    out = shape_result(raw, ViewRequest(view=view), SMALL)
    assert estimate_tokens(compact_json(out)) <= SMALL.max_tokens
    row = out["data"]["export_snapshot"]["sections"][0]
    assert row["shown"] == "partial" and 0 < row["to"] < 20_000
