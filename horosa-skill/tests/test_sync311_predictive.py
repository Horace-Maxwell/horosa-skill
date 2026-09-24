"""上游 v3.11.1+（Horosa-Public HEAD 9b74714b）星运族同步：快照文字漂移 / [小限摘要] / 选项与缺省。

每条断言都钉在旧实现会红的值上（负向对照见提交说明）。权威出处写在各测试的注释里：
- 文字：上游 builder 源（utils/astroAiSnapshot.js、components/astro/*.js、utils/predictiveAiSnapshot.js、
  utils/profectionSummary.js）逐字；
- 值：波斯向运应期表 = 上游 AstroPersianDirected.js buildPersianHits 在 node 里原样执行的产物（摘要 sha256）；
  小限摘要 = profectionSummary.js 算法按 DateTime.jdn 口径手算。
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from test_service import FakeClient, FakeJsClient

from horosa_skill import predictive_text as P
from horosa_skill import service as S
from horosa_skill.agent_guidance import TOOL_GUIDANCE
from horosa_skill.config import Settings
from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

_FIXTURES = Path(__file__).parent / "fixtures"
# chart 服务把 /chart 挂在根路径（service._chart_server_endpoint），桩按真实路径记录。
CHART = S._chart_server_endpoint("/chart")
BIRTH = {
    "date": "1995-06-03", "time": "05:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
    "hsys": 0, "zodiacal": 0, "agent_confirmed_settings": True,
}


class RecordingClient(FakeClient):
    """FakeClient + 调用记录 + 按端点覆写响应（真实形状）。"""

    def __init__(self, overrides: dict | None = None) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []
        self.overrides = overrides or {}

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        if endpoint in self.overrides:
            value = self.overrides[endpoint]
            return value(payload) if callable(value) else copy.deepcopy(value)
        return super().call(endpoint, payload)

    def payloads(self, endpoint: str) -> list[dict]:
        return [payload for called, payload in self.calls if called == endpoint]


class RecordingJsClient(FakeJsClient):
    def __init__(self) -> None:
        super().__init__()
        self.runs: list[tuple[str, dict]] = []

    def run(self, tool_name: str, payload: dict) -> dict:
        self.runs.append((tool_name, dict(payload)))
        return super().run(tool_name, payload)


def _service(tmp_path, client=None, js_client=None) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(
        settings, client=client or RecordingClient(), store=MemoryStore(settings), js_client=js_client or RecordingJsClient()
    )


def _section(text: str, title: str) -> str:
    head = f"[{title}]\n"
    start = text.index(head) + len(head)
    end = text.find("\n\n[", start)
    return text[start:] if end < 0 else text[start:end]


# ── A1 方法说明（上游 utils/astroAiSnapshot.js:2021-2141 PREDICTIVE_METHOD_NOTES 逐字）──────────────

def test_method_notes_mirror_upstream_v311_rewrites() -> None:
    notes = S._PREDICTIVE_METHOD_NOTES
    assert notes["zodialrelease"][0] == (
        "黄道释放：自所选基点(默认幸运点,可改精神点等)所在星座起,按各星座守护星小年逐座、逐层释放,划分人生篇章(一级期)与子期(二级期)。"
    )
    assert notes["distributions"][0] == '界推运(分配法)：上升按主限速率行经黄道各界,界主星即该段"分配星";界表用当前全局界系设置。'
    assert notes["givenyear"] == [
        "指定年天象盘：按所给年份的时刻与地点起一张实时天象盘,与本命对照。",
        "读法：天象盘行星落本命宫位与两盘相位定该年主题。",
    ]
    assert notes["yearsystem129"][0] == "129 年系统：以七星小年合计 129 年为总周期,按小年切主限,主限内再七等分为子限。"
    assert notes["balbillus"][0].startswith("主/子限期法(Balbillus)：罗马期法,主限长度=该星小年 ×(1 − 离擢升度角距/360)")
    assert notes["triplicityrulers"][0].startswith("三分主星推运：当值光体(昼生取太阳、夜生取月亮)所在星座的三分性三主星")
    assert notes["keypoints"] == [
        "数字相位推运(120 关键点)：每颗星取「自释放点起第几个星座」k(1–12),年龄为 k 的倍数时该星被激活;另按各星专用小年(3/8/18/5/7/9/13)的倍数激活一次。",
        "读法：命中即激活年;k 越小复现越密;结合被激活点的本命性质定主题。",
    ]
    assert notes["extrareturns"] == [
        "多重回归：木星/土星等回归本命位置的整回归时刻表。",
        "读法：整回归=大周期重启(如土星回归约 29.5 岁);两次回归之间可自行取中点作阶段参照,表内不列。",
    ]


# ── A2 年龄推进点：精确穿越岁数（上游 AstroAgePoint.js:44-100，[Q-184/T-103]）────────────────────

_AGEPOINT_RESPONSE = {  # vendored astropy agepoint.compute 真实形状（1990-05-10 14:30 +08:00 上海盘节选）
    "agepoint": {
        "points": [
            {"age": 10, "apLon": 227.01, "sign": "Scorpio", "signlon": 17.01, "house": 2, "aspectTo": None},
            {"age": 11, "apLon": 231.93, "sign": "Scorpio", "signlon": 21.93, "house": 2, "aspectTo": "Moon",
             "aspect": "合", "aspectAge": 11.49, "aspects": [{"aspectTo": "Moon", "aspectAge": 11.49}]},
            {"age": 17, "apLon": 262.0, "sign": "Sagittarius", "signlon": 22.0, "house": 3, "aspectTo": None},
        ],
        "crossings": [{"age": 11.49, "aspectTo": "Moon", "apLon": 234.34}, {"age": 23.53, "aspectTo": "Saturn", "apLon": 295.32}],
    }
}


def test_agepoint_prints_exact_crossing_ages() -> None:
    text = S._build_agepoint_snapshot_text(_AGEPOINT_RESPONSE)
    body = _section(text, "年龄推进点（Age Point / Huber）")
    assert "关键岁数（合本命，精确穿越岁数）：11.49岁合月；23.53岁合土" in body
    assert "| 年龄 | 落座 | 宫 | 合本命（穿越岁数） |" in body
    assert "| 11岁 | 天蝎 21.93° | 2宫 | 月(11.49岁) |" in body
    # JS `${22.0}` = "22"：整数值的浮点不带 .0（旧实现印 22.0°）。
    assert "| 17岁 | 射手 22° | 3宫 | — |" in body


def test_agepoint_header_uses_natal_chart_birth_lines(tmp_path) -> None:
    # 上游 buildPredictiveBirthHeaderLines（astroAiSnapshot.js:1956-1998）：旧实现对无盘响应一律写「夜生盘」。
    client = RecordingClient({"/predict/agepoint": _AGEPOINT_RESPONSE})
    result = _service(tmp_path, client).run_tool("agepoint", dict(BIRTH), save_result=False)
    header = _section(result.data["snapshot_text"], "起盘信息")
    # 出生时间行取本命盘回显 params.birth 原样（真后端回显 YYYY-MM-DD；FakeClient 原样回声请求里的 YYYY/MM/DD）。
    assert header.splitlines() == [
        "出生时间：1995/06/03 05:30:00 周六",
        "真太阳时：1995/06/03 05:30:00",
        "经纬度：121e28 31n13",
        "时区：+08:00",
        "黄道：回归黄道",
        "宫制：整宫制",
        "盘型：日生盘",
    ]
    assert CHART in [endpoint for endpoint, _ in client.calls]


def test_distributions_intro_names_global_bounds_table() -> None:
    text = S._build_distributions_snapshot_text(
        {"dist": [{"distributor": "Mars", "sign": "Virgo", "participants": ["Moon"], "startDate": "1997-08-01 21:57:47", "endDate": "2002-03-29 07:41:27"}]}
    )
    body = _section(text, "界推运（分配法 / Distributions）")
    assert body.splitlines()[0] == "上升点经主限运动穿越黄道各界（界表用当前全局界系设置）；分配星=界主星，参与星=该期间内上升点触及的行星。"
    assert "| 火 | 室女 | 月 | 1997-08-01 21:57:47 | 2002-03-29 07:41:27 |" in body


# ── A3 多重回归：逆行三过全列 + 各回时刻 + 本命黄经（AstroExtraReturns.js:36-70，[Q-366/T-345]）────────

_SATURN_RETURNS = {  # vendored astroextra.compute_planet_return 真实响应（1990-05-10 盘，Saturn，count=5 节选）
    "returns": [
        {"which": 1, "date": "2020-02-03", "time": "16:54:41",
         "passes": [{"date": "2020-02-03", "time": "16:54:41", "pass": 1, "retrograde": False}]},
        {"which": 2, "date": "2049-03-16", "time": "02:12:19", "passes": [
            {"date": "2049-03-16", "pass": 1, "retrograde": False},
            {"date": "2049-06-29", "pass": 2, "retrograde": True},
            {"date": "2049-12-11", "pass": 3, "retrograde": False}]},
    ],
    "natalLon": 295.321,
    "body": "Saturn",
}


def test_extrareturns_lists_every_retrograde_pass_times_and_natal_lon(tmp_path) -> None:
    client = RecordingClient({"/astroextra/planetreturn": _SATURN_RETURNS})
    result = _service(tmp_path, client).run_tool("extrareturns", dict(BIRTH), save_result=False)
    body = _section(result.data["snapshot_text"], "多重回归")
    assert body.splitlines()[0] == (
        "土星返照（≈29.5 年）：第1回 2020-02-03，第2回 2049-03-16/2049-06-29(逆)/2049-12-11；"
        "时刻：第1回 16:54:41，第2回 02:12:19；本命黄经 295.3°"
    )
    # 上游导出取 5 回（与组件 count=5 对齐；旧实现 4 回）。
    assert {p["count"] for p in client.payloads("/astroextra/planetreturn")} == {5}


# ── A2/F6 波斯向运：速率/方向/年数驱动主表 + 日期与上游 moment 口径逐日一致 ───────────────────────────

def _persian_digest(hits: list[dict]) -> str:
    blob = "\n".join(
        f"{P.js_str(h['age'])}|{h['promittor']}|{P.js_str(h['aspect'])}|{h['significator']}|{h['date']}" for h in hits
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def test_persian_hits_match_upstream_js_execution() -> None:
    # 权威：上游 components/astro/AstroPersianDirected.js buildPersianHits（v3.11.1+）在 node + moment 2.30 下原样执行，
    # 输入 tests/fixtures/chart_1998_predictive.json；旧 Python 端口按整数日截断以外的口径算日期，40% 行差 1 天。
    chart = json.loads((_FIXTURES / "chart_1998_predictive.json").read_text(encoding="utf-8"))
    for (rate, years, direction), (count, digest) in {
        ("persian", 90, "direct"): (570, "e597c672f53f7f526be6c92bea60328b1384514b01de4e42429164b845760cf6"),
        ("prophected", 120, "converse"): (23520, "497813ef96b1e4117e5a67947fa09398e7cf68cc40669806b54ec0e958cca7fe"),
        ("naibod", 200, "direct"): (1269, "fb805c121f5a6cae9ff51172eb0cb9284aa21384d8b40da36cc3aa34327315f7"),
    }.items():
        hits = S._build_persian_hits(chart, rate, years, direction)
        assert (len(hits), _persian_digest(hits)) == (count, digest), (rate, years, direction)
    default = S._build_persian_hits(chart, "persian", 90, "direct")
    assert {"age": 1.43, "promittor": "Mercury", "aspect": 60, "significator": "Pars Fortuna", "date": "1999-07-28"} in default


def test_persiandirected_options_drive_main_table_and_near_hits() -> None:
    chart = json.loads((_FIXTURES / "chart_1998_predictive.json").read_text(encoding="utf-8"))
    moment: list[str] = []
    text = S._build_persiandirected_snapshot_text(
        chart, {"rateKey": "prophected", "direction": "converse", "maxYears": 120},
        now=datetime(2026, 9, 24, 12, 0, 0), moment_lines=moment,
    )
    body = _section(text, "波斯向运（Persian Directed）")
    assert body.splitlines()[0] == (
        "黄经象征向运(Prophected 30°/年)：所有行星/点按此速率逆向(Converse)推进,本命宫头不动；下表为向运星触及本命的应期。"
    )
    main_rows = [ln for ln in body.split("◆")[0].splitlines() if ln.startswith("| ") and "---" not in ln and "年龄" not in ln]
    assert len(main_rows) == 480  # max(200, maxYears×4)
    assert "◆ 近期命中（距今最近）" in body
    assert moment == ["当前向运年龄：28.59 岁（按导出时刻）"]


def test_persianchart_keeps_dirzone_and_rejects_unknown_rate(tmp_path) -> None:
    client = RecordingClient()
    service = _service(tmp_path, client)
    result = service.run_tool(
        "persiandirected", {**BIRTH, "datetime": "2026-09-01", "dirZone": "-05:00", "rateKey": "naibod"}, save_result=False
    )
    assert result.ok is True
    sent = client.payloads("/predict/persianchart")[-1]
    # 上游 v3.11 [Q-173]：persianchart 按 dirZone 解释目标时刻（旧实现把 dirZone 剥掉）。
    assert sent["dirZone"] == "-05:00" and sent["rateKey"] == "naibod"
    assert "黄经象征向运(Naibod 59′08″/年)" in result.data["snapshot_text"]
    bad = service.run_tool("persiandirected", {**BIRTH, "rateKey": "fast"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.predictive_invalid_option"


# ── A2/F10 赤纬推运 / 恒星推运：目标日缺省今天 + 三法小节 + 月长档 ──────────────────────────────────

def _methods(kind: str) -> list[dict]:
    base = {
        "secondary": {"datetime": "1995-07-04 08:12:00"},
        "tertiary": {"datetime": "1997-09-08 21:08:54"},
        "minor": {"datetime": "1998-04-18 19:05:32"},
    }
    out = []
    for method, when in base.items():
        entry: dict = {"method": method, "progressedDate": when}
        if kind == "decl":
            entry["declinations"] = [{"id": "Sun", "decl": 22.9123}, {"id": "Moon", "decl": -2.0}]
            entry["parallels"] = [{"a": "Sun", "b": "Jupiter", "type": "parallel", "orb": 0.018}]
        else:
            entry["positions"] = [
                {"id": "Sun", "sign": "Gemini", "signlon": 0.5412, "lonspeed": 0.9567},
                {"id": "Pluto", "sign": "Scorpio", "signlon": 1.2, "lonspeed": 0.0},
            ]
            entry["aspectsToNatal"] = [{"a": "Sun", "b": "Venus", "aspect": 0.0, "orb": 0.401}]
        out.append(entry)
    return out


def test_jaynesprog_mirrors_upstream_builder(tmp_path) -> None:
    client = RecordingClient({"/astroextra/jaynesprog": {"methods": _methods("decl"), "natalDeclinations": [{"id": "Sun", "decl": 22.1}]}})
    before = datetime.now().strftime("%Y-%m-%d")
    result = _service(tmp_path, client).run_tool("jaynesprog", dict(BIRTH), save_result=False)
    after = datetime.now().strftime("%Y-%m-%d")
    sent = client.payloads("/astroextra/jaynesprog")[-1]
    # F10：缺省推到今天（上游 today()），旧实现推到出生日（零推运）。
    assert sent["targetDate"] in {before, after} and sent["targetDate"] != BIRTH["date"]
    assert sent["targetTime"] == "12:00:00" and sent["minorVariant"] == "synodic"
    text = result.data["snapshot_text"]
    main = _section(text, "赤纬推运（Declination）")
    assert main.splitlines() == [
        "赤纬推运：推运后看赤纬平行/反平行（下表为二次推运，推至所选目标日期）。",
        f"目标日期：{sent['targetDate']} 12:00:00（各法推运时刻=按该法折算，见各小节）",
    ]
    natal = _section(text, "本命盘配置")
    assert natal.startswith("出生时间：1995/06/03 05:30:00 周六")  # FakeClient 回声请求日期格式
    assert "◆ 本命赤纬\n| 点 | 赤纬 |\n| --- | --- |\n| 日 | 22.10° |" in natal
    periods = _section(text, "时段盘 赤纬平行/反平行")
    assert periods.splitlines()[2] == "| 日 | 平行 | 木 | 0.018 |"
    assert "◆ 二次推运 推运赤纬\n推运时刻：1995-07-04 08:12:00\n| 点 | 赤纬 |" in periods
    assert "◆ 小推运 推运赤纬\n推运时刻：1998-04-18 19:05:32\n月长算法：朔望月每年（标准·默认）" in periods
    assert "◆ 三次推运 赤纬平行/反平行" in periods


def test_vedicprog_mirrors_upstream_prog_builder(tmp_path) -> None:
    client = RecordingClient({"/astroextra/progressions": {"methods": _methods("pos")}})
    result = _service(tmp_path, client).run_tool(
        "vedicprog", {**BIRTH, "targetDate": "2026-09-24", "minorVariant": "sidereal"}, save_result=False
    )
    sent = client.payloads("/astroextra/progressions")[-1]
    assert sent["zodiacal"] == 1 and sent["minorVariant"] == "sidereal"
    text = result.data["snapshot_text"]
    assert "[起盘信息]" not in text  # 上游 vedicprog preset 无该段（生辰行并入 [本命盘配置]）
    assert _section(text, "恒星推运（Vedic Sidereal）").splitlines() == [
        "二次/三次/小限推运在恒星黄道（sidereal）下计算；下表为二次推运，推至下方所列目标日期。",
        "目标日期：2026-09-24 12:00:00（各法推运时刻=按该法折算，见各小节）",
    ]
    table = _section(text, "时段盘配置 二次推运位置")
    assert table.splitlines()[:3] == ["| 点 | 恒星推运位置 |", "| --- | --- |", "| 日 | 双子 0.54° |"]
    assert "◆ 小推运 推运位置\n推运时刻：1998-04-18 19:05:32\n月长算法：恒星月每年\n| 点 | 恒星推运位置 | 速度 |" in table
    assert "| 日 | 双子 0.54° | 0.9567 |" in table
    assert "◆ 二次推运 与本命相位\n| 推运点 | 相位 | 本命点 | 误差 |\n| --- | --- | --- | --- |\n| 日 | 0º | 金 | 0.401 |" in table
    bad = _service(tmp_path, RecordingClient()).run_tool("vedicprog", {**BIRTH, "minorVariant": "lunar"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.predictive_invalid_option"


def test_planetaryarc_defaults_to_tomorrow_now_and_puts_table_under_aspects(tmp_path) -> None:
    arc_response = {"date": "x", "arcSource": "Moon", "chart": {"objects": [], "aspects": [
        {"directId": "Venus", "objects": [{"natalId": "Mars", "aspect": 135, "delta": 0.4038}]}]}}
    client = RecordingClient({"/predict/planetaryarc": arc_response})
    result = _service(tmp_path, client).run_tool("planetaryarc", dict(BIRTH), save_result=False)
    sent = client.payloads("/predict/planetaryarc")[-1]
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    # F10：上游 todayStr() = 明天此刻（[Q-174/T-114]）；旧实现缺省成出生日。
    assert sent["datetime"].startswith(tomorrow)
    text = result.data["snapshot_text"]
    assert _section(text, "行星弧（Planetary Arc）") == "行星弧(默认月亮弧)：以所选天体的二次推运移动量为弧推进全盘，看向运星对本命的相位。"
    assert _section(text, "相位").splitlines() == ["| 向运星 | 相位 | 本命星 | 误差 |", "| --- | --- | --- | --- |", "| 金 | 135º | 火 | 0.404 |"]


# ── 行星年龄 / 129 年系统（planetaryAges.js:79-127 / AstroYearSystem129.js:20-50）──────────────────

def test_planetaryages_defaults_to_now_and_adds_year_bands() -> None:
    chart = json.loads((_FIXTURES / "chart_1998_predictive.json").read_text(encoding="utf-8"))
    moment: list[str] = []
    # 出生 1998-02-20 20:48；「此刻」2026-09-24 → 周岁 28 → 太阳带（上游无 asOf 即按 moment()，旧实现不标带）。
    text = S._build_planetaryages_snapshot_text(chart, None, now=datetime(2026, 9, 24, 12, 0, 0), moment_lines=moment)
    assert "当前年龄：约 28 岁" in text and "| 22-41岁 | 日 | 双鱼 1° | ● |" in text
    assert moment == ["当前主政：日（22-41岁）"]
    # moment diff 的锚 = 生日 + 整月数（月末钳位）：2/29 生人平年 2/28 当天即满岁；前一刻未满。
    assert S._full_years_between("2024-02-29 05:30:00", datetime(2027, 2, 28, 12, 0, 0)) == 3
    assert S._full_years_between("2024-02-29 05:30:00", datetime(2027, 2, 28, 5, 0, 0)) == 2
    assert S._full_years_between("1998-02-20 20:48:00", datetime(2026, 2, 20, 20, 47, 59)) == 27
    assert "◆ 行星年四档（小年/中年/大年/极大年）" in text and "土：小年 30 · 中年 43.5 · 大年 57 · 极大年 465" in text
    # 四档常量 = 上游 HEAD divination/data/hellenisticData.json planetary_years（日中年 69.5、月中年 66.5）。
    # ⚠ vendored 副本（horosa-core-js/src/vendor/divination/data/hellenisticData.json）此键仍是旧值 39.5/39.5，
    # 本仓无消费方；已报 lead 走 re-vendor，不在此手改 vendored 数据。
    assert P.PLANETARY_YEARS["Sun"] == {"least": 19, "mean": 69.5, "greater": 120, "greatest": 1461}
    assert P.PLANETARY_YEARS["Moon"] == {"least": 25, "mean": 66.5, "greater": 108, "greatest": 520}
    assert sum(y["least"] for y in P.PLANETARY_YEARS.values()) == 129
    ys = S._build_yearsystem129_snapshot_text(chart)
    assert "| 月 | 月 | 1998-02-20 |" in ys  # 上游 cn = AstroTxtMsg[id]（单字），旧实现印「月亮」


# ── B [小限摘要]（profectionSummary.js:73-156，[Q-105]）─────────────────────────────────────────

def test_profection_summary_values_follow_upstream_arithmetic() -> None:
    # 手算（DateTime.jdn：出生按 +08:00、目标按 dirZone）：days=11362.27 → 已满 31 岁、当年第 2 月、日推 3 座；
    # 上升室女(5)：年座=(5+31)%12=牡羊·第 8 宫；月座=金牛·第 9 宫；日座=狮子·第 12 宫。
    wrap = {"chart": {"isDiurnal": True, "objects": [
        {"id": "Asc", "sign": "Virgo"}, {"id": "Pars Fortuna", "sign": "Aries"}, {"id": "Moon", "sign": "Scorpio"}, {"id": "Sun", "sign": "Aries"}]}}
    params = {"date": "1995-06-03", "time": "05:30:00", "datetime": "2026-07-12 12:00:00", "dirZone": "+08:00"}
    assert P.build_profection_summary_lines(wrap, params, None, None) == [
        "年小限（自上升）：牡羊 · 第 8 宫（自上升所在星座起数）", "小限主星：火", "已满 31 岁",
    ]
    assert P.build_profection_summary_lines(wrap, params, "m", "asc") == [
        "月小限（自上升）：金牛 · 第 9 宫（自上升所在星座起数）", "小限主星：金", "已满 31 岁　当年第 2 月",
        "年级参照：牡羊 · 第 8 宫（自上升所在星座起数）",
    ]
    assert P.build_profection_summary_lines(wrap, params, "d", "asc")[0] == "日小限（自上升）：狮子 · 第 12 宫（自上升所在星座起数）"
    # 再推 7 天：当年第 46.76 天 → 月内 16.33 天 ÷ 2.5 天/座 = 推 6 座 → 金牛+6 = 天蝎·第 3 宫（2.5 天/座口径的判别点）。
    later = {**params, "datetime": "2026-07-19 12:00:00"}
    assert P.build_profection_summary_lines(wrap, later, "d", "asc")[:2] == ["日小限（自上升）：天蝎 · 第 3 宫（自上升所在星座起数）", "小限主星：火"]
    assert P.build_profection_summary_lines(wrap, params, "y", "fortune")[:2] == ["年小限（自福点）：天蝎 · 第 8 宫（自福点所在星座起数）", "小限主星：火"]
    assert P.build_profection_summary_lines(wrap, params, "y", "moon")[1] == "小限主星：水"


def test_profection_emits_summary_section_at_upstream_position(tmp_path) -> None:
    assert AI_EXPORT_PRESET_SECTIONS["profection"] == ["本命盘配置", "起盘信息", "小限摘要", "时段盘配置", "相位", "方法说明"]
    service = _service(tmp_path)
    result = service.run_tool("profection", {**BIRTH, "datetime": "2026-07-12 12:00:00", "profGrain": "m"}, save_result=False)
    text = result.data["snapshot_text"]
    titles = [line for line in text.splitlines() if line.startswith("[")]
    assert titles == ["[本命盘配置]", "[起盘信息]", "[小限摘要]", "[时段盘配置]", "[相位]", "[方法说明]"]
    assert _section(text, "小限摘要").splitlines()[0] == "月小限（自上升）：金牛 · 第 9 宫（自上升所在星座起数）"
    # [起盘信息] = 上游 buildSetupLines（推运时间/时区/经纬度/步进/容许度/月交点逆行）。
    assert _section(text, "起盘信息").splitlines() == [
        "推运时间：2026-07-12 12:00:00", "推运时区：+08:00", "推运经纬度：121e28 31n13",
        "时间步进：y", "相位容许度：1", "月交点逆行：否",
    ]
    bad = service.run_tool("profection", {**BIRTH, "profStart": "venus"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.predictive_invalid_option"


def test_period_presets_mirror_upstream() -> None:
    # 上游 aiExport.js:639-652：目标时刻型 5 法无 [当前时点]；vedicprog 无 [起盘信息]；zr 无 skill 自拟 [本命盘星与虚点]。
    for key in ("solararc", "solarreturn", "lunarreturn", "givenyear"):
        assert AI_EXPORT_PRESET_SECTIONS[key] == ["本命盘配置", "起盘信息", "时段盘配置", "相位", "方法说明"], key
    assert AI_EXPORT_PRESET_SECTIONS["vedicprog"] == ["恒星推运（Vedic Sidereal）", "本命盘配置", "时段盘配置 二次推运位置", "当前时点", "方法说明"]
    assert AI_EXPORT_PRESET_SECTIONS["zodialrelease"] == ["起盘信息", "星盘信息", "基于X点推运", "当前时点", "方法说明"]


# ── F19 返照/小限/主限法盘缺省 ───────────────────────────────────────────────────────────────

def test_return_tools_default_to_this_years_birthday_at_natal_place(tmp_path) -> None:
    for tool, endpoint in (("solarreturn", "/predict/solarreturn"), ("lunarreturn", "/predict/lunarreturn"), ("givenyear", "/predict/givenyear")):
        client = RecordingClient()
        year = datetime.now(timezone(timedelta(hours=8))).strftime("%Y")
        result = _service(tmp_path, client).run_tool(tool, dict(BIRTH), save_result=False)
        assert result.ok is True, (tool, result.error)
        sent = client.payloads(endpoint)[-1]
        # 上游 aiAnalysisContext.js:2681-2687（[挂载自检 F-17]）：当年 + 出生月日 + 出生时分；dirLat/dirLon 缺省本命。
        assert sent["datetime"] == f"{year}-06-03 05:30", tool
        assert (sent["dirLat"], sent["dirLon"], sent["dirZone"]) == ("31n13", "121e28", "+08:00"), tool
        assert result.input_normalized["datetime"] == sent["datetime"]


def test_profection_and_solararc_default_to_now(tmp_path) -> None:
    for tool, endpoint in (("profection", "/predict/profection"), ("solararc", "/predict/solararc")):
        client = RecordingClient()
        before = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
        _service(tmp_path, client).run_tool(tool, dict(BIRTH), save_result=False)
        after = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
        sent = client.payloads(endpoint)[-1]
        assert sent["datetime"] in {before, after}, tool
        assert sent["dirZone"] == "+08:00", tool


def test_pdchart_defaults_to_first_filtered_direction_row(tmp_path) -> None:
    chart = FakeClient().call("/chart", dict(BIRTH))
    chart["predictives"] = {"primaryDirection": [
        [0.1, "T_Mars_0", "N_Sun_0", "Z", "1995-06-20 00:00:00"],      # 界行 → core 方法下剔除
        [0.2, "D_Vesta_60", "N_Sun_0", "Z", "1995-07-01 00:00:00"],    # 灶神星不在 core 支持集 → 剔除
        [0.5, "D_Mars_60", "N_Neptune_0", "Z", "1995-12-24 13:19:16"],
    ]}
    client = RecordingClient({CHART: lambda payload: chart if payload.get("includePrimaryDirection") else FakeClient().call("/chart", payload)})
    result = _service(tmp_path, client).run_tool("pdchart", {**BIRTH, "pdMethod": "core_alchabitius"}, save_result=False)
    assert result.ok is True
    sent = client.payloads("/predict/pdchart")[-1]
    # 上游 AstroPrimaryDirectionChart.js:454 defaultPdChartDateTime：首条过滤后行的日期（UTC 墙钟）。
    assert (sent["datetime"], sent["dirZone"]) == ("1995-12-24 13:19:16", "+00:00")
    bad = _service(tmp_path, RecordingClient()).run_tool("pd", {**BIRTH, "pdMethod": "koch"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.predictive_invalid_option"


# ── F8 黄道星释：基点 → 起释星座 + 段头 + 层级钻取 ─────────────────────────────────────────────

_ZR_RESPONSE = {"zr": [
    {"sign": "Aquarius", "level": 1, "date": "1995-06-03", "days": 10950, "sublevel": [
        {"sign": "Aquarius", "level": 2, "date": "1995-06-03", "days": 900},
        {"sign": "Leo", "level": 2, "date": "1998-02-10", "days": 500},
        {"sign": "Virgo", "level": 2, "date": "1999-06-25", "days": 400},
        {"sign": "Leo", "level": 2, "date": "2000-07-29", "days": 300, "truncated": True},
    ]},
    {"sign": "Pisces", "level": 1, "date": "2025-05-27", "days": 4500},
]}


def test_zr_base_point_resolves_start_sign_and_upstream_label(tmp_path) -> None:
    client = RecordingClient({"/predict/zr": _ZR_RESPONSE})
    service = _service(tmp_path, client)
    result = service.run_tool("zr", {**BIRTH, "basePoint": "Pars Spirit"}, save_result=False)
    # FakeClient 本命盘 lots：灵点在宝瓶 → startSign=Aquarius（上游 AstroZR.js:367-376）。
    assert client.payloads("/predict/zr")[-1]["startSign"] == "Aquarius"
    text = result.data["snapshot_text"]
    body = _section(text, "基于灵点推运")
    assert body.splitlines() == ["AI输出模式：输出所有L1（星座+时间）", "L1-1：宝瓶-1995-06-03", "L1-2：双鱼-2025-05-27"]
    assert _section(text, "星盘信息").splitlines() == ["黄道：Tropical", "宫制：整宫制", "盘型：日生盘"]
    drill = service.run_tool("zr", {**BIRTH, "aiMode": "l2_in_l1"}, save_result=False)
    assert _section(drill.data["snapshot_text"], "基于福点推运").splitlines() == [
        "AI输出模式：输出某个L1下全部L2", "L1-1：宝瓶-1995-06-03",
        "L2-1：宝瓶-1995-06-03", "L2-2：狮子-1998-02-10", "L2-3：室女-1999-06-25", "L2-4：狮子-2000-07-29-LB-截",
    ]
    bad = service.run_tool("zr", {**BIRTH, "basePoint": "Vertex"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.predictive_invalid_option"


def test_zr_current_period_line_feeds_current_moment() -> None:
    line = S._zr_current_period_line(_ZR_RESPONSE["zr"], datetime(1998, 6, 1, tzinfo=timezone.utc))
    assert line == "当前所处：L1 宝瓶期（1995-06-03 至 2025-05-27） / L2 狮子期（1998-02-10 至 1999-06-25）"


# ── F7 Balbillus / 三分主星 / 数字相位：选项透传到 vendored builder ───────────────────────────────

def test_progextra_options_are_validated_and_forwarded(tmp_path) -> None:
    js = RecordingJsClient()
    service = _service(tmp_path, RecordingClient(), js)
    service.run_tool("balbillus", {**BIRTH, "startPlanet": "Moon", "yearType": "hellenistic", "mode": "forward"}, save_result=False)
    service.run_tool("triplicityrulers", {**BIRTH, "division": "halves", "lifespan": 90}, save_result=False)
    service.run_tool("keypoints", {**BIRTH, "mode": "body"}, save_result=False)
    options = [payload.get("options") for tool, payload in js.runs if tool == "progextra"]
    assert options == [
        {"startPlanet": "Moon", "yearType": "hellenistic", "mode": "forward"},
        {"division": "halves", "lifespan": 90.0},
        {"mode": "body"},
    ]
    bad = service.run_tool("triplicityrulers", {**BIRTH, "lifespan": 10}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.predictive_invalid_option"


def test_progextra_locator_lines_land_in_current_moment(tmp_path) -> None:
    # 上游 balbillus.js:255-270 extraLines → buildCurrentMomentLines；JS stub 截获后经 moment_lines 回传。
    class LocatorJs(RecordingJsClient):
        def run(self, tool_name: str, payload: dict) -> dict:
            result = super().run(tool_name, payload)
            if tool_name == "progextra":
                result = {**result, "moment_lines": ["当前主限：日（起 2026-06-02，时长 15.35 年）"]}
            return result

    text = _service(tmp_path, RecordingClient(), LocatorJs()).run_tool("balbillus", dict(BIRTH), save_result=False).data["snapshot_text"]
    assert _section(text, "当前时点").splitlines()[-1] == "当前主限：日（起 2026-06-02，时长 15.35 年）"


# ── F15 [寿命格局] 取主法 ─────────────────────────────────────────────────────────────────────

def test_lifespan_method_reaches_natal_extras(tmp_path) -> None:
    js = RecordingJsClient()
    service = _service(tmp_path, RecordingClient(), js)
    service.run_tool("chart", {**BIRTH, "lifespanMethod": "dorotheus"}, save_result=False)
    sent = [payload for tool, payload in js.runs if tool == "astroextra"][-1]
    assert sent["options"] == {"lifespanMethod": "dorotheus"}
    bad = service.run_tool("chart", {**BIRTH, "lifespanMethod": "valens"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.predictive_invalid_option"


# ── F20 主限法词表与标签（primaryDirectionSync.js:57-115）───────────────────────────────────────

def test_primary_direction_labels_follow_upstream_vocabulary() -> None:
    assert S._primary_direction_method_text("placidus") == "Placidus（半弧）"
    assert S._primary_direction_method_text("core_alchabitius") == "Alchabitius"
    assert S._primary_direction_method_text(None) == "Alchabitius"
    assert S._primary_direction_time_key_text("VanDam") == "Van Dam（真弧）"
    assert S._primary_direction_time_key_text("User") == "自定义（每年度数）"
    assert len(S._PD_METHOD_LABELS) == 13 and len(S._PD_TIME_KEY_LABELS) == 26


def test_primary_direction_table_mirrors_upstream_builder(tmp_path) -> None:
    # 上游 components/direction/AstroDirectMain.js:168-223 directionObjText / :122 degreeText / :337-431 段结构。
    wrap = {"chart": {"objects": [{"id": "Moon", "house": "House3", "ruleHouses": ["House11"]}]}}
    assert S._pd_direction_obj_text("D_Moon_120", wrap) == "月 (3th; 11R)的120度右相位处"
    assert S._pd_direction_obj_text("S_Sun_90", wrap) == "日的90度左相位处"
    assert S._pd_direction_obj_text("N_Vertex_0", wrap) == "宿命点"
    assert S._pd_direction_obj_text("T_Mars_Aries", wrap) == "牡羊的火界"
    assert S._pd_direction_obj_text("C_Cusp3_0", wrap) == "第3宫头的反映点"
    assert S._pd_direction_obj_text("MP_Jupiter_90", wrap) == "木的世界平行·ASC"
    assert S._pd_direction_obj_text("LT_Pars Spirit_0", wrap) == "Spirit点"
    # msg() 先 AstroTxtMsg 后 AstroMsg（constants/AstroText.js:278 AstroMsg[STAR_ALGOL]='大陵五'）：恒星迫星落中文星名。
    assert S._pd_direction_obj_text("FS_Algol_0", wrap) == "恒星 大陵五"
    assert S._pd_direction_obj_text("N_Regulus_0", wrap) == "狮心轩辕十四"
    assert S._pd_degree_text(-0.124066360236327, "core_alchabitius") == "-0度7分"
    assert S._pd_split_degree_text(36.37) == "36度22分"
    service = _service(tmp_path)
    text = service.run_tool(
        "pd", {**BIRTH, "pdMethod": "placidus", "pdTimeKey": "VanDam", "pdConverse": 0}, save_result=False
    ).data["snapshot_text"]
    setting = _section(text, "主限法设置").splitlines()
    assert setting[:4] == ["推运方法：Placidus（半弧）", "度数换算：Van Dam（真弧）", "方向类型：黄道（In Zodiaco）", "向运方向：顺向 Direct"]
    assert "弧算法（投影）：Placidus（半弧严密）" in setting and "盘面宫制（分宫）：Placidus" in setting
    assert _section(text, "主限法表格").splitlines()[0] == "| Arc | 迫星 | 应星 | 日期(UTC) |"
    assert "表中距今最近行：" in _section(text, "当前时点")
    chart_text = service.run_tool("pdchart", {**BIRTH, "datetime": "2031-04-06 09:33:00", "direction": "converse"}, save_result=False).data["snapshot_text"]
    assert _section(chart_text, "主限法盘设置").splitlines()[-2:] == ["向运方向：逆向 Converse", "当前Arc：3度0分"]


def test_guidance_states_upstream_defaults() -> None:
    def defaults(tool: str) -> dict:
        return {item["field"]: item["value"] for item in TOOL_GUIDANCE[tool]["safe_defaults"]}

    assert defaults("vedicprog")["targetDate"] == "今天" and defaults("jaynesprog")["minorVariant"] == "synodic"
    assert defaults("planetaryarc")["datetime"] == "明天此刻"
    assert defaults("solarreturn")["datetime"] == "今年生日时刻" and defaults("lunarreturn")["dirLat/dirLon"] == "出生地"
    assert defaults("profection")["profGrain"] == "y" and defaults("zr")["basePoint"] == "Pars Fortuna"
    assert defaults("persiandirected")["maxYears"] == 90 and defaults("chart")["lifespanMethod"] == "ptolemy"
