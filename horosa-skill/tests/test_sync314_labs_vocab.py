"""上游 v3.14.0（Horosa-Public e55c3a66）辅盘「变换盘」「黄道制」：词表、入参、路由、导出登记。

权威：
- 选项的唯一来源是上游 `utils/transformCharts.js`（TRANSFORM_GROUPS / TRANSFORM_PLANETS / TRANSFORM_HOUSES /
  TRANSFORM_PAGE_SETTINGS / ZODIAC_VERSIONS / ZODIAC_PAGE_SETTINGS），本仓逐字 vendor（vendor_manifest.json 看守）。
  Python 侧 `auxlab_vocab.py` 抄了值、中文名与「哪种变换用到哪些选项」，这里在 node 里把 vendored 表导出来逐项比。
- 请求体只带这种变换用到的选项：上游 `utils/aiAnalysisContext/derivedLabsHeadless.js` transformRequestOptions（同样 vendored）。
- 段表 / 键表：上游 `utils/aiExport/presets.js`、`pipeline.js`（有上游 checkout 时逐项核）。
"""
from __future__ import annotations

from skips import upstream_source  # 上游拆文件后读「门面 + 子模块」全集（v3.15.0）
import json
import re
from pathlib import Path

import pytest
from node_esm import run_node_esm
from skips import needs_upstream, upstream_path

from horosa_skill import auxlab_vocab as V
from horosa_skill.agent_guidance import build_agent_guidance, validate_agent_preflight
from horosa_skill.engine.registry import (
    ASTRO_CHART_FAMILY_TOOLS,
    CLASSICAL_ANALYSIS_TOOLS,
    TOOL_DEFINITIONS,
)
from horosa_skill.engine.router import route
from horosa_skill.exports.registry import (
    AI_EXPORT_OPTIONAL_SECTIONS,
    AI_EXPORT_PLANET_INFO_TECHNIQUES,
    AI_EXPORT_PRESET_SECTIONS,
    AI_EXPORT_SECTION_MIGRATION_KEYS,
    AI_EXPORT_TECHNIQUES,
)
from horosa_skill.schemas.tools import (
    DispatchInput,
    TransformChartInput,
    ZodiacSystemsInput,
)
from horosa_skill.service.endpoints import _PYTHON_CHART_ENDPOINTS
from horosa_skill.surfaces.mcp_schema import advertised_technique_schema

_CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
_BIRTH = {"date": "1990-05-15", "time": "14:30:00", "zone": "+08:00", "lat": "31n14", "lon": "121e28"}
_PRESETS_JS = "Horosa-Web/astrostudyui/src/utils/aiExport/presets.js"
_PIPELINE_JS = "Horosa-Web/astrostudyui/src/utils/aiExport/pipeline.js"
_JAVA = "Horosa-Web/astrostudysrv/astrostudy/src/main/java/spacex/astrostudy/controller/AstroExtraController.java"
_ENGINE_PY = "Horosa-Web/astropy/astrostudy/transform_charts.py"
_ZODIAC_DATA_PY = "Horosa-Web/astropy/astrostudy/zodiac_data.py"


def _vendored() -> dict:
    return json.loads(run_node_esm(
        "import * as T from './src/vendor/utils/transformCharts.js';"
        "import * as A from './src/constants/AstroText.js';"
        "console.log(JSON.stringify({"
        " groups: T.TRANSFORM_GROUPS.map(g => [g.label, g.kinds.map(k => [k.value, k.label, k.options || []])]),"
        " kinds: T.TRANSFORM_KINDS, planets: T.TRANSFORM_PLANETS, houses: T.TRANSFORM_HOUSES,"
        " planetNames: Object.fromEntries(T.TRANSFORM_PLANETS.map(id => [id, A.AstroMsgCN[id]])),"
        " defaults: T.TRANSFORM_PAGE_SETTINGS.defaults(), variants: T.TRANSFORM_PAGE_SETTINGS.schema.variant.oneOf,"
        " zodiac: T.ZODIAC_VERSIONS.map(v => [v.value, v.label]), zodiacDefault: T.ZODIAC_PAGE_SETTINGS.defaults().version}))",
        cwd=_CORE_JS, timeout=60,
    ))


# ─────────────────────────── 词表与 vendored 上游表互锚 ───────────────────────────


def test_python_tables_equal_the_vendored_upstream_tables() -> None:
    js = _vendored()
    assert [[group, [[value, label, list(opts)] for value, label, opts in kinds]] for group, kinds in V.TRANSFORM_GROUPS] == js["groups"]
    assert list(V.TRANSFORM_KINDS) == js["kinds"] and len(V.TRANSFORM_KINDS) == 33
    assert list(V.TRANSFORM_PLANETS) == js["planets"]
    assert V.TRANSFORM_PLANET_LABELS == js["planetNames"]
    assert list(V.TRANSFORM_HOUSES) == js["houses"]
    assert list(V.TRANSFORM_VARIANT_LABELS) == js["variants"]
    assert {key: js["defaults"][key] for key in V.TRANSFORM_DEFAULTS} == V.TRANSFORM_DEFAULTS
    assert [list(pair) for pair in V.ZODIAC_VERSIONS] == js["zodiac"] and len(V.ZODIAC_VERSIONS) == 19
    assert V.ZODIAC_VERSION_DEFAULT == js["zodiacDefault"] == "z13a"


def test_request_fields_equal_the_vendored_upstream_function_for_every_kind() -> None:
    """transform_request_fields（Python 发的）== 上游 transformRequestOptions（vendored）：33 种 × 两组设置逐键比。"""
    cases = [
        {"kind": kind, "planet": planet, "shift": shift, "house": house, "variant": variant}
        for kind in V.TRANSFORM_KINDS
        for planet, shift, house, variant in (("Moon", False, 1, "improved"), ("Saturn", True, 7, "classic"))
    ]
    js = json.loads(run_node_esm(
        "import { transformKindDef } from './src/vendor/utils/transformCharts.js';"
        "import { transformRequestOptions } from './src/vendor/utils/aiAnalysisContext/derivedLabsHeadless.js';"
        "const cases = JSON.parse(process.argv[1]);"
        "console.log(JSON.stringify(cases.map(s => transformRequestOptions(s, transformKindDef(s.kind)))))",
        json.dumps(cases), cwd=_CORE_JS, timeout=60,
    ))
    assert [V.transform_request_fields(case) for case in cases] == js
    # 手算三例（上游 derivedLabsHeadless.test.js 的期望）：
    assert V.transform_request_fields({"kind": "superimposed", "planet": "Moon", "shift": True, "house": 4, "variant": "classic"}) == {
        "transformKind": "superimposed", "transformPlanet": "Moon", "transformShift": 1}
    assert V.transform_request_fields({"kind": "inverted", "planet": "Moon", "shift": True, "house": 4, "variant": "classic"}) == {
        "transformKind": "inverted", "transformVariant": "classic"}
    assert V.transform_request_fields({"kind": "antiscia", "planet": "Moon", "shift": True, "house": 4, "variant": "classic"}) == {"transformKind": "antiscia"}


@needs_upstream(_ENGINE_PY, _ZODIAC_DATA_PY, _JAVA)
def test_every_kind_and_version_is_known_to_the_upstream_backend() -> None:
    """后端认不出的种类 / 版本会静默退回缺省（transform_charts.build_transform_chart / zodiac_systems.build_zodiac_systems）：
    词表里的每一项都要是后端真认识的；请求键都在 Java 白名单里（漏登记会被静默丢弃）。"""
    engine = upstream_source(upstream_path(_ENGINE_PY))
    for kind in V.TRANSFORM_KINDS:
        assert re.search(rf"['\"]{kind}['\"]", engine), kind
    zodiac = upstream_source(upstream_path(_ZODIAC_DATA_PY))
    rows = [m.groups() for m in re.finditer(r"^ {4}'([^']+)': \{'label': '([^']+)'", zodiac, re.MULTILINE)]
    assert sorted(rows) == sorted(V.ZODIAC_VERSIONS)
    java = upstream_source(upstream_path(_JAVA))
    for field in (*V.TRANSFORM_FIELD_TO_SETTING, "zodiacVersion"):
        assert f'"{field}"' in java, field


# ─────────────────────────── 入参校验：认不出即拒，不落缺省 ───────────────────────────


def test_transform_inputs_read_names_and_refuse_unknown_values() -> None:
    model = TransformChartInput(**_BIRTH, transformKind="叠置盘", transformPlanet="月亮", transformShift="1", transformHouse="3", transformVariant="经典")
    assert (model.transformKind, model.transformPlanet, model.transformShift, model.transformHouse, model.transformVariant) == (
        "superimposed", "Moon", True, 3, "classic")
    assert TransformChartInput(**_BIRTH, transformKind="地理盘 · 经度作中天赤经").transformKind == "geodeticLong"
    assert TransformChartInput(**_BIRTH).transformKind is None  # 缺省由 runner 按上游页面缺省补，不在模型里冒充显式值
    for bad in ({"transformKind": "nope"}, {"transformPlanet": "Chiron"}, {"transformHouse": 13}, {"transformHouse": 0},
                {"transformVariant": "modern"}, {"transformShift": 2}):
        with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError（逐字段结构化错误由 run_tool 还原，见 service 用例）
            TransformChartInput(**_BIRTH, **bad)


def test_zodiac_version_reads_names_and_refuses_unknown_values() -> None:
    assert ZodiacSystemsInput(**_BIRTH, zodiacVersion="十四星座 · 等分").zodiacVersion == "z14"
    assert ZodiacSystemsInput(**_BIRTH, zodiacVersion="Z12F").zodiacVersion == "z12f"
    assert ZodiacSystemsInput(**_BIRTH).zodiacVersion is None
    with pytest.raises(Exception):  # noqa: B017
        ZodiacSystemsInput(**_BIRTH, zodiacVersion="z99")


def test_transform_field_applies_follows_the_kind() -> None:
    assert V.transform_field_applies({"transformKind": "epoch"}, "transformHouse") is True
    assert V.transform_field_applies({"transformKind": "epoch"}, "transformPlanet") is False
    assert V.transform_field_applies({}, "transformVariant") is True          # 缺省 inverted 用口径
    assert V.transform_field_applies({}, "transformHouse") is False
    assert V.transform_field_applies({"transformKind": "antiscia"}, "transformKind") is True


# ─────────────────────────── 广告层 / guidance / 闸门 ───────────────────────────


def test_advertised_layer_carries_the_selector_and_hides_the_option_knobs() -> None:
    for tool, selector, hidden in (
        ("transformchart", "transformKind", ("transformPlanet", "transformShift", "transformHouse", "transformVariant", "lifespanMethod")),
        ("zodiacsystems", "zodiacVersion", V.ZODIAC_UNUSED_CHART_KEYS),
    ):
        model = TOOL_DEFINITIONS[tool].input_model
        props = advertised_technique_schema(tool, model.model_json_schema())["properties"]
        assert selector in props, tool
        for key in hidden:
            assert key not in props, (tool, key)
            assert key in model.model_fields, (tool, key)   # 声明着：校验层照收
        assert {"date", "time", "zone", "lat", "lon"} <= set(props)


def test_guidance_documents_every_kind_version_and_hidden_knob() -> None:
    doc = build_agent_guidance(tool_name="transformchart")["tools"]["transformchart"]["options_keys"]
    for kind, label in V.TRANSFORM_KIND_LABELS.items():
        assert f"{kind}={label}" in doc["transformKind"], kind
    assert "superimposed=叠置盘[transformPlanet+transformShift]" in doc["transformKind"]
    assert "epoch=受孕盘[transformHouse]" in doc["transformKind"]
    for key in ("transformPlanet", "transformShift", "transformHouse", "transformVariant", "lifespanMethod"):
        assert doc.get(key), key
    zdoc = build_agent_guidance(tool_name="zodiacsystems")["tools"]["zodiacsystems"]["options_keys"]
    for value, label in V.ZODIAC_VERSIONS:
        assert f"{value}={label}" in zdoc["zodiacVersion"], value
    for key in V.ZODIAC_UNUSED_CHART_KEYS:
        assert zdoc[key].startswith("不改结果"), key


def test_gate_asks_which_transform_and_which_version() -> None:
    blocked = validate_agent_preflight("transformchart", dict(_BIRTH))
    assert blocked["ok"] is False
    assert blocked["code"] == "agent_guidance.required"
    assert [item["field"] for item in blocked["ask_if_missing"]] == ["transformKind"]
    assert blocked["ask_if_missing"][0]["options_count"] == 33   # 长表不逐条念给用户；全表在 guidance
    assert validate_agent_preflight("transformchart", {**_BIRTH, "transformKind": "novien"})["ok"] is True
    assert validate_agent_preflight("transformchart", {**_BIRTH, "defaults_accepted": True})["ok"] is True
    blocked = validate_agent_preflight("zodiacsystems", dict(_BIRTH))
    assert [item["field"] for item in blocked["ask_if_missing"]] == ["zodiacVersion"]
    assert validate_agent_preflight("zodiacsystems", {**_BIRTH, "zodiacVersion": "z14"})["ok"] is True


# ─────────────────────────── 路由 ───────────────────────────


@pytest.mark.parametrize(("query", "tool"), [
    ("给我排一张变换盘", "transformchart"), ("看看我的日心盘", "transformchart"), ("受孕盘", "transformchart"),
    ("antiscia chart for my birth", "transformchart"), ("transform chart", "transformchart"),
    ("黄道制看一下", "zodiacsystems"), ("十三星座里我是什么座", "zodiacsystems"), ("我是蛇夫座吗", "zodiacsystems"),
    ("13-sign zodiac placement", "zodiacsystems"), ("am I an ophiuchus", "zodiacsystems"),
])
def test_router_picks_the_new_tools(query: str, tool: str) -> None:
    assert route(DispatchInput(query=query)).tools == [tool]


@pytest.mark.parametrize("query", ["九分盘", "本月上旬盘点", "龙盘", "十三宫", "这个地理盘点一下"])
def test_router_does_not_take_ambiguous_names(query: str) -> None:
    """「九分盘」是印占 D9 的通称；「旬盘」「地理盘」后面接「点」就是日常话——都不拿来选变换盘。"""
    try:
        tools = route(DispatchInput(query=query)).tools
    except Exception:  # noqa: BLE001 - 未命中 / 需选择都算「没选变换盘」
        tools = []
    assert "transformchart" not in tools and "zodiacsystems" not in tools


# ─────────────────────────── 导出登记 / 家族集合 ───────────────────────────


def test_export_registration_matches_the_upstream_presets() -> None:
    upstream_transform = ["起盘信息", "宫位宫头", "星与虚点", "信息", "相位", "行星", "希腊点", "12分度", "主宰星链", "分宫制宫神星表", "古典", "埃及历", "寿命格局", "变换盘"]
    preset = AI_EXPORT_PRESET_SECTIONS["transformchart"]
    assert [title for title in preset if title != "月宿"] == upstream_transform   # 月宿 = 同族 skill 既有 extra（恒星黄道盘才有）
    assert "可能性" not in preset and "古典格局" not in preset
    assert AI_EXPORT_PRESET_SECTIONS["zodiacsystems"] == ["黄道制"]
    assert "变换盘" not in AI_EXPORT_OPTIONAL_SECTIONS["transformchart"]            # 专属段必出
    assert "zodiacsystems" not in AI_EXPORT_OPTIONAL_SECTIONS
    labels = {item["key"]: item["label"] for item in AI_EXPORT_TECHNIQUES}
    assert labels["transformchart"] == "变换盘" and labels["zodiacsystems"] == "黄道制"
    assert {"transformchart", "zodiacsystems"} <= set(AI_EXPORT_SECTION_MIGRATION_KEYS)
    assert "transformchart" in AI_EXPORT_PLANET_INFO_TECHNIQUES and "zodiacsystems" not in AI_EXPORT_PLANET_INFO_TECHNIQUES


def test_family_sets_and_endpoints() -> None:
    assert "transformchart" in ASTRO_CHART_FAMILY_TOOLS and "zodiacsystems" not in ASTRO_CHART_FAMILY_TOOLS
    # 上游 pipeline.js CLASSICAL_SKIP_KEYS 含这两键：本命口径的 /astroextra/analysis 不挂（不让本命结论冒充变换盘结论）。
    assert not {"transformchart", "zodiacsystems"} & CLASSICAL_ANALYSIS_TOOLS
    assert {"/astroextra/transformchart", "/astroextra/zodiacsystems"} <= _PYTHON_CHART_ENDPOINTS
    for tool in ("transformchart", "zodiacsystems"):
        definition = TOOL_DEFINITIONS[tool]
        assert definition.execution == "local" and definition.domain == "astro" and definition.mcp_name == f"horosa_astro_{tool}"


@needs_upstream(_PRESETS_JS, _PIPELINE_JS)
def test_upstream_key_sets_carry_both_keys_the_way_the_skill_mirrors_them() -> None:
    presets = upstream_source(upstream_path(_PRESETS_JS))

    def js_list(name: str) -> list[str]:
        body = re.search(rf"{name} = (?:new Set\()?\[(.*?)\]", presets, re.DOTALL).group(1)
        return re.findall(r"'([^']+)'", re.sub(r"//[^\n]*", "", body))

    assert {"transformchart", "zodiacsystems"} <= set(js_list("ASTRO_LIKE_EXPORT_KEYS"))
    assert {"transformchart", "zodiacsystems"} <= set(js_list("DERIVED_ASTRO_MODULE_KEYS"))
    assert js_list("DERIVED_ASTRO_NO_NATAL_FALLBACK_KEYS") == ["transformchart", "zodiacsystems"]
    planet_info = js_list("export const AI_EXPORT_PLANET_INFO_TECHNIQUES")
    assert "transformchart" in planet_info and "zodiacsystems" not in planet_info
    transform = re.search(r"^\ttransformchart: \[(.*?)\],$", presets, re.MULTILINE).group(1)
    assert re.findall(r"'([^']+)'", transform) == [t for t in AI_EXPORT_PRESET_SECTIONS["transformchart"] if t != "月宿"]
    assert re.search(r"^\tzodiacsystems: \['黄道制'\],$", presets, re.MULTILINE)
    pipeline = upstream_source(upstream_path(_PIPELINE_JS))
    skip = re.search(r"CLASSICAL_SKIP_KEYS = \[(.*?)\]", pipeline).group(1)
    assert {"transformchart", "zodiacsystems"} <= set(re.findall(r"'([^']+)'", skip))
