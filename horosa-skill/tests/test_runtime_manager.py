from __future__ import annotations

import json
import tarfile
from pathlib import Path
from types import MethodType

from horosa_skill.config import Settings
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
