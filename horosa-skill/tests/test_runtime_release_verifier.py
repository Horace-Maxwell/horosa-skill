from __future__ import annotations

import importlib.util
import json
import tarfile
import zipfile
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_runtime_release.py"
SPEC = importlib.util.spec_from_file_location("verify_runtime_release", SCRIPT_PATH)
assert SPEC and SPEC.loader
verify_runtime_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_runtime_release)


def _payload_manifest(*, version: str, platform: str) -> bytes:
    return (
        json.dumps(
            {
                "schema_version": 1,
                "version": version,
                "runtime_payload_version": version,
                "platform": platform,
            },
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _write_tar(path: Path, *, version: str, platform: str) -> None:
    manifest = _payload_manifest(version=version, platform=platform)
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo("runtime-payload/runtime-manifest.json")
        info.size = len(manifest)
        archive.addfile(info, fileobj=__import__("io").BytesIO(manifest))


def _write_zip(path: Path, *, version: str, platform: str) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("runtime-payload/runtime-manifest.json", _payload_manifest(version=version, platform=platform))


def test_assert_payload_manifest_accepts_matching_version(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.tar.gz"
    _write_tar(archive, version="0.5.9", platform="darwin-arm64")

    verify_runtime_release._assert_payload_manifest(archive, "darwin-arm64", "0.5.9")


def test_assert_payload_manifest_rejects_stale_version(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.zip"
    _write_zip(archive, version="0.5.6", platform="win32-x64")

    with pytest.raises(SystemExit, match="stale or mismatched embedded runtime manifest"):
        verify_runtime_release._assert_payload_manifest(archive, "win32-x64", "0.5.9")


_WIN_FILE_ENTRIES = [
    "runtime-payload/runtime-manifest.json",
    "runtime-payload/Horosa-Web/start_horosa_local.ps1",
    "runtime-payload/Horosa-Web/stop_horosa_local.ps1",
    "runtime-payload/Horosa-Web/astropy/__init__.py",
    "runtime-payload/Horosa-Web/vendor/kinqimen/__init__.py",
    "runtime-payload/Horosa-Web/vendor/kintaiyi/__init__.py",
    "runtime-payload/Horosa-Web/vendor/kinjinkou/__init__.py",
    "runtime-payload/Horosa-Web/vendor/kinwangji/__init__.py",
    "runtime-payload/Horosa-Web/vendor/kinwuzhao/__init__.py",
    "runtime-payload/Horosa-Web/vendor/taixuanshifa/__init__.py",
    "runtime-payload/Horosa-Web/vendor/jingjue/__init__.py",
    "runtime-payload/Horosa-Web/vendor/shenyishu/__init__.py",
    "runtime-payload/Horosa-Web/vendor/kin_year_domain.py",
    "runtime-payload/Horosa-Web/astropy/astrostudy/geomancy/data/ifa_odu.json",
    "runtime-payload/Horosa-Web/vendor/kinastro/astro/__init__.py",
    "runtime-payload/Horosa-Web/vendor/kinastro/astro/shaozi/data/shaozi_tiaowen_6144.json",
    "runtime-payload/runtime/windows/python/python.exe",
    "runtime-payload/runtime/windows/java/bin/java.exe",
    "runtime-payload/runtime/windows/node/node.exe",
    "runtime-payload/runtime/windows/bundle/astrostudyboot.jar",
    "runtime-payload/horosa-core-js/bin/cli.mjs",
    "runtime-payload/horosa-core-js/node_modules/lunar-javascript/package.json",
]
_SWEFILES_DIR = "runtime-payload/Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles/"


_LAUNCHERS = (
    "runtime-payload/Horosa-Web/start_horosa_local.ps1",
    "runtime-payload/Horosa-Web/stop_horosa_local.ps1",
)


def _write_full_win_zip(path: Path, *, swefiles_empty: bool, launcher_bom: bool = True) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name in _WIN_FILE_ENTRIES:
            if name in _LAUNCHERS:
                # 真实形态：UTF-8 BOM 打头（Windows PowerShell 5.1 才会按 UTF-8 解码）
                archive.writestr(name, (b"\xef\xbb\xbf" if launcher_bom else b"") + b"Write-Host 'x'\n")
            else:
                archive.writestr(name, b"x")
        if swefiles_empty:
            archive.writestr(_SWEFILES_DIR, b"")  # bare directory-marker entry, no files inside
        else:
            archive.writestr(_SWEFILES_DIR + "seas_18.se1", b"ephemeris")


def test_assert_entries_rejects_empty_required_directory(tmp_path: Path) -> None:
    # Regression: a zip whose required dir (swefiles) is only a bare marker must FAIL — previously
    # `startswith(required)` matched the marker against itself and greenlit a broken runtime.
    archive = tmp_path / "runtime.zip"
    _write_full_win_zip(archive, swefiles_empty=True)
    with pytest.raises(SystemExit, match="missing required entries"):
        verify_runtime_release._assert_entries(archive, "win32-x64")


def test_assert_entries_accepts_required_directory_with_a_real_file(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.zip"
    _write_full_win_zip(archive, swefiles_empty=False)
    verify_runtime_release._assert_entries(archive, "win32-x64")  # must not raise


def test_windows_launchers_must_carry_a_utf8_bom(tmp_path: Path) -> None:
    """无 BOM 的 .ps1 会被 Windows PowerShell 5.1 按 ANSI 解码 —— 一个非 ASCII 字符就能打成 parse
    error，启动器未跑先死（v0.25.0 Windows 补建时真炸过）。发布闸必须拦在上传之前。"""
    archive = tmp_path / "runtime.zip"
    _write_full_win_zip(archive, swefiles_empty=False, launcher_bom=False)
    with pytest.raises(SystemExit, match="lack a UTF-8 BOM"):
        verify_runtime_release._assert_windows_launchers_are_bom_encoded(archive)


def test_windows_launchers_with_a_bom_pass(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.zip"
    _write_full_win_zip(archive, swefiles_empty=False)
    verify_runtime_release._assert_windows_launchers_are_bom_encoded(archive)  # must not raise
