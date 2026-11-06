"""工具数的写手：加一个技法后一条命令改完全部声明（`bump_version.py --tool-counts`）。

判官是 verify_docs_sync，写手用判官读的同一批形状。这里最要紧的一条是最后那条：在一份真实文档的副本上模拟「多了四个技法」，
写手跑完判官必须全绿——写手漏掉任何判官看得见的声明，这里就红。"""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_{name}_under_test", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


JUDGE = _load("verify_docs_sync")
BUMP = _load("bump_version")
TOTALS = {110: 114, 121: 125}
GATED = {100: 104}


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('<img src="https://img.shields.io/badge/tools-110-1d4ed8" alt="110 tools" />', '<img src="https://img.shields.io/badge/tools-114-1d4ed8" alt="114 tools" />'),
        ("![tools](https://img.shields.io/badge/tools-110-1d4ed8)", "![tools](https://img.shields.io/badge/tools-114-1d4ed8)"),
        ('<img alt="tools" src="https://img.shields.io/badge/技法-110-1d4ed8" />', '<img alt="tools" src="https://img.shields.io/badge/技法-114-1d4ed8" />'),
        ("- **110 个真实技法，一次安装**", "- **114 个真实技法，一次安装**"),
        ("把星阙的 110 个真实术数 / 占星技法做成 MCP", "把星阙的 114 个真实术数 / 占星技法做成 MCP"),
        ('<img src="banner.svg" alt="把星阙 110 个术数 / 占星技法做成 MCP" />', '<img src="banner.svg" alt="把星阙 114 个术数 / 占星技法做成 MCP" />'),
        ("exposes 110 real technique tools", "exposes 114 real technique tools"),
        ("(110 callable tools; latest)", "(114 callable tools; latest)"),
        ("| Claude Code | 全量 121 |", "| Claude Code | 全量 125 |"),
        ("MCP 全量面 121 = 110 技法 + 11 门面", "MCP 全量面 125 = 114 技法 + 11 门面"),
        ("| full (121) |", "| full (125) |"),
        ("连接器里看到 121 个 `horosa_*` 工具", "连接器里看到 125 个 `horosa_*` 工具"),
        ("100 个技法工具触发 must_ask_user", "104 个技法工具触发 must_ask_user"),
        ("100 technique tools trigger must_ask_user", "104 technique tools trigger must_ask_user"),
        ("110 / 110 ok=true", "114 / 114 ok=true"),
    ],
)
def test_every_shape_the_judge_reads_gets_rewritten(line: str, expected: str) -> None:
    assert JUDGE.rewrite_tool_counts(line, totals=TOTALS, gated=GATED) == (expected, 1)


@pytest.mark.parametrize(
    "line",
    [
        "106 条基准用例与工具注册表锁步",  # 工具这个词在行里，但 106 是用例数：v0.47.0 那次重放抓到的误改
        "Cursor 全局约 40 个工具上限",
        "v0.110.0 起的版本 110",
        "116 → 120 工具 <!-- docs-sync:ignore-count -->",
        "110 工具 <!-- docs-sync:ignore-count -->",
        "耗时 110 s，比上一版快",
    ],
)
def test_other_numbers_stay_put(line: str) -> None:
    assert JUDGE.rewrite_tool_counts(line, totals=TOTALS, gated={106: 110}) == (line, 0)


def test_one_pass_does_not_chain_rewrites() -> None:
    """旧闸门数恰好等于新总数时不能串：100→104 之后不许再被 104→108 改一次。"""
    out, _ = JUDGE.rewrite_tool_counts("全量 100 与 104 工具", totals={100: 104, 104: 108}, gated={})
    assert out == "全量 104 与 108 工具"


def test_stated_numbers_are_read_from_the_repo(tmp_path: Path) -> None:
    (tmp_path / "horosa-skill" / "contracts").mkdir(parents=True)
    (tmp_path / "README.md").write_text('<img src="https://img.shields.io/badge/tools-114-1d4ed8" />', encoding="utf-8")
    (tmp_path / "horosa-skill" / "contracts" / "mcp_list_budget.json").write_text('{"full_tools": 125}', encoding="utf-8")
    totals, gated = BUMP.count_changes(tmp_path, techniques=118, full=129, gated=108, exempt=10)
    assert totals == {114: 118, 125: 129} and gated == {104: 108}


def test_the_judge_passes_after_the_hand_runs_on_a_simulated_new_technique(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """多四个技法：把全部 COUNT_DOCS 复制出来，写手改完，判官对这份副本必须没有一条意见。"""
    technique_count = len(JUDGE.TOOL_DEFINITIONS)
    exempt = technique_count - JUDGE.expected_gated()
    for rel in {*JUDGE.COUNT_DOCS, *JUDGE.FULL_SURFACE_DOCS}:
        source = JUDGE.ROOT / rel
        if source.is_file():
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    budget = json.loads((JUDGE.PKG / "contracts" / "mcp_list_budget.json").read_text(encoding="utf-8"))
    full = int(budget["full_tools"])
    grown = technique_count + 4
    totals = {technique_count: grown, full: full + 4}
    gated = {technique_count - exempt: grown - exempt}
    touched = JUDGE.sync_tool_counts(tmp_path, totals=totals, gated=gated)
    assert len(touched) >= 12, "写手应当覆盖全部写工具数的文档"

    contracts = tmp_path / "horosa-skill" / "contracts"
    contracts.mkdir(parents=True, exist_ok=True)
    (contracts / "mcp_list_budget.json").write_text(json.dumps({**budget, "full_tools": full + 4}), encoding="utf-8")
    monkeypatch.setattr(JUDGE, "ROOT", tmp_path)
    monkeypatch.setattr(JUDGE, "PKG", tmp_path / "horosa-skill")
    monkeypatch.setattr(JUDGE, "TOOL_DEFINITIONS", dict.fromkeys(range(grown)))
    monkeypatch.setattr(JUDGE, "check_server_instructions", lambda: None)  # 读的是真模块的常量，与文档无关
    monkeypatch.setattr(JUDGE, "ERRORS", [])
    JUDGE.check_tool_counts()
    JUDGE.check_full_surface_counts()
    assert JUDGE.ERRORS == []


def test_the_judge_really_objects_when_the_hand_has_not_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """对照：同样的副本不跑写手，判官要红，否则上一条绿得没有意义。"""
    for rel in JUDGE.COUNT_DOCS:
        source = JUDGE.ROOT / rel
        if source.is_file():
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    monkeypatch.setattr(JUDGE, "ROOT", tmp_path)
    monkeypatch.setattr(JUDGE, "TOOL_DEFINITIONS", dict.fromkeys(range(len(JUDGE.TOOL_DEFINITIONS) + 4)))
    monkeypatch.setattr(JUDGE, "check_server_instructions", lambda: None)
    monkeypatch.setattr(JUDGE, "ERRORS", [])
    JUDGE.check_tool_counts()
    assert len(JUDGE.ERRORS) > 10
