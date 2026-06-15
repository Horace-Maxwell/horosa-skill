#!/usr/bin/env python3
"""One-command Windows-side release sync.

The macOS side keeps publishing a new version as the public GitHub `latest` while it is still
incomplete — darwin-only `runtime-manifest.json`, no win32 zip — which breaks `horosa-skill install`
for every Windows user (v0.10.0/v0.11.0/v0.12.0/v0.13.0 all did this). The Windows offline runtime is
built off-CI on a real Windows box, so it can only be produced + uploaded from here. `release-completeness.yml`
*detects* the gap; this script is the Windows-side *remediation*, packaging the otherwise-manual dance
(build → download darwin → dual-platform manifest + checksums → verify → upload) into one repeatable,
idempotent command. It does NOT touch the macOS release flow.

Usage (run from the repo root on the Windows build box):
    python horosa-skill/scripts/sync_windows_release.py            # detect + (if needed) build + verify; never uploads
    python horosa-skill/scripts/sync_windows_release.py --upload   # also upload the win zip + dual manifest to the release
    python horosa-skill/scripts/sync_windows_release.py --check    # detect-only: report completeness, build nothing

Safe by default: without --upload it stops after building + verifying locally (no irreversible action).
Idempotent: if the current `latest` already has the Windows half + a dual-platform manifest, it reports
"in sync, nothing to do" and exits 0 without building.

Prerequisites for an actual build (only needed when the release is incomplete): this Windows box must be
synced to the release commit (`git pull` — the build stamps the version from pyproject.toml), have
`vendor/runtime-source/` populated, and have `gh`/`uv`/`npm`/`curl` on PATH (same as the manual runbook).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = "Horace-Maxwell/horosa-skill"
SKILL_ROOT = Path(__file__).resolve().parents[1]          # horosa-skill/
REPO_ROOT = SKILL_ROOT.parent                              # repo root
SCRIPTS = SKILL_ROOT / "scripts"
DIST = SKILL_ROOT / "dist" / "runtime"
PLATFORMS = ("darwin-arm64", "win32-x64")


def run(cmd: list[str], *, cwd: Path | None = None, capture: bool = False) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(
        cmd, cwd=str(cwd or REPO_ROOT), check=True, text=True,
        encoding="utf-8", errors="replace",
        stdout=(subprocess.PIPE if capture else None),
        stderr=(subprocess.STDOUT if capture else None),
    )


def gh_json(args: list[str]):
    out = subprocess.run(["gh", *args], check=True, text=True, encoding="utf-8", errors="replace",
                         stdout=subprocess.PIPE).stdout
    return json.loads(out) if out.strip() else None


def read_pyproject_version() -> str:
    import tomllib
    return tomllib.loads((SKILL_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def latest_tag() -> str:
    # `gh api --jq .tag_name` emits the bare extracted value (e.g. "v0.13.0"), not JSON — read it raw.
    out = subprocess.run(
        ["gh", "api", f"repos/{REPO}/releases/latest", "--jq", ".tag_name"],
        check=True, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE,
    ).stdout
    return out.strip()


def release_assets(tag: str) -> list[str]:
    data = gh_json(["release", "view", tag, "--repo", REPO, "--json", "assets"]) or {}
    return [a["name"] for a in data.get("assets", [])]


def fetch_latest_manifest_platforms() -> list[str] | None:
    """Return the platform keys in the live latest manifest, or None if it 404s / is unparseable."""
    url = f"https://github.com/{REPO}/releases/latest/download/runtime-manifest.json"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:  # follows GitHub's 302 to the asset
            data = json.loads(resp.read().decode("utf-8"))
        return list(data.get("platforms", {}).keys())
    except Exception:
        return None


def assess(tag: str) -> dict:
    version = tag.lstrip("v")
    assets = release_assets(tag)
    win_zip = f"horosa-runtime-win32-x64-v{version}.zip"
    darwin_tar = f"horosa-runtime-darwin-arm64-v{version}.tar.gz"
    platforms = fetch_latest_manifest_platforms()
    return {
        "tag": tag,
        "version": version,
        "has_win_zip": win_zip in assets,
        "has_darwin_tar": darwin_tar in assets,
        "has_manifest_asset": "runtime-manifest.json" in assets,
        "manifest_platforms": platforms,
        "manifest_dual": bool(platforms) and all(p in platforms for p in PLATFORMS),
        "win_zip": win_zip,
        "darwin_tar": darwin_tar,
    }


def is_complete(a: dict) -> bool:
    return a["has_win_zip"] and a["has_darwin_tar"] and a["has_manifest_asset"] and a["manifest_dual"]


def build_and_verify(a: dict) -> tuple[Path, Path]:
    """Build the win zip, download darwin, regenerate dual manifest + SHA256SUMS, verify both. Returns paths."""
    version = a["version"]
    win_zip = DIST / a["win_zip"]
    darwin_tar = DIST / a["darwin_tar"]

    print("\n[build] win32-x64 runtime (downloads Node/JDK/Python, npm-installs lunar-javascript, bakes hardened launchers)…")
    run(["uv", "run", "python", "scripts/build_runtime_release_windows.py"], cwd=SKILL_ROOT)
    if not win_zip.is_file():
        sys.exit(f"build did not produce {win_zip}")

    print("\n[darwin] downloading the macOS archive from the release…")
    run(["gh", "release", "download", a["tag"], "--repo", REPO, "--pattern", a["darwin_tar"],
         "--dir", str(DIST), "--clobber"])

    base = f"https://github.com/{REPO}/releases/latest/download"
    print("\n[manifest] regenerating dual-platform runtime-manifest.json…")
    run(["uv", "run", "python", "scripts/generate_release_manifest.py",
         "--version", version,
         "--darwin-archive", f"dist/runtime/{a['darwin_tar']}", "--darwin-url", f"{base}/{a['darwin_tar']}",
         "--windows-archive", f"dist/runtime/{a['win_zip']}", "--windows-url", f"{base}/{a['win_zip']}",
         "--output", "dist/runtime/runtime-manifest.json"], cwd=SKILL_ROOT)

    print("\n[checksums] writing SHA256SUMS.txt over both archives…")
    import hashlib
    lines = []
    for name in (a["darwin_tar"], a["win_zip"]):
        digest = hashlib.sha256((DIST / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    (DIST / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join("  " + ln for ln in lines))

    print("\n[verify] verify_runtime_release.py over both archives + manifest…")
    run(["uv", "run", "python", "scripts/verify_runtime_release.py",
         "--darwin-archive", f"dist/runtime/{a['darwin_tar']}",
         "--windows-archive", f"dist/runtime/{a['win_zip']}",
         "--manifest", "dist/runtime/runtime-manifest.json"], cwd=SKILL_ROOT)
    return win_zip, darwin_tar


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Windows-side release sync for Horosa Skill.")
    ap.add_argument("--upload", action="store_true", help="upload the built win zip + dual manifest + SHA256SUMS to the release (--clobber)")
    ap.add_argument("--check", action="store_true", help="detect-only: report completeness and exit; build nothing")
    args = ap.parse_args(argv)

    tag = latest_tag()
    if not tag:
        sys.exit("could not resolve the latest release tag via gh")
    a = assess(tag)
    print(f"latest release: {tag}")
    print(f"  win32 zip asset:     {'yes' if a['has_win_zip'] else 'NO'}")
    print(f"  darwin tar asset:    {'yes' if a['has_darwin_tar'] else 'NO'}")
    print(f"  manifest asset:      {'yes' if a['has_manifest_asset'] else 'NO'}")
    print(f"  manifest platforms:  {a['manifest_platforms']}")

    if is_complete(a):
        print(f"\n[OK] {tag} already has the Windows half + a dual-platform manifest — in sync, nothing to do.")
        return 0

    print(f"\n[GAP] {tag} is missing its Windows half (this is the recurring darwin-only-latest failure).")
    if args.check:
        print("      (--check) detect-only; not building. Re-run without --check to build + verify.")
        return 2

    # Building needs the local tree synced to the release commit (version is stamped from pyproject).
    local_version = read_pyproject_version()
    if local_version != a["version"]:
        sys.exit(
            f"local repo pyproject is {local_version} but latest release is {a['version']}.\n"
            f"Run `git pull` to sync to the {tag} commit before building (the builder stamps the version "
            f"from pyproject.toml), then re-run this script."
        )

    win_zip, darwin_tar = build_and_verify(a)
    print(f"\n[built+verified] {win_zip.name} and dual-platform manifest are ready and pass verify_runtime_release.py.")

    if not args.upload:
        print("\n[stop] safe mode: not uploading. Re-run with --upload to publish to the release:")
        print(f"       python horosa-skill/scripts/sync_windows_release.py --upload")
        return 0

    print("\n[upload] uploading win zip + dual manifest + SHA256SUMS to the release (--clobber)…")
    run(["gh", "release", "upload", tag, "--repo", REPO,
         str(win_zip), str(DIST / "runtime-manifest.json"), str(DIST / "SHA256SUMS.txt"), "--clobber"])

    after = assess(tag)
    if is_complete(after):
        print(f"\n[DONE] {tag} now has both platforms + a dual-platform manifest. Windows install restored.")
        print("       (Tip: `horosa-skill install --force` + `doctor` to confirm, and the release-completeness "
              "guard should now go green.)")
        return 0
    print(f"\n[WARN] post-upload re-check still incomplete: {after['manifest_platforms']} — "
          "GitHub CDN may be lagging on releases/latest/download; re-check in a minute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
