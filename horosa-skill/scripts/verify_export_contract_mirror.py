#!/usr/bin/env python
"""Export-contract mirror guard — machine-assert the skill's export registry stays aligned with the
vendored upstream aiExport.js.

Two assertions, both defending the "three-layer version skew" failure (skill mirror < vendored runtime <
upstream HEAD) that let ~20 techniques drift silently before v0.23.0:

1. **Version lockstep**: the vendored aiExport.js `AI_EXPORT_SETTINGS_VERSION` must equal the skill's
   `MIRRORED_UPSTREAM_AIEXPORT_VERSION`. Bumping one without the other (or syncing an old tree) fails here.
2. **Technique-key coverage**: every skill export-technique key must either exist in the vendored upstream
   `AI_EXPORT_TECHNIQUES` keys OR be on the explicit DIVERGENCE whitelist (skill-only compat/catch-all keys).
   Catches an upstream key rename/removal that the skill still mirrors.

Deliberately NOT a per-section diff: internal preset↔builder consistency is already asserted by the
offline contract tests (missing/unknown == []); this guard's unique job is the cross-tree version + key
alignment. Run in CI alongside verify_docs_sync.py.
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
}

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
    # guard the alias map itself: an alias whose target vanished upstream is a silent hole.
    stale_aliases = [k for k, up in KEY_ALIAS.items() if up not in upstream_keys]
    if stale_aliases:
        raise SystemExit(f"KEY_ALIAS targets missing from vendored upstream: {stale_aliases} (upstream renamed again?)")

    print(
        f"export-contract-mirror: ok (aiExport v{vendored_version} == MIRRORED v{mirrored}; "
        f"{len(skill_keys)} skill keys, {len(upstream_keys)} upstream keys, "
        f"{len([k for k in skill_keys if k in DIVERGENCE_WHITELIST])} whitelisted)"
    )


if __name__ == "__main__":
    main()
