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
RECONFIGURE = 'reconfigure(encoding="utf-8"'


def scripts_printing_non_ascii_without_utf8_stdio(sources: dict[str, str]) -> list[str]:
    return sorted(name for name, text in sources.items() if NON_ASCII_PRINT.search(text) and RECONFIGURE not in text)


def test_every_script_that_prints_non_ascii_forces_utf8_stdio() -> None:
    sources = {p.name: p.read_text(encoding="utf-8") for p in SCRIPTS.glob("*.py")}
    assert scripts_printing_non_ascii_without_utf8_stdio(sources) == []


def test_guard_catches_a_script_without_the_reconfigure() -> None:
    bad = 'import sys\nprint("完成")\n'
    good = 'import sys\nsys.stdout.reconfigure(encoding="utf-8", errors="replace")\nprint("完成")\n'
    ascii_only = 'print("done")\n'
    assert scripts_printing_non_ascii_without_utf8_stdio({"bad.py": bad, "good.py": good, "ascii.py": ascii_only}) == ["bad.py"]


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
