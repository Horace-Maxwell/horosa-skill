#!/usr/bin/env python
"""Upstream-sync guard — assert the **vendored** trees still match the **upstream HEAD**.

The gap this closes: every pre-existing guard compares the skill against its own vendored copy, so once
`vendor/runtime-source` falls behind upstream, all of them stay green forever. That is exactly how the
mirror constant sat at 48 while upstream shipped 50 — no machine signal, found only by hand-diffing.
Both vendor trees are gitignored, and `horosa-core-js/src/vendor` (which IS tracked) had no guard at all.

Checks (upstream located via `$HOROSA_SOURCE_ROOT`, the same env the sync script uses):

0. **Upstream worktree is clean** — every check below reads files *on disk*, so uncommitted edits look
   like upstream drift, and a re-vendor would pull unreviewed work-in-progress into a shipped artifact.
   Provenance records a *commit*, so a dirty tree makes that record incoherent too. Noted locally,
   hard-failed under `--require-upstream`.
1. **Contract currency** — upstream `AI_EXPORT_SETTINGS_VERSION` == the skill's
   `MIRRORED_UPSTREAM_AIEXPORT_VERSION`.
1b. **Technique-key arrival** — upstream's `AI_EXPORT_PRESET_SECTIONS` key set vs the set recorded in
   `contracts/upstream_provenance.json`. ⚠️ This is the only check that can see a new upstream technique:
   upstream deliberately adds keys **without** moving either version gate ("新技法键只加键、两把版本闸恒
   不动", upstream aiExport.js:306), so check 1 is structurally blind to it. `tianxing` (v3.7.0) and
   `qimenzeri` (v3.7.1) both arrived under an unchanged v50 and went unnoticed until v0.26.0.
2. **Vendored sentinels** — sha256 equality for the high-signal files the sync script copies (the export
   contract itself plus the modules whose absence/staleness produced past incidents).
2b. **Vendored runtime subtrees** — every file under the ken-engine / astrostudy / websrv trees compared
   both ways (changed, removed, and *newly added upstream*). Point sentinels can never be complete:
   the v3.7.3 `kintaiyi/jieqi.py` full-year-domain fix sat stale in the vendored tree because none of
   the 7 sentinels lives under a ken engine directory, and verify_vendor_runtime_sources only asserts
   REQUIRED_PATHS *existence*. Exclusions mirror the sync script's, or the guard goes permanently red
   on files it was never meant to copy.
3. **core-js vendor drift** — each `verbatim` entry in `contracts/vendor_manifest.json` is re-rendered
   from upstream through the headless transform plus its declared deviations, and must equal the
   vendored file. `curated`/`bespoke` entries are excluded by design (they have their own assertions in
   `revendor_core_js.py --from-manifest`).
   This deliberately does NOT compare raw bytes against untransformed upstream: every vendored file
   legitimately carries the transform, so a raw compare flags ~half the tree and can never go green —
   and a permanently-red check is one people learn to scroll past.
4. **Provenance staleness** — the recorded upstream commit vs upstream HEAD.

No upstream checkout (GitHub CI): print a `skipped` record + `::notice` and exit 0 — visibly skipped, never
a fake green. `--require-upstream` (release pipeline) turns absence, and a stale provenance record, into a
hard failure.

`--write-state` records the reconciled upstream into `contracts/upstream_provenance.json`. It runs **only
after every check passed**: a provenance record written by a red run launders a failure into a durable
claim of currency, which is strictly worse than having no record (v0.25.0 shipped with exactly that —
`vendor_sync_state.json` claimed "最近一次核对过的上游状态" while the guard was failing).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _upstream_preset import parse_preset_sections, read_settings_version  # noqa: E402
from revendor_core_js import load_manifest, manifest_drift  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_ROOT = REPO_ROOT / "horosa-skill"
VENDOR_ROOT = REPO_ROOT / "vendor/runtime-source"
CORE_JS_VENDOR = PKG_ROOT / "horosa-core-js/src/vendor"
PROVENANCE = PKG_ROOT / "contracts" / "upstream_provenance.json"

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
# 逐文件比对的整棵子树。单点哨兵永远补不全：v0.26.0 审计时 `kintaiyi/jieqi.py` 的**全年份域修复**
# （首版误用 `datetime(year,…)`，域外直接 ValueError 炸掉整个 taiyi/pan）就卡在 vendored 树里，
# 因为 7 个哨兵一个都不在 ken 引擎目录下，而 verify_vendor_runtime_sources 只查 REQUIRED_PATHS 是否存在。
# 子树比对不挑文件，新增/改动/丢失都报。
SENTINEL_TREES = [
    "Horosa-Web/vendor",                    # ken + 神数 引擎（kinqimen/kintaiyi/kinjinkou/…）
    "Horosa-Web/astropy/astrostudy",        # Python 算法本体
    "Horosa-Web/astropy/websrv",            # HTTP 端点层
]
# 与 sync_vendored_runtime_sources.sh 的 RSYNC_FILTERS 及 kinastro 裁剪保持一致——比对口径必须
# 等于同步口径，否则守卫会对着「本就故意没拷」的文件恒红。
TREE_EXCLUDE_DIRS = {
    "__pycache__", ".pytest_cache", ".cache", "_CodeSignature", ".horosa-logs",
    # kinastro 只 vendor 引擎（sync 脚本 :89-90 裁掉这些，含 ~26MB 地理编码库）
    "tools", "ui", "frontend", "docs", "wiki", "examples", "tests", "styles", "scripts",
    ".devcontainer", ".streamlit", ".git", ".github",
}
TREE_EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".map", ".tmp", ".temp", ".pid")


def _tree_files(root: Path) -> dict[str, Path]:
    """Relative-path → file, honouring the sync script's exclusion set."""
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for path in root.rglob("*"):
        if not path.is_file() or path.name.startswith("._") or path.name == ".DS_Store":
            continue
        rel = path.relative_to(root)
        if any(part in TREE_EXCLUDE_DIRS for part in rel.parts):
            continue
        if path.suffix in TREE_EXCLUDE_SUFFIXES:
            continue
        out[rel.as_posix()] = path
    return out


# 上游应用版本的唯一机器可读来源（astrostudyui/package.json 不带版本）。
UPSTREAM_VERSION_MANIFEST = "Horosa_Desktop_Installer/package.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_sha256(root: Path) -> str:
    """Digest over sorted (relpath, filehash) — changes iff the vendored JS tree changes."""
    if not root.is_dir():
        return ""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.js")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(_sha256(path).encode())
    return digest.hexdigest()


def _skill_registered_keys() -> set[str]:
    """Technique keys the skill already registers, mapped into upstream's naming.

    Two keys diverge by name (`wangji`↔`huangji`, `acg`↔`locastro`); that map lives in
    verify_export_contract_mirror.py, which is the guard that owns key-level naming.
    """
    sys.path.insert(0, str(PKG_ROOT / "src"))
    from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS
    from verify_export_contract_mirror import KEY_ALIAS

    keys = set(AI_EXPORT_PRESET_SECTIONS)
    return keys | {KEY_ALIAS.get(k, k) for k in keys}


def _skill_mirror_version() -> int:
    sys.path.insert(0, str(PKG_ROOT / "src"))
    from horosa_skill.exports.registry import MIRRORED_UPSTREAM_AIEXPORT_VERSION

    return int(MIRRORED_UPSTREAM_AIEXPORT_VERSION)


def _git(upstream: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(upstream), *args], capture_output=True, text=True, timeout=30, check=False
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _upstream_app_version(upstream: Path) -> str:
    manifest = upstream / UPSTREAM_VERSION_MANIFEST
    if not manifest.is_file():
        return ""
    try:
        return str(json.loads(manifest.read_text(encoding="utf-8")).get("version", ""))
    except (json.JSONDecodeError, OSError):
        return ""


def load_provenance() -> dict:
    if not PROVENANCE.is_file():
        return {}
    try:
        return json.loads(PROVENANCE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def diff_preset_keys(upstream_keys: set[str], recorded_keys: set[str]) -> tuple[list[str], list[str]]:
    """Return (gained, lost). Split out for direct testing — this is check 1b's whole logic."""
    return sorted(upstream_keys - recorded_keys), sorted(recorded_keys - upstream_keys)

def _package_version() -> str:
    sys.path.insert(0, str(PKG_ROOT / "src"))
    from horosa_skill import __version__

    return str(__version__)


def _report_state_currency() -> None:
    """跨树比对做不了时的替代信号：上一次真跑记录的 mirror 版本还等于现在的常量吗？

    原实现读 `contracts/vendor_sync_state.json`；该文件已被 `upstream_provenance.json` 取代
    （超集：另记上游 commit / 应用版本 / preset 键集 / core-js 树摘要），语义一致地搬过来。
    provenance 只由**全部检查通过**的 `--write-state` 写入，所以它记的 skill_mirrored_version
    一旦落后于当前常量，就说明镜像版本在没有任何跨树核对的情况下往前走过——v0.24.0 记 48、
    而 v0.25.0 起常量已是 50，正是这个形状。
    """
    provenance = load_provenance()
    if not provenance:
        print(f"::warning::upstream-sync: {PROVENANCE.name} missing — cross-tree sync has never been recorded")
        return
    recorded = provenance.get("skill_mirrored_version")
    current = _skill_mirror_version()
    at_sha = (provenance.get("upstream_git_sha") or "unknown")[:12]
    at_version = provenance.get("upstream_app_version", "unknown")
    if recorded == current:
        print(
            f"upstream-sync: state current (mirror v{current}; last cross-tree check against "
            f"upstream {at_version} @ {at_sha})"
        )
        return
    # `::warning::` 是单行命令——消息里带换行会被 GitHub 在第一个 \n 处截断，注解结尾留个悬空冒号。
    # 所以补救命令写在同一行；多行的详细说明另外用普通 log 输出。
    print(
        f"::warning::upstream-sync: {PROVENANCE.name} is STALE — it records "
        f"skill_mirrored_version={recorded} (upstream {at_version} @ {at_sha}) but the registry constant is now "
        f"{current}; the mirror moved forward with no cross-tree verification against upstream HEAD. Fix: run "
        f"`HOROSA_SOURCE_ROOT=<Horosa-Public> uv run python scripts/preflight_release.py` on the maintenance box."
    )




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

    provenance = load_provenance()
    aiexport_text = upstream_aiexport.read_text(encoding="utf-8", errors="replace")

    # 0. upstream worktree cleanliness. Everything below compares against the **files on disk**, so a
    #    maintainer's uncommitted edits read as "upstream drifted" — and worse, a re-vendor would pull
    #    unreviewed work-in-progress into a shipped artifact. Provenance records a *commit*, so a dirty
    #    tree also makes that record incoherent. Report it prominently; hard-fail the release chain.
    dirty = [
        line[3:]
        for line in _git(upstream, "status", "--porcelain", "Horosa-Web/astropy", "Horosa-Web/astrostudyui").splitlines()
        if line.strip()
    ]
    if dirty:
        message = (
            f"upstream worktree has {len(dirty)} uncommitted change(s) — any drift reported below may be "
            f"work-in-progress, not a released upstream change. Vendor from a clean tree:\n    - "
            + "\n    - ".join(dirty[:10])
            + ("\n    - …" if len(dirty) > 10 else "")
        )
        if args.require_upstream:
            failures.append(message)
        else:
            print(f"::notice::upstream-sync — {message}")

    # 1. contract currency
    upstream_version = read_settings_version(aiexport_text)
    mirrored = _skill_mirror_version()
    if upstream_version != mirrored:
        failures.append(
            f"export contract behind upstream: upstream AI_EXPORT_SETTINGS_VERSION={upstream_version} != "
            f"skill MIRRORED_UPSTREAM_AIEXPORT_VERSION={mirrored} — re-sync both vendor trees and backfill "
            "the new sections (docs/LESSONS.md 记的正是这条静默漂移)"
        )

    # 1b. technique-key arrival — the ONLY signal for "upstream shipped a new technique", because the
    #     version gates above deliberately do not move for new keys (upstream aiExport.js:306).
    upstream_keys = set(parse_preset_sections(aiexport_text))
    recorded_keys = set(provenance.get("upstream_preset_keys") or [])
    if recorded_keys:
        # The two directions need different baselines:
        #   gained — recorded ∪ skill-registered. A key the skill already registers is not an unhandled
        #            arrival; folding it in lets the check self-heal on registration while staying loud
        #            for anything genuinely unaddressed.
        #   lost   — recorded ONLY. The skill legitimately carries keys upstream has no counterpart for
        #            (`acg`/`astrodata`/`wangji`, the DIVERGENCE_WHITELIST + alias set); counting those
        #            as "upstream removed it" is a guaranteed false alarm.
        gained, _ = diff_preset_keys(upstream_keys, recorded_keys | _skill_registered_keys())
        _, lost = diff_preset_keys(upstream_keys, recorded_keys)
        if gained:
            failures.append(
                f"upstream gained {len(gained)} technique key(s): {', '.join(gained)} — "
                "AI_EXPORT_SETTINGS_VERSION does NOT move for new keys (upstream aiExport.js:306), so this "
                "is the only signal. Register them (AGENTS §5 布线清单) or, if unavailable on the "
                "open-source stack, add them to the exclusion ledger in docs/LESSONS.md; then re-record "
                "with --write-state."
            )
        if lost:
            failures.append(
                f"upstream removed {len(lost)} technique key(s): {', '.join(lost)} — the skill may be "
                "shipping a technique upstream retired; confirm before re-recording."
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

    # 2b. whole-subtree comparison. Point sentinels can never be complete — the kintaiyi 全年份域 fix
    #     sat stale in the vendored tree because none of the 7 sentinels lives under a ken engine dir.
    tree_drift: list[str] = []
    tree_checked = 0
    for rel in SENTINEL_TREES:
        vendored_files = _tree_files(VENDOR_ROOT / rel)
        upstream_files = _tree_files(upstream / rel)
        tree_checked += len(vendored_files)
        for name, vendored_path in sorted(vendored_files.items()):
            up_path = upstream_files.get(name)
            if up_path is None:
                tree_drift.append(f"{rel}/{name}: not in upstream (renamed/removed?)")
            elif _sha256(vendored_path) != _sha256(up_path):
                tree_drift.append(f"{rel}/{name}: vendored copy differs")
        # 上游新增、vendored 没有的文件（新引擎/新端点整个漏掉正是这一类）。
        # 但比对口径必须等于**同步口径**：sync 脚本对 Horosa-Web/vendor 是逐个引擎目录拷贝，
        # 不拷根级杂项（README 等），所以只在「已 vendor 的顶层目录内部」判缺失，
        # 否则守卫会对着从来就不该拷的文件恒红。
        vendored_tops = {n.split("/", 1)[0] for n in vendored_files}
        for name in sorted(set(upstream_files) - set(vendored_files)):
            top = name.split("/", 1)[0]
            if top in vendored_tops:
                tree_drift.append(f"{rel}/{name}: present upstream, missing from vendor/runtime-source")
        # 上游整个**新增**的顶层目录 = 潜在新引擎/新能力，单独报（要不要 vendor 是人的决定）。
        new_tops = sorted(
            {n.split("/", 1)[0] for n in upstream_files if "/" in n} - vendored_tops - set(TREE_EXCLUDE_DIRS)
        )
        for top in new_tops:
            tree_drift.append(f"{rel}/{top}/: 上游新增整个目录，未 vendor —— 判断是否为新引擎/新能力")
    if tree_drift:
        failures.append(
            f"vendored runtime subtrees drifted ({len(tree_drift)}; re-run "
            f"scripts/sync_vendored_runtime_sources.sh):\n    - " + "\n    - ".join(tree_drift[:15])
            + ("\n    - …" if len(tree_drift) > 15 else "")
        )

    # 3. core-js vendor drift — the oracle is the manifest, NOT a raw sha256.
    #    A raw-byte compare against untransformed upstream flags every file that legitimately carries
    #    the headless transform (128 of 257 here), so it can never be green — and a permanently-red
    #    check is one people learn to scroll past. The manifest renders upstream through the same
    #    pipeline plus each file's declared deviations, so equality is a real, achievable assertion.
    drifted = manifest_drift(upstream / "Horosa-Web/astrostudyui/src")
    compared = sum(1 for e in load_manifest().values() if e.get("mode") == "verbatim")
    unmatched = [k for k, e in load_manifest().items() if e.get("mode") in {"curated", "bespoke"}]
    if drifted:
        failures.append(
            f"core-js vendored JS out of sync with upstream ({len(drifted)}; "
            f"re-vendor with `revendor_core_js.py <upstream-src> --from-manifest --only <prefix>`):\n    - "
            + "\n    - ".join(drifted[:20])
            + ("\n    - …" if len(drifted) > 20 else "")
        )

    # 4. provenance staleness — "which upstream commit is this tree from?" must be machine-answerable.
    upstream_sha = _git(upstream, "rev-parse", "HEAD")
    recorded_sha = provenance.get("upstream_git_sha") or ""
    if recorded_sha and upstream_sha and recorded_sha != upstream_sha:
        behind = _git(upstream, "rev-list", "--count", f"{recorded_sha}..HEAD") or "?"
        message = (
            f"vendored tree was reconciled against upstream {recorded_sha[:12]} but upstream HEAD is "
            f"{upstream_sha[:12]} ({behind} commit(s) ahead) — re-sync, or re-record with --write-state "
            "once you have verified the delta."
        )
        if args.require_upstream:
            failures.append(message)
        else:
            print(f"::notice::upstream-sync — {message}")

    if failures:
        raise SystemExit("upstream-sync: FAIL\n- " + "\n- ".join(failures))

    # Green only. Writing provenance on a red run turns a failure into a durable claim of currency.
    if args.write_state:
        PROVENANCE.parent.mkdir(parents=True, exist_ok=True)
        PROVENANCE.write_text(
            json.dumps(
                {
                    "_comment": (
                        "vendored 树对到的上游状态。只由 verify_upstream_sync.py --write-state 在**全部检查通过**时"
                        "写入——红着写等于把失败洗成一条持久的「已核对」声明。"
                    ),
                    "upstream_git_sha": upstream_sha,
                    "upstream_git_committed_at": _git(upstream, "log", "-1", "--format=%cI"),
                    "upstream_app_version": _upstream_app_version(upstream),
                    "aiexport_settings_version": upstream_version,
                    "skill_mirrored_version": mirrored,
                    # 记「这次核对时 skill 是哪个版本」——provenance 落后时的报错能指出是哪一版之后失联的。
                    "upstream_checked_at_package_version": _package_version(),
                    "upstream_preset_keys": sorted(upstream_keys),
                    "core_js": {
                        "files_compared": compared,
                        "files_unmatched": len(unmatched),
                        "tree_sha256": _tree_sha256(CORE_JS_VENDOR),
                    },
                    "runtime_source": {"sentinels_verified": len(SENTINELS)},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    app_version = _upstream_app_version(upstream) or "?"
    print(
        f"upstream-sync: ok (upstream {app_version} @ {upstream_sha[:12] or '?'}; aiExport v{upstream_version} "
        f"== mirror; {len(upstream_keys)} technique keys; {len(SENTINELS)} sentinels identical; "
        f"{compared} core-js files identical, {len(unmatched)} unmatched/bespoke; "
        f"{tree_checked} runtime-subtree files compared)"
    )


if __name__ == "__main__":
    main()
