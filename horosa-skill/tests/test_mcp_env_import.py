"""坏的 HOROSA_MCP_MAX_CONCURRENT_TOOLS 不许在 import 时打死整个 CLI（v0.47.2-dev）。

`mcp_runner` 模块级 `int(os.environ…)`，而 `surfaces/cli.py` 顶层 import 了 MCP server：一个写错的值让 `--version`、`--help`、`doctor`
全部 ValueError 退出，连能帮你查环境变量的命令都起不来。只有真子进程抓得到——CliRunner 进来时模块早就 import 完了。"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest


def _version_with(value: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "HOROSA_MCP_MAX_CONCURRENT_TOOLS": value}
    return subprocess.run([sys.executable, "-m", "horosa_skill", "--version"], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, timeout=120)


@pytest.mark.parametrize("value", ["abc", "4.5", " "])
def test_a_bad_value_does_not_kill_the_cli_at_import(value: str) -> None:
    result = _version_with(value)
    assert result.returncode == 0, result.stderr[-400:]
    assert "ValueError" not in result.stderr


@pytest.mark.parametrize(("value", "expected"), [("abc", 4), ("", 4), ("7", 7), ("0", 1), ("-3", 1)])
def test_the_limit_keeps_its_meaning(value: str, expected: int) -> None:
    code = "from horosa_skill.surfaces import mcp_runner as r; print(r._MAX_CONCURRENT_TOOLS)"
    env = {**os.environ, "HOROSA_MCP_MAX_CONCURRENT_TOOLS": value}
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=120)
    assert done.returncode == 0, done.stderr[-400:]
    assert int(done.stdout.strip().splitlines()[-1]) == expected
