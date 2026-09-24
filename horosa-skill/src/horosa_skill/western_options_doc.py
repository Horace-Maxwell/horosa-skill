"""西占工具口径词表（上游 v3.11 western 同步）：长词表不进 tools/list，住 `horosa_agent_guidance` 的 `options_keys`。

tools/list 字节预算吃紧（`hsys` 在 47 个工具上重复，多 150 B 就是 +7 KB），所以：

1. 各输入模型 `ADVERTISE_HIDDEN` 字段（照常声明 + 校验、MCP 扁平面顶层照收，只是不进广告层）——说明直接取模型字段
   description（单源，改描述即改文档）；
2. BirthInput 上的快照口径键（[信息] 互容接纳过滤 / [埃及历] 七轴 / [古典·显赫计分] 判定项）——同取字段 description；
3. 引擎词表类长文本（宫制 0–24、卜卦 20 类 / 7 流派、择日 37 用事 / 5 流派、七政宿度制 0–8、印占大运 15 体系 / 6 流派、
   世运规则集、关系盘 0–4）——写在本模块；键集与中文名由 tests/test_sync311_western.py 对 vendored 引擎源逐键核对
   （漂移即红），宫制表直接由 astro_rulers.HOUSE_SYSTEM_LABELS（上游 AstroConst.HOUSE_SYSTEM_OPTIONS 镜像）生成。
"""

from __future__ import annotations

from typing import Any

from horosa_skill.astro_rulers import HOUSE_SYSTEM_LABELS

# 上游 significators.js CATEGORY_DEF（20 类）：(键, quesitedLabel, 事项宫；None = 综合取月亮下一入相/相关宫主)。
HORARY_CATEGORIES: tuple[tuple[str, str, int | None], ...] = (
    ("general", "事项", None), ("wealth", "财物", 2), ("family", "兄弟/亲属", 3), ("property", "房产/田宅", 4),
    ("father", "父亲", 4), ("mother", "母亲", 10), ("pregnancy", "子嗣", 5), ("health", "疾病", 6),
    ("marriage", "对象/婚姻", 7), ("lawsuit", "对手", 7), ("theft", "盗贼/失物", 7), ("death", "死亡/遗产", 8),
    ("travel", "旅行/远行", 9), ("career", "职位/事业", 10), ("hope", "愿望/朋友", 11), ("enemy", "私敌", 12),
    ("message", "消息/书信", 3), ("lost", "失物", 2), ("lost_animal", "走失活物", 6), ("trade", "交易对手", 7),
)
# 上游 horarySchools.js HORARY_SCHOOLS（七档，HORARY_SCHOOL_ORDER 序）：(键, 中文名, 起盘字段 horaryBackendFields)。
HORARY_SCHOOLS: tuple[tuple[str, str, str], ...] = (
    ("classical", "经典主流", "hsys 2 · 界系 2 · 托勒密三分 · 七政 · 福点不反转"),
    ("renaissance", "文艺复兴", "hsys 2 · 界系 2 · 托勒密三分 · 七政 · 福点不反转"),
    ("strict", "当代严谨", "hsys 2 · 界系 0 · 多罗修斯三分 · 七政 · 福点夜反转"),
    ("sequence", "序列判读", "hsys 2 · 界系 2 · 托勒密三分 · 七政 · 福点不反转"),
    ("hellenistic", "希腊化", "hsys 0 · 界系 0 · 多罗修斯三分 · 七政 · 福点夜反转"),
    ("medieval", "中世纪", "hsys 1 · 界系 0 · 多罗修斯三分 · 七政 · 福点夜反转"),
    ("modern", "现代心理", "hsys 3 · 界系 2 · 托勒密三分 · 含三王星 · 福点不反转"),
)
# 上游 topicMaster.js TOPIC_MASTER（37 类）：(topic_id, cn)。
ELECTION_TOPICS: tuple[tuple[str, str], ...] = (
    ("marriage", "结婚/订婚"), ("business", "创业/开业/开市"), ("organization", "团体组织成立"), ("move_in", "入宅/迁居"),
    ("completion", "落成"), ("buy_property", "购屋/租屋"), ("buy_land", "购地"), ("renovation", "整修/动土/破土"),
    ("trade", "买卖交易"), ("buy_car", "购车(签约付订)"), ("deliver_car", "交车(驶离)"), ("contract", "签约/承诺"),
    ("registration", "登记"), ("application", "申请"), ("diet", "节食/减肥"), ("quit_habit", "戒烟/戒毒"),
    ("pursue_love", "追求爱情"), ("job_hunt", "求职"), ("team_departure", "队伍出发/比赛"), ("publishing", "出版/节目开播"),
    ("medication", "用药"), ("surgery", "手术"), ("banquet", "宴会/盛会"), ("inauguration", "就职典礼"),
    ("funeral", "葬礼(活人)"), ("bed_setting", "安床"), ("travel", "出行"), ("blessing", "祈福"), ("altar", "安香/安神位"),
    ("ritual", "法会/建醮"), ("general_day", "大众吉日(简)"), ("planting", "播种/种植/农耕"), ("sailing", "海行/航海"),
    ("litigation", "诉讼/战阵/竞争"), ("release", "释囚/解约脱身"), ("haircut", "理发/剪甲"), ("talisman", "制作护符"),
)
# 上游 westernSchools.js WEST_SCHOOL_ORDER / WEST_SCHOOLS[].cn。
ELECTION_SCHOOLS: tuple[tuple[str, str], ...] = (
    ("modern_main", "现代主流"), ("hellenistic", "希腊化"), ("persian", "波斯-阿拉伯"),
    ("renaissance", "文艺复兴"), ("modern_revival", "古典复兴"),
)
# 上游 guolaoData.js SU28_MODE_LABEL（0–8）。
GUOLAO_SU28_MODES: tuple[tuple[int, str], ...] = (
    (0, "荀爽距星(19年测)"), (1, "斗柄定房法"), (2, "回归今宿"), (3, "回归古制开禧"), (4, "恒星制"),
    (5, "恒星制·现代天赤"), (6, "授时历古法"), (7, "赤道回归(元明)"), (8, "赤道回归(实时)"),
)
# 上游 IndiaChart.js / indiaConst INDIA_DASHA_SYSTEM_OPTIONS（15 档）与 INDIA_SCHOOL_OPTIONS + INDIA_SCHOOL_DEFAULTS（预设岁差/宫制）。
INDIA_DASHA_SYSTEMS: tuple[tuple[str, str], ...] = (
    ("vimshottari", "Vimshottari"), ("yogini", "Yogini"), ("ashtottari", "Ashtottari"), ("tribhagi", "Tribhāgī（÷3）"),
    ("shodashottari", "Shodashottari"), ("dvadashottari", "Dvadashottari"), ("panchottari", "Panchottari"),
    ("shatabdika", "Shatabdika"), ("chaturashitiSama", "Chaturashiti"), ("dwisaptatiSama", "Dwisaptati"),
    ("shashtihayani", "Shashtihayani"), ("shattrimshaSama", "Shattrimsha"), ("chara", "Chara"),
    ("taraDasha", "Tāra(强度序)"), ("akkg", "AKKG(AK 播种)"),
)
INDIA_SCHOOLS: tuple[tuple[str, str, str, int], ...] = (
    ("parashari", "Parāśarī 帕拉萨拉(默认)", "lahiri", 0), ("jaimini", "Jaimini 贾米尼", "lahiri", 0),
    ("tajika", "Tājika 塔吉卡(年盘)", "lahiri", 0), ("kp", "KP 系统", "krishnamurti", 3),
    ("nadi", "Nāḍī 纳迪", "lahiri", 0), ("western_sidereal", "Western Sidereal 西方恒星(对照)", "fagan_bradley", 3),
)
# 上游 divination/mundane/ruleset.js MUNDANE_RULESETS。
MUNDANE_RULESETS: tuple[tuple[str, str], ...] = (
    ("ptolemaic", "托勒密古典"), ("medieval", "中世纪(Lilly)"), ("modern", "现代(Carter–Campion)"), ("barbault", "Barbault 周期"),
)
# 上游 AstroRelative.js hook 表（relative 0–4；「关系量化」页签同 0 另调 /astroextra/relative）。
RELATIVE_MODES: tuple[tuple[int, str], ...] = (
    (0, "比较盘"), (1, "组合盘"), (2, "影响盘"), (3, "时空中点盘"), (4, "马克斯盘"),
)
# 上游 horarySchools.js HORARY_PARAM_SPEC 键序（卜卦 options 覆写键全表）。
HORARY_PARAM_KEYS: tuple[str, ...] = (
    "hsys", "termsVariant", "geminiBoundEmended", "tradition", "tripSystem", "accidentalMode", "partileDef", "lotsSet",
    "pofReversal", "orbMode", "interferenceTiming", "detectAbscission", "refranationAsDestruction",
    "refranationIncludeSignChange", "collectionRequireReception", "oppositionVerdict", "cazimiOrb", "combustOrb",
    "underBeamsOrb", "combustMitigateSameSign", "combustExemptConjAnswer", "vocMode", "vocIncludeOuter",
    "vocMitigateSigns", "viaCombustaVariant", "antiscia", "fixedStarOrb", "fixedStarOrbMode", "considerationsMode",
    "ascEarlyDeg", "ascLateDeg", "hourAgreementVariant", "perfectionStrict", "perfectionCandidates",
    "receptionForHardAspects", "receptionPerfection", "rescueAfterDestruction", "timingStationAware",
    "backendConditionNotes", "personScope", "querentGender", "moonPromotion", "naturalSignifEnhanced", "verdictProfile",
    "timingVariant", "timingModifiers", "timingSecondLaw", "onePlanetBoth", "parentHousesVariant", "includeOuter",
)
# 卜卦 / 择日判读全局层吃的顶层古典键（上游 judgeLayerOverrides.js JUDGE_KEYS_FROM_CLASSICAL + divinationJudgeGlobals）。
JUDGE_GLOBAL_KEYS = (
    "cazimiOrb/combustOrb/underBeamsOrb/vocMode/vocIncludeOuter/viaCombustaVariant/partileDef/antisciaOrb/"
    "starOrb(=fixedStarOrb)/starOrbMode(=fixedStarOrbMode)/combustMitigateSameSign/antiscia"
)

# BirthInput 上只作用于快照的口径键（send:'never'）按工具挂文档：[埃及历]/[信息] 随 service._CLASSICAL_ANALYSIS_TOOLS
# （键表 service._EGYPT_AXIS_KEYS），[古典·显赫计分] 主宰光体四个全局判定键只 chart。
_EMINENCE_KEYS = ("busyPlaces", "dynamicalDivisions", "domicileMasterMethod", "rayWeighting")


def house_system_doc() -> str:
    table = " ".join(f"{k}={v}" for k, v in HOUSE_SYSTEM_LABELS.items())
    return (
        f"宫制索引 0–{len(HOUSE_SYSTEM_LABELS) - 1}（上游 AstroConst.HOUSE_SYSTEM_OPTIONS 全表）：{table}。"
        "MCP 扁平面 enum 只广告 0–8（tools/list 预算），9–24 后端照收：客户端按 enum 拦时经 request 整包传。"
    )


def _static_doc(tool_name: str) -> dict[str, str]:
    if tool_name == "horary":
        return {
            "category": "问卜类别（20 类，括号=事项宫；认不出 → general）："
            + " ".join(f"{k}={label}({house if house else '月亮下一入相'})" for k, label, house in HORARY_CATEGORIES)
            + "；father/mother 的 4/10 宫随 options.parentHousesVariant（traditional 4父10母 | modern 反之）。",
            "school": "判读流派 7 档（缺省 classical），同时定起盘字段（上游 horaryBackendFields）："
            + "；".join(f"{k} {cn}（{fields}）" for k, cn, fields in HORARY_SCHOOLS)
            + "。显式 hsys/termsVariant/geminiBoundEmended/tradition 或 options.tripSystem 压过流派。",
            "options": "判读层覆写 {键: 值}，键 = 引擎 HORARY_PARAM_SPEC 全表：" + "/".join(HORARY_PARAM_KEYS)
            + "（hsys/termsVariant/geminiBoundEmended/tradition 与 tripSystem 同时改起盘）；认不出的键回执 data.params_ignored。",
            "判读全局层": f"顶层古典键 {JUDGE_GLOBAL_KEYS} 进判读全局层（内建 < 全局 < 流派差异 < options）；"
            "顶层 triplicity/lotReversal 不作用于卜卦盘（流派绑定，另出告警）。",
        }
    if tool_name == "election":
        return {
            "topicId": "用事（37 类，认不出 → marriage）：" + " ".join(f"{k}={cn}" for k, cn in ELECTION_TOPICS),
            "school": "择日流派 5 档：" + " ".join(f"{k}={cn}" for k, cn in ELECTION_SCHOOLS)
            + "；未显式给 hsys 时宫制随流派（hellenistic/modern_revival=0、persian=1、renaissance=2、modern_main=0）。",
            "判读全局层": f"顶层古典键 {JUDGE_GLOBAL_KEYS} 进判读全局层（流派口径之下、options 之上）。",
        }
    if tool_name == "guolao_chart":
        return {
            "doubingSu28": "宿度制 0–8（缺省 2）：" + " ".join(f"{k}={label}" for k, label in GUOLAO_SU28_MODES)
            + "；子选项只在对应制下生效：4→guolaoAyanamsa，6→guolaoTuibianMethod/guolaoGufaPrecess，7/8→guolaoEqTropicalAnchor。",
        }
    if tool_name == "india_chart":
        return {
            "dashaSystem": "大运体系 15 档（缺省 vimshottari；决定 [大运Dasha] 段）："
            + " ".join(f"{k}={label}" for k, label in INDIA_DASHA_SYSTEMS)
            + "；taraDasha/akkg 为展示体系，不下发后端。",
            "indiaSchool": "流派 6 档（进 [起盘信息] 流派行；未给 indiaAyanamsa/indiaHsys 时补该派预设）："
            + "；".join(f"{k}={label}（{ayan}/hsys {hsys}）" for k, label, ayan, hsys in INDIA_SCHOOLS),
        }
    if tool_name == "mundane":
        return {
            "mundaneRuleset": "规则集 4 档（缺省 modern）：" + " ".join(f"{k}={label}" for k, label in MUNDANE_RULESETS)
            + "；进 [世俗入宫] 首行，右栏卡片段（年盘概要等）按该规则集判读；[定局·年主/盘主]、[地理分野] 两段尚未随规则集（已知缺口）。",
        }
    if tool_name == "relative":
        return {
            "relative": "关系盘 0–4（缺省 0）：" + " ".join(f"{k}={label}" for k, label in RELATIVE_MODES) + "。",
        }
    return {}


def western_options_doc(tool_name: str) -> dict[str, str]:
    """{键: 说明}；无文档返回 {}。键名即请求键（顶层按名传，或走 request 整包）。"""
    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.schemas.tools import BirthInput
    from horosa_skill.surfaces.mcp_schema import advertise_hidden_fields

    definition = TOOL_DEFINITIONS.get(tool_name)
    if definition is None:
        return {}
    model = definition.input_model
    fields: dict[str, Any] = model.model_fields
    doc: dict[str, str] = {}
    if "hsys" in fields and not tool_name.startswith("india"):
        doc["hsys"] = house_system_doc()
    for name in sorted(advertise_hidden_fields(model)):
        field = fields.get(name)
        if field is not None and field.description:
            doc[name] = field.description
    if isinstance(model, type) and issubclass(model, BirthInput):
        from horosa_skill.service import HorosaSkillService

        if tool_name in HorosaSkillService._CLASSICAL_ANALYSIS_TOOLS:
            doc["showOnlyRulExaltReception"] = str(BirthInput.model_fields["showOnlyRulExaltReception"].description)
            for name in HorosaSkillService._EGYPT_AXIS_KEYS:
                doc[name] = str(BirthInput.model_fields[name].description)
        if tool_name == "chart":
            for name in _EMINENCE_KEYS:
                doc[name] = str(BirthInput.model_fields[name].description)
    doc.update(_static_doc(tool_name))
    return doc
