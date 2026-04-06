from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path


def resolve_mcporter_command() -> list[str]:
    override = os.environ.get("HOROSA_MCPORTER_BIN", "").strip()
    if override:
        return shlex.split(override)

    candidates = ["mcporter"]
    if os.name == "nt":
        candidates = ["mcporter.cmd", "mcporter.exe", "mcporter"]

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved]

    npx_candidates = ["npx"]
    if os.name == "nt":
        npx_candidates = ["npx.cmd", "npx.exe", "npx"]
    for candidate in npx_candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved, "mcporter"]

    raise FileNotFoundError(
        "mcporter was not found in PATH. Install it with `npm i -g mcporter`, "
        "or set HOROSA_MCPORTER_BIN to an explicit executable path."
    )


def isolated_runtime_root(home_dir: Path) -> Path:
    home = home_dir.expanduser().resolve()
    return home / ".horosa" / "runtime"


def isolated_data_dir(home_dir: Path) -> Path:
    home = home_dir.expanduser().resolve()
    return home / ".horosa-skill"
