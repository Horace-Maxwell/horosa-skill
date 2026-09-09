"""重打发布资产：只改嵌入清单的版本，其余字节分毫不动。

**为什么需要它**：一次不含 payload 变化的发布仍然必须**换掉资产文件名与嵌入版本**
（`verify_runtime_release.py::_assert_payload_manifest` 要求嵌入清单版本 == 发布清单版本）。
而 Windows 半边的构建输入只存在于 Windows 构建机上 —— mac 上无从重建，只能重打。

重打最容易出的两种错，两条用例各钉一条：
  · 顺手「规范化」了别的条目 —— `.ps1` 的 UTF-8 BOM 一旦丢失，Windows PowerShell 5.1 按 ANSI
    解码，一个非 ASCII 字符就让整个启动器解析失败（v0.25.1 的坑，`_assert_windows_launchers_are_bom_encoded`
    专门守它）；
  · 只改了文件名没改嵌入版本 —— 发布看起来成了，`verify_runtime_release.py` 才会红。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "repack_release_assets.py"
BOM = b"\xef\xbb\xbf"


def _make_zip(path: Path, version: str) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "runtime-payload/runtime-manifest.json",
            json.dumps({"version": version, "runtime_payload_version": version, "platform": "win32-x64"}),
        )
        archive.writestr("runtime-payload/Horosa-Web/start_horosa_local.ps1", BOM + "Write-Host '启动'\n".encode())
        archive.writestr("runtime-payload/Horosa-Web/stop_horosa_local.ps1", BOM + "Write-Host '停止'\n".encode())
        archive.writestr("runtime-payload/engine/blob.bin", bytes(range(256)))


def _run(source: Path, out: Path, version: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--out", str(out), "--version", version],
        capture_output=True, text=True, check=False,
    )


def test_zip_repack_updates_only_the_embedded_manifest(tmp_path) -> None:
    source = tmp_path / "horosa-runtime-win32-x64-v0.36.0.zip"
    out = tmp_path / "horosa-runtime-win32-x64-v0.37.0.zip"
    _make_zip(source, "0.36.0")

    result = _run(source, out, "0.37.0")
    assert result.returncode == 0, result.stderr

    with zipfile.ZipFile(source) as before, zipfile.ZipFile(out) as after:
        assert before.namelist() == after.namelist(), "条目集合与顺序必须原样"
        manifest = json.loads(after.read("runtime-payload/runtime-manifest.json"))
        assert manifest["version"] == "0.37.0"
        assert manifest["runtime_payload_version"] == "0.37.0"
        assert manifest["platform"] == "win32-x64", "清单里别的键不许动"
        for name in before.namelist():
            if name == "runtime-payload/runtime-manifest.json":
                continue
            assert before.read(name) == after.read(name), f"{name} 的字节被改动了"


def test_windows_launchers_keep_their_bom(tmp_path) -> None:
    """🔴 BOM 丢了 → PowerShell 5.1 按 ANSI 解码 → 整个启动器不可用（v0.25.1）。"""
    source = tmp_path / "a.zip"
    out = tmp_path / "b.zip"
    _make_zip(source, "0.36.0")
    assert _run(source, out, "0.37.0").returncode == 0

    with zipfile.ZipFile(out) as archive:
        for name in ("start_horosa_local.ps1", "stop_horosa_local.ps1"):
            data = archive.read(f"runtime-payload/Horosa-Web/{name}")
            assert data.startswith(BOM), f"{name} 丢了 UTF-8 BOM"


def test_tar_repack_preserves_every_other_member(tmp_path) -> None:
    source = tmp_path / "horosa-runtime-darwin-arm64-v0.36.0.tar.gz"
    out = tmp_path / "horosa-runtime-darwin-arm64-v0.37.0.tar.gz"
    payload = tmp_path / "payload"
    (payload / "runtime-payload" / "Horosa-Web").mkdir(parents=True)
    (payload / "runtime-payload" / "runtime-manifest.json").write_text(
        json.dumps({"version": "0.36.0", "runtime_payload_version": "0.36.0"}), encoding="utf-8"
    )
    script = payload / "runtime-payload" / "Horosa-Web" / "start_horosa_local.sh"
    script.write_text("#!/usr/bin/env bash\necho 起动\n", encoding="utf-8")
    script.chmod(0o755)
    with tarfile.open(source, "w:gz") as archive:
        archive.add(payload / "runtime-payload", arcname="runtime-payload")

    assert _run(source, out, "0.37.0").returncode == 0
    with tarfile.open(out) as archive:
        names = archive.getnames()
        assert "runtime-payload/Horosa-Web/start_horosa_local.sh" in names
        manifest = json.loads(archive.extractfile("runtime-payload/runtime-manifest.json").read())
        assert manifest["version"] == "0.37.0"
        member = archive.getmember("runtime-payload/Horosa-Web/start_horosa_local.sh")
        assert member.mode & 0o111, "可执行位必须保住，否则启动脚本跑不了"
        assert archive.extractfile(member).read().decode() == "#!/usr/bin/env bash\necho 起动\n"


def test_repack_refuses_to_overwrite_an_existing_archive(tmp_path) -> None:
    source = tmp_path / "a.zip"
    out = tmp_path / "b.zip"
    _make_zip(source, "0.36.0")
    out.write_bytes(b"existing")
    result = _run(source, out, "0.37.0")
    assert result.returncode != 0
    assert out.read_bytes() == b"existing"


def test_repack_refuses_an_archive_without_a_payload_manifest(tmp_path) -> None:
    source = tmp_path / "a.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("runtime-payload/engine/blob.bin", b"x")
    result = _run(source, tmp_path / "b.zip", "0.37.0")
    assert result.returncode != 0
    assert "runtime-manifest.json" in (result.stdout + result.stderr)
    assert not (tmp_path / "b.zip").exists(), "失败时不许留下半个归档"
