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
