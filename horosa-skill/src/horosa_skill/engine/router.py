from __future__ import annotations

import re
from dataclasses import dataclass, field

from horosa_skill.engine import intents
from horosa_skill.engine.query_text import normalize_query
from horosa_skill.engine.synonyms import display_name, synonym_scores
from horosa_skill.errors import DispatchResolutionError, bilingual
from horosa_skill.schemas.tools import DispatchInput


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


# 择日搜索族（v0.36.0 B2 补 8 支）：词面都含基底技法名（「八字择日」含「八字」）→ 基底规则必须排除，
# 否则一句话点亮两个工具；generic「择日」→ election 也要排除这些词面。
_ZERI_PHRASES: dict[str, list[str]] = {
    "huanglizeri": ["黄历择吉", "黄历择日", "通书择日", "huanglizeri", "almanac election"],
    "bazizeri": ["八字择时", "八字择日", "bazizeri", "bazi election"],
    "taiyizeri": ["太乙择时", "太乙择日", "taiyizeri", "taiyi election"],
    "ziweizeri": ["紫微择时", "紫微择日", "ziweizeri", "ziwei election"],
    "liurengzeri": ["六壬择时", "六壬择日", "liurengzeri", "liureng election"],
    "sanshizeri": ["三式择时", "三式择日", "三式合一择时", "sanshizeri", "sanshi election"],
    "qizhengzeri": ["七政择时", "七政四余择时", "qizhengzeri"],
    "indiazeri": ["印度择时", "印度择日", "吠陀择日", "muhurta", "indiazeri"],
}
_ALL_ZERI_WORDS: list[str] = [word for words in _ZERI_PHRASES.values() for word in words]

# 上游 v3.11 星运四键的分派词。互斥要点：回归轴是**逐年时间轴**——「太阳返照时间轴」含「太阳返照」、
# 「日月返照年表」含「月返」，不排除就一句话同时点亮 solarreturn/lunarreturn；产前朔望 ≠ 星历的「朔望弦」；
# 二次推运按词面会与恒星/赤纬/月相三支推运撞车（各有工具），故排除这些限定词。星历排除巴比伦的「数理星历」段名。
_EPHEMERIS_WORDS = ["星历", "行星入座", "入座时间", "留逆", "朔望弦", "ephemeris"]
_RETURNTIMELINE_WORDS = ["回归轴", "返照时间轴", "返照年表", "返照轴", "return timeline", "returntimeline"]
_PRENATAL_SYZYGY_WORDS = ["产前朔望", "产前新月", "产前满月", "prenatal syzygy", "prenatal lunation", "prenatalsyzygy"]
_PROG_WORDS = [
    "二次推运", "三次推运", "小推运", "回归黄道推运",
    "secondary progression", "tertiary progression", "minor progression", "progressed chart",
]
_PROG_EXCLUDE = ["恒星", "印度", "vedic", "sidereal", "赤纬", "jayne", "declination", "月相", "lunation"]
# 推运图族四法（上游 v3.13.0 之后）。「jay」不能单列：它是「jayne」（赤纬推运）的前缀。
_JAY_WORDS = ["周日小限", "jay profection", "jayprofection", "diurnal profection"]
_NEROMAN_WORDS = ["演进推运", "neroman", "néroman", "evolved direction", "演进弧"]
_MICHON_WORDS = ["双黄道", "michon", "double zodiac", "回归恒星叠合"]
_BEZZA_WORDS = ["bezza", "bezzafigure", "directed figure", "推运图(bezza)"]


@dataclass
class RouteResult:
    """路由结果：选中的技法 + 「这是缺省选择，不是用户点名的」之类必须披露的说明。"""

    tools: list[str]
    warnings: list[str] = field(default_factory=list)
    intent_class: str | None = None


def select_tools(request: DispatchInput) -> list[str]:
    """兼容入口：只要技法名（未命中 / 需选择 / 超出范围都抛 DispatchResolutionError）。"""
    return route(request).tools


def route(request: DispatchInput) -> RouteResult:
    """确定性、离线、表驱动：先按技法关键词，再按意图类（engine/intents.py），都不中就结构化拒绝。

    v0.49 之前没命中关键词且带出生数据时一律起西洋本命盘（「我和他合不合」也是）；现在出生数据不再参与选技法。
    """
    raw_query = request.query or ""
    text = normalize_query(raw_query)
    selected: list[str] = []
    warnings: list[str] = []
    is_zeri = _contains_any(text, _ALL_ZERI_WORDS)

    def add(tool_name: str) -> None:
        if tool_name not in selected:
            selected.append(tool_name)

    def disclose(tool_name: str, why_zh: str, why_en: str) -> None:
        warnings.append(bilingual(
            f"这句话没有点名技法，按「{why_zh}」缺省选了{display_name(tool_name)}（{tool_name}）；用户要别的技法请直接点名。",
            f"The query names no technique; {display_name(tool_name)} ({tool_name}) was chosen as the default for "
            f"{why_en}. Name another technique to use it instead.",
        ))

    # 八字合婚：目录里没有「两份八字对合」的技法——明说，不要退到单人八字或西洋合盘假装做了。
    if _contains_any(text, intents.BAZI_WORDS) and _contains_any(text, intents.MATCHING_WORDS):
        _refuse_not_in_catalogue(
            text,
            what_zh="八字合婚（两份八字对合）", what_en="BaZi marriage matching (two BaZi charts compared)",
            nearest=["bazi_birth", "relative"],
            note_zh="可以分别给两个人各排一张八字（八字排盘 ×2）再对照，或改用西洋合盘（合盘）。",
            note_en="Run a BaZi chart for each person and compare them, or use Western synastry (relative) instead.",
        )
    # 农历 → 公历：目录只有公历 → 农历（农历换算）和整月对照（万年历）。
    if re.search(intents.LUNAR_TO_SOLAR_PATTERN, text):
        _refuse_not_in_catalogue(
            text,
            what_zh="农历 → 公历换算（某个农历日是公历哪天）", what_en="lunar → Gregorian lookup (which Gregorian day a lunar date falls on)",
            nearest=["calendar_month", "nongli_time"],
            note_zh="可以用万年历（calendar_month）查那个月逐日的公历 / 农历对照，自己找到对应的那一天；农历换算只做公历 → 农历。",
            note_en="Use the month calendar (calendar_month) for the month in question and find the day in its per-day "
                    "Gregorian / lunar table; nongli_time only converts Gregorian → lunar.",
        )

    if _contains_any(text, ["紫微", "ziwei", "zi wei", "purple star", "斗数"]) and not is_zeri and not _contains_any(
        text, ["紫微规则", "斗数规则", "格局规则", "ziwei rules", "ziwei_rules", "策天", "飞星紫微", "cetian"]
    ):
        add("ziwei_birth")
    if _contains_any(text, ["紫微规则", "斗数规则", "格局规则", "ziwei rules", "ziwei_rules"]):
        add("ziwei_rules")
    if _contains_any(text, ["八字反查", "反推八字", "四柱反推", "干支反查", "反推出生", "inverse bazi", "reverse bazi", "bazi_inverse"]):
        add("bazi_inverse")
    elif _contains_any(text, ["八字", "bazi", "ba zi", "四柱", "four pillars"]) and not is_zeri:
        if _contains_any(text, ["直断", "direct", "大运", "流年"]):
            add("bazi_direct")
        else:
            add("bazi_birth")
    # 小六壬 含「六壬」二字 → 大六壬分支须排除，否则「小六壬测走失」误路由 liureng（同「卜卦含卦字」先例）。
    if (
        _contains_any(text, ["六壬", "liureng", "liu ren"])
        and not _contains_any(text, ["小六壬", "xiaoliuren", "xiao liu ren", "金口诀", "jinkou"])
        and not is_zeri
    ):
        if _contains_any(text, ["年运", "runyear", "行年"]):
            add("liureng_runyear")
        else:
            add("liureng_gods")
    if _contains_any(text, ["小六壬", "xiaoliuren", "xiao liu ren"]):
        add("xiaoliuren")
    if _contains_any(text, ["飞宫", "小奇门", "feigong"]):
        add("feigong")
    if _contains_any(text, ["小成图", "xiaochengtu"]):
        add("xiaochengtu")
    # 皇极轨策：用「轨策」全词，禁裸「皇极」（皇极经世=wangji 神数，键名分叉不可混）。
    if _contains_any(text, ["皇极轨策", "轨策", "guice"]):
        add("guice")
    # 择日搜索族（上游 v3.7.x）：在时间窗内**找**时刻，与「评一个候选时刻」的 election 是两回事。
    if _contains_any(text, ["奇门择日", "qimenzeri", "奇门找局", "找局"]):
        add("qimenzeri")
    if _contains_any(text, ["天星择日", "征象搜索", "tianxing"]):
        add("tianxing")
    # 七政择日动盘：单时刻十一曜山位/方位 + 日月食/方位搜索（与「窗口搜时刻」的 tianxing 两回事）。
    if _contains_any(text, ["七政择日", "择日动盘", "择日双轮", "方位搜索", "日食", "月食", "二十四山方位", "qizhengelection"]):
        add("qizhengelection")
    # 生时校正：KP 法扫描候选出生时刻（与「出生时间不确定要不要校正」一类问法都指这里）。
    if _contains_any(text, ["生时校正", "出生时间校正", "校时", "rectify", "rectification", "不知道几点出生", "出生时间不准"]):
        add("india_rectify")
    # 行星周期：世运两星合冲时间轴（「木土合相」「土冥周期」一类问法）。
    if _contains_any(text, ["行星周期", "木土合", "土冥", "天海", "大会合", "conjunction cycle", "planetcycles", "planet cycles"]):
        add("planet_cycles")
    # 出生节气窗：定位出生前后节气（「我出生在哪个节气」「距立春几天」）。
    if _contains_any(text, ["出生节气", "节气窗", "哪个节气出生", "哪个节气", "距节", "jieqi birth", "jieqi_birth"]):
        add("jieqi_birth")
    # 飞宫小奇门 含「奇门」二字 → 奇门遁甲分支须排除，否则「飞宫小奇门问出行」误路由 qimen。
    # 「奇门择日」同理：它有自己的工具，落到 qimen 会给出一张单点盘而不是一段搜索结果。
    if (
        _contains_any(text, ["奇门", "qimen", "qi men"])
        and not _contains_any(text, ["飞宫", "小奇门", "feigong", "奇门择日", "qimenzeri", "找局"])
        and not is_zeri
    ):
        add("qimen")
    if _contains_any(text, ["太乙", "taiyi", "太一", "tai yi"]) and not is_zeri:
        add("taiyi")
    if _contains_any(text, ["金口诀", "jinkou"]):
        add("jinkou")
    if _contains_any(text, ["宿占", "宿盘", "suzhan"]):
        add("suzhan")
    if _contains_any(text, ["六爻", "易卦", "sixyao", "guazhan", "liuyao", "liu yao", "i ching", "yi jing", "周易", "摇卦", "铜钱卦", "金钱卦"]):
        add("sixyao")
    if _contains_any(text, ["统摄法", "tongshefa"]):
        add("tongshefa")
    # 灵棋经：用「灵棋」全词。禁裸「棋」——它会把「奇门棋盘」这类说法误点亮；也别写裸「经」
    # （皇极经世/一掌经/太玄经全在射程内）。互斥检查：本词不与任何既有分派词重叠。
    if _contains_any(text, ["灵棋", "lingqi"]):
        add("lingqi")
    if _contains_any(text, ["参评数", "邵子", "金锁银匙", "canping"]) and not _contains_any(
        text, ["正传", "zhengchuan", "邵子神数", "邵子数", "shaozi"]
    ):
        add("canping")
    if _contains_any(text, ["河洛理数", "河洛", "heluo", "he luo"]):
        add("heluo")
    if _contains_any(text, ["调波盘", "调波", "谐波盘", "harmonic"]):
        add("harmonic")
    if _contains_any(text, ["三式合一", "sanshi", "sanshiunited"]) and not is_zeri:
        add("sanshiunited")
    if _contains_any(text, ["节气", "jieqi", "solar terms", "solar term"]) and not _contains_any(
        text, ["出生节气", "节气窗", "哪个节气出生", "哪个节气", "jieqi_birth", "jieqi birth"]
    ):
        add("jieqi_year")
    if _contains_any(text, ["农历", "nongli", "阴历", "lunar date", "chinese calendar date", "chinese date"]):
        add("nongli_time")
    # 梅花易数：目录里的「梅花易数」是按卦名查梅易断语（gua_meiyi），不是起卦；载荷规划缺卦名时会明说并指向六爻。
    if _contains_any(text, ["梅花易数", "梅花易", "梅易", "梅花", "meiyi", "meihua", "mei hua"]):
        add("gua_meiyi")
    # 卦义查询：只在「问卦的意思」时；「起一卦 / 卜一卦」是起卦，不是查卦辞（v0.49 前会落到 gua_desc 或西洋卜卦）。
    elif (_contains_any(text, ["卦"]) or re.search(r"\b(gua|hexagram)\b", text)) and _contains_any(
        text, ["卦义", "卦辞", "爻辞", "卦象", "什么意思", "含义", "意思", "解释", "meaning", "what does"]
    ) and not re.search(intents.CAST_GUA_PATTERN, text):
        add("gua_desc")
    if _contains_any(text, ["合盘", "合个盘", "合一个盘", "关系盘", "relative", "synastry", "composite", "配对盘"]):
        add("relative")
    is_return_timeline = _contains_any(text, _RETURNTIMELINE_WORDS)
    if _contains_any(text, ["solar return", "solarreturn", "太阳返照"]) and not is_return_timeline:
        add("solarreturn")
    if _contains_any(text, ["lunar return", "lunarreturn", "月返"]) and not is_return_timeline:
        add("lunarreturn")
    if _contains_any(text, ["solar arc", "solararc", "太阳弧"]):
        add("solararc")
    if _contains_any(text, ["法达", "firdaria"]):
        add("firdaria")
    if _contains_any(text, ["十年大运", "decennials", "decennial"]):
        add("decennials")
    if _contains_any(text, ["primary direction", "pdchart", "pd ", "本初方向", "主限"]):
        if _contains_any(text, ["chart", "盘", "chart view"]):
            add("pdchart")
        else:
            add("pd")
    # 「周日小限」（Jay）含「小限」二字、「diurnal profection」含 profection → 排除，否则一句话点亮两个工具。
    if _contains_any(text, ["profection", "小限"]) and not _contains_any(text, _JAY_WORDS):
        add("profection")
    # 「流年」是中式通用词（八字直断/紫微/六壬都用）：不再兜底成西占指定年推运，没有别的技法命中时归意图类「运势」让用户挑。
    if _contains_any(text, ["given year", "givenyear"]):
        add("givenyear")
    if _contains_any(text, ["zodiacal release", "zr"]):
        add("zr")
    if _contains_any(text, ["印度", "india", "vedic", "jyotish", "kundli", "吠陀"]) and not is_zeri and not _contains_any(
        text, ["恒星推运", "印度推运", "vedicprog", "vedic progression", "sidereal progression", "生时校正", "rectif", "校时"]
    ):
        add("india_chart")
    if _contains_any(text, ["七政四余", "guolao", "果老"]) and not is_zeri and not _contains_any(
        text, ["张果", "qizhengkin", "七政择日", "择日动盘", "qizhengelection"]
    ):
        add("guolao_chart")
    if _contains_any(text, ["希腊", "hellen", "hellenistic"]):
        add("hellen_chart")
    if _contains_any(text, ["量化盘", "germany", "midpoint", "中点盘"]):
        add("germany")
    if _contains_any(text, ["年龄推进点", "年龄点", "age point", "agepoint", "huber", "胡伯"]):
        add("agepoint")
    if _contains_any(text, ["界推运", "分配法", "distributions", "distribution"]):
        add("distributions")
    if _contains_any(text, ["世俗盘", "世俗入宫", "入宫盘", "mundane", "ingress", "时代纪元"]):
        add("mundane")
    if _contains_any(text, ["赤纬推运", "jayne", "jaynesprog"]):
        add("jaynesprog")
    # vedic 单独出现是印度本命盘（india_chart）；只有带推运语义才是 vedicprog（v0.36.0 修 vedic→vedicprog 误路由）。
    # 「恒星黄道二次推运」不含「恒星推运」四连字，却明确是恒星支——二次推运规则排除了「恒星」，这里接住。
    if _contains_any(text, ["恒星推运", "印度推运", "vedicprog", "vedic progression", "sidereal progression", "恒星黄道二次推运", "恒星二次推运"]):
        add("vedicprog")
    if _contains_any(text, _PROG_WORDS) and not _contains_any(text, _PROG_EXCLUDE):
        add("prog")
    if _contains_any(text, _EPHEMERIS_WORDS) and not _contains_any(text, ["数理星历"]):
        add("ephemeris")
    if is_return_timeline:
        add("returntimeline")
    if _contains_any(text, _PRENATAL_SYZYGY_WORDS):
        add("prenatalsyzygy")
    if _contains_any(text, ["行星弧", "planetary arc", "planetaryarc", "月亮弧"]):
        add("planetaryarc")
    if _contains_any(text, ["行星年龄", "人生七阶", "ages of man", "planetaryages"]):
        add("planetaryages")
    if _contains_any(text, ["balbillus", "巴比留斯", "旺距削减"]):
        add("balbillus")
    if _contains_any(text, ["129年系统", "129年", "yearsystem129", "小年"]):
        add("yearsystem129")
    if _contains_any(text, ["波斯向运", "persian directed", "persiandirected", "象征向运"]):
        add("persiandirected")
    if _contains_any(text, _NEROMAN_WORDS):
        add("neroman")
    if _contains_any(text, _JAY_WORDS):
        add("jayprofection")
    if _contains_any(text, _MICHON_WORDS):
        add("michon")
    # 「推运图」是上游 Bezza 一法的中文名，但字面也像「某某推运的图」：只在没有更具体的推运技法命中时才归 Bezza
    # （与「流年」→ givenyear 同一条兜底纪律）。
    if _contains_any(text, _BEZZA_WORDS) or ("推运图" in text and not selected):
        add("bezzafigure")
    # 西洋卜卦占星：只认明说「占星 / horary / 卜卦盘」的说法。通用的「卜卦 / 起卦 / 占问」是起一卦，
    # 由下面的意图类给六爻（缺省、披露）或让用户挑——v0.49 前它们全部落到西洋卜卦盘。
    if _contains_any(text, ["卜卦占星", "占星卜卦", "卜卦盘", "西洋卜卦", "horary"]):
        add("horary")
    # 评一个候选时刻（election 盘）只认明说「候选时刻 / electional」；泛泛的「择日 / 选个日子」是在一段时间里找日子，
    # 归意图类「择日」让用户挑方法（v0.49 前一律给 election 单点盘，而用户没给候选时刻）。
    if (
        _contains_any(text, ["electional", "election chart", "择日盘", "候选时刻", "用事时刻", "选时盘"])
        and not _contains_any(
            text, ["奇门择日", "天星择日", "qimenzeri", "tianxing", "奇门找局", "征象搜索", "七政择日", "择日动盘", "择日双轮"]
        )
        and not is_zeri
        and not _contains_any(text, ["通书", "tongshu"])
    ):
        add("election")
    for zeri_tool, zeri_words in _ZERI_PHRASES.items():
        if _contains_any(text, zeri_words):
            add(zeri_tool)
    if _contains_any(text, ["皇极经世", "心易发微", "wangji", "邵雍数"]):
        add("wangji")
    if _contains_any(text, ["五兆", "wuzhao"]):
        add("wuzhao")
    if _contains_any(text, ["太玄", "揲蓍", "taixuan"]):
        add("taixuan")
    if _contains_any(text, ["荆诀", "jingjue", "京氏易", "靖聩"]):
        add("jingjue")
    if _contains_any(text, ["神易数", "shenyishu", "神乙数", "神乙"]):
        add("shenyishu")
    # 神数正传（五流派合一）：含「铁板/邵子」流派名 → 需与独立 tieban/shaozi/canping 神数互斥（键名分叉）。
    if _contains_any(text, ["神数正传", "正传", "zhengchuan"]):
        add("zhengchuan")
    if _contains_any(text, ["邵子神数", "邵子数", "shaozi"]) and not _contains_any(text, ["正传", "zhengchuan"]):
        add("shaozi")
    if _contains_any(text, ["铁板神数", "铁板", "tieban", "tie ban"]) and not _contains_any(text, ["正传", "zhengchuan"]):
        add("tieban")
    if _contains_any(text, ["鬼谷分定经", "分定经", "两头钳", "fendjing", "fenjing", "分经神数"]):
        add("fendjing")
    if _contains_any(text, ["北极神数", "北极经", "beiji"]):
        add("beiji")
    if _contains_any(text, ["南极神数", "南极经", "nanji"]):
        add("nanji")
    if _contains_any(text, ["蠢子数", "蠢子", "chunzi", "淳子神数", "淳子"]):
        add("chunzi")
    if _contains_any(text, ["演禽", "禽星", "xianqin", "七政演禽"]):
        add("xianqin")
    if _contains_any(text, ["策天", "飞星紫微", "策天飞星", "cetian"]):
        add("cetian")
    if _contains_any(text, ["张果星宗", "张果", "七政四余钦", "qizhengkin", "qizheng"]):
        add("qizhengkin")
    if _contains_any(text, ["西洋游戏", "dice", "占星骰子", "otherbu"]):
        add("otherbu")
    if _contains_any(text, ["13宫", "chart13", "十三宫"]):
        add("chart13")
    # ---- v0.36.0 B2：此前无路由规则的 25 个技法 ----
    if _contains_any(text, ["一掌经", "掌经", "yizhangjing"]):
        add("yizhangjing")
    if _contains_any(text, ["占星地图", "astrocartography", "astro-cartography", "行星线", "acg"]):
        add("acg")
    if _contains_any(text, ["名人星盘", "名人库", "名人出生", "celebrity", "astrodata", "famous birth"]):
        add("astrodata")
    if _contains_any(text, ["巴比伦", "babylon"]):
        add("babylon")
    if _contains_any(text, ["十二分盘", "dwadasamsa", "dwad", "chart12"]):
        add("chart12")
    if _contains_any(text, ["龙盘", "龙头盘", "draconic"]):
        add("draconic")
    if _contains_any(text, ["重置盘", "迁居盘", "移居盘", "relocation", "relocated chart"]):
        add("relocation")
    if _contains_any(text, ["三分主", "triplicity"]):
        add("triplicityrulers")
    if _contains_any(text, ["数字相位推运", "释放点", "小年数", "keypoints", "key points"]):
        add("keypoints")
    if _contains_any(text, ["月相推运", "次限月相", "lunation phase", "lunationphase", "progressed lunation"]):
        add("lunationphase")
    if _contains_any(text, ["多重回归", "行星回归", "土星回归", "木星回归", "saturn return", "jupiter return", "extrareturns", "月交返照"]):
        add("extrareturns")
    if _contains_any(text, ["地占", "geomancy", "geomantic"]):
        add("geomancy")
    if _contains_any(text, ["塔罗", "tarot", "牌阵"]):
        add("tarot")
    if _contains_any(text, ["通书", "通胜", "董公", "tongshu"]) and not _contains_any(text, ["通书择日", "黄历择"]):
        add("tongshu")
    if _contains_any(text, ["万年历", "月历", "日历", "month calendar", "calendar_month", "本月黄历"]):
        add("calendar_month")
    if (
        _contains_any(text, ["黄历", "宜忌", "huangli", "almanac"])
        and not is_zeri
        and not _contains_any(text, ["万年历", "月历", "日历", "本月黄历", "month calendar", "almanac election"])
    ):
        add("huangli")
    if _contains_any(text, ["黄道释放", "zodiacal releasing"]):
        add("zr")
    if _contains_any(text, ["lunar calendar", "阴历换算"]):
        add("nongli_time")
    # 明说本命盘的说法：只在没有更具体的技法命中时兜底（避免「紫微星盘」双点）。
    if not selected and _contains_any(text, ["natal chart", "birth chart", "本命盘", "西洋星盘", "本命星盘", "western astrology", "占星盘"]):
        add("chart")
    if selected:
        if "bezzafigure" in selected and not _contains_any(text, _BEZZA_WORDS):
            disclose("bezzafigure", "推运图", "a directed-figure question")
        return RouteResult(selected, warnings)
    return _route_by_intent(request, text, raw_query, warnings)


def _route_by_intent(request: DispatchInput, text: str, raw_query: str, warnings: list[str]) -> RouteResult:
    """没有点名技法：按意图类分流（engine/intents.py）。出生数据不参与——它说明不了用户想问什么。"""

    def picked(tool: str, why_zh: str, why_en: str, intent_key: str) -> RouteResult:
        warnings.append(bilingual(
            f"这句话没有点名技法，按「{why_zh}」缺省选了{display_name(tool)}（{tool}）；用户要别的技法请直接点名。",
            f"The query names no technique; {display_name(tool)} ({tool}) was chosen as the default for {why_en}. "
            "Name another technique to use it instead.",
        ))
        return RouteResult([tool], warnings, intent_key)

    category = intents.out_of_scope_category(text, raw_query)
    if category is not None:
        key, zh, en = category
        coverage_zh = "；".join(zh_line for zh_line, _en in intents.COVERAGE)
        coverage_en = "; ".join(en_line for _zh, en_line in intents.COVERAGE)
        raise DispatchResolutionError(
            f"「{zh}」不在星阙的技法目录里（out of scope）。",
            code=intents.CODE_OUT_OF_SCOPE,
            details={
                "category": key,
                "candidates": [],
                "covers": [bilingual(zh_line, en_line) for zh_line, en_line in intents.COVERAGE],
                "agent_recovery": intents.choice_recovery(
                    intent=None, names=[], reason="out_of_scope",
                    prompt_zh=f"星阙不做{zh}。它能做的是：{coverage_zh}。如果想换成其中一种来问这件事，请说明用哪一种。",
                    prompt_en=f"Horosa does not do {en}. It covers: {coverage_en}. To ask about this with one of "
                              "those, say which.",
                ),
            },
        )
    if intents.RELATIONSHIP.matches(text) or (request.subject and request.subject.inner and request.subject.outer):
        return picked("relative", "两个人的关系", "a two-person relationship question", "relationship")
    # 「卜卦」在星阙里是西洋卜卦占星模块的名字，口语里又是「起一卦」：两种都说得通 → 让用户挑，不替他定。
    if re.search(r"卜[一个]{0,2}卦", text):
        _refuse_choice(intents.BUGUA, text)
    if re.search(intents.CAST_GUA_PATTERN, text):
        return picked("sixyao", "起一卦", "casting a hexagram", "divination")
    if _contains_any(text, intents.SOLAR_TERM_NAMES):
        return RouteResult(["jieqi_year"], warnings, "calendar")
    if intents.DATE_SELECTION.matches(text):
        _refuse_choice(intents.DATE_SELECTION, text)
    if _contains_any(text, intents.LIFE_TIMING_STRONG):
        _refuse_choice(intents.LIFE_TIMING, text)
    if _contains_any(text, intents.NATAL_WESTERN_WORDS):
        return picked("chart", "星盘", "an astrology chart request", "natal")
    if _contains_any(text, intents.NATAL_WESTERN_INFERRED):
        return picked("chart", "上升 / 星座", "a rising-sign or zodiac-sign question", "natal")
    if intents.DIVINATION.matches(text):
        _refuse_choice(intents.DIVINATION, text)
    if intents.LIFE_TIMING.matches(text):
        _refuse_choice(intents.LIFE_TIMING, text)
    if intents.NATAL_CHOICE.matches(text):
        _refuse_choice(intents.NATAL_CHOICE, text)
    candidates = _suggest_candidates(text)
    raise DispatchResolutionError(
        "未能从请求文本中解析出匹配的技法（no matching tool）。",
        code=intents.CODE_NO_MATCH,
        details={
            "candidates": candidates,
            "candidate_tools": intents.candidate_details(candidates),
            "hint": _GUIDANCE_HINT,
            "agent_recovery": intents.choice_recovery(
                intent=None, names=candidates, reason="no_matching_tool",
                prompt_zh="这句话没有对上任何技法。想用哪一种来看？也可以换个说法，直接说技法名（如「八字」「奇门」「星盘」「六爻」）。",
                prompt_en="The request does not match any technique. Which one should be used? You can also rephrase "
                          "with a technique's name (BaZi, Qi Men, natal chart, Liu Yao …).",
            ),
        },
    )


_GUIDANCE_HINT = bilingual(
    "从 candidates 里选技法名直调对应工具；也可把用户原话交给 horosa_agent_guidance(intent=…)，它只回最相关的几种技法和各自要的字段（几 KB）。",
    "Call a tool from candidates directly, or pass the user's request to horosa_agent_guidance(intent=…), which returns "
    "only the few most relevant techniques and the fields each needs (a few KB).",
)


def _refuse_choice(intent: intents.IntentClass, text: str) -> None:
    names = list(intent.candidates)
    raise DispatchResolutionError(
        "识别出了意图，但有几种合适的技法，需要用户挑一种（technique choice required）。",
        code=intents.CODE_CHOICE,
        details={
            "intent_class": intent.key,
            "candidates": names,
            "candidate_tools": intents.candidate_details(names),
            "hint": _GUIDANCE_HINT,
            "agent_recovery": intents.choice_recovery(
                intent=intent, names=names, reason="technique_choice_required",
                prompt_zh=intent.ask_zh, prompt_en=intent.ask_en,
            ),
        },
    )


def _refuse_not_in_catalogue(text: str, *, what_zh: str, what_en: str, nearest: list[str], note_zh: str, note_en: str) -> None:
    raise DispatchResolutionError(
        f"目录里没有{what_zh}这项技法（not in catalogue）。",
        code=intents.CODE_NO_MATCH,
        details={
            "reason": "not_in_catalogue",
            "requested": bilingual(what_zh, what_en),
            "candidates": list(nearest),
            "candidate_tools": intents.candidate_details(nearest),
            "hint": _GUIDANCE_HINT,
            "agent_recovery": intents.choice_recovery(
                intent=None, names=list(nearest), reason="not_in_catalogue",
                prompt_zh=f"星阙的目录里没有{what_zh}。{note_zh}要用哪一种？",
                prompt_en=f"Horosa's catalogue has no {what_en}. {note_en} Which one should be used?",
            ),
        },
    )


# 关键词路由未命中时的候选建议：常用技法池按名称/关键词与查询的重合度粗排 top-N。
_CANDIDATE_POOL: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("chart", ("星盘", "本命", "natal", "chart", "占星")),
    ("qimen", ("奇门", "遁甲", "qimen")),
    ("liureng_gods", ("六壬", "壬课", "liureng")),
    ("bazi_birth", ("八字", "四柱", "bazi")),
    ("ziwei_birth", ("紫微", "斗数", "ziwei")),
    ("sixyao", ("六爻", "卦", "起卦", "周易")),
    ("tarot", ("塔罗", "tarot", "牌")),
    ("lingqi", ("灵棋", "灵棋经", "lingqi")),
    ("horary", ("卜卦占星", "horary", "问事")),
    ("election", ("择日", "择吉", "election")),
    ("tianxing", ("天星择日", "征象搜索", "tianxing")),
    ("qizhengelection", ("七政择日", "择日动盘", "方位搜索", "日食", "月食", "qizhengelection")),
    ("india_rectify", ("生时校正", "出生时间校正", "校时", "rectify")),
    ("planet_cycles", ("行星周期", "木土合", "大会合", "planet_cycles")),
    ("jieqi_birth", ("出生节气", "节气窗", "jieqi_birth")),
    ("qimenzeri", ("奇门择日", "奇门找局", "qimenzeri")),
    ("calendar_month", ("黄历", "万年历", "农历", "老黄历")),
    ("astrodata", ("名人", "celebrity", "明星")),
    ("xuanshi", ("玄史", "玄学史", "星占史", "天象记录", "史书天象", "占验")),
    ("acg", ("地图", "acg", "迁移", "行星线")),
    ("relative", ("合盘", "关系", "synastry", "配对")),
    ("yizhangjing", ("一掌经", "掌经")),
    ("taiyi", ("太乙", "taiyi")),
)


def _suggest_candidates(text: str, limit: int = 5) -> list[str]:
    """未命中时的候选：先按全表同义词打分（v0.36.0 B2，覆盖全部技法），再用常用池补满。"""
    hits = [name for _score, name in synonym_scores(text)]
    lowered = normalize_query(text)
    scored: list[tuple[int, int, str]] = []
    for order, (name, keywords) in enumerate(_CANDIDATE_POOL):
        score = sum(1 for keyword in keywords if keyword.lower() in lowered)
        scored.append((-score, order, name))
    scored.sort()
    for _, _, name in scored:
        if name not in hits:
            hits.append(name)
    return hits[:limit]
