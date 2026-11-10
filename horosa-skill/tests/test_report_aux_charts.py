"""Report figures the app draws from a chart the stored result does not hold (reports/aux_charts.py).

The app fetches one more chart for these pages: the directed / progressed outer ring (演进推运 / Bezza / 周日小限 / 推运 /
恒星推运), the selected moment (天星择日), the syzygy moment (产前朔望) and the 七政 Moira wheel (七政择日). The report service
computes that chart through the real engine at render time — never stored, never added to the tool response — and the
app's own drawing code draws it. What must hold:
- each figure is the app's drawing of exactly the engine's charts (fixtures captured live from the vendored runtime);
- the tool path still sends `withChart: 0`; the report repeats the stored request with `withChart: 1` and the stored
  target, not today's date;
- the extra computation stores no memory run, and a report never starts the runtime;
- any failure leaves the report with its previous figures plus a note that says what is missing and why.
"""
from __future__ import annotations

import gzip
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fakes import CaptureClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.reports import app_charts, aux_charts
from horosa_skill.reports.figures import extract_figures, figure_notes
from horosa_skill.reports.layout import body_blocks
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads

PKG_ROOT = Path(__file__).resolve().parents[1]
_RAW = json.loads(gzip.decompress((PKG_ROOT / "tests" / "fixtures" / "report_aux_charts_live.json.gz").read_bytes()))


def _resolve(node: Any) -> Any:
    if isinstance(node, dict):
        if "$same_as" in node:
            target: Any = _RAW
            for key in node["$same_as"]:
                target = target[key]
            return _resolve({k: v for k, v in target.items() if k in ("params", "chart", "aspects", "lots")}
                            if node["$same_as"][-1] == "base" else target)
        return {key: _resolve(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_resolve(item) for item in node]
    return node


FIXTURE = {tool: _resolve(case) for tool, case in _RAW.items() if not tool.startswith("_")}
DOUBLE = ("neroman", "bezzafigure", "jayprofection", "prog", "vedicprog")
SINGLE = ("tianxing", "prenatalsyzygy")

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")


class _Client:
    """The real engine client's render call, pinned to the source tree's horosa-core-js."""

    def render_app_charts(self, figures):
        from horosa_skill.engine.js_client import HorosaJsEngineClient

        client = HorosaJsEngineClient(Settings.from_env())
        client._candidate_engine_roots = lambda: [PKG_ROOT / "horosa-core-js"]  # type: ignore[method-assign]
        return client.render_app_charts(figures)


def _settled(tool: str, client: Any = None) -> tuple[list[dict[str, Any]], list[str]]:
    case = FIXTURE[tool]
    figures = extract_figures(tool, case["data"], tool)
    merged = aux_charts.merge(tool, figures, aux_charts.build(tool, case["aux"]))
    return aux_charts.settle(app_charts.attach_app_svgs(merged, tool, case["data"], client or _Client()))


def _lons(chart: dict[str, Any]) -> dict[str, float]:
    return {str(o["id"]): float(o["lon"]) % 360 for o in chart["chart"]["objects"] if isinstance(o, dict) and "lon" in o}


# ───────────────────────────── figures from the live engine charts ─────────────────────────────

def test_the_double_wheel_is_built_from_the_engines_two_charts_only() -> None:
    for tool in DOUBLE:
        aux = FIXTURE[tool]["aux"]
        spec = aux_charts.build(tool, aux)
        natal, outer = _lons(aux["natal"]), _lons(aux["outer"])
        assert {b["id"]: b["lon"] for b in spec["bodies"]} == {k: natal[k] for k in (b["id"] for b in spec["bodies"])}
        assert {b["id"]: b["lon"] for b in spec["outer_bodies"]} == {k: outer[k] for k in (b["id"] for b in spec["outer_bodies"])}
        assert any(abs(natal[b["id"]] - b["lon"]) > 1e-6 for b in spec["outer_bodies"]), f"{tool}: outer ring must be the moved chart"
        request = spec["app_request"]
        assert request["kind"] == "bi_wheel"
        assert request["data"]["natualChart"]["chart"] is aux["natal"]["chart"] and request["data"]["dirChart"]["chart"] is aux["outer"]["chart"]
        assert aux["moment"] and aux["moment"] in spec["ring_note"], "the caption says which moment the outer ring is"


@needs_node
@pytest.mark.parametrize("tool", DOUBLE)
def test_progression_double_wheels_are_the_apps_double_chart(tool: str) -> None:
    figures, notes = _settled(tool)
    assert notes == []
    first = figures[0]
    assert first["renderer"] == "app" and first["app_kind"] == "bi_wheel", first.get("renderer_note")
    assert first["title"] == aux_charts.title(tool)
    assert 'font-family="ywastrochart"' in first["app_svg"]
    assert "app_request" not in first, "the engine charts do not travel into the document"
    assert [f["kind"] for f in figures].count("wheel") == 1, "vedicprog: the stored natal-only wheel is replaced by the double wheel"
    assert figure_notes(first, str)[0].startswith("内圈为本命盘，外圈为"), "caption is the progression's, not the synastry one"


@needs_node
@pytest.mark.parametrize("tool", SINGLE)
def test_moment_charts_are_the_apps_single_wheel(tool: str) -> None:
    figures, notes = _settled(tool)
    assert notes == [] and len(figures) == 1
    spec = figures[0]
    assert spec["renderer"] == "app" and spec["app_kind"] == "natal_wheel", spec.get("renderer_note")
    assert FIXTURE[tool]["aux"]["moment"] in spec["title"]
    # the drawn chart is the engine's chart at that moment, the same one the text section lists
    sun = _lons(FIXTURE[tool]["aux"]["chart"])["Sun"]
    assert next(b for b in spec["bodies"] if b["id"] == "Sun")["lon"] == sun


def test_tianxing_figure_is_the_moment_the_text_section_lists() -> None:
    case = FIXTURE["tianxing"]
    assert f"选中命中：{case['aux']['moment']}" in case["data"]["snapshot_text"]
    syzygy = FIXTURE["prenatalsyzygy"]
    assert syzygy["aux"]["moment"] == syzygy["data"]["syzygy"]["datetime"]
    listed = {o["id"]: o["lon"] for o in syzygy["data"]["syzygy_chart"]["objects"]}
    assert {k: v for k, v in _lons(syzygy["aux"]["chart"]).items() if k in listed} == {k: v % 360 for k, v in listed.items()}


def test_without_the_app_drawing_the_builtin_double_wheel_still_draws() -> None:
    class Gone:
        def render_app_charts(self, figures):
            return None

    figures, notes = _settled("neroman", Gone())
    assert figures[0]["renderer"] == "builtin" and figures[0]["outer_bodies"] and notes == []
    assert "app_request" not in figures[0]


# ───────────────────────────── the service: compute at render time ─────────────────────────────

class _EngineWithCharts(CaptureClient):
    """Fake backend that answers like the live engine for the aux requests (fixture charts)."""

    def call(self, endpoint: str, payload: dict) -> dict:
        response = super().call(endpoint, payload)
        if endpoint == "/astroextra/neroman" and payload.get("withChart") == 1:
            return {**response, "chart": FIXTURE["neroman"]["aux"]["outer"]}
        if endpoint == "/":  # the chart service's /chart route
            return json.loads(json.dumps(FIXTURE["neroman"]["aux"]["natal"]))
        return response


def _service(tmp_path: Path, client: Any) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt", data_dir=tmp_path / "data")
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())


def _stored(service: HorosaSkillService, tool: str) -> tuple[dict[str, Any], dict[str, Any]]:
    env = service.run_tool(tool, build_sample_payloads()[tool], save_result=True)
    assert env.ok and env.memory_ref
    return service._load_report_source(env.memory_ref.run_id, None)


def _runs(service: HorosaSkillService) -> int:
    return len(service.store.query_runs(limit=500))


def test_tool_call_keeps_withchart_0_and_the_report_repeats_the_stored_request_with_the_chart(tmp_path: Path) -> None:
    client = _EngineWithCharts()
    service = _service(tmp_path, client)
    run, artifact = _stored(service, "neroman")
    tool_bodies = [p for e, p in client.calls if e == "/astroextra/neroman"]
    assert [b["withChart"] for b in tool_bodies] == [0], "the tool response must not grow by the ~100 KB chart"
    client.calls.clear()
    runs_before = _runs(service)
    figures, notes = service._report_figures(service.report_builder.build_figures(run=run, source_artifact=artifact), run, artifact)
    assert notes == [] and figures[0]["title"] == aux_charts.title("neroman") and figures[0]["outer_bodies"]
    [aux_body] = [p for e, p in client.calls if e == "/astroextra/neroman"]
    assert aux_body["withChart"] == 1
    assert {k: v for k, v in aux_body.items() if k != "withChart"} == {k: v for k, v in tool_bodies[0].items() if k != "withChart"}, \
        "same request as the tool call (stored target, not today)"
    assert _runs(service) == runs_before, "the extra computation must not store a memory run"


def test_selected_moment_chart_runs_the_chart_tool_without_storing_it(tmp_path: Path) -> None:
    client = CaptureClient()
    service = _service(tmp_path, client)
    run, artifact = _stored(service, "tianxing")
    runs_before, client.calls[:] = _runs(service), []
    figures, notes = service._report_figures(service.report_builder.build_figures(run=run, source_artifact=artifact), run, artifact)
    assert notes == [] and figures[0]["title"] == "选中时刻星盘 · 2028-04-01 00:01:30"
    assert [(e, p["date"], p["time"]) for e, p in client.calls if e == "/"] == [("/", "2028/04/01", "00:01:30")]
    assert not [e for e, _p in client.calls if e.startswith("/electionscan")], "the scan is not repeated"
    assert _runs(service) == runs_before, "the extra computation must not store a memory run"


def test_engine_without_the_chart_keeps_the_report_and_says_what_is_missing(tmp_path: Path) -> None:
    service = _service(tmp_path, CaptureClient())  # the fake answers withChart=1 like withChart=0: no chart
    run, artifact = _stored(service, "neroman")
    figures, notes = service._report_figures(service.report_builder.build_figures(run=run, source_artifact=artifact), run, artifact)
    assert figures == []
    assert len(notes) == 1 and notes[0].startswith("演进推运双盘（Néroman）没有画出") and "withChart=1" in notes[0]
    result = service.report_render({"run_id": run["run_id"], "format": "pdf", "style": "chart", "output_path": "n.pdf"})
    assert Path(result["file"]["path"]).read_bytes().startswith(b"%PDF")


def test_a_report_never_starts_the_runtime(tmp_path: Path) -> None:
    client = _EngineWithCharts()
    service = _service(tmp_path, client)
    run, artifact = _stored(service, "vedicprog")
    before = service.report_builder.build_figures(run=run, source_artifact=artifact)
    assert [f["kind"] for f in before] == ["wheel"], "the stored natal chart (raw.natalChart) is drawn as a single wheel"
    client.probe = lambda endpoint="/common/time", payload=None: False  # type: ignore[method-assign]
    started: list[Any] = []
    service.runtime_manager.start_local_services = lambda **kw: started.append(kw)  # type: ignore[method-assign]
    client.calls.clear()
    figures, notes = service._report_figures(before, run, artifact)
    assert started == [] and client.calls == []
    assert [f["title"] for f in figures] == [f["title"] for f in before], "previous figure stays"
    assert len(notes) == 1 and "排盘引擎没有在运行" in notes[0]


def test_vedicprog_double_wheel_replaces_the_natal_only_wheel(tmp_path: Path) -> None:
    client = _EngineWithCharts()
    service = _service(tmp_path, client)
    run, artifact = _stored(service, "vedicprog")
    client.calls.clear()
    figures, notes = service._report_figures(service.report_builder.build_figures(run=run, source_artifact=artifact), run, artifact)
    assert notes == [] and [f["title"] for f in figures] == [aux_charts.title("vedicprog")]
    chart_bodies = [p for e, p in client.calls if e == "/"]  # the chart service's /chart route
    assert len(chart_bodies) == 2 and all(b["zodiacal"] == 1 for b in chart_bodies), "app: both rings re-fetched sidereal"
    method = next(m for m in run_payload_methods(service, run) if m["method"] == "secondary")
    assert chart_bodies[1]["date"].replace("/", "-") == method["progressedDate"]["date"]  # transport writes the date with slashes
    assert chart_bodies[1]["time"] == method["progressedDate"]["time"]


def run_payload_methods(service: HorosaSkillService, run: dict[str, Any]) -> list[dict[str, Any]]:
    _run, artifact = service._load_report_source(run["run_id"], None)
    chart = service.report_builder.chart_source(run=_run, source_artifact=artifact)
    return chart["data"]["methods"]


# ───────────────────────────── where the note is printed ─────────────────────────────

def test_figure_notes_are_printed_under_the_figure_heading() -> None:
    document = {"sections": [{"id": "s", "title": "起盘信息", "body": "x", "group": "chart", "human_visible": True}],
                "figures": [], "figure_notes": ["演进推运双盘没有画出：原因。"]}
    blocks = body_blocks(document)
    kinds = [(b.kind, b.text) for b in blocks]
    assert ("heading", "盘图") in kinds and ("note", "演进推运双盘没有画出：原因。") in kinds
    assert ("figures", "") not in kinds, "no figure block when there is nothing to draw"
    document["figures"] = [{"kind": "wheel", "title": "本命盘"}]
    kinds = [b.kind for b in body_blocks(document)]
    assert kinds.index("figures") < kinds.index("note")
