import json

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore


def test_memory_store_writes_artifact(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    store = MemoryStore(settings)
    run_id = store.create_run(entrypoint="tool", query_text="test")
    ref = store.record_tool_result(
        run_id=run_id,
        tool_name="chart",
        ok=True,
        input_normalized={"date": "1990-01-01"},
        envelope_dict={"ok": True, "tool": "chart"},
        summary=["ok"],
        warnings=[],
        error=None,
    )
    assert ref.run_id == run_id
    assert ref.tool_name == "chart"
    assert (tmp_path / "runs").exists()
    artifact_path = (tmp_path / "runs").rglob("*.json").__next__()
    assert artifact_path.parent.parent.parent.parent == (tmp_path / "runs")
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["tool"] == "chart"

    queried = store.query_runs(tool="chart", include_payload=True)
    assert queried[0]["artifacts"][0]["payload"]["tool"] == "chart"
