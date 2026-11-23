"""上游 v3.14.0 同步 · 报告盘图：app 样式包重建到 e55c3a66 后必须成立的事（reports/app_charts.py + horosa-core-js/app-charts）。

v3.14.0 做了「全站界面亮暗统一」。跑 app 原版绘图代码的那些盘（D3 / SVG）重打包即跟上；照样式表手排的那些盘（HTML 重画）不会——
包重建后它们的 SVG 一字不变，正是因为数字是抄的。这里把两版之间真正变了的每一处钉成数值：

- 符号字体 ywastro 换了三个字形的度量（狮子座 e、150° 相位 V、凯龙 y）：随包字体必须就是 pin 上那个文件；
- 五行颜色全站统一：金 #ab5500、土 #7a4f2a（此前 #866a00 / #805526）；
- 小六壬：传序角标改到宫格右上竖排，一传实底；
- 小成图：宫格内边距 19 / 12 / 9、行距 8，角标一行（用宫在左、推 N 靠右）；
- 地占护盾方盘：得地角标 16 px 粗体；
- 塔罗：凯尔特十字缩简版 / 加权版的横压牌同样横置（认位置的 crossFixed）；
- 卜 · 其他各盘的页面根同时带 `horosa-astro-redesign horosa-huangji-redesign` 两个作用域，次级字色随前者。

期望值的来源：上游 `layouts/app/19-cnx-divination.less` / `12-india-tarot-geomancy.less` / `01-base.less` 的规则，以及把 app 自己的
SSR 标记放进 app 正式构建的样式表（dist-file）在无头 Chrome 里量出的盒（备忘里记了做法）——不是把当前输出抄成期望。
每条都做过负向对照（把旧数 / 旧文件放回去必红），见各用例的说明。
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest
from test_app_charts import FIXTURE, PKG_ROOT, _cjk_font, _Client

from horosa_skill.reports import app_charts
from horosa_skill.reports.figures import drawing_to_png, extract_figures, figure_drawing

CORE_JS = PKG_ROOT / "horosa-core-js"
MANIFEST = json.loads((PKG_ROOT / "contracts" / "app_charts_bundle.json").read_text(encoding="utf-8"))
BOARDS = json.loads(gzip.decompress((PKG_ROOT / "tests" / "fixtures" / "app_charts_boards_live.json.gz").read_bytes()))
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not on PATH")


def _render(kind: str, data: dict, options: dict | None = None) -> str:
    [result] = _Client().render_app_charts([{"kind": kind, "data": data, "options": options or {}}])
    assert result["ok"], result.get("error")
    return result["svg"]


def _tool_data(script: str, *modules: str) -> dict:
    """算正文的那份 core-js 工具结果（data），喂给 app 的盘。"""
    from node_esm import run_node_esm

    return json.loads(run_node_esm(script, *[CORE_JS / "src" / "tools" / name for name in modules], cwd=CORE_JS))


def _attrs(tag: str) -> dict[str, str]:
    return dict(re.findall(r'([\w:-]+)="([^"]*)"', tag))


def _rects(svg: str) -> list[dict[str, str]]:
    return [_attrs(tag) for tag in re.findall(r"<rect\b[^>]*>", svg)]


def _texts(svg: str) -> list[tuple[dict[str, str], str]]:
    return [(_attrs(tag), body) for tag, body in re.findall(r"<text\b([^>]*)>([^<]*)</text>", svg)]


# ───────────────────────────── 符号字体 ─────────────────────────────

def test_packaged_symbol_fonts_are_the_pinned_upstream_files() -> None:
    """build.mjs 把 pin 上的字体哈希记进清单并拷进包里；`--check` 对上游、这里对清单。
    负向对照：把 v3.13.2 的 ywastro.ttf 放回 data/fonts/ → 本用例红（sha eb452947… ≠ f03a941b…）。"""
    fonts = MANIFEST["fonts"]
    assert set(fonts) == {file for file, _name in app_charts.GLYPH_FONTS.values()}, "every font the report registers is pinned"
    for name, meta in fonts.items():
        body = (app_charts.FONT_DIR / name).read_bytes()
        assert hashlib.sha256(body).hexdigest() == meta["sha256"] and len(body) == meta["bytes"], name
    # ywastro 与 ywastrochart 在 app 里是同一个文件，所以两个字族才能共用一份；上游哪天分家，build.mjs 先停。
    assert fonts["ywastro.ttf"]["upstream"] == ["assets/ywastro.ttf", "assets/ywastrochart.ttf"]


def test_v3140_glyph_metrics_are_recentred_in_the_packaged_font() -> None:
    """上游 v3.14.0：「狮子座、150° 相位、凯龙三个字形的度量在字体里改正(不再压邻字、偏位或越界)」。
    旧字体里这三个字形的前进宽度是 27 / 163 / 261（千分之一 em），墨迹落在原点左侧（狮子座 −412…366、150° −630…163）；
    新字体墨迹从 0 起、前进宽度 = 墨宽。负向对照：换回旧字体 → 三个都红。"""
    from PIL import ImageFont
    from reportlab.pdfbase.ttfonts import TTFontFile

    path = str(app_charts.FONT_DIR / "ywastro.ttf")
    widths = TTFontFile(path).charWidths
    ink = ImageFont.truetype(path, 1000)
    for char, advance in (("e", 782), ("V", 633), ("y", 466)):  # AstroText: Leo / Asp150 / Chiron
        assert round(widths[ord(char)]) == advance, (char, widths[ord(char)])
        left, _top, right, _bottom = ink.getbbox(char, anchor="ls")
        assert left == 0 and abs(right - advance) <= 1, f"{char}: ink {left}…{right} must sit inside its advance {advance}"


def test_declination_ladder_glyph_advances_are_the_packaged_fonts() -> None:
    """adapters/declination.js 手抄了七曜 + 三王星字形的前进宽度（HTML 弹性行要它来排度数）：与随包字体逐个核。"""
    from reportlab.pdfbase.ttfonts import TTFontFile

    source = (CORE_JS / "app-charts" / "adapters" / "declination.js").read_text(encoding="utf-8")
    table = dict(re.findall(r"([A-Z]): ([\d.]+)", re.search(r"const GLYPH_ADVANCE = \{([^}]*)\}", source).group(1)))
    widths = TTFontFile(str(app_charts.FONT_DIR / "ywastro.ttf")).charWidths
    assert len(table) == 10
    assert {char: round(widths[ord(char)] / 1000, 3) for char in table} == {char: float(value) for char, value in table.items()}


# ───────────────────────────── 主题令牌 ─────────────────────────────

@needs_node
def test_five_element_colours_are_the_v3140_unified_set() -> None:
    """01-base.less 亮色：--horosa-bazi-metal #ab5500、--horosa-bazi-earth #7a4f2a（v3.13.2 是 #866a00 / #805526）。
    八字、奇门、五兆、金口诀的干支都按这一套上色。负向对照：换回 v3.13.2 的包 → 四个盘都还印着旧色 → 红。"""
    for tool, kind in (("bazi_birth", "bazi"), ("qimen", "qimen"), ("wuzhao", "wuzhao"), ("jinkou", "jinkou")):
        data = FIXTURE[tool]
        figures = app_charts.attach_app_svgs(extract_figures(tool, data, tool), tool, data, _Client())
        svg = next(f for f in figures if f.get("app_kind") == kind)["app_svg"].lower()
        assert "#ab5500" in svg or "#7a4f2a" in svg, f"{tool}: 金 / 土 must be drawn in the unified colours"
        assert "#866a00" not in svg and "#805526" not in svg, f"{tool}: v3.13.2 five-element colours left in the figure"


@needs_node
def test_page_scopes_combine_and_the_astro_scope_repoints_the_secondary_ink() -> None:
    """卜 · 其他各页的根是 `horosa-astro-redesign horosa-huangji-redesign`：前者把 --horosa-text-secondary 改指 astro-muted
    （亮色 = --horosa-text-soft #5f584c），后者给 huangji 令牌。只认一个作用域时次级字色落回全局的 #6f695f（小成图中宫、五兆）。
    负向对照：index.js 改回只认单个作用域名 → 两个断言都红。"""
    import subprocess

    script = ("const b=require(process.argv[1]);"
              "const svg='<a fill=\"var(--horosa-text-secondary, #6b7280)\" stroke=\"var(--horosa-huangji-cta-bg, #000)\"/>';"
              "process.stdout.write(JSON.stringify([b.resolveThemeVars(svg,'horosa-astro-redesign horosa-huangji-redesign'),"
              "b.resolveThemeVars(svg,'horosa-huangji-redesign'),b.resolveThemeVars(svg)]))")
    both, huangji, bare = json.loads(subprocess.run(["node", "-e", script, str(CORE_JS / "dist" / "app-charts.cjs")],
                                                   capture_output=True, text=True, encoding="utf-8", check=True).stdout)
    assert both == '<a fill="#5f584c" stroke="#7d5419"/>', both
    assert huangji == '<a fill="#6f695f" stroke="#7d5419"/>', huangji
    assert bare == '<a fill="#6f695f" stroke="#000"/>', bare
    xct = _tool_data("const x = await import(process.argv[1]);"
                     "process.stdout.write(JSON.stringify(x.runXiaoChengTu({ qiguaFa: 'manual', up: '乾', lo: '兑', dongYaos: [3], yongGong: 1 }).data));",
                     "xiaochengtu.js")
    centre = [attrs for attrs, body in _texts(_render("xiaochengtu", {"xiaochengtu": xct})) if body in {"五·十", "中宫无卦"}]
    assert len(centre) == 2 and {attrs["fill"] for attrs in centre} == {"#5f584c"}, centre


# ───────────────────────────── 小六壬 ─────────────────────────────

@needs_node
def test_xiaoliuren_sequence_badges_stack_at_the_palace_corner_and_the_first_is_filled() -> None:
    """19-cnx-divination.less（v3.14.0）：`.horosa-xlr-page .horosa-cnx-cell-sq .horosa-cnx-cell-seqs { top: 5px; right: 5px;
    flex-direction: column; align-items: flex-end; gap: 2px }`、角标 `padding: 0 4px; line-height: 14px`（连边 16 高）；
    `.horosa-cnx-seq.is-1` 实底 --horosa-huangji-cta-bg #7d5419 配 #fffaf0 字，二传 30 %、三传 12 % 的金底。
    三数 1、1、2（道门九宫）一传二传同落大安：两个角标同一右沿、竖着相隔 18。
    负向对照：adapter 改回横排（y 同、x 递减）→「同一右沿」红；去掉 is-1 的实底 → 颜色红。"""
    data = _tool_data("const l = await import(process.argv[1]);"
                      "process.stdout.write(JSON.stringify(l.runXiaoLiuRen({ nums: [1, 1, 2], school: 'dao' }).data));", "xiaoliuren.js")
    assert [c["name"] if isinstance(c, dict) else c for c in data["chuan"]][:2] == ["大安", "大安"], "the case needs two 传 on one palace"
    svg = _render("xiaoliuren", {"xiaoliuren": data})
    badges = {}
    rects = _rects(svg)
    for attrs, body in _texts(svg):
        if body in {"一传", "二传", "三传"} and attrs["font-size"] == "10":
            x, y = float(attrs["x"]), float(attrs["y"])
            box = next(r for r in rects if r.get("height") == "15" and abs(float(r["x"]) + float(r["width"]) / 2 - x) < 0.6 and abs(float(r["y"]) + 7.5 - y) < 0.6)
            badges[body] = (box, attrs)
    assert set(badges) == {"一传", "二传", "三传"}
    first, second = badges["一传"][0], badges["二传"][0]
    right = lambda r: float(r["x"]) + float(r["width"])  # noqa: E731
    assert abs(right(first) - right(second)) < 0.01, "stacked badges share the right edge"
    assert abs(float(second["y"]) - float(first["y"]) - 18) < 0.01, "16 px pill + 2 px gap"
    assert first["fill"] == "#7d5419" and first["stroke"] == "#7d5419" and badges["一传"][1]["fill"] == "#fffaf0"
    assert second["fill"] == "rgba(154, 106, 37, 0.3)" and badges["三传"][0]["fill"] == "rgba(154, 106, 37, 0.12)"
    assert badges["二传"][1]["fill"] == badges["三传"][1]["fill"] == "#9b6a2d"
    # 角标贴宫格右上角：距宫格外沿 6（1 px 边 + 5）。宫格 = 202 见方的大方框。
    cell = next(r for r in rects if r.get("rx") == "10" and abs(float(r["width"]) - 201) < 0.01
                and float(r["x"]) < float(first["x"]) < float(r["x"]) + 201 and float(r["y"]) < float(first["y"]) < float(r["y"]) + 201)
    # 矩形都按半像素落笔（x + 0.5、宽 − 1）：外沿 = 属性值 ± 0.5
    assert abs((float(cell["x"]) - 0.5 + 202) - (right(first) + 0.5) - 6) < 0.01 and abs(float(first["y"]) - float(cell["y"]) - 6) < 0.01


@needs_node
def test_xiaoliuren_board_is_laid_out_as_the_app_does_at_a_desktop_window() -> None:
    """app 自己的版式（680 px 盘、桌面窗口，Chrome 里量）：盘内边距 26（+1 边）、九宫 202 见方、宫名 23 px、三传条 102 高、
    整盘 879.1 高（六宫 667.1）。此前按约 1050 px 窗口的 clamp 值手排（内边距 22、宫名 21、整盘 861）。"""
    for school, height in (("dao", 880), ("main", 668)):
        data = _tool_data("const l = await import(process.argv[1]);"
                          f"process.stdout.write(JSON.stringify(l.runXiaoLiuRen({{ nums: [5, 20, 7], school: '{school}' }}).data));", "xiaoliuren.js")
        svg = _render("xiaoliuren", {"xiaoliuren": data})
        assert f'width="680" height="{height}"' in svg[:120], svg[:120]
        names = [attrs for attrs, body in _texts(svg) if attrs.get("font-size") == "23"]
        assert len(names) == (9 if school == "dao" else 6) and {attrs["font-weight"] for attrs in names} == {"800"}
        cells = [r for r in _rects(svg) if r.get("rx") == "10" and abs(float(r["width"]) - 201) < 0.01 and abs(float(r["height"]) - 201) < 0.01]
        assert len(cells) == len(names) and min(float(r["x"]) for r in cells) == 27.5


# ───────────────────────────── 小成图 ─────────────────────────────

@needs_node
def test_xiaochengtu_palaces_carry_the_v3140_padding_and_badge_row() -> None:
    """19-cnx-divination.less（v3.14.0）：`.horosa-xct-cell { gap: 8px; padding: 19px 12px 9px }`（此前 9 / 14px 12px）；
    角标行 `top: 3px; left: 6px; right: 6px`，`.is-step { margin-left: auto }`——用宫在左、推 N 贴右。
    桌面窗口下宫名 44 px（clamp 上限）：宫高 = 2 + 19 + 9 + 18 + 8 + 44 + 8 + 13.5 × 1.5715 = 129.2，卦画顶 = 宫顶 + 20。
    负向对照：把内边距改回 14 / 14、行距 9 → 卦画顶与宫名中线两条断言红；角标改回右上横排 → 用宫的左沿断言红。"""
    data = _tool_data("const x = await import(process.argv[1]);"
                      "process.stdout.write(JSON.stringify(x.runXiaoChengTu({ qiguaFa: 'manual', up: '乾', lo: '兑', dongYaos: [3], yongGong: 1 }).data));",
                      "xiaochengtu.js")
    svg = _render("xiaochengtu", {"xiaochengtu": data})
    rects, texts = _rects(svg), _texts(svg)
    cells = [r for r in rects if r.get("rx") == "10" and abs(float(r["height"]) - 128.2152) < 0.01]
    assert len(cells) == 9, "nine palaces of 129.2 (border included)"
    step = next((attrs, body) for attrs, body in texts if re.fullmatch(r"推\d", body))
    yong = next((attrs, body) for attrs, body in texts if body == "用宫" and attrs["font-size"] == "10")
    home = next(r for r in cells if float(r["x"]) < float(yong[0]["x"]) < float(r["x"]) + float(r["width"])
                and float(r["y"]) < float(yong[0]["y"]) < float(r["y"]) + float(r["height"]))
    x0, y0, width = float(home["x"]) - 0.5, float(home["y"]) - 0.5, float(home["width"]) + 1
    yong_box = next(r for r in rects if r.get("height") == "14" and abs(float(r["y"]) - (y0 + 4.5)) < 0.01 and float(r["x"]) < float(yong[0]["x"]) < float(r["x"]) + float(r["width"]))
    assert abs(float(yong_box["x"]) - (x0 + 7.5)) < 0.01, "用宫 starts 6 px inside the border, 3 px below it"
    assert yong_box["fill"] == "#7d5419" and yong[0]["fill"] == "#fffaf0", "用宫 is an is-1 badge: filled"
    step_boxes = [r for r in rects if r.get("height") == "14" and float(r["x"]) < float(step[0]["x"]) < float(r["x"]) + float(r["width"])
                  and abs(float(r["y"]) + 7 - float(step[0]["y"])) < 1]
    assert step_boxes, "推N badge drawn"
    step_cell = next(r for r in cells if float(r["x"]) < float(step[0]["x"]) < float(r["x"]) + float(r["width"])
                     and float(r["y"]) < float(step[0]["y"]) < float(r["y"]) + float(r["height"]))
    assert abs((float(step_cell["x"]) - 0.5 + width) - (float(step_boxes[0]["x"]) + float(step_boxes[0]["width"])) - 7.5) < 0.01, "推N sits at the right edge"
    # 卦画（30 × 4 的条）顶在宫顶 + 20；宫名 44 px 的中线在宫顶 + 68；地盘行中线在宫顶 + 108.6
    bars_top = min(float(r["y"]) for r in rects if r.get("width") in {"30", "12"} and r.get("height") == "4"
                   and x0 < float(r["x"]) < x0 + width and y0 < float(r["y"]) < y0 + 129.3)
    assert abs(bars_top - (y0 + 20)) < 0.01, bars_top - y0
    name = next(attrs for attrs, _body in texts if attrs.get("font-size") == "44" and x0 < float(attrs["x"]) < x0 + width and y0 < float(attrs["y"]) < y0 + 129.3)
    assert abs(float(name["y"]) - (y0 + 68)) < 0.01 and name["font-weight"] == "800"
    meta = next(attrs for attrs, _body in texts if attrs.get("font-size") == "13.5" and x0 < float(attrs["x"]) < x0 + width and y0 < float(attrs["y"]) < y0 + 129.3)
    assert abs(float(meta["y"]) - (y0 + 108.6076)) < 0.01


# ───────────────────────────── 地占 · 灵棋 ─────────────────────────────

@needs_node
def test_geomancy_tenancy_mark_is_the_v3140_corner_badge() -> None:
    """12-india-tarot-geomancy.less（v3.14.0）：`.horosa-geomancy-shield-tenancy { top: 6px; right: 7px; font-size: 16px;
    font-weight: 700 }`（此前 3 / 4、11 px、常规体、不透明度 .9）。每格一枚，右沿 = 格右沿 − 8（1 px 边 + 7）。
    负向对照：字号改回 11 → 红。"""
    data = FIXTURE["geomancy"]
    figures = app_charts.attach_app_svgs(extract_figures("geomancy", data, "geomancy"), "geomancy", data, _Client())
    svg = figures[0]["app_svg"]
    marks = [attrs for attrs, body in _texts(svg) if body in {"◎", "○", "◇", "✕"}]
    assert len(marks) == 16 and {(attrs["font-size"], attrs["font-weight"], attrs["text-anchor"]) for attrs in marks} == {("16", "700", "end")}
    cells = [r for r in _rects(svg) if r.get("rx") == "12"]
    assert len(cells) == 16
    for mark in marks:
        x, y = float(mark["x"]), float(mark["y"])
        cell = next(r for r in cells if float(r["x"]) < x <= float(r["x"]) + float(r["width"]) + 1 and float(r["y"]) < y < float(r["y"]) + float(r["height"]))
        assert abs((float(cell["x"]) + float(cell["width"]) + 0.5) - x - 8) < 0.01 and abs(y - (float(cell["y"]) - 0.5) - 15) < 0.01


@needs_node
def test_lingqi_layers_follow_the_apps_own_layout() -> None:
    """21-lingqi.less（两版相同；此前 adapter 画的是另一种版式）：层名在 66 px 的居中列里，24 px 金色粗体，下面是位（11 px）与枚数
    小牌（11 px、17 px 行、圆角 8 的细框）；棋子 72 px（2 px 边）在右侧区域居中、相隔 20。量自 app：行高 106、行距 18。
    负向对照：层名改回左对齐黑字 20 px / 棋子 58 → 红。"""
    data = FIXTURE["lingqi"]
    figures = app_charts.attach_app_svgs(extract_figures("lingqi", data, "lingqi"), "lingqi", data, _Client())
    svg = figures[0]["app_svg"]
    texts = _texts(svg)
    labels = [attrs for attrs, body in texts if body in {"上", "中", "下"} and attrs["font-size"] == "24"]
    assert len(labels) == 3 and {(attrs["fill"], attrs["font-weight"], attrs["text-anchor"], attrs["x"]) for attrs in labels} == {("#9a6a25", "700", "middle", "78")}
    assert [round(float(b["y"]) - float(a["y"]), 2) for a, b in zip(labels, labels[1:])] == [124.0, 124.0], "106 px rows, 18 px apart"
    counts = [attrs for attrs, body in texts if re.fullmatch(r"\d 枚", body)]
    assert len(counts) == 3 and all(attrs["text-anchor"] == "middle" and attrs["x"] == "78" for attrs in counts)
    pills = [r for r in _rects(svg) if r.get("rx") == "8" and r.get("height") == "18" and r.get("fill") == "none"]
    assert len(pills) == 3, "each 枚数 sits in its outlined pill"
    chips = re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="35" fill="(#f6efdd|#d8ccb2)" stroke="([^"]+)" stroke-width="2"', svg)
    assert len(chips) == 12 and sorted({float(cx) for cx, *_ in chips}) == [245.0, 337.0, 429.0, 521.0], "four 72 px chips, 20 px apart, centred in their area"
    assert {(fill, stroke) for _cx, _cy, fill, stroke in chips} == {("#f6efdd", "rgba(154, 106, 37, 0.55)"), ("#d8ccb2", "rgba(110, 100, 82, 0.5)")}


# ───────────────────────────── app 原版代码跟到 v3.14.0 ─────────────────────────────

@needs_node
def test_tarot_crossing_card_lies_across_in_every_celtic_variant() -> None:
    """TarotMain（v3.14.0）：横压牌认位置的 crossFixed，不认牌阵名——缩简版 celtic6 / 加权版 celtic11 的第 2 张同样横置 90°
    （v3.13.2 只转标准 10 张版，另两种两张牌整张叠住）。负向对照：换回 v3.13.2 的包 → celtic6 / celtic11 没有 rotate(90) → 红。"""
    for spread in ("celtic", "celtic6", "celtic11"):
        data = _tool_data("const t = await import(process.argv[1]);"
                          f"process.stdout.write(JSON.stringify(t.runTarot({{ seed: 'horosa', spread: '{spread}', deck: 'rws' }}).data));", "tarot.js")
        board = data["board_context"]
        assert board["draws"][1]["position"]["x"] == board["draws"][0]["position"]["x"], "the crossing card shares the first card's spot"
        svg = _render("tarot", {"board_context": board}, {"size": 760, "art": app_charts.tarot_art_sizes()})
        assert len(re.findall(r"rotate\(90\)", svg)) == 1, f"{spread}: exactly the crossing card is turned"


@needs_node
def test_the_bundle_draws_with_the_v3140_app_code() -> None:
    """重打包即跟上的几处（app 原版代码）：赤纬梯 0° 刻度不再与「赤道 0°」叠印；紫微中宫时区写 UTC+08:00（zoneText）；
    大六壬盘字一律 stroke="none"；巴比伦 / 米雄的 svg 根挂 horosa-plain-text-board（报告本来就不给字描边，等价）。
    负向对照：换回 v3.13.2 的包 → 四条全红。（包与 pin 是否同源归 test_app_charts 的 pin 守卫，这里不再钉提交号。）"""
    zw = app_charts.attach_app_svgs(extract_figures("ziwei_birth", FIXTURE["ziwei_birth"], "ziwei_birth"), "ziwei_birth", FIXTURE["ziwei_birth"], _Client())[0]["app_svg"]
    assert "时区：UTC+08:00" in zw
    lr = next(f for f in app_charts.attach_app_svgs(extract_figures("liureng_gods", FIXTURE["liureng_gods"], "liureng_gods"), "liureng_gods",
                                                    FIXTURE["liureng_gods"], _Client()) if f.get("app_kind") == "liureng")["app_svg"]
    opening = re.findall(r"<text\b[^>]*>", lr)
    assert opening and all('stroke="none"' in tag for tag in opening)
    for tool, kind in (("babylon", "babylon"), ("michon", "michon")):
        svg = next(f for f in app_charts.attach_app_svgs(extract_figures(tool, FIXTURE[tool], tool), tool, FIXTURE[tool], _Client()) if f.get("app_kind") == kind)["app_svg"]
        assert 'class="horosa-plain-text-board"' in svg[:200], tool


# ───────────────────────────── 两条出图路径 · 规整规则 ─────────────────────────────

def _all_figures() -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for tool in sorted(key for key in FIXTURE if not key.startswith("_") and key != "sixyao"):
        base = "tarot" if tool.startswith("tarot_") else tool
        data = FIXTURE[tool]
        for index, spec in enumerate(app_charts.attach_app_svgs(extract_figures(base, data, base), base, data, _Client())):
            out.append((f"{tool}#{index}", spec))
    data = BOARDS["heluo"]
    for index, spec in enumerate(app_charts.attach_app_svgs(extract_figures("heluo", data, "heluo"), "heluo", data, _Client())):
        out.append((f"heluo#{index}", spec))
    return out


@needs_node
def test_every_kind_survives_both_output_paths_and_the_normalising_rules() -> None:
    """既有夹具里的每一张 app 图：①规整后不剩 svglib 不认的东西（var() / currentColor / dominant-baseline / 行内 tspan /
    内联 style 里的字族 / 未注册的字族）；②矢量路径（svglib → reportlab，PDF 用）转得出、字体全是嵌入的；③位图路径（Pillow，
    DOCX / PNG 用）出得了图。此前只对 chart / ziwei_birth 两张做②③。"""
    from reportlab.graphics.shapes import String

    regular, bold, files = _cjk_font()
    allowed_families = {app_charts.TEXT_FAMILY, app_charts.TEXT_BOLD_FAMILY, app_charts.OPTIONAL_FAMILY, *(name for _file, name in app_charts.GLYPH_FONTS.values())}
    figures = _all_figures()
    kinds = {spec.get("app_kind") for _label, spec in figures}
    assert kinds >= set(MANIFEST["kinds"]) - {"liuyao", "declination_ladder", "guolao_moira"}, sorted(set(MANIFEST["kinds"]) - kinds)
    for label, spec in figures:
        assert spec.get("renderer") == "app" and spec.get("app_svg"), (label, spec.get("renderer_note"))
        svg = spec["app_svg"]
        assert "var(" not in svg and "currentColor" not in svg, label
        normal = app_charts.normalize_svg(svg)
        assert "dominant-baseline" not in normal and "alignment-baseline" not in normal, label
        for tag in re.findall(r"<tspan\b[^>]*>", normal):
            assert re.search(r'\sx="', tag), (label, tag)
        for tag in re.findall(r"<(?:text|tspan)\b[^>]*>", normal):
            assert not re.search(r'style="[^"]*font-family', tag), (label, tag)
        families = set(re.findall(r'font-family="([^"]*)"', normal))
        assert families <= allowed_families, (label, families - allowed_families)
        drawing = figure_drawing(dict(spec), 400, regular, bold, None)
        assert drawing is not None and spec.get("renderer") == "app", (label, spec.get("renderer_note"))
        names: set[str] = set()

        def walk(node):
            for child in getattr(node, "contents", None) or []:
                if isinstance(child, String):
                    names.add(child.fontName)
                else:
                    walk(child)

        walk(drawing)
        assert names <= {regular, bold, *app_charts.glyph_font_files()}, (label, names)
        png = drawing_to_png(drawing, files, scale=1.0)
        assert png and png[:4] in {b"\x89PNG", b"\xff\xd8\xff\xe0"}, label
