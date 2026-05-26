"""Local-tool tests.

qimen / taiyi / jinkou are computed by the Horosa "ken" backend (kinqimen / kintaiyi /
kinjinkou) on the Python chart service, then reformatted into 星阙 aiExport.js sections by
the headless JS layer. Because that pipeline needs the live runtime (Java :9999 + Python
chart :8899), those four are integration tests that skip when the services aren't running.
liureng (headless layout) is exercised with a mocked client, and tongshefa has no ken
engine and runs as a pure headless JS tool.
"""
from __future__ import annotations

import socket

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService


def _server_up(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


RUNTIME_UP = _server_up("127.0.0.1", 8899) and _server_up("127.0.0.1", 9999)
requires_runtime = pytest.mark.skipif(
    not RUNTIME_UP, reason="Horosa runtime not listening on :9999 (Java) + :8899 (chart/ken)"
)


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


class LiuRengParityLocalClient(FakeLocalClient):
    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/liureng/gods":
            return {
                "Result": {
                    "liureng": {
                        "nongli": {"dayGanZi": "戊申", "time": "癸巳", "birth": "2028-04-06 09:35:18"},
                        "fourColumns": {
                            "year": {"ganzi": "戊申"},
                            "month": {"ganzi": "丙辰"},
                            "day": {"ganzi": "戊申"},
                            "time": {"ganzi": "癸巳"},
                        },
                        "xun": {"旬空": "寅卯", "旬首": "甲辰"},
                        "season": {},
                        "gods": {},
                        "godsGan": {},
                        "godsMonth": {},
                        "godsZi": {},
                        "godsYear": {"taisui1": {}},
                    }
                }
            }
        if endpoint in {"/chart", "/"}:
            return {
                "Result": {
                    "chart": {
                        "isDiurnal": True,
                        "nongli": {"dayGanZi": "戊申", "time": "癸巳"},
                        "objects": [{"id": "Sun", "sign": "Aries"}],
                    }
                }
            }
        return super().call(endpoint, payload)


def make_service(tmp_path, client: HorosaApiClient | None = None) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        chart_server_root="http://127.0.0.1:8899",
        runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    # client=None -> real clients (used by the @requires_runtime ken integration tests);
    # a fake client is injected for the mocked liureng test.
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings))


def _assert_clean_export(result) -> None:
    export = result.data.get("export_snapshot")
    assert export is not None
    assert export.get("missing_selected_sections") == []
    assert export.get("unknown_detected_sections") == []


@requires_runtime
def test_qimen_runs_via_ken_backend(tmp_path) -> None:
    service = make_service(tmp_path)
    result = service.run_tool(
        "qimen",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "options": {"qijuMethod": "chaibu"}},
        save_result=False,
    )
    assert result.ok is True
    pan = result.data["pan"]
    assert pan.get("source") == "kinqimen"
    assert pan.get("juText")
    assert isinstance(pan.get("cells"), list) and pan["cells"]
    assert "[起盘信息]" in result.data["snapshot_text"]
    assert "[九宫方盘]" in result.data["snapshot_text"]
    _assert_clean_export(result)


@requires_runtime
def test_taiyi_runs_via_ken_backend(tmp_path) -> None:
    service = make_service(tmp_path)
    result = service.run_tool(
        "taiyi",
        {"date": "2026-02-17", "time": "21:50:07", "zone": "+08:00", "lat": "31n14", "lon": "121e28", "options": {"style": 3, "tn": 0, "sex": "男"}},
        save_result=False,
    )
    assert result.ok is True
    pan = result.data["pan"]
    assert pan.get("source") == "kintaiyi"
    assert pan.get("zhao")
    kook = pan.get("kook")
    assert (kook.get("text") if isinstance(kook, dict) else kook)
    assert "[太乙盘]" in result.data["snapshot_text"]
    _assert_clean_export(result)


@requires_runtime
def test_jinkou_runs_via_ken_backend(tmp_path) -> None:
    service = make_service(tmp_path)
    result = service.run_tool(
        "jinkou",
        {"date": "2026-02-17", "time": "21:50:07", "zone": "+08:00", "lat": "31n14", "lon": "121e28", "options": {"diFen": "午"}},
        save_result=False,
    )
    assert result.ok is True
    jinkou = result.data["jinkou"]
    assert jinkou.get("source") == "kinjinkou"
    assert isinstance(jinkou.get("rows"), list) and jinkou["rows"]
    assert "[金口诀速览]" in result.data["snapshot_text"]
    _assert_clean_export(result)


@requires_runtime
def test_sanshiunited_combines_ken_qimen_taiyi(tmp_path) -> None:
    service = make_service(tmp_path)
    result = service.run_tool(
        "sanshiunited",
        {"date": "1998-02-20", "time": "20:48:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "qimen_options": {"qijuMethod": "chaibu"}, "taiyi_options": {"style": 3}},
        save_result=False,
    )
    assert result.ok is True
    assert result.data["qimen"].get("juText")
    assert result.data["taiyi"].get("kook")
    assert "[起盘信息]" in result.data["snapshot_text"]
    _assert_clean_export(result)


def test_liureng_defaults_to_xingque_astrology_guiren_system(tmp_path) -> None:
    service = make_service(tmp_path, client=LiuRengParityLocalClient())

    result = service.run_tool(
        "liureng_gods",
        {
            "date": "2028-04-06",
            "time": "09:33:00",
            "zone": "+08:00",
            "lat": "31n13",
            "lon": "121e28",
        },
        save_result=False,
    )

    assert result.ok is True
    layout = result.data["headless_liureng"]["layout"]
    assert layout["guirengType"] == 2
    assert layout["guirengLabel"] == "星占法贵人"
    assert layout["guizi"] == "午"
    assert "贵人体系：星占法贵人" in result.data["snapshot_text"]
    assert "MongoDB" not in result.data["snapshot_text"]


def test_tongshefa_local_tool_runs_headless_engine(tmp_path) -> None:
    service = make_service(tmp_path)
    result = service.run_tool(
        "tongshefa",
        {"taiyin": "巽", "taiyang": "坤", "shaoyang": "震", "shaoyin": "震"},
        save_result=False,
    )
    assert result.ok is True
    assert result.data["tongshefa"]["baseLeft"]["name"]
    assert result.data["export_snapshot"] is not None


def test_tongshefa_uses_jingfang_palace_element_not_upper_trigram(tmp_path) -> None:
    # Alignment regression: 统摄法 takes a hexagram's element from its 京房本宫 palace, not its upper
    # trigram. left=风雷益 (巽/震, palace 巽宫 木), right=火地晋 (离/坤, palace 乾宫 金 — upper trigram
    # would wrongly give 火). 星阙 expects right_elem=金 and main_relation=实克思.
    service = make_service(tmp_path)
    result = service.run_tool(
        "tongshefa",
        {"taiyin": "巽", "taiyang": "离", "shaoyang": "震", "shaoyin": "坤"},
        save_result=False,
    )
    assert result.ok is True
    data = result.data["tongshefa"]
    assert data["baseLeft"]["name"] == "风雷益"
    assert data["baseRight"]["name"] == "火地晋"
    assert data["left_elem"] == "木"
    assert data["right_elem"] == "金"  # palace 乾宫, NOT upper trigram 离/火
    assert data["main_relation"] == "实克思"
