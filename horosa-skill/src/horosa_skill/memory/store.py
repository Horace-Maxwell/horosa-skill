from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from horosa_skill import fsretry
from horosa_skill.config import Settings
from horosa_skill.memory import search as _search
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


def _write_json_atomic(path: Path, payload: Any) -> tuple[int, str]:
    """把 JSON 写到 `path`，返回 (字节数, sha256)。要么换成完整的新文件，要么原文件一字不动。

    `runs/` 下的产物是一次起盘唯一的完整副本。`write_text` 先截断再写：磁盘写满 / 进程被杀时留下 0 字节，已有内容再也救不回来，
    并发读者还会读到半个文件。这里写同目录临时文件（`os.replace` 同卷才原子）、落盘后再替换。
    用 `os.open` 而不是 mkstemp：后者固定 0600，会改掉产物一直以来按 umask 建的权限；改写时沿用原文件的权限。
    """
    # 不带缩进：没人读这些文件的排版。实测一份星盘产物省 20%（62.9 → 50.4 KB），结构多的引擎 JSON 省得更多（录制件最多 2.48 倍）。
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o666)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            shutil.copymode(path, tmp_path)
        fsretry.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return len(data), hashlib.sha256(data).hexdigest()


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


class UnknownRunError(ValueError):
    """按 id 找不到 run。继承 ValueError：一直 `except ValueError` 的调用方照样接得住。"""

    def __init__(self, run_id: Any) -> None:
        super().__init__(f"Unknown run_id: {run_id}")
        self.run_id = run_id


class EmptyAnswerError(ValueError):
    """写回的答案是空的。空答案曾经把已存的答案整个抹掉；清空不是这条路的功能。"""


# 被替换掉的旧答案留多少条（每个 run）。
ANSWER_HISTORY_LIMIT = 20
# 一次带 text 的查询最多花多久把还没进索引的盘面正文读进来（老库升级后的头几次查询）；`memory rebuild` 不限时。
BODY_BACKFILL_BUDGET_SECONDS = 2.0
# 坏库隔离后自动重建的时间预算：超了就停，剩下的由 `horosa-skill memory rebuild` 接着做。
AUTO_REBUILD_BUDGET_SECONDS = 20.0


class MemoryStore:
    def __init__(self, settings: Settings, *, entity_extractor: Any = None) -> None:
        self.settings = settings
        self.db_path = self.settings.db_path
        self.output_dir = self.settings.output_dir
        assert self.db_path is not None
        assert self.output_dir is not None
        # 损坏自愈痕迹：非 None = 本进程把坏库隔离到了该路径（doctor/health 面板据此告知用户）。
        self.corruption_recovery: dict[str, str] | None = None
        # 存储不可用的原因：非 None = 建库失败。构造绝不因此抛错：算盘不靠记忆库，存档失败由调用方转成 warning。
        self.init_error: str | None = None
        # 检索文档的 trigram 索引是否可用（缺 FTS5 的环境走逐行比对）。
        self._fts_ok = False
        # 存档健康检查的进程内缓存：(时刻, 结果)。查询每次都问，目录扫描不该每次都做。
        self._health_cache: tuple[float, dict[str, Any]] | None = None
        # 重建时从产物的归一化输入抽实体（service 构造时挂上 `service.envelope._extract_entities`；memory 层不导入 service）。
        self.entity_extractor: Any = entity_extractor
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if self.init_error is not None:
            self.initialize()  # 权限恢复 / 锁释放后自愈；还不行就让这次操作自己报错给调用方
        with self._open() as connection:
            yield connection

    @contextmanager
    def _writer(self) -> Iterator[sqlite3.Connection]:
        """写路径的连接。只坏中间页的库构造时看不出来，要到写才报 malformed；这里走与建库期同一条隔离路径，下一次写落在新库上。

        本次写仍然抛错：这份数据没进库，调用方要如实告知。读路径不走这里：为一次查询失败搬走整个库不值得。"""
        try:
            with self.connect() as connection:
                yield connection
        except sqlite3.DatabaseError as exc:
            if _is_corruption_error(exc):
                self._recover_from_write_corruption(exc)
            raise

    def _recover_from_write_corruption(self, exc: sqlite3.Error) -> None:
        # 只凭报错文字不够：别的进程刚把库隔离走时这里也可能撞上同样的话。亲自确认**当前这份库**真坏了才动它。
        if self._database_is_sound():
            return
        try:
            backup = self._quarantine_corrupt_db(exc)
            self._initialize_schema()
        except (sqlite3.Error, OSError) as failure:
            self._note_init_failure(failure)
            return
        self.init_error = None
        self.corruption_recovery = {"backup": str(backup), "at": utc_now_iso(), "error": f"{exc}"}
        self._after_quarantine(backup)

    def _after_quarantine(self, backup: Path) -> None:
        """坏库隔离后，马上照 `runs/` 里的产物把索引找回来。绝不抛错：找不回来，新库照样能用，只是旧记录暂时搜不到。"""
        from horosa_skill.memory.rebuild import rebuild_from_artifacts

        self._health_cache = None
        try:
            self.set_meta("quarantine", {"backup": str(backup), "at": utc_now_iso()})
            report = rebuild_from_artifacts(self, budget_seconds=AUTO_REBUILD_BUDGET_SECONDS, index_bodies=False)
        except (sqlite3.Error, OSError, ValueError) as failure:
            report = {"ok": False, "complete": False, "error": f"{type(failure).__name__}: {failure}"}
        if self.corruption_recovery is not None:
            self.corruption_recovery["rebuild"] = {
                key: report.get(key) for key in ("ok", "complete", "restored_runs", "unreadable_count", "error") if key in report
            }
        logging.getLogger(__name__).log(
            logging.WARNING,
            "记忆库已按 runs/ 里的产物重建索引：找回 %s 条记录%s。隔离文件 %s 不会被自动删除。",
            (report.get("restored_runs") or {}).get("total", 0) if isinstance(report.get("restored_runs"), dict) else 0,
            "" if report.get("complete") else "（没做完，跑 `horosa-skill memory rebuild` 接着做）",
            backup,
        )


    def _database_is_sound(self) -> bool:
        """当前库是否完好。用 integrity_check 而不是 quick_check：后者不比对索引与表内容，那类损坏同样报 malformed。"""
        try:
            with self._open() as conn:
                return [str(row[0]) for row in conn.execute("PRAGMA integrity_check(1)")] == ["ok"]
        except sqlite3.Error as exc:
            return not _is_corruption_error(exc)  # 锁占用等：没有证据说它坏了

    def _note_init_failure(self, exc: Exception) -> None:
        message = f"{type(exc).__name__}: {exc}"
        if message != self.init_error:  # 每次操作都会重试，同一个原因只说一遍
            # 建库期通知，没有工具调用可告知——不是降级点（verify_silent_degrades 只盯 logger.warning）。
            logging.getLogger(__name__).log(logging.WARNING, "记忆库不可用（%s）：%s；存档会失败，计算不受影响。", self.db_path, exc)
        self.init_error = message

    @contextmanager
    def _reader(self) -> Iterator[sqlite3.Connection]:
        """读路径的连接。数据目录只读时 WAL 库连读都读不了（要建 -shm）：退到只读、不可变的方式打开，查询照常。"""
        readonly = False
        try:
            with self.connect() as probe:
                probe.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
        except sqlite3.OperationalError as exc:
            text = f"{exc}".lower()
            if ("readonly" not in text and "unable to open" not in text) or not self.db_path.is_file():
                raise
            readonly = True
        if not readonly:
            with self.connect() as connection:
                yield connection
            return
        connection = sqlite3.connect(f"{self.db_path.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _open(self) -> Iterator[sqlite3.Connection]:
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

        记忆库是**便利缓存**（完整快照另有 runs/ 磁盘产物），重建的代价是旧记录不再出现在检索里——
        远好于每次调用都因 malformed 崩死。锁占用绝不按损坏处理（_is_corruption_error）。
        建不起来（只读、路径不可用）只记 `init_error`，不抛：计算不靠记忆库，下一次操作时再试。
        """
        quarantined: Path | None = None
        try:
            self.settings.ensure_dirs()
        except OSError as exc:
            # 建不出来的可能只是 runtime 根或 trace 目录，与记忆库无关：是否影响存档由下面的建库说了算。
            logging.getLogger(__name__).debug("ensure_dirs failed: %s", exc)
        try:
            try:
                self._initialize_schema()
            except sqlite3.Error as exc:
                # 只凭报错文字不够（别的进程刚把库隔离走时也会撞上同样的话）：亲自确认这份库真坏了才动它。
                if not _is_corruption_error(exc) or self._database_is_sound():
                    raise
                quarantined = self._quarantine_corrupt_db(exc)
                self._initialize_schema()
                self.corruption_recovery = {"backup": str(quarantined), "at": utc_now_iso(), "error": f"{exc}"}
        except (sqlite3.Error, OSError) as exc:
            self._note_init_failure(exc)
        else:
            self.init_error = None
            if quarantined is not None:
                self._after_quarantine(quarantined)

    def _quarantine_corrupt_db(self, exc: sqlite3.Error) -> Path:
        stamp = utc_now_iso().replace(":", "").replace("-", "").replace("+0000", "Z")
        backup = self.db_path.with_name(f"{self.db_path.name}.corrupt-{stamp}.bak")
        logger = logging.getLogger(__name__)
        for suffix in ("", "-wal", "-shm"):
            src = Path(f"{self.db_path}{suffix}")
            if src.exists():
                try:
                    src.replace(Path(f"{backup}{suffix}"))
                except OSError as move_exc:  # 移不动（权限/占用）→ 如实上抛原始损坏错误
                    raise exc from move_exc
        # 建库期通知，没有工具调用可告知——不是降级点（verify_silent_degrades 只盯 logger.warning）。
        logger.log(
            logging.WARNING,
            "记忆库损坏（%s）——已隔离到 %s 并重建空库。旧记录的产物文件还在 runs/ 目录，接下来照这些文件自动重建索引；"
            "没找回的可以再跑 `horosa-skill memory rebuild`。",
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
        result: dict[str, Any] = {"ok": ok and self.init_error is None, "detail": rows[:5]}
        if self.init_error:
            result["init_error"] = self.init_error
        if self.corruption_recovery:
            result["recovered_from_corruption"] = self.corruption_recovery
        return result

    def _initialize_schema(self) -> None:
        with self._open() as conn:
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
            # 被替换掉的旧答案（写回第二次答案不再覆盖第一次）；实体的匹配键（繁简折叠 + 日期写法统一）。
            self._ensure_column(conn, "runs", "answer_history_json", "TEXT")
            self._ensure_column(conn, "entities", "search_key", "TEXT")
            # 检索文档：每个 run 一行（head = 库里的字，body = 产物里的盘面正文）。state 0 = 正文还没从产物文件读进来；
            # stamp = 建 head 时的 runs.updated_at，对不上就是过期（旧版本进程或绕过 store 写的行），查询前自动补。
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS run_search (
                    id INTEGER PRIMARY KEY,
                    run_id TEXT NOT NULL UNIQUE,
                    head TEXT NOT NULL DEFAULT '',
                    body TEXT NOT NULL DEFAULT '',
                    state INTEGER NOT NULL DEFAULT 0,
                    stamp TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_run_search_pending ON run_search(id) WHERE state = 0;
                CREATE INDEX IF NOT EXISTS idx_entities_unkeyed ON entities(id) WHERE search_key IS NULL;
                CREATE TRIGGER IF NOT EXISTS run_search_run_deleted AFTER DELETE ON runs BEGIN
                    DELETE FROM run_search WHERE run_id = old.id;
                END;
                """
            )
            self._ensure_fts(conn)
            conn.commit()
            self._sync_search(conn)

    def _ensure_fts(self, conn: sqlite3.Connection) -> None:
        """检索文档的 trigram 索引。`detail=none` 不存位置表：2000 份八字正文实测整库 23 MB（带位置表 47 MB），
        三个字以上的词用 GLOB 走索引（1 ms）；缺 FTS5 的环境 `_fts_ok=False`，检索退回逐行比对，结果一样、只是慢。

        老库的 `runs_fts` 只索引问题与答案三列、不折叠繁简，已被 `run_search` 取代——连同三个触发器一起撤掉。"""
        try:
            existed = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='run_search_fts'").fetchone()
            conn.executescript(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS run_search_fts USING fts5(
                    head, body, content='run_search', content_rowid='id', tokenize='trigram', detail=none
                );
                CREATE TRIGGER IF NOT EXISTS run_search_ai AFTER INSERT ON run_search BEGIN
                    INSERT INTO run_search_fts(rowid, head, body) VALUES (new.id, new.head, new.body);
                END;
                CREATE TRIGGER IF NOT EXISTS run_search_ad AFTER DELETE ON run_search BEGIN
                    INSERT INTO run_search_fts(run_search_fts, rowid, head, body) VALUES ('delete', old.id, old.head, old.body);
                END;
                CREATE TRIGGER IF NOT EXISTS run_search_au AFTER UPDATE OF head, body ON run_search BEGIN
                    INSERT INTO run_search_fts(run_search_fts, rowid, head, body) VALUES ('delete', old.id, old.head, old.body);
                    INSERT INTO run_search_fts(rowid, head, body) VALUES (new.id, new.head, new.body);
                END;
                """
            )
            if not existed and conn.execute("SELECT 1 FROM run_search LIMIT 1").fetchone():
                conn.execute("INSERT INTO run_search_fts(run_search_fts) VALUES('rebuild')")
            self._fts_ok = True
        except sqlite3.Error:
            self._fts_ok = False
        try:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'runs_fts'").fetchone():
                conn.executescript(
                    """
                    DROP TRIGGER IF EXISTS runs_fts_ai;
                    DROP TRIGGER IF EXISTS runs_fts_ad;
                    DROP TRIGGER IF EXISTS runs_fts_au;
                    DROP TABLE IF EXISTS runs_fts;
                    """
                )
        except sqlite3.Error:
            pass  # 撤不掉（别的进程正用着）：留着无害，下次再撤

    # ---- 检索文档 ----

    def _write_search_doc(
        self, conn: sqlite3.Connection, run_id: str, *, texts: Any = (), pending: bool | None = None
    ) -> None:
        """重算一个 run 的 head，并把 `texts`（盘面正文）并进 body。在调用方的事务里跑：run 行与它的检索文档一起提交。

        `pending`：True = 正文要从产物文件重读（state 0）；False = 刚建的 run，没有产物可读；None = 沿用原状（没有文档行时按 0）。"""
        run = conn.execute(
            "SELECT query_text, user_question_text, ai_answer_text, ai_answer_json, answer_history_json, updated_at FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if run is None:
            return
        calls = conn.execute("SELECT tool_name, summary_json FROM tool_calls WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
        entities = conn.execute("SELECT display_name, entity_key FROM entities WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
        history = self._parse_json_field(run["answer_history_json"])
        head = _search.build_head(
            query_text=run["query_text"],
            user_question=run["user_question_text"],
            ai_answer=run["ai_answer_text"],
            answer_structured=self._parse_json_field(run["ai_answer_json"]),
            previous_answers=[item.get("ai_answer_text") for item in history if isinstance(item, dict)] if isinstance(history, list) else (),
            tool_names=[call["tool_name"] for call in calls],
            entities=[(entity["display_name"], entity["entity_key"]) for entity in entities],
            summaries=_search.summary_lines(call["summary_json"] for call in calls),
        )
        doc = conn.execute("SELECT id, head, body, state FROM run_search WHERE run_id = ?", (run_id,)).fetchone()
        if doc is None:
            conn.execute(
                "INSERT INTO run_search (run_id, head, body, state, stamp) VALUES (?, ?, ?, ?, ?)",
                (run_id, head, _search.merge_body("", texts), _search.SEARCH_DOC_VERSION if pending is False else 0, run["updated_at"]),
            )
            return
        body = _search.merge_body(doc["body"], texts)
        state = 0 if pending else doc["state"]
        if head != doc["head"] or body != doc["body"]:
            conn.execute(
                "UPDATE run_search SET head = ?, body = ?, state = ?, stamp = ? WHERE id = ?",
                (head, body, state, run["updated_at"], doc["id"]),
            )
        else:  # 字没变：只动 state / stamp，不触发索引重写
            conn.execute("UPDATE run_search SET state = ?, stamp = ? WHERE id = ?", (state, run["updated_at"], doc["id"]))

    def _sync_search(self, conn: sqlite3.Connection) -> int:
        """给没有检索文档、或文档过期的 run 补 head，给没有匹配键的实体补键。返回补了多少个 run。

        老库升级走这里（一次性，万条约几秒，分批提交不长占写锁）；平时是一条查不出行的 SELECT。"""
        fixed = 0
        while True:
            stale = conn.execute(
                """
                SELECT runs.id FROM runs LEFT JOIN run_search s ON s.run_id = runs.id
                WHERE s.run_id IS NULL OR s.stamp IS NOT runs.updated_at
                ORDER BY runs.rowid LIMIT 500
                """
            ).fetchall()
            unkeyed = conn.execute(
                "SELECT id, display_name, entity_key FROM entities WHERE search_key IS NULL ORDER BY id LIMIT 2000"
            ).fetchall()
            if not stale and not unkeyed:
                return fixed
            conn.execute("BEGIN IMMEDIATE")
            try:
                for row in unkeyed:
                    conn.execute(
                        "UPDATE entities SET search_key = ? WHERE id = ?",
                        (_search.entity_search_key(row["display_name"], row["entity_key"]), row["id"]),
                    )
                for row in stale:
                    self._write_search_doc(conn, row["id"], pending=True)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            fixed += len(stale)

    def index_pending_bodies(self, *, budget_seconds: float | None) -> dict[str, int]:
        """把还没进索引的盘面正文从产物文件读进检索文档，新的先读。读文件不便宜，所以有时间预算；None = 读完为止。

        返回 `{"indexed": 这次读了几个 run, "pending": 还剩几个}`。"""
        deadline = None if budget_seconds is None else time.monotonic() + budget_seconds
        indexed = 0
        with self.connect() as conn:
            while True:
                rows = conn.execute("SELECT id, run_id FROM run_search WHERE state = 0 ORDER BY id DESC LIMIT 50").fetchall()
                if not rows:
                    break
                batch: list[tuple[int, list[str]]] = []
                for row in rows:
                    paths = conn.execute(
                        "SELECT path FROM artifacts WHERE run_id = ? AND kind IN ('tool_result', 'dispatch_result') ORDER BY id",
                        (row["run_id"],),
                    ).fetchall()
                    texts: list[str] = []
                    for item in paths:
                        texts.extend(_search.export_texts_from_file(Path(item["path"])))
                    batch.append((row["id"], texts))
                    if deadline is not None and time.monotonic() > deadline:
                        break
                conn.execute("BEGIN IMMEDIATE")
                try:
                    for doc_id, texts in batch:
                        current = conn.execute("SELECT body FROM run_search WHERE id = ?", (doc_id,)).fetchone()
                        if current is None:
                            continue
                        # 文件里读到的在前，库里已有而文件里没有的（别的进程刚并进来的）接在后面：只增不丢。
                        body = _search.merge_body(
                            _search.merge_body("", texts), _search.body_parts(current["body"]), normalized=True
                        )
                        if body != current["body"]:
                            conn.execute(
                                "UPDATE run_search SET body = ?, state = ? WHERE id = ?", (body, _search.SEARCH_DOC_VERSION, doc_id)
                            )
                        else:
                            conn.execute("UPDATE run_search SET state = ? WHERE id = ?", (_search.SEARCH_DOC_VERSION, doc_id))
                    conn.commit()
                except BaseException:
                    conn.rollback()
                    raise
                indexed += len(batch)
                if deadline is not None and time.monotonic() > deadline:
                    break
            pending = int(conn.execute("SELECT COUNT(*) FROM run_search WHERE state = 0").fetchone()[0])
        return {"indexed": indexed, "pending": pending}

    # ---- 库级备忘（隔离 / 重建的痕迹，跨进程可见） ----

    def get_meta(self, key: str) -> Any:
        try:
            with self._reader() as conn:
                row = conn.execute("SELECT value FROM store_meta WHERE key = ?", (key,)).fetchone()
        except sqlite3.Error:
            return None
        return self._parse_json_field(row["value"]) if row is not None else None

    def set_meta(self, key: str, value: Any) -> None:
        with self._writer() as conn:
            conn.execute(
                "INSERT INTO store_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value, ensure_ascii=False)),
            )
            conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError as exc:
                # 并发初始化：两个进程（两个客户端同时起 stdio server、agent 并行跑 `tool run`）都看到列缺失，
                # 后到的 ALTER 撞「duplicate column name」——列已由对方加上，迁移目标已达成。2026-10 表面审计在全新
                # 数据目录上 6 路并行 `tool run` 复现过（exit 1，OperationalError 直接冒到 CLI）。
                if "duplicate column name" not in f"{exc}".lower():
                    raise

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
        with self._writer() as conn:
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
            self._write_search_doc(conn, run_id, pending=False)
            conn.commit()
        return run_id

    def record_entities(self, run_id: str, entities: list[dict[str, Any]]) -> None:
        if not entities:
            return
        now = utc_now_iso()
        with self._writer() as conn:
            for entity in entities:
                entity_key = entity.get("entity_key", entity.get("display_name", ""))
                display_name = entity.get("display_name", "")
                conn.execute(
                    """
                    INSERT INTO entities (run_id, entity_type, entity_key, display_name, metadata_json, created_at, search_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        entity.get("entity_type", "subject"),
                        entity_key,
                        display_name,
                        json.dumps(entity.get("metadata", {}), ensure_ascii=False),
                        now,
                        _search.entity_search_key(display_name, entity_key),
                    ),
                )
            self._write_search_doc(conn, run_id)
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
        with self._writer() as conn:
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
            self._write_search_doc(conn, run_id, texts=_search.export_texts(envelope_dict))
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
        return self.record_facade_result(
            run_id=run_id, payload=payload, tool_name="horosa_dispatch", kind="dispatch_result", trace_id=trace_id, group_id=group_id,
        )

    def record_facade_result(
        self,
        *,
        run_id: str,
        payload: dict[str, Any],
        tool_name: str,
        kind: str,
        trace_id: str | None = None,
        group_id: str | None = None,
    ) -> MemoryRef:
        """门面的整份结果（dispatch_result / hecan_result）作为该 run 的一份产物。"""
        now = utc_now_iso()
        artifact_path = self._write_artifact(
            run_id=run_id,
            tool_name=tool_name,
            payload=payload,
            tool_call_id=None,
            kind=kind,
            trace_id=trace_id,
            group_id=group_id,
            evaluation_case_id=None,
        )
        with self._writer() as conn:
            cursor = conn.execute(
                """
                INSERT INTO artifacts (run_id, tool_call_id, tool_name, kind, path, created_at, file_size, sha256)
                VALUES (?, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, tool_name, kind, str(artifact_path), now, *_file_hash_info(artifact_path)),
            )
            conn.execute("UPDATE runs SET updated_at = ?, group_id = COALESCE(group_id, ?) WHERE id = ?", (now, group_id, run_id))
            self._write_search_doc(conn, run_id, texts=_search.export_texts(payload))
            conn.commit()
        self._refresh_run_manifest(run_id)
        return MemoryRef(
            run_id=run_id,
            tool_name=tool_name,
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
            raise UnknownRunError(run_id)
        if not path.is_file():
            raise ValueError(f"Report artifact does not exist: {path}")
        now = utc_now_iso()
        kind = f"report_{format_name.lower()}"
        payload = path.read_bytes()
        with self._writer() as conn:
            cursor = conn.execute(
                """
                INSERT INTO artifacts (run_id, tool_call_id, tool_name, kind, path, created_at, file_size, sha256)
                VALUES (?, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, tool_name, kind, str(path), now, *_file_hash_info(path)),
            )
            conn.execute("UPDATE runs SET updated_at = ?, group_id = COALESCE(group_id, ?) WHERE id = ?", (now, group_id, run_id))
            self._write_search_doc(conn, run_id)
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
        """写回一条答案。空答案拒收（`EmptyAnswerError`）；不带 `user_question` 时已存的问题原样保留；
        已有的答案若与新答案不同，连同它的结构化内容与元数据移进 `answer_history`（最多留 `ANSWER_HISTORY_LIMIT` 条）。"""
        if not isinstance(ai_answer, str) or not ai_answer.strip():
            raise EmptyAnswerError("ai_answer is empty")
        now = utc_now_iso()
        with self._writer() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT id, query_text, user_question_text, ai_answer_text, ai_answer_json, answer_meta_json, answer_history_json
                FROM runs WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                raise UnknownRunError(run_id)
            final_user_question = (
                (user_question or "").strip() or (row["user_question_text"] or "").strip() or (row["query_text"] or "").strip()
            ) or None
            history = self._parse_json_field(row["answer_history_json"])
            history = [item for item in history if isinstance(item, dict)] if isinstance(history, list) else []
            previous = row["ai_answer_text"]
            replaced = bool(previous and previous.strip()) and previous != ai_answer
            if replaced:
                history.append(
                    {
                        "ai_answer_text": previous,
                        "ai_answer_structured": self._parse_json_field(row["ai_answer_json"]),
                        "answer_meta": self._parse_json_field(row["answer_meta_json"]) or {},
                        "user_question": row["user_question_text"] or row["query_text"],
                        "replaced_at": now,
                    }
                )
                history = history[-ANSWER_HISTORY_LIMIT:]
            conn.execute(
                """
                UPDATE runs
                SET user_question_text = ?, ai_answer_text = ?, ai_answer_json = ?, answer_meta_json = ?, updated_at = ?,
                    usage_count = COALESCE(usage_count, 0) + 1, last_used_at = ?, answer_history_json = ?
                WHERE id = ?
                """,
                (
                    final_user_question,
                    ai_answer,
                    json.dumps(ai_answer_structured, ensure_ascii=False) if ai_answer_structured is not None else None,
                    json.dumps(answer_meta or {}, ensure_ascii=False),
                    now,
                    now,  # 写回解读就是用过：答过的 run 不该被 prune 选中
                    json.dumps(history, ensure_ascii=False) if history else None,
                    run_id,
                ),
            )
            self._write_search_doc(conn, run_id)
            conn.commit()
        updated, skipped = self._refresh_run_artifacts(run_id)
        manifest = self._refresh_run_manifest(run_id)
        return {
            "ok": True,
            "run_id": run_id,
            "user_question": final_user_question,
            "ai_answer_text": ai_answer,
            "ai_answer": ai_answer,  # 旧字段名，再留一个版本；读取面一直叫 ai_answer_text
            "ai_answer_structured": ai_answer_structured,
            "answer_meta": answer_meta or {},
            "replaced_previous": replaced,
            "previous_answers": len(history),
            "artifacts_updated": updated,
            "artifacts_skipped": skipped,
            "manifest_path": manifest["path"],
        }

    @staticmethod
    def _instant_bound(value: Any) -> Any:
        """带偏移的 ISO 时间 → 与 `created_at` 同形的 UTC 串（按时刻比，不按字面比）；别的原样交给 SQL。"""
        if isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except ValueError:
                return value
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        return value

    def _run_filters(
        self,
        *,
        run_id: str | None,
        group_id: str | None,
        tool: str | list[str] | None,
        entity: str | list[str] | None,
        artifact_kind: str | None,
        after: str | None,
        before: str | None,
    ) -> tuple[list[str], list[Any]]:
        sql: list[str] = []
        params: list[Any] = []
        if run_id:
            sql.append("AND runs.id = ?")
            params.append(run_id)
        if group_id:
            sql.append("AND runs.group_id = ?")
            params.append(group_id)
        tools = [tool] if isinstance(tool, str) else list(tool or [])
        tools = [name for name in tools if name]
        if tools:
            marks = ",".join("?" for _ in tools)
            sql.append(f"AND EXISTS (SELECT 1 FROM tool_calls t WHERE t.run_id = runs.id AND t.tool_name IN ({marks}))")
            params.extend(tools)
        # 实体：给几个叫法（档案的名字与别名）就是「任一命中」；比的是归一后的匹配键，`%` `_` 只是普通字符。
        needles = [entity] if isinstance(entity, str) else list(entity or [])
        needles = list(dict.fromkeys(key for key in (_search.entity_search_key(item) for item in needles) if key))
        if needles:
            match = " OR ".join(
                "instr(COALESCE(e.search_key, lower(e.display_name) || char(10) || lower(e.entity_key)), ?) > 0" for _ in needles
            )
            sql.append(f"AND EXISTS (SELECT 1 FROM entities e WHERE e.run_id = runs.id AND ({match}))")
            params.extend(needles)
        if artifact_kind:
            sql.append("AND EXISTS (SELECT 1 FROM artifacts a WHERE a.run_id = runs.id AND a.kind = ?)")
            params.append(artifact_kind)
        if after:
            sql.append("AND runs.created_at >= ?")
            params.append(self._instant_bound(after))
        if before:
            sql.append("AND runs.created_at <= ?")
            params.append(self._instant_bound(before))
        return sql, params

    def _text_filters(self, terms: list[str]) -> tuple[list[str], list[Any]]:
        """每个词一个条件，词与词是 AND。三字以上且没有 GLOB 元字符的走 trigram 索引，其余逐行比。"""
        sql: list[str] = []
        params: list[Any] = []
        for term in terms:
            if self._fts_ok and len(term) >= _search.TRIGRAM_MIN and not any(ch in term for ch in "*?[]"):
                sql.append(
                    "AND runs.id IN (SELECT run_id FROM run_search WHERE id IN ("
                    "SELECT rowid FROM run_search_fts WHERE head GLOB ? UNION SELECT rowid FROM run_search_fts WHERE body GLOB ?))"
                )
                params.extend([f"*{term}*", f"*{term}*"])
            else:
                sql.append(
                    "AND EXISTS (SELECT 1 FROM run_search s WHERE s.run_id = runs.id AND (instr(s.head, ?) > 0 OR instr(s.body, ?) > 0))"
                )
                params.extend([term, term])
        return sql, params

    def query_runs(
        self,
        *,
        run_id: str | None = None,
        group_id: str | None = None,
        tool: str | list[str] | None = None,
        entity: str | list[str] | None = None,
        text: str | None = None,
        artifact_kind: str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int = 20,
        offset: int = 0,
        include_payload: bool = True,
        include_history: bool = False,
        scan_report: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """按条件取 run，新的在前（`created_at`、同秒按写入顺序），顺序只由这两样定：翻页不重不漏。

        `text` 搜的是每个 run 的检索文档（问题、答案、技法名、实体、摘要、盘面正文），空白分开的词要全中；
        路径、id、时间戳、JSON 键名不在文档里。老库升级后正文要从产物文件读进索引，一次查询只读一小会儿：
        `scan_report["not_scanned"]` 是符合其余条件、正文还没读进来的 run 数（它们的问题与答案已经可搜）。"""
        filters, params = self._run_filters(
            run_id=run_id, group_id=group_id, tool=tool, entity=entity, artifact_kind=artifact_kind, after=after, before=before
        )
        terms = _search.query_terms(text)
        if scan_report is not None:
            scan_report["not_scanned"] = 0
        if terms:
            pending = self._prepare_text_search()
            if scan_report is not None and pending:
                with self._reader() as conn:
                    scan_report["not_scanned"] = int(
                        conn.execute(
                            "\n".join(
                                [
                                    "SELECT COUNT(*) FROM runs WHERE 1=1",
                                    *filters,
                                    "AND EXISTS (SELECT 1 FROM run_search s WHERE s.run_id = runs.id AND s.state = 0)",
                                ]
                            ),
                            params,
                        ).fetchone()[0]
                    )
        text_filters, text_params = self._text_filters(terms)
        preferred = [tool] if isinstance(tool, str) else list(tool or [])
        results: list[dict[str, Any]] = []
        with self._reader() as conn:
            rows = conn.execute(
                "\n".join(
                    [
                        "SELECT runs.* FROM runs WHERE 1=1",
                        *filters,
                        *text_filters,
                        "ORDER BY runs.created_at DESC, runs.rowid DESC LIMIT ? OFFSET ?",
                    ]
                ),
                [*params, *text_params, max(1, limit), max(0, offset)],
            ).fetchall()
            for row in rows:
                artifacts = conn.execute(
                    "SELECT tool_name, kind, path, created_at, file_size, sha256 FROM artifacts WHERE run_id = ? ORDER BY id DESC",
                    (row["id"],),
                ).fetchall()
                tool_calls = conn.execute(
                    """
                    SELECT tool_name, ok, input_json, summary_json, warnings_json, error_json, trace_id, group_id, evaluation_case_id, created_at
                    FROM tool_calls WHERE run_id = ? ORDER BY id DESC
                    """,
                    (row["id"],),
                ).fetchall()
                if preferred:  # 被问到的技法排在前面（稳定排序，其余保持新到旧）
                    artifacts = sorted(artifacts, key=lambda item: item["tool_name"] not in preferred)
                    tool_calls = sorted(tool_calls, key=lambda item: item["tool_name"] not in preferred)
                if artifact_kind:
                    artifacts = [artifact for artifact in artifacts if artifact["kind"] == artifact_kind]
                artifact_records = [self._artifact_record_to_dict(artifact, include_payload=include_payload) for artifact in artifacts]
                history = self._parse_json_field(row["answer_history_json"])
                history = history if isinstance(history, list) else []
                record = {
                    "run_id": row["id"],
                    "entrypoint": row["entrypoint"],
                    "query_text": row["query_text"],
                    "subject": self._parse_json_field(row["subject_json"]),
                    "group_id": row["group_id"],
                    "user_question": row["user_question_text"] or row["query_text"],
                    "ai_answer_text": row["ai_answer_text"],
                    "ai_answer_structured": self._parse_json_field(row["ai_answer_json"]),
                    "answer_meta": self._parse_json_field(row["answer_meta_json"]) or {},
                    "previous_answers": len(history),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "usage_count": row["usage_count"] or 0,
                    "last_used_at": row["last_used_at"],
                    "tool_calls": [self._tool_call_record_to_dict(item) for item in tool_calls],
                    "artifacts": artifact_records,
                    "artifact_summary": self._artifact_summary(artifact_records),
                }
                if include_history:
                    record["answer_history"] = history
                results.append(record)
        # 使用度记账：按 id 点取 = 真被用到（memory_show / 回读），列表浏览不记。记不上（只读介质）不妨碍读。
        if run_id and results:
            try:
                self.touch_run_usage(run_id)
            except (sqlite3.Error, OSError):
                pass
        return results

    def _prepare_text_search(self) -> int:
        """带 text 的查询之前：补齐过期的 head，再在时间预算内把待读的正文读进索引。返回还没读进来的 run 数。

        库写不了（只读介质）就按现有的索引搜：能搜到多少算多少，不让查询因此失败。"""
        try:
            with self.connect() as conn:
                self._sync_search(conn)
                if not conn.execute("SELECT 1 FROM run_search WHERE state = 0 LIMIT 1").fetchone():
                    return 0
            return self.index_pending_bodies(budget_seconds=BODY_BACKFILL_BUDGET_SECONDS)["pending"]
        except (sqlite3.Error, OSError):
            try:
                with self.connect() as conn:
                    return int(conn.execute("SELECT COUNT(*) FROM run_search WHERE state = 0").fetchone()[0])
            except sqlite3.Error:
                return 0

    def touch_run_usage(self, run_id: str) -> None:
        """点用记账：usage_count+1 + last_used_at=now（召回排序与 prune 的依据）。"""
        with self._writer() as conn:
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
        cutoff **且** usage_count 为空/0 **且**没有写回过答案。删除级联 tool_calls/artifacts/entities 行 + 磁盘产物文件。
        点用过的 run 永不入选（哪怕很老）——「用过」就是价值证明；写回答案现在算点用，判答案列是给升级之前写回的那些。"""
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, unused_days))).replace(microsecond=0).isoformat()
        with self._writer() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, last_used_at, usage_count FROM runs
                WHERE COALESCE(last_used_at, created_at) < ? AND COALESCE(usage_count, 0) = 0
                    AND COALESCE(ai_answer_text, '') = ''
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

    def storage_usage(self) -> dict[str, Any]:
        """本机存档占了多少盘（doctor 用）。只算随使用增长的三样，不含 runtime；清理走 `memory prune`，这里只报数。"""

        def tree_size(root: Path | None) -> tuple[int, int]:
            size = files = 0
            for folder, _, names in os.walk(root) if root is not None else ():
                for name in names:
                    try:
                        size += os.stat(os.path.join(folder, name)).st_size
                        files += 1
                    except OSError:
                        continue  # 遍历途中被删 / 替换的文件
            return size, files

        artifact_bytes, artifact_files = tree_size(self.output_dir)
        trace_bytes, _ = tree_size(self.settings.trace_dir)
        database_bytes = 0
        for suffix in ("", "-wal", "-shm"):
            try:
                database_bytes += os.stat(f"{self.db_path}{suffix}").st_size
            except OSError:
                continue
        try:
            with self._open() as conn:
                runs: int | None = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        except sqlite3.Error:
            runs = None  # 库打不开 / 表坏了：没有数就说没有，不写 0
        return {
            "runs": runs,
            "artifact_files": artifact_files,
            "artifact_bytes": artifact_bytes,
            "database_bytes": database_bytes,
            "trace_bytes": trace_bytes,
            "total_bytes": artifact_bytes + database_bytes + trace_bytes,
        }

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
        _write_json_atomic(target_path, artifact_payload)
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

    def _refresh_run_artifacts(self, run_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """把新的问答写进这个 run 的盘面 / 调度产物。返回（改写了的，没改成的 + 原因）：文件缺了、读不了的不再悄悄跳过。

        报告是交付好的文件（可能在用户的目录里），写回答案不许改写它；manifest 由调用方随后重建。"""
        with self.connect() as conn:
            rows = conn.execute(
                r"""
                SELECT id, tool_name, kind, path, tool_call_id FROM artifacts
                WHERE run_id = ? AND kind != 'run_manifest' AND kind NOT LIKE 'report\_%' ESCAPE '\'
                """,
                (run_id,),
            ).fetchall()
        updated: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for row in rows:
            path = Path(row["path"])
            entry = {"tool_name": row["tool_name"], "kind": row["kind"], "path": str(path)}
            if not path.is_file():
                skipped.append({**entry, "reason": "missing"})
                continue
            try:
                raw_payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:  # unreadable / not JSON: leave that artifact as written, refresh the rest
                skipped.append({**entry, "reason": f"unreadable: {type(exc).__name__}"})
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
            file_size, sha256 = _write_json_atomic(path, updated_payload)
            # 文件变了，落库的 size / sha 必须跟上：manifest 与检索都优先取落库值，不再现算。
            with self._writer() as conn:
                conn.execute("UPDATE artifacts SET file_size = ?, sha256 = ? WHERE id = ?", (file_size, sha256, row["id"]))
                conn.commit()
            updated.append(entry)
        return updated, skipped

    def _build_run_manifest_payload(self, run_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if run is None:
                raise UnknownRunError(run_id)
            tool_calls = conn.execute(
                """
                SELECT id, tool_name, ok, input_json, summary_json, warnings_json, error_json, trace_id, group_id, evaluation_case_id, created_at
                FROM tool_calls
                WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
            artifacts = conn.execute(
                "SELECT tool_name, kind, path, created_at, file_size, sha256, tool_call_id FROM artifacts WHERE run_id = ? ORDER BY id ASC",
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
                "answer_history": self._parse_json_field(run["answer_history_json"]) or [],
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
            raise UnknownRunError(run_id)
        created = datetime.fromisoformat(str(run_row["created_at"]).replace("Z", "+00:00")) if run_row["created_at"] else datetime.now(timezone.utc)
        target_dir = self.output_dir / created.strftime("%Y") / created.strftime("%m") / created.strftime("%d")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{run_id}_manifest.json"
        _write_json_atomic(target_path, manifest_payload)
        now = utc_now_iso()
        with self._writer() as conn:
            conn.execute("BEGIN IMMEDIATE")  # 查与写同一个事务：两个进程同时刷新不会各插一行
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
                except (OSError, ValueError) as exc:  # 读不了 / 坏 JSON：payload 置空，但把原因交给调用方
                    record["payload"] = None
                    record["payload_error"] = f"{type(exc).__name__}: {exc}"
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
