from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import url2pathname

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


WINDOWS_LOCAL_CACHE_FACTORY = "horosa.offline.LocalCacheFactory"
WINDOWS_LOCAL_CACHE_CONFIG = "offline"
WINDOWS_BOOT_CACHE_CONFIG_PATH = "BOOT-INF/classes/conf/properties/cache/caches.json"
WINDOWS_BOOT_WEBPARAMS_PATH = "BOOT-INF/classes/conf/properties/param/webparams.properties"
WINDOWS_BOOT_LOG4J_PATH = "BOOT-INF/classes/log4j2.xml"
WINDOWS_BOOT_BOUNDLESS_PREFIX = "BOOT-INF/lib/boundless-"


class HorosaRuntimeManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.runtime_root = settings.runtime_root
        self.current_dir = settings.runtime_current_dir
        self.tracer = TraceRecorder(settings)
        self._service_lock = threading.Lock()

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
                self._apply_runtime_overrides(manifest)
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
        with self._service_lock:
            with self.tracer.span(workflow_name="runtime.start", metadata={"entrypoint": "runtime.start"}) as trace:
                self._require_runtime()
                manifest = self.load_installed_manifest(strict=True)
                patched_files: list[str] = []
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

                recovered_partial_state = False
                recovery_details: dict[str, Any] | None = None
                if self._any_services_reachable(initial_status):
                    recovery_details = self.stop_local_services()
                    recovered_partial_state = True

                patched_files = self._apply_runtime_overrides(manifest)
                script = self.current_dir / self._relative_manifest_path(manifest, "services", "start_script")
                if not script.exists():
                    raise RuntimeValidationError(
                        f"Runtime start script missing: {script}",
                        code="runtime.start_script_missing",
                        details={"path": str(script)},
                    )

                env = os.environ.copy()
                env.setdefault("HOROSA_SERVER_PORT", str(self.settings.local_backend_port))
                env.setdefault("HOROSA_CHART_PORT", str(self.settings.local_chart_port))
                home_value = self._default_home_value()
                env.setdefault("HOME", home_value)
                if os.name == "nt":
                    env.setdefault("USERPROFILE", home_value)
                    drive, tail = os.path.splitdrive(home_value)
                    if drive:
                        env.setdefault("HOMEDRIVE", drive)
                        env.setdefault("HOMEPATH", tail or "\\")

                command = self._platform_command(script)
                completed, readiness = self._run_start_command(
                    command=command,
                    script=script,
                    env=env,
                    manifest=manifest,
                )
                retried_after_cleanup = False
                combined_output = f"{completed.stdout}\n{completed.stderr}".lower()
                if (
                    completed.returncode != 0
                    and not readiness["ready"]
                    and (
                        self._any_services_reachable(readiness["endpoints"])
                        or "pid files already exist" in combined_output
                    )
                ):
                    recovery_details = self.stop_local_services()
                    recovered_partial_state = True
                    retried_after_cleanup = True
                    completed, readiness = self._run_start_command(
                        command=command,
                        script=script,
                        env=env,
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
                            "retried_after_cleanup": retried_after_cleanup,
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
                        "recovered_partial_state": recovered_partial_state,
                    }
                )
                trace["command"] = command
                trace["patched_files"] = patched_files
                return {
                    "ok": True,
                    "already_running": False,
                    "command": command,
                    "stdout": completed.stdout[-4000:],
                    "stderr": completed.stderr[-4000:],
                    "endpoints": readiness["endpoints"],
                    "warning": startup_warning,
                    "patched_files": patched_files,
                    "recovered_partial_state": recovered_partial_state,
                    "recovery": recovery_details,
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
                return self._file_url_to_path(source)
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
                return json.loads(self._file_url_to_path(location).read_text(encoding="utf-8"))
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                response = client.get(location)
                response.raise_for_status()
                return response.json()
        return json.loads(Path(location).expanduser().read_text(encoding="utf-8"))

    def _file_url_to_path(self, location: str) -> Path:
        parsed = urlparse(location)
        path_text = url2pathname(parsed.path or "")
        if parsed.netloc and parsed.netloc not in {"", "localhost"}:
            if os.name == "nt":
                path_text = f"\\\\{parsed.netloc}{path_text}"
            else:
                path_text = f"//{parsed.netloc}{path_text}"
        elif os.name == "nt" and path_text.startswith("\\") and len(path_text) >= 3 and path_text[2] == ":":
            path_text = path_text[1:]
        return Path(path_text)

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

    def _apply_runtime_overrides(self, manifest: dict[str, Any] | None) -> list[str]:
        if os.name != "nt":
            return []
        template_root = self._runtime_template_root() / "windows"
        patched: list[str] = []
        if template_root.exists():
            overrides = {
                "services.start_script": template_root / "start_horosa_local.ps1",
                "services.stop_script": template_root / "stop_horosa_local.ps1",
            }
            for field, source in overrides.items():
                if not source.exists():
                    continue
                section, key = field.split(".", 1)
                destination = self.current_dir / self._relative_manifest_path(manifest, section, key)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                patched.append(str(destination))

        boot_jar = self.current_dir / self._relative_manifest_path(manifest, "artifacts", "boot_jar")
        if boot_jar.is_file():
            self._patch_windows_boot_jar(manifest, boot_jar)
            patched.append(str(boot_jar))
        return patched

    def _runtime_template_root(self) -> Path:
        return Path(__file__).resolve().parents[3] / "scripts" / "runtime_templates"

    def _patch_windows_boot_jar(self, manifest: dict[str, Any] | None, jar_path: Path) -> None:
        replacements = {
            WINDOWS_BOOT_CACHE_CONFIG_PATH: self._rewrite_windows_cache_config(
                self._read_archive_entry_text(jar_path, WINDOWS_BOOT_CACHE_CONFIG_PATH)
            ).encode("utf-8"),
            WINDOWS_BOOT_WEBPARAMS_PATH: self._rewrite_windows_webparams(
                self._read_archive_entry_text(jar_path, WINDOWS_BOOT_WEBPARAMS_PATH)
            ).encode("utf-8"),
            WINDOWS_BOOT_LOG4J_PATH: self._rewrite_windows_log4j(
                self._read_archive_entry_text(jar_path, WINDOWS_BOOT_LOG4J_PATH)
            ).encode("utf-8"),
            **self._compile_windows_runtime_patch_classes(manifest, jar_path),
        }
        self._rewrite_zip_archive(jar_path, replacements)

    def _read_archive_entry_text(self, archive_path: Path, entry_name: str) -> str:
        try:
            with zipfile.ZipFile(archive_path) as archive:
                return archive.read(entry_name).decode("utf-8")
        except KeyError as exc:
            raise RuntimeValidationError(
                f"Runtime archive is missing `{entry_name}`.",
                code="runtime.windows_patch_missing_entry",
                details={"archive": str(archive_path), "entry": entry_name},
            ) from exc
        except (OSError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
            raise RuntimeValidationError(
                "Runtime archive could not be patched for Windows local mode.",
                code="runtime.windows_patch_invalid_archive",
                details={"archive": str(archive_path), "entry": entry_name, "error": str(exc)},
            ) from exc

    def _rewrite_windows_cache_config(self, content: str) -> str:
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise RuntimeValidationError(
                "Windows cache override expects an object.",
                code="runtime.windows_patch_invalid_cache_config",
            )
        entries = payload.get("cachefactoryclass")
        if not isinstance(entries, list) or not entries:
            raise RuntimeValidationError(
                "Windows cache override expects `cachefactoryclass` to be a non-empty array.",
                code="runtime.windows_patch_invalid_cache_config",
            )
        rewritten: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise RuntimeValidationError(
                    "Windows cache override expects every cache entry to be an object.",
                    code="runtime.windows_patch_invalid_cache_config",
                )
            patched = dict(entry)
            patched["class"] = WINDOWS_LOCAL_CACHE_FACTORY
            patched["config"] = WINDOWS_LOCAL_CACHE_CONFIG
            rewritten.append(patched)
        payload["needlocalmemcache"] = False
        payload["needcompress"] = False
        payload["needhystrix"] = False
        payload["cachefactoryclass"] = rewritten
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    def _rewrite_windows_webparams(self, content: str) -> str:
        updated = re.sub(
            r"(?m)^webencrypt\.rsaparam\.class=.*$",
            "webencrypt.rsaparam.class=",
            content,
        )
        if "webencrypt.rsaparam.class=" not in updated:
            updated = updated.rstrip("\n") + "\nwebencrypt.rsaparam.class=\n"
        if not updated.endswith("\n"):
            updated += "\n"
        return updated

    def _rewrite_windows_log4j(self, content: str) -> str:
        log_root = self._windows_log_root()
        replaced = False

        def apply_basedir(match: re.Match[str]) -> str:
            nonlocal replaced
            replaced = True
            return f"{match.group(1)}{log_root}{match.group(2)}"

        updated = re.sub(
            r'(<Property\s+name="basedir">).*?(</Property>)',
            apply_basedir,
            content,
            count=1,
            flags=re.DOTALL,
        )
        if replaced:
            return updated
        if updated == content:
            updated = updated.replace("${env:HOME}/.horosa-logs/astrostudyboot", log_root)
            if updated != content:
                return updated
        raise RuntimeValidationError(
            "Windows log override could not locate the backend log root property.",
            code="runtime.windows_patch_invalid_log4j",
        )

    def _windows_log_root(self) -> str:
        home_value = self._default_home_value().rstrip("\\/")
        return home_value.replace("\\", "/") + "/.horosa-logs/astrostudyboot"

    def _compile_windows_runtime_patch_classes(
        self,
        manifest: dict[str, Any] | None,
        jar_path: Path,
    ) -> dict[str, bytes]:
        source_root = self._runtime_template_root() / "windows" / "java"
        source_path = source_root / "horosa" / "offline" / "LocalCacheFactory.java"
        if not source_path.is_file():
            raise RuntimeValidationError(
                "Windows runtime patch source is missing.",
                code="runtime.windows_patch_missing_source",
                details={"path": str(source_path)},
            )

        java_path = self.current_dir / self._relative_manifest_path(manifest, "runtimes", "java")
        javac_path = java_path.with_name("javac.exe")
        if not javac_path.is_file():
            raise RuntimeValidationError(
                "Windows runtime patch requires `javac.exe` in the bundled Java runtime.",
                code="runtime.windows_patch_missing_javac",
                details={"path": str(javac_path)},
            )

        with tempfile.TemporaryDirectory(prefix="horosa-runtime-java-") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            boundless_jar = temp_dir / "boundless.jar"
            self._extract_boot_lib(jar_path, WINDOWS_BOOT_BOUNDLESS_PREFIX, boundless_jar)

            classes_dir = temp_dir / "classes"
            classes_dir.mkdir(parents=True, exist_ok=True)
            compiled = subprocess.run(
                [
                    str(javac_path),
                    "-encoding",
                    "UTF-8",
                    "-cp",
                    str(boundless_jar),
                    "-d",
                    str(classes_dir),
                    str(source_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if compiled.returncode != 0:
                raise RuntimeInstallError(
                    "Failed to compile the Windows local-cache compatibility classes.",
                    code="runtime.windows_patch_compile_failed",
                    details={
                        "javac": str(javac_path),
                        "source": str(source_path),
                        "stdout": compiled.stdout[-4000:],
                        "stderr": compiled.stderr[-4000:],
                    },
                )

            entries: dict[str, bytes] = {}
            for class_file in classes_dir.rglob("*.class"):
                arcname = f"BOOT-INF/classes/{class_file.relative_to(classes_dir).as_posix()}"
                entries[arcname] = class_file.read_bytes()
            if not entries:
                raise RuntimeValidationError(
                    "Windows runtime patch did not produce any compatibility classes.",
                    code="runtime.windows_patch_compile_failed",
                )
            return entries

    def _extract_boot_lib(self, jar_path: Path, prefix: str, target_path: Path) -> None:
        try:
            with zipfile.ZipFile(jar_path) as archive:
                for entry in archive.infolist():
                    if entry.filename.startswith(prefix) and entry.filename.endswith(".jar"):
                        target_path.write_bytes(archive.read(entry.filename))
                        return
        except (OSError, zipfile.BadZipFile) as exc:
            raise RuntimeValidationError(
                "Runtime archive could not be read while preparing Windows compatibility classes.",
                code="runtime.windows_patch_invalid_archive",
                details={"archive": str(jar_path), "error": str(exc)},
            ) from exc
        raise RuntimeValidationError(
            "Runtime archive does not contain the bundled `boundless` library required for Windows compatibility.",
            code="runtime.windows_patch_missing_boundless",
            details={"archive": str(jar_path)},
        )

    def _rewrite_zip_archive(self, archive_path: Path, replacements: dict[str, bytes]) -> None:
        temp_path = archive_path.with_suffix(f"{archive_path.suffix}.tmp")
        with zipfile.ZipFile(archive_path) as source, zipfile.ZipFile(temp_path, "w") as target:
            target.comment = source.comment
            seen: set[str] = set()
            for info in source.infolist():
                seen.add(info.filename)
                data = replacements.get(info.filename, source.read(info.filename))
                new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                new_info.compress_type = info.compress_type
                new_info.comment = info.comment
                new_info.extra = info.extra
                new_info.internal_attr = info.internal_attr
                new_info.external_attr = info.external_attr
                new_info.create_system = info.create_system
                new_info.flag_bits = info.flag_bits
                target.writestr(new_info, data)

            for entry_name, data in replacements.items():
                if entry_name in seen:
                    continue
                new_info = zipfile.ZipInfo(entry_name)
                new_info.compress_type = zipfile.ZIP_DEFLATED
                new_info.external_attr = 0o644 << 16
                target.writestr(new_info, data)
        temp_path.replace(archive_path)

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

    def _any_services_reachable(self, endpoints: list[dict[str, Any]]) -> bool:
        return any(bool(item.get("reachable")) for item in endpoints)

    def _run_start_command(
        self,
        *,
        command: list[str],
        script: Path,
        env: dict[str, str],
        manifest: dict[str, Any] | None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
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
        return completed, readiness

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

    def _default_home_value(self) -> str:
        home = os.environ.get("HOME", "").strip()
        if home:
            return home
        userprofile = os.environ.get("USERPROFILE", "").strip()
        if userprofile:
            return userprofile
        data_dir = self.settings.data_dir
        if data_dir.name == ".horosa-skill":
            return str(data_dir.parent)
        runtime_root = self.settings.runtime_root
        runtime_parts = [part.lower() for part in runtime_root.parts]
        if len(runtime_parts) >= 2 and runtime_parts[-1] == "runtime" and runtime_parts[-2] == ".horosa":
            return str(runtime_root.parent.parent)
        return str(Path.home())
