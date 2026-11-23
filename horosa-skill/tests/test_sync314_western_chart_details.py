"""上游 v3.14.0 · 占星「盘面细节」段（导出 v61）与重置盘的两处改口。

**金标的独立来源**
- `tests/fixtures/sync314_western_chart_details.json.gz` = 上游自己的全表金标 `astropy/tests/data/golden_chart_details.json`
  （四张定盘：缺省口径 / 五项口径全非缺省 / 南半球 / 极区 Koch；30 张表逐值）+ 上游测试里的请求体（`GOLDEN_CHARTS`，
  用 `targetDate=2026/01/01` 钉住受孕期）+ vendored `buildChartDetailsText` 排出的正文。
  `test_fixture_matches_upstream` 在 HOROSA_SOURCE_ROOT 可用时把三者对上游逐值重比。
- 正文排版的逐字期望值另见 npm selfcheck（上游 jest `chartDetails.test.js` 的样本与断言原样搬过去）。
- live 用例把时钟冻在 2026-01-01 12:00（盘时区）：skill 工具的 30 张表 == 上游金标、整段正文 == 夹具正文——
  请求体（与起盘同形 + 口径键 + 目标时刻）错一个键就红。

**负向对照（都实跑过，见各用例 docstring）**。
"""

from __future__ import annotations

from skips import upstream_source  # 上游拆文件后读「门面 + 子模块」全集（v3.15.0）
import copy
import gzip
import hashlib
import itertools
import json
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from float_tree import golden_diff, golden_text_diff
from fakes import CaptureClient, FakeClient, FakeJsClient
from node_esm import run_node_esm
from skips import needs_upstream, upstream_path
from sync314_western_fakes import chart_details_fixture, fake_chart_details_response
from test_local_js_tools import make_service, requires_chart

from horosa_skill import western_vocab as vocab
from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.engine.registry import CHART_DETAILS_TOOLS, CLASSICAL_ANALYSIS_TOOLS, TOOL_DEFINITIONS
from horosa_skill.errors import ToolTransportError, ToolValidationError
from horosa_skill.exports.registry import (
    AI_EXPORT_OPTIONAL_SECTIONS,
    AI_EXPORT_PRESET_SECTIONS,
    SECTIONS_NOT_PRODUCED_BY_DESIGN,
)
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools.base import advertise_hidden_fields
from horosa_skill.service import HorosaSkillService, _clock
from horosa_skill.service.text.western import _with_natal_planet_sign
from horosa_skill.western_options_doc import western_options_doc

CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "sync314_western_chart_details.json.gz"
FX = chart_details_fixture()
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")

BIRTH = {"date": "1990-05-17", "time": "14:30:00", "zone": "+08:00", "lat": "31n14", "lon": "121e28", "defaults_accepted": True}
DETAIL_KEYS = ("detailFaces", "detailVariant", "detailLunar", "detailMundo", "detailMidpoint", "detailTable")
# 上游请求键 → skill 入参名（chartDetailRequestFields 的反向；夹具里的请求体是上游形状）。
REQUEST_TO_SETTING = {"detailFaces": "detailFaces", "variant": "detailVariant", "lunarMethod": "detailLunar",
                      "mundoSystem": "detailMundo", "midpointCoord": "detailMidpoint"}
ALL_TABLES = [value for value, _label in vocab.CHART_DETAIL_TABLES]


def _settings(tmp_path) -> Settings:
    return Settings(server_root="http://127.0.0.1:9", runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")


class DerivedJs(FakeJsClient):
    """FakeJsClient 没有 classical_derived 的桩（本命盘的古典衍化四段因此缺席）；段位用例需要它们在场。"""

    def run(self, tool_name: str, payload: dict) -> dict:
        if tool_name == "classical_derived":
            titles = ("古典·派生宫转宫", "古典·气候带", "古典·显赫计分", "古典·世界范式盘")
            return {"snapshot_text": "\n\n".join(f"[{title}]\n{title}：离线替身内容。" for title in titles)}
        return super().run(tool_name, payload)


def _service(tmp_path, client=None, js_client=None) -> HorosaSkillService:
    settings = _settings(tmp_path)
    return HorosaSkillService(settings, client=client or FakeClient(), store=MemoryStore(settings), js_client=js_client or DerivedJs())


def _titles(text: str) -> list[str]:
    return re.findall(r"^\[(.+?)\]$", text, flags=re.M)


def _section(text: str, title: str) -> str:
    start = text.index(f"[{title}]\n")
    nxt = re.search(r"^\[.+\]$", text[start + len(title) + 3:], flags=re.M)
    end = start + len(title) + 3 + nxt.start() if nxt else len(text)
    return text[start:end].strip()


def _freeze(monkeypatch, zone: str, moment: tuple[int, ...] = (2026, 1, 1, 12, 0, 0)) -> None:
    sign = -1 if zone.startswith("-") else 1
    offset = timedelta(hours=sign * int(zone[1:3]), minutes=sign * int(zone[4:6]))
    frozen = datetime(*moment, tzinfo=timezone(offset))
    monkeypatch.setattr(_clock, "now", lambda tz=None: frozen.astimezone(tz) if tz else frozen)


def _calls(client: CaptureClient, endpoint: str) -> list[dict]:
    wire = "/" if endpoint == "/chart" else endpoint   # chart 服务上 /chart 的线上路径是 "/"（endpoints._chart_server_endpoint）
    return [payload for called, payload in client.calls if called == wire]


def _skill_payload(case: str, **extra) -> dict:
    """夹具里的上游请求体 → skill 工具入参（日期写成 ISO，口径键换成 skill 入参名）。"""
    payload = {REQUEST_TO_SETTING.get(key, key): value for key, value in FX["requests"][case].items()}
    payload["date"] = payload["date"].replace("/", "-")
    return {**payload, "defaults_accepted": True, **extra}


# ─────────────────────────── 词表 / 映射：手抄件对 vendored 上游逐值互锚 ───────────────────────────
@requires_node
def test_vocabularies_tables_and_defaults_equal_the_vendored_upstream_module(tmp_path) -> None:
    """western_vocab 的五项口径值域 / 中文名 / 缺省、30 张表的 id / 中文名 / 顺序 == vendored utils/chartDetails.js。
    负向对照：把 CHART_DETAIL_DEFAULTS['detailLunar'] 改成 'tithi'、或把表名「寿主」改成「寿主星」→ 红（实跑过）。"""
    catalog = HorosaJsEngineClient(_settings(tmp_path)).run("chart_details", {"action": "catalog"})
    assert [(row["value"], row["label"]) for row in catalog["tables"]] == list(vocab.CHART_DETAIL_TABLES)
    assert len(vocab.CHART_DETAIL_TABLES) == 30
    groups = catalog["setting_groups"]
    assert set(groups) == set(vocab.CHART_DETAIL_REQUEST_KEYS) == set(vocab.CHART_DETAIL_ECHO_PATHS)
    for name, group in groups.items():
        upstream = [(row["value"], row["label"]) for row in catalog["options"][group]]
        mine = [(row["value"], row["label"].removesuffix("（缺省）")) for row in vocab.CHART_DETAIL_VOCABULARIES[name].accepted]
        assert mine == upstream, name
        assert vocab.CHART_DETAIL_DEFAULTS[name] == catalog["defaults"][group]
        assert vocab.CHART_DETAIL_VOCABULARIES[name].labels[catalog["defaults"][group]].endswith("（缺省）")
    assert vocab.CHART_DETAIL_DEFAULTS["detailTable"] == catalog["defaults"]["table"] == "topics"
    assert [row["value"] for row in vocab.CHART_DETAIL_VOCABULARIES["detailTable"].accepted] == ALL_TABLES


@requires_node
def test_request_field_port_equals_the_upstream_function_for_every_combination() -> None:
    """Python 手抄的 chart_detail_request_fields == vendored chartDetailRequestFields，五项口径 2×2×5×12×6 = 1440 种组合逐一比。
    负向对照：把 CHART_DETAIL_REQUEST_KEYS 的 'lunarMethod' 写成 'lunar' → 红（实跑过）。"""
    names = list(vocab.CHART_DETAIL_REQUEST_KEYS)
    domains = [[row["value"] for row in vocab.CHART_DETAIL_VOCABULARIES[name].accepted] for name in names]
    script = (
        "const m = await import(process.argv[1]);"
        "const names = JSON.parse(process.argv[2]); const domains = JSON.parse(process.argv[3]); const out = [];"
        "const walk = (i, acc) => { if (i === names.length) { out.push(m.chartDetailRequestFields(acc)); return; }"
        " domains[i].forEach((v) => walk(i + 1, { ...acc, [names[i]]: v })); };"
        "walk(0, {}); process.stdout.write(JSON.stringify(out));"
    )
    upstream = json.loads(run_node_esm(script, CORE_JS / "src" / "vendor" / "utils" / "chartDetails.js", json.dumps(names), json.dumps(domains)))
    combos = list(itertools.product(*domains))
    assert len(upstream) == len(combos) == 1440
    for combo, expected in zip(combos, upstream):
        assert vocab.chart_detail_request_fields(dict(zip(names, combo))) == expected, combo
    assert vocab.chart_detail_request_fields({}) == {}


@needs_upstream("Horosa-Web/astropy/astrostudy/chart_details_more.py", "Horosa-Web/astropy/astrostudy/chart_details.py")
def test_option_domains_equal_what_the_backend_accepts() -> None:
    """后端对认不出的值静默回缺省：词表必须正好是后端认的那几档（chart_details_more.py 的三张表 + chart_details.py 的两个判断）。"""
    more = upstream_source(upstream_path("Horosa-Web/astropy/astrostudy/chart_details_more.py"))
    main = upstream_source(upstream_path("Horosa-Web/astropy/astrostudy/chart_details.py"))

    def values(name: str) -> list[str]:
        return [row["value"] for row in vocab.CHART_DETAIL_VOCABULARIES[name].accepted]

    lunar = re.search(r"^LUNAR_METHODS\s*=\s*\(([^)]*)\)", more, flags=re.M)
    assert sorted(re.findall(r"'(\w+)'", lunar.group(1))) == sorted(values("detailLunar"))
    mundo = re.search(r"^MUNDO_SYSTEMS\s*=\s*\{(.*?)\}", more, flags=re.M | re.S)
    assert sorted(re.findall(r"'(\w+)':\s*b'", mundo.group(1)) + ["proportional"]) == sorted(values("detailMundo"))
    coords = re.search(r"^MIDPOINT_COORDS\s*=\s*\(([^)]*)\)", more, flags=re.M)
    assert sorted(re.findall(r"'(\w+)'", coords.group(1))) == sorted(values("detailMidpoint"))
    assert "'element' if str(data.get('detailFaces')) == 'element' else 'chaldean'" in main
    assert "classic = str(data.get('variant')) == 'classic'" in main
    for request_key in ("lunarMethod", "mundoSystem", "midpointCoord"):
        assert f"data.get('{request_key}')" in main
    for table, _label in vocab.CHART_DETAIL_TABLES:
        assert f"'{table}':" in main, table


@needs_upstream("Horosa-Web/astropy/tests/data/golden_chart_details.json", "Horosa-Web/astropy/tests/test_chart_details.py")
def test_fixture_matches_upstream() -> None:
    """夹具 = 上游金标的子集（逐值）+ 上游测试里的请求体（把那几行源码原样 exec 出来比）。"""
    raw = upstream_path("Horosa-Web/astropy/tests/data/golden_chart_details.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FX["source"]["golden_sha256"]
    goldens = json.loads(raw)
    source = upstream_source(upstream_path("Horosa-Web/astropy/tests/test_chart_details.py"))
    namespace: dict = {}
    for name in ("CHART", "DAY_CHART", "POLAR"):
        exec(re.search(rf"^{name} = .*$", source, flags=re.M).group(0), {"dict": dict}, namespace)  # noqa: S102 — 上游测试源里的三行字面量
    exec(source[source.index("GOLDEN_CHARTS = {"): source.index("GOLDEN_PATH")], {"dict": dict, **namespace}, namespace)  # noqa: S102
    assert "targetDate='2026/01/01'" in source and FX["source"]["target_date"] == "2026/01/01"
    assert set(FX["goldens"]) == set(FX["requests"]) == set(FX["texts"]) == {"polar-koch", "seattle-night", "sydney", "tokyo-classic"}
    for case in FX["goldens"]:
        assert FX["goldens"][case] == goldens[case], case
        assert FX["requests"][case] == namespace["GOLDEN_CHARTS"][case], case


@requires_node
def test_fixture_texts_are_what_the_vendored_builder_prints_for_the_goldens(tmp_path) -> None:
    """夹具正文 = 真 JS 工具对金标排出的正文（vendored builder 或共享名表一动即红——例如共享 AstroConst shim 缺恒星常量时
    「狮心轩辕十四」会印成「轩辕十四」，见 test_sync314_western_shims.py）。"""
    js = HorosaJsEngineClient(_settings(tmp_path))
    for case, golden in FX["goldens"].items():
        out = js.run("chart_details", {"result": golden, "tables": ["hellenistic"]})
        assert out["text"] == FX["texts"][case], case
        assert out["tables"] == {"hellenistic": {"label": "希腊化细节", "data": golden["hellenistic"]}}
    sydney = FX["texts"]["sydney"].split("\n")
    assert sydney[0] == "[盘面细节]" and sydney[1] == "口径：迦勒底面 · 改进"
    assert any(line.startswith("月亮日(Tithi):") for line in sydney) and any(line.startswith("世俗相位(地平):") for line in sydney)
    assert any(line.startswith("中点(世俗位置,前 15 组):") for line in sydney)
    tokyo = FX["texts"]["tokyo-classic"].split("\n")
    assert tokyo[1] == "口径：元素面 · 经典" and any(line.startswith("中点(赤经,前 15 组):") for line in tokyo)
    assert any(line.startswith("世俗相位缺点:") for line in FX["texts"]["polar-koch"].split("\n")) is bool(FX["goldens"]["polar-koch"]["inMundo"]["missing"])


# ─────────────────────────── schema / guidance / 导出契约 ───────────────────────────
def test_detail_knobs_are_declared_only_where_the_section_is_produced() -> None:
    """五项口径 + 当前表只挂本命盘 / 重置盘 / 占星地图的输入模型（声明而不广告）；上游跳过的派生盘不挂（挂了就是死键）。"""
    for tool in ("chart", "relocation", "acg"):
        model = TOOL_DEFINITIONS[tool].input_model
        assert set(DETAIL_KEYS) <= set(model.model_fields), tool
        assert set(DETAIL_KEYS) <= advertise_hidden_fields(model), tool
        doc = western_options_doc(tool)
        assert set(DETAIL_KEYS) <= set(doc), tool
        assert all(f"{value}={label}" in doc["detailTable"] for value, label in vocab.CHART_DETAIL_TABLES)
    for tool in ("chart13", "chart12", "hellen_chart", "harmonic", "draconic", "mundane"):
        assert not set(DETAIL_KEYS) & set(TOOL_DEFINITIONS[tool].input_model.model_fields), tool
        assert not set(DETAIL_KEYS) & set(western_options_doc(tool)), tool
    assert CHART_DETAILS_TOOLS == CLASSICAL_ANALYSIS_TOOLS == frozenset({"chart", "relocation"})


def test_export_presets_register_the_section_where_upstream_does() -> None:
    """presets.js v61：astrochart 排在「古典·显赫计分」之后，astrochart_like / relocation / locastro(=acg) 排在「古典格局」之后；
    四个键同列可选段（后端失败只少这一段）。改黄道读数框架的派生盘键没有这一段。"""
    astro = AI_EXPORT_PRESET_SECTIONS["astrochart"]
    assert astro[astro.index("古典·显赫计分") + 1] == "盘面细节" and astro[astro.index("盘面细节") + 1] == "古典·世界范式盘"
    for key in ("astrochart_like", "relocation", "acg"):
        preset = AI_EXPORT_PRESET_SECTIONS[key]
        assert preset[preset.index("古典格局") + 1] == "盘面细节" and preset[preset.index("盘面细节") + 1] == "埃及历", key
    for key in ("astrochart", "astrochart_like", "relocation", "acg"):
        assert "盘面细节" in AI_EXPORT_OPTIONAL_SECTIONS[key], key
    for key in ("hellenastro", "dwadasamsa", "harmonic", "draconic", "mundane"):
        assert "盘面细节" not in AI_EXPORT_PRESET_SECTIONS[key], key
    assert "盘面细节" in SECTIONS_NOT_PRODUCED_BY_DESIGN["chart13"]


@needs_upstream("Horosa-Web/astrostudyui/src/utils/aiExport/presets.js", "Horosa-Web/astrostudyui/src/utils/aiExport/pipeline.js")
def test_section_placement_and_skip_table_track_upstream_source() -> None:
    presets = upstream_source(upstream_path("Horosa-Web/astrostudyui/src/utils/aiExport/presets.js"))
    union = presets[presets.index("AI_EXPORT_V61_SECTION_UNION = {"):]
    union = union[: union.index("};")]
    assert re.findall(r"(\w+): \['盘面细节'\]", union) == ["astrochart", "astrochart_like", "relocation", "locastro"]
    preset_table = presets[presets.index("export const AI_EXPORT_PRESET_SECTIONS = {"):]
    for upstream_key, skill_key in (("astrochart", "astrochart"), ("astrochart_like", "astrochart_like"), ("relocation", "relocation"), ("locastro", "acg")):
        row = re.search(rf"^\t{upstream_key}: \[(.*?)\],", preset_table, flags=re.M).group(1)
        titles = re.findall(r"'([^']+)'", row)
        mine = [t for t in AI_EXPORT_PRESET_SECTIONS[skill_key] if t in titles]   # skill 多出的段（月宿 / 占星地图明细）不比
        assert mine == [t for t in titles if t in AI_EXPORT_PRESET_SECTIONS[skill_key]], upstream_key
        assert "盘面细节" in titles
    pipeline = upstream_source(upstream_path("Horosa-Web/astrostudyui/src/utils/aiExport/pipeline.js"))
    assert "const CLASSICAL_SKIP_KEYS = ['hellenastro', 'dwadasamsa', 'harmonic', 'draconic', 'transformchart', 'zodiacsystems'];" in pipeline
    # 与 [古典格局] 同进同退，重置盘不再按本命出生地另补（两段随重置盘快照进正文）。
    assert "const derived = relocated ? [] : await Promise.all([fetchAstroClassicalAnalysisSectionForExport(), fetchChartDetailsSectionForExport()]);" in pipeline


# ─────────────────────────── service（离线，桩）：请求体 / 段位 / data / 技法卡 ───────────────────────────
def test_chart_request_body_section_position_and_data(tmp_path, monkeypatch) -> None:
    """缺省调用：请求体与起盘同形（不带任何口径键，= 上游「缺省不带任何参数」）、带盘时区的此刻、predictive=0；段排在
    「古典·显赫计分」之后；导出干净；data.chart_details 回显口径 + 缺省「当前表」topics；技法卡回显受孕期起算时刻。
    负向对照：把 enrich._attach_chart_details 里 `body.update(request_fields)` 之后的目标时刻块删掉 → targetDate 断言红；
    把 chart_family 里 [盘面细节] 的插入点挪到 [古典格局] 之后 → 段序断言红（都实跑过）。"""
    _freeze(monkeypatch, "+08:00", (2026, 11, 13, 9, 30, 15))
    client = CaptureClient()
    result = _service(tmp_path, client=client).run_tool("chart", BIRTH, save_result=False)
    assert result.ok and not [note for note in result.warnings if "盘面细节" in note or "chart details" in note]
    body = _calls(client, "/astroextra/chartdetails")
    assert len(body) == 1
    body = body[0]
    chart_body = _calls(client, "/chart")[0]
    for key in ("time", "zone", "lat", "lon", "hsys", "zodiacal", "ad", "gpsLat", "gpsLon", "tradition", "strongRecption"):
        assert body[key] == chart_body[key], key
    assert body["date"] == BIRTH["date"]   # /chart 的线上日期另被写成斜杠式（endpoints._java_chart_payload），astroextra 族照原样
    assert body["predictive"] == 0
    assert (body["targetDate"], body["targetTime"]) == ("2026/11/13", "09:30:15")
    assert not {"detailFaces", "variant", "lunarMethod", "mundoSystem", "midpointCoord", *DETAIL_KEYS, "defaults_accepted", "includePrimaryDirection"} & set(body)
    titles = _titles(result.data["snapshot_text"])
    assert titles[titles.index("古典·显赫计分") + 1] == "盘面细节"
    assert titles[titles.index("盘面细节") + 1: titles.index("盘面细节") + 3] == ["古典·世界范式盘", "古典格局"]
    assert _section(result.data["snapshot_text"], "盘面细节") == FX["texts"]["seattle-night"]
    export = result.data["export_snapshot"]
    assert export["unknown_detected_sections"] == [] and export["missing_selected_sections"] == []
    assert "盘面细节" in export["section_titles_detected"]
    details = result.data["chart_details"]
    assert details["settings"] == {name: vocab.CHART_DETAIL_DEFAULTS[name] for name in vocab.CHART_DETAIL_ECHO_PATHS}
    assert details["computed_at"] == {"lat": "31n14", "lon": "121e28"} and details["fertility_from"] == "2026-11-13 09:30:15"
    assert list(details["tables"]) == ["topics"] and details["tables"]["topics"]["data"] == FX["goldens"]["seattle-night"]["topics"]
    card = result.data["technique_card"]["settings"]
    assert card["detailFertilityFrom"]["value"] == "2026-11-13 09:30:15"
    assert not [key for key in card if key in vocab.CHART_DETAIL_ECHO_PATHS]   # 没给的口径不印（缺省）


def test_knobs_reach_the_request_and_are_echoed(tmp_path, monkeypatch) -> None:
    """「改这个参数，结果必须变」：五项口径（中文名也认）进请求体的上游键名、回显在 data 与技法卡；点名的表回带原值。
    负向对照：enrich 里把 `body.update(request_fields)` 注掉 → 请求体断言红 + 回显守卫报 tool.chart_details_setting_mismatch（实跑过）。"""
    _freeze(monkeypatch, "+08:00")
    client = CaptureClient()
    payload = {**BIRTH, "detailFaces": "元素面", "detailVariant": "经典", "detailLunar": "tithi", "detailMundo": "Koch",
               "detailMidpoint": "赤经", "detailTable": "寿主, stats"}
    result = _service(tmp_path, client=client).run_tool("chart", payload, save_result=False)
    assert result.ok, result.error
    body = _calls(client, "/astroextra/chartdetails")[0]
    assert {k: body.get(k) for k in ("detailFaces", "variant", "lunarMethod", "mundoSystem", "midpointCoord")} == {
        "detailFaces": "element", "variant": "classic", "lunarMethod": "tithi", "mundoSystem": "koch", "midpointCoord": "ra"}
    assert not set(DETAIL_KEYS[1:]) & set(body)
    assert not set(DETAIL_KEYS) & set(_calls(client, "/astroextra/analysis")[0])
    details = result.data["chart_details"]
    assert details["settings"] == {"detailFaces": "element", "detailVariant": "classic", "detailLunar": "tithi",
                                   "detailMundo": "koch", "detailMidpoint": "ra"}
    assert list(details["tables"]) == ["hyleg", "stats"]
    card = result.data["technique_card"]["settings"]
    assert {key: card[key]["text"] for key in vocab.CHART_DETAIL_ECHO_PATHS} == {
        "detailFaces": "元素面", "detailVariant": "经典", "detailLunar": "Tithi", "detailMundo": "Koch", "detailMidpoint": "赤经"}
    assert any("detailFaces" in note and "element" in note for note in result.warnings)   # 中文名 → 规范值的解读回显
    default = _service(tmp_path / "d").run_tool("chart", BIRTH, save_result=False)
    assert default.data["chart_details"]["settings"] != details["settings"]


@pytest.mark.parametrize("key,value", [("detailFaces", "egyptian"), ("detailVariant", "modern"), ("detailLunar", "lunar"),
                                       ("detailMundo", "whole"), ("detailMidpoint", "galactic"), ("detailTable", ["topics", "nope"])])
def test_unknown_knob_values_are_refused_at_the_schema(tmp_path, key, value) -> None:
    """后端对认不出的值静默回缺省 → 入口就拒（tool.invalid_option，options 是全表）。"""
    with pytest.raises(ToolValidationError) as excinfo:
        _service(tmp_path).run_tool("chart", {**BIRTH, key: value}, save_result=False)
    assert excinfo.value.code == "tool.invalid_option"
    assert key in str(excinfo.value)


def test_backend_silently_falling_back_to_a_default_is_an_error(tmp_path) -> None:
    """后端没按所给口径算（回显 ≠ 所求）→ tool.chart_details_setting_mismatch，不许带着「月亮日(传统)」冒充 Tithi。
    负向对照：把 enrich 里 `if not_applied:` 那个 raise 去掉 → 本用例拿到 ok=True（实跑过）。"""

    class DeafBackend(FakeClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            if endpoint == "/astroextra/chartdetails":
                return fake_chart_details_response({k: v for k, v in payload.items() if k != "lunarMethod"})
            return super().call(endpoint, payload)

    result = _service(tmp_path, client=DeafBackend()).run_tool("chart", {**BIRTH, "detailLunar": "tithi"}, save_result=False)
    assert result.ok is False and result.error.code == "tool.chart_details_setting_mismatch", result.error
    assert result.error.details["not_applied"] == [{"key": "detailLunar", "asked": "tithi", "applied": "traditional"}]


def test_request_fields_must_agree_with_the_upstream_mapping(tmp_path) -> None:
    """JS 用 vendored chartDetailRequestFields 重算的键与 Python 发出去的不一致 → tool.chart_details_request_mismatch。
    负向对照：把 enrich 里那条比较去掉 → ok=True（实跑过）。"""

    class DriftedJs(FakeJsClient):
        def run(self, tool_name: str, payload: dict) -> dict:
            out = super().run(tool_name, payload)
            if tool_name == "chart_details":
                out = {**out, "request_fields": {**out["request_fields"], "lunar": "tithi"}}
            return out

    result = _service(tmp_path, js_client=DriftedJs()).run_tool("chart", {**BIRTH, "detailLunar": "tithi"}, save_result=False)
    assert result.ok is False and result.error.code == "tool.chart_details_request_mismatch", result.error
    assert result.error.details["sent"] == {"lunarMethod": "tithi"}


@pytest.mark.parametrize("failure", ["transport", "empty"])
def test_backend_failure_only_drops_the_section_and_says_so(tmp_path, failure) -> None:
    """上游「盘面细节段失败不影响主体快照」：盘照出、这一段不出、warnings 说明；导出不报缺段（条件段双登记）。"""

    class Broken(FakeClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            if endpoint == "/astroextra/chartdetails":
                if failure == "transport":
                    raise ToolTransportError("boom", code="tool.backend_param_error", details={})
                return {"birth": "x"}   # 没有细节表（buildChartDetailsText 回空）
            return super().call(endpoint, payload)

    result = _service(tmp_path, client=Broken()).run_tool("chart", BIRTH, save_result=False)
    assert result.ok
    assert "盘面细节" not in _titles(result.data["snapshot_text"]) and "古典格局" in _titles(result.data["snapshot_text"])
    assert any("[盘面细节] 本次未产出" in note for note in result.warnings), result.warnings
    assert "chart_details" not in result.data
    assert result.data["export_snapshot"]["missing_selected_sections"] == []


def test_relocation_computes_both_derived_sections_at_the_relocated_place(tmp_path, monkeypatch) -> None:
    """上游 v3.14.0 AstroRelocationLab.relocParams：[盘面细节] / [古典格局] 的请求体 = 本命起盘参数 + 重置后的经纬（不带出生地的
    gps 坐标）。旧行为（v0.50.1）：[古典格局] 按出生地算。段序 = relocation preset（古典格局 → 盘面细节 → 埃及历）。
    负向对照：把 enrich._derived_section_params 改成原样返回 payload → lat/lon 断言红（实跑过）。"""
    _freeze(monkeypatch, "+08:00")
    client = CaptureClient()
    payload = {**BIRTH, "relocLat": "51n30", "relocLon": "0w07", "detailVariant": "classic"}
    result = _service(tmp_path, client=client).run_tool("relocation", payload, save_result=False)
    assert result.ok, result.error
    for endpoint in ("/astroextra/analysis", "/astroextra/chartdetails"):
        body = _calls(client, endpoint)[0]
        assert (body["lat"], body["lon"]) == ("51n30", "0w07"), endpoint
        assert (body["date"], body["time"], body["zone"]) == (BIRTH["date"], BIRTH["time"], BIRTH["zone"]), endpoint
        assert body.get("gpsLat") is None and body.get("gpsLon") is None and "relocLat" not in body, endpoint
    assert _calls(client, "/astroextra/chartdetails")[0]["variant"] == "classic"
    reloc_body = _calls(client, "/astroextra/relocation")[0]
    assert (reloc_body["lat"], reloc_body["relocLat"]) == ("31n14", "51n30") and not set(DETAIL_KEYS) & set(reloc_body)
    assert not set(DETAIL_KEYS) & set(_calls(client, "/chart")[0])   # 本命四角对比用的那张本命盘
    titles = _titles(result.data["snapshot_text"])
    assert titles[titles.index("古典格局") + 1] == "盘面细节" and titles[-1] == "重置盘"
    assert result.data["chart_details"]["computed_at"] == {"lat": "51n30", "lon": "0w07"}
    export = result.data["export_snapshot"]
    assert export["unknown_detected_sections"] == [] and export["missing_selected_sections"] == []


def test_relocation_falls_back_to_the_birthplace_when_no_new_place_is_given(tmp_path) -> None:
    """后端回显的 relocLat / relocLon 就是这张重置盘实际用的地点（缺省回退出生地）：两段跟着它走，不另猜。"""

    class EchoBirthplace(CaptureClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            out = super().call(endpoint, payload)
            if endpoint == "/astroextra/relocation":
                out = {**out, "relocLat": payload.get("relocLat") or payload["lat"], "relocLon": payload.get("relocLon") or payload["lon"]}
            return out

    client = EchoBirthplace()
    result = _service(tmp_path, client=client).run_tool("relocation", BIRTH, save_result=False)
    assert result.ok
    body = _calls(client, "/astroextra/chartdetails")[0]
    assert (body["lat"], body["lon"]) == ("31n14", "121e28")


def test_relocation_borrows_the_natal_planet_sign_judgements() -> None:
    """上游 withNatalPlanetSign：重置盘的 [可能性] 借本命的星座断语（只借 PlanetSign；重置盘自己有就不动；本命没有就不借）。"""
    natal = {"predict": {"PlanetSign": {"Sun": ["太阳金牛：稳重。"]}, "HouseLord": {"x": 1}}}
    borrowed = _with_natal_planet_sign({"chart": {"objects": []}}, natal)
    assert borrowed["predict"] == {"PlanetSign": {"Sun": ["太阳金牛：稳重。"]}}
    own = {"predict": {"PlanetSign": {"Moon": ["自己的"]}}}
    assert _with_natal_planet_sign(own, natal) is own
    bare = {"chart": {}}
    assert _with_natal_planet_sign(bare, {"chart": {}}) is bare and _with_natal_planet_sign(bare, None) is bare


def test_relocation_possibility_section_appears_when_the_natal_chart_carries_planet_sign(tmp_path) -> None:
    """整链：本命 /chart 回包带 predict.PlanetSign（Java 聚合层才补这个字段）→ 重置盘快照出 [可能性]。
    内置 runtime 的 /chart 走 Python chart 服务、不带 predict——此时无可借、段照旧不出（与本命盘工具同）。"""

    class Backend(FakeClient):
        """重置盘回包不带 predict（后端重置盘不跑推断）；本命 /chart 带不带由 natal_predict 定。"""

        natal_predict: dict | None = None

        def call(self, endpoint: str, payload: dict) -> dict:
            out = copy.deepcopy(super().call(endpoint, payload))
            if endpoint == "/astroextra/relocation":
                out["chart"].pop("predict", None)
            if endpoint == "/":
                out.pop("predict", None)
                if self.natal_predict is not None:
                    out["predict"] = self.natal_predict
            return out

    payload = {**BIRTH, "relocLat": "51n30", "relocLon": "0w07"}
    borrowing = Backend()
    borrowing.natal_predict = {"PlanetSign": {"Sun": ["太阳落金牛：重实际。"]}}
    with_predict = _service(tmp_path, client=borrowing).run_tool("relocation", payload, save_result=False)
    assert _section(with_predict.data["snapshot_text"], "可能性") == "[可能性]\n日\n太阳落金牛：重实际。"
    without = _service(tmp_path / "n", client=Backend()).run_tool("relocation", payload, save_result=False)
    assert "可能性" not in _titles(without.data["snapshot_text"])


def test_acg_carries_the_section_after_the_classical_analysis(tmp_path, monkeypatch) -> None:
    """占星地图（上游 locastro preset）：本命盘段里 [古典格局] 之后出 [盘面细节]；口径键不进 /chart 与 /location/acg。"""
    _freeze(monkeypatch, "+08:00")
    client = CaptureClient()
    result = _service(tmp_path, client=client).run_tool("acg", {**BIRTH, "detailMundo": "campanus"}, save_result=False)
    assert result.ok, result.error
    titles = _titles(result.data["snapshot_text"])
    assert titles[titles.index("古典格局") + 1] == "盘面细节" and "占星地图" in titles[titles.index("盘面细节"):]
    assert _calls(client, "/astroextra/chartdetails")[0]["mundoSystem"] == "campanus"
    for endpoint in ("/chart", "/location/acg"):
        assert not set(DETAIL_KEYS) & set(_calls(client, endpoint)[0]), endpoint
    assert result.data["chart_details"]["settings"]["detailMundo"] == "campanus"
    assert result.data["technique_card"]["settings"]["detailFertilityFrom"]["value"] == "2026-01-01 12:00:00"
    export = result.data["export_snapshot"]
    assert export["unknown_detected_sections"] == [] and export["missing_selected_sections"] == []


@pytest.mark.parametrize("tool", ["chart13", "chart12", "hellen_chart", "harmonic", "draconic"])
def test_derived_charts_do_not_fetch_or_print_the_section(tmp_path, tool) -> None:
    """上游 pipeline.js CLASSICAL_SKIP_KEYS：后端按本命参数、回归黄道算，挂到改黄道读数框架的派生盘上就是本命结论冒充派生盘结论。"""
    client = CaptureClient()
    result = _service(tmp_path, client=client).run_tool(tool, BIRTH, save_result=False)
    assert result.ok, result.error
    assert _calls(client, "/astroextra/chartdetails") == []
    assert "盘面细节" not in _titles(result.data["snapshot_text"]) and "chart_details" not in result.data


@requires_node
def test_real_js_pipeline_prints_the_golden_text_for_the_golden_response(tmp_path, monkeypatch) -> None:
    """真 JS 工具 + 回上游金标的后端桩：整段正文 == 夹具正文（五项口径全非缺省的那张盘），请求体键过了 vendored 映射的对拍。"""
    _freeze(monkeypatch, "+09:00")

    class GoldenBackend(CaptureClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            if endpoint == "/astroextra/chartdetails":
                self.calls.append((endpoint, dict(payload)))
                return copy.deepcopy(FX["goldens"]["tokyo-classic"])
            return super().call(endpoint, payload)

    class RealChartDetails(FakeJsClient):
        def __init__(self, real: HorosaJsEngineClient) -> None:
            super().__init__()
            self.real = real

        def run(self, tool_name: str, payload: dict) -> dict:
            return self.real.run(tool_name, payload) if tool_name == "chart_details" else super().run(tool_name, payload)

    client = GoldenBackend()
    js = RealChartDetails(HorosaJsEngineClient(_settings(tmp_path / "js")))
    result = _service(tmp_path, client=client, js_client=js).run_tool("chart", _skill_payload("tokyo-classic", detailTable=ALL_TABLES), save_result=False)
    assert result.ok, result.error
    assert _section(result.data["snapshot_text"], "盘面细节") == FX["texts"]["tokyo-classic"]
    sent = _calls(client, "/astroextra/chartdetails")[0]
    for key, value in FX["requests"]["tokyo-classic"].items():
        assert sent[key] == (value.replace("/", "-") if key == "date" else value), key
    tables = result.data["chart_details"]["tables"]
    assert list(tables) == ALL_TABLES
    assert {name: row["label"] for name, row in tables.items()} == dict(vocab.CHART_DETAIL_TABLES)
    assert all(tables[name]["data"] == FX["goldens"]["tokyo-classic"][name] for name in ALL_TABLES)


# ─────────────────────────── live：skill 工具 == 上游全表金标 ───────────────────────────
@requires_chart
@pytest.mark.parametrize("case", sorted(FX["goldens"]))
def test_live_chart_details_equal_the_upstream_goldens(case: str, tmp_path, monkeypatch) -> None:
    """共享 v3.14.0 引擎：skill 的本命盘工具按上游测试的同一张盘、同一组口径、同一个目标时刻（2026-01-01 12:00 盘时区）
    取 30 张表 == 上游金标逐值，[盘面细节] 整段 == 夹具正文。
    负向对照（实跑过）：请求体里把 hsys 丢掉 → inMundo / degrees 等表红；把 lunarMethod 键名写错 → sydney / tokyo 两张盘
    报 tool.chart_details_request_mismatch；不发 targetDate → fertility 表与「受孕期」行红。"""
    _freeze(monkeypatch, FX["requests"][case]["zone"])
    result = make_service(tmp_path).run_tool("chart", _skill_payload(case, detailTable=ALL_TABLES), save_result=False)
    assert result.ok, result.error
    details = result.data["chart_details"]
    golden = FX["goldens"][case]
    # 金标在 macOS 录：POSIX 逐值（容差 1e-7）、Windows 比形状与去数字的行（tests/float_tree.py 写明为什么）。
    differing = {name: diff for name in ALL_TABLES if (diff := golden_diff(json.loads(json.dumps(details["tables"][name]["data"])), golden[name]))}
    assert differing == {}
    assert golden_text_diff(_section(result.data["snapshot_text"], "盘面细节"), FX["texts"][case]) == []
    assert details["fertility_from"] == "2026-01-01 12:00:00"
    assert details["settings"]["detailVariant"] == golden["variant"] and details["settings"]["detailLunar"] == golden["lunarDays"]["method"]
    export = result.data["export_snapshot"]
    assert export["unknown_detected_sections"] == [] and export["missing_selected_sections"] == []


@requires_chart
def test_live_relocation_details_and_classical_analysis_follow_the_new_place(tmp_path, monkeypatch) -> None:
    """重置盘 live：出生地随便放在别处、重置到东京 → [盘面细节] 的 30 张表 == 上游「东京」金标（同一出生时刻、东京的经纬）；
    [古典格局] 的分析 == 直接在东京起本命盘的那份，≠ 按出生地算的那份（v0.50.1 的旧行为）。"""
    case = "tokyo-classic"
    _freeze(monkeypatch, FX["requests"][case]["zone"])
    at_place = {k: v for k, v in _skill_payload(case, detailTable=ALL_TABLES).items() if k not in ("gpsLat", "gpsLon")}
    service = make_service(tmp_path)
    reloc = service.run_tool("relocation", {**at_place, "lat": "10s00", "lon": "20w00", "relocLat": at_place["lat"], "relocLon": at_place["lon"]}, save_result=False)
    assert reloc.ok, reloc.error
    tables = reloc.data["chart_details"]["tables"]
    assert {name: diff for name in ALL_TABLES if (diff := golden_diff(json.loads(json.dumps(tables[name]["data"])), FX["goldens"][case][name]))} == {}
    assert golden_text_diff(_section(reloc.data["snapshot_text"], "盘面细节"), FX["texts"][case]) == []
    assert reloc.data["chart_details"]["computed_at"] == {"lat": at_place["lat"], "lon": at_place["lon"]}
    natal_there = service.run_tool("chart", at_place, save_result=False)
    natal_birthplace = service.run_tool("chart", {**at_place, "lat": "10s00", "lon": "20w00"}, save_result=False)
    assert reloc.data["_classicalAnalysis"] == natal_there.data["_classicalAnalysis"]
    assert reloc.data["_classicalAnalysis"] != natal_birthplace.data["_classicalAnalysis"]
    assert _section(reloc.data["snapshot_text"], "古典格局") == _section(natal_there.data["snapshot_text"], "古典格局")
    titles = _titles(reloc.data["snapshot_text"])
    assert titles[titles.index("古典格局") + 1] == "盘面细节"


@requires_chart
def test_live_acg_prints_the_same_section_as_the_natal_chart(tmp_path, monkeypatch) -> None:
    case = "sydney"
    _freeze(monkeypatch, FX["requests"][case]["zone"])
    result = make_service(tmp_path).run_tool("acg", _skill_payload(case), save_result=False)
    assert result.ok, result.error
    assert _section(result.data["snapshot_text"], "盘面细节") == FX["texts"][case]
    assert result.data["chart_details"]["tables"]["topics"]["data"] == FX["goldens"][case]["topics"]


def test_fixture_keeps_the_backend_key_order() -> None:
    """夹具可重建（gzip mtime=0、无文件名），且**不排序键**：[盘面细节] 的「统计」行按后端回包里的键序列出各项
    （`Object.keys(d.stats[group])`），夹具若 sort_keys 就不再是后端的那份回包（第一版夹具这么存，统计行对不上）。"""
    raw = FIXTURE_PATH.read_bytes()
    assert raw[:4] == b"\x1f\x8b\x08\x00" and raw[4:8] == b"\x00\x00\x00\x00"   # 无 FNAME、mtime 0
    data = json.loads(gzip.decompress(raw).decode("utf-8"))
    assert json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8") == gzip.decompress(raw)
    assert list(data["goldens"]["seattle-night"]["stats"]["element"]) != sorted(data["goldens"]["seattle-night"]["stats"]["element"])


def test_js_layer_rejecting_a_setting_is_reported_not_swallowed(tmp_path) -> None:
    """第二道闸：schema 放行、而 vendored 上游口径词表（chart_details JS 工具）判无效 → tool.chart_details_invalid_setting，
    不许带着缺省口径出 [盘面细节]。负向对照：enrich.py 里 `if js.get("invalid")` 分支删掉 → 本用例红（得到 ok=True）。"""

    class RejectingJs(DerivedJs):
        def run(self, tool_name: str, payload: dict) -> dict:
            if tool_name == "chart_details":
                return {"invalid": [{"key": "detailFaces", "value": "chaldean", "allowed": ["element"]}]}
            return super().run(tool_name, payload)

    result = _service(tmp_path, js_client=RejectingJs()).run_tool("chart", BIRTH, save_result=False)
    assert result.ok is False and result.error.code == "tool.chart_details_invalid_setting", result.error
    assert result.error.details["invalid"][0]["key"] == "detailFaces"
