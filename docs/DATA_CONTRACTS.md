# Data Contracts

> 读者：维护者 + 客户端开发。何时读：查 envelope / export / record / manifest 的 schema 版本与形状时（`tool envelope` 版本独立于包版本）。

## 版本面

- tool envelope：`0.8.0`（与 `schemas/common.py::TOOL_ENVELOPE_SCHEMA_VERSION` 由 `verify_docs_sync` 锁步；
  0.8.0 起 `export_snapshot.sections[*]` 只有 `{index, raw_title, title, included, body}`，不再带 `data`——
  引擎对象只在 `data.<key>` 出现一次）
- export contract：`horosa.ai.export.settings.v1`
- record schema：`horosa.skill.record.v1`
- run manifest schema：`horosa.skill.run.manifest`
- runtime manifest：见 [`RUNTIME_MANIFEST_SPEC.md`](./RUNTIME_MANIFEST_SPEC.md)

## Tool Envelope

所有工具统一返回：

- `ok`
- `tool`
- `version`
- `input_normalized`
- `data`
- `summary`
- `warnings`
- `memory_ref`
- `error`
- `trace_id`
- `group_id`

可选云端决策层（v0.39.0，`HOROSA_JEV` 缺省 `off`）开启时的自陈，缺省关时**不出现**（信封逐字节不变）：

- `data.technique_card.decisions[]`：本次技法调用里每一条 Jev 决策——`surface`（dispatch / extract / zhancat …）、
  `mode`（shadow / enforce）、`model_requested` / `model`（返回的真实 id）、`state_sha256` 与 `redaction`
  （脱敏统计，不含原文）、`answers`（每问的选项 / 置信 / top-3 分布）、`adopted` 与 `reason`、`decision`
  （该面的结构化判定）、`latency_ms`。
- `DispatchEnvelope.decision_layer`：`{provider, mode, scope, model, surfaces:{面: 生效模式}, records[]}`，
  路由（S1）与抽取（S2）的记录在这里；技法级（S3 门类）的记录在各 `results.<tool>.data.technique_card.decisions`。

## Export Snapshot

适用于所有接入导出协议的技法：

- `technique`
- `settings_used`
- `selected_sections`
- `sections`
- `export_text`
- `format_source`
- `snapshot_text`
- `bundle_version`
- `provenance`
- `citation`

## Local Record Payload

artifact 顶层包含：

- 原始 envelope 内容
- `record_meta`
  - `run_id`
  - `tool_name`
  - `trace_id`
  - `group_id`
  - `evaluation_case_id`
- `conversation`
  - `query_text`
  - `user_question`
  - `ai_answer_text`
  - `ai_answer_structured`

## Knowledge Contract

`knowledge_read` 返回：

- `domain`
- `category`
- `key`
- `rendered_text`
- `lines`
- `bundle_version`
- `provenance`
- `citation`
