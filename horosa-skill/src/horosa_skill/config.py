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

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = _default_home_dir()
        db_path_env = os.environ.get("HOROSA_SKILL_DB_PATH")
        output_dir_env = os.environ.get("HOROSA_SKILL_OUTPUT_DIR")
        return cls(
            server_root=os.environ.get("HOROSA_SERVER_ROOT", "http://127.0.0.1:9999"),
            chart_server_root=os.environ.get("HOROSA_CHART_SERVER_ROOT", "http://127.0.0.1:8899"),
            db_path=Path(db_path_env) if db_path_env else data_dir / "memory.db",
            output_dir=Path(output_dir_env) if output_dir_env else data_dir / "runs",
            runtime_root=Path(os.environ.get("HOROSA_RUNTIME_ROOT", str(_default_runtime_root()))),
            runtime_manifest_url=os.environ.get("HOROSA_RUNTIME_MANIFEST_URL"),
            runtime_platform=os.environ.get("HOROSA_RUNTIME_PLATFORM"),
            runtime_release_repo=os.environ.get("HOROSA_RUNTIME_RELEASE_REPO", DEFAULT_RELEASE_REPO),
            local_backend_port=int(os.environ.get("HOROSA_LOCAL_BACKEND_PORT", "9999")),
            local_chart_port=int(os.environ.get("HOROSA_LOCAL_CHART_PORT", "8899")),
            runtime_start_timeout_seconds=float(os.environ.get("HOROSA_RUNTIME_START_TIMEOUT_SECONDS", "15")),
            js_engine_timeout_seconds=float(os.environ.get("HOROSA_JS_ENGINE_TIMEOUT_SECONDS", "60")),
            host=os.environ.get("HOROSA_SKILL_HOST", "127.0.0.1"),
            port=int(os.environ.get("HOROSA_SKILL_PORT", "8765")),
            log_level=os.environ.get("HOROSA_SKILL_LOG_LEVEL", "INFO"),
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        assert self.db_path is not None
        assert self.output_dir is not None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def runtime_current_dir(self) -> Path:
        return self.runtime_root / "current"

    @property
    def runtime_state_path(self) -> Path:
        return self.runtime_root / "runtime-state.json"

    @property
    def default_runtime_manifest_url(self) -> str:
        return f"https://github.com/{self.runtime_release_repo}/releases/latest/download/runtime-manifest.json"
