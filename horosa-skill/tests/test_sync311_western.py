"""上游 v3.11 西占选项补齐（western chunk）：卜卦/择日流派起盘字段与判读全局层、七政宿度制、占星地图、世运规则集、
印占大运体系/流派、巴比伦纪元与星历源、古典显示子选项。

每条用例都在旧代码上红（负向对照见各用例注释）。服务级用例跑**真 JS 引擎**（vendored 上游 builder）+ HTTP 桩：
桩只供端点形状（或 live 实抓的整盘夹具），段文本全部由上游 builder 产出；期望值带权威出处（上游源行号 / 引擎词表）。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from test_service import FakeClient

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

FIXTURES = Path(__file__).parent / "fixtures"
HORARY_FIX = json.loads((FIXTURES / "sync311_western_horary.json").read_text(encoding="utf-8"))
CHART_TRADITIONAL = json.loads(
    (Path(__file__).resolve().parents[1] / "horosa-core-js" / "test" / "fixtures" / "chart_traditional.json").read_text(encoding="utf-8")
)
BIRTH = {"date": "2026-03-10", "time": "14:20:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True}


class RecordingClient(FakeClient):
    """FakeClient + 记账；/chart 可换成指定的盘（live 实抓夹具按请求宫制取）。"""

    def __init__(self, chart_for=None) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []
        self.chart_for = chart_for

    def call(self, endpoint: str, payload: dict) -> dict:
        # chart 服务上 /chart 的真实路由是 "/"（service._chart_server_endpoint），记账时归一回 /chart。
        endpoint = "/chart" if endpoint == "/" else endpoint
        self.calls.append((endpoint, copy.deepcopy(payload)))
        if endpoint == "/chart" and self.chart_for is not None:
            return copy.deepcopy(self.chart_for(payload))
        return super().call(endpoint, payload)

    def bodies(self, endpoint: str) -> list[dict]:
        return [p for e, p in self.calls if e == endpoint]


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
    nxt = body.find("\n[")
    return body if nxt < 0 else body[:nxt]


def _horary_chart_by_hsys(payload: dict) -> dict:
    return HORARY_FIX["hsys2"] if int(payload.get("hsys", 0)) == 2 else HORARY_FIX["hsys0"]


# ─────────────────────────── F1 卜卦：流派起盘字段 ───────────────────────────


def test_horary_casts_chart_with_the_school_backend_fields(tmp_path: Path) -> None:
    """上游 HoraryMain.js:543 `{ zodiacal: 0, ...horaryBackendFields(school) }`；horarySchools.js:231-272 七档 backend。
    负向对照：旧 runner 只补 hsys=0 —— classical 盘按整宫、埃及界、Dorothean 三分集起，下面四条断言全红。"""
    client = RecordingClient()
    service = _service(tmp_path, client)
    assert service.run_tool("horary", {**BIRTH, "category": "career"}, save_result=False).ok
    sent = client.bodies("/chart")[-1]
    # classical：Regiomontanus / 托勒密界·经典传本 / 七政 / 福点不反转 / Ptolemy 三分集。
    assert (sent["hsys"], sent["termsVariant"], sent["tradition"], sent["lotReversal"], sent["triplicity"]) == (2, 2, 1, 0, "Ptolemaic")

    assert service.run_tool("horary", {**BIRTH, "school": "modern"}, save_result=False).ok
    sent = client.bodies("/chart")[-1]
    assert (sent["hsys"], sent["tradition"]) == (3, 0)  # 现代心理档：Placidus + 三王星

    assert service.run_tool("horary", {**BIRTH, "school": "medieval"}, save_result=False).ok
    sent = client.bodies("/chart")[-1]
    assert (sent["hsys"], sent["termsVariant"], sent["lotReversal"], sent["triplicity"]) == (1, 0, 1, "Dorothean")


def test_horary_explicit_settings_override_the_school(tmp_path: Path) -> None:
    """显式 hsys / options.tripSystem 压过流派（上游 horaryBackendFields(id, overrides) 的覆盖语义）；
    顶层全局 triplicity 不作用于卜卦盘（流派绑定，HoraryMain.js:563）但必须说出来。"""
    client = RecordingClient()
    service = _service(tmp_path, client)
    result = service.run_tool("horary", {**BIRTH, "hsys": 0}, save_result=False)
    sent = client.bodies("/chart")[-1]
    assert (sent["hsys"], sent["termsVariant"]) == (0, 2)
    assert result.data["backendFields"]["hsys"] == 0

    service.run_tool("horary", {**BIRTH, "options": {"tripSystem": "dorothean"}}, save_result=False)
    assert client.bodies("/chart")[-1]["triplicity"] == "Dorothean"

    result = service.run_tool("horary", {**BIRTH, "triplicity": "Dorothean"}, save_result=False)
    assert client.bodies("/chart")[-1]["triplicity"] == "Ptolemaic"
    assert any("triplicity" in w and "流派" in w for w in result.warnings), result.warnings


def test_horary_school_house_system_changes_the_judgment(tmp_path: Path) -> None:
    """值级：同一提问时刻（live 实抓 2026-03-10 14:20 上海，夹具 sync311_western_horary.json），经典档 Regiomontanus
    盘里问卜者太阳落第 9 宫（果宫），整宫盘里落第 8 宫——[征象力量] 与 [根本性] 随之改变。
    负向对照：旧代码恒以整宫起盘 → 经典档也读出「第8宫 · 续宫」与「上升主落 8 宫」警告。"""
    service = _service(tmp_path, RecordingClient(chart_for=_horary_chart_by_hsys))
    classical = service.run_tool("horary", {**BIRTH, "category": "career"}, save_result=False)
    text = classical.data["snapshot_text"]
    assert "◆ 太阳（问卜者）：力量 -2\n落 双鱼座 · 第9宫 · 果宫·偏弱 · 游走·无尊贵" in _section(text, "征象力量")
    assert _section(text, "根本性").strip() == "适合判断。"
    whole = service.run_tool("horary", {**BIRTH, "category": "career", "hsys": 0}, save_result=False)
    text0 = whole.data["snapshot_text"]
    assert "◆ 太阳（问卜者）：力量 -1\n落 双鱼座 · 第8宫 · 续宫·中等 · 游走·无尊贵" in _section(text0, "征象力量")
    assert "上升主落 8 宫" in _section(text0, "根本性")


# ─────────────────────────── F13 卜卦：判读全局层 / 定盘自评 ───────────────────────────


def test_horary_top_level_classical_keys_feed_the_global_judge_layer(tmp_path: Path) -> None:
    """上游 judgeLayerOverrides.js：顶层古典键 → horaryJudgeOpts 第 2 层（全局层），流派差异集压过它、页面覆盖再压过。
    antisciaOrb：任何流派都不绑 → 全局层直接生效（[映点对映点] 表 orb 同吃，horarySnapshot.js [H8]）；
    fixedStarOrb：classical 档绑定 2°（SCHOOL_JUDGE_DIFF.classical）→ 全局 5° 被流派压住，options 覆盖才生效。
    负向对照：旧 runner 不把顶层古典键交给 JS（只转交 considerationsMode/lotsSet）→ 两个全局键都不进判读。"""
    service = _service(tmp_path, RecordingClient(chart_for=lambda p: CHART_TRADITIONAL))
    base = service.run_tool("horary", BIRTH, save_result=False)
    wide = service.run_tool("horary", {**BIRTH, "antisciaOrb": 3}, save_result=False)
    assert _section(base.data["snapshot_text"], "映点对映点") != _section(wide.data["snapshot_text"], "映点对映点")
    assert wide.data["judgment"]["params_global"] == ["antisciaOrb"]
    # 等于全局缺省的值不进全局层（上游「只含用户改过的键」）：antisciaOrb 缺省 1。
    same = service.run_tool("horary", {**BIRTH, "antisciaOrb": 1}, save_result=False)
    assert same.data["judgment"]["params_global"] == []
    assert same.data["snapshot_text"] == base.data["snapshot_text"]
    # starOrb（后端名）→ fixedStarOrb 全局层；classical 绑定 2° 压住它，快照不变。
    star_global = service.run_tool("horary", {**BIRTH, "starOrb": 5}, save_result=False)
    assert star_global.data["judgment"]["params_global"] == ["fixedStarOrb"]
    assert _section(star_global.data["snapshot_text"], "恒星会合") == _section(base.data["snapshot_text"], "恒星会合")
    star_page = service.run_tool("horary", {**BIRTH, "options": {"fixedStarOrb": 5}}, save_result=False)
    assert _section(star_page.data["snapshot_text"], "恒星会合") != _section(base.data["snapshot_text"], "恒星会合")


def test_horary_invalid_global_enum_is_an_error(tmp_path: Path) -> None:
    service = _service(tmp_path, RecordingClient(chart_for=lambda p: CHART_TRADITIONAL))
    result = service.run_tool("horary", {**BIRTH, "vocMode": "no_such_mode"}, save_result=False)
    assert result.ok is False
    assert result.error.code == "tool.horary_invalid_setting"
    assert "vocMode" in result.error.message


def test_horary_self_assessment_and_question_reach_the_snapshot(tmp_path: Path) -> None:
    """上游 HoraryMain.js:487-497 三勾选 → runHorary opts（radicality.js:174-179/258-259）；问句/阵营 →
    buildHorarySnapshot 第 3 参 → [定盘考量] 首两行（horarySnapshot.js:115-118）。
    负向对照：旧 JS 工具把整个判读 opts 当第 3 参传、从不传三勾选 → 问句行缺、第 18 条恒「未命中」。"""
    service = _service(tmp_path, RecordingClient(chart_for=lambda p: CHART_TRADITIONAL))
    base = _section(service.run_tool("horary", BIRTH, save_result=False).data["snapshot_text"], "定盘考量")
    assert "18. " in base and "所问之事" not in base
    asked = service.run_tool(
        "horary",
        {**BIRTH, "questionText": "这份工作能拿到吗", "castingCamp": "querent", "sincerityConfirmed": False},
        save_result=False,
    )
    body = _section(asked.data["snapshot_text"], "定盘考量")
    assert body.startswith("所问之事：“这份工作能拿到吗”\n起盘阵营：问卜者中心（时地取问卜者）\n")
    line18 = next(line for line in body.splitlines() if line.startswith("- 18. "))
    assert line18.endswith("：命中（可救济：「我确认问题真诚」勾选）"), line18
    bad = service.run_tool("horary", {**BIRTH, "castingCamp": "nowhere"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.horary_invalid_setting"


# ─────────────────────────── F13 择日：用事专属输入 / 判读全局层 / 流派宫制 ───────────────────────────


def test_election_topic_inputs_reach_the_rule_pack(tmp_path: Path) -> None:
    """上游 ElectionMain.js:376-440 左栏按用事显示的控件 → runElection opts（rulePacks.js 读 opts.tradeSide /
    talismanStar / surgeryPart / surgeryPartOpposite）。负向对照：旧 runner 不转交这四键 → [用事专属] 一律「（选…后判）」跳过。"""
    service = _service(tmp_path, RecordingClient(chart_for=lambda p: CHART_TRADITIONAL))
    trade = service.run_tool("election", {**BIRTH, "topicId": "trade", "tradeSide": "sell"}, save_result=False)
    assert "售:己方(1宫主" in _section(trade.data["snapshot_text"], "用事专属")
    talisman = service.run_tool("election", {**BIRTH, "topicId": "talisman", "talismanStar": "jupiter"}, save_result=False)
    assert "护符主星 木星 不逆行/不燃烧/不在座末" in _section(talisman.data["snapshot_text"], "用事专属")
    surgery = service.run_tool(
        "election", {**BIRTH, "topicId": "surgery", "surgeryPart": "leo", "surgeryPartOpposite": True}, save_result=False
    )
    assert "月不落手术部位星座（狮子" in _section(surgery.data["snapshot_text"], "用事专属")
    assert "·延及对宫）" in _section(surgery.data["snapshot_text"], "用事专属")
    # 用事不读它 → warnings 说出来（判据 = 引擎 evaluateTopicPack 去键重跑比对，不手抄用事表）。
    unused = service.run_tool("election", {**BIRTH, "topicId": "marriage", "tradeSide": "sell"}, save_result=False)
    assert any("tradeSide" in w and "marriage" in w for w in unused.warnings), unused.warnings
    bad = service.run_tool("election", {**BIRTH, "topicId": "talisman", "talismanStar": "pluto"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.election_invalid_setting"


def test_election_crisis_date_casts_the_onset_chart(tmp_path: Path) -> None:
    """上游 fetchCrisisBase（ElectionMain.js:159-171）：病始日期正午、择日地点起盘 → 月黄经 → [危象日参照]。
    值级：桩盘月亮 Capricorn（chart_traditional.json 月黄经）= 择日盘月亮 → 已行 0°，最近危象点 360°（月归本位）。
    负向对照：旧代码无 crisisBase 输入 → 不起病始盘、无 [危象日参照] 段。"""
    client = RecordingClient(chart_for=lambda p: CHART_TRADITIONAL)
    service = _service(tmp_path, client)
    result = service.run_tool("election", {**BIRTH, "topicId": "surgery", "crisisBase": "2026-03-01"}, save_result=False)
    crisis = [p for p in client.bodies("/chart") if str(p.get("date")) == "2026/03/01"]
    assert crisis and crisis[0]["time"] == "12:00:00" and crisis[0]["lat"] == BIRTH["lat"]
    body = _section(result.data["snapshot_text"], "危象日参照")
    assert body.startswith("自病始（2026-03-01）月已行 0°；最近危象点 360°（大危象·月归本位·第4大危象(~28日)），相距 0°。")
    bad = service.run_tool("election", {**BIRTH, "topicId": "surgery", "crisisBase": "March 1"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.election_invalid_setting"


def test_election_global_judge_layer_and_school_house_link(tmp_path: Path) -> None:
    """顶层 vocMode → 择日判读全局层（ElectionJudgment.js:296 `...judgeLayerOverrides()` → resolveElectionParams 第 2 层）
    → [流派口径] 空亡口径行；流派宫制联动（westernSchools.js hsys：renaissance=2）→ /chart 请求，显式 hsys 压过。
    负向对照：旧 runner 不转交顶层键（空亡口径恒「无入相即空」）、hsys 恒取 BirthInput 缺省 0。"""
    client = RecordingClient(chart_for=lambda p: CHART_TRADITIONAL)
    service = _service(tmp_path, client)
    result = service.run_tool("election", {**BIRTH, "vocMode": "kenodromia"}, save_result=False)
    assert "- 空亡口径：30° 法（希腊化）" in _section(result.data["snapshot_text"], "流派口径")
    service.run_tool("election", {**BIRTH, "school": "renaissance"}, save_result=False)
    assert client.bodies("/chart")[-1]["hsys"] == 2
    service.run_tool("election", {**BIRTH, "school": "renaissance", "hsys": 3}, save_result=False)
    assert client.bodies("/chart")[-1]["hsys"] == 3
    service.run_tool("election", BIRTH, save_result=False)
    assert client.bodies("/chart")[-1]["hsys"] == 0  # 现代主流档不联动 → 页面缺省 0（ElectionMain.js:100）
