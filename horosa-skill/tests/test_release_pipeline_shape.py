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
    # after flipping, the public latest is checked again
    assert publish.rstrip().endswith("sync_windows_release.py --check")


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
    assert "if: always()" in tail and "horosa-lane/logs/**" in tail and "lane-report.json" in MATRIX
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
