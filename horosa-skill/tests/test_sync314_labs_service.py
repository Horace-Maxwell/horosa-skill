"""上游 v3.14.0 辅盘「变换盘」「黄道制」：工具端到端（离线）。

后端结果 = 共享 vendored v3.14.0 引擎实抓（fixtures/sync314_labs_live.json.gz；与上游后端金标逐值相同，见
test_sync314_labs_goldens.py），JS = 真 node 引擎（vendored 上游 transformCharts.js / astroextra / 埃及历），
整盘通用段 = engine/astro_snapshot.py。上游无头路径：utils/aiAnalysisContext/derivedLabsHeadless.js。
"""
from __future__ import annotations

import gzip
import json
from functools import cache
from pathlib import Path

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill import auxlab_vocab as V
from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.errors import ToolValidationError
from horosa_skill.exports.registry import (
    AI_EXPORT_OPTIONAL_SECTIONS,
    AI_EXPORT_PRESET_SECTIONS,
)
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.runners import auxlabs

_FIXTURES = Path(__file__).parent / "fixtures"
TRANSFORM = "/astroextra/transformchart"
ZODIAC = "/astroextra/zodiacsystems"


@cache
def live() -> dict:
    return json.loads(gzip.decompress((_FIXTURES / "sync314_labs_live.json.gz").read_bytes()).decode("utf-8"))


@cache
def golden() -> dict:
    return json.loads((_FIXTURES / "sync314_labs_upstream_golden.json").read_text(encoding="utf-8"))


def birth(**extra: object) -> dict:
    return {**live()["birth"], "agent_confirmed_settings": True, **extra}


class RecordingClient(FakeClient):
    def __init__(self, overrides: dict | None = None) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []
        self.overrides = overrides or {}

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        if endpoint in self.overrides:
            value = self.overrides[endpoint]
            return json.loads(json.dumps(value(payload) if callable(value) else value))
        return super().call(endpoint, payload)

    def sent(self, endpoint: str) -> list[dict]:
        return [payload for called, payload in self.calls if called == endpoint]


def _settings(tmp_path: Path) -> Settings:
    return Settings(server_root="http://127.0.0.1:9", runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")


def _service(tmp_path: Path, client: FakeClient, *, real_js: bool = True) -> HorosaSkillService:
    settings = _settings(tmp_path)
    js = HorosaJsEngineClient(settings) if real_js else FakeJsClient()
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=js)


def _full(key: str):
    """重放某一种变换的整份实抓回包；请求的种类对不上就报错（免得用例把别的盘当成所要的那张）。"""
    response = live()["transform_full"][key]

    def reply(payload: dict) -> dict:
        assert payload.get("transformKind") == key.split("/")[0], payload.get("transformKind")
        return response

    return reply


def _sections(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for block in text.split("\n\n["):
        head, _, body = block.lstrip("[").partition("]\n")
        out[head] = body
    return out


def _export(result) -> dict:
    return result.data["export_snapshot"]


# ─────────────────────────── 变换盘 ───────────────────────────


def test_transformchart_novien_end_to_end(tmp_path: Path) -> None:
    client = RecordingClient({TRANSFORM: _full("novien/improved")})
    result = _service(tmp_path, client).run_tool("transformchart", birth(transformKind="九分盘"), save_result=False)
    assert result.ok is True, result.error
    export = _export(result)
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []
    sections = _sections(result.data["snapshot_text"])
    preset = AI_EXPORT_PRESET_SECTIONS["transformchart"]
    assert list(sections) == [title for title in preset if title in sections]            # 段序 = preset 序
    assert set(preset) - set(sections) <= set(AI_EXPORT_OPTIONAL_SECTIONS["transformchart"])
    assert "可能性" not in sections and "古典格局" not in sections
    # 请求体：本命盘参数（tradition / predictive 恒 false）+ 只带九分盘用到的口径；别的专属键一个不带。
    (sent,) = client.sent(TRANSFORM)
    assert {k: v for k, v in sent.items() if k.startswith("transform")} == {"transformKind": "novien", "transformVariant": "improved"}
    assert sent["tradition"] is False and sent["predictive"] is False and sent["hsys"] == 1 and sent["date"] == "1975-02-10"
    # 这两页没有本命回落、不挂本命口径的派生分析：不另取本命盘，不打 /astroextra/analysis。
    assert [endpoint for endpoint, _ in client.calls] == [TRANSFORM]
    # 九分盘是等宫但宫头不对齐星座：标注说真话、宫主表不按整宫折叠（上游 wholeSignRulers.js v3.14.0）。
    assert "回归黄道，等宫(变换后)" in sections["起盘信息"].splitlines()
    assert "当前分宫制即整宫制" not in sections["分宫制宫神星表"]
    # [变换盘]：九分盘 = 黄经 × 9 − 90°（手算：太阳 321.850440 × 9 − 90 ≡ 286.653960；月亮 321.836467 × 9 − 90 ≡ 286.528203），
    # 与上游金标的 286.653960 / 286.528199 相符（本命黄经取倒置盘金标 − 180°）。
    lines = sections["变换盘"].splitlines()
    assert lines[0].startswith("变换:九分盘。黄经 × 9 − 90°;") and lines[1] == "口径:改进"
    assert "太阳:本命黄经 321.85° → 286.65°" in lines and "月亮:本命黄经 321.84° → 286.53°" in lines
    assert "这张盘的黄经是换算出来的量,赤经赤纬、方位高度、出界和赤纬平行仍按星体本来的位置。" in lines
    # 结构化数据
    data = result.data
    assert data["transform"]["kind"] == "novien" and data["transform"]["label"] == "九分盘" and data["transform"]["options_used"] == ["variant"]
    assert data["settings"] == {"kind": "novien", "planet": "Moon", "shift": False, "house": 1, "variant": "improved"}
    assert data["request"] == {"transformKind": "novien", "transformVariant": "improved"}
    assert [[row["id"], round(row["lon"], 6)] for row in data["positions"]] == golden()["transform_full_B"]["novien/improved"]["positions"]
    assert data["params_ignored"] == [] and not any("用不上" in warning for warning in result.warnings)
    assert "_derivedSelf" not in json.dumps(export, ensure_ascii=False)


def test_transformchart_node_houses_text_uses_the_true_cusps(tmp_path: Path) -> None:
    client = RecordingClient({TRANSFORM: _full("nodeHouses/improved")})
    result = _service(tmp_path, client).run_tool("transformchart", birth(transformKind="nodeHouses"), save_result=False)
    assert result.ok is True, result.error
    north_node = dict(golden()["transform_full_B"]["nodeHouses/improved"]["positions"])["North Node"]   # 246.414151 = 射手 6°24′
    assert round(north_node, 6) == 246.414151
    houses = {house["id"]: house for house in result.data["chart"]["houses"]}
    assert houses["House1"]["lon"] == pytest.approx(north_node, abs=1e-6) and houses["House1"]["sign"] == "Sagittarius"
    assert houses["House2"]["lon"] == pytest.approx(north_node - 30.0, abs=1e-6) and houses["House2"]["sign"] == "Scorpio"
    # 盘面画的「段头」原样留在 raw（画盘用）：比真宫头少 30°。
    raw = {house["id"]: house for house in result.data["raw"]["chart"]["chart"]["houses"]}
    assert raw["House1"]["lon"] == pytest.approx(north_node - 30.0, abs=1e-6) and raw["House1"]["sign"] == "Scorpio"
    cusps = _sections(result.data["snapshot_text"])["宫位宫头"].splitlines()
    assert any(line.startswith("| 第一宫 | 6˚射手24分") for line in cusps), cusps
    assert any(line.startswith("| 第二宫 | 6˚天蝎24分") for line in cusps), cusps
    assert "地平上下和得时失时取出生时的值,不随变换改。" in _sections(result.data["snapshot_text"])["变换盘"].splitlines()
    assert _export(result)["missing_selected_sections"] == [] and _export(result)["unknown_detected_sections"] == []


def test_transformchart_persona_writes_the_moment(tmp_path: Path) -> None:
    client = RecordingClient({TRANSFORM: _full("persona/improved")})
    result = _service(tmp_path, client).run_tool("transformchart", birth(transformKind="persona"), save_result=False)
    assert result.ok is True, result.error
    (sent,) = client.sent(TRANSFORM)
    assert {k: v for k, v in sent.items() if k.startswith("transform")} == {"transformKind": "persona", "transformPlanet": "Moon"}   # 基准星缺省月亮
    sections = _sections(result.data["snapshot_text"])
    moment = golden()["transform_full_B"]["persona/improved"]["moment"]
    assert moment == "1976-02-11 02:38:17"
    assert f"起盘时刻:{moment}" in sections["变换盘"].splitlines() and "基准星:月亮" in sections["变换盘"].splitlines()
    assert any(line.startswith(moment) for line in sections["起盘信息"].splitlines())      # 这张盘就是那一刻起的
    assert result.data["transform"]["moment"] == moment
    assert _export(result)["missing_selected_sections"] == [] and _export(result)["unknown_detected_sections"] == []


def test_transformchart_default_kind_is_the_upstream_page_default(tmp_path: Path) -> None:
    client = RecordingClient()
    result = _service(tmp_path, client, real_js=False).run_tool("transformchart", birth(), save_result=False)
    assert result.ok is True, result.error
    (sent,) = client.sent(TRANSFORM)
    assert {k: v for k, v in sent.items() if k.startswith("transform")} == {"transformKind": "inverted", "transformVariant": "improved"}
    assert result.data["settings"]["kind"] == V.TRANSFORM_DEFAULTS["kind"] == "inverted"


@pytest.mark.parametrize(("extra", "sent_fields"), [
    ({"transformKind": "superimposed", "transformShift": True}, {"transformKind": "superimposed", "transformPlanet": "Moon", "transformShift": 1}),
    ({"transformKind": "superimposed", "transformPlanet": "土星"}, {"transformKind": "superimposed", "transformPlanet": "Saturn", "transformShift": 0}),
    ({"transformKind": "planetCentered", "transformPlanet": "Sun"}, {"transformKind": "planetCentered", "transformPlanet": "Sun"}),
    ({"transformKind": "epoch", "transformHouse": 7}, {"transformKind": "epoch", "transformHouse": 7}),
    ({"transformKind": "sunRise", "transformVariant": "经典"}, {"transformKind": "sunRise", "transformVariant": "classic"}),
    ({"transformKind": "antiscia"}, {"transformKind": "antiscia"}),
])
def test_each_option_reaches_the_backend_request(tmp_path: Path, extra: dict, sent_fields: dict) -> None:
    client = RecordingClient()
    result = _service(tmp_path, client, real_js=False).run_tool("transformchart", birth(**extra), save_result=False)
    assert result.ok is True, result.error
    (sent,) = client.sent(TRANSFORM)
    assert {k: v for k, v in sent.items() if k.startswith("transform")} == sent_fields
    assert result.data["request"] == sent_fields


def test_options_the_transform_does_not_use_are_receipted_not_swallowed(tmp_path: Path) -> None:
    client = RecordingClient()
    payload = birth(transformKind="antiscia", transformPlanet="Mars", transformHouse=5, transformVariant="classic", transformShift=True)
    result = _service(tmp_path, client, real_js=False).run_tool("transformchart", payload, save_result=False)
    assert result.ok is True, result.error
    (sent,) = client.sent(TRANSFORM)
    assert {k: v for k, v in sent.items() if k.startswith("transform")} == {"transformKind": "antiscia"}       # 一个也不下发
    ignored = {item["key"]: item for item in result.data["params_ignored"]}
    assert set(ignored) == {"transformPlanet", "transformHouse", "transformVariant", "transformShift"}
    assert ignored["transformHouse"]["value"] == 5 and ignored["transformHouse"]["used_by"] == ["epoch"]
    assert ignored["transformPlanet"]["used_by"] == ["superimposed", "planetCentered", "persona"]
    assert any("映点盘（antiscia）用不上这些选项" in warning and "transformPlanet='Mars'" in warning for warning in result.warnings)
    # 回执过的选项回到缺省，不进 settings / 正文。
    assert result.data["settings"] == {"kind": "antiscia", **{k: v for k, v in V.TRANSFORM_DEFAULTS.items() if k != "kind"}}
    # 用得上的不回执
    used = _service(tmp_path, RecordingClient(), real_js=False).run_tool(
        "transformchart", birth(transformKind="superimposed", transformPlanet="Mars", transformShift=True), save_result=False)
    assert used.data["params_ignored"] == [] and not any("用不上" in warning for warning in used.warnings)


def test_technique_card_lists_only_the_options_this_transform_uses(tmp_path: Path) -> None:
    service = _service(tmp_path, RecordingClient(), real_js=False)
    card = service.run_tool("transformchart", birth(transformKind="epoch", transformHouse=7), save_result=False).data["technique_card"]["settings"]
    assert card["transformKind"]["value"] == "epoch" and card["transformKind"]["label"] == "变换种类" and "受孕盘" in card["transformKind"]["text"]
    assert card["transformHouse"]["value"] == 7 and card["transformHouse"]["label"] == "对应宫头"
    assert not {"transformPlanet", "transformShift", "transformVariant"} & set(card)
    default = service.run_tool("transformchart", birth(), save_result=False).data["technique_card"]["settings"]
    assert default["transformKind"]["value"] == "inverted" and default["transformVariant"]["value"] == "improved"
    assert not {"transformPlanet", "transformShift", "transformHouse"} & set(default)


def test_moment_failure_is_a_structured_error_not_an_empty_chart(tmp_path: Path) -> None:
    """高纬受孕盘：后端回 {kind, rulers, golden, momentFailed: true}、没有 chart（实抓）。上游页面显示「这张盘算不出这个时刻」。"""
    failed = live()["transform_moment_failed"]
    assert failed["response"]["momentFailed"] is True and "chart" not in failed["response"]
    client = RecordingClient({TRANSFORM: failed["response"]})
    result = _service(tmp_path, client).run_tool("transformchart", birth(**failed["birth_override"], transformKind="epoch"), save_result=False)
    assert result.ok is False
    assert result.error.code == "tool.transformchart_empty"
    assert result.error.details["reason"] == "moment_failed" and "算不出起盘时刻" in result.error.message


def test_backend_answering_another_kind_fails_loudly(tmp_path: Path) -> None:
    """后端对认不出的变换静默退回倒置盘（transform_charts.build_transform_chart）：回来的种类 ≠ 请求的，就不是所要的那张盘。"""
    inverted = {**live()["transform_full"]["superimposed/improved"], "kind": "inverted"}
    client = RecordingClient({TRANSFORM: inverted})
    result = _service(tmp_path, client).run_tool("transformchart", birth(transformKind="novien"), save_result=False)
    assert result.ok is False and result.error.code == "tool.transformchart_unknown_kind"
    assert (result.error.details["requested"], result.error.details["answered"]) == ("novien", "inverted")


def test_request_fields_are_cross_checked_against_the_vendored_upstream_function(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Python 侧「哪种变换带哪些选项」写漂了（这里少发口径），vendored 上游 transformRequestOptions 重算的那份对不上 → 报错。"""
    monkeypatch.setattr(auxlabs, "transform_request_fields", lambda settings: {"transformKind": settings["kind"]})
    client = RecordingClient({TRANSFORM: _full("novien/improved")})
    result = _service(tmp_path, client).run_tool("transformchart", birth(transformKind="novien"), save_result=False)
    assert result.ok is False and result.error.code == "tool.transformchart_request_mismatch"
    assert result.error.details["sent"] == {"transformKind": "novien"}
    assert result.error.details["upstream"] == {"transformKind": "novien", "transformVariant": "improved"}


def test_unknown_values_are_refused_with_the_full_option_table(tmp_path: Path) -> None:
    """后端对认不出的变换 / 版本静默退回缺省；入口在请求发出之前就拒，逐字段给全表（坏入参不起盘，run_tool 直接抛）。"""
    client = RecordingClient()
    service = _service(tmp_path, client, real_js=False)
    with pytest.raises(ToolValidationError) as caught:
        service.run_tool("transformchart", birth(transformKind="mirror"), save_result=False)
    assert caught.value.code == "tool.invalid_option"
    (field,) = caught.value.details["fields"]
    assert field["field"] == "transformKind" and [option["value"] for option in field["options"]] == list(V.TRANSFORM_KINDS)
    with pytest.raises(ToolValidationError) as caught:
        service.run_tool("transformchart", birth(transformKind="epoch", transformHouse=13), save_result=False)
    assert caught.value.code == "tool.invalid_option" and caught.value.details["fields"][0]["field"] == "transformHouse"
    with pytest.raises(ToolValidationError) as caught:
        service.run_tool("zodiacsystems", birth(zodiacVersion="z99"), save_result=False)
    assert caught.value.code == "tool.invalid_option"
    assert [option["value"] for option in caught.value.details["fields"][0]["options"]] == [value for value, _ in V.ZODIAC_VERSIONS]
    assert client.calls == []


def test_js_engine_failure_is_an_error_not_a_chart_without_its_section(tmp_path: Path) -> None:
    class Broken(FakeJsClient):
        def run(self, tool_name: str, payload: dict) -> dict:
            if tool_name == "aux_labs":
                raise RuntimeError("node exploded")
            return super().run(tool_name, payload)

    settings = _settings(tmp_path)
    service = HorosaSkillService(settings, client=RecordingClient(), store=MemoryStore(settings), js_client=Broken())
    result = service.run_tool("transformchart", birth(transformKind="inverted"), save_result=False)
    assert result.ok is False and result.error.code == "tool.transformchart_snapshot_failed"
    result = service.run_tool("zodiacsystems", birth(), save_result=False)
    assert result.ok is False and result.error.code == "tool.zodiacsystems_snapshot_failed"


# ─────────────────────────── 黄道制 ───────────────────────────


def _zodiac(version: str) -> dict:
    return {**live()["zodiac"], "version": version, "wheel": live()["zodiac_wheels"][version]}


def test_zodiacsystems_end_to_end(tmp_path: Path) -> None:
    client = RecordingClient({ZODIAC: lambda payload: _zodiac(payload["zodiacVersion"])})
    result = _service(tmp_path, client).run_tool("zodiacsystems", birth(), save_result=False)
    assert result.ok is True, result.error
    (sent,) = client.sent(ZODIAC)
    assert sent["zodiacVersion"] == "z13a" and sent["tradition"] is False and sent["predictive"] is False     # 缺省 = 上游页面缺省
    assert [endpoint for endpoint, _ in client.calls] == [ZODIAC]                                              # 没有本命回落：不另起本命盘
    text = result.data["snapshot_text"]
    assert list(_sections(text)) == ["黄道制"]                                                                  # 这一页没有盘体
    export = _export(result)
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []
    lines = text.splitlines()
    assert lines[:2] == ["[黄道制]", "黄道版本:十三星座 · 甲本(黄经不变,只换分段)"]
    assert "太阳:回归黄经 321.85° · 摩羯 22.54° · 星座 摩羯 · 银河黄道 金牛 25.36°" in lines
    data = result.data
    assert data["version"] == "z13a" and data["versionLabel"] == "十三星座 · 甲本"
    assert len(data["rows"]) == 28 and len(data["around"]) == 10 and data["year"] and len(data["wheel"]) == 13 and len(data["houses13Cusps"]) == 13
    assert set(data["rows"][0]["versions"]) == {value for value, _ in V.ZODIAC_VERSIONS}                       # 全部版本的落段都在数据里


def test_zodiac_version_changes_the_request_and_the_text(tmp_path: Path) -> None:
    client = RecordingClient({ZODIAC: lambda payload: _zodiac(payload["zodiacVersion"])})
    service = _service(tmp_path, client)
    texts = {}
    for version in ("z13a", "z14", "z12a"):
        result = service.run_tool("zodiacsystems", birth(zodiacVersion=version), save_result=False)
        assert result.ok is True, result.error
        texts[version] = result.data["snapshot_text"]
        assert len(result.data["wheel"]) == {"z13a": 13, "z14": 14, "z12a": 12}[version]
    assert [payload["zodiacVersion"] for payload in client.sent(ZODIAC)] == ["z13a", "z14", "z12a"]
    assert "黄道版本:十四星座 · 等分(黄经不变,只换分段)" in texts["z14"] and "太阳:回归黄经 321.85° · 水瓶 24.85° ·" in texts["z12a"]
    assert len(set(texts.values())) == 3


def test_zodiac_backend_answering_another_version_fails_loudly(tmp_path: Path) -> None:
    client = RecordingClient({ZODIAC: _zodiac("z13a")})
    result = _service(tmp_path, client).run_tool("zodiacsystems", birth(zodiacVersion="z14"), save_result=False)
    assert result.ok is False and result.error.code == "tool.zodiacsystems_unknown_kind"
    assert result.error.details["requested"] == "z14" and result.error.details["answered"] == "z13a"


def test_zodiac_without_rows_is_a_structured_error(tmp_path: Path) -> None:
    client = RecordingClient({ZODIAC: {"version": "z13a", "galacticCenter": 266.5}})
    result = _service(tmp_path, client).run_tool("zodiacsystems", birth(), save_result=False)
    assert result.ok is False and result.error.code == "tool.zodiacsystems_empty"


def test_zodiac_card_shows_the_version_and_not_the_unused_chart_keys(tmp_path: Path) -> None:
    service = _service(tmp_path, RecordingClient(), real_js=False)
    card = service.run_tool("zodiacsystems", birth(zodiacVersion="z12f", zodiacal=1, siderealAyanamsa="lahiri"), save_result=False).data["technique_card"]["settings"]
    assert card["zodiacVersion"]["value"] == "z12f" and "十二段 · 综合本" in card["zodiacVersion"]["text"]
    assert not {"hsys", "zodiacal"} & set(card)      # 宫制 / 黄道不参与分段（auxlab_vocab.ZODIAC_UNUSED_CHART_KEYS）
    chart_card = service.run_tool("transformchart", birth(), save_result=False).data["technique_card"]["settings"]
    assert {"hsys", "zodiacal"} <= set(chart_card)   # 变换盘照常回显


# ─────────────────────────── 离线桩（FakeClient + FakeJsClient）同形 ───────────────────────────


@pytest.mark.parametrize(("tool", "extra"), [
    ("transformchart", {"transformKind": "superimposed", "transformShift": True}),
    ("transformchart", {"transformKind": "vertical"}),
    ("transformchart", {"transformKind": "persona"}),
    ("zodiacsystems", {"zodiacVersion": "z14"}),
])
def test_offline_stubs_produce_a_clean_export(tmp_path: Path, tool: str, extra: dict) -> None:
    result = _service(tmp_path, RecordingClient(), real_js=False).run_tool(tool, birth(**extra), save_result=False)
    assert result.ok is True, result.error
    export = _export(result)
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []
    assert AI_EXPORT_PRESET_SECTIONS[tool][-1] in _sections(result.data["snapshot_text"])
