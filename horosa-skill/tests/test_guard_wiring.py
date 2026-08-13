"""Meta-guard: every `scripts/verify_*.py` must actually be invoked by something.

AGENTS §7 推论：「新增只挂 CI 的守卫时，先问这条路径 CI 走不走得到」。The dual failure is quieter and
has bitten twice — a guard exists, looks authoritative, and is wired into **nothing** that runs:

* `release.yml` (`runs-on: self-hosted`, zero runners registered) owned the two cross-tree gates for
  20 consecutive tags; not one step ever executed.
* `verify_export_contract_mirror.py` needs `vendor/runtime-source`, which is gitignored — so it cannot
  run on GitHub CI at all. It is only real because `preflight_release.py` calls it. Nothing asserted
  that until this test.

So: a guard is only a guard if some runner invokes it. This test is deliberately dumb — it greps the
runners for each script's filename — because anything cleverer would itself need a guard.
"""

from __future__ import annotations

from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent
SCRIPTS = PKG_ROOT / "scripts"

# Every place a guard may legitimately be wired into. A guard that runs *only* off-CI (needs the
# vendored tree or upstream checkout) belongs in preflight/release paths, not in ci.yml — but it has
# to be in one of these, or it is decoration.
RUNNERS = (
    REPO_ROOT / ".github/workflows/ci.yml",
    SCRIPTS / "preflight_release.py",
    SCRIPTS / "sync_windows_release.py",
    SCRIPTS / "build_runtime_release.sh",
    SCRIPTS / "build_runtime_release_windows.ps1",
    SCRIPTS / "scaffold_linux_runtime.py",
    SCRIPTS / "run_full_self_check.py",
)


def _runner_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in RUNNERS if path.is_file())


def test_every_verify_script_is_invoked_by_a_runner() -> None:
    text = _runner_text()
    orphans = sorted(p.name for p in SCRIPTS.glob("verify_*.py") if p.name not in text)
    assert orphans == [], (
        f"these guards are wired into nothing that runs: {orphans}. "
        "Add them to ci.yml (in-repo assertions) or preflight_release.py / a builder (off-CI ones). "
        "A guard nobody invokes reads as coverage while asserting nothing."
    )


def test_cross_tree_guards_are_wired_into_preflight_not_only_ci() -> None:
    """跨树闸只有维护机能做真——CI 上它们各自退到「仓内可判的那一半」，这是设计，不是覆盖。

    所以带跨树参数的调用必须出现在 preflight 里；否则「真闸」就只存在于口头。
    """
    preflight = (SCRIPTS / "preflight_release.py").read_text(encoding="utf-8")
    assert "--require-upstream" in preflight, "verify_upstream_sync 的跨树模式必须由 preflight 调用"
    assert '"--source", "upstream"' in preflight, "段级欠账棘轮的上游模式必须由 preflight 调用"
    assert "verify_export_contract_mirror.py" in preflight, (
        "mirror 守卫需要 vendor/runtime-source（gitignored），CI 上跑不了 —— 它只能靠 preflight 做真"
    )


def test_ci_does_not_pretend_to_run_the_cross_tree_comparison() -> None:
    """CI 里那两条调用**不带**跨树参数，是有意的；但注释必须说清楚，别让人以为 CI 覆盖了它。"""
    ci = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "--require-upstream" not in ci, (
        "CI 上没有上游 checkout，加了这个参数只会得到一条恒红的 step —— 真闸在 preflight_release.py"
    )
    assert "preflight_release.py" in ci, "CI 必须指明真正的跨树闸在哪，否则读者会以为这里就是全部"
