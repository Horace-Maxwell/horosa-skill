from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

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
    # v0.37.0 运行时安全：mac 启动器的「只杀自己人」补丁开关（设 0 会失去误杀保护），
    # 以及 AppCDS 训练 JVM 的端口（上游硬编码 39997，与别的程序撞车时是静默降级）。
    "HOROSA_MCP_MAX_CONCURRENT_TOOLS": "stable",
    "HOROSA_RUNTIME_LAUNCHER_PATCH": "experimental",
    "HOROSA_RUNTIME_TRUST_PORTS": "experimental",
    "HOROSA_PORTS": "stable",
    "HOROSA_CDS_TRAIN_PORT": "experimental",
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
    "HOROSA_RUNTIME_CALL_WAIT_SECONDS": "stable",
    "HOROSA_RUNTIME_JAVA_RETRY_COOLDOWN_SECONDS": "stable",
    "HOROSA_MCP_COMPACT": "stable",
    "HOROSA_MCP_ELICIT": "stable",
    "HOROSA_MCP_ELICIT_TIMEOUT_SECONDS": "stable",
    "HOROSA_MCP_TOKEN": "stable",
    "HOROSA_MCP_ALLOWED_HOSTS": "stable",
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
    "HOROSA_UVX_BIN": "internal",
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
    "HOROSA_LAUNCH_NONCE": "internal",
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
            # 启动期环境审计，没有工具调用可告知——不是降级点（verify_silent_degrades 只盯 logger.warning）。
            logger.log(logging.WARNING, "%s", line)
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


# 未展开的模板占位符：`${user_config.runtimeRoot}` / `${CLAUDE_PLUGIN_ROOT}` 这类。
_UNEXPANDED_TEMPLATE = re.compile(r"^\$\{[^}]*\}$")
_warned_unexpanded: set[str] = set()
# 本进程内见过的未展开占位符：{env 名: 字面量}。doctor 会把它读出来当面告诉用户
# —— 这条通知发生在**任何工具调用之前**（Settings.from_env），没有 envelope 可挂，
# 但它绝不能只活在日志里：宿主没替换占位符时，用户看到的是「装了却全是 not_installed」。
_unexpanded_templates: dict[str, str] = {}


def unexpanded_env_templates() -> dict[str, str]:
    """本进程启动时被当作「未设置」处理的未展开占位符（供 doctor / 诊断输出）。"""
    return dict(_unexpanded_templates)


def _env_text(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    stripped = value.strip()
    if not stripped:
        return default
    if _UNEXPANDED_TEMPLATE.match(stripped):
        # 🔴 宿主没展开占位符时，值是**字面量**而不是路径。照单全收的后果实测过两次：
        # `HOROSA_RUNTIME_ROOT='${user_config.runtimeRoot}'` → 每个技法工具都回
        # `runtime.not_installed`，而 `Settings.ensure_dirs()` 还会在 CWD 里 mkdir 出一个
        # 名叫 `${user_config.runtimeRoot}` 的真目录（仓里那几个 `${env:HOME:-…}` 目录同族）。
        # 当作未设置 → 回落默认值，是唯一不会把用户目录搞脏的解释。
        _unexpanded_templates[name] = stripped
        if name not in _warned_unexpanded:
            _warned_unexpanded.add(name)
            # 用 logger.log(WARNING) 而非 logger.warning：verify_silent_degrades 把包内的
            # 裸 logger.warning 定义为「只告诉了日志、没告诉调用方」的债。这条是**启动期配置
            # 通知**，那一刻还没有任何工具调用、没有 envelope 可挂；调用方要知道的那一份走
            # `unexpanded_env_templates()` → doctor，比 warnings 列表更早也更该出现在那儿。
            logger.log(
                logging.WARNING,
                "%s 的值是未展开的模板占位符 %r（宿主没有替换它）——按未设置处理，回落默认值。",
                name, stripped,
            )
        return default
    return stripped


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


# 自动挑端口的备用区间：默认口被占时从这里往上找。避开常见开发端口（3000/5000/8000/8080）。
_AUTO_BACKEND_BASE = 19999
_AUTO_CHART_BASE = 18899
_AUTO_SPAN = 100


def _auto_ports(runtime_root: Path, backend_default: int, chart_default: int) -> tuple[int, int]:
    """`HOROSA_PORTS=auto`：挑一对能用的端口。

    顺序：① 注册表里记着的那对（这份 runtime 上次就跑在那儿；正在跑的话必须复用，否则每个新
    客户端都会另起一套）→ ② 默认口若空闲就用默认 → ③ 从备用区间往上探。
    挑出来只是**候选**：`start_local_services` 仍会做归属判定，占着的若不是我们的照样报冲突。
    """
    from horosa_skill.runtime.ports import find_free_port, port_bindable

    recorded: dict[str, Any] = {}
    try:
        raw = (runtime_root / "runtime-state.json").read_text(encoding="utf-8")
        state = json.loads(raw)
        if isinstance(state, dict) and isinstance(state.get("ports"), dict):
            recorded = state["ports"]
    except (OSError, ValueError):
        recorded = {}

    def _pick(recorded_key: str, default_port: int, base: int) -> int:
        candidate = recorded.get(recorded_key)
        if isinstance(candidate, int) and 0 < candidate < 65536:
            # 空闲（可重用）或正被占（很可能就是我们上次起的那份）都直接复用。
            return candidate
        if port_bindable(default_port):
            return default_port
        return find_free_port(base, span=_AUTO_SPAN)

    return (
        _pick("backend", backend_default, _AUTO_BACKEND_BASE),
        _pick("chart", chart_default, _AUTO_CHART_BASE),
    )


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
    "runtime_java_retry_cooldown_seconds": "HOROSA_RUNTIME_JAVA_RETRY_COOLDOWN_SECONDS",
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
    # Java 后端起不来（degraded_chart_only）后的重试冷却：冷却期内碰 Java 的调用快速失败
    # （runtime.java_backend_unavailable），不再为了再试 Java 先杀掉健康的 chart 服务再全量重启；0 = 关闭冷却。
    runtime_java_retry_cooldown_seconds: float = 120.0
    # MCP 精简工具面：True 时只暴露 11 个门面工具（dispatch/guidance/memory/report 等 + 通用直呼
    # horosa_tool_run），技法工具不平铺（省 tools/list 上下文预算）；默认 False 保持 97 工具全量平铺。
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
        runtime_root = _env_path("HOROSA_RUNTIME_ROOT", _default_runtime_root())
        backend_port = _env_int("HOROSA_LOCAL_BACKEND_PORT", 9999, minimum=1, maximum=65535)
        chart_port = _env_int("HOROSA_LOCAL_CHART_PORT", 8899, minimum=1, maximum=65535)
        ports_mode = (_env_text("HOROSA_PORTS", "") or "").strip().lower()
        if ports_mode == "auto":
            backend_port, chart_port = _auto_ports(runtime_root, backend_port, chart_port)
        # 🔴 URL 必须跟着端口走。旧实现里 server_root 与 local_backend_port 是两个互不相干的字段：
        # 只设 HOROSA_LOCAL_BACKEND_PORT=19999 时，启动器听 19999，而探针、客户端、doctor 全都还
        # 打 9999 —— 用户「换个端口避开占用」的正常操作，结果是「服务起来了却一个技法都用不了」。
        server_root_env = _env_text("HOROSA_SERVER_ROOT")
        chart_root_env = _env_text("HOROSA_CHART_SERVER_ROOT")
        db_path_env = _env_text("HOROSA_SKILL_DB_PATH")
        output_dir_env = _env_text("HOROSA_SKILL_OUTPUT_DIR")
        trace_dir_env = _env_text("HOROSA_TRACE_DIR")
        return cls(
            server_root=server_root_env or f"http://127.0.0.1:{backend_port}",
            chart_server_root=chart_root_env or f"http://127.0.0.1:{chart_port}",
            data_dir=data_dir,
            db_path=Path(db_path_env).expanduser() if db_path_env else data_dir / "memory.db",
            output_dir=Path(output_dir_env).expanduser() if output_dir_env else data_dir / "runs",
            runtime_root=runtime_root,
            runtime_manifest_url=_env_text("HOROSA_RUNTIME_MANIFEST_URL"),
            runtime_platform=_env_text("HOROSA_RUNTIME_PLATFORM"),
            runtime_release_repo=_env_text("HOROSA_RUNTIME_RELEASE_REPO", DEFAULT_RELEASE_REPO) or DEFAULT_RELEASE_REPO,
            local_backend_port=backend_port,
            local_chart_port=chart_port,
            runtime_start_timeout_seconds=_env_float("HOROSA_RUNTIME_START_TIMEOUT_SECONDS", 45.0, minimum=0.1),
            runtime_java_retry_cooldown_seconds=_env_float("HOROSA_RUNTIME_JAVA_RETRY_COOLDOWN_SECONDS", 120.0, minimum=0.0),
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
                    "derived:data_dir" if field in {"db_path", "output_dir", "trace_dir"}
                    # 两个 URL 无独立 env 时由端口派生（auto 模式下端口本身也是探出来的）
                    else "derived:local_backend_port" if field == "server_root"
                    else "derived:local_chart_port" if field == "chart_server_root"
                    else "auto:HOROSA_PORTS" if ports_mode == "auto" and field in {
                        "local_backend_port", "local_chart_port"
                    }
                    else "default"
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
