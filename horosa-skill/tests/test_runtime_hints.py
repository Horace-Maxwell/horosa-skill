"""`runtime.not_installed` 的修复命令按安装上下文生成（v0.38.1 C7）+ 无载荷平台第一跳就给出路（A9/A10）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from horosa_skill.config import ENV_FLAG_REGISTRY, Settings
from horosa_skill.errors import RuntimeValidationError
from horosa_skill.runtime import hints
from horosa_skill.runtime.manager import HorosaRuntimeManager

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent


def test_plugin_context_points_at_the_cached_plugin_checkout() -> None:
    root = "/Users/x y/.claude/plugins/cache/horosa-skill/horosa/0.38.1"
    hint = hints.install_command({"HOROSA_INSTALL_CONTEXT": "plugin", "HOROSA_PLUGIN_ROOT": root})
    assert hint["context"] == "plugin"
    assert hint["install"] == f'uv run --directory "{root}/horosa-skill" horosa-skill install'
    assert hint["doctor"].endswith("horosa-skill doctor")


def test_mcpb_context_runs_from_the_bundle_directory() -> None:
    root = r"C:\Users\张三\AppData\Local\Claude\Claude Extensions\local.dxt.horosa"
    hint = hints.install_command({"HOROSA_INSTALL_CONTEXT": "mcpb", "HOROSA_PLUGIN_ROOT": root})
    assert hint["context"] == "mcpb" and hint["install"] == f'uv run --directory "{root}" horosa-skill install'


def test_an_unexpanded_plugin_root_is_not_trusted() -> None:
    hint = hints.install_command({"HOROSA_INSTALL_CONTEXT": "plugin", "HOROSA_PLUGIN_ROOT": "${CLAUDE_PLUGIN_ROOT}"})
    assert hint["context"] != "plugin"


def test_checkout_context_in_this_repository() -> None:
    hint = hints.install_command({})
    assert hint["context"] == "checkout" and hint["install"] == "uv run horosa-skill install"
    assert Path(hint["cwd"]).resolve() == PKG_ROOT


def test_wheel_context_uses_the_pinned_wheel_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill import __version__

    monkeypatch.setattr(hints, "_package_is_checkout", lambda: False)
    monkeypatch.delenv("HOROSA_RUNTIME_MIRROR", raising=False)
    hint = hints.install_command({})
    assert hint["context"] == "wheel" and hint["cwd"] is None
    assert hint["install"].startswith('uvx --from "https://github.com/')
    assert f"horosa_skill-{__version__}-py3-none-any.whl" in hint["install"]
    assert "pip install horosa-skill" not in hint["install"], "PyPI 未开通，不许指过去"


def test_quote_is_unconditional_and_escapes_embedded_quotes() -> None:
    assert hints._quote("plain") == '"plain"'
    assert hints._quote("a b") == '"a b"'
    assert hints._quote('say "hi"') == '"say \\"hi\\""'
    assert hints._quote("C:\\Users\\张三") == '"C:\\Users\\张三"'


def _empty_manager(tmp_path: Path, platform_name: str) -> HorosaRuntimeManager:
    return HorosaRuntimeManager(Settings(
        runtime_root=tmp_path / "runtime-root", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs",
        runtime_platform=platform_name,
    ))


def test_not_installed_error_carries_context_specific_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = str(tmp_path / "plugins" / "horosa" / "0.38.1")
    monkeypatch.setenv("HOROSA_INSTALL_CONTEXT", "plugin")
    monkeypatch.setenv("HOROSA_PLUGIN_ROOT", root)
    with pytest.raises(RuntimeValidationError) as excinfo:
        _empty_manager(tmp_path, "darwin-arm64")._require_runtime()
    details = excinfo.value.details
    assert excinfo.value.code == "runtime.not_installed" and details["install_context"] == "plugin"
    assert details["agent_recovery"]["commands"][0] == f'uv run --directory "{root}/horosa-skill" horosa-skill install'
    assert "uv run --directory" in details["next_action"] and "Run `" in details["next_action"]


@pytest.mark.parametrize("platform_name", ["darwin-x64", "linux-x64", "linux-arm64", "freebsd-x86_64"])
def test_a_platform_without_a_payload_is_a_dead_end_on_the_first_call(tmp_path: Path, platform_name: str) -> None:
    """此前第一跳报 not_installed → 用户去 install → 第二跳才说 install_missing_platform。"""
    with pytest.raises(RuntimeValidationError) as excinfo:
        _empty_manager(tmp_path, platform_name)._require_runtime()
    details = excinfo.value.details
    assert excinfo.value.code == "runtime.platform_unsupported"
    assert details["platform"] == platform_name and details["supported"] == ["darwin-arm64", "win32-x64"]
    assert "HOROSA_SERVER_ROOT" in details["next_action"] and "Gateway mode" in details["next_action"]
    assert details["agent_recovery"]["must_ask_user"] is False
    if platform_name == "darwin-x64":
        assert "Rosetta" in details["reason"]


def test_windows_on_arm_is_not_a_dead_end(tmp_path: Path) -> None:
    with pytest.raises(RuntimeValidationError) as excinfo:
        _empty_manager(tmp_path, "win32-arm64")._require_runtime()
    assert excinfo.value.code == "runtime.not_installed"


def test_platform_advice_is_bilingual() -> None:
    from horosa_skill.runtime.manager import _platform_dead_end_advice

    for key in ("darwin-x64", "linux-x64", "win32-arm64", "sunos-sparc"):
        advice = _platform_dead_end_advice(key)
        assert " / " in advice["reason"] and " / " in advice["next_action"], key
        assert "Gateway mode" in advice["next_action"]


def test_new_context_env_flags_are_registered() -> None:
    assert ENV_FLAG_REGISTRY["HOROSA_INSTALL_CONTEXT"] == "stable"
    assert ENV_FLAG_REGISTRY["HOROSA_PLUGIN_ROOT"] == "stable"


def test_plugin_and_mcpb_manifests_declare_their_context() -> None:
    plugin = json.loads((REPO_ROOT / ".claude-plugin" / "mcp.json").read_text(encoding="utf-8"))
    env = plugin["mcpServers"]["horosa"]["env"]
    assert env["HOROSA_INSTALL_CONTEXT"] == "plugin" and env["HOROSA_PLUGIN_ROOT"] == "${CLAUDE_PLUGIN_ROOT}"
    mcpb = json.loads((PKG_ROOT / "manifest.json").read_text(encoding="utf-8"))
    env = mcpb["server"]["mcp_config"]["env"]
    assert env["HOROSA_INSTALL_CONTEXT"] == "mcpb" and env["HOROSA_PLUGIN_ROOT"] == "${__dirname}"
