# 受限网络下安装 / Installing on a restricted network

> 适用：github.com:443 直连不通、只有代理、企业证书拦截、或完全离线的机器（issue #14 那类场景）。
> 三样东西要落到本机：① `horosa-skill` 这个 Python 包（纯 Python wheel）、② 离线 runtime 归档（macOS arm64
> `.tar.gz` / Windows x64 `.zip`，约 0.7–0.95 GB）、③ 一次 `install` 用来解压归档并写清单。下面三条路径任选其一。

## 0. 先自检（v0.38.0 起）

```bash
uv run horosa-skill doctor --probe-network   # 或 uvx --from "<wheel URL>" horosa-skill doctor --probe-network
```

`network_hints.reachability` 逐个列出清单 URL 经**每个镜像前缀**与直连的可达性（状态码 / 耗时 / 错误），`next_action`
指向下面对应的路径。默认 `doctor` 不发任何网络请求；只有 `--probe-network`（`setup` 默认开）才探。

## 1. 镜像前缀：`HOROSA_RUNTIME_MIRROR`

```bash
export HOROSA_RUNTIME_MIRROR="https://<你的镜像>/github,https://<备用镜像>"
uv run horosa-skill install
```

- 逗号分隔、只对 `https://github.com/...` 的 URL 做**前缀替换**（`https://github.com/O/R/releases/download/...`
  → `https://<镜像>/O/R/releases/download/...`），镜像按顺序试，原始 URL 永远排最后兜底。
- 同一个开关同时作用于 **runtime 清单、runtime 归档、wheel 资产 URL**：`client config --launcher uvx-wheel` 生成的配置
  会直接把镜像后的 wheel URL 写进去（`launcher.alternatives` 列出全部候选）。
- 下载支持断点续传（`.part` 落在 `<runtime_root>/downloads/`，重跑 `install` 接着传）、按设置重试；校验 sha256。

## 2. API 直链 + 本地归档：`install --archive`

`api.github.com` 通、`github.com` 不通的机器（常见于只放行 API 域名的代理）：

```bash
curl -s https://api.github.com/repos/Horace-Maxwell/horosa-skill/releases/latest \
  | python3 -c "import json,sys; [print(a['id'], a['name']) for a in json.load(sys.stdin)['assets']]"
# 记下本平台归档（darwin-arm64 .tar.gz 或 win32-x64 .zip）的 id：
curl -L -H "Accept: application/octet-stream" -o runtime.zip \
  https://api.github.com/repos/Horace-Maxwell/horosa-skill/releases/assets/<id>
uv run horosa-skill install --archive runtime.zip
```

`--archive` 也接受 `file://` URL；安装器仍会校验归档内嵌的清单版本与布局。

## 3. 完全离线：U 盘搬运

在一台能上网的机器上下载两件东西，拷到目标机：

1. wheel：`https://github.com/Horace-Maxwell/horosa-skill/releases/download/v0.37.0/horosa_skill-0.37.0-py3-none-any.whl`
2. 本平台的 runtime 归档（同一 release 页）。

目标机（只需 uv；Python ≥ 3.12 由 uv 自动准备——uv 本身也可从镜像或离线安装包装）：

```bash
uvx --from ./horosa_skill-0.37.0-py3-none-any.whl horosa-skill install --archive ./horosa-runtime-win32-x64-v0.37.0.zip
uvx --from ./horosa_skill-0.37.0-py3-none-any.whl horosa-skill doctor
uvx --from ./horosa_skill-0.37.0-py3-none-any.whl horosa-skill client config --format <client> --launcher uvx-wheel --write <配置文件>
```

生成的配置里 `--from` 会指向线上 wheel URL；离线机器把它改成本地 wheel 路径即可（`uvx --from <本地 .whl>` 同样成立）。

## 代理与企业证书

- 下载走 `HTTPS_PROXY` / `HTTP_PROXY` / `ALL_PROXY`（`NO_PROXY` 照常）；**回环探测（127.0.0.1 的本地服务）永远不走代理**，
  否则 Clash/VPN 会把健康的后端报成不可达。
- 企业根证书：`SSL_CERT_FILE=<你的 CA bundle>`；uv 侧用 `UV_NATIVE_TLS=1` 让它信任系统证书库。
- Windows PowerShell 5.1 的管道会按控制台代码页重编码——给 agent 传 JSON 用 `--input <file>` / `--output <file>`，
  别用 `|`（见 SKILL.md「Shell-only agents」）。

## 错误码速查

| 码 | 意思 | 处置 |
| --- | --- | --- |
| `runtime.install_manifest_fetch_failed` | 清单 URL 经所有镜像都取不到 | 路径 1 换镜像 / 路径 2 直链 |
| `runtime.install_download_failed` | 归档下载失败（`resume_note` 说明 `.part` 是否保留） | 重跑 `install` 续传；或路径 2/3 |
| `runtime.install_sha256_mismatch` | 归档内容与清单 sha256 不符（镜像给了别的文件） | 换镜像或走直链；别 `--force` 跳过校验 |
| `runtime.install_long_path` | Windows 路径超 260 且未开长路径 | 设 `HOROSA_RUNTIME_ROOT=C:\horosa` 或开注册表 `LongPathsEnabled` |
| `runtime.install_missing_platform` | 清单里没有本机平台 | Intel Mac / Linux 走网关模式（`HOROSA_SERVER_ROOT` 指向装了 runtime 的机器）；Windows ARM 不会走到这里——它自动装 win32-x64 载荷走仿真（结果里 `warnings[].code == runtime.platform_emulated`），走到这里说明清单连 win32-x64 都缺 |
| `runtime.install_os_too_old` | 本机系统版本低于载荷声明的 `min_os`（派生的 Windows 载荷要 Windows 10 1809+） | 升级系统，或走网关模式 |

---

## English

Applies to machines where `github.com:443` is unreachable, only a proxy is allowed, a corporate CA intercepts
TLS, or there is no network at all. Three things must land on the machine: the pure-Python **wheel** of
`horosa-skill`, the platform **runtime archive** (~0.7–0.95 GB), and one `install` run to unpack it.

**0. Probe first** — `horosa-skill doctor --probe-network` lists, per mirror prefix and for the direct URL,
whether the release manifest is reachable (status / latency / error). Plain `doctor` never touches the network.

**1. Mirror prefix** — `HOROSA_RUNTIME_MIRROR="https://<mirror>/github,https://<backup>"`: comma-separated
prefixes that replace `https://github.com` for the manifest, the runtime archives *and* the wheel URL
(`client config --launcher uvx-wheel` writes the mirrored URL into the client config; `launcher.alternatives`
lists every candidate). The original URL is always the last fallback; downloads resume (`.part` under
`<runtime_root>/downloads/`) and are sha256-checked.

**2. Assets API + local archive** — when `api.github.com` works but `github.com` does not: list
`releases/latest` assets, download your platform archive with `Accept: application/octet-stream`, then
`horosa-skill install --archive runtime.zip` (`file://` URLs work too).

**3. Fully offline (USB)** — copy the wheel and the runtime archive from a connected machine, then
`uvx --from ./horosa_skill-0.37.0-py3-none-any.whl horosa-skill install --archive ./<archive>`; a local
`.whl` path works everywhere the release URL does.

**Proxies & corporate CAs** — downloads honour `HTTPS_PROXY`/`HTTP_PROXY`/`ALL_PROXY`; loopback probes to the
local services never go through a proxy. Set `SSL_CERT_FILE` for a private CA and `UV_NATIVE_TLS=1` so uv
trusts the system store. On Windows PowerShell 5.1 pass JSON via `--input`/`--output` files, not pipes.

Error codes: `runtime.install_manifest_fetch_failed` (try a mirror / the API path), `runtime.install_download_failed`
(re-run to resume), `runtime.install_sha256_mismatch` (the mirror served a different file — switch mirrors, never
skip verification), `runtime.install_long_path` (`HOROSA_RUNTIME_ROOT=C:\horosa` or enable `LongPathsEnabled`),
`runtime.install_missing_platform` (gateway mode via `HOROSA_SERVER_ROOT`; Windows on ARM never lands here — it installs the
win32-x64 payload under emulation and reports `runtime.platform_emulated` in `warnings`), `runtime.install_os_too_old` (the
host is older than the payload's `min_os` — upgrade the OS or use gateway mode).
