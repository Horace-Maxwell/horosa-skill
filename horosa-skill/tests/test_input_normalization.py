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
