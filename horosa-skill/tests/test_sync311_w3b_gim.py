"""sync311 wave3b：七政四余 / 印度律盘 / 世俗盘 的上游保真补缺（上游 Horosa-Public 9b74714b = v3.11.1+）。

服务级用例跑**真 JS 引擎**（vendored 上游 builder）+ 录制回放的 HTTP 桩（`fixtures/sync311_w3b_*_live.json`，vendored 实例
chart :8877 / java :9977 实抓）：桩只供后端真值，段文本全部由上游 builder 产出；期望值按上游公式/常量表独立算出，
不抄 builder 输出（整份快照回放 == live 录制的那一条除外——它锁的是「离线回放链与 live 同形」）。
"""

from __future__ import annotations

import copy
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
from test_service import FakeClient

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

FIXTURES = Path(__file__).resolve().parent / "fixtures"
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

GUOLAO_FIX = json.loads((FIXTURES / "sync311_w3b_guolao_live.json").read_text(encoding="utf-8"))


def _service(tmp_path: Path, client) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9",
        chart_server_root="http://127.0.0.1:9",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings))  # 真 JS 引擎


def _section(text: str, title: str) -> str:
    marker = f"[{title}]\n"
    at = text.find(marker)
    if at < 0:
        return ""
    body = text[at + len(marker):]
    nxt = body.find("\n\n[")
    return body if nxt < 0 else body[:nxt]


# ─────────────────────────────── 七政四余 guolao_chart ───────────────────────────────


class GuolaoReplayClient(FakeClient):
    """回放 live 录制：本命 /chart（predictive 假）/ 流年 /chart（predictive 真）/ 两个时刻的 /nongli/time / /qizheng/moira。"""

    def __init__(self, fix: dict, *, chart_patch=None) -> None:
        super().__init__()
        self.fix = fix
        self.chart_patch = chart_patch
        self.calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        endpoint = "/chart" if endpoint == "/" else endpoint
        self.calls.append((endpoint, copy.deepcopy(payload)))
        if endpoint == "/chart":
            if payload.get("predictive") in (True, 1, "1"):
                return copy.deepcopy(self.fix["chart_transit"])
            chart = copy.deepcopy(self.fix["chart_natal"])
            return self.chart_patch(chart) if self.chart_patch else chart
        if endpoint == "/nongli/time":
            natal_date = str(self.fix["payload"]["date"]).replace("/", "-")
            key = "nongli_natal" if str(payload.get("date")).replace("/", "-") == natal_date else "nongli_transit"
            return copy.deepcopy(self.fix[key])
        if endpoint == "/qizheng/moira":
            return copy.deepcopy(self.fix["moira"])
        return super().call(endpoint, payload)

    def requests(self, endpoint: str) -> list[dict]:
        return [p for e, p in self.calls if e == endpoint]


def _guolao_run(tmp_path, extra: dict | None = None, *, chart_patch=None):
    client = GuolaoReplayClient(GUOLAO_FIX, chart_patch=chart_patch)
    payload = {**GUOLAO_FIX["payload"], **(extra or {})}
    env = _service(tmp_path, client).run_tool("guolao_chart", payload, save_result=False)
    return env, client


@requires_node
def test_guolao_offline_replay_reproduces_the_live_snapshot(tmp_path) -> None:
    """离线回放链（录制的后端真值 + 真 JS 引擎）逐字复现 live 快照 —— 夹具裁剪（fixedStars/大运表/nativeRules）不改一字。"""
    env, _ = _guolao_run(tmp_path)
    assert env.ok, env.error
    assert env.data["snapshot_text"] == GUOLAO_FIX["live_snapshot_text"]
    exp = env.data["export_snapshot"]
    assert exp["missing_selected_sections"] == [] and exp["unknown_detected_sections"] == []


# 上游常量（逐值）：SZConst.SignZi / SZConst.SZSigns（宫域两字）/ AstroText.AstroMsgCN（星座名）/ AstroTxtMsg（曜单字）。
_SIGN_ZI_AREA_CN = {"Aries": ("戌", "降娄", "白羊"), "Gemini": ("申", "实沉", "双子")}
_OBJ_CN = {"Mercury": "水", "Mars": "火", "Sun": "日", "Saturn": "土", "Venus": "金", "Uranus": "天", "Moon": "月"}


def _split_degree(deg: float) -> tuple[int, int]:
    """上游 GuoLaoChartMain.splitDegree（:290-300）：宫内度 floor + 分 floor。"""
    d = deg + 360 if deg < 0 else deg
    whole = math.floor(d % 30)
    return whole, math.floor(((d % 30) - whole) * 60)


@requires_node
def test_guolao_house_su_section_is_the_upstream_gfm_table(tmp_path) -> None:
    """[七政四余宫位与二十八宿星曜] = 上游 buildHouseSuAndGodsSection（:1602-1671）GFM 表。

    旧版是 skill 自拟的「宫位：House11 / 星曜：Mercury 壁」行式（英文 id、无宫内度、无地支/宫域、按后端宫 id 不按命宫起数）。
    期望行按上游公式独立算：宫标签 = 地支—宫域—星座座—第N宫（N = 该座相对命度座的序，命度 = 占星上升 Gemini）；
    星 = 曜 d˚宿m分，d/m = (黄经 − 该宿距星度) 的宫内度分（displayCoord=ecliptic → 快照整段按黄经，:2033）。"""
    env, _ = _guolao_run(tmp_path)
    body = _section(env.data["snapshot_text"], "七政四余宫位与二十八宿星曜")
    assert body.startswith("| 宫位 | 二十八宿 | 星曜 |\n| --- | --- | --- |\n"), body[:80]
    chart = GUOLAO_FIX["chart_natal"]["chart"]
    assert chart["displayCoord"] == "ecliptic"
    objs = {o["id"]: o for o in chart["objects"]}
    su_ra = {s["name"]: s["ra"] for s in chart["fixedStarSu28"]}
    asc_idx = int(objs["Asc"]["lon"] // 30)  # Gemini = 2
    zi, area, cn = _SIGN_ZI_AREA_CN["Aries"]
    label = f"{zi}—{area}—{cn}座—第{(0 - asc_idx + 12) % 12 + 1}宫"
    stars = []
    for pid in sorted(("Mercury", "Mars", "Sun"), key=lambda p: objs[p]["ra"]):  # 宫内按赤经升序（:1624-1633）
        assert objs[pid]["su28"] == "壁"
        d, m = _split_degree(objs[pid]["lon"] - su_ra["壁"])
        stars.append(f"{_OBJ_CN[pid]} {d}˚壁{m}分")
    assert f"| {label} | 壁 | {'；'.join(stars)} |" in body.split("\n")
    assert "| 戌—降娄—白羊座—第11宫 | 壁 | 水 0˚壁7分；火 2˚壁53分；日 6˚壁18分 |" in body.split("\n")
    # 空宫一行「无/无」（:1635-1638）。
    assert "| 酉—大梁—金牛座—第12宫 | 无 | 无 |" in body.split("\n")
    assert "宫位：House" not in env.data["snapshot_text"]


@requires_node
def test_guolao_gods_section_comes_from_moira_rules_with_long_life_char(tmp_path) -> None:
    """[神煞] = 上游 buildRulesGodsSection（:1757-1776）：rules.godHits 逐支 + 十二长生字（本命年柱纳音起）。旧版恒「无」。

    申支：年柱 戊申（大驿土）→ 土长生在申（longLifeMapForYear，guolaoMoiraTables.js）→ 首字「长生」，其后 godHits[申] 的
    gods∪good∪neutral∪bad∪taisui 去重原序。"""
    env, _ = _guolao_run(tmp_path)
    body = _section(env.data["snapshot_text"], "神煞")
    rules = GUOLAO_FIX["moira"]
    assert rules["yearStars"]["birth"]["yearPole"] == "戊申"
    hit = next(h for h in rules["godHits"] if h["zi"] == "申")
    names: list[str] = []
    for key in ("gods", "goodGods", "neutralGods", "badGods", "taisuiGods"):
        for name in hit.get(key) or []:
            if name not in names:
                names.append(name)
    assert f"申：{'、'.join(['长生', *names])}" in body.split("\n")
    assert body.split("\n")[0].startswith("子：帝旺、")  # 土长生在申 → 子=帝旺
    assert len(body.split("\n")) == 12


@requires_node
def test_guolao_aspect_section_is_the_upstream_gfm_table_with_cn_names(tmp_path) -> None:
    """[相位] = 上游 buildGuolaoAspectSection（:2158-2179）GFM 五列表；名 = msg()（AstroTxtMsg：Uranus→天）、相位名 =
    GUOLAO_ASPECT_LABEL_CN、误差 = round(orb,3)。旧版是「日 60˚ Uranus（离相，误差9.668）」行式——共享 AstroConst shim 缺
    URANUS 等常量时名表键塌成 "undefined"，同一行也会印 Uranus（负向对照之二）。"""
    env, _ = _guolao_run(tmp_path)
    body = _section(env.data["snapshot_text"], "相位")
    assert body.startswith("| 主体 | 相位 | 对象 | 状态 | 误差 |\n| --- | --- | --- | --- | --- |\n")
    sep = GUOLAO_FIX["chart_natal"]["aspects"]["normalAsp"]["Sun"]["Separative"]
    uranus = next(a for a in sep if a["id"] == "Uranus")
    orb = round(uranus["orb"] * 1000) / 1000
    assert f"| 日 | 六合 (60°) | 天 | 离相 | {orb:g} |" in body.split("\n")
    assert "Uranus" not in body and "Neptune" not in body


@requires_node
def test_guolao_moira_rules_and_patterns_receive_four_pillars(tmp_path) -> None:
    """规则层四柱：上游本命/流年盘都是 Java /chart（chart.nongli 挂 OnlyFourColumns），MoiraPropRuleEngine.readPoles 读
    chartObj.chart.nongli.bazi；缺了只剩公历年干支单柱（[虚实] 只剩年柱、godHits 少月/日/时起的神煞）。旧版两张盘都无 nongli。"""
    env, client = _guolao_run(tmp_path)
    assert env.ok, env.error
    (req,) = client.requests("/qizheng/moira")
    assert req["chartObj"]["chart"]["nongli"]["bazi"]["year"]["branch"]["cell"] == "申"
    assert req["chartObj"]["chart"]["nongli"] == GUOLAO_FIX["nongli_natal"]
    assert req["transitChartObj"]["chart"]["nongli"] == GUOLAO_FIX["nongli_transit"]
    dates = [str(p["date"]).replace("/", "-") for p in client.requests("/nongli/time")]
    assert dates == ["2028-04-06", "2026-09-04"]
    # 政余格局的神煞行同吃本命四柱（buildGodRowsFromChart 读 chart.nongli.bazi.guolaoGods）：命度临岁驾（申）。
    zi_gods = GUOLAO_FIX["nongli_natal"]["bazi"]["guolaoGods"]["ziGods"]
    assert "岁驾" in (zi_gods["申"].get("taisuiGods") or [])
    assert "命登岁驾" in _section(env.data["snapshot_text"], "政余格局")


@requires_node
def test_guolao_setup_date_line_uses_upstream_slash_format(tmp_path) -> None:
    """[起盘信息] 日期行 = `日期：${params.date} ${params.time}`，params.date = format('YYYY/MM/DD')（:2337/:2043）。"""
    env, _ = _guolao_run(tmp_path)
    assert _section(env.data["snapshot_text"], "起盘信息").split("\n")[0] == "日期：2028/04/06 09:33:00"


_JD_1990_01_15_1200_CST = 2447906.5 + 4 / 24  # 1990-01-15 12:00 +08:00 = 04:00 UT（1990-01-15 0h UT = JD 2447906.5）


def _as_1990_01_15(chart: dict) -> dict:
    chart["chart"]["date"] = {"date": {"jdn": 2447907}, "time": {"value": 12.0}, "utcoffset": {"value": 8.0}, "jd": _JD_1990_01_15_1200_CST}
    return chart


def _first_limit_row(text: str) -> str:
    return next(line for line in _section(text, "大限").split("\n") if line.startswith("| 第1限 |"))


@requires_node
def test_guolao_limit_year_boundary_knob_reaches_the_limit_table(tmp_path) -> None:
    """大限年界（上游显示偏好 limitYearBoundary，GuoLaoInput.js:850；无头读同一份偏好 :2058）改 [大限] 的年内起点：
    buildGuolaoLimitTable 起算 age = 1 + birthFrac（:219-236），birthYear = 公历年 + yearShift。
    1990-01-15 12:00 +08:00：公历元旦界 frac = 14.5 日/365.25 ≈ 0.04、yearShift 0；立春界（1990 立春在 02-04，生于其前）→
    上一年立春起算 frac ≈ 0.94、yearShift −1（立春前生人岁次属上一年）。首限年数 = 9 + 命度宫内度/3（命度 = 上升 双子
    25°11′ → 17.395 年）→ 元旦界 1+0.04 → 1..round(18.43)−1 = 1–17 岁；立春界 1+0.94 → round(1.94)=2..round(19.34)−1 = 2–18 岁，
    起讫年 (1989+2−1)–(1989+18−1) 仍是 1990–2006 年。旧版显示层写死 gregorian，键被 FlexibleModel 吞掉 → 两次同为 1–17 岁。"""
    base = {"date": "1990-01-15", "time": "12:00:00", "moiraRules": False}
    greg, _ = _guolao_run(tmp_path / "g", base, chart_patch=_as_1990_01_15)
    lichun, _ = _guolao_run(tmp_path / "l", {**base, "guolaoLimitYearBoundary": "lichun"}, chart_patch=_as_1990_01_15)
    assert greg.ok and lichun.ok, (greg.error, lichun.error)
    asc = next(o for o in GUOLAO_FIX["chart_natal"]["chart"]["objects"] if o["id"] == "Asc")
    span = 9 + (asc["lon"] % 30) / 3
    assert round(span, 1) == 17.4
    assert _first_limit_row(greg.data["snapshot_text"]) == "| 第1限 | 命宫 | 1-17岁 | 1990-2006年 | 约17.4年 |"
    assert _first_limit_row(lichun.data["snapshot_text"]) == "| 第1限 | 命宫 | 2-18岁 | 1990-2006年 | 约17.4年 |"
    bad, _ = _guolao_run(tmp_path / "b", {**base, "guolaoLimitYearBoundary": "spring"})
    assert not bad.ok and bad.error.code == "tool.guolao_invalid_display_setting"
    assert bad.error.details["allowed"] == ["gregorian", "lichun", "dongzhi"]


@requires_node
def test_guolao_non_asc_life_mode_without_life_master_point_is_warned(tmp_path) -> None:
    """命度法非上升时上游命度 = Java BaZi 的 LifeMasterDeg74；Python 排盘服务无此点 → 同回退序落回上升，必须告警（旧版静默）。"""
    env, _ = _guolao_run(tmp_path, {"guolaoLifeMode": "yumao"})
    assert env.ok, env.error
    assert any("七政命度「日出安命」" in w and "LifeMasterDeg74" in w for w in env.warnings), env.warnings
    asc, _ = _guolao_run(tmp_path / "asc")
    assert not any("LifeMasterDeg74" in w for w in asc.warnings)


@requires_node
def test_guolao_star_dignity_keeps_the_outer_planet_rows(tmp_path) -> None:
    """[星曜庙旺与星点动态] = 上游 buildStarDignityMotionSection（:1788-1850）：STAR_POINTS 含 天/海/冥（AstroConst.URANUS/
    NEPTUNE/PLUTO）。共享 shim `src/constants/AstroConst.js` 此前不导出这三个常量 → `o.id === undefined` 恒假 → 三行被
    静默丢掉（旧版该段 13 行，上游 16 行）。地支按上游 ziOf：黄经所在宫序 s → ['子'…'亥'][(10 − s + 12) % 12]（黄仪取 lon）。"""
    env, _ = _guolao_run(tmp_path)
    body = _section(env.data["snapshot_text"], "星曜庙旺与星点动态（殿垣庙旺乐喜怒 · 顺逆留伏迟速）")
    objs = {o["id"]: o for o in GUOLAO_FIX["chart_natal"]["chart"]["objects"]}
    zlist = "子丑寅卯辰巳午未申酉戌亥"
    rows = body.split("\n")
    for name, pid in (("天", "Uranus"), ("海", "Neptune"), ("冥", "Pluto")):
        s = int((objs[pid]["lon"] % 360) // 30)
        assert any(r.startswith(f"| {name} | {zlist[(10 - s + 12) % 12]} |") for r in rows), (name, rows)
    assert len(rows) == 2 + 14 + 2  # 表头两行 + 七政四余 11 + 天海冥 3 + 升/顶


def test_shared_astroconst_shim_defines_every_id_its_consumers_reference() -> None:
    """AGENTS §5 闭包提取陷阱③：名表/星点表以 AstroConst.* 为键时 shim 必须补齐——缺一个就是 `undefined` 键，查不到、
    不报错。凡 import 共享 shim（src/constants/AstroConst.js）的模块，引用到的 AstroConst.X 必须都由 shim 导出。
    修前：tools/guolaoStarDignity.js 缺 URANUS/NEPTUNE/PLUTO、vendor/utils/astroClassicalDerived.js 缺 PARS_SPIRIT。"""
    root = Path(__file__).resolve().parents[1] / "horosa-core-js"
    shim_path = (root / "src" / "constants" / "AstroConst.js").resolve()
    defined = set(re.findall(r"export (?:const|function|let) ([A-Za-z_0-9]+)", shim_path.read_text(encoding="utf-8")))
    missing: dict[str, list[str]] = {}
    for path in sorted((root / "src").rglob("*.js")):
        text = path.read_text(encoding="utf-8")
        m = re.search(r"from '((?:\.\./)+)constants/AstroConst\.js'", text)
        if not m:
            continue
        if (path.parent / ("../" * m.group(1).count("../")) / "constants" / "AstroConst.js").resolve() != shim_path:
            continue
        gaps = sorted(set(re.findall(r"AstroConst\.([A-Z_0-9]+)\b", text)) - defined)
        if gaps:
            missing[path.relative_to(root).as_posix()] = gaps
    assert not missing, missing


@requires_node
def test_eminence_four_points_row_counts_pars_spirit(tmp_path) -> None:
    """同一 shim 缺口的另一处消费方：[古典·显赫计分]（vendor/utils/astroClassicalDerived.js computeEminence）「四显赫点」=
    福点/精神点/根基点/擢升点。shim 缺 PARS_SPIRIT → 精神点 id 为 undefined → lotObj 恒查不到 → 该点整个不参与计分
    （上游 AstroConst.PARS_SPIRIT = 'Pars Spirit'）。用 live 夹具里的真 lots 验：精神点按其落宫出现在「满足要素」里。"""
    from horosa_skill.engine.js_client import HorosaJsEngineClient

    settings = Settings(runtime_root=tmp_path / "runtime", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    chart = copy.deepcopy(GUOLAO_FIX["chart_natal"])
    js = HorosaJsEngineClient(settings).run("classical_derived", {"chart": chart, "lat": "31n13"})
    text = js.get("snapshot_text") or ""
    row = next(line for line in text.split("\n") if line.startswith("| 四显赫点 |"))
    spirit = next(lot for lot in chart["lots"] if lot["id"] == "Pars Spirit")
    house = int(re.sub(r"\D", "", spirit["house"]))
    assert f"精神点{house}宫" in row, row


UPSTREAM_ASTROCONST = Path("/Users/horacedong/Desktop/Horosa-Public/Horosa-Web/astrostudyui/src/constants/AstroConst.js")


@pytest.mark.skipif(not UPSTREAM_ASTROCONST.is_file(), reason="needs the upstream Horosa-Public checkout")
def test_shared_astroconst_shim_string_ids_equal_upstream_values() -> None:
    """shim 里每个字符串常量都必须逐值等于上游 constants/AstroConst.js 同名常量（猜值会静默对不上排盘 objects[].id）。"""
    shim = (Path(__file__).resolve().parents[1] / "horosa-core-js" / "src" / "constants" / "AstroConst.js").read_text(encoding="utf-8")
    upstream = UPSTREAM_ASTROCONST.read_text(encoding="utf-8")
    pat = re.compile(r"^export const ([A-Z_0-9]+)\s*=\s*'([^']*)'", re.M)
    up = dict(pat.findall(upstream))
    mine = dict(pat.findall(shim))
    assert {"URANUS", "NEPTUNE", "PLUTO", "CHIRON", "PARS_SPIRIT"} <= set(mine)
    assert {k: v for k, v in mine.items() if up.get(k) != v} == {}


def _with_life_master_in_leo(chart: dict) -> dict:
    objs = chart["chart"]["objects"]
    asc = next(o for o in objs if o["id"] == "Asc")
    life = {**asc, "id": "LifeMasterDeg74", "lon": asc["lon"] + 60.0, "ra": asc["ra"] + 60.0, "sign": "Leo"}
    objs.append(life)
    return chart


@requires_node
def test_guolao_gumao_life_mode_counts_houses_from_the_life_master_point(tmp_path) -> None:
    """命度法 gumao（遇卯安命）/ 地支（自定命宫）：上游 GuoLaoChartStyle.normalizeGuolaoLifeMode 认这两类（v3.11 R2），
    lifeDegree 因此取命度点 LifeMasterDeg74 起第 1 宫（GuoLaoMoiraWheel.lifeDegree）。vendored guolaoMoira.js 此前是只认
    yumao/cotrans 的旧平移件 → gumao 归一成 asc → 宫序按上升（Gemini 为第 1 宫）。盘里放一个落狮子的命度点来区分。"""
    env, _ = _guolao_run(tmp_path, {"guolaoLifeMode": "gumao", "moiraRules": False}, chart_patch=_with_life_master_in_leo)
    assert env.ok, env.error
    rows = _section(env.data["snapshot_text"], "七政四余宫位与二十八宿星曜").split("\n")
    assert any(r.startswith("| 午—鹑火—狮子座—第1宫 |") for r in rows), rows[:6]
    assert any(r.startswith("| 申—实沉—双子座—第11宫 |") for r in rows)
    assert not any("LifeMasterDeg74" in w for w in env.warnings)  # 盘里有命度点 → 不告警


# ─────────────────────────────── 印度律盘 india_chart ───────────────────────────────

INDIA_FIX = json.loads((FIXTURES / "sync311_w3b_india_live.json").read_text(encoding="utf-8"))


class IndiaReplayClient(FakeClient):
    def __init__(self, chart: dict) -> None:
        super().__init__()
        self.chart = chart
        self.calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, copy.deepcopy(payload)))
        if endpoint == "/india/chart":
            return copy.deepcopy(self.chart)
        return super().call(endpoint, payload)


def _india_run(tmp_path, *, chart: dict | None = None, extra: dict | None = None):
    client = IndiaReplayClient(chart or INDIA_FIX["india_chart"])
    env = _service(tmp_path, client).run_tool("india_chart", {**INDIA_FIX["payload"], **(extra or {})}, save_result=False)
    return env, client


def _titles(text: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"^\[(.+)\]$", text, re.M)]


@requires_node
def test_india_setup_section_carries_the_upstream_calibre_line(tmp_path) -> None:
    """[起盘信息] = 流派头行 + 本命起盘行，首条黄道行换成 indiaCalibreLine（IndiaChart.js:1113-1130）：
    `${zodiacalDisplayText(1, ayan)}，${INDIA_HOUSE_SYSTEM_OPTIONS[hsys].label}`。indiaSchool=kp → 预设 krishnamurti / hsys 3
    （INDIA_SCHOOL_DEFAULTS），后端回显同值 → 「恒星黄道·Krishnamurti / KP，KP / Placidus」（岁差表 label 'Krishnamurti / KP'、
    分宫制表 3 → 'KP / Placidus'）。旧版只有本命行「恒星黄道，KP / Placidus」（无岁差名）。"""
    env, _ = _india_run(tmp_path)
    assert env.ok, env.error
    assert INDIA_FIX["india_chart"]["params"]["hsys"] == 3 and INDIA_FIX["india_chart"]["params"]["ayanamsa"] == "krishnamurti"
    setup = _section(env.data["snapshot_text"], "起盘信息").split("\n")
    assert setup[0].startswith("流派：KP 系统（")
    assert "恒星黄道·Krishnamurti / KP，KP / Placidus" in setup
    assert "恒星黄道，KP / Placidus" not in setup  # 首条黄道行已被口径行替换（replaceIndiaCalibreLine 只换第一条）
    # [信息] 段是本命 buildInfoSection 原样（上游不替换那里）。
    assert "恒星黄道，KP / Placidus" in _section(env.data["snapshot_text"], "信息").split("\n")


@requires_node
def test_india_section_composition_mirrors_build_india_snapshot_text(tmp_path) -> None:
    """段组成 = 上游 buildIndiaSnapshotText（:1131-1194）：[星盘信息] = 本命 [宫位宫头]+[星与虚点]+[信息] 三段正文拼接、
    不单列 [宫位宫头]/[星与虚点]、不挑 [月宿]/[古典]；[信息]/[相位]/[行星]/[希腊点]/[可能性] 恒出（ensureSection 空段写
    「无数据」）。旧版照本命盘出 [宫位宫头]/[星与虚点]/[月宿]/[古典]，[星盘信息] 缺席（由导出层拿通用起盘行兜底）。"""
    from horosa_skill.service import (
        _build_house_cusp_lines,
        _build_info_section,
        _build_star_and_lot_position_lines,
    )

    env, _ = _india_run(tmp_path)
    text = env.data["snapshot_text"]
    titles = _titles(text)
    assert titles[:7] == ["起盘信息", "星盘信息", "信息", "相位", "行星", "希腊点", "可能性"], titles[:8]
    assert not {"宫位宫头", "星与虚点", "月宿", "古典"} & set(titles)
    chart = INDIA_FIX["india_chart"]
    norm = env.input_normalized
    expected = [
        line.rstrip()
        for block in (_build_house_cusp_lines(chart), _build_star_and_lot_position_lines(chart), _build_info_section(chart, norm))
        for line in "\n".join(f"{x}" for x in block).split("\n")
        if line.strip()
    ]
    assert _section(text, "星盘信息").split("\n") == expected
    assert _section(text, "可能性") == "无数据"
    exp = env.data["export_snapshot"]
    # 夹具的 jyotish 只留 panchanga → Jyotish 派生段缺席是夹具裁剪所致；段组成七段一段不缺、无未登记段。
    assert not {"起盘信息", "星盘信息", "信息", "相位", "行星", "希腊点", "可能性"} & set(exp["missing_selected_sections"])
    assert exp["unknown_detected_sections"] == []


@requires_node
def test_india_calibre_line_mismatch_with_backend_is_warned(tmp_path) -> None:
    """口径行的岁差/分宫制经上游 normalize*（认不出 → Lahiri / 整宫）；后端实算值不在上游表内时两者会静默分叉 → 必须告警。"""
    chart = copy.deepcopy(INDIA_FIX["india_chart"])
    chart["params"]["ayanamsa"] = "user"  # 后端自定义历元档；上游印占岁差表无 'user'
    env, _ = _india_run(tmp_path, chart=chart)
    assert env.ok, env.error
    assert "恒星黄道·Lahiri / Chitrapaksha，KP / Placidus" in _section(env.data["snapshot_text"], "起盘信息").split("\n")
    assert any("口径行按上游词表归一" in w and "岁差 user" in w for w in env.warnings), env.warnings
    clean, _ = _india_run(tmp_path / "clean")
    assert not any("口径行" in w for w in clean.warnings)


def _js_to_fixed(value: Any, digits: int) -> str:
    """JS Number.prototype.toFixed：规范 21.1.3.3 先取 -x，再对**二进制精确值**取最近的 n/10^f（平局取大 = 绝对值 HALF_UP），再补符号。
    必须 Decimal(float) 精确转换而非 Decimal(repr(x))：0.85 的双精度是 0.8499999…，JS 给 "0.8"，按十进制字面量会得 "0.9"。"""
    from decimal import ROUND_HALF_UP, Decimal

    number = float(value)
    quant = Decimal(1).scaleb(-digits)
    text = f"{Decimal(abs(number)).quantize(quant, rounding=ROUND_HALF_UP):f}"
    return f"-{text}" if number < 0 else text


@requires_node
def test_india_dasha_section_lists_every_antardasha_row(tmp_path) -> None:
    """[大运Dasha] = 上游 buildDashaSnapshotLines（IndiaChart.js:429-494）+ buildAntardashaTableLines（:395-428，[#80] 小运全展）。
    期望整段按上游公式从夹具 jyotish.dasha.vimshottari 独立算出：nameOf = lord.label||lord.key；fmtDate = 前 10 位；
    n1(x).toFixed(1)；大运行标记 ▶=active、·=birthBalance；小运行标记 ▶=当下（Date.now() 落在 [start,end)）、·=当前大运内；
    9 大运×9 小运 = 90 行 < DASHA_ANTAR_ROW_MAX 120 → 无截断行。负向对照：把 vendored builder 里 `out.push(...buildAntardashaTableLines(`
    一行去掉（旧版「只挑当下一支」形态）→ 小运序列整片消失，本用例红。"""
    from datetime import datetime, timezone

    vim = INDIA_FIX["india_chart"]["jyotish"]["dasha"]["vimshottari"]
    env, _ = _india_run(tmp_path)
    assert env.ok, env.error
    name_of = lambda lord: (lord or {}).get("label") or (lord or {}).get("key") or "—"  # noqa: E731
    fmt_date = lambda d: (re.match(r"^(\d{4}-\d{2}-\d{2})", f"{d or ''}") or [None, f"{d or ''}" or "—"])[1]  # noqa: E731
    n1 = lambda x: float(x) if isinstance(x, (int, float)) and math.isfinite(float(x)) else 0.0  # noqa: E731
    now = datetime.now(timezone.utc)
    ts = lambda s: datetime.strptime(f"{s}"[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)  # noqa: E731（JS new Date('YYYY-MM-DD') = UTC 零点）
    nak = vim.get("moonNakshatra") or {}
    expected = [
        "系统：Vimshottari（120 年周期）",
        f"月宿：{nak.get('label') or nak.get('name') or nak.get('key') or '—'}（宿主星 {name_of(vim.get('firstLord'))}）",
        f"首运：已历 {_js_to_fixed(n1(vim.get('firstElapsedYears')), 1)} 年、余 {_js_to_fixed(n1(vim.get('firstBalanceYears')), 1)} 年",
    ]
    active = next((m for m in vim["mahadashas"] if m.get("active")), None)
    assert active is not None  # 夹具：首运 birthBalance 且 active
    expected.append(
        f"当前大运（Mahadasha）：{name_of(active['lord'])}（{fmt_date(active['start'])} → {fmt_date(active['end'])}，"
        f"{_js_to_fixed(n1(active.get('startAge')), 0)}–{_js_to_fixed(n1(active.get('endAge')), 0)} 岁）"
    )
    sub = next((s for s in active.get("antardashas") or [] if s.get("start") and s.get("end") and ts(s["start"]) <= now < ts(s["end"])), None)
    if sub:
        expected.append(f"当前小运（Antardasha）：{name_of(sub['lord'])}（{fmt_date(sub['start'])} → {fmt_date(sub['end'])}）")
    expected += ["大运序列：", "| 标记 | 主星 | 起 | 止 | 年数 | 年龄段 |", "| --- | --- | --- | --- | --- | --- |"]
    for m in vim["mahadashas"]:
        mark = "▶" if m.get("active") else ("·" if m.get("birthBalance") else "")
        expected.append(
            f"| {mark} | {name_of(m['lord'])} | {fmt_date(m['start'])} | {fmt_date(m['end'])} | {_js_to_fixed(n1(m.get('years')), 1)} 年 | "
            f"{_js_to_fixed(n1(m.get('startAge')), 0)}–{_js_to_fixed(n1(m.get('endAge')), 0)} 岁 |"
        )
    antar_rows = []
    for m in vim["mahadashas"]:
        for a in m.get("antardashas") or []:
            live = bool(a.get("start") and a.get("end")) and ts(a["start"]) <= now < ts(a["end"])
            antar_rows.append(
                f"| {'▶' if live else ('·' if m.get('active') else '')} | {name_of(m['lord'])} | {name_of(a['lord'])} | "
                f"{fmt_date(a['start'])} | {fmt_date(a['end'])} | {_js_to_fixed(n1(a.get('years')), 1)} 年 |"
            )
    assert len(antar_rows) == 90
    expected += ["小运序列(Antardasha,全大运展开;▶=当下、·=当前大运内):", "| 标记 | 大运主星 | 小运主星 | 起 | 止 | 年数 |", "| --- | --- | --- | --- | --- | --- |", *antar_rows]
    got = _section(env.data["snapshot_text"], "大运Dasha").split("\n")
    assert got == expected
    assert not any("已截断" in line for line in got)
    assert sum(1 for line in got if line.startswith("| ▶ |")) == 2  # 当前大运一行 + 当下小运一行（夹具日期跨 2025–2152，当下恒落在表内）
