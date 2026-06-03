#!/usr/bin/env python3
"""Generate shaozi_tiaowen_6144.json from the vendored shaozi_tiaowen.csv.

星阙's kinastro/astro/shaozi engine looks up verse text via
`self.tiaowen_db.get(tiaowen_id, "【條文待補充】")`, loading `shaozi_tiaowen_6144.json`
({"1111": "<verse>", ...}). Upstream ships only the CSV (header 條文號碼,卦,條文) and prints
"條文 JSON 不存在" at runtime, so every 邵子神数 reading comes back with placeholder verses. We
generate the JSON from the CSV at PACKAGE time (never modifying the 星阙 tree) so the bundled
offline runtime emits real 邵子神数 判词. Verse ids absent from the CSV still fall back to the
engine's placeholder — harmless and identical to upstream behaviour for those ids.

Usage: gen_shaozi_tiaowen.py <path-to-shaozi/data dir>   (writes shaozi_tiaowen_6144.json there)
Idempotent; a no-op (exit 0) if the CSV is absent.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: gen_shaozi_tiaowen.py <shaozi/data dir>", file=sys.stderr)
        return 2
    data_dir = Path(argv[1])
    csv_path = data_dir / "shaozi_tiaowen.csv"
    json_path = data_dir / "shaozi_tiaowen_6144.json"
    if not csv_path.is_file():
        print(f"[gen-shaozi] CSV not found ({csv_path}); skipping", file=sys.stderr)
        return 0

    db: dict[str, str] = {}
    # utf-8-sig strips the BOM on the 條文號碼 header.
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)  # 條文號碼, 卦, 條文
        for row in reader:
            if len(row) < 3:
                continue
            tiaowen_id = (row[0] or "").strip()
            verse = (row[2] or "").strip()
            if tiaowen_id and verse:
                db[tiaowen_id] = verse

    if not db:
        print(f"[gen-shaozi] CSV parsed 0 verses ({csv_path}); leaving JSON unwritten", file=sys.stderr)
        return 0

    json_path.write_text(json.dumps(db, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"[gen-shaozi] wrote {len(db)} verses -> {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
