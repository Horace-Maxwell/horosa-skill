#!/usr/bin/env python
"""Export-section debt ratchet — make the skill↔upstream **per-section** gap a tracked, only-shrinking number.

Why this exists: `verify_export_contract_mirror.py` deliberately checks only version + technique *keys*
("Deliberately NOT a per-section diff"). That left a blind spot big enough to hide 235 missing sections
while every guard stayed green — v0.23.0 could claim "整版对齐 v48" because at the key level it was true.

This guard closes it with a lint-baseline ratchet:

* **New debt fails.** A preset section that exists upstream but not in the skill, and is not already in
  `contracts/export_section_debt.json`, is a regression — you either backfilled a technique wrong or
  synced a newer upstream without registering what it added.
* **Paid debt also fails** (with a clear "run --update-baseline" hint), so the baseline can never drift
  upward silently and every backfill visibly ratchets the number down in git.

Source of truth: the **vendored** aiExport by default; `--source upstream` compares against
`$HOROSA_SOURCE_ROOT`.

⚠️ **On GitHub CI neither source exists.** `vendor/runtime-source` is gitignored and there is no
upstream checkout, so the section diff is *skipped* there — this file used to claim the vendored mode
"works with no upstream checkout, e.g. GitHub CI", which was simply false and let the ratchet read as
CI-enforced when it never ran (found 2026-08, alongside the release.yml-never-ran discovery). What CI
*can* still assert is the baseline's own coherence against the in-repo registry, and it now does
(`_assert_baseline_coherent`). The real section diff is a maintainer-machine step —
`scripts/preflight_release.py` runs it with `--source upstream --require-upstream` before tagging.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _upstream_preset import load_upstream_aiexport  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_ROOT = REPO_ROOT / "horosa-skill"
BASELINE = PKG_ROOT / "contracts" / "export_section_debt.json"
VENDORED_AIEXPORT = REPO_ROOT / "vendor/runtime-source/Horosa-Web/astrostudyui/src/utils/aiExport.js"
_UPSTREAM_REL = "Horosa-Web/astrostudyui/src/utils/aiExport.js"

# skill 键 → 上游键（键名分叉，与 verify_export_contract_mirror.py 的 KEY_ALIAS 同源）
KEY_ALIAS = {"wangji": "huangji", "acg": "locastro"}
# 上游无对应技法的 skill-only 键（compat alias / catch-all / skill 自建工具）。
# ⚠️ 这里每多一个键，就整键**不做段级比对**——写错一个等于给自己开一个永久盲区。
# `astrochart_like` 曾经在这份名单里，而上游**确实**有同名 preset（15 段）：于是它的
# `占星地图` 段缺失从来没被计入过任何一版欠账。判据是「上游 AI_EXPORT_PRESET_SECTIONS 里有没有这个键」，
# 不是「skill 侧觉得它是不是别名」——verify_export_contract_mirror.py 的 DIVERGENCE_WHITELIST 管的是
# 键**覆盖**（skill 有而上游无），跟这里的段级比对不是同一个问题，两份名单不该互相抄。
SKILL_ONLY_KEYS = {"generic", "astrodata"}


def _assert_baseline_coherent() -> None:
    """无 aiExport 源时（GitHub CI）唯一还能做真的断言：基线 vs 仓内 registry 的自洽。

    抓的是「技法被改名/删掉，而 `export_section_debt.json` 里还留着旧键」这类漂移——不需要任何
    vendored/上游树。以前这条路径是纯 skip，于是整个 step 在 CI 里零断言。
    """
    if not BASELINE.is_file():
        raise SystemExit(f"export-section-baseline: FAIL — baseline missing at {BASELINE}")
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    presets = _skill_presets()
    stale = sorted(
        key
        for key, entry in baseline.get("keys", {}).items()
        if not entry.get("absent_key") and key not in presets
    )
    if stale:
        raise SystemExit(
            "export-section-baseline: FAIL — baseline references keys that no longer exist in "
            f"AI_EXPORT_PRESET_SECTIONS: {', '.join(stale)} (technique renamed/removed? re-run "
            "--update-baseline on a box with a vendored tree)"
        )
    print(
        f"export-section-baseline: baseline coherent ({len(baseline.get('keys', {}))} keys, "
        f"all present in the registry) — section diff needs a vendored/upstream tree, see preflight_release.py"
    )


def _skill_presets() -> dict[str, list[str]]:
    sys.path.insert(0, str(PKG_ROOT / "src"))
    from horosa_skill.exports.registry import AI_EXPORT_PRESET_SECTIONS

    return {key: list(value) for key, value in AI_EXPORT_PRESET_SECTIONS.items()}


def _resolve_source(source: str, require_upstream: bool) -> Path | None:
    if source == "vendored":
        return VENDORED_AIEXPORT if VENDORED_AIEXPORT.is_file() else None
    root = os.environ.get("HOROSA_SOURCE_ROOT")
    if not root:
        if require_upstream:
            raise SystemExit(
                "export-section-baseline: --source upstream --require-upstream but HOROSA_SOURCE_ROOT is unset."
            )
        return None
    candidate = Path(root).expanduser() / _UPSTREAM_REL
    return candidate if candidate.is_file() else None


def _diff(upstream: dict[str, list[str]], skill: dict[str, list[str]]) -> dict[str, dict[str, list[str]]]:
    upstream_for_skill_key = {key: KEY_ALIAS.get(key, key) for key in skill}
    debt: dict[str, dict[str, list[str]]] = {}
    for skill_key, sections in skill.items():
        if skill_key in SKILL_ONLY_KEYS:
            continue
        upstream_sections = upstream.get(upstream_for_skill_key[skill_key])
        if upstream_sections is None:
            continue
        missing = [s for s in upstream_sections if s not in set(sections)]
        extra = [s for s in sections if s not in set(upstream_sections)]
        if missing or extra:
            debt[skill_key] = {"missing": missing, "extra": extra}
    mapped = {KEY_ALIAS.get(k, k) for k in skill}
    for upstream_key, sections in upstream.items():
        if upstream_key not in mapped:
            debt[upstream_key] = {"missing": list(sections), "extra": [], "absent_key": True}
    return debt


def _totals(debt: dict[str, dict[str, list[str]]]) -> dict[str, int]:
    return {
        "missing_sections": sum(len(v["missing"]) for v in debt.values()),
        "extra_sections": sum(len(v["extra"]) for v in debt.values()),
        "absent_keys": sum(1 for v in debt.values() if v.get("absent_key")),
        "keys_with_debt": len(debt),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["vendored", "upstream"], default="vendored")
    parser.add_argument("--require-upstream", action="store_true")
    parser.add_argument("--update-baseline", action="store_true", help="rewrite the baseline to today's debt")
    args = parser.parse_args()

    aiexport = _resolve_source(args.source, args.require_upstream)
    if aiexport is None:
        print(json.dumps({"section_diff": "skipped", "reason": f"{args.source} aiExport.js unavailable"}, ensure_ascii=False))
        print(f"::notice::export-section-baseline section diff skipped ({args.source} aiExport.js unavailable)")
        _assert_baseline_coherent()
        return

    version, upstream = load_upstream_aiexport(aiexport)
    skill = _skill_presets()
    debt = _diff(upstream, skill)
    totals = _totals(debt)

    if args.update_baseline:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(
                {
                    "_comment": "上游 preset 段级欠账基线（棘轮：只减不增）。回填后跑 --update-baseline 收紧。",
                    "source": {"kind": args.source, "aiexport_settings_version": version},
                    "totals": totals,
                    "keys": {k: debt[k] for k in sorted(debt)},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"export-section-baseline: baseline updated ({totals['missing_sections']} missing sections)")
        return

    if not BASELINE.is_file():
        raise SystemExit(f"export-section-baseline: baseline missing at {BASELINE}; run --update-baseline once.")
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    base_keys = baseline.get("keys", {})

    regressions: list[str] = []
    improvements: list[str] = []
    for key, entry in sorted(debt.items()):
        base = base_keys.get(key, {"missing": [], "extra": []})
        new_missing = sorted(set(entry["missing"]) - set(base.get("missing", [])))
        new_extra = sorted(set(entry["extra"]) - set(base.get("extra", [])))
        if new_missing:
            regressions.append(f"{key}: +{len(new_missing)} missing {new_missing[:6]}")
        if new_extra:
            regressions.append(f"{key}: +{len(new_extra)} unknown-to-upstream {new_extra[:6]}")
    for key, base in sorted(base_keys.items()):
        entry = debt.get(key, {"missing": [], "extra": []})
        paid = sorted(set(base.get("missing", [])) - set(entry["missing"]))
        if paid:
            improvements.append(f"{key}: -{len(paid)} {paid[:6]}")

    if regressions:
        raise SystemExit(
            "export-section-baseline: FAIL — new upstream-section debt (backfill it, or re-run "
            "--update-baseline only if you deliberately accept it):\n- " + "\n- ".join(regressions)
        )
    if improvements:
        raise SystemExit(
            "export-section-baseline: debt was PAID DOWN but the baseline still lists it — tighten the "
            "ratchet with `--update-baseline` and commit:\n- " + "\n- ".join(improvements)
        )
    print(
        f"export-section-baseline: ok (source={args.source} aiExport v{version}; "
        f"{totals['missing_sections']} missing / {totals['extra_sections']} extra / "
        f"{totals['absent_keys']} absent keys — matches baseline)"
    )


if __name__ == "__main__":
    main()
