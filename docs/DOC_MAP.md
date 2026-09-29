# Doc Map — 每份指导性文档的用途、更新触发与守卫

> 这张表是「文档实时更新制度」的账本（AGENTS.md §2 协议 v3 第 5 条）。规则：**仓里每一份指导性文档都必须在这里有一行**
> （`scripts/verify_docs_sync.py::check_doc_map` 锁：新增文档不登记即红），每行写明它归谁管、什么事件必须更新它、哪把守卫在看着它。
> 「守卫」列写 `verify_docs_sync` 的检查函数名、脚本名或 `人工`（人工 = 只有 §2 协议在管，请尽量把它变成机器守卫）。

| 文档 | 用途 / 读者 | 更新触发 | 守卫 |
| --- | --- | --- | --- |
| `CLAUDE.md` | Claude Code 30 秒入口：铁律速览 + 路由 | 铁律 / 路由 / 协议版本变化 | `check_links`、`check_tool_counts`（技法数） |
| `AGENTS.md` | 全部 agent / 维护者的现行规则（§0–§12） | 每条教训（LESSONS → 蒸馏）、每次发布的 compaction gate | `check_lessons_distilled`、`check_links`、`check_conflict_markers` |
| `README.md` | 中文用户首页：能力、安装、客户端矩阵、平台表、状态 | 版本 / 工具数 / 测试数 / 客户端或平台事实变化 | `check_versions`、`check_tool_coverage`、`check_test_count_*`、`check_platform_table`、`check_client_matrix_connectors`、`check_docker_claims`、`check_knowledge_counts`、`check_group_headers`、`check_export_contract_versions`、`check_gate_counts`（v0.40.0 三把新锁） |
| `README_EN.md` | 英文首页（与中文逐节对齐） | 同上 | 同上 |
| `README.zh-CN.md` | 简短中文指针 | 极少 | `check_links` |
| `docs/LESSONS.md` | 只增台账：symptom → root cause → fix/guard 原文 | 每次踩坑（协议 v3 第 1 条） | `check_lessons_distilled`（每节必有索引行；最新三版必有 AGENTS 蒸馏） |
| `docs/DOC_MAP.md` | 本表 | 新增 / 删除任何指导性文档 | `check_doc_map` |
| `docs/GLOSSARY.md` | 领域名词 | 新名词进入规则 | `check_links`、人工 |
| `docs/OPERATIONS.md` | 维护者 runbook：验证、live、发布、事故、会话交接 | 脚本 / 流水线 / 流程变化 | `check_links`、`check_stale_claims`；命令真值靠 `run_ci_gates.py` |
| `docs/OFFLINE_RUNTIME_RELEASES.md` | 离线 runtime 发布形态与契约 | 载荷平台 / 清单字段 / 发布流变化 | `check_platform_table`（间接）、`check_links` |
| `docs/INSTALL_RESTRICTED_NETWORK.md` | 受限网络安装 | 版本 / 资产名变化 | `check_pinned_install_commands`、`bump_version.py` |
| `docs/RUNTIME_MANIFEST_SPEC.md` | runtime-manifest.json 字段规范 | 清单字段变化 | `verify_runtime_release.py`（契约侧）、人工 |
| `docs/runtime-manifest.example.json` | 清单示例 | 版本 / 字段变化 | `bump_version.py` |
| `docs/REPO_LAYOUT.md` | 仓库结构与一次调用链路 | 目录 / 模块增删 | `check_stale_claims`、`check_links` |
| `docs/ARCHITECTURE.md` | 计算模型与层次 | 计算路径变化 | 人工 |
| `docs/DATA_CONTRACTS.md` | envelope / 导出契约 | schema 版本变化 | `check_envelope_schema_version` |
| `docs/INPUT_CONTRACTS.md` | 入参契约 | schema 字段变化 | `verify_schema_knob_wiring.py`（间接） |
| `docs/EXPORT_AUDIT_GUIDE.md` | 导出段审计方法 | 审计工具变化 | 人工 |
| `docs/EVALUATION.md` | 评测（HorosaBench / Jev） | 评测集 / 阈值变化 | `verify_router_corpus.py`（间接） |
| `docs/ALGORITHM_COVERAGE.md` | 技法覆盖与算源分类 | 技法增删 / 算源变化 | `verify_technique_provenance.py`（间接）、人工 |
| `docs/WINDOWS_RELEASE_BUILD_PROMPT.md` | Windows 半边派生的操作提示 | 派生流水线变化 | 人工 |
| `docs/WINDOWS_REPORT_STABILITY_PROMPT.md` | Windows 报告稳定性排查提示 | 报告渲染路径变化 | 人工 |
| `docs/templates/HANDOFF_TEMPLATE.md` | 会话交接文件模板（复制成 `HANDOFF-*.local.md`，不提交） | 交接协议变化 | 人工 |
| `skills/horosa-agent/SKILL.md` | AI 客户端行为唯一策略源 | 闸门 / 入参 / 段契约 / 工具面变化 | `check_frontmatter`、`check_tool_coverage`、`check_pinned_install_commands` |
| `skills/horosa-agent/references/payloads.md` | 各技法载荷参考 | 入参变化 | 人工（随 SKILL） |
| `skills/horosa-agent/references/reports.md` | 报告输出参考 | 报告工具变化 | 人工 |
| `skills/horosa-agent/references/troubleshooting.md` | 客户端排障 | 错误码 / doctor 变化 | 人工 |
| `skills/horosa-agent/references/chinese-methods.md` | 中式技法口径 | 缺省 / 流派变化 | 人工 |
| `skills/horosa-agent/references/predictive.md` | 星运族参考 | 星运工具变化 | 人工 |
| `skills/horosa-agent/references/late-zi.md` | 晚子时矩阵 | 日界口径变化 | 人工 |
| `.agents/skills/horosa-agent/SKILL.md` | Codex / agentskills.io 入口（薄） | 策略源变化 | `check_agent_entry_docs` |
| `.cursor/rules/horosa-skill.mdc` | Cursor 规则入口（薄） | 策略源变化 | `check_agent_entry_docs` |
| `GEMINI.md` | Gemini CLI 薄镜像（**生成件**） | 改 `scripts/gen_agent_mirrors.py` 模板 | `check_agent_mirrors_generated`、`check_agent_mirrors` |
| `.github/copilot-instructions.md` | Copilot 薄镜像（**生成件**） | 同上 | 同上 |
| `.windsurf/rules/horosa-skill.md` | Devin Desktop / 旧 Windsurf 薄镜像（**生成件**） | 同上 | 同上 |
| `.clinerules/horosa-skill.md` | Cline 薄镜像（**生成件**） | 同上 | 同上 |
| `horosa-skill/README.md` | wheel 随包 README（setup / client config / check / doctor 四命令版） | 命令变化 | `check_links`、人工 |
| `horosa-skill/examples/clients/README.md` | 客户端接入示例索引（key → 客户端 → 落点 → 工具面） | 客户端增删 / 改名 | `check_links`、ledger |
| `horosa-skill/examples/clients/claude-code.md` | Claude Code 接入示例 | 客户端事实变化（ledger） | `check_third_party_facts`（affects） |
| `horosa-skill/examples/clients/codex.md` | Codex 接入示例 | 同上 | 同上 |
| `horosa-skill/examples/clients/openclaw-mcp.md` | OpenClaw 接入示例 | 同上 | 同上 |
| `horosa-skill/examples/clients/openwebui-streamable-http.md` | Open WebUI 接入示例 | 同上 | 同上 |
| `horosa-skill/examples/clients/remote-connectors-oauth-gateway.md` | claude.ai / ChatGPT 经 OAuth 网关 | 连接器事实变化 | `check_client_matrix_connectors`、ledger |
| `horosa-skill/contracts/third_party_facts.json` | 第三方事实账本（来源 URL + 核实日期） | 任何第三方事实变化；每 120 天复核 | `check_third_party_facts`、`docs-currency.yml` |
| `vendor/README.md` | vendor 目录说明 | 镜像子树增删 | `check_links` |
| `CONTRIBUTING.md` / `SECURITY.md` / `SUPPORT.md` / `CODE_OF_CONDUCT.md` | 社区元文档 | 流程 / 联系方式变化 | `check_links` |
| `CHANGELOG.md`（gitignored 本地件） | Keep-a-Changelog 台账 | 每次行为变化（协议 v3 第 3 条） | 人工（不进仓，故无 CI 守卫） |
| `.claude/skills/horosa-dev/SKILL.md`（本地、不随仓分发） | 维护者操作 skill | runbook 变化 | 人工（随 OPERATIONS） |
