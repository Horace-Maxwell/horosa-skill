"""sync_windows_release 重写 SHA256SUMS 时保留 .mcpb / .whl 行（v0.38.1 R15）。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("sync_windows_release", PKG_ROOT / "scripts" / "sync_windows_release.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

PREVIOUS = (
    "1111  horosa-runtime-darwin-arm64-v1.tar.gz\n"
    "2222  horosa-runtime-win32-x64-v1.zip\n"
    "3333  horosa-skill-1.mcpb\n"
    "4444  horosa_skill-1-py3-none-any.whl\n"
)


def test_merge_keeps_the_lines_it_did_not_recompute() -> None:
    fresh = ["aaaa  horosa-runtime-darwin-arm64-v1.tar.gz", "bbbb  horosa-runtime-win32-x64-v1.zip"]
    merged = mod.merge_sha256sums(PREVIOUS, fresh, {"horosa-runtime-darwin-arm64-v1.tar.gz", "horosa-runtime-win32-x64-v1.zip"})
    assert merged == ["3333  horosa-skill-1.mcpb", "4444  horosa_skill-1-py3-none-any.whl", *fresh]


def test_merge_with_no_previous_file_is_just_the_fresh_lines() -> None:
    assert mod.merge_sha256sums("", ["aaaa  x.tar.gz"], {"x.tar.gz"}) == ["aaaa  x.tar.gz"]
    assert mod.merge_sha256sums("bad line without hash\n", ["aaaa  x.tar.gz"], {"x.tar.gz"}) == ["aaaa  x.tar.gz"]
