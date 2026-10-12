"""server.json guard — strict conformance to the official MCP Registry server schema.

Pinned schema: https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json
(top-level allowed keys, reverse-DNS name, packages[].transport object). Structural checks are
implemented by hand so CI needs no extra dependency; if the registry schema revs, update
_PINNED_SCHEMA + the allowed-key set together.

v0.41.0 adds the rules the registry only enforces at PUBLISH time — its `/v0/validate` endpoint (and
`mcp-publisher validate`) answered `valid:true` for our old pypi+mcpb file that a real publish would reject:
- the namespace must spell the GitHub owner exactly as GitHub does (`io.github.Horace-Maxwell/…`): the OIDC grant
  is `io.github.<repository_owner>/*` and the permission check is a case-sensitive prefix match (registry issue #689);
- no `pypi` package while PyPI is not published (the registry requires the package to exist and carry an
  `mcp-name:` marker in its README);
- `_meta…/publisher-provided` ≤ 4096 bytes; mcpb identifiers are tag-pinned GitHub release URLs.
The facts and their sources: contracts/third_party_facts.json `mcp-registry.publish`.
"""

from __future__ import annotations

import json
import re
import sys

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER_JSON = ROOT / "server.json"
PYPROJECT = ROOT / "horosa-skill" / "pyproject.toml"

_PINNED_SCHEMA = "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
_ALLOWED_TOP_LEVEL = {
    "$schema", "_meta", "description", "icons", "name", "packages",
    "remotes", "repository", "title", "version", "websiteUrl",
}
_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$")
_PUBLISHER_META = "io.modelcontextprotocol.registry/publisher-provided"
_PUBLISHER_META_MAX_BYTES = 4096
_GITHUB_REPO = re.compile(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)/?$")


def _publisher_meta_bytes(meta: object) -> int:
    """Upper bound of the registry's own size measure (Go json.Marshal): ASCII-escaped compact JSON is never shorter."""
    return len(json.dumps(meta, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))


def server_json_problems(payload: dict, *, pyproject_text: str | None = None) -> list[str]:
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

    repo_match = _GITHUB_REPO.match(str((payload.get("repository") or {}).get("url") or ""))
    owner = repo_match.group("owner") if repo_match else None
    repo = repo_match.group("repo") if repo_match else None
    if owner is None:
        errors.append("repository.url must be https://github.com/<owner>/<repo>")
    elif name.lower().startswith("io.github.") and not name.startswith(f"io.github.{owner}/"):
        # 🔴 v0.41.0：注册表按 GitHub 原样的 owner 大小写授予 `io.github.<owner>/*`，前缀比较区分大小写——
        # 小写的 `io.github.horace-maxwell/…` 发布时 403（issue #689）。
        errors.append(
            f"name namespace must spell the GitHub owner exactly as GitHub does: expected `io.github.{owner}/…`, got {name!r} "
            "(the registry's OIDC grant is case-sensitive)"
        )

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
        stray = set(meta) - {_PUBLISHER_META}
        if stray:
            errors.append(f"_meta keys must be registry-defined namespaces {[_PUBLISHER_META]}; got {sorted(stray)}")
        size = _publisher_meta_bytes(meta.get(_PUBLISHER_META) or {})
        if size > _PUBLISHER_META_MAX_BYTES:
            errors.append(f"_meta[{_PUBLISHER_META}] is {size} bytes > {_PUBLISHER_META_MAX_BYTES} (publish fails: exceeds 4KB limit)")

    packages = payload.get("packages")
    if not isinstance(packages, list) or not packages:
        errors.append("packages must contain at least one package definition")
    version = str(payload.get("version") or "")
    # 🔴 逐个查，不是只查 packages[0]。加第二个 package（mcpb）时，只查首个的旧实现对它
    # 一无所知 —— 一个 identifier 指向不存在的 release 资产、fileSha256 为空的条目会一路绿灯
    # 进注册表，客户端安装时才 404。
    for index, package in enumerate(packages or []):
        for field in ("registryType", "identifier"):
            if field not in package:
                errors.append(f"packages[{index}] missing field: {field}")
        transport = package.get("transport")
        if not isinstance(transport, dict) or "type" not in transport:
            errors.append(f"packages[{index}] transport must be an object with a 'type' (schema 2025-12-11 shape)")
        registry_type = package.get("registryType")
        if registry_type not in {"npm", "pypi", "nuget", "cargo", "oci", "mcpb"}:
            errors.append(f"registryType must be a real distribution channel, got {registry_type!r}")
        if registry_type == "pypi":
            # v0.41.0：PyPI 通道未开通（维护者暂缓）。注册表发布时要求包真实存在且 README 带 `mcp-name:` 标记，
            # 留着这一条 = 整条记录发不出去（/v0/validate 却说 valid）。开通 PyPI 时连同 pyproject 锁步一起恢复。
            errors.append(
                "packages[%d] is a pypi package but PyPI is not published — the registry rejects it at publish time; "
                "list the mcpb bundle only" % index
            )
        if registry_type == "mcpb":
            digest = str(package.get("fileSha256") or "")
            if not re.fullmatch(r"[a-f0-9]{64}", digest):
                errors.append(f"packages[{index}] fileSha256 must be a 64-char lowercase sha256 (clients verify it before install), got {digest[:16]!r}")
            identifier = str(package.get("identifier") or "")
            if "mcp" not in identifier.lower():
                errors.append("mcpb identifier URL must contain 'mcp' (registry ownership rule)")
            pkg_version = str(package.get("version") or version)
            if owner and repo:
                expected = re.compile(
                    rf"^https://github\.com/{re.escape(owner)}/{re.escape(repo)}/releases/download/v{re.escape(pkg_version)}/[^/]+\.mcpb$"
                )
                if not expected.match(identifier):
                    # 资产 URL 必须指向**当前**版本的 tag（`releases/latest/download/…` 注册表直接拒），否则升级后客户端装到的还是旧包。
                    errors.append(f"mcpb identifier must be this repo's tag-pinned release asset for v{pkg_version}: {identifier}")
            if package.get("version") and package["version"] != version:
                errors.append(f"packages[{index}].version {package['version']!r} != server version {version!r}")
    if pyproject_text is not None:
        version_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject_text, re.M)
        if version_match and version != version_match.group(1):
            errors.append(f"server.json version {version!r} != pyproject version {version_match.group(1)!r}")

    raw = json.dumps(payload, ensure_ascii=False)
    if "TBD" in raw:
        errors.append("server.json must not carry TBD placeholders (a published registry entry is read by clients as-is)")
    return errors


def main() -> None:
    payload = json.loads(SERVER_JSON.read_text(encoding="utf-8"))
    errors = server_json_problems(payload, pyproject_text=PYPROJECT.read_text(encoding="utf-8"))
    if errors:
        raise SystemExit("server.json: FAIL\n- " + "\n- ".join(errors))
    print("server.json: ok (registry-schema conformant; publish-time rules: owner casing, mcpb-only, publisher meta ≤ 4 KB)")


if __name__ == "__main__":
    main()
