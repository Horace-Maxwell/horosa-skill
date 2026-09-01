"""Shared parser for upstream `aiExport.js` — used by the sync + section-baseline guards.

The upstream literal is plain JS with a stable shape (`key: ['段名', …],` + one `...SPREAD`), but three
traps make naive parsing wrong:

1. `//` comments quote section names (e.g. ``// [MU] '古典':buildIndiaSnapshotText 实测不产出``) —
   extracting strings before stripping comments invents sections that do not exist.
2. `AI_EXPORT_PRESET_SECTIONS` spreads `...JIEQI_SETTING_PRESETS`, whose entries are declared in a
   separate literal; ignoring the spread silently loses those keys.
3. Entries may live **outside** the object literal as post-literal member assignments —
   ``AI_EXPORT_PRESET_SECTIONS.qimenzeri = [...AI_EXPORT_PRESET_SECTIONS.qimen, '择日搜索配置', …];``
   (aiExport.js:735). Brace-matching the literal alone silently drops the whole key: `qimenzeri`'s
   20 sections were invisible to the section-debt ratchet until v0.26.0. The member pass must run
   **after** the literal + spread pass, because its `...` references resolve against already-parsed
   keys, and tokens must be walked in source order so spread-expanded and literal sections interleave
   the way upstream wrote them.
"""

from __future__ import annotations

import re
from pathlib import Path

_LINE_COMMENT = re.compile(r"//[^\n]*")
_ENTRY = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\[([^\]]*)\]", re.DOTALL)
_STRING = re.compile(r"'([^']*)'|\"([^\"]*)\"")
_SPREAD = re.compile(r"\.\.\.\(?\s*([A-Za-z_][A-Za-z0-9_]*)")
_VERSION = re.compile(r"AI_EXPORT_SETTINGS_VERSION\s*=\s*(\d+)")

# trap 3: `AI_EXPORT_PRESET_SECTIONS.key = [...]` / `AI_EXPORT_PRESET_SECTIONS['key'] = [...]`
# The array body must be matched lazily up to `];` rather than with `[^\]]*`: a bracket-form spread
# (`...AI_EXPORT_PRESET_SECTIONS['qimen']`) puts a `]` inside the body and would truncate it.
_MEMBER_ASSIGN = re.compile(
    r"^AI_EXPORT_PRESET_SECTIONS(?:\.([A-Za-z_][A-Za-z0-9_]*)|\[\s*['\"]([^'\"]+)['\"]\s*\])\s*=\s*\[(.*?)\]\s*;",
    re.M | re.DOTALL,
)
# tokens inside such an array, walked in source order: a spread of another preset key, or a literal.
# 🔴 spread 有**两种写法**，上游同一个文件里两种都在用：
#   `...AI_EXPORT_PRESET_SECTIONS.qimen`              （v3.7.1 的 qimenzeri）
#   `...(AI_EXPORT_PRESET_SECTIONS.bazi || [])`       （v3.10.0 的择日八技法，带括号与 || 兜底）
# 只认第一种时，第二种会被整个跳过 —— 解析结果只剩 3 个字面量段，于是基底那十几段全被
# export-section 守卫报成「skill 多出来的段」。假债务比漏检更坏：它会诱使人去 --update-baseline，
# 把一条本该常绿的检查腌成永久噪声。
_MEMBER_TOKEN = re.compile(
    r"\.\.\.\(?\s*AI_EXPORT_PRESET_SECTIONS(?:\.([A-Za-z_][A-Za-z0-9_]*)|\[\s*['\"]([^'\"]+)['\"]\s*\])"
    r"|'([^']*)'"
    r"|\"([^\"]*)\""
)


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


def _apply_member_assignments(text: str, presets: dict[str, list[str]]) -> None:
    """Fold post-literal `AI_EXPORT_PRESET_SECTIONS.<key> = [...]` entries in (trap 3), in place."""
    for dot_key, bracket_key, array_body in _MEMBER_ASSIGN.findall(_LINE_COMMENT.sub("", text)):
        key = dot_key or bracket_key
        sections: list[str] = []
        for spread_dot, spread_bracket, single, double in _MEMBER_TOKEN.findall(array_body):
            ref = spread_dot or spread_bracket
            if ref:
                if ref not in presets:
                    raise SystemExit(
                        f"AI_EXPORT_PRESET_SECTIONS.{key} spreads ...AI_EXPORT_PRESET_SECTIONS.{ref}, "
                        f"but {ref} was not parsed — upstream changed shape; update _upstream_preset.py"
                    )
                sections.extend(presets[ref])
            else:
                sections.append(single or double)
        presets[key] = sections


def parse_preset_sections(text: str) -> dict[str, list[str]]:
    """Parse `AI_EXPORT_PRESET_SECTIONS`, resolving `...SPREAD` refs (trap 2) and post-literal
    member assignments (trap 3)."""
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
    # must run last: member-assignment spreads resolve against the keys parsed above.
    _apply_member_assignments(text, presets)
    if not presets:
        raise SystemExit("parsed AI_EXPORT_PRESET_SECTIONS but found zero keys — parser or source changed shape")
    return presets


def load_upstream_aiexport(path: Path) -> tuple[int, dict[str, list[str]]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return read_settings_version(text), parse_preset_sections(text)
