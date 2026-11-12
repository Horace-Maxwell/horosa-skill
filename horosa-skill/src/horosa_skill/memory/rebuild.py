"""记忆库的「以产物为准」：照 `runs/` 里的文件重建索引、清点崩溃残留、给查询与 doctor 报健康状况。

`runs/` 下每个 run 都有完整副本：每次调用一份产物（`{run}_{tool}_{tool_call_id}.json`，带 `record_meta` 与 `conversation`），
外加一份 manifest（`{run}_manifest.json`，整条 run 的行：问答、实体、调用、产物清单）。数据库只是这些文件的索引：
坏库被隔离、或者库被删了，库里的每张表与检索文档都能从这些文件重新填回来。

保守的规矩：
- 只增不删。库里已有的行不改（只修指错地方的产物路径）；`--sweep` 之外不删任何文件，删也只删确定没人在写的临时文件与空 run。
- 太新的文件（`min_age_seconds` 内）不收：那可能是另一个进程正写到一半、还没提交的那份。
- 隔离出来的 `*.corrupt-*.bak` 永不删除：那是用户的数据，删不删由用户决定。
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from horosa_skill.memory import search as _search

if TYPE_CHECKING:
    from horosa_skill.memory.store import MemoryStore

_MANIFEST = re.compile(r"^([0-9a-f]{32})_manifest\.json$")
_REPORT = re.compile(r"^([0-9a-f]{32})_(.+)_report_(\d{8}T\d{6}Z)\.(\w+)$")
_ARTIFACT = re.compile(r"^([0-9a-f]{32})_(.+)_(\d+|dispatch)\.json$")
_TMP = re.compile(r"^\..+\.(\d+)\.[0-9a-f]{8}\.tmp$")

# 临时文件多旧才算残留：写它的进程已经不在且超过 10 分钟，或者不管谁写的、超过一天。
TMP_STALE_SECONDS = 600
TMP_ABANDONED_SECONDS = 86400
# 空 run（没有调用、没有产物、没有答案）多旧才报：调度可能先建 run 再跑很久的择时。
EMPTY_RUN_SECONDS = 3600
# 报告里列多少个样本（完整数量另给）。
SAMPLE = 10


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _mtime_iso(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, UTC).replace(microsecond=0).isoformat()
    except OSError:
        return _now()


def _age(path: Path, now: float) -> float:
    try:
        return now - path.stat().st_mtime
    except OSError:
        return 0.0


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)  # 信号 0 只问「在不在」，不发任何信号
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True  # 在，只是不归我们管
    return True


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@dataclass
class RunFiles:
    run_id: str
    manifest: Path | None = None
    artifacts: list[tuple[Path, str, str]] = field(default_factory=list)  # (路径, 文件名里的技法, 调用 id 或 dispatch)
    reports: list[tuple[Path, str, str]] = field(default_factory=list)  # (路径, 技法, 格式)

    @property
    def newest(self) -> str:
        paths = [self.manifest] if self.manifest else []
        paths += [item[0] for item in self.artifacts]
        return max((str(path.parent) for path in paths), default="")


@dataclass
class Inventory:
    runs: dict[str, RunFiles] = field(default_factory=dict)
    tmp_files: list[Path] = field(default_factory=list)
    other_files: int = 0


def scan_artifact_tree(output_dir: Path | None) -> Inventory:
    """列出 `runs/` 下按 run 归好的文件。只看文件名，不读内容。"""
    inventory = Inventory()
    if output_dir is None or not output_dir.is_dir():
        return inventory
    for folder, _, names in os.walk(output_dir):
        for name in names:
            path = Path(folder) / name
            if _TMP.match(name):
                inventory.tmp_files.append(path)
                continue
            match = _MANIFEST.match(name)
            if match:
                inventory.runs.setdefault(match.group(1), RunFiles(match.group(1))).manifest = path
                continue
            match = _REPORT.match(name)
            if match:
                inventory.runs.setdefault(match.group(1), RunFiles(match.group(1))).reports.append(
                    (path, match.group(2), match.group(4).lower())
                )
                continue
            match = _ARTIFACT.match(name)
            if match:
                inventory.runs.setdefault(match.group(1), RunFiles(match.group(1))).artifacts.append(
                    (path, match.group(2), match.group(3))
                )
                continue
            inventory.other_files += 1
    return inventory


def _db_state(conn: sqlite3.Connection) -> tuple[set[str], dict[str, dict[str, sqlite3.Row]]]:
    run_ids = {row[0] for row in conn.execute("SELECT id FROM runs")}
    artifacts: dict[str, dict[str, sqlite3.Row]] = {}
    for row in conn.execute("SELECT id, run_id, kind, path, tool_call_id FROM artifacts"):
        artifacts.setdefault(row["run_id"], {})[Path(row["path"]).name] = row
    return run_ids, artifacts


def _stale_tmp(path: Path, now: float) -> bool:
    match = _TMP.match(path.name)
    age = _age(path, now)
    if age > TMP_ABANDONED_SECONDS:
        return True
    return bool(match) and age > TMP_STALE_SECONDS and not _pid_alive(int(match.group(1)))


def sweep_report(store: MemoryStore, *, inventory: Inventory | None = None, delete: bool = False) -> dict[str, Any]:
    """崩溃残留清点：临时文件、没有行的产物、没有 manifest 的 run、文件不见了的产物行、空 run。

    默认只报；`delete=True` 只删确定没人在写的临时文件，与旧于一小时、什么都没有的空 run（行与它的 manifest）。"""
    now = time.time()
    inventory = inventory or scan_artifact_tree(store.output_dir)
    report: dict[str, Any] = {"deleted": delete}
    stale = [path for path in inventory.tmp_files if _stale_tmp(path, now)]
    report["tmp_files"] = {"total": len(inventory.tmp_files), "stale": len(stale), "sample": [str(p) for p in stale[:SAMPLE]]}
    with store.connect() as conn:
        run_ids, artifact_rows = _db_state(conn)
        missing_files = [
            row["path"]
            for rows in artifact_rows.values()
            for row in rows.values()
            if not Path(row["path"]).is_file()
        ]
        cutoff = datetime.fromtimestamp(now - EMPTY_RUN_SECONDS, UTC).replace(microsecond=0).isoformat()
        empty = [
            row[0]
            for row in conn.execute(
                """
                SELECT id FROM runs WHERE updated_at < ? AND COALESCE(ai_answer_text, '') = ''
                  AND NOT EXISTS (SELECT 1 FROM tool_calls t WHERE t.run_id = runs.id)
                  AND NOT EXISTS (SELECT 1 FROM artifacts a WHERE a.run_id = runs.id AND a.kind != 'run_manifest')
                """,
                (cutoff,),
            )
        ]
    on_disk_artifacts = {
        path.name: run_id for run_id, files in inventory.runs.items() for path, _, _ in files.artifacts
    }
    orphans = [name for name, run_id in on_disk_artifacts.items() if name not in artifact_rows.get(run_id, {})]
    without_manifest = [
        run_id
        for run_id in run_ids
        if not (inventory.runs.get(run_id) and inventory.runs[run_id].manifest) and run_id not in set(empty)
    ]
    unindexed = [run_id for run_id in inventory.runs if run_id not in run_ids]
    report["artifacts_without_rows"] = {"total": len(orphans), "sample": orphans[:SAMPLE]}
    report["runs_without_rows"] = {"total": len(unindexed), "sample": unindexed[:SAMPLE]}
    report["runs_without_manifest"] = {"total": len(without_manifest), "sample": without_manifest[:SAMPLE]}
    report["rows_with_missing_files"] = {"total": len(missing_files), "sample": missing_files[:SAMPLE]}
    report["empty_runs"] = {"total": len(empty), "sample": empty[:SAMPLE]}
    if delete:
        removed_tmp = 0
        for path in stale:
            try:
                path.unlink()
                removed_tmp += 1
            except OSError:
                continue
        removed_runs = 0
        if empty:
            with store._writer() as conn:
                conn.execute("BEGIN IMMEDIATE")
                for run_id in empty:
                    # 事务里再确认一次：这期间有人往里写了就不动它
                    still_empty = conn.execute(
                        """
                        SELECT 1 FROM runs WHERE id = ? AND COALESCE(ai_answer_text, '') = ''
                          AND NOT EXISTS (SELECT 1 FROM tool_calls t WHERE t.run_id = runs.id)
                          AND NOT EXISTS (SELECT 1 FROM artifacts a WHERE a.run_id = runs.id AND a.kind != 'run_manifest')
                        """,
                        (run_id,),
                    ).fetchone()
                    if not still_empty:
                        continue
                    for row in conn.execute("SELECT path FROM artifacts WHERE run_id = ?", (run_id,)).fetchall():
                        Path(row["path"]).unlink(missing_ok=True)
                    conn.execute("DELETE FROM entities WHERE run_id = ?", (run_id,))
                    conn.execute("DELETE FROM artifacts WHERE run_id = ?", (run_id,))
                    conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
                    removed_runs += 1
                conn.commit()
        report["removed"] = {"tmp_files": removed_tmp, "empty_runs": removed_runs}
    return report


# ---- 重建 ----


def _manifest_tool_calls(manifest: dict[str, Any], files: RunFiles) -> list[tuple[int | None, dict[str, Any]]]:
    """manifest 里的调用配上调用 id：新 manifest 自带 `id`；老的按技法、按文件名里的 id 顺序配对。"""
    calls = [call for call in manifest.get("tool_calls") or [] if isinstance(call, dict)]
    by_tool: dict[str, list[int]] = {}
    for _, tool, suffix in files.artifacts:
        if suffix.isdigit():
            by_tool.setdefault(tool, []).append(int(suffix))
    for ids in by_tool.values():
        ids.sort()
    paired: list[tuple[int | None, dict[str, Any]]] = []
    for call in calls:
        call_id = call.get("id")
        if not isinstance(call_id, int):
            ids = by_tool.get(_safe(call.get("tool_name")), [])
            call_id = ids.pop(0) if ids else None
        paired.append((call_id, call))
    return paired


def _safe(name: Any) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(name or "")) or "_"


def _insert_tool_call(conn: sqlite3.Connection, run_id: str, call_id: int | None, call: dict[str, Any]) -> int:
    taken = call_id is not None and conn.execute("SELECT 1 FROM tool_calls WHERE id = ?", (call_id,)).fetchone()
    values = (
        run_id,
        call.get("tool_name") or "unknown",
        1 if call.get("ok") else 0,
        json.dumps(call.get("input") if call.get("input") is not None else {}, ensure_ascii=False),
        json.dumps(call.get("summary") or [], ensure_ascii=False),
        json.dumps(call.get("warnings") or [], ensure_ascii=False),
        json.dumps(call["error"], ensure_ascii=False) if call.get("error") else None,
        call.get("trace_id"),
        call.get("group_id"),
        call.get("evaluation_case_id"),
        call.get("created_at") or _now(),
    )
    columns = "run_id, tool_name, ok, input_json, summary_json, warnings_json, error_json, trace_id, group_id, evaluation_case_id, created_at"
    if call_id is not None and not taken:
        conn.execute(f"INSERT INTO tool_calls (id, {columns}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (call_id, *values))
        return call_id
    cursor = conn.execute(f"INSERT INTO tool_calls ({columns}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values)
    return int(cursor.lastrowid)


def _artifact_kind(meta: dict[str, Any], suffix: str) -> str:
    """门面产物（文件名后缀 dispatch）按 record_meta.kind 认（dispatch_result / hecan_result）；技法产物是 tool_result。"""
    if suffix != "dispatch":
        return "tool_result"
    kind = meta.get("kind")
    return kind if kind in ("dispatch_result", "hecan_result") else "dispatch_result"


def _call_from_envelope(envelope: dict[str, Any], tool: str, path: Path) -> dict[str, Any]:
    meta = envelope.get("record_meta") if isinstance(envelope.get("record_meta"), dict) else {}
    return {
        "tool_name": envelope.get("tool") or meta.get("tool_name") or tool,
        "ok": bool(envelope.get("ok")),
        "input": envelope.get("input_normalized") if isinstance(envelope.get("input_normalized"), dict) else {},
        "summary": envelope.get("summary") if isinstance(envelope.get("summary"), list) else [],
        "warnings": envelope.get("warnings") if isinstance(envelope.get("warnings"), list) else [],
        "error": envelope.get("error") if isinstance(envelope.get("error"), dict) else None,
        "trace_id": envelope.get("trace_id") or meta.get("trace_id"),
        "group_id": envelope.get("group_id") or meta.get("group_id"),
        "evaluation_case_id": meta.get("evaluation_case_id"),
        "created_at": _mtime_iso(path),
    }


def _insert_artifact(conn: sqlite3.Connection, run_id: str, call_id: int | None, tool: str, kind: str, path: Path, created_at: str) -> None:
    try:
        size: int | None = path.stat().st_size
    except OSError:
        size = None
    # sha256 留空：读取端会按需现算。重建上万份产物时逐个整读算哈希不值得。
    conn.execute(
        "INSERT INTO artifacts (run_id, tool_call_id, tool_name, kind, path, created_at, file_size, sha256) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
        (run_id, call_id, tool, kind, str(path), created_at, size),
    )


def _restore_run(store: MemoryStore, conn: sqlite3.Connection, files: RunFiles, report: dict[str, Any]) -> bool:
    """库里没有这个 run：先照 manifest，manifest 缺了或读不了就照各份产物里的 `record_meta` / `conversation` 填回来。"""
    manifest = _read_json(files.manifest) if files.manifest else None
    if files.manifest and not isinstance(manifest, dict):
        report["unreadable"].append(str(files.manifest))
        manifest = None
    envelopes: list[tuple[Path, str, str, dict[str, Any]]] = []
    for path, tool, suffix in sorted(files.artifacts, key=lambda item: (item[2] == "dispatch", item[2].zfill(12))):
        payload = _read_json(path)
        if isinstance(payload, dict):
            envelopes.append((path, tool, suffix, payload))
        else:
            report["unreadable"].append(str(path))
    run_fields: dict[str, Any]
    if isinstance(manifest, dict) and isinstance(manifest.get("run"), dict):
        run_fields = dict(manifest["run"])
        source = "manifest"
    elif envelopes:
        first = envelopes[0][3]
        meta = first.get("record_meta") if isinstance(first.get("record_meta"), dict) else {}
        conversation = first.get("conversation") if isinstance(first.get("conversation"), dict) else {}
        run_fields = {
            "entrypoint": meta.get("entrypoint") or ("dispatch" if envelopes[0][2] == "dispatch" else "tool"),
            "query_text": conversation.get("query_text"),
            "subject": meta.get("subject") or {},
            "group_id": meta.get("group_id"),
            "user_question": conversation.get("user_question"),
            "ai_answer_text": conversation.get("ai_answer_text"),
            "ai_answer_structured": conversation.get("ai_answer_structured"),
            "answer_meta": conversation.get("answer_meta") or {},
            "created_at": meta.get("created_at") or _mtime_iso(envelopes[0][0]),
            "updated_at": meta.get("updated_at") or meta.get("created_at") or _mtime_iso(envelopes[0][0]),
        }
        source = "artifacts"
    else:
        return False
    now = _now()
    created_at = run_fields.get("created_at") or now
    history = run_fields.get("answer_history")
    conn.execute(
        """
        INSERT INTO runs (id, entrypoint, query_text, subject_json, group_id, created_at, updated_at, user_question_text,
                          ai_answer_text, ai_answer_json, answer_meta_json, usage_count, last_used_at, answer_history_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            files.run_id,
            run_fields.get("entrypoint") or "tool",
            run_fields.get("query_text"),
            json.dumps(run_fields.get("subject") or {}, ensure_ascii=False),
            run_fields.get("group_id"),
            created_at,
            run_fields.get("updated_at") or created_at,
            run_fields.get("user_question") or run_fields.get("query_text"),
            run_fields.get("ai_answer_text"),
            json.dumps(run_fields["ai_answer_structured"], ensure_ascii=False) if run_fields.get("ai_answer_structured") is not None else None,
            json.dumps(run_fields.get("answer_meta") or {}, ensure_ascii=False),
            now,  # 找回来的记录算刚用过：不然 `memory prune` 会把一整批找回的旧 run 当成「久未使用」
            json.dumps(history, ensure_ascii=False) if isinstance(history, list) and history else None,
        ),
    )
    entities: list[dict[str, Any]] = []
    if source == "manifest":
        entities = [item for item in manifest.get("entities") or [] if isinstance(item, dict)]  # type: ignore[union-attr]
    call_ids: dict[str, int] = {}  # 文件名 → 调用 id
    if source == "manifest":
        for call_id, call in _manifest_tool_calls(manifest, files):  # type: ignore[arg-type]
            new_id = _insert_tool_call(conn, files.run_id, call_id, call)
            match = next((item for item in files.artifacts if item[2] == str(call_id)), None)
            if match is not None:
                call_ids[match[0].name] = new_id
    for path, tool, suffix, envelope in envelopes:
        if suffix == "dispatch" or path.name in call_ids:
            continue
        # manifest 之后才写进来的调用（manifest 刷新前进程没了），或者根本没有 manifest：照产物补调用行
        call = _call_from_envelope(envelope, tool, path)
        call_ids[path.name] = _insert_tool_call(conn, files.run_id, int(suffix), call)
        if source == "artifacts" and not entities:
            entities = _entities_from_envelope(store, envelope, run_fields.get("query_text"))
    for path, tool, suffix, envelope in envelopes:
        meta = envelope.get("record_meta") if isinstance(envelope.get("record_meta"), dict) else {}
        kind = _artifact_kind(meta, suffix)
        _insert_artifact(conn, files.run_id, call_ids.get(path.name), meta.get("tool_name") or tool, kind, path, _mtime_iso(path))
    _restore_reports(conn, files, manifest)
    for entity in entities:
        conn.execute(
            """
            INSERT INTO entities (run_id, entity_type, entity_key, display_name, metadata_json, created_at, search_key)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                files.run_id,
                entity.get("entity_type") or "subject",
                entity.get("entity_key") or entity.get("display_name") or "",
                entity.get("display_name") or "",
                json.dumps(entity.get("metadata") or {}, ensure_ascii=False),
                entity.get("created_at") or created_at,
                _search.entity_search_key(entity.get("display_name"), entity.get("entity_key")),
            ),
        )
    if files.manifest:
        _insert_artifact(conn, files.run_id, None, "_run", "run_manifest", files.manifest, now)
    store._write_search_doc(conn, files.run_id, pending=True)
    report["restored_runs"][f"from_{source}"] += 1
    return True


def _entities_from_envelope(store: MemoryStore, envelope: dict[str, Any], query_text: Any) -> list[dict[str, Any]]:
    """没有 manifest 时按产物的归一化输入重建实体。抽取规则属于 service 层（`service.envelope._extract_entities`），
    由 service 构造时挂到 `store.entity_extractor`；memory 层不反向导入 service。没挂（裸 store）就不建实体，run 照样可按字搜。"""
    extractor = getattr(store, "entity_extractor", None)
    if extractor is None:
        return []
    payload = envelope.get("input_normalized") if isinstance(envelope.get("input_normalized"), dict) else {}
    return list(extractor(payload, query_text if isinstance(query_text, str) else None))


def _restore_reports(conn: sqlite3.Connection, files: RunFiles, manifest: Any) -> None:
    """报告：`runs/` 里的照文件名收；manifest 记着的、在别处（用户指定的目录）且文件还在的也收。"""
    seen: set[str] = set()
    for path, tool, fmt in files.reports:
        _insert_artifact(conn, files.run_id, None, tool, f"report_{fmt}", path, _mtime_iso(path))
        seen.add(str(path))
    records = manifest.get("artifacts") if isinstance(manifest, dict) else None
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict) or not str(record.get("kind") or "").startswith("report_"):
            continue
        path = Path(str(record.get("path") or ""))
        if str(path) in seen or not path.is_file():
            continue
        _insert_artifact(conn, files.run_id, None, record.get("tool_name") or "report", record["kind"], path, record.get("created_at") or _mtime_iso(path))
        seen.add(str(path))


def _adopt_files(
    store: MemoryStore, conn: sqlite3.Connection, files: RunFiles, known: dict[str, sqlite3.Row], now: float, min_age: float, report: dict[str, Any]
) -> bool:
    """库里有这个 run：收下没有行的产物文件（含调用行），修正指错地方的路径。返回是否动了库。"""
    changed = False
    for path, tool, suffix in files.artifacts:
        row = known.get(path.name)
        if row is not None:
            if row["path"] != str(path) and not Path(row["path"]).is_file():
                conn.execute("UPDATE artifacts SET path = ? WHERE id = ?", (str(path), row["id"]))
                report["repaired_paths"] += 1
                changed = True
            continue
        if _age(path, now) < min_age:
            report["skipped_recent"] += 1  # 可能是别的进程正写着、还没提交的那份
            continue
        envelope = _read_json(path)
        if not isinstance(envelope, dict):
            report["unreadable"].append(str(path))
            continue
        call_id: int | None = None
        if suffix.isdigit():
            existing = conn.execute("SELECT run_id FROM tool_calls WHERE id = ?", (int(suffix),)).fetchone()
            if existing is not None and existing["run_id"] == files.run_id:
                call_id = int(suffix)
            else:
                call_id = _insert_tool_call(conn, files.run_id, int(suffix), _call_from_envelope(envelope, tool, path))
        meta = envelope.get("record_meta") if isinstance(envelope.get("record_meta"), dict) else {}
        kind = _artifact_kind(meta, suffix)
        _insert_artifact(conn, files.run_id, call_id, meta.get("tool_name") or tool, kind, path, _mtime_iso(path))
        report["adopted_artifacts"] += 1
        changed = True
    for path, tool, fmt in files.reports:
        if path.name not in known and _age(path, now) >= min_age:
            _insert_artifact(conn, files.run_id, None, tool, f"report_{fmt}", path, _mtime_iso(path))
            report["adopted_artifacts"] += 1
            changed = True
    if files.manifest is not None:
        row = known.get(files.manifest.name)
        if row is None:
            _insert_artifact(conn, files.run_id, None, "_run", "run_manifest", files.manifest, _now())
            changed = True
        elif row["path"] != str(files.manifest) and not Path(row["path"]).is_file():
            conn.execute("UPDATE artifacts SET path = ? WHERE id = ?", (str(files.manifest), row["id"]))
            report["repaired_paths"] += 1
            changed = True
    if changed:
        store._write_search_doc(conn, files.run_id, pending=True)
    return changed


def rebuild_from_artifacts(
    store: MemoryStore,
    *,
    budget_seconds: float | None = None,
    index_bodies: bool = True,
    min_age_seconds: float = 60.0,
    sweep: bool = False,
) -> dict[str, Any]:
    """照 `runs/` 的文件把库补齐：没有行的 run 整条找回，有行的 run 收下漏记的产物、补写缺的 manifest，再把正文读进检索。

    幂等：库是好的时候什么都不加。`budget_seconds` 到了就停（`complete: False`），新的 run 先做。"""
    started = time.monotonic()
    deadline = None if budget_seconds is None else started + budget_seconds
    now = time.time()
    report: dict[str, Any] = {
        "ok": True,
        "complete": True,
        "scanned_runs": 0,
        "already_indexed": 0,
        "restored_runs": {"total": 0, "from_manifest": 0, "from_artifacts": 0},
        "adopted_artifacts": 0,
        "repaired_paths": 0,
        "manifests_written": 0,
        "skipped_recent": 0,
        "unreadable": [],
        "not_restored": [],
    }
    inventory = scan_artifact_tree(store.output_dir)
    with store.connect() as conn:
        run_ids, artifact_rows = _db_state(conn)
        max_suffix = max(
            (int(suffix) for files in inventory.runs.values() for _, _, suffix in files.artifacts if suffix.isdigit()), default=0
        )
        for files in sorted(inventory.runs.values(), key=lambda item: item.newest, reverse=True):
            if deadline is not None and time.monotonic() >= deadline:
                report["complete"] = False
                break
            report["scanned_runs"] += 1
            conn.execute("BEGIN IMMEDIATE")
            try:
                exists = conn.execute("SELECT 1 FROM runs WHERE id = ?", (files.run_id,)).fetchone()
                if exists:
                    known = {
                        Path(row["path"]).name: row
                        for row in conn.execute("SELECT id, path, kind FROM artifacts WHERE run_id = ?", (files.run_id,))
                    }
                    if not _adopt_files(store, conn, files, known, now, min_age_seconds, report):
                        report["already_indexed"] += 1
                elif not files.artifacts and not files.manifest:
                    pass  # 只有报告文件：没有可以重建 run 的东西
                elif not _restore_run(store, conn, files, report):
                    report["not_restored"].append(files.run_id)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        if max_suffix:
            # 以后的调用 id 不和磁盘上已有的文件名撞
            conn.execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = 'tool_calls'", (max_suffix,))
            conn.execute(
                "INSERT INTO sqlite_sequence (name, seq) SELECT 'tool_calls', ? WHERE NOT EXISTS"
                " (SELECT 1 FROM sqlite_sequence WHERE name = 'tool_calls')",
                (max_suffix,),
            )
            conn.commit()
        report["restored_runs"]["total"] = report["restored_runs"]["from_manifest"] + report["restored_runs"]["from_artifacts"]
        # 库里有、盘上没有 manifest 的 run：照库补写（太新的跳过，写的人马上会自己写）
        cutoff = datetime.fromtimestamp(now - min_age_seconds, UTC).replace(microsecond=0).isoformat()
        missing_manifest = [
            row[0]
            for row in conn.execute("SELECT id FROM runs WHERE updated_at <= ? ORDER BY created_at DESC", (cutoff,))
            if not (inventory.runs.get(row[0]) and inventory.runs[row[0]].manifest)
            and conn.execute("SELECT 1 FROM tool_calls WHERE run_id = ? LIMIT 1", (row[0],)).fetchone()
        ]
    for run_id in missing_manifest:
        if deadline is not None and time.monotonic() >= deadline:
            report["complete"] = False
            break
        try:
            store._refresh_run_manifest(run_id)
            report["manifests_written"] += 1
        except (OSError, ValueError, sqlite3.Error) as exc:
            report["unreadable"].append(f"{run_id}: {type(exc).__name__}")
    with store.connect() as conn:
        store._sync_search(conn)
    if index_bodies:
        remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
        bodies = store.index_pending_bodies(budget_seconds=remaining)
        if bodies["pending"]:
            report["complete"] = False
    else:
        with store.connect() as conn:
            bodies = {"indexed": 0, "pending": int(conn.execute("SELECT COUNT(*) FROM run_search WHERE state = 0").fetchone()[0])}
    report["search"] = {"bodies_indexed": bodies["indexed"], "bodies_pending": bodies["pending"]}
    report["sweep"] = sweep_report(store, inventory=scan_artifact_tree(store.output_dir), delete=sweep)
    report["quarantined"] = [str(path) for path in quarantined_backups(store)]
    report["unreadable_count"] = len(report["unreadable"])
    report["unreadable"] = report["unreadable"][:SAMPLE]
    report["elapsed_seconds"] = round(time.monotonic() - started, 2)
    report["at"] = _now()
    try:
        store.set_meta(
            "last_rebuild",
            {key: report[key] for key in ("at", "complete", "restored_runs", "adopted_artifacts", "unreadable_count")},
        )
    except (sqlite3.Error, OSError):
        pass
    store._health_cache = None
    return report


# ---- 健康状况 ----


def quarantined_backups(store: MemoryStore) -> list[Path]:
    parent = store.db_path.parent
    prefix = f"{store.db_path.name}.corrupt-"
    try:
        return sorted(path for path in parent.iterdir() if path.name.startswith(prefix) and path.name.endswith(".bak"))
    except OSError:
        return []


def _tree_has_runs(output_dir: Path | None) -> bool:
    if output_dir is None or not output_dir.is_dir():
        return False
    for _, _, names in os.walk(output_dir):
        if any(_MANIFEST.match(name) or _ARTIFACT.match(name) for name in names):
            return True
    return False


HEALTH_CACHE_SECONDS = 60.0


def store_health(store: MemoryStore, *, full: bool = False) -> dict[str, Any]:
    """存档要不要提醒用户：有隔离出来的坏库、有没进库的 run 文件、上次重建没做完。

    查询时 `full=False`：先做几样便宜的检查，有可疑才清点整棵 `runs/`（结果进程内缓存一分钟）；doctor 用 `full=True` 每次都清点。"""
    from horosa_skill.errors import bilingual

    if not full and store._health_cache is not None and time.monotonic() - store._health_cache[0] < HEALTH_CACHE_SECONDS:
        return store._health_cache[1]
    backups = quarantined_backups(store)
    last_rebuild = store.get_meta("last_rebuild")
    suspicious = full or bool(backups) or (isinstance(last_rebuild, dict) and not last_rebuild.get("complete"))
    if not suspicious:
        try:
            with store.connect() as conn:
                empty = conn.execute("SELECT 1 FROM runs LIMIT 1").fetchone() is None
        except sqlite3.Error:
            empty = False
        suspicious = empty and _tree_has_runs(store.output_dir)
    result: dict[str, Any] = {"ok": True, "quarantined": [str(path) for path in backups], "warnings": []}
    if suspicious:
        try:
            sweep = sweep_report(store)
        except (sqlite3.Error, OSError) as exc:
            sweep = {"error": f"{type(exc).__name__}: {exc}"}
        result["sweep"] = sweep
        unindexed = (sweep.get("runs_without_rows") or {}).get("total", 0)
        orphans = (sweep.get("artifacts_without_rows") or {}).get("total", 0)
        if unindexed or orphans:
            result["ok"] = False
            result["warnings"].append(
                bilingual(
                    f"本机存档里有 {unindexed} 个 run、{orphans} 份产物文件不在记忆库里，检索找不到它们。"
                    "跑 `horosa-skill memory rebuild` 照 runs/ 里的文件把它们找回来（只增不删）。",
                    f"{unindexed} stored runs and {orphans} artifact files are not in the memory index, so searches miss them."
                    " Run `horosa-skill memory rebuild` to restore them from the files under runs/ (it only adds).",
                )
            )
    if backups:
        result["ok"] = False
        rebuilt = isinstance(last_rebuild, dict) and last_rebuild.get("complete")
        restored = (last_rebuild.get("restored_runs") or {}).get("total", 0) if isinstance(last_rebuild, dict) else 0
        names = "、".join(path.name for path in backups[:3])
        if rebuilt:
            result["warnings"].append(
                bilingual(
                    f"记忆库曾经损坏，坏库已隔离为 {names}；索引已照 runs/ 里的产物重建（找回 {restored} 条）。"
                    "隔离文件不会被自动删除，确认记录都在之后可以自己删掉它。",
                    f"The memory database was damaged and has been set aside as {names}; the index was rebuilt from the"
                    f" artifacts under runs/ ({restored} runs restored). The set-aside file is never deleted automatically:"
                    " once the records look complete you may delete it yourself.",
                )
            )
        else:
            result["warnings"].append(
                bilingual(
                    f"记忆库曾经损坏，坏库已隔离为 {names}，索引还没有完整重建，部分旧记录可能搜不到。"
                    "跑 `horosa-skill memory rebuild` 照 runs/ 里的产物找回它们；隔离文件不会被删除。",
                    f"The memory database was damaged and has been set aside as {names}; the index has not been fully rebuilt,"
                    " so some older runs may be missing from results. Run `horosa-skill memory rebuild` to restore them from"
                    " the artifacts under runs/; the set-aside file is never deleted.",
                )
            )
    elif isinstance(last_rebuild, dict) and not last_rebuild.get("complete"):
        result["ok"] = False
        result["warnings"].append(
            bilingual(
                "上次重建记忆索引没有做完。跑 `horosa-skill memory rebuild` 接着做。",
                "The last memory index rebuild did not finish. Run `horosa-skill memory rebuild` to complete it.",
            )
        )
    result["last_rebuild"] = last_rebuild
    store._health_cache = (time.monotonic(), result)
    return result
