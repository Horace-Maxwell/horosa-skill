"""wave 3b · 西占 chart 家族导出正文与上游逐字节对齐（Horosa-Public @ 9b74714b，aiExport v57/v58）。

金标来源（全部由**上游代码**产出，不手写）：`tests/fixtures/sync311_chartexport_live.json`
- 两张 live /chart 盘（vendored v3.11.1+ 引擎 :8877；回归缺省盘 + 恒星黄道·Raman / hsys 8 / 一组非默认古典口径盘）与
  上游 `utils/astroAiSnapshot.js` buildAstroSnapshotContent 在**同一张盘**上（node 里跑 esbuild 打包的上游源）产出的全文；
- 节气 [春分宿盘]（上游 `components/jieqi/JieQiChartsMain.js` buildJieQiSuSection，三种起宫分支）；
- 合盘最小形状（上游 `components/astro/AstroRelative.js` buildRelativeSnapshotText，比较盘 + 关系量化页签）；
- 古典格局子块（上游 buildClassicalSection → buildPatternOverviewLines，[Q-558/T-520] 合相/映点联结）。
每条测试写明「旧代码为什么会红」（负向对照）。实测方式（wave 3b 报告）：① 整文件放到 2aa2771 树上 → 收集期 ImportError
（无 engine.astro_snapshot）；② 在新树的 scratch 拷贝上逐项突变回旧行为（宫制回显优先 / 去掉排盘规则·古典口径·命主星行 / 宫头·相位
回行式 / 寿命长名·无界 / 合盘回行式·[合成图盘] 恒出·条件段单登记 / 宿盘旧宫标 / 不补 strongRecption / shim 缺 PARS_SPIRIT /
埃及名标签恒定·并入 egyptianCalendar / 先验权力缺合相映点·子块不在 [古典] / 龙盘无交点类型，共 20 项），对应测试逐项变红。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from test_service import CaptureClient, FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.engine import astro_snapshot as snap
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.exports.registry import AI_EXPORT_OPTIONAL_SECTIONS, AI_EXPORT_PRESET_SECTIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import (
    HorosaSkillService,
    _build_astro_snapshot_text,
    _build_natal_extra_sections,
    _build_relative_snapshot_text,
    _chart_family_snapshot_fields,
)

CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
FIXTURE = json.loads((Path(__file__).resolve().parent / "fixtures" / "sync311_chartexport_live.json").read_text(encoding="utf-8"))
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _settings(tmp_path) -> Settings:
    return Settings(
        server_root="http://127.0.0.1:9999",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )


def _split(text: str) -> dict[str, str]:
    """`[X]` 整行段头切段（与 exports/parser 同口径），段体去首尾空白。"""
    out: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in f"{text}".split("\n"):
        if re.fullmatch(r"\[.+\]", line):
            current = out.setdefault(line[1:-1], [])
            continue
        if current is not None:
            current.append(line)
    return {title: "\n".join(lines).strip() for title, lines in out.items()}


def _service(tmp_path, client=None, js_client=None) -> HorosaSkillService:
    settings = _settings(tmp_path)
    return HorosaSkillService(settings, client=client or FakeClient(), store=MemoryStore(settings), js_client=js_client or FakeJsClient())


# ─────────────────────────── 整盘：与上游 buildAstroSnapshotContent 逐字节 ───────────────────────────
@requires_node
@pytest.mark.parametrize("case", ["tropical_default", "sidereal_classical_hsys8"])
def test_chart_snapshot_matches_upstream_builder_byte_for_byte(case: str, tmp_path) -> None:
    """同一张 live 盘：skill `_build_astro_snapshot_text` 的每一段 == 上游 buildAstroSnapshotContent 同名段（逐字节），段序同。

    覆盖 item 1-4：[起盘信息] 宫制/黄道「请求参数优先」（hsys 8 回显 Alcabitus 撞名，旧代码印 Alcabitus）/ 恒星黄道一行式
    「恒星黄道·Raman，…」（旧代码另起「恒星黄道岁差：」行）/ 排盘规则 / 古典口径（非默认项）/ 日主星·时主星·命主星；
    宫位宫头·星与虚点·相位·行星·希腊点·12分度 的 GFM 表（旧代码逐行文本）；[寿命格局] 单字名 + 带界的位置（旧代码「太阳」
    + 无界）；[古典] 的「古典格局」子块（旧代码塞在 [古典格局] 段、标「格局速览」且星座名用「牡羊/室女」）；[埃及历] 只吃本盘。
    12分度/主宰星链链行/寿命格局 与 [埃及历] 走真 JS（vendored natalExtras / egyptSection，与生产同一条 cli 路径）。
    """
    fx = FIXTURE[case]
    js = HorosaJsEngineClient(_settings(tmp_path))
    chart = fx["chart"]
    extras = js.run("astroextra", {"chart": chart, "options": {}})["data"]
    egypt = js.run("egypt_section", {"chart": chart, "fields": {}})["text"]
    response = {**chart, "_natalExtras": _build_natal_extra_sections(extras), "_egyptSection": egypt}
    skill = _split(_build_astro_snapshot_text(fx["fields"], response))
    upstream = _split(fx["upstream_text"])
    # 段集与段序：skill 仅多出 [月宿]（skill-extra，恒星黄道盘才有；上游把宿写进 [行星] 的「月宿」列）。
    assert [title for title in skill if title != "月宿"] == list(upstream)
    for title, body in upstream.items():
        assert skill[title] == body, title


def test_start_info_house_system_label_is_request_first() -> None:
    """[V6-W2]（astroAiSnapshot.js:457-467）：宫制标注 = derivedWholeSignLabelOf → HouseSys[fields.hsys] → chart.hsys 回显。
    夹具盘回显「Alcabitius」；旧实现回显优先 → hsys 8/9/14/24 统统标成回显值（8 撞名 Alcabitus、24 撞名整宫制）。"""
    chart = FIXTURE["tropical_default"]["chart"]
    assert chart["chart"]["hsys"] == "Alcabitus"   # perchart 盘级回显 = HouseSys['1'] 的同名串（8/24 的回显也撞这类名）
    for hsys, label in ((8, "天顶为10宫中点等宫制"), (9, "Porphyry"), (14, "Horizontal"), (24, "福点整宫制")):
        start = _split(_build_astro_snapshot_text({"hsys": hsys}, chart))["起盘信息"].splitlines()
        assert f"回归黄道，{label}" in start, (hsys, start)
    # 请求缺宫制键 → 回显兜底（上游同序第三位）
    assert "回归黄道，Alcabitus" in _split(_build_astro_snapshot_text({}, chart))["起盘信息"].splitlines()


def test_chart_family_snapshot_fields_default_day_boundary_to_upstream_globals() -> None:
    """页面/挂载 fields 恒带日界两键（models/astro.js:395-403、aiAnalysisContext.js:606-607 = dayBoundary 缺省 1/1），
    headless 缺键按 1/1 补 → 时间基准行「是；是」+ 排盘规则「23点算第二天 / 次日日柱」；显式值照用。
    旧代码：时间基准行「否；否」且无「排盘规则」行（上游 buildBaseInfoLines:446-455 恒出）。"""
    chart = FIXTURE["tropical_default"]["chart"]
    start = _split(_build_astro_snapshot_text(_chart_family_snapshot_fields({"hsys": 1}), chart))["起盘信息"].splitlines()
    assert "时间基准：钟表时(按输入钟面时刻,无真太阳时校正)；晚子时归次日：是；23 点换日：是" in start
    assert "排盘规则：日柱开关【23点算第二天(日柱进位次日)】+ 时柱开关【晚子时按次日日柱计算(时干用次日日干起子时)】。本盘四柱按此规则计算。" in start
    flipped = _split(_build_astro_snapshot_text(_chart_family_snapshot_fields({"after23NewDay": 0, "lateZiHourUseNextDay": 0}), chart))["起盘信息"]
    assert "排盘规则：日柱开关【24点算第二天(日柱守今、24点才换日柱)】+ 时柱开关【晚子时按当日柱计算(时干用今日日干起子时)】。本盘四柱按此规则计算。" in flipped
    assert "晚子时归次日：否；23 点换日：否" in flipped


def test_classical_calibre_line_lists_only_non_default_keys() -> None:
    """astroAiSnapshot.js:327-419 buildClassicalCalibreLine：全默认 → 零增行；非默认键按头七键 + spec 序出短语（值域外脏值不发、
    vocIncludeOuter 只随非默认 vocMode、starOrb 映回前端名）。旧代码无此行。期望串 = 上游在 live 夹具上的原文。"""
    assert snap.build_classical_calibre_line({"termsVariant": 0, "lotReversal": 1, "cazimiOrb": 17 / 60}) == ""
    sidereal = FIXTURE["sidereal_classical_hsys8"]
    expected = next(line for line in sidereal["upstream_text"].splitlines() if line.startswith("古典口径（非默认项）："))
    assert snap.build_classical_calibre_line(sidereal["fields"]) == expected
    assert expected == (
        "古典口径（非默认项）：界系=托勒密·校勘本；月交点=真交点；区分判定=Ptolemy 5°缓冲；福点=恒昼式(不随昼夜反转)；"
        "日心 cazimi=60′；空亡口径=容许度12°30′；空亡计三王星=开；宫头相位=开(≤3°)；点位相位=开(受体·≤3°)；映点容许度=2°；"
        "恒星轨档=按星等；恒星平轨=2°；落宫宫头前移=3°。"
    )
    # 值域外 / 缺 vocMode 的伴发键不发（classicalChartGlobals.js:185/188）
    assert snap.build_classical_calibre_line({"antisciaOrb": 7, "vocIncludeOuter": 1}) == ""


@requires_node
def test_classical_param_spec_mirror_matches_vendored_js() -> None:
    """Python 侧 CLASSICAL_PARAM_SPEC（send:'nonDefault' 子集，口径自陈行的判默认单源）与 vendored classicalParamSpec.js 逐项互锚：
    上游改默认/值域/键序 → vendored 先变（verbatim 看守）→ 这里红。"""
    script = (
        "import('./src/vendor/utils/classicalParamSpec.js').then((m)=>{console.log(JSON.stringify("
        "m.CLASSICAL_PARAM_SPEC.filter((s)=>s.send==='nonDefault').map((s)=>[s.key,s.backendKey||null,s.valueType,s.default,"
        "s.defaultAliases||[],s.options?s.options.map((o)=>o.value):null])));});"
    )
    vendored = json.loads(subprocess.run(["node", "-e", script], cwd=CORE_JS, capture_output=True, text=True, encoding="utf-8", check=True).stdout)
    mine = [
        [key, backend, vtype, default, list(aliases), list(options) if options is not None else None]
        for key, backend, vtype, default, aliases, options in snap.CLASSICAL_PARAM_SPEC_NON_DEFAULT
    ]
    assert mine == vendored


# ─────────────────────────── 古典·显赫计分：AstroConst shim 缺 PARS_SPIRIT ───────────────────────────
@requires_node
def test_classical_derived_sections_match_upstream_incl_spirit_lot(tmp_path) -> None:
    """[古典·*] 四段（vendored astroClassicalDerived）== 上游同盘 opt-in 输出。「四显赫点」按 AstroConst.PARS_SPIRIT 取精神点——
    共享 shim（src/constants/AstroConst.js）此前缺该常量 → id undefined → 精神点静默丢、小分由 1.5 掉成 1。"""
    fx = FIXTURE["tropical_default"]
    js = HorosaJsEngineClient(_settings(tmp_path))
    text = js.run("classical_derived", {"chart": fx["chart"], "eminence": {}})["snapshot_text"]
    mine = _split(text)
    for title, body in fx["upstream_classical_derived"].items():
        assert mine[title] == body, title
    assert "| 四显赫点 | 福点5宫✓ / 精神点9宫✓ / 根基点5宫✓ / 擢升点12宫 | 1.5 |" in mine["古典·显赫计分"].splitlines()


# ─────────────────────────── [古典] 古典格局子块（格局速览）───────────────────────────
def test_classical_section_pattern_overview_matches_upstream() -> None:
    """astroAiSnapshot.js:1486-1490：格局速览是 [古典] 段「围绕」与「身体部位」之间的「古典格局」子块，星座名走 SIGNS.cn
    （白羊/处女/水瓶）；先验权力联结四种（互容/接纳/主宰环 + [Q-558/T-520] 合相 0° 与映点）。旧代码：子块不在 [古典]
    （在 [古典格局] 且标「格局速览」）、星座名「牡羊/室女」、先验权力漏合相/映点两种联结。"""
    fx = FIXTURE["pattern_synthetic"]
    assert _split(_build_astro_snapshot_text({}, fx["chart"]))["古典"] == fx["classical"]
    assert "先验权力：土主宰环火(8·12)、金合相土(8·12)、火映点木(8·12)·昼生·非八杀朝天" in fx["classical"].splitlines()


# ─────────────────────────── 节气 [X宿盘]（buildJieQiSuSection）───────────────────────────
@pytest.mark.parametrize("case", ["no_bazi_default", "bazi_wu", "house_start_asc"])
def test_jieqi_su_section_matches_upstream(case: str) -> None:
    """JieQiChartsMain.js:739-821 逐字：宫位「地支—星次—星座座—第N宫」（八字起宫 = 日赤经座 − 时支座 − 5；缺 nongli.bazi /
    起宫=ASC 时按 ASC 赤经）、按二十八宿分组、宿内度 = 星赤经 − 距星赤经、页面星表缺省 DEFAULT_OBJECTS。
    旧代码是自拟格式（「日期/外盘/盘型」头 + `宫位：House1` + 黄道座内度），与上游零行相同。"""
    fx = FIXTURE["jieqi_su"][case]
    assert snap.build_jieqi_su_section(fx["chart"], fx["fields"]) == fx["expected"]


@requires_node
def test_jieqi_su_tables_mirror_vendored_js() -> None:
    """宿盘三张表与 vendored suzhan/SZConst.js、su28/Su28Helper.js 逐项互锚（上游改表 → 先红）。"""
    script = (
        "Promise.all([import('./src/vendor/suzhan/SZConst.js'),import('./src/vendor/su28/Su28Helper.js'),"
        "import('./src/constants/AstroConst.js')]).then(([sz,su,ac])=>{console.log(JSON.stringify({zi:sz.ZiSign,"
        "area:sz.SZSigns.map((x)=>`${x[0]}${x[1]}`),su:su.Su28,asc:sz.SZHouseStart_ASC,bazi:sz.SZHouseStart_Bazi,"
        "def:ac.DEFAULT_OBJECTS,trad:ac.TRADITION_OBJECTS}));});"
    )
    vendored = json.loads(subprocess.run(["node", "-e", script], cwd=CORE_JS, capture_output=True, text=True, encoding="utf-8", check=True).stdout)
    assert vendored["zi"] == snap.SZ_ZI_SIGN
    assert tuple(vendored["area"]) == snap.SZ_SIGN_AREA
    assert tuple(vendored["su"]) == snap.SU28_ORDER
    assert (vendored["asc"], vendored["bazi"]) == (snap.SZ_HOUSE_START_ASC, snap.SZ_HOUSE_START_BAZI)
    assert tuple(vendored["def"]) == snap.DEFAULT_OBJECTS and tuple(vendored["trad"]) == snap.TRADITION_OBJECTS


# ─────────────────────────── 合盘（buildRelativeSnapshotText）───────────────────────────
def test_relative_tables_and_score_match_upstream() -> None:
    """AstroRelative.js:74-133/207-226：互摄相位 / 中点 / 映点 / 关系量化连接一律 GFM 表，空列表不产段；契合分数按 JS 数字串
    （66，不是 66.0）。旧代码：行式「主体：…/与 … 成 … 相位」、空列表印占位存根、分数 `66.0`。"""
    fx = FIXTURE["relative_synthetic"]
    payload = {
        "inner": {"name": "甲", "date": "2028-04-06", "time": "09:33:00", "lon": "121e28", "lat": "31n13"},
        "outer": {"name": "乙", "date": "1992-03-02", "time": "08:18:00", "lon": "121e28", "lat": "31n13"},
        "hsys": 1, "zodiacal": 0, "relative": 0,
    }
    skill = _split(_build_relative_snapshot_text(payload, {**fx["comp_result"], "_relativeScore": fx["score_result"]}))
    upstream = _split(fx["comp_text"])
    score = _split(fx["score_text"])
    score.pop("关系起盘信息")   # 上游无头合盘把 Score 页签的重复 [关系起盘信息] 剥掉（aiAnalysisContext.js:1252）
    upstream.update(score)
    assert list(skill) == list(upstream)
    for title, body in upstream.items():
        assert skill[title] == body, title


def test_relative_embedded_charts_follow_upstream_tab_gating(tmp_path) -> None:
    """AstroRelative.js:160-206：组合/时空中点盘 → [合成图盘]/[时空中点·合成图盘] = 响应盘的**无头全口径**整盘；
    比较盘 / 影响盘页签不出该段。旧代码：[合成图盘] 恒出（无盘印「无」）、正文是 18 行截断的旧缩略格式。"""
    chart = FIXTURE["tropical_default"]["chart"]
    base = {"inner": {"date": "2028-04-06", "time": "09:33:00"}, "outer": {"date": "1992-03-02", "time": "08:18:00"}, "hsys": 1, "zodiacal": 0}
    composite = _split(_build_relative_snapshot_text({**base, "relative": 1}, chart))
    body = composite["合成图盘"].splitlines()
    assert body[0] == "· 起盘信息" and "· 相位" in body and "· 行星" in body and "· 主宰星链" not in body   # 未富化 → 无主宰星链
    assert "| 宫位 | 宫头 |" in body
    time_space = _split(_build_relative_snapshot_text({**base, "relative": 3}, chart))
    assert "时空中点·合成图盘" in time_space and "合成图盘" not in time_space
    comp = _split(_build_relative_snapshot_text({**base, "relative": 0}, chart))
    assert "合成图盘" not in comp and "影响图盘-星盘A" not in comp
    # 条件段双登记：上游按页签/空列表出段 → preset 与 optional 同列
    for title in ("A对B相位", "B对A反映点", "合成图盘", "关系量化", "张力连接"):
        assert title in AI_EXPORT_PRESET_SECTIONS["relative"] and title in AI_EXPORT_OPTIONAL_SECTIONS["relative"], title


# ─────────────────────────── item 8：strongRecption 上游缺省 0 ───────────────────────────
def test_strong_reception_defaults_to_upstream_zero_for_chart_family_requests(tmp_path) -> None:
    """models/astro.js:105-108/506、aiAnalysisContext.js:567/704、AstroChart13.js:24：本命 / 十三分 / 十二分盘请求恒带
    strongRecption（缺省 0）；Java ChartController.getParams 同样 `getValueAsBool("strongRecption", false)`。skill 直连 Python，
    不带即 perchart.py:814 缺省 True（严格接纳）→ [信息] 接纳/互容与上游缺省盘不同。旧代码：请求无该键。
    AuxLab 三盘（调波/龙/重置）走 AstroExtraCommon.chartParams（不带该键）→ 本仓也不补；显式值永远优先。"""
    client = CaptureClient()
    service = _service(tmp_path, client=client)
    base = {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "hsys": 1, "agent_confirmed_settings": True}
    # CaptureClient 记的是打到 chart 服务的**远端**路径（`_chart_server_endpoint`：/chart → 根路径 "/"）。
    for tool, endpoint in (("chart", "/"), ("chart13", "/chart13"), ("chart12", "/chart12"), ("hellen_chart", "/chart13")):
        client.calls.clear()
        env = service.run_tool(tool, dict(base), save_result=False)
        assert env.ok, (tool, env.error)
        sent = [payload for ep, payload in client.calls if ep == endpoint]
        assert sent and sent[0].get("strongRecption") == 0, (tool, [ep for ep, _ in client.calls])
        assert env.input_normalized.get("strongRecption") == 0
    client.calls.clear()
    service.run_tool("chart", {**base, "strongRecption": True}, save_result=False)
    assert [p for ep, p in client.calls if ep == "/"][0]["strongRecption"] is True
    for tool, endpoint in (("harmonic", "/astroextra/harmonic"), ("draconic", "/astroextra/draconic"), ("relocation", "/astroextra/relocation")):
        client.calls.clear()
        assert service.run_tool(tool, dict(base), save_result=False).ok
        sent = [payload for ep, payload in client.calls if ep == endpoint]
        assert sent and "strongRecption" not in sent[0], tool


def test_chart_family_knobs_are_hidden_from_tools_list_but_documented() -> None:
    """wave 3b 新读的三键：日界两键声明在 chart 家族四个输入模型的 `_ChartDayBoundaryKnobs`（校验层照收、MCP 扁平面顶层可传、
    ADVERTISE_HIDDEN 不进广告层），strongRecption 沿用 BirthInput（本就不广告）并补描述；三者都进 western_options_doc → guidance
    options_keys。🔴 日界两键不能放进 BirthInput：`advertised_technique_schema` 以「不在 BirthInput 里」判子类自有字段，放进去会把
    紫微/八字/奇门等中式工具已广告的同名键挤出广告层（实测 tools/list −564 B 就是这个症状）。
    旧代码：日界两键未声明（MCP 顶层传入被 FastMCP arg model 静默丢弃）、strongRecption 无描述、文档与 guidance 都查不到。"""
    from horosa_skill.agent_guidance import build_agent_guidance
    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.schemas.tools import BirthInput, ZiWeiBirthInput
    from horosa_skill.surfaces.mcp_schema import advertised_technique_schema
    from horosa_skill.western_options_doc import western_options_doc

    keys = {"after23NewDay", "lateZiHourUseNextDay"}
    for tool in ("chart", "chart13", "chart12", "hellen_chart", "harmonic", "draconic", "relocation"):
        model = TOOL_DEFINITIONS[tool].input_model
        assert keys <= set(model.model_fields), tool
        schema = advertised_technique_schema(tool, model.model_json_schema())
        assert not (keys | {"strongRecption"}) & set(schema["properties"]), tool
        doc = western_options_doc(tool)
        assert keys <= set(doc) and "排盘规则" in doc["after23NewDay"] and "晚子时" in doc["lateZiHourUseNextDay"], tool
        assert ("strongRecption" in doc) == (tool in {"chart", "chart13", "chart12", "hellen_chart"}), tool
        assert keys <= set(build_agent_guidance(tool_name=tool)["tools"][tool]["options_keys"]), tool
    assert "缺省" in (BirthInput.model_fields["strongRecption"].description or "")
    assert keys.isdisjoint(BirthInput.model_fields)
    # 中式工具自有的同名键仍在广告层（负向：放进 BirthInput 即从这里消失）
    ziwei = advertised_technique_schema("ziwei_birth", ZiWeiBirthInput.model_json_schema())
    assert "after23NewDay" in ziwei["properties"]


# ─────────────────────────── [埃及历] 只吃本盘 ───────────────────────────
class _EgyptRecordingJs(FakeJsClient):
    def __init__(self) -> None:
        super().__init__()
        self.egypt_payloads: list[dict] = []

    def run(self, tool_name: str, payload: dict[str, object]) -> dict:
        if tool_name == "egypt_section":
            self.egypt_payloads.append(payload)
        return super().run(tool_name, payload)


class _AnalysisWithCalendar(FakeClient):
    def __init__(self, *, fail_analysis: bool = False) -> None:
        super().__init__()
        self.fail_analysis = fail_analysis

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/astroextra/analysis":
            if self.fail_analysis:
                raise RuntimeError("analysis down")
            return {**super().call(endpoint, payload), "egyptianCalendar": {"siriusRising": "2028-08-05", "decanIndex": 9}}
        return super().call(endpoint, payload)


@pytest.mark.parametrize("fail_analysis", [False, True])
def test_egypt_section_reads_only_the_chart(tmp_path, fail_analysis: bool) -> None:
    """上游唯一调用点 astroAiSnapshot.js:1731 `buildEgyptSectionLines(chartObj, …)` 传 /chart 结果（无 egyptianCalendar，该字段
    只在 /astroextra/analysis）→ 上游 [埃及历] 恒无「天狼偕日升」行。旧代码：把 analysis 的 egyptianCalendar 并进盘对象（多一行），
    且只在 analysis 成功后才建 [埃及历]（analysis 失败 → 段整个丢）。"""
    js = _EgyptRecordingJs()
    service = _service(tmp_path, client=_AnalysisWithCalendar(fail_analysis=fail_analysis), js_client=js)
    env = service.run_tool("chart", {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True}, save_result=False)
    assert env.ok, env.error
    assert js.egypt_payloads, "egypt_section 未调用"
    assert all("egyptianCalendar" not in p["chart"] for p in js.egypt_payloads)


@requires_node
def test_egypt_decan_naming_tag_follows_school(tmp_path) -> None:
    """[Q-540/T-502]（AstroEgypt.js:80-86）：◆各行星落旬 的主显名标签随「旬名传统」档（埃及本名 → 「埃及名」；科普特-希腊名 /
    赫尔墨斯名 原样）。旧 tools/egyptSection.js 恒写「·埃及名 」（选后两档时标签错）。"""
    js = HorosaJsEngineClient(_settings(tmp_path))
    chart = FIXTURE["tropical_default"]["chart"]

    def decans(fields: dict) -> str:
        text = js.run("egypt_section", {"chart": chart, "fields": fields})["text"]
        return text.split("◆ 上升旬详情")[0]

    assert "·埃及名 " in decans({})
    coptic = decans({"egypt_decanNaming": {"value": "coptic"}})
    assert "·科普特-希腊名 " in coptic and "·埃及名 " not in coptic
    assert "·赫尔墨斯名 " in decans({"egypt_decanNaming": {"value": "hermes"}})


# ─────────────────────────── 派生盘专属段（AuxLab）───────────────────────────
def test_derived_chart_specialty_sections_follow_auxlab_templates(tmp_path) -> None:
    """AstroDraconicLab.js:53 北交点行注明真/平交点（[Q-351/T-332]，旧代码漏）；AstroRelocationLab.js:139 地点行印页面 state
    的十进制度 `Number(deg.toFixed(4))`（40n43 → 40.7167、74w00 → -74；旧代码印后端回显 40n43）；AstroHarmonicLab.js:73-81
    [调波盘] 恒出（out 至少 [段头, 调波数]）；位置/同频数值走 toFixed（平局取大，非 Python 银行家舍入）。"""
    service = _service(tmp_path)
    base = {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "hsys": 1, "agent_confirmed_settings": True}
    draconic = _split(service.run_tool("draconic", dict(base), save_result=False).data["snapshot_text"])["龙盘"].splitlines()
    assert draconic[0] == "北交点 123.45°（平交点） → 归零白羊 0°（龙盘基准）"
    true_node = _split(service.run_tool("draconic", {**base, "westNodeType": "true"}, save_result=False).data["snapshot_text"])["龙盘"]
    assert true_node.splitlines()[0] == "北交点 123.45°（真交点） → 归零白羊 0°（龙盘基准）"
    reloc = _split(service.run_tool("relocation", {**base, "relocLat": "40n43", "relocLon": "74w00"}, save_result=False).data["snapshot_text"])["重置盘"]
    assert reloc.splitlines()[0] == "重置地点：纬 40.7167 / 经 -74"
    harmonic = _split(service.run_tool("harmonic", {**base, "harmonic": 5}, save_result=False).data["snapshot_text"])["调波盘"].splitlines()
    assert harmonic[0] == "调波数：H5"
    assert "Sun：本命黄经 11.87° → 调波 Capricorn16.90°" in harmonic
