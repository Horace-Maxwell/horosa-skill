"""中国占卜与三式族输入：大六壬、卦、奇门、太乙、金口诀、小六壬、飞宫、小成图、皇极轨策、神数正传、三式合一、宿占、天文地占、塔罗、灵棋经、六爻。"""
from __future__ import annotations

from typing import Any

from pydantic import Field

from horosa_skill.schemas.tools.base import BirthInput, FlexibleModel, _unadvertised


class LiuRengGodsInput(FlexibleModel):
    date: str
    time: str
    zone: str
    lat: str
    lon: str
    gpsLat: float | None = None
    gpsLon: float | None = None
    # 日界（F2）：None=不发送 → Java /liureng/gods 缺省 1=23 点换日（= 上游出厂缺省 dayBoundary.js:39-45）；
    # 此前硬缺省 False 下发 → 六壬（及金口诀前置、三式合一六壬腿）静默按 24 点换日，与同盘奇门/太乙不同日柱。
    after23NewDay: bool | None = None
    # 晚子时时柱开关：None=不发送（沿用后端默认 1=时干按次日日干起子时）；显式 0/1 全链穿透。
    lateZiHourUseNextDay: int | bool | None = None
    yue: str | None = None
    isDiurnal: bool | None = None
    guirengType: int | None = 2
    ad: int | None = 1
    # 占断向导：上游据 zhanCategory 产出整个 [占断向导] 段（hunyin/taichan/jibing/caiyun/…）。
    # 此前 skill 没有这个入口，等于该段永远不出——补上即解锁。
    zhanCategory: str | None = Field(
        default=None,
        description="占断门类（hunyin 婚姻 / taichan 胎产 / jibing 疾病 / caiyun 财运 …）：驱动 [占断向导] 段。",
    )
    # 起课口径（上游 LIURENG_PAGE_SETTINGS：castMethod 26 法 + xuanShiZhi/yanShuNum、yueJiangMethod、fenZhouYe、
    # seHaiMethod、seHaiBoundary、shiRuKe、yearShenShaSort、yinyangSystem、tuWangShuai、wuxing、timeAlg）。
    # tools/list 字节预算吃紧：描述 ≤20 字，词表住 agent_guidance 的 options_keys；JS 按上游词表校验、认不出即报错。
    options: dict[str, Any] | None = Field(default=None, description="起课口径，见 guidance")


class LiuRengRunYearInput(LiuRengGodsInput):
    gender: bool | None = True
    guaYearGanZi: str | None = None
    guaDate: str | None = None
    guaTime: str | None = None
    guaZone: str | None = None
    guaLon: str | None = None
    guaLat: str | None = None
    guaAd: int | None = None
    guaAfter23NewDay: bool | None = None


class GuaNamesInput(FlexibleModel):
    name: list[str]


class QimenInput(BirthInput):
    # after23NewDay None=不发送（ken 权威引擎默认 1=23点起算次日日柱）；显式 0/1 直达 /qimen/pan 与 nongli 前置。
    after23NewDay: bool | None = None
    # 晚子时时柱开关：None=不发送（沿用后端默认 1=时干按次日日干起子时）；显式 0/1 全链穿透。
    lateZiHourUseNextDay: int | bool | None = None
    timeAlg: int | None = 0
    options: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    nongli: dict[str, Any] | None = None
    jieqi_year_prev: dict[str, Any] | None = None
    jieqi_year_current: dict[str, Any] | None = None
    # 法奇门「相关人员」(星阙 相关人员批)：[{name, yearGan}] 或 [{name, birth}]（birth=公历
    # YYYY-MM-DD[ HH:mm:ss]，skill 经 /nongli/time yearJieqi 按立春界解析年干）。提供后
    # [八门化气大阵] 段逐人多出「生年干·姓名」保护行；缺省不出该类行，段表不变。
    faRelatedPeople: list[dict[str, Any]] | None = None


class TaiyiInput(BirthInput):
    # after23NewDay None=不发送（ken 权威引擎默认 1）；显式 0/1 直达 /taiyi/pan 与 nongli 前置。
    after23NewDay: bool | None = None
    # 晚子时时柱开关：None=不发送（沿用后端默认 1=时干按次日日干起子时）；显式 0/1 全链穿透。
    lateZiHourUseNextDay: int | bool | None = None
    timeAlg: int | None = 0
    gender: str | int | None = None
    # 键：style / tn / timeBasis(direct|trueSolar) / gameTheory / sex / school{六轴}；词表住 agent_guidance options_keys。
    options: dict[str, Any] = Field(default_factory=dict, description="太乙口径（style/tn/timeBasis/school…）")
    nongli: dict[str, Any] | None = None


class JinKouInput(LiuRengGodsInput):
    diFen: str | None = None
    # 快照的贵人/占断层按性别取用（jinkou.js:59 读 payload.gender，Python 整包透传），
    # 但此前无人声明它 —— 能用、agent 却看不见。
    gender: str | int | None = Field(default=None, description="性别：1/男 或 0/女；影响贵人取用与占断行。")
    guirengType: int | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    liureng: dict[str, Any] | None = None


class XiaoLiuRenInput(FlexibleModel):
    # 小六壬：三数起三传（主流六宫 main / 道门九宫 dao，dao 才有五行生克与拜解）。起课为【冻结值】——
    # nums=[月,日,时] 三正整数显式优先；缺 nums 则按占时正统起（date/time/zone+lon+lat → 农历月/日/时支序，
    # 前置 /nongli/time 派生）。askEvent=所问；showOneThree=道门是否列一↔三关系（默认列）。
    nums: list[int] | None = None
    school: str | None = "main"
    showOneThree: bool | None = True
    askEvent: str | None = None
    question: str | None = None
    # 占时起数所需（缺 nums 时必填）：
    date: str | None = None
    time: str | None = None
    zone: str | None = None
    lon: str | None = None
    lat: str | None = None
    ad: int | None = 1
    timeAlg: int | None = None
    # 晚子时双开关（占时影响时支序，见 references/late-zi.md）。
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None


class FeiGongInput(FlexibleModel):
    # 飞宫小奇门：时上起青龙·甲乘龙飞九宫。局为【冻结值】——起支 + 日干支一经定局即不重起。
    # 起支来源 qiMode：hour 时支（默认，占时）/ manualZhi 选支 / manualNum 数取 / yearZhi 年支；
    # 也可直接给已定 qiZhi。命宫随 mingAge/mingGender 重排；koujing=河魁口径（zheng 正 / yi 异两说）。
    qiMode: str | None = "hour"
    qiZhi: str | None = None
    zhi: str | None = None
    num: int | None = None
    yearZhi: str | None = None
    hourZhi: str | None = None
    dayGan: str | None = None
    dayZhi: str | None = None
    mingAge: int | None = None
    mingGender: str | None = "male"
    liuYueMonth: int | None = None
    koujing: str | None = "zheng"
    askEvent: str | None = None
    question: str | None = None
    # 占时起局所需（缺 dayGan/dayZhi 或 hour 模式缺 hourZhi 时）：
    date: str | None = None
    time: str | None = None
    zone: str | None = None
    lon: str | None = None
    lat: str | None = None
    ad: int | None = 1
    timeAlg: int | None = None
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None


class XiaoChengTuInput(FlexibleModel):
    # 小成图：洛书九宫佈局·正旁推·四象·应期·股市研判。卦为【冻结值】——起卦一经起出即不重起。
    # qiguaFa：manual 手动(上/下卦 up/lo + 动爻 dongYaos) / number 两数(upNum/loNum + qiguaShu 天地数
    # tiandi/先天 xiantian) / stock 股价(open/close 字符串保末尾 0) / dayan 大衍(seed 或 manualCounts，
    # 须显式，禁静默随机) / time 占时梅花卦(date/time → 年支序+月+日=上数、+时支序=下数)。yongGong 用宫(1-9 非5)。
    qiguaFa: str | None = "manual"
    up: str | None = None
    lo: str | None = None
    dongYaos: list[int] | None = None
    upNum: int | None = None
    loNum: int | None = None
    qiguaShu: str | None = "tiandi"
    open: str | None = None
    close: str | None = None
    seed: int | None = None
    manualCounts: list[int] | None = None
    yongGong: int | None = 1
    # 闢卦细判口径（上游挂载 schema xiaochengtu.piKoujing）：'zheng'★ 正传 得配害·失配利 | 'yiwen' 异文 → [四象]
    piKoujing: str | None = Field(default=None, description="闢卦口径 zheng/yiwen")
    kline: dict[str, Any] | None = None
    askEvent: str | None = None
    question: str | None = None
    # 占时(qiguaFa='time')所需：
    date: str | None = None
    time: str | None = None
    zone: str | None = None
    lon: str | None = None
    lat: str | None = None
    ad: int | None = 1
    timeAlg: int | None = None
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None


class GuiceInput(FlexibleModel):
    # 皇极轨策：十二法起卦 + 演数四位 + 卦变断法 + 三要十应 + 元会运世 + 大定起数。卦为【冻结值】。
    # 起卦法 qiguaFa：time 年月日时 / baoshu 报数 / wushu 物数 / shengyin 声音 / zizhan 字占 /
    # zhangchi 丈尺 / chicun 尺寸 / weiren 为人 / ziji 自己 / dongwu 动物·五方 / jingwu 惊悟 / duanfa 端法。
    # 十开关流派（默认心易发微本）：school/yanshuFa(策 ce/轨 gui)/jiGongMode/qiguaShu/shenSha/shiFang/
    # shuXi(周易 zhouyi/梅花 meihua)/dadingTable/shiyingSet。FlexibleModel 额外接受各法专属起卦字段。
    qiguaFa: str | None = "time"
    school: str | None = None
    yanshuFa: str | None = None
    jiGongMode: str | None = None
    qiguaShu: str | None = None
    shenSha: bool | None = None
    shiFang: bool | None = None
    shuXi: str | None = None
    dadingTable: str | None = None
    shiyingSet: str | None = None
    # 法专属起卦输入（按 qiguaFa 取用；FlexibleModel 亦接受未列字段）：
    nums: list[int] | None = None
    wuShu: int | None = None
    shengShu: int | None = None
    text: str | None = None
    shu: int | None = None
    shu2: int | None = None
    hourZhi: str | None = None
    # 免起课路径（guice.js:29-39 逐键读取；样例载荷一直这样调）：给了四柱/农历月日就不再从 date/time 起课。
    yearZhi: str | None = None
    monthZhi: str | None = None
    lunarMonth: int | None = None
    lunarDay: int | None = None
    year: int | None = None
    dayGan: str | None = None
    pillars: list[str] | None = None
    # 十应之录（占时耳目所及，机不能代）+ 方位 + 所问：
    shiyingInputs: dict[str, Any] | None = None
    fangKey: str | None = None
    askEvent: str | None = None
    question: str | None = None
    # 占时四柱（缺显式 ctx 时由 date/time 起；ctx 立春界年柱 + 农历月日 + 时支）：
    date: str | None = None
    time: str | None = None
    zone: str | None = None
    lon: str | None = None
    lat: str | None = None
    ad: int | None = 1
    timeAlg: int | None = None
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None


class ZhengChuanInput(FlexibleModel):
    # 神数正传：五流派——tieban 铁板神数 / shaozi 邵子神数 / dading 大定数 / liuqin 六亲数 / xinyi 铁算心易。
    # 除 xinyi（查询层，不需生辰）外，四柱走 /nongli/time 权威口径（立春界年柱 + 农历月日）。gender 男/女 或 1/0。
    school: str | None = "tieban"
    # 十进制坐标别名（与 BirthInput 同：后端载荷候选会回退到 gpsLat/gpsLon；此前 MCP 扁平面静默丢弃）。
    gpsLat: float | None = None
    gpsLon: float | None = None
    gender: str | int | None = None
    # 生辰（tieban/shaozi/dading/liuqin 起四柱所需；dading 另需 date/time 建 bazi 推运表）：
    date: str | None = None
    time: str | None = None
    zone: str | None = None
    lon: str | None = None
    lat: str | None = None
    ad: int | None = 1
    timeAlg: int | None = None
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None
    # 流派专属：tieban askGz（占问干支）；shaozi fatherAge/motherAge/yuan（上/中/下元）；
    # liuqin askHourZhi/env（晴阴雨雪/明晦）；dading dadingYear（所推流年）+ 可手填 dayun/xiaoyun/suijun/age。
    askGz: str | None = None
    fatherAge: int | None = None
    motherAge: int | None = None
    yuan: str | None = None
    askHourZhi: str | None = None
    env: str | None = None
    dadingYear: int | None = None
    dayun: str | None = None
    xiaoyun: str | None = None
    suijun: str | None = None
    age: int | None = None
    # xinyi 查询层（铁算心易·条文秘数/性情项查询，任一即可）：
    # sync311 F14：上游挂载缺省（aiAnalysisContext.js:3240-3243，F-53）父母/日/一刻/乾/子；ke 收 1–8 或 一刻…八刻
    # （查表键是「一刻…八刻」，此前 int 直送 → 八刻分命恒空）；简体项目/宫/声音归一到表内繁体。
    item: str | None = None
    sound: str | None = None
    ke: int | str | None = None
    gong: str | None = None
    xqZhi: str | None = None
    xqYushu: int | None = None


class SanShiUnitedInput(FlexibleModel):
    date: str
    time: str
    zone: str
    lat: str
    lon: str
    gpsLat: float | None = None
    gpsLon: float | None = None
    ad: int | None = 1
    # after23NewDay None=不发送（三式权威引擎默认 1）；显式 0/1 透传三式子工具。
    after23NewDay: bool | None = None
    # 晚子时时柱开关：None=不发送（沿用后端默认 1）；显式 0/1 透传到三式子工具。
    lateZiHourUseNextDay: int | bool | None = None
    timeAlg: int | None = 0
    qimen_options: dict[str, Any] = Field(default_factory=dict)
    taiyi_options: dict[str, Any] = Field(default_factory=dict)
    # 六壬层口径（同 liureng_gods options；castMethod 锁 zheng、timeAlg 走顶层共享）。tools/list 预算：描述 ≤20 字。
    liureng_options: dict[str, Any] | None = Field(default=None, description="六壬层口径，见 guidance")
    liureng_yue: str | None = None
    liureng_isDiurnal: bool | None = None
    # [紫微四化]：上游由紫微子页签的 UI 状态驱动，headless 开成显式入参（下标越界回退末项，同上游钳制）。
    ziweiSihua: dict[str, Any] | None = Field(default=None, description="紫微四化层选择 {daxianIdx, liunianIdx}；给了才产 [紫微四化] 段。")


class SuZhanInput(BirthInput):
    # F11（上游 SuZhanMain.js:396-428 + models/astro.js）：宫制缺省 1（页面共享 astro 模型 DefaultHouseSystem=1）；
    # 外盘/盘型只影响快照两行标签（上游缺省不带键 → 不出那两行，故缺省 None）；人事十二宫缺省 0=八字公式起盘
    # （:312-316，1=ASC）；宿度制 0–8 缺省 0（newChartSeeds.js:48）。bool 旧写法照收（True→1 斗柄）。
    hsys: int | None = 1
    szchart: int | None = None
    szshape: int | None = None
    houseStartMode: int | None = 0
    doubingSu28: int | None = 0
    # 农历四柱时间算法（Java ChartController [Q-419/T-383]：0 真太阳时缺省 / 1 直接时间 / 3 平太阳时）——只作用于
    # 八字公式起盘所读的农历时支。
    nongliTimeAlg: Any | None = _unadvertised()


class GeomancyInput(BirthInput):
    # 天文地占 (astronomical geomancy): 以起卦时刻(date/time/place)确定性起卦(castMethod='time' + timeSeed 由时刻派生)。
    # 后端由 4 母卦推 16 图形 + 十二宫图形入宫 + 判官/见证/解读技法 + 转宫派生 + 定局落星。question 为所问，
    # questionType 择 11 类问类。
    question: str | None = None
    # 问类（后端 _QTYPES 十一类，webgeomancysrv.py:42-46）：custom/life/health/wealth/marriage/career/children/
    # journey/religion/enemy/death；其它值结构化报错（此前 lawsuit/theft/… 被后端静默改回 custom）。
    questionType: str | None = "custom"
    # 十六卦目录（v0.33.0 批 I-5，/geomancy/catalog）：includeCatalog=true 加产 [十六卦目录] 段（16 图形属性总表）。
    includeCatalog: bool | None = Field(default=None, description="附十六图形属性总表（五行/主星/星座/性/象意，agent grounding 用）")
    # 传本流派：european_classical/european_planetary/european_modern/arabic_raml/india_ramal/sikidy/
    # hakata/greek（8 家占断传本）。ifa（西非同族结构对照）为结构对照模式、不产占断，本 skill 不暴露 ——
    # 传 ifa 会以 tool.geomancy_structural_only_unsupported 明确拒绝并说明。
    profile: str | None = "european_classical"
    tradition: bool | None = None  # 通用古典盘开关（chart 族共享，geomancy 不使用；保留以兼容 chart_birth 透传）
    # 黄道体系(classical/planetary)、判读深度(L1/L2/L3)、所问宫(1-12，显式优先于问类查表)、
    # 转宫(turnTo：以某宫为新命宫重算，问他人/事中之事时用)。
    zodiacSystem: str | None = None
    readingScope: str | None = None
    quesitedHouse: int | None = None
    turnTo: int | None = None
    # 传本粒度覆盖 passthrough（markStyle/direction/houseProjection/wrapHouses/reconciler/reconcilerMode/
    # haltEnabled/compoundMode/numberSystem/chartMode/houseSystem/ascSource/namesSystem/parityScope +
    # sync311 F12：housePlacement 图形入宫 / castNumbers 报数起卦十六数 / planetaryChart* 行星地占盘四键）；
    # 未传=None → 内核回落 profile 默认，旧盘字节零变；认不出的键回执 data.params_ignored。
    options: dict[str, Any] | None = None


class TarotInput(BirthInput):
    # 塔罗：确定性抽牌。种子 = 上游「生辰」种子来源 seedFromFields（TarotMain.js:97-108）：
    # name|date|time|lat|lon（空项跳过）——同人同刻同地同牌；seed 显式种子覆盖。
    # spread 牌阵（缺省 three；须在该牌组 caps.spreads 允许表内，键名见 guidance：single/relation/celtic…），
    # deck 牌系（默认 rws 韦特），question 所问。
    question: str | None = None
    spread: str | None = None
    deck: str | None = "rws"
    seed: str | None = None
    # 缺省随牌组（deck.usesReversals）；显式 true/false 一律下发（此前 true 从不下发，马赛系开不了逆位）。
    usesReversals: bool | None = None
    # dignities 元素尊位强弱、variant 对应体系（A/B/C），影响逐牌详解与综合断语。
    dignities: bool | None = None
    variant: str | None = None
    # 定局法（引擎 YESNO_MODES 八法）：majority/orientation/single/numeric/polarity/weighted_center/anchor/single3。
    verdictMode: str | None = "majority"
    # 生命牌：给出生年月日（+可选 refYear 流年）才产出[生命牌]段；不传则该段自然不出。
    birth: dict[str, Any] | None = None
    # 引擎其余判读设置（sync311 F9，锚引擎 resolveSettings 键集）：meaningSystem/reversalMode/timingMethod/
    # timingUnit/majorsOverlay/sig/includeBlank/…；认不出的键回执 data.params_ignored，值不被引擎接受即报错。
    options: dict[str, Any] | None = Field(default=None, description="引擎判读设置（键表见 guidance）")


class LingqiInput(BirthInput):
    # 灵棋经（上游 v3.9.0）：十二棋子（上4/中4/下4）一时掷之成卦，古法「不可再擲」。
    # 以起卦时刻确定性起卦（date/time 派生种子，同刻同卦可复现）——headless 不暴露 random 档，
    # 否则同一时刻两次调用得到不同卦，既违古法也让回归测试无从写起。
    question: str | None = None
    # 问类：general 通用 / career 仕途 / wealth 求财 / marriage 婚姻 / health 疾病 /
    # travel 行人 / lawsuit 官讼 / home 家宅。只影响[起盘信息]的问类标注。
    category: str | None = "general"
    # 冻结卦：读档或复算时传入 [上,中,下] 三层正面枚数（各 0–4），传了就照它复排，绝不重掷。
    counts: list[int] | None = None
    # 注家显示（yan 颜氏/he 何氏/chen 陈氏/liu 刘氏 + ke 课断 + shi 断诗）。段头恒出，
    # 开关只影响段内行——段集恒定是上游 parityAll 哨兵口径，不要拿它当条件段。
    zhuVisible: dict[str, Any] | None = None


class SixYaoLineInput(FlexibleModel):
    value: int | bool
    change: bool | None = False
    god: str | None = None
    name: str | None = None


class SixYaoInput(FlexibleModel):
    date: str
    time: str
    zone: str
    lat: str
    lon: str
    gpsLat: float | None = None
    gpsLon: float | None = None
    ad: int | None = 1
    question: str | None = None
    # 求测人性别：只进 [起盘信息]「求测人性别」行（上游 GuaZhanMain.buildGuaSnapshotText:232-236，引擎不据此取用神）；
    # None = 上游 buildCaseSnapshotFields 缺省 gender ?? 1（男）。
    gender: int | None = Field(default=None, description="求测人性别 1男(缺省)/0女，仅随盘记录")
    gua_code: str | None = None
    changed_code: str | None = None
    lines: list[SixYaoLineInput] = Field(default_factory=list)
    # 占时时间算法（上游 [Q-390/T-372]：页面 > 全局 > 缺省真太阳时 0）；None = 按 0 发送。
    timeAlg: int | None = Field(default=None, description="占时时间算法：0=真太阳时（缺省）1=直接时间")
    # 日界/晚子时：None = 不发送（后端 1/1 = 星阙出厂全局默认）；显式 0/1 直达 /nongli/time。
    after23NewDay: int | None = Field(default=None, description="日界 1=23点换日(缺省)")
    lateZiHourUseNextDay: int | None = Field(default=None, description="晚子时干 1=次日(缺省)")
    # 判读口径 = 上游六爻挂载齿轮 SIXYAO_FIELDS 24 键（扁平形，JS 侧按上游 mergeLiuyaoGearSettings 合并）。
    liuyaoSettings: dict[str, Any] | None = Field(
        default=None,
        description=(
            "判读口径（上游六爻齿轮 24 键）：school 流派预设 / askType 占测事项(用神) / yongOverride / benming / "
            "tuChangsheng / bianyaoScope / fushen / yuepoMode / shishen / jinTuiTu / tianshiSchool / yearBoundary / "
            "guashen / sixGods / yuqi / yingqi / doctrine / gufa / yueLiushen / guirenFa / shenshaOn / shenshaBase / "
            "shenshaSet / shenshaExOn；取值见 horosa_agent_guidance。"
        ),
    )
