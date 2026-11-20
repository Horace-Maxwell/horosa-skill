"""审计 PF-04（第 3 条）：升级后旧副本留到新 runtime 第一次起成功；起不来就自动换回旧版。

以前换入新载荷后当场删 previous/：新版起不来时只剩一份坏的 runtime，用户只能重新下载 730 MB。
目录搬移与标记文件是真的；载荷完整性判定、停服务、真正的启动被替身（它们各有自己的用例）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import RuntimeInstallError
from horosa_skill.runtime.manager import HorosaRuntimeManager


def _manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, start) -> HorosaRuntimeManager:  # noqa: ANN001
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path / "d",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    manager = HorosaRuntimeManager(settings)
    for name, version in (("current", "0.52.0"), ("previous", "0.51.0")):
        root = manager.runtime_root / name
        root.mkdir(parents=True)
        (root / "runtime-manifest.json").write_text(json.dumps({"version": version}), encoding="utf-8")
    monkeypatch.setattr(manager, "_payload_is_complete", lambda root: (root / "runtime-manifest.json").is_file())
    monkeypatch.setattr(manager, "stop_local_services", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(manager, "_start_local_services_impl", start)
    manager._mark_upgrade_pending(manager.runtime_root / "previous", previous_version="0.51.0", version="0.52.0")
    return manager


def _version(manager: HorosaRuntimeManager) -> str:
    return json.loads((manager.current_dir / "runtime-manifest.json").read_text(encoding="utf-8"))["version"]


def test_first_successful_start_confirms_the_upgrade_and_drops_the_old_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """负向对照（实跑过）：start_local_services 不调 _confirm_pending_upgrade → previous/ 与标记还在 → 红。"""
    manager = _manager(tmp_path, monkeypatch, lambda **kwargs: {"ok": True, "already_running": False, "degraded": False})
    assert manager.upgrade_pending() == {"previous_version": "0.51.0", "version": "0.52.0", "since": manager.upgrade_pending()["since"]}
    manager.start_local_services()
    assert manager.upgrade_pending() is None and not (manager.runtime_root / "previous").exists() and _version(manager) == "0.52.0"


def test_a_failed_first_start_rolls_back_to_the_previous_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """负向对照（实跑过）：去掉 start_local_services 里的回滚分支 → 原样抛 start_failed、current 仍是坏的新版 → 红。"""
    def start(**kwargs):  # noqa: ANN003, ANN202
        raise RuntimeInstallError("boom", code="runtime.start_failed", details={})

    manager = _manager(tmp_path, monkeypatch, start)
    with pytest.raises(RuntimeInstallError) as caught:
        manager.start_local_services()
    assert caught.value.code == "runtime.install_rolled_back"
    assert caught.value.details["rolled_back_to"] == "0.51.0" and caught.value.details["failed_version"] == "0.52.0"
    assert _version(manager) == "0.51.0" and manager.upgrade_pending() is None
    assert not (manager.runtime_root / "failed-upgrade").exists()


def test_no_rollback_when_another_process_holds_the_port_or_nothing_is_pending(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(**kwargs):  # noqa: ANN003, ANN202
        raise RuntimeInstallError("timeout", code="runtime.start_timeout", details={"port_takers": [{"pid": 1}]})

    manager = _manager(tmp_path, monkeypatch, blocked)
    with pytest.raises(RuntimeInstallError) as caught:
        manager.start_local_services()
    assert caught.value.code == "runtime.start_timeout" and _version(manager) == "0.52.0" and manager.upgrade_pending() is not None
    (manager.runtime_root / ".upgrade-pending.json").unlink()

    def failed(**kwargs):  # noqa: ANN003, ANN202
        raise RuntimeInstallError("boom", code="runtime.start_failed", details={})

    monkeypatch.setattr(manager, "_start_local_services_impl", failed)
    with pytest.raises(RuntimeInstallError) as caught:
        manager.start_local_services()
    assert caught.value.code == "runtime.start_failed" and _version(manager) == "0.52.0"


def test_a_degraded_or_still_starting_start_keeps_the_old_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager(tmp_path, monkeypatch, lambda **kwargs: {"ok": True, "starting": True})
    manager.start_local_services()
    assert manager.upgrade_pending() is not None
    monkeypatch.setattr(manager, "_start_local_services_impl", lambda **kwargs: {"ok": True, "degraded": True})
    manager.start_local_services()
    assert manager.upgrade_pending() is not None and (manager.runtime_root / "previous").exists()
