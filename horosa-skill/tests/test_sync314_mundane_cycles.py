"""上游 v3.14.0（Horosa-Public @ e55c3a66）世俗盘「世运周期表」14 张 + Barbault 谐波 / 慢星组合。

- 段 `[世运周期表]`（aiExport v61，preset 里排在「行星周期」之后）：只在 `mundaneType=cycles` 成段。计算在后端
  `/astroextra/mundanecycles`（astrostudy/mundane_cycles.py、meteorology.py），请求字段与正文由 vendored 上游
  `utils/mundaneCycles.js`（`mundaneCycleRequestFields` / `buildMundaneCycleText`）出，Python 只取数。
- Barbault：`bbSet` / `bbHarm` 进页面设置（MundaneMain.js MUNDANE_PAGE_SETTINGS）；后端 `harm` 1–12。

服务级离线用例跑**真 JS 引擎** + 脚本化 HTTP 桩；期望值的独立来源：
- 上游 `astropy/tests/test_mundane_cycles.py` 的固定样本（大合日期与三重合 / 换三分性标志、千年轮转首三段、中档法达每段 75 年、
  千年表 / 世界年表 1701 年那一行）；
- 天文事实：木土大合的公布黄经（1961-02 摩羯 25°12′、1980-12 天秤 9°30′、1981-03 天秤 8°06′、1981-07 天秤 4°56′、
  2000-05 金牛 22°43′、2020-12 水瓶 0°29′）。
"""

from __future__ import annotations

from skips import upstream_source  # 上游拆文件后读「门面 + 子模块」全集（v3.15.0）
import copy
import json
import re
from pathlib import Path

import pytest
from skips import needs_upstream, upstream_path
from test_sync311_mundane_election import MUNDANE, ScriptedClient, _clean, _section, _service

from horosa_skill.errors import ToolTransportError
from horosa_skill.exports.registry import AI_EXPORT_OPTIONAL_SECTIONS, AI_EXPORT_PRESET_SECTIONS
from horosa_skill.schemas.tools import MundaneInput
from horosa_skill.schemas.tools.base import advertise_hidden_fields
from horosa_skill.service import HorosaSkillService

PKG_ROOT = Path(__file__).resolve().parents[1]
VENDOR = PKG_ROOT / "horosa-core-js" / "src" / "vendor"
FIX = json.loads((Path(__file__).parent / "fixtures" / "sync314_mundane_live.json").read_text(encoding="utf-8"))
CYCLES = {**MUNDANE, "mundaneType": "cycles"}
ENDPOINT = "/astroextra/mundanecycles"


class CycleClient(ScriptedClient):
    """ScriptedClient + 可替换的周期表 / Barbault 响应（缺省 = 夹具里的真实响应）。"""

    def __init__(self, *, cycle=None, barbault=None) -> None:
        super().__init__()
        self.cycle = cycle
        self.barbault = barbault

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == ENDPOINT and self.cycle is not None:
            self.calls.append((endpoint, copy.deepcopy(payload)))
            return self.cycle(payload) if callable(self.cycle) else copy.deepcopy(self.cycle)
        if endpoint == "/astroextra/barbault" and self.barbault is not None:
            self.calls.append((endpoint, copy.deepcopy(payload)))
            return self.barbault(payload)
        return super().call(endpoint, payload)


def _run(tmp_path, client, **extra):
    return _service(tmp_path, client).run_tool("mundane", {**CYCLES, **extra}, save_result=False)


def _has(text: str, title: str) -> bool:
    return f"[{title}]" in text.split("\n")


# ────────────────────────────── 契约锚点 ──────────────────────────────


def test_cycle_table_section_is_registered_as_a_conditional_cycles_card() -> None:
    preset = AI_EXPORT_PRESET_SECTIONS["mundane"]
    assert preset.index("世运周期表") == preset.index("行星周期") + 1  # 上游 presets.js：紧随「行星周期」
    assert "世运周期表" in AI_EXPORT_OPTIONAL_SECTIONS["mundane"]  # 只在 cycles 盘型成段 → 条件段双登记
    assert "世运周期表" in HorosaSkillService._MUNDANE_TYPE_CARDS["cycles"]
    assert ENDPOINT in __import__("horosa_skill.service.endpoints", fromlist=["x"])._PYTHON_CHART_ENDPOINTS


def test_cycle_option_keys_equal_the_vendored_settings_schema() -> None:
    """Python 手持的键表（发请求 / 归一整数用）必须等于 vendored 上游 MUNDANE_CYCLE_DEFAULTS 的键集；上游加一个选项即红。"""
    text = (VENDOR / "utils" / "mundaneCycles.js").read_text(encoding="utf-8")
    defaults = re.search(r"export const MUNDANE_CYCLE_DEFAULTS = \{(.*?)\};", text, re.S)
    assert defaults, "MUNDANE_CYCLE_DEFAULTS not found in the vendored module"
    keys = set(re.findall(r"(\w+):", defaults.group(1)))
    assert keys == set(HorosaSkillService._MUNDANE_CYCLE_OPTION_KEYS)
    # 数值型选项 = 选项表里 value 是数字的那几键（上游 oneOf 严格相等，'200' ≠ 200）。
    options = re.search(r"export const MUNDANE_CYCLE_OPTIONS = \{(.*?)\n\};", text, re.S).group(1)
    numeric = set(re.findall(r"^\t(\w+): \[\{ value: \d", options, re.M))
    assert numeric == set(HorosaSkillService._MUNDANE_CYCLE_INT_KEYS)
    # 每个键都是已声明、不广告的 schema 字段（MCP 扁平面照收），且带说明（guidance options_keys 的来源）。
    hidden = advertise_hidden_fields(MundaneInput)
    for key in HorosaSkillService._MUNDANE_CYCLES_KEYS:
        assert key in MundaneInput.model_fields and key in hidden, key
        assert MundaneInput.model_fields[key].description, key
    # 这些键不许漏进 /chart 请求体。
    assert set(HorosaSkillService._MUNDANE_CYCLES_KEYS) <= HorosaSkillService._MUNDANE_ONLY_KEYS


def test_cycle_table_descriptions_name_every_upstream_table_and_default() -> None:
    text = (VENDOR / "utils" / "mundaneCycles.js").read_text(encoding="utf-8")
    tables = re.findall(r"\{ value: '(\w+)', label: '([^']+)'", text.split("export const MUNDANE_CYCLE_OPTIONS")[0])
    assert len(tables) == 14
    doc = MundaneInput.model_fields["cycleTable"].description
    for value, label in tables:
        assert f"{value} {label}" in doc, (value, label)


def test_barbault_harmonic_range_covers_the_page_dropdown() -> None:
    # v3.15.0：世俗盘页拆成壳 + main/*，卡片段与表格常量在 vendored mundane/main/{cards,tables}.js（壳不再 vendor）。
    text = "".join(path.read_text(encoding="utf-8") for path in sorted((VENDOR / "mundane" / "main").glob("*.js")))
    page = [int(v) for v in re.findall(r"\{ v: (\d+), cn:", text.split("const BARBAULT_HARMONICS = ")[1].split("\n")[0])]
    low, high = HorosaSkillService._MUNDANE_BB_HARM_RANGE
    assert page == [1, 2, 3, 4] and low == 1 and set(page) <= set(range(low, high + 1))


@needs_upstream("Horosa-Web/astropy/astrostudy/astroextra_parts/cycles.py")
def test_barbault_harmonic_range_is_the_backend_range() -> None:
    text = upstream_source(upstream_path("Horosa-Web/astropy/astrostudy/astroextra_parts/cycles.py"))
    low, high = HorosaSkillService._MUNDANE_BB_HARM_RANGE
    assert f"if harm < {low} or harm > {high}:" in text


# ────────────────────────────── 世运周期表：真 JS + 脚本化后端 ──────────────────────────────


def test_default_cycle_table_request_is_chart_params_plus_target_and_fields(tmp_path) -> None:
    client = CycleClient()
    env = _run(tmp_path, client)
    assert env.ok, env.error
    (req,) = client.requests(ENDPOINT)
    # 上游 MundaneCycleTables.body()：chartParams(盘) + targetDate / targetTime（盘面日期时刻）+ mundaneCycleRequestFields(缺省设置)。
    assert (req["date"], req["time"]) == ("2025-03-20", "17:01:41")  # 入宫盘时刻（桩 /jieqi/year 的春分）
    assert (req["targetDate"], req["targetTime"]) == (req["date"], req["time"])
    assert (req["zone"], req["lat"], req["lon"], req["hsys"]) == ("+08:00", "31n13", "121e28", 0)
    assert req["tradition"] is False and req["predictive"] is False
    assert {k: req[k] for k in ("table", "conjKind", "variant")} == {"table": "conjunctions", "conjKind": "great", "variant": "improved"}
    # 没给年份不带 startYear / endYear（后端以盘面年份为中心）；世运专属键不许漏进请求体。
    assert not {"startYear", "endYear", "mundaneType", "cycleTable", "year", "ingressTerm", "bbSet", "bbHarm"} & set(req)
    body = _section(env.data["snapshot_text"], "世运周期表")
    assert body[:2] == ["表：大中小合(木土、火土、火木的真实地心合,标出换三分性的一合)", "合：大合(木土)"]
    # 行 = 后端 rows 逐行（夹具是真实响应的前 8 行）：三重合 / 换三分性标志同上游 test_great_conjunctions_of_the_last_century。
    assert [line for line in body if line.startswith("1961-02")] == ["1961-02-19 摩羯 25.20°"]
    assert [line for line in body if line.startswith("1980-12")] == ["1980-12-31 天秤 9.50° 换三分性"]
    assert [line[11:] for line in body if line.startswith("1981-")] == ["天秤 8.11° 三重合", "天秤 4.93° 三重合"]
    text = env.data["snapshot_text"]
    assert text.index("[大年时代]") < text.index("[世运周期表]") < text.index("[Barbault 聚散指数]") < text.index("[起盘信息]")
    assert not env.warnings, env.warnings
    _clean(env)


def test_cycle_options_become_request_fields_and_inapplicable_ones_are_reported(tmp_path) -> None:
    client = CycleClient()
    env = _run(tmp_path, client, cycleTable="profections", profRate="monarchy", profBase="changeAsc", cycleVariant="classic")
    assert env.ok, env.error
    (req,) = client.requests(ENDPOINT)
    assert {k: req.get(k) for k in ("table", "profRate", "profBase", "variant")} == {
        "table": "profections", "profRate": "monarchy", "profBase": "changeAsc", "variant": "classic"}
    assert not env.warnings, env.warnings
    # 年表只认起始年；洪水起点、结束年对千年表不起作用 → 不下发，warnings 点名。
    client = CycleClient()
    env = _run(tmp_path, client, cycleTable="thousands", cycleStartYear="1701", cycleEndYear=1800, flood="b")
    assert env.ok, env.error
    (req,) = client.requests(ENDPOINT)
    assert req["table"] == "thousands" and req["startYear"] == 1701 and "endYear" not in req and "flood" not in req
    (note,) = [w for w in env.warnings if "不起作用" in w]
    assert "`flood`" in note and "`cycleEndYear`" in note and "千年表" in note
    # 数值型选项按整数下发（'6' → 6）：上游 oneOf 是严格相等，后端 `_int` 也只认数。
    client = CycleClient()
    env = _run(tmp_path, client, cycleTable="weather", weatherMonths="6")
    assert env.ok, env.error
    assert client.requests(ENDPOINT)[0]["weatherMonths"] == 6


def test_invalid_cycle_settings_are_refused_before_any_request(tmp_path) -> None:
    for extra, key in (
        ({"cycleTable": "bogus"}, "cycleTable"),            # 后端 _choice：认不出的表静默回大中小合
        ({"cycleTable": "firdaria", "firdariaYears": 300}, "firdariaYears"),
        ({"profRate": "yearly"}, "profRate"),
        ({"cycleStartYear": 0}, "cycleStartYear"),          # 历史纪年无 0 年（上游 renderYear 把 0 当没填）
        ({"cycleEndYear": "abc"}, "cycleEndYear"),
        ({"bbSet": "slow9"}, "bbSet"),
        ({"bbHarm": 13}, "bbHarm"),                         # 后端 harm 越界静默归 1
        ({"bbHarm": 2.5}, "bbHarm"),
    ):
        client = CycleClient()
        env = _run(tmp_path, client, **extra)
        assert not env.ok and env.error.code == "tool.mundane_invalid_setting", (extra, env.error)
        assert [i["key"] for i in env.error.details["invalid"]] == [key], env.error.details
        assert client.calls == [], extra  # 一条后端请求都没发


def test_cycle_settings_on_another_chart_type_are_reported_not_applied(tmp_path) -> None:
    client = CycleClient()
    env = _service(tmp_path, client).run_tool("mundane", {**MUNDANE, "cycleTable": "turns", "bbHarm": 2}, save_result=False)
    assert env.ok, env.error
    assert client.requests(ENDPOINT) == [] and client.requests("/astroextra/barbault")[-1].get("harm") is None
    (note,) = [w for w in env.warnings if "mundaneType=cycles" in w]
    assert "`cycleTable`" in note and "`bbHarm`" in note
    assert not _has(env.data["snapshot_text"], "世运周期表")
    # 值照样先校验：盘型不对不等于可以带病。
    bad = _service(tmp_path, CycleClient()).run_tool("mundane", {**MUNDANE, "cycleTable": "bogus"}, save_result=False)
    assert not bad.ok and bad.error.code == "tool.mundane_invalid_setting"


def test_cycle_table_backend_failures_drop_only_that_section_and_say_so(tmp_path) -> None:
    def refuse(_payload):
        raise ToolTransportError("后端拒绝了本次请求参数（backend_param_error）。", code="tool.backend_param_error", details={"err": "param error"})

    cases = {
        "refused": (refuse, "排盘引擎没有算出这张表"),
        # 后端对认不出的表 / 旧引擎：回的是另一张表 → 不许把它当成所请求的表写进快照。
        "wrong_table": ({"table": "conjunctions", "variant": "improved", "targetYear": 2025, "kind": "great", "rows": [{"date": "2020-12-21 18:20:37", "lon": 300.49}]},
                        "回的不是所请求的表"),
        "empty": ({"table": "turns", "variant": "improved", "targetYear": 2025, "flood": "a", "rows": []}, "没有内容"),
    }
    for name, (cycle, needle) in cases.items():
        env = _run(tmp_path, CycleClient(cycle=cycle), cycleTable="turns")
        assert env.ok, (name, env.error)
        text = env.data["snapshot_text"]
        assert not _has(text, "世运周期表"), name
        assert [w for w in env.warnings if "[世运周期表]" in w and needle in w], (name, env.warnings)
        for title in ("木土纪元", "大年时代", "Barbault 聚散指数"):
            assert _has(text, title), (name, title)
        _clean(env)  # 条件段缺席不算 missing


# ────────────────────────────── Barbault：慢星组合 / 谐波 ──────────────────────────────


def _barbault_echo(payload: dict) -> dict:
    return {"planets": payload.get("planets"), "harm": int(payload.get("harm") or 1), "maxIndex": 540.0,
            "points": [{"year": 1902, "month": 1, "index": 50.2}, {"year": 1932, "month": 7, "index": 359.6}], "extrema": []}


def test_barbault_set_and_harmonic_reach_the_backend_and_the_snapshot(tmp_path) -> None:
    client = CycleClient(barbault=_barbault_echo)
    env = _run(tmp_path, client, bbSet="outer3", bbHarm="3")
    assert env.ok, env.error
    # 上游 computeBarbault（MundaneMain.js:819）：planets = 所选组合；harm 只在 >1 时下发。
    assert client.requests("/astroextra/barbault")[-1] == {
        "startYear": 1900, "endYear": 2050, "stepMonths": 6, "planets": ["Uranus", "Neptune", "Pluto"], "harm": 3}
    assert _section(env.data["snapshot_text"], "Barbault 聚散指数") == [
        "（慢星组合 仅外三星 ♅♆♇（最平滑） · 3 次谐波 · 1900–2050 · 2 点）",
        "最深谷（聚集）1902-01（50°）；最高峰（四散）1932-07（360°）",
    ]
    assert not env.warnings, env.warnings
    # 缺省：不带 harm 键（零回归），标题不写谐波。
    client = CycleClient(barbault=_barbault_echo)
    env = _run(tmp_path, client)
    assert "harm" not in client.requests("/astroextra/barbault")[-1]
    assert _section(env.data["snapshot_text"], "Barbault 聚散指数")[0] == "（慢星组合 五慢星 ♃♄♅♆♇（默认） · 1900–2050 · 2 点）"


def test_barbault_harmonic_not_honoured_by_the_engine_is_not_mislabelled(tmp_path) -> None:
    """旧引擎不认 harm（响应不回显 / 回 1）：照写会把原指数标成「2 次谐波」——该段不出并说明。"""
    client = CycleClient(barbault=lambda payload: {**_barbault_echo(payload), "harm": 1})
    env = _run(tmp_path, client, bbHarm=2)
    assert env.ok, env.error
    assert not _has(env.data["snapshot_text"], "Barbault 聚散指数")
    assert [w for w in env.warnings if "2 次谐波未被排盘引擎采用" in w], env.warnings
    _clean(env)


# ────────────────────────────── live（vendored v3.14.0 实例） ──────────────────────────────

from test_local_js_tools import make_service, requires_chart, requires_current_runtime_contract  # noqa: E402


def _live(tmp_path, **extra):
    env = make_service(tmp_path).run_tool("mundane", {**CYCLES, "hsys": 1, **extra}, save_result=False)
    assert env.ok, env.error
    return env


def _live_rows(tmp_path, **extra) -> list[str]:
    env = _live(tmp_path, **extra)
    assert not env.warnings, env.warnings
    _clean(env)
    return _section(env.data["snapshot_text"], "世运周期表")


@requires_chart
@requires_current_runtime_contract
def test_live_great_conjunctions_match_published_dates_and_longitudes(tmp_path) -> None:
    rows = _live_rows(tmp_path)
    assert rows[:2] == ["表：大中小合(木土、火土、火木的真实地心合,标出换三分性的一合)", "合：大合(木土)"]
    signs = ["白羊", "金牛", "双子", "巨蟹", "狮子", "处女", "天秤", "天蝎", "射手", "摩羯", "水瓶", "双鱼"]
    # (日期, 星座, 公布的座内度°′, 标志)：日期与标志 = 上游 test_great_conjunctions_of_the_last_century / test_element_change_is_flagged；
    # 黄经 = 公布星历值（度分），引擎值须在 0.02° 内。
    published = [
        ("1961-02-19", "摩羯", 25 + 12 / 60, ""), ("1980-12-31", "天秤", 9 + 30 / 60, " 换三分性"),
        ("1981-03-04", "天秤", 8 + 6 / 60, " 三重合"), ("1981-07-24", "天秤", 4 + 56 / 60, " 三重合"),
        ("2000-05-28", "金牛", 22 + 43 / 60, " 换三分性"), ("2020-12-21", "水瓶", 29 / 60, " 换三分性"),
    ]
    got = {line[:10]: line for line in rows[2:]}
    for date, sign, deg, flags in published:
        m = re.fullmatch(rf"{date} ({'|'.join(signs)}) (\d+\.\d\d)°(.*)", got[date])
        assert m and m.group(1) == sign and m.group(3) == flags, got[date]
        assert abs(float(m.group(2)) - deg) < 0.02, (got[date], deg)
    # 1960–2030 之间恰这六次（上游同一断言）。
    assert [d[:7] for d in sorted(got) if "1960" <= d[:4] <= "2030"] == ["1961-02", "1980-12", "1981-03", "1981-07", "2000-05", "2020-12"]
    # 经典档只留三连合的第一合（上游 test_classic_keeps_the_first_of_a_triple_conjunction）。
    classic = _live_rows(tmp_path, cycleVariant="classic")
    assert "算法：经典" in classic and not [line for line in classic if "三重合" in line]
    assert [line[:7] for line in classic if "1960" <= line[:4] <= "2030" and line[4] == "-"] == ["1961-02", "1980-12", "2000-05", "2020-12"]


@requires_chart
@requires_current_runtime_contract
def test_live_year_tables_match_the_upstream_fixed_samples_for_1701(tmp_path) -> None:
    """上游 test_thousands_row_fixed_sample / test_world_year_row_fixed_sample（手算值）：1701 年。"""
    thousands = _live_rows(tmp_path, year=1701, cycleTable="thousands")
    assert thousands[1] == "1701 千年主 火 转主 土 季摄 火"
    world = _live_rows(tmp_path, year=1701, cycleTable="worldYears")
    # worldYear 184802 · 世主 Mars · dirYear 122.0 → 狮子 2.00° · profYear 60.0 → 双子 0.00° · 法达三级 Mars · 季摄 Sun · 颤动 7.45°。
    assert world[1] == "1701 世界年 184802 世主 火 方向 狮子 2.00° 小限 双子 0.00° 法达 火 中 火 小 火 季摄 日 颤动 7.45°"
    # 起始年是入参：盘面年份 2025、起始年 1701 → 首行年份随之（行多时快照取目标年前后，1701 起 40 行里靠后的 12 行）。
    shifted = _live_rows(tmp_path, cycleTable="thousands", cycleStartYear=1701)
    assert shifted[-1] == "其余 28 行略" and shifted[1].startswith("1729 ") and shifted[-2].startswith("1740 ")


@requires_chart
@requires_current_runtime_contract
def test_live_turns_and_firdaria_follow_the_documented_orders(tmp_path) -> None:
    # 千年轮转：巨蟹起、迦勒底序土木火…，洪水 a 自公元前 3381 年、b 自公元前 3102 年（上游 test_turns_walk_cancer_and_the_chaldean_order）。
    turns = _live_rows(tmp_path, cycleTable="turns")
    assert turns[1] == "起点：公元前 3381 年起" and turns[2] == "年长：恒星年"
    assert [line.split(" ", 1)[1] for line in turns[3:6]] == ["巨蟹 土", "狮子 木", "处女 火"]
    assert turns[3].startswith("-3381-09-23 ")
    flood_b = _live_rows(tmp_path, cycleTable="turns", flood="b")
    assert flood_b[1] == "起点：公元前 3102 年起" and flood_b[3].startswith("-3102-02-18 ")
    # 世运法达中档：日、月、北交…每段 75 年（上游 test_middle_firdaria_is_seventy_five_years_each）。
    middle = _live_rows(tmp_path, cycleTable="firdaria", firdariaLevel="middle")
    assert middle[1] == "档：中(75 年)"
    assert [line.split(" ", 1)[1] for line in middle[3:6]] == ["日 75 年", "月 75 年", "北交 75 年"]
    # 小档首段：改进 10 年、经典 9 年（上游 test_lesser_firdaria_standard_and_classic_sum_to_seventy_five）。
    lesser = _live_rows(tmp_path, cycleTable="firdaria", firdariaLevel="lesser")
    classic = _live_rows(tmp_path, cycleTable="firdaria", firdariaLevel="lesser", cycleVariant="classic")
    first = lambda rows: next(line for line in rows if re.match(r"-?\d+-\d\d-\d\d ", line))  # noqa: E731
    assert first(lesser).endswith(" 10 年") and first(classic).endswith(" 9 年") and "算法：经典" in classic


_TABLES = sorted(t for t in FIX["mundanecycles"] if "_" not in t)


@requires_chart
@requires_current_runtime_contract
@pytest.mark.parametrize("table", _TABLES)
def test_live_every_cycle_table_makes_a_clean_section(tmp_path, table) -> None:
    assert len(_TABLES) == 14
    rows = _live_rows(tmp_path, cycleTable=table)
    assert rows[0].startswith("表：") and len(rows) >= 3, rows
    # 与抓夹具时同一引擎、同一请求 → 正文逐字相同（夹具 section = 真 builder 对未裁响应的原文）。气象占 / 世俗主限随盘面地点，hsys 无关。
    if table not in {"directions"}:  # 世俗主限随宫制（本用例 hsys 1，夹具 hsys 0）
        assert rows == FIX["mundanecycles"][table]["section"], table


# 「改这个参数，结果必须变」：每个选项键在它起作用的那张表上改一档，[世运周期表] 正文必须与缺省不同。
_KNOBS = [
    ("conjunctions", {"conjKind": "middle"}), ("conjunctions", {"conjKind": "lesser"}), ("conjunctions", {"cycleVariant": "classic"}),
    ("conjunctions", {"cycleStartYear": 1500, "cycleEndYear": 1600}),
    ("meanConjunctions", {"meanTable": "table7"}), ("turns", {"flood": "b"}), ("turns", {"cycleYear": "solar"}),
    ("firdaria", {"firdariaLevel": "middle"}), ("firdaria", {"firdariaYears": 100}), ("firdaria", {"cycleYear": "world"}),
    ("profections", {"profRate": "monarchy"}), ("profections", {"profBase": "ingress"}), ("profections", {"cycleVariant": "classic"}),
    ("thousands", {"cycleStartYear": 1701}), ("dawr", {"dawrStart": "b"}), ("era", {"eraKind": "change"}),
    ("revolution", {"ingressPoint": 90}), ("weather", {"weatherMonths": 6}), ("weather", {"cycleVariant": "classic"}),
    ("directions", {"mpdKey": "Naibod"}),
]


@requires_chart
@requires_current_runtime_contract
@pytest.mark.parametrize("table,knob", _KNOBS, ids=[f"{t}:{'+'.join(k)}" for t, k in _KNOBS])
def test_live_each_cycle_option_changes_the_section(tmp_path, table, knob) -> None:
    base = _live_rows(tmp_path, cycleTable=table)
    changed = _live_rows(tmp_path, cycleTable=table, **knob)
    assert changed != base, (table, knob)


@requires_chart
@requires_current_runtime_contract
def test_live_barbault_set_and_harmonic_change_the_curve(tmp_path) -> None:
    def head_and_extrema(**extra):
        env = _live(tmp_path, **extra)
        assert not env.warnings, env.warnings
        return _section(env.data["snapshot_text"], "Barbault 聚散指数")

    base = head_and_extrema()
    assert base[0].startswith("（慢星组合 五慢星 ♃♄♅♆♇（默认） · 1900–2050 · ")
    harm = head_and_extrema(bbHarm=2)
    assert harm[0].startswith("（慢星组合 五慢星 ♃♄♅♆♇（默认） · 2 次谐波 · 1900–2050 · ") and harm[1] != base[1]
    outer = head_and_extrema(bbSet="outer3")
    assert outer[0].startswith("（慢星组合 仅外三星 ♅♆♇（最平滑） · 1900–2050 · ") and outer[1] != base[1]
    # 仅外三星 3 对 → 满刻度 540°（上游 test_outer_three_variant_smooth_minima）；谐波后每对仍折到 0–180，峰值不超 540。
    peak = lambda rows: int(re.search(r"最高峰（四散）\d+-\d\d（(\d+)°）", rows[1]).group(1))  # noqa: E731
    assert peak(outer) <= 540 and peak(head_and_extrema(bbSet="outer3", bbHarm=12)) <= 540
    assert peak(base) <= 1800
