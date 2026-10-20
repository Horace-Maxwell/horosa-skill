"""端点路由：哪些端点走 Python chart 服务、神数端点表、Java 日期格式的重试写法（只换写法不换值）。"""
from __future__ import annotations

from typing import Any

_JAVA_CHART_DATE_ENDPOINTS = {"/chart", "/chart12", "/chart13", "/india/chart"}
_JAVA_DATE_FALLBACK_ENDPOINTS = {
    "/nongli/time",
    "/jieqi/year",
    "/liureng/gods",
    "/liureng/runyear",
}
_PYTHON_CHART_ENDPOINTS = {
    "/chart",
    # 天星择日·征象搜索（上游 v3.7.0；挂在主 chart 服务，Java 侧无此路由）
    "/electionscan/scan",
    # 单时刻逐叶判读 + 条件类型自省（上游 v3.9.x R4；explainAt 参数与条件树报错自愈用）
    "/electionscan/explain",
    "/electionscan/conditiontypes",
    # 择日十技法（v3.10.0）的两个后端扫描成员。不登记的后果不是 404 而是**被路由去 Java 聚合层**，
    # 那边没有这条路由 → HTTP 500，而同样的请求体直接打 chart 服务是好的 —— 症状像「后端坏了」，
    # 实则是路由表漏登记（AGENTS §5 布线清单第 2 步）。
    "/qizhengelectionscan/scan",
    "/qizhengelectionscan/explain",
    "/qizhengelectionscan/conditiontypes",
    "/indiaelectionscan/scan",
    "/indiaelectionscan/explain",
    "/indiaelectionscan/conditiontypes",
    # 七政择日动盘三路由（批 I-1b；同挂主 chart 服务 webqizhengelectionsrv）
    "/qizhengelection/pan",
    "/qizhengelection/eclipses",
    "/qizhengelection/azimuthsearch",
    "/chart12",
    "/chart13",
    "/predict/persianchart",
    "/predict/solarreturn",
    "/predict/lunarreturn",
    "/predict/solararc",
    "/predict/givenyear",
    "/predict/profection",
    "/predict/pd",
    "/predict/pdchart",
    "/predict/zr",
    "/predict/dice",
    "/modern/relative",
    # 合盘关系量化打分（契合分数 + 顺畅/张力连接），与 /modern/relative 比较盘互补。
    "/astroextra/relative",
    "/india/chart",
    # 印度出生时间校正（批 I-2；独立端点，照 shadbalarange 骨架不进命盘缓存键）
    "/india/rectify",
    # ACG 落点/事件（批 I-4）
    "/location/acgpoint",
    "/location/acgevent",
    "/germany/midpoint",
    "/astroextra/harmonic",
    # 玄史知识库（只读 SQLite bundle，随 runtime 分发）：26 个检索/结构视图端点。
    "/xuanshi/summary",
    "/xuanshi/events",
    "/xuanshi/event",
    "/xuanshi/celestial",
    "/xuanshi/celestial_event",
    "/xuanshi/microchronology",
    "/xuanshi/decade_omens",
    "/xuanshi/celestial_term_profile",
    "/xuanshi/figures",
    "/xuanshi/figure",
    "/xuanshi/techniques",
    "/xuanshi/technique",
    "/xuanshi/celestial_terms",
    "/xuanshi/celestial_term",
    "/xuanshi/dynasties",
    "/xuanshi/dynasty",
    "/xuanshi/stories",
    "/xuanshi/story",
    "/xuanshi/channels",
    "/xuanshi/map",
    "/xuanshi/persons_graph",
    "/xuanshi/timeline",
    "/xuanshi/events_meta",
    "/xuanshi/facets",
    "/xuanshi/search",
    "/xuanshi/daily",
    "/astroextra/ephemeris",
    "/astroextra/draconic",
    "/astroextra/relocation",
    "/predict/agepoint",
    "/predict/dist",
    "/astroextra/jaynesprog",
    "/astroextra/progressions",
    "/astroextra/planetreturn",
    "/astroextra/analysis",
    # 世俗盘子盘群（新月/满月图、日月食判词、木土大合相、行星聚散指数）依赖的 astroextra 精算端点。
    "/astroextra/prenatal_syzygy",
    "/astroextra/eclipsedetail",
    "/astroextra/greatconj",
    # 批 I-3：行星周期（任意两星合冲时间轴）+ 日月返照年表
    "/astroextra/planetcycles",
    "/astroextra/returns",
    "/astroextra/barbault",
    "/geomancy/reading",
    # 占星地图（AstroCartoGraphy）：行星地理投影线精算端点。
    "/location/acg",
    "/predict/planetaryarc",
    "/jieqi/year",
    # 批 I-3：出生节气窗（BirthJieQi，八字起运窗同源）
    "/jieqi/birth",
    # 批 I-5：文本库三件（判词库/心易起卦/十六卦目录）
    "/cetian/texts",
    "/wangji/xinyi",
    "/geomancy/catalog",
    "/qimen/pan",
    "/taiyi/pan",
    "/jinkou/pan",
    # 神数 family (v2.5.x) — kentang mounts on the chart service (:8899), each returns a backend-built `snapshot`.
    "/wangji/pan",
    "/wuzhao/pan",
    "/taixuan/pan",
    "/jingjue/pan",
    "/shenyishu/pan",
    # 9 kinastro-* 神数
    "/shaozi/pan",
    "/tieban/pan",
    "/fendjing/pan",
    "/beiji/pan",
    "/nanji/pan",
    "/chunzi/pan",
    "/xianqin/pan",
    "/cetian/pan",
    "/qizhengkin/pan",
}


def _slash_date_prefix(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if len(value) < 10 or value[4] != "-" or value[7] != "-":
        return value
    return f"{value[:4]}/{value[5:7]}/{value[8:10]}{value[10:]}"


def _dash_date_prefix(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if len(value) < 10 or value[4] != "/" or value[7] != "/":
        return value
    return f"{value[:4]}-{value[5:7]}-{value[8:10]}{value[10:]}"


def _java_zone_hour(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if len(text) != 6 or text[0] not in "+-" or text[3] != ":":
        return value
    hours = text[1:3]
    minutes = text[4:6]
    if not (hours.isdigit() and minutes == "00"):
        return value
    signed = int(hours)
    if text[0] == "-":
        signed = -signed
    return str(signed)


def _java_chart_payload(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    if endpoint not in _JAVA_CHART_DATE_ENDPOINTS:
        return payload
    normalized = dict(payload)
    for key in ("date", "datetime"):
        if key in normalized:
            normalized[key] = _slash_date_prefix(normalized[key])
    return normalized


def _java_chart_payload_candidates(endpoint: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Payload variants `_call_remote` retries on a `200001 param error`, validated payload first.

    Each variant must describe the SAME chart — only the spelling changes (date separator, `+08:00` vs `8`, compact vs
    decimal coordinates, with / without gps fields) — because older desktop builds reachable in external mode
    (`HOROSA_SERVER_ROOT`) accept different spellings. 🔴 v0.41.1: two families used to retry with `abs(gpsLon)`,
    i.e. a western birth re-cast at an eastern longitude and returned `ok=True` (New York → Central Asia). No incident
    ever needed it; a live probe of all 110 techniques at three western-hemisphere places hit zero param errors.
    """
    first = _java_chart_payload(endpoint, payload)
    if endpoint not in _JAVA_CHART_DATE_ENDPOINTS and endpoint not in _JAVA_DATE_FALLBACK_ENDPOINTS:
        return [first]

    variants: list[dict[str, Any]] = []

    def add(candidate: dict[str, Any]) -> None:
        if candidate not in variants:
            variants.append(candidate)

    date_variants = [dict(first)]
    dashed = dict(first)
    slash = dict(first)
    for key in ("date", "datetime", "guaDate"):
        if key in dashed:
            dashed[key] = _dash_date_prefix(dashed[key])
        if key in slash:
            slash[key] = _slash_date_prefix(slash[key])
    if endpoint in _JAVA_CHART_DATE_ENDPOINTS:
        if dashed != first:
            date_variants.append(dashed)
    else:
        # Nongli/jieqi/liureng endpoints are less consistent across bundled
        # Java runtime builds. Keep the validated Xingque-style payload first,
        # then retry the slash date variant that older local backends accept.
        if slash != first:
            date_variants.append(slash)
        if dashed != first and dashed not in date_variants:
            date_variants.append(dashed)

    zone_hour = _java_zone_hour(first.get("zone"))
    zone_values = [first.get("zone")]
    if zone_hour != first.get("zone"):
        zone_values.append(zone_hour)

    for date_candidate in date_variants:
        for zone_value in zone_values:
            candidate = dict(date_candidate)
            if "zone" in candidate:
                candidate["zone"] = zone_value
            add(candidate)

            gps_lat = candidate.get("gpsLat")
            gps_lon = candidate.get("gpsLon")
            if isinstance(gps_lat, (int, float)) and isinstance(gps_lon, (int, float)):
                # Some Windows chart-runtime builds reject compact `31n13`/`121e28`
                # before falling through to gpsLat/gpsLon. Try decimal-only
                # variants so user-facing clients do not have to hand-edit payloads.
                gps_only = {key: value for key, value in candidate.items() if key not in {"lat", "lon"}}
                add(gps_only)

                decimal_lat_lon = dict(candidate)
                decimal_lat_lon["lat"] = gps_lat
                decimal_lat_lon["lon"] = gps_lon
                add(decimal_lat_lon)

            without_gps = {key: value for key, value in candidate.items() if key not in {"gpsLat", "gpsLon"}}
            add(without_gps)
    return variants


def _chart_server_endpoint(endpoint: str) -> str:
    return "/" if endpoint == "/chart" else endpoint


_SHENSHU_ENDPOINTS = {
    # 5 standalone engines
    "wangji": "/wangji/pan",
    "wuzhao": "/wuzhao/pan",
    "taixuan": "/taixuan/pan",
    "jingjue": "/jingjue/pan",
    "shenyishu": "/shenyishu/pan",
    # 9 kinastro-* engines (shared kinastro engine)
    "shaozi": "/shaozi/pan",
    "tieban": "/tieban/pan",
    "fendjing": "/fendjing/pan",
    "beiji": "/beiji/pan",
    "nanji": "/nanji/pan",
    "chunzi": "/chunzi/pan",
    "xianqin": "/xianqin/pan",
    "cetian": "/cetian/pan",
    "qizhengkin": "/qizhengkin/pan",
}
