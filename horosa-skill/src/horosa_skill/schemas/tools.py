from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from horosa_skill.astro_rulers import HOUSE_SYSTEM_LABELS


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    agent_confirmed_settings: bool | None = None
    defaults_accepted: bool | None = None
    clarification_notes: str | None = None


def _unadvertised() -> Any:
    """已声明（MCP 顶层按名可传、进 pydantic 校验层）但不进 tools/list 广告层的旋钮（长词表 → 预算）。

    键表与取值由 horosa_agent_guidance 的 options_keys 给（agent_guidance.py），广告层只在 `request`
    描述里计数「另 N 个高级旋钮」（surfaces/mcp_schema.py 的 x-horosa-hidden）。
    """
    return Field(default=None, json_schema_extra={"x-horosa-hidden": True})


class PlanetInfoSettingInput(FlexibleModel):
    showHouse: int | bool | None = 1
    showRuler: int | bool | None = 1


class AstroMeaningSettingInput(FlexibleModel):
    enabled: int | bool | None = 0


class BirthInput(FlexibleModel):
    date: str = Field(description="公历日期 YYYY-MM-DD（如 1995-06-03）；公元前配 ad=-1。")
    time: str = Field(description="时间 HH:mm 或 HH:mm:ss（24 小时制，如 05:30）。")
    zone: str = Field(description="时区：+08:00 这类固定偏移，或 IANA 名（如 Asia/Shanghai，按盘面日期自动折算）。")
    # F17（上游 utils/timezone.js:124-151 unifyCnZone）：IANA Asia/Urumqi 且日期 ≥ 1949-10-01 时按北京时间
    # （Asia/Shanghai）折算，载荷留 geoZone/zoneAdvisory 并进 warnings/技法卡。false=保留新疆地理时区（+06:00）；
    # 直接给偏移（如 "+06:00"）也不归并。非 BirthInput 族模型经 request 逃生舱传。
    cnUnifiedZone: bool | None = Field(default=None, description="北京时间统一（false=保留新疆时区）")
    lat: str = Field(description="纬度：31n13（31°13'N）或十进制 31.2167（会自动归一）；南纬用 s。")
    lon: str = Field(description="经度：121e28（121°28'E）或十进制 121.4667（会自动归一）；西经用 w。")
    ad: int | None = Field(default=1, description="纪元：1=公元后（默认），-1=公元前。")
    # 响应视图（所有技法工具通用，FlexibleModel 均接受）：None=完整；"sections"=段标题+正文；
    # "titles"=只留段标题索引。仅精简返回体，完整快照照常存档（memory_show 可取回）。
    response_view: str | None = Field(
        default=None,
        description="响应精简视图：缺省=完整；'sections'=段标题+正文；'titles'=只留段标题索引（完整结果已存档，memory_show 可取回）。",
    )
    # 全表 0–24 由 astro_rulers.HOUSE_SYSTEM_LABELS（上游 AstroConst.HOUSE_SYSTEM_OPTIONS 镜像）生成——校验层描述，
    # 不进 tools/list（广告层 hsys 走 mcp_schema.CORE_DOC + 0–8 enum，预算所限）。
    hsys: int | None = Field(
        default=0,
        description=(
            "宫制索引 0–24（上游 AstroConst.HOUSE_SYSTEM_OPTIONS）："
            + " ".join(f"{k}={v}" for k, v in HOUSE_SYSTEM_LABELS.items())
            + "。缺省 0=整宫 Whole Sign（上游页面缺省 1 Alcabitus）。注意 1 不是 Placidus（Placidus=3）。"
        ),
    )
    # 地点显示名：进 [起盘信息]/配置段与搜索请求（样例载荷一直带它，此前 MCP 扁平面静默丢弃）。
    pos: str | None = None
    # 当事人显示名：随请求透传到后端并进盘头（样例载荷一直带它，此前 MCP 扁平面静默丢弃）。
    name: str | None = None
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
    # ── 古典参数 typed 化（v0.33.0 批 I-6：上游 WP-2~8 30 键补全声明；描述照 classicalParamSpec.js
    # 标签逐条对齐，helper.py 45 键白名单为回显权威。全部 None=不发送=后端默认，零回归。──
    dignityDebilities: Any | None = Field(default=None, description="弱陷计负分（陷 −5 · 落 −4；缺省开）。")
    almutenTripMode: str | None = Field(default=None, description="Almuten 三分计分：all=三主全计（缺省）| sectRulerOnly=仅当值主。")
    planetaryHourMethod: str | None = Field(default=None, description="行星时制式：sunrise=日出起算等长时（缺省）| unequal=昼夜不等时（传统）| equal24=廿四时等分。")
    combustOwnChariotExempt: Any | None = Field(default=None, description="界内三分内免燃烧 own chariot（Porphyry；缺省关）。")
    westLilithType: str | None = Field(default=None, description="黑月莉莉丝：mean=平均远地点（缺省）| true=真实远地点(osculating)。")
    topocentricMoon: Any | None = Field(default=None, description="月亮站心视差修正（影响月亮黄经 ≤1°，福点随动；缺省关）。")
    lotReversal: Any | None = Field(default=None, description="福点按昼夜反转（缺省开；关则恒昼式）。")
    lotsDocReverse: Any | None = Field(default=None, description="婚·子·友·疾四点用文档序公式（缺省关）。")
    hermeticLotsReversal: Any | None = Field(default=None, description="七星点按昼夜反转（批判本校勘；缺省开，关则恒同式）。")
    erosConstruction: str | None = Field(default=None, description="爱欲点构成：paulus=金星·水星系（缺省）| valens=福点·精神系。")
    lotFortuneVariant: str | None = Field(default=None, description="福点公式变体：standard=标准昼夜式（缺省）| moonAboveNight=月在地平上恒夜式。")
    lotFatherCombustAlt: Any | None = Field(default=None, description="父点土星伏时替代式（Dorotheus 系；缺省关）。")
    lotProjection: str | None = Field(default=None, description="希腊点点度计数法：portion=度数投射（缺省）| sign=整星座。")
    orbSystem: str | None = Field(default=None, description="容许度判据体系：perObject=星体轨任一覆盖（缺省）| byAspect=按相位名(合冲刑拱8°/六合4°) | wholeSign=整星座位相 | wholeSignMoiety=整星座内两轨半距和。")
    luminaryOrbBonus: int | None = Field(default=None, description="发光体·四轴轨加成：0（缺省）/10/20/30（%）。")
    orbs: dict[str, Any] | None = Field(default=None, description="逐星容许度覆盖（星体 id → 度；缺省用默认表）。")
    orbScale: float | None = Field(default=None, description="容许度全局倍数（缺省 1.0）。")
    aspectIncludeCusps: Any | None = Field(default=None, description="宫头参与相位（≤3°；缺省关）。")
    aspectIncludeLots: Any | None = Field(default=None, description="希腊点参与相位（点为受体 ≤3°；缺省关）。")
    aspectIncludeMidpoints: Any | None = Field(default=None, description="中点参与相位（日月四轴硬相 ≤1.5°；缺省关）。")
    starOrbMode: str | None = Field(default=None, description="恒星轨档：school=按流派平轨（缺省）| byMagnitude=按星等。")
    stationMarking: str | None = Field(default=None, description="留驻判定（盘面 S·D 标）：off=仅逆行R标（缺省）| exactWindow=距留点≤1日 | distance=距留点黄经≤2′ | absSpeed=日速<1′ | relSpeed=日速<3%均速。")
    solarReturnVariant: str | None = Field(default=None, description="太阳返照法：precise=精确回归（缺省，现代）| hellenistic=希腊式（月定上升）。")
    returnLatitudeMode: str | None = Field(default=None, description="返照落宫投影：ecliptic=黄道度（缺省）| withLatitude=计入黄纬（Umar al-Tabari 法）。")
    houseCuspAdvance: int | None = Field(default=None, description="行星落宫宫头前移：5°（缺省，传统）/3/1/0（整宫制豁免）。")
    vulcanCalc: str | None = Field(default=None, description="祝融星（推算行星）：off（缺省）| weston=轨道根数法 | baker=水星系推算。")
    customTermsDay: Any | None = Field(default=None, description="自定义界表·昼表（termsVariant=4 时生效；非法整表回落埃及界）。")
    customTermsNight: Any | None = Field(default=None, description="自定义界表·夜表（可缺=昼夜同表）。")
    userAyanT0: float | None = Field(default=None, description="自定义恒星黄道参考历元 JD（siderealAyanamsa='user' 配套）。")
    userAyanDeg: float | None = Field(default=None, description="自定义恒星黄道在 T0 历元的岁差度（'user' 配套）。")
    # 快照口径键（send:'never'——不进 /chart，只改导出段；BirthInput 字段不进 tools/list 广告层）：
    # [古典·显赫计分] 主宰光体判定四键（classicalParamSpec.js）+ [信息]/[古典格局] 互容接纳过滤 + [埃及历] 七轴（egypt_*）。
    busyPlaces: str | None = Field(default=None, description="有利宫位集：'1,4,5,7,10,11'（缺省）| '1,4,7,10' | '1,2,4,5,7,9,10,11' | '1,3,4,5,7,9,10,11'。")
    dynamicalDivisions: Any | None = Field(default=None, description="动力学区分（象限强度分区）：0（缺省）/1。")
    domicileMasterMethod: str | None = Field(default=None, description="主宰主星判法：domicile 庙主派（缺省）| bound 界主派。")
    rayWeighting: str | None = Field(default=None, description="七射线权重：off（缺省）| equal | weighted。")
    showOnlyRulExaltReception: Any | None = Field(default=None, description="仅按本垣/擢升计算互容接纳（[信息] 接纳互容行与 [古典格局] 格局速览·先验权力同口径）：0（缺省）/1。")
    # 埃及历七轴取值 = egyptianSchools.EGYPT_SCHOOL_AXES（首项默认档；认不出的值报 tool.egypt_invalid_setting）。
    egypt_decanRuler: str | None = Field(default=None, description="埃及历·旬主星制：chaldean 迦勒底外貌（缺省）| triplicity 三分性旬星。")
    egypt_decanAnchor: str | None = Field(default=None, description="埃及历·旬序锚定：greek 希腊化回归（缺省）| ancient 古代恒星。")
    egypt_decanNaming: str | None = Field(default=None, description="埃及历·旬名录传统：egypt 埃及本名（缺省）| coptic 科普特-希腊名 | hermes 赫尔墨斯名。")
    egypt_starClock: str | None = Field(default=None, description="埃及历·星钟法：diagonal 对角星钟·升起法（缺省）| transit 过中天星钟。")
    egypt_calendarAnchor: str | None = Field(default=None, description="埃及历·历法锚点：ce139 公元 139 年重合点（缺省）| nabonassar 那波那萨尔纪元 | philip 腓力纪元。")
    egypt_petosirisMod: int | None = Field(default=None, description="埃及历·Petosiris 模数：29（缺省）| 30。")
    egypt_godEdition: str | None = Field(default=None, description="埃及历·众神版本：seamless 无缺口自洽版（缺省）| variant 通行变体。")
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


# [寿命格局] 取主法（上游 AstroLifespan.js:14-18；上游是全局设置 horosa.lifespan.method，skill 按调用传）。
_LIFESPAN_METHOD_DESC = "[寿命格局]取主法：ptolemy 托勒密（缺省）| alcabitius | dorotheus"


class AstroChartInput(BirthInput):
    """本命/盘面族（chart/chart13/chart12/hellen_chart）：在 BirthInput 上加 [寿命格局] 取主法。"""

    lifespanMethod: str | None = Field(default=None, description=_LIFESPAN_METHOD_DESC)


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
    # 上游 v3.11.0 挂载齿轮（techniqueMountSettings.js:1030-1039）：
    indiaExtraVargas: Any | None = Field(
        default=None,
        description="附加分盘（简表，最多 4 张）：如 [9, 7] 或 '9,7'。可选 2/3/4/7/9/10/12/16/20/24/27/30/40/45/60；每张只出宫头 + 星曜落宫 + 行星，进 [附加分盘] 段。缺省=只挂主盘。",
    )
    indiaTripataki: bool | None = Field(
        default=None,
        description="Tripataki 三旗盘（opt-in，后端多建 12 盘约 0.3–0.8s）：true 时产 [Tripataki 三旗盘逐月净分] 段（月心/土心逐月净分）。",
    )
    # 上游印度盘页 / 挂载齿轮（techniqueMountSettings.js:1000-1051 → IndiaChart.fieldsToParams :79-143）的其余口径：
    # 照常声明（校验 + MCP 扁平面收顶层键），不进 tools/list 广告层（预算）；值域词表见 agent_guidance。
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset({
        "dashaSystem", "indiaSchool", "dashaSeed", "sthiraStart", "transitDate", "tajakaYear", "annualChartType",
        "varshaLat", "varshaLon", "prashnaTime", "prashnaNumber", "prashnaMatter", "prashnaSchools",
        "prashnaCuspMode", "prashnaPrimaryHouse",
    })
    dashaSystem: str | None = Field(default=None, description="大运体系（15 档，缺省 vimshottari）：决定 [大运Dasha] 段所列体系。")
    indiaSchool: str | None = Field(default=None, description="流派：parashari（缺省）/jaimini/tajika/kp/nadi/western_sidereal；未给岁差/宫制时按派补预设。")
    dashaSeed: str | None = Field(default=None, description="大运起点：moon（缺省）/七政/节点/上升/特殊上升/副星。")
    sthiraStart: str | None = Field(default=None, description="Sthira 座运起座：lagna（缺省）| brahma。")
    transitDate: str | None = Field(default=None, description="过运日期 YYYY/MM/DD（缺省今日）。")
    tajakaYear: int | None = Field(default=None, description="年度盘年份（缺省当前年）。")
    annualChartType: str | None = Field(default=None, description="年盘口径：varsha（缺省）| tithi。")
    varshaLat: Any | None = Field(default=None, description="年盘异地纬度（须与 varshaLon 同给）。")
    varshaLon: Any | None = Field(default=None, description="年盘异地经度（须与 varshaLat 同给）。")
    prashnaTime: str | None = Field(default=None, description="问事起卦时刻 YYYY/MM/DD HH:mm:ss（给了才产 [问事 Praśna]）。")
    prashnaNumber: int | None = Field(default=None, description="KP 问时数 1–249（缺省 1）。")
    prashnaMatter: str | None = Field(default=None, description="所问事项（career/marriage/…）。")
    prashnaSchools: Any | None = Field(default=None, description="问事流派（缺省 ['kp']）。")
    prashnaCuspMode: str | None = Field(default=None, description="问事宫始定法（缺省 asc_driven_placidus）。")
    prashnaPrimaryHouse: int | None = Field(default=None, description="问事主宫 1–12（缺省按事项）。")


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
    # pdchart 界限显示开关（service 读 params.showPdBounds；agent_guidance 一直在文档里写它，schema 此前未声明 → MCP 扁平面丢弃）。
    showPdBounds: int | bool | None = None


class ProfectionInput(PredictiveInput):
    # [Q-105] 小限页 G9 年/月/日小限 + 多起点（上游 utils/profectionSummary.js，挂载齿轮 techniqueMountSettings.js:1359-1362）。
    profGrain: str | None = Field(default=None, description="[小限摘要]粒度：y 年（缺省）| m 月 | d 日")
    profStart: str | None = Field(default=None, description="[小限摘要]起点：asc 上升（缺省）| sect 区分光 | fortune 福点 | moon | mc")


class ZodiacalReleaseInput(PredictiveInput):
    # 上游 AstroZR.js ZR_BASE_POINTS / AI_MODE_ITEMS（挂载齿轮 techniqueMountSettings.js:1277-1285）。
    basePoint: str | None = Field(
        default=None,
        description="推运基点：Pars Fortuna（缺省）/Pars Spirit/Pars Mercury…Pars Saturn/Asc/Desc/MC/IC/十二星座英文名",
    )
    aiMode: str | None = Field(default=None, description="输出层级：l1_all（缺省）| l2_in_l1 | l3_in_l2 | l4_in_l3")
    aiL1Idx: int | None = Field(default=None, description="钻取序号（0 起；aiL2Idx/aiL3Idx 同）")
    aiL2Idx: int | None = None
    aiL3Idx: int | None = None


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
    timeAlg: int | None = 0
    # 本地引擎（上游页面主路径）不实现 byLon / adjustJieqi：给了真值即整盘走 Java /bazi/*（唯一实现它们的引擎）并进 warnings。
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


class ZeriScanInput(BirthInput):
    """择日十技法的共享入参（上游 v3.10.0）。

    `date`/`time`/`zone`/`lat`/`lon` 继承自 BirthInput —— 它们是**候选时刻**的坐标，不是出生盘；
    真正的搜索范围由 startDate/startTime/endDate/endTime 给。命中后展示盘按基底技法自己的算源铸，
    只有区间搜索在本地/后端扫描引擎里跑（各工具的 `compute_sources` 如实标出这一分工）。

    条件树按 passthrough 建模而非在此重编：上游十技法合计三百余个条件类，各自 params 形状/validate/
    compile 都不同，在这里重写一遍等于造第二份真值源，上游一加条件类就烂。vendored 的
    `compile<X>Tree` 会跑各叶子自己的 validate 抛本地化错误；条件类键与参数走 agent_guidance 暴露。
    """

    startDate: str | None = Field(default=None, description="搜索窗起始日（YYYY-MM-DD）")
    startTime: str | None = Field(default="00:00", description="搜索窗起始时刻（HH:mm）")
    endDate: str | None = Field(default=None, description="搜索窗结束日（YYYY-MM-DD）")
    endTime: str | None = Field(default="23:59", description="搜索窗结束时刻（HH:mm）")
    pos: str | None = Field(default=None, description="地点显示名，进配置段与搜索请求")
    conditions: Any | None = Field(
        default=None,
        description=(
            "条件树。组节点 {kind:'group', joiner:'all'|'any'|'xor', negate?, children:[…]}；"
            "叶节点 {kind:'leaf', type:'<条件类键>', negate?, params:{…}}。"
            "条件类键与参数见本工具的 agent_guidance。"
        ),
    )
    options: dict[str, Any] | None = Field(
        default=None, description="起局/判读口径覆写；与顶层同名字段双读合并，options 优先。"
    )
    natal: dict[str, Any] | None = Field(
        default=None, description="本命盘上下文（部分条件类按本命比对时需要，如八字/紫微/六壬的本命组）。"
    )
    maxHits: int | None = Field(default=None, description="命中上限（缺省用引擎自带上限）。")
    maxSpanDays: int | None = Field(
        default=None,
        description="搜索窗天数上限，只能**调低**：给的值超过本工具的硬上限时按硬上限执行，不会放宽。",
    )
    # [Q-452/Q-453] 快照「命中清单」两旋钮（上游 zeriSnapshotPrefs：60 行·10–500；判读树 3 行·0–20）。
    zeriSnapshotMaxRows: int | None = Field(default=None, description="清单行数10-500(缺省60)")
    zeriSnapshotExplainRows: int | None = Field(default=None, description="判读树行数0-20(缺省3)")


class HuangliZeriInput(ZeriScanInput):
    """黄历择吉：**日粒度**扫描（不吃起局开关），命中段是整日。"""


class BaziZeriInput(ZeriScanInput):
    """八字择时：时辰粒度。起局三开关 + godKeyPos/phaseType 与 bazi_birth 同词表。"""

    timeAlg: int | None = None
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None
    godKeyPos: str | None = None
    phaseType: int | None = None


class TaiyiZeriInput(ZeriScanInput):
    """太乙择时：时辰粒度。太乙时基是**钟表时**（上游口径，与后端 kentang 太乙一致）。"""

    # 引擎按对象展开（taiyiZeriScanEngine：applyTaiyiSchool(pan, o.school || {})）——此前声明成 str，任何字符串都被静默
    # 忽略、对象又过不了校验。展示盘（taiyi runner）读同一顶层 school，扫描与所见同一套流派。
    school: dict[str, Any] | None = Field(default=None, description="流派六轴对象，同 taiyi options.school。")


class ZiweiZeriInput(ZeriScanInput):
    """紫微择时：时辰粒度。"""

    timeAlg: int | None = None
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None
    # 扫描按 options.gender 起盘（上游工作台常驻键，出厂 1）；顶层写法与 options 双读合并，展示盘同跟。
    gender: int | str | None = None


class LiurengZeriInput(ZeriScanInput):
    """六壬择时：时辰粒度。"""

    guirengType: int | None = Field(default=None, description="贵人取法，与 liureng_gods 同词表。")
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None


class SanshiZeriInput(ZeriScanInput):
    """三式合一择时：时辰粒度，条件可跨六壬/奇门/太乙三盘（70 个条件类，最多的一支）。"""

    timeAlg: int | None = None
    after23NewDay: int | None = None
    lateZiHourUseNextDay: int | None = None
    guirengType: int | None = None


class ZeriBackendScanInput(ZeriScanInput):
    """后端扫描成员共享：多一个单时刻逐叶判读入口（与 tianxing 的 explainAt 同款）。"""

    explainAt: str | None = Field(
        default=None,
        description="对该时刻做逐叶判读（YYYY-MM-DD HH:mm[:ss]）；与扫描求值器同源。不给则不产该段。",
    )


class QizhengZeriInput(ZeriBackendScanInput):
    """七政择时：判定与区间搜索都在 astropy 后端（swisseph 直连分钟粒度），非本地重算。"""

    height: float | None = Field(default=None, description="海拔（米），缺省 0")
    # 扫描上下文实读三键（QizhengScanContext；上游页出厂 2/mean/mean）。ayanamsaDeg 已删：两个扫描都不读它
    # （它只属七政择日动盘 qizhengelection），声明着等于广告一个死开关。
    su28Mode: int | None = Field(default=None, description="宿度制：2=回归今宿（缺省）3=开禧宿度")
    nodeType: str | None = Field(default=None, description="罗计：mean（缺省）|true")
    lilithType: str | None = Field(default=None, description="月孛：mean（缺省）|true")


class IndiaZeriInput(ZeriBackendScanInput):
    """印度择时（Muhurta）：后端扫描。段自足 —— 印度盘全文见 india_chart 本身，本工具只出择时三段。"""

    # 扫描上下文读 ayanamsa（IndiaScanContext）；indiaAyanamsa 是与 india_chart 同词表的别名（显式 ayanamsa 优先）。
    # indiaHsys 已删：Muhurta 扫描不读分宫制、本工具也不铸印度盘，声明着等于广告一个死开关。
    indiaAyanamsa: Any | None = Field(default=None, description="扫描岁差制（缺省 lahiri），与 india_chart 同词表")
    nodeType: str | None = Field(default=None, description="罗睺计都：mean（缺省）|true")


class QimenZeriInput(QimenInput):
    """奇门择日「找局」：在时间窗内扫出满足条件树的时辰。

    盘面参数与 QimenInput 逐字相同（同一套 22 项 options / 晚子时 / 时家算法），只多出搜索窗与条件树 ——
    展示盘仍走 ken `/qimen/pan`，只有区间**搜索**用本地引擎（见 service._run_qimenzeri_tool 的算权说明）。
    """

    # service 会把 pos 读进搜索请求（_run_qimenzeri_tool 的 geo），但此前 schema 不声明 ——
    # FlexibleModel 收得下，agent 却无从得知它存在。声明即可发现。
    pos: str | None = Field(default=None, description="地点显示名，进配置段与搜索请求")
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
    maxSpanDays: int | None = Field(
        default=None,
        description="搜索窗跨度上限（天），缺省即本工具硬上限；只能**调低**，给更大的值不会放宽。",
    )
    maxHits: int | None = Field(default=None, description="命中区间数上限，缺省 1000")
    zeriSnapshotMaxRows: int | None = Field(default=None, description="清单行数10-500(缺省60)")
    zeriSnapshotExplainRows: int | None = Field(default=None, description="判读树行数0-20(缺省3)")


class TianxingInput(BirthInput):
    """天星择日·征象搜索：在时间窗内扫出满足西占征象条件的时段。

    lat/lon/zone/hsys/zodiacal 复用 BirthInput —— 它们就是**搜索盘**的坐标与口径，不另起一套词汇。
    date/time 是 [起盘信息] 展示的锚点时刻，缺省取窗口起点。
    """

    # 后端 ScanContext 实读 partileDef（election_scan.py:367），白名单也一直带着它，
    # 唯独 schema 没声明 —— 能用、agent 看不见。
    partileDef: str | None = Field(default=None, description="精确相位(partile)判定：same_degree（缺省）等。")
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
    zeriSnapshotMaxRows: int | None = Field(default=None, description="清单行数10-500(缺省60)")
    zeriSnapshotExplainRows: int | None = Field(default=None, description="判读树行数0-20(缺省3)")


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
    pos: str | None = Field(default=None, description="地点显示名，进快照的起盘信息行")
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
    # dayunRule: 'mingGongQiyun'(默认·《参评诀》单双月数日÷3) / 'mingGongOne'(一岁起运) /
    # 'baziStyle'(节气起运，与八字盘同源)。镜像上游 aiAnalysisContext.js:1903 的每技法设置；
    # 上游 [Win-D69] 记的正是「页面选了档、挂载不传 → 挂载恒回落默认档+一岁起」这个 bug。
    dayunRule: str | None = None


class GuoLaoInput(BirthInput):
    # 七政起盘口径长尾键：照常声明（校验 + MCP 扁平面收顶层），不进 tools/list 广告层（词表见 agent_guidance）。
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset({
        "guolaoNodeMode", "guolaoTrueSolarTime", "guolaoNodeType", "guolaoLilithType",
        "guolaoAyanamsa", "guolaoTuibianMethod", "guolaoGufaPrecess", "guolaoEqTropicalAnchor",
    })
    # 宿度制（上游 GuoLaoChartStyle.js:10 缺省 2 回归今宿；值域 guolaoData.SU28_MODE_LABEL 0–8）。BirthInput 那个是 bool
    # （宿占用），这里放宽成 int —— 2–8 此前被 pydantic 拒；旧 true/false 照后端 parseSu28Mode 解释为 1/0。
    doubingSu28: int | bool | None = Field(default=None, description="宿度制 0–8（缺省 2 回归今宿；4 恒星制；全表见 guidance）。")
    # 七政四余（v0.36.0 C1）：Java /qizheng/moira 规则层入参 + 流年盘时刻。缺省与上游 UI 默认一致。
    guolaoLifeMode: str | None = Field(default=None, description="命度法：asc 上升（缺省）| yumao 日出 | gumao 遇卯 | cotrans 赤黄 | 子–亥自定。")
    guolaoBodyMode: str | None = Field(default=None, description="身宫法：taiyin（太阴落宫，默认）| youjin（逢酉·琴堂）| 指定地支。")
    moiraTransitDate: str | None = Field(default=None, description="流年盘日期 YYYY-MM-DD（[流年流曜] 段的流年时刻；缺省=今天）。")
    moiraTransitTime: str | None = Field(default=None, description="流年盘时间 HH:mm:ss（缺省 12:00:00）。")
    moiraRules: bool | None = Field(default=None, description="false=跳过 /qizheng/moira（不产 [虚实]/[本命化曜]/[流年流曜]，省一次流年铸盘）。")
    # 显示层口径（上游 v3.11.0 挂载齿轮 techniqueMountSettings.js:1159-1175；缺省 = 上游全局缺省
    # GuoLaoChartStyle.GUOLAO_DEFAULT_DISPLAY：gong / 古度限度法 / tong10 / 9）。四键逐字打印进快照并改段结构。
    guolaoLifeMasterMode: str | None = Field(default=None, description="命主取法：gong=宫主（缺省）| du=度主 | dudegrade=贬宫主专度主（果老）。改 [三主与化曜] 的命主与难仇恩用「度」行。")
    guolaoMinorLimitType: str | None = Field(default=None, description="行运法：''=古度限度法（缺省）| minor=小限 | month=月限 | tong=童限 | dongwei=洞微大限。改 [大限] 所附行运法结构与 [限法实算] 的实算行。")
    guolaoTongxianBase: str | None = Field(default=None, description="童限基数（行运法=tong 时生效）：tong10=通行十年（缺省）| gu9=古九岁 | xu11=虚十一。")
    guolaoLimitChildBase: int | None = Field(default=None, description="定童限：9=九年起（缺省）| 10=十年起。改 [大限] 首限年数与各限起讫岁、[限法实算] 的童限/限度。")
    # 起盘口径（上游页面左栏 / 挂载齿轮 techniqueMountSettings.js:1123-1181；缺省 = GuoLaoChartStyle.js getStored* 缺省）。
    guolaoNodeMode: str | None = Field(default=None, description="罗计命名：northKetuSouthRahu 北计南罗（缺省）| northRahuSouthKetu 北罗南计（整盘换位）。")
    guolaoTrueSolarTime: str | None = Field(default=None, description="报时星太阳时：true 真太阳时（缺省）| mean 平太阳时 | off 钟表时。")
    guolaoNodeType: str | None = Field(default=None, description="罗计取法：mean 平交点（缺省）| true 真交点。")
    guolaoLilithType: str | None = Field(default=None, description="月孛取法：mean 平远地点（缺省）| true 真远地点。")
    guolaoAyanamsa: str | None = Field(default=None, description="恒星制岁差（仅宿度制 4）：47 制键，缺省郑氏。")
    guolaoTuibianMethod: str | None = Field(default=None, description="推变黄道术（仅宿度制 6）：jiyuan 纪元（缺省）| jintui 进退 | huiyuan 会圆。")
    guolaoGufaPrecess: int | bool | None = Field(default=None, description="古宿随岁差（仅宿度制 6）：0 钉死元时（缺省）| 1 东移。")
    guolaoEqTropicalAnchor: str | None = Field(default=None, description="赤道回归锚点（仅宿度制 7/8）：dongzhi 牛前冬至（缺省）| chunfen 春分。")


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
    timeAlg: int | None = 1
    # 日界/晚子时：None → JS 侧按上游 YiZhangJingMain 缺席回退全局出厂默认 1/1（23 点算次日）。
    after23NewDay: int | None = Field(default=None, description="日界 1=23点换日(缺省)")
    lateZiHourUseNextDay: int | None = Field(default=None, description="晚子时干 1=次日(缺省)")
    # 排盘选项 = 上游 KinAstroMain.buildYizhangjingOpts 同键，缺省 = KINASTRO_PAGE_SETTINGS 出厂档
    # （「秘传口诀」预设，KinAstroMain.js:1039-1056）：定月法 lunar 农历月 / jieqi 节气月；顺逆 yangNanYinNv /
    # menShunNvNi；命宫 shiShang / shuZhiMao；大限一宫 7 或 10 年；大限起法 mi / age1；小限起宫 ri / yue；
    # 小限顺逆 chart 随盘 / always 一律顺行；逐年法 xiaoxian 小限（出厂）/ liunian 流年十二神；流年十二神组
    # A/B/C；早子时；重犯口诀组 alpha / beta；星名系统 A/B/C；六道术语 gui / edao；童限显示；
    # 神煞合参层（出厂关，开则多出 [神煞合参] 段）。
    dingYue: str | None = "lunar"
    shunniRule: str | None = "yangNanYinNv"
    mingGongMethod: str | None = "shiShang"
    dayunLength: int | None = 7
    dayunStartAge: str | None = "mi"
    xiaoxianStart: str | None = "ri"
    xiaoxianDir: str | None = Field(default="chart", description="小限 chart随盘/always顺行")
    annualMethod: str | None = Field(default="xiaoxian", description="逐年法 xiaoxian/liunian")
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
    pointHsys: str | None = Field(default=None, description="落点/宫尖线宫制（缺省 placidus）")
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
    # 上游 AstroAcg.genParams（AstroAcg.js:348-372）的其余引擎口径 + CCG + 关系盘 + 快照图层：照常声明（校验 + MCP
    # 扁平面收顶层键），不进 tools/list 广告层（预算）；值域见 agent_guidance，后端认不出的值经 meta 回显比对后告警。
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset({
        "geodeticZero", "cuspLines", "coord", "posType", "horizon", "nodeType", "lilithType", "draconic", "harmonic",
        "vibration", "midpointMode", "lotsCustom", "asteroids", "ayanamsa", "stars", "ccgDate", "ccgTime", "ccgMix",
        "relMode", "relDate", "relTime", "relZone", "relLat", "relLon", "paranMode", "showLS", "showGeodetic",
        "showStarParans",
    })
    geodeticZero: float | None = Field(default=None, description="地理等价 0°♈ 子午线（东经度；缺省流派默认）。")
    cuspLines: bool | None = Field(default=None, description="十二宫尖线（opt-in，按 pointHsys 宫制）。")
    coord: str | None = Field(default=None, description="坐标系：geo（缺省）| helio | topo。")
    posType: str | None = Field(default=None, description="位置类型：apparent（缺省）| true | j2000。")
    horizon: str | None = Field(default=None, description="地平：geometric（缺省）| apparent（折射）。")
    nodeType: str | None = Field(default=None, description="交点：mean（缺省）| true。")
    lilithType: str | None = Field(default=None, description="Lilith：mean（缺省）| true | intp | body。")
    draconic: str | None = Field(default=None, description="龙黄道：off（缺省）| mean | true。")
    harmonic: int | None = Field(default=None, description="谐波 H（1=关，缺省）。")
    vibration: bool | None = Field(default=None, description="Cochrane 5/7/9 振动线。")
    midpointMode: str | None = Field(default=None, description="中点线：zodiac（缺省）| mundo。")
    lotsCustom: str | None = Field(default=None, description="自定义阿拉伯点 'A,B,C[,sect]'。")
    asteroids: bool | None = Field(default=None, description="含小行星（Ceres/Pallas/Juno/Vesta/Eris）。")
    ayanamsa: str | None = Field(default=None, description="恒星黄道读数（47 制键；缺省回归）。")
    stars: bool | None = Field(default=None, description="固定星线（opt-in）。")
    ccgDate: str | None = Field(default=None, description="CCG 时间地图日期 YYYY-MM-DD（给了才画）。")
    ccgTime: str | None = Field(default=None, description="CCG 时刻（缺省 12:00:00）。")
    ccgMix: str | None = Field(default=None, description="CCG 口径：mixed（缺省）| transit | progressed。")
    relMode: str | None = Field(default=None, description="关系盘：davison | composite | synastry（须配 relDate）。")
    relDate: str | None = Field(default=None, description="B 盘出生日期 YYYY-MM-DD。")
    relTime: str | None = Field(default=None, description="B 盘出生时间（缺省 12:00:00）。")
    relZone: str | None = Field(default=None, description="B 盘时区（缺省随 A 盘）。")
    relLat: str | None = Field(default=None, description="B 盘纬度（缺省同 A 地）。")
    relLon: str | None = Field(default=None, description="B 盘经度（缺省同 A 地）。")
    paranMode: str | None = Field(default=None, description="快照交映子块：off（缺省）| lum | all。")
    showLS: bool | None = Field(default=None, description="快照含本地空间线子块。")
    showGeodetic: bool | None = Field(default=None, description="快照含地理等价线子块。")
    showStarParans: bool | None = Field(default=None, description="快照含固定星交映（须 stars）。")


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
    id: str | None = Field(default=None, description="详情键：事件 id（XTS-027）/ 编辑层 slug（fig-laozi）。")
    tradition: str | None = Field(default=None, description="传统过滤：正史 / 野载。")
    dynasty: str | None = Field(default=None, description="朝代过滤（如 唐 / 南北朝 / 志怪笔记）。")
    technique: str | None = Field(default=None, description="术数门类过滤（如 占星 / 相术 / 卜筮）。")
    history: str | None = Field(default=None, description="史书过滤（如 新唐书 / 晋书）。")
    evidence: str | None = Field(default=None, description="证据等级过滤。")
    omen: str | None = Field(default=None, description="天象类（日食/彗孛/流星…）：celestial/term_profile/microchronology。")
    source: str | None = Field(default=None, description="天象出处过滤（celestial 用）。")
    year_from: int | None = Field(default=None, description="天象起始公历年（可负=公元前）。")
    year_to: int | None = Field(default=None, description="天象结束公历年。")
    macro: str | None = Field(default=None, description="timeline 宏观段下钻键。")
    period: str | None = Field(default=None, description="map 的时期过滤。")
    date_key: str | None = Field(default=None, description="daily 的日期键（YYYY-MM-DD，缺省今日）。")
    page: int | None = Field(default=None, description="列表页码（1 起）。")
    page_size: int | None = Field(default=None, description="每页条数（默认 30）。")
    limit: int | None = Field(default=None, description="条数上限。")
    decade: int | None = Field(default=None, description="microchronology 十年期。")
    has_crosswalk: bool | None = Field(default=None, description="celestial：有无交叉对照。")
    in_chapter: bool | None = Field(default=None, description="celestial：in_chapter。")
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


class GermanyInput(BirthInput):
    predictive: bool | None = False
    # 汉堡中点盘口径（上游挂载齿轮 techniqueMountSettings.js:1213-1238 → AstroMidpoint.js:301-307 下发 /germany/midpoint；
    # 后端 webgermanysrv.midpoint 读这些键）。此前未声明：CLI 经 extra 透传得到，MCP 扁平面却静默丢弃、流派写错也不报。
    # 照常声明（校验 + MCP 扁平面收顶层键），不进 tools/list 广告层（预算）；说明见 agent_guidance options_keys。
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset(
        {"school", "orb", "personalOrb", "strictFactors", "frames", "declination", "davison"}
    )
    school: Literal["classic", "pure", "uranian", "cosmo"] | None = Field(
        default=None, description="汉堡流派：classic 原始汉堡（缺省）| pure 纯净派 | uranian 美国对称 | cosmo 宇宙生物学（不用虚星，缺省容许度 1.5°）。"
    )
    orb: float | None = Field(default=None, gt=0, le=10, description="中点容许度（°；缺省 1，cosmo 缺省 1.5）。")
    personalOrb: float | None = Field(default=None, gt=0, le=10, description="个人点（Basic Five）容许度（°）；缺省不分叉。")
    strictFactors: bool | None = Field(default=None, description="严格汉堡因子集：true 剔黑月/紫气（缺省 false）。")
    frames: bool | None = Field(default=None, description="六宫框（[六宫框落宫] 段）：缺省 true。")
    declination: bool | None = Field(default=None, description="赤纬平行/反平行接触：缺省 true。")
    davison: dict[str, Any] | None = Field(default=None, description="戴维森盘第二人 {date,time,zone,lat,lon[,ad]}：产 [戴维森盘] 段。")
    # 上游 v3.11 [Q-442/T-405]「校时」页签（只读预览）：待校事件 → 太阳弧（Naibod）推进 MC/Asc 看是否触动本命因子。
    rectifyEvents: list[dict[str, Any]] | None = Field(
        default=None,
        description="校时预览事件（可选）：[{date:'YYYY-MM-DD', type:marriage|children|career|move|loss|accident|other, label}]；给了才产 [校时预览]（推进 MC/Asc 看是否触动本命因子，只预览不改盘）。",
    )


class HarmonicInput(BirthInput):
    # 调波盘 (harmonic chart) is a backend chart-extra computation (POST /astroextra/harmonic on the
    # Python chart service). harmonic = the H-number (1–360, 星阙 default 9); orb = conjunction orb.
    predictive: bool | None = False
    lifespanMethod: str | None = Field(default=None, description=_LIFESPAN_METHOD_DESC)
    harmonic: int | None = 9
    orb: float | None = 2.0


class BabylonInput(BirthInput):
    # 巴比伦占星（美索不达米亚天象体系）：恒星黄道 · 毕宿锚（Aldebaran = 金牛 15°）。
    # 本体系无十二宫位、无相位、无上升点——盘面是数据清单，解读装置是「位」(三分+日段) 与行星神性。
    # 派系口径直接改分至规范与「位」的落点 → 结果敏感，缺省不静默切换。
    predictive: bool | None = False
    scheme: str | None = Field(default=None, description="实位派系：swissA10（默认）/ systemA / systemB。")
    solstice: str | None = Field(default=None, description="分至规范：A10（春分白羊 10°）/ B8（春分白羊 8°）；缺省跟派系档。")
    # 真正的判读参数（此前一个都没接）：
    dodecaVariant: str | None = Field(default=None, description="十二分变体：A（加于宫起点）/ B（加于点本身·楔文）；缺省跟派系档。")
    cubitDeg: float | None = Field(default=None, description="肘度（1 cubit 折合黄经度数），缺省跟派系档（2.2）。")
    # v3.11：era 进 [起盘信息] 纪元行（babylonAiSnapshot.js:219-221）；ephemerisSource 选 [数理星历] 木星阶梯/锯齿函数（:120）。
    # 不进 tools/list 广告层（预算），词表见 agent_guidance。
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset({"era", "ephemerisSource"})
    era: str | None = Field(default=None, description="纪元显示：seleucid 塞琉古 S.E.（缺省）| arsacid 安息（= S.E.−64）。")
    ephemerisSource: str | None = Field(default=None, description="数理星历位置源：swiss（缺省）| systemA 阶梯 | systemB 锯齿（木星）；缺省跟派系档。")


class DraconicInput(BirthInput):
    # 龙盘 (draconic chart)：把命盘各点黄经减去北交点黄经（POST /astroextra/draconic）。
    # 后端返回 {nodeLon, positions, conjunctions, chart}，chart 与 /chart 同形。
    predictive: bool | None = False
    lifespanMethod: str | None = Field(default=None, description=_LIFESPAN_METHOD_DESC)
    orb: float | None = 2.0


class RelocationInput(BirthInput):
    # 重置盘 (relocation)：保留出生 UT，仅用新经纬重算十二宫与上升/中天（POST /astroextra/relocation）。
    # 行星黄经由 UT 决定故不变，宫位/角点随地点变 —— 迁居占星的标准做法。
    # relocLat/relocLon 缺省回退到出生地，等于本命盘（结果敏感：不给新地点就不是「重置」）。
    predictive: bool | None = False
    lifespanMethod: str | None = Field(default=None, description=_LIFESPAN_METHOD_DESC)
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


_TARGET_DATE_DESC = "目标日期 YYYY-MM-DD（缺省=今天，上游同律）"
_MINOR_VARIANT_DESC = "小推运月长：synodic 朔望月/年（缺省）| sidereal 恒星月/年 | engine 引擎历史值"


class JaynesProgInput(BirthInput):
    # Jayne 赤纬推运 (v2.5.0): secondary progression to a target date, then declination parallels.
    predictive: bool | None = True
    targetDate: str | None = Field(default=None, description=_TARGET_DATE_DESC)
    targetTime: str | None = "12:00:00"
    orb: float | None = 1.0
    minorVariant: str | None = Field(default=None, description=_MINOR_VARIANT_DESC)


class VedicProgInput(BirthInput):
    # 恒星推运 Vedic (v2.5.0): progressions under the sidereal zodiac.
    predictive: bool | None = True
    targetDate: str | None = Field(default=None, description=_TARGET_DATE_DESC)
    targetTime: str | None = "12:00:00"
    orb: float | None = 1.5
    minorVariant: str | None = Field(default=None, description=_MINOR_VARIANT_DESC)


# ── 上游 v3.11 星运四键（[Q-106/T-10] 星历/回归轴/产前朔望 + [#80] 回归黄道二次推运）──
# date/time/zone/lat/lon 恒是**本命盘**；上游请求体（AstroExtraCommon.chartParams）tradition/predictive 恒 false。
class EphemerisInput(BirthInput):
    predictive: bool | None = False
    startDate: str | None = Field(default=None, description="区间起 YYYY-MM-DD（缺省今天）")
    endDate: str | None = Field(default=None, description="区间止（缺省今天+90天）")
    includeTransits: bool | None = Field(default=None, description="列行运触发（缺省 true）")
    eclipseTimeMode: str | None = Field(default=None, description="食相时刻 max（缺省）|syzygy")


class ReturnTimelineInput(BirthInput):
    predictive: bool | None = False
    startYear: int | None = Field(default=None, description="起始年（缺省今年）")
    count: int | None = Field(default=None, description="年数 1–40（缺省 12）")


class PrenatalSyzygyInput(BirthInput):
    predictive: bool | None = False


class ProgInput(BirthInput):
    predictive: bool | None = False
    targetDate: str | None = Field(default=None, description="目标日 YYYY-MM-DD（缺省今天）")
    targetTime: str | None = Field(default=None, description="目标时刻（缺省 12:00:00）")
    minorVariant: str | None = Field(default=None, description="小推运月长 synodic|sidereal|engine")


class PlanetaryArcInput(BirthInput):
    # 行星弧 (v2.5.0): directs the whole chart by the secondary-progressed arc of arcSource (default Moon).
    predictive: bool | None = True
    datetime: str | None = Field(default=None, description="目标时刻（缺省=明天此刻，上游同律）")
    asporb: float | None = 1.0
    arcSource: str | None = Field(default="Moon", description="弧源：Moon（缺省）/Sun/Mercury/Venus/Mars/Jupiter/Saturn")


class PlanetaryAgesInput(BirthInput):
    # 行星年龄 (v2.5.0): Ptolemy seven ages — reads the natal chart, marks the band of asOf (default: none).
    predictive: bool | None = False
    asOf: str | None = None


class BalbillusInput(BirthInput):
    # Balbillus 129年系统 (v2.5.0): 旺距削减主限 — reads the natal chart, splits life into recursive sub-periods.
    # 可调项 = 上游挂载齿轮（techniqueMountSettings.js:1260-1266）→ vendored builder opts。
    predictive: bool | None = False
    startPlanet: str | None = Field(default=None, description="起始星：Sun（缺省）/Moon/Mercury/Venus/Mars/Jupiter/Saturn")
    yearType: str | None = Field(default=None, description="年制：solar 回归年（缺省）| hellenistic 360 日")
    mode: str | None = Field(default=None, description="距离口径：nearest 最近角距（缺省）| forward 顺黄道距")


class TriplicityRulersInput(BirthInput):
    # 三分主星推运 (星阙 v2.6.x): 区间光体所在座的三颗三分主星按昼夜换序，划分人生各阶段。纯前端切分本命盘。
    # 可调项 = 上游挂载齿轮（techniqueMountSettings.js:1237-1248）。
    predictive: bool | None = False
    system: str | None = Field(default=None, description="三分体系：Dorothean（缺省随本盘 triplicity）| Ptolemaic | PtolemaicWaterVariant")
    division: str | None = Field(default=None, description="划分法：thirds 三分（缺省）| halves 两分")
    lifespan: float | None = Field(default=None, description="寿命基准/年龄上限 30–120（缺省 75）")


class KeypointsInput(BirthInput):
    # 数字相位推运 (星阙 v2.6.x): 七星小年数 + 自释放点起第 k 座挂钩，凡年龄为 k 或小年倍数即激活。纯前端切分本命盘。
    predictive: bool | None = False
    mode: str | None = Field(default=None, description="释放点：soul 身·月亮起（缺省）| body 命·上升起")


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
    # 长尾旋钮：照常声明（校验 + MCP 扁平面收顶层键），不进 tools/list 广告层（mcp_schema.advertise_hidden_fields）。
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset(
        {"sincerityConfirmed", "confirmYouthMatch", "isEventChart", "questionText", "castingCamp"}
    )
    # 卜卦 (horary): the chart is cast at the QUESTION moment (date/time/place = when the question was asked).
    # category picks the quesited house — 引擎词表 CATEGORY_DEF 20 类（general/wealth/family/property/father/mother/
    # pregnancy/health/marriage/lawsuit/theft/death/travel/career/hope/enemy/message/lost/lost_animal/trade；
    # unknown → general）。全表与中文名见 agent_guidance。
    category: str | None = "general"
    # 流派档（horarySchools.js HORARY_SCHOOLS 七档）：classical(默认)/renaissance/strict/sequence/hellenistic/medieval/modern。
    # 流派同时决定**起盘字段**（上游 horaryBackendFields：宫制/界系/三分集/福点反转/星群，页面 HoraryMain.js:543）与判读口径。
    school: str | None = Field(default=None, description="卜卦流派七档（缺省 classical；定宫制界系与判读，见 guidance）。")
    # 星群随流派（modern=0 含三王星，其余 1）；显式给值压过流派。
    tradition: bool | None = None
    predictive: bool | None = False
    # 卜卦七档参数谱（星阙 v3.6.0，界表勘误 + 判读叠层二期）。上游 horarySchools.js 的 HORARY_PARAM_SPEC
    # 中 hsys/termsVariant/geminiBoundEmended/tradition 标 sendToBackend：缺省随流派档，显式给值压过流派
    # （与上游高级面板 horaryOverrides 同语义，同时进起盘与判读）。
    hsys: Any | None = Field(default=None, description="宫制：缺省随流派（经典=2 Regiomontanus/希腊化=0/中世纪=1/现代=3）；显式值优先。")
    termsVariant: Any | None = Field(default=None, description="界系 0–3（缺省随流派，见 guidance）。")
    geminiBoundEmended: Any | None = Field(default=None, description="双子界表勘误开关（v3.6.0 修订）。")
    considerationsMode: Any | None = Field(
        default=None, description="定盘考量(considerations before judgment)硬度：warn / strict / lenient / ignore。"
    )
    lotsSet: Any | None = Field(default=None, description="阿拉伯点集：minimal（默认）/ core15。")
    # 定盘自评（上游卜卦左栏三勾选，HoraryMain.js:487-497 → runHorary opts）：影响 [定盘考量] 第 18 条（无诚意）与
    # 命度早晚 / 事件盘两条的「已救济」判定。问句与阵营进 [定盘考量] 段首两行（buildHorarySnapshot 第 3 参）。
    sincerityConfirmed: bool | None = Field(default=None, description="问题真诚自评：缺省 true（上游缺省勾选）；false→定盘考量第18条命中。")
    confirmYouthMatch: bool | None = Field(default=None, description="年轻体貌合上升（救济命度过早）：缺省 false。")
    isEventChart: bool | None = Field(default=None, description="事件盘（客观时刻，救济命度过晚）：缺省 false。")
    questionText: str | None = Field(default=None, description="所问之事原文（进 [定盘考量] 段）。")
    castingCamp: str | None = Field(default=None, description="起盘阵营：astrologer（缺省）/querent/midpoint；时地须已按阵营给。")
    # 判读层参数覆写（HORARY_PARAM_SPEC 全部键，压过流派档；sendToBackend 四键 + tripSystem 同时改起盘）。
    # 键名以引擎自带词表为准；不认识的键会原样回执在 data.params_ignored，不静默吞。
    # 顶层全局古典键（cazimiOrb/combustOrb/underBeamsOrb/vocMode/vocIncludeOuter/viaCombustaVariant/partileDef/
    # antisciaOrb/starOrb/starOrbMode/combustMitigateSameSign/antiscia）进判读**全局层**（流派绑定之下，上游
    # judgeLayerOverrides 同口径）；顶层 triplicity/lotReversal 不作用于卜卦盘（流派绑定，另有告警）。
    # 🔴 receptionMode / almutenScheme 两个字段已删：引擎词表里**根本没有这两个名字**（近邻是
    # receptionForHardAspects / receptionPerfection / accidentalMode，语义并不等同）。
    # 它们是凭空发明的旋钮，声称了三个版本、一次都没生效过。
    options: dict[str, Any] | None = Field(
        default=None, description="判读层参数覆写 {key: value}；键取自引擎词表 HORARY_PARAM_SPEC。"
    )


class ElectionInput(BirthInput):
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset(
        {"tradeSide", "talismanStar", "surgeryPart", "surgeryPartOpposite", "crisisBase"}
    )
    # 择日 (electional): the chart is cast at a CANDIDATE moment (date/time/place = the time being evaluated).
    # topicId picks the rule pack + hard flags: marriage/business/move_in/buy_property/trade/buy_car/contract/
    # surgery/travel/job_hunt/... (TOPIC_MASTER 37 类；unknown → marriage；全表见 agent_guidance).
    topicId: str | None = "marriage"
    tradition: bool | None = True
    predictive: bool | None = False
    # 宫制：缺省随流派档联动（westernSchools.js hsys：hellenistic/modern_revival=0、persian=1、renaissance=2；
    # modern_main 不联动 → 页面缺省 0）；显式给值压过流派。
    hsys: int | None = Field(default=None, description="宫制：缺省随流派（hellenistic=0/persian=1/renaissance=2，现代主流=0）；显式值优先。")
    # 择日口径（星阙 v3.6.0）：流派轴 + 13 个判读层参数，全部取自上游 electionParams.js。
    # 🔴 此前这里挂着 dignityScheme / starSet / medicalCritical / hourRuler / returnCharts /
    # primaryDirections / natalCompare / mundaneCompare / lotsSet / considerationsMode 十个字段，
    # 与 ELECTION_PARAM_SPEC 的 13 键**零重合**，且 skill 与上游全树都无人消费 —— 注释一边引着
    # 正确出处、字段一边写着发明的名字，声称了三个版本一次都没生效。诚实起见整批删除。
    # 顶层全局古典键（cazimiOrb/vocMode/partileDef/antisciaOrb/starOrb… 同卜卦）进判读**全局层**（流派口径之下）。
    school: Any | None = Field(
        default=None,
        description="择日流派档：modern_main（默认）/ hellenistic / persian / renaissance / modern_revival。",
    )
    options: dict[str, Any] | None = Field(
        default=None,
        description=(
            "判读层参数覆写 {key: value}；键取自引擎词表 ELECTION_PARAM_SPEC："
            "termsVariant / tripSystem / orbProfile / vocMode / bodySet / mansionAnchor / "
            "marriageTradition / querentGender / erosConstruction / lotsReversal / "
            "firdariaNightOrder / zrLot / pdTimeKey。不认识的键原样回执在 data.params_ignored。"
        ),
    )
    # 本命合参（上游「选本命盘」）：给了才产 [本命合参] 与 [回归与主限]（择日前最近日返/月返 + 择日日期 ±240 日
    # 主限命中，主限时间钥匙随 options.pdTimeKey）。缺 date/time/zone/lat/lon 任一 → tool.election_natal_missing_fields。
    natal: dict[str, Any] | None = Field(
        default=None,
        description="本命出生资料 {date,time,zone,lat,lon[,ad]}：加产 [本命合参] 与 [回归与主限]（日/月返 + 主限命中）。",
    )
    # 用事专属输入（上游左栏按用事显示的控件，ElectionMain.js:376-440 → runElection opts）：只在对应用事的规则包里
    # 生效，给了却不作用会进 warnings。值域锚定引擎词表（认不出的报错）。
    tradeSide: str | None = Field(default=None, description="买卖方向（trade）：sell=强己方 / buy=强货主方；缺省不指定。")
    talismanStar: str | None = Field(default=None, description="护符主星（talisman）：sun/moon/mercury/venus/mars/jupiter/saturn。")
    surgeryPart: str | None = Field(default=None, description="手术部位星座（surgery）：aries…pisces（按星座主管身体部位）。")
    surgeryPartOpposite: bool | None = Field(default=None, description="部位禁忌延及对宫（surgery）；缺省不延。")
    crisisBase: Any | None = Field(default=None, description="病始日期 YYYY-MM-DD（surgery/medication）：产 [危象日参照]。")


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
    # 神数 family (wangji 皇极经世 / wuzhao 五兆 / taixuan 太玄筮法 / jingjue 荆诀 / shenyishu 神易数 + 9 kinastro):
    # ganzhi-based, so date (+ time) + the 晚子时 switches drive the cast; kinastro 族另读 gender/zone（四柱按时区
    # 定气/立春界）。`options` = 技法旋钮，**逐技法键表**在 shenshu_options.SHENSHU_OPTION_KNOBS（类型校验；
    # horosa_agent_guidance(tool_name=…).options_keys 可查）；认不出的键不转发、回执 data.params_ignored。
    # 不在 tools/list 写键表：14 个工具共享本模型，逐工具描述会把广告层撑爆（预算见 verify_mcp_list_budget）。
    date: str
    # v0.36.0：神数五支的性别/地点此前未声明——`_run_shenshu_tool` 原样转发，CLI 有效而 MCP 扁平面静默丢弃
    # （PR #17 同型）。gender 五支皆用；zone/lat/lon（或 gpsLat/gpsLon）xianqin/qizhengkin/cetian 起盘需要。
    gender: int | str | None = None
    zone: str | None = None
    lat: str | None = None
    lon: str | None = None
    gpsLat: float | None = None
    gpsLon: float | None = None
    time: str | None = "00:00:00"
    after23NewDay: int | None = 1
    lateZiHourUseNextDay: int | None = 1
    options: dict | None = None


class CetianInput(ShenShuInput):
    # 策天飞星（v0.33.0 批 I-5）：+判词库原文（/cetian/texts，13 篇古籍判词）。
    textKey: str | None = Field(
        default=None,
        description="判词原文：list=目录 | all=全库（约 9 千字）| zhaodan/taiyuan/wuxing/qili/feixing/liming/yunxian/shengsi/keying/xianglun/jinjing/shenming/ruyuan 单篇。给了才产 [判词原文] 段。",
    )
    # v0.36.0：神数五支的性别/地点此前未声明——`_run_shenshu_tool` 原样转发，CLI 有效而 MCP 扁平面静默丢弃
    # （PR #17 同型）。gender 五支皆用；zone/lat/lon（或 gpsLat/gpsLon）xianqin/qizhengkin/cetian 起盘需要。
    gender: int | str | None = None
    zone: str | None = None
    lat: str | None = None
    lon: str | None = None
    gpsLat: float | None = None
    gpsLon: float | None = None
    # 地点显示名（sync311 F16）：上游 kinastro 挂载恒带 fields.pos（kinAstroFieldsSync.js:81），策天 [起盘]
    # 「地点」行只认它（webcetiansrv.py:398，缺名不出该行）；此前扁平面未声明 → 静默丢弃。
    pos: str | None = None


class QizhengKinInput(ShenShuInput):
    # 七政四余·张果星宗：地点显示名进 [起盘]（webqizhengkinsrv.py:484；缺名后端落占位「星阙地点」）。
    pos: str | None = None


class WangjiInput(ShenShuInput):
    # 皇极经世（v0.33.0 批 I-5）：+心易三法独立起卦（/wangji/xinyi；时刻法已内嵌于盘面 [心易发微]）。
    # sync311 F15：所选之法的卦面进 [心易发微]（上游 HuangJiMain.buildSnapshotText），缺省 datetime（上游挂载缺省）。
    xinyiMethod: str | None = Field(
        default=None,
        description="心易起卦法：datetime（缺省）/number/direction/character/none。结果进 [心易发微]。",
    )
    upperNum: int | None = Field(default=None, description="报数法上卦数")
    lowerNum: int | None = Field(default=None, description="报数法下卦数")
    objectGua: str | None = Field(default=None, description="方位法物象卦（缺省離，简繁皆可）")
    xinyiDirection: str | None = Field(default=None, description="方位法方位（缺省南，简繁皆可）")
    xinyiHour: int | None = Field(default=None, description="方位法时辰 0-23（缺省盘面时辰）")
    upperStrokes: int | None = Field(default=None, description="字画法上字笔画数")
    lowerStrokes: int | None = Field(default=None, description="字画法下字笔画数")


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
    rateKey: str | None = Field(default=None, description="速率：persian 1°/年（缺省）| prophected 30°/年 | naibod 59′08″/年；驱动应期表与指定日期盘")
    direction: str | None = Field(default=None, description="方向：direct（缺省）| converse 逆向；驱动应期表与指定日期盘")
    maxYears: float | None = Field(default=None, description="应期年数（缺省 90；上游五档 50/90/120/150/200）")
    nodeRetrograde: bool | None = Field(default=None, description="交点按逆行处理（缺省 false，上游同默认）")


class MundaneInput(FlexibleModel):
    # 世俗入宫盘 (mundane ingress chart): cast at the precise solar-term ingress moment of a given year.
    # date/time are DERIVED from the ingress (jieqi) computation, so the inputs are year + 入宫节气 + place.
    year: int | str
    ingressTerm: str | None = "春分"  # 春分 / 夏至 / 秋分 / 冬至 (the four cardinal ingresses)
    lifespanMethod: str | None = Field(default=None, description=_LIFESPAN_METHOD_DESC)
    zone: str | None = "+08:00"
    lat: str | None = None
    lon: str | None = None
    gpsLat: float | None = None
    gpsLon: float | None = None
    ad: int | None = 1
    hsys: int | None = 0
    tradition: bool | None = False
    # 盘型分派（上游 MundaneMain 的 MUNDANE_TYPES）：底盘恒为入宫盘；盘型只决定加产哪组专属段/卡
    # （mundanehorary → [世运卜卦]/[世运问判]；solunar/vedicmundane → 各自求根盘；newmoon/fullmoon/
    # solecl/lunecl/cycles → 对应子盘的判读卡）。region 需 UI 选建置盘，headless 不支持（降级告警）。
    mundaneType: str | None = Field(
        default=None,
        description="盘型：ingress（默认）/ newmoon / fullmoon / solecl / lunecl / cycles / solunar / vedicmundane / mundanehorary。",
    )
    mhKind: str | None = Field(default=None, description="世运卜卦问类：war 战争（默认）/ weather 天候 / price 物价。")
    solunarType: str | None = Field(default=None, description="恒星派入境盘型：capsolar（默认）/arisolar/cansolar/libsolar/caplunar/arilunar/canlunar/liblunar。")
    solunarWeights: str | None = Field(default=None, description="恒星派权重方案（scheme_a 默认）。")
    solunarOrb: float | None = Field(default=None, description="角化容许度（默认 3°）。")
    vedicYear: int | None = Field(default=None, description="吠陀世运年份（缺省取 year）。")
    # 世运口径（上游页面设置 MundaneMain.js:519-526 + 吠陀世运 :1330-1340）与入宫盘的黄道口径：照常声明（校验 + MCP 扁平面
    # 收顶层键），不进 tools/list 广告层（预算）；值域见 agent_guidance。古典全局键（cazimiOrb…）经 request 整包透传进 /chart。
    ADVERTISE_HIDDEN: ClassVar[frozenset[str]] = frozenset({
        "mundaneRuleset", "mundaneOrbScheme", "mundaneIngressRule", "vedicDashaYearLen", "vedicFoundingYear",
        "vedicNatalAsc", "zodiacal", "siderealAyanamsa",
    })
    mundaneRuleset: str | None = Field(default=None, description="规则集：ptolemaic / medieval / modern（缺省）/ barbault。")
    mundaneOrbScheme: str | None = Field(default=None, description="受冲容许度覆盖：auto（缺省随规则集）/ moiety / by_aspect。")
    mundaneIngressRule: str | None = Field(default=None, description="入境主管制覆盖：auto（缺省）/ quarterly / aries_annual / capricorn_year。")
    vedicDashaYearLen: float | None = Field(default=None, description="世运大运年长：365.2425（缺省）/ 360。")
    vedicFoundingYear: int | None = Field(default=None, description="建国年（Muntha 敏感点用，须配 vedicNatalAsc）。")
    vedicNatalAsc: str | None = Field(default=None, description="建国盘上升星座键（aries…pisces）。")
    zodiacal: int | None = Field(default=None, description="黄道：0 回归（缺省）/ 1 恒星（配 siderealAyanamsa）。")
    siderealAyanamsa: str | None = Field(default=None, description="恒星黄道岁差制（zodiacal=1 时）。")


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
