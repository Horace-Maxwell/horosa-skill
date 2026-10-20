"""`client config` / setup 生成的配置载荷：按客户端形状出 horosa 条目（启动器、钉版本 wheel 缓存、Codex env 根）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from horosa_skill import __version__, clients_extra
from horosa_skill.client_config.locations import (
    _CLIENT_COMPACT_DEFAULT,
    _CLIENT_COMPACT_REASON,
    _CLIENT_NAMES,
    _codex_env_roots,
    _preferred_config_path,
)
from horosa_skill.client_config.openclaw import _build_openclaw_config
from horosa_skill.client_tools import (
    resolve_uv_command,
    resolve_uvx_command,
    wheel_asset_name,
    zero_install_wheel_url,
)
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.surfaces.mcp_server import (
    COMPACT_SURFACE_TOOL_COUNT,
    FACADE_TOOL_COUNT,
)


def _resolve_skill_root(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    if (candidate / "pyproject.toml").exists():
        return candidate
    nested = candidate / "horosa-skill"
    if (nested / "pyproject.toml").exists():
        return nested
    raise typer.BadParameter("Path must point to the horosa-skill package directory or the repo root that contains it.")


def _quote_cli_arg(value: str) -> str:
    return f'"{value}"' if any(char.isspace() for char in value) else value


def _format_cli_command(parts: list[str]) -> str:
    return " ".join(_quote_cli_arg(part) for part in parts)


def _wheel_cache_dir() -> Path:
    return Path.home() / ".horosa" / "wheels"


def _wheel_looks_valid(path: Path, version: str) -> bool:
    import zipfile

    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            metadata = f"horosa_skill-{version}.dist-info/METADATA"
            if metadata not in names or "horosa_skill/__init__.py" not in names:
                return False
            return f"Version: {version}" in archive.read(metadata).decode("utf-8", errors="replace")
    except (OSError, zipfile.BadZipFile):
        return False


def _cache_wheel(url: str, *, version: str | None = None, dest_dir: Path | None = None, fetch: Any | None = None) -> tuple[Path | None, str | None]:
    """把发布页的 wheel 预下载到 ~/.horosa/wheels/（v0.38.1 C15），返回 (本地路径 | None, 警告 | None)。

    🔴 为什么：`uvx --from <URL>` 按 URL 缓存环境，但 uv 对直链依赖「尊重 HTTP 缓存头」——每次客户端冷启动都可能
    发一次再验证请求，离线时不保证能起。配置里写本地 wheel 路径 → 冷启动零网络、离线可用；升级 = 换文件名。
    校验：zip 结构 + dist-info 的 Version 必须等于本包版本（wheel 没有单独签名；sha256 记在旁边的 .sha256）。
    """
    import hashlib

    version = version or __version__
    dest_dir = dest_dir or _wheel_cache_dir()
    dest = dest_dir / wheel_asset_name(version)
    if dest.is_file() and _wheel_looks_valid(dest, version):
        return dest, None
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        if fetch is not None:
            fetch(url, part)
        else:
            import httpx

            with httpx.Client(timeout=120.0, follow_redirects=True) as http, http.stream("GET", url) as response:
                response.raise_for_status()
                with part.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        handle.write(chunk)
        if not _wheel_looks_valid(part, version):
            part.unlink(missing_ok=True)
            return None, f"下载到的文件不是 horosa_skill {version} 的 wheel（结构或版本不符），配置里保留 URL。"
        digest = hashlib.sha256(part.read_bytes()).hexdigest()
        part.replace(dest)
        dest.with_name(dest.name + ".sha256").write_text(f"{digest}  {dest.name}\n", encoding="utf-8")
        return dest, None
    except Exception as exc:  # noqa: BLE001 - 预下载失败不阻断 setup：配置回退到 URL 形态
        return None, f"wheel 预下载失败（{type(exc).__name__}: {exc}）；配置里保留 URL，客户端冷启动时再取。"


def _build_client_config_payload(
    *, format_name: str, skill_root: Path, server_name: str, launcher: str, surface: str,
    wheel_source: str | None = None,
) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    """`client config` 的产物，也是 `setup` 第 3 步（v0.38.0 B4）。返回 (payload, stdio 命令, 工具面 env)。

    源码 checkout 只在 `uv` 启动器与 mcporter/openclaw 形态下才需要：uvx 形态是给**没有 checkout** 的机器
    用的（wheel 装出来的包旁边没有 pyproject.toml），此前一律先 `_resolve_skill_root` → 零安装用户跑
    `client config --launcher uvx-wheel` 直接 BadParameter。
    """
    launcher_key = launcher.strip().lower()
    if launcher_key not in {"uv", "uvx", "uvx-git", "uvx-wheel"}:
        raise typer.BadParameter("`--launcher` must be `uv`, `uvx-wheel`, `uvx-git` or `uvx`.")
    resolved_skill_root: Path | None = None
    if launcher_key == "uv" or format_name.strip().lower() in {"mcporter", "openclaw"}:
        resolved_skill_root = _resolve_skill_root(skill_root)
    warnings: list[str] = []
    launcher_info: dict[str, Any] = {"kind": launcher_key}
    if launcher_key in {"uvx", "uvx-git", "uvx-wheel"}:
        # 🔴 写绝对路径（v0.38.0 B2）：GUI 客户端在 Windows 上不继承 shell PATH，裸 `uvx` = file not found。
        try:
            uvx_command = resolve_uvx_command()
        except FileNotFoundError as exc:
            uvx_command = ["uvx"]
            warnings.append(f"uvx 未找到，配置里只能写裸 `uvx`（GUI 客户端可能起不来）：{exc}")
    if launcher_key == "uvx-wheel":
        # 🔴 免 git、免 PyPI 的零安装（v0.38.0 B3）：每个 Release 都附带纯 Python wheel，`uvx --from <URL>` 直接起；
        # URL 走 HOROSA_RUNTIME_MIRROR 的前缀改写（github.com:443 不通的机器只需一个开关，issue #14）。
        # uvx 按 `--from` 的 URL 缓存环境：钉版本的 URL 稳定，升级 = 换 URL（重跑 client config / setup）。
        from horosa_skill.runtime.mirrors import mirror_candidates, preferred_mirror_url

        wheel_url = zero_install_wheel_url()
        # `wheel_source`（setup 预下载到 ~/.horosa/wheels 的本地文件）优先：冷启动零网络、离线可用。
        from_value = wheel_source or preferred_mirror_url(wheel_url)
        stdio_command = [*uvx_command, "--from", from_value, "horosa-skill", "serve", "--transport", "stdio"]
        launcher_info.update({
            "wheel_url": preferred_mirror_url(wheel_url),
            **({"wheel_cached_path": wheel_source} if wheel_source else {}),
            "alternatives": mirror_candidates(wheel_url),
            "pinned_version": __version__,
            "install_hint": f"uvx --from \"{preferred_mirror_url(wheel_url)}\" horosa-skill install",
            "refresh_hint": f"uvx --refresh --from \"{preferred_mirror_url(wheel_url)}\" horosa-skill --version",
            "docs": "docs/INSTALL_RESTRICTED_NETWORK.md（镜像 / API 直链 / 离线搬运）",
        })
    elif launcher_key == "uvx":
        # PyPI 分发（v0.36.0 C4）：不需要源码 checkout；离线 runtime 仍由 `uvx horosa-skill install` 装到默认目录。
        stdio_command = [*uvx_command, "horosa-skill", "serve", "--transport", "stdio"]
    elif launcher_key == "uvx-git":
        # 🔴 PyPI 尚未开通（`pip install horosa-skill` 现在是 404），所以 `uvx` 那条今天还跑不通。
        # 直接从 Git 装是**当下唯一可用的零安装路径**；钉当前版本 tag 让配置可复现。
        stdio_command = [
            *uvx_command, "--from",
            f"git+https://github.com/Horace-Maxwell/horosa-skill@v{__version__}#subdirectory=horosa-skill",
            "horosa-skill", "serve", "--transport", "stdio",
        ]
    else:
        uv_command = resolve_uv_command()
        stdio_command = [
            *uv_command,
            "run",
            "--directory",
            str(resolved_skill_root),
            "horosa-skill",
            "serve",
            "--transport",
            "stdio",
        ]
    key = format_name.strip().lower()
    surface_key = surface.strip().lower()
    if surface_key not in {"auto", "full", "compact"}:
        raise typer.BadParameter("`--surface` must be `auto`, `full` or `compact`.")
    use_compact = _CLIENT_COMPACT_DEFAULT.get(key, False) if surface_key == "auto" else surface_key == "compact"
    surface_env = {"HOROSA_MCP_COMPACT": "1"} if use_compact else {}
    tool_surface = {
        "mode": "compact" if use_compact else "full",
        "tools": COMPACT_SURFACE_TOOL_COUNT if use_compact else FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS),
        "reason": (
            _CLIENT_COMPACT_REASON.get(key, "该客户端对工具总数敏感")
            if use_compact
            else f"该客户端能吃下全量平铺面（{FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS)} 个工具）"
        ),
        "override": "--surface full / --surface compact",
    }
    if key in {"mcporter", "openclaw"}:
        payload: dict[str, Any] = _build_openclaw_config(
            skill_root=resolved_skill_root,
            server_name=server_name,
            format_name=key,
            isolate_home=None,
        )
    elif key == "claude-code":
        payload = {
            "note": "运行下面这一条命令即可把 Horosa 注册进 Claude Code（stdio 直连，无需常驻 serve）；或把 mcpServers 合并进项目的 .mcp.json / ~/.claude.json。",
            # 🔴 必须走 _format_cli_command：checkout / uv 路径里有空格（`C:\Users\John Doe\…`、
            # `/Users/x/My Projects`）时，裸 join 出来的命令会把路径拆成两个参数 —— README 教的
            # 就是这条复制粘贴命令。精简面顺带带上 `-e HOROSA_MCP_COMPACT=1`，与 setup 的写法一致。
            "command": _format_cli_command(
                ["claude", "mcp", "add", server_name]
                + [item for key, value in (surface_env or {}).items() for item in ("-e", f"{key}={value}")]
                + ["--", *stdio_command]
            ),
            "config_path": str(_preferred_config_path("claude-code")),
            "mcpServers": {
                server_name: {
                    "command": stdio_command[0],
                    "args": stdio_command[1:],
                    **({"env": surface_env} if surface_env else {}),
                }
            },
            "tool_surface": tool_surface,
            **({"env_note": "精简面：给这条命令加 `-e HOROSA_MCP_COMPACT=1`"} if use_compact else {}),
            "alternative_http": {
                # 跟随 launcher：uvx/uvx-git 用户没有 checkout，`uv run` 那条对他们不成立。
                "note": ("或先 `" + (" ".join(stdio_command[:-2]) if launcher_key != "uv"
                                     else "uv run --directory <checkout>/horosa-skill horosa-skill")
                         + " serve` 再注册 HTTP 端点："),
                "command": f"claude mcp add {server_name} --transport http http://127.0.0.1:8765/mcp",
            },
        }
    elif key == "claude-desktop":
        payload = {
            "note": "合并进 Claude Desktop 的 claude_desktop_config.json（mcpServers 键下）。",
            "config_path": str(_preferred_config_path("claude-desktop")),
            "tool_surface": tool_surface,
            "mcpServers": {
                server_name: {
                    "command": stdio_command[0],
                    "args": stdio_command[1:],
                    **({"env": surface_env} if surface_env else {}),
                }
            },
        }
    elif key == "codex":
        # Codex 硬约束（examples/clients/codex.md 有全文）：RawMcpServerConfig deny_unknown_fields
        # （字段写错=整段拒收）；env 不转发 shell 环境 → HOROSA_* 必须显式写进 env 表；
        # 启动超时默认 10 s < 首次冷启动（runtime 预热 ~45s）→ 显式 120s；工具默认 60s < 长盘
        # （tianxing 跨月扫描）→ 600s。首轮工具目录只等 1s（mcp_optional_startup_grace_ms=1000）：
        # 冷启动时第一轮对话可能看不到 horosa 工具，第二轮即恢复——要首轮即见就解开 required 注释
        # （代价：server 起不来时 Codex 启动直接报错）。
        payload = {
            "note": (
                "追加到 ~/.codex/config.toml（或用 --write 原位合并，只动 [mcp_servers." + server_name + "] 表并先备份）。"
                "HTTP 变体需先 `uv run horosa-skill serve`。"
            ),
            "config_path": str(_preferred_config_path("codex")),
            "toml_stdio": (
                f"[mcp_servers.{server_name}]\n"
                # command 必须与 args/cwd 一样走 json.dumps：JSON 转义 ⊂ TOML 基本字符串转义。
                # 裸插值在 Windows 上会把路径里的反斜杠原样写进 TOML → 整个文件不可解析
                # （tomllib: Unescaped '\'；mac/Linux 路径无反斜杠故恒绿，windows-smoke 才炸）。
                f"command = {json.dumps(stdio_command[0])}\n"
                f"args = {json.dumps(stdio_command[1:])}\n"
                # 🔴 cwd 只在 uv（源码 checkout）形态写。uvx 形态是给**没有 checkout** 的机器用的，
                # 写死本机路径 → 对方 Codex 起不来（cwd 不存在即 spawn 失败）。
                + (f"cwd = {json.dumps(str(resolved_skill_root))}\n" if launcher_key == "uv" else "")
                + (
                "# 冷启动（首次装 runtime/预热）可超 Codex 默认 10 s；长盘（择日扫描）可超默认工具 60 s。\n"
                "startup_timeout_sec = 120\n"
                "tool_timeout_sec = 600\n"
                "# 首轮即见工具（否则冷启动首轮目录里可能没有 horosa，第二轮恢复）；\n"
                "# 代价：server 启动失败时 Codex 直接报错。按需解开：\n"
                "# required = true\n"
                "\n"
                f"[mcp_servers.{server_name}.env]\n"
                + ("HOROSA_MCP_COMPACT = \"1\"          # " + tool_surface["reason"] + "\n" if use_compact else "")
                # 🔴 v0.38.1 C6：Codex 不转发你 shell 里的 HOROSA_*。runtime 根与数据目录显式写成绝对路径
                # （与 MCPB / 插件的 user_config 一致），否则 Codex 起的 server 会算出另一个 runtime 根。
                # 不写 `env_vars`：老版本 Codex 对未知键 deny_unknown_fields，会整块拒收这个 server。
                + f"HOROSA_RUNTIME_ROOT = {json.dumps(str(_codex_env_roots()['HOROSA_RUNTIME_ROOT']))}\n"
                + f"HOROSA_SKILL_DATA_DIR = {json.dumps(str(_codex_env_roots()['HOROSA_SKILL_DATA_DIR']))}\n"
                + "# Codex 不把 shell 环境交给 server——任何 HOROSA_* 必须在这里显式声明才可见，例如：\n"
                f"# HOROSA_MCP_COMPACT = \"1\"          # 11 门面模式（Codex 无工具搜索，{len(TOOL_DEFINITIONS)} 技法全量较重）\n"
                "# HOROSA_TOOLSETS = \"astro,cn\"      # 或按域裁剪\n"
                )
            ),
            "toml_http": (
                f"[mcp_servers.{server_name}]\n"
                "url = \"http://127.0.0.1:8765/mcp\"\n"
                "startup_timeout_sec = 120\n"
                "tool_timeout_sec = 600\n"
            ),
            "docs": "examples/clients/codex.md（含 exec 模式文本回落、enabled_tools 高频入口集、排障清单）",
            "tool_surface": tool_surface,
        }
    elif key == "cursor":
        # Cursor 官方 install deep link：config = base64({"command","args"})，点击即装。
        import base64

        cursor_entry = {"command": stdio_command[0], "args": stdio_command[1:]}
        if surface_env:
            cursor_entry["env"] = surface_env
        cursor_config = json.dumps(cursor_entry, ensure_ascii=False)
        encoded = base64.b64encode(cursor_config.encode("utf-8")).decode("ascii")
        payload = {
            "note": "点击 deep_link 一键安装进 Cursor；或把 mcpServers 合并进 ~/.cursor/mcp.json。",
            "config_path": str(_preferred_config_path("cursor")),
            "deep_link": f"cursor://anysphere.cursor-deeplink/mcp/install?name={server_name}&config={encoded}",
            "mcpServers": {server_name: cursor_entry},
            "tool_surface": tool_surface,
        }
    elif key == "vscode":
        # VS Code 官方安装链接（vscode:mcp/install?<url-encoded JSON>）+ CLI 等价命令。
        from urllib.parse import quote

        vscode_entry = {"name": server_name, "command": stdio_command[0], "args": stdio_command[1:]}
        if surface_env:
            vscode_entry["env"] = surface_env
        vscode_config = json.dumps(vscode_entry, ensure_ascii=False)
        # mcp.json 形状（`servers` 根键 + `type: stdio`）：让 --write / setup 能合并进用户级 mcp.json，
        # 而不是把 install_link/cli_command 这些说明写成配置（v0.38.0 B2）。
        vscode_file_entry: dict[str, Any] = {"type": "stdio", "command": stdio_command[0], "args": stdio_command[1:]}
        if surface_env:
            vscode_file_entry["env"] = surface_env
        payload = {
            "note": "点击 install_link 一键安装进 VS Code；或运行 cli_command；或把 servers 合并进用户级 mcp.json。",
            "config_path": str(_preferred_config_path("vscode")),
            "servers": {server_name: vscode_file_entry},
            "install_link": f"vscode:mcp/install?{quote(vscode_config, safe='')}",
            # 单引号只在 POSIX shell 里成立；cmd.exe / PowerShell 会把它当字面量 → JSON 解析失败。
            # 两条都给，让 Windows 用户不用自己猜转义。
            "cli_command": f"code --add-mcp '{vscode_config}'",
            "cli_command_windows": "code --add-mcp \"" + vscode_config.replace('"', '\\"') + "\"",
            "tool_surface": tool_surface,
        }
    elif key in {"gemini", "windsurf", "cline", "zed"}:
        # 四家都是「一个 JSON 文件里挂一个 stdio server」，只是根键与个别字段不同。
        entry: dict[str, Any] = {"command": stdio_command[0], "args": stdio_command[1:]}
        if surface_env:
            entry["env"] = surface_env
        if key == "gemini":
            # Gemini CLI 的 per-server `timeout` 是毫秒；默认 600000（10 分钟）已够长盘扫描。
            # `trust: false` = 每次工具调用仍走确认，别替用户放开。
            entry.update({"timeout": 600000, "trust": False})
            root_key = "mcpServers"
        elif key == "windsurf":
            root_key = "mcpServers"
        elif key == "cline":
            # Cline 的 per-server `timeout` 是**秒**（源码 sdk/packages/shared/src/mcp.ts：默认 60，范围 1–3600）。
            entry.update({"type": "stdio", "timeout": 600})
            root_key = "mcpServers"
        else:  # zed：context_servers 下直接 command/args/env（zed.dev/docs/ai/mcp，2026-09 核对）；无 `source` 字段
            # Zed 的 ContextServerCommand 也有 per-server `timeout`（秒，默认 60）——这才是 Zed 的真缺口。
            entry["timeout"] = 600
            root_key = "context_servers"
        config_path = str(_preferred_config_path(key))
        payload = {
            "note": f"合并进 {config_path}（{root_key} 键下）。",
            "config_path": config_path,
            root_key: {server_name: entry},
            "tool_surface": tool_surface,
        }
    elif key in clients_extra.EXTRA_CLIENTS:
        # v0.41.0：16 家的条目形状 / 根键 / 超时字段都在 clients_extra 一行里；这里只补启动器与工具面。
        payload = clients_extra.build_payload(
            key, server_name=server_name, stdio_command=stdio_command, surface_env=surface_env,
            env_roots=_codex_env_roots(), config_path=_preferred_config_path(key),
        )
        payload["tool_surface"] = tool_surface
        warnings.extend(payload.pop("warnings", []))
    else:
        raise typer.BadParameter(
            "format must be one of: " + " / ".join((*_CLIENT_NAMES, "mcporter", "openclaw"))
        )
    payload["launcher"] = launcher_info
    if warnings:
        payload["warnings"] = warnings
    return payload, stdio_command, surface_env
