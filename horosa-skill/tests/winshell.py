"""在任何平台上按 Windows 终端的规则拆一行命令（v0.50.0-dev）：setup 打印给 Windows 用户粘的命令，本机就能验它在
cmd 和 PowerShell 里各会变成什么 argv。

- `cmd_argv`：cmd.exe 先看引号外有没有 `& | < > ^`、有没有 `%`（变量展开），再按 C 运行库（CommandLineToArgvW）的规则拆。
- `powershell_argv`：PowerShell 参数模式，只认 setup 会写出来的那一小类——光写的词与双引号串；双引号里出现 `$` / `` ` `` / `"`、
  光写的词里出现 PowerShell 的特殊字符，都当成「这条命令在 PowerShell 里不是你以为的样子」报错。光写的 `--` 会被
  npm 装的 claude.ps1 当成参数结束符吃掉，这里照样丢掉。
- `commands`：一段文字里的几条命令（Windows 每条一行；POSIX 用 ` && ` 连）。
"""
from __future__ import annotations

_CMD_META = frozenset("&|<>^")
_PS_META = frozenset("$`'\"&|;,(){}@#<>")


class NotThisShell(ValueError):
    """这行字在这个终端里不会被读成预期的 argv。"""


def crt_argv(line: str) -> list[str]:
    """C 运行库 / CommandLineToArgvW 的拆法（反斜杠只在引号前有意义）。"""
    args: list[str] = []
    i, n = 0, len(line)
    while True:
        while i < n and line[i] in " \t":
            i += 1
        if i >= n:
            return args
        out: list[str] = []
        quoted = False
        while i < n:
            ch = line[i]
            if ch == "\\":
                j = i
                while j < n and line[j] == "\\":
                    j += 1
                count = j - i
                if j < n and line[j] == '"':
                    out.append("\\" * (count // 2))
                    if count % 2:
                        out.append('"')
                        i = j + 1
                    else:
                        i = j
                else:
                    out.append("\\" * count)
                    i = j
            elif ch == '"':
                if quoted and i + 1 < n and line[i + 1] == '"':
                    out.append('"')
                    i += 2
                else:
                    quoted = not quoted
                    i += 1
            elif ch in " \t" and not quoted:
                break
            else:
                out.append(ch)
                i += 1
        args.append("".join(out))


def cmd_argv(line: str) -> list[str]:
    if "%" in line:
        raise NotThisShell(f"cmd 会展开 %…%：{line}")
    quoted = False
    for ch in line:
        if ch == '"':
            quoted = not quoted
        elif ch in _CMD_META and not quoted:
            raise NotThisShell(f"cmd 会把引号外的 {ch!r} 当成命令符号：{line}")
    return crt_argv(line)


def powershell_argv(line: str) -> list[str]:
    args: list[str] = []
    i, n = 0, len(line)
    while i < n:
        while i < n and line[i] in " \t":
            i += 1
        if i >= n:
            break
        parts: list[str] = []
        any_quoted = False
        while i < n and line[i] not in " \t":
            ch = line[i]
            if ch == '"':
                end = line.find('"', i + 1)
                if end < 0:
                    raise NotThisShell(f"PowerShell 里引号没有闭合：{line}")
                segment = line[i + 1:end]
                if "$" in segment or "`" in segment:
                    raise NotThisShell(f"PowerShell 会展开双引号里的 $ / `：{segment}")
                parts.append(segment)
                any_quoted = True
                i = end + 1
            else:
                if ch in _PS_META:
                    raise NotThisShell(f"PowerShell 会把光写的 {ch!r} 当成语法：{line}")
                parts.append(ch)
                i += 1
        value = "".join(parts)
        if value == "--" and not any_quoted:
            continue  # claude.ps1（npm 装的）把光写的 -- 当参数结束符吃掉
        args.append(value)
    return args


def commands(text: str, *, windows: bool) -> list[str]:
    if windows:
        if "&&" in text:
            raise NotThisShell("Windows PowerShell 5.1 不认 &&")
        return [line for line in text.splitlines() if line.strip()]
    return text.split(" && ")


__all__ = ["NotThisShell", "cmd_argv", "commands", "crt_argv", "powershell_argv"]
