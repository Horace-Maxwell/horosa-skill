from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from importlib.metadata import PackageNotFoundError, version as package_version
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

import typer

from horosa_skill.agent_guidance import build_agent_guidance, validate_agent_preflight
from horosa_skill.config import Settings
from horosa_skill.benchmark import run_benchmark
from horosa_skill.client_tools import (
    extract_json_value,
    isolated_data_dir,
    isolated_runtime_ports,
    isolated_runtime_root,
    resolve_mcporter_command,
    resolve_uv_command,
)
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import RuntimeError, ToolValidationError
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import run_mcp_server
from horosa_skill.tracing import TraceRecorder

app = typer.Typer(
    help=(
        "Horosa Skill CLI — 本地术数/占星技法工具箱。\n"
        "上手三步：`install`（装离线 runtime）→ `selfcheck`（活体验证）→ `serve`（起 MCP 接 AI 客户端）。\n"
        "客户端注册：`client config --format claude-code|claude-desktop|codex`。\n"
        "Use `ask` / `dispatch` for natural-language orchestration, `tool run` for direct method calls, "
        "and `memory show/query/answer` for local record management. "
        "OpenClaw path: `client openclaw-setup`."
    )
)
tool_app = typer.Typer(help="Direct atomic method calls such as chart, qimen, liureng, and bazi.")
memory_app = typer.Typer(help="Inspect local records, show a single run, or attach the AI's final answer.")
export_app = typer.Typer(help="Inspect the Xingque AI export registry and parse exported text into structured JSON.")
knowledge_app = typer.Typer(help="Read bundled Xingque hover knowledge such as 星盘释义、大六壬地支提示、奇门象意。")
benchmark_app = typer.Typer(help="Run HorosaBench benchmark cases for routing, export parity, and knowledge quality.")
trace_app = typer.Typer(help="Inspect recent local trace records for tool runs, dispatches, and runtime operations.")
client_app = typer.Typer(help="Default OpenClaw entry: `openclaw-setup`. Also generate configs and run smoke checks for OpenClaw / mcporter.")
report_app = typer.Typer(help="Generate structured Horosa reports as JSON, DOCX, or PDF artifacts.")
agent_app = typer.Typer(help="Show agent-safe tool routing and clarification guidance before calculation.")
app.add_typer(tool_app, name="tool")
app.add_typer(memory_app, name="memory")
app.add_typer(export_app, name="export")
app.add_typer(knowledge_app, name="knowledge")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(trace_app, name="trace")
app.add_typer(client_app, name="client")
app.add_typer(report_app, name="report")
app.add_typer(agent_app, name="agent")


def _version_callback(value: bool) -> None:
    if not value:
        return
    try:
        resolved = package_version("horosa-skill")
    except PackageNotFoundError:
        resolved = "unknown"
    typer.echo(f"horosa-skill {resolved}")
    raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the installed Horosa Skill package version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Horosa Skill command line entrypoint."""


def _service() -> HorosaSkillService:
    return HorosaSkillService(Settings.from_env())


def _runtime_manager(settings: Settings | None = None) -> HorosaRuntimeManager:
    return HorosaRuntimeManager(settings or Settings.from_env())


def _start_stdio_runtime_warmup(manager: HorosaRuntimeManager) -> None:
    def _warmup() -> None:
        try:
            manager.start_local_services()
        except RuntimeError as exc:
            # 预热失败推迟不了问题只会掩盖它：stderr 一行警告（stdio 协议流在 stdout，不受影响）。
            sys.stderr.write(f"[horosa] runtime 预热失败（首次调用时会重试）：{exc.code} {exc}\n")
            sys.stderr.flush()

    threading.Thread(target=_warmup, name="horosa-stdio-runtime-warmup", daemon=True).start()


def _tracer(settings: Settings | None = None) -> TraceRecorder:
    return TraceRecorder(settings or Settings.from_env())


def _load_payload(*, stdin: bool, input_file: Optional[Path]) -> dict:
    if stdin:
        stream = getattr(sys.stdin, "buffer", None)
        if stream is not None:
            raw = stream.read().decode("utf-8-sig")
        else:
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


def _load_optional_payload(*, stdin: bool, input_file: Optional[Path]) -> dict:
    if not stdin and input_file is None:
        return {}
    return _load_payload(stdin=stdin, input_file=input_file)


def _print_json(data: object) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(text.encode("utf-8"))
        stream.write(b"\n")
        stream.flush()
        return
    typer.echo(text)


def _enforce_agent_preflight(tool_name: str, payload: dict[str, Any]) -> None:
    preflight = validate_agent_preflight(tool_name, payload)
    if preflight.get("ok"):
        return
    raise ToolValidationError(preflight["message"], code=preflight["code"], details=preflight)


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
    backend_port, chart_port = isolated_runtime_ports(resolved_home)
    env = {
        "HOME": str(resolved_home),
        "HOROSA_RUNTIME_ROOT": str(isolated_runtime_root(resolved_home)),
        "HOROSA_SKILL_DATA_DIR": str(isolated_data_dir(resolved_home)),
        "HOROSA_LOCAL_BACKEND_PORT": str(backend_port),
        "HOROSA_LOCAL_CHART_PORT": str(chart_port),
        "HOROSA_SERVER_ROOT": f"http://127.0.0.1:{backend_port}",
        "HOROSA_CHART_SERVER_ROOT": f"http://127.0.0.1:{chart_port}",
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


def _client_config_write(path: Path, payload: object) -> Path:
    """`client config --write` 落盘：目标文件已是 JSON 对象且本次产物含 `mcpServers` 时，
    按 server 键合并（保留用户已有的其他 MCP server），其余情况整文件写入。
    防止把用户真实的 claude_desktop_config.json / mcp.json 清空成只剩 horosa。"""
    target = path.expanduser().resolve()
    if isinstance(payload, dict) and isinstance(payload.get("mcpServers"), dict) and target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if isinstance(existing, dict):
            merged = dict(existing)
            servers = dict(merged.get("mcpServers") or {})
            servers.update(payload["mcpServers"])
            merged["mcpServers"] = servers
            return _write_json_file(target, merged)
    return _write_json_file(target, payload)


def _default_openclaw_native_config_path() -> Path:
    return Path.home() / ".openclaw" / "openclaw.json"


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"OpenClaw native config is not valid JSON: {path}",
            code="openclaw.native_config.invalid_json",
            details={"path": str(path), "error": str(exc)},
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"OpenClaw native config must be a JSON object: {path}",
            code="openclaw.native_config.invalid_shape",
            details={"path": str(path), "actual_type": type(payload).__name__},
        )
    return payload


def _merge_openclaw_native_config(
    existing: dict[str, Any],
    *,
    server_name: str,
    server_block: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(existing)
    mcp_section = merged.get("mcp")
    if not isinstance(mcp_section, dict):
        mcp_section = {}
    else:
        mcp_section = dict(mcp_section)
    servers = mcp_section.get("servers")
    if not isinstance(servers, dict):
        servers = {}
    else:
        servers = dict(servers)
    servers[server_name] = server_block
    mcp_section["servers"] = servers
    merged["mcp"] = mcp_section
    return merged


def _write_openclaw_native_config(
    *,
    path: Path,
    server_name: str,
    server_block: dict[str, Any],
) -> Path:
    output_path = path.expanduser().resolve()
    existing = _read_json_object(output_path)
    payload = _merge_openclaw_native_config(
        existing,
        server_name=server_name,
        server_block=server_block,
    )
    return _write_json_file(output_path, payload)


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
    elif issues == ["services:java_backend_not_running"]:
        user_summary = (
            "Degraded (chart-only): the Python chart service is up, but the Java backend (:9999) is not. "
            "Chart-side techniques (三式 ken/神数/地占/塔罗/西占 chart 族) still work; Java-side ones "
            "(nongli/bazi/ziwei/liureng and 占时 casts) will error until it recovers."
        )
        next_action = (
            "See `java_diagnostics` below for the captured Java boot error. Known cause on Windows: "
            "proxy/VPN or security software (WFP filters) blocking JDK-17 AF_UNIX/TCP loopback — "
            "issue #14. Retry after disabling the interfering software and rebooting, or keep using "
            "chart-only techniques."
        )
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


def _probe_executable(path: Path, args: list[str]) -> dict[str, Any]:
    """实跑探针：不止「文件存在」，还验证真的能执行并回读版本串。"""
    if not path.is_file():
        return {"path": str(path), "exists": False, "runnable": False}
    try:
        completed = subprocess.run([str(path), *args], capture_output=True, text=True, timeout=15)
        output = (completed.stdout or completed.stderr or "").strip().splitlines()
        return {
            "path": str(path),
            "exists": True,
            "runnable": completed.returncode == 0,
            "version": output[0][:80] if output else "",
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"path": str(path), "exists": True, "runnable": False, "error": str(exc)[:200]}


def _probe_port(port: int) -> dict[str, Any]:
    """端口占用探测：区分空闲 / 被占（被占时是否是本产品由 doctor 的可达性检查判断）。"""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        occupied = sock.connect_ex(("127.0.0.1", port)) == 0
    return {"port": port, "occupied": occupied}


def _doctor_environment_context(settings: Settings) -> dict[str, Any]:
    explicit_runtime_root = "HOROSA_RUNTIME_ROOT" in os.environ
    explicit_data_dir = "HOROSA_SKILL_DATA_DIR" in os.environ
    explicit_home = "HOME" in os.environ or (os.name == "nt" and "USERPROFILE" in os.environ)
    workspace_hint = os.environ.get("OPENCLAW_WORKSPACE")
    default_openclaw_workspace = Path.home() / ".openclaw" / "workspace"
    # 磁盘体检：runtime 全量约 2GB，升级/重装峰值需要双份空间。
    import shutil as _shutil

    try:
        usage = _shutil.disk_usage(settings.runtime_root if settings.runtime_root.exists() else Path.home())
        disk = {
            "free_gb": round(usage.free / (1024**3), 1),
            "total_gb": round(usage.total / (1024**3), 1),
            "sufficient_for_install": usage.free > 5 * (1024**3),
        }
    except OSError:
        disk = {"free_gb": None, "total_gb": None, "sufficient_for_install": None}
    current = settings.runtime_root / "current"
    node_bin = current / "runtime" / ("win" if os.name == "nt" else "mac") / "node" / ("node.exe" if os.name == "nt" else "bin/node")
    probes = {
        "node": _probe_executable(node_bin, ["--version"]),
        "backend_port": _probe_port(settings.local_backend_port),
        "chart_port": _probe_port(settings.local_chart_port),
    }
    return {
        "runtime_root": str(settings.runtime_root),
        "data_dir": str(settings.data_dir),
        "home": str(Path.home()),
        "disk": disk,
        "probes": probes,
        "uses_explicit_runtime_root": explicit_runtime_root,
        "uses_explicit_data_dir": explicit_data_dir,
        "uses_explicit_home": explicit_home,
        "openclaw_workspace_hint": workspace_hint or str(default_openclaw_workspace),
        "note": (
            "`doctor` checks the current process environment. If OpenClaw was set up with "
            "an isolated HOME/env block, use `client openclaw-check --workspace <workspace>` "
            "or run doctor with the same HOROSA_RUNTIME_ROOT/HOROSA_SKILL_DATA_DIR values."
        ),
    }


def _failed_smoke_checks(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    compute_ok = report.get("compute_ok")
    for field in ("server_visible", "knowledge_registry_ok", "memory_show_ok"):
        if report.get(field) is not True:
            failures.append(field)
    if compute_ok is not None:
        if compute_ok is not True:
            failures.append("compute_ok")
    elif report.get("chart_ok") is not True:
        failures.append("chart_ok")
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
        compute_tool = report.get("compute_tool") or "a representative Horosa tool"
        if list_checked:
            user_summary = (
                f"Ready. OpenClaw can see Horosa, list {report.get('listed_tool_count', 0)} tools, "
                f"run {compute_tool}, save the result, and read it back."
            )
        else:
            user_summary = "Ready. Horosa passed the quick OpenClaw smoke check: call, compute, save, and readback all worked."
        next_action = f"Open OpenClaw and use the config at {config_path}."
    elif "server_visible" in failed_checks or "knowledge_registry_ok" in failed_checks:
        user_summary = "OpenClaw did not get a healthy response from the Horosa server."
        next_action = f"Run `{_openclaw_check_command(workspace_root, config_path)}` after you confirm the runtime is installed and mcporter is available."
    elif "compute_ok" in failed_checks or "chart_ok" in failed_checks:
        user_summary = "OpenClaw reached Horosa, but the representative tool call did not finish successfully."
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
            "compute_ok": report.get("compute_ok", report.get("chart_ok")) is True,
            "memory_show_ok": report.get("memory_show_ok") is True,
        },
    }


def _setup_summary(
    *,
    workspace_root: Path,
    config_path: Path,
    native_config_path: Path | None,
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
        "native_config_written_to": str(native_config_path) if native_config_path is not None else None,
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
    elif code == "client.command_timeout":
        user_summary = f"{action_label} started the OpenClaw client command, but the subprocess did not return in time."
        next_action = (
            "Stop any stuck `horosa-skill serve --transport stdio` / `mcporter` processes, "
            "rerun `uv run horosa-skill client openclaw-setup --workspace <workspace>`, "
            "then retry the smoke check."
        )

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


def _run_subprocess_json(command: list[str], *, cwd: Path, timeout_seconds: float = 180.0) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(str(exc), code="client.command_not_found", details={"command": command, "cwd": str(cwd)}) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Command timed out after {timeout_seconds} seconds: {' '.join(command)}",
            code="client.command_timeout",
            details={
                "command": command,
                "cwd": str(cwd),
                "timeout_seconds": timeout_seconds,
                "stdout": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
                "stderr": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            },
        ) from exc
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

    def call_tool(tool_name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        command = [
            *resolve_mcporter_command(),
            "call",
            f"horosa.{tool_name}",
        ]
        if payload is not None:
            command.extend(["--args", json.dumps(payload, ensure_ascii=False)])
        command.extend(
            [
                "--output",
                "json",
                "--config",
                str(config_path),
                "--root",
                str(workspace_root),
                "--timeout",
                str(call_timeout_ms),
            ]
        )
        return _run_subprocess_json(command, cwd=workspace_root, timeout_seconds=150)

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
            timeout_seconds=60,
        )
    registry_result = call_tool("horosa_knowledge_registry")
    confirmed_payload = {
        "agent_confirmed_settings": True,
        "clarification_notes": "OpenClaw smoke check fixture with explicit test settings.",
    }
    chart_payload = {
        **confirmed_payload,
        "date": "2026-04-04",
        "time": "15:58:35",
        "zone": "+08:00",
        "lat": "26n04",
        "lon": "119e19",
        "gpsLat": 26.066667,
        "gpsLon": 119.316667,
        "hsys": 1,
        "tradition": False,
        "predictive": True,
        "zodiacal": 0,
        "simpleAsp": False,
        "strongRecption": False,
        "virtualPointReceiveAsp": True,
        "southchart": False,
        "ad": 1,
    }
    chart_result = call_tool("horosa_astro_chart", chart_payload)
    if _is_mcporter_timeout_response(chart_result):
        chart_result = call_tool("horosa_astro_chart", chart_payload)

    chart_ok = chart_result.get("ok") is True
    fallback_tool = "horosa_cn_qimen"
    fallback_result: dict[str, Any] | None = None
    if not chart_ok:
        # Keep the heavyweight chart result as a diagnostic, but verify the
        # OpenClaw path with a stable headless local tool before failing setup.
        fallback_payload = {
            **confirmed_payload,
            "date": "2026-04-04",
            "time": "15:58:35",
            "zone": "+08:00",
            "lat": "26n04",
            "lon": "119e19",
        }
        fallback_result = call_tool(fallback_tool, fallback_payload)
        if _is_mcporter_timeout_response(fallback_result):
            fallback_result = call_tool(fallback_tool, fallback_payload)

    fallback_ok = (fallback_result or {}).get("ok") is True
    compute_result = chart_result if chart_ok else (fallback_result or chart_result)
    compute_ok = chart_ok or fallback_ok
    compute_tool = "horosa_astro_chart" if chart_ok else (fallback_tool if fallback_ok else None)
    memory_ref = compute_result.get("memory_ref") or {}
    run_id = memory_ref.get("run_id")
    artifact_path = memory_ref.get("artifact_path")
    memory_show = call_tool("horosa_memory_show", {"run_id": run_id, "include_payload": False}) if run_id else {}
    report = {
        "workspace": str(workspace_root),
        "config": str(config_path),
        "list_checked": include_list,
        "server_visible": (list_result or {}).get("status") == "ok" if include_list else registry_result.get("ok") is True,
        "listed_tool_count": len((list_result or {}).get("tools", [])) if include_list else None,
        "knowledge_registry_ok": registry_result.get("ok") is True,
        "chart_ok": chart_ok,
        "chart_error": chart_result.get("error") if not chart_ok else None,
        "fallback_tool": fallback_tool if not chart_ok else None,
        "fallback_tool_ok": fallback_ok if fallback_result is not None else None,
        "fallback_error": (fallback_result or {}).get("error") if fallback_result and not fallback_ok else None,
        "compute_ok": compute_ok,
        "compute_tool": compute_tool,
        "memory_show_ok": memory_show.get("ok") is True,
        "run_id": run_id,
        "artifact_path": artifact_path,
        "ok": (
            (registry_result.get("ok") is True)
            and compute_ok
            and memory_show.get("ok") is True
            and ((list_result or {}).get("status") == "ok" if include_list else True)
        ),
    }
    report.update(_smoke_summary(report, workspace_root=workspace_root, config_path=config_path))
    _write_json_file(output_path, report)
    return report


def _install_progress_printer():
    """stderr 下载进度（stdout 保持纯 JSON 契约）：TTY 用行内百分比，非 TTY 每 ~50MB 一行。"""
    state = {"last": 0}
    is_tty = sys.stderr.isatty()

    def _progress(done: int, total: int | None) -> None:
        if is_tty:
            if total:
                pct = done * 100 // total
                sys.stderr.write(f"\r下载 runtime：{done // (1024*1024)}MB / {total // (1024*1024)}MB（{pct}%）")
            else:
                sys.stderr.write(f"\r下载 runtime：{done // (1024*1024)}MB")
            sys.stderr.flush()
            if total and done >= total:
                sys.stderr.write("\n")
        else:
            if done - state["last"] >= 50 * 1024 * 1024:
                state["last"] = done
                suffix = f" / {total // (1024*1024)}MB" if total else ""
                sys.stderr.write(f"下载 runtime：{done // (1024*1024)}MB{suffix}\n")
                sys.stderr.flush()

    return _progress


def _run_install(archive: str | None, manifest_url: str | None, force: bool, *, mode: str) -> None:
    settings = Settings.from_env()
    manager = _runtime_manager(settings)
    typer.echo("正在解析 runtime 版本与资产…（约 730MB 下载、解压后约 2GB，请留足磁盘）", err=True)
    try:
        result = manager.install(archive=archive, manifest_url=manifest_url, force=force, progress=_install_progress_printer())
    except RuntimeError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    except OSError as exc:
        # 磁盘满 / 权限不足 / 跨卷等 IO 失败：结构化输出而非裸 traceback。
        typer.echo(json.dumps({"ok": False, "code": "runtime.install_io_error", "message": str(exc), "details": {}}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    if mode == "upgrade":
        result["mode"] = "upgrade"
    _print_json(result)


@app.command(help="Install the offline runtime (~730MB download; resumable, mirror-aware). 安装离线 runtime（断点续传/多镜像）。")
def install(
    archive: str | None = typer.Option(None, help="Local archive path or URL to a runtime asset."),
    manifest_url: str | None = typer.Option(None, help="Release manifest URL that maps platforms to runtime archives."),
    force: bool = typer.Option(False, help="Reinstall even if the same runtime version is already present."),
) -> None:
    _run_install(archive, manifest_url, force, mode="install")


@app.command(help="Version-aware install alias: skips the 730MB download when already up to date. 升级（已最新则秒退）。")
def upgrade(
    manifest_url: str | None = typer.Option(None, help="Release manifest URL that maps platforms to runtime archives."),
    force: bool = typer.Option(False, help="Reinstall even if the same runtime version is already present."),
) -> None:
    _run_install(None, manifest_url, force, mode="upgrade")


@app.command(help="Uninstall the offline runtime (dry-run by default; --yes to execute). 卸载 runtime（默认只打印将删清单）。")
def uninstall(
    purge_data: bool = typer.Option(False, "--purge-data", help="Also delete user data (memory.db / runs / traces). 同时删除用户数据（不可恢复）。"),
    yes: bool = typer.Option(False, "--yes", help="Actually delete. Without this flag only the removal plan is printed."),
) -> None:
    settings = Settings.from_env()
    manager = _runtime_manager(settings)
    try:
        result = manager.uninstall(purge_data=purge_data, yes=yes)
    except RuntimeError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result)


@app.command()
def doctor() -> None:
    settings = Settings.from_env()
    manager = _runtime_manager(settings)
    report = manager.doctor()
    report["environment"] = _doctor_environment_context(settings)
    # 记忆库完整性探针（v0.33.0 批 II-1）：PRAGMA quick_check + 损坏自愈痕迹；坏库在 MemoryStore
    # 构造时已分类恢复（隔离 .corrupt-<ts>.bak 并重建），这里如实呈现。
    try:
        from horosa_skill.memory.store import MemoryStore as _MemoryStore

        report["memory_db"] = {"path": str(settings.db_path), **_MemoryStore(settings).integrity_check()}
    except Exception as exc:  # noqa: BLE001 - 体检项自身失败也要如实入报告
        report["memory_db"] = {"path": str(settings.db_path), "ok": False, "detail": [f"{exc}"]}
    # env 旗标审计（批 II-1）：未知 HOROSA_* 的 warn-and-ignore 结果入报告。
    from horosa_skill.config import audit_env_flags as _audit_env_flags

    try:
        report["env_flags"] = {"ok": True, "warnings": _audit_env_flags(force=True)}
    except ValueError as exc:
        report["env_flags"] = {"ok": False, "warnings": [str(exc)]}
    report.update(_doctor_summary(report))
    _print_json(report)


@app.command(help="Client-agnostic live check: cast one chart, store it, read it back. 活体体检（起一张盘→存→读回）。")
def selfcheck() -> None:
    settings = Settings.from_env()
    manager = _runtime_manager(settings)
    report: dict[str, Any] = {"ok": False, "steps": {}}
    try:
        doctor_report = manager.doctor()
        report["steps"]["doctor"] = {"ok": not doctor_report.get("issues"), "issues": doctor_report.get("issues", [])}
        service = HorosaSkillService(settings, runtime_manager=manager)
        result = service.run_tool(
            "nongli_time",
            {
                "date": "2028-04-06",
                "time": "09:33:00",
                "zone": "+08:00",
                "lon": "121e28",
                "lat": "31n13",
                "agent_confirmed_settings": True,
            },
            query_text="selfcheck 活体体检",
        )
        report["steps"]["compute"] = {"ok": result.ok, "tool": "nongli_time", "error": result.error.model_dump(mode="json") if result.error else None}
        probe_result = result
        if not result.ok:
            # Issue #14: nongli_time 走 Java 后端(:9999)；Java 被环境杀死（如 WFP 拦 JDK-17 loopback）时
            # 不能让整个 selfcheck 挂死 —— 改用 chart 侧 kentang 的 wangji 证明 chart 半边活着（降级可用）。
            fallback = service.run_tool(
                "wangji",
                {
                    "date": "1998-02-20",
                    "time": "20:48:00",
                    "after23NewDay": 1,
                    "agent_confirmed_settings": True,
                    "clarification_notes": "selfcheck degraded chart-only probe",
                },
                query_text="selfcheck 降级 chart-only 活体体检",
            )
            report["steps"]["compute_chart_only_fallback"] = {
                "ok": fallback.ok,
                "tool": "wangji",
                "error": fallback.error.model_dump(mode="json") if fallback.error else None,
            }
            if fallback.ok:
                report["degraded"] = "chart_only"
                probe_result = fallback
        run_id = probe_result.memory_ref.run_id if probe_result.memory_ref else None
        shown = service.show_memory({"run_id": run_id}) if run_id else {"ok": False}
        report["steps"]["memory_roundtrip"] = {"ok": bool(shown.get("ok")), "run_id": run_id}
        report["ok"] = bool(probe_result.ok and shown.get("ok"))
        if report.get("degraded") == "chart_only":
            report["next_action"] = (
                "降级可用（chart-only）：Java 后端(:9999)未就绪，nongli/bazi/ziwei/liureng 与占时起课暂不可用；"
                "chart 侧技法（三式 ken/神数/地占/塔罗/西占 chart 族）可正常 `serve` 使用。"
                "跑 `uv run horosa-skill doctor` 看 java_diagnostics 里捕获的 Java 启动错误；"
                "Windows 已知诱因 = 代理/VPN/安全软件的 WFP 过滤拦截 JDK-17 loopback（issue #14）。"
            )
        else:
            report["next_action"] = (
                "全部通过：可以 `serve` 并接入 AI 客户端。" if report["ok"]
                else "有步骤失败：按 steps 中的 error/issues 排查，或运行 `uv run horosa-skill doctor` 看完整体检。"
            )
    except RuntimeError as exc:
        report["steps"]["error"] = {"code": exc.code, "message": str(exc), "details": exc.details}
        report["next_action"] = "运行 `uv run horosa-skill install` 安装离线 runtime 后重试。" if exc.code == "runtime.not_installed" else "运行 `uv run horosa-skill doctor` 定位。"
    _print_json(report)
    if not report["ok"]:
        raise typer.Exit(code=1)


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
    # 启动横幅（stderr）：监听地址 + 客户端注册一行指引；stdio 模式不打印（协议流走 stdout/stdin）。
    if transport != "stdio":
        typer.echo(
            f"Horosa Skill MCP 正在 http://{host}:{port}/mcp 监听（streamable-http，{len(TOOL_DEFINITIONS)} 个技法工具）。\n"
            f"接入 Claude Code：claude mcp add horosa --transport http http://{host}:{port}/mcp\n"
            f"其他客户端配置见 examples/clients/ 或 README「接入 AI 客户端」。",
            err=True,
        )
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
        _enforce_agent_preflight(tool_name, payload)
        result = service.run_tool(tool_name, payload, save_result=save_result, query_text=query_text)
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result.model_dump(mode="json"))


@agent_app.command("guidance")
def agent_guidance(
    tool_name: str | None = typer.Option(None, "--tool", help="Tool name or MCP tool name, such as liureng_gods or horosa_cn_liureng_gods."),
    intent: str | None = typer.Option(None, "--intent", help="Optional user intent text to echo back in the guidance payload."),
    include_all: bool = typer.Option(False, "--all", help="Return guidance for every registered calculation/export tool."),
) -> None:
    """Return machine-readable guidance that tells agents what to ask before tool calls."""

    _print_json(build_agent_guidance(tool_name=tool_name, intent=intent, include_all=include_all))


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


@knowledge_app.command("search")
def knowledge_search(
    query: str = typer.Argument(..., help="Full-text query across all 24 knowledge domains."),
    domain: Optional[str] = typer.Option(None, help="Optional domain filter (e.g. bazi, ziwei, qimen)."),
    limit: int = typer.Option(8, help="Max matches to return (1-20)."),
    save_result: bool = typer.Option(False, help="Persist the result in local memory."),
) -> None:
    """Search bundled knowledge (hover + technique manuals); every match carries a citation."""
    payload: dict[str, Any] = {"query": query, "limit": limit}
    if domain:
        payload["domain"] = domain
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
        _enforce_agent_preflight("dispatch", payload)
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


@app.command(help="合参：一问多技法交叉印证，产出合参模板（分歧必须披露）。Cross-technique synthesis template.")
def hecan(
    query: str = typer.Option(..., "--query", help="用户的问题（路由据此选盘，除非显式 --tool）。"),
    tool: list[str] = typer.Option([], "--tool", help="显式指定技法（可重复），缺省由路由选。"),
    max_tools: int = typer.Option(5, "--max-tools", help="最多同时起几个技法。"),
    stdin: bool = typer.Option(False, "--stdin", help="Read birth/subject JSON from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read birth/subject JSON from a file."),
) -> None:
    payload = _load_optional_payload(stdin=stdin, input_file=input_file)
    payload.update({"query": query, "max_tools": max_tools})
    if tool:
        payload["tools"] = list(tool)
    service = _service()
    try:
        result = service.hecan(payload)
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result)


@benchmark_app.command("faithfulness", help="盘面事实忠实性校验：AI 答案 vs 已存 run 的机读真值（supported/invented/contradicted）。Verify an AI answer against a stored run's computed chart facts.")
def benchmark_faithfulness(
    run_id: str = typer.Option(..., "--run-id", help="Stored run whose computed facts are the ground truth."),
    answer_file: Optional[Path] = typer.Option(None, "--answer-file", help="Read the AI answer text from a file."),
    answer_text: Optional[str] = typer.Option(None, "--answer-text", help="Short inline AI answer text."),
    tool: str | None = typer.Option(None, "--tool", help="Optional tool name for multi-tool runs."),
) -> None:
    from horosa_skill.benchmark.faithfulness import extract_facts, verify_answer

    if not answer_file and not answer_text:
        typer.echo(json.dumps({"ok": False, "message": "需要 --answer-file 或 --answer-text"}, ensure_ascii=False), err=True)
        raise typer.Exit(code=2)
    if answer_file:
        try:
            answer = answer_file.expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            raise typer.BadParameter(f"无法读取 --answer-file：{exc}") from exc
    else:
        answer = answer_text or ""
    service = _service()
    try:
        run, artifact = service._load_report_source(run_id, tool)  # noqa: SLF001 - 同包 CLI 面复用装载器
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc)}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    facts = extract_facts(artifact.get("payload") or {})
    report = verify_answer(answer, facts)
    report["run_id"] = run_id
    report["tool"] = artifact.get("tool_name")
    _print_json(report)
    if not report["ok"]:
        raise typer.Exit(code=1)


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


@client_app.command("config")
def client_config(
    format_name: str = typer.Option(
        "claude-code",
        "--format",
        help="Target client: claude-code / claude-desktop / cursor / vscode / codex / mcporter / openclaw.",
    ),
    skill_root: Path = typer.Option(
        _package_root(),
        help="Path to the horosa-skill package directory, or the repo root that contains it.",
    ),
    server_name: str = typer.Option("horosa", help="Server name key written into the MCP config."),
    write: Path | None = typer.Option(None, help="Optional output file path (also printed to stdout)."),
) -> None:
    """按客户端生成即用 MCP 配置（自动注入真实绝对路径，无手填占位符）。"""
    resolved_skill_root = _resolve_skill_root(skill_root)
    uv_command = resolve_uv_command()
    stdio_command = [
        *uv_command,
        "run",
        "--directory",
        str(resolved_skill_root),
        "horosa-skill",
        "serve",
        "--transport",
        "stdio",
    ]
    key = format_name.strip().lower()
    if key in {"mcporter", "openclaw"}:
        payload: dict[str, Any] = _build_openclaw_config(
            skill_root=resolved_skill_root,
            server_name=server_name,
            format_name=key,
            isolate_home=None,
        )
    elif key == "claude-code":
        payload = {
            "note": "运行下面这一条命令即可把 Horosa 注册进 Claude Code（stdio 直连，无需常驻 serve）。",
            "command": "claude mcp add " + server_name + " -- " + " ".join(stdio_command),
            "alternative_http": {
                "note": "或先 `uv run horosa-skill serve` 再注册 HTTP 端点：",
                "command": f"claude mcp add {server_name} --transport http http://127.0.0.1:8765/mcp",
            },
        }
    elif key == "claude-desktop":
        payload = {
            "note": "合并进 Claude Desktop 的 claude_desktop_config.json（mcpServers 键下）。",
            "mcpServers": {
                server_name: {
                    "command": stdio_command[0],
                    "args": stdio_command[1:],
                }
            },
        }
    elif key == "codex":
        payload = {
            "note": "追加到 Codex 的 config.toml；HTTP 变体需先 `uv run horosa-skill serve`。",
            "toml_stdio": (
                f"[mcp_servers.{server_name}]\n"
                f"command = \"{stdio_command[0]}\"\n"
                f"args = {json.dumps(stdio_command[1:])}\n"
            ),
            "toml_http": f"[mcp_servers.{server_name}]\nurl = \"http://127.0.0.1:8765/mcp\"\n",
        }
    elif key == "cursor":
        # Cursor 官方 install deep link：config = base64({"command","args"})，点击即装。
        import base64

        cursor_config = json.dumps({"command": stdio_command[0], "args": stdio_command[1:]}, ensure_ascii=False)
        encoded = base64.b64encode(cursor_config.encode("utf-8")).decode("ascii")
        payload = {
            "note": "点击 deep_link 一键安装进 Cursor；或把 mcpServers 合并进 ~/.cursor/mcp.json。",
            "deep_link": f"cursor://anysphere.cursor-deeplink/mcp/install?name={server_name}&config={encoded}",
            "mcpServers": {server_name: {"command": stdio_command[0], "args": stdio_command[1:]}},
        }
    elif key == "vscode":
        # VS Code 官方安装链接（vscode:mcp/install?<url-encoded JSON>）+ CLI 等价命令。
        from urllib.parse import quote

        vscode_config = json.dumps(
            {"name": server_name, "command": stdio_command[0], "args": stdio_command[1:]}, ensure_ascii=False
        )
        payload = {
            "note": "点击 install_link 一键安装进 VS Code；或运行 cli_command。",
            "install_link": f"vscode:mcp/install?{quote(vscode_config, safe='')}",
            "cli_command": f"code --add-mcp '{vscode_config}'",
        }
    else:
        raise typer.BadParameter(
            "format must be one of: claude-code / claude-desktop / cursor / vscode / codex / mcporter / openclaw"
        )
    if write is not None:
        _client_config_write(write, payload)
    _print_json(payload)


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
    native_config: Path | None = typer.Option(
        None,
        "--native-config",
        help="Optional OpenClaw native config path. Defaults to ~/.openclaw/openclaw.json.",
    ),
    write_native_config: bool = typer.Option(
        True,
        "--write-native-config/--no-write-native-config",
        help="Also merge Horosa into OpenClaw's native mcp.servers config so agent sessions can see horosa_* tools.",
    ),
    skip_smoke: bool = typer.Option(
        False,
        help="Skip the final smoke check if you only want install + config generation.",
    ),
    manifest_url: str | None = typer.Option(
        None,
        "--manifest-url",
        help="Optional runtime manifest URL. Defaults to the public GitHub Release manifest for the installed package version.",
    ),
) -> None:
    resolved_skill_root = _resolve_skill_root(skill_root)
    workspace_root = workspace.expanduser().resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    config_path = (config.expanduser().resolve() if config is not None else workspace_root / "config" / "mcporter.json")
    native_config_path = (
        native_config.expanduser().resolve()
        if native_config is not None
        else _default_openclaw_native_config_path().expanduser().resolve()
    )
    home_dir = (isolate_home.expanduser().resolve() if isolate_home is not None else workspace_root / ".horosa-home")
    env_overrides = _isolated_env_vars(home_dir)

    payload = _build_openclaw_config(
        skill_root=resolved_skill_root,
        server_name=server_name,
        format_name="mcporter",
        isolate_home=home_dir,
    )
    _write_json_file(config_path, payload)
    native_config_written_to: Path | None = None
    if write_native_config:
        native_config_written_to = _write_openclaw_native_config(
            path=native_config_path,
            server_name=server_name,
            server_block=payload["mcpServers"][server_name],
        )

    with _temporary_env(env_overrides):
        settings = Settings.from_env()
        manager = _runtime_manager(settings)
        try:
            install_result, install_seconds = _timed_call(lambda: manager.install(manifest_url=manifest_url))
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
        "runtime_payload_version": ((install_result.get("manifest") or {}).get("runtime_payload_version")),
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
        "manifest_version": doctor_result.get("manifest_version"),
        "runtime_payload_version": doctor_result.get("runtime_payload_version"),
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
        "native_config": str(native_config_written_to) if native_config_written_to is not None else None,
        "native_config_written_to": str(native_config_written_to) if native_config_written_to is not None else None,
        "native_config_note": (
            "Horosa was merged into OpenClaw native mcp.servers. Restart OpenClaw or start a new agent session "
            "if an existing session still reports clientToolCount: 0."
            if native_config_written_to is not None
            else "Skipped native OpenClaw config write. mcporter checks may pass, but agent sessions may not see horosa_* tools until mcp.servers is configured."
        ),
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
                (
                    f"Restart OpenClaw or start a new agent session so it reloads native MCP config at {native_config_written_to}."
                    if native_config_written_to is not None
                    else f"Open OpenClaw and use the generated mcporter config at {config_path}."
                ),
                f"Re-run `uv run horosa-skill client openclaw-check --workspace {workspace_root} --config {config_path}` whenever you want a fresh smoke report.",
            ]
            if not skip_smoke
            else [
                (
                    f"Restart OpenClaw or start a new agent session so it reloads native MCP config at {native_config_written_to}."
                    if native_config_written_to is not None
                    else f"Open OpenClaw and use the generated mcporter config at {config_path}."
                ),
                f"Run `uv run horosa-skill client openclaw-check --workspace {workspace_root} --config {config_path}` to verify the setup when convenient.",
            ]
        ),
    }
    report.update(
        _setup_summary(
            workspace_root=workspace_root,
            config_path=config_path,
            native_config_path=native_config_written_to,
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
        help="Run the exhaustive all-tool OpenClaw self-check instead of a quick smoke check.",
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
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=900)
        except subprocess.TimeoutExpired:
            typer.echo(
                json.dumps(
                    {"ok": False, "code": "openclaw_check.timeout", "message": "openclaw-check --full exceeded 900s and was aborted (a child MCP/runtime process is likely wedged)."},
                    ensure_ascii=False,
                    indent=2,
                ),
                err=True,
            )
            raise typer.Exit(code=2)
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


@report_app.command("template")
def report_template(
    run_id: str = typer.Option(..., "--run-id", help="Run id to turn into an AI-fillable report template."),
    tool: str | None = typer.Option(None, "--tool", help="Optional tool name for dispatch or multi-tool runs."),
    language: str = typer.Option("zh-CN", "--language", help="Report language tag."),
) -> None:
    service = _service()
    try:
        result = service.report_template({"run_id": run_id, "tool_name": tool, "language": language})
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result)


@report_app.command("render")
def report_render(
    run_id: str = typer.Option(..., "--run-id", help="Run id to render."),
    format_name: str = typer.Option("pdf", "--format", help="Output format: json, docx, or pdf."),
    tool: str | None = typer.Option(None, "--tool", help="Optional tool name for dispatch or multi-tool runs."),
    output: Path | None = typer.Option(None, "--output", help="Optional output path. Defaults to the Horosa memory output directory."),
    title: str | None = typer.Option(None, "--title", help="Optional report title."),
    language: str = typer.Option("zh-CN", "--language", help="Report language tag."),
    include_raw_json: bool = typer.Option(False, "--include-raw-json/--no-include-raw-json", help="Embed the full source envelope in the report JSON."),
    stdin: bool = typer.Option(False, "--stdin", help="Read optional ai_report JSON from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read optional ai_report JSON from a file."),
) -> None:
    ai_payload = _load_optional_payload(stdin=stdin, input_file=input_file)
    ai_report = ai_payload.get("ai_report", ai_payload)
    service = _service()
    try:
        result = service.report_render(
            {
                "run_id": run_id,
                "tool_name": tool,
                "format": format_name,
                "language": language,
                "title": title,
                "ai_report": ai_report,
                "include_raw_json": include_raw_json,
                "output_path": str(output.expanduser()) if output else None,
            }
        )
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result)


@report_app.command("technique", help="技法依据报告：本次/本会话用了什么技法、什么口径、谁算的（确定性，无需 AI 正文）。Deterministic method/provenance report — no ai_report needed.")
def report_technique(
    run_id: str | None = typer.Option(None, "--run-id", help="Report on a single stored run."),
    group_id: str | None = typer.Option(None, "--group-id", help="Report on a whole session (all runs sharing this group id)."),
    format_name: str = typer.Option("markdown", "--format", help="Output format: markdown, json, docx, or pdf."),
    output: Path | None = typer.Option(None, "--output", help="Optional output path. Defaults to the Horosa memory output directory."),
    title: str | None = typer.Option(None, "--title", help="Optional report title."),
    include_sections: bool = typer.Option(True, "--include-sections/--no-include-sections", help="List each technique's produced section titles."),
) -> None:
    service = _service()
    try:
        result = service.technique_report(
            {
                "run_id": run_id,
                "group_id": group_id,
                "format": format_name,
                "title": title,
                "include_sections": include_sections,
                "output_path": str(output.expanduser()) if output else None,
            }
        )
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    # 报告正文已落盘；命令行只回摘要 + 一致性结论（把整篇 markdown 打进 stdout 会淹掉真正要看的告警）。
    _print_json({key: value for key, value in result.items() if key != "document"})


@report_app.command("from-tool")
def report_from_tool(
    tool: str = typer.Argument(..., help="Tool name such as chart, qimen, liureng_gods, or sixyao."),
    format_name: str = typer.Option("pdf", "--format", help="Output format: json, docx, or pdf."),
    output: Path | None = typer.Option(None, "--output", help="Optional output path. Defaults to the Horosa memory output directory."),
    question: str | None = typer.Option(None, "--question", help="Optional user question to store with this report run."),
    title: str | None = typer.Option(None, "--title", help="Optional report title."),
    language: str = typer.Option("zh-CN", "--language", help="Report language tag."),
    ai_answer_text: str | None = typer.Option(None, "--ai-answer-text", help="Free-form AI analysis text to render directly into the final report."),
    ai_answer_file: Optional[Path] = typer.Option(None, "--ai-answer-file", help="Read free-form AI analysis text from a UTF-8 file."),
    ai_report_file: Optional[Path] = typer.Option(None, "--ai-report-file", help="Read structured ai_report JSON from a UTF-8 file."),
    include_raw_json: bool = typer.Option(False, "--include-raw-json/--no-include-raw-json", help="Embed the full source envelope in the report JSON."),
    stdin: bool = typer.Option(False, "--stdin", help="Read the tool payload JSON from stdin."),
    input_file: Optional[Path] = typer.Option(None, "--input", help="Read the tool payload JSON from a file."),
) -> None:
    payload = _load_payload(stdin=stdin, input_file=input_file)
    ai_report: dict[str, Any] = {}
    if ai_report_file is not None:
        try:
            raw_ai_report = json.loads(ai_report_file.read_text(encoding="utf-8"))
        except OSError as exc:
            raise typer.BadParameter(f"--ai-report-file could not be read: {exc}")
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"--ai-report-file is not valid JSON: {exc}")
        if not isinstance(raw_ai_report, dict):
            raise typer.BadParameter("--ai-report-file must contain a JSON object.")
        ai_report = raw_ai_report.get("ai_report", raw_ai_report)
        if not isinstance(ai_report, dict):
            raise typer.BadParameter("--ai-report-file ai_report must be a JSON object.")
    final_ai_answer_text = ai_answer_text
    if ai_answer_file is not None:
        try:
            file_text = ai_answer_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise typer.BadParameter(f"--ai-answer-file could not be read: {exc}")
        final_ai_answer_text = f"{final_ai_answer_text}\n\n{file_text}".strip() if final_ai_answer_text else file_text
    service = _service()
    try:
        _enforce_agent_preflight(tool, payload)
        result = service.report_from_tool(
            {
                "tool_name": tool,
                "payload": payload,
                "format": format_name,
                "language": language,
                "title": title,
                "question": question,
                "ai_report": ai_report,
                "ai_answer_text": final_ai_answer_text,
                "include_raw_json": include_raw_json,
                "output_path": str(output.expanduser()) if output else None,
            }
        )
    except ToolValidationError as exc:
        typer.echo(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "details": exc.details}, ensure_ascii=False, indent=2), err=True)
        raise typer.Exit(code=2)
    _print_json(result)


@memory_app.command("query")
def memory_query(
    run_id: str | None = typer.Option(None, help="Filter by exact run id."),
    tool: str | None = typer.Option(None, help="Filter by tool name."),
    entity: str | None = typer.Option(None, help="Filter by entity name."),
    text: str | None = typer.Option(None, help="Search query text, user question, AI answer, subject, tool, artifact path, or artifact kind."),
    artifact_kind: str | None = typer.Option(None, help="Filter by artifact kind, for example report_json, report_docx, report_pdf, or tool_result."),
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
        text=text,
        artifact_kind=artifact_kind,
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
