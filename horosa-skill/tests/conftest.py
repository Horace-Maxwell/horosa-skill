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

import pytest

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


@pytest.fixture(autouse=True)
def _host_smart_app_control_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """生成的客户端配置不许随维护机的 Smart App Control 状态变（v0.43.1-dev）。

    `--entry auto` 在 SAC 为「开」的 Windows 上写 `python -m horosa_skill`；不钉住，断言 `horosa-skill serve` 的用例在这类维护机上红、
    CI（没有 SAC）上绿。要测 SAC 分支的用例自己 monkeypatch `manager.smart_app_control_state`；真读注册表走 `read_smart_app_control_state`。
    """
    from horosa_skill.runtime import manager

    monkeypatch.setattr(manager, "smart_app_control_state", lambda: None)


@pytest.fixture(autouse=True)
def _never_touch_the_users_real_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    """测试永不读写用户真实的数据目录与 runtime。

    `Settings()` / `Settings.from_env()` 没给 data_dir / runtime_root 时落到 `%APPDATA%/HorosaSkill` 与
    `%LOCALAPPDATA%/Horosa/runtime`（mac/Linux：`~/.horosa-skill` 与 `~/.horosa/runtime`）。维护机上那里装着真 runtime、
    真记忆库：测试会往真 traces 里写记录；server_root 指向无人监听的端口、又没给 runtime_root 的用例更会去「启动」
    真 runtime、改写它的 boot jar（2026-10-20 Windows 实测：jar 被运行中的 Java 锁着 → WinError 5，残留 324 MB 临时文件；
    mac 上 jar 不被锁，改写会直接成功）。拒连 8899/9999 只挡住了网络，挡不住这条文件系统路径。
    CI 上两个目录是空的，所以只在维护机咬人。要测默认路径解析本身的用例自己再 monkeypatch。
    """
    from horosa_skill import config

    base = tmp_path_factory.mktemp("user-dirs")
    monkeypatch.setattr(config, "_default_home_dir", lambda: base / "data")
    monkeypatch.setattr(config, "_default_runtime_root", lambda: base / "runtime")
