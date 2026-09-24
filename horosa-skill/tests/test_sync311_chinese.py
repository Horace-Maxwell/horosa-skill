"""v3.11.x 上游同步 · 中国技法 chunk（八字 / 紫微 / 六壬 / 三式合一 / 七政四余 / 印度律盘）的回归与值级金标。

每条都写明「旧代码为什么会红」（负向对照）：
- 真 node 引擎的用例直接跑 horosa-core-js（与生产同一条 cli 路径 / vendored 模块），期望值的权威出处写在注释里；
- 服务层用例用 test_service 的 HTTP 桩 + 真 JS 引擎或带真内容的桩，断言段真的进了导出契约。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from test_service import CaptureClient, FakeClient, FakeJsClient

# service 的私有助手按「svc.X」在用例里取（而不是顶层 from-import）：负向对照在旧代码上跑时，缺哪个助手
# 只红用它的那几条，而不是整个文件 import 失败 —— 否则「旧代码会红」对每条用例都成了同一个无信息的原因。
import horosa_skill.service as svc
from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.errors import ToolValidationError
from horosa_skill.exports.registry import (
    AI_EXPORT_OPTIONAL_SECTIONS,
    AI_EXPORT_PRESET_SECTIONS,
)
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _node(script: str) -> dict:
    """在 horosa-core-js 下跑一段 ESM 脚本，脚本须 `console.log(JSON.stringify(...))` 作为最后一行输出。"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=CORE_JS, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _settings(tmp_path) -> Settings:
    return Settings(
        server_root="http://127.0.0.1:9999",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )


def _real_js(tmp_path) -> HorosaJsEngineClient:
    return HorosaJsEngineClient(_settings(tmp_path))


def _section(text: str, title: str) -> str:
    head = f"[{title}]\n"
    assert head in text, f"missing [{title}] in:\n{text[:1500]}"
    body = text.split(head, 1)[1]
    nxt = body.find("\n[")
    return (body if nxt < 0 else body[:nxt]).strip()


# ────────────────────────────── 时间基准行（上游 utils/timeBasisLine.js）──────────────────────────────

def test_time_basis_line_mirrors_upstream_builder() -> None:
    # 权威：上游 timeBasisLine.js（TIME_ALG_LABEL / yesNo 缺位回退「否」/ zone、note 缺省不产 / `；` 连接）。
    assert svc.build_time_basis_line(time_alg=0, late_zi_hour_use_next_day=1, after23_new_day=0) == (
        "时间基准：真太阳时(经度+均时差校正)；晚子时归次日：是；23 点换日：否"
    )
    # timeAlg 缺位 → 钟表时（七政 fieldsToParams 不带 timeAlg 的就是这一档）；开关缺位 → 否。
    assert svc.build_time_basis_line(time_alg=None, late_zi_hour_use_next_day=None, after23_new_day=None) == (
        "时间基准：钟表时(按输入钟面时刻,无真太阳时校正)；晚子时归次日：否；23 点换日：否"
    )
    assert svc.build_time_basis_line(time_alg=3, late_zi_hour_use_next_day="0", after23_new_day=True, zone="+08:00", note="补注") == (
        "时间基准：平太阳时(仅经度校正,无均时差)；晚子时归次日：否；23 点换日：是；时区：+08:00；补注"
    )
    # 未知档原样回显（JS `TIME_ALG_LABEL[x] || x`）。
    assert svc.build_time_basis_line(time_alg=7, late_zi_hour_use_next_day=1, after23_new_day=1).startswith("时间基准：7；")


# ────────────────────────────── 八字 ──────────────────────────────

# 2028-01-30 09:33 上海：Java /bazi/birth 实测 nongli.year=戊申（正月初一岁首）、yearJieqi=丁未（立春岁首）。
_BAZI_NONGLI_0130 = {
    "year": "戊申", "yearJieqi": "丁未", "month": "正月", "day": "初五", "leap": False,
    "birth": "2028-01-30 09:24:01", "clockTime": "2028-01-30 09:33:00",
}


def _bazi_payload(**extra):
    return {"date": "2028-01-30", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
            "timeAlg": 0, "after23NewDay": False, "adjustJieqi": False, **extra}


def test_bazi_info_gains_time_basis_and_shengxiao_lines() -> None:
    """上游 BaZi.js:361（时间基准）/ :369-375（生肖）。旧 builder 两行都没有 → 红。"""
    text = svc._build_bazi_snapshot_text(_bazi_payload(), {"bazi": {"nongli": _BAZI_NONGLI_0130, "fourColumns": {}}})
    info = _section(text, "起盘信息").splitlines()
    # 缺省：Java /bazi/birth 晚子时开关缺省 1（BaZiBirthController.java:98），after23NewDay 由 schema 缺省 False 下发。
    assert "时间基准：真太阳时(经度+均时差校正)；晚子时归次日：是；23 点换日：否" in info
    assert info.index("时间算法：真太阳时") + 1 == info.index("时间基准：真太阳时(经度+均时差校正)；晚子时归次日：是；23 点换日：否")
    # 立春岁首（缺省）：yearJieqi 丁未 → 羊；正月初一岁首：year 戊申 → 猴（两档正好差一个生肖）。
    assert "生肖：羊（岁首=立春）" in info
    assert info.index("农历：戊申年正月初五") < info.index("生肖：羊（岁首=立春）") < info.index("真太阳时：2028-01-30 09:24:01")
    lunar = _section(
        svc._build_bazi_snapshot_text(_bazi_payload(zodiacBoundary="lunar"), {"bazi": {"nongli": _BAZI_NONGLI_0130}}),
        "起盘信息",
    )
    assert "生肖：猴（岁首=正月初一）" in lunar
    flipped = _section(
        svc._build_bazi_snapshot_text(_bazi_payload(lateZiHourUseNextDay=0, after23NewDay=True), {"bazi": {"nongli": _BAZI_NONGLI_0130}}),
        "起盘信息",
    )
    assert "时间基准：真太阳时(经度+均时差校正)；晚子时归次日：否；23 点换日：是" in flipped
    # 认不出的岁首档不静默：按立春出、进 warnings（改这个参数结果必须变 / 变不了就得说）。
    with svc._degrade_collector() as notes:
        bogus = _section(
            svc._build_bazi_snapshot_text(_bazi_payload(zodiacBoundary="spring"), {"bazi": {"nongli": _BAZI_NONGLI_0130}}),
            "起盘信息",
        )
    assert "生肖：羊（岁首=立春）" in bogus
    assert any("zodiacBoundary='spring'" in note for note in notes), notes


def test_bazi_adjust_jieqi_bool_is_labelled_not_printed_raw() -> None:
    """schema 里 adjustJieqi 是 bool：旧版 str(False)='False' 查表落空 →「节气修正：False」原样进快照。"""
    info = _section(svc._build_bazi_snapshot_text(_bazi_payload(), {"bazi": {"nongli": _BAZI_NONGLI_0130}}), "起盘信息")
    assert "节气修正：不调整节气" in info and "节气修正：False" not in info
    on = _section(svc._build_bazi_snapshot_text(_bazi_payload(adjustJieqi=True), {"bazi": {"nongli": _BAZI_NONGLI_0130}}), "起盘信息")
    assert "节气修正：节气按纬度调整" in on


# ────────────────────────────── 紫微 ──────────────────────────────

_ZW_HOUSES = [
    ("命宫", "癸亥", [2, 11]), ("父母宫", "甲子", [12, 21]), ("福德宫", "乙丑", [22, 31]), ("田宅宫", "甲寅", [32, 41]),
    ("官禄宫", "乙卯", [42, 51]), ("交友宫", "丙辰", [52, 61]), ("迁移宫", "丁巳", [62, 71]), ("疾厄宫", "戊午", [72, 81]),
    ("财帛宫", "己未", [82, 91]), ("子女宫", "庚申", [92, 101]), ("夫妻宫", "辛酉", [102, 111]), ("兄弟宫", "壬戌", [112, 121]),
]
# 2028-04-06 09:33 上海（戊申年，水二局）/ziwei/birth 实测盘的运限骨架（宫名/宫干支/大限）。
_ZW_CHART = {
    "birth": "2028-04-06 09:33:00", "yearGan": "戊", "yearZi": "申", "wuxingJu": 2, "lifeHouseIndex": 0,
    "houses": [{"name": n, "ganzi": gz, "direction": d} for n, gz, d in _ZW_HOUSES],
}


@requires_node
def test_ziwei_period_overview_is_unconditional_real_engine(tmp_path) -> None:
    """[运限概览]（上游 v3.11.0 #80，ZiWeiMain.js:241-256 / :597-599）：不给 period/schools 也出。
    旧 ziweiExtras 只有 [运限]/[流派叠层]，且 Python 侧在两者都缺时直接不调 JS → 红。"""
    out = _real_js(tmp_path).run("ziwei_extras", {"chart": _ZW_CHART})
    body = _section(out["text"], "运限概览").splitlines()
    assert body[:3] == [
        "全大限 × 流年一览(公历年与干支由代码算出,禁自行推算):",
        "| 虚岁 | 宫位 | 宫干支 | 该限流年（公历年-干支） |",
        "| --- | --- | --- | --- |",
    ]
    # 生年 2028 戊申：虚岁 2 = 2029（公历 2029 = 己酉年，公开历法事实），逐年 +1。
    assert body[3] == "| 2~11 | 命 | 癸亥 | 2029-己酉、2030-庚戌、2031-辛亥、2032-壬子、2033-癸丑、2034-甲寅、2035-乙卯、2036-丙辰、2037-丁巳、2038-戊午 |"
    assert len([line for line in body if line.startswith("| ") and "~" in line]) == 12
    assert body[-1] == "要某一年/某月的完整流曜与四化落宫,请在「挂载设置 → 运限」里选定年月(或直接说出年份)。"
    assert "[运限]" not in out["text"] and "[流派叠层]" not in out["text"]
    assert out.get("errors") == []


@requires_node
def test_ziwei_zhongxian_school_reaches_period_daxian_segment(tmp_path) -> None:
    """[Q-432/T-395④]（ZiWeiMain.js:293-304）沈氏三限：schools.zhongxian 开时 [运限] 大限段列四段中限。
    旧 runZiweiExtras 只在 [流派叠层] 求值期间覆盖 ZWEngineOptions → 对 [运限] 永远不生效 → 红。"""
    out = _real_js(tmp_path).run(
        "ziwei_extras", {"chart": _ZW_CHART, "period": {"daxian": [1]}, "schools": {"zhongxian": True}}
    )
    period = _section(out["text"], "运限")
    # ziweiCore.zhongxianOf：自大限起岁每 2.5 年一段、共四段。
    assert "沈氏三限（大限内四分，各 2.5 年；宫位沿本大限宫）：中限1 12~14.5岁、中限2 14.5~17岁、中限3 17~19.5岁、中限4 19.5~22岁" in period
    # 可变单例必须还原：下一次不带 schools 的调用不得残留沈氏行。
    plain = _real_js(tmp_path).run("ziwei_extras", {"chart": _ZW_CHART, "period": {"daxian": [1]}})
    assert "沈氏三限" not in plain["text"]


@requires_node
def test_ziwei_borrow_palace_overlay_no_longer_reference_error(tmp_path) -> None:
    """旧 ziweiExtras 调 allBorrowedStars 却没 import → ReferenceError 被吞，整个 [流派叠层]（连同童限）静默消失。"""
    out = _real_js(tmp_path).run(
        "ziwei_extras", {"chart": _ZW_CHART, "schools": {"childLimit": True, "borrowPalace": True}}
    )
    overlay = _section(out["text"], "流派叠层")
    # 童限（ziweiCore.childLimits）：水二局只有 1 岁一步，落命宫。
    assert overlay.splitlines()[:2] == ["· 童限", "  1岁·命宫"]
    assert out.get("errors") == []


def test_ziwei_unknown_gender_label_says_male_layout() -> None:
    """[Q-193/T-139]（ZiWeiMain.js:419-420）：未知性别按男排，快照要说出来（旧版写「—」）。"""
    text = svc._build_ziwei_snapshot_text({"date": "2028-04-06", "time": "09:33:00", "gender": None}, {"chart": {"houses": []}})
    assert "性别：未知（按男排）" in _section(text, "起盘信息")


class _ZiweiClient(FakeClient):
    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/ziwei/birth":
            return {"chart": json.loads(json.dumps(_ZW_CHART))}
        return super().call(endpoint, payload)


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


@requires_node
def test_ziwei_birth_export_carries_overview_without_period(tmp_path) -> None:
    settings = _settings(tmp_path)
    service = HorosaSkillService(
        settings, client=_ZiweiClient(), store=MemoryStore(settings),
        js_client=_HybridJs(_real_js(tmp_path), {"ziwei_extras"}),
    )
    env = service.run_tool(
        "ziwei_birth",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": True,
         "agent_confirmed_settings": True},
        save_result=False,
    )
    assert env.ok, env.error
    export = env.data["export_snapshot"]
    assert "运限概览" in export["section_titles_detected"]
    assert export["unknown_detected_sections"] == [] and export["missing_selected_sections"] == []
    # 段序同上游：命中格局 → 运限概览。
    snap = env.data["snapshot_text"]
    assert snap.index("[命中格局]") < snap.index("[运限概览]")


# ────────────────────────────── 大六壬 ──────────────────────────────

_LR_FIXTURE = CORE_JS / "test" / "fixtures" / "chart_liureng.json"


@requires_node
def test_liureng_sanchuan_relation_lines_value_golden(tmp_path) -> None:
    """[Q-450/T-413]（LiuRengMain.js:4436-4447）[三传] 追加三传递生递克 + 逐传徽记。旧 [三传] 只有三行 → 红。

    夹具 2026-04-04 21:18：戊申日，旬首甲辰（旬空寅卯），三传 卯→寅→丑（元首课）。
    权威：卯寅同属木 = 比和；寅木克丑土 = 克；卯/寅落旬空；申子辰驿马在寅；戊禄在巳（三传无巳 → 无禄徽）。
    """
    fixture = json.loads(_LR_FIXTURE.read_text(encoding="utf-8"))
    out = _real_js(tmp_path).run("liureng", fixture)
    lines = _section(out["snapshot_text"], "三传").splitlines()
    assert lines[0] == "课式：元首课"
    # sanshi chunk：tools/liureng.js 改走 vendored 上游 buildLiuRengSnapshotText，[三传] 三行变上游 GFM 表
    # （表头两行 + 三行）——两行关系行仍紧随其后收尾，故按段尾断言（原 lines[4:] 钉的是旧手写行式）。
    assert lines[-2:] == ["三传递生递克：初传→中传 比和；中传→末传 克", "逐传徽记：初传卯(空)；中传寅(空·马)"]


@requires_node
def test_vendored_liureng_main_snapshot_chain_runs_end_to_end() -> None:
    """vendored 上游 buildLiuRengSnapshotText 真数据整链：此前三个 import 被 stub 成空 ——
    ChuangChart（三传核，buildSanChuanData 恒 null）、LRSanChuanRelationMini（[三传] 递生递克行
    ReferenceError）、LRXiangDoc（[取象] ReferenceError）。旧 vendored 文件跑到 [三传] 即抛 → 红。"""
    fixture = str(_LR_FIXTURE)
    res = _node(
        f"""
import {{ readFileSync }} from 'node:fs';
import {{ buildLiuRengSnapshotText }} from './src/vendor/liureng/LiuRengMain.js';
import {{ normalizeChart }} from './src/tools/liureng.js';
const f = JSON.parse(readFileSync({json.dumps(fixture)}, 'utf8'));
const txt = buildLiuRengSnapshotText({{ date: '2026-04-04', time: '21:18', zone: '+08:00', lon: '119e19', lat: '26n05' }},
  f.liureng, f.runyear, normalizeChart(f), 2, '', 1, {{}});
console.log(JSON.stringify({{ txt }}));
"""
    )
    sanchuan = _section(res["txt"], "三传")
    assert sanchuan.startswith("课式：元首课")
    assert "三传递生递克：初传→中传 比和；中传→末传 克" in sanchuan
    assert "逐传徽记：初传卯(空)；中传寅(空·马)" in sanchuan
    assert "[取象]" in res["txt"]


@requires_node
def test_liurengzeri_scan_pans_are_no_longer_all_null() -> None:
    """liurengZeriScanEngine 走 vendored LiuRengMain.buildSanChuanData：ChuangChart 被 stub 时它恒 null →
    computeLiurengScanPan 每个时辰都返回 null → 六壬择时（及三式择时六壬腿）对**任何**条件都零命中，且是形状合法的
    空结果。旧代码：pan=null、hit_count=0 → 红。命中逐个用同一引擎独立复算，课式必须真是元首课。"""
    res = _node(
        """
import { runZeriScan } from './src/tools/zeriScan.js';
import { computeLiurengScanPan } from './src/vendor/divination/zeri/liurengZeriScanEngine.js';
const geo = { zone: 8, lon: '121e28', lat: '31n14' };
const pan = computeLiurengScanPan(geo, { timeAlg: 1 }, '2026-03-01', '12:00');
const leaf = (type) => ({ kind: 'group', joiner: 'all', negate: false, children: [{ kind: 'leaf', negate: false, joiner: 'all', type, params: { values: ['元首课'] } }] });
const cfg = { startDate: '2026-03-01', startTime: '00:00', endDate: '2026-03-08', endTime: '23:59' };
const lr = await runZeriScan({ technique: 'liurengzeri', action: 'scan', cfg, geo, options: { timeAlg: 1 }, tree: leaf('ke_name') });
const ss = await runZeriScan({ technique: 'sanshizeri', action: 'scan', cfg, geo, options: { timeAlg: 1 }, tree: leaf('lr_ke_name') });
const picks = (lr.data.intervals || []).map((iv) => { const [d, t] = String(iv.pick).split(' '); const p = computeLiurengScanPan(geo, { timeAlg: 1 }, d, t); return p && p.sanChuan ? p.sanChuan.name : null; });
console.log(JSON.stringify({ pan: pan ? { name: pan.sanChuan.name, cuang: pan.sanChuan.cuang } : null, lr: lr.data.hit_count, ss: ss.data.hit_count, picks }));
"""
    )
    assert res["pan"] is not None and len(res["pan"]["cuang"]) == 3
    assert res["lr"] > 0 and res["ss"] > 0
    assert res["picks"] and all(name == "元首课" for name in res["picks"])


# ────────────────────────────── 三式合一 ──────────────────────────────

@requires_node
def test_sanshiunited_picks_liureng_qizheng_section() -> None:
    """[Q-451/T-414]（sanshiSnapshotSections.js:44-45）三式合一挑段单补「七政」。旧挑段单漏它 → 红。
    v3.11.x wave-3 起三式快照由 vendored 上游 buildSanShiUnitedSnapshotText 产出、挑段单即 vendored
    sanshiSnapshotSections.js（不再经 liureng 子工具桩注入），故直接断言单源段单；真盘产段由
    tests/test_sync311_sanshiunited.py 的 live 回放金标（含【七政】）守。"""
    res = _node(
        """
import { SANSHI_LIURENG_DUANGUA_SECTIONS } from './src/vendor/sanshi/sanshiSnapshotSections.js';
console.log(JSON.stringify({ picks: SANSHI_LIURENG_DUANGUA_SECTIONS }));
"""
    )
    assert res["picks"][-1] == "七政" and res["picks"].index("占断向导") == len(res["picks"]) - 2


# ────────────────────────────── 七政四余 ──────────────────────────────

@requires_node
def test_guolao_info_facts_port_of_upstream_jest_fixture() -> None:
    """vendored bespoke 抽出件对上游 __tests__/guolaoInfoFactsSnapshot.test.js 夹具逐条复验（期望值即上游 jest 断言）。
    旧代码：guolaoInfoFacts.js / guolaoSnapshotSections.js 不存在 → import 失败 → 红。"""
    res = _node(
        """
import * as AstroConst from './src/constants/AstroConst.js';
import { buildGuolaoMoiraInfoFacts } from './src/vendor/guolao/guolaoInfoFacts.js';
import * as S from './src/vendor/guolao/guolaoSnapshotSections.js';
import { buildGuolaoBirthStarsSection } from './src/tools/guolaoMoira.js';
const ROOT = { chart: { displayCoord: 'ecliptic', objects: [
  { id: AstroConst.LIFEMASTERDEG74, lon: 250.713, house: 'House1' }, { id: AstroConst.ASC, lon: 250.713 },
  { id: AstroConst.MOON, lon: 42.0, lonspeed: 13.1, house: 'House7' }, { id: AstroConst.SUN, lon: 75.5, lonspeed: 0.95 } ],
  fixedStarSu28: [{ name: '角', ra: 0 }, { name: '亢', ra: 30 }, { name: '氐', ra: 60 }, { name: '房', ra: 240 }, { name: '心', ra: 255 }],
  nongli: { bazi: { fourColumns: { year: { ganzi: '庚午' }, month: { ganzi: '己丑' }, day: { ganzi: '甲子' }, time: { ganzi: '庚午' } } } } } };
const TR = { nongli: { bazi: { fourColumns: { year: { ganzi: '丙午' }, month: { ganzi: '丁酉' } } } } };
const facts = (display, extra) => buildGuolaoMoiraInfoFacts({ value: {}, rootValue: ROOT, transitValue: TR,
  params: { date: '1990/01/15', time: '12:00:00' }, transitParams: { date: '2026/09/16', time: '12:00:00' }, display: display || {}, fields: {}, ...(extra || {}) });
const f = facts({});
const rules = { yearStars: { birth: { yearPole: '庚午', planetRows: [{ star: '日', changeTo: '禄', items: [] }] } } };
console.log(JSON.stringify({
  zi: f.life.zi, lifeHost: f.lifeSuHost.name, selfHost: f.selfSuHost.name, age: f.age, tyt: f.transitYearText,
  anchors: S.buildGuolaoAnchorLines(f),
  gong: S.buildGuolaoMastersSection(facts({ lifeMasterMode: 'gong' })), du: S.buildGuolaoMastersSection(facts({ lifeMasterMode: 'du' })),
  calc: S.buildGuolaoLimitCalcSection(f),
  noTransitLabels: facts({}, { transitValue: null }).limits.items.map((it) => it.label),
  minor: S.buildGuolaoLimitCalcSection(facts({ minorLimitType: 'minor' })), month: S.buildGuolaoLimitCalcSection(facts({ minorLimitType: 'month' })),
  tong: S.buildGuolaoLimitCalcSection(facts({ minorLimitType: 'tong', tongxianBase: 'gu9' })), dw: S.buildGuolaoLimitCalcSection(facts({ minorLimitType: 'dongwei' })),
  before: buildGuolaoBirthStarsSection(rules),
  withRows: buildGuolaoBirthStarsSection({ ...rules, natalYearStars: [{ name: '天禄', star: '木', shortName: '禄', quality: '吉', zi: '寅', signName: '人马' }] }),
}));
"""
    )
    assert (res["zi"], res["lifeHost"], res["selfHost"], res["age"], res["tyt"]) == ("寅", "房", "亢", 37, "丙午")
    assert res["anchors"][2] == "命度宿主：房 10度42分；身度宿主：亢 12度0分"
    assert "主宫主" in res["gong"] and "专度主" in res["du"] and res["gong"] != res["du"]
    assert res["gong"].splitlines()[1] == "命主(宫主)：木" and res["du"].splitlines()[1].startswith("命主(度主)：")
    assert "◆ 难仇恩用（主星五行四役）" in res["gong"]
    assert res["calc"].splitlines() == [
        "◆ 飞限 · 童限 · 小限 · 月限 · 限度（37 岁 · 丙午年）",
        "飞限：亥；小限：寅；月限：未；限度：25巳08；至：23巳08",
    ]
    assert "月限" not in res["noTransitLabels"]
    assert "◆ 行运法实算 · 小限" in res["minor"] and "生月12" in res["month"]
    assert "◆ 行运法实算 · 童限（基数古九岁）" in res["tong"] and "本年飞星吊度 ≈" in res["dw"]
    assert len({res["calc"], res["minor"], res["month"], res["tong"], res["dw"]}) == 5
    assert "命曜落宫" not in res["before"]
    assert "◆ 命曜落宫\n天禄：木（禄；吉 · 寅 · 人马）" in res["withRows"]


@requires_node
def test_guolao_limit_section_child_base_knob_changes_first_limit() -> None:
    """[大限] 由 vendored buildGuolaoLimitSection 出（GFM 表）：首限年数 = 定童限基数 + 命度宫内度/3（不四舍），
    birthYear 取 params.date（YYYY/MM/DD）。改 limitChildBase 9→10，首限必须 +1 年。"""
    res = _node(
        """
import { buildGuolaoLimitSection } from './src/vendor/guolao/guolaoSnapshotSections.js';
const chart = { displayCoord: 'equatorial', objects: [{ id: 'Asc', ra: 27.8, lon: 27.8 }, { id: 'Sun', ra: 295, lon: 295 }],
  date: { jd: 2447907.1666666665, utcoffset: { value: 8 } } };
const p = { date: '1990/01/15', time: '12:00:00' };
console.log(JSON.stringify({ nine: buildGuolaoLimitSection(chart, {}, p, '', 'tong10', { limitChildBase: 9 }),
  ten: buildGuolaoLimitSection(chart, {}, p, '', 'tong10', { limitChildBase: 10 }),
  dongwei: buildGuolaoLimitSection(chart, {}, p, 'dongwei', 'tong10', {}) }));
"""
    )
    nine, ten = res["nine"].splitlines(), res["ten"].splitlines()
    assert nine[:3] == ["古度限度法（命度十二宫大限）：", "| 限 | 宫 | 起讫岁 | 起讫年 | 年数 |", "| --- | --- | --- | --- | --- |"]
    # 命度 27.8°（宫内 27.8°）：9 + 27.8/3 = 18.27 年 / 10 + 27.8/3 = 19.27 年。
    assert nine[3].startswith("| 第1限 | 命宫 | 1-") and nine[3].endswith("| 约18.3年 |")
    assert ten[3].endswith("| 约19.3年 |")
    assert "1990-" in nine[3]
    assert "洞微大限（命宫顺行·飞星吊度·起限" in res["dongwei"]


def test_guolao_python_fallback_limit_years_use_dash_dates() -> None:
    """[大限] Python 兜底：skill 归一后日期是 YYYY-MM-DD，旧版只按 '/' 切 → 出生年恒 0 →「（0-12年）」。"""
    chart = {"objects": [{"id": "Asc", "ra": 27.8, "lon": 27.8}]}
    first = svc._build_guolao_limit_lines(chart, {"date": "1990-01-15"})[0]
    assert first.startswith("第1限 命宫：1-") and "（1990-" in first


class _GuolaoClient(CaptureClient):
    """/qizheng/moira 桩补上 Java 真形状的 anchors（live 实测 2028-04-06 09:33 上海，占星上升）+ natalYearStars。"""

    def call(self, endpoint: str, payload: dict) -> dict:
        out = super().call(endpoint, payload)
        if endpoint == "/nongli/time":
            # Java OnlyFourColumns.getNongli() 真形状（live 实测 1990-01-15 12:00 上海：己巳 丁丑 庚辰 壬午，
            # 1-15 在立春前 → 年柱仍是己巳）：四柱在 bazi.{year,month,day,time}.{stem,branch}.cell。
            pole = lambda gz: {"stem": {"cell": gz[0]}, "branch": {"cell": gz[1]}}  # noqa: E731
            out = {**out, "year": "己巳", "yearJieqi": "己巳", "monthGanZi": "丁丑", "dayGanZi": "庚辰",
                   "bazi": {"year": pole("己巳"), "month": pole("丁丑"), "day": pole("庚辰"), "time": pole("壬午")}}
        if endpoint == "/qizheng/moira":
            out = {
                **out,
                "anchors": {
                    "life": {"label": "命度", "sourceId": "Asc", "longitude": 71.1499, "degreeText": "11度8分", "sign": "Gemini",
                             "signName": "双子", "zi": "申", "area": "实沉", "moiraHouse": "命宫"},
                    "self": {"label": "身度", "sourceId": "Moon", "longitude": 151.1332, "degreeText": "1度7分", "sign": "Virgo",
                             "signName": "处女", "zi": "巳", "area": "鹑尾", "moiraHouse": "田宅"},
                    "lifeModeName": "占星上升",
                },
                "natalYearStars": [{"name": "命宫", "star": "金", "shortName": "权印", "quality": "强、正宫", "zi": "申",
                                    "sign": "Gemini", "signName": "双子", "area": "实沉", "mode": "birth"}],
            }
        return out


class _GuolaoJs(FakeJsClient):
    """guolao_moira 的 info_sections / rules_sections 走真 node 引擎（段体是真 builder 在桩盘上的输出），其余沿用带内容桩。"""

    def __init__(self, real: HorosaJsEngineClient) -> None:
        super().__init__()
        self._real = real
        self.info_payloads: list[dict] = []

    def run(self, tool_name: str, payload: dict[str, object]) -> dict:
        if tool_name == "guolao_moira" and payload.get("action") in {"info_sections", "rules_sections"}:
            if payload.get("action") == "info_sections":
                self.info_payloads.append(payload)
            return self._real.run(tool_name, payload)
        return super().run(tool_name, payload)


@requires_node
def test_guolao_chart_emits_new_sections_in_upstream_order(tmp_path) -> None:
    """[Q-435]（GuoLaoChartMain.js:2092-2104）：[大限] → [三主与化曜] → [限法实算] → [虚实]；
    [起盘信息] 带时间基准 + 七政两套时标补注（:2046）与命度/身度/宿主行（:2073-2076）。旧版四样都没有 → 红。"""
    settings = _settings(tmp_path)
    client = _GuolaoClient()
    js = _GuolaoJs(_real_js(tmp_path))
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=js)
    env = service.run_tool(
        "guolao_chart",
        {"date": "1990-01-15", "time": "12:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
         "moiraTransitDate": "2026-09-16", "guolaoMinorLimitType": "minor", "agent_confirmed_settings": True},
        save_result=False,
    )
    assert env.ok, env.error
    snap = env.data["snapshot_text"]
    info = _section(snap, "起盘信息").splitlines()
    assert info[3] == (
        "时间基准：钟表时(按输入钟面时刻,无真太阳时校正)；晚子时归次日：是；23 点换日：是；"
        "本页两套时标：盘面星体与宫位按上列基准；四柱由排盘服务按真太阳时(经度+均时差)另算；琴堂逢酉身宫的时支按钟面时刻取"
    )
    assert any(line.startswith("命度：") for line in info) and any(line.startswith("命度宿主：") for line in info)
    assert snap.index("[大限]") < snap.index("[三主与化曜]") < snap.index("[限法实算]") < snap.index("[虚实]") < snap.index("[政余格局]")
    # 命度取 Java anchors（申宫）：命度宿主随盘面（桩盘无 fixedStarSu28）；三主：申宫宫主 = 水（古法立成）。
    assert "命度：双子 11度8分（申 · 实沉 · 命宫 · 占星上升）" in info
    masters = _section(snap, "三主与化曜").splitlines()
    assert masters[0] == "◆ 三主 · 命宫配干 · 化曜（主宫主）" and "命宫宫主：水" in masters
    # 本命四柱来自 /nongli/time（年柱己巳 → 甲己之年丙作首：寅=丙寅 → 申宫配干壬申；A 诀己 → 太阴）。
    # 若没挂上本命四柱，事实层回退公历 1990 = 庚午 → 申宫配干甲申、化曜按庚 —— 与立春前生人的真年柱不符。
    assert "命宫配干(五虎遁)：壬申" in masters and "生年化曜(A诀)：太阴" in masters
    calc = _section(snap, "限法实算")
    assert "（37 岁 · 丙午年）" in calc and "◆ 行运法实算 · 小限（生年支加命宫逆数）" in calc
    # [本命化曜] 追加命曜落宫（rules.natalYearStars）。
    assert "◆ 命曜落宫\n命宫：金（权印；强、正宫 · 申 · 双子）" in _section(snap, "本命化曜")
    assert _section(snap, "大限").startswith("古度限度法（命度十二宫大限）：")
    # 本命四柱取 Java OnlyFourColumns（/nongli/time，timeAlg=0 真太阳时），挂到 chart.nongli 再交事实层。
    nongli_calls = [p for endpoint, p in client.calls if endpoint == "/nongli/time"]
    assert nongli_calls and nongli_calls[-1]["timeAlg"] == 0
    sent = js.info_payloads[-1]
    assert sent["params"]["date"] == "1990/01/15" and sent["transitParams"]["date"] == "2026/09/16"
    assert sent["display"] == {"limitYearBoundary": "gregorian", "lifeMasterMode": "gong", "minorLimitType": "minor",
                               "tongxianBase": "tong10", "limitChildBase": 9}
    assert sent["chart"]["chart"]["nongli"]["bazi"]["year"]["stem"]["cell"] == "己"
    export = env.data["export_snapshot"]
    assert {"三主与化曜", "限法实算"} <= set(export["section_titles_detected"])
    assert export["unknown_detected_sections"] == []


def test_guolao_invalid_display_setting_fails_loudly(tmp_path) -> None:
    settings = _settings(tmp_path)
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    env = service.run_tool(
        "guolao_chart",
        {"date": "1990-01-15", "time": "12:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
         "guolaoMinorLimitType": "xiaoxian", "agent_confirmed_settings": True},
        save_result=False,
    )
    assert env.ok is False and env.error.code == "tool.guolao_invalid_display_setting"
    with pytest.raises(ToolValidationError):
        service._guolao_display_settings({"guolaoLimitChildBase": 11})
    assert service._guolao_display_settings({"guolaoLimitChildBase": "10"})["limitChildBase"] == 10


# ────────────────────────────── 印度律盘 ──────────────────────────────

def test_normalize_india_extra_vargas_mirrors_upstream() -> None:
    # 权威：上游 AstroConst.normalizeIndiaExtraVargas（值域 INDIA_MOUNT_VARGA_OPTIONS / 去重 / 上限 4 / <=1 丢）。
    assert svc._normalize_india_extra_vargas([9, 7, 9, 5]) == ([9, 7], [9, 5])
    assert svc._normalize_india_extra_vargas("9,7，10 60") == ([9, 7, 10, 60], [])
    assert svc._normalize_india_extra_vargas([2, 3, 4, 7, 9]) == ([2, 3, 4, 7], [9])
    assert svc._normalize_india_extra_vargas([1, 0, "x"]) == ([], [1, 0, "x"])


def test_india_remote_payload_translates_tripataki_opt_in() -> None:
    on = svc._india_chart_remote_payload({"date": "2028-04-06", "indiaTripataki": True, "indiaExtraVargas": [9]})
    assert on["tripataki"] == 1 and "indiaTripataki" not in on and "indiaExtraVargas" not in on
    off = svc._india_chart_remote_payload({"date": "2028-04-06", "indiaTripataki": False})
    assert "tripataki" not in off


def test_india_extra_vargas_section_fetches_each_varga(tmp_path) -> None:
    """[附加分盘]（IndiaChart.js:1265-1333）：逐张另取 /india/chart?chartnum=N，只挑 宫位宫头/星与虚点/行星 三段，
    段内小标题 `── D9 婚姻 ──`，接在整份快照末尾。旧版没有该入参/该段 → 红。"""
    settings = _settings(tmp_path)
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())
    env = service.run_tool(
        "india_chart",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28",
         "indiaExtraVargas": [9, 1, 42], "agent_confirmed_settings": True},
        save_result=False,
    )
    assert env.ok, env.error
    india_calls = [p for endpoint, p in client.calls if endpoint in {"/india/chart"}]
    assert [p.get("chartnum") for p in india_calls] == [None, 9]
    assert all("indiaExtraVargas" not in p for p in india_calls)
    extra = _section(env.data["snapshot_text"], "附加分盘").splitlines()
    assert extra[0] == "以下为主盘之外另挂的分盘,只列该分盘的宫头与星曜落宫(大运/瑜伽/相位等仍以主盘段为准)。"
    assert extra[1] == "── D9 婚姻 ──" and len(extra) > 2 and "" not in extra
    assert env.data["snapshot_text"].rstrip().endswith(extra[-1])
    assert any("[1, 42]" in w for w in env.warnings), env.warnings
    export = env.data["export_snapshot"]
    assert "附加分盘" in export["section_titles_detected"] and export["unknown_detected_sections"] == []


@requires_node
def test_jyotish_tripataki_monthly_net_section_renders() -> None:
    """[Q-127/T-35] 三旗盘逐月净分。上游 builder 两处 bug（本仓声明式偏离）：scS 先用后定义（暂时性死区 → 整个
    buildJyotishSnapshotLines 抛出）、月序读 m.index（后端 month_rows 键是 month）。旧 vendored 文件 → 抛错 → 红。"""
    res = _node(
        """
import { buildJyotishSnapshotLines } from './src/vendor/india/jyotishSnapshot.js';
const months = (nets) => nets.map((net, i) => ({ month: i + 1, label: `m${i + 1}`, rows: [], score: { net } }));
const out = buildJyotishSnapshotLines({ jyotish: { tripataki: { available: true, byCenter: {
  moon: { available: true, centerSign: 'Scorpio', months: months([-6, -5, 1]) },
  saturn: { available: false, reason: 'missing_center_sign' } } } } });
console.log(JSON.stringify(out['Tripataki 三旗盘逐月净分'] || null));
"""
    )
    assert res == [
        "| 中心 | 座 | 逐月净分(月序:有效吉−凶) |",
        "| --- | --- | --- |",
        "| 月心 | 天蝎 | 1:-6 2:-5 3:1 |",
    ]


# ────────────────────────────── 导出契约登记 ──────────────────────────────

def test_registry_registers_new_sections_with_conditional_double_registration() -> None:
    preset = AI_EXPORT_PRESET_SECTIONS
    optional = AI_EXPORT_OPTIONAL_SECTIONS
    # 段位同上游 aiExport.js（v3.11.1+ HEAD）。
    assert preset["ziwei"][preset["ziwei"].index("命中格局") + 1] == "运限概览"
    assert preset["sanshiunited"][preset["sanshiunited"].index("六壬概览") + 1] == "七政"
    assert preset["guolao"][preset["guolao"].index("大限") + 1: preset["guolao"].index("大限") + 3] == ["三主与化曜", "限法实算"]
    assert preset["indiachart"][preset["indiachart"].index("大运Dasha") + 1] == "附加分盘"
    assert preset["indiachart"][preset["indiachart"].index("Tripataki 宿距三旗") + 1] == "Tripataki 三旗盘逐月净分"
    for key, titles in {
        "ziwei": ["运限概览"], "guolao": ["三主与化曜", "限法实算"],
        "indiachart": ["附加分盘", "Tripataki 三旗盘逐月净分"],
    }.items():
        assert set(titles) <= set(optional[key]), key
    # 择日派生键：段表与 optional 都从基底继承（ZERI_DERIVED_KEYS）。
    assert {"三主与化曜", "限法实算"} <= set(preset["qizhengzeri"]) and {"三主与化曜", "限法实算"} <= set(optional["qizhengzeri"])
    assert "运限概览" in preset["ziweizeri"] and "运限概览" in optional["ziweizeri"]
    assert "七政" in preset["sanshizeri"]
