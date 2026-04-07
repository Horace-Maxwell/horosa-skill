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


def _first_existing_path(candidates: list[Path]) -> str | None:
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _windows_uv_fallbacks() -> list[Path]:
    candidates: list[Path] = []
    local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
    appdata = os.environ.get("APPDATA", "").strip()
    userprofile = os.environ.get("USERPROFILE", "").strip()

    if local_appdata:
        candidates.append(Path(local_appdata) / "Programs" / "uv" / "uv.exe")
        candidates.extend(sorted((Path(local_appdata) / "Programs" / "Python").glob("Python*\\Scripts\\uv.exe"), reverse=True))
    if appdata:
        candidates.extend(sorted((Path(appdata) / "Python").glob("Python*\\Scripts\\uv.exe"), reverse=True))
    if userprofile:
        candidates.append(Path(userprofile) / ".local" / "bin" / "uv.exe")
    return candidates


def _windows_mcporter_fallbacks() -> list[Path]:
    appdata = os.environ.get("APPDATA", "").strip()
    if not appdata:
        return []
    npm_root = Path(appdata) / "npm"
    return [
        npm_root / "mcporter.cmd",
        npm_root / "mcporter.exe",
        npm_root / "mcporter",
    ]


def _windows_npx_fallbacks() -> list[Path]:
    appdata = os.environ.get("APPDATA", "").strip()
    if not appdata:
        return []
    npm_root = Path(appdata) / "npm"
    return [
        npm_root / "npx.cmd",
        npm_root / "npx.exe",
        npm_root / "npx",
    ]


def _resolve_command(
    *,
    override_env: str,
    candidates: list[str],
    error_message: str,
    npx_package: str | None = None,
    windows_fallbacks: list[Path] | None = None,
    windows_npx_fallbacks: list[Path] | None = None,
) -> list[str]:
    override = os.environ.get(override_env, "").strip()
    if override:
        return _split_command_override(override)

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved]

    if os.name == "nt" and windows_fallbacks:
        resolved = _first_existing_path(windows_fallbacks)
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
        if os.name == "nt" and windows_npx_fallbacks:
            resolved = _first_existing_path(windows_npx_fallbacks)
            if resolved:
                return [resolved, npx_package]

    raise FileNotFoundError(error_message)


def resolve_mcporter_command() -> list[str]:
    candidates = ["mcporter"]
    windows_fallbacks: list[Path] | None = None
    windows_npx_fallbacks: list[Path] | None = None
    if os.name == "nt":
        candidates = ["mcporter.cmd", "mcporter.exe", "mcporter"]
        windows_fallbacks = _windows_mcporter_fallbacks()
        windows_npx_fallbacks = _windows_npx_fallbacks()
    return _resolve_command(
        override_env="HOROSA_MCPORTER_BIN",
        candidates=candidates,
        npx_package="mcporter",
        windows_fallbacks=windows_fallbacks,
        windows_npx_fallbacks=windows_npx_fallbacks,
        error_message=(
            "mcporter was not found in PATH. Install it with `npm i -g mcporter`, "
            "or set HOROSA_MCPORTER_BIN to an explicit executable path."
        ),
    )


def resolve_uv_command() -> list[str]:
    candidates = ["uv"]
    windows_fallbacks: list[Path] | None = None
    if os.name == "nt":
        candidates = ["uv.exe", "uv.cmd", "uv"]
        windows_fallbacks = _windows_uv_fallbacks()
    return _resolve_command(
        override_env="HOROSA_UV_BIN",
        candidates=candidates,
        windows_fallbacks=windows_fallbacks,
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
