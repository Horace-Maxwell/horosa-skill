"""真 .mcpb 的内容契约（v0.38.1 R8）：`mcpb validate` 只看 manifest，不看包里有什么。"""
from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("verify_mcpb_manifest", PKG_ROOT / "scripts" / "verify_mcpb_manifest.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _bundle(path: Path, entries: list[str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for entry in entries:
            archive.writestr(entry, "x")
    return path


def _good_entries() -> list[str]:
    entries = ["manifest.json"]
    for required in mod.REQUIRED_IN_BUNDLE:
        entry = required if "." in Path(required).name else required.rstrip("/") + "/file.txt"
        if entry not in entries:
            entries.append(entry)
    return entries


def test_a_complete_bundle_passes(tmp_path: Path) -> None:
    assert mod.bundle_archive_errors(_bundle(tmp_path / "ok.mcpb", _good_entries())) == []


def test_a_bundle_missing_the_windows_templates_is_red(tmp_path: Path) -> None:
    """负向对照：排掉 scripts/runtime_templates/windows → 宿主 `uv run --directory <bundle>` 构建失败（装得上、一跑就炸）。"""
    entries = [e for e in _good_entries() if not e.startswith("scripts/runtime_templates/windows")]
    problems = mod.bundle_archive_errors(_bundle(tmp_path / "bad.mcpb", entries))
    assert any("scripts/runtime_templates/windows" in p for p in problems), problems


def test_a_bundle_carrying_vendor_or_tests_is_red(tmp_path: Path) -> None:
    problems = mod.bundle_archive_errors(_bundle(tmp_path / "fat.mcpb", [*_good_entries(), "vendor/runtime-source/x", "tests/test_x.py"]))
    assert any("vendor/" in p for p in problems) and any("tests/" in p for p in problems)


def test_not_a_zip_and_missing_file_are_red(tmp_path: Path) -> None:
    junk = tmp_path / "junk.mcpb"
    junk.write_bytes(b"not a zip")
    assert any("not a zip" in p for p in mod.bundle_archive_errors(junk))
    assert any("not found" in p for p in mod.bundle_archive_errors(tmp_path / "missing.mcpb"))


def test_packer_version_is_pinned_and_shared_with_the_build_script() -> None:
    build = (PKG_ROOT / "scripts" / "build_mcpb.sh").read_text(encoding="utf-8")
    assert mod.MCPB_PACKAGE == "@anthropic-ai/mcpb@2.1.2"
    assert build.count(mod.MCPB_PACKAGE) == 2 and "@anthropic-ai/mcpb@2 " not in build
    assert 'verify_mcpb_manifest.py" --bundle' in build, "build_mcpb.sh must verify the bundle it just packed"
