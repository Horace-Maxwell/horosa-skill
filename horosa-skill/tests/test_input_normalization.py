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


def test_normalize_request_payload_leaves_unknown_iana_zone_when_datetime_is_missing() -> None:
    normalized = normalize_request_payload({"zone": "America/Los_Angeles"})

    assert normalized["zone"] == "America/Los_Angeles"


def test_normalize_request_payload_does_not_crash_on_calendar_invalid_date_with_iana_zone() -> None:
    # Regression: the date/time regexes accept digit-shaped but calendar-invalid values
    # (e.g. 2020-02-30). With an IANA zone name this used to reach datetime() and raise
    # ValueError straight out of normalization. It must degrade, not crash.
    normalized = normalize_request_payload(
        {"zone": "Asia/Shanghai", "date": "2020-02-30", "time": "12:00:00"}
    )

    assert normalized["date"] == "2020-02-30"
    # Could not derive a reference instant, so the IANA name is left for the backend to reject.
    assert normalized["zone"] == "Asia/Shanghai"


def test_normalize_request_payload_normalizes_utc_designators_to_zero_offset() -> None:
    for token in ("Z", "z", "UTC", "GMT", "utc"):
        normalized = normalize_request_payload({"zone": token})
        assert normalized["zone"] == "+00:00", token
    # UTC with an explicit offset must still parse, not collapse to +00:00.
    assert normalize_request_payload({"zone": "UTC+8"})["zone"] == "+08:00"
    assert normalize_request_payload({"zone": "GMT+05:30"})["zone"] == "+05:30"
