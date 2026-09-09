"""server.json guard — strict conformance to the official MCP Registry server schema.

Pinned schema: https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json
(top-level allowed keys, reverse-DNS name, packages[].transport object). Structural checks are
implemented by hand so CI needs no extra dependency; if the registry schema revs, update
_PINNED_SCHEMA + the allowed-key set together.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER_JSON = ROOT / "server.json"

_PINNED_SCHEMA = "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
_ALLOWED_TOP_LEVEL = {
    "$schema", "_meta", "description", "icons", "name", "packages",
    "remotes", "repository", "title", "version", "websiteUrl",
}
_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$")


def main() -> None:
    payload = json.loads(SERVER_JSON.read_text(encoding="utf-8"))
    errors: list[str] = []

    extra = set(payload) - _ALLOWED_TOP_LEVEL
    if extra:
        errors.append(f"top-level keys not in registry schema: {sorted(extra)}")
    for key in ("name", "description", "version"):
        if key not in payload:
            errors.append(f"missing required field: {key}")

    name = payload.get("name", "")
    if not _NAME_PATTERN.match(name) or name.count("/") != 1:
        errors.append(f"name must be reverse-DNS namespace/name (exactly one '/'): got {name!r}")
    elif "." not in name.split("/", 1)[0]:
        errors.append(f"name namespace should be reverse-DNS (e.g. io.github.<owner>): got {name!r}")

    if payload.get("$schema") != _PINNED_SCHEMA:
        errors.append(f"$schema must be pinned to {_PINNED_SCHEMA}")

    # 注册表把 description 当卡片标题用，上限 100 字符 —— 超了整条记录被拒（我们曾是 158）。
    description = str(payload.get("description") or "")
    if len(description) > 100:
        errors.append(f"description must be ≤100 chars (registry limit), got {len(description)}")

    # 私有元数据必须住在注册表规定的命名空间下。自造 key（我们曾用 `io.github.<owner>/<name>`）
    # 会被 publish 拒收，而本地校验此前完全看不见这一条。
    meta = payload.get("_meta")
    if isinstance(meta, dict):
        allowed_meta = {"io.modelcontextprotocol.registry/publisher-provided"}
        stray = set(meta) - allowed_meta
        if stray:
            errors.append(
                f"_meta keys must be registry-defined namespaces {sorted(allowed_meta)}; got {sorted(stray)}"
            )

    packages = payload.get("packages")
    if not isinstance(packages, list) or not packages:
        errors.append("packages must contain at least one package definition")
    # 🔴 逐个查，不是只查 packages[0]。加第二个 package（mcpb）时，只查首个的旧实现对它
    # 一无所知 —— 一个 identifier 指向不存在的 release 资产、fileSha256 为空的条目会一路绿灯
    # 进注册表，客户端安装时才 404。
    for index, package in enumerate(packages or []):
        for field in ("registryType", "identifier", "version"):
            if field not in package:
                errors.append(f"packages[{index}] missing field: {field}")
        transport = package.get("transport")
        if not isinstance(transport, dict) or "type" not in transport:
            errors.append(f"packages[{index}] transport must be an object with a 'type' (schema 2025-12-11 shape)")
        # Registry 认可的分发通道；`github` 不是其中之一（repository.source 只是元数据，不是通道）。
        # 我们走 `mcpb`：GitHub Release 上的 .mcpb + fileSha256，客户端安装前自校验 —— 这条路不需要
        # 发 PyPI，正好绕开 horosa-core-js 在 wheel 之外的分发归属问题。
        registry_type = package.get("registryType")
        if registry_type not in {"npm", "pypi", "nuget", "cargo", "oci", "mcpb"}:
            errors.append(f"registryType must be a real distribution channel, got {registry_type!r}")
        if registry_type == "pypi":
            # v0.36.0 C4：PyPI 是主分发通道（uvx horosa-skill …）；identifier/version 与 pyproject 锁步。
            pyproject = (ROOT / "horosa-skill" / "pyproject.toml").read_text(encoding="utf-8")
            name_match = re.search(r'^name\s*=\s*"([^"]+)"', pyproject, re.M)
            version_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
            if not name_match or package.get("identifier") != name_match.group(1):
                errors.append(f"pypi identifier must equal pyproject name ({name_match.group(1) if name_match else '?'}), got {package.get('identifier')!r}")
            if not version_match or package.get("version") != version_match.group(1):
                errors.append(f"pypi package version must equal pyproject version ({version_match.group(1) if version_match else '?'}), got {package.get('version')!r}")
            if package.get("runtimeHint") != "uvx":
                errors.append("pypi package runtimeHint must be 'uvx' (the documented launcher)")
        if registry_type == "mcpb":
            digest = str(package.get("fileSha256") or "")
            blocked = "publish_blocked_until" in json.dumps(payload.get("_meta") or {}, ensure_ascii=False)
            if not digest:
                if not blocked:
                    errors.append("mcpb packages must carry fileSha256 (clients verify it before install)")
            elif len(digest) != 64:
                errors.append(f"fileSha256 must be a 64-char sha256 digest, got {len(digest)} chars")
            identifier = str(package.get("identifier") or "")
            if "mcp" not in identifier.lower():
                errors.append("mcpb identifier URL must contain 'mcp' (registry ownership rule)")
            # 资产 URL 必须指向**当前**版本的 tag，否则升级后客户端装到的还是旧包。
            if package.get("version") and f"/v{package['version']}/" not in identifier:
                errors.append(
                    f"mcpb identifier must point at the current release tag v{package['version']}: {identifier}"
                )

    raw = SERVER_JSON.read_text(encoding="utf-8")
    if "TBD" in raw:
        errors.append("server.json must not carry TBD placeholders (a published registry entry is read by clients as-is)")
    if errors:
        raise SystemExit("server.json: FAIL\n- " + "\n- ".join(errors))
    print("server.json: ok (registry-schema conformant)")


if __name__ == "__main__":
    main()
