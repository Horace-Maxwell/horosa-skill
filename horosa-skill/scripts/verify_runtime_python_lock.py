#!/usr/bin/env python3
"""Guard for contracts/runtime_python_lock.json (v0.38.0 A1).

Without --seed (CI): the lock is well-formed, every name in contracts/upstream_python_requirements.txt is
classified (pure / native / excluded), nothing excluded leaks into pure ∪ native, every platform override
is explained in docs/LESSONS.md, and every native dist has a wheel_sources verdict for each derivable
platform. With --seed <tar.gz> (preflight / hosted assemble): the lock's dist set equals the seed's.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
REPO_ROOT = PKG_ROOT.parent
LOCK = PKG_ROOT / "contracts" / "runtime_python_lock.json"
REQUIREMENTS = PKG_ROOT / "contracts" / "upstream_python_requirements.txt"
LESSONS = REPO_ROOT / "docs" / "LESSONS.md"
_NORMALIZE = re.compile(r"[-_.]+")


def normalize(name: str) -> str:
    return _NORMALIZE.sub("-", name).lower()


def requirement_names(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        names.append(normalize(re.split(r"[<>=!~\[; ]", line, 1)[0]))
    return names


def audit_lock(lock: dict, requirements: str, lessons: str) -> list[str]:
    errors: list[str] = []
    for key in ("python", "pure", "native", "excluded", "platform_tags", "platform_overrides", "wheel_sources", "seed"):
        if key not in lock:
            errors.append(f"lock lacks `{key}`")
    if errors:
        return errors
    pure = {normalize(r.split("==")[0]) for r in lock["pure"]}
    native = {normalize(r.split("==")[0]) for r in lock["native"]}
    excluded = {normalize(n) for n in lock["excluded"]}
    for req in lock["pure"] + lock["native"]:
        if "==" not in req:
            errors.append(f"lock entry is not pinned with ==: {req}")
    if pure & native:
        errors.append(f"dists both pure and native: {sorted(pure & native)}")
    leaked = (pure | native) & excluded
    if leaked:
        errors.append(f"excluded dists leaked into the dep set: {sorted(leaked)}")
    for name in requirement_names(requirements):
        if name not in pure | native | excluded:
            errors.append(f"upstream requirement `{name}` is neither in the lock nor in `excluded`")
    for platform_key, overrides in (lock.get("platform_overrides") or {}).items():
        for name, version in overrides.items():
            if f"{name}" not in lessons or f"{version}" not in lessons:
                errors.append(f"platform_overrides[{platform_key}][{name}]={version} has no docs/LESSONS.md entry")
    for platform_key in lock["platform_overrides"]:
        verdicts = (lock.get("wheel_sources") or {}).get(platform_key) or {}
        missing = sorted(native - set(verdicts))
        if missing:
            errors.append(f"wheel_sources[{platform_key}] lacks a verdict for native dists: {missing} (rerun gen_runtime_python_lock.py --check-index --write)")
    return errors


def compare_with_seed(lock: dict, seed: Path) -> list[str]:
    sys.path.insert(0, str(SCRIPTS))
    from gen_runtime_python_lock import EXCLUDED, read_seed_dists  # noqa: E402

    _, dists = read_seed_dists(seed)
    seed_set = {f"{d['name']}=={d['version']}" for n, d in dists.items() if n not in EXCLUDED}
    lock_set = set(lock["pure"]) | set(lock["native"])
    errors: list[str] = []
    if seed_set != lock_set:
        errors.append(
            "lock drift vs seed — regenerate with gen_runtime_python_lock.py --seed <tar> --check-index --write: "
            f"only in seed {sorted(seed_set - lock_set)}; only in lock {sorted(lock_set - seed_set)}"
        )
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=Path, default=None, help="compare the lock against this darwin-arm64 archive")
    ap.add_argument("--lock", type=Path, default=LOCK)
    args = ap.parse_args()
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    errors = audit_lock(lock, REQUIREMENTS.read_text(encoding="utf-8"), LESSONS.read_text(encoding="utf-8") if LESSONS.exists() else "")
    if args.seed is not None:
        errors.extend(compare_with_seed(lock, args.seed))
    if errors:
        print("runtime-python-lock FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    sdist = {p: sorted(n for n, v in (lock.get("wheel_sources") or {}).get(p, {}).items() if v == "sdist") for p in lock["platform_overrides"]}
    print(f"runtime-python-lock OK: python {lock['python']}, {len(lock['pure'])} pure + {len(lock['native'])} native; build-from-sdist {sdist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
