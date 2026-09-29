# Support

Horosa Skill has a few different support paths depending on what you need.

## Self-Service First / 先自助排查

Before opening an issue, run these locally — they resolve most problems:

```bash
uv run horosa-skill doctor      # 环境体检：runtime/磁盘/端口/node 实跑探针 + next_action
uv run horosa-skill selfcheck   # 活体验证：起一张盘 → 存 → 读回（失败带修复指引）
```

- Runtime not installed → `uv run horosa-skill install` (≈730MB download, resumable).
- A tool answers `runtime.starting` with `retry_after_seconds` → the backend is still booting (slow on first start and under
  Windows ARM emulation); retry after that many seconds — it is not an error to report.
- Windows: the runtime root must be a pure-ASCII path — `install` refuses with `runtime.path_not_ascii` and `doctor` reports
  `windows:runtime_root_not_ascii` → set `HOROSA_RUNTIME_ROOT=C:\horosa` and re-run `install`.
- `uv run horosa-skill doctor --explain` prints one plain-language line + `next_action` per issue; paste that block into a report.
- Backend cold start can take up to ~45s on the first call — retry once before reporting.
- Behind a slow network? Set `HOROSA_RUNTIME_MIRROR=<mirror-prefix>` and re-run install.
- github.com unreachable / offline machine → [docs/INSTALL_RESTRICTED_NETWORK.md](./docs/INSTALL_RESTRICTED_NETWORK.md)（镜像 / API 直链 / U 盘搬运）。

## Usage Questions

Use GitHub Discussions if they become available for the repository. Until then,
open a GitHub issue only when your question is directly tied to a reproducible
problem in this repository.

## Bug Reports

Open a GitHub issue and include / 请求应带信息:

- what you tried to do（想做什么）
- which command, tool, or client you used（哪条命令 / 哪个工具 / 哪个 AI 客户端）
- which surface: CLI / MCP stdio / streamable-http, compact (`HOROSA_MCP_COMPACT=1`) or full（哪个面）
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
