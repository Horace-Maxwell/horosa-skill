from __future__ import annotations

from dataclasses import dataclass
from typing import Type

from horosa_skill.schemas.tools import (
    BaZiBirthInput,
    BaZiDirectInput,
    BirthInput,
    DecennialsInput,
    ExportParseInput,
    ExportRegistryInput,
    FirdariaInput,
    GermanyInput,
    GuaNamesInput,
    JinKouInput,
    JieQiYearInput,
    KnowledgeReadInput,
    KnowledgeRegistryInput,
    LiuRengGodsInput,
    LiuRengRunYearInput,
    NongliTimeInput,
    OtherBuInput,
    PredictiveInput,
    QimenInput,
    RelativeInput,
    SanShiUnitedInput,
    SixYaoInput,
    SuZhanInput,
    TaiyiInput,
    TongSheFaInput,
    ZiWeiBirthInput,
    ZiWeiRulesInput,
)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    domain: str
    action: str
    endpoint: str | None
    input_model: Type
    description: str
    execution: str = "remote"

    @property
    def mcp_name(self) -> str:
        return f"horosa_{self.domain}_{self.action}"


TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    "export_registry": ToolDefinition("export_registry", "export", "registry", None, ExportRegistryInput, "Return the full 星阙 AI 导出设置 registry in machine-readable JSON.", execution="local"),
    "export_parse": ToolDefinition("export_parse", "export", "parse", None, ExportParseInput, "Convert 星阙 AI 导出文本快照 into structured JSON sections.", execution="local"),
    "knowledge_registry": ToolDefinition("knowledge_registry", "knowledge", "registry", None, KnowledgeRegistryInput, "List bundled Xingque hover knowledge domains, categories, and keys.", execution="local"),
    "knowledge_read": ToolDefinition("knowledge_read", "knowledge", "read", None, KnowledgeReadInput, "Read bundled Xingque hover knowledge for astrology, 六壬, and 奇门.", execution="local"),
    "qimen": ToolDefinition("qimen", "cn", "qimen", None, QimenInput, "Run the local 奇门遁甲 engine with headless frontend parity.", execution="local"),
    "taiyi": ToolDefinition("taiyi", "cn", "taiyi", None, TaiyiInput, "Run the local 太乙 engine with headless frontend parity.", execution="local"),
    "jinkou": ToolDefinition("jinkou", "cn", "jinkou", None, JinKouInput, "Run the local 金口诀 engine with headless frontend parity.", execution="local"),
    "tongshefa": ToolDefinition("tongshefa", "cn", "tongshefa", None, TongSheFaInput, "Run the local 统摄法 engine with machine-readable output.", execution="local"),
    "sanshiunited": ToolDefinition("sanshiunited", "cn", "sanshiunited", None, SanShiUnitedInput, "Run the local 三式合一 aggregator with 奇门、太乙、大六壬 parity sections.", execution="local"),
    "suzhan": ToolDefinition("suzhan", "cn", "suzhan", None, SuZhanInput, "Generate the 宿占 / 宿盘 output with machine-readable snapshot sections.", execution="local"),
    "sixyao": ToolDefinition("sixyao", "cn", "sixyao", None, SixYaoInput, "Generate the 易卦 / 六爻 output with line, movement, and interpretation sections.", execution="local"),
    "chart": ToolDefinition("chart", "astro", "chart", "/chart", BirthInput, "Generate a core Horosa chart."),
    "chart13": ToolDefinition("chart13", "astro", "chart13", "/chart13", BirthInput, "Generate the chart13 variant."),
    "hellen_chart": ToolDefinition("hellen_chart", "astro", "hellen_chart", None, BirthInput, "Generate the 希腊星盘 / 希腊星术 chart output.", execution="local"),
    "guolao_chart": ToolDefinition("guolao_chart", "astro", "guolao_chart", None, BirthInput, "Generate the 七政四余 chart output.", execution="local"),
    "germany": ToolDefinition("germany", "astro", "germany", None, GermanyInput, "Generate the 量化盘 / midpoint analysis output.", execution="local"),
    "solarreturn": ToolDefinition("solarreturn", "predict", "solarreturn", "/predict/solarreturn", PredictiveInput, "Compute the solar return chart."),
    "lunarreturn": ToolDefinition("lunarreturn", "predict", "lunarreturn", "/predict/lunarreturn", PredictiveInput, "Compute the lunar return chart."),
    "solararc": ToolDefinition("solararc", "predict", "solararc", "/predict/solararc", PredictiveInput, "Compute solar arc directions."),
    "givenyear": ToolDefinition("givenyear", "predict", "givenyear", "/predict/givenyear", PredictiveInput, "Compute given-year predictive output."),
    "profection": ToolDefinition("profection", "predict", "profection", "/predict/profection", PredictiveInput, "Compute profection output."),
    "pd": ToolDefinition("pd", "predict", "pd", "/predict/pd", PredictiveInput, "Compute primary directions."),
    "pdchart": ToolDefinition("pdchart", "predict", "pdchart", "/predict/pdchart", PredictiveInput, "Compute primary direction chart output."),
    "zr": ToolDefinition("zr", "predict", "zr", "/predict/zr", PredictiveInput, "Compute zodiacal release output."),
    "firdaria": ToolDefinition("firdaria", "predict", "firdaria", None, FirdariaInput, "Generate the 法达星限 output.", execution="local"),
    "decennials": ToolDefinition("decennials", "predict", "decennials", None, DecennialsInput, "Generate the 十年大运 output with full timeline sections.", execution="local"),
    "otherbu": ToolDefinition("otherbu", "other", "otherbu", None, OtherBuInput, "Generate the 西洋游戏 / 占星骰子 output.", execution="local"),
    "relative": ToolDefinition("relative", "astro", "relative", "/modern/relative", RelativeInput, "Compute relationship / relative chart output."),
    "india_chart": ToolDefinition("india_chart", "astro", "india_chart", "/india/chart", BirthInput, "Compute Indian chart output."),
    "ziwei_birth": ToolDefinition("ziwei_birth", "cn", "ziwei_birth", "/ziwei/birth", ZiWeiBirthInput, "Generate Zi Wei birth chart."),
    "ziwei_rules": ToolDefinition("ziwei_rules", "cn", "ziwei_rules", "/ziwei/rules", ZiWeiRulesInput, "Fetch Zi Wei rules."),
    "bazi_birth": ToolDefinition("bazi_birth", "cn", "bazi_birth", "/bazi/birth", BaZiBirthInput, "Generate BaZi birth output."),
    "bazi_direct": ToolDefinition("bazi_direct", "cn", "bazi_direct", "/bazi/direct", BaZiDirectInput, "Generate BaZi direct output."),
    "liureng_gods": ToolDefinition("liureng_gods", "cn", "liureng_gods", "/liureng/gods", LiuRengGodsInput, "Generate LiuReng gods output."),
    "liureng_runyear": ToolDefinition("liureng_runyear", "cn", "liureng_runyear", "/liureng/runyear", LiuRengRunYearInput, "Generate LiuReng runyear output."),
    "jieqi_year": ToolDefinition("jieqi_year", "cn", "jieqi_year", "/jieqi/year", JieQiYearInput, "Generate JieQi year output."),
    "nongli_time": ToolDefinition("nongli_time", "cn", "nongli_time", "/nongli/time", NongliTimeInput, "Generate NongLi time output."),
    "gua_desc": ToolDefinition("gua_desc", "cn", "gua_desc", "/gua/desc", GuaNamesInput, "Fetch Gua descriptions."),
    "gua_meiyi": ToolDefinition("gua_meiyi", "cn", "gua_meiyi", "/gua/meiyi", GuaNamesInput, "Fetch MeiYi Gua descriptions."),
}
