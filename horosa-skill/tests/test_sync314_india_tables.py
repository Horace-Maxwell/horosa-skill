"""上游 v3.14.0（Horosa-Public e55c3a66）印占三张新表 + 合盘八重合 + 印度择日带印占全文（sync314 · india 批）。

- india_chart 多三段：[Yoga 判定表] / [印占补充表]（随 `/india/chart` 的 jyotish.yogaTable / extraTables）与 [穿界时刻]
  （另取 `/astroextra/transitevents`，所选三项是入参 indiaTransitPlanet / indiaTransitKind / indiaTransitDays）；
- relative 多一段 [八重合]（另取 `/astroextra/ashtakoota`；男方 = ashtakootaMaleSide，缺省按两人 gender）；
- indiazeri 的正文 = 印占全文 + 择时三段（展示盘 = 命中首刻的 india_chart，岁差 / 罗计交点跟扫描口径）。

服务级用例跑**真 JS 引擎**（vendored 上游 utils/indiaExtraTables.js）+ 录制回放的 HTTP 桩
（fixtures/sync314_india_live.json，vendored v3.14.0 实例 chart :8877 实抓）。

期望值的独立来源（不是把本仓输出抄成期望）：
- 上游后端金标 `astropy/tests/data/golden_india_tables.json`：charts['beijing-1990']（Yoga 成立数 / 条目号、Graha Samaya、
  Dirah 合计两档、Sphuta 黄经）与 pairs['a']（八重合八项分、合计两套、男女方月亮宿 / 座）——数值抄在下面的 UPSTREAM_GOLDEN_*，
  `test_literals_equal_the_upstream_golden` 在有上游检出时逐值对回上游文件；
- 上游前端 jest 用例（utils/__tests__/indiaExtraTables.test.js / indiaTablesSnapshotSettings.test.js）里的行文写法；
- 穿界表的行：按录制回包的原始行用本文件自己的小公式（上游 transitEventText / extraPointName 的表）独立排出来比对。

每条负向对照都实跑过，注在各用例的 docstring 里。
"""

from __future__ import annotations

from skips import upstream_source  # 上游拆文件后读「门面 + 子模块」全集（v3.15.0）
import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeClient
from skips import needs_upstream, upstream_path
from test_local_js_tools import make_service, requires_chart
from test_sync311_w3b_gim import _section, _service, requires_node

from horosa_skill.errors import ToolTransportError, ToolValidationError
from horosa_skill.exports.registry import AI_EXPORT_OPTIONAL_SECTIONS, AI_EXPORT_PRESET_SECTIONS

FIX = json.loads((Path(__file__).resolve().parent / "fixtures" / "sync314_india_live.json").read_text(encoding="utf-8"))

# ── 上游 astropy/tests/data/golden_india_tables.json（e55c3a66）──────────────────────────────────────────────
UPSTREAM_GOLDEN_BEIJING = {
    "yogaHitIds": [7, 30, 31, 41, 46, 47, 67, 69, 71],          # 改进档成立的条目号（9 条）
    "yogaClassicHitIds": [30, 31, 41, 46, 47, 67, 69, 71],      # 经典档（8 条；第 7 条「半月」只在改进档成立）
    "samaya": {"Sun": 18, "Moon": 11, "Mercury": 17, "Venus": 7, "Mars": 6, "Jupiter": 26, "Saturn": 13},
    "dirahSum": {"Sun": 45, "Moon": -7, "Mercury": 25, "Venus": 20, "Mars": 40, "Jupiter": 20, "Saturn": 50},
    "dirahClassicSum": {"Sun": 55, "Moon": 3, "Mercury": 25, "Venus": 20, "Mars": 40, "Jupiter": 20, "Saturn": 50},
    "sphuta": {
        "Trisphuta": 169.55784828315177, "Chatusphuta": 199.90674117042863, "Panchasphuta": 127.53774410739561,
        "Prana": 34.930007161998674, "Deha": 131.1959910966898, "Mrityu": 266.21027917714514, "Sookshma": 72.33627743583384,
    },
}
UPSTREAM_GOLDEN_PAIR_A = {
    "scores": {"Varna": (0.0, 1.0), "Vashya": (0.0, 0.0), "Tara": (1.5, 1.5), "Yoni": (2.0, 2.0), "Graha Maitri": (3.0, 3.0),
               "Gana": (0.0, 0.0), "Bhakoot": (0.0, 0.0), "Nadi": (8.0, 8.0)},   # (通行表, 传统表)
    "total": 14.5, "classicTotal": 15.5, "max": 36, "ayanamsa": "Lahiri / Chitrapaksha",
    "groomNakshatra": 23, "brideNakshatra": 21, "groomSign": 9, "brideSign": 8,
    "doshaPresent": {"Nadi": False, "Bhakoot": True},
}

# 上游 utils/indiaExtraTables.js 的三张小表（独立排穿界行用；与 vendored 文件的一致性由 selfcheck.mjs 的上游 jest 夹具金标守）。
SIGNS = ["白羊", "金牛", "双子", "巨蟹", "狮子", "处女", "天秤", "天蝎", "射手", "摩羯", "水瓶", "双鱼"]
PLANET_CN = {"Sun": "日", "Moon": "月", "Mercury": "水", "Venus": "金", "Mars": "火", "Jupiter": "木", "Saturn": "土", "Asc": "上升"}
RELATION_CN = {"own": "自座", "friend": "友", "neutral": "中", "enemy": "敌"}
KOOTA_CN = {"Varna": "种姓", "Vashya": "相制", "Tara": "星宿吉凶", "Yoni": "生类", "Graha Maitri": "星主友谊", "Gana": "性情组",
            "Bhakoot": "星座距", "Nadi": "脉"}


def _titles(text: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"^\[(.+)\]$", text, re.M)]


def _degrade_notes(env) -> list[str]:
    """降级说明（缺段原因）。夹具的 jyotish 只留了几个子块，导出层那句「结果不完整：预设 N 段中 M 段未产出」与本文件无关，滤掉。"""
    return [w for w in env.warnings if not w.startswith("结果不完整")]


def _js_num(value: float) -> str:
    """JS 模板里的数：14.5 → '14.5'、3.0 → '3'。"""
    return f"{int(value)}" if float(value).is_integer() else f"{value}"


def _signed(value: int) -> str:
    return f"+{value}" if value > 0 else f"{value}"


def _expected_transit_row(row: dict[str, Any]) -> str:
    """上游 buildTransitEventLines 的一行：`| 日期 时:分 | 星 | 进入 | 座主 |`（transitEventText 四种事件写法）。"""
    back = "(逆)" if row.get("retrograde") else ""
    kind = row["kind"]
    if kind == "sign":
        entered = f"{SIGNS[row['sign']]}{back}"
    elif kind == "nakshatra":
        entered = f"第 {row['number']} 宿{back}"
    elif kind == "pada":
        entered = f"第 {row['number']} 足{back}"
    else:
        entered = f"{SIGNS[row['sign']]}第 {row['number']} 段 · {PLANET_CN[row['lord']]}{back}"
    return f"| {row['date']} {row['time'][:5]} | {PLANET_CN[row['planet']]} | {entered} | {RELATION_CN[row['relation']]} |"


class India314Client(FakeClient):
    """回放 fixtures/sync314_india_live.json：/india/chart、/astroextra/transitevents（按所选三项取录制组）、
    /astroextra/ashtakoota（按男方 + 岁差取录制组）；其余端点走 FakeClient。"""

    def __init__(self, *, chart: dict | None = None, fail: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.chart = chart if chart is not None else FIX["india_chart"]
        self.fail = fail or {}
        self.calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, copy.deepcopy(payload)))
        if endpoint in self.fail:
            failure = self.fail[endpoint]
            if isinstance(failure, Exception):
                raise failure
            return copy.deepcopy(failure)
        if endpoint == "/india/chart":
            return copy.deepcopy(self.chart)
        if endpoint == "/astroextra/transitevents":
            wanted = (payload.get("transitPlanet"), payload.get("transitKind"), payload.get("transitDays"))
            for recorded in FIX["transitevents"].values():
                req = recorded["request"]
                if (req["transitPlanet"], req["transitKind"], req["transitDays"]) == wanted:
                    return copy.deepcopy(recorded["response"])
            raise AssertionError(f"no recorded transitevents for {wanted}")
        if endpoint == "/astroextra/ashtakoota":
            key = payload.get("maleSide") + ("_raman" if payload.get("siderealAyanamsa") == "raman" else "")
            return copy.deepcopy(FIX["ashtakoota"][key]["response"])
        return super().call(endpoint, payload)

    def requests(self, endpoint: str) -> list[dict]:
        return [p for e, p in self.calls if e == endpoint]


def _india(tmp_path, extra: dict | None = None, **client_kwargs):
    client = India314Client(**client_kwargs)
    env = _service(tmp_path, client).run_tool("india_chart", {**FIX["payload"], **(extra or {})}, save_result=False)
    return env, client


def _relative(tmp_path, *, inner: dict | None = None, outer: dict | None = None, extra: dict | None = None, **client_kwargs):
    client = India314Client(**client_kwargs)
    payload = {
        "agent_confirmed_settings": True,
        "inner": {**FIX["pair"]["inner"], **(inner or {})},
        "outer": {**FIX["pair"]["outer"], **(outer or {})},
        **(extra or {}),
    }
    env = _service(tmp_path, client).run_tool("relative", payload, save_result=False)
    return env, client


# ─────────────────────────────── 期望值与上游金标互锚 ───────────────────────────────


@needs_upstream("Horosa-Web/astropy/tests/data/golden_india_tables.json")
def test_literals_equal_the_upstream_golden() -> None:
    """本文件抄下来的期望值 == 上游后端金标文件里的值（抄错一位就红）。"""
    golden = json.loads(upstream_source(upstream_path("Horosa-Web/astropy/tests/data/golden_india_tables.json")))
    chart = golden["charts"]["beijing-1990"]
    assert [row[0] for row in chart["yoga"] if row[1]] == UPSTREAM_GOLDEN_BEIJING["yogaHitIds"]
    assert [row[0] for row in chart["yoga"] if row[2]] == UPSTREAM_GOLDEN_BEIJING["yogaClassicHitIds"]
    assert len(chart["yoga"]) == 111
    extra = chart["extra"]
    assert {row["planet"]: row["value"] for row in extra["samaya"]} == UPSTREAM_GOLDEN_BEIJING["samaya"]
    assert {row["planet"]: row["sum"] for row in extra["dirah"]} == UPSTREAM_GOLDEN_BEIJING["dirahSum"]
    assert {row["planet"]: row["sum"] for row in extra["dirahClassic"]} == UPSTREAM_GOLDEN_BEIJING["dirahClassicSum"]
    assert {row["name"]: row["lon"] for row in extra["sphuta"]} == UPSTREAM_GOLDEN_BEIJING["sphuta"]
    pair = golden["pairs"]["a"]
    assert {row["name"]: (row["score"], row["classic"]) for row in pair["rows"]} == UPSTREAM_GOLDEN_PAIR_A["scores"]
    for key in ("total", "classicTotal", "max", "ayanamsa", "groomNakshatra", "brideNakshatra", "groomSign", "brideSign"):
        assert pair[key] == UPSTREAM_GOLDEN_PAIR_A[key], key
    assert {d["koota"]: d["present"] for d in pair["doshas"]} == UPSTREAM_GOLDEN_PAIR_A["doshaPresent"]


def test_recorded_engine_blocks_equal_the_upstream_golden() -> None:
    """录制夹具（vendored 引擎实抓）里的两个引擎子块与上游金标同值——夹具不是另一份真相。"""
    jyotish = FIX["india_chart"]["jyotish"]
    assert [row["id"] for row in jyotish["yogaTable"]["rows"] if row["hit"]] == UPSTREAM_GOLDEN_BEIJING["yogaHitIds"]
    assert [row["id"] for row in jyotish["yogaTable"]["rows"] if row["classicHit"]] == UPSTREAM_GOLDEN_BEIJING["yogaClassicHitIds"]
    assert {row["planet"]: row["sum"] for row in jyotish["extraTables"]["dirah"]} == UPSTREAM_GOLDEN_BEIJING["dirahSum"]
    for row in jyotish["extraTables"]["sphuta"]:
        assert row["lon"] == pytest.approx(UPSTREAM_GOLDEN_BEIJING["sphuta"][row["name"]], abs=1e-9)
    koota = FIX["ashtakoota"]["inner"]["response"]
    assert (koota["total"], koota["classicTotal"], koota["groomNakshatra"], koota["brideNakshatra"]) == (14.5, 15.5, 23, 21)


# ─────────────────────────────── india_chart：Yoga 判定表 / 印占补充表 ───────────────────────────────


@requires_node
def test_yoga_table_section_lists_the_golden_hits(tmp_path) -> None:
    """[Yoga 判定表]：概述行 = 111 条里成立 9 条(经典写法 8 条)；表里正好是金标成立的 9 条，改进 / 经典两列各自写。

    负向对照（实跑）：把 vendored jyotishSnapshot.js 的 `out['Yoga 判定表'] = yogaTableLines` 一行删掉 → 本用例首条 assert 红
    （titles 里没有该段）。"""
    env, _ = _india(tmp_path)
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    titles = _titles(text)
    assert "Yoga 判定表" in titles and "印占补充表" in titles
    # 段序 = 上游 buildJyotishSnapshotLines：两段紧跟（本夹具没有 [瑜伽格局 Yogas]，两段相邻、Yoga 表在前）。
    assert titles.index("印占补充表") == titles.index("Yoga 判定表") + 1
    body = _section(text, "Yoga 判定表").split("\n")
    hits, classic = len(UPSTREAM_GOLDEN_BEIJING["yogaHitIds"]), len(UPSTREAM_GOLDEN_BEIJING["yogaClassicHitIds"])
    assert body[0] == f"111 条里成立 {hits} 条(经典写法 {classic} 条),按上升星座起整宫,计数只算七曜"
    assert body[1] == "| 组合 | 类 | 性质 | 改进 | 经典 | 条件 |"
    rows = body[3:]
    by_id = {row["id"]: row for row in FIX["india_chart"]["jyotish"]["yogaTable"]["rows"]}
    assert len(rows) == hits
    for line, yoga_id in zip(rows, UPSTREAM_GOLDEN_BEIJING["yogaHitIds"]):
        row = by_id[yoga_id]
        classic_hit = yoga_id in UPSTREAM_GOLDEN_BEIJING["yogaClassicHitIds"]
        assert line.startswith(f"| {row['zh']}({row['name']}) | {row['group']} | "), line
        assert f"| 成立 | {'成立' if classic_hit else '不成立'} | " in line, line
    # 第 7 条「半月」只在改进档成立（金标 [7, true, false]）。
    assert rows[0].startswith("| 半月(Ardha Chandra) | 形状 | 吉 | 成立 | 不成立 | ")


@requires_node
def test_extra_tables_section_carries_the_golden_numbers(tmp_path) -> None:
    """[印占补充表]：Graha Samaya 七值、Dirah Bala 合计（改进 / 经典两档）、七个 Sphuta 的位置都等于上游金标。

    负向对照（实跑）：回放盘里把 extraTables.dirah 的太阳合计改成 44 → 「| 日 | … | +45 |」那条 assert 红。"""
    env, _ = _india(tmp_path)
    assert env.ok, env.error
    body = _section(env.data["snapshot_text"], "印占补充表").split("\n")
    at = body.index("Graha Samaya(0–26,经验式)")
    assert body[at + 3:at + 10] == [f"| {PLANET_CN[p]} | {v} |" for p, v in UPSTREAM_GOLDEN_BEIJING["samaya"].items()]
    at = body.index("Dirah Bala")
    dirah_rows = body[at + 3:at + 10]
    for line, (planet, total) in zip(dirah_rows, UPSTREAM_GOLDEN_BEIJING["dirahSum"].items()):
        assert line.startswith(f"| {PLANET_CN[planet]} | ") and line.endswith(f" | {_signed(total)} |"), line
    at = body.index("Dirah Bala 合计(经典口径)")
    assert body[at + 3:at + 10] == [f"| {PLANET_CN[p]} | {_signed(v)} |" for p, v in UPSTREAM_GOLDEN_BEIJING["dirahClassicSum"].items()]
    # 本盘西占版两档逐项相同（金标 dirahWestern == dirahWesternClassic）→ 上游只写一句。
    assert "Dirah 西占版(经典口径):与上表逐项相同" in body
    at = body.index("Sphuta")
    labels = {"Trisphuta": "三合点", "Chatusphuta": "四合点", "Panchasphuta": "五合点", "Prana": "命息点", "Deha": "身点",
              "Mrityu": "死点", "Sookshma": "细点"}
    expected = []
    for name, lon in UPSTREAM_GOLDEN_BEIJING["sphuta"].items():
        expected.append(f"| {labels[name]}({name}) | {SIGNS[int(lon // 30)]} {lon % 30:.2f}° |")
    assert body[at + 3:at + 10] == expected
    exp = env.data["export_snapshot"]
    assert exp["unknown_detected_sections"] == []
    assert {"Yoga 判定表", "印占补充表", "穿界时刻"} <= set(exp["section_titles_detected"])


@requires_node
def test_engine_block_failures_are_named_not_silently_dropped(tmp_path) -> None:
    """引擎子块失败（落 partialErrors）：两段不出，[未能计算] 点名「Yoga 判定表、补充表」（上游 INDIA_PARTIAL_LABELS v3.14.0 新增两项）。

    负向对照（实跑）：把 vendored INDIA_PARTIAL_LABELS 里新加的两行删掉 → 正文写成原始键 yogaTable、extraTables，本用例红。"""
    chart = copy.deepcopy(FIX["india_chart"])
    del chart["jyotish"]["yogaTable"], chart["jyotish"]["extraTables"]
    chart["jyotish"]["partialErrors"] = ["yogaTable", "extraTables"]
    env, _ = _india(tmp_path, chart=chart)
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    assert "Yoga 判定表" not in _titles(text) and "印占补充表" not in _titles(text)
    assert _section(text, "未能计算").strip() == "以下各段本次未能计算(不是没有,而是没算出来):Yoga 判定表、补充表"
    # 两段是条件段（双登记）：缺席不报 missing（夹具的 jyotish 只留了几个子块，别的段缺席与本用例无关）。
    assert not {"Yoga 判定表", "印占补充表"} & set(env.data["export_snapshot"]["missing_selected_sections"])


# ─────────────────────────────── india_chart：穿界时刻 ───────────────────────────────


@requires_node
def test_transit_section_default_selection_and_request_shape(tmp_path) -> None:
    """[穿界时刻] 缺省 = 上游 TRANSIT_DEFAULT_SELECTION（七星 · 入星座 · 90 天），起始 = transitDate；请求体 = 上游
    indiaTransitEventParams + transitStart + 所选三项；段落在全文末尾（[未能计算] 之后、[附加分盘] 之前）。

    负向对照（实跑）：enrich._india_transit_entry 里把 `"zodiacal": 1` 一行去掉 → 请求体断言红；把 chart_family 里
    `_india_ensure_section(tail, "穿界时刻", …)` 那段去掉 → titles[-1] 断言红。"""
    env, client = _india(tmp_path)
    assert env.ok, env.error
    assert _degrade_notes(env) == []
    text = env.data["snapshot_text"]
    assert _titles(text)[-1] == "穿界时刻"
    recorded = FIX["transitevents"]["default"]
    (body,) = client.requests("/astroextra/transitevents")
    assert body == {
        "date": "1990-05-15", "time": "12:00:00", "ad": 1, "zone": "+08:00", "lat": "39n54", "lon": "116e24",
        "hsys": 5, "zodiacal": 1, "siderealAyanamsa": "lahiri",
        "transitStart": "2028/04/06", "transitPlanet": "all", "transitKind": "sign", "transitDays": 90,
    }
    # 三个所选键只进穿界请求，不进 /india/chart 请求体。
    (chart_req,) = client.requests("/india/chart")
    assert not {"indiaTransitPlanet", "indiaTransitKind", "indiaTransitDays", "transitPlanet", "transitKind", "transitDays"} & set(chart_req)
    lines = _section(text, "穿界时刻").split("\n")
    rows = recorded["response"]["rows"]
    total = recorded["response"]["total"]
    assert lines[0] == f"起始 2028/04/06,范围 90 天,星 七星,事件 入星座;共 {total} 条,时刻按本盘时区,恒星黄道(岁差 Lahiri / Chitrapaksha)"
    assert lines[1] == "| 时刻 | 星 | 进入 | 座主 |"
    assert lines[3:] == [_expected_transit_row(row) for row in rows]
    assert total == len(rows) and total > 30   # 月亮 90 天过 39–40 座，另有日 / 水 / 金 / 火入座


@requires_node
@pytest.mark.parametrize(
    ("given", "recorded_key", "head"),
    [
        ({"indiaTransitPlanet": "Moon", "indiaTransitKind": "pada", "indiaTransitDays": 30}, "moon_pada_30", "范围 30 天,星 月亮,事件 入足"),
        ({"indiaTransitPlanet": "水星", "indiaTransitKind": "入星宿", "indiaTransitDays": "180"}, "mercury_nakshatra_180", "范围 180 天,星 水星,事件 入星宿"),
        ({"indiaTransitPlanet": "Sun", "indiaTransitKind": "kakshya", "indiaTransitDays": 30}, "sun_kakshya_30", "范围 30 天,星 太阳,事件 入 Kakshya"),
    ],
)
def test_transit_selection_changes_the_request_and_the_table(tmp_path, given, recorded_key, head) -> None:
    """改所选三项，请求与表都跟着变（中文别名经词表读成规范值）。

    负向对照（实跑）：enrich._india_transit_entry 里把 selection 恒写成缺省 → 三组全红（请求体仍是 all / sign / 90）。"""
    env, client = _india(tmp_path, given)
    assert env.ok, env.error
    recorded = FIX["transitevents"][recorded_key]
    (body,) = client.requests("/astroextra/transitevents")
    for key in ("transitPlanet", "transitKind", "transitDays"):
        assert body[key] == recorded["request"][key]
    lines = _section(env.data["snapshot_text"], "穿界时刻").split("\n")
    rows = recorded["response"]["rows"]
    assert lines[0] == f"起始 2028/04/06,{head};共 {recorded['response']['total']} 条,时刻按本盘时区,恒星黄道(岁差 Lahiri / Chitrapaksha)"
    assert lines[3:] == [_expected_transit_row(row) for row in rows[:200]]
    assert lines != _section(_india(tmp_path)[0].data["snapshot_text"], "穿界时刻").split("\n")


@requires_node
def test_transit_table_with_no_events_says_so(tmp_path) -> None:
    """范围内没有事件（土星 30 天不换座）：段照出，写明原因（上游 buildTransitEventLines）。"""
    assert FIX["transitevents"]["saturn_sign_30"]["response"]["rows"] == []
    env, _ = _india(tmp_path, {"indiaTransitPlanet": "Saturn", "indiaTransitDays": 30})
    lines = _section(env.data["snapshot_text"], "穿界时刻").split("\n")
    assert lines == [
        "起始 2028/04/06,范围 30 天,星 土星,事件 入星座;共 0 条,时刻按本盘时区,恒星黄道(岁差 Lahiri / Chitrapaksha)",
        "这段时间里没有所选的穿界事件",
    ]


@requires_node
@pytest.mark.parametrize(
    ("field", "value"),
    [("indiaTransitPlanet", "Pluto"), ("indiaTransitKind", "house"), ("indiaTransitDays", 45), ("indiaTransitDays", "半年")],
)
def test_transit_selection_outside_the_upstream_tables_is_rejected(tmp_path, field, value) -> None:
    """后端对认不出的星 / 事件静默换成七星 / 入星座、天数夹到 1–366，段头却照抄原值——入口就拦成 tool.invalid_option。

    负向对照（实跑）：把 IndiaChartInput._transit_vocabulary 校验器去掉 → 请求照发（45 天被后端照算、段头写「范围 45」），本用例红。"""
    client = India314Client()
    with pytest.raises(ToolValidationError) as err:
        _service(tmp_path, client).run_tool("india_chart", {**FIX["payload"], field: value}, save_result=False)
    assert err.value.code == "tool.invalid_option", err.value
    assert field in f"{err.value}" and client.calls == []


@requires_node
@pytest.mark.parametrize(
    "failure",
    [
        ToolTransportError("后端拒绝了本次请求参数（backend_param_error）。", code="tool.backend_param_error", details={"err": "param error"}),
        {"total": 0},                      # 200 但没有 rows
        {"rows": "not-a-list"},
    ],
)
def test_transit_fetch_failure_is_visible_and_does_not_break_the_chart(tmp_path, failure) -> None:
    """穿界表取不到 / 回包形状不对：主盘照出、该段缺席，warnings 里说明（不静默）。条件段：缺席不报 missing。

    负向对照（实跑）：把 _india_transit_entry 里两处 _degrade 换成 pass → warnings 断言红。"""
    env, _ = _india(tmp_path, fail={"/astroextra/transitevents": failure})
    assert env.ok, env.error
    assert "穿界时刻" not in _titles(env.data["snapshot_text"])
    assert "Yoga 判定表" in _titles(env.data["snapshot_text"])
    assert any("[穿界时刻] 本次未产出" in w for w in env.warnings), env.warnings
    assert "穿界时刻" not in env.data["export_snapshot"]["missing_selected_sections"]


@requires_node
def test_transit_section_sits_before_the_extra_vargas(tmp_path) -> None:
    """上游 buildIndiaSnapshotForFields:1491-1510：先 appendTransitSectionWithParams，再接 [附加分盘]。"""
    env, _ = _india(tmp_path, {"indiaExtraVargas": [9]})
    assert env.ok, env.error
    assert _titles(env.data["snapshot_text"])[-2:] == ["穿界时刻", "附加分盘"]


@requires_node
def test_python_transit_vocabulary_equals_the_vendored_tables() -> None:
    """india_vocab 的三张词表 / 缺省 == vendored 上游 TRANSIT_*_OPTIONS / TRANSIT_DEFAULT_SELECTION（逐值；经 JS 工具取）。

    负向对照（实跑）：在 india_vocab.INDIA_TRANSIT_VOCABULARIES['indiaTransitDays'] 里加一档 45 → 本用例红。"""
    from fakes import FakeJsClient

    from horosa_skill.india_vocab import INDIA_TRANSIT_DEFAULTS, INDIA_TRANSIT_REQUEST_KEYS, INDIA_TRANSIT_VOCABULARIES

    vocab = FakeJsClient().run("india_tables", {"action": "transit_vocab"})   # 这个桩直接跑真 JS
    for field, table in (("indiaTransitPlanet", "planets"), ("indiaTransitKind", "kinds"), ("indiaTransitDays", "days")):
        assert [item["value"] for item in INDIA_TRANSIT_VOCABULARIES[field].accepted] == [o["value"] for o in vocab[table]], field
        for option in vocab[table]:   # 上游页面上的中文名也要认得
            assert INDIA_TRANSIT_VOCABULARIES[field].parse(option["label"]).value == option["value"], (field, option)
    assert {INDIA_TRANSIT_REQUEST_KEYS[field]: value for field, value in INDIA_TRANSIT_DEFAULTS.items()} == vocab["defaults"]
    assert vocab["maxRows"] == 200


# ─────────────────────────────── india_chart：三旗盘与段内空行 ───────────────────────────────


@requires_node
def test_tripataki_chart_keeps_the_whole_snapshot(tmp_path) -> None:
    """上游 v3.14.0「开三旗盘时 AI 快照整份为空」：skill 自 v3.11 起就把 SIGN_CN_S / scS 上提（当时是偏离，现为上游原文）。
    服务级确认：indiaTripataki=true 的真回包（月序键是后端的 `month`）下，三旗盘两段与它后面的段都在。

    负向对照（实跑，npm selfcheck 同款）：把 SIGN_CN_S / scS 挪回 Argala 块前 → JS builder 抛 ReferenceError，Jyotish 段全缺、
    warnings 出「Jyotish 派生段…未产出」，本用例红。"""
    tri = FIX["india_chart"]["jyotish"]["tripataki"]
    assert tri["available"] and "month" in tri["byCenter"]["moon"]["months"][0] and "index" not in tri["byCenter"]["moon"]["months"][0]
    env, client = _india(tmp_path)
    assert env.ok, env.error
    assert _degrade_notes(env) == []
    assert client.requests("/india/chart")[0]["tripataki"] == 1
    text = env.data["snapshot_text"]
    titles = _titles(text)
    assert "Tripataki 三旗盘逐月净分" in titles and "Yoga 判定表" in titles and "穿界时刻" in titles
    body = _section(text, "Tripataki 三旗盘逐月净分")
    moon = tri["byCenter"]["moon"]
    cells = " ".join(f"{m['month']}:{m['score']['net'] if m.get('score') else '-'}" for m in moon["months"])
    assert cells in body and "undefined" not in body


@requires_node
def test_star_info_blocks_are_separated_by_one_blank_line(tmp_path) -> None:
    """上游 v3.14.0 buildIndiaSnapshotText:1275-1277 + ensureSection：[星盘信息] 的宫头表 / 星与虚点表 / 信息三块之间各空一行
    （紧挨着时下游 markdown 会把第二张表的表头当成第一张表的数据行）；段内不留连续空行、首尾不留空行。

    负向对照（实跑）：把 _india_ensure_section 改回「滤掉全部空行」→ 本用例红（两张表头之间没有空行）。"""
    env, _ = _india(tmp_path)
    text = env.data["snapshot_text"]
    block = _section(text, "星盘信息").split("\n")
    second = block.index("| 点位 | 位置 | 逆行 |")
    assert block[0] == "| 宫位 | 宫头 |" and block[second - 1] == "" and block[second - 2].startswith("| 第")
    blanks = [i for i, line in enumerate(block) if line == ""]
    assert len(blanks) == 2 and block[blanks[1] + 1].startswith("经度：")
    assert "\n\n\n" not in text


# ─────────────────────────────── relative：八重合 ───────────────────────────────


def _expected_koota_lines(result: dict[str, Any], side: str) -> list[str]:
    """按上游 buildAshtakootaLines 的写法，从上游金标值独立排出 [八重合] 的头两行与八项表。"""
    g = UPSTREAM_GOLDEN_PAIR_A
    groom = (SIGNS[g["groomSign"]], g["groomNakshatra"]) if side == "inner" else (SIGNS[g["brideSign"]], g["brideNakshatra"])
    bride = (SIGNS[g["brideSign"]], g["brideNakshatra"]) if side == "inner" else (SIGNS[g["groomSign"]], g["groomNakshatra"])
    return [
        f"合计 {_js_num(result['total'])} / 36(另一套传统表 {_js_num(result['classicTotal'])}),岁差 Lahiri / Chitrapaksha",
        f"男方:{'星盘 A' if side == 'inner' else '星盘 B'},月亮 {groom[0]} 第 {groom[1]} 宿;女方:月亮 {bride[0]} 第 {bride[1]} 宿",
        "| 项 | 满分 | 通行表 | 传统表 |",
        "| --- | --- | --- | --- |",
    ]


@requires_node
def test_ashtakoota_section_matches_the_upstream_golden_pair(tmp_path) -> None:
    """[八重合]（上游 GOLDEN_PAIRS['a']，性别都没给 → 男方 = 星盘 A）：合计两套、男女方月亮座 / 宿、八项分、Dosha 行。

    负向对照（实跑）：把 western._build_relative_snapshot_text 里 add("八重合", …) 那段去掉 → 首条 assert 红；
    把 _attach_relative_ashtakoota 里 maleSide 恒写 'outer' → 请求体断言红。"""
    env, client = _relative(tmp_path)
    assert env.ok, env.error
    assert not any("八重合" in w for w in env.warnings), env.warnings
    text = env.data["snapshot_text"]
    assert _titles(text)[-1] == "八重合"     # 上游无头路径（pair.js:205）接在全部段之后
    (body,) = client.requests("/astroextra/ashtakoota")
    assert body["maleSide"] == "inner" and body["siderealAyanamsa"] == ""
    assert {k: body["inner"][k] for k in ("date", "time", "zone", "lat", "lon")} == {
        "date": "1975-02-10", "time": "21:15:00", "zone": "-08:00", "lat": "47n36", "lon": "122w20"}
    lines = _section(text, "八重合").split("\n")
    g = UPSTREAM_GOLDEN_PAIR_A
    assert lines[:4] == _expected_koota_lines({"total": g["total"], "classicTotal": g["classicTotal"]}, "inner")
    assert lines[4:12] == [
        f"| {KOOTA_CN[name]}({name}) | {top} | {_js_num(score)} | {_js_num(classic)} |"
        for top, (name, (score, classic)) in enumerate(g["scores"].items(), start=1)
    ]
    # 金标 doshas：Bhakoot present、无化解条件；Nadi 不成立。
    assert lines[12:] == [
        "有 Bhakoot Dosha(星座距)(该项 0 分);没有满足本页列出的化解条件",
        "化解条件只作标注,分数照原样;各家认不认、认哪几条说法不一",
    ]
    exp = env.data["export_snapshot"]
    assert exp["unknown_detected_sections"] == [] and "八重合" in exp["section_titles_detected"]
    assert env.data["_relativeAshtakoota"]["total"] == 14.5


@requires_node
@pytest.mark.parametrize(
    ("inner", "outer", "extra", "side"),
    [
        ({"gender": "女"}, {"gender": "男"}, {}, "outer"),            # 上游 maleSideOf(0, 1)
        ({"gender": 1}, {"gender": 0}, {}, "inner"),
        ({}, {"gender": "male"}, {}, "outer"),                        # maleSideOf(undefined, 1)
        ({"gender": 0}, {"gender": 0}, {}, "inner"),                  # 同性 → 星盘 A
        ({"gender": 1}, {"gender": 0}, {"ashtakootaMaleSide": "outer"}, "outer"),   # 显式入参压过性别（= 页内亲手改）
        ({"gender": 0}, {"gender": 1}, {"ashtakootaMaleSide": "星盘 A"}, "inner"),
    ],
)
def test_ashtakoota_male_side_follows_gender_unless_given(tmp_path, inner, outer, extra, side) -> None:
    """男方：显式 ashtakootaMaleSide 优先，否则按两人 gender 交上游 maleSideOf；改男方，请求与正文都变。

    负向对照（实跑）：把 _attach_relative_ashtakoota 的 ashtakoota_side 调用换成恒 'inner' → 第 1、3 组红。"""
    env, client = _relative(tmp_path, inner=inner, outer=outer, extra=extra)
    assert env.ok, env.error
    (body,) = client.requests("/astroextra/ashtakoota")
    assert body["maleSide"] == side
    recorded = FIX["ashtakoota"][side]["response"]
    lines = _section(env.data["snapshot_text"], "八重合").split("\n")
    assert lines[:4] == _expected_koota_lines(recorded, side)
    if side == "outer":
        # 男女对调后种姓一项两套表互换（金标对的是 inner；outer 的合计取自同一引擎的录制回包）：正文不是 inner 那份。
        assert (recorded["total"], recorded["classicTotal"]) == (15.5, 14.5)


@requires_node
def test_ashtakoota_follows_the_sidereal_ayanamsa(tmp_path) -> None:
    """岁差随 siderealAyanamsa（上游 pair.js：cal.siderealAyanamsa）：改岁差，月亮宿 / 合计都变。"""
    env, client = _relative(tmp_path, extra={"zodiacal": 1, "siderealAyanamsa": "raman"})
    assert env.ok, env.error
    assert client.requests("/astroextra/ashtakoota")[0]["siderealAyanamsa"] == "raman"
    recorded = FIX["ashtakoota"]["inner_raman"]["response"]
    head = _section(env.data["snapshot_text"], "八重合").split("\n")[0]
    assert head == f"合计 {_js_num(recorded['total'])} / 36(另一套传统表 {_js_num(recorded['classicTotal'])}),岁差 Raman"
    assert recorded["total"] != UPSTREAM_GOLDEN_PAIR_A["total"]


@requires_node
def test_ashtakoota_bad_male_side_is_rejected(tmp_path) -> None:
    client = India314Client()
    with pytest.raises(ToolValidationError) as err:
        _service(tmp_path, client).run_tool(
            "relative", {"agent_confirmed_settings": True, **FIX["pair"], "ashtakootaMaleSide": "第三人"}, save_result=False)
    assert err.value.code == "tool.invalid_option" and client.calls == []


@requires_node
@pytest.mark.parametrize(
    "failure",
    [ToolTransportError("后端拒绝了本次请求参数（backend_param_error）。", code="tool.backend_param_error", details={"err": "param error"}),
     {"total": 1}],
)
def test_ashtakoota_failure_is_visible_and_keeps_the_rest(tmp_path, failure) -> None:
    """八重合取不到：既有合盘段照出、该段缺席，warnings 说明。条件段：缺席不报 missing。

    负向对照（实跑）：把 _attach_relative_ashtakoota 的 _degrade 换成 pass → warnings 断言红。"""
    env, _ = _relative(tmp_path, fail={"/astroextra/ashtakoota": failure})
    assert env.ok, env.error
    titles = _titles(env.data["snapshot_text"])
    assert "八重合" not in titles and "关系起盘信息" in titles
    assert any("[八重合] 本次未产出" in w for w in env.warnings), env.warnings
    assert "八重合" not in env.data["export_snapshot"]["missing_selected_sections"]


# ─────────────────────────────── 导出契约 ───────────────────────────────


def test_presets_carry_the_new_sections_in_upstream_order() -> None:
    """上游 presets.js（v62 / v65）：indiachart 在「副星 Upagraha」之后接三段；relative「八重合」居首；
    indiazeri = [...indiachart, 择时三段]。三段 + 八重合都是条件段（双登记），indiazeri 的 optional 集随基底继承。

    负向对照（实跑）：把 ZERI_DERIVED_KEYS 的段表循环改成跳过 indiazeri（只留 optional 继承）→ 本用例红（KeyError: 'indiazeri'）。"""
    india = AI_EXPORT_PRESET_SECTIONS["indiachart"]
    at = india.index("副星 Upagraha")
    assert india[at + 1:at + 4] == ["Yoga 判定表", "印占补充表", "穿界时刻"]
    assert AI_EXPORT_PRESET_SECTIONS["relative"][0] == "八重合"
    assert AI_EXPORT_PRESET_SECTIONS["indiazeri"] == [*india, "择时搜索配置", "择时条件", "命中时段"]
    assert {"Yoga 判定表", "印占补充表", "穿界时刻"} <= set(AI_EXPORT_OPTIONAL_SECTIONS["indiachart"])
    assert "八重合" in AI_EXPORT_OPTIONAL_SECTIONS["relative"]
    # AGENTS §5.3 第 5 条：派生键只继承段表、不继承 optional 集，会把基底的条件段升格成必出段。
    assert set(AI_EXPORT_OPTIONAL_SECTIONS["indiachart"]) <= set(AI_EXPORT_OPTIONAL_SECTIONS["indiazeri"])


@needs_upstream("Horosa-Web/astrostudyui/src/utils/aiExport/presets.js")
def test_presets_match_the_upstream_source() -> None:
    src = upstream_source(upstream_path("Horosa-Web/astrostudyui/src/utils/aiExport/presets.js"))
    assert "'瑜伽格局 Yogas', '副星 Upagraha',\n\t\t'Yoga 判定表', '印占补充表', '穿界时刻'," in src
    assert "relative: ['八重合', '关系起盘信息'," in src
    assert "AI_EXPORT_PRESET_SECTIONS.indiazeri = [...(AI_EXPORT_PRESET_SECTIONS.indiachart || []), '择时搜索配置', '择时条件', '命中时段'];" in src


# ─────────────────────────────── indiazeri：印占全文 + 择时三段 ───────────────────────────────

_ZERI_PAYLOAD = {
    "agent_confirmed_settings": True, "date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
    "pos": "上海", "startDate": "2028-04-01", "endDate": "2028-04-03",
    "conditions": {"kind": "group", "joiner": "all", "children": [{"kind": "leaf", "type": "vara", "params": {"values": [4]}}]},
}


@requires_node
def test_indiazeri_text_is_the_india_chart_plus_three_zeri_sections(tmp_path) -> None:
    """上游 v3.14.0：印度择日正文 = 命中首刻的印占全文 + 择时三段（此前只有三段）。展示盘 = india_chart，时刻 = 首个命中的 pick。

    负向对照（实跑）：把 _ZERI_BACKEND_TOOLS['indiazeri'] 的 base_tool 改回 None → titles 只剩三段，本用例红。"""
    client = India314Client()
    env = _service(tmp_path, client).run_tool("indiazeri", dict(_ZERI_PAYLOAD), save_result=False)
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    titles = _titles(text)
    assert titles[:2] == ["起盘信息", "星盘信息"] and titles[-3:] == ["择时搜索配置", "择时条件", "命中时段"]
    assert {"Yoga 判定表", "印占补充表", "穿界时刻"} <= set(titles)
    (chart_req,) = client.requests("/india/chart")
    pick = client.call("/indiaelectionscan/scan", {})["intervals"][0]["pick"]   # FakeClient 的扫描桩
    assert f"{chart_req['date']} {chart_req['time']}".replace("/", "-") == pick   # /india/chart 的日期按 Java 写法发（斜杠）
    assert env.data["pan_moment"] == pick and env.data["compute_sources"]["pan"] == "india_chart"
    exp = env.data["export_snapshot"]
    assert exp["unknown_detected_sections"] == []
    # 夹具的 jyotish 只留了几个子块：只断言新段与择时三段不在缺段清单里（整份 clean 归 live 用例）。
    assert not {"Yoga 判定表", "印占补充表", "穿界时刻", "择时搜索配置", "择时条件", "命中时段"} & set(exp["missing_selected_sections"])


@requires_node
@pytest.mark.parametrize(
    ("given", "ayanamsa", "node"),
    [({}, "lahiri", None), ({"indiaAyanamsa": "raman", "nodeType": "true"}, "raman", "true"),
     ({"options": {"ayanamsa": "krishnamurti"}}, "krishnamurti", None)],
)
def test_indiazeri_display_chart_follows_the_scan_calibre(tmp_path, given, ayanamsa, node) -> None:
    """展示盘跟扫描口径（上游 IndiaZeriMain.buildFields：indiaAyanamsa ← options.ayanamsa、indiaNodeType ← options.nodeType）；
    本工具继承来的西占 hsys / zodiacal / siderealAyanamsa 不带进印占盘。

    负向对照（实跑）：把 _zeri_backend_base_payload 里 `base_payload["indiaAyanamsa"] = …` 一行去掉 → 第 1、3 组红
    （缺省与 options.ayanamsa 都到不了展示盘；第 2 组因顶层 indiaAyanamsa 本就在声明键里而照过）。"""
    client = India314Client()
    env = _service(tmp_path, client).run_tool(
        "indiazeri", {**_ZERI_PAYLOAD, "hsys": 3, "zodiacal": 0, "siderealAyanamsa": "fagan_bradley", **given}, save_result=False)
    assert env.ok, env.error
    scan_req = client.requests("/indiaelectionscan/scan")[0]
    (chart_req,) = client.requests("/india/chart")
    assert scan_req["ayanamsa"] == ayanamsa and chart_req["indiaAyanamsa"] == ayanamsa
    assert chart_req.get("nodeType") == node
    assert chart_req.get("hsys") == 0 and "siderealAyanamsa" not in chart_req and "explainAt" not in chart_req
    # （[穿界时刻] 的岁差取后端回显的实际口径；回放盘的回显恒是录制时的 lahiri，这一点由 live 用例看。）


# ─────────────────────────────── live（共享 vendored v3.14.0 引擎）───────────────────────────────


@requires_chart
def test_live_india_chart_reproduces_the_upstream_golden(tmp_path) -> None:
    """真引擎：beijing-1990 的 Yoga 成立数 / Dirah 合计 / Sphuta 与上游金标同值；穿界表缺省 90 天、改成月亮入足即变。"""
    service = make_service(tmp_path)
    payload = {k: v for k, v in FIX["payload"].items() if k != "indiaTripataki"}
    env = service.run_tool("india_chart", payload, save_result=False)
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    assert _section(text, "Yoga 判定表").split("\n")[0] == "111 条里成立 9 条(经典写法 8 条),按上升星座起整宫,计数只算七曜"
    extra = _section(text, "印占补充表").split("\n")
    at = extra.index("Dirah Bala 合计(经典口径)")
    assert extra[at + 3:at + 10] == [f"| {PLANET_CN[p]} | {_signed(v)} |" for p, v in UPSTREAM_GOLDEN_BEIJING["dirahClassicSum"].items()]
    assert "| 三合点(Trisphuta) | 处女 19.56° |" in extra
    default = _section(text, "穿界时刻").split("\n")
    assert default[0].startswith("起始 2028/04/06,范围 90 天,星 七星,事件 入星座;共 ")
    moon = service.run_tool("india_chart", {**payload, "indiaTransitPlanet": "Moon", "indiaTransitKind": "pada", "indiaTransitDays": 30},
                            save_result=False)
    moon_lines = _section(moon.data["snapshot_text"], "穿界时刻").split("\n")
    assert moon_lines[0].startswith("起始 2028/04/06,范围 30 天,星 月亮,事件 入足;共 ") and moon_lines != default
    assert all(" | 月 | 第 " in line for line in moon_lines[3:])
    exp = env.data["export_snapshot"]
    assert exp["unknown_detected_sections"] == [] and exp["missing_selected_sections"] == []


@requires_chart
def test_live_relative_ashtakoota_reproduces_the_upstream_golden_pair(tmp_path) -> None:
    service = make_service(tmp_path)
    pair = {"inner": dict(FIX["pair"]["inner"]), "outer": dict(FIX["pair"]["outer"])}
    env = service.run_tool("relative", {"agent_confirmed_settings": True, **pair}, save_result=False)
    assert env.ok, env.error
    lines = _section(env.data["snapshot_text"], "八重合").split("\n")
    g = UPSTREAM_GOLDEN_PAIR_A
    assert lines[:4] == _expected_koota_lines({"total": g["total"], "classicTotal": g["classicTotal"]}, "inner")
    pair["inner"]["gender"], pair["outer"]["gender"] = 0, 1
    swapped = service.run_tool("relative", {"agent_confirmed_settings": True, **pair}, save_result=False)
    assert _section(swapped.data["snapshot_text"], "八重合").split("\n")[1].startswith("男方:星盘 B,月亮 射手 第 21 宿;女方:月亮 摩羯 第 23 宿")
    assert env.data["export_snapshot"]["unknown_detected_sections"] == []


@requires_chart
def test_live_indiazeri_carries_the_india_chart_at_the_first_hit(tmp_path) -> None:
    service = make_service(tmp_path)
    payload = {**_ZERI_PAYLOAD, "indiaAyanamsa": "raman",
               "conditions": {"kind": "group", "joiner": "all", "children": [{"kind": "leaf", "type": "lagna", "params": {"values": [1]}}]}}
    env = service.run_tool("indiazeri", payload, save_result=False)
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    titles = _titles(text)
    assert titles[-3:] == ["择时搜索配置", "择时条件", "命中时段"] and "Panchanga 五要素" in titles
    assert "恒星黄道(岁差 Raman)" in _section(text, "穿界时刻").split("\n")[0]   # 穿界表与展示盘同一岁差
    setup = _section(text, "起盘信息")
    assert "恒星黄道·Raman，整宫制 Whole Sign" in setup and env.data["pan_moment"] in setup
    # 条件是「上升白羊」→ 命中首刻那一盘的第一宫就是白羊（展示盘与扫描同一岁差才成立）。
    assert "| 第一宫 | 0˚牡羊0分" in _section(text, "星盘信息")
    exp = env.data["export_snapshot"]
    assert exp["unknown_detected_sections"] == [] and exp["missing_selected_sections"] == []
