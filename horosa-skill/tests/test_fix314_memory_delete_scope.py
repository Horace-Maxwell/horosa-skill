"""删除连带报告与 trace、缺省进回收站、可放回（审计 O-06 / 待决项 6）。

修前：memory delete --yes 之后报告 PDF 还在（reports_kept），trace 里这条 run 的行还在；删了就找不回。
负向对照（实跑过）：delete_runs 不把 reports 并进 files → 第一条红；不调 _scrub_traces → 第一条红；restore 不重建 → 第二条红。
"""
from __future__ import annotations

import json
from pathlib import Path

from test_memory_facades import _cli, _cli_service, _ids, _run


def _report(service, run_id: str) -> Path:
    out = service.report_render({"run_id": run_id, "format": "json", "style": "chart"})
    return Path(out["artifact_path"])


def test_delete_takes_reports_and_trace_lines_and_goes_to_trash(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    mine = _run(service, name="王小明")
    report = _report(service, mine)
    trace = tmp_path / "data" / "traces" / "t.jsonl"
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text(json.dumps({"run_id": mine, "summary": ["王小明"]}) + "\n" + json.dumps({"run_id": "other"}) + "\n", encoding="utf-8")
    plan = json.loads(_cli(tmp_path, "memory", "delete", "--run-id", mine).stdout)
    assert plan["reports_deleted"] == [str(report)] and plan["trace_lines"] == 1 and plan["disposal"] == "trash"
    done = json.loads(_cli(tmp_path, "memory", "delete", "--run-id", mine, "--yes").stdout)
    assert not report.exists() and done["trace_lines_removed"] == 1 and mine not in trace.read_text(encoding="utf-8")
    assert '"other"' in trace.read_text(encoding="utf-8")
    assert (tmp_path / "data" / "trash" / done["trash_id"] / "trash.json").is_file()


def test_a_trashed_run_can_be_restored(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    mine = _run(service, name="王小明")
    done = json.loads(_cli(tmp_path, "memory", "delete", "--run-id", mine, "--yes").stdout)
    assert _ids(_cli_service(tmp_path).query_memory({})) == []
    listed = json.loads(_cli(tmp_path, "memory", "restore").stdout)
    assert [item["trash_id"] for item in listed["trash"]] == [done["trash_id"]]
    back = json.loads(_cli(tmp_path, "memory", "restore", "--trash-id", done["trash_id"]).stdout)
    assert back["restored_runs"] == 1 and _ids(_cli_service(tmp_path).query_memory({})) == [mine]


def test_keep_reports_and_permanent(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    mine = _run(service, name="王小明")
    report = _report(service, mine)
    done = json.loads(_cli(tmp_path, "memory", "delete", "--run-id", mine, "--yes", "--keep-reports", "--permanent").stdout)
    assert report.exists() and done["disposal"] == "permanent" and "trash_id" not in done


def test_old_trash_is_purged(tmp_path: Path) -> None:
    import os
    import time

    from horosa_skill.memory import manage

    entry = tmp_path / "trash" / "old"
    entry.mkdir(parents=True)
    (entry / "trash.json").write_text("{}", encoding="utf-8")
    old = time.time() - 31 * 86400
    os.utime(entry / "trash.json", (old, old))
    assert manage.purge_trash(tmp_path / "trash") == 1 and not entry.exists()
