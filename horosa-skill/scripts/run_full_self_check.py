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
        report_result: dict | None = None
        with acquire_evaluation_lock(settings):
            manager.start_local_services()
            try:
                for tool_name in TOOL_DEFINITIONS:
                    payload = payloads[tool_name]
                    round_results: list[dict] = []
                    for round_index in range(1, rounds + 1):
                        result = service.run_tool(
                            tool_name,
                            copy.deepcopy(payload),
                            save_result=True,
                            query_text=f"{tool_name} 报告自检第 {round_index} 轮",
                        )
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
                    latest_run_id = round_results[-1]["memory_ref"]["run_id"] if round_results and round_results[-1].get("memory_ref") else None
                    report_template_ok = False
                    report_json_check = {
                        "ok": False,
                        "artifact_path": None,
                        "exists": False,
                        "file_size": 0,
                        "sha256": None,
                        "artifact_registered": False,
                        "artifact_meta_ok": False,
                        "coverage_ok": False,
                        "targeted_analysis_ok": False,
                        "quality_ok": False,
                        "delivery_checklist_ok": False,
                        "delivery_missing": [],
                        "readable_text_ok": False,
                        "search_index_ok": False,
                    }
                    if latest_run_id:
                        template = service.report_template({"run_id": latest_run_id, "tool_name": tool_name})
                        report_template_ok = (
                            template.get("schema") == "horosa.skill.report.template.v1"
                            and template.get("tool_name") == tool_name
                            and isinstance(template.get("targeted_analysis_contract"), dict)
                            and isinstance(template.get("question_analysis"), dict)
                            and template.get("question_analysis", {}).get("has_question") is True
                            and bool(template.get("targeted_analysis_contract", {}).get("answer_plan"))
                            and "direct_answer" in template.get("ai_fillable", {})
                            and bool(template.get("ai_fillable", {}).get("answer_plan"))
                            and (tool_name not in TOOL_EXPORT_TECHNIQUE_MAP or bool(template.get("source_export_sections")))
                            and (
                                tool_name not in TOOL_EXPORT_TECHNIQUE_MAP
                                or bool(template.get("source_context", {}).get("export_text"))
                            )
                            and (
                                tool_name not in TOOL_EXPORT_TECHNIQUE_MAP
                                or template.get("coverage_contract", {}).get("all_source_export_sections_required") is True
                            )
                        )
                        source_sections = template.get("source_export_sections") if isinstance(template.get("source_export_sections"), list) else []
                        ai_sections = [
                            {
                                "title": section.get("title"),
                                "body": f"自检解释：{section.get('title')}",
                                "evidence_lines": [section.get("title")],
                                "relevance_to_question": "用于回答当前自检问题。",
                            }
                            for section in source_sections
                            if isinstance(section, dict)
                        ]
                        rendered_report = service.report_render(
                            {
                                "run_id": latest_run_id,
                                "tool_name": tool_name,
                                "format": "json",
                                "ai_report": {
                                    "analysis_focus": f"{tool_name} 报告自检",
                                    "direct_answer": "报告可针对用户问题进行结构化解释。",
                                    "executive_summary": "报告自检摘要。",
                                    "analysis_sections": ai_sections,
                                    "evidence": [{"source": tool_name, "line": "self-check"}],
                                    "recommendations": ["继续保留本地报告 artifact。"],
                                    "limitations": [],
                                },
                                "include_raw_json": False,
                            }
                        )
                        rendered_path = Path(str(rendered_report.get("artifact_path", "")))
                        rendered_payload = json.loads(rendered_path.read_text(encoding="utf-8")) if rendered_path.is_file() else {}
                        queried_report = service.store.query_runs(run_id=latest_run_id, include_payload=False, limit=1)
                        artifacts = queried_report[0]["artifacts"] if queried_report else []
                        artifact_kinds = {artifact["kind"] for artifact in artifacts}
                        report_artifact = next((artifact for artifact in artifacts if artifact["kind"] == "report_json"), {})
                        coverage = rendered_payload.get("coverage") if isinstance(rendered_payload, dict) else {}
                        ai_coverage = rendered_payload.get("ai_coverage_status") if isinstance(rendered_payload, dict) else {}
                        report_index = rendered_payload.get("report_index") if isinstance(rendered_payload, dict) else {}
                        question_analysis = rendered_payload.get("question_analysis") if isinstance(rendered_payload, dict) else {}
                        report_quality = rendered_payload.get("report_quality") if isinstance(rendered_payload, dict) else {}
                        delivery_checklist = rendered_payload.get("delivery_checklist") if isinstance(rendered_payload, dict) else {}
                        coverage_matrix = rendered_payload.get("section_coverage_matrix") if isinstance(rendered_payload, dict) else {}
                        content_outline = rendered_payload.get("content_outline") if isinstance(rendered_payload, dict) else []
                        plain_text = rendered_payload.get("plain_text") if isinstance(rendered_payload, dict) else ""
                        search_index = rendered_payload.get("search_index") if isinstance(rendered_payload, dict) else {}
                        section_ids = {
                            section.get("id")
                            for section in rendered_payload.get("sections", [])
                            if isinstance(section, dict)
                        } if isinstance(rendered_payload, dict) else set()
                        report_json_check = {
                            "ok": rendered_report.get("ok") is True,
                            "artifact_path": rendered_report.get("artifact_path"),
                            "exists": rendered_path.is_file(),
                            "file_size": rendered_report.get("file_size", 0),
                            "sha256": rendered_report.get("sha256"),
                            "artifact_registered": "report_json" in artifact_kinds,
                            "artifact_meta_ok": (
                                report_artifact.get("exists") is True
                                and bool(report_artifact.get("file_size"))
                                and bool(report_artifact.get("sha256"))
                            ),
                            "coverage_ok": (
                                tool_name not in TOOL_EXPORT_TECHNIQUE_MAP
                                or (
                                    isinstance(coverage, dict)
                                    and coverage.get("all_source_export_sections_required") is True
                                    and bool(coverage.get("must_explain_sections"))
                                )
                            ),
                            "targeted_analysis_ok": (
                                isinstance(rendered_payload.get("targeted_analysis_contract"), dict)
                                and isinstance(report_index, dict)
                                and isinstance(question_analysis, dict)
                                and question_analysis.get("has_question") is True
                                and bool(report_index.get("answer_plan"))
                                and bool(report_index.get("targeted_answer_requirements"))
                                and report_index.get("ready_to_deliver") is True
                                and report_index.get("delivery_missing") == []
                                and report_index.get("storage", {}).get("managed_by") == "horosa_skill.memory"
                                and (
                                    tool_name not in TOOL_EXPORT_TECHNIQUE_MAP
                                    or (
                                        isinstance(ai_coverage, dict)
                                        and ai_coverage.get("status") == "complete"
                                        and ai_coverage.get("missing_sections") == []
                                        and ai_coverage.get("has_direct_answer") is True
                                        and ai_coverage.get("has_evidence") is True
                                    )
                                )
                            ),
                            "quality_ok": (
                                (
                                    tool_name not in TOOL_EXPORT_TECHNIQUE_MAP
                                    and {
                                    "report_quality",
                                    "report_metadata",
                                    "delivery_checklist",
                                    "question_analysis",
                                    "section_coverage_matrix",
                                    "ai_interpretation",
                                        "recommendations_limitations",
                                        "provenance",
                                    }.issubset(section_ids)
                                )
                                or (
                                    tool_name in TOOL_EXPORT_TECHNIQUE_MAP
                                    and isinstance(report_quality, dict)
                                    and report_quality.get("source_complete") is True
                                    and report_quality.get("ready_for_human_reading") is True
                                    and isinstance(coverage_matrix, dict)
                                    and coverage_matrix.get("all_sections_covered") is True
                                    and coverage_matrix.get("missing_section_titles") == []
                                    and {
                                        "report_quality",
                                        "report_metadata",
                                        "delivery_checklist",
                                        "question_analysis",
                                        "section_coverage_matrix",
                                        "ai_interpretation",
                                        "recommendations_limitations",
                                        "provenance",
                                    }.issubset(section_ids)
                                )
                            ),
                            "delivery_checklist_ok": (
                                isinstance(delivery_checklist, dict)
                                and delivery_checklist.get("schema") == "horosa.skill.report.delivery_checklist.v1"
                                and delivery_checklist.get("ready_to_deliver") is True
                                and delivery_checklist.get("missing") == []
                                and isinstance(delivery_checklist.get("checks"), dict)
                                and delivery_checklist.get("checks", {}).get("has_required_report_sections") is True
                                and delivery_checklist.get("checks", {}).get("has_search_index") is True
                                and (
                                    tool_name not in TOOL_EXPORT_TECHNIQUE_MAP
                                    or (
                                        delivery_checklist.get("checks", {}).get("has_source_export_text") is True
                                        and delivery_checklist.get("checks", {}).get("has_source_export_sections") is True
                                        and delivery_checklist.get("checks", {}).get("source_sections_covered") is True
                                    )
                                )
                            ),
                            "delivery_missing": delivery_checklist.get("missing", []) if isinstance(delivery_checklist, dict) else [],
                            "readable_text_ok": (
                                isinstance(content_outline, list)
                                and len(content_outline) == len(rendered_payload.get("sections", []))
                                and isinstance(plain_text, str)
                                and "报告质量检查" in plain_text
                                and "交付检查清单" in plain_text
                                and "报告元信息" in plain_text
                                and tool_name in plain_text
                                and "逐章解释覆盖矩阵" in plain_text
                                and "AI 解盘正文" in plain_text
                                and "来源追溯" in plain_text
                                and (tool_name not in TOOL_EXPORT_TECHNIQUE_MAP or "星阙 AI 导出正文" in plain_text)
                            ),
                            "search_index_ok": (
                                isinstance(search_index, dict)
                                and search_index.get("schema") == "horosa.skill.report.search_index.v1"
                                and search_index.get("tool_name") == tool_name
                                and bool(search_index.get("keywords"))
                                and isinstance(search_index.get("search_text"), str)
                                and "逐章解释覆盖矩阵" in search_index.get("search_text", "")
                                and "交付检查清单" in search_index.get("search_text", "")
                                and (
                                    tool_name not in TOOL_EXPORT_TECHNIQUE_MAP
                                    or bool(search_index.get("section_titles"))
                                )
                            ),
                        }
                    tool_results.append(
                        {
                            "tool": tool_name,
                            "ok": all(item["result_ok"] for item in round_results),
                            "rounds_requested": rounds,
                            "rounds": round_results,
                            "retrieved_runs": len(queried),
                            "artifact_exists": all(item["artifact_exists"] for item in round_results),
                            "stored_payload_ok": len(artifact_checks) >= rounds and all(item["stored_payload_ok"] for item in artifact_checks[:rounds]),
                            "report_template_ok": report_template_ok,
                            "report_json_ok": (
                                report_json_check["ok"]
                                and report_json_check["exists"]
                                and bool(report_json_check["file_size"])
                                and bool(report_json_check["sha256"])
                                and report_json_check["artifact_registered"]
                                and report_json_check["artifact_meta_ok"]
                                and report_json_check["coverage_ok"]
                                and report_json_check["targeted_analysis_ok"]
                                and report_json_check["quality_ok"]
                                and report_json_check["delivery_checklist_ok"]
                                and report_json_check["readable_text_ok"]
                                and report_json_check["search_index_ok"]
                            ),
                            "report_json": report_json_check,
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

                representative = next((item for item in tool_results if item["tool"] == "chart"), tool_results[0] if tool_results else None)
                representative_run_id = (
                    representative["rounds"][-1]["memory_ref"]["run_id"]
                    if representative and representative.get("rounds") and representative["rounds"][-1].get("memory_ref")
                    else None
                )
                report_formats: dict[str, dict] = {}
                if representative_run_id:
                    service.record_ai_answer(
                        {
                            "run_id": representative_run_id,
                            "user_question": "请生成结构化报告自检。",
                            "ai_answer": "这是 Horosa Skill 报告导出自检写回。",
                            "ai_answer_structured": {
                                "executive_summary": "报告导出自检摘要。",
                                "analysis_sections": [{"title": "自检", "body": "JSON、DOCX、PDF 均应可生成。"}],
                                "recommendations": ["确认 artifact 可检索。"],
                                "limitations": ["这是工程自检，不是正式解读。"],
                            },
                            "answer_meta": {"source": "run_full_self_check"},
                        }
                    )
                    for format_name in ("json", "docx", "pdf"):
                        rendered = service.report_render(
                            {
                                "run_id": representative_run_id,
                                "tool_name": representative["tool"],
                                "format": format_name,
                                "include_raw_json": format_name == "json",
                            }
                        )
                        report_formats[format_name] = {
                            "ok": rendered.get("ok") is True,
                            "artifact_path": rendered.get("artifact_path"),
                            "exists": Path(str(rendered.get("artifact_path", ""))).is_file(),
                            "file_size": rendered.get("file_size"),
                            "sha256": rendered.get("sha256"),
                        }
                    report_query = service.store.query_runs(run_id=representative_run_id, include_payload=False, limit=1)
                    artifact_kinds = {artifact["kind"] for artifact in report_query[0]["artifacts"]} if report_query else set()
                    report_pdf_query = service.store.query_runs(
                        text="结构化报告自检",
                        artifact_kind="report_pdf",
                        include_payload=False,
                        limit=5,
                    )
                    report_pdf_retrievable = any(
                        run.get("run_id") == representative_run_id
                        and any(artifact.get("kind") == "report_pdf" and artifact.get("exists") for artifact in run.get("artifacts", []))
                        and run.get("artifact_summary", {}).get("has_reports") is True
                        and run.get("artifact_summary", {}).get("latest_report", {}).get("kind") == "report_pdf"
                        for run in report_pdf_query
                    )
                    report_json_plain_text_query = service.store.query_runs(
                        run_id=representative_run_id,
                        text="逐章解释覆盖矩阵",
                        artifact_kind="report_json",
                        include_payload=False,
                        limit=1,
                    )
                    report_json_plain_text_retrievable = any(
                        run.get("run_id") == representative_run_id
                        and any(artifact.get("kind") == "report_json" and artifact.get("exists") for artifact in run.get("artifacts", []))
                        for run in report_json_plain_text_query
                    )
                    report_result = {
                        "ok": all(item["ok"] and item["exists"] and item["file_size"] for item in report_formats.values())
                        and {"report_json", "report_docx", "report_pdf"}.issubset(artifact_kinds)
                        and report_pdf_retrievable
                        and report_json_plain_text_retrievable,
                        "run_id": representative_run_id,
                        "tool": representative["tool"],
                        "formats": report_formats,
                        "artifact_kinds": sorted(artifact_kinds),
                        "report_pdf_retrievable_by_text": report_pdf_retrievable,
                        "report_json_plain_text_retrievable": report_json_plain_text_retrievable,
                    }

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

    failed_tools = [
        item["tool"]
        for item in tool_results
        if (
            not item["ok"]
            or item["retrieved_runs"] < 1
            or not item["artifact_exists"]
            or not item["stored_payload_ok"]
            or not item["report_template_ok"]
            or not item["report_json_ok"]
        )
    ]
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
    report_ok = bool(report_result and report_result["ok"])
    return {
        "generated_at": datetime.now(ZoneInfo("America/Los_Angeles")).isoformat(),
        "tool_count": len(tool_results),
        "missing_payloads": missing_payloads,
        "extra_payloads": extra_payloads,
        "tools": tool_results,
        "dispatch": dispatch_result,
        "knowledge": knowledge_result,
        "reports": report_result,
        "failed_tools": failed_tools,
        "missing_export_contract_tools": missing_export,
        "ok": not missing_payloads and not extra_payloads and not failed_tools and not missing_export and dispatch_ok and knowledge_ok and report_ok,
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
