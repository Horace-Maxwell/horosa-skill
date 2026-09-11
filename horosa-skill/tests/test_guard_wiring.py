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

import re
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent
SCRIPTS = PKG_ROOT / "scripts"

# Every place a guard may legitimately be wired into. A guard that runs *only* off-CI (needs the
# vendored tree or upstream checkout) belongs in preflight/release paths, not in ci.yml — but it has
# to be in one of these, or it is decoration.
RUNNERS = (
    REPO_ROOT / ".github/workflows/ci.yml",
    # v0.38.0 A5：托管发布流水线与真机矩阵也是守卫的运行者（verify_runtime_live / verify_runtime_python_lock --seed …）
    REPO_ROOT / ".github/workflows/release-runtime.yml",
    REPO_ROOT / ".github/workflows/runtime-matrix.yml",
    SCRIPTS / "publish_release.sh",
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


# --- v0.27.0+ 制度化批次：把口头注意点收进机器后，守住这些机制本身 ----------------------------


def _load_preflight():
    import importlib.util

    spec = importlib.util.spec_from_file_location("preflight_release", SCRIPTS / "preflight_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preflight_blocks_a_machine_generated_git_identity() -> None:
    """v0.27.0 现场：user.name/email 都没配，发布 commit 的作者串成了 `…@主机名.local`——
    GitHub 不归属到任何账号，而 git 只在 commit 那一刻才猜，全程无提示。tag 之前必须拦。"""
    preflight = _load_preflight()
    assert preflight.identity_problems("", "") != []
    assert preflight.identity_problems("Horace", "horacedong@Horaces-MacBook-Pro.local") != []
    assert preflight.identity_problems("Horace-Maxwell", "maxwelldhx@gmail.com") == []


def test_preflight_checks_for_stranded_origin_commits() -> None:
    """main 没配 upstream tracking 时 `git status` 永远不提示 behind——另一台机器的修复
    无声滞留了 8 天。preflight 现在 fetch 后断言 HEAD..origin/main 为空。"""
    source = (SCRIPTS / "preflight_release.py").read_text(encoding="utf-8")
    assert '"fetch", "--quiet", "origin", "main"' in source
    assert '"HEAD..origin/main"' in source


def test_live_gates_refuse_unnamed_default_port_stacks() -> None:
    """live 门禁只认显式点名的实例：默认端口上恰好在跑的栈来源不可知（可能根本不是本仓的树），
    env 未设时必须 skip 且**连 TCP 都不去碰它**——短路必须在 `and` 左侧。"""
    source = (PKG_ROOT / "tests/test_local_js_tools.py").read_text(encoding="utf-8")
    assert "_CHART_EXPLICIT and _server_up" in source, "chart 探针必须被显式性短路"
    assert "_JAVA_EXPLICIT and _server_up" in source, "java 探针必须被显式性短路"
    assert "start_vendored_instance.sh" in source, "skip 理由必须告诉人正确的起法"


def test_release_asset_contract_is_asserted_not_just_documented() -> None:
    """SBOM 生成器一直在仓里，却不在任何发布链上——v0.27.0 首发漏传，靠人对比上一版资产列表
    才发现。文档列的必要资产必须有 CI 断言 + 脚本化的生成步骤。"""
    workflow = (REPO_ROOT / ".github/workflows/release-completeness.yml").read_text(encoding="utf-8")
    assert "horosa-skill-sbom.json" in workflow, "completeness 必须断言 SBOM 资产在场"
    # v0.37.0：`.mcpb` 同理 —— server.json 的 mcpb package 直指这个资产 URL，缺了它注册表那条记录 404。
    assert ".mcpb" in workflow, "completeness 必须断言 MCPB 包在场"
    # v0.38.0 A6：mcpb 打包不可复现，server.json 的 fileSha256 必须对得上**发布上**那份（本次首发就漂了一次）
    assert "fileSha256" in workflow and "sha256sum" in workflow, "completeness 必须把 server.json 的 mcpb sha 与发布资产对齐"
    sync = (SCRIPTS / "sync_windows_release.py").read_text(encoding="utf-8")
    assert "has_mcpb" in sync, "双平台完整性判据必须把 .mcpb 算进去"
    publish = (SCRIPTS / "publish_release.sh").read_text(encoding="utf-8")
    for step in ("package_runtime_payload.sh", "generate_release_manifest.py", "generate_sbom.py",
                 "build_mcpb.sh", "SHA256SUMS.txt", "verify_runtime_release.py"):
        assert step in publish, f"darwin 半边发布脚本缺步骤：{step}（手打清单必漏）"
    # v0.37.0：mcpb 的 sha 必须在发布流程里回填进 server.json —— 客户端安装前会校验它，
    # 留空发出去 = 注册表那条记录装不上。
    assert "fileSha256" in publish, "publish 必须把 mcpb 的 sha 回填进 server.json"
    assert ".mcpb" in publish, "publish 的资产列表必须含 .mcpb"


def test_vendored_instance_scripts_keep_the_boot_and_kill_disciplines() -> None:
    """起法 = 三段 PYTHONPATH + 内嵌解释器 + failed=0 判据（少一样就是 v0.26.0 整轮误判的形状）；
    停法 = 只按 pidfile 的 PID（pkill 法则：按进程名杀会连别的实例一起带走）。"""
    start = (SCRIPTS / "start_vendored_instance.sh").read_text(encoding="utf-8")
    assert "flatlib-ctrad2" in start and "Horosa-Web/astropy" in start and "Horosa-Web/vendor" in start
    assert "runtime/mac/python/bin/python3" in start, "必须用内嵌解释器（裸 python 缺 9 个依赖）"
    assert "failed=0" in start, "就绪判据必须是 kentang prewarm failed=0"
    # v0.36.0 收尾：Java 必须按上游桌面模式起。裸 `-jar` 连 jar 内写死的 `mongodb.host` 超时 → 全 Java 族 9999，
    # 被当成「本机无 Mongo 的环境限制」写进文档整整十个版本。四样缺一样就退回那个状态。
    java_lines = [line for line in start.splitlines() if not line.lstrip().startswith("#")]
    java_code = "\n".join(java_lines)
    for flag in ("HOROSA_DESKTOP_MONGO_OPTIONAL=1", "HOROSA_MONGO_FALLBACK_DIR=", "needtranslog=false", "--mongodb.ip="):
        assert flag in java_code, f"Java 起法缺桌面模式开关 {flag}（裸 -jar = 全 Java 族 9999）"
    # v0.37.0：log4j 的 basedir 不改写，日志会落进 CWD 下一个字面量 `${env:HOME…}` 目录
    # （仓根 / horosa-skill/ / vendor/runtime-source/ 下各攒了一份）。`-Dbasedir=` 覆盖不了它。
    assert "log4j2.configurationFile" in java_code, "必须指一份改写过的 log4j 配置，否则日志落进字面量目录"
    assert "-jar" in java_code and "mongodb.host" not in java_code, "主机名必须被 --mongodb.ip 覆盖，不能把 mongodb.host 写进命令"
    stop = (SCRIPTS / "stop_vendored_instance.sh").read_text(encoding="utf-8")
    # 注释里**应该**提 pkill 法则（解释为什么不用它）；不许出现的是把它当命令用——只查非注释行。
    code_lines = [line for line in stop.splitlines() if not line.lstrip().startswith("#")]
    offenders = [line for line in code_lines if "pkill" in line or "pgrep" in line]
    assert offenders == [], f"停法只许按 PID，不许按进程名: {offenders}"
    assert "pidfile" in stop or ".pid" in stop


def test_provenance_contract_is_regenerable_from_a_checked_in_generator() -> None:
    """契约可再生 ⇒ 生成器必须入仓（scratchpad 里的一次性脚本会随会话蒸发，下次只能凭记忆重写）。"""
    generator = SCRIPTS / "gen_technique_provenance.py"
    assert generator.is_file()
    source = generator.read_text(encoding="utf-8")
    assert "parents[1]" in source and "/Users/" not in source, "生成器必须用仓内相对路径"


# --- v0.38.0：CI 闸（主干红了 19 个 commit 没人看） ----------------------------------------------


def _fake_gh(stdout: str, returncode: int = 0):
    class Done:
        def __init__(self):
            self.returncode, self.stdout, self.stderr = returncode, stdout, ""

    def runner(cmd, **kwargs):
        assert cmd[:3] == ["gh", "run", "list"] and "--commit" in cmd
        return Done()

    return runner


def test_ci_gate_blocks_red_pending_and_missing_runs_but_only_warns_without_gh() -> None:
    preflight = _load_preflight()
    sha = "0123456789abcdef"
    assert preflight.ci_gate_failures(sha, runner=_fake_gh('[{"conclusion":"success","status":"completed"}]')) == []
    red = preflight.ci_gate_failures(sha, runner=_fake_gh('[{"conclusion":"failure","status":"completed"}]'))
    assert red and "failure" in red[0]
    pending = preflight.ci_gate_failures(sha, runner=_fake_gh('[{"conclusion":"","status":"in_progress"}]'))
    assert pending and "in_progress" in pending[0]
    missing = preflight.ci_gate_failures(sha, runner=_fake_gh("[]"))
    assert missing and "没有 ci.yml 运行记录" in missing[0]

    def no_gh(cmd, **kwargs):
        raise FileNotFoundError("gh")

    assert preflight.ci_gate_failures(sha, runner=no_gh) == [], "gh 缺席只警告，不把离线维护机锁死"
    assert "ci_gate_failures(" in (SCRIPTS / "preflight_release.py").read_text(encoding="utf-8").split("def main")[1], "闸必须接进 main"
    publish = (SCRIPTS / "publish_release.sh").read_text(encoding="utf-8")
    assert "gh run list" in publish and "--commit" in publish, "publish_release.sh --draft 也要先查 CI 结论"


# --- v0.38.0：本机必须能跑 ci.yml 同款门禁（主干红了 19 个 commit 的另一半原因：本机只跑 pytest + docs-sync） ----


def test_run_ci_gates_mirrors_the_ci_test_job() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_ci_gates", SCRIPTS / "run_ci_gates.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    steps = module.ci_test_steps((REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    commands = [command for _name, command in steps]
    assert any("uv run pytest" in c for c in commands), "pytest 必须在镜像里"
    verify_in_ci = {c.split("scripts/")[1].split()[0] for c in commands if "scripts/verify_" in c}
    assert len(verify_in_ci) >= 12, verify_in_ci
    # every verify_* the CI test job runs as a single-line step is reachable locally through the mirror
    ci = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8").split("\n  windows-smoke:")[0]
    single_line = set(re.findall(r"run: uv run python scripts/(verify_[a-z_]+\.py)", ci))
    assert single_line <= verify_in_ci, single_line - verify_in_ci
    assert "run_ci_gates.py" in (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8"), "AGENTS §8 必须指明 push 前跑它"
