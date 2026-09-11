"""SKILL.md 的 shell 契约 ↔ Typer app（v0.38.0 B5）。

「Shell-only agents (no MCP)」与「First 3 commands on a fresh machine」两节是 shell-only agent 抄命令的地方；
一条写错的 `--flag` 或子命令，agent 会拿到 Typer 的 usage 报错并判定「工具坏了」（issue #5 的模式）。
本文件把两节里每条 `horosa-skill …` 命令逐 token 对到真实的 Click 命令树上：子命令必须存在、每个 `--flag`
必须是该命令的选项（含 `--no-x` 反向旗标）。负向对照：`--nope` / 未知子命令必红。
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import click
import typer

from horosa_skill.surfaces.cli import app

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "horosa-agent" / "SKILL.md"
MIRROR = ROOT / ".agents" / "skills" / "horosa-agent" / "SKILL.md"
SECTIONS = ("## Shell-only agents (no MCP)", "## First 3 commands on a fresh machine")
# `horosa-skill <command …>` preceded by line start / whitespace / backtick / "(" — never by "/" (a path) —
# and followed by a word (so `…/horosa-skill && cd` in a clone line is not a command).
COMMAND = re.compile(r"(?:^|[\s`(])horosa-skill\s+([a-z][\w-]*[^`|#\n]*)")


def _sections(text: str, headings: tuple[str, ...] = SECTIONS) -> dict[str, str]:
    found: dict[str, str] = {}
    for heading in headings:
        index = text.find(heading)
        if index < 0:
            continue
        rest = text[index + len(heading):]
        nxt = re.search(r"\n## ", rest)
        found[heading] = rest[: nxt.start()] if nxt else rest
    return found


def audit_commands(text: str) -> list[str]:
    """Every `horosa-skill …` in `text` must resolve to a real command with real options."""
    root = typer.main.get_command(app)
    problems: list[str] = []
    for match in COMMAND.finditer(text):
        try:
            tokens = shlex.split(match.group(1), posix=True)
        except ValueError:
            tokens = match.group(1).split()
        command: click.Command | None = root
        path: list[str] = []
        index = 0
        while index < len(tokens) and isinstance(command, click.Group):
            name = tokens[index]
            if name.startswith("-"):
                break
            child = command.commands.get(name)
            if child is None:
                problems.append(f"unknown command `horosa-skill {' '.join([*path, name])}`")
                command = None
                break
            command = child
            path.append(name)
            index += 1
        if command is None:
            continue
        if isinstance(command, click.Group):
            problems.append(f"`horosa-skill {' '.join(path)}` is a command group, not a runnable command")
            continue
        allowed = {opt for param in command.params for opt in (*param.opts, *param.secondary_opts)} | {"--help"}
        for token in tokens[index:]:
            if token.startswith("--"):
                flag = token.split("=", 1)[0]
                if flag not in allowed:
                    problems.append(f"`horosa-skill {' '.join(path)}` has no option `{flag}`")
    return problems


def test_both_shell_sections_exist_in_the_policy_source() -> None:
    assert set(_sections(SKILL.read_text(encoding="utf-8"))) == set(SECTIONS)
    assert SECTIONS[0] in _sections(MIRROR.read_text(encoding="utf-8")), "the Codex mirror carries the shell contract too"


def test_every_command_and_flag_in_the_shell_sections_exists() -> None:
    for path in (SKILL, MIRROR):
        for heading, body in _sections(path.read_text(encoding="utf-8")).items():
            assert COMMAND.search(body), f"{path.name} {heading}: no horosa-skill command to check?"
            assert audit_commands(body) == [], f"{path.name} {heading}"


def test_audit_catches_an_unknown_flag_and_an_unknown_command() -> None:
    """负向对照：守卫必须真能抓。"""
    problems = audit_commands("run `horosa-skill tool run qimen --input x.json --nope` then `horosa-skill nope --x`")
    assert any("--nope" in p for p in problems), problems
    assert any("unknown command `horosa-skill nope`" in p for p in problems), problems
    assert audit_commands("`horosa-skill tool` alone") == ["`horosa-skill tool` is a command group, not a runnable command"]


def test_audit_ignores_paths_and_shell_glue() -> None:
    text = "git clone https://github.com/x/horosa-skill && cd horosa-skill/horosa-skill && uv sync\n<repo>/horosa-skill horosa-skill doctor"
    assert audit_commands(text) == []
    assert len(list(COMMAND.finditer(text))) == 1
