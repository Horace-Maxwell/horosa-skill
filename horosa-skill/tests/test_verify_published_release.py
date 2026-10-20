"""verify_published_release.py — the release-completeness checks, now testable (v0.41.1).

They used to be ~75 lines of heredoc Python inside release-completeness.yml that no test could reach; each case below
is a shape of incomplete release the workflow is there to catch.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("verify_published_release", PKG_ROOT / "scripts" / "verify_published_release.py")
vpr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vpr)

CONTRACT = json.loads((PKG_ROOT / "contracts" / "release_platforms.json").read_text(encoding="utf-8"))
TAG = "v9.9.9"
VERSION = "9.9.9"


def _complete() -> tuple[dict, str, dict]:
    platforms, sums, digests = {}, [], {}
    for i, (key, entry) in enumerate(CONTRACT["platforms"].items()):
        asset = entry["asset"].format(version=VERSION)
        sha = f"{i:02d}" * 32
        platforms[key] = {
            "url": f"https://github.com/o/r/releases/download/{TAG}/{asset}",
            "sha256": sha, "archive_type": "zip", "size": 100 + i, "min_os": entry.get("min_os"),
        }
        sums.append(f"{sha}  {asset}")
        digests[asset] = sha
    return {"version": VERSION, "platforms": platforms}, "\n".join(sums) + "\n", digests


def _probe_ok(manifest: dict):
    sizes = {e["url"]: e["size"] for e in manifest["platforms"].values()}
    return lambda url: (200, str(sizes[url]))


def test_a_complete_release_passes() -> None:
    manifest, sums, digests = _complete()
    assert vpr.manifest_problems(TAG, manifest, CONTRACT, sums, digests, _probe_ok(manifest)) == []


def test_each_incomplete_shape_is_reported() -> None:
    manifest, sums, digests = _complete()
    key, *_ = list(manifest["platforms"])
    first = manifest["platforms"][key]
    asset = CONTRACT["platforms"][key]["asset"].format(version=VERSION)

    missing = json.loads(json.dumps(manifest))
    del missing["platforms"][key]
    assert any("missing the `" in e for e in vpr.manifest_problems(TAG, missing, CONTRACT, sums, digests, _probe_ok(manifest)))

    pinned = json.loads(json.dumps(manifest))
    pinned["platforms"][key]["url"] = first["url"].replace(TAG, "v9.9.8")
    probe = lambda url: (200, None)  # noqa: E731
    assert any("pin-forward" in e for e in vpr.manifest_problems(TAG, pinned, CONTRACT, sums, digests, probe))

    tampered = dict(digests, **{asset: "ff" * 32})
    assert any("SHA256SUMS.txt says" in e for e in vpr.manifest_problems(TAG, manifest, CONTRACT, sums, tampered, _probe_ok(manifest)))

    old_os = json.loads(json.dumps(manifest))
    old_os["platforms"][key]["min_os"] = "0.0"
    assert any(".min_os is" in e for e in vpr.manifest_problems(TAG, old_os, CONTRACT, sums, digests, _probe_ok(manifest)))

    assert any("Content-Length" in e for e in vpr.manifest_problems(TAG, manifest, CONTRACT, sums, digests, lambda url: (200, "1")))
    assert any("HTTP 404" in e for e in vpr.manifest_problems(TAG, manifest, CONTRACT, sums, digests, lambda url: (404, None)))

    def unreachable(url):
        raise OSError("connection refused")

    assert any("not reachable" in e for e in vpr.manifest_problems(TAG, manifest, CONTRACT, sums, digests, unreachable))
    assert any("does not list" in e for e in vpr.manifest_problems(TAG, manifest, CONTRACT, "", digests, _probe_ok(manifest)))
    assert any("does not match latest tag" in e for e in vpr.manifest_problems("v9.9.10", manifest, CONTRACT, sums, digests, _probe_ok(manifest)))


def test_platforms_not_yet_contracted_for_an_old_version_are_not_required() -> None:
    manifest, sums, digests = _complete()
    expected_now = vpr.expected_platforms(CONTRACT, VERSION)
    expected_old = vpr.expected_platforms(CONTRACT, "0.1.0")
    assert set(expected_old) <= set(expected_now) and len(expected_old) < len(expected_now)
