#!/usr/bin/env python3
"""Cross-tree gate: the committed `horosa-core-js/dist/app-charts.cjs` must be exactly what the pinned upstream builds.

The report figures run the 星阙 app's own chart code from that bundle (reports/app_charts.py). It is built from a
Horosa-Public checkout by `horosa-core-js/app-charts/build.mjs`; this rebuilds it in memory from HOROSA_SOURCE_ROOT and
fails when the bundle, its license notice or `contracts/app_charts_bundle.json` differ — i.e. upstream chart code moved
(re-vendor: rerun the build and look at the figures) or someone edited the bundle by hand.

    HOROSA_SOURCE_ROOT=/path/to/Horosa-Public uv run python scripts/verify_app_charts_bundle.py

Needs Node ≥ 20 and `npm ci` in horosa-core-js (esbuild / d3 / linkedom are devDependencies). Part of preflight_release.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

PKG_ROOT = Path(__file__).resolve().parents[1]
CORE_JS = PKG_ROOT / "horosa-core-js"


def main() -> int:
    source_root = os.environ.get("HOROSA_SOURCE_ROOT")
    if not source_root or not (Path(source_root).expanduser() / "Horosa-Web" / "astrostudyui" / "src").is_dir():
        print("app-charts: FAIL — HOROSA_SOURCE_ROOT must be a Horosa-Public checkout (Horosa-Web/astrostudyui/src)", file=sys.stderr)
        return 2
    node = os.environ.get("HOROSA_NODE_BIN") or shutil.which("node")
    if not node:
        print("app-charts: FAIL — node not found (set HOROSA_NODE_BIN)", file=sys.stderr)
        return 2
    if not (CORE_JS / "node_modules" / "esbuild").is_dir():
        print("app-charts: FAIL — run `npm ci` in horosa-skill/horosa-core-js first (esbuild is a devDependency)", file=sys.stderr)
        return 2
    result = subprocess.run(
        [node, "app-charts/build.mjs", "--source-root", str(Path(source_root).expanduser()), "--check"],
        cwd=CORE_JS,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
