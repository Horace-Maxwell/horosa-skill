"""Unit tests for the upstream-sync guard (scripts/verify_upstream_sync.py).

Two defects this pins, both of which shipped in v0.25.0:

1. **Version equality cannot detect a new upstream technique.** Upstream adds technique keys without
   moving either version gate ("新技法键只加键、两把版本闸恒不动", upstream aiExport.js:306). `tianxing`
   (v3.7.0) and `qimenzeri` (v3.7.1) both arrived under an unchanged `AI_EXPORT_SETTINGS_VERSION = 50`,
   so check 1 stayed green while a whole technique was missing. Only the preset-key-set diff sees it.
2. **`--write-state` wrote provenance before the failure raise.** A record claiming "最近一次核对过的
   上游状态" written by a red run launders a failure into a durable claim of currency — strictly worse
   than no record at all.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_upstream_sync.py"
_spec = importlib.util.spec_from_file_location("verify_upstream_sync", _SCRIPT)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


# --- defect 1: new-key arrival under an unchanged version gate ---------------------------------


def test_new_upstream_key_is_detected_even_when_version_is_identical() -> None:
    """The exact v3.7.x scenario: same version number, extra key."""
    before = {"qimen", "bazi", "horary"}
    after = before | {"tianxing", "qimenzeri"}
    gained, lost = guard.diff_preset_keys(after, before)
    assert gained == ["qimenzeri", "tianxing"]
    assert lost == []


def test_removed_upstream_key_is_reported() -> None:
    gained, lost = guard.diff_preset_keys({"qimen"}, {"qimen", "retired"})
    assert gained == []
    assert lost == ["retired"]


def test_identical_key_sets_produce_no_signal() -> None:
    assert guard.diff_preset_keys({"a", "b"}, {"b", "a"}) == ([], [])


def test_version_equality_alone_would_have_missed_it() -> None:
    """Documents *why* check 1b exists: both texts declare v50, only one has the key."""
    from _upstream_preset import parse_preset_sections, read_settings_version  # noqa: PLC0415

    old = "const AI_EXPORT_SETTINGS_VERSION = 50;\nconst AI_EXPORT_PRESET_SECTIONS = {\n\tqimen: ['a'],\n};\n"
    new = old + "AI_EXPORT_PRESET_SECTIONS.qimenzeri = [...AI_EXPORT_PRESET_SECTIONS.qimen, 'b'];\n"
    assert read_settings_version(old) == read_settings_version(new) == 50, "version gate is blind by design"
    gained, _ = guard.diff_preset_keys(set(parse_preset_sections(new)), set(parse_preset_sections(old)))
    assert gained == ["qimenzeri"], "the key-set diff is the only thing that sees it"


# --- defect 2: provenance must never be written by a failing run --------------------------------


def test_write_state_block_runs_after_the_failure_raise() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    raise_at = source.index('raise SystemExit("upstream-sync: FAIL\\n- "')
    write_at = source.index("if args.write_state:")
    assert write_at > raise_at, (
        "--write-state must be gated behind the failure raise; writing provenance on a red run turns a "
        "failure into a durable claim of currency (v0.25.0 shipped exactly that)"
    )


# --- provenance shape ---------------------------------------------------------------------------


def test_provenance_file_is_present_and_well_formed() -> None:
    data = json.loads(guard.PROVENANCE.read_text(encoding="utf-8"))
    for field in ("upstream_git_sha", "upstream_app_version", "aiexport_settings_version", "upstream_preset_keys"):
        assert field in data, f"provenance must carry {field} — 'which upstream is this?' has to be machine-answerable"
    assert isinstance(data["upstream_preset_keys"], list) and data["upstream_preset_keys"], "key set must be recorded"
    assert data["upstream_preset_keys"] == sorted(data["upstream_preset_keys"]), "keys are stored sorted for stable diffs"


def test_retired_sync_state_file_is_gone() -> None:
    legacy = guard.PROVENANCE.parent / "vendor_sync_state.json"
    assert not legacy.exists(), "vendor_sync_state.json is superseded by upstream_provenance.json"


def test_load_provenance_tolerates_missing_and_malformed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guard, "PROVENANCE", tmp_path / "nope.json")
    assert guard.load_provenance() == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(guard, "PROVENANCE", bad)
    assert guard.load_provenance() == {}, "a corrupt record must degrade to 'no record', never crash the guard"


# --- defect 3: point sentinels can never cover whole engine trees ------------------------------


def test_sentinel_trees_cover_the_ken_engine_directory() -> None:
    """v0.26.0: `kintaiyi/jieqi.py` 的全年份域修复卡在 vendored 树里没人发现——7 个哨兵一个都不在
    ken 引擎目录下，而 verify_vendor_runtime_sources 只查 REQUIRED_PATHS 是否**存在**。"""
    assert "Horosa-Web/vendor" in guard.SENTINEL_TREES, "ken 引擎树必须整棵比对，不能只靠点哨兵"
    # 记录「为什么需要子树比对」：点哨兵里唯一在 vendor/ 下的是根级共享件 kin_year_domain.py，
    # **引擎目录内部**（kintaiyi/… 等）一个都没有 —— jieqi.py 正是这么漏掉的。
    inside_engine_dirs = [
        s for s in guard.SENTINELS
        if s.startswith("Horosa-Web/vendor/") and s.count("/") > 2
    ]
    assert inside_engine_dirs == [], f"若已给引擎目录加点哨兵，请更新本测试的叙述: {inside_engine_dirs}"


def test_tree_file_walk_honours_the_sync_scripts_exclusions(tmp_path: Path) -> None:
    """比对口径必须等于同步口径，否则守卫会对着「本就故意没拷」的文件恒红。"""
    root = tmp_path / "t"
    (root / "kinastro" / "astro").mkdir(parents=True)
    (root / "kinastro" / "astro" / "engine.py").write_text("x", encoding="utf-8")
    for junk in [
        root / "kinastro" / "tools" / "cities.py",      # sync 脚本裁掉（~26MB 地理编码库）
        root / "kinastro" / "tests" / "test_x.py",
        root / "kinastro" / ".github" / "workflows" / "ci.yml",
        root / "kinastro" / "astro" / "__pycache__" / "engine.cpython-312.pyc",
    ]:
        junk.parent.mkdir(parents=True, exist_ok=True)
        junk.write_text("x", encoding="utf-8")
    (root / "kinastro" / "astro" / "stale.pyc").write_text("x", encoding="utf-8")

    found = set(guard._tree_files(root))
    assert found == {"kinastro/astro/engine.py"}, f"排除口径与 sync 脚本不一致: {sorted(found)}"


def test_tree_walk_returns_empty_for_a_missing_root(tmp_path: Path) -> None:
    assert guard._tree_files(tmp_path / "nope") == {}
