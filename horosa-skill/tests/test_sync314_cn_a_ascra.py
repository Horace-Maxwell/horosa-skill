"""星阙 v3.14.0「上升起盘两档」（ascRaMode）：宿占 / 节气盘宿盘 / 七政赤仪 / 三式合一外圈赤道分宫。

上游（release：「上升起盘两档(结果会变):二十八宿 / 宿占 / 节气盘 / 七政赤仪分改进(真赤经)/ 经典(东点黄经)」）：
  后端四轴的赤经此前不是真值 —— 上升点的 ra 实为「东点的黄经」。v3.14.0 起 ra = 黄道上升点的真赤经，旧值作为上升点对象的
  eastPointLon 单独下发；用上升赤经定命宫 / 画上升的盘要表态取哪一个。单一来源 utils/ascRaMode.js（verbatim vendored）：
  normalizeAscRaMode / withAscRaMode(Root) / ascRaModeSnapshotLine / guolaoAscRaModeOf，缺省 improved。
  · 宿占 SuZhanMain.js suzhanAscRaModeOf：只在「ASC 起盘」时起作用，[起盘信息] 多一行「上升取法：…」；
  · 节气盘 JieQiChartsMain.js buildJieQiSuSection：内嵌宿盘跟随同一设置，ASC 起盘时段首写明；
  · 七政 guolao/main/snapshot.js _buildGuolaoSnapshotTextV2Core：只在赤仪（chart.displayCoord === 'equatorial'）起作用；
  · 三式 SanShiUnitedMain.js buildOuterData(rawChartObj, coord, ascRaMode)：只在外圈赤道分宫时起作用。

skill 侧：四个技法收 ascRaMode（improved / classic），三式另开外圈坐标 outerCoord（上游页面设置，此前 skill 写死黄道）；
宿占快照改成 verbatim vendored（suzhan/SuZhanMain.js），节气盘宿盘是 Python 端口 → 换法也移植到 Python 并与 vendored JS 差分。

期望值的独立来源：
  ① 上游自己的测试夹具 utils/__tests__/ascRaModeTwoTiers.test.js（上升真赤经 100° 巨蟹 / 东点黄经 85° 双子：改进「巨蟹座—第1宫」、
     经典「巨蟹座—第2宫」；三式外圈第 1 宫落 未 / 申）；
  ② 录制的 v3.14.0 后端真值（tests/fixtures/sync314_cn_a_live.json.gz）上按定义手算：命宫座 = floor(所取赤经 / 30)，
     第 N 宫 = (该座序 − 命宫座序 + 12) % 12 + 1，宿内度 = 所取赤经 − 该宿距星赤经。

负向对照（实跑过，逐条见各用例 docstring 末行「负向」）：
- tools/suzhan.js 去掉 `fields.ascRaMode = { value: p.ascRaMode }` → 宿占经典档三条用例红（第 1 宫仍落巨蟹、无「经典」行）；
- astro_snapshot.build_jieqi_su_section 去掉 with_asc_ra_mode_root → 节气盘经典档红（夏至 / 秋分命宫不换座）；
- astro_snapshot.with_asc_ra_mode 改成就地改 asc["ra"] → 差分用例红（入参被改）；
- tools/guolaoMoira.js info_sections 不调 applyGuolaoAscRaMode（直接用 src.chart）→ 七政经典档红（上升宿内度 / 大限首限不变）；
- tools/sanshiUnited.js 把 buildOuterData 第二参写回 'ecliptic' → 三式赤道分宫两条红；第三参去掉 → 经典档红；
- runners 里去掉 _warn_asc_ra_mode_inert → 「给了 classic 但不起作用」三条告警用例红。
"""

from __future__ import annotations

import copy
import gzip
import json
import math
import subprocess
from pathlib import Path

import pytest
from fakes import FakeClient
from test_local_js_tools import make_service, requires_runtime
from test_sync311_w3b_gim import GUOLAO_FIX, _guolao_run, _section, _service, requires_node

from horosa_skill.engine import astro_snapshot as snap
from horosa_skill.schemas.tools.astro import GuoLaoInput
from horosa_skill.schemas.tools.base import advertise_hidden_fields
from horosa_skill.schemas.tools.cn_divination import SanShiUnitedInput, SuZhanInput
from horosa_skill.schemas.tools.cn_mingli import JieQiYearInput
from horosa_skill.western_vocab import ASC_RA_MODE, ASC_RA_MODE_DEFAULT, SANSHI_OUTER_COORD, SANSHI_OUTER_COORD_DEFAULT

ROOT = Path(__file__).resolve().parents[1]
CORE_JS = ROOT / "horosa-core-js"
FIX = json.loads(gzip.decompress((ROOT / "tests" / "fixtures" / "sync314_cn_a_live.json.gz").read_bytes()))

IMPROVED_LINE = "上升取法：改进(上升点真赤经,与行星、宫头同一坐标)"
CLASSIC_LINE = "上升取法：经典(东点黄经,旧版口径)"
CLASSIC_FALLBACK_LINE = "上升取法：经典(东点黄经,旧版口径);本盘未带东点黄经,实际按真赤经"

# 上游常量（逐值，独立于 vendored JS）：AstroConst.LIST_SIGNS 序的 SZConst.SignZi 地支 / SZSigns 星次 / AstroMsgCN 星座名。
_SIGNS = (
    ("戌", "降娄", "白羊"), ("酉", "大梁", "金牛"), ("申", "实沉", "双子"), ("未", "鹑首", "巨蟹"), ("午", "鹑火", "狮子"), ("巳", "鹑尾", "处女"),
    ("辰", "寿星", "天秤"), ("卯", "大火", "天蝎"), ("寅", "析木", "射手"), ("丑", "星纪", "摩羯"), ("子", "玄枵", "水瓶"), ("亥", "娵訾", "双鱼"),
)

# 上游 ascRaModeTwoTiers.test.js 的夹具盘：上升真赤经 100°(巨蟹段)，东点黄经 85°(双子段)：两档命宫差一座。
_UP_ASC = {"id": "Asc", "lon": 95, "ra": 100, "eastPointLon": 85, "sign": "Cancer", "signlon": 5}
_UP_SUN = {"id": "Sun", "lon": 40, "ra": 37.6, "sign": "Taurus", "signlon": 10, "house": "House11", "su28": "昴"}


def _up_chart(asc: dict | None = None) -> dict:
    return {"houses": [{"id": "House1", "lon": 95}, {"id": "House2", "lon": 125}], "objects": [asc or _UP_ASC, _UP_SUN], "fixedStarSu28": []}


def _node(script: str) -> object:
    done = subprocess.run(["node", "-e", script], cwd=CORE_JS, capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(done.stdout)


def _replay(tmp_path, case: str, extra: dict | None = None, *, drop: tuple[str, ...] = ()):
    """录制的后端往返 + 真 JS 引擎：按 [endpoint, backend, payload] 回放；没录过的请求直接失败（不许静默落到桩）。"""
    fix = FIX["cases"][case]
    service = _service(tmp_path, FakeClient())
    seen: list[tuple[str, dict]] = []

    def replay(endpoint, payload, *, backend=None):
        seen.append((endpoint, copy.deepcopy(payload)))
        keyed = payload
        if endpoint == "/qizheng/moira":   # 请求体带两张整盘（本命 / 流年），夹具键只留参数
            keyed = {k: v for k, v in payload.items() if k not in ("chartObj", "transitChartObj")}
        key = json.dumps([endpoint, backend, keyed], ensure_ascii=False, sort_keys=True, default=str)
        if key not in FIX["responses"]:
            raise AssertionError(f"unrecorded backend call for {case}: {endpoint} backend={backend} payload={payload}")
        return copy.deepcopy(FIX["responses"][key])

    service._call_remote = replay
    payload = {k: v for k, v in {**fix["payload"], **(extra or {})}.items() if k not in drop}
    env = service.run_tool(fix["tool"], payload, save_result=False)
    return env, seen


def _asc_of(chart: dict) -> dict:
    return next(o for o in chart["objects"] if o["id"] == "Asc")


def _recorded_chart(case: str, endpoint: str = "/chart", *, predictive: bool = False) -> dict:
    for key in FIX["cases"][case]["calls"]:
        ep, _backend, payload = json.loads(key)
        if ep == endpoint and bool(payload.get("predictive")) == predictive:
            return FIX["responses"][key]
    raise AssertionError(f"no recorded {endpoint} for {case}")


def _deg_min(value: float) -> tuple[int, int]:
    """上游 AstroHelper.signDegMin：座内整度 / 整分（均向下取整）。"""
    d = value + 360 if value < 0 else value
    whole = math.floor(d % 30)
    return whole, math.floor(((d % 30) - whole) * 60)


def _house_label(sign_idx: int, life_idx: int) -> str:
    zi, area, cn = _SIGNS[sign_idx]
    return f"{zi}—{area}—{cn}座—第{(sign_idx - life_idx + 12) % 12 + 1}宫"


# ───────────────────────────── 词表 / schema ─────────────────────────────
@requires_node
def test_vocabularies_are_anchored_to_the_vendored_upstream_tables() -> None:
    """ascRaMode / outerCoord 的规范值与缺省 = vendored 上游表（utils/ascRaMode.js ASC_RA_MODE_OPTIONS；SANSHI_PAGE_SETTINGS.schema）。"""
    up = _node(
        "Promise.all([import('./src/vendor/utils/ascRaMode.js'),import('./src/vendor/sanshi/main/options.js')]).then(([a,s])=>{"
        "console.log(JSON.stringify({values:a.ASC_RA_MODE_OPTIONS.map((o)=>o.value),labels:a.ASC_RA_MODE_OPTIONS.map((o)=>o.label),"
        "def:a.ASC_RA_MODE_DEFAULT,coord:s.SANSHI_PAGE_SETTINGS.schema.outerCoord.oneOf,coordDef:s.SANSHI_PAGE_SETTINGS.defaults().outerCoord,"
        "sanshiAsc:s.SANSHI_PAGE_SETTINGS.schema.ascRaMode.oneOf,sanshiAscDef:s.SANSHI_PAGE_SETTINGS.defaults().ascRaMode}));});"
    )
    assert [item["value"] for item in ASC_RA_MODE.accepted] == up["values"] == up["sanshiAsc"] == ["improved", "classic"]
    assert up["labels"] == ["改进（真赤经）", "经典（东点黄经）"]
    assert ASC_RA_MODE_DEFAULT == up["def"] == up["sanshiAscDef"] == "improved"
    assert (snap.ASC_RA_MODE_IMPROVED, snap.ASC_RA_MODE_CLASSIC) == tuple(up["values"])
    assert [item["value"] for item in SANSHI_OUTER_COORD.accepted] == up["coord"] == ["ecliptic", "equatorial"]
    assert SANSHI_OUTER_COORD_DEFAULT == up["coordDef"] == "ecliptic"
    # 上游两档的中文名都是别名
    assert ASC_RA_MODE.parse("改进（真赤经）").value == "improved" and ASC_RA_MODE.parse("经典（东点黄经）").value == "classic"


@pytest.mark.parametrize("model", [SuZhanInput, GuoLaoInput, SanShiUnitedInput, JieQiYearInput])
def test_four_tools_declare_asc_ra_mode_hidden_and_reject_unknown_values(model) -> None:
    """四个技法都声明 ascRaMode（校验层收、认不出即拒），不进 tools/list 广告层（预算），说明走 guidance。"""
    base = {"date": "1990-05-17", "time": "07:30:27", "zone": "+08:00", "lat": "31n14", "lon": "121e28", "year": 2028}
    assert model(**base).ascRaMode is None
    assert model(**base, ascRaMode="经典").ascRaMode == "classic"
    assert model(**base, ascRaMode="improved").ascRaMode == "improved"
    with pytest.raises(Exception) as err:
        model(**base, ascRaMode="eastpoint-ish")
    assert "ascRaMode" in str(err.value)
    assert "ascRaMode" in advertise_hidden_fields(model)


def test_guidance_documents_the_new_keys() -> None:
    from horosa_skill.agent_guidance import build_agent_guidance

    def keys_of(tool: str) -> dict:
        return build_agent_guidance(tool_name=tool)["tools"][tool]["options_keys"]

    for tool in ("suzhan", "guolao_chart", "jieqi_year", "sanshiunited"):
        doc = keys_of(tool)["ascRaMode"]
        assert "improved" in doc and "classic" in doc and "warnings" in doc, tool
    assert "outerCoord" in keys_of("sanshiunited")["options"] and "equatorial" in keys_of("sanshiunited")["options"]
    assert "ASC 起盘" in keys_of("jieqi_year")["houseStartMode"]
    assert "ascRaMode" in keys_of("suzhan")["houseStartMode"]


# ───────────────────────────── Python 端口 ↔ vendored JS 差分 ─────────────────────────────
_DIFF_CHARTS = [
    _up_chart(),
    {**_up_chart(), "objectMap": {"Asc": _UP_ASC}},                       # 懒缓存要拿掉
    _up_chart({"id": "Asc", "lon": 95, "ra": 100}),                      # 老响应：没有 eastPointLon
    _up_chart({"id": "Asc", "lon": 95, "ra": 100, "eastPointLon": None}),
    _up_chart({"id": "Asc", "lon": 95, "ra": 100, "eastPointLon": ""}),
    _up_chart({"id": "Asc", "lon": 95, "ra": 100, "eastPointLon": "85.5"}),   # 数字串
    _up_chart({"id": "Asc", "lon": 95, "ra": 100, "eastPointLon": 100}),      # 两值相同 → 原样
    _up_chart({"id": "Asc", "lon": 95, "ra": 100, "eastPointLon": "abc"}),
    {"houses": [], "objects": [_UP_SUN]},                                 # 没有上升点
    {"houses": []},
]


@requires_node
def test_python_asc_ra_port_matches_the_vendored_js_on_every_shape() -> None:
    """节气盘宿盘是 Python 端口，换法也在 Python：with_asc_ra_mode(_root) / chart_has_east_point / asc_ra_mode_snapshot_line
    对一批形状（有 / 无 / 空 / 数字串 / 相同 / 非数的 eastPointLon、带 objectMap、无上升点）与 vendored utils/ascRaMode.js 逐字同。
    负向：with_asc_ra_mode 改成就地改 asc["ra"] → 「不改入参」断言红；去掉 objectMap 剔除 → 第 2 张盘红。"""
    modes = ["improved", "classic", "nonsense", None]
    script = (
        "import('./src/vendor/utils/ascRaMode.js').then((m)=>{const charts=" + json.dumps(_DIFF_CHARTS, ensure_ascii=False)
        + ";const modes=" + json.dumps(modes)
        + ";const out=[];charts.forEach((c)=>{modes.forEach((mode)=>{const root={chart:c,params:{}};out.push({"
        "chart:m.withAscRaMode(c,mode),root:m.withAscRaModeRoot(root,mode),line:m.ascRaModeSnapshotLine(mode,c),"
        "east:m.chartHasEastPoint(c),norm:m.normalizeAscRaMode(mode)});});});console.log(JSON.stringify(out));});"
    )
    up = iter(_node(script))
    for chart in _DIFF_CHARTS:
        for mode in modes:
            want = next(up)
            before = copy.deepcopy(chart)
            root = {"chart": chart, "params": {}}
            assert snap.with_asc_ra_mode(chart, mode) == want["chart"], (chart, mode)
            assert snap.with_asc_ra_mode_root(root, mode) == want["root"], (chart, mode)
            assert snap.asc_ra_mode_snapshot_line(mode, chart) == want["line"], (chart, mode)
            assert snap.chart_has_east_point(chart) is want["east"], chart
            assert snap.normalize_asc_ra_mode(mode) == want["norm"]
            assert chart == before, "入参被就地改了"
    # 改进档 / 无旧值：同一个对象原样返回（上游 toBe 同引用）
    legacy = _DIFF_CHARTS[2]
    assert snap.with_asc_ra_mode(legacy, "classic") is legacy and snap.with_asc_ra_mode(_DIFF_CHARTS[0], "improved") is _DIFF_CHARTS[0]
    assert snap.asc_ra_mode_snapshot_line("classic", legacy) == CLASSIC_FALLBACK_LINE


# ───────────────────────────── 上游测试夹具上的值级金标 ─────────────────────────────
@requires_node
def test_suzhan_tool_reproduces_the_upstream_two_tier_fixture() -> None:
    """上游 ascRaModeTwoTiers.test.js「两档命宫不同(真赤经巨蟹 / 东点黄经双子)」：改进「巨蟹座—第1宫」、经典「巨蟹座—第2宫」并写明
    档位；八字公式起盘不出这一行、恒按改进；不就地改盘。经 tools/suzhan.js 的 runSuzhan 入口。
    负向：tools/suzhan.js 去掉 fields.ascRaMode 注入 → 经典档仍出「第1宫」「改进」。"""
    chart = {"chart": _up_chart(), "params": {}}
    script = (
        "import('./src/tools/suzhan.js').then((m)=>{const chart=" + json.dumps(chart, ensure_ascii=False)
        + ";const run=(hs,mode)=>m.runSuzhan({chart,params:{date:'1990-01-01',time:'12:00:00',houseStartMode:hs,doubingSu28:0,ascRaMode:mode}});"
        "console.log(JSON.stringify({imp:run(1,undefined),impX:run(1,'improved'),cls:run(1,'classic'),bazi:run(0,'classic'),ra:chart.chart.objects[0].ra}));});"
    )
    out = _node(script)
    for key in ("imp", "impX"):
        lines = out[key]["text"].split("\n")
        # 上游断言只到「巨蟹座—第1宫」（/巨蟹座—第1宫/）。v3.15.0 宿占改按赤经分宫、星曜按赤经落宫，上升本身也落进第 1 宫一行，
        # 行尾不再是「无 | 无」—— 这里与上游同口径只钉宫位列。
        assert IMPROVED_LINE in lines and any(line.startswith("| 未—鹑首—巨蟹座—第1宫 |") for line in lines), key
        assert out[key]["data"]["ascRaMode"] == "improved"
    lines = out["cls"]["text"].split("\n")
    assert CLASSIC_LINE in lines and any(line.startswith("| 未—鹑首—巨蟹座—第2宫 |") for line in lines)
    assert lines[lines.index("人事十二宫起盘：ASC起盘") + 1] == CLASSIC_LINE   # 紧跟起盘行（SuZhanMain.js:355-357）
    assert out["cls"]["data"] == {"ok": True, "nongliHour": None, "ascRaMode": "classic", "eastPointAvailable": True}
    assert "上升取法" not in out["bazi"]["text"] and out["bazi"]["data"]["ascRaMode"] == "improved"
    assert out["ra"] == 100   # 不就地改盘


def test_jieqi_su_section_two_tiers_on_the_upstream_fixture() -> None:
    """节气盘 [X宿盘]（Python 端口）在同一张上游夹具盘上：ASC 起盘时段首写明档位，改进第 1 宫 = 巨蟹、经典第 2 宫；
    八字公式起盘（缺省）不写这一行、恒按改进（JieQiChartsMain.js buildJieQiSuSection + suzhanAscRaModeOf）。
    负向：build_jieqi_su_section 去掉 with_asc_ra_mode_root → 经典档第一行宫位仍是「第1宫」。"""
    root = {"chart": _up_chart(), "params": {}}
    improved = snap.build_jieqi_su_section(root, {"houseStartMode": 1}).split("\n")
    assert improved[:2] == [IMPROVED_LINE, "宫位：未—鹑首—巨蟹座—第1宫"]
    classic = snap.build_jieqi_su_section(root, {"houseStartMode": 1, "ascRaMode": "classic"}).split("\n")
    assert classic[:2] == [CLASSIC_LINE, "宫位：未—鹑首—巨蟹座—第2宫"]
    # wrapper 形 fields（上游页面形）同口径
    assert snap.build_jieqi_su_section(root, {"houseStartMode": {"value": 1}, "ascRaMode": {"value": "classic"}}).split("\n") == classic
    bazi = snap.build_jieqi_su_section(root, {"ascRaMode": "classic"}).split("\n")
    assert bazi[0] == "宫位：未—鹑首—巨蟹座—第1宫" and not any("上升取法" in line for line in bazi)
    assert root["chart"]["objects"][0]["ra"] == 100
    legacy = {"chart": _up_chart({"id": "Asc", "lon": 95, "ra": 100}), "params": {}}
    assert snap.build_jieqi_su_section(legacy, {"houseStartMode": 1, "ascRaMode": "classic"}).split("\n")[:2] == [
        CLASSIC_FALLBACK_LINE, "宫位：未—鹑首—巨蟹座—第1宫"]


@requires_node
def test_guolao_setup_line_and_swap_follow_the_display_coord() -> None:
    """七政：赤仪（displayCoord=equatorial）才读上升赤经——applyGuolaoAscRaMode 经典档把上升点 ra 换成东点黄经、[起盘信息] 在
    「宿度制」行后多一行；黄仪恒原样、不加行（main/snapshot.js:1129-1133 / :1169）。fields.ascRaMode 缺省 = improved。"""
    script = (
        "import('./src/vendor/guolao/guolaoSnapshotSections.js').then((m)=>{const mk=(coord)=>({chart:{displayCoord:coord,objects:["
        + json.dumps(_UP_ASC) + "," + json.dumps(_UP_SUN) + "]},params:{}});const out={};"
        "[['eq','equatorial'],['ecl','ecliptic']].forEach(([k,coord])=>{['classic','improved',null].forEach((mode)=>{"
        "const fields=mode?{ascRaMode:{value:mode}}:{};const raw=mk(coord);const r=m.applyGuolaoAscRaMode(raw,fields);"
        "out[`${k}:${mode}`]={mode:r.ascRaMode,ra:r.result.chart.objects[0].ra,same:r.result===raw,rawRa:raw.chart.objects[0].ra,"
        "lines:m.buildGuolaoSetupLines(fields,{},undefined,r.result.chart,r.ascRaMode)};});});console.log(JSON.stringify(out));});"
    )
    out = _node(script)
    assert out["eq:classic"]["mode"] == "classic" and out["eq:classic"]["ra"] == 85 and out["eq:classic"]["rawRa"] == 100
    assert out["eq:improved"]["ra"] == 100 and out["eq:improved"]["same"] is True and out["eq:null"]["mode"] == "improved"
    lines = out["eq:classic"]["lines"]
    at = next(i for i, line in enumerate(lines) if line.startswith("宿度制："))
    assert lines[at + 1] == CLASSIC_LINE and lines[at + 2].startswith("命主取法：")
    assert out["eq:null"]["lines"][at + 1] == IMPROVED_LINE
    for key in ("ecl:classic", "ecl:improved", "ecl:null"):   # 黄仪：恒改进、不换、不加行
        assert out[key]["mode"] == "improved" and out[key]["ra"] == 100 and out[key]["same"] is True
        assert not any("上升取法" in line for line in out[key]["lines"])


@requires_node
def test_sanshi_outer_ring_reproduces_the_upstream_two_tier_fixture() -> None:
    """上游同文件「三式:只在外圈赤道分宫时起作用」：赤道分宫第 1 宫落 未（赤经 100° 巨蟹段）/ 申（东点黄经 85° 双子段），
    快照行挂在第 1 宫那一支；黄道分宫逐字现状。经 tools/sanshiUnited.js 的 resolveSanshiOuter（词表锚 vendored schema）。"""
    script = (
        "Promise.all([import('./src/tools/sanshiUnited.js'),import('./src/vendor/sanshi/main/outerRing.js')]).then(([t,v])=>{"
        "const chart=" + json.dumps(_up_chart(), ensure_ascii=False) + ";"
        "const first=(od)=>Object.keys(od.housesByBranch).find((b)=>od.housesByBranch[b].indexOf('1')>=0);"
        "const run=(input)=>{const o=t.resolveSanshiOuter(input);if(!o.ok){return {error:o.error};}"
        "const od=v.buildOuterData(chart,o.outerCoord,o.ascRaMode);return {outer:o,first:first(od),line:od.ascRaLine||null};};"
        "console.log(JSON.stringify({def:run({}),eq:run({outerCoord:'equatorial'}),cls:run({outerCoord:'equatorial',ascRaMode:'classic'}),"
        "eclCls:run({ascRaMode:'classic'}),bad:run({outerCoord:'galactic'}),badAsc:run({ascRaMode:'east'})}));});"
    )
    out = _node(script)
    assert out["def"] == {"outer": {"ok": True, "outerCoord": "ecliptic", "ascRaMode": "improved"}, "first": "未", "line": None}
    assert out["eq"]["first"] == "未" and out["eq"]["line"] == IMPROVED_LINE
    assert out["cls"]["first"] == "申" and out["cls"]["line"] == CLASSIC_LINE
    assert out["eclCls"]["first"] == "未" and out["eclCls"]["line"] is None   # 黄道分宫不读上升赤经
    assert out["bad"]["error"]["code"] == "invalid_option" and out["bad"]["error"]["allowed"] == ["ecliptic", "equatorial"]
    assert out["badAsc"]["error"]["field"] == "ascRaMode"


# ───────────────────────────── 录制的 v3.14.0 后端真值：端到端回放 ─────────────────────────────
@requires_node
@pytest.mark.parametrize("case", ["suzhan_asc", "suzhan_bazi", "guolao_eq", "jieqi_year", "sanshiunited", "liureng_gods", "jinkou"])
def test_offline_replay_reproduces_the_live_snapshot(tmp_path, case: str) -> None:
    """回放链（录制的后端真值 + 真 JS 引擎）逐字复现录制时的 live 快照——夹具裁剪（大运表 / 恒星表）不改一字，导出契约 clean。"""
    env, _ = _replay(tmp_path, case)
    assert env.ok, env.error
    assert env.data["snapshot_text"] == FIX["cases"][case]["live_snapshot_text"]
    assert list(env.warnings or []) == []
    exp = env.data["export_snapshot"]
    assert exp["missing_selected_sections"] == [] and exp["unknown_detected_sections"] == []


def test_recorded_backend_carries_true_ra_and_the_east_point() -> None:
    """夹具前提（v3.14.0 后端）：上升点 ra = 真赤经、eastPointLon = 东点黄经，两值不同系且落不同座；别的对象不带 eastPointLon。
    真赤经独立复核：tan(α) = cos(ε)·tan(λ)（黄纬 0 的点），ε 取 23.44°（1990 年，容差 0.01°）。"""
    chart = _recorded_chart("suzhan_asc")["chart"]
    asc = _asc_of(chart)
    lam = math.radians(asc["lon"])
    alpha = math.degrees(math.atan2(math.cos(math.radians(23.4406)) * math.sin(lam), math.cos(lam))) % 360
    assert abs(alpha - asc["ra"]) < 0.01, (alpha, asc["ra"])
    assert math.floor(asc["ra"] / 30) == 3 and math.floor(asc["eastPointLon"] / 30) == 2   # 巨蟹 / 双子
    assert all(o.get("eastPointLon") is None for o in chart["objects"] if o["id"] != "Asc")


def _suzhan_expected_rows(chart: dict, used_ra: float) -> tuple[str, str]:
    """命宫行（第 1 宫）与「上升」星曜项，按定义手算：命宫座 = floor(所取赤经/30)；宿内度 = 所取赤经 − 该宿距星赤经。"""
    asc = _asc_of(chart)
    life_idx = math.floor(used_ra / 30)
    ref = next(s for s in chart["fixedStarSu28"] if s["name"] == asc["su28"])
    d, m = _deg_min((used_ra - ref["ra"]) % 360)
    return _house_label(life_idx, life_idx), f"上升 {d}˚{asc['su28']}{m}分"


@requires_node
@pytest.mark.parametrize("mode", ["improved", "classic"])
def test_suzhan_asc_start_follows_the_chosen_ascendant(tmp_path, mode: str) -> None:
    """宿占 ASC 起盘两档（录制盘：上升真赤经 93.6° 巨蟹 / 东点黄经 79.3° 双子）：命宫座与「上升」宿内度都按所取的那个赤经。
    改进：巨蟹座—第1宫；经典：双子座—第1宫（巨蟹成第 2 宫）。[起盘信息] 写明档位，data.ascRaMode 回报实际档，后端请求不带该键。
    负向：tools/suzhan.js 去掉 fields.ascRaMode 注入 → 经典档命宫仍巨蟹、无「经典」行。"""
    env, seen = _replay(tmp_path, "suzhan_asc", {"ascRaMode": mode})
    assert env.ok, env.error
    chart = _recorded_chart("suzhan_asc")["chart"]
    asc = _asc_of(chart)
    used = asc["ra"] if mode == "improved" else asc["eastPointLon"]
    life_row, asc_item = _suzhan_expected_rows(chart, used)
    text = env.data["snapshot_text"]
    info = _section(text, "起盘信息").split("\n")
    assert info[-2:] == ["人事十二宫起盘：ASC起盘", IMPROVED_LINE if mode == "improved" else CLASSIC_LINE]
    rows = _section(text, "宿盘宫位与二十八宿星曜").split("\n")
    assert any(row.startswith(f"| {life_row} |") for row in rows), life_row   # 同座可有两个宫头（Alcabitius），行可重
    assert not any("第1宫" in row and not row.startswith(f"| {life_row} |") for row in rows)
    assert life_row == ("未—鹑首—巨蟹座—第1宫" if mode == "improved" else "申—实沉—双子座—第1宫")
    assert sum(1 for row in rows if asc_item in row) == 1, asc_item
    assert all(("第1宫" if mode == "improved" else "第2宫") in row for row in rows if "巨蟹座" in row)
    assert env.data["ascRaMode"] == mode and list(env.warnings or []) == []
    assert all("ascRaMode" not in payload for _ep, payload in seen)
    assert _asc_of(env.data["chart"])["ra"] == asc["ra"]   # 回给调用方的盘是后端原盘


@requires_node
def test_suzhan_classic_is_inert_and_says_so_under_the_bazi_formula(tmp_path) -> None:
    """八字公式起盘不读上升赤经（上游 suzhanAscRaModeOf 恒改进）：给 classic 快照逐字同缺省、不写「上升取法」，warnings 说明没起作用。
    负向：runner 去掉 _warn_asc_ra_mode_inert → warnings 为空。"""
    base, _ = _replay(tmp_path / "a", "suzhan_bazi")
    env, _ = _replay(tmp_path / "b", "suzhan_bazi", {"ascRaMode": "classic"})
    assert env.ok and env.data["snapshot_text"] == base.data["snapshot_text"]
    assert "上升取法" not in env.data["snapshot_text"] and env.data["ascRaMode"] == "improved"
    assert len(env.warnings) == 1 and "ascRaMode=classic 本次不起作用" in env.warnings[0] and "houseStartMode=1" in env.warnings[0]


@requires_node
def test_guolao_equatorial_classic_moves_the_ascendant_and_the_limits(tmp_path) -> None:
    """七政赤仪（缺省宿度制 0 荀爽距星）两档：经典档把上升点换成东点黄经 —— [起盘信息] 的档位行、[七政四余宫位与二十八宿星曜]
    里「上升」的宿内度（= 所取赤经 − 该宿距星赤经，手算）、[大限]（命度 = 上升显示度）都变。宫序不变：七政的「第 N 宫」按命度的
    **黄经**座起（上游 computeAscSignIndex → lifeDegree(chart, fields, true) 强制黄经），不读上升赤经。其余星曜行逐字同。
    负向：tools/guolaoMoira.js info_sections 直接用 src.chart → 经典档「上升」行与 [大限] 不变。"""
    imp, seen = _replay(tmp_path / "a", "guolao_eq")
    cls, _ = _replay(tmp_path / "b", "guolao_eq", {"ascRaMode": "classic"})
    assert imp.ok and cls.ok, (imp.error, cls.error)
    chart = _recorded_chart("guolao_eq")["chart"]
    assert chart["displayCoord"] == "equatorial"
    asc = _asc_of(chart)
    ref = next(s for s in chart["fixedStarSu28"] if s["name"] == asc["su28"])
    for env, used, line in ((imp, asc["ra"], IMPROVED_LINE), (cls, asc["eastPointLon"], CLASSIC_LINE)):
        info = _section(env.data["snapshot_text"], "起盘信息").split("\n")
        at = next(i for i, row in enumerate(info) if row.startswith("宿度制："))
        assert info[at + 1] == line and info[at + 2].startswith("命主取法：")
        life_idx = math.floor(asc["lon"] / 30)   # 宫序按命度黄经座（两档同）
        d, m = _deg_min((used - ref["ra"]) % 360)
        rows = _section(env.data["snapshot_text"], "七政四余宫位与二十八宿星曜").split("\n")
        hit = [row for row in rows if f"上升 {d}˚{asc['su28']}{m}分" in row]
        assert len(hit) == 1 and hit[0].startswith(f"| {_house_label(life_idx, life_idx)} |"), (hit, used)
    assert imp.data["ascRaMode"] == "improved" and cls.data["ascRaMode"] == "classic"
    # [大限] 首限年数 = 命度（上升显示度）在座内的余度折算（两档的上升差 14°、换了座）→ 表必不同
    assert _section(imp.data["snapshot_text"], "大限") != _section(cls.data["snapshot_text"], "大限")
    imp_rows = _section(imp.data["snapshot_text"], "七政四余宫位与二十八宿星曜").split("\n")
    cls_rows = _section(cls.data["snapshot_text"], "七政四余宫位与二十八宿星曜").split("\n")
    assert [r for r in imp_rows if "上升" not in r] == [r for r in cls_rows if "上升" not in r]   # 只有上升那一行变
    assert all("ascRaMode" not in payload for _ep, payload in seen)
    assert list(cls.warnings or []) == []


@requires_node
def test_guolao_ecliptic_classic_is_inert_and_says_so(tmp_path) -> None:
    """黄仪盘（sync311 录制盘，displayCoord=ecliptic）各环取黄经、不读上升赤经：给 classic 快照逐字同录制、无「上升取法」行，
    warnings 说明没起作用（上游 guolaoAscRaModeOf 黄仪恒改进）。"""
    assert GUOLAO_FIX["chart_natal"]["chart"]["displayCoord"] == "ecliptic"
    env, _ = _guolao_run(tmp_path, {"ascRaMode": "classic"})
    assert env.ok, env.error
    assert env.data["snapshot_text"] == GUOLAO_FIX["live_snapshot_text"] and "上升取法" not in env.data["snapshot_text"]
    assert env.data["ascRaMode"] == "improved"
    assert any("ascRaMode=classic 本次不起作用" in note and "赤仪宿度制" in note for note in env.warnings)


def _jieqi_charts() -> dict:
    for key in FIX["cases"]["jieqi_year"]["calls"]:
        ep, backend, _payload = json.loads(key)
        if ep == "/jieqi/year" and backend is None:
            return FIX["responses"][key]["charts"]
    raise AssertionError("no recorded /jieqi/year")


@requires_node
def test_jieqi_year_su_sections_follow_house_start_and_ascendant_mode(tmp_path) -> None:
    """节气盘四张 [X宿盘]（2028 北京）：houseStartMode=1 时段首写明上升取法，各宫「第 N 宫」按所取赤经的座起数。录制盘里夏至
    （真赤经 77.1° 双子 / 东点黄经 58.7° 金牛）与秋分（37.3° 金牛 / 26.5° 白羊）两档换座，春分 / 冬至同座。期望逐节气手算。
    缺省（八字公式）不写这一行；缺省 + classic → 逐字同缺省并进 warnings。
    负向：build_jieqi_su_section 去掉 with_asc_ra_mode_root → 经典档夏至 / 秋分首宫序号不变。"""
    base, _ = _replay(tmp_path / "a", "jieqi_year")
    imp, _ = _replay(tmp_path / "b", "jieqi_year", {"houseStartMode": 1})
    cls, seen = _replay(tmp_path / "c", "jieqi_year", {"houseStartMode": 1, "ascRaMode": "classic"})
    inert, _ = _replay(tmp_path / "d", "jieqi_year", {"ascRaMode": "classic"})
    assert all(env.ok for env in (base, imp, cls, inert))
    charts = _jieqi_charts()
    flipped = []
    for title in ("春分", "夏至", "秋分", "冬至"):
        chart = charts[title]["chart"]
        asc = _asc_of(chart)
        first_sign = math.floor((chart["houses"][0]["lon"] % 360) / 30)
        for env, used, line in ((imp, asc["ra"], IMPROVED_LINE), (cls, asc["eastPointLon"], CLASSIC_LINE)):
            rows = _section(env.data["snapshot_text"], f"{title}宿盘").split("\n")
            assert rows[0] == line, (title, rows[0])
            assert rows[1] == f"宫位：{_house_label(first_sign, math.floor(used / 30))}", (title, rows[1])
        if math.floor(asc["ra"] / 30) != math.floor(asc["eastPointLon"] / 30):
            flipped.append(title)
        assert not _section(base.data["snapshot_text"], f"{title}宿盘").startswith("上升取法")
    assert flipped == ["夏至", "秋分"]
    assert inert.data["snapshot_text"] == base.data["snapshot_text"]
    assert len(inert.warnings) == 1 and "节气盘 ascRaMode=classic 本次不起作用" in inert.warnings[0]
    assert list(cls.warnings or []) == [] and list(imp.warnings or []) == []
    # 两个前端设置都不进后端请求（上游两条 /jieqi/year 请求都不带）
    assert seen and all("ascRaMode" not in payload and "houseStartMode" not in payload for _ep, payload in seen)


# 上游 SanShiUnitedMain.js signToBranch 的地支序（BRANCH_ORDER 按黄道座：白羊=戌 … 双鱼=亥），与 _SIGNS[i][0] 同表。
@requires_node
def test_sanshiunited_outer_ring_coord_and_ascendant_mode(tmp_path) -> None:
    """三式合一外圈：缺省黄道分宫（逐字同录制）；outerCoord=equatorial 时星曜度数按赤经（标「（赤经）」）、人事宫位从上升赤经所在
    支起，第 1 宫那一支写明上升取法；经典档上升换成东点黄经（录制盘：巨蟹 未 → 双子 申）。黄道 + classic → 逐字同缺省并进 warnings。
    负向：tools/sanshiUnited.js buildOuterData 第二参写回 'ecliptic' → 赤道两条红；第三参去掉 → 经典档红。"""
    base, _ = _replay(tmp_path / "a", "sanshiunited")
    eq, _ = _replay(tmp_path / "b", "sanshiunited", {"outerCoord": "equatorial"})
    cls, seen = _replay(tmp_path / "c", "sanshiunited", {"outerCoord": "equatorial", "ascRaMode": "classic"})
    inert, _ = _replay(tmp_path / "d", "sanshiunited", {"ascRaMode": "classic"})
    assert all(env.ok for env in (base, eq, cls, inert)), [env.error for env in (base, eq, cls, inert)]
    asc = _asc_of(_recorded_chart("sanshiunited")["chart"])
    assert base.data["outer"] == {"outerCoord": "ecliptic", "ascRaMode": "improved", "eastPointAvailable": True}
    assert "上升取法" not in base.data["snapshot_text"] and "（赤经）" not in base.data["snapshot_text"]
    for env, used, line in ((eq, asc["ra"], IMPROVED_LINE), (cls, asc["eastPointLon"], CLASSIC_LINE)):
        text = env.data["snapshot_text"]
        lines = text.split("\n")
        assert lines.count(line) == 1
        at = lines.index(line)
        zi, _area, cn = _SIGNS[math.floor(used / 30)]
        # 第 1 宫那一支的小节 = 上升所取赤经的座（「未-巨蟹座」/「申-双子座」），档位行挂在这一小节里
        head_at = max(i for i, row in enumerate(lines[:at]) if row.startswith("「"))
        assert lines[head_at] == f"「{zi}-{cn}座」" and lines[head_at + 1] == "人事宫位：第 1 宫", lines[head_at: at + 1]
        end = next((i for i in range(at, len(lines)) if not lines[i].strip()), len(lines))
        d, m = _deg_min(used)
        assert any(row.startswith("星盘：") and f"上升 (1th; -){d}°{m:02d}（赤经）" in row for row in lines[head_at:end]), lines[head_at:end]
    assert eq.data["outer"]["ascRaMode"] == "improved" and cls.data["outer"] == {
        "outerCoord": "equatorial", "ascRaMode": "classic", "eastPointAvailable": True}
    assert inert.data["snapshot_text"] == base.data["snapshot_text"]
    assert any("三式合一 ascRaMode=classic 本次不起作用" in note and "outerCoord=equatorial" in note for note in inert.warnings)
    assert list(cls.warnings or []) == []
    assert all("ascRaMode" not in payload and "outerCoord" not in payload for _ep, payload in seen)
    assert "ascRaMode" not in cls.data["liureng"].get("castOptions", {})   # 外圈键不漏进六壬层 options


@requires_node
def test_sanshiunited_rejects_an_unknown_outer_coord(tmp_path) -> None:
    """认不出的 outerCoord 在校验层就拒（词表），不静默按黄道。"""
    from horosa_skill.errors import ToolValidationError

    with pytest.raises(ToolValidationError) as err:
        _replay(tmp_path, "sanshiunited", {"outerCoord": "galactic"})
    assert err.value.code == "tool.invalid_option" and "outerCoord" in str(err.value)


# ───────────────────────────── live（共享 vendored v3.14.0 引擎）─────────────────────────────
_LIVE_BIRTH = {"date": "1990-05-17", "time": "07:30:27", "zone": "+08:00", "lat": "31n14", "lon": "121e28",
               "gpsLat": 31.2333, "gpsLon": 121.4667, "ad": 1, "agent_confirmed_settings": True}


@requires_runtime
@requires_node
@pytest.mark.parametrize("mode", ["improved", "classic"])
def test_live_suzhan_and_guolao_two_tiers(tmp_path, mode: str) -> None:
    """live：宿占（ASC 起盘）与七政（赤仪）新旧两档，数值取自本次后端回包（ra / eastPointLon）：「上升」宿内度 = 所取赤经 − 该宿
    距星赤经；宿占命宫座 = floor(所取赤经 / 30)，七政宫序按命度黄经座（两档同，见上面回放用例）。"""
    service = make_service(tmp_path)
    line = IMPROVED_LINE if mode == "improved" else CLASSIC_LINE
    for tool, extra, title in (("suzhan", {"houseStartMode": 1}, "宿盘宫位与二十八宿星曜"),
                               ("guolao_chart", {"moiraTransitDate": "2026-01-01"}, "七政四余宫位与二十八宿星曜")):
        env = service.run_tool(tool, {**_LIVE_BIRTH, **extra, "ascRaMode": mode}, save_result=False)
        assert env.ok, (tool, env.error)
        asc = _asc_of(env.data["chart"])
        assert asc["eastPointLon"] is not None and abs(asc["eastPointLon"] - asc["ra"]) > 1
        used = asc["ra"] if mode == "improved" else asc["eastPointLon"]
        life_idx = math.floor((used if tool == "suzhan" else asc["lon"]) / 30)
        text = env.data["snapshot_text"]
        assert line in _section(text, "起盘信息").split("\n"), tool
        rows = _section(text, title).split("\n")
        assert any(row.startswith(f"| {_house_label(life_idx, life_idx)} |") for row in rows), (tool, life_idx)
        ref = next(s for s in env.data["chart"]["fixedStarSu28"] if s["name"] == asc["su28"])
        d, m = _deg_min((used - ref["ra"]) % 360)
        assert sum(1 for row in rows if f"上升 {d}˚{asc['su28']}{m}分" in row) == 1, (tool, mode, d, m)
        assert env.data["ascRaMode"] == mode and list(env.warnings or []) == [], (tool, env.warnings)
        exp = env.data["export_snapshot"]
        assert exp["missing_selected_sections"] == [] and exp["unknown_detected_sections"] == [], tool


@requires_runtime
@requires_node
def test_live_jieqi_year_and_sanshiunited_two_tiers(tmp_path) -> None:
    """live：节气盘四张宿盘（ASC 起盘）与三式合一外圈（赤道分宫）新旧两档，逐张按本次回包的 ra / eastPointLon 手算。"""
    service = make_service(tmp_path)
    jq = {"year": 2028, "zone": "+08:00", "lat": "39n54", "lon": "116e24", "gpsLat": 39.9, "gpsLon": 116.4,
          "jieqis": ["春分", "夏至", "秋分", "冬至"], "ad": 1, "agent_confirmed_settings": True, "houseStartMode": 1}
    for mode, line in (("improved", IMPROVED_LINE), ("classic", CLASSIC_LINE)):
        env = service.run_tool("jieqi_year", {**jq, "ascRaMode": mode}, save_result=False)
        assert env.ok, env.error
        for title in jq["jieqis"]:
            chart = env.data["charts"][title]["chart"]
            asc = _asc_of(chart)
            used = asc["ra"] if mode == "improved" else asc["eastPointLon"]
            rows = _section(env.data["snapshot_text"], f"{title}宿盘").split("\n")
            first_sign = math.floor((chart["houses"][0]["lon"] % 360) / 30)
            assert rows[:2] == [line, f"宫位：{_house_label(first_sign, math.floor(used / 30))}"], (mode, title)
        exp = env.data["export_snapshot"]
        assert exp["missing_selected_sections"] == [] and exp["unknown_detected_sections"] == []
        env = service.run_tool("sanshiunited", {**_LIVE_BIRTH, "outerCoord": "equatorial", "ascRaMode": mode}, save_result=False)
        assert env.ok, env.error
        lines = env.data["snapshot_text"].split("\n")
        assert lines.count(line) == 1 and env.data["outer"]["ascRaMode"] == mode
        exp = env.data["export_snapshot"]
        assert exp["missing_selected_sections"] == [] and exp["unknown_detected_sections"] == []
