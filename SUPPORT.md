# Support

Horosa Skill has a few different support paths depending on what you need.

## Self-Service First / 先自助排查

Before opening an issue, run these locally — they resolve most problems:

```bash
uv run horosa-skill doctor      # 环境体检：runtime/磁盘/端口/node 实跑探针 + next_action
uv run horosa-skill selfcheck   # 活体验证：起一张盘 → 存 → 读回（失败带修复指引）
```

- Runtime not installed → `uv run horosa-skill install` (≈730MB download, resumable).
- Backend cold start can take up to ~45s on the first call — retry once before reporting.
- Behind a slow network? Set `HOROSA_RUNTIME_MIRROR=<mirror-prefix>` and re-run install.

## Usage Questions

Use GitHub Discussions if they become available for the repository. Until then,
open a GitHub issue only when your question is directly tied to a reproducible
problem in this repository.

## Bug Reports

Open a GitHub issue and include / 请求应带信息:

- what you tried to do（想做什么）
- which command, tool, or client you used（哪条命令 / 哪个工具 / 哪个 AI 客户端）
- platform and runtime version（`uv run horosa-skill --version` + OS）
- the full JSON output of `uv run horosa-skill doctor`（脱敏后）
- relevant logs or screenshots（相关日志，注意脱敏个人生辰）
- whether the problem is reproducible on a fresh clone or fresh runtime install

## Feature Requests

Open a GitHub issue using the feature request template and describe:

- the workflow you want to enable
- the target tool, export surface, or runtime area
- why the current behavior is insufficient

## Security Issues

Do not post sensitive exploit details in a public issue.

Instead, follow the guidance in [SECURITY.md](./SECURITY.md) and report the
issue through a private maintainer-controlled channel.

## Contribution Questions

If you plan to contribute code, docs, or runtime-packaging changes, read
[CONTRIBUTING.md](./CONTRIBUTING.md) first.
