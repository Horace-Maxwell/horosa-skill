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
    date: str
    time: str
    zone: str
    lat: str
    lon: str
    ad: int | None = 1
    hsys: int | None = 0
    tradition: bool | None = False
    predictive: bool | None = True
    southchart: bool | None = False
    zodiacal: int | bool | None = 0
    pdtype: Any | None = None
    pdMethod: Any | None = None
    pdTimeKey: Any | None = None
    pdaspects: list[int | str] | None = None
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
    relative: int | None = 0


class ZiWeiBirthInput(FlexibleModel):
    date: str
    time: str
    zone: str
    lat: str
    lon: str
    gender: bool | None = True
    after23NewDay: bool | None = False
    timeAlg: int | None = 0
    sihua: dict[str, list[str]] | None = None
    ad: int | None = 1


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
    phaseType: int | None = 0
    ad: int | None = 1


class BaZiDirectInput(BaZiBirthInput):
    gender: bool | None = True
    adjustJieqi: bool | None = False


class LiuRengGodsInput(FlexibleModel):
    date: str
    time: str
    zone: str
    lat: str
    lon: str
    gpsLat: float | None = None
    gpsLon: float | None = None
    after23NewDay: bool | None = False
    yue: str | None = None
    isDiurnal: bool | None = None
    guirengType: int | None = 2
    ad: int | None = 1


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
    timeAlg: int | None = 0
    ad: int | None = 1


class GuaNamesInput(FlexibleModel):
    name: list[str]


class QimenInput(BirthInput):
    after23NewDay: bool | None = False
    timeAlg: int | None = 0
    options: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    nongli: dict[str, Any] | None = None
    jieqi_year_prev: dict[str, Any] | None = None
    jieqi_year_current: dict[str, Any] | None = None


class TaiyiInput(BirthInput):
    after23NewDay: bool | None = False
    timeAlg: int | None = 0
    gender: str | int | None = None
    options: dict[str, Any] = Field(default_factory=dict)
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


class SanShiUnitedInput(FlexibleModel):
    date: str
    time: str
    zone: str
    lat: str
    lon: str
    gpsLat: float | None = None
    gpsLon: float | None = None
    ad: int | None = 1
    after23NewDay: bool | None = False
    timeAlg: int | None = 0
    qimen_options: dict[str, Any] = Field(default_factory=dict)
    taiyi_options: dict[str, Any] = Field(default_factory=dict)
    liureng_yue: str | None = None
    liureng_isDiurnal: bool | None = None


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


class HoraryInput(BirthInput):
    # 卜卦 (horary): the chart is cast at the QUESTION moment (date/time/place = when the question was asked).
    # category picks the quesited house: general/wealth/family/property/pregnancy/health/marriage/lawsuit/
    # theft/death/travel/career/hope/enemy (unknown → general).
    category: str | None = "general"
    tradition: bool | None = True
    predictive: bool | None = False


class ElectionInput(BirthInput):
    # 择日 (electional): the chart is cast at a CANDIDATE moment (date/time/place = the time being evaluated).
    # topicId picks the rule pack + hard flags: marriage/business/move_in/buy_property/trade/buy_car/contract/
    # surgery/travel/job_hunt/... (see TOPIC_MASTER; unknown → marriage).
    topicId: str | None = "marriage"
    tradition: bool | None = True
    predictive: bool | None = False


class YearSystem129Input(BirthInput):
    # 129年系统 (v2.5.0): seven planets each rule their 小年 (土30木12火15日19金8水20月25 = 129y), computed server-side.
    predictive: bool | None = True


class PersianDirectedInput(BirthInput):
    # 波斯向运 (v2.5.0): symbolic 1°/year direction — every planet/point advances +1°/年, natal cusps fixed.
    predictive: bool | None = False


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
    domain: str
    category: str
    key: str | None = None
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
