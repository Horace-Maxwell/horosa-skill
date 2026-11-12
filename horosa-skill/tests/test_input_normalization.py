import pytest

from horosa_skill.errors import ToolValidationError
from horosa_skill.input_normalization import normalize_request_payload


def test_normalize_request_payload_pads_date_time_and_zone_fields() -> None:
    normalized = normalize_request_payload(
        {
            "date": "2028/4/6",
            "time": "9:3",
            "zone": "8",
            "datetime": "2031-4-6 9:3",
            "guaDate": "2020-4-6",
            "guaTime": "5:6",
            "dirZone": "+8",
            "guaZone": "0800",
        }
    )

    assert normalized["date"] == "2028-04-06"
    assert normalized["time"] == "09:03:00"
    assert normalized["zone"] == "+08:00"
    assert normalized["datetime"] == "2031-04-06 09:03:00"
    assert normalized["guaDate"] == "2020-04-06"
    assert normalized["guaTime"] == "05:06:00"
    assert normalized["dirZone"] == "+08:00"
    assert normalized["guaZone"] == "+08:00"


def test_normalize_request_payload_pads_decimal_coordinate_birth_inputs() -> None:
    normalized = normalize_request_payload(
        {
            "lat": "31.2167",
            "lon": "121.4667",
            "gpsLat": None,
            "gpsLon": None,
        }
    )

    assert normalized["lat"] == "31n13"
    assert normalized["lon"] == "121e28"
    assert normalized["gpsLat"] == 31.2167
    assert normalized["gpsLon"] == 121.4667


def test_normalize_request_payload_coordinate_formats_full_compat() -> None:
    # 坐标格式全兼容哨兵：十进制串（含带号/留白）、compact DMS、数值直通 —— 全部归一到
    # compact + gps 十进制；科学计数暗雷（121e30 是东经 121°30′ 不是 1.21e+32）由 compact
    # 分支先行匹配锁死。带秒的罗盘串（12W30:00）v0.50.0 起就地读懂；方向字母与字段不符（纬度写 W）拒绝——
    # 旧断言「原样透传后端」恰是缺陷：后端把 12W30:00 当纬度读，盘悄悄落在别处。
    n = normalize_request_payload({"lat": "-31.2", "lon": "+121.5"})
    assert n["lat"] == "31s12" and n["lon"] == "121e30"
    assert n["gpsLat"] == -31.2 and n["gpsLon"] == 121.5

    n = normalize_request_payload({"lat": " 39.9 ", "lon": "116.4"})
    assert n["lat"] == "39n54" and n["lon"] == "116e24"

    n = normalize_request_payload({"lat": 26.07, "lon": 0})
    assert n["lat"] == "26n04" and n["lon"] == "0e00"

    n = normalize_request_payload({"lon": "121e30"})
    assert n["lon"] == "121e30"
    assert n["gpsLon"] == 121.5  # 绝不是 1.21e+32

    n = normalize_request_payload({"lon": "12W30:00"})
    assert n["lon"] == "12w30" and n["gpsLon"] == -12.5
    with pytest.raises(ToolValidationError) as caught:
        normalize_request_payload({"lat": "12W30:00"})
    assert caught.value.code == "tool.invalid_coordinate"


def test_normalize_request_payload_gender_labels_to_int() -> None:
    # 性别标签归一为 0(女)/1(男)：字符串标签统一，int/None/未识别值不动。八字链下游按 0/1
    # 判大运顺逆；若 '女' 原样进 JS 会 Number()→NaN→恒判男 → 女命方向反转，故必须先归一。
    assert normalize_request_payload({"gender": "女"})["gender"] == 0
    assert normalize_request_payload({"gender": "Female"})["gender"] == 0
    assert normalize_request_payload({"gender": "F"})["gender"] == 0
    assert normalize_request_payload({"gender": "坤"})["gender"] == 0
    assert normalize_request_payload({"gender": "男"})["gender"] == 1
    assert normalize_request_payload({"gender": "male"})["gender"] == 1
    assert normalize_request_payload({"gender": "乾"})["gender"] == 1
    assert normalize_request_payload({"gender": 0})["gender"] == 0
    assert normalize_request_payload({"gender": 1})["gender"] == 1
    assert normalize_request_payload({"gender": None})["gender"] is None
    # v0.50.0：认不出的性别拒绝（旧断言「原样保留」= 下游 Number('其他') → NaN → 恒按男命排，正是要修的缺陷）。
    with pytest.raises(ToolValidationError) as caught:
        normalize_request_payload({"gender": "其他"})
    assert caught.value.code == "tool.invalid_gender"


def test_normalize_request_payload_converts_iana_timezones_from_event_datetime() -> None:
    normalized = normalize_request_payload(
        {
            "date": "2026-05-18",
            "time": "13:14",
            "zone": "America/Los_Angeles",
            "datetime": "2026-12-01 09:00",
            "dirZone": "America/Los_Angeles",
            "guaDate": "2026-01-15",
            "guaTime": "08:30",
            "guaZone": "America/New_York",
        }
    )

    assert normalized["zone"] == "-07:00"
    assert normalized["dirZone"] == "-08:00"
    assert normalized["guaZone"] == "-05:00"


def test_normalize_request_payload_refuses_iana_zone_when_datetime_is_missing() -> None:
    # v0.50.0：没有日期时刻就换算不了偏移；旧行为把 IANA 名原样交给后端（后端拒或按别的口径读）。
    with pytest.raises(ToolValidationError) as caught:
        normalize_request_payload({"zone": "America/Los_Angeles"})
    assert caught.value.code == "tool.invalid_zone"


def test_normalize_request_payload_does_not_crash_on_calendar_invalid_date_with_iana_zone() -> None:
    # Regression: the date/time regexes accept digit-shaped but calendar-invalid values
    # (e.g. 2020-02-30). With an IANA zone name this used to reach datetime() and raise
    # ValueError straight out of normalization. It must degrade, not crash.
    # v0.50.0: the nonexistent date is now refused as such (one issue, for `date`), not passed through.
    with pytest.raises(ToolValidationError) as caught:
        normalize_request_payload({"zone": "Asia/Shanghai", "date": "2020-02-30", "time": "12:00:00"})
    assert caught.value.code == "tool.invalid_date"
    assert [item["field"] for item in caught.value.details["fields"]] == ["date"]


def test_normalize_request_payload_normalizes_utc_designators_to_zero_offset() -> None:
    for token in ("Z", "z", "UTC", "GMT", "utc"):
        normalized = normalize_request_payload({"zone": token})
        assert normalized["zone"] == "+00:00", token
    # UTC with an explicit offset must still parse, not collapse to +00:00.
    assert normalize_request_payload({"zone": "UTC+8"})["zone"] == "+08:00"
    assert normalize_request_payload({"zone": "GMT+05:30"})["zone"] == "+05:30"


def test_per_field_prompt_names_the_technique(tmp_path) -> None:
    """逐字段追问开头点名技法（显示名 + 注册表键）：dispatch / 合参一次跑几个技法时，「zone 认不出」得知道是哪一个的。"""
    from fakes import FakeClient, FakeJsClient

    from horosa_skill.config import Settings
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService

    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payload = {"date": "1990-05-03", "time": "08:00:00", "zone": "火星时间", "lat": "31n13", "lon": "121e28",
               "agent_confirmed_settings": True}
    with pytest.raises(ToolValidationError) as caught:
        service.run_tool("chart", payload, save_result=False)
    error = caught.value
    assert str(error).startswith("本命盘（chart）的输入： / Input for chart:"), str(error)
    assert error.details["agent_recovery"]["prompt_to_user"].startswith("本命盘（chart）的输入")
    assert error.details["tool"] == "chart"
    # 不带技法名的归一（门面 / 共享模型）照旧不加开头。
    with pytest.raises(ToolValidationError) as bare:
        normalize_request_payload({"zone": "火星时间"})
    assert not str(bare.value).startswith("Input for") and "tool" not in bare.value.details
