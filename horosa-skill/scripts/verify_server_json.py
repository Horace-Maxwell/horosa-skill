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

    packages = payload.get("packages")
    if not isinstance(packages, list) or not packages:
        errors.append("packages must contain at least one package definition")
    else:
        package = packages[0]
        for field in ("registryType", "identifier", "version"):
            if field not in package:
                errors.append(f"first package missing field: {field}")
        transport = package.get("transport")
        if not isinstance(transport, dict) or "type" not in transport:
            errors.append("first package transport must be an object with a 'type' (schema 2025-12-11 shape)")
        # Registry 认可的分发通道；`github` 不是其中之一（repository.source 只是元数据，不是通道）。
        # 我们走 `mcpb`：GitHub Release 上的 .mcpb + fileSha256，客户端安装前自校验 —— 这条路不需要
        # 发 PyPI，正好绕开 horosa-core-js 在 wheel 之外的分发归属问题。
        registry_type = package.get("registryType")
        if registry_type not in {"npm", "pypi", "nuget", "cargo", "oci", "mcpb"}:
            errors.append(f"registryType must be a real distribution channel, got {registry_type!r}")
        if registry_type == "mcpb":
            digest = str(package.get("fileSha256") or "")
            if not digest:
                errors.append("mcpb packages must carry fileSha256 (clients verify it before install)")
            elif digest != "TBD-set-by-release-pipeline" and len(digest) != 64:
                errors.append(f"fileSha256 must be a 64-char sha256 digest, got {len(digest)} chars")
            if "mcp" not in str(package.get("identifier") or "").lower():
                errors.append("mcpb identifier URL must contain 'mcp' (registry ownership rule)")

    if errors:
        raise SystemExit("server.json: FAIL\n- " + "\n- ".join(errors))
    print("server.json: ok (registry-schema conformant)")


if __name__ == "__main__":
    main()
