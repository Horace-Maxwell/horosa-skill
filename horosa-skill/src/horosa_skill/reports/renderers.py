from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from horosa_skill.errors import bilingual
from horosa_skill.textscript import SIMPLIFIED, TRADITIONAL_HK


HUMAN_RENDER_HIDDEN_SECTION_IDS = {
    "report_metadata",
    "report_quality",
    "delivery_checklist",
    "coverage_contract",
    "section_coverage_matrix",
    "targeted_analysis_contract",
    "question_analysis",
    "input_overview",
    "technique_summary",
    "ai_interpretation",
    "recommendations_limitations",
    "xingque_export_text",
    "provenance",
}


def _labeler(script: str) -> Any:
    """渲染器自己写死的标签（目录 / 完整盘面 / 页脚…）按输出文字转一次。

    只用于字面量：文档里的文字调用方已转好，对繁体再转一次不幂等（萬里 → 萬裡、征戰 → 徵戰），绝不能整段再过一遍。
    """
    if script == SIMPLIFIED:
        return str
    from horosa_skill.textscript import convert

    return lambda text: convert(text, script)


def render_report(
    document: dict[str, Any], *, output_path: Path, format_name: str, script: str = SIMPLIFIED
) -> dict[str, Any]:
    """`script` 决定 DOCX/PDF 选哪套字形的字体（繁体用 TC/HK 字体）与渲染器自带标签的写法。

    咨询 / 排盘报告的文字由调用方先转好；**技法依据报告传简体原文**——它的人读版与 markdown 由模板现生成，模板里的标签
    也要转，所以在这里生成之后整体转一次（先转再生成会让模板标签漏转，生成后再转已转的部分又不幂等）。
    """
    normalized = format_name.lower()
    if normalized not in {"json", "docx", "pdf", "markdown"}:
        raise ValueError("format must be one of: json, docx, pdf, markdown")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Render to a temp sibling first, then atomically os.replace() into place. A mid-render failure
    # (python-docx / reportlab raising, disk error) thus can never leave a truncated/corrupt artifact
    # at output_path — the destination is only touched once a complete file exists.
    fd, tmp_name = tempfile.mkstemp(dir=str(output_path.parent), prefix=f".{output_path.name}.", suffix=".tmp")
    os.close(fd)
    tmp_path = Path(tmp_name)
    technique_report = _is_technique_report(document)
    if technique_report:
        from horosa_skill.textscript.localize import localize_document

        if normalized in {"docx", "pdf"}:
            document = _technique_report_human_document(document)
        if normalized != "markdown":
            document = localize_document(document, script)
    try:
        if normalized == "json":
            tmp_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        elif normalized == "markdown":
            # markdown 只服务**技法依据报告**（确定性元数据）。咨询报告不走这条：它的正文样式规矩
            # 由 DOCX/PDF 渲染器承载，且 references/reports.md 明令正文不带机器元数据。
            from horosa_skill.reports.technique_card import render_technique_report_markdown

            tmp_path.write_text(_labeler(script)(render_technique_report_markdown(document)), encoding="utf-8")
        elif normalized == "docx":
            _render_docx(document, tmp_path, script)
        else:  # pdf
            _render_pdf(document, tmp_path, script)
        payload = tmp_path.read_bytes()
        os.replace(str(tmp_path), str(output_path))
    except BaseException as exc:
        tmp_path.unlink(missing_ok=True)  # cleanup on ANY exit, cancellation included
        # Only an ordinary render failure degrades to TXT. Ctrl-C, SystemExit and an MCP cancel (BaseException) must
        # propagate — before v0.41.1 they came back as a "successful" degraded report.
        if normalized in {"docx", "pdf"} and isinstance(exc, Exception):
            # 渲染失败降级：自动改存 TXT（纯文本全文），绝不静默丢内容——结果里如实标注降级。
            degraded = _render_txt_degraded(document, output_path)
            if degraded is not None:
                degraded["degraded_from"] = normalized
                degraded["degrade_reason"] = f"{type(exc).__name__}: {exc}"
                return degraded
        raise
    return {
        "path": str(output_path),
        "format": normalized,
        "file_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _is_technique_report(document: dict[str, Any]) -> bool:
    from horosa_skill.reports.technique_card import TECHNIQUE_REPORT_SCHEMA

    return document.get("schema") == TECHNIQUE_REPORT_SCHEMA


def _technique_report_human_document(report: dict[str, Any]) -> dict[str, Any]:
    """技法依据报告 → DOCX/PDF 人读文档。

    技法依据报告没有 ai_report，渲染器只画 ai_report 块与 human_visible 段，直接渲染会只剩封面和目录。
    这里取 markdown 版（同一份确定性元数据），按 `## ` 拆成人读段；管道表照常成真表格，行内 `**` / 反引号去掉。
    """
    from horosa_skill.reports.technique_card import render_technique_report_markdown

    sections: list[dict[str, Any]] = []
    title, body = "概览", []

    def flush() -> None:
        if any(line.strip() for line in body):
            sections.append({
                "id": f"technique_report_{len(sections) + 1}",
                "title": title,
                "body": "\n".join(body).strip(),
                "human_visible": True,
            })

    for line in render_technique_report_markdown(report).splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            flush()
            title, body = line[3:].strip(), []
            continue
        body.append(line.replace("**", "").replace("`", ""))
    flush()
    return {
        "title": report.get("title"),
        "cover_label": "技法依据报告",
        "cover_meta": "算源 · 口径 · 导出契约 · 一致性检查",
        "intro_heading": "报告说明",
        "user_question": "本报告只列确定性的技法依据（算源、口径、导出契约与一致性检查），不含任何解读。",
        "sections": sections,
    }


def _render_txt_degraded(document: dict[str, Any], intended_path: Path) -> dict[str, Any] | None:
    # DOCX/PDF 渲染异常时的兜底：把报告全文（plain_text 或 JSON）写成 UTF-8 TXT 落在同名 .txt。
    try:
        txt_path = intended_path.with_suffix(".txt")
        text = document.get("plain_text")
        if not isinstance(text, str) or not text.strip():
            text = json.dumps(document, ensure_ascii=False, indent=2)
        txt_path.write_text(text, encoding="utf-8")
        payload = txt_path.read_bytes()
        return {
            "path": str(txt_path),
            "format": "txt",
            "file_size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    except OSError:
        return None


_MD_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")


def _split_markdown_blocks(text: str) -> list[tuple[str, Any]]:
    """把正文拆成 ('text', str) 与 ('table', {'header': [...], 'rows': [[...]]}) 块序列。

    识别标准 Markdown 管道表：表头行 `| a | b |` + 分隔行 `|---|---|` + 数据行。
    非表格内容原样归入 text 块（含空行分段语义交由调用方 _paragraphs 处理）。
    """
    lines = (text or "").splitlines()
    blocks: list[tuple[str, Any]] = []
    buffer: list[str] = []

    def flush_text() -> None:
        if buffer:
            blocks.append(("text", "\n".join(buffer)))
            buffer.clear()

    def parse_row(line: str) -> list[str]:
        row = line.strip()
        if row.startswith("|"):
            row = row[1:]
        if row.endswith("|"):
            row = row[:-1]
        return [cell.strip() for cell in row.split("|")]

    i = 0
    while i < len(lines):
        line = lines[i]
        is_pipe_row = "|" in line and line.strip().startswith("|")
        if is_pipe_row and i + 1 < len(lines) and _MD_TABLE_SEP_RE.match(lines[i + 1] or ""):
            header = parse_row(line)
            rows: list[list[str]] = []
            j = i + 2
            while j < len(lines) and "|" in lines[j] and lines[j].strip().startswith("|"):
                cells = parse_row(lines[j])
                # 列数对齐表头（缺补空、多截断），保证表格矩形。
                if len(cells) < len(header):
                    cells = cells + [""] * (len(header) - len(cells))
                rows.append(cells[: len(header)])
                j += 1
            flush_text()
            blocks.append(("table", {"header": header, "rows": rows}))
            i = j
            continue
        buffer.append(line)
        i += 1
    flush_text()
    return blocks


def _render_docx(document: dict[str, Any], output_path: Path, script: str = SIMPLIFIED) -> None:
    from docx import Document
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    t = _labeler(script)
    doc = Document()
    font_name = _docx_font_name(script)
    for section in doc.sections:
        section.top_margin = Inches(0.65)
        section.bottom_margin = Inches(0.62)
        section.left_margin = Inches(0.72)
        section.right_margin = Inches(0.72)
    _docx_apply_base_styles(doc, font_name, qn, Pt, RGBColor)
    docx_content_width = Inches(6.25)

    def set_cell_shading(cell: Any, fill: str) -> None:
        tc_pr = cell._tc.get_or_add_tcPr()
        shading = OxmlElement("w:shd")
        shading.set(qn("w:fill"), fill)
        tc_pr.append(shading)

    def set_cell_border(cell: Any, color: str = "D8DED9", size: str = "8") -> None:
        tc_pr = cell._tc.get_or_add_tcPr()
        borders = tc_pr.first_child_found_in("w:tcBorders")
        if borders is None:
            borders = OxmlElement("w:tcBorders")
            tc_pr.append(borders)
        for edge in ["top", "left", "bottom", "right"]:
            tag = f"w:{edge}"
            element = borders.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                borders.append(element)
            element.set(qn("w:val"), "single")
            element.set(qn("w:sz"), size)
            element.set(qn("w:color"), color)

    def set_table_full_width(table: Any) -> None:
        tbl_pr = table._tbl.tblPr
        tbl_w = tbl_pr.find(qn("w:tblW"))
        if tbl_w is None:
            tbl_w = OxmlElement("w:tblW")
            tbl_pr.append(tbl_w)
        tbl_w.set(qn("w:type"), "pct")
        tbl_w.set(qn("w:w"), "5000")
        layout = tbl_pr.find(qn("w:tblLayout"))
        if layout is None:
            layout = OxmlElement("w:tblLayout")
            tbl_pr.append(layout)
        layout.set(qn("w:type"), "fixed")

    def set_left_border(cell: Any, color: str = "0F766E", size: str = "28") -> None:
        tc_pr = cell._tc.get_or_add_tcPr()
        borders = tc_pr.first_child_found_in("w:tcBorders")
        if borders is None:
            borders = OxmlElement("w:tcBorders")
            tc_pr.append(borders)
        left = borders.find(qn("w:left"))
        if left is None:
            left = OxmlElement("w:left")
            borders.append(left)
        left.set(qn("w:val"), "single")
        left.set(qn("w:sz"), size)
        left.set(qn("w:color"), color)

    def style_run(run: Any, *, size: int | float | None = None, bold: bool = False, color: str | None = None) -> None:
        run.font.name = font_name
        run._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)
        run.bold = bold
        if size is not None:
            run.font.size = Pt(size)
        if color:
            run.font.color.rgb = RGBColor.from_string(color)

    def add_data_table(header: list[str], rows: list[list[str]]) -> None:
        # Markdown 管道表 → Word 真表格：表头底纹加粗 + 跨页重复（w:tblHeader）+ 全宽 + 细边框。
        cols = max(1, len(header))
        table = doc.add_table(rows=1, cols=cols)
        table.autofit = False
        set_table_full_width(table)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        widths = [Inches(w) for w in _column_widths(header, rows, 6.25, 0.5 if cols <= 8 else 6.25 / cols)]
        for column, width in zip(table.columns, widths):
            column.width = width
        header_row = table.rows[0]
        # 跨页重复表头
        tr_pr = header_row._tr.get_or_add_trPr()
        tbl_header = OxmlElement("w:tblHeader")
        tbl_header.set(qn("w:val"), "true")
        tr_pr.append(tbl_header)
        for idx, cell in enumerate(header_row.cells):
            cell.width = widths[idx]
            set_cell_shading(cell, "EEF6F2")
            set_cell_border(cell)
            p = cell.paragraphs[0]
            run = p.add_run(header[idx] if idx < len(header) else "")
            style_run(run, size=9.6, bold=True, color="0F766E")
        for data_row in rows:
            row = table.add_row()
            for idx, cell in enumerate(row.cells):
                cell.width = widths[idx]
                set_cell_border(cell)
                add_inline_runs(cell.paragraphs[0], data_row[idx] if idx < len(data_row) else "", size=9.6)
        doc.add_paragraph()

    def add_inline_runs(paragraph: Any, text: str, *, size: float = 10.2, color: str = "14211F", bold_label: bool = False) -> None:
        # **粗体** 成粗体 run，`代码` 去反引号；「键：值」行键加粗（与 PDF 同一口径）。
        labelled = _LABEL_LINE_RE.match(text) if bold_label else None
        if labelled:
            style_run(paragraph.add_run(labelled.group(1) + labelled.group(2)), size=size, bold=True, color=color)
            text = labelled.group(3)
        for index, piece in enumerate(_MD_BOLD_RE.split(text)):
            if piece:
                style_run(paragraph.add_run(_MD_CODE_RE.sub(r"\1", piece)), size=size, bold=index % 2 == 1, color=color)

    def add_text(text: str, *, style: str = "Normal") -> None:
        # 正文按块渲染：Markdown 管道表成真表格；其余逐行认标题 / 列表 / 引用 / 键值行。
        for kind, payload in _split_markdown_blocks(text):
            if kind == "table":
                add_data_table(payload["header"], payload["rows"])
                continue
            for line_kind, marker, body in _md_lines(payload):
                if line_kind in {"blank", "rule"}:
                    continue
                if line_kind == "heading":
                    p = doc.add_paragraph()
                    p.paragraph_format.space_before = Pt(6)
                    style_run(p.add_run(body.replace("**", "")), size=11, bold=True, color="0F766E")
                elif line_kind in {"bullet", "ordered"}:
                    p = doc.add_paragraph(style="List Bullet" if line_kind == "bullet" else "List Number")
                    add_inline_runs(p, body)
                elif line_kind == "quote":
                    p = doc.add_paragraph(style=style)
                    p.paragraph_format.left_indent = Inches(0.25)
                    add_inline_runs(p, body, size=9.8, color="66706D")
                else:
                    p = doc.add_paragraph(style=style)
                    add_inline_runs(p, body, bold_label=True)

    def set_outline_level(paragraph: Any, level: int) -> None:
        # 给段落挂大纲级别（0=一级）：Word 导航窗格/自动目录识别 outlineLvl，无需换 Heading 视觉样式。
        p_pr = paragraph._p.get_or_add_pPr()
        outline = OxmlElement("w:outlineLvl")
        outline.set(qn("w:val"), str(level))
        p_pr.append(outline)

    def add_heading_block(text: str, *, level: int = 1) -> None:
        table = doc.add_table(rows=1, cols=1)
        table.autofit = False
        set_table_full_width(table)
        table.columns[0].width = docx_content_width
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        cell.width = docx_content_width
        set_cell_shading(cell, "EEF6F2")
        set_cell_border(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(3)
        set_outline_level(p, 0 if level == 1 else 1)
        run = p.add_run(text)
        style_run(run, size=16 if level == 1 else 12.5, bold=True, color="14211F" if level == 1 else "0F766E")
        doc.add_paragraph()

    def add_card(title_text: str, body_text: str, *, accent: str = "0F766E") -> None:
        table = doc.add_table(rows=1, cols=1)
        table.autofit = False
        set_table_full_width(table)
        table.columns[0].width = docx_content_width
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        cell.width = docx_content_width
        set_cell_shading(cell, "FFFFFF")
        set_cell_border(cell, color="DFE7E1")
        set_left_border(cell, color=accent, size="28")
        p = cell.paragraphs[0]
        title_run = p.add_run(title_text)
        style_run(title_run, size=12.5, bold=True, color=accent)
        for kind, payload in _split_markdown_blocks(body_text):
            if kind == "table":
                # 卡片内表格：渲染在卡片下方为独立真表格（表格嵌单元格在窄卡内可读性差）。
                pass_through_tables.append(payload)
                continue
            for paragraph in _paragraphs(payload):
                p = cell.add_paragraph()
                run = p.add_run(paragraph)
                style_run(run, size=10.2, color="14211F")
        doc.add_paragraph()
        while pass_through_tables:
            payload = pass_through_tables.pop(0)
            add_data_table(payload["header"], payload["rows"])

    pass_through_tables: list[dict[str, Any]] = []

    ai_report = document.get("ai_report") if isinstance(document.get("ai_report"), dict) else {}
    display_question = str(document.get("intro_text") or "") or _display_question(document, ai_report, t)
    human_executive_summary = _human_ai_value(ai_report, "executive_summary")
    human_consultation_basis = _human_ai_value(ai_report, "consultation_basis")
    human_reading_steps = _human_ai_list(ai_report, "reading_steps")
    human_analysis_sections = _human_ai_list(ai_report, "analysis_sections")
    human_recommendations = _human_ai_list(ai_report, "recommendations")
    human_limitations = _human_ai_list(ai_report, "limitations")
    cover = doc.add_table(rows=3, cols=1)
    cover.autofit = False
    set_table_full_width(cover)
    cover.columns[0].width = docx_content_width
    cover.alignment = WD_TABLE_ALIGNMENT.CENTER
    for row in cover.rows:
        cell = row.cells[0]
        cell.width = docx_content_width
        set_cell_shading(cell, "11231F")
        set_cell_border(cell, color="24443E", size="10")
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    p = cover.cell(0, 0).paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(str(document.get("cover_label") or t("专业咨询报告")))
    style_run(run, size=9.5, color="DBE8E3")
    p = cover.cell(1, 0).paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(str(document.get("title") or t("结构化咨询报告")))
    style_run(run, size=27, bold=True, color="FFFFFF")
    p = cover.cell(2, 0).paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta = str(document.get("cover_meta") or t("结构化解读 · 行动建议 · 风险提示"))
    run = p.add_run(meta)
    style_run(run, size=9.5, color="DBE8E3")
    doc.add_paragraph()

    # 目录：TOC 域（取大纲级别 1-2），Word 打开时经 updateFields 自动生成、可点击跳转。
    toc_head = doc.add_paragraph()
    toc_run = toc_head.add_run(t("目录"))
    style_run(toc_run, size=13, bold=True, color="0F766E")
    toc_paragraph = doc.add_paragraph()
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), 'TOC \\o "1-2" \\h \\z \\u')
    placeholder = OxmlElement("w:r")
    placeholder_text = OxmlElement("w:t")
    placeholder_text.text = t("（打开文档后目录将自动更新）")
    placeholder.append(placeholder_text)
    fld.append(placeholder)
    toc_paragraph._p.append(fld)
    settings_element = doc.settings.element
    update_fields = settings_element.find(qn("w:updateFields"))
    if update_fields is None:
        update_fields = OxmlElement("w:updateFields")
        settings_element.append(update_fields)
    update_fields.set(qn("w:val"), "true")
    doc.add_paragraph()

    add_heading_block(str(document.get("intro_heading") or t("解读目标")))
    add_text(display_question)
    human_sections = [s for s in _human_sections(document) if isinstance(s, dict)]
    for section in human_sections:
        if section.get("group") == "basis":
            add_heading_block(str(section.get("title") or t("基本信息")))
            add_text(str(section.get("body") or ""))
    show_ai = document.get("show_ai", True) is not False

    if show_ai and human_consultation_basis:
        add_card(t("起盘依据"), str(human_consultation_basis or ""), accent="0F766E")
    if show_ai and human_reading_steps:
        add_card(t("解盘步骤"), _steps_text(human_reading_steps), accent="2563EB")
    if show_ai and (ai_report.get("analysis_focus") or ai_report.get("direct_answer")):
        add_card(
            t("核心结论"),
            str(ai_report.get("direct_answer") or ai_report.get("analysis_focus") or ""),
        )
    if show_ai and human_executive_summary:
        add_heading_block(t("总览摘要"))
        add_text(str(human_executive_summary or ""))
    if show_ai and ai_report.get("answer_text") and str(ai_report.get("answer_text")) != str(human_executive_summary or ""):
        add_heading_block(t("完整解盘正文"))
        add_text(str(ai_report.get("answer_text") or ""))
    if show_ai and human_analysis_sections:
        add_heading_block(t("正文解读"))
        for section in human_analysis_sections:
            if isinstance(section, dict):
                add_heading_block(str(section.get("title") or t("分析")), level=2)
                add_text(str(section.get("body") or section.get("content") or ""))
            else:
                add_text(str(section))
    if show_ai and human_recommendations:
        add_card(t("建议"), "\n".join(f"- {item}" for item in human_recommendations), accent="B7791F")
    if show_ai and human_limitations:
        add_heading_block(t("限制与注意事项"))
        add_text("\n".join(f"- {item}" for item in human_limitations))

    parts = {"chart": t("完整盘面"), "appendix": t("附录")}
    current_group: str | None = None
    for section in human_sections:
        group = section.get("group")
        if group == "basis":
            continue
        if group in parts and group != current_group:
            doc.add_page_break()
            add_heading_block(parts[group])
        current_group = group
        add_heading_block(str(section.get("title") or t("章节")), level=2 if group in parts else 1)
        add_text(str(section.get("body") or ""))

    # 文档元数据：文件属性可检索/归档（标题/作者/主题/关键词/创建时间）。
    # OOXML core property 单项硬限 255 字符；search_index 里可能混入整段长文本，先滤短词再截断。
    source_meta = document.get("source") if isinstance(document.get("source"), dict) else {}
    props = doc.core_properties
    props.title = _core_prop_text(document.get("title") or t("结构化咨询报告"))
    props.author = "Horosa Skill"
    props.subject = _core_prop_text(source_meta.get("technique_label") or source_meta.get("tool_name") or "")
    keywords = document.get("search_index") if isinstance(document.get("search_index"), dict) else {}
    keyword_list = keywords.get("keywords") if isinstance(keywords.get("keywords"), list) else []
    short_keywords = [str(k).strip() for k in keyword_list if str(k).strip() and len(str(k).strip()) <= 24]
    props.keywords = _core_prop_text(", ".join(short_keywords[:12]))
    props.comments = "Generated by Horosa Skill report renderer"

    # 页脚：报告标题 + 「第 X 页 / 共 Y 页」域（与 PDF 页脚对齐）。
    footer = doc.sections[0].footer
    footer_p = footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = footer_p.add_run(f"{props.title}　·　{t('第')} ")  # 标题已转过，不能再转（不幂等）
    style_run(title_run, size=8, color="66706D")
    for instr in ("PAGE", "NUMPAGES"):
        fld_page = OxmlElement("w:fldSimple")
        fld_page.set(qn("w:instr"), instr)
        run_el = OxmlElement("w:r")
        text_el = OxmlElement("w:t")
        text_el.text = "1"
        run_el.append(text_el)
        fld_page.append(run_el)
        footer_p._p.append(fld_page)
        if instr == "PAGE":
            mid_run = footer_p.add_run(t(" 页 / 共 "))
            style_run(mid_run, size=8, color="66706D")
    tail_run = footer_p.add_run(t(" 页"))
    style_run(tail_run, size=8, color="66706D")

    doc.save(str(output_path))


_MD_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
_MD_BULLET_RE = re.compile(r"^\s*[-*•·]\s+(.*)$")
_MD_ORDERED_RE = re.compile(r"^\s*(\d{1,3})[.)、]\s+(.*)$")
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MD_CODE_RE = re.compile(r"`([^`]+)`")
_LABEL_LINE_RE = re.compile(r"^([^：:|*`\[\]]{1,14})([：:])(.+)$")


def _md_inline(text: str) -> str:
    """一行 Markdown → reportlab 段落标记：先转义，再还原 **粗体** 与 `代码`（引擎正文里常见的两种）。"""
    escaped = _esc(text)
    escaped = _MD_BOLD_RE.sub(r"<b>\1</b>", escaped)
    return _MD_CODE_RE.sub(r'<font color="#0f766e">\1</font>', escaped)


def _md_lines(text: str) -> list[tuple[str, str, str]]:
    """正文逐行分类：(kind, marker, text)，kind ∈ heading / bullet / ordered / quote / rule / blank / text。"""
    out: list[tuple[str, str, str]] = []
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            out.append(("blank", "", ""))
        elif stripped in {"---", "***", "___", "==", "==="}:
            out.append(("rule", "", ""))
        elif (m := _MD_HEADING_RE.match(stripped)):
            out.append(("heading", m.group(1), m.group(2).strip()))
        elif stripped.startswith("[") and stripped.endswith("]") and len(stripped) <= 40:
            out.append(("heading", "###", stripped[1:-1]))
        elif (m := _MD_BULLET_RE.match(line)):
            out.append(("bullet", "•", m.group(1)))
        elif (m := _MD_ORDERED_RE.match(line)):
            out.append(("ordered", f"{m.group(1)}.", m.group(2)))
        elif stripped.startswith(">"):
            out.append(("quote", "", stripped.lstrip("> ").strip()))
        else:
            out.append(("text", "", stripped))
    return out


def _visual_width(text: str) -> int:
    return sum(2 if ord(ch) > 0x2E7F else 1 for ch in text)


def _column_widths(header: list[str], rows: list[list[str]], total: float, minimum: float) -> list[float]:
    """按每列内容的视觉宽度（CJK 记 2）分配列宽：短列不被拉宽、长列多拿空间，每列不低于 minimum。"""
    cols = max(1, len(header))
    weights = []
    for index in range(cols):
        cells = [header[index] if index < len(header) else ""] + [row[index] if index < len(row) else "" for row in rows]
        longest = max((_visual_width(str(cell)) for cell in cells), default=1)
        weights.append(min(max(longest, 4), 60))
    scale = total / sum(weights)
    widths = [max(w * scale, minimum) for w in weights]
    overflow = sum(widths) - total
    if overflow > 0:
        flexible = [i for i, w in enumerate(widths) if w > minimum]
        flex_total = sum(widths[i] - minimum for i in flexible) or 1
        for i in flexible:
            widths[i] -= overflow * (widths[i] - minimum) / flex_total
    return widths


def _render_pdf(document: dict[str, Any], output_path: Path, script: str = SIMPLIFIED) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import CondPageBreak, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.platypus.flowables import HRFlowable
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    font_name, bold_font_name = _register_pdf_fonts(pdfmetrics, UnicodeCIDFont, TTFont, script)
    t = _labeler(script)
    # 主字体缺字形的生僻字（Ext-B 起，如《灵棋经》里的 𡛸 𤣥 𥦗）交给补字字体画——不补就是方块。下面所有 Paragraph 都经它。
    patch_glyphs = _pdf_glyph_fallback(pdfmetrics, TTFont, font_name, bold_font_name, script)
    _Paragraph = Paragraph

    def Paragraph(text: str, *args: Any, **kwargs: Any) -> Any:  # noqa: N802 - 与 reportlab 同名，下文调用点不变
        return _Paragraph(patch_glyphs(text), *args, **kwargs)

    styles = getSampleStyleSheet()
    page_width, page_height = A4
    left_margin = right_margin = 22 * mm
    top_margin = bottom_margin = 18 * mm
    content_width = page_width - left_margin - right_margin
    ink = colors.HexColor("#14211f")
    muted = colors.HexColor("#66706d")
    green = colors.HexColor("#0f766e")
    amber = colors.HexColor("#b7791f")
    paper = colors.HexColor("#fbfaf5")
    pale = colors.HexColor("#eef6f2")
    line = colors.HexColor("#d8ded9")
    stripe = colors.HexColor("#f7faf8")

    base = ParagraphStyle(
        "HorosaBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9.6,
        leading=16,
        textColor=ink,
        spaceAfter=4,
    )
    cover_title = ParagraphStyle(
        "HorosaCoverTitle",
        parent=styles["Title"],
        fontName=bold_font_name,
        fontSize=27,
        leading=34,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    cover_meta = ParagraphStyle(
        "HorosaCoverMeta",
        parent=base,
        fontName=font_name,
        fontSize=10.5,
        leading=16,
        textColor=colors.HexColor("#dbe8e3"),
        alignment=TA_CENTER,
    )
    heading = ParagraphStyle(
        "HorosaHeading",
        parent=styles["Heading1"],
        fontName=bold_font_name,
        fontSize=15,
        leading=21,
        textColor=ink,
        spaceBefore=14,
        spaceAfter=8,
    )
    subheading = ParagraphStyle(
        "HorosaSubHeading",
        parent=styles["Heading2"],
        fontName=bold_font_name,
        fontSize=11.5,
        leading=17,
        textColor=green,
        spaceBefore=8,
        spaceAfter=5,
    )
    part_style = ParagraphStyle("HorosaPart", parent=heading, fontSize=19, leading=26, textColor=colors.white)
    inner_heading = ParagraphStyle("HorosaInnerHeading", parent=base, fontName=bold_font_name, fontSize=10.4,
                                   leading=16, textColor=green, spaceBefore=6, spaceAfter=2)
    bullet_style = ParagraphStyle("HorosaBullet", parent=base, leftIndent=14, bulletIndent=3, spaceAfter=2)
    quote_style = ParagraphStyle("HorosaQuote", parent=base, leftIndent=12, textColor=muted, fontSize=9.2)
    toc_styles = [
        ParagraphStyle("HorosaToc0", parent=base, fontName=bold_font_name, fontSize=10, leading=14, leftIndent=0,
                       spaceBefore=3, spaceAfter=0),
        ParagraphStyle("HorosaToc1", parent=base, fontSize=8.8, leading=11.5, leftIndent=14, textColor=muted,
                       spaceBefore=0, spaceAfter=0),
    ]
    toc_page_styles = [ParagraphStyle(f"{style.name}Page", parent=style, leftIndent=0, alignment=TA_RIGHT)
                       for style in toc_styles]

    def toc_table(entries: list[tuple[int, str, str]], pages: dict[str, int]) -> Any:
        # 自绘目录：第一遍页码还不知道就留空（行高不变，版面与第二遍一致），第二遍填上一遍记下的页码。
        rows = []
        for level, text, key in entries:
            depth = min(level, len(toc_styles) - 1)
            page = pages.get(key)
            rows.append([
                Paragraph(f'<a href="#{key}">{_esc(text)}</a>', toc_styles[depth]),
                Paragraph(str(page) if page else "", toc_page_styles[depth]),
            ])
        return Table(
            rows,
            colWidths=[content_width - 18 * mm, 18 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                *[("LINEBELOW", (0, r), (-1, r), 0.3, line) for r, (lv, _, _) in enumerate(entries) if lv == 0],
            ]),
        )

    def compose(pages: dict[str, int]) -> list[Any]:
        # 每遍排版都现组一份 story：flowable 被 wrap/split 过就不能再排（multiBuild 复用同一批对象会 LayoutError）。
        story: list[Any] = []
        entries: list[tuple[int, str, str]] = []
        toc_at: int | None = None

        def mark(flowable: Any, level: int, text: str) -> Any:
            # 目录 / 书签登记：afterFlowable 看见这个标记就记一条（标题块是 Table，不是 Paragraph）。
            # 键按出现顺序编号，各遍一致——上一遍记下的页码才能对回这一遍的同一个标题。
            key = f"h{len(entries)}"
            entries.append((level, text, key))
            flowable._horosa_toc = (level, text, key)
            return flowable

        def add_heading(text: str, style: ParagraphStyle = heading, *, level: int = 0) -> None:
            block = Table(
                [[Paragraph(_esc(text), style)]],
                colWidths=[content_width],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), pale),
                        ("BOX", (0, 0), (-1, -1), 0.55, line),
                        ("LEFTPADDING", (0, 0), (-1, -1), 9),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                ),
            )
            story.append(CondPageBreak(60 * mm if level == 0 else 40 * mm))  # 标题不落在页底孤零零一行
            story.append(Spacer(1, 8))
            story.append(mark(block, level, text))
            story.append(Spacer(1, 5))

        def add_part(text: str) -> None:
            story.append(PageBreak())
            block = Table(
                [[Paragraph(_esc(text), part_style)]],
                colWidths=[content_width],
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#11231f")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 14),
                    ("TOPPADDING", (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ]),
            )
            story.append(mark(block, 0, text))
            story.append(Spacer(1, 10))

        table_cell = ParagraphStyle("HorosaTableCell", parent=base, fontSize=8.6, leading=12, spaceAfter=0)
        table_head = ParagraphStyle("HorosaTableHead", parent=table_cell, fontName=bold_font_name, textColor=green)

        def add_data_table(header: list[str], rows: list[list[str]]) -> None:
            # Markdown 管道表 → PDF 真表格：按内容分配列宽、表头底纹 + repeatRows 跨页重复表头 + 隔行浅底。
            cols = max(1, len(header))
            data = [[Paragraph(_md_inline(h), table_head) for h in header]]
            for row in rows:
                data.append([Paragraph(_md_inline(row[idx] if idx < len(row) else ""), table_cell) for idx in range(cols)])
            table_style = [
                ("BACKGROUND", (0, 0), (-1, 0), pale),
                ("GRID", (0, 0), (-1, -1), 0.4, line),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
            table_style += [("BACKGROUND", (0, r), (-1, r), stripe) for r in range(2, len(data), 2)]
            story.append(
                Table(
                    data,
                    colWidths=_column_widths(header, rows, content_width, 12 * mm if cols <= 8 else content_width / cols),
                    repeatRows=1,
                    style=TableStyle(table_style),
                )
            )
            story.append(Spacer(1, 6))

        def add_text(text: str) -> None:
            for kind, marker, body in _md_lines(text):
                if kind == "blank":
                    story.append(Spacer(1, 3))
                elif kind == "rule":
                    story.append(HRFlowable(width="100%", thickness=0.5, color=line, spaceBefore=4, spaceAfter=4))
                elif kind == "heading":
                    story.append(Paragraph(_md_inline(body), inner_heading))
                elif kind in {"bullet", "ordered"}:
                    story.append(Paragraph(_md_inline(body), bullet_style, bulletText=marker))
                elif kind == "quote":
                    story.append(Paragraph(_md_inline(body), quote_style))
                elif (labelled := _LABEL_LINE_RE.match(body)) and "<" not in labelled.group(1):
                    # 「日期：…」「时间算法：…」这类键值行：键加粗，扫读快。
                    story.append(Paragraph(f"<b>{_esc(labelled.group(1))}</b>{_esc(labelled.group(2))}{_md_inline(labelled.group(3))}", base))
                else:
                    story.append(Paragraph(_md_inline(body), base))

        def add_body(text: str) -> None:
            for kind, payload in _split_markdown_blocks(text):
                if kind == "table":
                    add_data_table(payload["header"], payload["rows"])
                else:
                    add_text(payload)

        def add_note_card(title_text: str, body_text: str, *, accent: Any = green) -> None:
            rows = [
                [Paragraph(_esc(title_text), ParagraphStyle("CardTitle", parent=subheading, textColor=accent))],
                *[[Paragraph(_md_inline(paragraph), base)] for paragraph in _paragraphs(body_text)],
            ]
            story.append(
                Table(
                    rows,
                    colWidths=[content_width],
                    style=TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#dfe7e1")),
                            ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
                            ("LEFTPADDING", (0, 0), (-1, -1), 11),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                            ("TOPPADDING", (0, 0), (-1, -1), 7),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                        ]
                    ),
                )
            )
            story.append(Spacer(1, 9))

        ai_report = document.get("ai_report") if isinstance(document.get("ai_report"), dict) else {}
        show_ai = document.get("show_ai", True) is not False
        display_question = str(document.get("intro_text") or "") or _display_question(document, ai_report, t)
        human_executive_summary = _human_ai_value(ai_report, "executive_summary")
        human_consultation_basis = _human_ai_value(ai_report, "consultation_basis")
        human_reading_steps = _human_ai_list(ai_report, "reading_steps")
        human_analysis_sections = _human_ai_list(ai_report, "analysis_sections")
        human_recommendations = _human_ai_list(ai_report, "recommendations")
        human_limitations = _human_ai_list(ai_report, "limitations")
        metadata = [str(document.get("cover_meta") or t("结构化解读 · 行动建议 · 风险提示"))]
        cover = Table(
            [
                [Paragraph(_esc(str(document.get("cover_label") or t("专业咨询报告"))), cover_meta)],
                [Paragraph(_esc(str(document.get("title") or t("结构化咨询报告"))), cover_title)],
                [Paragraph(_esc(" / ".join(metadata)), cover_meta)],
            ],
            colWidths=[content_width],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#11231f")),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#24443e")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 20),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 20),
                    ("TOPPADDING", (0, 0), (0, 0), 20),
                    ("BOTTOMPADDING", (0, 0), (0, 0), 8),
                    ("TOPPADDING", (0, 1), (0, 1), 10),
                    ("BOTTOMPADDING", (0, 1), (0, 1), 12),
                    ("TOPPADDING", (0, 2), (0, 2), 8),
                    ("BOTTOMPADDING", (0, 2), (0, 2), 20),
                ]
            ),
        )
        story.append(cover)
        story.append(Spacer(1, 14))

        human_sections = [s for s in _human_sections(document) if isinstance(s, dict)]
        if len(human_sections) >= 4:
            story.append(Paragraph(_esc(t("目录")), subheading))
            toc_at = len(story)  # 目录表等全部标题登记完再插进来
            story.append(PageBreak())

        add_heading(str(document.get("intro_heading") or t("解读目标")))
        add_body(display_question)
        for section in human_sections:
            if section.get("group") == "basis":
                add_heading(str(section.get("title") or t("起盘信息")))
                add_body(str(section.get("body") or ""))
        if show_ai:
            if human_consultation_basis:
                add_note_card(t("起盘依据"), str(human_consultation_basis or ""), accent=green)
            if human_reading_steps:
                add_note_card(t("解盘步骤"), _steps_text(human_reading_steps), accent=colors.HexColor("#2563eb"))
            if ai_report.get("analysis_focus") or ai_report.get("direct_answer"):
                add_note_card(
                    t("核心结论"),
                    str(ai_report.get("direct_answer") or ai_report.get("analysis_focus") or ""),
                    accent=green,
                )
            if human_executive_summary:
                add_heading(t("总览摘要"))
                add_body(str(human_executive_summary or ""))
            if ai_report.get("answer_text") and str(ai_report.get("answer_text")) != str(human_executive_summary or ""):
                add_heading(t("完整解盘正文"))
                add_body(str(ai_report.get("answer_text") or ""))
            if human_analysis_sections:
                add_heading(t("正文解读"))
                for section in human_analysis_sections:
                    if isinstance(section, dict):
                        add_heading(str(section.get("title") or t("分析")), subheading, level=1)
                        add_body(str(section.get("body") or section.get("content") or ""))
                    else:
                        add_body(str(section))
            if human_recommendations:
                add_note_card(t("建议"), "\n".join(f"- {item}" for item in human_recommendations), accent=amber)
            if human_limitations:
                add_heading(t("限制与注意事项"))
                add_body("\n".join(f"- {item}" for item in human_limitations))

        parts = {"chart": t("完整盘面"), "appendix": t("附录")}
        current_group: str | None = None
        for section in human_sections:
            group = section.get("group")
            if group == "basis":
                continue
            if group in parts and group != current_group:
                add_part(parts[group])
            current_group = group
            add_heading(str(section.get("title") or t("章节")), level=1 if group in parts else 0)
            add_body(str(section.get("body") or ""))
        if toc_at is not None:
            story.insert(toc_at, toc_table(entries, pages))
        return story

    title_text =str(document.get("title") or t("咨询报告"))

    page_total = {"value": 0}

    def on_page(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFillColor(paper)
        canvas.rect(0, 0, page_width, page_height, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#e6eee9"))
        canvas.rect(0, page_height - 8, page_width, 8, fill=1, stroke=0)
        canvas.setFont(font_name, 7.5)
        canvas.setFillColor(muted)
        canvas.drawString(left_margin, 10 * mm, title_text)
        total = page_total["value"]
        canvas.drawRightString(page_width - right_margin, 10 * mm,
                               t(f"第 {doc.page} 页 / 共 {total} 页") if total else t(f"第 {doc.page} 页"))
        canvas.restoreState()

    class _Doc(SimpleDocTemplate):
        def afterFlowable(self, flowable: Any) -> None:  # reportlab 回调名
            entry = getattr(flowable, "_horosa_toc", None)
            if entry is None:
                return
            level, text, key = entry
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
            pages_seen[key] = self.page

    doc = _Doc(
        str(output_path),
        pagesize=A4,
        rightMargin=right_margin,
        leftMargin=left_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
        title=title_text,
        author="Horosa 星阙",
    )
    # 「共 M 页」与目录页码：先排一遍拿到总页数和各标题页码，再排一遍写进页脚 / 目录。
    # 不用「延迟出页」的 canvas：那会把每个书签都钉在第 1 页。
    pages: dict[str, int] = {}
    pages_seen: dict[str, int] = {}
    for _ in range(3):
        pages_seen.clear()
        doc.build(compose(pages), onFirstPage=on_page, onLaterPages=on_page)
        stable = pages_seen == pages and page_total["value"] == doc.page
        pages = dict(pages_seen)
        page_total["value"] = doc.page
        if stable:
            break


def _docx_font_name(script: str = SIMPLIFIED) -> str:
    if script != SIMPLIFIED:
        return _docx_traditional_font_name(script)
    # 中文字体候选（按平台常见优先级）：Win 微软雅黑 → Mac 苹方/宋体 → Arial Unicode → Noto CJK。
    # 返回的字体名同时用于 w:eastAsia，确保 CJK 字形真实存在，异机打开不豆腐。
    if Path("C:/Windows/Fonts/msyh.ttc").exists() or Path("C:/Windows/Fonts/msyh.ttf").exists():
        return "Microsoft YaHei"
    if Path("/System/Library/Fonts/PingFang.ttc").exists():
        return "PingFang SC"
    if Path("/System/Library/Fonts/Supplemental/Songti.ttc").exists():
        return "Songti SC"
    if Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf").exists():
        return "Arial Unicode MS"
    for noto in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"):
        if Path(noto).exists():
            return "Noto Sans CJK SC"
    return "Arial"


def _docx_traditional_font_name(script: str) -> str:
    # 繁体用繁体字形的字体（简体字体也能显示多数繁体字，但字形是大陆规范，台港读者一眼看出不对）。
    hk = script == TRADITIONAL_HK
    if Path("C:/Windows/Fonts/msjh.ttc").exists() or Path("C:/Windows/Fonts/msjh.ttf").exists():
        return "Microsoft JhengHei"
    if Path("/System/Library/Fonts/PingFang.ttc").exists():
        return "PingFang HK" if hk else "PingFang TC"
    if Path("/System/Library/Fonts/Supplemental/Songti.ttc").exists():
        return "Songti TC"
    if Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf").exists():
        return "Arial Unicode MS"
    for noto in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"):
        if Path(noto).exists():
            return "Noto Sans CJK HK" if hk else "Noto Sans CJK TC"
    return "Arial"


def _docx_apply_base_styles(doc: Any, font_name: str, qn: Any, Pt: Any, RGBColor: Any) -> None:
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = font_name
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)
    normal.font.size = Pt(10.2)
    normal.font.color.rgb = RGBColor.from_string("14211F")
    for style_name, size, color in [
        ("Title", 27, "14211F"),
        ("Heading 1", 16, "14211F"),
        ("Heading 2", 12.5, "0F766E"),
        ("List Bullet", 9.5, "66706D"),
    ]:
        try:
            style = styles[style_name]
        except KeyError:
            continue
        style.font.name = font_name
        style._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)


def _paragraphs(text: str) -> list[str]:
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [item.strip() for item in raw.split("\n") if item.strip()]
    return paragraphs or ["无"]


def _esc(value: str) -> str:
    return html.escape(str(value)).replace("\n", "<br/>")


# 补字字体：系统正文字体（微软雅黑 / 正黑 / 宋体）只收到 CJK 基本区 + 扩展 A，扩展 B 起的古籍字（《灵棋经》《天机》条文里实有 13 个）
# 画出来是方块。Windows 自带的 SimSun-ExtB / MingLiU-ExtB 正好收这些字（2026-10-23 本机实测：13 个里微软雅黑缺 12、SimSun-ExtB 缺 0）。
# 按文字族挑：繁体先用细明体 ExtB（台港字形）。没有任何候选的平台（macOS / Linux 默认装）行为不变。
_PDF_GLYPH_FALLBACK_CANDIDATES: dict[str, tuple[str, ...]] = {
    "sc": ("C:/Windows/Fonts/simsunb.ttf", "C:/Windows/Fonts/mingliub.ttc"),
    "tc": ("C:/Windows/Fonts/mingliub.ttc", "C:/Windows/Fonts/simsunb.ttf"),
}
_GLYPH_FALLBACK_FROM = 0x2E80  # CJK 部首起；ASCII 与标记（<b>、&amp;、href 键）永远不会被包


def _wrap_missing_glyphs(markup: str, primary: Any, fallback: Any, fallback_font: str) -> str:
    """把主字体画不了、补字字体画得了的字连成段，包进 `<font name=…>`；其余逐字节不变。primary / fallback 支持 `in`（码位集合）。"""
    out: list[str] = []
    run: list[str] = []
    for ch in markup:
        code = ord(ch)
        if code >= _GLYPH_FALLBACK_FROM and code not in primary and code in fallback:
            run.append(ch)
            continue
        if run:
            out.append(f'<font name="{fallback_font}">{"".join(run)}</font>')
            run = []
        out.append(ch)
    if run:
        out.append(f'<font name="{fallback_font}">{"".join(run)}</font>')
    return "".join(out)


def _pdf_glyph_fallback(pdfmetrics: Any, TTFont: Any, font_name: str, bold_font_name: str, script: str) -> Any:
    """返回给 Paragraph 标记补字的函数；主字体不是 TTF（reportlab 自带 CID 回退）或本机没有补字字体时返回原样函数。"""
    identity = lambda markup: markup  # noqa: E731
    try:
        primary = set(pdfmetrics.getFont(font_name).face.charToGlyph)
        bold = set(pdfmetrics.getFont(bold_font_name).face.charToGlyph) if bold_font_name != font_name else primary
    except Exception:  # noqa: BLE001 - CID 字体没有 face/charToGlyph：不补字（探针，原样即答案）
        return identity
    kind = "sc" if script == SIMPLIFIED else "tc"
    for index, path in enumerate(_PDF_GLYPH_FALLBACK_CANDIDATES[kind]):
        font = _load_ttf(TTFont, f"HorosaGlyph{kind.upper()}{index}", path, None)
        if font is None:
            continue
        pdfmetrics.registerFont(font)
        # `<b>` 里的补字段同样落在补字字体上（它没有粗体），否则 reportlab 找不到该族的粗体映射直接抛错。
        pdfmetrics.registerFontFamily(font.fontName, normal=font.fontName, bold=font.fontName,
                                      italic=font.fontName, boldItalic=font.fontName)
        covered = set(font.face.charToGlyph)
        drawable = primary & bold  # 常规体与粗体都有的字才不需要补
        return lambda markup: _wrap_missing_glyphs(markup, drawable, covered, font.fontName)
    return identity


# PDF 字体候选：(常规体路径, 常规体字面名, 粗体路径, 粗体字面名)。字面名 None = 取第 0 号子字体。
# 正文用常规体、标题与 **强调** 用粗体（此前一律取集合第 0 号 = Songti SC Black，整本 PDF 看起来全是粗体）。
# TTC 里的子字体顺序随系统版本会变，所以按字面名找，不写死序号。
_PDF_FONT_CANDIDATES: dict[str, list[tuple[str, tuple[str, ...] | None, str | None, tuple[str, ...] | None]]] = {
    "sc": [
        ("C:/Windows/Fonts/msyh.ttc", None, "C:/Windows/Fonts/msyhbd.ttc", None),
        ("C:/Windows/Fonts/msyh.ttf", None, "C:/Windows/Fonts/msyhbd.ttf", None),
        ("C:/Windows/Fonts/simhei.ttf", None, None, None),
        ("C:/Windows/Fonts/simsun.ttc", None, None, None),
        ("/System/Library/Fonts/Supplemental/Songti.ttc", ("STSongti-SC-Regular", "STSongti-SC-Light"),
         "/System/Library/Fonts/Supplemental/Songti.ttc", ("STSongti-SC-Bold", "STSongti-SC-Black")),
        ("/System/Library/Fonts/STHeiti Light.ttc", ("STHeitiSC-Light",),
         "/System/Library/Fonts/STHeiti Medium.ttc", ("STHeitiSC-Medium",)),
        ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", None, None, None),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", ("NotoSansCJKsc-Regular",),
         "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", ("NotoSansCJKsc-Bold",)),
        ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", ("NotoSansCJKsc-Regular",),
         "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", ("NotoSansCJKsc-Bold",)),
    ],
    "tc": [
        ("C:/Windows/Fonts/msjh.ttc", None, "C:/Windows/Fonts/msjhbd.ttc", None),
        ("C:/Windows/Fonts/msjh.ttf", None, "C:/Windows/Fonts/msjhbd.ttf", None),
        ("C:/Windows/Fonts/mingliu.ttc", None, None, None),
        ("/System/Library/Fonts/Supplemental/Songti.ttc", ("STSongti-TC-Regular", "STSongti-TC-Light"),
         "/System/Library/Fonts/Supplemental/Songti.ttc", ("STSongti-TC-Bold",)),
        ("/System/Library/Fonts/STHeiti Light.ttc", ("STHeitiTC-Light",),
         "/System/Library/Fonts/STHeiti Medium.ttc", ("STHeitiTC-Medium",)),
        ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", None, None, None),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", ("NotoSansCJKtc-Regular", "NotoSansCJKhk-Regular"),
         "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", ("NotoSansCJKtc-Bold", "NotoSansCJKhk-Bold")),
        ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", ("NotoSansCJKtc-Regular", "NotoSansCJKhk-Regular"),
         "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", ("NotoSansCJKtc-Bold", "NotoSansCJKhk-Bold")),
    ],
}


def _face_index(TTFont: Any, path: str, names: tuple[str, ...] | None) -> int | None:
    """TTC 里按字面名（按偏好顺序）找子字体序号；names 为 None 取 0；找不到返回 None。"""
    if names is None or not path.lower().endswith(".ttc"):
        return 0
    found: dict[str, int] = {}
    for index in range(32):
        try:
            face = TTFont(f"HorosaProbe{index}", path, subfontIndex=index).face
        except Exception:  # noqa: BLE001 - 越界或 reportlab 读不了这个子字体：探测到此为止（探针，None 即答案）
            break
        name = face.name.decode("utf-8", "replace") if isinstance(face.name, bytes) else str(face.name)
        found.setdefault(name, index)
    return next((found[n] for n in names if n in found), None)


def _load_ttf(TTFont: Any, font_name: str, path: str, names: tuple[str, ...] | None) -> Any | None:
    if not Path(path).exists():
        return None
    index = _face_index(TTFont, path, names)
    if index is None:
        return None
    try:
        return TTFont(font_name, path, subfontIndex=index) if path.lower().endswith(".ttc") else TTFont(font_name, path)
    except Exception:  # noqa: BLE001 - 这一款载不了就换下一款（探针，None 即答案）
        return None


def _register_pdf_fonts(pdfmetrics: Any, UnicodeCIDFont: Any, TTFont: Any, script: str = SIMPLIFIED) -> tuple[str, str]:
    """返回 (正文字体, 粗体字体) 并登记字体族（<b> 才能真的变粗）。繁体只选繁体字形字体（简体字体缺上千个繁体字）。"""
    kind = "sc" if script == SIMPLIFIED else "tc"
    for index, (regular_path, regular_names, bold_path, bold_names) in enumerate(_PDF_FONT_CANDIDATES[kind]):
        regular = _load_ttf(TTFont, f"Horosa{kind.upper()}{index}", regular_path, regular_names)
        if regular is None:
            continue
        pdfmetrics.registerFont(regular)
        bold_name = regular.fontName
        if bold_path:
            bold = _load_ttf(TTFont, f"Horosa{kind.upper()}{index}B", bold_path, bold_names)
            if bold is not None:
                pdfmetrics.registerFont(bold)
                bold_name = bold.fontName
        pdfmetrics.registerFontFamily(regular.fontName, normal=regular.fontName, bold=bold_name,
                                      italic=regular.fontName, boldItalic=bold_name)
        return regular.fontName, bold_name
    fallback = "STSong-Light" if kind == "sc" else "MSung-Light"  # reportlab 自带 CID 字体（Adobe-GB1 / Adobe-CNS1）
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(fallback))
        return fallback, fallback
    except Exception as exc:  # noqa: BLE001 - reportlab raises various errors for a missing CID resource
        # v0.41.1：此前静默退到 Helvetica——它画不了中文，结果是一份整页方块却标着 format: pdf 的「成功」报告。
        # 抛出去交给 render_report：降级成全文 TXT，并在 degrade_reason 里写清原因。
        raise RuntimeError(
            bilingual(
                f"PDF 注册不到任何能显示中文的字体（{fallback} 不可用）。",
                f"No CJK-capable font could be registered for the PDF ({fallback} unavailable).",
            )
        ) from exc


def _core_prop_text(value: Any, limit: int = 255) -> str:
    """OOXML core property 文本硬限 255 字符，超限写入会直接抛错，统一在此截断。"""
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _human_sections(document: dict[str, Any]) -> list[dict[str, Any]]:
    sections = document.get("sections") if isinstance(document.get("sections"), list) else []
    output: list[dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        if section.get("human_visible") is not True:
            continue
        if str(section.get("id") or "") in HUMAN_RENDER_HIDDEN_SECTION_IDS:
            continue
        output.append(section)
    return output


def _human_ai_value(ai_report: dict[str, Any], key: str) -> Any:
    human_key = f"human_{key}"
    if human_key in ai_report:
        return ai_report.get(human_key)
    return ai_report.get(key)


def _human_ai_list(ai_report: dict[str, Any], key: str) -> list[Any]:
    value = _human_ai_value(ai_report, key)
    return value if isinstance(value, list) else []


def _display_question(document: dict[str, Any], ai_report: dict[str, Any], t: Any = str) -> str:
    raw_question = str(document.get("user_question") or "").strip()
    if raw_question:
        return raw_question
    focus = str(ai_report.get("analysis_focus") or "").strip()
    return focus or t("整体综合解盘")


def _steps_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"{index}. {item}" for index, item in enumerate(value, start=1) if str(item).strip())
    return str(value or "")
