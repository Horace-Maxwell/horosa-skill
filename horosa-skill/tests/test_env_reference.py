"""`docs/ENV_VARS.md` 由注册表生成、不许漂（docs/LESSONS.md v0.50.0-dev「环境变量文档只列了一小半」）。"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from horosa_skill.config import ENV_FLAG_REGISTRY
from horosa_skill.env_docs import ENV_FLAG_DOCS

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent


def test_every_registered_variable_has_a_description() -> None:
    assert sorted(set(ENV_FLAG_REGISTRY) - set(ENV_FLAG_DOCS)) == []
    assert sorted(set(ENV_FLAG_DOCS) - set(ENV_FLAG_REGISTRY)) == []
    assert all(text.strip() and "\n" not in text for text in ENV_FLAG_DOCS.values())


def test_the_reference_document_is_the_current_render() -> None:
    result = subprocess.run(
        [sys.executable, str(PKG_ROOT / "scripts" / "gen_env_reference.py"), "--check"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_the_document_lists_every_variable_once() -> None:
    text = (REPO_ROOT / "docs" / "ENV_VARS.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| `(HOROSA_[A-Z0-9_]+)` \|", text, flags=re.M)
    assert sorted(rows) == sorted(ENV_FLAG_REGISTRY)


def test_user_docs_only_name_registered_variables() -> None:
    """文档里出现的 HOROSA_* 名字必须是注册表里的（v0.47.2-dev 曾把并发上限的变量名写丢了末尾的 `_TOOLS`）。"""
    docs = [REPO_ROOT / "README.md", REPO_ROOT / "README_EN.md", PKG_ROOT / "README.md",
            *sorted((REPO_ROOT / "docs").glob("*.md"))]
    known = set(ENV_FLAG_REGISTRY)
    strays: dict[str, set[str]] = {}
    for doc in docs:
        if doc.name in {"LESSONS.md"}:  # 台账记的是历史，包括写错过的名字
            continue
        text = doc.read_text(encoding="utf-8")
        for match in re.finditer(r"HOROSA_[A-Z0-9_]*[A-Z0-9]", text):
            name = match.group(0)
            if text[match.end():match.end() + 2] == "_*":  # `HOROSA_IO_AUDIT_*/` 是目录名模式，不是变量
                continue
            if name not in known and not name.startswith("HOROSA_TYPO"):
                strays.setdefault(doc.name, set()).add(name)
    assert strays == {}
