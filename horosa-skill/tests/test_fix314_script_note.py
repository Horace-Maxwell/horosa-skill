"""简体输出里夹的繁体条文要说一声；段名按简体给（审计 O-16）。

一掌经条文 554 个繁体字、正传 83、河洛 28；策天段名「[命宮]」而正文「宫名：命宫」。条文是引文，照原书不折；
export_snapshot.script_note 说一句，阅读视图带上；视图里段名折简体（繁体输出在出口再统一转），点「命宫」也对得上「命宮」段。
负向对照（实跑过）：_quotes_traditional 恒 False → 第一条红；_plan_envelope 不折段名 → 第二条红。
"""
from __future__ import annotations

from pathlib import Path

from horosa_skill.result_view import READING, Budget, ViewRequest, shape_result
from horosa_skill.service.export import SCRIPT_NOTE, _quotes_traditional
from test_local_js_tools import requires_runtime

QUOTE = "父母親掌權，主導性強，兄弟姊妹關係親密，為人處事謹慎，與長輩緣份深厚，財運亨通，晚歲榮華。" * 2


def test_note_fires_on_traditional_quotes_only() -> None:
    assert _quotes_traditional(QUOTE)
    assert not _quotes_traditional("父母亲掌权，主导性强。" * 10)


def _envelope():
    sections = [{"index": 1, "title": "命宮", "body": "宫名：命宫"}, {"index": 2, "title": "夫妻宮", "body": "宫名：夫妻宫"}]
    text = "[命宮]\n宫名：命宫\n\n[夫妻宮]\n宫名：夫妻宫"
    return {"ok": True, "tool": "cetian", "run_id": "r1", "warnings": [], "summary": [],
            "data": {"export_snapshot": {"technique": {"key": "cetian", "label": "策天飞星"}, "export_text": text,
                                         "sections": sections, "script_note": SCRIPT_NOTE}}}


def test_view_titles_follow_simplified_and_carry_the_note() -> None:
    budget = Budget(max_chars=60000, max_tokens=40000)
    snap = shape_result(_envelope(), ViewRequest(view=READING), budget)["data"]["export_snapshot"]
    assert snap["export_text"] == "[命宫]\n宫名：命宫\n\n[夫妻宫]\n宫名：夫妻宫"
    assert [row["title"] for row in snap["sections"]] == ["命宫", "夫妻宫"] and snap["script_note"] == SCRIPT_NOTE
    picked = shape_result(_envelope(), ViewRequest(view=READING, sections=("夫妻宫",)), budget)
    assert picked["data"]["export_snapshot"]["export_text"].startswith("[夫妻宫]\n宫名：夫妻宫")


@requires_runtime
def test_live_yizhangjing_carries_the_note(tmp_path: Path) -> None:
    from horosa_skill.config import Settings
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService
    from horosa_skill.testing_payloads import build_sample_payloads

    settings = Settings.from_env().model_copy(update={"db_path": tmp_path / "m.db", "output_dir": tmp_path / "runs", "data_dir": tmp_path / "d"})
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    result = service.run_tool("yizhangjing", {**build_sample_payloads()["yizhangjing"], "defaults_accepted": True}, save_result=False)
    assert result.ok and result.data["export_snapshot"].get("script_note") == SCRIPT_NOTE
