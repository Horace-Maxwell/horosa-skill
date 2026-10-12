"""Read and upsert ONE child entry under a top-level YAML mapping key, leaving every other byte alone (v0.41.0).

Why not a YAML library: the package has none (adding a compiled dependency for one client is a supply-chain and
Windows-ARM cost), and a full round-trip would reformat the user's file and drop their comments anyway. Goose keeps its
MCP servers in `~/.config/goose/config.yaml` under `extensions:`; `setup --client goose` only needs to (a) replace or
append the `horosa` child and (b) read entries back for `client check`. Same contract as `jsonc.upsert_server_entry`:
touch our block only, verify by reading it back, refuse shapes we do not understand instead of guessing.

Supported shape (what `goose configure` writes): block mappings, 2+ space indentation, no tabs. Values we write are
JSON (a subset of YAML 1.2 flow syntax), so our own entries always parse back exactly.
"""

from __future__ import annotations

import json
import re
from typing import Any

from horosa_skill.errors import bilingual

__all__ = ["YamlShapeError", "read_children", "upsert_child"]


class YamlShapeError(ValueError):
    """The file is not in the block-mapping shape this module edits; the caller should print the snippet instead."""


_KEY_LINE = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z0-9_.\-\"']+)\s*:(?:\s+(?P<value>.*?))?\s*$")


def _is_noise(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("#")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _unquote_key(key: str) -> str:
    if len(key) >= 2 and key[0] == key[-1] and key[0] in "\"'":
        return key[1:-1]
    return key


def _strip_comment(value: str) -> str:
    """Drop a trailing ` # comment` outside quotes."""
    quote: str | None = None
    for index, char in enumerate(value):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or value[index - 1] in " \t"):
            return value[:index].rstrip()
    return value


def _scalar(raw: str) -> Any:
    raw = _strip_comment(raw).strip()
    if raw == "":
        return None
    try:
        return json.loads(raw)  # our own writes, true/false/null/numbers, "double quoted", [flow], {flow}
    except ValueError:
        pass
    if len(raw) >= 2 and raw[0] == raw[-1] == "'":
        return raw[1:-1].replace("''", "'")
    if raw.startswith("[") and raw.endswith("]"):
        return [_scalar(part) for part in raw[1:-1].split(",") if part.strip()]
    return raw


def _top_level_span(lines: list[str], parent: str) -> tuple[int, int] | None:
    """(index of `parent:` line, index one past its block) or None when the key is absent."""
    start = None
    for index, line in enumerate(lines):
        if not _is_noise(line) and line.startswith("\t"):
            # a tab-indented line has zero *space* indent and would read as a new top-level key — refuse, never guess
            raise YamlShapeError(bilingual("YAML 不允许用 tab 缩进", "tabs are not valid YAML indentation"))
        if _is_noise(line) or _indent(line):
            continue
        match = _KEY_LINE.match(line)
        if start is None:
            if match and _unquote_key(match.group("key")) == parent:
                value = _strip_comment(match.group("value") or "")
                if value not in ("", "{}"):
                    raise YamlShapeError(bilingual(f"`{parent}:` 写成了流式风格（{value[:40]}），不改它",
                                                   f"`{parent}:` is written in flow style ({value[:40]}); not editing it"))
                start = index
        else:
            return start, index
    return (start, len(lines)) if start is not None else None


def _children(lines: list[str], start: int, end: int) -> tuple[int | None, list[tuple[str, int, int]]]:
    """Child indent and [(name, first line, one past last line)] inside the parent block."""
    child_indent: int | None = None
    spans: list[tuple[str, int, int]] = []
    for index in range(start + 1, end):
        line = lines[index]
        if _is_noise(line):
            continue
        if "\t" in line[: _indent(line) + 1]:
            raise YamlShapeError(bilingual("YAML 不允许用 tab 缩进", "tabs are not valid YAML indentation"))
        if child_indent is None:
            child_indent = _indent(line)
        if _indent(line) == child_indent:
            match = _KEY_LINE.match(line)
            if not match:
                raise YamlShapeError(bilingual(f"映射下有认不出的行：{line.strip()[:60]}", f"unexpected line under the mapping: {line.strip()[:60]}"))
            if spans:
                spans[-1] = (spans[-1][0], spans[-1][1], index)
            spans.append((_unquote_key(match.group("key")), index, end))
        elif _indent(line) < child_indent:
            raise YamlShapeError(bilingual("映射下的缩进不一致", "inconsistent indentation under the mapping"))
    # trim trailing blank/comment lines off the last child so an append lands right after its content
    if spans:
        name, first, last = spans[-1]
        while last - 1 > first and _is_noise(lines[last - 1]):
            last -= 1
        spans[-1] = (name, first, last)
    return child_indent, spans


def _parse_body(lines: list[str]) -> dict[str, Any]:
    """Parse the body of one child: `key: scalar`, `key:` + `- item` list, `key:` + one nested mapping level."""
    out: dict[str, Any] = {}
    body = [line for line in lines if not _is_noise(line)]
    if not body:
        return out
    base = _indent(body[0])
    index = 0
    while index < len(body):
        line = body[index]
        match = _KEY_LINE.match(line)
        if not match or _indent(line) != base:
            index += 1
            continue
        key = _unquote_key(match.group("key"))
        value = match.group("value")
        if value is not None and _strip_comment(value) != "":
            out[key] = _scalar(value)
            index += 1
            continue
        nested = []
        index += 1
        while index < len(body) and _indent(body[index]) > base:
            nested.append(body[index])
            index += 1
        if nested and nested[0].lstrip().startswith("- "):
            out[key] = [_scalar(item.lstrip()[2:]) for item in nested if item.lstrip().startswith("- ")]
        elif nested:
            out[key] = _parse_body(nested)
        else:
            out[key] = None
    return out


def read_children(text: str, parent: str) -> dict[str, dict[str, Any]]:
    """{child name: parsed mapping} under top-level `parent:`; {} when the key is absent."""
    lines = text.splitlines()
    span = _top_level_span(lines, parent)
    if span is None:
        return {}
    _child_indent, spans = _children(lines, *span)
    return {name: _parse_body(lines[first + 1:last]) for name, first, last in spans}


def _render_child(name: str, entry: dict[str, Any], indent: int) -> list[str]:
    pad, inner = " " * indent, " " * (indent * 2)
    return [f"{pad}{name}:"] + [f"{inner}{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in entry.items()]


def upsert_child(text: str, parent: str, name: str, entry: dict[str, Any], *, indent: int = 2) -> str:
    """Replace or append `parent.name`; everything else stays byte-identical. Verified by reading it back."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    span = _top_level_span(lines, parent)
    if span is None:
        tail = [""] if lines and lines[-1].strip() else []
        lines = lines + tail + [f"{parent}:"] + _render_child(name, entry, indent)
    else:
        start, end = span
        if _strip_comment(_KEY_LINE.match(lines[start]).group("value") or "") == "{}":  # type: ignore[union-attr]
            lines[start] = f"{parent}:"
        child_indent, spans = _children(lines, start, end)
        block = _render_child(name, entry, child_indent or indent)
        existing = next((item for item in spans if item[0] == name), None)
        if existing is not None:
            _name, first, last = existing
            lines[first:last] = block
        else:
            insert_at = spans[-1][2] if spans else start + 1
            lines[insert_at:insert_at] = block
    out = newline.join(lines) + newline
    if read_children(out, parent).get(name) != entry:
        raise YamlShapeError(bilingual(f"写完回读，`{parent}.{name}` 与写入的不一致", f"after writing, `{parent}.{name}` does not read back as written"))
    return out
