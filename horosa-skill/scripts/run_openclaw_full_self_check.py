from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from horosa_skill.client_tools import resolve_mcporter_command
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.testing_payloads import build_sample_payloads


DEFAULT_WORKSPACE = Path("/Users/horacedong/.openclaw/workspace")
DEFAULT_OUTPUT = Path.home() / ".horosa-skill" / "self_check_report_openclaw_full.json"


def _run_mcporter(workspace: Path, selector: str, payload: dict[str, Any], *, timeout_ms: int = 120000) -> dict[str, Any]:
    command = [
        *resolve_mcporter_command(),
        "call",
        selector,
        "--args",
        json.dumps(payload, ensure_ascii=False),
        "--output",
        "json",
        "--timeout",
        str(timeout_ms),
    ]
    result = subprocess.run(
        command,
        cwd=str(workspace),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"mcporter call failed: {selector}")
    return json.loads(result.stdout)


def _run_mcporter_list(workspace: Path, *, timeout_ms: int = 120000) -> dict[str, Any]:
    command = [*resolve_mcporter_command(), "list", "horosa", "--json"]
    result = subprocess.run(
        command,
        cwd=str(workspace),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_ms / 1000,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "mcporter list failed")
    return json.loads(result.stdout)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _has_export_contract(tool_name: str, response: dict[str, Any]) -> bool:
    data = response.get("data", {})
    if tool_name in {"export_registry", "export_parse", "knowledge_registry", "knowledge_read"}:
        return True
    return isinstance(data, dict) and isinstance(data.get("export_snapshot"), dict) and isinstance(data.get("export_format"), dict)


def _check_one_tool(workspace: Path, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    definition = TOOL_DEFINITIONS[tool_name]
    selector = f"horosa.{definition.mcp_name}"
    response = _run_mcporter(workspace, selector, payload)

    _assert(response.get("ok") is True, f"{tool_name}: ok != true")
    memory_ref = response.get("memory_ref") or {}
    run_id = memory_ref.get("run_id")
    artifact_path = memory_ref.get("artifact_path")
    _assert(isinstance(run_id, str) and run_id, f"{tool_name}: missing run_id")
    _assert(isinstance(artifact_path, str) and Path(artifact_path).exists(), f"{tool_name}: artifact missing")
    _assert(_has_export_contract(tool_name, response), f"{tool_name}: missing export contract")

    show_result = _run_mcporter(
        workspace,
        "horosa.horosa_memory_show",
        {"run_id": run_id, "include_payload": False},
    )
    _assert(show_result.get("ok") is True, f"{tool_name}: memory_show failed")
    _assert(show_result.get("result", {}).get("run_id") == run_id, f"{tool_name}: memory_show wrong run")

    query_result = _run_mcporter(
        workspace,
        "horosa.horosa_memory_query",
        {"run_id": run_id, "tool": tool_name, "include_payload": False, "limit": 5},
    )
    _assert(query_result.get("ok") is True, f"{tool_name}: memory_query failed")
    results = query_result.get("results") or []
    _assert(any(item.get("run_id") == run_id for item in results if isinstance(item, dict)), f"{tool_name}: memory_query missing run")

    return {
        "selector": selector,
        "run_id": run_id,
        "artifact_path": artifact_path,
        "trace_id": response.get("trace_id"),
        "group_id": response.get("group_id"),
        "has_export_snapshot": isinstance(response.get("data", {}).get("export_snapshot"), dict),
        "has_export_format": isinstance(response.get("data", {}).get("export_format"), dict),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run every Horosa MCP tool through OpenClaw/mcporter and verify call/return/store/read/find.")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    workspace = args.workspace.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payloads = build_sample_payloads()
    report: dict[str, Any] = {
        "workspace": str(workspace),
        "server": "horosa",
        "tool_count": 0,
        "passed_tools": [],
        "failed_tools": {},
        "tools": {},
        "dispatch": {},
        "answer_writeback": {},
        "memory_tools": {},
        "ok": False,
    }

    try:
        list_result = _run_mcporter_list(workspace)
        _assert(list_result.get("status") == "ok", "mcporter list did not return ok")
        report["server_visible"] = True
        report["listed_tool_count"] = len(list_result.get("tools", []))
    except Exception as exc:  # noqa: BLE001
        report["server_visible"] = False
        report["bootstrap_error"] = str(exc)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    for tool_name in TOOL_DEFINITIONS:
        report["tool_count"] += 1
        try:
            report["tools"][tool_name] = _check_one_tool(workspace, tool_name, payloads[tool_name])
            report["passed_tools"].append(tool_name)
        except Exception as exc:  # noqa: BLE001
            report["failed_tools"][tool_name] = str(exc)

    try:
        dispatch_payload = {
            "query": "请起一局奇门遁甲并返回结构化结果",
            "birth": payloads["qimen"],
            "save_result": True,
        }
        dispatch_result = _run_mcporter(workspace, "horosa.horosa_dispatch", dispatch_payload)
        _assert(dispatch_result.get("ok") is True, "dispatch: ok != true")
        dispatch_memory = dispatch_result.get("memory_ref") or {}
        dispatch_run_id = dispatch_memory.get("run_id")
        _assert(isinstance(dispatch_run_id, str) and dispatch_run_id, "dispatch: missing run_id")
        dispatch_show = _run_mcporter(workspace, "horosa.horosa_memory_show", {"run_id": dispatch_run_id, "include_payload": False})
        dispatch_query = _run_mcporter(workspace, "horosa.horosa_memory_query", {"run_id": dispatch_run_id, "include_payload": False, "limit": 5})
        _assert(dispatch_show.get("ok") is True, "dispatch: memory_show failed")
        _assert(dispatch_query.get("ok") is True, "dispatch: memory_query failed")
        _assert(bool(dispatch_result.get("result_export_contracts")), "dispatch: missing result_export_contracts")
        report["dispatch"] = {
            "ok": True,
            "run_id": dispatch_run_id,
            "selected_tools": dispatch_result.get("selected_tools", []),
            "artifact_path": dispatch_memory.get("artifact_path"),
        }
    except Exception as exc:  # noqa: BLE001
        report["dispatch"] = {"ok": False, "error": str(exc)}

    try:
        representative = report["tools"].get("chart") or next(iter(report["tools"].values()))
        run_id = representative["run_id"]
        answer_result = _run_mcporter(
            workspace,
            "horosa.horosa_memory_record_answer",
            {
                "run_id": run_id,
                "user_question": "这次结果代表什么？",
                "ai_answer": "这是 OpenClaw 全量联调写回测试。",
                "ai_answer_structured": {"status": "ok", "source": "openclaw-full-self-check"},
                "answer_meta": {"mode": "openclaw", "scope": "full"},
            },
        )
        _assert(answer_result.get("ok") is True, "memory_record_answer failed")
        show_after = _run_mcporter(workspace, "horosa.horosa_memory_show", {"run_id": run_id, "include_payload": False})
        result_record = show_after.get("result", {})
        _assert(result_record.get("ai_answer_text") == "这是 OpenClaw 全量联调写回测试。", "memory_show missing ai_answer_text")
        report["answer_writeback"] = {"ok": True, "run_id": run_id, "manifest_path": answer_result.get("manifest_path")}
    except Exception as exc:  # noqa: BLE001
        report["answer_writeback"] = {"ok": False, "error": str(exc)}

    report["memory_tools"] = {
        "show_available": "horosa_memory_show",
        "query_available": "horosa_memory_query",
        "record_answer_available": "horosa_memory_record_answer",
    }
    report["ok"] = not report["failed_tools"] and report["dispatch"].get("ok") is True and report["answer_writeback"].get("ok") is True

    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
