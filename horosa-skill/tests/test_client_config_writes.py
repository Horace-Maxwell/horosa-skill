"""MCP-12 / C-16：客户端配置落盘的三条不变量，对每一种可写格式逐个验证。

1. 内容没变就不写、也不备份（重跑 setup 不产生任何文件变化）；
2. 第一份 `.horosa-bak` 是用户的原文件，以后永不覆盖；之后每次真改动另存带时间戳的，有上限；
3. 原子替换、保留原文件权限位（0600 的配置不会变成 0644）；OpenClaw 主配置同样留底。

旧实现每次都覆盖同一个 `.horosa-bak`（第二次跑完，用户原文件就没了），Codex TOML 直接 write_text，
所有格式写完都是 umask 权限，OpenClaw 主配置没有备份。
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from horosa_skill.client_config import merge as client_merge
from horosa_skill.client_config import openclaw as client_openclaw
from horosa_skill.client_config import payload as client_payload
from horosa_skill.client_config.locations import _CLIENT_NAMES
from horosa_skill.surfaces import runtime_helpers

# 有可合并配置文件的格式，以及每种格式「用户原来就有」的一份内容（带别家 server 与密钥）。
_ORIGINALS: dict[str, str] = {
    "json": json.dumps({"mcpServers": {"other": {"command": "x", "env": {"OTHER_API_KEY": "user-secret"}}}}, indent=4),
    "jsonc": '{\n  // 用户注释\n  "mcpServers": {"other": {"command": "x"}},\n}\n',
    "toml": '# 用户注释\nmodel = "o4"\n\n[mcp_servers.other]\ncommand = "x"\n',
    "yaml": "GOOSE_PROVIDER: openai\n# keep\nextensions:\n  developer:\n    enabled: true\n    type: builtin\n",
}


def _build(format_name: str) -> dict:
    payload, _command, _env = client_payload._build_client_config_payload(
        format_name=format_name, skill_root=runtime_helpers._package_root(), server_name="horosa",
        launcher="uvx-wheel", surface="auto",
    )
    return payload


def _writable_formats() -> list[tuple[str, str]]:
    """(格式, 原文件样式)：能经 `_merge_client_config` 落盘的全部格式。"""
    out: list[tuple[str, str]] = []
    for name in _CLIENT_NAMES:
        payload = _build(name)
        if isinstance(payload.get("toml_stdio"), str):
            out.append((name, "toml"))
        elif payload.get("config_format") == "yaml":
            out.append((name, "yaml"))
        elif payload.get("config_format") == "dsh-patch":
            out.append((name, "dsh"))
        elif payload.get("strict_json"):
            out.append((name, "json"))
        elif isinstance(payload.get(payload.get("root_key") or ""), dict) or any(
            isinstance(payload.get(k), dict) for k in client_merge._MERGEABLE_ROOT_KEYS
        ):
            out.append((name, "json"))
    return out


_FORMATS = _writable_formats()


def _backups(target: Path) -> list[Path]:
    return sorted(target.parent.glob(f"{target.name}.horosa-bak*"))


def test_every_writable_format_is_swept() -> None:
    names = {name for name, _style in _FORMATS}
    assert {"claude-desktop", "cursor", "vscode", "codex", "zed", "goose", "opencode"} <= names, sorted(names)


@pytest.mark.parametrize(("format_name", "style"), _FORMATS)
def test_rerun_writes_nothing_and_keeps_the_users_original_backup(
    format_name: str, style: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "配置 dir" / f"config.{ 'toml' if style == 'toml' else 'yaml' if style == 'yaml' else 'json'}"
    target.parent.mkdir()
    original = _ORIGINALS.get(style if style != "dsh" else "json", _ORIGINALS["json"])
    if style == "dsh":
        original = "# 用户手写的补丁文件\n"
    target.write_text(original, encoding="utf-8")
    if os.name != "nt":
        target.chmod(0o600)
    payload = _build(format_name)

    first = client_merge._merge_client_config(target, payload)
    assert first["changed"] is True
    after_first = target.read_bytes()
    first_backup = target.with_name(f"{target.name}.horosa-bak")
    assert first["backup"] == str(first_backup) and first_backup.read_text(encoding="utf-8") == original
    if os.name != "nt":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600, "原文件 0600：写完还得是 0600"
        assert stat.S_IMODE(first_backup.stat().st_mode) == 0o600, "备份里有同样的密钥，权限跟原文件"

    second = client_merge._merge_client_config(target, payload)
    assert (second["changed"], second["backup"]) == (False, None), "内容没变：不写、不备份"
    assert target.read_bytes() == after_first
    assert _backups(target) == [first_backup]
    assert first_backup.read_text(encoding="utf-8") == original, "用户的原文件永远在第一份备份里"
    assert not list(target.parent.glob("*.horosa-tmp")), "临时文件不留下"

    # 条目真的变了（换了工具面）→ 第一份备份不动，另存一份带时间戳的
    changed_payload = json.loads(json.dumps(payload))
    if style == "toml":
        changed_payload["toml_stdio"] = changed_payload["toml_stdio"].replace("startup_timeout_sec = 120", "startup_timeout_sec = 121")
    elif style == "dsh":
        changed_payload["dsh_patch"] = [*changed_payload["dsh_patch"], {"x_marker": 1}]
    else:
        root = changed_payload.get("root_key") or next(k for k in client_merge._MERGEABLE_ROOT_KEYS if isinstance(changed_payload.get(k), dict))
        changed_payload[root]["horosa"] = {**changed_payload[root]["horosa"], "x_marker": 1}
    third = client_merge._merge_client_config(target, changed_payload)
    assert third["changed"] is True and third["backup"] and third["backup"] != str(first_backup)
    assert Path(third["backup"]).read_bytes() == after_first
    assert first_backup.read_text(encoding="utf-8") == original


def test_timestamped_backups_are_bounded_and_the_first_is_never_pruned(tmp_path: Path) -> None:
    target = tmp_path / "mcp.json"
    target.write_text('{"mcpServers": {}}', encoding="utf-8")
    payload = _build("cursor")
    for index in range(client_merge.MAX_TIMESTAMPED_BACKUPS + 4):
        payload["mcpServers"]["horosa"] = {**payload["mcpServers"]["horosa"], "x_marker": index}
        client_merge._merge_client_config(target, payload)
    backups = _backups(target)
    assert target.with_name("mcp.json.horosa-bak") in backups
    assert json.loads(target.with_name("mcp.json.horosa-bak").read_text(encoding="utf-8")) == {"mcpServers": {}}
    assert len(backups) == 1 + client_merge.MAX_TIMESTAMPED_BACKUPS


def test_a_new_file_gets_no_backup(tmp_path: Path) -> None:
    target = tmp_path / "new" / "mcp.json"
    result = client_merge._merge_client_config(target, _build("cursor"))
    assert (result["changed"], result["backup"]) == (True, None) and _backups(target) == []


def test_codex_toml_goes_through_the_atomic_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Codex TOML 曾是唯一一处 `write_text` 直写：写到一半出错会留下半个 config.toml。"""
    target = tmp_path / "config.toml"
    target.write_text(_ORIGINALS["toml"], encoding="utf-8")
    calls: list[Path] = []
    real_replace = client_merge.fsretry.replace

    def spy(src: Path, dst: Path) -> None:
        calls.append(Path(dst))
        real_replace(src, dst)

    monkeypatch.setattr(client_merge.fsretry, "replace", spy)
    client_merge._merge_client_config(target, _build("codex"))
    assert target.resolve() in [path.resolve() for path in calls]


@pytest.mark.skipif(os.name == "nt", reason="[platform] POSIX 权限位")
def test_openclaw_native_config_is_backed_up_and_keeps_its_mode(tmp_path: Path) -> None:
    target = tmp_path / "openclaw.json"
    original = json.dumps({"models": {"key": "user-secret"}, "mcp": {"servers": {"other": {"command": "x"}}}})
    target.write_text(original, encoding="utf-8")
    target.chmod(0o600)
    block = {"command": "uv", "args": ["run", "horosa-skill", "serve"]}

    client_openclaw._write_openclaw_native_config(path=target, server_name="horosa", server_block=block)
    client_openclaw._write_openclaw_native_config(path=target, server_name="horosa", server_block=block)

    backup = target.with_name("openclaw.json.horosa-bak")
    assert backup.read_text(encoding="utf-8") == original
    assert _backups(target) == [backup], "第二次内容没变，不再留底"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600 and stat.S_IMODE(backup.stat().st_mode) == 0o600
    merged = json.loads(target.read_text(encoding="utf-8"))
    assert merged["models"] == {"key": "user-secret"} and set(merged["mcp"]["servers"]) == {"other", "horosa"}
