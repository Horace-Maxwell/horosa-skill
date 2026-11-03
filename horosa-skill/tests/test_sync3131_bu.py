"""上游星阙 v3.13.1（965af0f4..06f25f21）卜类 / 三式 / 神数 / 玄史 / 繁体输出 的同步点。

每条钉一个值级事实，期望值取自上游源本身（HOROSA_SOURCE_ROOT 指 Horosa-Public）、vendored 引擎或 vendored v3.13.1
实例的录制（tests/fixtures/sync3131_jieqi_live.json），不手算。负向对照均实际跑过，记在各条 docstring 里。
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from horosa_skill.textscript import TRADITIONAL, convert
from horosa_skill.textscript.localize import classic_spans, localize

PKG = Path(__file__).resolve().parents[1]
CORE_JS_SRC = PKG / "horosa-core-js" / "src"
JIEQI_LIVE = Path(__file__).resolve().parent / "fixtures" / "sync3131_jieqi_live.json"
RULES_JSON = PKG / "src" / "horosa_skill" / "textscript" / "data" / "horosa_char_rules.json"
_UPSTREAM_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
UPSTREAM_UI = Path(_UPSTREAM_ROOT) / "Horosa-Web" / "astrostudyui" / "src" if _UPSTREAM_ROOT else None
requires_upstream = pytest.mark.skipif(
    UPSTREAM_UI is None or not UPSTREAM_UI.is_dir(), reason="HOROSA_SOURCE_ROOT (upstream checkout) not set"
)
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _node(module: str, body: str, *args: Any) -> Any:
    from node_esm import run_node_esm

    script = (
        "import(process.argv[1]).then(async (m) => { const argv = process.argv.slice(2);"
        " const fs = await import('node:fs');"
        f" const out = await (async () => {{ {body} }})(); process.stdout.write(JSON.stringify(out)); }});"
    )
    return json.loads(run_node_esm(script, CORE_JS_SRC / module, *args))


# ── 奇门：节气种子日柱（上游「冬至日柱订正」） ─────────────────────────────────────────────────────────

@requires_node
def test_qimen_seed_day_pillar_is_filled_by_the_terms_own_date() -> None:
    """上游 utils/preciseCalcBridge.js fillJieqiDayGanzhiFromLocal（:234-279 @06f25f21）：/jieqi/year 的节气行不带日柱时
    按本地历法补，v3.13.1 起按**交节日自身日期**取（getDayGanZhi），不再按节气名去本地年表捡（本地表「冬至」是上年
    12 月那个 → 冬至日柱恒错一年）。本仓奇门打的是 Python /jieqi/year，录制显示它**从不**带日柱 —— 此前 tools/qimen.js
    根本不补，种子 dayGanzhi 恒空串（置闰至锚 / 日家至甲子全退兜底）。期望值 = 同一请求打 Java 层 /jieqi/year 回的
    bazi.fourColumns.day.ganzi（录制，非手算），3 年 × 24 节气逐条相等。
    负向对照：qimen.js 的 getLocalDayGanzhi 去掉「按交节日期」分支（只按名查本地表）→ 红（实跑过）。
    「buildYearSeed 根本不补」由下一条（整盘比对）看守。"""
    live = json.loads(JIEQI_LIVE.read_text(encoding="utf-8"))
    got = _node(
        "tools/qimen.js",
        "const live = JSON.parse(fs.readFileSync(new URL(argv[0]), 'utf8')); const out = {};"
        " for (const [y, rows] of Object.entries(live.years)) {"
        "   const yr = { jieqi24: rows.map(([jieqi, time]) => ({ jieqi, time })) };"
        "   const seed = m.jieqiSeedFromYearResult(m.fillJieqiDayGanzhiFromLocal(yr, Number(y), '+08:00'));"
        "   out[y] = rows.map(([jieqi]) => seed[jieqi].dayGanzhi); }"
        " return out;",
        JIEQI_LIVE,
    )
    for year, rows in live["years"].items():
        assert got[year] == [row[2] for row in rows], year
    # 上游修的就是这个错：按节气名去本地年表捡冬至，捡到的是上一年 12 月那天
    by_name = _node(
        "vendor/utils/localNongliAdapter.js",
        "return m.buildLocalJieqiYearSeed(2024, '+08:00')['冬至'];",
    )
    java_2024_dz = next(row[2] for row in live["years"]["2024"] if row[0] == "冬至")
    assert by_name["dateKey"].startswith("202312") and by_name["dayGanzhi"] != java_2024_dz


@requires_node
@pytest.mark.parametrize(
    ("date", "options"),
    [
        ("2024-12-15", {"paiPanType": 2}),                                          # 日家：至甲子定局
        ("2024-12-25", {"paiPanType": 3, "school": "飞盘", "qijuMethod": "zhirun"}),  # 置闰：冬至锚
        ("2024-03-01", {"paiPanType": 3, "school": "飞盘", "qijuMethod": "wurun"}),   # 无闰
        ("2025-01-10", {"paiPanType": 3, "school": "飞盘", "qijuMethod": "wurun"}),
    ],
)
def test_qimen_local_route_with_python_seeds_equals_java_seeded_pan(date: str, options: dict[str, Any]) -> None:
    """本地路由（飞盘 / 日家…，isQimenLocalRoute）吃节气种子：Python /jieqi/year（无日柱，本仓实际路径）补日柱后排出的盘
    与带 Java 日柱的种子排出的盘逐字相同（上游页面 = Java seedOnly 回包 + fillJieqiDayGanzhiFromLocal，同为此口径）。
    此前不补：2024-12-15 日家出「阴遁九局 大雪上元」（应「阴遁六局 大雪下元」）、2024-03-01 飞盘无闰出「阳遁九局 雨水上元」
    （应「阳遁一局 惊蛰上元」）。负向对照：buildYearSeed 不调 fillJieqiDayGanzhiFromLocal → 四条全红（实跑过）。"""
    got = _node(
        "tools/qimen.js",
        "const live = JSON.parse(fs.readFileSync(new URL(argv[0]), 'utf8')); const date = argv[1]; const options = JSON.parse(argv[2]);"
        " const y = parseInt(date.slice(0, 4), 10);"
        " const py = (yy) => ({ jieqi24: live.years[yy].map(([jieqi, time]) => ({ jieqi, time })) });"
        " const jv = (yy) => ({ jieqi24: live.years[yy].map(([jieqi, time, g]) => ({ jieqi, time, bazi: { fourColumns: { day: { ganzi: g } } } })) });"
        " const base = { date, time: '12:00:00', zone: '+08:00', lat: '39n54', lon: '116e23', options };"
        " const need3 = options.paiPanType === 2 || options.paiPanType === 6;"
        " const run = (f) => m.runQimen({ ...base, jieqi_year_prev: f(y - 1), jieqi_year_current: f(y),"
        "   ...(need3 && live.years[y + 1] ? { jieqi_year_next: f(y + 1) } : {}) }).snapshot_text;"
        " return { py: run(py), jv: run(jv) };",
        JIEQI_LIVE,
        date,
        json.dumps(options, ensure_ascii=False),
    )
    assert got["py"] and got["py"] == got["jv"]


# ── 演禽：参筹秘书并入江西派（旧值别名）；改回原值归回原流派 ───────────────────────────────────────────

@requires_node
def test_yanqin_canchou_is_a_legacy_alias_of_jiangxi_and_setoption_rematches() -> None:
    """上游 components/yanqin/yanqinSchools.js（v3.13.1）：canchou 标 hidden、覆盖项与 jiangxi 逐项相同（键保留，旧记录照解析）；
    setOption 偏离预设记 schoolBase、改回该预设组合即归回原流派（rematchPreset）。本仓 tools/yanqinYanfa.js 每次调用
    applyPreset + 逐键 setOption（vendored），shenshu_options 的 school 词表照收 canchou。
    结果：canchou 与 jiangxi 只差流派名一行；jiangxi + sansuo=fanqin（= 预设值）仍是 jiangxi，sansuo=suobo 才是 custom
    且记 schoolBase=jiangxi（v3.13.1 起）。
    负向对照：shenshu_options 的 xianqin.school 词表删去 canchou → 首条断言红（实跑过）。rematchPreset 本身在本仓单次设键
    路径上不可观测（每键只设一次、设成预设值时根本不偏离），这里只钉 schoolBase 随 vendored 引擎出现。"""
    from horosa_skill.shenshu_options import SHENSHU_OPTION_KNOBS

    assert "canchou" in SHENSHU_OPTION_KNOBS["xianqin"]["school"].choices
    got = _node(
        "tools/yanqinYanfa.js",
        "const base = { year: 2024, month: 5, day: 1, hour: 10 };"
        " const a = m.runYanqinYanfa({ ...base, school: 'canchou' }); const b = m.runYanqinYanfa({ ...base, school: 'jiangxi' });"
        " const al = a.text.split('\\n'), bl = b.text.split('\\n');"
        " return { diff: al.map((l, i) => [l, bl[i]]).filter(([l, r]) => l !== r),"
        "   same: m.runYanqinYanfa({ ...base, school: 'jiangxi', sansuo: 'fanqin' }).data.settings.school,"
        "   off: m.runYanqinYanfa({ ...base, school: 'jiangxi', sansuo: 'suobo' }).data.settings };",
    )
    assert len(got["diff"]) == 1
    left, right = got["diff"][0]
    assert left.startswith("参筹秘书(＝江西派);") and right.startswith("江西派(翻禽倒将);")
    assert left.split(";", 1)[1] == right.split(";", 1)[1]
    assert got["same"] == "jiangxi"
    assert got["off"]["school"] == "custom" and got["off"]["schoolBase"] == "jiangxi"


# ── 繁体：v3.13.1 新判据 + 玄史古籍转换档 ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("simplified", "traditional"),
    [
        ("核验里语", "核驗裡語"),            # 上游 hantRules.js 「里」+ 验里→驗裡（hantCorpus WORD_BOUNDARY_CONTEXTS 核[验里]语）
        ("十神里正", "十神裡正"),            # + 神里→神裡（十[神里]正）
        ("见生便喜、见克便忧", "見生便喜、見剋便憂"),  # KE_CONTEXT.domain + 见（六爻古断）
    ],
)
def test_upstream_v3131_hant_rules(simplified: str, traditional: str) -> None:
    """上游 utils/scriptConvert/hantRules.js（06f25f21）：「里」整词 +验里 / 神里；「克」生克语境 +见。规则表逐项比对在
    tests/test_textscript.py::test_character_rules_cover_upstream_except_documented_deviations（上游改 → 它红，本次实红过）。
    负向对照：horosa_char_rules.json 删去「验里」/「神里」/ ke.domain 的「见」→ 对应一条红（实跑过）。"""
    assert convert(simplified, TRADITIONAL) == traditional


# 上游 utils/__tests__/hantClassicScope.test.js（06f25f21 新增）的两组 test.each，逐条照抄。
_CLASSIC_KEEP = [
    ("范晔", "范曄"), ("问范曰", "問范曰"), ("范明友", "范明友"), ("范阳", "范陽"), ("吴范", "吳范"),
    ("范文正公", "范文正公"), ("能大师范阳人", "能大師范陽人"), ("昭国里", "昭國里"), ("太平里", "太平里"), ("邻里", "鄰里"),
    ("里中火起", "里中火起"), ("步里客谈", "步里客談"),
]
_CLASSIC_WORDS = [("洪范九畴", "洪範九疇"), ("垂范后世", "垂範後世"), ("范围", "範圍"), ("心里", "心裡"), ("这里", "這裡"), ("宫里", "宮裡")]


@pytest.mark.parametrize(("simplified", "traditional"), _CLASSIC_KEEP + _CLASSIC_WORDS)
def test_classic_scope_matches_upstream_toHantClassic(simplified: str, traditional: str) -> None:
    """上游 hantConverter.toHantClassic / hantRules.js CLASSIC_RULES + CLASSIC_NOT_RIGHT（v3.13.1「玄史古籍原文繁体『范 / 里』
    保留原字」）：古籍区段里范 / 里缺省保留原字，只在整词表里取 範 / 裡，「范阳」右邻否决。期望值 = 上游 hantClassicScope.test.js。
    负向对照：converter._apply_char_rules 去掉 classic 分支 → 问范曰 / 范明友 / 吴范 / 昭国里 / 太平里 / 里中火起 等 7 条红
    （范晔 / 范阳 / 整词表各条通用档本就同字，不红；实跑过）。"""
    assert convert(simplified, TRADITIONAL, ((0, len(simplified)),)) == traditional


@requires_upstream
def test_classic_tables_equal_upstream_value_for_value() -> None:
    """horosa_char_rules.json 的 classic 段 = 上游 hantRules.js CLASSIC_RULES（整词表、次序）+ CLASSIC_NOT_RIGHT（右邻否决）。
    hantClassicScope.test.js 的两组用例也逐条解析出来比（不靠上面照抄的副本）。
    负向对照：classic.范.words 删去「示范」→ 红（实跑过）。"""
    import re

    from test_textscript import _upstream_consts

    up = _upstream_consts()
    ours = json.loads(RULES_JSON.read_text(encoding="utf-8"))["classic"]
    assert {k for k in ours if not k.startswith("_")} == set(up["CLASSIC_RULES"])
    for char, words in up["CLASSIC_RULES"].items():
        assert ours[char]["words"] == words, char
        assert ours[char]["to"] == ("範" if char == "范" else "裡")   # hantRules.js CLASSIC_INDEX 的 to
        assert set(ours[char]["right_veto"]) == set(up["CLASSIC_NOT_RIGHT"].get(char, set())), char
    test_js = (UPSTREAM_UI / "utils" / "__tests__" / "hantClassicScope.test.js").read_text(encoding="utf-8")
    cases = re.findall(r"\['([^']+)', '([^']+)'\]", test_js)
    assert len(cases) >= 18
    for simplified, traditional in cases:
        assert convert(simplified, TRADITIONAL, ((0, len(simplified)),)) == traditional, simplified


def test_xuanshi_original_text_spans_convert_in_classic_scope_only() -> None:
    """上游 XuanShi{Events,Figures,Celestial,Micro,Search}.js 把「原文 / 史书原文」容器挂 horosa-script-classic，其余界面文案
    走通用档。本仓玄史出一段快照文本：「原文：」之后到行尾 / 下一格标签为止是古籍区段（textscript.localize.classic_spans），
    其余照通用档；只对 tool=xuanshi 的信封生效，别的工具同一段字逐字不变。
    负向对照：localize._walk 不再按 CLASSIC_TOOLS 置 classic → 原文行「范明友 / 昭国里」转成 範 / 裡 → 红（实跑过）。"""
    text = "[条目详情]\n标题：范明友\n原文：范明友居昭国里，心里不安；白话：范明友住在昭国里\n"
    assert [text[a:b] for a, b in classic_spans(text)] == ["范明友居昭国里，心里不安"]
    row = "1. 标题：吴范；原文：吴范问范曰；解读：范"
    assert [row[a:b] for a, b in classic_spans(row)] == ["吴范问范曰"]
    out = localize({"tool": "xuanshi", "data": {"snapshot_text": text, "export_snapshot": {"export_text": text}}}, TRADITIONAL)
    want = "[條目詳情]\n標題：範明友\n原文：范明友居昭國里，心裡不安；白話：範明友住在昭國裡\n"
    assert out["data"]["snapshot_text"] == want
    assert out["data"]["export_snapshot"]["export_text"] == want
    other = localize({"tool": "astrodata", "data": {"snapshot_text": text}}, TRADITIONAL)
    assert other["data"]["snapshot_text"] == convert(text, TRADITIONAL)
    assert "原文：範明友居昭國裡" in other["data"]["snapshot_text"]


def test_xuanshi_envelope_end_to_end_keeps_classic_chars_in_original_only(tmp_path: Path) -> None:
    """真走一次 run_tool('xuanshi')（后端打桩回一条事件详情）→ textscript.localize（MCP / CLI 出口同一函数）：信封 tool=xuanshi，
    快照与 export_text 的「原文：」行范 / 里保留原字，标题 / 白话行照通用档。
    负向对照：localize.CLASSIC_TOOLS 改成空集 → 原文行出「範明友居昭國裡」→ 红（实跑过）。"""
    from horosa_skill.config import Settings
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    service._call_remote = lambda endpoint, payload, backend=None: {  # type: ignore[method-assign]
        "event_id": "E1", "title": "范明友占", "original_text": "范明友居昭国里", "modern_text": "范明友住在昭国里",
    }
    result = service.run_tool("xuanshi", {"action": "event", "id": "E1"}, save_result=False)
    assert result.ok and result.tool == "xuanshi"
    out = localize(result, TRADITIONAL)
    for text in (out.data["snapshot_text"], out.data["export_snapshot"]["export_text"]):
        lines = text.splitlines()
        assert "原文：范明友居昭國里" in lines
        assert "標題：範明友占" in lines and "白話：範明友住在昭國裡" in lines


# ── 宿占：sunriseMode 是死键（上游 SUZHAN_DEAD_CLASSICAL_KEYS） ──────────────────────────────────────

class _StopAtChart(Exception):
    pass


def test_suzhan_neither_forwards_nor_echoes_sunrise_mode(tmp_path: Path) -> None:
    """上游 utils/techniqueMountSettings.js:1722（06f25f21）SUZHAN_DEAD_CLASSICAL_KEYS 收 sunriseMode（宿占挂载齿轮隐去），
    宿占 recordPayloadKeys（:1774）不带它；vendored v3.13.1 实例实测 apparent 与缺省宿占快照逐字同（八字公式 / ASC 两档）。
    BirthInput（C2）现对所有继承工具接受 sunriseMode → 宿占此前会照单下发 /chart、技法卡印「日出 / 日没口径=apparent」，
    替没参与计算的口径作证。负向对照：guolao._run_suzhan_tool 改回 `{**payload, …}` → 下发断言红；
    technique_card._FIELD_DEAD_FOR_TOOLS 去掉 suzhan → 卡片断言红（均实跑过）。"""
    from horosa_skill.config import Settings
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.reports.technique_card import _settings_used
    from horosa_skill.service import HorosaSkillService

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    sent: list[dict[str, Any]] = []

    def call_remote(endpoint: str, payload: dict[str, Any], backend: str | None = None) -> dict[str, Any]:
        sent.append(dict(payload))
        raise _StopAtChart(endpoint)

    service._call_remote = call_remote  # type: ignore[method-assign]
    for house_start in (0, 1):
        with pytest.raises(_StopAtChart):
            service._run_suzhan_tool({"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "39n54",
                                      "lon": "116e23", "houseStartMode": house_start, "sunriseMode": "apparent"})
    assert len(sent) == 2 and all("sunriseMode" not in body for body in sent)
    assert "sunriseMode" not in _settings_used({"sunriseMode": "apparent"}, {}, "cn", "suzhan")
    assert _settings_used({"sunriseMode": "apparent"}, {}, "cn", "guolao")["sunriseMode"]["value"] == "apparent"
