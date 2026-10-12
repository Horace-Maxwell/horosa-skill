"""官方 MCP Registry 上架（v0.41.0）：MCPB-only 条目 + 发布后自动登记。

**为什么旧检查抓不到**：`verify_server_json.py` 与注册表的 `/v0/validate`（`mcp-publisher validate`）对旧的 pypi+mcpb 文件
都说 valid——而真发布会被拒两次：命名空间小写（OIDC 授予 `io.github.Horace-Maxwell/*`，前缀比较区分大小写，issue #689）、
pypi 包不存在。两条都只在 publish 时才执行，没人发过所以没人见过。另：mcpb 的 sha 在 tag 之后才回填，tag 处的 server.json
带的是旧 sha——注册表版本不可变，发错一次就永远错。本文件锁：守卫抓得住这几条（负向对照）；渲染只信发布页的 SHA256SUMS；
工作流在 publish 之后、幂等、钉版本的 publisher。
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, PKG_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load("verify_server_json")
render_mod = _load("render_registry_server_json")
SERVER = json.loads((REPO_ROOT / "server.json").read_text(encoding="utf-8"))
SHA = "ab" * 32


def test_checked_in_server_json_passes_the_publish_time_rules() -> None:
    pyproject = (PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert guard.server_json_problems(SERVER, pyproject_text=pyproject) == []
    assert SERVER["name"] == "io.github.Horace-Maxwell/horosa-skill"
    assert [p["registryType"] for p in SERVER["packages"]] == ["mcpb"]


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda d: d.update(name="io.github.horace-maxwell/horosa-skill"), "case-sensitive"),
        (lambda d: d["packages"].append({"registryType": "pypi", "identifier": "horosa-skill", "transport": {"type": "stdio"}}), "PyPI is not published"),
        (lambda d: d["_meta"]["io.modelcontextprotocol.registry/publisher-provided"].update(blob="x" * 5000), "exceeds 4KB"),
        (lambda d: d["packages"][0].update(identifier="https://github.com/Horace-Maxwell/horosa-skill/releases/latest/download/horosa-skill.mcpb"), "tag-pinned"),
        (lambda d: d["packages"][0].update(fileSha256="ABC"), "64-char"),
        (lambda d: d.update(description="x" * 101), "≤100"),
    ],
)
def test_guard_catches_each_publish_time_rejection(mutate, needle: str) -> None:
    payload = copy.deepcopy(SERVER)
    mutate(payload)
    problems = guard.server_json_problems(payload)
    assert any(needle in p for p in problems), problems


def _sums(version: str, sha: str = SHA) -> str:
    return f"{'cd' * 32}  horosa-runtime-darwin-arm64-v{version}.tar.gz\n{sha}  horosa-skill-{version}.mcpb\n"


def test_render_takes_the_digest_from_the_release_not_from_main() -> None:
    older = copy.deepcopy(SERVER)  # main still describes the previous release
    payload, problems = render_mod.render(older, tag="v9.9.9", sums_text=_sums("9.9.9"))
    assert problems == []
    package = payload["packages"][0]
    assert payload["version"] == "9.9.9"
    assert package["identifier"] == "https://github.com/Horace-Maxwell/horosa-skill/releases/download/v9.9.9/horosa-skill-9.9.9.mcpb"
    assert package["fileSha256"] == SHA
    assert "/v9.9.9/" in json.dumps(payload["_meta"]), "publisher-provided 里的 wheel 命令也要指向同一个 tag"
    assert SERVER["packages"][0]["fileSha256"] != SHA, "渲染不许改动传入的 checked-in 对象"


def test_render_refuses_a_missing_sums_line_and_a_drifted_backfill() -> None:
    _payload, missing = render_mod.render(SERVER, tag="v9.9.9", sums_text="")
    assert any("no line for horosa-skill-9.9.9.mcpb" in p for p in missing)
    same_version = SERVER["version"]
    _payload, drifted = render_mod.render(SERVER, tag=f"v{same_version}", sums_text=_sums(same_version, sha="ef" * 32))
    assert any("checked-in fileSha256" in p for p in drifted), "main 的回填 ≠ 发布资产：先修 main，别把错 sha 写进不可变的注册表"
    _payload, bad_tag = render_mod.render(SERVER, tag="0.40.2", sums_text=_sums("0.40.2"))
    assert bad_tag and "vX.Y.Z" in bad_tag[0]


def test_sums_parser_accepts_binary_mode_marker_and_ignores_other_files() -> None:
    assert render_mod.sums_digest(f"{SHA} *horosa-skill-1.0.0.mcpb\n", "horosa-skill-1.0.0.mcpb") == SHA
    assert render_mod.sums_digest(f"{SHA}  horosa-skill-1.0.0.mcpb.sig\n", "horosa-skill-1.0.0.mcpb") is None


def test_render_moves_the_wheel_commands_to_the_listed_tag() -> None:
    payload, problems = render_mod.render(SERVER, tag="v0.0.9", sums_text=_sums("0.0.9"))
    assert problems == []
    meta = payload["_meta"]["io.modelcontextprotocol.registry/publisher-provided"]
    assert all("/v0.0.9/horosa_skill-0.0.9-py3" in line for line in meta["install"] + meta["start"])


def test_registry_workflow_runs_after_publish_idempotently_with_a_pinned_publisher() -> None:
    """文本级（venv 里没有 PyYAML）：发布后才登记、已登记跳过、OIDC、publisher 钉版本 + sha。"""
    import re

    release = (REPO_ROOT / ".github" / "workflows" / "release-runtime.yml").read_text(encoding="utf-8")
    job = release[release.index("\n  mcp-registry:"):]
    assert re.search(r"needs: \[resolve, publish\]", job) and "needs.publish.result == 'success'" in job
    assert "uses: ./.github/workflows/publish-mcp-registry.yml" in job and "id-token: write" in job

    text = (REPO_ROOT / ".github" / "workflows" / "publish-mcp-registry.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text and "workflow_call:" in text and "id-token: write" in text
    steps = text[text.index("    steps:"):]  # 头部注释也提到这些词；只看步骤区
    render_at = steps.index("render_registry_server_json.py")
    probe_at = steps.index('listed=$(')
    login_at = steps.index("login github-oidc")
    publish_at = steps.index('mcp-publisher" publish')
    assert render_at < probe_at < login_at < publish_at, "渲染 → 已登记则跳过 → 登录 → 发布，顺序不能乱"
    assert text.count("if: steps.probe.outputs.listed != 'true'") == 2, "安装与发布两步都要被「已登记」短路"
    assert re.search(r'MCP_PUBLISHER_VERSION: "\d+\.\d+\.\d+"', text)
    assert re.search(r'MCP_PUBLISHER_SHA256: "[a-f0-9]{64}"', text) and "sha256sum -c" in text
    assert "releases/latest/download/mcp-publisher" not in text, "publisher 必须钉版本 + 校验 sha"
