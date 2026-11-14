"""直接收农历日期（审计 F02 / F07 / 待决项 2，P0：以前两条错路都通向另一张盘）。

- 结构化写法（`lunar: true` / `calendar: "农历"` / `isLunar` / `dateType: "lunar"` + `leap`）：以前只换来「不是本技法的参数」，然后按公历同号日起盘。
- 汉字月日（「1990年八月十五」）与节日（「1990年中秋」）：以前报 invalid_date + 不必问用户 = 让模型改写成公历 8 月 15 日。
换算只查 `data/lunar_months.json`（scripts/gen_lunar_table.mjs 从 lunar-javascript 生成），1900–2100 年每一天与 lunar-javascript 逐日往返。

负向对照（实跑过）：parse_date 里 `lunar = parse_lunar_date(raw)` 那三行删掉 → 文字写法用例全红；`_apply_calendar_flags` 改成直接 return →
结构化用例红；表里任一年的 start 改动一天 → 往返用例红。
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from node_esm import run_node_esm

from horosa_skill import lunar_calendar as L
from horosa_skill.input_fields import FieldIssue, parse_date
from horosa_skill.input_normalization import normalize_collecting_issues
from horosa_skill.schemas.tools import BaZiBirthInput

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")
PKG = Path(__file__).resolve().parents[1]
CORE_JS = PKG / "horosa-core-js"

# 期望值的独立来源：1990 中秋 = 10-03、1991 春节 = 02-15（除夕 02-14）为公开历表；其余与 lunar-javascript 直算一致。
TEXT_CASES = [
    ("农历1990年四月初九", "1990-05-03"), ("1990年闰五月初三", "1990-06-25"), ("1990年腊月廿三", "1991-02-07"),
    ("1990年八月十五", "1990-10-03"), ("一九九〇年八月十五", "1990-10-03"), ("1990年中秋", "1990-10-03"), ("1990年除夕", "1991-02-14"),
    ("1991年春节", "1991-02-15"), ("农历1990-04-09", "1990-05-03"), ("lunar 1990-04-09", "1990-05-03"), ("1990年二月二", "1990-02-26"),
    ("1990年七月七日", "1990-08-26"), ("1990年腊月初八", "1991-01-23"),
]


@pytest.mark.parametrize(("text", "solar"), TEXT_CASES)
def test_lunar_spellings_convert(text: str, solar: str) -> None:
    parsed = parse_date(text)
    assert parsed.value == solar and "按农历换算" in parsed.note_zh


@pytest.mark.parametrize("text", ["1990年5月3日", "1990-05-03", "19900503"])
def test_arabic_month_day_without_a_lunar_mark_stays_gregorian(text: str) -> None:
    assert parse_date(text).value == "1990-05-03"


def test_leap_ambiguity_is_asked_with_both_dates() -> None:
    with pytest.raises(FieldIssue) as excinfo:
        parse_date("1990年五月初三")
    assert excinfo.value.code == "tool.lunar_leap_month_ambiguous" and excinfo.value.ask_user
    assert [o["value"] for o in excinfo.value.options] == ["1990-05-26", "1990-06-25"]


@pytest.mark.parametrize(("text", "code"), [("农历八月十五", "tool.lunar_date_needs_year"), ("农历1850年三月初三", "tool.lunar_date_unsupported"),
                                            ("1990年闰四月初三", "tool.invalid_date"), ("农历1990年四月三十", "tool.invalid_date")])
def test_impossible_or_incomplete_lunar_dates_are_refused(text: str, code: str) -> None:
    with pytest.raises(FieldIssue) as excinfo:
        parse_date(text)
    assert excinfo.value.code == code


def _norm(**extra):
    payload = {"date": "1990-04-09", "time": "08:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 0, **extra}
    return normalize_collecting_issues(payload, model=BaZiBirthInput)


@pytest.mark.parametrize("flags", [{"lunar": True}, {"calendar": "农历"}, {"isLunar": "true"}, {"dateType": "lunar"}, {"calendar": "lunar"}])
def test_structured_lunar_flags_convert_instead_of_being_ignored(flags: dict) -> None:
    out, issues = _norm(**flags)
    assert issues == [] and out["date"] == "1990-05-03"
    assert not any(key in out for key in flags)


def test_structured_leap_flag_and_julian_refusal() -> None:
    out, issues = _norm(date="1990-05-03", lunar=True, leap=True)
    assert issues == [] and out["date"] == "1990-06-25"
    out, issues = _norm(calendar="julian")
    assert [i["code"] for i in issues] == ["tool.calendar_unsupported"]
    out, issues = _norm(calendar="gregorian")
    assert issues == [] and out["date"] == "1990-04-09"


@requires_node
def test_table_is_current_with_the_generator() -> None:
    subprocess.run(["node", str(PKG / "scripts" / "gen_lunar_table.mjs"), "--check"], check=True, capture_output=True, text=True, encoding="utf-8")


@requires_node
def test_every_day_1900_to_2100_round_trips_against_lunar_javascript(tmp_path: Path) -> None:
    script = """
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(process.argv[1]);
const { Solar } = require('lunar-javascript');
const rows = [];
let s = Solar.fromYmd(1900, 1, 31);
while (s.getYear() <= 2100) {
  const l = s.getLunar();
  if (l.getYear() > 2100) break;
  rows.push([s.toYmd(), l.getYear(), Math.abs(l.getMonth()), l.getDay(), l.getMonth() < 0 ? 1 : 0]);
  s = s.next(1);
}
fs.writeFileSync(process.argv[2], JSON.stringify(rows));
"""
    out = tmp_path / "days.json"
    run_node_esm(script, str(CORE_JS / "package.json"), str(out), cwd=CORE_JS, timeout=600)
    rows = json.loads(out.read_text())
    assert len(rows) > 73000
    bad = [row for row in rows if L.to_solar(row[1], row[2], row[3], bool(row[4])).isoformat() != row[0]]
    assert bad == [], bad[:5]


def test_a_techniques_own_calendar_setting_is_not_taken_for_the_date_calendar() -> None:
    """十年大运的 `calendarType: calendar_360` 是技法设置，不是「日期用什么历」。MCP 面的预归一化不知道技法（fields=None），
    曾把它当成认不出的历法报 calendar_unsupported，十年大运整个起不了盘（全量 pytest 抓到）。"""
    from horosa_skill.schemas.tools.predictive import DecennialsInput

    for model in (None, DecennialsInput):
        out, issues = normalize_collecting_issues({"date": "1990-04-09", "time": "08:00", "zone": "+08:00", "lat": "31n13",
                                                   "lon": "121e28", "calendarType": "calendar_360"}, model=model)
        assert issues == [] and out["calendarType"] == "calendar_360" and out["date"] == "1990-04-09"
    # 不知道技法时，认得出的农历标记照样换算
    out, issues = normalize_collecting_issues({"date": "1990-04-09", "calendar": "lunar"}, model=None)
    assert issues == [] and out["date"] == "1990-05-03"
