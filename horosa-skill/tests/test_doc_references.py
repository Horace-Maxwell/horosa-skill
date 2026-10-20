"""Files and functions the current-truth docs name must exist (v0.41.1).

AGENTS.md once cited `verify_docs_sync.check_client_matrix` as the lock on the README client matrix — the function
had been gone for releases, so the rule read as enforced while nothing enforced it. This scans the docs agents act on
(not docs/LESSONS.md, which is history by design) for backticked test / script / source / contract paths, workflow
names and `check_*` / `verify_*` names, and fails on any that does not resolve.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent
DOCS = ["AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", "README.md", "README_EN.md"]
# Named on purpose as history: the old self-hosted release workflow, removed in v0.38.0 (AGENTS §7 explains why).
HISTORICAL = {"release.yml"}
_TICKED = re.compile(r"`([^`\s]+)`")
_PATH = re.compile(r"(horosa-skill/)?(tests|scripts|src/horosa_skill|contracts)/[\w./-]+\.(py|sh|ps1|json|mjs|js)")
_FUNC = re.compile(r"`(?:[\w.]+\.)?((?:check|verify)_[a-z_0-9]+)(?:\(\))?`")


def _doc_paths() -> list[Path]:
    docs = [REPO_ROOT / name for name in DOCS]
    docs += [p for p in sorted((REPO_ROOT / "docs").glob("*.md")) if p.name != "LESSONS.md"]
    return [p for p in docs if p.is_file()]


def _known_basenames() -> set[str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    return {line.rsplit("/", 1)[-1] for line in out.splitlines()}


def _known_functions() -> set[str]:
    names: set[str] = set()
    for root in ("scripts", "src", "tests"):
        for path in (PKG_ROOT / root).rglob("*.py"):
            names |= set(re.findall(r"^\s*def (\w+)", path.read_text(encoding="utf-8"), re.M))
    return names


def dangling_references(text: str, basenames: set[str], functions: set[str]) -> list[str]:
    bad = []
    for match in _TICKED.finditer(text):
        ref = match.group(1).split("::")[0].rstrip(",;:")
        if _PATH.fullmatch(ref):
            if not ((PKG_ROOT / ref.removeprefix("horosa-skill/")).exists() or (REPO_ROOT / ref).exists()):
                bad.append(ref)
        elif re.fullmatch(r"(\.github/workflows/)?[\w-]+\.yml", ref):
            if ref.rsplit("/", 1)[-1] not in basenames | HISTORICAL:
                bad.append(ref)
        elif re.fullmatch(r"test_\w+\.py", ref) and not (PKG_ROOT / "tests" / ref).exists():
            bad.append(ref)
    for match in _FUNC.finditer(text):
        name = match.group(1)
        if name not in functions and not (PKG_ROOT / "scripts" / f"{name}.py").exists():
            bad.append(match.group(0).strip("`"))
    return bad


def test_current_docs_only_name_things_that_exist() -> None:
    basenames, functions = _known_basenames(), _known_functions()
    problems = {p.relative_to(REPO_ROOT).as_posix(): dangling_references(p.read_text(encoding="utf-8"), basenames, functions)
                for p in _doc_paths()}
    assert {k: v for k, v in problems.items() if v} == {}


def test_the_scan_flags_a_vanished_test_script_workflow_and_check() -> None:
    text = (
        "lock: `verify_docs_sync.check_client_matrix`; test `tests/test_gone_forever.py`; "
        "script `scripts/verify_gone.py`; workflow `gone-workflow.yml`; ok `tests/test_doc_references.py`"
    )
    assert dangling_references(text, _known_basenames(), _known_functions()) == [
        "tests/test_gone_forever.py", "scripts/verify_gone.py", "gone-workflow.yml", "verify_docs_sync.check_client_matrix",
    ]
