"""The gateway Dockerfile must COPY every source path the wheel force-includes (v0.38.0 B0).

`pyproject.toml` force-includes `scripts/runtime_templates/windows` into the wheel (the Windows launcher
templates, v0.36.0 C4). The tracked Dockerfile copied only `pyproject.toml README.md src`, so `uv pip
install --system .` aborted inside the image — the same failure shape as the `.mcpbignore` lesson: a
build-time include list and a packaging COPY list drifting apart with nothing comparing them.
"""

from __future__ import annotations

import shlex
import tomllib
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]


def force_include_sources(pyproject_text: str) -> list[str]:
    data = tomllib.loads(pyproject_text)
    wheel = data["tool"]["hatch"]["build"]["targets"]["wheel"]
    sources = list(wheel.get("force-include", {}).keys())
    sources.extend(wheel.get("packages", []))
    return sources


def copy_sources(dockerfile_text: str) -> list[str]:
    sources: list[str] = []
    for line in dockerfile_text.splitlines():
        if not line.strip().upper().startswith("COPY "):
            continue
        parts = [part for part in shlex.split(line.strip())[1:] if not part.startswith("--")]
        sources.extend(parts[:-1])
    return sources


def uncovered(sources: list[str], copies: list[str]) -> list[str]:
    def covered(source: str) -> bool:
        return any(source == copy or source.startswith(copy.rstrip("/") + "/") for copy in copies)

    return sorted(source for source in sources if not covered(source))


def test_dockerfile_copies_every_force_included_source() -> None:
    sources = force_include_sources((PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    copies = copy_sources((PKG_ROOT / "Dockerfile").read_text(encoding="utf-8"))
    assert "scripts/runtime_templates/windows" in sources, "the guard's reason to exist vanished from pyproject"
    assert uncovered(sources, copies) == [], (
        "Dockerfile does not COPY these wheel inputs, so `uv pip install .` fails inside the image"
    )


def test_guard_fires_when_the_template_copy_is_missing() -> None:
    """Negative control: the Dockerfile as tracked before v0.38.0 must be red."""
    legacy = "FROM python:3.12-slim\nCOPY pyproject.toml README.md ./\nCOPY src ./src\nRUN uv pip install --system .\n"
    sources = force_include_sources((PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert uncovered(sources, copy_sources(legacy)) == ["scripts/runtime_templates/windows"]
    fixed = legacy.replace("COPY src ./src\n", "COPY src ./src\nCOPY scripts/runtime_templates ./scripts/runtime_templates\n")
    assert uncovered(sources, copy_sources(fixed)) == []
