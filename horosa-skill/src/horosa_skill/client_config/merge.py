"""把 horosa 条目合并写进客户端配置文件：JSON / JSONC（保注释）/ Codex TOML / Goose YAML，只动自己那一段。"""
from __future__ import annotations

import json
import os
import re
import stat
import time
from pathlib import Path
from typing import Any

import typer

from horosa_skill import clients_extra, fsretry


def _write_json_file(path: Path, payload: object) -> Path:
    """生成件（报告 JSON、mcporter 工作区配置…）：整份写，但同样原子替换、保留已有文件的权限位。"""
    output_path = path.expanduser().resolve()
    _atomic_write(output_path, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    return output_path


BACKUP_SUFFIX = ".horosa-bak"
# 第一份 `.horosa-bak` 永远是「我们第一次碰这个文件之前」的样子，永不覆盖；之后每次真改动另存一份带时间戳的，只留最近几份。
MAX_TIMESTAMPED_BACKUPS = 5


def _file_mode(path: Path) -> int | None:
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return None


def _atomic_write(target: Path, data: bytes, *, mode: int | None = None) -> None:
    """临时文件 + 原子替换；目标已存在就沿用它的权限位（`0600` 的配置不会变成 `0644`）。

    🔴 C-16：旧实现用 `write_text` 写临时文件再替换，新文件按 umask 建（通常 0644）——用户特意设成 0600、里面还有别家
    API key 的 `~/.cursor/mcp.json` / `~/.codex/config.toml`，跑一次 setup 就变成同机其他用户可读。
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    keep = _file_mode(target) if mode is None else mode
    tmp = target.with_name(f"{target.name}.horosa-tmp")
    tmp.write_bytes(data)
    try:
        if keep is not None:
            os.chmod(tmp, keep)
        fsretry.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def _backup_before_change(target: Path, original: bytes) -> Path | None:
    """改写之前留底：第一次留 `<name>.horosa-bak`（之后永不覆盖）；以后每次另存 `<name>.horosa-bak.<时间戳>`，只留最近几份。

    🔴 MCP-12：旧实现每次都覆盖同一个 `.horosa-bak`——跑第二次 setup，备份里就只剩我们自己上一次写的东西，
    用户的原文件没了。备份与原文件同权限（备份里有的密钥，原文件不让别人读，备份也不能让）。
    """
    mode = _file_mode(target)
    first = target.with_name(f"{target.name}{BACKUP_SUFFIX}")
    if not first.exists():
        _atomic_write(first, original, mode=mode)
        return first
    try:
        if first.read_bytes() == original:
            return None  # 要备份的正是第一份备份：不重复留
    except OSError:
        pass
    stamp = time.strftime("%Y%m%dT%H%M%S", time.localtime())
    extra = target.with_name(f"{target.name}{BACKUP_SUFFIX}.{stamp}")
    serial = 1
    while extra.exists():
        serial += 1
        extra = target.with_name(f"{target.name}{BACKUP_SUFFIX}.{stamp}-{serial}")
    _atomic_write(extra, original, mode=mode)
    stamped = sorted(target.parent.glob(f"{target.name}{BACKUP_SUFFIX}.*"))
    for old in stamped[:-MAX_TIMESTAMPED_BACKUPS]:
        try:
            old.unlink()
        except OSError:
            pass
    return extra


def _commit_config(target: Path, new: bytes) -> dict[str, Any]:
    """所有客户端配置的唯一落盘口：内容没变就什么都不写（也不备份）；变了就先留底再原子替换，权限位不变。"""
    original = target.read_bytes() if target.exists() else None
    if original is not None and original == new:
        return {"changed": False, "backup": None}
    backup = _backup_before_change(target, original) if original else None
    _atomic_write(target, new)
    return {"changed": True, "backup": str(backup) if backup else None}


_MERGEABLE_ROOT_KEYS = ("mcpServers", "servers", "context_servers")
_PIN_WHEEL = re.compile(r"/v(\d+\.\d+\.\d+)/horosa_skill-\d+\.\d+\.\d+-py3-none-any\.whl")
_PIN_GIT = re.compile(r"horosa-skill@v(\d+\.\d+\.\d+)#")
_PIN_LOCAL_WHEEL = re.compile(r"horosa_skill-(\d+\.\d+\.\d+)-py3-none-any\.whl$")


def _merge_client_config(path: Path, payload: object) -> dict[str, Any]:
    """`client config --write` / `setup` 落盘（v0.38.0 B2：根键感知、备份、原子替换、绝不写元键）。

    v0.33.0 的合并只认 `mcpServers`：VS Code 的根键是 `servers`、Zed 是 `context_servers`、claude-code
    产物只有一条命令字符串——这三家 `--write ~/.config/zed/settings.json` 会把用户整个 settings.json
    覆盖成我们的 payload（连 `note`/`tool_surface` 一起写进去），且 JSON 目标不备份、非原子写。
    现在：① 只动 `<root>[<server_name>]`，其余键（`theme`、别的 server…）逐字保留；② 目标存在则先
    `.horosa-bak`；③ 临时文件 + `os.replace`，写到一半断电也不会留半个文件；④ 非对象 JSON 拒写；
    ⑤ 没有可合并根键的格式（openclaw 之外的纯说明产物）拒写而不是把说明当配置。
    """
    target = path.expanduser().resolve()
    if isinstance(payload, dict) and isinstance(payload.get("toml_stdio"), str):
        outcome = _commit_config(target, _codex_toml_merged(target, payload["toml_stdio"]).encode("utf-8"))
        return {"path": str(target), "format": "toml", "root_key": "mcp_servers", **outcome}
    if not isinstance(payload, dict):
        raise typer.BadParameter("这份产物不是对象，无法合并进客户端配置。")
    if payload.get("config_format") == "yaml":
        return _write_yaml_merge(target, payload)
    if payload.get("config_format") == "dsh-patch":
        # 我们自己的独立补丁文件（从不碰 ~/.dsh/cordis.patch.yml）：整份重写，先备份。
        outcome = _commit_config(target, clients_extra.render_dsh_patch(payload).encode("utf-8"))
        return {"path": str(target), "format": "dsh-patch", "root_key": "insert", "servers": sorted(payload.get("insert") or {}),
                **outcome}
    # v0.41.0：新客户端的根键（OpenCode `mcp`、Amp 字面量 `amp.mcpServers`）由产物显式声明，不进通用猜测表——
    # OpenClaw 的产物也是 `{"mcp": {"servers": …}}`，把 `mcp` 放进猜测表会把它的 `servers` 当成一个 server 合并，覆盖用户已有的全部条目。
    declared = payload.get("root_key")
    root_key = declared if isinstance(declared, str) and isinstance(payload.get(declared), dict) else next(
        (key for key in _MERGEABLE_ROOT_KEYS if isinstance(payload.get(key), dict)), None
    )
    if root_key is None:
        raise typer.BadParameter(
            "这个格式的产物没有可合并的 server 块（mcpServers / servers / context_servers），"
            "拒绝把说明文字写成配置文件；请按 note 手动接入。"
        )
    servers = payload[root_key]
    written_format = "json"
    if target.exists():
        raw = target.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise typer.BadParameter(f"{target} 不是 UTF-8 文本（{exc}），拒绝合并——请手动把 {root_key} 片段粘进去。") from exc
        from horosa_skill import jsonc as _jsonc

        if _jsonc.is_jsonc_only(text) and payload.get("strict_json"):
            # v0.41.0：Deep Code 用 JSON.parse 读、失败就整份丢弃（连 API key 一起）——带注释的文件对它已经是坏的，
            # 保注释插入只会让它继续坏着；拒写并说清楚，比静默写进一份它根本不读的文件好。
            raise typer.BadParameter(
                f"{target} 含注释或尾逗号：这个客户端会把整份配置（含 API key）静默丢弃。先删掉注释 / 尾逗号让它成为严格 JSON，再重跑。"
            )
        if _jsonc.is_jsonc_only(text):
            # 🔴 v0.38.1 C4：Zed 出厂 settings.json / VS Code mcp.json 带注释与尾逗号，此前直接拒写。
            # 文本级插入：只动 <root_key>.<server> 这一段，注释与其它键逐字节保留；写完回读验证。
            existing = _jsonc.loads(text)
            if not isinstance(existing, dict):
                raise typer.BadParameter(f"{target} 顶层不是 JSON 对象，拒绝合并。")
            new_text = text
            for name, entry in servers.items():
                new_text = _jsonc.upsert_server_entry(new_text, root_key, name, entry)
            merged_check = _jsonc.loads(new_text)
            if not all(name in (merged_check.get(root_key) or {}) for name in servers):
                raise typer.BadParameter(f"{target} 含注释，文本级插入后回读不到 {root_key} 条目，拒绝写入。")
            output_text = new_text if new_text.endswith("\n") else new_text + "\n"
            if "\r\n" in text:
                # 🔴 v0.41.0 windows-smoke：保注释写入沿用原文件的换行；插入段是 LF，统一成 CRLF 后**按原字节**写（见下方 newline=""）。
                output_text = output_text.replace("\r\n", "\n").replace("\n", "\r\n")
            written_format = "jsonc"
        else:
            try:
                existing = json.loads(text) if raw.strip() else {}
            except json.JSONDecodeError as exc:
                raise typer.BadParameter(
                    f"{target} 不是合法 JSON（{exc}），拒绝合并——请手动把 {root_key} 片段粘进去。"
                ) from exc
            if not isinstance(existing, dict):
                raise typer.BadParameter(f"{target} 顶层不是 JSON 对象，拒绝合并。")
            current = existing.get(root_key)
            if isinstance(current, dict) and all(current.get(name) == entry for name, entry in servers.items()):
                # 条目已经一字不差：整份文件都不重写（不重排用户的缩进 / 键序，也不留一份没意义的备份）。
                return {"path": str(target), "format": written_format, "root_key": root_key, "servers": sorted(servers),
                        "changed": False, "backup": None}
            merged = dict(existing)
            block = dict(merged.get(root_key) or {})
            block.update(servers)
            merged[root_key] = block
            output_text = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
    else:
        output_text = json.dumps({root_key: dict(servers)}, ensure_ascii=False, indent=2) + "\n"
    # jsonc 分支已自带原文件的换行，不能再让 Windows 文本模式把 \n 翻成 \r\n（CRLF 文件会变 \r\r\n，每跑一次多一倍空行）；
    # 纯 JSON 分支照旧走平台换行（以前 write_text(newline=None) 的行为：Windows 上 \n → \r\n）。
    if written_format != "jsonc" and os.linesep != "\n":
        output_text = output_text.replace("\n", os.linesep)
    outcome = _commit_config(target, output_text.encode("utf-8"))
    return {"path": str(target), "format": written_format, "root_key": root_key, "servers": sorted(servers), **outcome}


def _write_yaml_merge(target: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """YAML 客户端（Goose `extensions:`）：只 upsert `<root_key>.<server>` 一段，其余字节原样；先备份、原子替换（v0.41.0）。"""
    from horosa_skill import yaml_block

    root_key = str(payload["root_key"])
    servers = payload[root_key]
    raw = target.read_bytes() if target.exists() else b""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise typer.BadParameter(f"{target} 不是 UTF-8 文本（{exc}），拒绝合并——请手动把 {root_key} 片段粘进去。") from exc
    try:
        for name, entry in servers.items():
            text = yaml_block.upsert_child(text, root_key, name, entry)
    except yaml_block.YamlShapeError as exc:
        raise typer.BadParameter(f"{target} 的 YAML 形状不认识（{exc}），拒绝合并——请手动把 {root_key} 片段粘进去。") from exc
    # yaml_block 已按原文件换行拼好：按字节写（文本模式会在 Windows 上二次翻译成 \r\r\n）
    outcome = _commit_config(target, text.encode("utf-8"))
    return {"path": str(target), "format": "yaml", "root_key": root_key, "servers": sorted(servers), **outcome}


def _codex_toml_merged(target: Path, toml_snippet: str) -> str:
    """把生成的 `[mcp_servers.<name>]` 片段合并进已有 config.toml，返回合并后的全文：只 upsert 该 server 表，
    其余内容（含注释）逐字保留（tomlkit）。目标不存在/为空则就是片段本身。目标不是合法 TOML 时拒绝合并（绝不静默覆盖用户文件）。
    落盘（留底、原子替换、保权限）统一走 `_commit_config`——MCP-12 之前这里是唯一一处 `write_text` 直写。"""
    import tomlkit

    snippet_doc = tomlkit.parse(toml_snippet)
    snippet_servers = snippet_doc.get("mcp_servers")
    if not snippet_servers:
        raise typer.BadParameter("codex 片段缺少 [mcp_servers.<name>] 表，拒绝写入。")
    raw_bytes = target.read_bytes() if target.exists() else b""
    if not raw_bytes.strip():
        return toml_snippet
    # 🔴 读取也在护栏内：Notepad / `Out-File` 存出来的 config.toml 可能是 UTF-16LE（BOM ff fe）
    # 或 UTF-8-with-BOM。此前 read_text(utf-8) 在 try 之外，UTF-16 直接以 UnicodeDecodeError
    # 的 traceback 逃出 `setup --client codex`。
    try:
        if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
            raw = raw_bytes.decode("utf-16")
        else:
            raw = raw_bytes.decode("utf-8-sig")
        existing = tomlkit.parse(raw)
    except Exception as exc:  # noqa: BLE001 - 解码或解析失败 = 用户文件形状未知，绝不覆盖（UnicodeDecodeError 本就是 Exception）
        raise typer.BadParameter(
            f"{target} 不是合法 TOML 或编码无法识别（{exc}），拒绝合并——请手动把生成片段粘进去。"
        ) from exc
    servers_table = existing.get("mcp_servers")
    if servers_table is None:
        existing["mcp_servers"] = snippet_servers
    else:
        for name, table in snippet_servers.items():
            servers_table[name] = table
    return tomlkit.dumps(existing)


def _write_codex_toml_merge(target: Path, toml_snippet: str) -> Path:
    """合并并落盘（与 `_merge_client_config` 的 Codex 分支同一条路：留底、原子替换、保权限）。保留给直接调用它的旧代码与测试。"""
    _commit_config(target, _codex_toml_merged(target, toml_snippet).encode("utf-8"))
    return target
