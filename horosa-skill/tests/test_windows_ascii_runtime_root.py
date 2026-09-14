"""Windows：runtime 根必须是纯 ASCII（v0.38.1）。

真机证据（v0.38.1 draft 的 runtime-matrix，en-US cp1252 runner）：
  runtime 根「horosa 测试 lane」 → `Unable to access jarfile …??…`；jar 参数改相对后 → `could not find java.dll`
      （随包 JDK 17 的 java.exe 用 GetModuleFileNameA / GetCommandLineA）
  runtime 根「horosa lane é」（cp1252 能表示） → Java 起来了，但 Swiss Ephemeris 打不开星历：`KeyError: 'Chiron'`，
      29 个 chart 族测试报 `tool.backend_param_error`（pyswisseph 把 UTF-8 路径交给 C fopen，Windows 的 fopen 按 ANSI 解字节）
所以规则只能是「纯 ASCII」——中文系统（cp936）上的中文用户名同样中招。修法：install 下载前拒绝、doctor 报 issue。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import RECOVERY_TABLE, RuntimeInstallError
from horosa_skill.runtime import manager as manager_module
from horosa_skill.runtime.manager import HorosaRuntimeManager
from horosa_skill.surfaces import cli as cli_module


@pytest.mark.parametrize(
    ("path", "ok"),
    [
        (r"C:\horosa", True),
        (r"D:\a\_temp\horosa lane runtime", True),          # spaces are fine (launcher quotes every path)
        (r"D:\a\_temp\horosa 测试 lane\runtime", False),    # killed java.exe on the cp1252 runner
        (r"C:\Users\张三\AppData\Local\Horosa\runtime", False),  # zh-CN default root: swisseph still breaks
        (r"D:\a\_temp\horosa lane é\runtime", False),       # cp1252-representable, yet the ephemeris could not be opened
        (r"C:\Users\Иван\AppData", False),
    ],
)
def test_windows_runtime_path_must_be_ascii(path: str, ok: bool) -> None:
    assert manager_module.windows_runtime_path_ok(path) is ok


def _settings(tmp_path: Path, root: Path) -> Settings:
    return Settings(runtime_root=root, db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_platform="win32-x64")


def _as_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module, "_host_is_windows", lambda: True)
    monkeypatch.setattr(manager_module, "windows_ansi_code_page", lambda: 936)


def test_install_refuses_a_non_ascii_root_before_downloading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _as_windows(monkeypatch)
    root = tmp_path / "张三" / "runtime"
    manager = HorosaRuntimeManager(_settings(tmp_path, root))

    def boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("must refuse before touching the manifest or the archive")

    monkeypatch.setattr(manager, "_read_json_location", boom)
    monkeypatch.setattr(manager, "_materialize_archive", boom)
    with pytest.raises(RuntimeInstallError) as excinfo:
        manager.install(manifest_url="https://example.invalid/runtime-manifest.json")
    assert excinfo.value.code == "runtime.path_not_ascii"
    details = excinfo.value.details
    assert "张三" in details["runtime_root"] and details["ansi_code_page"] == 936 and "fopen" in details["why"]
    assert "HOROSA_RUNTIME_ROOT" in details["next_action"] and details["agent_recovery"]["must_ask_user"] is True
    assert not root.exists()


def test_install_is_not_refused_for_an_ascii_root_with_spaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """负向对照：同样的 Windows 形状，纯 ASCII（带空格）的根照常往下走（这里走到读清单）。"""
    _as_windows(monkeypatch)
    manager = HorosaRuntimeManager(_settings(tmp_path, tmp_path / "horosa lane" / "runtime"))
    reached: list[str] = []

    def stop_here(location):  # noqa: ANN001
        reached.append(location)
        raise RuntimeInstallError("stop", code="test.reached_manifest", details={})

    monkeypatch.setattr(manager, "_read_json_location", stop_here)
    with pytest.raises(RuntimeInstallError) as excinfo:
        manager.install(manifest_url="https://example.invalid/runtime-manifest.json")
    assert excinfo.value.code == "test.reached_manifest" and reached


def test_the_accented_root_that_broke_the_ephemeris_is_refused_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """「horosa lane é」：Java 能起（cp1252 可表示），星历打不开——ANSI 可表示不等于安全，旧的 ANSI 判定会放行它（负向对照）。"""
    _as_windows(monkeypatch)
    root = tmp_path / "horosa lane é" / "runtime"
    assert str(root).encode("cp1252")  # the previous rule (ANSI-representable) would have let this through
    manager = HorosaRuntimeManager(_settings(tmp_path, root))
    with pytest.raises(RuntimeInstallError) as excinfo:
        manager._require_ascii_runtime_root()
    assert excinfo.value.code == "runtime.path_not_ascii"


def test_off_windows_nothing_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module, "_host_is_windows", lambda: False)
    HorosaRuntimeManager(_settings(tmp_path, tmp_path / "horosa 测试 lane"))._require_ascii_runtime_root()


def test_doctor_reports_the_non_ascii_root_as_an_issue_with_advice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _as_windows(monkeypatch)
    report = HorosaRuntimeManager(_settings(tmp_path, tmp_path / "张三" / "runtime")).doctor()
    assert "windows:runtime_root_not_ascii" in report["issues"]
    advice = cli_module._advice_for("windows:runtime_root_not_ascii")
    assert "HOROSA_RUNTIME_ROOT" in advice["next_action"] and "doctor 报了" not in advice["user_summary"]
    clean = HorosaRuntimeManager(_settings(tmp_path, tmp_path / "horosa lane" / "runtime")).doctor()
    assert "windows:runtime_root_not_ascii" not in clean["issues"]


def test_windows_path_report_carries_the_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module.os, "name", "nt")
    monkeypatch.setattr(manager_module, "_windows_long_paths_enabled", lambda: False)
    monkeypatch.setattr(manager_module, "windows_ansi_code_page", lambda: 1252)
    bad = manager_module.windows_path_report(Path(r"C:\Users\张三\AppData\Local\Horosa\runtime"))
    assert bad["runtime_root_ascii"] is False and bad["ansi_code_page"] == 1252 and "HOROSA_RUNTIME_ROOT" in bad["path_fix"]
    good = manager_module.windows_path_report(Path(r"C:\horosa"))
    assert good["runtime_root_ascii"] is True and good["path_fix"] is None


def test_error_code_is_classified() -> None:
    assert RECOVERY_TABLE["runtime.path_not_ascii"]["kind"] == "runtime"
    assert "runtime.path_not_ansi" not in RECOVERY_TABLE
