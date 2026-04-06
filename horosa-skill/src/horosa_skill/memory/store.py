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
                    group_id TEXT,
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
                    trace_id TEXT,
                    group_id TEXT,
                    evaluation_case_id TEXT,
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
            self._ensure_column(conn, "runs", "user_question_text", "TEXT")
            self._ensure_column(conn, "runs", "ai_answer_text", "TEXT")
            self._ensure_column(conn, "runs", "ai_answer_json", "TEXT")
            self._ensure_column(conn, "runs", "answer_meta_json", "TEXT")
            self._ensure_column(conn, "runs", "group_id", "TEXT")
            self._ensure_column(conn, "tool_calls", "trace_id", "TEXT")
            self._ensure_column(conn, "tool_calls", "group_id", "TEXT")
            self._ensure_column(conn, "tool_calls", "evaluation_case_id", "TEXT")
            conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def create_run(
        self,
        *,
        entrypoint: str,
        query_text: str | None = None,
        subject: dict[str, Any] | None = None,
        group_id: str | None = None,
    ) -> str:
        run_id = uuid.uuid4().hex
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    id, entrypoint, query_text, subject_json, group_id, created_at, updated_at,
                    user_question_text, ai_answer_text, ai_answer_json, answer_meta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    entrypoint,
                    query_text,
                    json.dumps(subject or {}, ensure_ascii=False),
                    group_id,
                    now,
                    now,
                    query_text,
                    None,
                    None,
                    json.dumps({}, ensure_ascii=False),
                ),
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
        trace_id: str | None = None,
        group_id: str | None = None,
        evaluation_case_id: str | None = None,
    ) -> MemoryRef:
        now = utc_now_iso()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tool_calls (
                    run_id, tool_name, ok, input_json, summary_json, warnings_json, error_json,
                    trace_id, group_id, evaluation_case_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    tool_name,
                    1 if ok else 0,
                    json.dumps(input_normalized, ensure_ascii=False),
                    json.dumps(summary, ensure_ascii=False),
                    json.dumps(warnings, ensure_ascii=False),
                    json.dumps(error, ensure_ascii=False) if error else None,
                    trace_id,
                    group_id,
                    evaluation_case_id,
                    now,
                ),
            )
            tool_call_id = int(cursor.lastrowid)
            artifact_path = self._write_artifact(
                run_id=run_id,
                tool_name=tool_name,
                payload=envelope_dict,
                tool_call_id=tool_call_id,
                kind="tool_result",
                trace_id=trace_id,
                group_id=group_id,
                evaluation_case_id=evaluation_case_id,
            )
            artifact_cursor = conn.execute(
                """
                INSERT INTO artifacts (run_id, tool_call_id, tool_name, kind, path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, tool_call_id, tool_name, "tool_result", str(artifact_path), now),
            )
            conn.execute("UPDATE runs SET updated_at = ?, group_id = COALESCE(group_id, ?) WHERE id = ?", (now, group_id, run_id))
            conn.commit()
        self._refresh_run_manifest(run_id)
        return MemoryRef(
            run_id=run_id,
            tool_name=tool_name,
            artifact_path=str(artifact_path),
            tool_call_id=tool_call_id,
            artifact_id=int(artifact_cursor.lastrowid),
            trace_id=trace_id,
            group_id=group_id,
        )

    def record_dispatch_result(
        self,
        *,
        run_id: str,
        payload: dict[str, Any],
        trace_id: str | None = None,
        group_id: str | None = None,
    ) -> MemoryRef:
        now = utc_now_iso()
        artifact_path = self._write_artifact(
            run_id=run_id,
            tool_name="horosa_dispatch",
            payload=payload,
            tool_call_id=None,
            kind="dispatch_result",
            trace_id=trace_id,
            group_id=group_id,
            evaluation_case_id=None,
        )
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO artifacts (run_id, tool_call_id, tool_name, kind, path, created_at)
                VALUES (?, NULL, ?, ?, ?, ?)
                """,
                (run_id, "horosa_dispatch", "dispatch_result", str(artifact_path), now),
            )
            conn.execute("UPDATE runs SET updated_at = ?, group_id = COALESCE(group_id, ?) WHERE id = ?", (now, group_id, run_id))
            conn.commit()
        self._refresh_run_manifest(run_id)
        return MemoryRef(
            run_id=run_id,
            tool_name="horosa_dispatch",
            artifact_path=str(artifact_path),
            artifact_id=int(cursor.lastrowid),
            trace_id=trace_id,
            group_id=group_id,
        )

    def attach_ai_response(
        self,
        *,
        run_id: str,
        user_question: str | None = None,
        ai_answer: str,
        ai_answer_structured: dict[str, Any] | list[Any] | None = None,
        answer_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self.connect() as conn:
            row = conn.execute("SELECT id, query_text FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise ValueError(f"Unknown run_id: {run_id}")
            final_user_question = (user_question or row["query_text"] or "").strip() or None
            conn.execute(
                """
                UPDATE runs
                SET user_question_text = ?, ai_answer_text = ?, ai_answer_json = ?, answer_meta_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    final_user_question,
                    ai_answer,
                    json.dumps(ai_answer_structured, ensure_ascii=False) if ai_answer_structured is not None else None,
                    json.dumps(answer_meta or {}, ensure_ascii=False),
                    now,
                    run_id,
                ),
            )
            conn.commit()
        self._refresh_run_artifacts(run_id)
        manifest = self._refresh_run_manifest(run_id)
        return {
            "ok": True,
            "run_id": run_id,
            "user_question": final_user_question,
            "ai_answer": ai_answer,
            "ai_answer_structured": ai_answer_structured,
            "answer_meta": answer_meta or {},
            "manifest_path": manifest["path"],
        }

    def query_runs(
        self,
        *,
        run_id: str | None = None,
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
                , runs.subject_json, runs.group_id, runs.user_question_text, runs.ai_answer_text, runs.ai_answer_json, runs.answer_meta_json
            FROM runs
            LEFT JOIN tool_calls ON tool_calls.run_id = runs.id
            LEFT JOIN entities ON entities.run_id = runs.id
            WHERE 1=1
            """
        ]
        params: list[Any] = []
        if run_id:
            sql.append("AND runs.id = ?")
            params.append(run_id)
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
                    SELECT tool_name, ok, input_json, summary_json, warnings_json, error_json, trace_id, group_id, evaluation_case_id, created_at
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
                        "subject": self._parse_json_field(row["subject_json"]),
                        "group_id": row["group_id"],
                        "user_question": row["user_question_text"] or row["query_text"],
                        "ai_answer_text": row["ai_answer_text"],
                        "ai_answer_structured": self._parse_json_field(row["ai_answer_json"]),
                        "answer_meta": self._parse_json_field(row["answer_meta_json"]) or {},
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "tool_calls": [self._tool_call_record_to_dict(item) for item in tool_calls],
                        "artifacts": [self._artifact_record_to_dict(artifact, include_payload=include_payload) for artifact in artifacts],
                    }
                )
        return results

    def _write_artifact(
        self,
        *,
        run_id: str,
        tool_name: str,
        payload: dict[str, Any],
        tool_call_id: int | None,
        kind: str,
        trace_id: str | None,
        group_id: str | None,
        evaluation_case_id: str | None,
    ) -> Path:
        now = datetime.now(timezone.utc)
        target_dir = self.output_dir / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d")
        target_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"{tool_call_id}" if tool_call_id is not None else "dispatch"
        target_path = target_dir / f"{run_id}_{tool_name}_{suffix}.json"
        artifact_payload = self._build_record_payload(
            run_id=run_id,
            tool_name=tool_name,
            kind=kind,
            payload=payload,
            trace_id=trace_id,
            group_id=group_id,
            evaluation_case_id=evaluation_case_id,
        )
        target_path.write_text(json.dumps(artifact_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target_path

    def _get_run_row(self, run_id: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()

    def _parse_json_field(self, value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value

    def _build_record_payload(
        self,
        *,
        run_id: str,
        tool_name: str,
        kind: str,
        payload: dict[str, Any],
        trace_id: str | None,
        group_id: str | None,
        evaluation_case_id: str | None,
    ) -> dict[str, Any]:
        artifact_payload = dict(payload)
        run = self._get_run_row(run_id)
        subject = self._parse_json_field(run["subject_json"]) if run is not None else {}
        ai_answer_structured = self._parse_json_field(run["ai_answer_json"]) if run is not None else None
        answer_meta = self._parse_json_field(run["answer_meta_json"]) if run is not None else {}
        artifact_payload["record_meta"] = {
            "schema": "horosa.skill.record.v1",
            "kind": kind,
            "run_id": run_id,
            "tool_name": tool_name,
            "entrypoint": run["entrypoint"] if run is not None else None,
            "created_at": run["created_at"] if run is not None else None,
            "updated_at": run["updated_at"] if run is not None else None,
            "trace_id": trace_id,
            "group_id": group_id or (run["group_id"] if run is not None else None),
            "evaluation_case_id": evaluation_case_id,
            "subject": subject or {},
        }
        artifact_payload["conversation"] = {
            "query_text": run["query_text"] if run is not None else None,
            "user_question": (run["user_question_text"] or run["query_text"]) if run is not None else None,
            "ai_answer_text": run["ai_answer_text"] if run is not None else None,
            "ai_answer_structured": ai_answer_structured,
            "answer_meta": answer_meta or {},
        }
        return artifact_payload

    def _refresh_run_artifacts(self, run_id: str) -> None:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT tool_name, kind, path, tool_call_id FROM artifacts WHERE run_id = ? AND kind != 'run_manifest'",
                (run_id,),
            ).fetchall()
        for row in rows:
            path = Path(row["path"])
            if not path.is_file():
                continue
            try:
                raw_payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            base_payload = raw_payload
            if isinstance(raw_payload, dict) and raw_payload.get("record_meta"):
                base_payload = {
                    key: value
                    for key, value in raw_payload.items()
                    if key not in {"record_meta", "conversation"}
                }
            record_meta = raw_payload.get("record_meta", {}) if isinstance(raw_payload, dict) else {}
            updated_payload = self._build_record_payload(
                run_id=run_id,
                tool_name=row["tool_name"],
                kind=row["kind"],
                payload=base_payload if isinstance(base_payload, dict) else {},
                trace_id=record_meta.get("trace_id"),
                group_id=record_meta.get("group_id"),
                evaluation_case_id=record_meta.get("evaluation_case_id"),
            )
            path.write_text(json.dumps(updated_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_run_manifest_payload(self, run_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if run is None:
                raise ValueError(f"Unknown run_id: {run_id}")
            tool_calls = conn.execute(
                """
                SELECT tool_name, ok, input_json, summary_json, warnings_json, error_json, trace_id, group_id, evaluation_case_id, created_at
                FROM tool_calls
                WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
            artifacts = conn.execute(
                "SELECT tool_name, kind, path, created_at FROM artifacts WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            ).fetchall()
            entities = conn.execute(
                "SELECT entity_type, entity_key, display_name, metadata_json, created_at FROM entities WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            ).fetchall()
        return {
            "kind": "horosa.skill.run.manifest",
            "schema_version": 1,
            "run": {
                "id": run["id"],
                "entrypoint": run["entrypoint"],
                "query_text": run["query_text"],
                "subject": self._parse_json_field(run["subject_json"]) or {},
                "group_id": run["group_id"],
                "user_question": run["user_question_text"] or run["query_text"],
                "ai_answer_text": run["ai_answer_text"],
                "ai_answer_structured": self._parse_json_field(run["ai_answer_json"]),
                "answer_meta": self._parse_json_field(run["answer_meta_json"]) or {},
                "created_at": run["created_at"],
                "updated_at": run["updated_at"],
            },
            "entities": [
                {
                    "entity_type": row["entity_type"],
                    "entity_key": row["entity_key"],
                    "display_name": row["display_name"],
                    "metadata": self._parse_json_field(row["metadata_json"]) or {},
                    "created_at": row["created_at"],
                }
                for row in entities
            ],
            "tool_calls": [self._tool_call_record_to_dict(row) for row in tool_calls],
            "artifacts": [dict(row) for row in artifacts if row["kind"] != "run_manifest"],
        }

    def _refresh_run_manifest(self, run_id: str) -> dict[str, Any]:
        manifest_payload = self._build_run_manifest_payload(run_id)
        run_row = self._get_run_row(run_id)
        if run_row is None:
            raise ValueError(f"Unknown run_id: {run_id}")
        created = datetime.fromisoformat(str(run_row["created_at"]).replace("Z", "+00:00")) if run_row["created_at"] else datetime.now(timezone.utc)
        target_dir = self.output_dir / created.strftime("%Y") / created.strftime("%m") / created.strftime("%d")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{run_id}_manifest.json"
        target_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        now = utc_now_iso()
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM artifacts WHERE run_id = ? AND kind = 'run_manifest' ORDER BY id DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO artifacts (run_id, tool_call_id, tool_name, kind, path, created_at)
                    VALUES (?, NULL, ?, ?, ?, ?)
                    """,
                    (run_id, "_run", "run_manifest", str(target_path), now),
                )
            else:
                conn.execute(
                    "UPDATE artifacts SET path = ?, created_at = ? WHERE id = ?",
                    (str(target_path), now, existing["id"]),
                )
            conn.commit()
        return {"path": str(target_path), "payload": manifest_payload}

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
