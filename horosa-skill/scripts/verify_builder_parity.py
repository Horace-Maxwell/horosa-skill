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
}

# Entries that must be REQUIRED on BOTH platforms (legit per-platform path swaps like python3<->python.exe
# and .sh<->.ps1 are intentionally not checked here — only the platform-agnostic payload contents).
REQUIRED_ON_BOTH = (
    [f"vendor/{e}/" for e in ENGINES]
    + [
        "vendor/kinastro/astro/",
        "shaozi/data/shaozi_tiaowen_6144.json",
        "node_modules/lunar-javascript/package.json",
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
        "run shaozi-gen + plotly-strip + lunar-javascript, and REQUIRED_ENTRIES is symmetric across platforms."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
