from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from horosa_skill.config import Settings
from horosa_skill.schemas.common import MemoryRef


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class MemoryStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.ensure_dirs()
        self.db_path = self.settings.db_path
        self.output_dir = self.settings.output_dir
        assert self.db_path is not None
        assert self.output_dir is not None
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    entrypoint TEXT NOT NULL,
                    query_text TEXT,
                    subject_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tool_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    ok INTEGER NOT NULL,
                    input_json TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    warnings_json TEXT NOT NULL,
                    error_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    tool_call_id INTEGER,
                    tool_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id),
                    FOREIGN KEY(tool_call_id) REFERENCES tool_calls(id)
                );

                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_key TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                );
                """
            )
            conn.commit()

    def create_run(self, *, entrypoint: str, query_text: str | None = None, subject: dict[str, Any] | None = None) -> str:
        run_id = uuid.uuid4().hex
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO runs (id, entrypoint, query_text, subject_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, entrypoint, query_text, json.dumps(subject or {}, ensure_ascii=False), now, now),
            )
            conn.commit()
        return run_id

    def record_entities(self, run_id: str, entities: list[dict[str, Any]]) -> None:
        if not entities:
            return
        now = utc_now_iso()
        with self.connect() as conn:
            for entity in entities:
                conn.execute(
                    """
                    INSERT INTO entities (run_id, entity_type, entity_key, display_name, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        entity.get("entity_type", "subject"),
                        entity.get("entity_key", entity.get("display_name", "")),
                        entity.get("display_name", ""),
                        json.dumps(entity.get("metadata", {}), ensure_ascii=False),
                        now,
                    ),
                )
            conn.commit()

    def record_tool_result(
        self,
        *,
        run_id: str,
        tool_name: str,
        ok: bool,
        input_normalized: dict[str, Any],
        envelope_dict: dict[str, Any],
        summary: list[str],
        warnings: list[str],
        error: dict[str, Any] | None,
    ) -> MemoryRef:
        now = utc_now_iso()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tool_calls (run_id, tool_name, ok, input_json, summary_json, warnings_json, error_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    tool_name,
                    1 if ok else 0,
                    json.dumps(input_normalized, ensure_ascii=False),
                    json.dumps(summary, ensure_ascii=False),
                    json.dumps(warnings, ensure_ascii=False),
                    json.dumps(error, ensure_ascii=False) if error else None,
                    now,
                ),
            )
            tool_call_id = int(cursor.lastrowid)
            artifact_path = self._write_artifact(run_id=run_id, tool_name=tool_name, payload=envelope_dict, tool_call_id=tool_call_id)
            artifact_cursor = conn.execute(
                """
                INSERT INTO artifacts (run_id, tool_call_id, tool_name, kind, path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, tool_call_id, tool_name, "tool_result", str(artifact_path), now),
            )
            conn.execute("UPDATE runs SET updated_at = ? WHERE id = ?", (now, run_id))
            conn.commit()
        return MemoryRef(
            run_id=run_id,
            tool_name=tool_name,
            artifact_path=str(artifact_path),
            tool_call_id=tool_call_id,
            artifact_id=int(artifact_cursor.lastrowid),
        )

    def record_dispatch_result(self, *, run_id: str, payload: dict[str, Any]) -> MemoryRef:
        now = utc_now_iso()
        artifact_path = self._write_artifact(run_id=run_id, tool_name="horosa_dispatch", payload=payload, tool_call_id=None)
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO artifacts (run_id, tool_call_id, tool_name, kind, path, created_at)
                VALUES (?, NULL, ?, ?, ?, ?)
                """,
                (run_id, "horosa_dispatch", "dispatch_result", str(artifact_path), now),
            )
            conn.execute("UPDATE runs SET updated_at = ? WHERE id = ?", (now, run_id))
            conn.commit()
        return MemoryRef(
            run_id=run_id,
            tool_name="horosa_dispatch",
            artifact_path=str(artifact_path),
            artifact_id=int(cursor.lastrowid),
        )

    def query_runs(
        self,
        *,
        tool: str | None = None,
        entity: str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int = 20,
        include_payload: bool = True,
    ) -> list[dict[str, Any]]:
        sql = [
            """
            SELECT DISTINCT runs.id, runs.entrypoint, runs.query_text, runs.created_at, runs.updated_at
            FROM runs
            LEFT JOIN tool_calls ON tool_calls.run_id = runs.id
            LEFT JOIN entities ON entities.run_id = runs.id
            WHERE 1=1
            """
        ]
        params: list[Any] = []
        if tool:
            sql.append("AND tool_calls.tool_name = ?")
            params.append(tool)
        if entity:
            sql.append("AND (entities.display_name LIKE ? OR entities.entity_key LIKE ?)")
            params.extend([f"%{entity}%", f"%{entity}%"])
        if after:
            sql.append("AND runs.created_at >= ?")
            params.append(after)
        if before:
            sql.append("AND runs.created_at <= ?")
            params.append(before)
        sql.append("ORDER BY runs.created_at DESC LIMIT ?")
        params.append(limit)

        with self.connect() as conn:
            rows = conn.execute("\n".join(sql), params).fetchall()
            results = []
            for row in rows:
                artifact_sql = """
                    SELECT tool_name, kind, path, created_at
                    FROM artifacts
                    WHERE run_id = ?
                """
                artifact_params: list[Any] = [row["id"]]
                if tool:
                    artifact_sql += " ORDER BY CASE WHEN tool_name = ? THEN 0 ELSE 1 END, id DESC"
                    artifact_params.append(tool)
                else:
                    artifact_sql += " ORDER BY id DESC"
                artifacts = conn.execute(artifact_sql, artifact_params).fetchall()
                tool_calls = conn.execute(
                    """
                    SELECT tool_name, ok, input_json, summary_json, warnings_json, error_json, created_at
                    FROM tool_calls
                    WHERE run_id = ?
                    ORDER BY CASE WHEN tool_name = ? THEN 0 ELSE 1 END, id DESC
                    """,
                    (row["id"], tool or ""),
                ).fetchall()
                results.append(
                    {
                        "run_id": row["id"],
                        "entrypoint": row["entrypoint"],
                        "query_text": row["query_text"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "tool_calls": [self._tool_call_record_to_dict(item) for item in tool_calls],
                        "artifacts": [self._artifact_record_to_dict(artifact, include_payload=include_payload) for artifact in artifacts],
                    }
                )
        return results

    def _write_artifact(self, *, run_id: str, tool_name: str, payload: dict[str, Any], tool_call_id: int | None) -> Path:
        now = datetime.now(timezone.utc)
        target_dir = self.output_dir / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d")
        target_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"{tool_call_id}" if tool_call_id is not None else "dispatch"
        target_path = target_dir / f"{run_id}_{tool_name}_{suffix}.json"
        target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target_path

    def _artifact_record_to_dict(self, artifact: sqlite3.Row, *, include_payload: bool) -> dict[str, Any]:
        record = dict(artifact)
        if include_payload:
            path = Path(record["path"])
            if path.is_file():
                try:
                    record["payload"] = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    record["payload"] = None
        return record

    def _tool_call_record_to_dict(self, tool_call: sqlite3.Row) -> dict[str, Any]:
        record = dict(tool_call)
        for key in ("input_json", "summary_json", "warnings_json", "error_json"):
            value = record.get(key)
            if isinstance(value, str):
                try:
                    record[key.removesuffix("_json")] = json.loads(value)
                except Exception:
                    record[key.removesuffix("_json")] = value
            elif value is None:
                record[key.removesuffix("_json")] = None
            del record[key]
        record["ok"] = bool(record["ok"])
        return record
