from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService


class FakeClient(HorosaApiClient):
    def __init__(self) -> None:
        super().__init__("http://fake")

    def call(self, endpoint: str, payload: dict) -> dict:
        if endpoint == "/nongli/time":
            return {"birth": f"{payload['date']} {payload['time']}", "nongli": "丙午年二月十七"}
        if endpoint == "/jieqi/year":
            return {"year": payload["year"], "jieqi24": [{"name": "春分"}, {"name": "夏至"}]}
        if endpoint == "/liureng/gods":
            return {"liureng": {"layout": "ok", "fourColumns": {"year": {"ganzi": "丙午"}}}}
        return {
            "endpoint": endpoint,
            "params": payload,
            "chart": {
                "ok": True,
                "houses": [{"name": "命宫"}],
                "planets": [{"name": "Sun"}],
                "aspects": [{"type": "trine"}],
                "greekPoints": [{"name": "Fortuna"}],
                "possibility": [{"name": "Opportunity"}],
            },
            "predictives": [{"name": "L1"}],
            "bazi": {"fourColumns": {"year": {"ganzi": "甲子"}}},
            "liureng": {"ke": ["一课"], "overview": ["概览"]},
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
        return {
            "data": {"guiName": "天乙", "jiangName": "登明", "wangElem": "木"},
            "snapshot_text": "[起盘信息]\n日期：2026-04-04 21:18\n\n[金口诀速览]\n地分：酉",
        }


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
