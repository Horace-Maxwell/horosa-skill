# ChatGPT / claude.ai 远程连接器：经 OAuth 网关接入 / Remote connectors through an OAuth gateway

> 现状（2026-09）：claude.ai 的自定义连接器与 ChatGPT 的远程 MCP **只接 OAuth**（claude.ai：可选 OAuth client id/secret；
> ChatGPT：OAuth + CIMD/DCR），**没有**填静态 Bearer 令牌的入口。本 server 的 `serve --transport streamable-http --token`
> 只提供静态 Bearer。两者之间需要一层**终结 OAuth 的 HTTPS 网关**：网关对连接器说 OAuth，对本 server 注入
> `Authorization: Bearer <HOROSA_MCP_TOKEN>`。本仓不实现 OAuth 资源服务器（另案）。
>
> 🔴 **无鉴权把 `serve --host 0.0.0.0` 暴露到公网 = 任何人都能读你的记忆库（`horosa_memory_query`）并起盘。**
> 网关之外的路径一律回环；令牌只配在网关里。

## 拓扑

```
ChatGPT / claude.ai ──OAuth──▶ HTTPS 网关（Cloudflare Access / oauth2-proxy / Authentik）──Bearer──▶ horosa-skill serve（127.0.0.1:8765）
```

## 本机侧

```bash
export HOROSA_MCP_TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
uv run horosa-skill serve --transport streamable-http --host 127.0.0.1 --port 8765 --token "$HOROSA_MCP_TOKEN"
# 网关经隧道 / 反代打到 127.0.0.1:8765/mcp；HOROSA_MCP_ALLOWED_HOSTS 加上网关对外的 Host（防 DNS 重绑定 421）
```

## 网关侧（两种现成配方）

**Cloudflare Access + cloudflared（推荐，零公网端口）**

1. `cloudflared tunnel` 把 `https://horosa.example.com` 指到 `http://127.0.0.1:8765`。
2. Access 应用（Self-hosted）保护该主机名，身份源选你自己的 IdP；在 **Policies → Include** 只放行你的邮箱。
3. Access 的 **Service Auth / Header** 里为上游注入请求头 `Authorization: Bearer <HOROSA_MCP_TOKEN>`
   （Zero Trust → Access → Applications → 该应用 → Settings → *Additional settings* → HTTP headers）。
4. 连接器一侧：claude.ai *Settings → Connectors → Add custom connector* 填 `https://horosa.example.com/mcp`，
   OAuth 走 Access 的登录页；ChatGPT *Settings → Connectors → Create* 同一 URL。

**oauth2-proxy（自托管）**

```yaml
# oauth2-proxy.cfg（节选）
upstreams = ["http://127.0.0.1:8765/"]
provider = "oidc"                      # 或 github / google
oidc_issuer_url = "https://<your-idp>/"
email_domains = ["example.com"]
pass_authorization_header = false      # 不把 IdP 的 token 透传给 horosa
skip_provider_button = true
# 上游注入静态 Bearer（oauth2-proxy ≥ 7.4：injectRequestHeaders）
```

```yaml
injectRequestHeaders:
  - name: Authorization
    values:
      - value: "QmVhcmVyIDx5b3VyLXRva2VuPg=="   # base64("Bearer <HOROSA_MCP_TOKEN>")
```

## 验收

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://horosa.example.com/mcp            # 未登录：302/401（网关拦下）
curl -sS -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer 错的" http://127.0.0.1:8765/mcp   # 本机直连：401
curl -sS -o /dev/null -w "%{http_code}\n" -H "Host: evil.example" -H "Authorization: Bearer $HOROSA_MCP_TOKEN" http://127.0.0.1:8765/mcp  # 421（Host 不在白名单）
```

连接器里看到 116 个 `horosa_*` 工具即接通；`horosa_agent_guidance` 是第一条该调的。

---

**English summary.** claude.ai custom connectors and ChatGPT remote MCP only speak OAuth; this server only offers a static
Bearer token. Put an OAuth-terminating HTTPS gateway (Cloudflare Access + cloudflared, or oauth2-proxy) in front of
`serve --transport streamable-http --host 127.0.0.1 --token …`, have the gateway inject `Authorization: Bearer <HOROSA_MCP_TOKEN>`
towards the upstream, and add the gateway's public Host to `HOROSA_MCP_ALLOWED_HOSTS`. Never expose `--host 0.0.0.0`
without authentication: anyone could read your memory store. No OAuth resource server ships with this repo.
