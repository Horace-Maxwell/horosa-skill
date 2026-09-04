import json
import re
import zipfile
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.exports.parser import parse_export_content
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import ToolTransportError, ToolValidationError
from horosa_skill.knowledge import build_knowledge_registry
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import TOOL_EXPORT_TECHNIQUE_MAP, HorosaSkillService, _java_chart_payload, _java_chart_payload_candidates
from horosa_skill.testing_payloads import build_sample_payloads


def test_liureng_tool_description_prevents_manual_agent_calculation() -> None:
    description = TOOL_DEFINITIONS["liureng_gods"].description

    assert "当前" in description or "current-time" in description
    assert "do not hand-calculate" in description
    assert "shell/Python" in description
    assert "Xingque-compatible" in description


class FakeClient(HorosaApiClient):
    def __init__(self) -> None:
        super().__init__("http://fake")

    def probe(self, endpoint: str = "/common/time", payload: dict | None = None) -> bool:
        return True

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/electionscan/scan":
            # 真实形状：每行必带 pick/pickEnd（ε 缓冲后的安全起盘时刻）与 startJd/endJd。缺 pick 时
            # runner 会退回按分钟截断的 start，恰落征象边界外侧 —— 桩里必须有。
            if str(payload.get("startDate", "")).startswith("1999"):
                return {"err": "span_too_large", "detail": "span 400.0d exceeds 93d; split the request"}
            # 零命中窗（1997 起点）：合法响应但 intervals 空 —— 供「零命中仍出段/选中时刻星盘不产」用例。
            if str(payload.get("startDate", "")).startswith("1997"):
                return {"intervals": [], "truncated": False, "stats": {"evalPoints": 7, "spanDays": 3.0}}
            return {
                "intervals": [{
                    "start": "2028-04-01 00:00", "end": "2028-04-19 21:09",
                    "pick": "2028-04-01 00:01:30", "pickEnd": "2028-04-19 21:07:59",
                    "startJd": 2461862.1666666665, "endJd": 2461881.048255995, "durationMin": 27189.5,
                }],
                "truncated": False,
                "stats": {"evalPoints": 42, "spanDays": 20.0},
            }
        if endpoint == "/electionscan/explain":
            # 真实形状（election_scan.explain）：{'t', 'tree'}，tree 与条件树同构 {kind,op,pass,children}。
            return {
                "t": payload.get("t"),
                "tree": {"kind": "group", "op": "all", "pass": False, "children": [
                    {"kind": "leaf", "type": "in_sign", "pass": True, "actual": "金 158°51′ 处女"},
                    {"kind": "leaf", "type": "aspect", "pass": False, "actual": "金-月 差 8.2°(限 6°)"},
                ]},
            }
        if endpoint in ("/qizhengelectionscan/scan", "/indiaelectionscan/scan"):
            # 七政/印度择时（上游 v3.10.0）：与 /electionscan/scan 同形（区间 + pick/pickEnd + stats），
            # 判定跑在 astropy 侧。桩只保证形状；值级真相归 live 测试与 selfcheck。
            return {
                "intervals": [{
                    "start": "2028-04-01 06:12", "end": "2028-04-01 07:48",
                    "pick": "2028-04-01 06:13:30", "pickEnd": "2028-04-01 07:46:30",
                    "startJd": 2461862.7583333333, "endJd": 2461862.825, "durationMin": 96.0,
                }],
                "truncated": False,
                "stats": {"evalPoints": 96, "spanDays": 8.0},
            }
        if endpoint in ("/qizhengelectionscan/conditiontypes", "/indiaelectionscan/conditiontypes"):
            return {"types": ["day_night", "vara", "tithi"], "groups": ["all", "any", "not", "xor"]}
        if endpoint in ("/qizhengelectionscan/explain", "/indiaelectionscan/explain"):
            return {"t": payload.get("t"), "tree": {"kind": "group", "op": "all", "pass": True, "children": []}}
        if endpoint == "/electionscan/conditiontypes":
            return {"types": ["aspect", "in_sign", "numeric"], "groups": ["all", "any", "not", "xor"]}
        if endpoint == "/cetian/texts":
            return {"texts": {
                "zhaodan": {"title": "照胆经叙跋", "sections": [{"subtitle": "", "body": "立命即知富贵，安身便见根基。"}]},
                "keying": {"title": "克应歌", "sections": [{"subtitle": "", "body": "克应之说最玄微。"}]},
            }}
        if endpoint == "/wangji/xinyi":
            # 真实端点回 {ResultCode, Result:{method, result:{卦面}, sections}}；_unwrap_result 会连剥
            # Result 与内层小写 result 两层 → runner 拿到的是裸卦面 dict。桩照全信封发。
            return {"ResultCode": 0, "Result": {
                "method": payload.get("method"),
                "result": {"本卦": "頤", "變卦": "蠱", "動爻": 1},
                "sections": [{"title": "心易发微", "rows": [{"label": "本卦", "value": "頤"}]}],
            }}
        if endpoint == "/geomancy/catalog":
            return {"figures": [
                {"nameEn": "Via", "nameZh": "道路", "dots": [1, 1, 1, 1], "elementZh": "水", "planetZh": "太阴",
                 "signZh": "狮子", "qualityZh": "变动", "keywordsZh": "中性偏凶·利出行/变化"},
                {"nameEn": "Populus", "nameZh": "民众", "dots": [2, 2, 2, 2], "elementZh": "水", "planetZh": "太阴",
                 "signZh": "巨蟹", "qualityZh": "稳定", "keywordsZh": "中性·随众"},
            ], "traditions": []}
        if endpoint == "/location/acgpoint":
            return {
                "lat": payload.get("clickLat"), "lon": payload.get("clickLon"),
                "orb": payload.get("orb") or 2.0, "hsys": "W",
                "hits": [{"planet": "North Node", "angle": "Asc", "orb": 1.27}],
                "relocAngles": {"Asc": 218.94, "Desc": 38.94, "MC": 136.93, "IC": 316.93},
                "sensitive": {"vertex": 79.92, "eastpoint": 231.8},
                "cusps": [210.0 + i * 30 for i in range(12)],
            }
        if endpoint == "/location/acgevent":
            return {"kind": payload.get("kind"), "jd": 2461443.17, "date": "2027/02/06", "time": "15:59:39"}
        if endpoint == "/astroextra/planetcycles":
            return {
                "events": [
                    {"jd": 2459205.26, "year": 2020, "month": 12, "day": 21, "hour": 18.34, "lon": 300.49, "sign": 10},
                ],
                "startYear": payload.get("startYear"), "endYear": payload.get("endYear"),
                "p1": payload.get("p1") or "Jupiter", "p2": payload.get("p2") or "Saturn",
                "aspect": float(payload.get("aspect") or 0), "center": payload.get("center") or "geo",
            }
        if endpoint == "/astroextra/returns":
            return {"rows": [{
                "year": 2026,
                "solarReturn": {"jd": 2461193.9, "datetime": "2026-06-02 17:35:27", "date": "2026-06-02", "time": "17:35:27"},
                "lunarReturn": {"jd": 2461045.15, "datetime": "2026-01-04 23:34:20", "date": "2026-01-04", "time": "23:34:20"},
                "solarAsc": {"id": "Asc", "lon": 236.256, "sign": "Scorpio", "signlon": 26.256},
                "lunarAsc": {"id": "Asc", "lon": 120.5, "sign": "Leo", "signlon": 0.5},
            }]}
        if endpoint == "/jieqi/birth":
            # 样例出生 2028-04-06 09:33 → 落在 清明~谷雨 之间（括界判定用）。
            return {"jieqi": [
                {"ord": 4, "jieqi": "清明", "jie": True, "time": "2028-04-04 15:02:44", "ad": 1, "jdn": 2461865.13},
                {"ord": 5, "jieqi": "谷雨", "jie": False, "time": "2028-04-19 22:08:00", "ad": 1, "jdn": 2461880.42},
                {"ord": 6, "jieqi": "立夏", "jie": True, "time": "2028-05-05 07:30:15", "ad": 1, "jdn": 2461895.81},
            ]}
        if endpoint == "/india/rectify":
            # 真实形状（rectify_core，jsonpickle 直吐无信封；vara.note/disclaimer 上游原文）。
            return {
                "available": True, "anchorTime": "1990-01-01 12:00:00",
                "windowMinutes": 10.0, "stepSeconds": 120, "candidates": 11,
                "rpSource": payload.get("rectifyRpSource") or "anchor",
                "anchorRp": {"set": ["Venus", "Mars", "Moon", "Saturn", "Jupiter", "Mercury"]},
                "vara": {"civil": "Saturn", "sunrise": "Saturn", "basisUsed": "sunrise",
                         "note": "日界=日出;既有本命 KP 面板用民用日口径,二者不同时此处以日出为准并双份回显"},
                "resolution": {"maxLagnaDeltaDeg": 0.4926, "narrowestSubDeg": 0.6667, "adequate": True,
                               "stepSeconds": 120, "suggestedStepSeconds": 120},
                "criteriaActive": ["rp", "pranapada", "boundary"],
                "runs": {"lagnaSubLord": [
                    {"value": "Rahu", "fromIndex": 0, "toIndex": 3, "count": 4, "fromTime": "11:50:00", "toTime": "11:56:00"},
                    {"value": "Jupiter", "fromIndex": 4, "toIndex": 10, "count": 7, "fromTime": "11:58:00", "toTime": "12:10:00"},
                ]},
                "top": [{
                    "offsetSeconds": 0, "time": "12:00:00", "ascLon": 56.86,
                    "lagnaSignLord": "Venus", "lagnaStarLord": "Mars", "lagnaSubLord": "Jupiter",
                    "score": {"total": 13.0, "parts": {"pranapada": 1.0, "rp": 6.0, "events": 0}},
                    "rp": {"score": 6.0, "maxScore": 6.0, "hits": {}},
                    "pranapada": {"overall": "good", "score": 1.0},
                    "boundary": {"moonGandanta": None, "lagnaGandanta": {"inGandanta": True}},
                }],
                "samples": [], "elapsedMs": 18.2,
                "disclaimer": "半自动校时:输出证据与排序,采信与「采用」由用户决定",
            }
        if endpoint == "/predict/persianchart":
            # 真实形状（getPersianDirectedByDate，jsonpickle 直吐无信封）。
            return {
                "date": payload.get("datetime"), "rateKey": payload.get("rateKey") or "persian",
                "direction": payload.get("direction") or "direct", "ageYears": 31.25,
                "chart": {
                    "objects": [
                        {"id": "Sun", "sign": "Virgo", "signlon": 8.855},
                        {"id": "Moon", "sign": "Scorpio", "signlon": 12.5},
                    ],
                    "aspects": [
                        {"directId": "Sun", "objects": [{"natalId": "Pluto", "aspect": 135, "delta": 0.74}]},
                    ],
                },
                "natalChart": {"chart": {}},
                "lots": [{"id": "Pars Spirit", "lon": 62.67}],
            }
        if endpoint == "/qizhengelection/pan":
            # 真实形状（webqizhengelectionsrv.pan）：Result 是 dict → _unwrap_result 剥出内层。
            return {
                "jdUt": 2461284.77, "trueSolarTime": "14:15:31", "equationOfTimeMin": -0.08,
                "lifeDeg": 157.58, "lifeJd": 2461284.4, "sunAzimuthSpeedDegPerMin": 0.2819,
                "rise": {"sunrise": "05:42:11", "sunset": "18:31:04", "moonrise": "20:02:00", "moonset": "08:11:00"},
                "planets": [
                    {"id": "Sun", "label": "日", "lonTropical": 158.855, "lat": 0.0002, "speedLon": 0.967,
                     "retrograde": False, "azimuth": 232.92, "altitudeTrue": 46.25, "altitudeAppa": 46.27},
                    {"id": "Mercury", "label": "水", "lonTropical": 172.4, "lat": 1.2, "speedLon": -0.5,
                     "retrograde": True, "azimuth": 245.1, "altitudeTrue": -3.4, "altitudeAppa": -3.2},
                ],
                "housesBySystem": {"A": [150.0 + i * 30 for i in range(12)]},
                "stellarLon": [{"name": "壁", "lon": 10.46}],
                "ascmc": {"asc": 250.1, "mc": 160.2},
            }
        if endpoint == "/qizhengelection/eclipses":
            # 真实形状：Result 是**数组** → _unwrap_result 不剥，信封原样返回。
            return {"ResultCode": 0, "Result": [
                {"jd": 2461443.17, "date": "2027-02-06", "time": "23:59:39", "kindFlag": 9},
                {"jd": 2461619.92, "date": "2027-08-02", "time": "18:06:41", "kindFlag": 5},
            ]}
        if endpoint == "/qizhengelection/azimuthsearch":
            return {"ResultCode": 0, "Result": [
                {"jd": 2461284.68, "date": "2026-09-01", "time": "12:14:31", "azimuth": 180.0},
            ]}
        house_signs = [
            ("House8", 0.0),
            ("House9", 30.0),
            ("House10", 60.0),
            ("House11", 90.0),
            ("House12", 120.0),
            ("House1", 150.0),
            ("House2", 180.0),
            ("House3", 210.0),
            ("House4", 240.0),
            ("House5", 270.0),
            ("House6", 300.0),
            ("House7", 330.0),
        ]
        chart_payload = {
            "params": {
                "birth": f"{payload.get('date', '1990-01-01')} {payload.get('time', '12:00:00')}",
                "date": payload.get("date", "1990-01-01"),
                "time": payload.get("time", "12:00:00"),
                "zone": payload.get("zone", "+00:00"),
                "lat": payload.get("lat", "31n14"),
                "lon": payload.get("lon", "121e28"),
                "hsys": payload.get("hsys", 0),
                "zodiacal": payload.get("zodiacal", 0),
                "tradition": payload.get("tradition", False),
            },
            "chart": {
                "ok": True,
                "isDiurnal": True,
                "zodiacal": "Tropical",
                "hsys": "Whole Sign",
                "dayofweek": "周六",
                "dayerStar": "Saturn",
                "timerStar": "Sun",
                "nongli": {"birth": f"{payload.get('date', '1990-01-01')} {payload.get('time', '12:00:00')}"},
                "houses": [{"id": house_id, "lon": lon} for house_id, lon in house_signs],
                "objects": [
                    {"id": "Sun", "house": "House8", "ruleHouses": ["House12"], "su28": "角", "sign": "Aries", "signlon": 14.55, "lon": 14.55, "meanSpeed": 0.983, "lonspeed": 0.985, "selfDignity": ["exalt", "dayTrip", "face"], "score": 8, "antisciaPoint": {"sign": "Virgo", "signlon": 15.43}, "cantisciaPoint": {"sign": "Pisces", "signlon": 15.43}},
                    {"id": "Moon", "house": "House3", "ruleHouses": ["House11"], "su28": "亢", "sign": "Scorpio", "signlon": 10.1, "lon": 220.1, "meanSpeed": 13.183, "lonspeed": 12.189, "selfDignity": ["partTrip", "fall"], "score": -1},
                    {"id": "Mercury", "house": "House7", "ruleHouses": ["House1", "House10"], "su28": "氐", "sign": "Pisces", "signlon": 16.78, "lon": 346.78, "meanSpeed": 1.0, "lonspeed": 1.011, "selfDignity": ["term", "fall", "exile"], "score": -7},
                    {"id": "Venus", "house": "House9", "ruleHouses": ["House2", "House9"], "su28": "房", "sign": "Taurus", "signlon": 5.73, "lon": 35.73, "meanSpeed": 1.2, "lonspeed": 1.229, "selfDignity": ["ruler", "dayTrip", "term"], "score": 10},
                    {"id": "Mars", "house": "House7", "ruleHouses": ["House3", "House8"], "su28": "心", "sign": "Pisces", "signlon": 25.72, "lon": 355.72, "meanSpeed": 0.517, "lonspeed": 0.781, "selfDignity": ["nightTrip", "term", "face"], "score": 6},
                    {"id": "Jupiter", "house": "House11", "ruleHouses": ["House4", "House7"], "su28": "尾", "sign": "Cancer", "signlon": 16.0, "lon": 106.0, "meanSpeed": 0.083, "lonspeed": 0.075, "selfDignity": ["exalt"], "score": 4},
                    {"id": "Saturn", "house": "House8", "ruleHouses": ["House5", "House6"], "su28": "箕", "sign": "Aries", "signlon": 5.95, "lon": 5.95, "meanSpeed": 0.033, "lonspeed": 0.124, "selfDignity": ["partTrip", "fall"], "hayyiz": "Hayyiz"},
                    {"id": "North Node", "house": "House7", "sign": "Pisces", "signlon": 7.21, "lon": 337.21, "lonspeed": -0.053},
                    {"id": "South Node", "house": "House1", "sign": "Virgo", "signlon": 7.21, "lon": 157.21, "lonspeed": -0.053},
                    {"id": "Pars Fortuna", "house": "House8", "sign": "Aries", "signlon": 9.05, "lon": 9.05},
                ],
                "stars": [{"id": "Sun", "stars": [["Bih", "Aries", 14.66, None, "壁宿二"]]}],
                "orientOccident": {"Sun": {"oriental": [{"id": "Saturn"}], "occidental": [{"id": "Venus"}]}},
            },
            "lots": [
                {"id": "Pars Spirit", "house": "House6", "sign": "Aquarius", "signlon": 17.95, "lon": 317.95},
                {"id": "Pars Faith", "house": "House5", "sign": "Capricorn", "signlon": 20.18, "lon": 290.18},
            ],
            "aspects": {
                "normalAsp": {
                    "Sun": {
                        "Applicative": [{"asp": 90, "id": "Jupiter", "orb": 1.452}],
                        "Separative": [{"asp": 0, "id": "Saturn", "orb": 8.6}],
                    },
                    "Moon": {
                        "Applicative": [{"asp": 120, "id": "Mercury", "orb": 6.686}],
                    },
                },
                "immediateAsp": {
                    "Sun": [{"asp": 0, "id": "Saturn", "orb": 8.6}, {"asp": 90, "id": "Jupiter", "orb": 1.452}],
                },
                "signAsp": {
                    "Sun": [{"asp": 0, "id": "Saturn"}, {"asp": 90, "id": "Jupiter"}],
                },
            },
            "receptions": {
                "normal": [{"beneficiary": "Venus", "supplier": "Moon", "supplierRulerShip": ["exalt", "nightTrip"]}],
                "abnormal": [{"beneficiary": "Mercury", "supplier": "Jupiter", "beneficiaryDignity": ["term", "fall"], "supplierRulerShip": ["ruler", "face"]}],
            },
            "mutuals": {
                "normal": [{"planetA": {"id": "Sun", "rulerShip": ["exalt"]}, "planetB": {"id": "Saturn", "rulerShip": ["partTrip"]}}],
                "abnormal": [],
            },
            "surround": {
                "attacks": {"Sun": {"MinDelta": [{"id": "Saturn", "aspect": 0}, {"id": "Jupiter", "aspect": -90}]}},
                "houses": {"House10": [{"id": "Venus"}, {"id": "Jupiter"}]},
                "planets": {"Sun": [{"id": "Saturn"}, {"id": "Venus"}]},
            },
            "declParallel": {
                "parallel": [["Sun", "Purple Clouds"], ["Pars Faith", "Mercury"]],
                "contraParallel": {"Neptune": ["Pallas"]},
            },
            "predict": {
                "PlanetSign": {
                    "Mars": ["火星落在双鱼座，描绘这样一个人。"],
                    "Jupiter": ["木星落在巨蟹座，描绘了这样一个人。"],
                }
            },
            "predictives": {
                "firdaria": [
                    {
                        "mainDirect": "Sun",
                        "subDirect": [
                            {"subDirect": "Venus", "date": "2000-01-01"},
                            {"subDirect": "Mercury", "date": "2001-01-01"},
                        ],
                    }
                ],
                "yearsystem129": [
                    {
                        "mainDirect": "Moon",
                        "subDirect": [
                            {"subDirect": "Moon", "date": "1990-01-01"},
                            {"subDirect": "Saturn", "date": "1993-08-17"},
                        ],
                    },
                    {
                        "mainDirect": "Saturn",
                        "subDirect": [
                            {"subDirect": "Saturn", "date": "2015-01-01"},
                        ],
                    },
                ],
            },
            # fourColumns 附带 v3.9.2 合冲字段（four.ganHe/ziHe6/ziXing…，后端真值同构：
            # {关系名: [{cell,zhu}…]}）——[干支合冲] 是纯排版段，桩必须给真内容（§5 规则 6）。
            "bazi": {"fourColumns": {
                "year": {"ganzi": "甲子"},
                "ganHe": {"甲己合土": [{"cell": "甲", "zhu": "年干"}, {"cell": "己", "zhu": "时干"}]},
                "ziCong": {"子午冲": [{"cell": "子", "zhu": "年支"}, {"cell": "午", "zhu": "日支"}]},
                "ziXing": {"子卯刑": [{"cell": "子", "zhu": "年支"}, {"cell": "卯", "zhu": "月支"}]},
            }},
            "liureng": {"ke": ["一课"], "overview": ["概览"]},
            "nongli": {"bazi": {"guolaoGods": {"ziGods": {"子": {"allGods": ["青龙"], "taisuiGods": ["岁驾"]}}}}},
        }
        if endpoint == "/qimen/pan":
            # ken (kinqimen) success shape — `source` is what _require_ken_pan checks.
            return {"source": "kinqimen", "selected": {"排局": "陽遁九局上"}, "raw": {"排局": "陽遁九局上"}, "mode": "hour", "sections": []}
        if endpoint == "/taiyi/pan":
            return {"source": "kintaiyi", "raw": {}, "kook": {"text": "二十四局"}, "palace16": []}
        if endpoint == "/jinkou/pan":
            return {"source": "kinjinkou", "rows": [{"name": "贵神"}], "raw": {}}
        if endpoint == "/nongli/time":
            # 全形状桩（供小六壬/飞宫/小成图/皇极轨策 占时起卦派生用；对既有 qimen/taiyi 流是纯增键）：
            # yearJieqi=立春界年柱、monthGanZi、dayGanZi、time=时柱干支、monthInt/dayInt=农历月日。
            return {
                "birth": f"{payload['date']} {payload['time']}", "nongli": "丙午年二月十七",
                "year": "丙午", "yearJieqi": "丙午", "monthGanZi": "辛卯", "dayGanZi": "戊辰",
                "time": "庚午", "monthInt": 2, "dayInt": 17, "leap": False,
            }
        if endpoint == "/calendar/month":
            # 黄历月历桩：两天当月项 + 一天补位（跨月过滤锚），字段形态与后端真值同构。
            month = str(payload.get("date") or "2028-04-06")[:7]
            return {
                "prevDays": [],
                "days": [
                    {
                        "birth": f"{month}-01 12:00:00", "year": "戊申", "yearJieqi": "戊申",
                        "month": "三月", "day": "初一", "dayInt": 1, "leap": False,
                        "monthGanZi": "丙辰", "dayGanZi": "甲子", "yearNaying": "大驿土",
                        "dayOfWeek": 6, "jieqi": None, "jieqiTime": None,
                        "moonTime": "12:20:33", "date": f"{month}-01", "time": "庚午",
                        "chef": "乙木用事", "jiedelta": "清明后第2天", "qimengYearGua": None,
                    },
                    {
                        "birth": f"{month}-06 12:00:00", "year": "戊申", "yearJieqi": "戊申",
                        "month": "三月", "day": "初六", "dayInt": 6, "leap": False,
                        "monthGanZi": "丙辰", "dayGanZi": "己巳", "yearNaying": "大驿土",
                        "dayOfWeek": 4, "jieqi": "清明", "jieqiTime": "2028-04-04 16:02:11",
                        "moonTime": None, "date": f"{month}-06", "time": "庚午",
                        "chef": "乙木用事", "jiedelta": "清明后第2天", "qimengYearGua": None,
                    },
                    {
                        "birth": "2028-05-01 12:00:00", "year": "戊申", "yearJieqi": "戊申",
                        "month": "四月", "day": "初八", "dayInt": 8, "leap": False,
                        "monthGanZi": "丁巳", "dayGanZi": "甲午", "dayOfWeek": 1,
                        "jieqi": None, "moonTime": None, "date": "2028-05-01",
                    },
                ],
            }
        if endpoint == "/jieqi/year":
            # entries carry both `name` (jieqi_year tool) and `jieqi`+`time` (mundane ingress lookup).
            term = (payload.get("jieqis") or [None])[0]
            entries = [
                {"name": "春分", "jieqi": "春分", "time": "2025-03-20 17:01:41"},
                {"name": "夏至", "jieqi": "夏至", "time": "2025-06-21 10:42:00"},
            ]
            if term and term not in {"春分", "夏至"}:
                entries.append({"name": term, "jieqi": term, "time": "2025-09-23 06:19:00"})
            return {"year": payload["year"], "jieqi24": entries}
        if endpoint == "/liureng/gods":
            return {"liureng": {"layout": "ok", "fourColumns": {"year": {"ganzi": "丙午"}}}}
        if endpoint == "/liureng/runyear":
            return {
                "liureng": {"layout": "ok", "fourColumns": {"year": {"ganzi": "丙午"}}},
                "runyear": {"year": "甲子", "age": 38},
            }
        if endpoint == "/germany/midpoint":
            return {
                "midpoints": [
                    {"idA": "Sun", "idB": "Moon", "sign": "Aries", "signlon": 15.0},
                    {"idA": "Venus", "idB": "Mars", "sign": "Cancer", "signlon": 102.5},
                ],
                "aspects": {
                    "Sun": [
                        {"aspect": 90, "delta": 0.125, "midpoint": {"idA": "Venus", "idB": "Mars"}},
                    ]
                },
                "tnp": [
                    {"id": "Cupido", "lon": 33.5, "sign": "Taurus", "signlon": 3.5},
                    {"id": "Hades", "lon": 132.0, "sign": "Leo", "signlon": 12.0},
                ],
            }
        if endpoint == "/geomancy/reading":
            # 天文地占：合成 reading（4母→16图形/十二宫/判官见证/解读技法），供 geomancy 契约 round-trip。
            def _gfig(nz, pz, ez):
                return {"nameZh": nz, "nameEn": nz, "planetZh": pz, "elementZh": ez}

            return {
                "reading": {
                    "question": payload.get("question") or "",
                    "questionType": payload.get("questionType") or "custom",
                    "questionTypeZh": "事业",
                    "profileId": payload.get("profile") or "european_classical",
                    "ascendantFigure": _gfig("获得", "太阳", "火"),
                    "ascendantSignZh": "白羊",
                    "judge": _gfig("道路", "太阴", "水"),
                    "reconciler": _gfig("会合", "水星", "风"),
                    "rightWitness": _gfig("牢狱", "土星", "地"),
                    "leftWitness": _gfig("获得", "太阳", "火"),
                    "primaryHouse": 10,
                    # v3.5.1：解读技法补三方/数量；转宫派生 + 定局落星·甲乙 全集段供契约覆盖。
                    "technique": {"perfection": "occupation", "aspect": "trine", "points_parity": {"total": 68, "parity": "even", "scope": "shield16"}, "timing": {"speed": "slow", "unit": "月", "quantity": {"label": "少", "total": 68, "min": 60, "max": 76}}, "triplicities": [1, 5]},
                    "derived": {"turn_to": 7, "derived_querent_house": 7, "derived_quesited_house": 4, "perfection": "conjunction", "figure": _gfig("会合", "水星", "风")},
                    "planetPlacement": {"Sun": [1, 10], "Moon": [], "Mars": [5]},
                    "planetPlacementByTwelves": {"Sun": 1, "Moon": 2, "Mars": 5},
                    "houses": [{"house": 1, "nameZh": "命宫", "roles": ["querent"], "figure": _gfig("获得", "太阳", "火"), "reading": "问者得力"}],
                    "figures16": [_gfig("获得", "太阳", "火") for _ in range(16)],
                },
                "figures": [],
            }
        if endpoint == "/location/acg":
            # 占星地图：两星线表 + 一条偕升 + 一处交点，供 acg 契约 round-trip。
            def _acg_planet(mc, ic, zlat, zlon):
                return {
                    "lines": {"mc": {"lon": mc}, "ic": {"lon": ic}, "asc": [], "desc": []},
                    "zenith": {"lat": zlat, "lon": zlon},
                    "oob": False,
                }

            return {
                "meta": {"mode": "mundo", "lsMode": "great", "geodetic": "sepharial", "geodeticVar": "longitude"},
                "planets": {"Sun": _acg_planet(120.5, -59.5, 11.2, 120.5), "Moon": _acg_planet(30.0, -150.0, -5.1, 30.0)},
                "parans": [{"lat": 42.5, "a": "Sun", "aEvent": "mc", "b": "Moon", "bEvent": "rise", "type": "RSCA"}],
                "crossings": [{"pa": "Sun", "av": "mc", "pb": "Moon", "bv": "asc", "lat": 42.5, "lon": 120.5}],
            }
        if endpoint == "/predict/dice":
            return {
                "planet": payload.get("planet", "Sun"),
                "sign": payload.get("sign", "Aries"),
                "house": payload.get("house", 0),
                "diceChart": chart_payload,
                "chart": chart_payload,
            }
        # `/predict/*` 的交叉相位是**数组**形状（后端 perpredict.getAspects），且挂在 `chart` 里，
        # 与本命盘的 {normalAsp, immediateAsp, signAsp} 完全不同。桩早先在**顶层**塞本命形状的
        # aspects，于是「推运相位段在真机上是空的」这个 bug 在离线测试里恒绿。桩必须同形。
        predictive_cross_aspects = [
            {"directId": "Sun", "objects": [{"natalId": "Sun", "aspect": 0, "delta": 0.0}, {"natalId": "Mars", "aspect": 90, "delta": 0.929}]},
            {"directId": "Moon", "objects": [{"natalId": "Venus", "aspect": 120, "delta": 0.262}]},
        ]
        if endpoint in {"/predict/solarreturn", "/predict/lunarreturn", "/predict/givenyear"}:
            return {
                "date": payload.get("datetime", "2031-04-06 09:33:00"),
                "chart": {**chart_payload["chart"], "aspects": predictive_cross_aspects},
                "lots": chart_payload["lots"],
                "dirParams": {
                    "date": "2031-04-06",
                    "time": "09:33:00",
                    "zone": payload.get("dirZone", payload.get("zone", "+08:00")),
                    "lat": payload.get("dirLat", payload.get("lat", "31n13")),
                    "lon": payload.get("dirLon", payload.get("lon", "121e28")),
                },
                "dirChart": chart_payload,
            }
        if endpoint in {"/predict/solararc", "/predict/profection"}:
            # 真实响应只有 {chart:{objects, aspects}}，顶层**没有** aspects——桩不许比真实响应更宽松。
            return {
                "date": payload.get("datetime", "2031-04-06 09:33:00"),
                "chart": {**chart_payload["chart"], "aspects": predictive_cross_aspects},
                "lots": chart_payload["lots"],
            }
        if endpoint == "/predict/pd":
            return {
                "pd": [
                    [0.25, "D_Moon_120", "N_Saturn_0", "Z", "2031-04-06 09:33:00"],
                    [1.5, "S_Sun_90", "N_MC_0", "Z", "2032-08-12 10:00:00"],
                ]
            }
        if endpoint == "/predict/pdchart":
            return {
                "date": payload.get("datetime", "2031-04-06 09:33:00"),
                "arc": 3.0,
                "chart": chart_payload["chart"],
                "lots": chart_payload["lots"],
                "aspects": chart_payload["aspects"],
            }
        if endpoint == "/predict/zr":
            return {
                "zr": [
                    {
                        "sign": "Aries",
                        "level": 1,
                        "date": "2028-04-06",
                        "days": 15,
                        "sublevel": [{"sign": "Taurus", "level": 2, "date": "2028-04-21", "days": 8}],
                    }
                ]
            }
        if endpoint == "/gua/desc":
            return {
                payload["name"][0]: {"name": "乾为天", "卦辞": "元亨利贞"},
                payload["name"][1]: {"name": "水火既济", "卦辞": "亨小利贞"},
            }
        if endpoint == "/chart13":
            return chart_payload
        if endpoint == "/astroextra/harmonic":
            # 真实后端把**整个标准 chart-wrap** 放在 `chart` 键下（比通用段构建器预期深一层），
            # 调波专属数据与之并列。桩必须同形——早先的桩没有 chart，于是 skill 侧
            # 「盘面段全是占位存根」这个 bug 在离线测试里完全看不见。
            return {
                "harmonic": payload.get("harmonic", 9),
                "positions": [
                    {"id": "Sun", "sign": "Capricorn", "signlon": 16.9, "lon": 286.9, "natalLon": 11.87},
                    {"id": "Moon", "sign": "Aries", "signlon": 10.05, "lon": 10.05, "natalLon": 1.12},
                ],
                "conjunctions": [{"a": "Mars", "b": "Saturn", "orb": 0.05}],
                "chart": chart_payload,
            }
        if endpoint.startswith("/xuanshi/"):
            # 玄史只读检索：search 返回**裸数组**（真实服务 jsonpickle 直吐 list），条目带史书引证等
            # 富字段——桩照真实形状，桩每简化一层就关掉一层守卫。
            return [
                {
                    "event_id": "XTS-027", "tradition": "正史", "history": "新唐书", "volume_no": "204",
                    "citation": "《新唐书》卷二百零四（CCDH 17-204；对照 Kanripo KR2a0027），段29",
                    "title": "尚献甫以荧惑犯五诸侯断己死并求厌", "period": "长安二年", "dynasty": "唐",
                    "techniques": ["占星"], "outcome": "如断而卒",
                },
                {
                    "event_id": "XTS-031", "tradition": "正史", "history": "旧唐书", "volume_no": "191",
                    "citation": "《旧唐书》卷一百九十一", "title": "袁天纲相武则天当为天子",
                    "period": "贞观初", "dynasty": "唐", "techniques": ["相术"], "outcome": "验",
                },
            ]
        if endpoint in {"/astroextra/draconic", "/astroextra/relocation"}:
            # 与 /astroextra/harmonic 同一嵌套形状：标准 chart-wrap 挂在 `chart` 键下，技法专属字段并列。
            # 桩必须同形——否则 skill 侧「盘面段全是占位存根」这类 off-by-one-level 缺陷离线看不见。
            if endpoint.endswith("draconic"):
                return {
                    "nodeLon": 123.45,
                    "positions": [{"id": "Sun", "natalLon": 11.87, "lon": 248.42, "sign": "Sagittarius", "signlon": 8.42}],
                    "conjunctions": [{"a": "Sun", "b": "Mars", "orb": 1.2}],
                    "chart": chart_payload,
                }
            return {
                "chart": chart_payload,
                "natalLat": payload.get("lat", "31n14"),
                "natalLon": payload.get("lon", "121e28"),
                "relocLat": payload.get("relocLat", "51n30"),
                "relocLon": payload.get("relocLon", "0w07"),
            }
        if endpoint == "/astroextra/planetreturn":
            # 多重回归: per-body return dates. Synthesize a couple so [多重回归] emits + export stays clean.
            return {"returns": [{"which": 1, "date": "2019-05-10"}, {"which": 2, "date": "2048-11-02"}]}
        if endpoint == "/astroextra/analysis":
            # 古典格局派生分析 (星阙 v2.6.7 analyze_chart) 的离线替身：合成护卫/优势相位/度数围攻 + 传光/聚光/
            # 不合意/交点弯曲 + 逐题主星 + 偶然尊贵 + Almuten + 分布/气质，使 [古典格局] 段离线稳定 emit。
            return {
                "classicalPatterns": {
                    "doryphory": [{"planet": "Venus", "light": "Sun", "elong": 28.4}],
                    "overcoming": [{"over": "Mars", "overSign": "Aries", "under": "Venus", "underSign": "Taurus", "aspect": "square"}],
                    "besieging": [{"planet": "Mercury", "left": "Mars", "right": "Saturn"}],
                },
                "aspectDynamics": {
                    "translation": [{"mover": "Moon", "from": "Saturn", "to": "Jupiter"}],
                    "collection": [{"collector": "Saturn", "p1": "Sun", "p2": "Moon"}],
                    "aversion": [{"a": "Sun", "b": "Saturn"}],
                    "bending": [{"planet": "Moon", "at": "北弯"}],
                    # 连接学说后四式 (空亡/阻止/挫败/收回)
                    "void": [{"planet": "Moon", "mode": "sign"}],
                    "prohibition": [{"blocker": "Mars", "between": "Venus", "to": "Jupiter"}],
                    "frustration": [{"frustrated": "Venus", "via": "Jupiter", "to": "Saturn"}],
                    "refranation": [{"planet": "Mercury", "to": "Sun"}],
                },
                "topicAlmuten": [{"topic": "婚配", "house": 7, "significator": "Venus", "almuten": "Mars"}],
                "accidentalDignity": [{"planet": "Saturn", "score": 12, "factors": ["角宫+5", "行速+2", "自由光+5"]}],
                "almutem": {"winner": "Saturn", "totals": {"Saturn": 30, "Jupiter": 29, "Venus": 26}},
                "distribution": {
                    "elements": {"Fire": 3, "Earth": 1, "Air": 2, "Water": 4},
                    "modes": {"Cardinal": 2, "Fixed": 2, "Mutable": 6},
                    "hemispheres": {"east": 2, "west": 8},
                },
                "temperament": {"temperaments": {"Choleric": 3, "Phlegmatic": 6}, "qualities": {"Hot": 5, "Cold": 7}},
            }
        # 神数 family — synthesize a snapshot whose [小节] headers cover the full export preset, so the
        # offline export-contract suite round-trips cleanly for all 14 (5 standalone + 9 kinastro-*).
        # 条件段（OPTIONAL）不合成 —— 真实后端只在特定入参时产它们（心易起卦/判词原文等 skill 侧追加段）。
        from horosa_skill.exports.registry import AI_EXPORT_OPTIONAL_SECTIONS as _OPTIONALS
        from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS as _PRESETS

        _SHENSHU_ENGINE = {
            "/wangji/pan": "kinwangji", "/wuzhao/pan": "kinwuzhao", "/taixuan/pan": "taixuanshifa",
            "/jingjue/pan": "jingjue", "/shenyishu/pan": "shenyishu",
            "/shaozi/pan": "kinastro-shaozi", "/tieban/pan": "kinastro-tieban", "/fendjing/pan": "kinastro-fendjing",
            "/beiji/pan": "kinastro-beiji", "/nanji/pan": "kinastro-nanji", "/chunzi/pan": "kinastro-chunzi",
            "/xianqin/pan": "kinastro-xianqin", "/cetian/pan": "kinastro-cetian", "/qizhengkin/pan": "kinastro-qizheng",
        }
        if endpoint in _SHENSHU_ENGINE:
            engine = _SHENSHU_ENGINE[endpoint]
            tech = endpoint.strip("/").split("/")[0]
            optional = set(_OPTIONALS.get(tech, []))
            sections = [s for s in _PRESETS.get(tech, ["起盘"]) if s not in optional]
            snapshot = "\n".join(f"[{title}]\n{title}：戊寅 —" for title in sections)
            return {
                "source": engine,
                "engine": engine,
                "dateStr": payload.get("date", f"{payload.get('year', 2025)}-01-01"),
                "timeStr": payload.get("time", "00:00:00"),
                "snapshot": snapshot,
            }
        if endpoint in ("/ziwei/birth", "/ziwei/rules"):
            # 紫微 P0–P2 (星阙 v2.6.x)：houses 带 主/辅/煞/杂曜 + 大限/小限；顶层 patterns 命中格局。
            return {
                "chart": {
                    "lifeMaster": "巨门",
                    "bodyMaster": "天相",
                    "wuxingJuText": "土五局",
                    "doujun": "巳",
                    "houses": [
                        {
                            "name": "命宫",
                            "ganzi": "甲子",
                            "direction": [5, 14],
                            "smallDirection": [1, 13, 25],
                            "starsMain": [{"name": "紫微", "sihua": "权"}],
                            "starsAssist": [{"name": "左辅"}],
                            "starsEvil": [{"name": "擎羊"}],
                            "starsOthersGood": [{"name": "三台"}],
                            "starsSmall": [{"name": "天才"}],
                        }
                    ],
                },
                "patterns": [
                    {"name": "府相朝垣", "category": "富贵", "broken": False, "duanyi": "天府天相来朝命垣，仓廪充盈。"},
                    {"name": "禄逢冲破", "category": "破格", "broken": True, "duanyi": "禄逢羊陀火铃冲破，得而复失。"},
                ],
            }
        return chart_payload


def sample_final_ai_report(question: str, *, source_title: str = "起盘信息") -> dict:
    return {
        "analysis_focus": question,
        "answer_text": (
            "我先直接给结论：这件事可以推进，但不适合盲目加速。"
            "从盘面材料看，当前更适合先确认资源、风险和时间窗口，再把行动拆成几个可验证步骤。"
            "如果用户问的是事业或财务，就要把机会和风险分开处理：事业可以准备，财务不要把不确定性放大成高杠杆。"
        ),
        "direct_answer": "结论上：已根据真实盘面和用户问题完成针对性判断，建议稳健推进、分阶段验证。",
        "executive_summary": "先看起盘结果，再围绕问题拆解机会、风险、时间窗口和行动建议。",
        "consultation_basis": [
            "以本次工具算出的真实盘面结果为依据。",
            "围绕用户问题提取关键章节、证据线索和现实行动含义。",
        ],
        "reading_steps": [
            "确认输入的时间、地点和用户事情。",
            "读取工具输出的盘面结构、导出正文和章节。",
            "围绕问题给出结论、证据、建议和限制。",
        ],
        "analysis_sections": [
            {
                "title": "问题结论",
                "body": "本次分析不是泛泛解释技法，而是把盘面结果转成用户能直接使用的判断。",
                "evidence_lines": [source_title],
                "relevance_to_question": "直接回应用户问题。",
            },
            {
                "title": "行动建议",
                "body": "行动上建议先确认现实条件，再分阶段推进，避免把不确定性扩大成高风险决策。",
                "evidence_lines": [source_title],
                "relevance_to_question": "把盘面结论转成行动框架。",
            },
        ],
        "evidence": [{"source_section_title": source_title, "source_line": "测试盘面线索"}],
        "recommendations": ["保留报告和原始盘面，后续可复盘。", "如有具体选择，再追问时间窗口和风险边界。"],
        "limitations": ["报告用于辅助判断，不替代现实尽调。"],
    }


class FakeJsClient(HorosaJsEngineClient):
    def __init__(self) -> None:
        self.settings = None

    def run(self, tool_name: str, payload: dict[str, object]) -> dict:
        if tool_name == "tianxing":
            action = str(payload.get("action") or "snapshot")
            if action == "compile":
                return {"data": {"ok": True, "compiled": {"type": "all", "conditions": [
                    {"type": "in_sign", "params": {"planet": "Sun", "signs": [0]}},
                ]}}}
            if action == "split":
                # 跨月切成两段 —— 真正走到「按月切分 + 缝合」两条路径，单段会把它们双双绕过。
                # ⚠ 必须从**真实 cfg** 派生：写死日期会让「换个窗口」的用例静默拿到旧窗口。
                cfg = payload.get("cfg") or {}
                s, e = str(cfg.get("startDate") or ""), str(cfg.get("endDate") or "")
                mid = f"{s[:7]}-28" if len(s) >= 7 else s
                return {"data": {"ok": True, "segments": [
                    {"startDate": s, "startTime": cfg.get("startTime", "00:00"), "endDate": mid, "endTime": "00:00:00"},
                    {"startDate": mid, "startTime": "00:00:00", "endDate": e, "endTime": cfg.get("endTime", "23:59")},
                ]}}
            if action == "stitch":
                merged = [row for group in (payload.get("lists") or []) for row in group]
                return {"data": {"ok": True, "intervals": merged}}
            if action == "explain_section":
                # canned 但形状照真渲染器（tianxing.js explain_section）；真语汇由 npm selfcheck 金标守。
                explain = payload.get("explain")
                if not isinstance(explain, dict):
                    return {
                        "data": {"ok": False, "error": {"code": "missing_explain_tree", "message": "缺少判读树（explain）。"}},
                        "snapshot_text": "",
                    }
                return {"data": {"ok": True}, "snapshot_text": (
                    f"[单时判读]\n判读时刻：{payload.get('t')}\n且(全部满足) ✗\n"
                    "  设定 金 在 处女座\n  实际 金 158°51′ 处女 ✓\n"
                    "  设定 金 三合 月\n  实际 金-月 差 8.2°(限 6°) ✗"
                )}
            results = ((payload.get("ctx") or {}).get("results")) or []
            rows = "\n".join(
                f"{i + 1}. {r.get('start')} ~ {r.get('end')}" for i, r in enumerate(results)
            ) or "时间段内无满足全部条件的时刻。"
            return {"data": {"ok": True}, "snapshot_text": "\n".join([
                "[起盘信息]", "时间：2028-04-01 00:00　时区：+08:00", "地点：福州　119°19′E, 26°05′N", "",
                "[征象搜索配置]", "时间段：2028-04-01 00:00 → 2028-05-20 23:59",
                "搜索盘面：回归黄道 · 宫制：Placidus", "",
                "[征象条件]", "查找 太阳 在 白羊座", "",
                f"[命中区间]\n共 {len(results)} 个区间：\n{rows}",
            ])}
        if tool_name == "qizhengelection":
            # canned 但段头/行形照真渲染器（qizhengElection.js）；真展示换算由 npm selfcheck 金标守。
            kind = str(payload.get("kind") or "pan")
            fields = payload.get("fields") or {}
            if not isinstance(payload.get("data"), dict):
                return {"data": {"ok": False, "error": {"code": "missing_data", "message": "缺少后端返回数据（data）。"}}, "snapshot_text": ""}
            header = f"[起盘信息]\n时间：{fields.get('date')} {fields.get('time')}　时区：{fields.get('zone')}\n地点：{fields.get('pos')}"
            if kind == "pan":
                body = (
                    "[择日动盘]\n山位口径：二十四山·地盘　真北\n"
                    "日：08巳51 | 00申山25+ | 方位 232.9° 高度 46.3° | 平\n"
                    "水：22卯24 | 01酉山12− | 方位 245.1° 高度 -3.4° | 逆\n\n"
                    "[天象要素]\n真太阳时：14:15:31　均时差：-0.08 分\n日出：05:42:11　日没：18:31:04\n命度：07巳34（日出起）"
                )
            elif kind == "eclipses":
                body = "[日月食搜索]\n未来日食\n2027-02-06 23:59:39　环食·中心\n2027-08-02 18:06:41　全食·中心"
            else:
                body = "[方位搜索]\n日 到达 180.0°(未来 3 天)\n2026-09-01 12:14:31　180.0°（07午山30）"
            return {"data": {"ok": True}, "snapshot_text": f"{header}\n\n{body}"}
        if tool_name in ("zeri_scan", "zeri_scan_remote"):
            # 择日十技法（v3.10.0）。这个桩只负责**形状**：段头一律从真 preset 末三段取，
            # 不手抄 —— 手抄段头正是 v0.33.1 记的那条「桩比真实响应更简单」的亚型，
            # 段头一改桩就悄悄对不上而测试照绿。值级真相归 selfcheck.mjs 的金标（跑真引擎）。
            from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS as _PRESETS

            technique = str(payload.get("technique") or "")
            action = str(payload.get("action") or "scan")
            if action == "compile":
                return {"data": {"ok": True, "compiled": {"type": "all", "conditions": []}}}
            if action == "scan":
                return {"data": {
                    "ok": True,
                    "intervals": [
                        {"start": "2028-04-01 19:00", "end": "2028-04-01 21:00",
                         "pick": "2028-04-01 19:01", "pickEnd": "2028-04-01 20:59",
                         "startMs": 1838286000000, "endMs": 1838293200000, "durationMin": 120},
                        {"start": "2028-04-03 01:00", "end": "2028-04-03 03:00",
                         "pick": "2028-04-03 01:01", "pickEnd": "2028-04-03 02:59",
                         "startMs": 1838444400000, "endMs": 1838451600000, "durationMin": 120},
                    ],
                    "truncated": False,
                    "stats": {"samples": 193, "evalCount": 769, "spanDays": 8},
                    "hit_count": 2,
                    "compiled_tree": {"type": "all", "conditions": []},
                    "limits": {"max_hits": 1000, "max_span_days": 1830},
                }}
            sections = _PRESETS.get(technique, [])[-3:] or ["择时搜索配置", "择时条件", "命中时段"]
            results = payload.get("results") or []
            rows = "\n".join(
                f"{i + 1}. {r.get('start')} ~ {r.get('end')}" for i, r in enumerate(results)
            ) or "范围内无满足条件的时段。"
            return {"data": {"ok": True}, "snapshot_text": "\n\n".join([
                f"[{sections[0]}]\n时间段：2028-04-01 00:00 → 2028-04-08 23:59\n地点：福州　时区：8",
                f"[{sections[1]}]\n条件组（全部满足）",
                f"[{sections[2]}]\n{rows}",
            ])}
        if tool_name == "qimenzeri":
            action = str(payload.get("action") or "scan")
            if action == "scan":
                return {"data": {
                    "ok": True,
                    "intervals": [
                        {"start": "2028-04-01 19:00", "end": "2028-04-01 21:00",
                         "pick": "2028-04-01 19:01", "pickEnd": "2028-04-01 20:59",
                         "startMs": 1838286000000, "endMs": 1838293200000,
                         "durationMin": 120, "juText": "阳遁九局中元"},
                        {"start": "2028-04-03 01:00", "end": "2028-04-03 03:00",
                         "pick": "2028-04-03 01:01", "pickEnd": "2028-04-03 02:59",
                         "startMs": 1838444400000, "endMs": 1838451600000,
                         "durationMin": 120, "juText": "阳遁九局中元"},
                    ],
                    "truncated": False,
                    "stats": {"samples": 193, "evalCount": 769, "spanDays": 8},
                    "hit_count": 2,
                    "compiled_tree": {"type": "pattern_ji", "params": {"names": ["青龙回首"]}},
                }}
            results = payload.get("results") or []
            rows = "\n".join(
                f"{i + 1}. {r.get('start')} ~ {r.get('end')}　{r.get('juText', '')}" for i, r in enumerate(results)
            ) or "时间段内无满足条件的时辰。"
            return {"data": {"ok": True}, "snapshot_text": "\n".join([
                "[择日搜索配置]", "时间段：2028-04-01 00:00 → 2028-04-08 23:59",
                "地点：福州　时区：8", "参数：时家转盘·拆补·阴盘", "",
                "[择日条件]", "吉格·青龙回首", "",
                f"[命中时辰]\n{rows}",
            ])}
        if tool_name == "qimen":
            # 法奇门叠加层 (星阙 v-next)：snapshot 含全 14 段 preset（含六害/化解/八门化气大阵/用神分论/七要/孤辰寡宿）。
            from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS as _PRESETS

            sections = _PRESETS.get("qimen", [])
            return {
                "data": {"juText": "阳遁九局", "zhiFu": "天蓬", "zhiShi": "休门"},
                "snapshot_text": "\n".join(f"[{title}]\n{title}：—" for title in sections),
            }
        if tool_name == "taiyi":
            return {
                "data": {"zhao": "阳遁", "kook": "二十四局"},
                "snapshot_text": "[起盘信息]\n日期：2026-04-04 21:18\n\n[太乙盘]\n主算：二十四局",
            }
        if tool_name == "liuyao":
            # 六爻断卦结构 (analyzeLiuyao 引擎)：离线替身给结构化 [断卦结构] 段，供 sixyao 契约 round-trip。
            return {
                "data": {},
                "snapshot_text": (
                    "[断卦结构]\n流派：通用\n卦序：坎宫·三世(世3应6)\n"
                    "逐爻(初→上)：六神│伏神│本爻│世应│旺衰│状态│神煞\n第1爻：勾陈 卯木子孙 旺"
                ),
            }
        if tool_name == "tarot":
            # 塔罗：离线替身给引擎直出的 [牌阵综览]/[逐牌详解]/[综合断语]/[定局]，供 tarot 契约 round-trip。
            return {
                "deck": "rws",
                "spread": payload.get("spread") or "three",
                "snapshot_text": (
                    "[牌阵综览]\n【Rider–Waite–Smith (RWS)】三张(过去·现在·未来)(种子:test)\n所问:事业能否升迁\n\n"
                    "[逐牌详解]\n位置1(过去)：6 The Lovers 恋人（逆位）\n  含义:失败、愚妄之谋\n\n"
                    "[综合断语]\n主导元素:火(行动/意志)；大牌占比:67%\n\n"
                    "[定局]\nYes/No=NO(majority,score -1) · 精华牌 17 The Star 星星"
                ),
            }
        if tool_name == "lingqi":
            # 灵棋经：七段恒出（注家开关只影响段内行、不改段集）。离线替身给真内容，
            # 供 lingqi 导出契约 round-trip —— 禁裸「无」段、禁 generated_template 回退。
            return {
                "counts": [3, 2, 1],
                "seed": "t-656577286",
                "snapshot_text": (
                    "[起盘信息]\n所问:事业能否升迁(问类:仕途)\n占时：2028-04-06 09:33（+08:00）\n\n"
                    "[棋势]\n上位:3 枚(太阳)—— 君·天\n中位:2 枚(少阴)—— 臣·人\n下位:1 枚(少阳)—— 民·地\n"
                    "层际:中下为耦(得耦而悦)\n阴阳:阳数 2 层、阴数 1 层(阳多者道同而助)\n\n"
                    "[卦象]\n第三十二 中平卦(3·2·1)· 阴获外阳之象\n\n"
                    "[繇辞]\n象曰:居安思危,守成有终。\n\n"
                    "[诸家注]\n颜氏(颜幼明):进退在己,不可躁动。\n何氏(何承天):守常则吉。\n\n"
                    "[课断]\n此课:先难后易,宜静待时。\n\n"
                    "[断诗]\n诗曰:春来花自开 / 何须苦相催"
                ),
            }
        if tool_name == "bazi_geju":
            # 八字格局 (baziGeju 引擎)：离线替身给 [五行力量]/[格局·用神]/[盲派结构]，供 bazi 契约 round-trip。
            # 桩文本逐字取自真引擎（1989-09-04 00:30 男 = 己巳 壬申 丁卯 庚子，与
            # horosa-core-js/test/selfcheck.mjs 的值级金标同盘）。旧桩是手编的：`月令官·透` 这个 via
            # 引擎根本不产（只有 本气/中气/余气透干），四柱也互不自洽 —— 桩一旦不是真值，它就再也
            # 兜不住引擎侧的错（时柱键名那个 bug 就是这么活下来的，§5 规则 6）。
            return {
                "data": {},
                "snapshot_text": (
                    "[五行力量]\n（通行示例权重：天干100/本气100/中气60/余气30/月令×1.5）\n"
                    "分布：木9.3%　火18.6%　土16.3%　金28.8%　水27%\n最旺：金　最弱：木\n"
                    "日主火：身弱（同党印比 27.9% · 异党 72.1%）\n\n"
                    "[格局·用神]\n当前主用流派：传统综合（各派取用可异，下列多派对照）\n"
                    "格局：正财格（月令财·本气透干）\n"
                    "成败：破格——月令申逢刑，忌神坏格无救。（按透干十神/月令刑冲机械判定，会合牵制之细致变化请人工复核。）\n\n"
                    "[盲派结构]\n（象法·参考，与扶抑/格局体系不同）\n宾主：年宾(己巳) 月宾(壬申) 日主(丁卯) 时宾(庚子)"
                ),
            }
        if tool_name == "tongshefa":
            return {
                "data": {
                    "selected": {"taiyin": "巽", "taiyang": "坤", "shaoyang": "震", "shaoyin": "震"},
                    "baseLeft": {"name": "风雷益"},
                    "baseRight": {"name": "地雷复"},
                    "main_relation": "思克实",
                },
                "snapshot_text": "[本卦]\n左卦：风雷益\n右卦：地雷复\n\n[六爻]\n第六爻：左阳 / 右阴 / 已变\n\n[潜藏]\n左潜藏：山地剥\n\n[亲和]\n左亲和：泽风大过",
            }
        if tool_name == "jinkou":
            # 解读层 (星阙 v2.5.x)：snapshot 含全 20 段 preset（含用神强弱/四位生克/应期/地支关系/相关神煞）。
            from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS as _PRESETS

            sections = _PRESETS.get("jinkou", [])
            return {
                "data": {"guiName": "天乙", "jiangName": "登明", "wangElem": "木"},
                "snapshot_text": "\n".join(f"[{title}]\n{title}：—" for title in sections),
            }
        if tool_name == "canping":
            return {
                "data": {
                    "method": "ming",
                    "gender": "男",
                    "element": "水",
                    "partName": "水部",
                    "dayPalaceBranch": "亥",
                    "mingGong": "卯",
                    "benming": {"verses": {"numShun": 2152, "numNi": 3352}},
                    "dayun": [{"ageStart": 1, "ageEnd": 10, "branch": "卯"}],
                    "series": {"rows": [{"age": 1, "ganzhi": "丙午"}]},
                },
                "input_normalized": {"fourPillars": {"yearGz": "丙午", "monthBranch": "寅", "dayBranch": "戌", "hourBranch": "亥"}},
                "snapshot_text": (
                    "[起盘]\n年纳音：水（水部）  取法：明法(月支反向)\n日宫支：亥  命宫：卯\n\n"
                    "[本命]\n顺 2152：海底珊瑚枝，月里栽丹桂。\n逆 3352：雨漲長江急，煙波萬頃潮。\n\n"
                    "[大运·歲運]\n1-10岁 卯：顺2544 戰勝頭歌回，論功先後處。 ／ 逆2944 清秋天宇闊，雁字寫長空。"
                ),
            }
        if tool_name == "astroextra":
            # v2.4.0 本命增补 (12分度 / 主宰星链 / 寿命格局) for chart + mundane astrochart exports.
            return {
                "data": {
                    "dodeca": [{"id": "Sun", "natalLon": 10.0, "dodecaLon": 120.0}],
                    "dispositor": [{"id": "Sun", "chain": ["Sun", "Mars"]}],
                    "lifespan": {
                        "isDiurnal": True,
                        "hyleg": {"key": "sun", "lon": 10.0, "house": 1},
                        "alcocoden": {"alcocoden": "mars", "aspectToHyleg": "三合", "baseYears": 80, "predictedYears": 75},
                        "rulers": {"epikratetor": "sun", "oikodespotes": "mars", "kurios": "jupiter", "concordant": False},
                    },
                },
            }
        if tool_name == "heluo":
            return {
                "data": {
                    "gender": "男",
                    "chart": {
                        "tian": 19, "di": 44, "tianGua": "離", "diGua": "巽",
                        "xian": {"name": "火風鼎", "yuan": 3},
                        "hou": {"name": "水火既濟", "yuan": 6},
                    },
                    "dayun": {"all": [{"ageStart": 1, "ageEnd": 9, "gua": "火風鼎", "pos": 3, "yang": True}]},
                    "judge": {"xie": True},
                },
                "input_normalized": {"fourPillars": {"year": "丙午", "month": "庚寅", "day": "壬戌", "hour": "辛亥"}},
                "snapshot_text": (
                    "[起命]\n天数19→離　地数44→巽\n先天卦：火風鼎　元堂 九三\n后天卦：水火既濟　元堂 上六\n\n"
                    "[先天·火風鼎 元堂爻辞]\n摘要：此爻是鼎之賢。\n诗歌：象曰：鼎耳革。失其義也。\n\n"
                    "[后天·水火既濟 元堂爻辞]\n摘要：此爻是才足以濟世。\n诗歌：象曰：濡其首厲。何可久也？\n\n"
                    "[命运篇]\n天元气 艮(无)　地元气 離(有)\n化工 坎(有:坎)　葉\n\n"
                    "[大限·岁运]\n1-9岁 火風鼎 九三（阳9）"
                ),
            }
        if tool_name == "yizhangjing":
            return {
                "data": {
                    "input": {"yearBranch": "寅", "month": 1, "day": 24, "hourBranch": "戌", "gender": "男"},
                    "mingGong": {"branch": "未", "star": "天驛"},
                    "pattern": {"fourPalaceRank": "中中", "mingGe": "天驛命", "nineGrade": "中中", "gradeCount": {"up": 1, "mid": 2, "down": 1}},
                    "renshi": [{"palace": "命", "branch": "未", "star": "天驛"}],
                    "dayun": [{"from": 1, "to": 7, "branch": "卯", "star": "天破"}],
                    "shenshaHits": [{"palace": "命", "branch": "未", "star": "天驛", "name": "华盖", "text": "主孤高"}],
                    "shenshaLayer": True,
                },
                "input_normalized": {"date": "1998-02-20", "gender": 1},
                "snapshot_text": (
                    "[起盘信息]\n性别：男　生年支：寅(虎)　农历1月24日　生时支：戌（农历月）\n\n"
                    "[四柱四宫断语]\n年宫 寅(虎)·天權·人道·上品：早年有权。\n\n"
                    "[命宫与人事十二宫]\n命宫 未宫·天驛\n命=未天驛　财帛=午天文\n\n"
                    "[格局判定]\n四宫等第：中中　命格：天驛命　九品估：中中\n\n"
                    "[重犯]\n天貴×2：贵人重现。\n\n"
                    "[交互格]\n日天文×时天驛：文驛交驰。\n\n"
                    "[职业适性]\n（月柱天權）：宜公门。\n\n"
                    "[大限]\n从月宫起·一宫7年·顺行\n1-7岁 卯·天破(地狱道·下品)：早limit。\n\n"
                    "[小限与流年十二神]\n小限一宫一年·起日柱宫：1=太岁\n\n"
                    "[流年总论]\n（主星天驛）：驿马奔波。\n\n"
                    "[神煞合参]\n（通用命理合参层·非本术原生）\n命(未·天驛)：华盖—主孤高"
                ),
            }
        if tool_name == "xiaoliuren":
            # 小六壬：6 段无条件恒出（道门九宫含五行生克/拜解）。真内容样例，供离线契约 round-trip。
            return {
                "data": {"school": "dao", "nums": [5, 20, 7], "chuan": ["小吉", "空亡", "速喜"], "analysis": {}},
                "input_normalized": {"nums": [5, 20, 7], "school": "dao", "showOneThree": True, "askEvent": "求财"},
                "snapshot_text": (
                    "[问事]\n所问:求财\n\n"
                    "[起课]\n流派:道门九宫;三数:5、20、7(月/日/时,作一顺数自大安起)\n\n"
                    "[三传]\n第一传 小吉(坎水) —— 我/事件主体\n第二传 空亡(中土) —— 他人与外界因素\n第三传 速喜(离火) —— 事情的结果\n\n"
                    "[生克]\n空亡土克小吉水(2克1) → 被克\n速喜火生空亡土(3生2) → 有贵人相助,生我,爱我,保护我\n\n"
                    "[九神]\n大安(震木):木·正东\n速喜(离火):火·正南\n空亡(中土):失去、虚伪、空想\n\n"
                    "[化解]\n小吉被空亡克 → 拜玉皇化解"
                ),
            }
        if tool_name == "feigong":
            # 飞宫小奇门：7 段无条件恒出。真内容样例，供离线契约 round-trip。
            return {
                "data": {"qiZhi": "午", "jianZhi": "申", "longGong": 9, "dayGan": "甲", "dayZhi": "子", "zhongGong": ["乙", "庚"]},
                "input_normalized": {"qiMode": "manualZhi", "qiZhi": "午", "dayGan": "甲", "dayZhi": "子", "askEvent": "求财"},
                "snapshot_text": (
                    "[问事]\n所问:求财\n\n"
                    "[起局]\n起支:午;建星起于申;青龙(甲)落 9 宫\n\n"
                    "[干支]\n甲乘龙飞九宫:甲9 乙中 丙1 丁2 戊3 己4 庚中 辛6 壬7 癸8\n中宫双干:乙庚(五十居中)\n八门:休门起 1 宫\n\n"
                    "[命宫]\n年龄 35(男):调整数 35,命宫 3(震)\n\n"
                    "[宫位]\n主(日干甲)落 9 宫;客(日支子)落 1 宫\n\n"
                    "[运气]\n主宫9 得景门(平):远行有阻,音信利。\n\n"
                    "[应期]\n建星:申 起建,建除十二神随支顺布(以天星所临断应期缓急)。"
                ),
            }
        if tool_name == "xiaochengtu":
            # 小成图：6 段恒出 + [股市]（stock 模式）。真内容样例，供离线契约 round-trip。
            return {
                "data": {"mode": "stock", "ben": "天泽履", "zhi": "乾为天", "dongYaos": [], "yongGong": 1},
                "input_normalized": {"qiguaFa": "stock", "yongGong": 1, "askEvent": "问股"},
                "snapshot_text": (
                    "[问事]\n所问:问股\n\n"
                    "[起卦]\n本卦:天泽履;之卦:乾为天;动爻:无\n\n"
                    "[佈局]\n4巽 | 9乾 | 2离\n3乾 | 五(中) | 7乾\n8乾 | 1兑 | 6乾\n中宫五、十居中,无卦。\n\n"
                    "[推导]\n用宫所主:1宫坎(北·十一月),宫主命病盗\n\n"
                    "[四象]\n本卦天泽履:老阳\n\n"
                    "[应期]\n数占:正推链宫数相加 = 30(问数以数应)\n\n"
                    "[股市]\n研判·开盘:用宫天盘乾 → 涨(幅度大)\n研判·收盘:正推末卦乾 → 涨(幅度大)"
                ),
            }
        if tool_name == "guice":
            # 皇极轨策：占事直断/演数/四位 恒出 + 起卦/卦变/断法 条件段。真内容样例，供离线契约 round-trip。
            return {
                "data": {"qiguaFa": "baoshu", "gua": {"ben": "山天大畜", "bian": "风天小畜", "dongYao": 5}, "settings": {"school": "default", "qiguaFa": "baoshu"}},
                "input_normalized": {"qiguaFa": "baoshu", "settings": {"school": "default"}},
                "snapshot_text": (
                    "[占事直断]\n| 项 | 值 |\n| --- | --- |\n| 占事 | 问事业 |\n| 本卦 | 山天大畜　5 爻动 |\n| 变卦 | 风天小畜 |\n| 演数 | 策数 11149 |\n\n"
                    "[起卦]\n| 步骤 | 依据 | 所得 |\n| --- | --- | --- |\n| 上卦 | 先数 7 ÷8 余 | 艮 |\n| 下卦 | 后数 9 ÷8 余 | 乾 |\n\n"
                    "[演数]\n| 项 | 值 |\n| --- | --- |\n| 身数 | 192 |\n| 所得 | 11149 |\n\n"
                    "[四位]\n| 位 | 数 | 卦 | 取象 |\n| --- | --- | --- | --- |\n| 千 | 1 | 坎 | 水 |\n\n"
                    "[卦变]\n| 项 | 卦 |\n| --- | --- |\n| 本卦 | 山天大畜 |\n| 变卦 | 风天小畜 |\n\n"
                    "[断法]\n| 项 | 判 |\n| --- | --- |\n| 用生体 | 助力 |"
                ),
            }
        if tool_name == "zhengchuan":
            # 神数正传：五流派各产 17 段之子集，唯一恒出段=起盘信息。此桩为 tieban 子集，供离线契约 round-trip。
            return {
                "data": {"school": "tieban", "pillars": ["戊寅", "辛卯", "戊辰", "庚午"], "pillar_source_note": None},
                "input_normalized": {"school": "tieban"},
                "snapshot_text": (
                    "[起盘信息]\n流派:铁板神数　四柱:戊寅 辛卯 戊辰 庚午　性别:男\n\n"
                    "[起数]\n年上起数 戊寅→…　装成先天卦\n\n"
                    "[本命条文]\n一二三：命主聪明，早年多波折。\n\n"
                    "[流年条文]\n三十六岁：运转东南，渐入佳境。"
                ),
            }
        if tool_name == "progextra":
            # v2.5.0 推运 vendored builders (balbillus etc.) — return the single-section snapshot directly.
            technique = payload.get("technique")
            if technique == "balbillus":
                return {
                    "tool": "progextra",
                    "technique": "balbillus",
                    "data": {"ok": True},
                    "snapshot_text": (
                        "[Balbillus]\n"
                        "Balbillus 法（129 年系统 · 旺距削减）：主限长度 = 小年 × (1 − 离擢升度角距/360)。\n\n"
                        "| 主限 | 子限 | 起始日期 | 时长(年) |\n"
                        "| --- | --- | --- | --- |\n"
                        "| 太阳(15.62年) | 太阳 | 1990-01-01 | 1.30 |\n"
                        "| 太阳(15.62年) | 木星 | 1991-04-21 | 0.64 |"
                    ),
                }
            _PROGEXTRA_FAKE = {
                "triplicityrulers": (
                    "[三分主星推运]\n昼生盘，区间光体=太阳（白羊），三分主星依其落宫与状态主导人生各阶段（三分（0–25 / 25–50 / 50–75））。\n\n"
                    "| 阶段 | 主星 | 年龄段 | 日期段 | 落宫 | 状态 |\n| --- | --- | --- | --- | --- | --- |\n"
                    "| 主三分主星 | 太阳 | 0–25岁 | 1990~2015 | 第11宫·续宫·中 | 平 |"
                ),
                "keypoints": (
                    "[数字相位推运]\n释放点=身（月亮起）。各星与「自释放点起第 k 个星座」挂钩数字 k。\n\n"
                    "星位挂钩：太阳=第1座(小年18)\n\n"
                    "| 年龄 | 因数 | 位置激活 | 小年激活 |\n| --- | --- | --- | --- |\n| 1 | 质数 | 太阳 | - |"
                ),
                "lunationphase": (
                    "[月相推运]\n本命月相=朔 · 新月（日月差 10.0°）。次限推运日月差每年约 12.1908°。\n\n"
                    "| 起始年龄 | 日期 | 月相 | 关键词 |\n| --- | --- | --- | --- |\n| 0.0 岁(本命) | 1990-04-06 | 朔 · 新月 | 萌发 · 新启 · 直觉行动 |"
                ),
            }
            if technique in _PROGEXTRA_FAKE:
                return {"tool": "progextra", "technique": technique, "data": {"ok": True}, "snapshot_text": _PROGEXTRA_FAKE[technique]}
            return {"tool": "progextra", "technique": technique, "data": {"ok": False}, "snapshot_text": ""}
        if tool_name == "horary":
            return {
                "tool": "horary",
                "category": payload.get("category", "general"),
                "data": {"ok": True, "verdict": "倾向：不成 / 受阻", "significators": {"querentKey": "venus", "quesitedKey": "mars"}},
                "snapshot_text": (
                    "[起卦信息]\n问题类别：对象/婚姻\n时主星（活跃征象）：金星\n"
                    "[根本性]\n适合判断。\n"
                    "[征象星指派]\n问卜者 = 1宫主 金星 ＋ 月亮\n对象/婚姻 = 7宫主 火星（自然征象星 金星）\n"
                    "[完成分析]\n- 两征象星刚出相位 → 事已过/绝对失败。\n完成度三分：安全征象 3/3 → all\n"
                    "[月亮的故事]\n- 月刚离开 水星（对分(冲)，已过 1.3°）→ 事情来由/已过\n"
                    "[相位全览]\n- 太阳 六合 土星（入相/将成，差 0.6°）\n"
                    "[裁决]\n倾向：不成 / 受阻（建议另择时再问）\nQuery：①能否成事=否 ②好坏=凶 ③真假=真\n"
                    "[应期方位]\n无准确相位，应期不定；方位：—\n"
                    "[描述]\n- 问卜者：金星 体貌温和\n"
                    "（裁决只呈现证据与倾向，不替用户下命定结论。）"
                ),
            }
        if tool_name == "election":
            return {
                "tool": "election",
                "topicId": payload.get("topicId", "marriage"),
                "data": {"ok": True, "topic": "结婚/订婚", "overall": {"score": 0, "gradeCn": "不宜（含红线）"}, "hard_flags": 6},
                "snapshot_text": (
                    "[起盘信息]\n用事类型：结婚/订婚\n起盘时刻：戴戒指 + 互相宣示成为夫妻。\n"
                    "[总评]\n0/100　不宜（含红线）\n结婚/订婚择日：不宜（含红线）（0 分）。\n没有完美的择日盘：仅供参考。\n"
                    "[红线]\n- [high] 月亮逢刑（90°）：不安定、缺生产力 → 应避\n"
                    "[分项]\n月亮状态（40/100）\n  · 月亮逢刑\n"
                    "[用事专属]（满足 1/3）\n- ✓ 宜：金星有力\n- ✗ 忌：水逆\n"
                    "[建议]\n- 另择月相吉、月无刑冲的时段。"
                ),
            }
        if tool_name == "liureng":
            return {
                "data": {
                    "layout": {"downZi": ["子"], "upZi": ["申"], "houseTianJiang": ["青龙"]},
                    "ke": {"raw": [["青龙", "申", "甲"]], "lines": ["一课：地盘=甲，天盘=申，贵神=青龙"]},
                    "sanChuan": {"name": "涉害课", "cuang": ["甲申", "乙酉", "丙戌"], "liuQin": ["官鬼", "父母", "兄弟"], "tianJiang": ["青龙", "六合", "太常"]},
                    "runtime_note": "local_headless_liureng",
                },
                "snapshot_text": (
                    "[起盘信息]\n日期：2026-04-04 21:18\n\n"
                    "[十二盘式]\n月将：申；占时：巳；贵人：丑\n\n"
                    "[十二地盘/十二天盘/十二贵神对应]\n1. 地盘子 -> 天盘申 -> 贵神青龙\n\n"
                    "[四课]\n一课：地盘=甲，天盘=申，贵神=青龙\n\n"
                    "[三传]\n课式：涉害课\n初传：干支=甲申；六亲=官鬼；贵神=青龙\n\n"
                    "[概览]\n四课、三传已由本地 headless 六壬引擎根据离线盘面生成。"
                ),
            }
        if tool_name == "guolao_moira":
            # 七政四余 政余格局：headless buildLocalMoiraPatterns 的离线替身（喜/忌格各一）。
            return {
                "snapshot_text": "喜格：金水相涵（政余喜格：金水同宫，且不以冬令破格。）\n忌格：孛犯太阳（政余忌格：孛与太阳同宫。）",
                "data": {"patterns": [
                    {"name": "金水相涵", "level": "good", "detail": "政余喜格：金水同宫，且不以冬令破格。"},
                    {"name": "孛犯太阳", "level": "bad", "detail": "政余忌格：孛与太阳同宫。"},
                ]},
            }
        if tool_name == "calendar_extras":
            # 黄历页三个子模块的段块（真实 builder 纯本地、零后端）。日子馆两段只在给了
            # rizi.persons 时产 —— 桩沿用同一条件，好让 optional 的语义在离线也成立。
            blocks = [
                "[今日宜忌]\n宜：祭祀\n忌：动土",
                "[值神值宿]\n值神：金匮（黄道）",
                "[彭祖百忌]\n丁不剃头",
                "[吉神凶煞]\n吉神：天德",
                "[冲煞·胎神·方位]\n冲牛煞西",
                "[时辰吉凶]\n子时 吉",
                "[物候·六曜·数九三伏]\n候：温风至",
                "[流年年神方位]\n太岁：东南",
                "[通书择日]\n流派：董公择日",
            ]
            rizi = payload.get("rizi") if isinstance(payload.get("rizi"), dict) else None
            if rizi and rizi.get("persons"):
                blocks.append("[日子馆·个性化择日]\n事项：嫁娶")
                blocks.append("[当事人八字]\nmale（甲）：乙亥年 属猪")
            return {"text": "\n\n".join(blocks)}
        if tool_name in {"huangli", "tongshu"}:
            # 纯本地技法的离线替身：段头与顺序取自上游 preset（真实 builder 零后端往返，
            # 这里只是让契约测试有稳定输入）。
            from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS as _P

            blocks = []
            for title in _P[tool_name]:
                blocks.append(f"[{title}]\n{title}：离线替身内容。")
            return {"text": "\n\n".join(blocks)}
        if tool_name == "babylon":
            # 六段的离线替身：段头与顺序须与上游一致（微黄道居末，上游测试断言了这一点）。
            return {
                "text": "\n".join(
                    [
                        "[起盘信息]", "技法:巴比伦占星(美索不达米亚天象体系);坐标:恒星黄道 · 毕宿锚。",
                        "", "[七曜按宫]", "月:巨蟹 6°25′(ALLA);可变",
                        "", "[分至天狼星]", "图式:春分白羊 10°。",
                        "", "[位三法]", "月位:三分之一 · 昼段。",
                        "", "[行星神性]", "月 = Sîn(月神);中性偏吉。",
                        "", "[微黄道]", "十二分变体:B;微段 = 2;30°,全周 144 段。",
                    ]
                )
            }
        if tool_name == "egypt_section":
            # 假盘面不带真实黄经，vendored builder 会算出无意义结果 → 返回空文本，
            # 走与「/astroextra/analysis 失败」同一条优雅降级路径（该段不出）。
            return {"text": ""}
        raise AssertionError(f"Unexpected local tool: {tool_name}")


class FakeRuntimeManager:
    def __init__(self, *, degraded: bool = False, cooldown: float = 0.0) -> None:
        self.started = 0
        self.degraded = degraded
        self.cooldown = cooldown

    def start_local_services(self) -> dict[str, object]:
        self.started += 1
        return {"ok": True, "already_running": False, "degraded": self.degraded}

    def java_backend_cooldown_remaining(self) -> float:
        return self.cooldown


class ProbeClient(FakeClient):
    def __init__(self, *, probe_ok: bool) -> None:
        super().__init__()
        self.probe_ok = probe_ok
        self.probe_calls = 0

    def probe(self, endpoint: str = "/common/time", payload: dict | None = None) -> bool:
        self.probe_calls += 1
        return self.probe_ok


class CaptureClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        return super().call(endpoint, payload)


class OldBuildShenShuClient(FakeClient):
    """Simulates an OLDER 星阙 chart-service build: 神数 /{key}/pan returns structured `basic` data but
    NO `snapshot` field (the build predates the engine's build_snapshot()). The skill must surface this
    as a clean transport error rather than a silently-empty reading."""

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint.endswith("/pan") and endpoint.lstrip("/").split("/")[0] in {
            "shaozi", "tieban", "fendjing", "beiji", "nanji", "chunzi", "xianqin", "cetian", "qizhengkin",
            "wangji", "wuzhao", "taixuan", "jingjue", "shenyishu",
        }:
            return {"source": "kinastro", "engine": "kinastro-old", "basic": {"year_gz": "戊寅"}}  # no `snapshot`
        return super().call(endpoint, payload)


def test_shenshu_old_backend_without_snapshot_errors_clearly(tmp_path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, client=OldBuildShenShuClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool("shaozi", {"date": "1998-02-20", "time": "20:48:00", "gender": 1}, save_result=False)
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "transport.shenshu_snapshot_unavailable"
    assert "过旧" in result.error.message or "snapshot" in result.error.message.lower()


def test_shenshu_unparseable_date_errors_clearly(tmp_path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool("wuzhao", {"date": "not-a-date", "time": "20:48:00"}, save_result=False)
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "tool.shenshu_bad_date"


def test_service_tool_list_exposes_input_contracts(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    tools = {tool["name"]: tool for tool in service.list_tools()}

    assert tools["solarreturn"]["input_contract"]["required_for_real_call"] == [
        "date",
        "time",
        "zone",
        "lat",
        "lon",
        "datetime",
        "dirZone",
        "dirLat",
        "dirLon",
    ]
    assert tools["pd"]["input_contract"]["target_fields"]["pdaspects"].startswith("纳入表格")
    assert "主限法盘星体表格" in tools["pdchart"]["input_contract"]["output_contract"]


def test_service_tool_call_persists_memory(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    result = service.run_tool(
        "chart",
        {"date": "1990-01-01", "time": "12:00", "zone": "8", "lat": "31n14", "lon": "121e28"},
    )

    assert result.ok is True
    assert result.memory_ref is not None
    assert result.data["export_snapshot"]["technique"]["key"] == "astrochart"
    assert result.data["export_snapshot"]["sections"][0]["title"] == "起盘信息"
    assert "宫位宫头" in result.data["export_snapshot"]["selected_sections"]
    assert "星与虚点" in result.data["export_snapshot"]["selected_sections"]
    assert "第八宫 宫头" in result.data["export_snapshot"]["export_text"]
    assert "日 (8th; 12R)" in result.data["export_snapshot"]["export_text"]
    assert "福点 (8th; -)" in result.data["export_snapshot"]["export_text"]
    queried = store.query_runs(tool="chart")
    assert len(queried) == 1


def test_invalid_tool_payload_returns_agent_recovery_prompt(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    with pytest.raises(ToolValidationError) as exc_info:
        service.run_tool("chart", {"agent_confirmed_settings": True}, save_result=False)

    assert exc_info.value.code == "tool.invalid_payload"
    recovery = exc_info.value.details["agent_recovery"]
    assert recovery["must_ask_user"] is True
    assert "调用 `chart` 前需要先确认" in recovery["prompt_to_user"]
    assert any(item["field"] == "date/time/place" for item in recovery["ask_if_missing"])


def test_service_starts_runtime_before_first_remote_call_when_probe_fails(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    runtime_manager = FakeRuntimeManager()
    client = ProbeClient(probe_ok=False)
    service = HorosaSkillService(
        settings,
        client=client,
        store=MemoryStore(settings),
        js_client=FakeJsClient(),
        runtime_manager=runtime_manager,
    )

    result = service.run_tool(
        "chart",
        {"date": "1990-01-01", "time": "12:00", "zone": "8", "lat": "31n14", "lon": "121e28"},
        save_result=False,
    )

    assert result.ok is True
    assert runtime_manager.started == 1
    assert client.probe_calls == 1


def test_service_skips_runtime_restart_after_remote_runtime_is_confirmed(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    runtime_manager = FakeRuntimeManager()
    client = ProbeClient(probe_ok=False)
    service = HorosaSkillService(
        settings,
        client=client,
        store=MemoryStore(settings),
        js_client=FakeJsClient(),
        runtime_manager=runtime_manager,
    )

    for _ in range(2):
        result = service.run_tool(
            "chart",
            {"date": "1990-01-01", "time": "12:00", "zone": "8", "lat": "31n14", "lon": "121e28"},
            save_result=False,
        )
        assert result.ok is True

    assert runtime_manager.started == 1
    assert client.probe_calls == 1


def test_chart_classical_sections_emit_offline(tmp_path) -> None:
    # 星阙 v2.6.7 古典占星 (hermetic)：FakeClient 的 /astroextra/analysis 替身提供派生格局后，chart 导出应稳定
    # 含 [古典] (buildClassicalSection ← /chart objects: Melothesia 等) 与 [古典格局]
    # (buildClassicalAnalysisSection ← analyze_chart: 护卫/优势相位/传光/逐题主星/偶然尊贵/Almuten/分布/气质)。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool(
        "chart",
        {"date": "1990-01-01", "time": "12:00", "zone": "+08:00", "lat": "31n14", "lon": "121e28"},
        save_result=False,
    )
    assert result.ok is True, result.error
    snapshot = result.data["snapshot_text"]
    assert "[古典]" in snapshot and "[古典格局]" in snapshot
    # [古典]: FakeClient 各曜带 sign 但无逐曜古典状态字段，故离线仅 身体部位(Melothesia) 恒在；
    # 逐曜古典状态/围攻/围绕 等富集内容由 live 测试 + catalog fixture 覆盖。
    assert "身体部位(Melothesia)" in snapshot
    # [古典格局]: 桩数据派生的逐键内容，逐条核对建造器输出形态。
    for marker in (
        "护卫：金 护卫 日",                 # doryphory
        "优势相位：火(牡羊) 凌驾 金(金牛)·四分",   # overcoming
        "度数围攻：水 被 火/土 度数围攻",        # besieging
        "传光：月 自 土 传光予 木",             # translation
        "聚光：土 聚 日、月 之光",              # collection
        "不合意：日 与 土 不合意",              # aversion
        "交点弯曲：月 交点弯曲（北弯）",          # bending
        "空亡：月 空亡（本座内不再成相）",        # void
        "阻止：火 阻止 金→木 入相",             # prohibition
        "挫败：金 挫败（木 先成相 土）",          # frustration
        "收回：水 收回（趋留撤离 日）",          # refranation
        "婚配（7宫·自然象征金）主星火",          # topicAlmuten
        "偶然尊贵",
        "土 12（角宫+5·行速+2·自由光+5）",      # accidentalDignity
        "Almuten 总主：土",                   # almutem
        "分布权重",
        "气质评估",
    ):
        assert marker in snapshot, marker
    export = result.data.get("export_snapshot") or {}
    detected = export.get("section_titles_detected") or []
    assert "古典" in detected and "古典格局" in detected
    assert export.get("unknown_detected_sections") == []


def test_liureng_headless_export_includes_courses_transmissions_without_mongodb_claims(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "liureng_gods",
        {
            "date": "2028-04-06",
            "time": "09:33:00",
            "zone": "+08:00",
            "lat": "31n13",
            "lon": "121e28",
            "gpsLat": 31.2167,
            "gpsLon": 121.4667,
            "after23NewDay": False,
        },
        query_text="请用大六壬分析这件事",
    )

    assert result.ok is True
    assert result.memory_ref is not None
    export_text = result.data["export_snapshot"]["export_text"]
    assert "四课" in result.data["export_snapshot"]["selected_sections"]
    assert "三传" in result.data["export_snapshot"]["selected_sections"]
    assert "一课：地盘=甲，天盘=申，贵神=青龙" in export_text
    assert "课式：涉害课" in export_text
    assert "MongoDB" not in export_text
    assert "7897" not in export_text
    liureng_call = next(payload for endpoint, payload in client.calls if endpoint == "/liureng/gods")
    assert "gpsLat" not in liureng_call
    assert "gpsLon" not in liureng_call
    chart_call = next(payload for endpoint, payload in client.calls if endpoint in {"/chart", "/"})
    assert chart_call["gpsLat"] == 31.2167
    assert chart_call["gpsLon"] == 121.4667

    template = service.report_template({"run_id": result.memory_ref.run_id, "tool_name": "liureng_gods"})
    brief_text = json.dumps(template["conversation_brief"], ensure_ascii=False)
    contract_text = json.dumps(template["targeted_analysis_contract"], ensure_ascii=False)
    assert "不要把空字段或缺失章节解释成需要 MongoDB" in brief_text
    assert "Never claim that Horosa Skill requires MongoDB" in contract_text


def test_service_memory_query_and_show(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    result = service.run_tool(
        "chart",
        {"date": "1990-01-01", "time": "12:00", "zone": "8", "lat": "31n14", "lon": "121e28", "name": "Horosa Smoke"},
    )

    assert result.memory_ref is not None
    query_result = service.query_memory({"tool": "chart", "entity": "Horosa Smoke", "limit": 5})
    assert query_result["ok"] is True
    assert query_result["count"] == 1
    assert query_result["results"][0]["run_id"] == result.memory_ref.run_id

    show_result = service.show_memory({"run_id": result.memory_ref.run_id})
    assert show_result["ok"] is True
    assert show_result["result"]["run_id"] == result.memory_ref.run_id

    text_query = service.query_memory({"text": "Horosa Smoke", "limit": 5})
    assert text_query["ok"] is True
    assert text_query["count"] == 1
    assert text_query["results"][0]["run_id"] == result.memory_ref.run_id


def test_local_tool_call_always_attaches_complete_export_contract(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "qimen",
        {"date": "2026-04-04", "time": "21:18", "zone": "+08:00", "lat": "31n14", "lon": "121e28"},
        save_result=False,
    )

    assert result.ok is True
    assert result.data["export_snapshot"]["technique"]["key"] == "qimen"
    assert result.data["export_snapshot"]["format_source"] == "snapshot_parser"
    # v13（上游 v3.9.x 重同步）：段序改为**逐字镜像上游** preset —— 八宫克应 回到上游位置（八宫详解 之后），
    # 末尾新增条件段 日家占方（古籍金函系）。段序不是装饰：selected_sections 决定导出正文的出段顺序。
    assert result.data["export_snapshot"]["selected_sections"] == [
        "起盘信息", "盘型", "全局速览", "盘面要素", "奇门演卦", "八宫详解", "八宫克应", "九宫方盘",
        "旺相休囚死·月令能量", "六害总览", "化解方案", "八门化气大阵", "用神分论", "财富七要", "事业七要",
        "恋爱姻缘", "孤辰寡宿", "日家占方（古籍金函系）",
    ]
    assert any(section["title"] == "奇门演卦" for section in result.data["export_snapshot"]["sections"])
    assert any(section["title"] == "化解方案" for section in result.data["export_snapshot"]["sections"])


def test_qimen_fails_loudly_when_ken_returns_failure_envelope(tmp_path) -> None:
    """Regression: ken endpoints return HTTP 200 with ``{"ResultCode": -1, "Result": "..."}`` on
    failure. Because that envelope is still a dict, ``_call_remote`` does not raise. It must NOT be
    forwarded to the JS layer (which would silently fall back to its local scaffold compute and
    produce a chart that does NOT match 星阙). ken is the sole compute authority, so a failed ken
    response has to surface as a loud ``tool.ken_compute_failed`` error. ``_require_ken_pan`` guards
    qimen/taiyi/jinkou identically; qimen exercises the path here."""

    class KenFailureClient(FakeClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            if endpoint == "/qimen/pan":
                return {"ResultCode": -1, "Result": "qimen calculation failed"}
            return super().call(endpoint, payload)

    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=KenFailureClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "qimen",
        {"date": "2026-04-04", "time": "21:18", "zone": "+08:00", "lat": "31n14", "lon": "121e28"},
        save_result=False,
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "tool.ken_compute_failed"
    assert result.error.details.get("engine") == "kinqimen"


def test_knowledge_registry_and_read_are_queryable_and_persisted(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    registry = service.run_tool("knowledge_registry", {"domain": "astro"}, save_result=False)
    assert registry.ok is True
    assert registry.data["domains"][0]["domain"] == "astro"
    assert any(category["name"] == "planet" for category in registry.data["domains"][0]["categories"])

    liureng = service.run_tool("knowledge_read", {"domain": "liureng", "category": "shen", "key": "子"}, save_result=True)
    assert liureng.ok is True
    assert liureng.memory_ref is not None
    assert liureng.data["title"] == "神后子神"
    assert "类象" in liureng.data["rendered_text"]

    qimen = service.run_tool("knowledge_read", {"domain": "qimen", "category": "door", "key": "休门"}, save_result=False)
    assert qimen.ok is True
    assert qimen.data["key"] == "休门"
    assert "休养" in qimen.data["rendered_text"]

    astro = service.run_tool(
        "knowledge_read",
        {"domain": "astro", "category": "aspect", "aspect_degree": 90, "object_a": "Sun", "object_b": "Jupiter"},
        save_result=False,
    )
    assert astro.ok is True
    assert astro.data["title"].startswith("太阳 - 木星")
    assert "相位角：90°" in astro.data["tips"]

    queried = store.query_runs(tool="knowledge_read", include_payload=True)
    assert len(queried) == 1
    payload = queried[0]["artifacts"][0]["payload"]
    assert payload["data"]["domain"] == "liureng"
    assert payload["data"]["category"] == "shen"


def test_knowledge_registry_bundle_has_expected_domains() -> None:
    registry = build_knowledge_registry()
    # v0.28.0：3 个 hover 域之外新增 21 个方法论手册域（helpdocs 自动发现）——断超集不断全集，
    # 手册域自己的契约在 tests/test_knowledge_helpdocs.py。
    domains = [item["domain"] for item in registry["domains"]]
    assert {"astro", "liureng", "qimen"} <= set(domains)
    assert len(domains) >= 24


def test_phase2_tools_attach_export_contracts(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    guolao = service.run_tool(
        "guolao_chart",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    hellen = service.run_tool(
        "hellen_chart",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    tongshe = service.run_tool("tongshefa", {}, save_result=False)
    sanshi = service.run_tool(
        "sanshiunited",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    suzhan = service.run_tool(
        "suzhan",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    germany = service.run_tool(
        "germany",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    otherbu = service.run_tool(
        "otherbu",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "question": "测试"},
        save_result=False,
    )
    firdaria = service.run_tool(
        "firdaria",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    decennials = service.run_tool(
        "decennials",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    sixyao = service.run_tool(
        "sixyao",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gua_code": "111111", "changed_code": "101010"},
        save_result=False,
    )

    assert guolao.ok is True
    assert guolao.data["export_snapshot"]["technique"]["key"] == "guolao"
    assert hellen.ok is True
    # 上游 v50 把这一族按出盘页面拆键（ASTRO_LIKE_EXPORT_KEYS）：希腊盘有自己的 `hellenastro`。
    assert hellen.data["export_snapshot"]["technique"]["key"] == "hellenastro"
    assert tongshe.ok is True
    assert tongshe.data["export_snapshot"]["technique"]["key"] == "tongshefa"
    assert sanshi.ok is True
    assert sanshi.data["export_snapshot"]["technique"]["key"] == "sanshiunited"
    assert suzhan.ok is True
    assert suzhan.data["export_snapshot"]["technique"]["key"] == "suzhan"
    assert germany.ok is True
    assert germany.data["export_snapshot"]["technique"]["key"] == "germany"
    assert otherbu.ok is True
    assert otherbu.data["export_snapshot"]["technique"]["key"] == "otherbu"
    assert firdaria.ok is True
    assert firdaria.data["export_snapshot"]["technique"]["key"] == "firdaria"
    assert decennials.ok is True
    assert decennials.data["export_snapshot"]["technique"]["key"] == "decennials"
    assert sixyao.ok is True
    assert sixyao.data["export_snapshot"]["technique"]["key"] == "sixyao"


def test_sixyao_time_based_gua_varies_with_time_and_is_deterministic() -> None:
    # 回归 #12: lines 空时曾写死返回 既济(101010)→益(100011)，与起卦时间无关。修复后按四柱干支 +
    # 时辰以时起卦 (梅花易数)：不同时间不同卦、恰一动爻、同输入确定一致、不再是写死的既济→益。
    from horosa_skill.service import _time_based_gua_lines, _derive_gua_code, _derive_changed_gua_code

    cases = [
        ({"yearGanZi": "癸卯", "monthGanZi": "甲子", "dayGanZi": "甲子"}, "00:00:00"),
        ({"yearGanZi": "甲辰", "monthGanZi": "庚午", "dayGanZi": "庚戌"}, "06:30:00"),
        ({"yearGanZi": "乙巳", "monthGanZi": "己卯", "dayGanZi": "戊子"}, "18:45:00"),
        ({"yearGanZi": "丙午", "monthGanZi": "甲午", "dayGanZi": "壬戌"}, "12:52:00"),
        ({"yearGanZi": "丙午", "monthGanZi": "庚子", "dayGanZi": "庚辰"}, "23:59:00"),
    ]
    combos = set()
    for nongli, t in cases:
        lines = _time_based_gua_lines(nongli, {"time": t})
        assert len(lines) == 6
        assert all(line["value"] in (0, 1) for line in lines)
        assert sum(1 for line in lines if line["change"]) == 1  # 以时起卦恰一个动爻
        combos.add((_derive_gua_code(lines), _derive_changed_gua_code(lines)))
    assert len(combos) >= 4, combos  # 不再固定单一卦象 (修复前为 1)
    assert ("101010", "100011") not in combos  # 写死的 既济→益 不再出现
    n = {"yearGanZi": "丙午", "monthGanZi": "甲午", "dayGanZi": "壬戌"}
    assert _derive_gua_code(_time_based_gua_lines(n, {"time": "12:52:00"})) == _derive_gua_code(
        _time_based_gua_lines(n, {"time": "12:52:00"})
    )


@pytest.mark.parametrize("tool_name", ["chart", "guolao_chart"])
def test_service_normalizes_human_friendly_birth_fields_before_remote_calls(tmp_path, tool_name: str) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        tool_name,
        {
            "date": "1995-06-03",
            "time": "5:30",
            "zone": "8",
            "lat": "31.2167",
            "lon": "121.4667",
            "ad": 1,
        },
        save_result=False,
    )

    assert result.ok is True
    assert result.input_normalized["zone"] == "+08:00"
    assert result.input_normalized["lat"] == "31n13"
    assert result.input_normalized["lon"] == "121e28"
    assert result.input_normalized["gpsLat"] == pytest.approx(31.2167)
    assert result.input_normalized["gpsLon"] == pytest.approx(121.4667)
    assert client.calls, "expected remote client call to be captured"
    endpoint, remote_payload = client.calls[0]
    assert endpoint == "/"
    assert result.input_normalized["date"] == "1995-06-03"
    assert remote_payload["date"] == "1995/06/03"
    assert remote_payload["zone"] == "+08:00"
    assert remote_payload["lat"] == "31n13"
    assert remote_payload["lon"] == "121e28"
    assert remote_payload["gpsLat"] == pytest.approx(31.2167)
    assert remote_payload["gpsLon"] == pytest.approx(121.4667)


def test_service_sends_slash_dates_to_python_chart_server_without_changing_input(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "chart",
        {
            "date": "2028/04/06",
            "time": "09:33",
            "zone": "+00:00",
            "lat": "41n26",
            "lon": "174w30",
            "gpsLat": -41.433333,
            "gpsLon": -174.5,
        },
        save_result=False,
    )

    assert result.ok is True
    assert result.input_normalized["date"] == "2028-04-06"
    chart_payloads = [call_payload for endpoint, call_payload in client.calls if endpoint == "/"]
    assert chart_payloads
    assert chart_payloads[0]["date"] == "2028/04/06"


def test_java_chart_payload_slashes_datetime_only_for_chart_family() -> None:
    chart_payload = _java_chart_payload(
        "/chart",
        {"date": "2028-04-06", "datetime": "2031-04-06 09:33:00", "time": "09:33:00"},
    )
    assert chart_payload["date"] == "2028/04/06"
    assert chart_payload["datetime"] == "2031/04/06 09:33:00"

    nongli_payload = _java_chart_payload("/nongli/time", {"date": "2028-04-06"})
    assert nongli_payload["date"] == "2028-04-06"


def test_java_chart_payload_candidates_cover_windows_runtime_variants() -> None:
    candidates = _java_chart_payload_candidates(
        "/chart",
        {
            "date": "2028-04-06",
            "time": "09:33:00",
            "zone": "+08:00",
            "lat": "41n26",
            "lon": "174w30",
            "gpsLat": -41.433333,
            "gpsLon": -174.5,
        },
    )

    assert {
        "date": "2028/04/06",
        "time": "09:33:00",
        "zone": "+08:00",
        "lat": "41n26",
        "lon": "174w30",
        "gpsLat": -41.433333,
        "gpsLon": -174.5,
    } in candidates
    assert {
        "date": "2028-04-06",
        "time": "09:33:00",
        "zone": "+08:00",
        "lat": "41n26",
        "lon": "174w30",
        "gpsLat": -41.433333,
        "gpsLon": -174.5,
    } in candidates
    assert {
        "date": "2028/04/06",
        "time": "09:33:00",
        "zone": "8",
        "lat": "41n26",
        "lon": "174w30",
        "gpsLat": -41.433333,
        "gpsLon": -174.5,
    } in candidates
    assert {
        "date": "2028/04/06",
        "time": "09:33:00",
        "zone": "+08:00",
        "lat": "41n26",
        "lon": "174w30",
        "gpsLat": -41.433333,
        "gpsLon": 174.5,
    } in candidates
    assert {
        "date": "2028-04-06",
        "time": "09:33:00",
        "zone": "8",
        "lat": "41n26",
        "lon": "174w30",
        "gpsLat": -41.433333,
        "gpsLon": 174.5,
    } in candidates
    assert {
        "date": "2028-04-06",
        "time": "09:33:00",
        "zone": "8",
        "lat": "41n26",
        "lon": "174w30",
    } in candidates
    assert {
        "date": "2028/04/06",
        "time": "09:33:00",
        "zone": "+08:00",
        "gpsLat": -41.433333,
        "gpsLon": -174.5,
    } in candidates
    assert {
        "date": "2028/04/06",
        "time": "09:33:00",
        "zone": "+08:00",
        "lat": -41.433333,
        "lon": -174.5,
        "gpsLat": -41.433333,
        "gpsLon": -174.5,
    } in candidates
    assert {
        "date": "2028/04/06",
        "time": "09:33:00",
        "zone": "+08:00",
        "lat": -41.433333,
        "lon": 174.5,
        "gpsLat": -41.433333,
        "gpsLon": 174.5,
    } in candidates


def test_calendar_month_snapshot_sections_and_cross_month_filter(tmp_path) -> None:
    # 黄历/万年历：起盘信息+当月月历(GFM 表)+选中日详情+方法说明；跨月补位项不入当月表。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "calendar_month",
        {"date": "2028-04-06", "zone": "+08:00", "lon": "120e00", "day": "2028-04-06", "agent_confirmed_settings": True},
        save_result=False,
    )

    assert result.ok is True
    snapshot = result.data["snapshot_text"]
    for head in ("[起盘信息]", "[当月月历]", "[选中日详情]", "[方法说明]"):
        assert head in snapshot
    assert "| 公历 | 星期 | 农历 | 日干支 | 节气/朔望 |" in snapshot
    assert "清明 2028-04-04 16:02:11" in snapshot
    assert "朔 12:20:33" in snapshot
    # 跨月补位（2028-05-01）不得混入当月月历表。
    assert "05-01" not in snapshot
    # 选中日详情字段落位。
    assert "农历：戊申年三月初六" in snapshot
    assert "年柱口径" in snapshot
    export_format = result.data.get("export_snapshot") or {}
    assert export_format.get("technique", {}).get("key") == "calendar"
    assert export_format.get("missing_selected_sections") in (None, [])
    assert export_format.get("unknown_sections") in (None, [])


def test_predictive_common_sections_appended_for_predictive_family(tmp_path) -> None:
    # 星运族公共段：当前时点(导出时刻+盘主年龄) + 方法说明(机理与读法) 在统一出口追加。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "profection",
        {
            "date": "1995-06-03",
            "time": "05:30:00",
            "zone": "+08:00",
            "lat": "31n13",
            "lon": "121e28",
            "datetime": "2026-07-12 12:00:00",
            "agent_confirmed_settings": True,
        },
        save_result=False,
    )

    assert result.ok is True
    snapshot = result.data["snapshot_text"]
    assert "[当前时点]" in snapshot and "[方法说明]" in snapshot
    assert "导出时刻：" in snapshot
    assert "盘主当前年龄：" in snapshot
    assert "小限(年限)" in snapshot
    # 非星运技法不受影响（零变化）。
    nongli = service.run_tool(
        "nongli_time",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lon": "121e28", "agent_confirmed_settings": True},
        save_result=False,
    )
    assert "[方法说明]" not in (nongli.data.get("snapshot_text") or "")


def test_nongli_payload_candidates_keep_validated_payload_first_then_legacy_slash_fallback() -> None:
    candidates = _java_chart_payload_candidates(
        "/nongli/time",
        {
            "date": "2028-04-06",
            "time": "09:03:00",
            "zone": "+08:00",
            "lat": "31n13",
            "lon": "121e28",
            "gpsLat": 31.2167,
            "gpsLon": 121.4667,
        },
    )

    assert candidates[0] == {
        "date": "2028-04-06",
        "time": "09:03:00",
        "zone": "+08:00",
        "lat": "31n13",
        "lon": "121e28",
        "gpsLat": 31.2167,
        "gpsLon": 121.4667,
    }
    assert {
        "date": "2028/04/06",
        "time": "09:03:00",
        "zone": "+08:00",
        "lat": "31n13",
        "lon": "121e28",
        "gpsLat": 31.2167,
        "gpsLon": 121.4667,
    } in candidates
    assert {
        "date": "2028/04/06",
        "time": "09:03:00",
        "zone": "8",
        "lat": "31n13",
        "lon": "121e28",
        "gpsLat": 31.2167,
        "gpsLon": 121.4667,
    } in candidates
    assert {
        "date": "2028/04/06",
        "time": "09:03:00",
        "zone": "+08:00",
        "gpsLat": 31.2167,
        "gpsLon": 121.4667,
    } in candidates


def test_service_retries_chart_payload_variants_after_backend_param_error(tmp_path) -> None:
    class RetryChartClient(FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[str, dict]] = []

        def call(self, endpoint: str, payload: dict) -> dict:
            self.calls.append((endpoint, dict(payload)))
            if endpoint == "/" and payload.get("zone") != "8":
                raise ToolTransportError(
                    "backend rejected payload",
                    code="transport.http_error",
                    details={"endpoint": endpoint, "status_code": 500, "body": '{"ResultCode":200001,"Result":"param error"}'},
                )
            return super().call(endpoint, payload)

    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = RetryChartClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "chart",
        {"date": "2026-04-04", "time": "15:58:35", "zone": "+08:00", "lat": "26n04", "lon": "119e19"},
        save_result=False,
    )

    assert result.ok is True
    assert result.input_normalized["zone"] == "+08:00"
    assert any(payload.get("zone") == "8" for endpoint, payload in client.calls if endpoint == "/")


def test_service_retries_nongli_time_legacy_payload_after_backend_param_error(tmp_path) -> None:
    class RetryNongliClient(FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[str, dict]] = []

        def call(self, endpoint: str, payload: dict) -> dict:
            self.calls.append((endpoint, dict(payload)))
            if endpoint == "/nongli/time" and "/" not in str(payload.get("date", "")):
                raise ToolTransportError(
                    "backend rejected payload",
                    code="transport.http_error",
                    details={
                        "endpoint": endpoint,
                        "status_code": 500,
                        "body": '{"ResultCode":200001,"Result":"param error Index 1 out of bounds for length 1"}',
                    },
                )
            return super().call(endpoint, payload)

    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = RetryNongliClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "qimen",
        {
            "date": "2028/4/6",
            "time": "9:3",
            "zone": "8",
            "lat": "31.2167",
            "lon": "121.4667",
            "ad": 1,
        },
        save_result=False,
    )

    assert result.ok is True
    nongli_calls = [call_payload for endpoint, call_payload in client.calls if endpoint == "/nongli/time"]
    assert nongli_calls[0]["date"] == "2028-04-06"
    assert any(call_payload["date"] == "2028/04/06" for call_payload in nongli_calls)


def test_sanshiunited_subresults_use_compact_export_contracts(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool("sanshiunited", build_sample_payloads()["sanshiunited"], save_result=False)

    assert result.ok is True
    subresults = result.data["subresults"]
    assert sorted(subresults) == ["liureng_gods", "qimen", "taiyi"]
    for subresult in subresults.values():
        assert "data" not in subresult
        assert "export_snapshot" not in subresult
        assert "export_format" not in subresult
        assert subresult["export_contract"]["has_export_snapshot"] is True
        assert subresult["export_contract"]["has_export_snapshot"] is True
        assert subresult["export_contract"]["section_titles"]


@pytest.mark.parametrize("tool_name", ["nongli_time", "qimen", "sixyao"])
def test_service_normalizes_single_digit_nongli_dates_before_remote_calls(tmp_path, tool_name: str) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())

    payload = {
        "date": "2028/4/6",
        "time": "9:3",
        "zone": "8",
        "lat": "31.2167",
        "lon": "121.4667",
        "ad": 1,
    }
    if tool_name == "sixyao":
        payload["question"] = "测试六爻输出"

    result = service.run_tool(tool_name, payload, save_result=False)

    assert result.ok is True
    assert result.input_normalized["date"] == "2028-04-06"
    assert result.input_normalized["time"] == "09:03:00"
    assert result.input_normalized["zone"] == "+08:00"
    assert result.input_normalized["lat"] == "31n13"
    assert result.input_normalized["lon"] == "121e28"

    nongli_calls = [call_payload for endpoint, call_payload in client.calls if endpoint == "/nongli/time"]
    assert nongli_calls, "expected /nongli/time to be called with normalized values"
    assert nongli_calls[0]["date"] == "2028-04-06"
    assert nongli_calls[0]["time"] == "09:03:00"
    assert nongli_calls[0]["zone"] == "+08:00"
    assert nongli_calls[0]["lat"] == "31n13"
    assert nongli_calls[0]["lon"] == "121e28"


def test_service_normalizes_iana_zone_before_nongli_remote_calls(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "qimen",
        {
            "date": "2026-05-18",
            "time": "13:14",
            "zone": "America/Los_Angeles",
            "lat": "34.0522",
            "lon": "-118.2437",
            "ad": 1,
        },
        save_result=False,
    )

    assert result.ok is True
    assert result.input_normalized["zone"] == "-07:00"
    nongli_calls = [call_payload for endpoint, call_payload in client.calls if endpoint == "/nongli/time"]
    assert nongli_calls, "expected /nongli/time to be called with normalized IANA timezone"
    assert nongli_calls[0]["zone"] == "-07:00"


def test_all_callable_techniques_keep_non_empty_structured_export_contracts(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()

    assert sorted(payloads) == sorted(TOOL_DEFINITIONS)

    for tool_name, technique_key in TOOL_EXPORT_TECHNIQUE_MAP.items():
        result = service.run_tool(tool_name, payloads[tool_name], save_result=False)
        assert result.ok is True, tool_name
        assert result.data["export_snapshot"]["technique"]["key"] == technique_key, tool_name
        assert result.data["export_snapshot"]["format_source"] == "snapshot_parser", tool_name
        assert result.data["export_snapshot"]["selected_sections"], tool_name
        assert result.data["export_snapshot"]["sections"], tool_name
        assert all(section["title"] for section in result.data["export_snapshot"]["sections"]), tool_name


def test_predictive_tools_export_real_natal_and_timed_chart_content(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()

    # 上游 v50 的推运族段结构：[本命盘配置]/[起盘信息]/[时段盘配置]/[相位]（不再带
    # 本命盘/返照盘/推运盘/流年盘 前缀；旧名走 map_legacy_section_title 迁移）。
    expected_sections = {
        "solarreturn": ["本命盘配置", "时段盘配置", "相位"],
        "lunarreturn": ["本命盘配置", "时段盘配置", "相位"],
        "givenyear": ["本命盘配置", "时段盘配置", "相位"],
        "solararc": ["本命盘配置", "时段盘配置", "相位"],
        "profection": ["本命盘配置", "时段盘配置", "相位"],
    }
    for tool_name, sections in expected_sections.items():
        result = service.run_tool(tool_name, payloads[tool_name], save_result=False)
        export_format = result.data["export_snapshot"]
        text = result.data["snapshot_text"]
        assert all(section in export_format["selected_sections"] for section in sections), tool_name
        assert "本命盘配置" in text, tool_name
        # 时段盘的两个子块标题（上游 buildDirectedChartLines 的排版）。
        assert "时段盘 星与虚点" in text, tool_name
        assert "日 (" in text and "月 (" in text, tool_name
        # 推运族的 [X盘相位] 是**交叉相位**（行运星 ↔ 本命星），不是本命盘那三个子标题。
        # 旧断言查 "标准相位" 恰恰是在断言那个 bug 的产物：真机上该段只有三个空子标题、
        # 零条相位，而桩在顶层塞了本命形状的 aspects 才让它显得成立。
        assert "行运" in text and "与 本命" in text, tool_name
        assert "标准相位" not in text, tool_name


def test_primary_direction_exports_tables_and_pdchart_positions(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()

    pd_result = service.run_tool("pd", payloads["pd"], save_result=False)
    pd_text = pd_result.data["snapshot_text"]
    assert "主限法表格" in pd_text  # 上游 v48 段名对齐（旧名 主/界限法表格 → 主限法表格）
    assert "| Arc | 迫星 | 应星 | 类型 | 日期 |" in pd_text
    assert "推运月" in pd_text
    assert "本命土" in pd_text
    assert "2031-04-06" in pd_text

    pdchart_result = service.run_tool("pdchart", payloads["pdchart"], save_result=False)
    pdchart_text = pdchart_result.data["snapshot_text"]
    assert "本命盘星与虚点" in pdchart_text
    assert "主限法盘星体表格" in pdchart_text
    assert "| 星体/虚点 | 位置 | 宫位 | 速度 |" in pdchart_text
    assert "主限法盘相位" in pdchart_text


def test_primary_direction_full_house_settings_surface(tmp_path) -> None:
    # 主限法 v12 (星阙 v2.6.6)：核5方位法 + In Mundo + 仅逆向 + 映点 + 界 + 新时间钥匙 全部出现在设置段。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()
    payload = {
        **payloads["pd"],
        "pdMethod": "meridian",
        "pdtype": 1,
        "pdDirect": 0,
        "pdConverse": 1,
        "pdAntiscia": 1,
        "pdTerms": 1,
        "pdTimeKey": "Kundig",
    }
    text = service.run_tool("pd", payload, save_result=False).data["snapshot_text"]
    assert "Meridian" in text
    assert "In Mundo（世俗）" in text
    assert "仅逆向 (converse)" in text
    assert "Kündig" in text
    assert "映点(antiscia)作迫星：是" in text
    assert "界(terms)作迫星：是" in text


def test_primary_direction_core5_method_labels() -> None:
    # 主限法 v12 核5：每个公开方位法都有专属标签；未核验旧键（placidus 等）不再有标签（后端会回退 core_alchabitius）。
    from horosa_skill.service import _primary_direction_method_text, _primary_direction_time_key_text

    assert _primary_direction_method_text("core_alchabitius") == "Alcabitius 半弧法"
    assert _primary_direction_method_text("meridian") == "Meridian"
    assert _primary_direction_method_text("porphyry") == "Porphyry"
    assert _primary_direction_method_text("equal_ecliptic") == "Equal（黄道）"
    assert _primary_direction_method_text("equal_hour_circle") == "Equal（时圈）"
    assert _primary_direction_method_text("horosa_legacy") == "传统赤经法"
    # 移除的未核验方位法：params 回显是原样输入，标签如实标注引擎回退（行集等同 core，live 测试钉死）。
    assert _primary_direction_method_text("placidus") == "placidus（未核验，引擎回退 Alcabitius 半弧法）"
    # 时间钥匙 22 项全部有标签（上游下拉一致）。
    for key in (
        "Ptolemy", "Naibod", "TrueSolarArc", "SymbolicSolarArc", "Cardano", "Umar", "Wollner",
        "Plantiko", "Simmonite", "SynodicYear", "Kepler", "Brahe", "Kundig", "SymbolicDegree",
        "SymbolicYear", "SymbolicMoon", "SymbolicMonth", "Quarterly", "Quinary", "Duodenary",
        "Novenary", "SelfMeasure",
    ):
        label = _primary_direction_time_key_text(key)
        assert label and label != "无", key


def test_germany_uranian_snapshot_has_full_sections(tmp_path) -> None:
    # 中点盘 Uranian (星阙 v2.5.2)：10 段含 行星/TNP星体/90°中点盘/行星图/映点/中点列表。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool(
        "germany",
        {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    text = result.data["snapshot_text"]
    for header in ("行星", "TNP星体", "90°中点盘", "行星图", "映点", "中点列表"):
        assert header in text, header
    assert "Cupido" in text or "Hades" in text  # TNP 渲染


def test_uranian_dial_math_matches_upstream() -> None:
    # 移植自 星阙 utils/uranianDial.js 的纯函数校验。
    from horosa_skill.service import _dial_antiscion, _dial_mid, _dial_planetary_pictures, _dial_sep

    assert abs(_dial_antiscion(15.0) - 165.0) < 1e-9  # 15°白羊 回照 → 165
    assert abs(_dial_mid(10.0, 20.0) - 15.0) < 1e-9
    assert abs(_dial_mid(350.0, 10.0) - 0.0) < 1e-9  # 跨 0° 近中点 = 0，非 180
    pts = [
        {"id": "Sun", "lon": 0.0},
        {"id": "Moon", "lon": 90.0},
        {"id": "Asc", "lon": 0.0},
        {"id": "MC", "lon": 90.0},
    ]
    pics = _dial_planetary_pictures(pts, 90.0, 1.0)
    assert pics, "Sun+Moon−Asc=MC 应命中一张行星图"


def test_guolao_limit_table_matches_upstream_algorithm() -> None:
    # 七政四余·大限：移植自 星阙 GuoLaoMoiraWheel.buildGuolaoLimitTable（JS Math.round half-up）。
    from horosa_skill.service import _guolao_limit_table

    rows = _guolao_limit_table(0.0, 2000)
    assert len(rows) == 12
    assert rows[0] == {"index": 1, "palace": "命宫", "years": 9.0, "from_age": 1, "to_age": 9, "from_year": 2000, "to_year": 2008}
    assert rows[1]["palace"] == "财帛" and (rows[1]["from_age"], rows[1]["to_age"]) == (10, 19)
    assert rows[3]["palace"] == "田宅" and rows[3]["years"] == 15.0
    # 首限年数随命度入宫度变化：life=15° → 9 + 15/3 = 14。
    assert _guolao_limit_table(15.0, 2000)[0]["to_age"] == 14


def test_guolao_snapshot_has_limit_and_aspect_sections(tmp_path) -> None:
    # 七政四余 大限 + 相位 段（星阙 v2.5.x Moira 还原度）。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool(
        "guolao_chart",
        {"date": "1998/03/02", "time": "08:18:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
        save_result=False,
    )
    text = result.data["snapshot_text"]
    assert "大限" in text
    assert "第1限 命宫" in text
    assert "相位" in text


def test_zodiacal_release_exports_timeline_rows(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()

    result = service.run_tool("zr", payloads["zr"], save_result=False)
    text = result.data["snapshot_text"]
    assert "本命盘星与虚点" in text
    assert "基于X点推运" in text
    assert "L1：牡羊" in text
    assert "L2：金牛" in text


def test_all_callable_techniques_keep_clean_contracts_across_repeated_saved_runs(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())
    payloads = build_sample_payloads()

    for tool_name, technique_key in TOOL_EXPORT_TECHNIQUE_MAP.items():
        service.run_tool(tool_name, payloads[tool_name], save_result=True)
        service.run_tool(tool_name, payloads[tool_name], save_result=True)

        queried = store.query_runs(tool=tool_name, include_payload=True, limit=5)
        assert len(queried) >= 2, tool_name

        for run in queried[:2]:
            artifact_payload = run["artifacts"][0]["payload"]
            export_snapshot = artifact_payload["data"]["export_snapshot"]
            export_format = artifact_payload["data"]["export_snapshot"]
            assert artifact_payload["ok"] is True, tool_name
            assert export_snapshot["technique"]["key"] == technique_key, tool_name
            assert export_snapshot["format_source"] == "snapshot_parser", tool_name
            assert export_format["selected_sections"], tool_name
            assert export_format["sections"], tool_name
            assert all(section["title"] for section in export_format["sections"]), tool_name


def test_all_callable_techniques_can_generate_report_json_artifacts(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())
    payloads = build_sample_payloads()

    for tool_name, technique_key in TOOL_EXPORT_TECHNIQUE_MAP.items():
        result = service.run_tool(tool_name, payloads[tool_name], save_result=True, query_text=f"生成 {tool_name} 报告")
        assert result.memory_ref is not None, tool_name
        template = service.report_template({"run_id": result.memory_ref.run_id, "tool_name": tool_name})
        assert template["schema"] == "horosa.skill.report.template.v1", tool_name
        assert template["technique"] == technique_key, tool_name
        assert template["source_export_sections"], tool_name
        assert template["coverage_contract"]["all_source_export_sections_required"] is True, tool_name
        assert template["coverage_contract"]["source_export_section_count"] == len(template["source_export_sections"]), tool_name
        assert template["source_context"]["export_text"], tool_name
        assert template["source_context"]["export_sections"], tool_name
        assert all(section["body"] for section in template["source_context"]["export_sections"]), tool_name
        assert template["targeted_analysis_contract"]["answer_priority"] == "directly_answer_user_question_first", tool_name
        assert template["question_analysis"]["has_question"] is True, tool_name
        assert template["targeted_analysis_contract"]["question_analysis"]["raw_question"] == f"生成 {tool_name} 报告", tool_name
        assert template["targeted_analysis_contract"]["answer_plan"], tool_name
        assert template["targeted_analysis_contract"]["targeted_answer_requirements"], tool_name
        assert template["ai_fillable"]["targeted_answer_requirements"], tool_name
        assert template["ai_fillable"]["answer_plan"], tool_name
        assert template["ai_fillable"]["analysis_focus"] == f"生成 {tool_name} 报告", tool_name
        assert template["conversation_brief"]["role"].startswith("你是接入 Horosa Skill 的 AI 解盘助手"), tool_name
        assert "像在 AI 对话窗口中完成一次认真解盘" in "\n".join(template["conversation_brief"]["output_style"]), tool_name
        assert "answer_text" in template["ai_fillable"], tool_name
        assert "direct_answer" in template["ai_fillable"], tool_name

        ai_sections = [
            {
                "title": section["title"],
                "body": f"解释 {section['title']}",
                "evidence_lines": [section["title"]],
                "relevance_to_question": "用于回答用户问题。",
            }
            for section in template["source_export_sections"]
        ]
        rendered = service.report_render(
            {
                "run_id": result.memory_ref.run_id,
                "tool_name": tool_name,
                "format": "json",
                "ai_report": {
                    "analysis_focus": f"生成 {tool_name} 报告",
                    "direct_answer": "已根据用户问题完成针对性分析。",
                    "executive_summary": "报告摘要。",
                    "analysis_sections": ai_sections,
                    "evidence": [{"source": tool_name, "line": "测试证据"}],
                    "recommendations": ["保留报告。"],
                    "limitations": [],
                },
            }
        )
        path = Path(rendered["artifact_path"])
        assert rendered["ok"] is True, tool_name
        assert path.is_file(), tool_name
        assert rendered["file_size"] > 100, tool_name
        report_payload = json.loads(path.read_text(encoding="utf-8"))
        assert report_payload["schema"] == "horosa.skill.report.v1", tool_name
        assert report_payload["source"]["tool_name"] == tool_name, tool_name
        assert report_payload["source"]["technique"] == technique_key, tool_name
        assert report_payload["sections"], tool_name
        assert report_payload["coverage"]["all_source_export_sections_required"] is True, tool_name
        assert report_payload["coverage"]["must_explain_sections"] == [
            section["title"] for section in template["source_export_sections"]
        ], tool_name
        assert report_payload["targeted_analysis_contract"]["user_question"] == f"生成 {tool_name} 报告", tool_name
        assert report_payload["question_analysis"]["has_question"] is True, tool_name
        assert report_payload["report_index"]["question_analysis"]["raw_question"] == f"生成 {tool_name} 报告", tool_name
        assert report_payload["report_index"]["answer_plan"], tool_name
        assert report_payload["report_index"]["targeted_answer_requirements"], tool_name
        assert report_payload["targeted_analysis_contract"]["targeted_answer_requirements"], tool_name
        assert report_payload["report_index"]["analysis_focus"] == f"生成 {tool_name} 报告", tool_name
        assert report_payload["report_index"]["coverage_status"] == "complete", tool_name
        assert report_payload["report_index"]["ready_to_deliver"] is True, tool_name
        assert report_payload["report_index"]["delivery_missing"] == [], tool_name
        assert report_payload["report_index"]["delivery_checks"]["has_targeted_requirements"] is True, tool_name
        assert report_payload["ai_coverage_status"]["missing_sections"] == [], tool_name
        assert report_payload["ai_coverage_status"]["has_direct_answer"] is True, tool_name
        assert report_payload["ai_coverage_status"]["has_evidence"] is True, tool_name
        assert report_payload["section_coverage_matrix"]["all_sections_covered"] is True, tool_name
        assert report_payload["section_coverage_matrix"]["missing_section_titles"] == [], tool_name
        assert report_payload["section_coverage_matrix"]["source_section_count"] == len(template["source_export_sections"]), tool_name
        assert report_payload["content_outline"], tool_name
        assert len(report_payload["content_outline"]) == len(report_payload["sections"]), tool_name
        assert report_payload["content_outline"][0]["title"] == "报告元信息", tool_name
        assert report_payload["sections"][0]["id"] == "report_metadata", tool_name
        assert "逐章解释覆盖矩阵" in report_payload["plain_text"], tool_name
        assert "报告元信息" in report_payload["plain_text"], tool_name
        assert result.memory_ref.run_id in report_payload["plain_text"], tool_name
        assert tool_name in report_payload["plain_text"], tool_name
        assert "星阙 AI 导出正文" in report_payload["plain_text"], tool_name
        assert template["source_export_sections"][0]["title"] in report_payload["plain_text"], tool_name
        assert report_payload["search_index"]["schema"] == "horosa.skill.report.search_index.v1", tool_name
        assert report_payload["search_index"]["tool_name"] == tool_name, tool_name
        assert report_payload["search_index"]["technique"] == technique_key, tool_name
        assert f"生成 {tool_name} 报告" in report_payload["search_index"]["keywords"], tool_name
        assert template["source_export_sections"][0]["title"] in report_payload["search_index"]["section_titles"], tool_name
        assert "逐章解释覆盖矩阵" in report_payload["search_index"]["search_text"], tool_name
        assert "交付检查清单" in report_payload["search_index"]["search_text"], tool_name
        assert report_payload["report_quality"]["source_complete"] is True, tool_name
        assert report_payload["report_quality"]["ai_analysis_complete"] is True, tool_name
        assert report_payload["report_quality"]["ready_for_human_reading"] is True, tool_name
        assert report_payload["delivery_checklist"]["schema"] == "horosa.skill.report.delivery_checklist.v1", tool_name
        assert report_payload["delivery_checklist"]["ready_to_deliver"] is True, tool_name
        assert report_payload["delivery_checklist"]["missing"] == [], tool_name
        assert report_payload["delivery_checklist"]["checks"]["source_sections_covered"] is True, tool_name
        assert report_payload["delivery_checklist"]["checks"]["has_targeted_requirements"] is True, tool_name
        assert report_payload["delivery_checklist"]["checks"]["has_search_index"] is True, tool_name
        section_ids = {section["id"] for section in report_payload["sections"]}
        assert {
            "report_metadata",
            "report_quality",
            "delivery_checklist",
            "coverage_contract",
            "section_coverage_matrix",
            "targeted_analysis_contract",
            "question_analysis",
            "ai_interpretation",
            "recommendations_limitations",
            "xingque_export_text",
            "provenance",
        }.issubset(section_ids), tool_name
        queried = store.query_runs(run_id=result.memory_ref.run_id, include_payload=True)
        assert "report_json" in {artifact["kind"] for artifact in queried[0]["artifacts"]}, tool_name
        report_artifact = next(artifact for artifact in queried[0]["artifacts"] if artifact["kind"] == "report_json")
        assert report_artifact["exists"] is True, tool_name
        assert report_artifact["file_size"] > 100, tool_name
        assert report_artifact["sha256"], tool_name
        assert report_artifact["payload"]["report_index"]["tool_name"] == tool_name, tool_name
        assert report_artifact["payload"]["report_index"]["storage"]["managed_by"] == "horosa_skill.memory", tool_name
        assert report_artifact["payload"]["report_index"]["ready_to_deliver"] is True, tool_name
        assert report_artifact["payload"]["report_index"]["delivery_missing"] == [], tool_name


def test_all_callable_techniques_can_generate_human_readable_pdf_and_docx(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())
    payloads = build_sample_payloads()
    bad_terms = ["待 AI", "AI 后续应", "这份报告已把"]

    for tool_name in TOOL_EXPORT_TECHNIQUE_MAP:
        question = f"请针对这个人的事业、财务和决策风险生成可直接阅读的 {tool_name} 咨询报告。"
        result = service.run_tool(tool_name, payloads[tool_name], save_result=True, query_text=question)
        assert result.memory_ref is not None, tool_name

        rendered_json = service.report_render(
            {
                "run_id": result.memory_ref.run_id,
                "tool_name": tool_name,
                "format": "json",
                "ai_report": sample_final_ai_report(question),
            }
        )
        report_payload = json.loads(Path(rendered_json["artifact_path"]).read_text(encoding="utf-8"))
        assert report_payload["report_quality"]["ready_for_human_reading"] is True, tool_name
        assert report_payload["delivery_checklist"]["ready_to_deliver"] is True, tool_name
        assert report_payload["delivery_checklist"]["missing"] == [], tool_name
        assert report_payload["ai_report"]["direct_answer"], tool_name
        assert report_payload["ai_report"]["consultation_basis"], tool_name
        assert report_payload["ai_report"]["reading_steps"], tool_name
        assert report_payload["ai_report"]["analysis_sections"], tool_name
        assert not any(term in report_payload["plain_text"] for term in bad_terms), tool_name

        rendered_pdf = service.report_render(
            {"run_id": result.memory_ref.run_id, "tool_name": tool_name, "format": "pdf"}
        )
        rendered_docx = service.report_render(
            {"run_id": result.memory_ref.run_id, "tool_name": tool_name, "format": "docx"}
        )
        pdf_path = Path(rendered_pdf["artifact_path"])
        docx_path = Path(rendered_docx["artifact_path"])
        assert pdf_path.read_bytes().startswith(b"%PDF"), tool_name
        assert docx_path.read_bytes().startswith(b"PK"), tool_name
        assert rendered_pdf["file_size"] > 500, tool_name
        assert rendered_docx["file_size"] > 5000, tool_name
        with zipfile.ZipFile(docx_path) as archive:
            docx_text = re.sub("<[^>]+>", "", archive.read("word/document.xml").decode("utf-8"))
        assert "起盘依据" in docx_text, tool_name
        assert "解盘步骤" in docx_text, tool_name
        assert not any(term in docx_text for term in ["Run ID", "来源追溯", "report_metadata", "Horosa Skill"]), tool_name
        if tool_name in {"bazi_birth", "bazi_direct"}:
            assert "大运流年与阶段判断" in docx_text, tool_name


def test_all_callable_techniques_without_question_generate_overall_reading_docx(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())
    payloads = build_sample_payloads()

    for tool_name in TOOL_EXPORT_TECHNIQUE_MAP:
        result = service.run_tool(tool_name, payloads[tool_name], save_result=True)
        assert result.memory_ref is not None, tool_name
        rendered = service.report_render(
            {
                "run_id": result.memory_ref.run_id,
                "tool_name": tool_name,
                "format": "docx",
                "ai_report": sample_final_ai_report("整体综合解盘"),
            }
        )
        with zipfile.ZipFile(Path(rendered["artifact_path"])) as archive:
            docx_text = re.sub("<[^>]+>", "", archive.read("word/document.xml").decode("utf-8"))
        assert "解读目标" in docx_text, tool_name
        assert "综合命局咨询" in docx_text or "整体综合解盘" in docx_text, tool_name
        assert "解读目标无" not in docx_text, tool_name
        assert "起盘依据" in docx_text, tool_name
        assert "解盘步骤" in docx_text, tool_name
        assert "核心结论" in docx_text, tool_name
        assert not any(term in docx_text for term in ["Run ID", "来源追溯", "report_metadata", "Horosa Skill"]), tool_name


def test_bazi_report_promotes_liunian_output_into_human_reading(tmp_path) -> None:
    class BaziFlowClient(FakeClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            def column(ganzi: str) -> dict:
                return {"ganzi": ganzi, "stem": {"name": ganzi[0]}, "branch": {"name": ganzi[1]}}

            return {
                "bazi": {
                    "nongli": {"birth": "1995-06-03 05:18:42"},
                    "fourColumns": {
                        "year": column("乙亥"),
                        "month": column("辛巳"),
                        "day": column("乙卯"),
                        "time": column("己卯"),
                    },
                    "mainDirection": [
                        {"year": 2019, "ganzi": "甲申"},
                        {"year": 2029, "ganzi": "乙酉"},
                    ],
                    "direction": [
                        {
                            "mainDirect": {"ganzi": "甲申"},
                            "startYear": 2019,
                            "subDirect": [
                                {"date": "2026", "ganzi": "丙午"},
                                {"date": "2027", "ganzi": "丁未"},
                                {"date": "2028", "ganzi": "戊申"},
                            ],
                        }
                    ],
                }
            }

    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=BaziFlowClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool(
        "bazi_birth",
        {
            "date": "1995-06-03",
            "time": "05:30:00",
            "zone": "+08:00",
            "lat": "31n13",
            "lon": "121e28",
            "gender": True,
            "timeAlg": 0,
        },
        save_result=True,
        query_text="这个人未来三年事业和财务风险如何？",
    )

    rendered = service.report_render(
        {
            "run_id": result.memory_ref.run_id,
            "tool_name": "bazi_birth",
            "format": "docx",
            "ai_report": sample_final_ai_report("这个人未来三年事业和财务风险如何？"),
        }
    )
    with zipfile.ZipFile(Path(rendered["artifact_path"])) as archive:
        docx_text = re.sub("<[^>]+>", "", archive.read("word/document.xml").decode("utf-8"))
    assert "大运流年与阶段判断" in docx_text
    assert "2026" in docx_text
    assert "2027" in docx_text
    assert "2028" in docx_text
    assert "事业判断上" in docx_text
    assert "财务判断上" in docx_text


def test_all_callable_techniques_final_export_text_matches_max_section_contract(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()

    for tool_name, technique_key in TOOL_EXPORT_TECHNIQUE_MAP.items():
        result = service.run_tool(tool_name, payloads[tool_name], save_result=False)
        export_text = result.data["export_snapshot"]["export_text"]
        reparsed = parse_export_content(technique=technique_key, content=export_text)
        assert reparsed["missing_selected_sections"] == [], tool_name
        assert reparsed["unknown_detected_sections"] == [], tool_name


def test_all_callable_techniques_do_not_emit_bare_empty_or_dependency_hallucination_sections(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()
    forbidden_claim_terms = [
        "MongoDB",
        "7897",
        "星阙桌面",
        "桌面应用",
        "远程数据库",
        "外部数据库",
        "外部服务",
        "无法输出",
        "需要安装",
    ]

    for tool_name in TOOL_EXPORT_TECHNIQUE_MAP:
        result = service.run_tool(tool_name, payloads[tool_name], save_result=False, query_text=f"审计 {tool_name}")
        export_snapshot = result.data["export_snapshot"]
        export_text = export_snapshot["export_text"]
        assert not any(term in export_text for term in forbidden_claim_terms), tool_name
        # 段名一致性闸：任何工具 emit 的段名必须能被契约认领（preset/可选段/legacy 映射之一），
        # unknown 非空 = builder 段名与 registry 拼写漂移，立即红。
        assert export_snapshot.get("unknown_detected_sections") == [], (
            f"{tool_name}: unknown sections {export_snapshot.get('unknown_detected_sections')}"
        )
        for section in export_snapshot["sections"]:
            body = section.get("body", "").strip()
            assert body and body != "无", f"{tool_name}:{section.get('title')}"
            if "未返回" in body:
                assert "不能臆造" in body, f"{tool_name}:{section.get('title')}"


def test_dispatch_exposes_child_export_contracts_explicitly(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    result = service.dispatch(
        {
            "query": "请用奇门和六壬综合分析",
            "birth": {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
            "save_result": True,
        }
    )

    assert result.ok is True
    assert "qimen" in result.result_export_contracts
    assert "liureng_gods" in result.result_export_contracts
    qimen_contract = result.result_export_contracts["qimen"]
    liureng_contract = result.result_export_contracts["liureng_gods"]
    assert qimen_contract["has_export_snapshot"] is True
    assert qimen_contract["has_export_snapshot"] is True
    assert qimen_contract["technique"]["key"] == "qimen"
    assert "奇门演卦" in qimen_contract["selected_sections"]
    assert liureng_contract["has_export_snapshot"] is True
    assert liureng_contract["has_export_snapshot"] is True
    assert liureng_contract["technique"]["key"] == "liureng"
    queried = store.query_runs(tool="liureng_gods", include_payload=True)
    assert queried
    assert sorted(result.selected_tools) == sorted(result.result_export_contracts)
    for tool_name, contract in result.result_export_contracts.items():
        assert contract["tool"] == tool_name
        assert contract["selected_sections"]
        # dispatch 轻契约：快照本体在 results[tool].data，contract 只带元信息。
        assert contract["technique"]["key"] == TOOL_EXPORT_TECHNIQUE_MAP[tool_name]
        assert "export_snapshot" not in contract and "snapshot_text" not in contract
        assert contract["section_titles"]


def test_service_can_attach_ai_answer_to_existing_run(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    result = service.dispatch(
        {
            "query": "请用奇门分析事业",
            "birth": {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
            "save_result": True,
        }
    )

    assert result.memory_ref is not None
    updated = service.record_ai_answer(
        {
            "run_id": result.memory_ref.run_id,
            "user_question": "我接下来事业走势如何？",
            "ai_answer": "先稳后升，宜先整理资源再扩张。",
            "ai_answer_structured": {"trend": "up_later"},
            "answer_meta": {"source": "assistant"},
        }
    )

    assert updated["ok"] is True
    queried = store.query_runs(text="我接下来事业走势如何", include_payload=True)
    assert queried
    assert queried[0]["run_id"] == result.memory_ref.run_id
    by_tool = store.query_runs(tool="qimen", include_payload=True)
    assert by_tool
    assert by_tool[0]["ai_answer_text"] == "先稳后升，宜先整理资源再扩张。"
    assert by_tool[0]["artifacts"][0]["payload"]["conversation"]["ai_answer_structured"] == {"trend": "up_later"}


def test_service_can_build_report_template_and_render_json_docx_pdf(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    result = service.run_tool(
        "chart",
        {"date": "2026-04-04", "time": "15:58:35", "zone": "8", "lat": "26n04", "lon": "119e19"},
        save_result=True,
        query_text="请生成当前星盘报告",
    )
    assert result.memory_ref is not None
    service.record_ai_answer(
        {
            "run_id": result.memory_ref.run_id,
            "ai_answer": "这是一份结构化报告测试回答。",
            "ai_answer_structured": {
                "executive_summary": "星盘报告摘要。",
                "analysis_focus": "检查后天宫位",
                "direct_answer": "后天宫位信息可以被报告引用。",
                "analysis_sections": [{"title": "起盘信息", "body": "后天宫位与星体信息齐全。", "evidence_lines": ["宫位宫头"]}],
                "evidence": [{"source_section_title": "宫位宫头", "source_line": "第八宫 宫头"}],
                "recommendations": ["保留完整导出正文。"],
                "limitations": ["测试环境不代表真实解读。"],
            },
        }
    )

    template = service.report_template({"run_id": result.memory_ref.run_id, "tool_name": "chart"})
    assert template["schema"] == "horosa.skill.report.template.v1"
    assert template["tool_name"] == "chart"
    assert template["technique"] == "astrochart"
    assert template["source_export_sections"]
    assert template["source_context"]["export_sections"][0]["body"]
    assert template["coverage_contract"]["must_explain_sections"]
    assert template["targeted_analysis_contract"]["required_ai_fields"]
    assert template["question_analysis"]["focus_domains"] == ["general_reading"]
    assert template["targeted_analysis_contract"]["answer_plan"]
    assert template["ai_fillable"]["direct_answer"] == ""
    service.record_ai_answer(
        {
            "run_id": result.memory_ref.run_id,
            "ai_answer": "这是一份覆盖全部星盘导出章节的结构化报告测试回答。",
            "ai_answer_structured": {
                "executive_summary": "星盘报告摘要。",
                "analysis_focus": "检查后天宫位",
                "direct_answer": "后天宫位信息可以被报告引用。",
                "analysis_sections": [
                    {
                        "title": section["title"],
                        "body": f"{section['title']} 已纳入报告解释。",
                        "evidence_lines": [section["title"]],
                        "relevance_to_question": "用于检查星盘报告是否完整覆盖原始导出。",
                    }
                    for section in template["source_export_sections"]
                ],
                "evidence": [{"source_section_title": "宫位宫头", "source_line": "第八宫 宫头"}],
                "recommendations": ["保留完整导出正文。"],
                "limitations": ["测试环境不代表真实解读。"],
            },
        }
    )

    rendered_json = service.report_render(
        {
            "run_id": result.memory_ref.run_id,
            "tool_name": "chart",
            "format": "json",
            "include_raw_json": True,
        }
    )
    rendered_docx = service.report_render({"run_id": result.memory_ref.run_id, "tool_name": "chart", "format": "docx"})
    rendered_pdf = service.report_render({"run_id": result.memory_ref.run_id, "tool_name": "chart", "format": "pdf"})

    for rendered in (rendered_json, rendered_docx, rendered_pdf):
        path = Path(rendered["artifact_path"])
        assert path.is_file()
        assert rendered["file_size"] > 100
        assert rendered["sha256"]

    assert Path(rendered_json["artifact_path"]).read_text(encoding="utf-8").startswith("{")
    report_payload = json.loads(Path(rendered_json["artifact_path"]).read_text(encoding="utf-8"))
    assert report_payload["coverage"]["source_export_section_count"] == len(template["source_export_sections"])
    assert report_payload["coverage"]["source_export_text_chars"] > 0
    assert report_payload["report_index"]["has_ai_answer"] is True
    assert report_payload["report_index"]["question_analysis"]["has_question"] is True
    assert report_payload["report_index"]["answer_plan"]
    assert report_payload["report_index"]["targeted_answer_requirements"]
    assert report_payload["report_index"]["storage"]["managed_by"] == "horosa_skill.memory"
    assert report_payload["report_index"]["ready_to_deliver"] is True
    assert report_payload["report_index"]["delivery_missing"] == []
    assert report_payload["report_quality"]["source_complete"] is True
    assert report_payload["report_quality"]["ready_for_human_reading"] is True
    assert report_payload["delivery_checklist"]["ready_to_deliver"] is True
    assert report_payload["delivery_checklist"]["missing"] == []
    assert report_payload["delivery_checklist"]["checks"]["has_ai_direct_answer"] is True
    assert report_payload["delivery_checklist"]["checks"]["has_provenance"] is True
    assert report_payload["section_coverage_matrix"]["source_section_count"] == len(template["source_export_sections"])
    assert report_payload["content_outline"][0]["title"] == "报告元信息"
    assert report_payload["sections"][0]["items"]["run_id"] == result.memory_ref.run_id
    assert "报告元信息" in report_payload["plain_text"]
    assert "交付检查清单" in report_payload["plain_text"]
    assert "AI 解盘正文" in report_payload["plain_text"]
    assert "来源追溯" in report_payload["plain_text"]
    assert report_payload["search_index"]["plain_text_chars"] == len(report_payload["plain_text"])
    assert "检查后天宫位" in report_payload["search_index"]["keywords"]
    section_titles = {section["title"] for section in report_payload["sections"]}
    assert {
        "报告质量检查",
        "报告元信息",
        "交付检查清单",
        "AI 解释覆盖清单",
        "逐章解释覆盖矩阵",
        "针对性解盘要求",
        "用户问题拆解",
        "AI 解盘正文",
        "建议、限制与追问",
        "来源追溯",
    }.issubset(section_titles)
    assert Path(rendered_docx["artifact_path"]).read_bytes().startswith(b"PK")
    assert Path(rendered_pdf["artifact_path"]).read_bytes().startswith(b"%PDF")
    queried = store.query_runs(run_id=result.memory_ref.run_id, include_payload=False)
    artifact_kinds = {artifact["kind"] for artifact in queried[0]["artifacts"]}
    assert {"report_json", "report_docx", "report_pdf"}.issubset(artifact_kinds)
    for artifact in queried[0]["artifacts"]:
        assert artifact["exists"] is True
        assert artifact["file_size"] > 0
        assert artifact["sha256"]

    report_pdf_runs = store.query_runs(
        run_id=result.memory_ref.run_id,
        text="后天宫位",
        artifact_kind="report_pdf",
        include_payload=False,
    )
    assert report_pdf_runs
    assert report_pdf_runs[0]["artifacts"]
    assert {artifact["kind"] for artifact in report_pdf_runs[0]["artifacts"]} == {"report_pdf"}
    assert report_pdf_runs[0]["artifact_summary"]["has_reports"] is True
    assert report_pdf_runs[0]["artifact_summary"]["counts_by_kind"]["report_pdf"] == 1
    assert report_pdf_runs[0]["artifact_summary"]["latest_report"]["kind"] == "report_pdf"

    report_json_plain_text_runs = store.query_runs(
        text="逐章解释覆盖矩阵",
        artifact_kind="report_json",
        include_payload=False,
    )
    assert any(run["run_id"] == result.memory_ref.run_id for run in report_json_plain_text_runs)


def test_service_can_render_report_from_tool_in_one_call(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    rendered = service.report_from_tool(
        {
            "tool_name": "qimen",
            "payload": {"date": "2028-04-06", "time": "09:33:00", "zone": "8", "lat": "31n13", "lon": "121e28"},
            "format": "json",
            "question": "请生成奇门结构化报告",
            "ai_report": {"executive_summary": "奇门报告摘要。"},
        }
    )

    assert rendered["ok"] is True
    assert rendered["format"] == "json"
    assert Path(rendered["artifact_path"]).is_file()
    assert rendered["tool_result"]["ok"] is True
    assert rendered["source"]["tool_name"] == "qimen"
    assert rendered["answer_writeback"]["ok"] is True
    assert rendered["answer_writeback"]["answer_text_chars"] > 0
    run_id = rendered["tool_result"]["memory_ref"]["run_id"]
    stored = service.store.query_runs(run_id=run_id, text="奇门报告摘要", include_payload=True)
    assert stored
    assert stored[0]["ai_answer_text"] == "奇门报告摘要。"
    assert stored[0]["ai_answer_structured"]["executive_summary"] == "奇门报告摘要。"
    assert stored[0]["answer_meta"]["source"] == "report_render"
    assert stored[0]["artifact_summary"]["has_reports"] is True
    assert stored[0]["artifact_summary"]["counts_by_kind"]["report_json"] == 1


def test_report_from_tool_without_ai_report_returns_analysis_packet_not_final_report(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.report_from_tool(
        {
            "tool_name": "qimen",
            "payload": {"date": "2028-04-06", "time": "09:33:00", "zone": "8", "lat": "31n13", "lon": "121e28"},
            "format": "pdf",
            "question": "这个事情能不能推进？风险在哪里？",
        }
    )

    assert result["ok"] is True
    assert result["mode"] == "analysis_required"
    assert result["needs_ai_analysis"] is True
    assert result["final_report_generated"] is False
    assert result["artifact_path"] is None
    assert result["tool_result"]["ok"] is True
    assert result["report_template"]["source_context"]["export_text"]
    assert result["report_template"]["source_context"]["export_sections"]
    assert result["report_template"]["targeted_analysis_contract"]["targeted_answer_requirements"]
    assert result["report_template"]["conversation_brief"]["role"].startswith("你是接入 Horosa Skill 的 AI 解盘助手")
    assert "完整对话式解盘正文" in result["report_template"]["conversation_brief"]["final_ai_report_contract"]["answer_text"]
    assert result["ai_process"]["input"]
    assert result["ai_process"]["conversation_brief"]["plate_context"]["tool_name"] == "qimen"
    assert result["ai_process"]["process"]
    assert result["ai_process"]["output"].startswith("最终报告必须来自 AI")
    assert "answer_text" in result["ai_process"]["ai_report_skeleton"]
    assert result["ai_process"]["next_call"]["payload"]["run_id"] == result["run_id"]
    assert result["ai_process"]["next_call"]["payload"]["ai_report"] == "<AI fills this object from ai_report_skeleton>"

    stored = service.show_memory({"run_id": result["run_id"], "include_payload": True})
    assert stored["ok"] is True
    assert stored["result"]["artifact_summary"]["has_reports"] is False
    assert stored["result"]["ai_answer_text"] is None
    artifact_kinds = {artifact["kind"] for artifact in stored["result"]["artifacts"]}
    assert "tool_result" in artifact_kinds
    assert "report_pdf" not in artifact_kinds


def test_report_from_tool_accepts_freeform_ai_answer_text(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    answer_text = (
        "结论上，这件事可以推进，但不适合在信息不足时突然加速。"
        "我会先看奇门盘里的起局信息、值符值使和宫位关系，再把这些线索转成现实行动建议。"
        "事业上适合先整理资源和选择窗口，财务上要避免高杠杆，决策上要把可验证的小步骤放在前面。"
    )

    rendered = service.report_from_tool(
        {
            "tool_name": "qimen",
            "payload": {"date": "2028-04-06", "time": "09:33:00", "zone": "8", "lat": "31n13", "lon": "121e28"},
            "format": "docx",
            "question": "这个事情能不能推进？风险在哪里？",
            "ai_answer_text": answer_text,
        }
    )

    assert rendered["ok"] is True
    assert rendered["answer_writeback"]["ok"] is True
    run_id = rendered["tool_result"]["memory_ref"]["run_id"]
    stored = service.show_memory({"run_id": run_id, "include_payload": True})
    assert stored["result"]["ai_answer_text"] == answer_text
    assert stored["result"]["ai_answer_structured"]["answer_text"] == answer_text
    with zipfile.ZipFile(Path(rendered["artifact_path"])) as archive:
        docx_text = re.sub("<[^>]+>", "", archive.read("word/document.xml").decode("utf-8"))
    assert "完整解盘正文" in docx_text
    assert "这件事可以推进" in docx_text
    assert "可读解读" not in docx_text
    assert "关键线索" not in docx_text
    assert "本次咨询使用" not in docx_text
    assert "盘面返回的核心摘要" not in docx_text
    assert "Run ID" not in docx_text


def test_report_contract_targets_user_question_and_memory_retrieval(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    question = "我接下来事业什么时候适合换工作？是否应该跳槽？"
    result = service.run_tool(
        "qimen",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "8", "lat": "31n13", "lon": "121e28"},
        save_result=True,
        query_text=question,
    )
    assert result.memory_ref is not None

    template = service.report_template({"run_id": result.memory_ref.run_id, "tool_name": "qimen"})
    assert template["question_analysis"]["focus_domains"] == ["career", "timing", "decision"]
    assert template["question_analysis"]["needs_timing"] is True
    assert template["question_analysis"]["needs_decision_support"] is True
    requirement_ids = {
        item["id"]
        for item in template["targeted_analysis_contract"]["targeted_answer_requirements"]
    }
    assert {"focus_career", "timing_window", "decision_support"}.issubset(requirement_ids)
    assert template["ai_fillable"]["targeted_answer_requirements"]

    ai_sections = [
        {
            "title": section["title"],
            "body": f"{section['title']} 用于判断事业换工作节奏与跳槽风险。",
            "evidence_lines": [section["title"]],
            "relevance_to_question": "直接服务于事业、时间窗口和是否跳槽的判断。",
        }
        for section in template["source_export_sections"]
    ]
    rendered = service.report_render(
        {
            "run_id": result.memory_ref.run_id,
            "tool_name": "qimen",
            "format": "json",
            "ai_report": {
                "analysis_focus": question,
                "direct_answer": "可以准备换工作，但需要等待更清晰的时间窗口再正式跳槽。",
                "executive_summary": "事业问题以先准备、后行动为宜。",
                "analysis_sections": ai_sections,
                "evidence": [{"source_section_title": template["source_export_sections"][0]["title"], "source_line": "奇门自检线索"}],
                "recommendations": ["先整理作品和资源，再选择合适窗口投递。"],
                "limitations": ["真实决策仍需结合行业机会与个人现实约束。"],
                "follow_up_questions": ["可以继续追问具体月份或目标公司方向。"],
            },
        }
    )

    report_payload = json.loads(Path(rendered["artifact_path"]).read_text(encoding="utf-8"))
    assert report_payload["delivery_checklist"]["ready_to_deliver"] is True
    assert report_payload["delivery_checklist"]["checks"]["has_targeted_requirements"] is True
    assert report_payload["targeted_analysis_contract"]["question_analysis"]["focus_domains"] == ["career", "timing", "decision"]
    assert report_payload["report_index"]["ready_to_deliver"] is True
    assert report_payload["report_index"]["delivery_missing"] == []
    report_requirement_ids = {
        item["id"]
        for item in report_payload["report_index"]["targeted_answer_requirements"]
    }
    assert {"focus_career", "timing_window", "decision_support"}.issubset(report_requirement_ids)
    assert "时间窗口" in report_payload["search_index"]["keywords"]
    assert "决策建议" in report_payload["search_index"]["keywords"]
    assert "换工作" in report_payload["plain_text"]
    assert "跳槽" in report_payload["plain_text"]

    by_question = store.query_runs(text="跳槽", artifact_kind="report_json", include_payload=True)
    assert any(run["run_id"] == result.memory_ref.run_id for run in by_question)
    by_requirement = store.query_runs(text="时间窗口", artifact_kind="report_json", include_payload=False)
    assert any(run["run_id"] == result.memory_ref.run_id for run in by_requirement)
    stored = service.show_memory({"run_id": result.memory_ref.run_id, "include_payload": True})
    assert stored["ok"] is True
    assert stored["result"]["ai_answer_text"].startswith("可以准备换工作")
    assert stored["result"]["ai_answer_structured"]["analysis_focus"] == question
    assert stored["result"]["answer_meta"]["source"] == "report_render"
    assert stored["result"]["artifact_summary"]["has_reports"] is True
    assert stored["result"]["artifact_summary"]["latest_report"]["kind"] == "report_json"


def test_targeted_consultation_report_roundtrip_persists_and_retrieves_ai_analysis(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    question = "这个人未来三年事业、财务和决策风险应该怎么判断？是否适合换工作或做更激进的投资？"
    result = service.run_tool(
        "qimen",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "8", "lat": "31n13", "lon": "121e28"},
        save_result=True,
        query_text=question,
    )
    assert result.memory_ref is not None

    template = service.report_template({"run_id": result.memory_ref.run_id, "tool_name": "qimen"})
    assert template["question_analysis"]["focus_domains"] == ["career", "wealth", "timing", "decision"]
    source_title = template["source_export_sections"][0]["title"]
    ai_report = {
        "analysis_focus": question,
        "direct_answer": "结论上：可以准备换工作，但不宜裸辞；财务上不建议高杠杆或激进投资。",
        "executive_summary": "此局适合先做机会筛选和资源整理，等时间窗口清楚后再行动。",
        "consultation_basis": [
            "以奇门局的起局时间、值符值使、门星神仪和宫位互动作为判断依据。",
            "把事业、财务、风险和时间窗口分开判断，避免只给抽象结论。",
        ],
        "reading_steps": [
            "先确认用局和用户问题。",
            "再看事业相关宫位、门星神仪与动静变化。",
            "最后把财务风险、行动窗口和现实约束合并成建议。",
        ],
        "analysis_sections": [
            {
                "title": "事业策略",
                "body": "事业上可以主动准备换工作，但应先建立备选机会，不宜裸辞。",
                "evidence_lines": [source_title],
                "relevance_to_question": "直接回答是否适合换工作。",
            },
            {
                "title": "财务风险",
                "body": "财务判断偏保守，暂时不建议高杠杆、借贷扩张或激进投资。",
                "evidence_lines": [source_title],
                "relevance_to_question": "直接回答是否适合做更激进的投资。",
            },
            {
                "title": "行动窗口",
                "body": "更适合先观察机会质量，再选择阻力较小的窗口推进。",
                "evidence_lines": [source_title],
                "relevance_to_question": "给出时间和行动节奏。",
            },
        ],
        "evidence": [{"source_section_title": source_title, "source_line": "奇门起局与宫位线索"}],
        "recommendations": [
            "先整理简历、作品和目标岗位，再分批投递。",
            "投资部分以现金流安全为先，暂缓高杠杆配置。",
            "如果出现明确 offer，再结合薪资、团队和行业周期做最终决策。",
        ],
        "limitations": ["本报告提供决策辅助，不替代现实尽调、合同审核和财务规划。"],
        "follow_up_questions": ["可以继续追问具体月份、目标行业或某个 offer 是否值得接。"],
    }

    rendered_json = service.report_render(
        {
            "run_id": result.memory_ref.run_id,
            "tool_name": "qimen",
            "format": "json",
            "ai_report": ai_report,
        }
    )
    assert rendered_json["answer_writeback"]["ok"] is True
    rendered_docx = service.report_render({"run_id": result.memory_ref.run_id, "tool_name": "qimen", "format": "docx"})
    rendered_pdf = service.report_render({"run_id": result.memory_ref.run_id, "tool_name": "qimen", "format": "pdf"})

    report_payload = json.loads(Path(rendered_json["artifact_path"]).read_text(encoding="utf-8"))
    assert report_payload["report_index"]["ready_to_deliver"] is True
    assert report_payload["delivery_checklist"]["ready_to_deliver"] is True
    assert report_payload["report_quality"]["ready_for_human_reading"] is True
    assert report_payload["ai_report"]["analysis_focus"] == question
    assert "不宜裸辞" in report_payload["ai_report"]["direct_answer"]
    assert "高杠杆" in report_payload["plain_text"]
    assert "换工作" in report_payload["search_index"]["keywords"]
    assert "激进投资" in report_payload["search_index"]["keywords"]

    with zipfile.ZipFile(Path(rendered_docx["artifact_path"])) as archive:
        docx_text = re.sub("<[^>]+>", "", archive.read("word/document.xml").decode("utf-8"))
    assert "解读目标" in docx_text
    assert "起盘依据" in docx_text
    assert "解盘步骤" in docx_text
    assert "核心结论" in docx_text
    assert "事业策略" in docx_text
    assert "财务风险" in docx_text
    assert "不宜裸辞" in docx_text
    assert "高杠杆" in docx_text
    assert not any(term in docx_text for term in ["Run ID", "来源追溯", "report_metadata", "Horosa Skill"])
    assert Path(rendered_pdf["artifact_path"]).read_bytes().startswith(b"%PDF")

    shown = service.show_memory({"run_id": result.memory_ref.run_id, "include_payload": True})
    assert shown["ok"] is True
    stored_run = shown["result"]
    assert stored_run["ai_answer_text"] == ai_report["direct_answer"]
    assert stored_run["ai_answer_structured"]["analysis_focus"] == question
    assert stored_run["answer_meta"]["source"] == "report_render"
    artifact_kinds = {artifact["kind"] for artifact in stored_run["artifacts"]}
    assert {"tool_result", "report_json", "report_docx", "report_pdf", "run_manifest"}.issubset(artifact_kinds)
    assert stored_run["artifact_summary"]["has_reports"] is True
    assert stored_run["artifact_summary"]["counts_by_kind"]["report_json"] == 1
    assert stored_run["artifact_summary"]["counts_by_kind"]["report_docx"] == 1
    assert stored_run["artifact_summary"]["counts_by_kind"]["report_pdf"] == 1
    for artifact in stored_run["artifacts"]:
        assert artifact["exists"] is True
        assert artifact["file_size"] > 0
        assert artifact["sha256"]

    by_question = service.query_memory(
        {"text": "激进投资", "artifact_kind": "report_json", "include_payload": True, "limit": 5}
    )
    assert by_question["ok"] is True
    assert any(item["run_id"] == result.memory_ref.run_id for item in by_question["results"])
    matched = next(item for item in by_question["results"] if item["run_id"] == result.memory_ref.run_id)
    assert matched["artifact_summary"]["has_reports"] is True
    assert matched["artifacts"][0]["kind"] == "report_json"
    assert matched["artifacts"][0]["payload"]["report_index"]["ready_to_deliver"] is True
    assert "高杠杆" in json.dumps(matched["artifacts"][0]["payload"], ensure_ascii=False)

    by_answer = service.query_memory(
        {"text": "不宜裸辞", "tool": "qimen", "include_payload": False, "limit": 5}
    )
    assert by_answer["ok"] is True
    assert any(item["run_id"] == result.memory_ref.run_id for item in by_answer["results"])


def test_report_manifest_preserves_ai_answer_and_report_artifact_index(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    rendered = service.report_from_tool(
        {
            "tool_name": "bazi_birth",
            "payload": {
                "date": "1995-06-03",
                "time": "05:30:00",
                "zone": "+08:00",
                "lat": "31n13",
                "lon": "121e28",
                "gender": True,
            },
            "format": "json",
            "question": "未来三年事业和财务怎么规划？是否适合激进投资？",
            "ai_report": {
                "analysis_focus": "未来三年事业、财务和投资风险。",
                "direct_answer": "结论上：事业宜稳中求进，财务不宜激进投资。",
                "executive_summary": "先保现金流，再筛选更确定的机会。",
                "analysis_sections": [
                    {
                        "title": "事业规划",
                        "body": "适合准备机会，但不宜仓促转向。",
                        "evidence_lines": ["起盘信息"],
                        "relevance_to_question": "回应事业规划。",
                    },
                    {
                        "title": "财务规划",
                        "body": "不宜激进投资，应先控制风险和现金流。",
                        "evidence_lines": ["起盘信息"],
                        "relevance_to_question": "回应财务规划。",
                    },
                ],
                "recommendations": ["先保现金流。", "投资降低杠杆。"],
                "limitations": ["仍需结合现实收入、行业和负债情况。"],
                "evidence": [{"source_section_title": "起盘信息", "source_line": "样本起盘线索"}],
            },
        }
    )
    assert rendered["ok"] is True
    run_id = rendered["tool_result"]["memory_ref"]["run_id"]
    service.report_render({"run_id": run_id, "tool_name": "bazi_birth", "format": "docx"})
    service.report_render({"run_id": run_id, "tool_name": "bazi_birth", "format": "pdf"})

    shown = service.show_memory({"run_id": run_id, "include_payload": True})
    manifest_artifact = next(artifact for artifact in shown["result"]["artifacts"] if artifact["kind"] == "run_manifest")
    manifest = manifest_artifact["payload"]
    assert manifest["run"]["id"] == run_id
    assert manifest["run"]["user_question"] == "未来三年事业和财务怎么规划？是否适合激进投资？"
    assert manifest["run"]["ai_answer_text"] == "结论上：事业宜稳中求进，财务不宜激进投资。"
    assert manifest["run"]["ai_answer_structured"]["analysis_focus"] == "未来三年事业、财务和投资风险。"
    assert manifest["run"]["answer_meta"]["source"] == "report_render"
    manifest_kinds = {artifact["kind"] for artifact in manifest["artifacts"]}
    assert {"tool_result", "report_json", "report_docx", "report_pdf"}.issubset(manifest_kinds)
    manifest_paths = [Path(artifact["path"]) for artifact in manifest["artifacts"]]
    assert all(path.is_file() for path in manifest_paths)
    assert manifest["artifact_summary"]["has_reports"] is True
    assert manifest["artifact_summary"]["counts_by_kind"]["report_json"] == 1
    assert manifest["artifact_summary"]["counts_by_kind"]["report_docx"] == 1
    assert manifest["artifact_summary"]["counts_by_kind"]["report_pdf"] == 1
    for artifact in manifest["artifacts"]:
        assert artifact["exists"] is True
        assert artifact["file_size"] > 0
        assert artifact["sha256"]

    queried = service.query_memory(
        {"text": "激进投资", "artifact_kind": "run_manifest", "include_payload": True, "limit": 5}
    )
    assert queried["ok"] is True
    assert any(item["run_id"] == run_id for item in queried["results"])
    matched = next(item for item in queried["results"] if item["run_id"] == run_id)
    assert matched["artifacts"][0]["payload"]["run"]["ai_answer_text"].endswith("财务不宜激进投资。")


def test_report_question_analysis_understands_natural_timing_and_decision_words(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "qimen",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "8", "lat": "31n13", "lon": "121e28"},
        save_result=True,
        query_text="重点分析事业、时间窗口、决策建议，并保留原始技法依据。",
    )
    assert result.memory_ref is not None

    template = service.report_template({"run_id": result.memory_ref.run_id, "tool_name": "qimen"})
    assert template["question_analysis"]["focus_domains"] == ["career", "timing", "decision"]
    assert "时间窗口" in template["question_analysis"]["keywords_detected"]
    assert "决策" in template["question_analysis"]["keywords_detected"]
    assert "建议" in template["question_analysis"]["keywords_detected"]
    assert template["question_analysis"]["needs_timing"] is True
    assert template["question_analysis"]["needs_decision_support"] is True
    requirement_ids = {
        item["id"]
        for item in template["targeted_analysis_contract"]["targeted_answer_requirements"]
    }
    assert {"focus_career", "timing_window", "decision_support"}.issubset(requirement_ids)


def test_late_zi_switch_threads_through_all_chart_flows(tmp_path) -> None:
    # 晚子时开关全链穿透：显式 0 抵达各端点；不传时键缺席（零默认漂移，后端按默认 1 起算）。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    client = CaptureClient()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())
    base = {"date": "2026-05-27", "time": "23:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True}

    cases = [
        ("bazi_birth", "/bazi/birth"),
        ("ziwei_birth", "/ziwei/birth"),
        ("liureng_gods", "/liureng/gods"),
        ("nongli_time", "/nongli/time"),
        ("qimen", "/qimen/pan"),
        ("taiyi", "/taiyi/pan"),
        ("jinkou", "/jinkou/pan"),
    ]
    for tool_name, endpoint in cases:
        client.calls.clear()
        service.run_tool(tool_name, {**base, "lateZiHourUseNextDay": 0}, save_result=False)
        captured = [payload for ep, payload in client.calls if ep == endpoint]
        assert captured, f"{tool_name} 未调用 {endpoint}"
        assert captured[0].get("lateZiHourUseNextDay") == 0, f"{tool_name} 未穿透 lateZi 到 {endpoint}"

        client.calls.clear()
        service.run_tool(tool_name, dict(base), save_result=False)
        captured = [payload for ep, payload in client.calls if ep == endpoint]
        assert captured and "lateZiHourUseNextDay" not in captured[0], f"{tool_name} 缺省时不得发送 lateZi（零漂移）"

    # qimen 显式 after23NewDay=0 抵达权威引擎（此前 ken 调用收不到该开关）。
    client.calls.clear()
    service.run_tool("qimen", {**base, "after23NewDay": 0}, save_result=False)
    ken = [payload for ep, payload in client.calls if ep == "/qimen/pan"]
    assert ken and ken[0].get("after23NewDay") == 0

    # sanshiunited 显式开关透传三式子工具。
    client.calls.clear()
    service.run_tool("sanshiunited", {**base, "lateZiHourUseNextDay": 0}, save_result=False)
    for endpoint in ("/qimen/pan", "/taiyi/pan", "/liureng/gods"):
        captured = [payload for ep, payload in client.calls if ep == endpoint]
        assert captured and captured[0].get("lateZiHourUseNextDay") == 0, f"sanshiunited 未透传到 {endpoint}"


def test_operational_errors_carry_agent_recovery(tmp_path) -> None:
    # 运行时/传输类错误统一带 agent_recovery（可执行的修复指引），不再只丢技术字段。
    settings = Settings(
        server_root="http://127.0.0.1:1",  # 无监听端口 → transport.connection_error
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool(
        "nongli_time",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lon": "121e28", "agent_confirmed_settings": True},
        save_result=False,
    )
    assert result.ok is False
    assert result.error is not None
    recovery = (result.error.details or {}).get("agent_recovery")
    assert isinstance(recovery, dict) and recovery.get("prompt_to_user")
    assert "doctor" in json.dumps(recovery)


def test_preflight_skips_questions_for_provided_fields(tmp_path) -> None:
    # 闸按已提供字段过滤：用户已给出生数据时不再重复追问 date/time/location。
    from horosa_skill.agent_guidance import validate_agent_preflight

    gate_empty = validate_agent_preflight("chart", {})
    fields_when_empty = {str(item.get("field")) for item in gate_empty["ask_if_missing"]}

    gate_full = validate_agent_preflight(
        "chart",
        {"date": "1995-06-03", "time": "05:30", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
    )
    fields_when_full = {str(item.get("field")) for item in gate_full["ask_if_missing"]}
    assert gate_full["ok"] is False  # 仍需确认结果敏感设置（hsys/zodiacal 等仍在问）
    # 已提供的出生信息组不再出现在追问里；空 payload 时仍会问。
    assert "date/time/place" in fields_when_empty
    assert "date/time/place" not in fields_when_full
    assert "hsys" in fields_when_full


def test_dispatch_no_match_returns_candidates(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.dispatch({"query": "看看老黄历宜忌", "agent_confirmed_settings": True, "save_result": False})
    assert result.ok is False
    details = result.error.details or {}
    assert details.get("candidates") and "calendar_month" in details["candidates"]


def test_response_view_trims_payload_but_archives_full(tmp_path) -> None:
    # response_view=titles：返回体只留段标题索引；memory 存档仍是全量（可取回）。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    base = {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True}

    result = service.run_tool("qimen", {**base, "response_view": "titles"})
    assert result.ok is True
    contract = result.data["export_snapshot"]
    assert contract["sections"] and all(set(section) == {"index", "title"} for section in contract["sections"])
    assert "export_text" not in contract
    assert result.data["snapshot_text"] == ""
    assert any("response_view" in warning for warning in result.warnings)
    # 存档保全量。
    shown = service.show_memory({"run_id": result.memory_ref.run_id, "include_payload": True})
    archived = None
    for artifact in shown["result"].get("artifacts", []):
        if artifact.get("kind") == "tool_result":
            archived = json.loads(Path(artifact["path"]).read_text(encoding="utf-8"))
            break
    assert archived and archived["data"]["snapshot_text"]
    assert archived["data"]["export_snapshot"]["export_text"]

    # sections 视图：标题+正文，剥结构化 data。
    result2 = service.run_tool("qimen", {**base, "response_view": "sections"}, save_result=False)
    sections2 = result2.data["export_snapshot"]["sections"]
    assert sections2 and all(set(section) == {"index", "title", "body"} for section in sections2)


def test_export_contract_is_deduplicated_single_copy(tmp_path) -> None:
    # 响应体去重锚：同一份快照只存 顶层 snapshot_text + export_snapshot.export_text 两份，
    # 冗余副本（export_format / raw_text / filtered_text / 内嵌 snapshot_text / sections.content）不复现。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool(
        "qimen",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True},
        save_result=False,
    )
    assert result.ok is True
    data = result.data
    assert isinstance(data["snapshot_text"], str) and data["snapshot_text"]
    assert "export_format" not in data
    contract = data["export_snapshot"]
    for redundant in ("raw_text", "filtered_text", "snapshot_text"):
        assert redundant not in contract, redundant
    assert contract["export_text"]
    assert contract["sections"]
    for section in contract["sections"]:
        assert "content" not in section
        assert section["title"]
    # 全文最多出现 2 份：顶层 snapshot_text + export_snapshot.export_text。
    serialized = json.dumps(data, ensure_ascii=False)
    probe = data["snapshot_text"][:24]
    assert probe and serialized.count(probe) <= 2


def test_report_render_replays_legacy_archive_shape(tmp_path) -> None:
    # 向后兼容锚：旧归档（data.export_format 副本、无新形状 export_snapshot）仍可出报告。
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool(
        "qimen",
        {"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True},
        query_text="旧归档回放",
    )
    run_id = result.memory_ref.run_id
    # 把归档改写成旧形状：export_snapshot → export_format（含彼时的 snapshot_text 内嵌份）。
    shown = service.show_memory({"run_id": run_id, "include_payload": True})
    artifact_path = None
    for artifact in shown["result"].get("artifacts", []):
        if artifact.get("kind") == "tool_result":
            artifact_path = artifact.get("path")
            break
    assert artifact_path
    archive = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
    data = archive["data"]
    # 还原旧归档形状：export_snapshot 带冗余全文键 + export_format 完整副本并存。
    legacy_snapshot = dict(data["export_snapshot"])
    legacy_snapshot["raw_text"] = data.get("snapshot_text")
    legacy_snapshot["filtered_text"] = legacy_snapshot.get("export_text")
    legacy_snapshot["snapshot_text"] = data.get("snapshot_text")
    data["export_snapshot"] = legacy_snapshot
    data["export_format"] = {
        "technique": legacy_snapshot["technique"],
        "selected_sections": legacy_snapshot["selected_sections"],
        "format_source": legacy_snapshot["format_source"],
        "snapshot_text": data.get("snapshot_text"),
        "bundle_version": legacy_snapshot.get("bundle_version"),
        "provenance": legacy_snapshot.get("provenance"),
        "citation": legacy_snapshot.get("citation"),
        "sections": [
            {**{k: v for k, v in section.items() if k != "raw_title"}, "content": f"[{section['title']}]"}
            for section in legacy_snapshot["sections"]
        ],
    }
    Path(artifact_path).write_text(json.dumps(archive, ensure_ascii=False), encoding="utf-8")

    rendered = service.report_render(
        {
            "run_id": run_id,
            "tool_name": "qimen",
            "format": "json",
            "ai_report": {"executive_summary": "旧归档也能出报告。", "answer_text": "结论：可以推进。"},
        }
    )
    assert rendered["ok"] is True


def test_service_emits_trace_and_provenance_for_tool_results(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        trace_dir=tmp_path / "traces",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "chart",
        {"date": "1990-01-01", "time": "12:00", "zone": "8", "lat": "31n14", "lon": "121e28"},
        save_result=True,
        evaluation_case_id="chart_case",
    )

    assert result.trace_id
    assert result.group_id
    assert result.memory_ref is not None
    assert result.memory_ref.trace_id == result.trace_id
    assert result.memory_ref.group_id == result.group_id
    assert result.data["export_snapshot"]["provenance"]["source_domain"] == "xingque_ai_export"
    assert result.data["export_snapshot"]["provenance"]["bundle_version"] == result.data["export_snapshot"]["bundle_version"]
    # 唯一导出契约：export_format 副本不再产出。
    assert "export_format" not in result.data
    assert settings.trace_dir.exists()
    trace_files = sorted(settings.trace_dir.glob("*.jsonl"))
    assert trace_files
    assert result.trace_id in trace_files[0].read_text(encoding="utf-8")


def test_knowledge_results_include_provenance(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool("knowledge_read", {"domain": "qimen", "category": "door", "key": "休门"}, save_result=False)

    assert result.ok is True
    assert result.data["bundle_version"] == 1
    assert result.data["provenance"]["domain"] == "qimen"
    assert result.data["provenance"]["category"] == "door"
    assert result.data["citation"] == "Xingque hover knowledge · qimen/door/休门"


def test_dispatch_emits_group_trace_for_children(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        trace_dir=tmp_path / "traces",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store, js_client=FakeJsClient())

    result = service.dispatch(
        {
            "query": "请用奇门和六壬综合分析",
            "birth": {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"},
            "save_result": True,
        },
        evaluation_case_id="dispatch_case",
    )

    assert result.trace_id
    assert result.group_id
    for item in result.results.values():
        assert item.group_id == result.group_id
        assert item.trace_id
    queried = store.query_runs(run_id=result.memory_ref.run_id, include_payload=True)
    assert queried[0]["group_id"] == result.group_id


def test_run_tool_wraps_unexpected_exception_into_error_envelope(tmp_path) -> None:
    """Regression: an unexpected (non-HorosaSkillError) exception during tool execution or
    snapshot/summary/export post-processing must surface as a clean ok=False envelope
    (`tool.internal_error`), never crash the CLI / break the MCP session / abort a dispatch."""

    class ExplodingClient(FakeClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            # `/chart` is rewritten to "/" by _chart_server_endpoint before reaching the
            # client, so raise on both forms to be robust.
            if endpoint in {"/chart", "/"}:
                raise ValueError("boom from backend")
            return super().call(endpoint, payload)

    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=ExplodingClient(), store=MemoryStore(settings), js_client=FakeJsClient())

    result = service.run_tool(
        "chart",
        {"date": "1990-01-01", "time": "12:00", "zone": "+08:00", "lat": "31n14", "lon": "121e28"},
        save_result=False,
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "tool.internal_error"
    assert "boom from backend" in result.error.message
    assert result.error.details.get("exception_type") == "ValueError"


# --- 择日搜索族（上游 v3.7.0 tianxing / v3.7.1 qimenzeri）--------------------------------------


def _zeri_service(tmp_path):
    settings = Settings(
        server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs"
    )
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def test_tianxing_splits_by_month_and_stitches(tmp_path) -> None:
    """窗口超 93 天必须切分（后端单请求硬顶），且缝合回一份区间表。"""
    service = _zeri_service(tmp_path)
    calls: list[dict] = []
    original = service.client.call

    def spy(endpoint: str, payload: dict) -> dict:
        if endpoint == "/electionscan/scan":
            calls.append(payload)
        return original(endpoint, payload)

    service.client.call = spy  # type: ignore[method-assign]
    result = service.run_tool("tianxing", build_sample_payloads()["tianxing"], save_result=False)
    assert result.ok is True, result.error
    assert len(calls) == 2, "跨月窗口必须切成多段请求"
    assert result.data["stats"]["segments"] == 2
    assert result.data["hit_count"] == len(result.data["intervals"]) == 2


def test_tianxing_fails_loudly_on_electionscan_error_envelope(tmp_path) -> None:
    """端点 HTTP 200 回 {'err': …}；没有守卫时会静默退化成「零命中」——那是一个看起来合理的假结果。"""
    service = _zeri_service(tmp_path)
    payload = {**build_sample_payloads()["tianxing"], "startDate": "1999-01-01", "endDate": "1999-03-01"}
    result = service.run_tool("tianxing", payload, save_result=False)
    assert result.ok is False, "span_too_large 必须报错，绝不能变成零命中"
    assert result.error.code == "tool.electionscan_failed"
    assert result.error.details["scan_error"]["err"] == "span_too_large"


def test_tianxing_rejects_invalid_conditions_before_any_http(tmp_path) -> None:
    service = _zeri_service(tmp_path)
    payload = {**build_sample_payloads()["tianxing"]}
    payload.pop("conditions")
    result = service.run_tool("tianxing", payload, save_result=False)
    assert result.ok is False
    assert result.error.code == "tool.tianxing_missing_conditions"


def test_tianxing_explain_at_appends_section_and_tree(tmp_path) -> None:
    """explainAt（v0.33.0）：结果多 explain 键 + 快照尾追 [单时判读]；t 归一 '-'→'/'、缺秒补 ':00'。"""
    service = _zeri_service(tmp_path)
    seen: list[dict] = []
    original = service.client.call

    def spy(endpoint: str, payload: dict) -> dict:
        if endpoint == "/electionscan/explain":
            seen.append(payload)
        return original(endpoint, payload)

    service.client.call = spy  # type: ignore[method-assign]
    payload = {**build_sample_payloads()["tianxing"], "explainAt": "2028-04-01 00:01"}
    result = service.run_tool("tianxing", payload, save_result=False)
    assert result.ok is True, result.error
    assert seen and seen[0]["t"] == "2028/04/01 00:01:00", "t 必须照上游 explainInterval 归一"
    assert seen[0].get("conditions"), "explain 必须带编译后的条件树"
    explain = result.data["explain"]
    assert explain["tree"]["kind"] == "group" and explain["tree"]["children"], "判读树必须原样带回"
    text = result.data["snapshot_text"]
    assert "[单时判读]" in text and text.index("[单时判读]") > text.index("[命中区间]"), "段须追加在快照尾部"
    assert "设定" in text and "实际" in text
    export = result.data["export_snapshot"]
    assert "单时判读" in export["section_titles_detected"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_tianxing_without_explain_at_emits_no_explain_key(tmp_path) -> None:
    """条件段零回归：未给 explainAt 时无 explain 键、无 [单时判读] 段、不打 /electionscan/explain。"""
    service = _zeri_service(tmp_path)
    calls: list[str] = []
    original = service.client.call
    service.client.call = lambda e, p: (calls.append(e) or original(e, p))  # type: ignore[method-assign]
    result = service.run_tool("tianxing", build_sample_payloads()["tianxing"], save_result=False)
    assert result.ok is True, result.error
    assert "explain" not in result.data
    assert "[单时判读]" not in (result.data["snapshot_text"] or "")
    assert "/electionscan/explain" not in calls
    assert "单时判读" not in result.data["export_snapshot"]["missing_selected_sections"]


def test_tianxing_invalid_conditions_error_carries_server_types(tmp_path) -> None:
    """条件树编译失败时（自愈式报错），details 附服务端 /electionscan/conditiontypes 实现集。"""

    class RejectingJs(FakeJsClient):
        def run(self, tool_name: str, payload: dict[str, object]) -> dict:
            if tool_name == "tianxing" and str(payload.get("action")) == "compile":
                return {"data": {"ok": False, "error": {"code": "invalid_conditions", "message": "「相位」条件：planetA 缺失"}}}
            return super().run(tool_name, payload)

    settings = Settings(
        server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs"
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=RejectingJs())
    result = service.run_tool("tianxing", build_sample_payloads()["tianxing"], save_result=False)
    assert result.ok is False
    assert result.error.code == "tool.tianxing_invalid_conditions"
    assert result.error.details["server_condition_types"] == ["aspect", "in_sign", "numeric"]


def test_cetian_text_key_appends_classics(tmp_path) -> None:
    """批 I-5：textKey=list 出目录 / 单篇出原文；未给不打 /cetian/texts。"""
    service = _zeri_service(tmp_path)
    calls: list[str] = []
    original = service.client.call
    service.client.call = lambda e, p: (calls.append(e) or original(e, p))  # type: ignore[method-assign]
    base = {"date": "1998-02-20", "time": "20:48", "gender": 1}
    plain = service.run_tool("cetian", base, save_result=False)
    assert plain.ok is True, plain.error
    assert "/cetian/texts" not in calls and "[判词原文]" not in plain.data["snapshot_text"]
    listing = service.run_tool("cetian", {**base, "textKey": "list"}, save_result=False)
    assert listing.ok is True, listing.error
    assert "判词库 2 篇" in listing.data["snapshot_text"] and "照胆经叙跋" in listing.data["snapshot_text"]
    one = service.run_tool("cetian", {**base, "textKey": "keying"}, save_result=False)
    assert "《克应歌》（keying）" in one.data["snapshot_text"] and "克应之说最玄微" in one.data["snapshot_text"]
    bad = service.run_tool("cetian", {**base, "textKey": "nope"}, save_result=False)
    assert bad.ok is False and bad.error.code == "tool.cetian_text_unknown_key"
    export = one.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_wangji_xinyi_casting_methods(tmp_path) -> None:
    """批 I-5：xinyiMethod=number 独立起卦产 [心易起卦]；缺省零回归。"""
    service = _zeri_service(tmp_path)
    base = {"date": "1998-02-20", "time": "20:48"}
    plain = service.run_tool("wangji", base, save_result=False)
    assert plain.ok is True, plain.error
    assert "[心易起卦]" not in plain.data["snapshot_text"]
    cast = service.run_tool("wangji", {**base, "xinyiMethod": "number", "upperNum": 7, "lowerNum": 12}, save_result=False)
    assert cast.ok is True, cast.error
    text = cast.data["snapshot_text"]
    assert "[心易起卦]" in text and "起法：报数" in text and "本卦：頤" in text
    assert cast.data["xinyi"]["result"]["本卦"] == "頤" and cast.data["xinyi"]["method"] == "number"
    export = cast.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_geomancy_include_catalog(tmp_path) -> None:
    """批 I-5：includeCatalog=true 产 [十六卦目录]（属性总表）；缺省零回归。"""
    service = _zeri_service(tmp_path)
    base = build_sample_payloads()["geomancy"]
    plain = service.run_tool("geomancy", base, save_result=False)
    assert plain.ok is True, plain.error
    assert "[十六卦目录]" not in plain.data["snapshot_text"]
    rich = service.run_tool("geomancy", {**base, "includeCatalog": True}, save_result=False)
    assert rich.ok is True, rich.error
    text = rich.data["snapshot_text"]
    assert "[十六卦目录]" in text and "道路（Via）" in text and "五行 水" in text and "主星 太阴" in text
    assert "●" in text, "卦形点须渲染"
    assert rich.data["catalog"]["figures"]
    export = rich.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_acg_click_point_and_event_conditional_sections(tmp_path) -> None:
    """批 I-4：clickLat/clickLon → [落点分析]；eventKind → [事件时刻]；缺省两段不产、不打端点。"""
    service = _zeri_service(tmp_path)
    calls: list[str] = []
    original = service.client.call
    service.client.call = lambda e, p: (calls.append(e) or original(e, p))  # type: ignore[method-assign]
    base = build_sample_payloads()["acg"]
    plain = service.run_tool("acg", base, save_result=False)
    assert plain.ok is True, plain.error
    assert "/location/acgpoint" not in calls and "/location/acgevent" not in calls
    assert "[落点分析]" not in plain.data["snapshot_text"] and "[事件时刻]" not in plain.data["snapshot_text"]
    rich = service.run_tool(
        "acg", {**base, "clickLat": 40.7, "clickLon": -74.0, "eventKind": "solar_eclipse"}, save_result=False
    )
    assert rich.ok is True, rich.error
    text = rich.data["snapshot_text"]
    assert "[落点分析]" in text and "[事件时刻]" in text
    assert "北交 临 Asc（距 1.27°）" in text
    assert "重置四角：" in text and "宿命点" in text
    assert "日食（next）：2027/02/06 15:59:39 UTC" in text
    assert rich.data["acg"]["point"]["hits"] and rich.data["acg"]["event"]["date"] == "2027/02/06"
    export = rich.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_planet_cycles_renders_timeline(tmp_path) -> None:
    """批 I-3：行星周期两段恒出；事件行 = UT 时刻 + 黄经度分（_sign_degree）。"""
    service = _zeri_service(tmp_path)
    result = service.run_tool("planet_cycles", build_sample_payloads()["planet_cycles"], save_result=False)
    assert result.ok is True, result.error
    assert result.data["cycles"]["events"]
    text = result.data["snapshot_text"]
    assert "[周期配置]" in text and "[会合事件]" in text
    assert "木星-土星" in text and "合" in text and "地心" in text
    assert "2020-12-21 18:20（UT）" in text and "宝瓶" in text, "2020 大合相在宝瓶 0°29′"
    export = result.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_jieqi_birth_marks_bracketing_terms(tmp_path) -> None:
    """批 I-3：出生节气窗——节/气标注 + 出生所落区间（纯时刻比较）。"""
    service = _zeri_service(tmp_path)
    result = service.run_tool("jieqi_birth", build_sample_payloads()["jieqi_birth"], save_result=False)
    assert result.ok is True, result.error
    text = result.data["snapshot_text"]
    assert "[出生节气窗]" in text
    assert "清明（节）　2028-04-04 15:02:44" in text
    assert "谷雨（气）" in text
    assert "出生落于 清明（2028-04-04 15:02:44）与 谷雨（2028-04-19 22:08:00）之间" in text
    export = result.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_extrareturns_timeline_conditional_section(tmp_path) -> None:
    """批 I-3：timelineStartYear/timelineCount 才产 [日月返照年表]；缺省不打 /astroextra/returns。"""
    service = _zeri_service(tmp_path)
    calls: list[str] = []
    original = service.client.call
    service.client.call = lambda e, p: (calls.append(e) or original(e, p))  # type: ignore[method-assign]
    plain = service.run_tool("extrareturns", build_sample_payloads()["extrareturns"], save_result=False)
    assert plain.ok is True, plain.error
    assert "/astroextra/returns" not in calls
    assert "[日月返照年表]" not in (plain.data["snapshot_text"] or "")
    dated = service.run_tool(
        "extrareturns", {**build_sample_payloads()["extrareturns"], "timelineStartYear": 2026, "timelineCount": 1},
        save_result=False,
    )
    assert dated.ok is True, dated.error
    assert "/astroextra/returns" in calls
    text = dated.data["snapshot_text"]
    assert "[日月返照年表]" in text
    assert "2026：日返 2026-06-02 17:35:27（升 26˚天蝎15分）" in text
    assert dated.data["timeline"][0]["year"] == 2026
    export = dated.data["export_snapshot"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_india_rectify_emits_five_sections_with_upstream_vocabulary(tmp_path) -> None:
    """批 I-2：生时校正五段恒出，语汇照上游校时器（校时之靶/采样/总-RP-PP/免责声明原样）。"""
    service = _zeri_service(tmp_path)
    result = service.run_tool("india_rectify", build_sample_payloads()["india_rectify"], save_result=False)
    assert result.ok is True, result.error
    assert result.data["rectify"]["available"] is True
    text = result.data["snapshot_text"]
    for section in ("[起盘信息]", "[校时扫描]", "[Lagna 子主区段]", "[候选榜]", "[声明]"):
        assert section in text, section
    assert "校时之靶 · 2 段" in text
    assert "罗睺：11:50:00 ~ 11:56:00（4 采样）" in text, "KP 主星须走罗睺/计都中文口径"
    assert "总 13　RP 6/6　PP good" in text
    assert "⚠ Lagna 落界" in text, "gandanta 边界预警必须上榜行"
    assert "半自动校时:输出证据与排序,采信与「采用」由用户决定" in text, "免责声明须原样带回"
    export = result.data["export_snapshot"]
    assert export["technique"]["key"] == "india_rectify"
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_india_rectify_fails_loudly_when_unavailable(tmp_path) -> None:
    class UnavailableClient(FakeClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            if endpoint == "/india/rectify":
                return {"available": False, "reason": "scan_error"}
            return super().call(endpoint, payload)

    settings = Settings(
        server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs"
    )
    service = HorosaSkillService(settings, client=UnavailableClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    result = service.run_tool("india_rectify", build_sample_payloads()["india_rectify"], save_result=False)
    assert result.ok is False
    assert result.error.code == "tool.india_rectify_failed"


def test_persiandirected_datetime_appends_directed_chart_section(tmp_path) -> None:
    """批 I-2：datetime 时 /predict/persianchart 整铸 + [指定日期向运盘] 段；缺省不打端点（零回归）。"""
    service = _zeri_service(tmp_path)
    calls: list[str] = []
    original = service.client.call
    service.client.call = lambda e, p: (calls.append(e) or original(e, p))  # type: ignore[method-assign]
    base = {"date": "1995-06-03", "time": "05:30", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}
    plain = service.run_tool("persiandirected", base, save_result=False)
    assert plain.ok is True, plain.error
    assert "/predict/persianchart" not in calls
    assert "directed_chart" not in plain.data
    assert "\n[指定日期向运盘]\n" not in plain.data["snapshot_text"]
    dated = service.run_tool("persiandirected", {**base, "datetime": "2026-09-01"}, save_result=False)
    assert dated.ok is True, dated.error
    assert "/predict/persianchart" in calls
    assert dated.data["directed_chart"]["chart"]["objects"]
    text = dated.data["snapshot_text"]
    assert "[指定日期向运盘]" in text and text.index("[指定日期向运盘]") > text.index("[波斯向运（Persian Directed）]")
    assert "向运太阳" in text
    export = dated.data["export_snapshot"]
    assert "指定日期向运盘" in export["section_titles_detected"]
    assert export["missing_selected_sections"] == [] and export["unknown_detected_sections"] == []


def test_qizhengelection_pan_emits_sections_and_data(tmp_path) -> None:
    """七政择日动盘（批 I-1b）：pan 出 [起盘信息]+[择日动盘]+[天象要素]，契约零缺零未知。"""
    service = _zeri_service(tmp_path)
    result = service.run_tool("qizhengelection", build_sample_payloads()["qizhengelection"], save_result=False)
    assert result.ok is True, result.error
    assert result.data["action"] == "pan"
    assert result.data["pan"]["planets"], "pan 原始数据必须带回"
    text = result.data["snapshot_text"]
    for section in ("[起盘信息]", "[择日动盘]", "[天象要素]"):
        assert section in text, section
    export = result.data["export_snapshot"]
    assert export["technique"]["key"] == "qizhengelection"
    assert export["missing_selected_sections"] == []
    assert export["unknown_detected_sections"] == []


def test_qizhengelection_eclipses_action(tmp_path) -> None:
    service = _zeri_service(tmp_path)
    payload = {**build_sample_payloads()["qizhengelection"], "action": "eclipses", "kind": "solar", "count": 2}
    result = service.run_tool("qizhengelection", payload, save_result=False)
    assert result.ok is True, result.error
    assert len(result.data["eclipses"]) == 2
    assert "[日月食搜索]" in result.data["snapshot_text"]
    assert result.data["export_snapshot"]["missing_selected_sections"] == []


def test_qizhengelection_azimuthsearch_requires_target(tmp_path) -> None:
    service = _zeri_service(tmp_path)
    payload = {**build_sample_payloads()["qizhengelection"], "action": "azimuthsearch"}
    result = service.run_tool("qizhengelection", payload, save_result=False)
    assert result.ok is False
    assert result.error.code == "tool.qizhengelection_missing_target"
    ok = service.run_tool("qizhengelection", {**payload, "targetAz": 180}, save_result=False)
    assert ok.ok is True, ok.error
    assert ok.data["hits"] and "[方位搜索]" in ok.data["snapshot_text"]


def test_qizhengelection_fails_loudly_on_error_envelope(tmp_path) -> None:
    """HTTP 200 + {'ResultCode':-1,'Result':'… failed'} 必须报错，绝不能静默变空结果。"""

    class FailingClient(FakeClient):
        def call(self, endpoint: str, payload: dict) -> dict:
            if endpoint == "/qizhengelection/eclipses":
                return {"ResultCode": -1, "Result": "eclipse search failed"}
            return super().call(endpoint, payload)

    settings = Settings(
        server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs"
    )
    service = HorosaSkillService(settings, client=FailingClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payload = {**build_sample_payloads()["qizhengelection"], "action": "eclipses"}
    result = service.run_tool("qizhengelection", payload, save_result=False)
    assert result.ok is False
    assert result.error.code == "tool.qizhengelection_failed"
    assert "eclipse search failed" in str(result.error.details.get("error"))


def test_qimenzeri_carries_qimen_sections_plus_three(tmp_path) -> None:
    """21 段 = 奇门 18 + 择日 3（v13：奇门侧多了条件段 日家占方）；八宫克应 是 default-off，
    既不该被检出也不该记为缺段。段表仍由 qimen 的 preset spread 派生 —— 单一真值源不变。"""
    service = _zeri_service(tmp_path)
    result = service.run_tool("qimenzeri", build_sample_payloads()["qimenzeri"], save_result=False)
    assert result.ok is True, result.error
    export = result.data["export_snapshot"]
    assert export["technique"]["key"] == "qimenzeri"
    assert len(export["technique"]["preset_sections"]) == 21
    assert "日家占方（古籍金函系）" in export["technique"]["preset_sections"]
    for title in ("择日搜索配置", "择日条件", "命中时辰"):
        assert title in export["section_titles_detected"], title
    assert "八宫克应" not in export["missing_selected_sections"], "default-off 段不得记为缺段"
    assert export["missing_selected_sections"] == []
    assert export["unknown_detected_sections"] == []


def test_qimenzeri_discloses_the_split_compute_authority(tmp_path) -> None:
    """展示盘走 ken、区间搜索走本地引擎 —— 结果必须逐项写明，不许含糊成「都是 ken 算的」。"""
    service = _zeri_service(tmp_path)
    result = service.run_tool("qimenzeri", build_sample_payloads()["qimenzeri"], save_result=False)
    assert result.data["compute_sources"] == {"scan": "local_calcDunJia", "pan": "kinqimen"}
    # 起盘时刻取 pick（两端各内缩 1 分钟的边界安全值），不是 start —— 用 start 会落到时辰边界外侧。
    assert result.data["pan_moment"] == "2028-04-01 19:01"


def test_qimenzeri_rejects_oversized_span(tmp_path) -> None:
    service = _zeri_service(tmp_path)
    payload = {**build_sample_payloads()["qimenzeri"], "endDate": "2029-04-08"}
    result = service.run_tool("qimenzeri", payload, save_result=False)
    assert result.ok is False
    assert result.error.code == "tool.qimenzeri_span_too_large"
    assert "HOROSA_JS_ENGINE_TIMEOUT_SECONDS" in result.error.details["hint"]


def test_zero_hit_search_still_emits_the_hit_section(tmp_path) -> None:
    """零命中时上游写的是「无满足条件」这句真话，而不是丢段 —— 所以**搜索/命中这几段不是条件段**，
    不进 AI_EXPORT_OPTIONAL_SECTIONS。登记成 optional 等于拿一个真实回归探测器换零收益。

    ⚠ 断言口径是「这几段不许在 optional 里」，不是「optional 集必须为空」：v13 起 qimenzeri
    从 qimen spread 继承了真·条件段 日家占方（vendored DunJiaCalc 只在 pan.isJinhan 时出，
    且那时常规段一个都不出）。把整集断言成空，会逼下一个人要么删掉真条件段的登记、要么删掉本测试。
    """
    from horosa_skill.exports.registry import AI_EXPORT_OPTIONAL_SECTIONS

    never_optional = {
        "tianxing": ("起盘信息", "搜索配置", "条件", "命中区间"),
        "qimenzeri": ("择日搜索配置", "择日条件", "命中时辰"),
    }
    for key, titles in never_optional.items():
        optional = set(AI_EXPORT_OPTIONAL_SECTIONS.get(key) or ())
        leaked = sorted(optional.intersection(titles))
        assert leaked == [], f"{key} 的零命中仍出段，不该登记为条件段: {leaked}"

    service = _zeri_service(tmp_path)

    class NoHits(FakeJsClient):
        def run(self, tool_name: str, payload: dict) -> dict:
            out = super().run(tool_name, payload)
            if tool_name == "qimenzeri" and str(payload.get("action")) == "scan":
                out["data"] = {**out["data"], "intervals": [], "hit_count": 0}
            return out

    service.js_client = NoHits()
    result = service.run_tool("qimenzeri", build_sample_payloads()["qimenzeri"], save_result=False)
    assert result.ok is True, result.error
    assert result.data["hit_count"] == 0
    assert "命中时辰" in result.data["export_snapshot"]["section_titles_detected"]


# --- 占时起课的经纬度前置（v0.26.1）---------------------------------------------------------


def test_time_cast_tools_demand_geo_before_hitting_nongli(tmp_path) -> None:
    """五个占时工具此前把 `lat: null` 发给 /nongli/time → Java 回 200001 → 用户只看到一句
    「本地 Horosa 后端返回 HTTP 500」。现在缺 lon/lat 就提前报结构化错误，指名缺哪个。

    ⚠️ 这个 bug 曾被误诊为环境问题：Java 的农历结果按**年**缓存，任何一次带 lat 的请求都会焐热该年，
    此后同年无 lat 请求全部成功 —— 所以它表现为时好时坏。复现必须换冷年份。
    """
    service = _zeri_service(tmp_path)
    cases = {
        "xiaoliuren": {"date": "2031-05-20", "time": "12:30:00", "zone": "+08:00", "school": "dao", "askEvent": "问事"},
        "feigong": {"date": "2031-05-20", "time": "12:30:00", "zone": "+08:00", "qiMode": "hour", "askEvent": "求财"},
        "xiaochengtu": {"date": "2031-05-20", "time": "12:30:00", "zone": "+08:00", "qiguaFa": "time", "askEvent": "问事"},
        "guice": {"date": "2031-05-20", "time": "12:30:00", "zone": "+08:00", "qiguaFa": "time", "askEvent": "问事"},
        "zhengchuan": {"date": "2031-05-20", "time": "12:30:00", "zone": "+08:00", "school": "tieban", "gender": 1},
    }
    for tool, payload in cases.items():
        result = service.run_tool(tool, {**payload, "agent_confirmed_settings": True}, save_result=False)
        assert result.ok is False, f"{tool}: 缺 lat 时不该成功"
        assert result.error.code == f"tool.{tool}_cast_geo_required", f"{tool}: {result.error.code}"
        assert "lat" in result.error.details["missing"], tool


def test_time_cast_geo_guard_names_only_what_is_missing(tmp_path) -> None:
    service = _zeri_service(tmp_path)
    payload = {
        "date": "2031-05-20", "time": "12:30:00", "zone": "+08:00", "lon": "121e28",
        "school": "dao", "askEvent": "问事", "agent_confirmed_settings": True,
    }
    result = service.run_tool("xiaoliuren", payload, save_result=False)
    assert result.error.details["missing"] == ["lat"], "给了 lon 就不该再报 lon"


def test_java_result_codes_are_translated_not_swallowed() -> None:
    """`HorosaApiClient.call` 从不看 ResultCode，两个语义完全不同的失败都长成同一句 HTTP 500。"""
    from horosa_skill.engine.client import _java_result_code_hint

    assert "经纬度" in _java_result_code_hint('{"ResultCode" : 200001, "Result" : "param error"}')
    assert "MongoDB" in _java_result_code_hint('{"ResultCode" : 9999, "Result" : "no.register.app"}')
    assert _java_result_code_hint('{"ResultCode" : 0, "Result" : {}}') == ""


def test_generic_9999_is_not_labelled_a_mongo_problem() -> None:
    """9999 是通用失败码，不是 no.register.app 的同义词。

    Windows 构建机实测：缺 lat 触发的上游字符串越界回的是
    `{"ResultCode": 9999, "Result": "begin 1, end 3, length 1"}`（不是 mac 侧看到的 200001）。
    只按码值贴「app 注册没读到（在 MongoDB 里）」，会把一个参数 bug 指去查 Mongo——正是本仓
    连着两轮在清的那类误诊。认不出就给中性提示，不替用户断案。
    """
    from horosa_skill.engine.client import _java_result_code_hint

    hint = _java_result_code_hint('{"ResultCode" : 9999, "Result" : "begin 1, end 3, length 1"}')
    assert "MongoDB" not in hint, f"不得把参数 bug 指去查 Mongo: {hint}"
    assert "不等于" in hint, f"要显式否掉「9999 == app 注册问题」这个等式: {hint}"
    assert "Result" in hint and "lat" in hint, "中性提示要指向 Result 原文并提醒核经纬度"


# --- tianxing 三个「用户拿到错答案」的 bug（v0.26.1）------------------------------------------


def test_tianxing_forwards_top_level_classical_options(tmp_path) -> None:
    """古典口径既可走 options 字典、也可走 BirthInput 继承的**顶层**同名字段（schema 逐个带描述）。
    v0.26.0 只读 options → 顶层写法被静默丢弃，搜索用默认口径跑，结果不同却零报错。"""
    service = _zeri_service(tmp_path)
    sent: list[dict] = []
    original = service.client.call

    def spy(endpoint: str, payload: dict) -> dict:
        if endpoint == "/electionscan/scan":
            sent.append(payload)
        return original(endpoint, payload)

    service.client.call = spy  # type: ignore[method-assign]
    payload = {**build_sample_payloads()["tianxing"], "combustOrb": 15, "termsVariant": "ptolemy",
               "siderealAyanamsa": "fagan_bradley", "precision": "minute"}
    assert service.run_tool("tianxing", payload, save_result=False).ok is True
    assert sent, "没有发出扫描请求"
    first = sent[0]
    assert first["combustOrb"] == 15, "顶层 combustOrb 被丢了"
    assert first["termsVariant"] == "ptolemy", "顶层 termsVariant 被丢了"
    # 快照会把 siderealAyanamsa 印出来，所以它必须真的进请求，否则输出在声称一个没用上的设置
    assert first["siderealAyanamsa"] == "fagan_bradley", "siderealAyanamsa 没进请求，但快照会印它"
    assert first["precision"] == "minute", "precision 是个文档化了却没接线的死旋钮"


def test_tianxing_options_dict_wins_over_top_level(tmp_path) -> None:
    service = _zeri_service(tmp_path)
    sent: list[dict] = []
    original = service.client.call
    service.client.call = lambda e, p: (sent.append(p) if e == "/electionscan/scan" else None) or original(e, p)  # type: ignore[method-assign,assignment]
    payload = {**build_sample_payloads()["tianxing"], "combustOrb": 15, "options": {"combustOrb": 9}}
    service.run_tool("tianxing", payload, save_result=False)
    assert sent[0]["combustOrb"] == 9, "显式 options 应压过顶层"


def test_tianxing_forwards_every_key_the_backend_actually_reads(tmp_path) -> None:
    """白名单窄于后端实读集 = 在客户端把已修好的后端 bug 重新装回去。

    election_scan.scan 把整个请求体交给 perchart.push_classical_request（`_cls_req = dict(data)`），
    后者实读 nodeExaltation/dignityDebilities/lotsDocReverse/orbSystem/luminaryOrbBonus/
    customTermsDay/customTermsNight 等键；上游 [F8] 那条注释记的正是「dignityDebilities/orbSystem
    等发了不生效」，后端收编修好了，而 skill 的白名单窄 7 键又把它们静默滤掉 ——
    schema 上带着描述、chart 工具上照常生效，唯独天星择日搜索里无声失效。
    """
    service = _zeri_service(tmp_path)
    sent: list[dict] = []
    original = service.client.call
    service.client.call = lambda e, p: (sent.append(p) if e == "/electionscan/scan" else None) or original(e, p)  # type: ignore[method-assign,assignment]
    backend_read_keys = {
        "nodeExaltation": 1, "dignityDebilities": 0, "lotsDocReverse": 1,
        "orbSystem": "lilly", "luminaryOrbBonus": 2, "customTermsDay": "egyptian",
        "customTermsNight": "ptolemy",
    }
    payload = {**build_sample_payloads()["tianxing"], **backend_read_keys}
    assert service.run_tool("tianxing", payload, save_result=False).ok is True
    assert sent, "没有发出扫描请求"
    for key, value in backend_read_keys.items():
        assert sent[0].get(key) == value, f"{key} 被白名单滤掉了，但后端实读它"


def test_tianxing_js_failure_never_becomes_a_fabricated_export(tmp_path) -> None:
    """JS 侧失败时旧实现只读 snapshot_text → None → format_source 回落 generated_template，
    产出一份拿 payload YAML 填出来的伪造导出，而 agent 被要求只依据 export_text 解读。"""
    service = _zeri_service(tmp_path)

    class SnapshotBroken(FakeJsClient):
        def run(self, tool_name: str, payload: dict) -> dict:
            if tool_name == "tianxing" and str(payload.get("action")) == "snapshot":
                return {"data": {"ok": False, "error": {"code": "snapshot_failed", "message": "boom"}},
                        "snapshot_text": ""}
            return super().run(tool_name, payload)

    service.js_client = SnapshotBroken()
    result = service.run_tool("tianxing", build_sample_payloads()["tianxing"], save_result=False)
    assert result.ok is False, "JS 快照失败必须报错，不能伪造出一份导出"
    assert result.error.code == "tool.tianxing_snapshot_failed"


def test_tianxing_stitch_failure_is_not_reported_as_zero_hits(tmp_path) -> None:
    service = _zeri_service(tmp_path)

    class StitchBroken(FakeJsClient):
        def run(self, tool_name: str, payload: dict) -> dict:
            if tool_name == "tianxing" and str(payload.get("action")) == "stitch":
                return {"data": {"ok": False, "error": {"code": "stitch_failed", "message": "boom"}}}
            return super().run(tool_name, payload)

    service.js_client = StitchBroken()
    result = service.run_tool("tianxing", build_sample_payloads()["tianxing"], save_result=False)
    assert result.ok is False, "缝合失败会变成一个看起来完全合理的「零命中」"
    assert result.error.code == "tool.tianxing_stitch_failed"


def test_tianxing_rejects_unparseable_inverted_and_oversized_windows(tmp_path) -> None:
    """旧守卫用 `span is not None` 判 → 解析不出来的日期形状**直接跳过上限**；倒置窗口得负数，
    `负数 > max` 恒 False 也能溜过去。而 JS 侧 wallToMs 照样能解析它们，于是一路跑到超时。"""
    service = _zeri_service(tmp_path)
    base = build_sample_payloads()["tianxing"]
    cases = [
        ({"startDate": "2028-04-01T00:00", "endDate": "2032-12-31"}, "tool.tianxing_bad_window"),
        ({"startDate": "2028-04-01 10:00", "endDate": "2032-12-31"}, "tool.tianxing_bad_window"),
        ({"startDate": "2028-12-31", "endDate": "2028-01-01"}, "tool.tianxing_inverted_window"),
        ({"startDate": "2028-01-01", "endDate": "2038-01-01"}, "tool.tianxing_span_too_large"),
    ]
    for override, expected in cases:
        result = service.run_tool("tianxing", {**base, **override}, save_result=False)
        assert result.ok is False, f"{override} 不该放行"
        assert result.error.code == expected, f"{override}: {result.error.code}"


def _service(tmp_path) -> HorosaSkillService:
    """离线技法服务（FakeClient + FakeJsClient）——技法卡/技法报告用例共用。"""
    settings = Settings(
        server_root="http://127.0.0.1:9",
        chart_server_root="http://127.0.0.1:9",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def test_technique_card_rides_every_technique_response_and_survives_response_view(tmp_path) -> None:
    """技法卡必须**随每次输出**给出，且 `response_view` 精简时也留着。

    精简模式恰恰是最需要溯源的场景（快照都不回了），把卡一起裁掉等于让它在唯一需要它的时候消失。
    """
    service = _service(tmp_path)
    payload = build_sample_payloads()["tarot"]
    result = service.run_tool("tarot", payload, save_result=True)
    card = result.data["technique_card"]
    assert card["schema"] == "horosa.skill.technique_card.v1"
    assert card["tool"] == "tarot"
    assert card["technique"]["key"] == "tarot"
    assert card["versions"]["skill"] and card["versions"]["export_settings"] == 14
    assert card["refs"]["run_id"] == result.memory_ref.run_id

    slim = service.run_tool("tarot", {**payload, "response_view": "titles"}, save_result=False)
    assert slim.data["snapshot_text"] == "", "response_view 该裁的还是要裁"
    assert slim.data["technique_card"]["tool"] == "tarot", "但技法卡不裁"


def test_technique_card_can_be_switched_off(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOROSA_TECHNIQUE_CARD", "0")
    service = _service(tmp_path)
    result = service.run_tool("tarot", build_sample_payloads()["tarot"], save_result=False)
    assert "technique_card" not in result.data


def test_technique_report_covers_a_whole_session_and_needs_no_ai_report(tmp_path) -> None:
    """与咨询报告的分界线：这份不需要 ai_report，也**永远**不含解读。"""
    service = _service(tmp_path)
    samples = build_sample_payloads()
    group_id = None
    for tool in ("tarot", "tongshefa"):
        result = service.run_tool(tool, samples[tool], save_result=True, group_id=group_id)
        group_id = group_id or result.group_id

    report = service.technique_report({"group_id": group_id, "format": "markdown"})
    assert report["ok"] is True
    assert report["technique_count"] == 2
    assert report["scope"] == "group"
    artifact = Path(report["artifact_path"])
    assert artifact.is_file() and artifact.stat().st_size > 0
    text = artifact.read_text(encoding="utf-8")
    assert "# 会话技法依据报告" in text
    assert "## 一致性检查" in text
    # 确定性文档：不许出现任何「解读/建议」字样的伪装——它不是咨询报告。
    assert "ai_report" not in text


def test_technique_report_refuses_cleanly_when_nothing_has_been_run(tmp_path) -> None:
    service = _service(tmp_path)
    with pytest.raises(ToolValidationError) as excinfo:
        service.technique_report({"format": "markdown"})
    assert excinfo.value.code == "report.technique.no_cards"


def test_technique_report_rejects_an_unknown_format(tmp_path) -> None:
    service = _service(tmp_path)
    with pytest.raises(ToolValidationError) as excinfo:
        service.technique_report({"format": "html"})
    assert excinfo.value.code == "report.technique.invalid_format"


# --- v0.28.0（上游 v3.9.2）：干支合冲 / 选中时刻星盘 ---------------------------------------------


def test_bazi_hechong_lines_mirror_the_upstream_relline_format() -> None:
    """[干支合冲] 行格式金标——逐字镜像上游 BaZi.js relLine：`{cell}（{zhu}） …→{key}`，分号连接，
    全空不产段。字段来自后端 fourColumns（纯排版，零新计算）。"""
    from horosa_skill.service import _build_bazi_hechong_lines

    four = {
        "ganHe": {"甲己合土": [{"cell": "甲", "zhu": "年干"}, {"cell": "己", "zhu": "时干"}]},
        "ziCong": {"子午冲": [{"cell": "子", "zhu": "年支"}, {"cell": "午", "zhu": "日支"}]},
        "ziXing": {},
    }
    lines = _build_bazi_hechong_lines(four)
    assert lines == [
        "干合：甲（年干） 己（时干）→甲己合土",
        "支冲：子（年支） 午（日支）→子午冲",
    ]
    assert _build_bazi_hechong_lines({}) == [], "全空不产段（上游 heCongLines.length 同判）"


def test_bazi_snapshot_carries_hechong_between_fenye_and_dayun(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.run_tool("bazi_birth", build_sample_payloads()["bazi_birth"], save_result=False)
    assert result.ok is True
    titles = [s["title"] for s in result.data["export_snapshot"]["sections"]]
    assert "干支合冲" in titles
    body = next(s["body"] for s in result.data["export_snapshot"]["sections"] if s["title"] == "干支合冲")
    assert "干合：甲（年干） 己（时干）→甲己合土" in body


def test_tianxing_selected_moment_chart_is_conditional_on_hits(tmp_path) -> None:
    """[选中时刻星盘]（v3.9.2）：有命中→补铸 /chart 并入（headerless 子段头 `· X`）；零命中→不产段
    且不误报 missing（条件段双登记）。"""
    service = _service(tmp_path)
    payload = build_sample_payloads()["tianxing"]
    hit = service.run_tool("tianxing", payload, save_result=False)
    assert hit.ok is True
    export = hit.data["export_snapshot"]
    assert "选中时刻星盘" in export["section_titles_detected"]
    body = next(s["body"] for s in export["sections"] if s["title"] == "选中时刻星盘")
    assert body.startswith("选中命中：")
    assert "· 起盘信息" in body, "整张盘 headerless 并入：子段头必须已转 `· X`，防被顶层拆段"
    assert "\n[" not in f"\n{body}", "段内不得残留顶层段头"

    # 零命中窗口（FakeClient 对 1999 起点回空 intervals）→ 段自然缺席、契约仍干净。
    miss = service.run_tool(
        "tianxing", {**payload, "startDate": "1997-01-02", "endDate": "1997-01-05"}, save_result=False
    )
    assert miss.ok is True
    miss_export = miss.data["export_snapshot"]
    assert "选中时刻星盘" not in miss_export["section_titles_detected"]
    assert miss_export["missing_selected_sections"] == []


# --- v0.28.0 B3：合参 horosa_hecan --------------------------------------------------------------


def test_hecan_routes_and_returns_a_synthesis_template(tmp_path) -> None:
    """合参 = 模板不是终稿：逐技法证据表 + 口径一致性 + ai_fillable 综合槽，分歧披露写进 instructions。"""
    service = _service(tmp_path)
    result = service.hecan({
        "query": "综合奇门和六壬分析当前事业局势",
        "birth": build_sample_payloads()["qimen"],
        "save_result": True,
    })
    assert result["ok"] is True
    assert result["schema"] == "horosa.skill.hecan.v1"
    assert set(result["selected_tools"]) == {"qimen", "liureng_gods"}
    rows = result["synthesis_contract"]["ai_fillable"]["cross_validation"]
    assert [r["tool"] for r in rows] == result["selected_tools"]
    assert all(r["conclusion"] == "" for r in rows), "结论槽必须留白给 AI——预填即伪造"
    instructions = "\n".join(result["synthesis_contract"]["instructions"])
    assert "分歧" in instructions and "不许平均" in instructions
    assert "只准引用" in instructions or "不许引用未导出" in instructions
    # 证据是指针不是全文（memory_show 取全量），响应不背 N 份快照。
    for tech in result["techniques"]:
        assert tech["evidence_pointer"]["read_with"] == "horosa_memory_show"
        assert "export_snapshot" not in tech
    assert result["consistency"]["setting_conflicts"] == []


def test_hecan_accepts_explicit_tools_and_caps_them(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.hecan({
        "query": "全面看这个人",
        "tools": ["bazi_birth", "ziwei_birth", "liureng_gods", "qimen", "taiyi", "jinkou", "sixyao"],
        "max_tools": 3,
        "birth": build_sample_payloads()["bazi_birth"],
        "save_result": False,
    })
    assert result["ok"] is True
    assert result["selected_tools"] == ["bazi_birth", "ziwei_birth", "liureng_gods"], "上限必须截断"


def test_hecan_routing_failure_passes_through_recovery(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.hecan({"query": "呵呵", "save_result": False})
    assert result["ok"] is False
    assert result["code"], "路由失败必须透出结构化错误，不包一层假成功"


def test_birthinput_declares_upstream_classical_echo_whitelist() -> None:
    """批 I-6 锁步：上游 helper.py 古典回显白名单（45 键）必须全部在 BirthInput typed 声明——
    typed 化是可发现性契约（agent 只能看见声明过的旋钮），删声明=旋钮对 agent 隐形。
    新键到达由重同步侦察负责；本测试防「已声明键被误删」的回退。"""
    from horosa_skill.schemas.tools import BirthInput

    upstream_echo_keys = {
        "termsVariant", "leoBoundFirst", "geminiBoundEmended", "triplicity", "lotReversal",
        "westNodeType", "sectBuffer", "houseCuspAdvance", "cazimiOrb", "combustOrb", "underBeamsOrb",
        "vocMode", "vocIncludeOuter", "starOrb", "starOrbMode", "antisciaOrb", "viaCombustaVariant",
        "lotsDocReverse", "nodeExaltation", "combustOwnChariotExempt", "westLilithType",
        "topocentricMoon", "stationMarking", "hermeticLotsReversal", "erosConstruction",
        "lotFortuneVariant", "lotFatherCombustAlt", "lotProjection", "dignityDebilities",
        "almutenTripMode", "planetaryHourMethod", "orbSystem", "luminaryOrbBonus",
        "aspectIncludeCusps", "aspectIncludeLots", "aspectIncludeMidpoints", "solarReturnVariant",
        "returnLatitudeMode", "vulcanCalc", "customTermsDay", "customTermsNight",
        "siderealAyanamsa", "userAyanT0", "userAyanDeg", "orbs", "orbScale",
    }
    declared = set(BirthInput.model_fields.keys())
    missing = sorted(upstream_echo_keys - declared)
    assert missing == [], f"BirthInput 缺少上游古典白名单键的 typed 声明：{missing}"


# ---- v0.36.0 A5 分后端就绪：Java 挂了不许先杀健康的 chart 服务再全量重启 ----
def _java_cooldown_service(tmp_path, runtime_manager: FakeRuntimeManager) -> tuple[HorosaSkillService, ProbeClient]:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    java_client = ProbeClient(probe_ok=False)  # Java 探针失败
    service = HorosaSkillService(
        settings,
        client=java_client,
        chart_client=FakeClient(),  # chart 服务健康（probe True）
        store=MemoryStore(settings),
        js_client=FakeJsClient(),
        runtime_manager=runtime_manager,
    )
    return service, java_client


def test_java_endpoint_fails_fast_during_cooldown_and_chart_tool_stays_up(tmp_path) -> None:
    from horosa_skill.testing_payloads import build_sample_payloads

    runtime_manager = FakeRuntimeManager(cooldown=90.0)
    service, java_client = _java_cooldown_service(tmp_path, runtime_manager)
    payloads = build_sample_payloads()

    bazi = service.run_tool("bazi_birth", payloads["bazi_birth"], save_result=False)
    assert bazi.ok is False
    assert bazi.error is not None and bazi.error.code == "runtime.java_backend_unavailable"
    assert bazi.error.details["retry_after_seconds"] == 90.0
    assert "doctor" in bazi.error.details["hint"]
    assert runtime_manager.started == 0  # 冷却期内：不重启、更不 stop 健康的 chart 服务
    assert java_client.probe_calls == 1

    chart = service.run_tool("chart", payloads["chart"], save_result=False)
    assert chart.ok is True, chart.error
    assert runtime_manager.started == 0


def test_java_endpoint_starts_once_and_does_not_restart_again_when_start_comes_back_degraded(tmp_path) -> None:
    from horosa_skill.testing_payloads import build_sample_payloads

    runtime_manager = FakeRuntimeManager(degraded=True, cooldown=0.0)
    service, _java_client = _java_cooldown_service(tmp_path, runtime_manager)
    bazi = service.run_tool("bazi_birth", build_sample_payloads()["bazi_birth"], save_result=False)
    assert bazi.ok is False
    assert bazi.error is not None and bazi.error.code == "runtime.java_backend_unavailable"
    # 此前：start(degraded) → 调用连不上 → connection_retry 再 start 一次（又杀一次 chart）。现在只起一次。
    assert runtime_manager.started == 1
