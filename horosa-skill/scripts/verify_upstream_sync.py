#!/usr/bin/env python
"""Upstream-sync guard — assert the **vendored** trees still match the **upstream HEAD**.

The gap this closes: every pre-existing guard compares the skill against its own vendored copy, so once
`vendor/runtime-source` falls behind upstream, all of them stay green forever. That is exactly how the
mirror constant sat at 48 while upstream shipped 50 — no machine signal, found only by hand-diffing.
Both vendor trees are gitignored, and `horosa-core-js/src/vendor` (which IS tracked) had no guard at all.

Checks (upstream located via `$HOROSA_SOURCE_ROOT`, the same env the sync script uses):

1. **Contract currency** — upstream `AI_EXPORT_SETTINGS_VERSION` == the skill's
   `MIRRORED_UPSTREAM_AIEXPORT_VERSION`. This is the one assertion that goes red the moment upstream
   ships a new export contract.
2. **Vendored sentinels** — sha256 equality for the high-signal files the sync script copies (the export
   contract itself plus the modules whose absence/staleness produced past incidents).
3. **core-js vendor drift** — every `horosa-core-js/src/vendor/**/*.js` is matched to an upstream file by
   basename and compared; unmatched files are reported (not failed) so bespoke shims stay legal.

No upstream checkout (GitHub CI): print a `skipped` record + `::notice` and exit 0 — visibly skipped, never
a fake green. `--require-upstream` (release pipeline) turns absence into a hard failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _upstream_preset import read_settings_version  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_ROOT = REPO_ROOT / "horosa-skill"
VENDOR_ROOT = REPO_ROOT / "vendor/runtime-source"
CORE_JS_VENDOR = PKG_ROOT / "horosa-core-js/src/vendor"
SYNC_STATE = PKG_ROOT / "contracts" / "vendor_sync_state.json"

# 高信号哨兵：全是曾经出过事故或承载契约的文件（逐字节比对，便宜且致命）。
SENTINELS = [
    "Horosa-Web/astrostudyui/src/utils/aiExport.js",
    "Horosa-Web/vendor/kin_year_domain.py",
    "Horosa-Web/astropy/astrostudy/geomancy/data/ifa_odu.json",
    "Horosa-Web/astropy/websrv/webchartsrv.py",
    "Horosa-Web/astropy/websrv/kentang/registry.py",
    "Horosa-Web/astropy/astrostudy/perpredict.py",
    "Horosa-Web/astropy/astrostudy/perchart.py",
]
# core-js vendor 的上游搜索根（按 basename 建索引）
CORE_JS_UPSTREAM_ROOTS = ["Horosa-Web/astrostudyui/src"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _skill_mirror_version() -> int:
    sys.path.insert(0, str(PKG_ROOT / "src"))
    from horosa_skill.exports.registry import MIRRORED_UPSTREAM_AIEXPORT_VERSION

    return int(MIRRORED_UPSTREAM_AIEXPORT_VERSION)


def _package_version() -> str:
    sys.path.insert(0, str(PKG_ROOT / "src"))
    from horosa_skill import __version__

    return str(__version__)


def _report_state_currency() -> None:
    """跨树比对做不了时的替代信号：上一次真跑记录的 mirror 版本还等于现在的常量吗？

    `contracts/vendor_sync_state.json` 只由带 `--write-state` 的**真**跨树比对写入。所以它记的
    `skill_mirrored_version` 一旦落后于当前 `MIRRORED_UPSTREAM_AIEXPORT_VERSION`，就说明镜像版本
    在没有任何跨树核对的情况下往前走过——v0.24.0 记 48、而 v0.25.0 起常量已是 50，正是这个形状。
    """
    if not SYNC_STATE.is_file():
        print(f"::warning::upstream-sync: {SYNC_STATE.name} missing — cross-tree sync has never been recorded")
        return
    state = json.loads(SYNC_STATE.read_text(encoding="utf-8"))
    recorded = state.get("skill_mirrored_version")
    current = _skill_mirror_version()
    at_version = state.get("upstream_checked_at_package_version", "unknown")
    if recorded == current:
        print(f"upstream-sync: state current (mirror v{current}, last cross-tree check at package {at_version})")
        return
    # `::warning::` 是单行命令——消息里带换行会被 GitHub 在第一个 \n 处截断，注解结尾留个悬空冒号。
    # 所以补救命令写在同一行；多行的详细说明另外用普通 log 输出。
    print(
        f"::warning::upstream-sync: vendor_sync_state.json is STALE — it records "
        f"skill_mirrored_version={recorded} (checked at package {at_version}) but the registry constant is now "
        f"{current}; the mirror moved forward with no cross-tree verification against upstream HEAD. Fix: run "
        f"`HOROSA_SOURCE_ROOT=<Horosa-Public> uv run python scripts/preflight_release.py` on the maintenance box."
    )


def _upstream_basename_index(upstream: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for rel_root in CORE_JS_UPSTREAM_ROOTS:
        root = upstream / rel_root
        if not root.is_dir():
            continue
        for path in root.rglob("*.js"):
            index.setdefault(path.name, []).append(path)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-upstream", action="store_true")
    parser.add_argument("--write-state", action="store_true", help="record the compared upstream in contracts/")
    args = parser.parse_args()

    root = os.environ.get("HOROSA_SOURCE_ROOT")
    upstream = Path(root).expanduser().resolve() if root else None
    if upstream is None or not (upstream / "Horosa-Web").is_dir():
        message = "HOROSA_SOURCE_ROOT unset or does not contain Horosa-Web/"
        if args.require_upstream:
            raise SystemExit(f"upstream-sync: FAIL — {message} (release pipeline requires the upstream checkout).")
        # 没有上游树时也**不再什么都不断言**：跨树比对做不了，但「上一次真跑距今多远」是仓内可判的。
        # 这条以前是纯 skip，于是这个守卫在任何自动化环境里都从未断言过任何东西——release.yml 里那次
        # 带 --require-upstream 的调用从 v0.9.2 起 20 次全部排队 24h 后被取消（无 self-hosted runner）。
        print(json.dumps({"cross_tree": "skipped", "reason": message}, ensure_ascii=False))
        print(f"::notice::upstream-sync cross-tree check skipped — {message}")
        _report_state_currency()
        return

    failures: list[str] = []
    upstream_aiexport = upstream / SENTINELS[0]
    if not upstream_aiexport.is_file():
        raise SystemExit(f"upstream-sync: FAIL — upstream aiExport.js not found at {upstream_aiexport}")

    # 1. contract currency
    upstream_version = read_settings_version(upstream_aiexport.read_text(encoding="utf-8", errors="replace"))
    mirrored = _skill_mirror_version()
    if upstream_version != mirrored:
        failures.append(
            f"export contract behind upstream: upstream AI_EXPORT_SETTINGS_VERSION={upstream_version} != "
            f"skill MIRRORED_UPSTREAM_AIEXPORT_VERSION={mirrored} — re-sync both vendor trees and backfill "
            "the new sections (docs/LESSONS.md 记的正是这条静默漂移)"
        )

    # 2. vendored sentinels
    sentinel_drift: list[str] = []
    for rel in SENTINELS:
        up_path, vendored_path = upstream / rel, VENDOR_ROOT / rel
        if not up_path.is_file():
            sentinel_drift.append(f"{rel}: missing upstream (renamed/removed?)")
        elif not vendored_path.is_file():
            sentinel_drift.append(f"{rel}: missing in vendor/runtime-source (sync dropped it)")
        elif _sha256(up_path) != _sha256(vendored_path):
            sentinel_drift.append(f"{rel}: vendored copy differs from upstream")
    if sentinel_drift:
        failures.append("vendored sentinels drifted:\n    - " + "\n    - ".join(sentinel_drift))

    # 3. core-js vendor drift
    index = _upstream_basename_index(upstream)
    drifted: list[str] = []
    unmatched: list[str] = []
    compared = 0
    if CORE_JS_VENDOR.is_dir():
        for path in sorted(CORE_JS_VENDOR.rglob("*.js")):
            candidates = index.get(path.name, [])
            if len(candidates) != 1:
                unmatched.append(f"{path.relative_to(CORE_JS_VENDOR)} ({len(candidates)} upstream matches)")
                continue
            compared += 1
            if _sha256(path) != _sha256(candidates[0]):
                drifted.append(str(path.relative_to(CORE_JS_VENDOR)))
    if drifted:
        failures.append(
            f"core-js vendored JS differs from upstream ({len(drifted)}):\n    - " + "\n    - ".join(drifted[:20])
            + ("\n    - …" if len(drifted) > 20 else "")
        )

    if args.write_state:
        SYNC_STATE.parent.mkdir(parents=True, exist_ok=True)
        SYNC_STATE.write_text(
            json.dumps(
                {
                    "_comment": "最近一次**真**跨树核对（vendored ↔ 上游 HEAD）的状态；只由带 "
                    "--write-state 的真跑写入。`skill_mirrored_version` 落后于 registry 常量 = "
                    "镜像在无跨树核对的情况下前进过（见 verify_upstream_sync._report_state_currency）。",
                    "upstream_aiexport_settings_version": upstream_version,
                    "skill_mirrored_version": mirrored,
                    "core_js_files_compared": compared,
                    "upstream_checked_at_package_version": _package_version(),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    if failures:
        raise SystemExit("upstream-sync: FAIL\n- " + "\n- ".join(failures))
    print(
        f"upstream-sync: ok (upstream aiExport v{upstream_version} == mirror; {len(SENTINELS)} sentinels identical; "
        f"{compared} core-js files identical, {len(unmatched)} unmatched/bespoke)"
    )


if __name__ == "__main__":
    main()
