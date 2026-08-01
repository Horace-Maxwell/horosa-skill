"""Shared parser for upstream `aiExport.js` — used by the sync + section-baseline guards.

The upstream literal is plain JS with a stable shape (`key: ['段名', …],` + one `...SPREAD`), but two
traps make naive parsing wrong:

1. `//` comments quote section names (e.g. ``// [MU] '古典':buildIndiaSnapshotText 实测不产出``) —
   extracting strings before stripping comments invents sections that do not exist.
2. `AI_EXPORT_PRESET_SECTIONS` spreads `...JIEQI_SETTING_PRESETS`, whose entries are declared in a
   separate literal; ignoring the spread silently loses those keys.
"""

from __future__ import annotations

import re
from pathlib import Path

_LINE_COMMENT = re.compile(r"//[^\n]*")
_ENTRY = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\[([^\]]*)\]", re.DOTALL)
_STRING = re.compile(r"'([^']*)'|\"([^\"]*)\"")
_SPREAD = re.compile(r"\.\.\.([A-Za-z_][A-Za-z0-9_]*)")
_VERSION = re.compile(r"AI_EXPORT_SETTINGS_VERSION\s*=\s*(\d+)")


def read_settings_version(text: str) -> int:
    match = _VERSION.search(text)
    if not match:
        raise SystemExit("could not read AI_EXPORT_SETTINGS_VERSION from aiExport.js")
    return int(match.group(1))


def _object_block(text: str, name: str) -> str | None:
    """Return the `{...}` body of `const <name> = { … }` via brace matching."""
    anchor = re.search(rf"{name}\s*=\s*\{{", text)
    if not anchor:
        return None
    start = anchor.end()
    depth = 1
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index]
    return None


def _parse_map(body: str) -> dict[str, list[str]]:
    body = _LINE_COMMENT.sub("", body)  # trap 1: comments quote section names
    result: dict[str, list[str]] = {}
    for key, array_body in _ENTRY.findall(body):
        sections = [a or b for a, b in _STRING.findall(array_body)]
        result[key] = sections
    return result


def parse_preset_sections(text: str) -> dict[str, list[str]]:
    """Parse `AI_EXPORT_PRESET_SECTIONS`, resolving `...SPREAD` references (trap 2)."""
    body = _object_block(text, "AI_EXPORT_PRESET_SECTIONS")
    if body is None:
        raise SystemExit("could not locate AI_EXPORT_PRESET_SECTIONS in aiExport.js")
    presets = _parse_map(body)
    for spread_name in _SPREAD.findall(_LINE_COMMENT.sub("", body)):
        spread_body = _object_block(text, spread_name)
        if spread_body is None:
            raise SystemExit(
                f"AI_EXPORT_PRESET_SECTIONS spreads ...{spread_name} but that literal was not found — "
                "upstream changed shape; update _upstream_preset.py"
            )
        presets.update(_parse_map(spread_body))
    if not presets:
        raise SystemExit("parsed AI_EXPORT_PRESET_SECTIONS but found zero keys — parser or source changed shape")
    return presets


def load_upstream_aiexport(path: Path) -> tuple[int, dict[str, list[str]]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return read_settings_version(text), parse_preset_sections(text)
