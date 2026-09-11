from __future__ import annotations

import glob
import hashlib
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


def _first_existing_path(candidates: list[str]) -> str | None:
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def _windows_uv_fallbacks() -> list[str]:
    candidates: list[str] = []
    local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
    appdata = os.environ.get("APPDATA", "").strip()
    userprofile = os.environ.get("USERPROFILE", "").strip()

    if local_appdata:
        candidates.append(os.path.join(local_appdata, "Programs", "uv", "uv.exe"))
        candidates.extend(
            sorted(
                glob.glob(os.path.join(local_appdata, "Programs", "Python", "Python*", "Scripts", "uv.exe")),
                reverse=True,
            )
        )
    if appdata:
        candidates.extend(
            sorted(
                glob.glob(os.path.join(appdata, "Python", "Python*", "Scripts", "uv.exe")),
                reverse=True,
            )
        )
    if userprofile:
        candidates.append(os.path.join(userprofile, ".local", "bin", "uv.exe"))
    return candidates


def _windows_uvx_fallbacks() -> list[str]:
    """Same directories as uv: uv ships `uvx.exe` next to `uv.exe`."""
    return [candidate[: -len("uv.exe")] + "uvx.exe" for candidate in _windows_uv_fallbacks() if candidate.endswith("uv.exe")]


def _windows_mcporter_fallbacks() -> list[str]:
    appdata = os.environ.get("APPDATA", "").strip()
    if not appdata:
        return []
    npm_root = os.path.join(appdata, "npm")
    return [
        os.path.join(npm_root, "mcporter.cmd"),
        os.path.join(npm_root, "mcporter.exe"),
        os.path.join(npm_root, "mcporter"),
    ]


def _windows_npx_fallbacks() -> list[str]:
    appdata = os.environ.get("APPDATA", "").strip()
    if not appdata:
        return []
    npm_root = os.path.join(appdata, "npm")
    return [
        os.path.join(npm_root, "npx.cmd"),
        os.path.join(npm_root, "npx.exe"),
        os.path.join(npm_root, "npx"),
    ]


def _resolve_command(
    *,
    override_env: str,
    candidates: list[str],
    error_message: str,
    npx_package: str | None = None,
    windows_fallbacks: list[str] | None = None,
    windows_npx_fallbacks: list[str] | None = None,
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
    windows_fallbacks: list[str] | None = None
    windows_npx_fallbacks: list[str] | None = None
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
    windows_fallbacks: list[str] | None = None
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


def resolve_uvx_command() -> list[str]:
    """Absolute path to `uvx` (v0.38.0 B2).

    GUI clients on Windows (Claude Desktop, Cursor, VS Code…) spawn the server WITHOUT the user's shell
    PATH, so a bare `"command": "uvx"` in their config fails with "file not found" while the same
    command works in a terminal. Resolution: `HOROSA_UVX_BIN` → PATH (`uvx.exe`/`uvx.cmd`/`uvx` on
    Windows) → the known Windows install dirs → the `uvx` sibling of whatever `resolve_uv_command`
    found. No `cmd /c` wrapper is ever needed: uv ships real executables, only `.cmd` shims need a shell.
    """
    candidates = ["uvx"]
    windows_fallbacks: list[str] | None = None
    if os.name == "nt":
        candidates = ["uvx.exe", "uvx.cmd", "uvx"]
        windows_fallbacks = _windows_uvx_fallbacks()
    try:
        return _resolve_command(
            override_env="HOROSA_UVX_BIN",
            candidates=candidates,
            windows_fallbacks=windows_fallbacks,
            error_message="uvx not found",
        )
    except FileNotFoundError:
        pass
    try:
        uv_path = resolve_uv_command()[0]
    except FileNotFoundError:
        uv_path = ""
    if uv_path and os.path.isabs(uv_path):
        stem = os.path.basename(uv_path)
        sibling_name = "uvx.exe" if stem.lower().endswith(".exe") else "uvx"
        sibling = os.path.join(os.path.dirname(uv_path), sibling_name)
        if os.path.isfile(sibling):
            return [sibling]
    raise FileNotFoundError(
        "uvx was not found in PATH (or next to uv). Install uv (https://docs.astral.sh/uv/), "
        "or set HOROSA_UVX_BIN to an explicit executable path. GUI clients on Windows do not inherit "
        "your shell PATH, so the config must carry an absolute path."
    )


def wheel_asset_name(version: str) -> str:
    """hatchling normalises `horosa-skill` to `horosa_skill` in the wheel filename."""
    return f"horosa_skill-{version}-py3-none-any.whl"


def zero_install_wheel_url(version: str | None = None, repo: str | None = None) -> str:
    """The pure-Python wheel attached to every GitHub Release (v0.38.0 B3): `uvx --from <this>` needs
    neither git nor PyPI on the user's machine, and the URL goes through HOROSA_RUNTIME_MIRROR like the
    runtime archives do."""
    from horosa_skill import __version__
    from horosa_skill.config import DEFAULT_RELEASE_REPO

    version = version or __version__
    repo = repo or DEFAULT_RELEASE_REPO
    return f"https://github.com/{repo}/releases/download/v{version}/{wheel_asset_name(version)}"


def isolated_runtime_root(home_dir: Path) -> Path:
    home = home_dir.expanduser().resolve()
    return home / ".horosa" / "runtime"


def isolated_data_dir(home_dir: Path) -> Path:
    home = home_dir.expanduser().resolve()
    return home / ".horosa-skill"


def isolated_runtime_ports(home_dir: Path) -> tuple[int, int]:
    home = str(home_dir.expanduser().resolve())
    digest = hashlib.sha256(home.encode("utf-8")).digest()
    offset = int.from_bytes(digest[:2], "big") % 20000
    backend_port = 20000 + (offset * 2)
    chart_port = backend_port + 1
    return backend_port, chart_port


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
        if isinstance(value, (dict, list)):
            # Some stdio clients prepend or append human diagnostics around the
            # JSON body. The self-check path needs the first complete JSON
            # value, not a perfect stdout stream.
            return value

    raise ValueError("No JSON content was found.")
