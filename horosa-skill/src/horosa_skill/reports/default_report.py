"""确定性默认解读：调用方没写到的字段由这里补齐。这里的文字都是机器写的，不是 AI 解读。

去向看 `merge_ai_report`：机器 JSON 的 `ai_report` 总是带着；`human_*`（人读版 PDF / DOCX）只在调用方给了一段
`answer_text` 且没写对应字段时才不带。调用方写了 `analysis_sections`，或没有 `answer_text` 时，补齐的段落会印在「AI 解读」下面。
"""

from __future__ import annotations

import copy
import functools
import json
import re
from pathlib import Path
from typing import Any

from horosa_skill.reports.question import analyze_question
from horosa_skill.reports.source import analysis_section_matches_source, read_caller_answer, read_user_question

_TECHNIQUE_PROFILES_PATH = Path(__file__).parents[1] / "data" / "report_technique_profiles.json"


@functools.lru_cache(maxsize=1)
def _technique_profiles() -> dict[str, Any]:
    return json.loads(_TECHNIQUE_PROFILES_PATH.read_text(encoding="utf-8"))


def merge_ai_report(
    *,
    run: dict[str, Any],
    ai_report: dict[str, Any] | None,
    source: dict[str, Any],
    input_normalized: dict[str, Any],
    summary: list[Any],
    export_sections: list[dict[str, Any]],
    export_text: str,
) -> dict[str, Any]:
    base = read_caller_answer(run=run, ai_report=ai_report)
    base_has_answer_text = bool(str(base.get("answer_text") or "").strip())
    base_has_executive_summary = bool(str(base.get("executive_summary") or base.get("summary") or "").strip())
    base_has_consultation_basis = bool(base.get("consultation_basis"))
    base_has_reading_steps = bool(base.get("reading_steps"))
    base_has_analysis_sections = isinstance(base.get("analysis_sections"), list) and bool(base.get("analysis_sections"))
    base_has_recommendations = isinstance(base.get("recommendations"), list) and bool(base.get("recommendations"))
    base_has_limitations = isinstance(base.get("limitations"), list) and bool(base.get("limitations"))
    default_report = _default_ai_report(
        run=run,
        source=source,
        input_normalized=input_normalized,
        summary=summary,
        export_sections=export_sections,
        export_text=export_text,
    )
    merged = copy.deepcopy(default_report)
    for key, value in base.items():
        if value not in (None, "", [], {}):
            merged[key] = value
    merged["analysis_sections"] = _complete_analysis_sections(
        analysis_sections=merged.get("analysis_sections") if isinstance(merged.get("analysis_sections"), list) else [],
        default_sections=default_report.get("analysis_sections") if isinstance(default_report.get("analysis_sections"), list) else [],
        export_sections=export_sections,
    )
    # Machine JSON keeps deterministic coverage backfills. Human DOCX/PDF should not
    # turn those backfills into "AI-written" prose when the client supplied a single
    # natural-language answer_text, which is the common path for Cursor/OpenClaw/etc.
    if base_has_answer_text and not base_has_analysis_sections:
        human_analysis_sections: list[Any] = []
    else:
        human_analysis_sections = merged.get("analysis_sections") if isinstance(merged.get("analysis_sections"), list) else []
    if base_has_answer_text and not base_has_recommendations:
        human_recommendations: list[Any] = []
    else:
        human_recommendations = merged.get("recommendations") if isinstance(merged.get("recommendations"), list) else []
    if base_has_answer_text and not base_has_limitations:
        human_limitations: list[Any] = []
    else:
        human_limitations = merged.get("limitations") if isinstance(merged.get("limitations"), list) else []
    human_executive_summary = (
        merged.get("executive_summary") or merged.get("summary") or ""
        if base_has_executive_summary or not base_has_answer_text
        else ""
    )
    human_consultation_basis = merged.get("consultation_basis") or "" if base_has_consultation_basis or not base_has_answer_text else ""
    human_reading_steps = (
        merged.get("reading_steps")
        if isinstance(merged.get("reading_steps"), list) and (base_has_reading_steps or not base_has_answer_text)
        else []
    )
    return {
        "analysis_focus": merged.get("analysis_focus") or "",
        "direct_answer": merged.get("direct_answer") or merged.get("answer") or "",
        "consultation_basis": merged.get("consultation_basis") or "",
        "reading_steps": merged.get("reading_steps") if isinstance(merged.get("reading_steps"), list) else [],
        "executive_summary": merged.get("executive_summary") or merged.get("summary") or "",
        "analysis_sections": merged.get("analysis_sections") if isinstance(merged.get("analysis_sections"), list) else [],
        "recommendations": merged.get("recommendations") if isinstance(merged.get("recommendations"), list) else [],
        "limitations": merged.get("limitations") if isinstance(merged.get("limitations"), list) else [],
        "evidence": merged.get("evidence") if isinstance(merged.get("evidence"), list) else [],
        "follow_up_questions": merged.get("follow_up_questions") if isinstance(merged.get("follow_up_questions"), list) else [],
        "answer_text": merged.get("answer_text") or "",
        "human_executive_summary": human_executive_summary,
        "human_consultation_basis": human_consultation_basis,
        "human_reading_steps": human_reading_steps,
        "human_analysis_sections": human_analysis_sections,
        "human_recommendations": human_recommendations,
        "human_limitations": human_limitations,
        "raw": merged,
    }


def _complete_analysis_sections(
    *,
    analysis_sections: list[Any],
    default_sections: list[Any],
    export_sections: list[dict[str, Any]],
) -> list[Any]:
    """Preserve the AI's targeted answer while backfilling source-section coverage."""
    completed = copy.deepcopy(analysis_sections)
    if not export_sections:
        return completed or copy.deepcopy(default_sections)
    for index, source_section in enumerate(export_sections, start=1):
        source_title = str(source_section.get("title") or f"导出章节 {index}")
        if any(analysis_section_matches_source(section, source_title) for section in completed):
            continue
        default_match = next(
            (
                section
                for section in default_sections
                if analysis_section_matches_source(section, source_title)
            ),
            None,
        )
        if default_match:
            completed.append(copy.deepcopy(default_match))
    existing_titles = {
        str(section.get("title") or section.get("source_section_title") or "").strip()
        for section in completed
        if isinstance(section, dict)
    }
    for default_section in default_sections:
        if not isinstance(default_section, dict):
            continue
        default_title = str(default_section.get("title") or default_section.get("source_section_title") or "").strip()
        if default_title and default_title not in existing_titles:
            completed.append(copy.deepcopy(default_section))
            existing_titles.add(default_title)
    return completed


def _default_ai_report(
    *,
    run: dict[str, Any],
    source: dict[str, Any],
    input_normalized: dict[str, Any],
    summary: list[Any],
    export_sections: list[dict[str, Any]],
    export_text: str,
) -> dict[str, Any]:
    question = _consultation_question(read_user_question(run))
    technique = str(source.get("technique") or source.get("tool_name") or "")
    if technique in {"bazi", "bazi_birth", "bazi_direct"} or str(source.get("tool_name") or "").startswith("bazi"):
        return _default_bazi_report(
            question=question,
            source=source,
            input_normalized=input_normalized,
            export_sections=export_sections,
            export_text=export_text,
        )
    return _default_generic_report(
        question=question,
        source=source,
        input_normalized=input_normalized,
        summary=summary,
        export_sections=export_sections,
        export_text=export_text,
    )


def _default_generic_report(
    *,
    question: str,
    source: dict[str, Any],
    input_normalized: dict[str, Any],
    summary: list[Any],
    export_sections: list[dict[str, Any]],
    export_text: str,
) -> dict[str, Any]:
    technique_label = source.get("technique_label") or source.get("technique") or source.get("tool_name") or "当前技法"
    profile = _technique_report_profile(source)
    source_titles = [str(section.get("title")) for section in export_sections if section.get("title")]
    focus_text = _focus_text(question)
    consultation_basis = _generic_consultation_basis(
        input_normalized=input_normalized,
        technique_label=str(technique_label),
    )
    analysis_sections = [
        {
            "title": "整体结论",
            "source_section_title": source_titles[0] if source_titles else "工具摘要",
            "body": _generic_overview_text(
                technique_label=str(technique_label),
                question=question,
                summary=summary,
                export_sections=export_sections,
                profile=profile,
            ),
            "evidence_lines": _evidence_from_sections(export_sections, limit=4) or [str(item) for item in summary[:3]],
            "relevance_to_question": "直接回应本次咨询主题，先给读者一个可落地的判断框架。",
            "confidence": "medium",
        }
    ]
    for section in export_sections:
        title = str(section.get("title") or "导出章节")
        analysis_sections.append(
            {
                "title": title,
                "source_section_title": title,
                "body": _section_reading_body(section, profile=profile),
                "evidence_lines": _clean_lines(section.get("lines") if isinstance(section.get("lines"), list) else [], limit=5),
                "relevance_to_question": "把原始导出章节翻译成读者能理解的现实含义。",
                "confidence": "medium",
            }
        )
    return {
        "analysis_focus": question,
        "consultation_basis": consultation_basis,
        "reading_steps": _generic_reading_steps(profile=profile, question=question),
        "direct_answer": _generic_direct_answer(
            question=question,
            technique_label=str(technique_label),
            profile=profile,
            focus_text=focus_text,
        ),
        "executive_summary": "\n".join(
            [
                f"本次咨询主题：{question}。",
                f"采用技法：{technique_label}；阅读重心是{profile['basis']}。",
                f"报告会把盘面线索转化为{focus_text}，并按{profile['decision_style']}给出可读结论。",
            ]
        ),
        "analysis_sections": analysis_sections,
        "recommendations": [
            f"先阅读“整体结论”，再按{profile['evidence_name']}核对原始盘面线索。",
            "如果用于真实决策，请补充具体问题、时间范围、背景约束与已知事实。",
            f"可继续要求 AI 按{profile['recommended_followup']}做专项展开。",
        ],
        "limitations": [
            "本报告基于本地工具输出进行解释，不替代专业法律、医疗、财务意见。",
            "未提供现实背景时，判断会偏向盘面结构解读，具体落点需要二次追问校准。",
        ],
        "evidence": _evidence_from_sections(export_sections, limit=10) or [export_text[:300]] if export_text else [],
        "follow_up_questions": [
            "你最想优先分析事业、关系、财务还是阶段运势？",
            "这次报告是用于复盘过去、判断当下，还是规划未来？",
        ],
    }


def _default_bazi_report(
    *,
    question: str,
    source: dict[str, Any],
    input_normalized: dict[str, Any],
    export_sections: list[dict[str, Any]],
    export_text: str,
) -> dict[str, Any]:
    """机器写的八字默认解读：按明面干支数五行、套固定句式。不是星阙引擎的结果，也不是 AI 写的。"""
    question = _consultation_question(question)
    pillars = _extract_bazi_pillars(export_text)
    day_master = _day_master_text(pillars.get("日柱"))
    element_counts = _bazi_element_counts(pillars)
    element_text = "、".join(f"{name}{count}" for name, count in element_counts.items() if count)
    # 计数恒有五个键：按 dict 真值判空恒真，读不出四柱时全 0、max/min 都落在「木」——必须看值。
    has_elements = any(element_counts.values())
    strongest = max(element_counts, key=element_counts.get) if has_elements else ""
    weakest = min(element_counts, key=element_counts.get) if has_elements else ""
    focus_text = _focus_text(question)
    subject_profile = _bazi_subject_profile(input_normalized=input_normalized, pillars=pillars, day_master=day_master)
    consultation_basis = _bazi_consultation_basis(
        input_normalized=input_normalized,
        pillars=pillars,
        day_master=day_master,
    )
    decision_hint = _bazi_decision_hint(question=question, day_master=day_master, counts=element_counts)
    core_lines = [
        f"四柱为：{_format_pillars(pillars)}。" if pillars else "四柱信息已从星阙导出中读取。",
        f"日主为{day_master}，报告会以日主承载力、月令环境、五行流动和神煞提示为主线。" if day_master else "报告会以四柱结构、五行流动和神煞提示为主线。",
        f"从明面干支粗略计数看，五行分布为：{element_text}；其中{strongest}相对突出，{weakest}相对需要被留意。" if has_elements else "五行强弱需要结合藏干、月令、大运流年继续细化。",
    ]
    evidence = _evidence_from_sections(export_sections, limit=12)
    start_info = _section_by_title(export_sections, "起盘信息")
    pillars_info = _section_by_title(export_sections, "四柱")
    direction_info = _section_by_title(export_sections, "流年")
    gods_info = _section_by_title(export_sections, "神煞")
    analysis_sections = [
        {
            "title": "个案档案",
            "source_section_title": "起盘信息",
            "body": subject_profile,
            "evidence_lines": _clean_lines(start_info.get("lines", []) if start_info else [], limit=6),
            "relevance_to_question": "先固定这个人的出生资料、四柱与日主，确保后续解读围绕同一个个案。",
            "confidence": "high",
        },
        {
            "title": "本次问题定向判断",
            "source_section_title": "综合解读",
            "body": _bazi_targeted_reading(
                question=question,
                day_master=day_master,
                counts=element_counts,
                decision_hint=decision_hint,
            ),
            "evidence_lines": [f"咨询主题：{question}", f"五行粗略计数：{element_text}"] if element_text else [f"咨询主题：{question}"],
            "relevance_to_question": "把命局结构直接落到本次具体问题，避免只做泛泛命盘说明。",
            "confidence": "medium",
        },
        {
            "title": "命盘核心结论",
            "source_section_title": "四柱与三元",
            "body": "\n".join(
                [
                    "这张八字的阅读重点不应停留在“列出四柱”，而要看它呈现出的性格驱动力、资源调度方式和人生议题。",
                    *core_lines,
                    "整体上，它更适合被解读为一张需要在自我主张、现实秩序、资源压力与行动节奏之间找到平衡的命盘。",
                ]
            ),
            "evidence_lines": _clean_lines(pillars_info.get("lines", []) if pillars_info else [], limit=6),
            "relevance_to_question": "回应用户要一份能直接看的最终解读，而不是原始字段堆叠。",
            "confidence": "medium",
        },
        {
            "title": "起盘信息与时间可靠性",
            "source_section_title": "起盘信息",
            "body": _bazi_starting_context(start_info, input_normalized),
            "evidence_lines": _clean_lines(start_info.get("lines", []) if start_info else [], limit=8),
            "relevance_to_question": "确认报告使用的时间、地点、真太阳时等基础信息，避免后续判断失根。",
            "confidence": "high",
        },
        {
            "title": "日主与命局气势",
            "source_section_title": "四柱与三元",
            "body": _bazi_day_master_reading(pillars, day_master, element_counts),
            "evidence_lines": _clean_lines(pillars_info.get("lines", []) if pillars_info else [], limit=8),
            "relevance_to_question": "把四柱翻译成可理解的人格与行动结构。",
            "confidence": "medium",
        },
        {
            "title": "五行流动与现实议题",
            "source_section_title": "四柱与三元",
            "body": _bazi_element_reading(element_counts),
            "evidence_lines": [f"五行粗略计数：{element_text}"] if element_text else [],
            "relevance_to_question": "解释命盘中不同力量如何落到工作、资源、表达和压力管理。",
            "confidence": "medium",
        },
        {
            "title": "大运流年与阶段判断",
            "source_section_title": "流年行运概略",
            "body": _bazi_liunian_reading(direction_info, question=question),
            "evidence_lines": _section_lines(direction_info, limit=12),
            "relevance_to_question": "把八字从静态命局推进到阶段运势，尤其用于事业、财务、关系和时间窗口问题。",
            "confidence": "medium",
        },
        {
            "title": "神煞提示与事件倾向",
            "source_section_title": "神煞（四柱与三元）",
            "body": _bazi_shensha_reading(gods_info),
            "evidence_lines": _clean_lines(gods_info.get("lines", []) if gods_info else [], limit=10),
            "relevance_to_question": "将神煞从名单翻译为可读的提醒，而不是机械堆砌。",
            "confidence": "medium",
        },
        {
            "title": "事业、关系与财务建议",
            "source_section_title": "综合解读",
            "body": _bazi_life_advice(day_master, element_counts),
            "evidence_lines": evidence[:6],
            "relevance_to_question": "把盘面信息落到可操作的生活和决策建议。",
            "confidence": "medium",
        },
    ]
    covered_titles = {
        str(section.get("source_section_title") or section.get("title") or "")
        for section in analysis_sections
        if isinstance(section, dict)
    }
    for section in export_sections:
        title = str(section.get("title") or "")
        if not title or title in covered_titles:
            continue
        analysis_sections.append(
            {
                "title": title,
                "source_section_title": title,
                "body": _section_reading_body(section),
                "evidence_lines": _clean_lines(section.get("lines") if isinstance(section.get("lines"), list) else [], limit=6),
                "relevance_to_question": "保留并解释星阙导出的完整章节，避免最终报告缺漏。",
                "confidence": "medium",
            }
        )
    return {
        "analysis_focus": question,
        "consultation_basis": consultation_basis,
        "reading_steps": _bazi_reading_steps(question),
        "direct_answer": f"就「{question}」来看，结论上：{decision_hint} 这张八字的主线是以{day_master or '日主'}为中心，在自我主张、现实秩序、资源压力与行动节奏之间找平衡；具体判断应优先落到{focus_text}，并用大运流年继续校准时间点。",
        "executive_summary": "\n".join(
            [
                f"个案主线：{_format_pillars(pillars) or '四柱信息已读取'}；日主：{day_master or '未明'}。",
                f"本次咨询重点：{question}；报告会把命局结构转译为{focus_text}。",
                "结论先行：这张盘适合从长期积累、资源调度、规则边界和执行节奏入手解读；短期事件和具体年份仍需叠加大运流年。",
            ]
        ),
        "analysis_sections": analysis_sections,
        "recommendations": [
            "如果要继续精读，优先补充大运、流年和当前最关心的问题，这会显著提高判断针对性。",
            "把报告中的“强项”用于职业定位和资源配置，把“压力点”用于制定边界、节奏和风险预案。",
            "涉及关系、投资、健康等现实决策时，把八字结论作为观察框架，不要替代事实核查与专业意见。",
        ],
        "limitations": [
            "本报告采用本地八字工具输出与确定性解释模板生成，未调用外部 AI API。",
            "五行计数是基于明面干支的阅读辅助，不等于完整旺衰定格；完整判断仍需结合藏干、月令、通根、调候、大运流年。",
            "神煞只作为提示线索，不宜单独作为吉凶断语。",
        ],
        "evidence": evidence,
        "follow_up_questions": [
            "要不要继续生成大运流年版，把事业、财务、关系分年份展开？",
            "你更想看性格结构、职业路径、感情关系，还是未来三年的阶段重点？",
            "出生时间是否确定到分钟？如果不确定，可以比较相邻时辰差异。",
        ],
    }


def _generic_overview_text(
    *,
    technique_label: str,
    question: str,
    summary: list[Any],
    export_sections: list[dict[str, Any]],
    profile: dict[str, str],
) -> str:
    summary_text = "；".join(str(item) for item in summary[:4] if str(item).strip())
    section_text = "、".join(str(section.get("title")) for section in export_sections[:6] if section.get("title"))
    lines = [
        f"本次咨询使用 {technique_label} 处理「{question}」。",
        f"这类技法的阅读重点是{profile['basis']}；报告会优先把它翻译成{profile['decision_style']}。",
        f"盘面返回的核心摘要为：{summary_text}。" if summary_text else "",
        f"可用于判断的主要章节包括：{section_text}。" if section_text else "",
        f"阅读顺序建议：先看整体结论，再按{profile['evidence_name']}核对依据，最后看建议与限制。",
    ]
    return "\n".join(line for line in lines if line)


def _generic_reading_steps(*, profile: dict[str, str], question: str) -> list[str]:
    steps = [
        f"先确认起盘依据：时间、地点、参数和本技法所需输入是否完整。",
        f"再抓主线：优先看{profile['basis']}，不要从单个词或单个字段直接下断语。",
        f"然后按问题落点拆解：把盘面线索转成{profile['decision_style']}。",
        f"最后给行动建议：明确可推进事项、风险边界、需要补充的信息和下一步追问方向。",
    ]
    if question == "综合命局咨询":
        steps[2] = f"然后做整体综合解盘：把盘面线索转成{profile['decision_style']}，同时覆盖机会、压力和风险边界。"
    return steps


def _generic_consultation_basis(*, input_normalized: dict[str, Any], technique_label: str) -> str:
    date = input_normalized.get("date") or input_normalized.get("birth_date")
    time = input_normalized.get("time") or input_normalized.get("birth_time")
    zone = input_normalized.get("zone") or input_normalized.get("timezone")
    lat = input_normalized.get("lat") or input_normalized.get("gpsLat")
    lon = input_normalized.get("lon") or input_normalized.get("gpsLon")
    parts: list[str] = []
    if date or time:
        parts.append(f"起盘时间：{date or '未提供日期'} {time or '未提供时间'}")
    if zone:
        parts.append(f"时区：{zone}")
    if lon or lat:
        parts.append(f"地点：经度 {lon or '未提供'}，纬度 {lat or '未提供'}")
    if not parts:
        return f"本报告基于 {technique_label} 的本地起盘结果生成；若要进一步校准，请补充时间、地点与问题背景。"
    return "；".join(parts) + "。"


def _bazi_consultation_basis(
    *,
    input_normalized: dict[str, Any],
    pillars: dict[str, str],
    day_master: str,
) -> str:
    parts = [_generic_consultation_basis(input_normalized=input_normalized, technique_label="八字").rstrip("。")]
    formatted = _format_pillars(pillars)
    if formatted:
        parts.append(f"四柱：{formatted}")
    if day_master:
        parts.append(f"日主：{day_master}")
    return "；".join(part for part in parts if part) + "。"


def _generic_direct_answer(
    *,
    question: str,
    technique_label: str,
    profile: dict[str, str],
    focus_text: str,
) -> str:
    if question == "综合命局咨询":
        return (
            f"在没有指定单一问题时，这份{technique_label}报告会按整体全面解读处理：先看{profile['basis']}，"
            f"再提炼主要机会、压力、风险边界和后续可追问方向；阅读重点放在{profile['decision_style']}。"
        )
    decision_hint = _generic_decision_hint(question)
    return (
        f"就「{question}」来看，结论上：{decision_hint}"
        f"{technique_label}的判断重点是先看{profile['basis']}，再把关键章节落到{focus_text}；"
        f"后续解释应按{profile['decision_style']}展开，"
        "不要只看单个字段或孤立吉凶。"
    )


def _generic_decision_hint(question: str) -> str:
    analysis = analyze_question(question)
    domains = set(analysis.get("focus_domains") if isinstance(analysis.get("focus_domains"), list) else [])
    hints: list[str] = []
    if "career" in domains:
        hints.append("事业上应先判断当前环境是否能持续积累能力、信用和资源，不宜只被短期机会牵动")
    if "wealth" in domains:
        hints.append("财务上应把现金流、风险上限和可复盘机制放在收益想象之前，高杠杆或边界不清的选择要谨慎")
    if "relationship" in domains:
        hints.append("关系上应先分清双方责任、互动节奏和真实需求，再判断推进或收缩")
    if "health" in domains:
        hints.append("健康相关只给趋势提醒，具体诊断应交给专业医疗判断")
    if "study" in domains:
        hints.append("学习申请上应把准备节奏、资源支持和关键时间点拆开评估")
    if "relocation" in domains:
        hints.append("迁移远行上应同时评估环境收益、成本、手续和后续承接能力")
    if analysis.get("needs_timing"):
        hints.append("时间上先按阶段顺序判断，具体年月需要结合对应推运或应期材料再细化")
    if analysis.get("needs_decision_support"):
        hints.append("决策上优先选择下行风险可控、证据更充分、能长期累积的方案")
    if not hints:
        hints.append("先做整体结构判断，再把机会、压力、风险边界和下一步追问拆开看")
    return "；".join(hints) + "。"


def _technique_report_profile(source: dict[str, Any]) -> dict[str, str]:
    key = f"{source.get('tool_name') or ''} {source.get('technique') or ''} {source.get('technique_label') or ''}"
    table = _technique_profiles()
    for entry in table["profiles"]:
        if any(marker in key for marker in entry["markers"]):
            return entry
    return table["default"]


def _section_reading_body(section: dict[str, Any], *, profile: dict[str, str] | None = None) -> str:
    title = str(section.get("title") or "本章节")
    lines = _clean_lines(section.get("lines") if isinstance(section.get("lines"), list) else [], limit=8)
    if not lines:
        body = str(section.get("body") or "").strip()
        lines = [item.strip() for item in body.splitlines() if item.strip()][:8]
    if not lines:
        return f"{title} 暂无可展开正文；建议回到原始工具输出确认该章节是否为空。"
    profile = profile or _technique_report_profile({})
    return "\n".join(
        [
            f"{title} 是本次判断的直接依据之一。",
            f"可读解读：这一组信息应放回{profile['basis']}中理解，重点看它如何支持{profile['decision_style']}，而不是被当成孤立吉凶字段。",
            "关键线索：" + "；".join(lines[:5]),
        ]
    )


def _consultation_question(question: str) -> str:
    cleaned = str(question or "").strip()
    if not cleaned:
        return "综合命局咨询"
    if any(marker in cleaned for marker in ["这个人", "此人", "本人", "客户", "咨询", "判断", "是否", "适合"]):
        return cleaned
    if ("生成" in cleaned or "输出" in cleaned) and "报告" in cleaned:
        focus = _focus_text(cleaned)
        if focus == "综合判断、风险提示与后续追问方向":
            return "综合命局咨询"
        return f"{focus}专项咨询"
    return cleaned


def _focus_text(question: str) -> str:
    analysis = analyze_question(question)
    domains = analysis.get("focus_domains") if isinstance(analysis.get("focus_domains"), list) else []
    labels = {
        "career": "事业发展与工作选择",
        "wealth": "财务资源与风险管理",
        "relationship": "关系互动与边界",
        "health": "身心节奏与健康注意事项",
        "study": "学习考试与申请推进",
        "relocation": "迁移远行与环境变化",
        "timing": "时间窗口与阶段节奏",
        "decision": "决策取舍与行动优先级",
        "general_reading": "综合判断、风险提示与后续追问方向",
    }
    ordered = [labels[item] for item in domains if item in labels]
    if not ordered:
        ordered = [labels["general_reading"]]
    if analysis.get("needs_timing") and labels["timing"] not in ordered:
        ordered.append(labels["timing"])
    if analysis.get("needs_decision_support") and labels["decision"] not in ordered:
        ordered.append(labels["decision"])
    return "、".join(ordered)


def _bazi_subject_profile(*, input_normalized: dict[str, Any], pillars: dict[str, str], day_master: str) -> str:
    date = input_normalized.get("date") or "未提供"
    time = input_normalized.get("time") or "未提供"
    zone = input_normalized.get("zone") or "未提供"
    lat = input_normalized.get("lat") or input_normalized.get("gpsLat") or "未提供"
    lon = input_normalized.get("lon") or input_normalized.get("gpsLon") or "未提供"
    gender = input_normalized.get("gender")
    gender_text = "男命/阳顺规则输入" if gender is True else "女命/阴逆规则输入" if gender is False else "未指定"
    return "\n".join(
        [
            f"出生资料：{date} {time}，时区 {zone}，经纬度 {lon} / {lat}。",
            f"性别/顺逆输入：{gender_text}。",
            f"四柱结构：{_format_pillars(pillars) or '未能从导出正文中提取完整四柱'}。",
            f"日主定位：{day_master or '未明'}。后续所有判断都围绕日主如何承接环境、资源、压力与行动节奏展开。",
        ]
    )


def _bazi_reading_steps(question: str) -> list[str]:
    steps = [
        "先核对起盘：公历时间、时区、经纬度、真太阳时、性别/顺逆和四柱是否一致。",
        "再定日主：以日柱天干为中心，观察月令环境、四柱结构、五行流动和十神压力。",
        "再看阶段：结合大运、流年和当前问题，把静态命局推进到具体时间窗口。",
        "最后落现实：分别给出事业、财务、关系、风险边界和后续追问方向。",
    ]
    if question != "综合命局咨询":
        steps[3] = "最后针对用户问题给结论：先回答能不能/要不要/怎么做，再说明风险边界和需要补充的行运材料。"
    return steps


def _bazi_targeted_reading(
    *,
    question: str,
    day_master: str,
    counts: dict[str, int],
    decision_hint: str,
) -> str:
    focus = _focus_text(question)
    analysis = analyze_question(question)
    lines = [
        f"本次问题聚焦：{focus}。",
        f"直接判断：{decision_hint}",
        f"命局阅读中心为{day_master or '日主'}；判断时要先看这个人如何处理自我驱动力、规则压力、资源分配和实际执行。",
    ]
    if "career" in analysis.get("focus_domains", []) or "事业" in focus:
        lines.append("事业层面：更适合看长期积累、专业输出、组织规则与执行节奏是否匹配；若环境只给短期刺激但不给稳定资源，消耗会变大。")
    if "wealth" in analysis.get("focus_domains", []) or "财务" in focus:
        lines.append("财务层面：重点不是一时收益，而是现金流、储备、风险上限和资源调度；适合做可追踪预算与阶段性复盘。")
    if "relationship" in analysis.get("focus_domains", []) or "关系" in focus:
        lines.append("关系层面：要注意边界、责任分配和沟通节奏；压力大时容易把外部事务带入关系，需要提前拆分问题。")
    if analysis.get("needs_timing"):
        lines.append("时间层面：当前命局报告只给结构判断；若要具体到年份、月份或转折点，需要叠加大运、流年或对应推运技法。")
    if analysis.get("needs_decision_support"):
        lines.append("决策层面：优先选择能长期累积能力、资源与信用的路径；对高杠杆、高消耗、边界不清的选项应提高门槛。")
    if len(lines) == 2:
        lines.append("综合层面：这张盘更适合从长期稳定、资源管理和行动节奏来规划，而不是用单一吉凶标签判断。")
    return "\n".join(lines)


def _bazi_decision_hint(*, question: str, day_master: str, counts: dict[str, int]) -> str:
    analysis = analyze_question(question)
    focus_domains = set(analysis.get("focus_domains") if isinstance(analysis.get("focus_domains"), list) else [])
    parts: list[str] = []
    if "career" in focus_domains or any(word in question for word in ["工作", "事业", "跳槽", "换工作", "职业"]):
        parts.append("换工作可以进入准备和筛选阶段，但不宜为了短期刺激仓促裸辞；更适合选择能长期积累专业、信用和资源的岗位")
    if "wealth" in focus_domains or any(word in question for word in ["财务", "投资", "钱", "收益", "风险"]):
        parts.append("财务上不建议高杠杆或激进投资；更适合把现金流、储备、止损线和复盘机制先建立起来")
    if analysis.get("needs_timing") or any(word in question for word in ["未来三年", "几年", "时间", "什么时候"]):
        parts.append("未来三年应按“先稳住资源与能力，再择机推进”的节奏处理，具体月份和年份需要再叠加大运流年")
    if analysis.get("needs_decision_support") or any(word in question for word in ["是否", "适合", "应该", "选择"]):
        parts.append("决策上优先选下行风险可控、边界清晰、可持续累积的方案")
    if not parts:
        parts.append(f"以{day_master or '日主'}为核心，先看长期稳定性、资源调度和执行节奏，再判断具体行动")
    return "；".join(parts) + "。"


def _extract_bazi_pillars(export_text: str) -> dict[str, str]:
    stems = "甲乙丙丁戊己庚辛壬癸"
    branches = "子丑寅卯辰巳午未申酉戌亥"
    result: dict[str, str] = {}
    for label in ["年柱", "月柱", "日柱", "时柱", "胎元", "命宫", "身宫"]:
        match = re.search(rf"{label}\s*[：:]\s*([{stems}][{branches}])", export_text)
        # v0.40 起 [四柱与三元] 是上游 GFM 表（BaZi.js:389-394「| 年柱 | 戊申 | 藏干 | …」），四主柱只有表格行。
        match = match or re.search(rf"\|\s*{label}\s*\|\s*([{stems}][{branches}])\s*\|", export_text)
        if match:
            result[label] = match.group(1)
    return result


def _day_master_text(day_pillar: str | None) -> str:
    if not day_pillar:
        return ""
    stem = day_pillar[0]
    element = {
        "甲": "阳木",
        "乙": "阴木",
        "丙": "阳火",
        "丁": "阴火",
        "戊": "阳土",
        "己": "阴土",
        "庚": "阳金",
        "辛": "阴金",
        "壬": "阳水",
        "癸": "阴水",
    }.get(stem, stem)
    return f"{stem}（{element}）"


def _bazi_element_counts(pillars: dict[str, str]) -> dict[str, int]:
    element_map = {
        "甲": "木",
        "乙": "木",
        "丙": "火",
        "丁": "火",
        "戊": "土",
        "己": "土",
        "庚": "金",
        "辛": "金",
        "壬": "水",
        "癸": "水",
        "子": "水",
        "丑": "土",
        "寅": "木",
        "卯": "木",
        "辰": "土",
        "巳": "火",
        "午": "火",
        "未": "土",
        "申": "金",
        "酉": "金",
        "戌": "土",
        "亥": "水",
    }
    counts = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
    for label in ["年柱", "月柱", "日柱", "时柱"]:
        for char in pillars.get(label, ""):
            element = element_map.get(char)
            if element:
                counts[element] += 1
    return counts


def _format_pillars(pillars: dict[str, str]) -> str:
    labels = ["年柱", "月柱", "日柱", "时柱"]
    return "，".join(f"{label}{pillars[label]}" for label in labels if pillars.get(label))


def _section_by_title(sections: list[dict[str, Any]], needle: str) -> dict[str, Any] | None:
    for section in sections:
        if needle in str(section.get("title") or ""):
            return section
    return None


def _bazi_starting_context(start_info: dict[str, Any] | None, input_normalized: dict[str, Any]) -> str:
    lines = _clean_lines(start_info.get("lines", []) if start_info else [], limit=10)
    if not lines and input_normalized:
        lines = [f"{key}: {value}" for key, value in input_normalized.items()]
    return "\n".join(
        [
            "起盘信息决定后面所有判断的边界。本报告已保留公历时间、时区、经纬度、真太阳时和农历信息，适合后续复核。",
            "如果出生时间或地点存在误差，优先复查时辰；八字中时柱对后半生议题、子女/晚年/执行方式等解释影响较大。",
            "本次关键起盘线索：" + ("；".join(lines[:6]) if lines else "未读取到详细起盘线索。"),
        ]
    )


def _bazi_day_master_reading(pillars: dict[str, str], day_master: str, counts: dict[str, int]) -> str:
    month = pillars.get("月柱", "")
    day = pillars.get("日柱", "")
    hour = pillars.get("时柱", "")
    return "\n".join(
        [
            f"日柱为{day or '未明'}，日主{day_master or '未明'}是整张盘的阅读中心。",
            f"月柱{month or '未明'}代表出生季节与外部环境，决定日主面对的压力、资源与规则感；时柱{hour or '未明'}则更偏向执行方式、后续发展和落地能力。",
            "从四柱结构看，判断重点不是单独说某一柱吉凶，而是观察日主如何在环境、资源、约束和行动之间取得平衡。",
            "如果后续加入大运流年，可以进一步判断哪些年份会放大资源、压力、财务或关系议题。",
        ]
    )


def _bazi_element_reading(counts: dict[str, int]) -> str:
    if not any(counts.values()):
        return "五行信息不足，建议回到原始八字输出补齐四柱与藏干后再判断。"
    sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    strongest = "、".join(name for name, count in sorted_counts if count == sorted_counts[0][1])
    weakest_count = sorted_counts[-1][1]
    weakest = "、".join(name for name, count in sorted_counts if count == weakest_count)
    return "\n".join(
        [
            "五行不是简单的多就好、少就坏，而是看它们是否形成可用的流动。",
            "明面干支计数：" + "，".join(f"{name}{count}" for name, count in counts.items()) + "。",
            f"相对突出的元素是{strongest}，通常表示这类主题更容易被感知、被动员，或在现实中更常成为主线。",
            f"相对需要留意的是{weakest}，它可能表现为需要后天补足的能力、节奏或外部支持。",
            "完整旺衰还要看月令、藏干、通根、合冲刑害与大运流年；本段先作为最终报告的阅读地图。",
        ]
    )


def _bazi_liunian_reading(direction_info: dict[str, Any] | None, *, question: str) -> str:
    lines = _section_lines(direction_info, limit=18)
    if not lines or lines == ["无"]:
        return "\n".join(
            [
                "当前八字导出没有提供可展开的大运/流年明细，因此本段只做方法说明，不强行编造年份判断。",
                "如果问题涉及未来几年、换工作、投资、婚恋或迁移，建议重新调用带大运流年输出的八字工具，或补充流年/大运表后再生成专项报告。",
                "在没有流年明细时，本报告只把命局结构作为长期倾向，具体年份与月份应保持开放。",
            ]
        )
    current = []
    upcoming = []
    for line in lines:
        if any(token in line for token in ["2026", "2027", "2028", "2029", "2030", "未来", "流年"]):
            upcoming.append(line)
        else:
            current.append(line)
    parts = [
        "大运与流年用于把静态命局推进到阶段判断：同一张命盘，在不同运限里会呈现不同的压力、机会和触发点。",
        "本次可读取的行运线索：" + "；".join(lines[:8]) + "。",
    ]
    if upcoming:
        parts.append("与未来阶段直接相关的线索：" + "；".join(upcoming[:8]) + "。这些年份更适合拿来细看事业节奏、财务风险和行动窗口。")
    if current:
        parts.append("背景运限线索：" + "；".join(current[:5]) + "。它们用于理解这个人长期面对的环境主题和资源调度方式。")
    if any(word in question for word in ["事业", "工作", "职业", "换工作", "跳槽"]):
        parts.append("事业判断上，流年不宜只看“有机会”或“有压力”，要看机会是否能沉淀为职位、能力、信用和可持续资源。")
    if any(word in question for word in ["财", "投资", "钱", "风险", "收益"]):
        parts.append("财务判断上，遇到流年触发时要先看现金流、储备和止损线；高杠杆或高波动选择需要更严格的现实验证。")
    if any(word in question for word in ["未来", "几年", "时间", "什么时候"]):
        parts.append("时间判断上，本段能给阶段顺序；若要精确到月份或事件点，还需要叠加更细的流月、流日或对应技法。")
    return "\n".join(parts)


def _section_lines(section: dict[str, Any] | None, *, limit: int) -> list[str]:
    if not section:
        return []
    lines = section.get("lines")
    if isinstance(lines, list) and lines:
        return _clean_lines(lines, limit=limit)
    body = str(section.get("body") or "").strip()
    if not body:
        return []
    return _clean_lines(body.splitlines(), limit=limit)


def _bazi_shensha_reading(gods_info: dict[str, Any] | None) -> str:
    lines = _clean_lines(gods_info.get("lines", []) if gods_info else [], limit=16)
    if not lines:
        return "神煞章节为空；本报告不强行扩展不存在的材料。"
    helpful = [line for line in lines if any(word in line for word in ["天德", "天乙", "贵人", "国印", "词馆", "禄"])]
    pressure = [line for line in lines if any(word in line for word in ["岁破", "月破", "大耗", "血", "吊客", "五鬼", "官符", "丧门"])]
    parts = [
        "神煞适合用作提示，不适合单独当成绝对吉凶。本报告把它们翻译成“可观察倾向”。",
    ]
    if helpful:
        parts.append("支持性线索：" + "；".join(helpful[:5]) + "。这些更适合理解为学习、贵人、资质、制度资源或被看见的机会。")
    if pressure:
        parts.append("压力性线索：" + "；".join(pressure[:6]) + "。这些更适合提醒风险管理、情绪消耗、规则冲突或突发成本。")
    parts.append("实际使用时，应把神煞放回四柱和行运中验证，避免只凭名字下结论。")
    return "\n".join(parts)


def _bazi_life_advice(day_master: str, counts: dict[str, int]) -> str:
    return "\n".join(
        [
            f"事业上，{day_master or '日主'}更需要找到能长期积累、能稳定输出的环境；不要只追求短期刺激，要看资源、规则和执行节奏是否匹配。",
            "关系上，建议把边界、沟通节奏和现实责任说清楚；如果盘面压力元素被触发，容易把外部压力带入亲密关系或合作关系。",
            "财务上，适合建立可追踪的预算、储备与风险上限；命盘提示可用来观察资源流动，但投资决策仍要回到事实、现金流和风险控制。",
            "身心节奏上，避免长期把自己放在高压和高消耗环境里；越是需要承担责任，越要保留恢复、学习和调整的空间。",
        ]
    )


def _clean_lines(lines: list[Any], *, limit: int) -> list[str]:
    output: list[str] = []
    for line in lines:
        text = str(line or "").strip()
        if not text:
            continue
        output.append(text)
        if len(output) >= limit:
            break
    return output


def _evidence_from_sections(sections: list[dict[str, Any]], *, limit: int) -> list[str]:
    evidence: list[str] = []
    for section in sections:
        title = str(section.get("title") or "导出章节")
        lines = _clean_lines(section.get("lines") if isinstance(section.get("lines"), list) else [], limit=3)
        if not lines:
            body = str(section.get("body") or "").strip()
            lines = [item.strip() for item in body.splitlines() if item.strip()][:3]
        for line in lines:
            evidence.append(f"{title}: {line}")
            if len(evidence) >= limit:
                return evidence
    return evidence
