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
    return json.loads(result.output)


def test_doctor_public_keys() -> None:
    report = _run_json("doctor")
    required = {
        "environment", "memory_db", "env_flags", "settings_provenance",
    }
    missing = sorted(required - set(report))
    assert missing == [], f"doctor 公开键缺失（破坏脚本用户）：{missing}"
    assert {"path", "ok", "detail"} <= set(report["memory_db"])
    assert {"ok", "warnings", "set"} <= set(report["env_flags"])
    rows = report["settings_provenance"]
    assert rows and {"field", "value", "source"} == set(rows[0])
    sources = {row["source"].split(":")[0] for row in rows}
    assert sources <= {"env", "derived", "default"}


def test_client_config_codex_public_keys() -> None:
    payload = _run_json("client", "config", "--format", "codex")
    assert {"note", "toml_stdio", "toml_http"} <= set(payload)


def test_settings_provenance_reflects_env(monkeypatch) -> None:
    from horosa_skill.config import Settings

    monkeypatch.setenv("HOROSA_MCP_COMPACT", "1")
    monkeypatch.delenv("HOROSA_SERVER_ROOT", raising=False)
    s = Settings.from_env()
    assert s.settings_provenance["mcp_compact"] == "env:HOROSA_MCP_COMPACT"
    assert s.settings_provenance["server_root"] == "default"
    assert s.settings_provenance["db_path"] == "derived:data_dir"


def test_field_env_map_stays_registered() -> None:
    """锁步：FIELD_ENV_MAP 里的每个 env 名必须在 ENV_FLAG_REGISTRY（provenance 指向幽灵旗标=脏）。"""
    from horosa_skill.config import ENV_FLAG_REGISTRY, FIELD_ENV_MAP

    ghosts = sorted(set(FIELD_ENV_MAP.values()) - set(ENV_FLAG_REGISTRY))
    assert ghosts == [], ghosts
