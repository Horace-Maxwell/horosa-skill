"""Pre-tag release gate — run this on a box that HAS the upstream Horosa-Public checkout.

Why this exists as a *local* script instead of a CI job: the two cross-tree checks below need both
the vendored trees and upstream HEAD in the same place, and upstream only lives on the maintainer's
machine. The release workflow that used to own them (`.github/workflows/release.yml`) is
`runs-on: self-hosted`, and the repo has **zero** self-hosted runners registered — every one of the
20 tag-triggered runs from v0.9.2 through v0.25.0 sat queued for 24h and was auto-cancelled without
executing a single step. So those gates were never real. Making them a documented, one-command local
step is the honest version: it can actually run where the data is.

Usage (mac maintenance box):

    HOROSA_SOURCE_ROOT=/Users/horacedong/Desktop/Horosa-Public \
        uv run python scripts/preflight_release.py

Exits non-zero on the first failing gate. On success it rewrites
`contracts/upstream_provenance.json`, so the resulting diff is the git-visible proof that the
cross-tree comparison actually happened at this version — commit it with the release.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]

# (label, argv, blocking)：blocking=False 的闸失败只警告，不阻止打 tag。
GATES: tuple[tuple[str, list[str], bool], ...] = (
    (
        "upstream sync (contract version + sentinel sha256 + core-js per-file)",
        ["scripts/verify_upstream_sync.py", "--require-upstream", "--write-state"],
        True,
    ),
    (
        "export-section debt ratchet against upstream",
        ["scripts/verify_export_section_baseline.py", "--source", "upstream", "--require-upstream"],
        True,
    ),
    # ⚠️ 打包输入闸：mac 维护机本来就没有 runtime/windows 与 prepareruntime（它们只在 Windows
    # 构建机上），所以它在 mac 上恒红。打 tag 本身不产出包（发布是另起 workflow / 本机构建，
    # Windows 半由 sync_windows_release.py --upload 另传），因此这一闸只**警告**、不拦。
    ("vendored runtime inputs", ["scripts/verify_vendor_runtime_sources.py"], False),
    ("export-contract mirror", ["scripts/verify_export_contract_mirror.py"], True),
    ("docs sync", ["scripts/verify_docs_sync.py"], True),
    ("runtime-builder parity", ["scripts/verify_builder_parity.py"], True),
)


def main() -> int:
    source_root = os.environ.get("HOROSA_SOURCE_ROOT")
    if not source_root or not (Path(source_root).expanduser() / "Horosa-Web").is_dir():
        print(
            "preflight: FAIL — HOROSA_SOURCE_ROOT must point at a Horosa-Public checkout containing "
            "Horosa-Web/.\nThat is the whole point of this script: without upstream, the two cross-tree "
            "gates cannot assert anything and you are back to the silent-drift failure mode.",
            file=sys.stderr,
        )
        return 2

    failed: list[str] = []
    warned: list[str] = []
    for label, argv, blocking in GATES:
        print(f"\n=== {label} ===", flush=True)
        result = subprocess.run([sys.executable, *argv], cwd=PKG_ROOT)
        if result.returncode != 0:
            (failed if blocking else warned).append(label)

    print()
    for label in warned:
        print(f"::warning::preflight: {label} 未通过（非阻断）—— 该闸的输入只在 Windows 构建机上；"
              f"发布 Windows 半时由 sync_windows_release.py --upload 负责，判据是它 --check 的 [GAP]/[OK]。")
    if failed:
        print("preflight: FAIL — do not tag. Failing gates:", file=sys.stderr)
        for label in failed:
            print(f"  - {label}", file=sys.stderr)
        return 1
    print(
        "preflight: ok — all gates green. `contracts/upstream_provenance.json` was rewritten; commit it "
        "with the release so the cross-tree check leaves a git trace."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
