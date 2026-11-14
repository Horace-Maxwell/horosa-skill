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


# 六条规则（审计 O-23：以前 15.4 KB——正文再给一遍、question_analysis 两遍、必讲段清单三遍，还写着「逐项解释全部章节」，
# 与 reports.md「有针对性的回答可以跳过段」相反）。
TEMPLATE_RULES = [
    "先直接回答 user_question（能不能、该不该、风险在哪、整体主题），再给盘面依据、推理、风险边界与下一步建议。",
    "只依据盘面正文：source_context.export_text；不在手里时按 source_context.text_with 那次调用取。不手算、不编造盘面没有的东西；"
    "空字段或缺失段不是缺依赖——不要说需要 MongoDB、桌面端服务或联网。",
    "关键判断句末写段号，如「……日主偏弱 [E3]」（段号 = source_export_sections[].cite_id，报告里每段标题前印的就是它）；"
    "引用用户自备笔记写「（用户笔记《标题》第几行）」。没有依据的话只能写成背景或不确定处。",
    "有针对性：与问题无关的段可以不讲；analysis_sections 只写用得上的段，每项带 cite_id。",
    "executive_summary 是报告最前面的结论摘要：不超过四段、每段至少一个段号；分节细读写进 analysis_sections。",
    "limitations 写不确定处：出生时间误差会改变什么、流派口径不同处、盘面没覆盖的问题——照实写，不要凑。",
]


def build_template(
    *,
    run: dict[str, Any],
    source_artifact: dict[str, Any],
    language: str,
    include_text: bool = True,
) -> dict[str, Any]:
    """`include_text=False`（horosa_report_template 缺省）不再附全文，只给取全文的那次调用。"""
    payload = read_payload(source_artifact)
    source = read_source_meta(run=run, source_artifact=source_artifact, payload=payload)
    export_format = read_export_format(payload)
    data = payload.get("data") if isinstance(payload, dict) else {}
    raw_export_snapshot = data.get("export_snapshot") if isinstance(data, dict) else {}
    export_snapshot = raw_export_snapshot if isinstance(raw_export_snapshot, dict) else {}
    export_sections = read_export_sections(export_format, include_body=True)
    export_text = read_export_text(export_snapshot=export_snapshot, export_format=export_format, payload=payload)
    user_question = read_user_question(run)
    question_analysis = analyze_question(user_question)
    targeted_contract = build_targeted_contract(
        user_question=user_question,
        question_analysis=question_analysis,
        coverage=build_coverage_contract(export_sections=export_sections, export_text=export_text, source=source),
    )
    text = {"export_text": export_text} if include_text else {
        "text_with": f'horosa_memory_show(run_id="{run["run_id"]}", response_tool="{source["tool_name"]}")',
        "export_text_chars": len(export_text),
    }
    return {
        "schema": REPORT_TEMPLATE_SCHEMA,
        "run_id": run["run_id"],
        "tool_name": source["tool_name"],
        "technique": source["technique"],
        "language": language,
        "user_question": user_question,
        "focus": {key: question_analysis.get(key) for key in ("focus_domains", "needs_timing", "needs_decision_support")
                  if question_analysis.get(key) not in (None, [], "")},
        "ai_instructions": list(TEMPLATE_RULES),
        "source_context": {
            "input_normalized": payload.get("input_normalized") if isinstance(payload.get("input_normalized"), dict) else {},
            "summary": payload.get("summary") if isinstance(payload.get("summary"), list) else [],
            **text,
            "provenance": read_provenance(export_snapshot=export_snapshot, export_format=export_format, source=source),
        },
        "source_export_sections": [
            {"cite_id": section.get("cite_id"), "title": section.get("title"), "chars": len(str(section.get("body") or ""))}
            for section in export_sections
        ],
        "ai_fillable": {
            "analysis_focus": user_question,
            "answer_plan": targeted_contract["answer_plan"],
            "targeted_answer_requirements": targeted_contract["targeted_answer_requirements"],
            "direct_answer": "",
            "executive_summary": "",
            "answer_text": "",
            "analysis_sections": [],   # 每项 {title, cite_id, body, evidence_lines, relevance_to_question, confidence}
            "recommendations": [],
            "limitations": [],
            "evidence": [],
            "follow_up_questions": [],
        },
        "source": source,
    }
