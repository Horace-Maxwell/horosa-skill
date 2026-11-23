"""上游 v3.14.0 辅盘「变换盘」「黄道制」的值级金标（离线）。

期望值的来源都不是本仓的输出：
- **上游自己的后端金标** `astropy/tests/data/golden_transform_full.json`（上游 test_everything_matches_the_full_golden：西雅图盘
  1975-02-10 21:15 −08:00 / 47n36 / 122w20 / hsys 1，33 种变换 × 改进 / 经典两档的各点黄经、宫头、起盘时刻、垂直黄道两解、
  现代宫主表与黄金分割表）与 `golden_zodiac_systems.json`（19 个黄道版本在 J2000 的座头 / 座长表）。两份原样摘抄在
  fixtures/sync314_labs_upstream_golden.json，有上游 checkout 时逐项核对摘抄没走样。
- **上游后端测试里写死的数**（test_zodiac_systems.py：西雅图盘太阳落摩羯座、十三宫 [5,5,5,6,4,6]、太阳宫内 22.848°、火星 15.744°）。
- **手算**：各黄道版本的落段 = 座头（随岁差移动的版本加 J2000 起算的黄经总岁差）起逐段减座长。

被测物 = 共享 vendored v3.14.0 引擎实抓的后端结果（fixtures/sync314_labs_live.json.gz，请求体由 runner 自己构造）→ 真 node 引擎
tools/auxLabs.js（vendored 上游 transformSnapshotLines / transformSnapshotChart / zodiacSnapshotLines）排出的正文行。
"""
from __future__ import annotations

from skips import upstream_source  # 上游拆文件后读「门面 + 子模块」全集（v3.15.0）
import gzip
import hashlib
import json
import re
from functools import cache
from pathlib import Path

import pytest
from node_esm import run_node_esm
from skips import needs_upstream, upstream_path

from horosa_skill import auxlab_vocab as V

_FIXTURES = Path(__file__).parent / "fixtures"
_CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
_GOLDEN_FULL = "Horosa-Web/astropy/tests/data/golden_transform_full.json"
_GOLDEN_ZODIAC = "Horosa-Web/astropy/tests/data/golden_zodiac_systems.json"
_TEN = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto")
# AstroMsgCN（上游 constants/AstroText.js）里这几个点的中文名；全表由真引擎出，这里只列断言要念到的。
_NAME = {"Sun": "太阳", "Moon": "月亮", "Mercury": "水星", "Venus": "金星", "Mars": "火星", "Jupiter": "木星", "Saturn": "土星",
         "Uranus": "天王星", "Neptune": "海王星", "Pluto": "冥王星", "North Node": "北交", "Asc": "上升", "MC": "天顶"}
KEYS = tuple(
    f"{kind}/{variant}"
    for kind in V.TRANSFORM_KINDS
    for variant in (("improved", "classic") if "variant" in V.TRANSFORM_KIND_OPTIONS[kind] else ("improved",))
)


@cache
def live() -> dict:
    return json.loads(gzip.decompress((_FIXTURES / "sync314_labs_live.json.gz").read_bytes()).decode("utf-8"))


@cache
def golden() -> dict:
    return json.loads((_FIXTURES / "sync314_labs_upstream_golden.json").read_text(encoding="utf-8"))


def settings_for(key: str) -> dict:
    kind, variant = key.split("/")
    return {"kind": kind, "planet": "Moon", "shift": False, "house": 4, "variant": variant}


@cache
def transform_outputs() -> dict:
    """37 份实抓后端结果各过一遍真引擎的 aux_labs（一次 node 进程；载荷走临时文件——Windows 命令行有长度上限）。"""
    import tempfile

    cases = {key: {"technique": "transformchart", "result": live()["transform"][key], "settings": settings_for(key)} for key in KEYS}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cases.json"
        path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
        out = run_node_esm(
            "import { readFileSync } from 'node:fs'; import { fileURLToPath } from 'node:url';"
            "import { runTool } from './src/tools/index.js';"
            "const cases = JSON.parse(readFileSync(fileURLToPath(process.argv[1]), 'utf8')); const out = {};"
            "for (const [key, payload] of Object.entries(cases)) { out[key] = await runTool('aux_labs', payload); }"
            "console.log(JSON.stringify(out))",
            path, cwd=_CORE_JS, timeout=120,
        )
    return json.loads(out)


@cache
def zodiac_outputs() -> dict:
    import tempfile

    base = live()["zodiac"]
    cases = {
        version: {"technique": "zodiacsystems", "settings": {"version": version},
                  "result": {**base, "version": version, "wheel": live()["zodiac_wheels"][version]}}
        for version, _label in V.ZODIAC_VERSIONS
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cases.json"
        path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
        out = run_node_esm(
            "import { readFileSync } from 'node:fs'; import { fileURLToPath } from 'node:url';"
            "import { runTool } from './src/tools/index.js';"
            "const cases = JSON.parse(readFileSync(fileURLToPath(process.argv[1]), 'utf8')); const out = {};"
            "for (const [key, payload] of Object.entries(cases)) { out[key] = await runTool('aux_labs', payload); }"
            "console.log(JSON.stringify(out))",
            path, cwd=_CORE_JS, timeout=120,
        )
    return json.loads(out)


def _house_number(house: dict) -> int:
    return int(re.sub(r"\D", "", house["id"]))


def _position_line(lines: list[str], name: str) -> tuple[float, float]:
    """`名:本命黄经 a° → b°` → (a, b)。"""
    hits = [re.fullmatch(rf"{re.escape(name)}:本命黄经 (-?[\d.]+)° → (-?[\d.]+)°", line) for line in lines]
    found = [m for m in hits if m]
    assert len(found) == 1, (name, [line for line in lines if line.startswith(name)])
    return float(found[0].group(1)), float(found[0].group(2))


# ─────────────────────────── 摘抄的上游金标没走样 ───────────────────────────


@needs_upstream(_GOLDEN_FULL, _GOLDEN_ZODIAC)
def test_the_copied_upstream_goldens_equal_the_upstream_files() -> None:
    full = json.loads(upstream_source(upstream_path(_GOLDEN_FULL)))
    assert golden()["transform_full_B"] == {key[2:]: value for key, value in full.items() if key.startswith("B/")}
    assert golden()["zodiac_tables"] == json.loads(upstream_source(upstream_path(_GOLDEN_ZODIAC)))["tables"]
    for relative, recorded in golden()["sources"].items():
        text = upstream_path(relative).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(text).hexdigest() == recorded, f"{relative} changed upstream: re-capture and re-check the goldens"


def test_the_golden_covers_every_kind_and_both_variants() -> None:
    table = golden()["transform_full_B"]
    assert sorted(table) == sorted(f"{kind}/{variant}" for kind in V.TRANSFORM_KINDS for variant in ("improved", "classic"))
    assert set(KEYS) <= set(table) and len(KEYS) == 37


# ─────────────────────────── 变换盘：后端结果 == 上游后端金标 ───────────────────────────


@pytest.mark.parametrize("key", KEYS)
def test_captured_backend_result_equals_the_upstream_full_golden(key: str) -> None:
    """runner 构造的请求体（只带这种变换用到的选项）打出来的盘 == 上游 full_snapshot（各选项全带）在同一张盘上的金标。"""
    resp, want = live()["transform"][key], golden()["transform_full_B"][key]
    assert [[row["id"], round(row["lon"], 6)] for row in resp["positions"]] == want["positions"]
    houses = sorted(resp["chart"]["chart"]["houses"], key=_house_number)
    assert [round(house["lon"], 6) for house in houses] == want["cusps"]
    assert houses[0].get("hsysDerived") == want["derived"]
    assert resp.get("moment") == want["moment"]
    assert resp.get("vertical") == want["vertical"]
    assert resp["kind"] == key.split("/")[0]


def test_recorded_request_bodies_carry_only_the_options_each_kind_uses() -> None:
    requests = live()["transform_requests"]
    assert requests["inverted/classic"] == {"transformKind": "inverted", "transformVariant": "classic"}
    assert requests["superimposed/improved"] == {"transformKind": "superimposed", "transformPlanet": "Moon", "transformShift": 0}
    assert requests["epoch/improved"] == {"transformKind": "epoch", "transformHouse": 4}
    assert requests["persona/improved"] == {"transformKind": "persona", "transformPlanet": "Moon"}
    assert requests["antiscia/improved"] == {"transformKind": "antiscia"}
    for key in KEYS:
        assert requests[key] == V.transform_request_fields(settings_for(key)), key


def test_modern_rulers_and_golden_section_equal_the_upstream_golden() -> None:
    resp, want = live()["transform"]["superimposed/improved"], golden()["transform_full_B"]["superimposed/improved"]
    assert resp["rulers"] == want["rulers"] and resp["golden"] == want["golden"]


# ─────────────────────────── 变换盘：正文行带着上游金标的数 ───────────────────────────


@pytest.mark.parametrize("key", KEYS)
def test_transform_section_lines_carry_the_upstream_golden_longitudes(key: str) -> None:
    kind, variant = key.split("/")
    out = transform_outputs()[key]
    lines = out["lines"]
    assert out["title"] == "变换盘"
    assert lines[0].startswith(f"变换:{V.TRANSFORM_KIND_LABELS[kind]}。")
    table = golden()["transform_full_B"]
    # 星不动的盘（地理盘只挪四轴与宫头）给出十星的本命黄经——与本例无关的另一条金标。
    natal = dict(table["geodeticLong/improved"]["positions"])
    want = dict(table[key]["positions"])
    for point in _TEN:
        if point not in want:      # 行星中心盘不列中心星
            assert kind == "planetCentered" and point == "Moon", (key, point)
            assert not any(line.startswith(f"{_NAME[point]}:本命黄经") for line in lines)
            continue
        before, after = _position_line(lines, _NAME[point])
        assert before == pytest.approx(natal[point], abs=0.0051), (key, point)
        assert after == pytest.approx(want[point] % 360.0, abs=0.0051), (key, point)
    for point in ("Asc", "MC", "North Node"):
        assert _position_line(lines, _NAME[point])[1] == pytest.approx(want[point] % 360.0, abs=0.0051), (key, point)
    # 用到的选项才写（上游 transformSnapshotLines 按 transformKindDef(kind).options）。
    options = V.TRANSFORM_KIND_OPTIONS[kind]
    text = "\n".join(lines)
    assert ("基准星:月亮" in lines) is ("planet" in options)
    assert ("宫位:不动" in lines) is ("shift" in options)
    assert ("对应本命第 4 宫头" in lines) is ("house" in options)
    if "variant" in options:
        assert ("口径:改进" if variant == "improved" else "口径:经典(四轴留在本命;现代宫主表白羊主冥王、天蝎主火星)") in lines
    else:
        assert "口径:" not in text
    assert out["request_fields"] == live()["transform_requests"][key]


def test_moment_kinds_write_the_upstream_golden_moment() -> None:
    table = golden()["transform_full_B"]
    assert table["persona/improved"]["moment"] == "1976-02-11 02:38:17" and table["epoch/improved"]["moment"] == "1974-05-10 01:39:26"
    for kind in ("persona", "epoch"):
        lines = transform_outputs()[f"{kind}/improved"]["lines"]
        assert f"起盘时刻:{table[f'{kind}/improved']['moment']}" in lines
        # 另起时刻的盘没有「坐标口径」两句（那是把本命盘换算出来的盘才有的说明）。
        assert not any("本来的位置" in line or "得时失时" in line for line in lines)
    assert not any(line.startswith("起盘时刻") for line in transform_outputs()["inverted/improved"]["lines"])


def test_coordinate_notes_follow_the_backend_flags() -> None:
    """后端 _result(physical=…, natal_horizon=…)：整体旋转 / 镜像 / 换地方的盘赤经赤纬跟着重算，其余盘的黄经是换算出来的量。"""
    moved_note = "这张盘的黄经是换算出来的量,赤经赤纬、方位高度、出界和赤纬平行仍按星体本来的位置。"
    horizon_note = "地平上下和得时失时取出生时的值,不随变换改。"
    rigid = {"inverted", "sunRise", "superimposed", "antiscia", "contraAntiscia", "geodeticLong", "geodeticRa", "localityArmc", "localityMc"}
    for key in KEYS:
        kind = key.split("/")[0]
        lines = transform_outputs()[key]["lines"]
        if kind in ("persona", "epoch"):
            continue
        if kind in rigid:
            assert moved_note not in lines and horizon_note not in lines, key
        elif kind == "nodeHouses":          # 星不动、四轴落在北交点：坐标按新位置，地平上下仍取本命
            assert moved_note not in lines and horizon_note in lines, key
        else:
            assert moved_note in lines and horizon_note in lines, key


def test_vertical_chart_lists_the_two_solutions_from_the_upstream_golden() -> None:
    rows = golden()["transform_full_B"]["vertical/improved"]["vertical"]
    lines = transform_outputs()["vertical/improved"]["lines"]
    inside = [row for row in rows if not row["outside"]]
    assert len(rows) == 10 and inside
    for row in inside:
        hit = [re.fullmatch(rf"{_NAME[row['id']]} 赤纬 (-?[\d.]+)°:两解 ([\d.]+)° / ([\d.]+)°", line) for line in lines]
        found = [m for m in hit if m]
        assert len(found) == 1, row["id"]
        got = [float(found[0].group(i)) for i in (1, 2, 3)]
        assert got == pytest.approx([row["declination"], row["first"], row["second"]], abs=0.0051), row["id"]
    outside = [row["id"] for row in rows if row["outside"]]
    assert (f"出黄道带:{'、'.join(_NAME[i] for i in outside)}" in lines) is bool(outside)
    # 别的变换没有这张表
    assert not any("两解" in line for line in transform_outputs()["inverted/improved"]["lines"])


def test_node_houses_chart_gives_the_true_cusps_to_the_text() -> None:
    """上游 transformSnapshotChart：北交宫盘盘面画「段头」，给 AI 的宫头 = 段头 + 30°——一宫从北交点起、逆着黄经每宫 30°。"""
    for variant in ("improved", "classic"):
        key = f"nodeHouses/{variant}"
        want = golden()["transform_full_B"][key]
        houses = sorted(transform_outputs()[key]["snapshot_houses"], key=_house_number)
        assert [round(house["lon"], 5) for house in houses] == [round((cusp + 30.0) % 360.0, 5) for cusp in want["cusps"]]
        north_node = dict(want["positions"])["North Node"]
        assert houses[0]["lon"] == pytest.approx(north_node, abs=1e-6)              # 一宫头 = 北交点
        assert houses[1]["lon"] == pytest.approx((north_node - 30.0) % 360.0, abs=1e-6)  # 二宫逆着黄经走 30°
        signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
        assert [house["sign"] for house in houses] == [signs[int(house["lon"] // 30) % 12] for house in houses]
    for key in KEYS:
        if not key.startswith("nodeHouses/"):
            assert transform_outputs()[key]["snapshot_houses"] is None, key


def test_modern_ruler_and_golden_section_lines() -> None:
    lines = transform_outputs()["superimposed/improved"]["lines"]
    want = golden()["transform_full_B"]["superimposed/improved"]
    ruler_lines = [line for line in lines if line.startswith("本命第 ")]
    assert len(ruler_lines) == 12 == len(want["rulers"])
    for row, line in zip(want["rulers"], ruler_lines):
        assert line.startswith(f"本命第 {row['house']} 宫现代宫主:主星 "), line
        for point in row["inside"]:
            assert _NAME[point] in line.split("宫内 ", 1)[1], (row["house"], point)
        assert ("宫内 " in line) is bool(row["inside"]) and ("宫头前 3° " in line) is bool(row["nearCusp"])
    near = [row for row in want["golden"] if row["near"]]
    golden_lines = [line for line in lines if line.startswith("黄金分割点 ")]
    assert len(golden_lines) == len(near)
    for row, line in zip(near, golden_lines):
        m = re.fullmatch(r"黄金分割点 ([\d.]+)°\(比例 ([\d.]+)\):(.+)", line)
        assert float(m.group(1)) == pytest.approx(row["lon"], abs=0.0051) and float(m.group(2)) == pytest.approx(row["ratio"], abs=0.00051)
        assert m.group(3) == "、".join(_NAME[i] for i in row["near"])


# ─────────────────────────── 黄道制：每个版本一条落段金标 ───────────────────────────

_J2000 = 2451545.0
# 西雅图盘的时刻（上游 test_zodiac_systems.py：swisseph.julday(1975, 2, 11, 5.25)）。
_JD = 2442454.71875


def _precession(jd: float) -> float:
    """J2000 起算的黄经总岁差（度）：(5028.796195 t + 1.1054348 t²)″，t 为儒略世纪。"""
    t = (jd - _J2000) / 36525.0
    return (5028.796195 * t + 1.1054348 * t * t) / 3600.0


def _locate(version: str, lon: float) -> tuple[str, float]:
    """手算落段：座头（J2000 表；随岁差移动的版本加岁差）起逐段减座长。"""
    table = golden()["zodiac_tables"][version]
    moves = {row["key"]: row["moves"] for row in live()["zodiac"]["versions"]}[version]
    start = table[0][1] + (_precession(_JD) if moves else 0.0)
    remain = (lon - start) % 360.0
    for sign, _start, length in table:
        if remain < length:
            return sign, remain
        remain -= length
    raise AssertionError((version, lon))


@pytest.mark.parametrize("version", [value for value, _label in V.ZODIAC_VERSIONS])
def test_each_zodiac_version_places_the_points_where_the_version_table_says(version: str) -> None:
    out = zodiac_outputs()[version]
    lines = out["lines"]
    assert out["title"] == "黄道制" and out["version"] == {"value": version, "label": V.ZODIAC_VERSION_LABELS[version]}
    assert lines[0] == f"黄道版本:{V.ZODIAC_VERSION_LABELS[version]}(黄经不变,只换分段)"
    # 各点的回归黄经取上游变换盘金标里的本命位置（地理盘：星不动），与黄道制这一路的结果互为旁证。
    natal = dict(golden()["transform_full_B"]["geodeticLong/improved"]["positions"])
    for point in _TEN:
        hit = [re.match(rf"{_NAME[point]}:回归黄经 ([\d.]+)° · (\S+) ([\d.]+)° · 星座 ", line) for line in lines]
        found = [m for m in hit if m]
        assert len(found) == 1, (version, point)
        sign, inside = _locate(version, natal[point])
        assert float(found[0].group(1)) == pytest.approx(natal[point], abs=0.0051), (version, point)
        assert found[0].group(2) == sign, (version, point, found[0].group(2), sign)
        assert float(found[0].group(3)) == pytest.approx(inside, abs=0.0052), (version, point)


def test_versions_really_differ_and_the_default_is_the_thirteen_sign_table() -> None:
    sun = {version: next(line for line in zodiac_outputs()[version]["lines"] if line.startswith("太阳:回归黄经")) for version, _ in V.ZODIAC_VERSIONS}
    assert len(set(sun.values())) >= 10          # 版本一换，落段行就换（有几个版本对这颗星恰好同段同度）
    assert "· 摩羯 22.54° ·" in sun["z13a"] and "· 水瓶 24.85° ·" in sun["z12a"] and sun["z14"] not in (sun["z13a"], sun["z12a"])
    # 版本只换落段：星座、银河黄道、换星座与十三宫各行逐字相同。
    rest = {version: [line for line in zodiac_outputs()[version]["lines"][2:] if "回归黄经" not in line] for version, _ in V.ZODIAC_VERSIONS}
    assert all(lines == rest["z13a"] for lines in rest.values())


def test_constellation_galactic_and_thirteen_house_lines_match_the_upstream_backend_tests() -> None:
    lines = zodiac_outputs()["z13a"]["lines"]
    # test_build_gives_rows_for_every_version：西雅图盘太阳 con == 'Cap'（摩羯），在黄道上。
    sun = next(line for line in lines if line.startswith("太阳:回归黄经"))
    assert "· 星座 摩羯 · 银河黄道 " in sun and "(黄道外)" not in sun
    # 银心回归黄经：J2000 约 266.84°（上游 test_galactic_center_is_near_the_known_longitude）+ 1975 年的岁差 ≈ −0.349°。
    center = float(re.fullmatch(r"银心回归黄经 ([\d.]+)°", lines[1]).group(1))
    assert center == pytest.approx(266.84 + _precession(_JD), abs=0.06)
    galactic = re.search(r"银河黄道 (\S+) ([\d.]+)°", sun)
    natal_sun = dict(golden()["transform_full_B"]["geodeticLong/improved"]["positions"])["Sun"]
    span = (natal_sun - center) % 360.0
    twelve = ("白羊", "金牛", "双子", "巨蟹", "狮子", "处女", "天秤", "天蝎", "射手", "摩羯", "水瓶", "双鱼")
    assert galactic.group(1) == twelve[int(span // 30)] and float(galactic.group(2)) == pytest.approx(span % 30.0, abs=0.011)
    # test_thirteen_houses_in_payload / test_thirteen_houses_follow_thirteen_sign_lengths：
    houses = next(line for line in lines if line.startswith("十三宫(上升起按十三星座各座长度排宫):"))
    got = {name: (int(house), float(folded)) for name, house, folded in re.findall(r"([^、:]+?) (\d+) 宫\(宫内折 30° 为 ([\d.]+)°\)", houses.split(":", 1)[1])}
    assert [got[_NAME[p]][0] for p in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter")] == [5, 5, 5, 6, 4, 6]
    assert got["太阳"][1] == pytest.approx(22.848, abs=0.051) and got["火星"][1] == pytest.approx(15.744, abs=0.051)
    assert got["上升"] == (1, 0.0)


def test_crossing_lines_cover_every_planet_and_agree_with_the_current_constellation() -> None:
    """上游 test_each_crossing_really_changes_constellation：上次换入的座 == 现在的座 == 下次换出的座。"""
    around = live()["zodiac"]["around"]
    lines = zodiac_outputs()["z13a"]["lines"]
    assert [row["id"] for row in around] == list(_TEN)
    for row in around:
        assert row["last"]["to"] == row["con"] == row["next"]["from"] and row["last"]["from"] != row["last"]["to"]
        assert f"{_NAME[row['id']]} 上次换星座:{row['last']['date']} 自{row['last']['fromName']}" in lines
        assert f"{_NAME[row['id']]} 下次换星座:{row['next']['date']} 入{row['next']['toName']}" in lines
    # 一年跨界表只留页面（上游 aiExportContentAudit：「一年跨界表只留页面」）
    assert live()["zodiac"]["year"] and not any("一年" in line for line in lines)
