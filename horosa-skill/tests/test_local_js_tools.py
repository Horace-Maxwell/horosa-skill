from __future__ import annotations

from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService


class FakeLocalClient(HorosaApiClient):
    def __init__(self) -> None:
        super().__init__("http://fake")

    def probe(self, endpoint: str = "/common/time", payload: dict | None = None) -> bool:
        return True

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/nongli/time":
            return {
                "Result": {
                    "yearJieqi": "丙午",
                    "year": "丙午",
                    "monthGanZi": "庚寅",
                    "dayGanZi": "壬戌",
                    "jieqi": "立春",
                    "jiedelta": "立春后第14天",
                    "birth": f"{payload['date']} {payload['time']}",
                    "month": "正月",
                    "day": "初一",
                    "leap": False,
                    "yearGanZi": "丙午",
                    "monthInt": 1,
                    "dayInt": 1,
                    "time": "辛亥",
                }
            }
        if endpoint == "/jieqi/year":
            return {"Result": {"jieqi24": []}}
        if endpoint == "/liureng/gods":
            return {
                "Result": {
                    "liureng": {
                        "nongli": {"dayGanZi": "甲辰", "time": "申时", "monthGanZi": "丙申"},
                        "fourColumns": {"month": {"ganzi": "丙申"}},
                        "xun": {"旬空": "寅卯", "旬首": "甲辰"},
                        "season": {"金": "囚", "木": "旺", "水": "休", "火": "相", "土": "死"},
                        "gods": {},
                        "godsGan": {},
                        "godsMonth": {},
                        "godsZi": {},
                        "godsYear": {"taisui1": {}},
                    }
                }
            }
        raise AssertionError(f"Unexpected endpoint: {endpoint}")


QIMEN_TIANPAN_GOLDEN_NONGLI = {
    "yearJieqi": "戊寅",
    "year": "戊寅",
    "monthGanZi": "甲寅",
    "dayGanZi": "戊戌",
    "time": "壬戌",
    "jieqi": "雨水",
    "jiedelta": "雨水后第1天",
    "birth": "1998-02-20 20:48:00",
    "month": "正月",
    "day": "廿四",
    "leap": False,
}

QIMEN_TIANPAN_GOLDEN = {
    "1": "庚",
    "2": "丙",
    "3": "丁",
    "4": "戊",
    "6": "己",
    "7": "壬",
    "8": "辛",
    "9": "乙",
}

QIMEN_DIPAN_GOLDEN = {
    "1": "壬",
    "2": "戊",
    "3": "庚",
    "4": "辛",
    "6": "丙",
    "7": "乙",
    "8": "己",
    "9": "丁",
}

QIMEN_RENPAN_GOLDEN = {
    "1": "死",
    "2": "惊",
    "3": "开",
    "4": "景",
    "6": "休",
    "7": "杜",
    "8": "伤",
    "9": "生",
}

QIMEN_SHENPAN_GOLDEN = {
    "1": "符",
    "2": "蛇",
    "3": "阴",
    "4": "天",
    "6": "合",
    "7": "地",
    "8": "玄",
    "9": "虎",
}


class QimenGoldenLocalClient(FakeLocalClient):
    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/nongli/time":
            return {"Result": dict(QIMEN_TIANPAN_GOLDEN_NONGLI)}
        return super().call(endpoint, payload)


def pick_outer_palaces(map_obj: dict) -> dict:
    return {key: map_obj[key] for key in ["1", "2", "3", "4", "6", "7", "8", "9"]}


def make_service(tmp_path, client: HorosaApiClient | None = None) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        chart_server_root="http://127.0.0.1:8899",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    return HorosaSkillService(settings, client=client or FakeLocalClient(), store=store)


def test_qimen_local_tool_runs_headless_engine(tmp_path) -> None:
    service = make_service(tmp_path)

    result = service.run_tool(
        "qimen",
        {
            "date": "2026-02-17",
            "time": "21:50:07",
            "zone": "+08:00",
            "lat": "31n14",
            "lon": "121e28",
            "options": {
                "sex": 1,
                "paiPanType": 3,
                "qijuMethod": "chaibu",
                "zhiShiType": 0,
                "yueJiaQiJuType": 1,
                "kongMode": "day",
                "yimaMode": "day",
            },
        },
        save_result=False,
    )

    assert result.ok is True
    assert result.data["pan"]["juText"]
    assert result.data["export_snapshot"] is not None


def test_qimen_tianpan_matches_legacy_horosa_golden_case(tmp_path) -> None:
    service = make_service(tmp_path, client=QimenGoldenLocalClient())

    result = service.run_tool(
        "qimen",
        {
            "date": "1998-02-20",
            "time": "20:48:00",
            "zone": "+08:00",
            "lat": "31n13",
            "lon": "121e28",
            "options": {
                "qijuMethod": "chaibu",
                "timeAlg": 1,
            },
        },
        save_result=False,
    )

    assert result.ok is True
    pan = result.data["pan"]
    assert pan["juText"] == "阳遁九局上元"
    assert pick_outer_palaces(pan["tianGan"]) == QIMEN_TIANPAN_GOLDEN
    assert pick_outer_palaces(pan["diPan"]) == QIMEN_DIPAN_GOLDEN
    assert pick_outer_palaces(pan["renPan"]) == QIMEN_RENPAN_GOLDEN
    assert pick_outer_palaces(pan["shenPan"]) == QIMEN_SHENPAN_GOLDEN
    assert pan["zhiFu"] == "天禽"
    assert pan["zhiShi"] == "死门"
    assert "天盘：庚 丙 丁 戊 癸 己 壬 辛 乙" in result.data["snapshot_text"]


def test_sanshiunited_uses_fixed_qimen_tianpan_golden_case(tmp_path) -> None:
    service = make_service(tmp_path, client=QimenGoldenLocalClient())

    result = service.run_tool(
        "sanshiunited",
        {
            "date": "1998-02-20",
            "time": "20:48:00",
            "zone": "+08:00",
            "lat": "31n13",
            "lon": "121e28",
            "qimen_options": {
                "qijuMethod": "chaibu",
                "timeAlg": 1,
            },
        },
        save_result=False,
    )

    assert result.ok is True
    qimen = result.data["qimen"]
    assert qimen["juText"] == "阳遁九局上元"
    assert pick_outer_palaces(qimen["tianGan"]) == QIMEN_TIANPAN_GOLDEN
    assert "[东南巽宫]" in result.data["snapshot_text"]
    assert "天盘干：庚" in result.data["snapshot_text"]


def test_taiyi_local_tool_runs_headless_engine(tmp_path) -> None:
    service = make_service(tmp_path)

    result = service.run_tool(
        "taiyi",
        {
            "date": "2026-02-17",
            "time": "21:50:07",
            "zone": "+08:00",
            "lat": "31n14",
            "lon": "121e28",
            "options": {"style": 3, "tn": 0, "tenching": 0, "sex": "男", "rotation": "固定"},
        },
        save_result=False,
    )

    assert result.ok is True
    assert result.data["pan"]["kook"]["text"]
    assert result.data["export_snapshot"] is not None


def test_jinkou_local_tool_runs_headless_engine(tmp_path) -> None:
    service = make_service(tmp_path)

    result = service.run_tool(
        "jinkou",
        {
            "date": "2026-02-17",
            "time": "21:50:07",
            "zone": "+08:00",
            "lat": "31n14",
            "lon": "121e28",
            "options": {"diFen": "午", "guirengType": 0},
        },
        save_result=False,
    )

    assert result.ok is True
    assert result.data["jinkou"]["guiName"] == "青龙"
    assert result.data["jinkou"]["wangElem"]


def test_tongshefa_local_tool_runs_headless_engine(tmp_path) -> None:
    service = make_service(tmp_path)

    result = service.run_tool(
        "tongshefa",
        {
            "taiyin": "巽",
            "taiyang": "坤",
            "shaoyang": "震",
            "shaoyin": "震",
        },
        save_result=False,
    )

    assert result.ok is True
    assert result.data["tongshefa"]["baseLeft"]["name"]
    assert result.data["export_snapshot"] is not None
