"""广告层的共享字段词典（MCP-11）：一个字段名一句描述，所有工具共用。

🔴 审查时全量面有 485 个广告出去的属性没有描述（229 个字段名：lateZiHourUseNextDay ×37、after23NewDay ×35、
gpsLat / gpsLon ×26 …）。一个照字面办事的模型看到一个没描述的键，只能猜。规则：
- 广告出去的每个属性都有描述：先用工具自己的（模型 Field 描述 / 域核心 CORE_DOC），没有就查本词典；
- 词典里也没有的技法旋钮**不广告**（照样按名接受，计入「还有 N 个高级旋钮」，全表在 horosa_agent_guidance）——
  不描述就不广告，比广告一个只能猜的键好；
- 门面工具的字段全部在词典里（门面就那么几个键，精简面下它们就是全部工具）。
`scripts/verify_mcp_list_budget.py` 守「广告层零无描述属性」。描述要短：每一句乘以出现它的工具数进 tools/list 预算。
词条来源：域核心与 tool_run 公共字段沿用原句；结果敏感设置取 horosa_agent_guidance 追问用户的那一问；其余按模型与
references 文档写（不确定含义的不写——宁可不广告）。
"""
from __future__ import annotations

from horosa_skill.surfaces.mcp_requests import tool_run_field_docs

# 手写词条：门面字段 + 高频 / 结果敏感的技法字段。中文短句，与 CORE_DOC 同一口径（只写键名说不出的东西）。
_CURATED: dict[str, str] = {
    # 晚子时口径（references/late-zi.md）——结果敏感，闸门会追问
    "after23NewDay": "23:00 起换日 1/0",
    "lateZiHourUseNextDay": "晚子时按次日日干 1/0",
    "request": "整包载荷（对象或 JSON 串）",
    "options": "技法选项对象（键见 horosa_agent_guidance）",
    "isDiurnal": "true=昼贵 false=夜贵；不传=按时间自动",
    # 追问句截出来不像描述、或同名字段在别的工具里另有含义的，在这里写定（一个名字一句）
    "domain": "知识域（user = 你的笔记）",
    "technique": "技法名",
    "category": "类别（问事类别 / 知识类目）",
    "year": "年份",
    "school": "流派",
    "method": "取法",
    "sex": "性别",
    "selected_sections": "只解析这些段",
    "indiaAyanamsa": "恒星黄道岁差制",
    "q": "检索词",
    "location": "地点",
    "pdMethod": "主限算法",
    "pdTimeKey": "主限时间钥（弧度→年）",
    # 门面：记忆库
    "run_id": "存档 id（horosa_memory_query 可查）",
    "tool": "按技法名过滤",
    "entity": "按当事人 / 对象名过滤",
    "text": "全文关键词",
    "artifact_kind": "按产物类型过滤",
    "after": "起始时间（ISO）",
    "before": "截止时间（ISO）",
    "limit": "条数上限",
    "offset": "跳过前 N 条（翻页）",
    "include_payload": "附带完整载荷",
    "user_question": "用户原问题",
    "ai_answer": "AI 的解读全文",
    "ai_answer_structured": "结构化解读（可选）",
    "answer_meta": "解读元数据（可选）",
    # 门面：报告
    "tool_name": "技法名（chart / horosa_astro_chart 均可）；全表：horosa://catalog/techniques",
    "format": "输出格式",
    "style": "analysis=AI 解盘报告 chart=完整排盘",
    "language": "报告语言",
    "title": "报告标题",
    "ai_report": "按 horosa_report_template 填的报告正文",
    "ai_answer_text": "AI 的解读全文（写回存档）",
    "include_raw_json": "附带原始 JSON",
    "group_id": "会话组 id（与 run_id 二选一）",
    "include_sections": "列出各技法的产出段",
    "output_path": "须在报告输出目录内",
    "payload": "技法入参（同该技法工具）",
    # 门面：指引 / 知识 / 导出
    "intent": "用户意图（自然语言）",
    "include_all": "返回全部工具的指引索引",
    "key": "条目键",
    "aspect_degree": "相位度数（astro 相位条目）",
    "object_a": "相位一方",
    "object_b": "相位另一方",
    "jiang_name": "天将名（六壬）",
    "tian_branch": "天盘支（六壬）",
    "di_branch": "地盘支（六壬）",
    "content": "星阙导出的文本快照",
    "planet_info": "星体信息显示设置",
    "astro_meaning": "释义显示设置",
    "query": "检索词",
    # 技法：高频
    "orb": "容许度（度）",
    "seed": "随机种子（同种子可复现）",
    "targetTime": "目标时刻",
}


QUESTION_DOC_LIMIT = 16  # 字符：追问句截成广告层短描述（每句乘以出现它的工具数进 tools/list 预算）


def _short(question: str) -> str:
    """追问句 → 短描述：取问号 / 括注之前；仍超长就退到上限内最后一个逗号 / 顿号 / 空格，不切在词中间。"""
    text = question.strip().split("？")[0].split("（")[0].strip()
    if len(text) <= QUESTION_DOC_LIMIT:
        return text
    cut = text[:QUESTION_DOC_LIMIT]
    best = max(cut.rfind(ch) for ch in "，、 ")
    return (cut[:best] if best > 0 else cut).rstrip("，、 ")


def field_docs() -> dict[str, str]:
    """字段名 → 广告层描述（一个名字一句）。CORE_DOC 与 tool_run 公共字段优先，其次本词典，最后取指引里追问用户的那一问。"""
    from horosa_skill.agent_guidance import tool_table
    from horosa_skill.surfaces.mcp_schema import CORE_DOC

    questions: dict[str, str] = {}

    def scan(obj: object) -> None:
        if isinstance(obj, dict):
            field, question = obj.get("field"), obj.get("question")
            if isinstance(field, str) and isinstance(question, str) and question.strip():
                questions.setdefault(field, _short(question))
            for value in obj.values():
                scan(value)
        elif isinstance(obj, (list, tuple)):
            for value in obj:
                scan(value)

    for name in sorted(vars(tool_table)):
        if not name.startswith("__"):
            scan(getattr(tool_table, name))
    return {**questions, **_CURATED, **tool_run_field_docs(), **CORE_DOC}
