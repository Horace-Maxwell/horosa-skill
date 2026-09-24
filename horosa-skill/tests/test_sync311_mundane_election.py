"""上游 v3.11 两处导出增量：世俗盘 25 张右栏卡 + 择日 [回归与主限]。

- 世俗盘（aiExport.js:621-623 [Q-444/T-407]）：产段函数 `buildMundaneCardSections`（MundaneMain.js:232）逐字
  vendored 进 `vendor/mundane/MundaneMain.js`，Python 取页面按需物料后经 `tools/mundaneCards.js` 喂入。
- 择日（aiExport.js:590 [Q-445]）：`electionSnapshot` 只在 extra 有料时出 [回归与主限]；日/月返求根
  （returnCharts.solveReturnBefore）与主限命中（fetchPdHitsNearElection）的 HTTP 编排移植到 Python。

这里的服务级用例跑**真 JS 引擎**（vendored builder）+ 脚本化的 HTTP 桩：桩只供星历/端点形状，段文本全部由
上游 builder 产出，期望值带权威出处（上游源行号 / 回归定义 / 窗口规则），不抄 builder 输出。
"""

from __future__ import annotations

import copy
import math
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from test_service import FakeClient

from horosa_skill.config import Settings
from horosa_skill.exports.registry import AI_EXPORT_OPTIONAL_SECTIONS, AI_EXPORT_PRESET_SECTIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

PKG_ROOT = Path(__file__).resolve().parents[1]
VENDOR = PKG_ROOT / "horosa-core-js" / "src" / "vendor"
UPSTREAM_ROOT = Path(os.environ.get("HOROSA_SOURCE_ROOT") or "/Users/horacedong/Desktop/Horosa-Public")
UPSTREAM_AIEXPORT = UPSTREAM_ROOT / "Horosa-Web/astrostudyui/src/utils/aiExport.js"

# ── 脚本化星历：日/月黄经 = 平均速率 + 周期摄动（lonspeed 为其导数），让牛顿迭代真的要走几步。 ──
_EPOCH = datetime(2000, 1, 1, 12, 0, 0)
_SUN = {"lon0": 280.0, "rate": 360 / 365.25, "amp": 1.9, "period": 365.25}
_MOON = {"lon0": 218.0, "rate": 360 / 27.321661, "amp": 6.3, "period": 27.5546}
_VEDIC_ZERO = datetime(2025, 4, 14, 6, 0, 0)  # 吠陀用例：恒星太阳在此刻恰为 0°


def _days(moment: datetime) -> float:
    return (moment - _EPOCH).total_seconds() / 86400


def _body(spec: dict, moment: datetime) -> tuple[float, float]:
    d = _days(moment)
    w = 2 * math.pi / spec["period"]
    lon = (spec["lon0"] + spec["rate"] * d + spec["amp"] * math.sin(w * d)) % 360
    speed = spec["rate"] + spec["amp"] * w * math.cos(w * d)
    return lon, speed


def _parse_moment(payload: dict) -> datetime:
    date = str(payload.get("date") or "2000-01-01").replace("/", "-")
    time = str(payload.get("time") or "12:00:00")
    if len(time) == 5:
        time += ":00"
    return datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M:%S")


def _short_delta(target: float, cur: float) -> float:
    return ((target - cur + 540) % 360) - 180


class ScriptedClient(FakeClient):
    """FakeClient 的盘面形状 + 按请求时刻算出的日/月黄经，外加世运/择日所需端点的真实形状。"""

    def __init__(self, *, pd_rows: list | None = None, eclipses: list | None = None, vedic: bool = False) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []
        self.pd_rows = pd_rows or []
        self.eclipses = eclipses or []
        self.vedic = vedic

    def _chart(self, payload: dict) -> dict:
        base = copy.deepcopy(super().call("/chart", payload))
        moment = _parse_moment(payload)
        if self.vedic:
            sun_lon, sun_speed = (0.98565 * ((moment - _VEDIC_ZERO).total_seconds() / 86400)) % 360, 0.98565
        else:
            sun_lon, sun_speed = _body(_SUN, moment)
        moon_lon, moon_speed = _body(_MOON, moment)
        for obj in base["chart"]["objects"]:
            if obj["id"] == "Sun":
                obj.update(lon=sun_lon, lonspeed=sun_speed, signlon=sun_lon % 30)
            elif obj["id"] == "Moon":
                obj.update(lon=moon_lon, lonspeed=moon_speed, signlon=moon_lon % 30)
        # 四轴对象（buildFacts 的 meta.ascLon/mcLon 与 [四轴特殊点] 要它们）：与桩宫头一致（House1=150°、House10=60°）。
        base["chart"]["objects"] += [
            {"id": "Asc", "house": "House1", "sign": "Virgo", "signlon": 0.0, "lon": 150.0},
            {"id": "MC", "house": "House10", "sign": "Gemini", "signlon": 0.0, "lon": 60.0},
        ]
        if payload.get("includePrimaryDirection"):
            base["predictives"] = {**(base.get("predictives") or {}), "primaryDirection": copy.deepcopy(self.pd_rows)}
        return base

    def call(self, endpoint: str, payload: dict) -> dict:
        # chart 服务上 /chart 的真实路由是 "/"（service._chart_server_endpoint），记账时归一回 /chart。
        endpoint = "/chart" if endpoint == "/" else endpoint
        self.calls.append((endpoint, copy.deepcopy(payload)))
        if endpoint == "/chart":
            return self._chart(payload)
        if endpoint == "/jieqi/year":
            return {"year": payload["year"], "jieqi24": [
                {"jieqi": "春分", "time": "2025-03-20 17:01:41"},
                {"jieqi": "夏至", "time": "2025-06-21 10:42:00"},
                {"jieqi": "秋分", "time": "2025-09-23 02:19:12"},
                {"jieqi": "冬至", "time": "2025-12-21 23:03:00"},
            ]}
        if endpoint == "/astroextra/analysis":
            return {"patterns": [
                {"type": "grand_trine", "label": "Grand Trine", "points": ["Sun", "Jupiter", "Mars"]},
                {"type": "t_square", "label": "T-Square", "apex": "Saturn", "points": ["Saturn", "Moon", "Venus"]},
            ]}
        if endpoint == "/astroextra/prenatal_syzygy":
            # 自入宫时刻回溯先遇满月，再自其前一日回溯得新月（与 skill 子盘群的两次调用同序）。
            if str(payload.get("date")).startswith("2025-03-20"):
                return {"type": "full", "date": "2025-03-14", "time": "14:54:44", "datetime": "2025-03-14 14:54:44", "sunLon": 353.99, "moonLon": 173.99}
            return {"type": "new", "date": "2025-02-28", "time": "08:44:39", "datetime": "2025-02-28 08:44:39", "sunLon": 340.0, "moonLon": 340.0}
        if endpoint == "/astroextra/ephemeris":
            return {"eclipses": copy.deepcopy(self.eclipses), "lunarPhases": []}
        if endpoint == "/astroextra/eclipsedetail":
            solar = payload.get("eclipseKind") != "lunar"
            return {"kind": payload.get("eclipseKind"), "durationHours": 3.88 if solar else 3.49,
                    "influence": 3.9 if solar else 3.5, "influenceUnit": "年" if solar else "月"}
        if endpoint == "/astroextra/greatconj":
            return {"conjunctions": [
                {"year": 1961, "month": 2, "day": 18, "hour": 23.1, "lon": 295.4, "sign": 9},
                {"year": 1980, "month": 12, "day": 31, "hour": 21.3, "lon": 189.2, "sign": 6},
                {"year": 2020, "month": 12, "day": 21, "hour": 18.3, "lon": 300.5, "sign": 10},
            ]}
        if endpoint == "/astroextra/barbault":
            return {"planets": payload.get("planets"), "points": [
                {"year": 1900, "month": 1, "index": 1069.78},
                {"year": 1983, "month": 1, "index": 300.4},
                {"year": 2012, "month": 7, "index": 1333.6},
            ], "extrema": [], "maxIndex": 1800}
        return super().call(endpoint, payload)

    def requests(self, endpoint: str) -> list[dict]:
        return [p for e, p in self.calls if e == endpoint]


def _service(tmp_path, client) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9",
        chart_server_root="http://127.0.0.1:9",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings))  # 真 JS 引擎


_HEADER = re.compile(r"^\[(.+)\]$")  # 同上游 aiExport.parseSectionTitleLine（:1140）的判段口径


def _section(text: str, title: str) -> list[str]:
    """段体行：自 `[title]` 起，到下一个段头或空行为止（世俗盘段间空行、择日快照段间无空行，两种都认）。"""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line == f"[{title}]":
            body: list[str] = []
            for nxt in lines[i + 1:]:
                if not nxt.strip() or _HEADER.match(nxt.strip()):
                    break
                body.append(nxt)
            return body
    raise AssertionError(f"section [{title}] missing")


def _clean(env) -> None:
    exp = env.data["export_snapshot"]
    assert exp["missing_selected_sections"] == [] and exp["unknown_detected_sections"] == [], exp
    # 同名段只许出现一次：盘型轮只留专属卡，本命式卡（四轴特殊点/盘型格局…）只取入宫底盘那一轮——
    # 否则同一段名在快照里出现两次、且第二份算的是另一张盘（解析器按段名去重，missing/unknown 看不出来）。
    headers = [line for line in env.data["snapshot_text"].split("\n") if _HEADER.match(line.strip())]
    dupes = sorted({h for h in headers if headers.count(h) > 1})
    assert not dupes, dupes


MUNDANE = {"year": 2025, "ingressTerm": "春分", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gpsLat": 31.2167, "gpsLon": 121.4667, "hsys": 0}

# ────────────────────────────── 契约锚点（无网络、无 node） ──────────────────────────────


def test_mundane_type_cards_are_registered_in_preset_and_optional() -> None:
    preset = set(AI_EXPORT_PRESET_SECTIONS["mundane"])
    optional = set(AI_EXPORT_OPTIONAL_SECTIONS["mundane"])
    for mtype, titles in HorosaSkillService._MUNDANE_TYPE_CARDS.items():
        for title in titles:
            assert title in preset, (mtype, title)
            assert title in optional, (mtype, title)  # 盘型专属卡 = 条件段 → 双登记
    assert "回归与主限" in AI_EXPORT_PRESET_SECTIONS["election"] and "回归与主限" in AI_EXPORT_OPTIONAL_SECTIONS["election"]


@pytest.mark.skipif(not UPSTREAM_AIEXPORT.is_file(), reason="needs the upstream Horosa-Public checkout")
def test_mundane_and_election_presets_mirror_upstream_order() -> None:
    import sys

    sys.path.insert(0, str(PKG_ROOT / "scripts"))
    from _upstream_preset import load_upstream_aiexport

    _version, upstream = load_upstream_aiexport(UPSTREAM_AIEXPORT)
    assert AI_EXPORT_PRESET_SECTIONS["mundane"] == upstream["mundane"]
    assert AI_EXPORT_PRESET_SECTIONS["election"] == upstream["election"]


def test_cycle_defaults_are_anchored_to_the_vendored_builder() -> None:
    # 页面缺省（MundaneMain.js:554/:557）Python 端手持用于发请求；vendored builder 的显示回落必须同值。
    text = (VENDOR / "mundane" / "MundaneMain.js").read_text(encoding="utf-8")
    gc, bb = HorosaSkillService._MUNDANE_GC_DEFAULT_STATE, HorosaSkillService._MUNDANE_BB_DEFAULT_STATE
    assert f"clampYear(st.gcStart, {gc['gcStart']})" in text and f"clampYear(st.gcEnd, {gc['gcEnd']})" in text
    assert f"clampYear(st.bbStart, {bb['bbStart']})" in text and f"clampYear(st.bbEnd, {bb['bbEnd']})" in text
    m = re.search(r"const BARBAULT_SETS = \[\s*\{ key: '(\w+)'[^}]*planets: \[([^\]]*)\]", text)
    assert m, "BARBAULT_SETS[0] not found in the vendored builder"
    assert m.group(1) == bb["bbSet"]
    assert tuple(re.findall(r"'(\w+)'", m.group(2))) == HorosaSkillService._MUNDANE_BB_DEFAULT_PLANETS
    assert f"(CYCLE_PAIRS.find((pp) => pp.key === st.gcPair)" in text and "{ key: 'jupiter-saturn'" in text


def test_return_cycle_constants_are_anchored_to_vendored_timelords() -> None:
    text = (VENDOR / "divination" / "engine" / "timeLords.js").read_text(encoding="utf-8")
    solar = float(re.search(r"export const SOLAR_RETURN_DAYS = ([\d.]+);", text).group(1))
    lunar = float(re.search(r"export const LUNAR_RETURN_DAYS = ([\d.]+);", text).group(1))
    assert (HorosaSkillService._SOLAR_RETURN_DAYS, HorosaSkillService._LUNAR_RETURN_DAYS) == (solar, lunar)


# ────────────────────────────── 世俗盘：真 JS builder ──────────────────────────────


def test_mundane_ingress_cards_come_from_the_vendored_builder_with_python_fetched_state(tmp_path) -> None:
    client = ScriptedClient()
    env = _service(tmp_path, client).run_tool("mundane", dict(MUNDANE), save_result=False)
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    # [年盘概要]（MundaneMain.js:246-258）：入宫时刻 = /jieqi/year 的春分；上升 House1=150° 处女 → 宫主水星；
    # 处女为变动座；modern 规则集 ingressRule=aries_annual → 主管 12 个月。
    assert _section(text, "年盘概要")[:3] == [
        "2025 年 · 春分 · 白羊入宫 · 入宫时刻 2025-03-20 17:01:41",
        "上升 处女 → 年主星(命主) 水星",
        "本盘上升 变动星座 · 现代(Carter–Campion) → 主管约 12 个月",
    ]
    # [四季入境盘]（:259-266）：state.seasonSeed = skill 已为 [地区盘推运] 取的四枢轴时刻，截到分；春分为当前。
    assert _section(text, "四季入境盘") == [
        "2025 年四枢轴入境时刻（当地时区）：",
        "- 春分·白羊：2025-03-20 17:01（当前）",
        "- 夏至·巨蟹：2025-06-21 10:42",
        "- 秋分·天秤：2025-09-23 02:19",
        "- 冬至·摩羯：2025-12-21 23:03",
    ]
    # [盘型格局] 相位格局行（:387-395）：patData = /astroextra/analysis 的 patterns，世运义取上游 PATTERN_MUNDANE。
    pattern = _section(text, "盘型格局")
    assert "相位格局：" in pattern
    assert "- 大三角：三方和谐自足之局——某领域顺遂自洽,但易自满停滞、缺推动力。" in pattern
    assert "- T 三角（顶点 土星）：顶点星(apex)为张力出口——该星所主议题成为冲突焦点与行动驱力。" in pattern
    # 相位格局请求体照 AstroExtraCommon.chartParams：入宫盘时刻/地点 + tradition=false·predictive=false。
    (analysis,) = client.requests("/astroextra/analysis")
    assert (analysis["date"], analysis["time"], analysis["tradition"], analysis["predictive"]) == ("2025-03-20", "17:01:41", False, False)
    for title in ("天气占星", "四轴特殊点"):
        _section(text, title)
    # 卡片段紧贴正文之前（上游 buildAiSnapshot 拼接序：cardSecs 之后才是盘面正文）。
    assert text.index("[年盘概要]") < text.index("[起盘信息]")
    _clean(env)


def test_mundane_cycles_cards_request_the_upstream_page_defaults(tmp_path) -> None:
    client = ScriptedClient()
    env = _service(tmp_path, client).run_tool("mundane", {**MUNDANE, "mundaneType": "cycles"}, save_result=False)
    assert env.ok, env.error
    # 木土会合 = 页面挂载自动算的 1300–2200（MundaneMain.js:554/:753）；Barbault = 1900–2050、五慢星、跨度 150 年 → 半年步长（:793）。
    assert client.requests("/astroextra/greatconj")[-1] == {"startYear": 1300, "endYear": 2200}
    assert client.requests("/astroextra/barbault")[-1] == {
        "startYear": 1900, "endYear": 2050, "stepMonths": 6, "planets": ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"],
    }
    text = env.data["snapshot_text"]
    eras = _section(text, "木土纪元")
    assert eras[0] == "（木 ✕ 土（时代纪元）合相 · 地心 · 1300–2200 · 共 3 次）"
    # Barbault 最深谷/最高峰 = points 里 index 的最小/最大（:496-499），度数 Math.round。
    assert _section(text, "Barbault 聚散指数") == [
        "（慢星组合 五慢星 ♃♄♅♆♇（默认） · 1900–2050 · 3 点）",
        "最深谷（聚集）1983-01（300°）；最高峰（四散）2012-07（1334°）",
    ]
    _section(text, "大年时代")
    _clean(env)


def test_mundane_solar_eclipse_card_uses_the_eclipse_eclipsedetail_finds(tmp_path) -> None:
    # 与 skill [日食图] 段同一次食：eclipsedetail 自「入宫 − 2 日」起搜（astroextra.compute_eclipse_detail jd−2）。
    # 03-18 10:00 早于下限（入宫 03-20 17:01:41 − 2 日）→ 跳过；03-19 12:00 在下限之后、入宫之前 → 选中。
    eclipses = [
        {"type": "lunar_eclipse", "eclipseType": "total", "datetime": "2025-03-19 06:00:00", "lon": 178.0},
        {"type": "solar_eclipse", "eclipseType": "partial", "datetime": "2025-03-18 10:00:00", "lon": 358.0},
        {"type": "solar_eclipse", "eclipseType": "annular", "datetime": "2025-03-19 12:00:00", "lon": 359.0},
        {"type": "solar_eclipse", "eclipseType": "total", "datetime": "2025-09-21 19:41:00", "lon": 179.0},
    ]
    client = ScriptedClient(eclipses=eclipses)
    env = _service(tmp_path, client).run_tool("mundane", {**MUNDANE, "mundaneType": "solecl"}, save_result=False)
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    card = _section(text, "日食图判读")
    assert card[0] == "时刻 2025-03-19 12:00:00 · annular"
    assert "时长：约 3.88 小时 → 影响约 3.9 年（食时长定则）" in card
    detail = [p for p in client.requests("/astroextra/eclipsedetail") if p.get("date") == "2025-03-19"]
    assert detail and detail[-1]["time"] == "12:00:00" and detail[-1]["eclipseKind"] == "solar"
    # 食盘 = 该食时刻起盘（/chart 走 Java 日期口径时会被改写成 YYYY/MM/DD，比对前归一）。
    assert any(
        str(p.get("date")).replace("/", "-") == "2025-03-19" and p.get("time") == "12:00:00" for p in client.requests("/chart")
    )
    for title in ("食族 Saros", "天象占参考"):
        _section(text, title)
    assert "[月食图判读]" not in text
    _clean(env)


def test_mundane_newmoon_card_reads_the_syzygy_subchart(tmp_path) -> None:
    client = ScriptedClient()
    env = _service(tmp_path, client).run_tool("mundane", {**MUNDANE, "mundaneType": "newmoon"}, save_result=False)
    assert env.ok, env.error
    card = _section(env.data["snapshot_text"], "新月图判读")
    # selectedMoment = [新月图] 子盘那一次朔（入宫前最近的新月）。
    assert card[0] == "时刻 2025-02-28 08:44:39"
    assert card[-1] == "新月（日月合相）影响约一个月，主新启与变动；与当季入宫盘对照（入宫为时针、朔望为分针）。"
    assert "[满月图判读]" not in env.data["snapshot_text"]
    _clean(env)


def test_mundane_vedic_head_and_card_share_the_faithful_mesha_ingress(tmp_path) -> None:
    # 桩星历：恒星太阳在 2025-04-14 06:00:00 恰为 0°、日行 0.98565°。上游 solveVedicSolarIngress（同一步速）
    # 自 04-14 12:00 种子一步落到 06:00:00；旧实现借用恒星派求根器（步速 0.9856）会落到 05:59:59。
    client = ScriptedClient(vedic=True)
    env = _service(tmp_path, client).run_tool("mundane", {**MUNDANE, "mundaneType": "vedicmundane"}, save_result=False)
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    assert "梅沙入境时刻：2025-04-14 06:00:00" in _section(text, "吠陀世运")
    assert _section(text, "吠陀世运·年度盘")[0] == "当前入境时刻：2025-04-14 06:00:00"
    _section(text, "世运大运")
    _section(text, "KP 副主链")
    _clean(env)


def test_mundane_unsupported_type_is_reported_not_silently_ingress(tmp_path) -> None:
    """认不出的盘型不许静默当入宫盘：出段照旧、warnings 说出来。上游 MUNDANE_TYPES 十种自 v0.40.0（wave 3b）起全部可达
    （region 走建置盘流程，见 test_sync311_w3b_gim），所以对照用一个上游没有的盘型。"""
    env = _service(tmp_path, ScriptedClient()).run_tool("mundane", {**MUNDANE, "mundaneType": "cometchart"}, save_result=False)
    assert env.ok
    assert any("不支持的盘型 mundaneType=cometchart" in w for w in env.warnings), env.warnings
    assert "region" in HorosaSkillService._MUNDANE_SUPPORTED_TYPES


# ────────────────────────────── 择日：本命合参 + 回归与主限 ──────────────────────────────

ELECTION = {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "hsys": 0, "topicId": "marriage"}
NATAL = {"date": "1990-06-15", "time": "08:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}
# 行 = [弧, 迫星, 应星, 法, 日期]；择日日期 2028-04-06。
PD_ROWS = [
    [30.1, "D_Sun_0", "N_Moon_0", "Z", "2028-04-06 10:00:00"],      # Δ0
    [30.2, "D_Mars_90", "N_Asc_0", "Z", "2027-08-10 00:00:00"],     # Δ-240 → 在窗内（|Δ|>240 才剔）
    [30.3, "D_Venus_60", "N_MC_0", "Z", "2027-08-09 00:00:00"],     # Δ-241 → 剔
    [30.4, "S_Jupiter_120", "N_Sun_0", "", "2028-12-02 00:00:00"],  # Δ+240
    [30.5, "N_Saturn_180", "N_Venus_0", "Z", "2028-12-03 00:00:00"],  # Δ+241 → 剔
    [30.6, "short", "row"],                                          # 不足五列 → 跳过
    [30.7, "D_Moon_0", "N_Mars_0", "Z", "not-a-date"],               # 日期无效 → 跳过
    [30.8, "D_Sun_120", "N_Jupiter_0", "Z", "2028-04-01 00:00:00"],  # Δ-5
    [30.9, "D_Moon_60", "N_Saturn_0", "Z", "2028-04-11 00:00:00"],   # Δ+5（与 -5 同 |Δ|：稳定排序保原序）
    [31.0, "D_Venus_0", "N_Moon_0", "Z", "2028-04-16 00:00:00"],     # Δ+10
    [31.1, "S_Mars_180", "N_Sun_0", "Z", "2028-03-17 00:00:00"],     # Δ-20
    [31.2, "D_Jupiter_90", "N_Mercury_0", "Z", "2028-05-06 00:00:00"],  # Δ+30
    [31.3, "N_Moon_120", "N_Venus_0", "Z", "2028-02-26 00:00:00"],   # Δ-40
    [31.4, "D_Saturn_60", "N_Mars_0", "Z", "2028-05-26 00:00:00"],   # Δ+50
]


def _true_return_before(spec: dict, natal_lon: float, elec: datetime) -> datetime:
    """独立求根（二分）：择日时刻之前最近一次 lon(t) ≡ natal_lon —— 回归的定义本身。"""
    cycle = 360 / spec["rate"]
    lo, hi = elec - timedelta(days=cycle * 1.2), elec
    # 以 1 小时网格找最后一次穿越，再二分到秒级。
    grid = [lo + timedelta(hours=h) for h in range(int((hi - lo).total_seconds() // 3600) + 1)]
    last = None
    for a, b in zip(grid, grid[1:]):
        da, db = _short_delta(natal_lon, _body(spec, a)[0]), _short_delta(natal_lon, _body(spec, b)[0])
        if da >= 0 > db or da > 0 >= db:
            last = (a, b)
    assert last, "no crossing found"
    a, b = last
    for _ in range(60):
        mid = a + (b - a) / 2
        if _short_delta(natal_lon, _body(spec, mid)[0]) > 0:
            a = mid
        else:
            b = mid
    return a


def test_election_natal_adds_natal_integration_and_returns_with_primary_directions(tmp_path) -> None:
    client = ScriptedClient(pd_rows=PD_ROWS)
    env = _service(tmp_path, client).run_tool("election", {**ELECTION, "natal": NATAL}, save_result=False)
    assert env.ok, env.error
    text, receipt = env.data["snapshot_text"], env.data["natalReturns"]
    assert "[本命合参]" in text
    elec = datetime(2028, 4, 6, 9, 33, 0)
    natal_moment = datetime(1990, 6, 15, 8, 30, 0)
    for key, spec, tol_deg in (("solarReturn", _SUN, 0.005), ("lunarReturn", _MOON, 0.005)):
        got = datetime.strptime(receipt[key], "%Y-%m-%d %H:%M:%S")
        natal_lon = _body(spec, natal_moment)[0]
        # 回归定义（returnCharts.js:47 收敛判据 |Δ|<0.005°）+ 「择日之前最近一次」（独立二分求根作真值；
        # 容差 = 0.005° / 该体最慢速）。
        assert abs(_short_delta(natal_lon, _body(spec, got)[0])) < tol_deg, key
        truth = _true_return_before(spec, natal_lon, elec)
        slowest = spec["rate"] - spec["amp"] * 2 * math.pi / spec["period"]
        assert got <= elec and abs((got - truth).total_seconds()) <= tol_deg / slowest * 86400, (key, got, truth)
    # 上面是定义级真值；这里再钉端口在此星历上的逐秒输出（整秒折算 Math.round、≤6 步、|Δ|<0.005° 停），
    # 任何偏离上游迭代细节的改动都会先挪动这两个秒数。
    assert (receipt["solarReturn"], receipt["lunarReturn"]) == ("2027-06-15 14:29:46", "2028-03-24 12:53:02")
    ret = _section(text, "回归与主限")
    # 回归盘利钝（returnCharts.judgeReturnFacts）：上升=桩 Asc 处女；桩盘火星落 7 宫（角宫）→ 凶星临角；
    # 昼盘区分光太阳 exalt+dayTrip+face 有尊贵。
    assert ret[:4] == [
        f"- · 日返时刻 {receipt['solarReturn']}，上升 处女。",
        "- ▼ 日返盘凶星 火星 临角宫（本期承压）。",
        "- ▲ 日返盘区分光 太阳 有尊贵。",
        f"- · 月返时刻 {receipt['lunarReturn']}，上升 处女。",
    ]
    # 主限命中（fetchPdHitsNearElection :98-128）：|Δ|>240 剔、坏行跳过、按 |Δ| 稳定升序取前 8；
    # 排版（electionSnapshot.js:130-133）：日期（±N 日）：应星 ← 迫星（法），法为空不带括号。
    idx = ret.index("择日日期前后主限命中（±240 日内最近 8 条）：")
    assert ret[idx + 1:] == [
        "- 2028-04-06（+0 日）：N_Moon_0 ← D_Sun_0（Z）",
        "- 2028-04-01（-5 日）：N_Jupiter_0 ← D_Sun_120（Z）",
        "- 2028-04-11（+5 日）：N_Saturn_0 ← D_Moon_60（Z）",
        "- 2028-04-16（+10 日）：N_Moon_0 ← D_Venus_0（Z）",
        "- 2028-03-17（-20 日）：N_Sun_0 ← S_Mars_180（Z）",
        "- 2028-05-06（+30 日）：N_Mercury_0 ← D_Jupiter_90（Z）",
        "- 2028-02-26（-40 日）：N_Venus_0 ← N_Moon_120（Z）",
        "- 2028-05-26（+50 日）：N_Mars_0 ← D_Saturn_60（Z）",
    ]
    # 主限补拉请求：本命参数（日期用 /）+ 主限旗标；时间钥匙 = 有效口径（缺省 Ptolemy）。
    (pd_req,) = [p for p in client.requests("/chart") if p.get("includePrimaryDirection")]
    assert (pd_req["date"], pd_req["pdTimeKey"], pd_req["pdMethod"], pd_req["pdConverse"], pd_req["predictive"]) == (
        "1990/06/15", "Ptolemy", "core_alchabitius", 0, 1,
    )
    _clean(env)


def test_election_return_solver_caps_newton_at_six_steps_like_upstream(tmp_path) -> None:
    # 桩把 lonspeed 报成真速的 4 倍 → 牛顿每步只走 1/4，六步内收不敛。上游 solveReturnBefore
    # （returnCharts.js:40）固定：种子盘 1 张 + 循环 ≤6 张，不收敛就带着第 6 步之后的时刻返回（不报错、不加步）。
    client = ScriptedClient(pd_rows=PD_ROWS)
    orig = client._chart

    def lying_speed(payload: dict) -> dict:
        base = orig(payload)
        for obj in base["chart"]["objects"]:
            if obj["id"] in ("Sun", "Moon"):
                obj["lonspeed"] *= 4
        return base

    client._chart = lying_speed
    env = _service(tmp_path, client).run_tool("election", {**ELECTION, "natal": NATAL}, save_result=False)
    assert env.ok, env.error
    # 择日盘 1 + 本命盘 1 + 日返 (1+6) + 月返 (1+6) + 主限补拉 1 = 17。
    assert len(client.requests("/chart")) == 17
    receipt = env.data["natalReturns"]
    assert (receipt["solarReturn"], receipt["lunarReturn"]) == ("2027-06-15 08:42:04", "2028-03-24 16:09:15")


def test_election_pd_window_is_inclusive_at_240_days(tmp_path) -> None:
    # fetchPdHitsNearElection：`Math.abs(delta) > win` 才剔 —— ±240 日恰在窗内（returnCharts.js:123）。
    rows = [
        [1.0, "D_Sun_0", "N_Moon_0", "Z", "2027-08-10 00:00:00"],   # Δ-240
        [1.1, "D_Mars_0", "N_Asc_0", "Z", "2027-08-09 23:59:59"],   # Δ-241（只看日期部分）
        [1.2, "D_Venus_0", "N_MC_0", "Z", "2028-12-03 00:00:00"],   # Δ+241
        [1.3, "D_Moon_0", "N_Sun_0", "Z", "2028-04-09 00:00:00"],   # Δ+3
    ]
    client = ScriptedClient(pd_rows=rows)
    env = _service(tmp_path, client).run_tool("election", {**ELECTION, "natal": NATAL}, save_result=False)
    ret = _section(env.data["snapshot_text"], "回归与主限")
    idx = ret.index("择日日期前后主限命中（±240 日内最近 2 条）：")
    assert ret[idx + 1:] == [
        "- 2028-04-09（+3 日）：N_Sun_0 ← D_Moon_0（Z）",
        "- 2027-08-10（-240 日）：N_Moon_0 ← D_Sun_0（Z）",
    ]


def test_election_pd_time_key_follows_the_engine_resolved_override(tmp_path) -> None:
    # options.pdTimeKey 经引擎 resolveElectionParams 生效；旧存档值 Cardan → Cardano（returnCharts.js:106）。
    for given, sent in (("Naibod", "Naibod"), ("Cardan", "Cardano")):
        client = ScriptedClient(pd_rows=PD_ROWS)
        env = _service(tmp_path, client).run_tool(
            "election", {**ELECTION, "natal": NATAL, "options": {"pdTimeKey": given}}, save_result=False
        )
        assert env.ok, env.error
        (pd_req,) = [p for p in client.requests("/chart") if p.get("includePrimaryDirection")]
        assert pd_req["pdTimeKey"] == sent
        assert env.data["natalReturns"]["pdTimeKey"] == given


def test_election_without_natal_is_unchanged_and_incomplete_natal_is_an_input_error(tmp_path) -> None:
    client = ScriptedClient(pd_rows=PD_ROWS)
    svc = _service(tmp_path, client)
    plain = svc.run_tool("election", dict(ELECTION), save_result=False)
    assert plain.ok and "natalReturns" not in plain.data
    assert "[回归与主限]" not in plain.data["snapshot_text"] and "[本命合参]" not in plain.data["snapshot_text"]
    assert len(client.requests("/chart")) == 1  # 只起择日盘本身
    bad = svc.run_tool("election", {**ELECTION, "natal": {"date": "1990-06-15", "zone": "+08:00"}}, save_result=False)
    assert not bad.ok and bad.error.code == "tool.election_natal_missing_fields"
    assert set(bad.error.details["missing"]) == {"time", "lat", "lon"}


# ────────────────────────────── live（vendored 实例；未显式点名实例即 skip） ──────────────────────────────

from test_local_js_tools import make_service, requires_chart  # noqa: E402

_LIVE_TYPE_CARDS = {
    "ingress": ["年盘概要", "四季入境盘", "天气占星", "四轴特殊点", "盘型格局"],
    **{k: list(v) for k, v in HorosaSkillService._MUNDANE_TYPE_CARDS.items() if k != "vedicmundane"},
    "vedicmundane": ["吠陀世运·年度盘", "世运大运", "KP 副主链"],  # 天气与农业须手填受孕日 → 永不产
}


@requires_chart
@pytest.mark.parametrize("mundane_type", sorted(_LIVE_TYPE_CARDS))
def test_live_mundane_cards_per_type(tmp_path, mundane_type) -> None:
    payload = {**MUNDANE, "hsys": 1}
    if mundane_type != "ingress":
        payload["mundaneType"] = mundane_type
    env = make_service(tmp_path).run_tool("mundane", payload, save_result=False)
    assert env.ok, env.error
    detected = env.data["export_snapshot"]["section_titles_detected"]
    for title in _LIVE_TYPE_CARDS[mundane_type]:
        assert title in detected, (mundane_type, title)
    assert not [w for w in env.warnings if "mundane card" in w], env.warnings
    _clean(env)


@requires_chart
def test_live_election_returns_satisfy_the_return_definition(tmp_path) -> None:
    service = make_service(tmp_path)
    election = {**ELECTION, "gpsLat": 31.2167, "gpsLon": 121.4667}
    env = service.run_tool("election", {**election, "natal": NATAL}, save_result=False)
    assert env.ok, env.error
    receipt = env.data["natalReturns"]
    ret = _section(env.data["snapshot_text"], "回归与主限")
    assert ret[0].startswith(f"- · 日返时刻 {receipt['solarReturn']}，上升 ")
    assert "[本命合参]" in env.data["snapshot_text"]
    natal = service._call_remote("/chart", {**NATAL, "ad": 1, "hsys": 0, "zodiacal": 0, "tradition": 1, "predictive": 0})
    elec = datetime(2028, 4, 6, 9, 33, 0)
    for key, body, cycle in (("solarReturn", "sun", 365.25), ("lunarReturn", "moon", 27.321661)):
        got = datetime.strptime(receipt[key], "%Y-%m-%d %H:%M:%S")
        assert elec - timedelta(days=cycle * 1.1) < got <= elec, (key, got)
        at = service._call_remote("/chart", {
            "date": receipt[key][:10], "time": receipt[key][11:], "zone": "+08:00", "lat": "31n13", "lon": "121e28",
            "gpsLat": 31.2167, "gpsLon": 121.4667, "hsys": 0, "zodiacal": 0, "tradition": 1, "predictive": 0,
        })
        wanted = "Sun" if body == "sun" else "Moon"
        natal_lon = next(o["lon"] for o in natal["chart"]["objects"] if o["id"] == wanted)
        lon = next(o["lon"] for o in at["chart"]["objects"] if o["id"] == wanted)
        # 回归定义：返照时刻该体回到本命黄经（returnCharts.js 收敛判据 |Δ|<0.005°）。
        assert abs(_short_delta(natal_lon, lon)) < 0.005, (key, natal_lon, lon)
    _clean(env)


def test_js_round_mirrors_math_round_for_negative_values() -> None:
    """JS Math.round(x) = floor(x + 0.5)。旧 `_js_round` 用 int(x+0.5)（向零截断）：-1.7 → -1、-0.7 → 0，JS 为 -2 / -1。"""
    from horosa_skill.service import _js_round

    assert [_js_round(v) for v in (2.5, 1.4999, -0.5, -0.7, -1.5, -1.7, -2.5)] == [3, 1, 0, -1, -1, -2, -2]
