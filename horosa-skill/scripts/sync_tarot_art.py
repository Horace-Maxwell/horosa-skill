#!/usr/bin/env python3
"""Copy the 星阙 app's tarot card pictures into the Python package (report spread figures show real card faces).

The app ships them under `Horosa-Web/astrostudyui/public/tarot-art/<deck>/` (RWS 78, TdM / Wirth / Egyptian 22 majors each)
and names the file with `cardImageUrl` (components/tarot/engine/cardArt.js). The report figure runs that same code
(horosa-core-js/app-charts/adapters/tarot.js), so the files are copied byte for byte — no recompression: they are already
~q75 JPEGs at 300 px high (re-encoding saves nothing and would break the byte check against upstream).

    HOROSA_SOURCE_ROOT=/path/to/Horosa-Public uv run python scripts/sync_tarot_art.py          # copy + write manifest
    HOROSA_SOURCE_ROOT=/path/to/Horosa-Public uv run python scripts/sync_tarot_art.py --check  # verify only (exit 1 on drift)

`manifest.json` records the upstream commit and, per file, size / sha256 / pixel dimensions (the figure lays the card out
from them). Provenance of the scans themselves is NOT recorded upstream — see contracts/third_party_facts.json
(`tarot-art.provenance`). `scripts/verify_app_charts_bundle.py` runs the check in preflight.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

PKG_ROOT = Path(__file__).resolve().parents[1]
ART_DIR = PKG_ROOT / "src" / "horosa_skill" / "data" / "tarot-art"
MANIFEST = ART_DIR / "manifest.json"
UPSTREAM_REL = Path("Horosa-Web") / "astrostudyui" / "public" / "tarot-art"
DECKS = ("rws", "tdm", "wirth", "egyptian")


def _jpeg_size(data: bytes) -> tuple[int, int]:
    """(width, height) from the JPEG's SOF marker (stdlib; the files are baseline / progressive JFIF)."""
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        length = int.from_bytes(data[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
        i += 2 + length
    raise ValueError("no SOF marker")


def upstream_files(source_root: Path) -> dict[str, bytes]:
    root = source_root / UPSTREAM_REL
    out: dict[str, bytes] = {}
    for deck in DECKS:
        for path in sorted((root / deck).glob("*.jpg")):
            out[f"{deck}/{path.name}"] = path.read_bytes()
    return out


def build_manifest(files: dict[str, bytes], commit: str | None) -> dict:
    entries = {}
    for rel, data in sorted(files.items()):
        w, h = _jpeg_size(data)
        entries[rel] = {"width": w, "height": h, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return {
        "_comment": "Tarot card pictures copied byte for byte from the pinned Horosa-Public tree (scripts/sync_tarot_art.py). "
                    "Upstream records no source or licence for these scans; see contracts/third_party_facts.json tarot-art.provenance.",
        "upstream_commit": commit,
        "upstream_path": UPSTREAM_REL.as_posix(),
        "files": entries,
    }


def check_package(manifest: dict | None = None) -> list[str]:
    """Package files vs manifest (size, sha256, dimensions) — no upstream needed (tests use this)."""
    manifest = manifest if manifest is not None else json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems: list[str] = []
    listed = manifest.get("files") or {}
    on_disk = {p.relative_to(ART_DIR).as_posix() for p in ART_DIR.glob("*/*.jpg")}
    problems += [f"{rel}: on disk but not in manifest.json" for rel in sorted(on_disk - set(listed))]
    for rel, meta in sorted(listed.items()):
        path = ART_DIR / rel
        if not path.is_file():
            problems.append(f"{rel}: listed in manifest.json but missing")
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != meta.get("sha256") or len(data) != meta.get("bytes"):
            problems.append(f"{rel}: bytes differ from manifest.json")
        elif list(_jpeg_size(data)) != [meta.get("width"), meta.get("height")]:
            problems.append(f"{rel}: dimensions differ from manifest.json")
    return problems


def _commit(source_root: Path) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(source_root), "rev-parse", "HEAD"], capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-root", default=os.environ.get("HOROSA_SOURCE_ROOT"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.source_root or not (Path(args.source_root).expanduser() / UPSTREAM_REL).is_dir():
        print(f"tarot-art: FAIL — --source-root / HOROSA_SOURCE_ROOT must be a Horosa-Public checkout with {UPSTREAM_REL.as_posix()}", file=sys.stderr)
        return 2
    source_root = Path(args.source_root).expanduser()
    files = upstream_files(source_root)
    if not files:
        print("tarot-art: FAIL — no pictures found upstream", file=sys.stderr)
        return 2
    manifest = build_manifest(files, _commit(source_root))
    if args.check:
        committed = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else {}
        problems = check_package(committed) if committed else ["manifest.json missing"]
        if committed.get("files") != manifest["files"]:
            problems.append("manifest.json differs from the upstream pictures — rerun scripts/sync_tarot_art.py and look at the figures")
        if problems:
            print("tarot-art: out of date:\n  " + "\n  ".join(problems), file=sys.stderr)
            return 1
        print(f"tarot-art: up to date ({len(files)} pictures, {sum(len(d) for d in files.values())} bytes)")
        return 0
    for stale in ART_DIR.glob("*/*.jpg"):  # pictures upstream dropped must not linger in the package
        if stale.relative_to(ART_DIR).as_posix() not in files:
            stale.unlink()
    for rel, data in files.items():
        target = ART_DIR / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"tarot-art: wrote {len(files)} pictures ({sum(len(d) for d in files.values())} bytes) + manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
