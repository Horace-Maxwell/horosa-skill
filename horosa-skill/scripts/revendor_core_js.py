#!/usr/bin/env python
"""Re-vendor a 星阙 frontend JS file into `horosa-core-js/src/vendor/` with the headless transform.

The transform is the one AGENTS.md §5 spells out, applied mechanically so every re-vendor is identical
and reviewable:

1. sibling/relative imports get an explicit `.js` (Node ESM needs it; the browser bundler does not);
2. backend-only imports are dropped (`utils/request`, `{ServerRoot,ResultKey}`, `buildKentangEndpoint`)
   — Python does the fetching, the JS layer never speaks HTTP;
3. exported `fetch*Pan` network helpers are removed wholesale (same reason);
4. everything else — especially the `normalize*` overlays and every `build*SnapshotText` — is copied
   **verbatim**, because byte-identical formatting is the whole point of vendoring instead of porting.

Usage:  python scripts/revendor_core_js.py <upstream-src-root> <relative/path/File.js> [more...]
        (`--check` reports what would change without writing)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_ROOT = REPO_ROOT / "horosa-skill/horosa-core-js/src/vendor"

_DROP_IMPORT_PATTERNS = (
    re.compile(r"^import\s+request\s+from\s+['\"][^'\"]*utils/request['\"];?\s*$", re.M),
    re.compile(r"^import\s+\{[^}]*\b(?:ServerRoot|ResultKey)\b[^}]*\}\s+from\s+['\"][^'\"]+['\"];?\s*$", re.M),
    re.compile(r"^import\s+\{[^}]*buildKentangEndpoint[^}]*\}\s+from\s+['\"][^'\"]+['\"];?\s*$", re.M),
)
_RELATIVE_IMPORT = re.compile(r"(from\s+['\"])(\.[^'\"]*?)(['\"])")


def _strip_fetch_helpers(text: str) -> tuple[str, list[str]]:
    """Remove `export async function fetch*Pan(...) { … }` blocks by brace matching."""
    removed: list[str] = []
    pattern = re.compile(r"^export\s+(?:async\s+)?function\s+(fetch\w*Pan)\s*\(", re.M)
    while True:
        match = pattern.search(text)
        if not match:
            return text, removed
        start = match.start()
        brace = text.index("{", match.end() - 1)
        depth, index = 1, brace + 1
        while depth and index < len(text):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
            index += 1
        removed.append(match.group(1))
        text = text[:start] + text[index:].lstrip("\n")


_NAMED_IMPORT = re.compile(r"^import\s+\{\s*([^}]+?)\s*\}\s+from\s+['\"]([^'\"]+)['\"];?\s*$", re.M)


def _drop_orphaned_imports(text: str) -> tuple[str, list[str]]:
    """Remove named imports whose symbols are no longer referenced after the fetch strip.

    Stripping `fetch*Pan` orphans its network-layer helpers (e.g. `cachedKentangFetch` from
    `utils/kentangCache`). Leaving the import behind makes the module unloadable headless — the
    referenced file simply is not in the vendor tree. Keyed on *actual usage* rather than a filename
    denylist, so the next upstream helper is handled without editing this script.
    """
    notes: list[str] = []
    for match in list(_NAMED_IMPORT.finditer(text)):
        symbols = [s.strip().split(" as ")[-1].strip() for s in match.group(1).split(",") if s.strip()]
        body = text[: match.start()] + text[match.end() :]
        if symbols and not any(re.search(rf"\b{re.escape(sym)}\b", body) for sym in symbols):
            text = body
            notes.append(f"dropped orphaned import {{{', '.join(symbols)}}}")
    return text, notes


def transform(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    for pattern in _DROP_IMPORT_PATTERNS:
        text, count = pattern.subn("", text)
        if count:
            notes.append(f"dropped {count} backend import(s)")
    text, removed = _strip_fetch_helpers(text)
    if removed:
        notes.append("stripped " + ", ".join(removed))
    text, orphan_notes = _drop_orphaned_imports(text)
    notes.extend(orphan_notes)

    def add_suffix(match: re.Match[str]) -> str:
        target = match.group(2)
        if target.endswith((".js", ".json", ".mjs")):
            return match.group(0)
        return f"{match.group(1)}{target}.js{match.group(3)}"

    text, count = _RELATIVE_IMPORT.subn(add_suffix, text)
    if count:
        notes.append(f"suffixed {count} relative import(s)")
    return text, notes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream_src", type=Path, help="upstream astrostudyui/src root")
    parser.add_argument("files", nargs="+", help="paths relative to the upstream src root")
    parser.add_argument("--vendor-subdir", default=None, help="override the vendor destination subdir")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    for rel in args.files:
        source = args.upstream_src / rel
        if not source.is_file():
            raise SystemExit(f"upstream file not found: {source}")
        subdir = args.vendor_subdir or Path(rel).parent.name
        target = VENDOR_ROOT / subdir / Path(rel).name
        new_text, notes = transform(source.read_text(encoding="utf-8"))
        old_text = target.read_text(encoding="utf-8") if target.is_file() else ""
        status = "unchanged" if old_text == new_text else ("new" if not old_text else "updated")
        delta = len(new_text.splitlines()) - len(old_text.splitlines())
        print(f"{rel} → {target.relative_to(REPO_ROOT)}: {status} ({delta:+d} lines) [{'; '.join(notes) or 'verbatim'}]")
        if not args.check and status != "unchanged":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_text, encoding="utf-8")


if __name__ == "__main__":
    main()
