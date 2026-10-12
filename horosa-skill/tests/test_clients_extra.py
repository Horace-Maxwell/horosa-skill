"""16 家新客户端（v0.41.0）：每家的「会出事的那个事实」各钉一条。

**为什么旧检查抓不到**：此前只有 9 家，每家的形状都写在 cli 的分支里、测试跟着分支走。新 16 家里有几处一写错就静默失效的：
OpenCode 的命令是一个数组、没有 `args` 键（多写的 `args` 被静默丢掉）；Goose 缺 `enabled` / `args` 的条目被静默跳过；
Amp 的根键是字面量 `amp.mcpServers`；CodeBuddy 只读三个文件里第一个存在的；Deep Code 见注释就把整份配置连 API key 丢掉；
Copilot CLI 只转发 PATH；TRAE 没有用户级文件；dsh 的补丁文件里可能有用户别的补丁。本文件每条都是「改回错的样子就红」。
"""

from __future__ import annotations

import base64
import json
import zipfile
from pathlib import Path
from urllib.parse import unquote

import pytest
from typer.testing import CliRunner

from horosa_skill import clients_extra, skill_install
from horosa_skill.surfaces import cli
from horosa_skill.surfaces.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "rt"))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("HOROSA_MCP_COMPACT", raising=False)
    monkeypatch.setattr("horosa_skill.skill_install.default_home", lambda: tmp_path / "home")


def _setup(client: str, config: Path | None, *extra: str) -> dict:
    args = ["setup", "--client", client, "--skip-install", "--no-probe-network", "--no-stdio-probe", "--launcher", "uvx-wheel",
            "--no-cache-wheel", *extra]
    if config is not None:
        args[3:3] = ["--config", str(config)]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_every_extra_client_round_trips_through_setup_and_check(tmp_path: Path) -> None:
    names = {"goose": "config.yaml", "dsh": "horosa.cordis.yml"}
    for key in clients_extra.EXTRA_CLIENTS:
        config = tmp_path / "cfg" / key / names.get(key, f"{key}.json")
        report = _setup(key, config, "--no-skill")
        assert report["ok"] is True, key
        check = report["steps"]["client_check"]
        assert check["configured"] is True and check["problems"] == 0, (key, check)
        assert report["tools"] == 11 and report["surface"] == "compact", key


def test_opencode_command_is_one_array_with_environment(tmp_path: Path) -> None:
    config = tmp_path / "opencode.json"
    _setup("opencode", config, "--no-skill")
    entry = json.loads(config.read_text(encoding="utf-8"))["mcp"]["horosa"]
    assert entry["type"] == "local" and isinstance(entry["command"], list) and "args" not in entry
    assert entry["command"][-2:] == ["--transport", "stdio"] and entry["environment"] == {"HOROSA_MCP_COMPACT": "1"}
    assert entry["timeout"] >= 600000


def test_goose_keeps_the_users_extensions_and_writes_required_fields(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("GOOSE_PROVIDER: openai\n# keep\nextensions:\n  developer:\n    enabled: true\n    type: builtin\n", encoding="utf-8")
    _setup("goose", config, "--no-skill")
    text = config.read_text(encoding="utf-8")
    assert text.startswith("GOOSE_PROVIDER: openai\n# keep\nextensions:\n  developer:\n")
    from horosa_skill import yaml_block

    entry = yaml_block.read_children(text, "extensions")["horosa"]
    assert entry["enabled"] is True and entry["args"][-1] == "stdio" and entry["timeout"] == 600 and "cmd" in entry


def test_amp_root_key_is_the_literal_dotted_string(tmp_path: Path) -> None:
    config = tmp_path / "settings.json"
    config.write_text('{\n  // user comment\n  "amp.dangerouslyAllowAll": false\n}\n', encoding="utf-8")
    _setup("amp", config, "--no-skill")
    text = config.read_text(encoding="utf-8")
    assert "// user comment" in text
    from horosa_skill import jsonc

    data = jsonc.loads(text)
    assert set(data["amp.mcpServers"]["horosa"]) == {"command", "args", "env"}, "Amp 的 schema 封闭：不许多余字段"
    assert "amp" not in data


def test_codebuddy_writes_the_one_file_it_actually_reads(tmp_path: Path) -> None:
    home = tmp_path / "home"
    legacy = home / ".codebuddy.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(json.dumps({"mcpServers": {"mine": {"command": "x"}}}), encoding="utf-8")
    candidates = cli._client_config_locations("codebuddy", os_name="darwin", env={}, home=home, cwd=tmp_path)
    assert candidates == [home / ".codebuddy" / ".mcp.json", home / ".codebuddy" / "mcp.json", legacy]
    chosen = next(c for c in candidates if c.is_file())
    assert chosen == legacy, "只有旧文件在时必须写旧文件——新建 .mcp.json 会让 CodeBuddy 看不到用户原有的 server"


def test_deepcode_refuses_a_file_with_comments(tmp_path: Path) -> None:
    config = tmp_path / "settings.json"
    config.write_text('{\n  // my key\n  "env": {"API_KEY": "k"}\n}\n', encoding="utf-8")
    result = runner.invoke(app, ["setup", "--client", "deepcode", "--config", str(config), "--skip-install", "--no-probe-network",
                                 "--no-stdio-probe", "--launcher", "uvx-wheel", "--no-cache-wheel", "--no-skill"])
    assert result.exit_code == 2
    assert "整份配置" in result.stderr and config.read_text(encoding="utf-8").startswith('{\n  // my key'), "拒写：文件原样不动"
    clean = tmp_path / "clean.json"
    clean.write_text('{"env": {"API_KEY": "k"}}', encoding="utf-8")
    _setup("deepcode", clean, "--no-skill")
    data = json.loads(clean.read_text(encoding="utf-8"))
    assert data["env"] == {"API_KEY": "k"} and "horosa" in data["mcpServers"]


def test_copilot_cli_carries_home_and_the_probe_gets_only_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "realhome"))
    monkeypatch.setenv("SOME_SHELL_ONLY_VAR", "x")
    payload, _cmd, _env = cli._build_client_config_payload(
        format_name="copilot-cli", skill_root=cli._package_root(), server_name="horosa", launcher="uvx-wheel", surface="auto",
    )
    entry = payload["mcpServers"]["horosa"]
    assert entry["tools"] == ["*"] and entry["timeout"] >= 600000 and entry["type"] == "local"
    if cli.os.name != "nt":
        assert entry["env"]["HOME"] == str(tmp_path / "realhome")
    assert {"HOROSA_RUNTIME_ROOT", "HOROSA_SKILL_DATA_DIR", "HOROSA_MCP_COMPACT"} <= set(entry["env"])
    probe = cli._client_probe_env("copilot-cli", entry["env"])
    assert "SOME_SHELL_ONLY_VAR" not in probe and "PATH" in probe, "探针必须按 Copilot 的最坏形状（只给 PATH）起 server"
    problems = clients_extra.audit("copilot-cli", {**entry, "env": {}}, os_name="posix")
    assert {p["code"] for p in problems} >= {"copilot_cli_env_home_missing"}


def test_trae_prints_an_import_link_instead_of_guessing_a_file(tmp_path: Path) -> None:
    report = _setup("trae", None, "--no-skill")
    config = report["steps"]["config"]
    assert config["mode"] == "printed" and config["executed"] is False and report["config_path"] is None
    assert report["steps"]["client_check"]["skipped"] is True
    encoded = config["deep_link"].split("config=", 1)[1]
    entry = json.loads(base64.b64decode(unquote(encoded)))
    assert entry["env"]["START_MCP_TIMEOUT_MS"] == "120000" and entry["env"]["RUN_MCP_TIMEOUT_MS"] == "600000"
    assert config["deep_link_cn"].startswith("trae-cn://") and json.loads(config["paste_json"])["mcpServers"]["horosa"] == entry
    assert any("deep_link" in step for step in report["next_steps"])


def test_dsh_gets_a_standalone_patch_and_its_own_file_is_never_touched(tmp_path: Path) -> None:
    home = tmp_path / "home"
    user_patch = home / ".dsh" / "cordis.patch.yml"
    user_patch.parent.mkdir(parents=True)
    user_patch.write_text("- set: {path: x, value: !!js 'y'}\n", encoding="utf-8")
    config = tmp_path / "horosa.cordis.yml"
    report = _setup("dsh", config, "--no-skill")
    assert report["steps"]["client_check"]["problems"] == 0
    servers = clients_extra.read_dsh_patch(config.read_text(encoding="utf-8"))
    assert servers["horosa"]["toolCallTimeoutMs"] >= 600000 and servers["horosa"]["transport"] == "stdio"
    assert user_patch.read_text(encoding="utf-8") == "- set: {path: x, value: !!js 'y'}\n"
    assert any("dsh web --patch" in step for step in report["next_steps"])


@pytest.mark.parametrize(
    ("client", "field", "where"),
    [("opencode", "timeout", "entry"), ("goose", "timeout", "entry"), ("kimi", "startupTimeoutMs", "entry"),
     ("qwen", "discoveryTimeoutMs", "entry"), ("droid", "connectTimeout", "entry"), ("dsh", "toolCallTimeoutMs", "entry"),
     ("trae", "RUN_MCP_TIMEOUT_MS", "env")],
)
def test_check_flags_a_missing_timeout_for_each_client_that_needs_one(client: str, field: str, where: str) -> None:
    entry = {"command": "/abs/uvx", "args": ["serve", "--transport", "stdio"], "env": {"START_MCP_TIMEOUT_MS": "120000", "RUN_MCP_TIMEOUT_MS": "600000"},
             "timeout": 600000 if client != "goose" else 600, "startupTimeoutMs": 120000, "toolTimeoutMs": 600000,
             "discoveryTimeoutMs": 120000, "connectTimeout": 120000, "toolCallTimeoutMs": 600000}
    assert clients_extra.audit(client, entry) == []
    broken = json.loads(json.dumps(entry))
    (broken["env"] if where == "env" else broken).pop(field)
    codes = {p["code"] for p in clients_extra.audit(client, broken)}
    assert any(code.endswith(f"{field}_missing") for code in codes), codes


def test_locations_follow_each_clients_own_overrides() -> None:
    home = Path("/h")
    assert cli._client_config_locations("goose", os_name="nt", env={"APPDATA": "C:/A"}, home=home, cwd=home)[0] == Path("C:/A/Block/goose/config/config.yaml")
    assert cli._client_config_locations("goose", os_name="darwin", env={}, home=home, cwd=home)[0] == home / ".config" / "goose" / "config.yaml"
    assert cli._client_config_locations("opencode", os_name="nt", env={"XDG_CONFIG_HOME": "/x"}, home=home, cwd=home)[0] == Path("/x/opencode/opencode.json")
    assert cli._client_config_locations("copilot-cli", os_name="linux", env={"COPILOT_HOME": "/c"}, home=home, cwd=home) == [Path("/c/mcp-config.json")]
    assert cli._client_config_locations("warp", os_name="nt", env={}, home=home, cwd=home) == [home / ".warp" / ".mcp.json"]


def test_skill_folders_install_one_copy_per_client() -> None:
    home = Path("/h")
    shared = home / ".agents" / "skills"
    own = {"kiro": home / ".kiro" / "skills", "qoder": home / ".qoder" / "skills", "codebuddy": home / ".codebuddy" / "skills",
           "trae": home / ".trae" / "skills", "claude-code": home / ".claude" / "skills"}
    for client in cli._CLIENT_NAMES:
        dirs = skill_install.client_skill_dirs(client, env={}, home=home)
        assert len(dirs) <= 1 or client == "trae", (client, dirs)
        if client in own:
            assert dirs == [own[client]], client
        elif client != "claude-desktop":
            assert dirs == [shared], client
    assert skill_install.client_skill_dirs("copilot-cli", env={"COPILOT_HOME": "/c"}, home=home) == [Path("/c/skills")]


def test_claude_desktop_gets_an_uploadable_zip_and_duplicates_are_named(tmp_path: Path) -> None:
    report = _setup("claude-desktop", tmp_path / "claude_desktop_config.json")
    skill = report["steps"]["skill"]
    archive = Path(skill["zip"])
    with zipfile.ZipFile(archive) as bundle:
        assert "horosa-agent/SKILL.md" in bundle.namelist()
    assert any("Upload a skill" in step for step in report["next_steps"])

    _setup("cursor", tmp_path / "cursor.json")          # → ~/.agents/skills
    second = _setup("claude-code", tmp_path / "claude-project.json")  # → ~/.claude/skills
    assert any("会列出两份同名 skill" in step for step in second["next_steps"]), "两处都装了要提醒（Cursor / VS Code / Codex 会看到两份）"


def test_the_stdio_probe_gets_the_env_the_entry_actually_carries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """首次真探针实跑抓到：探针只给 Codex 补 runtime 根，Copilot CLI 条目里写对了的根没交给 server →「配置写对了」被测成 runtime_mismatch。
    负向对照：把探针的 env 换回旧的 {surface_env}，本条红在 runtime_mismatch。"""
    monkeypatch.setenv("SOME_SHELL_ONLY_VAR", "x")
    seen: dict[str, dict[str, str]] = {}

    def fake_probe(*, command, args, env, timeout, cwd=None):  # noqa: ANN001
        seen["env"] = dict(env)
        return {"ok": True, "tools": 11, "server_name": "horosa", "server_version": "x",
                "runtime_status": {"runtime_root": env.get("HOROSA_RUNTIME_ROOT", str(Path.home() / ".horosa" / "runtime"))}}

    monkeypatch.setattr(cli, "_stdio_probe", fake_probe)
    result = runner.invoke(app, ["setup", "--client", "copilot-cli", "--config", str(tmp_path / "mcp-config.json"), "--skip-install",
                                 "--no-probe-network", "--launcher", "uvx-wheel", "--no-cache-wheel", "--no-skill"])
    assert result.exit_code == 0, result.stderr
    assert seen["env"]["HOROSA_RUNTIME_ROOT"] == str((tmp_path / "rt").resolve())
    assert "SOME_SHELL_ONLY_VAR" not in seen["env"], "Copilot CLI 只转发 PATH——探针不许偷偷继承整个 shell 环境"


@pytest.mark.parametrize("client,name,original", [
    ("goose", "config.yaml", "GOOSE_PROVIDER: openai\r\n# keep\r\nextensions:\r\n  developer:\r\n    enabled: true\r\n"),
    ("zed", "settings.json", '{\r\n  // keep\r\n  "theme": "dark",\r\n}\r\n'),
])
def test_comment_preserving_writes_keep_crlf_files_crlf(tmp_path: Path, client: str, name: str, original: str) -> None:
    """windows-smoke 首推抓到：保注释写入把已带 CRLF 的文本交给文本模式写 → Windows 上 `\\r\\r\\n`，每跑一次多一倍空行。
    现在按原字节写、整份统一成原文件的换行（macOS 上旧代码的插入段是 LF，同样红：混合换行）。"""
    config = tmp_path / name
    config.write_bytes(original.encode("utf-8"))
    for _ in range(2):  # 第二遍也不许漂
        _setup(client, config, "--no-skill")
    raw = config.read_bytes()
    assert b"\r\r" not in raw, "换行被翻译了两次"
    assert raw.count(b"\n") == raw.count(b"\r\n"), "CRLF 文件里混进了 LF 行"
    assert raw.startswith(original.split("\r\n")[0].encode("utf-8") + b"\r\n")
