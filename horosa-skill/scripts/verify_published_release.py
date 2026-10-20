#!/usr/bin/env python3
"""Is the PUBLISHED `latest` release complete for every contracted platform? (release-completeness.yml)

Guards against the recurring "latest release is missing its Windows half" failure (v0.10.0 shipped with no
runtime-manifest.json; v0.11.0 / v0.12.0 with a darwin-only manifest). Checks, against the downloaded manifest and
SHA256SUMS.txt of the release:

* every SHA256SUMS line equals GitHub's own sha256 `digest` of the uploaded asset (v0.38.1 R15 — no 700 MB downloads);
* the manifest version matches the tag;
* every platform in contracts/release_platforms.json (`since`-gated) is present with url / sha256 / archive_type,
  carries the contract's `min_os` (from 0.38.1 on, R16), is pinned to THIS tag (pin-forward = users get an older
  runtime), answers HEAD 200 with a Content-Length equal to the manifest `size`, and is listed in SHA256SUMS.txt.

Until v0.41.1 this lived as ~75 lines of heredoc Python inside the workflow, where nothing could test it; the checks
and messages are unchanged. Stdlib only (the workflow runs the runner's python3).

    python3 horosa-skill/scripts/verify_published_release.py --tag vX.Y.Z --repo OWNER/NAME \
        --manifest manifest.json --sums SHA256SUMS.txt
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

PKG_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = PKG_ROOT / "contracts" / "release_platforms.json"


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", value)[:3])


def expected_platforms(contract: dict, version: str) -> list[str]:
    return [key for key, entry in contract["platforms"].items() if version_tuple(entry["since"]) <= version_tuple(version)]


def asset_digests(repo: str, tag: str) -> dict[str, str]:
    """GitHub's sha256 `digest` per uploaded asset name (assets without one are left out)."""
    api = subprocess.run(
        ["gh", "api", f"repos/{repo}/releases/tags/{tag}", "--jq", '.assets[] | "\\(.name) \\(.digest // \"\")"'],
        capture_output=True, text=True, check=False,
    ).stdout
    return {
        line.split()[0]: line.split()[1].removeprefix("sha256:")
        for line in api.splitlines()
        if len(line.split()) == 2 and line.split()[1]
    }


def head(url: str) -> tuple[int, str | None]:
    """HTTP status and Content-Length of a HEAD request; raises when the URL is not reachable."""
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.headers.get("Content-Length")


def manifest_problems(
    tag: str,
    manifest: dict,
    contract: dict,
    sums: str,
    digests: dict[str, str],
    probe: Callable[[str], tuple[int, str | None]] = head,
) -> list[str]:
    version = tag.lstrip("v")
    expected = expected_platforms(contract, version)
    errors: list[str] = []
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        listed_sha, name = parts
        if name in digests and digests[name] != listed_sha:
            errors.append(f"SHA256SUMS.txt says {name} = {listed_sha[:12]}… but the uploaded asset's digest is {digests[name][:12]}…")
    require_min_os = version_tuple(version) >= (0, 38, 1)
    got_version = manifest.get("version")
    if not got_version:
        errors.append("manifest has no `version`")
    elif tag not in (got_version, f"v{got_version}"):
        errors.append(f"manifest version {got_version!r} does not match latest tag {tag!r}")

    platforms = manifest.get("platforms") or {}
    for key in expected:
        entry = platforms.get(key)
        asset = contract["platforms"][key]["asset"].format(version=version)
        if not isinstance(entry, dict):
            errors.append(f"manifest is missing the `{key}` platform (the v0.11.0/v0.12.0 half-release failure)")
            continue
        for field in ("url", "sha256", "archive_type"):
            val = entry.get(field)
            if not isinstance(val, str) or not val.strip():
                errors.append(f"{key}.{field} is missing or empty")
        if require_min_os and entry.get("min_os") != contract["platforms"][key].get("min_os"):
            errors.append(f"{key}.min_os is {entry.get('min_os')!r}, contract says {contract['platforms'][key].get('min_os')!r}")
        url = entry.get("url")
        if isinstance(url, str) and url.strip():
            pinned = re.search(r"/releases/download/(v[^/]+)/", url)
            if pinned and pinned.group(1) != tag:
                errors.append(f"{key} manifest url is pinned to {pinned.group(1)}, not {tag} (pin-forward: users would install an older runtime): {url}")
            try:
                status, length = probe(url)
                if status != 200:
                    errors.append(f"{key} archive url returned HTTP {status}: {url}")
                size = entry.get("size")
                if isinstance(size, int) and length and int(length) != size:
                    errors.append(f"{key} manifest size {size} != Content-Length {length} for {url}")
            except Exception as exc:  # noqa: BLE001 - any failure means the asset is not downloadable
                errors.append(f"{key} archive url is not reachable ({exc}): {url}")
        if asset not in sums:
            errors.append(f"SHA256SUMS.txt does not list {asset}")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--tag", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--sums", type=Path, required=True)
    args = ap.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    sums = args.sums.read_text(encoding="utf-8")
    errors = manifest_problems(args.tag, manifest, contract, sums, asset_digests(args.repo, args.tag))
    if errors:
        print("::error::latest release is INCOMPLETE:")
        for e in errors:
            print(f"::error::  - {e}")
        return 1
    expected = expected_platforms(contract, args.tag.lstrip("v"))
    print(f"OK: latest release {args.tag} carries every contracted platform {expected}, archives reachable, sizes/tags/checksums consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
