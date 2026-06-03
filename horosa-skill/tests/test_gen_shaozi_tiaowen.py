"""Unit test for the 邵子神数 verse-JSON generator (scripts/gen_shaozi_tiaowen.py).

The generator turns the upstream shaozi_tiaowen.csv (header 條文號碼,卦,條文) into the
{tiaowen_id: verse} JSON that 星阙's kinastro shaozi engine loads. This guards the CSV→JSON
mapping (BOM handling, column order, skip-empty) so a malformed regeneration is caught in CI.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_GEN = Path(__file__).parents[1] / "scripts" / "gen_shaozi_tiaowen.py"
_spec = importlib.util.spec_from_file_location("gen_shaozi_tiaowen", _GEN)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def _write_csv(path: Path, rows: list[str]) -> None:
    # leading ﻿ mirrors the BOM on the real CSV's 條文號碼 header
    path.write_text("﻿條文號碼,卦,條文\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_generates_id_to_verse_map(tmp_path) -> None:
    _write_csv(tmp_path / "shaozi_tiaowen.csv", ["1111,乾,子時初刻弟兄稀 妻非趙姓必分離", "1112,履,先天定數可無疑"])
    assert gen.main(["gen", str(tmp_path)]) == 0
    out = json.loads((tmp_path / "shaozi_tiaowen_6144.json").read_text(encoding="utf-8"))
    assert out == {"1111": "子時初刻弟兄稀 妻非趙姓必分離", "1112": "先天定數可無疑"}
    # the id keys must match the engine's f"{1000+n:04d}" 4-digit format
    assert all(len(k) == 4 and k.isdigit() for k in out)


def test_skips_blank_and_short_rows(tmp_path) -> None:
    _write_csv(tmp_path / "shaozi_tiaowen.csv", ["1111,乾,有字", "1112,坤,", "short_row", "1113,屯,也有字"])
    assert gen.main(["gen", str(tmp_path)]) == 0
    out = json.loads((tmp_path / "shaozi_tiaowen_6144.json").read_text(encoding="utf-8"))
    assert out == {"1111": "有字", "1113": "也有字"}  # blank verse + malformed row dropped


def test_no_csv_is_a_noop(tmp_path) -> None:
    assert gen.main(["gen", str(tmp_path)]) == 0  # graceful, no crash
    assert not (tmp_path / "shaozi_tiaowen_6144.json").exists()
