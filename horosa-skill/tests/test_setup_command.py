"""`horosa-skill setup --client <target>`（v0.38.0 B4）：一条命令接入的行为契约。

**为什么旧检查抓不到**：接入此前是四条命令 + 手动粘配置，没有任何一处验证「客户端将要执行的那条命令
真能起 server」——`client config` 只打印建议、`client check` 只看文件、进程内 MCP 测试绕开 spawn。
本文件锁：步骤顺序固定；第 3 步之前失败 `config_untouched: true`；dry-run 零副作用；幂等；写完回读；
真 stdio 探测数工具；失败包结构化写 stderr、退出码 2。
"""

from __future__ import annotations

import json
import subprocess
import tarfile
import time
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from horosa_skill.surfaces import cli as cli_module
from horosa_skill.surfaces.cli import _SETUP_STEPS, app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """每个用例自己的 runtime 根 / 数据目录 / 端口；managed 模式（不指向外部服务）；无镜像。"""
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOROSA_RUNTIME_PLATFORM", "darwin-arm64")
    # 没人监听的端口：doctor 报 services:not_running（可接受），而不是把维护机上的真 runtime 当成本用例的
    monkeypatch.setenv("HOROSA_LOCAL_BACKEND_PORT", "39997")
    monkeypatch.setenv("HOROSA_LOCAL_CHART_PORT", "39898")
    for name in ("HOROSA_SERVER_ROOT", "HOROSA_CHART_SERVER_ROOT", "HOROSA_RUNTIME_MIRROR", "HOROSA_PORTS",
                 "HOROSA_RUNTIME_MANIFEST_URL", "HOROSA_MCP_COMPACT"):
        monkeypatch.delenv(name, raising=False)


def _run(*args: str):
    return runner.invoke(app, ["setup", *args])


def _stdout_json(result) -> dict:
    assert result.exit_code == 0, f"exit={result.exit_code}\nstdout={result.stdout}\nstderr={result.stderr}"
    return json.loads(result.stdout)


def _stderr_json(result) -> dict:
    """失败包在 stderr（前面还有逐步进度行）。"""
    assert result.exit_code == 2, f"exit={result.exit_code}\nstdout={result.stdout}\nstderr={result.stderr}"
    text = result.stderr
    return json.loads(text[text.index("{"):])


def _fake_archive(tmp_path: Path, *, drop: str | None = None) -> Path:
    """mac 布局的假载荷，manifest 显式写全路径（任何 CI OS 上 doctor 都按 manifest 查文件）。"""
    payload_root = tmp_path / "payload" / "runtime-payload"
    files = {
        "Horosa-Web/start_horosa_local.sh": "#!/usr/bin/env bash\nexit 0\n",
        "Horosa-Web/stop_horosa_local.sh": "#!/usr/bin/env bash\nexit 0\n",
        "horosa-core-js/bin/cli.mjs": "export {};\n",
        "runtime/mac/java/bin/java": "",
        "runtime/mac/python/bin/python3": "",
        "runtime/mac/node/bin/node": "",
        "runtime/mac/bundle/astrostudyboot.jar": "",
    }
    for relative, text in files.items():
        if relative == drop:
            continue
        target = payload_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    for directory in ("Horosa-Web/astropy", "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles"):
        (payload_root / directory).mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "1.2.3",
        "platform": "darwin-arm64",
        "services": {"start_script": "Horosa-Web/start_horosa_local.sh", "stop_script": "Horosa-Web/stop_horosa_local.sh"},
        "runtimes": {"python": "runtime/mac/python/bin/python3", "java": "runtime/mac/java/bin/java", "node": "runtime/mac/node/bin/node"},
        "artifacts": {
            "horosa_web_root": "Horosa-Web", "astropy_root": "Horosa-Web/astropy",
            "flatlib_root": "Horosa-Web/flatlib-ctrad2/flatlib",
            "swefiles_root": "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles",
            "boot_jar": "runtime/mac/bundle/astrostudyboot.jar", "horosa_core_js_root": "horosa-core-js",
        },
    }
    (payload_root / "runtime-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    archive = tmp_path / "runtime-payload.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(payload_root, arcname="runtime-payload")
    return archive


# ---------------------------------------------------------------- shape


def test_dry_run_touches_nothing_and_reports_every_step(tmp_path: Path) -> None:
    config = tmp_path / "mcp.json"
    report = _stdout_json(_run("--client", "cursor", "--config", str(config), "--dry-run", "--no-probe-network"))

    assert report["ok"] is True and report["dry_run"] is True
    assert list(report["steps"]) == list(_SETUP_STEPS)
    assert not config.exists(), "dry-run 不许落盘"
    assert not (tmp_path / "runtime-root" / "current").exists(), "dry-run 不许装 runtime"
    for name in ("network_probe", "install", "config", "client_check", "stdio_probe"):
        assert report["steps"][name]["skipped"] is True, name
    assert report["steps"]["config"]["path"] == str(config.resolve())
    assert "horosa" in report["steps"]["config"]["server_block"]
    assert report["steps"]["doctor"]["advisory"] is True
    assert report["surface"] == "compact" and report["tools"] == 11


def test_unknown_client_is_rejected_before_anything_happens(tmp_path: Path) -> None:
    config = tmp_path / "mcp.json"
    result = _run("--client", "nope", "--config", str(config), "--no-probe-network")
    assert result.exit_code == 2
    assert not config.exists()


def test_no_write_prints_the_block_and_skips_the_readback(tmp_path: Path) -> None:
    config = tmp_path / "settings.json"
    report = _stdout_json(_run("--client", "zed", "--config", str(config), "--no-write", "--skip-install",
                               "--no-probe-network", "--no-stdio-probe"))
    assert report["steps"]["config"]["skipped"] is True
    assert "horosa" in report["steps"]["config"]["server_block"]
    assert report["steps"]["client_check"]["skipped"] is True
    assert not config.exists()


# ---------------------------------------------------------------- the full offline flow


def test_full_offline_flow_is_idempotent(tmp_path: Path) -> None:
    archive = _fake_archive(tmp_path)
    config = tmp_path / "mcp.json"
    args = ("--client", "cursor", "--config", str(config), "--archive", str(archive), "--no-probe-network", "--no-stdio-probe")

    first = _stdout_json(_run(*args))
    assert first["ok"] is True
    assert first["steps"]["network_probe"]["skipped"] is True  # --archive → 不上网
    assert first["steps"]["install"]["changed"] is True
    assert first["steps"]["install"]["version"] == "1.2.3"
    assert first["steps"]["config"]["mode"] == "merge" and first["steps"]["config"]["backup"] is None
    assert first["steps"]["doctor"]["ready"] is True, first["steps"]["doctor"]
    assert first["steps"]["client_check"]["configured"] is True and first["steps"]["client_check"]["problems"] == 0
    written = json.loads(config.read_text(encoding="utf-8"))
    assert "stdio" in written["mcpServers"]["horosa"]["args"]
    assert written["mcpServers"]["horosa"]["env"] == {"HOROSA_MCP_COMPACT": "1"}
    first_bytes = config.read_bytes()

    second = _stdout_json(_run(*args))
    assert second["ok"] is True
    assert second["steps"]["install"]["changed"] is False, "同一载荷第二次不该重装"
    assert config.read_bytes() == first_bytes, "第二次写出的配置必须逐字节相同"
    assert config.with_name("mcp.json.horosa-bak").exists(), "覆盖前必须备份"
    assert second["steps"]["config"]["backup"].endswith("mcp.json.horosa-bak")


def test_merge_keeps_the_users_other_keys(tmp_path: Path) -> None:
    config = tmp_path / "settings.json"
    config.write_text(json.dumps({"theme": "dark", "context_servers": {"other": {"command": "x"}}}), encoding="utf-8")
    _stdout_json(_run("--client", "zed", "--config", str(config), "--skip-install", "--no-probe-network", "--no-stdio-probe"))
    merged = json.loads(config.read_text(encoding="utf-8"))
    assert merged["theme"] == "dark"
    assert set(merged["context_servers"]) == {"other", "horosa"}


def test_codex_writes_toml_that_passes_its_own_check(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    report = _stdout_json(_run("--client", "codex", "--config", str(config), "--skip-install",
                               "--no-probe-network", "--no-stdio-probe"))
    doc = tomllib.loads(config.read_text(encoding="utf-8"))
    assert doc["mcp_servers"]["horosa"]["startup_timeout_sec"] == 120
    assert doc["mcp_servers"]["horosa"]["tool_timeout_sec"] == 600
    assert report["steps"]["config"]["written"]["format"] == "toml"
    assert report["steps"]["client_check"]["problems"] == 0


# ---------------------------------------------------------------- failure envelopes


def test_install_failure_leaves_the_config_untouched(tmp_path: Path) -> None:
    config = tmp_path / "mcp.json"
    original = json.dumps({"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}).encode("utf-8")
    config.write_bytes(original)

    result = _run("--client", "cursor", "--config", str(config), "--archive", str(tmp_path / "missing.tar.gz"),
                  "--no-probe-network", "--no-stdio-probe")

    failure = _stderr_json(result)
    assert failure["ok"] is False and failure["step"] == "install"
    assert failure["code"].startswith("runtime."), failure["code"]
    assert failure["config_untouched"] is True and failure["backup_path"] is None
    assert "setup --client cursor" in failure["retry_command"]
    assert list(failure["steps"]) == ["network_probe"], "失败前已完成的步骤原样带上"
    assert config.read_bytes() == original, "第 3 步之前失败，用户配置一个字节都不能动"
    assert result.stdout.strip() == "", "失败包只走 stderr，stdout 保持空（脚本用户按退出码判）"


def test_network_probe_failure_is_fast_and_names_the_way_out(tmp_path: Path) -> None:
    config = tmp_path / "mcp.json"
    started = time.perf_counter()
    result = _run("--client", "cursor", "--config", str(config),
                  "--manifest-url", "http://127.0.0.1:9/runtime-manifest.json", "--no-stdio-probe")
    elapsed = time.perf_counter() - started

    failure = _stderr_json(result)
    assert failure["step"] == "network_probe" and failure["code"] == "setup.network_unreachable"
    assert failure["config_untouched"] is True
    assert "--no-probe-network" in failure["retry_command"]
    assert "HOROSA_RUNTIME_MIRROR" in failure["details"]["next_action"]
    assert failure["details"]["attempts"] and failure["details"]["attempts"][0]["ok"] is False
    assert elapsed < 30, f"探针必须快（{elapsed:.1f}s）——它存在的意义就是别等下载超时"
    assert not config.exists()


def test_doctor_failure_after_the_write_reports_the_backup(tmp_path: Path) -> None:
    """装上了但载荷缺件 → doctor 不通过 → 失败包要说明配置已写、备份在哪。"""
    archive = _fake_archive(tmp_path, drop="runtime/mac/bundle/astrostudyboot.jar")
    config = tmp_path / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

    result = _run("--client", "cursor", "--config", str(config), "--archive", str(archive),
                  "--no-probe-network", "--no-stdio-probe")

    failure = _stderr_json(result)
    assert failure["step"] == "doctor" and failure["code"] == "setup.doctor_not_ready"
    assert "missing:boot_jar" in failure["details"]["issues"]
    assert failure["config_untouched"] is False
    assert failure["backup_path"].endswith("mcp.json.horosa-bak") and Path(failure["backup_path"]).exists()
    assert "horosa" in json.loads(config.read_text(encoding="utf-8"))["mcpServers"]


# ---------------------------------------------------------------- launcher / mirror


def test_uvx_wheel_launcher_honours_the_mirror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_RUNTIME_MIRROR", "https://mirror.example/gh/")
    config = tmp_path / "mcp.json"
    report = _stdout_json(_run("--client", "cursor", "--config", str(config), "--launcher", "uvx-wheel",
                               "--dry-run", "--no-probe-network"))
    assert report["launcher"]["kind"] == "uvx-wheel"
    assert report["launcher"]["wheel_url"].startswith("https://mirror.example/gh/")
    args = report["steps"]["config"]["server_block"]["horosa"]["args"]
    assert "--from" in args and args[args.index("--from") + 1] == report["launcher"]["wheel_url"]
    assert "horosa-skill setup --client cursor" in report["recheck_command"] or report["recheck_command"].startswith("horosa-skill ")


def test_default_launcher_is_uv_inside_a_checkout_and_uvx_wheel_elsewhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert cli_module._default_setup_launcher(None) == "uv"
    assert cli_module._default_setup_launcher(tmp_path) == "uvx-wheel"
    monkeypatch.setattr(cli_module, "_package_root", lambda: tmp_path)
    assert cli_module._default_setup_launcher(None) == "uvx-wheel", "wheel 装出来的包旁边没有 pyproject.toml"


# ---------------------------------------------------------------- claude-code scopes


def test_claude_code_project_scope_writes_the_projects_mcp_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    report = _stdout_json(_run("--client", "claude-code", "--scope", "project", "--skip-install",
                               "--no-probe-network", "--no-stdio-probe"))
    assert report["config_mode"] == "merge"
    assert Path(report["config_path"]) == (tmp_path / ".mcp.json").resolve()
    written = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    assert "stdio" in written["mcpServers"]["horosa"]["args"]
    assert report["steps"]["client_check"]["configured"] is True


def test_claude_code_auto_scope_picks_the_project_file_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
    report = _stdout_json(_run("--client", "claude-code", "--skip-install", "--no-probe-network", "--no-stdio-probe"))
    assert report["config_mode"] == "merge"
    merged = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    assert set(merged["mcpServers"]) == {"other", "horosa"}


def test_claude_code_user_scope_runs_claude_mcp_add(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # 没有 .mcp.json → auto = user scope
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    fake_claude = tmp_path / "claude"
    real_which = cli_module.shutil.which
    monkeypatch.setattr(cli_module.shutil, "which", lambda name, *a, **k: str(fake_claude) if name == "claude" else real_which(name, *a, **k))
    seen: dict[str, list[str]] = {}

    def fake_add(command: list[str]):
        seen["command"] = command
        # 模拟 claude 把用户级条目写进 ~/.claude.json
        server = command[command.index("--") + 1:]
        (tmp_path / ".claude.json").write_text(
            json.dumps({"mcpServers": {"horosa": {"command": server[0], "args": server[1:]}}}), encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0, stdout="Added stdio MCP server horosa", stderr="")

    monkeypatch.setattr(cli_module, "_claude_mcp_add", fake_add)

    report = _stdout_json(_run("--client", "claude-code", "--skip-install", "--no-probe-network", "--no-stdio-probe"))

    assert report["config_mode"] == "claude-mcp-add"
    assert seen["command"][:6] == [str(fake_claude), "mcp", "add", "--scope", "user", "horosa"]
    assert seen["command"][6] == "--" and "stdio" in seen["command"][7:]
    assert report["steps"]["config"]["executed"] is True
    assert report["steps"]["config"]["rollback"] == "claude mcp remove --scope user horosa"
    assert report["steps"]["client_check"]["configured"] is True, "回读的是 claude 真写的 ~/.claude.json"


def test_claude_code_without_claude_on_path_prints_the_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    real_which = cli_module.shutil.which
    monkeypatch.setattr(cli_module.shutil, "which", lambda name, *a, **k: None if name == "claude" else real_which(name, *a, **k))
    calls: list[list[str]] = []
    monkeypatch.setattr(cli_module, "_claude_mcp_add", lambda command: calls.append(command))

    report = _stdout_json(_run("--client", "claude-code", "--skip-install", "--no-probe-network", "--no-stdio-probe"))

    assert calls == [], "claude 不在 PATH 就绝不能去跑"
    assert report["config_mode"] == "printed"
    assert report["steps"]["config"]["executed"] is False
    assert report["steps"]["config"]["command"].startswith("claude mcp add --scope user horosa -- ")
    assert report["steps"]["client_check"]["skipped"] is True
    assert report["next_steps"][0].startswith("先执行：claude mcp add")


# ---------------------------------------------------------------- the real stdio probe


def test_stdio_probe_spawns_the_exact_client_command_and_counts_tools(tmp_path: Path) -> None:
    """真 spawn：`<uv> run --directory <checkout> horosa-skill serve --transport stdio --skip-runtime-start`。"""
    config = tmp_path / "mcp.json"
    report = _stdout_json(_run("--client", "cursor", "--config", str(config), "--skip-install", "--no-probe-network"))
    probe = report["steps"]["stdio_probe"]
    assert probe["ok"] is True and probe["tools"] == 11 == probe["expected_tools"], probe
    assert probe["command"].endswith("serve --transport stdio --skip-runtime-start")
    assert probe["server_name"] == "Horosa Skill"
    assert report["ok"] is True


def test_stdio_probe_failure_carries_the_stderr_tail() -> None:
    import sys

    probe = cli_module._stdio_probe(
        command=sys.executable, args=["-c", "import sys; sys.stderr.write('boom: no such server\\n'); sys.exit(3)"],
        env={"PATH": "/usr/bin"}, timeout=30,
    )
    assert probe["ok"] is False
    assert "boom: no such server" in probe["stderr_tail"]


def test_manifest_probe_handles_file_urls_without_network(tmp_path: Path) -> None:
    manifest = tmp_path / "runtime-manifest.json"
    assert cli_module._probe_manifest_url(manifest.resolve().as_uri())["ok"] is False
    manifest.write_text("{}", encoding="utf-8")
    assert cli_module._probe_manifest_url(manifest.resolve().as_uri())["ok"] is True
