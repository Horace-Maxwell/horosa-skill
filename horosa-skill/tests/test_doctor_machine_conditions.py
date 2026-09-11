"""doctor 的机器条件诊断层（v0.38.0 B6）：码表锁步、--explain、零外网、长路径、磁盘、quarantine、仿真进程、下载旋钮。

**为什么旧检查抓不到**：doctor 的 issue 码只是字符串，没有任何一处保证每个码都有人话；`_guard_windows_long_paths`
与 `_require_install_disk_space` 从来没有测试（前者只在 Windows 真机上、后者只在磁盘真满时才走到）；
macOS quarantine 从没检测过；「doctor 不上外网」只是口头承诺。
"""

from __future__ import annotations

import inspect
import json
import re
import zipfile
from collections import namedtuple
from pathlib import Path

import pytest
from typer.testing import CliRunner

from horosa_skill.config import Settings
from horosa_skill.errors import RuntimeInstallError
from horosa_skill.runtime import manager as manager_module
from horosa_skill.runtime.manager import DOCTOR_ISSUE_CODES, HorosaRuntimeManager
from horosa_skill.surfaces import cli as cli_module
from horosa_skill.surfaces.cli import app

from test_runtime_manager import create_runtime_archive
from test_setup_command import _fake_archive  # explicit mac runtime paths in the manifest → doctor finds them on any host OS

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOROSA_LOCAL_BACKEND_PORT", "39987")
    monkeypatch.setenv("HOROSA_LOCAL_CHART_PORT", "39888")
    for name in ("HOROSA_SERVER_ROOT", "HOROSA_CHART_SERVER_ROOT", "HOROSA_RUNTIME_MIRROR", "HOROSA_PORTS",
                 "HOROSA_RUNTIME_DOWNLOAD_TIMEOUT_SECONDS", "HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS"):
        monkeypatch.delenv(name, raising=False)


def _settings(tmp_path: Path) -> Settings:
    return Settings(runtime_root=tmp_path / "runtime-root", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs",
                    runtime_platform="darwin-arm64")


# ---------------------------------------------------------------- advice lockstep


def test_every_doctor_code_has_advice() -> None:
    for code in (*DOCTOR_ISSUE_CODES, *cli_module._DOCTOR_WARNING_CODES):
        key = code.replace("*", "x")
        advice = cli_module._advice_for(key)
        assert "doctor 报了" not in advice["user_summary"], f"{code} 没有人话"
        assert advice["next_action"]


def test_issue_codes_in_source_are_all_registered() -> None:
    """新加一个 issues.append("…") 而不登记 DOCTOR_ISSUE_CODES → 红。"""
    source = inspect.getsource(HorosaRuntimeManager.doctor)
    literal = set(re.findall(r'issues\.append\("([^"]+)"\)', source))
    prefixed = {m + "*" for m in re.findall(r'issues\.append\(f"([a-z_]+:)\{', source)}
    registered = set(DOCTOR_ISSUE_CODES)
    assert literal <= registered, literal - registered
    assert prefixed <= registered, prefixed - registered
    # manifest / state validation codes come from load_*(strict=True)
    assert {"runtime.manifest_invalid", "runtime.state_invalid"} <= registered


def test_warning_codes_in_source_are_all_registered() -> None:
    source = inspect.getsource(cli_module._listener_scope_warnings) + inspect.getsource(cli_module._arch_warnings)
    literal = set(re.findall(r'"code": "([^"]+)"', source))
    assert literal == set(cli_module._DOCTOR_WARNING_CODES)


def test_unknown_code_gets_a_generic_but_actionable_line() -> None:
    advice = cli_module._advice_for("something:new")
    assert "--explain" in advice["next_action"]


# ---------------------------------------------------------------- --explain / --probe-network


def test_explain_writes_prose_to_stderr_and_keeps_stdout_json() -> None:
    result = runner.invoke(app, ["doctor", "--explain"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    lines = [line for line in result.stderr.splitlines() if line.strip()]
    assert 6 <= len(lines) <= 10, lines
    assert lines[0].startswith("状态：") and any(line.startswith("下一步：") for line in lines)
    assert report["advice"] == [] or all({"code", "user_summary", "next_action"} <= set(a) for a in report["advice"])


def test_doctor_makes_no_external_request_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """负向对照：默认 doctor 不许碰清单 URL；--probe-network 才碰。"""
    def boom(*args, **kwargs):
        raise AssertionError("doctor must not probe the network by default")

    monkeypatch.setattr(cli_module, "_probe_manifest_url", boom)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["network_probe"] is None

    canned = {"ok": True, "url": "https://mirror.example/m.json", "attempts": [{"url": "https://mirror.example/m.json", "status": 200, "ok": True}]}
    seen: dict[str, object] = {}

    def fake_probe(url, **kwargs):
        seen["url"] = url
        seen["kwargs"] = kwargs
        return canned

    monkeypatch.setattr(cli_module, "_probe_manifest_url", fake_probe)
    result = runner.invoke(app, ["doctor", "--probe-network", "--explain"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["network_probe"] == canned
    assert seen["kwargs"] == {"stop_at_first_success": False}, "doctor 要报每个镜像，不能第一个通了就停"
    assert seen["url"].endswith("runtime-manifest.json")
    assert any(line.startswith("网络：") for line in result.stderr.splitlines())


def test_probe_reports_every_mirror_when_asked_to(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_RUNTIME_MIRROR", "https://mirror.example/gh/")
    calls: list[str] = []

    class FakeResponse:
        status_code = 200

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def head(self, url):
            calls.append(url)
            return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "Client", FakeClient)
    url = "https://github.com/Horace-Maxwell/horosa-skill/releases/latest/download/runtime-manifest.json"
    every = cli_module._probe_manifest_url(url, stop_at_first_success=False)
    assert len(every["attempts"]) == 2 and every["ok"] is True
    calls.clear()
    first = cli_module._probe_manifest_url(url)
    assert len(first["attempts"]) == 1 and len(calls) == 1


# ---------------------------------------------------------------- Windows long paths


def _zip_with_entry(tmp_path: Path, entry: str) -> Path:
    archive = tmp_path / "payload.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(entry, "x")
    return archive


def test_long_path_guard_refuses_when_long_paths_are_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """🔴 首个测试：注册表关 + 深条目 → runtime.install_long_path（此前只在 Windows 真机上才会走到）。"""
    manager = HorosaRuntimeManager(_settings(tmp_path))  # build first: Settings() needs Path.home(), which os.name="nt" breaks
    monkeypatch.setattr(manager_module.os, "name", "nt")
    monkeypatch.setattr(manager_module, "_windows_long_paths_enabled", lambda: False)
    deep = "runtime-payload/" + "/".join(["d" * 20] * 12) + "/file.bin"  # > 250 chars on its own
    archive = _zip_with_entry(tmp_path, deep)

    with pytest.raises(RuntimeInstallError) as excinfo:
        manager._guard_windows_long_paths(archive, tmp_path / "x")
    assert excinfo.value.code == "runtime.install_long_path"
    assert excinfo.value.details["projected_length"] > manager_module.WINDOWS_PATH_LIMIT
    assert "HOROSA_RUNTIME_ROOT" in excinfo.value.details["next_action"]

    # negative controls: registry on → pass; short entry → pass
    monkeypatch.setattr(manager_module, "_windows_long_paths_enabled", lambda: True)
    manager._guard_windows_long_paths(archive, tmp_path / "x")
    monkeypatch.setattr(manager_module, "_windows_long_paths_enabled", lambda: False)
    manager._guard_windows_long_paths(_zip_with_entry(tmp_path, "runtime-payload/short.bin"), tmp_path / "x")


def test_long_path_guard_is_a_no_op_off_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = HorosaRuntimeManager(_settings(tmp_path))
    monkeypatch.setattr(manager_module.os, "name", "posix")
    deep = "runtime-payload/" + "/".join(["d" * 20] * 12) + "/file.bin"
    manager._guard_windows_long_paths(_zip_with_entry(tmp_path, deep), tmp_path / "x")


def test_install_temp_dir_uses_the_short_prefix() -> None:
    """`.horosa-install-XXXXXXXX/extract/` → `.hi-XXXXXXXX/x/`：20 个字符的余量，doctor 按同一常量估。"""
    source = inspect.getsource(HorosaRuntimeManager.install)
    assert "prefix=_INSTALL_TEMP_PREFIX" in source and "_INSTALL_EXTRACT_DIRNAME" in source
    assert manager_module._INSTALL_TEMP_PREFIX == ".hi-" and manager_module._INSTALL_EXTRACT_DIRNAME == "x"
    assert manager_module._INSTALL_TEMP_OVERHEAD == len(".hi-abcdefgh/x/")
    assert len(".horosa-install-abcdefgh/extract/") - manager_module._INSTALL_TEMP_OVERHEAD >= 18


def test_windows_path_report_headroom(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module.os, "name", "nt")
    monkeypatch.setattr(manager_module, "_windows_long_paths_enabled", lambda: False)
    short_root = Path("C:/horosa")
    report = manager_module.windows_path_report(short_root)
    assert report["long_paths_enabled"] is False and report["ok"] is True
    assert report["headroom_chars"] == manager_module.WINDOWS_PATH_LIMIT - (
        len(str(short_root)) + 1 + manager_module._INSTALL_TEMP_OVERHEAD + manager_module.PAYLOAD_LONGEST_ENTRY_CHARS
    )
    long_root = Path("C:/Users/" + "n" * 80 + "/OneDrive/Documents/horosa/runtime")
    report = manager_module.windows_path_report(long_root)
    assert report["ok"] is False and report["headroom_chars"] < 0 and "HOROSA_RUNTIME_ROOT" in report["fix"]
    monkeypatch.setattr(manager_module, "_windows_long_paths_enabled", lambda: True)
    assert manager_module.windows_path_report(long_root)["ok"] is True
    monkeypatch.setattr(manager_module.os, "name", "posix")
    assert manager_module.windows_path_report(long_root) is None


# ---------------------------------------------------------------- disk precheck


_Usage = namedtuple("_Usage", "total used free")


@pytest.mark.parametrize(
    ("asset", "free", "expect_error"),
    [
        ({"size": 100_000_000}, 399_999_999, True),   # 4 × size
        ({"size": 100_000_000}, 400_000_000, False),
        ({}, 2_999_999_999, True),                    # no size → 3 GB fallback
        ({}, 3_000_000_000, False),
        ({"size": "not-a-number"}, 3_000_000_000, False),
    ],
)
def test_disk_precheck_uses_four_times_size_or_the_fallback(asset, free, expect_error, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module.shutil, "disk_usage", lambda path: _Usage(10**12, 10**12 - free, free))
    manager = HorosaRuntimeManager(_settings(tmp_path))
    if expect_error:
        with pytest.raises(RuntimeInstallError) as excinfo:
            manager._require_install_disk_space(asset)
        assert excinfo.value.code == "runtime.install_insufficient_disk"
        assert excinfo.value.details["free_bytes"] == free
    else:
        manager._require_install_disk_space(asset)


# ---------------------------------------------------------------- macOS quarantine


def _fake_xattr(flagged: bool):
    class Completed:
        def __init__(self, code, out):
            self.returncode, self.stdout, self.stderr = code, out, ""

    def run(command, **kwargs):
        assert command[:3] == ["/usr/bin/xattr", "-p", "com.apple.quarantine"], command
        return Completed(0, "0083;66f1;Safari;ABC\n") if flagged else Completed(1, "")

    return run


def test_quarantined_binaries_become_an_issue_with_the_fix_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = HorosaRuntimeManager(_settings(tmp_path))
    manager.install(archive=str(_fake_archive(tmp_path)))  # Windows lanes: the bare archive's defaults resolve to runtime/windows/*
    monkeypatch.setattr(manager_module.sys, "platform", "darwin")
    monkeypatch.setattr(manager_module.subprocess, "run", _fake_xattr(True))

    report = manager.doctor()

    assert "quarantine:runtime_binaries" in report["issues"]
    assert len(report["quarantine"]["flagged"]) == 3
    assert report["quarantine"]["fix"].startswith("xattr -dr com.apple.quarantine ")

    monkeypatch.setattr(manager_module.subprocess, "run", _fake_xattr(False))
    clean = manager.doctor()
    assert "quarantine:runtime_binaries" not in clean["issues"] and clean["quarantine"]["flagged"] == []
    assert len(clean["quarantine"]["checked"]) == 3


def test_quarantine_check_is_skipped_off_macos_and_when_not_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = HorosaRuntimeManager(_settings(tmp_path))
    monkeypatch.setattr(manager_module.subprocess, "run", _fake_xattr(True))
    monkeypatch.setattr(manager_module.sys, "platform", "linux")
    assert manager.doctor()["quarantine"] == {"checked": [], "flagged": [], "fix": None}
    monkeypatch.setattr(manager_module.sys, "platform", "darwin")
    assert manager.doctor()["quarantine"]["checked"] == [], "没装就没有可查的文件"


# ---------------------------------------------------------------- emulated process warning


def test_emulated_process_becomes_a_warning_with_advice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module, "arch_report", lambda: {"process": "x64", "native": "arm64", "emulated": True})
    settings = Settings.from_env()
    report = cli_module._doctor_report(settings, cli_module._runtime_manager(settings))
    codes = [w["code"] for w in report["warnings"]]
    assert "platform:emulated_process" in codes
    assert any(a["code"] == "platform:emulated_process" for a in report["advice"])

    monkeypatch.setattr(manager_module, "arch_report", lambda: {"process": "arm64", "native": "arm64", "emulated": False})
    report = cli_module._doctor_report(settings, cli_module._runtime_manager(settings))
    assert "platform:emulated_process" not in [w["code"] for w in report["warnings"]]


# ---------------------------------------------------------------- download knobs


def test_download_knobs_are_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_RUNTIME_DOWNLOAD_TIMEOUT_SECONDS", "600")
    monkeypatch.setenv("HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS", "7")
    settings = Settings.from_env()
    assert settings.runtime_download_timeout_seconds == 600.0 and settings.runtime_download_attempts == 7
    assert settings.settings_provenance["runtime_download_attempts"] == "env:HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS"
    monkeypatch.setenv("HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS", "0")  # below minimum → default
    assert Settings.from_env().runtime_download_attempts == 3


def test_download_loop_honours_attempts_and_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    seen: list[object] = []

    class FailingClient:
        def __init__(self, *args, timeout=None, **kwargs):
            seen.append(timeout)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def stream(self, *args, **kwargs):
            raise httpx.ConnectError("refused")

    monkeypatch.setattr(manager_module.httpx, "Client", FailingClient)
    monkeypatch.setattr(manager_module.time, "sleep", lambda seconds: None)
    settings = _settings(tmp_path)
    settings.runtime_download_attempts = 2
    settings.runtime_download_timeout_seconds = 300.0
    manager = HorosaRuntimeManager(settings)

    with pytest.raises(RuntimeInstallError) as excinfo:
        manager._download_with_resume("https://example.com/runtime.tar.gz", tmp_path)
    assert excinfo.value.code == "runtime.install_download_failed"
    assert excinfo.value.details["attempts_per_source"] == 2
    assert len(seen) == 2, "一个源 × 2 次"
    assert seen[0].read == 300.0 and seen[0].connect == 60.0
