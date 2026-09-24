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
