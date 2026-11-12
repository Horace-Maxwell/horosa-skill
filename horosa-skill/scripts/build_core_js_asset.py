#!/usr/bin/env python3
"""Build the platform-independent JS engine asset `horosa-core-js-v<version>.tar.gz` (v0.50.0-dev, E-02).

Why it exists: the offline runtime archives (darwin-arm64 / win32-x64) are the only things that carried the JS engine. A wheel /
pip / Docker / gateway install on Linux or an Intel Mac — or anyone who skipped `install` — had no engine at all, so BaZi / Ziwei /
Qimen / Taiyi / Jinkou / Liuren / Heluo / Canping … failed with `js_engine.cli_missing`. The engine is pure JS plus four
production npm packages, so one archive serves every OS; `horosa-skill install` fetches it wherever no runtime archive does.

What goes in (the same selection the darwin payload copies, `package_runtime_payload.sh`):
  * every TRACKED file under `horosa-core-js/` (git ls-files; the committed `dist/app-charts.cjs` included), read from the
    working tree, which must not differ from HEAD there (`--allow-dirty` for local experiments only);
  * the production closure of `package-lock.json` (entries without `dev: true`), copied from an installed `node_modules`
    whose versions must equal the lock — or, with `--npm-ci`, from a fresh `npm ci --omit=dev --ignore-scripts` in a temp dir;
  * minus the payload's rsync exclusion set (`EXCLUDE_PATTERNS`, locked to `RSYNC_FILTERS` by tests/test_core_js_asset.py).

Deterministic: entries sorted, fixed mtime / owner / modes, PAX format, gzip header without name or time — the same tree gives
the same bytes (for a given zlib). Stdlib only.

    python3 horosa-skill/scripts/build_core_js_asset.py [--out-dir dist/runtime] [--npm-ci] [--allow-dirty]
"""
from __future__ import annotations

import argparse
import fnmatch
import gzip
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
CORE_JS_DIRNAME = "horosa-core-js"
ARCHIVE_ROOT = CORE_JS_DIRNAME  # top-level directory inside the archive (the installer and verifiers expect exactly this)
ASSET_TEMPLATE = "horosa-core-js-v{version}.tar.gz"
FIXED_MTIME = 315532800  # 1980-01-01T00:00:00Z: a constant, so the bytes do not depend on when or where the tree was checked out
# The darwin payload's rsync exclusion set (package_runtime_payload.sh RSYNC_FILTERS, `--exclude=X` / `--exclude=*/X` → X).
# 🔴 Exclusion sets live in several builders (AGENTS §6「排除集同加」); tests/test_core_js_asset.py fails when they drift.
EXCLUDE_PATTERNS: tuple[str, ...] = (
    ".DS_Store", "._*", "_CodeSignature", "${env:HOME}", ".horosa-logs", ".pytest_cache", ".cache", "__pycache__",
    "*.pyc", "*.pyo", "*.map", "*.tmp", "*.temp", "*.pid", "*.sqlite-wal", "*.sqlite-shm", "*.sqlite-journal",
)
# npm bookkeeping inside node_modules that `npm ci` writes but the engine never reads; leaving it out keeps the archive a
# function of the lock alone.
NODE_MODULES_SKIP = (".bin", ".package-lock.json")


class BuildError(Exception):
    pass


@dataclass(frozen=True)
class Entry:
    arcname: str
    source: Path | None  # None = directory entry


def excluded(relative: str) -> bool:
    return any(fnmatch.fnmatchcase(part, pattern) for part in relative.split("/") for pattern in EXCLUDE_PATTERNS)


def read_version(skill_root: Path) -> str:
    return tomllib.loads((skill_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def _git(skill_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(skill_root), *args], capture_output=True, check=False)


def tracked_files(skill_root: Path, *, allow_dirty: bool) -> list[str]:
    """Paths relative to horosa-core-js/ of every tracked file there (sorted)."""
    listed = _git(skill_root, "ls-files", "-z", "--", CORE_JS_DIRNAME)
    if listed.returncode != 0:
        raise BuildError(f"git ls-files failed in {skill_root}: {listed.stderr.decode('utf-8', 'replace').strip()}")
    names = [name for name in listed.stdout.decode("utf-8").split("\0") if name]
    if not names:
        raise BuildError(f"no tracked files under {skill_root / CORE_JS_DIRNAME} (not a git checkout?)")
    if not allow_dirty:
        dirty = _git(skill_root, "diff", "--name-only", "HEAD", "--", CORE_JS_DIRNAME)
        changed = dirty.stdout.decode("utf-8", "replace").split()
        if dirty.returncode != 0 or changed:
            raise BuildError(
                "horosa-core-js differs from HEAD (" + ", ".join(changed[:5]) + "): the release asset must be the committed tree. "
                "Commit or stash first (--allow-dirty only for local experiments)."
            )
    prefix = CORE_JS_DIRNAME + "/"
    relative = sorted(name[len(prefix):] for name in names if name.startswith(prefix))
    return [rel for rel in relative if not rel.startswith("node_modules/")]


def production_packages(lock: dict) -> dict[str, str]:
    """`node_modules/<name>` (nested paths included) → version, for every lock entry `npm ci --omit=dev` installs."""
    packages = lock.get("packages")
    if not isinstance(packages, dict):
        raise BuildError("package-lock.json has no `packages` map (lockfileVersion >= 2 is required)")
    result: dict[str, str] = {}
    for key, meta in packages.items():
        if not key or not isinstance(meta, dict) or meta.get("dev") is True:
            continue
        if meta.get("link"):
            raise BuildError(f"{key} is a linked package; the asset only carries registry packages")
        result[key] = str(meta.get("version") or "")
    return dict(sorted(result.items()))


def check_installed(node_modules_parent: Path, packages: dict[str, str]) -> list[str]:
    problems = []
    for key, version in packages.items():
        manifest = node_modules_parent / key / "package.json"
        try:
            installed = json.loads(manifest.read_text(encoding="utf-8")).get("version")
        except (OSError, ValueError):
            problems.append(f"{key} is not installed")
            continue
        if installed != version:
            problems.append(f"{key} is {installed}, package-lock.json says {version}")
    return problems


def npm_ci_stage(core_js: Path, work: Path) -> Path:
    """A fresh production install from the lock in `work` (network unless npm's cache has it)."""
    for name in ("package.json", "package-lock.json"):
        shutil.copy2(core_js / name, work / name)
    npm = shutil.which("npm")
    if npm is None:
        raise BuildError("--npm-ci needs npm on PATH")
    done = subprocess.run([npm, "ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund", "--loglevel=error"],
                          cwd=str(work), capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise BuildError(f"npm ci --omit=dev failed: {done.stderr.strip()[-600:]}")
    return work


def _walk_files(directory: Path) -> list[Path]:
    found: list[Path] = []
    for root, dirs, files in os.walk(directory, followlinks=False):
        root_path = Path(root)
        for name in list(dirs):
            if (root_path / name).is_symlink():
                raise BuildError(f"symlink in the package tree: {root_path / name}")
        # nested node_modules are their own lock entries (copied separately when they are production packages)
        dirs[:] = sorted(d for d in dirs if d != "node_modules")
        for name in sorted(files):
            path = root_path / name
            if path.is_symlink():
                raise BuildError(f"symlink in the package tree: {path}")
            found.append(path)
    return found


def collect_entries(core_js: Path, tracked: list[str], node_modules_parent: Path, packages: dict[str, str]) -> list[Entry]:
    files: dict[str, Path] = {}
    for rel in tracked:
        source = core_js / rel
        if source.is_symlink() or not source.is_file():
            raise BuildError(f"tracked file is missing or a symlink: {source}")
        if not excluded(rel):
            files[rel] = source
    for key in packages:
        package_dir = node_modules_parent / key
        for path in _walk_files(package_dir):
            rel = f"{key}/{path.relative_to(package_dir).as_posix()}"
            if any(part in NODE_MODULES_SKIP for part in rel.split("/")) or excluded(rel):
                continue
            files[rel] = path
    directories: set[str] = set()
    for rel in files:
        parts = rel.split("/")[:-1]
        for depth in range(1, len(parts) + 1):
            directories.add("/".join(parts[:depth]))
    entries = [Entry(ARCHIVE_ROOT, None)]
    entries += [Entry(f"{ARCHIVE_ROOT}/{rel}", None) for rel in sorted(directories)]
    entries += [Entry(f"{ARCHIVE_ROOT}/{rel}", files[rel]) for rel in sorted(files)]
    return sorted(entries, key=lambda entry: entry.arcname)


def write_archive(entries: list[Entry], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".partial")
    with partial.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for entry in entries:
                    info = tarfile.TarInfo(entry.arcname)
                    info.mtime = FIXED_MTIME
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    if entry.source is None:
                        info.type = tarfile.DIRTYPE
                        info.mode = 0o755
                        tar.addfile(info)
                        continue
                    data = entry.source.read_bytes()
                    info.size = len(data)
                    info.mode = 0o644
                    tar.addfile(info, io.BytesIO(data))
    os.replace(partial, output)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def build(*, skill_root: Path, out_dir: Path, version: str | None = None, node_modules_parent: Path | None = None,
          npm_ci: bool = False, allow_dirty: bool = False) -> dict:
    core_js = skill_root / CORE_JS_DIRNAME
    version = version or read_version(skill_root)
    package = json.loads((core_js / "package.json").read_text(encoding="utf-8"))
    if package.get("name") != CORE_JS_DIRNAME:
        raise BuildError(f"{core_js / 'package.json'} names {package.get('name')!r}, expected {CORE_JS_DIRNAME!r}")
    if package.get("version") != version:
        raise BuildError(
            f"horosa-core-js/package.json is {package.get('version')} but the release is {version}: run scripts/bump_version.py "
            "(the engine version moves in lock-step with the package)"
        )
    node_floor = (package.get("engines") or {}).get("node")
    if not isinstance(node_floor, str) or not node_floor.strip():
        raise BuildError("horosa-core-js/package.json has no engines.node: the asset's node floor would be unknown")
    tracked = tracked_files(skill_root, allow_dirty=allow_dirty)
    packages = production_packages(json.loads((core_js / "package-lock.json").read_text(encoding="utf-8")))
    declared = set((package.get("dependencies") or {}))
    missing_decl = sorted(name for name in declared if f"node_modules/{name}" not in packages)
    if missing_decl:
        raise BuildError(f"package-lock.json lacks production entries for {missing_decl}: run `npm install` and commit the lock")
    with tempfile.TemporaryDirectory(prefix="core-js-npm-") as work_raw:
        parent = npm_ci_stage(core_js, Path(work_raw)) if npm_ci else (node_modules_parent or core_js)
        problems = check_installed(parent, packages)
        if problems:
            raise BuildError(
                "node_modules does not match package-lock.json (" + "; ".join(problems) + "). Run "
                "`npm ci --omit=dev` in horosa-core-js, or pass --npm-ci for a fresh install in a temp dir."
            )
        entries = collect_entries(core_js, tracked, parent, packages)
        output = out_dir / ASSET_TEMPLATE.format(version=version)
        write_archive(entries, output)
    return {
        "path": str(output),
        "name": output.name,
        "version": version,
        "sha256": sha256_file(output),
        "size": output.stat().st_size,
        "files": sum(1 for entry in entries if entry.source is not None),
        "node_floor": node_floor,
        "dependencies": {key.removeprefix("node_modules/"): version_ for key, version_ in packages.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--out-dir", type=Path, default=SKILL_ROOT / "dist" / "runtime")
    parser.add_argument("--version", default=None, help="Release version (default: pyproject.toml).")
    parser.add_argument("--node-modules-from", type=Path, default=None,
                        help="Directory whose node_modules/ supplies the production packages (default: horosa-core-js itself).")
    parser.add_argument("--npm-ci", action="store_true", help="Install the production packages fresh from the lock in a temp dir.")
    parser.add_argument("--allow-dirty", action="store_true", help="Build from a working tree that differs from HEAD (never for a release).")
    parser.add_argument("--skill-root", type=Path, default=SKILL_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        result = build(skill_root=args.skill_root.resolve(), out_dir=args.out_dir.resolve(), version=args.version,
                       node_modules_parent=args.node_modules_from, npm_ci=args.npm_ci, allow_dirty=args.allow_dirty)
    except BuildError as exc:
        print(f"build_core_js_asset: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
