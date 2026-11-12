"""意图分类：一句话没有点名任何技法时，按「用户想干什么」分流，而不是拿出生数据起一张本命盘了事。

v0.49 之前 `select_tools` 的兜底是「没命中关键词 + 有出生数据 → chart」。于是「我和他合不合」「明天适合搬家吗」
「今年运势」「帮我算算」全部返回一张西洋本命盘，ok=true、warnings 为空——回答的不是用户问的那件事。

这里是一张表（纯数据 + 正则，离线、确定性），在关键词路由**之后**才用：

- `relationship` 两个人的事 → 合盘（披露为缺省选择；缺第二个人由载荷规划去要）
- `date_selection` 找日子 → 择日一族的候选 + 要窗口 / 用事 / 条件
- `calendar` 节气名 → 全年节气（查询里要有年份）
- `life_timing` 运势 / 什么时候 → 推运候选，让用户挑传统
- `divination` 就一件具体的事问成不成 → 起课 / 占卜候选，不替用户选流派
- `natal_choice` 「算命 / 命盘」这种没说流派的 → 本命候选
- `out_of_scope` 手相 / 风水 / 起名 / 个股买卖 → 目录里没有，明说，并列出目录覆盖什么

表里的词全部写成归一形态（简体、半角、小写；见 query_text.normalize_query）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from horosa_skill.engine.synonyms import display_name
from horosa_skill.errors import bilingual

CODE_NO_MATCH = "dispatch.no_matching_tool"
CODE_CHOICE = "dispatch.technique_choice_required"
CODE_OUT_OF_SCOPE = "dispatch.out_of_scope"


@dataclass(frozen=True)
class IntentClass:
    key: str
    words: tuple[str, ...]
    patterns: tuple[str, ...]
    candidates: tuple[str, ...]
    ask_zh: str
    ask_en: str
    # 合参（horosa_hecan）没点名技法时按这一类缺省起的一对技法（传统互参：三式互参、八字紫微互证）；空 = 这一类不替用户配对。
    hecan_pair: tuple[str, ...] = ()
    label_zh: str = ""
    label_en: str = ""

    def matches(self, text: str) -> bool:
        return any(word in text for word in self.words) or any(re.search(p, text) for p in self.patterns)


# 起卦通用说法：起卦 / 卜一卦 / 算个卦 / 摇卦……只说「起卦」没说哪一种。
CAST_GUA_PATTERN = r"[起卜算占摇求问打测][一个支]{0,2}卦|卦占|cast (a |an )?(hexagram|gua)|divine (a |an )?hexagram"

# 目录里没有的东西。键 = 类别，值 = (词表, 中文名, 英文名)。
OUT_OF_SCOPE: dict[str, tuple[tuple[str, ...], str, str]] = {
    "palmistry": (("手相", "掌纹", "palm reading", "palmistry"), "手相", "palmistry"),
    "physiognomy": (("面相", "骨相", "摸骨", "face reading", "physiognomy"), "面相", "face reading"),
    "fengshui": (("风水", "阳宅", "阴宅", "feng shui", "fengshui"), "风水", "feng shui"),
    "naming": (("起名", "取名", "改名", "姓名学", "测名", "baby name", "name analysis"), "起名 / 姓名学", "name analysis"),
    "character": (("测字", "拆字"), "测字", "character divination"),
    "dream": (("解梦", "梦见", "dream interpretation", "dreamt", "dreamed"), "解梦", "dream interpretation"),
    "finance": (
        ("股票", "炒股", "买股", "个股", "基金", "比特币", "加密货币", "彩票", "开奖", "双色球",
         "stock", "stocks", "shares", "crypto", "bitcoin", "lottery"),
        "个股 / 基金 / 彩票的买卖建议", "buy / sell advice on securities or lottery picks",
    ),
}
# 「should I buy NVDA」：动词 + 全大写代码（在未小写的原文上匹配）。
FINANCE_TICKER_PATTERN = r"\b(?:buy|sell|short|hold)\b[^.?!]*\b[A-Z]{2,5}\b"

COVERAGE: tuple[tuple[str, str], ...] = (
    ("西洋占星：本命盘与衍生盘、二十多种推运、卜卦占星、合盘、占星地图", "Western astrology: natal and derived charts, 20+ predictive systems, horary, synastry, astrocartography"),
    ("中式命理：八字、紫微斗数、七政四余、河洛理数、一掌经、神数十四种", "Chinese natal systems: BaZi, Zi Wei Dou Shu, Qi Zheng Si Yu, He Luo Li Shu, 14 shenshu systems"),
    ("起课占卜：大六壬、奇门遁甲、太乙、金口诀、六爻、小六壬、灵棋经、天文地占、塔罗", "Divination: Da Liu Ren, Qi Men Dun Jia, Tai Yi, Liu Yao, Xiao Liu Ren, Lingqi, geomancy, tarot"),
    ("择日：十种条件搜索（天星 / 奇门 / 黄历 / 八字 / 太乙 / 紫微 / 六壬 / 三式 / 七政 / 印度）与候选时刻评估", "Date selection: ten condition searches plus single-moment election"),
    ("历法：黄历、通书、万年历、农历换算（公历→农历）、节气", "Calendar: almanac, month calendar, Gregorian→lunar conversion, solar terms"),
)

RELATIONSHIP = IntentClass(
    key="relationship",
    words=("合婚", "配婚", "合不合", "配不配", "般配", "我和他", "我和她", "我跟他", "我跟她", "我们俩", "我俩", "两个人",
           "两人", "compatibility", "compatible", "my partner", "relationship with", "my boyfriend", "my girlfriend",
           "my husband", "my wife"),
    patterns=(),
    candidates=("relative",),
    ask_zh="", ask_en="",
)

DATE_SELECTION = IntentClass(
    key="date_selection",
    words=("择日", "择吉", "择时", "选日子", "挑日子", "选个日子", "挑个日子", "看日子", "好日子", "吉日", "哪天", "哪一天",
           "哪个日子", "什么日子", "宜不宜", "wedding date", "lucky day"),
    patterns=(
        r"适[合宜][^,，。?？]{0,10}[吗么不]",
        r"(pick|choose|find|select) (a|an|the) ((good|lucky|auspicious|wedding|moving|opening) )?(date|day)",
        r"auspicious (date|day|time)",
        r"(good|best|lucky) (day|date|time) (to|for)",
    ),
    candidates=("huanglizeri", "tianxing", "qimenzeri", "bazizeri", "election", "huangli", "tongshu"),
    ask_zh="想在哪段时间里找日子（起止日期）、做什么事、要满足什么条件？按哪一种择日法：黄历择吉 / 天星择日 / 奇门择日 / 八字择时…；"
           "如果是评估一个已经定好的候选时刻，用「择日」（候选时刻盘）；只看某一天的宜忌，用「老黄历」或「通书」。",
    ask_en="Which date range should be searched, for what purpose, and under which conditions? Choose a method: almanac, "
           "celestial (tianxing), Qi Men, BaZi…; to evaluate one already-chosen moment use the election chart; for one "
           "day's do's and don'ts use the almanac (huangli) or tongshu.",
    # 择日不配对：每种择日法的条件树词表不同，同一份 conditions 交给两种方法是错的。
    label_zh="择日", label_en="date selection",
)

# 强时运词：出现就是问「什么时候 / 运势」，先于「会不会」类判断。
LIFE_TIMING_STRONG: tuple[str, ...] = (
    "大运", "流年", "运势", "运程", "运气", "流月", "流日", "什么时候", "何时", "几时", "年运", "财运", "事业运", "桃花运", "感情运",
    "forecast", "outlook", "transit", "when will", "when do", "when is my", "horoscope for",
)

LIFE_TIMING = IntentClass(
    key="life_timing",
    words=LIFE_TIMING_STRONG + ("今年", "明年", "后年", "这个月", "下个月", "本月", "this year", "next year", "this month",
                                "next month"),
    patterns=(),
    candidates=("bazi_direct", "ziwei_birth", "solarreturn", "profection", "firdaria", "ephemeris", "liureng_runyear"),
    ask_zh="看运势用哪一派？八字直断（大运流年）/ 紫微斗数 / 太阳返照 / 小限 / 法达 / 星历（行运）/ 六壬行年…；"
           "若是就一件具体的事问应期，也可以改用起课占卜（六爻 / 奇门遁甲 / 大六壬）。",
    ask_en="Which system should read the timing? BaZi (decade and annual luck), Zi Wei Dou Shu, solar return, profection, "
           "firdaria, ephemeris (transits), Liu Ren annual…; for the timing of one concrete matter a divination "
           "technique (Liu Yao, Qi Men, Da Liu Ren) also fits.",
    hecan_pair=("bazi_direct", "ziwei_birth"), label_zh="运势", label_en="life timing",
)

DIVINATION = IntentClass(
    key="divination",
    words=("能不能", "会不会", "能否", "是否", "可不可以", "可以吗", "行不行", "该不该", "要不要", "好不好", "能成", "成不成",
           "有没有戏", "顺不顺利", "吉凶", "问事", "占问", "占卜", "算一下", "测一下", "divination", "yes or no", "oracle"),
    patterns=(
        r"[吗么][?？!！。 ]*$",
        r"\bwill (i|it|he|she|we|they|my|the|this)\b",
        r"\bshould (i|we)\b",
        r"\bis it (a good|wise|ok|okay|safe)\b",
        r"\bcan i\b",
        r"\b(does|do|is|did) (he|she|they)\b",
    ),
    candidates=("sixyao", "qimen", "liureng_gods", "xiaoliuren", "tarot", "horary", "lingqi", "geomancy"),
    ask_zh="就这件事起课 / 占卜，用哪一种？六爻 / 奇门遁甲 / 大六壬 / 小六壬 / 塔罗 / 卜卦占星 / 灵棋经 / 天文地占。"
           "各家结论可能不同，请指定一种（或用合参同时看几种）。",
    ask_en="Which divination technique should answer this? Liu Yao, Qi Men Dun Jia, Da Liu Ren, Xiao Liu Ren, tarot, "
           "horary astrology, Lingqi, geomancy. They can disagree, so name one (or use hecan to run several).",
    hecan_pair=("liureng_gods", "qimen"), label_zh="起课占断（三式互参）", label_en="divination (Liu Ren + Qi Men)",
)

BUGUA = IntentClass(
    key="divination",
    words=(),
    patterns=(),
    candidates=("sixyao", "horary"),
    ask_zh="「卜卦」指哪一种？六爻起卦（中式，按占时或摇卦起卦）/ 卜卦占星（西洋，按提问时刻起盘）。",
    ask_en="Which kind of 卜卦? Liu Yao (Chinese hexagram cast by the moment or coins) or horary astrology "
           "(Western chart of the question moment)?",
    hecan_pair=("sixyao", "horary"), label_zh="卜卦（六爻 + 卜卦占星）", label_en="卜卦 (Liu Yao + horary)",
)

NATAL_CHOICE = IntentClass(
    key="natal_choice",
    words=("算命", "命盘", "命理", "看命", "批命", "算算", "算一算", "我的命", "命格", "排盘", "起盘", "fortune", "destiny",
           "life reading", "my reading", "read my"),
    patterns=(r"[批算看排]一?[个张]?命", r"[排起]一?[个张]?盘"),
    candidates=("bazi_birth", "ziwei_birth", "chart", "guolao_chart", "india_chart"),
    ask_zh="按哪一种命理看？八字 / 紫微斗数 / 西洋本命盘 / 七政四余 / 印度占星。各家起盘口径不同，请指定一种（或用合参同时看几种）。",
    ask_en="Which natal system? BaZi, Zi Wei Dou Shu, Western natal chart, Qi Zheng Si Yu, Vedic. Their conventions "
           "differ, so name one (or use hecan to run several).",
    hecan_pair=("bazi_birth", "ziwei_birth"), label_zh="命理（八字紫微互证）", label_en="natal reading (BaZi + Zi Wei)",
)

# 二十四节气名：单独出现时是历法查询（「2027年立春是什么时候」），归全年节气。
SOLAR_TERM_NAMES: tuple[str, ...] = (
    "立春", "雨水", "惊蛰", "春分", "清明", "谷雨", "立夏", "小满", "芒种", "夏至", "小暑", "大暑",
    "立秋", "处暑", "白露", "秋分", "寒露", "霜降", "立冬", "小雪", "大雪", "冬至", "小寒", "大寒",
)

# 明确指西洋本命盘的说法（星盘的属性：上升 / 太阳星座……）。只在别的技法都没命中时兜底。
NATAL_WESTERN_WORDS: tuple[str, ...] = ("horoscope", "星盘", "出生盘", "astrology chart")
NATAL_WESTERN_INFERRED: tuple[str, ...] = (
    "上升星座", "上升点", "上升", "太阳星座", "月亮星座", "rising sign", "ascendant", "sun sign", "moon sign",
)

# 农历 → 公历：目录里只有公历 → 农历（nongli_time）与月历（calendar_month）。
LUNAR_TO_SOLAR_PATTERN = (
    r"(农历|阴历|旧历)[^,，。?？]{0,6}?闰?[正一二三四五六七八九十冬腊\d]{1,2}月(初|十|廿|卅|二十|三十|\d)"
    r"|lunar (new year|month|\d|[a-z]+ \d)|lunar .* to (gregorian|solar)"
    r"|(mid-autumn|dragon boat|chinese new year|lantern festival).*(when|date)|(when|date).*(mid-autumn|dragon boat|chinese new year|lantern festival)"
    r"|(春节|中秋|端午|元宵|七夕|重阳|除夕|腊八)[^,，。]{0,8}(哪天|哪一天|几号|几月|什么时候|公历|阳历)"
)
BAZI_WORDS: tuple[str, ...] = ("八字", "四柱", "生辰", "bazi", "ba zi", "four pillars")
MATCHING_WORDS: tuple[str, ...] = ("合婚", "配婚", "合盘", "合不合", "配对", "compatib")

CHOICE_CLASSES: tuple[IntentClass, ...] = (DATE_SELECTION, LIFE_TIMING, DIVINATION, NATAL_CHOICE)

# 候选的一句话说明（给 AI 客户端转述用）。没列的技法只给名字。
CANDIDATE_NOTES: dict[str, tuple[str, str]] = {
    "huanglizeri": ("在一段时间里按黄历条件找日子", "search a date range by almanac conditions"),
    "tianxing": ("在一段时间里按天象条件找时刻", "search a date range by celestial conditions"),
    "qimenzeri": ("在一段时间里找符合条件的奇门局", "search a date range for Qi Men patterns"),
    "bazizeri": ("在一段时间里按四柱条件找时辰", "search a date range by four-pillar conditions"),
    "election": ("评估一个已定的候选时刻（不是搜索）", "evaluate one chosen moment (not a search)"),
    "huangli": ("看某一天的宜忌", "one day's do's and don'ts"),
    "tongshu": ("按通书流派看某一天做某事", "one day for one activity by tongshu school"),
    "bazi_direct": ("八字大运流年", "BaZi decade and annual luck"),
    "ziwei_birth": ("紫微斗数命盘（含大限流年）", "Zi Wei Dou Shu chart with decade and annual periods"),
    "solarreturn": ("西洋太阳返照（年运盘）", "solar return for a year"),
    "profection": ("西洋小限（年主星）", "annual profection"),
    "firdaria": ("法达（波斯行星期）", "firdaria planetary periods"),
    "ephemeris": ("星历与行运触发本命点的时刻", "ephemeris and transit hits to the natal chart"),
    "liureng_runyear": ("大六壬行年", "Da Liu Ren annual figure"),
    "sixyao": ("六爻起卦（占时或摇卦）", "Liu Yao hexagram cast"),
    "qimen": ("奇门遁甲时家局", "Qi Men Dun Jia chart of the moment"),
    "liureng_gods": ("大六壬起课", "Da Liu Ren figure of the moment"),
    "xiaoliuren": ("小六壬掐指", "Xiao Liu Ren quick cast"),
    "tarot": ("塔罗牌阵", "tarot spread"),
    "horary": ("卜卦占星（提问时刻盘）", "horary chart of the question moment"),
    "lingqi": ("灵棋经", "Lingqi oracle"),
    "geomancy": ("天文地占", "astrological geomancy"),
    "bazi_birth": ("八字排盘", "BaZi four pillars"),
    "chart": ("西洋本命盘", "Western natal chart"),
    "guolao_chart": ("七政四余", "Qi Zheng Si Yu chart"),
    "india_chart": ("印度占星本命盘", "Vedic natal chart"),
    "relative": ("西洋合盘（两个人）", "Western synastry / composite for two people"),
    "calendar_month": ("万年历：整月逐日公历 / 农历对照", "month calendar with lunar dates per day"),
    "nongli_time": ("公历 → 农历换算", "Gregorian → lunar conversion"),
    "jieqi_year": ("全年二十四节气时刻", "the year's 24 solar terms"),
}


def candidate_details(names: list[str] | tuple[str, ...]) -> list[dict[str, str]]:
    from horosa_skill.engine.registry import TOOL_DEFINITIONS  # 延迟：registry 很重

    rows: list[dict[str, str]] = []
    for name in names:
        definition = TOOL_DEFINITIONS.get(name)
        if definition is None:
            continue
        note = CANDIDATE_NOTES.get(name)
        row = {"tool": name, "mcp_name": definition.mcp_name, "name": display_name(name)}
        if note:
            row["what"] = bilingual(note[0], note[1])
        rows.append(row)
    return rows


def out_of_scope_category(text: str, raw_query: str) -> tuple[str, str, str] | None:
    for key, (words, zh, en) in OUT_OF_SCOPE.items():
        if any(word in text for word in words):
            return key, zh, en
    if re.search(FINANCE_TICKER_PATTERN, raw_query or ""):
        _words, zh, en = OUT_OF_SCOPE["finance"]
        return "finance", zh, en
    return None


def choice_recovery(*, intent: IntentClass | None, names: list[str], prompt_zh: str, prompt_en: str, reason: str) -> dict:
    """路由拒绝统一的 agent_recovery：一条可直接转给用户的双语追问 + 一个带选项的问题（elicitation 表单可用）。"""
    labels = [display_name(name) for name in names]
    return {
        "must_ask_user": True,
        "kind": "input",
        "reason": reason,
        "prompt_to_user": bilingual(prompt_zh, prompt_en),
        "ask_if_missing": [
            {
                "field": "target technique",
                "question": bilingual("用哪一种技法？", "Which technique should be used?"),
                "options": labels,
                "values": list(names),
            }
        ] if names else [],
        "safe_defaults": [],
        "do_not_assume": [
            "Do not pick a technique for the user: schools disagree, and the choice changes the answer.",
            "Do not fall back to a natal chart because birth data happens to be present.",
        ],
        "next_action": "ask_user_then_call_chosen_tool" if names else "tell_user_not_supported",
        "intent_class": intent.key if intent else None,
    }
