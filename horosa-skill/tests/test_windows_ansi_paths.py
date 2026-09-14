"""Windows：runtime 根必须能穿过系统 ANSI 代码页（v0.38.1）。

真机证据（v0.38.1 draft 的 runtime-matrix，en-US cp1252 runner，工作目录「horosa 测试 lane」）：
  draft #1  `Error: Unable to access jarfile D:\\a\\_temp\\horosa ?? lane\\…\\astrostudyboot.jar`
  draft #2  （jar 参数改相对后）`Error: could not find java.dll` / `Could not find Java SE Runtime Environment.`
随包 JDK 17 的 java.exe 用 GetModuleFileNameA 找自己的 java.dll —— 参数怎么改都绕不开。修法：install 下载前拒绝、doctor 报 issue。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import RECOVERY_TABLE, RuntimeInstallError
from horosa_skill.runtime import manager as manager_module
from horosa_skill.runtime.manager import HorosaRuntimeManager
from horosa_skill.surfaces import cli as cli_module

CJK_ROOT = r"D:\a\_temp\horosa 测试 lane\runtime"
ACCENT_ROOT = r"D:\a\_temp\horosa lane é\runtime"


@pytest.mark.parametrize(
    ("path", "encoding", "safe"),
    [
        (CJK_ROOT, "cp1252", False),       # the runner shape that killed Java
        (CJK_ROOT, "cp936", True),         # zh-CN Windows: a Chinese user name is representable
        (ACCENT_ROOT, "cp1252", True),     # the lane's Windows runtime root: non-ASCII but representable
        (r"C:\Users\Иван\AppData", "cp1252", False),
        (r"C:\Users\Иван\AppData", "cp1251", True),
        (r"C:\horosa", "cp1252", True),
        ("C:\\Users\\x\\\U0001F600", "cp936", False),  # emoji: not in GBK
    ],
)
def test_path_is_ansi_safe_follows_the_code_page(path: str, encoding: str, safe: bool) -> None:
    assert manager_module.path_is_ansi_safe(path, encoding=encoding) is safe


def test_best_fit_mapping_does_not_count_as_representable() -> None:
    """严格编码：cp1252 没有「ł」，Windows 的 best-fit 会把它悄悄变成「l」—— 那同样是一个错的路径。"""
    assert manager_module.path_is_ansi_safe("C:\\Users\\Michał", encoding="cp1252") is False


def test_missing_codec_off_windows_is_not_a_refusal() -> None:
    assert manager_module.path_is_ansi_safe("/Users/张三/.horosa", encoding="no-such-codec") is True


def _settings(tmp_path: Path) -> Settings:
    return Settings(runtime_root=tmp_path / "runtime-root", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs",
                    runtime_platform="win32-x64")


def _as_cp1252_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module, "_host_is_windows", lambda: True)
    monkeypatch.setattr(manager_module, "windows_ansi_code_page", lambda: 1252)
    real = manager_module.path_is_ansi_safe
    monkeypatch.setattr(manager_module, "path_is_ansi_safe", lambda path, encoding="cp1252": real(path, encoding="cp1252"))


def test_install_refuses_a_non_ansi_root_before_downloading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _as_cp1252_windows(monkeypatch)
    settings = _settings(tmp_path)
    settings.runtime_root = tmp_path / "horosa 测试 lane" / "runtime"
    manager = HorosaRuntimeManager(settings)

    def boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("must refuse before touching the manifest or the archive")

    monkeypatch.setattr(manager, "_read_json_location", boom)
    monkeypatch.setattr(manager, "_materialize_archive", boom)
    with pytest.raises(RuntimeInstallError) as excinfo:
        manager.install(manifest_url="https://example.invalid/runtime-manifest.json")
    assert excinfo.value.code == "runtime.path_not_ansi"
    details = excinfo.value.details
    assert details["ansi_code_page"] == 1252 and "测试" in details["runtime_root"]
    assert "HOROSA_RUNTIME_ROOT" in details["next_action"] and details["agent_recovery"]["must_ask_user"] is True
    assert not (settings.runtime_root / "current").exists()


def test_install_is_not_refused_for_a_representable_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """负向对照：同样的 Windows 形状，但路径只含 cp1252 能表示的字符（空格 + é）→ 照常往下走（这里走到读清单）。"""
    _as_cp1252_windows(monkeypatch)
    settings = _settings(tmp_path)
    settings.runtime_root = tmp_path / "horosa lane é" / "runtime"
    manager = HorosaRuntimeManager(settings)
    reached: list[str] = []

    def stop_here(location):  # noqa: ANN001
        reached.append(location)
        raise RuntimeInstallError("stop", code="test.reached_manifest", details={})

    monkeypatch.setattr(manager, "_read_json_location", stop_here)
    with pytest.raises(RuntimeInstallError) as excinfo:
        manager.install(manifest_url="https://example.invalid/runtime-manifest.json")
    assert excinfo.value.code == "test.reached_manifest" and reached


def test_off_windows_nothing_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module, "_host_is_windows", lambda: False)
    manager = HorosaRuntimeManager(Settings(runtime_root=tmp_path / "horosa 测试 lane", db_path=tmp_path / "m.db",
                                            output_dir=tmp_path / "runs"))
    manager._require_ansi_safe_runtime_root()  # no raise


def test_doctor_reports_the_non_ansi_root_as_an_issue_with_advice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _as_cp1252_windows(monkeypatch)
    settings = _settings(tmp_path)
    settings.runtime_root = tmp_path / "horosa 测试 lane" / "runtime"
    report = HorosaRuntimeManager(settings).doctor()
    assert "windows:runtime_root_not_ansi" in report["issues"]
    advice = cli_module._advice_for("windows:runtime_root_not_ansi")
    assert "HOROSA_RUNTIME_ROOT" in advice["next_action"] and "doctor 报了" not in advice["user_summary"]
    settings.runtime_root = tmp_path / "horosa lane é" / "runtime"
    assert "windows:runtime_root_not_ansi" not in HorosaRuntimeManager(settings).doctor()["issues"]


def test_windows_path_report_carries_the_ansi_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module.os, "name", "nt")
    monkeypatch.setattr(manager_module, "_windows_long_paths_enabled", lambda: False)
    monkeypatch.setattr(manager_module, "windows_ansi_code_page", lambda: 1252)
    real = manager_module.path_is_ansi_safe
    monkeypatch.setattr(manager_module, "path_is_ansi_safe", lambda path, encoding="cp1252": real(path, encoding="cp1252"))
    bad = manager_module.windows_path_report(Path(CJK_ROOT))
    assert bad["runtime_root_ansi_safe"] is False and bad["ansi_code_page"] == 1252 and "HOROSA_RUNTIME_ROOT" in bad["ansi_fix"]
    good = manager_module.windows_path_report(Path(ACCENT_ROOT))
    assert good["runtime_root_ansi_safe"] is True and good["ansi_fix"] is None


def test_error_code_is_classified() -> None:
    assert RECOVERY_TABLE["runtime.path_not_ansi"]["kind"] == "runtime"
