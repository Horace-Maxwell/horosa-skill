"""Every version site `bump_version.py` rewrites is named in AGENTS.md's bump rule (v0.41.1).

The rule used to carry a count ("16 个站点") while `SITES` had grown to 19 — the three v0.41.0 additions (root
`plugin.json` / `mcp.json`, the wheel's generated SKILL copy) were missing from the list. The rule now names sites
instead of counting them, and this test fails the moment a site is added to `SITES` without being named there.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent
_spec = importlib.util.spec_from_file_location("bump_version", PKG_ROOT / "scripts" / "bump_version.py")
bump_version = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bump_version)


def _bump_rule() -> str:
    text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    start = text.index("**版本 bump 只有一个入口**")
    return text[start:text.index("\n- **", start + 1)]


def undocumented_sites(sites: tuple[str, ...], rule: str) -> list[str]:
    missing = []
    for site in sites:
        parts = site.split("/")
        candidates = {site, site.removeprefix("horosa-skill/"), "/".join(parts[-3:]), "/".join(parts[-2:]), parts[-1]}
        if not any(f"`{c}`" in rule or f"{c}`" in rule for c in candidates):
            missing.append(site)
    return missing


def test_every_bump_site_is_named_in_the_agents_rule() -> None:
    assert undocumented_sites(bump_version.SITES, _bump_rule()) == []


def test_the_check_notices_a_new_site_nobody_documented() -> None:
    assert undocumented_sites((*bump_version.SITES, "docs/NEW_PINNED_PAGE.md"), _bump_rule()) == ["docs/NEW_PINNED_PAGE.md"]


def test_the_rule_does_not_state_a_site_count() -> None:
    import re

    assert not re.search(r"\d+\s*个站点", _bump_rule()), "name the sites; a count goes stale (it said 16 while SITES had 19)"


def test_history_sentence_with_from_v_is_not_rewritten() -> None:
    """README_EN「from v0.41.0 every release is listed automatically」是历史起点：此前每次 bump 都被改成当前版本
    （0.45.1 → 0.46.0 → 0.46.1，v0.46.1 合并时发现）。负向对照：从 HISTORY_MARKERS 去掉 "from v" → 红。"""
    line = "listing each release's `.mcpb` only; from v0.46.1 every release is listed automatically once it goes public |"
    assert bump_version._is_history(line, "0.46.1")
    readme = (PKG_ROOT.parent / "README_EN.md").read_text(encoding="utf-8")
    assert "from v0.41.0 every release is listed automatically" in readme
