from __future__ import annotations

import argparse
import json
from importlib.resources import files
from pathlib import Path
from typing import Any
from datetime import datetime, timezone


def _bundle_path(name: str):
    return files("horosa_skill.knowledge.data").joinpath(name)


def _read_bundle(name: str) -> dict[str, Any]:
    return json.loads(_bundle_path(name).read_text(encoding="utf-8"))


def _normalize_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(normalized)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def _stable_build_timestamp() -> str:
    bundles = [_read_bundle("astro.json"), _read_bundle("liureng.json"), _read_bundle("qimen.json")]
    generated_times = [bundle.get("generated_at") for bundle in bundles if isinstance(bundle.get("generated_at"), str)]
    if generated_times:
        latest = max(_normalize_timestamp(value) for value in generated_times)
        return latest.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    paths = [_bundle_path("astro.json"), _bundle_path("liureng.json"), _bundle_path("qimen.json")]
    latest = max(Path(path).stat().st_mtime for path in paths)
    return datetime.fromtimestamp(latest, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_index() -> dict[str, Any]:
    astro = _read_bundle("astro.json")
    liureng = _read_bundle("liureng.json")
    qimen = _read_bundle("qimen.json")
    return {
        "schema_version": 1,
        "bundle_version": 1,
        "source": "xingque_hover_docs",
        "build_timestamp": _stable_build_timestamp(),
        "upstream_source_marker": "xingque_hover_docs",
        "domains": [
            {
                "domain": "astro",
                "missing_categories": [],
                "fallback_categories": [],
                "categories": [
                    {"name": key, "count": len(value), "keys_sample": sorted(value)[:20]}
                    for key, value in astro.get("categories", {}).items()
                ],
            },
            {
                "domain": "liureng",
                "missing_categories": [],
                "fallback_categories": [],
                "categories": [
                    {"name": "shen", "count": len(liureng.get("shen_entries", {})), "keys_sample": sorted(liureng.get("shen_entries", {}))[:20]},
                    {"name": "house", "count": len(liureng.get("jiang_info", {})), "keys_sample": sorted(liureng.get("jiang_info", {}))[:20]},
                ],
            },
            {
                "domain": "qimen",
                "missing_categories": [],
                "fallback_categories": [],
                "categories": [
                    {"name": key, "count": len(value), "keys_sample": sorted(value)[:20]}
                    for key, value in qimen.get("categories", {}).items()
                ],
            },
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or check bundled hover knowledge index.")
    parser.add_argument("--output", type=Path, default=Path("src/horosa_skill/knowledge/data/index.json"))
    parser.add_argument("--check", action="store_true", help="Validate the output file instead of overwriting it.")
    args = parser.parse_args()
    index = build_index()
    text = json.dumps(index, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not args.output.is_file():
            raise SystemExit(f"Missing knowledge index: {args.output}")
        existing = args.output.read_text(encoding="utf-8")
        if existing != text:
            raise SystemExit("Knowledge index is out of date.")
        print("knowledge-index: up to date")
        return
    args.output.write_text(text, encoding="utf-8")
    print(f"knowledge-index: wrote {args.output}")


if __name__ == "__main__":
    main()
