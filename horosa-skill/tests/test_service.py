from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService


class FakeClient(HorosaApiClient):
    def __init__(self) -> None:
        super().__init__("http://fake")

    def call(self, endpoint: str, payload: dict) -> dict:
        return {"endpoint": endpoint, "params": payload, "chart": {"ok": True}}


def test_service_tool_call_persists_memory(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    service = HorosaSkillService(settings, client=FakeClient(), store=store)

    result = service.run_tool(
        "chart",
        {"date": "1990-01-01", "time": "12:00", "zone": "8", "lat": "31n14", "lon": "121e28"},
    )

    assert result.ok is True
    assert result.memory_ref is not None
    queried = store.query_runs(tool="chart")
    assert len(queried) == 1

