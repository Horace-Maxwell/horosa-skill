"""发布闸的纯函数半边（v0.38.1 A3 / A16）：

* `verify_runtime_release.check_entry_lengths` —— PAYLOAD_LONGEST_ENTRY_CHARS 双向锁（低估 / 高估都红）。
* `verify_wheel_contents.host_path_hits` —— wheel 里任何文本条目不得含真实主目录路径。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PKG_ROOT / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_gate_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


release = _load("verify_runtime_release")
wheel = _load("verify_wheel_contents")


def test_limit_is_read_from_the_manager_constant() -> None:
    from horosa_skill.runtime import manager

    assert release.payload_longest_entry_limit() == manager.PAYLOAD_LONGEST_ENTRY_CHARS == 180


def test_the_measured_v0_38_0_payload_passes() -> None:
    assert release.check_entry_lengths({"darwin-arm64": (179, "…streamlit_app.py"), "win32-x64": (172, "…")}, 180) == []


def test_a_longer_entry_than_the_constant_is_red() -> None:
    problems = release.check_entry_lengths({"win32-x64": (190, "deep/entry")}, 180)
    assert len(problems) == 1 and "under-estimate" in problems[0]


def test_an_over_estimating_constant_is_red() -> None:
    problems = release.check_entry_lengths({"darwin-arm64": (150, "x")}, 180)
    assert len(problems) == 1 and "over-estimates" in problems[0]


def test_the_old_constant_200_would_have_been_red() -> None:
    """负向对照：v0.38.0 的 200 对实测 179 高估 21 → 默认根在用户名 ≥ 6 字符时被报 headroom −1。"""
    assert release.check_entry_lengths({"darwin-arm64": (179, "x")}, 200)


def test_windows_alone_checks_only_the_upper_bound() -> None:
    assert release.check_entry_lengths({"win32-x64": (150, "x")}, 180) == []


def test_longest_entry_helper() -> None:
    assert release.longest_entry({"a", "abc", "ab"}) == (3, "abc")
    assert release.longest_entry(set()) == (0, "")


# ---------------------------------------------------------------- wheel host paths


def test_real_home_paths_are_flagged() -> None:
    hits = wheel.host_path_hits({
        "horosa_skill/knowledge/data/astro.json": b'{"source": "/Users/somebody/Desktop/Horosa-Web/x.vue"}',
        "horosa_skill/a.py": "x = r'C:\\Users\\Somebody\\AppData'".encode("utf-8"),
        "horosa_skill/b.md": b"see /home/somebody/work/",
    })
    assert len(hits) == 3 and all("host home path" in hit for hit in hits)


def test_placeholder_users_are_allowed() -> None:
    assert wheel.host_path_hits({
        "a.py": b"# `/Users/x/My Projects` and /Users/<you>/code and C:\\Users\\<user>\\x",
        "b.py": "# C:\\Users\\张三\\AppData".encode("utf-8"),
        "c.md": b"/home/runner/work/horosa-skill and ${HOME}/.horosa and /Users/$USER/x",
    }) == []


def test_binary_entries_are_skipped() -> None:
    assert wheel.host_path_hits({"lib.so": b"/Users/somebody/build/"}) == []


def test_shipped_sources_and_knowledge_packs_carry_no_host_paths() -> None:
    src = PKG_ROOT / "src" / "horosa_skill"
    entries = {str(p.relative_to(src.parent)): p.read_bytes() for p in src.rglob("*") if p.is_file() and p.suffix in {".py", ".json", ".md", ".txt", ".ps1"}}
    assert wheel.host_path_hits(entries) == []
