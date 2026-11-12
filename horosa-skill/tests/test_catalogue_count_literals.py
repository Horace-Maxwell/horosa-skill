"""MCP-14：源码与随包文档里写死的「工具数 / 门面数」必须等于注册表算出来的数。

工具目录每加一个技法，注释与说明里的「116 个工具」「11 个门面工具」就悄悄过期一次（审查时找到 payload.py「12 门面」、
clients_extra「11 facade」、locations「116 … 11」、config「11 个门面」）。生成的文字已经从
`TOOL_DEFINITIONS` / `FACADE_TOOL_COUNT` / `COMPACT_SURFACE_TOOL_COUNT` 派生；这条测试管的是剩下的**字面量**：
在描述目录本身的句式里出现的数字，必须是当前的真值之一。

不算数的（不会被这条测试读到）：
- 带版本号 / 日期的历史叙述（`v0.36.0 …只给 112 个`、`2026-10-22 … 110 个技法`）——那是当时的事实；
- 第三方客户端的上限（「128 个工具上限」）——带「上限」二字；
- 行尾写了 `count-literal-ok` 的（必须说明为什么）。
"""
from __future__ import annotations

import re
from pathlib import Path

from horosa_skill.engine.registry import COMPACT_SURFACE_TOOL_COUNT, FACADE_TOOL_COUNT, TOOL_DEFINITIONS

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "horosa_skill"
REPO = Path(__file__).resolve().parents[2]

_FACADE = re.compile(r"(?<![\d.])(\d{1,3})\s*(?:个)?\s*(?:门面(?:级)?(?:工具)?|facade tools?|facades)", re.IGNORECASE)
_TOTAL = re.compile(r"(?<![\d.v])(1[0-4]\d)\s*(?:个)?\s*(?:工具|技法|tools|techniques)(?![A-Za-z])", re.IGNORECASE)
_HISTORICAL = re.compile(r"v\d+\.\d+|\d{4}-\d{2}-\d{2}|曾|此前|当时|at the time|上限|limit|count-literal-ok", re.IGNORECASE)


def _sources() -> list[Path]:
    files = sorted(PACKAGE.rglob("*.py")) + sorted((PACKAGE / "agent_skill").rglob("*.md"))
    files += sorted((REPO / "skills" / "horosa-agent").rglob("*.md")) if (REPO / "skills" / "horosa-agent").is_dir() else []
    return files


def _stale(text: str, pattern: re.Pattern[str], allowed: set[int]) -> list[str]:
    found = []
    for match in pattern.finditer(text):
        end = text.find("\n", match.end())
        number, line = match.group(1), text[text.rfind("\n", 0, match.start()) + 1:end if end != -1 else len(text)]
        if int(number) not in allowed and not _HISTORICAL.search(line):
            found.append(f"{number}: {line.strip()[:140]}")
    return found


def test_catalogue_counts_written_as_literals_are_current() -> None:
    techniques = len(TOOL_DEFINITIONS)
    facade_ok = {FACADE_TOOL_COUNT, COMPACT_SURFACE_TOOL_COUNT}
    total_ok = {techniques, FACADE_TOOL_COUNT + techniques}
    problems: dict[str, list[str]] = {}
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        stale = _stale(text, _FACADE, facade_ok) + _stale(text, _TOTAL, total_ok)
        if stale:
            problems[path.relative_to(REPO).as_posix()] = stale
    assert problems == {}, (
        f"写死的目录数过期了（当前：{techniques} 技法、{FACADE_TOOL_COUNT} 门面、全量 {FACADE_TOOL_COUNT + techniques}、"
        f"精简 {COMPACT_SURFACE_TOOL_COUNT}）——改成从注册表派生，或把句子改成不带数字"
    )


def test_the_detector_catches_a_stale_literal() -> None:
    """负向对照：这条守卫自己得能红。"""
    assert _stale("# 116 个工具的定义每轮都进上下文", _TOTAL, {len(TOOL_DEFINITIONS)})
    assert _stale("- compact surface everywhere (11 facade tools; …)", _FACADE, {FACADE_TOOL_COUNT})
    assert not _stale("# v0.36.0：`all` 只给 112 个而非 116", _TOTAL, {len(TOOL_DEFINITIONS)})
    assert not _stale("VS Code Copilot 跨所有 server 共 128 个工具上限", _TOTAL, {len(TOOL_DEFINITIONS)})
