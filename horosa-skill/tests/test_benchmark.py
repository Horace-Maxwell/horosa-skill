from __future__ import annotations

import json
from pathlib import Path

from horosa_skill.benchmark import load_benchmark_dataset, run_benchmark
from horosa_skill.config import Settings


def test_benchmark_dataset_loads() -> None:
    dataset = load_benchmark_dataset()
    assert dataset["metadata"]["name"] == "HorosaBench"
    assert dataset["cases"]


def test_benchmark_can_run_local_only_cases(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        trace_dir=tmp_path / "traces",
    )
    report = run_benchmark(settings=settings, skip_runtime=True, save_result=False)

    assert report["cases_executed"] >= 1
    assert "knowledge_qimen_door" in [item["id"] for item in report["results"]]
    assert report["ok"] is True


def test_generated_cases_stay_lockstep_with_the_tool_registry() -> None:
    """Bench v2：生成 case 与 TOOL_EXPORT_TECHNIQUE_MAP 永远锁步——新增技法自动获得 case，
    不再靠人记（静态数据集只有 4 case 的时代就是这么欠下的）。"""
    from horosa_skill.benchmark.runner import generate_tool_cases
    from horosa_skill.service import TOOL_EXPORT_TECHNIQUE_MAP

    cases = generate_tool_cases()
    assert {c["tool"] for c in cases} == set(TOOL_EXPORT_TECHNIQUE_MAP)
    for case in cases:
        assert case["expected_technique"] == TOOL_EXPORT_TECHNIQUE_MAP[case["tool"]]
        assert case["required_format_source"] == "snapshot_parser", "禁 generated_template 假导出"
        assert case["requires_runtime"] is True


def _unknown_export_keys(mapping: dict[str, str]) -> dict[str, str]:
    from horosa_skill.exports.registry import AI_EXPORT_TECHNIQUES

    known = {item["key"] for item in AI_EXPORT_TECHNIQUES}
    return {tool: key for tool, key in mapping.items() if key not in known}


def test_every_business_tool_is_in_export_technique_map() -> None:
    """锁步（v0.33.0 批 III-5 现场抓获的缺口）：bench 生成 case 只覆盖 TOOL_EXPORT_TECHNIQUE_MAP，
    「新增技法自动获得用例」的承诺依赖入表——批 I 的 4 个新工具全都漏了、bench 静默不覆盖。

    表现在由注册表派生，「漏登记」不会再发生；派生带来的新错法是**缺省键不存在**：工具名默认当导出键，导出键
    与工具名不同却没写覆盖时，parse 抛 Unknown 被吞成 export_snapshot=None，bench 照样生成用例。所以这里锁三件事：
    非业务工具显式列名、每个键都在导出注册表里、覆盖项没有死条目。"""
    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.service import TOOL_EXPORT_TECHNIQUE_MAP
    from horosa_skill.service.export import _EXPORT_TECHNIQUE_OVERRIDES

    non_business = {"export_parse", "export_registry", "knowledge_read", "knowledge_registry"}
    assert set(TOOL_DEFINITIONS) - set(TOOL_EXPORT_TECHNIQUE_MAP) == non_business
    assert _unknown_export_keys(TOOL_EXPORT_TECHNIQUE_MAP) == {}, "这些工具的导出键不在 AI_EXPORT_TECHNIQUES：缺覆盖项，或导出注册表没登记"
    dead = {k: v for k, v in _EXPORT_TECHNIQUE_OVERRIDES.items() if k == v or k not in TOOL_DEFINITIONS}
    assert dead == {}, f"覆盖项有死条目（与工具名相同，或工具不存在）：{dead}"


def test_a_new_tool_without_an_export_key_is_caught() -> None:
    """负向对照：新技法没进导出注册表，或导出键与工具名不同却忘了写覆盖，上一条必须红。"""
    from horosa_skill.service.export import _derive_export_technique_map

    mapping = _derive_export_technique_map(["chart", "pd", "brand_new_tool"], overrides={"chart": "astrochart"})
    assert _unknown_export_keys(mapping) == {"pd": "pd", "brand_new_tool": "brand_new_tool"}


def test_faithfulness_cases_run_offline_and_adversarial_goes_red(tmp_path) -> None:
    """v0.36.0 C3：faithfulness 类 case 跑工具→抽真值→判答案；塔罗两条离线可跑，对抗那条必须被判红且计为通过。"""
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        trace_dir=tmp_path / "traces",
    )
    report = run_benchmark(settings=settings, skip_runtime=True, save_result=False)
    by_id = {item["id"]: item for item in report["results"]}
    good, bad = by_id["faith_tarot_supported"], by_id["faith_tarot_wrong_orientation"]
    assert good["ok"] and good["faithfulness_ok"] and good["verdict_ok"], good
    assert bad["ok"] and not bad["faithfulness_ok"] and bad["flagged"] >= 2 and bad["verdict_ok"], bad
    assert {c["status"] for c in bad["claims"]} >= {"contradicted", "invented"}
    assert report["ok"] is True


def test_bench_records_a_broken_case_instead_of_aborting(tmp_path, monkeypatch) -> None:
    """单 case 的校验错误只红这一条：整轮 bench 不许因一条坏 payload 白跑。"""
    from horosa_skill.benchmark import runner as bench

    broken = {"id": "faith_tarot_missing_fields", "kind": "faithfulness", "tool": "tarot", "requires_runtime": False,
              "payload": {"agent_confirmed_settings": True, "spread": "three"}, "answer_text": "抽到了愚者。", "expect_ok": True}
    original = bench.load_benchmark_dataset

    def patched(dataset_path=None):
        data = original(dataset_path)
        data["cases"] = [c for c in data["cases"] if not c.get("requires_runtime")] + [broken]
        return data

    monkeypatch.setattr(bench, "load_benchmark_dataset", patched)
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", trace_dir=tmp_path / "traces")
    report = run_benchmark(settings=settings, skip_runtime=True, save_result=False)
    item = next(r for r in report["results"] if r["id"] == "faith_tarot_missing_fields")
    assert item["ok"] is False and item["error_code"] == "tool.invalid_payload" and item["verdict_ok"] is False
    assert report["ok"] is False and report["cases_executed"] >= 3
    assert report["verdict"] == "fail" and bench.exit_code(report) == 1


# ── 2026-11-11 深审 B-1：结论旁边写覆盖面；数据集片段对着仓里录下的真实导出核对 ─────────────────────────────


def test_a_partial_run_reports_coverage_and_never_a_bare_full_pass_rate(tmp_path) -> None:
    """此前 `--skip-runtime` 跑 120 条里的 3 条，顶层报 pass_rate 1.0、ok true，CI 日志读起来像全量通过。"""
    from horosa_skill.benchmark.runner import exit_code

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db",
                        output_dir=tmp_path / "runs", trace_dir=tmp_path / "traces")
    report = run_benchmark(settings=settings, skip_runtime=True, save_result=False)
    coverage = report["coverage"]
    assert coverage["executed"] == report["cases_executed"] < coverage["total"] == report["cases_total"]
    assert coverage["executed"] + coverage["skipped"] == coverage["total"]
    assert report["verdict"] == "pass_partial" and report["ok"] is True
    assert report["pass_rate"] == round(report["cases_passed"] / coverage["total"], 4) < 0.5
    assert report["pass_rate_executed"] == 1.0
    chinese, english = report["summary"].split(" / ", 1)
    assert f"{coverage['executed']}/{coverage['total']}" in chinese and f"executed {coverage['executed']} of {coverage['total']}" in english
    assert exit_code(report) == 0 and exit_code(report, require_full=True) == 2


def test_a_missing_fragment_is_named_in_the_case_result() -> None:
    from types import SimpleNamespace

    from horosa_skill.benchmark.runner import _evaluate_tool_case

    result = SimpleNamespace(ok=True, trace_id=None, group_id=None, data={"export_snapshot": {
        "export_text": "[宫位宫头]\n| 宫位 | 宫头 |", "selected_sections": ["宫位宫头"], "technique": {"key": "astrochart"}}})
    case = {"id": "x", "kind": "tool", "tool": "chart", "required_sections": ["宫位宫头", "相位"], "required_fragments": ["宫头：", "宫头"]}
    item = _evaluate_tool_case(case, result)
    assert item["missing_fragments"] == ["宫头："] and item["missing_sections"] == ["相位"] and not item["required_fragments_ok"]


FIXTURES = Path(__file__).parent / "fixtures"
# 手写 tool case 的 required_fragments 对着仓里录下的**真实**导出核对（离线）。录音来自 vendored 引擎实跑；
# app 形样例（export_snapshots/*.txt）是旧版式的样子，「宫头：」就还在里面——拿它核对抓不住 B-1，所以 chart 不用它。
RECORDED_EXPORTS: dict[str, list[tuple[str, tuple[str, ...]]]] = {
    "chart_export_parity": [("sync311_chartexport_live.json", ("tropical_default", "upstream_text")),
                            ("sync313_western_live.json", ("node_exalt", "upstream_text"))],
    "guolao_moira_sections": [("sync311_w3b_guolao_live.json", ("live_snapshot_text",))],
    "qimen_export_parity": [("export_snapshots/qimen_live_snapshot.txt", ())],
}
# 没有录音的：只有带运行时的 lane 能核对（`run_benchmark.py --require-full`）。
LIVE_ONLY = {"bazi_inverse_candidates": "仓里没有 bazi_inverse 的导出录音"}


def _recorded(name: str, path: tuple[str, ...]) -> str:
    raw = (FIXTURES / name).read_text(encoding="utf-8")
    if not path:
        return raw
    node = json.loads(raw)
    for key in path:
        node = node[key]
    return node


def test_every_curated_fragment_occurs_in_a_recorded_live_export() -> None:
    """B-1：数据集里「宫头：」在导出改成表格后再也不出现，bench 全量跑 119/120；离线 CI 只跑 --skip-runtime 看不见。"""
    cases = [c for c in load_benchmark_dataset()["cases"] if c["kind"] == "tool" and c.get("required_fragments")]
    assert cases
    for case in cases:
        if case["id"] in LIVE_ONLY:
            continue
        assert case["id"] in RECORDED_EXPORTS, f"{case['id']}：给它配一份录下的导出，或写进 LIVE_ONLY 并说明原因"
        for name, path in RECORDED_EXPORTS[case["id"]]:
            text = _recorded(name, path)
            missing = [fragment for fragment in case["required_fragments"] if fragment not in text]
            assert not missing, (case["id"], name, missing)
