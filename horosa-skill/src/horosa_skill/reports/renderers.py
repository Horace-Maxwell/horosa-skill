from __future__ import annotations

import hashlib
import html
import json
import re
import zipfile
from pathlib import Path
from typing import Any


def render_report(document: dict[str, Any], *, output_path: Path, format_name: str) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = format_name.lower()
    if normalized == "json":
        output_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    elif normalized == "docx":
        _render_docx(document, output_path)
    elif normalized == "pdf":
        _render_pdf(document, output_path)
    else:
        raise ValueError("format must be one of: json, docx, pdf")
    payload = output_path.read_bytes()
    return {
        "path": str(output_path),
        "format": normalized,
        "file_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _render_docx(document: dict[str, Any], output_path: Path) -> None:
    try:
        from docx import Document
    except ModuleNotFoundError:
        _render_docx_fallback(document, output_path)
        return

    doc = Document()
    doc.add_heading(str(document.get("title") or "Horosa Skill Report"), level=0)
    doc.add_paragraph(f"生成时间: {document.get('generated_at', '')}")
    doc.add_paragraph(f"Run ID: {document.get('run', {}).get('id', '')}")
    doc.add_paragraph(f"工具: {document.get('source', {}).get('tool_name', '')}")
    doc.add_paragraph(f"技法: {document.get('source', {}).get('technique') or ''}")

    _docx_heading(doc, "用户问题", 1)
    doc.add_paragraph(str(document.get("user_question") or "无"))

    ai_report = document.get("ai_report") if isinstance(document.get("ai_report"), dict) else {}
    if ai_report.get("analysis_focus") or ai_report.get("direct_answer"):
        _docx_heading(doc, "针对性回答", 1)
        if ai_report.get("analysis_focus"):
            doc.add_paragraph(f"分析焦点：{ai_report.get('analysis_focus')}")
        if ai_report.get("direct_answer"):
            doc.add_paragraph(f"直接回答：{ai_report.get('direct_answer')}")
    if ai_report.get("executive_summary") or ai_report.get("answer_text"):
        _docx_heading(doc, "AI 结论摘要", 1)
        doc.add_paragraph(str(ai_report.get("executive_summary") or ai_report.get("answer_text") or ""))
    if ai_report.get("analysis_sections"):
        _docx_heading(doc, "AI 分节分析", 1)
        for section in ai_report.get("analysis_sections", []):
            if isinstance(section, dict):
                _docx_heading(doc, str(section.get("title") or "分析"), 2)
                if section.get("relevance_to_question"):
                    doc.add_paragraph(f"与问题的关系：{section.get('relevance_to_question')}")
                doc.add_paragraph(str(section.get("body") or section.get("content") or ""))
                for line in section.get("evidence_lines", []) if isinstance(section.get("evidence_lines"), list) else []:
                    doc.add_paragraph(f"证据：{line}", style="List Bullet")
            else:
                doc.add_paragraph(str(section))
    if ai_report.get("evidence"):
        _docx_heading(doc, "证据引用", 1)
        for item in ai_report.get("evidence", []):
            doc.add_paragraph(str(item), style="List Bullet")
    if ai_report.get("recommendations"):
        _docx_heading(doc, "建议", 1)
        for item in ai_report.get("recommendations", []):
            doc.add_paragraph(str(item), style="List Bullet")
    if ai_report.get("limitations"):
        _docx_heading(doc, "限制与注意事项", 1)
        for item in ai_report.get("limitations", []):
            doc.add_paragraph(str(item), style="List Bullet")

    for section in document.get("sections", []):
        if not isinstance(section, dict):
            continue
        _docx_heading(doc, str(section.get("title") or "章节"), 1)
        body = str(section.get("body") or "")
        for paragraph in _paragraphs(body):
            doc.add_paragraph(paragraph)

    _docx_heading(doc, "Provenance", 1)
    for key, value in (document.get("provenance") or {}).items():
        doc.add_paragraph(f"{key}: {value}")
    doc.save(str(output_path))


def _render_pdf(document: dict[str, Any], output_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    except ModuleNotFoundError:
        _render_pdf_fallback(document, output_path)
        return

    font_name = "STSong-Light"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))
    except Exception:
        font_name = "Helvetica"

    styles = getSampleStyleSheet()
    base = ParagraphStyle("HorosaBody", parent=styles["BodyText"], fontName=font_name, fontSize=10, leading=15)
    title = ParagraphStyle("HorosaTitle", parent=styles["Title"], fontName=font_name, fontSize=20, leading=26)
    heading = ParagraphStyle("HorosaHeading", parent=styles["Heading1"], fontName=font_name, fontSize=14, leading=20, spaceBefore=12)
    subheading = ParagraphStyle("HorosaSubHeading", parent=styles["Heading2"], fontName=font_name, fontSize=12, leading=17, spaceBefore=8)
    story: list[Any] = []

    def add_heading(text: str, style: ParagraphStyle = heading) -> None:
        story.append(Paragraph(_esc(text), style))
        story.append(Spacer(1, 6))

    def add_body(text: str) -> None:
        for paragraph in _paragraphs(text):
            story.append(Paragraph(_esc(paragraph), base))
            story.append(Spacer(1, 4))

    story.append(Paragraph(_esc(str(document.get("title") or "Horosa Skill Report")), title))
    story.append(Spacer(1, 14))
    add_body(f"生成时间: {document.get('generated_at', '')}")
    add_body(f"Run ID: {document.get('run', {}).get('id', '')}")
    add_body(f"工具: {document.get('source', {}).get('tool_name', '')}")
    add_body(f"技法: {document.get('source', {}).get('technique') or ''}")
    story.append(PageBreak())

    add_heading("用户问题")
    add_body(str(document.get("user_question") or "无"))
    ai_report = document.get("ai_report") if isinstance(document.get("ai_report"), dict) else {}
    if ai_report.get("analysis_focus") or ai_report.get("direct_answer"):
        add_heading("针对性回答")
        add_body(
            "\n".join(
                item
                for item in [
                    f"分析焦点：{ai_report.get('analysis_focus')}" if ai_report.get("analysis_focus") else "",
                    f"直接回答：{ai_report.get('direct_answer')}" if ai_report.get("direct_answer") else "",
                ]
                if item
            )
        )
    if ai_report.get("executive_summary") or ai_report.get("answer_text"):
        add_heading("AI 结论摘要")
        add_body(str(ai_report.get("executive_summary") or ai_report.get("answer_text") or ""))
    if ai_report.get("analysis_sections"):
        add_heading("AI 分节分析")
        for section in ai_report.get("analysis_sections", []):
            if isinstance(section, dict):
                add_heading(str(section.get("title") or "分析"), subheading)
                body_parts = []
                if section.get("relevance_to_question"):
                    body_parts.append(f"与问题的关系：{section.get('relevance_to_question')}")
                body_parts.append(str(section.get("body") or section.get("content") or ""))
                if isinstance(section.get("evidence_lines"), list) and section.get("evidence_lines"):
                    body_parts.append("证据：" + "；".join(str(item) for item in section.get("evidence_lines", [])))
                add_body("\n".join(body_parts))
            else:
                add_body(str(section))
    if ai_report.get("evidence"):
        add_heading("证据引用")
        add_body("\n".join(f"- {item}" for item in ai_report.get("evidence", [])))
    if ai_report.get("recommendations"):
        add_heading("建议")
        add_body("\n".join(f"- {item}" for item in ai_report.get("recommendations", [])))
    if ai_report.get("limitations"):
        add_heading("限制与注意事项")
        add_body("\n".join(f"- {item}" for item in ai_report.get("limitations", [])))

    for section in document.get("sections", []):
        if not isinstance(section, dict):
            continue
        add_heading(str(section.get("title") or "章节"))
        add_body(str(section.get("body") or ""))

    add_heading("Provenance")
    add_body("\n".join(f"- {key}: {value}" for key, value in (document.get("provenance") or {}).items()))
    SimpleDocTemplate(str(output_path), pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36).build(story)


def _docx_heading(doc: Any, text: str, level: int) -> None:
    doc.add_heading(text, level=level)


def _paragraphs(text: str) -> list[str]:
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [item.strip() for item in raw.split("\n") if item.strip()]
    return paragraphs or ["无"]


def _esc(value: str) -> str:
    return html.escape(str(value)).replace("\n", "<br/>")


def _render_docx_fallback(document: dict[str, Any], output_path: Path) -> None:
    paragraphs: list[tuple[str, str]] = [("Title", str(document.get("title") or "Horosa Skill Report"))]
    paragraphs.extend(
        [
            ("Normal", f"生成时间: {document.get('generated_at', '')}"),
            ("Normal", f"Run ID: {document.get('run', {}).get('id', '')}"),
            ("Normal", f"工具: {document.get('source', {}).get('tool_name', '')}"),
            ("Normal", f"技法: {document.get('source', {}).get('technique') or ''}"),
            ("Heading1", "用户问题"),
            ("Normal", str(document.get("user_question") or "无")),
        ]
    )
    ai_report = document.get("ai_report") if isinstance(document.get("ai_report"), dict) else {}
    if ai_report.get("executive_summary") or ai_report.get("answer_text"):
        paragraphs.append(("Heading1", "AI 结论摘要"))
        paragraphs.append(("Normal", str(ai_report.get("executive_summary") or ai_report.get("answer_text") or "")))
    if ai_report.get("analysis_focus") or ai_report.get("direct_answer"):
        paragraphs.append(("Heading1", "针对性回答"))
        if ai_report.get("analysis_focus"):
            paragraphs.append(("Normal", f"分析焦点：{ai_report.get('analysis_focus')}"))
        if ai_report.get("direct_answer"):
            paragraphs.append(("Normal", f"直接回答：{ai_report.get('direct_answer')}"))
    for section in document.get("sections", []):
        if isinstance(section, dict):
            paragraphs.append(("Heading1", str(section.get("title") or "章节")))
            paragraphs.extend(("Normal", item) for item in _paragraphs(str(section.get("body") or "")))
    paragraphs.append(("Heading1", "Provenance"))
    for key, value in (document.get("provenance") or {}).items():
        paragraphs.append(("Normal", f"{key}: {value}"))

    document_xml = "\n".join(_docx_paragraph(style, text) for style, text in paragraphs)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _DOCX_CONTENT_TYPES)
        archive.writestr("_rels/.rels", _DOCX_RELS)
        archive.writestr("word/_rels/document.xml.rels", _DOCX_DOCUMENT_RELS)
        archive.writestr("word/styles.xml", _DOCX_STYLES)
        archive.writestr("word/document.xml", f"{_DOCX_DOCUMENT_PREFIX}{document_xml}{_DOCX_DOCUMENT_SUFFIX}")


def _docx_paragraph(style: str, text: str) -> str:
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style != "Normal" else ""
    runs = "".join(f"<w:r><w:t>{html.escape(part)}</w:t></w:r>" for part in str(text).split("\n"))
    return f"<w:p>{style_xml}{runs}</w:p>"


def _render_pdf_fallback(document: dict[str, Any], output_path: Path) -> None:
    lines = [
        str(document.get("title") or "Horosa Skill Report"),
        f"Generated: {document.get('generated_at', '')}",
        f"Run ID: {document.get('run', {}).get('id', '')}",
        f"Tool: {document.get('source', {}).get('tool_name', '')}",
        f"Technique: {document.get('source', {}).get('technique') or ''}",
        f"Question: {document.get('user_question') or 'N/A'}",
    ]
    ai_report = document.get("ai_report") if isinstance(document.get("ai_report"), dict) else {}
    if ai_report.get("executive_summary") or ai_report.get("answer_text"):
        lines.append(f"AI Summary: {ai_report.get('executive_summary') or ai_report.get('answer_text')}")
    for section in document.get("sections", [])[:8]:
        if isinstance(section, dict):
            lines.append(str(section.get("title") or "Section"))
            lines.extend(_paragraphs(str(section.get("body") or ""))[:8])
    ascii_lines = [_pdf_safe(line)[:110] for line in lines[:60]]
    text_stream = "BT /F1 10 Tf 50 790 Td 14 TL " + " T* ".join(f"({_pdf_escape(line)}) Tj" for line in ascii_lines) + " ET"
    stream_bytes = text_stream.encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream_bytes)).encode("ascii") + b" >>\nstream\n" + stream_bytes + b"\nendstream",
    ]
    chunks = [b"%PDF-1.4\n"]
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets:
        chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
    output_path.write_bytes(b"".join(chunks))


def _pdf_safe(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value)).strip()
    return normalized.encode("latin-1", errors="replace").decode("latin-1")


def _pdf_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


_DOCX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""
_DOCX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
_DOCX_DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>"""
_DOCX_DOCUMENT_PREFIX = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>"""
_DOCX_DOCUMENT_SUFFIX = """<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>"""
_DOCX_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
</w:styles>"""
