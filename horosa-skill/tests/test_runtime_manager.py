from __future__ import annotations

import json
import subprocess
import tarfile
import threading
import zipfile
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


def create_windows_runtime_archive(tmp_path: Path) -> Path:
    payload_root = tmp_path / "runtime-payload"
    (payload_root / "Horosa-Web/astropy").mkdir(parents=True, exist_ok=True)
    (payload_root / "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles").mkdir(parents=True, exist_ok=True)
    (payload_root / "horosa-core-js/bin").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/windows/java/bin").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/windows/python").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/windows/node").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/windows/bundle").mkdir(parents=True, exist_ok=True)
    (payload_root / "Horosa-Web/start_horosa_local.ps1").write_text("Write-Host 'old start'\n", encoding="utf-8")
    (payload_root / "Horosa-Web/stop_horosa_local.ps1").write_text("Write-Host 'old stop'\n", encoding="utf-8")
    (payload_root / "runtime/windows/java/bin/java.exe").write_text("", encoding="utf-8")
    (payload_root / "runtime/windows/python/python.exe").write_text("", encoding="utf-8")
    (payload_root / "runtime/windows/node/node.exe").write_text("", encoding="utf-8")
    boot_jar = payload_root / "runtime/windows/bundle/astrostudyboot.jar"
    with zipfile.ZipFile(boot_jar, "w") as archive:
        archive.writestr(
            "BOOT-INF/classes/conf/properties/cache/caches.json",
            json.dumps(
                {
                    "needlocalmemcache": False,
                    "needcompress": False,
                    "needhystrix": False,
                    "cachefactoryclass": [
                        {
                            "default": True,
                            "name": "comm",
                            "class": "boundless.types.cache.RedisCacheFactory",
                            "config": "classpath:conf/properties/cache/rediscomm.properties",
                        },
                        {
                            "name": "clientapps",
                            "class": "boundless.types.cache.MongoCacheFactory",
                            "config": "classpath:conf/properties/cache/clientapps.properties",
                        },
                    ],
                }
            ),
        )
        archive.writestr(
            "BOOT-INF/classes/conf/properties/param/webparams.properties",
            "webencrypt.rsaparam.class=spacex.astrostudy.helper.RsaParamHelper\n",
        )
        archive.writestr(
            "BOOT-INF/classes/log4j2.xml",
            '<Configuration><Properties><Property name="basedir">${env:HOME}/.horosa-logs/astrostudyboot</Property></Properties></Configuration>\n',
        )
        archive.writestr("BOOT-INF/lib/boundless-1.2.1.2.jar", b"boundless")
    (payload_root / "runtime-manifest.json").write_text(
        json.dumps(
            {
                "version": "1.2.3",
                "platform": "win32-x64",
                "services": {
                    "start_script": "Horosa-Web/start_horosa_local.ps1",
                    "stop_script": "Horosa-Web/stop_horosa_local.ps1",
                },
                "runtimes": {
                    "python": "runtime/windows/python/python.exe",
                    "java": "runtime/windows/java/bin/java.exe",
                    "node": "runtime/windows/node/node.exe",
                },
                "artifacts": {
                    "horosa_web_root": "Horosa-Web",
                    "astropy_root": "Horosa-Web/astropy",
                    "flatlib_root": "Horosa-Web/flatlib-ctrad2/flatlib",
                    "swefiles_root": "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles",
                    "boot_jar": "runtime/windows/bundle/astrostudyboot.jar",
                    "horosa_core_js_root": "horosa-core-js",
                },
            }
        ),
        encoding="utf-8",
    )
    archive_path = tmp_path / "runtime-payload.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for path in payload_root.rglob("*"):
            archive.write(path, path.relative_to(payload_root.parent))
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
    assert result["manifest"]["services"]["start_script"] == str(
        manager._platform_path("Horosa-Web/start_horosa_local.sh", "Horosa-Web/start_horosa_local.ps1")
    )
    assert (settings.runtime_current_dir / "runtime-manifest.json").is_file()


def test_install_runtime_binds_service_urls_to_current_settings(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        server_root="http://127.0.0.1:34528",
        chart_server_root="http://127.0.0.1:34529",
    )
    manager = HorosaRuntimeManager(settings)

    result = manager.install(archive=str(archive))
    installed_manifest = json.loads((settings.runtime_current_dir / "runtime-manifest.json").read_text(encoding="utf-8"))

    assert result["manifest"]["services"]["backend_url"] == "http://127.0.0.1:34528"
    assert result["manifest"]["services"]["chart_url"] == "http://127.0.0.1:34529"
    assert installed_manifest["services"]["backend_url"] == "http://127.0.0.1:34528"
    assert installed_manifest["services"]["chart_url"] == "http://127.0.0.1:34529"


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


def test_service_status_prefers_explicit_env_urls_over_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        server_root="http://127.0.0.1:34528",
        chart_server_root="http://127.0.0.1:34529",
    )
    manager = HorosaRuntimeManager(settings)
    seen: dict[str, str] = {}

    monkeypatch.setenv("HOROSA_SERVER_ROOT", "http://127.0.0.1:34528")
    monkeypatch.setenv("HOROSA_CHART_SERVER_ROOT", "http://127.0.0.1:34529")
    monkeypatch.setattr(manager, "_backend_reachable", lambda url: seen.setdefault("backend", url) or True)
    monkeypatch.setattr(manager, "_http_reachable", lambda url: seen.setdefault("chart", url) or True)

    manager._service_status(
        {
            "services": {
                "backend_url": "http://127.0.0.1:9999",
                "chart_url": "http://127.0.0.1:8899",
            }
        }
    )

    assert seen["backend"] == "http://127.0.0.1:34528/common/time"
    assert seen["chart"] == "http://127.0.0.1:34529"


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
    service_state = {"running": False}

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        reachable = service_state["running"]
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": reachable},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": reachable},
        ]

    def fake_write_runtime_state(self: HorosaRuntimeManager, payload: dict[str, object]) -> None:
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.settings.runtime_state_path.write_text(json.dumps(payload), encoding="utf-8")
        service_state["running"] = str(payload.get("status", "")).startswith("running")

    def fake_wait_for_service_state(
        self: HorosaRuntimeManager,
        *,
        expected_reachable: bool,
        timeout_seconds: float,
        manifest: dict | None,
    ) -> dict[str, object]:
        service_state["running"] = expected_reachable
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


def test_install_patches_windows_runtime_templates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = create_windows_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_platform="win32-x64",
    )
    manager = HorosaRuntimeManager(settings)
    monkeypatch.setattr(
        manager,
        "_compile_windows_runtime_patch_classes",
        lambda manifest, jar_path: {
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory.class": b"class-bytes",
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory$LocalCache.class": b"class-bytes",
        },
    )

    manager.install(archive=str(archive))
    manifest = manager.load_installed_manifest(strict=True)
    monkeypatch.setattr("horosa_skill.runtime.manager.os.name", "nt", raising=False)
    monkeypatch.setattr(manager, "_runtime_template_root", lambda: tmp_path / "template-root")
    monkeypatch.setenv("HOME", r"C:\Users\maxwe")
    monkeypatch.setenv("USERPROFILE", r"C:\Users\maxwe")
    windows_template_root = manager._runtime_template_root() / "windows"
    windows_template_root.mkdir(parents=True, exist_ok=True)
    (windows_template_root / "start_horosa_local.ps1").write_text(
        'Start-Process -RedirectStandardOutput "a" -RedirectStandardError "b"\n',
        encoding="utf-8",
    )
    (windows_template_root / "stop_horosa_local.ps1").write_text(
        'Write-Host "stop requested"\n',
        encoding="utf-8",
    )
    manager._apply_runtime_overrides(manifest)

    start_script = settings.runtime_current_dir / "Horosa-Web/start_horosa_local.ps1"
    stop_script = settings.runtime_current_dir / "Horosa-Web/stop_horosa_local.ps1"
    boot_jar = settings.runtime_current_dir / "runtime/windows/bundle/astrostudyboot.jar"
    assert "RedirectStandardOutput" in start_script.read_text(encoding="utf-8")
    assert "Write-Host \"stop requested\"" in stop_script.read_text(encoding="utf-8")
    with zipfile.ZipFile(boot_jar) as archive:
        cache_config = json.loads(archive.read("BOOT-INF/classes/conf/properties/cache/caches.json"))
        assert all(entry["class"] == "horosa.offline.LocalCacheFactory" for entry in cache_config["cachefactoryclass"])
        assert archive.read("BOOT-INF/classes/conf/properties/param/webparams.properties").decode("utf-8").strip().endswith(
            "webencrypt.rsaparam.class="
        )
        assert (
            archive.read("BOOT-INF/classes/log4j2.xml").decode("utf-8")
            == '<Configuration><Properties><Property name="basedir">C:/Users/maxwe/.horosa-logs/astrostudyboot</Property></Properties></Configuration>\n'
        )
        assert archive.read("BOOT-INF/classes/horosa/offline/LocalCacheFactory.class") == b"class-bytes"
        assert archive.read("BOOT-INF/classes/horosa/offline/LocalCacheFactory$LocalCache.class") == b"class-bytes"


def test_start_runtime_reports_patched_files_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = create_windows_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_platform="win32-x64",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    monkeypatch.setattr(
        manager,
        "_compile_windows_runtime_patch_classes",
        lambda manifest, jar_path: {
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory.class": b"class-bytes",
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory$LocalCache.class": b"class-bytes",
        },
    )
    manager.install(archive=str(archive))
    monkeypatch.setattr("horosa_skill.runtime.manager.os.name", "nt", raising=False)
    monkeypatch.setattr(manager, "_runtime_template_root", lambda: tmp_path / "template-root")
    windows_template_root = manager._runtime_template_root() / "windows"
    windows_template_root.mkdir(parents=True, exist_ok=True)
    (windows_template_root / "start_horosa_local.ps1").write_text(
        'Start-Process -RedirectStandardOutput "a" -RedirectStandardError "b"\n',
        encoding="utf-8",
    )
    (windows_template_root / "stop_horosa_local.ps1").write_text(
        'Write-Host "stop requested"\n',
        encoding="utf-8",
    )

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
        return subprocess.CompletedProcess(args=["powershell"], returncode=0, stdout="ok", stderr="")

    manager._service_status = MethodType(fake_service_status, manager)
    manager._wait_for_service_state = MethodType(fake_wait_for_service_state, manager)
    monkeypatch.setattr(subprocess, "run", fake_run)

    started = manager.start_local_services()

    assert started["ok"] is True
    assert len(started["patched_files"]) == 3
    assert any(path.endswith("astrostudyboot.jar") for path in started["patched_files"])


def test_start_runtime_skips_windows_jar_patch_when_services_are_already_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = create_windows_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_platform="win32-x64",
    )
    manager = HorosaRuntimeManager(settings)
    monkeypatch.setattr(
        manager,
        "_compile_windows_runtime_patch_classes",
        lambda manifest, jar_path: {
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory.class": b"class-bytes",
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory$LocalCache.class": b"class-bytes",
        },
    )
    manager.install(archive=str(archive))
    monkeypatch.setattr("horosa_skill.runtime.manager.os.name", "nt", raising=False)

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
        ]

    manager._service_status = MethodType(fake_service_status, manager)
    monkeypatch.setattr(
        manager,
        "_apply_runtime_overrides",
        lambda manifest: (_ for _ in ()).throw(AssertionError("should not patch a running runtime")),
    )

    started = manager.start_local_services()

    assert started["ok"] is True
    assert started["already_running"] is True


def test_start_runtime_sets_windows_home_env_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = create_windows_runtime_archive(tmp_path)
    home_root = tmp_path / "isolated-home"
    settings = Settings(
        data_dir=home_root / ".horosa-skill",
        runtime_root=home_root / ".horosa" / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_platform="win32-x64",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    monkeypatch.setattr(
        manager,
        "_compile_windows_runtime_patch_classes",
        lambda manifest, jar_path: {
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory.class": b"class-bytes",
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory$LocalCache.class": b"class-bytes",
        },
    )
    manager.install(archive=str(archive))

    monkeypatch.setattr("horosa_skill.runtime.manager.os.name", "nt", raising=False)
    monkeypatch.setattr(manager, "_apply_runtime_overrides", lambda manifest: [])
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": False},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
        ]

    captured_env: dict[str, str] = {}

    def fake_run_start_command(
        self: HorosaRuntimeManager,
        *,
        command: list[str],
        script: Path,
        env: dict[str, str],
        manifest: dict | None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        captured_env.update(env)
        return (
            subprocess.CompletedProcess(args=command, returncode=0, stdout="ok", stderr=""),
            {
                "ready": True,
                "endpoints": [
                    {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
                    {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
                ],
            },
        )

    manager._service_status = MethodType(fake_service_status, manager)
    manager._run_start_command = MethodType(fake_run_start_command, manager)

    started = manager.start_local_services()

    assert started["ok"] is True
    assert captured_env["HOME"] == str(home_root)
    assert captured_env["USERPROFILE"] == str(home_root)


def test_start_runtime_serializes_concurrent_calls(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    service_state = {"running": False}
    entered = threading.Event()
    release = threading.Event()
    run_start_calls: list[str] = []

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": service_state["running"]},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": service_state["running"]},
        ]

    def fake_run_start_command(
        self: HorosaRuntimeManager,
        *,
        command: list[str],
        script: Path,
        env: dict[str, str],
        manifest: dict | None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        run_start_calls.append("start")
        entered.set()
        release.wait(timeout=2)
        service_state["running"] = True
        return (
            subprocess.CompletedProcess(args=command, returncode=0, stdout="ok", stderr=""),
            {
                "ready": True,
                "endpoints": [
                    {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
                    {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
                ],
            },
        )

    manager._service_status = MethodType(fake_service_status, manager)
    manager._run_start_command = MethodType(fake_run_start_command, manager)

    background_result: dict[str, object] = {}

    def _background_start() -> None:
        background_result.update(manager.start_local_services())

    thread = threading.Thread(target=_background_start)
    thread.start()
    assert entered.wait(timeout=1)

    foreground_done = threading.Event()
    foreground_result: dict[str, object] = {}

    def _foreground_start() -> None:
        foreground_result.update(manager.start_local_services())
        foreground_done.set()

    waiter = threading.Thread(target=_foreground_start)
    waiter.start()
    assert not foreground_done.wait(timeout=0.1)

    release.set()
    thread.join(timeout=2)
    waiter.join(timeout=2)

    assert background_result["ok"] is True
    assert foreground_result["ok"] is True
    assert foreground_result["already_running"] is True
    assert run_start_calls == ["start"]


def test_repo_windows_start_template_bootstraps_python_paths() -> None:
    template = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "runtime_templates"
        / "windows"
        / "start_horosa_local.ps1"
    )

    content = template.read_text(encoding="utf-8")

    assert "runpy.run_path" in content
    assert 'Set-Content -LiteralPath $PyBootstrapPath' in content
    assert '-ArgumentList @($PyBootstrapPath)' in content
    assert "$env:HOME" in content
    assert "$env:USERPROFILE" in content
    assert "PYTHONIOENCODING" in content
    assert '-ArgumentList "-c", $PyBootCode' not in content


def test_repo_windows_runtime_java_template_exists() -> None:
    template = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "runtime_templates"
        / "windows"
        / "java"
        / "horosa"
        / "offline"
        / "LocalCacheFactory.java"
    )

    content = template.read_text(encoding="utf-8")

    assert "class LocalCacheFactory" in content
    assert "needMemCache" in content
