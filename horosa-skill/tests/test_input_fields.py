"""v0.50.0 逐字段入参校验（IN-01/02/03/04/06/09/13，input_fields + input_normalization）。

每个字段一张表：读得懂的写法 → 规范值；读不懂的 → 指定错误码（绝不原样流到引擎、绝不换成缺省值）。
表的种子是审计的探针清单（audit-1111/inputs），另补了繁体、全角、英文写法。最后一个用例对**全部技法**按 schema
推出字段种类（不手列工具）逐一喂垃圾值：一律拒、码对、永远不是 ok=True。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import RECOVERY_TABLE, ToolValidationError
from horosa_skill.input_fields import input_notes_scope
from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.service.text.chinese import resolve_sixyao_cast

BASE = {"date": "1990-05-03", "time": "08:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}


def _norm(**fields: Any) -> dict[str, Any]:
    return normalize_request_payload({**BASE, **fields})


def _refused(**fields: Any) -> ToolValidationError:
    with pytest.raises(ToolValidationError) as caught:
        normalize_request_payload({**BASE, **fields})
    return caught.value


# ───────────────────────── 时区 ─────────────────────────

ZONE_ACCEPTED = [
    ("+08:00", "+08:00"), ("8", "+08:00"), ("+8", "+08:00"), (8, "+08:00"), ("UTC+8", "+08:00"), ("GMT+0800", "+08:00"),
    ("08:00", "+08:00"), ("0800", "+08:00"), ("800", "+08:00"), ("5.5", "+05:30"), ("+0545", "+05:45"), ("UTC8", "+08:00"),
    ("Z", "+00:00"), ("UTC", "+00:00"), ("东八区", "+08:00"), ("東八區", "+08:00"), ("西五区", "-05:00"), ("东8区", "+08:00"),
    ("E8", "+08:00"), ("W5", "-05:00"), ("UT+8", "+08:00"), ("−08:00", "-08:00"), ("＋08:00", "+08:00"), ("－05:00", "-05:00"),
    # 地区名按盘面日期换算：1990-05-03 在中国大陆夏令时内（1986–1991），北京时间 = +09:00。
    ("北京时间", "+09:00"), ("Asia/Shanghai", "+09:00"), ("asia/shanghai", "+09:00"), ("US/Eastern", "-04:00"), ("Etc/GMT-8", "+08:00"),
    ("+14:00", "+14:00"), ("-12:00", "-12:00"),
]
ZONE_REFUSED = [
    ("480", "tool.invalid_zone"), (480, "tool.invalid_zone"), ("28800", "tool.invalid_zone"), ("+480:00", "tool.invalid_zone"),
    ("CST", "tool.invalid_zone"), ("EST", "tool.invalid_zone"), ("IST", "tool.invalid_zone"), ("PST", "tool.invalid_zone"),
    ("+15:00", "tool.invalid_zone"), ("-13:00", "tool.invalid_zone"), ("Mars/Base", "tool.invalid_zone"), ("东十五区", "tool.invalid_zone"),
    (True, "tool.invalid_zone"), ("+08:00:30", "tool.invalid_zone"), ("beijing-ish", "tool.invalid_zone"),
]


@pytest.mark.parametrize(("value", "expected"), ZONE_ACCEPTED)
def test_zone_forms_are_understood(value: Any, expected: str) -> None:
    assert _norm(zone=value)["zone"] == expected


@pytest.mark.parametrize(("value", "code"), ZONE_REFUSED)
def test_zone_garbage_is_refused(value: Any, code: str) -> None:
    error = _refused(zone=value)
    assert error.code == code
    entry = error.details["fields"][0]
    assert entry["field"] == "zone" and entry["got"] == value and entry["expected"] and entry["example"]


def test_ambiguous_abbreviation_offers_candidates_and_asks_the_user() -> None:
    error = _refused(zone="CST")
    assert {"+08:00", "-06:00"} <= {option["value"] for option in error.details["options"]}
    assert error.details["agent_recovery"]["must_ask_user"] is True


def test_minutes_are_refused_with_the_minute_reading_offered() -> None:
    error = _refused(zone=480)
    assert "+08:00" in [option["value"] for option in error.details["options"]]
    assert error.details["agent_recovery"]["must_ask_user"] is False  # 写法问题，agent 自己能改


@pytest.mark.parametrize(
    ("zone", "date", "time", "offsets"),
    [
        ("America/New_York", "2021-11-07", "01:30", ["-04:00", "-05:00"]),  # 回拨重叠：出现两次
        ("America/New_York", "2021-03-14", "02:30", ["-05:00", "-04:00"]),  # 拨快缺口：不存在
    ],
)
def test_iana_zone_on_ambiguous_or_missing_wall_time_is_refused_like_place(zone: str, date: str, time: str, offsets: list[str]) -> None:
    error = _refused(zone=zone, date=date, time=time)
    assert error.code == "tool.zone_ambiguous"
    assert error.details["options"] == offsets
    assert error.details["agent_recovery"]["must_ask_user"] is True


def test_iana_zone_keeps_prc_summer_time_and_explicit_offset_is_left_alone() -> None:
    # 1988 年中国大陆夏令时：IANA 名按当时规则 +09:00；显式 +08:00 不改（是否加提醒留给维护者，见报告）。
    assert _norm(zone="Asia/Shanghai", date="1988-06-01", time="12:00")["zone"] == "+09:00"
    assert _norm(zone="北京时间", date="1988-06-01", time="12:00")["zone"] == "+09:00"
    assert _norm(zone="+08:00", date="1988-06-01", time="12:00")["zone"] == "+08:00"


def test_iana_zone_without_date_and_time_is_refused() -> None:
    with pytest.raises(ToolValidationError) as caught:
        normalize_request_payload({"zone": "Asia/Shanghai"})
    assert caught.value.code == "tool.invalid_zone"


# ───────────────────────── 时刻 ─────────────────────────

TIME_ACCEPTED = [
    ("08:00", "08:00:00"), ("8:00", "08:00:00"), ("8:5", "08:05:00"), ("08:00:30", "08:00:30"), ("0830", "08:30:00"),
    ("T08:30", "08:30:00"), ("8时30分", "08:30:00"), ("8時30分", "08:30:00"),
    ("20点48", "20:48:00"), ("上午8点", "08:00:00"), ("下午3点", "15:00:00"), ("晚上8点半", "20:30:00"),
    ("早上6点", "06:00:00"), ("中午12点", "12:00:00"), ("凌晨3点", "03:00:00"), ("8:30 PM", "20:30:00"), ("PM 8:30", "20:30:00"),
    ("8pm", "20:00:00"), ("12 AM", "00:00:00"), ("１０：３０", "10:30:00"), ("早上十点一刻", "10:15:00"), ("辰初", "07:00:00"), ("午正", "12:00:00"), ("正午", "12:00:00"), ("noon", "12:00:00"),
    ("8.30am", "08:30:00"), ("8h30", "08:30:00"), ("午后2点", "14:00:00"),
]
TIME_REFUSED = [
    ("24:00", "tool.invalid_time"), ("25:00", "tool.invalid_time"), ("08:60", "tool.invalid_time"), ("8", "tool.invalid_time"),
    (8.5, "tool.invalid_time"), ("abc", "tool.invalid_time"), ("13pm", "tool.invalid_time"), ("上午15点", "tool.invalid_time"),
    ("晚上12点", "tool.invalid_time"), ("辰时", "tool.time_is_shichen"), ("子時", "tool.time_is_shichen"),
    ("unknown", "tool.time_unknown"), ("不详", "tool.time_unknown"), ("不知道", "tool.time_unknown"), ("不詳", "tool.time_unknown"),
    # 审计 F23 / F25：口语「8点」上午下午都可能；「午夜」要问是哪一天的零点
    ("8点", "tool.time_ampm_unclear"), ("8點", "tool.time_ampm_unclear"), ("八点半", "tool.time_ampm_unclear"),
    ("十点一刻", "tool.time_ampm_unclear"), ("午夜", "tool.time_midnight_ambiguous"), ("midnight", "tool.time_midnight_ambiguous"),
]


@pytest.mark.parametrize(("value", "expected"), TIME_ACCEPTED)
def test_time_forms_are_understood(value: Any, expected: str) -> None:
    assert _norm(time=value)["time"] == expected


@pytest.mark.parametrize(("value", "code"), TIME_REFUSED)
def test_time_garbage_is_refused(value: Any, code: str) -> None:
    assert _refused(time=value).code == code


def test_shichen_offers_the_two_hour_span_and_does_not_pick_a_time() -> None:
    error = _refused(time="辰时")
    assert error.details["options"][0]["value"] == "07:00–09:00"
    assert error.details["agent_recovery"]["must_ask_user"] is True


def test_midnight_24_offers_the_next_day_reading() -> None:
    assert "次日" in _refused(time="24:00").details["options"][0]["label"]


# ───────────────────────── 日期 ─────────────────────────

DATE_ACCEPTED = [
    ("1990-05-03", "1990-05-03"), ("1990/5/3", "1990-05-03"), ("1990.5.3", "1990-05-03"), ("19900503", "1990-05-03"),
    ("1990年5月3日", "1990-05-03"), ("1990年5月3號", "1990-05-03"), ("１９９０-０５-０３", "1990-05-03"), ("2000-02-29", "2000-02-29"),
    ("1900-02-28", "1900-02-28"), ("1500-02-29", "1500-02-29"), ("-0500-03-21", "-0500-03-21"),
    ("3000-01-01", "3000-01-01"), ("9999-12-31", "9999-12-31"), ("31/12/1990", "1990-12-31"), ("12/31/1990", "1990-12-31"),
]
DATE_REFUSED = [
    ("1990-02-30", "tool.invalid_date"), ("1990-13-01", "tool.invalid_date"), ("1990-00-10", "tool.invalid_date"),
    ("1900-02-29", "tool.invalid_date"), ("90-05-03", "tool.invalid_date"), ("03/05/1990", "tool.ambiguous_date"),
    # 农历：没有年份的问用户要年份；带年份的直接换算（tests/test_fix314_lunar_input.py）；只有月没有日的照旧拒。
    ("农历正月初五", "tool.lunar_date_needs_year"), ("農曆三月", "tool.lunar_date_unsupported"),
    ("yesterday", "tool.invalid_date"), (19900503.0, "tool.invalid_date"),
]


@pytest.mark.parametrize(("value", "expected"), DATE_ACCEPTED)
def test_date_forms_are_understood(value: Any, expected: str) -> None:
    assert _norm(date=value)["date"] == expected


@pytest.mark.parametrize(("value", "code"), DATE_REFUSED)
def test_date_garbage_is_refused(value: Any, code: str) -> None:
    assert _refused(date=value).code == code


def test_ambiguous_dmy_offers_both_readings() -> None:
    assert sorted(_refused(date="03/05/1990").details["options"]) == ["1990-03-05", "1990-05-03"]


def test_iso_datetime_in_date_is_split_and_a_conflicting_time_is_an_error() -> None:
    out = normalize_request_payload({"date": "1990-05-03T08:30:00", "zone": "+08:00"})
    assert (out["date"], out["time"]) == ("1990-05-03", "08:30:00")
    assert _refused(date="1990-05-03T09:30:00", time="08:30").code == "tool.field_conflict"


def test_lunar_refusal_names_the_conversion_tool() -> None:
    # 1900–2100 年的农历直接换算（test_fix314_lunar_input.py）；表外年份才指向万年历工具，没写年份的先问年份。
    assert "horosa_cn_calendar_month" in str(_refused(date="农历1850年正月初五"))
    assert "哪一年" in str(_refused(date="正月初五"))


def test_two_digit_year_with_explicit_era_is_kept() -> None:
    assert _norm(date="90-05-03", ad=1)["date"] == "0090-05-03"


# ───────────────────────── 经纬度 ─────────────────────────

COORD_ACCEPTED = [
    ("lat", "31n13", "31n13"), ("lat", "31.2167", "31n13"), ("lat", 31.2167, "31n13"), ("lat", "N31.2167", "31n13"),
    ("lat", "31°13′N", "31n13"), ("lat", "31° 13' N", "31n13"), ("lat", "31:13:00N", "31n13"), ("lat", "北纬31.2167", "31n13"),
    ("lat", "北緯31°13′", "31n13"), ("lat", "-33.8688", "33s52"), ("lat", "南纬33.8688", "33s52"), ("lon", "121e28", "121e28"),
    ("lon", "E121.47", "121e28"), ("lon", "東經121.47", "121e28"), ("lon", "东经121°28′", "121e28"), ("lon", "西经74.006", "74w00"),
    ("lon", "W74.006", "74w00"), ("lon", "12W30:00", "12w30"), ("lat", "３１．２１６７", "31n13"),
]
COORD_REFUSED = [
    ("lat", "121e28"), ("lon", "31n13"), ("lat", "95"), ("lat", "-91"), ("lon", "181"), ("lat", "40n75"), ("lat", "31°75′N"),
    ("lat", "上海"), ("lat", True), ("lon", "abc"), ("lat", "N31.2S"), ("lat", float("nan")), ("lon", float("inf")),
]


@pytest.mark.parametrize(("axis", "value", "expected"), COORD_ACCEPTED)
def test_coordinate_forms_are_understood(axis: str, value: Any, expected: str) -> None:
    assert _norm(**{axis: value})[axis] == expected


@pytest.mark.parametrize(("axis", "value"), COORD_REFUSED)
def test_coordinate_garbage_is_refused(axis: str, value: Any) -> None:
    assert _refused(**{axis: value}).code == "tool.invalid_coordinate"


def test_swapped_axes_are_refused_not_computed_six_hours_off() -> None:
    error = _refused(lat="121e28", lon="31n13")
    assert [entry["field"] for entry in error.details["fields"]] == ["lat", "lon"]


def test_minutes_over_sixty_offer_both_readings() -> None:
    values = [option["value"] for option in _refused(lat="40n75").details["options"]]
    assert values == [40.75, 41.25]


def test_conflicting_gps_pair_follows_lat_lon_with_a_warning() -> None:
    with input_notes_scope() as notes:
        out = _norm(gpsLat=40.0)
    assert out["lat"] == "31n13" and out["gpsLat"] == pytest.approx(31.216667)
    assert any("gpsLat" in note for note in notes)


def test_coordinate_aliases_are_read_with_a_warning() -> None:
    with input_notes_scope() as notes:
        out = normalize_request_payload({**{k: v for k, v in BASE.items() if k not in ("lat", "lon")}, "latitude": 31.2167, "lng": "121.4667"})
    assert (out["lat"], out["lon"]) == ("31n13", "121e28")
    assert any("latitude" in note for note in notes) and any("lng" in note for note in notes)


# ───────────────────────── 性别 ─────────────────────────

GENDER_ACCEPTED = [
    (1, 1), (0, 0), (True, 1), (False, 0), ("男", 1), ("女", 0), ("male", 1), ("Female", 0), ("M", 1), ("f", 0), ("乾造", 1),
    ("坤造", 0), ("男命", 1), ("女命", 0), ("先生", 1), ("小姐", 0), ("太太", 0), ("男生", 1), ("女生", 0), ("♂", 1), ("♀", 0),
    ("男士", 1), ("女士", 0), ("乾", 1), ("坤", 0), ("１", 1),
]
GENDER_REFUSED = ["其他", "x", 2, -1, "unknown", "true", "both", 0.5, "nan", "NaN", "nv"]   # 审计 F29：nan 不是性别


@pytest.mark.parametrize(("value", "expected"), GENDER_ACCEPTED)
def test_gender_forms_are_understood(value: Any, expected: int) -> None:
    assert _norm(gender=value)["gender"] == expected


@pytest.mark.parametrize("value", GENDER_REFUSED)
def test_gender_garbage_is_refused(value: Any) -> None:
    error = _refused(gender=value)
    assert error.code == "tool.invalid_gender" and error.details["agent_recovery"]["must_ask_user"] is True


def test_sex_alias_is_read_as_gender() -> None:
    assert _norm(sex="女")["gender"] == 0


# ───────────────────────── 宫制 / 黄道（schema 层的词表校验） ─────────────────────────

CHART = TOOL_DEFINITIONS["chart"].input_model
INDIA = TOOL_DEFINITIONS["india_chart"].input_model


@pytest.mark.parametrize(
    ("value", "expected"),
    [("Placidus", 3), ("placidus", 3), ("整宫制", 0), ("整宮制", 0), ("whole sign", 0), ("Whole Signs", 0), ("Alcabitius", 1), ("Koch", 4), (3, 3), ("3", 3)],
)
def test_house_system_names_resolve_through_the_shared_table(value: Any, expected: int) -> None:
    assert CHART.model_validate({**BASE, "hsys": value}).hsys == expected


def test_india_house_system_uses_the_india_table() -> None:
    assert INDIA.model_validate({**BASE, "hsys": "Placidus"}).hsys == 3  # 印占表 3 = KP / Placidus
    assert INDIA.model_validate({**BASE, "hsys": "Alcabitus"}).hsys == 8  # 印占表 8 = Alcabitus（西占表是 1）


@pytest.mark.parametrize("value", [99, -1, "Plac", True, "36"])
def test_house_system_outside_the_engine_table_is_refused(value: Any) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as caught:
        CHART.model_validate({**BASE, "hsys": value})
    error = caught.value.errors()[0]
    assert error["type"] == "horosa_field" and error["ctx"]["code"] == "tool.invalid_house_system"
    assert len(error["ctx"]["options"]) == 25  # 错误里列出全部合法 索引=名称


@pytest.mark.parametrize(("value", "expected"), [("tropical", 0), ("sidereal", 1), ("恒星黄道", 1), ("回歸黃道", 0), (1, 1), (True, 1)])
def test_zodiac_names_resolve(value: Any, expected: int) -> None:
    assert CHART.model_validate({**BASE, "zodiacal": value}).zodiacal == expected


# ───────────────────────── 推运目标 ─────────────────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2026", "2026"), (2026, "2026"), ("2026-05-03", "2026-05-03"), ("2026-05-03T08:00:00", "2026-05-03 08:00:00"), ("2026-5-3 8:00", "2026-05-03 08:00:00")],
)
def test_target_datetime_forms(value: Any, expected: str) -> None:
    assert _norm(datetime=value)["datetime"] == expected


@pytest.mark.parametrize("value", ["next year", "2026-13-01", "2026-05-03T08:00:00+08:00", "26"])
def test_target_datetime_garbage_is_refused(value: Any) -> None:
    assert _refused(datetime=value).code == "tool.invalid_datetime"


def test_dir_zone_goes_through_the_zone_validator() -> None:
    assert _norm(datetime="2026-05-03 08:00", dirZone="东八区")["dirZone"] == "+08:00"
    assert _refused(datetime="2026-05-03 08:00", dirZone="CST").code == "tool.invalid_zone"


# ───────────────────────── 结构：每个字段一条恢复条目 ─────────────────────────


def test_every_failing_field_gets_its_own_recovery_entry() -> None:
    error = _refused(zone="CST", time="辰时", lat="95")
    fields = {entry["field"]: entry for entry in error.details["agent_recovery"]["fix_fields"]}
    assert set(fields) == {"zone", "time", "lat"}
    for entry in fields.values():
        assert {"field", "got", "expected", "example", "code"} <= set(entry)
    assert error.details["agent_recovery"]["must_ask_user"] is True  # 时辰与缩写都只有用户知道


def test_nested_parties_go_through_the_same_validator() -> None:
    with pytest.raises(ToolValidationError) as caught:
        normalize_request_payload({"inner": {**BASE, "zone": "480"}, "outer": {**BASE, "time": "辰时"}})
    assert [entry["field"] for entry in caught.value.details["fields"]] == ["inner.zone", "outer.time"]


def test_engine_structures_below_party_level_are_left_lenient() -> None:
    # 引擎结果回传（nongli、jieqi_year_*…）不是用户输入，不替引擎判。
    out = normalize_request_payload({"nongli": {"zone": "东八区", "gender": "x", "date": "1990-02-30"}})
    assert out["nongli"] == {"zone": "东八区", "gender": "x", "date": "1990-02-30"}


def test_every_new_code_has_an_exact_recovery_entry() -> None:
    for code in ("tool.invalid_zone", "tool.zone_ambiguous", "tool.invalid_time", "tool.time_unknown", "tool.time_is_shichen",
                 "tool.invalid_date", "tool.ambiguous_date", "tool.lunar_date_unsupported", "tool.lunar_date_needs_year",
                 "tool.lunar_leap_month_ambiguous", "tool.calendar_unsupported", "tool.invalid_coordinate",
                 "tool.invalid_gender", "tool.missing_gender", "tool.missing_field", "tool.invalid_datetime", "tool.field_conflict",
                 "tool.invalid_house_system", "tool.invalid_zodiacal", "tool.invalid_option", "tool.confirmation_flag_not_boolean",
                 "tool.sixyao_invalid_cast"):
        assert code in RECOVERY_TABLE, code


# ───────────────────────── 全目录：按 schema 推字段种类，逐技法喂垃圾 ─────────────────────────

# 字段种类由 schema 推（键名 + 模型声明），不手列工具：新技法自动进来。
FIELD_KINDS: dict[str, tuple[list[Any], set[str]]] = {
    "date": (["1990-02-30", "yesterday", "03/05/1990"], {"tool.invalid_date", "tool.ambiguous_date"}),
    "time": (["25:00", "子时", "abc"], {"tool.invalid_time", "tool.time_is_shichen"}),  # 「辰时」对中式命理照算（待决项 1），子时不分早晚处处要问
    "zone": (["480", "CST", "Mars/Base"], {"tool.invalid_zone"}),
    "lat": (["95", "121e28", "上海"], {"tool.invalid_coordinate"}),
    "lon": (["181", "31n13", "abc"], {"tool.invalid_coordinate"}),
    "gender": (["其他", 2], {"tool.invalid_gender"}),
}
FIELD_KINDS["guaDate"], FIELD_KINDS["guaTime"], FIELD_KINDS["guaZone"] = FIELD_KINDS["date"], FIELD_KINDS["time"], FIELD_KINDS["zone"]
FIELD_KINDS["dirZone"] = FIELD_KINDS["zone"]
FIELD_KINDS["dirLat"], FIELD_KINDS["dirLon"] = FIELD_KINDS["lat"], FIELD_KINDS["lon"]


def _catalogue_cases() -> list[tuple[str, str]]:
    cases = []
    for name, definition in TOOL_DEFINITIONS.items():
        for field in definition.input_model.model_fields:
            if field in FIELD_KINDS:
                cases.append((name, field))
    return cases


CATALOGUE_CASES = _catalogue_cases()


def test_catalogue_cases_cover_most_techniques() -> None:
    assert len({name for name, _ in CATALOGUE_CASES}) >= 90, "字段种类推导坏了：几乎每个技法都有 date / time / zone"


@pytest.fixture(scope="module")
def service(tmp_path_factory: pytest.TempPathFactory) -> Any:
    from horosa_skill.config import Settings
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService

    root: Path = tmp_path_factory.mktemp("catalogue")
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=root / "rt",
                        db_path=root / "m.db", output_dir=root / "runs")
    return HorosaSkillService(settings, store=MemoryStore(settings))


@pytest.mark.parametrize(("tool_name", "field"), CATALOGUE_CASES)
def test_every_technique_refuses_garbage_in_every_field_of_a_known_kind(service: Any, tool_name: str, field: str) -> None:
    garbage, codes = FIELD_KINDS[field]
    fields = TOOL_DEFINITIONS[tool_name].input_model.model_fields
    payload = {key: value for key, value in BASE.items() if key in fields}
    if "datetime" in fields:
        payload["datetime"] = "2026-05-03 08:00:00"
    payload["agent_confirmed_settings"] = True
    for value in garbage:
        try:
            envelope = service.run_tool(tool_name, {**payload, field: value}, save_result=False)
        except ToolValidationError as exc:
            entries = [entry for entry in exc.details.get("fields", []) if entry["field"] == field]
            assert entries, (tool_name, field, value, exc.code)
            assert entries[0]["code"] in codes, (tool_name, field, value, entries[0]["code"])
            continue
        raise AssertionError(f"{tool_name}.{field}={value!r} was not refused (ok={envelope.ok}, code={envelope.code})")


# ───────────────────────── 六爻手动起卦（IN-07）：给了却用不了 = 报错，绝不悄悄改成以时起卦 ─────────────────────────



def test_sixyao_coin_values_are_read_with_moving_lines() -> None:
    cast = resolve_sixyao_cast({"lines": [{"value": v} for v in (9, 7, 8, 7, 6, 7)]})
    assert cast["method"] == "manual"
    assert [(line["value"], line["change"]) for line in cast["lines"]] == [(1, True), (1, False), (0, False), (1, False), (0, True), (1, False)]
    assert cast["notes"]  # 铜钱值读法进 warnings


@pytest.mark.parametrize(
    "payload",
    [
        {"lines": [{"value": 1}] * 7},
        {"lines": [{"value": 1}] * 5},
        {"lines": [{"value": 2}] * 6},
        {"lines": [{"value": 9, "change": False}, *[{"value": 1}] * 5]},
        {"gua_code": "1111010"},
        {"gua_code": "1234"},
        {"numbers": [3, 5]},
        {"changed_code": "111111"},
        {"lines": [{"value": 1}] * 6, "gua_code": "000000"},
    ],
)
def test_sixyao_unusable_cast_input_is_refused(payload: dict[str, Any]) -> None:
    with pytest.raises(ToolValidationError) as caught:
        resolve_sixyao_cast(payload)
    assert caught.value.code in {"tool.sixyao_invalid_lines", "tool.sixyao_invalid_cast"}


def test_sixyao_names_go_to_the_engine_table_with_a_traditional_fallback() -> None:
    cast = resolve_sixyao_cast({"gua_code": "火天大有", "changed_code": "乾為天"})
    assert cast["method"] == "gua_name" and cast["gua_name"] == ["火天大有"]
    assert cast["changed_name"] == ["乾為天", "乾为天"]  # 逐字折叠、「乾」不折成「干」
    assert resolve_sixyao_cast({"gua_code": "111101"})["method"] == "gua_code"
    assert resolve_sixyao_cast({})["method"] == "time"


# ───────────────────────── 推运目标年（IN-13） ─────────────────────────


def test_year_only_target_becomes_that_years_birthday() -> None:
    from horosa_skill.service.enrich import _apply_yearly_target

    effective = {"date": "1990-05-03", "time": "08:00:00", "datetime": "2026"}
    _apply_yearly_target("solarreturn", effective)
    assert effective["datetime"] == "2026-05-03 08:00"
    leap = {"date": "1992-02-29", "time": "08:00:00", "datetime": "2026"}
    _apply_yearly_target("givenyear", leap)
    assert leap["datetime"] == "2026-03-01 08:00"  # 上游 returnPickerSeed：平年落 3/1
    dated = {"date": "1990-05-03", "time": "08:00:00", "datetime": "2026-05-03"}
    _apply_yearly_target("givenyear", dated)
    assert dated["datetime"] == "2026-05-03 08:00"  # givenyear 后端不收纯日期


def test_year_field_on_a_predictive_tool_is_read_as_the_target() -> None:
    model = TOOL_DEFINITIONS["solarreturn"].input_model
    out = normalize_request_payload({**BASE, "year": 2026}, model=model)
    assert out["datetime"] == "2026" and "year" not in out


def test_year_only_target_is_refused_where_it_has_no_yearly_meaning(service: Any) -> None:
    with pytest.raises(ToolValidationError) as caught:
        service.run_tool("pd", {**BASE, "datetime": "2026", "agent_confirmed_settings": True}, save_result=False)
    assert caught.value.code == "tool.invalid_datetime"


# ───────────────────────── 神数时刻（C-14）、合参技法名（IN-15） ─────────────────────────


@pytest.mark.parametrize("bad", ["abc", "25:00", "08:61"])
def test_shenshu_split_refuses_an_unreadable_time_instead_of_midnight(bad: str) -> None:
    from horosa_skill.service.options_cn import _split_birth_ymdhm

    with pytest.raises(ToolValidationError) as caught:
        _split_birth_ymdhm({"date": "1990-05-03", "time": bad})
    assert caught.value.code == "tool.invalid_time"
    assert _split_birth_ymdhm({"date": "1990-05-03"})["hour"] == 0  # 没给钟点 = 模型缺省 00:00（留给维护者定）


def test_hecan_tools_accept_a_comma_string_and_chinese_names() -> None:
    from pydantic import ValidationError

    from horosa_skill.schemas.tools.facades import HecanInput

    assert HecanInput.model_validate({"query": "q", "tools": "八字、紫微斗数,horosa_cn_qimen"}).tools == ["bazi_birth", "ziwei_birth", "qimen"]
    with pytest.raises(ValidationError) as caught:
        HecanInput.model_validate({"query": "q", "tools": ["bazi_brth"]})
    assert "bazi_birth" in str(caught.value)


@pytest.mark.parametrize("tool_name", ["solarreturn", "lunarreturn", "givenyear", "profection", "solararc"])
def test_predictive_defaults_turn_a_year_into_that_years_birthday(service: Any, tool_name: str) -> None:
    effective = service._apply_upstream_predictive_defaults(tool_name, {**BASE, "datetime": "2026"})
    assert effective["datetime"] == "2026-05-03 08:00"


@pytest.mark.parametrize(("value", "expected"), [
    ("May 3, 1990", "1990-05-03"), ("3 May 1990", "1990-05-03"), ("公历1990年5月3日", "1990-05-03"), ("阳历1990年5月3日", "1990-05-03"),
    ("民国79年5月3日", "1990-05-03"), ("公元前500年3月21日", "-0500-03-21"), ("500-03-21 BCE", "-0500-03-21"),
])
def test_more_unambiguous_date_forms(value: str, expected: str) -> None:
    """审计 F23：英文月名、明说公历、民国纪年、公元前——以前都被拒（「500-03-21 BCE」还怪到了时刻头上）。"""
    assert _norm(date=value)["date"] == expected


@pytest.mark.parametrize("value", ["1990年5月", "1990", "500 BC"])
def test_a_date_without_its_day_asks_the_user(value: str) -> None:
    from horosa_skill.errors import ToolValidationError

    with pytest.raises(ToolValidationError) as caught:
        _norm(date=value)
    assert "date_incomplete" in str(caught.value.code) or "date_incomplete" in json.dumps(caught.value.details, ensure_ascii=False)


def test_late_and_early_zi_spans_are_one_hour() -> None:
    """审计 F24：晚子时 23:00–24:00、早子时 00:00–01:00（以前都给整个子时 23:00–01:00）。"""
    from horosa_skill.errors import ToolValidationError

    for value, span in (("晚子时", "23:00–24:00"), ("早子时", "00:00–01:00")):
        with pytest.raises(ToolValidationError) as caught:
            _norm(time=value)
        assert span in json.dumps(caught.value.details, ensure_ascii=False)


def test_an_unsigned_zone_is_read_but_flagged() -> None:
    """审计 F23：zone「08:00」不带正负号，多半是把时刻填进了 zone——照读 +08:00，但说一声。"""
    from horosa_skill.input_fields import parse_zone

    parsed = parse_zone("08:00")
    assert parsed.value == "+08:00" and "没有正负号" in parsed.note_zh
    assert parse_zone("+08:00").note_zh == ""


@pytest.mark.parametrize("value", ["0000-05-03", "1582-10-10"])
def test_year_zero_and_the_reform_gap_are_asked(value: str) -> None:
    """审计 F22：历史纪年没有公元 0 年（0000 与 -0001 以前读成同一张盘）；1582-10-05…14 改历跳过，问用户是哪种读法。"""
    with pytest.raises(ToolValidationError):
        _norm(date=value)


def test_dates_before_1583_say_how_they_were_read() -> None:
    from horosa_skill.input_fields import parse_date

    assert "公元前 500 年" in parse_date("-0500-03-21").note_zh and "公元 1037 年" in parse_date("1037-01-08").note_zh
    assert parse_date("1990-05-03").note_zh == ""


# 审计 F06：约数 / 时段 / 区间 → 问用户，options 给覆盖的区间；不再报「写法不对」让模型自己编一个。
VAGUE_TIMES = [
    ("下午", ["12:00–18:00"]), ("早上", ["05:00–09:00"]), ("凌晨", ["00:00–06:00"]), ("morning", ["05:00–12:00"]),
    ("大概8点", ["08:00", "20:00"]), ("8点左右", ["08:00", "20:00"]), ("8点多", ["08:00", "20:00"]), ("下午三点左右", ["15:00"]),
    ("around 3pm", ["15:00"]), ("约08:30", ["08:30"]), ("快12点", ["00:00", "12:00"]), ("晚上8点到10点", ["20:00–22:00"]),
    ("八九点", ["08:00–09:00 或 / or 20:00–21:00"]), ("7点到9点", ["07:00–09:00 或 / or 19:00–21:00"]),
]


@pytest.mark.parametrize(("value", "options"), VAGUE_TIMES)
def test_vague_times_are_asked_with_the_span_they_cover(value: str, options: list[str]) -> None:
    """负向对照（实跑过）：parse_time 里不调 _approximate_time → 全部回到 tool.invalid_time（「八九点」是 KeyError）→ 红。"""
    error = _refused(time=value)
    assert error.code == "tool.time_approximate"
    assert [option["value"] for option in error.details["options"]] == options
    assert error.details["agent_recovery"]["must_ask_user"] is True


def test_cn_hour_numbers_are_not_shadowed_by_the_lunar_reader() -> None:
    """两个 _cn_number 同名时农历那个把钟点那个顶掉：「二十三点」KeyError、「十二三点」读成 12 点。负向对照：把农历那个改回同名 → 红。"""
    assert _norm(time="二十三点")["time"] == "23:00:00"
    assert _refused(time="十二三点").code == "tool.invalid_time"


def test_confirmed_approximate_time_is_disclosed() -> None:
    with input_notes_scope(fresh=True) as notes:
        out = _norm(time="08:00", time_approximate=True)
    assert out["time"] == "08:00:00" and "time_approximate" not in out
    assert any("约数" in note for note in notes)


def test_gregorian_date_with_a_matching_lunar_note_is_read_as_gregorian() -> None:
    """审计 F34：「1990年5月3日（农历四月初九）」以前整体判成农历拒掉。负向对照（实跑过）：parse_date 不调 _annotated_lunar → 红。"""
    assert _norm(date="1990年5月3日（农历四月初九）")["date"] == "1990-05-03"
    assert _norm(date="1991-02-07（农历腊月廿三）")["date"] == "1991-02-07"


def test_gregorian_date_with_a_conflicting_lunar_note_is_asked() -> None:
    error = _refused(date="1990-05-03(农历四月初十)")
    assert error.code == "tool.field_conflict" and error.details["agent_recovery"]["must_ask_user"] is True
    assert [str(option.get("value", option)) if isinstance(option, dict) else option for option in error.details["options"]] == ["1990-05-03", "1990-05-04"]
