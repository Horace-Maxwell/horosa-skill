from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from horosa_skill.config import Settings
from horosa_skill.errors import RuntimeError, ToolValidationError
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import run_mcp_server

app = typer.Typer(help="Horosa Skill CLI")
tool_app = typer.Typer(help="Atomic tool commands")
memory_app = typer.Typer(help="Local memory commands")
export_app = typer.Typer(help="AI export registry and parsing commands")
app.add_typer(tool_app, name="tool")
app.add_typer(memory_app, name="memory")
app.add_typer(export_app, name="export")


def _service() -> HorosaSkillService:
    return HorosaSkillService(Settings.from_env())


def _runtime_manager(settings: Settings | None = None) -> HorosaRuntimeManager:
    return HorosaRuntimeManager(settings or Settings.from_env())


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
    started_now = False
    if not skip_runtime_start:
        try:
            start_result = manager.start_local_services()
            started_now = not start_result.get("already_running", False)
        except RuntimeError as exc:
            typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
            raise typer.Exit(code=2)
    try:
        run_mcp_server(settings, transport=transport)
    finally:
        if started_now:
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
) -> None:
    payload = _load_payload(stdin=stdin, input_file=input_file)
    service = _service()
    try:
        result = service.run_tool(tool_name, payload, save_result=save_result)
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


@memory_app.command("query")
def memory_query(
    tool: str | None = typer.Option(None, help="Filter by tool name."),
    entity: str | None = typer.Option(None, help="Filter by entity name."),
    after: str | None = typer.Option(None, help="Only return runs created after this ISO timestamp."),
    before: str | None = typer.Option(None, help="Only return runs created before this ISO timestamp."),
    limit: int = typer.Option(20, help="Maximum runs to return."),
    include_payload: bool = typer.Option(True, "--include-payload/--no-include-payload", help="Embed saved JSON payloads in the query output."),
) -> None:
    service = _service()
    data = service.store.query_runs(
        tool=tool,
        entity=entity,
        after=after,
        before=before,
        limit=limit,
        include_payload=include_payload,
    )
    _print_json(data)


if __name__ == "__main__":
    app()
