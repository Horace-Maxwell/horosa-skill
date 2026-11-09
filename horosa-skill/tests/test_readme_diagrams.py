"""README diagrams are build output (`scripts/gen_readme_diagrams.py`): the numbers they draw must follow the registry.

The guard is `verify_docs_sync.check_readme_diagrams_generated`. These tests prove it can fail: a hand-edited SVG,
a stray SVG nobody renders, a README table that stops partitioning the registry, and a README that drops a figure.
"""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent

_spec = importlib.util.spec_from_file_location("gen_readme_diagrams", PKG_ROOT / "scripts" / "gen_readme_diagrams.py")
gen = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(gen)


@pytest.fixture(scope="module")
def rendered() -> dict[str, str]:
    return gen.render_all()


def _fake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rendered: dict[str, str]) -> Path:
    for rel, body in rendered.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(body, encoding="utf-8")
    monkeypatch.setattr(gen, "ROOT", tmp_path)
    monkeypatch.setattr(gen, "OUT", tmp_path / gen.OUT_REL)
    return tmp_path


def test_committed_diagrams_match_the_render(rendered: dict[str, str]) -> None:
    assert gen.drift(rendered) == []
    assert len(rendered) == len(gen.FIGURES) * len(gen.LANGS) * len(gen.THEME_NAMES)


def test_render_is_byte_stable() -> None:
    assert gen.render_all() == gen.render_all()


def test_hand_edited_svg_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rendered: dict[str, str]) -> None:
    root = _fake_root(tmp_path, monkeypatch, rendered)
    target = f"{gen.OUT_REL}/hero-zh-light.svg"
    (root / target).write_text(rendered[target].replace("114", "110"), encoding="utf-8")
    assert gen.drift(rendered) == [target]


def test_stray_svg_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rendered: dict[str, str]) -> None:
    root = _fake_root(tmp_path, monkeypatch, rendered)
    (root / gen.OUT_REL / "old-banner.svg").write_text("<svg/>", encoding="utf-8")
    assert gen.drift(rendered) == [f"{gen.OUT_REL}/old-banner.svg"]


def test_family_counts_partition_the_registry() -> None:
    facts = gen.collect_facts()
    assert sum(facts["families"].values()) == facts["tools"]


def test_readme_table_missing_a_tool_fails_the_render(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    row = next(line for line in readme.splitlines() if line.startswith("| `babylon`"))
    (tmp_path / "README.md").write_text(readme.replace(row + "\n", ""), encoding="utf-8")
    monkeypatch.setattr(gen, "ROOT", tmp_path)
    from horosa_skill.engine.registry import TOOL_DEFINITIONS

    with pytest.raises(SystemExit, match="babylon"):
        gen.readme_family_counts(set(TOOL_DEFINITIONS))


def test_docs_sync_flags_a_readme_that_drops_a_figure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = importlib.util.spec_from_file_location("verify_docs_sync", PKG_ROOT / "scripts" / "verify_docs_sync.py")
    ds = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(ds)
    for name in ("README.md", "README_EN.md"):
        shutil.copy(REPO_ROOT / name, tmp_path / name)
    zh = (tmp_path / "README.md").read_text(encoding="utf-8")
    (tmp_path / "README.md").write_text(zh.replace("./docs/assets/readme/repo-zh-dark.svg", "./docs/assets/readme/gone.svg"), encoding="utf-8")
    monkeypatch.setattr(ds, "ROOT", tmp_path)
    ds.ERRORS.clear()
    ds.check_readme_diagrams_generated()
    assert any("repo-zh-dark.svg" in e for e in ds.ERRORS), ds.ERRORS
    assert not any("README_EN.md" in e for e in ds.ERRORS), ds.ERRORS
