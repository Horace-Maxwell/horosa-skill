"""报告的索引：大纲、纯文本、检索键。它们都从最终章节算出来，所以要等所有章节定稿之后才建。"""

from __future__ import annotations

from typing import Any


def index_checks(*, sections: list[Any], run: dict[str, Any], source: dict[str, Any]) -> dict[str, bool]:
    """交付清单里关于索引的三项。清单的正文本身要进索引，等不到索引建完，所以从输入判断：大纲与纯文本每章一条，检索键至少有 run_id / 技法名。

    `test_index_checks_agree_with_the_finished_index` 拿成品核对。"""
    has_sections = any(isinstance(section, dict) for section in sections)
    has_identity = any(str(value or "").strip() for value in (run.get("run_id"), source.get("tool_name"), source.get("technique"), source.get("technique_label")))
    return {
        "has_content_outline": has_sections,
        "has_plain_text": has_sections,
        "has_search_index": has_sections and has_identity,
    }


def build_content_outline(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            "id": section.get("id"),
            "title": section.get("title"),
            "body_chars": len(str(section.get("body") or "")),
            "has_items": bool(section.get("items")),
        }
        for index, section in enumerate(sections, start=1)
        if isinstance(section, dict)
    ]


def build_plain_text(*, title: str, generated_at: str, sections: list[dict[str, Any]]) -> str:
    parts = [
        f"# {title}",
        f"生成时间：{generated_at}",
        "",
        "## 目录",
    ]
    for index, section in enumerate(sections, start=1):
        if isinstance(section, dict):
            parts.append(f"{index}. {section.get('title') or section.get('id') or '章节'}")
    for index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            continue
        title_text = section.get("title") or section.get("id") or f"章节 {index}"
        body = str(section.get("body") or "无")
        parts.extend(["", f"## {index}. {title_text}", body])
    return "\n".join(parts).strip() + "\n"


def build_search_index(
    *,
    run: dict[str, Any],
    source: dict[str, Any],
    user_question: str,
    question_analysis: dict[str, Any],
    targeted_contract: dict[str, Any],
    export_sections: list[dict[str, Any]],
    ai_report: dict[str, Any],
    provenance: dict[str, Any],
    plain_text: str,
) -> dict[str, Any]:
    section_titles = [str(section.get("title")) for section in export_sections if section.get("title")]
    ai_sections = ai_report.get("analysis_sections") if isinstance(ai_report.get("analysis_sections"), list) else []
    ai_titles = [
        str(section.get("title") or section.get("source_section_title"))
        for section in ai_sections
        if isinstance(section, dict) and (section.get("title") or section.get("source_section_title"))
    ]
    recommendations = [str(item) for item in ai_report.get("recommendations", [])] if isinstance(ai_report.get("recommendations"), list) else []
    evidence = [str(item) for item in ai_report.get("evidence", [])] if isinstance(ai_report.get("evidence"), list) else []
    focus_domains = question_analysis.get("focus_domains") if isinstance(question_analysis.get("focus_domains"), list) else []
    detected_keywords = question_analysis.get("keywords_detected") if isinstance(question_analysis.get("keywords_detected"), list) else []
    targeted_requirements = targeted_contract.get("targeted_answer_requirements") if isinstance(targeted_contract.get("targeted_answer_requirements"), list) else []
    requirement_terms = [
        str(item.get("label") or item.get("id") or item.get("instruction") or "")
        for item in targeted_requirements
        if isinstance(item, dict)
    ]
    key_phrases = _extract_consultation_key_phrases(
        "\n".join(
            str(item or "")
            for item in [
                user_question,
                ai_report.get("analysis_focus"),
                ai_report.get("direct_answer"),
                ai_report.get("executive_summary"),
                ai_report.get("answer_text"),
                plain_text,
            ]
        )
    )
    keywords = _dedupe_strings(
        [
            run.get("run_id"),
            source.get("tool_name"),
            source.get("technique"),
            source.get("technique_label"),
            user_question,
            ai_report.get("analysis_focus"),
            ai_report.get("direct_answer"),
            ai_report.get("executive_summary"),
            ai_report.get("answer_text"),
            provenance.get("bundle_version"),
            provenance.get("source_domain"),
            *focus_domains,
            *detected_keywords,
            *key_phrases,
            *requirement_terms,
            *section_titles,
            *ai_titles,
            *recommendations,
            *evidence,
        ]
    )
    return {
        "schema": "horosa.skill.report.search_index.v1",
        "run_id": run.get("run_id"),
        "tool_name": source.get("tool_name"),
        "technique": source.get("technique"),
        "technique_label": source.get("technique_label"),
        "user_question": user_question,
        "focus_domains": focus_domains,
        "section_titles": section_titles,
        "ai_section_titles": ai_titles,
        "recommendations": recommendations,
        "evidence": evidence,
        "keywords": keywords,
        "plain_text_chars": len(plain_text),
        "search_text": "\n".join(keywords + [plain_text]),
    }


def _extract_consultation_key_phrases(text: str) -> list[str]:
    phrase_catalog = [
        "换工作",
        "跳槽",
        "裸辞",
        "高杠杆",
        "激进投资",
        "投资风险",
        "财务风险",
        "事业策略",
        "行动窗口",
        "时间窗口",
        "决策风险",
        "事业走势",
        "感情关系",
        "婚姻关系",
        "复合",
        "桃花",
        "健康风险",
        "考试",
        "搬家",
        "迁移",
        "出国",
        "合作",
        "创业",
        "升职",
        "offer",
    ]
    return [phrase for phrase in phrase_catalog if phrase and phrase in text]


def _dedupe_strings(values: list[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output
