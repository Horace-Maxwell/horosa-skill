"""合参（horosa_hecan）v0.50.0 深审重做：H-1 正文节选 / H-2 少于两个技法不算合参 + 按领域缺省配对 / H-3 双语 /
F16 复用 run_id、原话与设置转发、memory_show 打开子 run。

离线：FakeClient + FakeJsClient。每条断言的负向对照在 LESSONS 合参条目里记了跑法。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.engine import hecan_select
from horosa_skill.errors import DispatchResolutionError, ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools import HecanInput
from horosa_skill.service import HorosaSkillService
from horosa_skill.service import hecan_template as tpl
from horosa_skill.testing_payloads import build_sample_payloads

SAMPLES = build_sample_payloads()
BIRTH = {**SAMPLES["bazi_birth"], "gender": 1}
MOMENT = {key: SAMPLES["qimen"][key] for key in ("date", "time", "zone", "lat", "lon")}
_CJK = re.compile(r"[一-鿿]")


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _bilingual(line: str) -> bool:
    zh, sep, en = line.partition(" / ")
    return bool(sep) and bool(_CJK.search(zh)) and bool(re.search(r"[A-Za-z]{3}", en)) and not _CJK.search(en.split("（")[0][:12])


# ---- H-2：少于两个技法不是交叉印证 ------------------------------------------------------------------------------


def test_one_technique_is_not_presented_as_a_finished_cross_validation(tmp_path: Path) -> None:
    result = _service(tmp_path).hecan({"query": "看看我的命", "birth": BIRTH, "tools": ["bazi_birth"], "agent_confirmed_settings": True})
    assert result["ok"] is True and result["selected_tools"] == ["bazi_birth"]
    assert result["cross_validation"] is False
    assert result["consistency"]["all_clear"] is None, "一个技法没有可比的对象：不许说「全绿」"
    assert any("不是交叉印证" in w and "not a cross-check" in w for w in result["warnings"])
    assert any("不是交叉印证" in line for line in result["summary"])
    assert not any("合参模板，不是终稿" in line for line in result["summary"])


def test_two_techniques_are_a_cross_validation(tmp_path: Path) -> None:
    result = _service(tmp_path).hecan({"query": "看看我的命", "birth": BIRTH, "tools": ["bazi_birth", "ziwei_birth"],
                                       "agent_confirmed_settings": True})
    assert result["cross_validation"] is True and result["consistency"]["all_clear"] in (True, False)
    assert not any("不是交叉印证" in w for w in result["warnings"])


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("看看我的命", ["bazi_birth", "ziwei_birth"]),            # 命理：八字紫微互证
        ("这个项目能不能成", ["liureng_gods", "qimen"]),          # 起课：三式互参
        ("今年运势怎么样", ["bazi_direct", "ziwei_birth"]),       # 运势
        ("帮我卜一卦", ["sixyao", "horary"]),                      # 卜卦两义：两种都起
        ("用奇门看看这件事", ["qimen", "liureng_gods"]),           # 点名一种：补同领域的另一个
        ("紫微看今年事业运", ["ziwei_birth", "bazi_direct"]),     # 一个技法在两个领域：问句命中的那个领域优先
        ("八字和紫微对照看", ["ziwei_birth", "bazi_birth"]),      # 点名两种：照用（顺序随路由）
    ],
)
def test_default_selection_is_a_pair_per_question_domain(query: str, expected: list[str]) -> None:
    selection = hecan_select.select(HecanInput.model_validate({"query": query}), max_tools=5)
    assert sorted(selection.tools) == sorted(expected) and len(selection.tools) >= 2
    if query != "八字和紫微对照看":
        assert selection.warnings and all(_bilingual(w) for w in selection.warnings), "缺省选的组合必须披露（双语）"


@pytest.mark.parametrize("query", ["帮我择个吉日搬家", "看看手相", "呵呵"])
def test_domains_without_a_default_pair_keep_the_structured_refusal(query: str) -> None:
    with pytest.raises(DispatchResolutionError):
        hecan_select.select(HecanInput.model_validate({"query": query}), max_tools=5)


def test_service_and_gate_select_the_same_pair(tmp_path: Path) -> None:
    from horosa_skill.agent_guidance import validate_agent_preflight

    verdict = validate_agent_preflight("hecan", {"query": "这个项目能不能成"})
    assert verdict["ok"] is False and verdict["selected_tools"] == ["liureng_gods", "qimen"]
    result = _service(tmp_path).hecan({"query": "这个项目能不能成", "context": MOMENT, "agent_confirmed_settings": True})
    assert result["ok"] is True and result["selected_tools"] == ["liureng_gods", "qimen"]


# ---- F16：复用 run_id、转发原话与设置、memory_show 打开子 run --------------------------------------------------------


def test_earlier_runs_are_reused_not_recomputed(tmp_path: Path) -> None:
    service = _service(tmp_path)
    first = service.run_tool("bazi_birth", {**BIRTH, "agent_confirmed_settings": True})
    rid = first.memory_ref.run_id
    computed: list[str] = []
    original = service.run_tool

    def spy(tool_name, payload, **kwargs):
        computed.append(tool_name)
        return original(tool_name, payload, **kwargs)

    service.run_tool = spy  # type: ignore[method-assign]
    result = service.hecan({"query": "看看我的命", "birth": BIRTH, "tools": [rid, "ziwei_birth"], "agent_confirmed_settings": True})
    assert computed == ["ziwei_birth"], "复用的八字不能再算一遍"
    rows = {row["tool"]: row for row in result["techniques"]}
    assert rows["bazi_birth"]["reused"] is True and rows["bazi_birth"]["run_id"] == rid
    assert rows["ziwei_birth"]["reused"] is False and rows["ziwei_birth"]["run_id"] == result["memory_ref"]["run_id"]
    assert result["child_runs"] == [
        {"tool": "bazi_birth", "run_id": rid, "reused": True},
        {"tool": "ziwei_birth", "run_id": result["memory_ref"]["run_id"], "reused": False},
    ]
    assert rows["bazi_birth"]["evidence"]["text"].startswith("[起盘信息]"), "复用的结果同样带正文节选"
    # 只给 run_id（不再算任何技法）也行；闸门不问已算过的东西。
    from horosa_skill.agent_guidance import validate_agent_preflight

    assert validate_agent_preflight("hecan", {"query": "x", "tools": [rid]})["ok"] is True
    only = service.hecan({"query": "看看我的命", "tools": [rid]})
    assert only["selected_tools"] == ["bazi_birth"] and only["cross_validation"] is False


def test_reused_run_for_another_birth_moment_is_flagged(tmp_path: Path) -> None:
    service = _service(tmp_path)
    rid = service.run_tool("bazi_birth", {**BIRTH, "agent_confirmed_settings": True}).memory_ref.run_id
    other = {**BIRTH, "date": "1991-01-01"}
    result = service.hecan({"query": "看看我的命", "birth": other, "tools": [rid, "ziwei_birth"], "agent_confirmed_settings": True})
    assert any("可能不是同一个人" in w and "date" in w for w in result["warnings"])


def test_unusable_run_ids_are_refused(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(ToolValidationError) as missing:
        service.hecan({"query": "x", "tools": ["0" * 32, "bazi_birth"], "birth": BIRTH})
    assert missing.value.code == "memory.run.not_found" and missing.value.details["field"] == "tools"
    empty = service.store.create_run(entrypoint="tool", query_text="x")
    with pytest.raises(ToolValidationError) as unusable:
        service.hecan({"query": "x", "tools": [empty], "birth": BIRTH})
    assert unusable.value.code == "hecan.run_not_reusable"
    from horosa_skill.errors import recovery_for

    assert recovery_for("hecan.run_not_reusable", {})["agent_recovery"]["next_action"] == "query_memory_for_run_id"


def test_question_and_settings_reach_each_technique(tmp_path: Path) -> None:
    result = _service(tmp_path).hecan(
        {"query": "这次合作能不能成", "birth": {**BIRTH}, "context": MOMENT, "tools": ["sixyao", "chart"],
         "preferences": {"hsys": 0}, "agent_confirmed_settings": True},
        include_results=True,
    )
    inputs = {name: envelope["input_normalized"] for name, envelope in result["results"].items()}
    assert inputs["sixyao"]["question"] == "这次合作能不能成"
    assert inputs["chart"]["hsys"] == 0
    assert inputs["sixyao"]["date"] == MOMENT["date"], "起课按 context 的时刻，不按出生"


def test_memory_show_of_a_hecan_run_opens_its_child_runs(tmp_path: Path) -> None:
    service = _service(tmp_path)
    rid = service.run_tool("bazi_birth", {**BIRTH, "agent_confirmed_settings": True}).memory_ref.run_id
    result = service.hecan({"query": "看看我的命", "birth": BIRTH, "tools": [rid, "ziwei_birth"], "agent_confirmed_settings": True})
    shown = service.show_memory({"run_id": result["memory_ref"]["run_id"]})
    record = shown["result"]
    assert record["entrypoint"] == "hecan"
    assert record["child_runs"] == result["child_runs"]
    kinds = [(a["kind"], a["tool_name"], a.get("from_run")) for a in record["artifacts"]]
    assert ("hecan_result", "horosa_hecan", None) in kinds
    assert ("tool_result", "ziwei_birth", None) in kinds
    assert ("tool_result", "bazi_birth", rid) in kinds, "复用的子结果从原 run 接上"
    reused = next(a for a in record["artifacts"] if a.get("from_run") == rid)
    assert reused["payload"]["data"]["export_snapshot"]["export_text"]
    # 存档里的合参记录带每个技法的正文节选（CLI / 存档也有盘面事实，不只段名与指针）。
    stored = next(a for a in record["artifacts"] if a["kind"] == "hecan_result")["payload"]
    assert all(row["evidence"]["text"] for row in stored["techniques"])


def test_memory_reading_view_lists_children_without_repeating_the_excerpt(tmp_path: Path) -> None:
    from horosa_skill.result_view import READING, Budget, ViewRequest, shape_result

    service = _service(tmp_path)
    result = service.hecan({"query": "看看我的命", "birth": BIRTH, "tools": ["bazi_birth", "ziwei_birth"], "agent_confirmed_settings": True})
    shown = service.show_memory({"run_id": result["memory_ref"]["run_id"]})
    view = shape_result(shown, ViewRequest(view=READING), Budget(max_tokens=20000, max_chars=48000))
    hecan_artifact = next(a for a in view["result"]["artifacts"] if a["kind"] == "hecan_result")
    for row in hecan_artifact["payload"]["techniques"]:
        assert "text" not in row["evidence"] and "text_in" in row["evidence"]
    assert hecan_artifact["payload"]["child_runs"]


# ---- H-1：正文节选有上限、截断明说 ---------------------------------------------------------------------------------


def test_each_technique_carries_a_bounded_excerpt_that_states_truncation() -> None:
    body = "甲" * 1500
    envelope = {
        "ok": True, "tool": "qimen",
        "data": {"export_snapshot": {"sections": [{"index": i, "title": f"段{i}", "body": body} for i in range(1, 6)],
                                     "export_text": "x"}},
    }
    excerpt = tpl.evidence(envelope, run_id="a" * 32, limit=4000)
    assert len(excerpt["text"]) <= 4000
    assert excerpt["complete"] is False and excerpt["sections_shown"] == ["段1", "段2"]
    assert excerpt["sections_not_shown"] == ["段3", "段4", "段5"]
    assert _bilingual(excerpt["note"]) and "4000" in excerpt["note"]
    assert excerpt["read_rest"].startswith(f'horosa_memory_show(run_id="{"a" * 32}", response_tool="qimen", response_sections=[3, 4, 5])')
    whole = tpl.evidence({**envelope, "data": {"export_snapshot": {"sections": [{"index": 1, "title": "段1", "body": "短"}]}}}, run_id=None)
    assert whole["complete"] is True and "note" not in whole and "read_rest" not in whole
    first_too_long = tpl.evidence({**envelope, "data": {"export_snapshot": {"sections": [{"index": 1, "title": "长", "body": "乙" * 9000}]}}},
                                  run_id=None, limit=4000)
    assert first_too_long["text"].endswith("…") and len(first_too_long["text"]) <= 4001 and first_too_long["complete"] is False


def test_mcp_results_do_not_repeat_the_excerpt_text(tmp_path: Path) -> None:
    result = _service(tmp_path).hecan({"query": "看看我的命", "birth": BIRTH, "tools": ["bazi_birth", "ziwei_birth"],
                                       "agent_confirmed_settings": True}, include_results=True)
    assert set(result["results"]) == {"bazi_birth", "ziwei_birth"}
    for row in result["techniques"]:
        assert "text" not in row["evidence"] and row["evidence"]["text_in"] == f"results.{row['tool']}"


# ---- H-3：摘要与契约说明双语 ------------------------------------------------------------------------------------------


def test_summary_warnings_and_instructions_are_bilingual(tmp_path: Path) -> None:
    result = _service(tmp_path).hecan({"query": "看看我的命", "birth": BIRTH, "tools": ["bazi_birth"], "agent_confirmed_settings": True})
    lines = [*result["summary"], *result["synthesis_contract"]["instructions"],
             *[w for w in result["warnings"] if "交叉印证" in w]]
    assert lines and all(_bilingual(line) for line in lines), [line for line in lines if not _bilingual(line)]
    instructions = "\n".join(result["synthesis_contract"]["instructions"])
    assert "不许平均" in instructions and "never average" in instructions


@pytest.mark.parametrize("drop_manifest", [False, True])
def test_a_rebuilt_store_keeps_the_hecan_record(tmp_path: Path, drop_manifest: bool) -> None:
    """库丢了照 runs/ 重建：合参产物仍是 hecan_result（文件名后缀与 dispatch 相同，按 record_meta.kind 认），memory_show 仍带 child_runs。"""
    from horosa_skill.memory.rebuild import rebuild_from_artifacts

    service = _service(tmp_path)
    result = service.hecan({"query": "看看我的命", "birth": BIRTH, "tools": ["bazi_birth", "ziwei_birth"], "agent_confirmed_settings": True})
    run_id = result["memory_ref"]["run_id"]
    for path in tmp_path.glob("memory.db*"):
        path.unlink()
    if drop_manifest:
        for path in (tmp_path / "runs").rglob("*_manifest.json"):
            path.unlink()
    service = _service(tmp_path)
    rebuild_from_artifacts(service.store, min_age_seconds=0)
    record = service.show_memory({"run_id": run_id})["result"]
    assert "hecan_result" in [a["kind"] for a in record["artifacts"]]
    assert record["child_runs"] == result["child_runs"]
