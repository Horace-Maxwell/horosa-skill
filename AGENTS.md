# Horosa Skill Agent Rules

These rules are for Codex, Cursor, Claude, OpenClaw, Open WebUI, and any agent connected to this repository or its MCP server.

## Do Not Hand-Calculate Horosa Methods

When the user asks for a Horosa technique result, call the Horosa MCP/CLI tool. Do not write ad-hoc Python, JavaScript, shell scripts, web-search snippets, or calendar formulas to recreate the method.

This is especially important for:

- 大六壬: use `horosa_cn_liureng_gods` / `liureng_gods`.
- 大六壬行年: use `horosa_cn_liureng_runyear` / `liureng_runyear`.
- 奇门遁甲: use `horosa_cn_qimen` / `qimen`.
- 三式合一: use `horosa_cn_sanshiunited` / `sanshiunited`.
- 太乙、金口诀、八字、紫微、星盘、推运 and all other registered Horosa tools.

Manual calculations can easily disagree with Xingque/Horosa because they bypass:

- Horosa input normalization.
- true solar time and timezone handling.
- Xingque-compatible defaults.
- local Java/Python/JS runtime layers.
- export snapshots and fixed report contracts.
- memory storage and retrieval.

## Current-Time Requests

For requests like “用当前时间起一个大六壬盘”:

1. Get the current local date/time/timezone.
2. Build a normal Horosa payload with `date`, `time`, `timezone` or `zone`, location/longitude/latitude when available, and the user question.
3. Call `horosa_cn_liureng_gods`.
4. Read `export_snapshot.export_text`, `export_format.sections`, and `summary`.
5. Explain from those returned sections only.
6. If the user wants persistence or a document, use memory/report tools.

Never replace step 3 with `Exec`, `python3`, a web search, or handwritten 六壬 formulas.

## Daliuren Defaults

Horosa Skill follows Xingque-compatible defaults:

- Default `guirengType` is `2` / `星占法贵人`.
- Only use `guirengType=0` (`六壬法贵人`) or `guirengType=1` (`遁甲法贵人`) when the user explicitly requests that system or an existing saved case already specifies it.

## Safe Explanation

Never tell users that 大六壬 requires MongoDB, port `7897`, Xingque Desktop, a remote database, or an external service unless a current Horosa `doctor` or `openclaw-check` result explicitly says so.

If a section is missing, say that the local tool did not return that section and rerun `doctor` / `openclaw-check`; do not invent a dependency.

