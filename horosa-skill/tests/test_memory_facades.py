"""记忆门面（memory_query / show / record_answer）与 CLI `memory`：入参怎么认、错误怎么说、结果多大。

台账：docs/LESSONS.md v0.50.0-dev「记忆检索的过滤条件各认各的」「写回答案会抹掉旧的」「记忆库坏了之后静悄悄」。
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fakes import FakeClient, FakeJsClient
from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError, classify_code
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.api import memory as memory_api

CONFIRM = {"agent_confirmed_settings": True, "clarification_notes": "memory facade test"}
BIRTH = {"date": "1990-05-03", "time": "08:00", "zone": "+08:00", "lat": "31n14", "lon": "121e28", "gender": 1, **CONFIRM}
MOM = {"date": "1962-3-5", "time": "6:00", "zone": "Asia/Shanghai", "lat": "26.9", "lon": "112.6", "gender": "女", "aliases": ["我妈"]}


def _settings(tmp_path: Path) -> Settings:
    data = tmp_path / "data"
    return Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=data,
                    db_path=data / "memory.db", output_dir=data / "runs", runtime_root=tmp_path / "rt")


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = _settings(tmp_path)
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _run(service: HorosaSkillService, tool: str = "bazi_birth", **extra) -> str:
    result = service.run_tool(tool, {**BIRTH, **extra}, save_result=True)
    assert result.ok, result.error
    return result.memory_ref.run_id


def _ids(result: dict) -> list[str]:
    return [row["run_id"] for row in result["results"]]


def _refused(call, code: str) -> ToolValidationError:
    with pytest.raises(ToolValidationError) as caught:
        call()
    assert caught.value.code == code, caught.value.code
    assert classify_code(code)[0] is not None
    return caught.value


# ── tool：每种叫法都认（M3 / N4）──────────────────────────────────────────────────────


@pytest.mark.parametrize("name", ["bazi_birth", "horosa_cn_bazi_birth", "BAZI_BIRTH", "Horosa_CN_Bazi_Birth", "八字", " 八字 "])
def test_tool_accepts_every_name_the_surface_accepts(tmp_path: Path, name: str) -> None:
    """此前只认注册表键：`horosa_cn_bazi_birth`、`八字` 都回 0 条（冷启动 AI 两次都这么写）。"""
    service = _service(tmp_path)
    run_id = _run(service)
    _run(service, tool="ziwei_birth")
    assert _ids(service.query_memory({"tool": name})) == [run_id]


def test_a_display_name_shared_by_several_techniques_matches_all_of_them(tmp_path: Path) -> None:
    service = _service(tmp_path)
    birth = _run(service)
    with service.store.connect() as conn:  # 另一个也叫「八字」的技法存过一条
        conn.execute("UPDATE tool_calls SET tool_name = 'bazi_direct' WHERE run_id = ?", (birth,))
        conn.commit()
    result = service.query_memory({"tool": "八字"})
    assert _ids(result) == [birth]
    assert result["applied_filters"]["tool"]["matched"] == ["bazi_birth", "bazi_direct"]


def test_an_unknown_tool_is_refused_with_the_catalogue(tmp_path: Path) -> None:
    service = _service(tmp_path)
    error = _refused(lambda: service.query_memory({"tool": "no_such_tool"}), "tool.unknown")
    assert "catalog" in error.details


def test_a_name_only_the_store_knows_is_still_accepted(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run_id = service.store.create_run(entrypoint="dispatch", query_text="调度", group_id="g")
    service.store.record_dispatch_result(run_id=run_id, payload={"ok": True})
    with service.store.connect() as conn:
        conn.execute("INSERT INTO tool_calls (run_id, tool_name, ok, input_json, summary_json, warnings_json, created_at)"
                     " VALUES (?, 'horosa_dispatch', 1, '{}', '[]', '[]', '2026-01-01T00:00:00+00:00')", (run_id,))
        conn.commit()
    assert _ids(service.query_memory({"tool": "horosa_dispatch"})) == [run_id]


# ── entity：档案的名字与别名（N4）、通配符、日期写法（M5）────────────────────────────


def test_a_profile_alias_finds_the_runs_stored_under_its_name(tmp_path: Path) -> None:
    """冷启动实测：「上次跟我妈说了什么」，entity="我妈" 对存成「妈妈」的 run 回 0 条。"""
    service = _service(tmp_path)
    service.profile({"action": "save", "name": "妈妈", "data": MOM})
    run_id = _run(service, profile="妈妈")
    _run(service)
    result = service.query_memory({"entity": "我妈"})
    assert _ids(result) == [run_id]
    assert result["applied_filters"]["entity"]["profiles"] == ["妈妈"]


@pytest.mark.parametrize("wildcard", ["%", "_", "王%", "_明"])
def test_like_wildcards_in_entity_are_literal(tmp_path: Path, wildcard: str) -> None:
    service = _service(tmp_path)
    _run(service, name="王小明")
    assert service.query_memory({"entity": wildcard})["count"] == 0


@pytest.mark.parametrize("form", ["1990-05-03", "1990/5/3", "1990.05.03", "1990年5月3日"])
def test_entity_dates_match_in_any_common_form(tmp_path: Path, form: str) -> None:
    service = _service(tmp_path)
    run_id = _run(service)
    assert _ids(service.query_memory({"entity": form})) == [run_id]


def test_a_person_named_by_the_common_name_parameter_is_found_by_name_alias_and_script(tmp_path: Path) -> None:
    """N4.3：技法载荷的 `name`（输入批次正把它声明为公共参数）落成实体；按名字、档案别名、繁体都找得到。"""
    service = _service(tmp_path)
    service.profile({"action": "save", "name": "陈丽华", "data": {**MOM, "aliases": ["华姐"]}})
    run_id = _run(service, name="陈丽华")
    for entity in ("陈丽华", "陳麗華", "华姐", "華姐"):
        assert _ids(service.query_memory({"entity": entity})) == [run_id], entity


# ── after / before / zone（M2 / M4）───────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["昨天", "11/11/2026", "2026-13-01", "2026-02-30", "last week", "2026-11-11T25:00"])
def test_unparseable_times_are_refused_with_the_accepted_forms(tmp_path: Path, value: str) -> None:
    """此前原样拿去和 created_at 比字符串：`昨天` 静默返回全部或空。"""
    service = _service(tmp_path)
    error = _refused(lambda: service.query_memory({"after": value}), "memory.query.invalid_time")
    assert error.details["accepted_forms"] and "2026-11-11" in f"{error}"


def _stamp(service: HorosaSkillService, run_id: str, created_at: str) -> None:
    with service.store.connect() as conn:
        conn.execute("UPDATE runs SET created_at = ? WHERE id = ?", (created_at, run_id))
        conn.commit()


def test_times_compare_as_instants_and_a_date_is_a_whole_local_day(tmp_path: Path) -> None:
    service = _service(tmp_path)
    early, late = _run(service), _run(service)
    _stamp(service, early, "2026-11-10T17:30:00+00:00")  # 北京时间 11-11 01:30
    _stamp(service, late, "2026-11-11T17:30:00+00:00")  # 北京时间 11-12 01:30
    day = service.query_memory({"after": "2026-11-11", "before": "2026-11-11", "zone": "+08:00"})
    assert _ids(day) == [early]
    assert day["applied_filters"]["time"]["zone_source"] == "input"
    assert _ids(service.query_memory({"after": "2026-11-11T09:00+08:00", "before": "2026-11-11T09:30+08:00"})) == []
    assert _ids(service.query_memory({"after": "2026-11-11T01:00+08:00", "before": "2026-11-11T02:00+08:00"})) == [early]
    assert _ids(service.query_memory({"after": "2026-11-10T17:30:00Z"})) == [late, early]
    machine = service.query_memory({"after": "2026-01-01"})
    assert machine["applied_filters"]["time"]["zone_source"] == "machine"


def test_an_unknown_zone_is_refused(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _refused(lambda: service.query_memory({"after": "2026-11-11", "zone": "Mars/Base"}), "memory.query.invalid_time")


def test_group_id_is_honoured(tmp_path: Path) -> None:
    """此前 group_id 被静默丢掉：传了等于没传。"""
    service = _service(tmp_path)
    first = _run(service)
    _run(service)
    group = service.store.query_runs(run_id=first, include_payload=False)[0]["group_id"]
    assert _ids(service.query_memory({"group_id": group})) == [first]


# ── 结果大小（N4.2 / C-21）────────────────────────────────────────────────────────────


def test_list_rows_carry_a_compact_subject_and_show_keeps_the_full_one(tmp_path: Path) -> None:
    """冷启动实测：4 行 15 KB，每行都带整份归一化载荷当 subject。"""
    service = _service(tmp_path)
    run_id = _run(service, name="王小明")
    row = service.query_memory({})["results"][0]
    assert set(row["subject"]) <= set(memory_api._SUBJECT_KEYS) | set(memory_api._NESTED_PEOPLE)
    assert row["subject"]["name"] == "王小明" and row["subject"]["date"] == "1990-05-03"
    assert "agent_confirmed_settings" in service.show_memory({"run_id": run_id})["result"]["subject"]


def test_limit_is_capped_and_the_result_says_so(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _run(service)
    result = service.query_memory({"limit": 10_000})
    assert result["applied_filters"]["limit"] == memory_api.QUERY_LIMIT_MAX
    assert any(str(memory_api.QUERY_LIMIT_MAX) in line for line in result["summary"])


def test_an_oversized_answer_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    """C-21：8 MiB 的「答案」此前照收，写进库也写进每一份产物文件。"""
    service = _service(tmp_path)
    run_id = _run(service)
    error = _refused(lambda: service.record_ai_answer({"run_id": run_id, "ai_answer_text": "长" * (memory_api.ANSWER_MAX_CHARS + 1)}),
                     "memory.answer.too_large")
    assert error.details["limits"][0]["field"] == "ai_answer_text"
    assert service.show_memory({"run_id": run_id})["result"]["ai_answer_text"] is None


# ── 写回答案（M14）────────────────────────────────────────────────────────────────────


def test_an_unknown_run_gets_the_structured_not_found_error(tmp_path: Path) -> None:
    """此前抛裸 ValueError：MCP 面成了 internal error，CLI 另起一个 memory.answer.unknown_run。"""
    service = _service(tmp_path)
    error = _refused(lambda: service.record_ai_answer({"run_id": "f" * 32, "ai_answer_text": "答"}), "memory.run.not_found")
    assert classify_code(error.code)[0] == "input"
    shown = service.show_memory({"run_id": "f" * 32})
    assert shown["code"] == "memory.run.not_found"
    assert shown["details"]["agent_recovery"]["next_action"] == "query_memory_for_run_id"


@pytest.mark.parametrize("answer", ["", "   "])
def test_an_empty_answer_is_refused_and_the_stored_one_survives(tmp_path: Path, answer) -> None:
    service = _service(tmp_path)
    run_id = _run(service)
    service.record_ai_answer({"run_id": run_id, "ai_answer_text": "第一次的解读"})
    _refused(lambda: service.record_ai_answer({"run_id": run_id, "ai_answer_text": answer}), "memory.answer.empty")
    assert service.show_memory({"run_id": run_id})["result"]["ai_answer_text"] == "第一次的解读"


def test_a_second_answer_keeps_the_first_and_the_question(tmp_path: Path) -> None:
    """此前第二次写回覆盖第一次，且不带 user_question 时把已存的问题重置成原始 query。"""
    service = _service(tmp_path)
    run_id = _run(service)
    service.record_ai_answer({"run_id": run_id, "user_question": "我今年适合换工作吗", "ai_answer_text": "第一次的解读"})
    second = service.record_ai_answer({"run_id": run_id, "ai_answer_text": "第二次的解读"})
    assert second["replaced_previous"] is True and second["previous_answers"] == 1
    assert second["ai_answer_text"] == second["ai_answer"] == "第二次的解读", "新名为准，旧名再留一个版本"
    assert any("沿用已存的问题" in line for line in second["summary"])
    shown = service.show_memory({"run_id": run_id})["result"]
    assert shown["user_question"] == "我今年适合换工作吗"
    assert [item["ai_answer_text"] for item in shown["answer_history"]] == ["第一次的解读"]
    assert _ids(service.query_memory({"text": "第一次的解读"})) == [run_id], "旧答案仍可搜"
    again = service.record_ai_answer({"run_id": run_id, "ai_answer": "第二次的解读"})  # 旧字段名照收；同一答案不进历史
    assert again["replaced_previous"] is False and again["previous_answers"] == 1


def test_the_answer_summary_says_which_artifacts_were_not_updated(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run_id = _run(service)
    artifact = Path(service.store.query_runs(run_id=run_id, include_payload=False)[0]["artifacts"][-1]["path"])
    artifact.unlink()
    result = service.record_ai_answer({"run_id": run_id, "ai_answer_text": "答"})
    assert [item["reason"] for item in result["artifacts_skipped"]] == ["missing"]
    assert any("没能同步" in line for line in result["summary"])


# ── show 说实话（M9）──────────────────────────────────────────────────────────────────


def test_show_says_what_is_missing_instead_of_claiming_a_full_record(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run_id = _run(service)
    artifact = Path(service.store.query_runs(run_id=run_id, include_payload=False)[0]["artifacts"][-1]["path"])
    whole = service.show_memory({"run_id": run_id})
    assert whole["complete"] is True
    artifact.write_text('{"ok": tru', encoding="utf-8")  # 写了一半
    broken = service.show_memory({"run_id": run_id})
    assert broken["complete"] is False
    assert broken["missing_artifacts"][0]["problem"].startswith("unreadable")
    assert not any("完整记录" in line and "不完整" not in line for line in broken["summary"])
    artifact.unlink()
    assert service.show_memory({"run_id": run_id})["missing_artifacts"][0]["problem"] == "missing"


# ── 存储打不开：结构化错误（M15）──────────────────────────────────────────────────────


def _readonly(folder: Path) -> None:
    if os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0):
        pytest.skip("需要 POSIX 权限位，且不能以 root 跑")
    for path in folder.glob("memory.db*"):
        if path.name.endswith(("-wal", "-shm")):
            path.unlink()
        else:
            path.chmod(0o444)
    folder.chmod(0o555)


@pytest.mark.parametrize("call", ["query", "show", "answer"])
def test_a_store_that_cannot_be_opened_gives_a_structured_error(tmp_path: Path, call: str) -> None:
    """此前只读数据目录上 memory_query 抛裸 sqlite3.OperationalError。"""
    service = _service(tmp_path)
    run_id = _run(service)
    data = tmp_path / "data"
    with sqlite3.connect(data / "memory.db") as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    service.store.db_path.unlink()  # 读不到库：连接时就会失败
    (data / "memory.db").mkdir()  # 占位：路径是目录，sqlite 打不开
    try:
        calls = {
            "query": lambda: service.query_memory({"text": "八字"}),
            "show": lambda: service.show_memory({"run_id": run_id}),
            "answer": lambda: service.record_ai_answer({"run_id": run_id, "ai_answer_text": "答"}),
        }
        error = _refused(calls[call], "memory.store_unavailable")
        assert " / " in f"{error}", "双语"
    finally:
        (data / "memory.db").rmdir()


def test_a_readonly_store_still_answers_queries(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run_id = _run(service)
    data = tmp_path / "data"
    _readonly(data)
    try:
        fresh = _service(tmp_path)
        assert _ids(fresh.query_memory({})) == [run_id]
        assert fresh.show_memory({"run_id": run_id})["ok"] is True, "点用记账写不进去也不妨碍读"
        _refused(lambda: fresh.record_ai_answer({"run_id": run_id, "ai_answer_text": "答"}), "memory.store_unavailable")
    finally:
        data.chmod(0o755)
        for path in data.glob("memory.db*"):
            path.chmod(0o644)


# ── 重建（M8 / M13）───────────────────────────────────────────────────────────────────


def _tree(service: HorosaSkillService) -> dict[str, set[str]]:
    """库里每个 run 对应的产物文件名（不含 manifest 行）——和 runs/ 目录比。"""
    with service.store.connect() as conn:
        rows = conn.execute("SELECT run_id, path FROM artifacts WHERE kind != 'run_manifest'").fetchall()
    found: dict[str, set[str]] = {}
    for row in rows:
        found.setdefault(row["run_id"], set()).add(Path(row["path"]).name)
    return found


def test_a_lost_database_is_rebuilt_from_the_artifact_tree(tmp_path: Path) -> None:
    from horosa_skill.memory.rebuild import rebuild_from_artifacts

    service = _service(tmp_path)
    answered = _run(service, name="王小明")
    service.record_ai_answer({"run_id": answered, "user_question": "事业如何", "ai_answer_text": "宜守不宜攻"})
    service.record_ai_answer({"run_id": answered, "ai_answer_text": "改过的解读"})
    plain = _run(service, tool="ziwei_birth")
    before = {run_id: service.show_memory({"run_id": run_id})["result"] for run_id in (answered, plain)}
    files_before = _tree(service)
    for path in (tmp_path / "data").glob("memory.db*"):
        path.unlink()
    service = _service(tmp_path)
    assert service.query_memory({})["count"] == 0
    report = rebuild_from_artifacts(service.store, min_age_seconds=0)
    assert report["restored_runs"] == {"total": 2, "from_manifest": 2, "from_artifacts": 0}
    assert report["complete"] is True and report["unreadable_count"] == 0
    assert _tree(service) == files_before
    for run_id, old in before.items():
        new = service.show_memory({"run_id": run_id})["result"]
        for key in ("query_text", "user_question", "ai_answer_text", "created_at", "group_id", "subject", "answer_history"):
            assert new[key] == old[key], key
        assert [c["tool_name"] for c in new["tool_calls"]] == [c["tool_name"] for c in old["tool_calls"]]
    assert _ids(service.query_memory({"entity": "王小明", "text": "宜守不宜攻"})) == [answered]
    again = rebuild_from_artifacts(service.store, min_age_seconds=0)
    assert again["restored_runs"]["total"] == 0 and again["already_indexed"] == 2, "幂等"


def test_a_run_without_a_manifest_is_rebuilt_from_its_artifacts(tmp_path: Path) -> None:
    from horosa_skill.memory.rebuild import rebuild_from_artifacts

    service = _service(tmp_path)
    run_id = _run(service, name="王小明")
    for path in (tmp_path / "data" / "runs").rglob(f"{run_id}_manifest.json"):
        path.unlink()
    for path in (tmp_path / "data").glob("memory.db*"):
        path.unlink()
    service = _service(tmp_path)
    report = rebuild_from_artifacts(service.store, min_age_seconds=0)
    assert report["restored_runs"]["from_artifacts"] == 1
    assert report["manifests_written"] == 1
    assert _ids(service.query_memory({"entity": "王小明", "tool": "八字"})) == [run_id]


def test_rebuild_adopts_orphan_files_but_not_ones_a_writer_may_still_own(tmp_path: Path) -> None:
    from horosa_skill.memory.rebuild import rebuild_from_artifacts

    service = _service(tmp_path)
    run_id = _run(service)
    with service.store.connect() as conn:  # 进程在提交前被杀：文件在，行不在
        conn.execute("DELETE FROM artifacts WHERE run_id = ? AND kind = 'tool_result'", (run_id,))
        conn.execute("DELETE FROM tool_calls WHERE run_id = ?", (run_id,))
        conn.commit()
    fresh = rebuild_from_artifacts(service.store)
    assert fresh["adopted_artifacts"] == 0 and fresh["skipped_recent"] == 1, "一分钟内的文件可能还在被写"
    old = rebuild_from_artifacts(service.store, min_age_seconds=0)
    assert old["adopted_artifacts"] == 1
    record = service.show_memory({"run_id": run_id})["result"]
    assert [c["tool_name"] for c in record["tool_calls"]] == ["bazi_birth"]


def test_stale_temp_files_are_reported_and_only_swept_when_asked(tmp_path: Path) -> None:
    from horosa_skill.memory.rebuild import TMP_ABANDONED_SECONDS, rebuild_from_artifacts

    service = _service(tmp_path)
    _run(service)
    folder = next((tmp_path / "data" / "runs").rglob("*_manifest.json")).parent
    stale = folder / ".x.json.999999.abcdef12.tmp"
    live = folder / f".y.json.{os.getpid()}.abcdef12.tmp"
    for path in (stale, live):
        path.write_text("{", encoding="utf-8")
    old = datetime.now(UTC).timestamp() - TMP_ABANDONED_SECONDS - 10
    os.utime(stale, (old, old))
    report = rebuild_from_artifacts(service.store, min_age_seconds=0)
    assert report["sweep"]["tmp_files"]["stale"] == 1 and stale.exists()
    swept = rebuild_from_artifacts(service.store, min_age_seconds=0, sweep=True)
    assert swept["sweep"]["removed"]["tmp_files"] == 1
    assert not stale.exists() and live.exists(), "活着的写者的临时文件不动"


def test_quarantine_is_visible_to_later_processes_and_never_deleted(tmp_path: Path) -> None:
    """此前坏库被隔离后，新库是空的，检索只是「没有结果」：没有警告，别的进程更不知道。"""
    service = _service(tmp_path)
    run_id = _run(service)
    db = tmp_path / "data" / "memory.db"
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    for path in (tmp_path / "data").glob("memory.db-*"):
        path.unlink()
    db.write_bytes(b"this is not a sqlite database " * 50)
    healed = _service(tmp_path)  # 构造时隔离并自动重建
    backups = list((tmp_path / "data").glob("memory.db.corrupt-*.bak"))
    assert len(backups) == 1
    later = _service(tmp_path)  # 另一个进程：只看得到磁盘上的痕迹
    result = later.query_memory({})
    assert _ids(result) == [run_id], "自动重建找回了记录"
    assert any(backups[0].name in line and "rebuild" not in line.split("/")[0] for line in result["warnings"])
    assert backups[0].exists()
    assert healed.store.corruption_recovery["rebuild"]["complete"] is True


def test_runs_on_disk_without_rows_trigger_a_warning(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _run(service)
    with service.store.connect() as conn:
        for table in ("entities", "artifacts", "tool_calls", "runs"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    result = _service(tmp_path).query_memory({})
    assert result["count"] == 0
    assert any("memory rebuild" in line for line in result["warnings"])


def test_doctor_reports_memory_health(tmp_path: Path) -> None:
    from horosa_skill.memory.rebuild import store_health

    service = _service(tmp_path)
    _run(service)
    healthy = store_health(service.store, full=True)
    assert healthy["ok"] is True and healthy["warnings"] == []
    assert healthy["sweep"]["runs_without_rows"]["total"] == 0


# ── CLI：delete / export / rebuild（M6 / M8）─────────────────────────────────────────


def _cli(tmp_path: Path, *args: str, input: str | None = None):
    from horosa_skill.surfaces.cli import app

    data = tmp_path / "data"
    env = {"HOROSA_SKILL_DATA_DIR": str(data), "HOROSA_SERVER_ROOT": "http://127.0.0.1:9",
           "HOROSA_CHART_SERVER_ROOT": "http://127.0.0.1:9", "HOROSA_RUNTIME_ROOT": str(tmp_path / "rt")}
    return CliRunner().invoke(app, list(args), env=env, input=input)


def _cli_service(tmp_path: Path) -> HorosaSkillService:
    data = tmp_path / "data"
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=data,
                        db_path=data / "memory.db", output_dir=data / "runs", runtime_root=tmp_path / "rt")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def test_cli_delete_lists_first_and_deletes_with_yes(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    mine = _run(service, name="王小明")
    other = _run(service, name="李四")
    files = [p for p in (tmp_path / "data" / "runs").rglob(f"{mine}_*")]
    assert files
    dry = _cli(tmp_path, "memory", "delete", "--entity", "王小明")
    assert dry.exit_code == 0, dry.output
    plan = json.loads(dry.stdout)
    assert plan["dry_run"] is True and plan["runs"] == 1 and all(p.exists() for p in files)
    done = _cli(tmp_path, "memory", "delete", "--entity", "王小明", "--yes")
    assert json.loads(done.stdout)["deleted_runs"] == 1
    assert not any(p.exists() for p in files)
    fresh = _cli_service(tmp_path)
    assert _ids(fresh.query_memory({})) == [other]
    assert fresh.query_memory({"text": "王小明"})["count"] == 0, "检索文档一起删了"
    from horosa_skill.memory.rebuild import rebuild_from_artifacts

    assert rebuild_from_artifacts(fresh.store, min_age_seconds=0)["restored_runs"]["total"] == 0, "删掉的不会被重建找回"


def test_cli_delete_needs_a_selection(tmp_path: Path) -> None:
    result = _cli(tmp_path, "memory", "delete", "--yes")
    assert result.exit_code == 2
    assert json.loads(result.stderr)["code"] == "memory.selection.missing"


def test_cli_export_writes_a_folder_a_person_can_read(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    run_id = _run(service, name="王小明")
    service.record_ai_answer({"run_id": run_id, "ai_answer_text": "宜守不宜攻"})
    out = tmp_path / "export"
    result = _cli(tmp_path, "memory", "export", "--entity", "王小明", "--out", str(out))
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["runs"] == 1
    folder = next(p for p in out.iterdir() if p.is_dir())
    text = (folder / "run.md").read_text(encoding="utf-8")
    assert "宜守不宜攻" in text and "八字" in text
    assert (folder / "manifest.json").exists() and list((folder / "artifacts").glob("*.json"))
    assert "run.md" in (out / "index.md").read_text(encoding="utf-8")
    again = _cli(tmp_path, "memory", "export", "--entity", "王小明", "--out", str(out))
    assert again.exit_code == 2 and json.loads(again.stderr)["code"] == "memory.export.target_invalid"


def test_cli_query_keeps_printing_a_list_and_refuses_bad_input(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    run_id = _run(service)
    listed = _cli(tmp_path, "memory", "query", "--tool", "八字", "--no-include-payload")
    assert listed.exit_code == 0, listed.output
    assert [row["run_id"] for row in json.loads(listed.stdout)] == [run_id]
    bad = _cli(tmp_path, "memory", "query", "--after", "昨天")
    assert bad.exit_code == 2 and json.loads(bad.stderr)["code"] == "memory.query.invalid_time"
    unknown = _cli(tmp_path, "memory", "answer", "--stdin", input=json.dumps({"run_id": "f" * 32, "ai_answer_text": "答"}))
    assert json.loads(unknown.stderr)["code"] == "memory.run.not_found"


def test_cli_rebuild_runs_on_a_healthy_store(tmp_path: Path) -> None:
    _run(_cli_service(tmp_path))
    result = _cli(tmp_path, "memory", "rebuild")
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["restored_runs"]["total"] == 0 and report["complete"] is True


def test_deleting_a_profile_says_how_many_runs_mention_the_person(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.profile({"action": "save", "name": "妈妈", "data": MOM})
    _run(service, profile="我妈")
    result = service.profile({"action": "delete", "name": "妈妈"})
    assert result["stored_runs_mentioning"] == 1
    assert any('memory delete --entity "妈妈"' in line for line in result["warnings"])
    assert service.query_memory({"entity": "妈妈"})["count"] == 1, "不连带删除"
