from __future__ import annotations

import hashlib
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


def _file_hash_info(path: Path) -> tuple[int, str | None]:
    # 一次读盘同时得 size+sha256；文件缺席/不可读回 (0, None)。
    try:
        data = path.read_bytes()
        return len(data), hashlib.sha256(data).hexdigest()
    except OSError:
        return 0, None


def _safe_file_component(name: str) -> str:
    # 文件名组件白名单（防 tool_name 含路径分隔等异常字符穿到磁盘路径）。
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(name or "")) or "_"


_CORRUPTION_MARKERS = ("malformed", "not a database", "corrupt")


def _is_corruption_error(exc: sqlite3.Error) -> bool:
    """损坏 vs 锁占用的分类（照 codex state_db_recovery 的形状）：
    「database is locked」是并发占用——重试/等待的问题，**绝不能**按损坏走隔离重建（会把好库搬走）；
    只有 malformed / not a database / corrupt 这类 DatabaseError 才判损坏。"""
    text = f"{exc}".lower()
    if "locked" in text:
        return False
    return isinstance(exc, sqlite3.DatabaseError) and any(marker in text for marker in _CORRUPTION_MARKERS)


class MemoryStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.ensure_dirs()
        self.db_path = self.settings.db_path
        self.output_dir = self.settings.output_dir
        assert self.db_path is not None
        assert self.output_dir is not None
        # 损坏自愈痕迹：非 None = 本次启动时把坏库隔离到了该路径（doctor/health 面板据此告知用户）。
        self.corruption_recovery: dict[str, str] | None = None
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        # WAL + busy_timeout：多进程（MCP server / CLI / dispatch 并发）读写不再 `database is locked`；
        # WAL 允许读写并行，NORMAL 同步在 WAL 下掉电最多丢最近事务、不损坏库。
        connection = sqlite3.connect(self.db_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA busy_timeout=30000")
            connection.execute("PRAGMA foreign_keys=ON")
        except sqlite3.Error:
            pass  # 只读介质等极端环境下 PRAGMA 失败不阻塞使用
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        """建库/迁移；损坏库走分类恢复：隔离为 `<db>.corrupt-<ts>.bak`（连 -wal/-shm）后重建空库。

        记忆库是**便利缓存**（完整快照另有 runs/ 磁盘产物），重建的代价是历史检索为空——
        远好于每次调用都因 malformed 崩死。锁占用绝不按损坏处理（_is_corruption_error）。
        """
        try:
            self._initialize_schema()
        except sqlite3.Error as exc:
            if not _is_corruption_error(exc):
                raise
            backup = self._quarantine_corrupt_db(exc)
            self._initialize_schema()
            self.corruption_recovery = {"backup": str(backup), "at": utc_now_iso(), "error": f"{exc}"}

    def _quarantine_corrupt_db(self, exc: sqlite3.Error) -> Path:
        stamp = utc_now_iso().replace(":", "").replace("-", "").replace("+0000", "Z")
        backup = self.db_path.with_name(f"{self.db_path.name}.corrupt-{stamp}.bak")
        import logging

        logger = logging.getLogger(__name__)
        for suffix in ("", "-wal", "-shm"):
            src = Path(f"{self.db_path}{suffix}")
            if src.exists():
                try:
                    src.replace(Path(f"{backup}{suffix}"))
                except OSError as move_exc:  # 移不动（权限/占用）→ 如实上抛原始损坏错误
                    raise exc from move_exc
        logger.warning(
            "记忆库损坏（%s）——已隔离到 %s 并重建空库；历史快照仍在 runs/ 目录，可用 memory 工具重建索引。",
            exc,
            backup,
        )
        return backup

    def integrity_check(self) -> dict[str, Any]:
        """PRAGMA quick_check 探针（doctor 用）：ok=True/False + 前几行诊断 + 损坏自愈痕迹。"""
        try:
            with self.connect() as conn:
                rows = [str(row[0]) for row in conn.execute("PRAGMA quick_check")]
            ok = rows == ["ok"]
        except sqlite3.Error as exc:
            ok, rows = False, [f"{exc}"]
        result: dict[str, Any] = {"ok": ok, "detail": rows[:5]}
        if self.corruption_recovery:
            result["recovered_from_corruption"] = self.corruption_recovery
        return result

    def _initialize_schema(self) -> None:
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
            # 写时落列（消 O(n²)）：sha256/file_size 在写入 artifact 时算一次入库，manifest 刷新与
            # 检索读取不再对每个文件全量 read_bytes 重算（老行列为 NULL → 读取端回退现算）。
            self._ensure_column(conn, "artifacts", "file_size", "INTEGER")
            self._ensure_column(conn, "artifacts", "sha256", "TEXT")
            # 记忆使用度（v0.33.0 批 II-4，照 codex history usage 形状）：按 id 点取（memory_show /
            # 回读）时 +1 并记时刻；召回排序与 prune --unused-days 都吃这两列。老行 NULL=从未点用。
            self._ensure_column(conn, "runs", "usage_count", "INTEGER")
            self._ensure_column(conn, "runs", "last_used_at", "TEXT")
            # 二级索引：按技法/时间/实体/产物类型的组合过滤从全表扫变索引查（IF NOT EXISTS 幂等，老库自动补建）。
            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_runs_group ON runs(group_id);
                CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON tool_calls(run_id);
                CREATE INDEX IF NOT EXISTS idx_tool_calls_tool ON tool_calls(tool_name, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id);
                CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts(kind);
                CREATE INDEX IF NOT EXISTS idx_entities_run ON entities(run_id);
                CREATE INDEX IF NOT EXISTS idx_entities_key ON entities(entity_key);
                """
            )
            self._ensure_fts(conn)
            conn.commit()

    def _ensure_fts(self, conn: sqlite3.Connection) -> None:
        # 全文检索（FTS5 external-content on runs）：query/user_question/ai_answer 三字段入索引，
        # 触发器随写同步；老库首建后做一次 rebuild 回填历史数据。FTS 在 query_runs 里作为加速预筛
        # （命中直接通过；未命中仍走既有 Python 深扫，因文本可能在 tool_calls/artifact 文件里）——
        # 语义只增不减。环境缺 FTS5 编译时静默跳过，检索回退旧路径。
        try:
            existed = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='runs_fts'"
            ).fetchone()
            conn.executescript(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS runs_fts USING fts5(
                    query_text, user_question_text, ai_answer_text,
                    content='runs', content_rowid='rowid',
                    tokenize='trigram'
                );
                CREATE TRIGGER IF NOT EXISTS runs_fts_ai AFTER INSERT ON runs BEGIN
                    INSERT INTO runs_fts(rowid, query_text, user_question_text, ai_answer_text)
                    VALUES (new.rowid, new.query_text, new.user_question_text, new.ai_answer_text);
                END;
                CREATE TRIGGER IF NOT EXISTS runs_fts_ad AFTER DELETE ON runs BEGIN
                    INSERT INTO runs_fts(runs_fts, rowid, query_text, user_question_text, ai_answer_text)
                    VALUES ('delete', old.rowid, old.query_text, old.user_question_text, old.ai_answer_text);
                END;
                CREATE TRIGGER IF NOT EXISTS runs_fts_au AFTER UPDATE ON runs BEGIN
                    INSERT INTO runs_fts(runs_fts, rowid, query_text, user_question_text, ai_answer_text)
                    VALUES ('delete', old.rowid, old.query_text, old.user_question_text, old.ai_answer_text);
                    INSERT INTO runs_fts(rowid, query_text, user_question_text, ai_answer_text)
                    VALUES (new.rowid, new.query_text, new.user_question_text, new.ai_answer_text);
                END;
                """
            )
            if not existed:
                conn.execute("INSERT INTO runs_fts(runs_fts) VALUES('rebuild')")
        except sqlite3.Error:
            pass

    def _fts_run_ids(self, conn: sqlite3.Connection, text: str) -> set[str]:
        # 文本转 FTS 短语（转义引号），返回命中 run id 集；FTS 缺失/查询异常回空集（走深扫）。
        # trigram 分词要求查询 ≥3 码点（中文两字词等短查询直接回落深扫，不发无效查询）。
        needle = (text or "").strip()
        if len(needle) < 3:
            return set()
        try:
            phrase = '"' + needle.replace('"', '""') + '"'
            rows = conn.execute(
                "SELECT runs.id FROM runs_fts JOIN runs ON runs.rowid = runs_fts.rowid WHERE runs_fts MATCH ?",
                (phrase,),
            ).fetchall()
            return {row["id"] for row in rows}
        except sqlite3.Error:
            return set()

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
            artifact_size, artifact_sha = _file_hash_info(artifact_path)
            artifact_cursor = conn.execute(
                """
                INSERT INTO artifacts (run_id, tool_call_id, tool_name, kind, path, created_at, file_size, sha256)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, tool_call_id, tool_name, "tool_result", str(artifact_path), now, artifact_size, artifact_sha),
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
                INSERT INTO artifacts (run_id, tool_call_id, tool_name, kind, path, created_at, file_size, sha256)
                VALUES (?, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, "horosa_dispatch", "dispatch_result", str(artifact_path), now, *_file_hash_info(artifact_path)),
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

    def default_report_path(self, *, run_id: str, tool_name: str, format_name: str) -> Path:
        now = datetime.now(timezone.utc)
        target_dir = self.output_dir / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d")
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_tool = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in tool_name)
        stamp = now.strftime("%Y%m%dT%H%M%SZ")
        return target_dir / f"{run_id}_{safe_tool}_report_{stamp}.{format_name.lower()}"

    def record_report_artifact(
        self,
        *,
        run_id: str,
        tool_name: str,
        format_name: str,
        path: Path,
        trace_id: str | None = None,
        group_id: str | None = None,
    ) -> dict[str, Any]:
        if self._get_run_row(run_id) is None:
            raise ValueError(f"Unknown run_id: {run_id}")
        if not path.is_file():
            raise ValueError(f"Report artifact does not exist: {path}")
        now = utc_now_iso()
        kind = f"report_{format_name.lower()}"
        payload = path.read_bytes()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO artifacts (run_id, tool_call_id, tool_name, kind, path, created_at, file_size, sha256)
                VALUES (?, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, tool_name, kind, str(path), now, *_file_hash_info(path)),
            )
            conn.execute("UPDATE runs SET updated_at = ?, group_id = COALESCE(group_id, ?) WHERE id = ?", (now, group_id, run_id))
            conn.commit()
        manifest = self._refresh_run_manifest(run_id)
        return {
            "ok": True,
            "run_id": run_id,
            "tool_name": tool_name,
            "kind": kind,
            "format": format_name.lower(),
            "artifact_path": str(path),
            "artifact_id": int(cursor.lastrowid),
            "file_size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "created_at": now,
            "trace_id": trace_id,
            "group_id": group_id,
            "manifest_path": manifest["path"],
        }

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
        group_id: str | None = None,
        tool: str | None = None,
        entity: str | None = None,
        text: str | None = None,
        artifact_kind: str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int = 20,
        offset: int = 0,
        include_payload: bool = True,
    ) -> list[dict[str, Any]]:
        sql = [
            """
            SELECT DISTINCT runs.id, runs.entrypoint, runs.query_text, runs.created_at, runs.updated_at
                , runs.subject_json, runs.group_id, runs.user_question_text, runs.ai_answer_text, runs.ai_answer_json, runs.answer_meta_json
                , runs.usage_count, runs.last_used_at
            FROM runs
            LEFT JOIN tool_calls ON tool_calls.run_id = runs.id
            LEFT JOIN entities ON entities.run_id = runs.id
            LEFT JOIN artifacts ON artifacts.run_id = runs.id
            WHERE 1=1
            """
        ]
        params: list[Any] = []
        if run_id:
            sql.append("AND runs.id = ?")
            params.append(run_id)
        # 会话过滤：`runs.group_id` 一直有值也一直有索引（idx_runs_group），只是从来没被当过查询条件——
        # 「这次会话用了哪些技法」需要它。
        if group_id:
            sql.append("AND runs.group_id = ?")
            params.append(group_id)
        if tool:
            sql.append("AND tool_calls.tool_name = ?")
            params.append(tool)
        if entity:
            sql.append("AND (entities.display_name LIKE ? OR entities.entity_key LIKE ?)")
            params.extend([f"%{entity}%", f"%{entity}%"])
        if artifact_kind:
            sql.append("AND artifacts.kind = ?")
            params.append(artifact_kind)
        if after:
            sql.append("AND runs.created_at >= ?")
            params.append(after)
        if before:
            sql.append("AND runs.created_at <= ?")
            params.append(before)
        offset = max(0, offset)
        target_count = max(1, limit) + offset
        candidate_limit = target_count
        if text:
            # Text search also scans artifact file contents, so fetch a wider local candidate window
            # before applying the final in-process filter.
            candidate_limit = max(candidate_limit * 20, 200)
        # rowid 次键：同秒创建的多个 run 顺序确定（分页/翻页稳定）。
        sql.append("ORDER BY runs.created_at DESC, runs.rowid DESC LIMIT ?")
        params.append(candidate_limit)

        with self.connect() as conn:
            rows = conn.execute("\n".join(sql), params).fetchall()
            fts_hits: set[str] = self._fts_run_ids(conn, text) if text else set()
            results = []
            for row in rows:
                artifact_sql = """
                    SELECT tool_name, kind, path, created_at, file_size, sha256
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
                if artifact_kind:
                    artifacts = [artifact for artifact in artifacts if artifact["kind"] == artifact_kind]
                artifact_records = [
                    self._artifact_record_to_dict(artifact, include_payload=include_payload)
                    for artifact in artifacts
                ]
                tool_calls = conn.execute(
                    """
                    SELECT tool_name, ok, input_json, summary_json, warnings_json, error_json, trace_id, group_id, evaluation_case_id, created_at
                    FROM tool_calls
                    WHERE run_id = ?
                    ORDER BY CASE WHEN tool_name = ? THEN 0 ELSE 1 END, id DESC
                    """,
                    (row["id"], tool or ""),
                ).fetchall()
                if text and row["id"] not in fts_hits and not self._run_matches_text(row=row, tool_calls=tool_calls, artifacts=artifact_records, text=text):
                    continue
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
                        "usage_count": row["usage_count"] or 0,
                        "last_used_at": row["last_used_at"],
                        "tool_calls": [self._tool_call_record_to_dict(item) for item in tool_calls],
                        "artifacts": artifact_records,
                        "artifact_summary": self._artifact_summary(artifact_records),
                    }
                )
                if len(results) >= target_count:
                    break
        # 使用度记账（批 II-4）：按 id 点取 = 真被用到（memory_show / 回读），列表浏览不记。
        if run_id and results:
            self.touch_run_usage(run_id)
        # 召回排序（批 II-4）：text 检索命中集内，点用多者优先（次键仍是新近）——常被回读的盘
        # 排到前面；无 text 的浏览列表保持纯新近序（零回归）。
        if text:
            results.sort(key=lambda item: item.get("created_at") or "", reverse=True)
            results.sort(key=lambda item: -(item.get("usage_count") or 0))
        # offset 分页：收集满 offset+limit 后切片（text 深扫语义下 SQL OFFSET 不可用，此处统一处理）。
        return results[offset:]

    def touch_run_usage(self, run_id: str) -> None:
        """点用记账：usage_count+1 + last_used_at=now（召回排序与 prune 的依据）。"""
        with self.connect() as conn:
            conn.execute(
                "UPDATE runs SET usage_count = COALESCE(usage_count, 0) + 1, last_used_at = ? WHERE id = ?",
                (utc_now_iso(), run_id),
            )
            conn.commit()

    @staticmethod
    def is_memory_worthy(record: dict[str, Any]) -> bool:
        """召回语料谓词（批 II-4，双谓词分离）：`should_persist` 恒真（审计契约——所有调用全存，
        本方法**不**影响写入）；本谓词只回答「这条值得进召回语料吗」——有产物、或有 AI 答案、
        或有成功的工具调用，三者其一即值得；三无（失败且零产物）的空 run 不值得。"""
        if record.get("artifacts") or record.get("ai_answer_text"):
            return True
        return any(bool(call.get("ok")) for call in record.get("tool_calls") or [])

    def prune_unused(self, *, unused_days: int, yes: bool = False) -> dict[str, Any]:
        """清理长期未点用的 run（默认 dry-run）：判据 = COALESCE(last_used_at, created_at) 早于
        cutoff **且** usage_count 为空/0。删除级联 tool_calls/artifacts/entities 行 + 磁盘产物文件。
        点用过的 run 永不入选（哪怕很老）——「用过」就是价值证明。"""
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, unused_days))).replace(microsecond=0).isoformat()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, last_used_at, usage_count FROM runs
                WHERE COALESCE(last_used_at, created_at) < ? AND COALESCE(usage_count, 0) = 0
                ORDER BY created_at ASC
                """,
                (cutoff,),
            ).fetchall()
            candidates = [dict(row) for row in rows]
            report: dict[str, Any] = {
                "unused_days": unused_days,
                "cutoff": cutoff,
                "candidates": len(candidates),
                "sample": [row["id"] for row in candidates[:10]],
                "dry_run": not yes,
                "deleted": 0,
                "files_removed": 0,
            }
            if not yes or not candidates:
                return report
            ids = [row["id"] for row in candidates]
            files_removed = 0
            for chunk_start in range(0, len(ids), 400):
                chunk = ids[chunk_start : chunk_start + 400]
                marks = ",".join("?" for _ in chunk)
                for path_row in conn.execute(f"SELECT path FROM artifacts WHERE run_id IN ({marks})", chunk):
                    try:
                        Path(path_row["path"]).unlink(missing_ok=True)
                        files_removed += 1
                    except OSError:
                        pass
                conn.execute(f"DELETE FROM entities WHERE run_id IN ({marks})", chunk)
                conn.execute(f"DELETE FROM artifacts WHERE run_id IN ({marks})", chunk)
                conn.execute(f"DELETE FROM tool_calls WHERE run_id IN ({marks})", chunk)
                conn.execute(f"DELETE FROM runs WHERE id IN ({marks})", chunk)
            conn.commit()
            report["deleted"] = len(ids)
            report["files_removed"] = files_removed
            return report

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
        target_path = target_dir / f"{run_id}_{_safe_file_component(tool_name)}_{suffix}.json"
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
                "SELECT tool_name, kind, path, created_at, file_size, sha256 FROM artifacts WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            ).fetchall()
            entities = conn.execute(
                "SELECT entity_type, entity_key, display_name, metadata_json, created_at FROM entities WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            ).fetchall()
        artifact_records = [
            self._artifact_manifest_record(row)
            for row in artifacts
            if row["kind"] != "run_manifest"
        ]
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
            "artifacts": artifact_records,
            "artifact_summary": self._artifact_summary(artifact_records),
        }

    def _artifact_manifest_record(self, artifact: sqlite3.Row) -> dict[str, Any]:
        record = dict(artifact)
        path = Path(str(record.get("path") or ""))
        exists = path.is_file()
        record["exists"] = exists
        # 优先取写入时落库的 size/sha（消每次 manifest 刷新对全部文件的 O(n²) 重读重算）；
        # 老行列为 NULL 时回退现算一次。
        if not exists:
            record["file_size"] = 0
            record["sha256"] = None
        elif not record.get("sha256"):
            record["file_size"], record["sha256"] = _file_hash_info(path)
        return record

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
        path = Path(record["path"])
        record["exists"] = path.is_file()
        # 优先取落库 size/sha；老行（NULL）回退现算。
        if not record["exists"]:
            record["file_size"] = 0
            record["sha256"] = None
        elif not record.get("sha256"):
            record["file_size"], record["sha256"] = _file_hash_info(path)
        if include_payload:
            if record["exists"]:
                try:
                    record["payload"] = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    record["payload"] = None
        return record

    def _artifact_summary(self, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        counts_by_kind: dict[str, int] = {}
        report_artifacts: list[dict[str, Any]] = []
        for artifact in artifacts:
            kind = str(artifact.get("kind") or "")
            counts_by_kind[kind] = counts_by_kind.get(kind, 0) + 1
            if kind.startswith("report_"):
                report_artifacts.append(
                    {
                        "kind": kind,
                        "tool_name": artifact.get("tool_name"),
                        "path": artifact.get("path"),
                        "exists": artifact.get("exists"),
                        "file_size": artifact.get("file_size"),
                        "sha256": artifact.get("sha256"),
                        "created_at": artifact.get("created_at"),
                    }
                )
        latest_report = report_artifacts[0] if report_artifacts else None
        return {
            "total": len(artifacts),
            "counts_by_kind": counts_by_kind,
            "report_count": len(report_artifacts),
            "report_artifacts": report_artifacts,
            "latest_report": latest_report,
            "has_reports": bool(report_artifacts),
        }

    def _run_matches_text(
        self,
        *,
        row: sqlite3.Row,
        tool_calls: list[sqlite3.Row],
        artifacts: list[dict[str, Any]],
        text: str,
    ) -> bool:
        needle = text.casefold().strip()
        if not needle:
            return True
        values: list[Any] = [
            row["id"],
            row["entrypoint"],
            row["query_text"],
            row["subject_json"],
            row["group_id"],
            row["user_question_text"],
            row["ai_answer_text"],
            row["ai_answer_json"],
            row["answer_meta_json"],
            row["created_at"],
            row["updated_at"],
        ]
        for tool_call in tool_calls:
            values.extend(
                [
                    tool_call["tool_name"],
                    tool_call["input_json"],
                    tool_call["summary_json"],
                    tool_call["warnings_json"],
                    tool_call["error_json"],
                    tool_call["trace_id"],
                    tool_call["group_id"],
                    tool_call["evaluation_case_id"],
                ]
            )
        for artifact in artifacts:
            values.extend([artifact.get("tool_name"), artifact.get("kind"), artifact.get("path"), artifact.get("created_at")])
            payload = artifact.get("payload")
            if payload is not None:
                values.append(json.dumps(payload, ensure_ascii=False, default=str))
            artifact_path = Path(str(artifact.get("path") or ""))
            if artifact_path.is_file() and self._path_contains_text(artifact_path, needle):
                return True
        return any(needle in str(value).casefold() for value in values if value is not None)

    def _path_contains_text(self, path: Path, needle: str) -> bool:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return needle in str(path).casefold()
        return needle in text.casefold()

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
