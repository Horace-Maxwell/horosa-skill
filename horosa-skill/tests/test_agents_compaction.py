"""AGENTS.md's own compaction rule, enforced (v0.41.1): no heading-delimited chunk runs past ~120 lines.

The rule ("任何 `##` 章节超过 ~120 行必须按主题分 `###` 子标题") lived only in prose; §4 had grown to 208 lines, §5 to
167, §8 to 148 and §7 to 134 with no subheadings. Each `##` / `###` chunk is now measured.
"""
from __future__ import annotations

import re
from pathlib import Path

AGENTS = Path(__file__).resolve().parents[2] / "AGENTS.md"
LIMIT = 120


def oversized_chunks(text: str, limit: int = LIMIT) -> list[str]:
    lines = text.split("\n")
    starts = [i for i, line in enumerate(lines) if re.match(r"^#{2,3} ", line)]
    out = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        if end - start > limit:
            out.append(f"{lines[start]} ({end - start} lines)")
    return out


def test_every_agents_section_stays_under_the_compaction_limit() -> None:
    assert oversized_chunks(AGENTS.read_text(encoding="utf-8")) == []


def test_the_check_catches_an_unsplit_long_section() -> None:
    text = "## 1. short\n" + "x\n" * 10 + "## 2. long\n" + "x\n" * 130 + "### 2.1 fine\n" + "x\n" * 5
    assert oversized_chunks(text) == ["## 2. long (131 lines)"]
