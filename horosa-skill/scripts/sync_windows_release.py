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
import re
import subprocess
import sys

# Windows 控制台默认 cp1252/cp936：脚本自己 print 的中文会抛 UnicodeEncodeError 并让脚本 exit 1
# （v0.38.0 的 repack 脚本在「打印成功信息」那一步失败过）。统一在入口把两条流改成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")
import urllib.request
from pathlib import Path

REPO = "Horace-Maxwell/horosa-skill"
SKILL_ROOT = Path(__file__).resolve().parents[1]          # horosa-skill/
REPO_ROOT = SKILL_ROOT.parent                              # repo root
SCRIPTS = SKILL_ROOT / "scripts"
DIST = SKILL_ROOT / "dist" / "runtime"
PLATFORMS = ("darwin-arm64", "win32-x64")
CONTRACT_PATH = SKILL_ROOT / "contracts" / "release_platforms.json"
WHEEL_SINCE = "0.38.0"  # the pure-Python wheel became a required asset with the zero-install path (B3)


def _vtuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version)[:3])


def load_platform_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def expected_platforms(version: str, contract: dict | None = None) -> list[str]:
    """Platform keys a release of `version` must ship (contracts/release_platforms.json `since` gate)."""
    contract = contract or load_platform_contract()
    return [key for key, entry in contract["platforms"].items() if _vtuple(entry["since"]) <= _vtuple(version)]


def platform_asset(key: str, version: str, contract: dict | None = None) -> str:
    contract = contract or load_platform_contract()
    return contract["platforms"][key]["asset"].format(version=version)


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
    manifest = fetch_manifest()
    return list(manifest.get("platforms", {}).keys()) if manifest else None


def fetch_manifest(tag: str | None = None, *, draft: bool = False) -> dict | None:
    """The release manifest: `releases/latest/download` for the public latest, `gh release download` for a
    specific (possibly draft) tag. None when absent / unparseable."""
    try:
        if tag is None or not draft:
            url = f"https://github.com/{REPO}/releases/{'latest/download' if tag is None else f'download/{tag}'}/runtime-manifest.json"
            with urllib.request.urlopen(url, timeout=30) as resp:  # follows GitHub's 302 to the asset
                return json.loads(resp.read().decode("utf-8"))
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["gh", "release", "download", tag, "--repo", REPO, "--pattern", "runtime-manifest.json",
                            "--dir", tmp, "--clobber"], check=True, capture_output=True)
            return json.loads((Path(tmp) / "runtime-manifest.json").read_text(encoding="utf-8"))
    except Exception:
        return None


_PINNED_URL = re.compile(r"/releases/download/(v[^/]+)/")


def assess_from(tag: str, assets: list[str], manifest: dict | None, contract: dict | None = None) -> dict:
    """Pure completeness verdict for one release from its asset names + manifest (v0.38.0 A3, contract-driven)."""
    contract = contract or load_platform_contract()
    version = tag.lstrip("v")
    expected = expected_platforms(version, contract)
    platforms_in_manifest = (manifest or {}).get("platforms") or {}
    per_platform: dict[str, dict] = {}
    for key in expected:
        asset = platform_asset(key, version, contract)
        entry = platforms_in_manifest.get(key) or {}
        url = str(entry.get("url") or "")
        pinned = _PINNED_URL.search(url)
        per_platform[key] = {
            "asset": asset,
            "present": asset in assets,
            "in_manifest": bool(entry),
            # a manifest that points at another tag's archive is the pin-forward failure; `latest/download`
            # URLs (pre-A3 releases) cannot be judged from the manifest alone and are accepted here
            "url_tag_matches": (pinned.group(1) == tag) if pinned else (bool(url) and "/latest/download/" in url),
            "url": url,
        }
    wheel_required = _vtuple(version) >= _vtuple(WHEEL_SINCE)
    wheel = f"horosa_skill-{version}-py3-none-any.whl"
    return {
        "tag": tag, "version": version, "expected_platforms": expected, "platforms": per_platform,
        "has_manifest_asset": "runtime-manifest.json" in assets,
        "has_mcpb": f"horosa-skill-{version}.mcpb" in assets,
        "wheel_required": wheel_required, "has_wheel": wheel in assets, "wheel": wheel,
        "manifest_platforms": list(platforms_in_manifest.keys()),
        "manifest_dual": all(p in platforms_in_manifest for p in expected),
        # legacy keys kept for callers/tests written against the two-platform shape
        "has_win_zip": per_platform.get("win32-x64", {}).get("present", False),
        "has_darwin_tar": per_platform.get("darwin-arm64", {}).get("present", False),
        "win_zip": f"horosa-runtime-win32-x64-v{version}.zip",
        "darwin_tar": f"horosa-runtime-darwin-arm64-v{version}.tar.gz",
    }


def assess(tag: str, *, draft: bool = False) -> dict:
    """Live verdict for `tag` (a published tag's manifest is fetched by tag URL; a draft's via gh)."""
    return assess_from(tag, release_assets(tag), fetch_manifest(tag, draft=draft))


def gaps(a: dict) -> list[str]:
    """Human-readable list of what is missing; empty = complete."""
    missing: list[str] = []
    for key, info in a["platforms"].items():
        if not info["present"]:
            missing.append(f"{key} archive ({info['asset']})")
        if not info["in_manifest"]:
            missing.append(f"{key} in manifest")
        elif not info["url_tag_matches"]:
            missing.append(f"{key} manifest url pinned to another tag ({info['url']})")
    if not a["has_manifest_asset"]:
        missing.append("runtime-manifest.json asset")
    if not a["has_mcpb"]:
        missing.append(f"horosa-skill-{a['version']}.mcpb")
    if a["wheel_required"] and not a["has_wheel"]:
        missing.append(a["wheel"])
    return missing


def is_complete(a: dict) -> bool:
    return not gaps(a)


def preflight_vendor_sources() -> None:
    """Refuse to build off a stale `vendor/runtime-source`.

    The Windows payload is built from the local vendored tree, which is gitignored — nothing in a
    `git pull` refreshes it. Both freshness guards existed but only ran in `release.yml`, never on
    the path that actually builds the Windows half, so a stale tree would ship silently (engines
    lagging the release's upstream sync). Version equality alone is NOT enough: upstream adds export
    keys under a "只加键纪律" (key-only addition) rule *without* bumping AI_EXPORT_SETTINGS_VERSION,
    so `verify_vendor_runtime_sources.py` can pass on a tree that is genuinely behind — only
    `verify_export_contract_mirror.py`'s per-key coverage catches that. Both, before every build.
    """
    print("\n[preflight] vendored runtime-source freshness (required-paths + export-contract mirror)…")
    for script, hint in (
        ("verify_vendor_runtime_sources.py", "required vendored inputs are missing"),
        ("verify_export_contract_mirror.py", "the vendored upstream tree is behind this release"),
    ):
        try:
            run(["uv", "run", "python", f"scripts/{script}"], cwd=SKILL_ROOT)
        except subprocess.CalledProcessError:
            sys.exit(
                f"\n[STOP] {script} failed — {hint}.\n"
                "       Building now would ship a stale Windows payload. Re-sync the vendored tree from a\n"
                "       current 星阙 workspace (sync_vendored_runtime_sources.sh, or the robocopy equivalent\n"
                "       on Windows — see AGENTS.md §7), then re-run this script."
            )


def build_and_verify(a: dict) -> tuple[Path, Path]:
    """Build the win zip, download darwin, regenerate dual manifest + SHA256SUMS, verify both. Returns paths."""
    version = a["version"]
    win_zip = DIST / a["win_zip"]
    darwin_tar = DIST / a["darwin_tar"]

    preflight_vendor_sources()

    print("\n[build] win32-x64 runtime (downloads Node/JDK/Python, npm-installs lunar-javascript, bakes hardened launchers)…")
    run(["uv", "run", "python", "scripts/build_runtime_release_windows.py"], cwd=SKILL_ROOT)
    if not win_zip.is_file():
        sys.exit(f"build did not produce {win_zip}")

    print("\n[darwin] downloading the macOS archive from the release…")
    run(["gh", "release", "download", a["tag"], "--repo", REPO, "--pattern", a["darwin_tar"],
         "--dir", str(DIST), "--clobber"])

    base = f"https://github.com/{REPO}/releases/download/{a['tag']}"  # tag-pinned (v0.38.0 A3)
    print("\n[manifest] regenerating dual-platform runtime-manifest.json…")
    run(["uv", "run", "python", "scripts/generate_release_manifest.py",
         "--version", version, "--url-base", base,
         "--darwin-archive", f"dist/runtime/{a['darwin_tar']}",
         "--windows-archive", f"dist/runtime/{a['win_zip']}",
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
    ap = argparse.ArgumentParser(description="Release completeness detector (+ Windows-box build fallback) for Horosa Skill.")
    ap.add_argument("--upload", action="store_true", help="upload the built win zip + dual manifest + SHA256SUMS to the release (--clobber)")
    ap.add_argument("--check", action="store_true", help="detect-only: report completeness and exit; build nothing")
    ap.add_argument("--tag", default=None, help="assess this tag instead of the public latest (e.g. a draft the pipeline is filling)")
    ap.add_argument("--draft", action="store_true", help="the --tag release is a draft: read its manifest via gh instead of the public URL")
    args = ap.parse_args(argv)

    tag = args.tag or latest_tag()
    if not tag:
        sys.exit("could not resolve the latest release tag via gh")
    a = assess(tag, draft=args.draft)
    print(f"{'release' if args.tag else 'latest release'}: {tag}  (expected platforms: {', '.join(a['expected_platforms'])})")
    for key, info in a["platforms"].items():
        print(f"  {key:14s} archive: {'yes' if info['present'] else 'NO':3s}  manifest: {'yes' if info['in_manifest'] else 'NO':3s}"
              f"  url tag ok: {'yes' if info['url_tag_matches'] else 'NO'}")
    print(f"  manifest asset:      {'yes' if a['has_manifest_asset'] else 'NO'}")
    print(f"  mcpb asset:          {'yes' if a['has_mcpb'] else 'NO'}")
    print(f"  wheel asset:         {'yes' if a['has_wheel'] else ('NO' if a['wheel_required'] else 'n/a (< 0.38.0)')}")

    missing = gaps(a)
    if not missing:
        print(f"\n[OK] {tag} carries every expected platform + manifest + mcpb{' + wheel' if a['wheel_required'] else ''} — complete.")
        return 0

    print(f"\n[GAP: {', '.join(missing)}]")
    if args.check:
        print("      (--check) detect-only; not building. The hosted pipeline (release-runtime.yml) fills the Windows half; "
              "re-run without --check only on a Windows box as the vendor-mode fallback.")
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
        print(f"\n[DONE] {tag} now carries every expected platform + manifest. Windows install restored.")
        print("       (Tip: `horosa-skill install --force` + `doctor` to confirm, and the release-completeness "
              "guard should now go green.)")
        return 0
    print(f"\n[WARN] post-upload re-check still incomplete: {gaps(after)} — "
          "GitHub CDN may be lagging on releases/latest/download; re-check in a minute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
