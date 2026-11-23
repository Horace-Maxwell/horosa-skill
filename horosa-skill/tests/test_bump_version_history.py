"""bump_version.py leaves "since which version" history alone, occurrence by occurrence (v0.52.0).

Why: the line-level check only recognised history written with a `v` ("Since v0.39.0", "自 v…"). "自 0.50.0 起", "since 0.50.0",
"(v0.41.0;", "before v0.41.0", "0.50.0 之前的发布", "a pre-0.50.0 manifest" were rewritten on every bump — by the v0.52.0 bump,
fourteen README / restricted-network notes said a feature shipped "since 0.52.0" (really 0.50.0 / 0.41.0).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent
_spec = importlib.util.spec_from_file_location("bump_version", PKG_ROOT / "scripts" / "bump_version.py")
bump_version = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bump_version)

HISTORY = [
    "> `horosa-skill install` 自 0.50.0 起改装**平台无关的 JS 引擎资产**",
    "| Linux | ⚠️ 无载荷（实验）；JS 引擎可装（自 0.50.0） | `install` …",
    "闸门怎么判（v0.50.0）：",
    "**Over MCP the default is the reading view** (since v0.50.0): the text",
    "installs the **platform-independent JS engine asset** (from 0.50.0) instead",
    "| `runtime.install_missing_platform` | 也没有 JS 引擎资产（0.50.0 之前的发布） | 换 0.50.0 及以后的清单",
    "`runtime.install_missing_platform` (a pre-0.50.0 manifest without the JS engine asset — from 0.50.0 on",
    "yourself with `--sha256` (since v0.50.0; before that the check was silently skipped).",
    "before v0.50.0 only agents that opened this repo saw it.",
]
CURRENT = [
    ('WHL="https://github.com/Horace-Maxwell/horosa-skill/releases/download/v0.50.0/horosa_skill-0.50.0-py3-none-any.whl"',
     'WHL="https://github.com/Horace-Maxwell/horosa-skill/releases/download/v9.9.9/horosa_skill-9.9.9-py3-none-any.whl"'),
    ('  "version": "0.50.0",', '  "version": "9.9.9",'),
    ("**Current version: `Horosa Skill 0.50.0` (119 callable tools", "**Current version: `Horosa Skill 9.9.9` (119 callable tools"),
    ("随每个 release 打包并校验（本仓版本 `v0.50.0`；公开 latest", "随每个 release 打包并校验（本仓版本 `v9.9.9`；公开 latest"),
    ("`uvx --from ./horosa_skill-0.50.0-py3-none-any.whl horosa-skill`", "`uvx --from ./horosa_skill-9.9.9-py3-none-any.whl horosa-skill`"),
]


def _rewrite(line: str) -> str:
    return bump_version.rewrite(line, Path("README.md"), "0.50.0", "9.9.9")[0]


def test_history_occurrences_survive_a_bump() -> None:
    assert [_rewrite(line) for line in HISTORY] == HISTORY


def test_current_version_sites_are_still_rewritten() -> None:
    assert [_rewrite(before) for before, _ in CURRENT] == [after for _, after in CURRENT]


def test_a_line_with_both_keeps_the_history_and_moves_the_pin() -> None:
    line = "（本仓版本 `v0.50.0`）…只装 JS 引擎资产（自 0.50.0，本地 JS 技法可用）"
    assert _rewrite(line) == "（本仓版本 `v9.9.9`）…只装 JS 引擎资产（自 0.50.0，本地 JS 技法可用）"


def test_the_old_whole_line_replace_is_what_corrupted_them() -> None:
    """Negative control: the pre-v0.52.0 rule (whole-line replace unless a v-prefixed marker) rewrites most of these."""
    old_rule = [line.replace("0.50.0", "9.9.9") if not bump_version._is_history(line, "0.50.0") else line for line in HISTORY]
    assert sum(a != b for a, b in zip(old_rule, HISTORY, strict=True)) >= 6


def test_the_next_bump_would_not_touch_any_history_in_the_real_sites() -> None:
    """Every 0.50.0 / 0.41.0 mention left in the bump sites is history — a 0.50.0 → 9.9.9 'bump' must change nothing."""
    for rel in bump_version.SITES:
        path = REPO_ROOT / rel
        if path.name in ("uv.lock", "package-lock.json", "pyproject.toml", "__init__.py"):
            continue
        text = path.read_text(encoding="utf-8")
        for old in ("0.50.0", "0.41.0"):
            assert bump_version.rewrite(text, path, old, "9.9.9")[1] == 0, (rel, old)
