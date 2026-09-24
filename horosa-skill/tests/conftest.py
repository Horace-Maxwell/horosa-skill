"""Session-wide pins for the test run.

Why this exists (v0.40.0 upstream-sync lesson): `HorosaJsEngineClient` resolves the core-js engine as
`HOROSA_CORE_JS_ROOT` → the **installed runtime's bundled copy** → this repo's source tree. On a maintainer
machine that has a runtime installed, every JS-backed tool in a test run therefore exercised the *installed*
(possibly months-old) engine instead of the code under test. A live run against a freshly vendored backend
reported jinkou / qimen / tongshefa section gaps that were pure artifacts of the old installed engine, while
the repo's own engine was clean. CI never sees it (no runtime installed there), so it only bites locally —
exactly where live verification happens. Pin the engine root to this repo for the whole session unless the
caller explicitly overrides it (tests that exercise resolution order monkeypatch the resolver directly).

Same shape, Python side: tests that spawn `python -m horosa_skill…` (stdio/http conformance, server exit,
setup probe) get `horosa_skill` from the venv's editable install, which points at whichever checkout ran
`uv sync` — in a git worktree that is the *main* checkout, so those tests exercised main's code (four
parallel implementers saw "116 tools" where their worktree had 120). Prepend this checkout's `src` to
PYTHONPATH so every child imports the code under test.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_CORE_JS_ROOT = Path(__file__).resolve().parents[1] / "horosa-core-js"
REPO_SRC = Path(__file__).resolve().parents[1] / "src"

if REPO_CORE_JS_ROOT.is_dir():
    os.environ.setdefault("HOROSA_CORE_JS_ROOT", str(REPO_CORE_JS_ROOT))

_pythonpath = [part for part in os.environ.get("PYTHONPATH", "").split(os.pathsep) if part]
if str(REPO_SRC) not in _pythonpath:
    os.environ["PYTHONPATH"] = os.pathsep.join([str(REPO_SRC), *_pythonpath])
