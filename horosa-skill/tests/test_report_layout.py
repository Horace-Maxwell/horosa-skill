"""DOCX 与 PDF 读同一串版面块：顺序只定义一次，两边不再各写一份。"""

from __future__ import annotations

import ast
from pathlib import Path

from horosa_skill.reports import layout, renderers
from horosa_skill.reports.layout import Block, body_blocks


def _doc(**extra: object) -> dict:
    return {
        "title": "报告",
        "sections": [
            {"id": "b", "group": "basis", "title": "基本信息", "human_visible": True, "body": "| 键 | 值 |\n| --- | --- |\n| 甲 | 1 |"},
            {"id": "c", "group": "chart", "cite_id": "E1", "title": "起盘信息", "human_visible": True, "body": "盘面一"},
            {"id": "a", "group": "appendix", "title": "技法依据", "human_visible": True, "body": "依据"},
            {"id": "report_quality", "title": "机器段", "human_visible": True, "body": "不印"},
        ],
        **extra,
    }


AI = {"direct_answer": "结论", "human_executive_summary": "摘要", "answer_text": "正文", "human_recommendations": ["建议甲"], "human_limitations": ["限制甲"],
      "human_reading_steps": ["一"], "human_consultation_basis": "依据", "human_analysis_sections": [{"title": "分节", "body": "分节正文"}, "裸字符串"]}


def _kinds(blocks: list[Block]) -> list[str]:
    return [f"{b.kind}:{b.role}" if b.role else b.kind for b in blocks]


def test_the_reading_order_is_data_first() -> None:
    """结论摘要 → 完整盘面（盘图在最前）→ AI 解读 → 附录（AGENTS 9.3.1 的报告骨架）。"""
    blocks = body_blocks(_doc(ai_report=AI, figures=[{"kind": "wheel"}]))
    order = [b.text or b.kind for b in blocks if b.kind in {"card", "part", "figures", "section"}]
    assert order == ["核心结论", "完整盘面", "figures", "起盘信息", "AI 解读", "起盘依据", "解盘步骤", "建议", "附录", "技法依据"]


def test_the_ai_reading_closes_the_document_when_there_is_no_appendix() -> None:
    document = _doc(ai_report=AI)
    document["sections"] = document["sections"][:2]
    assert body_blocks(document)[-1] == Block("body", body="- 限制甲")


def test_nothing_of_the_ai_is_printed_when_show_ai_is_false() -> None:
    blocks = body_blocks(_doc(ai_report=AI, show_ai=False))
    assert _kinds(blocks) == ["part:chart", "section:chart", "part:appendix", "section:appendix"]


def test_an_answer_equal_to_the_summary_is_not_printed_twice() -> None:
    blocks = body_blocks(_doc(ai_report={"human_executive_summary": "同一段", "answer_text": "同一段"}))
    assert sum(1 for b in blocks if "同一段" in b.body) == 1
    assert not any(b.kind == "part" and b.role == "ai" for b in blocks)


def test_cite_ids_belong_to_chart_sections_only() -> None:
    document = _doc()
    document["sections"][2]["cite_id"] = "E9"
    sections = [b for b in body_blocks(document) if b.kind == "section"]
    assert [(b.text, b.cite, b.in_part) for b in sections] == [("起盘信息", "E1", True), ("技法依据", "", True)]


def test_figures_with_no_sections_at_all_are_marked_as_orphans() -> None:
    assert _kinds(body_blocks({"sections": [], "figures": [{"kind": "wheel"}]})) == ["orphan_figures"]
    assert body_blocks({"sections": [], "figures": ["not a dict"]}) == []


def test_labels_go_through_the_labeler_and_document_text_does_not() -> None:
    blocks = body_blocks(_doc(ai_report=AI), lambda text: f"<{text}>")
    assert Block("card", "<核心结论>", "结论", role="green") in blocks
    assert any(b.kind == "section" and b.text == "起盘信息" for b in blocks), "文档里的文字调用方已转好，再转一次不幂等"


def test_both_renderers_print_exactly_what_the_blocks_say(tmp_path: Path, monkeypatch) -> None:
    """换掉块序列，两种格式的正文一起变：证明它们读的是同一串，不是各走各的。"""
    marker = [Block("part", "只在块里的部分", role="chart"), Block("heading", "只在块里的标题", role="ai_topic"), Block("body", body="只在块里的正文"),
              Block("section", "只在块里的章节", "章节正文", role="chart", cite="E7", in_part=True), Block("card", "只在块里的卡片", "卡片正文", role="amber"), Block("note", "只在块里的说明")]
    monkeypatch.setattr(renderers, "body_blocks", lambda document, t: marker)
    document = _doc(ai_report=AI)

    renderers.render_report(document, output_path=tmp_path / "r.docx", format_name="docx")
    renderers.render_report(document, output_path=tmp_path / "r.pdf", format_name="pdf")

    from docx import Document

    docx = Document(str(tmp_path / "r.docx"))
    text = "\n".join(cell.text for table in docx.tables for row in table.rows for cell in row.cells) + "\n".join(p.text for p in docx.paragraphs)
    for piece in ("只在块里的部分", "只在块里的标题", "只在块里的正文", "E7 · 只在块里的章节", "章节正文", "只在块里的卡片", "卡片正文", "只在块里的说明"):
        assert piece in text, piece
    assert "分节正文" not in text and "盘面一" not in text, "块之外的内容不许再从别处印进来"
    assert (tmp_path / "r.pdf").read_bytes()[:5] == b"%PDF-"

    # PDF 的正文压在内容流里读不出字：块多三十倍，文件就要明显变大（各走各的骨架时大小不变）。
    monkeypatch.setattr(renderers, "body_blocks", lambda document, t: marker * 30)
    renderers.render_report(document, output_path=tmp_path / "many.pdf", format_name="pdf")
    assert (tmp_path / "many.pdf").stat().st_size > (tmp_path / "r.pdf").stat().st_size * 1.5


def test_no_renderer_walks_the_ai_report_itself() -> None:
    """骨架只有一份：渲染器里再出现这些字段，就是又开始各写各的。"""
    source = Path(renderers.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    walkers = [node.name for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {"_render_docx", "_render_pdf"}]
    assert sorted(walkers) == ["_render_docx", "_render_pdf"]
    for field in ("human_analysis_sections", "human_recommendations", "human_limitations", "_human_ai_list", "_steps_text"):
        assert field not in source, field


def test_the_layout_knows_nothing_about_either_format() -> None:
    source = Path(layout.__file__).read_text(encoding="utf-8")
    imports = {alias.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import) for alias in node.names}
    assert not {"docx", "reportlab"} & imports and "from docx" not in source and "from reportlab" not in source
