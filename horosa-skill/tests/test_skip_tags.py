"""Every skip reason in the suite carries a tag (tests/skips.py) — checked statically and at run time.

The run-time hook only sees skips that fire on *this* machine; a Windows-only skip never fires on the Linux CI job, so
an untagged one there would surface first on a release lane. The AST scan below checks every literal skip reason in
`tests/` wherever it would fire. Reasons computed at run time (`_runtime_skip_reason()`) are covered by the hook.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import skips

TESTS = Path(__file__).resolve().parent
_SKIP_CALLS = ("pytest.skip", "pytest.mark.skip", "pytest.mark.skipif", "pytest.importorskip")


def _first_text(node: ast.expr, constants: dict[str, ast.expr]) -> str | None:
    """The leading literal text of a reason expression, or None when it is computed at run time."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        head = node.values[0] if node.values else None
        return head.value if isinstance(head, ast.Constant) else ""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _first_text(node.left, constants)
    if isinstance(node, ast.Name) and node.id in constants:
        return _first_text(constants[node.id], constants)
    if isinstance(node, ast.Name) and node.id == "UPSTREAM_REASON":
        return skips.UPSTREAM_REASON
    if isinstance(node, ast.IfExp):
        body, orelse = _first_text(node.body, constants), _first_text(node.orelse, constants)
        return body if body is not None and (orelse is None or skips.tag_of(body) is None) else orelse
    return None


def skip_reason_problems(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constants = {
        target.id: node.value for node in tree.body if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
    }
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or ast.unparse(node.func) not in _SKIP_CALLS:
            continue
        name = ast.unparse(node.func)
        reason = next((kw.value for kw in node.keywords if kw.arg == "reason"), None)
        if reason is None and name in {"pytest.skip", "pytest.mark.skip"} and node.args:
            reason = node.args[0]
        where = f"{path.name}:{node.lineno}"
        if reason is None:
            problems.append(f"{where}: {name} without a reason")
            continue
        text = _first_text(reason, constants)
        if text is None:
            continue  # computed at run time: the conftest hook checks it when it fires
        if skips.tag_of(text) is None:
            problems.append(f"{where}: {text[:70]!r}")
    return problems


def test_every_literal_skip_reason_is_tagged() -> None:
    problems = [p for path in sorted(TESTS.glob("test_*.py")) for p in skip_reason_problems(path)]
    assert problems == [], "untagged skip reasons (prefix one of [" + "] [".join(skips.TAGS) + "]):\n" + "\n".join(problems)


def test_the_scan_sees_each_spelling(tmp_path: Path) -> None:
    """负向对照：每种写法各一条没标签的，扫描都要点名。"""
    probe = tmp_path / "test_probe.py"
    probe.write_text(
        "import pytest\nREASON = 'needs a thing'\n"
        "a = pytest.mark.skipif(True, reason='no tag')\n"
        "b = pytest.mark.skipif(True, reason=REASON)\n"
        "def test_x():\n    pytest.skip(f'{1} later')\n"
        "def test_y():\n    pytest.importorskip('numpy')\n"
        "c = pytest.mark.skipif(True, reason='[host] fine')\n",
        encoding="utf-8",
    )
    problems = skip_reason_problems(probe)
    assert [p.split(":")[1].split(" ")[0] for p in problems] == ["3", "4", "6", "8"], problems


def test_an_untagged_skip_fails_the_run_and_tagged_ones_are_counted(tmp_path: Path) -> None:
    """The run-time hook, loaded as a plugin into a throwaway pytest run."""
    (tmp_path / "test_probe.py").write_text(
        "import pytest\n"
        "def test_untagged():\n    pytest.skip('backend unavailable')\n"
        "@pytest.mark.skipif(True, reason='[platform] only on Windows')\n"
        "def test_platform():\n    pass\n"
        "@pytest.mark.skipif(True, reason='[upstream-checkout] HOROSA_SOURCE_ROOT not set')\n"
        "def test_upstream():\n    pass\n",
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(TESTS), os.environ.get("PYTHONPATH", "")])}
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "skips", "--rootdir", str(tmp_path),
         "-c", os.devnull, str(tmp_path / "test_probe.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(tmp_path), timeout=120,
    )
    assert done.returncode == 1, done.stdout[-2000:]
    assert "untagged skip: 'backend unavailable'" in done.stdout
    assert "1 failed, 2 skipped" in done.stdout
    assert "skipped by reason: platform 1, upstream-checkout 1" in done.stdout
