from __future__ import annotations

import json
import os
import shlex
import shutil
from pathlib import Path
from typing import Any


def _split_command_override(raw: str) -> list[str]:
    if os.name != "nt":
        return shlex.split(raw)
    parts = shlex.split(raw, posix=False)
    return [part[1:-1] if len(part) >= 2 and part[0] == part[-1] == '"' else part for part in parts]


def _resolve_command(
    *,
    override_env: str,
    candidates: list[str],
    error_message: str,
    npx_package: str | None = None,
) -> list[str]:
    override = os.environ.get(override_env, "").strip()
    if override:
        return _split_command_override(override)

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved]

    if npx_package:
        npx_candidates = ["npx"]
        if os.name == "nt":
            npx_candidates = ["npx.cmd", "npx.exe", "npx"]
        for candidate in npx_candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return [resolved, npx_package]

    raise FileNotFoundError(error_message)


def resolve_mcporter_command() -> list[str]:
    candidates = ["mcporter"]
    if os.name == "nt":
        candidates = ["mcporter.cmd", "mcporter.exe", "mcporter"]
    return _resolve_command(
        override_env="HOROSA_MCPORTER_BIN",
        candidates=candidates,
        npx_package="mcporter",
        error_message=(
            "mcporter was not found in PATH. Install it with `npm i -g mcporter`, "
            "or set HOROSA_MCPORTER_BIN to an explicit executable path."
        ),
    )


def resolve_uv_command() -> list[str]:
    candidates = ["uv"]
    if os.name == "nt":
        candidates = ["uv.exe", "uv.cmd", "uv"]
    return _resolve_command(
        override_env="HOROSA_UV_BIN",
        candidates=candidates,
        error_message=(
            "uv was not found in PATH. Install uv, or set HOROSA_UV_BIN to an explicit executable path."
        ),
    )


def isolated_runtime_root(home_dir: Path) -> Path:
    home = home_dir.expanduser().resolve()
    return home / ".horosa" / "runtime"


def isolated_data_dir(home_dir: Path) -> Path:
    home = home_dir.expanduser().resolve()
    return home / ".horosa-skill"


def extract_json_value(raw: str) -> Any:
    text = raw.strip()
    if not text:
        raise ValueError("No JSON content was found.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    candidates = [index for index, char in enumerate(text) if char in "[{"]
    for index in candidates:
        try:
            value, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        remainder = text[index + end :].strip()
        if not remainder:
            return value

    raise ValueError("No JSON content was found.")
