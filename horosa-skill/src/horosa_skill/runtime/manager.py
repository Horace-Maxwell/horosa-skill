from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.errors import RuntimeInstallError, RuntimeValidationError
from horosa_skill.tracing import TraceRecorder


def _platform_key() -> str:
    machine = platform.machine().lower()
    if sys_platform := platform.system().lower():
        if sys_platform == "darwin":
            if "arm" in machine:
                return "darwin-arm64"
            return "darwin-x64"
        if sys_platform == "windows":
            if "arm" in machine:
                return "win32-arm64"
            return "win32-x64"
        if sys_platform == "linux":
            if "arm" in machine:
                return "linux-arm64"
            return "linux-x64"
    return f"{sys_platform}-{machine}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https", "file"}


class HorosaRuntimeManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.runtime_root = settings.runtime_root
        self.current_dir = settings.runtime_current_dir
        self.tracer = TraceRecorder(settings)

    def load_installed_manifest(self, *, strict: bool = False) -> dict[str, Any] | None:
        manifest_path = self.current_dir / "runtime-manifest.json"
        if not manifest_path.is_file():
            return None
        try:
            manifest = self._normalize_manifest_data(
                json.loads(manifest_path.read_text(encoding="utf-8")),
                manifest_path=manifest_path,
            )
        except (OSError, json.JSONDecodeError, RuntimeValidationError) as exc:
            if strict:
                if isinstance(exc, RuntimeValidationError):
                    raise
                raise RuntimeValidationError(
                    "Installed runtime manifest is invalid.",
                    code="runtime.manifest_invalid",
                    details={"manifest_path": str(manifest_path), "error": str(exc)},
                ) from exc
            return None
        return manifest

    def load_runtime_state(self, *, strict: bool = False) -> dict[str, Any] | None:
        if not self.settings.runtime_state_path.is_file():
            return None
        try:
            payload = json.loads(self.settings.runtime_state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            if strict:
                raise RuntimeValidationError(
                    "Runtime state file is invalid.",
                    code="runtime.state_invalid",
                    details={"path": str(self.settings.runtime_state_path), "error": str(exc)},
                ) from exc
            return None
        if not isinstance(payload, dict):
            if strict:
                raise RuntimeValidationError(
                    "Runtime state file must contain an object.",
                    code="runtime.state_invalid",
                    details={"path": str(self.settings.runtime_state_path)},
                )
            return None
        return payload

    def install(
        self,
        *,
        archive: str | None = None,
        manifest_url: str | None = None,
        platform_key: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        with self.tracer.span(
            workflow_name="runtime.install",
            metadata={"entrypoint": "runtime.install", "archive": archive, "manifest_url": manifest_url, "force": force},
        ) as trace:
            platform_name = platform_key or self.settings.runtime_platform or _platform_key()
            source = archive
            expected_sha256: str | None = None
            asset_meta: dict[str, Any] | None = None
            manifest_data: dict[str, Any] | None = None

            if source is None:
                manifest_location = manifest_url or self.settings.runtime_manifest_url
                if not manifest_location:
                    manifest_location = self.settings.default_runtime_manifest_url
                manifest_data = self._read_json_location(manifest_location)
                platforms = manifest_data.get("platforms", {})
                asset_meta = platforms.get(platform_name)
                if not isinstance(asset_meta, dict):
                    raise RuntimeInstallError(
                        f"Runtime manifest does not include platform `{platform_name}`.",
                        code="runtime.install_missing_platform",
                        details={"platform": platform_name, "manifest_url": manifest_location},
                    )
                source = str(asset_meta.get("url") or "").strip()
                expected_sha256 = str(asset_meta.get("sha256") or "").strip() or None
                if not source:
                    raise RuntimeInstallError(
                        f"Runtime asset URL missing for platform `{platform_name}`.",
                        code="runtime.install_missing_url",
                        details={"platform": platform_name, "manifest_url": manifest_location},
                    )

            self.runtime_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="horosa-runtime-install-") as temp_dir_raw:
                temp_dir = Path(temp_dir_raw)
                archive_path = self._materialize_archive(source, temp_dir)
                if expected_sha256 and _sha256_file(archive_path).lower() != expected_sha256.lower():
                    raise RuntimeValidationError(
                        "Runtime archive checksum mismatch.",
                        code="runtime.install_sha256_mismatch",
                        details={"archive": str(archive_path), "expected_sha256": expected_sha256},
                    )

                extract_dir = temp_dir / "extract"
                extract_dir.mkdir(parents=True, exist_ok=True)
                self._extract_archive(archive_path, extract_dir)
                payload_root = self._locate_payload_root(extract_dir)
                manifest = self._validate_payload_root(payload_root)
                (payload_root / "runtime-manifest.json").write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

                previous_dir = self.runtime_root / "previous"
                if previous_dir.exists():
                    shutil.rmtree(previous_dir)
                if self.current_dir.exists():
                    if not force:
                        current_manifest = self.load_installed_manifest()
                        if current_manifest == manifest:
                            return {
                                "ok": True,
                                "installed": True,
                                "changed": False,
                                "platform": platform_name,
                                "runtime_root": str(self.runtime_root),
                                "current_dir": str(self.current_dir),
                                "manifest": manifest,
                                "trace_id": trace["trace_id"],
                                "group_id": trace["group_id"],
                            }
                    self.current_dir.replace(previous_dir)

                target_parent = self.current_dir.parent
                target_parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(payload_root), str(self.current_dir))
                if previous_dir.exists():
                    shutil.rmtree(previous_dir)

            trace["platform"] = platform_name
            trace["manifest_version"] = manifest.get("version")
            return {
                "ok": True,
                "installed": True,
                "changed": True,
                "platform": platform_name,
                "runtime_root": str(self.runtime_root),
                "current_dir": str(self.current_dir),
                "manifest": manifest,
                "asset": asset_meta or {},
                "release_manifest": manifest_data or {},
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
            }

    def doctor(self) -> dict[str, Any]:
        with self.tracer.span(workflow_name="runtime.doctor", metadata={"entrypoint": "runtime.doctor"}) as trace:
            manifest_issue: dict[str, Any] | None = None
            runtime_state_issue: dict[str, Any] | None = None
            installed = self.current_dir.exists()
            try:
                manifest = self.load_installed_manifest(strict=True)
            except RuntimeValidationError as exc:
                manifest = None
                manifest_issue = {"code": exc.code, "message": str(exc), "details": exc.details}
            try:
                runtime_state = self.load_runtime_state(strict=True)
            except RuntimeValidationError as exc:
                runtime_state = None
                runtime_state_issue = {"code": exc.code, "message": str(exc), "details": exc.details}
            required = [(label, path, kind, True) for label, path, kind in self._required_paths(manifest)]
            optional = self._optional_paths(manifest)
            files = []
            for label, relative_path, kind, required_flag in [*required, *optional]:
                absolute = self.current_dir / relative_path
                exists = absolute.is_dir() if kind == "dir" else absolute.is_file()
                files.append(
                    {
                        "label": label,
                        "path": str(absolute),
                        "exists": exists,
                        "required": required_flag,
                    }
                )

            python_path = self._relative_manifest_path(manifest, "runtimes", "python")
            java_path = self._relative_manifest_path(manifest, "runtimes", "java")
            start_script = self._relative_manifest_path(manifest, "services", "start_script")
            stop_script = self._relative_manifest_path(manifest, "services", "stop_script")
            endpoints = self._service_status(manifest)

            issues = []
            if manifest_issue:
                issues.append(manifest_issue["code"])
            if runtime_state_issue:
                issues.append(runtime_state_issue["code"])
            for entry in files:
                if not entry["exists"]:
                    issues.append(f"missing:{entry['label']}")
            if installed and not self._all_services_reachable(endpoints):
                issues.append("services:not_running")

            trace["issues"] = issues
            return {
                "ok": not issues,
                "installed": installed,
                "platform": self.settings.runtime_platform or _platform_key(),
                "runtime_root": str(self.runtime_root),
                "current_dir": str(self.current_dir),
                "manifest": manifest,
                "manifest_issue": manifest_issue,
                "runtime_state": runtime_state,
                "runtime_state_issue": runtime_state_issue,
                "paths": {
                    "python": str(self.current_dir / python_path),
                    "java": str(self.current_dir / java_path),
                    "node": str(self.current_dir / self._relative_manifest_path(manifest, "runtimes", "node")),
                    "start_script": str(self.current_dir / start_script),
                    "stop_script": str(self.current_dir / stop_script),
                },
                "files": files,
                "endpoints": endpoints,
                "issues": issues,
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
            }

    def start_local_services(self) -> dict[str, Any]:
        with self.tracer.span(workflow_name="runtime.start", metadata={"entrypoint": "runtime.start"}) as trace:
            self._require_runtime()
            manifest = self.load_installed_manifest(strict=True)
            script = self.current_dir / self._relative_manifest_path(manifest, "services", "start_script")
            if not script.exists():
                raise RuntimeValidationError(
                    f"Runtime start script missing: {script}",
                    code="runtime.start_script_missing",
                    details={"path": str(script)},
                )

            initial_status = self._service_status(manifest)
            if self._all_services_reachable(initial_status):
                if self.load_runtime_state() is None:
                    self._write_runtime_state(
                        {
                            "managed": False,
                            "status": "already_running",
                            "updated_at": self._utc_now(),
                            "manifest_version": manifest.get("version") if manifest else None,
                            "platform": manifest.get("platform") if manifest else (self.settings.runtime_platform or _platform_key()),
                        }
                    )
                return {
                    "ok": True,
                    "already_running": True,
                    "command": None,
                    "stdout": "",
                    "stderr": "",
                    "endpoints": initial_status,
                    "trace_id": trace["trace_id"],
                    "group_id": trace["group_id"],
                }

            env = os.environ.copy()
            env.setdefault("HOROSA_SERVER_PORT", str(self.settings.local_backend_port))
            env.setdefault("HOROSA_CHART_PORT", str(self.settings.local_chart_port))

            command = self._platform_command(script)
            completed = subprocess.run(
                command,
                cwd=str(script.parent),
                env=env,
                capture_output=True,
                text=True,
            )
            readiness = self._wait_for_service_state(
                expected_reachable=True,
                timeout_seconds=self.settings.runtime_start_timeout_seconds,
                manifest=manifest,
            )
            startup_warning: dict[str, Any] | None = None
            if completed.returncode != 0 and readiness["ready"]:
                startup_warning = {
                    "code": "runtime.start_nonzero_but_ready",
                    "message": "Runtime start script exited non-zero, but all required services became reachable.",
                    "details": {
                        "command": command,
                        "returncode": completed.returncode,
                        "stdout": completed.stdout[-4000:],
                        "stderr": completed.stderr[-4000:],
                    },
                }
            elif completed.returncode != 0:
                raise RuntimeInstallError(
                    "Failed to start local Horosa runtime.",
                    code="runtime.start_failed",
                    details={
                        "command": command,
                        "stdout": completed.stdout[-4000:],
                        "stderr": completed.stderr[-4000:],
                        "endpoints": readiness["endpoints"],
                    },
                )
            if not readiness["ready"]:
                raise RuntimeInstallError(
                    "Local Horosa runtime did not become ready in time.",
                    code="runtime.start_timeout",
                    details={
                        "command": command,
                        "timeout_seconds": self.settings.runtime_start_timeout_seconds,
                        "endpoints": readiness["endpoints"],
                    },
                )
            self._write_runtime_state(
                {
                    "managed": True,
                    "status": "running_with_warnings" if startup_warning else "running",
                    "updated_at": self._utc_now(),
                    "manifest_version": manifest.get("version") if manifest else None,
                    "platform": manifest.get("platform") if manifest else (self.settings.runtime_platform or _platform_key()),
                    "command": command,
                    "startup_warning": startup_warning,
                }
            )
            trace["command"] = command
            return {
                "ok": True,
                "already_running": False,
                "command": command,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
                "endpoints": readiness["endpoints"],
                "warning": startup_warning,
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
            }

    def stop_local_services(self) -> dict[str, Any]:
        with self.tracer.span(workflow_name="runtime.stop", metadata={"entrypoint": "runtime.stop"}) as trace:
            self._require_runtime()
            manifest = self.load_installed_manifest(strict=True)
            script = self.current_dir / self._relative_manifest_path(manifest, "services", "stop_script")
            initial_status = self._service_status(manifest)
            if not any(item["reachable"] for item in initial_status):
                self._clear_runtime_state()
                return {
                    "ok": True,
                    "already_stopped": True,
                    "command": None,
                    "stdout": "",
                    "stderr": "",
                    "returncode": 0,
                    "endpoints": initial_status,
                    "trace_id": trace["trace_id"],
                    "group_id": trace["group_id"],
                }
            if not script.exists():
                raise RuntimeValidationError(
                    f"Runtime stop script missing: {script}",
                    code="runtime.stop_script_missing",
                    details={"path": str(script)},
                )
            command = self._platform_command(script)
            completed = subprocess.run(
                command,
                cwd=str(script.parent),
                env=os.environ.copy(),
                capture_output=True,
                text=True,
            )
            shutdown = self._wait_for_service_state(
                expected_reachable=False,
                timeout_seconds=max(3.0, min(self.settings.runtime_start_timeout_seconds, 10.0)),
                manifest=manifest,
            )
            if completed.returncode == 0 and shutdown["ready"]:
                self._clear_runtime_state()
            else:
                self._write_runtime_state(
                    {
                        "managed": True,
                        "status": "stop_requested",
                        "updated_at": self._utc_now(),
                        "manifest_version": manifest.get("version") if manifest else None,
                        "platform": manifest.get("platform") if manifest else (self.settings.runtime_platform or _platform_key()),
                    }
                )
            trace["command"] = command
            return {
                "ok": completed.returncode == 0 and shutdown["ready"],
                "already_stopped": False,
                "command": command,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
                "returncode": completed.returncode,
                "endpoints": shutdown["endpoints"],
                "trace_id": trace["trace_id"],
                "group_id": trace["group_id"],
            }

    def _require_runtime(self) -> None:
        if not self.current_dir.exists():
            raise RuntimeValidationError(
                "Horosa runtime is not installed.",
                code="runtime.not_installed",
                details={"current_dir": str(self.current_dir)},
            )

    def _materialize_archive(self, source: str, temp_dir: Path) -> Path:
        if _is_url(source):
            parsed = urlparse(source)
            if parsed.scheme == "file":
                return Path(parsed.path)
            filename = Path(parsed.path).name or "runtime-archive"
            target = temp_dir / filename
            with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                response = client.get(source)
                response.raise_for_status()
                target.write_bytes(response.content)
            return target
        return Path(source).expanduser().resolve()

    def _read_json_location(self, location: str) -> dict[str, Any]:
        if _is_url(location):
            parsed = urlparse(location)
            if parsed.scheme == "file":
                return json.loads(Path(parsed.path).read_text(encoding="utf-8"))
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                response = client.get(location)
                response.raise_for_status()
                return response.json()
        return json.loads(Path(location).expanduser().read_text(encoding="utf-8"))

    def _extract_archive(self, archive_path: Path, extract_dir: Path) -> None:
        name = archive_path.name.lower()
        if name.endswith(".tar.gz") or name.endswith(".tgz"):
            with tarfile.open(archive_path, "r:gz") as archive:
                archive.extractall(extract_dir, filter="data")
            return
        if name.endswith(".zip"):
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(extract_dir)
            return
        shutil.unpack_archive(str(archive_path), str(extract_dir))

    def _locate_payload_root(self, extract_dir: Path) -> Path:
        candidates = [
            extract_dir / "runtime-payload",
            extract_dir,
        ]
        for candidate in candidates:
            if (candidate / "runtime-manifest.json").is_file():
                return candidate
        for child in extract_dir.iterdir():
            if child.is_dir() and (child / "runtime-manifest.json").is_file():
                return child
        raise RuntimeValidationError(
            "Extracted runtime archive does not contain runtime-manifest.json.",
            code="runtime.install_manifest_missing",
            details={"extract_dir": str(extract_dir)},
        )

    def _manifest_defaults(self) -> dict[str, dict[str, str]]:
        return {
            "services": {
                "backend_url": self.settings.server_root.rstrip("/"),
                "chart_url": self.settings.chart_server_root.rstrip("/"),
                "start_script": str(self._platform_path("Horosa-Web/start_horosa_local.sh", "Horosa-Web/start_horosa_local.ps1")),
                "stop_script": str(self._platform_path("Horosa-Web/stop_horosa_local.sh", "Horosa-Web/stop_horosa_local.ps1")),
            },
            "runtimes": {
                "python": str(self._platform_path("runtime/mac/python/bin/python3", "runtime/windows/python/python.exe")),
                "java": str(self._platform_path("runtime/mac/java/bin/java", "runtime/windows/java/bin/java.exe")),
                "node": str(self._platform_path("runtime/mac/node/bin/node", "runtime/windows/node/node.exe")),
            },
            "artifacts": {
                "horosa_web_root": "Horosa-Web",
                "astropy_root": "Horosa-Web/astropy",
                "flatlib_root": "Horosa-Web/flatlib-ctrad2/flatlib",
                "swefiles_root": "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles",
                "boot_jar": str(self._platform_path("runtime/mac/bundle/astrostudyboot.jar", "runtime/windows/bundle/astrostudyboot.jar")),
                "horosa_core_js_root": "horosa-core-js",
            },
        }

    def _validate_payload_root(self, payload_root: Path) -> dict[str, Any]:
        manifest_path = payload_root / "runtime-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return self._normalize_manifest_data(manifest, manifest_path=manifest_path)

    def _normalize_manifest_data(self, manifest: Any, *, manifest_path: Path) -> dict[str, Any]:
        if not isinstance(manifest, dict) or "version" not in manifest:
            raise RuntimeValidationError(
                "Runtime manifest missing version.",
                code="runtime.manifest_invalid",
                details={"manifest_path": str(manifest_path)},
            )

        defaults = self._manifest_defaults()
        normalized = {
            "schema_version": int(manifest.get("schema_version", 1)),
            "version": str(manifest["version"]),
            "platform": str(manifest.get("platform") or self.settings.runtime_platform or _platform_key()),
            "runtime_layout_version": int(manifest.get("runtime_layout_version", 1)),
            "export_registry_version": int(manifest.get("export_registry_version", 6)),
            "services": {**defaults["services"], **(manifest.get("services") or {})},
            "runtimes": {**defaults["runtimes"], **(manifest.get("runtimes") or {})},
            "artifacts": {**defaults["artifacts"], **(manifest.get("artifacts") or {})},
        }
        for section_name in ("services", "runtimes", "artifacts"):
            section = normalized[section_name]
            if not isinstance(section, dict):
                raise RuntimeValidationError(
                    f"Runtime manifest section `{section_name}` must be an object.",
                    code="runtime.manifest_invalid",
                    details={"manifest_path": str(manifest_path), "section": section_name},
                )
            for key, value in section.items():
                if not isinstance(value, str) or not value.strip():
                    raise RuntimeValidationError(
                        f"Runtime manifest field `{section_name}.{key}` must be a non-empty string.",
                        code="runtime.manifest_invalid",
                        details={"manifest_path": str(manifest_path), "field": f"{section_name}.{key}"},
                    )
        return normalized

    def _platform_path(self, posix_relative: str, windows_relative: str) -> Path:
        if os.name == "nt":
            return Path(windows_relative)
        return Path(posix_relative)

    def _platform_command(self, script: Path) -> list[str]:
        if os.name == "nt":
            if script.suffix.lower() == ".ps1":
                return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
            return [str(script)]
        return ["/bin/bash", str(script)]

    def _http_reachable(self, url: str) -> bool:
        try:
            with httpx.Client(timeout=1.5, follow_redirects=True) as client:
                response = client.get(url)
                return response.status_code < 500
        except Exception:
            return False

    def _backend_reachable(self, backend_url: str) -> bool:
        parsed = urlparse(backend_url)
        if not parsed.scheme or not parsed.netloc:
            return False
        server_root = f"{parsed.scheme}://{parsed.netloc}"
        endpoint = parsed.path if parsed.path not in {"", "/"} else "/common/time"
        client = HorosaApiClient(server_root, timeout=3.0)
        return client.probe(endpoint=endpoint)

    def _required_paths(self, manifest: dict[str, Any] | None = None) -> list[tuple[str, Path, str]]:
        return [
            ("manifest", Path("runtime-manifest.json"), "file"),
            ("horosa_web", self._relative_manifest_path(manifest, "artifacts", "horosa_web_root"), "dir"),
            ("astropy", self._relative_manifest_path(manifest, "artifacts", "astropy_root"), "dir"),
            ("flatlib", self._relative_manifest_path(manifest, "artifacts", "flatlib_root"), "dir"),
            ("swefiles", self._relative_manifest_path(manifest, "artifacts", "swefiles_root"), "dir"),
            ("start_script", self._relative_manifest_path(manifest, "services", "start_script"), "file"),
            ("stop_script", self._relative_manifest_path(manifest, "services", "stop_script"), "file"),
            ("java_runtime", self._relative_manifest_path(manifest, "runtimes", "java"), "file"),
            ("python_runtime", self._relative_manifest_path(manifest, "runtimes", "python"), "file"),
            ("node_runtime", self._relative_manifest_path(manifest, "runtimes", "node"), "file"),
            ("boot_jar", self._relative_manifest_path(manifest, "artifacts", "boot_jar"), "file"),
            ("horosa_core_js_root", self._relative_manifest_path(manifest, "artifacts", "horosa_core_js_root"), "dir"),
        ]

    def _optional_paths(self, manifest: dict[str, Any] | None = None) -> list[tuple[str, Path, str, bool]]:
        return []

    def _relative_manifest_path(self, manifest: dict[str, Any] | None, section: str, key: str) -> Path:
        if manifest and isinstance(manifest.get(section), dict):
            value = manifest[section].get(key)
            if isinstance(value, str) and value.strip():
                return Path(value)
        defaults = self._manifest_defaults()
        return Path(defaults[section][key])

    def _service_status(self, manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
        backend_url = self.settings.server_root.rstrip("/")
        chart_url = self.settings.chart_server_root.rstrip("/")
        if manifest and isinstance(manifest.get("services"), dict):
            backend_url = str(manifest["services"].get("backend_url") or backend_url)
            chart_url = str(manifest["services"].get("chart_url") or chart_url)
        backend_probe = backend_url
        parsed_backend = urlparse(backend_url)
        if parsed_backend.scheme and parsed_backend.netloc and parsed_backend.path in {"", "/"}:
            backend_probe = backend_url.rstrip("/") + "/common/time"
        return [
            {"label": "java_backend", "url": backend_probe, "reachable": self._backend_reachable(backend_probe)},
            {"label": "python_chart", "url": chart_url, "reachable": self._http_reachable(chart_url)},
        ]

    def _all_services_reachable(self, endpoints: list[dict[str, Any]]) -> bool:
        return bool(endpoints) and all(bool(item.get("reachable")) for item in endpoints)

    def _wait_for_service_state(
        self,
        *,
        expected_reachable: bool,
        timeout_seconds: float,
        manifest: dict[str, Any] | None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + max(timeout_seconds, 0.1)
        endpoints = self._service_status(manifest)
        while time.monotonic() < deadline:
            if all(item["reachable"] == expected_reachable for item in endpoints):
                return {"ready": True, "endpoints": endpoints}
            time.sleep(0.25)
            endpoints = self._service_status(manifest)
        return {"ready": all(item["reachable"] == expected_reachable for item in endpoints), "endpoints": endpoints}

    def _write_runtime_state(self, payload: dict[str, Any]) -> None:
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.settings.runtime_state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _clear_runtime_state(self) -> None:
        if self.settings.runtime_state_path.exists():
            self.settings.runtime_state_path.unlink()

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat()
