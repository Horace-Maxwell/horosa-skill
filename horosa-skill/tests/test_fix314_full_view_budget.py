"""审计 S-28：response_view="full" 以前没有上限（八字一次 36 万字节）。放得下照原样；放不下回键目录，response_path 取子树。"""
from __future__ import annotations

from horosa_skill.result_view import FULL, Budget, ViewRequest, shape_result, take_view_request

BIG = {"ok": True, "tool": "bazi_birth", "run_id": "r1",
       "data": {"export_snapshot": {"export_text": "盘" * 400}, "raw": {"bazi": {"rows": ["字" * 3000 for _ in range(10)]}}}}
BUDGET = Budget(max_tokens=2000, max_chars=4000)


def test_small_full_result_is_returned_as_is() -> None:
    small = {"ok": True, "tool": "x", "data": {"a": 1}}
    assert shape_result(small, ViewRequest(view=FULL), BUDGET) == small


def test_oversized_full_result_returns_a_directory() -> None:
    """负向对照（实跑过）：shape_result 的 FULL 分支直接 return raw → 原样 3 万多字进回包 → 红。"""
    out = shape_result(BIG, ViewRequest(view=FULL), BUDGET)
    view = out["response_view"]
    assert view["exceeds_budget"] is True and out["run_id"] == "r1"
    paths = {row["path"] for row in view["directory"]}
    assert {"data", "data.export_snapshot", "data.raw"} <= paths
    assert len(str(out)) < 4000


def test_response_path_fetches_a_subtree_that_fits() -> None:
    _args, request = take_view_request({"run_id": "r1", "response_view": "full", "response_path": "data.export_snapshot"}, default_view="reading")
    out = shape_result(BIG, request, BUDGET)
    assert out["value"] == BIG["data"]["export_snapshot"] and out["response_view"]["path"] == "data.export_snapshot"
    missing = shape_result(BIG, ViewRequest(view=FULL, path="data.nope"), BUDGET)
    assert "不存在" in missing["response_view"]["how"]
