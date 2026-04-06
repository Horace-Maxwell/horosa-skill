from __future__ import annotations

import argparse
import copy
import json
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.evaluation_lock import acquire_evaluation_lock
from horosa_skill.exports.parser import parse_export_content
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.service import TOOL_EXPORT_TECHNIQUE_MAP, HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads


def build_payloads() -> dict[str, dict]:
    return build_sample_payloads()


def _contract_is_complete(tool_name: str, result: dict) -> bool:
    if tool_name not in TOOL_EXPORT_TECHNIQUE_MAP:
        return True
    return (
        result["has_export_snapshot"]
        and result["has_export_format"]
        and result["format_source"] == "snapshot_parser"
        and result["export_sections_count"] > 0
        and result["selected_sections_count"] > 0
        and result["technique_key"] == TOOL_EXPORT_TECHNIQUE_MAP[tool_name]
        and not result["reparsed_missing_selected_sections"]
        and not result["reparsed_unknown_detected_sections"]
    )


def _build_contract_summary(tool_name: str, payload: dict) -> dict:
    data = payload.get("data") if isinstance(payload, dict) else {}
    export_snapshot = data.get("export_snapshot") if isinstance(data, dict) else {}
    export_format = data.get("export_format") if isinstance(data, dict) else {}
    reparsed_missing: list[str] = []
    reparsed_unknown: list[str] = []
    technique = TOOL_EXPORT_TECHNIQUE_MAP.get(tool_name)
    if technique and isinstance(export_snapshot, dict) and isinstance(export_snapshot.get("export_text"), str):
        reparsed = parse_export_content(technique=technique, content=export_snapshot["export_text"])
        reparsed_missing = list(reparsed.get("missing_selected_sections", []) or [])
        reparsed_unknown = list(reparsed.get("unknown_detected_sections", []) or [])
    return {
        "tool": tool_name,
        "ok": payload.get("ok") is True if isinstance(payload, dict) else False,
        "has_export_snapshot": isinstance(export_snapshot, dict),
        "has_export_format": isinstance(export_format, dict),
        "format_source": export_snapshot.get("format_source") if isinstance(export_snapshot, dict) else None,
        "export_sections_count": len(export_format.get("sections", [])) if isinstance(export_format, dict) else 0,
        "selected_sections_count": len(export_format.get("selected_sections", [])) if isinstance(export_format, dict) else 0,
        "technique_key": export_snapshot.get("technique", {}).get("key") if isinstance(export_snapshot, dict) else None,
        "reparsed_missing_selected_sections": reparsed_missing,
        "reparsed_unknown_detected_sections": reparsed_unknown,
    }


def run_self_check(*, rounds: int = 2) -> dict:
    payloads = build_payloads()
    missing_payloads = sorted(set(TOOL_DEFINITIONS) - set(payloads))
    extra_payloads = sorted(set(payloads) - set(TOOL_DEFINITIONS))
    with tempfile.TemporaryDirectory(prefix="horosa-selfcheck-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        settings = Settings.from_env().model_copy(
            update={
                "db_path": tmp_root / "memory.db",
                "output_dir": tmp_root / "runs",
            }
        )
        manager = HorosaRuntimeManager(settings)
        service = HorosaSkillService(settings)
        tool_results: list[dict] = []
        dispatch_result: dict | None = None
        knowledge_result: dict | None = None
        with acquire_evaluation_lock(settings):
            manager.start_local_services()
            try:
                for tool_name in TOOL_DEFINITIONS:
                    payload = payloads[tool_name]
                    round_results: list[dict] = []
                    for round_index in range(1, rounds + 1):
                        result = service.run_tool(tool_name, copy.deepcopy(payload), save_result=True)
                        round_results.append(
                            {
                                "round": round_index,
                                "result_ok": result.ok,
                                "artifact_exists": bool(result.memory_ref and Path(result.memory_ref.artifact_path).is_file()),
                                "memory_ref": result.memory_ref.model_dump(mode="json") if result.memory_ref else None,
                                **_build_contract_summary(tool_name, result.model_dump(mode="json")),
                            }
                        )
                    queried = service.store.query_runs(tool=tool_name, include_payload=True, limit=rounds + 2)
                    recent_runs = queried[:rounds]
                    artifact_checks: list[dict] = []
                    for artifact_index, run in enumerate(recent_runs, start=1):
                        artifact_payload = run["artifacts"][0]["payload"] if run.get("artifacts") else {}
                        artifact_checks.append(
                            {
                                "artifact_round": artifact_index,
                                "run_id": run["run_id"],
                                "artifact_path": run["artifacts"][0]["path"] if run.get("artifacts") else None,
                                "stored_payload_ok": artifact_payload.get("ok") is True if isinstance(artifact_payload, dict) else False,
                                **_build_contract_summary(tool_name, artifact_payload),
                            }
                        )
                    tool_results.append(
                        {
                            "tool": tool_name,
                            "ok": all(item["result_ok"] for item in round_results),
                            "rounds_requested": rounds,
                            "rounds": round_results,
                            "retrieved_runs": len(queried),
                            "artifact_exists": all(item["artifact_exists"] for item in round_results),
                            "stored_payload_ok": len(artifact_checks) >= rounds and all(item["stored_payload_ok"] for item in artifact_checks[:rounds]),
                            "has_export_snapshot": bool(round_results and all(item["has_export_snapshot"] for item in round_results)),
                            "has_export_format": bool(round_results and all(item["has_export_format"] for item in round_results)),
                            "format_source": round_results[-1]["format_source"] if round_results else None,
                            "export_sections_count": min((item["export_sections_count"] for item in round_results), default=0),
                            "selected_sections_count": min((item["selected_sections_count"] for item in round_results), default=0),
                            "technique_key": round_results[-1]["technique_key"] if round_results else None,
                            "reparsed_missing_selected_sections": sorted(
                                {title for item in round_results for title in item.get("reparsed_missing_selected_sections", [])}
                            ),
                            "reparsed_unknown_detected_sections": sorted(
                                {title for item in round_results for title in item.get("reparsed_unknown_detected_sections", [])}
                            ),
                            "artifact_rounds": artifact_checks,
                        }
                    )

                dispatch_payload = {
                    "query": "请综合奇门、西占和六壬分析测试对象甲当前的状态",
                    "subject": {"name": "甲"},
                    "birth": payloads["qimen"],
                    "save_result": True,
                }
                dispatch = service.dispatch(dispatch_payload)
                queried_dispatch = service.store.query_runs(entity="甲", include_payload=True)
                dispatch_result = {
                    "ok": dispatch.ok,
                    "selected_tools": dispatch.selected_tools,
                    "memory_ref": dispatch.memory_ref.model_dump(mode="json") if dispatch.memory_ref else None,
                    "retrieved_runs": len(queried_dispatch),
                    "results_ok": {name: one.ok for name, one in dispatch.results.items()},
                    "selected_tools_covered": sorted(dispatch.selected_tools) == sorted(dispatch.result_export_contracts),
                    "result_export_contracts_ok": {
                        name: (
                            contract.get("has_export_snapshot") is True
                            and contract.get("has_export_format") is True
                            and bool(contract.get("selected_sections"))
                            and isinstance(contract.get("technique"), dict)
                            and bool(contract.get("technique", {}).get("key"))
                        )
                        for name, contract in dispatch.result_export_contracts.items()
                    },
                }
                knowledge_cases = {
                    "astro_aspect": {
                        "domain": "astro",
                        "category": "aspect",
                        "aspect_degree": 90,
                        "object_a": "Sun",
                        "object_b": "Jupiter",
                    },
                    "liureng_shen": {
                        "domain": "liureng",
                        "category": "shen",
                        "key": "子",
                    },
                    "qimen_door": {
                        "domain": "qimen",
                        "category": "door",
                        "key": "休门",
                    },
                }
                knowledge_reads: dict[str, dict] = {}
                for case_name, case_payload in knowledge_cases.items():
                    result = service.run_tool("knowledge_read", copy.deepcopy(case_payload), save_result=True)
                    queried = service.store.query_runs(tool="knowledge_read", include_payload=True, limit=20)
                    matched = next(
                        (
                            run
                            for run in queried
                            if run.get("artifacts")
                            and run["artifacts"][0].get("payload", {}).get("data", {}).get("domain") == case_payload["domain"]
                            and run["artifacts"][0].get("payload", {}).get("data", {}).get("category") == case_payload["category"]
                        ),
                        None,
                    )
                    artifact_payload = matched["artifacts"][0]["payload"] if matched else {}
                    knowledge_reads[case_name] = {
                        "ok": result.ok,
                        "domain": result.data.get("domain"),
                        "category": result.data.get("category"),
                        "title": result.data.get("title"),
                        "rendered_text_nonempty": bool(result.data.get("rendered_text")),
                        "lines_nonempty": bool(result.data.get("lines")),
                        "memory_ref": result.memory_ref.model_dump(mode="json") if result.memory_ref else None,
                        "artifact_payload_ok": artifact_payload.get("ok") is True if isinstance(artifact_payload, dict) else False,
                        "artifact_rendered_text_nonempty": bool(
                            artifact_payload.get("data", {}).get("rendered_text")
                        )
                        if isinstance(artifact_payload, dict)
                        else False,
                    }
                knowledge_result = {
                    "ok": all(item["ok"] and item["rendered_text_nonempty"] and item["artifact_payload_ok"] and item["artifact_rendered_text_nonempty"] for item in knowledge_reads.values()),
                    "cases": knowledge_reads,
                }
            finally:
                manager.stop_local_services()

    failed_tools = [item["tool"] for item in tool_results if not item["ok"] or item["retrieved_runs"] < 1 or not item["artifact_exists"] or not item["stored_payload_ok"]]
    missing_export = [
        item["tool"]
        for item in tool_results
        if not _contract_is_complete(item["tool"], item)
    ]
    dispatch_ok = bool(
        dispatch_result
        and dispatch_result["ok"]
        and dispatch_result["selected_tools_covered"]
        and all(dispatch_result["result_export_contracts_ok"].values())
    )
    knowledge_ok = bool(
        knowledge_result
        and knowledge_result["ok"]
    )
    return {
        "generated_at": datetime.now(ZoneInfo("America/Los_Angeles")).isoformat(),
        "tool_count": len(tool_results),
        "missing_payloads": missing_payloads,
        "extra_payloads": extra_payloads,
        "tools": tool_results,
        "dispatch": dispatch_result,
        "knowledge": knowledge_result,
        "failed_tools": failed_tools,
        "missing_export_contract_tools": missing_export,
        "ok": not missing_payloads and not extra_payloads and not failed_tools and not missing_export and dispatch_ok and knowledge_ok,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full Horosa skill self-check.")
    parser.add_argument("--output", type=Path, help="Optional output path for the JSON report.")
    parser.add_argument("--rounds", type=int, default=2, help="How many repeated runs to execute for each tool.")
    args = parser.parse_args()

    report = run_self_check(rounds=max(args.rounds, 1))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
