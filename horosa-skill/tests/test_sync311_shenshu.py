"""sync311 神数 / 占卜 chunk — audit F1–F18 (2026-09-24), one guard per finding.

Every assertion here pins an **upstream** behaviour (file:line cited next to it) and was checked to go red on
the pre-fix code (base 034eb57): the offline cases capture the exact request the skill sends (so a wrong key /
missing seed / wrong default fails on the payload itself, not on a section header), the JS cases run the real
vendored engine, and the live cases (``requires_chart`` / ``requires_runtime``) show "改参数结果必变" against
the vendored v3.11.1+ backend.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest
from test_local_js_tools import make_service, requires_chart, requires_runtime
from test_service import FakeClient, FakeJsClient

from horosa_skill.agent_guidance import build_agent_guidance, validate_agent_preflight
from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

CONFIRM = {"agent_confirmed_settings": True}
BASE = {"date": "1998-02-20", "time": "20:48:00", **CONFIRM}
PLACE = {"zone": "+08:00", "lat": "31n13", "lon": "121e28"}
# 上游无头起课种子（TaiXuanMain.js:141-152 / JingJueMain.js:105-117）：((1998·10000+2·100+20)·10000+20·100+48) mod 1e9
SEED_19980220_2048 = 802202048
SHENSHU = ("wangji", "wuzhao", "taixuan", "jingjue", "shenyishu", "shaozi", "tieban", "fendjing",
           "beiji", "nanji", "chunzi", "xianqin", "cetian", "qizhengkin")


class RecordingClient(FakeClient):
    """FakeClient that records every request and lets a test override single endpoints with realistic bodies."""

    def __init__(self, overrides: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []
        self.overrides = overrides or {}

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, json.loads(json.dumps(payload, ensure_ascii=False))))
        if endpoint in self.overrides:
            return self.overrides[endpoint](payload)
        return super().call(endpoint, payload)

    def sent(self, endpoint: str) -> list[dict]:
        return [payload for called, payload in self.calls if called == endpoint]


class RecordingFakeJs(FakeJsClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []

    def run(self, tool_name: str, payload: dict) -> dict:
        self.calls.append((tool_name, json.loads(json.dumps(payload, ensure_ascii=False))))
        return super().run(tool_name, payload)


class RecordingRealJs(HorosaJsEngineClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.calls: list[tuple[str, dict]] = []

    def run(self, tool_name: str, payload: dict) -> dict:
        self.calls.append((tool_name, json.loads(json.dumps(payload, ensure_ascii=False))))
        return super().run(tool_name, payload)


def _service(tmp_path, client: RecordingClient | None = None, *, real_js: bool = False):
    settings = Settings(
        server_root="http://127.0.0.1:9",
        chart_server_root="http://127.0.0.1:9",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = client or RecordingClient()
    js = RecordingRealJs(settings) if real_js else RecordingFakeJs()
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=js), client, js


def _run(service: HorosaSkillService, tool: str, payload: dict):
    return service.run_tool(tool, payload, save_result=False)


def _section(text: str, title: str) -> str:
    lines = (text or "").split("\n")
    if f"[{title}]" not in lines:
        return ""
    start = lines.index(f"[{title}]") + 1
    body = []
    for line in lines[start:]:
        if line.startswith("[") and line.endswith("]"):
            break
        body.append(line)
    return "\n".join(body)


# ---------------------------------------------------------------- F1 / F2：荆诀 / 太玄 起筮种子


@pytest.mark.parametrize("tool", ["jingjue", "taixuan"])
def test_cast_seed_is_the_upstream_headless_minute_seed(tmp_path, tool: str) -> None:
    """F1/F2：上游无头挂载 seed = yyyyMMddHHmm mod 1e9（JingJueMain.js:105-117 / TaiXuanMain.js:141-152）。

    旧码不发 seed：荆诀后端 random.randint（webjingjuesrv.py:351）真随机；太玄后端缺省只到小时
    （webtaixuansrv.py:409 yyyyMMddHH）→ 两处 `sent["seed"]` 在旧码上都是 KeyError。
    """
    service, client, _ = _service(tmp_path)
    assert _run(service, tool, BASE).ok
    assert client.sent(f"/{tool}/pan")[-1]["seed"] == SEED_19980220_2048
    assert _run(service, tool, {**BASE, "time": "20:49:00"}).ok
    assert client.sent(f"/{tool}/pan")[-1]["seed"] == SEED_19980220_2048 + 1, "分钟级：同一小时内不同分钟必异种子"
    # 显式种子覆盖；0 是合法种子（挂载自检 F-23：旧式 `> 0` 把 0 当未设）。
    result = _run(service, tool, {**BASE, "options": {"seed": 0}})
    assert result.ok and client.sent(f"/{tool}/pan")[-1]["seed"] == 0 and result.data["seed"] == 0
    card = result.data["technique_card"]["settings"]
    assert card["seed"]["value"] == 0


# ---------------------------------------------------------------- F3 / F4：五兆


def test_wuzhao_random_cast_modes_get_a_deterministic_cast_seed(tmp_path) -> None:
    """F3：敦煌揲筮 / 以钱代筮（自动掷）后端按 castSeed 定兆（webwuzhaosrv.py:640-643），旧码从不送 → 真随机。"""
    service, client, _ = _service(tmp_path)
    for options in ({"mode": "dunhuang"}, {"mode": "qian"}):
        result = _run(service, "wuzhao", {**BASE, "options": options})
        assert result.ok, result.error
        sent = client.sent("/wuzhao/pan")[-1]
        assert sent["mode"] == options["mode"] and sent["castSeed"] == SEED_19980220_2048, sent
        assert result.data["castSeed"] == SEED_19980220_2048
    assert client.sent("/wuzhao/pan")[-1]["qianAuto"] is True, "上游 DEFAULT_OPTIONS.qianAuto=true"
    # 显式 castSeed 覆盖；非随机诸式不带种子（上游 buildPanPayload :657-661 同律）。
    assert _run(service, "wuzhao", {**BASE, "options": {"mode": "dunhuang", "castSeed": 7}}).ok
    assert client.sent("/wuzhao/pan")[-1]["castSeed"] == 7
    assert _run(service, "wuzhao", {**BASE, "options": {"mode": "qian", "qianAuto": False}}).ok
    sent = client.sent("/wuzhao/pan")[-1]
    assert "castSeed" not in sent and sent["qianThrows"] == [2, 2, 2, 2, 2, 2], "关自动掷=定六掷（上游 DEFAULT_QIAN_THROWS），后端不再逐掷走 RNG"
    assert _run(service, "wuzhao", BASE).ok
    assert "castSeed" not in client.sent("/wuzhao/pan")[-1]


def test_wuzhao_unreplayable_modes_fall_back_to_ganzhi_with_the_upstream_note(tmp_path) -> None:
    """F3：折竹/唐法的随机分爻不吃种子——上游挂载在未开手动分爻时回落干支起例，并把复现说明并入 [揲筮]
    （WuZhaoMain.js:368-394，原句逐字）。旧码把 mode=day 原样送后端 → 每次调用不同兆。"""
    realistic = (
        "[起盘]\n起盘方式：干支起盘\n\n[揲筮]\n起兆：干支\n\n[兆]\n宫位：巽"
    )
    client = RecordingClient({"/wuzhao/pan": lambda p: {"engine": "kinwuzhao", "snapshot": realistic}})
    service, client, _ = _service(tmp_path, client)
    result = _run(service, "wuzhao", {**BASE, "options": {"mode": "day"}})
    assert result.ok, result.error
    assert client.sent("/wuzhao/pan")[-1]["mode"] == "ganzhi"
    note = "复现说明：挂载无法复现随机起兆(所选「日干起盘」需开启「手动分爻复现」并填分爻数;存档亦无兆数)→ 已按干支起例"
    assert note in _section(result.data["snapshot_text"], "揲筮"), "复现说明须并入 [揲筮] 段（上游 appendReplayNote）"
    assert any("日干起盘" in warning for warning in result.warnings), "回落不许静默"
    manual = _run(service, "wuzhao", {**BASE, "options": {"mode": "day", "manual": True}})
    sent = client.sent("/wuzhao/pan")[-1]
    assert manual.ok and sent["mode"] == "day" and sent["manual"] is True and sent["manualSplits"] == [18, 8, 5, 2, 1, 1]
    assert "复现说明" not in manual.data["snapshot_text"]


def test_wuzhao_gender_reaches_the_backend_as_male_female(tmp_path) -> None:
    """F4：五兆后端只认 'male'/'female'（webwuzhaosrv.py:497-499）。输入归一化把嵌套 options.gender 的
    'female' 改成 0、顶层 gender 本就是 1/0 → 旧码送去的永远不是后端认得的值（行年/年立恒留白）。"""
    service, client, _ = _service(tmp_path)
    assert _run(service, "wuzhao", {**BASE, "gender": 0}).ok
    assert client.sent("/wuzhao/pan")[-1]["gender"] == "female"
    assert _run(service, "wuzhao", {**BASE, "options": {"gender": "male"}}).ok
    assert client.sent("/wuzhao/pan")[-1]["gender"] == "male"
    assert _run(service, "wuzhao", BASE).ok
    assert client.sent("/wuzhao/pan")[-1]["gender"] == "", "未给性别 = 上游缺省「未指定」"


# ---------------------------------------------------------------- F5 / F16：闸门


def test_gate_asks_gender_for_beiji_nanji_chunzi() -> None:
    """F5：北极（大运顺逆）/南极（大运干支）/蠢子数（乾坤码）按性别出不同盘（live 实测见下），旧闸从不问。"""
    for tool in ("beiji", "nanji", "chunzi"):
        verdict = validate_agent_preflight(tool, {"date": "1990-01-01", "time": "12:00:00"})
        asked = {item["field"]: item for item in verdict["ask_if_missing"]}
        assert asked.get("gender", {}).get("values") == [1, 0], tool
    assert "gender" not in {i["field"] for i in validate_agent_preflight("fendjing", {"date": "1990-01-01"})["ask_if_missing"]}


def test_gate_asks_zone_where_year_month_pillars_depend_on_it(tmp_path) -> None:
    """F16：铁板/邵子/蠢子的权威四柱（kinastro_common.authoritative_pillars）与太玄（_zone_to_hours）按时区
    定立春/节气——live：1990-02-04 10:00 +08:00→己巳年、-05:00→庚午年。旧闸不问时区，静默按 +08:00。"""
    service, client, _ = _service(tmp_path)
    assert _run(service, "taixuan", {**BASE, "zone": "-05:00"}).ok
    assert client.sent("/taixuan/pan")[-1]["zone"] == "-05:00", "问到的时区必须真送到（webtaixuansrv.py:415）"
    for tool in ("tieban", "shaozi", "chunzi", "taixuan"):
        asked = {i["field"] for i in validate_agent_preflight(tool, {"date": "1990-01-01", "time": "12:00:00"})["ask_if_missing"]}
        assert "zone" in asked, tool
        given = {i["field"] for i in validate_agent_preflight(tool, {"date": "1990-01-01", "time": "12:00:00", "zone": "+08:00"})["ask_if_missing"]}
        assert "zone" not in given, tool
    assert "zone" not in {i["field"] for i in validate_agent_preflight("xianqin", {"date": "1990-01-01"})["ask_if_missing"]}


# ---------------------------------------------------------------- F6：options 键表 / 回执 / 类型


def test_shenshu_unknown_options_are_receipted_and_not_forwarded(tmp_path) -> None:
    service, client, _ = _service(tmp_path)
    result = _run(service, "shaozi", {**BASE, "gender": 1, "options": {"useKey": "0", "bogusKnob": 1}})
    assert result.ok, result.error
    sent = client.sent("/shaozi/pan")[-1]
    # 布尔陷阱：后端 bool(data.get("useKey", True))（webshaozisrv.py:173）——"0" 为真。归一成 int 0。
    assert sent["useKey"] == 0 and "bogusKnob" not in sent
    assert result.data["params_ignored"] == ["bogusKnob"] and "useKey" in result.data["params_applied"]
    assert any("bogusKnob" in warning for warning in result.warnings)
    # 旧 options 是整包并进请求体：写在 options 里的核心键（gender/zone…）照收（顶层未给时提升为顶层），不算「未识别」。
    promoted = _run(service, "tieban", {**BASE, "options": {"gender": 0, "zone": "-05:00"}})
    sent = client.sent("/tieban/pan")[-1]
    assert (sent["gender"], sent["zone"]) == (0, "-05:00")
    assert promoted.data["params_ignored"] == [] and {"gender", "zone"} <= set(promoted.data["params_applied"])


def test_shenshu_option_type_errors_are_structured(tmp_path) -> None:
    service, _, _ = _service(tmp_path)
    bad = _run(service, "beiji", {**BASE, "gender": 1, "options": {"beijiKe": "x"}})
    assert bad.ok is False and bad.error.code == "tool.shenshu_invalid_option"
    assert bad.error.details["key"] == "beijiKe"
    bad = _run(service, "wuzhao", {**BASE, "options": {"mode": "random"}})
    assert bad.ok is False and bad.error.code == "tool.shenshu_invalid_option"


def test_shenshu_top_level_knobs_are_accepted_and_generic_keys_are_quiet(tmp_path) -> None:
    """顶层写法（CLI / request 逃生舱）与 options 同收；dispatch 灌来的 BirthInput 通用键不当成写错的旋钮。"""
    service, client, _ = _service(tmp_path)
    assert _run(service, "jingjue", {**BASE, "seed": 5}).ok
    assert client.sent("/jingjue/pan")[-1]["seed"] == 5
    quiet = _run(service, "wangji", {**BASE, "hsys": 0, "zodiacal": 0, "ad": 1, "timeAlg": 0, "tradition": False})
    assert quiet.ok and quiet.data["params_ignored"] == []


def test_guidance_documents_every_shenshu_options_table() -> None:
    for tool in SHENSHU:
        keys = build_agent_guidance(tool_name=tool)["tools"][tool].get("options_keys") or {}
        assert keys, tool
    # 审计点名的 v3.11 新后端键全部在表（webnanjisrv/webchunzisrv/webxianqinsrv/webwuzhaosrv/webcetiansrv 读键）。
    expect = {
        "nanji": {"nanjiDay", "nanjiDegree", "nanjiHourZhi", "nanjiLunarYear", "nanjiPasswordCode", "nanjiSolarMonth"},
        "chunzi": {"chunziLunarDay", "chunziLunarMonth", "chunziMansion"},
        "xianqin": {"lunarDay", "lunarMonth", "lunarYear"},
        "wuzhao": {"castSeed"},
        "cetian": {"location"},
        "tieban": {"tiebanSchool", "tiebanKeSystem", "tiebanKe"},
    }
    for tool, keys in expect.items():
        documented = set(build_agent_guidance(tool_name=tool)["tools"][tool]["options_keys"])
        assert keys <= documented, (tool, keys - documented)


# ---------------------------------------------------------------- F7 / F17：演禽演法


def test_xianqin_yanfa_school_and_switches_reach_the_engine(tmp_path) -> None:
    """F7：演法流派/六开关（yanqinSchools YANQIN_PRESETS / YANQIN_OPTION_META）逐次传入真引擎；旧码 headless
    恒池本理（store 读 localStorage 恒 null），options.school 被当后端键送走、演法段纹丝不动。"""
    # 后端盘面桩不含演法段（真后端也不产，演法段全由 JS 层追加）——否则 FakeClient 的全 preset 合成会先占位。
    backend = {"engine": "kinastro-xianqin", "snapshot": "[起盘]\n起盘时间：1998-02-20 20:48:00\n\n[三宫]\n命宫：亥"}
    service, _, _ = _service(tmp_path, RecordingClient({"/xianqin/pan": lambda p: backend}), real_js=True)
    default = _section(_run(service, "xianqin", {**BASE, "gender": 1}).data["snapshot_text"], "演法·流派")
    assert default.startswith("池本理《禽星易见》")
    fenghuang = _section(_run(service, "xianqin", {**BASE, "gender": 1, "options": {"school": "fenghuang"}}).data["snapshot_text"], "演法·流派")
    assert fenghuang.startswith("凤凰演禽(现代占课);时禽=我/翻禽=彼")
    custom = _section(_run(service, "xianqin", {**BASE, "gender": 1, "options": {"woBi": "shi", "monthVerse": "B"}}).data["snapshot_text"], "演法·流派")
    assert custom.startswith("custom;时禽=我") and "月禽口诀B版" in custom, "偏离预设 → school 标 custom（上游 setOption 同律）"


def test_yanqin_js_rejects_values_outside_the_engine_vocabulary(tmp_path) -> None:
    settings = Settings(runtime_root=tmp_path / "runtime", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    out = HorosaJsEngineClient(settings).run("yanqin_yanfa", {"year": 1998, "month": 2, "day": 20, "hour": 20, "woBi": "nope"})
    assert out["data"]["ok"] is False and out["data"]["error"]["code"] == "invalid_setting"
    assert out["data"]["error"]["details"]["allowed"] == ["fan", "shi", "daoWo"]


def test_xianqin_yanfa_lunar_month_comes_from_nongli_bridge(tmp_path) -> None:
    """F17：上游无头路径经 deriveLocalNongliAsync 取权威 monthInt 注入演法（KinAstroMain.js:351-359）；
    旧码只在调用方传 lunarMonth 时注入，从不取数。钟表时（timeAlg=1）：演禽不吃真太阳时。"""
    service, client, js = _service(tmp_path)
    assert _run(service, "xianqin", {**BASE, "gender": 1}).ok
    nongli = client.sent("/nongli/time")
    assert nongli and nongli[-1]["timeAlg"] == 1 and nongli[-1]["zone"] == "+08:00"
    yanfa = [p for t, p in js.calls if t == "yanqin_yanfa"][-1]
    assert yanfa["lunarMonth"] == 2, "FakeClient /nongli/time monthInt=2"
    client.calls.clear()
    assert _run(service, "xianqin", {**BASE, "gender": 1, "options": {"lunarMonth": 5}}).ok
    assert not client.sent("/nongli/time"), "显式农历月优先，不再取数"
    assert [p for t, p in js.calls if t == "yanqin_yanfa"][-1]["lunarMonth"] == 5


# ---------------------------------------------------------------- F8：铁板框架推演


def _tieban_client() -> RecordingClient:
    pillars = [{"key": "year", "ganzhi": "戊寅"}, {"key": "month", "ganzhi": "甲寅"},
               {"key": "day", "ganzhi": "戊戌"}, {"key": "hour", "ganzhi": "壬戌"}]
    snapshot = "[起盘]\n起盘时间：1998-02-20 20:47:00\n\n[四柱]\n年柱：戊寅"
    return RecordingClient({"/tieban/pan": lambda p: {"engine": "kinastro-tieban", "pillars": pillars, "snapshot": snapshot}})


def test_tieban_framework_reads_upstream_keys_and_defaults_ke_to_one(tmp_path) -> None:
    """F8：上游无头挂载读 tiebanSchool / tiebanKeSystem / tiebanKe，缺省 south / qing8 / 1
    （KinAstroMain.buildKinAstroSnapshotForFields :329-346）。旧码读 options.school/keSystem 且按钟点折刻：
    20:47 → 戌时八刻，这里期望初刻即红。"""
    service, _, _ = _service(tmp_path, _tieban_client(), real_js=True)
    text = _run(service, "tieban", {**BASE, "time": "20:47:00", "gender": 1}).data["snapshot_text"]
    assert "九十六局:戌时初刻＝全日第81刻" in text and "流派:南派" in text and "刻制:清制·八刻" in text
    assert "\n\n[框架·流派刻制]" in text, "上游 `${text}\\n\\n${suffix}`：框架段前空一行"
    text = _run(service, "tieban", {**BASE, "time": "20:47:00", "gender": 1,
                                    "options": {"tiebanKe": 5, "tiebanSchool": "north", "tiebanKeSystem": "dou12"}}).data["snapshot_text"]
    assert "戌时五刻" in text and "流派:北派(洛阳/中州)" in text and "刻制:十二刻·斗宫" in text


# ---------------------------------------------------------------- F9 / F10 / F11：塔罗


TAROT = {**BASE, **PLACE, "question": "事业"}


def test_tarot_seed_is_upstream_birth_seed(tmp_path) -> None:
    """F10：上游「生辰」种子 seedFromFields = name|date|time|lat|lon 非空项（TarotMain.js:97-108）；
    旧码 yyyyMMddHHmm（199802202048）。"""
    service, _, js = _service(tmp_path)
    result = _run(service, "tarot", TAROT)
    assert result.ok and result.data["seed"] == "1998-02-20|20:48:00|31n13|121e28"
    assert [p for t, p in js.calls if t == "tarot"][-1]["seed"] == "1998-02-20|20:48:00|31n13|121e28"
    assert _run(service, "tarot", {**TAROT, "name": "张三"}).data["seed"] == "张三|1998-02-20|20:48:00|31n13|121e28"


def test_tarot_engine_settings_reach_the_engine(tmp_path) -> None:
    """F9：19 个引擎设置经 options 送达（键集锚 resolveSettings）；verdictMode 八法全开；usesReversals=true 下发。"""
    service, _, js = _service(tmp_path, real_js=True)
    base = _run(service, "tarot", {**TAROT, "spread": "three"})
    timed = _run(service, "tarot", {**TAROT, "spread": "three", "options": {"timingMethod": "major_number", "timingUnit": "月"}})
    assert base.ok and timed.ok, (base.error, timed.error)
    assert "计时(花色单位)" in base.data["snapshot_text"]
    assert "计时(大牌数字)" in timed.data["snapshot_text"] and "个月内" in timed.data["snapshot_text"]
    anchor = _run(service, "tarot", {**TAROT, "spread": "three", "verdictMode": "anchor"})
    assert "答案锚位" in _section(anchor.data["snapshot_text"], "定局"), "旧码把 anchor 截回 majority"
    reversed_tdm = _run(service, "tarot", {**TAROT, "deck": "tdm", "usesReversals": True})
    plain_tdm = _run(service, "tarot", {**TAROT, "deck": "tdm"})
    assert [p for t, p in js.calls if t == "tarot"][-2]["usesReversals"] is True
    assert reversed_tdm.data["snapshot_text"] != plain_tdm.data["snapshot_text"], "马赛牌默认无逆位，显式开逆位必须生效"
    ignored = _run(service, "tarot", {**TAROT, "options": {"notASetting": 1}})
    assert ignored.ok and ignored.data["params_ignored"] == ["notASetting"]
    bad = _run(service, "tarot", {**TAROT, "options": {"timingUnit": "年"}})
    assert bad.ok is False and bad.error.code == "tool.tarot_invalid_setting"


def test_tarot_spreads_are_engine_keys_and_deck_caps_are_enforced(tmp_path) -> None:
    """F11：牌阵键 = 引擎 SPREADS 真键；闸门曾建议 one / relationship（不存在，被静默换成 three）。"""
    service, _, _ = _service(tmp_path, real_js=True)
    bad = _run(service, "tarot", {**TAROT, "spread": "one"})
    assert bad.ok is False and bad.error.code == "tool.tarot_unknown_spread"
    assert "single" in bad.error.details["allowed"]
    capped = _run(service, "tarot", {**TAROT, "deck": "lenormand", "spread": "celtic"})
    assert capped.ok is False and capped.error.code == "tool.tarot_unsupported_spread_for_deck"
    assert _run(service, "tarot", {**TAROT, "deck": "lenormand"}).data["spread"] == "single", "缺省牌阵不开放 → 允许表首项"
    options = build_agent_guidance(tool_name="tarot")["tools"]["tarot"]["ask_if_missing"]
    spread_q = next(item for item in options if item["field"] == "spread")
    keys = [option.split()[-1] for option in spread_q["options"] if "（" not in option]
    for key in keys:
        assert _run(service, "tarot", {**TAROT, "spread": key}).ok, key


# ---------------------------------------------------------------- F10 / F11 / F12：天文地占


GEO = {**BASE, **PLACE, "question": "x", "questionType": "career"}


def test_geomancy_time_seed_and_time_place_follow_upstream(tmp_path) -> None:
    """F10/F12：timeSeed = 上游 computeTimeSeed (YY)MMDDHHmm mod 2^31−1（GeomancyMain.js:229-246）；
    所问时地随请求下发（:1161-1167）——否则 ascSource=real_chart / houseProjection=real_ephemeris 静默回落。"""
    service, client, _ = _service(tmp_path)
    result = _run(service, "geomancy", {**GEO, "options": {"housePlacement": "angular", "planetaryChart": True, "planetaryChartNodes": True, "nope": 1}})
    assert result.ok, result.error
    sent = client.sent("/geomancy/reading")[-1]
    assert sent["timeSeed"] == (98 * 100000000 + 2 * 1000000 + 20 * 10000 + 20 * 100 + 48) % 2147483647 == 1212267460
    assert {k: sent[k] for k in ("date", "time", "zone", "lat", "lon")} == {"date": "1998-02-20", "time": "20:48:00", **PLACE}
    assert sent["housePlacement"] == "angular" and sent["planetaryChart"] is True and sent["planetaryChartNodes"] is True
    assert "nope" not in sent and result.data["params_ignored"] == ["nope"]


def test_geomancy_cast_numbers_and_question_types(tmp_path) -> None:
    service, client, _ = _service(tmp_path)
    numbers = list(range(1, 17))
    assert _run(service, "geomancy", {**GEO, "options": {"castNumbers": numbers}}).ok
    sent = client.sent("/geomancy/reading")[-1]
    assert sent["castMethod"] == "numbers" and sent["castNumbers"] == numbers and sent["seed"] == 1212267460 and "timeSeed" not in sent
    bad = _run(service, "geomancy", {**GEO, "options": {"castNumbers": [1, 2, 3]}})
    assert bad.ok is False and bad.error.code == "tool.geomancy_invalid_cast_numbers"
    lawsuit = _run(service, "geomancy", {**GEO, "questionType": "lawsuit"})
    assert lawsuit.ok is False and lawsuit.error.code == "tool.geomancy_invalid_question_type", "旧码：后端静默改回 custom"
    options = build_agent_guidance(tool_name="geomancy")["tools"]["geomancy"]["ask_if_missing"]
    qtypes = {option.split()[-1] for option in next(i for i in options if i["field"] == "questionType")["options"]}
    assert qtypes == set(lawsuit.error.details["allowed"])


# ---------------------------------------------------------------- F13：玄史参数映射


# webxuanshisrv.py 逐端点真读的键（:114-530）；桩只认这些键——送错名字的请求当场红。
_XUANSHI_READS: dict[str, set[str]] = {
    "/xuanshi/search": {"q", "query", "limit", "tradition"},
    "/xuanshi/figures": {"status", "dynasty", "q", "limit", "offset"},
    "/xuanshi/figure": {"slug"},
    "/xuanshi/technique": {"slug"},
    "/xuanshi/celestial_term": {"slug"},
    "/xuanshi/dynasty": {"slug"},
    "/xuanshi/story": {"slug"},
    "/xuanshi/stories": {"channel_slug", "dynasty", "figure_slug", "technique_slug", "status", "limit", "offset", "search_text", "q"},
    "/xuanshi/celestial_term_profile": {"omen", "label"},
    "/xuanshi/microchronology": {"history", "omen_type", "omenType", "omen", "decade"},
    "/xuanshi/decade_omens": set(),
    "/xuanshi/celestial": {"dynasty", "omen", "history", "source", "year_from", "yearFrom", "year_to", "yearTo",
                           "has_crosswalk", "hasCrosswalk", "in_chapter", "inChapter", "keyword", "q", "page", "page_size", "pageSize"},
}


class StrictXuanshiClient(RecordingClient):
    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        reads = _XUANSHI_READS.get(endpoint)
        if reads is not None:
            unread = sorted(set(payload) - reads)
            if unread:
                raise AssertionError(f"{endpoint} does not read {unread}")
        return {"title": "stub", "slug": payload.get("slug"), "items": []}


@pytest.mark.parametrize(
    "payload, endpoint, expected",
    [
        ({"action": "figure", "id": "fig-laozi"}, "/xuanshi/figure", {"slug": "fig-laozi"}),
        ({"action": "technique", "q": "tech-liuren"}, "/xuanshi/technique", {"slug": "tech-liuren"}),
        ({"action": "term", "id": "term-huixing"}, "/xuanshi/celestial_term", {"slug": "term-huixing"}),
        ({"action": "dynasty", "id": "dyn-tang"}, "/xuanshi/dynasty", {"slug": "dyn-tang"}),
        ({"action": "story", "id": "story-1"}, "/xuanshi/story", {"slug": "story-1"}),
        ({"action": "term_profile", "q": "彗孛"}, "/xuanshi/celestial_term_profile", {"omen": "彗孛"}),
        ({"action": "microchronology", "omen": "彗孛", "history": "宋史", "decade": 1050}, "/xuanshi/microchronology",
         {"omen": "彗孛", "history": "宋史", "decade": 1050}),
        ({"action": "figures", "page": 2, "page_size": 3}, "/xuanshi/figures", {"limit": 3, "offset": 3}),
        ({"action": "stories", "q": "袁天罡", "limit": 5}, "/xuanshi/stories", {"q": "袁天罡", "limit": 5}),
        ({"action": "celestial", "q": "彗", "has_crosswalk": True, "in_chapter": False}, "/xuanshi/celestial",
         {"q": "彗", "has_crosswalk": True, "in_chapter": False}),
        ({"action": "decade_omens", "year_from": 1000}, "/xuanshi/decade_omens", {}),
    ],
)
def test_xuanshi_sends_the_parameter_names_the_backend_reads(tmp_path, payload, endpoint, expected) -> None:
    """F13：旧码 figure/technique/term/dynasty/story 发 `id`（后端只读 `slug` → 恒 null）、term_profile 发 id、
    microchronology 发 dynasty/年段、figures 发 page/page_size、celestial 丢 q/has_crosswalk/in_chapter。
    桩按 webxuanshisrv 逐端点读键把关：送了后端不读的键即 AssertionError → ok=False。"""
    service, client, _ = _service(tmp_path, StrictXuanshiClient())
    result = _run(service, "xuanshi", payload)
    assert result.ok, result.error
    assert client.sent(endpoint)[-1] == expected


class NullDetailClient(RecordingClient):
    """查无此 slug 时真后端回 JSON null（editorial.get_figure → None）。第 4 次同端点调用即判「在 null 上死循环」。"""

    def call(self, endpoint: str, payload: dict) -> dict | None:
        self.calls.append((endpoint, dict(payload)))
        if len(self.sent(endpoint)) > 3:
            raise AssertionError(f"retry loop on a JSON-null body: {endpoint} called {len(self.sent(endpoint))}x")
        return None


def test_xuanshi_unknown_slug_is_a_zero_hit_not_an_infinite_retry(tmp_path) -> None:
    """F13 连带：_call_remote 旧循环拿 `data is not None` 当成功判据 → 后端合法回 null 时无限重发（进程 100% CPU
    挂死、持续打后端）。旧映射下 figure 恒发错键、恒回 null，所以玄史详情查询在旧码上是必挂的。"""
    service, client, _ = _service(tmp_path, NullDetailClient())
    result = _run(service, "xuanshi", {"action": "figure", "id": "fig-no-such-person"})
    assert result.ok, result.error
    assert len(client.sent("/xuanshi/figure")) == 1
    assert "命中 0 条" in result.data["snapshot_text"]


# ---------------------------------------------------------------- F14：神数正传·铁算心易


def test_zhengchuan_xinyi_defaults_and_ke_names(tmp_path) -> None:
    """F14：上游挂载缺省 父母/日/一刻/乾/子（aiAnalysisContext.js:3240-3243, F-53）；八刻分命查表键是
    「一刻…八刻」。旧码：{school:xinyi} 无查询项直接报 xinyi_no_query；ke=3（int）查表恒空。"""
    service, _, _ = _service(tmp_path, real_js=True)
    default = _run(service, "zhengchuan", {"school": "xinyi", **CONFIRM})
    assert default.ok, default.error
    assert "| 一刻 | 乾 | 乾 |" in _section(default.data["snapshot_text"], "八刻分命")
    assert "| 父母 | 日 |" in _section(default.data["snapshot_text"], "条文秘数查询")
    third = _run(service, "zhengchuan", {"school": "xinyi", "ke": 3, "gong": "离", **CONFIRM})
    assert "| 三刻 | 離 | 鼎 |" in _section(third.data["snapshot_text"], "八刻分命")
    bad = _run(service, "zhengchuan", {"school": "xinyi", "ke": 9, **CONFIRM})
    assert bad.ok is False and bad.error.code == "tool.zhengchuan_invalid_xinyi_ke"


# ---------------------------------------------------------------- F15：皇极经世·心易发微


_WANGJI_BACKEND = (
    "[起盘]\n日期：1998-02-20 20:48\n\n[元会运世]\n元：…\n\n[天道卦]\n正卦：…\n\n[人事卦]\n年卦：…\n\n"
    "[历史年表]\n历史年表：无\n\n"
    "[心易发微]\nmethod：datetime\nresult：本卦：小過；變卦：豫\nsections：title：心易发微"
)


def test_wangji_xinyi_goes_into_xinyi_fawei_with_upstream_defaults(tmp_path) -> None:
    """F15：上游 buildHuangJiSnapshotForFields（HuangJiMain.js:161-198）缺省起 datetime 心易、所选之法卦面**进
    [心易发微]**（逐键「键：值」），入参全量：upperNum 5 / lowerNum 10 / upperStrokes 5 / lowerStrokes 8 /
    objectGua 離 / direction 南、时辰=盘面时辰。后端 /pan 自带的 [心易发微] 是 {method,result,sections} 的
    str()（「method：datetime」）——旧码原样出它，另把所选法塞进 skill 自造的 [心易起卦]。"""
    client = RecordingClient({"/wangji/pan": lambda p: {"engine": "kinwangji", "snapshot": _WANGJI_BACKEND}})
    service, client, _ = _service(tmp_path, client)
    result = _run(service, "wangji", BASE)
    assert result.ok, result.error
    sent = client.sent("/wangji/xinyi")[-1]
    assert {k: sent[k] for k in ("method", "hour", "upperNum", "lowerNum", "upperStrokes", "lowerStrokes", "objectGua", "direction")} == {
        "method": "datetime", "hour": 20, "upperNum": 5, "lowerNum": 10, "upperStrokes": 5, "lowerStrokes": 8,
        "objectGua": "離", "direction": "南"}
    fawei = _section(result.data["snapshot_text"], "心易发微")
    assert fawei.startswith("本卦：頤") and "method：" not in fawei and "[心易起卦]" not in result.data["snapshot_text"]
    none = _run(service, "wangji", {**BASE, "xinyiMethod": "none"})
    assert none.ok and "[心易发微]" not in none.data["snapshot_text"]
    assert none.data["export_snapshot"]["missing_selected_sections"] == [], "none 档该段缺席不算 missing（条件段双登记）"
    simplified = _run(service, "wangji", {**BASE, "xinyiMethod": "direction", "objectGua": "兑", "xinyiDirection": "东北", "xinyiHour": 3})
    assert simplified.ok, simplified.error
    sent = client.sent("/wangji/xinyi")[-1]
    assert (sent["objectGua"], sent["direction"], sent["hour"]) == ("兌", "東北", 3), "后端只认繁体（kinwangji/xinyi.py:42-72）"
    bad = _run(service, "wangji", {**BASE, "xinyiMethod": "direction", "xinyiDirection": "东东"})
    assert bad.ok is False and bad.error.code == "tool.wangji_invalid_xinyi_direction"


# ---------------------------------------------------------------- F16：地名 / 今年缺省入卡


def test_cetian_and_qizhengkin_forward_pos_and_pin_current_year(tmp_path) -> None:
    """F16：上游 kinastro 挂载恒带 pos（kinAstroFieldsSync.js:81）；策天「地点」行只认它（webcetiansrv.py:398），
    七政缺它落「星阙地点」占位（webqizhengkinsrv.py:484）。流年/大运年缺省=datetime.now().year → skill 显式钉住
    并记入技法卡（旧码：pos 不转发、卡里没有年）。"""
    service, client, _ = _service(tmp_path)
    year = datetime.now().year
    cetian = _run(service, "cetian", {**BASE, **PLACE, "gender": 1, "pos": "上海"})
    assert cetian.ok, cetian.error
    sent = client.sent("/cetian/pan")[-1]
    assert sent["pos"] == "上海" and sent["liunianYear"] == year
    assert cetian.data["technique_card"]["settings"]["liunianYear"]["value"] == year
    qizheng = _run(service, "qizhengkin", {**BASE, **PLACE, "gender": 1, "pos": "上海"})
    sent = client.sent("/qizhengkin/pan")[-1]
    assert qizheng.ok and sent["pos"] == "上海" and sent["qizhengKinCurrentYear"] == year
    assert qizheng.data["technique_card"]["settings"]["qizhengKinCurrentYear"]["value"] == year
    explicit = _run(service, "cetian", {**BASE, **PLACE, "gender": 1, "options": {"liunianYear": 2030}})
    assert client.sent("/cetian/pan")[-1]["liunianYear"] == 2030
    assert "liunianYear" not in explicit.data["technique_card"]["settings"], "显式给的年份不算 skill 替用户定的"
    kentang = _run(service, "cetian", {**BASE, **PLACE, "gender": 1, "options": {"method": "kentang"}})
    assert kentang.ok and "liunianYear" not in client.sent("/cetian/pan")[-1], "原法不起流年，不钉"


# ---------------------------------------------------------------- F18：显示名对齐上游


def test_tool_display_names_match_upstream_labels() -> None:
    """F18：上游 aiExport EXPORT_TECHNIQUES（aiExport.js:533-550）：荆诀 / 神易数 / 鬼谷分定经 / 蠢子数。"""
    from horosa_skill.exports.registry import get_technique_info

    for tool, right, wrong in (("jingjue", "荆诀", "京氏易"), ("shenyishu", "神易数", "神乙数"),
                               ("fendjing", "鬼谷分定经", "分经神数"), ("chunzi", "蠢子数", "淳子神数")):
        assert right in TOOL_DEFINITIONS[tool].description and wrong not in TOOL_DEFINITIONS[tool].description, tool
        assert get_technique_info(tool)["label"] == right, tool


# ================================================================= live（vendored v3.11.1+ backend）


def _live(tmp_path, tool: str, payload: dict):
    service = make_service(tmp_path)
    result = service.run_tool(tool, {**CONFIRM, **payload}, save_result=False)
    assert result.ok, result.error
    return result.data


@requires_chart
def test_live_jingjue_same_moment_same_gua(tmp_path) -> None:
    one = _live(tmp_path, "jingjue", BASE)
    two = _live(tmp_path, "jingjue", BASE)
    assert "起筮种子：802202048" in one["snapshot_text"] and one["snapshot_text"] == two["snapshot_text"]


@requires_chart
def test_live_taixuan_minute_changes_the_cast(tmp_path) -> None:
    """旧码同一小时内恒同卦（后端缺省种子 yyyyMMddHH）；上游分钟级种子 → 20:05 与 20:48 必异。"""
    early = _live(tmp_path, "taixuan", {**BASE, "time": "20:05:00"})
    late = _live(tmp_path, "taixuan", BASE)
    assert early["seed"] == 802202005 and late["seed"] == SEED_19980220_2048
    assert _section(early["snapshot_text"], "方州部家") != _section(late["snapshot_text"], "方州部家")


@requires_chart
def test_live_wuzhao_dunhuang_is_reproducible_and_gender_is_read(tmp_path) -> None:
    one = _live(tmp_path, "wuzhao", {**BASE, "options": {"mode": "dunhuang"}})
    two = _live(tmp_path, "wuzhao", {**BASE, "options": {"mode": "dunhuang"}})
    assert one["snapshot_text"] == two["snapshot_text"], "旧码不带 castSeed → 后端 random.Random() 真随机"
    male = _live(tmp_path, "wuzhao", {**BASE, "gender": 1, "options": {"mingZhi": "子"}})
    female = _live(tmp_path, "wuzhao", {**BASE, "gender": 0, "options": {"mingZhi": "子"}})
    assert "行年：辰" in male["snapshot_text"] and "行年：午" in female["snapshot_text"]


@requires_chart
@pytest.mark.parametrize("tool", ["beiji", "nanji", "chunzi"])
def test_live_beiji_nanji_chunzi_read_gender_so_the_gate_asks(tmp_path, tool: str) -> None:
    """F5 的 §5.12 证据：改性别结果必变 → 闸门必须问（旧闸不问，末条断言在旧码上红）。"""
    male = _live(tmp_path, tool, {**BASE, **PLACE, "gender": 1})
    female = _live(tmp_path, tool, {**BASE, **PLACE, "gender": 0})
    assert male["snapshot_text"] != female["snapshot_text"]
    assert "gender" in {i["field"] for i in validate_agent_preflight(tool, {"date": "1998-02-20"})["ask_if_missing"]}


@requires_chart
def test_live_tieban_year_pillar_follows_zone_so_the_gate_asks(tmp_path) -> None:
    """F16 的证据：1990 立春 = 1990-02-04 10:14 CST；10:00 在 +08:00 未过立春、在 -05:00（=15:00 UTC）已过
    → 年柱随时区翻转，闸门必须问时区（旧闸不问，末条断言在旧码上红）。"""
    east = _live(tmp_path, "tieban", {"date": "1990-02-04", "time": "10:00:00", "zone": "+08:00", "gender": 1})
    west = _live(tmp_path, "tieban", {"date": "1990-02-04", "time": "10:00:00", "zone": "-05:00", "gender": 1})
    assert "年柱：己巳" in east["snapshot_text"] and "年柱：庚午" in west["snapshot_text"]
    assert "zone" in {i["field"] for i in validate_agent_preflight("tieban", {"date": "1990-02-04", "gender": 1})["ask_if_missing"]}


@requires_chart
def test_live_wangji_xinyi_fawei_is_the_gua_not_the_wrapper(tmp_path) -> None:
    data = _live(tmp_path, "wangji", BASE)
    assert _section(data["snapshot_text"], "心易发微").startswith("本卦：小過\n變卦：豫\n動爻：3")


@requires_chart
def test_live_geomancy_real_chart_uses_the_forwarded_time_place(tmp_path) -> None:
    plain = _live(tmp_path, "geomancy", GEO)
    real = _live(tmp_path, "geomancy", {**GEO, "options": {"ascSource": "real_chart"}})
    assert plain["time_seed"] == 1212267460 and plain["snapshot_text"] != real["snapshot_text"]


@requires_chart
def test_live_xuanshi_figure_by_slug(tmp_path) -> None:
    data = _live(tmp_path, "xuanshi", {"action": "figure", "id": "fig-laozi"})
    assert "名称：老子" in _section(data["snapshot_text"], "条目详情")


@requires_chart
def test_live_cetian_place_name_line(tmp_path) -> None:
    data = _live(tmp_path, "cetian", {**BASE, **PLACE, "gender": 1, "pos": "上海"})
    assert "地点：上海" in data["snapshot_text"]


@requires_runtime
def test_live_xianqin_yanfa_lunar_month_from_nongli(tmp_path) -> None:
    data = _live(tmp_path, "xianqin", {**BASE, **PLACE, "gender": 1})
    assert data["technique_card"]["settings"]["yanqinLunarMonth"]["value"] == 1  # 1998-02-20 = 戊寅年正月廿四
    assert "农历1月戌时" in _section(data["snapshot_text"], "演法·投胎")
