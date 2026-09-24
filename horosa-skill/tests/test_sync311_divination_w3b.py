"""上游 v3.11 同步 · wave 3b 占卜/数算收口：六爻整份快照改 vendored 上游 buildGuaSnapshotText / 数算三技法
（参评数·河洛·一掌经）timeAlg 缺省随上游无头挂载 = 0（真太阳时）与日界缺省 1 / 神数正传 23 点档农历日随无头取钟面日。

每条钉「与上游同一函数逐字节同」或「改这个参数/缺省，结果必须变」的值级事实（真引擎：vendored core-js 经 node 跑；
HTTP 层用记录型桩，桩值取自 live 9977 /nongli/time 实测 2026-09-24），并在旧代码上必红（负向对照记在各条 docstring 里，
「旧代码」= 基线提交 2aa2771）。权威 = 上游 Horosa-Public HEAD 9b74714b（file:line 注在断言旁）；上游源锚（绊线）只在
HOROSA_SOURCE_ROOT 指向上游 checkout 时跑。
"""
from __future__ import annotations

import json

import pytest
from test_sync311_divination_w3 import (
    CORE_JS_SRC,
    DOCTRINE_CACHE,
    GUAZHAN,
    NONGLI,
    SH,
    SIX,
    UPSTREAM_UI,
    RecordingClient,
    _node,
    _ok,
    _run,
    _sections,
    _service,
    requires_upstream,
)

# ── 1. 六爻：整份快照 = 上游无头路径 buildGuaSnapshotText(buildCaseSnapshotFields(record), st) ─────────────

# 参照侧：直接跑 vendored 上游 buildGuaSnapshotText（revendor 流水线对上游逐字可复现；函数体逐字对拍见
# test_vendored_buildGuaSnapshotText_is_upstream_source），入参按上游无头路径独立装配 —— 与 skill 的装配代码无关：
#   fields = buildCaseSnapshotFields(record)（aiAnalysisContext.js:780-797：date/time 为同一 DateTime 的两种格式化、
#            zone 缺省 '+08:00'、lon/lat 缺省 ''、gender = record.gender ?? 1）；
#   st     = buildTimeGua(nongli)（regenerateSixyaoSnapshot:1748）或页面手动成卦 state（getCurrentGua + setupYao，
#            GuaZhanMain.js:1106-1138：爻名取该卦 yaoname）；给了齿轮才叠 liuyaoSettings（:1753-1755）；
#   先 await 断语库（ensureLiuyaoDoctrineLoaded :1735-1737）。
_UPSTREAM_WHOLE = """
const [gz, dc, gs, le] = await Promise.all([import(process.argv[1]), import(process.argv[2]), import(process.argv[3]), import(process.argv[4])]);
const nongli = JSON.parse(process.argv[5]);
const rec = JSON.parse(process.argv[6]);
const gear = JSON.parse(process.argv[7]);
const manual = JSON.parse(process.argv[8]);
await dc.loadDoctrine();
let gua;
if (manual.length) {
  const g = gs.getGua64(le.littleEndian(manual.map((y) => y.value)));
  gua = { yao: manual.map((y, i) => ({ value: y.value, change: !!y.change, name: gs.Gua64[g.index].yaoname[i] })), currentGua: g.index, nongli };
} else {
  gua = gz.buildTimeGua(nongli);
}
const st = Object.keys(gear).length ? { ...gua, liuyaoSettings: gear } : gua;
const dt = { format: (p) => (p === 'YYYY-MM-DD' ? rec.date : rec.time) };
const fields = { date: { value: dt }, time: { value: dt }, zone: { value: rec.zone || '+08:00' },
  lon: { value: rec.lon || '' }, lat: { value: rec.lat || '' },
  gender: { value: rec.gender !== undefined && rec.gender !== null ? rec.gender : 1 } };
process.stdout.write(gz.buildGuaSnapshotText(fields, st));
"""


def _upstream_whole(date: str, payload: dict, gear: dict | None = None, manual: list[dict] | None = None) -> str:
    rec = {key: payload.get(key) for key in ("date", "time", "zone", "lon", "lat", "gender")}
    return _node(
        _UPSTREAM_WHOLE, str(GUAZHAN), str(DOCTRINE_CACHE), str(CORE_JS_SRC / "vendor" / "gua" / "GuaConst.js"),
        str(CORE_JS_SRC / "vendor" / "gua" / "littleEndian.js"), json.dumps(NONGLI[(date, 0)], ensure_ascii=False),
        json.dumps(rec, ensure_ascii=False), json.dumps(gear or {}, ensure_ascii=False),
        json.dumps(manual or [], ensure_ascii=False),
    )


def _tianji_gear() -> dict:
    # 上游 mergeLiuyaoGearSettings({}, {school}) = applyPreset(school, {})（aiAnalysisContext.js:1684-1731）。
    return json.loads(_node(
        "import(process.argv[1]).then((m) => process.stdout.write(JSON.stringify(m.applyPreset('tianji', {}))));",
        str(CORE_JS_SRC / "vendor" / "gua" / "liuyaoSchools.js")))


@pytest.mark.parametrize("date,time,settings", [
    ("2026-09-24", "10:58:00", {}),
    ("2026-10-20", "10:00:00", {"school": "tianji"}),  # 断易天机派：判读层全开，整份逐字节仍须同
])
def test_sixyao_whole_snapshot_is_the_upstream_headless_builder(tmp_path, date: str, time: str, settings: dict) -> None:
    """整份六爻快照（八段）与上游无头路径逐字节相同：regenerateSixyaoSnapshot（aiAnalysisContext.js:1739-1760）=
    先载断语库 → buildTimeGua(nongli) → buildGuaSnapshotText(buildCaseSnapshotFields(record), st)。
    值级锚点（2026-09-24 10:58 上海，live 9977 真太阳时 11:09:58 甲午时 → 风雷益 上爻动）：
      旬空 = 丁酉/辛丑同属甲午旬 → 辰巳（六十甲子旬手核）；起卦时间带「甲午时」后缀（GuaZhanMain.js:238）；
      互/错/综按爻值变换手核（益 100011 → 互 000001 山地剥、错 011100 雷风恒、综 110001 山泽损，guaFromYaoValues）；
      关联卦逐爻含伏神卦（本宫首卦，:318-328）；求测人性别缺省男（buildCaseSnapshotFields gender ?? 1，:791）。
    负向对照：旧 runner 的 [起盘信息]/[卦象]/[六爻与动爻]/[卦辞与断语] 是 Python 自写段 —— 无旬空行、无「X时」后缀、
    [卦象] 只有本卦/之卦名、无关联卦逐爻、[卦辞与断语] 带「问题：」与自拟卦辞行、无 [判语库·参考诀表] → 整份不等且锚点全红。"""
    service = _service(tmp_path)
    payload = {**SIX, "date": date, "time": time}
    if settings:
        payload["liuyaoSettings"] = settings
    env = _ok(service, "sixyao", payload)
    ours = env.data["snapshot_text"]
    upstream = _upstream_whole(date, payload, gear=_tianji_gear() if settings else None)
    assert ours == upstream
    assert env.data["export_snapshot"]["missing_selected_sections"] == []
    assert env.data["export_snapshot"]["unknown_detected_sections"] == []
    sec = _sections(ours)
    # 段序 = builder 实际产段顺序（GuaZhanMain.js:222/263/286/335/339/369/384-387）。
    assert list(sec) == ["起盘信息", "卦象", "六爻与动爻", "断卦结构", "卦辞与断语", "判语库·参考诀表", "断诀命中", "占类断语"]
    if not settings:
        assert sec["起盘信息"] == [
            "日期：2026-09-24 10:58:00", "时区：+08:00", "经纬度：121e28 31n13", "求测人性别：男",
            "起卦时间：2026-09-24 11:09:58 甲午时", "干支：年丙午 月丁酉 日辛丑 时甲午", "旬空：月空辰巳 日空辰巳",
        ]
        assert sec["卦象"] == [
            "本卦：风雷益  巽宫木", "互卦：山地剥  乾宫金", "之卦(变卦)：水雷屯  坎宫水",
            "错卦(阴阳全变)：雷风恒  震宫木", "综卦(上下颠倒)：山泽损  艮宫土",
        ]
        rel = sec["六爻与动爻"]
        assert rel[5] == "第6爻：阳爻（动），爻名:卯木兄弟应"
        heads = [line for line in rel if line.endswith("逐爻（初→上）：")]
        assert heads == ["之卦(变卦)逐爻（初→上）：", "互卦逐爻（初→上）：", "伏神卦(本宫首卦)逐爻（初→上）：",
                         "综卦逐爻（初→上）：", "错卦逐爻（初→上）："]
        fu = rel.index("伏神卦(本宫首卦)逐爻（初→上）：")
        assert rel[fu + 1] == "第1爻：阴爻，爻名:丑土妻财"  # 巽为风（巽宫首卦）初爻
        # 无头卦无 guaDesc：[卦辞与断语] 只有段头，紧接 [判语库·参考诀表]（GuaZhanMain.js:338-369）。
        assert "[卦辞与断语]\n[判语库·参考诀表]\n◆ 诸爻持世诀" in ours


def test_sixyao_manual_lines_are_the_page_cast_state(tmp_path) -> None:
    """手动摇卦 = 页面一次性成卦 state（getCurrentGua + setupYao，GuaZhanMain.js:1106-1138：爻名取该卦 yaoname）→
    整份快照与上游 builder 逐字节同。乾为天初爻动：[六爻与动爻] 初爻「阳爻（动），爻名:子水子孙」（Gua64 乾为天 yaoname[0]），
    之卦天风姤。负向对照：旧 runner 手动爻不补爻名 → 「第1爻：阳爻（动）」无爻名，且 [卦象] 只有「本卦：乾为天」。"""
    service = _service(tmp_path)
    manual = [{"value": 1, "change": i == 0} for i in range(6)]
    payload = {**SIX, "lines": manual}
    env = _ok(service, "sixyao", payload)
    ours = env.data["snapshot_text"]
    assert ours == _upstream_whole("2026-09-24", payload, manual=manual)
    sec = _sections(ours)
    assert sec["六爻与动爻"][0] == "第1爻：阳爻（动），爻名:子水子孙"
    assert sec["卦象"][:3] == ["本卦：乾为天  乾宫金", "互卦：乾为天  乾宫金", "之卦(变卦)：天风姤  乾宫金"]
    assert [line["name"] for line in env.data["lines"]][:2] == ["子水子孙", "寅木妻财"]


def test_sixyao_querent_gender_line_follows_the_record(tmp_path) -> None:
    """[起盘信息]「求测人性别」行（GuaZhanMain.js:232-236，只认 0/1）：缺省 = buildCaseSnapshotFields 的 gender ?? 1
    → 男（:791；起课时间源 timepointDraft.gender 亦 1，AIAnalysisMain.js:996）；gender=0 或「女」→ 女；
    认不出的值结构化报错（上游对非 0/1 整行静默不出，skill 不吞）。负向对照：旧 runner 无此行、gender 死键。"""
    service = _service(tmp_path)
    info = lambda env: _sections(env.data["snapshot_text"])["起盘信息"]  # noqa: E731
    assert "求测人性别：男" in info(_ok(service, "sixyao", SIX))
    assert "求测人性别：女" in info(_ok(service, "sixyao", {**SIX, "gender": 0}))
    assert "求测人性别：女" in info(_ok(service, "sixyao", {**SIX, "gender": "女"}))
    bad = _run(service, "sixyao", {**SIX, "gender": 2})
    assert bad.ok is False and bad.error.code == "tool.sixyao_invalid_gender"


def test_sixyao_drops_skill_only_lines_but_keeps_descriptions(tmp_path) -> None:
    """skill 自写行一律退场：上游 [卦辞与断语] 无「问题：」行、无头卦也无卦辞行（builder 只按 st.guaDesc 出，
    GuaZhanMain.js:338-363）。问题原文仍在 data.question；/gua/desc 卦辞仍在 data.descriptions（结构化面）。
    负向对照：旧 runner 的 [卦辞与断语] = 「问题：求财 / 本卦：卦100011 / 卦辞：亨。/ 之卦：… / 之卦卦辞：亨。」。"""
    env = _ok(_service(tmp_path), "sixyao", SIX)
    text = env.data["snapshot_text"]
    assert "问题：" not in text and "卦辞：" not in text and "之卦卦辞" not in text
    assert _sections(text)["卦辞与断语"] == [""]
    assert env.data["question"] == "求财"
    assert set(env.data["descriptions"]) == {"100011", "100010"}


def test_sixyao_incomplete_lines_fail_loudly(tmp_path) -> None:
    """lines 不足六爻起不出卦：结构化 tool.sixyao_invalid_lines（上游页面卦不全即不成卦）。
    负向对照：旧 runner 照样按五爻拼出一份自写快照（ok=True，卦码 5 位）。"""
    five = [{"value": 1, "change": False}] * 5
    env = _run(_service(tmp_path), "sixyao", {**SIX, "lines": five})
    assert env.ok is False and env.error.code == "tool.sixyao_invalid_lines"


@requires_upstream
def test_vendored_buildGuaSnapshotText_is_upstream_source() -> None:
    """绊线：vendored buildGuaSnapshotText / guaText / guaFromYaoValues 与上游函数体逐字；上游无头路径仍是
    buildCaseSnapshotFields → buildTimeGua → buildGuaSnapshotText(fields, st)，buildTimeGua 仍只回 {yao,currentGua,nongli}
    （无 guaDesc/god → [卦辞与断语] 只有段头、逐爻无六神）、buildCaseSnapshotFields 的 gender 缺省仍为 1。任一处上游改了就红
    —— 提示重审 skill 的装配。"""
    upstream = (UPSTREAM_UI / "components" / "guazhan" / "GuaZhanMain.js").read_text(encoding="utf-8")
    vendored = GUAZHAN.read_text(encoding="utf-8")
    for head in ("export function buildGuaSnapshotText(fields, st){", "function guaText(gua){", "function guaFromYaoValues(values){"):
        start = upstream.index(head)
        body = upstream[start: upstream.index("\n}\n", start) + 3]
        assert body in vendored, head
    assert "return { yao, currentGua: guaidx, nongli };" in upstream
    ctx = (UPSTREAM_UI / "utils" / "aiAnalysisContext.js").read_text(encoding="utf-8")
    regen = ctx[ctx.index("async function regenerateSixyaoSnapshot(record, gearFlat){"):]
    regen = regen[: regen.index("\n}\n")]
    for needle in ("const fields = buildCaseSnapshotFields(record);", "const gua = buildTimeGua(nongli);",
                   "return buildGuaSnapshotText(fields, st);"):
        assert needle in regen, needle
    fields = ctx[ctx.index("function buildCaseSnapshotFields(record){"):]
    fields = fields[: fields.index("\n}\n")]
    assert "gender: { value: record && record.gender !== undefined && record.gender !== null ? record.gender : 1 }," in fields


# ── 2. 数算：timeAlg 缺省 0（真太阳时）、日界缺省 1 —— 上游页面与无头挂载同值 ─────────────────────────


SHUSUAN = {"date": "1998-02-20", "time": "11:05:00", **SH, "gender": 1}


def _hour_branch(tool: str, data: dict) -> str:
    if tool == "canping":
        return data["input_normalized"]["fourPillars"]["hourBranch"]
    if tool == "heluo":
        return data["heluo"]["fourPillars"]["hour"][1]
    return data["yizhangjing"]["input"]["hourBranch"]


@pytest.mark.parametrize("tool", ["canping", "heluo", "yizhangjing"])
def test_shusuan_time_alg_defaults_to_true_solar_like_upstream(tmp_path, tool: str) -> None:
    """缺省 timeAlg = 0（真太阳时）：上游无头 buildChartBaziParams 取 buildFieldObject timeAlg = record.timeAlg ?? 0
    （aiAnalysisContext.js:603,1793；参评/河洛/一掌经三条 builder 共用，:2054/2149/2196）；页面 fieldVal(f,'timeAlg',1)
    读的全局字段恒在、出厂种子 0（models/astro.js:375-377 + newChartSeeds.js:43），挂载齿轮缺省亦 0
    （techniqueMountSettings.js:147）。1998-02-20 11:05 上海：真太阳时 10:55:19 → 巳时；钟表 → 午时（live 9977
    /nongli/time 实测：timeAlg 0 时柱丁巳、1 → 戊午）。负向对照：旧 schema 缺省 timeAlg=1 → 缺省即午时。"""
    service = _service(tmp_path)
    default = _ok(service, tool, SHUSUAN).data
    clock = _ok(service, tool, {**SHUSUAN, "timeAlg": 1}).data
    assert _hour_branch(tool, default) == "巳"
    assert _hour_branch(tool, clock) == "午"
    assert default["input_normalized"]["timeAlg"] == 0


@pytest.mark.parametrize("tool", ["canping", "heluo"])
def test_shusuan_day_boundary_defaults_to_23_new_day_like_upstream(tmp_path, tool: str) -> None:
    """缺省日界 = 全局出厂 1（23 点换日）：上游无头 buildFieldObject after23NewDay = record ?? defaultAfter23NewDay()
    （aiAnalysisContext.js:606）、页面 fieldVal(f,'after23NewDay',defaultAfter23NewDay())（CanPingMain.js:141 /
    HeLuoMain.js:191）。1998-02-20 23:30（钟表时）：日柱 己亥（23 点换日）/ 戊戌（24 点换日）—— live 9977 /nongli/time
    实测同值。负向对照：旧 tools/canping.js / heluo.js 不传 → vendored baziLunarLocal 把 undefined 当 24 点换日 → 戊戌。"""
    service = _service(tmp_path)
    late = {**SHUSUAN, "time": "23:30:00", "timeAlg": 1}

    def day(data: dict) -> str:
        if tool == "canping":
            return data["input_normalized"]["fourPillars"]["dayBranch"]  # 参评数只取日支
        return data["heluo"]["fourPillars"]["day"]

    expect = {"canping": ("亥", "戌"), "heluo": ("己亥", "戊戌")}[tool]
    default = _ok(service, tool, late).data
    assert day(default) == expect[0] and default["input_normalized"]["after23NewDay"] == 1
    assert day(_ok(service, tool, {**late, "after23NewDay": 0}).data) == expect[1]


@requires_upstream
def test_shusuan_time_alg_default_evidence_still_holds_upstream() -> None:
    """绊线：无头 timeAlg ?? 0 / 日界 ?? 出厂默认、buildChartBaziParams 原样取、全局种子 0、挂载齿轮缺省 0，
    三页面 getModel 读全局 fields（回退 1 不生效的前提）。任一处上游改了就红 —— 提示重审三技法缺省。"""
    ctx = (UPSTREAM_UI / "utils" / "aiAnalysisContext.js").read_text(encoding="utf-8")
    assert "timeAlg: { value: (record.timeAlg !== undefined && record.timeAlg !== null) ? record.timeAlg : 0 }," in ctx
    assert ("after23NewDay: { value: (record.after23NewDay !== undefined && record.after23NewDay !== null) "
            "? record.after23NewDay : defaultAfter23NewDay() },") in ctx
    params = ctx[ctx.index("function buildChartBaziParams(record){"):]
    params = params[: params.index("\n}\n")]
    assert "timeAlg: fields.timeAlg.value," in params and "after23NewDay: fields.after23NewDay.value," in params
    seeds = (UPSTREAM_UI / "utils" / "newChartSeeds.js").read_text(encoding="utf-8")
    assert "timeAlg: { def: 0," in seeds
    model = (UPSTREAM_UI / "models" / "astro.js").read_text(encoding="utf-8")
    assert "value: newChartSeedValue('timeAlg')," in model
    mount = (UPSTREAM_UI / "utils" / "techniqueMountSettings.js").read_text(encoding="utf-8")
    assert "{ name: 'timeAlg', label: '时间算法', type: 'select', options: TIME_ALG_OPTIONS, default: 0, group: '时间换算' }," in mount
    for page in ("shusuan/CanPingMain.js", "shusuan/HeLuoMain.js", "yizhangjing/YiZhangJingMain.js"):
        src = (UPSTREAM_UI / "components" / page).read_text(encoding="utf-8")
        assert "timeAlg: fieldVal(f, 'timeAlg', 1)," in src, page


# ── 3. 神数正传：23 点档农历月日随无头取钟面日（页面 lunarByDayBoundary 进位，无头不进位） ─────────────


class LateZiClient(RecordingClient):
    """1998-02-20 23:30 上海（真太阳时 23:20:23，after23NewDay 缺省 1 → 日柱进位己亥，但农历日 dayInt 仍是钟面廿四）。
    值 = live 9977 /nongli/time 实测 2026-09-24（timeAlg 0，after23NewDay 缺省/1 同值）。"""

    LATE = {"birth": "1998-02-20 23:20:23", "year": "戊寅", "yearJieqi": "戊寅", "monthGanZi": "甲寅",
            "dayGanZi": "己亥", "time": "甲子", "monthInt": 1, "dayInt": 24, "leap": False}

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/nongli/time" and payload.get("time") == "23:30:00":
            self.calls.append((endpoint, json.loads(json.dumps(payload, ensure_ascii=False))))
            return dict(self.LATE)
        return super().call(endpoint, payload)


def test_zhengchuan_late_zi_lunar_day_is_the_civil_day_like_the_headless_mount(tmp_path) -> None:
    """上游无头 buildChartShusuanBazi 取 bazi.nongli.monthNum/dayNum（aiAnalysisContext.js:1971-1972 = 钟面农历，
    vendored baziLunarLocal.buildNongli 注明进位值只在 ziwei* 键）；页面 ZhengChuanMain.getModel 另走 lunarByDayBoundary
    （:193-196，23 点档随日柱进位次日）。两路不一致 → 按无头：1998-02-20 23:30 = 正月廿四（不进位成廿五）。
    后端 /nongli/time 的 dayInt 本就是钟面日（live 实测 after23NewDay 0/1 同为 24），skill 直取 = 无头口径。
    改这个日必变：同盘按页面进位值（廿五）起数 → 农历行与本命数一并改变（204 → 205，公式②；下方 JS 直跑对照）。
    负向对照（变异）：runner 改按 lunarByDayBoundary 进位（lunarDay=25）→ 「农历 | 1月25日」「本命数 | 205」，本条即红。"""
    service = _service(tmp_path, LateZiClient())
    payload = {"date": "1998-02-20", "time": "23:30:00", **SH, "gender": 1, "school": "tieban"}
    text = _ok(service, "zhengchuan", payload).data["snapshot_text"]
    lines = text.split("\n")
    assert "| 农历 | 1月24日 |" in lines and "| 本命数 | 204 | 公式② |" in lines
    # 页面口径（进位 → 廿五）对照：同一 vendored 引擎、只改 lunarDay。
    script = """
const m = await import(process.argv[1]);
const r = await m.runZhengChuan({ school: 'tieban', pillars: ['戊寅', '甲寅', '己亥', '甲子'], gender: 1, lunarMonth: 1, lunarDay: Number(process.argv[2]), isLeapMonth: false });
process.stdout.write(r.snapshot_text || '');
"""
    page = _node(script, str(CORE_JS_SRC / "tools" / "zhengchuan.js"), "25").split("\n")
    assert "| 农历 | 1月25日 |" in page and "| 本命数 | 205 | 公式② |" in page
    assert _node(script, str(CORE_JS_SRC / "tools" / "zhengchuan.js"), "24") == text


@requires_upstream
def test_zhengchuan_headless_lunar_day_evidence_still_holds_upstream() -> None:
    """绊线：无头 buildChartShusuanBazi 仍读 monthNum/dayNum（钟面），页面仍走 lunarByDayBoundary。上游若让无头也进位，
    本条即红 —— 提示 skill 跟进（届时改取进位值）。"""
    ctx = (UPSTREAM_UI / "utils" / "aiAnalysisContext.js").read_text(encoding="utf-8")
    shu = ctx[ctx.index("function buildChartShusuanBazi(record){"):]
    shu = shu[: shu.index("\n}\n")]
    assert "lunarDay: Number((bazi.lunar || bazi.nongli || {}).dayNum || (bazi.lunar || bazi.nongli || {}).day) || 0," in shu
    assert "lunarByDayBoundary" not in shu
    page = (UPSTREAM_UI / "components" / "shusuan" / "ZhengChuanMain.js").read_text(encoding="utf-8")
    assert "const lb = lunarByDayBoundary(nl);" in page
