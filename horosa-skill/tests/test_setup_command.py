"""`horosa-skill setup --client <target>`（v0.38.0 B4）：一条命令接入的行为契约。

**为什么旧检查抓不到**：接入此前是四条命令 + 手动粘配置，没有任何一处验证「客户端将要执行的那条命令
真能起 server」——`client config` 只打印建议、`client check` 只看文件、进程内 MCP 测试绕开 spawn。
本文件锁：步骤顺序固定；第 3 步之前失败 `config_untouched: true`；dry-run 零副作用；幂等；写完回读；
真 stdio 探测数工具；失败包结构化写 stderr、退出码 2。
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

import winshell
from fake_claude import FakeClaude
from horosa_skill.client_config import claude_cli
from horosa_skill.engine.registry import COMPACT_SURFACE_TOOL_COUNT
from horosa_skill.surfaces import runtime_helpers as runtime_helpers
from horosa_skill.surfaces import setup_flow as setup_flow
from horosa_skill.surfaces import doctor as doctor_checks
from horosa_skill.client_config import payload as client_payload
from horosa_skill.surfaces.cli import app
from horosa_skill.surfaces.setup_flow import _SETUP_STEPS

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
    # v0.41.0：setup 第 4 步会把 skill 装进 ~/.agents/skills 等目录——测试绝不能写进维护机真实的 HOME。
    monkeypatch.setattr("horosa_skill.skill_install.default_home", lambda: tmp_path / "home")


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
    for name in ("network_probe", "install", "config", "skill", "client_check", "stdio_probe"):
        assert report["steps"][name]["skipped"] is True, name
    assert report["steps"]["config"]["path"] == str(config.resolve())
    assert "horosa" in report["steps"]["config"]["server_block"]
    assert report["steps"]["doctor"]["advisory"] is True
    assert report["surface"] == "compact" and report["tools"] == COMPACT_SURFACE_TOOL_COUNT


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
    env = written["mcpServers"]["horosa"]["env"]
    assert env["HOROSA_MCP_COMPACT"] == "1"
    # 本文件的夹具在「终端」里设了非默认的 runtime 根 / 数据目录 / 端口：客户端不读终端环境，所以它们必须写进条目（MCP-05）。
    assert env["HOROSA_RUNTIME_ROOT"] == str((tmp_path / "runtime-root").resolve())
    assert env["HOROSA_SKILL_DATA_DIR"] == str((tmp_path / "data").resolve())
    assert (env["HOROSA_LOCAL_BACKEND_PORT"], env["HOROSA_LOCAL_CHART_PORT"]) == ("39997", "39898")
    assert not [name for name in env if "TOKEN" in name or "KEY" in name]
    assert set(first["steps"]["config"]["carried_env"]) == set(env) - {"HOROSA_MCP_COMPACT"}
    first_bytes = config.read_bytes()

    second = _stdout_json(_run(*args))
    assert second["ok"] is True
    assert second["steps"]["install"]["changed"] is False, "同一载荷第二次不该重装"
    assert config.read_bytes() == first_bytes, "第二次写出的配置必须逐字节相同"
    # MCP-12：旧断言是「第二次也留了 mcp.json.horosa-bak」——那份「备份」是我们自己第一次写的内容，而且每跑一次就把上一份
    # 覆盖掉：用户真正的原文件（如果有）第二次就没了。内容没变就不写、不备份，才是重跑应有的样子。
    assert second["steps"]["config"]["changed"] is False and second["steps"]["config"]["backup"] is None
    assert not list(tmp_path.glob("mcp.json.horosa-bak*")), "本来就没有原文件：没什么可备份的"
    assert "配置已是最新" in second["summary"] and "配置已写入" in first["summary"]


def _manifest_without(tmp_path: Path, platform: str) -> str:
    """本地清单：只有 darwin-arm64（不碰网络；`platform` 只是为了文件名好认）。"""
    manifest = tmp_path / f"manifest-no-{platform}.json"
    manifest.write_text(json.dumps({"version": "1.2.3", "platforms": {"darwin-arm64": {
        "url": (tmp_path / "missing.tar.gz").resolve().as_uri(), "sha256": "0" * 64}}}), encoding="utf-8")
    return manifest.resolve().as_uri()


@pytest.mark.parametrize("platform", ["linux-x64", "win32-x64"])
def test_setup_on_a_platform_without_a_payload_writes_the_config_instead_of_dying(
    platform: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E-12：没有离线载荷可装（Linux 根本没有 / 清单里缺本平台）不是「安装失败」。

    旧实现死在 install，retry_command 原样重复同一次失败，配置一个字没写——用户连网关模式都接不上。
    linux-x64：平台本就没有载荷，不去下载；win32-x64：平台有载荷但这份清单里没有（发布不全）。
    """
    monkeypatch.setenv("HOROSA_RUNTIME_PLATFORM", platform)
    config = tmp_path / "mcp.json"

    report = _stdout_json(_run("--client", "cursor", "--config", str(config), "--manifest-url", _manifest_without(tmp_path, platform),
                               "--no-probe-network", "--no-stdio-probe"))

    install = report["steps"]["install"]
    assert (install["skipped"], install["reason"], install["platform"]) == (True, "no_payload_for_platform", platform)
    assert "HOROSA_SERVER_ROOT" in install["next_action"], "出路（网关模式）跟着跳过的原因一起给"
    assert "horosa" in json.loads(config.read_text(encoding="utf-8"))["mcpServers"], "配置照写"
    assert report["steps"]["doctor"]["advisory"] is True
    gateway = [item for item in report["next_steps"] if "网关模式" in item]
    assert gateway and "HOROSA_CHART_SERVER_ROOT=" in gateway[0] and "setup --client cursor" in gateway[0]
    assert platform in report["summary"]


def test_setup_in_external_engine_mode_skips_install_and_carries_the_addresses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """引擎地址指到本机 runtime 之外：不装、不起；两个地址写进条目，客户端起的 server 才连得到同一处。"""
    monkeypatch.setenv("HOROSA_SERVER_ROOT", "http://127.0.0.1:18861")
    monkeypatch.setenv("HOROSA_CHART_SERVER_ROOT", "http://127.0.0.1:18862")
    config = tmp_path / "mcp.json"

    report = _stdout_json(_run("--client", "cursor", "--config", str(config), "--manifest-url", _manifest_without(tmp_path, "x"),
                               "--no-probe-network", "--no-stdio-probe"))

    assert (report["steps"]["install"]["skipped"], report["steps"]["install"]["reason"]) == (True, "external_engine")
    env = json.loads(config.read_text(encoding="utf-8"))["mcpServers"]["horosa"]["env"]
    assert (env["HOROSA_SERVER_ROOT"], env["HOROSA_CHART_SERVER_ROOT"]) == ("http://127.0.0.1:18861", "http://127.0.0.1:18862")
    assert report["steps"]["doctor"]["advisory"] is True and "外部引擎" in report["summary"]


def _manifest_with_engine(tmp_path: Path) -> str:
    """本地清单：只有 darwin-arm64 + 平台无关的 JS 引擎资产（file:// 归档，不碰网络）。"""
    from corejs_fixture import core_js_manifest_entry, make_core_js_archive

    info = make_core_js_archive(tmp_path / "rel" / "horosa-core-js-v1.2.3.tar.gz", "1.2.3")
    manifest = tmp_path / "rel" / "runtime-manifest.json"
    manifest.write_text(json.dumps({"version": "1.2.3", "platforms": {"darwin-arm64": {
        "url": (tmp_path / "missing.tar.gz").resolve().as_uri(), "sha256": "0" * 64}},
        "core_js": core_js_manifest_entry(info, info["path"].resolve().as_uri(), "1.2.3")}), encoding="utf-8")
    return manifest.resolve().as_uri()


@pytest.mark.parametrize("mode", ["no_payload", "external_engine"])
def test_setup_without_a_local_runtime_still_installs_the_js_engine(
    mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E-02：不装 runtime 的两条路（本平台没有载荷 / 外部引擎）此前一个字节都不装，八字 / 紫微 / 奇门等本地 JS 技法全部
    js_engine.cli_missing 而 setup 报成功。现在装平台无关的 JS 引擎资产（runtime 根下 core-js/），网关配置照写。"""
    monkeypatch.setattr("horosa_skill.surfaces.setup_flow._engine_available", lambda settings: False)
    if mode == "no_payload":
        monkeypatch.setenv("HOROSA_RUNTIME_PLATFORM", "linux-x64")
    else:
        monkeypatch.setenv("HOROSA_SERVER_ROOT", "http://127.0.0.1:18861")
        monkeypatch.setenv("HOROSA_CHART_SERVER_ROOT", "http://127.0.0.1:18862")
    config = tmp_path / "mcp.json"

    report = _stdout_json(_run("--client", "cursor", "--config", str(config), "--manifest-url", _manifest_with_engine(tmp_path),
                               "--no-probe-network", "--no-stdio-probe"))

    install = report["steps"]["install"]
    assert install["skipped"] is True, "the runtime itself is still not installed here"
    engine = install["engine"]
    assert engine["ok"] is True and engine["version"] == "1.2.3"
    assert (Path(engine["root"]) / "bin" / "cli.mjs").is_file()
    assert Path(engine["root"]).is_relative_to(tmp_path / "runtime-root")
    assert not (tmp_path / "runtime-root" / "current").exists()
    assert "horosa" in json.loads(config.read_text(encoding="utf-8"))["mcpServers"]


def test_setup_records_an_engine_install_failure_without_failing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("horosa_skill.surfaces.setup_flow._engine_available", lambda settings: False)
    monkeypatch.setenv("HOROSA_RUNTIME_PLATFORM", "linux-x64")
    config = tmp_path / "mcp.json"

    report = _stdout_json(_run("--client", "cursor", "--config", str(config), "--manifest-url", _manifest_without(tmp_path, "linux"),
                               "--no-probe-network", "--no-stdio-probe"))

    engine = report["steps"]["install"]["engine"]
    assert (engine["ok"], engine["code"]) == (False, "runtime.engine_asset_missing")
    assert any("install --engine-only" in item for item in report["next_steps"])
    assert "horosa" in json.loads(config.read_text(encoding="utf-8"))["mcpServers"], "the gateway config is still written"


def test_setup_installs_the_skill_where_the_client_reads_it(tmp_path: Path) -> None:
    """v0.41.0 第 4 步：skill 进客户端读的目录，幂等；next_steps 告诉用户新开会话才生效。"""
    config = tmp_path / ".mcp.json"
    args = ("--client", "claude-code", "--config", str(config), "--skip-install", "--no-probe-network", "--no-stdio-probe")
    first = _stdout_json(_run(*args))
    skill = first["steps"]["skill"]
    assert skill["ok"] is True and skill["targets"][0]["action"] == "installed"
    dest = tmp_path / "home" / ".claude" / "skills" / "horosa-agent"
    assert (dest / "SKILL.md").is_file() and (dest / "references").is_dir()
    assert any("新开一个会话" in item for item in first["next_steps"])
    assert "skill 已安装" in first["summary"]
    second = _stdout_json(_run(*args))
    assert second["steps"]["skill"]["targets"][0]["action"] == "unchanged"
    assert "skill 已是最新" in second["summary"]


def test_setup_skill_step_respects_no_skill_dry_run_and_skill_dir(tmp_path: Path) -> None:
    config = tmp_path / "mcp.json"
    base = ("--client", "cursor", "--config", str(config), "--skip-install", "--no-probe-network", "--no-stdio-probe")
    off = _stdout_json(_run(*base, "--no-skill"))
    assert off["steps"]["skill"] == {"ok": True, "skipped": True, "reason": "--no-skill", "summary": "skill 未安装（--no-skill）"}
    plan = _stdout_json(_run(*base, "--dry-run"))
    assert plan["steps"]["skill"]["targets"][0]["action"] == "would_install"
    assert not (tmp_path / "home").exists(), "dry-run 不许写 skill"
    custom = tmp_path / "my-skills"
    chosen = _stdout_json(_run(*base, "--skill-dir", str(custom)))
    assert chosen["steps"]["skill"]["targets"][0]["path"] == str(custom / "horosa-agent")
    assert (custom / "horosa-agent" / "SKILL.md").is_file()


def test_a_skill_failure_does_not_fail_the_onboarding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """skill 只建议性：MCP 配置已写好，skills 目录写不进去也不能让整条 setup 退出 2。"""

    def boom(*_args, **_kwargs):
        raise PermissionError("read-only skills folder")

    monkeypatch.setattr("horosa_skill.skill_install.install_skill", boom)
    report = _stdout_json(_run("--client", "cursor", "--config", str(tmp_path / "mcp.json"), "--skip-install",
                               "--no-probe-network", "--no-stdio-probe"))
    assert report["ok"] is True
    assert report["steps"]["skill"]["targets"][0]["action"] == "failed"
    assert any("skill 没装上" in item for item in report["next_steps"])


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
    assert setup_flow._default_setup_launcher(None) == "uv"
    assert setup_flow._default_setup_launcher(tmp_path) == "uvx-wheel"
    monkeypatch.setattr(runtime_helpers, "_package_root", lambda: tmp_path)
    assert setup_flow._default_setup_launcher(None) == "uvx-wheel", "wheel 装出来的包旁边没有 pyproject.toml"


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


def _claude_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """claude-code 用户级用例的隔离：cwd 与 HOME 都在 tmp 里（状态文件 = <home>/.claude.json）。"""
    home = tmp_path / "home dir"  # 带空格：打印出来的命令要能原样粘回终端
    home.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return home


def _in_process_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state_file: Path, **options) -> FakeClaude:
    fake = FakeClaude(state_file, **options)
    real_which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda name, *a, **k: str(tmp_path / "bin" / "claude") if name == "claude" else real_which(name, *a, **k))
    monkeypatch.setattr(setup_flow, "_run_claude", fake.run)
    return fake


_CLAUDE_ARGS = ("--client", "claude-code", "--skip-install", "--no-probe-network", "--no-stdio-probe")


def _pasted(text: str, *, windows: bool = os.name == "nt") -> list[list[str]]:
    """setup 打印的命令粘进终端后各条的 argv。Windows 上 cmd 与 PowerShell 都要读成同一个 argv（v0.50.0 windows-smoke：
    此前按 cmd 的规则写 JSON 参数，这里却用 shlex 拆，`Invalid JSON`；而真粘进 PowerShell 同样是坏的）。"""
    out: list[list[str]] = []
    for part in winshell.commands(text, windows=windows):
        if windows:
            argv = winshell.cmd_argv(part)
            assert winshell.powershell_argv(part) == argv, f"PowerShell 与 cmd 读成了两样：{part}"
        else:
            argv = shlex.split(part)
        out.append(argv)
    return out


def _replay(fake: FakeClaude, text: str, *, windows: bool = os.name == "nt") -> None:
    """把 setup 打印的命令（可能两条）原样喂回替身：打印出来的必须是能跑的命令。"""
    for argv in _pasted(text, windows=windows):
        completed = fake.run(argv)
        assert completed.returncode == 0, (argv, completed.stderr)


_WIN_UV = r"C:\Users\张 三\.local\bin\uv.exe"
_WIN_OLD = {"type": "stdio", "command": r"C:\Program Files\uv\uv.exe",
            "args": ["run", "--directory", r"C:\Users\张 三\horosa skill\horosa-skill", "horosa-skill", "serve"],
            "env": {"MY_API_KEY": "sk-do-not-print", "HOROSA_SKILL_DATA_DIR": r"D:\星阙 数据", "HOROSA_MCP_COMPACT": "1"}}


@pytest.mark.parametrize("fail_add", [False, True])
def test_commands_printed_for_windows_paste_into_powershell_and_cmd(tmp_path: Path, fail_add: bool) -> None:
    """Windows 那一支在本机跑：路径带空格、中文、反斜杠，旧条目有密钥（打印成 <NAME>）。rollback / restore_command / 执行过的
    命令在 cmd 与 PowerShell 里都读成同一个 argv，重放回替身就回到旧条目（密钥值是占位）。"""
    state = tmp_path / ".claude.json"
    state.write_text(json.dumps({"mcpServers": {"horosa": _WIN_OLD}}), encoding="utf-8")
    fake = FakeClaude(state, fail_add_times=1 if fail_add else 0)
    outcome = claude_cli.register_user_server(
        claude_bin=r"C:\Users\张 三\AppData\Roaming\npm\claude.cmd", server_name="horosa",
        stdio_command=[_WIN_UV, "run", "--directory", r"C:\Users\张 三\horosa skill", "horosa-skill", "serve"],
        env={"HOROSA_OUTPUT_SCRIPT": "zh-Hant"}, run=fake.run, config_path=state, os_name="nt",
    )
    printed = [outcome["command"], *outcome["commands"]]
    for text in printed:
        assert all(argv[0] == "claude" for argv in _pasted(text, windows=True))
    assert "sk-do-not-print" not in json.dumps(outcome)
    if fail_add:
        assert outcome["ok"] is False and outcome["restored_previous"] is True
        fake.run(["claude", "mcp", "remove", "--scope", "user", "horosa"])
        _replay(fake, outcome["restore_command"], windows=True)
    else:
        assert outcome["status"] == "updated" and "\n" in outcome["rollback"] and "&&" not in outcome["rollback"]
        _replay(fake, outcome["rollback"], windows=True)
    assert fake.entry("horosa") == {**_WIN_OLD, "env": {**_WIN_OLD["env"], "MY_API_KEY": "<MY_API_KEY>"}}


def test_windows_text_falls_back_to_cmd_only_when_no_common_form_exists() -> None:
    """含 " $ ` % 的参数在 PowerShell 与 cmd 里没有同一种写法：退回 cmd 的写法（照样是 cmd 里能跑的）。add-json 的 JSON 就是这种，
    所以装回旧条目能用 `add` 表达时一律用 `add`。"""
    plain = ["claude", "mcp", "add", "--scope", "user", "horosa", "-e", "K=a b", "--", r"C:\x y\uv.exe", "serve"]
    assert winshell.cmd_argv(claude_cli.shell_text(plain, os_name="nt")) == plain
    assert winshell.powershell_argv(claude_cli.shell_text(plain, os_name="nt")) == plain
    for odd in ('{"type": "http", "url": "https://x"}', "100%", "$HOME", "a`b"):
        command = ["claude", "mcp", "add-json", "--scope", "user", "horosa", odd]
        text = claude_cli.shell_text(command, os_name="nt")
        assert text == subprocess.list2cmdline(command) and winshell.crt_argv(text) == command
    assert claude_cli.restore_command("claude", "h", {"command": "uv", "args": ["serve"], "env": {}})[2] == "add"
    assert claude_cli.restore_command("claude", "h", {"type": "http", "url": "https://x"})[2] == "add-json"
    assert claude_cli.restore_command("claude", "h", {**_WIN_OLD, "timeout": 60})[2] == "add-json", "add 表达不了的键"


def test_claude_code_user_scope_registers_through_the_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = _claude_home(tmp_path, monkeypatch)
    fake = _in_process_claude(tmp_path, monkeypatch, home / ".claude.json")

    report = _stdout_json(_run(*_CLAUDE_ARGS))

    assert report["config_mode"] == "claude-mcp-add"
    command = fake.calls[0]
    assert command[:6] == [str(tmp_path / "bin" / "claude"), "mcp", "add", "--scope", "user", "horosa"]
    assert "--" in command and "stdio" in command[command.index("--"):]
    config = report["steps"]["config"]
    assert (config["status"], config["executed"]) == ("created", True)
    assert config["rollback"] == "claude mcp remove --scope user horosa"
    assert report["steps"]["client_check"]["configured"] is True, "回读的是 claude 真写的 ~/.claude.json"
    _replay(fake, config["rollback"])
    assert fake.entry("horosa") is None


def test_claude_code_user_scope_rerun_is_idempotent_and_an_update_replaces_the_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MCP-04：`claude mcp add` 只会新增（同名即 "already exists"、退出码 1）。重跑 = 不动；参数变了 = remove + add。

    旧实现每次都直接 `add`：第二次必失败，打印的 retry_command 是同一条命令（再失败一次）；精简面 / 繁体输出还把
    `-e K=V` 排在名字前面，名字被当成第二个环境变量吞掉，**第一次**就失败。
    """
    home = _claude_home(tmp_path, monkeypatch)
    state = home / ".claude.json"
    fake = _in_process_claude(tmp_path, monkeypatch, state)

    first = _stdout_json(_run(*_CLAUDE_ARGS))
    assert first["steps"]["config"]["status"] == "created"
    calls_after_first, bytes_after_first = len(fake.calls), state.read_bytes()

    second = _stdout_json(_run(*_CLAUDE_ARGS))
    assert second["ok"] is True
    assert (second["steps"]["config"]["status"], second["steps"]["config"]["executed"]) == ("unchanged", False)
    assert len(fake.calls) == calls_after_first, "一致就一条命令都不跑"
    assert state.read_bytes() == bytes_after_first
    assert "未改动" in second["summary"]

    previous = fake.entry("horosa")
    third = _stdout_json(_run(*_CLAUDE_ARGS, "--surface", "compact", "--output-script", "zh-Hant"))
    config = third["steps"]["config"]
    assert config["status"] == "updated" and config["executed"] is True
    assert {"field": "env.HOROSA_MCP_COMPACT", "change": "added"} in config["changes"]
    assert {"field": "env.HOROSA_OUTPUT_SCRIPT", "change": "added"} in config["changes"]
    entry = fake.entry("horosa")
    assert entry["env"]["HOROSA_MCP_COMPACT"] == "1" and entry["env"]["HOROSA_OUTPUT_SCRIPT"] == "zh-Hant"
    assert entry["command"] == previous["command"] and entry["args"] == previous["args"], "名字没有被 -e 吞掉、命令没有错位"
    assert third["steps"]["client_check"]["configured"] is True
    assert "已更新" in third["summary"]

    # 打印的 rollback 是能跑的命令，跑完回到上一次的条目
    _replay(fake, config["rollback"])
    assert fake.entry("horosa") == previous


def test_claude_code_first_registration_with_env_puts_the_name_before_the_env_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _claude_home(tmp_path, monkeypatch)
    fake = _in_process_claude(tmp_path, monkeypatch, home / ".claude.json")

    report = _stdout_json(_run(*_CLAUDE_ARGS, "--surface", "compact"))

    assert report["steps"]["config"]["status"] == "created"
    assert fake.entry("horosa")["env"]["HOROSA_MCP_COMPACT"] == "1"
    # 没装 claude 时打印的那条命令也得是同一个顺序
    printed = shlex.split(report["steps"]["config"]["command"])
    assert printed[:6] == ["claude", "mcp", "add", "--scope", "user", "horosa"] and printed[6] == "-e"


def test_claude_code_failed_update_puts_the_old_entry_back_and_never_prints_its_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _claude_home(tmp_path, monkeypatch)
    state = home / ".claude.json"
    old_entry = {"type": "stdio", "command": "/old/uv", "args": ["run", "horosa-skill", "serve"],
                 "env": {"MY_API_KEY": "sk-do-not-print", "HOROSA_MCP_COMPACT": "1"}}
    state.write_text(json.dumps({"numStartups": 3, "mcpServers": {"horosa": old_entry, "other": {"command": "x"}}}), encoding="utf-8")
    fake = _in_process_claude(tmp_path, monkeypatch, state, fail_add_times=1)

    result = _run(*_CLAUDE_ARGS)
    failure = _stderr_json(result)

    assert failure["code"] == "setup.claude_mcp_add_failed" and failure["step"] == "config"
    assert failure["details"]["restored_previous"] is True
    assert failure["config_untouched"] is True, "旧条目已装回去：用户的注册没有变化"
    assert fake.entry("horosa") == old_entry, "装回去的是原值（含密钥），不是打印用的占位"
    assert json.loads(state.read_text(encoding="utf-8"))["mcpServers"]["other"] == {"command": "x"}
    assert "sk-do-not-print" not in result.stderr and "sk-do-not-print" not in result.stdout
    assert failure["details"]["rollback_redacted"] == ["MY_API_KEY"]
    assert "<MY_API_KEY>" in failure["details"]["restore_command"]
    # retry_command 不再是「同一条必失败的命令」：替身恢复正常后重跑就是一次 updated
    retried = _stdout_json(_run(*_CLAUDE_ARGS))
    assert retried["steps"]["config"]["status"] == "updated"
    assert retried["steps"]["config"]["rollback_redacted"] == ["MY_API_KEY"]
    assert "sk-do-not-print" not in json.dumps(retried)


def test_claude_code_registration_reads_claude_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`CLAUDE_CONFIG_DIR` 设了，状态文件就在它里面：读（判一致）和回读（client_check）都得跟过去。"""
    _claude_home(tmp_path, monkeypatch)
    config_dir = tmp_path / "claude 配置"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
    fake = _in_process_claude(tmp_path, monkeypatch, config_dir / ".claude.json")

    first = _stdout_json(_run(*_CLAUDE_ARGS))
    second = _stdout_json(_run(*_CLAUDE_ARGS))

    assert first["steps"]["config"]["status"] == "created" and first["steps"]["client_check"]["configured"] is True
    assert second["steps"]["config"]["status"] == "unchanged" and len(fake.calls) == 1


def test_claude_code_replaces_an_entry_it_could_not_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """状态文件不在我们找的地方（读不到旧条目）而 `add` 说 already exists：照样 remove + add，并如实说没读到旧值。"""
    home = _claude_home(tmp_path, monkeypatch)
    elsewhere = tmp_path / "elsewhere" / ".claude.json"
    fake = _in_process_claude(tmp_path, monkeypatch, elsewhere)
    fake.run(["claude", "mcp", "add", "--scope", "user", "horosa", "--", "/old/uv", "serve"])
    monkeypatch.setattr(setup_flow, "_client_check_report", lambda clients, path: {
        "problems": 0, "clients": [{"findings": [{"entry": {"command": "uv"}}], "searched": [str(home / ".claude.json")]}]})

    report = _stdout_json(_run(*_CLAUDE_ARGS))

    config = report["steps"]["config"]
    assert config["status"] == "updated" and config["previous_entry_unreadable"] is True
    assert [call[2] for call in fake.calls[1:]] == ["add", "remove", "add"]
    assert fake.entry("horosa")["command"] != "/old/uv"


@pytest.mark.skipif(os.name == "nt", reason="[platform] 用 shebang 脚本当 claude；Windows 上由进程内替身的用例覆盖")
def test_claude_code_rerun_against_a_real_executable_that_rejects_duplicates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """同一件事，不打任何补丁：PATH 上放一个行为照真 CLI 抄的 `claude` 可执行文件，setup 连跑三次。

    负向对照用的就是这一条——它不依赖本仓任何内部函数名，把 setup_flow 的 claude-code 分支换回旧写法，第二次就红。
    """
    home = _claude_home(tmp_path, monkeypatch)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "claude"
    script.write_text(
        f"#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).with_name('fake_claude.py')))} \"$@\"\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    first = _stdout_json(_run(*_CLAUDE_ARGS))
    second = _stdout_json(_run(*_CLAUDE_ARGS))
    third = _stdout_json(_run(*_CLAUDE_ARGS, "--surface", "compact"))

    assert [r["steps"]["config"]["status"] for r in (first, second, third)] == ["created", "unchanged", "updated"]
    entry = json.loads((home / ".claude.json").read_text(encoding="utf-8"))["mcpServers"]["horosa"]
    assert entry["env"]["HOROSA_MCP_COMPACT"] == "1" and "stdio" in entry["args"]
    assert third["steps"]["client_check"]["configured"] is True


def test_claude_code_without_claude_on_path_prints_the_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    real_which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda name, *a, **k: None if name == "claude" else real_which(name, *a, **k))
    calls: list[list[str]] = []
    monkeypatch.setattr(setup_flow, "_run_claude", lambda command: calls.append(command))

    report = _stdout_json(_run("--client", "claude-code", "--skip-install", "--no-probe-network", "--no-stdio-probe"))

    assert calls == [], "claude 不在 PATH 就绝不能去跑"
    assert report["config_mode"] == "printed"
    assert report["steps"]["config"]["executed"] is False
    assert report["steps"]["config"]["command"].startswith("claude mcp add --scope user horosa ")
    assert " -- " in report["steps"]["config"]["command"]
    assert report["steps"]["client_check"]["skipped"] is True
    assert report["next_steps"][0].startswith("先执行：claude mcp add")


# ---------------------------------------------------------------- the real stdio probe


def test_stdio_probe_spawns_the_client_shaped_command_and_counts_tools(tmp_path: Path) -> None:
    """真 spawn：`<uv> run --directory <checkout> horosa-skill serve --transport stdio --skip-runtime-start`，
    并读 horosa://runtime/status 与宿主比对（v0.38.1 C14）。"""
    config = tmp_path / "mcp.json"
    report = _stdout_json(_run("--client", "cursor", "--config", str(config), "--skip-install", "--no-probe-network"))
    probe = report["steps"]["stdio_probe"]
    assert probe["ok"] is True and probe["tools"] == COMPACT_SURFACE_TOOL_COUNT == probe["expected_tools"], probe
    assert probe["command"].endswith("serve --transport stdio --skip-runtime-start")
    assert probe["server_name"] == "Horosa Skill"
    assert probe["env_shape"] == "minimal" and Path(probe["cwd"]).is_dir()
    status = probe["runtime_status"]
    assert isinstance(status, dict) and status["installed"] == report["steps"]["doctor"]["installed"], probe
    assert "runtime_mismatch" not in probe
    assert report["ok"] is True


def test_stdio_probe_failure_carries_the_stderr_tail() -> None:
    import sys

    probe = setup_flow._stdio_probe(
        command=sys.executable, args=["-c", "import sys; sys.stderr.write('boom: no such server\\n'); sys.exit(3)"],
        env={"PATH": "/usr/bin"}, timeout=30,
    )
    assert probe["ok"] is False
    assert "boom: no such server" in probe["stderr_tail"]


def test_manifest_probe_handles_file_urls_without_network(tmp_path: Path) -> None:
    manifest = tmp_path / "runtime-manifest.json"
    assert doctor_checks._probe_manifest_url(manifest.resolve().as_uri())["ok"] is False
    manifest.write_text("{}", encoding="utf-8")
    assert doctor_checks._probe_manifest_url(manifest.resolve().as_uri())["ok"] is True


# ---------------------------------------------------------------- v0.38.1 C14 / C15


def _names_and(env: dict[str, str], *wanted: str) -> tuple[set[str], dict[str, str | None]]:
    """只把**名字**和点名要看的几个值交给断言：环境字典一旦进了 pytest 的失败回显，终端里的真密钥就跟着打印出来了。"""
    return set(env), {name: env.get(name) for name in wanted}


def test_codex_probe_env_is_minimal_and_carries_only_the_configured_horosa_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", "/from/shell")
    monkeypatch.setenv("HOROSA_MCP_TOKEN", "placeholder")
    names, picked = _names_and(setup_flow._client_probe_env("codex", {"HOROSA_RUNTIME_ROOT": "/from/config"}), "HOROSA_RUNTIME_ROOT")
    assert picked == {"HOROSA_RUNTIME_ROOT": "/from/config"}
    assert "PATH" in names and "HOROSA_MCP_TOKEN" not in names
    # 其余客户端同理（MCP-05 / E-03）。旧断言在这里写的是「cursor 的探针环境里有终端的 HOROSA_MCP_TOKEN」——把缺陷本身
    # 当成了契约（探针继承终端环境 → 只因终端才通的配置也绿）。GUI 客户端不读 shell 环境，探针就不该带。
    monkeypatch.setenv("PYTHONPATH", "/from/shell/src")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:3128")
    names, picked = _names_and(setup_flow._client_probe_env("cursor", {"HOROSA_MCP_COMPACT": "1"}), "HOROSA_MCP_COMPACT", "HTTPS_PROXY")
    assert picked == {"HOROSA_MCP_COMPACT": "1", "HTTPS_PROXY": "http://proxy.invalid:3128"}, "条目自己的 env 在；装依赖要走的代理留着"
    assert "PATH" in names
    leaked = sorted(names & {"HOROSA_MCP_TOKEN", "HOROSA_RUNTIME_ROOT", "PYTHONPATH"})
    assert leaked == [], "终端里的 HOROSA_* / PYTHONPATH 不该进探针"
    assert [setup_flow._probe_env_shape(c) for c in ("codex", "cursor", "copilot-cli")] == ["codex", "minimal", "passthrough"]


def test_runtime_mismatch_is_detected_when_the_server_computes_another_root(tmp_path: Path) -> None:
    """负向对照：Codex 形状的环境里没有 HOROSA_RUNTIME_ROOT，而宿主用了非默认根 → server 报默认根 → 不一致。"""
    from horosa_skill.config import Settings

    settings = Settings(runtime_root=tmp_path / "custom-root", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    probe = {"ok": True, "runtime_status": {"installed": False, "runtime_root": str(tmp_path / "default-root")}}
    detail = setup_flow._probe_runtime_mismatch(probe, settings)
    assert detail and "custom-root" in detail and "default-root" in detail
    same = {"ok": True, "runtime_status": {"installed": False, "runtime_root": str(tmp_path / "custom-root")}}
    assert setup_flow._probe_runtime_mismatch(same, settings) is None
    assert setup_flow._probe_runtime_mismatch({"ok": True, "runtime_status": None}, settings) is None, "老 server 没有该资源 → 不判"


def _fake_wheel_bytes(version: str, *, good: bool = True) -> bytes:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("horosa_skill/__init__.py", "")
        archive.writestr(f"horosa_skill-{version}.dist-info/METADATA", f"Name: horosa-skill\nVersion: {version if good else '0.0.1'}\n")
    return buffer.getvalue()


def test_cache_wheel_downloads_validates_and_records_a_digest(tmp_path: Path) -> None:
    from horosa_skill import __version__

    calls: list[str] = []

    def fetch(url: str, dest: Path) -> None:
        calls.append(url)
        dest.write_bytes(_fake_wheel_bytes(__version__))

    path, warning = client_payload._cache_wheel("https://example.invalid/x.whl", dest_dir=tmp_path, fetch=fetch)
    assert warning is None and path == tmp_path / f"horosa_skill-{__version__}-py3-none-any.whl" and path.is_file()
    assert (tmp_path / f"{path.name}.sha256").read_text(encoding="utf-8").split()[1] == path.name
    again, _ = client_payload._cache_wheel("https://example.invalid/x.whl", dest_dir=tmp_path, fetch=fetch)
    assert again == path and calls == ["https://example.invalid/x.whl"], "已有合法缓存不再下载"


def test_cache_wheel_rejects_a_wrong_version_and_falls_back_to_the_url(tmp_path: Path) -> None:
    from horosa_skill import __version__

    def fetch(url: str, dest: Path) -> None:
        dest.write_bytes(_fake_wheel_bytes(__version__, good=False))

    path, warning = client_payload._cache_wheel("https://example.invalid/x.whl", dest_dir=tmp_path, fetch=fetch)
    assert path is None and warning and "URL" in warning
    assert not list(tmp_path.glob("*.whl")), "坏文件不留在缓存目录"

    def boom(url: str, dest: Path) -> None:
        raise OSError("offline")

    path, warning = client_payload._cache_wheel("https://example.invalid/x.whl", dest_dir=tmp_path, fetch=boom)
    assert path is None and "offline" in (warning or "")


def test_uvx_wheel_payload_uses_the_cached_wheel_when_given(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(client_payload, "resolve_uvx_command", lambda: ["/opt/uv/bin/uvx"])
    wheel = tmp_path / "horosa_skill-x.whl"
    payload, command, _ = client_payload._build_client_config_payload(
        format_name="cursor", skill_root=Path.cwd(), server_name="horosa", launcher="uvx-wheel", surface="auto", wheel_source=str(wheel),
    )
    assert command[:3] == ["/opt/uv/bin/uvx", "--from", str(wheel)] and payload["launcher"]["wheel_cached_path"] == str(wheel)
    assert payload["launcher"]["wheel_url"].startswith("https://")



# ---------------------------------------------------------------- Windows: a running horosa session holds the venv exe

_WINDOWS_FILE_LOCK_STDERR = (
    "   Building horosa-skill @ file:///C:/Users/me/src/horosa-skill\n"
    "      Built horosa-skill @ file:///C:/Users/me/src/horosa-skill\n"
    "error: failed to remove file `C:\\Users\\me\\src\\horosa-skill\\.venv\\Lib\\site-packages\\../../Scripts/horosa-skill.exe`: "
    "The process cannot access the file because it is being used by another process. (os error 32)\n"
)


def test_probe_stderr_diagnosis_recognises_the_windows_file_lock() -> None:
    """v0.39.0 Windows 维护机：挂着的 horosa MCP 会话占着 venv 的 horosa-skill.exe，客户端的 `uv run` 同步 venv 删不掉它。"""
    import re

    diagnosis = setup_flow._diagnose_probe_stderr(_WINDOWS_FILE_LOCK_STDERR)
    assert diagnosis is not None and diagnosis["cause"] == "windows_file_in_use"
    assert diagnosis["locked_file"] == "C:\\Users\\me\\src\\horosa-skill\\.venv\\Scripts\\horosa-skill.exe"
    for text in (diagnosis["explanation"], diagnosis["next_action"]):
        assert re.search(r"[\u4e00-\u9fff]", text) and re.search(r"[A-Za-z]{4}", text), f"必须中英双语：{text}"
    localized = _WINDOWS_FILE_LOCK_STDERR.replace(
        "The process cannot access the file because it is being used by another process.", "另一个程序正在使用此文件，进程无法访问。"
    )
    assert setup_flow._diagnose_probe_stderr(localized)["cause"] == "windows_file_in_use", "中文 Windows：中间那句本地化，两头不变"
    pyd = "error: failed to remove file `C:\\v\\Lib\\site-packages\\pydantic_core\\_core.pyd`: in use (os error 32)"
    assert setup_flow._diagnose_probe_stderr(pyd)["locked_file"].endswith("_core.pyd"), "已加载的扩展模块同理"
    assert setup_flow._diagnose_probe_stderr("boom: no such server\n") is None
    assert setup_flow._diagnose_probe_stderr("error: failed to remove file `C:\\x.exe`: Access is denied. (os error 5)") is None, "权限/杀软是另一类"
    assert setup_flow._diagnose_probe_stderr("") is None


def test_setup_names_the_windows_file_lock_when_the_probe_dies_on_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "mcp.json"
    monkeypatch.setattr(
        setup_flow,
        "_stdio_probe",
        lambda **kwargs: {"ok": False, "error": "ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)",
                          "stderr_tail": _WINDOWS_FILE_LOCK_STDERR},
    )
    failure = _stderr_json(_run("--client", "cursor", "--config", str(config), "--skip-install", "--no-probe-network"))
    assert failure["step"] == "stdio_probe" and failure["code"] == "setup.stdio_probe_failed"
    diagnosis = failure["details"]["diagnosis"]
    assert diagnosis["cause"] == "windows_file_in_use" and diagnosis["locked_file"].endswith("horosa-skill.exe")
    assert failure["message"] == diagnosis["explanation"], "认出来就换成人话，而不是通用那句"
    assert failure["steps"]["stdio_probe"]["diagnosis"] == diagnosis, "步骤记录里也带上（lane 报告读的是它）"
    assert failure["details"]["stderr_tail"] == _WINDOWS_FILE_LOCK_STDERR, "原始 stderr 仍原样保留"
