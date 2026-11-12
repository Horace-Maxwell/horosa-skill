"""上游 v3.13.1（Horosa-Public 965af0f4 → 06f25f21）命理 chunk 同步：八字天医口径 / 晚子时·时间算法四柱 / 八字择时
内嵌八字页键 / 日子馆当事人时区 / 紫微巨机三格。

每条写明上游出处（文件:行）、旧代码为什么会红，以及实跑过的负向对照。真 node 引擎的用例直接跑 horosa-core-js
（与生产同一 cli 路径）；live 用例只在显式点名的 vendored 实例上跑（test_local_js_tools 的门禁）。
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from horosa_skill.agent_guidance import TOOL_GUIDANCE
from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools import BaZiBirthInput, BaZiDirectInput, BaziZeriInput
from horosa_skill.service import HorosaSkillService

PKG = Path(__file__).resolve().parents[1]
CORE_JS_SRC = PKG / "horosa-core-js" / "src"
_UPSTREAM_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
UPSTREAM_UI = Path(_UPSTREAM_ROOT) / "Horosa-Web" / "astrostudyui" / "src" if _UPSTREAM_ROOT else None
requires_upstream = pytest.mark.skipif(
    UPSTREAM_UI is None or not UPSTREAM_UI.is_dir(), reason="[upstream-checkout] HOROSA_SOURCE_ROOT (upstream checkout) not set"
)
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")


class _NoBackend(HorosaApiClient):
    """八字走本地引擎：任何远端调用都是接线错误。"""

    def __init__(self) -> None:
        super().__init__("http://fake")

    def probe(self, endpoint: str = "/common/time", payload: dict | None = None) -> bool:
        return True

    def call(self, endpoint: str, payload: dict) -> dict:
        raise AssertionError(f"unexpected backend call {endpoint}")


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "runtime",
    )
    return HorosaSkillService(settings, client=_NoBackend(), store=MemoryStore(settings))


def _run(service: HorosaSkillService, tool: str, payload: dict) -> Any:
    env = service.run_tool(tool, {**payload, "agent_confirmed_settings": True}, save_result=False)
    assert env.ok is True, env.error
    return env


def _section(text: str, title: str) -> str:
    head = f"[{title}]\n"
    assert head in text, f"missing [{title}]"
    body = text.split(head, 1)[1]
    nxt = body.find("\n[")
    return (body if nxt < 0 else body[:nxt]).strip()


def _node(module: str, body: str, *args: str) -> Any:
    from node_esm import run_node_esm

    script = (
        "import(process.argv[1]).then(async (m) => { const argv = process.argv.slice(2);"
        f" const out = await (async () => {{ {body} }})(); process.stdout.write(JSON.stringify(out)); }});"
    )
    return json.loads(run_node_esm(script, CORE_JS_SRC / module, *args))


# 寅月（庚寅）生人：协纪天医 = 戌、地医 = 辰；子平天医 = 丑（baziShenShaLocal.js:476-480 / baziTianyiSchool.test.js）。
_BAZI = {"date": "1990-02-20", "time": "08:30:00", "zone": "+08:00", "lat": "39n54", "lon": "116e23", "gender": 1}
_XIEJI_LINE = "天医口径：协纪辨方书（正月起戌顺行，地医为其对冲）"
_ZIPING_LINE = "天医口径：子平（月支退一位，无地医）"


# ── 八字·天医口径（BaZi.js:437 / :1086 genParams；baziLunarLocal.js:1256-1258）──────────────────────────

@requires_node
def test_bazi_tianyi_school_reaches_engine_and_snapshot(tmp_path: Path) -> None:
    """v3.13.1 新增「天医口径」：xieji（缺省，天医正月起戌顺行、地医对冲）| ziping（月支退一位、无地医）。
    旧代码：runner 不认 tianyiSchool → 给了 ziping 也按协纪查神煞（辰时柱照挂「地医」），快照也无「天医口径」行。
    负向对照：mingli.py 去掉「非缺省才进 params」那三行（params 永不带 tianyiSchool）→ ziping 断言红（实跑过）。"""
    service = _service(tmp_path)
    default = _run(service, "bazi_birth", _BAZI)
    ziping = _run(service, "bazi_birth", {**_BAZI, "tianyiSchool": "ziping"})
    d_sec = _section(default.data["snapshot_text"], "神煞（四柱与三元）")
    z_sec = _section(ziping.data["snapshot_text"], "神煞（四柱与三元）")
    # 首行 = 上游 BaZi.js:437 逐字；缺省协纪也恒印。
    assert d_sec.splitlines()[0] == _XIEJI_LINE
    assert z_sec.splitlines()[0] == _ZIPING_LINE
    # 时柱辰（08:30 = 辰时）：协纪挂「地医」，子平无地医。
    d_time = next(line for line in d_sec.splitlines() if line.startswith("时柱："))
    z_time = next(line for line in z_sec.splitlines() if line.startswith("时柱："))
    assert "地医" in d_time and "地医" not in z_time
    assert all("地医" not in line for line in z_sec.splitlines()[1:])   # 首行口径说明本身含「无地医」
    # 技法依据卡回显（结果敏感设置）。
    card = ziping.data["technique_card"]["settings"]
    assert card["tianyiSchool"]["value"] == "ziping" and card["tianyiSchool"]["label"] == "天医口径"


def test_bazi_tianyi_school_forwarded_only_when_non_default(tmp_path: Path) -> None:
    """「缺省不发 = 零回归」：协纪 / 缺省 / 认不出的值都不进起盘参数（引擎与快照对缺键同按协纪）；认不出进 warnings。"""
    service = _service(tmp_path)
    for payload in ({}, {"tianyiSchool": "xieji"}, {"tianyiSchool": ""}):
        params, _ = service._bazi_params({**_BAZI, **payload})
        assert "tianyiSchool" not in params
    params, _ = service._bazi_params({**_BAZI, "tianyiSchool": "ziping"})
    assert params["tianyiSchool"] == "ziping"
    env = _run(service, "bazi_birth", {**_BAZI, "tianyiSchool": "bogus"})
    assert any("tianyiSchool" in w for w in env.warnings)
    assert _section(env.data["snapshot_text"], "神煞（四柱与三元）").splitlines()[0] == _XIEJI_LINE


def test_bazi_tianyi_school_declared_hidden_and_documented() -> None:
    """MCP 扁平面只认已声明键：未声明 = 静默丢键。新键走 _unadvertised（不吃 tools/list 预算），词表进 guidance。"""
    for model in (BaZiBirthInput, BaZiDirectInput):
        extra = model.model_fields["tianyiSchool"].json_schema_extra or {}
        assert extra.get("x-horosa-hidden") is True
    assert HorosaSkillService._BAZI_OPTION_VOCAB["tianyiSchool"] == ("xieji", "ziping")
    assert HorosaSkillService._BAZI_OPTION_DEFAULTS["tianyiSchool"] == "xieji"
    for tool in ("bazi_birth", "bazi_direct"):
        assert "ziping" in TOOL_GUIDANCE[tool]["options_keys"]["tianyiSchool"]


@requires_upstream
def test_bazi_tianyi_vocab_matches_upstream_domains() -> None:
    """值域逐值对上游 baziStoredOpt.js BAZI_OPT_DOMAINS.tianyiSchool（八字页左栏 / 挂载齿轮同表）。
    负向对照：把 _BAZI_OPTION_VOCAB 的 tianyiSchool 改成 ("xieji",) → 红（实跑过）。"""
    src = (UPSTREAM_UI / "utils" / "baziStoredOpt.js").read_text(encoding="utf-8")
    m = re.search(r"tianyiSchool:\s*\[([^\]]*)\]", src)
    assert m
    upstream = tuple(re.findall(r"'([^']+)'", m.group(1)))
    assert HorosaSkillService._BAZI_OPTION_VOCAB["tianyiSchool"] == upstream
    assert HorosaSkillService._BAZI_OPTION_DEFAULTS["tianyiSchool"] == upstream[0]


@requires_upstream
def test_bespoke_bazi_snapshot_builder_matches_upstream_body() -> None:
    """bespoke vendor/bazi/baziSnapshot.js 的 buildBaziSnapshotText 函数体与上游 BaZi.js 同名函数逐字相同
    （derived_sha256 只管「源动了没」，本条管「抽出的闭包确实跟上了」）。
    负向对照：删掉 vendored 文件里新增的「天医口径」那一行 → 红（实跑过）。"""
    def body(text: str) -> str:
        start = text.index("function buildBaziSnapshotText(params, result){")
        return text[start: text.index("\n}\n", start) + 3]

    vendored = (CORE_JS_SRC / "vendor" / "bazi" / "baziSnapshot.js").read_text(encoding="utf-8")
    upstream = (UPSTREAM_UI / "components" / "cntradition" / "BaZi.js").read_text(encoding="utf-8")
    assert body(vendored) == body(upstream)


# ── 八字·晚子时与时间算法改四柱（release note「改了四柱真跟着变」）──────────────────────────────────

@requires_node
def test_bazi_late_zi_and_time_alg_switches_change_pillars(tmp_path: Path) -> None:
    """上游 v3.13.1 修的是八字页左栏三键拆进覆盖层后重取漏带覆盖层（BaZi.js:974-996，UI 层死开关）。skill 无覆盖层，
    三键直进 genParams —— 本条钉住 skill 侧这三个开关确实改四柱（23:30 钟表时、东经 120°）：
    after23NewDay 换日柱、lateZiHourUseNextDay 换时干、timeAlg（真太阳时 vs 直接时间）换时支。
    负向对照：mingli.py 把 after23NewDay 恒写 1 → 第二条断言红（实跑过）。"""
    service = _service(tmp_path)
    base = {**_BAZI, "time": "23:30:00", "lon": "120e00"}

    def pillars(**kw: Any) -> list[str]:
        four = _run(service, "bazi_birth", {**base, **kw}).data["bazi"]["fourColumns"]
        return [four[k]["stem"]["cell"] + four[k]["branch"]["cell"] for k in ("year", "month", "day", "time")]

    assert pillars(timeAlg=1) == ["庚午", "戊寅", "丁巳", "庚子"]                          # 出厂 1/1：23 点换日、时干按次日
    assert pillars(timeAlg=1, after23NewDay=0) == ["庚午", "戊寅", "丙辰", "庚子"]         # 24 点换日：日柱回当日
    assert pillars(timeAlg=1, lateZiHourUseNextDay=0) == ["庚午", "戊寅", "丁巳", "戊子"]  # 时干按当日（丙）起子
    # 东经 100° 真太阳时 23:30 → 约 22:00（经度差 −80 分 + 二月时差约 −14 分，亥时），直接时间仍是子时。
    four_true = pillars(timeAlg=0, lon="100e00")
    four_clock = pillars(timeAlg=1, lon="100e00")
    assert four_true[3][1] == "亥" and four_clock[3][1] == "子"


# ── 八字择时·内嵌八字页三键（zeriPageCalibre.js:82-85 / baziZeriScanEngine.js:53 / BaziZeriMain.js:243-251）──

_ZERI = {
    "date": "2026-02-20", "time": "00:00:00", "zone": "+08:00", "lat": "39n54", "lon": "116e23",
    "startDate": "2026-02-20", "startTime": "00:00", "endDate": "2026-02-20", "endTime": "23:59", "timeAlg": 1,
    # 寅月：时柱见天医 —— 协纪 = 戌时、子平 = 丑时。
    "conditions": {"kind": "group", "joiner": "all", "children": [
        {"kind": "leaf", "type": "shensha_has", "params": {"values": ["天医"], "pillars": ["time"]}}]},
}


def _capture_base_calls(service: HorosaSkillService) -> list[tuple[str, dict]]:
    seen: list[tuple[str, dict]] = []
    original = service.run_tool

    def spy(tool_name: str, payload: dict, **kwargs: Any) -> Any:
        if tool_name == "bazi_birth":
            seen.append((tool_name, dict(payload)))
            return SimpleNamespace(ok=True, data={"snapshot_text": ""}, error=None)
        return original(tool_name, payload, **kwargs)

    service.run_tool = spy  # type: ignore[method-assign]
    return seen


def _hit_hours(env: Any) -> list[str]:
    return [str(row.get("pick") or row.get("start"))[11:13] for row in env.data["intervals"]]


@requires_node
def test_bazizeri_tianyi_school_drives_scan_and_display_chart(tmp_path: Path) -> None:
    """v3.13.1 BAZI_PAGE_SCAN_KEYS 加 tianyiSchool：扫描按它查神煞条件（makeBaziZeriEvalCtx），点结果行按冻结值回写
    内嵌八字页 → 展示盘同口径。旧代码：(1) 顶层 tianyiSchool / southMonth / minggongMethod 不进扫描 options（只透传给
    展示盘）；(2) options 里给的这三键只改扫描、展示盘按缺省 —— 同一结果两套口径。
    负向对照：zeri.py 的 bazizeri 分支去掉 page_options 回写（`out.update(...)` 那行）→ options 写法的展示盘断言红；
    top_keys 去掉三键 → 顶层写法的命中时辰断言红（均实跑过）。"""
    service = _service(tmp_path)
    seen = _capture_base_calls(service)
    xieji = _run(service, "bazizeri", _ZERI)
    assert _hit_hours(xieji) and set(_hit_hours(xieji)) <= {"19", "20"}          # 戌时
    assert seen[-1][1]["tianyiSchool"] == "xieji" and seen[-1][1]["southMonth"] == "none"
    assert seen[-1][1]["minggongMethod"] == "tongxing"
    # 顶层写法 → 扫描吃到（丑时）+ 展示盘同口径
    top = _run(service, "bazizeri", {**_ZERI, "tianyiSchool": "ziping"})
    assert _hit_hours(top) and set(_hit_hours(top)) <= {"01", "02"}
    assert seen[-1][1]["tianyiSchool"] == "ziping"
    # options 写法 → 扫描吃到 + 展示盘回写（options 优先于顶层）
    opt = _run(service, "bazizeri", {**_ZERI, "tianyiSchool": "xieji",
                                     "options": {"tianyiSchool": "ziping", "minggongMethod": "shufa"}})
    assert set(_hit_hours(opt)) <= {"01", "02"}
    assert (seen[-1][1]["tianyiSchool"], seen[-1][1]["minggongMethod"]) == ("ziping", "shufa")


def test_bazizeri_page_keys_declared_hidden() -> None:
    for key in ("southMonth", "minggongMethod", "tianyiSchool"):
        extra = BaziZeriInput.model_fields[key].json_schema_extra or {}
        assert extra.get("x-horosa-hidden") is True, key


@requires_node
def test_bazizeri_python_top_keys_match_vendored_page_scan_keys() -> None:
    """runner 顶层双读的三键 = vendored zeriPageCalibre.BAZI_PAGE_SCAN_KEYS（JS 单源；Python 只这一处列名）。
    负向对照：vendored 表多一键时本条红（以 zeri.py 少写 tianyiSchool 模拟，实跑过）。"""
    keys = _node("vendor/divination/zeri/zeriPageCalibre.js", "return m.BAZI_PAGE_SCAN_KEYS;")
    src = (PKG / "src" / "horosa_skill" / "service" / "runners" / "zeri.py").read_text(encoding="utf-8")
    m = re.search(r'if tool_name == "bazizeri":\n(?:\s*#[^\n]*\n)*\s*top_keys = \(\*top_keys, ([^)]*)\)', src)
    assert m
    assert re.findall(r'"([^"]+)"', m.group(1)) == keys


# ── 日子馆·当事人时区（RiziMain.js:86-90；riziPersonZone.test.js）────────────────────────────────────

@requires_node
def test_rizi_person_bazi_follows_person_zone() -> None:
    """2024 立春 = 北京时间 02-04 16:27；当地 16:00 在东八区是立春前（癸卯年），东二区是北京 22:00、立春后（甲辰年）。
    旧代码：calendarExtras.js 不下发当事人 zone → 一律东八区，[当事人八字] 年命恒癸卯。
    负向对照：calendarExtras.js 去掉 zone 展开那行 → 东二区断言红（实跑过）。"""
    def year_line(zone: str | None) -> str:
        person = {"name": "甲", "role": "self", "date": "2024-02-04", "time": "16:00:00", "gender": 1}
        if zone:
            person["zone"] = zone
        text = _node(
            "tools/calendarExtras.js",
            "return m.runCalendarExtras({year: 2026, month: 6, day: 1, rizi: {event: 'marriage', year: 2026,"
            " persons: [JSON.parse(argv[0])]}}).text;",
            json.dumps(person, ensure_ascii=False),
        )
        return _section(text, "当事人八字")

    assert "癸卯" in year_line(None) and "癸卯" in year_line("+08:00")
    east2 = year_line("+02:00")
    assert "甲辰" in east2 and "癸卯" not in east2


# ── 紫微·巨机三格（ziweige.json / ZiWeiPattern.java:241-247 / ziweiPatterns.js:114-120）─────────────

@requires_node
def test_ziwei_juji_patterns_split_in_vendored_table() -> None:
    """「巨机卯酉」拆成 巨机同临（富贵·卯·乙辛己丙年）/ 巨机居酉（破格）/ 巨机破荡(女命)；旧名经 expandLegacyGeju
    展开，存过旧名的择日条件不静默落空。vendored 表与条件类已逐字同步，此处钉 skill 运行时确实读到新表。"""
    out = _node(
        "vendor/divination/zeri/ziweiZeriConditionTypes.js",
        "return [m.expandLegacyGeju(['巨机卯酉']), m.ZIWEI_CONDITION_TYPES.geju_hit.label];",
    )
    assert out[0] == ["巨机居酉", "巨机破荡(女命)"]
    assert re.fullmatch(r"格局命中\(\d+ 格\)", out[1]) and out[1] != "格局命中(51 格)"


# 闸模块导入失败就该红：旧写法 except → `pytest.mark.skip("gate unavailable")`，live lane 上整组静默放行（C-18 第 2 项）。
from test_local_js_tools import make_service, requires_runtime  # noqa: E402


@requires_runtime
def test_ziwei_juji_patterns_live(tmp_path: Path) -> None:
    """live（v3.13.1 jar）：2026-02-17 22:00（丙午年、寅月亥时 → 命宫卯、天机巨门同守）男命命中「巨机同临」、
    女命另中「巨机破荡(女命)」；2026-02-23 10:00（命宫酉）命中「巨机居酉」。旧 jar / 旧表只出「巨机卯酉」。"""
    service = make_service(tmp_path)
    base = {"zone": "+08:00", "lat": "39n54", "lon": "116e23", "timeAlg": 1, "agent_confirmed_settings": True}

    def patterns(date: str, time: str, male: bool) -> str:
        env = service.run_tool("ziwei_birth", {**base, "date": date, "time": time, "gender": male}, save_result=False)
        assert env.ok, env.error
        return _section(env.data["snapshot_text"], "命中格局")

    male_mao = patterns("2026-02-17", "22:00:00", True)
    female_mao = patterns("2026-02-17", "22:00:00", False)
    assert "巨机同临" in male_mao and "巨机破荡(女命)" not in male_mao
    assert "巨机同临" in female_mao and "巨机破荡(女命)" in female_mao
    assert "巨机居酉" in patterns("2026-02-23", "10:00:00", True)
    assert "巨机卯酉" not in male_mao + female_mao
