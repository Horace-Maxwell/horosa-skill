"""`client check`：读真实配置文件，按各家规则（占位符白名单、超时、环境转发）体检 horosa 条目与 skill 状态。"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import typer

from horosa_skill import __version__, clients_extra
from horosa_skill.client_config import locations as client_locations
from horosa_skill.client_config.locations import _CLIENT_COMPACT_DEFAULT, _CLIENT_NAMES
from horosa_skill.client_config.merge import _PIN_GIT, _PIN_LOCAL_WHEEL, _PIN_WHEEL

# 根键：mcpServers（多数）/ servers（VS Code）/ context_servers（Zed）/ mcp_servers（Codex TOML）；
# v0.41.0 起 mcp（OpenCode）/ 字面量 amp.mcpServers（Amp）/ extensions（Goose YAML）。
_SERVER_ROOT_KEYS = ("mcpServers", "servers", "context_servers", "mcp_servers", "mcp", "amp.mcpServers", "extensions")


def _normalize_client_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """各家条目形状不同，体检前统一成 {command, args, env, …}（v0.41.0）。

    OpenCode：`command` 是数组（程序 + 参数）、env 叫 `environment`；Goose：`cmd` / `args` / `envs`。
    不归一的话，`_audit_client_entry` 看不到 args → 缺 `--transport stdio`、版本漂移这些检查全部静默跳过。
    """
    out = dict(entry)
    command = out.get("command")
    if isinstance(command, list) and command:
        out["command"] = str(command[0])
        out["args"] = [str(item) for item in command[1:]] + [str(item) for item in (out.get("args") or [])]
    elif "cmd" in out and "command" not in out:
        out["command"] = out.get("cmd")
    for alias in ("environment", "envs"):
        if isinstance(out.get(alias), dict) and "env" not in out:
            out["env"] = out[alias]
    return out


def _iter_client_entries(payload: Any) -> Any:
    """从一份客户端配置里找出 horosa 条目（含 Claude Code 的 projects.<path>.mcpServers 嵌套）。"""
    if not isinstance(payload, dict):
        return
    for key in _SERVER_ROOT_KEYS:
        block = payload.get(key)
        if isinstance(block, dict):
            for name, entry in block.items():
                if isinstance(entry, dict) and "horosa" in str(name).lower():
                    yield name, _normalize_client_entry(entry)
    projects = payload.get("projects")
    if isinstance(projects, dict):
        for project_path, project in projects.items():
            for name, entry in _iter_client_entries(project):
                yield f"{project_path}::{name}", entry


# 每个客户端**真的会展开**的 `${…}` 占位符（2026-09 按各家官方文档核对；前缀型以 `:` 结尾）。
# 不在表里的占位符会被客户端原样传给 server → `--directory ${x}` 不存在、env 里留着字面量。
CLIENT_PLACEHOLDER_WHITELIST: dict[str, tuple[str, ...]] = {
    "cursor": ("env:", "userHome", "workspaceFolder", "workspaceFolderBasename", "pathSeparator"),
    "vscode": ("workspaceFolder", "workspaceFolderBasename", "env:", "userHome", "input:"),
    "claude-code": ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA"),
    "claude-desktop": (),
    "codex": (),
    "gemini": (),
    "windsurf": (),
    "cline": (),
    "zed": (),
    # v0.41.0 的 16 家：生成器只写绝对路径，一个占位符都不用（各家展开规则不一，最安全的是不依赖）。
    **{key: () for key in clients_extra.EXTRA_CLIENTS},
}
_PLACEHOLDER_RE = re.compile(r"\$\{([^}]*)\}")


def _placeholder_allowed(var: str, client: str) -> bool:
    base = var.split(":-", 1)[0]
    for allowed in CLIENT_PLACEHOLDER_WHITELIST.get(client, ()):
        if allowed.endswith(":"):
            if base.startswith(allowed):
                return True
        elif base == allowed:
            return True
    return False


def _expand_client_placeholders(text: str, *, client: str, config_dir: Path | None) -> str:
    """按客户端规则把占位符换成本机路径（只为了检查 `--directory` 指得对不对；不知道的原样保留）。

    `${workspaceFolder}` / `${CLAUDE_PROJECT_DIR}` → 项目根（配置文件在 `.cursor/` / `.vscode/` 里时取上一层）。
    """
    project_root: Path | None = None
    if config_dir is not None:
        project_root = config_dir.parent if config_dir.name in {".cursor", ".vscode", ".gemini"} else config_dir

    def repl(match: re.Match[str]) -> str:
        var = match.group(1)
        base, _, default = var.partition(":-")
        if base in {"workspaceFolder", "CLAUDE_PROJECT_DIR"} and project_root is not None:
            return str(project_root)
        if base == "workspaceFolderBasename" and project_root is not None:
            return project_root.name
        if base == "userHome":
            return str(Path.home())
        if base == "pathSeparator":
            return os.sep
        if base.startswith("env:"):
            return os.environ.get(base[4:], default)
        return match.group(0)

    return _PLACEHOLDER_RE.sub(repl, text)


def _audit_client_entry(
    name: str, entry: dict[str, Any], *, client: str, config_dir: Path | None = None
) -> list[dict[str, str]]:
    """一条 horosa 配置的体检结果。纯函数，便于测试与守卫复用。"""
    problems: list[dict[str, str]] = []
    args = [str(a) for a in (entry.get("args") or [])]
    command = str(entry.get("command") or "")
    blob = " ".join([command, *args, json.dumps(entry.get("env") or {}, ensure_ascii=False)])

    # 🔴 按客户端白名单逐个判：此前只放行 `${workspaceFolder}` 与 `${CLAUDE_PROJECT_DIR`，于是 `.vscode/mcp.json`
    # 里写 `${CLAUDE_PROJECT_DIR}`（VS Code 不认）是绿的，而 `${env:HOME}`（Cursor / VS Code 都认）是红的。
    for var in _PLACEHOLDER_RE.findall(blob):
        if not _placeholder_allowed(var, client):
            allowed = ", ".join("${" + a + ("…}" if a.endswith(":") else "}") for a in CLIENT_PLACEHOLDER_WHITELIST.get(client, ())) or "（该客户端不展开任何占位符）"
            problems.append({
                "code": "unexpanded_placeholder",
                "detail": f"`${{{var}}}` 不是 {client} 会展开的占位符，会原样传给 server。",
                "fix": f"换成真实路径，或只用 {client} 支持的变量：{allowed}。",
            })
            break
    if args and "--transport" not in args:
        problems.append({
            "code": "missing_transport",
            "detail": "没有 `--transport stdio`。",
            "fix": "在 args 末尾加 [\"--transport\", \"stdio\"]；缺它时旧版本会默认起 HTTP server，客户端连不上。",
        })
    if "mcp" in args and "serve" not in args:
        problems.append({
            "code": "legacy_subcommand",
            "detail": "用的是已下线的 `horosa-skill mcp` 子命令。",
            "fix": "改成 `serve --transport stdio`。",
        })
    if "--directory" in args:
        index = args.index("--directory")
        if index + 1 < len(args):
            target = args[index + 1]
            # 🔴 相对路径要按**配置文件所在目录**解析，不是按跑 check 的那一刻的 CWD ——
            # 客户端启动 server 时的工作目录是项目根，而 `client check` 可能在任何地方被调用。
            expanded = _expand_client_placeholders(target, client=client, config_dir=config_dir)
            resolved = Path(expanded).expanduser()
            if not resolved.is_absolute() and config_dir is not None:
                resolved = (config_dir / resolved).resolve()
            # 占位符按客户端规则展开后再查；展开不了的（插件作用域 / 未知）跳过而不是误报。
            if "${" not in expanded and not (resolved / "pyproject.toml").is_file():
                problems.append({
                    "code": "directory_missing",
                    "detail": f"--directory 指向的目录里没有 pyproject.toml：{target}" + (f"（展开后 {expanded}）" if expanded != target else ""),
                    "fix": "指向 horosa-skill 包目录（含 pyproject.toml 的那一层）。",
                })
    # 裸命令名要靠 PATH；GUI 客户端（Claude Desktop / Cursor / VS Code…）在 Windows 上不继承 shell PATH，
    # 终端里能跑的 `uvx` 在客户端里就是 file not found（v0.38.0 B2）。绝对路径不查 PATH。
    if command and not any(sep in command for sep in ("/", "\\")) and shutil.which(command) is None:
        problems.append({
            "code": "command_not_on_path",
            "detail": f"`{command}` 不在 PATH 上（本机 which 找不到）；GUI 客户端还不继承你的 shell PATH。",
            "fix": "重跑 `horosa-skill client config --format <client>`（现在写绝对路径），或把 command 改成可执行文件的完整路径。",
        })
    # 钉版本的零安装源（wheel 资产 URL / git tag）与本包版本不一致 → 客户端跑的是别的版本（v0.38.0 B3）。
    if "--from" in args:
        source = args[args.index("--from") + 1] if args.index("--from") + 1 < len(args) else ""
        # v0.38.1 C15：`--from` 可以是 setup 预下载的本地 wheel；文件没了（清过缓存 / 换了机器）客户端就起不来。
        if source.endswith(".whl") and "://" not in source and not Path(source).expanduser().is_file():
            problems.append({
                "code": "wheel_cache_missing",
                "detail": f"--from 指向的本地 wheel 不存在：{source}",
                "fix": "重跑 `horosa-skill setup --client <client>`（会重新下载到 ~/.horosa/wheels/），或改回发布页的 wheel URL。",
            })
        pinned = _PIN_WHEEL.search(source) or _PIN_GIT.search(source) or _PIN_LOCAL_WHEEL.search(source)
        if pinned and pinned.group(1) != __version__:
            problems.append({
                "code": "launcher_version_drift",
                "detail": f"配置钉的是 v{pinned.group(1)}，本机 horosa-skill 是 v{__version__}。",
                "fix": "重跑 `horosa-skill client config --format <client> --launcher uvx-wheel --write <配置>`（或 `setup`）让 URL 跟上版本。",
            })
    if command.endswith("uvx") and "--from" not in args:
        problems.append({
            "code": "pypi_not_published",
            "detail": "`uvx horosa-skill` 依赖 PyPI，而本项目的 PyPI 通道尚未开通。",
            "fix": "用 `uvx --from \"git+https://github.com/Horace-Maxwell/horosa-skill@v<版本>"
                   "#subdirectory=horosa-skill\" horosa-skill`，或本地 checkout 走 `uv run --directory`。",
        })
    if client == "codex":
        # 缺省 = Codex 默认 startup 10 s / tool 60 s：首次冷启动要解压 runtime、择日扫描本来就几分钟——
        # 「一堆报错」（issue #18）最像的成因就是这两个没写。此前只在**写了且太短**时才报（v0.38.0 B2 补缺席分支）。
        startup = entry.get("startup_timeout_sec")
        if startup is None:
            problems.append({
                "code": "codex_startup_timeout_missing",
                "detail": "没写 startup_timeout_sec（Codex 默认 10 秒，首次启动要解压 runtime）。",
                "fix": "在 [mcp_servers.<name>] 里加 `startup_timeout_sec = 120`。",
            })
        elif clients_extra.timeout_too_short(startup, 120):
            problems.append({
                "code": "codex_startup_timeout_too_short",
                "detail": f"startup_timeout_sec={startup}（默认 10 秒）。",
                "fix": "设 120 以上：首次启动要解压 runtime。",
            })
        tool_timeout = entry.get("tool_timeout_sec")
        if tool_timeout is None:
            problems.append({
                "code": "codex_tool_timeout_missing",
                "detail": "没写 tool_timeout_sec（Codex 默认 60 秒，择日类扫描本来就要几分钟）。",
                "fix": "在 [mcp_servers.<name>] 里加 `tool_timeout_sec = 600`。",
            })
        elif clients_extra.timeout_too_short(tool_timeout, 600):
            problems.append({
                "code": "codex_tool_timeout_too_short",
                "detail": f"tool_timeout_sec={tool_timeout}（默认 60 秒）。",
                "fix": "设 600 以上：择日类扫描本来就要几分钟。",
            })
        cwd = entry.get("cwd")
        if cwd and "${" not in str(cwd) and not Path(str(cwd)).expanduser().is_dir():
            problems.append({
                "code": "codex_cwd_missing",
                "detail": f"cwd 指向的目录不存在：{cwd}（Codex 会 spawn 失败）。",
                "fix": "删掉 cwd（uvx 形态不需要），或指向存在的 horosa-skill 包目录。",
            })
        # v0.38.1 C6：Codex 不把你 shell 里的 HOROSA_* 交给 server。runtime 根 / 数据目录若只设在 shell 里，
        # Codex 起的那份 server 会算出**另一个** runtime 根 → 终端里 doctor ready、Codex 里全是 not_installed。
        env_table = entry.get("env") or {}
        missing_roots = [key for key in ("HOROSA_RUNTIME_ROOT", "HOROSA_SKILL_DATA_DIR") if not str(env_table.get(key) or "").strip()]
        if missing_roots:
            problems.append({
                "code": "codex_env_roots_missing",
                "detail": f"[mcp_servers.<name>.env] 缺 {' / '.join(missing_roots)}：Codex 不转发 shell 环境，server 会用默认目录。",
                "fix": "重跑 `horosa-skill client config --format codex --write ~/.codex/config.toml`（v0.38.1 起写入两个绝对路径）。",
            })
    if client in {"cline", "zed"}:
        # v0.38.1 C5：两家的 per-server `timeout` 都是秒、默认 60 —— 择日扫描 / 冷启动都会超。
        timeout = entry.get("timeout")
        if timeout is None:
            problems.append({
                "code": f"{client}_tool_timeout_missing",
                "detail": f"没写 timeout（{client} 默认 60 秒；择日类扫描与首次冷启动都可能超）。",
                "fix": "在该 server 条目里加 `\"timeout\": 600`（秒）。",
            })
        elif clients_extra.timeout_too_short(timeout, 600):
            problems.append({
                "code": f"{client}_tool_timeout_too_short",
                "detail": f"timeout={timeout}（{client} 默认 60 秒）。",
                "fix": "设 600 以上（秒）。",
            })
    problems.extend(clients_extra.audit(client, entry))
    return problems


_SKILL_STATE_HINTS = {
    "absent": "没装：`horosa-skill client skill --client {client}`（或重跑 setup）把规则装进去。",
    "outdated": "装的是旧版：`horosa-skill client skill --client {client}` 更新。",
    "modified": "skill 文件被改过；更新时会先备份成 horosa-agent.horosa-bak。",
    "foreign": "同名文件夹不是本工具装的，没有动它。",
    "symlink": "由别的工具（如 `npx skills`）以软链接管理，请在那边更新。",
}


def _client_skill_report(client: str) -> list[dict[str, Any]]:
    from horosa_skill import skill_install

    try:
        bundle = skill_install.bundle_digests()
    except FileNotFoundError:
        return []
    out: list[dict[str, Any]] = []
    for skills_dir in skill_install.client_skill_dirs(client):
        status = skill_install.skill_status(skills_dir, bundle=bundle)
        hint = _SKILL_STATE_HINTS.get(status["state"])
        if hint:
            status["hint"] = hint.format(client=client)
        out.append(status)
    return out


def _client_check_report(targets: list[str], config_path: Path | None = None) -> dict[str, Any]:
    """`client check` 的报告；`setup` 第 5 步回读磁盘时用同一份（v0.38.0 B4）。"""
    results: list[dict[str, Any]] = []
    for name in targets:
        if name not in _CLIENT_NAMES:
            raise typer.BadParameter(f"未知客户端 `{name}`。可选：{', '.join(_CLIENT_NAMES)}")
        candidates = [config_path] if config_path else client_locations._client_config_locations(name)
        found: list[dict[str, Any]] = []
        for candidate in candidates:
            path = candidate.expanduser()
            if not path.is_file():
                continue
            try:
                if path.suffix == ".toml":
                    import tomllib

                    payload = tomllib.loads(path.read_text(encoding="utf-8"))
                    payload = {"mcpServers": (payload.get("mcp_servers") or {})}
                elif path.name.endswith(".cordis.yml"):
                    payload = {"mcpServers": clients_extra.read_dsh_patch(path.read_text(encoding="utf-8-sig"))}
                elif path.suffix in {".yaml", ".yml"}:
                    from horosa_skill import yaml_block

                    payload = {"extensions": yaml_block.read_children(path.read_text(encoding="utf-8-sig"), "extensions")}
                else:
                    from horosa_skill import jsonc as _jsonc

                    payload = _jsonc.loads(path.read_text(encoding="utf-8-sig"))  # Zed / VS Code 允许注释与尾逗号
            except (OSError, ValueError) as exc:
                found.append({"path": str(path), "ok": False, "error": f"{type(exc).__name__}: {exc}"})
                continue
            entries = list(_iter_client_entries(payload))
            if not entries:
                found.append({"path": str(path), "ok": True, "horosa_entries": 0,
                              "note": "该文件存在但没有 horosa 条目。"})
                continue
            for entry_name, entry in entries:
                problems = _audit_client_entry(entry_name, entry, client=name, config_dir=path.parent)
                found.append({
                    "path": str(path), "entry": entry_name, "ok": not problems,
                    "problems": problems,
                    "tool_surface": "compact" if (entry.get("env") or {}).get("HOROSA_MCP_COMPACT") else "full",
                    "recommended_surface": "compact" if _CLIENT_COMPACT_DEFAULT.get(name) else "full",
                })
        results.append({
            "client": name,
            "searched": [str(Path(item).expanduser()) for item in candidates],
            "configured": bool([f for f in found if f.get("entry")]),
            "findings": found,
            "fix_command": f"uv run horosa-skill client config --format {name}",
            # v0.41.0：skill 装没装、是不是本版——只报告，不计入 problems（MCP 连得上与否和它无关）。
            "skill": _client_skill_report(name),
        })
    problems_total = sum(len(f.get("problems") or []) for r in results for f in r["findings"])
    configured = [r["client"] for r in results if r["configured"]]
    return {
        "ok": problems_total == 0,
        "configured_clients": configured,
        "problems": problems_total,
        "summary": (
            f"检查了 {len(results)} 个客户端；已配置 {len(configured)} 个"
            + (f"，发现 {problems_total} 处问题。" if problems_total else "，未发现问题。")
        ),
        "clients": results,
    }
