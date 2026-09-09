"""client-config 守卫的孪生测试。

含「旧检查为什么抓不到」那条：仓根 `.mcp.json` 从 2026-08-21 起 24/24 次连接失败，
而 622 个测试全绿 —— 因为**没有任何检查读过这个文件**。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent
SCRIPTS = PKG_ROOT / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("verify_client_configs", SCRIPTS / "verify_client_configs.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_guard_is_green_on_the_committed_configs() -> None:
    assert _load().main() == 0


def test_the_exact_shape_that_never_connected_is_rejected(monkeypatch, tmp_path: Path) -> None:
    """把 v0.37.0 之前的那份 `.mcp.json` 原样注回去，守卫必须红。

    那一份是插件语法混进项目作用域：`${CLAUDE_PLUGIN_ROOT}` 展开为空 → `--directory /horosa-skill`
    不存在；`${user_config.*}` 原样留在 env 里 → 每个技法工具 `runtime.not_installed`。
    """
    module = _load()
    broken = tmp_path / "broken.mcp.json"
    broken.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "horosa": {
                        "command": "uv",
                        "args": [
                            "run", "--directory", "${CLAUDE_PLUGIN_ROOT}/horosa-skill",
                            "horosa-skill", "serve", "--transport", "stdio",
                        ],
                        "env": {
                            "HOROSA_RUNTIME_ROOT": "${user_config.runtimeRoot}",
                            "HOROSA_SKILL_DATA_DIR": "${user_config.dataDir}",
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PROJECT_CONFIG", broken)
    errors: list[str] = []
    module.check_project_config(errors)
    joined = " ".join(errors)
    assert "CLAUDE_PLUGIN_ROOT" in joined, f"没抓到插件占位符：{errors}"
    assert "user_config." in joined, f"没抓到 user_config 占位符：{errors}"
    assert "env" in joined, f"没抓到 env 块：{errors}"


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda e: e["args"].remove("stdio"), "--transport stdio"),
        (lambda e: e["args"].__setitem__(2, "${NOPE}/horosa-skill"), "没有 `:-默认值`"),
        (lambda e: e["args"].__setitem__(2, "${CLAUDE_PROJECT_DIR:-.}/not-a-package"), "pyproject.toml 不存在"),
    ],
)
def test_negative_controls(monkeypatch, tmp_path: Path, mutate, needle: str) -> None:
    """每种坏法都必须被单独抓到，而不是靠某一条兜底。"""
    module = _load()
    payload = json.loads((REPO_ROOT / ".mcp.json").read_text(encoding="utf-8"))
    mutate(payload["mcpServers"]["horosa"])
    probe = tmp_path / "probe.mcp.json"
    probe.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(module, "PROJECT_CONFIG", probe)
    errors: list[str] = []
    module.check_project_config(errors)
    assert any(needle in e for e in errors), f"期望抓到 {needle!r}，实得 {errors}"


def test_plugin_config_rejects_an_undeclared_user_config_key(monkeypatch, tmp_path: Path) -> None:
    """user_config 键写错和没声明是同一类失败：宿主不替换，值原样落进 env。"""
    module = _load()
    payload = json.loads((REPO_ROOT / ".claude-plugin" / "mcp.json").read_text(encoding="utf-8"))
    entry = payload["mcpServers"]["horosa"]
    entry.setdefault("env", {})["HOROSA_RUNTIME_ROOT"] = "${user_config.typoedKey}"
    probe = tmp_path / "plugin.mcp.json"
    probe.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(module, "PLUGIN_CONFIG", probe)
    errors: list[str] = []
    module.check_plugin_config(errors)
    assert any("typoedKey" in e for e in errors), f"未声明的 user_config 键没被抓到：{errors}"


def test_why_the_old_checks_could_not_catch_it() -> None:
    """旧检查为什么全绿：没有任何一条读过 `.mcp.json`。

    `verify_docs_sync` 只查文档计数与链接，`test_mcp_contract` 走的是进程内构造的 server
    （根本不经过客户端配置文件），`test_client_config` 只测**生成器**的输出、不测仓里提交的那份。
    这条测试把「有没有人读这个文件」本身钉住。
    """
    readers = [
        path
        for path in list(SCRIPTS.glob("verify_*.py")) + list((PKG_ROOT / "tests").glob("test_*.py"))
        if path.name not in {"verify_client_configs.py", "test_verify_client_configs.py"}
        and ".mcp.json" in path.read_text(encoding="utf-8")
    ]
    assert readers == [], (
        f"现在还有别的检查也读 .mcp.json（{[p.name for p in readers]}）——"
        "本测试的前提（此前无人读它）需要重新表述"
    )
