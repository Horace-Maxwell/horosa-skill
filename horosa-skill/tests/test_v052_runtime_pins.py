"""审计 PF-01 第 3 层：信任根随包走——发布页 wheel 带 runtime_pins.json，清单（不论来自原站还是镜像）的摘要必须与钉值一致。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import RuntimeValidationError
from horosa_skill.runtime import pins
from horosa_skill.runtime.manager import HorosaRuntimeManager, _platform_key

SHA_GOOD, SHA_BAD = "a" * 64, "f" * 64


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, manifest_sha: str, manifest_version: str = "9.9.9") -> tuple[HorosaRuntimeManager, Path]:
    platform = _platform_key()
    pin_file = tmp_path / "runtime_pins.json"
    pin_file.write_text(json.dumps({"version": "9.9.9", "platforms": {platform: {"sha256": SHA_GOOD, "size": 100}},
                                    "core_js": {"sha256": SHA_GOOD, "size": 7}}), encoding="utf-8")
    monkeypatch.setattr(pins, "PINS_PATH", pin_file)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": manifest_version, "platforms": {platform: {
        "url": "https://example.invalid/never.tar.gz", "sha256": manifest_sha, "size": 100}},
        "core_js": {"url": "https://example.invalid/core.tgz", "sha256": manifest_sha, "size": 7}}), encoding="utf-8")
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path / "d",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    manager = HorosaRuntimeManager(settings)
    monkeypatch.setattr(manager, "_materialize_archive", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not download")))
    return manager, manifest


def test_a_manifest_that_disagrees_with_the_pins_is_refused_before_any_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """负向对照（实跑过）：install 不调 check_runtime_pin → 继续走到下载（替身断言）→ 红。"""
    manager, manifest = _setup(tmp_path, monkeypatch, manifest_sha=SHA_BAD)
    with pytest.raises(RuntimeValidationError) as caught:
        manager.install(manifest_url=str(manifest))
    assert caught.value.code == "runtime.install_pin_mismatch"
    assert caught.value.details["pinned_sha256"] == SHA_GOOD and caught.value.details["manifest_sha256"] == SHA_BAD


def test_the_engine_asset_is_checked_against_the_pins_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager, manifest = _setup(tmp_path, monkeypatch, manifest_sha=SHA_BAD)
    with pytest.raises(RuntimeValidationError) as caught:
        manager.install(manifest_url=str(manifest), engine_only=True)
    assert caught.value.code == "runtime.install_pin_mismatch" and caught.value.details["asset"] == "core_js"


def test_an_unpinned_version_needs_a_digest_or_an_explicit_opt_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager, manifest = _setup(tmp_path, monkeypatch, manifest_sha=SHA_GOOD, manifest_version="9.8.0")
    with pytest.raises(RuntimeValidationError) as caught:
        manager.install(manifest_url=str(manifest))
    assert caught.value.code == "runtime.install_unpinned_version"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert manager.check_runtime_pin(data, meta=data["platforms"][_platform_key()], platform=_platform_key(), core_js=False,
                                     sha256_given=False, allow_unpinned=True, location=str(manifest)) is False


def test_matching_pins_pass_and_a_source_checkout_pins_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager, manifest = _setup(tmp_path, monkeypatch, manifest_sha=SHA_GOOD)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert manager.check_runtime_pin(data, meta=data["platforms"][_platform_key()], platform=_platform_key(), core_js=False,
                                     sha256_given=False, allow_unpinned=False, location=None) is True
    monkeypatch.setattr(pins, "PINS_PATH", tmp_path / "absent.json")
    assert manager.check_runtime_pin(data, meta=data["platforms"][_platform_key()], platform=_platform_key(), core_js=False,
                                     sha256_given=False, allow_unpinned=False, location=None) is False


def test_the_source_tree_never_carries_a_pins_file() -> None:
    """钉值只由发布流水线在两个平台归档齐了之后生成；提交进源码树 = 开发版也按某个旧版本的钉值拒装。"""
    root = Path(__file__).resolve().parents[1]
    tracked = subprocess.run(["git", "ls-files", "src/horosa_skill/data/runtime_pins.json"], cwd=root, capture_output=True,
                             text=True, check=False).stdout.strip()
    assert tracked == "" and not (root / "src" / "horosa_skill" / "data" / "runtime_pins.json").exists()


def test_pins_from_a_dual_platform_manifest() -> None:
    manifest = {"version": "1.2.3", "platforms": {"darwin-arm64": {"url": "https://x/a.tar.gz", "sha256": "A" * 64, "size": 1},
                                                 "win32-x64": {"url": "https://x/b.zip", "sha256": "b" * 64, "size": 2}},
                "core_js": {"url": "https://x/c.tgz", "sha256": "c" * 64, "size": 3}}
    out = pins.pins_from_manifest(manifest)
    assert out["platforms"]["darwin-arm64"] == {"sha256": "a" * 64, "size": 1, "name": "a.tar.gz"} and out["core_js"]["name"] == "c.tgz"
