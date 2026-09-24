"""「星曜后天信息」导出开关（上游 aiExport.js:1933-2036 trimPlanetInfoBySetting，v0.40.0 逐字移植 exports/parser.py）。

期望值按上游函数的规则独立推出（不是跑一遍移植件抄输出）：
- 全开（缺省）→ 原样（零回归）；planet_info 给了对象但缺键 → 缺键即 0（normalizePlanetInfoSetting）。
- 括号内容逐段全匹配才算后天信息：后天:… / Nth / - / NR(NR…) / 主…宫 / 宫位未知|主宫未知 / (第)X宫（汉字数）。
  [Q-316/T-302] 三式合一「日马：申（坤二宫）」等宫位注记（坤 不是汉字数）不是后天信息 → 原样保留。
- 裁剪：按开关只留 宫位 / 主宰 之一，`; ` 连接；都不留 → 整个括号删除；尾处理 多空格并一、空括号删除、三连空行并二。
- 只对 AI_EXPORT_PLANET_INFO_TECHNIQUES 的技法生效（applyPlanetInfoFilterByContext）。
"""
from __future__ import annotations

import pytest

from horosa_skill.exports.parser import parse_export_content, trim_planet_info_by_setting
from horosa_skill.exports.registry import AI_EXPORT_PLANET_INFO_TECHNIQUES, get_technique_info

LINE = "土 (6th; 10R11R) 被 水 (10th; 3R6R) 接纳 (本垣+擢升)"


def test_full_on_or_no_setting_returns_the_content_verbatim() -> None:
    content = "日 (10th; 5R)\n\n\n\n月  (12th; 4R)（ ）"  # 连尾处理都不做：全开是纯直通
    assert trim_planet_info_by_setting(content, {"showHouse": 1, "showRuler": 1}) == content
    assert trim_planet_info_by_setting(content, {"showHouse": True, "showRuler": True}) == content


@pytest.mark.parametrize(
    ("setting", "expected"),
    [
        ({"showHouse": 1, "showRuler": 0}, "土 (6th) 被 水 (10th) 接纳 (本垣+擢升)"),
        ({"showHouse": 0, "showRuler": 1}, "土 (10R11R) 被 水 (3R6R) 接纳 (本垣+擢升)"),
        ({"showHouse": 0, "showRuler": 0}, "土 被 水 接纳 (本垣+擢升)"),
        ({}, "土 被 水 接纳 (本垣+擢升)"),  # 缺键即 0
        ({"showHouse": "1", "showRuler": 1}, "土 (10R11R) 被 水 (3R6R) 接纳 (本垣+擢升)"),  # 只认 1/True，字符串 "1" 不算开
    ],
)
def test_reception_line_is_trimmed_per_switch(setting: dict, expected: str) -> None:
    assert trim_planet_info_by_setting(LINE, setting) == expected


def test_non_planet_info_brackets_are_preserved() -> None:
    """[Q-316/T-302]：每段必须全匹配后天信息形态；三式合一的「（坤二宫）」「（震三宫）」与说明括号原样保留，
    同一行里真正的后天信息括号仍被裁。"""
    text = "日马：申（坤二宫）；庚击刑（震三宫）；火 (11th; 1R8R) 落 水瓶（固定·风）"
    assert trim_planet_info_by_setting(text, {"showHouse": 0, "showRuler": 0}) == "日马：申（坤二宫）；庚击刑（震三宫）；火 落 水瓶（固定·风）"
    assert trim_planet_info_by_setting("（第三宫）与（十二宫）", {"showHouse": 0, "showRuler": 1}) == "与"  # 汉字数宫位 = 后天信息，无主宰可留
    assert trim_planet_info_by_setting("（第三宫）", {"showHouse": 1, "showRuler": 0}) == "（第三宫）"


def test_houtian_prefix_unknown_and_dash_forms() -> None:
    assert trim_planet_info_by_setting("水 (后天: 10th; 主3宫)", {"showHouse": 0, "showRuler": 1}) == "水 (主3宫)"
    assert trim_planet_info_by_setting("水 (后天: 10th; 主3宫)", {"showHouse": 1, "showRuler": 0}) == "水 (10th)"
    assert trim_planet_info_by_setting("冥 (宫位未知; 主宫未知)", {"showHouse": 1, "showRuler": 0}) == "冥 (宫位未知)"
    assert trim_planet_info_by_setting("冥 (宫位未知; 主宫未知)", {"showHouse": 0, "showRuler": 1}) == "冥 (主宫未知)"
    # splitPlanetInfoParts 的兜底：宫位段已占（11th）后，剩下的 `-` 落到「未占的主宰段」（上游 forEach 末支 `if(!rulerPart)`）→ 主宰开时留 (-)。
    assert trim_planet_info_by_setting("冥 (11th; -)", {"showHouse": 0, "showRuler": 1}) == "冥 (-)"
    assert trim_planet_info_by_setting("冥 (11th; -)", {"showHouse": 1, "showRuler": 0}) == "冥 (11th)"
    # 单段 `-` 只当宫位段 → 无主宰可留 → 整括号删；上游尾处理只并 2+ 空格、不裁行尾单空格（parse_export 整体 strip）。
    assert trim_planet_info_by_setting("冥 (-)", {"showHouse": 0, "showRuler": 1}) == "冥 "
    assert trim_planet_info_by_setting("冥 (-)", {"showHouse": 1, "showRuler": 0}) == "冥 (-)"


def test_case_fullwidth_and_tail_cleanup_follow_upstream() -> None:
    # th 不分大小写；主宰段统一大写；全角括号同样处理；多空格并一、空括号删除、三连空行并二。
    assert trim_planet_info_by_setting("金（10TH; 3r6r）", {"showHouse": 0, "showRuler": 1}) == "金（3R6R）"
    assert trim_planet_info_by_setting("金（10TH; 3r6r）", {"showHouse": 1, "showRuler": 0}) == "金（10TH）"
    text = "A (10th)  B\n\n\n\nC（ ）D"
    assert trim_planet_info_by_setting(text, {"showHouse": 0, "showRuler": 0}) == "A B\n\nCD"


def test_parse_export_applies_the_switch_only_to_planet_info_techniques() -> None:
    content = "[信息]\n" + LINE + "\n\n[相位]\n日 (10th; 5R) 合 水 (10th; 3R6R)"
    assert "astrochart" in AI_EXPORT_PLANET_INFO_TECHNIQUES
    trimmed = parse_export_content(technique="astrochart", content=content, selected_sections=["信息", "相位"], planet_info={"showHouse": 1, "showRuler": 0})
    body = lambda section: section["content"].split("\n", 1)[1]  # noqa: E731 — 段 content 含 [标题] 头行
    by_title = {s["title"]: body(s) for s in trimmed["sections"]}
    assert by_title["信息"] == "土 (6th) 被 水 (10th) 接纳 (本垣+擢升)"
    assert by_title["相位"] == "日 (10th) 合 水 (10th)"
    untouched = parse_export_content(technique="astrochart", content=content, selected_sections=["信息", "相位"], planet_info=None)
    assert {s["title"]: body(s) for s in untouched["sections"]}["信息"] == LINE  # 无用户设置 = 上游缺省全开
    other = next(name for name in ("liuren", "qimen", "bazi") if get_technique_info(name) and not get_technique_info(name)["supports_planet_info"])
    same = parse_export_content(technique=other, content="[起课信息]\n日马：申（坤二宫）；火 (11th; 1R8R)", selected_sections=["起课信息"], planet_info={"showHouse": 0, "showRuler": 0})
    assert body(same["sections"][0]) == "日马：申（坤二宫）；火 (11th; 1R8R)"
