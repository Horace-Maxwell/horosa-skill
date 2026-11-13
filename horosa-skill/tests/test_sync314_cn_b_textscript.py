"""上游 v3.14.0（Horosa-Public 10fb75de → e55c3a66）繁体输出规则：hantRules.js 新增三条整词，并入本仓 `horosa_char_rules.json`。

上游 diff（utils/scriptConvert/hantRules.js，只动 RULES）：
  · 「历」的白名单 + `'藏历年': '藏曆年'` —— 「历年」本在白名单里作「歷年」（历年 = 过去多年），最长匹配会从「藏历年」里
    切出「历年」→「藏歷年」；东亚诸术的藏占正文 / 帮助里到处是「藏历年」。
  · 「后」「发」的白名单各 + `'后发座': '后髮座'`（星座名，取「皇后之发」；上游 utils/__tests__/transformCharts.test.js:106-110）。
规则是否与上游逐条相同由 tests/test_textscript.py::test_character_rules_cover_upstream_except_documented_deviations 在有上游
checkout 时裁定（基底上它就是红在「藏历年」）；本文件是没有上游 checkout 也跑的值级金样。

负向对照（2026-11-13 实跑）：
  · 删掉 JSON 里「藏历年」一行 → `test_tibetan_calendar_year_keeps_the_calendar_li` 两条、`test_plain_li_nian_…`、
    表项用例都红（得到「藏歷年」）；
  · 删掉两处「后发座」→ 本文件**照绿**：OpenCC 词典自己就把「后发座」转成「后髮座」，这一行在本仓是与上游对齐用的
    （上游的转换链没有这条词典词）。删掉它红的是上面那条上游比对用例（「后: 上游 后发座→后髮座，本仓 None」）。
    所以 `test_coma_berenices_keeps_the_empress_hou` 只是值的回归样例，不是这一行的守卫——如实写在这里。
"""

from __future__ import annotations

import json
from importlib import resources

import pytest

from horosa_skill.textscript import TRADITIONAL, TRADITIONAL_HK, convert


@pytest.mark.parametrize(("simplified", "traditional"), [
    ("藏占按藏历年、洛书流年按公历年", "藏占按藏曆年、洛書流年按公曆年"),
    ("岁数按藏历年算，出生那一年算一岁", "歲數按藏曆年算，出生那一年算一歲"),
])
def test_tibetan_calendar_year_keeps_the_calendar_li(simplified: str, traditional: str) -> None:
    assert convert(simplified, TRADITIONAL) == traditional
    assert convert(simplified, TRADITIONAL_HK) == traditional


def test_plain_li_nian_still_means_past_years() -> None:
    """新词不能把「历年」本义带歪：历年（过去多年）仍作「歷年」，农历年 / 公历年仍作「曆」。"""
    assert convert("历年藏历年表", TRADITIONAL) == "歷年藏曆年表"
    assert convert("农历年、公历年、历年来", TRADITIONAL) == "農曆年、公曆年、歷年來"


def test_coma_berenices_keeps_the_empress_hou() -> None:
    assert convert("后发座", TRADITIONAL) == "后髮座"                # 上游 transformCharts.test.js:109
    assert convert("北冕座与后发座", TRADITIONAL) == "北冕座與后髮座"
    assert convert("先天后天，后发制人", TRADITIONAL) == "先天後天，後發制人"   # 别的「后发」不受牵连


def test_rule_table_records_the_upstream_release_it_was_read_at() -> None:
    doc = json.loads(resources.files("horosa_skill.textscript.data").joinpath("horosa_char_rules.json").read_text(encoding="utf-8"))
    assert doc["upstream"]["release"] == "v3.14.0" and doc["upstream"]["commit"] == "e55c3a66"
    assert doc["rules"]["历"]["words"]["藏历年"] == "藏曆年"
    assert doc["rules"]["后"]["words"]["后发座"] == doc["rules"]["发"]["words"]["后发座"] == "后髮座"
