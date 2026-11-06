"""给 AI 的报告模板：缺解读时回 `analysis_required`，让接入的 AI 照着模板填 `ai_report`。"""

from __future__ import annotations

from typing import Any

from horosa_skill.reports.gates import build_coverage_contract
from horosa_skill.reports.question import analyze_question, build_targeted_contract
from horosa_skill.reports.source import (
    read_export_format,
    read_export_sections,
    read_export_text,
    read_payload,
    read_provenance,
    read_source_meta,
    read_user_question,
)

REPORT_TEMPLATE_SCHEMA = "horosa.skill.report.template.v1"

REQUIRED_SECTIONS = [
    "executive_summary",
    "input_overview",
    "technique_result",
    "ai_analysis",
    "recommendations",
    "provenance",
]


def build_template(
    *,
    run: dict[str, Any],
    source_artifact: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    payload = read_payload(source_artifact)
    source = read_source_meta(run=run, source_artifact=source_artifact, payload=payload)
    export_format = read_export_format(payload)
    data = payload.get("data") if isinstance(payload, dict) else {}
    raw_export_snapshot = data.get("export_snapshot") if isinstance(data, dict) else {}
    export_snapshot = raw_export_snapshot if isinstance(raw_export_snapshot, dict) else {}
    export_sections = read_export_sections(export_format, include_body=True)
    coverage_contract = build_coverage_contract(
        export_sections=export_sections,
        export_text=read_export_text(export_snapshot=export_snapshot, export_format=export_format, payload=payload),
        source=source,
    )
    user_question = read_user_question(run)
    question_analysis = analyze_question(user_question)
    targeted_contract = build_targeted_contract(
        user_question=user_question,
        question_analysis=question_analysis,
        coverage=coverage_contract,
    )
    conversation_brief = _conversation_brief(
        source=source,
        user_question=user_question,
        question_analysis=question_analysis,
        coverage=coverage_contract,
        export_sections=export_sections,
        input_normalized=payload.get("input_normalized") if isinstance(payload.get("input_normalized"), dict) else {},
    )
    return {
        "schema": REPORT_TEMPLATE_SCHEMA,
        "run_id": run["run_id"],
        "tool_name": source["tool_name"],
        "technique": source["technique"],
        "language": language,
        "user_question": user_question,
        "question_analysis": question_analysis,
        "required_sections": list(REQUIRED_SECTIONS),
        "ai_instructions": [
            "你是在任意 AI 对话窗口里为用户解盘：先读 source_context 的真实盘面结果，再回答 user_question。",
            "输出应像一次完整咨询后的结论，而不是字段解释、技术日志或模板说明。",
            "必须先直接回答用户问的事情，再说明盘面依据、推理步骤、风险边界和下一步建议。",
            "每个关键判断都尽量绑定 evidence 或 source_section_title；不要脱离盘面编造结论。",
            "引用盘面时在句末写段号，如「……日主偏弱 [E3]」：段号见 source_export_sections[].cite_id，报告里每个盘面段"
            "标题前印的就是它（PDF 里可点击跳转）。引用用户自备笔记写「（用户笔记《标题》第几行）」。没有依据的句子只能写成背景或不确定处。",
            "executive_summary 是放在报告最前面的结论摘要：不超过四段、每段至少一个段号；分节细读写进 analysis_sections。",
            "limitations 写「不确定处」：出生时间误差会改变什么、流派口径不同处、盘面没覆盖的问题——照实写，不要凑。",
        ],
        "conversation_brief": conversation_brief,
        "coverage_contract": coverage_contract,
        "targeted_analysis_contract": targeted_contract,
        "source_context": {
            "input_normalized": payload.get("input_normalized") if isinstance(payload.get("input_normalized"), dict) else {},
            "summary": payload.get("summary") if isinstance(payload.get("summary"), list) else [],
            "export_text": read_export_text(export_snapshot=export_snapshot, export_format=export_format, payload=payload),
            "export_sections": export_sections,
            "provenance": read_provenance(export_snapshot=export_snapshot, export_format=export_format, source=source),
        },
        "source_export_sections": [
            {key: value for key, value in section.items() if key not in {"body", "lines"}}
            for section in export_sections
        ],
        "ai_fillable": {
            "analysis_focus": user_question,
            "question_analysis": question_analysis,
            "answer_plan": targeted_contract["answer_plan"],
            "targeted_answer_requirements": targeted_contract["targeted_answer_requirements"],
            "direct_answer": "",
            "executive_summary": "",
            "answer_text": "",
            "analysis_sections": [
                {
                    "title": section["title"],
                    "cite_id": section["cite_id"],
                    "body": "",
                    "evidence_lines": [],
                    "relevance_to_question": "",
                    "confidence": "medium",
                }
                for section in export_sections
            ],
            "recommendations": [],
            "limitations": [],
            "evidence": [],
            "follow_up_questions": [],
        },
        "source": source,
    }


def _conversation_brief(
    *,
    source: dict[str, Any],
    user_question: str,
    question_analysis: dict[str, Any],
    coverage: dict[str, Any],
    export_sections: list[dict[str, Any]],
    input_normalized: dict[str, Any],
) -> dict[str, Any]:
    section_titles = [str(section.get("title")) for section in export_sections if section.get("title")]
    return {
        "schema": "horosa.skill.report.conversation_brief.v1",
        "role": "你是接入 Horosa Skill 的 AI 解盘助手，正在根据本地离线算法算出的真实盘面回答用户。",
        "user_context": {
            "question": user_question or "用户没有给出明确问题，请做整体综合解盘。",
            "input_normalized": input_normalized,
            "focus_domains": question_analysis.get("focus_domains", []),
            "needs_timing": question_analysis.get("needs_timing"),
            "needs_decision_support": question_analysis.get("needs_decision_support"),
        },
        "plate_context": {
            "tool_name": source.get("tool_name"),
            "technique": source.get("technique"),
            "technique_label": source.get("technique_label"),
            "source_sections": section_titles,
            "must_read": [
                "source_context.export_text",
                "source_context.export_sections",
                "source_context.input_normalized",
                "targeted_analysis_contract",
            ],
        },
        "interpretation_method": [
            "先用一句话回答用户的问题，明确能不能、该不该、风险在哪里或整体主题是什么。",
            "再说明你看了哪些盘面信息：起盘信息、核心结构、关键章节、特殊征象、时间/阶段线索。",
            "把盘面线索翻译成人能听懂的现实含义，不要只重复术语。",
            "如果问题涉及时间窗口、选择、风险或财务，必须给出阶段判断和保守/进取边界。",
            "如果盘面材料不足以判断，直接说明不足，不要硬编。",
            "不要把空字段或缺失章节解释成需要 MongoDB、7897 端口、星阙桌面应用、远程数据库或外部服务；Horosa Skill 的公开能力以本地离线 runtime 为准。",
        ],
        "output_style": [
            "像在 AI 对话窗口中完成一次认真解盘后给出的最终回复。",
            "中文、自然、有结论、有依据、有行动建议。",
            "不要输出代码、JSON 字段名、schema、run_id、内部路径或机器日志。",
            "不要说“待 AI 分析”“模板要求”“根据框架应当”，要直接给用户可读结论。",
            "如果工具返回错误或材料不足，只说明本次本地工具返回不足，并建议重新运行 doctor/openclaw-check 或补齐输入；不要臆造 MongoDB/桌面端依赖。",
        ],
        "final_ai_report_contract": {
            "answer_text": "完整对话式解盘正文，适合作为报告主体。",
            "direct_answer": "一句话直接结论。",
            "executive_summary": "3-6 条摘要。",
            "analysis_sections": "按问题和盘面分节解释，每节绑定证据线索。",
            "recommendations": "可执行建议。",
            "limitations": "限制、风险和不可判断处。",
            "evidence": "关键判断对应的盘面章节或原文线索。",
        },
        "coverage_required": coverage.get("must_explain_sections", []),
    }
