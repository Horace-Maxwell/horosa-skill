from __future__ import annotations

from horosa_skill.errors import DispatchResolutionError
from horosa_skill.schemas.tools import DispatchInput


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def select_tools(request: DispatchInput) -> list[str]:
    text = request.query.lower()
    selected: list[str] = []

    def add(tool_name: str) -> None:
        if tool_name not in selected:
            selected.append(tool_name)

    if _contains_any(text, ["紫微", "ziwei"]):
        add("ziwei_birth")
    if _contains_any(text, ["八字", "bazi", "四柱"]):
        if _contains_any(text, ["直断", "direct", "大运", "流年"]):
            add("bazi_direct")
        else:
            add("bazi_birth")
    # 小六壬 含「六壬」二字 → 大六壬分支须排除，否则「小六壬测走失」误路由 liureng（同「卜卦含卦字」先例）。
    if _contains_any(text, ["六壬", "liureng"]) and not _contains_any(text, ["小六壬", "xiaoliuren"]):
        if _contains_any(text, ["年运", "runyear", "行年"]):
            add("liureng_runyear")
        else:
            add("liureng_gods")
    if _contains_any(text, ["小六壬", "xiaoliuren"]):
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
    # 飞宫小奇门 含「奇门」二字 → 奇门遁甲分支须排除，否则「飞宫小奇门问出行」误路由 qimen。
    # 「奇门择日」同理：它有自己的工具，落到 qimen 会给出一张单点盘而不是一段搜索结果。
    if (
        _contains_any(text, ["奇门", "qimen"])
        and not _contains_any(text, ["飞宫", "小奇门", "feigong", "奇门择日", "qimenzeri", "奇门找局"])
    ):
        add("qimen")
    if _contains_any(text, ["太乙", "taiyi", "太一"]):
        add("taiyi")
    if _contains_any(text, ["金口诀", "jinkou"]):
        add("jinkou")
    if _contains_any(text, ["宿占", "宿盘", "suzhan"]):
        add("suzhan")
    if _contains_any(text, ["六爻", "易卦", "sixyao", "guazhan", "liuyao"]):
        add("sixyao")
    if _contains_any(text, ["统摄法", "tongshefa"]):
        add("tongshefa")
    if _contains_any(text, ["参评数", "邵子", "金锁银匙", "canping"]) and not _contains_any(text, ["正传", "zhengchuan"]):
        add("canping")
    if _contains_any(text, ["河洛理数", "河洛", "heluo"]):
        add("heluo")
    if _contains_any(text, ["调波盘", "调波", "谐波盘", "harmonic"]):
        add("harmonic")
    if _contains_any(text, ["三式合一", "sanshi", "sanshiunited"]):
        add("sanshiunited")
    if _contains_any(text, ["节气", "jieqi"]):
        add("jieqi_year")
    if _contains_any(text, ["农历", "nongli"]):
        add("nongli_time")
    # 卜卦 (Western horary) also contains the generic "卦" — keep it out of the 梅花易数/卦象 branch.
    if _contains_any(text, ["梅易", "卦", "gua"]) and not _contains_any(text, ["卜卦", "horary", "起卦", "占问"]):
        if _contains_any(text, ["梅易", "meiyi"]):
            add("gua_meiyi")
        else:
            add("gua_desc")
    if _contains_any(text, ["合盘", "关系", "relative", "synastry", "composite"]):
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
    if _contains_any(text, ["given year", "流年"]):
        add("givenyear")
    if _contains_any(text, ["zodiacal release", "zr"]):
        add("zr")
    if _contains_any(text, ["印度", "india"]):
        add("india_chart")
    if _contains_any(text, ["七政四余", "guolao"]):
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
    if _contains_any(text, ["恒星推运", "vedic", "vedicprog", "印度推运"]):
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
        text, ["小成图", "小六壬", "飞宫", "轨策", "皇极轨策", "xiaochengtu", "xiaoliuren", "feigong", "guice"]
    ):
        add("horary")
    # 「奇门择日」/「天星择日」都含「择日」二字 → 必须排除，否则一句话点亮三个工具。
    if _contains_any(text, ["择日", "择吉", "election", "electional", "选时", "用事时刻"]) and not _contains_any(
        text, ["奇门择日", "天星择日", "qimenzeri", "tianxing", "奇门找局", "征象搜索"]
    ):
        add("election")
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
    if _contains_any(text, ["铁板神数", "铁板", "tieban"]) and not _contains_any(text, ["正传", "zhengchuan"]):
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
    if _contains_any(text, ["13宫", "chart13"]):
        add("chart13")

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
    ("horary", ("卜卦占星", "horary", "问事")),
    ("election", ("择日", "择吉", "election")),
    ("tianxing", ("天星择日", "征象搜索", "tianxing")),
    ("qimenzeri", ("奇门择日", "奇门找局", "qimenzeri")),
    ("calendar_month", ("黄历", "万年历", "农历", "老黄历")),
    ("astrodata", ("名人", "celebrity", "明星")),
    ("acg", ("地图", "acg", "迁移", "行星线")),
    ("relative", ("合盘", "关系", "synastry", "配对")),
    ("yizhangjing", ("一掌经", "掌经")),
    ("taiyi", ("太乙", "taiyi")),
)


def _suggest_candidates(text: str, limit: int = 5) -> list[str]:
    lowered = text.lower()
    scored: list[tuple[int, int, str]] = []
    for order, (name, keywords) in enumerate(_CANDIDATE_POOL):
        score = sum(1 for keyword in keywords if keyword.lower() in lowered)
        scored.append((-score, order, name))
    scored.sort()
    return [name for _, _, name in scored[:limit]]
