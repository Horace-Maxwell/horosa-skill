"""自备知识库的检索索引：分块 + 中文双字切分 + SQLite FTS5（BM25），增量同步。

设计照搬几个已在生产上跑的开源实现（2026-10 调研，见 docs/LESSONS.md v0.45.0-dev）：
- **分块**（qmd `src/store.ts` 的打分断点法，Cherry Studio 同法；FastGPT 每块带标题路径、标题处不重叠）：先按 Markdown
  标题分节，不跨标题；节太长再在 空行 > 。！？； > 换行 > ，处挑断点切成约 TARGET_CHARS 字的块，相邻块重叠一句。
  每块记正文里的字符区间与行号，引用能精确到「哪个标题、第几行」。
- **中文全文检索**（basic-memory `script_ngrams.py`，Obsidian Copilot 同法）：汉字连续段切成相邻双字（「紫微斗数」→
  紫微 微斗 斗数），西文按词；建索引与查询前统一 NFKC、繁→简、大小写。查询的每个词变成双字短语，词与词 OR，
  bm25 排序。单个汉字的查询走子串回退。不用 jieba：它的词典是现代汉语，古籍里的「伤官见官」「日主旺」会切错。
- **索引放在状态目录**（qmd `~/.cache/qmd/index.sqlite`）：不在用户的文件夹里放任何东西；只存字符区间与倒排，
  **不存正文**（FTS5 contentless）——删了笔记，下次同步索引里也就没有它了。
- **增量同步**：按条目 sha256 比对，变了才重切重建；文件夹里没了的条目整条删掉。

FTS5 不可用（极少见的自编 SQLite）时自动退回逐条子串计分，功能不缺，只是没有 bm25 排序。
"""
from __future__ import annotations

import contextlib
import json
import math
import re
import sqlite3
import threading
import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"  # 分块 / 切词规则一变就加一：旧索引自动整库重建
TARGET_CHARS = 600
MAX_CHARS = 1000
MIN_CHARS = 120  # 比这还短的节（常是只有标题的上级节）并进下一节，不单独成块
OVERLAP_MAX = 150  # 重叠的那一句最长多少字；更长就不重叠
SNIPPET_CHARS = 160
PER_ENTRY_HITS = 2  # 检索结果里同一条目最多出几块（多了就是一个长文件刷屏）

_HAN = r"㐀-䶿一-鿿豈-﫿\U00020000-\U0003134f"
_CJK_RUN = re.compile(f"[{_HAN}]+")
_TOKEN = re.compile(f"[{_HAN}]+|[0-9a-z_]+")
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_SENTENCE_END = "。！？；!?;…"


# ───────────────────────────── 归一与切词 ─────────────────────────────


def normalize(text: str) -> str:
    """建索引与查询共用：NFKC（全角→半角）→ 繁→简 → casefold。"""
    from horosa_skill.textscript import fold_to_simplified

    return fold_to_simplified(unicodedata.normalize("NFKC", text)).casefold()


def _run_grams(run: str) -> list[str]:
    return [run] if len(run) == 1 else [run[i : i + 2] for i in range(len(run) - 1)]


def grams(text: str) -> list[str]:
    """归一后的切词：汉字段 → 相邻双字（单字段保留单字），西文 / 数字 → 整词。"""
    out: list[str] = []
    for match in _TOKEN.finditer(normalize(text)):
        token = match.group(0)
        out.extend(_run_grams(token) if _CJK_RUN.fullmatch(token) else [token])
    return out


@dataclass(frozen=True)
class Query:
    phrases: tuple[tuple[str, ...], ...]  # 每个词的双字序列
    singles: tuple[str, ...]  # 单个汉字的词：FTS 里没有对应的双字，走子串回退
    terms: tuple[str, ...]  # 归一后的原词（做摘要定位、子串回退用）

    @property
    def empty(self) -> bool:
        return not (self.phrases or self.singles)

    def fts(self) -> str:
        # 只有引号里的双字 / [0-9a-z_] 词进 MATCH：查询文本里的 FTS 语法字符（* ^ : NEAR）一律到不了解析器。
        return " OR ".join('"' + " ".join(phrase) + '"' for phrase in self.phrases)


def parse_query(query: str) -> Query:
    phrases: list[tuple[str, ...]] = []
    singles: list[str] = []
    terms: list[str] = []
    for raw in re.split(r"[\s,，、;；|/]+", str(query or "")):
        term = normalize(raw)
        tokens = _TOKEN.findall(term)
        if not tokens:
            continue
        joined = "".join(tokens)
        if joined in terms:
            continue
        terms.append(joined)
        if len(tokens) == 1 and _CJK_RUN.fullmatch(tokens[0]) and len(tokens[0]) == 1:
            singles.append(tokens[0])
            continue
        phrase: list[str] = []
        for token in tokens:
            phrase.extend(_run_grams(token) if _CJK_RUN.fullmatch(token) else [token])
        phrases.append(tuple(phrase))
    return Query(tuple(phrases), tuple(singles), tuple(terms))


# ───────────────────────────── 分块 ─────────────────────────────


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    start: int  # 正文里的字符区间 [start, end)：body[start:end] 就是这一块
    end: int
    line_start: int  # 正文行号（0 起），含
    line_end: int  # 含
    heading: tuple[str, ...]  # 标题路径（不含条目标题）


def _sections(body: str) -> list[tuple[int, int, tuple[str, ...]]]:
    """按 Markdown 标题分节：[(起, 止, 标题路径)]。代码块里的 # 不算标题。"""
    sections: list[tuple[int, int, tuple[str, ...]]] = []
    path: list[tuple[int, str]] = []
    start, pos, in_fence = 0, 0, False
    current: tuple[str, ...] = ()
    for line in body.splitlines(keepends=True):
        stripped = line.rstrip("\n")
        if _FENCE.match(stripped):
            in_fence = not in_fence
        heading = None if in_fence else HEADING.match(stripped)
        if heading:
            if pos > start:
                sections.append((start, pos, current))
            level = len(heading.group(1))
            while path and path[-1][0] >= level:
                path.pop()
            path.append((level, heading.group(2).strip()))
            current = tuple(title for _, title in path)
            start = pos
        pos += len(line)
    if pos > start:
        sections.append((start, pos, current))
    return sections


def _break_score(text: str, i: int) -> int:
    """在 text[i] 之后切的得分（qmd BREAK_PATTERNS 的中文版）。"""
    ch = text[i]
    nxt = text[i + 1] if i + 1 < len(text) else "\n"
    if ch == "\n" and nxt == "\n":
        return 20
    if ch in _SENTENCE_END:
        return 12 if nxt not in "」』”）)" else 0
    if ch in "」』”" and i > 0 and text[i - 1] in _SENTENCE_END:
        return 12
    if ch == "\n":
        return 6
    if ch in "，,：:":
        return 1
    return 0


def _split_long(text: str, base: int) -> list[tuple[int, int]]:
    """一节太长：在断点处切，返回 [(起, 止)]（相对整篇正文）。相邻块重叠最后一句。"""
    spans: list[tuple[int, int]] = []
    start = 0
    n = len(text)
    while n - start > MAX_CHARS:
        lo, hi = start + int(TARGET_CHARS * 0.6), min(start + MAX_CHARS, n - 1)
        best, best_score = -1, -1.0
        for i in range(lo, hi):
            score = _break_score(text, i)
            if score <= 0:
                continue
            # 离目标越远越打折（qmd：距离平方衰减），同分取靠近目标的。
            distance = abs(i - (start + TARGET_CHARS)) / TARGET_CHARS
            weighted = score * (1 - 0.7 * distance * distance)
            if weighted > best_score:
                best, best_score = i, weighted
        cut = (best + 1) if best >= 0 else min(start + MAX_CHARS, n)
        spans.append((base + start, base + cut))
        # 下一块从上一块最后一句开头起（≤ OVERLAP_MAX 字），句子太长就不重叠。
        back = cut - 1
        while back > start and _break_score(text, back - 1) < 12 and text[back - 1] != "\n":
            back -= 1
        start = back if 0 < cut - back <= OVERLAP_MAX and back > start else cut
        while start < n and text[start] in " \t\n":
            start += 1
    if start < n and text[start:].strip():
        spans.append((base + start, base + n))
    return spans


def chunk_body(body: str) -> list[Chunk]:
    """正文 → 块。不跨标题；太长的节在断点处切。太短的节（常是只有一行标题的上级节）并进紧跟着的**下级**节，
    标题路径取下级的（它本就含上级）；下一节是平级 / 上级就各自成块——不把两个话题揉进一块（FastGPT 同规则）。"""
    pieces: list[tuple[int, int, tuple[str, ...]]] = []
    pending: tuple[int, int, tuple[str, ...]] | None = None

    def emit(start: int, end: int, heading: tuple[str, ...]) -> None:
        for a, b in _split_long(body[start:end], start) if end - start > MAX_CHARS else [(start, end)]:
            pieces.append((a, b, heading))

    for start, end, heading in _sections(body):
        if pending is not None:
            p_start, p_end, p_heading = pending
            pending = None
            if len(heading) > len(p_heading) and heading[: len(p_heading)] == p_heading:
                start = p_start
            elif body[p_start:p_end].strip():
                emit(p_start, p_end, p_heading)
        if not body[start:end].strip():
            continue
        if end - start < MIN_CHARS:
            pending = (start, end, heading)
            continue
        emit(start, end, heading)
    if pending is not None and body[pending[0]:pending[1]].strip():
        emit(*pending)
    chunks: list[Chunk] = []
    for ordinal, (a, b, heading) in enumerate(pieces):
        while b > a and body[b - 1] in " \t\n":
            b -= 1
        while a < b and body[a] in " \t\n":
            a += 1
        if a >= b:
            continue
        chunks.append(Chunk(len(chunks), a, b, body.count("\n", 0, a), body.count("\n", 0, b - 1), heading))
    return chunks


# ───────────────────────────── 索引 ─────────────────────────────


_LOCK = threading.RLock()


def index_path(settings: Any) -> Path:
    from horosa_skill.knowledge.user import state_dir

    return state_dir(settings) / "index.sqlite"


def fts5_available() -> bool:
    try:
        with contextlib.closing(sqlite3.connect(":memory:")) as conn:
            conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        return True
    except sqlite3.Error:
        return False


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15, isolation_level=None)
    # 隐私：删掉的条目尽量不在库文件里留残页（secure_delete 把释放的页清零；FTS5 段合并前的旧词条不保证）。
    # 用回滚日志而非 WAL：读写都很短，WAL 的并发优势用不上，少一个常驻的 -wal 文件。
    conn.execute("PRAGMA secure_delete=ON")
    conn.execute("PRAGMA journal_mode=DELETE")
    return conn


def _create(conn: sqlite3.Connection) -> None:
    # 逐条 execute：executescript 会先隐式 COMMIT，把调用方的 BEGIN IMMEDIATE 事务提前结束。
    for statement in (
        "CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)",
        ("CREATE TABLE IF NOT EXISTS entries(entry_id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, title TEXT NOT NULL, "
         "tags TEXT NOT NULL, chunks INTEGER NOT NULL)"),
        ("CREATE TABLE IF NOT EXISTS chunks(rowid INTEGER PRIMARY KEY, entry_id TEXT NOT NULL, ordinal INTEGER NOT NULL, "
         "char_start INTEGER NOT NULL, char_end INTEGER NOT NULL, line_start INTEGER NOT NULL, line_end INTEGER NOT NULL, "
         "heading TEXT NOT NULL)"),
        "CREATE INDEX IF NOT EXISTS chunks_entry ON chunks(entry_id)",
    ):
        conn.execute(statement)
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE name='chunk_fts'").fetchone()
    if not exists:
        try:  # 不存正文（contentless，SQLite ≥ 3.43 才能按 rowid 删）；更旧的退回普通表
            conn.execute("CREATE VIRTUAL TABLE chunk_fts USING fts5(title, heading, tags, body, content='', "
                         "contentless_delete=1, tokenize='unicode61 remove_diacritics 0')")
        except sqlite3.OperationalError:
            conn.execute("CREATE VIRTUAL TABLE chunk_fts USING fts5(title, heading, tags, body, "
                         "tokenize='unicode61 remove_diacritics 0')")
        # 列权重：标题 4、标题路径 3、标签 3、正文 1（qmd 标题 4×正文；Obsidian Copilot 标题 5 / 标签 4 / 标题行 2.5 / 正文 1）。
        conn.execute("INSERT INTO chunk_fts(chunk_fts, rank) VALUES('rank', 'bm25(4.0, 3.0, 3.0, 1.0)')")


def _reset(conn: sqlite3.Connection) -> None:
    for table in ("chunk_vec", "chunk_fts", "chunks", "entries"):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    _create(conn)
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema', ?)", (SCHEMA_VERSION,))


@dataclass
class SyncReport:
    added: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    chunks: int = 0
    engine: str = "fts5"
    vectors: int = 0  # 本次新算了多少块的向量（可选向量检索就绪时，knowledge/vectors.py）

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def sync(settings: Any, entries: Iterable[Any], *, rebuild: bool = False) -> SyncReport:
    """把索引对齐到当前条目：sha256 变了的重建，没了的删掉。返回本次改了多少。"""
    report = SyncReport()
    entries = list(entries)
    if not fts5_available():
        report.engine = "substring"
        report.unchanged = len(entries)
        return report
    with _LOCK, contextlib.closing(_connect(index_path(settings))) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _create(conn)
            row = conn.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
            if rebuild or row is None or row[0] != SCHEMA_VERSION:
                _reset(conn)
            known = {eid: (sha, title, tags) for eid, sha, title, tags in
                     conn.execute("SELECT entry_id, sha256, title, tags FROM entries")}
            seen: set[str] = set()
            for entry in entries:
                seen.add(entry.id)
                tags = json.dumps(sorted(entry.tags), ensure_ascii=False)
                if known.get(entry.id) == (entry.sha256, entry.title, tags):
                    report.unchanged += 1
                    continue
                if entry.id in known:
                    _drop_entry(conn, entry.id)
                    report.updated += 1
                else:
                    report.added += 1
                pieces = chunk_body(entry.text)
                title_grams = " ".join(grams(entry.title))
                tag_grams = " ".join(g for tag in sorted(entry.tags) for g in grams(tag))
                for piece in pieces:
                    cursor = conn.execute(
                        "INSERT INTO chunks(entry_id, ordinal, char_start, char_end, line_start, line_end, heading) "
                        "VALUES(?,?,?,?,?,?,?)",
                        (entry.id, piece.ordinal, piece.start, piece.end, piece.line_start, piece.line_end,
                         json.dumps(piece.heading, ensure_ascii=False)),
                    )
                    conn.execute(
                        "INSERT INTO chunk_fts(rowid, title, heading, tags, body) VALUES(?,?,?,?,?)",
                        (cursor.lastrowid, title_grams, " ".join(g for h in piece.heading for g in grams(h)), tag_grams,
                         " ".join(grams(entry.text[piece.start:piece.end]))),
                    )
                conn.execute("INSERT OR REPLACE INTO entries(entry_id, sha256, title, tags, chunks) VALUES(?,?,?,?,?)",
                             (entry.id, entry.sha256, entry.title, tags, len(pieces)))
            for stale in set(known) - seen:
                _drop_entry(conn, stale)
                report.removed += 1
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        report.chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        from horosa_skill.knowledge import vectors

        if vectors.ready(settings):
            report.vectors = _sync_vectors(settings, conn, {entry.id: entry for entry in entries})
    return report


def _sync_vectors(settings: Any, conn: sqlite3.Connection, entries: dict[str, Any]) -> int:
    """给还没有向量的块补算（在 FTS 事务提交之后、分批提交：算向量慢，别占着写锁）。

    嵌入文本 = 「条目标题 › 标题路径」+ 块正文：块前加上下文是 Anthropic Contextual Retrieval 的省钱版
    （不用 LLM 生成，直接用标题路径）。换了模型的旧向量整表作废。"""
    from horosa_skill.knowledge import vectors

    conn.execute("CREATE TABLE IF NOT EXISTS chunk_vec(rowid INTEGER PRIMARY KEY, model TEXT NOT NULL, vec BLOB NOT NULL)")
    conn.execute("DELETE FROM chunk_vec WHERE model != ? OR rowid NOT IN (SELECT rowid FROM chunks)", (vectors.MODEL_NAME,))
    missing = conn.execute(
        "SELECT c.rowid, c.entry_id, c.char_start, c.char_end, c.heading FROM chunks c "
        "LEFT JOIN chunk_vec v ON v.rowid = c.rowid WHERE v.rowid IS NULL ORDER BY c.rowid"
    ).fetchall()
    rows = [(rowid, entries[eid], a, b, json.loads(h)) for rowid, eid, a, b, h in missing if eid in entries]
    if not rows:
        return 0
    model = vectors.embedder(settings)
    done = 0
    for start in range(0, len(rows), 64):
        batch = rows[start:start + 64]
        texts = [" › ".join([entry.title, *heading]) + "\n" + entry.text[a:b] for _, entry, a, b, heading in batch]
        matrix = model.embed(texts)
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany("INSERT OR REPLACE INTO chunk_vec(rowid, model, vec) VALUES(?,?,?)",
                         [(rowid, vectors.MODEL_NAME, matrix[i].tobytes()) for i, (rowid, *_rest) in enumerate(batch)])
        conn.execute("COMMIT")
        done += len(batch)
    return done


def _vector_rank(settings: Any, query: Query, raw_query: str) -> list[tuple[str, int, float]]:
    """查询向量与全部块向量的余弦（暴力算：几千块、512 维，毫秒级），过 MIN_COSINE 的前 50 个。"""
    import numpy as np

    from horosa_skill.knowledge import vectors

    with contextlib.closing(_connect(index_path(settings))) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='chunk_vec'").fetchone():
            return []
        rows = conn.execute("SELECT c.entry_id, c.ordinal, v.vec FROM chunk_vec v JOIN chunks c ON c.rowid = v.rowid "
                            "WHERE v.model = ?", (vectors.MODEL_NAME,)).fetchall()
    if not rows:
        return []
    matrix = np.frombuffer(b"".join(r[2] for r in rows), dtype=np.float32).reshape(len(rows), -1)
    query_vector = vectors.embedder(settings).embed([raw_query], query=True)[0]
    sims = matrix @ query_vector
    order = np.argsort(-sims, kind="stable")[:50]
    return [(rows[i][0], rows[i][1], float(sims[i])) for i in order if sims[i] >= vectors.MIN_COSINE]


RRF_K = 60  # Cormack, Clarke & Büttcher 2009；Elasticsearch / FastGPT / Cherry Studio 同值


def _fuse(lexical: list[tuple[str, int, float]], semantic: list[tuple[str, int, float]]) -> list[tuple[str, int, float]]:
    """倒数排名融合：只看名次不看分数（BM25 与余弦不同尺度）。同分按 BM25 名次、再按向量名次、再按 (条目, 块) 定序——
    调研里同分靠插入顺序决胜就排错过一次。返回分数归一到 0–1（最高者为 1）。"""
    fused: dict[tuple[str, int], list[float]] = {}
    for weight_list, position in ((lexical, 0), (semantic, 1)):
        for rank, (eid, ordinal, _) in enumerate(weight_list):
            slot = fused.setdefault((eid, ordinal), [0.0, float("inf"), float("inf")])
            slot[0] += 1 / (RRF_K + rank + 1)
            slot[1 + position] = min(slot[1 + position], rank)
    if not fused:
        return []
    best = max(v[0] for v in fused.values())
    ordered = sorted(fused.items(), key=lambda kv: (-kv[1][0], kv[1][1], kv[1][2], kv[0]))
    return [(eid, ordinal, slot[0] / best) for (eid, ordinal), slot in ordered]


def _drop_entry(conn: sqlite3.Connection, entry_id: str) -> None:
    rowids = [r for (r,) in conn.execute("SELECT rowid FROM chunks WHERE entry_id=?", (entry_id,))]
    conn.executemany("DELETE FROM chunk_fts WHERE rowid=?", [(r,) for r in rowids])
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='chunk_vec'").fetchone():
        conn.executemany("DELETE FROM chunk_vec WHERE rowid=?", [(r,) for r in rowids])
    conn.execute("DELETE FROM chunks WHERE entry_id=?", (entry_id,))
    conn.execute("DELETE FROM entries WHERE entry_id=?", (entry_id,))


def stored_chunks(settings: Any, entry_id: str) -> list[Chunk]:
    if not fts5_available() or not index_path(settings).exists():
        return []
    with contextlib.closing(_connect(index_path(settings))) as conn:
        rows = conn.execute("SELECT ordinal, char_start, char_end, line_start, line_end, heading FROM chunks "
                            "WHERE entry_id=? ORDER BY ordinal", (entry_id,)).fetchall()
    return [Chunk(o, a, b, ls, le, tuple(json.loads(h))) for o, a, b, ls, le, h in rows]


# ───────────────────────────── 检索 ─────────────────────────────


@dataclass(frozen=True)
class Hit:
    entry_id: str
    chunk: Chunk
    score: float  # 0–1（BM25 / (1 + BM25)；开了向量检索时是 RRF 融合分，最高者为 1），只在同一次检索里可比


def search(settings: Any, entries: dict[str, Any], query: Query, *, limit: int = 8, offset: int = 0,
           per_entry: int = PER_ENTRY_HITS, use_index: bool = True, raw_query: str = "") -> tuple[list[Hit], int]:
    """块级检索：返回 (这一页的命中, 总命中数)。同一条目最多 per_entry 块。entries = {id: UserKnowledgeEntry}。

    use_index=False（索引没对齐）时逐条子串计分；块从正文现切，不读索引里可能过期的区间。"""
    if query.empty or not entries:
        return [], 0
    ranked: list[tuple[str, int, float]] = []  # (entry_id, ordinal, score)
    use_index = use_index and fts5_available() and index_path(settings).exists()
    if query.phrases and use_index:
        with contextlib.closing(_connect(index_path(settings))) as conn:
            rows = conn.execute(
                "SELECT c.entry_id, c.ordinal, c.char_start, c.char_end, c.heading FROM chunk_fts f "
                "JOIN chunks c ON c.rowid = f.rowid WHERE chunk_fts MATCH ? ORDER BY f.rank LIMIT 500", (query.fts(),),
            ).fetchall()
            n_chunks, avg_len = conn.execute("SELECT COUNT(*), AVG(char_end - char_start) FROM chunks").fetchone()
            df = {phrase: conn.execute("SELECT COUNT(*) FROM chunk_fts WHERE chunk_fts MATCH ?",
                                       ('"' + " ".join(phrase) + '"',)).fetchone()[0] for phrase in query.phrases}
        ranked = _bm25(entries, rows, query, df, n_chunks or 1, avg_len or 1.0)
    elif query.phrases:
        ranked = _substring_rank(settings, entries, query.terms, use_index=use_index)
    if query.singles:
        seen = {(eid, o) for eid, o, _ in ranked}
        extra = [hit for hit in _substring_rank(settings, entries, query.singles, use_index=use_index)
                 if (hit[0], hit[1]) not in seen]
        ranked.extend((eid, o, score * 0.5) for eid, o, score in extra)  # 单字命中排在词命中之后
        ranked.sort(key=lambda r: -r[2])
    from horosa_skill.knowledge import vectors

    if use_index and raw_query.strip() and vectors.ready(settings):
        # 可选向量检索：与 BM25 做 RRF；只靠向量进来的候选已过 MIN_COSINE（换了说法的查询靠它补回来）。
        ranked = _fuse(ranked, _vector_rank(settings, query, raw_query))
    chunk_cache: dict[str, list[Chunk]] = {}
    hits: list[Hit] = []
    per: Counter[str] = Counter()
    for eid, ordinal, score in ranked:
        if eid not in entries or per[eid] >= per_entry:
            continue
        chunks = chunk_cache.setdefault(eid, chunks_for(settings, entries[eid], use_index))
        if ordinal >= len(chunks):
            continue
        per[eid] += 1
        hits.append(Hit(eid, chunks[ordinal], round(score, 4)))
    return hits[offset : offset + limit], len(hits)


BM25_K1, BM25_B = 1.2, 0.75
FIELD_WEIGHTS = {"title": 4.0, "heading": 3.0, "tags": 3.0, "body": 1.0}  # 与 FTS5 rank 的列权重一致


def _bm25(entries: dict[str, Any], rows: list[tuple[Any, ...]], query: Query, df: dict[tuple[str, ...], int],
          n_chunks: int, avg_len: float) -> list[tuple[str, int, float]]:
    """FTS5 只负责找候选（倒排、持久化）；分数自己算 BM25（字段加权，Lucene 的 IDF = ln(1 + (N-n+0.5)/(n+0.5))，恒为正）。

    不直接用 FTS5 的 bm25()：它对出现在过半块里的词把 IDF 压到 1e-6（fts5_aux.c），小知识库里「命宫」这种
    人人都写的词就成了 0 分——排序虽还对，分数却像没命中。"""
    out: list[tuple[str, int, float]] = []
    terms = ["".join(p) if all(_CJK_RUN.fullmatch(g) for g in p) else " ".join(p) for p in query.phrases]
    for eid, ordinal, start, end, heading in rows:
        entry = entries.get(eid)
        if entry is None:
            continue
        fields = {"body": normalize(entry.text[start:end]), "title": normalize(entry.title),
                  "heading": normalize(" ".join(json.loads(heading))), "tags": normalize(" ".join(sorted(entry.tags)))}
        length = max(end - start, 1)
        score = 0.0
        for phrase, term in zip(query.phrases, terms):
            n = df.get(phrase, 0)
            idf = math.log(1 + (n_chunks - n + 0.5) / (n + 0.5))
            tf = sum(weight * _count(fields[name], phrase, term) for name, weight in FIELD_WEIGHTS.items())
            score += idf * tf * (BM25_K1 + 1) / (tf + BM25_K1 * (1 - BM25_B + BM25_B * length / avg_len)) if tf else 0.0
        out.append((eid, ordinal, score / (1 + score)))
    out.sort(key=lambda r: -r[2])  # 稳定排序：同分保持 FTS5 的先后
    return out


def _count(text: str, phrase: tuple[str, ...], term: str) -> int:
    if all(_CJK_RUN.fullmatch(g) for g in phrase):
        return text.count(term)
    return len(re.findall(r"(?<![0-9a-z_])" + r"\W*".join(map(re.escape, phrase)) + r"(?![0-9a-z_])", text))


def chunks_for(settings: Any, entry: Any, use_index: bool = True) -> list[Chunk]:
    return (stored_chunks(settings, entry.id) if use_index else []) or chunk_body(entry.text)


def _substring_rank(settings: Any, entries: dict[str, Any], terms: Iterable[str], *,
                    use_index: bool = True) -> list[tuple[str, int, float]]:
    """FTS5 不可用 / 单字查询：逐块数子串（归一后），命中次数 + 命中的词数计分。"""
    terms = [t for t in terms if t]
    out: list[tuple[str, int, float]] = []
    for eid, entry in entries.items():
        chunks = chunks_for(settings, entry, use_index)
        for chunk in chunks:
            text = normalize(entry.text[chunk.start:chunk.end])
            counts = [text.count(t) for t in terms]
            if not any(counts):
                continue
            raw = sum(1 for c in counts if c) + 0.1 * min(sum(counts), 10)
            out.append((eid, chunk.ordinal, raw / (1 + raw)))
    out.sort(key=lambda r: -r[2])
    return out


def snippet(text: str, terms: Iterable[str], width: int = SNIPPET_CHARS) -> str:
    """命中词附近的一段原文（不是归一后的文本）。"""
    folded = normalize(text)
    position = -1
    for term in terms:
        position = folded.find(term)
        if position >= 0:
            break
    start = max(position - width // 4, 0) if position >= 0 else 0
    piece = text[start:start + width].replace("\n", " ").strip()
    return ("…" if start else "") + piece + ("…" if start + width < len(text) else "")


# ───────────────────────────── 计算时挑相关段落 ─────────────────────────────


def relevant_chunks(entry: Any, chunks: list[Chunk], focus: str, budget: int) -> list[Chunk]:
    """一条笔记比分到的字数长：挑与 focus（本次盘面导出文本 + 用户检索词）相关的块，按相关度装进 budget、按原文顺序返回。

    打分 = 块与 focus 共有的双字，各按「在这条笔记里有多少块含它」取 IDF 加权（只在这一条里算，常见的「之一」
    「者也」自然被压低）；标题路径里的命中算两倍。没有任何相关块就退回从头取（与此前的截断等价）。
    """
    if not chunks:
        return []
    focus_grams = set(grams(focus))
    block_grams = [set(grams(entry.text[c.start:c.end])) for c in chunks]
    heading_grams = [{g for h in c.heading for g in grams(h)} for c in chunks]
    df: Counter[str] = Counter(g for bag in block_grams for g in bag)
    n = len(chunks)
    scores = []
    for index, chunk in enumerate(chunks):
        shared = block_grams[index] & focus_grams
        score = sum(math.log(1 + n / df[g]) for g in shared if len(g) > 1)
        score += 2 * sum(math.log(1 + n / max(df[g], 1)) for g in heading_grams[index] & focus_grams if len(g) > 1)
        scores.append(score)
    # 只带有关的块（qmd / RAGFlow 都只给命中的）：预算没用完也不拿无关段落凑数。一块都不相关才退回从头取。
    order = sorted((i for i in range(n) if scores[i] > 0), key=lambda i: (-scores[i], i)) if any(scores) else list(range(n))
    picked: list[int] = []
    used = 0
    for index in order:
        size = chunks[index].end - chunks[index].start
        if used + size > budget:
            continue
        picked.append(index)
        used += size
    if not picked:  # 连最小的一块都放不下：给第一块（调用方会再截）
        picked = [order[0]]
    return [chunks[i] for i in sorted(picked)]
