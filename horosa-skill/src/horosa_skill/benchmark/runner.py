from __future__ import annotations

import copy
import os
import json
import tempfile
from importlib.resources import files
from pathlib import Path
from typing import Any

from horosa_skill.config import Settings
from horosa_skill.evaluation_lock import acquire_evaluation_lock
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.service import HorosaSkillService
from horosa_skill.errors import HorosaSkillError, bilingual
from horosa_skill.testing_payloads import build_sample_payloads


def _dataset_path() -> Any:
    return files("horosa_skill.benchmark.data").joinpath("horosa_bench.json")


def load_benchmark_dataset(dataset_path: Path | None = None) -> dict[str, Any]:
    if dataset_path is None:
        return json.loads(_dataset_path().read_text(encoding="utf-8"))
    return json.loads(dataset_path.read_text(encoding="utf-8"))


def _build_case_payload(case: dict[str, Any], sample_payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if case.get("sample_payload"):
        return copy.deepcopy(sample_payloads[case["sample_payload"]])
    return copy.deepcopy(case.get("payload", {}))


def _evaluate_tool_case(case: dict[str, Any], result: Any) -> dict[str, Any]:
    export_snapshot = result.data.get("export_snapshot") if isinstance(result.data, dict) else {}
    # 失败信封的 data 可能带 export_snapshot=None——评测器必须对任意信封形状稳健（评测器崩了
    # 整轮 bench 白跑，比单 case 红严重得多）。
    export_snapshot = export_snapshot if isinstance(export_snapshot, dict) else {}
    export_text = export_snapshot.get("export_text", "") if isinstance(export_snapshot, dict) else ""
    section_titles = set(export_snapshot.get("selected_sections", []) if isinstance(export_snapshot, dict) else [])
    required_sections = case.get("required_sections", [])
    required_fragments = case.get("required_fragments", [])
    # v2：生成 case 断言 format_source（禁 generated_template 假导出——tianxing 曾把 JS 失败
    # 伪造成正常导出，这是那次事故的普查版）。
    required_format_source = case.get("required_format_source")
    actual_format_source = export_snapshot.get("format_source") if isinstance(export_snapshot, dict) else None
    return {
        "id": case["id"],
        "kind": case["kind"],
        "tool": case["tool"],
        "ok": bool(result.ok),
        "trace_id": result.trace_id,
        "group_id": result.group_id,
        "expected_technique": case.get("expected_technique"),
        "actual_technique": (export_snapshot.get("technique") or {}).get("key") if isinstance(export_snapshot, dict) else None,
        "technique_ok": (case.get("expected_technique") is None or (export_snapshot.get("technique") or {}).get("key") == case.get("expected_technique")),
        "required_sections_ok": all(title in section_titles for title in required_sections),
        "required_fragments_ok": all(fragment in export_text for fragment in required_fragments),
        "format_source_ok": (required_format_source is None or actual_format_source == required_format_source),
        "required_sections": required_sections,
        "required_fragments": required_fragments,
    }


def _evaluate_dispatch_case(case: dict[str, Any], result: Any) -> dict[str, Any]:
    selected = sorted(result.selected_tools)
    expected = sorted(case.get("expected_selected_tools", []))
    return {
        "id": case["id"],
        "kind": case["kind"],
        "ok": bool(result.ok),
        "trace_id": result.trace_id,
        "group_id": result.group_id,
        "selected_tools": selected,
        "expected_selected_tools": expected,
        "selection_ok": selected == expected,
        "contracts_ok": all(contract.get("has_export_snapshot") for contract in result.result_export_contracts.values()),
    }


def _evaluate_faithfulness_case(case: dict[str, Any], result: Any) -> dict[str, Any]:
    """faithfulness 类 case（v0.36.0 C3）：跑工具 → 抽真值 → 判一段给定答案；期望 ok 或期望被判红。

    离线可跑（tarot/六爻等本地 JS 工具不需 runtime）；对抗用例（喂错值）期望 `expect_ok=false` 且
    contradicted/invented ≥ expect_min_flagged。
    """
    from horosa_skill.benchmark.faithfulness import extract_facts, verify_answer

    envelope = result.model_dump(mode="json") if hasattr(result, "model_dump") else dict(result)
    verdict = verify_answer(case.get("answer_text", ""), extract_facts(envelope)) if result.ok else {"ok": False, "claims": [], "metrics": {}}
    flagged = int(verdict.get("metrics", {}).get("contradicted", 0)) + int(verdict.get("metrics", {}).get("invented", 0))
    expect_ok = bool(case.get("expect_ok", True))
    expect_min_flagged = int(case.get("expect_min_flagged", 0 if expect_ok else 1))
    return {
        "id": case["id"],
        "kind": case["kind"],
        "tool": case["tool"],
        "ok": bool(result.ok),
        "trace_id": result.trace_id,
        "group_id": result.group_id,
        "faithfulness_ok": bool(verdict.get("ok")),
        "flagged": flagged,
        "claims": verdict.get("claims", []),
        "expect_ok": expect_ok,
        "verdict_ok": bool(result.ok) and (bool(verdict.get("ok")) == expect_ok) and flagged >= expect_min_flagged,
    }


def _evaluate_knowledge_case(case: dict[str, Any], result: Any) -> dict[str, Any]:
    rendered = result.data.get("rendered_text", "") if isinstance(result.data, dict) else ""
    required_fragments = case.get("required_fragments", [])
    return {
        "id": case["id"],
        "kind": case["kind"],
        "ok": bool(result.ok),
        "trace_id": result.trace_id,
        "group_id": result.group_id,
        "required_fragments": required_fragments,
        "required_fragments_ok": all(fragment in rendered for fragment in required_fragments),
    }


def _run_case(case: dict[str, Any], service: Any, sample_payloads: dict[str, Any], *, save_result: bool) -> dict[str, Any]:
    """按 case.kind 跑一条并返回评测结果（HorosaSkillError 交给调用方按条记红）。"""
    if case["kind"] == "tool":
        payload = _build_case_payload(case, sample_payloads)
        result = service.run_tool(
            case["tool"],
            payload,
            save_result=save_result,
            query_text=case.get("query"),
            evaluation_case_id=case["id"],
        )
        return _evaluate_tool_case(case, result)
    elif case["kind"] == "dispatch":
        payload = _build_case_payload(case, sample_payloads)
        result = service.dispatch(payload, evaluation_case_id=case["id"])
        return _evaluate_dispatch_case(case, result)
    elif case["kind"] == "knowledge":
        payload = _build_case_payload(case, sample_payloads)
        result = service.run_tool(
            "knowledge_read",
            payload,
            save_result=save_result,
            query_text=case.get("query"),
            evaluation_case_id=case["id"],
        )
        return _evaluate_knowledge_case(case, result)
    elif case["kind"] == "faithfulness":
        payload = _build_case_payload(case, sample_payloads)
        result = service.run_tool(
            case["tool"],
            payload,
            save_result=save_result,
            query_text=case.get("query"),
            evaluation_case_id=case["id"],
        )
        return _evaluate_faithfulness_case(case, result)
    raise HorosaSkillError(
        bilingual(f"未知的 bench case 类型：{case.get('kind')!r}", f"unknown bench case kind: {case.get('kind')!r}"),
        code="benchmark.invalid_case_kind",
        details={"id": case.get("id")},
    )


def _summarize(results: list[dict[str, Any]], *, skipped: list[str], dataset: dict[str, Any]) -> dict[str, Any]:
    executed = [item for item in results]
    passed = 0
    for item in executed:
        if item["kind"] == "tool":
            if (
                item["ok"] and item["technique_ok"] and item["required_sections_ok"]
                and item["required_fragments_ok"] and item.get("format_source_ok", True)
            ):
                passed += 1
        elif item["kind"] == "dispatch":
            if item["ok"] and item["selection_ok"] and item["contracts_ok"]:
                passed += 1
        elif item["kind"] == "knowledge":
            if item["ok"] and item["required_fragments_ok"]:
                passed += 1
        elif item["kind"] == "faithfulness":
            if item["verdict_ok"]:
                passed += 1
    executed_count = len(executed)
    return {
        "schema_version": 1,
        "benchmark": dataset.get("metadata", {}),
        "cases_total": len(dataset.get("cases", [])),
        "cases_executed": executed_count,
        "cases_skipped": len(skipped),
        "skipped_case_ids": skipped,
        "cases_passed": passed,
        "pass_rate": round((passed / executed_count), 4) if executed_count else 0.0,
        # 澄清闸自测（v0.33.0 批 II-2）：bench 与 pytest 共跑 sensitive_settings.json 的
        # self_tests + coverage 不变量（新工具漏登记闸表/策略=整轮 bench 红）。
        "gate_selftests": _gate_selftests(),
        "ok": executed_count > 0 and passed == executed_count and _gate_selftests()["ok"],
        "results": results,
    }


def _gate_selftests() -> dict[str, Any]:
    from horosa_skill.agent_guidance import run_sensitive_settings_selftests

    return run_sensitive_settings_selftests()


def generate_tool_cases() -> list[dict[str, Any]]:
    """Bench v2（v0.28.0）：按注册表**生成**逐工具 case，与工具集永远锁步。

    静态数据集只有 4 case，覆盖率靠人记——注册表驱动生成后，新增技法自动获得 case
    （sample payload 由 `testing_payloads` 的全集断言保证存在）。期望值取自导出契约本身：
    technique key + 快照必须是真解析（禁 `generated_template` 假导出）+ 非 optional preset 段全出。
    这些 case 都要求 runtime（离线 FakeClient 属测试层，bench 跑真栈）。
    """
    from horosa_skill.exports.registry import get_technique_info
    from horosa_skill.service import TOOL_EXPORT_TECHNIQUE_MAP

    cases: list[dict[str, Any]] = []
    for tool_name, technique in sorted(TOOL_EXPORT_TECHNIQUE_MAP.items()):
        info = get_technique_info(technique) or {}
        optional = set(info.get("optional_sections") or [])
        required = [s for s in (info.get("preset_sections") or []) if s not in optional][:6]
        cases.append({
            "id": f"gen_{tool_name}",
            "kind": "tool",
            "tool": tool_name,
            "sample_payload": tool_name,
            "requires_runtime": True,
            "generated": True,
            "expected_technique": technique,
            "required_sections": required,
            "required_format_source": "snapshot_parser",
        })
    return cases


from contextlib import contextmanager


# hermetic 模式保留的 env：显式实例指向 + 引擎二进制定位——剥掉它们评测就打不到被测栈了。
_HERMETIC_KEEP_ENV = {
    "HOROSA_CHART_SERVER_ROOT",
    "HOROSA_SERVER_ROOT",
    "HOROSA_NODE_BIN",
    "HOROSA_CORE_JS_ROOT",
    "HOROSA_RUNTIME_ROOT",
    "HOROSA_UV_BIN",
}


@contextmanager
def _hermetic_env():
    """剥掉除白名单外的所有 HOROSA_* 环境变量（退出恢复）。堵「本机旗标改评测结论」：
    HOROSA_CLARIFY=never 会放掉闸自测、HOROSA_MCP_COMPACT/TOOLSETS 会改工具面、
    HOROSA_TECHNIQUE_CARD 会改响应形状——评测报告却看不出这台机器开了什么。"""
    removed: dict[str, str] = {}
    for key in list(os.environ):
        if key.startswith("HOROSA_") and key not in _HERMETIC_KEEP_ENV:
            removed[key] = os.environ.pop(key)
    try:
        yield sorted(removed)
    finally:
        os.environ.update(removed)


def run_benchmark(
    *,
    settings: Settings,
    dataset_path: Path | None = None,
    skip_runtime: bool = False,
    save_result: bool = False,
    hermetic: bool = False,
) -> dict[str, Any]:
    if hermetic:
        with _hermetic_env() as scrubbed:
            report = run_benchmark(
                settings=settings, dataset_path=dataset_path, skip_runtime=skip_runtime,
                save_result=save_result, hermetic=False,
            )
            report["hermetic"] = {"enabled": True, "scrubbed_env": scrubbed, "kept_env": sorted(
                key for key in _HERMETIC_KEEP_ENV if os.environ.get(key)
            )}
            return report
    dataset = load_benchmark_dataset(dataset_path)
    # v2：手写 case（路由/知识/精选 parity）+ 注册表生成的逐工具 case 合并跑；id 冲突以手写为准。
    curated_ids = {case.get("id") for case in dataset.get("cases", [])}
    dataset = {**dataset, "cases": list(dataset.get("cases", [])) + [
        case for case in generate_tool_cases() if case["id"] not in curated_ids
    ]}
    sample_payloads = build_sample_payloads()
    skipped: list[str] = []

    with tempfile.TemporaryDirectory(prefix="horosa-benchmark-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        bench_settings = settings.model_copy(
            update={
                "db_path": tmp_root / "memory.db",
                "output_dir": tmp_root / "runs",
                "trace_dir": tmp_root / "traces",
            }
        )
        manager = HorosaRuntimeManager(bench_settings)
        service = HorosaSkillService(bench_settings)
        results: list[dict[str, Any]] = []
        runtime_started = False
        # 显式点名的实例（HOROSA_*_SERVER_ROOT env）优先：live 门禁同款纪律——调用方给了实例就
        # 直接打它，不再自起 bundled runtime（默认端口在维护机上常被占用，自起必撞）。
        external_instance = bool(
            os.environ.get("HOROSA_CHART_SERVER_ROOT") or os.environ.get("HOROSA_SERVER_ROOT")
        )
        with acquire_evaluation_lock(bench_settings):
            try:
                if not skip_runtime and not external_instance:
                    manager.start_local_services()
                    runtime_started = True
                for case in dataset.get("cases", []):
                    if skip_runtime and case.get("requires_runtime", False):
                        skipped.append(case["id"])
                        continue
                    try:
                        results.append(_run_case(case, service, sample_payloads, save_result=save_result))
                    except HorosaSkillError as exc:
                        # 单 case 的校验/传输错误只红这一条，不许让整轮 bench 白跑（v0.36.0 C3：tarot case
                        # 缺 date/time 曾把整个 --skip-runtime 烟测炸成 traceback）。
                        results.append({
                            "id": case["id"], "kind": case["kind"], "tool": case.get("tool"), "ok": False,
                            "error_code": exc.code, "error": str(exc), "trace_id": None, "group_id": None,
                            "technique_ok": False, "required_sections_ok": False, "required_fragments_ok": False,
                            "selection_ok": False, "contracts_ok": False, "verdict_ok": False,
                        })
                    continue
            finally:
                if runtime_started:
                    manager.stop_local_services()
        return _summarize(results, skipped=skipped, dataset=dataset)
