#!/usr/bin/env python3
"""Seed + derive: build a platform payload from a verified darwin-arm64 runtime archive (v0.38.0 A1/A2).

The platform-independent tree (Horosa-Web subset, astrostudyboot.jar, horosa-core-js with node_modules)
lives in the maintainer-built, live-tested darwin-arm64 archive — the *seed*. A derived payload copies
that tree byte for byte and swaps only what is native: the JDK, Node, the embedded CPython and the 19
native Python dists (re-fetched as wheels for the target, or built from sdist on the target runner when
PyPI ships none — pyswisseph / sxtwl for cp312 Windows). Nothing here needs `vendor/runtime-source`,
`npm`, or rsync, so it runs on a hosted GitHub runner (AGENTS §6 builder purity: stdlib + curl + pip).

Public helpers (imported by build_runtime_release_windows.py --seed and by the tests):
    verify_seed / materialize_seed / derive_manifest / copy_platform_tree / split_site_packages /
    copy_pure_site_packages / fetch_native_wheels / unpack_wheels / assert_binary_arch / jlink_image /
    find_jdk_home / load_toolchain / load_lock
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
CONTRACTS = PKG_ROOT / "contracts"
SEED_PLATFORM = "darwin-arm64"
SEED_PYTHON_SITE = "runtime/mac/python/lib/python{minor}/site-packages"
_NORMALIZE = re.compile(r"[-_.]+")


def normalize_name(name: str) -> str:
    return _NORMALIZE.sub("-", name).lower()


def load_toolchain(path: Path | None = None) -> dict:
    return json.loads((path or CONTRACTS / "runtime_toolchain.json").read_text(encoding="utf-8"))


def load_lock(path: Path | None = None) -> dict:
    return json.loads((path or CONTRACTS / "runtime_python_lock.json").read_text(encoding="utf-8"))


def _verifier():
    spec = importlib.util.spec_from_file_location("_horosa_verify_runtime_release", SCRIPTS / "verify_runtime_release.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


# --- seed -----------------------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_seed(archive: Path, *, expected_version: str | None = None) -> dict:
    """Refuse to derive from anything but a complete darwin-arm64 seed; returns its embedded manifest.

    Reuses verify_runtime_release's REQUIRED_ENTRIES / embedded-manifest checks (the release gate), so
    a seed that would fail the release cannot become the base of a derived platform either.
    """
    verifier = _verifier()
    if not archive.is_file() or not archive.name.endswith(".tar.gz"):
        raise SystemExit(f"seed must be an existing darwin-arm64 .tar.gz archive: {archive}")
    verifier._assert_entries(archive, SEED_PLATFORM)
    manifest = json.loads(verifier._read_archive_text(archive, "runtime-payload/runtime-manifest.json"))
    version = expected_version or str(manifest.get("version"))
    verifier._assert_payload_manifest(archive, SEED_PLATFORM, version)
    return manifest


class SeedTree:
    """The extracted `runtime-payload/` of a seed plus its embedded manifest.

    A plain class on purpose: this module is loaded via importlib.spec_from_file_location by builders
    and tests, and `@dataclass` under `from __future__ import annotations` needs the module registered
    in sys.modules to resolve its annotations (it crashes at import otherwise).
    """

    __slots__ = ("root", "manifest")

    def __init__(self, root: Path, manifest: dict) -> None:
        self.root = root
        self.manifest = manifest

    @property
    def horosa_web(self) -> Path:
        return self.root / "Horosa-Web"

    @property
    def core_js(self) -> Path:
        return self.root / "horosa-core-js"

    @property
    def boot_jar(self) -> Path:
        return self.root / "runtime" / "mac" / "bundle" / "astrostudyboot.jar"

    @property
    def python_root(self) -> Path:
        return self.root / "runtime" / "mac" / "python"

    def site_packages(self, python_minor: str) -> Path:
        return self.root / SEED_PYTHON_SITE.format(minor=python_minor)


def materialize_seed(archive: Path, cache_root: Path) -> SeedTree:
    """Extract `runtime-payload/` once per seed sha (exec bits preserved via tarfile's data filter)."""
    key = sha256_file(archive)[:12]
    target = cache_root / key
    marker = target / ".seed-ok"
    if not marker.is_file():
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(target, filter="data")
        marker.write_text(archive.name, encoding="utf-8")
    root = target / "runtime-payload"
    manifest = json.loads((root / "runtime-manifest.json").read_text(encoding="utf-8"))
    return SeedTree(root=root, manifest=manifest)


# --- manifest -------------------------------------------------------------------------------------

_INHERITED_KEYS = ("schema_version", "version", "runtime_layout_version", "runtime_payload_version", "export_registry_version")


def derive_manifest(seed_manifest: dict, *, platform: str, runtimes: dict[str, str], boot_jar: str,
                    start_script: str, stop_script: str, platform_requirements: dict | None = None) -> dict:
    """The derived manifest inherits every version/registry constant from the seed — a derived builder
    never stamps `export_registry_version` itself (verify_builder_parity.py keeps that invariant)."""
    missing = [key for key in _INHERITED_KEYS if key not in seed_manifest]
    if missing:
        raise SystemExit(f"seed manifest lacks {missing}; refusing to derive")
    services = dict(seed_manifest.get("services") or {})
    services.update({"start_script": start_script, "stop_script": stop_script})
    artifacts = dict(seed_manifest.get("artifacts") or {})
    artifacts["boot_jar"] = boot_jar
    manifest = {key: seed_manifest[key] for key in _INHERITED_KEYS}
    manifest["platform"] = platform
    manifest["services"] = services
    manifest["runtimes"] = dict(runtimes)
    manifest["artifacts"] = artifacts
    manifest["derived_from"] = {"platform": seed_manifest.get("platform"), "version": seed_manifest.get("version")}
    if platform_requirements:
        manifest["platform_requirements"] = dict(platform_requirements)
    # key order: mirror the hand-written manifests
    ordered = {k: manifest[k] for k in ("schema_version", "version", "platform", "runtime_layout_version",
                                         "runtime_payload_version", "export_registry_version", "services",
                                         "runtimes", "artifacts", "derived_from")}
    if "platform_requirements" in manifest:
        ordered["platform_requirements"] = manifest["platform_requirements"]
    return ordered


# --- platform-independent tree ---------------------------------------------------------------------

_COPY_IGNORE = shutil.ignore_patterns(".DS_Store", "._*", "__pycache__", "*.pyc", "*.pyo", ".pytest_cache", ".cache",
                                      "*.sqlite-wal", "*.sqlite-shm", "*.sqlite-journal")


def copy_platform_tree(seed: SeedTree, payload_root: Path, *, launchers: str, os_dir: str) -> None:
    """Horosa-Web (minus the seed's launchers when the target ships its own), horosa-core-js, the jar."""
    horosa_web = payload_root / "Horosa-Web"
    shutil.copytree(seed.horosa_web, horosa_web, ignore=_COPY_IGNORE, dirs_exist_ok=True)
    if launchers != "sh":
        for name in ("start_horosa_local.sh", "stop_horosa_local.sh"):
            (horosa_web / name).unlink(missing_ok=True)
    shutil.copytree(seed.core_js, payload_root / "horosa-core-js", ignore=_COPY_IGNORE, dirs_exist_ok=True)
    bundle = payload_root / "runtime" / os_dir / "bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed.boot_jar, bundle / "astrostudyboot.jar")


# --- site-packages ---------------------------------------------------------------------------------


def _dist_info_dirs(site_packages: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for entry in site_packages.glob("*.dist-info"):
        name = ""
        for line in (entry / "METADATA").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Name:"):
                name = line.split(":", 1)[1].strip()
                break
            if line == "":
                break
        found[normalize_name(name or entry.name.rsplit("-", 1)[0])] = entry
    return found


def _record_files(dist_info: Path) -> list[str]:
    record = dist_info / "RECORD"
    if not record.is_file():
        return []
    return [line.split(",", 1)[0] for line in record.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def split_site_packages(seed: SeedTree, lock: dict) -> tuple[list[str], list[str]]:
    """(pure, native) dist names present in the seed, classified by the lock."""
    pure = {normalize_name(r.split("==")[0]) for r in lock["pure"]}
    native = {normalize_name(r.split("==")[0]) for r in lock["native"]}
    present = set(_dist_info_dirs(seed.site_packages(str(lock["python"]))))
    return sorted(pure & present), sorted(native & present)


def copy_pure_site_packages(seed: SeedTree, lock: dict, dest: Path) -> list[str]:
    """Copy every RECORD-listed file of every pure dist from the seed's site-packages (skips bin/, __pycache__)."""
    site = seed.site_packages(str(lock["python"]))
    dists = _dist_info_dirs(site)
    pure, _ = split_site_packages(seed, lock)
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in pure:
        for rel in _record_files(dists[name]):
            if rel.startswith("../") or "__pycache__" in rel or rel.endswith((".pyc", ".pyo")):
                continue
            src = site / rel
            if not src.is_file():
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        copied.append(name)
    return copied


def _pip(python: str | None) -> list[str]:
    return [python or sys.executable, "-m", "pip"]


def fetch_native_wheels(lock: dict, platform_key: str, dest: Path, *, python: str | None = None,
                        build_from_sdist: bool = True) -> dict[str, Path]:
    """Wheels for every native dist at the seed's version: `pip download` when PyPI ships one for the
    target (lock.wheel_sources), else `pip wheel --no-binary :all:` on this machine (must BE the target).

    Returns {normalized name: wheel path}. Requires `python -m pip` (setup-python on the runner; locally
    pass --python pointing at an interpreter that has pip)."""
    dest.mkdir(parents=True, exist_ok=True)
    tags = list(lock["platform_tags"][platform_key])
    python_minor = str(lock["python"])
    abi = "cp" + python_minor.replace(".", "")
    overrides = (lock.get("platform_overrides") or {}).get(platform_key, {})
    sources = (lock.get("wheel_sources") or {}).get(platform_key, {})
    got: dict[str, Path] = {}
    for requirement in lock["native"]:
        name, _, version = requirement.partition("==")
        key = normalize_name(name)
        version = overrides.get(key, version)
        if sources.get(key) == "sdist":
            if not build_from_sdist:
                raise SystemExit(f"{name}=={version} has no wheel for {platform_key} and sdist builds are disabled")
            cmd = [*_pip(python), "wheel", "--no-deps", "--no-binary", ":all:", "--wheel-dir", str(dest), f"{name}=={version}"]
        else:
            cmd = [*_pip(python), "download", "--only-binary=:all:", "--no-deps", "--python-version", python_minor,
                   "--implementation", "cp", "--abi", abi, "--dest", str(dest), f"{name}=={version}"]
            for tag in tags:
                cmd += ["--platform", tag]
        subprocess.run(cmd, check=True)
        wheel = next((w for w in sorted(dest.glob("*.whl")) if normalize_name(w.name.split("-", 1)[0]) == key), None)
        if wheel is None:
            raise SystemExit(f"no wheel appeared for {name}=={version} in {dest}")
        got[key] = wheel
    return got


def unpack_wheels(wheels_root: Path, site_packages: Path) -> None:
    site_packages.mkdir(parents=True, exist_ok=True)
    for wheel in sorted(wheels_root.glob("*.whl")):
        with zipfile.ZipFile(wheel) as zf:
            zf.extractall(site_packages)


# --- binaries --------------------------------------------------------------------------------------

_MACHO_MAGIC = {0xFEEDFACF: "64", 0xCFFAEDFE: "64le", 0xFEEDFACE: "32", 0xCEFAEDFE: "32le"}
_FAT_MAGIC = {0xCAFEBABE, 0xBEBAFECA}
_CPU_ARM64 = 0x0100000C
_CPU_X86_64 = 0x01000007
_PE_MACHINE = {0x8664: "x86_64", 0xAA64: "arm64", 0x014C: "x86"}
_ARCH_ALIASES = {"x64": "x86_64", "amd64": "x86_64", "aarch64": "arm64"}


def binary_arches(data: bytes) -> set[str]:
    """Architectures a Mach-O (thin or fat), PE or ELF header declares; empty set = not a native binary."""
    if len(data) < 64:
        return set()
    magic_be = struct.unpack(">I", data[:4])[0]
    if magic_be in _FAT_MAGIC:
        count = struct.unpack(">I", data[4:8])[0]
        arches: set[str] = set()
        for index in range(min(count, 8)):
            cputype = struct.unpack(">I", data[8 + index * 20 : 12 + index * 20])[0]
            arches.add({_CPU_ARM64: "arm64", _CPU_X86_64: "x86_64"}.get(cputype, f"cpu{cputype:#x}"))
        return arches
    magic_le = struct.unpack("<I", data[:4])[0]
    if magic_le in (0xFEEDFACF, 0xFEEDFACE):
        cputype = struct.unpack("<I", data[4:8])[0]
        return {{_CPU_ARM64: "arm64", _CPU_X86_64: "x86_64"}.get(cputype, f"cpu{cputype:#x}")}
    if data[:2] == b"MZ":
        e_lfanew = struct.unpack("<I", data[60:64])[0]
        if e_lfanew + 6 <= len(data) and data[e_lfanew : e_lfanew + 4] == b"PE\0\0":
            machine = struct.unpack("<H", data[e_lfanew + 4 : e_lfanew + 6])[0]
            return {_PE_MACHINE.get(machine, f"pe{machine:#x}")}
    if data[:4] == b"\x7fELF":
        machine = struct.unpack("<H", data[18:20])[0]
        return {{0x3E: "x86_64", 0xB7: "arm64"}.get(machine, f"elf{machine:#x}")}
    return set()


def assert_binary_arch(path: Path, expected: str) -> None:
    """A derived payload must never carry the seed's arm64 binaries where the target needs x86_64."""
    want = _ARCH_ALIASES.get(expected, expected)
    with path.open("rb") as handle:
        head = handle.read(4096)
    found = binary_arches(head)
    if not found:
        raise SystemExit(f"{path}: not a recognised native binary (Mach-O / PE / ELF)")
    if want not in found:
        raise SystemExit(f"{path}: built for {sorted(found)}, expected {want}")


# --- JDK -------------------------------------------------------------------------------------------


def find_jdk_home(extracted: Path) -> Path:
    """The directory holding bin/ and jmods/ (Temurin macOS zips nest under Contents/Home)."""
    for candidate in (extracted, extracted / "Contents" / "Home", *sorted(extracted.glob("*/")), *sorted(extracted.glob("*/Contents/Home"))):
        if (candidate / "bin").is_dir() and ((candidate / "jmods").is_dir() or (candidate / "lib" / "modules").is_file()):
            return candidate
    raise SystemExit(f"no JDK home (bin/ + jmods/) under {extracted}")


def _jlink_major(jlink: Path) -> int | None:
    try:
        out = subprocess.run([str(jlink), "--version"], capture_output=True, text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.match(r"(\d+)", out)
    return int(match.group(1)) if match else None


def host_jlink(major: int = 17) -> Path | None:
    """A jlink that can run on THIS machine AND matches the target JDK's major version (jlink refuses to
    link jmods of another major: "jlink version 22.0 does not match target java.base version 17.0").
    Candidates: the vendored mac Zulu JDK (the mac packager's own), then PATH."""
    candidates: list[Path] = []
    vendored = PKG_ROOT.parent / "vendor" / "runtime-source" / "runtime" / "mac" / "java" / "bin" / "jlink"
    if vendored.is_file():
        candidates.append(vendored)
    found = shutil.which("jlink")
    if found:
        candidates.append(Path(found))
    for java_home in (os.environ.get("JAVA_HOME"),):
        if java_home and (Path(java_home) / "bin" / "jlink").is_file():
            candidates.append(Path(java_home) / "bin" / "jlink")
    for candidate in candidates:
        if _jlink_major(candidate) == major:
            return candidate
    return None


def jlink_image(jdk_home: Path, dest: Path, modules: list[str], *, jlink_bin: Path | None = None) -> None:
    """Link `modules` from `jdk_home/jmods` into `dest`. `jlink_bin` defaults to the JDK's own jlink (native
    build); a host jlink of the same major version cross-links a foreign platform's jmods (dry runs)."""
    jlink = jlink_bin or (jdk_home / "bin" / ("jlink.exe" if os.name == "nt" else "jlink"))
    jmods = jdk_home / "jmods"
    if not jlink.is_file() or not jmods.is_dir():
        raise SystemExit(f"jlink ({jlink}) or jmods ({jmods}) missing; pass --full-jdk to copy the whole JDK instead")
    if dest.exists():
        shutil.rmtree(dest)
    subprocess.run([str(jlink), "--module-path", str(jmods), "--add-modules", ",".join(modules), "--strip-debug",
                    "--no-header-files", "--no-man-pages", "--output", str(dest)], check=True)
