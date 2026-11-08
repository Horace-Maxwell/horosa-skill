"""地名 → 坐标 + 时区（v0.48.0）：horosa_place_search 门面与技法载荷的 `place` 键。

金标 = **上游星阙源本身**在 node 里跑出来的（tests/fixtures/place_search/harness.mjs + upstream_hooks.mjs：上游 bundler 写法源码
只读加载；tz-lookup 用 horosa-core-js/node_modules 那份，与上游 package-lock 同版本同 integrity），存成
tests/fixtures/place_search_upstream.json。离线测试拿**同一段**脚本跑 vendored 副本，输出必须与夹具逐值相同；
`test_fixture_matches_upstream` 在 HOROSA_SOURCE_ROOT 可用时重跑上游，夹具与上游漂移即红。
负向对照（把被测的那一行改回去 → 必红）逐条写在各测试的 docstring 里，均实际跑过。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.errors import ToolTransportError, ToolValidationError
from horosa_skill.input_normalization import _TZ_RULE_OVERRIDES, _normalize_iana_zone_value
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

PKG = Path(__file__).resolve().parents[1]
CORE_JS = PKG / "horosa-core-js"
VENDOR = CORE_JS / "src" / "vendor"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "place_search"
GOLDEN = Path(__file__).resolve().parent / "fixtures" / "place_search_upstream.json"
_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
UPSTREAM_SRC = Path(_ROOT) / "Horosa-Web" / "astrostudyui" / "src" if _ROOT else None
TZ_LOOKUP = CORE_JS / "node_modules" / "tz-lookup" / "tz.js"

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
requires_engine = pytest.mark.skipif(
    shutil.which("node") is None or not TZ_LOOKUP.is_file(),
    reason="node + horosa-core-js node_modules (npm ci --omit=dev) required",
)
requires_upstream = pytest.mark.skipif(
    UPSTREAM_SRC is None or not (UPSTREAM_SRC / "utils" / "aiTools" / "normalize" / "place.js").is_file() or not TZ_LOOKUP.is_file(),
    reason="HOROSA_SOURCE_ROOT (Horosa-Public checkout) + core-js node_modules required",
)

# 固定查询集：简体 / 全拼 / 首字母 / 繁体 / 英文（含重音与去空格）/ 地区 / 「省+市」/ 找不到。
CASES: dict[str, Any] = {
    "search": [
        "北京", "上海", "朝阳", "xian", "bj", "wlmq", "beijing", "shanghai", "臺北", "烏魯木齊", "澳門", "New York",
        "newyork", "London", "São Paulo", "saopaulo", "Reykjavík", "悉尼", "辽宁朝阳", "广东", "zz-no-such-place",
    ],
    "resolveDate": "1988-07-01",
    "resolve": [
        "上海", "朝阳", "北京", "New York", "辽宁朝阳", "乌鲁木齐", "xian", "悉尼", "臺北", "Vancouver", "温哥华", "London",
        "zz-no-such-place",
    ],
    # (地名, 日期)：北京 1986–1991 夏令时 / 新疆统一北京时间前后 / 纽约冬夏 / 南半球悉尼冬夏 / TZ_RULE_OVERRIDES 生效之后。
    "zones": [
        ["北京", "1988-07-01"], ["北京", "1995-07-01"], ["乌鲁木齐", "2000-01-01"], ["乌鲁木齐", "1940-01-01"],
        ["New York", "2026-01-15"], ["New York", "2026-07-15"], ["悉尼", "2026-01-15"], ["悉尼", "2026-07-15"],
        ["温哥华", "2026-07-15"], ["温哥华", "2027-01-15"], ["卡萨布兰卡", "2026-12-01"], ["埃德蒙顿", "2027-01-15"],
    ],
    # (IANA, 日期)：offsetForZoneAtDate / isDstActiveAt 直接对拍（覆盖表每一条都在内）。
    "offsets": [
        ["Asia/Shanghai", "1988-07-01"], ["Asia/Shanghai", "1995-07-01"], ["Asia/Urumqi", "1940-01-01"],
        ["America/New_York", "2026-01-15"], ["America/New_York", "2026-07-15"], ["Australia/Sydney", "2026-01-15"],
        ["Australia/Sydney", "2026-07-15"], ["America/Vancouver", "2026-10-31"], ["America/Vancouver", "2027-01-15"],
        ["America/Edmonton", "2027-01-15"], ["Africa/Casablanca", "2026-09-19"], ["Africa/Casablanca", "2026-12-01"],
        ["Africa/El_Aaiun", "2027-03-01"], ["Europe/London", "2026-07-15"],
    ],
}


def _run_harness(tmp_path: Path, modules: dict[str, Path], *, hooks: dict[str, Any] | None = None) -> dict[str, Any]:
    config: dict[str, Any] = {"modules": {k: v.resolve().as_uri() for k, v in modules.items()}, "cases": CASES}
    if hooks:
        config.update(hooks)
    path = tmp_path / "harness_config.json"
    path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    completed = subprocess.run(
        ["node", str(FIXTURES / "harness.mjs"), str(path)], capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr[-4000:])
    return json.loads(completed.stdout)


def _vendored_outputs(tmp_path: Path) -> dict[str, Any]:
    return _run_harness(tmp_path, {
        "cityMatch": VENDOR / "place" / "cityMatch.js",
        "cities": VENDOR / "place" / "data" / "cities.json",
        "full": VENDOR / "place" / "data" / "citiesFull.json",
        "fold": VENDOR / "place" / "data" / "cityTradSimpMap.json",
        "place": VENDOR / "place" / "place.js",
        "timezone": VENDOR / "utils" / "timezone.js",
    })


def _upstream_outputs(tmp_path: Path) -> dict[str, Any]:
    assert UPSTREAM_SRC is not None
    return _run_harness(tmp_path, {
        "cityMatch": UPSTREAM_SRC / "components" / "amap" / "cityMatch.js",
        "cities": UPSTREAM_SRC / "data" / "cities.json",
        "full": UPSTREAM_SRC / "data" / "citiesFull.json",
        "fold": UPSTREAM_SRC / "data" / "cityTradSimpMap.json",
        "place": UPSTREAM_SRC / "utils" / "aiTools" / "normalize" / "place.js",
        "timezone": UPSTREAM_SRC / "utils" / "timezone.js",
    }, hooks={
        "hooks": (FIXTURES / "upstream_hooks.mjs").resolve().as_uri(),
        "hookData": {"tzLookupUrl": TZ_LOOKUP.resolve().as_uri(), "upstreamRoot": UPSTREAM_SRC.resolve().as_uri()},
    })


def _golden() -> dict[str, Any]:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
    )


def _service(tmp_path: Path, js_client: Any = None) -> HorosaSkillService:
    settings = _settings(tmp_path)
    return HorosaSkillService(settings, store=MemoryStore(settings), js_client=js_client)


# ── 夹具 = 上游源；vendored 副本 = 夹具 ─────────────────────────────────────────────────────────────


@requires_upstream
def test_fixture_matches_upstream(tmp_path: Path) -> None:
    """夹具就是上游源在 node 里跑出来的：上游改了城市库 / 评分 / 时区规则，这里红，按 re-vendor Runbook 同步后重写夹具。"""
    assert _upstream_outputs(tmp_path) == _golden()["outputs"]


@requires_engine
def test_vendored_city_match_and_zones_equal_upstream(tmp_path: Path) -> None:
    """同一段脚本跑 vendored cityMatch / place / timezone 与城市库：候选、评分、顺序、坐标串、时区逐值等于上游。
    负向对照：把 vendored cityMatch.js 的同档排序（按名称长度）去掉 → search 段红；把 vendored timezone.js 的
    'America/Vancouver' 覆盖删掉 → zones / offsets 段红（均实跑过）。"""
    vendored = _vendored_outputs(tmp_path)
    golden = _golden()["outputs"]
    for section in ("search", "resolve", "zones", "offsets"):
        assert vendored[section] == golden[section], section


def test_golden_pins_the_cases_the_task_names() -> None:
    """夹具里的值是上游算的；这里只确认用例确实覆盖到了要钉的现象（防止夹具换了个没有意义的日期还照绿）。"""
    zones = {(z["query"], z["date"]): z for z in _golden()["outputs"]["zones"]}
    assert zones[("北京", "1988-07-01")]["place"]["zone"] == "+09:00" and zones[("北京", "1988-07-01")]["dstAware"]["dst"] is True
    assert zones[("北京", "1995-07-01")]["place"]["zone"] == "+08:00"
    assert zones[("乌鲁木齐", "2000-01-01")]["place"]["advisory"] == "cn-unified"
    assert zones[("乌鲁木齐", "1940-01-01")]["place"].get("advisory") is None
    assert zones[("乌鲁木齐", "2000-01-01")]["place"]["zone"] != zones[("乌鲁木齐", "1940-01-01")]["place"]["zone"]
    assert zones[("New York", "2026-01-15")]["place"]["zone"] != zones[("New York", "2026-07-15")]["place"]["zone"]
    sydney_jan, sydney_jul = zones[("悉尼", "2026-01-15")], zones[("悉尼", "2026-07-15")]
    assert sydney_jan["dstAware"]["dst"] is True and sydney_jul["dstAware"]["dst"] is False  # 南半球：一月是夏令时
    assert zones[("温哥华", "2027-01-15")]["place"]["zone"] == "-07:00"  # TZ_RULE_OVERRIDES：2026-11-01 起永久 -07
    resolve = _golden()["outputs"]["resolve"]
    assert resolve["朝阳"]["resolved"] is False and len(resolve["朝阳"]["candidates"]) > 1
    assert resolve["上海"]["confidence"] == "high"
    assert resolve["zz-no-such-place"]["code"] == "E_PLACE_NOT_FOUND"


def test_vendored_timezone_override_table_is_the_python_copy() -> None:
    """input_normalization._TZ_RULE_OVERRIDES 是 vendored utils/timezone.js TZ_RULE_OVERRIDES 的逐条抄本（vendored 文件由
    revendor --from-manifest 锁到上游）。负向对照：删掉 Python 表的 Africa/El_Aaiun 一条 → 红（实跑过）。"""
    text = (VENDOR / "utils" / "timezone.js").read_text(encoding="utf-8")
    block = text[text.index("const TZ_RULE_OVERRIDES = {"): text.index("};", text.index("const TZ_RULE_OVERRIDES = {"))]
    upstream = {
        zone: tuple(((int(y), int(m), int(d)), offset) for y, m, d, offset in re.findall(r"since:\s*'(\d{4})-(\d{2})-(\d{2})',\s*offset:\s*'([^']+)'", rules))
        for zone, rules in re.findall(r"'([A-Za-z_]+/[A-Za-z_]+)':\s*\[(.*?)\]", block, re.S)
    }
    assert len(upstream) == 4
    assert upstream == _TZ_RULE_OVERRIDES


def test_python_iana_offsets_equal_upstream_offset_for_zone_at_date() -> None:
    """本仓的 IANA 名换算（_normalize_iana_zone_value，zone="America/Vancouver" 这类入参用它）对上游 offsetForZoneAtDate 逐值相同，
    含覆盖表与北京时间统一。上游锚在当日 12:00Z、本仓锚在钟面时刻——这里用正午，不在切换日（切换日由 place 闸门单独处理）。
    负向对照：去掉 _normalize_iana_zone_value 里的覆盖表查询 → Vancouver 2027 / Casablanca 2026-12 / Edmonton 红（实跑过：
    本机 zoneinfo 给 -08:00 / +01:00 / -07:00，上游给 -07:00 / +00:00 / -06:00）。"""
    for zone, date, offset, _dst in _golden()["outputs"]["offsets"]:
        assert _normalize_iana_zone_value(zone, payload={"date": date, "time": "12:00:00"}, key="zone") == offset, (zone, date)
    for case in _golden()["outputs"]["zones"]:
        place = case["place"]
        got = _normalize_iana_zone_value(place["iana"], payload={"date": case["date"], "time": "12:00:00"}, key="zone")
        assert got == place["zone"], (case["query"], case["date"])


# ── 引擎工具（horosa-core-js place_search）= 上游 resolvePlaceOffline ─────────────────────────────────


@requires_engine
def test_engine_tool_returns_upstream_candidates_in_upstream_order(tmp_path: Path) -> None:
    """负向对照：把 tools/placeSearch.js 的候选改成 `.reverse()` → 红（实跑过）。"""
    client = HorosaJsEngineClient(_settings(tmp_path))
    for query, expected in _golden()["outputs"]["resolve"].items():
        data = client.run("place_search", {"query": query, "date": CASES["resolveDate"], "limit": 10})["data"]
        got = [[c["name"], c["region"], c["gpsLat"], c["gpsLon"]] for c in data["candidates"]]
        assert got == [[c["name"], c["region"], c["gpsLat"], c["gpsLon"]] for c in expected["candidates"]], query
        assert data["resolved"] is expected["resolved"] and data["confidence"] == expected["confidence"], query
        if expected.get("place"):
            for key in ("name", "lat", "lon", "gpsLat", "gpsLon", "zone"):
                assert data["match"][key] == expected["place"][key], (query, key)
            assert data["match"]["geoZone"] == expected["place"]["iana"]
            assert data["match"]["advisory"] == expected["place"].get("advisory")


@requires_engine
def test_engine_tool_zone_fields_are_upstream_dst_aware_zone(tmp_path: Path) -> None:
    client = HorosaJsEngineClient(_settings(tmp_path))
    for case in _golden()["outputs"]["zones"]:
        match = client.run("place_search", {"query": case["query"], "date": case["date"]})["data"]["match"]
        aware = case["dstAware"]
        assert (match["zone"], match["iana"], match["geoZone"], match["dst"], match["advisory"]) == (
            aware["offset"], aware["zone"], aware["geoZone"], aware["dst"], aware["advisory"]), (case["query"], case["date"])


@requires_engine
def test_cn_unified_opt_out_uses_the_geographic_zone(tmp_path: Path) -> None:
    """cnUnified=false（上游 localStorage kill-switch 的 headless 对应）→ 新疆按 Asia/Urumqi 自己的偏移。
    负向对照：placeSearch.js 忽略 cnUnified → 仍给 +08:00，红（实跑过）。"""
    client = HorosaJsEngineClient(_settings(tmp_path))
    unified = client.run("place_search", {"query": "乌鲁木齐", "date": "2000-01-01"})["data"]["match"]
    local = client.run("place_search", {"query": "乌鲁木齐", "date": "2000-01-01", "cnUnified": False})["data"]["match"]
    assert unified["zone"] == "+08:00" and unified["advisory"] == "cn-unified"
    assert local["zone"] == "+06:00" and local["iana"] == "Asia/Urumqi" and local["advisory"] is None


# ── 门面 horosa_place_search ──────────────────────────────────────────────────────────────────────


@requires_engine
def test_place_search_facade_shapes(tmp_path: Path) -> None:
    service = _service(tmp_path)
    unique = service.place_search({"query": "上海", "date": "1988-07-01"})
    assert unique["resolved"] is True and unique["ambiguous"] is False and unique["date_source"] == "given"
    assert {k: unique["match"][k] for k in ("lat", "lon", "zone", "iana", "dst")} == {
        "lat": "31n13", "lon": "121e28", "zone": "+09:00", "iana": "Asia/Shanghai", "dst": True}
    ambiguous = service.place_search({"query": "朝阳", "date": "1995-07-01", "limit": 3})
    assert ambiguous["ambiguous"] is True and ambiguous["match"] is None and len(ambiguous["candidates"]) == 3
    missing = service.place_search({"query": "zz-no-such-place"})
    assert missing["candidates"] == [] and missing["ambiguous"] is False and missing["date_source"] == "today"
    assert missing["warnings"], "no date → the offset-for-today caveat must be said"
    with pytest.raises(ToolValidationError) as bad:
        service.place_search({"query": "  "})
    assert bad.value.code == "place.invalid_payload"
    with pytest.raises(ToolValidationError) as bad_date:
        service.place_search({"query": "上海", "date": "88/7/1x"})
    assert bad_date.value.code == "place.invalid_payload"


@requires_engine
def test_place_search_flags_a_dst_switch_day_when_time_is_given(tmp_path: Path) -> None:
    """纽约 2026-03-08 02:00 跳表：上游正午锚给 -04:00，01:30 实际是 -05:00。给了 time 就必须报出来（候选上的 zone_at_time + warnings）。
    负向对照：_mark_zone_at_time 直接 return → 红（实跑过）。"""
    result = _service(tmp_path).place_search({"query": "New York", "date": "2026-03-08", "time": "01:30"})
    assert result["match"]["zone"] == "-04:00" and result["match"]["zone_at_time"] == "-05:00"
    assert any("-05:00" in w for w in result["warnings"])
    calm = _service(tmp_path).place_search({"query": "New York", "date": "2026-03-09", "time": "01:30"})
    assert "zone_at_time" not in calm["match"] and calm["warnings"] == []


# ── 技法载荷的 `place` 键 ─────────────────────────────────────────────────────────────────────────


@requires_engine
def test_unique_place_fills_coordinates_zone_and_pos(tmp_path: Path) -> None:
    """负向对照：_resolve_one_spot 不写 zone → 红（实跑过）。"""
    out = _service(tmp_path).resolve_place_fields({"date": "1988-07-01", "time": "08:00", "place": "上海", "gender": 1}, tool_name="bazi_birth")
    assert "place" not in out
    assert (out["lat"], out["lon"], out["gpsLat"], out["gpsLon"], out["zone"], out["pos"]) == (
        "31n13", "121e28", 31.2304, 121.4737, "+09:00", "上海")
    record = out["placeResolution"]
    assert record["status"] == "resolved" and record["zone_source"] == "place_and_date" and record["dst"] is True


@requires_engine
def test_xinjiang_place_carries_the_cn_unified_advisory(tmp_path: Path) -> None:
    out = _service(tmp_path).resolve_place_fields({"date": "2000-01-01", "time": "12:00", "place": "乌鲁木齐"}, tool_name="chart")
    assert out["zone"] == "+08:00" and out["zoneAdvisory"] == "cn-unified" and out["geoZone"] == "Asia/Urumqi"
    before = _service(tmp_path).resolve_place_fields({"date": "1940-01-01", "time": "12:00", "place": "乌鲁木齐"}, tool_name="chart")
    assert before["zone"] == "+06:00" and "zoneAdvisory" not in before


@requires_engine
def test_ambiguous_place_is_refused_with_candidates(tmp_path: Path) -> None:
    """「朝阳」= 北京朝阳区 / 长春朝阳区 / 辽宁朝阳市……绝不替用户挑。负向对照：去掉 high 判定、没有唯一命中时取第一个候选 → 红（实跑过）。"""
    with pytest.raises(ToolValidationError) as exc:
        _service(tmp_path).resolve_place_fields({"date": "1988-07-01", "time": "08:00", "place": "朝阳"}, tool_name="chart")
    error = exc.value
    assert error.code == "place.ambiguous"
    names = [(c["name"], c["region"]) for c in error.details["candidates"]]
    assert ("朝阳区", "北京城区") in names and ("朝阳市", "辽宁省") in names
    recovery = error.details["agent_recovery"]
    assert recovery["must_ask_user"] is True and recovery["reason"] == "place_ambiguous"
    assert recovery["ask_if_missing"][0]["field"] == "place" and len(recovery["ask_if_missing"][0]["options"]) == len(names)
    assert "朝阳区（北京城区）" in recovery["prompt_to_user"]


@requires_engine
def test_medium_confidence_is_not_auto_filled(tmp_path: Path) -> None:
    """上游 medium（前缀唯一最优）自己也要求「向用户复述确认」：不自动补。负向对照：自动补全也收 medium → 红（实跑过）。"""
    with pytest.raises(ToolValidationError) as exc:
        _service(tmp_path).resolve_place_fields({"date": "1988-07-01", "time": "08:00", "place": "辽宁朝阳"}, tool_name="chart")
    assert exc.value.code == "place.ambiguous" and exc.value.details["confidence"] == "medium"


@requires_engine
def test_unknown_place_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ToolValidationError) as exc:
        _service(tmp_path).resolve_place_fields({"date": "1988-07-01", "time": "08:00", "place": "zz-no-such-place"}, tool_name="chart")
    assert exc.value.code == "place.not_found"
    assert exc.value.details["agent_recovery"]["must_ask_user"] is True and exc.value.details["candidates"] == []


def test_explicit_coordinates_and_zone_beat_place(tmp_path: Path) -> None:
    """显式坐标在场时根本不查城市库（js_client 被调用即失败）；只给一半坐标是结构化错误，不拿 place 补另一半。
    负向对照：去掉「两轴都给了就返回」的短路 → 红（实跑过）。"""

    class _NoEngine:
        def run(self, *_a: Any, **_k: Any) -> dict[str, Any]:
            raise AssertionError("explicit coordinates must not hit the place engine")

    service = _service(tmp_path, js_client=_NoEngine())
    out = service.resolve_place_fields(
        {"date": "1988-07-01", "time": "08:00", "zone": "+08:00", "lat": "39n54", "lon": "116e24", "place": "上海"}, tool_name="chart")
    assert (out["lat"], out["lon"], out["zone"]) == ("39n54", "116e24", "+08:00") and "place" not in out
    assert out["placeResolution"]["status"] == "explicit_coordinates"
    with pytest.raises(ToolValidationError) as exc:
        service.resolve_place_fields({"date": "1988-07-01", "time": "08:00", "lat": "39n54", "place": "上海"}, tool_name="chart")
    assert exc.value.code == "place.coordinate_missing"


@requires_engine
def test_explicit_zone_beats_the_place_zone(tmp_path: Path) -> None:
    out = _service(tmp_path).resolve_place_fields(
        {"date": "1988-07-01", "time": "08:00", "zone": "+08:00", "place": "上海"}, tool_name="chart")
    assert out["zone"] == "+08:00" and out["lat"] == "31n13" and out["placeResolution"]["zone_source"] == "explicit"


@requires_engine
def test_dst_switch_day_refuses_instead_of_guessing_the_zone(tmp_path: Path) -> None:
    with pytest.raises(ToolValidationError) as exc:
        _service(tmp_path).resolve_place_fields({"date": "2026-03-08", "time": "01:30", "place": "New York"}, tool_name="chart")
    assert exc.value.code == "place.zone_ambiguous"
    assert exc.value.details["ask_if_missing"][0]["options"] == ["-04:00", "-05:00"]


@requires_engine
def test_place_inside_dispatch_birth_and_relative_parties(tmp_path: Path) -> None:
    service = _service(tmp_path)
    nested = service.resolve_place_fields({"query": "看八字", "birth": {"date": "1990-05-18", "time": "08:30", "place": "上海"},
                                           "context": {"place": "北京"}}, tool_name="dispatch")
    # 1990-05-18 在 1986–1991 夏令时内：期望值取自引擎本身（同一天的 place_search），不手写。
    shanghai = service.place_search({"query": "上海", "date": "1990-05-18"})["match"]
    beijing = service.place_search({"query": "北京", "date": "1990-05-18"})["match"]
    assert (nested["birth"]["lat"], nested["birth"]["zone"]) == (shanghai["lat"], shanghai["zone"])
    assert (nested["context"]["lat"], nested["context"]["zone"]) == (beijing["lat"], beijing["zone"])  # context 借 birth 的日期
    again = service.resolve_place_fields(nested, tool_name="dispatch")
    assert again == nested  # 幂等：解析过的位置不再有 place
    relative = service.resolve_place_fields({"inner": {"date": "1988-07-01", "time": "08:00", "place": "北京"},
                                             "outer": {"date": "1995-07-01", "time": "08:00", "place": "上海"}}, tool_name="relative")
    assert (relative["inner"]["zone"], relative["outer"]["zone"]) == ("+09:00", "+08:00")
    _stripped, records = service.pop_place_records(relative)
    assert [r["spot"] for r in records] == ["inner", "outer"] and "placeResolution" not in _stripped["inner"]


# ── 旧 runtime：缺 place_search 工具 / 缺 tz-lookup ───────────────────────────────────────────────────


def _engine_copy(tmp_path: Path, *, drop_tool: bool = False, drop_dependency: bool = False) -> Path:
    root = tmp_path / "stale-core-js"
    shutil.copytree(CORE_JS / "bin", root / "bin")
    shutil.copytree(CORE_JS / "src", root / "src")
    shutil.copy2(CORE_JS / "package.json", root / "package.json")
    shutil.copytree(CORE_JS / "node_modules", root / "node_modules", symlinks=False)
    if drop_tool:
        index = root / "src" / "tools" / "index.js"
        source = index.read_text(encoding="utf-8")
        assert "  place_search: runPlaceSearch,\n" in source  # 否则「旧 core-js」没造出来，测试会因错误的原因通过
        index.write_text(source.replace("  place_search: runPlaceSearch,\n", ""), encoding="utf-8")
    if drop_dependency:
        shutil.rmtree(root / "node_modules" / "tz-lookup")
        assert not (root / "node_modules" / "tz-lookup").exists()
    return root


@requires_engine
@pytest.mark.parametrize("stale", ["drop_tool", "drop_dependency"])
def test_a_stale_runtime_degrades_with_a_clear_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stale: str) -> None:
    """已装 runtime 只有旧 core-js（不认 place_search）或旧 node_modules（缺 tz-lookup）：报 place.runtime_outdated + 升级命令，
    不是 js_engine.execution_failed 的一团堆栈，也不静默。其余 JS 技法照常（tools/index.js 懒加载）。
    负向对照：_STALE_ENGINE 正则改成永不命中 → 两例都变成 js_engine.execution_failed，红（实跑过）。"""
    root = _engine_copy(tmp_path, drop_tool=stale == "drop_tool", drop_dependency=stale == "drop_dependency")
    client = HorosaJsEngineClient(_settings(tmp_path))
    monkeypatch.setattr(client, "_candidate_engine_roots", lambda: [root])
    service = _service(tmp_path, js_client=client)
    with pytest.raises(ToolValidationError) as exc:
        service.place_search({"query": "上海", "date": "1988-07-01"})
    assert exc.value.code == "place.runtime_outdated"
    assert exc.value.details["commands"] and "upgrade" in exc.value.details["commands"][0]
    with pytest.raises(ToolValidationError) as auto:
        service.resolve_place_fields({"date": "1988-07-01", "time": "08:00", "place": "上海"}, tool_name="chart")
    assert auto.value.code == "place.runtime_outdated"
    # 别的 JS 技法不受牵连：缺 tz-lookup 时 tools/index.js 照样加载。
    assert client.run("xiaoliuren", {"date": "1988-07-01", "time": "08:00"}) is not None


def test_other_engine_failures_keep_their_own_code(tmp_path: Path) -> None:
    class _Broken:
        def run(self, *_a: Any, **_k: Any) -> dict[str, Any]:
            raise ToolTransportError("node missing", code="js_engine.node_unavailable", details={"tool": "place_search"})

    with pytest.raises(ToolValidationError) as exc:
        _service(tmp_path, js_client=_Broken()).place_search({"query": "上海"})
    assert exc.value.code == "js_engine.node_unavailable"


# ── 走一遍真实入口（run_tool / MCP / CLI）─────────────────────────────────────────────────────────


@requires_engine
def test_run_tool_records_place_resolution_on_the_card_and_in_warnings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(tmp_path)
    seen: dict[str, Any] = {}

    def fake_local(definition: Any, payload: dict[str, Any]) -> dict[str, Any]:
        seen.update(payload)
        return {"ok": True}

    monkeypatch.setattr(service, "_run_local_tool", fake_local)
    envelope = service.run_tool("xiaoliuren", {"date": "1988-07-01", "time": "08:00", "place": "上海"}, save_result=False)
    assert seen["lat"] == "31n13" and seen["zone"] == "+09:00" and "place" not in seen and "placeResolution" not in seen
    assert any("上海" in w and "+09:00" in w for w in envelope.warnings), envelope.warnings
    card = envelope.data.get("technique_card") or {}
    assert card.get("place_resolution") and card["place_resolution"][0]["name"] == "上海"


@requires_engine
def test_ambiguous_place_through_run_tool_is_a_structured_refusal(tmp_path: Path) -> None:
    with pytest.raises(ToolValidationError) as exc:
        _service(tmp_path).run_tool("chart", {"date": "1988-07-01", "time": "08:00", "place": "朝阳"}, save_result=False)
    assert exc.value.code == "place.ambiguous"


def _mcp(tmp_path: Path, *, compact: bool = False):
    import anyio  # noqa: F401 - 与其它 MCP 测试同一个运行器

    from horosa_skill.schemas.common import DispatchEnvelope, ToolEnvelope
    from horosa_skill.surfaces import mcp_server as M

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", mcp_compact=compact)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    seen: list[dict[str, Any]] = []

    def _run_tool(tool_name: str, payload: dict[str, Any], **_kwargs: Any) -> ToolEnvelope:
        seen.append(dict(payload))
        return ToolEnvelope(ok=True, tool=tool_name, version="test", input_normalized=dict(payload))

    def _dispatch(payload: dict[str, Any], **_kwargs: Any) -> DispatchEnvelope:
        seen.append(dict(payload))
        return DispatchEnvelope(ok=True, version="test")

    service.run_tool = _run_tool  # type: ignore[method-assign]
    service.dispatch = _dispatch  # type: ignore[method-assign]
    return M.create_mcp_server(service, settings), seen


def _call(mcp: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    import anyio

    async def _go() -> Any:
        return await mcp.call_tool(name, arguments)

    return json.loads(anyio.run(_go).content[0].text)


@pytest.mark.parametrize("compact", [False, True])
def test_place_search_is_registered_read_only_on_both_surfaces(tmp_path: Path, compact: bool) -> None:
    import anyio

    mcp, _ = _mcp(tmp_path, compact=compact)
    tools = {tool.name: tool for tool in anyio.run(mcp.list_tools)}
    tool = tools["horosa_place_search"]
    assert tool.annotations.read_only_hint is True and tool.annotations.destructive_hint is False
    assert tool.annotations.open_world_hint is False
    assert set(tool.input_schema["properties"]) >= {"query", "date", "time", "limit"}


@requires_engine
def test_mcp_technique_call_resolves_place_before_the_model_validates(tmp_path: Path) -> None:
    """MCP 层先按技法模型校验（lat / lon / zone 必填）：place 必须在那之前补上，否则只会得到一份「缺 lat」的校验错误。
    负向对照：把 mcp_server 里技法闭包的 `_placed(...)` 去掉 → 红（实跑过）。"""
    mcp, seen = _mcp(tmp_path)
    body = {"request": {"date": "1988-07-01", "time": "08:00", "place": "上海", "gender": 1}, "agent_confirmed_settings": True}
    result = _call(mcp, "horosa_cn_bazi_birth", body)
    assert result.get("ok") is True, result
    assert seen[-1]["lat"] == "31n13" and seen[-1]["zone"] == "+09:00" and seen[-1]["placeResolution"]["name"] == "上海"
    refused = _call(mcp, "horosa_cn_bazi_birth", {**body, "request": {**body["request"], "place": "朝阳"}})
    assert refused["ok"] is False and refused["code"] == "place.ambiguous"
    assert refused["details"]["agent_recovery"]["must_ask_user"] is True


@requires_engine
def test_mcp_dispatch_with_place_in_birth(tmp_path: Path) -> None:
    mcp, seen = _mcp(tmp_path)
    result = _call(mcp, "horosa_dispatch", {"query": "看八字", "birth": {"date": "1988-07-01", "time": "08:00", "place": "上海", "gender": 1},
                                            "agent_confirmed_settings": True})
    assert result.get("ok") is True, result
    assert seen[-1]["birth"]["lat"] == "31n13" and seen[-1]["birth"]["zone"] == "+09:00"


@requires_engine
def test_mcp_place_search_returns_the_facade_shape(tmp_path: Path) -> None:
    mcp, _ = _mcp(tmp_path, compact=True)
    result = _call(mcp, "horosa_place_search", {"query": "朝阳", "date": "1995-07-01", "limit": 3})
    assert result["ambiguous"] is True and len(result["candidates"]) == 3 and result["next_step"]
    bad = _call(mcp, "horosa_place_search", {"query": ""})
    assert bad["ok"] is False and bad["code"] == "place.invalid_payload"


@requires_engine
def test_cli_place_search(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill.surfaces import cli

    monkeypatch.setattr(cli, "_service", lambda: _service(tmp_path))
    cli.place_search("New York", date="2026-01-15", time=None, limit=None)
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and out["match"]["zone"] == "-05:00" and out["match"]["iana"] == "America/New_York"
