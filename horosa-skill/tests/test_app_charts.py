"""Report figures drawn by the 星阙 app's own chart code (reports/app_charts.py + horosa-core-js/dist/app-charts.cjs).

What must hold:
- the committed bundle is the one its manifest describes (sha / kinds), and it really draws the live fixtures;
- rendering is byte-stable (seeded ids, OS-neutral navigator);
- the SVG survives svglib with the app's glyph font and the report's own TrueType text font (no Helvetica, no tofu);
- the 紫微 center prints its details (full mode), not the interactive「命盘信息」button, and coordinates are not
  mangled by the upstream scientific-notation bug (notes-local/upstream-reports/2026-11-09-…);
- when the bundle / Node is unavailable the figure falls back to the skill's own drawing and says so.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from horosa_skill.reports import app_charts
from horosa_skill.reports.figures import drawing_to_png, extract_figures, figure_drawing

PKG_ROOT = Path(__file__).resolve().parents[1]
BUNDLE = PKG_ROOT / "horosa-core-js" / "dist" / "app-charts.cjs"
MANIFEST = PKG_ROOT / "contracts" / "app_charts_bundle.json"
FIXTURE = json.loads(gzip.decompress((PKG_ROOT / "tests" / "fixtures" / "app_charts_live.json.gz").read_bytes()))

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")


class _Client:
    """The real engine client's render call, pinned to the source tree's horosa-core-js."""

    def render_app_charts(self, figures):
        from horosa_skill.config import Settings
        from horosa_skill.engine.js_client import HorosaJsEngineClient

        client = HorosaJsEngineClient(Settings.from_env())
        client._candidate_engine_roots = lambda: [PKG_ROOT / "horosa-core-js"]  # type: ignore[method-assign]
        return client.render_app_charts(figures)


def _figures(tool: str) -> list[dict]:
    data = FIXTURE[tool]
    return app_charts.attach_app_svgs(extract_figures(tool, data, tool), tool, data, _Client())


def _cjk_font() -> tuple[str, str, dict[str, tuple[str, int]]]:
    from horosa_skill.reports.renderers import _drawing_font_files

    from horosa_skill.reports.renderers import SIMPLIFIED

    fonts = _drawing_font_files(SIMPLIFIED)
    if not fonts:
        pytest.skip("no CJK TrueType font on this machine")
    regular, bold = fonts["names"]
    return regular, bold, {**fonts["files"], **app_charts.glyph_font_files()}


def test_committed_bundle_matches_its_manifest() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    body = BUNDLE.read_bytes()
    assert hashlib.sha256(body).hexdigest() == manifest["bundle_sha256"]
    assert len(body) == manifest["bundle_bytes"]
    assert {"natal_wheel", "bi_wheel", "ziwei", "guolao", "taiyi"} <= set(manifest["kinds"])
    assert manifest["theme_tokens"] > 100, "light-theme tokens are baked in from the app stylesheets"
    assert manifest["app_files"], "the manifest must pin every app source file it bundled"
    assert b"horacedong" not in body and b"/var/folders" not in body, "bundle must not embed machine paths"


@needs_node
def test_app_draws_the_natal_wheel_and_ziwei_byte_stably() -> None:
    first = _figures("chart")[0]
    assert first["renderer"] == "app" and first["app_kind"] == "natal_wheel"
    assert _figures("chart")[0]["app_svg"] == first["app_svg"], "same engine data must give the same SVG bytes"
    assert 'font-family="ywastrochart"' in first["app_svg"], "planets are the app's glyph font, not text"
    zw = _figures("ziwei_birth")[0]
    assert zw["renderer"] == "app" and zw["kind"] == "grid12"
    assert "命盘信息" not in zw["app_svg"], "the interactive button is removed; the center is printed in full"
    assert "121°28′" in zw["app_svg"] and "1°7′4″E" not in zw["app_svg"], "longitude 121e28 must not be read as 1.21e30"


@needs_node
def test_svg_converts_with_glyph_font_and_report_text_font() -> None:
    from reportlab.graphics.shapes import String

    regular, bold, files = _cjk_font()
    for tool in ("chart", "ziwei_birth"):
        spec = _figures(tool)[0]
        drawing = figure_drawing(spec, 400, regular, bold, None)
        assert drawing is not None and round(drawing.width) == 400
        names: set[str] = set()

        def walk(node):
            for child in getattr(node, "contents", None) or []:
                if isinstance(child, String):
                    names.add(child.fontName)
                else:
                    walk(child)

        walk(drawing)
        assert not names & {"Helvetica", "Helvetica-Bold", "Courier", "Courier-Bold"}, f"{tool}: unembedded / placeholder font left: {names}"
        assert names <= {regular, bold, *app_charts.glyph_font_files()}, names
        png = drawing_to_png(drawing, files, scale=1.0)
        assert png and png.startswith(b"\x89PNG")


def test_normalize_resolves_what_svglib_cannot() -> None:
    svg = ('<svg><g font-family="Helvetica Light"><text font-weight="600" fill="var(--a, var(--b, #123456))">1</text>'
           '<text font-family="ywastrochart" font-weight="400">a</text></g>'
           '<rect fill="transparent" stroke="rgba(184, 137, 63, 0.22)"/></svg>')
    out = app_charts.normalize_svg(svg)
    assert 'fill="#123456"' in out and "var(" not in out
    assert 'fill="none"' in out and 'stroke="#b8893f" stroke-opacity="0.22"' in out
    assert f'font-family="{app_charts.TEXT_BOLD_FAMILY}"' in out
    assert f'font-family="{app_charts.GLYPH_FONTS["ywastrochart"][1]}"' in out
    assert "font-weight" not in out


def test_unavailable_bundle_falls_back_to_the_skill_drawing_and_says_so() -> None:
    class Gone:
        def render_app_charts(self, figures):
            return None

    data = FIXTURE["chart"]
    spec = app_charts.attach_app_svgs(extract_figures("chart", data, "chart"), "chart", data, Gone())[0]
    assert spec["renderer"] == "builtin" and "unavailable" in spec["renderer_note"]
    assert "app_svg" not in spec

    class Broken:
        def render_app_charts(self, figures):
            raise RuntimeError("boom")

    spec = app_charts.attach_app_svgs(extract_figures("chart", data, "chart"), "chart", data, Broken())[0]
    assert spec["renderer"] == "builtin"


def test_switch_off_keeps_the_skill_drawing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_APP_CHARTS", "0")
    calls = []

    class Spy:
        def render_app_charts(self, figures):
            calls.append(figures)
            return []

    data = FIXTURE["chart"]
    spec = app_charts.attach_app_svgs(extract_figures("chart", data, "chart"), "chart", data, Spy())[0]
    assert spec["renderer"] == "builtin" and not calls


def test_plan_gives_each_wheel_its_own_layer() -> None:
    data = FIXTURE["chart"]
    plan = app_charts.plan("chart", data, extract_figures("chart", data, "chart"))
    assert [request["kind"] for _i, request in plan] == ["natal_wheel"]
    assert plan[0][1]["data"]["chart"] is data["chart"]
    synastry = {"inner": {"chart": data["chart"], "params": {"name": "甲"}}, "outer": {"chart": data["chart"], "params": {"name": "乙"}}}
    bi = [{"kind": "wheel", "source": ["inner"], "outer_bodies": [{"id": "Sun"}]}]
    [(_i, request)] = app_charts.plan("relative", synastry, bi)
    assert request["kind"] == "bi_wheel"
    assert request["data"]["natualChart"]["params"]["name"] == "甲", "inner person = houses ring, as the report caption says"
    assert app_charts.plan("babylon", data, [{"kind": "wheel", "source": []}]) == []


@needs_node
@pytest.mark.parametrize(
    ("tool", "kind", "marker"),
    [
        ("chart", "natal_wheel", 'font-family="ywastrochart"'),
        ("ziwei_birth", "ziwei", "命主"),
        ("guolao_chart", "guolao", "四柱"),
        ("taiyi", "taiyi", "中宫"),
        ("relative", "bi_wheel", 'font-family="ywastrochart"'),
    ],
)
def test_each_family_is_drawn_by_the_app_with_light_theme_tokens(tool: str, kind: str, marker: str) -> None:
    spec = next(f for f in _figures(tool) if f.get("app_kind") == kind)
    svg = spec["app_svg"]
    assert spec["renderer"] == "app" and svg.startswith("<svg") and marker in svg
    assert "var(" not in svg, "every app CSS variable must be resolved from the app's light-theme tokens"


def test_theme_tokens_are_the_light_values_not_the_dark_fallbacks() -> None:
    """六壬的底色回退值是暗色 #090b0e；必须按 app 亮色主题（layouts/app/*.less 的 :root）解析。"""
    import subprocess

    script = (
        "const b=require(process.argv[1]);"
        "process.stdout.write(b.resolveThemeVars('<rect fill=\"var(--horosa-astro-panel, #090b0e)\" "
        "stroke=\"var(--horosa-liureng-square-line, rgba(231, 189, 117, 0.18))\"/>'))"
    )
    node = shutil.which("node")
    if not node:
        pytest.skip("node not on PATH")
    out = subprocess.run([node, "-e", script, str(BUNDLE)], capture_output=True, text=True, check=True).stdout
    assert "#090b0e" not in out and "rgba(154, 106, 37, 0.16)" in out, out
