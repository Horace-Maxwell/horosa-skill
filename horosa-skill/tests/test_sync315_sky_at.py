"""上游 v3.15.0 AI 工具 sky_at（天文馆取数）在 skill 的接法：门面 horosa_sky_at。

- 请求体照上游 skyAt.run() 逐键发 /planetarium/state（天文馆同一后端、纯天文口径）；
- 正文跑上游 skyStateText 原函数（报告盘图 bundle 的 app-text 通道 sky_state），skill 不手抄排版；
- 桩只供后端回包的形状，期望值按上游函数的文字规则（方位自正南起 → 换成自正北、两位小数、按 bodies 次序）独立写出。
"""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeClient
from test_local_js_tools import make_service, requires_chart

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.api.sky import SKY_BODIES

STATE = {
    "observer": {"date": "2026/11/23", "time": "21:00:00", "zone": "+08:00", "lat": "39n54", "lon": "116e24", "locationName": "北京"},
    "sky": {"mode": "night", "sunAltitude": -46.913, "moonPhase": {"phaseName": "望", "illumination": 0.983, "ageDays": 13.46}},
    "bodies": [
        {"id": "Sun", "azimuth": 103.21, "altitudeAppa": -46.91, "altitudeTrue": -46.912, "ra": 239.12, "decl": -20.41,
         "zodiacSign": "射手", "zodiacDegree": 1.25, "aboveHorizon": False,
         "riseSet": {"rise": {"time": "07:09:25"}, "transit": {"time": "12:00:42"}, "set": {"time": "16:51:39"}}},
        {"id": "Saturn", "azimuth": 8.46, "altitudeAppa": 50.66, "altitudeTrue": 50.65, "ra": 8.57, "decl": 0.85,
         "zodiacSign": "白羊", "zodiacDegree": 8.2, "mag": 0.9, "aboveHorizon": True,
         "riseSet": {"rise": {"time": "14:33:55"}, "transit": None, "set": None}},
        {"id": "North Node", "azimuth": 49.6, "altitudeAppa": 21.44, "altitudeTrue": 21.4, "ra": 327.17, "decl": -13.23,
         "zodiacSign": "水瓶", "zodiacDegree": 24.88, "aboveHorizon": True},
    ],
    "stars": {
        "fixed": [{"id": "Aldebaran", "name": "毕宿五", "azimuth": 280.0, "altitudeAppa": 40.0, "ra": 68.98, "decl": 16.5, "mag": [0.85]},
                  {"id": "Antares", "name": "心宿二", "azimuth": 100.0, "altitudeAppa": -30.0, "ra": 247.35, "decl": -26.43, "mag": 1.06}],
        "catalog": [{"id": "HR2491", "name": "Sirius", "azimuth": 0.0, "altitudeAppa": -5.0, "ra": 101.29, "decl": -16.72, "mag": -1.46, "spectralClass": "A1"},
                    {"id": "HR7001", "name": "Vega", "azimuth": 123.78, "altitudeAppa": 20.87, "ra": 279.23, "decl": 38.78, "mag": 0.03, "spectralClass": "A0"}],
    },
}


class SkyClient(FakeClient):
    def __init__(self, state: Any = None) -> None:
        super().__init__()
        self.state = copy.deepcopy(STATE) if state is None else state
        self.sky_requests: list[dict] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/planetarium/state":
            self.sky_requests.append(copy.deepcopy(payload))
            return copy.deepcopy(self.state)
        return super().call(endpoint, payload)


def _service(tmp_path: Path, client: SkyClient) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings))  # 真 JS 客户端（bundle）


BASE = {"date": "2026-11-23", "time": "21:00", "zone": "+08:00", "lat": "39n54", "lon": "116e24"}


def test_request_body_is_the_upstream_run_body(tmp_path) -> None:
    client = SkyClient()
    svc = _service(tmp_path, client)
    svc.sky_at({**BASE})
    svc.sky_at({**BASE, "brightestStars": 2})
    plain, bright = client.sky_requests
    # skyAt.run()：日期写 /、时刻补秒、天文馆口径（hsys 1 / 回归黄道 / 无岁差制 / 不倒置）、恒带升中落；要亮星才带 9000 星表。
    assert plain == {"date": "2026/11/23", "time": "21:00:00", "zone": "+08:00", "lat": "39n54", "lon": "116e24",
                     "gpsLat": 39.9, "gpsLon": 116.4, "hsys": 1,
                     "zodiacal": 0, "siderealAyanamsa": "", "doubingSu28": 0, "southchart": 0, "starLimit": 0, "includeRiseSet": True}
    assert bright["starLimit"] == 9000


def test_content_is_the_upstream_sky_text(tmp_path) -> None:
    r = _service(tmp_path, SkyClient()).sky_at({**BASE, "bodies": ["saturn", "north node", "Sun"], "fixedStars": True,
                                                "brightestStars": 1, "visibleOnly": True})
    lines = r["content"].split("\n")
    assert lines[:3] == [
        "■ 观测",
        "时间:2026/11/23 21:00:00(+08:00)· 地点:39n54 116e24 北京",
        "天光:夜(太阳高度 -46.91°)· 月相:望,照亮 98.3%,月龄 13.5 日",
    ]
    table = [ln for ln in lines if ln.startswith("| ") and "---" not in ln]
    # 次序随 bodies（大小写 / 空格宽松读成上游名）；方位 = 后端自正南起 + 180 取模（自正北顺时针）；缺星等 / 缺升落写 —。
    assert table[1].startswith("| 土 | 188.46° | 50.66° | 50.65° | 8.57° | 0.85° | 白羊 8.20° | 0.90 | 地平上 | 升 14:33:55 / 中天 — / 落 不落 |")
    assert table[2].startswith("| 北交 | 229.60° | 21.44° | 21.40° |") and table[2].endswith("| 地平上 | — |")
    assert table[3].startswith("| 日 | 283.21° | -46.91° |") and "| — | 地平下 | 升 07:09:25 / 中天 12:00:42 / 落 16:51:39 |" in table[3]
    # 恒星组只列地平上的（visibleOnly）；亮星按星等取前 1（地平下的天狼星先被滤掉）。
    assert "| 毕宿五(Aldebaran) | 100.00° | 40.00° | 68.98° | 16.50° | 0.85 |" in lines and not any("心宿二" in ln for ln in lines)
    assert "■ 亮星前 1 颗(地平上)" in lines and any(ln.startswith("| ") and "| 303.78° | 20.87° |" in ln and "| A0 |" in ln for ln in lines)
    assert lines[-1] == "方位自正北顺时针;视高度含大气折射;升中落为当地当日。"
    assert (r["date"], r["time"], r["zone"]) == ("2026-11-23", "21:00:00", "+08:00") and "assumptions" not in r


def test_decimal_coordinates_and_iana_zone_are_normalized_like_the_mcp_layer(tmp_path) -> None:
    client = SkyClient()
    _service(tmp_path, client).sky_at({"date": "2026-11-23", "time": "21:00", "lat": 39.9042, "lon": 116.4074, "zone": "Asia/Shanghai"})
    req = client.sky_requests[0]
    assert (req["lat"], req["lon"], req["zone"], req["gpsLat"], req["gpsLon"]) == ("39n54", "116e24", "+08:00", 39.9042, 116.4074)


def test_missing_time_is_noon_and_said(tmp_path) -> None:
    client = SkyClient()
    r = _service(tmp_path, client).sky_at({k: v for k, v in BASE.items() if k != "time"})
    assert client.sky_requests[0]["time"] == "12:00:00" and "12:00:00" in r["assumptions"][0]


def test_sky_bodies_match_the_upstream_list_in_the_bundle(tmp_path) -> None:
    runs = _service(tmp_path, SkyClient()).js_client.run_app_texts([{"name": "sky_bodies"}])
    assert runs is not None and runs[0]["ok"], runs
    assert tuple(runs[0]["value"]) == SKY_BODIES


@pytest.mark.parametrize(
    ("extra", "code", "needle"),
    [
        ({"bodies": ["Sun", "Chiron"]}, "sky.invalid_payload", "Chiron"),
        ({"bodies": []}, "sky.invalid_payload", "bodies"),
        ({"brightestStars": 61}, "sky.invalid_payload", "brightestStars"),
        ({"time": "25:00"}, "tool.invalid_time", "25:00"),
        ({"date": "2026/13/01"}, "tool.invalid_date", "2026/13/01"),
        ({"lat": None}, "sky.location_missing", "lat"),
    ],
)
def test_bad_inputs_are_refused_before_any_request(tmp_path, extra: dict, code: str, needle: str) -> None:
    from horosa_skill.errors import ToolValidationError

    client = SkyClient()
    with pytest.raises(ToolValidationError) as err:
        _service(tmp_path, client).sky_at({**BASE, **extra})
    assert err.value.code == code and needle in json.dumps({"m": str(err.value), "d": err.value.details}, ensure_ascii=False)
    assert client.sky_requests == []


def test_backend_error_envelope_and_missing_bundle_are_loud(tmp_path, monkeypatch) -> None:
    from horosa_skill.errors import ToolTransportError

    with pytest.raises(ToolTransportError) as err:
        _service(tmp_path, SkyClient(state={"err": "planetarium param error"})).sky_at({**BASE})
    assert err.value.code == "sky.backend_failed" and err.value.details["backend_error"] == "planetarium param error"
    svc = _service(tmp_path, SkyClient())
    monkeypatch.setattr(svc.js_client, "run_app_texts", lambda calls: None)
    with pytest.raises(ToolTransportError) as err:
        svc.sky_at({**BASE})
    assert err.value.code == "sky.render_unavailable"


def test_mcp_facade_is_listed_ungated_and_says_ok(tmp_path) -> None:
    from horosa_skill.surfaces.mcp_schema import UNGATED_FACADES
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    svc = HorosaSkillService(settings, client=SkyClient(), store=MemoryStore(settings))
    mcp = create_mcp_server(svc, settings)
    names = [t.name for t in asyncio.run(mcp.list_tools())]
    assert "horosa_sky_at" in names and "horosa_sky_at" in UNGATED_FACADES
    result = asyncio.run(mcp.call_tool("horosa_sky_at", {**BASE, "bodies": ["Saturn"]}))
    payload = getattr(result, "structuredContent", None) or json.loads(result.content[0].text)
    assert payload["ok"] is True and payload["content"].startswith("■ 观测") and "| 土 |" in payload["content"]


@requires_chart
def test_live_sky_state_from_the_vendored_backend(tmp_path) -> None:
    r = make_service(tmp_path).sky_at({**BASE, "brightestStars": 3, "visibleOnly": True})
    lines = r["content"].split("\n")
    assert lines[0] == "■ 观测" and lines[2].startswith("天光:夜(太阳高度 -")
    rows = {ln.split(" | ")[0][2:]: ln for ln in lines if ln.startswith("| ") and "---" not in ln}
    assert set(rows) >= {"日", "月", "土", "北交", "南交"}
    # 21:00 的北京：太阳在地平下、满月前后的月亮在地平上（天文常识级判据，不抄后端数）。
    assert "地平下" in rows["日"] and "地平上" in rows["月"]
    assert "■ 亮星前 3 颗(地平上)" in lines
