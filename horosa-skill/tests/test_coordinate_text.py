"""十进制 → 罗盘串（31n13 / 121e28）与上游逐值相同（v0.48.0 parity 修复）。

上游：components/astro/AstroHelper.js 的 splitDegree / convertLatToStr / convertLonToStr（utils/aiTools/normalize/geoCompass.js 是它的
逐字抄本，上游 jest 切片锁两处同构）。度取整、分**向下取整**、秒 Math.round、秒满 60 进分、分满 60 进度、方向按原值符号。
本仓旧实现把分四舍五入：31.2304 → 31n14（上游 31n13），-118.2437 → 118w15（上游 118w14）——这串直接进起盘请求（后端按 `lat` 文本排盘）。

金标 = 上游源本身在 node 里跑出（fixtures/place_search/coordinate_harness.mjs + upstream_hooks.mjs，只读），存成
tests/fixtures/coordinate_text_upstream.json：逐条用例全表 + 五个批量集（整数分往返 / 半分 / 城市库全部坐标 / 4–7 位小数 / 进位边界）
的条数与 sha256。`test_fixture_matches_upstream` 在 HOROSA_SOURCE_ROOT 可用时重跑上游并逐条比对。
唯一有意不跟上游：非有限值与 |x| ≥ 1e21（上游当 0 → 0n00、或只取首位数字 → 1n06）在本仓不换算，交校验层报错。
负向对照（实跑过）：把 _format_compact_coordinate 的分改回 round(...) → 本文件 4 条 + 地名对拍 1 条红；去掉非有限值拒收 → 2 条红。
（把秒的 JS Math.round 换成 Python round 不会红：这里只比「是否等于 60」，两者在 [59.5, 60) 上取值相同——这条不是有效对照。）
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from horosa_skill.input_normalization import (
    _coerce_coordinate_decimal,
    _format_compact_coordinate,
    normalize_request_payload,
)

PKG = Path(__file__).resolve().parents[1]
CORE_JS = PKG / "horosa-core-js"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "place_search"
GOLDEN = Path(__file__).resolve().parent / "fixtures" / "coordinate_text_upstream.json"
_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
UPSTREAM_SRC = Path(_ROOT) / "Horosa-Web" / "astrostudyui" / "src" if _ROOT else None
TZ_LOOKUP = CORE_JS / "node_modules" / "tz-lookup" / "tz.js"
requires_upstream = pytest.mark.skipif(
    shutil.which("node") is None or UPSTREAM_SRC is None
    or not (UPSTREAM_SRC / "components" / "astro" / "AstroHelper.js").is_file() or not TZ_LOOKUP.is_file(),
    reason="node + HOROSA_SOURCE_ROOT (Horosa-Public checkout) + core-js node_modules required",
)


def _literal(value: float) -> str:
    return repr(value)


# (说明, 数字字面量)：上游与本仓都从这同一个字面量出发（JS Number(…) / Python float(…) 对十进制串同为正确舍入）。
CASES: list[tuple[str, str]] = [
    ("上海纬度（旧实现进成 31n14）", "31.2304"),
    ("上海经度", "121.4737"),
    ("洛杉矶经度（旧实现 118w15）", "-118.2437"),
    ("洛杉矶纬度", "34.0522"),
    ("零", "0"), ("负零", "-0"), ("负零小数", "-0.0"),
    ("北极 / 东 90", "90"), ("南极 / 西 90", "-90"), ("东 180", "180"), ("西 180", "-180"),
    ("179.99999 → 进位到 180", "179.99999"), ("-179.99999", "-179.99999"), ("179.9999999", "179.9999999"), ("89.9999999", "89.9999999"),
    ("x.9999（59′59.64″ 秒进分、分进度）", "31.9999"), ("x.99999", "31.99999"), ("x.999999", "31.999999"), ("x.9999999", "31.9999999"),
    ("59′59.95″ → 秒满 60 → 32n00", _literal(31 + 59 / 60 + 59.95 / 3600)),
    ("59′59.4″ → 仍是 59′（旧实现进成 32n00）", _literal(31 + 59 / 60 + 59.4 / 3600)),
    ("13′29.5″（秒恰 .5）", _literal(31 + 13 / 60 + 29.5 / 3600)),
    ("13′59.5″（浮点略小于 .5：不进分；旧实现 31n14）", _literal(31 + 13 / 60 + 59.5 / 3600)),
    ("13.5′（旧实现银行家舍入成 14）", "31.225"),
    ("31.2167", "31.2167"), ("121.4667", "121.4667"), ("39.9（浮点 53.9999…′）", "39.9"), ("116.4", "116.4"), ("26.07", "26.07"),
    ("-31.2", "-31.2"), ("121.5", "121.5"), ("-41.433333", "-41.433333"), ("-174.5", "-174.5"),
    ("1e-7（上游走 e 分支）", "1e-7"), ("5e-7", "5e-7"), ("-1e-7（负号仍判南 / 西）", "-1e-7"), ("1e-6", "1e-6"),
    ("0°0.49998′", "0.0083333"), ("刚不到 1′", "0.016666"), ("1′ 的浮点近似", "0.0166666667"),
    ("-0.12（度为 0 也判南 / 西）", "-0.12"), ("-0.5", "-0.5"),
    ("越界有限值 200.5", "200.5"), ("越界有限值 -720.25", "-720.25"),
    # 有意不跟上游：本仓不换算、交校验层报错（上游：NaN / ±Infinity → 0n00 / 0e00，≥1e21 → 只取首位数字）。
    ("NaN（不换算）", "NaN"), ("Infinity（不换算）", "Infinity"), ("-Infinity（不换算）", "-Infinity"),
    ("1e21（不换算）", "1e21"), ("-1e21（不换算）", "-1e21"), ("1.5e21（不换算）", "1.5e21"),
]
_OUT_OF_DOMAIN = {"NaN", "Infinity", "-Infinity", "1e21", "-1e21", "1.5e21"}


def _city_values() -> list[float]:
    values: list[float] = []
    for name in ("cities.json", "citiesFull.json"):
        for entry in json.loads((CORE_JS / "src" / "vendor" / "place" / "data" / name).read_text(encoding="utf-8")):
            for key in (("lat", "lng") if "lat" in entry else ("y", "x")):
                values.append(float(entry[key]))
    return values


def _bulk_sets() -> dict[str, list[float]]:
    """确定性生成；同一份 float 经 JSON 送进上游（repr 往返精确）。"""
    whole = [sign * (d + m / 60) for d in range(181) for m in range(60) for sign in (1, -1)]  # = 本仓解析 31n13 的那个 float
    half = [sign * (d + (m + 0.5) / 60) for d in range(181) for m in range(60) for sign in (1, -1)]  # 31n13.5 这类小数分
    decimals = []
    for digits in (4, 5, 6, 7):
        span = 360 * 10**digits + 1
        decimals += [(i * 2654435761 % span) / 10**digits - 180 for i in range(5000)]
    edges = []
    for d in (0, 1, 31, 89, 90, 121, 179):
        for m in (0, 13, 59):
            for s in (0, 29, 30, 59):
                for eps in (-1e-9, -1e-12, 0.0, 1e-12, 1e-9):
                    edges += [d + m / 60 + (s + 0.5) / 3600 + eps, -(d + m / 60 + (s + 0.5) / 3600 + eps)]
        for frac in (0.9999, 0.99999, 0.999999, 0.9999999, 0.99999999):
            edges += [d + frac, -(d + frac)]
    return {"whole_minutes": whole, "half_minutes": half, "city_library": _city_values(), "decimals_4_to_7": decimals,
            "carry_edges": edges}


def _python_pair(value: float) -> list[str]:
    return [_format_compact_coordinate(value, axis="lat"), _format_compact_coordinate(value, axis="lon")]


def _digest(pairs: list[list[str]]) -> str:
    return hashlib.sha256("\n".join(f"{lat}|{lon}" for lat, lon in pairs).encode("utf-8")).hexdigest()


def _upstream_outputs(tmp_path: Path) -> dict[str, Any]:
    assert UPSTREAM_SRC is not None
    config = {
        "hooks": (FIXTURES / "upstream_hooks.mjs").resolve().as_uri(),
        "hookData": {"tzLookupUrl": TZ_LOOKUP.resolve().as_uri(), "upstreamRoot": UPSTREAM_SRC.resolve().as_uri()},
        "astroHelper": (UPSTREAM_SRC / "components" / "astro" / "AstroHelper.js").resolve().as_uri(),
        "geoCompass": (UPSTREAM_SRC / "utils" / "aiTools" / "normalize" / "geoCompass.js").resolve().as_uri(),
        "cases": CASES,
        "sets": _bulk_sets(),
    }
    path = tmp_path / "coordinate_config.json"
    path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    completed = subprocess.run(["node", str(FIXTURES / "coordinate_harness.mjs"), str(path)],
                               capture_output=True, text=True, encoding="utf-8", timeout=300)
    if completed.returncode:
        raise RuntimeError(completed.stderr[-4000:])
    return json.loads(completed.stdout)


def _summarise(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "cases": raw["cases"],
        "sets": {name: {"count": len(pairs), "sha256": _digest(pairs)} for name, pairs in raw["sets"].items()},
        "compassMismatches": raw["compassMismatches"],
    }


def _golden() -> dict[str, Any]:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@requires_upstream
def test_fixture_matches_upstream(tmp_path: Path) -> None:
    raw = _upstream_outputs(tmp_path)
    assert raw["compassMismatches"] == 0  # 上游两份实现自己是同构的
    assert _summarise(raw) == _golden()["outputs"]
    sets = _bulk_sets()
    for name, pairs in raw["sets"].items():  # 有上游时逐条比，红了直接看到是哪个数
        mismatches = [(v, up, _python_pair(v)) for v, up in zip(sets[name], pairs) if _python_pair(v) != up]
        assert not mismatches, (name, mismatches[:5])


def test_every_named_case_equals_upstream() -> None:
    for label, literal, up_lat, up_lon in _golden()["outputs"]["cases"]:
        value = float(literal)
        if literal in _OUT_OF_DOMAIN:
            # 上游给 0n00 / 1n06 一类假坐标；本仓不换算（原值留给校验层报 tool.invalid_payload）。
            # （字符串 "1e21" 不在此列：罗盘串优先匹配，它是东经 1°21′——见 test_input_normalization 的 121e30 哨兵。）
            assert _coerce_coordinate_decimal(value) is None, label
            continue
        assert _python_pair(value) == [up_lat, up_lon], (label, literal)
        if "e" not in literal:  # 指数写法的串不收（121e30 是东经 121°30′ 的罗盘串，不是 1.21e32）；数字形态照收
            assert _coerce_coordinate_decimal(literal) == value, label  # 十进制串与数字走同一个 float


def test_bulk_sets_equal_upstream() -> None:
    """五个批量集 ~150k 个值：条数与输出摘要逐一等于上游。"""
    sets = _bulk_sets()
    golden = _golden()["outputs"]["sets"]
    assert set(sets) == set(golden)
    for name, values in sets.items():
        assert len(values) == golden[name]["count"], name
        assert _digest([_python_pair(v) for v in values]) == golden[name]["sha256"], name


def test_compact_text_round_trips_unchanged() -> None:
    """31n13 这类整数分输入：解析成十进制再换算回来必须原样（上游往返同样成立，见 whole_minutes 集）。"""
    # v0.50.0：只在合法值域里往返（纬度 ≤ 90°、经度 ≤ 180°）；域外的罗盘串（90n01、180e01）现在拒绝，见 test_input_fields。
    for d in range(181):
        for m in range(60):
            for lat_h, lon_h in (("n", "e"), ("s", "w")):
                text_lat, text_lon = f"{d}{lat_h}{m:02d}", f"{d}{lon_h}{m:02d}"
                payload = {"lon": text_lon} if d * 60 + m > 180 * 60 else {"lat": text_lat, "lon": text_lon}
                if d * 60 + m > 90 * 60:
                    payload.pop("lat", None)
                if not payload:
                    continue
                out = normalize_request_payload(payload)
                expect_lat = text_lat if (d or m or lat_h == "n") else f"{d}n{m:02d}"  # 0s00 是 -0 → 0n00（上游同）
                expect_lon = text_lon if (d or m or lon_h == "e") else f"{d}e{m:02d}"
                if "lat" in payload:
                    assert out["lat"] == expect_lat, text_lat
                assert out["lon"] == expect_lon, text_lon


def test_every_coordinate_key_goes_through_the_upstream_formatter() -> None:
    """lat / lon / dirLat / dirLon / guaLat / guaLon 与「只给 gpsLat / gpsLon」五条路都用同一个换算。"""
    out = normalize_request_payload({"lat": 31.2304, "lon": "-118.2437", "dirLat": "31.2304", "dirLon": -118.2437,
                                     "guaLat": 31.2304, "guaLon": "-118.2437"})
    assert [out[k] for k in ("lat", "lon", "dirLat", "dirLon", "guaLat", "guaLon")] == ["31n13", "118w14"] * 3
    gps = normalize_request_payload({"gpsLat": 31.2304, "gpsLon": -118.2437})
    assert (gps["lat"], gps["lon"], gps["gpsLat"], gps["gpsLon"]) == ("31n13", "118w14", 31.2304, -118.2437)


def test_non_finite_coordinates_are_refused_not_turned_into_zero(tmp_path: Path) -> None:
    from horosa_skill.config import Settings
    from horosa_skill.errors import ToolValidationError
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService

    # v0.50.0：非有限值在归一化这一步就拒（tool.invalid_coordinate），不再原样留给模型校验。
    with pytest.raises(ToolValidationError) as caught:
        normalize_request_payload({"lat": math.nan, "lon": math.inf})
    assert caught.value.code == "tool.invalid_coordinate"
    assert [item["field"] for item in caught.value.details["fields"]] == ["lat", "lon"]
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    with pytest.raises(ToolValidationError) as exc:
        service.run_tool("chart", {"date": "1990-01-01", "time": "12:00", "zone": "+08:00", "lat": math.nan, "lon": 121.5},
                         save_result=False)
    assert exc.value.code == "tool.invalid_coordinate"
