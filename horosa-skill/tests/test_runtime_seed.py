"""Seed + derive helpers (v0.38.0 A1): a derived payload may only come from a verified seed, inherits its
manifest constants, and must never carry the seed's arm64 binaries where the target needs x86_64."""

from __future__ import annotations

import importlib.util
import json
import struct
import tarfile
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("runtime_seed", PKG_ROOT / "scripts" / "runtime_seed.py")
seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed)
_vspec = importlib.util.spec_from_file_location("verify_runtime_release", PKG_ROOT / "scripts" / "verify_runtime_release.py")
verifier = importlib.util.module_from_spec(_vspec)
_vspec.loader.exec_module(verifier)


# --- binaries ---------------------------------------------------------------------------------------

def _macho(cputype: int) -> bytes:
    return struct.pack("<IIIIIII", 0xFEEDFACF, cputype, 0, 2, 0, 0, 0) + b"\0" * 64


def _fat(*cputypes: int) -> bytes:
    head = struct.pack(">II", 0xCAFEBABE, len(cputypes))
    for index, cputype in enumerate(cputypes):
        head += struct.pack(">IIIII", cputype, 0, 4096 * (index + 1), 100, 12)
    return head + b"\0" * 64


def _pe(machine: int) -> bytes:
    dos = bytearray(b"MZ" + b"\0" * 62)
    dos[60:64] = struct.pack("<I", 64)
    return bytes(dos) + b"PE\0\0" + struct.pack("<H", machine) + b"\0" * 64


def test_binary_arches_reads_macho_fat_pe_and_elf() -> None:
    assert seed.binary_arches(_macho(seed._CPU_ARM64)) == {"arm64"}
    assert seed.binary_arches(_macho(seed._CPU_X86_64)) == {"x86_64"}
    assert seed.binary_arches(_fat(seed._CPU_X86_64, seed._CPU_ARM64)) == {"x86_64", "arm64"}
    assert seed.binary_arches(_pe(0x8664)) == {"x86_64"}
    assert seed.binary_arches(_pe(0xAA64)) == {"arm64"}
    assert seed.binary_arches(b"\x7fELF" + b"\0" * 14 + struct.pack("<H", 0x3E) + b"\0" * 64) == {"x86_64"}
    assert seed.binary_arches(b"#!/bin/sh\n" + b"\0" * 64) == set()


def test_assert_binary_arch_rejects_the_seeds_arm64_where_x64_is_required(tmp_path: Path) -> None:
    """Negative control: the failure this exists for — an x64 payload shipping the seed's arm64 java."""
    java = tmp_path / "java"
    java.write_bytes(_macho(seed._CPU_ARM64))
    with pytest.raises(SystemExit):
        seed.assert_binary_arch(java, "x86_64")
    exe = tmp_path / "python.exe"
    exe.write_bytes(_pe(0xAA64))
    with pytest.raises(SystemExit):
        seed.assert_binary_arch(exe, "x64")
    ok = tmp_path / "node.exe"
    ok.write_bytes(_pe(0x8664))
    seed.assert_binary_arch(ok, "x64")  # aliases x64 → x86_64
    universal = tmp_path / "libpython.dylib"
    universal.write_bytes(_fat(seed._CPU_X86_64, seed._CPU_ARM64))
    seed.assert_binary_arch(universal, "x86_64")
    text = tmp_path / "script"
    text.write_bytes(b"#!/bin/sh\necho hi\n" + b"\0" * 64)
    with pytest.raises(SystemExit):
        seed.assert_binary_arch(text, "x86_64")


# --- manifest -------------------------------------------------------------------------------------

_SEED_MANIFEST = {
    "schema_version": 1, "version": "0.38.0", "platform": "darwin-arm64", "runtime_layout_version": 1,
    "runtime_payload_version": "0.38.0", "export_registry_version": 14,
    "services": {"backend_url": "http://127.0.0.1:9999", "chart_url": "http://127.0.0.1:8899",
                 "start_script": "Horosa-Web/start_horosa_local.sh", "stop_script": "Horosa-Web/stop_horosa_local.sh"},
    "runtimes": {"python": "runtime/mac/python/bin/python3", "java": "runtime/mac/java/bin/java", "node": "runtime/mac/node/bin/node"},
    "artifacts": {"horosa_web_root": "Horosa-Web", "astropy_root": "Horosa-Web/astropy", "boot_jar": "runtime/mac/bundle/astrostudyboot.jar",
                  "horosa_core_js_root": "horosa-core-js"},
}


def test_derive_manifest_inherits_constants_and_swaps_only_platform_keys() -> None:
    derived = seed.derive_manifest(
        _SEED_MANIFEST, platform="win32-x64",
        runtimes={"python": "runtime/windows/python/python.exe", "java": "runtime/windows/java/bin/java.exe", "node": "runtime/windows/node/node.exe"},
        boot_jar="runtime/windows/bundle/astrostudyboot.jar",
        start_script="Horosa-Web/start_horosa_local.ps1", stop_script="Horosa-Web/stop_horosa_local.ps1",
    )
    assert derived["export_registry_version"] == 14 and derived["version"] == "0.38.0" and derived["schema_version"] == 1
    assert derived["platform"] == "win32-x64"
    assert derived["services"]["backend_url"] == "http://127.0.0.1:9999"
    assert derived["services"]["start_script"].endswith(".ps1")
    assert derived["artifacts"]["boot_jar"] == "runtime/windows/bundle/astrostudyboot.jar"
    assert derived["artifacts"]["astropy_root"] == "Horosa-Web/astropy"
    assert derived["derived_from"] == {"platform": "darwin-arm64", "version": "0.38.0"}
    assert "platform_requirements" not in derived
    assert list(derived)[:3] == ["schema_version", "version", "platform"]


def test_derive_manifest_refuses_a_seed_without_the_registry_constant() -> None:
    broken = {k: v for k, v in _SEED_MANIFEST.items() if k != "export_registry_version"}
    with pytest.raises(SystemExit):
        seed.derive_manifest(broken, platform="win32-x64", runtimes={}, boot_jar="x", start_script="a", stop_script="b")


# --- verify_seed on a synthetic archive -------------------------------------------------------------

def _synthetic_seed(tmp_path: Path, *, version: str = "0.38.0", drop: str | None = None) -> Path:
    stage = tmp_path / "stage" / "runtime-payload"
    for required in verifier.REQUIRED_ENTRIES["darwin-arm64"]:
        rel = required[len("runtime-payload/"):]
        if required.endswith("/"):
            (stage / rel / "placeholder.txt").parent.mkdir(parents=True, exist_ok=True)
            (stage / rel / "placeholder.txt").write_text("x", encoding="utf-8")
        else:
            (stage / rel).parent.mkdir(parents=True, exist_ok=True)
            (stage / rel).write_text("x", encoding="utf-8")
    manifest = dict(_SEED_MANIFEST, version=version, runtime_payload_version=version)
    (stage / "runtime-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if drop:
        (stage / drop).unlink()
    archive = tmp_path / f"horosa-runtime-darwin-arm64-v{version}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(stage, arcname="runtime-payload")
    return archive


def test_verify_seed_accepts_a_complete_seed_and_returns_its_manifest(tmp_path: Path) -> None:
    archive = _synthetic_seed(tmp_path)
    manifest = seed.verify_seed(archive)
    assert manifest["platform"] == "darwin-arm64" and manifest["version"] == "0.38.0"
    tree = seed.materialize_seed(archive, tmp_path / "cache")
    assert tree.boot_jar.is_file() and tree.horosa_web.is_dir() and tree.core_js.is_dir()
    assert (tmp_path / "cache").iterdir()  # memoised by sha


def test_verify_seed_refuses_an_incomplete_or_mismatched_seed(tmp_path: Path) -> None:
    """Negative controls: a seed missing kin_year_domain.py, and a seed whose version is not the one asked for."""
    with pytest.raises(SystemExit):
        seed.verify_seed(_synthetic_seed(tmp_path / "a", drop="Horosa-Web/vendor/kin_year_domain.py"))
    with pytest.raises(SystemExit):
        seed.verify_seed(_synthetic_seed(tmp_path / "b", version="0.37.0"), expected_version="0.38.0")
    with pytest.raises(SystemExit):
        seed.verify_seed(tmp_path / "missing.tar.gz")


def test_copy_platform_tree_drops_the_seeds_launchers_for_ps1_targets(tmp_path: Path) -> None:
    archive = _synthetic_seed(tmp_path)
    tree = seed.materialize_seed(archive, tmp_path / "cache")
    payload = tmp_path / "payload"
    seed.copy_platform_tree(tree, payload, launchers="ps1", os_dir="windows")
    assert (payload / "runtime" / "windows" / "bundle" / "astrostudyboot.jar").is_file()
    assert not (payload / "Horosa-Web" / "start_horosa_local.sh").exists()
    assert (payload / "Horosa-Web" / "astropy").is_dir() and (payload / "horosa-core-js" / "bin" / "cli.mjs").is_file()


def test_find_jdk_home_handles_temurin_layouts(tmp_path: Path) -> None:
    flat = tmp_path / "flat" / "jdk-17.0.20.1+1"
    (flat / "bin").mkdir(parents=True); (flat / "jmods").mkdir()
    assert seed.find_jdk_home(tmp_path / "flat") == flat
    mac = tmp_path / "mac" / "jdk-17.0.20.1+1" / "Contents" / "Home"
    (mac / "bin").mkdir(parents=True); (mac / "jmods").mkdir()
    assert seed.find_jdk_home(tmp_path / "mac") == mac
    with pytest.raises(SystemExit):
        seed.find_jdk_home(tmp_path / "nowhere")


# ---------------------------------------------------------------- pip interpreter resolution (A5 dry run #1)


def test_resolve_pip_python_skips_interpreters_without_pip(tmp_path, monkeypatch) -> None:
    """uv 的 venv 没有 pip：`sys.executable -m pip` 会 "No module named pip"——解析器必须跳过它找到有 pip 的那个。"""
    venv_python = tmp_path / "venv" / "python"
    base_python = tmp_path / "base" / "python"
    for path in (venv_python, base_python):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    class Done:
        def __init__(self, code):
            self.returncode = code

    def fake_run(cmd, **kwargs):
        return Done(0 if cmd[0] == str(base_python) else 1)

    monkeypatch.setattr(seed.subprocess, "run", fake_run)
    monkeypatch.setattr(seed.sys, "executable", str(venv_python))
    monkeypatch.setattr(seed.sys, "base_prefix", str(tmp_path / "nowhere"))
    monkeypatch.setattr(seed.shutil, "which", lambda name: str(base_python) if name == "python3" else None)
    assert seed.resolve_pip_python(None) == str(base_python)
    assert seed.resolve_pip_python(str(base_python)) == str(base_python), "explicit --python wins"
    assert seed._pip(None)[1:] == ["-m", "pip"]

    monkeypatch.setattr(seed.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="no interpreter with pip"):
        seed.resolve_pip_python(None)
