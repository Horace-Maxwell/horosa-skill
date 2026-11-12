"""PDF 版面在极端内容下照样排得出、时间随内容线性增长（v0.50.0，评审 R-03 / R-10 / C-17）。

此前：一段 2000 字的结论（卡片是一张表，一格比一页高）、一行 2000 字的「标签：值」、一格 3000 字的表格、2000 字的章名，
任何一块排不下就 LayoutError，整份退成 TXT；几千行的解读按页数平方变慢（8000 行 72 秒）；标题后面跟整张不拆的表时，
表挪到下一页、标题孤零零留在页底。
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from reportlab.platypus.tables import Table

from horosa_skill.reports import renderers
from horosa_skill.service.api.reports import AI_REPORT_MAX_CHARS

PARA = "这是一段命理分析文字，" * 27 + "。"


def _document(sections: list[tuple[str, str]] = (), **ai: object) -> dict:
    return {
        "title": "版面测试",
        "sections": [
            {"id": f"s{index}", "title": title, "body": body, "human_visible": True, "group": "chart", "cite_id": f"E{index}"}
            for index, (title, body) in enumerate(sections, start=1)
        ],
        "ai_report": dict(ai),
    }


def _pdf(tmp_path: Path, document: dict, name: str = "x.pdf") -> dict:
    return renderers.render_report(document, output_path=tmp_path / name, format_name="pdf")


@pytest.mark.parametrize(
    ("label", "document"),
    [
        ("结论卡里 2400 字一段", _document(human_direct_answer=PARA * 8)),
        ("建议卡里 2400 字一段", _document(human_direct_answer="短", human_recommendations=[PARA * 8])),
        ("引擎段里 2100 字的键值行", _document([("起盘信息", "标签：" + "很长的值" * 525)])),
        ("引擎表格一格 3000 字", _document([("表", "| a | b |\n|---|---|\n| x | " + "格" * 3000 + " |")])),
        ("2000 字的章名", _document([("题" * 2000, "正文")])),
        ("调用方表格一格 3000 字", _document(human_executive_summary="| a | b |\n|---|---|\n| x | " + "格" * 3000 + " |")),
    ],
)
def test_one_oversized_block_never_degrades_the_whole_pdf(tmp_path: Path, label: str, document: dict) -> None:
    renderers.LAYOUT_SPILLS.clear()
    rendered = _pdf(tmp_path, document)
    assert rendered["format"] == "pdf" and "degraded_from" not in rendered, (label, rendered.get("degrade_reason"))
    assert renderers.LAYOUT_SPILLS == [], "正常排出来，不靠兜底"


def test_an_unlayoutable_block_degrades_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """兜底：一块表在整页上排不下又拆不开时（这里用一张关了拆分的超高表模拟），只有这一块摊成段落，PDF 照出。"""
    original = Table.split

    def refuse(self, availWidth, availHeight):  # noqa: N803 - reportlab 签名
        if any("不可拆" in str(getattr(leaf, "text", leaf)) for row in self._cellvalues for cell in row
               for leaf in (cell if isinstance(cell, (list, tuple)) else [cell])):
            return []
        return original(self, availWidth, availHeight)

    monkeypatch.setattr(Table, "split", refuse)
    renderers.LAYOUT_SPILLS.clear()
    wide = "| 不可拆 | b | c | d | e |\n|---|---|---|---|---|\n" + "| 行 | 值 | 值 | 值 | 值 |\n" * 80  # 五列：不走分栏
    rendered = _pdf(tmp_path, _document([("表", wide)]))
    assert rendered["format"] == "pdf" and "degraded_from" not in rendered, rendered.get("degrade_reason")
    assert renderers.LAYOUT_SPILLS, "那一块靠兜底摊开"


def _render_seconds(tmp_path: Path, lines: int, name: str) -> float:
    document = _document([("清单", "\n".join(f"第{n}条" for n in range(lines)))], human_executive_summary="命理\n" * lines)
    start = time.perf_counter()
    rendered = _pdf(tmp_path, document, name)
    assert rendered["format"] == "pdf"
    return time.perf_counter() - start


def test_render_time_grows_linearly_with_the_number_of_lines(tmp_path: Path) -> None:
    """引擎的长清单（分栏 Panels）与调用方一段几千行的文字：旧代码每页把剩下的全部行重排一次，四倍的行数约十五倍的时间。"""
    _render_seconds(tmp_path, 200, "warm.pdf")  # 字体解析等一次性开销
    small = _render_seconds(tmp_path, 1000, "small.pdf")
    large = _render_seconds(tmp_path, 4000, "large.pdf")
    assert large < max(small, 0.2) * 8, (small, large)


def test_headings_keep_with_their_first_block(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """标题后面是整张不拆的小表：不论前文把标题推到页上哪里，标题与表都在同一页。旧代码在某个填充量下标题落页底、表去了下一页。"""
    from reportlab.pdfgen.canvas import Canvas

    pages: dict[str, int] = {}
    original_outline = Canvas.addOutlineEntry
    original_draw = Table.drawOn

    def outline(canvas, title, key, level=0, closed=None):
        pages.setdefault(title, canvas.getPageNumber())
        return original_outline(canvas, title, key, level=level, closed=closed)

    def draw(self, canvas, x, y, _sW=0):  # noqa: N803 - reportlab 签名
        if any("表头甲" in str(getattr(leaf, "text", "")) for row in self._cellvalues for cell in row
               for leaf in (cell if isinstance(cell, (list, tuple)) else [cell])):
            pages.setdefault("表", canvas.getPageNumber())
        return original_draw(self, canvas, x, y, _sW)

    monkeypatch.setattr(Canvas, "addOutlineEntry", outline)
    monkeypatch.setattr(Table, "drawOn", draw)
    table = "| 表头甲 | 表头乙 |\n|---|---|\n" + "".join(f"| 行{n} | 值{n} |\n" for n in range(12))
    moved = 0
    for filler in range(4, 40, 2):  # 空行隔开的前文段落（不成分栏清单）：把标题推到页上各处，必有几次落在页底
        pages.clear()
        document = _document([("前文", "\n\n".join(f"前文第{n}段，" + "字" * 30 for n in range(filler))), ("小表", table)])
        assert _pdf(tmp_path, document, f"k{filler}.pdf")["format"] == "pdf"
        heading = next(page for title, page in pages.items() if title.endswith("小表"))
        assert heading == pages["表"], (filler, pages)
        moved += heading > next(page for title, page in pages.items() if title.endswith("前文"))
    assert moved, "扫描范围要覆盖「标题被挤到下一页」的情形，否则这条测不到东西"


def test_the_callers_reading_has_a_documented_size_limit(tmp_path: Path) -> None:
    from test_user_knowledge_and_chart_report import _chart_run, _service

    from horosa_skill.errors import ToolValidationError, recovery_for

    service = _service(tmp_path)
    run_id = _chart_run(service).memory_ref.run_id
    with pytest.raises(ToolValidationError) as caught:
        service.report_render({"run_id": run_id, "format": "pdf",
                               "ai_report": {"answer_text": "字" * AI_REPORT_MAX_CHARS, "recommendations": ["多一点"]}})
    error = caught.value
    assert error.code == "report.ai_report_too_large" and error.details["limit"] == AI_REPORT_MAX_CHARS
    assert error.details["largest_fields"][0]["field"] == "ai_report.answer_text" and error.details["run_id"] == run_id
    assert service.show_memory({"run_id": run_id})["result"].get("ai_answer_text") in (None, "")
    assert recovery_for("report.ai_report_too_large", None)["agent_recovery"]["kind"] == "input"
    with pytest.raises(ToolValidationError) as from_tool:
        service.report_from_tool({"tool_name": "chart", "payload": {}, "format": "pdf", "ai_answer_text": "字" * (AI_REPORT_MAX_CHARS + 1)})
    assert from_tool.value.code == "report.ai_report_too_large"


def spy_pages_total(spy) -> int:
    return max(page for _title, _level, page in spy.outline)


def test_reading_headings_are_in_the_toc_and_short_pages_are_not_left_mostly_empty(tmp_path: Path, monkeypatch) -> None:
    """评审 R-17：解读正文自己的一、二级标题不在目录里（目录只有「完整解盘正文」一行）；所问 + 一句结论之后强制换页，
    解读报告第 3 页只印两行。"""
    from test_user_knowledge_and_chart_report import _chart_run, _PdfSpy, _service

    service = _service(tmp_path)
    run_id = _chart_run(service).memory_ref.run_id
    spy = _PdfSpy(monkeypatch)
    reading = "## 一、依据\n\n日主甲木。\n\n### 细节\n\n略。\n\n## 二、建议\n\n宜守。"
    service.report_render({"run_id": run_id, "format": "pdf", "ai_answer_text": reading})
    toc = [entry for entry, _page in spy.toc()]
    assert "一、依据" in toc and "二、建议" in toc and "细节" not in toc
    pages = {title: page for title, _level, page in spy.outline}
    # 部分标题、「盘图」小标题与盘图在同一页：不孤零零留在页底，也不因为后面跟着整张不拆的块就被强制挤到下一页
    # （reportlab 的 keepWithNext 遇到 KeepTogether 恒判「放不下」，一份 12 页的报告因此被撑到 20 多页）
    assert pages["完整盘面"] == pages["盘图"], pages
    assert spy_pages_total(spy) <= 14, pages

    spy = _PdfSpy(monkeypatch)
    document = {**_document([("起盘信息", "日期：2028-04-06")], human_direct_answer="今年宜守。"), "user_question": "今年如何？"}
    renderers.render_report(document, output_path=tmp_path / "short.pdf", format_name="pdf")
    pages = {title: page for title, _level, page in spy.outline}
    # 盘面第一块很短：接着排在所问与结论下面，不另起一页留下大半页空白
    assert pages["完整盘面"] == pages["解读目标"], pages
