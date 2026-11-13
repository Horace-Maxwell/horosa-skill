"""`client openclaw-setup` / `openclaw-check` 的流程。命令函数只管打印与退出码：报告从这里返回，失败走 refusals。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import typer

from horosa_skill.client_config.merge import _write_json_file
from horosa_skill.client_config.openclaw import (
    _build_openclaw_config,
    _default_openclaw_native_config_path,
    _isolated_env_vars,
    _write_openclaw_native_config,
)
from horosa_skill.client_config.payload import _resolve_skill_root
from horosa_skill.config import Settings
from horosa_skill.errors import RuntimeError, bilingual
from horosa_skill.surfaces import openclaw_smoke, runtime_helpers
from horosa_skill.surfaces.openclaw_smoke import (
    _friendly_runtime_error_payload,
    _openclaw_setup_command,
    _setup_summary,
    _timed_call,
)
from horosa_skill.surfaces.refusals import _emit_refusal, _write_refusal
from horosa_skill.winproc import NO_WINDOW


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


def _run_openclaw_setup(
    *,
    workspace: Path,
    skill_root: Path,
    server_name: str,
    isolate_home: Path | None,
    config: Path | None,
    native_config: Path | None,
    write_native_config: bool,
    skip_smoke: bool,
    manifest_url: str | None,
) -> dict[str, Any]:
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
        manager = runtime_helpers._runtime_manager(settings)
        try:
            install_result, install_seconds = _timed_call(lambda: manager.install(manifest_url=manifest_url))
            start_result, start_seconds = _timed_call(lambda: manager.start_local_services())
            doctor_result, doctor_seconds = _timed_call(manager.doctor)
            smoke_report: dict[str, Any] | None = None
            smoke_seconds: float | None = None
            if not skip_smoke:
                smoke_output = settings.data_dir / "openclaw_setup_smoke_check.json"
                smoke_report, smoke_seconds = _timed_call(
                    lambda: openclaw_smoke._run_openclaw_smoke_check(
                        workspace_root=workspace_root,
                        config_path=config_path,
                        output_path=smoke_output,
                        include_list=False,
                    )
                )
        except RuntimeError as exc:
            _write_refusal(
                _friendly_runtime_error_payload(
                    exc,
                    action_label="OpenClaw setup",
                    workspace_root=workspace_root,
                    config_path=config_path,
                )
            )

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
    return report


def _run_openclaw_check(
    *, workspace: Path, config: Path | None, full: bool, output: Path | None
) -> tuple[dict[str, Any] | None, bool]:
    """(要打印的报告, 是否以退出码 2 结束)。全量自检没写出报告时返回 None，错误输出已转到 stderr。"""
    settings = Settings.from_env()
    workspace_root = workspace.expanduser().resolve()
    config_path = (config.expanduser().resolve() if config is not None else workspace_root / "config" / "mcporter.json")
    if not config_path.exists():
        _emit_refusal(
            "client.config_missing",
            f"mcporter config not found: {config_path}",
            {"config": str(config_path), "workspace": str(workspace_root)},
            status="needs_attention",
            ready_for_openclaw=False,
            user_summary="OpenClaw config not found yet.",
            next_action=f"Run `{_openclaw_setup_command(workspace_root)}` to create a ready-to-use config and smoke test it.",
        )

    default_output = settings.data_dir / ("openclaw_full_check.json" if full else "openclaw_smoke_check.json")
    output_path = (output.expanduser().resolve() if output is not None else default_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if full:
        script_path = runtime_helpers._package_root() / "scripts" / "run_openclaw_full_self_check.py"
        if not script_path.is_file():
            # 全量自检脚本只在源码仓里（不进 wheel）：uvx / pip 装的包跑 --full 以前只回一句 Python 的
            # "can't open file"。现在说清楚为什么、下一步怎么走；快速体检（不带 --full）照常可用。
            _emit_refusal(
                "openclaw_check.full_unavailable",
                bilingual(
                    "全量自检脚本只随源码仓分发，当前安装（wheel / uvx）里没有它。",
                    "The exhaustive self-check script ships with the source checkout only, not with this install.",
                ),
                {"expected_script": str(script_path)},
                next_action=(
                    "Run the quick check without --full, or clone "
                    "https://github.com/Horace-Maxwell/horosa-skill and run "
                    "`uv run horosa-skill client openclaw-check --full` from its horosa-skill/ directory."
                ),
            )
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
            result = subprocess.run(
                command, capture_output=True, text=True, check=False, timeout=900, encoding="utf-8", errors="replace",
                creationflags=NO_WINDOW,
            )
        except subprocess.TimeoutExpired:
            _emit_refusal("openclaw_check.timeout", "openclaw-check --full exceeded 900s and was aborted (a child MCP/runtime process is likely wedged).")
        report = None
        if output_path.exists():
            report = json.loads(output_path.read_text(encoding="utf-8"))
        else:
            typer.echo(result.stderr or result.stdout, err=True)
        return report, result.returncode != 0

    try:
        report = openclaw_smoke._run_openclaw_smoke_check(
            workspace_root=workspace_root,
            config_path=config_path,
            output_path=output_path,
        )
    except RuntimeError as exc:
        _write_refusal(
            _friendly_runtime_error_payload(
                exc,
                action_label="OpenClaw smoke check",
                workspace_root=workspace_root,
                config_path=config_path,
            )
        )
    return report, not report["ok"]
