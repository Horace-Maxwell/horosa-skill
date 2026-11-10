"""正文的版面顺序：DOCX 与 PDF 读同一串块，各自决定怎么画。

这里定的是「印什么、按什么顺序」：结论卡、总览、完整盘面（盘图在最前）、AI 解读排在附录之前。怎么画（分页、字号、段内链接、分栏）
归渲染器，块只带用途（`role`），不带样式。

封面、目录和报告说明不在这里：PDF 把基本信息画在封面上、报告说明只给解读报告，DOCX 把它们排在正文里、两种报告都有。
两边的结构本来就不同，硬并成一串块只是把 `if pdf` 搬个地方。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HUMAN_RENDER_HIDDEN_SECTION_IDS = {
    "report_metadata",
    "report_quality",
    "delivery_checklist",
    "coverage_contract",
    "section_coverage_matrix",
    "targeted_analysis_contract",
    "question_analysis",
    "input_overview",
    "technique_summary",
    "ai_interpretation",
    "recommendations_limitations",
    "xingque_export_text",
    "provenance",
}


@dataclass(frozen=True)
class Block:
    """`kind` 决定读哪些字段：
    card（text 标题、body、role = 强调色）· heading（text、role = 用途）· body（body）· part（text、role = chart / ai / appendix）·
    note（text）· figures（盘图；document["figure_notes"] 随后成 note）· section（text 标题、body、role = 分组、cite 段号、in_part = 在某个部分之下）·
    orphan_figures（text = 部分标题：有盘图却没有任何章节时，只有 PDF 补印）。
    """

    kind: str
    text: str = ""
    body: str = ""
    role: str = ""
    cite: str = ""
    in_part: bool = False


def _human_sections(document: dict[str, Any]) -> list[dict[str, Any]]:
    sections = document.get("sections") if isinstance(document.get("sections"), list) else []
    output: list[dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        if section.get("human_visible") is not True:
            continue
        if str(section.get("id") or "") in HUMAN_RENDER_HIDDEN_SECTION_IDS:
            continue
        output.append(section)
    return output


def _human_ai_value(ai_report: dict[str, Any], key: str) -> Any:
    human_key = f"human_{key}"
    if human_key in ai_report:
        return ai_report.get(human_key)
    return ai_report.get(key)


def _human_ai_list(ai_report: dict[str, Any], key: str) -> list[Any]:
    value = _human_ai_value(ai_report, key)
    return value if isinstance(value, list) else []


def _steps_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"{index}. {item}" for index, item in enumerate(value, start=1) if str(item).strip())
    return str(value or "")


def _ai_body_blocks(ai_report: dict[str, Any], t: Any) -> list[Block]:
    summary = _human_ai_value(ai_report, "executive_summary")
    basis = _human_ai_value(ai_report, "consultation_basis")
    steps = _human_ai_list(ai_report, "reading_steps")
    analysis = _human_ai_list(ai_report, "analysis_sections")
    recommendations = _human_ai_list(ai_report, "recommendations")
    limitations = _human_ai_list(ai_report, "limitations")
    answer_text = str(ai_report.get("answer_text") or "")
    separate_answer = bool(answer_text) and answer_text != str(summary or "")
    if not (basis or steps or analysis or recommendations or limitations or separate_answer):
        return []
    blocks = [
        Block("part", t("AI 解读"), role="ai"),
        Block("note", t("以下是 AI 依据上方盘面所作的解读，不是排盘引擎的输出；方括号里的 E 段号指向盘面原文。")),
    ]
    if basis:
        blocks.append(Block("card", t("起盘依据"), str(basis or ""), role="green"))
    if steps:
        blocks.append(Block("card", t("解盘步骤"), _steps_text(steps), role="blue"))
    if separate_answer:
        blocks += [Block("heading", t("完整解盘正文"), role="ai_topic"), Block("body", body=answer_text)]
    if analysis:
        blocks.append(Block("heading", t("正文解读"), role="ai_topic"))
        for section in analysis:
            if isinstance(section, dict):
                blocks.append(Block("heading", str(section.get("title") or t("分析")), role="ai_section"))
                blocks.append(Block("body", body=str(section.get("body") or section.get("content") or "")))
            else:
                blocks.append(Block("body", body=str(section)))
    if recommendations:
        blocks.append(Block("card", t("建议"), "\n".join(f"- {item}" for item in recommendations), role="amber"))
    if limitations:
        blocks += [Block("heading", t("不确定处与限制"), role="ai_topic"), Block("body", body="\n".join(f"- {item}" for item in limitations))]
    return blocks


def body_blocks(document: dict[str, Any], t: Any = str) -> list[Block]:
    """封面与目录之后的全部内容，按印出来的顺序。`t` 转渲染器自带的标签（文档里的文字调用方已转好）。"""
    ai_report = document.get("ai_report") if isinstance(document.get("ai_report"), dict) else {}
    show_ai = document.get("show_ai", True) is not False
    figures = any(isinstance(figure, dict) for figure in document.get("figures") or [])
    # 出报告时补算的盘没画出来（reports/aux_charts.py）：盘图节下说明缺了哪张、为什么
    figure_notes = [Block("note", str(note)) for note in document.get("figure_notes") or [] if str(note).strip()]
    blocks: list[Block] = []
    conclusion = _human_ai_value(ai_report, "direct_answer") or _human_ai_value(ai_report, "analysis_focus")
    if show_ai and conclusion:
        blocks.append(Block("card", t("核心结论"), str(conclusion), role="green"))
    summary = _human_ai_value(ai_report, "executive_summary")
    if show_ai and summary:
        blocks += [Block("heading", t("总览摘要"), role="summary"), Block("body", body=str(summary or ""))]

    ai_body = _ai_body_blocks(ai_report, t) if show_ai else []
    parts = {"chart": t("完整盘面"), "appendix": t("附录")}
    current_group: str | None = None
    for section in _human_sections(document):
        group = section.get("group")
        if group == "basis":
            continue
        if group == "appendix":  # 数据在前：AI 解读排在盘面之后、附录之前
            blocks += ai_body
            ai_body = []
        if group in parts and group != current_group:
            blocks.append(Block("part", parts[group], role=str(group)))
            if group == "chart" and (figures or figure_notes):
                blocks += [Block("heading", t("盘图"), role="figures"), *([Block("figures")] if figures else []), *figure_notes]
                figure_notes = []
        current_group = group
        cite = str(section.get("cite_id") or "") if group == "chart" else ""
        blocks.append(Block("section", str(section.get("title") or t("章节")), str(section.get("body") or ""), role=str(group or ""), cite=cite, in_part=group in parts))
    blocks += ai_body
    if figures and current_group is None:
        blocks.append(Block("orphan_figures", parts["chart"]))
    return blocks + figure_notes  # 没有「完整盘面」部分时说明排在最后，不丢
