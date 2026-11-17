"""上游 v3.14.0 辅盘「变换盘」「黄道制」：对真引擎的 live 用例（@requires_chart：只打 chart 服务，不需要 Java）。

逐个变换 / 逐个黄道版本跑一遍工具本身（run_tool：归一化 → 请求 → 富化 → 导出契约），期望值仍是上游自己的后端金标
（fixtures/sync314_labs_upstream_golden.json，出处见 test_sync314_labs_goldens.py）与手算的落段。
"""
from __future__ import annotations

import json
import re

import pytest
from float_tree import float_tree_diff
from skips import needs_upstream, upstream_path
from test_local_js_tools import make_service, requires_chart
from test_sync314_labs_goldens import (
    _JD,
    _NAME,
    _TEN,
    KEYS,
    _house_number,
    _locate,
    _precession,
    golden,
)

from horosa_skill import auxlab_vocab as V
from horosa_skill.exports.registry import (
    AI_EXPORT_OPTIONAL_SECTIONS,
    AI_EXPORT_PRESET_SECTIONS,
)
from horosa_skill.testing_payloads import build_sample_payloads

# 上游 astropy/tests/test_transform_charts.py FULL_CHARTS：B 西雅图 / S 悉尼（南半球），均 hsys=1、回归黄道。
BIRTH_B = {"date": "1975-02-10", "time": "21:15:00", "zone": "-08:00", "lat": "47n36", "lon": "122w20", "hsys": 1, "zodiacal": 0,
           "agent_confirmed_settings": True}
BIRTH_S = {"date": "1962-11-03", "time": "05:40:00", "zone": "+10:00", "lat": "33s52", "lon": "151e13", "hsys": 1, "zodiacal": 0,
           "agent_confirmed_settings": True}
_GOLDEN_FULL = "Horosa-Web/astropy/tests/data/golden_transform_full.json"


def _extra(key: str) -> dict:
    """与上游 full_snapshot 同一组选项（基准星月亮、宫头 4），只给这种变换用得上的。"""
    kind, variant = key.split("/")
    options = V.TRANSFORM_KIND_OPTIONS[kind]
    extra: dict = {"transformKind": kind}
    if "variant" in options:
        extra["transformVariant"] = variant
    if "planet" in options:
        extra["transformPlanet"] = "Moon"
    if "house" in options:
        extra["transformHouse"] = 4
    return extra


def _sections(text: str) -> list[str]:
    return re.findall(r"^\[(.+?)\]$", text, re.MULTILINE)


def _assert_matches(result, want: dict, key: str) -> None:
    assert result.ok is True, (key, result.error)
    data = result.data
    export = data["export_snapshot"]
    assert export["missing_selected_sections"] == [], (key, export["missing_selected_sections"])
    assert export["unknown_detected_sections"] == [], (key, export["unknown_detected_sections"])
    # 金标在 macOS 录、Windows 载荷是 MSVC 编的同一份引擎：浮点末位会差，按容差比（tests/float_tree.py；金标黄经已舍到 6 位 → 1e-6）。
    assert float_tree_diff([[row["id"], row["lon"]] for row in data["positions"]], want["positions"], abs_tol=1e-6) == [], key
    raw_houses = sorted(data["raw"]["chart"]["chart"]["houses"], key=_house_number)
    assert float_tree_diff([house["lon"] for house in raw_houses], want["cusps"], abs_tol=1e-6) == [], key
    assert raw_houses[0].get("hsysDerived") == want["derived"], key
    assert data["transform"]["moment"] == want["moment"], key
    assert float_tree_diff(data.get("vertical"), want["vertical"]) == [], key
    titles = _sections(data["snapshot_text"])
    preset = AI_EXPORT_PRESET_SECTIONS["transformchart"]
    assert titles == [title for title in preset if title in titles], key
    assert set(preset) - set(titles) <= set(AI_EXPORT_OPTIONAL_SECTIONS["transformchart"]), (key, set(preset) - set(titles))
    assert "可能性" not in titles and "古典格局" not in titles and titles[-1] == "变换盘", key
    assert data["params_ignored"] == [], key


@requires_chart
@pytest.mark.parametrize("key", KEYS)
def test_live_every_transform_kind_equals_the_upstream_full_golden(tmp_path, key: str) -> None:
    result = make_service(tmp_path).run_tool("transformchart", {**BIRTH_B, **_extra(key)}, save_result=False)
    _assert_matches(result, golden()["transform_full_B"][key], key)
    if key.startswith("nodeHouses/"):
        north_node = dict(golden()["transform_full_B"][key]["positions"])["North Node"]
        first = next(house for house in result.data["chart"]["houses"] if house["id"] == "House1")
        assert first["lon"] == pytest.approx(north_node, abs=1e-6)      # 正文与结构化数据用真宫头


@requires_chart
@needs_upstream(_GOLDEN_FULL)
@pytest.mark.parametrize("kind", V.TRANSFORM_KINDS)
def test_live_southern_chart_equals_the_upstream_full_golden(tmp_path, kind: str) -> None:
    """悉尼盘（南半球）：上游金标另一半，直接读上游文件。"""
    full = json.loads(upstream_path(_GOLDEN_FULL).read_text(encoding="utf-8"))
    key = f"{kind}/improved"
    result = make_service(tmp_path).run_tool("transformchart", {**BIRTH_S, **_extra(key)}, save_result=False)
    _assert_matches(result, full[f"S/{key}"], f"S/{key}")


@requires_chart
def test_live_superimposed_tables_equal_the_upstream_golden(tmp_path) -> None:
    result = make_service(tmp_path).run_tool("transformchart", {**BIRTH_B, **_extra("superimposed/improved")}, save_result=False)
    want = golden()["transform_full_B"]["superimposed/improved"]
    assert result.data["rulers"] == want["rulers"]
    assert float_tree_diff(result.data["golden"], want["golden"]) == []


@requires_chart
def test_live_shift_changes_the_houses_and_variant_changes_the_angles(tmp_path) -> None:
    """「改这个参数，结果必须变」：宫位同转、经典 / 改进两档、基准星、对应宫头。"""
    service = make_service(tmp_path)

    def run(**extra) -> dict:
        result = service.run_tool("transformchart", {**BIRTH_B, **extra}, save_result=False)
        assert result.ok is True, result.error
        return result.data

    def lon(data: dict, point: str) -> float:
        return next(row["lon"] for row in data["positions"] if row["id"] == point)

    still, moved = run(transformKind="superimposed"), run(transformKind="superimposed", transformShift=True)
    assert lon(still, "Asc") == pytest.approx(lon(still, "Asc") , abs=1e-9) and abs(lon(still, "Asc") - lon(moved, "Asc")) > 1.0
    assert "宫位:不动" in still["snapshot_text"] and "宫位:随之旋转" in moved["snapshot_text"]
    improved, classic = run(transformKind="inverted"), run(transformKind="inverted", transformVariant="classic")
    assert abs(lon(improved, "Asc") - lon(classic, "Asc")) == pytest.approx(180.0, abs=1e-6)      # 经典档四轴留在本命
    assert lon(improved, "Sun") == pytest.approx(lon(classic, "Sun"), abs=1e-9)
    moon, saturn = run(transformKind="planetCentered", transformPlanet="Moon"), run(transformKind="planetCentered", transformPlanet="Saturn")
    assert abs(lon(moon, "Sun") - lon(saturn, "Sun")) > 0.01
    assert "基准星:月亮" in moon["snapshot_text"] and "基准星:土星" in saturn["snapshot_text"]
    first, fourth = run(transformKind="epoch", transformHouse=1), run(transformKind="epoch", transformHouse=4)
    assert first["transform"]["moment"] != fourth["transform"]["moment"]


@requires_chart
def test_live_sidereal_transform_carries_the_lunar_mansions(tmp_path) -> None:
    result = make_service(tmp_path).run_tool(
        "transformchart", {**BIRTH_B, "zodiacal": 1, "siderealAyanamsa": "lahiri", "transformKind": "inverted"}, save_result=False)
    assert result.ok is True, result.error
    export = result.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []
    assert "月宿" in _sections(result.data["snapshot_text"])


@requires_chart
def test_live_polar_epoch_has_no_moment(tmp_path) -> None:
    result = make_service(tmp_path).run_tool(
        "transformchart", {**BIRTH_B, "lat": "78n13", "lon": "15e38", "transformKind": "epoch", "transformHouse": 1}, save_result=False)
    assert result.ok is False and result.error.code == "tool.transformchart_empty"
    assert result.error.details["reason"] == "moment_failed"


@requires_chart
@pytest.mark.parametrize("version", [value for value, _label in V.ZODIAC_VERSIONS])
def test_live_every_zodiac_version(tmp_path, version: str) -> None:
    result = make_service(tmp_path).run_tool("zodiacsystems", {**BIRTH_B, "zodiacVersion": version}, save_result=False)
    assert result.ok is True, (version, result.error)
    data = result.data
    export = data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []
    assert _sections(data["snapshot_text"]) == ["黄道制"]
    assert data["version"] == version and data["versionLabel"] == V.ZODIAC_VERSION_LABELS[version]
    lines = data["snapshot_text"].splitlines()
    assert lines[1] == f"黄道版本:{V.ZODIAC_VERSION_LABELS[version]}(黄经不变,只换分段)"
    natal = dict(golden()["transform_full_B"]["geodeticLong/improved"]["positions"])
    for point in _TEN:
        found = [m for m in (re.match(rf"{_NAME[point]}:回归黄经 ([\d.]+)° · (\S+) ([\d.]+)° · 星座 ", line) for line in lines) if m]
        assert len(found) == 1, (version, point)
        sign, inside = _locate(version, natal[point])
        assert found[0].group(2) == sign and float(found[0].group(3)) == pytest.approx(inside, abs=0.0052), (version, point)
    center = float(re.fullmatch(r"银心回归黄经 ([\d.]+)°", lines[2]).group(1))
    assert center == pytest.approx(266.84 + _precession(_JD), abs=0.06)


@requires_chart
def test_live_zodiac_result_does_not_depend_on_house_system_or_zodiac(tmp_path) -> None:
    """auxlab_vocab.ZODIAC_UNUSED_CHART_KEYS 的依据：宫制不参与；恒星黄道盘只有朔望点的回归黄经差约 1″，落段全同。"""
    service = make_service(tmp_path)

    def run(**extra) -> dict:
        result = service.run_tool("zodiacsystems", {**BIRTH_B, **extra}, save_result=False)
        assert result.ok is True, result.error
        return result.data

    base = run()
    for hsys in (0, 3):
        assert run(hsys=hsys)["snapshot_text"] == base["snapshot_text"], hsys
    sidereal = run(zodiacal=1, siderealAyanamsa="lahiri")
    differing = [row["id"] for row, other in zip(base["rows"], sidereal["rows"]) if abs(row["lon"] - other["lon"]) > 1e-9]
    assert differing in ([], ["Syzygy"])
    assert all(abs(row["lon"] - other["lon"]) < 0.001 for row, other in zip(base["rows"], sidereal["rows"]))
    assert [(row["con"], row["versions"]["z13a"]["sign"], (row["houses13"] or {}).get("house")) for row in base["rows"]] == [
        (row["con"], row["versions"]["z13a"]["sign"], (row["houses13"] or {}).get("house")) for row in sidereal["rows"]]
    assert sidereal["around"] == base["around"] and sidereal["year"] == base["year"]


@requires_chart
@pytest.mark.parametrize("tool", ["transformchart", "zodiacsystems"])
def test_live_sample_payloads_run_clean(tmp_path, tool: str) -> None:
    result = make_service(tmp_path).run_tool(tool, build_sample_payloads()[tool], save_result=False)
    assert result.ok is True, result.error
    export = result.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []
    assert result.data["technique_card"]["compute"].get("matches_declaration") is not False
