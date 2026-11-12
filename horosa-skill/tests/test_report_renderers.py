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

    def boom(document, output_path, *_args):  # noqa: ARG001
        raise RuntimeError("字体炸了")

    monkeypatch.setattr(renderers, "_render_pdf", boom)
    out = tmp_path / "r.pdf"
    result = render_report(_doc(), output_path=out, format_name="pdf")
    assert result["format"] == "txt"
    assert result["degraded_from"] == "pdf" and "字体炸了" in result["degrade_reason"]
    txt = Path(result["path"])
    # 退化的 TXT 是读者那份（与 PDF 同一串块），不是机器版 plain_text（v0.50.0，评审 R-01）
    body = txt.read_text(encoding="utf-8")
    assert txt.suffix == ".txt" and body.startswith("说明：") and "流年概览" in body and "总览：命主日元戊土。" in body
    assert "备用纯文本" not in body


def test_cancellation_during_a_render_propagates_instead_of_degrading(tmp_path, monkeypatch) -> None:
    """v0.41.1：取消 / Ctrl-C 是 BaseException，必须原样抛出并清掉临时文件——此前被当成渲染失败降级成「成功」的 TXT。"""
    import pytest

    from horosa_skill.reports import renderers

    def cancelled(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(renderers, "_render_pdf", cancelled)
    target = tmp_path / "report.pdf"
    with pytest.raises(KeyboardInterrupt):
        renderers.render_report({"plain_text": "x"}, output_path=target, format_name="pdf")
    assert not target.exists() and not target.with_suffix(".txt").exists()
    assert [p.name for p in tmp_path.iterdir()] == [], "temp file must be cleaned up"


def test_a_pdf_without_any_cjk_font_degrades_to_txt_instead_of_tofu(tmp_path, monkeypatch) -> None:
    """v0.41.1：一个中文字体都注册不上时，此前静默用 Helvetica 出一份满页方块的「成功」PDF；现在走既有的 TXT 降级并写明原因。"""
    from pathlib import Path as _Path

    from horosa_skill.reports import renderers

    monkeypatch.setattr(_Path, "exists", lambda self: False)  # no system font file anywhere

    import reportlab.pdfbase.cidfonts as cidfonts

    def no_cid(*_a, **_k):
        raise ValueError("CID resource missing")

    monkeypatch.setattr(cidfonts, "UnicodeCIDFont", no_cid)
    result = renderers.render_report({"plain_text": "中文正文"}, output_path=tmp_path / "r.pdf", format_name="pdf")
    assert result["format"] == "txt" and result["degraded_from"] == "pdf"
    assert "CJK" in result["degrade_reason"]
    assert (tmp_path / "r.txt").read_text(encoding="utf-8").endswith("中文正文\n")  # 没有人读块的极简文档：退回 plain_text


def test_degraded_txt_is_the_readers_document_and_never_overwrites(tmp_path: Path, monkeypatch) -> None:
    """评审 R-01：此前退化的 TXT 是机器版全文（Run ID / Trace ID、质量闸、交付清单、覆盖矩阵、机器建议、产物绝对路径），
    而且直接写在同名 .txt 上，旁边已有的同名文件被盖掉。"""
    from test_user_knowledge_and_chart_report import _chart_run, _service

    from horosa_skill.reports import renderers

    service = _service(tmp_path)
    run = _chart_run(service)
    run_id = run.memory_ref.run_id

    def boom(*_args, **_kwargs):
        raise RuntimeError("排版失败")

    monkeypatch.setattr(renderers, "_render_pdf", boom)
    (tmp_path / "runs").mkdir(exist_ok=True)
    (tmp_path / "runs" / "我的.txt").write_text("别人的文件", encoding="utf-8")
    result = service.report_render({"run_id": run_id, "format": "pdf", "output_path": "我的.pdf",
                                    "ai_answer_text": "## 总体结论\n\n今年宜守，**不宜**扩张。\n\n- 第一条"})
    assert result["format"] == "txt" and result["degraded_from"] == "pdf"
    assert result["degrade_reason"].startswith("PDF 排版时出错，改存为纯文本") and "排版失败" in result["degrade_reason"]
    assert (tmp_path / "runs" / "我的.txt").read_text(encoding="utf-8") == "别人的文件"
    body = Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert Path(result["artifact_path"]).name == "我的-2.txt"
    assert body.startswith("说明：这份报告本应是 PDF")
    for reader in ("核心结论", "今年宜守，不宜扩张。", "- 第一条", "完整盘面", "起盘信息"):
        assert reader in body, reader
    for machine in (run_id, "Run ID", "Trace ID", "交付检查清单", "覆盖矩阵", "AI should fill", str(tmp_path), "**"):
        assert machine not in body, machine
