"""`claude mcp …` 的替身：行为照 Claude Code 2.1.304 实测抄（contracts/third_party_facts.json 的 `claude-code.mcp-add`）。

既能当模块用（`FakeClaude(state).run(argv)`，进程内、哪个平台都跑），也能当可执行文件用
（`python fake_claude.py mcp add …`，状态文件按真 CLI 的规则找：`$CLAUDE_CONFIG_DIR/.claude.json`，否则 `~/.claude.json`）。

抄下来的四条行为，条条都是 setup 踩过或会踩的：
1. 同名条目已存在：`add` 与 `add-json` 都拒绝，stderr `MCP server <name> already exists in user config`，退出码 1；
2. `-e/--env` 是可变参数：`-e K=V <name> -- cmd` 会把名字吞成第二个环境变量（`Invalid environment variable format`）；
3. `remove` 不存在的名字：退出码 1；
4. 写出的条目形状：`{"type": "stdio", "command", "args", "env"}`，在顶层 `mcpServers` 下。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


class FakeClaude:
    def __init__(self, state_file: Path, *, fail_add_times: int = 0) -> None:
        self.state_file = Path(state_file)
        self.calls: list[list[str]] = []
        self.fail_add_times = fail_add_times  # 让接下来的 N 次 `add` 以 1 退出（模拟 remove 之后 add 失败）

    # ------------------------------------------------------------------ state
    def _load(self) -> dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def entry(self, name: str) -> dict | None:
        return (self._load().get("mcpServers") or {}).get(name)

    # ------------------------------------------------------------------ commands
    def run(self, command: list[str]) -> "subprocess.CompletedProcess[str]":
        """`command` 含程序名（command[0]），与 subprocess.run 的入参同形。"""
        self.calls.append(list(command))
        code, out, err = self._dispatch(list(command[1:]))
        return subprocess.CompletedProcess(command, code, stdout=out, stderr=err)

    def _dispatch(self, argv: list[str]) -> tuple[int, str, str]:
        if argv[:2] == ["mcp", "add"]:
            return self._add(argv[2:])
        if argv[:2] == ["mcp", "add-json"]:
            return self._add_json(argv[2:])
        if argv[:2] == ["mcp", "remove"]:
            return self._remove(argv[2:])
        return 1, "", f"error: unknown command '{' '.join(argv[:2])}'\n"

    @staticmethod
    def _split_scope(args: list[str]) -> tuple[str, list[str]]:
        rest, scope, index = [], "local", 0
        while index < len(args):
            if args[index] in {"--scope", "-s"} and index + 1 < len(args):
                scope, index = args[index + 1], index + 2
                continue
            if args[index] == "--":
                rest.extend(args[index:])
                break
            rest.append(args[index])
            index += 1
        return scope, rest

    def _add(self, args: list[str]) -> tuple[int, str, str]:
        scope, args = self._split_scope(args)
        positionals: list[str] = []
        env_items: list[str] = []
        index = 0
        while index < len(args):
            token = args[index]
            if token == "--":
                positionals.extend(args[index + 1:])
                break
            if token in {"-e", "--env"}:
                index += 1
                # 可变参数：一直吃到下一个选项或 `--`
                while index < len(args) and args[index] != "--" and not args[index].startswith("-"):
                    env_items.append(args[index])
                    index += 1
                continue
            positionals.append(token)
            index += 1
        env: dict[str, str] = {}
        for item in env_items:
            if "=" not in item:
                return 1, "", f"Invalid environment variable format: {item}, environment variables should be added as: -e KEY1=value1 -e KEY2=value2\n"
            key, _, value = item.partition("=")
            env[key] = value
        if len(positionals) < 2:
            return 1, "", "error: missing required argument 'commandOrUrl'\n"
        name, program, *program_args = positionals
        return self._register(scope, name, {"type": "stdio", "command": program, "args": program_args, "env": env},
                              f"Added stdio MCP server {name} with command: {program} {' '.join(program_args)} to {scope} config\n")

    def _add_json(self, args: list[str]) -> tuple[int, str, str]:
        scope, args = self._split_scope(args)
        if len(args) != 2:
            return 1, "", "error: missing required argument 'json'\n"
        name, text = args
        try:
            entry = json.loads(text)
        except ValueError:
            return 1, "", "Invalid JSON\n"
        return self._register(scope, name, entry, f"Added stdio MCP server {name} to {scope} config\n")

    def _register(self, scope: str, name: str, entry: dict, message: str) -> tuple[int, str, str]:
        if self.fail_add_times > 0:
            self.fail_add_times -= 1
            return 1, "", "simulated failure\n"
        data = self._load()
        servers = data.setdefault("mcpServers", {})
        if name in servers:
            return 1, "", f"MCP server {name} already exists in {scope} config\n"
        servers[name] = entry
        self._save(data)
        return 0, message, ""

    def _remove(self, args: list[str]) -> tuple[int, str, str]:
        scope, args = self._split_scope(args)
        name = args[0] if args else ""
        data = self._load()
        servers = data.get("mcpServers") or {}
        if name not in servers:
            return 1, "", f'No MCP server named "{name}" in {scope} scope\n'
        del servers[name]
        self._save(data)
        return 0, f"Removed MCP server {name} from {scope} config\n", ""


def _state_file_from_environment() -> Path:
    override = (os.environ.get("CLAUDE_CONFIG_DIR") or "").strip()
    return (Path(override) if override else Path.home()) / ".claude.json"


if __name__ == "__main__":
    completed = FakeClaude(_state_file_from_environment()).run(["claude", *sys.argv[1:]])
    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)
    raise SystemExit(completed.returncode)
