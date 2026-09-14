"""托管发布流水线与真机矩阵的形状契约（v0.38.0 A5）。

**为什么旧检查抓不到**：`release.yml` 曾挂在 `push: tags` 上而 self-hosted runner 数为 0——20 次 tag 触发排队 24 h 后被取消，
零 step 执行，runs 页面却像有覆盖；`publish_darwin_release.sh --publish` 会先发一个 darwin-only 清单的公开 release，
「缺半」窗口由人肉补传关闭。本文件锁：流水线只手动触发、清单只上 draft、publish 必 needs matrix 且先过 [OK]、
矩阵永不挂 push/PR、三 lane 都跑 verify_runtime_live、ARM lane 的阻断性由输入控制、旧 release.yml 不复活。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
RELEASE = (WORKFLOWS / "release-runtime.yml").read_text(encoding="utf-8")
MATRIX = (WORKFLOWS / "runtime-matrix.yml").read_text(encoding="utf-8")
PUBLISH = (REPO_ROOT / "horosa-skill" / "scripts" / "publish_release.sh").read_text(encoding="utf-8")


def _job(text: str, name: str) -> str:
    match = re.search(rf"^  {name}:\n(.*?)(?=^  [a-z_-]+:\n|\Z)", text, re.S | re.M)
    assert match, f"job {name} missing"
    return match.group(1)


def test_release_pipeline_is_dispatch_only() -> None:
    on_block = RELEASE.split("\njobs:", 1)[0]
    assert "workflow_dispatch:" in on_block
    for trigger in ("push:", "pull_request:", "tags:", "schedule:", "release:"):
        assert trigger not in on_block, f"release-runtime.yml must not trigger on {trigger}"
    assert "github.repository_owner == 'Horace-Maxwell'" in _job(RELEASE, "resolve")


def test_release_pipeline_never_creates_a_public_release_itself() -> None:
    assert "gh release create" not in RELEASE, "only publish_release.sh creates the (draft) release"
    publish = _job(RELEASE, "publish")
    assert "needs: [resolve, assemble, matrix]" in publish
    assert "sync_windows_release.py --check --tag" in publish and "--draft" in publish
    assert "--draft=false --latest" in publish
    assert "!inputs.dry_run" in publish and "inputs.publish" in publish
    assert publish.index("sync_windows_release.py --check --tag") < publish.index("--draft=false --latest"), "[OK] before flipping"
    # release events raised with GITHUB_TOKEN start no workflows: the guard must be dispatched by the publish job itself
    assert "gh workflow run release-completeness.yml" in publish
    assert publish.index("--draft=false --latest") < publish.index("gh workflow run release-completeness.yml")
    # after flipping, the public latest is checked again; then (v0.38.1 R1/R5) the release-mode matrix is dispatched —
    # a real https download of the public assets — so the check is no longer the last step, but it still follows the flip
    recheck = publish.rindex("sync_windows_release.py --check\n")
    assert publish.index("--draft=false --latest") < recheck < publish.index("gh workflow run runtime-matrix.yml")


def test_windows_half_is_derived_from_the_seed_and_verified_before_upload() -> None:
    build = _job(RELEASE, "build-windows")
    assert "build_runtime_release_windows.py --seed" in build
    assert "runs-on: windows-latest" in build
    assemble = _job(RELEASE, "assemble")
    for needle in (
        "verify_runtime_python_lock.py --seed",
        "generate_release_manifest.py",
        "--url-base",
        "verify_runtime_release.py",
        "--expect-platforms darwin-arm64,win32-x64",
        "SHA256SUMS.txt",
        "generate_sbom.py",
        "attest-build-provenance",
    ):
        assert needle in assemble, needle
    upload = assemble[assemble.index("gh release upload"):]
    assert "runtime-manifest.json" in upload, "the dual manifest reaches the draft only from assemble"
    assert assemble.index("verify_runtime_release.py") < assemble.index("gh release upload"), "verify before upload"
    assert "if: ${{ !inputs.dry_run }}" in assemble, "dry runs never upload"


def test_matrix_is_called_between_assemble_and_publish() -> None:
    matrix = _job(RELEASE, "matrix")
    assert "uses: ./.github/workflows/runtime-matrix.yml" in matrix
    assert "source: artifact" in matrix and "needs: [resolve, assemble]" in matrix


def test_runtime_matrix_never_runs_per_push_and_covers_three_real_machines() -> None:
    on_block = MATRIX.split("\njobs:", 1)[0]
    assert "workflow_call:" in on_block and "workflow_dispatch:" in on_block and "schedule:" in on_block
    for trigger in ("push:", "pull_request:"):
        assert trigger not in on_block, f"runtime-matrix.yml must not trigger on {trigger}"
    for runner in ("macos-latest", "windows-latest", "windows-11-arm"):
        assert f"runner: {runner}" in MATRIX, runner
    assert "fail-fast: false" in MATRIX
    assert MATRIX.count("verify_runtime_live.py") >= 2, "both the POSIX and the Windows lane steps must run the verifier"
    assert "--expect-payload-platform" in MATRIX and "--expect-emulated" in MATRIX


def test_arm_lane_blocking_is_an_input_not_a_hardcode() -> None:
    assert "continue-on-error: ${{ matrix.platform == 'win32-arm64' && inputs.arm_nonblocking == true }}" in MATRIX
    # blocking by default since dry run #4 went green on windows-11-arm (2026-09-11)
    assert MATRIX.count("arm_nonblocking:\n        type: boolean\n        default: false") == 2
    assert "default: true" not in RELEASE.split("arm_nonblocking:", 1)[1][:200]
    assert "expect_payload: win32-x64" in MATRIX.split("runner: windows-11-arm", 1)[1][:600], "the ARM lane installs the x64 payload"


def test_matrix_uploads_evidence_even_on_failure() -> None:
    tail = MATRIX[MATRIX.index("Upload lane evidence"):]
    assert "if: always()" in tail and "horosa 测试 lane/logs/**" in tail and "lane-report.json" in MATRIX
    # one artifact root only (Windows upload-artifact refused runner.temp + `~`); the verifier copies launcher.log into logs/
    assert "~/" not in tail
    verifier = (REPO_ROOT / "horosa-skill" / "scripts" / "verify_runtime_live.py").read_text(encoding="utf-8")
    assert "launcher.log" in verifier and "_collect_service_logs" in verifier


def test_publish_script_only_ever_makes_drafts() -> None:
    creates = [line for line in PUBLISH.splitlines() if "gh release create" in line and not line.lstrip().startswith("#")]
    assert creates and all("--draft" in line for line in creates), creates
    assert "--publish" not in [a for line in PUBLISH.splitlines() if not line.lstrip().startswith("#") for a in line.split()], (
        "the darwin-only public publish path is gone"
    )
    assert "runtime-manifest.json" not in PUBLISH.split("=== [8/8] draft release", 1)[1], "the draft upload never carries the manifest"
    assert "gh workflow run release-runtime.yml" in PUBLISH
    assert "gh run watch" in PUBLISH


def test_the_never_run_self_hosted_release_workflow_is_gone() -> None:
    assert not (WORKFLOWS / "release.yml").exists(), "release.yml (self-hosted, 20 cancelled tag runs) must not come back"
    assert not (REPO_ROOT / "horosa-skill" / "scripts" / "publish_darwin_release.sh").exists()


# ---------------------------------------------------------------- v0.38.1 B3：矩阵与 CI 覆盖

COMPLETENESS = (WORKFLOWS / "release-completeness.yml").read_text(encoding="utf-8")
CI = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")


def test_release_and_schedule_lanes_install_through_the_public_manifest_url() -> None:
    """R1：release / dispatch / schedule 模式必须走公开清单 URL（真下载）。旧写法两种模式都 `--assets-dir` → file://，
    2026-09-14 的 schedule 跑的 lane-report 里 install.source 仍是 file://…lane-manifest.json —— 从没有 lane 下载过。"""
    source = MATRIX[MATRIX.index("Resolve the install source"):MATRIX.index("Live verification (POSIX)")]
    assert "mode=manifest-url" in source and "releases/download/${TAG}/runtime-manifest.json" in source
    assert "gh release download" not in source, "release/schedule lanes must not pre-download and localise to file://"
    assert "mode=assets-dir" in source, "artifact mode still installs the pipeline's assembled set"
    assert '"--${{ steps.source.outputs.mode }}" "${{ steps.source.outputs.value }}"' in MATRIX
    assert '--assets-dir "' not in MATRIX, "a hard-coded --assets-dir would silently skip the download path again"
    verifier = (REPO_ROOT / "horosa-skill" / "scripts" / "verify_runtime_live.py").read_text(encoding="utf-8")
    assert "download_problems(" in verifier and "installed_archive_sha256" in verifier


def test_matrix_cron_is_off_the_hour_and_the_completeness_guard_kicks_it() -> None:
    cron = re.search(r'cron: "(\d+) (\d+) \* \* 1"', MATRIX)
    assert cron, "weekly cron missing"
    assert cron.group(1) != "0", "on-the-hour slots are delayed/dropped by GitHub (the 03:00 slot fired 5.5 h late on 2026-09-14)"
    kick = _job(COMPLETENESS, "weekly-matrix-kick")
    assert "actions: write" in kick and "gh workflow run runtime-matrix.yml" in kick
    assert "github.event_name == 'schedule'" in kick and "--created" in kick


def test_matrix_work_dir_carries_a_space_and_cjk() -> None:
    """R10：带空格 + 中文的工作目录在三台真机上过一遍（A1 编码 / A4 引号）。"""
    assert MATRIX.count("horosa 测试 lane") >= 5
    assert "horosa-lane" not in MATRIX.split("Resolve the install source", 1)[1]


def test_publish_requires_the_matrix_and_the_same_bytes() -> None:
    """R5：publish=true 没有 run_matrix=true 直接 fail；publish job 不再接受 skipped 的 matrix；翻公开前比对 lane 装的 sha 与 draft 资产。"""
    resolve = _job(RELEASE, "resolve")
    assert "publish=true requires run_matrix=true" in resolve
    publish = _job(RELEASE, "publish")
    condition = next(line for line in publish.splitlines() if line.strip().startswith("if:"))
    assert "needs.matrix.result == 'success'" in condition and "skipped" not in condition
    assert "verify_matrix_digests.py" in publish and "pattern: runtime-matrix-*" in publish and ".digest" in publish
    assert publish.index("verify_matrix_digests.py") < publish.index("--draft=false --latest"), "digest gate before the flip"
    assert "gh workflow run runtime-matrix.yml" in publish
    assert publish.index("--draft=false --latest") < publish.index("gh workflow run runtime-matrix.yml"), "release-mode matrix after the flip"


def test_completeness_checks_digests_min_os_and_the_mcpb_bundle() -> None:
    check = _job(COMPLETENESS, "check-latest-release-complete")
    assert "verify_mcpb_manifest.py --bundle" in check, "R8: unpack the published bundle"
    assert ".digest" in check and "SHA256SUMS.txt says" in check, "R15: SHA256SUMS lines vs GitHub's asset digests"
    assert "min_os" in check and "(0, 38, 1)" in check, "R16: min_os asserted from 0.38.1 on"


def test_ci_wheel_path_runs_a_real_stdio_probe_on_both_os() -> None:
    """R9/R18：wheel 装出来的包真起一次 stdio（116），Windows 上同样；全量面在 Windows 真机上也起一次。"""
    test_job = _job(CI, "test")
    assert "--no-write --no-probe-network --skip-install --no-cache-wheel" in test_job and 'probe["tools"] == 116' in test_job
    assert "--dry-run --no-probe-network" not in test_job, "dry-run proves nothing about the wheel's data files"
    smoke = _job(CI, "windows-smoke")
    assert "--surface full" in smoke and "-ne 116" in smoke
    assert "uvx --from $whl horosa-skill setup" in smoke and "uv build --wheel" in smoke
