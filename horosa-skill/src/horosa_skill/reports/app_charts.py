"""盘图用星阙 app 自己的样式：跑 app 原版绘图代码出 SVG，转成 reportlab 矢量图。

- 出图：`horosa-core-js/dist/app-charts.cjs`（`app-charts/build.mjs` 从 Horosa-Public 打包）在 Node 里用 app 的组件画——
  西洋盘是 `AstroChartCircle`、紫微是 `ZWChart`，喂的就是 app 喂给它们的那份引擎结果。这里不算任何位置（铁律 1）。
- 接入：`attach_app_svgs` 在报告渲染前对 `extract_figures` 的规格逐张配 app 图（一次 Node 调用），成功的规格多一个
  `app_svg`；`figures.figure_drawing` 有 `app_svg` 就画它，没有（旧 runtime 没带 bundle、Node 起不来、这张没对上）就画原来的图，
  规格里 `renderer` 写明用的是哪一种（`app` / `builtin`）及原因——退回不是静默的。
- 转换：svglib 读 SVG。先做几处无损规整：`transparent` → none、`var(--x, 回退)` → 回退值（app 的浅色主题值就写在回退里）、
  rgba → 颜色 + 透明度、数字字重 → 常规 / 粗体；字族只留 app 的符号字体（ywastro / morinus，随包 `data/fonts/`），其余文字一律用报告
  本身嵌入的 TrueType 字体（PDF/UA 要求字体全嵌；也保证中文不出方块）。
- 关掉：`HOROSA_APP_CHARTS=0` 只画原来的图（排查用）。
"""

from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any

FONT_DIR = Path(__file__).resolve().parents[1] / "data" / "fonts"
# SVG font-family → (随包字体文件, reportlab 注册名)。ywastro 与 ywastrochart 在 app 里是同一个文件。
GLYPH_FONTS = {
    "ywastrochart": ("ywastro.ttf", "HorosaGlyphYwastro"),
    "ywastro": ("ywastro.ttf", "HorosaGlyphYwastro"),
    "morinus": ("morinus-webfont.ttf", "HorosaGlyphMorinus"),
}
TEXT_FAMILY = "HorosaReportText"
TEXT_BOLD_FAMILY = "HorosaReportTextBold"

# 西洋轮：取 `figures._wheels` 记下的那一层（`source`：根 / dirChart / natalChart / charts.春分…），整份交给 app 的 AstroChartCircle。
# 不走 app 画法的：巴比伦（无宫位体系，app 用另一套 components/babylon）。合盘双圈走 drawDoubleChart（bi_wheel）。
_WHEEL_SKIP_TOOLS = frozenset({"babylon"})
_ZIWEI_TOOLS = frozenset({"ziwei_birth", "ziweizeri"})
_GUOLAO_TOOLS = frozenset({"guolao_chart", "qizhengzeri"})  # 七政择日动盘（qizhengelection）是另一种盘，不在此列
_HEAVY_KEYS = frozenset({"export_snapshot", "technique_card", "snapshot_text"})


def _dig(data: Any, path: list[str] | tuple[str, ...]) -> Any:
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def enabled() -> bool:
    return os.environ.get("HOROSA_APP_CHARTS", "1").strip().lower() not in {"0", "false", "off", "no"}


def plan(tool_name: str, data: Any, figures: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
    """(规格序号, Node 请求) 列表：哪几张图可以换成 app 的画法、喂什么数据。"""
    if not isinstance(data, dict):
        return []
    source = data["base"] if data.get("pan_moment") and isinstance(data.get("base"), dict) else data
    requests: list[tuple[int, dict[str, Any]]] = []
    for index, spec in enumerate(figures):
        kind = spec.get("kind")
        if kind == "wheel" and spec.get("outer_bodies") and isinstance(_dig(source, ["inner", "chart"]), dict) and isinstance(_dig(source, ["outer", "chart"]), dict):
            # 合盘双圈：与自绘图同一安排（内圈甲方宫位与行星、外圈乙方行星）= app AstroDoubleChartMain 的「星盘B」页
            pick = lambda layer: {key: layer[key] for key in ("params", "chart", "aspects", "lots") if key in layer}  # noqa: E731
            requests.append((index, {"kind": "bi_wheel", "data": {"natualChart": pick(source["inner"]), "dirChart": pick(source["outer"])},
                                     "options": {"size": 760}}))
        elif kind == "wheel" and tool_name not in _WHEEL_SKIP_TOOLS and not spec.get("outer_bodies") and isinstance(spec.get("source"), list):
            layer = _dig(source, spec["source"])
            if isinstance(layer, dict) and isinstance(layer.get("chart"), dict):
                payload = {key: value for key, value in layer.items() if key not in _HEAVY_KEYS}
                if not isinstance(payload.get("aspects"), dict):
                    # 自绘轮连了相位线 = 这一层的相位在根上 / raw 里（本命类、卜卦、择日）；没连就给空表，app 也不画线。
                    aspects = (_dig(source, ["aspects"]) or _dig(source, ["raw", "aspects"])) if spec.get("aspects") else None
                    payload["aspects"] = aspects if isinstance(aspects, dict) else {"normalAsp": {}}
                if not isinstance(payload.get("params"), dict) and isinstance(source.get("params"), dict):
                    payload["params"] = source["params"]  # 黄道 / 界 / 三分主星口径跟着本次请求走
                requests.append((index, {"kind": "natal_wheel", "data": payload, "options": {"size": 760}}))
        elif kind == "grid12" and tool_name in _ZIWEI_TOOLS and isinstance(source.get("chart"), dict):
            requests.append((index, {"kind": "ziwei", "data": {"chart": source["chart"]}, "options": {"size": 780}}))
        elif kind == "taiyi" and isinstance(source.get("pan") if isinstance(source.get("pan"), dict) else source.get("taiyi"), dict):
            # 与 figures._taiyi 同一份 pan（太乙 / 太乙择时在 pan，三式合一 / 三式择时在 taiyi）→ app 的 TaiyiBoardSvg
            pan = source["pan"] if isinstance(source.get("pan"), dict) else source["taiyi"]
            requests.append((index, {"kind": "taiyi", "data": {"pan": pan}, "options": {}}))
        elif kind == "grid12" and tool_name in _GUOLAO_TOOLS and isinstance(_dig(source, ["chart", "fixedStarSu28"]), (list, dict)):
            payload = {key: source[key] for key in ("params", "chart", "aspects", "lots") if key in source}
            requests.append((index, {"kind": "guolao", "data": payload, "options": {"size": 760}}))
    return requests


def attach_app_svgs(figures: list[dict[str, Any]], tool_name: str, data: Any, client: Any) -> list[dict[str, Any]]:
    """给能换的规格配上 app 原版 SVG（`app_svg`），其余标 `renderer: builtin` + 原因。返回新列表，不改入参。"""
    out = [dict(spec) for spec in figures]
    requests = plan(tool_name, data, out) if enabled() else []
    for spec in out:
        spec.setdefault("renderer", "builtin")
    if not requests:
        return out
    results = None
    failure = "app-charts bundle unavailable"
    render = getattr(client, "render_app_charts", None)
    if callable(render):
        try:
            results = render([request for _index, request in requests])
        except Exception as exc:  # noqa: BLE001 — 拿不到 app 的图就画原来的图，原因写进每张规格的 renderer_note
            failure = f"app-charts call failed: {type(exc).__name__}: {exc}"
            results = None
    for position, (index, request) in enumerate(requests):
        result = results[position] if results else None
        if result and result.get("ok") and isinstance(result.get("svg"), str):
            out[index].update(renderer="app", app_kind=request["kind"], app_svg=result["svg"])
        else:
            reason = failure if results is None else str((result or {}).get("error") or "render failed")
            out[index]["renderer_note"] = f"app {request['kind']}: {reason}"
    return out


# ───────────────────────────── SVG 规整 ─────────────────────────────

_VAR = re.compile(r"var\(\s*--[\w-]+\s*,\s*((?:[^()]|\([^()]*\))*)\)")
_RGBA = re.compile(r'(fill|stroke)="rgba\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)"')
_WEIGHT = re.compile(r'font-weight="(\d+|bold|normal)"')
_FAMILY = re.compile(r'font-family="([^"]*)"')
_TEXT_OPEN = re.compile(r"<(text|tspan)\b([^>]*)>")


def _resolve_vars(svg: str) -> str:
    for _ in range(4):  # var(--a, var(--b, #fff)) 嵌套最多两三层
        updated = _VAR.sub(lambda m: m.group(1).strip(), svg)
        if updated == svg:
            break
        svg = updated
    return svg


def _rgba(match: re.Match[str]) -> str:
    attr, r, g, b, a = match.groups()
    return f'{attr}="#{int(float(r)):02x}{int(float(g)):02x}{int(float(b)):02x}" {attr}-opacity="{a}"'


def _family(value: str, bold: bool) -> str:
    for name in (part.strip().strip("'\"").lower() for part in value.split(",")):
        if name in GLYPH_FONTS:
            return GLYPH_FONTS[name][1]
    return TEXT_BOLD_FAMILY if bold else TEXT_FAMILY


def normalize_svg(svg: str) -> str:
    svg = _resolve_vars(svg)
    svg = re.sub(r'(fill|stroke)="transparent"', r'\1="none"', svg)
    svg = _RGBA.sub(_rgba, svg)

    def text_tag(match: re.Match[str]) -> str:
        tag, attrs = match.groups()
        weight = _WEIGHT.search(attrs)
        bold = bool(weight) and (weight.group(1) == "bold" or (weight.group(1).isdigit() and int(weight.group(1)) >= 600))
        family = _FAMILY.search(attrs)
        if tag == "tspan" and not family and not weight:
            return match.group(0)  # 不带字族的 tspan 继承 <text> 的
        attrs = _WEIGHT.sub("", _FAMILY.sub("", attrs))
        return f'<{tag}{attrs} font-family="{_family(family.group(1) if family else "", bold)}">'

    svg = _TEXT_OPEN.sub(text_tag, svg)
    # 外层 <g> 上的 font-family / font-weight（文字继承）也要落到我们注册过的字族
    svg = re.sub(r'(<g\b[^>]*?)font-family="([^"]*)"', lambda m: f'{m.group(1)}font-family="{_family(m.group(2), False)}"', svg)
    svg = _WEIGHT.sub("", svg)
    return svg


# ───────────────────────────── SVG → reportlab ─────────────────────────────

# svglib 只肯把字族映射到 PDF 标准 14 字体（映射到别的已注册字体会静默落回 Helvetica）。于是文字字族先映射到 Courier /
# Courier-Bold（app 从不用 Courier，规整时其余字族都已改成这两个占位名），转完再把这两个名字换成报告嵌入的 TrueType 字体。
_TEXT_PLACEHOLDERS = {"Courier": "regular", "Courier-Bold": "bold"}


def _register_fonts() -> None:
    from svglib.fonts import get_global_font_map

    font_map = get_global_font_map()
    for file_name, rl_name in sorted({(f, n) for f, n in GLYPH_FONTS.values()}):
        font_map.register_font(rl_name, str(FONT_DIR / file_name), rlgFontName=rl_name)
    font_map.register_font(TEXT_FAMILY, rlgFontName="Courier")
    font_map.register_font(TEXT_BOLD_FAMILY, rlgFontName="Courier-Bold")


def _swap_text_fonts(node: Any, text_font: str, bold_font: str) -> None:
    from reportlab.graphics.shapes import String

    for child in getattr(node, "contents", []) or []:
        if isinstance(child, String):
            role = _TEXT_PLACEHOLDERS.get(child.fontName)
            if role:
                child.fontName = bold_font if role == "bold" else text_font
        else:
            _swap_text_fonts(child, text_font, bold_font)


def svg_drawing(svg: str, width: float, *, text_font: str, bold_font: str, problems: list[str] | None = None) -> Any | None:
    """app SVG → 宽 `width` 的 reportlab Drawing（矢量）。转不了返回 None 并把原因追加进 `problems`，调用方画原来的图。"""
    try:
        from svglib.svglib import svg2rlg

        _register_fonts()
        drawing = svg2rlg(io.BytesIO(normalize_svg(svg).encode("utf-8")))
    except Exception as exc:  # noqa: BLE001 — 任何解析失败都退回原画法；原因交给调用方写进 renderer_note
        if problems is not None:
            problems.append(f"{type(exc).__name__}: {exc}")
        return None
    if drawing is None or not drawing.width:
        if problems is not None:
            problems.append("svglib returned an empty drawing")
        return None
    _swap_text_fonts(drawing, text_font, bold_font)
    factor = width / float(drawing.width)
    drawing.scale(factor, factor)
    drawing.width, drawing.height = drawing.width * factor, drawing.height * factor
    return drawing


def glyph_font_files() -> dict[str, tuple[str, int]]:
    """reportlab 字体名 → (字体文件, 子字体序号)：位图（DOCX / PNG）画 app 图时要用到符号字体。"""
    return {rl_name: (str(FONT_DIR / file_name), 0) for file_name, rl_name in GLYPH_FONTS.values()}
