"""各族澄清策略：问什么、什么时候可以用星阙默认、不许假设什么。tool_table 按工具引用这些对象。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from horosa_skill.agent_guidance.base import (
    _AFTER23_DEFAULT_MEANING,
    COMMON_BIRTH_FIELDS,
)


def _policy(
    *,
    intent: str,
    required_context: list[str],
    ask_if_missing: list[dict[str, Any]],
    safe_defaults: list[dict[str, Any]] | None = None,
    do_not_assume: list[str] | None = None,
    output_contract: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "must_have_context": required_context,
        "ask_if_missing": ask_if_missing,
        "safe_defaults": safe_defaults or [],
        "do_not_assume": do_not_assume or [],
        "output_contract": output_contract
        or [
            "Use ok=true result only.",
            "Read export_snapshot.export_text and export_snapshot.sections before explaining.",
            "Persist or report only through Horosa memory/report tools when requested.",
        ],
    }


SHENSHU_POLICY = _policy(
    intent="神数 (皇极经世/五兆/荆诀/神易数/鬼谷分定经)：以干支起数，只需日期(可含时间)即可起盘，不需经纬度。技法旋钮走 options（键表见 options_keys）。",
    required_context=["date (公历日期)", "time (可选，影响时柱)"],
    ask_if_missing=[
        {"field": "date", "question": "请提供起盘的公历日期（年月日）。"},
        {"field": "time", "question": "几点起盘？（可选；影响时柱，留空按 00:00 起）"},
    ],
    safe_defaults=[
        {"field": "time", "value": "00:00:00", "meaning": "未给时间时按子初起时柱"},
        {"field": "after23NewDay", "value": 1, "meaning": "23 点后归次日（星阙默认）"},
        {"field": "lateZiHourUseNextDay", "value": 1, "meaning": "晚子时时干按次日日干起（星阙默认）"},
    ],
    do_not_assume=["date"],
)

# v0.36.0 B3：神数五支此前共用 SHENSHU_POLICY，从不问性别/地点——而 `_run_shenshu_tool` 一直在转发它们，
# 铁板/邵子/演禽按性别分条文（演禽不读地点，live 实测），策天/张果按地点起盘：不问就是静默默认。
_GENDER_QUESTION = {"field": "gender", "question": "性别？（条文按男女分列）", "options": ["男", "女"], "values": [1, 0]}
_PLACE_QUESTION = {
    "field": "location",
    "question": "起盘地点（经纬度或城市）与时区？",
    "options": ["当前位置/客户端位置", "指定城市或经纬度"],
}
SHENSHU_GENDER_POLICY = _policy(
    intent="神数 (演禽/北极/南极)：以干支起数并按性别取条文/定大运顺逆；需日期(含时间更准)与性别。",
    required_context=["date (公历日期)", "time (可选，影响时柱)", "gender (性别)"],
    ask_if_missing=[*SHENSHU_POLICY["ask_if_missing"], _GENDER_QUESTION],
    safe_defaults=SHENSHU_POLICY["safe_defaults"],
    do_not_assume=["date", "gender"],
)
# sync311 F16：年/月柱走 kin_year_domain 权威四柱（立春界 + 定气月，按**时区**折算，kinastro_common
# authoritative_pillars / webtaixuansrv _zone_to_hours）——live 实测 1990-02-04 10:00 +08:00 与 -05:00 年柱
# 己巳↔庚午、月柱丁丑↔戊寅。时区缺省 +08:00 是后端兜底，不是用户的口径 → 要问。
_ZONE_QUESTION = {
    "field": "zone",
    "question": "出生/起盘地的时区？（年柱月柱按时区定立春与节气）",
    "options": ["+08:00 北京时间", "其它时区（如 -05:00 / Asia/Tokyo）"],
}
SHENSHU_ZONE_POLICY = _policy(
    intent="神数 (太玄筮法)：以起课时刻起筮（种子=起课时刻派生，同刻同卦），四柱按时区定立春/节气；需日期、时间与时区。",
    required_context=["date (公历日期)", "time", "zone (时区)"],
    ask_if_missing=[*SHENSHU_POLICY["ask_if_missing"], _ZONE_QUESTION],
    safe_defaults=SHENSHU_POLICY["safe_defaults"],
    do_not_assume=["date", "timezone"],
)
SHENSHU_GENDER_ZONE_POLICY = _policy(
    intent="神数 (铁板/邵子/蠢子数)：以权威四柱起数并按性别取条文；四柱按时区定立春/节气，需日期、时间、时区与性别。",
    required_context=["date (公历日期)", "time", "zone (时区)", "gender (性别)"],
    ask_if_missing=[*SHENSHU_POLICY["ask_if_missing"], _GENDER_QUESTION, _ZONE_QUESTION],
    safe_defaults=SHENSHU_POLICY["safe_defaults"],
    do_not_assume=["date", "gender", "timezone"],
)
SHENSHU_PLACE_POLICY = _policy(
    intent="神数 (策天飞星/张果星宗)：按出生时刻+地点起盘并按性别取用；需日期、时间、时区、地点与性别。",
    required_context=["date (公历日期)", "time", "zone (时区)", "lat/lon 或 gpsLat/gpsLon (地点)", "gender (性别)"],
    ask_if_missing=[*SHENSHU_POLICY["ask_if_missing"], _GENDER_QUESTION, _PLACE_QUESTION, {"field": "zone", "question": "时区偏移（如 +08:00）？"}],
    safe_defaults=SHENSHU_POLICY["safe_defaults"],
    do_not_assume=["date", "gender", "location", "timezone"],
)


ASTRO_BIRTH_POLICY = _policy(
    intent="Birth/event astrology chart calculation.",
    required_context=COMMON_BIRTH_FIELDS,
    ask_if_missing=[
        {"field": "date/time/place", "question": "请提供出生/事件的日期、时间、时区和地点。"},
        {
            "field": "hsys",
            "question": "宫制要用哪一种？（索引见上游表：1 是 Alcabitus，不是 Placidus）",
            "options": ["1 Alcabitus（缺省 = 星阙 DefaultHouseSystem）", "0 整宫制/Whole Sign", "3 Placidus", "2 Regiomontanus", "4 Koch", "其他指定宫制（5–24：Vehlow/Polich Page/Sripati/MC等宫/Porphyry/Campanus/Equal/…/福点整宫制，全表见 options_keys.hsys）"],
            "values": [1, 0, 3, 2, 4, None],
        },
        {"field": "zodiacal", "question": "黄道体系要用哪一种？", "options": ["回归黄道（默认推荐）", "恒星黄道（需配 siderealAyanamsa）"], "values": [0, 1]},
        {
            "field": "siderealAyanamsa",
            "question": "若用恒星黄道，岁差(ayanāṃśa)取哪一制？（仅 zodiacal=1 时生效，缺省=lahiri）",
            "options": [
                "lahiri（默认）",
                "raman",
                "krishnamurti / KP",
                "fagan_bradley",
                "yukteshwar / true_citra / ss_revati 等（共 47 制，见 SIDEREAL_AYANAMSA_LABELS）",
            ],
            "values": ["lahiri", "raman", "krishnamurti", "fagan_bradley", None],
        },
        {"field": "tradition", "question": "是否需要传统占星扩展项？", "options": ["需要", "不需要/默认"]},
    ],
    safe_defaults=[
        {"field": "hsys", "value": 1, "meaning": "Alcabitus（星阙 DefaultHouseSystem；0 = 整宫制）"},
        {"field": "zodiacal", "value": 0, "meaning": "Tropical / 回归黄道"},
        {"field": "siderealAyanamsa", "value": "lahiri", "meaning": "恒星黄道缺省 Lahiri（仅 zodiacal=1 生效）"},
        {"field": "ad", "value": 1, "meaning": "公历纪年"},
    ],
    do_not_assume=["birth time", "birthplace", "timezone"],
)

PREDICTIVE_POLICY = _policy(
    intent="Predictive astrology calculation based on a natal chart and a target time.",
    required_context=COMMON_BIRTH_FIELDS + ["target/prediction date or year"],
    ask_if_missing=[
        {"field": "natal data", "question": "请提供本命出生日期、时间、时区和地点。"},
        {"field": "target time", "question": "要推哪一年/哪一天/哪个事件时间？"},
        {"field": "technique settings", "question": "是否沿用星阙默认推运设置？", "options": ["沿用默认", "指定主限/释放/返照等参数"]},
    ],
    safe_defaults=[
        {"field": "hsys", "value": 1, "meaning": "Alcabitus（星阙 DefaultHouseSystem；0 = 整宫制）"},
        {"field": "zodiacal", "value": 0, "meaning": "Tropical / 回归黄道"},
    ],
    do_not_assume=["target date/year", "birth time", "timezone"],
)

def _progression_target_policy(
    *,
    intent: str,
    targets: list[dict[str, Any]],
    do_not_assume: list[str],
    extra_defaults: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """推运族专属策略工厂（v0.36.0 B3）：此前 vedicprog/jaynesprog/planetaryarc/planetaryages/extrareturns
    共用 ASTRO_BIRTH_POLICY——问宫制却从不问目标时刻/弧源，agent 只能静默默认。
    extra_defaults：该工具在上游的真实缺省（v3.11 同步：目标时刻/月长/速率等），如实写进 safe_defaults。"""
    return _policy(
        intent=intent,
        required_context=COMMON_BIRTH_FIELDS + [str(item.get("field")) for item in targets],
        ask_if_missing=[
            {"field": "natal data", "question": "请提供本命出生日期、时间、时区和地点。"},
            *targets,
            {"field": "technique settings", "question": "是否沿用星阙默认推运设置？", "options": ["沿用默认", "指定参数"]},
        ],
        safe_defaults=[
            {"field": "hsys", "value": 1, "meaning": "Alcabitus（星阙 DefaultHouseSystem；0 = 整宫制）"},
            {"field": "zodiacal", "value": 0, "meaning": "Tropical / 回归黄道"},
            *(extra_defaults or []),
        ],
        do_not_assume=["birth time", "timezone", *do_not_assume],
    )


_TARGET_DATE_QUESTION = {"field": "targetDate/targetTime", "question": "推到哪一天？（targetDate YYYY-MM-DD，可加 targetTime；缺省=今天）"}
# F10（上游 AstroJaynesProgressions.js:37-39 / astroProgSnapshot.js:57-59）：目标日缺省今天（旧实现是出生日）。
_PROG_TARGET_DEFAULTS = [
    {"field": "targetDate", "value": "今天", "meaning": "缺省推到今日（本地日期，上游同律）"},
    {"field": "targetTime", "value": "12:00:00", "meaning": "目标时刻缺省正午"},
    {"field": "minorVariant", "value": "synodic", "meaning": "小推运月长=朔望月/年（上游 [Q-180] 缺省）"},
]
VEDICPROG_POLICY = _progression_target_policy(
    intent="恒星推运 / Vedic sidereal 二次推运：本命 + 目标日期。",
    targets=[_TARGET_DATE_QUESTION],
    do_not_assume=["target date"],
    extra_defaults=_PROG_TARGET_DEFAULTS,
)
JAYNESPROG_POLICY = _progression_target_policy(
    intent="赤纬推运 / Jayne：二次推运 + 赤纬平行，本命 + 目标日期。",
    targets=[_TARGET_DATE_QUESTION],
    do_not_assume=["target date"],
    extra_defaults=_PROG_TARGET_DEFAULTS,
)
PLANETARYARC_POLICY = _progression_target_policy(
    intent="行星弧向运：整盘按 arcSource 的二次推运弧推进，本命 + 弧源 + 目标时刻。",
    targets=[
        {
            "field": "arcSource",
            "question": "弧源用哪颗星？（月亮弧=Moon，太阳弧=Sun）",
            "options": ["Moon（默认·月亮弧）", "Sun（太阳弧）", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"],
            "values": ["Moon", "Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"],
        },
        {"field": "datetime", "question": "推到哪个目标时刻？（datetime YYYY-MM-DD HH:mm:ss + dirZone）"},
    ],
    do_not_assume=["arcSource", "target datetime"],
    extra_defaults=[
        {"field": "datetime", "value": "明天此刻", "meaning": "缺省目标时刻=明天此刻（上游 AstroPlanetaryArc.js todayStr，与页面同律）"},
        {"field": "arcSource", "value": "Moon", "meaning": "月亮弧（上游缺省）"},
    ],
)
PLANETARYAGES_POLICY = _progression_target_policy(
    intent="行星年龄 / 托勒密人生七阶：本命 + 观察基准日。",
    targets=[{"field": "asOf", "question": "以哪一天为基准算当前所在阶段？（asOf YYYY-MM-DD，缺省=今天）"}],
    do_not_assume=["asOf"],
)
EXTRARETURNS_POLICY = _progression_target_policy(
    intent="多重回归（土星/木星/月交返照）应期表：本命 + 年表范围。",
    targets=[
        {
            "field": "timelineStartYear/timelineCount",
            "question": "日月返照年表从哪一年起、算几年？",
            "options": ["缺省（出生年起 10 年）", "指定起始年与年数"],
        }
    ],
    do_not_assume=["timeline range"],
)
# 上游 v3.11 星运四键：区间 / 起始年与年数 / 目标日 都会改结果（缺省取「今天」，不同日子调用结果不同）→ 必问或记录接受默认。
EPHEMERIS_POLICY = _progression_target_policy(
    intent="星历：本命盘地点与时区下，区间内行星入座/留逆/朔望弦/食相 + 行运触发本命点（上游缺省今日起 90 天）。",
    targets=[
        {"field": "startDate/endDate", "question": "查哪段区间？（startDate/endDate YYYY-MM-DD；缺省=今天起 90 天，上限 732 天）"},
        {
            "field": "includeTransits",
            "question": "是否列出行运触发本命点的时刻？",
            "options": ["列出（默认）", "不列"],
            "values": [True, False],
        },
    ],
    do_not_assume=["date window"],
)
RETURNTIMELINE_POLICY = _progression_target_policy(
    intent="回归轴：逐年太阳返照 + 该年首个月亮返照时刻与两盘上升（上游缺省今年起 12 年，年数上限 40）。",
    targets=[
        {
            "field": "startYear/count",
            "question": "从哪一年起、列几年？",
            "options": ["缺省（今年起 12 年）", "指定起始年与年数（1–40）"],
        }
    ],
    do_not_assume=["year range"],
)
PRENATALSYZYGY_POLICY = _progression_target_policy(
    intent="产前朔望：自出生时刻回溯最近的朔/望，取度 + 以该时刻、出生地排盘（只需本命数据；出生时刻决定取哪一次朔望）。",
    targets=[],
    do_not_assume=["birth date/time"],
)
PROG_POLICY = _progression_target_policy(
    intent="二次推运（回归黄道）：二次/三次/小推运位置 + 与本命相位，本命 + 目标日期（上游缺省今天 12:00）。",
    targets=[
        _TARGET_DATE_QUESTION,
        {
            "field": "minorVariant",
            "question": "小推运月长按哪种算？",
            "options": ["synodic 朔望月每年（默认）", "sidereal 恒星月每年", "engine 引擎历史值（≈无推进）"],
            "values": ["synodic", "sidereal", "engine"],
        },
    ],
    do_not_assume=["target date"],
)

PERSIANDIRECTED_POLICY = _progression_target_policy(
    intent="波斯向运：黄经象征向运应期表（速率/方向/应期年数驱动主表与指定日期盘）。",
    targets=[
        {
            "field": "rateKey",
            "question": "向运速率？",
            "options": ["波斯 1°/年（默认）", "Prophected 30°/年", "Naibod 59′08″/年"],
            "values": ["persian", "prophected", "naibod"],
        },
        {"field": "direction", "question": "向运方向？", "options": ["顺向（默认）", "逆向 Converse"], "values": ["direct", "converse"]},
    ],
    do_not_assume=["rateKey", "direction"],
    extra_defaults=[
        {"field": "rateKey", "value": "persian", "meaning": "波斯 1°/年（上游缺省）"},
        {"field": "direction", "value": "direct", "meaning": "顺向（上游缺省）"},
        {"field": "maxYears", "value": 90, "meaning": "应期年数（上游齿轮 50/90/120/150/200）"},
    ],
)
BALBILLUS_POLICY = _progression_target_policy(
    intent="Balbillus 129 年系统（旺距削减主限）：起始星 / 年制 / 距离口径改主限铺排。",
    targets=[{"field": "technique settings", "question": "起始星/年制/距离口径是否沿用星阙默认？", "options": ["沿用默认（太阳·回归年·最近角距）", "指定参数"]}],
    do_not_assume=[],
    extra_defaults=[
        {"field": "startPlanet", "value": "Sun", "meaning": "自太阳起（上游缺省）"},
        {"field": "yearType", "value": "solar", "meaning": "回归年 365.2422 日（另 sidereal / hellenistic 360 / abumashar / mashaallah / bija）"},
        {"field": "mode", "value": "nearest", "meaning": "最近角距"},
        {"field": "subRule", "value": "once", "meaning": "子限一轮（cycle 循环到父期末 / fill 末段拉长填满）"},
    ],
)
# v3.13.0：129 年系统 / 年龄推进点 / 界推运各有四项口径（上游 techniqueMountSettings 挂载齿轮同名；缺省即上游缺省）。
YEARSYSTEM129_POLICY = _progression_target_policy(
    intent="129 年系统（七星时主 129 年一轮）：起始星 / 排序 / 年制 / 子限分法改各期起讫。",
    targets=[{"field": "technique settings", "question": "起始星/排序/年制/子限是否沿用星阙默认？", "options": ["沿用默认（太阳·黄道序·回归年·按天数）", "指定参数"]}],
    do_not_assume=[],
    extra_defaults=[
        {"field": "ys129StartPlanet", "value": "Sun", "meaning": "自太阳起（sect = 随昼夜区分取日/月，或七星任一）"},
        {"field": "ys129Order", "value": "zodiacal", "meaning": "按本命黄经序（chaldean 迦勒底序）"},
        {"field": "ys129YearType", "value": "solar", "meaning": "回归年（sidereal / hellenistic / abumashar / mashaallah / bija）"},
        {"field": "ys129SubRule", "value": "days", "meaning": "子限按天数（proportional 按比例 / equal 等分）"},
    ],
)
AGEPOINT_POLICY = _progression_target_policy(
    intent="年龄推进点（Huber Age Point）：推进法 / 事件范围 / 年制 / 推到几岁改事件年表。",
    targets=[{"field": "technique settings", "question": "推进法/事件/年制/年限是否沿用星阙默认？", "options": ["沿用默认（Koch 宫·全部事件·回归年·72 岁）", "指定参数"]}],
    do_not_assume=[],
    extra_defaults=[
        {"field": "apMethod", "value": "koch", "meaning": "Koch 宫，每宫 6 年（equal5 自上升每年 5°）"},
        {"field": "apEvents", "value": "full", "meaning": "全部点 × 五种相位（conj 只报合七星）"},
        {"field": "apYear", "value": "tropical", "meaning": "回归年（sidereal 恒星年）"},
        {"field": "apMaxAge", "value": 72, "meaning": "推到 72 岁（100 / 120 / 144）"},
    ],
)
DISTRIBUTIONS_POLICY = _progression_target_policy(
    intent="界推运（分配法 Distributions）：释放点 / 算法 / 年制 / 年限改界主与伙伴星年表。",
    targets=[{"field": "technique settings", "question": "释放点/算法/年制/年限是否沿用星阙默认？", "options": ["沿用默认（上升·上升时间·回归年·100 年）", "指定参数"]}],
    do_not_assume=[],
    extra_defaults=[
        {"field": "distReleaser", "value": "Asc", "meaning": "自上升释放（另 18 档：日月五星 / 中天 / 北交 / 宿命点 / 福点 / 精神点 / 产前朔望点 …）"},
        {"field": "distMethod", "value": "classical", "meaning": "上升时间，星座内均匀（exact 斜升差逐度 / qisma 每度 1 年）"},
        {"field": "distYear", "value": "tropical", "meaning": "回归年（egyptian 365 日 / julian 365.25 日）"},
        {"field": "distYears", "value": 100, "meaning": "推 100 年（60 / 80 / 120 / 150）"},
    ],
)
TRIPLICITYRULERS_POLICY = _progression_target_policy(
    intent="三分主星推运：当值光体三分主星分掌人生阶段（体系/划分法/寿命基准可调）。",
    targets=[{"field": "technique settings", "question": "三分体系/划分法/寿命基准是否沿用星阙默认？", "options": ["沿用默认（随本盘三分体系·三分·75 岁）", "指定参数"]}],
    do_not_assume=[],
    extra_defaults=[
        {"field": "system", "value": "随本盘 triplicity，否则 Dorothean", "meaning": "三分体系（上游 [Q-187/T-111] 同序）"},
        {"field": "division", "value": "thirds", "meaning": "三分 0–25/25–50/50–75"},
        {"field": "lifespan", "value": 75, "meaning": "寿命基准（30–120）"},
    ],
)
KEYPOINTS_POLICY = _progression_target_policy(
    intent="数字相位推运（120 关键点）：释放点（身=月亮 / 命=上升）改全部激活年。",
    targets=[{"field": "mode", "question": "释放点？", "options": ["身·月亮起（默认）", "命·上升起"], "values": ["soul", "body"]}],
    do_not_assume=["mode"],
    extra_defaults=[{"field": "mode", "value": "soul", "meaning": "身（月亮起，上游缺省）"}],
)


def _predictive_policy_with_defaults(extra_defaults: list[dict[str, Any]]) -> dict[str, Any]:
    """目标时刻型推运（返照/小限/太阳弧/主限/黄道释放）：共用 PREDICTIVE_POLICY 的问题，safe_defaults 写上游真实缺省。"""
    policy = deepcopy(PREDICTIVE_POLICY)
    policy["safe_defaults"] = [*policy["safe_defaults"], *extra_defaults]
    return policy


# F19（上游 aiAnalysisContext.js:2673-2760 / AstroPrimaryDirectionChart.js:454）。
_RETURN_DEFAULTS = [
    {"field": "datetime", "value": "今年生日时刻", "meaning": "当年+出生月日+出生时分（上游 [挂载自检 F-17]）"},
    {"field": "dirLat/dirLon", "value": "出生地", "meaning": "返照地缺省=本命经纬（异地返照请显式给）"},
    {"field": "dirZone", "value": "本命时区", "meaning": "返照地时区缺省=本命时区"},
]
_NOW_TARGET_DEFAULTS = [
    {"field": "datetime", "value": "此刻", "meaning": "缺省=当前时刻（上游 new DateTime() 钟面 +08:00）"},
    {"field": "dirZone", "value": "本命时区", "meaning": "目标时区缺省=本命时区"},
]
SOLARRETURN_POLICY = _predictive_policy_with_defaults(_RETURN_DEFAULTS)
PROFECTION_POLICY = _predictive_policy_with_defaults([
    *_NOW_TARGET_DEFAULTS,
    {"field": "profGrain", "value": "y", "meaning": "[小限摘要] 年小限（上游缺省）"},
    {"field": "profStart", "value": "asc", "meaning": "[小限摘要] 自上升起数（上游缺省）"},
])
SOLARARC_POLICY = _predictive_policy_with_defaults(_NOW_TARGET_DEFAULTS)
PD_POLICY = _predictive_policy_with_defaults([
    {"field": "pdMethod", "value": "core_alchabitius", "meaning": "上游缺省方位法（共 13 法）"},
    {"field": "pdTimeKey", "value": "Ptolemy", "meaning": "上游缺省度数换算（共 38 项）"},
    {"field": "pdtype", "value": 0, "meaning": "上游缺省方向类型 In Zodiaco（另 1 In Mundo / 4 Field Plane）"},
    {"field": "pdProjection/pdFrame", "value": "按 pdMethod 推（缺省 ptolemy × alcabitius）", "meaning": "弧算法 14 种 × 盘面宫制 12 种"},
])
PDCHART_POLICY = _predictive_policy_with_defaults([
    {"field": "datetime", "value": "主限表首条应期", "meaning": "过滤后首条主限行日期（UTC、dirZone=+00:00），无则出生次日"},
    {"field": "pdMethod", "value": "core_alchabitius", "meaning": "上游缺省方位法"},
    {"field": "pdTimeKey", "value": "Ptolemy", "meaning": "上游缺省度数换算"},
])
ZR_POLICY = _predictive_policy_with_defaults([
    {"field": "basePoint", "value": "Pars Fortuna", "meaning": "自福点所在座起释（上游缺省）"},
    {"field": "aiMode", "value": "l1_all", "meaning": "输出全部 L1 期（上游缺省）"},
])
# 盘面族（chart/chart13/chart12/hellen_chart/draconic）：[寿命格局] 取主法（F15，上游 AstroLifespan.js METHODS）。
ASTRO_CHART_POLICY = deepcopy(ASTRO_BIRTH_POLICY)
ASTRO_CHART_POLICY["safe_defaults"] = [
    *ASTRO_CHART_POLICY["safe_defaults"],
    {"field": "lifespanMethod", "value": "ptolemy", "meaning": "[寿命格局] 托勒密取主法（上游缺省；alcabitius/dorotheus 可选）"},
]


# 闸问题允许没有 options 的字段（自由文本/复合输入）；新问题要么带 options 要么在这里登记（tests/test_gate_policies.py 守）。
FREE_TEXT_GATE_FIELDS: frozenset[str] = frozenset({
    "date", "time", "date/time", "date/time/place", "date/time/gender", "datetime", "targetDate/targetTime", "asOf",
    "startDate/endDate", "conditions", "topic", "question", "natal data", "target time", "location", "askEvent",
    "birth data", "year", "name", "technique", "content", "category/key", "rectifyEvents", "guaDate/guaYearGanZi",
    "q", "query", "pillars", "fromYear", "nums / date-time", "qiZhi / date-time", "dayGan/dayZhi", "cast-input", "cast-input + date/time",
    "school-params", "event", "relocLat/relocLon", "inner/outer", "zone", "target technique",
})


# [Q-452 裁决 A / Q-453] 择日十技法 + 天星的快照「命中清单」两旋钮（上游 utils/zeriSnapshotPrefs.js 缺省）。
ZERI_SNAPSHOT_SAFE_DEFAULTS: list[dict[str, Any]] = [
    {"field": "zeriSnapshotMaxRows", "value": 60, "meaning": "快照命中清单最多列 60 行（可调 10–500；上游全局缺省）"},
    {"field": "zeriSnapshotExplainRows", "value": 3, "meaning": "清单前 3 行各附一棵判读树（设定 vs 实际 ✓✗，与扫描同源；可调 0–20，0=不附；上游全局缺省）"},
]

# ── 三式口径（sanshi chunk，上游 v3.11）──────────────────────────────────────────────────────
# 「星阙默认」必须字面等于上游缺省：奇门起局法缺省 = DunJiaMain.js:128 DEFAULT_OPTIONS.qijuMethod 'zhirun'（置闰）。
_QIMEN_QIJU_QUESTION: dict[str, Any] = {
    "field": "qijuMethod",
    "question": "起局方式？星阙默认为置闰（zhirun）。",
    "options": ["置闰（星阙默认）", "拆补", "茅山", "无闰", "阴盘报数（需 shuziReportNumber）"],
    "values": ["zhirun", "chaibu", "maoshan", "wurun", "shuzi"],
}
_QIMEN_SAFE_DEFAULTS: list[dict[str, Any]] = [
    {"field": "qijuMethod", "value": "zhirun", "meaning": "星阙默认（DunJiaMain DEFAULT_OPTIONS）：置闰"},
    {"field": "paiPanType", "value": 3, "meaning": "时家奇门（星阙默认）"},
    {"field": "timeAlg", "value": 0, "meaning": "星阙默认：真太阳时（ken 按真太阳时分量起局，时柱与九宫同一时辰）"},
    {"field": "sex", "value": 1, "meaning": "星阙默认；涉及命式时应先问"},
    {"field": "after23NewDay", "value": 1, "meaning": _AFTER23_DEFAULT_MEANING + "（不传即不发送，ken/农历前置按后端缺省 1）"},
]
