"""Claude Code 用户级注册（`claude mcp add --scope user`）：先读已有条目，再决定不动 / 新增 / 替换。

Claude Code 的命令行只会「新增」：同名条目已存在时 `claude mcp add` 与 `claude mcp add-json` 都以
`MCP server <name> already exists in user config` 退出码 1 结束（2.1.304 实测，见 contracts/third_party_facts.json 的
`claude-code.mcp-add-rerun`）。所以「重跑 setup」必须自己做三件事：读、比、换（remove + add）。

读的是 Claude Code 自己的用户级状态文件（`$CLAUDE_CONFIG_DIR/.claude.json`，缺省 `~/.claude.json`，顶层 `mcpServers`）；
写一律走官方命令，不手改那份文件。读不到（位置变了 / 文件坏了）时退回「先 add，撞上已存在再 remove + add」。
"""
from __future__ import annotations

import json
import ntpath
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from horosa_skill.client_config.env_carry import is_secret_env_name

RunClaude = Callable[[list[str]], "subprocess.CompletedProcess[str]"]

ALREADY_EXISTS_MARKER = "already exists"


def user_config_path(*, env: Mapping[str, str] | None = None, home: Path | None = None) -> Path:
    """Claude Code 用户级状态文件：`CLAUDE_CONFIG_DIR` 设了就在它里面，否则在 home 下。"""
    env = os.environ if env is None else env
    override = (env.get("CLAUDE_CONFIG_DIR") or "").strip()
    if override:
        return Path(override).expanduser() / ".claude.json"
    return (Path(home) if home is not None else Path.home()) / ".claude.json"


def read_user_entry(server_name: str, *, path: Path | None = None) -> dict[str, Any] | None:
    """已注册的用户级条目；没有、读不了或形状不认识都返回 None（调用方退回「先 add 再看」）。"""
    target = path or user_config_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    entry = servers.get(server_name) if isinstance(servers, dict) else None
    return dict(entry) if isinstance(entry, dict) else None


def desired_entry(stdio_command: list[str], env: Mapping[str, str]) -> dict[str, Any]:
    """`claude mcp add` 会写出的条目形状（type / command / args / env 四个键，env 为空也写 `{}`）。"""
    return {"type": "stdio", "command": stdio_command[0], "args": list(stdio_command[1:]), "env": dict(env)}


def _canonical(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "type": str(entry.get("type") or "stdio"),
        "command": entry.get("command"),
        "args": list(entry.get("args") or []),
        "env": dict(entry.get("env") or {}),
    }


def entry_changes(existing: Mapping[str, Any], desired: Mapping[str, Any]) -> list[dict[str, Any]]:
    """两个条目哪里不同：`type` / `command` / `args` 给前后值；env 只按变量给（值可能是用户自己写的，不回显）。"""
    before, after = _canonical(existing), _canonical(desired)
    changes: list[dict[str, Any]] = [
        {"field": field, "before": before[field], "after": after[field]}
        for field in ("type", "command", "args") if before[field] != after[field]
    ]
    env_before, env_after = before["env"], after["env"]
    for name in sorted(set(env_before) | set(env_after)):
        if env_before.get(name) != env_after.get(name):
            action = "added" if name not in env_before else "removed" if name not in env_after else "changed"
            changes.append({"field": f"env.{name}", "change": action})
    return changes


def add_command(claude_bin: str, server_name: str, stdio_command: list[str], env: Mapping[str, str]) -> list[str]:
    """`claude mcp add --scope user <name> -e K=V … -- <cmd…>`。

    🔴 名字必须排在 `-e` **前面**：`-e` 是可变参数，写成 `-e K=V <name> -- …` 会把名字当成第二个环境变量吞掉
    （`Invalid environment variable format: <name>`，退出码 1）。这也是 `claude mcp add --help` 里的示例顺序。
    """
    flags = [item for key, value in env.items() for item in ("-e", f"{key}={value}")]
    return [claude_bin, "mcp", "add", "--scope", "user", server_name, *flags, "--", *stdio_command]


def remove_command(claude_bin: str, server_name: str) -> list[str]:
    return [claude_bin, "mcp", "remove", "--scope", "user", server_name]


def add_json_command(claude_bin: str, server_name: str, entry: Mapping[str, Any]) -> list[str]:
    """把一个条目原样注册回去（恢复旧条目用；同名存在时它和 `add` 一样会拒绝）。"""
    return [claude_bin, "mcp", "add-json", "--scope", "user", server_name, json.dumps(dict(entry), ensure_ascii=False)]


# Windows 上粘命令的人用 PowerShell（5.1 / 7）还是 cmd，看不出来（v0.50.0-dev，windows-smoke）。此前一律 list2cmdline：
# 那是 cmd / C 运行库的规则，JSON 参数写成 "{\"type\": …}"——PowerShell 里反斜杠不是转义符，引号在第一个 \" 处就断了，
# 粘进去 `Invalid JSON`；`&&` 在 Windows PowerShell 5.1 里是语法错误；npm 装的 claude 在 PowerShell 里是 claude.ps1，
# 光写的 `--` 会被 PowerShell 当成「参数到此为止」吃掉，`-e` 就把后面的命令吞成环境变量。
# 两边都认的写法：只含 _WINDOWS_BARE 里字符的参数原样写；其余（以及 `--`）用双引号括起来——双引号里 cmd 只认 %，
# PowerShell 只认 $ 和 `，两边都不拿反斜杠转义。含 " $ ` % 或以 \ 结尾的参数没有两边都对的写法，整条退回 cmd 写法。
_WINDOWS_BARE = re.compile(r"[A-Za-z0-9_.:\\/=+-]+\Z")
_WINDOWS_NO_COMMON_FORM = frozenset('"$`%')


def _windows_token(arg: str) -> str | None:
    if arg != "--" and _WINDOWS_BARE.match(arg):
        return arg
    if any(ch in _WINDOWS_NO_COMMON_FORM for ch in arg) or arg.endswith("\\"):
        return None
    return f'"{arg}"'


def shell_text(command: list[str], *, os_name: str | None = None) -> str:
    """把一条命令写成**能直接粘进终端**的一行：POSIX 用 shlex；Windows 用 PowerShell 与 cmd 都认的写法
    （见上；没有共同写法时退回 cmd 的 list2cmdline）。"""
    if (os_name or os.name) == "nt":
        tokens = [_windows_token(arg) for arg in command]
        if all(token is not None for token in tokens):
            return " ".join(token for token in tokens if token is not None)
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def shell_sequence(lines: list[str], *, os_name: str | None = None) -> str:
    """几条命令依次执行：POSIX 用 `&&`；Windows 每条一行（Windows PowerShell 5.1 不认 `&&`，cmd 与 PowerShell 都认换行）。"""
    return ("\n" if (os_name or os.name) == "nt" else " && ").join(lines)


def restore_command(claude_bin: str, server_name: str, entry: Mapping[str, Any]) -> list[str]:
    """把旧条目装回去的命令。能用 `add` 表达的（stdio，只有 type / command / args / env）就用 `add`：参数里没有 JSON，
    哪个终端都粘得进去；`add` 写出的就是这四个键。表达不了的（别的键、http 条目）才用 `add-json`。"""
    command, args, env = entry.get("command"), entry.get("args", []), entry.get("env", {})
    if (set(entry) <= {"type", "command", "args", "env"} and entry.get("type", "stdio") == "stdio"
            and isinstance(command, str) and command and isinstance(args, list) and all(isinstance(a, str) for a in args)
            and isinstance(env, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in env.items())):
        return add_command(claude_bin, server_name, [command, *args], env)
    return add_json_command(claude_bin, server_name, entry)


def _program_name(claude_bin: str, *, os_name: str | None = None) -> str:
    """给人看的命令里写程序名，不写本机绝对路径。Windows 上 which 找到的是 `claude.CMD` / `claude.exe`：写 `claude`，
    让用户的终端自己按 PATHEXT 找（PowerShell 里 npm 装的是 claude.ps1，cmd 里是 claude.cmd）。"""
    if not claude_bin:
        return "claude"
    if (os_name or os.name) == "nt":
        stem, ext = ntpath.splitext(ntpath.basename(claude_bin))
        return stem if ext.lower() in {".exe", ".cmd", ".bat", ".com", ".ps1"} else stem + ext
    return Path(claude_bin).name


def _tail(text: str | None) -> str:
    return (text or "").strip()[-500:]


def _without_secret_values(entry: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """给人看的那份旧条目：名字像密钥的 env 值换成 `<NAME>` 占位（setup 的输出会进日志 / 会被贴进 issue）。"""
    env = dict(entry.get("env") or {})
    hidden = sorted(name for name in env if is_secret_env_name(name))
    if not hidden:
        return dict(entry), []
    return {**entry, "env": {name: (f"<{name}>" if name in hidden else value) for name, value in env.items()}}, hidden


def register_user_server(
    *, claude_bin: str, server_name: str, stdio_command: list[str], env: Mapping[str, str],
    run: RunClaude, config_path: Path | None = None, os_name: str | None = None,
) -> dict[str, Any]:
    """让用户级条目等于期望值，并说清做了什么。

    成功返回 `{ok: True, status, executed, touched, command, commands, rollback, changes?}`：
    - `unchanged`：已有条目与期望一致，一条命令都不跑；
    - `created`：此前没有，`add` 一次；
    - `updated`：此前有且不同，`remove` + `add`，`changes` 列出差异；`add` 失败时把旧条目用 `add-json` 装回去。
    失败返回 `{ok: False, failed_command, returncode, stdout, stderr, touched, restored_previous?, restore_command?}`；
    `touched` = 用户原来的注册此刻是不是已经变了（决定 setup 失败包里的 `config_untouched`）。
    `rollback` / `restore_command` 是能直接粘进终端的命令（Windows 上 PowerShell 与 cmd 都能粘；多条时每条一行）；
    旧条目 env 里名字像密钥的值不回显（`rollback_redacted` 点名）。`os_name` 只给测试用（在本机走 Windows 那一支）。
    """
    program = _program_name(claude_bin, os_name=os_name)

    def display(command: list[str]) -> str:  # 给人看的命令不带本机绝对路径
        return shell_text([program, *command[1:]], os_name=os_name)

    wanted = desired_entry(stdio_command, env)
    add = add_command(claude_bin, server_name, stdio_command, env)
    remove = remove_command(claude_bin, server_name)
    existing = read_user_entry(server_name, path=config_path)
    report: dict[str, Any] = {"command": display(add), "commands": [], "executed": False, "touched": False}

    def call(command: list[str]) -> "subprocess.CompletedProcess[str]":
        report["commands"].append(display(command))
        report["executed"] = True
        try:
            return run(command)
        except (OSError, subprocess.TimeoutExpired) as exc:
            # 起不来 / 超时也按「这条命令失败」走同一条路：中途（remove 之后）抛出去的话，旧条目就没人装回去了。
            return subprocess.CompletedProcess(command, 127, "", f"{type(exc).__name__}: {exc}")

    def failed(command: list[str], completed: "subprocess.CompletedProcess[str]", **extra: Any) -> dict[str, Any]:
        return {**report, "ok": False, "failed_command": display(command), "returncode": completed.returncode,
                "stdout": _tail(completed.stdout), "stderr": _tail(completed.stderr), **extra}

    if existing is not None and _canonical(existing) == _canonical(wanted):
        return {**report, "ok": True, "status": "unchanged", "rollback": display(remove)}

    replaced_blind = False
    if existing is None:
        completed = call(add)
        if completed.returncode == 0:
            report["touched"] = True
            return {**report, "ok": True, "status": "created", "rollback": display(remove), "stdout": _tail(completed.stdout)}
        if ALREADY_EXISTS_MARKER not in f"{completed.stderr or ''}{completed.stdout or ''}".lower():
            return failed(add, completed)
        # 条目在，但状态文件没读到（位置变了）：照样替换，只是说不出旧值。
        replaced_blind = True

    removed = call(remove)
    if removed.returncode != 0:
        return failed(remove, removed)
    report["touched"] = True
    completed = call(add)
    shown_previous, hidden = _without_secret_values(existing) if existing is not None else ({}, [])
    restore_shown = display(restore_command(claude_bin, server_name, shown_previous)) if existing is not None else None
    redacted = {"rollback_redacted": hidden} if hidden else {}
    if completed.returncode != 0:
        restored = None
        if existing is not None:
            # 真正装回去的是原条目（含原值）；`commands` 里记的是不带密钥值的那份。
            report["commands"].append(restore_shown)
            try:
                restored = run(add_json_command(claude_bin, server_name, existing)).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                restored = False
            if restored:
                report["touched"] = False
        return failed(add, completed, restored_previous=restored,
                      **({"restore_command": restore_shown} if restore_shown else {}), **redacted)
    changes = entry_changes(existing, wanted) if existing is not None else []
    rollback = shell_sequence([display(remove), *([restore_shown] if restore_shown else [])], os_name=os_name)
    return {
        **report, "ok": True, "status": "updated", "changes": changes, "rollback": rollback,
        "stdout": _tail(completed.stdout), **redacted,
        **({"previous_entry_unreadable": True} if replaced_blind else {}),
    }
