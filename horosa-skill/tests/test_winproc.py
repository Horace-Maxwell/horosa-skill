"""后台子进程在 Windows 上不弹控制台窗口（v0.50.2-dev，Windows 原生复验）。

MCP server 没有控制台时（GUI 宿主以 DETACHED 方式起、或 pythonw），它拉起的每个控制台程序都会新开一个可见窗口：实测每次
`tool run` 闪两个（node 版本探针 + 引擎）。修法是每个 spawn 都带 `winproc.NO_WINDOW`；这里扫全部源码，漏一个就红。
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from horosa_skill import winproc

SRC = Path(__file__).resolve().parents[1] / "src" / "horosa_skill"
_SPAWNERS = {"run", "Popen", "call", "check_call", "check_output"}


def _spawn_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _SPAWNERS
        and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"
    ]


def test_every_subprocess_spawn_passes_the_no_window_flag() -> None:
    """负向对照：去掉 js_client 里任一处 creationflags → 红（实跑过）。`**kwargs` 透传的（启动器）自己在 kwargs 里设。"""
    missing, seen = [], 0
    for path in sorted(SRC.rglob("*.py")):
        for call in _spawn_calls(ast.parse(path.read_text(encoding="utf-8"))):
            seen += 1
            if not any(kw.arg == "creationflags" or kw.arg is None for kw in call.keywords):
                missing.append(f"{path.relative_to(SRC)}:{call.lineno}")
    assert seen >= 14, "扫描器没扫到 spawn——守卫自己坏了"
    assert missing == [], missing


def test_no_window_is_zero_off_windows() -> None:
    assert winproc.NO_WINDOW == (subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


@pytest.mark.skipif(os.name != "nt", reason="[platform] 控制台窗口是 Windows 的概念")
def test_a_child_of_a_console_less_parent_gets_no_window() -> None:
    """父进程以 DETACHED_PROCESS 起（没有控制台），子进程带 NO_WINDOW 时拿不到控制台窗口。
    对照（不带标志 → 拿到可见窗口）在复验时实跑过，这里不跑——它会在维护者屏幕上真弹窗口。"""
    report = ("import ctypes,json;print(json.dumps(ctypes.windll.kernel32.GetConsoleWindow()))")
    middle = (
        "import subprocess,sys;from horosa_skill.winproc import NO_WINDOW;"
        f"print(subprocess.run([sys.executable,'-c',{report!r}],capture_output=True,text=True,"
        "creationflags=NO_WINDOW).stdout.strip())"
    )
    out = subprocess.run([sys.executable, "-c", middle], capture_output=True, text=True, timeout=60,
                         creationflags=subprocess.DETACHED_PROCESS, env={**os.environ, "PYTHONPATH": str(SRC.parent)})
    assert json.loads(out.stdout.strip()) == 0, out.stderr[-400:]
