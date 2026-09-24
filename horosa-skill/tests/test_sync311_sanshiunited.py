"""v3.11.x 上游同步 · wave 3 三式合一 chunk：快照改由 vendored 上游 buildSanShiUnitedSnapshotText 产出 +
六壬层占时随三式农历 + 择日（六壬 / 三式 / 太乙）展示盘跟随扫描口径。

权威与负向对照（每条用例的 docstring 写明「旧代码为什么会红」）：
- 服务层值级用例走 **真实 service + 真实 JS 引擎**，后端响应由 `ReplayClient` 从 live 录制
  （tests/fixtures/sync311_sanshiunited_live.json，vendored 上游 v3.11.1+ 实例 chart :8877 / java :9977）按
  「端点 + 决定响应的请求字段」回放 —— 回放键刻意比 wave-2 的宽（/chart 带 hsys / zodiacal，/qimen/pan 带
  realSunTime 与日界两键）：发错星盘宫制、丢了真太阳时显示值、日界两键没按上游显式发送，都查不到录制即红；
- 期望值出自那次 live 响应经 vendored 上游 builder 的输出，且与独立装配的上游 builder 逐字节核对过
  （见 wave-3 报告「byte comparison」一节）；
- 纯 JS 用例直接跑 horosa-core-js（与生产同一条 cli 路径 / vendored 模块）。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

PKG_ROOT = Path(__file__).resolve().parents[1]
CORE_JS = PKG_ROOT / "horosa-core-js"
LIVE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sync311_sanshiunited_live.json"
GOLDEN = Path(__file__).resolve().parent / "fixtures" / "golden_sanshiunited_default.txt"
FIXTURE_COMMENT = (
    "wave-3 sanshiunited chunk live recordings (vendored upstream v3.11.1+ instance: chart :8877 / java :9977), "
    "trimmed to the fields the engines read (replay proven byte-identical); regenerate with the scratchpad recorder "
    "over tests/test_sync311_sanshiunited.SCENARIOS."
)
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

# ─────────────────────────────── 录制 / 回放 ───────────────────────────────

BASE = {"date": "2026-09-24", "time": "10:57", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}
# 白露(9-07)之后、秋分(9-23)之前：中气过宫月将＝巳（太阳在处女），节气换将＝辰（白露换将）—— 两派必分。
BASE_JIEQI = {**BASE, "date": "2026-09-15"}
# 清明(4-04)之后、谷雨(4-19)之前：中气过宫月将＝戌（太阳在白羊），节气换将＝酉（清明换将）—— 两派必分。
ZERI_WINDOW = {"startDate": "2028-04-10", "startTime": "00:00", "endDate": "2028-04-10", "endTime": "23:59"}
ZERI_GEO = {"date": "2028-04-10", "time": "12:00", "zone": "+08:00", "lat": "26n05", "lon": "119e18",
            "gpsLat": 26.08, "gpsLon": 119.3}
# 一天窗里恒有命中的条件：昼占（六壬择时键 zhou_ye；三式择时同一条件带家前缀 lr_）。
_LR_TREE = {"kind": "group", "joiner": "all", "children": [
    {"kind": "leaf", "type": "zhou_ye", "params": {"value": "day"}}]}
_SS_TREE = {"kind": "group", "joiner": "all", "children": [
    {"kind": "leaf", "type": "lr_zhou_ye", "params": {"value": "day"}}]}

SCENARIOS: dict[str, tuple[str, dict[str, Any]]] = {
    "default": ("sanshiunited", BASE),
    "clock": ("sanshiunited", {**BASE, "timeAlg": 1}),
    "gui0": ("sanshiunited", {**BASE, "liureng_options": {"guirengType": 0}}),
    "gui0_yinyang": ("sanshiunited", {**BASE, "liureng_options": {"guirengType": 0, "yinyangSystem": "yinyang"}}),
    "zhongqi_0915": ("sanshiunited", BASE_JIEQI),
    "jieqi_0915": ("sanshiunited", {**BASE_JIEQI, "liureng_options": {"yueJiangMethod": "jieqi"}}),
    "sihua": ("sanshiunited", {**BASE, "ziweiSihua": {"daxianIdx": 0, "liunianIdx": 0}}),
    "lrzeri_jieqi": ("liurengzeri", {**ZERI_GEO, **ZERI_WINDOW, "conditions": _LR_TREE,
                                     "options": {"yueMode": "jieqi", "yinyangSystem": "yinyang"}}),
    "sszeri_lr": ("sanshizeri", {**ZERI_GEO, **ZERI_WINDOW, "conditions": _SS_TREE,
                                 "options": {"guirengType": 0, "yueMode": "jieqi", "taiyiAccum": 1}}),
}

# 回放键：端点 + 决定响应的请求字段（比 wave-2 的宽，见模块注释）。
_REPLAY_FIELDS: dict[str, tuple[str, ...]] = {
    "/nongli/time": ("date", "time", "timeAlg", "after23NewDay", "lateZiHourUseNextDay"),
    "/jieqi/year": ("year", "timeAlg"),
    "/qimen/pan": ("year", "month", "day", "hour", "minute", "qijuMethod", "qimenMode", "realSunTime",
                   "after23NewDay", "lateZiHourUseNextDay"),
    "/taiyi/pan": ("year", "month", "day", "hour", "minute", "style", "tn", "timeBasis", "sex", "after23NewDay"),
    "/chart": ("date", "time", "hsys", "zodiacal", "tradition"),
    "/ziwei/birth": ("date", "time", "gender", "timeAlg"),
    "/liureng/gods": ("date", "time", "timeAlg", "after23NewDay"),
}


def _norm(field: str, value: Any) -> Any:
    if value is None:
        return None
    text = str(value)
    if field == "date":
        return text.replace("/", "-")
    if field == "time" and len(text) == 5:
        return f"{text}:00"
    if isinstance(value, bool):
        return str(int(value))
    return text


def replay_key(endpoint: str, payload: dict[str, Any]) -> str:
    endpoint = "/chart" if endpoint == "/" else endpoint
    fields = _REPLAY_FIELDS.get(endpoint, ())
    return json.dumps([endpoint, [_norm(f, payload.get(f)) for f in fields]], ensure_ascii=False)


class ReplayClient(HorosaApiClient):
    """按录制回放后端；查无录制 = 请求形状与 live 验证过的不同 → 抛错。"""

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
    return service.run_tool(tool, {**payload, **overrides, "agent_confirmed_settings": True}, save_result=False)


def _block(text: str, title: str) -> list[str]:
    """上游 appendSection 形态：【段名】起、到下一个【…】段头前（段尾空行剥掉）。"""
    head = f"【{title}】\n"
    assert head in text, f"missing 【{title}】 in:\n{text[:1500]}"
    body = text.split(head, 1)[1]
    lines: list[str] = []
    for line in body.split("\n"):
        if line.startswith("【") and line.endswith("】"):
            break
        lines.append(line)
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _calls(client, endpoint: str) -> list[dict[str, Any]]:
    return [payload for ep, payload in client.calls if ep == endpoint]


def _node(script: str) -> Any:
    from node_esm import node_esm_process  # 统一入口（Windows ESM 路径口径）

    proc = node_esm_process(script, cwd=CORE_JS, timeout=180)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


# ═══════════════════════ 1. 快照 = 上游 buildSanShiUnitedSnapshotText ═══════════════════════


@requires_node
def test_sanshiunited_snapshot_is_the_upstream_builder_byte_for_byte(tmp_path) -> None:
    """[Item 1] 三式合一快照整份 = vendored 上游 buildSanShiUnitedSnapshotText（SanShiUnitedMain.js:1424）的输出。
    权威：tests/fixtures/golden_sanshiunited_default.txt = 同一 live 盘经**独立装配**的上游 builder 产出
    （scratchpad harness 按上游 genParams/fieldsToParams/fetchQimenPan/fetchTaiyiPan 另发请求、按 performRecalcByNongli
    另行装配；33927 B / 701 行 / 41 段，sha256 4be47af9…，与 skill 输出逐字节相同）。
    负向对照：旧代码在 service.py 里用子工具导出段自拼 —— 段头 [起盘信息]（非【】）、[大六壬] 只有
    「一课：地盘=辛，天盘=申，贵神=天空」四课体、段序/正文全不同 → 逐字节比较当场红。"""
    service, _client = _replay_service(tmp_path)
    env = _run(service, "default")
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    assert text == GOLDEN.read_text(encoding="utf-8")
    # 导出契约：41 个 builder 段逐段正文不变地进 export_snapshot（段序另由全技法 max-section 契约按 preset 排）。
    bodies = {s["title"]: s["body"] for s in env.data["export_snapshot"]["sections"]}
    titles = [line[1:-1] for line in text.splitlines() if line.startswith("【") and line.endswith("】")]
    assert len(titles) == 41
    for title in titles:
        assert bodies[title] == "\n".join(_block(text, title)).strip(), title
    assert env.data["export_snapshot"]["unknown_detected_sections"] == []
    assert env.data["export_snapshot"]["missing_selected_sections"] == []


@requires_node
def test_sanshiunited_dalioren_block_is_the_upstream_ke_chuan_relation_layout(tmp_path) -> None:
    """[Item 1 已知缺口] 上游【大六壬】= 一课…四课（日干上神起，[Q-153/T-70] 同序）、空行、初中末传带天将、
    sanChuanRelationSnapshotLines 的递生递克 + 空/禄/马徽记（SanShiUnitedMain.js:1524-1544）。
    权威：live 2026-09-24 10:57 上海盘（辛丑日午时，月将辰，星占法贵人）。
    负向对照：旧 [大六壬] = 六壬导出的 [四课] 体（「一课：地盘=辛，天盘=申，贵神=天空」四行、无三传无徽记）→ 红。"""
    service, _client = _replay_service(tmp_path)
    assert _block(_run(service, "default").data["snapshot_text"], "大六壬") == [
        "一课：辛申天空",
        "二课：申午勾陈",
        "三课：丑亥玄武",
        "四课：亥酉白虎",
        "",
        "初传：己亥（玄武）",
        "中传：丁酉（白虎）",
        "末传：乙未（青龙）",
        "三传递生递克：初传→中传 生入；中传→末传 生入",
        "逐传徽记：初传亥(马)；中传酉(禄)",
    ]


@requires_node
def test_sanshiunited_qimen_layer_gets_the_upstream_context(tmp_path) -> None:
    """上游 getKinqimenDunJia 以 context={isDiurnal: 星盘昼夜, displaySolarTime} 起 calcDunJia 脚手架，
    normalizeKinqimenData 沿用其神煞层；fetchQimenPan 显式发日界两键（getQimenOptions :3341-3343）。
    权威：辛日遁甲贵人 昼寅夜午（LRConst DayGuiDunJia/NightGuiDunJia），live 星盘 isDiurnal=true。
    负向对照：旧代码不给 context → 神煞「贵人」「幕贵」恒「—」（旧 live 输出 神煞全量：…贵人-— … 幕贵-—）；
    旧 ken 请求不带日界两键 → 回放键查无录制。"""
    service, client = _replay_service(tmp_path)
    text = _run(service, "default").data["snapshot_text"]
    shensha = _block(text, "神煞")
    assert "贵人：寅" in shensha and "幕贵：午" in shensha
    ken = _calls(client, "/qimen/pan")[-1]
    assert (ken["realSunTime"], ken["after23NewDay"], ken["lateZiHourUseNextDay"]) == ("2026-09-24 11:08:58", 1, 1)
    chart_req = (_calls(client, "/") or _calls(client, "/chart"))[-1]   # chart 服务把 /chart 挂在根路径
    assert chart_req["hsys"] == 1   # 三式共享主页星盘宫制（newChartSeeds.js:41 出厂 1）


# ═══════════════════════ 2. 六壬层占时随三式农历（timeAlg） ═══════════════════════


@requires_node
def test_sanshiunited_liureng_time_pillar_follows_the_sanshi_timeAlg(tmp_path) -> None:
    """[Item 2] 上游六壬层不另起盘：占日/占时 = buildLrNongli(三式农历, 奇门盘)（:1055 / :3772），随三式 timeAlg。
    权威：live 10:57（上海）直接时间 = 巳时（癸巳），真太阳时 11:08 = 午时（甲午）。
    负向对照：旧代码六壬层另打 /liureng/gods + /chart，课盘占时取 /chart 真太阳时农历 → timeAlg=1 时仍是
    「一课：地盘=辛，天盘=申」（午时课，旧 live 实测），而同一份快照的 [十二盘式] 写着占时巳 —— 红。"""
    service, client = _replay_service(tmp_path)
    clock = _run(service, "clock").data["snapshot_text"]
    assert _block(clock, "大六壬")[0] == "一课：辛酉白虎"
    assert _block(clock, "十二盘式")[1] == "月将：辰；占时：巳；位序：前十一"
    info = _block(clock, "起盘信息")
    assert "四柱：丙午年/丁酉月/辛丑日/癸巳时" in info and "时间算法：直接时间" in info
    assert "真太阳时：2026-09-24 11:08" in info   # resolveDisplaySolarTime：timeAlg=1 另取一份真太阳时农历
    assert [c["timeAlg"] for c in _calls(client, "/nongli/time")] == [1, 0]
    assert not _calls(client, "/liureng/gods")   # 不再另起一张六壬盘
    solar = _run(service, "default").data["snapshot_text"]
    assert _block(solar, "大六壬")[0] == "一课：辛申天空"
    assert _block(solar, "十二盘式")[1] == "月将：辰；占时：午；位序：前十"


@requires_node
def test_sanshiunited_liureng_layer_options_reach_the_cast(tmp_path) -> None:
    """六壬层口径（上游 SANSHI_PAGE_SETTINGS 六壬层 + guireng）经 buildSanshiLiuRengCastOverride 真的改课。
    权威：live 课盘 —— 辛丑日：星占法(2) 一课贵神天空、六壬法(0) 太阴、六壬法+阳阴系 昼夜互换回天空；
    2026-09-15（白露后、秋分前）中气过宫月将巳、节气换将月将辰。
    负向对照：口径被忽略 → 四个断言都等于缺省盘（天空 / 巳）→ 红。"""
    service, _client = _replay_service(tmp_path)
    first = lambda s: _block(_run(service, s).data["snapshot_text"], "大六壬")[0]  # noqa: E731
    assert first("gui0") == "一课：辛申太阴"
    assert first("gui0_yinyang") == "一课：辛申天空"
    zhongqi = _run(service, "zhongqi_0915").data["snapshot_text"]
    jieqi = _run(service, "jieqi_0915").data["snapshot_text"]
    assert "月将：巳" in _block(zhongqi, "起盘信息") and _block(zhongqi, "十二盘式")[1].startswith("月将：巳；")
    assert "月将：辰" in _block(jieqi, "起盘信息") and _block(jieqi, "十二盘式")[1].startswith("月将：辰；")


@requires_node
def test_sanshiunited_rejects_what_upstream_does_not_have(tmp_path) -> None:
    """六壬层键按上游 SANSHI_PAGE_SETTINGS 词表校验（vendored schema，不手抄）；上游三式合一没有的键（十二长生
    五行 wuxing 在三式断卦层恒传 ''）直接报错，不静默吞。负向对照：旧代码把 wuxing 转给 liureng_gods 子盘、
    三式快照不受影响 → ok=True → 红。"""
    service, _client = _replay_service(tmp_path)
    for bad, field in (({"wuxing": "木"}, "liureng_options.wuxing"), ({"guirengType": 7}, "liureng_options.guirengType"),
                       ({"yueJiangMethod": "foo"}, "liureng_options.yueJiangMethod")):
        env = _run(service, "default", liureng_options=bad)
        assert not env.ok and env.error.code == "tool.sanshiunited_invalid_option", (bad, env.error)
        assert env.error.details["field"] == field
    env = _run(service, "default", timeAlg=2)
    assert not env.ok and env.error.details["field"] == "timeAlg"


@requires_node
def test_sanshiunited_ziwei_sihua_is_the_builder_tail_section(tmp_path) -> None:
    """【紫微四化】由上游 builder 自己收尾（buildSanShiZiweiSihuaSnapshotLines，vendored SanShiZiWeiSihua.js）。
    权威：live /ziwei/birth（2026-09-24 10:57 男命）北派四化表。负向对照：旧代码在 Python 里把 JS 段以 [紫微四化]
    拼到尾部 → 段头不是【】→ 红。"""
    service, _client = _replay_service(tmp_path)
    text = _run(service, "sihua").data["snapshot_text"]
    assert text.rstrip().split("\n【")[-1].startswith("紫微四化】")
    assert _block(text, "紫微四化") == [
        "◆ 生年四化（丙）：禄天同·子女；权天机·父母；科文昌·父母；忌廉贞·迁移",
        "◆ 大运四化（3~12　辛卯限）：禄巨门·兄弟；权太阳·兄弟；科文曲·疾厄；忌文昌·父母",
        "◆ 流年四化（2028　戊申）：禄贪狼·夫妻；权太阴·子女；科右弼·命；忌天机·父母",
        "四化随当前紫微流派（beipai）取表；按起课时间排盘。",
    ]


def test_sanshiunited_conditional_sections_are_double_registered() -> None:
    """builder 的挑段（太乙派生 / 六壬断卦 / 紫微四化）只在有正文时出（appendPickedSections :1411-1420），
    故 preset 与 AI_EXPORT_OPTIONAL_SECTIONS 双登记（§5）。负向对照：旧 optional 只有紫微四化/奇门遁甲 →
    本盘缺席的 太乙博弈/空亡真假… 被报 missing → 红。"""
    from horosa_skill.exports.registry import AI_EXPORT_OPTIONAL_SECTIONS, AI_EXPORT_PRESET_SECTIONS

    conditional = ["太乙主客定算", "太乙八门与宿曜", "太乙断法", "太乙七大兵法", "太乙博弈", "太乙命法", "太乙命宫行限",
                   "毕法（已命中）", "占断向导", "年月神煞", "课体结构", "三传旺衰", "空亡真假", "旬空落点", "陷空",
                   "遁干特殊", "年命上神", "七政", "紫微四化", "奇门遁甲"]
    for key in ("sanshiunited", "sanshizeri"):
        assert set(conditional) <= set(AI_EXPORT_PRESET_SECTIONS[key]), key
        assert set(conditional) <= set(AI_EXPORT_OPTIONAL_SECTIONS[key]), key


# ═══════════════════════ 3. 择日展示盘跟随扫描口径 ═══════════════════════


@requires_node
def test_liurengzeri_display_follows_the_scan_jieqi_and_yinyang(tmp_path) -> None:
    """[Item 3] 上游 LiurengZeriMain.applyWorkbenchCalibre（:306-313）：yueMode→yueJiangMethod、yinyangSystem 原名
    回写六壬页后再起盘。权威：2028-04-10（清明后、谷雨前）节气换将月将酉、中气过宫月将戌；live 展示盘。
    负向对照：旧 _zeri_display_overrides 只回写贵人与日界 → 展示盘「换将：中气过宫（默认）」「月将：戌」（旧 live 实测）→ 红。"""
    service, _client = _replay_service(tmp_path)
    env = _run(service, "lrzeri_jieqi")
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    assert "换将：节气换将" in text and "月将：酉；占时：卯；位序：前六" in text
    assert "换将：中气过宫（默认）" not in text


@requires_node
def test_sanshizeri_display_follows_the_scan_liureng_keys(tmp_path) -> None:
    """[Item 3] 上游 SanshiZeriMain.applyWorkbenchCalibre（:319-335）：guirengType→guireng、yueMode→yueJiangMethod、
    其余原名回写三式页。权威：live 展示盘（2028-04-10 05:48 福州，六壬法贵人、节气换将月将酉、太乙金镜）。
    负向对照：旧展示盘不收六壬层 → 「月将：戌」「一课：地盘=乙，天盘=亥，贵神=螣蛇」（旧 live 实测）→ 红。"""
    service, _client = _replay_service(tmp_path)
    env = _run(service, "sszeri_lr")
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    assert "月将：酉" in _block(text, "起盘信息")
    assert _block(text, "大六壬")[0] == "一课：乙戌朱雀"
    assert "古法公式：太乙金鏡" in _block(text, "太乙")   # taiyiAccum → tn 早已到达（base 即如此，这里一并钉住）
    assert "[命中时段]" in text


def test_sanshizeri_display_uses_the_vendored_option_split() -> None:
    """展示盘三家口径取 JS 扫描回传的 vendored splitSanshiOptions（不在 Python 手抄键表）：奇门播种键
    （QM_SEED_KEYS，上游取自三式页本身）也随扫描口径进展示盘；缺拆分即报错而非静默回落。
    负向对照：旧映射只认 6 个奇门盘式键、不收六壬层 → liureng_options/anGanMode 缺席 → 红。"""
    split = {"liureng": {"guirengType": 0, "yueMode": "jieqi", "yinyangSystem": "yinyang", "after23NewDay": 1},
             "qimen": {"qijuMethod": "chaibu", "anGanMode": "dipan", "timeAlg": 1, "after23NewDay": 1},
             "taiyi": {"tn": 2, "after23NewDay": 1}}
    out = HorosaSkillService._zeri_display_overrides("sanshizeri", {"timeAlg": 1}, split)
    assert out["liureng_options"] == {"guirengType": 0, "yueJiangMethod": "jieqi", "yinyangSystem": "yinyang"}
    assert out["qimen_options"] == {"qijuMethod": "chaibu", "anGanMode": "dipan"}
    assert out["taiyi_options"] == {"tn": 2} and out["timeAlg"] == 1
    with pytest.raises(Exception) as exc:
        HorosaSkillService._zeri_display_overrides("sanshizeri", {}, None)
    assert getattr(exc.value, "code", "") == "tool.sanshizeri_option_split_missing"
    lr = HorosaSkillService._zeri_display_overrides("liurengzeri", {"yueMode": "zhongqi", "guirengType": 2})
    assert lr["options"] == {"yueJiangMethod": "zhongqi"} and lr["guirengType"] == 2


@requires_node
def test_zeri_scan_reports_the_vendored_sanshi_split() -> None:
    """JS 扫描回传的 option_split 就是 vendored splitSanshiOptions(options)（真 JS，一小时窗）。"""
    res = _node(
        """
import { runZeriScan } from './src/tools/zeriScan.js';
import { splitSanshiOptions } from './src/vendor/divination/zeri/sanshiOptionSplit.js';
const options = { guirengType: 0, yueMode: 'jieqi', anGanMode: 'dipan', qijuMethod: 'zhirun', taiyiAccum: 1, timeAlg: 0 };
const r = await runZeriScan({ technique: 'sanshizeri', action: 'scan',
  cfg: { startDate: '2028-04-10', startTime: '10:00', endDate: '2028-04-10', endTime: '11:00' },
  geo: { zone: '+08:00', lon: '119e18', lat: '26n05', gpsLon: 119.3, gpsLat: 26.08 }, options,
  tree: { kind: 'group', joiner: 'all', children: [{ kind: 'leaf', type: 'lr_zhou_ye', params: { value: 'day' } }] } });
console.log(JSON.stringify({ ok: r.data.ok, split: r.data.option_split, want: splitSanshiOptions(options) }));
"""
    )
    assert res["ok"] is True and res["split"] == res["want"]
    assert res["split"]["qimen"]["anGanMode"] == "dipan" and res["split"]["taiyi"]["tn"] == 1


# ═══════════════════════ vendoring：截断保留尾部导出清单 ═══════════════════════


def test_truncate_before_keeps_the_tail_export_list_for_head_defined_names() -> None:
    """上游 LiuRengMain.js 在 React 类**之后**用 `export { buildLiuRengReferenceBundle, … }` 导出头部纯函数；
    整段截掉 = 这些函数仍在却不再导出 → vendored SanShiUnitedMain.js 具名 import 它们即链接失败。
    负向对照：旧 truncate_before 不保留清单 → 输出里没有 `export {` 块 → 红。"""
    sys.path.insert(0, str(PKG_ROOT / "scripts"))
    import revendor_core_js as R

    src = (
        "import { x } from './x';\nexport function a(){ return x; }\nfunction b(){ return 1; }\nconst C = 2;\n"
        "class Main extends Component{ render(){ return b() + C; } }\nfunction tailOnly(){}\n"
        "export {\n\tb,\n\tC as Cee,\n\ttailOnly,\n};\nexport default Main;\n"
    )
    out, notes = R.apply_deviations(src, [{"kind": "truncate_before", "anchor": "^class Main extends Component"}])
    assert out.endswith("\nexport {\n\tb,\n\tC as Cee,\n};\n"), out
    assert "tailOnly" not in out and "export default" not in out
    assert any("kept tail export list ×2" in n for n in notes)


@requires_node
def test_vendored_sanshi_head_loads_and_liureng_main_keeps_its_tail_exports() -> None:
    """vendored SanShiUnitedMain.js（截断到 :1690）可载入且导出 builder；LiuRengMain.js 截断后仍导出上游尾部清单的
    8 个头部函数（buildLiuRengReferenceBundle 等，SanShiUnitedMain.js:95-105 具名 import 它们）。"""
    res = _node(
        """
const ss = await import('./src/vendor/sanshi/SanShiUnitedMain.js');
const lr = await import('./src/vendor/liureng/LiuRengMain.js');
const names = ['buildLiuRengReferenceBundle', 'buildReferenceDocumentText', 'buildOverviewReferenceText',
  'XIAO_JU_REFERENCE_TAB_KEYS', 'liurengChouBranch', 'buildQiZhengItems', 'QIZHENG_PLANET_COLOR', 'QIZHENG_WUXING_COLOR'];
console.log(JSON.stringify({ builder: typeof ss.buildSanShiUnitedSnapshotText, missing: names.filter((n) => !(n in lr)) }));
"""
    )
    assert res == {"builder": "function", "missing": []}
