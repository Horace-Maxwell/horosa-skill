"""v3.11.x 上游同步 · 三式 chunk（奇门 / 太乙 / 大六壬 / 金口诀 / 三式合一 及其择日）：选项可达 + 缺省忠实。

每条都写明「旧代码为什么会红」（负向对照，均已在基底 7dc692d 上实跑确认红）：
- 服务层值级用例走 **真实 service + 真实 JS 引擎**，后端响应由 `ReplayClient` 从 live 录制
  （tests/fixtures/sync311_sanshi_live.json，vendored 上游 v3.11.1+ 实例 chart :8877 / java :9977）按
  「端点 + 关键请求字段」回放 —— 旧代码发出的请求（拆补 / 钟表时分量 / 地分子 …）在录制里查不到即红，
  新代码的值级断言（局数 / 值符 / 三传 / 地分 …）的权威出处是那次 live 响应 + vendored 上游引擎；
- 纯 JS 用例直接跑 horosa-core-js（与生产同一条 cli 路径 / vendored 模块）。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_service import CaptureClient, FakeJsClient

import horosa_skill.service as svc
from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
LIVE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sync311_sanshi_live.json"
LR_FIXTURE = CORE_JS / "test" / "fixtures" / "chart_liureng.json"
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

# ─────────────────────────────── 录制 / 回放 ───────────────────────────────

BASE_QM = {"date": "2026-09-24", "time": "10:57", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}
BASE_LR = {"date": "2026-04-04", "time": "21:18", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}
RUNYEAR = {"date": "1990-05-12", "time": "08:30", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
           "gender": True, "guaDate": "2026-04-04", "guaTime": "21:18"}

# 录制场景（scratchpad 录制器按它跑 live 实例并落 fixture；测试按同名场景回放）。
SCENARIOS: dict[str, tuple[str, dict[str, Any]]] = {
    "qimen_default": ("qimen", BASE_QM),
    "qimen_maoshan": ("qimen", {**BASE_QM, "options": {"qijuMethod": "maoshan"}}),
    "qimen_chaibu": ("qimen", {**BASE_QM, "options": {"qijuMethod": "chaibu"}}),
    "qimen_clock": ("qimen", {**BASE_QM, "timeAlg": 1}),
    "qimen_rijia_local": ("qimen", {**BASE_QM, "options": {"paiPanType": 2}}),
    "taiyi_direct": ("taiyi", BASE_QM),
    "taiyi_true_solar": ("taiyi", {**BASE_QM, "options": {"timeBasis": "trueSolar"}}),
    "jinkou_default": ("jinkou", BASE_LR),
    "jinkou_difen_zi": ("jinkou", {**BASE_LR, "diFen": "子"}),
    "jinkou_panshi_yin": ("jinkou", {**BASE_LR, "options": {"panShi": "yin"}}),
    "liureng_default": ("liureng_gods", BASE_LR),
    "liureng_1059_solar": ("liureng_gods", {**BASE_LR, "time": "10:59:30"}),
    "liureng_1059_clock": ("liureng_gods", {**BASE_LR, "time": "10:59:30", "options": {"timeAlg": 1}}),
    "runyear": ("liureng_runyear", RUNYEAR),
    "sanshi_default": ("sanshiunited", BASE_QM),
    "sanshi_taiyi_true_solar": ("sanshiunited", {**BASE_QM, "taiyiTimeBasis": "trueSolar"}),
}

# 回放键：端点 + 决定响应的请求字段。旧代码请求形状不同（起局法 / 时间分量 / 地分 / 端点）即查无录制。
_REPLAY_FIELDS: dict[str, tuple[str, ...]] = {
    "/nongli/time": ("date", "time", "timeAlg", "after23NewDay", "lateZiHourUseNextDay"),
    "/jieqi/year": ("year", "timeAlg"),
    "/qimen/pan": ("year", "month", "day", "hour", "minute", "qijuMethod", "qimenMode"),
    "/taiyi/pan": ("year", "month", "day", "hour", "minute", "style", "tn", "timeBasis"),
    "/liureng/gods": ("date", "time", "timeAlg"),
    "/liureng/runyear": ("date", "time", "guaDate", "guaTime", "guaYearGanZi", "gender"),
    "/jinkou/pan": ("year", "month", "day", "hour", "minute", "difen", "yuejiang", "zhanshi"),
    "/chart": ("date", "time"),
}


def _norm(field: str, value: Any) -> Any:
    if value is None:
        return None
    text = str(value)
    if field in ("date", "guaDate"):
        return text.replace("/", "-")
    if field in ("time", "guaTime") and len(text) == 5:
        return f"{text}:00"
    return text


def replay_key(endpoint: str, payload: dict[str, Any]) -> str:
    endpoint = "/chart" if endpoint == "/" else endpoint
    fields = _REPLAY_FIELDS.get(endpoint, ())
    return json.dumps([endpoint, [_norm(f, payload.get(f)) for f in fields]], ensure_ascii=False)


class ReplayClient(HorosaApiClient):
    """按录制回放后端；查无录制 = 请求形状与 live 验证过的不同 → 抛错（旧代码即红在这里）。"""

    def __init__(self) -> None:
        super().__init__("http://replay")
        self.recordings = json.loads(LIVE_FIXTURE.read_text(encoding="utf-8"))["recordings"]
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def probe(self, endpoint: str = "/common/time", payload: dict | None = None) -> bool:
        return True

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        key = replay_key(endpoint, payload)
        if key not in self.recordings:
            raise AssertionError(f"no live recording for {key} — request shape differs from the live-verified one")
        return json.loads(json.dumps(self.recordings[key]["response"]))


def _settings(tmp_path) -> Settings:
    return Settings(
        server_root="http://127.0.0.1:9999",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )


def _replay_service(tmp_path) -> tuple[HorosaSkillService, ReplayClient]:
    settings = _settings(tmp_path)
    client = ReplayClient()
    return HorosaSkillService(
        settings, client=client, store=MemoryStore(settings), js_client=HorosaJsEngineClient(settings)
    ), client


def _run(service: HorosaSkillService, scenario: str, **overrides: Any):
    tool, payload = SCENARIOS[scenario]
    env = service.run_tool(tool, {**payload, **overrides, "agent_confirmed_settings": True}, save_result=False)
    return env


def _section(text: str, title: str) -> str:
    head = f"[{title}]\n"
    assert head in text, f"missing [{title}] in:\n{text[:1500]}"
    body = text.split(head, 1)[1]
    nxt = body.find("\n[")
    return (body if nxt < 0 else body[:nxt]).strip()


def _ss_section(text: str, title: str) -> str:
    """三式合一快照段（v3.11.x wave-3 起由上游 buildSanShiUnitedSnapshotText 产出，段头是【】）。"""
    head = f"【{title}】\n"
    assert head in text, f"missing 【{title}】 in:\n{text[:1500]}"
    body = text.split(head, 1)[1]
    nxt = body.find("\n【")
    return (body if nxt < 0 else body[:nxt]).strip()


def _node(script: str) -> Any:
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=CORE_JS, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


class RecordingJs(FakeJsClient):
    """FakeJsClient 外加记录每次 JS 调用的 (tool, payload)。"""

    def __init__(self) -> None:
        super().__init__()
        self.runs: list[tuple[str, dict[str, Any]]] = []

    def run(self, tool_name: str, payload: dict[str, object]) -> dict:
        self.runs.append((tool_name, json.loads(json.dumps(payload, ensure_ascii=False, default=str))))
        return super().run(tool_name, payload)


def _fake_service(tmp_path, client: HorosaApiClient | None = None, js: HorosaJsEngineClient | None = None) -> HorosaSkillService:
    settings = _settings(tmp_path)
    return HorosaSkillService(
        settings, client=client or CaptureClient(), store=MemoryStore(settings), js_client=js or FakeJsClient()
    )


def _calls(client, endpoint: str) -> list[dict[str, Any]]:
    return [payload for ep, payload in client.calls if ep == endpoint]


# ═══════════════════════════════ 奇门（F1 / F3）═══════════════════════════════


@requires_node
def test_qimen_default_is_upstream_zhirun_cast_on_true_solar_parts(tmp_path) -> None:
    """F1：缺省起局法 = 上游 DunJiaMain DEFAULT_OPTIONS.qijuMethod 'zhirun'；timeAlg=0（缺省）时 ken 收
    nongli.birth 的真太阳时分量（上游 resolveCalcDateTime / fetchQimenPan）。

    权威：live /qimen/pan（zhirun, 2026-09-24 11:08 真太阳时）→ 局数「阴遁一局中元」值符天柱值使惊门，时柱甲午。
    旧代码：缺省发 chaibu + 钟表时 10:57 → 录制里没有这个请求 → 红（旧盘即「阴遁一局中」却标「定局法：置闰」）。
    """
    service, client = _replay_service(tmp_path)
    env = _run(service, "qimen_default")
    assert env.ok, env.error
    [ken] = _calls(client, "/qimen/pan")
    assert (ken["qijuMethod"], ken["option"], ken["school"]) == ("zhirun", 2, "转盘")
    assert (ken["hour"], ken["minute"], ken["second"]) == (11, 8, 58)
    text = env.data["snapshot_text"]
    pan_type = _section(text, "盘型").splitlines()
    assert "局数：阴遁一局中元" in pan_type and "定局法：置闰" in pan_type
    assert "值符：天柱" in pan_type and "值使：惊门" in pan_type
    # 时柱与九宫同一时辰（此前 ken 按钟表时 10:57=巳时起局，时柱却标真太阳时的午）。
    assert "干支：年丙午 月丁酉 日辛丑 时甲午" in _section(text, "起盘信息")
    assert env.data["route"] == {"local": False, "reasons": []}
    assert env.data["pan"]["source"] == "kinqimen"


@requires_node
def test_qimen_maoshan_and_chaibu_reach_ken_unchanged(tmp_path) -> None:
    """F1：茅山 / 拆补 原样直达 ken（ken 收 茅山=3 / 无闰=4）。旧代码把 maoshan/wurun 压成 chaibu → 红。
    权威：live /qimen/pan maoshan →「阴遁七局上元」值符天辅值使杜门；chaibu →「阴遁一局中」。"""
    service, client = _replay_service(tmp_path)
    env = _run(service, "qimen_maoshan")
    assert env.ok, env.error
    assert _calls(client, "/qimen/pan")[0]["qijuMethod"] == "maoshan"
    pan_type = _section(env.data["snapshot_text"], "盘型").splitlines()
    assert {"局数：阴遁七局上元", "定局法：茅山", "值符：天辅", "值使：杜门"} <= set(pan_type)
    chaibu = _section(_run(service, "qimen_chaibu").data["snapshot_text"], "盘型").splitlines()
    assert {"局数：阴遁一局中", "定局法：拆补"} <= set(chaibu)


@requires_node
def test_qimen_clock_time_alg_keeps_clock_parts(tmp_path) -> None:
    """timeAlg=1（直接时间）：ken 收钟表时分量、农历前置同吃 1。live：10:57=巳时 → 值符天任值使生门、时柱癸巳。"""
    service, client = _replay_service(tmp_path)
    env = _run(service, "qimen_clock")
    assert env.ok, env.error
    [ken] = _calls(client, "/qimen/pan")
    assert (ken["hour"], ken["minute"], ken["qijuMethod"]) == (10, 57, "zhirun")
    assert _calls(client, "/nongli/time")[0]["timeAlg"] == 1
    text = env.data["snapshot_text"]
    assert {"值符：天任", "值使：生门"} <= set(_section(text, "盘型").splitlines())
    assert "干支：年丙午 月丁酉 日辛丑 时癸巳" in _section(text, "起盘信息")


@requires_node
def test_qimen_local_route_skips_ken_and_is_declared(tmp_path) -> None:
    """F3：上游 isQimenLocalRoute —— 日家（paiPanType=2）走本地 calcDunJia，**不打** ken（后端不认这些口径）。
    权威：vendored calcDunJia 对 live 农历/节气种子（含日家要的次年种子）的产物：日家奇门 阴遁三局中元 天英/景门。
    旧代码恒打 ken（且带 chaibu+钟表时）→ 录制里没有 → 红。"""
    service, client = _replay_service(tmp_path)
    env = _run(service, "qimen_rijia_local")
    assert env.ok, env.error
    assert _calls(client, "/qimen/pan") == []
    assert [p["year"] for p in _calls(client, "/jieqi/year")] == [2025, 2026, 2027]
    assert env.data["route"] == {"local": True, "reasons": ["paiPanType"]}
    assert env.data["compute_sources"] == {"pan": "local_route_calcDunJia"}
    pan_type = _section(env.data["snapshot_text"], "盘型").splitlines()
    assert "奇门遁甲方盘（日家奇门）" in pan_type
    assert {"局数：阴遁三局中元", "定局法：节气三元·六十日一局", "值符：天英", "值使：景门"} <= set(pan_type)
    # 依据卡：合法本地路由不许被标成「与声明不一致」（technique_provenance 已声明该算源）。
    assert env.data["technique_card"]["compute"]["matches_declaration"] is True


@requires_node
def test_qimen_route_predicate_mirrors_vendored_isQimenLocalRoute() -> None:
    """Python 路由镜像 vs vendored isQimenLocalRoute（DunJiaCalc.js:1195-1226）逐例对拍 + 本地口径键集锚定。
    旧代码没有这个镜像（恒打 ken）→ AttributeError → 红。上游改判据/加本地口径键，这里当场红。"""
    cases = [
        {}, {"paiPanType": 3}, {"paiPanType": 5}, {"paiPanType": 0}, {"paiPanType": "2"}, {"paiPanType": 4},
        {"paiPanType": 6}, {"school": "转盘"}, {"school": "飞盘"}, {"school": "混合"}, {"qijuMethod": "shuzi"},
        {"qijuMethod": "chaibu"}, {"zhiShiType": 1}, {"zhiShiType": "0"}, {"qijuMethod": "zhirun", "zhirunLeapDays": 10},
        {"qijuMethod": "chaibu", "zhirunLeapDays": 10}, {"godsPreset": "baihu_xuanwu"}, {"godsPreset": "gouchen_zhuque"},
        {"jiGongMode": "kun"}, {"jiGongMode": "gen"}, {"anGanMode": "off"}, {"anGanMode": "a"}, {"kongMarkBoth": True},
        {"kongMarkBoth": False}, {"shiftPalace": 2, "shiftZhiFuMode": "recalc"}, {"shiftPalace": 8, "shiftZhiFuMode": "recalc"},
        {"shiftPalace": 2, "shiftZhiFuMode": "follow"}, {"shiftPalace": -1, "shiftZhiFuMode": "recalc"},
    ]
    res = _node(
        "import { isQimenLocalRoute } from './src/vendor/dunjia/DunJiaCalc.js';\n"
        "import { readFileSync } from 'node:fs';\n"
        f"const cases = {json.dumps(cases, ensure_ascii=False)};\n"
        "const src = readFileSync('./src/vendor/dunjia/DunJiaCalc.js', 'utf8');\n"
        "const body = src.slice(src.indexOf('export function qimenLocalOnlyOverrides'), src.indexOf('export function isQimenLocalRoute'));\n"
        "const keys = [...body.matchAll(/out\\.push\\('(\\w+)'\\)/g)].map((m) => m[1]);\n"
        "console.log(JSON.stringify({ routes: cases.map((c) => isQimenLocalRoute(c)), keys }));"
    )
    assert [bool(svc._qimen_local_route_reasons(c)) for c in cases] == res["routes"]
    # 七组本地口径键：Python 镜像覆盖的集合必须与上游 qimenLocalOnlyOverrides 逐键相同。
    assert set(res["keys"]) == {"zhiShiType", "zhirunLeapDays", "godsPreset", "jiGongMode", "anGanMode",
                                "kongMarkBoth", "shiftZhiFuMode"}


def test_qimen_unknown_options_raise_instead_of_silent_default(tmp_path) -> None:
    """认不出的起局法 / 阴盘缺报数 → 结构化报错。旧代码：未知值静默落拆补、shuzi 缺数静默退节气拆补 → ok=True → 红。"""
    service = _fake_service(tmp_path)
    bad = service.run_tool("qimen", {**BASE_QM, "options": {"qijuMethod": "foo"}, "agent_confirmed_settings": True}, save_result=False)
    assert not bad.ok and bad.error.code == "tool.qimen_invalid_option"
    assert bad.error.details["allowed"] == ["zhirun", "chaibu", "maoshan", "wurun", "shuzi"]
    shuzi = service.run_tool("qimen", {**BASE_QM, "options": {"qijuMethod": "shuzi"}, "agent_confirmed_settings": True}, save_result=False)
    assert not shuzi.ok and shuzi.error.details["field"] == "shuziReportNumber"


def test_qimenzeri_scan_and_display_share_one_validated_option_set(tmp_path) -> None:
    """F3：奇门择日的扫描（本地 calcDunJia，缺省 zhirun）与展示盘（ken）起局法必须同一口径。
    旧代码：扫描 options 不带 qijuMethod（引擎缺省置闰）而展示盘 ken 收 chaibu → 同一次调用两套局 → 红。"""
    client, js = CaptureClient(), RecordingJs()
    service = _fake_service(tmp_path, client=client, js=js)
    env = service.run_tool(
        "qimenzeri",
        {**BASE_QM, "startDate": "2028-04-01", "endDate": "2028-04-02", "agent_confirmed_settings": True,
         "conditions": {"kind": "group", "joiner": "all", "children": [{"kind": "leaf", "type": "door", "params": {"names": ["开门"]}}]}},
        save_result=False,
    )
    assert env.ok, env.error
    scan = next(p for tool, p in js.runs if tool == "qimenzeri" and p.get("action") == "scan")
    assert scan["options"]["qijuMethod"] == "zhirun"
    assert _calls(client, "/qimen/pan")[0]["qijuMethod"] == scan["options"]["qijuMethod"]
    display = next(p for tool, p in js.runs if tool == "qimen")
    assert display["options"]["qijuMethod"] == "zhirun"


def test_qimen_guidance_default_is_literally_the_upstream_default() -> None:
    """F1：guidance 的「星阙默认」必须字面等于上游缺省，且与 service 真正使用的缺省同值。
    旧 guidance：起局法选项只写「星阙默认」无值、service 缺省 chaibu；qimen 还声称 after23NewDay=False 是星阙默认 → 红。"""
    from horosa_skill.agent_guidance import build_agent_guidance

    policy = build_agent_guidance(tool_name="qimen")["tools"]["qimen"]
    default = next(d for d in policy["safe_defaults"] if d["field"] == "qijuMethod")
    assert default["value"] == "zhirun" == svc._qimen_effective_options({})["qijuMethod"]
    question = next(q for q in policy["ask_if_missing"] if q["field"] == "qijuMethod")
    assert question["values"][0] == "zhirun" and "星阙默认" in question["options"][0]
    assert not any(d["field"] == "after23NewDay" and d["value"] is False for d in policy["safe_defaults"])
    assert "isQimenLocalRoute" in policy["options_keys"]["options"]


# ═══════════════════════════════ 太乙（F6）═══════════════════════════════


def _recorded(endpoint: str, payload: dict[str, Any]) -> Any:
    recordings = json.loads(LIVE_FIXTURE.read_text(encoding="utf-8"))["recordings"]
    return json.loads(json.dumps(recordings[replay_key(endpoint, payload)]["response"]))


@requires_node
def test_taiyi_true_solar_time_basis_reaches_ken(tmp_path) -> None:
    """F6：timeBasis=trueSolar 时 ken 按 nongli.birth 真太阳时分量起局（上游 fetchTaiyiPan → resolveCalculationDateTime），
    缺省 direct 按钟表时；[起盘信息] 四柱随基准（上游 buildTaiyiBaziLocal：direct→钟表时柱）。
    权威：live /taiyi/pan —— 10:57 钟表 → 陰遁十八局（理人）主算3客算8；11:08 真太阳 → 陰遁十九局（理天）主算14客算16。
    旧代码：该档既不发也不施加（ken 恒钟表时、请求无 timeBasis）→ 录制里没有 → 红。"""
    service, client = _replay_service(tmp_path)
    solar = _run(service, "taiyi_true_solar")
    assert solar.ok, solar.error
    [ken] = _calls(client, "/taiyi/pan")
    assert (ken["hour"], ken["minute"], ken["timeBasis"]) == (11, 8, "trueSolar")
    info = _section(solar.data["snapshot_text"], "起盘信息").splitlines()
    assert "时间基准：真太阳时" in info and "干支：年丙午 月丁酉 日辛丑 时甲午" in info
    board = _section(solar.data["snapshot_text"], "太乙盘").splitlines()
    assert "局式：陰遁十九局（理天）" in board and "主算：14 客算：16 定算：16" in board

    direct = _run(service, "taiyi_direct")
    assert direct.ok, direct.error
    info = _section(direct.data["snapshot_text"], "起盘信息").splitlines()
    assert "时间基准：直接时间" in info and "干支：年丙午 月丁酉 日辛丑 时癸巳" in info
    board = _section(direct.data["snapshot_text"], "太乙盘").splitlines()
    assert "局式：陰遁十八局（理人）" in board and "主算：3 客算：8 定算：9" in board


@requires_node
def test_taiyi_school_axes_override_the_ken_pan(tmp_path) -> None:
    """F6：太乙流派六轴经 vendored applyTaiyiSchool 施加到 ken 底盘（上游 TaiYiMain.recalc:629 同链）。
    值：live 底盘 + vendored 覆盖层 —— 三基=金镜、计神=逆 → 主算 3→18、客算 8→26、君臣民基 辰/亥/丑 → 酉/辰/丑。
    旧 runTaiyi 从不调 applyTaiyiSchool（只有择日扫描调）→ 两盘逐字相同 → 红（红在值上，不在请求形状上）。"""
    js = HorosaJsEngineClient(_settings(tmp_path))
    nongli = _recorded("/nongli/time", {"date": "2026-09-24", "time": "10:57:00", "timeAlg": 0})
    ken = _recorded("/taiyi/pan", {"year": 2026, "month": 9, "day": 24, "hour": 10, "minute": 57,
                                   "style": 3, "tn": 0, "timeBasis": "direct"})
    base = {**BASE_QM, "time": "10:57:00", "nongli": nongli, "ken_response": ken}
    plain = js.run("taiyi", {**base, "options": {"timeBasis": "direct"}})
    school = js.run("taiyi", {**base, "options": {"timeBasis": "direct", "school": {"sanji": "金镜", "jishen": "逆"}}})
    plain_board = _section(plain["snapshot_text"], "太乙盘").splitlines()
    school_board = _section(school["snapshot_text"], "太乙盘").splitlines()
    assert "主算：3 客算：8 定算：9" in plain_board and not any(line.startswith("流派覆盖") for line in plain_board)
    assert "主算：18 客算：26 定算：9" in school_board
    assert "君臣民基：酉/辰/丑" in school_board
    assert any(line.startswith("流派覆盖：计神=逆、三基起宫=金镜") for line in school_board)
    # 旧 schema 描述的平铺写法（options.jishen）照认；认不出的轴值报错而不静默当缺省。
    flat = js.run("taiyi", {**base, "options": {"jishen": "逆"}})
    assert any(line.startswith("流派覆盖：计神=逆") for line in _section(flat["snapshot_text"], "太乙盘").splitlines())
    bad = js.run("taiyi", {**base, "options": {"school": {"jishen": "nope"}}})
    assert bad["data"]["ok"] is False and bad["data"]["error"]["allowed"] == ["default", "逆", "顺"]


def test_taiyi_invalid_time_basis_raises_and_zeri_school_is_an_object(tmp_path) -> None:
    """F6：timeBasis 认不出报错；TaiyiZeriInput.school 按引擎要的**对象**声明（taiyiZeriScanEngine 展开 o.school）。
    旧代码：未知 timeBasis 静默当直接时间；school 声明成 str → 对象过不了校验、字符串被引擎静默忽略 → 红。"""
    from horosa_skill.schemas.tools import TaiyiZeriInput

    service = _fake_service(tmp_path)
    bad = service.run_tool("taiyi", {**BASE_QM, "options": {"timeBasis": "solar"}, "agent_confirmed_settings": True}, save_result=False)
    assert not bad.ok and bad.error.code == "tool.taiyi_invalid_option"
    model = TaiyiZeriInput(**BASE_QM, school={"jishen": "逆"})
    assert model.school == {"jishen": "逆"}
    assert TaiyiZeriInput.model_json_schema()["properties"]["school"]["anyOf"][0]["type"] == "object"


# ═══════════════════════════════ 金口诀（F7）═══════════════════════════════


@requires_node
def test_jinkou_difen_defaults_to_the_zhanshi_branch(tmp_path) -> None:
    """F7：地分缺省 = 自动取占时支（上游 JinKouMain diFenAuto:true → resolveJinKouDiFen）；十二长生五行缺省随日干。
    权威：/liureng/gods 占时 癸亥 → 地分亥；live /jinkou/pan(difen=亥) → 将神戌（河魁）、用爻将神(+)；戊日 → 土。
    旧代码：缺省发「子」→ 地分子、将神亥（登明）；十二长生五行误传四位旺相五行 → 红（红在值上：旧请求在录制里有）。"""
    service, client = _replay_service(tmp_path)
    env = _run(service, "jinkou_default")
    assert env.ok, env.error
    assert _calls(client, "/jinkou/pan")[0]["difen"] == "亥"
    text = env.data["snapshot_text"]
    brief = _section(text, "金口诀速览").splitlines()
    assert {"地分：亥", "占时：亥", "用爻：将神(+)", "将神：戌（河魁）；（土旺）"} <= set(brief)
    info = _section(text, "起盘信息").splitlines()
    assert "十二长生五行：土" in info and "贵人体系：kinjinkou 贵人歌诀" in info
    assert env.data["route"]["source"] == "kinjinkou"
    # 显式地分照旧直达 ken。
    zi = _run(service, "jinkou_difen_zi")
    assert {"地分：子", "将神：亥（登明）；（水旺）"} <= set(_section(zi.data["snapshot_text"], "金口诀速览").splitlines())


@requires_node
def test_jinkou_non_default_school_routes_to_the_local_engine(tmp_path) -> None:
    """F7：五项流派/盘法任一非缺省 → 上游改走本地 buildJinKouData（ken 不认这五项）。此前 skill 恒用 ken 行覆盖，
    五项全是死开关。权威：vendored buildJinKouData（阴盘）对 live 起课盘 → 用爻人元(+)、贵神未（太常）土囚、贵人六壬法。
    旧代码：照打 ken（difen 子）→ 用爻将神(-)、贵人体系 kinjinkou → 红。"""
    service, client = _replay_service(tmp_path)
    env = _run(service, "jinkou_panshi_yin")
    assert env.ok, env.error
    assert _calls(client, "/jinkou/pan") == []
    assert env.data["route"] == {"schoolsDefault": False, "source": "local", "reason": "school"}
    assert env.data["compute_sources"] == {"jinkou": "local_route_buildJinKouData"}
    brief = _section(env.data["snapshot_text"], "金口诀速览").splitlines()
    assert {"地分：亥", "用爻：人元(+)", "贵神：未（太常）；（土囚）"} <= set(brief)
    assert "贵人体系：六壬法贵人" in _section(env.data["snapshot_text"], "起盘信息").splitlines()
    assert env.data["technique_card"]["compute"]["matches_declaration"] is True


class _SolarGodsClient(CaptureClient):
    """/liureng/gods 的农历带与钟表时不同的真太阳时（10:59:30 钟表 → 11:00:35 真太阳）。"""

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/liureng/gods":
            self.calls.append((endpoint, dict(payload)))
            return {"liureng": {
                "nongli": {"birth": "2026-04-04 11:00:35", "time": "戊午", "dayGanZi": "戊申", "jiedelta": "惊蛰后第30天"},
                "fourColumns": {"year": {"ganzi": "丙午"}, "month": {"ganzi": "辛卯"}, "day": {"ganzi": "戊申"}, "time": {"ganzi": "戊午"}},
            }}
        return super().call(endpoint, payload)


def test_jinkou_time_basis_only_moves_the_ken_path(tmp_path) -> None:
    """F7：timeBasis=trueSolar → ken 收 liureng.nongli.birth 的真太阳时分量（上游 fetchJinKouPan）；本地路由时上游把
    该控件置灰 → 本次不生效且进 warnings。旧代码：ken 恒钟表时、不发 timeBasis、本地路由无从谈起 → 红。"""
    client = _SolarGodsClient()
    service = _fake_service(tmp_path, client=client)
    base = {**BASE_LR, "time": "10:59:30", "agent_confirmed_settings": True}
    env = service.run_tool("jinkou", {**base, "options": {"timeBasis": "trueSolar"}}, save_result=False)
    assert env.ok, env.error
    ken = _calls(client, "/jinkou/pan")[-1]
    assert (ken["hour"], ken["minute"], ken["second"], ken["timeBasis"]) == (11, 0, 35, "trueSolar")
    assert ken["difen"] == "午"  # 自动地分 = 占时支（农历真太阳时柱 戊午）
    service.run_tool("jinkou", base, save_result=False)
    ken = _calls(client, "/jinkou/pan")[-1]
    assert (ken["hour"], ken["minute"], ken["timeBasis"]) == (10, 59, "direct")
    before = len(_calls(client, "/jinkou/pan"))
    local = service.run_tool("jinkou", {**base, "options": {"panShi": "yin", "timeBasis": "trueSolar"}}, save_result=False)
    assert local.ok and len(_calls(client, "/jinkou/pan")) == before
    assert any("timeBasis=trueSolar 本次未生效" in w for w in local.warnings)
    bad = service.run_tool("jinkou", {**base, "options": {"panShi": "up"}}, save_result=False)
    assert not bad.ok and bad.error.code == "tool.jinkou_invalid_option"


# ═══════════════════════════════ 大六壬（F5）═══════════════════════════════


def _lr(tmp_path, **extra: Any) -> dict[str, Any]:
    """真 JS（生产 cli 路径）跑 tools/liureng.js：夹具 = 2026-04-04 21:18 戊申日 癸亥时 戌将（test/fixtures/chart_liureng.json）。"""
    fixture = json.loads(LR_FIXTURE.read_text(encoding="utf-8"))
    payload = {**fixture, "date": "2026-04-04", "time": "21:18:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", **extra}
    return HorosaJsEngineClient(_settings(tmp_path)).run("liureng", payload)


@requires_node
def test_liureng_cast_method_changes_the_courses(tmp_path) -> None:
    """F5：起课法经 vendored buildLiuRengCastOverride/computeQiXY 施加到天地盘（上游 LiuRengMain.js:3974-4082）。
    太岁加时（tsjs）= 太岁午 加 占时亥 → 一课 戊上子、涉害课 壬子→丁未→空寅；正时正将（缺省）→ 元首课 空卯→空寅→癸丑。
    选时法「事发之时=子」→ 月将戌加子 → 重审课 癸丑→辛亥→己酉。旧 liureng.js 自带手写起课核、castMethod 无入口 → 三次同盘 → 红。"""
    plain = _lr(tmp_path)["snapshot_text"]
    tsjs = _lr(tmp_path, options={"castMethod": "tsjs"})["snapshot_text"]
    assert "起课法：正时正将" in _section(plain, "起盘信息") and "起课法：太岁加时" in _section(tsjs, "起盘信息")
    assert _section(plain, "三传").startswith("课式：元首课")
    assert _section(tsjs, "四课").splitlines()[0] == "一课：地盘=戊，天盘=子，贵神=朱雀"
    tsjs_chuan = _section(tsjs, "三传").splitlines()
    assert tsjs_chuan[0] == "课式：涉害课"
    assert tsjs_chuan[3:6] == ["| 初传 | 壬子 | 妻财 | 朱雀 |", "| 中传 | 丁未 | 兄弟 | 白虎 |", "| 末传 | 空寅 | 官鬼 | 贵人 |"]
    xuanshi = _lr(tmp_path, options={"castMethod": "xuanshi", "xuanShiZhi": "子"})["snapshot_text"]
    assert "选时：子时" in _section(xuanshi, "起盘信息")
    assert _section(xuanshi, "三传").splitlines()[0] == "课式：重审课"
    assert "| 初传 | 癸丑 | 兄弟 | 天后 |" in _section(xuanshi, "三传")
    # 需逐课输入的法缺输入 → 报错（上游 computeQiXY 会静默回落正时）。
    missing = _lr(tmp_path, options={"castMethod": "xuanshi"})
    assert missing["data"]["ok"] is False and missing["data"]["error"]["field"] == "xuanShiZhi"


@requires_node
def test_liureng_guiren_three_and_four_are_real_tables(tmp_path) -> None:
    """F5：贵人 3（甲戊兼牛羊）/ 4（干合阳阴贵）走上游 LRConst.GuiRengs 两张新表（LRConst.js:135-169，本 chunk 由
    curated 改 verbatim 才补进来）。戊日夜占：B 派贵人未、C 派贵人未… 天将依次落位。
    旧代码：GUI_RENG_SYSTEMS 只有 0-2，3/4 静默落星占法（贵神朱雀/螣蛇…）→ 红。"""
    b = _lr(tmp_path, guirengType=3)["snapshot_text"]
    c = _lr(tmp_path, guirengType=4)["snapshot_text"]
    assert "贵人体系：甲戊兼牛羊" in _section(b, "起盘信息")
    assert _section(b, "四课").splitlines() == [
        "一课：地盘=戊，天盘=辰，贵神=六合", "二课：地盘=辰，天盘=卯，贵神=勾陈",
        "三课：地盘=申，天盘=未，贵神=贵人", "四课：地盘=未，天盘=午，贵神=螣蛇",
    ]
    assert "贵人体系：干合阳阴贵" in _section(c, "起盘信息")
    assert _section(c, "四课").splitlines()[1:3] == ["二课：地盘=辰，天盘=卯，贵神=朱雀", "三课：地盘=申，天盘=未，贵神=天空"]
    bad = _lr(tmp_path, guirengType=7)
    assert bad["data"]["ok"] is False and bad["data"]["error"]["allowed"] == [0, 1, 2, 3, 4]


@requires_node
def test_vendored_lrconst_is_verbatim_upstream(tmp_path) -> None:
    """LRConst.js curated→verbatim：五张贵人表 + getGuiZi 第 4 参 yinyangSystem（六壬法甲乙丙辛壬癸昼夜互换）。
    旧 curated 副本：GuiRengs 只有 3 张、getGuiZi 只收 3 参（buildLiuRengLayout 传的阳阴系被静默丢弃）→ 红。"""
    res = _node(
        "import * as C from './src/vendor/liureng/LRConst.js';\n"
        "const chart = { nongli: { dayGanZi: '甲子' }, isDiurnal: true };\n"
        "console.log(JSON.stringify({ n: C.GuiRengs.length, danmu: C.getGuiZi(chart, 0, undefined, 'danmu'),"
        " yinyang: C.getGuiZi(chart, 0, undefined, 'yinyang'), other: C.getGuiZi(chart, 2, undefined, 'yinyang') }));"
    )
    # 六壬法甲日：昼贵丑、夜贵未；阳阴系下昼夜互换 → 取夜贵。星占法（2）不受阳阴系影响。
    assert res == {"n": 5, "danmu": "丑", "yinyang": "未", "other": res["other"]}
    assert res["other"] == _node(
        "import * as C from './src/vendor/liureng/LRConst.js';\n"
        "console.log(JSON.stringify(C.getGuiZi({ nongli: { dayGanZi: '甲子' }, isDiurnal: true }, 2)));"
    )


@requires_node
def test_liureng_wuxing_and_doctrine_options_reach_the_snapshot(tmp_path) -> None:
    """F5：十二长生五行（缺省日干五行 戊→土；手选金）、年神序 suigui、土旺衰 huotu、涉害三键都进上游 builder 的对应行。
    权威：vendored buildLiuRengSnapshotText（LiuRengMain.js:4360）+ ZhangSheng 表：土长生申、金长生巳；太岁排轮太阴落辰；
    火土同宫末传丑土相（四季月土旺档为死）。旧 builder：[十二长生] 恒占位、年神/土旺衰只认未文档化的 castOverride → 红。"""
    plain = _lr(tmp_path)["snapshot_text"]
    assert "十二长生五行：土" in _section(plain, "起盘信息")
    assert "| 长生 | 申 |" in _section(plain, "十二长生")
    metal = _lr(tmp_path, options={"wuxing": "金"})["snapshot_text"]
    assert "十二长生五行：金" in _section(metal, "起盘信息") and "| 长生 | 巳 |" in _section(metal, "十二长生")
    assert "太阴：酉" in _section(plain, "年月神煞") and "末传丑土死" in _section(plain, "三传旺衰")
    doctrine = _lr(tmp_path, options={"yearShenShaSort": "suigui", "tuWangShuai": "huotu"})["snapshot_text"]
    assert "（年神＝太岁排轮）" in _section(doctrine, "年月神煞") and "太阴：辰（入课传）" in _section(doctrine, "年月神煞")
    assert "末传丑土相" in _section(doctrine, "三传旺衰")
    sehai = _lr(tmp_path, options={"seHaiMethod": "standard", "seHaiBoundary": "both", "shiRuKe": True})["snapshot_text"]
    assert "涉害取舍：标准深浅两向·两端皆计·始入课单列(十法)" in _section(sehai, "起盘信息")
    unknown = _lr(tmp_path, options={"fenZhouYe": "noon"})
    assert unknown["data"]["ok"] is False and unknown["data"]["error"]["allowed"] == ["chenhun", "maoyou", "yinshen"]


@requires_node
def test_liureng_time_alg_reaches_the_gods_request(tmp_path) -> None:
    """F5：上游 v3.11 LiuRengController 读 timeAlg（缺省真太阳时）。options.timeAlg=1 → /liureng/gods 带 timeAlg=1。
    权威：live /liureng/gods 10:59:30 —— 真太阳时 11:00:35 → 时柱戊午；直接时间 → 丁巳。
    旧代码：timeAlg 不下发 → 两次同为戊午 → 红（旧请求在录制里有，红在值上）。"""
    service, client = _replay_service(tmp_path)
    clock = _run(service, "liureng_1059_clock")
    assert clock.ok, clock.error
    assert _calls(client, "/liureng/gods")[-1]["timeAlg"] == 1
    assert "四柱：丙午年 辛卯月 戊申日 丁巳时" in _section(clock.data["snapshot_text"], "起盘信息")
    solar = _run(service, "liureng_1059_solar")
    assert "timeAlg" not in _calls(client, "/liureng/gods")[-1]
    assert "四柱：丙午年 辛卯月 戊申日 戊午时" in _section(solar.data["snapshot_text"], "起盘信息")
    bad = service.run_tool("liureng_gods", {**BASE_LR, "options": {"timeAlg": 3}, "agent_confirmed_settings": True}, save_result=False)
    assert not bad.ok and bad.error.code == "tool.liureng_invalid_option"
    missing = service.run_tool(
        "liureng_gods", {**BASE_LR, "options": {"castMethod": "yanshu"}, "agent_confirmed_settings": True}, save_result=False
    )
    assert not missing.ok and missing.error.code == "tool.liureng_invalid_option"
    assert missing.error.details["field"] == "yanShuNum"


@requires_node
def test_liureng_runyear_casts_the_ke_at_gua_time_and_reads_the_bare_runyear(tmp_path) -> None:
    """liureng_runyear 此前只打 /liureng/runyear，而该端点只回裸 {age, ageCycle, year}（LiuRengHelper.runYear）——
    没有课盘、runyear 又按包了一层去取 → 四课/三传/行年整段空（live 实测）。上游 = gods（起课档）+ runyear（出生档，
    卦年干支取起课盘年柱）。权威：live —— 起课 2026-04-04 21:18 元首课；1990 生男 行年壬寅 36 岁。旧代码 → 红。"""
    service, client = _replay_service(tmp_path)
    env = _run(service, "runyear")
    assert env.ok, env.error
    gods = _calls(client, "/liureng/gods")[0]
    assert (gods["date"], gods["time"]) == ("2026-04-04", "21:18:00")
    assert _calls(client, "/liureng/runyear")[0]["guaYearGanZi"] == "丙午"
    text = env.data["snapshot_text"]
    assert _section(text, "三传").startswith("课式：元首课")
    assert _section(text, "行年").splitlines() == ["行年干支：壬寅", "年龄：36岁", "性别：男"]
    assert "日期：2026-04-04 21:18" in _section(text, "起盘信息") and "问测人性别：男" in _section(text, "起盘信息")


@requires_node
def test_liureng_cast_methods_in_guidance_are_anchored_to_vendored_QI_METHODS() -> None:
    """options_keys 里的 26 起课法键序必须与 vendored QI_METHODS 逐一相同（手抄清单会漂移）。旧代码无此表 → 红。"""
    from horosa_skill.agent_guidance import LIURENG_CAST_METHODS, build_agent_guidance

    keys = _node(
        "import { QI_METHODS } from './src/vendor/liureng/LiuRengMain.js';\n"
        "console.log(JSON.stringify(QI_METHODS.map((m) => m.key)));"
    )
    assert [k for k, _ in LIURENG_CAST_METHODS] == keys and len(keys) == 26
    text = build_agent_guidance(tool_name="liureng_gods")["tools"]["liureng_gods"]["options_keys"]["options"]
    assert all(f"{k}=" in text for k in keys)


# ═══════════════════════════════ 三式合一 ═══════════════════════════════


@requires_node
def test_sanshiunited_forwards_the_liureng_layer_options(tmp_path) -> None:
    """F5：三式合一六壬层吃上游 SANSHI_PAGE_SETTINGS 六壬键 + guireng。辛丑日（阳阴系会互换的日干）live 课盘：
    缺省星占法 一课贵神天空；六壬法（0）→ 太阴；六壬法+阳阴系 → 昼夜互换回天空。
    旧代码：liureng_options 无入口（被静默忽略）→ 三次都是天空 → 红。"""
    service, _client = _replay_service(tmp_path)
    first = lambda env: _ss_section(env.data["snapshot_text"], "大六壬").splitlines()[0]  # noqa: E731
    assert first(_run(service, "sanshi_default")) == "一课：辛申天空"
    liuren = _run(service, "sanshi_default", liureng_options={"guirengType": 0})
    assert liuren.ok, liuren.error
    assert first(liuren) == "一课：辛申太阴"
    swapped = _run(service, "sanshi_default", liureng_options={"guirengType": 0, "yinyangSystem": "yinyang"})
    assert first(swapped) == "一课：辛申天空"


def test_sanshiunited_rejects_what_upstream_locks(tmp_path) -> None:
    """上游三式合一锁正时正将（pickSanshiLiurengCastOpts），时间算法为三盘共享；子盘口径认不出 → 报错而非占位残盘。
    旧代码：liureng_options 整体被忽略 → ok=True → 红。"""
    service = _fake_service(tmp_path)
    base = {**BASE_QM, "agent_confirmed_settings": True}
    cast = service.run_tool("sanshiunited", {**base, "liureng_options": {"castMethod": "tsjs"}}, save_result=False)
    assert not cast.ok and cast.error.code == "tool.sanshiunited_invalid_option"
    tz = service.run_tool("sanshiunited", {**base, "liureng_options": {"timeAlg": 1}}, save_result=False)
    assert not tz.ok and tz.error.details["field"] == "liureng_options.timeAlg"
    bad = service.run_tool("sanshiunited", {**base, "qimen_options": {"qijuMethod": "foo"}}, save_result=False)
    assert not bad.ok and bad.error.code == "tool.qimen_invalid_option"


@requires_node
def test_sanshiunited_taiyi_time_basis(tmp_path) -> None:
    """v3.11 三式太乙区 taiyiTimeBasis（SanShiUnitedMain.js:446/2326，缺省 direct、不随盘 timeAlg 串改）。
    权威：live /taiyi/pan 真太阳时 11:08 → 陰遁十九局（理天）主算14；缺省 → 陰遁十八局（理人）。旧代码 → 红。"""
    service, client = _replay_service(tmp_path)
    env = _run(service, "sanshi_taiyi_true_solar")
    assert env.ok, env.error
    assert _calls(client, "/taiyi/pan")[-1]["timeBasis"] == "trueSolar"
    board = _ss_section(env.data["snapshot_text"], "太乙").splitlines()
    assert "局式：陰遁十九局（理天）" in board and "主算：14 客算：16 定算：16" in board
    default = _ss_section(_run(service, "sanshi_default").data["snapshot_text"], "太乙").splitlines()
    assert "局式：陰遁十八局（理人）" in default
    # 同一张三式盘里奇门层按缺省置闰 + 真太阳时分量出盘（与独立 qimen 同源）。
    assert "局数：阴遁一局中元" in _ss_section(_run(service, "sanshi_default").data["snapshot_text"], "概览")


def test_sanshi_chunk_guidance_publishes_option_vocabularies() -> None:
    """词表住 guidance（tools/list 字节预算）：七个工具都回报 options_keys；太乙「星阙默认」= 直接时间而非 timeAlg。
    旧 guidance：无 options_keys、太乙把 timeAlg=0 标为星阙默认 → 红。"""
    from horosa_skill.agent_guidance import build_agent_guidance

    for tool in ("qimen", "qimenzeri", "taiyi", "taiyizeri", "jinkou", "liureng_gods", "liureng_runyear", "sanshiunited"):
        assert build_agent_guidance(tool_name=tool)["tools"][tool].get("options_keys"), tool
    taiyi = build_agent_guidance(tool_name="taiyi")["tools"]["taiyi"]
    assert {"field": "options.timeBasis", "value": "direct"}.items() <= next(
        d for d in taiyi["safe_defaults"] if d["field"] == "options.timeBasis"
    ).items()
    assert not any(d["field"] == "timeAlg" for d in taiyi["safe_defaults"])
    jinkou = build_agent_guidance(tool_name="jinkou")["tools"]["jinkou"]
    assert next(q for q in jinkou["ask_if_missing"] if q["field"] == "diFen")["values"][0] == "auto"
