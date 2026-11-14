"""按人 / 按 run / 按时间删除与导出本机存档（CLI `memory delete` / `memory export`）。

删除：默认只列出会删什么（dry-run），`yes=True` 才删。先删文件（产物、manifest、报告）、再删行：中途断了，剩下的是「行在、文件没了」，
再跑一次就删完；反过来会留下没有行的文件，`memory rebuild` 会把删掉的 run 又找回来。
v0.51.0-dev（审计 O-06 / 待决项 6）：报告是这条 run 的派生物，缺省一起删（`keep_reports=True` 才留）；trace 里这些 run 的行一并抹掉
（重写当日文件，原子替换）；给了 `trash_dir` 就移进回收站（`<data_dir>/trash/<id>/`，`restore_trash` 放回后照文件重建索引），
不给就直接删。回收站 30 天后由 `purge_trash` 清掉。

导出：每个 run 一个文件夹，里面是人能直接读的 `run.md`、manifest、产物 JSON 与报告副本，外加一份总目录 `index.md`。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from horosa_skill import fsretry
from horosa_skill.memory import search as _search
from horosa_skill.memory.rebuild import quarantined_backups, scan_artifact_tree

if TYPE_CHECKING:
    from horosa_skill.memory.store import MemoryStore

SAMPLE = 20


def select_runs(
    store: MemoryStore,
    *,
    run_ids: list[str] | None = None,
    entities: list[str] | None = None,
    before: str | None = None,
) -> list[dict[str, Any]]:
    """条件之间是 AND；`entities` 是同一个人的几种叫法（OR）；`before` 是 UTC 串，严格早于它。至少给一个条件（调用方保证）。"""
    sql = ["SELECT id, created_at, query_text, user_question_text FROM runs WHERE 1=1"]
    params: list[Any] = []
    if run_ids:
        sql.append(f"AND id IN ({','.join('?' for _ in run_ids)})")
        params += run_ids
    needles = list(dict.fromkeys(key for key in (_search.entity_search_key(item) for item in entities or []) if key))
    if needles:
        match = " OR ".join(
            "instr(COALESCE(e.search_key, lower(e.display_name) || char(10) || lower(e.entity_key)), ?) > 0" for _ in needles
        )
        sql.append(f"AND EXISTS (SELECT 1 FROM entities e WHERE e.run_id = runs.id AND ({match}))")
        params += needles
    if before:
        sql.append("AND created_at < ?")
        params.append(before)
    sql.append("ORDER BY created_at DESC, rowid DESC")
    with store.connect() as conn:
        rows = conn.execute("\n".join(sql), params).fetchall()
    return [
        {"run_id": row["id"], "created_at": row["created_at"], "question": row["user_question_text"] or row["query_text"]}
        for row in rows
    ]


def _run_files(store: MemoryStore, conn: sqlite3.Connection, run_ids: list[str]) -> tuple[list[Path], list[str]]:
    """要删的文件（产物、manifest，含库里没有行的同 run 文件）与只报不删的报告路径。"""
    wanted = set(run_ids)
    files: dict[str, Path] = {}
    reports: list[str] = []
    for run_id in run_ids:
        for row in conn.execute("SELECT kind, path FROM artifacts WHERE run_id = ?", (run_id,)):
            if str(row["kind"]).startswith("report_"):
                reports.append(row["path"])
            else:
                files[str(row["path"])] = Path(row["path"])
    for run_id, found in scan_artifact_tree(store.output_dir).runs.items():
        if run_id not in wanted:
            continue
        for path in [found.manifest, *(item[0] for item in found.artifacts)]:
            if path is not None:
                files.setdefault(str(path), path)
        for path, _, _ in found.reports:
            if str(path) not in reports:
                reports.append(str(path))
    return list(files.values()), reports


TRASH_DAYS = 30


def trash_root(settings: Any) -> Path:
    """回收站：`<data_dir>/trash`（不在存档目录 runs/ 里——重建索引不会把删掉的 run 找回来）。"""
    from horosa_skill.fileperm import make_private_dir

    root = Path(settings.data_dir).expanduser() / "trash"
    make_private_dir(root)
    return root


def _trace_files(trace_dir: Path | None) -> list[Path]:
    return sorted(trace_dir.glob("*.jsonl")) if trace_dir is not None and trace_dir.is_dir() else []


def _trace_hits(trace_dir: Path | None, run_ids: list[str]) -> int:
    needles = [run_id for run_id in run_ids if run_id]
    total = 0
    for path in _trace_files(trace_dir):
        try:
            total += sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                         if any(needle in line for needle in needles))
        except OSError:
            continue
    return total


def _scrub_traces(trace_dir: Path | None, run_ids: list[str]) -> int:
    """trace 里提到这些 run 的行抹掉：逐个文件重写到同目录临时文件再原子替换（审计 O-06：删除之后 trace 里还有这个人）。"""
    needles = [run_id for run_id in run_ids if run_id]
    removed = 0
    for path in _trace_files(trace_dir):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except OSError:
            continue
        kept = [line for line in lines if not any(needle in line for needle in needles)]
        if len(kept) == len(lines):
            continue
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".scrub-", suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.writelines(kept)
        fsretry.replace(Path(tmp), path)
        removed += len(lines) - len(kept)
    return removed


def _trash_target(store: MemoryStore, entry: Path, path: Path) -> Path:
    try:
        return entry / "files" / path.resolve().relative_to(Path(store.output_dir).resolve())
    except (ValueError, OSError):
        return entry / "outside" / hashlib.sha256(str(path).encode()).hexdigest()[:16] / path.name


def delete_runs(store: MemoryStore, selected: list[dict[str, Any]], *, yes: bool, keep_reports: bool = False,
                trace_dir: Path | None = None, trash_dir: Path | None = None) -> dict[str, Any]:
    run_ids = [item["run_id"] for item in selected]
    with store.connect() as conn:
        files, reports = _run_files(store, conn, run_ids)
    if not keep_reports:
        files = [*files, *(Path(path) for path in reports if Path(path) not in files)]
    report: dict[str, Any] = {
        "dry_run": not yes,
        "runs": len(run_ids),
        "sample": selected[:SAMPLE],
        "files": len([path for path in files if path.exists()]),
        **({"reports_kept": reports} if keep_reports else {"reports_deleted": reports}),
        "trace_lines": _trace_hits(trace_dir, run_ids),
        "disposal": "trash" if trash_dir is not None else "permanent",
        "deleted_runs": 0,
        "deleted_files": 0,
    }
    backups = quarantined_backups(store)
    if backups:
        report["quarantined_copies"] = [str(path) for path in backups]
    if not yes or not run_ids:
        return report
    removed = 0
    failed: list[str] = []
    moved: list[dict[str, str]] = []
    entry: Path | None = None
    if trash_dir is not None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        entry = trash_dir / f"{stamp}-{hashlib.sha256(','.join(sorted(run_ids)).encode()).hexdigest()[:8]}"
        entry.mkdir(parents=True, exist_ok=True)
    for path in files:
        try:
            if not path.exists():
                continue
            if entry is not None:
                target = _trash_target(store, entry, path)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(target))
                moved.append({"from": str(path), "to": str(target)})
            else:
                path.unlink()
            removed += 1
        except OSError as exc:
            failed.append(f"{path}: {type(exc).__name__}")
    if entry is not None:
        (entry / "trash.json").write_text(json.dumps({
            "schema": "horosa.skill.memory.trash.v1", "deleted_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "run_ids": run_ids, "sample": selected[:SAMPLE], "files": moved,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        report["trash_id"] = entry.name
    report["trace_lines_removed"] = _scrub_traces(trace_dir, run_ids)
    with store._writer() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for start in range(0, len(run_ids), 400):
            chunk = run_ids[start : start + 400]
            marks = ",".join("?" for _ in chunk)
            for table in ("entities", "artifacts", "tool_calls"):
                conn.execute(f"DELETE FROM {table} WHERE run_id IN ({marks})", chunk)
            conn.execute(f"DELETE FROM runs WHERE id IN ({marks})", chunk)  # 触发器顺带删检索文档
        conn.commit()
    report["deleted_runs"] = len(run_ids)
    report["deleted_files"] = removed
    if failed:
        report["files_not_deleted"] = failed
    return report


def list_trash(trash_dir: Path | None) -> list[dict[str, Any]]:
    out = []
    for entry in sorted(trash_dir.iterdir(), reverse=True) if trash_dir is not None and trash_dir.is_dir() else []:
        try:
            meta = json.loads((entry / "trash.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"trash_id": entry.name, "deleted_at": meta.get("deleted_at"), "runs": len(meta.get("run_ids") or []),
                    "sample": (meta.get("sample") or [])[:5]})
    return out


def restore_trash(store: MemoryStore, trash_dir: Path, trash_id: str) -> dict[str, Any]:
    """把回收站里的一批放回原处，再照文件重建这些 run 的索引（memory rebuild 的同一套）。原处已有同名文件的不覆盖、列出来。"""
    from horosa_skill.memory.rebuild import rebuild_from_artifacts

    entry = trash_dir / Path(trash_id).name
    meta = json.loads((entry / "trash.json").read_text(encoding="utf-8"))
    restored, skipped = 0, []
    for item in meta.get("files") or []:
        source, target = Path(item["to"]), Path(item["from"])
        if not source.exists():
            continue
        if target.exists():
            skipped.append(str(target))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        restored += 1
    rebuilt = rebuild_from_artifacts(store, min_age_seconds=0, index_bodies=True)
    if not skipped:
        shutil.rmtree(entry, ignore_errors=True)
    return {"ok": True, "trash_id": entry.name, "runs": len(meta.get("run_ids") or []), "restored_files": restored,
            "not_restored_files": skipped, "restored_runs": rebuilt.get("restored_runs", {}).get("total", 0)}


def purge_trash(trash_dir: Path | None, *, days: int = TRASH_DAYS, now: float | None = None) -> int:
    """回收站里超过 `days` 天的批次彻底删掉；返回删掉几批。"""
    cutoff = (now or time.time()) - days * 86400
    purged = 0
    for entry in trash_dir.iterdir() if trash_dir is not None and trash_dir.is_dir() else []:
        try:
            if entry.is_dir() and (entry / "trash.json").stat().st_mtime < cutoff:
                shutil.rmtree(entry)
                purged += 1
        except OSError:
            continue
    return purged


def compact_artifacts(store: MemoryStore, *, decompress: bool = False) -> dict[str, Any]:
    """把存档产物压成 .json.gz（`decompress=True` 反过来），库里的路径跟着改；manifest 与报告不动。可中断、幂等：每份先写新文件、
    改库、再删旧文件——断在中间只会多一份同内容的文件，下次跑照常收尾。最后 VACUUM（删除之后的库空间一并收回）。"""
    from horosa_skill.memory import artifact_io

    from horosa_skill.memory.store import _write_json_atomic

    converted = failed = 0
    saved = 0
    problems: list[str] = []
    with store.connect() as conn:
        rows = conn.execute("SELECT id, path, kind FROM artifacts WHERE substr(kind, 1, 7) != 'report_' AND kind != 'run_manifest'").fetchall()
    for row in rows:
        path = Path(row["path"])
        wanted = artifact_io.plain_name(path) if decompress else artifact_io.compressed_name(path)
        if wanted == path or not path.is_file() or not artifact_io.is_json_artifact(path):
            continue
        try:
            before = path.stat().st_size
            _write_json_atomic(wanted, artifact_io.read_json(path), compress=not decompress)
            after = wanted.stat().st_size
            with store._writer() as conn:
                conn.execute("UPDATE artifacts SET path = ?, file_size = ?, sha256 = NULL WHERE id = ?", (str(wanted), after, row["id"]))
                conn.commit()
            path.unlink()
            converted += 1
            saved += before - after
        except (OSError, ValueError, EOFError) as exc:
            failed += 1
            problems.append(f"{path}: {type(exc).__name__}")
    with store._writer() as conn:
        conn.execute("VACUUM")
    return {"ok": True, "mode": "decompress" if decompress else "compress", "converted": converted, "failed": failed,
            "bytes_saved": saved, **({"problems": problems[:SAMPLE]} if problems else {})}


def count_runs_mentioning(store: MemoryStore, names: list[str]) -> int:
    try:
        return len(select_runs(store, entities=names))
    except sqlite3.Error:
        return 0


# ---- 导出 ----

_UNSAFE = re.compile(r"[^0-9A-Za-z_.-]+")


def _markdown(record: dict[str, Any], texts: list[tuple[str, str]], copied: list[str]) -> str:
    lines = [f"# {record.get('user_question') or record.get('query_text') or record['run_id']}", ""]
    lines.append(f"- run_id: `{record['run_id']}`")
    lines.append(f"- 时间 / time (UTC): {record.get('created_at')}")
    tools = list(dict.fromkeys(call.get("tool_name") for call in record.get("tool_calls") or []))
    names = [" / ".join(_search.technique_names(tool)[:3]) for tool in tools if tool]
    if names:
        lines.append(f"- 技法 / techniques: {'；'.join(names)}")
    subject = record.get("subject") if isinstance(record.get("subject"), dict) else {}
    person = {key: subject[key] for key in ("name", "date", "time", "zone", "place", "lat", "lon", "gender") if subject.get(key) not in (None, "")}
    if person:
        lines.append("- 命主 / subject: " + ", ".join(f"{key}={value}" for key, value in person.items()))
    lines.append("")
    if record.get("ai_answer_text"):
        lines += ["## 解读 / Answer", "", str(record["ai_answer_text"]), ""]
    for index, item in enumerate(record.get("answer_history") or [], start=1):
        if isinstance(item, dict) and item.get("ai_answer_text"):
            lines += [f"## 之前的解读 {index} / Earlier answer {index}（{item.get('replaced_at')}）", "", str(item["ai_answer_text"]), ""]
    for tool, text in texts:
        lines += [f"## 盘面 / Chart — {tool}", "", "```text", text, "```", ""]
    if copied:
        lines += ["## 文件 / Files", ""] + [f"- {name}" for name in copied] + [""]
    return "\n".join(lines)


def export_runs(store: MemoryStore, selected: list[dict[str, Any]], out_dir: Path) -> dict[str, Any]:
    """每个 run 一个文件夹：`run.md`（人读）、`manifest.json`、`artifacts/`（产物 JSON 副本）、`reports/`（报告副本）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    index = ["# Horosa 存档导出 / Horosa runs export", ""]
    exported: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in selected:
        rows = store.query_runs(run_id=item["run_id"], limit=1, include_payload=False, include_history=True)
        if not rows:
            continue
        record = rows[0]
        folder = out_dir / _UNSAFE.sub("_", f"{(record.get('created_at') or '')[:10]}_{record['run_id'][:12]}")
        (folder / "artifacts").mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        texts: list[tuple[str, str]] = []
        for artifact in record.get("artifacts") or []:
            source = Path(str(artifact.get("path") or ""))
            kind = str(artifact.get("kind") or "")
            if not source.is_file():
                missing.append(str(source))
                continue
            if kind == "run_manifest":
                continue
            target_dir = folder / ("reports" if kind.startswith("report_") else "artifacts")
            target_dir.mkdir(exist_ok=True)
            if source.name.endswith(".json.gz"):   # 导出给人读：压缩过的产物解成明文 .json
                from horosa_skill.memory import artifact_io

                target = target_dir / artifact_io.plain_name(source).name
                target.write_text(artifact_io.read_text(source), encoding="utf-8")
            else:
                target = target_dir / source.name
                shutil.copy2(source, target)
            copied.append(f"{target_dir.name}/{target.name}")
            if kind in {"tool_result", "dispatch_result", "hecan_result"}:
                texts += [(str(artifact.get("tool_name")), text) for text in _search.export_texts_from_file(source)]
        try:
            manifest = store._build_run_manifest_payload(record["run_id"])
            (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        except (ValueError, sqlite3.Error):
            pass
        (folder / "run.md").write_text(_markdown(record, texts, copied), encoding="utf-8")
        exported.append({"run_id": record["run_id"], "folder": str(folder), "files": len(copied)})
        index.append(f"- [{record.get('created_at')} — {record.get('user_question') or record['run_id']}]({folder.name}/run.md)")
    (out_dir / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return {"ok": True, "out": str(out_dir), "runs": len(exported), "exported": exported[:SAMPLE], "missing_files": missing[:SAMPLE],
            "index": str(out_dir / "index.md")}
