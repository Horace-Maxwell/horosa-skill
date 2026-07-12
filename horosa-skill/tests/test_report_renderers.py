"""报告渲染世界一流面回归锚：MD 真表格 / 导航大纲 / TOC / 元数据 / 页脚页码 / 降级。"""
from __future__ import annotations

import zipfile
from pathlib import Path

from horosa_skill.reports.renderers import _split_markdown_blocks, render_report


def _doc() -> dict:
    return {
        "title": "测试八字报告",
        "source": {"technique_label": "八字", "tool_name": "bazi_birth"},
        # 长句混入 keywords（真实 builder 会塞问题/答案全文）——core property 255 限不许炸。
        "search_index": {"keywords": ["八字", "大运", "这是一段超过二十四个字符的长句关键词用来复现文档属性写入超限导致渲染降级的缺陷" * 3]},
        "plain_text": "备用纯文本",
        "ai_report": {
            "executive_summary": "总览：命主日元戊土。",
            "answer_text": "分析：\n| 十神 | 强度 |\n| --- | --- |\n| 正官 | 3.2 |\n结论平稳。",
            "analysis_sections": [{"title": "五行力量", "body": "| 五行 | 分值 |\n| --- | --- |\n| 木 | 12 |"}],
        },
        # 渲染契约：builder 产出的 section 均带 human_visible 标志，缺失视为机器段不渲染。
        "sections": [{"title": "流年概览", "human_visible": True, "body": "| 年份 | 干支 |\n| --- | --- |\n| 2026 | 丙午 |"}],
    }


def test_split_markdown_blocks_extracts_pipe_tables() -> None:
    blocks = _split_markdown_blocks("头\n| a | b |\n| --- | --- |\n| 1 | 2 |\n| 3 |\n尾")
    kinds = [k for k, _ in blocks]
    assert kinds == ["text", "table", "text"]
    table = blocks[1][1]
    assert table["header"] == ["a", "b"]
    # 列数对齐表头：短行补空成矩形。
    assert table["rows"] == [["1", "2"], ["3", ""]]


def test_docx_renders_real_tables_toc_metadata_footer(tmp_path: Path) -> None:
    out = tmp_path / "r.docx"
    result = render_report(_doc(), output_path=out, format_name="docx")
    assert result["format"] == "docx" and result["file_size"] > 0
    with zipfile.ZipFile(out) as z:
        xml = z.read("word/document.xml").decode("utf-8")
        core = z.read("docProps/core.xml").decode("utf-8")
        settings = z.read("word/settings.xml").decode("utf-8")
        footers = [n for n in z.namelist() if "footer" in n]
        footer = z.read(footers[0]).decode("utf-8") if footers else ""
    # MD 管道表 → 真 w:tbl（跨页重复表头标记）且单元格文本落位。
    assert "tblHeader" in xml and "正官" in xml and "丙午" in xml
    # 目录域 + 打开自动更新；标题挂大纲级别（导航窗格可跳转）。
    assert "TOC" in xml and "updateFields" in settings and "outlineLvl" in xml
    # 文档元数据与页脚页码域。
    assert "测试八字报告" in core
    assert "PAGE" in footer and "NUMPAGES" in footer


def test_pdf_renders_with_tables(tmp_path: Path) -> None:
    out = tmp_path / "r.pdf"
    result = render_report(_doc(), output_path=out, format_name="pdf")
    assert result["format"] == "pdf"
    assert out.read_bytes()[:5] == b"%PDF-"


def test_render_failure_degrades_to_txt(tmp_path: Path, monkeypatch) -> None:
    # 渲染器异常 → 自动改存 TXT（UTF-8 全文），结果标注降级来源与原因，绝不静默丢内容。
    import horosa_skill.reports.renderers as renderers

    def boom(document, output_path):  # noqa: ARG001
        raise RuntimeError("字体炸了")

    monkeypatch.setattr(renderers, "_render_pdf", boom)
    out = tmp_path / "r.pdf"
    result = render_report(_doc(), output_path=out, format_name="pdf")
    assert result["format"] == "txt"
    assert result["degraded_from"] == "pdf" and "字体炸了" in result["degrade_reason"]
    txt = Path(result["path"])
    assert txt.suffix == ".txt" and "备用纯文本" in txt.read_text(encoding="utf-8")
