"""`uninstall --purge-data`：只删本工具自己的东西（docs/LESSONS.md v0.50.0-dev「purge 整个删掉数据目录」）。

旧实现：要保留的（知识库 / 档案）都不在时，把 `HOROSA_SKILL_DATA_DIR` **整个 rmtree**。数据目录是用户自己指的
（MCPB / 插件的设置项里就能填），指到 `~/Documents/horosa`、指到一个已经放着别的东西的文件夹都很正常 ——
里头不是本工具写的文件跟着一起没了，而且 dry-run 只印一行目录名，看不出来。

这里钉四件事：白名单外的东西原地不动并在结果里列出来；目录空了才 rmdir；数据目录是家目录 / 文件系统根 /
包着 runtime 根时整条命令拒绝（一个字节都不删）；dry-run 的清单就是真删的清单。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from horosa_skill.config import Settings
from horosa_skill.errors import RuntimeError as HorosaRuntimeError
from horosa_skill.runtime import HorosaRuntimeManager
from horosa_skill.surfaces import cli


def _settings(tmp_path: Path, *, data: Path | None = None, runtime_root: Path | None = None) -> Settings:
    data = data or tmp_path / "data"
    return Settings(
        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
        data_dir=data, db_path=data / "memory.db", output_dir=data / "runs", trace_dir=data / "traces",
        runtime_root=runtime_root or tmp_path / "rt",
    )


def _manager(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> HorosaRuntimeManager:
    manager = HorosaRuntimeManager(settings)
    monkeypatch.setattr(manager, "stop_local_services", lambda **_: {"ok": True})
    return manager


def _skill_files(data: Path) -> None:
    """一份「用过一阵子」的数据目录：记忆库（含 WAL 与一次损坏隔离的备份）、产物、trace、账本、OpenClaw 自检结果。"""
    (data / "runs" / "2026" / "11").mkdir(parents=True)
    (data / "runs" / "2026" / "11" / "r.json").write_text("{}", encoding="utf-8")
    (data / "traces").mkdir()
    (data / "traces" / "t.jsonl").write_text("{}\n", encoding="utf-8")
    for name in ("memory.db", "memory.db-wal", "memory.db-shm", "memory.db.corrupt-20261101T000000Z.bak",
                 "jev_events.jsonl", "openclaw_smoke_check.json"):
        (data / name).write_text("x", encoding="utf-8")


def _foreign_files(data: Path) -> list[Path]:
    (data / "照片").mkdir(parents=True, exist_ok=True)
    (data / "照片" / "全家福.jpg").write_bytes(b"\xff\xd8")
    (data / "报税-2025.pdf").write_bytes(b"%PDF")
    return [data / "照片", data / "报税-2025.pdf"]


def test_purge_leaves_what_the_skill_did_not_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    _skill_files(settings.data_dir)
    foreign = _foreign_files(settings.data_dir)
    manager = _manager(settings, monkeypatch)

    done = manager.uninstall(purge_data=True, yes=True)

    assert (settings.data_dir / "照片" / "全家福.jpg").read_bytes() == b"\xff\xd8"
    assert (settings.data_dir / "报税-2025.pdf").read_bytes() == b"%PDF"
    assert sorted(done["left_in_place"]) == sorted(str(p) for p in foreign)
    assert str(settings.data_dir) not in done["removed"]
    survivors = sorted(p.name for p in settings.data_dir.iterdir())
    assert survivors == sorted(p.name for p in foreign), "本工具写的每一样都该删掉，别的一样不动"


def test_an_all_ours_data_dir_is_removed_and_listed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    _skill_files(settings.data_dir)
    manager = _manager(settings, monkeypatch)

    plan = manager.uninstall(purge_data=True)
    assert plan["would_remove"][-1] == str(settings.data_dir) and plan["left_in_place"] == []
    assert str(settings.data_dir / "memory.db-wal") in plan["would_remove"]

    done = manager.uninstall(purge_data=True, yes=True)
    assert not settings.data_dir.exists() and done["left_in_place"] == []


def test_everything_the_real_stores_write_is_on_the_allow_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """锁步：记忆库、产物、trace、命主档案、自备知识库（含回收站与索引）、决策账本各真写一次，然后全清 ——
    数据目录必须整个消失。以后谁往数据目录里多写一种文件而没在 `purge.OWNED_NAMES` 登记，这里会剩下它。"""
    from horosa_skill import profiles as P
    from horosa_skill.decisions.ledger import LEDGER_FILENAME, DecisionLedger
    from horosa_skill.knowledge import user as uk
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.tracing import TraceRecorder

    settings = _settings(tmp_path)
    settings = settings.model_copy(update={"user_knowledge_dir": settings.data_dir / "knowledge"})
    MemoryStore(settings)
    with TraceRecorder(settings).span(workflow_name="purge.lockstep", metadata={}):
        pass
    P.run_action(P.ProfileStore(settings), {"action": "save", "name": "甲", "data": {
        "date": "1990-1-1", "time": "12:00", "zone": "Asia/Shanghai", "lat": "31n13", "lon": "121e28", "gender": "男"}})
    uk.add_entry(settings, text="v1", entry_id="笔记")
    uk.add_entry(settings, text="v2", entry_id="笔记", overwrite=True)  # 回收站里留一份
    assert DecisionLedger(settings.data_dir / LEDGER_FILENAME).append({"event": "x"})
    (settings.data_dir / "runs" / "r.json").write_text("{}", encoding="utf-8")
    written = sorted(p.name for p in settings.data_dir.iterdir())
    assert {"memory.db", "runs", "traces", "profiles", "knowledge", uk.STATE_DIRNAME, LEDGER_FILENAME} <= set(written), written
    manager = _manager(settings, monkeypatch)

    done = manager.uninstall(purge_data=True, purge_knowledge=True, purge_profiles=True, yes=True)

    assert done["left_in_place"] == [] and not settings.data_dir.exists(), (written, done)


@pytest.mark.parametrize("flags", [
    {"purge_data": False},
    {"purge_data": True},
    {"purge_data": True, "purge_knowledge": True},
    {"purge_data": True, "purge_knowledge": True, "purge_profiles": True},
])
def test_the_dry_run_lists_exactly_what_the_real_run_removes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flags: dict) -> None:
    settings = _settings(tmp_path)
    _skill_files(settings.data_dir)
    _foreign_files(settings.data_dir)
    for name in ("knowledge", "knowledge-state", "profiles"):
        (settings.data_dir / name).mkdir()
        (settings.data_dir / name / "f").write_text("x", encoding="utf-8")
    (settings.runtime_root / "current").mkdir(parents=True)
    manager = _manager(settings, monkeypatch)

    plan = manager.uninstall(**flags)
    done = manager.uninstall(**flags, yes=True)

    assert plan["dry_run"] is True and done["dry_run"] is False
    assert plan["would_remove"] == done["removed"]
    assert plan["kept"] == done["kept"] and plan["left_in_place"] == done["left_in_place"]
    for text in done["removed"]:
        assert not Path(text).exists()
    for text in done["kept"] + done["left_in_place"]:
        assert Path(text).exists()


def test_without_purge_data_the_data_dir_is_not_even_looked_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    _skill_files(settings.data_dir)
    manager = _manager(settings, monkeypatch)
    done = manager.uninstall(yes=True)
    assert done["left_in_place"] == [] and (settings.data_dir / "memory.db").exists()


def test_a_symlinked_child_is_unlinked_not_followed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """有人把 runs/ 链到大盘上：删的是那个链接，链接指向的目录不是本工具的数据目录，不碰。"""
    settings = _settings(tmp_path)
    elsewhere = tmp_path / "big-disk" / "runs"
    elsewhere.mkdir(parents=True)
    (elsewhere / "r.json").write_text("{}", encoding="utf-8")
    settings.data_dir.mkdir()
    try:
        os.symlink(elsewhere, settings.data_dir / "runs", target_is_directory=True)
    except OSError:
        pytest.skip("[host] this account cannot create symlinks")
    manager = _manager(settings, monkeypatch)

    manager.uninstall(purge_data=True, yes=True)

    assert (elsewhere / "r.json").is_file() and not (settings.data_dir / "runs").exists()


# ── 拒绝：数据目录指到了不可能整个归本工具的地方 ──────────────────────────────


def _refusal_cases(tmp_path: Path) -> dict[str, Settings]:
    home = tmp_path / "home"
    return {
        "home": _settings(tmp_path, data=home),
        "above_home": _settings(tmp_path, data=tmp_path),
        "filesystem_root": _settings(tmp_path, data=Path(tmp_path.anchor)),
        "contains_runtime_root": _settings(tmp_path, data=tmp_path / "all", runtime_root=tmp_path / "all" / "runtime"),
    }


@pytest.mark.parametrize("case", ["home", "above_home", "filesystem_root", "contains_runtime_root"])
@pytest.mark.parametrize("yes", [False, True])
def test_purge_is_refused_where_the_data_dir_cannot_be_ours(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str, yes: bool) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    settings = _refusal_cases(tmp_path)[case]
    if case != "filesystem_root":
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        (settings.data_dir / "runs").mkdir(exist_ok=True)
        (settings.data_dir / "runs" / "不是本工具的.txt").write_text("x", encoding="utf-8")
    (settings.runtime_root / "current").mkdir(parents=True)
    manager = _manager(settings, monkeypatch)
    removed: list[str] = []
    # 两个删除入口都换成只记账：万一拒绝失效（负向对照），这条用例也绝不真的去删 `/` 或家目录里的东西。
    monkeypatch.setattr("horosa_skill.runtime.manager._rmtree_force", lambda path: removed.append(str(path)))
    monkeypatch.setattr("horosa_skill.runtime.purge.remove_owned", lambda path: removed.append(str(path)))

    with pytest.raises(HorosaRuntimeError) as excinfo:
        manager.uninstall(purge_data=True, yes=yes)

    assert excinfo.value.code == "runtime.purge_refused"
    assert excinfo.value.details["reason"] == case and excinfo.value.details["data_dir"] == str(settings.data_dir)
    assert " / " in str(excinfo.value), "拒绝的话要中英双语"
    assert removed == [] and (settings.runtime_root / "current").is_dir(), "拒绝 = 一样都不删，runtime 也不删"
    if case != "filesystem_root":
        assert (settings.data_dir / "runs" / "不是本工具的.txt").is_file()


@pytest.mark.parametrize("case", ["home", "contains_runtime_root"])
def test_a_plain_uninstall_is_not_refused_there(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    """拒的是「清数据」，不是卸载：不带 --purge-data 时数据目录指在哪儿都不相干。"""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    settings = _refusal_cases(tmp_path)[case]
    (settings.runtime_root / "current").mkdir(parents=True)
    manager = _manager(settings, monkeypatch)
    done = manager.uninstall(yes=True)
    assert done["ok"] is True and not (settings.runtime_root / "current").exists()


def test_cli_prints_the_refusal_as_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "runs").mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(home))
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "rt"))

    result = CliRunner().invoke(cli.app, ["uninstall", "--purge-data", "--yes"])

    assert result.exit_code == 2 and "Traceback" not in result.stderr
    payload = json.loads(result.stderr[result.stderr.index("{"):])
    assert payload["ok"] is False and payload["code"] == "runtime.purge_refused"
    assert (home / "runs").is_dir()
