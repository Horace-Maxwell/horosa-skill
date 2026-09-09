# Open WebUI · n8n · Dify（streamable-http 网关）

这三家的共同点：只会往一个 URL 发 MCP 请求，最多再带一个 `Authorization` 头。所以接法都一样 ——
把 Horosa Skill 以 **streamable-http** 起在一个它们够得着的地址上。

> 这条路走的是 MCP 网关，**离线 runtime 仍然跑在装了它的那台机器上**（macOS arm64 / Windows x64）。
> 容器里只有 Python 包、知识库与记忆库。

## 1. 本机 Open WebUI（同一台机器，最简单）

```bash
cd horosa-skill
uv sync
uv run horosa-skill serve            # 默认 127.0.0.1:8765，无需令牌
```

Open WebUI 里：`Admin Settings → External Tools → Add Server`，`Type` 选 `MCP (Streamable HTTP)`，
URL 填 `http://127.0.0.1:8765/mcp`。

## 2. Open WebUI 在 Docker Desktop 里（Mac / Windows）

容器访问宿主用 `host.docker.internal`，于是请求带的是 `Host: host.docker.internal:8765`。
DNS-rebinding 防护默认只放行回环写法，**这个别名已经内建放行**，不需要额外配置：

```bash
uv run horosa-skill serve            # 仍然只绑 127.0.0.1 就够
```

URL 填 `http://host.docker.internal:8765/mcp`。

需要放行别的 Host 头（自定义网关域名）时：

```bash
HOROSA_MCP_ALLOWED_HOSTS="gateway.internal:8765,mybox.lan:*" uv run horosa-skill serve
```

## 3. Linux Docker / 另一台机器（必须带令牌）

绑到非回环地址时**必须**给令牌，否则拒绝启动 —— 这个 server 能读写本机记忆库、生成文件、
驱动本地 runtime，同网段裸奔等于把这些权限交出去：

```bash
TOKEN=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))")
uv run horosa-skill serve --host 0.0.0.0 --port 8765 --token "$TOKEN"
echo "token: $TOKEN"
```

客户端侧填：

| 客户端 | 填什么 |
| --- | --- |
| Open WebUI | URL `http://<host>:8765/mcp`，Headers 加 `Authorization: Bearer <token>` |
| n8n（MCP Client 节点） | Endpoint 同上，Authentication 选 `Header Auth`，Name `Authorization`，Value `Bearer <token>` |
| Dify（自定义工具 / MCP） | Server URL 同上，Header 同上 |

无令牌或令牌不对时返回 `401` 并带 `WWW-Authenticate: Bearer`；Host 头不在白名单里返回
`421 Misdirected Request`。

> **没有 TLS。** 本 server 只说 HTTP。跨机器使用时请放在反向代理（Caddy / nginx / Cloudflare Tunnel）
> 后面，让代理终结 TLS，别把 8765 直接暴露到公网。

## 4. docker compose（网关模式）

`horosa-skill/docker-compose.yml` 已经是这个形状：容器跑网关，`HOROSA_SERVER_ROOT` /
`HOROSA_CHART_SERVER_ROOT` 指向装了离线 runtime 的宿主。

```bash
cd horosa-skill
HOROSA_MCP_TOKEN=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))") docker compose up
```

## 排障

| 症状 | 原因 | 处理 |
| --- | --- | --- |
| 容器里连不上，宿主 curl 正常 | 用了 `127.0.0.1`（那是容器自己） | 换 `host.docker.internal`（Mac/Win）或宿主网段 IP（Linux） |
| `421 Misdirected Request` | Host 头不在白名单 | 加 `HOROSA_MCP_ALLOWED_HOSTS` |
| `401` + `WWW-Authenticate` | 缺令牌或令牌不对 | 检查 `Authorization: Bearer <token>` |
| 启动即退出、报 `serve.token_required` | 绑了非回环却没给令牌 | 加 `--token`，或明知风险时加 `--allow-unauthenticated` |
| 启动即退出、报 `serve.port_in_use` | 8765 被别的进程占了（常见：另一个 serve） | 报错里点了名，换 `--port` 或关掉它 |
| 工具调用回 `runtime.starting` | 离线 runtime 正在启动（首次含解压+CDS 训练） | 等 `retry_after_seconds` 秒重试**同一个调用**；`horosa-skill runtime status` 看进度 |
