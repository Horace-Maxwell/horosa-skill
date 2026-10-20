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

import errno
import os
import socket
from pathlib import Path

# 🔴 Tests never talk to 127.0.0.1:8899 / :9999 — the maintainer's desktop app lives there (AGENTS iron rule 8).
# `run_ci_gates.py` pins both backends to the unreachable :9, but a plain `uv run pytest` did not: 34 tests build
# `Settings(...)` with the default ports, and code without an explicit *_SERVER_ROOT falls back to them, so on a machine
# with the desktop app open those tests sent real requests to it (2026-10-20 audit). Now (1) both roots default to :9
# exactly as in CI — children spawned by tests inherit that — and (2) any in-process connect to the desktop ports is
# refused as if nothing listened, which is what CI sees. Live runs name their instance explicitly (8877/9977) and are
# untouched: setdefault never overrides an explicit value.
for _var in ("HOROSA_SERVER_ROOT", "HOROSA_CHART_SERVER_ROOT"):
    if not os.environ.get(_var):
        os.environ[_var] = "http://127.0.0.1:9"

DESKTOP_PORTS = frozenset({8899, 9999})
_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1", "0.0.0.0", "::"})
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
DESKTOP_REFUSAL = "tests never connect to the maintainer's desktop app on 127.0.0.1:8899/9999"


def _is_desktop(address: object) -> bool:
    return isinstance(address, tuple) and len(address) >= 2 and address[1] in DESKTOP_PORTS and str(address[0]) in _LOOPBACK


def _guarded_connect(self: socket.socket, address: object) -> None:
    if _is_desktop(address):
        raise ConnectionRefusedError(errno.ECONNREFUSED, DESKTOP_REFUSAL)
    _real_connect(self, address)


def _guarded_connect_ex(self: socket.socket, address: object) -> int:
    if _is_desktop(address):
        return errno.ECONNREFUSED
    return _real_connect_ex(self, address)


socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
socket.socket.connect_ex = _guarded_connect_ex  # type: ignore[method-assign]

REPO_CORE_JS_ROOT = Path(__file__).resolve().parents[1] / "horosa-core-js"
REPO_SRC = Path(__file__).resolve().parents[1] / "src"

if REPO_CORE_JS_ROOT.is_dir():
    os.environ.setdefault("HOROSA_CORE_JS_ROOT", str(REPO_CORE_JS_ROOT))

_pythonpath = [part for part in os.environ.get("PYTHONPATH", "").split(os.pathsep) if part]
if str(REPO_SRC) not in _pythonpath:
    os.environ["PYTHONPATH"] = os.pathsep.join([str(REPO_SRC), *_pythonpath])
