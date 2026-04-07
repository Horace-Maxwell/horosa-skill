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


def make_service(tmp_path) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        chart_server_root="http://127.0.0.1:8899",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    return HorosaSkillService(settings, client=FakeLocalClient(), store=store)


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
