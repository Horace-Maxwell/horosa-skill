"""contracts/runtime_python_lock.json + its guard (v0.38.0 A1): the derived payload's dep set is a pure
function of the seed — nothing added, nothing excluded leaks in, every upstream name classified."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("verify_runtime_python_lock", PKG_ROOT / "scripts" / "verify_runtime_python_lock.py")
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

LOCK = json.loads((PKG_ROOT / "contracts" / "runtime_python_lock.json").read_text(encoding="utf-8"))
REQUIREMENTS = (PKG_ROOT / "contracts" / "upstream_python_requirements.txt").read_text(encoding="utf-8")
LESSONS = (PKG_ROOT.parent / "docs" / "LESSONS.md").read_text(encoding="utf-8")


def test_committed_lock_is_clean() -> None:
    assert guard.audit_lock(LOCK, REQUIREMENTS, LESSONS) == []
    assert LOCK["python"] == "3.12"
    assert len(LOCK["native"]) == 19 and len(LOCK["pure"]) == 76
    assert LOCK["wheel_sources"]["win32-x64"]["pyswisseph"] == "sdist"
    assert LOCK["wheel_sources"]["win32-x64"]["sxtwl"] == "sdist"
    assert LOCK["wheel_sources"]["win32-x64"]["numpy"].endswith("win_amd64.whl")


def test_scipy_and_plotly_can_never_enter_the_dep_set() -> None:
    """Negative control: the size red line is a machine rule, not a memory."""
    leaked = json.loads(json.dumps(LOCK))
    leaked["pure"].append("scipy==1.17.1")
    errors = guard.audit_lock(leaked, REQUIREMENTS, LESSONS)
    assert any("leaked" in e and "scipy" in e for e in errors)
    leaked = json.loads(json.dumps(LOCK))
    leaked["native"].append("plotly==6.0.0")
    assert any("plotly" in e for e in guard.audit_lock(leaked, REQUIREMENTS, LESSONS))


def test_an_unclassified_upstream_requirement_is_caught() -> None:
    errors = guard.audit_lock(LOCK, REQUIREMENTS + "\nsomething-new>=1\n", LESSONS)
    assert any("something-new" in e for e in errors)


def test_platform_override_needs_a_lessons_entry() -> None:
    lock = json.loads(json.dumps(LOCK))
    lock["platform_overrides"]["win32-x64"]["numpy"] = "9.9.9"
    assert any("platform_overrides" in e for e in guard.audit_lock(lock, REQUIREMENTS, LESSONS))
    assert guard.audit_lock(lock, REQUIREMENTS, LESSONS + "\nnumpy 9.9.9 override because …\n") == []


def test_missing_wheel_verdict_is_caught() -> None:
    lock = json.loads(json.dumps(LOCK))
    del lock["wheel_sources"]["win32-x64"]["numpy"]
    assert any("wheel_sources" in e and "numpy" in e for e in guard.audit_lock(lock, REQUIREMENTS, LESSONS))


def test_requirement_names_strip_specifiers_and_comments() -> None:
    assert guard.requirement_names("# c\nnumpy==2.4.2\npyswisseph>=2.10,<3\nopencc-python-reimplemented>=0.1.7 # x\n") == [
        "numpy", "pyswisseph", "opencc-python-reimplemented"]
