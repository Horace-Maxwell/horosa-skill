"""generate_release_manifest.py (v0.38.0 A3): every platform entry carries the archive's real `size`, and
`--url-base` produces tag-pinned URLs so pin-forward is visible from the manifest alone."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_release_manifest.py"


def _archives(tmp_path: Path) -> tuple[Path, Path]:
    tar = tmp_path / "horosa-runtime-darwin-arm64-v0.38.0.tar.gz"
    tar.write_bytes(b"x" * 1234)
    zip_ = tmp_path / "horosa-runtime-win32-x64-v0.38.0.zip"
    zip_.write_bytes(b"y" * 4321)
    return tar, zip_


def test_manifest_carries_sizes_and_tag_pinned_urls(tmp_path: Path) -> None:
    tar, zip_ = _archives(tmp_path)
    out = tmp_path / "runtime-manifest.json"
    subprocess.run([sys.executable, str(SCRIPT), "--version", "0.38.0", "--url-base", "https://github.com/o/r/releases/download/v0.38.0/",
                    "--darwin-archive", str(tar), "--windows-archive", str(zip_), "--output", str(out)], check=True)
    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert manifest["version"] == "0.38.0" and set(manifest["platforms"]) == {"darwin-arm64", "win32-x64"}
    darwin = manifest["platforms"]["darwin-arm64"]
    assert darwin["size"] == 1234 and darwin["archive_type"] == "tar.gz"
    assert darwin["url"] == "https://github.com/o/r/releases/download/v0.38.0/horosa-runtime-darwin-arm64-v0.38.0.tar.gz"
    assert manifest["platforms"]["win32-x64"]["size"] == 4321
    assert manifest["platforms"]["win32-x64"]["url"].endswith("/v0.38.0/horosa-runtime-win32-x64-v0.38.0.zip")


def test_explicit_url_still_wins_and_zero_platforms_is_an_error(tmp_path: Path) -> None:
    tar, _ = _archives(tmp_path)
    out = tmp_path / "m.json"
    subprocess.run([sys.executable, str(SCRIPT), "--version", "0.38.0", "--darwin-archive", str(tar),
                    "--darwin-url", "https://mirror.example/x.tar.gz", "--output", str(out)], check=True)
    assert json.loads(out.read_text(encoding="utf-8"))["platforms"]["darwin-arm64"]["url"] == "https://mirror.example/x.tar.gz"
    failed = subprocess.run([sys.executable, str(SCRIPT), "--version", "0.38.0", "--output", str(out)], capture_output=True)
    assert failed.returncode != 0
