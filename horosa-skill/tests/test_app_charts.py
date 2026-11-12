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
import re
import shutil
from pathlib import Path

import pytest

from horosa_skill.reports import app_charts
from horosa_skill.reports.figures import drawing_to_png, extract_figures, figure_drawing, figure_notes, is_drawn

PKG_ROOT = Path(__file__).resolve().parents[1]
BUNDLE = PKG_ROOT / "horosa-core-js" / "dist" / "app-charts.cjs"
MANIFEST = PKG_ROOT / "contracts" / "app_charts_bundle.json"
FIXTURE = json.loads(gzip.decompress((PKG_ROOT / "tests" / "fixtures" / "app_charts_live.json.gz").read_bytes()))

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not on PATH")


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
        pytest.skip("[host] no CJK TrueType font on this machine")
    regular, bold = fonts["names"]
    return regular, bold, {**fonts["files"], **app_charts.glyph_font_files()}


def test_committed_bundle_matches_its_manifest() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    body = BUNDLE.read_bytes()
    assert hashlib.sha256(body).hexdigest() == manifest["bundle_sha256"]
    assert len(body) == manifest["bundle_bytes"]
    assert {"natal_wheel", "bi_wheel", "ziwei", "guolao", "taiyi", "liureng", "liuyao", "uranian_dial"} <= set(manifest["kinds"])
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
    assert "圆形盘" not in next(f for f in _figures("liureng_gods") if f.get("app_kind") == "liureng")["app_svg"], "view toggle removed"
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
        ("liureng_gods", "liureng", "真太阳时"),
        ("germany", "uranian_dial", 'font-family="ywastrochart"'),
        ("jinkou", "jinkou", "贵神"),
        ("suzhan", "suzhan", "四柱"),
        ("babylon", "babylon", "恒星黄道"),
        ("feigong", "feigong", "中宫"),
        ("michon", "michon", "ASC"),
        ("qizhengkin", "qizhengkin", "坚七政"),
        ("cetian", "cetian", "命宫"),
        ("xianqin", "xianqin", "命星"),
        ("qimen", "qimen", "值符"),
        ("india_chart", "india_south", "命盘"),
        ("bazi_birth", "bazi", "日元"),
        ("geomancy", "geomancy", "护盾方盘"),
        ("xiaoliuren", "xiaoliuren", "一传"),
        ("xiaochengtu", "xiaochengtu", "用宫"),
        ("guice", "guice", "四位盘"),
        ("lingqi", "lingqi", "灵棋盘"),
        ("wuzhao", "wuzhao", "空亡"),
        ("yizhangjing", "yizhangjing", "命宫主星"),
        ("tongshefa", "tongshefa", "互潜"),
        ("acg", "acg", "acg-lines"),
        ("sanshiunited", "sanshi", "旬空"),
        ("tarot", "tarot", "凯尔特十字"),
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
        pytest.skip("[host] node not on PATH")
    out = subprocess.run([node, "-e", script, str(BUNDLE)], capture_output=True, text=True, check=True).stdout
    assert "#090b0e" not in out and "rgba(154, 106, 37, 0.16)" in out, out


@needs_node
def test_liuyao_uses_the_app_board_only_when_the_changed_hexagram_is_consistent() -> None:
    """样例载荷的动爻与 changed_code 对不上：app 会从动爻自己翻出之卦（正文里没有），所以只在两者一致 / 没有动爻时换 app 画法。"""
    import copy

    data = FIXTURE["sixyao"]
    figures = extract_figures("sixyao", data, "sixyao")
    assert app_charts.plan("sixyao", data, figures) == [], "inconsistent 变卦 → keep the skill's drawing (本卦 only)"
    still = copy.deepcopy(data)
    for line in still["lines"]:
        line["change"] = False
    spec = app_charts.attach_app_svgs(extract_figures("sixyao", still, "sixyao"), "sixyao", still, _Client())[0]
    assert spec["renderer"] == "app" and spec["app_kind"] == "liuyao"
    assert "乾宫·本宫" in spec["app_svg"] and "用神" in spec["app_svg"], "the app's own analysis line (analyzeLiuyao) is printed"


def test_bitmap_blends_translucent_fills() -> None:
    """RGBA 底上 Pillow 只覆盖 alpha、转 RGB 后整块实色（90° 盘三个扇区曾印成饱和色块）：半透明必须按 alpha 混合。"""
    import io

    from PIL import Image
    from reportlab.graphics.shapes import Drawing, Rect
    from reportlab.lib.colors import Color

    drawing = Drawing(20, 20)
    drawing.add(Rect(0, 0, 20, 20, fillColor=Color(0.84, 0.42, 0.35, alpha=0.1), strokeColor=None, fillOpacity=0.1))
    png = drawing_to_png(drawing, {"x": (str(app_charts.FONT_DIR / "ywastro.ttf"), 0)}, scale=1.0)
    r, g, b = Image.open(io.BytesIO(png)).convert("RGB").getpixel((10, 10))
    assert min(r, g, b) > 220, (r, g, b)


def test_tooltips_never_become_visible_text() -> None:
    svg = '<svg><text font-family="ywastrochart">I<title>本命 · 海王星</title></text><desc>x</desc></svg>'
    out = app_charts.normalize_svg(svg)
    assert "本命" not in out and "<desc" not in out and ">I</text>" in out


def test_symbols_missing_from_the_text_font_use_the_fallback_chain() -> None:
    from reportlab.graphics.shapes import Group, String

    regular, bold, _files = _cjk_font()
    chain = app_charts._symbol_chain()
    if not chain or 0x211E in (app_charts._charset(regular) or set()):
        pytest.skip("[host] no symbol fallback font on this machine, or the text font already has ℞")
    group = Group(String(0, 0, "℞", fontName="Courier"), String(0, 0, "本命", fontName="Courier"))
    app_charts._swap_text_fonts(group, regular, bold)
    assert group.contents[0].fontName in {name for name, *_ in chain}
    assert group.contents[1].fontName == regular


@needs_node
def test_app_only_figures_appear_only_when_the_app_draws_them() -> None:
    """金口诀 / 宿占 没有 skill 自画版本（kind="app"）：app 画出来才进报告，画不出来整张图不出现（不留空框）。"""
    for tool in ("jinkou", "suzhan"):
        figures = extract_figures(tool, FIXTURE[tool], tool)
        assert [f["kind"] for f in figures] == ["app"], tool
        assert not is_drawn(figures[0]), "no builtin drawing behind an app-only figure"
        assert app_charts.attach_app_svgs(figures, tool, FIXTURE[tool], None) == [], "undrawn app-only figure is dropped"


def test_suzhan_board_gets_the_four_pillars_from_board_context() -> None:
    """宿盘中宫要四柱（app 的盘来自 Java /chart，恒带 chart.nongli）；本盘走 chart 服务时 runner 另取放在 board_context，不并进 chart。"""
    data = FIXTURE["suzhan"]
    assert not data["chart"].get("nongli") and data["board_context"]["nongli"]["bazi"], "fixture exercises the chart-service path"
    [(_i, request)] = app_charts.plan("suzhan", data, extract_figures("suzhan", data, "suzhan"))
    assert request["data"]["board_context"]["nongli"] == data["board_context"]["nongli"]


def test_inline_style_fonts_are_lifted_and_italic_maps_to_the_text_font() -> None:
    """React 的 style={{ fontFamily }} 落成内联 style（巴比伦七曜符号）：不提成属性，svglib 拿到没注册的字族名、符号印成字母；
    斜体（楔文转写）svglib 映到 Oblique，也要换回报告字体（否则缺字形印方块）。"""
    out = app_charts.normalize_svg('<svg><text style="font-family:ywastro;font-variant-numeric:tabular-nums">G</text></svg>')
    assert 'font-family="HorosaAppYwastro"' in out and 'style="font-variant-numeric:tabular-nums"' in out, out
    regular, bold, _files = _cjk_font()
    drawing = app_charts.svg_drawing('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="40" viewBox="0 0 100 40">'
                                     '<text x="2" y="20" font-style="italic">MUL.MUL</text></svg>', 100, text_font=regular, bold_font=bold)
    assert [s.fontName for s in _strings(drawing)] == [regular]


@needs_node
def test_babylon_planets_use_the_app_glyph_font() -> None:
    regular, bold, _files = _cjk_font()
    spec = next(f for f in _figures("babylon") if f.get("app_kind") == "babylon")
    names = [s.fontName for s in _strings(app_charts.svg_drawing(spec["app_svg"], 520, text_font=regular, bold_font=bold))]
    assert names.count("HorosaAppYwastro") == 7, "七曜 glyphs (style font-family) must land on the registered glyph font"


def _strings(node):
    from reportlab.graphics.shapes import String

    for child in getattr(node, "contents", []) or []:
        if isinstance(child, String):
            yield child
        else:
            yield from _strings(child)


def test_suzhan_board_nongli_failure_says_what_it_costs() -> None:
    """宿盘盘图另取四柱失败：警告说的是「报告里不画宿盘」，不能借用七政四余的流年话术。负向对照：删掉 runner 里该分支 → 红。"""
    from horosa_skill.service._context import _degrade_collector
    from horosa_skill.service.runners.guolao import GuolaoRunners

    class _Down:
        def _call_remote(self, *_a, **_k):
            raise RuntimeError("java down")

    with _degrade_collector() as notes:
        assert GuolaoRunners._guolao_fetch_nongli(_Down(), {}, "2028-04-06", "09:33:00", role="宿盘盘图") is None
    assert any("宿占报告盘图" in note for note in notes) and not any("七政四余" in note for note in notes), notes


@needs_node
def test_page_scoped_tokens_use_the_pages_light_values() -> None:
    """飞宫在「卜其他」的皇极式布局里：--horosa-huangji-text 由 .horosa-huangji-redesign 按亮色重定义（→ --horosa-text）；
    取 var() 的回退值是暗色主题的浅米色 #e8dcc8（中宫干字几乎看不见）。负向对照：adapter 去掉 themeScope → 红。"""
    spec = next(f for f in _figures("feigong") if f.get("app_kind") == "feigong")
    assert "#e8dcc8" not in spec["app_svg"].lower(), "page scope must resolve --horosa-huangji-text to the light theme's text colour"


def test_bundle_stays_free_of_page_ui() -> None:
    """飞宫页模块经时空面板把地图与城市库（citiesFull.json 等 ~4 MB）拖进 bundle（实测 5.2 MB）；APP_UI_ONLY 把这些纯页面 UI
    桩掉后 1.5 MB、输出逐字节不变。新接一种盘时若又拖进页面 UI，这里先红。上限随正当的盘面代码（地占 / 灵棋 / 轨策…）
    放宽到 4 MB；河洛信息板的卦辞 / 爻辞库（heluoTiaowen.json，388 KB，esbuild 把 CJK 转义成 \\u 后约 0.7 MB）在画图路径上，
    塔罗牌阵（renderCenter 要牌组表、牌名与牌义：+0.43 MB，单牌详情抽屉已桩掉）也在，合起来放宽到 5.5 MB。
    地图 / 城市库 / 塔罗详情抽屉的逐项检查不变。"""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["bundle_bytes"] < 5_500_000, manifest["bundle_bytes"]
    assert not any(path.startswith(("components/amap/", "data/cit")) for path in manifest["app_files"])
    assert "components/tarot/CardDetailDrawer.js" not in manifest["app_files"], "the per-card drawer (≈140 KB of meanings) is page UI"


def test_dominant_baseline_becomes_dy() -> None:
    """svglib 不认 dominant-baseline：app 图里 middle / central 上千处整体上移约 0.35em（演禽竖排星名首字压出格子）。
    规整时折成 dy（em 随字号）。负向对照：去掉 _baseline 这一步 → 红。"""
    out = app_charts.normalize_svg('<svg><text x="1" y="2" dominant-baseline="middle">危</text>'
                                   '<text style="dominant-baseline:hanging">井</text><text dy="3" dominant-baseline="central">x</text></svg>')
    assert out.count('dy="0.35em"') == 1 and 'dy="0.8em"' in out and 'dy="3"' in out and "baseline" not in out, out


@needs_node
def test_component_stylesheet_light_tokens_and_class_rules_are_inlined() -> None:
    """坚七政圆盘的颜色全在组件 less 里（默认暗色、:root[light] 覆盖）+ 类规则（.qz-wheel-bg 的 fill）；svglib 两样都不认。
    css.applyComponentCss 照浏览器亮色主题内联。负向对照：adapter 去掉这一步 → 底色缺失 / 暗色残留 → 红。"""
    svg = next(f for f in _figures("qizhengkin") if f.get("app_kind") == "qizhengkin")["app_svg"]
    assert "var(--qz" not in svg and "#070718" not in svg and "#0b0b20" not in svg
    assert re.search(r'<rect fill="#f8f4eb"[^>]*class="qz-wheel-bg"', svg), "light panel fill from the class rule"


@needs_node
def test_kin_ziwei_center_has_the_four_pillars() -> None:
    """策天 / 演禽后端不产四柱，app 用 lunar-javascript 本地排（buildLocalBaziResult）；那个包被当 UI 桩掉时 app 的 try/catch
    把错吞了、中宫只剩「年 月 日 时」四个空标签。负向对照：REAL_FOR_APP 去掉 lunar-javascript → 红。"""
    svg = next(f for f in _figures("cetian") if f.get("app_kind") == "cetian")["app_svg"]
    assert re.search(r">壬\s*<", svg) and re.search(r">戌\s*<", svg), "四柱 ganzhi printed in the center"


@needs_node
def test_every_tspan_carries_its_own_x() -> None:
    """svglib 排行内 <tspan> 用的是占位字体（Courier）的字宽，换回报告字体后片段互相压字；每个 tspan 自带 x（太乙那样逐行起笔）才对。
    负向对照：南印 adapter 改回「名 / 度数 / R」一个 text 里三个行内 tspan → 红。"""
    for tool in ("qimen", "india_chart", "bazi_birth", "taiyi"):
        for spec in _figures(tool):
            for tag in re.findall(r"<tspan\b[^>]*>", spec.get("app_svg") or ""):
                assert re.search(r'\sx="', tag), (tool, tag)


@needs_node
def test_drawing_conventions_of_the_skill_drawing_are_not_printed_under_app_boards() -> None:
    """规格的 legend 只描述 skill 自绘图（「每宫自上而下：八神 / 九星 天盘干…」）；换成 app 遁甲盘后版式不同，不再印。"""
    pass

    spec = next(f for f in _figures("qimen") if f.get("kind") == "grid9")
    assert spec.get("app_svg") and not any("每宫自上而下" in n for n in figure_notes(spec, str))
    builtin = {k: v for k, v in spec.items() if k != "app_svg"}
    assert any("每宫自上而下" in n for n in figure_notes(builtin, str))


def test_core_js_tools_return_the_cast_objects_the_board_needs() -> None:
    """小成图 / 轨策的正文只回卦名；app 的盘要整卦对象（爻 / 上下卦 / 互卦）与起卦结果。core-js 工具把算正文时那一份
    qi / gua 原样放进 board_context（不另算），报告盘图用 app 的 buildPan / buildGuicePan 按同一份再起。"""
    from node_esm import run_node_esm

    if not shutil.which("node"):
        pytest.skip("[host] node not on PATH")
    tools = PKG_ROOT / "horosa-core-js" / "src" / "tools"
    script = (
        "const [x, g] = await Promise.all([import(process.argv[1]), import(process.argv[2])]);"
        "const a = x.runXiaoChengTu({ qiguaFa: 'manual', up: '乾', lo: '兑', dongYaos: [3], yongGong: 1 }).data.board_context;"
        "const b = g.runGuice({ qiguaFa: 'baoshu', nums: [7, 9], hourZhi: '午', yearZhi: '午', monthZhi: '巳', lunarMonth: 4, lunarDay: 5 }).data.board_context;"
        "process.stdout.write(JSON.stringify({ a, b }));"
    )
    out = json.loads(run_node_esm(script, tools / "xiaochengtu.js", tools / "guice.js", cwd=PKG_ROOT / "horosa-core-js"))
    assert out["a"]["ben"]["lines"] and out["a"]["ben"]["up"] == "乾" and out["a"]["zhi"]["lines"]
    assert out["b"]["gua"]["up"] and out["b"]["gua"]["dongYao"]


@needs_node
def test_sanshi_board_replaces_the_liureng_grid_under_its_own_title() -> None:
    """三式合一：自绘的是六壬天地盘；app 的是三式合一盘（外圈星盘 + 奇门 + 六壬 + 课传），换上时标题随之改（不是同一种盘）。
    外圈要起课那张星盘——runner 留在 board_context；缺了就仍画自绘的六壬天地盘。"""
    figures = _figures("sanshiunited")
    board = next(f for f in figures if f.get("app_kind") == "sanshi")
    assert board["title"] == "三式合一盘"
    assert "阳遁" in board["app_svg"] and "驿马" in board["app_svg"], "the board's own info cards (旬 / 局, 神煞) are drawn"
    data = {k: v for k, v in FIXTURE["sanshiunited"].items() if k != "board_context"}
    assert all(r["kind"] != "sanshi" for _i, r in app_charts.plan("sanshiunited", data, extract_figures("sanshiunited", data, "sanshiunited")))


def test_builtin_grid_captions_keep_their_legend_in_pdf_and_docx() -> None:
    """legend 拆出后，PDF 九宫与 DOCX 格子盘的图注曾直接读 text / lines，自绘图的画法说明就丢了（只该在 app 图下不印）。"""
    import inspect

    from horosa_skill.reports import figures, renderers

    pdf = inspect.getsource(figures._pdf_flowables)
    docx = inspect.getsource(renderers)
    assert 'spec.get("text"), *(spec.get("lines")' not in pdf and 'figure.get("text"), *(figure.get("lines")' not in docx
    spec = {"kind": "grid9", "legend": ["每宫自上而下"], "text": "局"}
    assert figures.figure_notes(spec, str) == ["局", "每宫自上而下"]


def test_tall_app_boards_are_narrowed_to_fit_one_page() -> None:
    """三式合一盘 720 × 1110：按 470 pt 宽排高 725 pt，超过盘图标题下的剩余高度 → 标题孤零零留在上一页。按宽高比收窄到高 ≤ 600 pt。"""
    from horosa_skill.reports.figures import _APP_FIGURE_MAX_HEIGHT, _app_figure_width

    tall = {"app_svg": '<svg xmlns="http://www.w3.org/2000/svg" width="720" height="1110">'}
    square = {"app_svg": '<svg xmlns="http://www.w3.org/2000/svg" width="720" height="720">'}
    assert abs(_app_figure_width(tall, 470) * 1110 / 720 - _APP_FIGURE_MAX_HEIGHT) < 0.01
    assert _app_figure_width(square, 470) == 470


@needs_node
def test_the_render_process_exits_as_soon_as_its_output_is_written() -> None:
    """app 原版代码加载时留着轮询的 setTimeout：不主动退出的话每次出图都白等约 2.5 s（全技法报告测试因此慢了三成）。

    输出要远大于管道缓冲（约 64 KB）：管道下 stdout.write 是异步的，不等写完就 exit 会截断，小输出测不出来。
    """
    import subprocess
    import time

    class Recorder:
        requests: list = []

        def render_app_charts(self, figures):
            Recorder.requests = list(figures)
            return None

    app_charts.attach_app_svgs(extract_figures("chart", FIXTURE["chart"], "chart"), "chart", FIXTURE["chart"], Recorder())
    assert Recorder.requests, "chart 应该有要 app 画的图"
    def render(figures: list) -> tuple[str, float]:
        started = time.monotonic()
        completed = subprocess.run(["node", str(PKG_ROOT / "horosa-core-js" / "bin" / "cli.mjs"), "render-charts"],
                                   cwd=PKG_ROOT / "horosa-core-js", capture_output=True, input=json.dumps({"figures": figures}),
                                   text=True, encoding="utf-8", timeout=120)
        return completed.stdout, time.monotonic() - started

    # 不截断：退早了输出正好停在 65 511 字节（管道缓冲），负向对照实测。
    figures = Recorder.requests * 12
    out, _elapsed = render(figures)
    assert len(out) > 200_000, len(out)
    parsed = json.loads(out)
    assert parsed["ok"] is True and len(parsed["results"]) == len(figures) and all(r["ok"] for r in parsed["results"])
    # 不空等：本机正常 0.2 s，被定时器拖住是 2.6 s；门槛给慢的 CI 机器留了余量。
    _out, elapsed = render([])
    assert elapsed < 1.8, f"render-charts took {elapsed:.2f} s with nothing to draw: something keeps the event loop alive again"


@needs_node
def test_jinkou_without_a_run_year_drops_the_apps_on_screen_hint_and_says_why() -> None:
    """评审 R-11：结果没有行年（[行年] 无）时 app 在右下格只印「起盘后显示行年/旬日/旺衰/神煞」——给页面上还没起盘的人看的
    界面提示，印进报告是错话。adapter 去掉这句、不造数据，图下说明右下格为什么空着。"""
    spec = next(f for f in _figures("jinkou") if f.get("app_kind") == "jinkou")
    assert "起盘后显示" not in spec["app_svg"] and "贵神" in spec["app_svg"]
    assert any("右下格" in line and "没有行年" in line for line in spec.get("lines") or [])
    assert any("没有行年" in note for note in figure_notes(spec, str))
