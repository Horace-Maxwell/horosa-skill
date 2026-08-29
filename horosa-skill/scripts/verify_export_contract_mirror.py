#!/usr/bin/env python
"""Export-contract mirror guard — machine-assert the skill's export registry stays aligned with the
vendored upstream aiExport.js.

Two assertions, both defending the "three-layer version skew" failure (skill mirror < vendored runtime <
upstream HEAD) that let ~20 techniques drift silently before v0.23.0:

1. **Version lockstep**: the vendored aiExport.js `AI_EXPORT_SETTINGS_VERSION` must equal the skill's
   `MIRRORED_UPSTREAM_AIEXPORT_VERSION`. Bumping one without the other (or syncing an old tree) fails here.
2. **Technique-key coverage (skill → upstream)**: every skill export-technique key must either exist in the
   vendored upstream `AI_EXPORT_TECHNIQUES` keys OR be on the explicit DIVERGENCE whitelist (skill-only
   compat/catch-all keys). Catches an upstream key rename/removal that the skill still mirrors.
2b. **Technique-key arrival (upstream → skill)**: every vendored-upstream key must be mirrored by the skill
   or be on `UPSTREAM_ONLY_LEDGER` with a reason. Check 2 alone is one-way — it asserts `skill ⊆ upstream`,
   so a **new upstream technique can never fail it**, no matter how current the vendored tree is. That hole
   is why this guard stayed green through `lingqi` (upstream v3.9.0) while the only signal lived in
   verify_upstream_sync's check 1b — which CI runs without `--require-upstream`, i.e. not at all.

Deliberately NOT a per-section diff: internal preset↔builder consistency is already asserted by the
offline contract tests (missing/unknown == []); this guard's unique job is the cross-tree version + key
alignment. Run in CI alongside verify_docs_sync.py.

⚠️ 本守卫的盲区（v0.31.0 实证）：它只比 vendored 镜像的版本常量与 key 集合——上游**加段不 bump
版本**时（v3.9.5 horary +9、常量原地 56）本守卫全绿穿透。同步健康的权威判据是
verify_upstream_sync.py（sentinel sha256）与 verify_export_section_baseline.py 的
`--source upstream --require-upstream` 形态；本守卫只兜「新 key 到达」与「版本倒退」两类。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDORED_AIEXPORT = REPO_ROOT / "vendor/runtime-source/Horosa-Web/astrostudyui/src/utils/aiExport.js"

# Documented skill↔upstream key-name divergences: the skill export key differs from the upstream one.
# A skill key is valid if its alias is present in the vendored upstream keys.
KEY_ALIAS = {
    "wangji": "huangji",  # 皇极经世：skill 键 wangji ↔ 上游键 huangji（键名分叉，见 docs/LESSONS.md）
    "acg": "locastro",    # 占星地图：skill 键 acg ↔ 上游键 locastro
}

# skill-only export keys with no 1:1 upstream technique (compat aliases / catch-all / skill-only tool) —
# never expected in the vendored AI_EXPORT_TECHNIQUES. Keep this list tight; add only with a one-line reason.
DIVERGENCE_WHITELIST = {
    "astrochart_like": "skill compat alias for chart13/derived astro presets",
    "generic": "skill catch-all preset for unrecognized pasted exports; no upstream technique",
    "astrodata": "名人星盘库为 skill 侧离线检索 tool；上游 aiExport 无对应导出技法（celebrity DB 页无 AI 导出契约）",
    "xuanshi": "玄史知识库为 skill 侧检索 tool（runtime 自带只读 SQLite bundle，/xuanshi/* 端点）；上游玄史页无 AI 导出契约",
    "qizhengelection": "七政择日动盘为 skill 侧工具（/qizhengelection/pan|eclipses|azimuthsearch 直连）；上游择日双轮是果老盘内嵌 UI，无 AI 导出契约",
    "india_rectify": "印度生时校正为 skill 侧工具（/india/rectify 直连）；上游校时器是印占页抽屉 UI（§17），无 AI 导出契约",
}

# upstream export keys the skill deliberately does NOT mirror. Every entry needs a reason and a ledger
# reference (AGENTS.md §5 审计前置 / docs/LESSONS.md 排除台账) — "有引擎文件 ≠ 可进公开 skill".
# Keep this empty unless a technique is genuinely unavailable headless; it is the one place where
# "we knowingly skipped an upstream technique" is allowed to be recorded.
UPSTREAM_ONLY_LEDGER: dict[str, str] = {}

# upstream spreads these into AI_EXPORT_TECHNIQUES via JIEQI_SPLIT_TECHNIQUES (string array), not as
# {key:...} object literals — recognize them by presence as a string literal in the file.
JIEQI_SPLIT_KEYS = {"jieqi_meta", "jieqi_chunfen", "jieqi_xiazhi", "jieqi_qiufen", "jieqi_dongzhi"}

_VERSION_RE = re.compile(r"AI_EXPORT_SETTINGS_VERSION\s*=\s*(\d+)")
_TECHNIQUES_BLOCK_RE = re.compile(r"AI_EXPORT_TECHNIQUES\s*=\s*\[(.*?)\];", re.DOTALL)
_KEY_RE = re.compile(r"key:\s*'([^']+)'")


def _load_skill_registry():
    sys.path.insert(0, str(REPO_ROOT / "horosa-skill" / "src"))
    from horosa_skill.exports import registry  # noqa: E402

    return registry


def main() -> None:
    if not VENDORED_AIEXPORT.is_file():
        raise SystemExit(
            f"vendored aiExport.js not found at {VENDORED_AIEXPORT}\n"
            "run sync_vendored_runtime_sources.py first (mirror guard needs the vendored upstream copy)."
        )
    text = VENDORED_AIEXPORT.read_text(encoding="utf-8", errors="replace")
    registry = _load_skill_registry()

    # 1. version lockstep
    vm = _VERSION_RE.search(text)
    if not vm:
        raise SystemExit(f"could not read AI_EXPORT_SETTINGS_VERSION from {VENDORED_AIEXPORT}")
    vendored_version = int(vm.group(1))
    mirrored = int(registry.MIRRORED_UPSTREAM_AIEXPORT_VERSION)
    if vendored_version != mirrored:
        raise SystemExit(
            f"export-contract version skew: vendored aiExport AI_EXPORT_SETTINGS_VERSION={vendored_version} "
            f"!= skill MIRRORED_UPSTREAM_AIEXPORT_VERSION={mirrored}.\n"
            "Bump MIRRORED_UPSTREAM_AIEXPORT_VERSION in exports/registry.py after re-syncing, or re-sync a "
            "current Horosa-Public checkout."
        )

    # 2. technique-key coverage
    block = _TECHNIQUES_BLOCK_RE.search(text)
    if not block:
        raise SystemExit(f"could not locate AI_EXPORT_TECHNIQUES array in {VENDORED_AIEXPORT}")
    upstream_keys = set(_KEY_RE.findall(block.group(1)))
    if not upstream_keys:
        raise SystemExit("parsed AI_EXPORT_TECHNIQUES but found zero keys — parser or source changed shape")
    # add jieqi splits spread in via JIEQI_SPLIT_TECHNIQUES (present as string literals in the file).
    upstream_keys |= {k for k in JIEQI_SPLIT_KEYS if f"'{k}'" in text}

    def _covered(key: str) -> bool:
        return key in upstream_keys or KEY_ALIAS.get(key) in upstream_keys or key in DIVERGENCE_WHITELIST

    skill_keys = [t["key"] for t in registry.AI_EXPORT_TECHNIQUES]
    orphans = [k for k in skill_keys if not _covered(k)]
    if orphans:
        raise SystemExit(
            "skill export-technique keys not present in vendored upstream AI_EXPORT_TECHNIQUES "
            f"(and not covered by KEY_ALIAS/DIVERGENCE_WHITELIST): {orphans}\n"
            "an upstream rename/removal, or a skill-only key that needs an alias/whitelist entry with a reason."
        )
    # 2b. the other direction. `skill ⊆ upstream` is structurally blind to a NEW upstream technique —
    #     it can only ever fail on a rename/removal. Upstream ships new keys without moving either
    #     version gate (aiExport.js:306), so with check 2 alone a fully re-synced vendored tree still
    #     reports "ok" while a whole technique is missing (that is exactly how `lingqi` got through).
    mapped_skill_keys = set(skill_keys) | {KEY_ALIAS.get(k, k) for k in skill_keys}
    unmirrored = sorted(upstream_keys - mapped_skill_keys - set(UPSTREAM_ONLY_LEDGER))
    if unmirrored:
        raise SystemExit(
            f"vendored upstream has {len(unmirrored)} technique key(s) the skill does not mirror: {unmirrored}\n"
            "Register them (AGENTS §5 布线清单), or — if genuinely unavailable on the open-source headless "
            "stack — add them to UPSTREAM_ONLY_LEDGER here with a reason and a docs/LESSONS.md ledger entry."
        )
    # guard the ledger itself: an entry whose key vanished upstream is stale bookkeeping that hides the
    # next arrival behind an excuse written for a technique that no longer exists.
    stale_ledger = sorted(set(UPSTREAM_ONLY_LEDGER) - upstream_keys)
    if stale_ledger:
        raise SystemExit(f"UPSTREAM_ONLY_LEDGER entries no longer present upstream: {stale_ledger} (drop them)")

    # guard the alias map itself: an alias whose target vanished upstream is a silent hole.
    stale_aliases = [k for k, up in KEY_ALIAS.items() if up not in upstream_keys]
    if stale_aliases:
        raise SystemExit(f"KEY_ALIAS targets missing from vendored upstream: {stale_aliases} (upstream renamed again?)")

    print(
        f"export-contract-mirror: ok (aiExport v{vendored_version} == MIRRORED v{mirrored}; "
        f"{len(skill_keys)} skill keys, {len(upstream_keys)} upstream keys, "
        f"{len([k for k in skill_keys if k in DIVERGENCE_WHITELIST])} whitelisted, "
        f"{len(UPSTREAM_ONLY_LEDGER)} upstream-only ledgered)"
    )


if __name__ == "__main__":
    main()
