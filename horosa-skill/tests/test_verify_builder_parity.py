from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_builder_parity.py"
SPEC = importlib.util.spec_from_file_location("verify_builder_parity", SCRIPT_PATH)
assert SPEC and SPEC.loader
verify_builder_parity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_builder_parity)


def test_repo_is_currently_in_parity() -> None:
    assert verify_builder_parity.main() == 0


def test_stamped_export_registry_version_is_anchored_to_the_registry_constant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The N-way cross-check can pass with every stamper unanimously wrong — which is exactly how
    # v0.26.0 shipped manifests declaring export contract 11 after the registry constant went to 12.
    # Anchoring to the source-of-truth constant is what closes that seam.
    fake_registry = tmp_path / "registry.py"
    fake_registry.write_text("AI_EXPORT_SETTINGS_VERSION = 9999\n", encoding="utf-8")
    monkeypatch.setattr(
        verify_builder_parity,
        "ANCHORED_CONSTANTS",
        {"export_registry_version": ("AI_EXPORT_SETTINGS_VERSION", fake_registry)},
    )

    assert verify_builder_parity.main() == 1


def test_anchor_points_at_the_real_registry_module() -> None:
    name, source = verify_builder_parity.ANCHORED_CONSTANTS["export_registry_version"]
    assert name == "AI_EXPORT_SETTINGS_VERSION"
    assert source.is_file(), f"anchor source missing: {source}"
    assert f"{name} =" in source.read_text(encoding="utf-8")


def test_every_core_js_npm_dependency_must_ship_on_every_platform(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """v0.48.0：依赖集从 horosa-core-js/package.json 派生——新加一个 npm 依赖却没进两个 builder 的 require_path 与三个平台的
    REQUIRED_ENTRIES，这把锁就红（tz-lookup 是第一个按这条进来的；moment 之前一直没人查）。"""
    import json

    real = json.loads(verify_builder_parity.CORE_JS_PACKAGE.read_text(encoding="utf-8"))
    assert {"tz-lookup", "moment", "lunar-javascript", "astronomy-engine"} <= set(real["dependencies"])
    fake = tmp_path / "package.json"
    fake.write_text(json.dumps({**real, "dependencies": {**real["dependencies"], "not-bundled-dep": "1.0.0"}}), encoding="utf-8")
    monkeypatch.setattr(verify_builder_parity, "CORE_JS_PACKAGE", fake)
    assert verify_builder_parity.main() == 1
    err = capsys.readouterr().err
    assert "not-bundled-dep" in err and "macOS builder" in err and "Windows builder" in err and "win32-x64" in err
