"""OpenClaw 接入的冒烟检查：经 mcporter 真调一个技法并读回存档；npx mcporter 预热、子进程 JSON 调用与超时、结果摘要与友好错误。命令本身在 cli.py。"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path, PureWindowsPath
from typing import Any

from horosa_skill.client_config.merge import _write_json_file
from horosa_skill.client_config.payload import _format_cli_command
from horosa_skill.client_tools import extract_json_value, resolve_mcporter_command
from horosa_skill.errors import RuntimeError, bilingual


def _timed_call(callback):
    started_at = time.perf_counter()
    result = callback()
    return result, round(time.perf_counter() - started_at, 3)


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
    code = exc.code  # HorosaSkillError guarantees a code and a dict `details`
    details = exc.details
    command = [str(part) for part in details.get("command", [])]
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
    elif code == "runtime.platform_unsupported":
        user_summary = f"{action_label} found no offline runtime payload for this platform."
        next_action = str(details.get("next_action") or "Use gateway mode: point HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT at a supported machine.")
    elif code.startswith("runtime.install") or code == "runtime.not_installed":
        user_summary = f"{action_label} could not finish installing the offline runtime."
        next_action = "Check your network access to the Horosa runtime release and rerun the setup command."
    elif code.startswith("runtime.start"):
        user_summary = f"{action_label} installed the runtime, but the local Horosa services did not start cleanly."
        next_action = "Run `uv run horosa-skill doctor` for more details, then rerun the setup command."
    elif code in {"client.command_failed", "client.invalid_json"}:
        user_summary = f"{action_label} started the OpenClaw client command, but it did not return a clean JSON result."
        next_action = "Run `uv run horosa-skill doctor` and make sure mcporter can start Horosa, then retry the smoke check."
    elif code == "client.command_timeout" and details.get("phase") == "npx_install":
        user_summary = f"{action_label} could not fetch `mcporter` through npx in time (npx downloads it on first use)."
        next_action = (
            "Install it once with `npm i -g mcporter` (or set `HOROSA_MCPORTER_BIN`), "
            + (f"then rerun `{retry_command}`." if retry_command else "then rerun the command.")
        )
    elif code == "client.command_timeout" and details.get("output_complete"):
        user_summary = (
            f"{action_label}: the OpenClaw client command printed its complete result, but its process did not exit in time."
        )
        next_action = (
            "Something in the client's process tree (usually the stdio server it started) kept the pipes open. "
            "Rerun with `MCPORTER_DEBUG_HANG=1` to list what mcporter was waiting on, stop leftover "
            "`horosa-skill serve --transport stdio` / `mcporter` processes, then retry the smoke check."
        )
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


def _timeout_output_text(value: object) -> str:
    """`TimeoutExpired.stdout/stderr` is bytes on POSIX even with text=True (str on Windows) — keep both."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value if isinstance(value, str) else ""


def _has_json_object(text: str) -> bool:
    try:
        return isinstance(extract_json_value(text or ""), dict)
    except ValueError:
        return False


# v0.38.1 post-release: the first `npx mcporter …` also downloads mcporter (with a native bundler binding) — that
# install used to run inside the 150 s budget of the first tool call. Fetch it once, on its own budget, first.
NPX_MCPORTER_WARMUP_TIMEOUT_SECONDS = 300.0


def _is_npx_mcporter(command: list[str]) -> bool:
    # PureWindowsPath splits on both "/" and "\\", so the check reads the same on every host.
    return len(command) == 2 and PureWindowsPath(command[0]).name.lower() in {"npx", "npx.cmd", "npx.exe"} and command[1] == "mcporter"


def _warm_npx_mcporter(command: list[str], *, cwd: Path) -> float | None:
    """When mcporter resolves through the npx fallback, run `npx mcporter --version` once so npx's first-run install
    is not charged to a tool call's timeout. Returns seconds spent, or None when mcporter is a real executable."""
    if not _is_npx_mcporter(command):
        return None
    warm_command = [*command, "--version"]
    started = time.perf_counter()
    try:
        subprocess.run(
            warm_command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=NPX_MCPORTER_WARMUP_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            str(exc), code="client.command_not_found", details={"command": warm_command, "cwd": str(cwd), "phase": "npx_install"}
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            bilingual(
                f"npx 在 {NPX_MCPORTER_WARMUP_TIMEOUT_SECONDS:.0f} 秒内没下载完 mcporter（首次使用时 npx 会先下载它）。",
                f"npx did not finish fetching mcporter within {NPX_MCPORTER_WARMUP_TIMEOUT_SECONDS:.0f} seconds (npx downloads it on first use).",
            ),
            code="client.command_timeout",
            details={
                "command": warm_command,
                "cwd": str(cwd),
                "phase": "npx_install",
                "timeout_seconds": NPX_MCPORTER_WARMUP_TIMEOUT_SECONDS,
                "output_complete": False,
                "stderr": _timeout_output_text(exc.stderr)[-4000:],
            },
        ) from exc
    # The exit code is deliberately ignored: this step only pays for the download. A broken install surfaces on the
    # first real call with its own error.
    return round(time.perf_counter() - started, 3)


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
        stdout_text = _timeout_output_text(exc.stdout)
        stderr_text = _timeout_output_text(exc.stderr)
        raise RuntimeError(
            f"Command timed out after {timeout_seconds} seconds: {' '.join(command)}",
            code="client.command_timeout",
            details={
                "command": command,
                "cwd": str(cwd),
                "timeout_seconds": timeout_seconds,
                # True = the command had already printed a complete JSON result and then did not exit: something in its
                # process tree (usually the stdio server it started) kept the pipes open. False = it never finished.
                "output_complete": _has_json_object(stdout_text),
                "stdout": stdout_text[-4000:],
                "stderr": stderr_text[-4000:],
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
    mcporter_command = resolve_mcporter_command()
    npx_warmup_seconds = _warm_npx_mcporter(mcporter_command, cwd=workspace_root)

    def call_tool(tool_name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        command = [
            *mcporter_command,
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
                *mcporter_command,
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
        "npx_warmup_seconds": npx_warmup_seconds,
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
