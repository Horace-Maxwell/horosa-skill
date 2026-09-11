"""CLI JSON 输出公开契约（v0.33.0 批 II-3）——脚本用户的稳定面。

顶层键集在此冻结：**删键/改名 = 破坏性变更**，必须有意为之（更新本契约 + CHANGELOG 声明）。
加键随时允许（断言用 ⊆ 方向：契约键必须在场，不锁新增）。
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from horosa_skill.surfaces.cli import app

runner = CliRunner()


def _run_json(*args: str) -> dict:
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, result.output
    # 契约只关心 stdout（`setup` 等命令把进度行写到 stderr；`result.output` 会把两者交错）。
    return json.loads(result.stdout)


def test_doctor_public_keys() -> None:
    report = _run_json("doctor")
    required = {
        "environment", "memory_db", "env_flags", "settings_provenance",
    }
    missing = sorted(required - set(report))
    assert missing == [], f"doctor 公开键缺失（破坏脚本用户）：{missing}"
    assert {"path", "ok", "detail"} <= set(report["memory_db"])
    assert {"node", "uv", "backend_port", "chart_port"} <= set(report["environment"]["probes"])  # uv 探针 v0.38.0 B4
    assert {"ok", "warnings", "set"} <= set(report["env_flags"])
    rows = report["settings_provenance"]
    assert rows and {"field", "value", "source"} == set(rows[0])
    sources = {row["source"].split(":")[0] for row in rows}
    assert sources <= {"env", "derived", "default"}


def test_setup_public_keys(tmp_path, monkeypatch) -> None:
    """`setup` 输出契约（v0.38.0 B4）：顶层键 + 七步顺序 + 每步 `ok`；失败包键集见 test_setup_command。"""
    from horosa_skill.surfaces.cli import _SETUP_STEPS

    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "rt"))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    report = _run_json("setup", "--client", "cursor", "--config", str(tmp_path / "mcp.json"), "--dry-run", "--no-probe-network")
    required = {
        "ok", "client", "launcher", "surface", "tools", "config_path", "config_mode", "dry_run",
        "steps", "next_steps", "summary", "recheck_command",
    }
    missing = sorted(required - set(report))
    assert missing == [], f"setup 公开键缺失（破坏脚本用户）：{missing}"
    assert list(report["steps"]) == list(_SETUP_STEPS) == [
        "network_probe", "install", "config", "doctor", "client_check", "stdio_probe", "next_steps",
    ]
    assert all("ok" in step for step in report["steps"].values())
    assert {"kind"} <= set(report["launcher"])
    assert isinstance(report["next_steps"], list) and report["next_steps"]


def test_client_config_codex_public_keys() -> None:
    payload = _run_json("client", "config", "--format", "codex")
    assert {"note", "toml_stdio", "toml_http"} <= set(payload)


def test_settings_provenance_reflects_env(monkeypatch) -> None:
    from horosa_skill.config import Settings

    monkeypatch.setenv("HOROSA_MCP_COMPACT", "1")
    monkeypatch.delenv("HOROSA_SERVER_ROOT", raising=False)
    monkeypatch.delenv("HOROSA_CHART_SERVER_ROOT", raising=False)
    s = Settings.from_env()
    assert s.settings_provenance["mcp_compact"] == "env:HOROSA_MCP_COMPACT"
    # v0.37.0 D1：两个 URL 不再是独立的默认值，而是由端口**派生**。
    # 🔴 旧行为下 `HOROSA_LOCAL_BACKEND_PORT=19999` 只改启动器监听的端口，server_root 仍是
    # 写死的 :9999 —— 用户「换端口避开占用」的正常操作，结果是「服务起来了却一个技法都用不了」。
    # 旧断言把这两个字段的**互不相干**当成了契约，所以它不会为那个 bug 变红。
    assert s.settings_provenance["server_root"] == "derived:local_backend_port"
    assert s.settings_provenance["chart_server_root"] == "derived:local_chart_port"
    assert s.settings_provenance["db_path"] == "derived:data_dir"


def test_field_env_map_stays_registered() -> None:
    """锁步：FIELD_ENV_MAP 里的每个 env 名必须在 ENV_FLAG_REGISTRY（provenance 指向幽灵旗标=脏）。"""
    from horosa_skill.config import ENV_FLAG_REGISTRY, FIELD_ENV_MAP

    ghosts = sorted(set(FIELD_ENV_MAP.values()) - set(ENV_FLAG_REGISTRY))
    assert ghosts == [], ghosts
