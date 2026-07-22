#!/usr/bin/env python3
"""Lint that the macOS and Windows runtime builders stay in lockstep.

The offline runtime is built two ways that independently re-implement the same staging:
`scripts/package_runtime_payload.sh` (macOS) and `scripts/build_runtime_release_windows.py` (Windows).
When a packaging step lands in one but not the other, the lagging platform's payload silently regresses —
this is exactly what happened at v0.10.0 (the 邵子 verse-JSON generation + plotly strip were added to the
mac builder but not the Windows one, so a Windows build would have shipped placeholder 邵子 verses and a
40 MB-larger zip and still passed verification). `verify_runtime_release.py`'s REQUIRED_ENTRIES is the
cross-platform contract both builders must satisfy; this lint asserts the two builders and that contract
have not diverged. Stdlib-only; exits non-zero with an explanation on any divergence. Wired into CI.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
MAC_BUILDER = SCRIPTS / "package_runtime_payload.sh"
WIN_BUILDER = SCRIPTS / "build_runtime_release_windows.py"
VERIFIER = SCRIPTS / "verify_runtime_release.py"

# The 8 standalone ken/神数 engines both builders must vendor (the shared kinastro engine — backing the
# 9 kinastro-* 神数 — is handled as a separate step token below).
ENGINES = [
    "kinqimen",
    "kintaiyi",
    "kinjinkou",
    "kinwangji",
    "kinwuzhao",
    "taixuanshifa",
    "jingjue",
    "shenyishu",
]

# Packaging steps that must appear in BOTH builders (substring -> human label).
SHARED_STEPS = {
    "kinastro": "vendor the shared kinastro engine (9 kinastro-* 神数)",
    "gen_shaozi_tiaowen": "generate shaozi_tiaowen_6144.json (邵子 real verses)",
    "plotly": "strip plotly (~40 MB, streamlit-only)",
    "lunar-javascript": "bundle the lunar-javascript npm dep (canping/heluo)",
    "kin_year_domain": "copy the 全年份域 shared module kin_year_domain.py (16 engines lazily import it)",
}

# Embedded-manifest integer constants that must be stamped identically by every script that writes
# a runtime manifest. Substring checks can't see numeric drift: at v0.16.1 the mac packager bumped
# export_registry_version 6→7 while the Windows builder kept stamping 6 and this lint stayed green.
SHARED_MANIFEST_CONSTANTS = ("schema_version", "runtime_layout_version", "export_registry_version")

# Every manifest-stamping script, not just the mac/win release pair: around v0.22.0 the linux builder
# and both dev scaffolds still stamped export_registry_version 6 while mac/win were at 10 — the
# constants cross-check only read mac/win, so CI stayed green through that drift. Scripts listed here
# that don't exist are skipped (repo layout may evolve); an existing script missing a constant errors.
CONSTANT_STAMPERS = {
    "macOS builder": MAC_BUILDER,
    "Windows builder": WIN_BUILDER,
    "Linux builder": SCRIPTS / "build_runtime_release_linux.py",
    "Windows scaffold": SCRIPTS / "scaffold_windows_runtime.py",
    "Linux scaffold": SCRIPTS / "scaffold_linux_runtime.py",
}

# Builders that download a Temurin JDK must resolve it via the Adoptium API redirect, which only
# points at binaries that exist. GitHub `releases/latest` on temurin17-binaries picks by tag commit
# date, so a freshly-tagged GA can have zero platform assets for hours (jdk-17.0.20-ga stranded both
# JDK-downloading builders). The mac builder vendors runtime/mac/java and is exempt.
JDK_DOWNLOADING_BUILDERS = {
    "Windows builder": WIN_BUILDER,
    "Linux builder": SCRIPTS / "build_runtime_release_linux.py",
}
ADOPTIUM_API_NEEDLE = "api.adoptium.net/v3/binary/latest/17/ga/"
GITHUB_TEMURIN_LATEST_NEEDLE = "temurin17-binaries/releases/latest"

# Entries that must be REQUIRED on BOTH platforms (legit per-platform path swaps like python3<->python.exe
# and .sh<->.ps1 are intentionally not checked here — only the platform-agnostic payload contents).
REQUIRED_ON_BOTH = (
    [f"vendor/{e}/" for e in ENGINES]
    + [
        "vendor/kinastro/astro/",
        "shaozi/data/shaozi_tiaowen_6144.json",
        "node_modules/lunar-javascript/package.json",
        "vendor/kin_year_domain.py",
        "geomancy/data/ifa_odu.json",
    ]
)


def _load_required_entries() -> dict:
    spec = importlib.util.spec_from_file_location("_horosa_verify_for_parity", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.REQUIRED_ENTRIES


def main() -> int:
    errors: list[str] = []
    mac = MAC_BUILDER.read_text(encoding="utf-8")
    win = WIN_BUILDER.read_text(encoding="utf-8")

    for engine in ENGINES:
        if engine not in mac:
            errors.append(f"macOS builder ({MAC_BUILDER.name}) does not reference engine `{engine}`")
        if engine not in win:
            errors.append(f"Windows builder ({WIN_BUILDER.name}) does not reference engine `{engine}`")

    for token, label in SHARED_STEPS.items():
        if token not in mac:
            errors.append(f"macOS builder is missing step `{token}` ({label}) — would regress vs Windows")
        if token not in win:
            errors.append(f"Windows builder is missing step `{token}` ({label}) — would regress vs macOS")

    for name in SHARED_MANIFEST_CONSTANTS:
        stamped: dict[str, list[int]] = {}
        for label, path in CONSTANT_STAMPERS.items():
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            vals = sorted({int(v) for v in re.findall(rf'"{name}"\s*:\s*(\d+)', text)})
            if not vals:
                errors.append(f"{label} ({path.name}) does not stamp `{name}` in its embedded manifest")
                continue
            stamped[label] = vals
        if len({tuple(v) for v in stamped.values()}) > 1:
            detail = ", ".join(f"{label}={vals}" for label, vals in sorted(stamped.items()))
            errors.append(
                f"embedded-manifest constant `{name}` drifted across manifest-stamping scripts: {detail} "
                "— bump the lagging script(s) in the same change"
            )

    for label, path in JDK_DOWNLOADING_BUILDERS.items():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if ADOPTIUM_API_NEEDLE not in text:
            errors.append(
                f"{label} ({path.name}) does not resolve the JDK via the Adoptium API "
                f"(`{ADOPTIUM_API_NEEDLE}`)"
            )
        if GITHUB_TEMURIN_LATEST_NEEDLE in text:
            errors.append(
                f"{label} ({path.name}) still queries GitHub `{GITHUB_TEMURIN_LATEST_NEEDLE}` — "
                "a freshly-tagged GA can have zero platform assets; use the Adoptium API redirect"
            )

    required = _load_required_entries()
    for platform in ("darwin-arm64", "win32-x64"):
        joined = "\n".join(required.get(platform, []))
        for needle in REQUIRED_ON_BOTH:
            if needle not in joined:
                errors.append(f"verify_runtime_release.py REQUIRED_ENTRIES[{platform!r}] is missing `{needle}`")

    if errors:
        print("builder-parity lint FAILED — the two runtime builders / the verifier contract have drifted:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(
        f"builder-parity OK: both builders vendor all {len(ENGINES)} standalone engines + kinastro, "
        "run shaozi-gen + plotly-strip + lunar-javascript, stamp identical manifest constants, "
        "and REQUIRED_ENTRIES is symmetric across platforms."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
