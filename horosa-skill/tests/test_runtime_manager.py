from __future__ import annotations

import json
import subprocess
import tarfile
from pathlib import Path
from types import MethodType

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import RuntimeValidationError
from horosa_skill.runtime import HorosaRuntimeManager


def create_runtime_archive(tmp_path: Path) -> Path:
    payload_root = tmp_path / "runtime-payload"
    (payload_root / "Horosa-Web/astropy").mkdir(parents=True, exist_ok=True)
    (payload_root / "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles").mkdir(parents=True, exist_ok=True)
    (payload_root / "horosa-core-js/bin").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/mac/java/bin").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/mac/python/bin").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/mac/node/bin").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/mac/bundle").mkdir(parents=True, exist_ok=True)
    (payload_root / "Horosa-Web/start_horosa_local.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (payload_root / "Horosa-Web/stop_horosa_local.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (payload_root / "horosa-core-js/bin/cli.mjs").write_text("export {};\n", encoding="utf-8")
    (payload_root / "runtime/mac/java/bin/java").write_text("", encoding="utf-8")
    (payload_root / "runtime/mac/python/bin/python3").write_text("", encoding="utf-8")
    (payload_root / "runtime/mac/node/bin/node").write_text("", encoding="utf-8")
    (payload_root / "runtime/mac/bundle/astrostudyboot.jar").write_text("", encoding="utf-8")
    (payload_root / "runtime-manifest.json").write_text(json.dumps({"version": "1.2.3"}), encoding="utf-8")
    archive_path = tmp_path / "runtime-payload.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(payload_root, arcname="runtime-payload")
    return archive_path


def test_install_runtime_from_local_archive(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)

    result = manager.install(archive=str(archive))

    assert result["ok"] is True
    assert result["manifest"]["version"] == "1.2.3"
    assert result["manifest"]["schema_version"] == 1
    assert result["manifest"]["services"]["start_script"] == "Horosa-Web/start_horosa_local.sh"
    assert (settings.runtime_current_dir / "runtime-manifest.json").is_file()


def test_doctor_reports_installed_runtime(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    report = manager.doctor()

    assert report["installed"] is True
    assert report["manifest"]["version"] == "1.2.3"
    assert any(item["label"] == "java_runtime" for item in report["files"])
    assert any(item["label"] == "python_runtime" for item in report["files"])
    assert any(item["label"] == "node_runtime" for item in report["files"])
    assert any(item["label"] == "horosa_core_js_root" for item in report["files"])


def test_install_runtime_from_manifest_file_url(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    manifest = tmp_path / "runtime-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "1.2.3",
                "platforms": {
                    "darwin-arm64": {
                        "url": archive.resolve().as_uri(),
                        "sha256": "",
                        "archive_type": "tar.gz",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_platform="darwin-arm64",
    )
    manager = HorosaRuntimeManager(settings)

    result = manager.install(manifest_url=manifest.resolve().as_uri())

    assert result["ok"] is True
    assert result["manifest"]["version"] == "1.2.3"
    assert (settings.runtime_current_dir / "runtime-manifest.json").is_file()


def test_start_and_stop_runtime_updates_state(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        state = self.load_runtime_state()
        reachable = bool(state and state.get("status") == "running")
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": reachable},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": reachable},
        ]

    def fake_write_runtime_state(self: HorosaRuntimeManager, payload: dict[str, object]) -> None:
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.settings.runtime_state_path.write_text(json.dumps(payload), encoding="utf-8")

    def fake_wait_for_service_state(
        self: HorosaRuntimeManager,
        *,
        expected_reachable: bool,
        timeout_seconds: float,
        manifest: dict | None,
    ) -> dict[str, object]:
        if not expected_reachable and self.settings.runtime_state_path.exists():
            self.settings.runtime_state_path.unlink()
        return {
            "ready": True,
            "endpoints": [
                {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": expected_reachable},
                {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": expected_reachable},
            ],
        }

    manager._service_status = MethodType(fake_service_status, manager)
    manager._write_runtime_state = MethodType(fake_write_runtime_state, manager)
    manager._wait_for_service_state = MethodType(fake_wait_for_service_state, manager)

    started = manager.start_local_services()

    assert started["ok"] is True
    assert started["already_running"] is False
    assert settings.runtime_state_path.is_file()

    stopped = manager.stop_local_services()

    assert stopped["ok"] is True
    assert stopped["already_stopped"] is False
    assert not settings.runtime_state_path.exists()


def test_doctor_reports_invalid_manifest_and_runtime_state_without_crashing(tmp_path: Path) -> None:
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    settings.runtime_current_dir.mkdir(parents=True, exist_ok=True)
    (settings.runtime_current_dir / "runtime-manifest.json").write_text("{bad json", encoding="utf-8")
    settings.runtime_state_path.parent.mkdir(parents=True, exist_ok=True)
    settings.runtime_state_path.write_text("[1, 2, 3]", encoding="utf-8")

    report = manager.doctor()

    assert report["installed"] is True
    assert report["ok"] is False
    assert report["manifest"] is None
    assert report["manifest_issue"]["code"] == "runtime.manifest_invalid"
    assert report["runtime_state"] is None
    assert report["runtime_state_issue"]["code"] == "runtime.state_invalid"
    assert "runtime.manifest_invalid" in report["issues"]
    assert "runtime.state_invalid" in report["issues"]


def test_start_runtime_raises_for_invalid_installed_manifest(tmp_path: Path) -> None:
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    settings.runtime_current_dir.mkdir(parents=True, exist_ok=True)
    (settings.runtime_current_dir / "runtime-manifest.json").write_text("{bad json", encoding="utf-8")

    with pytest.raises(RuntimeValidationError, match="Installed runtime manifest is invalid"):
        manager.start_local_services()


def test_start_runtime_does_not_treat_partial_service_state_as_already_running(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    service_states = iter(
        [
            [
                {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
                {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
            ],
            [
                {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
                {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
            ],
        ]
    )

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return next(service_states)

    def fake_wait_for_service_state(
        self: HorosaRuntimeManager,
        *,
        expected_reachable: bool,
        timeout_seconds: float,
        manifest: dict | None,
    ) -> dict[str, object]:
        return {
            "ready": True,
            "endpoints": [
                {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": expected_reachable},
                {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": expected_reachable},
            ],
        }

    manager._service_status = MethodType(fake_service_status, manager)
    manager._wait_for_service_state = MethodType(fake_wait_for_service_state, manager)

    started = manager.start_local_services()

    assert started["ok"] is True
    assert started["already_running"] is False


def test_doctor_marks_partial_service_state_as_not_running(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
        ]

    manager._service_status = MethodType(fake_service_status, manager)

    report = manager.doctor()

    assert report["ok"] is False
    assert "services:not_running" in report["issues"]


def test_start_runtime_succeeds_when_script_returns_nonzero_but_services_become_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": False},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
        ]

    def fake_wait_for_service_state(
        self: HorosaRuntimeManager,
        *,
        expected_reachable: bool,
        timeout_seconds: float,
        manifest: dict | None,
    ) -> dict[str, object]:
        return {
            "ready": True,
            "endpoints": [
                {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": expected_reachable},
                {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": expected_reachable},
            ],
        }

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["bash"], returncode=1, stdout="partial startup", stderr="pid warning")

    manager._service_status = MethodType(fake_service_status, manager)
    manager._wait_for_service_state = MethodType(fake_wait_for_service_state, manager)
    monkeypatch.setattr(subprocess, "run", fake_run)

    started = manager.start_local_services()

    assert started["ok"] is True
    assert started["warning"]["code"] == "runtime.start_nonzero_but_ready"
    assert manager.load_runtime_state()["status"] == "running_with_warnings"


def test_start_runtime_recovers_partial_state_before_launch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    service_states = iter(
        [
            [
                {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
                {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
            ],
            [
                {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
                {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
            ],
        ]
    )

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return next(service_states)

    def fake_wait_for_service_state(
        self: HorosaRuntimeManager,
        *,
        expected_reachable: bool,
        timeout_seconds: float,
        manifest: dict | None,
    ) -> dict[str, object]:
        return {
            "ready": True,
            "endpoints": [
                {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": expected_reachable},
                {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": expected_reachable},
            ],
        }

    stop_calls: list[str] = []

    def fake_stop_local_services() -> dict[str, object]:
        stop_calls.append("stop")
        return {"ok": True, "already_stopped": False}

    manager._service_status = MethodType(fake_service_status, manager)
    manager._wait_for_service_state = MethodType(fake_wait_for_service_state, manager)
    monkeypatch.setattr(manager, "stop_local_services", fake_stop_local_services)

    started = manager.start_local_services()

    assert started["ok"] is True
    assert started["recovered_partial_state"] is True
    assert stop_calls == ["stop"]


def test_start_runtime_retries_after_failed_launch_with_stale_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": False},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
        ]

    run_results = iter(
        [
            (
                subprocess.CompletedProcess(args=["bash"], returncode=1, stdout="pid files already exist", stderr=""),
                {
                    "ready": False,
                    "endpoints": [
                        {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
                        {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
                    ],
                },
            ),
            (
                subprocess.CompletedProcess(args=["bash"], returncode=0, stdout="ok", stderr=""),
                {
                    "ready": True,
                    "endpoints": [
                        {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
                        {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
                    ],
                },
            ),
        ]
    )

    def fake_run_start_command(
        self: HorosaRuntimeManager,
        *,
        command: list[str],
        script: Path,
        env: dict[str, str],
        manifest: dict | None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        return next(run_results)

    stop_calls: list[str] = []

    def fake_stop_local_services() -> dict[str, object]:
        stop_calls.append("stop")
        return {"ok": True, "already_stopped": False}

    manager._service_status = MethodType(fake_service_status, manager)
    manager._run_start_command = MethodType(fake_run_start_command, manager)
    monkeypatch.setattr(manager, "stop_local_services", fake_stop_local_services)

    started = manager.start_local_services()

    assert started["ok"] is True
    assert started["recovered_partial_state"] is True
    assert stop_calls == ["stop"]
