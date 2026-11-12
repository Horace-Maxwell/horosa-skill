from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from horosa_skill import fsretry
from horosa_skill.errors import bilingual
from horosa_skill.reports.layout import _human_sections, body_blocks
from horosa_skill.textscript import SIMPLIFIED, TRADITIONAL_HK


# 版面块的用途 → 各格式的画法（layout.py 只说用途）。
_DOCX_HEADING_LEVELS = {"summary": 1, "ai_topic": 2, "ai_section": 2, "figures": 2}
_DOCX_ACCENTS = {"green": "0F766E", "blue": "2563EB", "amber": "B7791F"}
_PDF_HEADING_LEVELS = {"summary": 0, "ai_topic": 0, "ai_section": 1, "figures": 1}


def _labeler(script: str) -> Any:
    """渲染器自己写死的标签（目录 / 完整盘面 / 页脚…）按输出文字转一次。

    只用于字面量：文档里的文字调用方已转好，对繁体再转一次不幂等（萬里 → 萬裡、征戰 → 徵戰），绝不能整段再过一遍。
    """
    if script == SIMPLIFIED:
        return str
    from horosa_skill.textscript import convert

    return lambda text: convert(text, script)


# 临时文件名不带目标文件名：`.{目标名}.xxxxxxxx.tmp` 比目标名长 14 字节，文件名上限（output_path.MAX_NAME_BYTES）就得替它留余量。
_TMP_PREFIX = ".horosa-report-"


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
    fd, tmp_name = tempfile.mkstemp(dir=str(output_path.parent), prefix=_TMP_PREFIX, suffix=".tmp")
    os.close(fd)
    tmp_path = Path(tmp_name)
    technique_report = _is_technique_report(document)
    if technique_report:
        from horosa_skill.textscript.localize import localize_document

        if normalized in {"docx", "pdf"}:
            document = _technique_report_human_document(document)
        if normalized != "markdown":
            document = localize_document(document, script)
    warnings: list[str] = []
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
            warnings = _render_pdf(document, tmp_path, script)
        payload = tmp_path.read_bytes()
        final_path = _place_rendered(tmp_path, output_path)
    except BaseException as exc:
        tmp_path.unlink(missing_ok=True)  # cleanup on ANY exit, cancellation included
        # Only an ordinary render failure degrades to TXT. Ctrl-C, SystemExit and an MCP cancel (BaseException) must
        # propagate — before v0.41.1 they came back as a "successful" degraded report.
        if normalized in {"docx", "pdf"} and isinstance(exc, Exception):
            # 渲染失败降级：自动改存 TXT（同一份人读内容的纯文本），绝不静默丢内容——结果里如实标注降级。
            degraded = _render_txt_degraded(document, output_path, script=script, format_name=normalized)
            if degraded is not None:
                degraded["degraded_from"] = normalized
                degraded["degrade_reason"] = (
                    f"{normalized.upper()} 排版时出错，改存为纯文本，内容与 {normalized.upper()} 版相同"
                    f"（技术原因：{type(exc).__name__}: {exc}）"
                )
                return degraded
        raise
    return {
        "path": str(final_path),
        "format": normalized,
        "file_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        **({"requested_output_path": str(output_path)} if final_path != output_path else {}),
        **({"warnings": warnings} if warnings else {}),
    }


def write_artifact(payload: bytes, *, output_path: Path, format_name: str) -> dict[str, Any]:
    """已经生成好的字节（PNG 盘图 / ICS 日历）落盘：同 render_report 的临时文件 + 原子替换（半截文件不会出现在目标路径）、
    目标被占用时另存旁边的空闲名字；返回同一形状的结果。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(output_path.parent), prefix=_TMP_PREFIX, suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        final_path = _place_rendered(tmp_path, output_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return {
        "path": str(final_path),
        "format": format_name,
        "file_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        **({"requested_output_path": str(output_path)} if final_path != output_path else {}),
    }


def _place_rendered(tmp_path: Path, output_path: Path) -> Path:
    """把渲染好的临时文件原子地放到位，返回最终路径。

    Windows 上目标开在 Acrobat / Word 里时 replace 拿不到（共享冲突，等也等不来）。整份报告已经渲染好，不能因为用户开着上一版就退化成
    TXT（v0.47.2-dev 之前正是如此）：存到旁边第一个空闲的 `名字 (1).pdf`，由调用方如实告知。其他错误照常抛。
    """
    try:
        fsretry.replace(tmp_path, output_path)
        return output_path
    except PermissionError as exc:
        if not fsretry.is_sharing_violation(exc):
            raise
    for index in range(1, 100):
        candidate = output_path.with_name(f"{output_path.stem} ({index}){output_path.suffix}")
        if not candidate.exists():
            fsretry.replace(tmp_path, candidate, budget_seconds=0.2)
            return candidate
    raise PermissionError(bilingual(
        f"目标文件正被占用，旁边也没有空闲的名字：{output_path}",
        f"output file is in use and no free name next to it: {output_path}",
    ))


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


def _render_txt_degraded(
    document: dict[str, Any], intended_path: Path, *, script: str = SIMPLIFIED, format_name: str = "pdf"
) -> dict[str, Any] | None:
    """DOCX/PDF 渲染异常时的兜底：同一份**人读**内容写成 UTF-8 纯文本（v0.50.0，评审 R-01）。

    此前写的是 document["plain_text"]——机器版全文：run / trace id、质量闸、交付清单、覆盖矩阵、机器回填的「建议」、
    产物绝对路径，读者拿到的是一份内部记录。现在按渲染器同一串块（layout.body_blocks）出文字：封面信息、所问、核心结论、
    盘面、AI 解读、附录，开头一句白话说明为什么是纯文本。落在同名 .txt；那个名字已有文件就用 -2、-3（不盖掉别的文件）。"""
    try:
        text = _reader_text(document, script=script, format_name=format_name)
        candidate = intended_path.with_suffix(".txt")
        for index in range(1, 100):
            target = candidate if index == 1 else candidate.with_name(f"{candidate.stem}-{index}.txt")
            try:
                with open(target, "x", encoding="utf-8", newline="\n") as handle:
                    handle.write(text)
                break
            except FileExistsError:
                continue
        else:
            return None
        payload = target.read_bytes()
        return {
            "path": str(target),
            "format": "txt",
            "file_size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    except OSError:
        return None


def _markdown_plain(text: str) -> str:
    """调用方 Markdown → 纯文本（块树同 PDF / DOCX）：列表留 - / 1.，引用留 >，表格一行一行用 | 隔开。"""
    from horosa_skill.reports import markdown as md

    lines: list[str] = []

    def walk(blocks: list[Any], indent: str = "") -> None:
        for block in blocks:
            if isinstance(block, (md.Paragraph, md.Heading)):
                lines.extend(indent + line for line in md.plain(block.spans).split("\n"))
            elif isinstance(block, md.ListBlock):
                for number, item in enumerate(block.items, start=block.start):
                    marker = f"{number}. " if block.ordered else "- "
                    head = item[0] if item and isinstance(item[0], md.Paragraph) else None
                    first = md.plain(head.spans).split("\n") if head else [""]
                    lines.append(indent + marker + first[0])
                    lines.extend(indent + " " * len(marker) + line for line in first[1:])
                    walk(item[1:] if head else item, indent + " " * len(marker))
            elif isinstance(block, md.Quote):
                walk(block.children, indent + "> ")
            elif isinstance(block, md.Code):
                lines.extend(indent + "    " + line for line in block.text.split("\n"))
            elif isinstance(block, md.Table):
                for row in [block.header, *block.rows]:
                    lines.append(indent + " | ".join(md.plain(cell) for cell in row))
            elif isinstance(block, md.Rule):
                lines.append(indent + "———")
            lines.append("")

    walk(md.parse(text))
    return "\n".join(lines).strip()


def _engine_plain(text: str) -> str:
    """引擎导出段 → 纯文本：去掉行内 ** 与反引号，长小数照人读版取 4 位；表格行原样（| 隔开本就是纯文本）。"""
    out = []
    for line in str(text or "").splitlines():
        if _MD_TABLE_SEP_RE.match(line):
            continue
        out.append(_display_number(_plain(line)).rstrip())
    return "\n".join(out).strip()


def _reader_text(document: dict[str, Any], *, script: str = SIMPLIFIED, format_name: str = "pdf") -> str:
    """降级 TXT 的正文：与 PDF / DOCX 同一串块，只换成纯文字。没有任何人读内容（极简的测试文档）时退回 plain_text。"""
    t = _labeler(script)
    kind = format_name.upper()
    out: list[str] = [
        t(f"说明：这份报告本应是 {kind}，排版时出了问题，改存为纯文本。内容与 {kind} 版相同；盘图画不出来，见同一报告的 PDF 或 PNG。"),
        "",
    ]
    title = str(document.get("cover_title") or document.get("title") or "")
    if title:
        out += [title, "=" * min(40, max(8, len(title) * 2)), ""]
    generated = _local_date(document.get("generated_at"))
    if generated:
        out += [t("生成于") + f" {generated}", ""]
    content_start = len(out)
    human_sections = _human_sections(document)
    for section in human_sections:
        if section.get("group") == "basis":
            out += [f"【{section.get('title') or t('基本信息')}】", _engine_plain(str(section.get("body") or "")), ""]
    ai_report = document.get("ai_report") if isinstance(document.get("ai_report"), dict) else {}
    # 只印真有的所问（没写问题时 PDF 印一句缺省话「整体综合解盘」，那不算内容）
    question = str(document.get("intro_text") or document.get("user_question") or ai_report.get("analysis_focus") or "")
    if question.strip() and document.get("style") != "chart":
        out += [f"【{document.get('intro_heading') or t('解读目标')}】", _markdown_plain(question), ""]
    figures = [f for f in document.get("figures") or [] if isinstance(f, dict)]
    for block in body_blocks(document, t):
        if block.kind == "card":
            out += [f"【{block.text}】", _markdown_plain(block.body), ""]
        elif block.kind == "heading":
            out += [block.text, "-" * min(40, max(8, len(block.text) * 2))]
        elif block.kind == "body":
            out += [_markdown_plain(block.body), ""]
        elif block.kind in {"part", "orphan_figures"}:
            out += ["", f"==== {block.text} ====", ""]
        elif block.kind == "note":
            out += [block.text, ""]
        elif block.kind == "figures" and figures:
            names = "、".join(str(f.get("title") or "") for f in figures if f.get("title"))
            out += [t("盘图（纯文本里画不出）：") + names, ""]
        elif block.kind == "section":
            heading = f"{block.cite} · {block.text}" if block.cite else block.text
            out += [heading, "-" * min(40, max(8, len(heading) * 2)), _engine_plain(block.body), ""]
    if not any(line.strip() for line in out[content_start:]):
        fallback = document.get("plain_text")
        out.append(fallback if isinstance(fallback, str) and fallback.strip() else json.dumps(document, ensure_ascii=False, indent=2))
    return "\n".join(out).rstrip() + "\n"


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
    from docx.shared import Inches, Mm, Pt, RGBColor

    t = _labeler(script)
    doc = Document()
    font_name = _docx_font_name(script)
    for section in doc.sections:
        section.page_width = Mm(210)  # A4，与 PDF 同纸张（python-docx 缺省是 Letter）
        section.page_height = Mm(297)
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
        # 与 PDF 同一套整理：全空列不印、宽而矮的盘式表转竖排。
        header, rows = _drop_empty_columns(header, rows)
        header, rows = _transpose_wide_table(header, rows)
        cols = max(1, len(header))
        table = doc.add_table(rows=1, cols=cols)
        table.autofit = False
        set_table_full_width(table)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        widths = [Inches(w / 72) for w in _column_widths(header, rows, 6.25 * 72, min(36, 6.25 * 72 / cols * 0.6))]
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
            head = header[idx] if idx < len(header) else ""
            if isinstance(head, _MdCell):
                add_spans(p, head.spans, size=9.6, bold=True, color="0F766E")
            else:
                style_run(p.add_run(head), size=9.6, bold=True, color="0F766E")
        for data_row in rows:
            row = table.add_row()
            for idx, cell in enumerate(row.cells):
                cell.width = widths[idx]
                set_cell_border(cell)
                value = data_row[idx] if idx < len(data_row) else ""
                if isinstance(value, _MdCell):
                    add_spans(cell.paragraphs[0], value.spans, size=9.6)
                else:
                    add_inline_runs(cell.paragraphs[0], value, size=9.6)
        doc.add_paragraph()

    def add_inline_runs(paragraph: Any, text: str, *, size: float = 10.2, color: str = "14211F", bold_label: bool = False) -> None:
        # **粗体** 成粗体 run，`代码` 去反引号；「键：值」行键加粗（与 PDF 同一口径）。
        text = _display_number(text)
        labelled = _LABEL_LINE_RE.match(text) if bold_label else None
        if labelled and _is_time_colon(labelled.group(1), labelled.group(3)):
            labelled = None
        if labelled:
            style_run(paragraph.add_run(labelled.group(1) + labelled.group(2)), size=size, bold=True, color=color)
            text = labelled.group(3)
        for index, piece in enumerate(_MD_BOLD_RE.split(text)):
            if piece:
                style_run(paragraph.add_run(_MD_CODE_RE.sub(r"\1", piece)), size=size, bold=index % 2 == 1, color=color)

    def add_kv_table(pairs: list[tuple[str, str]]) -> None:
        # 连续的「键：值」行排成两列对照表（与 PDF 同一口径；此前 Word 版是一行一段）。
        table = doc.add_table(rows=0, cols=2)
        table.autofit = False
        widths = [Inches(1.45), Inches(6.25 - 1.45)]
        for key, value in pairs:
            row = table.add_row()
            for idx, cell in enumerate(row.cells):
                cell.width = widths[idx]
                set_cell_border(cell, color="E3E8E5", size="4")
            style_run(row.cells[0].paragraphs[0].add_run(key), size=9.4, bold=True, color="66706D")
            add_inline_runs(row.cells[1].paragraphs[0], value, size=9.8)

    def add_text(text: str, *, style: str = "Normal") -> None:
        # 正文按块渲染：Markdown 管道表成真表格；其余逐行认标题 / 列表 / 引用 / 键值行。
        for kind, payload in _split_markdown_blocks(text):
            if kind == "table":
                add_data_table(payload["header"], payload["rows"])
                continue
            pending_kv: list[tuple[str, str]] = []
            for line_kind, marker, body in _md_lines(payload):
                labelled = _LABEL_LINE_RE.match(body) if line_kind == "text" else None
                if labelled and not _is_time_colon(labelled.group(1), labelled.group(3)) and "<" not in labelled.group(1):
                    pending_kv.append((labelled.group(1).strip(), labelled.group(3).strip()))
                    continue
                if pending_kv:
                    add_kv_table(pending_kv)
                    pending_kv = []
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
            if pending_kv:
                add_kv_table(pending_kv)

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

    def add_hyperlink(paragraph: Any, url: str, text: str, *, size: float, bold: bool, italic: bool, strike: bool) -> None:
        # 真超链接（w:hyperlink + 外部关系），不是蓝色文字。
        from docx.opc.constants import RELATIONSHIP_TYPE as RT

        rel_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
        link = OxmlElement("w:hyperlink")
        link.set(qn("r:id"), rel_id)
        run = paragraph.add_run(text)
        style_run(run, size=size, bold=bold, color="0F766E")
        run.italic = italic or None
        run.font.strike = strike or None
        run.font.underline = True
        link.append(run._r)
        paragraph._p.append(link)

    def add_spans(paragraph: Any, spans: list[Any], *, size: float = 10.2, color: str = "14211F", bold: bool = False) -> None:
        # 调用方 Markdown 的行内片段 → Word run：粗 / 斜 / 删除线 / 行内代码 / 换行 / 超链接；文字原样（不改数字、不换 emoji）。
        for span in spans:
            if span.brk:
                paragraph.add_run().add_break()
                continue
            if span.href:
                add_hyperlink(paragraph, span.href, span.text, size=size, bold=bold or span.bold, italic=span.italic, strike=span.strike)
                continue
            run = paragraph.add_run(span.text)
            style_run(run, size=size, bold=bold or span.bold, color="0F766E" if span.code else color)
            if span.italic:
                run.italic = True
            if span.strike:
                run.font.strike = True

    _LIST_STYLES = {(False, 0): "List Bullet", (False, 1): "List Bullet 2", (False, 2): "List Bullet 3",
                    (True, 0): "List Number", (True, 1): "List Number 2", (True, 2): "List Number 3"}

    def add_markdown(text: str, target: Any = None, *, depth: int = 0, quote: bool = False, tables: list[Any] | None = None,
                     toc: bool = False) -> None:
        # 调用方 Markdown 的块树（reports/markdown.py，PDF 画同一棵）。target = 文档或卡片格子；卡片里的表格交给 tables，排在卡片下方。
        from horosa_skill.reports import markdown as md

        target = doc if target is None else target
        color, size = ("66706D", 9.8) if quote else ("14211F", 10.2)

        def blocks_into(blocks: list[Any], depth: int, quote: bool) -> None:
            for block in blocks:
                if isinstance(block, md.Paragraph):
                    p = target.add_paragraph()
                    if depth or quote:
                        p.paragraph_format.left_indent = Inches(0.25 * (depth + (1 if quote else 0)))
                    add_spans(p, block.spans, size=size if not quote else 9.8, color=color if not quote else "66706D")
                elif isinstance(block, md.Heading):
                    p = target.add_paragraph()
                    p.paragraph_format.space_before = Pt(6)
                    if toc and block.level <= 2 and not depth and not quote:
                        set_outline_level(p, 1)  # 解读正文的一、二级标题进 Word 目录（与 PDF 同）
                    add_spans(p, block.spans, size=11, bold=True, color="0F766E")
                elif isinstance(block, md.ListBlock):
                    style_name = _LIST_STYLES[(block.ordered, min(depth, 2))]
                    for number, item in enumerate(block.items, start=block.start):
                        p = target.add_paragraph(style=style_name)
                        if block.ordered and block.start != 1 and number == block.start:
                            pass  # Word 的编号从 1 起；起始号不同的情形少见，内容照印
                        rest = item
                        if item and isinstance(item[0], md.Paragraph):
                            add_spans(p, item[0].spans, size=size, color=color)
                            rest = item[1:]
                        blocks_into(rest, depth + 1, quote)
                elif isinstance(block, md.Quote):
                    blocks_into(block.children, depth, True)
                elif isinstance(block, md.Code):
                    p = target.add_paragraph()
                    p.paragraph_format.left_indent = Inches(0.25 * (depth + 1))
                    for index, code_line in enumerate(block.text.split("\n")):
                        if index:
                            p.add_run().add_break()
                        style_run(p.add_run(code_line), size=9.2, color="0F766E")
                elif isinstance(block, md.Table):
                    header = [_MdCell.of(cell) for cell in block.header]
                    rows = [[_MdCell.of(cell) for cell in row] for row in block.rows]
                    if tables is not None:
                        tables.append({"header": header, "rows": rows})
                    else:
                        add_data_table(header, rows)
                elif isinstance(block, md.Rule):
                    p = target.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    style_run(p.add_run("· · ·"), size=9, color="66706D")

        blocks_into(md.parse(text), depth, quote)

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
        # 卡片内表格：渲染在卡片下方为独立真表格（表格嵌单元格在窄卡内可读性差）。
        add_markdown(body_text, cell, tables=pass_through_tables)
        doc.add_paragraph()
        while pass_through_tables:
            payload = pass_through_tables.pop(0)
            add_data_table(payload["header"], payload["rows"])

    pass_through_tables: list[dict[str, Any]] = []

    def add_figures(figures: list[dict[str, Any]]) -> None:
        # 盘图：十二宫 / 九宫格子盘画成 Word 表格；星盘轮 / 卦图 / 太乙盘 / 90° 度盘画成位图（与 PDF 同一份规格）。
        from horosa_skill.reports import figures as figure_kit

        image_fonts = _drawing_font_files(script)
        for figure in figures:
            kind = figure.get("kind")
            drawing = None
            if figure_kit.is_drawn(figure) and image_fonts is not None:
                from reportlab.lib import colors as rl_colors

                regular, bold = image_fonts["names"]
                drawing = figure_kit.figure_drawing(figure, 420 if kind in {"hexagram", "taiyi", "grid12"} else 380, regular, bold, rl_colors)
            if drawing is None and (kind == "app" or (figure_kit.is_drawn(figure) and kind in figure_kit.DRAWN_KINDS)):
                continue  # 矢量图拿不到字体文件 / 只有 app 画得出的盘没画成：跳过图、留文字说明
            if drawing is not None:
                # 矢量图转位图嵌进 Word（Pillow 画，不依赖 renderPM）；拿不到字体文件就跳过图、留文字说明。
                from horosa_skill.reports.app_charts import glyph_font_files

                png = figure_kit.drawing_to_png(drawing, {**image_fonts["files"], **glyph_font_files()}, photo_jpeg=True)
                if png is None:
                    continue
                import io

                picture = doc.add_paragraph()
                picture.alignment = WD_ALIGN_PARAGRAPH.CENTER
                shape = picture.add_run().add_picture(io.BytesIO(png), width=Inches(4.2 if kind == "hexagram" else 4.6))
                notes = [figure.get("title"), *figure_kit.figure_notes(figure, t)]
                # 替代文字（读屏软件念的那句）：图名 + 图例说明，只描述盘的结构、不做解读（Word 无障碍指南）。
                shape._inline.docPr.set("descr", "；".join(str(n) for n in notes if n)[:1000])
                caption = doc.add_paragraph()
                caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                style_run(caption.add_run("　".join(str(n) for n in notes if n)), size=8.6, color="66706D")
                continue
            grid = 4 if kind == "grid12" else 3
            table = doc.add_table(rows=grid, cols=grid)
            table.autofit = False
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            width = docx_content_width / grid
            for row in table.rows:
                for cell in row.cells:
                    cell.width = width
                    set_cell_border(cell, color="C9D3CE")
            for item in figure.get("cells") or []:
                position = figure_kit.grid_position(figure, item)
                if not position:
                    continue
                cell = table.cell(*position)
                if item.get("emphasis"):
                    set_cell_shading(cell, "EEF6F2")
                paragraph = cell.paragraphs[0]
                style_run(paragraph.add_run(str(item.get("title") or "")), size=8.6, bold=True, color="0F766E")
                if item.get("label") and kind == "grid12":
                    style_run(paragraph.add_run("　" + str(item["label"])), size=8.6 if figure.get("cell_style") != "liureng" else 14,
                              bold=figure.get("cell_style") == "liureng", color="66706D" if figure.get("cell_style") != "liureng" else "14211F")
                for line in item.get("lines") or []:
                    if line:
                        style_run(cell.add_paragraph().add_run(str(line)), size=8.2, color="14211F")
                if item.get("label") and kind == "grid9":
                    style_run(cell.add_paragraph().add_run(str(item["label"])), size=8.2, color="B7791F")
            if kind == "grid12":
                center = table.cell(1, 1).merge(table.cell(2, 2))
                set_cell_shading(center, "F3F7F5")
                info = figure.get("center") or {}
                style_run(center.paragraphs[0].add_run(str(info.get("title") or "")), size=11, bold=True, color="0F766E")
                columns = info.get("columns") or []
                for r in range(4 if columns else 0):  # 六壬四课竖格（右起一课）：课名 / 天将 / 上神 / 下神
                    cells = [str(col.get("title") or "") if r == 0 else str((col.get("lines") or ["", "", ""])[r - 1]) for col in columns]
                    style_run(center.add_paragraph().add_run("　".join(cells)), size=9 if r else 8, bold=r == 2,
                              color="14211F" if r else "66706D")
                for line in info.get("lines") or []:
                    style_run(center.add_paragraph().add_run(str(line)), size=8.8, color="14211F")
            caption = doc.add_paragraph()
            caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
            notes = [*figure_kit.figure_notes(figure, t), figure.get("title")]  # 含 legend（自绘格子盘的画法说明）
            style_run(caption.add_run("　".join(str(x) for x in notes if x)), size=8.6, color="66706D")
        if image_fonts is None and any(f.get("kind") in figure_kit.DRAWN_KINDS for f in figures):
            note = doc.add_paragraph()
            style_run(note.add_run(t("图形盘图（星盘 / 卦象 / 太乙盘 / 度盘）见同一报告的 PDF 版；下文为完整的位置与相位表。")), size=9, color="66706D")

    ai_report = document.get("ai_report") if isinstance(document.get("ai_report"), dict) else {}
    display_question = str(document.get("intro_text") or "") or _display_question(document, ai_report, t)
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
    run = p.add_run(str(document.get("cover_title") or document.get("title") or t("结构化咨询报告")))
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
    # 域的缓存结果预填各章标题：WPS / Pages / 网页预览这些不更新域的软件也能看到一份目录（此前只印一句占位话）；
    # Word 打开时照常按 updateFields 重建成带页码、可点击的目录。
    placeholder = OxmlElement("w:r")
    toc_lines = [t("目录（Word 中右键「更新域」生成页码）")] + [
        (f"{section['cite_id']} · " if section.get("group") == "chart" and section.get("cite_id") else "")
        + str(section.get("title") or "")
        for section in _human_sections(document) if section.get("group") != "basis"
    ]
    for index, line in enumerate(toc_lines):
        if index:
            placeholder.append(OxmlElement("w:br"))
        text_element = OxmlElement("w:t")
        text_element.set(qn("xml:space"), "preserve")
        text_element.text = line
        placeholder.append(text_element)
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
    add_markdown(display_question)
    human_sections = [s for s in _human_sections(document) if isinstance(s, dict)]
    for section in human_sections:
        if section.get("group") == "basis":
            add_heading_block(str(section.get("title") or t("基本信息")))
            add_text(str(section.get("body") or ""))
    figures = [f for f in document.get("figures") or [] if isinstance(f, dict)]
    for block in body_blocks(document, t):
        if block.kind == "card":
            add_card(block.text, block.body, accent=_DOCX_ACCENTS[block.role])
        elif block.kind == "heading":
            add_heading_block(block.text, level=_DOCX_HEADING_LEVELS[block.role])
        elif block.kind == "body":  # 调用方写的（解读正文 / 摘要）：Markdown 块树
            add_markdown(block.body, toc=True)
        elif block.kind == "part":
            doc.add_page_break()
            add_heading_block(block.text)
        elif block.kind == "note":
            style_run(doc.add_paragraph().add_run(block.text), size=9, color="66706D")
        elif block.kind == "figures":
            add_figures(figures)
        elif block.kind == "section":
            add_heading_block(f"{block.cite} · {block.text}" if block.cite else block.text, level=2 if block.in_part else 1)
            add_text(block.body)
        # orphan_figures：DOCX 一直不补印（盘图只跟着「完整盘面」走）

    # 文档元数据：文件属性可检索/归档（标题/作者/主题/关键词/创建时间）。
    # OOXML core property 单项硬限 255 字符；search_index 里可能混入整段长文本，先滤短词再截断。
    source_meta = document.get("source") if isinstance(document.get("source"), dict) else {}
    props = doc.core_properties
    props.title = _core_prop_text(document.get("title") or t("结构化咨询报告"))
    props.author = "Horosa Skill"
    props.subject = _core_prop_text(source_meta.get("technique_label") or source_meta.get("tool_name") or "")
    # 文件属性的关键词给人检索用（评审 R-14）：技法名 + 正文里真有的章名。此前取检索索引的键，混着「直接回答」「证据绑定」
    # 这类模板内部用语与 bazi_birth 这类内部标识。
    candidates = [source_meta.get("technique_label"), *(section.get("title") for section in _human_sections(document))]
    short_keywords = [str(k).strip() for k in candidates
                      if k and str(k).strip() and len(str(k).strip()) <= 24 and not _INTERNAL_KEYWORD_RE.match(str(k).strip())]
    props.keywords = _core_prop_text(", ".join(dict.fromkeys(short_keywords[:12])))
    props.comments = "Generated by Horosa Skill report renderer"
    # python-docx 的模板自带 2013-12-23 的创建 / 修改时间与空的修改人：写成这次生成的时刻（评审 R-14）。
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).replace(microsecond=0)
    props.created = now
    props.modified = now
    props.last_modified_by = "Horosa Skill"
    props.revision = 1
    props.language = _docx_lang(script)
    _docx_apply_language_and_font_fallback(doc, script, font_name, qn)

    # 页脚：报告标题 + 「第 X 页 / 共 Y 页」域（与 PDF 页脚对齐）。
    doc.sections[0].different_first_page_header_footer = True  # 封面不印页脚（与 PDF 一致）
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
# 键：最长 14 字；带括注 / 数字的星名（「金 (12th; 5R12R)」）放宽到 24 字。键里不能有逗号 / 句号 / 分号——那是句子。
_LABEL_LINE_RE = re.compile(r"^((?:[^：:|*`\[\]，。；]{1,14})|(?=[^：:]*[()（）0-9])[^：:|*`\[\]，。；]{15,24})([：:])(.+)$")
_LISTING_MIN_LINES = 14  # 连续这么多条互不相干的短行才分栏排（几行的小段照常一行一段）
# PDF 版面的「长」：格子 / 键值的值超过这么多字就按可跨页的方式排；标题超过这么多字就不进标题条（见 _render_pdf）。
_LONG_CELL_CHARS = 400
_LONG_HEADING_CHARS = 120
_PANEL_MIN_ROW_HEIGHT = 12.0  # 分栏清单一行的最小高度（8.8 pt 字、行距 12.4 + 上下各 1.6 内边距，取保守下限）


def _is_time_colon(label: str, value: str) -> bool:
    return bool(re.search(r"\d\s*$", label) and re.match(r"\s*\d", value))


_KINSOKU_NO_START = "，：；？！）》〉」』】〕…·．％、。"
_KINSOKU_NO_END = "（《〈「『【〔"


def _extend_kinsoku() -> None:
    """reportlab 的行首 / 行尾禁则表只有半角 , : 与部分日文标点，全角 ，：；（） 不在里面——报告里 229 行以「，、」开头
    （v0.43 评审）。补进去（只增不删，幂等）；wordWrap="CJK" 的段落按它断行。"""
    from reportlab.lib import textsplit

    missing_start = "".join(ch for ch in _KINSOKU_NO_START if ch not in textsplit.ALL_CANNOT_START)
    if missing_start:
        textsplit.ALL_CANNOT_START += missing_start
    missing_end = "".join(ch for ch in _KINSOKU_NO_END if ch not in textsplit.ALL_CANNOT_END)
    if missing_end:
        textsplit.ALL_CANNOT_END += missing_end


def _drop_empty_columns(header: list[str], rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    """整列都是空 / 「—」的列不印（星体表的「逆行」「月宿」、塔罗的「尊位」）；至少三行数据才判，首列永远保留。"""
    if len(rows) < 3 or len(header) < 3:
        return header, rows
    blank = {"", "—", "-", "–", "－", "无"}
    keep = [i for i in range(len(header))
            if i == 0 or any(str(row[i] if i < len(row) else "").strip() not in blank for row in rows)]
    if len(keep) == len(header):
        return header, rows
    return [header[i] for i in keep], [[row[i] if i < len(row) else "" for i in keep] for row in rows]


def _is_sentence(text: str) -> bool:
    """「◆ 兄弟数：3–9 人」「◆ 互见…：刑伤已定。」是一条结论，不是小标题：冒号后有值，或以句号收尾。"""
    text = text.strip()
    _, sep, tail = text.partition("：") if "：" in text else text.partition(":")
    return bool(sep and tail.strip()) or text.endswith(("。", "！", "？"))


def _drawing_font_files(script: str) -> dict[str, Any] | None:
    """DOCX 位图要的字体：注册 PDF 用的那一对字体，取回它们的文件路径与子字体序号；拿不到（CID 回退字体）返回 None。"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    try:
        regular, bold = _register_pdf_fonts(pdfmetrics, UnicodeCIDFont, TTFont, script)
    except RuntimeError:
        return None
    files = {name: getattr(pdfmetrics.getFont(name), "horosa_source", None) for name in (regular, bold)}
    if not all(files.values()):
        return None
    return {"names": (regular, bold), "files": files}


def _mostly_latin(markup: str) -> bool:
    text = re.sub(r"<[^>]+>", "", markup)
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    cjk = sum(1 for ch in text if ord(ch) >= 0x2E80)
    return latin >= 6 and latin > cjk * 2


def _local_date(value: Any) -> str:
    """报告的 generated_at（UTC ISO）→ 本机时区的日期；解析不了就不印。"""
    from datetime import datetime

    try:
        return datetime.fromisoformat(str(value)).astimezone().strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def _plain(text: str) -> str:
    """量宽度用：去掉行内 Markdown 记号（粗体星号、反引号），只留会印出来的字。"""
    return str(text or "").replace("**", "").replace("`", "")


_LONG_FLOAT_RE = re.compile(r"(?<![\d.])(-?\d+\.\d{4})\d{3,}(?![\d.])")


def _display_number(text: str) -> str:
    """人读版里把 7 位以上小数（引擎原文的 `误差0.7548645849180389`）四舍五入到 4 位。只对引擎原文；机读 JSON 不经这里。
    emoji 不在这里换（v0.50.0）：DOCX 原样保留（Word 有彩色字体兜底），PDF 在 _pdf_symbols 里按含义换成画得出的符号。"""
    return _LONG_FLOAT_RE.sub(lambda m: f"{float(m.group(0)):.4f}", text)


# ── PDF 里的 emoji 与符号（v0.50.0，评审 R-02）────────────────────────────────
# PDF 只能嵌 TrueType 轮廓字体，彩色 emoji（Apple Color Emoji / Segoe UI Emoji 是位图或 COLR）一个都画不出来。此前只把
# U+1F300–1FAFF 一段换成 ▸：✅ ❌ ⚠️ ⭐ 1️⃣ 不在这一段，印成方块；🔴 / 🟢、👍 / 👎 全成 ▸，意思反了也看不出。
# 现在：先去掉不占位的修饰（变体选择符、零宽连接、肤色），键帽数字成圈码，常见的按含义换（不同含义换成不同符号，红绿灯保留颜色）；
# 其余符号由 _wrap_missing_glyphs_chain 按真实字体的 cmap 判：主字体和补字链都画不了才换成 ▸。DOCX 不经这里，原样保留 emoji。
_INVISIBLE_MARKS = frozenset([0xFE0E, 0xFE0F, 0x200D, *range(0x1F3FB, 0x1F400), *range(0xE0020, 0xE0080)])
_KEYCAP = 0x20E3
_KEYCAP_DIGITS = {"0": "⓪", "1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤", "6": "⑥", "7": "⑦", "8": "⑧", "9": "⑨", "#": "#", "*": "*"}
_RED, _ORANGE, _AMBER, _GREEN, _BLUE, _PURPLE, _BROWN = "#c53030", "#dd6b20", "#b7791f", "#2f855a", "#2b6cb0", "#6b46c1", "#8b5a2b"
_PDF_SYMBOLS: dict[str, tuple[str, str | None]] = {
    # 对 / 错
    "✅": ("✓", _GREEN), "✔": ("✓", None), "☑": ("✓", None), "🆗": ("✓", None),
    "❌": ("✗", _RED), "❎": ("✗", None), "✖": ("✗", None), "🚫": ("✗", _RED), "⛔": ("✗", _RED),
    # 星 / 提示
    "⭐": ("★", _AMBER), "🌟": ("★", _AMBER), "✨": ("✦", _AMBER), "💫": ("✦", None),
    "❗": ("!", _RED), "❕": ("!", None), "‼": ("!!", _RED), "❓": ("?", None), "❔": ("?", None), "⁉": ("!?", None),
    "💡": ("◆", _AMBER), "📌": ("▸", None), "📍": ("▸", None), "👉": ("▸", None), "🔹": ("◆", _BLUE), "🔸": ("◆", _ORANGE),
    "🔺": ("▲", _RED), "🔻": ("▼", _RED), "📈": ("↗", _GREEN), "📉": ("↘", _RED),
    "👍": ("⊕", _GREEN), "👎": ("⊖", _RED),
    # 方向
    "➡": ("→", None), "⬅": ("←", None), "⬆": ("↑", None), "⬇": ("↓", None), "↗": ("↗", None), "↘": ("↘", None),
    "🔄": ("⟳", None), "🔁": ("⟳", None),
    # 红绿灯：同一个圆点，颜色不同（意思不同就印得不同）
    "🔴": ("●", _RED), "🟠": ("●", _ORANGE), "🟡": ("●", _AMBER), "🟢": ("●", _GREEN), "🔵": ("●", _BLUE),
    "🟣": ("●", _PURPLE), "🟤": ("●", _BROWN), "⚫": ("●", None), "⚪": ("○", None),
    "🟥": ("■", _RED), "🟧": ("■", _ORANGE), "🟨": ("■", _AMBER), "🟩": ("■", _GREEN), "🟦": ("■", _BLUE),
    "🟪": ("■", _PURPLE), "🟫": ("■", _BROWN), "⬛": ("■", None), "⬜": ("□", None),
    "🔟": ("⑩", None),
}


def _pdf_symbols(markup: str) -> str:
    """PDF 段落标记里的 emoji → 画得出的符号（只动标签外的文字）。见上方表的说明。"""
    if markup.isascii():
        return markup
    out: list[str] = []
    in_tag = False
    index, size = 0, len(markup)
    while index < size:
        ch = markup[index]
        if in_tag:
            out.append(ch)
            in_tag = ch != ">"
            index += 1
            continue
        if ch == "<":
            in_tag = True
            out.append(ch)
            index += 1
            continue
        code = ord(ch)
        # 键帽：数字 / # / * + (FE0F) + U+20E3
        if ch in _KEYCAP_DIGITS:
            follow = index + 1
            if follow < size and ord(markup[follow]) == 0xFE0F:
                follow += 1
            if follow < size and ord(markup[follow]) == _KEYCAP:
                out.append(_KEYCAP_DIGITS[ch])
                index = follow + 1
                continue
        if code in _INVISIBLE_MARKS or code == _KEYCAP:
            index += 1
            continue
        mapped = _PDF_SYMBOLS.get(ch)
        if mapped is not None:
            text, color = mapped
            out.append(f'<font color="{color}">{text}</font>' if color else text)
        else:
            out.append(ch)
        index += 1
    return "".join(out)


def _is_symbol(ch: str) -> bool:
    """会被「画不了就换 ▸」的字：符号（So）与 emoji 区。字母、汉字从不换（v0.43 起的规矩：正文文字补不了就原样留）。"""
    import unicodedata

    code = ord(ch)
    return unicodedata.category(ch) == "So" or 0x1F000 <= code <= 0x1FAFF or 0x2600 <= code <= 0x27BF


_CITE_RE = re.compile(r"\[(E\d+)\]")


def _md_inline(text: str, anchors: frozenset[str] = frozenset()) -> str:
    """一行 Markdown → reportlab 段落标记：先转义，再还原 **粗体** 与 `代码`（引擎正文里常见的两种）。

    anchors = 本报告里真有的盘面段号：AI 正文里的 [E3] 变成跳到该段的内部链接（STORM 式行内引用）；
    报告里没有的段号原样留字，不生成指向空处的链接（reportlab 对悬空目标会报错）。"""
    escaped = _esc(_display_number(text))
    escaped = _MD_BOLD_RE.sub(r"<b>\1</b>", escaped)
    escaped = _MD_CODE_RE.sub(r'<font color="#0f766e">\1</font>', escaped)
    if anchors:
        escaped = _CITE_RE.sub(lambda m: f'<a href="#{m.group(1)}" color="#0f766e">[{m.group(1)}]</a>'
                               if m.group(1) in anchors else m.group(0), escaped)
    return escaped


def _md_spans_markup(spans: list[Any], anchors: frozenset[str] = frozenset()) -> str:
    """调用方 Markdown 的行内片段（reports/markdown.Span）→ reportlab 段落标记。不四舍五入数字（那只对引擎原文）。
    [E3] 段号照旧链到报告里真有的盘面段；链接是真链接（只有 http / https / mailto，解析时已筛过）。"""
    out: list[str] = []
    for span in spans:
        if span.brk:
            out.append("<br/>")
            continue
        text = _esc(span.text)
        if span.code:
            text = f'<font color="#0f766e">{text}</font>'
        elif anchors:
            text = _CITE_RE.sub(lambda m: f'<a href="#{m.group(1)}" color="#0f766e">[{m.group(1)}]</a>'
                                if m.group(1) in anchors else m.group(0), text)
        if span.strike:
            text = f"<strike>{text}</strike>"
        if span.italic:
            text = f"<i>{text}</i>"
        if span.bold:
            text = f"<b>{text}</b>"
        if span.href:
            text = f'<a href="{html.escape(span.href, quote=True)}" color="#0f766e"><u>{text}</u></a>'
        out.append(text)
    return "".join(out)


_LINES_PER_FLOWABLE = 40
# 兜底（_render_pdf 里的 Guarded）摊开过的块：只给测试看「这块是正常排出来的，还是靠兜底」。
LAYOUT_SPILLS: list[str] = []


def _line_groups(spans: list[Any], size: int) -> list[list[Any]]:
    """按换行把一段的行内片段切成每组至多 size 行（组间的那个换行去掉：组本身就是新的一行）。"""
    groups: list[list[Any]] = [[]]
    lines = 0
    for span in spans:
        if span.brk:
            lines += 1
            if lines % size == 0:
                groups.append([])
                continue
        groups[-1].append(span)
    return [group for group in groups if group] or [[]]


def _code_markup(text: str) -> str:
    """代码块：保留缩进与换行（空格转不断行空格），不解释里面的任何记号。"""
    return "<br/>".join(html.escape(line).replace(" ", "&nbsp;") for line in str(text).split("\n")) or "&nbsp;"


class _MdCell(str):
    """调用方 Markdown 表格的一格：字符串值 = 纯文字（量列宽、判空列用），`spans` = 行内片段（PDF / DOCX 各自画）。"""

    spans: list[Any]

    @classmethod
    def of(cls, spans: list[Any]) -> _MdCell:
        cell = cls("".join(span.text for span in spans))
        cell.spans = spans
        return cell

    def markup(self, anchors: frozenset[str] = frozenset()) -> str:
        return _md_spans_markup(self.spans, anchors)


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
        elif stripped.startswith("◆") and len(stripped) <= 40 and not _is_sentence(stripped.lstrip("◆ ")):
            out.append(("heading", "###", stripped.lstrip("◆ ").strip()))
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
    # 表头尽量不折行（「起始年」被挤成「起始 / 年」）：每列至少放得下表头，表头总宽超过整行时才按比例退让。
    head_need = [_visual_width(str(header[i] if i < len(header) else "")) * 4.6 + 11 for i in range(cols)]
    # 数字 / 西文串（大限「112~121」、「2036-丙辰」的年份）也不该被拆开：每列至少放得下本列最长的那一串。
    token_need = [
        max([len(tok) * 4.6 + 11 for row in rows if i < len(row) for tok in _UNBREAKABLE_RE.findall(_plain(str(row[i])))] or [0])
        for i in range(cols)
    ]
    need = [max(h, t_) for h, t_ in zip(head_need, token_need)]
    if sum(need) <= total:
        minimums = [max(minimum, n) for n in need]
    elif sum(head_need) <= total:
        minimums = [max(minimum, n) for n in head_need]
    else:
        minimums = [minimum] * cols
    widths = [max(w * scale, floor) for w, floor in zip(weights, minimums)]
    overflow = sum(widths) - total
    if overflow > 0:  # 超出的部分只从「比自己下限宽」的列里按余量比例扣，每列都不跌破自己的下限
        flexible = [i for i, w in enumerate(widths) if w > minimums[i]]
        flex_total = sum(widths[i] - minimums[i] for i in flexible) or 1
        for i in flexible:
            widths[i] -= overflow * (widths[i] - minimums[i]) / flex_total
    return widths


_UNBREAKABLE_RE = re.compile(r"[0-9A-Za-z][0-9A-Za-z.~\-–/:%°′″]*")


def _transpose_wide_table(header: list[str], rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    """宽而矮的表（≤4 行数据、≥7 列，典型是八字四柱）转成竖排：列 = 年柱 / 月柱 / 日柱 / 时柱，行 = 干支 / 藏干 / 十神…

    这正是排盘的传统盘式；横排时九列挤在一行里，藏干这种长格被压成三行。只换行列，不改任何一格的内容。
    """
    if not rows or len(rows) > 4 or len(header) < 7:
        return header, rows
    new_header = [header[0]] + [row[0] if row else "" for row in rows]
    new_rows = [[header[i]] + [row[i] if i < len(row) else "" for row in rows] for i in range(1, len(header))]
    return new_header, new_rows


def _label_first_widths(header: list[str], rows: list[list[str]], total: float) -> list[float]:
    """转置后的盘式表：首列（干支 / 藏干…）按内容定宽，其余各柱等宽——四柱并排要齐。"""
    first = max([_visual_width(header[0])] + [_visual_width(row[0]) for row in rows if row])
    first_width = min(max(first * 5.2 + 14.0, total * 0.12), total * 0.28)
    rest = (total - first_width) / max(len(header) - 1, 1)
    return [first_width] + [rest] * (len(header) - 1)


def _panel_count(widths: list[int], *, budget: int) -> int:
    """一列短行（或一张窄表）能并排放几栏：每栏需要 sum(widths) 个视觉宽度单位，整页约 budget 个。"""
    need = max(sum(widths), 1) + 2
    return max(1, min(3, budget // need))



def _render_pdf(document: dict[str, Any], output_path: Path, script: str = SIMPLIFIED) -> list[str]:
    """排版并写出 PDF；返回要告诉调用方的事（如：没有可嵌入的中文字体）。"""
    cite_anchors = frozenset(
        str(section.get("cite_id")) for section in _human_sections(document) if section.get("group") == "chart" and section.get("cite_id")
    )

    def inline(text: str) -> str:
        if isinstance(text, _MdCell):
            return text.markup(cite_anchors)
        return _md_inline(text, cite_anchors)

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        CondPageBreak, Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )
    from reportlab.platypus.flowables import HRFlowable
    from reportlab.platypus.tables import Table as RLTable
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    _extend_kinsoku()
    font_name, bold_font_name = _register_pdf_fonts(pdfmetrics, UnicodeCIDFont, TTFont, script)
    t = _labeler(script)
    # 本机没有能嵌入的中文 TrueType：PDF 用 reportlab 自带的 CID 字体（不嵌入，由阅读器的中文字体显示）。此前静默如此（评审 R-16）：
    # 换台电脑打开字形可能不同、个别符号缺字。结果的 warnings 与 PDF 封面都写明，并说怎么办。
    font_note = "" if isinstance(pdfmetrics.getFont(font_name), TTFont) else t(
        "本机没有可嵌入的中文字体，这份 PDF 的中文由阅读器自带的字体显示（未嵌入）：换一台电脑打开，字形可能不同，个别符号可能缺字。"
        "装一款中文 TrueType 字体（如 Noto Sans CJK）后重出即可嵌入。")
    # 主字体缺字形的生僻字（Ext-B 起，如《灵棋经》里的 𡛸 𤣥 𥦗）交给补字字体画——不补就是方块。下面所有 Paragraph 都经它。
    patch_glyphs = _pdf_glyph_fallback(pdfmetrics, TTFont, font_name, bold_font_name, script)
    # 带标签 PDF（PDF/UA-1，reports/pdf_tagging.py）：段落打 P / H 标签，版式表的底色与框线标 Artifact，数据表格子是 TH / TD。
    from horosa_skill.reports import pdf_tagging as tagging

    _Paragraph = tagging.TaggedParagraph
    def _own_font(table: Any) -> Any:
        # reportlab 画字符串格子（含占位的空串）前会 setFont 成格子样式的字体，缺省是不嵌入的 Helvetica——PDF 里就多了一款没嵌入的
        # 字体，「PDF/UA-1」的声明就不成立（评审 R-15）。每张表的格子字体都设成报告字体。
        table.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), font_name)]))
        return table

    def Table(*args: Any, **kwargs: Any) -> Any:  # noqa: N802 - 下文所有版式表沿用原名
        return _own_font(tagging.layout_table(*args, **kwargs))

    def data_table(*args: Any, **kwargs: Any) -> Any:
        return _own_font(tagging.data_table(*args, **kwargs))
    heading_tags = {
        "HorosaCoverTitle": "H1", "HorosaPart": "H1",
        "HorosaHeading": "H2", "HorosaSection0": "H2", "HorosaTocTitle": "H2",
        "HorosaSection1": "H3", "HorosaSubHeading": "H3", "HorosaCoverSection": "H3", "CardTitle": "H3",
        "HorosaInnerHeading": "H4",
    }

    latin_styles: dict[str, Any] = {}

    def Paragraph(text: str, *args: Any, **kwargs: Any) -> Any:  # noqa: N802 - 与 reportlab 同名，下文调用点不变
        # 以西文为主的段落（North Node、King of Cups、中点名）不走 CJK 断行——那会把单词拆成「North Nod / e」。
        style = args[0] if args else kwargs.get("style")
        if style is not None and getattr(style, "wordWrap", None) == "CJK" and _mostly_latin(text):
            if style.name not in latin_styles:
                latin_styles[style.name] = ParagraphStyle(f"{style.name}Latin", parent=style, wordWrap=None)
            if args:
                args = (latin_styles[style.name], *args[1:])
            else:
                kwargs["style"] = latin_styles[style.name]
        paragraph = _Paragraph(patch_glyphs(_pdf_symbols(text)), *args, **kwargs)
        paragraph.pdf_tag = heading_tags.get(str(getattr(paragraph.style, "name", "")).removesuffix("Latin"), "P")
        return paragraph

    styles = getSampleStyleSheet()
    page_width, page_height = A4
    left_margin = right_margin = 22 * mm
    top_margin = bottom_margin = 18 * mm
    # Frame 四边各有 6 pt 内边距：可用宽 = 版心 − 12（此前按版心算，满宽表格右出框 12 pt，键值表看着往右偏）。
    content_width = page_width - left_margin - right_margin - 12
    ink = colors.HexColor("#14211f")
    muted = colors.HexColor("#66706d")
    green = colors.HexColor("#0f766e")
    amber = colors.HexColor("#b7791f")
    paper = colors.HexColor("#fbfaf5")
    pale = colors.HexColor("#eef6f2")
    line = colors.HexColor("#d8ded9")
    stripe = colors.HexColor("#f7faf8")
    dark = colors.HexColor("#11231f")

    base = ParagraphStyle(
        "HorosaBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10,
        leading=16.5,
        textColor=ink,
        spaceAfter=4,
        wordWrap="CJK",  # 中文按字断行 + 行首禁则（标点不落行首，见 _extend_kinsoku）
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
    cover_label_style = ParagraphStyle("HorosaCoverLabel", parent=cover_meta, fontSize=9.5, leading=14,
                                       textColor=colors.HexColor("#e9c46a"))
    cover_section_style = ParagraphStyle("HorosaCoverSection", parent=base, fontName=bold_font_name, fontSize=10.5,
                                         leading=15, textColor=green, spaceAfter=4)
    cover_note_style = ParagraphStyle("HorosaCoverNote", parent=base, fontSize=8.8, leading=13.5, textColor=muted,
                                      spaceAfter=0)
    cover_footnote_style = ParagraphStyle("HorosaCoverFootnote", parent=base, fontSize=8, leading=12, textColor=muted)
    toc_title_style = ParagraphStyle("HorosaTocTitle", parent=heading, fontSize=17, leading=24, spaceBefore=4,
                                     spaceAfter=10)
    cover_key = ParagraphStyle("HorosaCoverKey", parent=base, fontSize=8.4, leading=12, textColor=muted, spaceAfter=0)
    cover_value = ParagraphStyle("HorosaCoverValue", parent=base, fontName=bold_font_name, fontSize=10, leading=14,
                                 spaceAfter=0)

    def cover_info_grid(pairs: list[tuple[str, str]]) -> Any:
        # 封面信息卡：每格「小字键 / 粗体值」上下两行，三格一排；长值（所问、地点全称）独占一整排。
        cells: list[list[Any]] = []
        row: list[Any] = []
        spans: list[tuple[int, int]] = []
        per_row = 3
        for key, value in pairs:
            cell = [Paragraph(_esc(key), cover_key), Paragraph(inline(value), cover_value)]
            if _visual_width(value) > 24:
                if row:
                    cells.append(row + [""] * (per_row - len(row)))
                    row = []
                spans.append((len(cells), len(cells)))
                cells.append([cell] + [""] * (per_row - 1))
                continue
            row.append(cell)
            if len(row) == per_row:
                cells.append(row)
                row = []
        if row:
            cells.append(row + [""] * (per_row - len(row)))
        style = [
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.6, line),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, line),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]
        style += [("SPAN", (0, r), (-1, r)) for r, _ in spans]
        # splitInRow：「所问」一类长值（上千字）独占的那一行可以续到下一页，不让封面整份排不下。
        return Table(cells, colWidths=[content_width / per_row] * per_row, style=TableStyle(style), splitInRow=1)

    section_styles = [
        ParagraphStyle("HorosaSection0", parent=heading, fontSize=14, leading=19, spaceBefore=0, spaceAfter=0),
        ParagraphStyle("HorosaSection1", parent=heading, fontSize=12.5, leading=17, spaceBefore=0, spaceAfter=0),
    ]
    part_style = ParagraphStyle("HorosaPart", parent=heading, fontSize=19, leading=26, textColor=colors.white)
    inner_heading = ParagraphStyle("HorosaInnerHeading", parent=base, fontName=bold_font_name, fontSize=10.4,
                                   leading=16, textColor=green, spaceBefore=6, spaceAfter=2)
    bullet_style = ParagraphStyle("HorosaBullet", parent=base, leftIndent=14, bulletIndent=3, spaceAfter=2,
                                  bulletFontName=font_name)  # 列表序号与正文同一字体（缺省是不嵌入的 Helvetica）
    quote_style = ParagraphStyle("HorosaQuote", parent=base, leftIndent=12, textColor=muted, fontSize=9.2)
    code_style = ParagraphStyle("HorosaCode", parent=base, fontSize=8.8, leading=13, textColor=green, backColor=stripe,
                                borderPadding=(3, 4, 3, 4), spaceBefore=3, spaceAfter=6, wordWrap="CJK")
    muted_note = ParagraphStyle("HorosaMutedNote", parent=base, fontSize=8.8, leading=13, textColor=muted)
    kv_label = ParagraphStyle("HorosaKvLabel", parent=base, fontName=bold_font_name, fontSize=8.8, leading=13,
                              textColor=muted, spaceAfter=0)
    kv_value = ParagraphStyle("HorosaKvValue", parent=base, fontSize=9.4, leading=13.6, spaceAfter=0)
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

    figures = [f for f in document.get("figures") or [] if isinstance(f, dict)]
    cell_base = ParagraphStyle("HorosaFigCell", parent=base, fontSize=7.6, leading=10.2, spaceAfter=0)
    figure_styles = {
        "cell": cell_base,
        "cell_muted": ParagraphStyle("HorosaFigMuted", parent=cell_base, textColor=muted),
        "cell_strong": ParagraphStyle("HorosaFigStrong", parent=cell_base, fontName=bold_font_name, fontSize=8.2),
        "cell_title": ParagraphStyle("HorosaFigTitle", parent=cell_base, fontName=bold_font_name, fontSize=8.2,
                                     textColor=green),
        "cell_big": ParagraphStyle("HorosaFigBig", parent=cell_base, fontName=bold_font_name, fontSize=15, leading=19,
                                   alignment=TA_CENTER),
        "center_title": ParagraphStyle("HorosaFigCenterTitle", parent=cell_base, fontName=bold_font_name, fontSize=11,
                                       leading=15, alignment=TA_CENTER, textColor=green),
        "center": ParagraphStyle("HorosaFigCenter", parent=cell_base, fontSize=8.4, leading=12, alignment=TA_CENTER),
        "caption": ParagraphStyle("HorosaFigCaption", parent=base, fontSize=8.2, leading=12, textColor=muted,
                                  alignment=TA_CENTER, spaceBefore=2),
    }

    def figure_flowables() -> list[Any]:
        from horosa_skill.reports.figures import pdf_flowables

        return pdf_flowables(figures, content_width=content_width, font=font_name, bold_font=bold_font_name,
                             styles=figure_styles, colors=colors, paragraph=Paragraph, esc=_esc, t=t,
                             table=Table, figure=tagging.TaggedFigure)

    frame_height = page_height - top_margin - bottom_margin - 12

    class Guarded(Flowable):
        """包住一块版式表：照常排；只有在一整页上都排不下、它自己又拆不开时，才把格子里的内容摊成段落照排。"""

        def __init__(self, inner: Any) -> None:
            super().__init__()
            self.inner = inner
            self.keepWithNext = getattr(inner, "keepWithNext", 0)

        def __getattr__(self, name: str) -> Any:  # 目录 / 书签标记、测试读的格子都在里面那块上
            if name == "inner":
                raise AttributeError(name)
            return getattr(self.inner, name)

        def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
            canvas = self.__dict__.get("canv")
            self.width, self.height = (self.inner.wrapOn(canvas, avail_width, avail_height) if canvas is not None
                                       else self.inner.wrap(avail_width, avail_height))
            return self.width, self.height

        def split(self, avail_width: float, avail_height: float) -> list[Any]:
            canvas = self.__dict__.get("canv")
            parts = (self.inner.splitOn(canvas, avail_width, avail_height) if canvas is not None
                     else self.inner.split(avail_width, avail_height))
            if parts or avail_height < frame_height * 0.95:
                return parts
            LAYOUT_SPILLS.append(type(self.inner).__name__)
            return _spill(self.inner)

        def getSpaceBefore(self) -> float:  # noqa: N802 - reportlab 接口名
            return self.inner.getSpaceBefore()

        def getSpaceAfter(self) -> float:  # noqa: N802 - reportlab 接口名
            return self.inner.getSpaceAfter()

        def drawOn(self, canvas: Any, x: float, y: float, _sW: float = 0) -> None:  # noqa: N802 - reportlab 接口名
            self.inner.drawOn(canvas, x, y, _sW)

    card_box = colors.HexColor("#dfe7e1")

    class CardPiece(Flowable):
        """卡片的一块：里面的段落照常排（能拆就跟着拆），外面画白底、框线与左侧色条（标 Artifact）。
        首块画上框、末块画下框；拆开时前半不画下框、后半不画上框——跨页的卡片看起来就是一张续到下一页的卡。"""

        _PAD_X = 11

        def __init__(self, inner: Any, accent: Any, *, first: bool, last: bool) -> None:
            super().__init__()
            self.inner, self.accent, self.first, self.last = inner, accent, first, last
            self._content = [inner]  # 测试与书签沿用「容器」的读法
            self._pad_top = 7 if first else 2
            self._pad_bottom = 7 if last else 2

        def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
            canvas = self.__dict__.get("canv")
            inner_width = avail_width - 2 * self._PAD_X
            room = avail_height - self._pad_top - self._pad_bottom
            _, height = (self.inner.wrapOn(canvas, inner_width, room) if canvas is not None
                         else self.inner.wrap(inner_width, room))
            self.width, self.height = avail_width, height + self._pad_top + self._pad_bottom
            return self.width, self.height

        def split(self, avail_width: float, avail_height: float) -> list[Any]:
            canvas = self.__dict__.get("canv")
            inner_width = avail_width - 2 * self._PAD_X
            room = avail_height - self._pad_top - 2
            parts = (self.inner.splitOn(canvas, inner_width, room) if canvas is not None
                     else self.inner.split(inner_width, room))
            if len(parts) < 2:
                return []
            return [CardPiece(parts[0], self.accent, first=self.first, last=False),
                    *[CardPiece(part, self.accent, first=False, last=self.last and index == len(parts) - 2)
                      for index, part in enumerate(parts[1:])]]

        def draw(self) -> None:
            canvas = self.canv
            tagged = isinstance(canvas, tagging.TaggingCanvas)
            if tagged:
                canvas.artifact_begin()
            canvas.saveState()
            canvas.setFillColor(colors.white)
            canvas.rect(0, 0, self.width, self.height, fill=1, stroke=0)
            canvas.setStrokeColor(card_box)
            canvas.setLineWidth(0.6)
            canvas.line(self.width, 0, self.width, self.height)
            if self.first:
                canvas.line(0, self.height, self.width, self.height)
            if self.last:
                canvas.line(0, 0, self.width, 0)
            canvas.setStrokeColor(self.accent)
            canvas.setLineWidth(3)
            canvas.line(0, 0, 0, self.height)
            canvas.restoreState()
            if tagged:
                canvas.artifact_end()
            self.inner.drawOn(canvas, self._PAD_X, self._pad_bottom)

    def settle_keep_with_next(story: list[Any]) -> list[Any]:
        """标题与它下面的第一块排在同一页（评审 R-10）。不用 reportlab 的 keepWithNext：它把标题与下一块包成 KeepTogether，
        下一块本身是 KeepTogether（整张不拆的小表、盘图）时内层量出来恒为「无限高」，于是每次都强制换页——标题跟着盘图去了下一页，
        上一页留下大半空白。这里自己分组：
        - 下一块是 KeepTogether：把标题（与中间的间距）放进它的内容开头；
        - 下一块不到四分之一页高：标题与它包成一个 KeepTogether；
        - 下一块很长（一大段结论、长表、分栏清单）：不整组挪页，只要求标题下面至少还有 40 mm。
        「完整盘面」这类部分标题的换页高度也在这里按「标题 + 下面第一块正文」现量（_part_room）。"""
        for index, flowable in enumerate(story):
            if getattr(flowable, "_horosa_part_break", False):
                flowable.height = _part_room(story[index + 1:])
        out: list[Any] = []
        index = 0
        while index < len(story):
            flowable = story[index]
            if not getattr(flowable, "keepWithNext", 0) or isinstance(flowable, Spacer):
                out.append(flowable)
                index += 1
                continue
            group = [flowable]
            nxt = index + 1
            while nxt < len(story) and isinstance(story[nxt], Spacer) and not isinstance(story[nxt], CondPageBreak):
                group.append(story[nxt])
                nxt += 1
            for member in group:
                member.keepWithNext = 0
            following = story[nxt] if nxt < len(story) else None
            if isinstance(following, KeepTogether):
                following._content[0:0] = group
                index = nxt
            elif following is not None and not isinstance(following, CondPageBreak) and _height(following) <= frame_height * 0.25:
                if getattr(following, "keepWithNext", 0):  # 连着的小标题：留给下一轮与它自己的下一块分组
                    out.extend(group)
                    index = nxt
                    continue
                out.append(KeepTogether([*group, following]))
                index = nxt + 1
            else:
                out.append(CondPageBreak(40 * mm))
                out.extend(group)
                index = nxt
        return out

    def _height(flowable: Any) -> float:
        """一块的自然高度；KeepTogether 量里面的内容（它自己的 wrap 恒报「无限高」）；量不了当作一整页。"""
        try:
            if isinstance(flowable, KeepTogether):
                return sum(_height(item) for item in flowable._content)
            _, height = flowable.wrap(content_width, frame_height)
            extra = flowable.getSpaceBefore() + flowable.getSpaceAfter() if hasattr(flowable, "getSpaceBefore") else 0
            return float(height) + float(extra)
        except Exception:  # noqa: BLE001 - 量不了：按一整页算（最坏是多换一次页）
            return frame_height

    def _part_room(following: list[Any]) -> float:
        """部分标题要接着排需要的高度：标题与间距 + 后面的小标题 + 第一块正文（比一页还高 → 当作要一整页）。"""
        need = 0.0
        for flowable in following:
            if isinstance(flowable, CondPageBreak):
                continue
            need += _height(flowable)
            if not isinstance(flowable, Spacer) and getattr(flowable, "_horosa_toc", None) is None:
                break  # 第一块正文量完了
        return min(max(need, frame_height * 0.4), frame_height)

    def _spill(flowable: Any) -> list[Any]:
        out: list[Any] = []
        cells = getattr(flowable, "_cellvalues", None)
        content = getattr(flowable, "_content", None)
        if cells is not None:
            for row in cells:
                for cell in row:
                    for leaf in cell if isinstance(cell, (list, tuple)) else [cell]:
                        if isinstance(leaf, str):
                            if leaf.strip():
                                out.append(Paragraph(_esc(leaf), base))
                        elif isinstance(leaf, Flowable):
                            out.extend(_spill(leaf) if hasattr(leaf, "_cellvalues") else [leaf])
        elif isinstance(content, list):
            for leaf in content:
                out.extend(_spill(leaf) if hasattr(leaf, "_cellvalues") or hasattr(leaf, "_content") else [leaf])
        elif hasattr(flowable, "rows"):  # Panels：一行一段
            out.extend(Paragraph(inline(" ".join(str(c) for c in row)), base) for row in flowable.rows)
        return out

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
            dest_labels[key] = f"跳到「{text}」"
            flowable._horosa_toc = (level, text, key)
            return flowable

        def add_heading(text: str, style: ParagraphStyle = heading, *, level: int = 0, anchor: str = "") -> None:
            # 章节标题：左侧色条 + 细底线，不再整块铺底色（满篇浅绿框太重，层级反而看不出来）。
            # anchor = 盘面段号（E3）：AI 正文里的 [E3] 链到这里。
            if anchor:
                dest_labels[anchor] = f"跳到盘面段「{text}」"
            block = Table(
                [[Paragraph((f'<a name="{anchor}"/>' if anchor else "") + _esc(text), section_styles[min(level, 1)])]],
                colWidths=[content_width],
                style=TableStyle(
                    [
                        ("LINEBEFORE", (0, 0), (0, -1), 3.2 if level == 0 else 2.4, green),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.6, line),
                        ("LEFTPADDING", (0, 0), (-1, -1), 9),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                ),
            )
            if len(text) > _LONG_HEADING_CHARS:  # 一页都放不下的「标题」（调用方给的超长章名）：不进标题条，按标题字号的段落排
                block = Paragraph((f'<a name="{anchor}"/>' if anchor else "") + _esc(text), section_styles[min(level, 1)])
            story.append(CondPageBreak(60 * mm if level == 0 else 40 * mm))  # 标题不落在页底孤零零一行
            story.append(Spacer(1, 10))
            # 标题和它下面的第一块排在同一页（评审 R-10：标题后面是整张不拆的表时，表挪到下一页、标题留在页底）
            story.append(keep_with_next(mark(block, level, text)))
            story.append(keep_with_next(Spacer(1, 6)))

        def keep_with_next(flowable: Any) -> Any:
            flowable.keepWithNext = 1
            return flowable

        def add_part(text: str, *, new_page: bool = True) -> None:
            # 「完整盘面」「AI 解读」原则上另起一页；但上一页只印了寥寥几行（所问 + 一句结论）时就接着排，不留一页大半空白
            # （评审 R-17：解读报告第 3 页只有两行）。「附录」通常只有几行，够地方就接着排。
            if new_page:
                # 高度在 settle_keep_with_next 里按「部分标题 + 它下面第一块正文」现量：放得下才接着排，放不下就换页
                # （只看剩余比例时，部分标题留在页上、下面的盘图挪去下一页，又是半页空白）。
                part_break = CondPageBreak(frame_height * 0.62)
                part_break._horosa_part_break = True
                story.append(part_break)
            else:
                story.append(CondPageBreak(70 * mm))
            story.append(Spacer(1, 12))
            block = Table(
                [[Paragraph(_esc(text), part_style)]],
                colWidths=[content_width],
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), dark),
                    ("LINEBELOW", (0, 0), (-1, -1), 2, amber),
                    ("LEFTPADDING", (0, 0), (-1, -1), 14),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
                ]),
            )
            story.append(mark(block, 0, text))
            story.append(Spacer(1, 6))

        table_cell = ParagraphStyle("HorosaTableCell", parent=base, fontSize=8.8, leading=12.4, spaceAfter=0)
        table_head = ParagraphStyle("HorosaTableHead", parent=table_cell, fontName=bold_font_name, textColor=green)
        list_cell = ParagraphStyle("HorosaListCell", parent=table_cell, fontSize=8.8, leading=12.4)

        def table_style_for(data_rows: int, *, header: bool = True, compact: bool = False) -> list[Any]:
            pad = 2 if compact else 3
            style = [
                ("GRID", (0, 0), (-1, -1), 0.4, line),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), pad),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
            ]
            first = 1 if header else 0
            if header:
                style.append(("BACKGROUND", (0, 0), (-1, 0), pale))
            style += [("BACKGROUND", (0, r), (-1, r), stripe) for r in range(first + 1, first + data_rows, 2)]
            return style

        def panel_table(header: list[str] | None, rows: list[list[str]], per_panel: int, panels: int,
                        widths: list[float]) -> Any:
            # 一张「k 栏并排」的表：第 p 栏放 rows[p*n:(p+1)*n]，栏间空一窄列。先左栏到底、再右栏，读序不乱。
            gap = 4 * mm
            cols = len(widths)
            data: list[list[Any]] = []
            used_panels = -(-len(rows) // per_panel) if per_panel else 0
            if header:
                head_row: list[Any] = []
                for p in range(panels):
                    head_row += [Paragraph(inline(h), table_head) if p < max(used_panels, 1) else "" for h in header]
                    head_row += [""] if p < panels - 1 else []
                data.append(head_row)
            for r in range(per_panel):
                row_cells: list[Any] = []
                for p in range(panels):
                    index = p * per_panel + r
                    cells = rows[index] if index < len(rows) else [""] * cols
                    style = table_cell if header else list_cell
                    row_cells += [Paragraph(inline(cells[c] if c < len(cells) else ""), style) for c in range(cols)]
                    row_cells += [""] if p < panels - 1 else []
                data.append(row_cells)
            col_widths: list[float] = []
            for p in range(panels):
                col_widths += widths + ([gap] if p < panels - 1 else [])
            used = -(-len(rows) // per_panel) if per_panel else 0  # 行数少时最后一栏可能一行都没有：不给它印表头与边框
            style = []
            first = 1 if header else 0
            for p in range(used):
                c0 = p * (cols + 1)
                c1 = c0 + cols - 1
                if header:
                    style += [("BACKGROUND", (c0, 0), (c1, 0), pale), ("GRID", (c0, 0), (c1, -1), 0.4, line)]
                else:
                    style += [("LINEBELOW", (c0, 0), (c1, -1), 0.3, line)]
                style += [("BACKGROUND", (c0, r), (c1, r), stripe) for r in range(first + 1, first + per_panel, 2)]
            style += [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 1.6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
            ]
            return data_table(data, colWidths=col_widths, style=TableStyle(style), hAlign="LEFT",
                                      header_rows=1 if header else 0)

        class Panels(Flowable):
            """长清单 / 窄长表分栏排：每到一页按剩余高度现算这一屏每栏放几行，放不下的留给下一屏。

            reportlab 的 Table 跨页只会竖着断，k 栏并排的表一断读序就乱（左栏续到下一页、右栏却在上一页）；
            这里先量再切，每一屏都是「左栏读完读右栏」。
            """

            def __init__(self, header: list[str] | None, rows: list[list[str]], panels: int, widths: list[float]) -> None:
                super().__init__()
                self.header, self.rows, self.panels, self.widths = header, rows, panels, widths
                self._table: Any = None

            def _build(self, rows: list[list[str]]) -> Any:
                per_panel = -(-len(rows) // self.panels)
                return panel_table(self.header, rows, per_panel, self.panels, self.widths)

            def _screen_cap(self, avail_height: float) -> int:
                # 一屏每栏最多放得下几行：每行至少 _PANEL_MIN_ROW_HEIGHT 高。只拿这么多行去量——此前每一页都把剩下的全部行
                # 建成表再量（二分里还要建十几次），8000 行的清单渲染 70 多秒（评审 C-17，按页数平方增长）。
                return max(1, int(avail_height // _PANEL_MIN_ROW_HEIGHT) + 1)

            def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
                # 剩下的行比一屏放得下的上限还多：只建上限那么多行，量出的高度已经超过可用高度，排版器随后调 split。
                cap = self._screen_cap(max(avail_height, 1.0)) * self.panels
                self._table = self._build(self.rows if len(self.rows) <= cap else self.rows[:cap])
                self.width, self.height = self._table.wrap(avail_width, avail_height)
                return self.width, self.height

            def split(self, avail_width: float, avail_height: float) -> list[Any]:
                low, high, best = 1, min(-(-len(self.rows) // self.panels), self._screen_cap(avail_height)), 0
                while low <= high:  # 二分：这一屏每栏最多放几行
                    mid = (low + high) // 2
                    _, height = self._build(self.rows[: mid * self.panels]).wrap(avail_width, avail_height)
                    if height <= avail_height:
                        best, low = mid, mid + 1
                    else:
                        high = mid - 1
                if best < 4:
                    return []  # 剩下的地方连四行都放不下：整体挪到下一页
                cut = best * self.panels
                if cut >= len(self.rows):
                    return [self._build(self.rows)]
                return [self._build(self.rows[:cut]), Panels(self.header, self.rows[cut:], self.panels, self.widths)]

            def draw(self) -> None:
                self._table.drawOn(self.canv, 0, 0)

        def add_data_table(header: list[str], rows: list[list[str]]) -> None:
            story.extend(data_table_flowables(header, rows))

        def data_table_flowables(header: list[str], rows: list[list[str]]) -> list[Any]:
            # Markdown 管道表 → PDF 真表格：按内容分配列宽、表头底纹 + repeatRows 跨页重复表头 + 隔行浅底。
            # 格子是 _MdCell（调用方 Markdown 表）时印它自己的行内标记，量宽仍按纯文字。
            header, rows = _drop_empty_columns(header, rows)
            transposed = _transpose_wide_table(header, rows)
            was_transposed = transposed[0] is not header
            header, rows = transposed
            cols = max(1, len(header))
            col_max = [
                max([_visual_width(_plain(header[c]))] + [_visual_width(_plain(row[c])) if c < len(row) else 0 for row in rows])
                for c in range(cols)
            ]
            panels = _panel_count(col_max, budget=96) if cols <= 4 and len(rows) >= 16 else 1
            if panels > 1:
                # 窄长表（小运 / 流年 / 宫位表…）：一栏只占半页宽，拖好几页——并排成两三栏。
                panel_width = (content_width - 4 * mm * (panels - 1)) / panels
                widths = _column_widths(header, rows, panel_width, 9 * mm)
                return [Panels(header, rows, panels, widths), Spacer(1, 6)]
            data = [[Paragraph(inline(h), table_head) for h in header]]
            for row in rows:
                data.append([Paragraph(inline(row[idx] if idx < len(row) else ""), table_cell) for idx in range(cols)])
            # 短值的窄表（五行力量：木 / 7.7%）不拉满整行：按内容定宽、靠左，省得两列各占半页空着。
            natural = sum(w * 4.6 + 14 for w in col_max)
            table_width = content_width if was_transposed or natural > content_width * 0.6 else max(natural * 1.25, content_width * 0.4)
            # 格子里有长文（一格上千字）：允许从行内断开续到下一页（splitInRow），否则一格比一页高就整份 LayoutError、
            # 退成 TXT（评审 R-03）。只对这种表开：普通表的行照旧整行挪页，不在行中间断。
            tall = any(len(_plain(cell)) > _LONG_CELL_CHARS for row in rows for cell in row)
            table = data_table(
                data,
                header_rows=1,
                colWidths=(_label_first_widths(header, rows, content_width) if was_transposed
                           else _column_widths(header, rows, table_width, min(12 * mm, table_width / cols * 0.6))),
                repeatRows=1,
                style=TableStyle(table_style_for(len(rows))),
                hAlign="LEFT",
                splitInRow=1 if tall else 0,
            )
            # 十几行以内的表整张不拆（拆了常剩一两行孤零零在下一页顶上，如大运第 10 步）。
            return [KeepTogether([table]) if len(rows) <= 14 and not tall else table, Spacer(1, 6)]

        def add_kv_grid(pairs: list[tuple[str, str]]) -> None:
            # 值是一大段的（上千字）不进对照表：键成一行粗体、值按正文段落排，可以跨页（评审 R-03：一格比一页高 → LayoutError →
            # 整份退成 TXT）。其余照旧成表；顺序不变。
            run: list[tuple[str, str]] = []
            for key, value in pairs:
                if len(value) <= _LONG_CELL_CHARS:
                    run.append((key, value))
                    continue
                if run:
                    add_kv_table(run)
                    run = []
                story.append(keep_with_next(Paragraph(_esc(key), kv_label)))
                story.append(Paragraph(inline(value), base))
            if run:
                add_kv_table(run)

        def add_kv_table(pairs: list[tuple[str, str]]) -> None:
            # 连续的「键：值」行（起盘信息、命宫、节气…）排成两列对照表：键一列对齐，值不再被行距拉散。
            # 键列固定 30mm（同一报告里各段对齐），键特别长才放宽，封顶 44mm。
            label_width = min(max(max(_visual_width(k) for k, _ in pairs) * 1.75 * mm + 8 * mm, 30 * mm), 44 * mm)
            data = [[Paragraph(_esc(k), kv_label), Paragraph(inline(v), kv_value)] for k, v in pairs]
            story.append(
                data_table(  # 键列是行表头（TH Scope=Row）
                    data,
                    header_rows=0,
                    header_cols=1,
                    colWidths=[label_width, content_width - label_width],
                    style=TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.3, line),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 2.6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
                    ]),
                    hAlign="LEFT",
                )
            )
            story.append(Spacer(1, 5))

        def add_listing(lines: list[str]) -> None:
            # 一长串互不相干的短行（中点树、星体逐条、神数条文…）：一行一段要拖几十页，分两三栏排。
            widths = [max(_visual_width(_plain(text)) for text in lines)]
            panels = _panel_count(widths, budget=100)
            panel_width = (content_width - 4 * mm * (panels - 1)) / panels
            story.append(Panels(None, [[text] for text in lines], panels, [panel_width]))
            story.append(Spacer(1, 6))

        def add_text(text: str) -> None:
            pending_kv: list[tuple[str, str]] = []
            pending_lines: list[str] = []

            def flush() -> None:
                if pending_kv:  # 单独一行的「键：值」也排成对照表：同一份报告里键值只有一种样子
                    add_kv_grid(pending_kv)
                pending_kv.clear()
                if len(pending_lines) >= _LISTING_MIN_LINES and _panel_count(
                        [max(_visual_width(_plain(text)) for text in pending_lines)], budget=100) > 1:
                    add_listing(list(pending_lines))
                else:
                    for line_text in pending_lines:
                        story.append(Paragraph(inline(line_text), base))
                pending_lines.clear()

            for kind, marker, body in _md_lines(text):
                labelled = _LABEL_LINE_RE.match(body) if kind == "text" else None
                if labelled and _is_time_colon(labelled.group(1), labelled.group(3)):
                    labelled = None  # 「2028-04-06 09:33:00 周四」的冒号是时刻，不是键值分隔
                if labelled and "<" not in labelled.group(1):
                    if pending_lines:
                        flush()
                    pending_kv.append((labelled.group(1).strip(), labelled.group(3).strip()))
                    continue
                if kind == "text":
                    if pending_kv:
                        flush()
                    pending_lines.append(body)
                    continue
                flush()
                if kind == "blank":
                    story.append(Spacer(1, 3))
                elif kind == "rule":
                    story.append(tagging.ArtifactHR(width="100%", thickness=0.5, color=line, spaceBefore=4, spaceAfter=4))
                elif kind == "heading":
                    # 段内小标题：进 PDF 书签（第三级），不进目录（目录只到两级，保证一页放得下）。
                    sub = Paragraph(inline(body), inner_heading)
                    sub._horosa_outline = (2, _plain(body))
                    story.append(keep_with_next(sub))
                elif kind in {"bullet", "ordered"}:
                    story.append(Paragraph(inline(body), bullet_style, bulletText=marker))
                elif kind == "quote":
                    story.append(Paragraph(inline(body), quote_style))
            flush()

        def add_body(text: str) -> None:
            for kind, payload in _split_markdown_blocks(text):
                if kind == "table":
                    add_data_table(payload["header"], payload["rows"])
                else:
                    add_text(payload)

        def md_flowables(blocks: list[Any], indent: float = 0.0, quote: bool = False, depth: int = 0, toc: bool = False) -> list[Any]:
            """调用方 Markdown 的块树 → flowable（reports/markdown.py；DOCX 画同一棵树）。不做键值对照表、不改数字。"""
            from horosa_skill.reports import markdown as md

            body_style = md_style("HorosaMd", base, indent, quote)
            out: list[Any] = []
            for block in blocks:
                if isinstance(block, md.Paragraph):
                    # 一段里换行很多（AI 一行一条写了几千行）：每 _LINES_PER_FLOWABLE 行一个段落对象。reportlab 拆段时把剩下的
                    # 全部行重新断一遍，一个几千行的段落按页数平方变慢（评审 C-17：8000 行 72 秒）；分组后每次只重断一组。
                    groups = _line_groups(block.spans, _LINES_PER_FLOWABLE)
                    for index, group in enumerate(groups):
                        style = body_style if index == len(groups) - 1 else md_style("HorosaMdTight", base, indent, quote, tight=True)
                        out.append(Paragraph(_md_spans_markup(group, cite_anchors), style))
                elif isinstance(block, md.Heading):
                    sub = Paragraph(_md_spans_markup(block.spans, cite_anchors), md_style("HorosaMdHeading", inner_heading, indent, quote))
                    if toc and block.level <= 2 and not indent and not quote:
                        # 解读正文自己的一、二级标题进目录（第二级）：读者翻解读报告要找的就是这些（评审 R-17）
                        mark(sub, 1, md.plain(block.spans))
                    else:
                        sub._horosa_outline = (2, md.plain(block.spans))  # 更细的小标题：书签第三级，不进目录
                    out.append(keep_with_next(sub))
                elif isinstance(block, md.ListBlock):
                    item_style = md_style("HorosaMdItem", bullet_style, indent + 14, quote, bullet_at=indent + 3)
                    for number, item in enumerate(block.items, start=block.start):
                        marker = f"{number}." if block.ordered else ("•" if depth == 0 else "◦")
                        rest = item
                        if item and isinstance(item[0], md.Paragraph):
                            out.append(Paragraph(_md_spans_markup(item[0].spans, cite_anchors), item_style, bulletText=marker))
                            rest = item[1:]
                        else:
                            out.append(Paragraph("", item_style, bulletText=marker))
                        out.extend(md_flowables(rest, indent + 14, quote, depth + 1))
                elif isinstance(block, md.Quote):
                    out.extend(md_flowables(block.children, indent + 12, True, depth))
                elif isinstance(block, md.Code):
                    out.append(Paragraph(_code_markup(block.text), md_style("HorosaMdCode", code_style, indent + 6, quote)))
                elif isinstance(block, md.Table):
                    header = [_MdCell.of(cell) for cell in block.header]
                    rows = [[_MdCell.of(cell) for cell in row] for row in block.rows]
                    out.extend(data_table_flowables(header, rows))
                elif isinstance(block, md.Rule):
                    out.append(tagging.ArtifactHR(width="100%", thickness=0.5, color=line, spaceBefore=4, spaceAfter=4))
            return out

        md_styles: dict[tuple[str, float, bool, float | None], Any] = {}

        def md_style(name: str, parent: Any, indent: float, quote: bool, bullet_at: float | None = None, tight: bool = False) -> Any:
            key = (name, indent, quote, bullet_at)
            if key not in md_styles:
                extra: dict[str, Any] = {"leftIndent": parent.leftIndent + indent if bullet_at is None else indent}
                if tight:
                    extra["spaceAfter"] = 0
                if bullet_at is not None:
                    extra["bulletIndent"] = bullet_at
                if quote:
                    extra.update(textColor=muted, fontSize=min(parent.fontSize, 9.6))
                md_styles[key] = ParagraphStyle(f"{name}{len(md_styles)}", parent=parent, **extra)
            return md_styles[key]

        def add_markdown(text: str, *, toc: bool = False) -> None:
            from horosa_skill.reports import markdown as md

            story.extend(md_flowables(md.parse(text), toc=toc))

        def add_note_card(title_text: str, body_text: str, *, accent: Any = green) -> None:
            # 卡片 = 标题 + 正文各块，每块包一层 CardPiece 画框与左侧色条：块与块之间、一段长文内部都能照常跨页
            # （评审 C-17 / R-03：此前整张卡是一张表，一段 2000 字的结论比一页高 → LayoutError → 整份退成 TXT；
            # 拆成一行一块的表又让每页重排剩下的全部行，几千行时按页数平方变慢）。正文里的表格排在卡片下方（DOCX 同样处理）。
            from horosa_skill.reports import markdown as md

            blocks = md.parse(body_text)
            tables = [block for block in blocks if isinstance(block, md.Table)]
            inner = md_flowables([block for block in blocks if not isinstance(block, md.Table)]) or [Paragraph(_esc(t("无")), base)]
            title = Paragraph(_esc(title_text), ParagraphStyle("CardTitle", parent=subheading, textColor=accent))
            pieces = [title, *inner]
            for index, flowable in enumerate(pieces):
                piece = CardPiece(flowable, accent, first=index == 0, last=index == len(pieces) - 1)
                story.append(keep_with_next(piece) if index == 0 else piece)
            for table in tables:
                story.extend(md_flowables([table]))
            story.append(Spacer(1, 9))

        ai_report = document.get("ai_report") if isinstance(document.get("ai_report"), dict) else {}
        display_question = str(document.get("intro_text") or "") or _display_question(document, ai_report, t)
        chart_style = document.get("style") == "chart"
        human_sections = [s for s in _human_sections(document) if isinstance(s, dict)]
        basis_sections = [s for s in human_sections if s.get("group") == "basis"]

        # ── 封面：独占一页。深色题签 + 基本信息卡 +（排盘报告）报告说明 + 生成时间；不印页脚。
        cover = Table(
            [
                [Paragraph(_esc(str(document.get("cover_label") or t("专业咨询报告"))), cover_label_style)],
                [Paragraph(_esc(str(document.get("cover_title") or document.get("title") or t("结构化咨询报告"))), cover_title)],
                [Paragraph(_esc(str(document.get("cover_meta") or t("结构化解读 · 行动建议 · 风险提示"))), cover_meta)],
            ],
            colWidths=[content_width],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), dark),
                    ("LINEBELOW", (0, -1), (-1, -1), 3, amber),
                    ("LEFTPADDING", (0, 0), (-1, -1), 22),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 22),
                    ("TOPPADDING", (0, 0), (0, 0), 46),
                    ("BOTTOMPADDING", (0, 0), (0, 0), 10),
                    ("TOPPADDING", (0, 1), (0, 1), 12),
                    ("BOTTOMPADDING", (0, 1), (0, 1), 14),
                    ("TOPPADDING", (0, 2), (0, 2), 6),
                    ("BOTTOMPADDING", (0, 2), (0, 2), 42),
                ]
            ),
        )
        story.append(Spacer(1, 18 * mm))
        story.append(cover)
        story.append(Spacer(1, 16))
        for section in basis_sections:
            pairs = [
                (row[0], row[1])
                for kind, block in _split_markdown_blocks(str(section.get("body") or ""))
                if kind == "table"
                for row in block["rows"]
                if len(row) >= 2 and str(row[1]).strip()
            ]
            if not pairs:
                continue
            story.append(Paragraph(_esc(str(section.get("title") or t("基本信息"))), cover_section_style))
            story.append(cover_info_grid(pairs))
            story.append(Spacer(1, 12))
        if chart_style and display_question.strip():
            story.append(
                Table(
                    [[Paragraph(inline(paragraph), cover_note_style)] for paragraph in _paragraphs(display_question)],
                    colWidths=[content_width],
                    splitInRow=1,
                    style=TableStyle([
                        ("LINEBEFORE", (0, 0), (0, -1), 2.4, amber),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                    ]),
                )
            )
        generated = _local_date(document.get("generated_at"))
        if generated:
            story.append(Spacer(1, 14))
            story.append(Paragraph(_esc(t("生成于") + f" {generated} · " + t("星阙 Horosa")), cover_footnote_style))
        if font_note:
            story.append(Spacer(1, 8))
            story.append(Paragraph(_esc(font_note), cover_footnote_style))

        if len(human_sections) >= 4:
            # 条目少的目录直接排在封面下方，不单独占一页（十来行的目录独占一页、封面又空三分之二，两页都浪费）。
            if len(human_sections) + (2 if figures else 1) <= 12:
                story.append(Spacer(1, 16))
                story.append(Paragraph(_esc(t("目录")), cover_section_style))
            else:
                story.append(PageBreak())
                story.append(Paragraph(_esc(t("目录")), toc_title_style))
            toc_at = len(story)  # 目录表等全部标题登记完再插进来
        if not chart_style:
            story.append(PageBreak())
            add_heading(str(document.get("intro_heading") or t("解读目标")))
            add_markdown(display_question)
        # 摘要照 STORM 的 lead：能单独读、句句带段号；细读放在盘面之后，读者先看到「算出了什么」再看「怎么解」。
        accents = {"green": green, "blue": colors.HexColor("#2563eb"), "amber": amber}
        for block in body_blocks(document, t):
            if block.kind == "card":
                add_note_card(block.text, block.body, accent=accents[block.role])
            elif block.kind == "heading":
                add_heading(block.text, level=_PDF_HEADING_LEVELS[block.role])
            elif block.kind == "body":  # 调用方写的（解读正文 / 摘要）：Markdown 块树
                add_markdown(block.body, toc=True)
            elif block.kind == "part":
                # 「完整盘面」另起一页；「附录」通常只有几行，够地方就接着排。
                add_part(block.text, new_page=block.role != "appendix")
            elif block.kind == "note":
                story.append(Paragraph(_esc(block.text), muted_note))
                story.append(Spacer(1, 4))
            elif block.kind == "figures":
                story.extend(figure_flowables())
            elif block.kind == "section":
                if block.role == "appendix":
                    story.append(CondPageBreak(70 * mm))  # 附录小表（技法依据 ~10 行）不被拆成「标题 + 两行」留在页底
                add_heading(f"{block.cite} · {block.text}" if block.cite else block.text, level=1 if block.in_part else 0, anchor=block.cite)
                add_body(block.body)
            elif block.kind == "orphan_figures":  # 没有盘面段（极少数工具）：盘图跟在封面后
                add_part(block.text)
                add_heading(t("盘图"), level=1)
                story.extend(figure_flowables())
        if toc_at is not None:
            story.insert(toc_at, toc_table(entries, pages))
        story = settle_keep_with_next(story)
        # 最后一道：任何一块在整页上都排不下又拆不开时，只把这一块拆成段落照排，其余版面不受影响（评审 R-03 的兜底；
        # 此前一块 LayoutError 就整份退成 TXT）。
        return [Guarded(flowable) if isinstance(flowable, (RLTable, KeepTogether, Panels)) else flowable for flowable in story]

    title_text =str(document.get("title") or t("咨询报告"))

    page_total = {"value": 0}
    # 页脚：报告名 + 起盘时刻（几份报告打印混在一起时能分开）；没有时刻的技法只印报告名。
    footer_text = "　·　".join(part for part in (title_text, str(document.get("footer_meta") or "")) if part)

    @tagging.artifact
    def on_cover(canvas: Any, doc: Any) -> None:
        canvas.showOutline()  # 打开就显示书签栏
        canvas.saveState()
        canvas.setFillColor(paper)
        canvas.rect(0, 0, page_width, page_height, fill=1, stroke=0)
        canvas.restoreState()

    @tagging.artifact
    def on_page(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFillColor(paper)
        canvas.rect(0, 0, page_width, page_height, fill=1, stroke=0)
        canvas.setStrokeColor(line)
        canvas.setLineWidth(0.4)
        canvas.line(left_margin, 13.5 * mm, page_width - right_margin, 13.5 * mm)
        canvas.setFont(font_name, 7.5)
        canvas.setFillColor(muted)
        canvas.drawString(left_margin, 10 * mm, footer_text)
        total = page_total["value"]
        canvas.drawRightString(page_width - right_margin, 10 * mm,
                               t(f"第 {doc.page} 页 / 共 {total} 页") if total else t(f"第 {doc.page} 页"))
        canvas.restoreState()

    class _Doc(SimpleDocTemplate):
        def afterFlowable(self, flowable: Any) -> None:  # reportlab 回调名
            outline = getattr(flowable, "_horosa_outline", None)
            if outline is not None:
                level, text = outline
                level = min(level, getattr(self, "_horosa_level", 0) + 1)  # 书签层级不能跳级（reportlab 会抛错）
                key = f"o{id(flowable)}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=level, closed=True)
                return
            entry = getattr(flowable, "_horosa_toc", None)
            if entry is None:
                return
            level, text, key = entry
            self._horosa_level = level
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
        lang="zh-CN" if script == SIMPLIFIED else "zh-HK" if script == TRADITIONAL_HK else "zh-TW",
        author="Horosa 星阙",
        subject=str(document.get("footer_meta") or document.get("cover_meta") or ""),
        creator="Horosa 星阙",
    )
    # 「共 M 页」与目录页码：先排一遍拿到总页数和各标题页码，再排一遍写进页脚 / 目录。
    # 不用「延迟出页」的 canvas：那会把每个书签都钉在第 1 页。
    pages: dict[str, int] = {}
    pages_seen: dict[str, int] = {}
    # 链接的替代文字（读屏念「跳到哪」）：目录项与 [E3] 引用的去处；字体退回不嵌入的 CID 字体时不声称 PDF/UA。
    dest_labels: dict[str, str] = {}
    ua_claim = isinstance(pdfmetrics.getFont(font_name), TTFont)

    class canvas_class(tagging.TaggingCanvas):  # noqa: N801 - reportlab 的 canvasmaker
        pass

    canvas_class.dest_labels = dest_labels
    canvas_class.ua_claim = ua_claim
    canvas_class.initial_font = font_name
    for _ in range(3):
        pages_seen.clear()
        doc._horosa_level = 0
        doc.build(compose(pages), onFirstPage=on_cover, onLaterPages=on_page, canvasmaker=canvas_class)
        stable = pages_seen == pages and page_total["value"] == doc.page
        pages = dict(pages_seen)
        page_total["value"] = doc.page
        if stable:
            break
    return [font_note] if font_note else []


# DOCX 的中文字体名候选：(本机探测的文件, 简体名, 繁体名, 香港名)。DOCX 不嵌入字体，名字写给**打开文档的那台电脑**看；
# 本机有哪款就写哪款（异机打开时 Word 再按字体表里的备用名 / 字符集找替身，见 _DOCX_FONT_FALLBACK）。
_DOCX_FONT_CANDIDATES: tuple[tuple[tuple[str, ...], str, str, str], ...] = (
    (("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyh.ttf"), "Microsoft YaHei", "", ""),
    (("C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/msjh.ttf"), "", "Microsoft JhengHei", "Microsoft JhengHei"),
    (("/System/Library/Fonts/PingFang.ttc",), "PingFang SC", "PingFang TC", "PingFang HK"),
    (("/System/Library/Fonts/Supplemental/Songti.ttc",), "Songti SC", "Songti TC", "Songti TC"),
    (("/System/Library/Fonts/Supplemental/Arial Unicode.ttf",), "Arial Unicode MS", "Arial Unicode MS", "Arial Unicode MS"),
    (("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"),
     "Noto Sans CJK SC", "Noto Sans CJK TC", "Noto Sans CJK HK"),
)
# 本机一款中文字体都没有（CI 的 ubuntu、精简的 Linux 服务器）：写一款读者那边最可能有的中文字体。
# 🔴 此前退成 "Arial"——w:eastAsia 指向一款没有中文字形的字体，而 Arial 本来就在模板字体表里，字体替身信息
# （altName / charset 86 / 88）也就加不进去：异机打开只能乱猜（v0.50.0-dev，CI Linux 红、本机绿）。
_DOCX_PORTABLE_FONT = {"sc": "Microsoft YaHei", "tc": "Microsoft JhengHei", "hk": "Microsoft JhengHei"}


def _docx_font_name(script: str = SIMPLIFIED) -> str:
    """正文与 w:eastAsia 用的中文字体名。繁体用繁体字形的字体（简体字体也能显示多数繁体字，但字形是大陆规范，台港读者一眼看出不对）。"""
    column = 0 if script == SIMPLIFIED else 2 if script == TRADITIONAL_HK else 1
    for paths, *names in _DOCX_FONT_CANDIDATES:
        name = names[column]
        if name and any(Path(path).exists() for path in paths):
            return name
    return _DOCX_PORTABLE_FONT["sc" if script == SIMPLIFIED else "hk" if script == TRADITIONAL_HK else "tc"]


_INTERNAL_KEYWORD_RE = re.compile(r"^(?:[a-z0-9]+(?:[_\-][a-z0-9]+)*|[0-9a-f]{16,})$")
# 字体在打开文档的电脑上没有时，Word 按字体表里的备用名 / 字符集 / 字族找替身（不同平台各有一款中文字体）。
# charset：86 = GB2312（简体），88 = Big5（繁体），按十六进制写。
_DOCX_FONT_FALLBACK = {
    "sc": {"altName": "Microsoft YaHei", "serif_altName": "SimSun", "charset": "86"},
    "tc": {"altName": "Microsoft JhengHei", "serif_altName": "PMingLiU", "charset": "88"},
}


def _docx_lang(script: str) -> str:
    return "zh-CN" if script == SIMPLIFIED else "zh-HK" if script == TRADITIONAL_HK else "zh-TW"


def _docx_apply_language_and_font_fallback(doc: Any, script: str, font_name: str, qn: Any) -> None:
    """文档语言与字体替身（评审 R-14）：模板的 w:lang 是 en-US（东亚文字也标 en-US），拼写检查与断行都按英文来；
    正文字体是出报告那台电脑上的字体名（PingFang SC / 宋体…），换平台打开没有这款字体时 Word 只能乱猜。"""
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.oxml import OxmlElement

    lang = _docx_lang(script)
    for lang_element in doc.styles.element.iter(qn("w:lang")):
        lang_element.set(qn("w:val"), lang)
        lang_element.set(qn("w:eastAsia"), lang)
    defaults = doc.styles.element.find(qn("w:docDefaults"))
    rpr = defaults.find(qn("w:rPrDefault")).find(qn("w:rPr")) if defaults is not None else None
    if rpr is not None and rpr.find(qn("w:lang")) is None:
        element = OxmlElement("w:lang")
        element.set(qn("w:val"), lang)
        element.set(qn("w:eastAsia"), lang)
        rpr.append(element)
    kind = _DOCX_FONT_FALLBACK["sc" if script == SIMPLIFIED else "tc"]
    serif = any(word in font_name for word in ("Song", "Ming", "Sim", "宋", "明"))
    entry = (
        f'<w:font w:name="{html.escape(font_name, quote=True)}">'
        f'<w:altName w:val="{kind["serif_altName"] if serif else kind["altName"]}"/>'
        f'<w:charset w:val="{kind["charset"]}"/><w:family w:val="{"roman" if serif else "swiss"}"/>'
        '<w:pitch w:val="variable"/></w:font>'
    )
    try:
        table = doc.part.part_related_by(RT.FONT_TABLE)
    except KeyError:
        return
    blob = table.blob.decode("utf-8")
    if f'w:name="{html.escape(font_name, quote=True)}"' not in blob and "</w:fonts>" in blob:
        table._blob = blob.replace("</w:fonts>", entry + "</w:fonts>").encode("utf-8")


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
# 补字链：主字体缺的字按顺序找第一款画得了的。扩展 B 古籍字（Windows SimSun-ExtB / MingLiU-ExtB）在前；
# 其后是符号与拉丁扩展——埃及历转写 ḥ ṭ、梵文转写 ṇ ṃ、卦符 ䷀ ☰、行星符 ♃ ☿、✓ ✗ ⚠ ⟷ ▶（v0.43 评审：110 份里
# 十几份印成方块）。macOS 用 Arial Unicode + Apple Symbols，Windows 用 Segoe UI Symbol + Arial，Linux 用 DejaVu。
_SYMBOL_FALLBACKS = (
    "C:/Windows/Fonts/seguisym.ttf", "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/System/Library/Fonts/Apple Symbols.ttf",
    "/System/Library/Fonts/Geneva.ttf",  # ȧ ᵢ ₋₂（埃及历 / 巴比伦转写；前两款都缺）
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
)
_PDF_GLYPH_FALLBACK_CANDIDATES: dict[str, tuple[str, ...]] = {
    "sc": ("C:/Windows/Fonts/simsunb.ttf", "C:/Windows/Fonts/mingliub.ttc", *_SYMBOL_FALLBACKS),
    "tc": ("C:/Windows/Fonts/mingliub.ttc", "C:/Windows/Fonts/simsunb.ttf", *_SYMBOL_FALLBACKS),
}
_GLYPH_FALLBACK_FROM = 0x80  # ASCII（含标记 <b>、&amp;、href 键）永远不会被包
_SYMBOL_PLACEHOLDERS = ("▸", "•", "·")  # 画不了的符号换成第一个画得出的


def _wrap_missing_glyphs(markup: str, primary: Any, fallback: Any, fallback_font: str) -> str:
    """单款补字字体的写法（保留给调用方 / 测试）：等价于只有一环的补字链。"""
    return _wrap_missing_glyphs_chain(markup, primary, [(fallback_font, fallback)])


def _wrap_missing_glyphs_chain(markup: str, primary: Any, chain: list[tuple[str, Any]]) -> str:
    """把主字体画不了的字按补字链找第一款画得了的字体，同字体的相邻字连成段包进 `<font name=…>`；

    补不了的文字、主字体有的字原样留着（正文文字从不替换）；**符号**（So / emoji 区）主字体与补字链都画不了时换成 ▸
    （v0.50.0，评审 R-02：按真实 cmap 判，不按码位段猜）。标签内不动。primary / 链上的码位集合都只需支持 `in`。
    """
    out: list[str] = []
    run: list[str] = []
    run_font: str | None = None
    in_tag = False

    def flush() -> None:
        nonlocal run, run_font
        if run:
            out.append(f'<font name="{run_font}">{"".join(run)}</font>')
        run, run_font = [], None

    def drawable(code: int) -> bool:
        return code in primary or any(code in covered for _, covered in chain)

    placeholder = next((c for c in _SYMBOL_PLACEHOLDERS if drawable(ord(c))), "")
    for ch in markup:
        code = ord(ch)
        if in_tag or ch == "<":
            flush()
            out.append(ch)
            in_tag = ch != ">"
            continue
        if code >= _GLYPH_FALLBACK_FROM and not drawable(code) and _is_symbol(ch):
            ch = placeholder
            if not ch:
                continue
            code = ord(ch)
        font = None
        if code >= _GLYPH_FALLBACK_FROM and code not in primary:
            font = next((name for name, covered in chain if code in covered), None)
        if font is None:
            flush()
            out.append(ch)
            continue
        if font != run_font:
            flush()
            run_font = font
        run.append(ch)
    flush()
    return "".join(out)


class _AllOf:
    """几份覆盖都含这个码位（`in`）。"""

    __slots__ = ("parts",)

    def __init__(self, *parts: Any) -> None:
        self.parts = parts

    def __contains__(self, code: object) -> bool:
        return all(code in part for part in self.parts)


class _EncodableCoverage:
    """CID 字体的「能画哪些字」：码位能用该字符集合对应的国标编码编出来（`code in coverage`，与 TTF 的 cmap 集合同用法）。"""

    __slots__ = ("codec",)

    def __init__(self, codec: str) -> None:
        self.codec = codec

    def __contains__(self, code: object) -> bool:
        try:
            chr(code).encode(self.codec)  # type: ignore[arg-type]
        except (TypeError, ValueError):  # UnicodeEncodeError 是 ValueError；代理码位 / 非整数同样「画不了」
            return False
        return True


# reportlab 自带的两款 CID 字体（本机没有中文 TrueType 时的回退，CI 的 ubuntu 就是）不嵌入、也不带 cmap，
# face 上没有 charToGlyph。它们的字符集合 Adobe-GB1 / Adobe-CNS1 是照 GBK（GB 18030）/ 大五码 + HKSCS 收字的：
# 用对应编码编得出来 = 阅读器有字形。此前这一支直接「不补字」，✓ ☯ 🎉 这类符号原样进 PDF，印成方块或乱码（v0.50.0-dev，CI Linux 红）。
_CID_FONT_CHARSETS = {"STSong-Light": "gbk", "MSung-Light": "big5hkscs"}


def _font_coverage(font: Any) -> Any | None:
    """字体画得出的码位（支持 `in`）：TrueType 用真实 cmap；reportlab 自带 CID 字体按字符集合；都不是返回 None。"""
    glyphs = getattr(getattr(font, "face", None), "charToGlyph", None)
    if glyphs is not None:
        return set(glyphs)
    codec = _CID_FONT_CHARSETS.get(str(getattr(font, "fontName", "")))
    return _EncodableCoverage(codec) if codec else None


def _pdf_glyph_fallback(pdfmetrics: Any, TTFont: Any, font_name: str, bold_font_name: str, script: str) -> Any:
    """返回给 Paragraph 标记补字的函数；量不出主字体能画哪些字时返回原样函数。"""
    identity = lambda markup: markup  # noqa: E731
    try:
        primary = _font_coverage(pdfmetrics.getFont(font_name))
        bold = primary if bold_font_name == font_name else _font_coverage(pdfmetrics.getFont(bold_font_name))
    except Exception:  # noqa: BLE001 - 字体没注册：不补字（探针，原样即答案）
        return identity
    if primary is None or bold is None:
        return identity
    kind = "sc" if script == SIMPLIFIED else "tc"
    # 常规体与粗体都有的字才不需要补（CID 回退时两者是同一款）
    drawable = primary if bold is primary else (primary & bold if isinstance(primary, set) and isinstance(bold, set)
                                                else _AllOf(primary, bold))
    chain: list[tuple[str, Any]] = []
    for index, path in enumerate(_PDF_GLYPH_FALLBACK_CANDIDATES[kind]):
        font = _load_ttf(TTFont, f"HorosaGlyph{kind.upper()}{index}", path, None)
        if font is None:
            continue
        pdfmetrics.registerFont(font)
        # `<b>` 里的补字段同样落在补字字体上（它没有粗体），否则 reportlab 找不到该族的粗体映射直接抛错。
        pdfmetrics.registerFontFamily(font.fontName, normal=font.fontName, bold=font.fontName,
                                      italic=font.fontName, boldItalic=font.fontName)
        chain.append((font.fontName, set(font.face.charToGlyph)))
    # 没有补字字体时也要过一遍：画不了的符号照样换掉（文字仍原样，逐字节不变）
    return lambda markup: _wrap_missing_glyphs_chain(markup, drawable, chain)


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


# 字体集的「字面名 → 序号」表。枚举要把 .ttc 里每个子字体都解析一遍（Songti.ttc 约 0.3 秒），一份 PDF 要查好几次，
# 长命的 MCP server 每份报告都重来，占了渲染约七成的时间。键带 mtime / 大小：系统更新字体后序号可能变，文件变了就重新枚举。
_FACE_NAMES: dict[tuple[str, int, int], dict[str, int]] = {}


def _face_names(TTFont: Any, path: str) -> dict[str, int]:
    stat = os.stat(path)
    key = (path, stat.st_mtime_ns, stat.st_size)
    cached = _FACE_NAMES.get(key)
    if cached is not None:
        return cached
    found: dict[str, int] = {}
    for index in range(32):
        try:
            face = TTFont(f"HorosaProbe{index}", path, subfontIndex=index).face
        except Exception:  # noqa: BLE001 - 越界或 reportlab 读不了这个子字体：探测到此为止（探针，None 即答案）
            break
        name = face.name.decode("utf-8", "replace") if isinstance(face.name, bytes) else str(face.name)
        found.setdefault(name, index)
    if found:  # 一个子字体都读不出来时不记：可能只是这一次读失败
        _FACE_NAMES[key] = found
    return found


def _face_index(TTFont: Any, path: str, names: tuple[str, ...] | None) -> int | None:
    """TTC 里按字面名（按偏好顺序）找子字体序号；names 为 None 取 0；找不到返回 None。"""
    if names is None or not path.lower().endswith(".ttc"):
        return 0
    found = _face_names(TTFont, path)
    return next((found[n] for n in names if n in found), None)


# 解析好的 TTFont，按注册名 + 文件 mtime / 大小缓存。一份 PDF 要载常规体、粗体和补字字体，Windows 上这几款都是
# 十几 MB 的雅黑 / 宋体 ExtB，每款解析约 0.15 秒；同名再注册 reportlab 本来就丢掉新对象，所以重解析纯属白费
# （v0.48.0 Windows 原生复验：110 份 PDF 解析了 728 次、106 秒）。
_TTF_CACHE: dict[tuple[Any, str, int, int], Any] = {}


def _load_ttf(TTFont: Any, prefix: str, path: str, names: tuple[str, ...] | None) -> Any | None:
    """注册名 = 前缀 + 字体文件身份（路径 + 子字体序号）的短摘要。reportlab 的 registerFont 对 TrueType **只认第一次**：
    同名再注册静默忽略、getFont 仍回旧字体。此前注册名只看候选表序号（HorosaSC0…），候选表一变（测试钉字体、
    或 Windows 上序号 0 恰是真字体）就拿回别的文件——v0.48.0 windows-smoke 因此两条红。"""
    if not Path(path).exists():
        return None
    index = _face_index(TTFont, path, names)
    if index is None:
        return None
    import hashlib

    font_name = f"{prefix}-{hashlib.sha1(f'{Path(path).resolve()}|{index}'.encode('utf-8')).hexdigest()[:10]}"
    stat = os.stat(path)
    key = (TTFont, font_name, stat.st_mtime_ns, stat.st_size)  # 带上类：测试会换成替身类
    cached = _TTF_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        font = TTFont(font_name, path, subfontIndex=index) if path.lower().endswith(".ttc") else TTFont(font_name, path)
    except Exception:  # noqa: BLE001 - 这一款载不了就换下一款（探针，None 即答案）
        return None
    font.horosa_source = (path, index)  # DOCX 的星盘位图（figures.drawing_to_png）用同一款字体文件
    _TTF_CACHE[key] = font
    return font


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


def _display_question(document: dict[str, Any], ai_report: dict[str, Any], t: Any = str) -> str:
    raw_question = str(document.get("user_question") or "").strip()
    if raw_question:
        return raw_question
    focus = str(ai_report.get("analysis_focus") or "").strip()
    return focus or t("整体综合解盘")
