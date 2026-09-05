from __future__ import annotations

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


def test_every_business_tool_is_in_export_technique_map() -> None:
    """锁步（v0.33.0 批 III-5 现场抓获的缺口）：bench 生成 case 只覆盖 TOOL_EXPORT_TECHNIQUE_MAP，
    「新增技法自动获得用例」的承诺依赖入表——批 I 的 4 个新工具全都漏了、bench 静默不覆盖。
    非业务工具（导出/知识门面）显式列名；其余任何注册工具不在表=红。"""
    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.service import TOOL_EXPORT_TECHNIQUE_MAP

    non_business = {"export_parse", "export_registry", "knowledge_read", "knowledge_registry"}
    unmapped = sorted(set(TOOL_DEFINITIONS) - set(TOOL_EXPORT_TECHNIQUE_MAP) - non_business)
    assert unmapped == [], f"业务工具未入 TOOL_EXPORT_TECHNIQUE_MAP（bench 不生成用例）：{unmapped}"


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
