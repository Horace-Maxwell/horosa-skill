"""门面工具输入：dispatch / hecan、导出与知识库、玄史、agent 指引、记忆、报告、技法依据报告。"""
from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from horosa_skill.schemas.tools.astro import RelativePartyInput
from horosa_skill.schemas.tools.base import BirthInput, FlexibleModel
from horosa_skill.schemas.tools.cn_divination import LiuRengGodsInput
from horosa_skill.schemas.tools.cn_mingli import (
    BaZiBirthInput,
    NongliTimeInput,
    ZiWeiBirthInput,
)


class PlanetInfoSettingInput(FlexibleModel):
    showHouse: int | bool | None = 1
    showRuler: int | bool | None = 1


class AstroMeaningSettingInput(FlexibleModel):
    enabled: int | bool | None = 0


class XuanshiInput(FlexibleModel):
    # 玄史（中国玄学史知识库）：runtime 自带两个只读 SQLite bundle（玄学事件 7900+ / 天象记录 27000+ /
    # 地名 / 人物图 2200+ 节点），由 python chart 服务的 /xuanshi/* 只读端点提供检索与结构视图。
    # 纯检索工具，无结果敏感设置。action 决定查哪个面：
    #   search（默认）= q 全文检索玄学事件；events/event = 多维过滤列表 / 单事件全档
    #   （原文+白话+解读+流程+结局+引证）；celestial/celestial_event = 天象记录；
    #   figures/figure = 人物；dynasties/dynasty = 朝代；techniques/technique = 术数门类；
    #   terms/term/term_profile = 天象名词；timeline = 宏观时间线（带 macro 下钻）；
    #   map = 地理点位；graph = 人物共现网络；stories/story = 专题故事；channels = 频道；
    #   daily = 今日推送；summary = 全库统计；microchronology / decade_omens / facets /
    #   events_meta = 编年细化 / 十年灾异 / 分面计数 / 列表页元数据。
    action: str | None = "search"
    q: str | None = Field(default=None, description="全文检索词（事件/人物/术数名皆可）。")
    id: str | None = Field(default=None, description="详情键：事件 id（XTS-027）/ 编辑层 slug（fig-laozi）。")
    tradition: str | None = Field(default=None, description="传统过滤：正史 / 野载。")
    dynasty: str | None = Field(default=None, description="朝代过滤（如 唐 / 南北朝 / 志怪笔记）。")
    technique: str | None = Field(default=None, description="术数门类过滤（如 占星 / 相术 / 卜筮）。")
    history: str | None = Field(default=None, description="史书过滤（如 新唐书 / 晋书）。")
    evidence: str | None = Field(default=None, description="证据等级过滤。")
    omen: str | None = Field(default=None, description="天象类（日食/彗孛/流星…）：celestial/term_profile/microchronology。")
    source: str | None = Field(default=None, description="天象出处过滤（celestial 用）。")
    year_from: int | None = Field(default=None, description="天象起始公历年（可负=公元前）。")
    year_to: int | None = Field(default=None, description="天象结束公历年。")
    macro: str | None = Field(default=None, description="timeline 宏观段下钻键。")
    period: str | None = Field(default=None, description="map 的时期过滤。")
    date_key: str | None = Field(default=None, description="daily 的日期键（YYYY-MM-DD，缺省今日）。")
    page: int | None = Field(default=None, description="列表页码（1 起）。")
    page_size: int | None = Field(default=None, description="每页条数（默认 30）。")
    limit: int | None = Field(default=None, description="条数上限。")
    decade: int | None = Field(default=None, description="microchronology 十年期。")
    has_crosswalk: bool | None = Field(default=None, description="celestial：有无交叉对照。")
    in_chapter: bool | None = Field(default=None, description="celestial：in_chapter。")
    top_n: int | None = Field(default=None, description="graph 节点上限（默认 70）。")
    min_weight: int | None = Field(default=None, description="graph 边最小权重（默认 2）。")


class TechniqueReportInput(FlexibleModel):
    # 技法依据报告：确定性的「这次用了什么技法、什么口径、谁算的」，**不需要 AI 正文**
    # （那是 horosa_report_render 的活，两种文档不混）。
    # run_id 或 group_id 二选一；都不给则取最近一次有技法卡的运行。
    run_id: str | None = None
    group_id: str | None = None
    format: str = "markdown"
    title: str | None = None
    output_path: str | None = Field(default=None, description="须在报告输出目录内（相对路径按它解析）")
    # 是否把每个技法的产出段目录写进报告（默认写；关掉可得到极短的一页）。
    include_sections: bool | None = True


class DispatchSubjectInput(FlexibleModel):
    name: str | None = None
    birth: BirthInput | ZiWeiBirthInput | BaZiBirthInput | LiuRengGodsInput | NongliTimeInput | None = None
    inner: RelativePartyInput | None = None
    outer: RelativePartyInput | None = None
    gua_names: list[str] | None = None
    year: int | str | None = None


# dispatch / hecan 自身的顶层字段；其余顶层键在「没给 birth / subject 却给了 date」时视为出生/起课信息。
_DISPATCH_OWN_FIELDS = frozenset({
    "query", "subject", "birth", "context", "preferences", "save_result", "tools", "max_tools", "request",
    "agent_confirmed_settings", "defaults_accepted", "clarification_notes",
})


class DispatchInput(FlexibleModel):
    query: str
    subject: DispatchSubjectInput | None = None
    birth: BirthInput | ZiWeiBirthInput | BaZiBirthInput | LiuRengGodsInput | NongliTimeInput | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)
    save_result: bool = True

    @model_validator(mode="before")
    @classmethod
    def _lift_flat_birth(cls, data: Any) -> Any:
        """顶层平铺的出生信息（技法工具的写法）收进 `birth`。

        技法工具收平铺的 date/time/zone/lat/lon，dispatch / hecan 却要 `{"birth": {...}}`。agent 照技法工具的
        习惯平铺传过来时，旧行为是 FlexibleModel 把这些键当额外字段收下、路由却看不见 → 被选中的技法报缺 date，
        而追问文本让用户「请提供出生日期、时间、时区和地点」——用户明明给过。显式给了 birth / subject 时不动。
        """
        if not isinstance(data, dict) or data.get("birth") is not None or data.get("subject") is not None:
            return data
        if data.get("date") in (None, ""):
            return data
        lifted = {key: value for key, value in data.items() if key not in _DISPATCH_OWN_FIELDS}
        kept = {key: value for key, value in data.items() if key in _DISPATCH_OWN_FIELDS}
        return {**kept, "birth": lifted}


class HecanInput(DispatchInput):
    # 合参（v0.28.0）：一问多技法交叉印证。入参 = dispatch 全形（query + birth/subject + 确认字段），
    # 另加 tools 显式指定技法（缺省由路由选盘）与 max_tools 上限。产出不是终稿而是**合参模板**
    # （ai_fillable：各技法结论槽 + 相互印证/分歧槽），分歧必须披露、不许平均——AI 填完即合参报告。
    tools: list[str] | None = None
    max_tools: int | None = 5


class ExportRegistryInput(FlexibleModel):
    technique: str | None = None


class ExportParseInput(FlexibleModel):
    technique: str
    content: str
    selected_sections: list[str] | None = None
    planet_info: PlanetInfoSettingInput | None = None
    astro_meaning: AstroMeaningSettingInput | None = None


class KnowledgeRegistryInput(FlexibleModel):
    domain: str | None = None


class KnowledgeReadInput(FlexibleModel):
    # query 模式（v0.30.0）：给 `query` 即跨域全文检索，domain 变可选过滤器、category 不用；
    # 不给 `query` 走精读老路（domain 必填，category 手册域可缺省首类）。
    domain: str = ""
    category: str = ""
    key: str | None = None
    query: str | None = None
    limit: int | None = None
    aspect_degree: int | str | None = None
    object_a: str | None = None
    object_b: str | None = None
    jiang_name: str | None = None
    tian_branch: str | None = None
    di_branch: str | None = None


class AgentGuidanceInput(FlexibleModel):
    tool_name: str | None = None
    intent: str | None = None
    include_all: bool = False


class MemoryAnswerInput(FlexibleModel):
    run_id: str
    user_question: str | None = None
    ai_answer: str
    ai_answer_structured: dict[str, Any] | list[Any] | None = None
    answer_meta: dict[str, Any] = Field(default_factory=dict)


class MemoryQueryInput(FlexibleModel):
    run_id: str | None = None
    tool: str | None = None
    entity: str | None = None
    text: str | None = None
    artifact_kind: str | None = None
    after: str | None = None
    before: str | None = None
    limit: int = 20
    # 分页偏移：跳过前 N 条命中（与 limit 搭配翻页）。
    offset: int = 0
    include_payload: bool = True


class MemoryShowInput(FlexibleModel):
    run_id: str
    include_payload: bool = True


class ReportTemplateInput(FlexibleModel):
    run_id: str
    tool_name: str | None = None
    language: str = "zh-CN"


class ReportRenderInput(FlexibleModel):
    run_id: str
    tool_name: str | None = None
    format: str = "pdf"
    language: str = "zh-CN"
    title: str | None = None
    ai_report: dict[str, Any] = Field(default_factory=dict)
    ai_answer_text: str | None = None
    include_raw_json: bool = False
    output_path: str | None = Field(default=None, description="须在报告输出目录内（相对路径按它解析）")


class ReportFromToolInput(FlexibleModel):
    tool_name: str
    payload: dict[str, Any]
    format: str = "pdf"
    language: str = "zh-CN"
    title: str | None = None
    question: str | None = None
    ai_report: dict[str, Any] = Field(default_factory=dict)
    ai_answer_text: str | None = None
    include_raw_json: bool = False
    output_path: str | None = Field(default=None, description="须在报告输出目录内（相对路径按它解析）")
