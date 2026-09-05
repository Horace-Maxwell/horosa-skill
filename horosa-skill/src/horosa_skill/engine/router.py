from __future__ import annotations

from horosa_skill.engine.synonyms import synonym_scores
from horosa_skill.errors import DispatchResolutionError
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


def select_tools(request: DispatchInput) -> list[str]:
    text = request.query.lower()
    selected: list[str] = []
    is_zeri = _contains_any(text, _ALL_ZERI_WORDS)

    def add(tool_name: str) -> None:
        if tool_name not in selected:
            selected.append(tool_name)

    if _contains_any(text, ["紫微", "ziwei", "purple star", "斗数"]) and not is_zeri and not _contains_any(
        text, ["紫微规则", "斗数规则", "格局规则", "ziwei rules", "ziwei_rules", "策天", "飞星紫微", "cetian"]
    ):
        add("ziwei_birth")
    if _contains_any(text, ["紫微规则", "斗数规则", "格局规则", "ziwei rules", "ziwei_rules"]):
        add("ziwei_rules")
    if _contains_any(text, ["八字反查", "反推八字", "四柱反推", "干支反查", "反推出生", "inverse bazi", "reverse bazi", "bazi_inverse"]):
        add("bazi_inverse")
    elif _contains_any(text, ["八字", "bazi", "四柱", "four pillars"]) and not is_zeri:
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
    if _contains_any(text, ["六爻", "易卦", "sixyao", "guazhan", "liuyao", "i ching", "yi jing", "周易"]):
        add("sixyao")
    if _contains_any(text, ["统摄法", "tongshefa"]):
        add("tongshefa")
    # 灵棋经：用「灵棋」全词。禁裸「棋」——它会把「奇门棋盘」这类说法误点亮；也别写裸「经」
    # （皇极经世/一掌经/太玄经全在射程内）。互斥检查：本词不与任何既有分派词重叠。
    if _contains_any(text, ["灵棋", "靈棋", "lingqi"]):
        add("lingqi")
    if _contains_any(text, ["参评数", "邵子", "金锁银匙", "canping"]) and not _contains_any(text, ["正传", "zhengchuan"]):
        add("canping")
    if _contains_any(text, ["河洛理数", "河洛", "heluo", "he luo"]):
        add("heluo")
    if _contains_any(text, ["调波盘", "调波", "谐波盘", "harmonic"]):
        add("harmonic")
    if _contains_any(text, ["三式合一", "sanshi", "sanshiunited"]) and not is_zeri:
        add("sanshiunited")
    if _contains_any(text, ["节气", "jieqi", "solar terms"]) and not _contains_any(
        text, ["出生节气", "节气窗", "哪个节气出生", "哪个节气", "jieqi_birth", "jieqi birth"]
    ):
        add("jieqi_year")
    if _contains_any(text, ["农历", "nongli"]):
        add("nongli_time")
    # 卜卦 (Western horary) also contains the generic "卦" — keep it out of the 梅花易数/卦象 branch.
    if _contains_any(text, ["梅易", "卦", "gua"]) and not _contains_any(text, ["卜卦", "horary", "起卦", "占问"]):
        if _contains_any(text, ["梅易", "meiyi"]):
            add("gua_meiyi")
        else:
            add("gua_desc")
    if _contains_any(text, ["合盘", "关系盘", "relative", "synastry", "composite", "配对盘"]):
        add("relative")
    if _contains_any(text, ["solar return", "solarreturn", "太阳返照"]):
        add("solarreturn")
    if _contains_any(text, ["lunar return", "lunarreturn", "月返"]):
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
    if _contains_any(text, ["profection", "小限"]):
        add("profection")
    # 「流年」是中式通用词（八字直断/紫微/六壬都用）：只在没有更具体技法命中时才指西占指定年推运。
    if _contains_any(text, ["given year", "givenyear"]) or ("流年" in text and not selected):
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
    if _contains_any(text, ["恒星推运", "印度推运", "vedicprog", "vedic progression", "sidereal progression"]):
        add("vedicprog")
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
    # 卜卦盘 的「起卦」通用词会被小成图/小六壬/飞宫/皇极轨策的「…起卦」误触 → 显式排除新式起卦技法。
    if _contains_any(text, ["卜卦", "horary", "占问", "起卦"]) and not _contains_any(
        text,
        [
            "小成图", "小六壬", "飞宫", "轨策", "皇极轨策", "xiaochengtu", "xiaoliuren", "feigong", "guice",
            # v0.36.0：「六爻起卦/统摄法起卦/地占起卦」的通用「起卦」不是卜卦占星
            "六爻", "统摄", "地占", "灵棋", "梅易", "sixyao", "tongshefa", "geomancy", "lingqi",
        ],
    ):
        add("horary")
    # 「奇门择日」/「天星择日」都含「择日」二字 → 必须排除，否则一句话点亮三个工具。
    if (
        _contains_any(text, ["择日", "择吉", "election", "electional", "选时", "用事时刻"])
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
    if _contains_any(text, ["京氏易", "靖瞶", "jingjue"]):
        add("jingjue")
    if _contains_any(text, ["神乙数", "神乙", "shenyishu"]):
        add("shenyishu")
    # 神数正传（五流派合一）：含「铁板/邵子」流派名 → 需与独立 tieban/shaozi/canping 神数互斥（键名分叉）。
    if _contains_any(text, ["神数正传", "正传", "zhengchuan"]):
        add("zhengchuan")
    if _contains_any(text, ["邵子神数", "邵子数", "shaozi"]) and not _contains_any(text, ["正传", "zhengchuan"]):
        add("shaozi")
    if _contains_any(text, ["铁板神数", "铁板", "tieban", "tie ban"]) and not _contains_any(text, ["正传", "zhengchuan"]):
        add("tieban")
    if _contains_any(text, ["分经神数", "两头钳", "fendjing", "fenjing"]):
        add("fendjing")
    if _contains_any(text, ["北极神数", "北极经", "beiji"]):
        add("beiji")
    if _contains_any(text, ["南极神数", "南极经", "nanji"]):
        add("nanji")
    if _contains_any(text, ["淳子神数", "淳子", "chunzi"]):
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
    # 英文/口语本命盘触发：只在没有更具体的技法命中时兜底（避免「紫微星盘」双点）。
    if not selected and _contains_any(text, ["natal chart", "birth chart", "horoscope", "本命盘", "西洋星盘", "占星盘", "western astrology"]):
        add("chart")

    if not selected:
        birth = request.birth or (request.subject.birth if request.subject else None)
        relative = request.subject and request.subject.inner and request.subject.outer
        if relative:
            add("relative")
        elif birth:
            add("chart")

    if not selected:
        raise DispatchResolutionError(
            "未能从请求文本中解析出匹配的技法（no matching tool）。",
            code="dispatch.no_matching_tool",
            details={
                "candidates": _suggest_candidates(text),
                "hint": "可从 candidates 里选技法名直调对应工具，完整技法目录见 horosa_agent_guidance(include_all=true)。",
            },
        )

    return selected


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
    lowered = text.lower()
    scored: list[tuple[int, int, str]] = []
    for order, (name, keywords) in enumerate(_CANDIDATE_POOL):
        score = sum(1 for keyword in keywords if keyword.lower() in lowered)
        scored.append((-score, order, name))
    scored.sort()
    for _, _, name in scored:
        if name not in hits:
            hits.append(name)
    return hits[:limit]
