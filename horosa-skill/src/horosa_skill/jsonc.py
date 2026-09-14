"""JSON-with-comments 的容错读取与**保注释**的条目写入（v0.38.1 C4）。

为什么：Zed 的 settings.json 出厂模板、VS Code 的 mcp.json 都允许 `//` / `/* */` 注释与尾逗号。
此前 `client config --write` / `setup` 用 `json.loads` 读它们 → JSONDecodeError → 拒写（「不是合法 JSON」），
用户只能手贴。整文件重排也不行：那会抹掉注释（用户的配置是他的）。

做法：读用 `loads()`（剥注释、尾逗号后再 json.loads）；写用 `upsert_server_entry()` —— 只在文本里定位
根键块 / 同名条目，替换或插入一段，其余**字节原样**。写完再用 `loads()` 回读验证。
"""
from __future__ import annotations

import json
from typing import Any

from horosa_skill.errors import bilingual

__all__ = ["strip_comments", "loads", "is_jsonc_only", "upsert_server_entry"]


def _scan(text: str):
    """逐字符产出 (index, char, in_string)；注释内的字符不产出（调用方看不到它们）。"""
    i, n = 0, len(text)
    in_string = False
    escaped = False
    while i < n:
        ch = text[i]
        if in_string:
            yield i, ch, True
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            yield i, ch, True
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        yield i, ch, False
        i += 1


def strip_comments(text: str) -> str:
    """去掉注释与尾逗号，其余字符（含字符串内容）原样；结果可交给 json.loads。"""
    out: list[str] = []
    pending_comma = -1  # 位置：out 里最近一个未决定的结构逗号
    for _, ch, in_string in _scan(text):
        if in_string:
            out.append(ch)
            pending_comma = -1
            continue
        if ch == ",":
            out.append(ch)
            pending_comma = len(out) - 1
            continue
        if ch in "}]" and pending_comma >= 0:
            del out[pending_comma]
            pending_comma = -1
        elif not ch.isspace():
            pending_comma = -1
        out.append(ch)
    return "".join(out)


def loads(text: str) -> Any:
    return json.loads(strip_comments(text))


def is_jsonc_only(text: str) -> bool:
    """严格 JSON 解析不了、但按 JSONC 能解析 → 文件里有注释 / 尾逗号，写入必须走文本级插入。"""
    if not text.strip():
        return False
    try:
        json.loads(text)
        return False
    except ValueError:
        pass
    try:
        loads(text)
        return True
    except ValueError:
        return False


def _object_members(text: str, open_index: int) -> tuple[list[tuple[str, int, int, int]], int]:
    """从 `open_index`（一个 `{`）起解析该对象的直接成员：[(key, key_start, value_start, value_end_exclusive)]，
    以及对象闭括号的下标。注释被跳过；嵌套结构按深度匹配。"""
    assert text[open_index] == "{"
    members: list[tuple[str, int, int, int]] = []
    depth = 0
    key: str | None = None
    key_start = -1
    value_start = -1
    expecting = "key"
    string_buf: list[str] = []
    string_start = -1
    prev_in_string = False
    for i, ch, in_string in _scan(text[open_index:]):
        i += open_index
        if in_string:
            if not prev_in_string:
                string_start = i
                string_buf = []
            string_buf.append(ch)
            prev_in_string = True
            if depth == 1 and expecting == "key" and len(string_buf) > 1 and ch == '"' and string_buf[-2:] != ['\\', '"']:
                # 字符串闭合：是键
                try:
                    key = json.loads("".join(string_buf))
                except ValueError:
                    key = "".join(string_buf).strip('"')
                key_start = string_start
                expecting = "colon"
            elif depth == 1 and expecting == "value" and value_start < 0:
                value_start = string_start
            continue
        if prev_in_string:
            prev_in_string = False
            if depth == 1 and expecting == "value_scalar":
                pass
        if ch == "{" or ch == "[":
            if depth == 1 and expecting == "value" and value_start < 0:
                value_start = i
            depth += 1
            if depth == 1:
                expecting = "key"
            continue
        if ch == "}" or ch == "]":
            depth -= 1
            if depth == 1 and value_start >= 0 and key is not None:
                # 嵌套值结束
                if expecting == "value":
                    members.append((key, key_start, value_start, i + 1))
                    key, key_start, value_start, expecting = None, -1, -1, "comma"
                continue
            if depth == 0:
                if key is not None and value_start >= 0:
                    members.append((key, key_start, value_start, i))
                return members, i
            continue
        if depth != 1:
            continue
        if expecting == "colon" and ch == ":":
            expecting = "value"
            continue
        if expecting == "value":
            if ch.isspace():
                continue
            if value_start < 0:
                value_start = i
            if ch == ",":
                members.append((key or "", key_start, value_start, i))
                key, key_start, value_start, expecting = None, -1, -1, "key"
            continue
        if expecting == "comma" and ch == ",":
            expecting = "key"
            continue
        if expecting == "key" and ch == ",":
            continue
    raise ValueError(bilingual("JSON 对象没有闭合（括号不配对）。", "Unterminated JSON object (unbalanced braces)."))


def _trim_value_end(text: str, start: int, end: int) -> int:
    """标量值的结束位置去掉尾随空白。"""
    while end > start and text[end - 1].isspace():
        end -= 1
    return end


def _first_open_brace(text: str) -> int:
    for i, ch, in_string in _scan(text):
        if not in_string and ch == "{":
            return i
    raise ValueError(bilingual("文件顶层不是 JSON 对象。", "The document is not a JSON object."))


def _indent_of(text: str, index: int) -> str:
    line_start = text.rfind("\n", 0, index) + 1
    return text[line_start:index][: len(text[line_start:index]) - len(text[line_start:index].lstrip())]


def upsert_server_entry(text: str, root_key: str, name: str, entry: Any, *, indent: int = 2) -> str:
    """把 `<root_key>.<name> = entry` 写进 JSONC 文本，**只动这一段**：注释、别的键、空行全部原样。

    - 根键块存在、同名条目存在 → 替换该条目的值；
    - 根键块存在、无同名条目 → 插到块的开头；
    - 根键块不存在 → 插到顶层对象末尾。
    """
    top = _first_open_brace(text)
    members, top_close = _object_members(text, top)
    root = next((m for m in members if m[0] == root_key), None)
    unit = " " * indent
    if root is not None:
        _, _, value_start, value_end = root
        if text[value_start] != "{":
            raise ValueError(bilingual(f"`{root_key}` 的值不是对象。", f"`{root_key}` is not an object."))
        inner, inner_close = _object_members(text, value_start)
        existing = next((m for m in inner if m[0] == name), None)
        block_indent = _indent_of(text, root[1])
        entry_indent = block_indent + unit
        rendered = json.dumps(entry, ensure_ascii=False, indent=indent)
        rendered = ("\n" + entry_indent).join(rendered.splitlines())
        if existing is not None:
            _, key_start, ex_value_start, ex_value_end = existing
            ex_value_end = _trim_value_end(text, ex_value_start, ex_value_end)
            return text[:ex_value_start] + rendered + text[ex_value_end:]
        head = text[: value_start + 1]
        tail = text[value_start + 1:]
        if inner:
            return head + "\n" + entry_indent + json.dumps(name, ensure_ascii=False) + ": " + rendered + "," + tail
        return head + "\n" + entry_indent + json.dumps(name, ensure_ascii=False) + ": " + rendered + "\n" + block_indent + tail.lstrip(" \t")
    # 没有根键：插在顶层对象末尾
    block_indent = unit
    rendered = json.dumps({name: entry}, ensure_ascii=False, indent=indent)
    rendered = ("\n" + block_indent).join(rendered.splitlines())
    before = text[:top_close].rstrip()
    needs_comma = bool(members) and not before.endswith(",") and not before.endswith("{")
    insertion = ("," if needs_comma else "") + "\n" + block_indent + json.dumps(root_key) + ": " + rendered + "\n"
    return before + insertion + text[top_close:]
