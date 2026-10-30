#!/usr/bin/env python
"""Hand-copied upstream logic audit — the guard the vendor manifest cannot be.

Why this exists (v0.46.0, upstream v3.11.3 → v3.13.0): every vendored file matched `vendor_manifest.json`, yet a
dozen skill-side copies of upstream logic had gone stale — a Python table (`_INDIA_MOUNT_VARGA_OPTIONS`, 12 of 16
labels renamed), literal defaults (taiyizeri `after23NewDay` 0 → the global default), UI strings, the year-wide civil
calendar (`shiftMoment` / `solveReturnBefore` moved to the Julian/BCE axis), a backend field that no longer existed
(yearsystem129). The manifest guards *files*; a hand copy is a second source of truth nobody guards.

This audit closes the gap with a ledger:

* `--scan --from OLD --to NEW` (maintainer machine, needs `$HOROSA_SOURCE_ROOT` with its astrostudyui
  node_modules): lists every upstream top-level name whose comment-stripped code changed between the two pins and
  that a skill file mentions (Python under `src/horosa_skill`, JS glue under `horosa-core-js/src/tools|shared`).
  Each hit must carry a verdict in `contracts/upstream_port_audit.json` (`no_port …` / `port_unchanged …` /
  `ported …` / `reviewed …`); unreviewed hits fail. `--write-skeleton PATH` dumps the hit list as a starting point.
* default (no `--scan`, CI-safe): the ledger must be audited **to the recorded upstream pin**
  (`contracts/upstream_provenance.json`). Re-pinning upstream without re-running the audit fails here.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

PKG_ROOT = Path(__file__).resolve().parents[1]
LEDGER = PKG_ROOT / "contracts" / "upstream_port_audit.json"
PROVENANCE = PKG_ROOT / "contracts" / "upstream_provenance.json"
UI_SRC = "Horosa-Web/astrostudyui/src"
SCAN_ROOTS = (PKG_ROOT / "src" / "horosa_skill", PKG_ROOT / "horosa-core-js" / "src" / "tools",
              PKG_ROOT / "horosa-core-js" / "src" / "shared")
# no_port = 只是引用 / 调 vendored 函数 / 撞名；port_unchanged = 有移植，逐值核过上游改动不影响它；ported = 这轮已改；
# reviewed = 该技法域在这轮同步里做过逐函数新旧上游比对（未逐名细分结论时如实写这一档，不冒充前三档）。
VERDICTS = ("no_port", "port_unchanged", "ported", "reviewed")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_ledger() -> list[str]:
    ledger, provenance = _load(LEDGER), _load(PROVENANCE)
    problems = []
    pin = provenance.get("upstream_git_sha") or ""
    if ledger.get("to") != pin:
        problems.append(
            f"upstream_port_audit.json is audited to {str(ledger.get('to'))[:12]} but the recorded upstream pin is {pin[:12]} — "
            f"run `scripts/audit_upstream_ports.py --scan --from {str(ledger.get('to'))[:12]} --to {pin[:12]}`, review every hit, "
            "record verdicts, then set `from`/`to`"
        )
    for name, verdict in sorted((ledger.get("reviewed") or {}).items()):
        if not isinstance(verdict, str) or not verdict.startswith(VERDICTS):
            problems.append(f"ledger verdict for {name!r} must start with one of {VERDICTS}: {verdict!r}")
    return problems


def _export_tree(source_root: Path, sha: str, dest: Path) -> Path:
    data = subprocess.run(["git", "-C", str(source_root), "archive", sha, UI_SRC], check=True, capture_output=True).stdout
    with tarfile.open(fileobj=BytesIO(data)) as tar:
        tar.extractall(dest, filter="data")
    return dest / UI_SRC


def changed_names(source_root: Path, old: str, new: str) -> list[tuple[str, str]]:
    node = shutil.which("node")
    modules = source_root / "Horosa-Web" / "astrostudyui" / "node_modules"
    if node is None or not (modules / "@babel" / "parser").is_dir():
        raise SystemExit(f"audit-upstream-ports: needs node and {modules}/@babel/parser (upstream dev deps)")
    with tempfile.TemporaryDirectory() as tmp:
        old_src = _export_tree(source_root, old, Path(tmp) / "old")
        new_src = _export_tree(source_root, new, Path(tmp) / "new")
        out = subprocess.run(
            [node, str(PKG_ROOT / "scripts" / "upstream_decl_diff.mjs"), str(old_src), str(new_src)],
            check=True, capture_output=True, text=True, encoding="utf-8", env={**os.environ, "NODE_PATH": str(modules)},
        ).stdout
    return [tuple(item) for item in json.loads(out)]


def skill_hits(changed: list[tuple[str, str]]) -> dict[str, dict]:
    files = [p for root in SCAN_ROOTS for p in root.rglob("*")
             if p.suffix in (".py", ".js", ".mjs") and "knowledge/data" not in p.as_posix()]
    texts = {p: p.read_text(encoding="utf-8", errors="replace") for p in files}
    hits: dict[str, dict] = {}
    for name, kind in changed:
        # 名字过短 / 全小写（如 `msg`、`today`）在 skill 里撞名太多，只看带大写或下划线、≥6 字的标识符。
        if len(name) < 6 or not re.search(r"[A-Z_]", name):
            continue
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
        where = sorted(p.relative_to(PKG_ROOT).as_posix() for p, text in texts.items() if pattern.search(text))
        if where:
            hits[name] = {"upstream": kind, "skill_files": where}
    return hits


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scan", action="store_true", help="recompute hits between two upstream pins (needs HOROSA_SOURCE_ROOT)")
    parser.add_argument("--from", dest="old", help="old upstream sha (default: ledger `from`)")
    parser.add_argument("--to", dest="new", help="new upstream sha (default: ledger `to`)")
    parser.add_argument("--write-skeleton", type=Path, help="write the hit list as JSON to this path")
    args = parser.parse_args(argv)

    if not args.scan:
        problems = check_ledger()
        for problem in problems:
            print(f"audit-upstream-ports: {problem}")
        if problems:
            return 1
        ledger = _load(LEDGER)
        print(f"audit-upstream-ports: ok (ledger audited {ledger['from'][:12]} → {ledger['to'][:12]}, "
              f"{len(ledger.get('reviewed') or {})} reviewed names)")
        return 0

    root = os.environ.get("HOROSA_SOURCE_ROOT")
    if not root or not (Path(root) / UI_SRC).is_dir():
        print("audit-upstream-ports: --scan needs HOROSA_SOURCE_ROOT pointing at a Horosa-Public checkout")
        return 2
    ledger = _load(LEDGER)
    old, new = args.old or ledger.get("from"), args.new or ledger.get("to")
    hits = skill_hits(changed_names(Path(root), old, new))
    reviewed = (ledger.get("reviewed") or {}) if new == ledger.get("to") else {}
    missing = sorted(name for name in hits if name not in reviewed)
    if args.write_skeleton:
        args.write_skeleton.write_text(json.dumps(hits, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    for name in missing:
        print(f"UNREVIEWED {hits[name]['upstream']:8s} {name}: {', '.join(hits[name]['skill_files'][:4])}")
    print(f"audit-upstream-ports: {len(hits)} hit(s) {old[:12]} → {new[:12]}; {len(missing)} unreviewed")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
