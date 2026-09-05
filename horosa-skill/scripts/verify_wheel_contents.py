#!/usr/bin/env python3
"""Build the wheel and assert everything `uvx horosa-skill` needs is inside it.

PyPI is the v0.36.0 distribution channel (issues #6/#11/#14 were all the "clone + uv sync" barrier).
A wheel that installs but lacks its data files fails at the first knowledge lookup, bench run, or
clarification gate — silently, on the user's machine. This guard builds the wheel exactly like the
publish workflow (`uv build --wheel`) and checks the entries the runtime code reads via
`importlib.resources` / `Path(__file__)`:

- knowledge packs + index (`knowledge/data/**`), the bench dataset, the clarification-gate table,
- the Windows start/stop script overrides (force-included from scripts/runtime_templates), with their
  UTF-8 BOM intact,
- the console script entry point.

`horosa-core-js` is deliberately NOT in the wheel: the offline runtime payload bundles it
(`artifacts.horosa_core_js_root`) and `HOROSA_CORE_JS_ROOT` overrides it. Stdlib + uv. Wired into CI.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ENTRIES = (
    "horosa_skill/knowledge/data/index.json",
    "horosa_skill/knowledge/data/helpdocs/bazi.json",
    "horosa_skill/knowledge/data/helpdocs/bazi_pithy.json",
    "horosa_skill/benchmark/data/horosa_bench.json",
    "horosa_skill/data/sensitive_settings.json",
    "horosa_skill/runtime/templates/windows/start_horosa_local.ps1",
    "horosa_skill/runtime/templates/windows/stop_horosa_local.ps1",
    "horosa_skill/surfaces/mcp_server.py",
    "horosa_skill/surfaces/mcp_schema.py",
)
MIN_HELPDOC_PACKS = 18


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="horosa-wheel-") as tmp:
        completed = subprocess.run(
            ["uv", "build", "--wheel", "-o", tmp], cwd=PKG_ROOT, capture_output=True, text=True, check=False
        )
        if completed.returncode != 0:
            print("wheel-contents: `uv build --wheel` failed:", file=sys.stderr)
            print(completed.stderr[-2000:], file=sys.stderr)
            return 1
        wheels = sorted(Path(tmp).glob("*.whl"))
        if len(wheels) != 1:
            print(f"wheel-contents: expected exactly one wheel, got {[w.name for w in wheels]}", file=sys.stderr)
            return 1
        with zipfile.ZipFile(wheels[0]) as archive:
            names = set(archive.namelist())
            entry_points = next((n for n in names if n.endswith("entry_points.txt")), None)
            entry_text = archive.read(entry_points).decode("utf-8") if entry_points else ""
            launcher_heads = {n: archive.read(n)[:3] for n in names if n.endswith(".ps1")}
        errors = [f"missing {entry}" for entry in REQUIRED_ENTRIES if entry not in names]
        # The .ps1 overrides must keep their UTF-8 BOM *inside the wheel*: Windows PowerShell 5.1
        # decodes a BOM-less file as ANSI, and one non-ASCII character then unparses the whole
        # launcher (v0.25.1 — `runtime.start_failed` before a single service starts). The source-tree
        # test covers scripts/runtime_templates; this covers the artifact `uvx horosa-skill` ships.
        for name, head in launcher_heads.items():
            if head != b"\xef\xbb\xbf":
                errors.append(f"{name} lost its UTF-8 BOM inside the wheel (Windows PowerShell 5.1 would parse it as ANSI)")
        packs = [n for n in names if n.startswith("horosa_skill/knowledge/data/helpdocs/") and n.endswith(".json")]
        if len(packs) < MIN_HELPDOC_PACKS:
            errors.append(f"only {len(packs)} helpdoc packs in the wheel (expected ≥ {MIN_HELPDOC_PACKS})")
        if "horosa-skill = horosa_skill.surfaces.cli:app" not in entry_text:
            errors.append("console script `horosa-skill` entry point missing from entry_points.txt")
        if any("horosa-core-js" in n for n in names):
            errors.append("horosa-core-js must not be vendored into the wheel (it ships in the runtime payload)")
        if errors:
            print(f"wheel-contents FAILED ({wheels[0].name}):", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1
        print(f"wheel-contents OK: {wheels[0].name} carries {len(names)} entries, {len(packs)} helpdoc packs, runtime templates, console script")
        return 0


if __name__ == "__main__":
    sys.exit(main())
