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


def test_kinastro_only_exclusions_do_not_apply_to_other_trees(tmp_path: Path) -> None:
    """排除口径按**树**限定，不按名字全局限定。

    `tools/ui/tests/docs/scripts/…` 是 sync 脚本**只**加在 kinastro 那一条 rsync 上的
    `--exclude`。曾经它们是全局排除的，等于「任何树下叫 tests/scripts 的目录都不比对」——
    astrostudy/websrv 下同名目录里的真漂移会整片溜过（当前上游恰好没有这种目录，所以是个
    还没爆的哑弹，不是没子弹）。
    """
    root = tmp_path / "astrostudy"
    for rel in ["geomancy/reading.py", "tests/test_geomancy.py", "scripts/gen.py", "docs/notes.md"]:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    found = set(guard._tree_files(root))
    assert found == {"geomancy/reading.py", "tests/test_geomancy.py", "scripts/gen.py", "docs/notes.md"}, (
        f"kinastro 专属排除泄漏到了别的树: {sorted(found)}"
    )


# --- defect 4: check 2b silently dropped every upstream-only ROOT-LEVEL file --------------------


def test_upstream_only_root_level_file_is_reported_in_a_wholesale_tree() -> None:
    """v0.26.1 之后的真实事故形状：6 个上游引擎模块对**所有**守卫隐形。

    旧实现 `vendored_tops = {n.split("/",1)[0] for n in vendored_files}` 对根级文件求出的 top 就是
    文件名自己，于是上游新增的根级文件永远匹配不上任何已 vendor 的顶层目录 → 整类丢弃；
    配套的「新增顶层目录」检查又要求 `"/" in n`，两头都漏。实测漏掉
    `cetian_yiyu{,_data,_texts}.py` + `wuzhao_{classics,duanci,leizhan}.py`，共 5,512 行。
    """
    missing, notices = guard.missing_upstream_files(
        upstream_names={"geomancy/reading.py", "cetian_yiyu.py", "wuzhao_classics.py"},
        vendored_names={"geomancy/reading.py"},
        copy_mode="whole",
        root_files=set(),
    )
    assert missing == ["cetian_yiyu.py", "wuzhao_classics.py"], "整棵 rsync 的树里，根级文件缺失就是缺口"
    assert notices == []


def test_per_dir_tree_only_fails_on_the_root_files_the_sync_script_names() -> None:
    """`Horosa-Web/vendor` 是逐引擎目录拷 + 点名两个根级文件——比对口径必须等于同步口径。

    点名内的缺失是硬缺口（v3.5.0 的 kin_year_domain.py：16 个引擎懒 import 它，漏拷 = 全线 500）；
    点名外的（README.md）只报 notice，否则守卫对着「本就故意没拷」的文件恒红。
    """
    missing, notices = guard.missing_upstream_files(
        upstream_names={"kinqimen/qimen.py", "kin_year_domain.py", "README.md"},
        vendored_names={"kinqimen/qimen.py"},
        copy_mode="per-dir",
        root_files={"kin_year_domain.py", "test_month_pillar_boundary.py"},
    )
    assert missing == ["kin_year_domain.py"]
    assert notices == ["README.md"], "清单外的根级新增要可见，但不阻断"


def test_files_inside_an_entirely_new_upstream_directory_are_not_listed_one_by_one() -> None:
    """整个新增的目录由 new_tops 报一行；逐文件展开会让一棵新引擎树刷出几百行。"""
    missing, notices = guard.missing_upstream_files(
        upstream_names={"newengine/a.py", "newengine/b.py", "kinqimen/qimen.py"},
        vendored_names={"kinqimen/qimen.py"},
        copy_mode="whole",
        root_files=set(),
    )
    assert missing == [] and notices == []


def test_sentinel_trees_declare_a_copy_mode_matching_the_sync_script() -> None:
    assert guard.SENTINEL_TREES["Horosa-Web/vendor"]["copy"] == "per-dir"
    assert guard.SENTINEL_TREES["Horosa-Web/astropy/astrostudy"]["copy"] == "whole"
    assert guard.SENTINEL_TREES["Horosa-Web/astropy/websrv"]["copy"] == "whole"
    sync = (Path(guard.__file__).resolve().parent / "sync_vendored_runtime_sources.sh").read_text(encoding="utf-8")
    for named in guard.SENTINEL_TREES["Horosa-Web/vendor"]["root_files"]:
        assert named in sync, f"{named} 声明为点名拷贝，但 sync 脚本里没有它 —— 两边口径必须锁步"


# --- defect 5: truncated FAIL output made a large drift look small ------------------------------


def test_drift_block_states_the_total_and_what_it_hid() -> None:
    text = guard._drift_block("things drifted", [f"f{i}.py" for i in range(56)], limit=15, full=False)
    assert "56 条" in text, "总数必须在标题里——56 条和 16 条不能长得一样"
    assert "另有 41 条未显示" in text
    assert guard._drift_block("x", ["a", "b"], limit=15, full=False).count("…") == 0


def test_drift_block_full_prints_everything() -> None:
    text = guard._drift_block("x", [f"f{i}" for i in range(56)], limit=15, full=True)
    assert "未显示" not in text and "f55" in text


# --- defect 6: the no-upstream path claimed currency it had not verified ------------------------


def test_no_upstream_path_never_claims_the_state_is_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """这条路径没做任何跨树比对，就不许说 current。

    旧文案是 "state current (mirror v50; last cross-tree check against upstream 3.7.3 …)"——
    本仓落后上游 4 个 release、少一个整技法时，它照样这么印。
    """
    record = tmp_path / "prov.json"
    record.write_text(
        json.dumps({"skill_mirrored_version": 50, "upstream_git_sha": "f8275b32d393", "upstream_app_version": "3.7.3"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(guard, "PROVENANCE", record)
    monkeypatch.setattr(guard, "_skill_mirror_version", lambda: 50)
    guard._report_state_currency()
    out = capsys.readouterr().out
    assert "state current" not in out
    assert "unverified" in out and "3.7.3" in out


# --- defect 7: `--require-upstream --write-state` 自锁 -------------------------------------------


def test_write_state_is_not_blocked_by_the_staleness_it_exists_to_fix() -> None:
    """staleness 的补救动作就是 --write-state，所以两者同时在场时它不能是 blocking failure。

    preflight_release.py 用的正是 `--require-upstream --write-state`。旧逻辑下，「刚重同步到新上游」
    这个**最常见**的发布前状态会自锁：check 4 先 raise，写记录的代码块在 raise 之后，于是那句
    「re-record with --write-state」在它自己的参数组合下永远做不到。
    """
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "if args.require_upstream and not args.write_state:" in source, (
        "staleness 在 --write-state 在场时必须降级为 notice"
    )
    # 但「红着写记录」仍必须不可能——写记录只发生在全部检查通过之后。
    raise_at = source.index('raise SystemExit("upstream-sync: FAIL\\n- "')
    write_at = source.index("if args.write_state:")
    assert write_at > raise_at


def test_preflight_uses_the_flag_combination_this_guard_supports() -> None:
    preflight = (_SCRIPT.parent / "preflight_release.py").read_text(encoding="utf-8")
    assert '"--require-upstream", "--write-state"' in preflight, (
        "preflight 的跨树闸必须同时带这两个参数：前者让它做真，后者留下 git 可见的核对证据"
    )


def test_skill_only_key_demoted_upstream_is_a_notice_not_a_retirement(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """v3.9.2 实况：上游把 `generic` 从 preset 键降为运行时兜底 context。它在 skill 侧本就是
    DIVERGENCE_WHITELIST 里的 skill-only 键——上游撤它不构成任何镜像内容的 retirement。
    不减这层时 lost 检查会自锁：红 → --write-state 拒写 → recorded 永含旧键 → 永远红。"""
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "_skill_only_keys()" in source and "whitelisted_lost" in source
    assert "generic" in guard._skill_only_keys(), "generic 必须在 skill-only 集里（mirror 白名单单源）"
