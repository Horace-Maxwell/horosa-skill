# Operations

> 读者：运维 / 用户支持。何时读：install / doctor / serve / run 运维操作时。

## 目标

这份文档面向维护者，描述 Horosa Skill 的安装、运行、发布、校验和排障路径。

## 本地运行

1. 进入 [`horosa-skill`](../horosa-skill)
2. 运行 `uv sync --dev`
3. 运行 `uv run horosa-skill install`
4. 运行 `uv run horosa-skill doctor`
5. 运行 `uv run horosa-skill serve`

## 发布前检查

**打 tag 之前必须先跑这一条**（AGENTS §7 标为强制；它把跨树校验一并跑完，成功会重写
`contracts/upstream_provenance.json`，那个 diff 就是「跨树核对真发生过」的 git 证据）：

```bash
HOROSA_SOURCE_ROOT=<Horosa-Public checkout> uv run python scripts/preflight_release.py
```

它内部已含 verify_upstream_sync（`--require-upstream`）/ verify_export_section_baseline
（`--source upstream`）/ verify_vendor_runtime_sources / verify_export_contract_mirror /
verify_docs_sync / verify_builder_parity。此外单独跑：

- `uv run pytest -q`
- `cd horosa-core-js && npm test`（loadcheck 全量 import 冒烟 + selfcheck golden）
- `uv run python scripts/verify_readme_links.py`
- `uv run python scripts/verify_server_json.py`
- `uv run python scripts/build_knowledge_index.py --check`
- `uv run python scripts/run_benchmark.py --skip-runtime`

## ken 技法验证（奇门 / 太乙 / 金口 / 三式合一）

这些技法由 **ken 后端**（`kinqimen`/`kintaiyi`/`kinjinkou`）在 Python chart 服务上计算（`/qimen/pan`、
`/taiyi/pan`、`/jinkou/pan`），`horosa-core-js` 只负责把 ken 响应重排成 `aiExport.js` 分段。验证需要 chart
服务在线（`:8899`，以及 Java `:9999`）：

1. 起后端：在 Horosa-Web 下 `HOROSA_SKIP_UI_BUILD=1 ./start_horosa_local.sh`（mac）/ `start_horosa_local.ps1`（Win）。
2. 确认监听：`:9999`（Java）+ `:8899`（chart/ken）。
3. `uv run pytest -q`：`tests/test_local_js_tools.py` 里 qimen/taiyi/jinkou/sanshiunited 为集成测试，后端不在时自动 skip；
   `tongshefa` 始终执行。
4. 验收标准：每个技法产出其 aiExport.js 分段（奇门：起盘信息/盘型/盘面要素/奇门演卦/八宫详解/九宫方盘；
   太乙：起盘信息/太乙盘/十六宫标记；金口：起盘信息/金口诀速览/金口诀四位/四位神煞），且 export 契约干净
   （无 missing/unknown 分段）。

离线运行时必须打包 `Horosa-Web/vendor/{kinqimen,kintaiyi,kinjinkou}` 及其依赖（bidict/numpy/kerykeion/ephem/
pendulum）——见 [`OFFLINE_RUNTIME_RELEASES.md`](./OFFLINE_RUNTIME_RELEASES.md)。

## Runtime Release

Runtime release 采用“轻仓库 + 重 release 资产”模式。

- 构建脚本：[`build_runtime_release.sh`](./../horosa-skill/scripts/build_runtime_release.sh)
- 输出目录：`horosa-skill/dist/runtime/`
- 必要资产：
  - `horosa-runtime-darwin-arm64-v<version>.tar.gz`
  - `horosa-runtime-win32-x64-v<version>.zip`
  - `runtime-manifest.json`
  - `SHA256SUMS.txt`
  - `horosa-skill-sbom.json`

## Provenance / Attestation

🔴 **当前没有 attestation，这条以前写反了。** `release.yml` 是
`runs-on: self-hosted` 而本仓**从未注册过 self-hosted runner** —— v0.9.2→v0.25.0 的 20 次 tag
触发全部排队 24h 后被取消，其中的 SBOM 与 `attest-build-provenance` 一步都没执行过。
实测 v0.26.0 的 manifest（`sha256:ab43d2e6…`）查 attestation 返回 **404**。

所以：`gh attestation verify` 现在必然失败，**别照着跑再去怀疑资产有问题**。
SBOM 由发布者在本机手动生成并上传（见「手动发布」）；provenance attestation 暂缺。
`release.yml` 已改为仅 `workflow_dispatch`（推 tag 不再触发）——宁可明确没有，也不要假覆盖。

## 故障处理

- `doctor` 显示 `runtime.manifest_invalid`
  - 检查 `~/.horosa/runtime/current/runtime-manifest.json`
- `services:not_running`
  - 先运行 `horosa-skill stop`
  - 再运行 `horosa-skill serve`
- benchmark 只想跑无 runtime 部分
  - 运行 `uv run horosa-skill benchmark run --skip-runtime`
- `uv run` / `pytest` 报 `pydantic_core` 的 `.so` `library load disallowed by system policy`
  - `.venv` 指向了 miniconda（带 library validation）。重建为 uv 自管 CPython：
    `uv venv --clear --python-preference only-managed --python 3.12 && uv sync`
- 奇门/太乙/金口报 `transport.connection_error` 或返回空盘
  - chart 服务（`:8899`）未起或未挂载 ken。确认后端在线，且 `import kinqimen/kintaiyi/kinjinkou` 能成功
    （`vendor` 在 PYTHONPATH 上）。
