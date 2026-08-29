from __future__ import annotations

import logging
import os
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_RELEASE_REPO = "Horace-Maxwell/horosa-skill"

logger = logging.getLogger(__name__)

# ── env 旗标生命周期注册表（v0.33.0 批 II-1/II-3）────────────────────────────────
# 单一真值源：每个 HOROSA_* 旗标在此登记生命周期档（stable=文档化用户面 / experimental=试验 /
# internal=构建机·脚本·runtime 机务，用户一般不设 / deprecated=保留但劝退）。前向兼容纪律：
# **未知旗标 warn-and-ignore**（一次性告警，绝不硬拒——codex 0.112.0 因未知 key 硬拒配置直接
# 起不来的反面教材）；只有显式 HOROSA_STRICT_CONFIG=1 才升级为报错。removed 档=接受并忽略+
# 指路替代（删旗标不删兼容）。
ENV_FLAG_REGISTRY: dict[str, str] = {
    "HOROSA_STRICT_CONFIG": "stable",
    "HOROSA_CLARIFY": "stable",
    "HOROSA_SERVER_ROOT": "stable",
    "HOROSA_CHART_SERVER_ROOT": "stable",
    "HOROSA_SKILL_DATA_DIR": "stable",
    "HOROSA_SKILL_DB_PATH": "stable",
    "HOROSA_SKILL_OUTPUT_DIR": "stable",
    "HOROSA_RUNTIME_ROOT": "stable",
    "HOROSA_RUNTIME_MANIFEST_URL": "stable",
    "HOROSA_RUNTIME_PLATFORM": "stable",
    "HOROSA_RUNTIME_RELEASE_REPO": "stable",
    "HOROSA_RUNTIME_MIRROR": "stable",
    "HOROSA_LOCAL_BACKEND_PORT": "stable",
    "HOROSA_LOCAL_CHART_PORT": "stable",
    "HOROSA_RUNTIME_START_TIMEOUT_SECONDS": "stable",
    "HOROSA_MCP_COMPACT": "stable",
    "HOROSA_MCP_ELICIT": "stable",
    "HOROSA_TOOLSETS": "stable",
    "HOROSA_JS_ENGINE_TIMEOUT_SECONDS": "stable",
    "HOROSA_SKILL_HOST": "stable",
    "HOROSA_SKILL_PORT": "stable",
    "HOROSA_SKILL_LOG_LEVEL": "stable",
    "HOROSA_TRACE_ENABLED": "stable",
    "HOROSA_TRACE_DIR": "stable",
    "HOROSA_TRACE_CAPTURE_PAYLOADS": "stable",
    "HOROSA_TRACE_CAPTURE_AI_ANSWERS": "stable",
    "HOROSA_TRACE_OTLP_ENDPOINT": "stable",
    "HOROSA_TECHNIQUE_CARD": "stable",
    "HOROSA_OUTPUT_SCHEMA": "stable",
    "HOROSA_ASTRODATA_DB": "stable",
    "HOROSA_NODE_BIN": "stable",
    "HOROSA_CORE_JS_ROOT": "experimental",
    "HOROSA_UV_BIN": "internal",
    "HOROSA_MCPORTER_BIN": "internal",
    "HOROSA_SERVER_PORT": "internal",
    "HOROSA_CHART_PORT": "internal",
    "HOROSA_BACKEND_PORT": "internal",
    "HOROSA_ROOT": "internal",
    "HOROSA_LOG_ROOT": "internal",
    "HOROSA_SOURCE_ROOT": "internal",
    "HOROSA_WINDOWS_SOURCE_ROOT": "internal",
    "HOROSA_LINUX_JAVA_HOME": "internal",
    "HOROSA_LINUX_PYTHON_HOME": "internal",
    "HOROSA_LINUX_SKIP_DOWNLOAD": "internal",
    "HOROSA_RUNTIME_RELEASE_BASE_URL": "internal",
    "HOROSA_SKILL_PYPROJECT": "internal",
}
# removed 档：曾存在于历史版本、现已删除的旗标 → 接受并忽略 + 指路。删代码不删兼容。
REMOVED_ENV_FLAGS: dict[str, str] = {}

_ENV_AUDIT_DONE = False


def audit_env_flags(*, force: bool = False) -> list[str]:
    """扫描 HOROSA_* 环境变量：未知 → warn-and-ignore（返回并记日志，进程内只告警一次）；
    HOROSA_STRICT_CONFIG=1 时未知升级为 ValueError（显式选择加入的严格档）。"""
    global _ENV_AUDIT_DONE
    warnings: list[str] = []
    for key in sorted(os.environ):
        if not key.startswith("HOROSA_"):
            continue
        if key in ENV_FLAG_REGISTRY:
            continue
        if key in REMOVED_ENV_FLAGS:
            warnings.append(f"环境变量 {key} 已在新版移除：{REMOVED_ENV_FLAGS[key]}（本次忽略）")
            continue
        warnings.append(f"未知环境变量 {key}（拼写有误？或来自更新版本的 skill）——已忽略，不影响运行。")
    if warnings and (os.environ.get("HOROSA_STRICT_CONFIG", "").strip().lower() in {"1", "true", "yes"}):
        raise ValueError("HOROSA_STRICT_CONFIG=1：" + "；".join(warnings))
    if warnings and (force or not _ENV_AUDIT_DONE):
        for line in warnings:
            logger.warning("%s", line)
    _ENV_AUDIT_DONE = True
    return warnings


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


# 字段 ↔ env 旗标映射（provenance 用；新增 env 驱动字段须同步登记，测试锁步）。
FIELD_ENV_MAP = {
    "server_root": "HOROSA_SERVER_ROOT",
    "chart_server_root": "HOROSA_CHART_SERVER_ROOT",
    "data_dir": "HOROSA_SKILL_DATA_DIR",
    "db_path": "HOROSA_SKILL_DB_PATH",
    "output_dir": "HOROSA_SKILL_OUTPUT_DIR",
    "runtime_root": "HOROSA_RUNTIME_ROOT",
    "runtime_manifest_url": "HOROSA_RUNTIME_MANIFEST_URL",
    "runtime_platform": "HOROSA_RUNTIME_PLATFORM",
    "runtime_release_repo": "HOROSA_RUNTIME_RELEASE_REPO",
    "local_backend_port": "HOROSA_LOCAL_BACKEND_PORT",
    "local_chart_port": "HOROSA_LOCAL_CHART_PORT",
    "runtime_start_timeout_seconds": "HOROSA_RUNTIME_START_TIMEOUT_SECONDS",
    "mcp_compact": "HOROSA_MCP_COMPACT",
    "js_engine_timeout_seconds": "HOROSA_JS_ENGINE_TIMEOUT_SECONDS",
    "host": "HOROSA_SKILL_HOST",
    "port": "HOROSA_SKILL_PORT",
    "log_level": "HOROSA_SKILL_LOG_LEVEL",
    "trace_enabled": "HOROSA_TRACE_ENABLED",
    "trace_dir": "HOROSA_TRACE_DIR",
    "trace_capture_payloads": "HOROSA_TRACE_CAPTURE_PAYLOADS",
    "trace_capture_ai_answers": "HOROSA_TRACE_CAPTURE_AI_ANSWERS",
    "trace_otlp_endpoint": "HOROSA_TRACE_OTLP_ENDPOINT",
}


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
    # 冷启动等待：Java(Spring Boot fat jar)+Python(星历重导入) 后端首启常超 15s，45s 覆盖常见机器。
    runtime_start_timeout_seconds: float = 45.0
    # MCP 精简工具面：True 时只暴露 dispatch/guidance/memory/report 门面 + 通用直呼 horosa_tool_run，
    # 技法工具不平铺（省 tools/list 上下文预算）；默认 False 保持 87 工具全量平铺。
    mcp_compact: bool = False
    js_engine_timeout_seconds: float = 60.0
    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "INFO"
    trace_enabled: bool = True
    trace_dir: Path | None = None
    trace_capture_payloads: bool = False
    trace_capture_ai_answers: bool = False
    trace_otlp_endpoint: str | None = None
    # Settings provenance（v0.33.0 批 II-3）：每字段的取值来源（env:<NAME> / derived:<字段> / default），
    # doctor 三列（字段/值/来源）据此呈现——「这项配置为什么是这个值」一眼可答。exclude 不入序列化。
    settings_provenance: dict[str, str] = Field(default_factory=dict, exclude=True)

    @classmethod
    def from_env(cls) -> "Settings":
        audit_env_flags()
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
            runtime_start_timeout_seconds=_env_float("HOROSA_RUNTIME_START_TIMEOUT_SECONDS", 45.0, minimum=0.1),
            mcp_compact=_env_bool("HOROSA_MCP_COMPACT", False),
            js_engine_timeout_seconds=_env_float("HOROSA_JS_ENGINE_TIMEOUT_SECONDS", 60.0, minimum=0.1),
            host=_env_text("HOROSA_SKILL_HOST", "127.0.0.1") or "127.0.0.1",
            port=_env_int("HOROSA_SKILL_PORT", 8765, minimum=1, maximum=65535),
            log_level=(_env_text("HOROSA_SKILL_LOG_LEVEL", "INFO") or "INFO").upper(),
            trace_enabled=_env_bool("HOROSA_TRACE_ENABLED", True),
            trace_dir=Path(trace_dir_env).expanduser() if trace_dir_env else data_dir / "traces",
            trace_capture_payloads=_env_bool("HOROSA_TRACE_CAPTURE_PAYLOADS", False),
            trace_capture_ai_answers=_env_bool("HOROSA_TRACE_CAPTURE_AI_ANSWERS", False),
            trace_otlp_endpoint=_env_text("HOROSA_TRACE_OTLP_ENDPOINT"),
            settings_provenance={
                field: (f"env:{env_name}" if _env_text(env_name) is not None else (
                    # 三个路径字段无独立 env 时由 data_dir 派生（而非模型默认）
                    "derived:data_dir" if field in {"db_path", "output_dir", "trace_dir"} else "default"
                ))
                for field, env_name in FIELD_ENV_MAP.items()
            },
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
