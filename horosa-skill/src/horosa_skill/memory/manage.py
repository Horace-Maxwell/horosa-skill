"""按人 / 按 run / 按时间删除与导出本机存档（CLI `memory delete` / `memory export`）。

删除：默认只列出会删什么（dry-run），`yes=True` 才删。先删文件（产物、manifest）、再删行：中途断了，剩下的是「行在、文件没了」，
再跑一次就删完；反过来会留下没有行的文件，`memory rebuild` 会把删掉的 run 又找回来。报告文件是交付给用户的，只列出、不删。

导出：每个 run 一个文件夹，里面是人能直接读的 `run.md`、manifest、产物 JSON 与报告副本，外加一份总目录 `index.md`。
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

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


def delete_runs(store: MemoryStore, selected: list[dict[str, Any]], *, yes: bool) -> dict[str, Any]:
    run_ids = [item["run_id"] for item in selected]
    with store.connect() as conn:
        files, reports = _run_files(store, conn, run_ids)
    report: dict[str, Any] = {
        "dry_run": not yes,
        "runs": len(run_ids),
        "sample": selected[:SAMPLE],
        "files": len([path for path in files if path.exists()]),
        "reports_kept": reports,
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
    for path in files:
        try:
            if path.exists():
                path.unlink()
                removed += 1
        except OSError as exc:
            failed.append(f"{path}: {type(exc).__name__}")
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
            shutil.copy2(source, target_dir / source.name)
            copied.append(f"{target_dir.name}/{source.name}")
            if kind in {"tool_result", "dispatch_result"}:
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
