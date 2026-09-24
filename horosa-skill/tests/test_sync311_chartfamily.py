"""上游 v3.11.x（Horosa-Public @ 9b74714b，aiExport v57/v58）西占 chart 家族导出快照同步 —— 值级金标。

每组断言都照抄上游 jest 夹具与期望（出处写在各测试 docstring 里），把 skill 的 Python 移植钉在桌面端被测的同一份真值上：

- `utils/__tests__/wholeSignRulers.test.js`：整宫/分宫两表、resolveHouseSystem 矩阵、极区回退与撞名消歧；
- `utils/__tests__/astroClassicalSnapshot.test.js` / `astroV2FactEquivalence.test.js`：[主宰星链] 尾块与 [分宫制宫神星表] 段；
- `utils/__tests__/snapshotTimeBasis.contract.test.js`：时间基准行；
- `components/dice/__tests__/diceChartObjectsTable.test.js`：骰子逆行列与两盘相位；
- `components/germany/__tests__/germanyHamburgSnapshot.test.js`：六宫框落宫 / 校时预览。

其余（比较盘 A/B、二十四节气、正合、恒星轨、节气键显式勾选落空=真取消）按上游源码行为逐字断言，行号见各测试。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from horosa_skill.astro_rulers import (
    DERIVED_WHOLE_SIGN_LABEL,
    HOUSE_SYSTEM_RULERS_COLLAPSED,
    HOUSE_SYSTEM_RULERS_HEADERS,
    RULER_CALIBRE_LINE,
    WHOLE_SIGN_RULERS_HEAD,
    WHOLE_SIGN_RULERS_HEADERS,
    build_house_system_ruler_rows,
    build_whole_sign_ruler_rows,
    house_num_of_id,
    resolve_asc_sign,
    resolve_house_system,
    ruler_of_sign,
    sign_of_lon,
    whole_sign_house_of,
)
from horosa_skill.config import Settings
from horosa_skill.exports.parser import parse_export_content
from horosa_skill.exports.registry import AI_EXPORT_OPTIONAL_SECTIONS, AI_EXPORT_PRESET_SECTIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import (
    HorosaSkillService,
    _build_astro_snapshot_text,
    _build_jieqi_snapshot_text,
    _build_otherbu_snapshot_text,
    _build_relative_snapshot_text,
    _dice_chart_aspect_lines,
    _dice_chart_object_lines,
    _fixed_star_orb_params,
    _germany_house_frames_lines,
    _germany_rectify_lines,
)
from horosa_skill.testing_payloads import build_sample_payloads
from horosa_skill.time_basis import build_time_basis_line, time_basis_label
from test_service import FakeClient, FakeJsClient

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "astro_v2_baseline_chartobj.json"


def _sections(text: str) -> dict[str, list[str]]:
    """[X] 段 → 正文行（与 exports/parser.split_content_sections 同口径：整行 `[X]` 起新段；段尾空行去掉）。

    无头嵌入整盘的子段以 `· X` 标签、空行分隔，仍属父段正文（上游 headerless 契约）。
    """
    out: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in f"{text}".split("\n"):
        if re.fullmatch(r"\[.+\]", line):
            current = out.setdefault(line[1:-1], [])
            continue
        if current is not None:
            current.append(line)
    for title, lines in out.items():
        while lines and not lines[-1].strip():
            lines.pop()
    return out


# ─────────────────────────── wholeSignRulers.js（v57）───────────────────────────
@pytest.mark.parametrize(
    ("chart_obj", "fields", "num", "whole", "label"),
    [
        ({"params": {"hsys": 0}, "chart": {}}, None, "0", True, "整宫制"),
        ({"params": {"hsys": "0"}, "chart": {"hsys": "Whole Sign"}}, None, "0", True, "整宫制"),
        ({"params": {}, "chart": {"hsys": "Whole Sign"}}, None, "0", True, "整宫制"),
        ({"params": {}, "chart": {"hsys": "整宫制"}}, None, "0", True, "整宫制"),
        ({"params": {"hsys": 1}, "chart": {"hsys": "Alcabitius"}}, None, "1", False, "Alcabitus"),
        ({"params": {}, "chart": {"hsys": "Alcabitius"}}, None, "1", False, "Alcabitus"),
        ({"params": {"hsys": 24}, "chart": {"hsys": "Fortuna_Whole"}}, None, "24", False, "福点整宫制"),
        ({"params": {}, "chart": {"hsys": "Fortuna_Whole"}}, None, None, False, "Fortuna_Whole"),
        ({"params": {}, "chart": {"hsys": "福点整宫制"}}, None, "24", False, "福点整宫制"),
        ({"params": {"hsys": 2}, "chart": {"hsys": "Regiomontanus"}}, None, "2", False, "Regiomontanus"),
        ({"params": {}, "chart": {"hsys": "Regiomontanus"}}, None, "2", False, "Regiomontanus"),
        ({"params": {}, "chart": {}}, None, None, False, ""),
        ({"params": {"hsys": 1}, "chart": {"hsys": "Alcabitius"}}, {"hsys": {"value": "0"}}, "0", True, "整宫制"),
        ({"params": {"hsys": 0}, "chart": {"hsys": "Whole Sign"}}, {"hsys": {"value": 3}}, "3", False, "Placidus"),
        ({"params": {"hsys": 0}, "chart": {}}, {"hsys": 24}, "24", False, "福点整宫制"),
    ],
)
def test_resolve_house_system_matrix_matches_upstream_jest(chart_obj, fields, num, whole, label) -> None:
    """wholeSignRulers.test.js「resolveHouseSystem 矩阵」15 例逐条照抄（只有上升整宫制 0/'Whole Sign' 判真；福点整宫制 24 恒假）。"""
    assert resolve_house_system(chart_obj, fields) == {"num": num, "label": label, "isAscWholeSign": whole}


def _frame_house(n: int, sign: str, size: float | None = 30, **extra) -> dict:
    return {"id": f"House{n}", "sign": sign, "lon": 0, "size": size, **extra}


def test_polar_fallback_and_echo_disambiguation_match_upstream_jest() -> None:
    """wholeSignRulers.test.js「极区回退与文本兜底撞名消歧」：表头说真话 + 'Whole Sign'→24 / 'Alcabitus'→8 用盘面自证。"""
    polar = {"params": {"hsys": 3}, "chart": {"hsys": "Placidus", "houses": [
        _frame_house(1, "Aries", 40, hsysFallback="Porphyry"), _frame_house(2, "Taurus", 20, hsysFallback="Porphyry")]}}
    assert resolve_house_system(polar, None) == {"num": "3", "label": "Placidus→回退Porphyry", "isAscWholeSign": False, "fallback": "Porphyry"}
    flatlib_spelling = {"params": {"hsys": 4}, "chart": {"houses": [_frame_house(1, "Aries", 40, hsysFallback="Porphyrius")]}}
    assert resolve_house_system(flatlib_spelling, None)["label"] == "Koch→回退Porphyry"
    fortuna_echo = {"params": {}, "chart": {"hsys": "Whole Sign", "objects": [{"id": "Asc", "sign": "Aries", "lon": 10}], "houses": [_frame_house(1, "Gemini")]}}
    assert resolve_house_system(fortuna_echo, None) == {"num": "24", "label": "福点整宫制", "isAscWholeSign": False}
    real_whole = {"params": {}, "chart": {"hsys": "Whole Sign", "objects": [{"id": "Asc", "sign": "Aries", "lon": 10}], "houses": [_frame_house(1, "Aries")]}}
    assert resolve_house_system(real_whole, None) == {"num": "0", "label": "整宫制", "isAscWholeSign": True}
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    equal_mc = {"params": {}, "chart": {"hsys": "Alcabitus", "houses": [_frame_house(i + 1, s, 30) for i, s in enumerate(signs)]}}
    assert resolve_house_system(equal_mc, None)["num"] == "8"
    quadrant = {"params": {}, "chart": {"hsys": "Alcabitus", "houses": [_frame_house(i + 1, s, 42.5 if i == 3 else 30) for i, s in enumerate(signs)]}}
    assert resolve_house_system(quadrant, None)["num"] == "1"
    # 数字位在场时消歧不介入；奇形回显 trim 后精确匹配、认不出原样且不折叠（安全方向）
    assert resolve_house_system({**fortuna_echo, "params": {"hsys": 0}}, None)["num"] == "0"
    assert resolve_house_system({"params": {}, "chart": {"hsys": "Placidus "}}, None) == {"num": "3", "label": "Placidus", "isAscWholeSign": False}
    assert resolve_house_system({"params": {}, "chart": {"hsys": "placidus"}}, None) == {"num": None, "label": "placidus", "isAscWholeSign": False}
    assert resolve_house_system({"params": {}, "chart": {"hsys": "whole_sign"}}, None) == {"num": None, "label": "whole_sign", "isAscWholeSign": False}


def test_derived_chart_label_is_whole_from_transformed_asc() -> None:
    """[Q-148/T-55]（wholeSignRulers.js:163-201）：派生盘 houses[].hsysDerived='wholeFromAsc' → 标注「整宫(变换后上升)」，
    数字位照旧（isAscWholeSign 仍按请求宫制判）。"""
    chart_obj = {"params": {"hsys": 1}, "chart": {"hsys": "Alcabitus", "houses": [_frame_house(1, "Aries", hsysDerived="wholeFromAsc")]}}
    assert resolve_house_system(chart_obj, None) == {"num": "1", "label": DERIVED_WHOLE_SIGN_LABEL, "isAscWholeSign": False}
    assert DERIVED_WHOLE_SIGN_LABEL == "整宫(变换后上升)"


def _mk_split() -> dict:
    """wholeSignRulers.test.js 截段星座判别盘：Asc 巨蟹 25°、2 宫头处女 2°、太阳狮子 28° 落 House1、月巨蟹 10° 落 House12。"""
    return {
        "chart": {
            "hsys": "Alcabitius",
            "houses": [
                {"id": "House1", "sign": "Cancer", "lon": 115}, {"id": "House2", "sign": "Virgo", "lon": 152}, {"id": "House3", "sign": "Libra", "lon": 185},
                {"id": "House4", "sign": "Scorpio", "lon": 215}, {"id": "House5", "sign": "Sagittarius", "lon": 248}, {"id": "House6", "sign": "Capricorn", "lon": 280},
                {"id": "House7", "sign": "Capricorn", "lon": 295}, {"id": "House8", "sign": "Pisces", "lon": 332}, {"id": "House9", "sign": "Aries", "lon": 5},
                {"id": "House10", "sign": "Taurus", "lon": 35}, {"id": "House11", "sign": "Gemini", "lon": 68}, {"id": "House12", "sign": "Cancer", "lon": 100},
            ],
            "objects": [
                {"id": "Asc", "sign": "Cancer", "lon": 115},
                {"id": "Sun", "sign": "Leo", "lon": 148, "house": "House1"},
                {"id": "Moon", "sign": "Cancer", "lon": 100, "house": "House12"},
                {"id": "Mercury", "sign": "Virgo", "lon": 160, "house": "House2"},
                {"id": "Venus", "sign": "Leo", "lon": 130, "house": "House1"},
                {"id": "Mars", "lon": 250, "house": "House5"},
                {"id": "Jupiter", "sign": "Pisces", "lon": 340, "house": "House8"},
                {"id": "Saturn", "sign": "Capricorn", "lon": 290, "house": "House6"},
            ],
        },
        "params": {"hsys": 1},
        "lots": [],
    }


def test_split_sign_chart_whole_vs_house_system_rows_match_upstream_jest() -> None:
    """wholeSignRulers.test.js「截段星座盘」四例：整宫 2 宫=狮子/日 vs 分宫 2 宫=处女/水；月 1 宫 vs 12 宫；火只有 lon → 射手。"""
    ws = build_whole_sign_ruler_rows(_mk_split())
    hs = build_house_system_ruler_rows(_mk_split())
    assert {k: ws[1][k] for k in ("house", "sign", "ruler", "rulerHouseNum", "rulerSign")} == {"house": 2, "sign": "Leo", "ruler": "Sun", "rulerHouseNum": 2, "rulerSign": "Leo"}
    assert {k: hs[1][k] for k in ("house", "sign", "ruler", "rulerHouseNum", "rulerSign")} == {"house": 2, "sign": "Virgo", "ruler": "Mercury", "rulerHouseNum": 2, "rulerSign": "Virgo"}
    assert (ws[0]["ruler"], ws[0]["rulerHouseNum"]) == ("Moon", 1) and (hs[0]["ruler"], hs[0]["rulerHouseNum"]) == ("Moon", 12)
    aries = next(r for r in ws if r["sign"] == "Aries")
    assert (aries["ruler"], aries["rulerSign"], aries["rulerHouseNum"]) == ("Mars", "Sagittarius", 6)
    assert [r["house"] for r in hs] == list(range(1, 13))
    assert (hs[5]["sign"], hs[5]["ruler"], hs[6]["sign"], hs[6]["ruler"]) == ("Capricorn", "Saturn", "Capricorn", "Saturn")
    assert WHOLE_SIGN_RULERS_HEADERS == ("宫", "整宫星座", "宫主", "宫主落宫(整宫)", "宫主落座")
    assert HOUSE_SYSTEM_RULERS_HEADERS == ("宫", "宫头座", "宫主", "宫主落宫", "宫主落座")


def test_boundaries_match_upstream_jest() -> None:
    """wholeSignRulers.test.js「边界」：上升回退链 / 缺宫主对象 / houses 缺 sign 按 lon 定座、非法宫号跳过 / 基础函数。"""
    assert resolve_asc_sign({"chart": {"houses": [{"id": "House1", "sign": "Leo"}], "objects": []}}) == "Leo"
    assert resolve_asc_sign({"chart": {"houses": [], "objects": [{"id": "Asc", "lon": 200}]}}) == "Libra"
    assert resolve_asc_sign({"chart": {"houses": [{"id": "House1", "lon": 359.9}], "objects": []}}) == "Pisces"
    assert resolve_asc_sign({"chart": {"houses": [], "objects": []}}) is None
    assert build_whole_sign_ruler_rows(None) == [] and build_house_system_ruler_rows(None) == []
    co = {"chart": {"houses": [{"id": "House1", "sign": "Aries"}], "objects": [{"id": "Asc", "sign": "Aries"}, {"id": "Venus"}]}}
    ws = build_whole_sign_ruler_rows(co)
    assert {k: ws[0][k] for k in ("ruler", "rulerFound", "rulerHouseNum")} == {"ruler": "Mars", "rulerFound": False, "rulerHouseNum": None}
    assert {k: ws[1][k] for k in ("ruler", "rulerFound", "rulerHouseNum", "rulerSign")} == {"ruler": "Venus", "rulerFound": True, "rulerHouseNum": None, "rulerSign": None}
    hs = build_house_system_ruler_rows({"chart": {"houses": [{"id": "House2", "lon": 40}, {"id": "House13", "sign": "Leo"}, {"sign": "Leo"}, {"id": "House1", "sign": "Nope"}], "objects": [{"id": "Venus", "sign": "Gemini", "house": "House3"}]}})
    assert hs == [{"house": 2, "sign": "Taurus", "ruler": "Venus", "rulerFound": True, "rulerHouseNum": 3, "rulerHouseId": "House3", "rulerSign": "Gemini"}]
    assert (whole_sign_house_of("Gemini", "Cancer"), whole_sign_house_of("Pisces", "Cancer")) == (12, 9)
    assert (ruler_of_sign("Scorpio"), ruler_of_sign("Aquarius"), ruler_of_sign("Nope")) == ("Mars", "Saturn", None)
    assert (sign_of_lon(-1), sign_of_lon(720), sign_of_lon("abc")) == ("Pisces", "Aries", None)
    assert (house_num_of_id("House 12"), house_num_of_id("House0"), house_num_of_id(None)) == (12, None, None)


# ───────────────── astroAiSnapshot.js：[主宰星链] 尾块 + [分宫制宫神星表]（v57）─────────────────
def _full_chart(**params) -> dict:
    """astroClassicalSnapshot.test.js「AI 四同步补齐」fullChart 夹具（宫头只给 1/4/7/10 四宫）。"""
    return {
        "chart": {
            "isDiurnal": True,
            "stars": [],
            "houses": [
                {"id": "House1", "sign": "Aries", "signlon": 0},
                {"id": "House4", "sign": "Cancer", "signlon": 0},
                {"id": "House7", "sign": "Libra", "signlon": 0},
                {"id": "House10", "sign": "Capricorn", "signlon": 0},
            ],
            "objects": [
                {"id": "Asc", "sign": "Aries", "signlon": 5, "lon": 5},
                {"id": "Sun", "sign": "Aries", "signlon": 29, "house": "House1", "lon": 29},
                {"id": "Moon", "sign": "Scorpio", "signlon": 28, "house": "House8", "lon": 238},
                {"id": "Mars", "sign": "Aries", "signlon": 10, "house": "House1", "lon": 10},
                {"id": "Mercury", "sign": "Pisces", "signlon": 1, "house": "House12", "lon": 331},
                {"id": "Venus", "sign": "Taurus", "signlon": 5, "house": "House2", "lon": 35},
                {"id": "Jupiter", "sign": "Sagittarius", "signlon": 5, "house": "House9", "lon": 245},
                {"id": "Saturn", "sign": "Capricorn", "signlon": 5, "house": "House10", "lon": 275},
            ],
        },
        "params": {"birth": "1991-02-20 14:00:00", "zone": "+08:00", **params},
        "lots": [],
        "aspects": {},
        # `_attach_natal_extras` 的产物：链行来自 JS astroextra（此处给一行代表），宫主两表是纯 Python。
        "_natalExtras": {"主宰星链": "日：日 → 火"},
    }


def test_dispositor_section_carries_whole_sign_ruler_table_per_upstream_jest() -> None:
    """astroClassicalSnapshot.test.js「#79 [主宰星链] = 链行 + 判读口径行 + 整宫制宫主表」（1宫牡羊→火 落第一宫 牡羊；8宫天蝎→火 同落）。"""
    secs = _sections(_build_astro_snapshot_text({}, _full_chart()))
    dispositor = secs["主宰星链"]
    calibre = dispositor.index(RULER_CALIBRE_LINE)
    assert calibre > 0 and "整宫制" in dispositor[calibre] and "nR" in dispositor[calibre] and "[分宫制宫神星表]" in dispositor[calibre]
    assert dispositor[calibre + 1] == "◆ 整宫制宫主表(wholeSignRulers)" == WHOLE_SIGN_RULERS_HEAD
    assert dispositor[calibre + 2] == "| 宫 | 整宫星座 | 宫主 | 宫主落宫(整宫) | 宫主落座 |"
    rows = dispositor[calibre + 4:]
    assert len(rows) == 12
    assert rows[0] == "| 1宫 | 牡羊 | 火 | 第一宫 | 牡羊 |"
    assert rows[7] == "| 8宫 | 天蝎 | 火 | 第一宫 | 牡羊 |"
    assert "houseRows" not in "\n".join(dispositor)
    # 夹具宫头只给 1/4/7/10 四宫 → 分宫表 4 行；整宫表恒 12 行（两表不同源）
    house_system = secs["分宫制宫神星表"]
    assert re.fullmatch(r"◆ 当前分宫制(\(.+\))?宫神星表\(houseRows\)", house_system[0])
    assert house_system[1] == "| 宫 | 宫头座 | 宫主 | 宫主落宫 | 宫主落座 |"
    assert len(house_system[3:]) == 4
    # 段序：紧随 [主宰星链]（aiExportSectionSemantics.test.js「preset 九键皆含且紧随主宰星链」的快照侧对应）
    order = list(secs)
    assert order[order.index("主宰星链") + 1] == "分宫制宫神星表"


def test_house_system_section_collapses_for_asc_whole_sign_only() -> None:
    """astroClassicalSnapshot.test.js「#79 上升整宫制盘(params.hsys=0) 折叠成一行；福点整宫制(24) 不折叠」。"""
    whole = _sections(_build_astro_snapshot_text({}, _full_chart(hsys="0")))
    assert whole["分宫制宫神星表"] == [HOUSE_SYSTEM_RULERS_COLLAPSED]
    assert HOUSE_SYSTEM_RULERS_COLLAPSED == "当前分宫制即整宫制：宫神星表与[主宰星链]段「◆ 整宫制宫主表(wholeSignRulers)」逐行相同，不再重复列出。"
    assert "◆ 整宫制宫主表(wholeSignRulers)" in whole["主宰星链"]
    fortuna = _sections(_build_astro_snapshot_text({}, _full_chart(hsys=24)))["分宫制宫神星表"]
    assert fortuna[0] == "◆ 当前分宫制(福点整宫制)宫神星表(houseRows)"
    assert len(fortuna) > 3


def test_baseline_fixture_split_tables_per_upstream_fact_equivalence() -> None:
    """astroV2FactEquivalence.test.js §7：基线 echo 'Alcabitius' → 表头 Alcabitus；火星（双鱼、后端缺 house）整宫落第九宫、分宫落宫空位。"""
    chart_obj = {**json.loads(FIXTURE.read_text(encoding="utf-8")), "_natalExtras": {"主宰星链": "日：日 → 金"}}
    secs = _sections(_build_astro_snapshot_text({}, chart_obj))
    assert secs["分宫制宫神星表"][0] == "◆ 当前分宫制(Alcabitus)宫神星表(houseRows)"
    ws_rows = [row.split(" | ") for row in secs["主宰星链"] if row.startswith("| ") and "宫主" not in row and "---" not in row]
    hs_rows = [row.split(" | ") for row in secs["分宫制宫神星表"][3:]]
    assert [r[3] for r in ws_rows if r[2] == "火"] == ["第九宫", "第九宫"]
    assert [r[3] for r in hs_rows if r[2] == "火"] == ["", ""]
    assert [r[:3] for r in ws_rows] == [r[:3] for r in hs_rows]   # 基线宫头逐座相接 → 前三列两表同


def test_ruler_sections_need_natal_extras_marker_only_not_js_success() -> None:
    """JS astroextra 失败时 `_attach_natal_extras` 仍挂空 dict：宫主两表（纯 Python）照出，只少链行。"""
    chart_obj = {**_full_chart(), "_natalExtras": {}}
    secs = _sections(_build_astro_snapshot_text({}, chart_obj))
    assert secs["主宰星链"][0] == RULER_CALIBRE_LINE
    assert "分宫制宫神星表" in secs
    # 无标记（非 chart 家族，例 india_chart）→ 两段都不出（上游 IndiaChart 只挑段，不含这两段）。
    bare = {key: value for key, value in _full_chart().items() if key != "_natalExtras"}
    assert "主宰星链" not in _sections(_build_astro_snapshot_text({}, bare))
    assert "分宫制宫神星表" not in _sections(_build_astro_snapshot_text({}, bare))


def test_base_info_marks_derived_chart_houses_as_whole_from_transformed_asc() -> None:
    """[Q-148/T-55]（astroAiSnapshot.js:461-468）：派生盘 [起盘信息]/[信息] 的宫制标注读 houses[].hsysDerived。"""
    chart_obj = _full_chart(hsys=1)
    chart_obj["chart"] = {**chart_obj["chart"], "zodiacal": "Tropical", "hsys": "Alcabitus"}
    plain = _sections(_build_astro_snapshot_text({"hsys": 1}, chart_obj))
    assert "回归黄道，Alcabitus" in plain["起盘信息"]
    derived = json.loads(json.dumps(chart_obj))
    derived["chart"]["houses"] = [{**house, "hsysDerived": "wholeFromAsc"} for house in derived["chart"]["houses"]]
    secs = _sections(_build_astro_snapshot_text({"hsys": 1}, derived))
    assert "回归黄道，整宫(变换后上升)" in secs["起盘信息"]
    assert "回归黄道，整宫(变换后上升)" in secs["信息"]
    assert secs["分宫制宫神星表"][0] == "◆ 当前分宫制(整宫(变换后上升))宫神星表(houseRows)"


# ─────────────────────────── timeBasisLine.js ───────────────────────────
def test_time_basis_line_matches_upstream_contract() -> None:
    """snapshotTimeBasis.contract.test.js「单行格式」三例逐字。"""
    assert build_time_basis_line(time_alg=0) == "时间基准：真太阳时(经度+均时差校正)；晚子时归次日：否；23 点换日：否"
    assert build_time_basis_line() == "时间基准：钟表时(按输入钟面时刻,无真太阳时校正)；晚子时归次日：否；23 点换日：否"
    assert (
        build_time_basis_line(time_alg="2", late_zi_hour_use_next_day=1, after23_new_day="1", zone="+08:00")
        == "时间基准：春分定卯时；晚子时归次日：是；23 点换日：是；时区：+08:00"
    )
    assert "钟表时" in time_basis_label(1)


def test_chart_start_info_carries_time_basis_line_but_info_section_does_not() -> None:
    """astroAiSnapshot.js:442-445 / 1696：只有整盘快照的 [起盘信息] 带 withTimeBasis（timeAlg 1 = 钟表时）；[信息] 复用同函数不带。"""
    secs = _sections(_build_astro_snapshot_text({"lateZiHourUseNextDay": 0, "after23NewDay": 1}, _full_chart()))
    basis = [line for line in secs["起盘信息"] if line.startswith("时间基准：")]
    assert basis == ["时间基准：钟表时(按输入钟面时刻,无真太阳时校正)；晚子时归次日：否；23 点换日：是"]
    assert not [line for line in secs["信息"] if line.startswith("时间基准：")]


# ─────────────────────────── [相位] 正合（Q-254/T-227）───────────────────────────
def test_exact_aspects_are_written_as_zhenghe_not_separating() -> None:
    """astroAiSnapshot.js:719-722：Exact 相态单列「正合」（此前与 Separative 同折「离相」）。基线夹具 日 Exact 木 120° orb 0.01。"""
    chart_obj = json.loads(FIXTURE.read_text(encoding="utf-8"))
    aspects = _sections(_build_astro_snapshot_text({}, chart_obj))["相位"]
    # v2 表化（astroAiSnapshot.js:707-727 ◆标准相位 GFM 表：主体|相位|对象|相态|误差）。
    exact = [line for line in aspects if line.startswith("| ") and "| 120˚ | 木 " in line and line.endswith("| 0.01 |")]
    assert exact and all("| 正合 | 0.01 |" in line for line in exact), exact


# ─────────────────────────── 恒星轨（aiExport.js:6742）───────────────────────────
def test_fixed_star_orb_params_follow_chart_then_default() -> None:
    """classicalChartGlobals.js:271 fixedStarOrbParamsFor：随盘 starOrb/starOrbMode 优先，缺则前端名，再缺全局缺省（1°/school）。"""
    assert _fixed_star_orb_params({}) == {"fixedStarOrb": 1}
    assert _fixed_star_orb_params({"starOrb": 2.5}) == {"fixedStarOrb": 2.5}
    assert _fixed_star_orb_params({"fixedStarOrb": 3}) == {"fixedStarOrb": 3}
    assert _fixed_star_orb_params({"starOrb": "", "fixedStarOrb": 3}) == {"fixedStarOrb": 3}
    assert _fixed_star_orb_params({"starOrbMode": "byMagnitude"}) == {"fixedStarOrb": 1, "fixedStarOrbMode": "byMagnitude"}
    assert _fixed_star_orb_params({"starOrbMode": "school"}) == {"fixedStarOrb": 1}


def _service(tmp_path, *, client=None, chart_client=None, js_client=None) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(
        settings,
        client=client or FakeClient(),
        chart_client=chart_client,
        store=MemoryStore(settings),
        js_client=js_client or FakeJsClient(),
    )


class _CaptureClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        return super().call(endpoint, payload)


def test_classical_analysis_request_forwards_chart_star_orb(tmp_path) -> None:
    """[古典格局] 的 /astroextra/analysis 请求：恒星轨随盘（此前硬编 fixedStarOrb=1）。"""
    client = _CaptureClient()
    service = _service(tmp_path, client=client)
    payload = {**build_sample_payloads()["chart"], "starOrb": 2.5, "starOrbMode": "byMagnitude"}
    result = service.run_tool("chart", payload, save_result=False)
    assert result.ok is True, result.error
    sent = [body for endpoint, body in client.calls if endpoint == "/astroextra/analysis"]
    assert sent and sent[0]["fixedStarOrb"] == 2.5 and sent[0]["fixedStarOrbMode"] == "byMagnitude"


class _AstroExtraDown(FakeJsClient):
    def run(self, tool_name: str, payload: dict) -> dict:
        if tool_name == "astroextra":
            from horosa_skill.errors import ToolTransportError

            raise ToolTransportError("node down", code="js_engine.node_unavailable", details={})
        return super().run(tool_name, payload)


def test_js_extras_failure_keeps_python_ruler_tables_and_warns(tmp_path) -> None:
    """JS astroextra 挂了：链行/12分度/寿命格局缺席并进 warnings，但整宫制宫主表与 [分宫制宫神星表]（纯 Python）照出。"""
    service = _service(tmp_path, js_client=_AstroExtraDown())
    result = service.run_tool("chart", build_sample_payloads()["chart"], save_result=False)
    assert result.ok is True, result.error
    secs = _sections(result.data["snapshot_text"])
    assert secs["主宰星链"][0] == RULER_CALIBRE_LINE
    assert secs["分宫制宫神星表"][0].startswith("◆ 当前分宫制(Alcabitus)宫神星表")
    assert "12分度" not in secs
    assert any("astro natal extras" in warning for warning in result.warnings), result.warnings


def test_chart_family_tools_export_house_system_section_offline(tmp_path) -> None:
    """九键（chart 家族）preset 登记 + 快照实产 [分宫制宫神星表]：missing/unknown 皆空。"""
    service = _service(tmp_path)
    for tool in ("chart", "chart13", "chart12", "hellen_chart", "harmonic", "draconic", "relocation", "acg"):
        result = service.run_tool(tool, build_sample_payloads()[tool], save_result=False)
        assert result.ok is True, (tool, result.error)
        export = result.data["export_snapshot"]
        assert "分宫制宫神星表" in export["section_titles_detected"], tool
        assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == [], (tool, export["missing_selected_sections"], export["unknown_detected_sections"])


# ─────────────────────────── registry（aiExport.js:595-625/857-861）───────────────────────────
def test_presets_place_new_sections_at_upstream_positions() -> None:
    for key in ("astrochart", "astrochart_like", "hellenastro", "dwadasamsa", "harmonic", "draconic", "relocation", "acg", "mundane"):
        preset = AI_EXPORT_PRESET_SECTIONS[key]
        assert preset[preset.index("主宰星链") + 1] == "分宫制宫神星表", key
    assert AI_EXPORT_PRESET_SECTIONS["astrochart_like"] == [
        "起盘信息", "宫位宫头", "星与虚点", "信息", "相位", "行星", "月宿", "希腊点", "12分度", "主宰星链", "分宫制宫神星表",
        "古典", "古典格局", "埃及历", "寿命格局", "可能性", "占星地图",
    ]
    relative = AI_EXPORT_PRESET_SECTIONS["relative"]
    assert relative[relative.index("B对A反映点") + 1: relative.index("B对A反映点") + 3] == ["比较盘-星盘A", "比较盘-星盘B"]
    assert AI_EXPORT_PRESET_SECTIONS["otherbu"][-2:] == ["骰子盘相位", "天象盘相位"]
    germany = AI_EXPORT_PRESET_SECTIONS["germany"]
    assert germany[germany.index("中点列表") + 1: germany.index("中点列表") + 3] == ["六宫框落宫", "校时预览"]
    assert AI_EXPORT_PRESET_SECTIONS["jieqi"][:2] == ["节气盘参数", "二十四节气"]
    # 条件段双登记（AGENTS §5.5）
    for key, titles in {
        "relative": ("比较盘-星盘A", "比较盘-星盘B"),
        "otherbu": ("骰子盘相位", "天象盘相位"),
        "germany": ("六宫框落宫", "校时预览"),
        "jieqi": ("二十四节气",),
    }.items():
        assert set(titles) <= set(AI_EXPORT_OPTIONAL_SECTIONS[key]), key


# ─────────────────────────── relative（AstroRelative.js:150-205）───────────────────────────
def _party_chart(birth: str) -> dict:
    chart = _full_chart(hsys=0)
    chart["params"] = {**chart["params"], "birth": birth, "lon": "121e28", "lat": "31n13"}
    chart["chart"] = {**chart["chart"], "hsys": "Whole Sign", "zodiacal": "Tropical"}
    return chart


def _relative_payload(mode: int, **extra) -> dict:
    return {
        "inner": {"name": "甲", "date": "2028-04-06", "time": "09:33:00", "lon": "121e28", "lat": "31n13"},
        "outer": {"name": "乙", "date": "1992-03-02", "time": "08:18:00", "lon": "121e28", "lat": "31n13"},
        "hsys": 0,
        "zodiacal": 0,
        "relative": mode,
        **extra,
    }


def test_relative_header_prints_house_system_and_zodiac_labels() -> None:
    """[Q-255/T-238·AS-22⑪]（AstroRelative.js:151-159）：出人话标签，此前直出数字「宫制：1」「黄道：0」。"""
    head = _sections(_build_relative_snapshot_text(_relative_payload(0, hsys=1), {}))["关系起盘信息"]
    assert "宫制：Alcabitus" in head and "黄道：回归黄道" in head
    sidereal = _sections(_build_relative_snapshot_text(_relative_payload(0, zodiacal=1, siderealAyanamsa="lahiri"), {}))["关系起盘信息"]
    assert "黄道：恒星黄道·Lahiri / Chitrapaksha" in sidereal and "宫制：整宫制" in sidereal
    bare_sidereal = _sections(_build_relative_snapshot_text(_relative_payload(0, zodiacal=1), {}))["关系起盘信息"]
    assert "黄道：恒星黄道" in bare_sidereal


def test_relative_comp_mode_embeds_both_full_charts_headerless() -> None:
    """[Q-441/T-404]（AstroRelative.js:168-181）：比较盘页签把 inner(A)/outer(B) 两盘无头整盘嵌入（段头转 `· X`）。"""
    response = {"inToOutAsp": [], "inner": _party_chart("2028-04-06 09:33:00"), "outer": _party_chart("1992-03-02 08:18:00")}
    secs = _sections(_build_relative_snapshot_text(_relative_payload(0), response))
    for title, birth in (("比较盘-星盘A", "2028-04-06 09:33:00"), ("比较盘-星盘B", "1992-03-02 08:18:00")):
        body = secs[title]
        assert body[0] == "· 起盘信息" and birth in "\n".join(body)
        for sub in ("· 星与虚点", "· 相位", "· 主宰星链", "· 分宫制宫神星表"):
            assert sub in body, (title, sub)
        assert not [line for line in body if re.fullmatch(r"\[.+\]", line)]   # 无整行段头（否则会被切成顶层段）
    # 比较盘的 inner/outer 不再冒充「影响图盘」；影响图盘只属影响盘/马克斯盘页签（AstroRelative.js:194-205），比较盘不出该段。
    assert "影响图盘-星盘A" not in secs and "影响图盘-星盘B" not in secs


def test_relative_synastry_mode_keeps_influence_charts_and_no_comp_sections() -> None:
    response = {"inner": _party_chart("2028-04-06 09:33:00"), "outer": _party_chart("1992-03-02 08:18:00")}
    secs = _sections(_build_relative_snapshot_text(_relative_payload(2), response))
    assert "比较盘-星盘A" not in secs and "比较盘-星盘B" not in secs
    # 影响盘两盘 = buildAstroSnapshotContent(res.inner, null, {headerless:true}) 全口径（AstroRelative.js:199/204），不再是旧的缩略行式。
    assert secs["影响图盘-星盘A"][0] == "· 起盘信息"


class _RelativeCompClient(FakeClient):
    """/modern/relative 比较盘（relative=0）真实形状：互摄相位数组 + inner/outer 两张完整 chart-wrap。"""

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/modern/relative":
            natal = super().call("/chart", {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00"})
            other = super().call("/chart", {"date": "1992-03-02", "time": "08:18:00", "zone": "+08:00"})
            return {"inToOutAsp": [{"id": "Sun", "objects": [{"id": "Moon", "aspect": 90, "delta": 0.5}]}], "inner": natal, "outer": other}
        if endpoint == "/astroextra/relative":
            # 真实形状（astroextra.relative_score）：契合分 + 顺畅/张力连接。
            return {
                "score": 66.0,
                "highlights": [{"a": "Moon", "b": "Mars", "aspect": 60, "impact": 2.892, "orb": 0.289}],
                "challenges": [{"a": "Uranus", "b": "Sun", "aspect": 90, "impact": -2.351, "orb": 0.163}],
            }
        return super().call(endpoint, payload)


def test_relative_comp_pipeline_enriches_embedded_charts(tmp_path) -> None:
    """整条流水线：比较盘两盘经 `_attach_relative_comp_charts` 富化（JS 链行/12分度/寿命格局）后无头嵌入，导出干净。"""
    service = _service(tmp_path, client=_RelativeCompClient())
    result = service.run_tool("relative", build_sample_payloads()["relative"], save_result=False)
    assert result.ok is True, result.error
    export = result.data["export_snapshot"]
    assert {"比较盘-星盘A", "比较盘-星盘B"} <= set(export["section_titles_detected"])
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []
    body = _sections(result.data["snapshot_text"])["比较盘-星盘A"]
    assert "· 12分度" in body and "· 寿命格局" in body and "日：日 → 火" in body   # FakeJsClient astroextra 的链 [Sun, Mars]


# ─────────────────────────── otherbu（DiceMain.js:72-170）───────────────────────────
def test_dice_object_table_marks_retrograde_per_upstream_jest() -> None:
    """diceChartObjectsTable.test.js「逆行标记」：lonspeed<0 标「逆」，其余 —；表头逐字。"""
    chart_obj = {"chart": {"houses": [{"id": "House1"}], "objects": [
        {"id": "Mars", "house": "House1", "signlon": 28.9, "sign": "Leo", "lonspeed": -0.2},
        {"id": "Sun", "house": "House1", "signlon": 15.3, "sign": "Taurus", "lonspeed": 0.98},
        {"id": "Asc", "house": "House1", "signlon": 1.0, "sign": "Aries"},
    ]}}
    lines = _dice_chart_object_lines(chart_obj)
    text = "\n".join(lines)
    assert lines[0] == "| 宫位 | 星体 | 度 | 座 | 分 | 逆行 |"
    assert re.search(r"\| 火 \| 28 \| 狮子 \| 53 \| 逆 \|", text)
    assert re.search(r"\| 日 \| 15 \| 金牛 \| 18 \| — \|", text)
    assert "| — | 上升 | 1 | 牡羊 | 0 | — |" in lines
    assert _dice_chart_object_lines({"chart": {"houses": [{"id": "House2"}], "objects": []}})[2] == "| 第二宫 | 无 | — | — | — | — |"


def test_dice_aspect_lines_per_upstream_jest() -> None:
    """diceChartObjectsTable.test.js「相位段」：normalAsp 四态各成行（Exact/Separative 同折离相）；无 aspects → []（不产段）。"""
    chart_obj = {"chart": {"objects": [{"id": "Sun"}, {"id": "Moon"}], "aspects": {"normalAsp": {
        "Sun": {"Applicative": [{"id": "Moon", "asp": 120, "orb": 2.5347}], "Exact": [], "Separative": [{"id": "Mars", "asp": 90, "orb": 0}], "None": [{"id": "Venus", "asp": 60}]},
    }}}}
    lines = _dice_chart_aspect_lines(chart_obj)
    assert lines[0] == "| 主体 | 相位 | 对象 | 相态 | 误差 |"
    assert "| 日 | 120˚ | 月 | 入相 | 2.535 |" in lines
    assert "| 日 | 90˚ | 火 | 离相 | 0 |" in lines
    assert "| 日 | 60˚ | 金 | — |  |" in lines
    assert _dice_chart_aspect_lines({"chart": {"objects": []}}) == []


def test_dice_snapshot_pool_line_result_labels_and_aspect_sections() -> None:
    """buildDiceSnapshotText：[Q-145/T-52] 掷星星池行；骰子结果译名；有 normalAsp 才出两盘相位段（逐字镜像上游取数路径）。"""
    chart_obj = {"chart": {"houses": [{"id": "House1"}], "objects": [{"id": "Sun", "house": "House1", "signlon": 3, "sign": "Aries"}]}}
    upstream_shaped = {**chart_obj, "chart": {**chart_obj["chart"], "aspects": {"normalAsp": {"Sun": {"Applicative": [{"id": "Moon", "asp": 60, "orb": 1}]}}}}}
    text = _build_otherbu_snapshot_text(
        {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lon": "121e28", "lat": "31n13", "tradition": True, "question": "问"},
        {"planet": "Venus", "sign": "Libra", "house": 6, "diceChart": upstream_shaped, "chart": chart_obj},
    )
    secs = _sections(text)
    assert "掷星星池：传统七政 + 交点 / 虚点(不含三王星)(背景盘面仍按完整星集绘制)" in secs["起盘信息"]
    assert secs["骰子结果"] == ["行星：金", "星座：天秤", "宫位：第七宫"]
    assert "骰子盘相位" in secs and "天象盘相位" not in secs
    live_shaped = {**chart_obj, "aspects": {"normalAsp": {"Sun": {"Applicative": [{"id": "Moon", "asp": 60, "orb": 1}]}}}}
    # 后端 /predict/dice 把 aspects 放在 chartObj 顶层（getChartObj）；上游 builder 读 chartObj.chart.aspects → 不产段。照镜像。
    assert _dice_chart_aspect_lines(live_shaped) == []
    assert "掷星星池：含三王星的完整星集(背景盘面仍按完整星集绘制)" in _sections(_build_otherbu_snapshot_text({"tradition": False}, {"house": 0}))["起盘信息"]


# ─────────────────────────── germany（AstroMidpoint.js:405-468）───────────────────────────
_GERMANY_PTS = [{"id": "Sun", "lon": 10.0}, {"id": "Moon", "lon": 100.0}, {"id": "MC", "lon": 270.0}, {"id": "Asc", "lon": 0.0}]


def _equal_cusps(first: float) -> list[float]:
    return [((first + i * 30) % 360 + 360) % 360 for i in range(12)]


def test_house_frames_table_per_upstream_jest() -> None:
    """germanyHamburgSnapshot.test.js「六宫框全框×全点表」：placements 缺则按 cusps 定宫；无 frames → 空。"""
    result = {"houseFrames": {"frames": {
        "meridian": {"cusps": _equal_cusps(0), "placements": {"Sun": 1, "Moon": 4, "MC": 10, "Asc": 1}},
        "sun": {"cusps": _equal_cusps(280)},
        "earth": {"cusps": _equal_cusps(180), "placements": {"Sun": 7}},
    }}}
    lines = _germany_house_frames_lines(result, _GERMANY_PTS)
    assert lines[0].startswith("（子午局=东点 1 宫头·天顶 10 宫头赤道分宫")
    assert lines[1] == "| 点 | 子午局 | 太阳局 | 地球局 |"
    assert "| 日 | 1 | 4 | 7 |" in lines
    assert "| 月 | 4 | 7 | 10 |" in lines
    assert _germany_house_frames_lines({}, _GERMANY_PTS) == []


def test_rectify_preview_per_upstream_jest() -> None:
    """germanyHamburgSnapshot.test.js「校时预览」：出生 1990-01-01，事件 2000-01-01 ≈ 10 年 → Naibod 弧 ≈ 9.85°；
    MC 270+9.85 vs 木星 280 → 90°盘角距 0.15 命中；末行命中合计。无事件不产段。"""
    birth = {"date": "1990/01/01", "time": "12:00:00"}
    assert _germany_rectify_lines(birth, [], _GERMANY_PTS) == []
    points = [*_GERMANY_PTS, {"id": "Jupiter", "lon": 280.0}]
    lines = _germany_rectify_lines(birth, [{"label": "升职", "date": "2000-01-01", "type": "career"}], points)
    assert lines[0] == "（已录事件推进 MC/Asc 看是否触动本命因子，只预览不改盘；盘基 90°·容许 1°·太阳弧 Naibod；1°MC≈4 分钟出生时间）"
    assert lines[1] == "| 事件 | 类型 | 日期 | 弧° | 命中(轴→本命因子·角距) |"
    row = next(line for line in lines if line.startswith("| 升职 |"))
    assert re.match(r"^\| 升职 \| 事业 \| 2000-01-01 \| 9\.8\d \| .*MC→木·0\.1\d°", row), row
    # 值级：(3651.5 天 / 365.2422) × 0.9856473 = 9.85397…° → '9.85'；七个等距命中（MC/Asc × 日/月/木 + …）按角距升序
    assert "| 9.85 |" in row
    assert re.fullmatch(r"命中合计：\d+", lines[-1])
    unnamed = _germany_rectify_lines(birth, [{"date": "not-a-date"}], points)
    assert "| 事件1 | 其他 | — | — | 无命中 |" in unnamed and unnamed[-1] == "命中合计：0"


class _GermanyCaptureClient(_CaptureClient):
    def call(self, endpoint: str, payload: dict) -> dict:
        out = super().call(endpoint, payload)
        if endpoint == "/germany/midpoint":
            out = {**out, "houseFrames": {"frames": {"ascendant": {"cusps": _equal_cusps(150)}}}}
        return out


def test_germany_pipeline_emits_frames_and_rectify_without_leaking_events_to_backend(tmp_path) -> None:
    client = _GermanyCaptureClient()
    service = _service(tmp_path, client=client)
    payload = {**build_sample_payloads()["germany"], "rectifyEvents": [{"date": "2030-01-01", "type": "move", "label": "迁居"}]}
    result = service.run_tool("germany", payload, save_result=False)
    assert result.ok is True, result.error
    secs = _sections(result.data["snapshot_text"])
    assert secs["六宫框落宫"][1] == "| 点 | 上升局 |"
    assert any(line.startswith("| 迁居 | 迁居 | 2030-01-01 |") for line in secs["校时预览"])
    order = list(secs)
    assert order.index("中点列表") < order.index("六宫框落宫") < order.index("校时预览")
    assert all("rectifyEvents" not in body for _, body in client.calls)
    export = result.data["export_snapshot"]
    assert {"六宫框落宫", "校时预览"} <= set(export["section_titles_detected"])
    assert export["unknown_detected_sections"] == []


# ─────────────────────────── jieqi（JieQiChartsMain.js:880-933）───────────────────────────
def _jieqi_seed_row(term: str, time: str, year: str, month: str, day: str, hour: str) -> dict:
    """Java /jieqi/year（JieQiController.setupBazi）的逐节气形状：bazi.fourColumns.<柱>.ganzi（外带大量神煞/卦字段）。"""
    col = lambda gz: {"ganzi": gz, "naying": "纳音", "goodGods": [], "stem": {"cell": gz[0]}}   # noqa: E731
    return {"ord": 0, "jieqi": term, "jie": True, "time": time, "ad": 1,
            "bazi": {"fourColumns": {"year": col(year), "month": col(month), "day": col(day), "time": col(hour)}}}


def test_jieqi_snapshot_24_terms_table_full_charts_and_3d_pointer() -> None:
    chart = _party_chart("2028-03-20 10:17:20")
    chart["params"] = {**chart["params"], "hsys": 1, "name": "春分"}
    response = {
        "charts": {"春分": chart},
        "_jieqi24Seed": [_jieqi_seed_row("立春", "2028-02-04 15:31:25", "戊申", "乙丑", "己未", "壬申"),
                          _jieqi_seed_row("春分", "2028-03-20 10:17:20", "戊申", "乙卯", "甲辰", "己巳")],
    }
    payload = {"year": 2028, "zone": "+08:00", "lon": "121e28", "lat": "31n13", "jieqis": ["春分", "夏至"]}
    secs = _sections(_build_jieqi_snapshot_text(payload, response))
    assert list(secs)[:3] == ["节气盘参数", "二十四节气", "春分星盘"]
    table = secs["二十四节气"]
    assert table[:2] == ["| 节气 | 交节时刻 | 年柱 | 月柱 | 日柱 | 时柱 |", "| --- | --- | --- | --- | --- | --- |"]
    assert "| 立春 | 2028-02-04 15:31:25 | 戊申 | 乙丑 | 己未 | 壬申 |" in table
    # [Q-224/T-180] 未拉到的分至盘明示（行落在当时的末段 = [二十四节气]）
    assert table[-1] == "说明：夏至的星盘 / 宿盘尚未拉取（打开对应页签后再导出即纳入）。"
    # [Q-446/T-409] 星盘段 = 全口径无头整盘；3D 段 = 一行指引
    star = secs["春分星盘"]
    assert star[0] == "· 起盘信息" and "· 相位" in star and "· 主宰星链" in star
    assert secs["春分3D盘"] == ["3D 盘为「春分星盘」同一节气盘的三维视图(星位/宫位/相位同上 [春分星盘] 段,无独立数据)。"]
    assert "夏至星盘" not in secs


class _JieqiJavaClient(FakeClient):
    """Java 聚合层：/jieqi/year 给全年 24 节气 + 四柱（上游页面种子请求同路）。"""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        if endpoint == "/jieqi/year":
            return {"jieqi24": [_jieqi_seed_row("小寒", "2028-01-06 03:54:50", "丁未", "壬子", "庚寅", "戊寅")], "charts": {}}
        return super().call(endpoint, payload)


class _JieqiChartClient(FakeClient):
    """Python chart 服务：/jieqi/year 只回所请求的分至项 + 分至盘，无四柱。"""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        if endpoint == "/jieqi/year":
            terms = list(payload.get("jieqis") or [])
            chart = super().call("/chart", {"date": "2028-03-20", "time": "10:17:20", "zone": "+08:00"})
            return {"jieqi24": [{"jieqi": term, "time": "2028-03-20 10:17:20"} for term in terms], "charts": {term: chart for term in terms}}
        return super().call(endpoint, payload)


def test_jieqi_pipeline_takes_24_terms_seed_from_java(tmp_path) -> None:
    java, chart = _JieqiJavaClient(), _JieqiChartClient()
    service = _service(tmp_path, client=java, chart_client=chart)
    result = service.run_tool("jieqi_year", build_sample_payloads()["jieqi_year"], save_result=False)
    assert result.ok is True, result.error
    seed_calls = [body for endpoint, body in java.calls if endpoint == "/jieqi/year"]
    assert seed_calls and "jieqis" not in seed_calls[0] and "seedOnly" not in seed_calls[0] and seed_calls[0]["timeAlg"] == 0
    assert [endpoint for endpoint, _ in chart.calls].count("/jieqi/year") == 1
    secs = _sections(result.data["snapshot_text"])
    assert "| 小寒 | 2028-01-06 03:54:50 | 丁未 | 壬子 | 庚寅 | 戊寅 |" in secs["二十四节气"]
    assert "· 主宰星链" in secs["春分星盘"]
    export = result.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


class _JieqiJavaDown(_JieqiJavaClient):
    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/jieqi/year":
            from horosa_skill.errors import ToolTransportError

            raise ToolTransportError("java down", code="transport.connection_error", details={})
        return super().call(endpoint, payload)


def test_jieqi_seed_failure_degrades_with_warning_not_silently(tmp_path) -> None:
    service = _service(tmp_path, client=_JieqiJavaDown(), chart_client=_JieqiChartClient())
    result = service.run_tool("jieqi_year", build_sample_payloads()["jieqi_year"], save_result=False)
    assert result.ok is True, result.error
    assert "二十四节气" not in _sections(result.data["snapshot_text"])
    assert any("二十四节气" in warning for warning in result.warnings), result.warnings
    assert result.data["export_snapshot"]["missing_selected_sections"] == []


# ─────────────────────────── parser（aiExport.js:3547-3552）───────────────────────────
def test_jieqi_explicit_selection_matching_nothing_is_a_true_cancel() -> None:
    """[挂载自检 F-38]：节气盘整键/分键显式勾选的段本内容没有 → ''（不回吐全文）；其他技法保留「回退剥后文」兜底。"""
    content = "[春分星盘]\n· 起盘信息\n盘\n\n[春分宿盘]\n宿"
    assert parse_export_content(technique="jieqi_xiazhi", content=content, selected_sections=["夏至星盘"])["export_text"] == ""
    assert parse_export_content(technique="jieqi", content=content, selected_sections=["夏至星盘"])["export_text"] == ""
    assert parse_export_content(technique="jieqi", content=content)["export_text"].startswith("[春分星盘]")
    assert parse_export_content(technique="jieqi", content=content, selected_sections=["春分宿盘"])["export_text"] == "[春分宿盘]\n宿"
    other = parse_export_content(technique="astrochart", content="[起盘信息]\n甲", selected_sections=["相位"])
    assert other["export_text"] == "[起盘信息]\n甲"


# ─────────────────────────── live（显式点名的 vendored 实例；AGENTS §8）───────────────────────────
from test_local_js_tools import make_service as _live_service  # noqa: E402
from test_local_js_tools import requires_chart, requires_runtime  # noqa: E402


def _table_rows(lines: list[str], skip: int) -> list[list[str]]:
    return [[cell.strip() for cell in row.strip().strip("|").split("|")] for row in lines[skip:] if row.startswith("|")]


@requires_chart
def test_live_derived_chart_label_and_whole_sign_table_round_trip_backend_nr(tmp_path) -> None:
    """chart13（十三分盘，后端 thirteenthchart.py 每宫打 hsysDerived）：[起盘信息] 标「整宫(变换后上升)」；
    [主宰星链] 的整宫制宫主表与后端 perchart 的 ruleHouses（nR 宫主标记）逐星互为反查（上游「对拍」同款）。"""
    result = _live_service(tmp_path).run_tool("chart13", build_sample_payloads()["chart13"], save_result=False)
    assert result.ok is True, result.error
    secs = _sections(result.data["snapshot_text"])
    assert any(line.endswith("，整宫(变换后上升)") for line in secs["起盘信息"]), secs["起盘信息"]
    assert secs["分宫制宫神星表"][0] == "◆ 当前分宫制(整宫(变换后上升))宫神星表(houseRows)"
    names = {"Sun": "日", "Moon": "月", "Mercury": "水", "Venus": "金", "Mars": "火", "Jupiter": "木", "Saturn": "土"}
    head = secs["主宰星链"].index(WHOLE_SIGN_RULERS_HEAD)
    ws_rows = _table_rows(secs["主宰星链"], head + 3)
    assert len(ws_rows) == 12
    checked = 0
    for obj in result.data["chart"]["objects"]:
        if obj.get("id") in names and isinstance(obj.get("ruleHouses"), list):
            ruled = sorted(int(str(house).replace("House", "")) for house in obj["ruleHouses"])
            assert ruled == sorted(int(row[0].rstrip("宫")) for row in ws_rows if row[2] == names[obj["id"]]), obj["id"]
            checked += 1
    assert checked >= 5


@requires_chart
def test_live_polar_placidus_fallback_label(tmp_path) -> None:
    """极圈内 Placidus 无解 → 后端兜底 Porphyry 并逐宫打 hsysFallback（flatlib swe.py:337-359）；分宫表表头说真话。"""
    payload = {**build_sample_payloads()["chart"], "hsys": 3, "lat": "78n13", "gpsLat": 78.2167}
    result = _live_service(tmp_path).run_tool("chart", payload, save_result=False)
    assert result.ok is True, result.error
    assert _sections(result.data["snapshot_text"])["分宫制宫神星表"][0] == "◆ 当前分宫制(Placidus→回退Porphyry)宫神星表(houseRows)"


@requires_chart
def test_live_relative_comp_embeds_both_charts(tmp_path) -> None:
    result = _live_service(tmp_path).run_tool("relative", build_sample_payloads()["relative"], save_result=False)
    assert result.ok is True, result.error
    export = result.data["export_snapshot"]
    assert {"比较盘-星盘A", "比较盘-星盘B"} <= set(export["section_titles_detected"])
    secs = _sections(result.data["snapshot_text"])
    assert "2028-04-06 09:33:00" in "\n".join(secs["比较盘-星盘A"]) and "1992-03-02 08:18:00" in "\n".join(secs["比较盘-星盘B"])
    assert "宫制：整宫制" in secs["关系起盘信息"] and "黄道：回归黄道" in secs["关系起盘信息"]


@requires_chart
def test_live_germany_house_frames_mirror_backend_placements(tmp_path) -> None:
    """后端 houseFrames（webgermanysrv.py:99-106 缺省即带）→ [六宫框落宫]：每格 = 后端 frames[key].placements[id]
    （缺则按 cusps 定宫）。值级：上升局上升=1 宫、交点局北交=1 宫（houseframes.py 锚点即 1 宫头）。
    ⚠ 太阳局太阳/月亮局太阴恰落宫头（☉−90°+90° 的浮点往返），后端 _house_of 可判到前一宫——表照后端，不「纠正」。"""
    result = _live_service(tmp_path).run_tool("germany", build_sample_payloads()["germany"], save_result=False)
    assert result.ok is True, result.error
    table = _sections(result.data["snapshot_text"])["六宫框落宫"]
    labels = ["子午局", "上升局", "太阳局", "月亮局", "交点局", "地球局"]
    assert table[1] == f"| 点 | {' | '.join(labels)} |"
    rows = {row[0]: row[1:] for row in _table_rows(table, 3)}
    assert rows["上升"][1] == "1" and rows["北交"][4] == "1"
    frames = result.data["raw"]["houseFrames"]["frames"]
    for column, key in enumerate(("meridian", "ascendant", "sun", "moon", "node", "earth")):
        placements = frames[key]["placements"]
        for point_id, cn in (("Sun", "日"), ("Moon", "月"), ("Asc", "上升"), ("MC", "中天"), ("North Node", "北交"), ("AriesPoint", "白羊点")):
            if point_id in placements:
                assert rows[cn][column] == str(placements[point_id]), (key, point_id)


@requires_chart
def test_live_dice_tables_and_mirrored_aspect_path(tmp_path) -> None:
    """骰子两盘表带逆行列；后端把 aspects 放在 chartObj 顶层，上游 builder 读 chartObj.chart.aspects → 两盘相位段不产（照镜像）。"""
    result = _live_service(tmp_path).run_tool("otherbu", build_sample_payloads()["otherbu"], save_result=False)
    assert result.ok is True, result.error
    secs = _sections(result.data["snapshot_text"])
    assert secs["骰子盘宫位与星体"][0] == "| 宫位 | 星体 | 度 | 座 | 分 | 逆行 |"
    assert isinstance(result.data["diceChart"].get("aspects"), dict) and "aspects" not in result.data["diceChart"]["chart"]
    assert "骰子盘相位" not in secs and "天象盘相位" not in secs


@requires_runtime
def test_live_jieqi_24_terms_carry_java_four_pillars(tmp_path) -> None:
    """[二十四节气] 种子行取 Java /jieqi/year（setupBazi）。值级：2028 春分行四柱 = 戊申 乙卯 甲辰 己巳——
    年柱 2028=甲子(1984)+44=戊申；日柱按儒略日数 (JDN−11) mod 60（2028-03-20 JDN 2461851 → 40 = 甲辰）；
    月柱 戊年卯月 = 乙卯（五虎遁）；时柱 甲日巳时 = 己巳（五鼠遁）。立春前两节（小寒/大寒）年柱仍为丁未。"""
    result = _live_service(tmp_path).run_tool("jieqi_year", build_sample_payloads()["jieqi_year"], save_result=False)
    assert result.ok is True, result.error
    rows = _table_rows(_sections(result.data["snapshot_text"])["二十四节气"], 2)
    assert len(rows) == 24
    spring = next(row for row in rows if row[0] == "春分")
    assert spring[2:] == ["戊申", "乙卯", "甲辰", "己巳"], spring
    assert [row[2] for row in rows if row[0] in {"小寒", "大寒"}] == ["丁未", "丁未"]
