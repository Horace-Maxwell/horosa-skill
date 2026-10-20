"""OpenClaw / mcporter 的配置：horosa server 块（可隔离 HOME）、mcporter / openclaw 两种格式，以及 openclaw.json 原生配置的读、合并、写。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import typer

from horosa_skill.client_config.merge import _write_json_file
from horosa_skill.client_tools import (
    isolated_data_dir,
    isolated_runtime_ports,
    isolated_runtime_root,
    resolve_uv_command,
)
from horosa_skill.errors import RuntimeError


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
