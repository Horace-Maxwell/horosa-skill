from __future__ import annotations

from horosa_skill.benchmark import load_benchmark_dataset, run_benchmark
from horosa_skill.config import Settings


def test_benchmark_dataset_loads() -> None:
    dataset = load_benchmark_dataset()
    assert dataset["metadata"]["name"] == "HorosaBench"
    assert dataset["cases"]


def test_benchmark_can_run_local_only_cases(tmp_path) -> None:
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        trace_dir=tmp_path / "traces",
    )
    report = run_benchmark(settings=settings, skip_runtime=True, save_result=False)

    assert report["cases_executed"] >= 1
    assert "knowledge_qimen_door" in [item["id"] for item in report["results"]]
    assert report["ok"] is True
