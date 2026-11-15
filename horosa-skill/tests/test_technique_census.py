"""审计 A-1 第 0 期 / PF-21：技法登记普查。改了哪个技法进出哪张表，这条就红；有意的改动重录：

    uv run python scripts/technique_census.py --write

`technique_census.py <技法名>` 列出它在哪些表里——新增技法时照着同族技法逐张核。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "technique_census.py"


def _census():
    spec = importlib.util.spec_from_file_location("technique_census", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["technique_census"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_every_technique_sits_in_the_recorded_tables() -> None:
    """新进程里跑 --check：运行中才填的缓存（_VERIFIED_EXAMPLES / memory.search._TOOL_NAMES）随前面跑过的用例变，同进程跑会抖。
    负向对照（实跑过）：把 xiaoliuren 从 engine.intents.CANDIDATE_NOTES 摘掉 → --check 报 xiaoliuren 少了这张表 → 红。"""
    import os
    import subprocess

    env = {**os.environ, "HOROSA_SERVER_ROOT": "http://127.0.0.1:9", "HOROSA_CHART_SERVER_ROOT": "http://127.0.0.1:9"}
    result = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True, encoding="utf-8",
                            errors="replace", env=env, timeout=300, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_full_coverage_tables_cover_every_technique() -> None:
    census = _census()
    tables = census.census()
    techniques = census._tool_names()
    full = [table for table, members in tables.items() if set(members) == techniques]
    assert any(table.endswith(":TOOL_GUIDANCE") for table in full) and any(table.endswith(":TOOL_SYNONYMS") for table in full)
