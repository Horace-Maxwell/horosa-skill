# Horosa Skill — Claude Code 入口

本仓把星阙（Horosa）的 110 个术数/占星技法打包成 local-first 的 MCP server + CLI（离线 runtime 走
GitHub Releases；MCP 全量面 120 = 110 技法 + 10 门面，`HOROSA_MCP_COMPACT=1` 精简面 11）。本仓是星阙的**下游**（sync 方向：星阙 → skill，永不反向）。

**总规则与完整路由在 [AGENTS.md](./AGENTS.md)（§0 路由 · §1 铁律 · §2 问题记录协议）——先读它。**

## 铁律速览（详见 AGENTS.md §1）

1. 星阙技法结果**禁手算**——一律走 Horosa MCP/CLI 工具。
2. 结果敏感设置缺失**先问后调**（运行时闸门 `agent_guidance.required` 会拦）。
3. vendor/参照唯一来源 = 开源仓 **Horosa-Public**；上游星阙树只读，教训永不写回上游。
4. 🔴 踩坑必记（协议 v3）：`docs/LESSONS.md` 原文 + AGENTS.md 蒸馏 + CHANGELOG + 机器守卫 + 文档实时更新（`docs/DOC_MAP.md` /
   `contracts/third_party_facts.json` / 生成件镜像），同一 change 完成；是否跟上由 `verify_docs_sync.py` 裁定。
5. 发布不信绿灯：pin-forward 下 guard 必绿；`sync_windows_release.py --check` 的 `[GAP]` 才权威。
6. 文档同步交给 CI：改文档/发版跑 `cd horosa-skill && uv run python scripts/verify_docs_sync.py`（仓根没有 `scripts/`）；push 前本机门禁
   只认 `uv run python scripts/run_ci_gates.py`（24 步 CI 镜像）——别裸跑 `verify_*.py` 全集，`verify_runtime_live.py` 是会下载 runtime 的真 lane。
8. `:9999` / `:8899` 是用户桌面版星阙的端口——永不 kill、永不对其测试；本仓 vendored 测试实例用 8877 / 9977（`scripts/start_vendored_instance.sh`）。
7. 会话开始：仓根若有 `HANDOFF-*.local.md` 先读它（多会话接力的现场状态）；会话结束前更新它与本机 memory。

## 按任务跳转

| 任务 | 读哪里 |
| --- | --- |
| 作为 AI 客户端调用技法 / 出报告 | [skills/horosa-agent/SKILL.md](./skills/horosa-agent/SKILL.md)（唯一策略源） |
| 本仓开发 / 验证 / 发布操作 | `/horosa-dev` skill（`.claude/skills/horosa-dev/SKILL.md`，维护者本地、不随仓分发）+ AGENTS.md §6–§8 |
| 改代码 / 新增技法 / re-vendor | AGENTS.md §4–§5 |
| 发布事故（缺半 / repack / pin-forward） | AGENTS.md §7 |
| 按症状排障 | AGENTS.md §8 症状速查表 |
| 查历史教训 / 查名词 | [docs/LESSONS.md](./docs/LESSONS.md) / [docs/GLOSSARY.md](./docs/GLOSSARY.md) |
| 改任何文档 / 第三方事实 | [docs/DOC_MAP.md](./docs/DOC_MAP.md)（每份文档的触发与守卫）+ AGENTS.md §2 第 5 条 |
