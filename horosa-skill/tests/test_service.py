from horosa_skill.config import Settings
from horosa_skill.exports.parser import parse_export_content
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.knowledge import build_knowledge_registry
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import TOOL_EXPORT_TECHNIQUE_MAP, HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads


class FakeClient(HorosaApiClient):
    def __init__(self) -> None:
        super().__init__("http://fake")

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
                ]
            },
            "bazi": {"fourColumns": {"year": {"ganzi": "甲子"}}},
            "liureng": {"ke": ["一课"], "overview": ["概览"]},
            "nongli": {"bazi": {"guolaoGods": {"ziGods": {"子": {"allGods": ["青龙"], "taisuiGods": ["岁驾"]}}}}},
        }
        if endpoint == "/nongli/time":
            return {"birth": f"{payload['date']} {payload['time']}", "nongli": "丙午年二月十七"}
        if endpoint == "/jieqi/year":
            return {"year": payload["year"], "jieqi24": [{"name": "春分"}, {"name": "夏至"}]}
        if endpoint == "/liureng/gods":
            return {"liureng": {"layout": "ok", "fourColumns": {"year": {"ganzi": "丙午"}}}}
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
        if endpoint == "/gua/desc":
            return {
                payload["name"][0]: {"name": "乾为天", "卦辞": "元亨利贞"},
                payload["name"][1]: {"name": "水火既济", "卦辞": "亨小利贞"},
            }
        if endpoint == "/chart13":
            return chart_payload
        return chart_payload


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
        raise AssertionError(f"Unexpected local tool: {tool_name}")


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
    queried = store.query_runs(entity="我接下来事业走势如何", include_payload=True)
    assert queried == []
    by_tool = store.query_runs(tool="qimen", include_payload=True)
    assert by_tool
    assert by_tool[0]["ai_answer_text"] == "先稳后升，宜先整理资源再扩张。"
    assert by_tool[0]["artifacts"][0]["payload"]["conversation"]["ai_answer_structured"] == {"trend": "up_later"}


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
