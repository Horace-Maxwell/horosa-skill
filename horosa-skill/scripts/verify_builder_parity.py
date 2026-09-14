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

# Windows 控制台默认 cp1252/cp936：脚本自己 print 的中文会抛 UnicodeEncodeError 并让脚本 exit 1
# （v0.38.0 的 repack 脚本在「打印成功信息」那一步失败过）。统一在入口把两条流改成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")
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

# The N-way cross-check above only proves the stampers agree with *each other* — five scripts can be
# unanimously wrong. `export_registry_version` declares which export contract a payload was built
# against, so its source of truth is the registry constant in code. v0.26.0 drifted exactly here: the
# 天星/奇门择日 change bumped AI_EXPORT_SETTINGS_VERSION 11→12 and left all five stampers at 11, and
# this lint stayed green because every stamper still matched every other stamper. Anchor it.
EXPORT_REGISTRY_SOURCE = SCRIPTS.parent / "src" / "horosa_skill" / "exports" / "registry.py"
ANCHORED_CONSTANTS = {"export_registry_version": ("AI_EXPORT_SETTINGS_VERSION", EXPORT_REGISTRY_SOURCE)}

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
        "astrostudy/qizheng_election_scan.py",
        "astrostudy/india_election_scan.py",
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
        anchor = ANCHORED_CONSTANTS.get(name)
        if anchor and stamped:
            const_name, source = anchor
            if not source.exists():
                errors.append(f"cannot anchor `{name}`: {source} is missing")
                continue
            match = re.search(rf"^{const_name}\s*=\s*(\d+)", source.read_text(encoding="utf-8"), re.MULTILINE)
            if not match:
                errors.append(f"cannot anchor `{name}`: {const_name} not found in {source.name}")
                continue
            expected = int(match.group(1))
            lagging = {label: vals for label, vals in stamped.items() if vals != [expected]}
            if lagging:
                detail = ", ".join(f"{label}={vals}" for label, vals in sorted(lagging.items()))
                errors.append(
                    f"embedded-manifest constant `{name}` does not match its source of truth "
                    f"{const_name}={expected} ({source.name}): {detail} — the stampers can be unanimously "
                    "wrong, so bump every stamper in the same change as the registry constant"
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

    # v0.38.0 A2: the Windows builder's seed mode must derive only from a verified seed and must not stamp
    # manifest constants itself (it inherits them); the jlink module list has ONE source of truth.
    if "runtime_seed" not in win or "verify_seed(" not in win:
        errors.append("Windows builder has no seed+derive mode (must import runtime_seed and call verify_seed( before deriving)")
    if "derive_manifest(" not in win:
        errors.append("Windows builder's seed mode must build its manifest with runtime_seed.derive_manifest (inherit, never stamp)")
    toolchain_path = SCRIPTS.parent / "contracts" / "runtime_toolchain.json"
    if toolchain_path.exists():
        import json as _json

        pinned = list(_json.loads(toolchain_path.read_text(encoding="utf-8"))["java"]["jlink_modules"])
        mac_match = re.search(r'jlink_modules="([^"]+)"', mac)
        mac_list = mac_match.group(1).split(",") if mac_match else []
        if sorted(mac_list) != sorted(pinned):
            errors.append(
                "jlink module list drifted: package_runtime_payload.sh vs contracts/runtime_toolchain.json — "
                f"mac-only {sorted(set(mac_list) - set(pinned))}, contract-only {sorted(set(pinned) - set(mac_list))}"
            )
        if "jlink_modules" not in win:
            errors.append("Windows builder's seed mode must take the jlink module list from contracts/runtime_toolchain.json")

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
