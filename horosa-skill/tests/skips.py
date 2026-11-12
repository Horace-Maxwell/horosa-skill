"""Skip reasons carry a tag; the tag says whether a skip is legitimate where it happened.

Why (v0.50.0-dev, C-18 #2 / #10): a skipped test is indistinguishable from a passing one in a green run. The live-lane
gate (`scripts/verify_runtime_live.py`) used a *denylist* of five reason substrings, so a new way of not testing the
runtime — an in-body `pytest.skip("backend unavailable")`, a fallback `pytest.mark.skip("gate unavailable")` — passed
the lane silently. And about fifty tests that need the upstream checkout (`HOROSA_SOURCE_ROOT`) skipped in CI under a
dozen different spellings, so nobody could say what CI covers; one of them guessed a maintainer path instead of
skipping and failed outright on a machine where that guess was stale.

Now every skip reason starts with one of `TAGS` (`tests/conftest.py` turns an untagged skip into a failure, and prints
the skips per tag at the end of the run), and the live lane accepts only `LIVE_LANE_ALLOWED` — an allowlist
(`scripts/verify_runtime_live.py` keeps a copy; `tests/test_verify_runtime_live.py` holds the two in lockstep).
"""
from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path

import pytest

TAGS: dict[str, str] = {
    "upstream-checkout": "needs the upstream Horosa-Public checkout (HOROSA_SOURCE_ROOT) or the gitignored vendor/runtime-source",
    "platform": "only meaningful on another operating system",
    "host": "a capability this machine lacks (node on PATH, a CJK font, symlink privilege, IPv6, a free port …)",
    "opt-in": "an explicitly opted-in external dependency (Jev API key, veraPDF, an embedding model)",
    "version-skew": "the installed runtime payload predates this tree's export contract (not a regression)",
    "not-applicable": "a parametrized case that does not apply to this input",
    "no-runtime": "the live engine is not reachable / not explicitly named",
}
# A live lane exists to test the runtime: a skip for `no-runtime` (or an untagged one) means it did not.
LIVE_LANE_ALLOWED = frozenset(TAGS) - {"no-runtime"}

_TAG_RE = re.compile(r"^\[([a-z-]+)\] ")


def tag_of(reason: str) -> str | None:
    """The tag at the start of a skip reason, or None when it is untagged / unknown."""
    match = _TAG_RE.match(reason or "")
    return match.group(1) if match and match.group(1) in TAGS else None


def reason(tag: str, text: str) -> str:
    if tag not in TAGS:
        raise ValueError(f"unknown skip tag {tag!r}; known: {sorted(TAGS)}")
    return f"[{tag}] {text}"


# ---- the upstream checkout ----------------------------------------------------------------------------------------
# Unset means "not available" — never a guess at a maintainer path (test_sync311_mundane_election guessed
# ~/Desktop/Horosa-Public and failed on a machine whose copy there was another version).
_SOURCE_ENV = os.environ.get("HOROSA_SOURCE_ROOT") or ""
SOURCE_ROOT: Path | None = Path(_SOURCE_ENV) if _SOURCE_ENV and Path(_SOURCE_ENV).is_dir() else None
UPSTREAM_REASON = reason("upstream-checkout", "HOROSA_SOURCE_ROOT (Horosa-Public checkout) not set")


def upstream_path(relative: str) -> Path | None:
    """`<HOROSA_SOURCE_ROOT>/<relative>` when the checkout is configured, else None."""
    return SOURCE_ROOT / relative if SOURCE_ROOT is not None else None


def needs_upstream(*relatives: str, why: str = "") -> pytest.MarkDecorator:
    """skipif the checkout is not configured or lacks any of `relatives` (paths under the checkout root)."""
    missing = SOURCE_ROOT is None or any(not (SOURCE_ROOT / rel).exists() for rel in relatives)
    detail = f" ({why})" if why else (f" (needs {', '.join(relatives)})" if relatives and SOURCE_ROOT is not None else "")
    return pytest.mark.skipif(missing, reason=UPSTREAM_REASON + detail)


# ---- pytest hooks (re-exported by tests/conftest.py) ---------------------------------------------------------------
SKIPS_BY_TAG: Counter[str] = Counter()


def _skip_reason(report: pytest.TestReport) -> str:
    longrepr = report.longrepr
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        text = str(longrepr[2])
        return text[len("Skipped: "):] if text.startswith("Skipped: ") else text
    return str(longrepr or "")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> object:
    """An untagged skip becomes a failure; tagged ones are counted."""
    outcome = yield
    report = outcome.get_result()
    if not report.skipped or hasattr(report, "wasxfail"):
        return
    why = _skip_reason(report)
    tag = tag_of(why)
    if tag is None:
        report.outcome = "failed"
        report.longrepr = (
            f"untagged skip: {why!r}\nEvery skip reason starts with one of "
            f"{', '.join(f'[{t}]' for t in TAGS)} (tests/skips.py) — say why this is not tested here."
        )
        return
    SKIPS_BY_TAG[tag] += 1


def pytest_terminal_summary(terminalreporter: object, exitstatus: int, config: pytest.Config) -> None:
    if SKIPS_BY_TAG:
        counts = ", ".join(f"{tag} {n}" for tag, n in sorted(SKIPS_BY_TAG.items(), key=lambda kv: (-kv[1], kv[0])))
        terminalreporter.write_line(f"skipped by reason: {counts}")  # type: ignore[attr-defined]
