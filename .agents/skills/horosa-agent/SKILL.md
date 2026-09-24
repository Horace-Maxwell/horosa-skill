---
name: horosa-agent
description: >-
  Use Horosa (星阙) local metaphysics MCP tools correctly — 110 techniques: Western astrology natal
  chart, solar return, progressions, primary directions, horary, electional 择日, birth-time
  rectification, 八字 bazi, 紫微斗数 ziwei, 大六壬, 奇门遁甲 qimen, 太乙, 金口诀, 六爻, 梅花心易,
  河洛理数, 铁板神数, 塔罗 tarot, 天文地占 geomancy, 老黄历, AstroCartoGraphy, celebrity birth data,
  Chinese esoteric history. Trigger on 起盘 排盘 起课 起卦 算命 推运 看盘 合盘 卜卦 择日 生时校正,
  fortune-telling, divination, chart casting, or any Horosa/星阙 reading. Never hand-calculate.
license: AGPL-3.0-only
dependencies:
  tools:
    - type: mcp
      name: horosa
      note: >-
        Local Horosa Skill MCP server (Python 3.12 + uv + offline runtime). Register with
        `uv run --directory <repo>/horosa-skill horosa-skill client config --format codex`
        (see examples/clients/codex.md for the full Codex setup, timeouts, and env whitelist).
---

# Horosa Agent Skill (Codex / agentskills.io entry)

Thin client-agnostic contract. The **single policy source** is
[`skills/horosa-agent/SKILL.md`](../../../skills/horosa-agent/SKILL.md) — read it
(and its `references/`) before deep work. Maintainer/repo law: `AGENTS.md`.

## Non-negotiable rules

1. **Never hand-calculate** any Horosa/星阙 technique (no shell/Python/JS/web formulas, no memorized
   tables). Every 盘/课/卦/运 comes from a `horosa` MCP tool call (`horosa_astro_chart`,
   `horosa_cn_qimen`, `horosa_cn_liureng_gods`, …) or the `horosa-skill` CLI.
2. **Clarify before calling**: if a result-changing setting is missing (birth/event time, place,
   timezone, gender, house system, 起局方式, 贵人体系, target year), ask the user a short question
   with options first. Tools reject unconfirmed calls with `agent_guidance.required`; after the user
   answers, retry with `agent_confirmed_settings: true` (or `defaults_accepted: true` when they
   accept defaults) plus `clarification_notes`. Never self-confirm; never switch tools to bypass the
   gate. In non-interactive runs (`codex exec`), surface the question as your final answer instead
   of guessing.
3. **Read results only from `export_snapshot.export_text` / `.sections`** — that text is the chart.
   Do not restate numbers that are not in it, and do not invent sections it lacks.
4. If `horosa` tools are absent from the tool list: first turn after a cold start may simply be too
   early (Codex waits ~1s for optional servers; the runtime warms in ~45s) — retry next turn. Still
   absent → the server is not configured; point the user at `examples/clients/codex.md`.
5. Errors carry structured recovery: on `details.agent_recovery`, relay `prompt_to_user` verbatim
   and stop. On transport errors, suggest `horosa-skill doctor` / `horosa-skill selfcheck`.
6. **Compact surface.** Codex gets the 11 facade tools by default (`HOROSA_MCP_COMPACT=1`); call any technique
   by name via `horosa_tool_run(tool_name="qimen", …)` — the catalogue is the `horosa://catalog/techniques`
   resource. A missing flat `horosa_*` name is not a missing technique.

## Shell-only agents (no MCP)

`codex exec` without MCP, CI bots, plain shell tools: the CLI carries the same contract. Parse **stdout only**
(exactly one JSON document; progress lines and error envelopes go to stderr). On Windows PowerShell 5.1 pass
payloads as `--input` / `--output` files, never through the pipe (it re-encodes bytes and mangles Chinese).

| Need | Command |
| --- | --- |
| Tool names + `aka:` aliases | `horosa-skill tool list` |
| What to confirm before a call | `horosa-skill agent guidance --tool qimen` |
| Run one technique | `horosa-skill tool run qimen --input payload.json --output result.json` |
| Natural-language routing | `horosa-skill dispatch --input query.json --output result.json` |
| One-command onboarding on a fresh machine | `horosa-skill setup --client codex` (`uv run horosa-skill setup --client codex` inside a checkout) |

Exit 2 + stderr `code: "agent_guidance.required"` = ask the user with `details.agent_recovery.prompt_to_user`,
then rerun with `agent_confirmed_settings: true` + `clarification_notes` (or `defaults_accepted: true` only when
the user explicitly accepts defaults). Exit 0 with `ok: false` = a real engine error (`error.code`), not a missing
technique. Read results only from `data.export_snapshot.export_text`; quote `data.technique_card` afterwards.
