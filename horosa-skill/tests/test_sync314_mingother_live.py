"""上游 v3.14.0 同步 · 命 · 其他：东亚诸术 / 诸方杂术——对真引擎（vendored chart 服务）的 live 验证。

离线契约在 test_sync314_mingother_contract.py（桩后端 + 真 JS），子术金标在 horosa-core-js/test/selfcheck.mjs。这里验的是只有真后端
才答得了的事：
- 人类图：闸门 / 爻按公开定义从黄经手推（轮起点 302°、每闸门 5.625°、每爻 0.9375°），与后端回的逐点比对；设计时刻 = 太阳少 88° 弧。
- 灵名字母：上游 astropy/tests/data/golden_spirit_names.json 的 41 例（原样拷贝）经 skill 的 zhufang 工具逐例重放。
- 性别 A/B：东亚诸术随性别变（→ 进 GENDER_FACT_TOOLS），诸方杂术不变（→ 不进）。
- 宫制 / 黄道 / 交点 / 象限：真的改结果。
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
from test_local_js_tools import make_service, requires_chart

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SPIRIT = json.loads((FIXTURES / "sync314_mingother_spirit_names_golden.json").read_text(encoding="utf-8"))
CONFIRMED = {"agent_confirmed_settings": True}
BIRTH = {"date": "1975-02-10", "time": "21:15:00", "zone": "-08:00", "lat": "47n36", "lon": "122w20"}
# 人类图轮（公开定义）：自水瓶 2°（黄经 302°）起的 64 闸门顺序。
GATE_WHEEL = [41, 19, 13, 49, 30, 55, 37, 63, 22, 36, 25, 17, 21, 51, 42, 3, 27, 24, 2, 23, 8, 20, 16, 35, 45, 12, 15, 52, 39, 53,
              62, 56, 31, 33, 7, 4, 29, 59, 40, 64, 47, 6, 46, 18, 48, 57, 32, 50, 28, 44, 1, 43, 14, 34, 9, 5, 26, 11, 10, 58, 38, 54, 61, 60]
HD_NAME = {"Sun": "太阳", "Moon": "月亮", "Mercury": "水星", "Venus": "金星", "Mars": "火星", "Jupiter": "木星", "Saturn": "土星"}

pytestmark = requires_chart


def _ok(service: Any, tool: str, payload: dict[str, Any]) -> Any:
    result = service.run_tool(tool, payload, save_result=False)
    assert result.ok, (result.error.code if result.error else None, result.error.message if result.error else None)
    export = result.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []
    return result


def _section(text: str, title: str) -> list[str]:
    lines = text.split("\n")
    at = lines.index(f"[{title}]")
    out: list[str] = []
    for line in lines[at + 1:]:
        if line.startswith("[") and line.endswith("]"):
            break
        out.append(line)
    return out


def _gate_line(lon: float) -> tuple[int, int]:
    v = (lon - 302.0) % 360.0
    return GATE_WHEEL[int(v // 5.625) % 64], min(int((v % 5.625) // 0.9375) + 1, 6)


def test_dongya_live_reads_the_natal_planets_and_follows_gender_house_system_and_zodiac(tmp_path: Path) -> None:
    """真 /chart：七政七行；性别改流年八卦；宫制改宫卦 / 按地平合卦；恒星黄道改度卦。

    负向对照：GENDER_FACT_TOOLS 留着 dongya 而 runner 不把 gender 交给 JS → female / male 两行相同，第一条断言红。"""
    service = make_service(tmp_path)
    base = _ok(service, "dongya", {**CONFIRMED, **BIRTH, "gender": 0, "flowYear": 2026})
    text = base.data["snapshot_text"]
    iching = _section(text, "易卦星盘")
    planet_rows = [line for line in iching if "度卦" in line]
    assert len(planet_rows) == 7 and {line.split("(")[0] for line in planet_rows} == set(HD_NAME.values())
    assert base.data["compute_sources"]["natal_chart"] == "chart_service" and base.warnings == []
    # 太阳行按本命盘黄经手推：先天圆图每 5.625° 一卦（度卦环与座卦表取自 vendored 表，这里只验「读的是这张盘的太阳」）。
    sun = next(o for o in base.data["chart"]["objects"] if o["id"] == "Sun")
    assert abs(sun["lon"] - 321.85) < 0.05  # 1975-02-10 21:15 PST 太阳在水瓶 21°51′
    assert next(line for line in planet_rows if line.startswith("太阳(乾)")).startswith("太阳(乾):度卦 22 山火贲")
    # 性别 A/B：只有 [藏占] 的流年八卦行变（53 岁：女命离、男命坎）。
    male = _ok(service, "dongya", {**CONFIRMED, **BIRTH, "gender": 1, "flowYear": 2026}).data["snapshot_text"]
    assert _section(text, "藏占")[0].startswith("2026 年 53 岁(女命):流年八卦 离")
    assert _section(male, "藏占")[0].startswith("2026 年 53 岁(男命):流年八卦 坎")
    diff = [(a, b) for a, b in zip(text.split("\n"), male.split("\n"), strict=True) if a != b]
    assert len(diff) == 1 and diff[0][0].startswith("2026 年 53 岁")
    # 宫制：上海 1998-02-20 20:48 的太阳在整宫制（0）落 6 宫、Alcabitus（1，缺省）落 5 宫 → 宫卦按十二辟卦序
    # （1 宫泰、2 大壮、3 夬、4 乾、5 姤、6 遁 …）从「33 遁」变「44 姤」；六段本机算的不变。
    shanghai = {**CONFIRMED, "date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1, "flowYear": 2026}
    whole = _ok(service, "dongya", {**shanghai, "hsys": 0})
    alcabitius = _ok(service, "dongya", shanghai)
    house = lambda result: next(o for o in result.data["chart"]["objects"] if o["id"] == "Sun")["house"]  # noqa: E731
    assert (house(whole), house(alcabitius)) == ("House6", "House5")
    sun_of = lambda result: next(line for line in _section(result.data["snapshot_text"], "易卦星盘") if line.startswith("太阳(乾)"))  # noqa: E731
    assert ";宫卦 33 天山遁 → " in sun_of(whole) and ";宫卦 44 天风姤 → " in sun_of(alcabitius)
    assert whole.data["snapshot_text"].split("[易卦星盘]")[0] == alcabitius.data["snapshot_text"].split("[易卦星盘]")[0]
    # 恒星黄道：黄经减岁差约 23.5° → 太阳度卦换卦（321.85° → 298.4°：环上第 57 格 → 第 53 格）。
    sidereal = _ok(service, "dongya", {**CONFIRMED, **BIRTH, "gender": 0, "flowYear": 2026, "zodiacal": 1}).data["snapshot_text"]
    sun_row = next(line for line in _section(sidereal, "易卦星盘") if line.startswith("太阳(乾)"))
    assert not sun_row.startswith("太阳(乾):度卦 22 山火贲"), sun_row


def test_zhufang_live_human_design_gates_follow_the_public_definition(tmp_path: Path) -> None:
    """后端回的每个点的闸门 / 爻 = 按公开定义从它的黄经手推的值；地球 = 太阳 + 180°；设计太阳 = 个人太阳 − 88°。
    快照行逐点印的就是这些数。"""
    service = make_service(tmp_path)
    result = _ok(service, "zhufang", {**CONFIRMED, **BIRTH, "hsys": 3})
    hd = result.data["remote"]["humanDesign"]
    for group in ("personality", "design"):
        assert len(hd[group]) == 13
        for row in hd[group]:
            assert (row["gate"], row["line"]) == _gate_line(row["lon"]), (group, row)
    p = {row["id"]: row for row in hd["personality"]}
    d = {row["id"]: row for row in hd["design"]}
    assert math.isclose((p["Earth"]["lon"] - p["Sun"]["lon"]) % 360, 180.0, abs_tol=1e-6)
    assert math.isclose((p["Sun"]["lon"] - d["Sun"]["lon"]) % 360, 88.0, abs_tol=1e-4)
    assert 85 < hd["birthJd"] - hd["designJd"] < 93
    # 这张盘的手推结论（与 selfcheck 的排版金标同盘）：太阳 321.85° → 49.4；通道 4-63 / 23-43 / 28-38 → 投射者、脾权威、4/6、二分人。
    lines = _section(result.data["snapshot_text"], "人类图")
    assert lines[0] == "类型 投射者 · 内在权威 直觉(脾) · 人生角色 4/6(机会主义者 / 角色模范) · 二分人"
    assert lines[3] == "通道:4-63、23-43、28-38"
    assert lines[4].startswith("个人(出生):太阳 49.4 · 地球 4.4 · ")
    assert result.warnings == [] and result.data["compute_sources"]["humanDesign"] == "chart_service"
    # 平交点：只动交点两行的数（上游 test_mean_node_option_changes_only_the_nodes）。
    mean = _ok(service, "zhufang", {**CONFIRMED, **BIRTH, "hsys": 3, "hdTrueNode": False})
    mean_hd = mean.data["remote"]["humanDesign"]
    assert mean_hd["trueNode"] is False
    for a, b in zip(hd["personality"], mean_hd["personality"], strict=True):
        assert ("Node" in a["id"]) == (abs(a["lon"] - b["lon"]) > 1e-6), a["id"]
    assert _section(mean.data["snapshot_text"], "人类图")[1].endswith("交点 平交点")


@pytest.mark.parametrize("case", SPIRIT["cases"], ids=lambda c: f"{c['datetime']}@{c['lon']}q{c['quadrant']}")
def test_zhufang_live_reproduces_the_upstream_spirit_name_goldens(tmp_path: Path, case: dict[str, Any]) -> None:
    """上游灵名字母金标 41 例：五要点投字序号 / 象限四宫投字序号，经 skill 的 zhufang 工具整条链（上游请求体映射 → 后端 → 排版）。"""
    date, time = case["datetime"].split(" ")
    result = _ok(make_service(tmp_path), "zhufang", {
        **CONFIRMED, "date": date, "time": time, "zone": SPIRIT["zone"], "lat": SPIRIT["lat"], "lon": case["lon"],
        "hsys": SPIRIT["hsys"], "spiritQuadrant": case["quadrant"],
    })
    spirit = result.data["remote"]["spiritNames"]
    lines = _section(result.data["snapshot_text"], "灵名字母")
    if "ibnEzra" in case:
        assert [row["letter"]["index"] for row in spirit["ibnEzra"]] == case["ibnEzra"]
        # 快照的五要点行印的就是这五个序号。
        assert [int(part.rsplit("(", 1)[1].rstrip(")")) for part in lines[0].removeprefix("五要点:").split(";")] == case["ibnEzra"]
    if "quadrantLetters" in case:
        assert [row["letter"]["index"] for row in spirit["quadrantRows"]] == case["quadrantLetters"]
        assert lines[2].startswith(f"象限 {case['quadrant']}:")


def test_zhufang_live_ignores_gender_and_follows_house_system_and_quadrant(tmp_path: Path) -> None:
    """诸方杂术不随性别变（所以不进 GENDER_FACT_TOOLS）；宫制改十一宫 / 象限宫头的度数主星；象限换一组宫。"""
    service = make_service(tmp_path)
    base = _ok(service, "zhufang", {**CONFIRMED, **BIRTH, "hsys": 3}).data["snapshot_text"]
    for gender in (0, 1):
        assert _ok(service, "zhufang", {**CONFIRMED, **BIRTH, "hsys": 3, "gender": gender}).data["snapshot_text"] == base
    alcabitius = _ok(service, "zhufang", {**CONFIRMED, **BIRTH, "hsys": 1}).data["snapshot_text"]
    assert _section(base, "灵名字母")[1] == "十一宫度数主星 土星(巨蟹 12.82°)→ מ Mem"
    assert _section(alcabitius, "灵名字母")[1] == "十一宫度数主星 木星(双鱼 21.60°)→ ל Lamed"
    assert _section(base, "人类图") == _section(alcabitius, "人类图")  # 人类图不读宫位
    quad3 = _ok(service, "zhufang", {**CONFIRMED, **BIRTH, "hsys": 3, "spiritQuadrant": 3}).data["snapshot_text"]
    assert _section(quad3, "灵名字母")[2].startswith("象限 3:") and _section(quad3, "灵名字母")[2] != _section(base, "灵名字母")[2]
    # 恒星黄道给了不生效：结果逐字相同，并在 warnings 里说明。
    sidereal = service.run_tool("zhufang", {**CONFIRMED, **BIRTH, "hsys": 3, "zodiacal": 1}, save_result=False)
    assert sidereal.ok and sidereal.data["snapshot_text"] == base and any("zodiacal=1" in note for note in sidereal.warnings)


def test_both_tools_take_a_place_name_and_resolve_the_zone_from_it(tmp_path: Path) -> None:
    """标准入口：只给地名（不给坐标 / 时区）——坐标与那一天的时区由地名解析；东亚诸术的藏历日界、诸方杂术的灵名字母都随之算。
    1988-07-01 上海在夏令时（+09:00）：时区取错的话人类图的月亮闸门 / 藏历日都会偏。"""
    service = make_service(tmp_path)
    place = {**CONFIRMED, "date": "1988-07-01", "time": "08:30:00", "place": "上海"}
    explicit = {**CONFIRMED, "date": "1988-07-01", "time": "08:30:00", "zone": "+09:00", "lat": "31n14", "lon": "121e28"}
    dongya = _ok(service, "dongya", {**place, "gender": 1, "flowYear": 2026})
    assert dongya.input_normalized["zone"] == "+09:00" and dongya.input_normalized["lon"].startswith("121e")
    same = _ok(service, "dongya", {**explicit, "gender": 1, "flowYear": 2026, "lat": dongya.input_normalized["lat"], "lon": dongya.input_normalized["lon"]})
    assert dongya.data["snapshot_text"] == same.data["snapshot_text"]
    zhufang = _ok(service, "zhufang", place)
    assert zhufang.data["request"]["zone"] == "+09:00" and zhufang.data["request"]["date"] == "1988/07/01"
    wrong_zone = _ok(service, "zhufang", {**explicit, "zone": "+08:00", "lat": zhufang.input_normalized["lat"], "lon": zhufang.input_normalized["lon"]})
    assert _section(zhufang.data["snapshot_text"], "人类图") != _section(wrong_zone.data["snapshot_text"], "人类图")

