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
