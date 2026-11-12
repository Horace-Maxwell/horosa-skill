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
- MCP `tools/list` 预算：全量 ≤ 256 KB / 精简 ≤ 30 KB（棘轮只降不升）+ **每工具 inputSchema ≤ 5000 B**（Codex 0.158 缺省
  `tool_input_schema_max_bytes`，超出即静默剥说明）——`contracts/mcp_list_budget.json`，`verify_mcp_list_budget.py` 锁

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
- `benchmark faithfulness` 报告的 `model_opinion`（仅 `HOROSA_JEV_SCOPE=snapshot`）：`{provider, model, mode, tau, latency_ms,
  n, n_judged, agreement_rate, disagreements[], per_claim[{text, deterministic, model, supported_probability, agrees}], note}`；
  确定性字段 `ok` / `claims` / `metrics` 不受影响。

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

## MCP 结果视图（v0.50.0）

MCP 工具调用的返回体由 `horosa_skill/result_view.py` 整形（CLI 与存档不经过这一层，仍是完整信封）。调用参数 `response_view`：

- `reading`（缺省，`HOROSA_MCP_RESULT_VIEW` 可改）：`data.export_snapshot` 只留 `technique` {key,label}、`export_text`（正文一遍）、
  `sections[]` 段索引 {index,title,chars[,shown,from,to]}、`missing_selected_sections` / `unknown_detected_sections` / `citation`；
  `data.snapshot_text` 与引擎原始子树（`data.chart` / `data.pan` / `data.bazi` …）不带，`data.response_view` =
  {view, raw_fields_omitted[], full}（取全量的调用）；`technique_card`、`compute_sources`、`route`、`knowledge_context`、`file(s)` 与小值原样。
- `sections`：同上，但正文在 `sections[].body`，没有 `export_text`；`titles`：只有段索引；`full`（别名 `raw`）：完整信封（v0.49.0 的缺省）。
- 模型预算（`HOROSA_MCP_RESULT_MAX_TOKENS` 缺省 20 000 估算 token、`HOROSA_MCP_RESULT_MAX_CHARS` 缺省 48 000 字符）：超了按段裁，
  `warnings` 写明续读调用 `horosa_memory_show(run_id, response_tool, response_sections=[…], response_offset=N)`。
- 调度 / 合参：`results.<tool>` 各自是阅读视图，共用一份预算；调度的 `result_export_contracts` 在阅读视图里为空（段索引已在各结果里）。
- `horosa_memory_show`：技法产物载荷同样成阅读视图；调度产物只留各技法的指向；运行清单不带载荷。
- 线上 JSON 不缩进；`full` 视图仍受 900 KB 线上预算管（调度的 `results.<tool>` 一起裁）。

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
