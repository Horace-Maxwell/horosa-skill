"""DOCX / PDF 的文档属性、语言、字体（v0.50.0，评审 R-14 / R-15 / R-16）。

此前：DOCX 的创建 / 修改时间是 python-docx 模板的 2013-12-23，关键词是检索索引里的「直接回答」「证据绑定」，w:lang 一律
en-US，字体名是出报告那台电脑上的（换平台打开没有替身信息）；PDF 每页开头与表格空格子 setFont 一次不嵌入的 Helvetica、
矢量图开头 setFont 一次 Times-Roman，却照样在元数据里声称 PDF/UA-1；本机没有中文 TrueType 时静默改用不嵌入的 CID 字体。
"""
from __future__ import annotations

import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from test_user_knowledge_and_chart_report import _chart_run, _PdfSpy, _service

from horosa_skill.reports import renderers

_STANDARD_14 = rb"/BaseFont\s*/(Helvetica|Times-Roman|Times-Bold|Courier|Symbol|ZapfDingbats)\b"


@pytest.mark.parametrize("font_host", ["host", "no_cjk_font"], indirect=True)  # 补字链与这里无关：两种现场就够
@pytest.mark.parametrize(("language", "lang"), [("zh-CN", "zh-CN"), ("zh-TW", "zh-TW")])
def test_docx_metadata_language_and_font_fallback(tmp_path: Path, language: str, lang: str, font_host: str) -> None:
    service = _service(tmp_path)
    run_id = _chart_run(service).memory_ref.run_id
    rendered = service.report_render({"run_id": run_id, "format": "docx", "language": language, "ai_answer_text": "今年宜守。"})
    with zipfile.ZipFile(rendered["artifact_path"]) as archive:
        core = archive.read("docProps/core.xml").decode("utf-8")
        styles = archive.read("word/styles.xml").decode("utf-8")
        fonts = archive.read("word/fontTable.xml").decode("utf-8")
    created = re.search(r"<dcterms:created[^>]*>([^<]+)<", core).group(1)
    assert created.startswith(str(datetime.now(timezone.utc).year)) and "2013" not in created
    assert f"<dc:language>{lang}</dc:language>" in core
    keywords = re.search(r"<cp:keywords>([^<]*)<", core).group(1)
    assert "直接回答" not in keywords and "證據綁定" not in keywords and "_" not in keywords
    assert keywords.split(", ")[0] in {"星盘", "星盤"}
    assert set(re.findall(r'<w:lang w:val="([^"]+)" w:eastAsia="([^"]+)"', styles)) == {(lang, lang)}
    font = re.search(r'<w:rFonts [^>]*w:eastAsia="([^"]+)"', styles).group(1)
    # 本机一款中文字体都没有时写读者最可能有的那款，不是没有中文字形的 Arial（此前 CI ubuntu 上就是 Arial，替身信息也加不进去）
    assert font not in {"Arial", "Calibri", "Times New Roman"}, font
    entry = re.search(rf'<w:font w:name="{re.escape(font)}">(.*?)</w:font>', fonts, re.S)
    assert entry and "<w:altName " in entry.group(1)
    assert f'w:charset w:val="{"86" if lang == "zh-CN" else "88"}"' in entry.group(1)


def test_pdf_references_only_embedded_fonts_and_claims_ua_only_then(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run_id = _chart_run(service).memory_ref.run_id
    rendered = service.report_render({"run_id": run_id, "format": "pdf", "style": "chart"})
    data = Path(rendered["artifact_path"]).read_bytes()
    if re.search(rb"/(STSong|MSung)-Light", data):  # 正文走了不嵌入的 CID 字体（补字链的 TrueType 照样嵌入，不能拿 /FontFile2 判）
        pytest.skip("[host] 本机没有中文 TrueType：CID 字体分支见 test_no_embeddable_cjk_font_is_said_out_loud")
    assert not re.search(_STANDARD_14, data), re.findall(_STANDARD_14, data)
    assert b"pdfuaid:part" in data


def test_the_ua_claim_follows_the_fonts_actually_referenced(tmp_path: Path) -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    from horosa_skill.reports import pdf_tagging

    canvas = pdf_tagging.TaggingCanvas(str(tmp_path / "a.pdf"))
    canvas.setFont("Helvetica", 10)  # 只 setFont、一个字都不画也算引用
    assert canvas.fonts_all_embedded() is False
    regular, _bold = renderers._register_pdf_fonts(pdfmetrics, UnicodeCIDFont, TTFont)  # 用报告自己的字体，不另注册
    if not isinstance(pdfmetrics.getFont(regular), TTFont):
        pytest.skip("[host] 本机没有中文 TrueType")

    class Canvas(pdf_tagging.TaggingCanvas):
        initial_font = regular

    clean = Canvas(str(tmp_path / "b.pdf"))
    clean.drawString(10, 10, "字")
    assert clean.fonts_all_embedded() is True


def test_no_embeddable_cjk_font_is_said_out_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(renderers, "_PDF_FONT_CANDIDATES", {"sc": [], "tc": []})
    service = _service(tmp_path)
    run_id = _chart_run(service).memory_ref.run_id
    spy = _PdfSpy(monkeypatch)
    rendered = service.report_render({"run_id": run_id, "format": "pdf", "style": "chart"})
    assert rendered["format"] == "pdf"
    assert any("没有可嵌入的中文字体" in item for item in rendered.get("warnings") or []), rendered.get("warnings")
    assert any("没有可嵌入的中文字体" in line for line in rendered["summary"])
    assert any("没有可嵌入的中文字体" in text for text in spy.texts()), "PDF 封面上也写明"
    assert b"pdfuaid:part" not in Path(rendered["artifact_path"]).read_bytes()
