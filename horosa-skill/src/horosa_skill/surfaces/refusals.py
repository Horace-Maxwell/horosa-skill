"""命令拒绝执行的出口：exit 2 + stderr 一份 JSON。CLI 与各流程模块共用，stderr 上的 JSON 只有这里写（tests/test_cli_refusals.py）。"""
from __future__ import annotations

import json
from typing import Any, NoReturn

import typer

from horosa_skill.errors import HorosaSkillError, recovery_for


def _write_refusal(body: dict[str, Any]) -> NoReturn:
    """命令拒绝执行的唯一出口：exit 2 + stderr 一份 JSON（SKILL.md 的契约）。

    `default=str`：body 来自各层，一个 json 编码不了的值不该把拒绝变成 traceback——v0.47.2-dev 之前 22 处手写，
    pydantic 的 ValueError 就是这样把 exit 2 打成 exit 1 的。
    """
    typer.echo(json.dumps(body, ensure_ascii=False, indent=2, default=str), err=True)
    raise typer.Exit(code=2)


def _emit_refusal(code: str, message: str, details: dict[str, Any] | None = None, **extra: Any) -> NoReturn:
    """带错误码的拒绝：details 补上与 MCP 面同一套恢复说明；`extra` 是个别命令约定的顶层键。"""
    _write_refusal({"ok": False, **extra, "code": code, "message": message, "details": recovery_for(code, details)})


def _refuse(exc: HorosaSkillError) -> NoReturn:
    _emit_refusal(exc.code, str(exc), exc.details)
