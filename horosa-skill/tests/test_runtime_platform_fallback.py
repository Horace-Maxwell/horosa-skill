"""v0.38.0 A4 — installer platform policy: Windows on ARM installs the win32-x64 payload under emulation
(announced, never silent); Intel Mac / Linux are refused with the gateway advice; a payload's `min_os`
floor is honoured; doctor names host vs payload platform.

**Why the old checks could not catch it**: `install()` looked the host key up in `manifest.platforms`
and raised on a miss — there was no notion of "another payload that works here", so an ARM Windows box
was a dead end even though the x64 toolchain runs under Windows 11 emulation (A0 runner-probe).
`_normalize_manifest_data` dropped every key it did not know, so the derived payload's
`platform_requirements` (A2) never reached the installed manifest — nothing could check `min_os`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import RuntimeInstallError
from horosa_skill.runtime import manager as manager_module
from horosa_skill.runtime.manager import (
    PLATFORM_FALLBACKS,
    SUPPORTED_PAYLOAD_PLATFORMS,
    HorosaRuntimeManager,
    _assert_min_os,
    _platform_key,
)

from test_runtime_manager import create_runtime_archive, create_windows_runtime_archive

PKG_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((PKG_ROOT / "contracts" / "release_platforms.json").read_text(encoding="utf-8"))


def _settings(tmp_path: Path, platform_name: str) -> Settings:
    return Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_platform=platform_name,
    )


def _manifest(tmp_path: Path, platforms: dict[str, dict], *, version: str = "1.2.3") -> str:
    path = tmp_path / "release-manifest.json"
    path.write_text(json.dumps({"version": version, "platforms": platforms}), encoding="utf-8")
    return path.resolve().as_uri()


# ---------------------------------------------------------------- lockstep with the contract


def test_installer_constants_match_the_release_platform_contract() -> None:
    """The wheel does not ship contracts/, so the installer duplicates the policy — keep both in step."""
    assert set(SUPPORTED_PAYLOAD_PLATFORMS) == set(CONTRACT["platforms"])
    assert {k: (v["installs"], v["mode"]) for k, v in CONTRACT["aliases"].items()} == PLATFORM_FALLBACKS
    for unsupported in CONTRACT["unsupported"]:
        assert unsupported not in PLATFORM_FALLBACKS and unsupported not in SUPPORTED_PAYLOAD_PLATFORMS


def test_darwin_x64_never_falls_back_to_arm64() -> None:
    """Rosetta runs x86_64 on arm64, not the reverse — the constant itself must say so."""
    assert "darwin-x64" not in PLATFORM_FALLBACKS
    assert all(installed != "darwin-arm64" for installed, _mode in PLATFORM_FALLBACKS.values())


# ---------------------------------------------------------------- install(): fallback


def test_windows_on_arm_installs_the_x64_payload_and_says_so(tmp_path: Path) -> None:
    archive = create_windows_runtime_archive(tmp_path)
    manifest_url = _manifest(
        tmp_path,
        {"win32-x64": {"url": archive.resolve().as_uri(), "sha256": "", "archive_type": "zip"}},
    )
    manager = HorosaRuntimeManager(_settings(tmp_path, "win32-arm64"))

    result = manager.install(manifest_url=manifest_url)

    assert result["ok"] is True
    assert result["platform"] == "win32-x64"
    assert result["platform_fallback"] == {"requested": "win32-arm64", "installed": "win32-x64", "mode": "x64-emulation"}
    codes = [w["code"] for w in result["warnings"]]
    assert codes == ["runtime.platform_emulated"], "the fallback must be announced, never silent"
    assert result["manifest"]["platform"] == "win32-x64"


def test_windows_on_arm_fallback_is_idempotent_and_still_announced(tmp_path: Path) -> None:
    """The version short-circuit path must carry the same fallback note (setup re-runs install)."""
    archive = create_windows_runtime_archive(tmp_path)
    manifest_url = _manifest(
        tmp_path,
        {"win32-x64": {"url": archive.resolve().as_uri(), "sha256": "", "archive_type": "zip"}},
    )
    manager = HorosaRuntimeManager(_settings(tmp_path, "win32-arm64"))
    manager.install(manifest_url=manifest_url)

    again = manager.install(manifest_url=manifest_url)

    assert again["skipped_download"] is True
    assert again["platform"] == "win32-x64"
    assert again["platform_fallback"]["mode"] == "x64-emulation"
    assert [w["code"] for w in again["warnings"]] == ["runtime.platform_emulated"]


def test_native_install_carries_no_fallback_note(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    manifest_url = _manifest(
        tmp_path,
        {"darwin-arm64": {"url": archive.resolve().as_uri(), "sha256": "", "archive_type": "tar.gz"}},
    )
    result = HorosaRuntimeManager(_settings(tmp_path, "darwin-arm64")).install(manifest_url=manifest_url)

    assert result["platform_fallback"] is None
    assert result["warnings"] == []


def test_windows_on_arm_without_any_x64_payload_is_still_a_dead_end_with_advice(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    manifest_url = _manifest(
        tmp_path,
        {"darwin-arm64": {"url": archive.resolve().as_uri(), "sha256": "", "archive_type": "tar.gz"}},
    )
    with pytest.raises(RuntimeInstallError) as excinfo:
        HorosaRuntimeManager(_settings(tmp_path, "win32-arm64")).install(manifest_url=manifest_url)

    assert excinfo.value.code == "runtime.install_missing_platform"
    assert "win32-x64" in excinfo.value.details["reason"]
    assert excinfo.value.details["supported_platforms"] == ["darwin-arm64"]


def test_intel_mac_is_refused_even_when_an_arm64_payload_exists(tmp_path: Path) -> None:
    """🔴 Negative control for the fallback: darwin-x64 must NOT quietly get the arm64 archive."""
    archive = create_runtime_archive(tmp_path)
    manifest_url = _manifest(
        tmp_path,
        {
            "darwin-arm64": {"url": archive.resolve().as_uri(), "sha256": "", "archive_type": "tar.gz"},
            "win32-x64": {"url": archive.resolve().as_uri(), "sha256": "", "archive_type": "zip"},
        },
    )
    settings = _settings(tmp_path, "darwin-x64")
    with pytest.raises(RuntimeInstallError) as excinfo:
        HorosaRuntimeManager(settings).install(manifest_url=manifest_url)

    assert excinfo.value.code == "runtime.install_missing_platform"
    assert "Rosetta" in excinfo.value.details["reason"]
    assert "HOROSA_SERVER_ROOT" in excinfo.value.details["next_action"]
    assert not settings.runtime_current_dir.exists()


# ---------------------------------------------------------------- min_os


def test_min_os_refuses_an_older_host() -> None:
    with pytest.raises(RuntimeInstallError) as excinfo:
        _assert_min_os("10.0.17763", "win32-x64", host_version="10.0.17134")
    assert excinfo.value.code == "runtime.install_os_too_old"
    assert excinfo.value.details["min_os"] == "10.0.17763"
    assert excinfo.value.details["host_os"] == "10.0.17134"
    assert "HOROSA_SERVER_ROOT" in excinfo.value.details["next_action"]


@pytest.mark.parametrize(
    ("min_os", "host"),
    [
        ("10.0.17763", "10.0.17763"),  # equal
        ("10.0.17763", "10.0.22631"),  # newer build
        ("12.0", "14.6.1"),  # macOS
        ("10.0.17763", ""),  # unreadable host version must not block
        (None, "1.0"),  # payload without a floor
        ("", "1.0"),
    ],
)
def test_min_os_accepts_equal_newer_or_unknown(min_os, host) -> None:
    _assert_min_os(min_os, "win32-x64", host_version=host)


def test_install_checks_the_manifest_entry_min_os_before_downloading(tmp_path: Path, monkeypatch) -> None:
    archive = create_windows_runtime_archive(tmp_path)
    manifest_url = _manifest(
        tmp_path,
        {"win32-x64": {"url": archive.resolve().as_uri(), "sha256": "", "archive_type": "zip", "min_os": "10.0.17763"}},
    )
    monkeypatch.setattr(manager_module, "host_os_version", lambda: "10.0.10240")
    settings = _settings(tmp_path, "win32-x64")

    with pytest.raises(RuntimeInstallError) as excinfo:
        HorosaRuntimeManager(settings).install(manifest_url=manifest_url)

    assert excinfo.value.code == "runtime.install_os_too_old"
    assert not settings.runtime_current_dir.exists()


def test_install_checks_the_payload_platform_requirements_min_os(tmp_path: Path, monkeypatch) -> None:
    """A derived payload (A2) carries `platform_requirements.min_os` inside the archive itself."""
    archive = create_windows_runtime_archive(tmp_path)
    _inject_platform_requirements(archive, {"min_os": "10.0.17763", "arch": "x64"})
    monkeypatch.setattr(manager_module, "host_os_version", lambda: "6.3.9600")
    settings = _settings(tmp_path, "win32-x64")

    with pytest.raises(RuntimeInstallError) as excinfo:
        HorosaRuntimeManager(settings).install(archive=str(archive))

    assert excinfo.value.code == "runtime.install_os_too_old"
    assert not settings.runtime_current_dir.exists()


def _inject_platform_requirements(archive: Path, requirements: dict, extra: dict | None = None) -> None:
    """Rewrite runtime-manifest.json inside a zip archive (test payloads are zips for Windows)."""
    import shutil
    import zipfile

    tmp = archive.with_suffix(".tmp.zip")
    with zipfile.ZipFile(archive) as src, zipfile.ZipFile(tmp, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename.endswith("runtime-manifest.json"):
                manifest = json.loads(data.decode("utf-8"))
                manifest["platform_requirements"] = requirements
                manifest.update(extra or {})
                data = json.dumps(manifest).encode("utf-8")
            dst.writestr(item, data)
    shutil.move(str(tmp), str(archive))


# ---------------------------------------------------------------- manifest passthrough + doctor


def test_installed_manifest_keeps_platform_requirements_and_derived_from(tmp_path: Path) -> None:
    """🔴 `_normalize_manifest_data` used to drop every unknown key — the A2 provenance vanished."""
    archive = create_windows_runtime_archive(tmp_path)
    _inject_platform_requirements(
        archive,
        {"min_os": "10.0.17763", "arch": "x64"},
        extra={"derived_from": {"seed_platform": "darwin-arm64", "seed_sha256": "abc"}},
    )
    settings = _settings(tmp_path, "win32-x64")
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    installed = json.loads((settings.runtime_current_dir / "runtime-manifest.json").read_text(encoding="utf-8"))
    assert installed["platform_requirements"] == {"min_os": "10.0.17763", "arch": "x64"}
    assert installed["derived_from"]["seed_platform"] == "darwin-arm64"
    assert manager.load_installed_manifest(strict=True)["platform_requirements"]["min_os"] == "10.0.17763"


def test_doctor_reports_host_vs_payload_platform_and_emulation(tmp_path: Path) -> None:
    archive = create_windows_runtime_archive(tmp_path)
    _inject_platform_requirements(archive, {"min_os": "10.0.17763", "arch": "x64"})
    manifest_url = _manifest(
        tmp_path,
        {"win32-x64": {"url": archive.resolve().as_uri(), "sha256": "", "archive_type": "zip"}},
    )
    manager = HorosaRuntimeManager(_settings(tmp_path, "win32-arm64"))
    manager.install(manifest_url=manifest_url)

    report = manager.doctor()

    assert report["host_platform"] == "win32-arm64"
    assert report["payload_platform"] == "win32-x64"
    assert report["emulated"] is True
    assert report["platform_requirements"] == {"min_os": "10.0.17763", "arch": "x64"}


def test_doctor_native_install_is_not_emulated(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    manager = HorosaRuntimeManager(_settings(tmp_path, "darwin-arm64"))
    manager.install(archive=str(archive))

    report = manager.doctor()

    assert report["host_platform"] == "darwin-arm64"
    assert report["payload_platform"] == "darwin-arm64"
    assert report["emulated"] is False


def test_doctor_without_an_install_has_no_payload_platform(tmp_path: Path) -> None:
    report = HorosaRuntimeManager(_settings(tmp_path, "win32-arm64")).doctor()

    assert report["installed"] is False
    assert report["payload_platform"] is None
    assert report["emulated"] is False
    assert report["platform_requirements"] is None


# ---------------------------------------------------------------- host key on Windows-on-ARM


def test_platform_key_reads_the_native_arch_under_x64_emulation(monkeypatch) -> None:
    """An x64 CPython on an ARM64 Windows host reports AMD64 — PROCESSOR_ARCHITEW6432 tells the truth."""
    monkeypatch.setattr(manager_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(manager_module.platform, "machine", lambda: "AMD64")
    monkeypatch.setenv("PROCESSOR_ARCHITEW6432", "ARM64")
    assert _platform_key() == "win32-arm64"

    monkeypatch.delenv("PROCESSOR_ARCHITEW6432")
    assert _platform_key() == "win32-x64"


def test_platform_key_ignores_the_wow64_variable_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(manager_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(manager_module.platform, "machine", lambda: "arm64")
    monkeypatch.setenv("PROCESSOR_ARCHITEW6432", "ARM64")
    assert _platform_key() == "darwin-arm64"


# ---------------------------------------------------------------- CLI support flag


def test_cli_platform_supported_includes_fallback_hosts(monkeypatch) -> None:
    from horosa_skill.surfaces.cli import _platform_supported

    monkeypatch.setattr("horosa_skill.runtime.manager._platform_key", lambda: "win32-arm64")
    assert _platform_supported({"installed": False}) is True
    monkeypatch.setattr("horosa_skill.runtime.manager._platform_key", lambda: "darwin-x64")
    assert _platform_supported({"installed": False}) is False
    assert _platform_supported({"installed": True}) is True


# ---------------------------------------------------------------- arch: process vs native


def test_native_machine_sees_through_wow64_on_windows(monkeypatch) -> None:
    """x64 Python on an ARM64 Windows host: process says AMD64, PROCESSOR_ARCHITEW6432 says ARM64."""
    monkeypatch.setattr(manager_module.os, "name", "nt")
    monkeypatch.setattr(manager_module.platform, "machine", lambda: "AMD64")
    monkeypatch.setenv("PROCESSOR_ARCHITECTURE", "AMD64")
    monkeypatch.setenv("PROCESSOR_ARCHITEW6432", "ARM64")
    # no ctypes.windll off Windows → the env fallback is what runs here
    report = manager_module.arch_report()
    assert report == {"process": "x64", "native": "arm64", "emulated": True}


def test_native_machine_on_a_native_windows_process(monkeypatch) -> None:
    monkeypatch.setattr(manager_module.os, "name", "nt")
    monkeypatch.setattr(manager_module.platform, "machine", lambda: "ARM64")
    monkeypatch.setenv("PROCESSOR_ARCHITECTURE", "ARM64")
    monkeypatch.delenv("PROCESSOR_ARCHITEW6432", raising=False)
    assert manager_module.arch_report() == {"process": "arm64", "native": "arm64", "emulated": False}


def test_rosetta_python_still_gets_the_arm64_payload(monkeypatch) -> None:
    """The payload is self-contained; an x86_64 host Python on Apple Silicon must not be sent to the dead end."""
    monkeypatch.setattr(manager_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(manager_module.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(manager_module, "_darwin_translated", lambda: True)
    assert _platform_key() == "darwin-arm64"
    monkeypatch.setattr(manager_module.sys, "platform", "darwin")
    assert manager_module.native_machine() == "arm64"

    monkeypatch.setattr(manager_module, "_darwin_translated", lambda: False)
    assert _platform_key() == "darwin-x64", "a real Intel Mac stays darwin-x64"


def test_doctor_carries_the_arch_block(tmp_path: Path) -> None:
    report = HorosaRuntimeManager(_settings(tmp_path, "darwin-arm64")).doctor()
    assert set(report["arch"]) == {"process", "native", "emulated"}
    assert isinstance(report["arch"]["emulated"], bool)
