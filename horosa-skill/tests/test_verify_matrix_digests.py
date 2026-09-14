"""publish 前字节一致性闸的孪生测试（v0.38.1 R5）：负向对照 = sha 不一致 / 少一条 lane / lane 没记 sha。"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("verify_matrix_digests", PKG_ROOT / "scripts" / "verify_matrix_digests.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

DARWIN = "horosa-runtime-darwin-arm64-v0.38.1.tar.gz"
WIN = "horosa-runtime-win32-x64-v0.38.1.zip"
SHA_D, SHA_W = "a" * 64, "b" * 64


def _lanes(tmp_path: Path, reports: dict[str, dict]) -> Path:
    root = tmp_path / "lanes"
    for lane, report in reports.items():
        (root / lane).mkdir(parents=True)
        (root / lane / "lane-report.json").write_text(json.dumps(report), encoding="utf-8")
    return root


def _report(name: str, sha: str, ok: bool = True) -> dict:
    return {"ok": ok, "installed_archive_name": name, "installed_archive_sha256": sha}


def test_parsers_read_the_api_digest_lines_and_sha256sums() -> None:
    assert mod.parse_digests(f"{DARWIN} sha256:{SHA_D}\nnotes.txt \nx y z\n") == {DARWIN: SHA_D}
    assert mod.parse_sums(f"{SHA_W}  {WIN}\n{SHA_D} *{DARWIN}\n") == {WIN: SHA_W, DARWIN: SHA_D}


def test_three_matching_lanes_pass(tmp_path: Path) -> None:
    lanes = mod.lane_evidence(_lanes(tmp_path, {
        "runtime-matrix-darwin-arm64": _report(DARWIN, SHA_D),
        "runtime-matrix-win32-x64": _report(WIN, SHA_W),
        "runtime-matrix-win32-arm64": _report(WIN, SHA_W),
    }))
    assert mod.check(lanes, {DARWIN: SHA_D, WIN: SHA_W}, {}, expect_lanes=3) == []


def test_a_lane_that_installed_other_bytes_blocks_the_flip(tmp_path: Path) -> None:
    lanes = mod.lane_evidence(_lanes(tmp_path, {
        "runtime-matrix-darwin-arm64": _report(DARWIN, SHA_D),
        "runtime-matrix-win32-x64": _report(WIN, "c" * 64),
        "runtime-matrix-win32-arm64": _report(WIN, SHA_W),
    }))
    problems = mod.check(lanes, {DARWIN: SHA_D, WIN: SHA_W}, {}, expect_lanes=3)
    assert len(problems) == 1 and "win32-x64" in problems[0] and "did not test the bytes" in problems[0]


def test_missing_lane_or_missing_evidence_blocks_the_flip(tmp_path: Path) -> None:
    two = mod.lane_evidence(_lanes(tmp_path, {
        "runtime-matrix-darwin-arm64": _report(DARWIN, SHA_D),
        "runtime-matrix-win32-x64": _report(WIN, SHA_W),
    }))
    assert any("expected evidence from 3 lanes" in p for p in mod.check(two, {DARWIN: SHA_D, WIN: SHA_W}, {}, expect_lanes=3))
    blank = mod.lane_evidence(_lanes(tmp_path / "b", {"runtime-matrix-darwin-arm64": {"ok": True}}))
    assert any("no installed_archive_name" in p for p in mod.check(blank, {}, {}, expect_lanes=1))
    failed = mod.lane_evidence(_lanes(tmp_path / "c", {"runtime-matrix-darwin-arm64": _report(DARWIN, SHA_D, ok=False)}))
    assert any("ok=False" in p for p in mod.check(failed, {DARWIN: SHA_D}, {}, expect_lanes=1))


def test_sha256sums_is_the_fallback_when_the_api_has_no_digest(tmp_path: Path) -> None:
    lanes = mod.lane_evidence(_lanes(tmp_path, {"runtime-matrix-darwin-arm64": _report(DARWIN, SHA_D)}))
    assert mod.check(lanes, {}, {DARWIN: SHA_D}, expect_lanes=1) == []
    assert any("neither an asset digest nor a SHA256SUMS line" in p for p in mod.check(lanes, {}, {}, expect_lanes=1))
