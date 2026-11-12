"""盘图 PNG（报告 format=png）：把 `figures.extract_figures` 的盘图规格画成位图，一张盘一个文件。

- 盘图本身只来自引擎数据：规格由 extract_figures 取（不算任何东西；正文与数据对不上的整张不画），这里只负责画。
  星盘轮 / 卦象 / 太乙盘 / 90° 度盘用 PDF 同一份矢量画法（figures.figure_drawing）转位图；十二宫 / 九宫格子盘在 PDF / DOCX 里
  是表格，这里另画成格子图（同样的格位、同样的字段，不增删内容）。图上方印图名，下方印图例说明（与 PDF 图题同一份 figure_notes）。
- 字体：用 PDF 选中的那一对中文字体（renderers._drawing_font_files，同一张候选表 `_PDF_FONT_CANDIDATES`）。本机没有可用的
  TrueType 中文字体 → `PngFontUnavailable`；字体缺图上要画的字 → 同样拒绝并列出缺的字。绝不画出方块字。
- 尺寸：长边不超过 PNG_LONG_EDGE_MAX（Claude 标准档原生长边 1568 px，不被再缩放；也远低于多图请求的 3000 px 限制）。
"""
from __future__ import annotations

import io
import math
from typing import Any

from horosa_skill.reports import figures as figure_kit

PNG_LONG_EDGE_MAX = 1568
_INK, _MUTED, _TEAL, _AMBER = "#14211f", "#66706d", "#0f766e", "#b7791f"
_GRID_RULE, _CENTER_FILL, _EMPHASIS_FILL = "#c9d3ce", "#f3f7f5", "#eef6f2"


class PngFontUnavailable(Exception):
    """画不出不带方块字的 PNG：本机没有可用的中文 TrueType 字体（missing 为空），或字体缺 missing 里的字。"""

    def __init__(self, missing: list[str] | None = None) -> None:
        self.missing = sorted(set(missing or []))
        super().__init__("missing glyphs: " + "".join(self.missing) if self.missing else "no CJK TrueType font")


def _fonts(script: str) -> dict[str, Any]:
    from horosa_skill.reports import renderers

    fonts = renderers._drawing_font_files(script)
    if fonts is None:
        raise PngFontUnavailable()
    return fonts


def _coverage(name: str) -> set[int]:
    from reportlab.pdfbase import pdfmetrics

    face = getattr(pdfmetrics.getFont(name), "face", None)
    return set(getattr(face, "charToGlyph", None) or ())


def missing_glyphs(texts: list[tuple[str, str]]) -> list[str]:
    """(字体名, 文字) → 该字体画不了的字（空白不算）。"""
    covered: dict[str, set[int]] = {}
    missing: list[str] = []
    for name, text in texts:
        if name not in covered:
            covered[name] = _coverage(name)
        missing += [ch for ch in str(text) if not ch.isspace() and ord(ch) not in covered[name]]
    return missing


# ───────────────────────────── 格子盘（十二宫 / 九宫） ─────────────────────────────


_BREAK_AFTER = ("\u3000、，；", " ")  # 先找全角分隔（星曜之间），没有再退到半角空格（「海 12°」别拆开）


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    """按字宽折行：优先断在全角空格 / 顿号逗号之后，其次半角空格（「土·奎」「海 12°」这类不拆开），都没有再逐字断；英文数字串不从中间断。"""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    lines: list[str] = []
    for raw in str(text).split("\n"):
        current = ""
        for ch in raw:
            if current and stringWidth(current + ch, font, size) > width:
                cut = next((found for found in (max((i + 1 for i, c in enumerate(current) if c in marks), default=0)
                                                for marks in _BREAK_AFTER) if found), 0)
                if not cut:
                    cut = len(current)
                    if ch.isascii() and ch.isalnum():  # 不在英文数字串中间断：退到串首
                        while cut > 0 and current[cut - 1].isascii() and current[cut - 1].isalnum():
                            cut -= 1
                        cut = cut or len(current)
                lines.append(current[:cut].rstrip(" \u3000"))
                current = current[cut:]
            current += ch
        lines.append(current)
    return [line for line in lines if line.strip()]


def _cell_rows(cell: dict[str, Any], kind: str, liureng: bool, width: float, font: str, bold: str) -> list[tuple[str, str, float, str, str]]:
    """一格要画的行：(文字, 字体, 字号, 颜色, 对齐)。字段与 PDF / DOCX 的格子同一套（title / label / lines）。"""
    rows: list[tuple[str, str, float, str, str]] = []

    def add(text: Any, name: str, size: float, color: str, align: str = "start") -> None:
        for line in _wrap(str(text or ""), name, size, width):
            rows.append((line, name, size, color, align))

    lines = [str(line) for line in cell.get("lines") or [] if str(line).strip()]
    if kind == "grid12" and liureng:
        add(cell.get("title"), font, 9.0, _MUTED, "middle")
        add(cell.get("label"), bold, 15.0, _INK, "middle")
        for line in lines:
            add(line, font, 8.0, _MUTED, "middle")
        return rows
    if kind == "grid12":
        head = str(cell.get("title") or "")
        add(head, bold, 9.6, _TEAL)
        if cell.get("label"):
            add(cell["label"], font, 8.4, _MUTED)
        for index, line in enumerate(lines):
            last_two = index >= len(lines) - 2 and index > 0
            add(line, bold if index == 0 else font, 8.6, _INK if index == 0 or not last_two else _MUTED)
        return rows
    add(cell.get("title"), font, 9.0, _MUTED, "middle")  # 九宫：宫名 / 八神 / 九星天盘干 / 八门地盘干 / 标记
    for index, line in enumerate(lines):
        add(line, font if index == 0 else bold, 9.6, _INK, "middle")
    if cell.get("label"):
        add(cell["label"], font, 8.6, _AMBER, "middle")
    return rows


def _center_rows(center: dict[str, Any], width: float, font: str, bold: str) -> list[tuple[str, str, float, str, str]]:
    rows = [(line, bold, 12.0, _TEAL, "middle") for line in _wrap(str(center.get("title") or ""), bold, 12.0, width)]
    columns = center.get("columns") or []
    if columns:  # 六壬四课竖格（右起一课）：课名 / 天将 / 上神 / 下神，各占一行
        for r in range(4):
            cells = [str(col.get("title") or "") if r == 0 else str((col.get("lines") or ["", "", ""])[r - 1]) for col in columns]
            rows.append(("　".join(cells), bold if r == 2 else font, 9.0 if r else 8.2, _INK if r else _MUTED, "middle"))
    for line in center.get("lines") or []:
        rows += [(text, font, 9.0, _INK, "middle") for text in _wrap(str(line), font, 9.0, width)]
    return rows


def grid_drawing(spec: dict[str, Any], width: float, font: str, bold: str, colors: Any) -> Any:
    """十二宫（4×4，中间 2×2 并作中宫）/ 九宫（3×3）格子图。格位按 figures.grid_position（地支 / 星座 / 卦），不自己排。"""
    from reportlab.graphics.shapes import Drawing, Rect, String

    kind = spec.get("kind")
    n = 4 if kind == "grid12" else 3
    pad, line_gap = 6.0, 2.4
    cell_w = width / n
    liureng = spec.get("cell_style") == "liureng"
    grid: dict[tuple[int, int], dict[str, Any]] = {}
    for cell in spec.get("cells") or []:
        position = figure_kit.grid_position(spec, cell)
        if position is not None:
            grid[position] = cell
    contents = {pos: _cell_rows(cell, kind, liureng, cell_w - 2 * pad, font, bold) for pos, cell in grid.items()}

    def height_of(rows: list[tuple[str, str, float, str, str]]) -> float:
        return sum(size + line_gap for _, _, size, _, _ in rows) + 2 * pad

    row_h = []
    for r in range(n):
        tallest = max([height_of(contents.get((r, c), [])) for c in range(n)
                       if not (n == 4 and 1 <= r <= 2 and 1 <= c <= 2)] or [0.0])
        row_h.append(max(tallest, 62.0 if n == 4 else 84.0))
    center = _center_rows(spec.get("center") or {}, cell_w * 2 - 2 * pad, font, bold) if n == 4 else []
    if n == 4:  # 中宫装不下就把中间两行撑高
        need = height_of(center) - (row_h[1] + row_h[2])
        if need > 0:
            row_h[1] += need / 2
            row_h[2] += need / 2
    inset = 1.5  # 外框线画在图内：贴边画会被位图边界裁掉半条
    total_h = sum(row_h) + 2 * inset
    drawing = Drawing(width + 2 * inset, total_h)
    tops = [inset + sum(row_h[:r]) for r in range(n)]

    def rect(x: float, top: float, w: float, h: float, fill: str, stroke: str, stroke_width: float) -> None:
        drawing.add(Rect(inset + x, total_h - top - h, w, h, fillColor=colors.HexColor(fill), strokeColor=colors.HexColor(stroke),
                         strokeWidth=stroke_width))

    def text_block(rows: list[tuple[str, str, float, str, str]], x: float, top: float, w: float, h: float, vcenter: bool) -> None:
        used = height_of(rows) - 2 * pad
        y = top + pad + (max(0.0, (h - 2 * pad - used) / 2) if vcenter else 0.0)
        for text, name, size, color, align in rows:
            y += size
            anchor_x = inset + (x + w / 2 if align == "middle" else x + pad)
            drawing.add(String(anchor_x, total_h - y, text, fontName=name, fontSize=size, fillColor=colors.HexColor(color),
                               textAnchor=align))
            y += line_gap

    cells = [(r, c) for r in range(n) for c in range(n) if not (n == 4 and 1 <= r <= 2 and 1 <= c <= 2)]
    # 着重格最后画：先画的着重框会被相邻格的灰框盖住一边
    cells.sort(key=lambda pos: bool((grid.get(pos) or {}).get("emphasis")))
    if n == 4:
        rect(cell_w, tops[1], cell_w * 2, row_h[1] + row_h[2], _CENTER_FILL, _GRID_RULE, 0.6)
        text_block(center, cell_w, tops[1], cell_w * 2, row_h[1] + row_h[2], vcenter=True)
    for r, c in cells:
        cell = grid.get((r, c))
        emphasis = bool(cell and cell.get("emphasis"))
        rect(c * cell_w, tops[r], cell_w, row_h[r], _EMPHASIS_FILL if emphasis else "#ffffff",
             _TEAL if emphasis else _GRID_RULE, 1.2 if emphasis else 0.6)
        if cell is not None:
            text_block(contents[(r, c)], c * cell_w, tops[r], cell_w, row_h[r], vcenter=liureng or kind == "grid9")
    return drawing


# ───────────────────────────── 成图 ─────────────────────────────


def _drawing_texts(drawing: Any) -> list[tuple[str, str]]:
    """全部文字（含 app 图里嵌套在组里的）；app 的符号字体自带字形，不进缺字检查。"""
    from reportlab.graphics.shapes import String

    from horosa_skill.reports.app_charts import glyph_font_files

    glyph_fonts = set(glyph_font_files())
    out: list[tuple[str, str]] = []

    def walk(node: Any) -> None:
        for shape in getattr(node, "contents", None) or []:
            if isinstance(shape, String):
                if shape.fontName not in glyph_fonts:
                    out.append((shape.fontName, shape.text))
            else:
                walk(shape)

    walk(drawing)
    return out


def _figure_drawing(spec: dict[str, Any], font: str, bold: str, colors: Any) -> Any:
    kind = spec.get("kind")
    if spec.get("app_svg"):
        drawing = figure_kit.figure_drawing(spec, 560.0 if kind == "grid12" else 440.0, font, bold, colors)
        if drawing is not None:
            return drawing
    if kind in {"grid12", "grid9"}:
        return grid_drawing(spec, 560.0 if kind == "grid12" else 480.0, font, bold, colors)
    width = {"hexagram": 420.0, "taiyi": 440.0, "dial90": 420.0}.get(str(kind), 440.0)
    return figure_kit.figure_drawing(spec, width, font, bold, colors)


def render_figure_pngs(figures: list[dict[str, Any]], *, script: str, t: Any = str) -> list[dict[str, Any]]:
    """每张盘图一份 PNG：[{"title", "width", "height", "png"}]。字体不可用 / 缺字 → PngFontUnavailable（什么都不返回）。

    先把所有图都画好、查完字，再交给调用方落盘：缺字时一个文件都不写。"""
    from reportlab.lib import colors

    fonts = _fonts(script)
    regular, bold = fonts["names"]
    prepared = []
    for spec in figures:
        drawing = _figure_drawing(spec, regular, bold, colors)
        if drawing is None:  # 只有 app 画得出的盘（kind="app"）这次没转成：不出这张
            continue
        title = str(spec.get("title") or "")
        notes = [str(note) for note in figure_kit.figure_notes(spec, t) if note]
        prepared.append((spec, drawing, title, notes))
    missing = missing_glyphs([pair for _, drawing, title, notes in prepared
                              for pair in [*_drawing_texts(drawing), (bold, title), *((regular, note) for note in notes)]])
    if missing:
        raise PngFontUnavailable(missing)

    out: list[dict[str, Any]] = []
    for spec, drawing, title, notes in prepared:
        # 先按图本身定倍率，再按成图（加图名、图例）的实际尺寸收一次：成图长边不超过 PNG_LONG_EDGE_MAX，不事后重采样（重采样会糊字、也更大）。
        scale = min(3.0, PNG_LONG_EDGE_MAX / max(drawing.width, drawing.height))
        for _ in range(3):
            canvas = _compose(drawing, title, notes, fonts, regular, bold, scale)
            if max(canvas.size) <= PNG_LONG_EDGE_MAX:
                break
            scale *= PNG_LONG_EDGE_MAX / max(canvas.size) * 0.995
        buffer = io.BytesIO()
        # 物理尺寸：图按 pt 画、每 pt 放大 scale 个像素，所以分辨率是 72 × scale dpi。不写（评审 R-17）时排版软件按 72 dpi 读，
        # 一张 1568 px 的盘图被当成 55 cm 宽插进文档。
        dpi = round(72 * scale)
        canvas.save(buffer, format="PNG", optimize=True, dpi=(dpi, dpi))
        out.append({"title": title, "kind": spec.get("kind"), "width": canvas.width, "height": canvas.height,
                    "dpi": dpi, "png": buffer.getvalue()})
    return out


def _compose(drawing: Any, title: str, notes: list[str], fonts: dict[str, Any], regular: str, bold: str, scale: float) -> Any:
    """图名在上、盘图居中、图例说明在下的一张白底图。"""
    from PIL import Image, ImageDraw, ImageFont

    from horosa_skill.reports.app_charts import glyph_font_files

    body = figure_kit.drawing_to_png(drawing, {**fonts["files"], **glyph_font_files()}, scale=scale)
    if body is None:  # Pillow / reportlab 缺件：与缺字体同样处理（不出半张图）
        raise PngFontUnavailable()
    figure = Image.open(io.BytesIO(body)).convert("RGB")
    margin = round(18 * scale)
    title_font = ImageFont.truetype(fonts["files"][bold][0], round(13 * scale), index=fonts["files"][bold][1])
    note_size = 8.6 * scale
    note_font = ImageFont.truetype(fonts["files"][regular][0], round(note_size), index=fonts["files"][regular][1])
    width = figure.width + 2 * margin
    note_lines = [line for note in notes for line in _wrap_pixels(note, note_font, width - 2 * margin)]
    title_h = round(13 * scale * 1.6)
    note_h = math.ceil(len(note_lines) * note_size * 1.5)
    height = margin + title_h + figure.height + (round(6 * scale) + note_h if note_lines else 0) + margin
    canvas = Image.new("RGB", (width, height), "white")
    pen = ImageDraw.Draw(canvas)
    pen.text((width / 2, margin), title, font=title_font, fill=_INK, anchor="mt")
    canvas.paste(figure, (margin, margin + title_h))
    y = margin + title_h + figure.height + round(6 * scale)
    for line in note_lines:
        pen.text((margin, y), line, font=note_font, fill=_MUTED, anchor="lt")
        y += note_size * 1.5
    return canvas


def _wrap_pixels(text: str, font: Any, width: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        if current and font.getlength(current + ch) > width:
            lines.append(current)
            current = ""
        current += ch
    if current.strip():
        lines.append(current)
    return lines
