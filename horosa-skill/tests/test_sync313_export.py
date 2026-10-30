"""导出契约 v16（上游 aiExport v58 → v60，星阙 v3.13.0）：段表、条件段、旧段名迁移。

上游源：utils/aiExport/presets.js（v59 germany [赤纬接触] 自 [汉堡学派要素] 拆出；v60 [中点坐标]/[公式求解]）、
utils/aiExport/sectionFilter.js:51 LEGACY_CONTENT_SECTION_TITLES（两处内容段改名）与 :83-101（profection 族
[星盘信息]、jaynesprog 首段名两条早年迁移——skill 此前一直漏登）。
"""

from __future__ import annotations

import pytest

from horosa_skill.exports import registry as r


def test_versions_track_upstream_v60() -> None:
    assert r.MIRRORED_UPSTREAM_AIEXPORT_VERSION == 60
    assert r.AI_EXPORT_SETTINGS_VERSION == r.AI_EXPORT_SECTION_MIGRATION_VERSION == 16


@pytest.mark.parametrize(("key", "old", "new"), [
    ("indiachart", "分盘吉位 Vimśopaka", "分盘吉位 Vaiśeṣikāṁśa"),
    ("fengshui", "成員卦象", "成员卦象"),
    ("solararc", "星盘信息", "时段盘配置"),
    ("profection", "星盘信息", "时段盘配置"),
    ("jaynesprog", "赤纬推运（Jayne Declination）", "赤纬推运（Declination）"),
])
def test_legacy_section_titles_migrate_to_the_current_name(key: str, old: str, new: str) -> None:
    """负向对照：删掉 map_legacy_section_title 里任一条 → 对应参数红（实跑过 indiachart / jaynesprog 两条）。"""
    assert r.map_legacy_section_title(key, old) == new
    assert new in r.AI_EXPORT_PRESET_SECTIONS[key]


def test_renames_do_not_leak_to_other_keys() -> None:
    assert r.map_legacy_section_title("chart", "星盘信息") == "星盘信息"
    assert r.map_legacy_section_title("astrochart", "分盘吉位 Vimśopaka") == "分盘吉位 Vimśopaka"


def test_new_conditional_sections_are_double_registered() -> None:
    """条件段（缺省可能不产）必须 preset + optional 双登记，否则缺席时报 missing。"""
    for key, titles in {
        "germany": ["赤纬接触", "中点坐标", "公式求解"],
        "distributions": ["伙伴星期"],
        "indiachart": ["未能计算"],
    }.items():
        for title in titles:
            assert title in r.AI_EXPORT_PRESET_SECTIONS[key], (key, title)
            assert title in r.AI_EXPORT_OPTIONAL_SECTIONS[key], (key, title)
    assert r.AI_EXPORT_PRESET_SECTIONS["germany"].index("赤纬接触") == r.AI_EXPORT_PRESET_SECTIONS["germany"].index("六宫框落宫") + 1
