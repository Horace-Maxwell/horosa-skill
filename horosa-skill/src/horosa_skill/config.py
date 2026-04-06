from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_RELEASE_REPO = "Horace-Maxwell/horosa-skill"


def _default_home_dir() -> Path:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "HorosaSkill"
    return Path.home() / ".horosa-skill"


def _default_runtime_root() -> Path:
    if os.name == "nt":
        local_appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if local_appdata:
            return Path(local_appdata) / "Horosa" / "runtime"
    return Path.home() / ".horosa" / "runtime"


def _env_text(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


def _env_path(name: str, default: Path) -> Path:
    raw_value = _env_text(name)
    if raw_value is None:
        return default
    return Path(raw_value).expanduser()


def _env_int(name: str, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    raw_value = _env_text(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    if minimum is not None and value < minimum:
        return default
    if maximum is not None and value > maximum:
        return default
    return value


def _env_float(name: str, default: float, *, minimum: float | None = None) -> float:
    raw_value = _env_text(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError:
        return default
    if minimum is not None and value < minimum:
        return default
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw_value = _env_text(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


class Settings(BaseModel):
    server_root: str = Field(default="http://127.0.0.1:9999")
    chart_server_root: str = Field(default="http://127.0.0.1:8899")
    data_dir: Path = Field(default_factory=_default_home_dir)
    runtime_root: Path = Field(default_factory=_default_runtime_root)
    db_path: Path | None = None
    output_dir: Path | None = None
    runtime_manifest_url: str | None = None
    runtime_platform: str | None = None
    runtime_release_repo: str = DEFAULT_RELEASE_REPO
    local_backend_port: int = 9999
    local_chart_port: int = 8899
    runtime_start_timeout_seconds: float = 15.0
    js_engine_timeout_seconds: float = 60.0
    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "INFO"
    trace_enabled: bool = True
    trace_dir: Path | None = None
    trace_capture_payloads: bool = False
    trace_capture_ai_answers: bool = False
    trace_otlp_endpoint: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = _env_path("HOROSA_SKILL_DATA_DIR", _default_home_dir())
        db_path_env = _env_text("HOROSA_SKILL_DB_PATH")
        output_dir_env = _env_text("HOROSA_SKILL_OUTPUT_DIR")
        trace_dir_env = _env_text("HOROSA_TRACE_DIR")
        return cls(
            server_root=_env_text("HOROSA_SERVER_ROOT", "http://127.0.0.1:9999") or "http://127.0.0.1:9999",
            chart_server_root=_env_text("HOROSA_CHART_SERVER_ROOT", "http://127.0.0.1:8899") or "http://127.0.0.1:8899",
            data_dir=data_dir,
            db_path=Path(db_path_env).expanduser() if db_path_env else data_dir / "memory.db",
            output_dir=Path(output_dir_env).expanduser() if output_dir_env else data_dir / "runs",
            runtime_root=_env_path("HOROSA_RUNTIME_ROOT", _default_runtime_root()),
            runtime_manifest_url=_env_text("HOROSA_RUNTIME_MANIFEST_URL"),
            runtime_platform=_env_text("HOROSA_RUNTIME_PLATFORM"),
            runtime_release_repo=_env_text("HOROSA_RUNTIME_RELEASE_REPO", DEFAULT_RELEASE_REPO) or DEFAULT_RELEASE_REPO,
            local_backend_port=_env_int("HOROSA_LOCAL_BACKEND_PORT", 9999, minimum=1, maximum=65535),
            local_chart_port=_env_int("HOROSA_LOCAL_CHART_PORT", 8899, minimum=1, maximum=65535),
            runtime_start_timeout_seconds=_env_float("HOROSA_RUNTIME_START_TIMEOUT_SECONDS", 15.0, minimum=0.1),
            js_engine_timeout_seconds=_env_float("HOROSA_JS_ENGINE_TIMEOUT_SECONDS", 60.0, minimum=0.1),
            host=_env_text("HOROSA_SKILL_HOST", "127.0.0.1") or "127.0.0.1",
            port=_env_int("HOROSA_SKILL_PORT", 8765, minimum=1, maximum=65535),
            log_level=(_env_text("HOROSA_SKILL_LOG_LEVEL", "INFO") or "INFO").upper(),
            trace_enabled=_env_bool("HOROSA_TRACE_ENABLED", True),
            trace_dir=Path(trace_dir_env).expanduser() if trace_dir_env else data_dir / "traces",
            trace_capture_payloads=_env_bool("HOROSA_TRACE_CAPTURE_PAYLOADS", False),
            trace_capture_ai_answers=_env_bool("HOROSA_TRACE_CAPTURE_AI_ANSWERS", False),
            trace_otlp_endpoint=_env_text("HOROSA_TRACE_OTLP_ENDPOINT"),
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        assert self.db_path is not None
        assert self.output_dir is not None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.trace_dir is not None:
            self.trace_dir.mkdir(parents=True, exist_ok=True)

    @property
    def runtime_current_dir(self) -> Path:
        return self.runtime_root / "current"

    @property
    def runtime_state_path(self) -> Path:
        return self.runtime_root / "runtime-state.json"

    @property
    def default_runtime_manifest_url(self) -> str:
        return f"https://github.com/{self.runtime_release_repo}/releases/latest/download/runtime-manifest.json"
