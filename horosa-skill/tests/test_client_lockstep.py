"""新客户端 = 一处登记，处处锁步（v0.41.0）。

**为什么旧检查抓不到**：AGENTS §5.15/16 写着「新客户端要同批更新 README×2 矩阵（`check_client_matrix` 锁）、真机 lane、
路径表、占位符表…」，但 `check_client_matrix` 早已不存在——规则写着有人锁，实际没人锁。客户端从 9 家扩到 25 家时，
任何一处漏登记都只会表现为「某客户端在文档里查不到 / lane 从没跑过它 / 第三方事实没人复核」。本文件把每个
`setup --client` 键与它必须出现的每一处钉在一起（负向对照：从任一处删掉一个键即红）。
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from horosa_skill import skill_install
from horosa_skill.surfaces import cli
from horosa_skill.client_config import audit as client_audit
from horosa_skill.client_config import locations as client_locations

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent

_spec = importlib.util.spec_from_file_location("verify_runtime_live", PKG_ROOT / "scripts" / "verify_runtime_live.py")
assert _spec is not None and _spec.loader is not None
live = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(live)

CLIENTS = client_locations._CLIENT_NAMES


def test_every_client_runs_through_setup_on_the_real_lanes() -> None:
    assert tuple(live.CLIENTS) == tuple(CLIENTS)


def test_every_client_has_its_generator_facts() -> None:
    for client in CLIENTS:
        assert client in client_locations._CLIENT_COMPACT_DEFAULT, client
        assert client in client_locations._CLIENT_RESTART_HINTS, client
        assert client in client_audit.CLIENT_PLACEHOLDER_WHITELIST, client
        if client_locations._CLIENT_COMPACT_DEFAULT[client]:
            assert client in client_locations._CLIENT_COMPACT_REASON, client
        for os_name in ("darwin", "linux", "nt"):
            assert client_locations._client_config_locations(client, os_name=os_name, env={}, home=Path("/h"), cwd=Path("/p")), (client, os_name)
        assert client in skill_install.CLIENT_SKILL_DIRS, f"{client}: skill 目录要显式登记（[] = 不读本机 skill），别靠缺省落到共享目录"


@pytest.mark.parametrize("readme", ["README.md", "README_EN.md"])
def test_every_client_has_a_works_with_row(readme: str) -> None:
    rows = [line for line in (REPO_ROOT / readme).read_text(encoding="utf-8").splitlines() if line.startswith("|")]
    for client in CLIENTS:
        assert any(f"setup --client {client}" in row for row in rows), f"{readme}: Works-with 矩阵缺 `setup --client {client}` 那一行"


def test_every_client_is_in_the_examples_index_and_the_setup_help() -> None:
    index = (PKG_ROOT / "examples" / "clients" / "README.md").read_text(encoding="utf-8")
    for client in CLIENTS:
        assert re.search(rf"^\| `{re.escape(client)}` \|", index, re.M), f"examples/clients/README.md 缺 `{client}` 一行"
    from typer.testing import CliRunner

    help_text = CliRunner().invoke(cli.app, ["setup", "--help"], terminal_width=400).stdout
    for client in CLIENTS:
        assert client in help_text, f"`setup --help` 没列出 {client}"


def test_every_client_has_a_dated_third_party_fact() -> None:
    ledger = json.loads((PKG_ROOT / "contracts" / "third_party_facts.json").read_text(encoding="utf-8"))
    subjects = set(ledger["required_subjects"])
    facts = {fact["subject"] for fact in ledger["facts"]}
    for client in CLIENTS:
        assert client in subjects and client in facts, f"{client}: 第三方事实台账缺登记（路径 / 根键 / 超时要有出处与核实日期）"


def test_lockstep_guard_actually_catches_a_missing_lane_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """负向对照：lane 少一个客户端，第一条断言必须红。"""
    monkeypatch.setattr(live, "CLIENTS", tuple(CLIENTS[:-1]))
    with pytest.raises(AssertionError):
        test_every_client_runs_through_setup_on_the_real_lanes()
