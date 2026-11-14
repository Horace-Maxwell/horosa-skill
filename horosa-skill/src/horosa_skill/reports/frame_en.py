"""报告的英文界面（审计待决项 1：language:"en" = 英文界面 + 原文盘面）。

只换报告自己写的「框」：封面、目录、章节名、基本信息的项目名、页脚、渲染器自带的说明句。盘面正文（引擎输出）保持中文原文不译——
十神、神煞、格局没有公认英译，机器翻错比不翻更糟，也违背「不替语料编译名」；AI 解读由调用方用英文写。封面说明一句。
"""
from __future__ import annotations

import copy
import re
from typing import Any

FRAME_NOTE = "Chart data is printed in the engine's original Chinese; the reading is in English."

LABELS: dict[str, str] = {
    # 渲染器 / 版面自带的标签（renderers.py、layout.py 里经 t() 的字面量）
    "AI 解读": "Reading", "完整盘面": "Chart data", "附录": "Appendix", "核心结论": "Key conclusion", "总览摘要": "Summary",
    "起盘依据": "Basis of the chart", "解盘步骤": "How the chart was read", "完整解盘正文": "Full reading",
    "正文解读": "Section-by-section reading", "建议": "Recommendations", "不确定处与限制": "Uncertainties and limits",
    "解读目标": "Question", "基本信息": "Basic information", "盘图": "Chart figure", "目录": "Contents", "章节": "Section",
    "分析": "Analysis", "生成于": "Generated", "无": "None", "整体综合解盘": "General reading", "星阙 Horosa": "Horosa",
    "专业咨询报告": "Consultation report", "咨询报告": "Consultation report", "结构化咨询报告": "Consultation report",
    "结构化解读 · 行动建议 · 风险提示": "Reading · Recommendations · Risks", "目录（Word 中右键「更新域」生成页码）":
    "Contents (in Word, right-click and choose Update Field for page numbers)",
    "以下是 AI 依据后附盘面所作的解读，不是排盘引擎的输出；方括号里的 E 段号指向「完整盘面」里的原文。":
    "The reading below was written by an AI from the chart data that follows; it is not engine output. Section numbers in "
    "brackets ([E3]) point to the original text under “Chart data”.",
    "图形盘图（星盘 / 卦象 / 太乙盘 / 度盘）见同一报告的 PDF 版；下文为完整的位置与相位表。":
    "The chart figures are in the PDF version of this report; the full position and aspect tables follow.",
    "盘图（纯文本里画不出）：": "Chart figures (cannot be drawn in plain text):",
    # builder 写的框
    "完整排盘报告": "Full chart report", "技法依据": "Method", "报告说明": "About this report",
    "项目": "Item", "内容": "Value", "技法": "Technique", "姓名": "Name", "日期": "Date", "时间": "Time", "时区": "Time zone",
    "地点": "Place", "纬度": "Latitude", "经度": "Longitude", "关键设置": "Key settings", "性别": "Gender", "问题": "Question",
}
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^第 (\d+) 页 / 共 (\d+) 页$"), r"Page \1 of \2"),
    (re.compile(r"^第 (\d+) 页$"), r"Page \1"),
)


def label(text: str) -> str:
    if text in LABELS:
        return LABELS[text]
    for pattern, replacement in _PATTERNS:
        if pattern.match(text):
            return pattern.sub(replacement, text)
    return text


def _table_keys(body: str) -> str:
    """「| 项目 | 内容 |」两列表：表头与第一列的项目名换成英文（值不动）。"""
    out = []
    for line in str(body or "").split("\n"):
        cells = line.split("|")
        if len(cells) >= 4 and line.startswith("|"):
            cells[1] = f" {label(cells[1].strip())} "
            if cells[2].strip() in LABELS and set(cells[1].strip()) != {"-"}:
                cells[2] = f" {label(cells[2].strip())} "
            line = "|".join(cells)
        out.append(line)
    return "\n".join(out)


def english_frame(document: dict[str, Any]) -> dict[str, Any]:
    """返回一份换了英文框的副本；盘面段（group=chart）一字不动。"""
    doc = copy.deepcopy(document)
    doc["interface"] = "en"
    title = str(doc.get("title") or "")
    if title.startswith("结构化咨询报告 · "):
        doc["title"] = "Consultation report · " + title.removeprefix("结构化咨询报告 · ")
    elif title.endswith(" · 完整排盘报告"):
        doc["title"] = title.removesuffix(" · 完整排盘报告") + " · Full chart report"
    for key in ("cover_label", "intro_heading"):
        if doc.get(key):
            doc[key] = label(str(doc[key]))
    if doc.get("style") == "chart" and doc.get("intro_text"):
        doc["intro_text"] = "This report is generated directly from the Horosa engine's chart: every chart section and the method used."
    doc["intro_text"] = FRAME_NOTE + ("\n\n" + str(doc["intro_text"]) if doc.get("intro_text") else "")
    for section in doc.get("sections") or []:
        if not isinstance(section, dict) or section.get("group") == "chart":
            continue
        if section.get("title"):
            section["title"] = label(str(section["title"]))
        if section.get("group") in {"basis", "appendix"} and isinstance(section.get("body"), str):
            section["body"] = _table_keys(section["body"])
    return doc
