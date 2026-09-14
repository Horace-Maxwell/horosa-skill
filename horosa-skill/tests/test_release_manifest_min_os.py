"""发布清单带 `min_os`（v0.38.1 R16）：来自 contracts/release_platforms.json，install 下载前就能拒绝老系统。"""
from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((PKG_ROOT / "contracts" / "release_platforms.json").read_text(encoding="utf-8"))


def test_every_shipped_platform_declares_a_parseable_min_os() -> None:
    from horosa_skill.runtime.manager import _version_tuple

    for key, entry in CONTRACT["platforms"].items():
        assert _version_tuple(entry.get("min_os", "")), (key, entry.get("min_os"))
    assert CONTRACT["platforms"]["win32-x64"]["min_os"] == "10.0.17763"
    assert CONTRACT["platforms"]["darwin-arm64"]["min_os"] == "11.0"


def test_generate_release_manifest_copies_min_os_from_the_contract(tmp_path: Path) -> None:
    darwin = tmp_path / "horosa-runtime-darwin-arm64-v9.9.9.tar.gz"
    with tarfile.open(darwin, "w:gz") as tar:
        p = tmp_path / "x.txt"
        p.write_text("x", encoding="utf-8")
        tar.add(p, arcname="runtime-payload/x.txt")
    windows = tmp_path / "horosa-runtime-win32-x64-v9.9.9.zip"
    with zipfile.ZipFile(windows, "w") as archive:
        archive.writestr("runtime-payload/x.txt", "x")
    out = tmp_path / "runtime-manifest.json"
    completed = subprocess.run(
        [sys.executable, str(PKG_ROOT / "scripts" / "generate_release_manifest.py"), "--version", "9.9.9",
         "--darwin-archive", str(darwin), "--windows-archive", str(windows),
         "--url-base", "https://example.invalid/releases/download/v9.9.9", "--output", str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert completed.returncode == 0, completed.stderr
    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert manifest["platforms"]["darwin-arm64"]["min_os"] == CONTRACT["platforms"]["darwin-arm64"]["min_os"]
    assert manifest["platforms"]["win32-x64"]["min_os"] == CONTRACT["platforms"]["win32-x64"]["min_os"]
    assert manifest["platforms"]["win32-x64"]["size"] == windows.stat().st_size


def test_install_refuses_an_old_host_from_the_manifest_min_os_before_downloading(tmp_path: Path, monkeypatch) -> None:
    """负向对照：没有 min_os 的清单（旧形状）不会在下载前拦；带 min_os 的会。"""
    import pytest

    from horosa_skill.config import Settings
    from horosa_skill.errors import RuntimeInstallError
    from horosa_skill.runtime import manager as manager_module
    from horosa_skill.runtime.manager import HorosaRuntimeManager

    monkeypatch.setattr(manager_module, "host_os_version", lambda: "10.0.10240")  # Windows 10 1507
    settings = Settings(runtime_root=tmp_path / "rt", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_platform="win32-x64")
    manager = HorosaRuntimeManager(settings)

    def boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("must refuse before downloading")

    monkeypatch.setattr(manager, "_materialize_archive", boom)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": "9.9.9", "platforms": {"win32-x64": {
        "url": "https://example.invalid/x.zip", "sha256": "", "archive_type": "zip", "min_os": "10.0.17763"}}}), encoding="utf-8")
    with pytest.raises(RuntimeInstallError) as excinfo:
        manager.install(manifest_url=manifest.resolve().as_uri())
    assert excinfo.value.code == "runtime.install_os_too_old"
