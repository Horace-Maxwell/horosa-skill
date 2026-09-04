"""技法同义词表（v0.36.0 B2）——让 agent「找得到」：中文口语 + 拼音 + 英文，一处维护、三处消费。

消费点：MCP 工具描述的 `aka:` 一行（广告层，预算见 verify_mcp_list_budget）、dispatch 路由未命中时的候选
打分（`router._suggest_candidates`）、路由语料棘轮（contracts/router_corpus.json）。键集与 TOOL_DEFINITIONS
锁步（tests/test_router_corpus.py）——新工具必须带同义词入册，否则用户用英文/口语永远搜不到它。
不改任何 mcp_name（公开 API，用户 enabled_tools 在用）。
"""
from __future__ import annotations

TOOL_SYNONYMS: dict[str, tuple[str, ...]] = {
    # ---- 三式 / 中式起课 ----
    "qimen": ("奇门遁甲", "奇门", "qi men dun jia", "qimen", "遁甲"),
    "taiyi": ("太乙神数", "太乙", "tai yi", "taiyi"),
    "jinkou": ("金口诀", "大六壬金口诀", "jin kou jue", "jinkou"),
    "tongshefa": ("统摄法", "tong she fa", "tongshefa"),
    "sanshiunited": ("三式合一", "三式", "san shi", "sanshi", "sanshiunited"),
    "suzhan": ("宿占", "宿盘", "二十八宿占", "su zhan", "suzhan"),
    "sixyao": ("六爻", "易卦", "周易占卜", "i ching", "yi jing", "liu yao", "sixyao", "liuyao"),
    "canping": ("邵子参评数", "参评数", "金锁银匙", "can ping", "canping"),
    "heluo": ("河洛理数", "河洛", "he luo li shu", "heluo"),
    "yizhangjing": ("一掌经", "掌经", "yi zhang jing", "yizhangjing"),
    "xiaoliuren": ("小六壬", "xiao liu ren", "xiaoliuren"),
    "feigong": ("飞宫小奇门", "飞宫", "小奇门", "fei gong", "feigong"),
    "xiaochengtu": ("小成图", "xiao cheng tu", "xiaochengtu"),
    "guice": ("皇极轨策", "轨策", "gui ce", "guice"),
    "zhengchuan": ("神数正传", "正传", "zheng chuan", "zhengchuan"),
    "geomancy": ("天文地占", "地占", "geomancy", "geomantic"),
    "lingqi": ("灵棋经", "灵棋", "ling qi", "lingqi"),
    "tarot": ("塔罗", "塔罗牌", "牌阵", "tarot", "tarot spread"),
    "gua_desc": ("卦义", "卦象说明", "hexagram meaning", "gua"),
    "gua_meiyi": ("梅花易数", "梅易", "mei hua yi shu", "meihua"),
    # ---- 西占本命 / 派生盘 ----
    "chart": ("本命盘", "西洋星盘", "星盘", "natal chart", "birth chart", "horoscope", "western astrology"),
    "chart13": ("13 宫盘", "十三宫", "chart13", "13-house chart"),
    "chart12": ("十二分盘", "dwadasamsa", "dwad", "chart12"),
    "draconic": ("龙盘", "龙头盘", "draconic chart", "draconic"),
    "relocation": ("重置盘", "迁居盘", "移居盘", "relocation chart", "relocated chart"),
    "hellen_chart": ("希腊占星", "古典占星盘", "hellenistic", "hellenistic chart"),
    "guolao_chart": ("七政四余", "果老星宗", "果老法", "qizheng siyu", "guolao"),
    "germany": ("汉堡学派", "量化盘", "中点盘", "uranian", "midpoints", "hamburg school"),
    "harmonic": ("调波盘", "谐波盘", "harmonic chart", "harmonics"),
    "babylon": ("巴比伦占星", "巴比伦", "babylonian astrology", "babylon"),
    "acg": ("占星地图", "行星线", "astrocartography", "astro-cartography", "acg", "relocation lines"),
    "astrodata": ("名人星盘库", "名人库", "名人出生数据", "celebrity charts", "astrodata", "famous births"),
    "relative": ("合盘", "关系盘", "配对", "synastry", "composite", "relationship chart"),
    "india_chart": ("印度占星", "吠陀占星", "jyotish", "vedic chart", "kundli", "sidereal chart"),
    "india_rectify": ("生时校正", "出生时间校正", "校时", "birth time rectification", "rectify", "kp rectification"),
    "mundane": ("世俗占星", "入宫盘", "世俗入宫", "mundane astrology", "ingress chart"),
    "planet_cycles": ("行星周期", "木土合相", "大会合", "planetary cycles", "conjunction cycle", "planet cycles"),
    "jieqi_birth": ("出生节气", "节气窗", "哪个节气出生", "birth solar term", "jieqi window"),
    # ---- 推运 ----
    "solarreturn": ("太阳返照", "日返", "solar return"),
    "lunarreturn": ("太阴返照", "月返", "lunar return"),
    "solararc": ("太阳弧", "solar arc"),
    "givenyear": ("指定年推运", "流年推运", "given year", "transit year"),
    "profection": ("小限", "年运推限", "profection", "annual profection"),
    "pd": ("主限", "本初方向", "primary directions", "primary direction"),
    "pdchart": ("主限法盘", "主限盘", "primary direction chart", "pdchart"),
    "zr": ("黄道释放", "zodiacal releasing", "zodiacal release", "zr"),
    "firdaria": ("法达", "法达星限", "firdaria", "firdar"),
    "decennials": ("十年大运", "decennials", "decennial"),
    "agepoint": ("年龄推进点", "年龄点", "胡伯", "age point", "huber"),
    "distributions": ("界推运", "分配法", "distributions", "distribution through the bounds"),
    "jaynesprog": ("赤纬推运", "jayne", "declination progression", "jaynesprog"),
    "vedicprog": ("恒星推运", "印度推运", "vedic progression", "sidereal progression", "vedicprog"),
    "planetaryarc": ("行星弧", "月亮弧", "planetary arc", "planetaryarc"),
    "planetaryages": ("行星年龄", "人生七阶", "ages of man", "planetary ages"),
    "balbillus": ("巴比留斯", "旺距削减", "balbillus"),
    "yearsystem129": ("129 年系统", "129年", "小年", "129-year system", "yearsystem129"),
    "triplicityrulers": ("三分主星推运", "三分主", "triplicity rulers", "triplicity"),
    "keypoints": ("数字相位推运", "释放点", "小年数", "key points", "keypoints"),
    "lunationphase": ("月相推运", "次限月相", "lunation phase", "progressed lunation"),
    "extrareturns": ("多重回归", "行星回归", "土星回归", "木星回归", "saturn return", "jupiter return", "planet returns"),
    "persiandirected": ("波斯向运", "象征向运", "persian directed", "symbolic direction"),
    # ---- 卜卦 / 择日 ----
    "horary": ("卜卦占星", "卜卦", "占问", "horary", "horary astrology"),
    "election": ("择日", "择吉", "选时", "electional", "election astrology", "electional astrology"),
    "tianxing": ("天星择日", "征象搜索", "astro election search", "tianxing"),
    "qizhengelection": ("七政择日动盘", "择日双轮", "方位搜索", "日食", "月食", "qizheng election wheel", "eclipse search"),
    "qimenzeri": ("奇门择日", "奇门找局", "qimen election", "qimenzeri"),
    "huanglizeri": ("黄历择吉", "黄历择日", "通书择日", "almanac election", "huanglizeri"),
    "bazizeri": ("八字择时", "八字择日", "bazi election", "bazizeri"),
    "taiyizeri": ("太乙择时", "太乙择日", "taiyi election", "taiyizeri"),
    "ziweizeri": ("紫微择时", "紫微择日", "ziwei election", "ziweizeri"),
    "liurengzeri": ("六壬择时", "六壬择日", "liureng election", "liurengzeri"),
    "sanshizeri": ("三式择时", "三式择日", "三式合一择时", "sanshi election", "sanshizeri"),
    "qizhengzeri": ("七政择时", "七政四余择时", "qizheng election search", "qizhengzeri"),
    "indiazeri": ("印度择时", "印度择日", "吠陀择日", "muhurta", "indiazeri"),
    # ---- 神数 ----
    "wangji": ("皇极经世", "心易发微", "邵雍数", "huang ji jing shi", "wangji"),
    "wuzhao": ("五兆", "wu zhao", "wuzhao"),
    "taixuan": ("太玄", "太玄经", "揲蓍", "tai xuan", "taixuan"),
    "jingjue": ("京氏易", "靖瞶", "jing jue", "jingjue"),
    "shenyishu": ("神乙数", "神乙", "shen yi shu", "shenyishu"),
    "shaozi": ("邵子神数", "邵子数", "shao zi", "shaozi"),
    "tieban": ("铁板神数", "铁板", "tie ban", "tieban"),
    "fendjing": ("分经神数", "两头钳", "fen jing", "fendjing"),
    "beiji": ("北极神数", "北极经", "bei ji", "beiji"),
    "nanji": ("南极神数", "南极经", "nan ji", "nanji"),
    "chunzi": ("淳子神数", "淳子", "chun zi", "chunzi"),
    "xianqin": ("演禽", "禽星", "七政演禽", "yan qin", "xianqin"),
    "cetian": ("策天飞星", "策天", "飞星紫微", "ce tian", "cetian"),
    "qizhengkin": ("张果星宗", "七政四余钦", "张果", "qizhengkin"),
    # ---- 命理 / 历法 ----
    "ziwei_birth": ("紫微斗数", "紫微", "斗数", "purple star", "zi wei dou shu", "ziwei"),
    "ziwei_rules": ("紫微规则库", "斗数规则", "紫微格局规则", "ziwei rules"),
    "bazi_birth": ("八字", "四柱", "生辰八字", "four pillars", "ba zi", "bazi"),
    "bazi_direct": ("八字直断", "直断", "八字大运流年", "bazi reading", "bazi direct"),
    "liureng_gods": ("大六壬", "六壬", "壬课", "da liu ren", "liureng"),
    "liureng_runyear": ("六壬行年", "行年", "年运", "liureng runyear"),
    "jieqi_year": ("全年节气", "节气盘", "二十四节气", "solar terms", "jieqi"),
    "nongli_time": ("农历换算", "农历", "阴历", "lunar calendar", "nongli"),
    "huangli": ("老黄历", "黄历", "今日宜忌", "宜忌", "chinese almanac", "huangli"),
    "tongshu": ("通书", "通胜", "董公择日", "tongshu", "tung shing"),
    "calendar_month": ("万年历", "月历", "日历", "month calendar", "perpetual calendar"),
    "otherbu": ("占星骰子", "西洋游戏", "astrology dice", "astro dice"),
    # ---- 协议 / 知识 ----
    "export_registry": ("导出注册表", "export registry", "section registry"),
    "export_parse": ("解析导出文本", "parse export", "snapshot parser"),
    "knowledge_registry": ("知识库目录", "knowledge registry", "domains"),
    "knowledge_read": ("查知识", "术语解释", "knowledge lookup", "glossary"),
    "xuanshi": ("玄史", "玄学史", "星占史", "史书天象", "astrology history", "xuanshi"),
}


def synonyms_for(tool_name: str) -> tuple[str, ...]:
    return TOOL_SYNONYMS.get(tool_name, ())


def aka_line(tool_name: str, *, limit: int = 5) -> str:
    """MCP 描述里的一行别名（预算内：≤ ~60 B）。"""
    items = [s for s in synonyms_for(tool_name) if s.lower() != tool_name.lower()][:limit]
    return f"aka: {', '.join(items)}" if items else ""


def synonym_scores(text: str) -> list[tuple[int, str]]:
    """按同义词命中数给每个工具打分（大到小；0 分不返回）。子串匹配，大小写不敏感。"""
    lowered = text.lower()
    scored: list[tuple[int, str]] = []
    for name, words in TOOL_SYNONYMS.items():
        hits = sum(1 for word in (name, *words) if word.lower() in lowered)
        if hits:
            scored.append((hits, name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored
