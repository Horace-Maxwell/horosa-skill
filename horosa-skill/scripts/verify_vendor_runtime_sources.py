from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_PATHS = [
    "vendor/runtime-source/runtime/mac",
    "vendor/runtime-source/runtime/windows",
    "vendor/runtime-source/prepareruntime",
    "horosa-skill/scripts/build_runtime_release.sh",
    # v3.5.0 全年份域 shared module — 16 ken/神数 engine files lazily `from kin_year_domain import ...`
    # for the BC/远期 year fallback path. If the sync dropped it, every ken/神数 engine 500s on its
    # first out-of-domain request. This is the machine guard for the kin_year_domain sync-drop lesson.
    "vendor/runtime-source/Horosa-Web/vendor/kin_year_domain.py",
    # v3.5.1 地占大改版 data — the new ifa/numbers/vedic engines read these; a real file here proves
    # the geomancy subtree is the current one (not a pre-v3.5.1 stale copy).
    "vendor/runtime-source/Horosa-Web/astropy/astrostudy/geomancy/data/ifa_odu.json",
    # 政余/xuanshi 神数 backing SQLite (kentang /xuanshi mount) — a real file inside, never an empty dir.
    "vendor/runtime-source/Horosa-Web/astropy/astrostudy/xuanshi/data/public_data.sqlite",
    # 玄史知识库编辑层（v0.32.0 xuanshi 工具）——缺席时引擎静默降级为 {}，只有这里判红。
    "vendor/runtime-source/Horosa-Web/astropy/astrostudy/xuanshi/data/editorial.sqlite",
    # export-contract source of truth; also content-checked for version currency (see below).
    "vendor/runtime-source/Horosa-Web/astrostudyui/src/utils/aiExport.js",
]

# The vendored aiExport.js version must EQUAL the skill's mirror constant. It used to be a `>=` lower
# bound, which passed for any newer tree too — so a vendored tree that had moved ahead (or a mirror
# constant left behind) produced no signal at all. Equality makes both directions of skew red, and the
# constant now lives in one place (exports/registry.py) instead of being duplicated here.
_AIEXPORT_REL = "vendor/runtime-source/Horosa-Web/astrostudyui/src/utils/aiExport.js"
_AIEXPORT_VERSION_RE = re.compile(r"AI_EXPORT_SETTINGS_VERSION\s*=\s*(\d+)")


def _expected_aiexport_version(root: Path) -> int:
    import sys

    sys.path.insert(0, str(root / "horosa-skill" / "src"))
    from horosa_skill.exports.registry import MIRRORED_UPSTREAM_AIEXPORT_VERSION

    return int(MIRRORED_UPSTREAM_AIEXPORT_VERSION)


def _check_aiexport_version(root: Path) -> dict:
    """Assert the vendored aiExport.js version == the skill's MIRRORED_UPSTREAM_AIEXPORT_VERSION."""
    target = root / _AIEXPORT_REL
    text = target.read_text(encoding="utf-8", errors="replace")
    match = _AIEXPORT_VERSION_RE.search(text)
    if not match:
        raise SystemExit(f"Could not read AI_EXPORT_SETTINGS_VERSION from {target}")
    version = int(match.group(1))
    expected = _expected_aiexport_version(root)
    if version != expected:
        raise SystemExit(
            f"Vendored aiExport.js version skew: AI_EXPORT_SETTINGS_VERSION={version} != skill "
            f"MIRRORED_UPSTREAM_AIEXPORT_VERSION={expected}. Re-sync against the matching Horosa-Public "
            f"checkout, or advance the mirror constant together with the backfilled sections."
        )
    return {"aiexport_settings_version": version, "expected": expected}


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify vendored runtime source prerequisites for release builds.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.root.resolve()
    results = []
    missing = []
    for rel in REQUIRED_PATHS:
        target = root / rel
        exists = target.exists()
        results.append({"path": str(target), "exists": exists})
        if not exists:
            missing.append(str(target))
    if missing:
        raise SystemExit("Missing vendored runtime sources:\n" + "\n".join(missing))
    version_info = _check_aiexport_version(root)
    print(json.dumps({"ok": True, "checked": results, "aiexport": version_info}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
