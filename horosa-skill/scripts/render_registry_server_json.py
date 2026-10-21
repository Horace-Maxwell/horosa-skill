#!/usr/bin/env python3
"""Render the server.json to publish to the official MCP Registry for ONE public release (v0.41.0).

Why not publish the checked-in server.json as-is:
- the `.mcpb` sha is backfilled in a commit AFTER the tag (mcpb packing is not byte-reproducible; v0.40.2: tag d86fc2c,
  pin f4661ea), so the file at the tag carries a stale digest — clients verify `fileSha256` before install;
- registry versions are immutable: whatever goes out first stays out.
So the digest comes from the release's own `SHA256SUMS.txt`, the identifier is the tag-pinned asset URL, and the
registry's publish-time HEAD (200, or 3xx + Location, no redirect following) is repeated here before anything is sent.
The checked-in name / description / `_meta` stay the single source; `verify_server_json.server_json_problems` judges
the rendered file exactly like the checked-in one.

    python scripts/render_registry_server_json.py --tag v0.40.2 --out /tmp/server.json
    python scripts/render_registry_server_json.py --tag v0.40.2 --sums SHA256SUMS.txt --no-head --out x.json   # offline

Stdlib only (runs on a bare ubuntu runner before any `uv sync`).
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
SERVER_JSON = ROOT / "server.json"
_TAG = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)$")

_spec = importlib.util.spec_from_file_location("verify_server_json", Path(__file__).resolve().parent / "verify_server_json.py")
assert _spec is not None and _spec.loader is not None
_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_guard)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003 - the registry does not follow redirects either
        return None


def head_status(url: str, *, timeout: float = 10.0) -> tuple[int, str | None]:
    """(status, Location) for a HEAD without following redirects — the registry's own publish-time probe."""
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, method="HEAD"), timeout=timeout) as response:
            return response.status, response.headers.get("Location")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Location") if exc.headers else None


def sums_digest(sums_text: str, filename: str) -> str | None:
    for line in sums_text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == filename and re.fullmatch(r"[a-f0-9]{64}", parts[0]):
            return parts[0]
    return None


def render(checked_in: dict, *, tag: str, sums_text: str) -> tuple[dict, list[str]]:
    """(rendered payload, problems). Pure: no network."""
    match = _TAG.match(tag)
    if not match:
        return checked_in, [f"tag must look like vX.Y.Z, got {tag!r}"]
    version = match.group("version")
    repo_url = str((checked_in.get("repository") or {}).get("url") or "").rstrip("/")
    payload = copy.deepcopy(checked_in)
    payload["version"] = version
    problems: list[str] = []
    # publisher-provided 的 install / start 命令钉着 main 的版本；给更早的公开版补登记时（main 已经 bump），它们要跟着 tag 走。
    old = str(checked_in.get("version") or "")
    meta = (payload.get("_meta") or {}).get("io.modelcontextprotocol.registry/publisher-provided")
    if old and old != version and isinstance(meta, dict):
        for key in ("install", "start"):
            if isinstance(meta.get(key), list):
                meta[key] = [str(line).replace(f"v{old}/", f"v{version}/").replace(f"-{old}-py3", f"-{version}-py3") for line in meta[key]]
    mcpb = [p for p in payload.get("packages") or [] if p.get("registryType") == "mcpb"]
    if len(mcpb) != 1:
        problems.append(f"expected exactly one mcpb package, found {len(mcpb)}")
    for package in mcpb:
        bundle = f"horosa-skill-{version}.mcpb"
        digest = sums_digest(sums_text, bundle)
        if digest is None:
            problems.append(f"SHA256SUMS.txt of {tag} has no line for {bundle}")
            continue
        package["identifier"] = f"{repo_url}/releases/download/{tag}/{bundle}"
        package["fileSha256"] = digest
        if "version" in package:
            package["version"] = version
        if checked_in.get("version") == version:
            declared = next((p.get("fileSha256") for p in checked_in.get("packages") or [] if p.get("registryType") == "mcpb"), None)
            if declared != digest:
                # main 上的回填与发布资产不一致 = 有人重打过包；release-completeness 同样会红。先修 main，再上注册表。
                problems.append(f"checked-in fileSha256 {str(declared)[:12]}… != published {digest[:12]}… for {bundle}")
    payload_text = json.dumps(payload, ensure_ascii=False)
    for stale in re.findall(r"/releases/download/v(\d+\.\d+\.\d+)/", payload_text):
        if stale != version:
            problems.append(f"rendered server.json still points at v{stale} (expected {tag})")
            break
    problems += _guard.server_json_problems(payload)
    return payload, problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", required=True, help="public release tag, e.g. v0.40.2")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--sums", type=Path, help="local SHA256SUMS.txt instead of downloading the release's copy")
    ap.add_argument("--no-head", action="store_true", help="skip the asset HEAD probe (offline tests only)")
    args = ap.parse_args(argv)
    checked_in = json.loads(SERVER_JSON.read_text(encoding="utf-8"))
    repo_url = str((checked_in.get("repository") or {}).get("url") or "").rstrip("/")
    if args.sums is not None:
        sums_text = args.sums.read_text(encoding="utf-8")
    else:
        url = f"{repo_url}/releases/download/{args.tag}/SHA256SUMS.txt"
        with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed https GitHub URL
            sums_text = response.read().decode("utf-8")
    payload, problems = render(checked_in, tag=args.tag, sums_text=sums_text)
    if not problems and not args.no_head:
        for package in payload.get("packages") or []:
            status, location = head_status(str(package.get("identifier")))
            if not (status == 200 or (300 <= status < 400 and location)):
                problems.append(f"HEAD {package.get('identifier')} → {status} (the registry needs 200 or a redirect; is the release still a draft?)")
    if problems:
        print("registry server.json: FAIL\n- " + "\n- ".join(problems), file=sys.stderr)
        return 1
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    package = payload["packages"][0]
    print(f"registry server.json: ok → {args.out} ({payload['name']} {payload['version']}, sha {package['fileSha256'][:12]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
