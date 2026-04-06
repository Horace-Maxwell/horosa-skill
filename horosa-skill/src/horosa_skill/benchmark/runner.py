from __future__ import annotations

import copy
import json
import tempfile
from importlib.resources import files
from pathlib import Path
from typing import Any

from horosa_skill.config import Settings
from horosa_skill.evaluation_lock import acquire_evaluation_lock
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.service import HorosaSkillService
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
    export_text = export_snapshot.get("export_text", "") if isinstance(export_snapshot, dict) else ""
    section_titles = set(export_snapshot.get("selected_sections", []) if isinstance(export_snapshot, dict) else [])
    required_sections = case.get("required_sections", [])
    required_fragments = case.get("required_fragments", [])
    return {
        "id": case["id"],
        "kind": case["kind"],
        "tool": case["tool"],
        "ok": bool(result.ok),
        "trace_id": result.trace_id,
        "group_id": result.group_id,
        "expected_technique": case.get("expected_technique"),
        "actual_technique": export_snapshot.get("technique", {}).get("key") if isinstance(export_snapshot, dict) else None,
        "technique_ok": (case.get("expected_technique") is None or export_snapshot.get("technique", {}).get("key") == case.get("expected_technique")),
        "required_sections_ok": all(title in section_titles for title in required_sections),
        "required_fragments_ok": all(fragment in export_text for fragment in required_fragments),
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
        "contracts_ok": all(contract.get("has_export_snapshot") and contract.get("has_export_format") for contract in result.result_export_contracts.values()),
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


def _summarize(results: list[dict[str, Any]], *, skipped: list[str], dataset: dict[str, Any]) -> dict[str, Any]:
    executed = [item for item in results]
    passed = 0
    for item in executed:
        if item["kind"] == "tool":
            if item["ok"] and item["technique_ok"] and item["required_sections_ok"] and item["required_fragments_ok"]:
                passed += 1
        elif item["kind"] == "dispatch":
            if item["ok"] and item["selection_ok"] and item["contracts_ok"]:
                passed += 1
        elif item["kind"] == "knowledge":
            if item["ok"] and item["required_fragments_ok"]:
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
        "ok": executed_count > 0 and passed == executed_count,
        "results": results,
    }


def run_benchmark(
    *,
    settings: Settings,
    dataset_path: Path | None = None,
    skip_runtime: bool = False,
    save_result: bool = False,
) -> dict[str, Any]:
    dataset = load_benchmark_dataset(dataset_path)
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
        with acquire_evaluation_lock(bench_settings):
            try:
                if not skip_runtime:
                    manager.start_local_services()
                    runtime_started = True
                for case in dataset.get("cases", []):
                    if skip_runtime and case.get("requires_runtime", False):
                        skipped.append(case["id"])
                        continue
                    if case["kind"] == "tool":
                        payload = _build_case_payload(case, sample_payloads)
                        result = service.run_tool(
                            case["tool"],
                            payload,
                            save_result=save_result,
                            query_text=case.get("query"),
                            evaluation_case_id=case["id"],
                        )
                        results.append(_evaluate_tool_case(case, result))
                    elif case["kind"] == "dispatch":
                        payload = _build_case_payload(case, sample_payloads)
                        result = service.dispatch(payload, evaluation_case_id=case["id"])
                        results.append(_evaluate_dispatch_case(case, result))
                    elif case["kind"] == "knowledge":
                        payload = _build_case_payload(case, sample_payloads)
                        result = service.run_tool(
                            "knowledge_read",
                            payload,
                            save_result=save_result,
                            query_text=case.get("query"),
                            evaluation_case_id=case["id"],
                        )
                        results.append(_evaluate_knowledge_case(case, result))
            finally:
                if runtime_started:
                    manager.stop_local_services()
        return _summarize(results, skipped=skipped, dataset=dataset)
