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
    """FakeClient + 记账；/chart 可换成指定的盘（live 实抓夹具按请求宫制取），其它端点可按 routes 换响应。"""

    def __init__(self, chart_for=None, routes=None) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []
        self.chart_for = chart_for
        self.routes = routes or {}

    def call(self, endpoint: str, payload: dict) -> dict:
        # chart 服务上 /chart 的真实路由是 "/"（service._chart_server_endpoint），记账时归一回 /chart。
        endpoint = "/chart" if endpoint == "/" else endpoint
        self.calls.append((endpoint, copy.deepcopy(payload)))
        if endpoint == "/chart" and self.chart_for is not None:
            return copy.deepcopy(self.chart_for(payload))
        if endpoint in self.routes:
            return copy.deepcopy(self.routes[endpoint](payload))
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


# ─────────────────────────── F2/F3 七政四余：宿度制 + 起盘口径 ───────────────────────────

CHART_GUOLAO = json.loads(
    (Path(__file__).resolve().parents[1] / "horosa-core-js" / "test" / "fixtures" / "chart_guolao.json").read_text(encoding="utf-8")
)["chart"]
GUOLAO_BIRTH = {"date": "1985-03-21", "time": "10:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
                "moiraTransitDate": "2026-09-01", "agent_confirmed_settings": True}


def _first_chart(client: RecordingClient) -> dict:
    return client.bodies("/chart")[0]


def test_guolao_default_mansion_system_is_upstream_mode_2(tmp_path: Path) -> None:
    """上游 GuoLaoChartStyle.js:10 GUOLAO_DEFAULT_SU28_MODE = 2（回归今宿）；fieldsToParams（GuoLaoChartMain.js:2339-2357）
    把它作 doubingSu28 下发。负向对照：旧 runner 发 doubingSu28=True —— perchart.parseSu28Mode 解释成 1（斗柄定房法·赤仪），
    快照也没有「宿度制：」行。"""
    client = RecordingClient()
    result = _service(tmp_path, client).run_tool("guolao_chart", GUOLAO_BIRTH, save_result=False)
    sent = _first_chart(client)
    assert sent["doubingSu28"] == 2 and sent["zodiacal"] == 0 and sent["guolaoZhengSidereal"] == 0
    info = _section(result.data["snapshot_text"], "起盘信息")
    # 上游 _buildGuolaoSnapshotTextV2Core:2047-2073 六行（缺省口径）。
    for line in ("七政命度：占星上升", "罗计：北计南罗", "报时星太阳时：真太阳时(经度+均时差)",
                 "罗计取法：平交点；月孛取法：平远地点", "宿度制：回归今宿；身宫法：太阴落宫(果老)",
                 "命主取法：宫主；行运法：古度限度法"):
        assert f"\n{line}\n" in f"\n{info}\n", line


def test_guolao_mode_sub_options_follow_upstream_gates(tmp_path: Path) -> None:
    """fieldsToParams 的条件透传（GuoLaoChartMain.js:2360-2399）：恒星制(4) → 恒星黄道 + guolaoZhengSidereal + 岁差复用
    siderealAyanamsa；授时历古法(6) → 推变黄道术/古宿随岁差；报时星/四余取法仅非缺省才发。门控外的子选项不下发并告警。
    负向对照：旧 schema 把 doubingSu28 定为 bool（4/6 直接校验失败），子选项无人翻译。"""
    client = RecordingClient()
    service = _service(tmp_path, client)
    r4 = service.run_tool("guolao_chart", {**GUOLAO_BIRTH, "doubingSu28": 4, "guolaoAyanamsa": "raman",
                                            "guolaoTrueSolarTime": "mean", "guolaoNodeType": "true"}, save_result=False)
    assert r4.ok, r4.error
    sent = _first_chart(client)
    assert (sent["doubingSu28"], sent["zodiacal"], sent["guolaoZhengSidereal"], sent["siderealAyanamsa"]) == (4, 1, 1, "raman")
    assert (sent["trueSolarTime"], sent["guolaoNodeType"]) == ("mean", "true")
    info = _section(r4.data["snapshot_text"], "起盘信息")
    assert "宿度制：恒星制；身宫法：太阴落宫(果老)" in info
    assert "报时星太阳时：平太阳时(仅经度)" in info and "罗计取法：真交点；月孛取法：平远地点" in info

    client.calls.clear()
    service.run_tool("guolao_chart", {**GUOLAO_BIRTH, "doubingSu28": 6, "guolaoTuibianMethod": "jintui", "guolaoGufaPrecess": 1}, save_result=False)
    sent = _first_chart(client)
    assert (sent["guolaoTuibianMethod"], sent["guolaoGufaPrecess"]) == ("jintui", 1)

    client.calls.clear()
    gated = service.run_tool("guolao_chart", {**GUOLAO_BIRTH, "guolaoTuibianMethod": "jintui"}, save_result=False)
    assert "guolaoTuibianMethod" not in _first_chart(client)
    assert any("guolaoTuibianMethod" in w and "宿度制 6" in w for w in gated.warnings), gated.warnings

    bad = service.run_tool("guolao_chart", {**GUOLAO_BIRTH, "doubingSu28": 9}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.guolao_invalid_display_setting"
    bad_mode = service.run_tool("guolao_chart", {**GUOLAO_BIRTH, "guolaoNodeMode": "sideways"}, save_result=False)
    assert bad_mode.ok is False and bad_mode.error.code == "tool.guolao_invalid_display_setting"


def test_guolao_node_mode_and_life_mode_change_the_reading(tmp_path: Path) -> None:
    """罗计「北罗南计」= applyGuolaoNodeMode 整盘深换北/南交 id（GuoLaoChartMain.js:1202-1211，页面与无头同吃换位后的盘）；
    命度法 gumao（normalizeGuolaoLifeMode 值域）进 [起盘信息] 与格局求值的 fields。
    负向对照：旧代码不认 guolaoNodeMode（盘不换位、无「罗计：」行）。"""
    service = _service(tmp_path, RecordingClient(chart_for=lambda p: CHART_GUOLAO))
    plain = service.run_tool("guolao_chart", GUOLAO_BIRTH, save_result=False)
    swapped = service.run_tool(
        "guolao_chart", {**GUOLAO_BIRTH, "guolaoNodeMode": "northRahuSouthKetu", "guolaoLifeMode": "gumao"}, save_result=False
    )
    objs = {o["id"]: o for o in plain.data["chart"]["objects"]}
    objs_sw = {o["id"]: o for o in swapped.data["chart"]["objects"]}
    assert objs_sw["North Node"]["lon"] == objs["South Node"]["lon"]
    assert objs_sw["South Node"]["lon"] == objs["North Node"]["lon"]
    info = _section(swapped.data["snapshot_text"], "起盘信息")
    assert "罗计：北罗南计" in info and "七政命度：遇卯安命(古法)" in info
    # 值级：[星曜庙旺与星点动态] 的罗/计两行随换位对调（上游 buildStarDignityMotionSection：罗=NORTH_NODE、计=SOUTH_NODE）。
    dignity_title = "星曜庙旺与星点动态（殿垣庙旺乐喜怒 · 顺逆留伏迟速）"
    assert "| 罗 | 酉 | - | 逆 |" in _section(plain.data["snapshot_text"], dignity_title)
    assert "| 罗 | 卯 | 旺 | 逆 |" in _section(swapped.data["snapshot_text"], dignity_title)


# ─────────────────────────── F18 巴比伦：纪元 / 数理星历位置源 ───────────────────────────

BABYLON_BIRTH = {"date": "1990-06-15", "time": "08:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True}


def test_babylon_era_and_ephemeris_source_reach_the_snapshot(tmp_path: Path) -> None:
    """上游 babylonAiSnapshot.js:219-221 纪元行（seleucid S.E. / arsacid = S.E.−64）与 :120 [数理星历] 木星函数
    （ephemerisSource systemB → 锯齿）；两键 = 上游挂载 babylonEra 齿轮 / 页面 effectiveOpts（BabylonMain.js:170-177）。
    [数理星历] 的五星锚取本盘恒星黄经 lons（:373 同传）。1990-06-15 的算术历年 = S.E.2301（纪元行两制同一年相差 64）。
    负向对照：旧 runner 注释「era 无人消费」而不下发、JS 不传 lons（五星行缺席），ephemerisSource 无入口。"""
    service = _service(tmp_path, RecordingClient())
    base = service.run_tool("babylon", BABYLON_BIRTH, save_result=False)
    text = base.data["snapshot_text"]
    assert "纪元:塞琉古纪元 S.E.2301 年" in _section(text, "起盘信息")
    assert "◆ 木星（System A）" in _section(text, "数理星历")
    alt = service.run_tool("babylon", {**BABYLON_BIRTH, "era": "arsacid", "ephemerisSource": "systemB"}, save_result=False)
    alt_text = alt.data["snapshot_text"]
    assert "纪元:安息纪元 2237 年" in _section(alt_text, "起盘信息")
    assert "◆ 木星（System B）" in _section(alt_text, "数理星历")
    assert "木星按 System B 锯齿函数" in _section(alt_text, "数理星历")
    bad = service.run_tool("babylon", {**BABYLON_BIRTH, "era": "julian"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.babylon_invalid_setting"


# ─────────────────────────── F14 印度律盘：大运体系 / 流派 / 问事·年盘 ───────────────────────────

INDIA_BIRTH = {"date": "1990-06-15", "time": "08:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
               "zodiacal": 1, "agent_confirmed_settings": True}


def _md(lord: str, start: str, end: str, years: float, a0: int, a1: int, **extra) -> dict:
    return {"lord": {"label": lord}, "start": start, "end": end, "years": years, "startAge": a0, "endAge": a1, **extra}


# 后端 jyotish.dasha 的真实形状（webindiasrv 同字段；年份取 1990-06-15 上海 live 实抓的前两运）。
_JYOTISH = {"dasha": {
    "vimshottari": {"available": True, "moonNakshatra": {"label": "危"}, "firstLord": {"label": "罗睺"},
                    "firstElapsedYears": 11.6, "firstBalanceYears": 6.4,
                    "mahadashas": [_md("罗睺", "1978-11-03", "1996-11-03", 18, -12, 6, birthBalance=True),
                                   _md("木星", "1996-11-03", "2012-11-03", 16, 6, 22)]},
    "yogini": {"available": True, "moonNakshatra": {"label": "危"}, "firstLord": {"label": "木星"},
               "firstElapsedYears": 2.0, "firstBalanceYears": 1.0,
               "mahadashas": [_md("木星", "1988-06-30", "1991-07-01", 3, -2, 1, birthBalance=True),
                              _md("火星", "1991-07-01", "1995-07-01", 4, 1, 5)]},
}}


def _india_client() -> RecordingClient:
    def india(payload: dict) -> dict:
        base = copy.deepcopy(FakeClient().call("/chart", payload))
        base["jyotish"] = copy.deepcopy(_JYOTISH)
        return base
    return RecordingClient(routes={"/india/chart": india})


def test_india_dasha_system_selects_the_dasha_section(tmp_path: Path) -> None:
    """上游 buildIndiaSnapshotText:1183-1187 → buildDashaSnapshotLines(chartObj, indiaDashaSystem)（IndiaChart.js:429-494，
    vendored 逐字）：体系行 + 该体系树的 GFM 大运表。负向对照：旧 Python 移植只认 Vimshottari（dashaSystem 透传也恒出它），
    且是旧版平铺格式。"""
    service = _service(tmp_path, _india_client())
    text = service.run_tool("india_chart", {**INDIA_BIRTH, "dashaSystem": "yogini"}, save_result=False).data["snapshot_text"]
    assert _section(text, "大运Dasha").strip() == "\n".join([
        "系统：Yogini（36 年 · 8 女神）",
        "月宿：危（宿主星 木星）",
        "首运：已历 2.0 年、余 1.0 年",
        "大运序列：",
        "| 标记 | 主星 | 起 | 止 | 年数 | 年龄段 |",
        "| --- | --- | --- | --- | --- | --- |",
        "| · | 木星 | 1988-06-30 | 1991-07-01 | 3.0 年 | -2–1 岁 |",
        "|  | 火星 | 1991-07-01 | 1995-07-01 | 4.0 年 | 1–5 岁 |",
    ])
    default = service.run_tool("india_chart", INDIA_BIRTH, save_result=False).data["snapshot_text"]
    assert _section(default, "大运Dasha").startswith("系统：Vimshottari（120 年周期）\n月宿：危（宿主星 罗睺）")
    bad = service.run_tool("india_chart", {**INDIA_BIRTH, "dashaSystem": "decennial"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.india_chart_invalid_setting"


def test_india_school_line_presets_and_prashna_fields(tmp_path: Path) -> None:
    """流派行（buildIndiaSnapshotText:1170-1174）+ 无头预设（resolveIndiaHeadlessParams:1197-1213：未给岁差/宫制按派补）；
    问事族只在 prashnaTime 在场时下发且问时数缺省 1（fieldsToParams:125-142，[Q-126/T-34]）；年盘异地须经纬齐备（:106-112）；
    展示体系 akkg 不下发 dashaSystem（:81）。负向对照：旧代码无流派行、不补预设、问时数缺 → 后端 KP 问事整段空。"""
    client = _india_client()
    service = _service(tmp_path, client)
    result = service.run_tool(
        "india_chart",
        {**INDIA_BIRTH, "indiaSchool": "kp", "dashaSystem": "akkg", "prashnaTime": "2026/09/01 10:00:00",
         "prashnaMatter": "career", "varshaLat": "39n54"},
        save_result=False,
    )
    assert result.ok, result.error
    sent = client.bodies("/india/chart")[0]
    assert (sent["indiaAyanamsa"], sent["indiaHsys"], sent["hsys"]) == ("krishnamurti", 3, 3)
    assert sent["prashnaNumber"] == 1 and sent["prashnaMatter"] == "career"
    assert "dashaSystem" not in sent and "varshaLat" not in sent and "indiaSchool" not in sent
    info = _section(result.data["snapshot_text"], "起盘信息")
    assert info.startswith("流派：KP 系统（相位范式 significator 链 · 主运取向 Vimshottari）\n当前分盘：命盘\n分盘：D1\n")
    assert "恒星黄道岁差：Krishnamurti" in info  # 预设岁差同时落进快照口径行（请求与快照同源）
    # 没起卦 → 问事族一个都不下发。
    client.calls.clear()
    service.run_tool("india_chart", {**INDIA_BIRTH, "prashnaMatter": "career"}, save_result=False)
    assert "prashnaMatter" not in client.bodies("/india/chart")[0]


def test_india_school_presets_mirror_the_vendored_table() -> None:
    """Python 侧只镜像 INDIA_SCHOOL_DEFAULTS 的 ayanamsa/hsys 两列（取盘前要用、JS 在取盘后才跑）；镜像必须与
    vendored india/indiaConst.js（curated，upstream_sha256 看守 AstroConst.js）逐值一致 —— 上游改表这里先红。"""
    import subprocess

    from horosa_skill.service import _INDIA_SCHOOL_PRESETS

    core = Path(__file__).resolve().parents[1] / "horosa-core-js"
    script = (
        "import('./src/vendor/india/indiaConst.js').then((m)=>{const o={};"
        "Object.keys(m.INDIA_SCHOOL_DEFAULTS).forEach((k)=>{o[k]=[m.INDIA_SCHOOL_DEFAULTS[k].ayanamsa,m.INDIA_SCHOOL_DEFAULTS[k].hsys];});"
        "console.log(JSON.stringify(o));});"
    )
    out = subprocess.run(["node", "-e", script], cwd=core, capture_output=True, text=True, check=True).stdout
    assert {k: tuple(v) for k, v in json.loads(out).items()} == _INDIA_SCHOOL_PRESETS


# ─────────────────────────── F4 占星地图：引擎口径 / CCG / 图层 / 事件时区 ───────────────────────────

ACG_BIRTH = {"date": "1990-06-15", "time": "08:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
             "agent_confirmed_settings": True}


def _acg_response(payload: dict) -> dict:
    """后端 ACGraph.compute 的形状：meta 回显**归一后的**有效口径（ACGraph.py:239-340 值域外回缺省），两星角化线 + 本地空间
    方位（lines.lsAz）+ 一条日月交映；给了 ccgDate 才有 ccg 块（:354-360）。"""
    def norm(key, allowed, default):
        v = f"{payload.get(key, default)}".lower()
        return v if v in allowed else default

    def planet(mc, az, alt):
        return {"lines": {"mc": {"lon": mc}, "ic": {"lon": mc - 180}, "asc": [], "desc": [], "lsAz": {"az": az, "alt": alt}},
                "zenith": {"lat": 1.0, "lon": mc}, "oob": False}

    harmonic = int(float(payload.get("harmonic") or 1))
    draconic = norm("draconic", ("off", "mean", "true"), "off")
    resp = {
        "meta": {
            "mode": norm("mode", ("mundo", "zodiac"), "mundo"), "lsMode": norm("lsMode", ("great", "rhumb"), "great"),
            "geodetic": "sepharial", "geodeticVar": "longitude", "coord": norm("coord", ("geo", "helio", "topo"), "geo"),
            "posType": "apparent", "horizon": "geometric", "nodeType": "mean", "lilithType": "mean", "asteroids": False,
            "draconic": None if draconic == "off" else draconic, "harmonic": harmonic if harmonic > 1 else None,
            "vibration": None, "ayanamsa": None, "ayanLabel": None, "ayanVal": None, "relMode": None, "davison": None,
        },
        "planets": {"Sun": planet(120.5, 247.2, 6.9), "Moon": planet(30.0, 63.3, -18.8)},
        "parans": [{"lat": 42.5, "a": "Sun", "aEvent": "mc", "b": "Moon", "bEvent": "rise", "type": "RSCA"}],
        "crossings": [],
    }
    if payload.get("ccgDate"):
        resp["ccg"] = {"date": payload["ccgDate"], "time": payload.get("ccgTime"), "mix": payload.get("ccgMix"),
                       "planets": {"Sun": {"kind": "transit", "lon": 119.0718, "lines": {"mc": {"lon": -149.32}}}}}
    return resp


def _acg_client() -> RecordingClient:
    return RecordingClient(routes={
        "/location/acg": _acg_response,
        # T-49：带 zone 则回该时区钟面并回显 zone（webacgsrv.acgevent）。
        "/location/acgevent": lambda p: {"kind": p.get("kind"), "jd": 2448094.625, "date": "1990/07/22",
                                         "time": "11:02:12", "zone": p.get("zone") or "+00:00"},
    })


def test_acg_forwards_engine_keys_and_uses_the_upstream_map_section(tmp_path: Path) -> None:
    """上游 AstroAcg.genParams（AstroAcg.js:348-372）逐键下发；落点宫制缺省 placidus（:130/184，此前后端缺省 whole）；
    [占星地图] = vendored buildAcgSectionText（acgSnapshot.js:77-190，口径头行读后端 meta）。本命盘带页面同一套
    fields（黄道/岁差/古典键）。负向对照：旧 runner 只白名单 4 个地图键、本命盘只传 7 键、[占星地图] 是本仓自拟表。"""
    client = _acg_client()
    service = _service(tmp_path, client)
    result = service.run_tool("acg", {**ACG_BIRTH, "coord": "topo", "draconic": "true", "harmonic": 5, "cuspLines": True,
                                      "stars": False, "zodiacal": 1, "siderealAyanamsa": "raman", "cazimiOrb": 1},
                              save_result=False)
    assert result.ok, result.error
    sent = client.bodies("/location/acg")[0]
    assert (sent["coord"], sent["draconic"], sent["harmonic"], sent["cuspLines"], sent["stars"], sent["hsys"]) == (
        "topo", "true", "5", "1", "0", "placidus")
    natal = client.bodies("/chart")[0]
    assert (natal["zodiacal"], natal["siderealAyanamsa"], natal["cazimiOrb"]) == (1, "raman", 1)
    assert "coord" not in natal and "harmonic" not in natal
    body = _section(result.data["snapshot_text"], "占星地图")
    assert body.startswith("口径 本体(in-mundo·真黄纬) · 坐标系 站心 · 龙黄道 真交点 · 谐波 H5\n主要行星角化线")
    assert "- 太阳:MC 120.50°E / IC 59.50°W / ASC — / DSC —" in body


def test_acg_event_feeds_ccg_with_zone_and_layers_reach_the_snapshot(tmp_path: Path) -> None:
    """世运事件 → CCG 全行运（pickMundane AstroAcg.js:386-404，zone 随本命时区 T-49）；快照图层 paranMode / showLS
    （snapshotUiState :277-287 → acgSnapshot.js ◆ 子块）；后端不认的口径值经 meta 回显比对告警（不静默）。"""
    client = _acg_client()
    service = _service(tmp_path, client)
    result = service.run_tool("acg", {**ACG_BIRTH, "eventKind": "solar_eclipse", "paranMode": "lum", "showLS": True,
                                      "coord": "bogus"}, save_result=False)
    assert result.ok, result.error
    assert client.bodies("/location/acgevent")[0]["zone"] == "+08:00"
    sent = client.bodies("/location/acg")[0]
    assert (sent["ccgDate"], sent["ccgTime"], sent["ccgMix"]) == ("1990/07/22", "11:02:12", "transit")
    text = result.data["snapshot_text"]
    body = _section(text, "占星地图")
    assert "CCG 时间地图(1990/07/22 11:02:12 · 全行运):\n- 行运太阳:MC 149.32°W(黄经 119.0718°)" in body
    assert "◆ 本地空间线(画法 大圆;" in body and "| 太阳 | 247.2° | 6.9° |" in body
    assert "◆ 行星交映(仅日月对,同图 1° 去重,共 1 条纬线):" in body and "| 太阳 | 中天 | 月亮 | 升 | 42.50°N |" in body
    assert _section(text, "事件时刻").startswith("日食（next）：1990/07/22 11:02:12 +08:00；已填入 CCG 全行运通道")
    assert any("coord='bogus'" in w for w in result.warnings), result.warnings

    client.calls.clear()
    service.run_tool("acg", {**ACG_BIRTH, "clickLat": 39.9, "clickLon": 116.4}, save_result=False)
    point = client.bodies("/location/acgpoint")[0]
    assert point["hsys"] == "placidus" and point["mode"] == "mundo" and point["orb"] == 2


# ─────────────────────────── F5 世运：规则集 / 页面级覆盖 / 吠陀三键 / 入宫盘口径 ───────────────────────────


def test_mundane_ruleset_head_and_cards_follow_the_ruleset(tmp_path: Path) -> None:
    """上游 buildAiSnapshot（MundaneMain.js:2852-2860）头行「规则集：」+ 入境主管制页面级覆盖行；buildMundaneCardSections
    （:242-262）按 rulesetConfig(ex.mundaneRuleset) 与覆盖键算 [年盘概要] 的主管期。桩盘上升处女（变动座）：
    托勒密古典 = quarterly → ingressGovernance 半年 + 须再起秋分盘；modern 缺省 = aries_annual 全年。入宫盘带页面口径键。
    负向对照：旧 runner 不认 mundaneRuleset（头无「规则集」、卡恒 modern）、入宫盘请求只带 11 个固定键。"""
    from test_sync311_mundane_election import MUNDANE, ScriptedClient

    client = ScriptedClient()
    service = _service(tmp_path, client)
    env = service.run_tool("mundane", {**MUNDANE, "mundaneRuleset": "ptolemaic", "zodiacal": 1, "siderealAyanamsa": "lahiri",
                                       "cazimiOrb": 1}, save_result=False)
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    assert _section(text, "世俗入宫").splitlines()[:3] == ["规则集：托勒密古典", "入宫节气：春分", "年份：2025"]
    card = _section(text, "年盘概要").splitlines()
    assert card[2] == "本盘上升 变动星座 · 托勒密古典 → 主管约 6 个月；季度递归 → 须再起 秋分·天秤 入境盘各管一季"
    assert card[3] == "四轴变动座 → 白羊盘主管半年,须再起秋分(天秤)入境"
    ingress_chart = next(p for e, p in client.calls if e == "/chart" and str(p.get("date")).replace("/", "-") == "2025-03-20")
    assert (ingress_chart["zodiacal"], ingress_chart["siderealAyanamsa"], ingress_chart["cazimiOrb"]) == (1, "lahiri", 1)
    assert "mundaneRuleset" not in ingress_chart

    override = service.run_tool("mundane", {**MUNDANE, "mundaneIngressRule": "capricorn_year"}, save_result=False)
    head = _section(override.data["snapshot_text"], "世俗入宫").splitlines()
    assert head[0] == "规则集：现代(Carter–Campion)" and "入境主管制：摩羯优先(冬至为年首)（页面级覆盖）" in head
    bad = service.run_tool("mundane", {**MUNDANE, "mundaneRuleset": "hellenistic"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.mundane_invalid_setting"


def test_mundane_vedic_founding_inputs_reach_the_vedic_cards(tmp_path: Path) -> None:
    """吠陀世运三键（MundaneMain.js:441-449）：建国年 + 建国上升 → Muntha 敏感点（munthaSign 每年顺进一座）；年长 360。
    梅沙入境年 2025、建国 1947 → 盘龄 78 → 金牛起顺进 78 座 = 78 mod 12 = 6 → 天蝎。负向对照：旧代码不转交三键（无 Muntha 行、年长恒现代）。"""
    from test_sync311_mundane_election import MUNDANE, ScriptedClient

    service = _service(tmp_path, ScriptedClient(vedic=True))
    env = service.run_tool("mundane", {**MUNDANE, "mundaneType": "vedicmundane", "vedicFoundingYear": 1947,
                                       "vedicNatalAsc": "taurus", "vedicDashaYearLen": 360}, save_result=False)
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    assert "Muntha 敏感点：天蝎（建国上升每年顺进一座,盘龄 78）" in _section(text, "吠陀世运·年度盘")
    assert _section(text, "世运大运").startswith("（Vimshottari · 年长口径 360（传统））")


# ─────────────────────────── F17 古典导出子选项：互容接纳过滤 / 埃及历七轴 / 显赫计分判定项 ───────────────────────────

RECEPTION_FIX = json.loads((FIXTURES / "sync311_western_reception_charts.json").read_text(encoding="utf-8"))


def _info_block(text: str, head: str, stop: str) -> list[str]:
    lines = _section(text, "信息").splitlines()
    at = lines.index(head)
    end = lines.index(stop, at + 1) if stop in lines[at + 1:] else len(lines)
    return lines[at + 1:end]


def test_only_ruler_exalt_reception_filters_info_lines(tmp_path: Path) -> None:
    """上游 astroAiSnapshot.js:221-245 keepReceptionLine/keepMutualLine + :558 resolveOnlyRulerExaltReception（全局
    showOnlyRulExaltReception=1）。live 夹具（strongRecption=0 缺省档）：正接纳 6 条里 3 条供给方只有次级尊贵
    （夜三分/界/面），正互容 4 对里 水–火 一对两方都无本垣/擢升。负向对照：旧 _keep_reception_line 恒 True、互容不滤。"""
    fix = RECEPTION_FIX["info"]
    client = RecordingClient(chart_for=lambda payload: fix["chart"])
    service = _service(tmp_path, client)
    base = {**fix["request"], "date": fix["request"]["date"].replace("/", "-"), "agent_confirmed_settings": True}
    plain = service.run_tool("chart", base, save_result=False)
    only = service.run_tool("chart", {**base, "showOnlyRulExaltReception": 1}, save_result=False)
    assert plain.ok and only.ok, (plain.error, only.error)
    p_normal = _info_block(plain.data["snapshot_text"], "正接纳：", "邪接纳：")
    o_normal = _info_block(only.data["snapshot_text"], "正接纳：", "邪接纳：")
    assert len(p_normal) == 6 and len(o_normal) == 3
    assert all("(本垣" in line for line in o_normal), o_normal  # 留下的三条供给方皆本垣（ruler）
    assert [line for line in p_normal if line not in o_normal] == [
        line for line in p_normal if "本垣" not in line and "擢升" not in line
    ]
    p_mut = _info_block(plain.data["snapshot_text"], "正互容：", "邪互容：")
    o_mut = _info_block(only.data["snapshot_text"], "正互容：", "邪互容：")
    assert len(p_mut) == 4 and len(o_mut) == 3
    dropped = [line for line in p_mut if line not in o_mut]
    assert len(dropped) == 1 and dropped[0].startswith("水") and "火" in dropped[0]


def test_only_ruler_exalt_reception_also_filters_apriori_links(tmp_path: Path) -> None:
    """上游 astroPatternOverview.js:197-207：格局速览「先验权力」的联结取自滤后的互容/接纳（与 [信息] 详细行同口径）。
    live 夹具（整宫，上升射手）：夜生，月（擢升+夜三分）与 木（共管三分+面）互容，月主 8 宫（巨蟹）、木主 1 宫（射手）
    → 先验权力(8·1)；木方无本垣/擢升 →
    开关开时该互容被滤，先验权力行随之消失。负向对照：旧 _pattern_overview 读未滤的 m/r。"""
    fix = RECEPTION_FIX["apriori"]
    service = _service(tmp_path, RecordingClient(chart_for=lambda payload: fix["chart"]))
    base = {**fix["request"], "date": fix["request"]["date"].replace("/", "-"), "agent_confirmed_settings": True}
    plain = service.run_tool("chart", base, save_result=False)
    only = service.run_tool("chart", {**base, "showOnlyRulExaltReception": True}, save_result=False)
    assert plain.ok and only.ok, (plain.error, only.error)
    # 格局速览是 [古典] 段的「古典格局」子块（上游 astroAiSnapshot.js:1486-1490 buildClassicalSection），不在 [古典格局] 段。
    p = _section(plain.data["snapshot_text"], "古典").splitlines()
    o = _section(only.data["snapshot_text"], "古典").splitlines()
    assert "先验权力：月互容木(8·1)·夜生·八杀朝天大贵" in p
    assert not any(line.startswith("先验权力") for line in o)
    assert [line for line in p if line not in o] == ["先验权力：月互容木(8·1)·夜生·八杀朝天大贵"]


def test_egypt_school_axes_reach_the_egypt_section(tmp_path: Path) -> None:
    """上游 astroAiSnapshot.js:1733 `egyptSchoolFromFields(fields) || currentEgyptSchool()`；七轴取值锚 egyptianSchools.EGYPT_SCHOOL_AXES。
    盘 = core-js chart_traditional（日 双子 11°45′ → 双子第二旬）。迦勒底面主序 双子 I 木 / II 火 / III 日；三分性旬星制取同三分性
    三座（双子/天秤/水瓶）庙主 → II = 天秤之主 金（egyptianData.js:140 triplicityDecanRuler）。负向对照：旧 runner 不转交 egypt_*，
    段恒为默认档（无「所用口径」行、日面主恒火）。"""
    client = RecordingClient(chart_for=lambda payload: CHART_TRADITIONAL)
    service = _service(tmp_path, client)
    plain = service.run_tool("chart", BIRTH, save_result=False)
    school = service.run_tool("chart", {**BIRTH, "egypt_decanRuler": "triplicity", "egypt_decanNaming": "coptic"}, save_result=False)
    assert plain.ok and school.ok, (plain.error, school.error)
    p = _section(plain.data["snapshot_text"], "埃及历").splitlines()
    s = _section(school.data["snapshot_text"], "埃及历").splitlines()
    assert p[0] == "◆ 各行星落旬" and not any(line.startswith("◆ 所用口径") for line in p)
    assert s[0] == "◆ 所用口径：旬主星制=三分性旬星；旬名录传统=科普特-希腊名"
    p_sun = next(line for line in p if line.startswith("日："))
    s_sun = next(line for line in s if line.startswith("日："))
    assert "·面主火·" in p_sun and "·面主金·" in s_sun
    bad = service.run_tool("chart", {**BIRTH, "egypt_starClock": "sundial"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.egypt_invalid_setting"


def test_eminence_predominator_options_reach_the_eminence_section(tmp_path: Path) -> None:
    """上游 astroAiSnapshot.js:1716-1726 predOpts → astroClassicalDerived.computePredominator（:488-547）+ 七射线（:595-601）。
    盘 = chart_traditional：昼生，日在 9 宫、月在 4 宫。缺省有利宫集 1·4·5·7·10·11 不含 9；宽集 1·2·4·5·7·9·10·11 含 9 →
    太阳多一判据「有利宫(9)」。负向对照：旧 classical_derived 不收 predOpts（恒缺省集、恒庙主派、七射线恒关）。"""
    client = RecordingClient(chart_for=lambda payload: CHART_TRADITIONAL)
    service = _service(tmp_path, client)
    plain = service.run_tool("chart", BIRTH, save_result=False)
    tuned = service.run_tool("chart", {**BIRTH, "busyPlaces": "1,2,4,5,7,9,10,11", "domicileMasterMethod": "bound",
                                       "dynamicalDivisions": 1, "rayWeighting": "weighted"}, save_result=False)
    assert plain.ok and tuned.ok, (plain.error, tuned.error)
    p = _section(plain.data["snapshot_text"], "古典·显赫计分")
    t = _section(tuned.data["snapshot_text"], "古典·显赫计分")
    p_pred = next(line for line in p.splitlines() if line.startswith("主宰光体"))
    t_pred = next(line for line in t.splitlines() if line.startswith("主宰光体"))
    assert "有利宫(9)" not in p_pred and "当前判法=庙主派" in p_pred and "动力学分区加权" not in p_pred
    assert "有利宫(9)" in t_pred and "当前判法=界主派" in t_pred and ";动力学分区加权" in t_pred
    assert "七射线分布" not in p and "七射线分布(加权 · 灵学体系推算)" in t
    bad = service.run_tool("chart", {**BIRTH, "busyPlaces": "1,2,3"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.chart_invalid_setting"


# ─────────────────────────── F16/F20 文档：宫制 0–24 / 词表进 guidance / 汉堡中点盘键 ───────────────────────────


def test_guidance_vocab_matches_the_vendored_engine_tables() -> None:
    """options_keys 的手写词表（western_options_doc）逐键逐名对 vendored 引擎模块导出（node 直接 import）——上游改表这里先红。
    负向对照：旧代码无 western_options_doc 模块（导入即红）。"""
    import subprocess

    from horosa_skill import western_options_doc as W

    core = Path(__file__).resolve().parents[1] / "horosa-core-js"
    script = """
    const [sig, hs, tm, ws, gd, ic, mr] = await Promise.all([
      import('./src/vendor/divination/horary/significators.js'), import('./src/vendor/divination/horary/horarySchools.js'),
      import('./src/vendor/divination/data/topicMaster.js'), import('./src/vendor/divination/election/westernSchools.js'),
      import('./src/vendor/guolao/guolaoData.js'), import('./src/vendor/india/indiaConst.js'), import('./src/vendor/mundane/ruleset.js')]);
    console.log(JSON.stringify({
      categories: Object.entries(sig.CATEGORY_DEF).map(([k, v]) => [k, v.quesitedLabel, v.quesitedHouse]),
      schools: hs.HORARY_SCHOOL_ORDER.map((k) => [k, hs.HORARY_SCHOOLS[k].cn, hs.HORARY_SCHOOLS[k].backend]),
      params: hs.HORARY_PARAM_SPEC.map((s) => s.key),
      topics: Object.entries(tm.TOPIC_MASTER).map(([k, v]) => [k, v.cn]),
      electionSchools: ws.WEST_SCHOOL_ORDER.map((k) => [k, ws.WEST_SCHOOLS[k].cn]),
      su28: Object.entries(gd.SU28_MODE_LABEL).map(([k, v]) => [Number(k), v]),
      dasha: ic.INDIA_DASHA_SYSTEM_OPTIONS.map((o) => [o.value, o.label]),
      indiaSchools: ic.INDIA_SCHOOL_OPTIONS.map((o) => [o.value, o.label, ic.INDIA_SCHOOL_DEFAULTS[o.value].ayanamsa,
                                                        ic.INDIA_SCHOOL_DEFAULTS[o.value].hsys]),
      rulesets: mr.MUNDANE_RULESETS.map((r) => [r.key, r.label]),
    }));
    """
    out = subprocess.run(["node", "--input-type=module", "-e", script], cwd=core, capture_output=True, text=True, check=True)
    eng = json.loads(out.stdout)
    assert [tuple(x) for x in eng["categories"]] == list(W.HORARY_CATEGORIES)
    assert [tuple(x) for x in eng["topics"]] == list(W.ELECTION_TOPICS)
    assert [tuple(x) for x in eng["electionSchools"]] == list(W.ELECTION_SCHOOLS)
    assert tuple(eng["params"]) == W.HORARY_PARAM_KEYS
    assert [tuple(x) for x in eng["su28"]] == list(W.GUOLAO_SU28_MODES)
    assert [tuple(x) for x in eng["dasha"]] == list(W.INDIA_DASHA_SYSTEMS)
    assert [tuple(x) for x in eng["indiaSchools"]] == list(W.INDIA_SCHOOLS)
    assert [tuple(x) for x in eng["rulesets"]] == list(W.MUNDANE_RULESETS)

    def fields_text(b: dict) -> str:  # 流派起盘字段摘要的生成规则（horaryBackendFields 同键）
        trip = "托勒密" if b["tripSystem"] == "ptolemaic" else "多罗修斯"
        bodies = "七政" if b["tradition"] == 1 else "含三王星"
        lot = "福点夜反转" if b["lotReversal"] == 1 else "福点不反转"
        return f"hsys {b['hsys']} · 界系 {b['termsVariant']} · {trip}三分 · {bodies} · {lot}"

    assert [(k, cn, fields_text(b)) for k, cn, b in eng["schools"]] == list(W.HORARY_SCHOOLS)


def test_guidance_documents_house_systems_hidden_knobs_and_gate_vocab() -> None:
    """F16：宫制 0–24 全表进 guidance（options_keys.hsys）与校验层描述，广告层仍只背 0–8（预算）；F20：卜卦 20 类 / 7 流派、
    关系盘 0–4 进闸门问题的 options/values；schema 里写「见 guidance」的隐藏旋钮在 options_keys 里都查得到。
    负向对照：旧 guidance 无 options_keys、BirthInput.hsys 描述只列 0–8、卜卦类别只 14 个且不问流派、关系盘只「星阙默认」。"""
    from horosa_skill.agent_guidance import TOOL_GUIDANCE, build_agent_guidance
    from horosa_skill.astro_rulers import HOUSE_SYSTEM_LABELS
    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.schemas.tools import BirthInput
    from horosa_skill.surfaces.mcp_schema import advertise_hidden_fields

    assert len(HOUSE_SYSTEM_LABELS) == 25
    chart_keys = build_agent_guidance(tool_name="chart")["tools"]["chart"]["options_keys"]
    for index, label in HOUSE_SYSTEM_LABELS.items():
        assert f"{index}={label}" in chart_keys["hsys"]
        assert f"{index}={label}" in (BirthInput.model_fields["hsys"].description or "")
    assert {"showOnlyRulExaltReception", "egypt_decanRuler", "busyPlaces", "rayWeighting"} <= set(chart_keys)
    for tool_name, definition in TOOL_DEFINITIONS.items():
        hidden = advertise_hidden_fields(definition.input_model)
        if hidden:
            keys = build_agent_guidance(tool_name=tool_name)["tools"][tool_name].get("options_keys") or {}
            assert hidden <= set(keys), (tool_name, sorted(hidden - set(keys)))
    horary = {item["field"]: item for item in TOOL_GUIDANCE["horary"]["ask_if_missing"]}
    assert len(horary["category"]["values"]) == 20 and "lost_animal" in horary["category"]["values"]
    assert horary["school"]["values"] == ["classical", "renaissance", "strict", "sequence", "hellenistic", "medieval", "modern"]
    relative = {item["field"]: item for item in TOOL_GUIDANCE["relative"]["ask_if_missing"]}
    assert relative["relative"]["values"] == [0, 1, 2, 3, 4] and relative["relative"]["options"][4] == "马克斯盘"


def test_germany_uranian_keys_are_declared_validated_and_forwarded(tmp_path: Path) -> None:
    """F20：上游挂载齿轮 techniqueMountSettings.js:1213-1238 → AstroMidpoint.js:301-307 下发 /germany/midpoint 的七键
    （school/orb/personalOrb/strictFactors/frames/declination/davison；后端 webgermanysrv.midpoint 读）。声明后 MCP 扁平面
    顶层照收、流派写错报错。负向对照：旧 GermanyInput 未声明 → 扁平面签名无这些键、school 写错静默当 classic。"""
    from horosa_skill.schemas.tools import GermanyInput
    from horosa_skill.surfaces.mcp_server import _signature_for_input_model

    keys = {"school", "orb", "personalOrb", "strictFactors", "frames", "declination", "davison"}
    assert keys <= set(_signature_for_input_model(GermanyInput).parameters)
    client = RecordingClient()
    service = _service(tmp_path, client)
    with pytest.raises(ToolValidationError) as bad:
        service.run_tool("germany", {**BIRTH, "school": "sideways"}, save_result=False)
    assert bad.value.code == "tool.invalid_payload"
    env = service.run_tool("germany", {**BIRTH, "school": "cosmo", "orb": 1.2, "strictFactors": True, "declination": False},
                           save_result=False)
    assert env.ok, env.error
    sent = client.bodies("/germany/midpoint")[-1]
    assert (sent["school"], sent["orb"], sent["strictFactors"], sent["declination"]) == ("cosmo", 1.2, True, False)
