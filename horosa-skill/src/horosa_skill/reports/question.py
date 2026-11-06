"""用户问题的拆解与针对性解盘要求：模板要它告诉 AI 怎么答，文档要它写进机器章节，默认解读要它定口吻。"""

from __future__ import annotations

from typing import Any


def analyze_question(user_question: str) -> dict[str, Any]:
    question = user_question.strip()
    focus_catalog = {
        "relationship": ["感情", "关系", "婚姻", "伴侣", "复合", "桃花"],
        "career": ["事业", "工作", "职业", "升职", "项目", "合作"],
        "wealth": ["财", "钱", "收入", "投资", "生意", "盈利"],
        "timing": ["什么时候", "何时", "多久", "时间", "时间窗口", "阶段", "节点", "月份", "年份", "未来", "接下来"],
        "decision": ["是否", "能不能", "要不要", "可不可以", "适不适合", "选择", "决策", "建议", "行动", "取舍"],
        "health": ["健康", "身体", "疾病", "恢复"],
        "study": ["考试", "学习", "论文", "学校", "申请"],
        "relocation": ["搬家", "迁移", "出国", "旅行", "远行"],
    }
    matched_focus = [
        domain
        for domain, keywords in focus_catalog.items()
        if any(keyword in question for keyword in keywords)
    ]
    return {
        "schema": "horosa.skill.report.question_analysis.v1",
        "raw_question": question,
        "has_question": bool(question),
        "focus_domains": matched_focus or (["general_reading"] if question else []),
        "primary_focus": (matched_focus or (["general_reading"] if question else []))[0] if question else None,
        "keywords_detected": [
            keyword
            for keywords in focus_catalog.values()
            for keyword in keywords
            if keyword in question
        ],
        "needs_prediction": any(keyword in question for keyword in ["未来", "接下来", "走势", "会不会", "能否", "是否"]),
        "needs_timing": any(keyword in question for keyword in ["什么时候", "何时", "多久", "时间", "时间窗口", "阶段", "节点", "月份", "年份"]),
        "needs_decision_support": any(keyword in question for keyword in ["是否", "能不能", "要不要", "适不适合", "选择", "决策", "建议", "行动", "取舍"]),
        "recommended_response_style": "answer_first_then_evidence",
    }


def build_targeted_contract(
    *,
    user_question: str,
    question_analysis: dict[str, Any],
    coverage: dict[str, Any],
) -> dict[str, Any]:
    targeted_requirements = _targeted_answer_requirements(question_analysis)
    return {
        "schema": "horosa.skill.report.targeted_analysis.v1",
        "user_question": user_question,
        "question_analysis": question_analysis,
        "answer_priority": "directly_answer_user_question_first",
        "answer_plan": [
            "先用 direct_answer 用一句话回答用户核心问题。",
            "再用 executive_summary 给出 3-5 条总览结论。",
            "逐项解释 must_explain_sections 中的所有星阙导出章节。",
            "每个关键判断都绑定 source_section_title、source_line、字段名或原始导出线索。",
            "最后给出 recommendations、limitations 和必要的 follow_up_questions。",
        ],
        "targeted_answer_requirements": targeted_requirements,
        "required_ai_fields": [
            "analysis_focus",
            "question_analysis",
            "answer_plan",
            "direct_answer",
            "executive_summary",
            "analysis_sections",
            "recommendations",
            "limitations",
            "evidence",
        ],
        "section_policy": "Each analysis section should map to a source export section when possible.",
        "evidence_policy": "Every important conclusion should cite a source_section_title, source_line, field name, or original export clue.",
        "memory_policy": "The final report artifact is stored in Horosa memory and can be retrieved later for comparison or experience improvement.",
        "dependency_hallucination_policy": "Never claim that Horosa Skill requires MongoDB, port 7897, Xingque Desktop, or an external database for Liureng/Qimen/Sanshi output. If a field is missing, report it as a local tool/result issue with the run context.",
        "must_explain_sections": coverage.get("must_explain_sections", []),
    }


def _targeted_answer_requirements(question_analysis: dict[str, Any]) -> list[dict[str, Any]]:
    focus_domains = question_analysis.get("focus_domains") if isinstance(question_analysis.get("focus_domains"), list) else []
    requirements: list[dict[str, Any]] = [
        {
            "id": "direct_answer",
            "label": "直接回答",
            "instruction": "先给出一句明确结论，避免只复述盘面。",
            "required": True,
        },
        {
            "id": "evidence_linking",
            "label": "证据绑定",
            "instruction": "每个关键判断都要绑定导出章节、字段或原文线索。",
            "required": True,
        },
    ]
    focus_instructions = {
        "career": ("事业/工作", "必须说明事业、工作、项目或合作层面的具体含义。"),
        "wealth": ("财务/收益", "必须说明收入、投资、生意或资源流动层面的具体含义。"),
        "relationship": ("关系/感情", "必须说明关系状态、互动模式或感情决策层面的具体含义。"),
        "health": ("健康/身体", "必须只做趋势与注意事项提示，并保留非医疗诊断限制。"),
        "study": ("学习/考试", "必须说明学习、考试、申请或研究推进层面的具体含义。"),
        "relocation": ("迁移/远行", "必须说明出行、搬迁、远方事务或环境变化层面的具体含义。"),
    }
    for domain, (label, instruction) in focus_instructions.items():
        if domain in focus_domains:
            requirements.append({"id": f"focus_{domain}", "label": label, "instruction": instruction, "required": True})
    if question_analysis.get("needs_timing"):
        requirements.append(
            {
                "id": "timing_window",
                "label": "时间窗口",
                "instruction": "必须给出时间窗口、阶段顺序或明确说明无法从当前材料判断时间。",
                "required": True,
            }
        )
    if question_analysis.get("needs_decision_support"):
        requirements.append(
            {
                "id": "decision_support",
                "label": "决策建议",
                "instruction": "必须给出可执行选项、风险点和建议优先级。",
                "required": True,
            }
        )
    if not focus_domains or focus_domains == ["general_reading"]:
        requirements.append(
            {
                "id": "general_synthesis",
                "label": "综合解盘",
                "instruction": "按盘面重点提炼核心主题、机会、风险和下一步可追问方向。",
                "required": True,
            }
        )
    return requirements


def format_targeting(contract: dict[str, Any]) -> str:
    question_analysis = contract.get("question_analysis") if isinstance(contract.get("question_analysis"), dict) else {}
    focus_domains = question_analysis.get("focus_domains") if isinstance(question_analysis.get("focus_domains"), list) else []
    targeted_requirements = contract.get("targeted_answer_requirements") if isinstance(contract.get("targeted_answer_requirements"), list) else []
    return "\n".join(
        [
            f"- 用户问题：{contract.get('user_question') or '无'}",
            f"- 问题焦点：{'、'.join(str(item) for item in focus_domains) if focus_domains else '未指定'}",
            f"- 需要时间判断：{question_analysis.get('needs_timing')}",
            f"- 需要决策建议：{question_analysis.get('needs_decision_support')}",
            f"- 回答优先级：{contract.get('answer_priority')}",
            f"- 章节策略：{contract.get('section_policy')}",
            f"- 证据策略：{contract.get('evidence_policy')}",
            f"- 存储策略：{contract.get('memory_policy')}",
            "- 定向要求：" + ("；".join(str(item.get("label") or item.get("id")) for item in targeted_requirements if isinstance(item, dict)) if targeted_requirements else "无"),
        ]
    )


def format_question_analysis(question_analysis: dict[str, Any]) -> str:
    focus_domains = question_analysis.get("focus_domains") if isinstance(question_analysis.get("focus_domains"), list) else []
    return "\n".join(
        [
            f"- 原始问题：{question_analysis.get('raw_question') or '无'}",
            f"- 有明确问题：{question_analysis.get('has_question')}",
            f"- 关注领域：{'、'.join(str(item) for item in focus_domains) if focus_domains else '无'}",
            f"- 需要趋势判断：{question_analysis.get('needs_prediction')}",
            f"- 需要时间判断：{question_analysis.get('needs_timing')}",
            f"- 需要决策支持：{question_analysis.get('needs_decision_support')}",
            f"- 推荐回答方式：{question_analysis.get('recommended_response_style')}",
        ]
    )
