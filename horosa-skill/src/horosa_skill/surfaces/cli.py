from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Optional

import typer

from horosa_skill.config import Settings
from horosa_skill.benchmark import run_benchmark
from horosa_skill.client_tools import (
    extract_json_value,
    isolated_data_dir,
    isolated_runtime_root,
    resolve_mcporter_command,
    resolve_uv_command,
)
from horosa_skill.errors import RuntimeError, ToolValidationError
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import run_mcp_server
from horosa_skill.tracing import TraceRecorder

app = typer.Typer(
    help=(
        "Horosa Skill CLI. Recommended path: install -> doctor -> serve. "
        "Use `ask` / `dispatch` for natural-language orchestration, `tool run` for direct method calls, "
        "and `memory show/query/answer` for local record management."
    )
)
tool_app = typer.Typer(help="Direct atomic method calls such as chart, qimen, liureng, and bazi.")
memory_app = typer.Typer(help="Inspect local records, show a single run, or attach the AI's final answer.")
export_app = typer.Typer(help="Inspect the Xingque AI export registry and parse exported text into structured JSON.")
knowledge_app = typer.Typer(help="Read bundled Xingque hover knowledge such as 星盘释义、大六壬地支提示、奇门象意。")
benchmark_app = typer.Typer(help="Run HorosaBench benchmark cases for routing, export parity, and knowledge quality.")
trace_app = typer.Typer(help="Inspect recent local trace records for tool runs, dispatches, and runtime operations.")
client_app = typer.Typer(help="Generate ready-to-paste client configs and run client-facing smoke checks such as OpenClaw / mcporter.")
app.add_typer(tool_app, name="tool")
app.add_typer(memory_app, name="memory")
app.add_typer(export_app, name="export")
app.add_typer(knowledge_app, name="knowledge")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(trace_app, name="trace")
app.add_typer(client_app, name="client")


def _service() -> HorosaSkillService:
    return HorosaSkillService(Settings.from_env())


def _runtime_manager(settings: Settings | None = None) -> HorosaRuntimeManager:
    return HorosaRuntimeManager(settings or Settings.from_env())


def _start_stdio_runtime_warmup(manager: HorosaRuntimeManager) -> None:
    def _warmup() -> None:
        try:
            manager.start_local_services()
        except RuntimeError:
            pass

    threading.Thread(target=_warmup, name="horosa-stdio-runtime-warmup", daemon=True).start()


def _tracer(settings: Settings | None = None) -> TraceRecorder:
    return TraceRecorder(settings or Settings.from_env())


def _load_payload(*, stdin: bool, input_file: Optional[Path]) -> dict:
    if stdin:
        raw = sys.stdin.read()
    elif input_file is not None:
        raw = input_file.read_text(encoding="utf-8")
    else:
        raise typer.BadParameter("Provide exactly one of --stdin or --input.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(data, dict):
        raise typer.BadParameter("Input JSON must be an object.")
    return data


def _print_json(data: object) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))


def _package_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_skill_root(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    if (candidate / "pyproject.toml").exists():
        return candidate
    nested = candidate / "horosa-skill"
    if (nested / "pyproject.toml").exists():
        return nested
    raise typer.BadParameter("Path must point to the horosa-skill package directory or the repo root that contains it.")


def _build_openclaw_server_block(
    *,
    skill_root: Path,
    isolate_home: Path | None,
) -> dict[str, Any]:
    skill_root = skill_root.expanduser().resolve()
    uv_command = resolve_uv_command()
    serve_args = [
        "run",
        "--directory",
        str(skill_root),
        "horosa-skill",
        "serve",
        "--transport",
        "stdio",
    ]
    if isolate_home is None:
        return {
            "command": uv_command[0],
            "args": [*uv_command[1:], *serve_args],
            "cwd": str(skill_root),
        }

    home_dir = isolate_home.expanduser().resolve()
    runtime_root = isolated_runtime_root(home_dir)
    data_dir = isolated_data_dir(home_dir)
    server_block = {
        "command": uv_command[0],
        "args": [*uv_command[1:], *serve_args],
        "cwd": str(skill_root),
        "env": {
            "HOME": str(home_dir),
            "HOROSA_RUNTIME_ROOT": str(runtime_root),
            "HOROSA_SKILL_DATA_DIR": str(data_dir),
        },
    }
    if os.name == "nt":
        server_block["env"]["USERPROFILE"] = str(home_dir)
    return server_block


def _build_openclaw_config(
    *,
    skill_root: Path,
    server_name: str,
    format_name: str,
    isolate_home: Path | None,
) -> dict[str, Any]:
    server_block = _build_openclaw_server_block(
        skill_root=skill_root,
        isolate_home=isolate_home,
    )
    if format_name == "mcporter":
        return {"mcpServers": {server_name: server_block}}
    if format_name == "openclaw":
        return {"mcp": {"servers": {server_name: server_block}}}
    raise typer.BadParameter("`--format` must be either `mcporter` or `openclaw`.")


def _run_subprocess_json(command: list[str], *, cwd: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(str(exc), code="client.command_not_found", details={"command": command, "cwd": str(cwd)}) from exc
    parsed: dict[str, Any] | None = None
    for candidate in (result.stdout, result.stderr):
        try:
            candidate_value = extract_json_value(candidate or "")
        except ValueError:
            continue
        if isinstance(candidate_value, dict):
            parsed = candidate_value
            break
    if result.returncode != 0 and parsed is None:
        raise RuntimeError(
            result.stderr.strip() or result.stdout.strip() or "Command failed",
            code="client.command_failed",
            details={"command": command, "cwd": str(cwd), "returncode": result.returncode},
        )
    if parsed is not None:
        return parsed
    raise RuntimeError(
        f"Command did not return JSON: {' '.join(command)}",
        code="client.invalid_json",
        details={
            "command": command,
            "cwd": str(cwd),
            "stdout": (result.stdout or "")[-4000:],
            "stderr": (result.stderr or "")[-4000:],
        },
    )


def _is_mcporter_timeout_response(payload: dict[str, Any]) -> bool:
    issue = payload.get("issue")
    if not isinstance(issue, dict) or issue.get("kind") != "offline":
        return False
    text = f"{payload.get('error', '')}\n{issue.get('rawMessage', '')}".lower()
    return "timed out" in text


@app.command()
def install(
    archive: str | None = typer.Option(None, help="Local archive path or URL to a runtime asset."),
    manifest_url: str | None = typer.Option(None, help="Release manifest URL that maps platforms to runtime archives."),
    force: bool = typer.Option(False, help="Reinstall even if the same runtime version is already present."),
) -> None:
    settings = Settings.from_env()
    manager = _runtime_manager(settings)
    try:
        result = manager.install(archive=archive, manifest_url=manifest_url, force=force)
    except RuntimeError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result)


@app.command()
def doctor() -> None:
    settings = Settings.from_env()
    manager = _runtime_manager(settings)
    _print_json(manager.doctor())


@app.command()
def stop() -> None:
    settings = Settings.from_env()
    manager = _runtime_manager(settings)
    try:
        result = manager.stop_local_services()
    except RuntimeError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result)


@app.command()
def serve(
    transport: str = typer.Option("streamable-http", help="MCP transport: streamable-http or stdio."),
    host: str = typer.Option("127.0.0.1", help="Host for streamable HTTP."),
    port: int = typer.Option(8765, help="Port for streamable HTTP."),
    skip_runtime_start: bool = typer.Option(False, help="Do not auto-start the installed offline runtime."),
) -> None:
    settings = Settings.from_env()
    settings.host = host
    settings.port = port
    manager = _runtime_manager(settings)
    service = HorosaSkillService(settings, runtime_manager=manager)
    started_now = False
    if not skip_runtime_start:
        if transport == "stdio":
            _start_stdio_runtime_warmup(manager)
        else:
            try:
                start_result = manager.start_local_services()
                started_now = not start_result.get("already_running", False)
            except RuntimeError as exc:
                typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
                raise typer.Exit(code=2)
    try:
        run_mcp_server(settings, transport=transport, service=service)
    finally:
        # For stdio clients such as OpenClaw/mcporter, keeping the runtime warm
        # avoids a full local Java+Python restart on every tool call.
        if started_now and transport != "stdio":
            try:
                manager.stop_local_services()
            except RuntimeError:
                pass


@tool_app.command("list")
def tool_list() -> None:
    _print_json(_service().list_tools())


@tool_app.command("run")
def tool_run(
    tool_name: str,
    stdin: bool = typer.Option(False, "--stdin", help="Read a JSON object from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read a JSON object from a file."),
    save_result: bool = typer.Option(True, help="Persist the result in local memory."),
    query_text: str | None = typer.Option(None, help="Optional original user question to store together with this run."),
) -> None:
    payload = _load_payload(stdin=stdin, input_file=input_file)
    service = _service()
    try:
        result = service.run_tool(tool_name, payload, save_result=save_result, query_text=query_text)
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result.model_dump(mode="json"))


@export_app.command("registry")
def export_registry(
    technique: str | None = typer.Option(None, help="Return only one technique block."),
    save_result: bool = typer.Option(False, help="Persist the result in local memory."),
) -> None:
    service = _service()
    result = service.run_tool("export_registry", {"technique": technique} if technique else {}, save_result=save_result)
    _print_json(result.model_dump(mode="json"))


@export_app.command("parse")
def export_parse(
    stdin: bool = typer.Option(False, "--stdin", help="Read a JSON object from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read a JSON object from a file."),
    save_result: bool = typer.Option(False, help="Persist the result in local memory."),
) -> None:
    payload = _load_payload(stdin=stdin, input_file=input_file)
    service = _service()
    try:
        result = service.run_tool("export_parse", payload, save_result=save_result)
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result.model_dump(mode="json"))


@knowledge_app.command("registry")
def knowledge_registry(
    domain: str | None = typer.Option(None, help="Optional knowledge domain filter: astro, liureng, qimen."),
    save_result: bool = typer.Option(False, help="Persist the result in local memory."),
) -> None:
    service = _service()
    result = service.run_tool("knowledge_registry", {"domain": domain} if domain else {}, save_result=save_result)
    _print_json(result.model_dump(mode="json"))


@knowledge_app.command("read")
def knowledge_read(
    stdin: bool = typer.Option(False, "--stdin", help="Read a JSON object from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read a JSON object from a file."),
    save_result: bool = typer.Option(False, help="Persist the result in local memory."),
) -> None:
    payload = _load_payload(stdin=stdin, input_file=input_file)
    service = _service()
    try:
        result = service.run_tool("knowledge_read", payload, save_result=save_result)
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result.model_dump(mode="json"))


@app.command()
def dispatch(
    stdin: bool = typer.Option(False, "--stdin", help="Read a JSON object from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read a JSON object from a file."),
) -> None:
    payload = _load_payload(stdin=stdin, input_file=input_file)
    service = _service()
    try:
        result = service.dispatch(payload)
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result.model_dump(mode="json"))


@app.command(help="Friendly alias of `dispatch` for natural-language use.")
def ask(
    stdin: bool = typer.Option(False, "--stdin", help="Read a JSON object from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read a JSON object from a file."),
) -> None:
    dispatch(stdin=stdin, input_file=input_file)


@benchmark_app.command("run")
def benchmark_run(
    dataset: Optional[Path] = typer.Option(None, help="Optional benchmark dataset JSON path."),
    skip_runtime: bool = typer.Option(False, help="Skip runtime-backed cases and run only local knowledge / metadata checks."),
    save_result: bool = typer.Option(False, help="Persist benchmark tool outputs into the local record layer."),
) -> None:
    settings = Settings.from_env()
    report = run_benchmark(settings=settings, dataset_path=dataset, skip_runtime=skip_runtime, save_result=save_result)
    _print_json(report)


@trace_app.command("latest")
def trace_latest(
    limit: int = typer.Option(30, help="How many recent trace rows to print from the newest local trace file."),
) -> None:
    tracer = _tracer()
    _print_json(
        {
            "enabled": tracer.enabled,
            "files": [str(path) for path in tracer.latest_trace_files(limit=3)],
            "events": tracer.read_latest(limit=max(1, limit)),
        }
    )


@client_app.command("openclaw-config")
def client_openclaw_config(
    skill_root: Path = typer.Option(
        _package_root(),
        help="Path to the horosa-skill package directory, or the repo root that contains it.",
    ),
    format_name: str = typer.Option(
        "mcporter",
        "--format",
        help="Output config format: mcporter or openclaw.",
    ),
    server_name: str = typer.Option("horosa", help="Server name key written into the MCP config."),
    isolate_home: Path | None = typer.Option(
        None,
        help="Optional HOME directory to embed for fully isolated installs and smoke tests.",
    ),
    write: Path | None = typer.Option(
        None,
        help="Optional output file path. When set, the config is written there and also printed to stdout.",
    ),
) -> None:
    resolved_skill_root = _resolve_skill_root(skill_root)
    payload = _build_openclaw_config(
        skill_root=resolved_skill_root,
        server_name=server_name,
        format_name=format_name,
        isolate_home=isolate_home,
    )
    if write is not None:
        output_path = write.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_json(payload)


@client_app.command("openclaw-check")
def client_openclaw_check(
    workspace: Path = typer.Option(
        Path.home() / ".openclaw" / "workspace",
        help="OpenClaw workspace root. The default assumes ~/.openclaw/workspace.",
    ),
    config: Path | None = typer.Option(
        None,
        help="Explicit mcporter config path. Defaults to <workspace>/config/mcporter.json.",
    ),
    full: bool = typer.Option(
        False,
        help="Run the exhaustive 39-tool OpenClaw self-check instead of a quick smoke check.",
    ),
    output: Path | None = typer.Option(
        None,
        help="Optional report path. Defaults to a JSON file in the Horosa data directory.",
    ),
) -> None:
    settings = Settings.from_env()
    workspace_root = workspace.expanduser().resolve()
    config_path = (config.expanduser().resolve() if config is not None else workspace_root / "config" / "mcporter.json")
    if not config_path.exists():
        raise typer.BadParameter(f"mcporter config not found: {config_path}")

    default_output = settings.data_dir / ("openclaw_full_check.json" if full else "openclaw_smoke_check.json")
    output_path = (output.expanduser().resolve() if output is not None else default_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if full:
        script_path = _package_root() / "scripts" / "run_openclaw_full_self_check.py"
        command = [
            sys.executable,
            str(script_path),
            "--workspace",
            str(workspace_root),
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if output_path.exists():
            report = json.loads(output_path.read_text(encoding="utf-8"))
            _print_json(report)
        else:
            typer.echo(result.stderr or result.stdout, err=True)
        if result.returncode != 0:
            raise typer.Exit(code=2)
        return

    call_timeout_ms = 120000
    list_result = _run_subprocess_json(
        [
            *resolve_mcporter_command(),
            "list",
            "horosa",
            "--json",
            "--config",
            str(config_path),
            "--root",
            str(workspace_root),
        ],
        cwd=workspace_root,
    )
    registry_result = _run_subprocess_json(
        [
            *resolve_mcporter_command(),
            "call",
            "horosa.horosa_knowledge_registry",
            "--output",
            "json",
            "--config",
            str(config_path),
            "--root",
            str(workspace_root),
            "--timeout",
            str(call_timeout_ms),
        ],
        cwd=workspace_root,
    )
    chart_payload = {
        "date": "2026-04-04",
        "time": "15:58:35",
        "zone": "+08:00",
        "lat": "26n04",
        "lon": "119e19",
    }
    chart_result = _run_subprocess_json(
        [
            *resolve_mcporter_command(),
            "call",
            "horosa.horosa_astro_chart",
            "--args",
            json.dumps(chart_payload, ensure_ascii=False),
            "--output",
            "json",
            "--config",
            str(config_path),
            "--root",
            str(workspace_root),
            "--timeout",
            str(call_timeout_ms),
        ],
        cwd=workspace_root,
    )
    if _is_mcporter_timeout_response(chart_result):
        chart_result = _run_subprocess_json(
            [
                *resolve_mcporter_command(),
                "call",
                "horosa.horosa_astro_chart",
                "--args",
                json.dumps(chart_payload, ensure_ascii=False),
                "--output",
                "json",
                "--config",
                str(config_path),
                "--root",
                str(workspace_root),
                "--timeout",
                str(call_timeout_ms),
            ],
            cwd=workspace_root,
        )
    run_id = (chart_result.get("memory_ref") or {}).get("run_id")
    memory_show = _run_subprocess_json(
        [
            *resolve_mcporter_command(),
            "call",
            "horosa.horosa_memory_show",
            "--args",
            json.dumps({"run_id": run_id, "include_payload": False}, ensure_ascii=False),
            "--output",
            "json",
            "--config",
            str(config_path),
            "--root",
            str(workspace_root),
            "--timeout",
            str(call_timeout_ms),
        ],
        cwd=workspace_root,
    )
    report = {
        "workspace": str(workspace_root),
        "config": str(config_path),
        "server_visible": list_result.get("status") == "ok",
        "listed_tool_count": len(list_result.get("tools", [])),
        "knowledge_registry_ok": registry_result.get("ok") is True,
        "chart_ok": chart_result.get("ok") is True,
        "memory_show_ok": memory_show.get("ok") is True,
        "run_id": run_id,
        "artifact_path": (chart_result.get("memory_ref") or {}).get("artifact_path"),
        "ok": (
            list_result.get("status") == "ok"
            and registry_result.get("ok") is True
            and chart_result.get("ok") is True
            and memory_show.get("ok") is True
        ),
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_json(report)
    if not report["ok"]:
        raise typer.Exit(code=2)


@memory_app.command("query")
def memory_query(
    run_id: str | None = typer.Option(None, help="Filter by exact run id."),
    tool: str | None = typer.Option(None, help="Filter by tool name."),
    entity: str | None = typer.Option(None, help="Filter by entity name."),
    after: str | None = typer.Option(None, help="Only return runs created after this ISO timestamp."),
    before: str | None = typer.Option(None, help="Only return runs created before this ISO timestamp."),
    limit: int = typer.Option(20, help="Maximum runs to return."),
    include_payload: bool = typer.Option(True, "--include-payload/--no-include-payload", help="Embed saved JSON payloads in the query output."),
) -> None:
    service = _service()
    data = service.store.query_runs(
        run_id=run_id,
        tool=tool,
        entity=entity,
        after=after,
        before=before,
        limit=limit,
        include_payload=include_payload,
    )
    _print_json(data)


@memory_app.command("show")
def memory_show(
    run_id: str = typer.Argument(..., help="Exact run id to display."),
    include_payload: bool = typer.Option(True, "--include-payload/--no-include-payload", help="Embed saved JSON payloads in the output."),
) -> None:
    service = _service()
    data = service.store.query_runs(run_id=run_id, limit=1, include_payload=include_payload)
    if not data:
        typer.echo(json.dumps({"ok": False, "code": "memory.run.not_found", "message": f"Run not found: {run_id}", "details": {}}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(data[0])


@memory_app.command("answer")
def memory_answer(
    stdin: bool = typer.Option(False, "--stdin", help="Read a JSON object from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read a JSON object from a file."),
) -> None:
    payload = _load_payload(stdin=stdin, input_file=input_file)
    service = _service()
    try:
        result = service.record_ai_answer(payload)
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    except ValueError as exc:
        typer.echo(json.dumps({"ok": False, "code": "memory.answer.unknown_run", "message": str(exc), "details": {}}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result)


if __name__ == "__main__":
    app()
