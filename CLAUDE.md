# Horosa Skill — Claude Code 入口

本仓把星阙（Horosa）的 105 个术数/占星技法打包成 local-first 的 MCP server + CLI（离线 runtime 走
GitHub Releases）。本仓是星阙的**下游**（sync 方向：星阙 → skill，永不反向）。

**总规则与完整路由在 [AGENTS.md](./AGENTS.md)（§0 路由 · §1 铁律 · §2 问题记录协议）——先读它。**

## 铁律速览（详见 AGENTS.md §1）

1. 星阙技法结果**禁手算**——一律走 Horosa MCP/CLI 工具。
2. 结果敏感设置缺失**先问后调**（运行时闸门 `agent_guidance.required` 会拦）。
3. vendor/参照唯一来源 = 开源仓 **Horosa-Public**；上游星阙树只读，教训永不写回上游。
4. 🔴 踩坑必记（协议 v2）：`docs/LESSONS.md` 原文 + AGENTS.md 蒸馏 + CHANGELOG + 机器守卫，同一 change 完成。
5. 发布不信绿灯：pin-forward 下 guard 必绿；`sync_windows_release.py --check` 的 `[GAP]` 才权威。
6. 文档同步交给 CI：改文档/发版跑 `scripts/verify_docs_sync.py`。

## 按任务跳转

| 任务 | 读哪里 |
| --- | --- |
| 作为 AI 客户端调用技法 / 出报告 | [skills/horosa-agent/SKILL.md](./skills/horosa-agent/SKILL.md)（唯一策略源） |
| 本仓开发 / 验证 / 发布操作 | `/horosa-dev` skill（`.claude/skills/horosa-dev/SKILL.md`，维护者本地、不随仓分发）+ AGENTS.md §6–§8 |
| 改代码 / 新增技法 / re-vendor | AGENTS.md §4–§5 |
| 发布事故（缺半 / repack / pin-forward） | AGENTS.md §7 |
| 按症状排障 | AGENTS.md §8 症状速查表 |
| 查历史教训 / 查名词 | [docs/LESSONS.md](./docs/LESSONS.md) / [docs/GLOSSARY.md](./docs/GLOSSARY.md) |
