from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


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
    after23NewDay: bool | None = False
    yue: str | None = None
    isDiurnal: bool | None = None
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
    after: str | None = None
    before: str | None = None
    limit: int = 20
    include_payload: bool = True


class MemoryShowInput(FlexibleModel):
    run_id: str
    include_payload: bool = True
