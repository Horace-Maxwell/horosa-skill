"""verify_export_contract_mirror.py runs in CI against the pinned upstream checkout, and still gates the vendored copy at release.

Why (v0.51.0): the guard needed the gitignored vendor/runtime-source, so it ran only at release preflight. The audit's new
skill-side export key `ziwei_rules` (no upstream twin, needs a DIVERGENCE_WHITELIST entry) passed PR #23's CI and all 25
local gates, and first went red at preflight — after the version bump, on the release path. CI already checks out the
public upstream at the contract commit (PF-20, HOROSA_SOURCE_ROOT), which carries the same aiExport.js.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from skips import needs_upstream

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_export_contract_mirror.py"
_spec = importlib.util.spec_from_file_location("verify_export_contract_mirror", _SCRIPT)
mirror = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("verify_export_contract_mirror", mirror)
_spec.loader.exec_module(mirror)

_AIEXPORT = str(mirror.AIEXPORT_RELPATH)


@pytest.fixture
def ci_shape(monkeypatch, tmp_path):
    """No vendored tree (CI): point the vendored path at nothing."""
    monkeypatch.setattr(mirror, "VENDORED_AIEXPORT", tmp_path / "absent" / "aiExport.js")


@needs_upstream(_AIEXPORT)
def test_ci_shape_reads_the_upstream_checkout(ci_shape, capsys) -> None:
    mirror.main([])
    assert "export-contract-mirror: ok (upstream checkout;" in capsys.readouterr().out


@needs_upstream(_AIEXPORT)
def test_ci_shape_catches_an_unwhitelisted_skill_only_key(ci_shape, monkeypatch) -> None:
    """The v0.51.0 miss, replayed in CI shape: without its whitelist entry `ziwei_rules` is reported."""
    monkeypatch.setattr(mirror, "DIVERGENCE_WHITELIST", {k: v for k, v in mirror.DIVERGENCE_WHITELIST.items() if k != "ziwei_rules"})
    with pytest.raises(SystemExit, match=r"ziwei_rules"):
        mirror.main([])


def test_release_gates_still_require_the_vendored_copy(ci_shape, monkeypatch) -> None:
    monkeypatch.setenv("HOROSA_SOURCE_ROOT", str(Path(__file__).resolve().parents[2]))   # present, but not what ships
    with pytest.raises(SystemExit, match=r"--require-vendored"):
        mirror.main(["--require-vendored"])


def test_without_either_tree_it_says_what_to_set(ci_shape, monkeypatch) -> None:
    monkeypatch.delenv("HOROSA_SOURCE_ROOT", raising=False)
    with pytest.raises(SystemExit, match=r"HOROSA_SOURCE_ROOT is not set"):
        mirror.main([])


def test_preflight_passes_require_vendored() -> None:
    """(The Windows build's call is asserted on the recorded command in test_sync_windows_release.py.)"""
    preflight = (Path(__file__).resolve().parents[1] / "scripts" / "preflight_release.py").read_text(encoding="utf-8")
    assert '["scripts/verify_export_contract_mirror.py", "--require-vendored"]' in preflight
