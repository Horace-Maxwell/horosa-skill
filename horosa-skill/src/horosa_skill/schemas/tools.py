from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    agent_confirmed_settings: bool | None = None
    defaults_accepted: bool | None = None
    clarification_notes: str | None = None


class PlanetInfoSettingInput(FlexibleModel):
    showHouse: int | bool | None = 1
    showRuler: int | bool | None = 1


class AstroMeaningSettingInput(FlexibleModel):
    enabled: int | bool | None = 0


class BirthInput(FlexibleModel):
    date: str = Field(description="公历日期 YYYY-MM-DD（如 1995-06-03）；公元前配 ad=-1。")
    time: str = Field(description="时间 HH:mm 或 HH:mm:ss（24 小时制，如 05:30）。")
    zone: str = Field(description="时区：+08:00 这类固定偏移，或 IANA 名（如 Asia/Shanghai，按盘面日期自动折算）。")
    lat: str = Field(description="纬度：31n13（31°13'N）或十进制 31.2167（会自动归一）；南纬用 s。")
    lon: str = Field(description="经度：121e28（121°28'E）或十进制 121.4667（会自动归一）；西经用 w。")
    ad: int | None = Field(default=1, description="纪元：1=公元后（默认），-1=公元前。")
    # 响应视图（所有技法工具通用，FlexibleModel 均接受）：None=完整；"sections"=段标题+正文；
    # "titles"=只留段标题索引。仅精简返回体，完整快照照常存档（memory_show 可取回）。
    response_view: str | None = Field(
        default=None,
        description="响应精简视图：缺省=完整；'sections'=段标题+正文；'titles'=只留段标题索引（完整结果已存档，memory_show 可取回）。",
    )
    hsys: int | None = Field(default=0, description="宫制：0=整宫 Whole Sign（默认）、1=Placidus 等（详见 agent_guidance）。")
    tradition: bool | None = False
    predictive: bool | None = True
    southchart: bool | None = False
    zodiacal: int | bool | None = Field(default=0, description="黄道：0=回归 tropical（默认），1=恒星 sidereal（配 siderealAyanamsa）。")
    # 恒星黄道 ayanāṃśa (星阙 v2.6.4)：仅在 zodiacal=1(恒星) 时生效，选 47 个岁差模式之一
    # (lahiri/raman/krishnamurti/fagan_bradley/…，见 astro_sidereal.SIDEREAL_AYANAMSA_LABELS)。
    # 缺省(不传) == Lahiri，向后兼容回归黄道盘不受影响。贯穿全西洋技法盘(命占/合盘/中点/卜卦/三式/节气)。
    siderealAyanamsa: Any | None = None
    pdtype: Any | None = None
    pdMethod: Any | None = None
    pdTimeKey: Any | None = None
    pdaspects: list[int | str] | None = None
    # 主限法（星阙 v3.6.0 大改版）：顺/逆向、映点(antiscia)、界(terms) promissor 开关 + 年限上限。
    # pdMethod 现为**方位法全谱 13 法**（旧「核5」注记已过期两代）；pdTimeKey 含每盘真算
    # Simmonite/Kepler/Brahe/VanDam + 动态 TrueSolarArc/SymbolicSolarArc + 自定义率；
    # pdYears 上限 3000（>360 出多圈复发行）。仅在显式设置时透传（model_dump(exclude_none=True)），
    # 缺省走后端默认（顺逆都开/映点界关/100 年）。白名单在上游 astropy/astrostudy/perchart.py。
    pdDirect: Any | None = None
    pdConverse: Any | None = None
    pdAntiscia: Any | None = None
    pdTerms: Any | None = None
    pdYears: Any | None = None
    # v3.6.0 正交解耦：弧算法(投影) × 盘面宫制(分宫) 拆成两个独立轴，不再由 pdMethod 一个键决定。
    # 这些字段此前已能经 FlexibleModel extra 透传到后端并真实生效，但没有 schema 描述 = agent 发现不了，
    # 等于事实上不可用。声明出来即解锁（零 service 改动）。
    pdProjection: Any | None = Field(default=None, description="弧算法/投影（11 种）：与 pdFrame 正交，决定弧如何投影。")
    pdFrame: Any | None = Field(default=None, description="盘面宫制/分宫 frame（12 种，含 koch）：与 pdProjection 正交。")
    pdFramework: Any | None = Field(default=None, description="界行框架：aspect | bounds | release（hyleg/anareta 判读层）。")
    pdSignificators: Any | None = Field(default=None, description="应星扩展：Desc/IC/Syzygy/Spirit/Cusps/Stars/Lots 等。")
    pdPromissorTypes: Any | None = Field(default=None, description="迫星类型扩展：cusps / stars / lots。")
    pdTimeKeyCustom: Any | None = Field(default=None, description="自定义时间钥匙速率（0.001–30 度/年）。")
    pdParallel: Any | None = Field(default=None, description="赤纬平行是否计入（三类被限星之一）。")
    pdRaptParallel: Any | None = Field(default=None, description="周日运动平行（rapt parallel）是否计入。")
    # 古典参数全局化（星阙 v3.6.0）：以下 16 键由后端 webmodernsrv 统一透传给古典判读层，
    # 影响 [古典] / [古典格局] 段的逐值结果（容许度、空亡口径、界表流派、交点性质…）。
    # 与主限法同理：本仓早已能经 extra 透传，声明只为可发现性。
    westNodeType: Any | None = Field(default=None, description="交点取法：真交点 / 平交点。")
    sectBuffer: Any | None = Field(default=None, description="同异宗(sect)判定的地平缓冲角。")
    cazimiOrb: Any | None = Field(default=None, description="核心内(cazimi)容许度。")
    combustOrb: Any | None = Field(default=None, description="燃烧(combust)容许度。")
    underBeamsOrb: Any | None = Field(default=None, description="日光下(under the beams)容许度。")
    vocMode: Any | None = Field(default=None, description="月空(void of course)判定口径（六种之一）。")
    vocIncludeOuter: Any | None = Field(default=None, description="月空判定是否计入外行星。")
    starOrb: Any | None = Field(default=None, description="恒星触发容许度。")
    antisciaOrb: Any | None = Field(default=None, description="映点(antiscia)容许度。")
    viaCombustaVariant: Any | None = Field(default=None, description="燃烧之路(via combusta)区间口径。")
    termsVariant: Any | None = Field(default=None, description="界(terms)表流派：埃及 / 托勒密 等。")
    leoBoundFirst: Any | None = Field(default=None, description="狮子座界首主星口径。")
    geminiBoundEmended: Any | None = Field(default=None, description="双子界表勘误（v3.6.0 修订）。")
    triplicity: Any | None = Field(default=None, description="三分主星体系（Dorotheus / Ptolemy 等）。")
    # saturnExalt20 已随上游 v3.9.3 删档（2026-08-18 上游拍板：degree 位全仓零消费者=真死开关，
    # push_request_exalt_variants 签名 2→1 参）。typed 字段保留只会向 agent 广告一个死开关。
    nodeExaltation: Any | None = Field(default=None, description="交点是否参与旺弱(exaltation)判定。")
    gpsLat: float | None = None
    gpsLon: float | None = None
    includePrimaryDirection: bool | None = None
    simpleAsp: bool | None = None
    strongRecption: bool | None = None
    virtualPointReceiveAsp: bool | None = None
    doubingSu28: bool | None = None
    nodeRetrograde: bool | None = None
    asporb: float | None = 1.0
    datetime: str | None = None
    dirLat: str | None = None
    dirLon: str | None = None
    dirZone: str | None = None
    startSign: str | None = None
    stopLevelIdx: int | None = None


class IndiaChartInput(BirthInput):
    # 印度占星 (星阙 v2.6.4)：分宫制 4→全 24 制(indiaHsys 0–24)、黄道岁差 6→全 47(indiaAyanamsa)。
    # 印占恒星黄道引擎 pyswisseph，与西洋 siderealAyanamsa 共用 47 套岁差键。缺省 hsys=0(整宫)/lahiri。
    # 后端 webindiasrv 读 indiaHsys/indiaAyanamsa（亦兼容 hsys/ayanamsa/siderealMode）。
    indiaHsys: Any | None = None
    indiaAyanamsa: Any | None = None
    # 印占大扩容（星阙 v3.6.0）：KP 完整化 / SBC / 七新大运体系 / Ayurdaya / 纳迪 / Tajika / Prashna。
    # 后端 webindiasrv 已读这些键（本仓经 FlexibleModel extra 早已能透传），此处声明只为让 agent 看得见。
    dashaVariants: Any | None = Field(default=None, description="大运流派 21 开关（Vimśottarī/Kālachakra/Yogini… 的分派选项）。")
    dashaYearLength: Any | None = Field(default=None, description="大运年长档：五档（360日/365.25日/恒星年…）。")
    vargaVariant: Any | None = Field(default=None, description="分割盘(varga)流派：Parāśara / Jaimini 等口径。")
    karakaScheme: Any | None = Field(default=None, description="Chara Kāraka 取法（7/8 星制）。")
    yuddhaCriterion: Any | None = Field(default=None, description="行星战(graha yuddha)胜负判据。")


class PlanetCyclesInput(FlexibleModel):
    """行星周期：任意两星的合/冲时间轴（世运周期研究的骨架数据；无出生盘概念）。"""

    startYear: int | None = Field(default=None, description="起始年（缺省 1900）")
    endYear: int | None = Field(default=None, description="结束年（缺省 2100；区间上限 3400 年）")
    p1: str | None = Field(default=None, description="星一（英文名，缺省 Jupiter）：Jupiter/Saturn/Uranus/Neptune/Pluto/Mars…")
    p2: str | None = Field(default=None, description="星二（英文名，缺省 Saturn）")
    aspect: float | None = Field(default=None, description="相位角：0=合（缺省）/ 180=冲（任意角度亦可）")
    center: str | None = Field(default=None, description="坐标系：geo=地心（缺省）| helio=日心 | topo=站心")
    response_view: str | None = None


class JieQiBirthInput(BirthInput):
    """出生节气窗：定位出生时刻前后的节气精确时刻（八字起运窗的同源数据）。"""

    useLocalMao: int | None = Field(default=None, description="真太阳时卯时口径开关（0/1，缺省 0，上游同默认）")
    byLon: int | None = Field(default=None, description="按经度修正开关（0/1，缺省 0，上游同默认）")


class IndiaRectifyInput(BirthInput):
    """印度（KP 法）出生时间校正：以给定时刻为锚，在 ±半窗内扫描候选并按判据打分排序。

    date/time 是**待校正的出生时刻锚点**；判据 = RP（Ruling Planets 命中）/ Pranapada /
    边界（gandanta 甘丹塔预警）+ 可选事件评分（rectifyEvents 录入后才参评）。
    输出证据与排序，是否采用由用户决定（上游免责声明原样带回）。
    """

    rectifyWindowMinutes: float | None = Field(default=None, description="扫描半窗（分钟），缺省 30，上限 240（锚点前后各半窗）")
    rectifyStepSeconds: int | None = Field(default=None, description="扫描步长（秒），缺省 60，上限 600；过粗会整段跳过 KP 子主（响应带步长诊断）")
    rectifyTopK: int | None = Field(default=None, description="返回候选榜条数，缺省 3，上限 10")
    rectifyRpSource: str | None = Field(default=None, description="RP 取法：anchor（缺省，按原始钟表时刻取 RP，无自指）|candidate（字面读法，自动消解自指）")
    rectifyEvents: list[dict[str, Any]] | None = Field(
        default=None,
        description="人生事件列表（可选）：录入后事件评分才参评（criteriaActive 会如实回显参评判据）。",
    )
    indiaHsys: Any | None = Field(default=None, description="印占分宫制 0–24（缺省 0=整宫）")
    indiaAyanamsa: Any | None = Field(default=None, description="印占岁差键（缺省 lahiri，47 套同西洋 siderealAyanamsa）")
    tripataki: Any | None = Field(default=None, description="Tripatāki 三旗盘（opt-in，宿距三旗）。")
    prashnaTime: Any | None = Field(default=None, description="问事(Praśna)盘时刻；不传则用主盘时刻。")
    prashnaSchools: Any | None = Field(default=None, description="问事三派选择。")
    prashnaMatter: Any | None = Field(default=None, description="问事事项/所问之题。")
    prashnaNumber: Any | None = Field(default=None, description="问事数（ārūḍha 起数法用）。")
    prashnaCuspMode: Any | None = Field(default=None, description="问事盘宫头取法。")
    prashnaPrimaryHouse: Any | None = Field(default=None, description="问事主事宫指定。")
    tajakaYear: Any | None = Field(default=None, description="Tājika 年盘的目标年份。")
    annualChartType: Any | None = Field(default=None, description="年盘类型（阴历年盘 / 太阳返照年盘等）。")
    varshaLat: Any | None = Field(default=None, description="年盘地点纬度（不传沿用本命地）。")
    varshaLon: Any | None = Field(default=None, description="年盘地点经度（不传沿用本命地）。")


class PredictiveInput(BirthInput):
    predictive: bool | None = False


class RelativePartyInput(FlexibleModel):
    date: str
    time: str
    zone: str
    lat: str
    lon: str
    ad: int | None = 1
    name: str | None = None


class RelativeInput(FlexibleModel):
    inner: RelativePartyInput
    outer: RelativePartyInput
    hsys: int | None = 0
    zodiacal: int | None = 0
    siderealAyanamsa: Any | None = None
    relative: int | None = 0


class ZiWeiBirthInput(FlexibleModel):
    date: str
    time: str
    zone: str
    lat: str
    lon: str
    gender: bool | None = Field(default=True, description="性别：true/1=男（默认），false/0=女；'男'/'女'/'M'/'F' 会自动归一。")
    after23NewDay: bool | None = Field(default=False, description="日界开关：23 点后是否按次日日柱（星阙默认按当日=false；后端神数/三式默认为 1）。")
    # 晚子时时柱开关：None=不发送（沿用后端默认 1=时干按次日日干起子时）；显式 0/1 全链穿透。
    lateZiHourUseNextDay: int | bool | None = None
    timeAlg: int | None = Field(default=0, description="时间算法：0=平太阳时（默认），1=真太阳时。")
    sihua: dict[str, list[str]] | None = None
    ad: int | None = 1
    # 紫微流派叠层（星阙 v3.6.0「死开关接活」批）：这些开关在上游驱动 [流派叠层] / [运限] 段。
    # 声明出来即可显式透传；本仓对应导出段的接入见 exports/registry.py（回填批 4-3）。
    sihuaSchool: Any | None = Field(default=None, description="四化流派（中州 / 飞星 / 钦天 等）。")
    childLimit: Any | None = Field(default=None, description="童限取法。")
    zhongxian: Any | None = Field(default=None, description="中限（三限之一）取法。")
    huoPan: Any | None = Field(default=None, description="活盘（三限活盘）开关。")
    qishuWei: Any | None = Field(default=None, description="起数位（安星起点流派）。")
    borrowPalace: Any | None = Field(default=None, description="借宫（空宫借对宫）规则。")
    taiSuiRuGua: Any | None = Field(default=None, description="太岁入卦法开关。")
    taiSuiRelatives: Any | None = Field(default=None, description="太岁六亲取法。")
    # [运限] / [流派叠层]：上游由界面勾选与流派开关驱动，headless 开成显式入参。
    period: dict[str, Any] | None = Field(default=None, description="运限时段选择 {daxian:[], liunian:[], liuyue:[], liuri:[], liushi:[]}。")
    schools: dict[str, Any] | None = Field(default=None, description="流派叠层开关 {childLimit, zhongxian, huoPan, qishuWei, borrowPalace, taiSuiRuGua, taiSuiRelatives:[{branch,role,sex}]}；结果敏感。")


class ZiWeiRulesInput(FlexibleModel):
    pass


class BaZiBirthInput(FlexibleModel):
    date: str
    time: str
    zone: str
    lat: str
    lon: str
    godKeyPos: str | None = None
    timeAlg: int | None = 0
    byLon: bool | None = False
    after23NewDay: bool | None = False
    # 晚子时时柱开关：None=不发送（沿用后端默认 1=时干按次日日干起子时）；显式 0/1 全链穿透。
    lateZiHourUseNextDay: int | bool | None = None
    phaseType: int | None = 0
    ad: int | None = 1
    # [多运限·指定时段]：上游由界面勾选驱动，headless 开成显式入参。语义同上游 ——
    # 流年 × 流月笛卡尔各一段；流日/流时锚定到所选的第一个上层；总段数封顶 50。
    period: dict[str, Any] | None = Field(default=None, description="多运限时段选择 {liunian:[公历年], liuyue:[月序1-12], liuri:[公历日], liushi:[时辰序0-11]}。")


class BaZiDirectInput(BaZiBirthInput):
    gender: bool | None = True
    adjustJieqi: bool | None = False
    # [多运限·指定时段]：上游由界面勾选驱动，headless 开成显式入参。语义同上游 ——
    # 流年 × 流月笛卡尔各一段；流日/流时锚定到所选的第一个上层；总段数封顶 50。
    period: dict[str, Any] | None = Field(default=None, description="多运限时段选择 {liunian:[公历年], liuyue:[月序1-12], liuri:[公历日], liushi:[时辰序0-11]}。")


class LiuRengGodsInput(FlexibleModel):
    date: str
    time: str
    zone: str
    lat: str
    lon: str
    gpsLat: float | None = None
    gpsLon: float | None = None
    after23NewDay: bool | None = False
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


class JieQiYearInput(FlexibleModel):
    year: int | str
    zone: str
    lat: str
    lon: str
    time: str | None = None
    hsys: int | None = 0
    doubingSu28: bool | None = False
    southchart: bool | None = False
    seedOnly: bool | None = False
    zodiacal: int | None = 0
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
    after23NewDay: bool | None = False
    # 晚子时时柱开关：None=不发送（沿用后端默认 1=时干按次日日干起子时）；显式 0/1 全链穿透。
    lateZiHourUseNextDay: int | bool | None = None
    timeAlg: int | None = 0
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
    tongshu: dict[str, Any] | None = Field(default=None, description="通书择日设置 {school, event, liexiuUse, zuoShan, mingYear}；school 结果敏感。")
    rizi: dict[str, Any] | None = Field(default=None, description="日子馆 {event, year, topN, persons:[{name,date,time,gender,role}]}；给了 persons 才产 [日子馆·个性化择日]/[当事人八字]。")


class HuangliInput(FlexibleModel):
    # 老黄历日课：纯前端本地推演（lunar-javascript + 择日表），零后端往返，故无需 zone/经纬。
    date: str
    hour: int | None = Field(default=None, description="0–23 整点小时；影响 [时辰吉凶] 的当前时标记，缺省 12。")


class TongshuInput(FlexibleModel):
    # 通书择日：五流派各自独立的断语表，同一天在不同流派下结论可以完全相反 → school 结果敏感。
    date: str
    school: str | None = Field(default=None, description="流派：donggong 董公 / qimen 奇门叠数 / sanyuan 三垣列宿 / wutu 天元乌兔 / xuankong 三元玄空大卦。")
    event: str | None = Field(default=None, description="用事（嫁娶 / 开市 / 安葬 …），缺省「嫁娶」。")
    liexiuUse: str | None = Field(default=None, description="三垣列宿用事类（断语高亮），缺省「建宅」。")
    zuoShan: str | None = Field(default=None, description="坐山（玄空大卦用），缺省「子」。")
    mingYear: str | None = Field(default=None, description="命年干支（乌兔/玄空用），缺省「甲子」。")


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


class QimenZeriInput(QimenInput):
    """奇门择日「找局」：在时间窗内扫出满足条件树的时辰。

    盘面参数与 QimenInput 逐字相同（同一套 22 项 options / 晚子时 / 时家算法），只多出搜索窗与条件树 ——
    展示盘仍走 ken `/qimen/pan`，只有区间**搜索**用本地引擎（见 service._run_qimenzeri_tool 的算权说明）。
    """

    startDate: str | None = Field(default=None, description="搜索窗起始日（YYYY-MM-DD）")
    startTime: str | None = Field(default="00:00", description="搜索窗起始时刻（HH:mm）")
    endDate: str | None = Field(default=None, description="搜索窗结束日（YYYY-MM-DD）")
    endTime: str | None = Field(default="23:59", description="搜索窗结束时刻（HH:mm）")
    # 条件树按 passthrough 而非建模：上游有 30+ 条件类，各自 params 形状/validate/compile 都不同，
    # 在此重编一遍等于造第二份真值源，上游一加条件类就烂；vendored compileQimenTree 会跑各叶子自己的
    # validate 抛本地化错误。可发现性放 agent_guidance（列条件类键与必填 params）。
    conditions: Any | None = Field(
        default=None,
        description=(
            "条件树。组节点 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶节点 {type:'<条件类键>', params:{…}}。条件类键与参数见本工具的 agent_guidance。"
        ),
    )
    maxSpanDays: int | None = Field(default=None, description="搜索窗跨度上限（天），缺省 92")
    maxHits: int | None = Field(default=None, description="命中区间数上限，缺省 1000")


class TianxingInput(BirthInput):
    """天星择日·征象搜索：在时间窗内扫出满足西占征象条件的时段。

    lat/lon/zone/hsys/zodiacal 复用 BirthInput —— 它们就是**搜索盘**的坐标与口径，不另起一套词汇。
    date/time 是 [起盘信息] 展示的锚点时刻，缺省取窗口起点。
    """

    startDate: str | None = Field(default=None, description="搜索窗起始日（YYYY-MM-DD）")
    startTime: str | None = Field(default="00:00", description="搜索窗起始时刻（HH:mm）")
    endDate: str | None = Field(default=None, description="搜索窗结束日（YYYY-MM-DD）")
    endTime: str | None = Field(default="23:59", description="搜索窗结束时刻（HH:mm）")
    pos: str | None = Field(default=None, description="地点显示名，进 [征象搜索配置] 段")
    conditions: Any | None = Field(
        default=None,
        description=(
            "征象条件树。组节点 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶节点 {type:'<条件类键>', params:{…}}。32 个条件类键见本工具的 agent_guidance。"
        ),
    )
    precision: str | None = Field(default=None, description="扫描精度，缺省 minute")
    explainAt: str | None = Field(
        default=None,
        description=(
            "单时刻判据判读（YYYY-MM-DD HH:mm[:ss]）：对该时刻逐叶判读条件树（与扫描求值器绝对同源），"
            "加产 [单时判读] 段——每叶列「设定/实际 ✓✗」。用于回答「为什么这个时刻中/不中选」。"
            "Explain one moment leaf-by-leaf against the condition tree (adds a [单时判读] section)."
        ),
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="古典口径直通（cazimiOrb/combustOrb/vocMode/termsVariant/triplicity…）。",
    )


class QizhengElectionInput(BirthInput):
    """七政择日动盘（果老「择日双轮」headless 版）。

    date/time/zone/lat/lon 复用 BirthInput —— 它们就是**候选择日时刻**的坐标，非出生盘。
    三个动作共用一套入参：pan 用全部；eclipses 只用 date/zone(+kind/count)；
    azimuthsearch 用 date/time/zone/坐标(+body/targetAz/days)。
    """

    action: str | None = Field(
        default="pan",
        description=(
            "pan=十一曜动盘（黄道地支度/二十四山位/地平高度/顺逆）| eclipses=未来日月食搜索 | "
            "azimuthsearch=星曜到达目标罗盘方位的时刻搜索"
        ),
    )
    height: float | None = Field(default=None, description="海拔（米），缺省 0")
    nodeType: str | None = Field(default=None, description="罗计口径：mean（缺省）|true")
    lilithType: str | None = Field(default=None, description="月孛口径：mean（缺省）|true")
    ayanamsaDeg: float | None = Field(default=None, description="恒星制岁差回加度（回归制传 0/不传）")
    eleLifeMode: str | None = Field(default=None, description="命度起法：sunrise（缺省）|sunset|custom")
    eleLifeCustomTime: str | None = Field(default=None, description="eleLifeMode=custom 时的起命时刻 HH:mm:ss")
    extraBodies: list[dict[str, Any]] | None = Field(
        default=None,
        description=(
            "外圈透传星（照上游果老盘惯例：紫炁/天海冥从流年盘取黄经黄纬传入）："
            "[{id,label,lon,lat?,speed?}…]，后端按 lon/lat 算地平方位。"
        ),
    )
    plate: str | None = Field(default=None, description="二十四山盘别：di=地盘（缺省）|tian=天盘(+7.5°)|ren=人盘(−7.5°)")
    ziZheng: str | None = Field(default=None, description="子正口径：true=真北（缺省）|magnetic=磁北（配 declination）")
    declination: float | None = Field(default=None, description="磁偏角（东偏为正；仅 ziZheng=magnetic 时套用）")
    kind: str | None = Field(default=None, description="eclipses 专用：solar=日食（缺省）|lunar=月食")
    count: int | None = Field(default=None, description="eclipses 专用：搜索数量（缺省 8，上限 24）")
    targetAz: float | None = Field(default=None, description="azimuthsearch 专用：目标罗盘方位 0-359.9（0=北顺时针）")
    days: int | None = Field(default=None, description="azimuthsearch 专用：向后搜索天数（缺省 3，上限 30）")
    body: str | None = Field(default=None, description="azimuthsearch 专用：星曜中文标签 日月金木水火土（缺省 日）")


class TaiyiInput(BirthInput):
    # after23NewDay None=不发送（ken 权威引擎默认 1）；显式 0/1 直达 /taiyi/pan 与 nongli 前置。
    after23NewDay: bool | None = None
    # 晚子时时柱开关：None=不发送（沿用后端默认 1=时干按次日日干起子时）；显式 0/1 全链穿透。
    lateZiHourUseNextDay: int | bool | None = None
    timeAlg: int | None = 0
    gender: str | int | None = None
    options: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "引擎参数直通（style/tn/局式…）。太乙流派六轴（jishen/wenchang/keJianChen/sanji/youshen/"
            "shijiCoord）也放这里——上游 v3.6.0 已把它们接活为真产段的开关。"
        ),
    )
    nongli: dict[str, Any] | None = None


class JinKouInput(LiuRengGodsInput):
    diFen: str | None = None
    guirengType: int | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    liureng: dict[str, Any] | None = None


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
    # timeAlg=0 → 真太阳时 (longitude + equation-of-time); any other value → clock time. Default 1
    # (clock time) mirrors 星阙 CanPingMain.js's `fieldVal(f, 'timeAlg', 1)`.
    timeAlg: int | None = 1
    # 晚子时双开关（仅 hour==23 生效，见 references/late-zi.md）：after23NewDay=1 日柱进次日；
    # lateZiHourUseNextDay=1(默认) 时干用次日日干起子时、=0 用今日。缺省不传 → 上游默认口径。
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None
    # method: 'ming' (明法·月支反向取日宫) or 'gu' (古法·八字日支为日宫).
    method: str | None = "ming"


class HeLuoInput(FlexibleModel):
    # 河洛理数 computes its four pillars from the bazi chain in-process (not the ken backend); it needs
    # the birth date/time plus longitude+zone for the true-solar option. `lat` is not required.
    date: str
    time: str
    zone: str | None = None
    lon: str | None = None
    gender: str | int | None = None
    # timeAlg=0 → 真太阳时; any other value → clock time. Default 1 mirrors 星阙 HeLuoMain.js.
    timeAlg: int | None = 1
    # 晚子时双开关（仅 hour==23 生效，见 references/late-zi.md）：缺省不传 → 上游默认口径。
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None


class YizhangjingInput(FlexibleModel):
    # 一掌经：进程内纯函数排盘（农历/四柱来自 bazi 链）。岁首＝正月初一（非立春），异于八字口径。
    date: str
    time: str
    zone: str | None = None
    lon: str | None = None
    gender: str | int | None = None
    timeAlg: int | None = 1
    # 排盘选项（默认即通行口径）：定月法 lunar 农历月 / jieqi 节气月；顺逆 yangNanYinNv 阳男阴女顺 /
    # menShunNvNi 男顺女逆；命宫 shiShang 时上起命 / shuZhiMao 数至卯；大限一宫 7 或 10 年；
    # 大限起法 mi 月宫起 / age1 一岁起；小限起宫 ri 日柱宫 / yue 月柱宫；流年十二神组；早子时归前日；
    # 重犯口诀组 alpha 常见 / beta 异传；神煞合参层（无头导出默认开，关则不出该段）。
    dingYue: str | None = "lunar"
    shunniRule: str | None = "yangNanYinNv"
    mingGongMethod: str | None = "shiShang"
    dayunLength: int | None = 7
    dayunStartAge: str | None = "mi"
    xiaoxianStart: str | None = "ri"
    flowShenSet: str | None = "A"
    zaoZiAdjust: bool | None = False
    chongfanKou: str | None = "alpha"
    shenshaLayer: bool | None = True


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
    item: str | None = None
    sound: str | None = None
    ke: int | None = None
    gong: str | None = None
    xqZhi: str | None = None
    xqYushu: int | None = None


class ACGInput(BirthInput):
    # 占星地图（AstroCartoGraphy）：本命时刻的行星地理投影线（MC/IC 恒定经度、ASC/DESC 曲线、
    # 天顶点、偕升纬度带、线交点）。口径开关：mode=mundo 真黄纬（Jim Lewis 原版，默认）/zodiac
    # 黄道度；lsMode=great 大圆（默认）/rhumb 等角航线；geodetic 地理等价流派 sepharial（默认）
    # /mcrae/johndro，变体 longitude（默认）/ra。地图渲染属 UI，无头输出为结构化线表。
    mode: str | None = "mundo"
    lsMode: str | None = "great"
    geodetic: str | None = "sepharial"
    geodeticVar: str | None = "longitude"
    # 落点分析（v0.33.0 批 I-4，/location/acgpoint）：给 clickLat/clickLon 时加产 [落点分析] 段。
    clickLat: float | None = Field(default=None, description="落点纬度（十进制；给了 clickLat+clickLon 才产 [落点分析] 段：该地命中线/重置四角/敏感点）")
    clickLon: float | None = Field(default=None, description="落点经度（十进制，西经为负）")
    pointOrb: float | None = Field(default=None, description="落点命中容许度（度，缺省 2.0）")
    pointHsys: str | None = Field(default=None, description="落点重置盘分宫制（缺省 whole）")
    # 事件时刻（/location/acgevent）：给 eventKind 时加产 [事件时刻] 段（CCG 事件线时刻）。
    eventKind: str | None = Field(
        default=None,
        description=(
            "世运事件类型：solar_eclipse|lunar_eclipse|newmoon|fullmoon|aries_ingress|cancer_ingress|"
            "libra_ingress|capricorn_ingress（给了才产 [事件时刻] 段，返回 UTC 时刻）"
        ),
    )
    eventDirection: str | None = Field(default=None, description="事件查找方向：next（缺省）|prev")
    eventFromDate: str | None = Field(default=None, description="事件查找起点日期 YYYY-MM-DD（缺省取盘面日期）")


class AstrodataInput(FlexibleModel):
    # 名人星盘数据库（离线只读检索）：query 走 FTS 全文（姓名/条目/出生地/维基摘要），
    # category 按分类过滤，rodden 按可信度评级过滤（AA/A/B/C/DD/X/XX，可传多个），
    # personTitle 精确取单人详情（含可直接转排盘的出生数据）。纯查询不改结果 → 免确认门。
    query: str | None = None
    personTitle: str | None = None
    category: str | None = None
    rodden: str | list[str] | None = None
    birthYearFrom: int | None = None
    birthYearTo: int | None = None
    hasTimeOnly: bool | None = False
    limit: int | None = 20
    offset: int | None = 0


class XuanshiInput(FlexibleModel):
    # 玄史（中国玄学史知识库）：runtime 自带两个只读 SQLite bundle（玄学事件 7900+ / 天象记录 27000+ /
    # 地名 / 人物图 2200+ 节点），由 python chart 服务的 /xuanshi/* 只读端点提供检索与结构视图。
    # 纯检索工具，无结果敏感设置。action 决定查哪个面：
    #   search（默认）= q 全文检索玄学事件；events/event = 多维过滤列表 / 单事件全档
    #   （原文+白话+解读+流程+结局+引证）；celestial/celestial_event = 天象记录；
    #   figures/figure = 人物；dynasties/dynasty = 朝代；techniques/technique = 术数门类；
    #   terms/term/term_profile = 天象名词；timeline = 宏观时间线（带 macro 下钻）；
    #   map = 地理点位；graph = 人物共现网络；stories/story = 专题故事；channels = 频道；
    #   daily = 今日推送；summary = 全库统计；microchronology / decade_omens / facets /
    #   events_meta = 编年细化 / 十年灾异 / 分面计数 / 列表页元数据。
    action: str | None = "search"
    q: str | None = Field(default=None, description="全文检索词（事件/人物/术数名皆可）。")
    id: str | None = Field(default=None, description="详情类 action 的条目 id（如事件 XTS-027）。")
    tradition: str | None = Field(default=None, description="传统过滤：正史 / 野载。")
    dynasty: str | None = Field(default=None, description="朝代过滤（如 唐 / 南北朝 / 志怪笔记）。")
    technique: str | None = Field(default=None, description="术数门类过滤（如 占星 / 相术 / 卜筮）。")
    history: str | None = Field(default=None, description="史书过滤（如 新唐书 / 晋书）。")
    evidence: str | None = Field(default=None, description="证据等级过滤。")
    omen: str | None = Field(default=None, description="天象类别过滤（如 彗星 / 日食，celestial 用）。")
    source: str | None = Field(default=None, description="天象出处过滤（celestial 用）。")
    year_from: int | None = Field(default=None, description="天象起始公历年（可负=公元前）。")
    year_to: int | None = Field(default=None, description="天象结束公历年。")
    macro: str | None = Field(default=None, description="timeline 宏观段下钻键。")
    period: str | None = Field(default=None, description="map 的时期过滤。")
    date_key: str | None = Field(default=None, description="daily 的日期键（YYYY-MM-DD，缺省今日）。")
    page: int | None = Field(default=None, description="列表页码（1 起）。")
    page_size: int | None = Field(default=None, description="每页条数（默认 30）。")
    limit: int | None = Field(default=None, description="search/timeline 下钻的条数上限。")
    top_n: int | None = Field(default=None, description="graph 节点上限（默认 70）。")
    min_weight: int | None = Field(default=None, description="graph 边最小权重（默认 2）。")


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
    liureng_yue: str | None = None
    liureng_isDiurnal: bool | None = None
    # [紫微四化]：上游由紫微子页签的 UI 状态驱动，headless 开成显式入参（下标越界回退末项，同上游钳制）。
    ziweiSihua: dict[str, Any] | None = Field(default=None, description="紫微四化层选择 {daxianIdx, liunianIdx}；给了才产 [紫微四化] 段。")


class SuZhanInput(BirthInput):
    szchart: int | None = 0
    szshape: int | None = 0
    houseStartMode: int | None = 1
    doubingSu28: bool | None = True


class GermanyInput(BirthInput):
    predictive: bool | None = False


class HarmonicInput(BirthInput):
    # 调波盘 (harmonic chart) is a backend chart-extra computation (POST /astroextra/harmonic on the
    # Python chart service). harmonic = the H-number (1–360, 星阙 default 9); orb = conjunction orb.
    predictive: bool | None = False
    harmonic: int | None = 9
    orb: float | None = 2.0


class BabylonInput(BirthInput):
    # 巴比伦占星（美索不达米亚天象体系）：恒星黄道 · 毕宿锚（Aldebaran = 金牛 15°）。
    # 本体系无十二宫位、无相位、无上升点——盘面是数据清单，解读装置是「位」(三分+日段) 与行星神性。
    # 派系口径直接改分至规范与「位」的落点 → 结果敏感，缺省不静默切换。
    predictive: bool | None = False
    scheme: str | None = Field(default=None, description="实位派系：swissA10（默认）/ systemA / systemB。")
    solstice: str | None = Field(default=None, description="分至规范：A10（春分白羊 10°，默认）/ B8（春分白羊 8°）。")
    era: str | None = Field(default=None, description="纪元口径（塞琉古纪年等）。")


class DraconicInput(BirthInput):
    # 龙盘 (draconic chart)：把命盘各点黄经减去北交点黄经（POST /astroextra/draconic）。
    # 后端返回 {nodeLon, positions, conjunctions, chart}，chart 与 /chart 同形。
    predictive: bool | None = False
    orb: float | None = 2.0


class RelocationInput(BirthInput):
    # 重置盘 (relocation)：保留出生 UT，仅用新经纬重算十二宫与上升/中天（POST /astroextra/relocation）。
    # 行星黄经由 UT 决定故不变，宫位/角点随地点变 —— 迁居占星的标准做法。
    # relocLat/relocLon 缺省回退到出生地，等于本命盘（结果敏感：不给新地点就不是「重置」）。
    predictive: bool | None = False
    relocLat: Any | None = Field(default=None, description="重置地纬度（如 51n30）；缺省回退出生地。")
    relocLon: Any | None = Field(default=None, description="重置地经度（如 0w07）；缺省回退出生地。")


class AgePointInput(BirthInput):
    # 年龄推进点 (Age Point / Huber): backend /predict/agepoint computes the whole Koch-house age-point
    # cycle from the natal chart (no separate target time). Needs predictive on so the predict engine runs.
    predictive: bool | None = True


class DistributionsInput(BirthInput):
    # 界推运 (Distributions / 分配法): backend /predict/dist computes the full-life term-distribution
    # timeline (Asc by primary motion through the Egyptian bounds). Natal params only.
    predictive: bool | None = True


class JaynesProgInput(BirthInput):
    # Jayne 赤纬推运 (v2.5.0): secondary progression to a target date, then declination parallels.
    predictive: bool | None = True
    targetDate: str | None = None
    targetTime: str | None = "12:00:00"
    orb: float | None = 1.0


class VedicProgInput(BirthInput):
    # 恒星推运 Vedic (v2.5.0): progressions under the sidereal zodiac.
    predictive: bool | None = True
    targetDate: str | None = None
    targetTime: str | None = "12:00:00"
    orb: float | None = 1.5


class PlanetaryArcInput(BirthInput):
    # 行星弧 (v2.5.0): directs the whole chart by the secondary-progressed arc of arcSource (default Moon).
    predictive: bool | None = True
    datetime: str | None = None
    asporb: float | None = 1.0
    arcSource: str | None = "Moon"


class PlanetaryAgesInput(BirthInput):
    # 行星年龄 (v2.5.0): Ptolemy seven ages — reads the natal chart, marks the band of asOf (default: none).
    predictive: bool | None = False
    asOf: str | None = None


class BalbillusInput(BirthInput):
    # Balbillus 129年系统 (v2.5.0): 旺距削减主限 — reads the natal chart, splits life into recursive sub-periods.
    predictive: bool | None = False


class TriplicityRulersInput(BirthInput):
    # 三分主星推运 (星阙 v2.6.x): 区间光体所在座的三颗三分主星按昼夜换序，划分人生各阶段。纯前端切分本命盘。
    predictive: bool | None = False


class KeypointsInput(BirthInput):
    # 数字相位推运 (星阙 v2.6.x): 七星小年数 + 自释放点起第 k 座挂钩，凡年龄为 k 或小年倍数即激活。纯前端切分本命盘。
    predictive: bool | None = False


class LunationPhaseInput(BirthInput):
    # 月相推运 (星阙 v2.6.x): 由本命日月黄经差 + 次限推进率(约12.19°/年)求推运八相时间轴。纯前端切分本命盘。
    predictive: bool | None = False


class ExtraReturnsInput(BirthInput):
    # 多重回归 (星阙 v2.6.x): 土/木/月交三体返照——逐体走后端 /astroextra/planetreturn 取最近数回返照日期。
    predictive: bool | None = False
    # 日月返照年表（v0.33.0 批 I-3，/astroextra/returns）：逐年太阳返照/首月返精确时刻 + 返照上升。
    timelineStartYear: int | None = Field(
        default=None,
        description="日月返照年表起始年（给了本参数或 timelineCount 才加产 [日月返照年表] 段；缺省取出生年）",
    )
    timelineCount: int | None = Field(default=None, description="年表年数（缺省 10，上限 40）")


class HoraryInput(BirthInput):
    # 卜卦 (horary): the chart is cast at the QUESTION moment (date/time/place = when the question was asked).
    # category picks the quesited house: general/wealth/family/property/pregnancy/health/marriage/lawsuit/
    # theft/death/travel/career/hope/enemy (unknown → general).
    category: str | None = "general"
    # 流派档（horarySchools.js 的 HORARY_SCHOOLS）：classical(默认) / renaissance / medieval …
    # 它决定两段的有无——[偶然尊贵满分表] 只在 accidentalMode=='lilly' 出、[阿拉伯点全集] 只在
    # lotsSet=='core15' 出，二者都是 renaissance/medieval 档的口径。结果敏感 → 缺省不静默切换。
    school: str | None = Field(default=None, description="卜卦流派档：classical / renaissance / medieval（默认 classical）。")
    tradition: bool | None = True
    predictive: bool | None = False
    # 卜卦七档参数谱（星阙 v3.6.0，界表勘误 + 判读叠层二期）。上游 horarySchools.js 的 HORARY_PARAM_SPEC
    # 中 hsys/termsVariant/geminiBoundEmended/tradition 标 sendToBackend，其余在判读层生效。
    hsys: Any | None = Field(default=None, description="卜卦盘分宫制（Regiomontanus 等，随流派档）。")
    termsVariant: Any | None = Field(default=None, description="界(terms)表流派：埃及 / 托勒密。")
    geminiBoundEmended: Any | None = Field(default=None, description="双子界表勘误开关（v3.6.0 修订）。")
    considerationsMode: Any | None = Field(default=None, description="定盘考量(considerations before judgment)口径。")
    receptionMode: Any | None = Field(default=None, description="接纳(reception)判定口径。")
    almutenScheme: Any | None = Field(default=None, description="Almuten 取法（Ibn Ezra / Lilly 等）。")
    lotsSet: Any | None = Field(default=None, description="阿拉伯点集合范围（全集 / 常用）。")


class ElectionInput(BirthInput):
    # 择日 (electional): the chart is cast at a CANDIDATE moment (date/time/place = the time being evaluated).
    # topicId picks the rule pack + hard flags: marriage/business/move_in/buy_property/trade/buy_car/contract/
    # surgery/travel/job_hunt/... (see TOPIC_MASTER; unknown → marriage).
    topicId: str | None = "marriage"
    tradition: bool | None = True
    predictive: bool | None = False
    # 择日五档真差异化（星阙 v3.6.0）：流派轴 + 八大分析模块 + 医疗择日危象参照。
    # 上游 electionParams.js 的 13 键；未声明前 agent 无从得知这些档位存在。
    school: Any | None = Field(default=None, description="择日流派档（五档：古典 / 现代 / 中西合参 等）。")
    dignityScheme: Any | None = Field(default=None, description="尊贵五重矩阵取法。")
    lotsSet: Any | None = Field(default=None, description="阿拉伯点全谱 / 常用集。")
    starSet: Any | None = Field(default=None, description="恒星集（41 恒星）参与与否。")
    considerationsMode: Any | None = Field(default=None, description="择前三清单(considerations)口径。")
    medicalCritical: Any | None = Field(default=None, description="医疗择日危象日参照开关。")
    hourRuler: Any | None = Field(default=None, description="时主(planetary hour)合参。")
    returnCharts: Any | None = Field(default=None, description="回归盘合参（太阳/月亮返照）。")
    primaryDirections: Any | None = Field(default=None, description="主限合参。")
    natalCompare: Any | None = Field(default=None, description="本命合参（与当事人本命盘比对）。")
    mundaneCompare: Any | None = Field(default=None, description="时势合参（世运盘比对）。")


class GeomancyInput(BirthInput):
    # 天文地占 (astronomical geomancy): 以起卦时刻(date/time/place)确定性起卦(castMethod='time' + timeSeed 由时刻派生)。
    # 后端由 4 母卦推 16 图形 + 十二宫图形入宫 + 判官/见证/解读技法 + 转宫派生 + 定局落星。question 为所问，
    # questionType 择 11 类问类。
    question: str | None = None
    questionType: str | None = "custom"
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
    # haltEnabled/compoundMode/numberSystem/chartMode/houseSystem/ascSource/namesSystem/parityScope）；
    # 未传=None → 内核回落 profile 默认，旧盘字节零变。
    options: dict[str, Any] | None = None


class TarotInput(BirthInput):
    # 塔罗：以起卦时刻确定性抽牌（date/time 派生种子，同刻同盘可复现；lat/lon/zone 仅为一致复用，不参与抽牌）。
    # spread 牌阵(默认 three 三张·过去现在未来)，deck 牌系(默认 rws 韦特)，question 所问。seed 显式种子(可选，覆盖时间种子)。
    question: str | None = None
    spread: str | None = "three"
    deck: str | None = "rws"
    seed: str | None = None
    usesReversals: bool | None = True
    # dignities 元素尊位强弱、variant 占象变体（A/B），影响逐牌详解与综合断语。
    dignities: bool | None = None
    variant: str | None = None
    # 定局法：majority(多数) / orientation(正逆) / single(单张) / numeric(数字) / polarity(极性)。
    verdictMode: str | None = "majority"
    # 生命牌：给出生年月日（+可选 refYear 流年）才产出[生命牌]段；不传则该段自然不出。
    birth: dict[str, Any] | None = None


class TechniqueReportInput(FlexibleModel):
    # 技法依据报告：确定性的「这次用了什么技法、什么口径、谁算的」，**不需要 AI 正文**
    # （那是 horosa_report_render 的活，两种文档不混）。
    # run_id 或 group_id 二选一；都不给则取最近一次有技法卡的运行。
    run_id: str | None = None
    group_id: str | None = None
    format: str = "markdown"
    title: str | None = None
    output_path: str | None = None
    # 是否把每个技法的产出段目录写进报告（默认写；关掉可得到极短的一页）。
    include_sections: bool | None = True


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


class ShenShuInput(FlexibleModel):
    # 神数 family (wangji 皇极经世 / wuzhao 五兆 / taixuan 太玄 / jingjue 京房易/靖瞶 / shenyishu 神乙数):
    # ganzhi-based, so only date (+ optional time) + the 晚子时 switches are needed; lat/lon/zone are not used.
    # `options` passes any technique-specific override straight to the engine (e.g. wuzhao mode/number, seed).
    date: str
    time: str | None = "00:00:00"
    after23NewDay: int | None = 1
    lateZiHourUseNextDay: int | None = 1
    options: dict | None = None


class YearSystem129Input(BirthInput):
    # 129年系统 (v2.5.0): seven planets each rule their 小年 (土30木12火15日19金8水20月25 = 129y), computed server-side.
    predictive: bool | None = True


class PersianDirectedInput(BirthInput):
    # 波斯向运 (v2.5.0): symbolic 1°/year direction — every planet/point advances +1°/年, natal cusps fixed.
    predictive: bool | None = False
    # 指定日期向运盘（v0.33.0 批 I-2，/predict/persianchart）：给 datetime 时后端整铸该日向运盘
    # （27 directed 点 + 33 directed lots + 向运→本命相位命中），加产 [指定日期向运盘] 段。
    datetime: str | None = Field(
        default=None,
        description=(
            "目标日期 YYYY-MM-DD[ HH:mm:ss]：铸该日的波斯向运盘（directed 点位 + 向运→本命相位命中），"
            "加产 [指定日期向运盘] 段。缺省只出 1°/年应期表。Cast the directed chart at this date."
        ),
    )
    rateKey: str | None = Field(default=None, description="向运速率键（缺省 persian=1°/年；其余速率键与上游 rateKey 同名直通）")
    direction: str | None = Field(default=None, description="向运方向：direct（缺省）|converse（逆向）")
    nodeRetrograde: bool | None = Field(default=None, description="交点按逆行处理（缺省 false，上游同默认）")


class MundaneInput(FlexibleModel):
    # 世俗入宫盘 (mundane ingress chart): cast at the precise solar-term ingress moment of a given year.
    # date/time are DERIVED from the ingress (jieqi) computation, so the inputs are year + 入宫节气 + place.
    year: int | str
    ingressTerm: str | None = "春分"  # 春分 / 夏至 / 秋分 / 冬至 (the four cardinal ingresses)
    zone: str | None = "+08:00"
    lat: str | None = None
    lon: str | None = None
    gpsLat: float | None = None
    gpsLon: float | None = None
    ad: int | None = 1
    hsys: int | None = 0
    tradition: bool | None = False
    # 盘型分派（上游 MundaneMain 的 TITLE 映射）：当前 headless 支持 ingress（默认）与
    # mundanehorary；后者按 mhKind 出 [世运卜卦]/[世运问判] 两段。
    mundaneType: str | None = Field(default=None, description="盘型：ingress（默认）/ mundanehorary。")
    mhKind: str | None = Field(default=None, description="世运卜卦问类：war 战争（默认）/ weather 天候 / price 物价。")
    solunarType: str | None = Field(default=None, description="恒星派入境盘型：capsolar（默认）/arisolar/cansolar/libsolar/caplunar/arilunar/canlunar/liblunar。")
    solunarWeights: str | None = Field(default=None, description="恒星派权重方案（scheme_a 默认）。")
    solunarOrb: float | None = Field(default=None, description="角化容许度（默认 3°）。")
    vedicYear: int | None = Field(default=None, description="吠陀世运年份（缺省取 year）。")


class OtherBuInput(BirthInput):
    tradition: bool | None = False
    sign: str | None = "Aries"
    house: int | None = 0
    planet: str | None = "Sun"
    question: str | None = None


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
    gua_code: str | None = None
    changed_code: str | None = None
    lines: list[SixYaoLineInput] = Field(default_factory=list)


class FirdariaInput(BirthInput):
    predictive: bool | None = True


class DecennialsInput(BirthInput):
    predictive: bool | None = True
    startMode: str | None = "sect_light"
    orderType: str | None = "zodiacal"
    dayMethod: str | None = "valens"
    calendarType: str | None = "calendar_360"
    aiMode: str | None = "l1_all"
    aiL1Idx: int | None = 0
    aiL2Idx: int | None = 0
    aiL3Idx: int | None = 0


class DispatchSubjectInput(FlexibleModel):
    name: str | None = None
    birth: BirthInput | ZiWeiBirthInput | BaZiBirthInput | LiuRengGodsInput | NongliTimeInput | None = None
    inner: RelativePartyInput | None = None
    outer: RelativePartyInput | None = None
    gua_names: list[str] | None = None
    year: int | str | None = None


class DispatchInput(FlexibleModel):
    query: str
    subject: DispatchSubjectInput | None = None
    birth: BirthInput | ZiWeiBirthInput | BaZiBirthInput | LiuRengGodsInput | NongliTimeInput | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)
    save_result: bool = True


class HecanInput(DispatchInput):
    # 合参（v0.28.0）：一问多技法交叉印证。入参 = dispatch 全形（query + birth/subject + 确认字段），
    # 另加 tools 显式指定技法（缺省由路由选盘）与 max_tools 上限。产出不是终稿而是**合参模板**
    # （ai_fillable：各技法结论槽 + 相互印证/分歧槽），分歧必须披露、不许平均——AI 填完即合参报告。
    tools: list[str] | None = None
    max_tools: int | None = 5


class ExportRegistryInput(FlexibleModel):
    technique: str | None = None


class ExportParseInput(FlexibleModel):
    technique: str
    content: str
    selected_sections: list[str] | None = None
    planet_info: PlanetInfoSettingInput | None = None
    astro_meaning: AstroMeaningSettingInput | None = None


class KnowledgeRegistryInput(FlexibleModel):
    domain: str | None = None


class KnowledgeReadInput(FlexibleModel):
    # query 模式（v0.30.0）：给 `query` 即跨域全文检索，domain 变可选过滤器、category 不用；
    # 不给 `query` 走精读老路（domain 必填，category 手册域可缺省首类）。
    domain: str = ""
    category: str = ""
    key: str | None = None
    query: str | None = None
    limit: int | None = None
    aspect_degree: int | str | None = None
    object_a: str | None = None
    object_b: str | None = None
    jiang_name: str | None = None
    tian_branch: str | None = None
    di_branch: str | None = None


class AgentGuidanceInput(FlexibleModel):
    tool_name: str | None = None
    intent: str | None = None
    include_all: bool = False


class MemoryAnswerInput(FlexibleModel):
    run_id: str
    user_question: str | None = None
    ai_answer: str
    ai_answer_structured: dict[str, Any] | list[Any] | None = None
    answer_meta: dict[str, Any] = Field(default_factory=dict)


class MemoryQueryInput(FlexibleModel):
    run_id: str | None = None
    tool: str | None = None
    entity: str | None = None
    text: str | None = None
    artifact_kind: str | None = None
    after: str | None = None
    before: str | None = None
    limit: int = 20
    # 分页偏移：跳过前 N 条命中（与 limit 搭配翻页）。
    offset: int = 0
    include_payload: bool = True


class MemoryShowInput(FlexibleModel):
    run_id: str
    include_payload: bool = True


class ReportTemplateInput(FlexibleModel):
    run_id: str
    tool_name: str | None = None
    language: str = "zh-CN"


class ReportRenderInput(FlexibleModel):
    run_id: str
    tool_name: str | None = None
    format: str = "pdf"
    language: str = "zh-CN"
    title: str | None = None
    ai_report: dict[str, Any] = Field(default_factory=dict)
    ai_answer_text: str | None = None
    include_raw_json: bool = False
    output_path: str | None = None


class ReportFromToolInput(FlexibleModel):
    tool_name: str
    payload: dict[str, Any]
    format: str = "pdf"
    language: str = "zh-CN"
    title: str | None = None
    question: str | None = None
    ai_report: dict[str, Any] = Field(default_factory=dict)
    ai_answer_text: str | None = None
    include_raw_json: bool = False
    output_path: str | None = None
