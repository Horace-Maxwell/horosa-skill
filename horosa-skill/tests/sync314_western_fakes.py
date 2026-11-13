"""[盘面细节]（上游 v3.14.0）的离线替身：FakeClient 的 `/astroextra/chartdetails` 与 FakeJsClient 的 `chart_details`。

内容是真的：`tests/fixtures/sync314_western_chart_details.json.gz` 是上游自己的全表金标（astropy/tests/data/golden_chart_details.json，
30 张表）+ vendored `buildChartDetailsText` 排出的正文。桩只管形状——值级真相归 npm selfcheck 金标与
`tests/test_sync314_western_chart_details.py` 的真 JS / live 用例。

后端的「认不出的口径值静默回缺省、并回显实际用的那一档」这条行为桩照做（`fake_chart_details_response`），
service 的回显守卫才有东西可守。
"""
from __future__ import annotations

import copy
import gzip
import json
from functools import cache
from pathlib import Path
from typing import Any

FIXTURE = Path(__file__).parent / "fixtures" / "sync314_western_chart_details.json.gz"
DEFAULT_CASE = "seattle-night"

# 后端各口径的合法值（astrostudy/chart_details.py::_details 与 chart_details_more.py 的 LUNAR_METHODS / MUNDO_SYSTEMS /
# MIDPOINT_COORDS）；认不出 → 回缺省。请求键 → (回显路径, 缺省, 合法值)。与 skill 的词表**分开写**：这里是「后端怎么读」。
_BACKEND_KNOBS: dict[str, tuple[tuple[str, ...], str, tuple[str, ...]]] = {
    "detailFaces": (("faces",), "chaldean", ("chaldean", "element")),
    "variant": (("variant",), "improved", ("improved", "classic")),
    "lunarMethod": (("lunarDays", "method"), "traditional", ("traditional", "tithi", "equal", "angle", "centered")),
    "mundoSystem": (("inMundo", "system"), "proportional", (
        "proportional", "placidus", "koch", "porphyry", "regiomontanus", "campanus", "alcabitius", "meridian", "horizontal",
        "topocentric", "morinus", "krusinski")),
    "midpointCoord": (("midpoints", "coord"), "ecliptic", ("ecliptic", "mundane", "ra", "azimuth", "declination", "latitude")),
}
# 页面设置键 → 请求键（上游 chartDetailRequestFields 的映射；桩里独立再写一遍，不引 skill 的那份）。
_SETTING_TO_REQUEST = {
    "detailFaces": "detailFaces", "detailVariant": "variant", "detailLunar": "lunarMethod",
    "detailMundo": "mundoSystem", "detailMidpoint": "midpointCoord",
}
_SETTING_DEFAULTS = {
    "detailFaces": "chaldean", "detailVariant": "improved", "detailLunar": "traditional",
    "detailMundo": "proportional", "detailMidpoint": "ecliptic",
}


@cache
def chart_details_fixture() -> dict[str, Any]:
    with gzip.open(FIXTURE, "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def fake_chart_details_response(payload: dict[str, Any]) -> dict[str, Any]:
    """后端 /astroextra/chartdetails 的替身：金标全表 + 按请求回显口径（认不出的值回缺省，与真后端同）。"""
    result = copy.deepcopy(chart_details_fixture()["goldens"][DEFAULT_CASE])
    for request_key, (path, default, allowed) in _BACKEND_KNOBS.items():
        value = str(payload.get(request_key)) if payload.get(request_key) not in (None, "") else default
        node = result
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = value if value in allowed else default
    return result


def fake_chart_details_js(payload: dict[str, Any]) -> dict[str, Any]:
    """JS 工具 chart_details 的替身（真工具见 horosa-core-js/src/tools/chartDetails.js）。"""
    if payload.get("action") == "catalog":
        raise AssertionError("offline stub does not serve the chart_details catalog; use the real JS tool")
    given = payload.get("settings") if isinstance(payload.get("settings"), dict) else {}
    settings = {key: given.get(key) if given.get(key) not in (None, "") else default for key, default in _SETTING_DEFAULTS.items()}
    request_fields = {
        _SETTING_TO_REQUEST[key]: value for key, value in settings.items() if value != _SETTING_DEFAULTS[key]
    }
    out: dict[str, Any] = {"text": "", "request_fields": request_fields, "settings": settings}
    result = payload.get("result")
    if result is None:
        return out
    if not isinstance(result, dict) or not isinstance(result.get("persian"), list):
        return {**out, "error": "no_result"}
    out["text"] = chart_details_fixture()["texts"][DEFAULT_CASE]
    tables = [str(item) for item in (payload.get("tables") or [])]
    if tables:
        out["tables"] = {name: {"label": name, "data": result.get(name)} for name in tables}
    return out
