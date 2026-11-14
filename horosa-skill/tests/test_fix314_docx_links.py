"""DOCX：盘面段标题带书签、AI 正文里的 [E#] 是跳过去的内部链接、标题段 keepNext、表格行 cantSplit、占位目录与真实目录同源（审计 O-18）。

修前 python-docx 检查：`w:anchor` 0、`keepNext` 0、`cantSplit` 0；占位目录只列 E 段与技法依据。
负向对照（实跑过）：add_spans 不拆 [E#] → 第一条红；占位目录回到只列 human sections → 第二条红。
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from test_report_structure import _ai_report, _produced_cites
from test_user_knowledge_and_chart_report import _chart_run, _service


def _xml(tmp_path: Path) -> tuple[str, str]:
    service = _service(tmp_path)
    run = _chart_run(service)
    (first, _), (second, _) = _produced_cites(run)[:2]
    out = service.report_render({"run_id": run.memory_ref.run_id, "tool_name": "chart", "format": "docx",
                                 "ai_report": _ai_report(first, second)})
    return zipfile.ZipFile(out["artifact_path"]).read("word/document.xml").decode("utf-8"), first


def test_cites_link_to_bookmarked_sections(tmp_path: Path) -> None:
    xml, first = _xml(tmp_path)
    assert f'w:anchor="{first}"' in xml and f'w:name="{first}"' in xml
    assert 'w:anchor="E999"' not in xml and "[E999]" in re.sub(r"<[^>]+>", "", xml)   # 报告里没有的段号不链
    assert "<w:keepNext/>" in xml and "<w:cantSplit/>" in xml


def test_the_placeholder_toc_lists_the_ai_parts_too(tmp_path: Path) -> None:
    xml, _ = _xml(tmp_path)
    field = xml[xml.index('TOC \\o'):xml.index("</w:fldSimple>")]
    text = re.sub(r"<[^>]+>", "|", field)
    assert "AI 解读" in text and "完整盘面" in text and "解读目标" in text, text[:400]
