"""中式技法的枚举类设置词表（v0.50.0，`input_fields.Vocabulary` 机制）。

此前这些设置由 vendored / 自写 JS 用 `x === 'dao' ? 'dao' : 'main'`、`METHODS.has(x) ? x : 'ming'`、Python `payload.get(k) or 缺省`
判：「道家」「bogus」「Female」一律悄悄变成缺省口径，盘头却照印用户原文或缺省名。现在每个设置一张表：规范值 = 引擎认的线上值
（取自各 adapter / 上游选项表），别名只收有唯一含义的中文名；schema 层经 `parse_with` 挂成 BeforeValidator——认得 → 规范值
（做了解读的进 warnings），认不出 → `tool.invalid_option`（`details.options` 是全表）。

不收进词表的（理由见 tests/test_cn_vocab.py 头注）：只经 /nongli/time 的 `timeAlg`（后端自己判，0 / 1 / 3 都有意义）；自由文本。
"""
from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

from horosa_skill.input_fields import (
    FieldIssue,
    Parsed,
    Vocabulary,
    clean_text,
    field_validator_for,
    is_blank,
    parse_with,
)

V = Vocabulary

# 认平太阳时（3）的本地技法（上游 techniqueMountSettings TIME_ALG_WITH_MEAN_OPTIONS：神数正传 / 参评 / 河洛 / 一掌经）。
TIME_ALG_WITH_MEAN = V("timeAlg", {0: ("真太阳时", "true solar", "truesolar"), 3: ("平太阳时", "mean solar", "meansolar"),
                                   1: ("直接时间", "钟表时", "clock", "direct")},
                       labels={0: "真太阳时（缺省）", 3: "平太阳时", 1: "直接时间"})
# 紫微只有两档（上游 ZIWEI_TIME_FIELDS：`Number(v) === 1 ? 1 : 0`，存了 3 的盘按真太阳时算）。
_ZIWEI_TIME_ALG = V("timeAlg", {0: ("真太阳时", "true solar", "truesolar"), 1: ("直接时间", "钟表时", "clock", "direct")},
                    labels={0: "真太阳时（缺省）", 1: "直接时间"})


def parse_ziwei_time_alg(value: Any) -> Parsed:
    """紫微 timeAlg：0 / 1；3（平太阳时，来自全局新命盘缺省）照上游按真太阳时算并说明；其余（2 …）拒——旧写法把 2 悄悄读成真太阳时。"""
    if not isinstance(value, bool) and f"{value}".strip() in ("3", "3.0", "平太阳时"):
        return Parsed(0, "紫微 timeAlg=3（平太阳时）按真太阳时排（紫微只有真太阳时 / 直接时间两档，上游同）。",
                      "Ziwei timeAlg=3 (mean solar) was read as true solar time (Ziwei has only true-solar / clock; upstream does the same).")
    return _ZIWEI_TIME_ALG.parse(value)

TRIGRAM = {name: (pinyin, symbol) for name, pinyin, symbol in (
    ("乾", "qian", "☰"), ("兑", "dui", "☱"), ("离", "li", "☲"), ("震", "zhen", "☳"),
    ("巽", "xun", "☴"), ("坎", "kan", "☵"), ("艮", "gen", "☶"), ("坤", "kun", "☷"),
)}


def _trigram_vocab(field: str) -> Vocabulary:
    return V(field, TRIGRAM, labels={name: name for name in TRIGRAM})


CN_VOCABULARIES: dict[str, dict[str, Vocabulary]] = {
    "xiaoliuren": {
        # xiaoliuren.js `input.school === 'dao' ? 'dao' : 'main'`
        "school": V("school", {"main": ("主流", "主流六宫", "六宫", "小六壬"), "dao": ("道家", "道门", "道门九宫", "九宫", "道")},
                    labels={"main": "主流六宫（缺省）", "dao": "道门九宫（五行生克与拜解）"}),
    },
    "feigong": {
        "qiMode": V("qiMode", {"hour": ("时支", "占时"), "manualZhi": ("选支",), "manualNum": ("数取", "报数"), "yearZhi": ("年支",)},
                    labels={"hour": "时支起（缺省）", "manualZhi": "选支（zhi）", "manualNum": "数取（num）", "yearZhi": "年支（yearZhi）"}),
        # feigong.js `input.koujing === 'yi' ? 'yi' : 'zheng'`
        "koujing": V("koujing", {"zheng": ("正", "正说", "正口径"), "yi": ("异", "异说", "异口径")},
                     labels={"zheng": "河魁正说（缺省）", "yi": "河魁异说"}),
    },
    "xiaochengtu": {
        "qiguaFa": V("qiguaFa", {"manual": ("手动",), "number": ("两数", "数字", "报数"), "stock": ("股价", "股票"),
                                 "dayan": ("大衍", "大衍筮法"), "time": ("占时", "时间", "梅花时间卦")},
                     labels={"manual": "手动（缺省）", "number": "两数", "stock": "股价", "dayan": "大衍", "time": "占时梅花卦"}),
        "qiguaShu": V("qiguaShu", {"tiandi": ("天地数",), "xiantian": ("先天数", "先天")},
                      labels={"tiandi": "天地数（缺省）", "xiantian": "先天数"}),
        # xiaochengtu.js `input.piKoujing === 'yiwen' ? 'yiwen' : 'zheng'`
        "piKoujing": V("piKoujing", {"zheng": ("正传",), "yiwen": ("异文",)}, labels={"zheng": "正传（缺省）", "yiwen": "异文"}),
    },
    "zhengchuan": {
        "school": V("school", {"tieban": ("铁板", "铁板神数"), "shaozi": ("邵子", "邵子神数"), "dading": ("大定", "大定数"),
                               "liuqin": ("六亲", "六亲数"), "xinyi": ("铁算心易", "心易")},
                    labels={"tieban": "铁板神数（缺省）", "shaozi": "邵子神数", "dading": "大定数", "liuqin": "六亲数", "xinyi": "铁算心易（查询层）"}),
        # zhengchuanShaoziLocal.guaOfRemainder：shang / xia 各一支，其余一律当 zhong
        "yuan": V("yuan", {"shang": ("上元",), "zhong": ("中元",), "xia": ("下元",)},
                  labels={"shang": "上元", "zhong": "中元（缺省）", "xia": "下元"}),
    },
    "canping": {
        # canping.js normalizeMethod：认不出 → 'ming'
        "method": V("method", {"ming": ("明法",), "gu": ("古法",)}, labels={"ming": "明法·月支反向取日宫（缺省）", "gu": "古法·日支为日宫"}),
        "timeAlg": TIME_ALG_WITH_MEAN,
    },
    "heluo": {
        # 标签取上游挂载齿轮（utils/techniqueMountSettings.js heluo）
        "ziShuMode": V("ziShuMode", {"pair": ("成对全取",), "single": ("每支取一",)}, labels={"pair": "成对全取（古本，缺省）", "single": "每支取一"}),
        "jiGongMode": V("jiGongMode", {"manualSanYuan": ("三元表",), "legacy": ("旧法",)},
                        labels={"manualSanYuan": "三元表（缺省）", "legacy": "旧法·性别"}),
        "pureGanKunVariant": V("pureGanKunVariant", {"current": ("通行",), "alt": ("抄本异",)},
                               labels={"current": "通行（节气半年，缺省）", "alt": "抄本异（反向·待核）"}),
        "liunianStep2": V("liunianStep2", {"ying": ("应爻法",), "sequential": ("顺行",)},
                          labels={"ying": "应爻法（缺省）", "sequential": "顺行（初→上）"}),
        "quHuaGong": V("quHuaGong", {"tuWangKunGen": ("土王寄坤艮",), "siFangBoOnly": ("直取四方伯",)},
                       labels={"tuWangKunGen": "土王寄坤艮（缺省）", "siFangBoOnly": "直取四方伯"}),
        "zhiZunEnabled": V("zhiZunEnabled", {1: ("true", "on", "yes", "是", "启用"), 0: ("false", "off", "no", "否", "不启用")},
                           labels={1: "启用三至尊卦（缺省）", 0: "不启用"}),
        "timeAlg": TIME_ALG_WITH_MEAN,
    },
    "yizhangjing": {
        # 标签取上游挂载齿轮（techniqueMountSettings.js yizhangjing）；定月法上游值 nongli = adapter 的 lunar
        "dingYue": V("dingYue", {"lunar": ("nongli", "农历月"), "jieqi": ("节气月",)}, labels={"lunar": "农历月（缺省）", "jieqi": "节气月"}),
        "shunniRule": V("shunniRule", {"yangNanYinNv": ("阳男阴女",), "menShunNvNi": ("男顺女逆",)},
                        labels={"yangNanYinNv": "阳男阴女（缺省）", "menShunNvNi": "男顺女逆"}),
        "mingGongMethod": V("mingGongMethod", {"shiShang": ("时上起命",), "shuZhiMao": ("数至卯",)},
                            labels={"shiShang": "时上起命（缺省）", "shuZhiMao": "数至卯"}),
        "dayunStartAge": V("dayunStartAge", {"mi": ("秘传起运",), "age1": ("1岁连续",)}, labels={"mi": "秘传起运（缺省）", "age1": "1岁连续"}),
        "xiaoxianStart": V("xiaoxianStart", {"ri": ("日柱宫",), "yue": ("月柱宫",)}, labels={"ri": "日柱宫（缺省）", "yue": "月柱宫"}),
        "xiaoxianDir": V("xiaoxianDir", {"chart": ("随盘向",), "always": ("一律顺行",)}, labels={"chart": "随盘向（缺省）", "always": "一律顺行"}),
        "annualMethod": V("annualMethod", {"xiaoxian": ("小限",), "liunian": ("流年十二神",)},
                          labels={"xiaoxian": "小限", "liunian": "流年十二神"}),
        "chongfanKou": V("chongfanKou", {"alpha": ("常见组",), "beta": ("异传组",)}, labels={"alpha": "常见组（缺省）", "beta": "异传组"}),
        "daoTerm": V("daoTerm", {"gui": ("鬼道",), "edao": ("饿鬼道",)}, labels={"gui": "鬼道·修罗道（缺省）", "edao": "饿鬼道·阿修罗道"}),
        "leapRule": V("leapRule", {"half": ("十五折半",), "midnight": ("夜半折半",)}, labels={"half": "十五折半（缺省）", "midnight": "夜半折半"}),
        "gradeSet": V("gradeSet", {"standard": ("主流",), "variant": ("变体",)}, labels={"standard": "主流（缺省）", "variant": "变体·天驿归凶"}),
        "dayunLength": V("dayunLength", {7: ("7年",), 10: ("10年",)}, labels={7: "一宫7年（缺省）", 10: "一宫10年"}),
        "flowShenSet": V("flowShenSet", {"A": ("甲组",), "B": ("乙组",), "C": ("丙组",)},
                         labels={"A": "甲组·太阳系（缺省）", "B": "乙组·六合系", "C": "丙组·岁破系"}),
        "starNaming": V("starNaming", {"A": ("主流",), "B": ("异名",), "C": ("改名",)}, labels={"A": "A·主流（缺省）", "B": "B·异名", "C": "C·改名"}),
        "timeAlg": TIME_ALG_WITH_MEAN,
    },
    # 紫微页只有两档（_ziwei_params 旧写法 `1 if timeAlg in (1, "1") else 0`：2 被悄悄读成真太阳时）
    "ziwei_birth": {"timeAlg": _ZIWEI_TIME_ALG},
    "tongshefa": {axis: _trigram_vocab(axis) for axis in ("taiyin", "taiyang", "shaoyang", "shaoyin")},
    "lingqi": {
        # lingqiSnapshot.lingqiCategoryLabel：认不出 → 「通用」
        "category": V("category", {"general": ("通用",), "career": ("仕途",), "wealth": ("求财",), "marriage": ("婚姻",),
                                   "health": ("疾病",), "travel": ("行人",), "lawsuit": ("官讼",), "home": ("家宅",)},
                      labels={"general": "通用（缺省）", "career": "仕途", "wealth": "求财", "marriage": "婚姻", "health": "疾病",
                              "travel": "行人", "lawsuit": "官讼", "home": "家宅"}),
    },
    "geomancy": {
        # runner 旧写法：`if profile not in _GEOMANCY_PROFILES: profile = "european_classical"`
        "profile": V("profile", {"european_classical": ("欧洲古典",), "european_planetary": ("欧洲行星",), "european_modern": ("欧洲现代",),
                                 "arabic_raml": ("阿拉伯", "raml"), "india_ramal": ("印度", "ramal"), "sikidy": ("马达加斯加",),
                                 "hakata": ("非洲南部",), "greek": ("希腊",)},
                     labels={"european_classical": "欧洲古典（缺省）", "european_planetary": "欧洲行星", "european_modern": "欧洲现代",
                             "arabic_raml": "阿拉伯 raml", "india_ramal": "印度 ramal", "sikidy": "sikidy", "hakata": "hakata", "greek": "希腊"}),
        "readingScope": V("readingScope", {"L1": (), "L2": (), "L3": ()}, labels={"L1": "L1", "L2": "L2", "L3": "L3（缺省）"}),
        "zodiacSystem": V("zodiacSystem", {"classical": ("古典",), "planetary": ("行星",)}, labels={"classical": "古典（缺省）", "planetary": "行星"}),
    },
}


def validate_cn_field(tool: str, field_name: str, value: Any) -> Any:
    vocabulary = CN_VOCABULARIES[tool][field_name]
    if tool == "ziwei_birth" and field_name == "timeAlg":
        return None if value is None or is_blank(value) else field_validator_for(parse_ziwei_time_alg, field_name)(value)
    if tool == "geomancy" and field_name == "profile" and clean_text(value).lower() == "ifa":
        return "ifa"  # 结构对照模式：runner 给专门的拒绝（tool.geomancy_structural_only_unsupported + 文化声明）
    return parse_with(vocabulary, field_name, value)


def parse_int_in_range(field_name: str, low: int, high: int) -> Any:
    """整数 + 闭区间：以前 bazi_inverse.count 越界被悄悄夹到 1–10、读不出就当 3。"""

    def parse(value: Any) -> Parsed:
        number: int | None = None
        if isinstance(value, int) and not isinstance(value, bool):
            number = value
        elif isinstance(value, float) and value.is_integer():
            number = int(value)
        elif isinstance(value, str) and clean_text(value).lstrip("+-").isdigit():
            number = int(clean_text(value))
        if number is None or not low <= number <= high:
            raise FieldIssue(
                "tool.invalid_option", f"{field_name} 要是 {low}–{high} 的整数，收到 {value!r}。",
                f"{field_name} must be an integer from {low} to {high}; got {value!r}.",
                expected_zh=f"{low}–{high} 的整数", expected_en=f"an integer from {low} to {high}", example=low,
                options=[{"value": low, "label": f"最小 {low}"}, {"value": high, "label": f"最大 {high}"}],
            )
        return Parsed(number)

    return parse


def parse_switch(field_name: str) -> Any:
    """布尔开关（true/false、1/0、是/否）。以前 `bool(value)` 把字符串 "false" 读成真。"""
    vocabulary = V(field_name, {1: ("true", "on", "yes", "是"), 0: ("false", "off", "no", "否")}, labels={1: "true", 0: "false"})

    def parse(value: Any) -> Parsed:
        if isinstance(value, bool):
            return Parsed(value)
        return Parsed(bool(vocabulary.parse(value).value))

    return parse


def cn_field_validator(tool: str, *fields: str) -> Any:
    """schema 类体里一行挂上：`_vocab = cn_field_validator("heluo", "ziShuMode", …)`（pydantic BeforeValidator，词表在本模块）。"""
    from pydantic import field_validator

    def _validate(cls: Any, value: Any, info: Any) -> Any:
        return validate_cn_field(tool, info.field_name, value)

    return field_validator(*fields, mode="before")(_validate)


# 梅花易数卦义的经卦码（初→上，1 = 阳），取自引擎 /gua/meiyi 的回包（live 测试逐码对拍）。
MEIYI_TRIGRAM_CODES = {"000": "坤", "001": "艮", "010": "坎", "011": "巽", "100": "震", "101": "离", "110": "兑", "111": "乾"}
_MEIYI_BY_NAME = Vocabulary("name", {code: (name, *TRIGRAM[name]) for code, name in MEIYI_TRIGRAM_CODES.items()},
                            labels={code: name for code, name in MEIYI_TRIGRAM_CODES.items()})


def parse_meiyi_names(value: Any) -> Any:
    """gua_meiyi.name：每一项都要读成三爻经卦码；任何一项读不出 → tool.invalid_option（options = 八个码与卦名）。"""
    from horosa_skill.input_fields import add_input_note
    from horosa_skill.input_normalization import field_issues_error

    items = value if isinstance(value, list) else [value]
    out: list[str] = []
    issues: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        text = clean_text(item) if item is not None else ""
        if text in MEIYI_TRIGRAM_CODES:
            out.append(text)
            continue
        try:
            parsed = _MEIYI_BY_NAME.parse(text)
        except FieldIssue as issue:
            issues.append({"field": f"name[{index}]", "code": issue.code, "got": item,
                           "expected": f"{issue.expected_zh} / {issue.expected_en}", "example": "111", "ask_user": False,
                           "options": issue.options, "message": f"梅花卦义只认三爻经卦码或经卦名，认不出 {item!r}。 / "
                                                                f"MeiYi only takes a three-line trigram code or trigram name; {item!r} is not one."})
            continue
        out.append(parsed.value)
        add_input_note(f"`name[{index}]`「{item}」按经卦码 {parsed.value}（{MEIYI_TRIGRAM_CODES[parsed.value]}）读。",
                       f"`name[{index}]` '{item}' was read as trigram code {parsed.value} ({MEIYI_TRIGRAM_CODES[parsed.value]}).")
    if issues:
        raise field_issues_error(issues)
    return out


# 六十四卦（初→上，1 = 阳）：data/gua64_names.json 由 vendored 上游 GuaConst.Gua64 生成（六爻 guaByName 同表同简名规则），
# tests/test_gua_desc_names.py 在 node 在场时与 JS 表逐行对拍。
_GUA64_PATH = Path(__file__).parent / "data" / "gua64_names.json"


@cache
def gua64_rows() -> tuple[tuple[str, str, str], ...]:
    return tuple(tuple(row) for row in json.loads(_GUA64_PATH.read_text(encoding="utf-8"))["rows"])


def parse_gua_desc_names(value: Any) -> Any:
    """gua_desc.name：每一项读成六位卦码（六位 0/1 码原样；全名「水火既济」、简名「既济」「乾」、繁体、带「卦」字都认）。
    认不出 → tool.invalid_option（options = 最接近的卦名，details.accepted = 六十四卦全表）。以前认不出的名字原样发给后端，
    [卦象] 印一行「X：无」或干脆没有，ok=true（v0.50.0 深审余项）。"""
    import difflib

    from horosa_skill.input_fields import add_input_note
    from horosa_skill.input_normalization import field_issues_error
    from horosa_skill.textscript import fold_to_simplified

    rows = gua64_rows()
    by_name = {**{full: (code, full) for code, full, _short in rows}, **{short: (code, full) for code, full, short in rows}}
    labels = [*by_name]
    items = value if isinstance(value, list) else [value]
    out: list[str] = []
    issues: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        text = clean_text(item) if item is not None else ""
        if re.fullmatch(r"[01]{6}", text):
            out.append(text)
            continue
        hit = None
        for candidate in dict.fromkeys((text, fold_to_simplified(text))):
            key = candidate[:-1] if candidate.endswith("卦") and len(candidate) > 1 else candidate
            hit = by_name.get(candidate) or by_name.get(key)
            if hit:
                break
        if hit is None:
            close = difflib.get_close_matches(fold_to_simplified(text), labels, n=5, cutoff=0.3)
            issues.append({"field": f"name[{index}]", "code": "tool.invalid_option", "got": item,
                           "expected": "六位 0/1 码（初→上，1 阳）或卦名（全名 水火既济 / 简名 既济、乾）/ six 0/1 digits or a hexagram name",
                           "example": "111111", "ask_user": False,
                           "options": [{"value": by_name[name][0], "label": by_name[name][1]} for name in close],
                           "message": f"认不出卦：{item!r}（六十四卦里没有这个名字）。 / Unrecognized hexagram: {item!r} (no such name among the 64)."})
            continue
        out.append(hit[0])
        add_input_note(f"`name[{index}]`「{item}」按卦码 {hit[0]}（{hit[1]}）读。", f"`name[{index}]` '{item}' was read as hexagram code {hit[0]} ({hit[1]}).")
    if issues:
        raise field_issues_error(issues, extra_details={"accepted": [{"value": code, "label": full} for code, full, _ in rows]},
                                 tool_name="gua_desc")
    return out
