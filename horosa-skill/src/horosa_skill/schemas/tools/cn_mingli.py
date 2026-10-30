"""中国命理族输入：节气八字、八字、紫微、节气年、农历、月历、黄历、通书、统摄法、参评数、河洛、一掌经、反推八字。"""
from __future__ import annotations

from typing import Any

from pydantic import Field

from horosa_skill.schemas.tools.base import BirthInput, FlexibleModel, _unadvertised


class JieQiBirthInput(BirthInput):
    """出生节气窗：定位出生时刻前后的节气精确时刻（八字起运窗的同源数据）。"""
    hsys: int | None = 0  # 上游 JieQiChartsMain.js:1014 页面初始 hsys 0（节气盘家族与 JieQiYearInput 同）

    useLocalMao: int | None = Field(default=None, description="真太阳时卯时口径开关（0/1，缺省 0，上游同默认）")
    byLon: int | None = Field(default=None, description="按经度修正开关（0/1，缺省 0，上游同默认）")


class ZiWeiBirthInput(FlexibleModel):
    date: str
    # 十进制坐标别名（与 BirthInput 同：后端载荷候选会回退到 gpsLat/gpsLon；此前 MCP 扁平面静默丢弃）。
    gpsLat: float | None = None
    gpsLon: float | None = None
    time: str
    zone: str
    lat: str
    lon: str
    gender: bool | None = Field(default=True, description="性别：true/1=男（默认），false/0=女；'男'/'女'/'M'/'F' 会自动归一。")
    # 日界（F2）：上游出厂缺省 1=23 点换日（utils/dayBoundary.js:39-45 defaultAfter23NewDay）。缺省不发送 →
    # Java /ziwei/birth 缺省 1（ZiWeiController.java:87）；本地引擎档由 runner 显式补 1（ZiWeiMain.js:680-681）。
    after23NewDay: bool | None = Field(default=None, description="日界 1=23点换日(默认) 0=24点")
    # 晚子时时柱开关：None=不发送（沿用后端默认 1=时干按次日日干起子时）；显式 0/1 全链穿透。
    lateZiHourUseNextDay: int | bool | None = None
    timeAlg: int | None = Field(default=0, description="0=真太阳时（默认）1=直接时间")
    # 旧入参：原样四化表 {干:[禄,权,科,忌]} ≡ 上游 sihuaSchool=custom + sihuaCustomTable（_run_ziwei_tool 映射）。
    sihua: dict[str, list[str]] | None = None
    ad: int | None = 1
    # F8：四化流派 + 上游 ZW_ENGINE_SWITCH_KEYS（ZiWeiMain.js:752-754）传本/排盘/叠层开关，编排见 tools/ziweiBirth.js。
    # 只有 sihuaSchool / period / schools 进广告层；其余已声明（MCP 顶层按名直传）但不广告，键表见
    # horosa_agent_guidance(ziwei_birth).options_keys（tools/list 预算）。取值锚 vendored ziweiOptions.js *_OPTIONS。
    sihuaSchool: Any | None = Field(default=None, description="四化流派（键见 guidance）")
    childLimit: Any | None = _unadvertised()
    zhongxian: Any | None = _unadvertised()
    huoPan: Any | None = _unadvertised()
    qishuWei: Any | None = _unadvertised()
    borrowPalace: Any | None = _unadvertised()
    taiSuiRuGua: Any | None = _unadvertised()
    taiSuiRelatives: Any | None = _unadvertised()
    sihuaCustomTable: Any | None = _unadvertised()
    brightnessCustomTable: Any | None = _unadvertised()
    daxianSpan: Any | None = _unadvertised()
    tianmaBasis: Any | None = _unadvertised()
    starSet: Any | None = _unadvertised()
    sanPan: Any | None = _unadvertised()
    shangShi: Any | None = _unadvertised()
    leapMonth: Any | None = _unadvertised()
    lateZi: Any | None = _unadvertised()
    yearBoundary: Any | None = _unadvertised()
    huoling: Any | None = _unadvertised()
    kongNaming: Any | None = _unadvertised()
    brightnessSource: Any | None = _unadvertised()
    lifeMasterBy: Any | None = _unadvertised()
    liuYueBasis: Any | None = _unadvertised()
    liunianSihuaGan: Any | None = _unadvertised()
    changshengStart: Any | None = _unadvertised()
    changshengDirection: Any | None = _unadvertised()
    kuiYue: Any | None = _unadvertised()
    kongwangStyle: Any | None = _unadvertised()
    flowLuanXi: Any | None = _unadvertised()
    flowHuoLing: Any | None = _unadvertised()
    flowShenshaOnChart: Any | None = _unadvertised()
    xiaoxianMode: Any | None = _unadvertised()
    ziweiXiaoxianYinyang: Any | None = _unadvertised()
    cnUnifiedZone: bool | None = _unadvertised()
    # [运限] / [流派叠层]：上游由界面勾选与流派开关驱动，headless 开成显式入参。
    period: dict[str, Any] | None = Field(default=None, description="运限时段 {daxian,liunian,liuyue,liuri,liushi}")
    schools: dict[str, Any] | None = Field(default=None, description="旧入参：流派叠层开关（键见 guidance）")


class ZiWeiRulesInput(FlexibleModel):
    pass


class BaZiBirthInput(FlexibleModel):
    date: str
    # 十进制坐标别名（与 BirthInput 同：后端载荷候选会回退到 gpsLat/gpsLon；此前 MCP 扁平面静默丢弃）。
    gpsLat: float | None = None
    gpsLon: float | None = None
    time: str
    zone: str
    lat: str
    lon: str
    godKeyPos: str | None = None
    # 五行力量·藏干版本（上游 baziLunarLocal.js:1141）：'fenye'=分野加权（月柱仅当令司令之干
    # 吃月乘）/ 缺省 'common'=通行版。此前 skill 无入口 → [五行力量] 段那条「分野加权」说明行
    # 结构上永不可达，而 [月令司令（分野）] 段却照出司令干，两段口径自相矛盾。
    cangVersion: str | None = None
    # 分野轮值表版本（上游 baziLunarLocal.js:1136）：'fajue' / 缺省 'common'。
    fenyeVersion: str | None = None
    # v3.11.2 南半球月令（BaZi.js genParams / baziLunarLocal.js flipMonthPillar / Java southMonth）：只对南纬出生生效。
    southMonth: str | None = Field(
        default=None,
        description="南半球月令（只对南纬出生生效，北纬忽略）：none=不对冲（缺省，月柱同北半球）| chong=对冲（月支取对冲之支，月干按年干五虎遁重起，胎元/命宫/大运随之）。",
    )
    timeAlg: int | None = 0
    # 本地引擎（上游页面主路径）不实现 byLon：给了真值即整盘走 Java /bazi/*（唯一实现它的引擎）并进 warnings。
    # adjustJieqi：v3.13.0 起上游恒发 0（BAZI_ADJUST_JIEQI_SENT），给了真值也按不调整起盘并进 warnings（保留字段=旧调用不报错）。
    byLon: bool | None = False
    # 日界（F2）：None=按上游出厂缺省 1（23 点换日；BaZi.js genParams 恒带 fields.after23NewDay=defaultAfter23NewDay()）。
    after23NewDay: bool | None = None
    # 晚子时时柱开关：None=不发送（沿用后端默认 1=时干按次日日干起子时）；显式 0/1 全链穿透。
    lateZiHourUseNextDay: int | bool | None = None
    phaseType: int | None = 0
    ad: int | None = 1
    # 盘法/流派（F9，上游 techniqueMountSettings.js:1705-1740 + BaZi.js:961-985 genParams 缺省）：
    # minggongMethod tongxing(缺省)|shufa · dayunPrecision precise(缺省)|integer ·
    # school zonghe(缺省)|fuyi|geju|tiaohou|bingyao|tongguan|mangpai|nayin · ageStyle nominal(虚岁,缺省)|real(周岁)。
    minggongMethod: Any | None = _unadvertised()
    dayunPrecision: Any | None = _unadvertised()
    school: Any | None = _unadvertised()
    ageStyle: Any | None = _unadvertised()
    cnUnifiedZone: bool | None = _unadvertised()
    # v0.36.0（PR #17，@xipfs）：此前未声明 → MCP 扁平面（FastMCP arg_model 丢未声明键）静默丢性别，快照恒
    # 「性别：未知」、大运顺逆无法判定；CLI/tool_run/dispatch 不受影响（FlexibleModel extra=allow）。
    gender: int | str | None = Field(
        default=None,
        description="性别：1/'男'/'M'/true=男；0/'女'/'F'/false=女；缺省=未指定（大运/流年顺逆无法判定）。",
    )
    response_view: str | None = Field(
        default=None,
        description="响应精简视图：缺省=完整；'sections'=段标题+正文；'titles'=只留段标题索引（完整结果已存档，memory_show 可取回）。",
    )
    # [多运限·指定时段]：上游由界面勾选驱动，headless 开成显式入参。语义同上游 ——
    # 流年 × 流月笛卡尔各一段；流日/流时锚定到所选的第一个上层；总段数封顶 50。
    period: dict[str, Any] | None = Field(default=None, description="多运限时段选择 {liunian:[公历年], liuyue:[月序1-12], liuri:[公历日], liushi:[时辰序0-11]}。")
    # [Q-191/T-135]（上游 v3.11.0 BaZi.js:369-375，页面 baziOpt.zodiacBoundary）：生肖岁首。
    zodiacBoundary: str | None = Field(
        default=None,
        description="生肖岁首：lichun=立春（缺省，同星阙页面缺省）| lunar=正月初一。只改 [起盘信息] 的「生肖：X（岁首=…）」行；正月初一与立春之间出生者两档差一个生肖。",
    )


class BaZiDirectInput(BaZiBirthInput):
    gender: bool | None = True
    # 十进制坐标别名（与 BirthInput 同：后端载荷候选会回退到 gpsLat/gpsLon；此前 MCP 扁平面静默丢弃）。
    gpsLat: float | None = None
    gpsLon: float | None = None
    adjustJieqi: bool | None = False
    # [多运限·指定时段]：上游由界面勾选驱动，headless 开成显式入参。语义同上游 ——
    # 流年 × 流月笛卡尔各一段；流日/流时锚定到所选的第一个上层；总段数封顶 50。
    period: dict[str, Any] | None = Field(default=None, description="多运限时段选择 {liunian:[公历年], liuyue:[月序1-12], liuri:[公历日], liushi:[时辰序0-11]}。")


class JieQiYearInput(FlexibleModel):
    year: int | str
    zone: str
    lat: str
    lon: str
    time: str | None = None
    hsys: int | None = 0
    # 宿度制 0–8（F16，上游 JieQiChartsMain.js:122-134 FT-10②：2–8 不再夹成 0/1；perchart.py:731 parseSu28Mode 九档）。
    # bool 旧写法照收（True→1 斗柄定房）。
    doubingSu28: int | None = Field(default=0, description="宿度制 0–8")
    southchart: bool | None = False
    seedOnly: bool | None = False
    zodiacal: int | None = 0
    # 恒星黄道岁差（zodiacal=1 生效）：Python /jieqi/year 的分至盘不读它（YearJieQi.params 无此键），
    # 给了就按上游 loadJieqiChart 逐节气 /chart 重排（JieQiChartsMain.js:524-553 buildChartRequestParams）。
    siderealAyanamsa: str | None = Field(default=None, description="恒星岁差（zodiacal=1）")
    gpsLat: float | None = None
    gpsLon: float | None = None
    jieqis: list[str] | None = None
    timeAlg: int | None = 0
    byLon: bool | None = False
    godKeyPos: str | None = None
    phaseType: int | None = 0
    # 晚子时时柱开关：None=不发送（沿用后端默认 1=时干按次日日干起子时）；显式 0/1 全链穿透。
    lateZiHourUseNextDay: int | bool | None = None
    ad: int | None = 1


class NongliTimeInput(FlexibleModel):
    date: str
    time: str
    zone: str
    lat: str | None = None
    lon: str
    gpsLat: float | None = None
    gpsLon: float | None = None
    gender: bool | None = None
    # 日界（F2）：None=不发送 → Java /nongli/time 缺省 1=23 点换日（NongliController.java:88，= 上游出厂缺省）。
    after23NewDay: bool | None = None
    # 晚子时时柱开关：None=不发送（沿用后端默认 1=时干按次日日干起子时）；显式 0/1 全链穿透。
    lateZiHourUseNextDay: int | bool | None = None
    # NongliController.java:92-95：/nongli/time 只认 0/1（其余一律夹回 0=真太阳时）；平太阳时 3 不在此端点。
    timeAlg: int | None = 0
    cnUnifiedZone: bool | None = _unadvertised()
    ad: int | None = 1


class CalendarMonthInput(FlexibleModel):
    # 黄历/万年历：date 所在公历月的整月月历（农历/干支/节气/朔望）。
    date: str
    zone: str
    lon: str = "120e00"  # 历算经度（节气/朔望真时刻按此），默认东经 120 度标准历算经度
    lat: str | None = None
    ad: int | None = 1
    day: str | None = None  # 选中日（YYYY-MM-DD）：给出则产 [选中日详情] 段
    # 以下三组喂给页面聚合快照的三个子模块（老黄历 / 通书择日 / 日子馆），纯前端推演、零后端往返。
    hour: int | None = Field(default=None, description="0–23 整点小时；影响 [时辰吉凶] 的当前时标记。")
    tongshu: dict[str, Any] | None = Field(default=None, description="通书 {school,event,liexiuUse,mingYear}；school 键见 guidance")
    rizi: dict[str, Any] | None = Field(default=None, description="日子馆 {event, year, topN, persons:[{name,date,time,gender,role}]}；给了 persons 才产 [日子馆·个性化择日]/[当事人八字]。")


class HuangliInput(FlexibleModel):
    # 老黄历日课：纯前端本地推演（lunar-javascript + 择日表），零后端往返，故无需 zone/经纬。
    date: str
    hour: int | None = Field(default=None, description="0–23 整点小时；影响 [时辰吉凶] 的当前时标记，缺省 12。")


class TongshuInput(FlexibleModel):
    # 通书择日：五流派各自独立的断语表，同一天在不同流派下结论可以完全相反 → school 结果敏感。
    date: str
    # 键 = 引擎词表 tongshuSchools.js TONGSHU_SCHOOLS：donggong 董公 / qimen 奇门叠数 / sanyuanliexiu 三垣列宿 /
    # wutu 天元乌兔 / sanyuan 三元玄空大卦（sanyuan 是玄空、不是三垣）；认不出的键结构化报错。词表进 guidance 不进广告层。
    school: str | None = Field(default=None, description="流派键（见 guidance）")
    event: str | None = Field(default=None, description="用事（嫁娶 / 开市 / 安葬 …），缺省「嫁娶」。")
    liexiuUse: str | None = Field(default=None, description="三垣列宿用事类（断语高亮），缺省「建宅」。")
    # zuoShan 已删：上游 techniqueMountSettings.js:1938 判定它是「双重幽灵」——无流派声明
    # needs.zuoShan、快照 builder 全文不消费（三元玄空段末自注「坐向卦须六十四卦天圆图…本法从缺」），
    # 选它 100% 无效果。声称一个不存在的能力比缺这个能力更糟。
    mingYear: str | None = Field(default=None, description="命年干支（乌兔/玄空用），缺省「甲子」。")


class TongSheFaInput(FlexibleModel):
    taiyin: str | None = "巽"
    taiyang: str | None = "坤"
    shaoyang: str | None = "震"
    shaoyin: str | None = "震"


class CanPingInput(FlexibleModel):
    # 邵子参评数（金锁银匙）computes its four pillars from the bazi chain in-process (not the ken
    # backend), so it only needs the birth date/time plus longitude+zone for the true-solar option.
    # `lat` is deliberately not required — canping's bazi only consumes lon for the time correction.
    date: str
    time: str
    zone: str | None = None
    lon: str | None = None
    gender: str | int | None = None
    # timeAlg=0 → 真太阳时 (longitude + equation-of-time); any other value → clock time. 缺省 0（sync311 wave 3b，
    # 此前误为 1）：上游无头 buildFieldObject timeAlg = record.timeAlg ?? 0（aiAnalysisContext.js:603）；页面
    # CanPingMain `fieldVal(f,'timeAlg',1)` 读的全局字段恒在、出厂种子 0，回退 1 不生效（详 tools/canping.js 注）。
    timeAlg: int | None = 0
    # 晚子时双开关（仅 hour==23 生效，见 references/late-zi.md）：after23NewDay=1 日柱进次日；
    # lateZiHourUseNextDay=1(默认) 时干用次日日干起子时、=0 用今日。None → JS 取上游出厂 1/1（tools/canping.js）。
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None
    # method: 'ming' (明法·月支反向取日宫) or 'gu' (古法·八字日支为日宫).
    method: str | None = "ming"
    # dayunRule: 'mingGongQiyun'(默认·《参评诀》单双月数日÷3) / 'mingGongOne'(一岁起运) /
    # 'baziStyle'(节气起运，与八字盘同源)。镜像上游 aiAnalysisContext.js:1903 的每技法设置；
    # 上游 [Win-D69] 记的正是「页面选了档、挂载不传 → 挂载恒回落默认档+一岁起」这个 bug。
    dayunRule: str | None = None


class HeLuoInput(FlexibleModel):
    # 河洛理数 computes its four pillars from the bazi chain in-process (not the ken backend); it needs
    # the birth date/time plus longitude+zone for the true-solar option. `lat` is not required.
    date: str
    time: str
    zone: str | None = None
    lon: str | None = None
    gender: str | int | None = None
    # timeAlg=0 → 真太阳时; any other value → clock time. 缺省 0（sync311 wave 3b，此前误为 1；上游无头
    # buildFieldObject timeAlg = record.timeAlg ?? 0，aiAnalysisContext.js:603；页面全局字段出厂种子 0，详 tools/heluo.js 注）。
    timeAlg: int | None = 0
    # 晚子时双开关（仅 hour==23 生效，见 references/late-zi.md）：None → JS 取上游出厂 1/1（tools/heluo.js）。
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None
    # 取法分歧四轴 + 流年法 + 阳令手定（缺省 = 引擎内建默认，逐字零回归；口径见 vendor/heluo/heluoLocal.js
    # 顶部【分歧参数】注释）。v0.36.0：此前 tools/heluo.js 把流年法发成死键 step2，引擎永远走应爻法。
    ziShuMode: str | None = None  # 'pair'★ 成对全取 | 'single' 每支阴阳取一数（实验）
    jiGongMode: str | None = None  # 'manualSanYuan'★ 三元表 | 'legacy'
    zhiZunEnabled: bool | int | str | None = None  # 三至尊卦（默认启用）
    pureGanKunVariant: str | None = None  # 'current'★ | 'alt' 纯卦乾坤落爻反向（抄本异·待核）
    liunianStep2: str | None = None  # 'ying'★ 应爻法 | 'sequential' 逐爻上行
    monthYangLing: bool | int | str | None = None  # 阳令手定；缺省按月支推
    # 上游挂载 schema heluo 另两键（techniqueMountSettings.js:1883-1904）：
    # 'tuWangKunGen'★ 土王寄坤艮 | 'siFangBoOnly' 直取四方伯（土用期不补坤艮）→ [命运篇] 化工行
    quHuaGong: str | None = Field(default=None, description="取化工 tuWangKunGen/siFangBoOnly")
    # 纪年基准（黄帝纪元差，缺省 2697，0 可达）→ [断验] 纪年行
    huangdiOffset: int | None = Field(default=None, description="黄帝纪元差(缺省2697)")


class YizhangjingInput(FlexibleModel):
    # 一掌经：进程内纯函数排盘（农历/四柱来自 bazi 链）。岁首＝正月初一（非立春），异于八字口径。
    date: str
    time: str
    zone: str | None = None
    lon: str | None = None
    gender: str | int | None = None
    # 时间算法：0 真太阳时（缺省，sync311 wave 3b 起；此前误为 1）| 1 钟表时。上游无头 buildFieldObject
    # timeAlg = record.timeAlg ?? 0（aiAnalysisContext.js:603）；页面全局字段出厂种子 0（详 tools/yizhangjing.js 注）。
    timeAlg: int | None = 0
    # 日界/晚子时：None → JS 侧按上游 YiZhangJingMain 缺席回退全局出厂默认 1/1（23 点算次日）。
    after23NewDay: int | None = Field(default=None, description="日界 1=23点换日(缺省)")
    lateZiHourUseNextDay: int | None = Field(default=None, description="晚子时干 1=次日(缺省)")
    # 排盘选项 = 上游 KinAstroMain.buildYizhangjingOpts 同键，缺省 = KINASTRO_PAGE_SETTINGS 出厂档
    # （「秘传口诀」预设，KinAstroMain.js:1039-1056）：定月法 lunar 农历月 / jieqi 节气月；顺逆 yangNanYinNv /
    # menShunNvNi；命宫 shiShang / shuZhiMao；大限一宫 7 或 10 年；大限起法 mi / age1；小限起宫 ri / yue；
    # 小限顺逆 chart 随盘 / always 一律顺行；逐年法 xiaoxian 小限 / liunian 流年十二神 / 未设=两法并列（上游 AI
    # 挂载无头重算缺省，见 tools/yizhangjing.js 注；桌面页出厂为小限）；流年十二神组
    # A/B/C；早子时；重犯口诀组 alpha / beta；星名系统 A/B/C；六道术语 gui / edao；童限显示；
    # 神煞合参层（出厂关，开则多出 [神煞合参] 段）。
    dingYue: str | None = "lunar"
    shunniRule: str | None = "yangNanYinNv"
    mingGongMethod: str | None = "shiShang"
    dayunLength: int | None = 7
    dayunStartAge: str | None = "mi"
    xiaoxianStart: str | None = "ri"
    xiaoxianDir: str | None = Field(default="chart", description="小限 chart随盘/always顺行")
    annualMethod: str | None = Field(default=None, description="逐年法 xiaoxian/liunian")
    flowShenSet: str | None = "A"
    zaoZiAdjust: bool | None = False
    chongfanKou: str | None = "alpha"
    starNaming: str | None = Field(default="A", description="星名 A/B/C")
    daoTerm: str | None = Field(default="gui", description="六道术语 gui/edao")
    tongxianShow: bool | None = Field(default=True, description="童限(缺省开)")
    shenshaLayer: bool | None = False
    # 折半法与品级变体（缺省字节不变；vendor/yizhangjing/yizhangjingReport.js）：
    leapRule: str | None = None  # 'half'★ 十五折半 | 'midnight' 夜半折半（十五日晚子时作下月）
    gradeSet: str | None = None  # 'standard'★ | 'variant' 品级变体表


class BaziInverseInput(FlexibleModel):
    # 八字反查（v0.36.0 C2）：四柱干支 → 候选公历出生时刻（Java /common/inversebazi，上游 BaZiHelper.getBirthes）。
    # 纯反查、不涉结果敏感设置 → 免确认门（与 astrodata 同类）。
    pillars: list[str] | None = Field(default=None, description="四柱干支 [年, 月, 日, 时]，如 ['甲子','丙寅','戊辰','庚申']；也可分给 year/month/day/hour。")
    year: str | None = None
    month: str | None = None
    day: str | None = None
    hour: str | None = None
    count: int | None = Field(default=3, description="候选时刻数量（1–10，默认 3）。")
    desc: bool | None = Field(default=True, description="true=从 fromYear 向过去逐年回推（默认）；false=向未来。")
    fromYear: int | None = Field(default=None, description="回推起始公历年（缺省=后端当前年）。")
