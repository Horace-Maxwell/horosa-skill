from __future__ import annotations

from dataclasses import dataclass
from typing import Type

from horosa_skill.schemas.tools import (
    AgePointInput,
    BalbillusInput,
    BaZiBirthInput,
    BaZiDirectInput,
    BirthInput,
    CanPingInput,
    DecennialsInput,
    DistributionsInput,
    ElectionInput,
    ExportParseInput,
    ExportRegistryInput,
    FirdariaInput,
    GermanyInput,
    GuaNamesInput,
    HarmonicInput,
    HeLuoInput,
    HoraryInput,
    JaynesProgInput,
    JinKouInput,
    JieQiYearInput,
    KnowledgeReadInput,
    KnowledgeRegistryInput,
    LiuRengGodsInput,
    LiuRengRunYearInput,
    MundaneInput,
    NongliTimeInput,
    OtherBuInput,
    PersianDirectedInput,
    PlanetaryAgesInput,
    PlanetaryArcInput,
    PredictiveInput,
    QimenInput,
    RelativeInput,
    VedicProgInput,
    YearSystem129Input,
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
    "canping": ToolDefinition("canping", "cn", "canping", None, CanPingInput, "Run the local 邵子参评数 / 金锁银匙 engine (本命、大运、流年 歲運 条文) with 星阙 parity.", execution="local"),
    "heluo": ToolDefinition("heluo", "cn", "heluo", None, HeLuoInput, "Run the local 河洛理数 engine (起命/先天卦/后天卦/命运篇/大限·岁运 with 元堂爻辞) with 星阙 parity.", execution="local"),
    "chart": ToolDefinition("chart", "astro", "chart", "/chart", BirthInput, "Generate a core Horosa chart."),
    "chart13": ToolDefinition("chart13", "astro", "chart13", "/chart13", BirthInput, "Generate the chart13 variant."),
    "hellen_chart": ToolDefinition("hellen_chart", "astro", "hellen_chart", None, BirthInput, "Generate the 希腊星盘 / 希腊星术 chart output.", execution="local"),
    "guolao_chart": ToolDefinition("guolao_chart", "astro", "guolao_chart", None, BirthInput, "Generate the 七政四余 chart output.", execution="local"),
    "germany": ToolDefinition("germany", "astro", "germany", None, GermanyInput, "Generate the 量化盘 / midpoint analysis output.", execution="local"),
    "harmonic": ToolDefinition("harmonic", "astro", "harmonic", None, HarmonicInput, "Generate the 调波盘 / harmonic chart (本命黄经×调波数), with 调波位置 and 同频合相.", execution="local"),
    "agepoint": ToolDefinition("agepoint", "predict", "agepoint", None, AgePointInput, "Generate the 年龄推进点 / Age Point (Huber) timeline — Koch-house age cycle with natal contacts.", execution="local"),
    "distributions": ToolDefinition("distributions", "predict", "distributions", None, DistributionsInput, "Generate the 界推运 / Distributions (分配法) timeline — Asc through the Egyptian bounds with distributor + participants.", execution="local"),
    "mundane": ToolDefinition("mundane", "astro", "mundane", None, MundaneInput, "Generate the 世俗入宫盘 / mundane ingress chart — cast at the precise solar-term (春分/夏至/秋分/冬至) ingress moment of a year.", execution="local"),
    "jaynesprog": ToolDefinition("jaynesprog", "predict", "jaynesprog", None, JaynesProgInput, "Generate the 赤纬推运 / Jayne Declination progression (secondary progression + declination parallels).", execution="local"),
    "vedicprog": ToolDefinition("vedicprog", "predict", "vedicprog", None, VedicProgInput, "Generate the 恒星推运 / Vedic sidereal progression.", execution="local"),
    "planetaryarc": ToolDefinition("planetaryarc", "predict", "planetaryarc", None, PlanetaryArcInput, "Generate the 行星弧 / Planetary Arc direction (whole chart directed by arcSource's secondary arc).", execution="local"),
    "planetaryages": ToolDefinition("planetaryages", "predict", "planetaryages", None, PlanetaryAgesInput, "Generate the 行星年龄 / Ages of Man (Ptolemy seven ages) for the natal chart.", execution="local"),
    "balbillus": ToolDefinition("balbillus", "predict", "balbillus", None, BalbillusInput, "Generate the Balbillus 129年系统 (旺距削减主限) life-period table for the natal chart.", execution="local"),
    "yearsystem129": ToolDefinition("yearsystem129", "predict", "yearsystem129", None, YearSystem129Input, "Generate the 129年系统 (seven-planet succession, 129-year cycle) periods for the natal chart.", execution="local"),
    "persiandirected": ToolDefinition("persiandirected", "predict", "persiandirected", None, PersianDirectedInput, "Generate the 波斯向运 / Persian Directed (symbolic 1°/year) hit-list for the natal chart.", execution="local"),
    "horary": ToolDefinition("horary", "chart", "horary", None, HoraryInput, "Run a 卜卦 / horary judgment (radicality, significators, perfection, moon, verdict, timing) for a question cast at its asked-moment.", execution="local"),
    "election": ToolDefinition("election", "chart", "election", None, ElectionInput, "Run a 择日 / electional judgment (hard flags, topic rule pack, scoring, recommendations) for a candidate moment.", execution="local"),
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
    "liureng_gods": ToolDefinition(
        "liureng_gods",
        "cn",
        "liureng_gods",
        "/liureng/gods",
        LiuRengGodsInput,
        "起大六壬正盘 / four lessons and three transmissions. Use this MCP tool for any 大六壬起课 request, including current-time pans; do not hand-calculate with shell/Python or web snippets. Returns Xingque-compatible structured export sections, memory, and report-ready data.",
        execution="local",
    ),
    "liureng_runyear": ToolDefinition(
        "liureng_runyear",
        "cn",
        "liureng_runyear",
        "/liureng/runyear",
        LiuRengRunYearInput,
        "Generate 大六壬行年 / runyear output through the local Horosa runtime. Use this tool instead of manual calendar scripts so storage, export contracts, and reports remain consistent.",
        execution="local",
    ),
    "jieqi_year": ToolDefinition("jieqi_year", "cn", "jieqi_year", "/jieqi/year", JieQiYearInput, "Generate JieQi year output."),
    "nongli_time": ToolDefinition("nongli_time", "cn", "nongli_time", "/nongli/time", NongliTimeInput, "Generate NongLi time output."),
    "gua_desc": ToolDefinition("gua_desc", "cn", "gua_desc", "/gua/desc", GuaNamesInput, "Fetch Gua descriptions."),
    "gua_meiyi": ToolDefinition("gua_meiyi", "cn", "gua_meiyi", "/gua/meiyi", GuaNamesInput, "Fetch MeiYi Gua descriptions."),
}
