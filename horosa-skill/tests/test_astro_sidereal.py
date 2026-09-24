"""恒星黄道 ayanāṃśa (A) + 西洋月宿 nakshatra (B) 的离线单测（星阙 v2.6.4 平价）。

不依赖 live 后端 —— 直接给 _build_astro_snapshot_text 喂合成 perchart 响应，断言：
  · sidereal 盘按 chart.siderealAyanamsa 真实标注岁差名（Raman≠Lahiri，修原硬编码 bug）；
  · sidereal 盘按 chart.nakshatras 出「月宿」段；tropical 盘两者都不出。
"""
from __future__ import annotations

from horosa_skill.astro_sidereal import (
    INDIA_HOUSE_SYSTEM_LABELS,
    SIDEREAL_AYANAMSA_LABELS,
    nakshatra_lord_cn,
    sidereal_ayanamsa_label,
)
from horosa_skill.service import _build_astro_snapshot_text, _build_india_snapshot_text, _build_nakshatra_lines


def _chart_response(*, sidereal: bool, ayan: str = "") -> dict:
    chart: dict = {
        "zodiacal": "Sidereal" if sidereal else "Tropical",
        "hsys": "Whole Sign",
        "houses": [{"id": "House1", "lon": 0.0}],
        "objects": [
            {"id": "Sun", "lon": 280.0, "house": "House1"},
            {"id": "Moon", "lon": 95.0, "house": "House1"},
        ],
        "siderealAyanamsa": ayan if sidereal else "",
    }
    if sidereal:
        chart["nakshatras"] = {
            "Sun": {"index": 21, "name": "Uttara Ashadha", "label": "牛", "lord": "Sun", "pada": 2},
            "Moon": {"index": 8, "name": "Pushya", "label": "柳", "lord": "Saturn", "pada": 1},
        }
    return {"chart": chart, "params": {"birth": "2000-01-01 12:00", "zone": "8", "lon": "121e", "lat": "31n"}}


def test_constants_complete() -> None:
    assert len(SIDEREAL_AYANAMSA_LABELS) == 47
    assert len(INDIA_HOUSE_SYSTEM_LABELS) == 24
    assert sidereal_ayanamsa_label("raman") == "Raman"
    assert sidereal_ayanamsa_label("") == "Lahiri / Chitrapaksha"  # 缺省回退
    assert sidereal_ayanamsa_label("unknown_key") == "unknown_key"  # 未知原样
    assert nakshatra_lord_cn("Ketu") == "计都"
    assert nakshatra_lord_cn("") == ""


def test_nakshatra_lines_sidereal_only() -> None:
    lines = _build_nakshatra_lines(_chart_response(sidereal=True, ayan="lahiri"))
    assert any("Uttara Ashadha·牛" in ln and "宿主太阳" in ln and "第2足" in ln for ln in lines)
    assert any("Pushya·柳" in ln and "宿主土星" in ln for ln in lines)
    # tropical → no nakshatras key → empty
    assert _build_nakshatra_lines(_chart_response(sidereal=False)) == []


def test_astro_snapshot_sidereal_raman() -> None:
    # 上游 astroAiSnapshot.js:457-467：黄道行 = zodiacalDisplayText(zodiacal, ayanKey) → 「恒星黄道·<岁差名>，<宫制>」一行
    # （v3.11 起不再另起「恒星黄道岁差：」行）。
    snap = _build_astro_snapshot_text({"zodiacal": 1, "siderealAyanamsa": "raman"}, _chart_response(sidereal=True, ayan="raman"))
    assert "恒星黄道·Raman，整宫制" in snap  # 真实岁差，非硬编码 Lahiri
    assert "Lahiri" not in snap
    assert "[月宿]" in snap


def test_astro_snapshot_sidereal_default_lahiri() -> None:
    # 后端解析后 chart.siderealAyanamsa='lahiri'（缺省）：fields 缺岁差键 → 回显兜底（ayanKey = fieldValue || chart.siderealAyanamsa）
    snap = _build_astro_snapshot_text({"zodiacal": 1}, _chart_response(sidereal=True, ayan="lahiri"))
    assert "恒星黄道·Lahiri / Chitrapaksha，整宫制" in snap
    assert "[月宿]" in snap


def test_astro_snapshot_tropical_no_sidereal_extras() -> None:
    snap = _build_astro_snapshot_text({"zodiacal": 0}, _chart_response(sidereal=False))
    assert "恒星黄道岁差" not in snap
    assert "[月宿]" not in snap
    assert "回归黄道" in snap


def test_india_chart_input_passthrough() -> None:
    # C: IndiaChartInput 声明 indiaHsys/indiaAyanamsa，model_dump 透传给后端 webindiasrv。
    from horosa_skill.schemas.tools import IndiaChartInput

    inp = IndiaChartInput(
        date="1998-02-20", time="20:48", zone="+08:00", lat="31n13", lon="121e28",
        indiaHsys=3, indiaAyanamsa="raman",
    )
    dumped = inp.model_dump(exclude_none=True)
    assert dumped["indiaHsys"] == 3
    assert dumped["indiaAyanamsa"] == "raman"


def test_india_chart_guidance_enumerates() -> None:
    # C: india_chart 策略枚举 24 分宫 + 47 岁差，agent 可发现。
    from horosa_skill.agent_guidance import build_tool_input_contract

    contract = build_tool_input_contract("india_chart")
    blob = str(contract)
    assert "indiaHsys" in blob and "indiaAyanamsa" in blob
    assert "24" in blob and "47" in blob


def test_india_snapshot_replaces_the_zodiac_line_with_the_calibre_line() -> None:
    # 印占盘响应可能不带 siderealAyanamsa：岁差名由 runner 按上游 indiaCalibreLine（后端回显 → 请求 indiaAyanamsa 回退）
    # 派生成 `_indiaCalibreLine`（见 test_sync311_w3b_gim 的 live 回放），整盘按 buildIndiaSnapshotText 把 [起盘信息] 首条黄道行换成它；
    # 无口径行时保留 buildAstroSnapshotContent 自己的黄道行（不再有 skill 自拟的「恒星黄道岁差：」行）。
    chart = {"zodiacal": "Sidereal", "hsys": "KP / Placidus", "houses": [], "objects": [], "siderealAyanamsa": ""}
    resp = {"chart": chart, "params": {"birth": "1998-02-20 20:48"}}
    fields = {"indiaHsys": 3, "indiaAyanamsa": "raman"}
    plain = _build_india_snapshot_text(fields, resp).split("\n\n")[0].split("\n")
    assert plain[0] == "[起盘信息]"
    zodiac = [line for line in plain if line.startswith(("恒星黄道", "回归黄道"))]
    assert len(zodiac) == 1 and zodiac[0].endswith("，KP / Placidus"), zodiac
    with_line = _build_india_snapshot_text(fields, {**resp, "_indiaCalibreLine": "恒星黄道·Raman，KP / Placidus"}).split("\n\n")[0].split("\n")
    assert "恒星黄道·Raman，KP / Placidus" in with_line
    assert [line for line in with_line if line.startswith(("恒星黄道", "回归黄道"))] == ["恒星黄道·Raman，KP / Placidus"]
    assert not any("恒星黄道岁差：" in line for line in with_line)
