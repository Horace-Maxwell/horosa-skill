"""上游 v3.14.0 导出契约里归星运族的两处：新键 timelords，以及「星曜后天信息」开关表的拆分。

上游 aiExport/presets.js（v65）把 AI_EXPORT_PLANET_INFO_TECHNIQUES 里正文不带后天括注（落宫 / 主宰宫）的十五个键挪进新表
AI_EXPORT_MEANING_ONLY_TECHNIQUES（发布说明：「星曜后天信息」两项开关只列给正文里真带这种括注的技法，十六个技法此前勾了没有变化）。
十五个里十四个是星运键（zodialrelease / decennials / planetaryages / persiandirected / yearsystem129 / balbillus / triplicityrulers /
keypoints / lunationphase / extrareturns / neroman / bezzafigure / jayprofection / michon），加七政 guolao；新键 timelords 直接进新表。

权威 = 上游 checkout 的 presets.js（HOROSA_SOURCE_ROOT；CI 按契约提交号浅取公开上游并设它，没设就 [upstream-checkout] 跳过——
vendor/runtime-source 是 gitignored 的本机重灌树，CI 上没有，v0.51 PR 在这里红过）。只比 skill 已有的导出键：
别的批还没接进来的上游新键（变换盘 transformchart …）不在本文件裁决。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from horosa_skill.exports import registry as R
from horosa_skill.exports.parser import parse_export_content

_UPSTREAM_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
PRESETS = (Path(_UPSTREAM_ROOT) / "Horosa-Web" / "astrostudyui" / "src" / "utils" / "aiExport" / "presets.js") if _UPSTREAM_ROOT else None
pytestmark = pytest.mark.skipif(
    PRESETS is None or not PRESETS.is_file(), reason="[upstream-checkout] HOROSA_SOURCE_ROOT (upstream checkout) not set"
)
# 上游导出键 → skill 导出键（占星地图：上游 locastro，skill acg）。
KEY_MAP = {"locastro": "acg"}
MOVED = ["zodialrelease", "decennials", "planetaryages", "persiandirected", "yearsystem129", "balbillus", "triplicityrulers", "keypoints",
         "lunationphase", "extrareturns", "neroman", "bezzafigure", "jayprofection", "michon", "guolao"]


def _upstream_list(name: str, opener: str) -> list[str]:
    assert PRESETS is not None
    text = PRESETS.read_text(encoding="utf-8")
    start = text.index(f"export const {name} = {opener}")
    body = text[start: text.index("]", start)]
    body = re.sub(r"//[^\n]*", "", body)   # 注释里引了键名（'hellenastro' …），先去注释
    return [KEY_MAP.get(key, key) for key in re.findall(r"'([A-Za-z0-9_]+)'", body)]


def _known() -> set[str]:
    return {item["key"] for item in R.AI_EXPORT_TECHNIQUES} | set(R.AI_EXPORT_PRESET_SECTIONS)


def test_planet_info_and_meaning_only_tables_mirror_upstream() -> None:
    """两张表逐键 == 上游（限 skill 已有的导出键）。负向对照（实跑）：把 michon 放回 AI_EXPORT_PLANET_INFO_TECHNIQUES → 红；
    AI_EXPORT_MEANING_ONLY_TECHNIQUES 去掉 timelords → 红。"""
    planet = _upstream_list("AI_EXPORT_PLANET_INFO_TECHNIQUES", "new Set([")
    meaning = _upstream_list("AI_EXPORT_MEANING_ONLY_TECHNIQUES", "[")
    known = _known()
    assert len(planet) > 25 and len(meaning) == 16, (len(planet), len(meaning))
    assert R.AI_EXPORT_PLANET_INFO_TECHNIQUES == {key for key in planet if key in known}
    assert R.AI_EXPORT_MEANING_ONLY_TECHNIQUES == [key for key in meaning if key in known]
    assert not set(R.AI_EXPORT_PLANET_INFO_TECHNIQUES) & set(R.AI_EXPORT_MEANING_ONLY_TECHNIQUES)
    assert R.AI_EXPORT_ASTRO_MEANING_TECHNIQUES == {*R.AI_EXPORT_PLANET_INFO_TECHNIQUES, *R.AI_EXPORT_MEANING_ONLY_TECHNIQUES, "otherbu", "qimen", "liureng"}
    assert meaning == [*MOVED[:14], "timelords", "guolao"]


def test_timelords_export_key_mirrors_upstream() -> None:
    text = PRESETS.read_text(encoding="utf-8")
    assert "\ttimelords: ['起盘信息', '时主轮转', '当前时段', '后续', '当前时点', '方法说明']," in text
    assert "{ key: 'timelords', label: '星运-时主轮转' }" in text
    assert R.AI_EXPORT_PRESET_SECTIONS["timelords"] == ["起盘信息", "时主轮转", "当前时段", "后续", "当前时点", "方法说明"]
    assert {"key": "timelords", "label": "星运-时主轮转"} in R.AI_EXPORT_TECHNIQUES
    migration = text[text.index("export const AI_EXPORT_SECTION_MIGRATION_KEYS"):]
    assert "'timelords'" in migration[: migration.index("];")] and "timelords" in R.AI_EXPORT_SECTION_MIGRATION_KEYS


@pytest.mark.parametrize("key", [*MOVED, "timelords"])
def test_moved_keys_keep_the_meaning_switch_and_drop_the_planet_info_switch(key: str) -> None:
    """挪走的键：仍可加释义（supports_astro_meaning），不再列「星曜后天信息」两项开关；给了 planet_info 也不改正文——
    这些技法的正文里没有后天括注，旧表下这个开关勾了也没有变化，却会把恰好长成 (10th; 5R) 的普通括号当后天信息裁掉。"""
    info = R.get_technique_info(key)
    assert info is not None, key
    assert info["supports_planet_info"] is False and info["planet_info_default"] is None
    assert info["supports_astro_meaning"] is True and info["astro_meaning_default"] == R.AI_EXPORT_ASTRO_MEANING_DEFAULT
    title = info["preset_sections"][0]
    content = f"[{title}]\n日 (10th; 5R) 合 水 (10th; 3R6R)"
    parsed = parse_export_content(technique=key, content=content, selected_sections=[title], planet_info={"showHouse": 0, "showRuler": 0})
    assert parsed["sections"][0]["content"].split("\n", 1)[1] == "日 (10th; 5R) 合 水 (10th; 3R6R)"
    assert parsed["settings_used"]["planetInfo"] == {} and key in parsed["settings_used"]["astroMeaning"]


def test_planet_info_techniques_still_trim() -> None:
    for key in ("astrochart", "solarreturn", "primarydirect", "prog"):
        title = R.get_technique_info(key)["preset_sections"][0]
        parsed = parse_export_content(technique=key, content=f"[{title}]\n日 (10th; 5R)", selected_sections=[title], planet_info={"showHouse": 1, "showRuler": 0})
        assert parsed["sections"][0]["content"].split("\n", 1)[1] == "日 (10th)", key
