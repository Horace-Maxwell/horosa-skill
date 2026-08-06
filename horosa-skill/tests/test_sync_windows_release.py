from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_windows_release.py"
SPEC = importlib.util.spec_from_file_location("sync_windows_release", SCRIPT_PATH)
assert SPEC and SPEC.loader
sync_windows_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_windows_release)


def _recorded_runner(calls: list[list[str]], *, fail_on: str | None = None):
    def fake_run(cmd: list[str], *, cwd: Path | None = None, capture: bool = False):
        calls.append(cmd)
        if fail_on and any(fail_on in part for part in cmd):
            raise subprocess.CalledProcessError(1, cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    return fake_run


def test_preflight_runs_both_vendor_freshness_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    # Both guards are required: the required-paths one alone passes on a tree that is genuinely
    # behind, because upstream adds export keys without bumping AI_EXPORT_SETTINGS_VERSION.
    calls: list[list[str]] = []
    monkeypatch.setattr(sync_windows_release, "run", _recorded_runner(calls))

    sync_windows_release.preflight_vendor_sources()

    flat = [" ".join(cmd) for cmd in calls]
    assert any("verify_vendor_runtime_sources.py" in cmd for cmd in flat)
    assert any("verify_export_contract_mirror.py" in cmd for cmd in flat)


@pytest.mark.parametrize(
    "failing_guard",
    ["verify_vendor_runtime_sources.py", "verify_export_contract_mirror.py"],
)
def test_preflight_refuses_to_build_on_stale_vendor_tree(
    monkeypatch: pytest.MonkeyPatch, failing_guard: str
) -> None:
    # A red guard must stop the build outright — building off a stale vendored tree silently ships
    # engines that lag the release's upstream sync (the payload is built from that tree, and nothing
    # in a `git pull` refreshes it because it is gitignored).
    calls: list[list[str]] = []
    monkeypatch.setattr(sync_windows_release, "run", _recorded_runner(calls, fail_on=failing_guard))

    with pytest.raises(SystemExit) as excinfo:
        sync_windows_release.preflight_vendor_sources()

    assert failing_guard in str(excinfo.value)
    assert "stale Windows payload" in str(excinfo.value)


def test_build_and_verify_preflights_before_invoking_the_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ordering matters: the gate is worthless if the builder already ran.
    order: list[str] = []
    monkeypatch.setattr(
        sync_windows_release,
        "preflight_vendor_sources",
        lambda: order.append("preflight"),
    )

    def fake_run(cmd: list[str], *, cwd: Path | None = None, capture: bool = False):
        if any("build_runtime_release_windows.py" in part for part in cmd):
            order.append("build")
            raise SystemExit("stop after the builder call — ordering is all this test needs")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(sync_windows_release, "run", fake_run)

    with pytest.raises(SystemExit):
        sync_windows_release.build_and_verify(
            {
                "version": "9.9.9",
                "tag": "v9.9.9",
                "win_zip": "horosa-runtime-win32-x64-v9.9.9.zip",
                "darwin_tar": "horosa-runtime-darwin-arm64-v9.9.9.tar.gz",
            }
        )

    assert order == ["preflight", "build"]
