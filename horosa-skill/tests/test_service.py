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
            "bazi": {"fourColumns": {"year": {"ganzi": "甲子"}}},
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
            return {"birth": f"{payload['date']} {payload['time']}", "nongli": "丙午年二月十七"}
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
            }
        if endpoint == "/predict/dice":
            return {
                "planet": payload.get("planet", "Sun"),
                "sign": payload.get("sign", "Aries"),
                "house": payload.get("house", 0),
                "diceChart": chart_payload,
                "chart": chart_payload,
            }
        if endpoint in {"/predict/solarreturn", "/predict/lunarreturn", "/predict/givenyear"}:
            return {
                "date": payload.get("datetime", "2031-04-06 09:33:00"),
                "chart": chart_payload["chart"],
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
            return {
                "date": payload.get("datetime", "2031-04-06 09:33:00"),
                "chart": chart_payload["chart"],
                "lots": chart_payload["lots"],
                "aspects": chart_payload["aspects"],
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
        _SHENSHU_FAKE = {
            "/wangji/pan": ("kinwangji", "[起盘]\n干支：戊寅\n[元会运世]\n运卦：乾\n[天道卦]\n天道：泰\n[人事卦]\n人事：否\n[历史年表]\n年表：—\n[心易发微]\n断：吉"),
            "/wuzhao/pan": ("kinwuzhao", "[起盘]\n干支：戊寅\n[揲筮]\n揲法：—\n[兆]\n兆象：—\n[木乡]\n木：—\n[火乡]\n火：—\n[土乡]\n土：—\n[金乡]\n金：—\n[水乡]\n水：—\n[特殊标记]\n标记：—"),
            "/taixuan/pan": ("taixuanshifa", "[起盘]\n干支：戊寅\n[玄首]\n首：中\n[方州部家]\n方州部家：—\n[表]\n表：—"),
            "/jingjue/pan": ("jingjue", "[起课]\n干支：戊寅\n[卦辞]\n辞：—\n[三分]\n三分：—\n[十六卦]\n卦：—"),
            "/shenyishu/pan": ("shenyishu", "[起盘]\n干支：戊寅\n[干支与五行]\n五行：木\n[神卦]\n卦：—\n[五行法则]\n法：—\n[兵占]\n占：—\n[主客判断]\n主客：—\n[神煞]\n煞：—\n[长生]\n长生：—\n[吉凶]\n断：吉"),
        }
        if endpoint in _SHENSHU_FAKE:
            engine, snapshot = _SHENSHU_FAKE[endpoint]
            return {
                "source": engine,
                "engine": engine,
                "dateStr": payload.get("date", f"{payload.get('year', 2025)}-01-01"),
                "timeStr": payload.get("time", "00:00:00"),
                "snapshot": snapshot,
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
        if tool_name == "qimen":
            return {
                "data": {"juText": "阳遁九局", "zhiFu": "天蓬", "zhiShi": "休门"},
                "snapshot_text": "[起盘信息]\n日期：2026-04-04 21:18\n\n[奇门演卦]\n值符值使演卦：天泽履之乾为天",
            }
        if tool_name == "taiyi":
            return {
                "data": {"zhao": "阳遁", "kook": "二十四局"},
                "snapshot_text": "[起盘信息]\n日期：2026-04-04 21:18\n\n[太乙盘]\n主算：二十四局",
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
            return {
                "data": {"guiName": "天乙", "jiangName": "登明", "wangElem": "木"},
                "snapshot_text": "[起盘信息]\n日期：2026-04-04 21:18\n\n[金口诀速览]\n地分：酉",
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
        raise AssertionError(f"Unexpected local tool: {tool_name}")


class FakeRuntimeManager:
    def __init__(self) -> None:
        self.started = 0

    def start_local_services(self) -> dict[str, object]:
        self.started += 1
        return {"ok": True, "already_running": False}


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
    assert result.data["export_format"]["sections"][0]["title"] == "起盘信息"
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
    assert result.data["export_format"]["format_source"] == "snapshot_parser"
    assert result.data["export_format"]["selected_sections"] == ["起盘信息", "盘型", "盘面要素", "奇门演卦", "八宫详解", "九宫方盘"]
    assert any(section["title"] == "奇门演卦" for section in result.data["export_format"]["sections"])


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
    assert [item["domain"] for item in registry["domains"]] == ["astro", "liureng", "qimen"]


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
    assert hellen.data["export_snapshot"]["technique"]["key"] == "astrochart_like"
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
        assert subresult["export_contract"]["has_export_format"] is True
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
        assert result.data["export_format"]["selected_sections"], tool_name
        assert result.data["export_format"]["sections"], tool_name
        assert all(section["title"] for section in result.data["export_format"]["sections"]), tool_name


def test_predictive_tools_export_real_natal_and_timed_chart_content(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()

    expected_sections = {
        "solarreturn": ["本命盘星与虚点", "返照盘星与虚点", "返照盘相位"],
        "lunarreturn": ["本命盘星与虚点", "返照盘星与虚点", "返照盘相位"],
        "givenyear": ["本命盘星与虚点", "流年盘星与虚点", "流年盘相位"],
        "solararc": ["本命盘星与虚点", "推运盘星与虚点", "推运盘相位"],
        "profection": ["本命盘星与虚点", "推运盘星与虚点", "推运盘相位"],
    }
    for tool_name, sections in expected_sections.items():
        result = service.run_tool(tool_name, payloads[tool_name], save_result=False)
        export_format = result.data["export_format"]
        text = export_format["snapshot_text"]
        assert all(section in export_format["selected_sections"] for section in sections), tool_name
        assert "本命盘" in text, tool_name
        assert any(label in text for label in ("返照盘", "推运盘", "流年盘")), tool_name
        assert "日 (" in text and "月 (" in text, tool_name
        assert "标准相位" in text, tool_name


def test_primary_direction_exports_tables_and_pdchart_positions(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()

    pd_result = service.run_tool("pd", payloads["pd"], save_result=False)
    pd_text = pd_result.data["export_format"]["snapshot_text"]
    assert "主/界限法表格" in pd_text
    assert "| Arc | 迫星 | 应星 | 类型 | 日期 |" in pd_text
    assert "推运月" in pd_text
    assert "本命土" in pd_text
    assert "2031-04-06" in pd_text

    pdchart_result = service.run_tool("pdchart", payloads["pdchart"], save_result=False)
    pdchart_text = pdchart_result.data["export_format"]["snapshot_text"]
    assert "本命盘星与虚点" in pdchart_text
    assert "主限法盘星体表格" in pdchart_text
    assert "| 星体/虚点 | 位置 | 宫位 | 速度 |" in pdchart_text
    assert "主限法盘相位" in pdchart_text


def test_zodiacal_release_exports_timeline_rows(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    payloads = build_sample_payloads()

    result = service.run_tool("zr", payloads["zr"], save_result=False)
    text = result.data["export_format"]["snapshot_text"]
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
            export_format = artifact_payload["data"]["export_format"]
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
    assert qimen_contract["has_export_format"] is True
    assert qimen_contract["technique"]["key"] == "qimen"
    assert "奇门演卦" in qimen_contract["selected_sections"]
    assert liureng_contract["has_export_snapshot"] is True
    assert liureng_contract["has_export_format"] is True
    assert liureng_contract["technique"]["key"] == "liureng"
    queried = store.query_runs(tool="liureng_gods", include_payload=True)
    assert queried
    assert sorted(result.selected_tools) == sorted(result.result_export_contracts)
    for tool_name, contract in result.result_export_contracts.items():
        assert contract["tool"] == tool_name
        assert contract["selected_sections"]
        assert contract["export_snapshot"]["technique"]["key"] == TOOL_EXPORT_TECHNIQUE_MAP[tool_name]
        assert contract["export_format"]["sections"]


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
    assert result.data["export_format"]["provenance"]["bundle_version"] == result.data["export_snapshot"]["bundle_version"]
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
