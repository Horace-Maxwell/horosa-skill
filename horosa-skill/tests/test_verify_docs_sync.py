"""Unit tests for the docs-sync tool-count checks (scripts/verify_docs_sync.py).

Why these exist: before v0.26.0 the count assertion was a single regex, `badge/tools-(\\d+)-`. The
English README happened to phrase things that way and was guarded; the Chinese README used
`badge/技法-83-` and drifted to 83 while the registry held 89 — with `alt="89 tools"` sitting on the
very same line. Six more stale claims hid in prose, in manifest.json, in banner.svg, and — worst —
twice in `_SERVER_INSTRUCTIONS`, the blurb shipped to every MCP client, which no guard read at all.

The bug was never the number. It was that the guard's reach was decided by an accident of phrasing.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PKG / "src"))
_SCRIPT = _PKG / "scripts" / "verify_docs_sync.py"
_spec = importlib.util.spec_from_file_location("verify_docs_sync", _SCRIPT)
docs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(docs)

from horosa_skill.engine.registry import TOOL_DEFINITIONS  # noqa: E402

N = len(TOOL_DEFINITIONS)


def _scan(line: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str = "README.md") -> list[str]:
    """Run check_tool_counts over a one-line doc and return the errors it raised."""
    (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / name).write_text(line + "\n", encoding="utf-8")
    errors: list[str] = []
    monkeypatch.setattr(docs, "ROOT", tmp_path)
    monkeypatch.setattr(docs, "COUNT_DOCS", [name])
    monkeypatch.setattr(docs, "err", errors.append)
    monkeypatch.setattr(docs, "check_server_instructions", lambda: None)
    docs.check_tool_counts()
    return errors


# --- the literal escape case ---------------------------------------------------------------------


def test_chinese_badge_label_is_checked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = f'<img src="https://img.shields.io/badge/技法-{N - 6}-1d4ed8?style=for-the-badge" />'
    assert _scan(bad, tmp_path, monkeypatch), "the 技法 badge label must be guarded, not just `tools`"
    good = f'<img src="https://img.shields.io/badge/技法-{N}-1d4ed8?style=for-the-badge" />'
    assert _scan(good, tmp_path, monkeypatch) == []


def test_badge_contradicting_its_own_alt_on_one_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """This exact shape shipped in v0.25.0: badge 83, alt 89, same line."""
    line = f'<img src="https://img.shields.io/badge/技法-{N - 6}-x" alt="{N} tools" />'
    errors = _scan(line, tmp_path, monkeypatch)
    assert any("contradicts alt" in e for e in errors)


# --- forms that escaped the old regex ------------------------------------------------------------


@pytest.mark.parametrize(
    "template",
    [
        "| 🌌 **{n} 技法一次装齐** |",
        "本地进程 · {n} 工具 · 澄清闸",
        "Local-first Horosa: {n} real technique tools over MCP",
        "exposes {n} real 术数/占星 techniques —",
        "本仓把星阙（Horosa）的 {n} 个术数/占星技法打包成",
        "<strong>{n}</strong> real techniques on your own machine",
        "| 🧰 可调用工具 | {n} / {n} `ok=true` |",
        "| Local memory | `{n} / {n}` writes |",
    ],
)
def test_stale_count_forms_are_caught(template: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _scan(template.format(n=N - 6), tmp_path, monkeypatch), f"stale count not caught in: {template}"
    assert _scan(template.format(n=N), tmp_path, monkeypatch) == [], f"false positive on correct count: {template}"


# --- precision: things that must NOT be flagged ---------------------------------------------------


def test_small_unrelated_counts_are_not_flagged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`约 9 个门面工具` is a real, different quantity — a looser regex would false-positive here."""
    line = "上下文预算受限的客户端可设 HOROSA_MCP_COMPACT=1，只暴露约 9 个门面工具，澄清闸照常生效。"
    assert _scan(line, tmp_path, monkeypatch) == []


def test_gated_tool_count_is_checked_against_its_own_quantity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`N 个技法工具触发 must_ask_user` is registry-minus-exempt, not the total — and drifted to 67."""
    gated = docs.expected_gated()
    assert gated != N, "this test is meaningless if every tool is gated"
    assert _scan(f"| {gated - 14} 个技法工具触发 `must_ask_user=true` |", tmp_path, monkeypatch)
    assert _scan(f"| {gated} 个技法工具触发 `must_ask_user=true` |", tmp_path, monkeypatch) == []
    assert _scan(f"| {N} 个技法工具触发 `must_ask_user=true` |", tmp_path, monkeypatch), (
        "the gated row must not silently accept the *total* tool count"
    )


def test_ignore_marker_exempts_a_frozen_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    line = f"| 🧰 可调用工具 | {N - 6} / {N - 6} `ok=true` | {docs.IGNORE_COUNT}"
    assert _scan(line, tmp_path, monkeypatch) == []


# --- the blurb that ships to every MCP client -----------------------------------------------------


def test_server_instructions_count_is_guarded() -> None:
    """No guard read _SERVER_INSTRUCTIONS before v0.26.0; it said 83 twice while the registry had 89."""
    errors: list[str] = []
    original = docs.err
    docs.err = errors.append
    try:
        docs.check_server_instructions()
    finally:
        docs.err = original
    assert errors == [], f"_SERVER_INSTRUCTIONS is out of sync with the registry: {errors}"


def test_server_instructions_check_actually_fires(monkeypatch: pytest.MonkeyPatch) -> None:
    import horosa_skill.surfaces.mcp_server as mcp

    monkeypatch.setattr(mcp, "_SERVER_INSTRUCTIONS", f"WHAT IT COVERS ({N - 6} tools)\ninstead of {N - 6}\n")
    errors: list[str] = []
    monkeypatch.setattr(docs, "err", errors.append)
    docs.check_server_instructions()
    assert len(errors) == 2, "both the '(N tools)' and 'instead of N' forms must be checked"
