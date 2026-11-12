from __future__ import annotations

from pathlib import Path

from horosa_skill import config as config_module
from horosa_skill.config import Settings


def test_settings_from_env_uses_safe_fallbacks(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data-home"))
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    monkeypatch.setenv("HOROSA_RUNTIME_RELEASE_REPO", "   ")
    monkeypatch.setenv("HOROSA_LOCAL_BACKEND_PORT", "not-a-port")
    monkeypatch.setenv("HOROSA_LOCAL_CHART_PORT", "70000")
    monkeypatch.setenv("HOROSA_RUNTIME_START_TIMEOUT_SECONDS", "0")
    monkeypatch.setenv("HOROSA_JS_ENGINE_TIMEOUT_SECONDS", "-5")
    monkeypatch.setenv("HOROSA_SKILL_PORT", "bad")
    monkeypatch.setenv("HOROSA_SKILL_LOG_LEVEL", "debug")
    monkeypatch.setenv("HOROSA_TRACE_ENABLED", "no")
    monkeypatch.setenv("HOROSA_TRACE_CAPTURE_PAYLOADS", "yes")
    monkeypatch.setenv("HOROSA_TRACE_CAPTURE_AI_ANSWERS", "1")
    monkeypatch.setenv("HOROSA_TRACE_OTLP_ENDPOINT", "https://example.com/trace")
    # v0.38.1 R11：出厂预算按宿主是否仿真取 45 / 120；这里钉成原生，让断言与跑测试的机器无关。
    monkeypatch.setattr(config_module, "_host_runs_emulated", lambda: False)

    settings = Settings.from_env()

    assert settings.data_dir == tmp_path / "data-home"
    assert settings.runtime_root == tmp_path / "runtime-root"
    assert settings.db_path == settings.data_dir / "memory.db"
    assert settings.output_dir == settings.data_dir / "runs"
    assert settings.runtime_release_repo == "Horace-Maxwell/horosa-skill"
    assert settings.local_backend_port == 9999
    assert settings.local_chart_port == 8899
    # 冷启动默认 45s：Java+Python 后端首启常超 15s。
    assert settings.runtime_start_timeout_seconds == 45.0
    assert settings.mcp_compact is False
    assert settings.js_engine_timeout_seconds == 60.0
    assert settings.port == 8765
    assert settings.log_level == "DEBUG"
    assert settings.trace_enabled is False
    assert settings.trace_capture_payloads is True
    assert settings.trace_capture_ai_answers is True
    assert settings.trace_otlp_endpoint == "https://example.com/trace"


def test_settings_from_env_expands_user_paths(monkeypatch) -> None:
    monkeypatch.setenv("HOROSA_SKILL_DB_PATH", "~/horosa-test/memory.db")
    monkeypatch.setenv("HOROSA_SKILL_OUTPUT_DIR", "~/horosa-test/runs")
    monkeypatch.setenv("HOROSA_TRACE_DIR", "~/horosa-test/traces")

    settings = Settings.from_env()

    assert str(settings.db_path).startswith(str(Path.home()))
    assert str(settings.output_dir).startswith(str(Path.home()))
    assert str(settings.trace_dir).startswith(str(Path.home()))


# ── v0.33.0 批 II-1 · env 旗标前向兼容（warn-and-ignore；STRICT 才拒）──────────────


def test_unknown_env_flag_warns_but_never_raises(monkeypatch) -> None:
    from horosa_skill import config as config_module

    monkeypatch.setenv("HOROSA_TYPO_FLAG", "1")
    monkeypatch.delenv("HOROSA_STRICT_CONFIG", raising=False)
    warnings = config_module.audit_env_flags(force=True)
    assert any("HOROSA_TYPO_FLAG" in w for w in warnings)
    settings = config_module.Settings.from_env()  # 未知旗标绝不阻断加载（codex 0.112.0 反面教材）
    assert settings.server_root


def test_strict_config_rejects_unknown_flags(monkeypatch) -> None:
    import pytest

    from horosa_skill import config as config_module

    monkeypatch.setenv("HOROSA_TYPO_FLAG", "1")
    monkeypatch.setenv("HOROSA_STRICT_CONFIG", "1")
    with pytest.raises(ValueError, match="HOROSA_TYPO_FLAG"):
        config_module.audit_env_flags(force=True)


def test_known_env_flags_produce_no_warnings(monkeypatch) -> None:
    from horosa_skill import config as config_module

    for key in list(__import__("os").environ):
        if key.startswith("HOROSA_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOROSA_MCP_COMPACT", "1")
    monkeypatch.setenv("HOROSA_SERVER_ROOT", "http://127.0.0.1:9999")
    assert config_module.audit_env_flags(force=True) == []


def test_env_registry_covers_all_flags_code_reads() -> None:
    """锁步：src/ 里出现的每个 HOROSA_* 字面量都必须在 ENV_FLAG_REGISTRY 登记——
    新增旗标忘登记 = 用户一设就被 warn-and-ignore 误伤为「未知」。"""
    import re
    from pathlib import Path

    from horosa_skill.config import ENV_FLAG_REGISTRY, REMOVED_ENV_FLAGS

    src = Path(__import__("horosa_skill").__file__).parent
    seen: set[str] = set()
    for py in src.rglob("*.py"):
        seen.update(re.findall(r"HOROSA_[A-Z0-9_]+", py.read_text(encoding="utf-8", errors="replace")))
    seen.discard("HOROSA_")
    known = set(ENV_FLAG_REGISTRY) | set(REMOVED_ENV_FLAGS)
    # 排除测试夹具/文档示例专用名（不是运行时读的旗标）
    unregistered = sorted(k for k in seen if k not in known and not k.startswith("HOROSA_TYPO"))
    assert unregistered == [], f"HOROSA_* 旗标未在 ENV_FLAG_REGISTRY 登记：{unregistered}"


def test_default_start_timeout_grows_on_emulated_hosts(monkeypatch, tmp_path: Path) -> None:
    """真机矩阵 ARM lane 实测冷启动 59.6 s；45 s 出厂预算让健康机器的 selfcheck / runtime start 以 starting 收场。"""
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "rt"))
    monkeypatch.delenv("HOROSA_RUNTIME_START_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setattr(config_module, "_host_runs_emulated", lambda: True)
    settings = Settings.from_env()
    assert settings.runtime_start_timeout_seconds == 120.0
    assert settings.settings_provenance["runtime_start_timeout_seconds"] == "default:emulated_host"
    monkeypatch.setenv("HOROSA_RUNTIME_START_TIMEOUT_SECONDS", "30")
    settings = Settings.from_env()
    assert settings.runtime_start_timeout_seconds == 30.0, "用户显式设置永远优先"
    assert settings.settings_provenance["runtime_start_timeout_seconds"] == "env:HOROSA_RUNTIME_START_TIMEOUT_SECONDS"
    monkeypatch.delenv("HOROSA_RUNTIME_START_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setattr(config_module, "_host_runs_emulated", lambda: False)
    settings = Settings.from_env()
    assert settings.runtime_start_timeout_seconds == 45.0
    assert settings.settings_provenance["runtime_start_timeout_seconds"] == "default"


def test_host_runs_emulated_reads_the_arch_report_and_the_fallback_table(monkeypatch) -> None:
    import horosa_skill.runtime.manager as manager_module

    monkeypatch.setattr(manager_module, "arch_report", lambda: {"process": "x86_64", "native": "arm64", "emulated": True})
    assert config_module._host_runs_emulated() is True
    monkeypatch.setattr(manager_module, "arch_report", lambda: {"process": "arm64", "native": "arm64", "emulated": False})
    monkeypatch.setattr(manager_module, "_platform_key", lambda: "win32-arm64")
    assert config_module._host_runs_emulated() is True, "Windows on ARM 跑 x64 载荷 = 仿真"
    monkeypatch.setattr(manager_module, "_platform_key", lambda: "darwin-arm64")
    assert config_module._host_runs_emulated() is False


# ── v0.47.2-dev · 代码里出现的每个 HOROSA_* 名字都已登记（否则合法的维护机 / 用户 shell 每次启动都报「未知环境变量」）──

# 不是环境变量、或故意不登记的名字（各有理由；新增要写明）。
_NOT_ENV_FLAGS = {
    "HOROSA_APP_CONTROL_STUB": "模块属性（应用控制替身打的标记），不是环境变量",
    "HOROSA_CHECKOUT": "测试里的客户端占位符 ${env:HOROSA_CHECKOUT}，由客户端展开，skill 不读",
    "HOROSA_EPHE_FASTPATH": "负向对照里故意拼错的 HOROSA_EPHE_PATH_FASTPATH",
    "HOROSA_TYPO": "测试故意用的未知旗标",
    "HOROSA_TYPO_FLAG": "测试故意用的未知旗标",
    "HOROSA_TYPO_API_TOKEN": "测试故意用的未知旗标：名字像令牌，验被拒的值整段遮掉（test_env_rejections）",
    "HOROSA_TYPO_RUNTIME_MIROR": "测试故意拼错的 HOROSA_RUNTIME_MIRROR：验未知变量只告警一次（test_env_rejections）",
}


def test_every_horosa_name_in_the_tree_is_registered() -> None:
    import re

    root = Path(__file__).resolve().parents[1]
    pattern = re.compile(r"\bHOROSA_[A-Z0-9_]*[A-Z0-9]\b")
    found: dict[str, str] = {}
    for base in ("src", "tests", "scripts"):
        for path in (root / base).rglob("*"):
            if path.suffix in {".py", ".ps1", ".sh", ".mjs", ".js"} and path.is_file() and "node_modules" not in path.parts:
                for name in pattern.findall(path.read_text(encoding="utf-8", errors="replace")):
                    found.setdefault(name, f"{base}/{path.relative_to(root / base).as_posix()}")
    unregistered = {name: where for name, where in found.items()
                    if name not in config_module.ENV_FLAG_REGISTRY and name not in config_module.REMOVED_ENV_FLAGS
                    and name not in _NOT_ENV_FLAGS}
    assert not unregistered, f"登记进 config.ENV_FLAG_REGISTRY（skill 不读的写 internal）或写进 _NOT_ENV_FLAGS 并给理由：{unregistered}"
    stale = sorted(name for name in _NOT_ENV_FLAGS if name not in found)
    assert not stale, f"_NOT_ENV_FLAGS 里的名字已不在树里，删掉：{stale}"


def test_maintainer_and_desktop_variables_do_not_warn(monkeypatch) -> None:
    for key in list(__import__("os").environ):
        if key.startswith("HOROSA_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOROSA_VERAPDF", r"C:\tools\verapdf\verapdf.bat")
    monkeypatch.setenv("HOROSA_JAVA_HOME", r"C:\jdk-17")
    assert config_module.audit_env_flags(force=True) == []
