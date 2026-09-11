#!/usr/bin/env python3
"""Derive the runtime Python dependency lock from a verified darwin-arm64 seed archive (v0.38.0 A1).

Why a lock derived from the *seed* and not from upstream's requirements file: upstream installs
`scripts/requirements/mac-python.txt` with floating specifiers on the maintainer's Mac, so the seed
carries e.g. numpy 2.4.6 against a `numpy==2.4.2` pin. The seed is the artifact that passed the live
suite; a derived payload (win32-x64) must carry the *same* dist set at the *same* versions:

    pure(seed)   — copied byte for byte
    native(seed) — re-fetched as binary wheels for the target platform (cp312, win_amd64)

Usage:
    gen_runtime_python_lock.py --seed dist/runtime/horosa-runtime-darwin-arm64-v0.36.0.tar.gz --write
    gen_runtime_python_lock.py --seed <tar.gz> --check-index --platforms win32-x64   # A0 availability probe

`--check-index` asks PyPI's JSON API (no downloads) which wheel exists for every native dist on
each target platform and prints the filename — that is the evidence for `contracts/runtime_toolchain.json`
`min_os` / tag choices and for any `platform_overrides`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
DEFAULT_LOCK = PKG_ROOT / "contracts" / "runtime_python_lock.json"
SITE_PACKAGES_RE = re.compile(r"^runtime-payload/runtime/mac/python/lib/python(?P<py>\d+\.\d+)/site-packages/(?P<dist>[^/]+)\.dist-info/(?P<file>METADATA|RECORD)$")
NATIVE_SUFFIXES = (".so", ".dylib", ".pyd")
# Dev-only / policy exclusions: present in some seeds, never part of a derived payload's dep set.
EXCLUDED = {
    "pip": "installer tooling, not a runtime dependency",
    "setuptools": "installer tooling, not a runtime dependency",
    "wheel": "installer tooling, not a runtime dependency",
    "pytest": "dev-only",
    "iniconfig": "dev-only (pytest)",
    "pluggy": "dev-only (pytest)",
    "plotly": "stripped by package_runtime_payload.sh (~40 MB, only streamlit's lazy import wants it)",
    "scipy": "size red line (AGENTS §6): never shipped, kintaiyi game_theory stays opt-in",
    "scikit-learn": "size red line (AGENTS §6): never shipped",
}
PLATFORM_TAGS = {
    "win32-x64": ["win_amd64"],
    "darwin-x64": ["macosx_12_0_x86_64", "macosx_11_0_x86_64", "macosx_10_13_x86_64", "macosx_10_9_x86_64"],
}


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_seed_dists(archive: Path) -> tuple[str, dict[str, dict[str, object]]]:
    """Return (python_minor, {name: {"version", "native", "files"}}) from the seed's dist-info entries."""
    dists: dict[str, dict[str, object]] = {}
    python_minor = ""
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            match = SITE_PACKAGES_RE.match(member.name)
            if not match:
                continue
            python_minor = match.group("py")
            key = match.group("dist")
            entry = dists.setdefault(key, {"name": "", "version": "", "native": False, "native_files": []})
            handle = tar.extractfile(member)
            if handle is None:
                continue
            text = handle.read().decode("utf-8", errors="replace")
            if match.group("file") == "METADATA":
                for line in text.splitlines():
                    if line.startswith("Name:") and not entry["name"]:
                        entry["name"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Version:") and not entry["version"]:
                        entry["version"] = line.split(":", 1)[1].strip()
                    elif line == "":
                        break
            else:
                for line in text.splitlines():
                    path = line.split(",", 1)[0]
                    if path.endswith(NATIVE_SUFFIXES):
                        entry["native"] = True
                        entry["native_files"].append(path)
    by_name: dict[str, dict[str, object]] = {}
    for key, entry in dists.items():
        name = entry["name"] or key.rsplit("-", 1)[0]
        version = entry["version"] or key.rsplit("-", 1)[-1]
        by_name[_normalize(str(name))] = {"name": str(name), "version": str(version), "native": bool(entry["native"]),
                                         "native_files": len(entry["native_files"])}
    return python_minor, by_name


def build_lock(archive: Path) -> dict[str, object]:
    python_minor, dists = read_seed_dists(archive)
    digest = hashlib.sha256()
    with archive.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    pure = sorted(f"{d['name']}=={d['version']}" for n, d in dists.items() if not d["native"] and n not in EXCLUDED)
    native = sorted(f"{d['name']}=={d['version']}" for n, d in dists.items() if d["native"] and n not in EXCLUDED)
    excluded_present = sorted(n for n in dists if n in EXCLUDED)
    return {
        "schema": 1,
        "python": python_minor,
        "seed": {"archive": archive.name, "sha256": digest.hexdigest(),
                 "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "pure": pure,
        "native": native,
        "excluded": {name: EXCLUDED[name] for name in EXCLUDED},
        "excluded_present_in_seed": excluded_present,
        "platform_tags": PLATFORM_TAGS,
        # name -> version to fetch instead of the seed's, only when the seed's version ships no wheel for
        # that platform; every entry must be explained in docs/LESSONS.md (verify_runtime_python_lock.py).
        "platform_overrides": {"win32-x64": {}},
        # filled by --check-index: per platform, name -> PyPI wheel filename or "sdist" (build on the runner)
        "wheel_sources": {},
    }


_WHEEL_RE = re.compile(r"^(?P<name>[^-]+)-(?P<ver>[^-]+)(?:-(?P<build>\d[^-]*))?-(?P<py>[^-]+)-(?P<abi>[^-]+)-(?P<plat>[^-]+)\.whl$")


def _python_tag_ok(py_tag: str, abi_tag: str, python_minor: str) -> bool:
    """Accept cp312-cp312, cp3xx-abi3 (xx ≤ 12), py3-none / py2.py3-none for a CPython `python_minor` target."""
    target = int(python_minor.split(".")[1])
    for tag in py_tag.split("."):
        if tag in {"py3", "py2"} and abi_tag == "none":
            return True
        m = re.fullmatch(r"cp3(\d+)", tag)
        if not m:
            continue
        minor = int(m.group(1))
        if abi_tag == f"cp3{minor}" and minor == target:
            return True
        if abi_tag == "abi3" and minor <= target:
            return True
        if abi_tag == "none" and minor <= target:
            return True
    return False


def _platform_tag_ok(plat_tag: str, wanted: list[str]) -> bool:
    for tag in plat_tag.split("."):
        if tag in wanted or tag == "any":
            return True
        # macOS: any deployment target at or below what we accept, same arch (or universal2)
        m = re.fullmatch(r"macosx_(\d+)_(\d+)_(x86_64|arm64|universal2)", tag)
        if m:
            arch = m.group(3)
            for want in wanted:
                w = re.fullmatch(r"macosx_(\d+)_(\d+)_(x86_64|arm64)", want)
                if w and arch in {w.group(3), "universal2"} and (int(m.group(1)), int(m.group(2))) <= (int(w.group(1)), int(w.group(2))):
                    return True
    return False


def pypi_wheels(name: str, version: str) -> list[str]:
    """Wheel filenames PyPI serves for name==version (JSON API; no download, no pip)."""
    import urllib.request

    url = f"https://pypi.org/pypi/{name}/{version}/json"
    with urllib.request.urlopen(url, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    return [entry["filename"] for entry in data.get("urls", []) if entry.get("packagetype") == "bdist_wheel"]


def matching_wheel(filenames: list[str], python_minor: str, platform_tags: list[str]) -> str:
    for filename in filenames:
        m = _WHEEL_RE.match(filename)
        if m and _python_tag_ok(m.group("py"), m.group("abi"), python_minor) and _platform_tag_ok(m.group("plat"), platform_tags):
            return filename
    return ""


def check_index(lock: dict[str, object], platforms: list[str]) -> int:
    """Ask PyPI which wheel exists for every native dist on each target platform; returns the count of misses.

    Uses the PyPI JSON API rather than `pip download` (whose `--dry-run` does not exist in pip 25) — no
    downloads, no pip on the box, same answer: the wheel filename a derive step would fetch. Records the
    verdict in `lock["wheel_sources"][platform] = {name: "<wheel filename>" | "sdist"}` so the derive step
    knows which dists it must BUILD on the target runner (pyswisseph / sxtwl ship no cp312 Windows wheels).
    """
    misses = 0
    python_minor = str(lock["python"])
    sources: dict[str, dict[str, str]] = lock.setdefault("wheel_sources", {})  # type: ignore[assignment]
    for platform_key in platforms:
        tags = list(lock["platform_tags"][platform_key])
        overrides = (lock.get("platform_overrides") or {}).get(platform_key, {})
        print(f"== {platform_key}: tags={tags} python={python_minor}")
        verdicts: dict[str, str] = {}
        for requirement in lock["native"]:
            name, _, version = requirement.partition("==")
            version = overrides.get(_normalize(name), version)
            try:
                wheels = pypi_wheels(name, version)
            except Exception as exc:  # noqa: BLE001 - report, keep going
                misses += 1
                print(f"   MISS {name}=={version}  (pypi lookup failed: {exc})")
                continue
            wheel = matching_wheel(wheels, python_minor, tags)
            if wheel:
                verdicts[_normalize(name)] = wheel
                print(f"   ok   {name}=={version}  ->  {wheel}")
            else:
                verdicts[_normalize(name)] = "sdist"
                misses += 1
                print(f"   MISS {name}=={version}  (no wheel for {tags} among {len(wheels)} wheels) -> build from sdist on the target runner")
        sources[platform_key] = verdicts
    return misses


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", required=True, type=Path, help="darwin-arm64 runtime archive (tar.gz)")
    ap.add_argument("--write", action="store_true", help=f"write the lock to {DEFAULT_LOCK}")
    ap.add_argument("--output", type=Path, default=DEFAULT_LOCK)
    ap.add_argument("--check-index", action="store_true", help="pip dry-run: which wheel would be picked per native dist")
    ap.add_argument("--platforms", default="win32-x64", help="comma-separated platform keys for --check-index")
    args = ap.parse_args()
    if not args.seed.is_file():
        print(f"seed not found: {args.seed}", file=sys.stderr)
        return 2
    lock = build_lock(args.seed)
    print(f"seed {args.seed.name}: python {lock['python']}, {len(lock['pure'])} pure + {len(lock['native'])} native dists"
          f" (excluded present: {lock['excluded_present_in_seed']})")
    for requirement in lock["native"]:
        print(f"   native: {requirement}")
    misses = 0
    if args.check_index:
        misses = check_index(lock, [p.strip() for p in args.platforms.split(",") if p.strip()])
        print(f"check-index: {misses} native dist(s) without a wheel (they are marked \"sdist\" and built on the target runner)")
    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
