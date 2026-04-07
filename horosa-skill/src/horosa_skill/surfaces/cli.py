from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
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
        "Horosa Skill CLI. Recommended OpenClaw path: `client openclaw-setup`. "
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
client_app = typer.Typer(help="Default OpenClaw entry: `openclaw-setup`. Also generate configs and run smoke checks for OpenClaw / mcporter.")
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
    server_block = {
        "command": uv_command[0],
        "args": [*uv_command[1:], *serve_args],
        "cwd": str(skill_root),
        "env": _isolated_env_vars(home_dir),
    }
    return server_block


def _isolated_env_vars(home_dir: Path) -> dict[str, str]:
    resolved_home = home_dir.expanduser().resolve()
    env = {
        "HOME": str(resolved_home),
        "HOROSA_RUNTIME_ROOT": str(isolated_runtime_root(resolved_home)),
        "HOROSA_SKILL_DATA_DIR": str(isolated_data_dir(resolved_home)),
    }
    if os.name == "nt":
        env["USERPROFILE"] = str(resolved_home)
    return env


@contextmanager
def _temporary_env(overrides: dict[str, str]):
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _write_json_file(path: Path, payload: object) -> Path:
    output_path = path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _timed_call(callback):
    started_at = time.perf_counter()
    result = callback()
    return result, round(time.perf_counter() - started_at, 3)


def _quote_cli_arg(value: str) -> str:
    return f'"{value}"' if any(char.isspace() for char in value) else value


def _format_cli_command(parts: list[str]) -> str:
    return " ".join(_quote_cli_arg(part) for part in parts)


def _openclaw_setup_command(workspace_root: Path | str = "<your-openclaw-workspace>") -> str:
    return _format_cli_command(
        [
            "uv",
            "run",
            "horosa-skill",
            "client",
            "openclaw-setup",
            "--workspace",
            str(workspace_root),
        ]
    )


def _openclaw_check_command(workspace_root: Path | str, config_path: Path | str | None = None) -> str:
    command = [
        "uv",
        "run",
        "horosa-skill",
        "client",
        "openclaw-check",
        "--workspace",
        str(workspace_root),
    ]
    if config_path is not None:
        command.extend(["--config", str(config_path)])
    return _format_cli_command(command)


def _doctor_summary(report: dict[str, Any]) -> dict[str, Any]:
    issues = [str(issue) for issue in report.get("issues", [])]
    reachable_endpoints = [
        endpoint.get("label")
        for endpoint in report.get("endpoints", [])
        if endpoint.get("reachable") is True
    ]
    installed = report.get("installed") is True
    ready_for_openclaw = installed and not issues
    if ready_for_openclaw:
        user_summary = "Ready. The offline runtime is installed and the local Horosa endpoints are responding."
        next_action = "Open OpenClaw, or rerun `uv run horosa-skill client openclaw-check --workspace <your-openclaw-workspace>` any time you want a fresh smoke report."
    elif not installed:
        user_summary = "The offline runtime is not installed yet."
        next_action = f"Run `{_openclaw_setup_command()}` to install the runtime, write a config, and verify the OpenClaw path."
    elif issues == ["services:not_running"]:
        user_summary = "The runtime files are installed, but the local Horosa services are not running yet."
        next_action = f"Run `{_openclaw_setup_command()}` to start the runtime and verify the OpenClaw path."
    else:
        user_summary = "Horosa still has runtime issues that need attention before OpenClaw will be fully ready."
        next_action = "Review the `issues` list below, fix the blocking item, then rerun `uv run horosa-skill doctor`."
    return {
        "status": "ready" if ready_for_openclaw else "needs_attention",
        "ready_for_openclaw": ready_for_openclaw,
        "user_summary": user_summary,
        "next_action": next_action,
        "reachable_endpoints": reachable_endpoints,
    }


def _failed_smoke_checks(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for field in ("server_visible", "knowledge_registry_ok", "chart_ok", "memory_show_ok"):
        if report.get(field) is not True:
            failures.append(field)
    return failures


def _smoke_summary(
    report: dict[str, Any],
    *,
    workspace_root: Path,
    config_path: Path,
) -> dict[str, Any]:
    failed_checks = _failed_smoke_checks(report)
    ready_for_openclaw = report.get("ok") is True
    list_checked = report.get("list_checked", True)
    if ready_for_openclaw:
        if list_checked:
            user_summary = (
                f"Ready. OpenClaw can see Horosa, list {report.get('listed_tool_count', 0)} tools, "
                "run a chart, save the result, and read it back."
            )
        else:
            user_summary = "Ready. Horosa passed the quick OpenClaw smoke check: call, compute, save, and readback all worked."
        next_action = f"Open OpenClaw and use the config at {config_path}."
    elif "server_visible" in failed_checks or "knowledge_registry_ok" in failed_checks:
        user_summary = "OpenClaw did not get a healthy response from the Horosa server."
        next_action = f"Run `{_openclaw_check_command(workspace_root, config_path)}` after you confirm the runtime is installed and mcporter is available."
    elif "chart_ok" in failed_checks:
        user_summary = "OpenClaw reached Horosa, but the chart test call did not finish successfully."
        next_action = f"Run `{_openclaw_check_command(workspace_root, config_path)}` again after `uv run horosa-skill doctor` confirms the runtime is healthy."
    else:
        user_summary = "OpenClaw computed a result, but the saved chart could not be read back cleanly."
        next_action = f"Run `{_openclaw_check_command(workspace_root, config_path)}` again to confirm the readback path."
    return {
        "status": "ready" if ready_for_openclaw else "needs_attention",
        "ready_for_openclaw": ready_for_openclaw,
        "user_summary": user_summary,
        "next_action": next_action,
        "recheck_command": _openclaw_check_command(workspace_root, config_path),
        "failed_checks": failed_checks,
        "checks": {
            "server_visible": report.get("server_visible") is True,
            "knowledge_registry_ok": report.get("knowledge_registry_ok") is True,
            "chart_ok": report.get("chart_ok") is True,
            "memory_show_ok": report.get("memory_show_ok") is True,
        },
    }


def _setup_summary(
    *,
    workspace_root: Path,
    config_path: Path,
    home_dir: Path,
    doctor_issues: list[str],
    smoke_report: dict[str, Any] | None,
    skip_smoke: bool,
) -> dict[str, Any]:
    smoke_ready = (smoke_report or {}).get("ok") is True
    ready_for_openclaw = not doctor_issues and (skip_smoke or smoke_ready)
    if ready_for_openclaw and not skip_smoke:
        user_summary = "Ready. Horosa installed the runtime, wrote the OpenClaw config, and passed the quick smoke check."
        next_action = f"Open OpenClaw and use the config at {config_path}."
    elif ready_for_openclaw:
        user_summary = "Setup finished and the local runtime looks healthy, but the smoke check was skipped."
        next_action = f"Run `{_openclaw_check_command(workspace_root, config_path)}` before relying on the OpenClaw path."
    elif doctor_issues:
        user_summary = "Setup finished the install, but the local runtime still needs attention before OpenClaw is fully ready."
        next_action = "Run `uv run horosa-skill doctor` to inspect the runtime issues, then rerun the setup command."
    else:
        user_summary = "Setup wrote the config, but the OpenClaw smoke check did not complete every required step."
        next_action = f"Run `{_openclaw_check_command(workspace_root, config_path)}` again after `uv run horosa-skill doctor` looks healthy."
    return {
        "status": "ready" if ready_for_openclaw else "needs_attention",
        "ready_for_openclaw": ready_for_openclaw,
        "user_summary": user_summary,
        "next_action": next_action,
        "default_entry": _openclaw_setup_command(workspace_root),
        "recheck_command": _openclaw_check_command(workspace_root, config_path),
        "config_written_to": str(config_path),
        "local_home": str(home_dir),
    }


def _friendly_runtime_error_payload(
    exc: RuntimeError,
    *,
    action_label: str,
    workspace_root: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    retry_command: str | None = None
    if action_label == "OpenClaw setup" and workspace_root is not None:
        retry_command = _openclaw_setup_command(workspace_root)
    elif workspace_root is not None:
        retry_command = _openclaw_check_command(workspace_root, config_path)

    next_action = "Review the error details below and rerun the command."
    user_summary = f"{action_label} did not finish successfully."
    code = exc.code or ""
    command = [str(part) for part in exc.details.get("command", [])] if isinstance(exc.details, dict) else []
    command_text = " ".join(command).lower()
    if code == "client.command_not_found" and "mcporter" in command_text:
        user_summary = f"{action_label} could not find `mcporter` on this machine."
        next_action = (
            "Install it with `npm i -g mcporter`, or set `HOROSA_MCPORTER_BIN`, "
            + (f"then rerun `{retry_command}`." if retry_command else "then rerun the command.")
        )
    elif code == "client.command_not_found" and "uv" in command_text:
        user_summary = f"{action_label} could not find `uv`."
        next_action = "Install uv, or set `HOROSA_UV_BIN`, then rerun the command."
    elif code.startswith("runtime.install") or code == "runtime.not_installed":
        user_summary = f"{action_label} could not finish installing the offline runtime."
        next_action = "Check your network access to the Horosa runtime release and rerun the setup command."
    elif code.startswith("runtime.start"):
        user_summary = f"{action_label} installed the runtime, but the local Horosa services did not start cleanly."
        next_action = "Run `uv run horosa-skill doctor` for more details, then rerun the setup command."
    elif code in {"client.command_failed", "client.invalid_json"}:
        user_summary = f"{action_label} started the OpenClaw client command, but it did not return a clean JSON result."
        next_action = "Run `uv run horosa-skill doctor` and make sure mcporter can start Horosa, then retry the smoke check."

    payload = {
        "ok": False,
        "status": "needs_attention",
        "ready_for_openclaw": False,
        "user_summary": user_summary,
        "next_action": next_action,
        "code": exc.code,
        "message": str(exc),
        "details": exc.details,
    }
    if retry_command is not None:
        payload["retry_command"] = retry_command
    return payload


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


def _run_openclaw_smoke_check(
    *,
    workspace_root: Path,
    config_path: Path,
    output_path: Path,
    include_list: bool = True,
) -> dict[str, Any]:
    call_timeout_ms = 120000
    list_result: dict[str, Any] | None = None
    if include_list:
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
        "list_checked": include_list,
        "server_visible": (list_result or {}).get("status") == "ok" if include_list else registry_result.get("ok") is True,
        "listed_tool_count": len((list_result or {}).get("tools", [])) if include_list else None,
        "knowledge_registry_ok": registry_result.get("ok") is True,
        "chart_ok": chart_result.get("ok") is True,
        "memory_show_ok": memory_show.get("ok") is True,
        "run_id": run_id,
        "artifact_path": (chart_result.get("memory_ref") or {}).get("artifact_path"),
        "ok": (
            (registry_result.get("ok") is True)
            and chart_result.get("ok") is True
            and memory_show.get("ok") is True
            and ((list_result or {}).get("status") == "ok" if include_list else True)
        ),
    }
    report.update(_smoke_summary(report, workspace_root=workspace_root, config_path=config_path))
    _write_json_file(output_path, report)
    return report


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
    report = manager.doctor()
    report.update(_doctor_summary(report))
    _print_json(report)


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
        _write_json_file(write, payload)
    _print_json(payload)


@client_app.command("openclaw-setup")
def client_openclaw_setup(
    workspace: Path = typer.Option(
        Path.home() / ".openclaw" / "workspace",
        help="OpenClaw workspace root. The command creates config/ under it when missing.",
    ),
    skill_root: Path = typer.Option(
        _package_root(),
        help="Path to the horosa-skill package directory, or the repo root that contains it.",
    ),
    server_name: str = typer.Option("horosa", help="Server name key written into the mcporter config."),
    isolate_home: Path | None = typer.Option(
        None,
        help="Optional isolated HOME. Defaults to <workspace>/.horosa-home for a self-contained setup.",
    ),
    config: Path | None = typer.Option(
        None,
        help="Optional mcporter config path. Defaults to <workspace>/config/mcporter.json.",
    ),
    skip_smoke: bool = typer.Option(
        False,
        help="Skip the final smoke check if you only want install + config generation.",
    ),
) -> None:
    resolved_skill_root = _resolve_skill_root(skill_root)
    workspace_root = workspace.expanduser().resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    config_path = (config.expanduser().resolve() if config is not None else workspace_root / "config" / "mcporter.json")
    home_dir = (isolate_home.expanduser().resolve() if isolate_home is not None else workspace_root / ".horosa-home")
    env_overrides = _isolated_env_vars(home_dir)

    payload = _build_openclaw_config(
        skill_root=resolved_skill_root,
        server_name=server_name,
        format_name="mcporter",
        isolate_home=home_dir,
    )
    _write_json_file(config_path, payload)

    with _temporary_env(env_overrides):
        settings = Settings.from_env()
        manager = _runtime_manager(settings)
        try:
            install_result, install_seconds = _timed_call(lambda: manager.install())
            start_result, start_seconds = _timed_call(lambda: manager.start_local_services())
            doctor_result, doctor_seconds = _timed_call(manager.doctor)
            smoke_report: dict[str, Any] | None = None
            smoke_seconds: float | None = None
            if not skip_smoke:
                smoke_output = settings.data_dir / "openclaw_setup_smoke_check.json"
                smoke_report, smoke_seconds = _timed_call(
                    lambda: _run_openclaw_smoke_check(
                        workspace_root=workspace_root,
                        config_path=config_path,
                        output_path=smoke_output,
                        include_list=False,
                    )
                )
        except RuntimeError as exc:
            typer.echo(
                json.dumps(
                    _friendly_runtime_error_payload(
                        exc,
                        action_label="OpenClaw setup",
                        workspace_root=workspace_root,
                        config_path=config_path,
                    ),
                    ensure_ascii=False,
                    indent=2,
                ),
                err=True,
            )
            raise typer.Exit(code=2)

    doctor_issues = doctor_result.get("issues", [])
    install_summary = {
        "ok": install_result.get("ok"),
        "changed": install_result.get("changed"),
        "platform": install_result.get("platform"),
        "runtime_root": install_result.get("runtime_root"),
        "version": ((install_result.get("manifest") or {}).get("version")),
    }
    runtime_summary = {
        "ok": start_result.get("ok"),
        "already_running": start_result.get("already_running"),
        "reachable_endpoints": [
            endpoint.get("label")
            for endpoint in start_result.get("endpoints", [])
            if endpoint.get("reachable") is True
        ],
    }
    doctor_summary = {
        "issues": doctor_issues,
        "reachable_endpoints": [
            endpoint.get("label")
            for endpoint in doctor_result.get("endpoints", [])
            if endpoint.get("reachable") is True
        ],
    }
    report = {
        "ok": (not doctor_issues) and (skip_smoke or (smoke_report or {}).get("ok") is True),
        "workspace": str(workspace_root),
        "config": str(config_path),
        "config_written_to": str(config_path),
        "isolate_home": str(home_dir),
        "local_home": str(home_dir),
        "runtime_root": env_overrides["HOROSA_RUNTIME_ROOT"],
        "data_dir": env_overrides["HOROSA_SKILL_DATA_DIR"],
        "timings": {
            "install_seconds": install_seconds,
            "runtime_start_seconds": start_seconds,
            "doctor_seconds": doctor_seconds,
            "smoke_seconds": smoke_seconds,
        },
        "install": install_summary,
        "runtime_start": runtime_summary,
        "doctor": doctor_summary,
        "smoke": smoke_report,
        "next_steps": (
            [
                f"Open OpenClaw and use the generated mcporter config at {config_path}.",
                f"Re-run `uv run horosa-skill client openclaw-check --workspace {workspace_root} --config {config_path}` whenever you want a fresh smoke report.",
            ]
            if not skip_smoke
            else [
                f"Open OpenClaw and use the generated mcporter config at {config_path}.",
                f"Run `uv run horosa-skill client openclaw-check --workspace {workspace_root} --config {config_path}` to verify the setup when convenient.",
            ]
        ),
    }
    report.update(
        _setup_summary(
            workspace_root=workspace_root,
            config_path=config_path,
            home_dir=home_dir,
            doctor_issues=doctor_issues,
            smoke_report=smoke_report,
            skip_smoke=skip_smoke,
        )
    )
    _print_json(report)
    if not report["ok"]:
        raise typer.Exit(code=2)


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
        typer.echo(
            json.dumps(
                {
                    "ok": False,
                    "status": "needs_attention",
                    "ready_for_openclaw": False,
                    "user_summary": "OpenClaw config not found yet.",
                    "next_action": f"Run `{_openclaw_setup_command(workspace_root)}` to create a ready-to-use config and smoke test it.",
                    "code": "client.config_missing",
                    "message": f"mcporter config not found: {config_path}",
                    "details": {"config": str(config_path), "workspace": str(workspace_root)},
                },
                ensure_ascii=False,
                indent=2,
            ),
            err=True,
        )
        raise typer.Exit(code=2)

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

    try:
        report = _run_openclaw_smoke_check(
            workspace_root=workspace_root,
            config_path=config_path,
            output_path=output_path,
        )
    except RuntimeError as exc:
        typer.echo(
            json.dumps(
                _friendly_runtime_error_payload(
                    exc,
                    action_label="OpenClaw smoke check",
                    workspace_root=workspace_root,
                    config_path=config_path,
                ),
                ensure_ascii=False,
                indent=2,
            ),
            err=True,
        )
        raise typer.Exit(code=2)
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
