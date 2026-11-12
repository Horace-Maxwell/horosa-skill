"""MCP-05 / E-03：终端里设着的「用哪套引擎、哪份数据」变量必须进客户端条目的 env；密钥永不进。

守的是一类问题，不是一个变量：
- `config.ENV_FLAG_REGISTRY` 的每个变量都得在 env_carry 的三张表之一里表态（新增变量时不会默默漏掉）；
- 每一种带 env 的客户端格式都真的写了（逐个格式建 payload、在序列化结果里找值）；
- 不带 env 的格式（mcporter / openclaw）点名告诉用户该在哪儿设。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from horosa_skill import config
from horosa_skill.client_config import env_carry
from horosa_skill.client_config import payload as client_payload
from horosa_skill.client_config.locations import _CLIENT_NAMES
from horosa_skill.surfaces import runtime_helpers

_NO_ENV_FORMATS = ("mcporter", "openclaw")  # `client config --format` 认、但条目没有 env 字段的两种
_ALL_FORMATS = (*_CLIENT_NAMES, *_NO_ENV_FORMATS)


@pytest.fixture
def clean_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    """把会被带走 / 点名的变量从测试进程里清掉（conftest 为了钉死后端设了几个），每条用例自己设要看的。"""
    for name in (*env_carry.CARRIED, *env_carry.NOT_CARRIED, *env_carry.FLAG_OWNED):
        monkeypatch.delenv(name, raising=False)


def _payload(format_name: str) -> dict:
    payload, _command, _env = client_payload._build_client_config_payload(
        format_name=format_name, skill_root=runtime_helpers._package_root(), server_name="horosa",
        launcher="uvx-wheel", surface="auto",
    )
    return payload


# ---------------------------------------------------------------- the three tables


def test_every_registered_variable_is_classified_exactly_once() -> None:
    tables = {"CARRIED": set(env_carry.CARRIED), "NOT_CARRIED": set(env_carry.NOT_CARRIED), "FLAG_OWNED": set(env_carry.FLAG_OWNED)}
    registry = set(config.ENV_FLAG_REGISTRY)
    classified = set().union(*tables.values())
    assert registry - classified == set(), "新登记的环境变量没有在 client_config/env_carry.py 里表态：客户端需不需要它？"
    assert classified - registry == set(), "env_carry 里有登记表没有的变量名（改名 / 删除后没跟上）"
    names = sorted(tables)
    overlaps = {f"{a}&{b}": sorted(tables[a] & tables[b]) for i, a in enumerate(names) for b in names[i + 1:] if tables[a] & tables[b]}
    assert overlaps == {}
    assert set(env_carry.NOT_CARRIED.values()) <= {"behaviour", "secret", "serve", "install", "diagnostics", "internal"}


def test_secret_looking_names_are_never_carried_whatever_the_tables_say(monkeypatch: pytest.MonkeyPatch) -> None:
    secret_named = sorted(name for name in config.ENV_FLAG_REGISTRY if env_carry.is_secret_env_name(name))
    assert {"HOROSA_MCP_TOKEN", "HOROSA_JEV_API_KEY"} <= set(secret_named)
    assert [name for name in secret_named if env_carry.NOT_CARRIED.get(name) != "secret"] == []
    assert [name for name, group in env_carry.NOT_CARRIED.items() if group == "secret" and not env_carry.is_secret_env_name(name)] == []
    # 第二道闸：就算有人把一个像密钥的名字放进了 CARRIED，carried_env 也不带它
    monkeypatch.setitem(env_carry.CARRIED, "HOROSA_MCP_TOKEN", "value")
    everything = {name: "/somewhere/x" for name in config.ENV_FLAG_REGISTRY}
    carried = env_carry.carried_env(everything)
    assert sorted(name for name in carried if env_carry.is_secret_env_name(name)) == []
    assert "HOROSA_MCP_TOKEN" not in env_carry.shell_only(everything), "点名的那张表也不提密钥"
    for name in ("MY_API_KEY", "GITHUB_TOKEN", "DB_PASSWORD", "X_PRIVATE_KEY", "SESSION_COOKIE", "client_secret"):
        assert env_carry.is_secret_env_name(name), name
    for name in ("HOROSA_RUNTIME_ROOT", "HOROSA_TOOLSETS", "PATH", "HOROSA_PORTS"):
        assert not env_carry.is_secret_env_name(name), name


def test_only_values_that_differ_from_the_default_are_carried_and_paths_become_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    defaults = env_carry._defaults()
    assert env_carry.carried_env({}) == {}
    assert env_carry.carried_env(dict(defaults)) == {}, "设成缺省值 = 没设：配置与不设时逐字节相同"
    assert env_carry.carried_env({"HOROSA_SERVER_ROOT": "http://127.0.0.1:9999/", "HOROSA_RUNTIME_ROOT": "  "}) == {}
    assert env_carry.carried_env({"HOROSA_RUNTIME_ROOT": "${user_config.runtime_root}"}) == {}, "宿主没展开的占位符当没设"
    carried = env_carry.carried_env({
        "HOROSA_RUNTIME_ROOT": "rel/runtime", "HOROSA_SERVER_ROOT": "http://127.0.0.1:19999/",
        "HOROSA_NODE_BIN": "node", "HOROSA_REPORT_OUTPUT_ROOTS": os.pathsep.join(["out a", str(tmp_path / "b")]),
        "HOROSA_TOOLSETS": "astro", "HOROSA_MCP_TOKEN": "placeholder", "HOROSA_MCP_COMPACT": "1", "UNRELATED": "x",
    })
    assert carried == {
        "HOROSA_RUNTIME_ROOT": str((tmp_path / "rel/runtime").resolve()),
        "HOROSA_REPORT_OUTPUT_ROOTS": os.pathsep.join([str((tmp_path / "out a").resolve()), str((tmp_path / "b").resolve())]),
        "HOROSA_NODE_BIN": "node",
        "HOROSA_SERVER_ROOT": "http://127.0.0.1:19999",
    }
    assert env_carry.carried_env({"HOROSA_NODE_BIN": os.path.join("tools", "node")}) == {
        "HOROSA_NODE_BIN": str((tmp_path / "tools" / "node").resolve())}
    assert env_carry.shell_only({"HOROSA_TOOLSETS": "astro", "HOROSA_CLARIFY": " ", "HOROSA_SKILL_LOG_LEVEL": "DEBUG"}) == ["HOROSA_TOOLSETS"]


def test_minimal_client_env_keeps_system_and_install_plumbing_and_drops_the_shell() -> None:
    shell = {
        "PATH": "/usr/bin", "HOME": "/home/u", "SystemRoot": "C:\\Windows", "LANG": "zh_CN.UTF-8",
        "HTTPS_PROXY": "http://proxy.invalid:3128", "https_proxy": "http://proxy.invalid:3128", "UV_INDEX_URL": "https://mirror.invalid/simple",
        "XDG_CACHE_HOME": "/home/u/.cache", "SSL_CERT_FILE": "/etc/ca.pem",
        "HOROSA_RUNTIME_ROOT": "/data", "HOROSA_MCP_TOKEN": "placeholder", "HOROSA_TOOLSETS": "astro",
        "PYTHONPATH": "/src", "VIRTUAL_ENV": "/venv", "ANY_API_KEY": "placeholder", "CLAUDE_CONFIG_DIR": "/c",
    }
    kept = set(env_carry.minimal_client_env(shell))
    assert kept == {"PATH", "HOME", "SystemRoot", "LANG", "HTTPS_PROXY", "https_proxy", "UV_INDEX_URL", "XDG_CACHE_HOME", "SSL_CERT_FILE"}


# ---------------------------------------------------------------- every client format


def test_the_client_list_this_file_sweeps_is_the_real_one() -> None:
    assert len(_CLIENT_NAMES) >= 25 and not set(_NO_ENV_FORMATS) & set(_CLIENT_NAMES)


@pytest.mark.parametrize("format_name", _CLIENT_NAMES)
def test_every_format_with_an_env_block_writes_the_carried_variables_and_no_secret(
    format_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_shell: None,
) -> None:
    runtime_root, data_dir = tmp_path / "运行时 root", tmp_path / "data dir"
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("HOROSA_SERVER_ROOT", "http://127.0.0.1:18861")
    monkeypatch.setenv("HOROSA_CHART_SERVER_ROOT", "http://127.0.0.1:18862")
    monkeypatch.setenv("HOROSA_MCP_TOKEN", "placeholder-token-value")
    monkeypatch.setenv("HOROSA_JEV_API_KEY", "placeholder-key-value")
    monkeypatch.setenv("HOROSA_TOOLSETS", "astro")

    payload = _payload(format_name)
    text = json.dumps(payload, ensure_ascii=False)

    for value in (str(runtime_root.resolve()), str(data_dir.resolve()), "http://127.0.0.1:18861", "http://127.0.0.1:18862"):
        # JSON 里再嵌一层字符串（TOML 片段 / 命令行）时反斜杠与非 ASCII 会被再转义一次：两种写法认其一
        assert value in text or json.dumps(value, ensure_ascii=False)[1:-1] in text or json.dumps(json.dumps(value))[2:-2] in text, (format_name, value)
    assert "placeholder-token-value" not in text and "placeholder-key-value" not in text
    assert payload["carried_env"] == ["HOROSA_RUNTIME_ROOT", "HOROSA_SKILL_DATA_DIR", "HOROSA_SERVER_ROOT", "HOROSA_CHART_SERVER_ROOT"]
    # 行为开关：不写，但点名
    assert payload["shell_only_env"] == ["HOROSA_TOOLSETS"]
    assert any("HOROSA_TOOLSETS" in warning and "没有" in warning for warning in payload["warnings"])
    assert '"HOROSA_TOOLSETS": "astro"' not in text and "HOROSA_TOOLSETS=astro" not in text


@pytest.mark.parametrize("format_name", _NO_ENV_FORMATS)
def test_formats_without_an_env_block_say_where_to_set_the_variables(
    format_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_shell: None,
) -> None:
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "rt"))
    payload = _payload(format_name)
    assert "carried_env" not in payload, "没写进去就不能说写了"
    assert any("HOROSA_RUNTIME_ROOT" in warning and "启动 serve 的环境" in warning for warning in payload["warnings"])


@pytest.mark.parametrize("format_name", _ALL_FORMATS)
def test_a_shell_with_nothing_set_adds_no_keys(format_name: str, clean_shell: None) -> None:
    payload = _payload(format_name)
    assert "carried_env" not in payload and "shell_only_env" not in payload


def test_codex_toml_carries_the_extra_variables_as_table_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_shell: None) -> None:
    import tomllib

    monkeypatch.setenv("HOROSA_SERVER_ROOT", "http://127.0.0.1:18861")
    monkeypatch.setenv("HOROSA_USER_KNOWLEDGE_DIR", str(tmp_path / 'notes "quoted" 笔记'))
    payload = _payload("codex")
    parsed = tomllib.loads(payload["toml_stdio"])
    env = parsed["mcp_servers"]["horosa"]["env"]
    assert env["HOROSA_SERVER_ROOT"] == "http://127.0.0.1:18861"
    assert env["HOROSA_USER_KNOWLEDGE_DIR"] == str((tmp_path / 'notes "quoted" 笔记').resolve()), "带引号 / 非 ASCII 的路径在 TOML 里原样读回"
    assert {"HOROSA_RUNTIME_ROOT", "HOROSA_SKILL_DATA_DIR"} <= set(env), "两个根恒写（v0.38.1 C6 的既定选择）"
