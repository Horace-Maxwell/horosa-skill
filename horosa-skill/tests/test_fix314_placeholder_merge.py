"""占位段在缺省阅读视图里合成末尾一段（审计 O-15：mundane 57 段里 25 段、cetian 56 段里 20 段各印一份「本次本地计算结果未返回…」）。

点名段 / 续读 / 全量视图 / 存档不变；只有一个占位段时照旧。
负向对照（实跑过）：_plan_envelope 里 `len(holders) >= 2` 改成永假 → 第一条红。
"""
from __future__ import annotations

from horosa_skill.exports.contract import missing_detail_text
from horosa_skill.result_view import READING, Budget, ViewRequest, shape_result


def _envelope(titles_bodies):
    sections = [{"index": i + 1, "title": t, "body": b} for i, (t, b) in enumerate(titles_bodies)]
    text = "\n\n".join(f"[{s['title']}]\n{s['body']}" for s in sections)
    return {"ok": True, "tool": "mundane", "run_id": "r1", "warnings": [], "summary": [],
            "data": {"export_snapshot": {"technique": {"key": "mundane", "label": "世俗盘"}, "export_text": text, "sections": sections}}}


ROWS = [("起盘信息", "日期：2026-03-20"), ("新月图", missing_detail_text("新月图")), ("年盘概要", "木星主事"),
        ("满月图", missing_detail_text("满月图")), ("日食图", missing_detail_text("日食图"))]


def _reading(env, **kw):
    return shape_result(env, ViewRequest(view=READING, **kw), Budget(max_chars=60000, max_tokens=40000))


def test_placeholders_merge_into_one_trailing_section() -> None:
    out = _reading(_envelope(ROWS))
    snap = out["data"]["export_snapshot"]
    text = snap["export_text"]
    assert text.count("本次本地计算结果") == 1, text
    assert text.rstrip().endswith("不能臆造外部依赖、桌面端服务或不存在的数据。")
    assert "[本次未返回的段]\n新月图、满月图、日食图（3 段）" in text
    assert text.index("[起盘信息]") < text.index("[年盘概要]") < text.index("[本次未返回的段]")
    shown = {row["title"]: row.get("shown") for row in snap["sections"]}
    assert shown == {"起盘信息": "full", "新月图": "merged", "年盘概要": "full", "满月图": "merged", "日食图": "merged"}


def test_named_sections_and_single_placeholder_are_unchanged() -> None:
    named = _reading(_envelope(ROWS), sections=(2,))["data"]["export_snapshot"]["export_text"]
    assert named.startswith("[新月图]\n本次本地计算结果未返回「新月图」")
    single = _envelope(ROWS[:3])
    assert _reading(single)["data"]["export_snapshot"]["export_text"] == single["data"]["export_snapshot"]["export_text"]
