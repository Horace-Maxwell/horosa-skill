"""维护脚本的可移植性（v0.38.1 A16–A18）：

* 打印非 ASCII 的脚本必须把 stdout/stderr 重配成 UTF-8（Windows 控制台默认 cp1252/cp936 → UnicodeEncodeError → exit 1）。
* 知识包构建脚本不再写死维护者的本机路径：HOROSA_SOURCE_ROOT 必填。
* 随 wheel 出货的知识包 `source` 是相对上游树的路径。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PKG_ROOT / "scripts"
NON_ASCII_PRINT = re.compile(r"""print\((?:f|rf|fr)?["'][^"']*[^\x00-\x7f]""")
# print()ing *data* serialised with ensure_ascii=False is the other way a script commits to non-ASCII output:
# the literal scan cannot see it (v0.40.0-dev: run_benchmark.py printed a report whose cases carry 休门 / 逆位 and
# died on the Windows maintainer's cp1252 pipe while Linux CI stayed green).
NON_ASCII_DATA = re.compile(r"ensure_ascii\s*=\s*False")
RECONFIGURE = 'reconfigure(encoding="utf-8"'


def prints_non_ascii(text: str) -> bool:
    return bool(NON_ASCII_PRINT.search(text)) or (bool(NON_ASCII_DATA.search(text)) and "print(" in text)


def scripts_printing_non_ascii_without_utf8_stdio(sources: dict[str, str]) -> list[str]:
    return sorted(name for name, text in sources.items() if prints_non_ascii(text) and RECONFIGURE not in text)


def test_every_script_that_prints_non_ascii_forces_utf8_stdio() -> None:
    sources = {p.name: p.read_text(encoding="utf-8") for p in SCRIPTS.glob("*.py")}
    assert scripts_printing_non_ascii_without_utf8_stdio(sources) == []


def test_guard_catches_a_script_without_the_reconfigure() -> None:
    bad = 'import sys\nprint("完成")\n'
    good = 'import sys\nsys.stdout.reconfigure(encoding="utf-8", errors="replace")\nprint("完成")\n'
    ascii_only = 'print("done")\n'
    assert scripts_printing_non_ascii_without_utf8_stdio({"bad.py": bad, "good.py": good, "ascii.py": ascii_only}) == ["bad.py"]


def test_guard_catches_a_script_that_prints_non_ascii_data() -> None:
    """The literal scan is blind to `print(json.dumps(report, ensure_ascii=False))` — the data carries the CJK."""
    data_bad = 'import json\nprint(json.dumps(report, ensure_ascii=False))\n'
    data_good = 'import json, sys\nsys.stdout.reconfigure(encoding="utf-8", errors="replace")\nprint(json.dumps(report, ensure_ascii=False))\n'
    writes_file_only = 'import json\npath.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")\n'
    ascii_json = 'import json\nprint(json.dumps(report))\n'
    found = scripts_printing_non_ascii_without_utf8_stdio(
        {"data_bad.py": data_bad, "data_good.py": data_good, "file_only.py": writes_file_only, "ascii_json.py": ascii_json}
    )
    assert found == ["data_bad.py"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_knowledge_bundle_script_requires_a_source_root() -> None:
    env = {k: v for k, v in os.environ.items() if k != "HOROSA_SOURCE_ROOT"}
    completed = subprocess.run(
        ["node", str(SCRIPTS / "build_hover_knowledge_bundle.mjs")], env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60, check=False,
    )
    assert completed.returncode == 2 and "HOROSA_SOURCE_ROOT" in completed.stderr


def test_knowledge_bundle_script_has_no_hardcoded_home_path() -> None:
    text = (SCRIPTS / "build_hover_knowledge_bundle.mjs").read_text(encoding="utf-8")
    assert "/Users/" not in text and "HOROSA_SOURCE_ROOT" in text


@pytest.mark.parametrize("pack", ["astro", "liureng", "qimen"])
def test_knowledge_pack_sources_are_relative_upstream_paths(pack: str) -> None:
    data = json.loads((PKG_ROOT / "src" / "horosa_skill" / "knowledge" / "data" / f"{pack}.json").read_text(encoding="utf-8"))
    source = str(data.get("source") or "")
    assert source.startswith("Horosa-Web/"), source
    assert not source.startswith("/") and "/Users/" not in source
