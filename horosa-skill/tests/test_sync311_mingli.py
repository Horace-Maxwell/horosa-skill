"""v3.11.x 上游同步 · 命理 chunk（八字 / 紫微 / 宿占 / 通书 / 农历·节气 / 输入层北京时间）的回归与值级金标。

每条都写明「旧代码为什么会红」（负向对照）。真 node 引擎的用例直接跑 horosa-core-js（与生产同一条 cli 路径、
同一批 vendored 模块）；服务层用例用 test_service 的 HTTP 桩（CaptureClient 抓发往后端的载荷）+ 真 JS 引擎。
期望值的权威出处写在注释里（上游文件:行、公开历法事实、或与 Java 独立实现的交叉核对）。
live 用例（@requires_runtime / @requires_chart）只在显式点名的实例上跑（test_local_js_tools 的门禁）。
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path

import pytest
from test_service import CaptureClient, FakeClient, FakeJsClient

from horosa_skill.agent_guidance import TOOL_GUIDANCE, build_agent_guidance
from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.errors import ToolValidationError
from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools import (
    BaZiBirthInput,
    JieQiYearInput,
    LiuRengGodsInput,
    NongliTimeInput,
    SuZhanInput,
    ZiWeiBirthInput,
)
from horosa_skill.service import HorosaSkillService

CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
_CHART_FIXTURE = CORE_JS / "test" / "fixtures" / "chart_traditional.json"


def _settings(tmp_path) -> Settings:
    return Settings(
        server_root="http://127.0.0.1:9999",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )


def _real_js(tmp_path) -> HorosaJsEngineClient:
    return HorosaJsEngineClient(_settings(tmp_path))


class _HybridJs(FakeJsClient):
    """指定工具走真 node 引擎，其余沿用 test_service 的带内容桩。"""

    def __init__(self, real: HorosaJsEngineClient, tools: set[str]) -> None:
        super().__init__()
        self._real = real
        self._tools = tools

    def run(self, tool_name: str, payload: dict[str, object]) -> dict:
        if tool_name in self._tools:
            return self._real.run(tool_name, payload)
        return super().run(tool_name, payload)


def _service(tmp_path, *, client=None, real: set[str] | None = None) -> HorosaSkillService:
    settings = _settings(tmp_path)
    js = _HybridJs(_real_js(tmp_path), real) if real else FakeJsClient()
    return HorosaSkillService(settings, client=client or CaptureClient(), store=MemoryStore(settings), js_client=js)


def _section(text: str, title: str) -> str:
    head = f"[{title}]\n"
    assert head in text, f"missing [{title}] in:\n{text[:1500]}"
    body = text.split(head, 1)[1]
    nxt = body.find("\n[")
    return (body if nxt < 0 else body[:nxt]).strip()


def _row(text: str, label: str) -> list[str]:
    """GFM 表里以 `| label |` 开头的那一行，按列切开（去首尾空列）。"""
    line = next((ln for ln in text.splitlines() if ln.startswith(f"| {label}")), "")
    return [cell.strip() for cell in line.strip().strip("|").split("|")] if line else []


_SH = {"zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True}


# ════════════════════════════════════ F2 · 日界缺省 ════════════════════════════════════

def test_after23_schema_defaults_are_unset_not_false() -> None:
    """上游出厂缺省 1=23 点换日（utils/dayBoundary.js:39-45 defaultAfter23NewDay）。旧 schema 硬缺省 False 且
    model_dump 会把它序列化下发 → Java 读成 0（live 实测 false→辛丑、缺省→壬寅）。旧代码：四个模型缺省 False → 红。"""
    for model in (ZiWeiBirthInput, BaZiBirthInput, LiuRengGodsInput, NongliTimeInput):
        assert model.model_fields["after23NewDay"].default is None, model.__name__


def test_after23_not_sent_to_java_when_unset_and_explicit_zero_reaches_ken(tmp_path) -> None:
    """缺省不发送（Java 缺省 1 = 上游出厂缺省）；显式 0 必须全链到位，含金口诀的 ken 载荷
    （上游 JinKouCalc.js:2823-2825 两键齐发）。旧代码：nongli/liureng/ziwei 发 False；jinkou 从不给 ken 发日界 → 红。"""
    client = CaptureClient()
    service = _service(tmp_path, client=client)
    base = {"date": "2026-05-27", "time": "23:30:00", **_SH}
    for tool, endpoint in (("nongli_time", "/nongli/time"), ("liureng_gods", "/liureng/gods"), ("ziwei_birth", "/ziwei/birth")):
        client.calls.clear()
        assert service.run_tool(tool, dict(base), save_result=False).ok
        sent = [p for ep, p in client.calls if ep == endpoint]
        assert sent and "after23NewDay" not in sent[0], f"{tool} 缺省时不得下发日界（旧代码下发 False）"
    client.calls.clear()
    assert service.run_tool("jinkou", {**base, "after23NewDay": 0, "diFen": "子"}, save_result=False).ok
    ken = [p for ep, p in client.calls if ep == "/jinkou/pan"]
    assert ken and ken[0].get("after23NewDay") == 0, "显式 after23NewDay=0 必须抵达 ken /jinkou/pan"
    lr = [p for ep, p in client.calls if ep == "/liureng/gods"]
    assert lr and lr[0].get("after23NewDay") in (0, False), "金口诀的六壬前置与 ken 同口径"


def test_guidance_names_upstream_day_boundary_default() -> None:
    """agent_guidance 的 safe_defaults 曾把 False 标成「星阙默认」（agent_guidance.py:415/579/1008/1505/1521）→ 红。"""
    seen = {}
    for tool, policy in TOOL_GUIDANCE.items():
        for item in policy.get("safe_defaults", []):
            if item.get("field") == "after23NewDay":
                seen[tool] = item
                assert item["value"] == 1, (tool, item)   # 全表：没有任何技法再把 0/False 标成星阙默认
    for tool in ("bazi_birth", "bazi_direct", "ziwei_birth", "liureng_gods", "qimen"):
        assert "23 点换日" in seen[tool]["meaning"], (tool, seen.get(tool))


def test_technique_card_echoes_effective_day_boundary_default(tmp_path) -> None:
    """缺省不再下发后，卡片仍须回显引擎实际按 1 起算（AGENTS §10：藏起这一行 = 藏起两次结果为何不同）。"""
    service = _service(tmp_path)
    env = service.run_tool("nongli_time", {"date": "2026-05-27", "time": "23:30:00", **_SH}, save_result=False)
    settings = env.data["technique_card"]["settings"]
    assert settings["after23NewDay"] == {"label": "晚子时·日柱开关（缺省）", "value": 1}


# ════════════════════════════════════ F9 · 八字本地优先 ════════════════════════════════════

@requires_node
def test_bazi_defaults_follow_upstream_page_genparams(tmp_path) -> None:
    """上游八字页主路径 = 本地引擎（BaZi.js:716-755）+ genParams 缺省（:961-985 / techniqueMountSettings.js:1692-1740）：
    godKeyPos 年、命宫通行版、起运精确、日界 1/1。旧代码走 Java /bazi/birth：godKeyPos 缺省「年日」、命宫子平数法、
    快照是 Python port（无纳音长生列、无命宫起法标注）→ 红。

    值级金标 1990-05-15 10:30 上海（真太阳时 10:39:33）：四柱 庚午 辛巳 庚辰 辛巳（公开万年历：1990-05-15 = 庚辰日，
    立夏后巳月，10:30 巳时）；命宫通行版 = 癸未，子平数法 = 辛巳（与 Java /bazi/birth 缺省 shufa 同盘 live 实测一致）。
    """
    client = CaptureClient()
    service = _service(tmp_path, client=client, real={"bazi_local"})
    env = service.run_tool("bazi_birth", {"date": "1990-05-15", "time": "10:30:00", "zone": "+08:00", "lat": "31n14",
                                          "lon": "121e28", "gender": 1, "agent_confirmed_settings": True}, save_result=False)
    assert env.ok, env.error
    assert not [ep for ep, _ in client.calls if ep.startswith("/bazi/")], "可靠域内不得打 Java /bazi/*"
    assert env.data["compute_sources"] == {"bazi": "lunar-local"}
    assert env.data["technique_card"]["compute"]["matches_declaration"] is True
    text = env.data["snapshot_text"]
    four = _section(text, "四柱与三元")
    assert four.splitlines()[0] == "| 柱 | 干支 | 藏干 | 十神 | 纳音 | 纳音长生 | 星运 | 自坐 | 空亡 |"
    assert [_row(four, f"{p}柱")[1] for p in "年月日时"] == ["庚午", "辛巳", "庚辰", "辛巳"]
    assert _row(four, "年柱")[5] == "胎", "纳音长生列（路旁土·午 = 胎）"
    assert "命宫：癸未，干十神:伤，支十神:印（起法：通行版）" in four
    info = _section(text, "起盘信息")
    assert "时间基准：真太阳时(经度+均时差校正)；晚子时归次日：是；23 点换日：是" in info
    assert "直接时间：1990-05-15 10:30:00　真太阳时：1990-05-15 10:39:33" in info
    assert "起运：出生后7年3个月10天0小时起运" in _section(text, "大运")
    # godKeyPos 缺省「年」（techniqueMountSettings.js:1699）：劫煞/灾煞只按年支午（寅午戌 → 劫煞亥、灾煞子）起，
    # 四柱无亥子 → 不出。旧 Java 缺省「年日」另按日支辰（申子辰 → 劫煞巳、灾煞午）→ 月/时柱巳带劫煞、年柱午带灾煞。
    shensha = _section(text, "神煞（四柱与三元）")
    assert "劫煞" not in shensha and "灾煞" not in shensha, shensha
    # 显式子平数法 → 命宫辛巳（与 Java 缺省同值——两套独立实现互证）。
    shufa = service.run_tool("bazi_birth", {"date": "1990-05-15", "time": "10:30:00", "zone": "+08:00", "lat": "31n14",
                                            "lon": "121e28", "gender": 1, "minggongMethod": "shufa",
                                            "agent_confirmed_settings": True}, save_result=False)
    assert "命宫：辛巳，干十神:劫，支十神:杀（起法：子平数法）" in shufa.data["snapshot_text"]


@requires_node
def test_bazi_late_zi_1_0_quadrant_and_lichun_boundary_goldens(tmp_path) -> None:
    """两盘四柱 + 命宫金标（一跨 23:00、一跨立春）。

    ① 2026-05-27 23:30 直接时间：上游 utils/dayBoundary.js:49-57 矩阵 (1,0) = 壬寅日 戊子时
      （旧代码走 Java /bazi/birth，(1,0) 档 live 实测 HTTP 500「timegan.error」→ 红）。
    ② 立春 2024-02-04 16:27（北京时间，紫金山天文台历表）前后各取一刻（直接时间）：16:20 属癸卯年乙丑月，
      16:35 属甲辰年丙寅月（年柱/月柱以立春为界——公开历法事实）；2024-02-04 = 戊戌日（2000-01-01 戊午日起数
      8800 日），申时 = 庚申（戊癸日壬子起）。
    命宫（通行版）按古法「子上起正月逆数至生月，生月上起生时顺数至卯」定支、五虎遁（年干）定干：
      ① 巳月子时 → 子；丙年庚寅起 → 庚子。② 立春前 丑月申时 → 申、癸年甲寅起 → 庚申；
      立春后 寅月申时 → 未、甲年丙寅起 → 辛未（命宫干支随立春整体翻转）。
    """
    service = _service(tmp_path, real={"bazi_local"})
    env = service.run_tool("bazi_birth", {"date": "2026-05-27", "time": "23:30:00", **_SH, "timeAlg": 1,
                                          "after23NewDay": 1, "lateZiHourUseNextDay": 0}, save_result=False)
    assert env.ok, env.error
    four = _section(env.data["snapshot_text"], "四柱与三元")
    assert [_row(four, f"{p}柱")[1] for p in "年月日时"] == ["丙午", "癸巳", "壬寅", "戊子"]
    assert "命宫：庚子，" in four and "（起法：通行版）" in four, four
    # 缺省（不给日界键）= 上游出厂 (1,1) → 壬寅日 庚子时。本地 lunar 引擎缺键 = 不进位（→ 辛丑日 戊子时），
    # 所以 runner 必须显式补 1/1（同上游 genParams 读 defaultAfter23NewDay()）。
    dflt = service.run_tool("bazi_birth", {"date": "2026-05-27", "time": "23:30:00", **_SH, "timeAlg": 1}, save_result=False)
    assert [_row(_section(dflt.data["snapshot_text"], "四柱与三元"), f"{p}柱")[1] for p in "日时"] == ["壬寅", "庚子"]
    before = service.run_tool("bazi_birth", {"date": "2024-02-04", "time": "16:20:00", **_SH, "timeAlg": 1}, save_result=False)
    after = service.run_tool("bazi_birth", {"date": "2024-02-04", "time": "16:35:00", **_SH, "timeAlg": 1}, save_result=False)
    b4 = _section(before.data["snapshot_text"], "四柱与三元")
    a4 = _section(after.data["snapshot_text"], "四柱与三元")
    assert [_row(b4, f"{p}柱")[1] for p in "年月日时"] == ["癸卯", "乙丑", "戊戌", "庚申"]
    assert [_row(a4, f"{p}柱")[1] for p in "年月日时"] == ["甲辰", "丙寅", "戊戌", "庚申"]
    assert "命宫：庚申，" in b4 and "命宫：辛未，" in a4, (b4, a4)


@requires_node
def test_bazi_upstream_options_are_reachable(tmp_path) -> None:
    """school / ageStyle / dayunPrecision / godKeyPos（上游挂载设置，techniqueMountSettings.js:1699-1740）。
    旧代码：前三个键 schema 不认、Java 也不读 → 快照不变 → 红。"""
    service = _service(tmp_path, real={"bazi_local"})
    base = {"date": "1990-05-15", "time": "10:30:00", "zone": "+08:00", "lat": "31n14", "lon": "121e28", "gender": 1,
            "agent_confirmed_settings": True}
    text = service.run_tool("bazi_birth", {**base, "school": "geju", "ageStyle": "real", "dayunPrecision": "integer",
                                           "godKeyPos": "年日"}, save_result=False).data["snapshot_text"]
    assert "当前主用流派：格局派（各派取用可异，下列多派对照）" in _section(text, "格局·用神")
    dayun = _section(text, "大运")
    assert "| 年份 | 周岁 | 小运 | 流年 |" in dayun and "| 1990 | 0 | 壬午 | 庚午 |" in dayun, "周岁 = 虚岁 − 1（BaZi.js:555-569）"
    # 起运整数档（上游 utils/baziLunarLocal.js:986-996 formatStartLuck）：round(7 + 3/12 + 10/365) = 7。
    assert dayun.splitlines()[0] == "起运：出生后约7年起运", dayun.splitlines()[0]
    # 神煞主位「年日」：日支辰（申子辰）→ 劫煞巳（月/时柱）、灾煞午（年柱）加入（缺省「年」时没有，见上一用例）。
    shensha = _section(text, "神煞（四柱与三元）")
    assert "年柱：整柱=福星贵人、沐浴、月德贵人、德秀贵人、灾煞；" in shensha and "月柱：整柱=学堂、暗禄、亡神、病符、劫煞、" in shensha
    bad = service.run_tool("bazi_birth", {**base, "godKeyPos": "月"}, save_result=False)
    assert bad.ok and any("八字 godKeyPos='月' 无法识别" in w for w in bad.warnings), bad.warnings


@requires_node
def test_bazi_java_only_knobs_and_bc_dates_route_to_java(tmp_path) -> None:
    """本地引擎不实现 byLon/adjustJieqi（上游已隐藏节气微调控件），公元前在 lunar-js 可靠域外（lunarDomainGuard AD1–9999）：
    这些情况整盘走 Java /bazi/*，并进 warnings（不静默）。公元前按上游带负号日期送本地判域（旧 skill 约定正号+ad=-1，
    不补负号就把公元前 100 年当公元 100 年本地起盘）。"""
    client = CaptureClient()
    service = _service(tmp_path, client=client, real={"bazi_local"})
    env = service.run_tool("bazi_birth", {"date": "0100-05-15", "time": "10:30:00", **_SH, "ad": -1}, save_result=False)
    assert env.ok, env.error
    sent = [p for ep, p in client.calls if ep == "/bazi/birth"]
    assert sent and sent[0]["date"] == "-0100-05-15"
    assert env.data["compute_sources"] == {"bazi": "java"}
    assert any("八字由 Java /bazi/birth 起盘" in w for w in env.warnings)
    client.calls.clear()
    direct = service.run_tool("bazi_direct", {"date": "1990-05-15", "time": "10:30:00", **_SH, "gender": 0, "adjustJieqi": True},
                              save_result=False)
    assert direct.ok and [ep for ep, _ in client.calls if ep == "/bazi/direct"]
    assert any("adjustJieqi" in w for w in direct.warnings)
    with pytest.raises(ToolValidationError) as exc:
        service._bazi_params({"date": "1990-05-15", "time": "10:30:00", "timeAlg": 2})
    assert exc.value.code == "tool.bazi_timealg_unsupported"


# ════════════════════════════════════ F8 · 紫微传本/流派 ════════════════════════════════════

class _ZiweiJava(CaptureClient):
    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        if endpoint == "/ziwei/birth":
            return {"chart": {"gender": "Male"}, "patterns": []}
        return FakeClient.call(self, endpoint, payload)


_ZW = {"date": "1985-11-07", "time": "23:30:00", **_SH, "gender": 1}


@requires_node
def test_ziwei_sihua_school_reaches_java_and_snapshot(tmp_path) -> None:
    """sihuaSchool（上游 techniqueMountSettings.js:1744-1752）：非通用流派 → Java 附 sihua 表（后端格局随流派，
    ZiWeiMain.js:776-779）+ 快照「四化流派」行。旧代码：Java 从不读 sihuaSchool、schema_knob_debt 却称其
    「verified live via backend」→ 请求里没有 sihua → 红。中州派戊干化科 = 太阳（ziweiSchools SIHUA_OVERRIDES）。"""
    client = _ZiweiJava()
    service = _service(tmp_path, client=client, real={"ziwei_birth"})
    env = service.run_tool("ziwei_birth", {**_ZW, "sihuaSchool": "zhongzhou", "daxianSpan": "ju"}, save_result=False)
    assert env.ok, env.error
    sent = next(p for ep, p in client.calls if ep == "/ziwei/birth")
    assert sent["sihua"]["戊"] == ["贪狼", "太阴", "太阳", "天机"]
    assert "sihuaSchool" not in sent and "daxianSpan" not in sent, "本地键不发后端（上游 :768-775 同）"
    info = _section(env.data["snapshot_text"], "起盘信息")
    assert "四化流派：中州派" in info and "传本设置：大限跨度=局数年(钦天)" in info


@requires_node
def test_ziwei_chuanben_option_switches_to_local_engine(tmp_path) -> None:
    """传本开关非缺省 → 本地 ZiweiCalc 重排（ZiWeiMain.js:786-804）。1985-11-07 23:30 上海男命 土五局：
    钦天「局数年」大限每限 5 年、命宫 5~9（三合缺省 10 年则 5~14，Java 同盘 live 实测）。旧代码：键被丢/Java 不读 → 红。"""
    service = _service(tmp_path, client=_ZiweiJava(), real={"ziwei_birth"})
    env = service.run_tool("ziwei_birth", {**_ZW, "daxianSpan": "ju"}, save_result=False)
    assert env.ok, env.error
    assert env.data["compute_sources"] == {"chart": "ZiweiCalc"}
    assert _row(_section(env.data["snapshot_text"], "宫位总览"), "命宫·胎")[:3] == ["命宫·胎", "丙戌", "5~9"]
    assert env.data["technique_card"]["compute"]["matches_declaration"] is True


@requires_node
def test_ziwei_flat_overlay_switch_and_unknown_value(tmp_path) -> None:
    """平铺流派叠层键（上游挂载键 childLimit 等，aiAnalysisContext.js:1913-1918）此前只认 schools{} 子字典，
    平铺键声明了却没人读 → [流派叠层] 不出 → 红。认不出的取值不静默（进 warnings）。"""
    service = _service(tmp_path, client=_ZiweiJava(), real={"ziwei_birth"})
    env = service.run_tool("ziwei_birth", {**_ZW, "daxianSpan": "ju", "childLimit": 1, "kuiYue": "nope"}, save_result=False)
    assert env.ok, env.error
    # 童限（ziweiCore.childLimits）：土五局 → 1–4 岁依次 命宫/财帛/疾厄/夫妻。
    assert _section(env.data["snapshot_text"], "流派叠层").splitlines()[:2] == ["· 童限", "  1岁·命宫、2岁·财帛宫、3岁·疾厄宫、4岁·夫妻宫"]
    assert any("kuiYue='nope'" in w for w in env.warnings)


def test_ziwei_option_fields_are_accepted_but_not_advertised(tmp_path) -> None:
    """22 个传本键 + 八字盘法键：已声明（FastMCP 签名收、MCP 顶层按名直传），但不进 tools/list 广告层
    （x-horosa-hidden，tools/list 预算）。旧代码：字段未声明 → MCP 扁平面静默丢键 → 红。"""
    from horosa_skill.memory.store import MemoryStore as _Store
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(db_path=Path(tmp) / "m.db", output_dir=Path(tmp) / "runs")
        mcp = create_mcp_server(HorosaSkillService(settings, store=_Store(settings)), settings)
        tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    ziwei = tools["horosa_cn_ziwei_birth"]
    assert "daxianSpan" not in ziwei.inputSchema["properties"] and "sihuaSchool" in ziwei.inputSchema["properties"]
    bazi_props = tools["horosa_cn_bazi_birth"].inputSchema["properties"]   # FlexibleModel 分支（同紫微）
    assert "minggongMethod" not in bazi_props and "cnUnifiedZone" not in bazi_props and "godKeyPos" in bazi_props
    suzhan_props = tools["horosa_cn_suzhan"].inputSchema["properties"]     # BirthInput 子类分支
    assert "nongliTimeAlg" not in suzhan_props and "houseStartMode" in suzhan_props
    assert "nongliTimeAlg" in SuZhanInput.model_fields
    assert "daxianSpan" in ZiWeiBirthInput.model_fields and "minggongMethod" in BaZiBirthInput.model_fields
    assert "个高级旋钮" in ziwei.inputSchema["properties"]["request"]["description"]
    # 键表经 horosa_agent_guidance（按 MCP 名查）到达 agent —— 广告层不列、guidance 必须列。
    keys = build_agent_guidance(tool_name="horosa_cn_ziwei_birth")["tools"]["ziwei_birth"]["options_keys"]
    assert "daxianSpan" in keys and "sihuaSchool" in keys
    bazi_keys = build_agent_guidance(tool_name="bazi_direct")["tools"]["bazi_direct"]["options_keys"]
    assert {"minggongMethod", "dayunPrecision", "school", "ageStyle"} <= set(bazi_keys)


# ════════════════════════════════════ F11 · 宿占 ════════════════════════════════════

class _SuzhanClient(CaptureClient):
    """Java /chart 回带农历四柱的整盘（fixture 盘 + ChartController 形 chart.nongli.bazi）；chart 服务 "/" 回不带 nongli 的盘。"""

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        fixture = json.loads(_CHART_FIXTURE.read_text(encoding="utf-8"))
        if endpoint == "/chart":
            fixture["chart"]["nongli"] = {"bazi": {"time": {"branch": {"cell": "申"}}}}
        return fixture


@requires_node
def test_suzhan_defaults_follow_upstream_page(tmp_path) -> None:
    """宿占缺省（models/astro.js:117-119 doubingSu28=0 / :312-316 houseStartMode=0 八字公式 / :81-83 hsys=1）。
    旧代码：doubingSu28 缺省 True（=斗柄）、houseStartMode 缺省 1 且快照不读它、hsys 0、只走 chart 服务 → 红。
    fixture 盘上升赤经 201.3°（天秤）、太阳赤经 70.2°（双子），时支申：八字公式 (2−2−5+24)%12=7 → 白羊宫头为第 6 宫；
    ASC 起宫则第 7 宫（SuZhanMain.js:148-192）。"""
    client = _SuzhanClient()
    service = _service(tmp_path, client=client, real={"suzhan"})
    env = service.run_tool("suzhan", {"date": "2026-06-02", "time": "14:30:00", **_SH}, save_result=False)
    assert env.ok, env.error
    java = [p for ep, p in client.calls if ep == "/chart"]
    assert java and java[0]["doubingSu28"] == 0 and java[0]["hsys"] == 1
    text = env.data["snapshot_text"]
    info = _section(text, "起盘信息")
    assert "宿法：荀爽距星(19年测)" in info and "人事十二宫起盘：八字公式起盘" in info and "外盘：" not in info
    assert "| 戌—降娄—白羊座—第6宫 |" in text
    assert env.data["compute_sources"] == {"chart": "java"}
    client.calls.clear()
    asc = service.run_tool("suzhan", {"date": "2026-06-02", "time": "14:30:00", **_SH, "houseStartMode": 1, "doubingSu28": 5},
                           save_result=False)
    assert not [ep for ep, _ in client.calls if ep == "/chart"], "ASC 档不需农历，走 chart 服务"
    assert "| 戌—降娄—白羊座—第7宫 |" in asc.data["snapshot_text"] and "宿法：恒星制·现代天赤" in asc.data["snapshot_text"]


@requires_node
def test_suzhan_nongli_time_alg_and_su28_validation(tmp_path) -> None:
    """nongliTimeAlg（Java ChartController [Q-419/T-383]，0/1/3）只在八字公式档随 Java /chart 下发；宿度制 0–8 外报错。
    旧代码：nongliTimeAlg 未声明也不转发；doubingSu28 是 bool，9 这类值静默落 0 → 红。"""
    client = _SuzhanClient()
    service = _service(tmp_path, client=client, real={"suzhan"})
    env = service.run_tool("suzhan", {"date": "2026-06-02", "time": "14:30:00", **_SH, "nongliTimeAlg": 1}, save_result=False)
    assert env.ok and next(p for ep, p in client.calls if ep == "/chart")["nongliTimeAlg"] == 1
    bad = service.run_tool("suzhan", {"date": "2026-06-02", "time": "14:30:00", **_SH, "doubingSu28": 9}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.suzhan_su28_invalid"
    assert SuZhanInput.model_fields["hsys"].default == 1 and SuZhanInput.model_fields["houseStartMode"].default == 0


# ════════════════════════════════════ F10 · 通书流派词表 ════════════════════════════════════

@requires_node
def test_tongshu_school_vocabulary_is_the_engine_one(tmp_path) -> None:
    """引擎键（tongshuSchools.js:4-8）sanyuanliexiu=三垣列宿、sanyuan=三元玄空大卦；旧文档写反（sanyuan=三垣、xuankong=玄空）。
    旧代码：xuankong 落进「（该流派待实现）」、未知键照样 ok → 红。"""
    service = _service(tmp_path, real={"tongshu", "calendar_extras"})
    liexiu = service.run_tool("tongshu", {"date": "2028-04-06", "school": "sanyuanliexiu", "agent_confirmed_settings": True}, save_result=False)
    assert "流派：三垣列宿加临（古法）" in liexiu.data["snapshot_text"]
    xk = service.run_tool("tongshu", {"date": "2028-04-06", "school": "xuankong", "agent_confirmed_settings": True}, save_result=False)
    assert xk.ok and "流派：三元玄空大卦" in xk.data["snapshot_text"] and "待实现" not in xk.data["snapshot_text"]
    assert any("xuankong" in w and "sanyuan" in w for w in xk.warnings)
    bogus = service.run_tool("tongshu", {"date": "2028-04-06", "school": "bogus", "agent_confirmed_settings": True}, save_result=False)
    assert bogus.ok is False and bogus.error.code == "tool.tongshu_unknown_school"
    assert [v["key"] for v in bogus.error.details["valid"]] == ["donggong", "qimen", "sanyuanliexiu", "wutu", "sanyuan"]
    cal = service.run_tool("calendar_month", {"date": "2028-04-06", "zone": "+08:00", "tongshu": {"school": "bogus"},
                                              "agent_confirmed_settings": True}, save_result=False)
    assert cal.ok is False and cal.error.code == "tool.tongshu_unknown_school"
    ask = next(q for q in TOOL_GUIDANCE["tongshu"]["ask_if_missing"] if q["field"] == "school")
    assert ask["values"] == ["donggong", "qimen", "sanyuanliexiu", "wutu", "sanyuan"]


# ════════════════════════════════════ F16 · 节气年盘 ════════════════════════════════════

class _JieqiClient(CaptureClient):
    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        if endpoint == "/jieqi/year":
            fixture = json.loads(_CHART_FIXTURE.read_text(encoding="utf-8"))
            fixture["params"] = {**fixture.get("params", {}), "birth": "2025-03-20 17:01:41"}
            return {"jieqi24": [{"jieqi": "春分", "time": "2025-03-20 17:01:41"}], "charts": {"春分": fixture}}
        return FakeClient.call(self, endpoint, payload)


def test_jieqi_year_su28_int_and_sidereal_ayanamsa_recharts(tmp_path) -> None:
    """doubingSu28 九档（上游 JieQiChartsMain.js:122-134 不再夹成 0/1）；siderealAyanamsa（zodiacal=1）上游逐节气
    /chart 带岁差（:524-553），本仓主调 Python /jieqi/year 不读它 → 按交节时刻逐盘重发 /chart。
    旧代码：doubingSu28 是 bool（3 → True）、siderealAyanamsa 未声明被丢且从未下发 → 红。"""
    client = _JieqiClient()
    service = _service(tmp_path, client=client)
    env = service.run_tool("jieqi_year", {"year": 2025, **_SH, "jieqis": ["春分"], "zodiacal": 1, "doubingSu28": 3,
                                          "siderealAyanamsa": "raman"}, save_result=False)
    assert env.ok, env.error
    main = next(p for ep, p in client.calls if ep == "/jieqi/year" and p.get("jieqis"))
    assert main["doubingSu28"] == 3
    rechart = [p for ep, p in client.calls if ep == "/"]
    # 发往 Python chart 服务（端点 "/"）按 chart 族约定用斜杠日期（test_service 同约定）。
    assert rechart and rechart[0]["siderealAyanamsa"] == "raman" and rechart[0]["date"] == "2025/03/20"
    assert rechart[0]["time"] == "17:01:41" and rechart[0]["doubingSu28"] == 3
    assert JieQiYearInput.model_fields["doubingSu28"].default == 0
    client.calls.clear()
    service.run_tool("jieqi_year", {"year": 2025, **_SH, "jieqis": ["春分"], "zodiacal": 0, "siderealAyanamsa": "raman"}, save_result=False)
    assert not [ep for ep, _ in client.calls if ep == "/"], "回归黄道下岁差不生效（PerChart 只在恒星黄道读它）→ 不重排"


# ════════════════════════════════════ F17 · 北京时间归并 ════════════════════════════════════

def test_urumqi_zone_unifies_to_beijing_time_from_1949() -> None:
    """上游 utils/timezone.js:130-151 unifyCnZone：Asia/Urumqi → Asia/Shanghai（日期 ≥ 1949-10-01，只归并名、偏移按
    日期算）。旧代码：Asia/Urumqi 恒 +06:00 → 红。1990-05-15 在中国夏令时（1986–1991）内 → +09:00（IANA tzdata）。"""
    out = normalize_request_payload({"date": "1990-05-15", "time": "10:30", "zone": "Asia/Urumqi"})
    assert (out["zone"], out.get("geoZone"), out.get("zoneAdvisory")) == ("+09:00", "Asia/Urumqi", "cn-unified")
    assert normalize_request_payload({"date": "2020-01-15", "time": "10:30", "zone": "Asia/Urumqi"})["zone"] == "+08:00"
    # 统一前（1949-10-01 之前）的新疆出生仍按地理时区；显式退出 / 直接给偏移都不归并。
    assert normalize_request_payload({"date": "1945-05-15", "time": "10:30", "zone": "Asia/Urumqi"})["zone"] == "+06:00"
    # 起点边界按日（上游比 YYYY-MM-DD）：1949-10-01 当天起归并，前一天不归并；四位以下的年不能因字符串比较被误归并。
    assert normalize_request_payload({"date": "1949-10-01", "time": "00:30", "zone": "Asia/Urumqi"})["zone"] == "+08:00"
    assert normalize_request_payload({"date": "1949-09-30", "time": "23:30", "zone": "Asia/Urumqi"})["zone"] == "+06:00"
    assert "zoneAdvisory" not in normalize_request_payload({"date": "0999-05-15", "time": "10:30", "zone": "Asia/Urumqi"})
    opt_out = normalize_request_payload({"date": "2020-01-15", "time": "10:30", "zone": "Asia/Urumqi", "cnUnifiedZone": False})
    assert opt_out["zone"] == "+06:00" and "zoneAdvisory" not in opt_out
    assert normalize_request_payload({"date": "2020-01-15", "time": "10:30", "zone": "+06:00"})["zone"] == "+06:00"


def test_cn_unified_zone_is_disclosed_in_warnings_and_card(tmp_path) -> None:
    service = _service(tmp_path)
    env = service.run_tool("nongli_time", {"date": "2020-01-15", "time": "10:30:00", "zone": "Asia/Urumqi",
                                           "lat": "43n48", "lon": "87e36", "agent_confirmed_settings": True}, save_result=False)
    assert env.ok and env.input_normalized["zone"] == "+08:00"
    assert any("Asia/Urumqi → Asia/Shanghai" in w for w in env.warnings)
    assert env.data["technique_card"]["settings"]["zoneAdvisory"]["value"] == "北京时间统一（Asia/Urumqi→Asia/Shanghai）"


# ════════════════════════════════════ live（显式点名的 vendored 实例）════════════════════════════════════

from test_local_js_tools import make_service, requires_runtime


@requires_runtime
def test_live_mingli_tools(tmp_path) -> None:
    """真后端 + 真引擎：日界缺省、八字本地优先、紫微传本/流派、宿占农历时支、节气岁差。"""
    service = make_service(tmp_path)
    nl = service.run_tool("nongli_time", {"date": "2026-05-27", "time": "23:30:00", **_SH, "timeAlg": 1}, save_result=False)
    assert nl.ok and nl.data.get("dayGanZi") == "壬寅", "缺省 = 23 点换日（旧代码下发 False → 辛丑）"
    bz = service.run_tool("bazi_birth", {"date": "2026-05-27", "time": "23:30:00", **_SH, "timeAlg": 1,
                                         "after23NewDay": 1, "lateZiHourUseNextDay": 0}, save_result=False)
    four = _section(bz.data["snapshot_text"], "四柱与三元")
    assert bz.ok and _row(four, "日柱")[1] == "壬寅" and _row(four, "时柱")[1] == "戊子"
    zw = service.run_tool("ziwei_birth", {**_ZW, "daxianSpan": "ju", "sihuaSchool": "zhongzhou"}, save_result=False)
    assert zw.ok and zw.data["compute_sources"] == {"chart": "ZiweiCalc"}
    assert "四化流派：中州派" in zw.data["snapshot_text"] and "| 命宫·胎 | 丙戌 | 5~9 |" in zw.data["snapshot_text"]
    sz = service.run_tool("suzhan", {"date": "1990-05-15", "time": "10:30:00", **_SH}, save_result=False)
    assert sz.ok and sz.data["compute_sources"] == {"chart": "java"} and not sz.warnings
    jq = service.run_tool("jieqi_year", {"year": 2024, **_SH, "jieqis": ["春分"], "zodiacal": 1, "siderealAyanamsa": "raman"},
                          save_result=False)
    assert jq.ok and "恒星黄道岁差：Raman" in _section(jq.data["snapshot_text"], "春分星盘")
