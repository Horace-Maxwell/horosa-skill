"""把 horosa 条目合并写进客户端配置文件：JSON / JSONC（保注释）/ Codex TOML / Goose YAML，只动自己那一段。"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import typer

from horosa_skill import clients_extra


def _write_json_file(path: Path, payload: object) -> Path:
    output_path = path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


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
        written = _write_codex_toml_merge(target, payload["toml_stdio"])
        backup = target.with_name(f"{target.name}.horosa-bak")
        return {"path": str(written), "format": "toml", "root_key": "mcp_servers",
                "backup": str(backup) if backup.exists() else None}
    if not isinstance(payload, dict):
        raise typer.BadParameter("这份产物不是对象，无法合并进客户端配置。")
    if payload.get("config_format") == "yaml":
        return _write_yaml_merge(target, payload)
    if payload.get("config_format") == "dsh-patch":
        # 我们自己的独立补丁文件（从不碰 ~/.dsh/cordis.patch.yml）：整份重写，先备份。
        backup = None
        if target.exists():
            backup = target.with_name(f"{target.name}.horosa-bak")
            backup.write_bytes(target.read_bytes())
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f"{target.name}.horosa-tmp")
        tmp.write_text(clients_extra.render_dsh_patch(payload), encoding="utf-8")
        os.replace(tmp, target)
        return {"path": str(target), "format": "dsh-patch", "root_key": "insert", "servers": sorted(payload.get("insert") or {}),
                "backup": str(backup) if backup else None}
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
    backup: Path | None = None
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
            backup = target.with_name(f"{target.name}.horosa-bak")
            backup.write_bytes(raw)
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
            backup = target.with_name(f"{target.name}.horosa-bak")
            backup.write_bytes(raw)
            merged = dict(existing)
            block = dict(merged.get(root_key) or {})
            block.update(servers)
            merged[root_key] = block
            output_text = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
    else:
        output_text = json.dumps({root_key: dict(servers)}, ensure_ascii=False, indent=2) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.horosa-tmp")
    # jsonc 分支已自带原文件的换行，不能再让 Windows 文本模式把 \n 翻成 \r\n（CRLF 文件会变 \r\r\n，每跑一次多一倍空行）；
    # 纯 JSON 分支照旧走平台换行。
    tmp.write_text(output_text, encoding="utf-8", newline="" if written_format == "jsonc" else None)
    try:
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()
    return {"path": str(target), "format": written_format, "root_key": root_key,
            "servers": sorted(servers), "backup": str(backup) if backup else None}


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
    backup: Path | None = None
    if raw:
        backup = target.with_name(f"{target.name}.horosa-bak")
        backup.write_bytes(raw)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.horosa-tmp")
    tmp.write_bytes(text.encode("utf-8"))  # yaml_block 已按原文件换行拼好；文本模式写会在 Windows 上二次翻译成 \r\r\n
    try:
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()
    return {"path": str(target), "format": "yaml", "root_key": root_key, "servers": sorted(servers),
            "backup": str(backup) if backup else None}


def _write_codex_toml_merge(target: Path, toml_snippet: str) -> Path:
    """把生成的 `[mcp_servers.<name>]` 片段合并进已有 config.toml：只 upsert 该 server 表，
    其余内容（含注释）逐字保留（tomlkit）；覆盖前先备份 `<file>.horosa-bak`。目标不存在/为空
    则整文件写入片段。目标不是合法 TOML 时拒绝合并（绝不静默覆盖用户文件）。"""
    import tomlkit

    snippet_doc = tomlkit.parse(toml_snippet)
    snippet_servers = snippet_doc.get("mcp_servers")
    if not snippet_servers:
        raise typer.BadParameter("codex 片段缺少 [mcp_servers.<name>] 表，拒绝写入。")
    raw_bytes = target.read_bytes() if target.exists() else b""
    if raw_bytes.strip():
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
        backup = target.with_name(f"{target.name}.horosa-bak")
        backup.write_text(raw, encoding="utf-8")
        servers_table = existing.get("mcp_servers")
        if servers_table is None:
            existing["mcp_servers"] = snippet_servers
        else:
            for name, table in snippet_servers.items():
                servers_table[name] = table
        target.write_text(tomlkit.dumps(existing), encoding="utf-8")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(toml_snippet, encoding="utf-8")
    return target
