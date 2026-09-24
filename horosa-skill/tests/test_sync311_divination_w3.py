"""上游 v3.11 同步 · wave 3 占卜收口：六爻以时起卦 / [断诀命中][占类断语] / 一掌经逐年法缺省 / 地占恒发三键 /
神数正传大定推运表时间算法。

每条钉「改这个参数，结果必须变」或「与上游同一函数逐字节同」的值级事实（真引擎：vendored core-js 经 node 跑；HTTP 层
用记录型桩，桩值取自 live 9977 /nongli/time 实测 2026-09-24），并在旧代码上必红（负向对照记在各条 docstring 里）。
权威 = 上游 Horosa-Public HEAD 9b74714b（file:line 注在断言旁）。上游源对拍（上游函数源码原样在 Node 里跑 / 源码锚点）
只在 HOROSA_SOURCE_ROOT 指向上游 checkout 时跑。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_local_js_tools import make_service, requires_chart
from test_service import FakeClient, FakeJsClient

import horosa_skill.service as service_module
from horosa_skill.config import Settings
from horosa_skill.errors import ToolTransportError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

PKG = Path(__file__).resolve().parents[1]
CORE_JS_SRC = PKG / "horosa-core-js" / "src"
GUAZHAN = CORE_JS_SRC / "vendor" / "guazhan" / "GuaZhanMain.js"
DOCTRINE_CACHE = CORE_JS_SRC / "vendor" / "gua" / "data" / "liuyaoDoctrineCache.js"
_UPSTREAM_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
UPSTREAM_UI = Path(_UPSTREAM_ROOT) / "Horosa-Web" / "astrostudyui" / "src" if _UPSTREAM_ROOT else None
requires_upstream = pytest.mark.skipif(
    UPSTREAM_UI is None or not UPSTREAM_UI.is_dir(), reason="HOROSA_SOURCE_ROOT (upstream checkout) not set"
)

CONFIRM = {"agent_confirmed_settings": True}
SH = {"zone": "+08:00", "lat": "31n13", "lon": "121e28"}

# live 9977 /nongli/time 实测（上海 121e28 31n13 +08:00）——键 = (date, timeAlg)。
NONGLI: dict[tuple[str, int], dict[str, Any]] = {
    # 10:58 真太阳时 11:09:58 → 时柱甲午；钟表 → 癸巳。
    ("2026-09-24", 0): {"birth": "2026-09-24 11:09:58", "year": "丙午", "yearJieqi": "丙午", "monthGanZi": "丁酉",
                        "dayGanZi": "辛丑", "time": "甲午", "monthInt": 8, "dayInt": 14, "leap": False, "jieqi": None},
    ("2026-09-24", 1): {"birth": "2026-09-24 10:58:00", "year": "丙午", "yearJieqi": "丙午", "monthGanZi": "丁酉",
                        "dayGanZi": "辛丑", "time": "癸巳", "monthInt": 8, "dayInt": 14, "leap": False, "jieqi": None},
    # 戌月（四墓月）10:00：余气强、月建六神等六键都有可见产出。
    ("2026-10-20", 0): {"birth": "2026-10-20 10:19:19", "year": "丙午", "yearJieqi": "丙午", "monthGanZi": "戊戌",
                        "dayGanZi": "丁卯", "time": "乙巳", "monthInt": 9, "dayInt": 11, "leap": False, "jieqi": None},
    # 立春后、正月初一前：后端 year=乙巳（农历年）、yearJieqi=丙午（立春年），无 yearGZByLunar。
    ("2026-02-10", 0): {"birth": "2026-02-10 09:49:56", "year": "乙巳", "yearJieqi": "丙午", "monthGanZi": "庚寅",
                        "dayGanZi": "乙卯", "time": "辛巳", "monthInt": 12, "dayInt": 23, "leap": False, "jieqi": None},
    # 11:05 真太阳时 10:55:19 → 时柱丁巳；钟表 → 戊午。
    ("1998-02-20", 0): {"birth": "1998-02-20 10:55:19", "year": "戊寅", "yearJieqi": "戊寅", "monthGanZi": "甲寅",
                        "dayGanZi": "戊戌", "time": "丁巳", "monthInt": 1, "dayInt": 24, "leap": False},
    ("1998-02-20", 1): {"birth": "1998-02-20 11:05:00", "year": "戊寅", "yearJieqi": "戊寅", "monthGanZi": "甲寅",
                        "dayGanZi": "戊戌", "time": "戊午", "monthInt": 1, "dayInt": 24, "leap": False},
}


class RecordingClient(FakeClient):
    """FakeClient + 按 (date, timeAlg) 回 live 实测 nongli；记录每次请求。"""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, json.loads(json.dumps(payload, ensure_ascii=False))))
        if endpoint == "/nongli/time":
            alg = payload.get("timeAlg")
            return dict(NONGLI[(str(payload["date"]), 0 if alg is None else int(alg))])
        if endpoint == "/gua/desc":
            return {code: {"name": f"卦{code}", "卦辞": "亨。"} for code in payload.get("name") or []}
        return super().call(endpoint, payload)

    def sent(self, endpoint: str) -> list[dict]:
        return [payload for called, payload in self.calls if called == endpoint]


def _service(tmp_path, client: RecordingClient | None = None, js_client: Any = None) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "runtime",
    )
    return HorosaSkillService(settings, client=client or RecordingClient(), store=MemoryStore(settings), js_client=js_client)


def _run(service: HorosaSkillService, tool: str, payload: dict) -> Any:
    return service.run_tool(tool, {**payload, **CONFIRM}, save_result=False)


def _ok(service: HorosaSkillService, tool: str, payload: dict) -> Any:
    env = _run(service, tool, payload)
    assert env.ok is True, env.error
    return env


def _sections(text: str | None) -> dict[str, list[str]]:
    """[段名] → 段内行（去首尾空行）。"""
    out: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in (text or "").split("\n"):
        match = re.fullmatch(r"\[(.+)\]", line)
        if match:
            current = out.setdefault(match.group(1), [])
            continue
        if current is not None:
            current.append(line)
    return {title: "\n".join(body).strip("\n").split("\n") for title, body in out.items()}


def _node(script: str, *args: str) -> str:
    out = subprocess.run(["node", "--input-type=module", "-e", script, *args], check=True, capture_output=True, text=True, encoding="utf-8")
    return out.stdout


SIX = {"date": "2026-09-24", "time": "10:58:00", **SH, "question": "求财"}


# ── 1. 六爻以时起卦 = 上游 buildTimeGua ─────────────────────────────────────────────────────────


def test_sixyao_time_cast_is_upstream_buildTimeGua(tmp_path) -> None:
    """未手动摇卦 → 上游无头路径 buildTimeGua(nongli)（GuaZhanMain.js:74-98，aiAnalysisContext.regenerateSixyaoSnapshot:1748）：
    上卦 Gua8[(年支序+农历月数+农历日数)%8−1]、下卦 +时柱支序、动爻 %6−1。权威 = 把上游文件里 buildTimeGua 的源码原样切出在
    Node 里跑（见 test_vendored_buildTimeGua_is_upstream_source）：甲午时 → 风雷益(100011)上爻动、之卦屯(100010)；
    timeAlg=1 时柱癸巳 → 风火家人(101011)五爻动。爻名 = Gua64.yaoname，无六神（上游无头卦不带 god）。
    负向对照：旧 _time_based_gua_lines 取月/日**地支序** + 钟表时辰（午7+酉10+丑2=19，巳6）→ 火天大有 111101、初爻动。"""
    service = _service(tmp_path)
    solar = _ok(service, "sixyao", SIX).data
    assert (solar["current_code"], solar["changed_code"]) == ("100011", "100010")
    assert [line["name"] for line in solar["lines"]] == ["子水父母", "寅木兄弟", "辰土妻财世", "未土妻财", "巳火子孙", "卯木兄弟应"]
    assert [line["change"] for line in solar["lines"]] == [False] * 5 + [True]
    assert all(line["god"] is None for line in solar["lines"])
    assert "第6爻：阳爻（动），爻名:卯木兄弟应" in solar["snapshot_text"]
    clock = _ok(service, "sixyao", {**SIX, "timeAlg": 1}).data  # 时柱随 timeAlg（nongli.time）
    assert clock["current_code"] == "101011" and [line["change"] for line in clock["lines"]].index(True) == 4


def test_sixyao_gua_code_without_lines_is_the_given_gua(tmp_path) -> None:
    """只给本卦/变卦码（不给 lines）：卦线由码定（初→上，动爻 = 两码相异之位），不落以时起卦。
    负向对照：旧 runner 以时起卦 → [卦象] 写用户给的乾为天，[六爻与动爻]/[断卦结构] 判的却是风雷益。"""
    env = _ok(_service(tmp_path), "sixyao", {**SIX, "gua_code": "111111", "changed_code": "111110"})
    assert [line["value"] for line in env.data["lines"]] == [1] * 6
    assert [line["change"] for line in env.data["lines"]] == [False] * 5 + [True]
    assert "卦序：乾宫·本宫(世6应3)" in _sections(env.data["snapshot_text"])["断卦结构"]


@requires_upstream
def test_vendored_buildTimeGua_is_upstream_source() -> None:
    """上游 buildTimeGua 源码原样切出、在 Node 里对真 GuaConst 求值，与 vendored 函数逐格对拍（12 时辰 × 月日网格）。"""
    source = (UPSTREAM_UI / "components" / "guazhan" / "GuaZhanMain.js").read_text(encoding="utf-8")
    start = source.index("export function buildTimeGua(nongli){")
    body = source[start: source.index("\n}\n", start) + 3]
    vendored = GUAZHAN.read_text(encoding="utf-8")
    assert body in vendored  # 函数体逐字
    script = """
const [G, L, V] = await Promise.all([import(process.argv[1]), import(process.argv[2]), import(process.argv[3])]);
const src = process.argv[4].replace('export function', 'function');
const up = new Function('ZiList', 'Gua8', 'Gua64', 'getGua64', 'littleEndian', 'AstroConst', `${src}\\nreturn buildTimeGua;`)(
  G.ZiList, G.Gua8, G.Gua64, G.getGua64, L.littleEndian, { AstroColor: {} });
const zhi = G.ZiList; const out = [];
for (const y of ['甲子', '丙午', '乙巳']) for (const m of [1, 8, 12]) for (const d of [1, 14, 30]) for (const z of zhi) {
  const n = { year: y, monthInt: m, dayInt: d, time: `甲${z}` };
  const f = (g) => [g.currentGua, g.yao.map((x) => `${x.value}${x.change ? '*' : ''}${x.name}`).join(',')];
  out.push(JSON.stringify(f(up(n))) === JSON.stringify(f(V.buildTimeGua(n))));
}
process.stdout.write(JSON.stringify(out));
"""
    same = json.loads(_node(script, str(CORE_JS_SRC / "vendor" / "gua" / "GuaConst.js"),
                            str(CORE_JS_SRC / "vendor" / "gua" / "littleEndian.js"), str(GUAZHAN), body))
    assert len(same) == 3 * 3 * 3 * 12 and all(same)


# ── 2. [断诀命中] / [占类断语]（+ [断卦结构]）= 上游 buildGuaSnapshotText 同一段字节 ───────────────


_UPSTREAM_HEADLESS = """
const [gz, dc] = await Promise.all([import(process.argv[1]), import(process.argv[2])]);
const nongli = JSON.parse(process.argv[3]);
const gear = JSON.parse(process.argv[4]);
await dc.loadDoctrine();                                        // ensureLiuyaoDoctrineLoaded（aiAnalysisContext.js:1735-1737）
const gua = gz.buildTimeGua(nongli);                            // regenerateSixyaoSnapshot:1748
const st = Object.keys(gear).length ? { ...gua, liuyaoSettings: gear } : gua;
const at = (s) => ({ format: () => s });
const fields = { date: { value: at('x') }, time: { value: at('x') }, zone: { value: '+08:00' }, lon: { value: '121e28' }, lat: { value: '31n13' } };
process.stdout.write(gz.buildGuaSnapshotText(fields, st));
"""


@pytest.mark.parametrize("date,settings", [
    ("2026-09-24", {}),
    ("2026-10-20", {"school": "tianji"}),  # 断易天机派：世身/扩展神煞/月建六神/古法/天时古法全开
])
def test_sixyao_judging_sections_are_the_upstream_builder_bytes(tmp_path, date: str, settings: dict) -> None:
    """[断卦结构]/[断诀命中]/[占类断语] 三段与上游无头路径（regenerateSixyaoSnapshot：先载断语库 → buildTimeGua →
    buildGuaSnapshotText，:1739-1760）逐字节相同 —— 参照侧直接跑 vendored 上游 buildGuaSnapshotText（revendor 流水线
    对上游逐字可复现），与 skill 的装配代码无关。另钉值级锚点（三层环境 / 历史占例 / 断语库首条）。
    负向对照：旧 runner 不产 [断诀命中]/[占类断语]（KeyError），[断卦结构] 是旧手抄行式（逐爻非 GFM 表）；
    tools/liuyao.js 不 await loadDoctrine 时 [占类断语] 缺「断语·」行、与参照不等。"""
    service = _service(tmp_path)
    payload = {**SIX, "date": date, "time": "10:00:00" if date == "2026-10-20" else SIX["time"]}
    if settings:
        payload["liuyaoSettings"] = settings
    env = _ok(service, "sixyao", payload)
    ours = _sections(env.data["snapshot_text"])
    gear = {"school": "tianji"} if settings else {}
    # 参照侧的 liuyaoSettings = 上游 mergeLiuyaoGearSettings({}, {school}) = applyPreset(school, {})。
    if gear:
        gear = json.loads(_node(
            "import(process.argv[1]).then((m) => process.stdout.write(JSON.stringify(m.applyPreset('tianji', {}))));",
            str(CORE_JS_SRC / "vendor" / "gua" / "liuyaoSchools.js")))
    upstream = _sections(_node(_UPSTREAM_HEADLESS, str(GUAZHAN), str(DOCTRINE_CACHE),
                               json.dumps(NONGLI[(date, 0)], ensure_ascii=False), json.dumps(gear, ensure_ascii=False)))
    for title in ("断卦结构", "断诀命中", "占类断语"):
        assert ours[title] == upstream[title], title
    assert [t for t in ours if t in ("断诀命中", "占类断语")] == ["断诀命中", "占类断语"]
    assert list(ours).index("卦辞与断语") < list(ours).index("断诀命中")  # buildGuaSnapshotText:338-388 段序
    if not settings:
        assert ours["断诀命中"][0] == "三层环境：太岁午(岁破子)　月建酉(月破卯)　日建丑(日破未)"
        assert ours["占类断语"][:2] == ["历史占例：冉伯牛有疾卜得,乃知谩师之过也", "断语·总断门第一·孙膑：孙膑总断歌"]
    else:
        assert "世身：第5爻 未土父母" in ours["断诀命中"]
        assert "天时·古法分列(4 家;各家自成体系、彼此有冲突,不可合成单一结论)" in ours["占类断语"]
    assert env.data["export_snapshot"]["missing_selected_sections"] == []
    assert env.data["export_snapshot"]["unknown_detected_sections"] == []


SIX_KEYS = [
    # (键, 值, 行首标签, 期望新增行, 所在段) —— 期望行 = vendored 上游引擎对 2026-10-20 10:00 以时起卦（火天大有、三爻动）的输出。
    ("shishen", "standard", "世身：", "世身：第5爻 未土父母", "断诀命中"),
    ("tianshiSchool", "ancient", "天时·", "天时·古法分列(4 家;各家自成体系、彼此有冲突,不可合成单一结论)", "占类断语"),
    ("yuqi", 1, "余气强：", "余气强：第4爻酉(月建余气助之)", "断诀命中"),
    ("gufa", 1, "十六变：", "十六变：第9变·归魂(事归、可成)", "占类断语"),
    ("yueLiushen", 1, "月建六神：", "月建六神：第3爻:白虎　第4爻:勾陈　第5爻:玄武", "断诀命中"),
    ("shenshaExOn", 1, "扩展/月令神煞：", "扩展/月令神煞：第1爻(子):大刑(虎刑)·天解·外解·大杀·飞廉·网罗·奸私", "断诀命中"),
]


@pytest.mark.parametrize("key,value,label,line,section", SIX_KEYS)
def test_sixyao_formerly_dead_judging_keys_now_change_the_output(
    tmp_path, key: str, value: Any, label: str, line: str, section: str,
) -> None:
    """六键只影响 [断诀命中]/[占类断语]（liuyaoSnapshotEx.duanJueLines/zhanleiLines 读 a.shiShen/a.tianshi/yuqiStrong/
    a.gufa/a.yueLiuShenAnn/a.shenShaEx，liuyaoFacade.js:107-228）。两段现由 vendored 上游函数产出 → 键键生效。
    负向对照：旧 runner 不产两段、且把这六键回执为「本工具尚不产这两段」的死键（warnings 含键名）。"""
    service = _service(tmp_path)
    base = {**SIX, "date": "2026-10-20", "time": "10:00:00"}
    plain = _sections(_ok(service, "sixyao", base).data["snapshot_text"])
    env = _ok(service, "sixyao", {**base, "liuyaoSettings": {key: value}})
    tuned = _sections(env.data["snapshot_text"])
    assert [row for row in tuned[section] if row.startswith(line)]
    assert not [row for row in plain[section] if row.startswith(label)]  # 缺省（键关）该行不出
    assert key not in " ".join(env.warnings)


def test_sixyao_year_boundary_lunar_reads_the_lunar_new_year_gz(tmp_path) -> None:
    """定年界线=正月初一：上游 fetchPreciseNongli 的 ensureYearGZByLunar（preciseCalcBridge.js:361-377）给后端 nongli 补
    yearGZByLunar（本地历法 buildLocalBaziResult）。2026-02-10 在立春后、正月初一前：立春年丙午、农历年乙巳 → 太岁午 / 巳。
    负向对照：旧 runner 不补该键 → liuyaoSnapshotEx:17-19 回落 yearJieqi → 两档都是「太岁午」（死开关）。"""
    service = _service(tmp_path)
    base = {**SIX, "date": "2026-02-10", "time": "10:00:00"}
    runs = {mode: _ok(service, "sixyao", {**base, "liuyaoSettings": {"yearBoundary": mode}}).data for mode in ("lichun", "lunar")}
    envs = {mode: _sections(data["snapshot_text"]) for mode, data in runs.items()}
    assert envs["lichun"]["断诀命中"][0].startswith("三层环境：太岁午(岁破子)")
    assert envs["lunar"]["断诀命中"][0].startswith("三层环境：太岁巳(岁破亥)")
    # 同一窗口也钉起卦的年项：buildTimeGua 取 nongli.year（后端 = 农历年乙巳 → 巳6）而非立春年丙午：
    # 6+12+23=41 → 上乾、+辛巳6=47 → 下艮、47%6 → 五爻动 = 天山遁 001111（按丙午则是泽地萃 000110）。
    assert runs["lichun"]["current_code"] == "001111" and [line["change"] for line in runs["lichun"]["lines"]].index(True) == 4


def test_sixyao_js_side_notes_become_envelope_warnings(tmp_path) -> None:
    """JS 层自报的缺损（断语库未载入等，上游同样不阻断快照）进 envelope.warnings，不静默。
    负向对照：旧 runner 不读 data.warnings。"""
    class NoDoctrineJs(FakeJsClient):
        def run(self, tool_name: str, payload: dict) -> dict:
            result = super().run(tool_name, payload)
            if tool_name == "liuyao":
                result["data"] = {**result["data"], "doctrine_loaded": False, "warnings": ["六爻《断易天机》断语库未能载入：测试"]}
            return result

    env = _ok(_service(tmp_path, js_client=NoDoctrineJs()), "sixyao", SIX)
    assert "六爻《断易天机》断语库未能载入：测试" in env.warnings


def test_sixyao_time_cast_needs_the_js_engine_and_says_so(tmp_path) -> None:
    """以时起卦只在 vendored 上游函数里：JS 引擎起不来 → 结构化错误 tool.sixyao_time_cast_failed，绝不回落自写起卦式；
    手动摇卦亦然（wave 3b 起整份快照 = vendored buildGuaSnapshotText，Python 不再自写段）→ tool.sixyao_engine_failed。
    负向对照：旧 runner 在 Python 里按手写式起卦，引擎失败照样 ok=True。"""
    class DeadJs(FakeJsClient):
        def run(self, tool_name: str, payload: dict) -> dict:
            raise ToolTransportError("node missing", code="js_engine.node_missing")

    service = _service(tmp_path, js_client=DeadJs())
    env = _run(service, "sixyao", SIX)
    assert env.ok is False and env.error.code == "tool.sixyao_time_cast_failed"
    lines = [{"value": v, "change": i == 0} for i, v in enumerate([1, 1, 1, 1, 1, 1])]
    manual = _run(service, "sixyao", {**SIX, "lines": lines})
    assert manual.ok is False and manual.error.code == "tool.sixyao_engine_failed"


# ── 3. 一掌经逐年法缺省 = 上游 AI 挂载无头路径（未设 → 两法并列） ────────────────────────────────


YZJ = {"date": "1998-02-20", "time": "20:48:00", **SH, "gender": 1}


def test_yizhangjing_annual_method_unset_mirrors_the_headless_mount(tmp_path) -> None:
    """上游 AI 挂载缺省（未拨齿轮）：regenerateChartTechniqueSnapshot → buildYizhangjingSnapshotForRecord(record,
    {annualMethod: record.annualMethod})（aiAnalysisContext.js:3249-3259）→ undefined → yizhangjingReport.js:248 归 '' →
    :477-479 小限与流年十二神同出（+[流年总论]）。桌面页出厂 'xiaoxian'（KinAstroMain.js:1046）与此不一致，按无头。
    权威值 = vendored yizhangjingReport 对 1998-02-20 20:48 男命的输出。负向对照：旧 schema 缺省 'xiaoxian' → 缺省无流年十二神行。"""
    service = _service(tmp_path)
    xiao = "小限一宫一年·起日柱宫·随盘向：1=天厄 2=天權 3=天破 4=天奸 5=天文 6=天福 7=天驛 8=天孤 9=天刃"
    shen = "流年十二神（A组）以本命年支「寅」起太岁顺布，四柱/命宫落宫值神：年=太岁 月=太岁 日=病符 时=贵人 命=贵人"

    def rows(text: str) -> tuple[bool, bool, bool]:
        lines = text.split("\n")
        return (any(line.startswith(xiao) for line in lines), shen in lines, "[流年总论]" in lines)

    default = _ok(service, "yizhangjing", YZJ).data
    assert rows(default["snapshot_text"]) == (True, True, True)
    assert default["input_normalized"]["annualMethod"] == ""
    assert rows(_ok(service, "yizhangjing", {**YZJ, "annualMethod": "xiaoxian"}).data["snapshot_text"]) == (True, False, False)
    assert rows(_ok(service, "yizhangjing", {**YZJ, "annualMethod": "liunian"}).data["snapshot_text"]) == (False, True, True)


@requires_upstream
def test_yizhangjing_headless_default_evidence_still_holds_upstream() -> None:
    """证据链源码锚：无头挂载传 record.annualMethod、引擎把非 xiaoxian/liunian 归 ''、挂载齿轮缺省 'xiaoxian'（拨「小限」
    被 prune 成无覆盖）、页面出厂 'xiaoxian'。任一处上游改了就红 —— 提示重审 skill 的缺省。"""
    ctx = (UPSTREAM_UI / "utils" / "aiAnalysisContext.js").read_text(encoding="utf-8")
    report = (UPSTREAM_UI / "utils" / "yizhangjingReport.js").read_text(encoding="utf-8")
    mount = (UPSTREAM_UI / "utils" / "techniqueMountSettings.js").read_text(encoding="utf-8")
    page = (UPSTREAM_UI / "components" / "kinastro" / "KinAstroMain.js").read_text(encoding="utf-8")
    call = ctx[ctx.index("return await buildYizhangjingSnapshotForRecord(record, {"):]
    assert "annualMethod: record.annualMethod," in call[: call.index("});")]
    assert "const annualMethod = (o.annualMethod === 'liunian' || o.annualMethod === 'xiaoxian') ? o.annualMethod : '';" in report
    assert "{ name: 'annualMethod', label: '逐年法', type: 'select', default: 'xiaoxian'" in mount
    assert "yizhangjingAnnual: { def: 'xiaoxian'" in page


# ── 4. 地占：所问宫 / 读取范围 / 黄道体系恒发（上游两路同形） ────────────────────────────────────


GEO = {"date": "1998-02-20", "time": "20:48:00", **SH, "question": "x", "questionType": "career"}


def test_geomancy_always_sends_quesited_house_scope_and_zodiac(tmp_path) -> None:
    """页面 clickCast（GeomancyMain.js:1150-1158）与 AI 挂载复算（:808-817）恒发 quesitedHouse = 所问宫 ||
    QUESTION_TYPE_HOUSE[问类]（:205-208）、readingScope || 'L3'、zodiacSystem || 'classical'；换流派不动后两项。
    负向对照：旧 runner 未给即不发 → 内核按流派回落（european_planetary→planetary、arabic_raml→L2）。"""
    client = RecordingClient()
    service = _service(tmp_path, client, js_client=FakeJsClient())
    for profile in ("european_classical", "european_planetary", "arabic_raml"):
        _ok(service, "geomancy", {**GEO, "profile": profile})
        sent = client.sent("/geomancy/reading")[-1]
        assert (sent["quesitedHouse"], sent["readingScope"], sent["zodiacSystem"]) == (10, "L3", "classical"), profile
    _ok(service, "geomancy", {**GEO, "questionType": "custom"})
    assert client.sent("/geomancy/reading")[-1]["quesitedHouse"] == 1
    _ok(service, "geomancy", {**GEO, "quesitedHouse": 3, "readingScope": "L2", "zodiacSystem": "planetary"})
    sent = client.sent("/geomancy/reading")[-1]
    assert (sent["quesitedHouse"], sent["readingScope"], sent["zodiacSystem"]) == (3, "L2", "planetary")


@requires_upstream
def test_geomancy_question_house_table_matches_upstream() -> None:
    """_GEOMANCY_QUESTION_HOUSE 逐值 = 上游 QUESTION_TYPE_HOUSE（GeomancyMain.js:205-208）。"""
    source = (UPSTREAM_UI / "components" / "geomancy" / "GeomancyMain.js").read_text(encoding="utf-8")
    block = source[source.index("const QUESTION_TYPE_HOUSE = {"): source.index("};", source.index("const QUESTION_TYPE_HOUSE = {"))]
    upstream = {k: int(v) for k, v in re.findall(r"(\w+): (\d+)", block)}
    assert upstream == service_module._GEOMANCY_QUESTION_HOUSE


@requires_chart
def test_live_geomancy_profiles_keep_upstream_zodiac_and_scope(tmp_path) -> None:
    """live：european_planetary 不再落行星黄道（快照无「黄道=行星归属体系」）、arabic_raml 不再只读到 L2（无「范围=L2」）。
    负向对照：旧 runner 不发两键 → 内核回落流派 profile（profiles.json：planetary / L2）。"""
    service = make_service(tmp_path)
    planetary = service.run_tool("geomancy", {**GEO, **CONFIRM, "profile": "european_planetary"}, save_result=False)
    raml = service.run_tool("geomancy", {**GEO, **CONFIRM, "profile": "arabic_raml"}, save_result=False)
    assert planetary.ok and raml.ok, (planetary.error, raml.error)
    assert planetary.data["reading"]["zodiacSystem"] == "classical" and "黄道=行星归属体系" not in planetary.data["snapshot_text"]
    assert raml.data["reading"]["readingScope"] == "L3" and "范围=L2" not in raml.data["snapshot_text"]


# ── 5. 神数正传 · 大定推运表与四柱同一时间算法 ─────────────────────────────────────────────────


ZC = {"date": "1998-02-20", "time": "11:05:00", **SH, "gender": 1, "school": "dading", "dadingYear": 2030}


def test_zhengchuan_dading_luck_table_shares_the_pillars_time_algorithm(tmp_path) -> None:
    """上游页面与无头挂载都是一次 buildLocalBaziResult 同出四柱与推运表（ZhengChuanMain.getModel:145-189 /
    aiAnalysisContext.buildChartShusuanBazi:1948-1979；无头 timeAlg = record.timeAlg ?? 0，buildFieldObject:603）。
    1998-02-20 11:05：真太阳时 → 时柱丁巳、2030 小运庚寅（vendored buildLocalBaziResult + deriveDadingYearPillars 实算；
    行内首项丁巳是 2030 的大运，与时柱同名纯属巧合）；钟表时 → 时柱戊午、小运辛卯。负向对照：旧码四柱走后端缺省 0
    （时柱丁巳）而推运表走 JS 缺省 1 → 缺省即出「丁巳 ／ 辛卯 ／ 庚戌」（小运按钟表时柱推，与四柱不同源）。"""
    client = RecordingClient()
    service = _service(tmp_path, client)
    default = _ok(service, "zhengchuan", ZC).data["snapshot_text"]
    assert "| 大运／小运／岁君 | 丁巳 ／ 庚寅 ／ 庚戌 |" in default.split("\n")
    assert client.sent("/nongli/time")[-1]["timeAlg"] == 0
    clock = _ok(service, "zhengchuan", {**ZC, "timeAlg": 1}).data["snapshot_text"]
    assert "| 大运／小运／岁君 | 丁巳 ／ 辛卯 ／ 庚戌 |" in clock.split("\n")
