from __future__ import annotations

from dataclasses import dataclass
from typing import Type

from horosa_skill.schemas.tools import (
    BaZiBirthInput,
    BaZiDirectInput,
    BirthInput,
    ExportParseInput,
    ExportRegistryInput,
    GuaNamesInput,
    JinKouInput,
    JieQiYearInput,
    LiuRengGodsInput,
    LiuRengRunYearInput,
    NongliTimeInput,
    PredictiveInput,
    QimenInput,
    RelativeInput,
    TaiyiInput,
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
    "qimen": ToolDefinition("qimen", "cn", "qimen", None, QimenInput, "Run the local 奇门遁甲 engine with headless frontend parity.", execution="local"),
    "taiyi": ToolDefinition("taiyi", "cn", "taiyi", None, TaiyiInput, "Run the local 太乙 engine with headless frontend parity.", execution="local"),
    "jinkou": ToolDefinition("jinkou", "cn", "jinkou", None, JinKouInput, "Run the local 金口诀 engine with headless frontend parity.", execution="local"),
    "chart": ToolDefinition("chart", "astro", "chart", "/chart", BirthInput, "Generate a core Horosa chart."),
    "chart13": ToolDefinition("chart13", "astro", "chart13", "/chart13", BirthInput, "Generate the chart13 variant."),
    "solarreturn": ToolDefinition("solarreturn", "predict", "solarreturn", "/predict/solarreturn", PredictiveInput, "Compute the solar return chart."),
    "lunarreturn": ToolDefinition("lunarreturn", "predict", "lunarreturn", "/predict/lunarreturn", PredictiveInput, "Compute the lunar return chart."),
    "solararc": ToolDefinition("solararc", "predict", "solararc", "/predict/solararc", PredictiveInput, "Compute solar arc directions."),
    "givenyear": ToolDefinition("givenyear", "predict", "givenyear", "/predict/givenyear", PredictiveInput, "Compute given-year predictive output."),
    "profection": ToolDefinition("profection", "predict", "profection", "/predict/profection", PredictiveInput, "Compute profection output."),
    "pd": ToolDefinition("pd", "predict", "pd", "/predict/pd", PredictiveInput, "Compute primary directions."),
    "pdchart": ToolDefinition("pdchart", "predict", "pdchart", "/predict/pdchart", PredictiveInput, "Compute primary direction chart output."),
    "zr": ToolDefinition("zr", "predict", "zr", "/predict/zr", PredictiveInput, "Compute zodiacal release output."),
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
