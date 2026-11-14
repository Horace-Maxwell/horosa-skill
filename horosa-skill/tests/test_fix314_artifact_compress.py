"""存档产物压缩（审计待决项 7）：新产物存 .json.gz、读写都认两种后缀；memory compact 压旧产物、--decompress 反过来；重建认 .gz；导出给人读解成明文。

实测：131 个真实产物 28.4 MB，gzip 后 5.17 MB（18%）。
负向对照（实跑过）：_write_artifact 不压 → 第一条红；rebuild 的 _ARTIFACT 不认 .gz → 第三条红。
"""
from __future__ import annotations

import json
from pathlib import Path

from test_memory_facades import _cli, _cli_service, _ids, _run

from horosa_skill.memory import artifact_io, manage


def _artifact(service, run_id: str) -> Path:
    rows = service.show_memory({"run_id": run_id})["result"]["artifacts"]
    return next(Path(a["path"]) for a in rows if a["kind"] == "tool_result")


def test_new_artifacts_are_gzipped_and_read_back(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    run_id = _run(service, name="王小明")
    path = _artifact(service, run_id)
    assert path.name.endswith(".json.gz") and path.read_bytes()[:2] == b"\x1f\x8b"
    assert service.show_memory({"run_id": run_id})["result"]["artifacts"][0]["payload"]
    assert service.query_memory({"text": "王小明"})["count"] == 1        # 检索正文读得进 .gz
    service.record_ai_answer({"run_id": run_id, "ai_answer_text": "答案"})
    assert artifact_io.read_json(path)["conversation"]["ai_answer_text"] == "答案"   # 刷新沿用压缩形式


def test_compact_and_decompress_round_trip(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    service.settings.artifact_compress = False
    run_id = _run(service, name="王小明")
    plain = _artifact(service, run_id)
    assert plain.name.endswith(".json") and plain.read_bytes()[:1] == b"{"
    out = json.loads(_cli(tmp_path, "memory", "compact").stdout)
    assert out["converted"] == 1 and out["bytes_saved"] > 0 and not plain.exists()
    gz = _artifact(_cli_service(tmp_path), run_id)
    assert gz.name.endswith(".json.gz") and artifact_io.read_json(gz)["tool"]
    again = json.loads(_cli(tmp_path, "memory", "compact").stdout)
    assert again["converted"] == 0                                     # 幂等
    back = json.loads(_cli(tmp_path, "memory", "compact", "--decompress").stdout)
    assert back["converted"] == 1 and _artifact(_cli_service(tmp_path), run_id).name.endswith(".json")


def test_rebuild_and_export_understand_gz(tmp_path: Path) -> None:
    from horosa_skill.memory.rebuild import rebuild_from_artifacts

    service = _cli_service(tmp_path)
    run_id = _run(service, name="王小明")
    (tmp_path / "data" / "memory.db").unlink()
    fresh = _cli_service(tmp_path)
    assert rebuild_from_artifacts(fresh.store, min_age_seconds=0)["restored_runs"]["total"] == 1
    assert _ids(fresh.query_memory({})) == [run_id]
    exported = manage.export_runs(fresh.store, [{"run_id": run_id}], tmp_path / "out")
    files = list((tmp_path / "out").rglob("artifacts/*"))
    assert exported["runs"] == 1 and files and all(f.name.endswith(".json") for f in files)
    assert json.loads(files[0].read_text(encoding="utf-8"))["tool"]
