"""JS 引擎用哪个 Node：太旧 / 指错 / 起不来都要说清楚（docs/LESSONS.md v0.50.0-dev「Node 太旧时每个 JS 技法都报 error: {}」）。

替身 node 是 shell 脚本（审计时 `audit-1111/code/fakebin/node` 的同款）：Windows 上跑不了 `#!/bin/sh`，那边跳过。
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine import node_runtime
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.errors import ToolTransportError, recovery_for

PKG_ROOT = Path(__file__).resolve().parents[1]
posix_only = pytest.mark.skipif(os.name == "nt", reason="[platform] shell-script node stand-ins need a POSIX shell")


@pytest.fixture(autouse=True)
def _fresh_caches():
    node_runtime.clear_caches()
    yield
    node_runtime.clear_caches()


def _stub_node(directory: Path, *, version: str | None, body: str, counter: Path | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "node"
    count = f'echo x >> "{counter}"\n' if counter else ""
    version_branch = f'if [ "$1" = "--version" ]; then {count}echo "{version}"; exit 0; fi\n' if version else ""
    path.write_text("#!/bin/sh\n" + version_branch + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _client(tmp_path: Path) -> HorosaJsEngineClient:
    settings = Settings(runtime_root=tmp_path / "runtime", data_dir=tmp_path / "data",
                        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9")
    return HorosaJsEngineClient(settings)


_SYNTAX_ERROR = 'echo "file:///x/cli.mjs:3" >&2\necho "SyntaxError: Unexpected token \'with\'" >&2\nexit 1\n'


@posix_only
def test_a_too_old_node_is_named_with_the_version_it_needs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_NODE_BIN", str(_stub_node(tmp_path / "bin", version="v18.19.0", body=_SYNTAX_ERROR)))

    with pytest.raises(ToolTransportError) as excinfo:
        _client(tmp_path).run("huangli", {"date": "2028-04-06"})

    error = excinfo.value
    assert error.code == "js_engine.node_too_old"
    assert error.details["found"] == "v18.19.0" and error.details["required"] == ">=20.10.0"
    assert "v18.19.0" in str(error) and "20.10" in str(error) and " / " in str(error)
    assert recovery_for(error.code, error.details)["agent_recovery"]["next_action"] == "install_runtime_or_point_node_bin_at_a_newer_node"


@posix_only
def test_a_startup_crash_surfaces_the_stderr_line_not_an_empty_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Node 读不出版本（`--version` 也崩）时不拦，但真正的失败必须带上 stderr 里那行 SyntaxError，而不是 `error: {}`。"""
    monkeypatch.setenv("HOROSA_NODE_BIN", str(_stub_node(tmp_path / "bin", version=None, body=_SYNTAX_ERROR)))

    with pytest.raises(ToolTransportError) as excinfo:
        _client(tmp_path).run("huangli", {"date": "2028-04-06"})

    error = excinfo.value
    assert error.code == "js_engine.execution_failed"
    assert error.details["error"] == {"message": "SyntaxError: Unexpected token 'with'", "stage": "startup"}
    assert "SyntaxError: Unexpected token 'with'" in str(error)


@posix_only
def test_a_failure_with_json_on_stdout_keeps_the_engines_own_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = 'echo \'{"ok": false, "error": {"message": "bad input", "code": "x"}}\'\necho "noise" >&2\nexit 1\n'
    monkeypatch.setenv("HOROSA_NODE_BIN", str(_stub_node(tmp_path / "bin", version="v22.11.0", body=body)))
    with pytest.raises(ToolTransportError) as excinfo:
        _client(tmp_path).run("huangli", {})
    assert excinfo.value.details["error"] == {"message": "bad input", "code": "x"}


def test_a_missing_node_bin_target_is_an_error_naming_the_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """旧行为：悄悄回落到别的 node。用户以为在用自己指定的那个。"""
    monkeypatch.setenv("HOROSA_NODE_BIN", str(tmp_path / "no-such-node"))
    client = _client(tmp_path)

    with pytest.raises(ToolTransportError) as excinfo:
        client.run("huangli", {})

    assert excinfo.value.code == "js_engine.node_bin_missing"
    assert excinfo.value.details == {"variable": "HOROSA_NODE_BIN", "path": str(tmp_path / "no-such-node")}
    assert "HOROSA_NODE_BIN" in str(excinfo.value)
    assert client.node_choice().as_dict()["problem"] == "node_bin_missing"
    assert client.render_app_charts([{"kind": "x", "data": {}, "options": {}}]) in (None, [])  # 画图永不抛


@posix_only
def test_the_version_is_probed_once_per_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    counter = tmp_path / "probes.log"
    ok_body = 'cat > /dev/null\necho \'{"ok": true, "data": {"v": 1}}\'\n'
    monkeypatch.setenv("HOROSA_NODE_BIN", str(_stub_node(tmp_path / "bin", version="v22.11.0", body=ok_body, counter=counter)))
    client = _client(tmp_path)
    for _ in range(3):
        assert client.run("huangli", {}) == {"data": {"v": 1}}
    assert counter.read_text(encoding="utf-8").count("x") == 1


def test_the_installed_manifest_is_parsed_once_while_it_does_not_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-20：每次 JS 调用此前把已装清单读 3 遍、解析 3 遍。"""
    client = _client(tmp_path)
    current = client.settings.runtime_current_dir
    current.mkdir(parents=True)
    (current / "runtime-manifest.json").write_text(json.dumps({"version": "1"}), encoding="utf-8")
    calls: list[int] = []
    real = client.runtime_manager.load_installed_manifest
    monkeypatch.setattr(client.runtime_manager, "load_installed_manifest", lambda **kw: calls.append(1) or real(**kw))
    for _ in range(4):
        client.node_choice()
        client._candidate_engine_roots()
    assert len(calls) == 1
    (current / "runtime-manifest.json").write_text(json.dumps({"version": "2", "x": "longer"}), encoding="utf-8")
    client._candidate_engine_roots()
    assert len(calls) == 2, "清单换了要重新读"


def test_cli_missing_names_the_real_remedies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOROSA_CORE_JS_ROOT", raising=False)
    client = _client(tmp_path)
    monkeypatch.setattr(client, "_candidate_engine_roots", lambda: [tmp_path / "nowhere"])
    monkeypatch.setattr(client, "_require_node_new_enough", lambda node_bin: None)
    with pytest.raises(ToolTransportError) as excinfo:
        client.run("bazi_birth", {})
    error = excinfo.value
    assert error.code == "js_engine.cli_missing"
    assert {row["source"] for row in error.details["searched"]} == {"env:HOROSA_CORE_JS_ROOT", "runtime", "source_checkout"}
    prompt = recovery_for(error.code, error.details)["agent_recovery"]["prompt_to_user"]
    assert "HOROSA_CORE_JS_ROOT" in prompt and "HOROSA_CORE_JS_ROOT" in str(error)


def test_the_floor_matches_the_engines_package_json() -> None:
    declared = node_runtime.engine_floor_from_package(PKG_ROOT / "horosa-core-js")
    assert declared == node_runtime.NODE_FLOOR_TEXT
    assert node_runtime.parse_version(declared) == node_runtime.NODE_FLOOR


@pytest.mark.parametrize(("stderr", "expected"), [
    ("file:///x/cli.mjs:3\nSyntaxError: Unexpected token 'with'\n", "SyntaxError: Unexpected token 'with'"),
    ("node:internal/modules/cjs/loader:1\n  throw err;\nError: Cannot find module '/x'\n", "Error: Cannot find module '/x'"),
    ("Killed\n", "Killed"),
    ("", None),
])
def test_stderr_summary_picks_the_line_that_explains(stderr: str, expected: str | None) -> None:
    assert node_runtime.stderr_summary(stderr) == expected
