"""`yaml_block`（v0.41.0）：Goose 的 config.yaml 只动 `extensions.horosa` 一段。

**为什么旧检查抓不到**：此前没有任何 YAML 客户端；`_merge_client_config` 只认 JSON / TOML。不带 YAML 库、又不能整文件
重排（会抹掉用户注释与别的扩展）——所以锁：其余字节逐字保留；同名条目原位替换；回读等于写入；看不懂的形状拒写。
"""

from __future__ import annotations

import pytest

from horosa_skill import yaml_block

GOOSE = """GOOSE_PROVIDER: openai
# keep me
extensions:
  developer:
    bundled: true
    enabled: true
    name: developer
    timeout: 300
    type: builtin

  memory:
    enabled: false
    args:
      - --flag
      - 'it''s'
    envs:
      A: b   # trailing comment
    type: stdio
GOOSE_MODE: smart_approve
"""
ENTRY = {
    "enabled": True, "name": "horosa", "type": "stdio", "cmd": "/abs/uvx",
    "args": ["--from", "/a b/x.whl", "horosa-skill", "serve", "--transport", "stdio"],
    "envs": {"HOROSA_MCP_COMPACT": "1"}, "timeout": 600,
}


def test_append_keeps_every_other_line_byte_identical() -> None:
    out = yaml_block.upsert_child(GOOSE, "extensions", "horosa", ENTRY)
    added = out.splitlines()
    for line in GOOSE.splitlines():
        added.remove(line)  # ValueError = 用户原有的某一行丢了或被改了
    assert added[0] == "  horosa:" and len(added) == 1 + len(ENTRY), "只多出我们这一段"
    children = yaml_block.read_children(out, "extensions")
    assert children["horosa"] == ENTRY
    assert children["memory"] == {"enabled": False, "args": ["--flag", "it's"], "envs": {"A": "b"}, "type": "stdio"}
    assert out.index("  horosa:") < out.index("GOOSE_MODE"), "插在 extensions 块内，不是文件末尾"


def test_replace_in_place_is_idempotent() -> None:
    once = yaml_block.upsert_child(GOOSE, "extensions", "horosa", ENTRY)
    assert yaml_block.upsert_child(once, "extensions", "horosa", ENTRY) == once
    changed = yaml_block.upsert_child(once, "extensions", "horosa", {**ENTRY, "timeout": 900})
    assert changed == once.replace("timeout: 600", "timeout: 900")


@pytest.mark.parametrize("text", ["", "GOOSE_MODE: auto\n", "extensions: {}\n", "a: 1\r\nextensions:\r\n"])
def test_missing_or_empty_parent_is_created(text: str) -> None:
    out = yaml_block.upsert_child(text, "extensions", "horosa", ENTRY)
    assert yaml_block.read_children(out, "extensions") == {"horosa": ENTRY}
    if "\r\n" in text:
        assert "\r\n" in out and "\n" not in out.replace("\r\n", ""), "保留 CRLF"


@pytest.mark.parametrize("text", ["extensions: {developer: {enabled: true}}\n", "extensions:\n\tdev:\n\t\tx: 1\n"])
def test_shapes_we_do_not_understand_are_refused(text: str) -> None:
    with pytest.raises(yaml_block.YamlShapeError):
        yaml_block.upsert_child(text, "extensions", "horosa", ENTRY)


def test_read_children_on_a_file_without_the_parent_is_empty() -> None:
    assert yaml_block.read_children("GOOSE_MODE: auto\n", "extensions") == {}
