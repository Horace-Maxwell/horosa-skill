"""Unit tests for the upstream aiExport parser (scripts/_upstream_preset.py).

This parser is the ONLY thing that enumerates upstream section tables, so every guard that answers
"还有什么没同步" (verify_export_section_baseline, verify_upstream_sync) inherits its blind spots.
Its docstring records three traps; each one is pinned here so a future refactor cannot silently
reopen them:

1. `//` comments quote section names → stripping must precede string extraction.
2. `...JIEQI_SETTING_PRESETS` spreads a separate literal → those keys must resolve.
3. post-literal `AI_EXPORT_PRESET_SECTIONS.<key> = [...]` assignments live OUTSIDE the brace-matched
   literal. Trap 3 cost 20 invisible `qimenzeri` sections between upstream v3.7.1 and skill v0.26.0
   — the section-debt ratchet reported "0 absent keys" while a whole technique was missing.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "_upstream_preset.py"
_spec = importlib.util.spec_from_file_location("_upstream_preset", _SCRIPT)
up = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(up)

_VENDORED_AIEXPORT = (
    Path(__file__).resolve().parents[2]
    / "vendor/runtime-source/Horosa-Web/astrostudyui/src/utils/aiExport.js"
)


def _js(literal_body: str, tail: str = "") -> str:
    return f"const AI_EXPORT_SETTINGS_VERSION = 50;\nconst AI_EXPORT_PRESET_SECTIONS = {{\n{literal_body}\n}};\n{tail}"


# --- trap 3: post-literal member assignments -------------------------------------------------


def test_member_assignment_after_literal_is_parsed() -> None:
    text = _js(
        "\tbar: ['a', 'b'],",
        "AI_EXPORT_PRESET_SECTIONS.foo = [...AI_EXPORT_PRESET_SECTIONS.bar, 'x', 'y'];",
    )
    presets = up.parse_preset_sections(text)
    assert presets["foo"] == ["a", "b", "x", "y"], "spread must expand in source order, before the literals"


def test_member_assignment_bracket_form_is_parsed() -> None:
    text = _js("\tbar: ['a'],", "AI_EXPORT_PRESET_SECTIONS['foo'] = ['x', ...AI_EXPORT_PRESET_SECTIONS['bar']];")
    presets = up.parse_preset_sections(text)
    assert presets["foo"] == ["x", "a"], "literal-then-spread order must be preserved too"


def test_member_assignment_with_unresolvable_spread_raises() -> None:
    text = _js("\tbar: ['a'],", "AI_EXPORT_PRESET_SECTIONS.foo = [...AI_EXPORT_PRESET_SECTIONS.nope, 'x'];")
    with pytest.raises(SystemExit, match="nope"):
        up.parse_preset_sections(text)


def test_member_assignment_in_a_comment_is_ignored() -> None:
    text = _js("\tbar: ['a'],", "// AI_EXPORT_PRESET_SECTIONS.ghost = ['不存在的段'];")
    assert "ghost" not in up.parse_preset_sections(text)


@pytest.mark.skipif(not _VENDORED_AIEXPORT.exists(), reason="vendored runtime-source not present")
def test_qimenzeri_seen_with_qimen_plus_three_sections() -> None:
    """The real regression: upstream declares qimenzeri outside the literal (aiExport.js:735).

    Runs against the VENDORED copy so it gates in GitHub CI, which has no upstream checkout.
    """
    presets = up.parse_preset_sections(_VENDORED_AIEXPORT.read_text(encoding="utf-8", errors="replace"))
    assert "qimenzeri" in presets, "post-literal AI_EXPORT_PRESET_SECTIONS.qimenzeri must be visible to the ratchet"
    assert presets["qimenzeri"] == [*presets["qimen"], "择日搜索配置", "择日条件", "命中时辰"]


# --- traps 1 and 2: pinned so the new pass cannot regress them ---------------------------------


def test_comment_quoted_section_names_are_not_invented() -> None:
    text = _js("\t// [MU] '古典':buildIndiaSnapshotText 实测不产出\n\tbar: ['a'],")
    assert up.parse_preset_sections(text)["bar"] == ["a"]
    assert "古典" not in up.parse_preset_sections(text).get("bar", [])


def test_spread_of_a_separate_literal_resolves() -> None:
    text = (
        "const AI_EXPORT_SETTINGS_VERSION = 50;\n"
        "const JIEQI_SETTING_PRESETS = {\n\tjieqi_chunfen: ['春分星盘', '春分宿盘'],\n};\n"
        "const AI_EXPORT_PRESET_SECTIONS = {\n\t...JIEQI_SETTING_PRESETS,\n\tbar: ['a'],\n};\n"
    )
    presets = up.parse_preset_sections(text)
    assert presets["jieqi_chunfen"] == ["春分星盘", "春分宿盘"]


def test_missing_literal_raises() -> None:
    with pytest.raises(SystemExit, match="could not locate"):
        up.parse_preset_sections("const AI_EXPORT_SETTINGS_VERSION = 50;\n")


def test_read_settings_version() -> None:
    assert up.read_settings_version("export const AI_EXPORT_SETTINGS_VERSION = 50;") == 50
    with pytest.raises(SystemExit):
        up.read_settings_version("nothing here")
