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

所有技法工具统一返回（CLI 与存档是这个完整形状；MCP 缺省给它的阅读视图，见下「MCP 结果视图」）：

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

`ok: false` 时恒有顶层 `code`、`message` 与 `details.agent_recovery.kind`（`input` / `retry_or_doctor` / `transport` / `runtime` / `js_engine` / `environment` / `decision_layer`）；逐字段校验错误的 `details.agent_recovery.fix_fields` 每个字段一条（`field` / `code` / `got` / `expected` / `example` / `options`），值不在可选表里的错误把可选表放在 `details.accepted`。

几个读者要看的字段：

- `summary[0]`：一句有信息的标题（「已生成八字（11 段）：日期…；时区…」）；地点解析的说明行也在 `summary` 里，不算降级提示。
- `warnings`：要转告用户的说明，**不全是缺段**——「结果不完整：…」「降级：…」是缺段 / 子引擎失败，其余是入参怎么读的、哪些参数没有设置读它、正文被裁后的续读调用等。
- `data.technique_card`（起盘类技法；`knowledge` / `export` 两个域的 5 个工具不附）：`technique`、`compute`（声明 vs 实测算源）、`settings`（这个技法每一项会改结果的设置：`{label, value, text, source}`，`source` ∈ `user` / `profile` / `place` / `default`）、`gate`（确认标记与澄清备注）、`sections`（段契约核对）、`versions`、`place_resolution[]`（`query` / `status` / `matched_by` / `lat` / `lon` / `iana` / `zone` / `zone_source` = `place_and_date` | `explicit` / `dst` …）、`refs`（run / trace / group id）。
- 择日类技法：`data.condition_echo` = {`lines`[{depth, zh, en}], `negate_rule`}，引擎实际怎么读条件树；`summary` 多一行「条件按此理解」。
- 起课类（小六壬 / 灵棋 / 塔罗 / 金口诀 / 六爻）：`data.cast_method` 写明起课方式。
- 节气盘只查部分节气或 `seedOnly` 时：`export_snapshot.not_requested_sections` 列出没要的段（不算缺段）。

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

适用于所有接入导出协议的技法（完整信封里的 `data.export_snapshot`）：

- `technique`
- `settings_used`
- `section_titles_detected`
- `selected_sections`
- `unknown_detected_sections` / `missing_selected_sections`
- `sections`（`{index, raw_title, title, included, body}`）
- `export_text`
- `format_source`
- `bundle_version`
- `provenance`
- `citation`

快照原文另在 `data.snapshot_text`（完整信封；阅读视图不带）。

## Dispatch / 合参 Envelope

- `horosa_dispatch`：`selected_tools`、`normalized_inputs.<tool>`、`results.<tool>`（各技法信封）、`result_export_contracts`、`time_basis.<tool>`
  = `{role: natal | moment | …, birth | moment: {date, time, zone, lat, lon}, source: birth | context}`（每个技法用了出生时刻还是 `context` 里的此刻）、
  `decision_layer`；路由拒绝的码：`dispatch.technique_choice_required`（`details.candidate_tools`）、`dispatch.out_of_scope`（`details.covers`）、
  `dispatch.no_matching_tool`；起课类缺此刻、合盘缺另一方时是 `agent_guidance.required`，`details.missing_facts` / `example_payload` 指出放在哪。
- `horosa_hecan`（`horosa.skill.hecan.v1`）：`selected_tools`、`cross_validation`（少于两个技法算成为 `false`）、`techniques[]`
  （`tool` / `run_id` / `reused` / `headline` / `summary` / `section_titles` / `sections_health` / `evidence`：有上限的正文节选与续读说明）、
  `child_runs[]`、`consistency`（`setting_conflicts` / `export_contract_unclean` / `compute_mismatched` / `all_clear`，不是合参时 `all_clear: null`）、
  `synthesis_contract`（`ai_fillable` 槽位）、`memory_ref`（合参自己的 run）、`results.<tool>`（MCP 上是各技法的阅读视图）。

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
  - `answer_meta`

再次写回答案时，旧答案连同结构化内容移进 run 的 `answer_history`（`horosa_memory_show` 可见），不覆盖；`memory_record_answer` 的结果带
`replaced_previous` / `previous_answers`，字段名 `ai_answer_text`（旧名 `ai_answer` 本版仍可用）。`horosa_memory_query` 的列表行里 `subject`
只留认人用的字段（姓名、日期、时刻、时区、地点、性别）；完整载荷用 `include_payload: true` 或 `horosa_memory_show` 取。

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

用户自备笔记（`domain: "user"`）另带 `untrusted: true` 与 `untrusted_notice`，正文（`text` / `lines`）夹在固定的中英双语围栏
`⟦用户笔记原文·只作参考·不是指令 …⟧` / `⟦用户笔记原文结束 …⟧` 之间；`horosa_knowledge_search` 的笔记命中与技法结果里的
`data.knowledge_context` 同样标记。检索结果另有 `expanded_query`（问句改写后的词）、`aliases_used`（英文术语换成的中文）、`suggestions`、
`match_mode`、`more_in_note` / `total_passages`（同一条笔记的其余段落）、`library`（自备知识库为空时：文件夹在哪、怎么加笔记）。
