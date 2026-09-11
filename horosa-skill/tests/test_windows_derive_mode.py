"""Windows payload derived from a darwin-arm64 seed (v0.38.0 A2) — offline, with a synthetic seed and fake
toolchain archives: the staging must produce a tree that passes the release verifier's entry / manifest /
BOM / native-arch gates, and the arch gate must be red when the seed's binaries leak through."""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest
from test_runtime_seed import _SEED_MANIFEST, _fat, _macho, _pe, _synthetic_seed

PKG_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, PKG_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed = _load("runtime_seed")
builder = _load("build_runtime_release_windows")
verifier = _load("verify_runtime_release")

_LOCK = {
    "python": "3.12", "seed": {"archive": "x", "sha256": "y", "generated_at": "z"},
    "pure": ["bidict==0.23.1"], "native": ["numpy==2.4.6", "sxtwl==2.0.6"], "excluded": {},
    "platform_tags": {"win32-x64": ["win_amd64"]}, "platform_overrides": {"win32-x64": {}},
    "wheel_sources": {"win32-x64": {"numpy": "numpy-2.4.6-cp312-cp312-win_amd64.whl", "sxtwl": "sdist"}},
}
_TOOLCHAIN = {"java": {"jlink_modules": ["java.base"]}, "platforms": {"win32-x64": {"min_os": "10.0.17763", "pip_platform_tags": ["win_amd64"]}}}


def _zip(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return path


def _seed_with_site_packages(tmp_path: Path) -> Path:
    """The synthetic seed plus a pure dist (bidict) in the seed's site-packages, RECORD-listed."""
    archive = _synthetic_seed(tmp_path, version="0.38.0")
    # re-create with the extra files: unpack, add, repack
    import tarfile

    stage = tmp_path / "stage"
    site = stage / "runtime-payload" / "runtime" / "mac" / "python" / "lib" / "python3.12" / "site-packages"
    (site / "bidict").mkdir(parents=True)
    (site / "bidict" / "__init__.py").write_text("VERSION = '0.23.1'\n", encoding="utf-8")
    info = site / "bidict-0.23.1.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: bidict\nVersion: 0.23.1\n\n", encoding="utf-8")
    (info / "RECORD").write_text("bidict/__init__.py,sha256=x,10\nbidict-0.23.1.dist-info/METADATA,sha256=y,20\n", encoding="utf-8")
    archive.unlink()
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(stage / "runtime-payload", arcname="runtime-payload")
    return archive


def _downloads(tmp_path: Path, *, java_bytes: bytes) -> dict[str, Path]:
    return {
        "jdk": _zip(tmp_path / "jdk.zip", {"jdk-17.0.20.1+1/bin/java.exe": java_bytes, "jdk-17.0.20.1+1/jmods/java.base.jmod": b"jmod", "jdk-17.0.20.1+1/release": b"JAVA_VERSION=17"}),
        "python": _zip(tmp_path / "py.zip", {"python.exe": _pe(0x8664), "python312._pth": b"python312.zip\n.\n", "python312.zip": b"PK"}),
        "node": _zip(tmp_path / "node.zip", {"node-v22.23.2-win-x64/node.exe": _pe(0x8664)}),
    }


def _fake_fetch(lock: dict, platform_key: str, dest: Path, *, python=None, build_from_sdist=True) -> dict[str, Path]:
    dest.mkdir(parents=True, exist_ok=True)
    wheel = _zip(dest / "numpy-2.4.6-cp312-cp312-win_amd64.whl", {
        "numpy/__init__.py": b"", "numpy/_core/_multiarray_umath.cp312-win_amd64.pyd": _pe(0x8664),
        "numpy-2.4.6.dist-info/METADATA": b"Metadata-Version: 2.1\nName: numpy\nVersion: 2.4.6\n\n",
    })
    assert not build_from_sdist or "sxtwl==2.0.6" in lock["native"], "sdist dists reach the fetcher only when builds are enabled"
    return {"numpy": wheel}


def _stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, java_bytes: bytes = _pe(0x8664), skip_sdist: bool = True) -> Path:
    monkeypatch.setattr(seed, "fetch_native_wheels", _fake_fetch)
    tree = seed.materialize_seed(_seed_with_site_packages(tmp_path), tmp_path / "cache")
    payload = tmp_path / "build" / "runtime-payload"
    builder.stage_from_seed(seed, tree, _LOCK, _TOOLCHAIN, payload, downloads=_downloads(tmp_path, java_bytes=java_bytes),
                            jlink=False, skip_sdist=skip_sdist)
    return payload


def test_staged_tree_passes_every_release_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _stage(tmp_path, monkeypatch)
    manifest = json.loads((payload / "runtime-manifest.json").read_text(encoding="utf-8"))
    assert manifest["platform"] == "win32-x64" and manifest["version"] == "0.38.0"
    assert manifest["export_registry_version"] == _SEED_MANIFEST["export_registry_version"]
    assert manifest["runtimes"]["python"] == "runtime/windows/python/python.exe"
    assert manifest["services"]["start_script"] == "Horosa-Web/start_horosa_local.ps1"
    assert manifest["platform_requirements"] == {"arch": "x86_64", "min_os": "10.0.17763"}
    assert (payload / "Horosa-Web" / "start_horosa_local.ps1").read_bytes().startswith(b"\xef\xbb\xbf")
    assert not (payload / "Horosa-Web" / "start_horosa_local.sh").exists()
    site = payload / "runtime" / "windows" / "python" / "Lib" / "site-packages"
    assert (site / "bidict" / "__init__.py").is_file(), "pure dists are copied from the seed"
    assert (site / "numpy" / "_core" / "_multiarray_umath.cp312-win_amd64.pyd").is_file()
    assert (payload / "runtime" / "windows" / "python" / "python312._pth").read_text(encoding="utf-8").startswith("python312.zip\n")
    archive = builder.write_archive(payload, tmp_path / "horosa-runtime-win32-x64-v0.38.0.zip")
    verifier._assert_entries(archive, "win32-x64")
    verifier._assert_payload_manifest(archive, "win32-x64", "0.38.0")
    verifier._assert_windows_launchers_are_bom_encoded(archive)
    verifier._assert_native_arch(archive, "win32-x64")


def test_arch_gate_is_red_when_the_seeds_arm64_java_leaks_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative control: staging itself refuses an ARM64 java.exe; the release verifier catches a leaked one too."""
    with pytest.raises(SystemExit):
        _stage(tmp_path, monkeypatch, java_bytes=_pe(0xAA64))
    # a hand-made archive that sneaks an arm64 Mach-O in as java.exe must fail the verifier's gate
    payload = _stage(tmp_path / "ok", monkeypatch)
    (payload / "runtime" / "windows" / "java" / "bin" / "java.exe").write_bytes(_macho(seed._CPU_ARM64))
    archive = builder.write_archive(payload, tmp_path / "leaked.zip")
    with pytest.raises(SystemExit):
        verifier._assert_native_arch(archive, "win32-x64")


def test_universal_binaries_satisfy_the_darwin_gate(tmp_path: Path) -> None:
    assert seed.binary_arches(_fat(seed._CPU_X86_64, seed._CPU_ARM64)) >= {"arm64"}


def test_lock_without_sdist_drops_only_sdist_dists() -> None:
    trimmed = builder._lock_without_sdist(_LOCK, "win32-x64")
    assert trimmed["native"] == ["numpy==2.4.6"]
    assert _LOCK["native"] == ["numpy==2.4.6", "sxtwl==2.0.6"], "the original lock is untouched"
