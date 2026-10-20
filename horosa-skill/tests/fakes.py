"""测试替身：按端点回固定载荷的 FakeClient、记录调用的 CaptureClient、按 JS 工具回桩的 FakeJsClient。

原先住在 test_service.py 里，十七个测试文件从那里导入；v0.41.1 挪到这里（pytest 不收集它）。新替身也放这里，别再从测试模块互相导入。"""
from __future__ import annotations

import json
from pathlib import Path

from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.engine.js_client import HorosaJsEngineClient

# 上游 v3.11 星运四键：/astroextra/{ephemeris,prenatal_syzygy,progressions} 回**真实**响应（vendored v3.11.1+ 实例实抓
# 后裁剪，见 fixtures/sync311_newtools_live.json 的 _comment）。桩管形状；值级真相归 test_sync311_newtools.py 的上游 JS 金标。
_SYNC311_SAMPLE = json.loads(
    (Path(__file__).parent / "fixtures" / "sync311_newtools_live.json").read_text(encoding="utf-8")
)["scenarios"]["sample"]
_SYNC311_ASTROEXTRA_STUBS = {
    "/astroextra/ephemeris": _SYNC311_SAMPLE["ephemeris"],
    "/astroextra/prenatal_syzygy": _SYNC311_SAMPLE["prenatal_syzygy"],
    "/astroextra/progressions": _SYNC311_SAMPLE["progressions"],
}


class FakeClient(HorosaApiClient):
    def __init__(self) -> None:
        super().__init__("http://fake")

    def probe(self, endpoint: str = "/common/time", payload: dict | None = None) -> bool:
        return True

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint in _SYNC311_ASTROEXTRA_STUBS:
            return json.loads(json.dumps(_SYNC311_ASTROEXTRA_STUBS[endpoint]))
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
                    # 真实 /chart 的 objects 里带四轴（上升/天顶…）——小限摘要起点、keypoints 命位等按它取；桩不许比真实窄。
                    {"id": "Asc", "house": "House1", "sign": "Virgo", "signlon": 15.0, "lon": 165.0},
                    {"id": "MC", "house": "House10", "sign": "Gemini", "signlon": 12.0, "lon": 72.0},
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
        if endpoint == "/common/inversebazi":
            # Java CommController.inverseBazi：Dates=["YYYY-MM-DD HH:mm:ss", …]（Desc=true 向过去回推）
            return {"Dates": ["2024-02-15 15:30:00", "1964-02-29 15:30:00", "1904-03-15 15:30:00"][: int(payload.get("Count") or 3)]}
        if endpoint == "/qizheng/moira":
            # Java QizhengMoiraRuleService.analyze 响应形状（weakSolid / yearStars.birth|transit / transitYearStars），
            # 值取自上游 guolaoWeakSolidBirthStars.test.js 夹具。
            return {
                "weakSolid": {"houses": [
                    {"house": "命宫", "label": "实", "solid": True, "weakPillars": [], "solidPillars": ["年", "日"]},
                    {"house": "财帛", "label": "虚", "weak": True, "weakPillars": ["月"], "solidPillars": []},
                ]},
                "yearStars": {
                    "birth": {"yearPole": "丙午", "planetRows": [{"star": "木", "changeTo": "天贵", "items": ["岁星"]}, {"star": "火", "changeTo": "天刑", "items": []}]},
                    "transit": {"yearPole": "", "planetRows": [{"star": "火", "changeTo": "天刑", "items": []}]},
                },
                "transitYearStars": [{"name": "岁星", "star": "木", "shortName": "岁", "quality": "旺", "zi": "寅", "signName": "析木"}],
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
            # 真后端只回裸 {age, ageCycle, year}（tests/test_sync311_sanshi.py 的 live 断言）；替身照真形状回。
            return {"year": "甲子", "age": 38, "ageCycle": 38}
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
        from horosa_skill.exports.registry import (
            AI_EXPORT_OPTIONAL_SECTIONS as _OPTIONALS,
        )
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


# ── v0.40 mingli：八字 / 紫微 / 宿占改走 vendored 上游 builder（tools/baziLocal.js / ziweiBirth.js / suzhan.js）。
# 桩文本**逐字节选自真引擎输出**（不手编）：八字 = testing_payloads east_birth 同盘（2028-04-06 09:33 上海·性别未知）；
# 紫微 = 1985-11-07 23:30 上海男命 live 实出；宿占 = 1990-05-15 10:30 上海 live 实出（Java /chart + 八字公式起盘）。
# 段头即真 builder 段头；桩只管形状，值级真相归 tests/test_sync311_mingli.py 的真引擎金标（§5 规则 6）。
_BAZI_LOCAL_STUB_TEXT = "\n".join([
    "[起盘信息]", "日期：2028-04-06 09:33:00", "时区：+08:00", "经纬度：121e28 31n13", "性别：未知", "时间算法：真太阳时",
    "时间基准：真太阳时(经度+均时差校正)；晚子时归次日：是；23 点换日：是", "节气修正：不调整节气", "命造：乾造",
    "农历：二〇二八年三月十二", "生肖：猴（岁首=立春）", "直接时间：2028-04-06 09:33:00　真太阳时：2028-04-06 09:36:30",
    "清明后第3天； 调候：无", "",
    "[四柱与三元]", "| 柱 | 干支 | 藏干 | 十神 | 纳音 | 纳音长生 | 星运 | 自坐 | 空亡 |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    "| 年柱 | 戊申 | 庚劫、壬伤、戊印 | 印·劫 | 大驿土 | 长生 | 临官 | 病 | 寅卯 |",
    "| 月柱 | 丙辰 | 戊印、乙才、癸食 | 官·印 | 沙中土 | 墓 | 养 | 冠带 | 子丑 |",
    "| 日柱 | 辛酉 | 辛比 | 日元·比 | 石榴木 | 胎 | 帝旺 | 帝旺 | 子丑 |",
    "| 时柱 | 癸巳 | 丙官、庚劫、戊印 | 食·官 | 长流水 | 绝 | 长生 | 绝 | 午未 |",
    "胎元：丁未，干十神:杀，支十神:枭", "命宫：庚申，干十神:劫，支十神:劫（起法：通行版）", "身宫：壬戌，干十神:伤，支十神:印", "十二串宫：申", "",
    "[神煞（四柱与三元）]", "年柱：整柱=文昌贵人、福星贵人、德秀贵人、月厌；天干=无；地支=无；太岁=无",
    "日柱：整柱=词馆、禄神、红艳、桃花、德秀贵人、阴差阳错、八专、四废；天干=无；地支=无；太岁=无", "",
    "[五行力量]", "（通行示例权重：天干100/本气100/中气60/余气30/月令×1.5）", "| 五行 | 占比 |", "| --- | --- |",
    "| 木 | 7.7% |", "| 火 | 17.2% |", "| 土 | 26.6% |", "| 金 | 30.9% |", "| 水 | 17.6% |", "最旺：金　最弱：木",
    "日主金：身强（同党印比 57.5% · 异党 42.5%）", "",
    "[格局·用神]", "当前主用流派：传统综合（各派取用可异，下列多派对照）", "格局：正印格（月令印·本气透干）", "",
    "[盲派结构]", "（象法·参考，与扶抑/格局体系不同）", "宾主：年宾(戊申) 月宾(丙辰) 日主(辛酉) 时宾(癸巳)", "",
    "[月令司令（分野）]", "版本：通行版", "节后 1.8 日，当令：乙（余气）", "",
    "[干支合冲]", "干合：丙（月） 辛（日）→丙辛合水；丁（胎） 壬（身）→丁壬合木；戊（年） 癸（时）→戊癸合火", "",
    "[大运]", "起运：出生后9年7个月20天0小时起运", "| 步序 | 起运年 | 干支 |", "| --- | --- | --- |",
    "| 第2步 | 2037 | 丁巳 |", "| 第3步 | 2047 | 戊午 |", "",
    "[流年行运概略]", "| 板块 | 起始年 | 起始年龄 | 大运 | 流年 |", "| --- | --- | --- | --- | --- |",
    "| 板块1 | 2037 | 10岁 | 丁巳 | 2037-丁巳 2038-戊午 2039-己未 2040-庚申 2041-辛酉 2042-壬戌 2043-癸亥 2044-甲子 2045-乙丑 2046-丙寅 |",
])
_ZIWEI_BIRTH_STUB_TEXT = "\n".join([
    "[起盘信息]", "日期：1985-11-07 23:30:00", "时区：+08:00", "经纬度：121e28 31n13", "性别：男", "时间算法：真太阳时",
    "真太阳时：1985-11-07 23:50:28", "四化流派：通用·飞星", "生年天干：乙", "命宫：命宫（丙戌）", "命宫天干：丙",
    "四柱：乙丑 丁亥 辛亥 戊子", "命主：巨门", "身主：天相", "命局：阴男 土五局", "",
    "[宫位总览]", "| 宫位 | 干支 | 大限 | 星曜（四化括注） |", "| --- | --- | --- | --- |",
    "| 命宫·胎 | 丙戌 | 5~14 | 廉贞（命宫忌，自化忌）·旺、天府·庙、文昌（命宫科，自化科）·陷、铃星·庙 |",
    "| 财帛宫·冠带 | 壬午 | 45~54 | 紫微（生年科，自化权）·庙、咸池、天厨 |", "",
    "[身宫]", "身宫落命宫（丙戌）", "",
    "[来因宫]", "兄弟宫（乙酉）", "",
    "[八字大运]", "| 起运虚岁 | 起始年份 | 大运干支 |", "| --- | --- | --- |", "| 1 | 1985 | 丙戌 |", "",
    "[命中格局]", "府相朝垣（富贵·破）：天府天相于三方来朝命垣，仓廪充盈，衣食丰足，一生平稳得贵。", "",
    "[运限概览]", "全大限 × 流年一览(公历年与干支由代码算出,禁自行推算):", "| 虚岁 | 宫位 | 宫干支 | 该限流年（公历年-干支） |",
    "| --- | --- | --- | --- |",
    "| 5~14 | 命 | 丙戌 | 1989-己巳、1990-庚午、1991-辛未、1992-壬申、1993-癸酉、1994-甲戌、1995-乙亥、1996-丙子、1997-丁丑、1998-戊寅 |",
    "要某一年/某月的完整流曜与四化落宫,请在「挂载设置 → 运限」里选定年月(或直接说出年份)。",
])
_SUZHAN_STUB_TEXT = "\n".join([
    "[起盘信息]", "日期：1990-05-15 10:30:00", "时区：+08:00", "经纬度：121e28 31n14", "宿法：荀爽距星(19年测)", "人事十二宫起盘：八字公式起盘", "",
    "[宿盘宫位与二十八宿星曜]", "| 宫位 | 二十八宿 | 星曜 |", "| --- | --- | --- |",
    "| 戌—降娄—白羊座—第10宫 | 壁、奎 | 福点 5˚壁50分、金 0˚奎21分 |",
    "| 酉—大梁—金牛座—第11宫 | 奎、娄、胃 | 中天 16˚奎3分、水 7˚娄58分、日 10˚胃54分 |",
    "| 未—鹑首—巨蟹座—第1宫 | 井 | 木 4˚井43分 |",
])


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
            from horosa_skill.exports.registry import (
                AI_EXPORT_PRESET_SECTIONS as _PRESETS,
            )

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
                    # 三式择时回传 vendored splitSanshiOptions 的三家拆分（真拆分由 tests/test_sync311_sanshiunited.py
                    # 跑真 JS 守）；桩按同形回：六壬 / 奇门各取所属键、太乙 taiyiAccum → tn。
                    **({"option_split": {
                        "liureng": {k: v for k, v in (payload.get("options") or {}).items()
                                    if k in ("guirengType", "yueMode", "yinyangSystem", "after23NewDay", "lateZiHourUseNextDay")},
                        "qimen": {k: v for k, v in (payload.get("options") or {}).items()
                                  if k in ("paiPanType", "qijuMethod", "school", "timeAlg", "after23NewDay", "lateZiHourUseNextDay")},
                        "taiyi": ({"tn": (payload.get("options") or {})["taiyiAccum"]}
                                  if "taiyiAccum" in (payload.get("options") or {}) else {}),
                    }} if technique == "sanshizeri" else {}),
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
            from horosa_skill.exports.registry import (
                AI_EXPORT_PRESET_SECTIONS as _PRESETS,
            )

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
            # 六爻层（tools/liuyao.js = 上游 regenerateSixyaoSnapshot 无头路径；sync311 wave 3b 起整份快照 = vendored
            # buildGuaSnapshotText）离线替身：各段正文取自 vendored 引擎对本文件 FakeClient /nongli/time 桩的真实输出
            # （以时起卦 = buildTimeGua → 泽天夬、三爻动；段行节选）。段头取真 preset（漂移即红），段序 = builder 实际产段
            # 顺序（GuaZhanMain.js:219-385：[卦辞与断语]/[判语库·参考诀表] 在 [断诀命中]/[占类断语] 之前）；
            # 无头卦无 guaDesc → [卦辞与断语] 只有段头、紧接下一段头（上游同形）。
            # 未给 lines = 以时起卦 → 回卦线；给了 lines = 手动摇卦 → 原样回显。
            from horosa_skill.exports.registry import (
                AI_EXPORT_PRESET_SECTIONS as _PRESETS,
            )

            time_cast = not payload.get("lines")
            names = ["子水妻财", "寅木官鬼应", "辰土兄弟", "亥水妻财", "酉金子孙世", "未土兄弟"]
            lines = (
                [{"value": v, "change": i == 2, "god": None, "name": names[i]} for i, v in enumerate([1, 1, 1, 1, 1, 0])]
                if time_cast else payload.get("lines")
            )
            rec = payload.get("record") or {}
            bodies = {
                "起盘信息": (
                    f"日期：{rec.get('date')} {rec.get('time')}\n时区：{rec.get('zone')}\n经纬度：{rec.get('lon')} {rec.get('lat')}\n"
                    "求测人性别：男\n起卦时间：2028-04-06 09:33:00 庚午时\n干支：年丙午 月辛卯 日戊辰 时庚午\n旬空：月空午未 日空戌亥"
                ),
                "卦象": (
                    "本卦：泽天夬  坤宫土\n互卦：乾为天  乾宫金\n之卦(变卦)：兑为泽  兑宫金\n"
                    "错卦(阴阳全变)：山地剥  乾宫金\n综卦(上下颠倒)：天风姤  乾宫金"
                ),
                "六爻与动爻": (
                    "第1爻：阳爻（静），爻名:子水妻财\n第3爻：阳爻（动），爻名:辰土兄弟\n"
                    "之卦(变卦)逐爻（初→上）：\n第1爻：阳爻，爻名:巳火父母"
                ),
                "断卦结构": (
                    "流派：通用（卜筮正宗口径）\n卦序：坤宫·五世(世5应2)\n占测：自身/综合运势　用神：世(5爻)\n"
                    "| 爻 | 六神 | 地支 | 五行 | 六亲 | 世应 | 旺衰 | 状态 | 伏神 | 神煞 |\n"
                    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
                    "| 第1爻 | 勾陈 | 子 | 水 | 妻财 | — | 休 | 岁破,入墓 | — | 将星 |"
                ),
                "卦辞与断语": "",
                "判语库·参考诀表": "◆ 诸爻持世诀\n父母持世：主身劳心累、利文书房产长辈;求子嗣、求财较费力",
                "断诀命中": (
                    "三层环境：太岁午(岁破子)　月建卯(月破酉)　日建辰(日破戌)\n"
                    "日辰纳音：大林木(木)\n应期·用神值日(得信/应事)：酉[时/日]"
                ),
                "占类断语": "历史占例：汉高祖欲拜韩信为将卜得,知有王佐之才也\n断语·总断门第一·孙膑：孙膑总断歌",
            }
            assert set(bodies) == set(_PRESETS["sixyao"]), "sixyao preset drifted: refresh this fake from the vendored builder"
            blocks = [f"[{title}]\n{body}" if body else f"[{title}]" for title, body in bodies.items()]
            text = "\n\n".join(blocks).replace("[卦辞与断语]\n\n[判语库·参考诀表]", "[卦辞与断语]\n[判语库·参考诀表]")
            return {
                "lines": lines,
                "time_cast": time_cast,
                "current_gua": {"index": 53, "name": "泽天夬"} if time_cast else None,
                "snapshot_text": text,
                "data": {"doctrine_loaded": True, "settings_ignored": [], "settings_invalid": [], "warnings": []},
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
        if tool_name == "bazi_local":
            # 八字本地优先（tools/baziLocal.js）：Java 回退路径（给了 java_result）标 local=False，同真工具。
            return {
                "snapshot_text": _BAZI_LOCAL_STUB_TEXT,
                "data": {
                    "ok": True,
                    "local": not payload.get("java_result"),
                    "gender": "Male",
                    "bazi": {
                        "gender": "Male",
                        "fourColumns": {k: {"ganzi": gz} for k, gz in (("year", "戊申"), ("month", "丙辰"), ("day", "辛酉"), ("time", "癸巳"))},
                        "nongli": {"year": "二〇二八", "month": "三月", "day": "十二", "birth": "2028-04-06 09:36:30"},
                    },
                },
            }
        if tool_name == "ziwei_birth":
            # 紫微编排（tools/ziweiBirth.js）两段式：prepare 回流派四化表，finalize 回盘 + 快照。
            if payload.get("action") == "prepare":
                return {"data": {"ok": True, "sihua": None, "school": "beipai", "localEngine": False}, "warnings": []}
            result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
            return {
                "data": {"ok": True, "chart": result.get("chart"), "patterns": result.get("patterns") or [],
                         "school": "beipai", "localEngine": False, "localApplied": False, "localError": None},
                "text": _ZIWEI_BIRTH_STUB_TEXT,
                "warnings": [],
            }
        if tool_name == "suzhan":
            return {"text": _SUZHAN_STUB_TEXT, "data": {"ok": True, "nongliHour": "巳"}}
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
            from horosa_skill.exports.registry import (
                AI_EXPORT_PRESET_SECTIONS as _PRESETS,
            )

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
        if tool_name == "acg_section":
            # 形状同真工具 tools/acgSection.js（vendored acgSnapshot.buildAcgSectionText）；正文 = 真 builder 在本桩
            # /location/acg 两星数据上的逐字输出（值级真相由 tests/test_sync311_western.py 的真 JS 用例守）。
            planets = ((payload.get("acgData") or {}).get("planets") or {})
            if not planets:
                return {"text": ""}
            return {"text": (
                "【占星地图】\n口径 本体(in-mundo·真黄纬) · 坐标系 地心\n主要行星角化线(中天/天底=经线;上升/下降取赤道附近代表点):\n"
                "- 太阳:MC 120.50°E / IC 59.50°W / ASC — / DSC —\n- 月亮:MC 30.00°E / IC 150.00°W / ASC — / DSC —"
            )}
        if tool_name == "horary" and payload.get("action") == "backend_fields":
            # 形状同真工具 tools/horary.js action=backend_fields；值 = 上游 horarySchools.js classical 档经
            # horaryBackendFields（hsys 2 Regiomontanus / 托勒密界经典传本 / 七政 / 福点不反转 / Ptolemy 三分集）。
            return {"tool": "horary", "school": "classical", "data": {
                "ok": True, "school": "classical", "backend_overrides": [],
                "backendFields": {"hsys": 2, "termsVariant": 2, "tradition": 1, "lotReversal": 0, "triplicity": "Ptolemaic"},
            }}
        if tool_name == "election" and payload.get("action") == "resolve_params":
            # 形状同真工具 tools/election.js action=resolve_params（现代主流档：宫制不联动 schoolHsys=None）。
            return {"tool": "election", "data": {
                "ok": True, "effective": {"pdTimeKey": "Ptolemy"}, "school": payload.get("school") or "modern_main",
                "schoolHsys": None, "params_applied": [], "params_global": [], "params_ignored": [], "invalid_inputs": [],
            }}
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
        if tool_name == "sanshiunited":
            # 三式合一（v3.11.x sanshi 同步）：快照由 vendored 上游 buildSanShiUnitedSnapshotText 产出（段头【】、builder 段序）。
            # 段体节选自真引擎在 2026-09-24 10:57 上海盘上的 live 输出；段名逐个对真 preset 断言（不许漂）。
            # live builder 的条件段（挂载重算顶段「奇门遁甲」、给了 ziweiSihua 才出的「紫微四化」、本盘未命中的
            # 太乙博弈/命法/命宫行限与空亡真假…占断向导）桩也不产。逐字真值由 tests/test_sync311_sanshiunited.py 的 live 回放守。
            from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS as _PS3

            blocks = [
                ('起盘信息', '农历：丙午年八月十四\n直接时间：2026-09-24 10:57'),
                ('概览', '局数：阴遁一局中元\n旬首：甲午'),
                ('太乙', '盘式：時計太乙\n古法公式：太乙統宗'),
                ('太乙主客定算', '主算：3；無天，二曜虛蝕、五緯失度、慧孛飛流、霜雹為害；無地，有崩地震、川竭蝗蝻之象；純陽\n主将：艮宫（3）'),
                ('太乙八门与宿曜', '金函玉镜：門：巽休、震生、艮傷、坎杜、乾景、兌死、坤驚、離開；星：坎太乙、離攝提、艮軒轅、兌招搖、乾天符、中青龍、巽咸池、震太陰、坤天乙\n值日宿：軫'),
                ('太乙断法', '三门：三門不具。\n五将：掩。五將不發。'),
                ('太乙七大兵法', '雷公入水：巽\n临津问道：坤'),
                ('太乙十六宫', '子：始击、客大、飞鸟、三风、八风\n丑：民基'),
                ('大六壬', '一课：辛申天空\n二课：申午勾陈'),
                ('六壬大格', '1. 重审\n重审下凌上，子逆臣不恭。'),
                ('六壬小局', '1. 三奇\n三奇用旬行，两处共一名。'),
                ('六壬参考', '1. 旺孕\n行年旺相神，夫妇三合群。'),
                ('六壬概览', '1. 元武决\n元武亥子辰，临卯酉盗伤。加午未迁官，推详莫妄陈。'),
                ('十二盘式', '盘式：退间传式\n月将：辰；占时：午；位序：前十'),
                ('常用神煞', '日德：巳（避凶中正、逢凶化吉）\n日禄：酉（入课传）（食禄、身体、力量）'),
                ('年月神煞', '（年神＝四利三元序）\n月建：酉（入课传）'),
                ('课体结构', '时遁（间传·逆间）：不得出而潜藏'),
                ('三传旺衰', '初传亥水相、中传酉金旺、末传未土休'),
                ('遁干特殊', '中传酉遁丁（遁鬼、遁丁）：暗鬼——藏于支下之官鬼,防暗中之险、隐忧；丁马——遁出丁,主动、信息、奔走'),
                ('毕法（已命中）', '（以下为机械命中之断诀，烈度须合时令旺衰、年命制化，非定数）\n68. 制鬼之位乃良医：制鬼之位乃良医'),
                ('七政', '| 七政 | 临支 | 五行 | 度数 | 逆行 | 备注 |\n| --- | --- | --- | --- | --- | --- |'),
                ('正北坎宫', '遁甲：天盘干：戊；八神：地；九星：蓬；地盘干：戊\n「子-水瓶座」'),
                ('东北艮宫', '遁甲：天盘干：庚；八神：玄；九星：任；地盘干：庚\n「丑-摩羯座」'),
                ('正东震宫', '遁甲：天盘干：丙；八神：虎；九星：冲；地盘干：丙\n「卯-天蝎座」'),
                ('东南巽宫', '遁甲：天盘干：丁；八神：合；九星：辅；地盘干：丁\n「辰-天秤座」'),
                ('正南离宫', '遁甲：天盘干：己；八神：阴；九星：英；地盘干：己\n「午-狮子座」'),
                ('西南坤宫', '遁甲：天盘干：乙；八神：蛇；九星：内；地盘干：乙\n「未-巨蟹座」'),
                ('正西兑宫', '遁甲：天盘干：辛；八神：符；九星：柱；地盘干：辛\n「酉-金牛座」'),
                ('西北乾宫', '遁甲：天盘干：壬；八神：天；九星：心；地盘干：壬\n「戌-白羊座」'),
                ('神煞', '日禄：酉\n日德：巳'),
                ('八宫详解', '乾宫：\n奇门吉格：'),
                ('奇门九宫方盘', '| 宫 | 天干 | 神 | 门 | 天星 | 地干 |\n| --- | --- | --- | --- | --- | --- |'),
                ('奇门旺相休囚死·月令能量', '月令：酉（金令）。当令者旺、我生者相、生我者休、克我者囚、我克者死；旺相有力，休囚死无力。\n| 宫 | 星 | 星五行 | 星旺衰 | 门 | 门五行 | 门旺衰 | 宫五行 | 宫旺衰 |'),
                ('奇门六害总览', '危害递减：击刑＞入墓＞庚＞白虎＞门迫＞空亡；天干＞一切，先解击刑天干。\n| 危害 | 宫位 | 符号 |'),
                ('奇门化解方案', '| 宫位 | 危害 | 天盘干 | 化解 |\n| --- | --- | --- | --- |'),
                ('奇门八门化气大阵', '| 门 | 落宫 | 状态 |\n| --- | --- | --- |'),
                ('奇门用神分论', '用神＝日干「辛」（阴·实质），落 兑7宫；时干为平台（事之表象）。\n日干:辛(兑7宫)\u3000时干:甲(兑7宫)\u3000干合/配偶:丙(震3宫)'),
                ('奇门财富七要', '| 用神 | 落宫 | 危害 |\n| --- | --- | --- |'),
                ('奇门事业七要', '| 用神 | 落宫 | 危害 |\n| --- | --- | --- |'),
                ('奇门恋爱姻缘', '干合·正缘（配偶/理想型）:丙震3宫\n六合·人缘（月老）:合巽4宫'),
                ('奇门孤辰寡宿', '孤辰(申):于 坤·西南 用「巳（蛇）」六合住；寡宿(辰):于 巽·东南 用「酉（鸡）」六合住'),
            ]
            for title, _body in blocks:
                assert title in _PS3["sanshiunited"], title
            return {
                "tool": "sanshiunited",
                "data": {
                    "ok": True,
                    "liureng": {"yue": "辰", "timezi": "午", "guizi": "寅", "nianMing": "午",
                                "keText": ["一课 辛申天空", "二课 申午勾陈", "三课 丑亥玄武", "四课 亥酉白虎"],
                                "sanChuan": {"cuang": ["己亥", "丁酉", "乙未"], "tianJiang": ["玄武", "白虎", "青龙"]}},
                    "warnings": [],
                },
                "snapshot_text": "\n\n".join(f"【{title}】\n{body}" for title, body in blocks),
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
        if tool_name == "guolao_moira" and payload.get("action") == "rules_sections":
            # v0.36.0 C1：[虚实]/[本命化曜]/[流年流曜] 三段——真渲染由 npm selfcheck 金标守；这里只回段体，
            # 且只在拿到 Java 规则响应时回（桩与真 builder 同语义：无数据 → 空串不产段）。
            rules = payload.get("moiraRules") or {}
            if not (rules.get("weakSolid") or rules.get("yearStars")):
                return {"sections": {"weakSolid": "", "birthStars": "", "transitStars": ""}}
            return {"sections": {
                "weakSolid": "| 宫位 | 虚实 | 虚柱 | 实柱 |\n| --- | --- | --- | --- |\n| 命宫 | 实 | 无 | 年、日 |\n口径：虚宫按四柱旬空推虚；实宫按年、月、日、时四柱地支定实。",
                "birthStars": "本命年柱：丙午\n◆ 本命化曜\n木：化天贵（同归：岁星）",
                "transitStars": f"流年干支：{payload.get('transitYearGz') or '—'}\n◆ 流年化曜\n火：化天刑",
            }}
        if tool_name == "guolao_moira" and payload.get("action") == "info_sections":
            # v3.11.x [Q-231/Q-434/Q-435]：[起盘信息] 命度/身度/宿主行 + [大限] + [三主与化曜] + [限法实算]。
            # 段体取自真 builder 在上游 guolaoInfoFactsSnapshot.test.js 夹具上的输出（真值由
            # tests/test_sync311_chinese.py 的真 node 用例守；这里只回形状 + 真内容）。
            return {
                "anchorLines": [
                    "命度：射手 10度42分（寅 · 七政命度点 · 1宫 - 命宫）",
                    "身度：金牛 12度0分（酉 · 月亮 · 7宫 - 夫妻宫）",
                    "命度宿主：房 10度42分；身度宿主：亢 12度0分",
                ],
                "limitSection": (
                    "古度限度法（命度十二宫大限）：\n| 限 | 宫 | 起讫岁 | 起讫年 | 年数 |\n| --- | --- | --- | --- | --- |\n"
                    "| 第1限 | 命宫 | 1-13岁 | 1990-2002年 | 约12.6年 |"
                ),
                "masters": (
                    "◆ 三主 · 命宫配干 · 化曜（主宫主）\n命主(宫主)：木\n命宫宫主：木\n命度度主(宿主曜)：日\n"
                    "身主(身宫宫主)：金\n命宫配干(五虎遁)：戊寅\n生年化曜(A诀)：水"
                ),
                "limitCalc": "◆ 飞限 · 童限 · 小限 · 月限 · 限度（37 岁 · 丙午年）\n飞限：亥；小限：寅；月限：未；限度：25巳08；至：23巳08",
                # wave3b：[七政四余宫位与二十八宿星曜] / [神煞] / [相位] 三段（真 builder 在 live 夹具
                # sync311_w3b_guolao_live.json 上的输出节选；真值由 tests/test_sync311_w3b_gim.py 的真 node 用例守）。
                "houseSu": (
                    "| 宫位 | 二十八宿 | 星曜 |\n| --- | --- | --- |\n"
                    "| 戌—降娄—白羊座—第11宫 | 壁 | 水 0˚壁7分；火 2˚壁53分；日 6˚壁18分 |\n| 酉—大梁—金牛座—第12宫 | 无 | 无 |"
                ),
                "gods": "申：长生、文昌、伏尸、剑锋、孤虚、卦气、月符、披头、岁驾、福贵、太岁、地杀、指背",
                "aspects": "| 主体 | 相位 | 对象 | 状态 | 误差 |\n| --- | --- | --- | --- | --- |\n| 日 | 六合 (60°) | 天 | 离相 | 9.668 |",
                "errors": [],
            }
        if tool_name == "ziwei_extras":
            # 紫微 [运限概览]（v3.11.0 #80，有盘就出）/ [运限]（给了 period 才出）/ [流派叠层]（开了流派开关才出）。
            # 段体取自真引擎在 2028-04-06 09:33 上海盘上的输出；段头按真 preset 取（不手抄）。
            from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS as _PZ

            def _zw(title: str) -> str:
                assert title in _PZ["ziwei"], title
                return f"[{title}]"

            blocks = [
                f"{_zw('运限概览')}\n全大限 × 流年一览(公历年与干支由代码算出,禁自行推算):\n"
                "| 虚岁 | 宫位 | 宫干支 | 该限流年（公历年-干支） |\n| --- | --- | --- | --- |\n"
                "| 2~11 | 命 | 癸亥 | 2029-己酉、2030-庚戌、2031-辛亥、2032-壬子、2033-癸丑、2034-甲寅、2035-乙卯、2036-丙辰、2037-丁巳、2038-戊午 |\n"
                "要某一年/某月的完整流曜与四化落宫,请在「挂载设置 → 运限」里选定年月(或直接说出年份)。"
            ]
            if payload.get("period"):
                blocks.append(f"{_zw('运限')}\n◆ 大限：甲子（12~21岁），命宫【父母】·对宫【疾厄】")
            if payload.get("schools"):
                blocks.append(f"{_zw('流派叠层')}\n· 童限\n  1岁·命宫")
            return {"text": "\n\n".join(blocks), "errors": []}
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
        if tool_name == "mundane_cards":
            # 世运右栏卡片段（v3.11）：真渲染由 npm selfcheck 金标（vendored buildMundaneCardSections）与
            # tests/test_sync311_mundane_election.py 的真 JS 用例守；桩只管形状。段头取自真 preset / 真表（不手抄）：
            # 入宫底盘一轮回 preset 里「年盘概要…起盘信息」之间**非 optional** 的卡（必出卡），盘型轮回该盘型的
            # 专属卡（service._MUNDANE_TYPE_CARDS；service 侧再按同表过滤）。
            from horosa_skill.exports.registry import (
                AI_EXPORT_OPTIONAL_SECTIONS as _OPT,
            )
            from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS as _PRE
            from horosa_skill.service import HorosaSkillService as _Svc

            preset = _PRE["mundane"]
            cards = preset[preset.index("年盘概要"): preset.index("起盘信息")]
            optional = set(_OPT["mundane"])
            jobs_out = []
            for job in payload.get("jobs") or []:
                job_id = str(job.get("id"))
                titles = [t for t in cards if t not in optional] if job_id == "ingress" else list(_Svc._MUNDANE_TYPE_CARDS.get(job_id, ()))
                jobs_out.append({
                    "id": job_id,
                    "ok": True,
                    "cards": [{"title": t, "text": f"[{t}]\n{t}：离线桩判读行（逐字真值由 selfcheck 金标守）"} for t in titles],
                })
            # meta 与真工具同形（tools/mundaneCards.js settingsCheck：rulesetConfig 缺省 modern 的查名）。
            meta = {"ruleset": "modern", "rulesetLabel": "现代(Carter–Campion)", "orbSchemeLabel": None, "ingressRuleLabel": None}
            return {"tool": "mundane_cards", "data": {"ok": True, "jobs": jobs_out, "meta": meta}}
        raise AssertionError(f"Unexpected local tool: {tool_name}")


class CaptureClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        self.calls.append((endpoint, dict(payload)))
        return super().call(endpoint, payload)
