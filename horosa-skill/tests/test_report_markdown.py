"""调用方 Markdown 的块树：PDF 与 DOCX 画同一棵（v0.50.0，评审 R-07）；核心结论取第一句真话（R-06）。

旧渲染器逐行认 Markdown：`*斜体*`、`~~删除线~~`、`[链接](url)`、`<br>`、代码块、嵌套 / 有序列表原样印成符号；
「Note: …」被排进键值对照表；调用方写的 0.7548645849180389 被改成 0.7549；DOCX 没有真超链接。下面每条断言在旧代码下都红。
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest
from test_user_knowledge_and_chart_report import _chart_run, _flat, _PdfSpy, _service

from horosa_skill.reports import markdown as md

READING = """## 总体结论

**事业**上*稳中有进*，~~不宜冒进~~宜守成。误差 0.7548645849180389 原样保留。见 [星阙官网](https://example.com/a?b=1&c=2) 与 [E1]。<br>这是 br 之后的一行
Note: 这是一句以英文标签开头的话，不是键值行。

1. 第一条
   - 嵌套甲
   - 嵌套乙
2. 第二条

> 引用里的 **粗体**

```python
x = 1  # **不是粗体**
```

| 项目 | 判断 |
|:--|--:|
| 财运 | `平` |

<script>alert(1)</script> 原样印出。
"""


def test_the_parser_builds_one_tree_for_every_construct() -> None:
    blocks = md.parse(READING)
    kinds = [type(block).__name__ for block in blocks]
    assert kinds == ["Heading", "Paragraph", "ListBlock", "Quote", "Code", "Table", "Paragraph"]
    spans = blocks[1].spans
    assert any(span.italic and span.text == "稳中有进" for span in spans)
    assert any(span.strike and span.text == "不宜冒进" for span in spans)
    assert any(span.href == "https://example.com/a?b=1&c=2" and span.text == "星阙官网" for span in spans)
    assert sum(1 for span in spans if span.brk) == 2  # <br> 与单个换行都是换行
    nested = blocks[2].items[0][1]
    assert blocks[2].ordered and isinstance(nested, md.ListBlock) and not nested.ordered and len(nested.items) == 2
    assert blocks[4].text == "x = 1  # **不是粗体**"
    assert md.plain(blocks[5].rows[0][1]) == "平" and blocks[5].aligns == ["left", "right"]
    assert md.plain(blocks[6].spans).startswith("<script>")  # 原始 HTML 不解释，按字面
    unsafe = md.parse("[点我](javascript:alert(1))")[0].spans
    assert all(span.href is None for span in unsafe)
    # 中文里 CommonMark 不认的成对 ** / ~~ 照样是粗体 / 删除线；代码里的不动；单个 * 不动
    cjk = md.parse("前文**结论：**今年宜守，~~不宜。~~冒进 `**代码**` 2 * 3")[0].spans
    assert [span.text for span in cjk if span.bold] == ["结论："] and [span.text for span in cjk if span.strike] == ["不宜。"]
    assert any(span.code and span.text == "**代码**" for span in cjk) and md.plain(cjk).endswith("2 * 3")


@pytest.mark.parametrize("language", ["zh-CN", "zh-TW"])
def test_pdf_draws_the_tree_and_leaves_the_callers_numbers_alone(tmp_path: Path, monkeypatch, language: str) -> None:
    service = _service(tmp_path)
    run_id = _chart_run(service).memory_ref.run_id
    spy = _PdfSpy(monkeypatch)
    service.report_render({"run_id": run_id, "format": "pdf", "language": language, "ai_answer_text": READING})
    paragraphs = [item for flowable in spy.story for item in _flat(flowable) if isinstance(getattr(item, "text", None), str)]
    markup = "\n".join(item.text for item in paragraphs)
    plain = "\n".join(re.sub("<[^>]+>", "", item.text) for item in paragraphs)
    assert re.search(r"<strike>[^<]*</strike>", markup) and re.search(r"<i>[^<]*</i>", markup)
    assert 'href="https://example.com/a?b=1&amp;c=2"' in markup
    assert "0.7548645849180389" in plain and "0.7549" not in plain
    for raw in ("~~", "*稳", "](https", "&lt;br&gt;", "```"):
        assert raw not in markup, raw
    assert "#&nbsp;**不是粗" in markup  # 代码块里的记号原样（空格成不断行空格保缩进）
    assert "&lt;script&gt;" in markup  # 原始 HTML 按字面印
    bullets = [item.bulletText for item in paragraphs if getattr(item, "bulletText", None)]
    assert bullets[:4] == ["1.", "◦", "◦", "2."]
    # 「Note: …」是一句话，不进键值对照表（键值表的键格样式是 HorosaKvLabel）
    assert not any(getattr(item.style, "name", "") == "HorosaKvLabel" and "Note" in item.text for item in paragraphs)
    # 表格是真表格：表头一格就是「项目」
    assert any(re.sub("<[^>]+>", "", item.text) in {"项目", "項目"} and item.style.name == "HorosaTableHead" for item in paragraphs)


def test_docx_draws_the_same_tree_with_real_hyperlinks(tmp_path: Path) -> None:
    from docx import Document

    service = _service(tmp_path)
    run_id = _chart_run(service).memory_ref.run_id
    rendered = service.report_render({"run_id": run_id, "format": "docx", "ai_answer_text": READING})
    path = Path(rendered["artifact_path"])
    doc = Document(str(path))
    runs = [run for paragraph in doc.paragraphs for run in paragraph.runs]
    cells = [run for table in doc.tables for row in table.rows for cell in row.cells for p in cell.paragraphs for run in p.runs]
    assert any(run.font.strike and run.text == "不宜冒进" for run in runs + cells)
    assert any(run.italic and run.text == "稳中有进" for run in runs + cells)
    styles = {paragraph.style.name for paragraph in doc.paragraphs}
    assert {"List Number", "List Bullet 2"} <= styles
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    assert "0.7548645849180389" in text and "~~" not in text and "](https" not in text
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
        rels = archive.read("word/_rels/document.xml.rels").decode("utf-8")
    assert "<w:hyperlink " in xml and 'Target="https://example.com/a?b=1&amp;c=2"' in rels and 'TargetMode="External"' in rels


@pytest.mark.parametrize(
    ("reading", "expected"),
    [
        ("## 总体结论\n\n事业上稳中有进，宜守成。下半年见转机。", "事业上稳中有进，宜守成。下半年见转机。"),
        ("**结论**\n\n结论：今年宜守。\n第二行不算。", "今年宜守。"),
        ("# 标题\n\n---\n\n| a | b |\n|--|--|\n| 1 | 2 |", ""),
        ("- 日主甲木：身弱，喜印比。", "日主甲木：身弱，喜印比。"),
        ("~~划掉的话。~~留下的话。", "留下的话。"),  # CommonMark 不认（收尾 ~~ 前是标点、后是汉字），补认
        ("**结论：**今年宜守。", "今年宜守。"),
    ],
)
def test_the_conclusion_is_the_first_real_sentence(reading: str, expected: str) -> None:
    assert md.first_statement(reading) == expected


def test_no_conclusion_card_when_the_reading_has_no_sentence(tmp_path: Path, monkeypatch) -> None:
    """旧行为：取第一个非空行——「## 总体结论」被剥成「总体结论」印进核心结论卡；只有表格时印出表头那一行。"""
    service = _service(tmp_path)
    run_id = _chart_run(service).memory_ref.run_id
    spy = _PdfSpy(monkeypatch)
    service.report_render({"run_id": run_id, "format": "pdf", "ai_answer_text": "## 总体结论\n\n| 项 | 断 |\n|--|--|\n| 财 | 平 |"})
    assert "核心结论" not in spy.texts()
    spy = _PdfSpy(monkeypatch)
    service.report_render({"run_id": run_id, "format": "pdf", "ai_answer_text": "## 总体结论\n\n今年宜守，不宜扩张。"})
    texts = spy.texts()
    assert texts[texts.index("核心结论") + 1] == "今年宜守，不宜扩张。"
