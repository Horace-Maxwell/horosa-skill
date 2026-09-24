"""上游 v3.11 同步 · divination 块：六爻 / 择日十技法 / 一掌经 / 河洛 / 小成图 的口径可达与缺省忠实。

每条都钉「改这个参数，结果必须变」的值级事实（真引擎：vendored core-js 经 node 跑；HTTP 层用记录型桩），
并且在旧代码上必红（负向对照记在各条 docstring 里）。权威出处写在断言旁（上游 Horosa-Public HEAD 9b74714b）。
上游源对拍（键表 / 函数体逐字）只在 HOROSA_SOURCE_ROOT 指向上游 checkout 时跑。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from horosa_skill.agent_guidance import TOOL_GUIDANCE
from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads

PKG = Path(__file__).resolve().parents[1]
CORE_JS_SRC = PKG / "horosa-core-js" / "src"
_UPSTREAM_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
UPSTREAM_UI = Path(_UPSTREAM_ROOT) / "Horosa-Web" / "astrostudyui" / "src" if _UPSTREAM_ROOT else None
requires_upstream = pytest.mark.skipif(
    UPSTREAM_UI is None or not UPSTREAM_UI.is_dir(), reason="HOROSA_SOURCE_ROOT (upstream checkout) not set"
)

# /nongli/time 真实形状（live 9977 实测 2026-09-24 10:58 上海）：timeAlg=0 → birth 为真太阳时、时柱甲午。
NONGLI = {
    "birth": "2026-09-24 11:09:58", "time": "甲午", "dayGanZi": "辛丑", "monthGanZi": "丁酉",
    "year": "丙午", "yearJieqi": "丙午", "monthInt": 8, "dayInt": 14, "jieqi": None, "leap": False,
    "jiedelta": "白露后第17天", "month": "八月", "day": "十四",
}


class RecordingClient(HorosaApiClient):
    """记录每次远端调用；返回真实形状（段级真相归 live 与 JS 引擎）。"""

    def __init__(self) -> None:
        super().__init__("http://fake")
        self.calls: list[tuple[str, dict]] = []

    def probe(self, endpoint: str = "/common/time", payload: dict | None = None) -> bool:
        return True

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        if endpoint == "/nongli/time":
            return {"Result": dict(NONGLI)}
        if endpoint == "/gua/desc":
            return {"Result": {code: {"name": f"卦{code}", "卦辞": "亨。"} for code in payload.get("name") or []}}
        if endpoint in ("/electionscan/scan", "/qizhengelectionscan/scan", "/indiaelectionscan/scan"):
            return {"intervals": [
                {"start": "2028-04-01 06:12", "end": "2028-04-01 07:48", "pick": "2028-04-01 06:13:30",
                 "pickEnd": "2028-04-01 07:46:30", "startJd": 2461862.7583333333, "endJd": 2461862.825, "durationMin": 96.0},
                {"start": "2028-04-02 06:12", "end": "2028-04-02 07:48", "pick": "2028-04-02 06:13:30",
                 "pickEnd": "2028-04-02 07:46:30", "startJd": 2461863.7583333333, "endJd": 2461863.825, "durationMin": 96.0},
            ], "truncated": False, "stats": {"evalPoints": 96}}
        if endpoint in ("/electionscan/explain", "/qizhengelectionscan/explain", "/indiaelectionscan/explain"):
            # 真实形状（election_scan.explain）：{t, tree}，tree 与编译树同构 {kind, op, pass, children}。
            return {"t": payload.get("t"), "tree": {"kind": "group", "op": "all", "pass": True, "children": [
                {"kind": "leaf", "type": "probe", "pass": True, "actual": f"实测@{payload.get('t')}"},
            ]}}
        raise AssertionError(f"unexpected endpoint {endpoint}")

    def endpoints(self, name: str) -> list[dict]:
        return [payload for endpoint, payload in self.calls if endpoint == name]


def _service(tmp_path, client: HorosaApiClient | None = None) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "runtime",
    )
    return HorosaSkillService(settings, client=client or RecordingClient(), store=MemoryStore(settings))


def _run(service: HorosaSkillService, tool: str, payload: dict) -> Any:
    env = service.run_tool(tool, {**payload, "agent_confirmed_settings": True}, save_result=False)
    assert env.ok is True, env.error
    return env


def _node_json(expr_module: str, expr: str) -> Any:
    """跑一段 node：import 仓内 core-js 模块，打印 JSON。"""
    from node_esm import run_node_esm  # Path → file:// URL（Windows ESM loader 不认裸盘符路径）

    script = f"import(process.argv[1]).then((m) => {{ process.stdout.write(JSON.stringify({expr})); }});"
    return json.loads(run_node_esm(script, CORE_JS_SRC / expr_module))


def _lines(text: str | None, pattern: str) -> list[str]:
    return [line for line in (text or "").splitlines() if re.search(pattern, line)]


def _shensha_cells(text: str | None) -> list[str]:
    """[断卦结构] 逐爻表（上游 liuyaoStructLines GFM 表，GuaZhanMain.js:168-181）的「神煞」列（末列，空 = —）。
    wave 3 起 [断卦结构] 由 vendored 上游函数产出，旧行式「 神煞:…」不复存在 —— 断言改看表列，免得恒真。"""
    rows = [line.strip("|").split("|") for line in _lines(text, r"^\| 第[1-6]爻 \|")]
    return [cells[-1].strip() for cells in rows if len(cells) == 10]


# ── F4 六爻：占时时间算法 / 日界 与 判读口径 liuyaoSettings ──────────────────────────────────────


def test_sixyao_nongli_sends_true_solar_default_and_forwards_explicit_switches(tmp_path) -> None:
    """[Q-390/T-372] 占时 timeAlg：页面 > 全局 > 缺省真太阳时 0（GuaZhanMain.genParams :666-669）；日界两键随带。
    负向对照：旧 _run_sixyao_tool 根本不发 timeAlg / after23NewDay / lateZiHourUseNextDay（三条断言全红）。"""
    client = RecordingClient()
    service = _service(tmp_path, client)
    base = {"date": "2026-09-24", "time": "10:58:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "question": "求财"}
    _run(service, "sixyao", base)
    first = client.endpoints("/nongli/time")[-1]
    assert first["timeAlg"] == 0
    assert "after23NewDay" not in first and "lateZiHourUseNextDay" not in first  # 缺省不发 = 后端 1/1
    _run(service, "sixyao", {**base, "timeAlg": 1, "after23NewDay": 0, "lateZiHourUseNextDay": 0})
    second = client.endpoints("/nongli/time")[-1]
    assert (second["timeAlg"], second["after23NewDay"], second["lateZiHourUseNextDay"]) == (1, 0, 0)


def test_sixyao_liuyao_settings_reach_the_judging_engine(tmp_path) -> None:
    """liuyaoSettings 进 analyzeLiuyao：选 school 即套该派细项（上游 mergeLiuyaoGearSettings [Q-206/T-151]）。
    固定卦 乾宫·天风姤(111110, 二爻/上爻动)；权威 = vendored liuyaoSchools 预设表：增删卜易 guashen=false /
    shensha.on=false；askType=wealth → YONGSHEN_CATEGORIES 用神=妻财。
    负向对照：旧 runner 不把 liuyaoSettings 交 JS → 流派恒「通用」、卦身行恒在、用神恒「世」。"""
    service = _service(tmp_path)
    lines = [{"value": v, "change": i in (1, 5)} for i, v in enumerate([1, 1, 1, 1, 0, 0])]
    base = {"date": "2026-09-24", "time": "10:58:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "lines": lines}
    default = _run(service, "sixyao", base).data["snapshot_text"]
    tuned = _run(service, "sixyao", {**base, "liuyaoSettings": {"school": "zengshan", "askType": "wealth"}})
    text = tuned.data["snapshot_text"]
    assert _lines(default, "^流派：") == ["流派：通用（卜筮正宗口径）"] and _lines(default, "^卦身：")
    assert _lines(text, "^流派：") == ["流派：增删卜易(野鹤)"]
    assert not _lines(text, "^卦身：")  # 增删卜易弃卦身
    assert any(cell != "—" for cell in _shensha_cells(default))  # 通用派逐爻带神煞（防下一条恒真）
    assert _shensha_cells(text) == ["—"] * 6  # 增删卜易几弃神煞（shensha.on=false）
    assert _lines(text, "^占测：") == ["占测：求财/买卖/价格/雇员　用神：妻财(1爻)"]
    assert tuned.data["liuyao_settings"]["school"] == "zengshan" and tuned.warnings == []


def test_sixyao_flat_gear_keys_fold_and_bad_keys_are_reported(tmp_path) -> None:
    """扁平齿轮键按上游 mergeLiuyaoGearSettings 折回（shenshaOn→shensha.on；盲派变爻出「盲派作用」行，
    GuaZhanMain.js:188-190）；认不出的键 / 越词表的值 / 只改上游 [断诀命中][占类断语] 的键都进 warnings。
    负向对照：旧 liuyao.js 直接 normalize 嵌套形 → shenshaOn 无效、盲派行不存在、warnings 为空。"""
    service = _service(tmp_path)
    lines = [{"value": v, "change": i in (1, 5)} for i, v in enumerate([1, 1, 1, 1, 0, 0])]
    base = {"date": "2026-09-24", "time": "10:58:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "lines": lines}
    text = _run(service, "sixyao", {**base, "liuyaoSettings": {"shenshaOn": 0, "bianyaoScope": "blind"}}).data["snapshot_text"]
    assert _shensha_cells(text) == ["—"] * 6
    assert _lines(text, "^盲派作用：") == ["盲派作用：第2爻→第1爻(妻财)克合、第2爻→第5爻(子孙)生、第6爻→第3爻(兄弟)生、第6爻→第5爻(子孙)克合"]
    env = _run(service, "sixyao", {**base, "liuyaoSettings": {"school": "nope", "gufa": 1, "bogus": True}})
    joined = " ".join(env.warnings)
    assert "bogus" in joined and "school=nope" in joined
    # wave 3：gufa 等六键只改 [断诀命中]/[占类断语]，两段现由 vendored liuyaoSnapshotEx 产出 → 不再回执为死键。
    assert "gufa" not in joined


def test_liuyao_gear_table_is_guidance_complete() -> None:
    """guidance 必须点名 JS 齿轮表的每一个键（键表单源在 tools/liuyao.js LIUYAO_GEAR_FIELDS）。
    负向对照：旧代码无 LIUYAO_GEAR_FIELDS（node 导出为 undefined → json 解析失败）。"""
    fields = _node_json("tools/liuyao.js", "m.LIUYAO_GEAR_FIELDS")
    assert len(fields) == 24
    intent = TOOL_GUIDANCE["sixyao"]["intent"]
    missing = [key for key in fields if key not in intent]
    assert missing == []


@requires_upstream
def test_liuyao_gear_table_matches_upstream_schema() -> None:
    """LIUYAO_GEAR_FIELDS 逐键 = 上游 techniqueMountSettings.SIXYAO_FIELDS（name + switch/select/multiselect）。"""
    source = (UPSTREAM_UI / "utils" / "techniqueMountSettings.js").read_text(encoding="utf-8")
    block = source[source.index("const SIXYAO_FIELDS = ["): source.index("\n];", source.index("const SIXYAO_FIELDS = ["))]
    upstream = dict(re.findall(r"\{ name: '(\w+)', label: '[^']*', type: '(\w+)'", block))
    assert _node_json("tools/liuyao.js", "m.LIUYAO_GEAR_FIELDS") == upstream


# ── F14 一掌经：桌面出厂档缺省 + 新接通的排盘项 ─────────────────────────────────────────────────


YZJ = {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1}


def test_yizhangjing_defaults_follow_desktop_factory_profile(tmp_path) -> None:
    """KINASTRO_PAGE_SETTINGS 出厂：yizhangjingShensha=false（KinAstroMain.js:1039-1056）。
    逐年法 wave 3 起改随上游 AI 挂载无头路径：未设 → 小限与流年十二神并列 + [流年总论]（证据链见
    tools/yizhangjing.js 注与 test_sync311_divination_w3.py；桌面页出厂 'xiaoxian' 与无头不一致，按无头）。
    负向对照：shenshaLayer 缺省 true → 出 [神煞合参]。"""
    text = _run(_service(tmp_path), "yizhangjing", YZJ).data["snapshot_text"]
    assert _lines(text, "^逐年法") == ["逐年法：小限·起日柱宫·随盘向　重犯口诀：常见组"]
    assert _lines(text, "^小限一宫一年") and _lines(text, "^流年十二神（") and "[流年总论]" in text
    assert "[神煞合参]" not in text


def test_yizhangjing_new_options_change_the_output(tmp_path) -> None:
    """annualMethod / xiaoxianDir / starNaming / daoTerm / tongxianShow / shenshaLayer 均改输出（vendored
    yizhangjingReport.js:246-249,283,361-366）。负向对照：旧 tools/yizhangjing.js 不转发前五键 → 逐年法行不变。"""
    service = _service(tmp_path)
    liunian = _run(service, "yizhangjing", {**YZJ, "annualMethod": "liunian", "starNaming": "B", "daoTerm": "edao",
                                             "shenshaLayer": True, "tongxianShow": False}).data["snapshot_text"]
    assert _lines(liunian, "^逐年法") == ["逐年法：流年十二神(A组)　重犯口诀：常见组　星名系统：B系(显示层)　六道术语：饿鬼道系(显示层)"]
    assert _lines(liunian, "^流年十二神（A组）") and "[神煞合参]" in liunian and "[童限]" not in liunian
    always = _run(service, "yizhangjing", {**YZJ, "xiaoxianDir": "always"}).data["snapshot_text"]
    assert _lines(always, "^小限一宫一年")[0].startswith("小限一宫一年·起日柱宫·一律顺行：")


def test_yizhangjing_day_boundary_defaults_to_23h_new_day(tmp_path) -> None:
    """日界缺省 = 上游 defaultAfter23NewDay()=1（YiZhangJingMain.js:127）：23:30 生人按次日（农历日 +1）。
    1998-02-20 = 正月廿四 → 23:30 缺省作廿五；after23NewDay=0 守廿四。负向对照：旧代码不传日界 → 恒廿四。"""
    service = _service(tmp_path)
    late = {**YZJ, "time": "23:30:00"}
    assert _run(service, "yizhangjing", late).data["yizhangjing"]["input"]["day"] == 25
    assert _run(service, "yizhangjing", {**late, "after23NewDay": 0}).data["yizhangjing"]["input"]["day"] == 24


# ── F15 河洛 quHuaGong / huangdiOffset；小成图 piKoujing ─────────────────────────────────────────


def test_heluo_quhuagong_and_huangdi_offset_change_their_lines(tmp_path) -> None:
    """2026-01-20 在立春前 18 日土用期内（大寒初候）：土王寄坤艮补坤艮/反乾兑，直取四方伯不补
    （heluoLocal.solarTermHuagong）；纪年 = 干支年 2025 + huangdiOffset（heluoLocal.jiNian，0 可达）。
    负向对照：旧 tools/heluo.js 不转发两键 → 两行逐字不变。"""
    service = _service(tmp_path)
    base = {"date": "2026-01-20", "time": "10:00:00", "zone": "+08:00", "lon": "120e00", "gender": 1, "timeAlg": 1}
    default = _run(service, "heluo", base).data["snapshot_text"]
    tuned = _run(service, "heluo", {**base, "quHuaGong": "siFangBoOnly", "huangdiOffset": 0}).data["snapshot_text"]
    assert "化工 坎/坤/艮(有:坎)　葉" in default and "化工 坎(有:坎)　葉" in tuned
    assert _lines(default, "^纪年") == ["纪年：黄帝4722年 · 下元9运 · 乙巳"]
    assert _lines(tuned, "^纪年") == ["纪年：黄帝2025年 · 下元9运 · 乙巳"]


def test_xiaochengtu_pikoujing_flips_the_pi_reading(tmp_path) -> None:
    """「闢」一象之辞两传本相反：天泽履=闢，得配 → 正传「害」、异文「利」（xiaochengtuPan.siXiangOfHex）。
    负向对照：旧 vendored 快照是更早的手抄件，根本不传口径、也无「闢卦细判口径」行。"""
    service = _service(tmp_path)
    base = {"qiguaFa": "manual", "up": "乾", "lo": "兑", "dongYaos": [3], "yongGong": 1, "askEvent": "求财"}
    zheng = _run(service, "xiaochengtu", base).data["snapshot_text"]
    yiwen = _run(service, "xiaochengtu", {**base, "piKoujing": "yiwen"}).data["snapshot_text"]
    assert _lines(zheng, "闢") == ["本卦天泽履:闢(凶·离心;上升下降;得配为情:害)", "闢卦细判口径:正传(得配害·失配利)"]
    assert _lines(yiwen, "闢") == ["本卦天泽履:闢(凶·离心;上升下降;得配为情:利)", "闢卦细判口径:异文(得配利·失配害)"]


@requires_upstream
def test_xiaochengtu_snapshot_builder_is_byte_identical_to_upstream() -> None:
    """vendored buildXiaoChengTuSnapshotText 函数体与上游 XiaoChengTuMain.js 同名函数逐字相同。"""
    def body(text: str) -> str:
        start = text.index("export function buildXiaoChengTuSnapshotText(")
        return text[start: text.index("\n}\n", start) + 3]

    vendored = (CORE_JS_SRC / "vendor" / "xiaochengtu" / "xiaochengtuSnapshot.js").read_text(encoding="utf-8")
    upstream = (UPSTREAM_UI / "components" / "xiaochengtu" / "XiaoChengTuMain.js").read_text(encoding="utf-8")
    assert body(vendored) == body(upstream)


# ── F12 择日展示盘跟随扫描口径 + 上游宿主页出厂扫描口径 ─────────────────────────────────────────


def _capture_base_calls(service: HorosaSkillService) -> list[tuple[str, dict]]:
    """拦下择日 runner 对基底工具的 run_tool（展示盘），只记入参、回一个最小成功信封。"""
    seen: list[tuple[str, dict]] = []
    original = service.run_tool

    def spy(tool_name: str, payload: dict, **kwargs: Any) -> Any:
        if tool_name in ("bazi_birth", "ziwei_birth", "liureng_gods", "taiyi", "sanshiunited", "huangli", "guolao_chart", "chart"):
            seen.append((tool_name, dict(payload)))
            return SimpleNamespace(ok=True, data={"snapshot_text": ""}, error=None)
        return original(tool_name, payload, **kwargs)

    service.run_tool = spy  # type: ignore[method-assign]
    return seen


def _zeri(tool: str, **overrides: Any) -> dict:
    payload = {**build_sample_payloads()[tool], **overrides}
    payload.pop("agent_confirmed_settings", None)
    return payload


def test_zeri_display_pan_follows_scan_options(tmp_path) -> None:
    """上游 v3.11 [挂载自检 F-37]「所见行=所判口径」：各宿主 buildFields/applyWorkbenchCalibre 把冻结扫描 options
    回写展示盘。负向对照：旧 base_payload 丢掉 options → 下面每个断言的键都缺席或取基底工具缺省。"""
    service = _service(tmp_path)
    seen = _capture_base_calls(service)
    _run(service, "bazizeri", _zeri("bazizeri", options={"timeAlg": 1}))
    assert {k: seen[-1][1].get(k) for k in ("timeAlg", "after23NewDay", "godKeyPos", "phaseType")} == \
        {"timeAlg": 1, "after23NewDay": 1, "godKeyPos": "年", "phaseType": 0}  # BaziZeriMain.js:80 + :323-345
    _run(service, "ziweizeri", _zeri("ziweizeri", gender=0))
    assert (seen[-1][0], seen[-1][1].get("timeAlg"), seen[-1][1].get("gender")) == ("ziwei_birth", 1, 0)  # :318-332
    _run(service, "liurengzeri", _zeri("liurengzeri"))
    assert (seen[-1][1].get("guirengType"), seen[-1][1].get("after23NewDay")) == (2, 1)  # LiurengZeriMain.js:79,306-313
    one_day = {"startDate": "2028-04-01", "endDate": "2028-04-01"}  # 太乙/三式扫描最重，一天窗足够钉展示盘入参
    _run(service, "taiyizeri", _zeri("taiyizeri", options={"tn": 1}, **one_day))
    assert seen[-1][1].get("options") == {"tn": 1} and seen[-1][1].get("after23NewDay") == 0  # TaiyiZeriMain.js:255-261,324
    _run(service, "sanshizeri", _zeri("sanshizeri", options={"taiyiAccum": 1, "qijuMethod": "zhirun"}, **one_day))
    assert seen[-1][1].get("taiyi_options") == {"tn": 1} and seen[-1][1].get("qimen_options") == {"qijuMethod": "zhirun"}


def test_ziweizeri_gender_changes_the_scan(tmp_path) -> None:
    """紫微扫描按 options.gender 起盘（computeZiweiScanPan），命宫十二长生随阴阳男女顺逆 → 男女命中集不同。
    负向对照：旧 runner 不合并顶层 gender → 两次都按男命扫，命中集相同。"""
    service = _service(tmp_path)
    _capture_base_calls(service)
    tree = {"kind": "group", "joiner": "all", "children": [
        {"kind": "leaf", "type": "ming_changsheng", "params": {"values": ["长生", "帝旺", "临官"]}}]}
    window = {"startDate": "2028-04-01", "endDate": "2028-04-02", "conditions": tree}
    male = _run(service, "ziweizeri", _zeri("ziweizeri", gender=1, **window)).data["intervals"]
    female = _run(service, "ziweizeri", _zeri("ziweizeri", gender=0, **window)).data["intervals"]
    assert [r["start"] for r in male] != [r["start"] for r in female]


def test_liurengzeri_scans_with_page_default_guiren_and_nonnull_pans(tmp_path) -> None:
    """① 扫描真的出盘：vendored LiuRengMain 曾把 ChuangChart（三传引擎类，非 React 元素）当 UI 桩掉 →
    buildSanChuanData 抛 ReferenceError 被吞成 null → 六壬择时恒零命中。昼占条件一整天必有命中。
    ② 贵人缺省 = 页面出厂 2（LiurengZeriMain.js:79；扫描引擎自身缺省是 0）：2028-04-01 02:30 贵人 g0 临子、g2 临寅
    → 「贵人临寅」命中集随之不同。负向对照：旧代码 ① 零命中；② 不铺出厂档 → 缺省与显式 0 命中集相同。"""
    service = _service(tmp_path)
    _capture_base_calls(service)
    day_tree = {"kind": "group", "joiner": "all", "children": [
        {"kind": "leaf", "type": "zhou_ye", "params": {"value": "day"}}]}
    day = _run(service, "liurengzeri", _zeri("liurengzeri", startDate="2028-04-01", endDate="2028-04-01", conditions=day_tree))
    assert day.data["hit_count"] >= 1
    tree = {"kind": "group", "joiner": "all", "children": [
        {"kind": "leaf", "type": "guiren_pos", "params": {"values": ["寅"], "dir": "any"}}]}
    window = {"startDate": "2028-04-01", "endDate": "2028-04-01", "conditions": tree}
    page_default = _run(service, "liurengzeri", _zeri("liurengzeri", **window)).data["intervals"]
    engine_zero = _run(service, "liurengzeri", _zeri("liurengzeri", guirengType=0, **window)).data["intervals"]
    assert page_default and [r["start"] for r in page_default] != [r["start"] for r in engine_zero]


# ── F13 择日快照「命中清单」：上限 + 前 N 行判读树 ─────────────────────────────────────────────────


def test_local_zeri_snapshot_carries_explain_trees_by_default(tmp_path) -> None:
    """[Q-453] 缺省前 3 行各附判读树（zeriSnapshotPrefs 缺省 3），与扫描同源同步直算；0=不附；maxRows 夹到 10–500。
    负向对照：旧 snapshot 调用不传 explainAt → 缺省无「判读:」行。"""
    service = _service(tmp_path)
    _capture_base_calls(service)
    payload = _zeri("ziweizeri")  # 木三局一周 16 行命中：够验 N=3 与上限夹紧
    default = _run(service, "ziweizeri", payload)
    text = default.data["snapshot_text"]
    assert default.data["hit_count"] > 10 and text.count("   判读:") == 3
    assert "· 设定 五行局·五行局:3 → 实际 木三局 ✓" in text  # 设定配对到 UI 叶（kind:'leaf'），实际来自同源求值
    none = _run(service, "ziweizeri", {**payload, "zeriSnapshotExplainRows": 0}).data["snapshot_text"]
    assert "判读:" not in none
    capped = _run(service, "ziweizeri", {**payload, "zeriSnapshotMaxRows": 1}).data["snapshot_text"]
    listed = [line for line in capped.split("[命中时段]")[1].splitlines() if re.match(r"^\d+\. ", line)]
    assert len(listed) == 10  # maxRows 下限 10（normalizeZeriSnapshotMaxRows）


def test_qimenzeri_snapshot_carries_explain_trees(tmp_path) -> None:
    """奇门择日同律（QimenZeriMain.explainRowSync）。负向对照：旧 qimenzeri.js 快照无 explainAt。"""
    service = _service(tmp_path)
    captured: list[dict] = []
    original = service._run_qimen_tool
    service._run_qimen_tool = lambda payload: (captured.append(dict(payload)) or {"snapshot_text": "", "pan": {}})  # type: ignore[method-assign]
    env = _run(service, "qimenzeri", _zeri("qimenzeri", options={"timeAlg": 1}))
    service._run_qimen_tool = original  # type: ignore[method-assign]
    assert env.data["snapshot_text"].count("   判读:") == min(3, env.data["hit_count"]) > 0
    assert "· 设定 吉格·青龙回首 → 实际 青龙回首@" in env.data["snapshot_text"]  # 裸叶 {type,params} 也配到设定文本
    # 展示盘跟随扫描口径：options.timeAlg 回填顶层（_run_qimen_tool 读顶层起局三开关）。
    assert captured[-1]["timeAlg"] == 1 and captured[-1]["options"]["timeAlg"] == 1


@pytest.mark.parametrize("tool,endpoint", [
    ("tianxing", "/electionscan/explain"),
    ("qizhengzeri", "/qizhengelectionscan/explain"),
    ("indiazeri", "/indiaelectionscan/explain"),
])
def test_backend_zeri_prefetch_explains_like_upstream(tmp_path, tool: str, endpoint: str) -> None:
    """后端扫描家族按上游 prefetchSnapshotExplains 预取前 N 行判读树：t = row.pick、'-'→'/'；0 = 一次不打。
    负向对照：旧 runner 从不打 /explain（除非显式 explainAt），快照无「判读:」行。"""
    client = RecordingClient()
    service = _service(tmp_path, client)
    _capture_base_calls(service)
    env = _run(service, tool, _zeri(tool))
    ts = [p["t"] for p in client.endpoints(endpoint)]
    assert ts == ["2028/04/01 06:13:30", "2028/04/02 06:13:30"][: min(3, env.data["hit_count"])]
    assert "实测@2028/04/01 06:13:30 ✓" in env.data["snapshot_text"]
    client.calls.clear()
    _run(service, tool, _zeri(tool, zeriSnapshotExplainRows=0))
    assert client.endpoints(endpoint) == []


def test_python_explain_rows_clamp_matches_vendored_js() -> None:
    """Python 预取行数与 vendored normalizeZeriSnapshotExplainRows 逐值一致（clampInt：缺省 3、[0,20]、向下取整）。"""
    from horosa_skill.service import _zeri_explain_rows

    inputs = [None, "", 0, 3, 20, 21, -5, "7", 2.9, "abc"]
    js = _node_json(
        "vendor/utils/zeriSnapshotPrefs.js",
        f"{json.dumps(inputs)}.map((v) => m.normalizeZeriSnapshotExplainRows(v === null ? undefined : v))",
    )
    assert [_zeri_explain_rows({"zeriSnapshotExplainRows": v}) for v in inputs] == js


# ── 西占 F11/F12：后端扫描家族真正读的口径键 ─────────────────────────────────────────────────────


def test_qizhengzeri_scan_sends_the_keys_the_backend_reads(tmp_path) -> None:
    """QizhengScanContext 读 su28Mode/nodeType/lilithType（qizheng_election_scan.py:72-81），页面出厂 2/mean/mean；
    展示盘罗计/月孛同跟（guolaoNodeType/guolaoLilithType，perchart.applyGuolaoSiyu）；越界结构化报错。
    负向对照：旧 runner 三键一个不发（options 白名单也滤掉），ayanamsaDeg 照发。"""
    client = RecordingClient()
    service = _service(tmp_path, client)
    seen = _capture_base_calls(service)
    _run(service, "qizhengzeri", _zeri("qizhengzeri"))
    scan = client.endpoints("/qizhengelectionscan/scan")[-1]
    assert (scan["su28Mode"], scan["nodeType"], scan["lilithType"]) == (2, "mean", "mean")
    _run(service, "qizhengzeri", _zeri("qizhengzeri", nodeType="true", options={"su28Mode": 3, "lilithType": "TRUE"}))
    scan = client.endpoints("/qizhengelectionscan/scan")[-1]
    assert (scan["su28Mode"], scan["nodeType"], scan["lilithType"]) == (3, "true", "true")
    assert (seen[-1][1]["guolaoNodeType"], seen[-1][1]["guolaoLilithType"]) == ("true", "true")
    # 宿度制同跟（QizhengZeriMain.js:390）：扫描 3 → 展示盘 doubingSu28=3；缺省扫描 2 → 展示盘 2（不是 guolao 自身缺省）。
    assert seen[-1][1]["doubingSu28"] == 3 and seen[-2][1]["doubingSu28"] == 2
    env = service.run_tool("qizhengzeri", {**_zeri("qizhengzeri", su28Mode=5), "agent_confirmed_settings": True}, save_result=False)
    assert env.ok is False and env.error.code == "tool.qizhengzeri_bad_su28mode"


def test_indiazeri_scan_sends_ayanamsa_and_node_type(tmp_path) -> None:
    """IndiaScanContext 读 ayanamsa（缺省 lahiri）/nodeType（india_election_scan.py:71-72）；indiaAyanamsa 为同词表别名。
    负向对照：旧 runner 只发 indiaAyanamsa（后端不读 → 恒 Lahiri）、不发 nodeType。"""
    client = RecordingClient()
    service = _service(tmp_path, client)
    _run(service, "indiazeri", _zeri("indiazeri"))
    scan = client.endpoints("/indiaelectionscan/scan")[-1]
    assert (scan["ayanamsa"], scan["nodeType"]) == ("lahiri", "mean") and "indiaHsys" not in scan
    _run(service, "indiazeri", _zeri("indiazeri", indiaAyanamsa="raman", nodeType="true"))
    scan = client.endpoints("/indiaelectionscan/scan")[-1]
    assert (scan["ayanamsa"], scan["nodeType"]) == ("raman", "true")
    _run(service, "indiazeri", _zeri("indiazeri", indiaAyanamsa="raman", options={"ayanamsa": "krishnamurti"}))
    assert client.endpoints("/indiaelectionscan/scan")[-1]["ayanamsa"] == "krishnamurti"


def test_tianxing_forwards_lot_and_user_ayanamsa_keys_to_scan_and_moment_chart(tmp_path) -> None:
    """election_scan.ScanContext 自 v3.11 实读 lotReversal/lotFortuneVariant/hermeticLotsReversal/userAyanT0/userAyanDeg
    （election_scan.py:361-374）；[选中时刻星盘] 与扫描同源构参（TianxingElectionMain.previewChartParams）。
    负向对照：旧 _ELECTIONSCAN_OPTION_KEYS 滤掉这五键、子盘也不带。"""
    client = RecordingClient()
    service = _service(tmp_path, client)
    seen = _capture_base_calls(service)
    keys = {"lotReversal": 0, "lotFortuneVariant": "moonAboveNight", "hermeticLotsReversal": 0}
    _run(service, "tianxing", _zeri("tianxing", **keys, options={"userAyanT0": 2451545.0, "userAyanDeg": 30.0}))
    scan = client.endpoints("/electionscan/scan")[-1]
    assert {k: scan.get(k) for k in (*keys, "userAyanT0", "userAyanDeg")} == {**keys, "userAyanT0": 2451545.0, "userAyanDeg": 30.0}
    moment = [payload for name, payload in seen if name == "chart"][-1]
    assert moment["lotReversal"] == 0 and moment["userAyanDeg"] == 30.0


# ── guidance：新缺省如实写成上游缺省 ─────────────────────────────────────────────────────────────


def test_guidance_safe_defaults_state_the_upstream_defaults() -> None:
    def defaults(tool: str) -> dict[str, Any]:
        return {d["field"]: d["value"] for d in TOOL_GUIDANCE[tool]["safe_defaults"]}

    assert defaults("yizhangjing")["shenshaLayer"] is False and defaults("yizhangjing")["annualMethod"] is None
    assert defaults("sixyao")["timeAlg"] == 0
    assert defaults("heluo")["quHuaGong"] == "tuWangKunGen" and defaults("heluo")["huangdiOffset"] == 2697
    assert defaults("xiaochengtu")["piKoujing"] == "zheng"
    assert defaults("liurengzeri")["options"]["guirengType"] == 2
    assert defaults("qizhengzeri")["su28Mode"] == 2 and defaults("indiazeri")["indiaAyanamsa"] == "lahiri"
    for tool in ("huanglizeri", "bazizeri", "taiyizeri", "ziweizeri", "liurengzeri", "sanshizeri",
                 "qimenzeri", "qizhengzeri", "indiazeri", "tianxing"):
        assert (defaults(tool)["zeriSnapshotMaxRows"], defaults(tool)["zeriSnapshotExplainRows"]) == (60, 3), tool


def test_zeri_backend_scan_options_reject_out_of_vocabulary_node_type(tmp_path) -> None:
    service = _service(tmp_path)
    with pytest.raises(ToolValidationError) as err:
        service._zeri_backend_scan_options("indiazeri", {"nodeType": "osculating"})
    assert err.value.code == "tool.indiazeri_bad_nodetype"
