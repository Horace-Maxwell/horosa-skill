"""`setup --vectors`：把可选向量检索真正送进 MCP server 的环境。

**为什么旧路径到不了**：`[vectors]` 依赖要装在**客户端起 server 的那个环境**里（uvx 的工具环境 / `uv run` 的 venv），
不是跑 `setup` 的这个进程；此前文档只说「装 `[vectors]`」，配置里的启动器不带 extra，server 永远是纯 BM25，还不报错。

本文件锁：四种启动器的写法（不带 --vectors 时一个字不变）；依赖 / 模型在**写配置之前**验证，失败时配置不动；
stdio 探针要 server 自己报 ready；重跑 setup 不带参数不掉开关；`client check` 看得穿新写法。
"""

from __future__ import annotations

import json
import stat
import sys
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from horosa_skill import __version__
from horosa_skill.client_config import audit as client_audit
from horosa_skill.client_config import payload as client_payload
from horosa_skill.config import Settings
from horosa_skill.knowledge import vectors
from horosa_skill.surfaces import setup_flow
from horosa_skill.surfaces.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOROSA_RUNTIME_PLATFORM", "darwin-arm64")
    monkeypatch.setenv("HOROSA_LOCAL_BACKEND_PORT", "39997")
    monkeypatch.setenv("HOROSA_LOCAL_CHART_PORT", "39898")
    for name in ("HOROSA_SERVER_ROOT", "HOROSA_CHART_SERVER_ROOT", "HOROSA_RUNTIME_MIRROR", "HOROSA_PORTS",
                 "HOROSA_RUNTIME_MANIFEST_URL", "HOROSA_MCP_COMPACT", "HOROSA_KNOWLEDGE_VECTORS", "HF_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("horosa_skill.skill_install.default_home", lambda: tmp_path / "home")


def _command(launcher: str, tmp_path: Path, *, vectors_on: bool, wheel: str | None = None, entry: str = "script") -> list[str]:
    root = tmp_path / "pkg"
    root.mkdir(exist_ok=True)
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    _payload, command, _env = client_payload._build_client_config_payload(
        format_name="cursor", skill_root=root, server_name="horosa", launcher=launcher, surface="auto",
        wheel_source=wheel, entry=entry, vectors=vectors_on,
    )
    return command


# ---- 启动器写法


def test_uv_launcher_enables_the_extra_for_the_project_venv(tmp_path: Path) -> None:
    command = _command("uv", tmp_path, vectors_on=True)
    assert command[command.index("--extra") + 1] == "vectors"
    assert command.index("--extra") < command.index("horosa-skill"), "`--extra` 是 uv run 的选项，写到命令后面就成了 horosa-skill 的参数"


def test_uvx_wheel_with_a_cached_file_becomes_a_direct_reference(tmp_path: Path) -> None:
    wheel = tmp_path / "wheels" / f"horosa_skill-{__version__}-py3-none-any.whl"
    command = _command("uvx-wheel", tmp_path, vectors_on=True, wheel=str(wheel))
    assert command[command.index("--from") + 1] == f"horosa-skill[vectors]@{wheel.as_uri()}"


@pytest.mark.parametrize("launcher", ["uvx-wheel", "uvx-git"])
def test_remote_sources_keep_their_url(tmp_path: Path, launcher: str) -> None:
    plain = _command(launcher, tmp_path, vectors_on=False)
    wanted = plain[plain.index("--from") + 1]
    command = _command(launcher, tmp_path, vectors_on=True)
    assert command[command.index("--from") + 1] == f"horosa-skill[vectors]@{wanted}"


def test_pypi_launcher_names_the_extra(tmp_path: Path) -> None:
    command = _command("uvx", tmp_path, vectors_on=True)
    assert command[command.index("--from") + 1] == "horosa-skill[vectors]"


def test_a_home_with_spaces_cannot_split_the_spec(tmp_path: Path) -> None:
    """有的客户端按空格拆命令；file URI 百分号编码后整段没有空格。"""
    spec = client_payload.vectors_source(str(tmp_path / "John Doe" / "x.whl"))
    assert " " not in spec and "John%20Doe" in spec


def test_a_windows_wheel_path_is_a_valid_file_uri_on_any_host() -> None:
    spec = client_payload.vectors_source(r"C:\Users\John Doe\.horosa\wheels\x.whl")
    assert spec == "horosa-skill[vectors]@file:///C:/Users/John%20Doe/.horosa/wheels/x.whl"


@pytest.mark.parametrize("launcher", ["uvx-wheel", "uvx-git", "uvx"])
def test_uvx_launchers_pin_the_interpreter_for_the_extra(tmp_path: Path, launcher: str) -> None:
    """uv 不会为带 extra 的包按 requires-python 换解释器：PATH 里第一个是 3.11 的机器上 `[vectors]` 直接解析失败。"""
    command = _command(launcher, tmp_path, vectors_on=True)
    assert command[command.index("--python") + 1] == client_payload.VECTORS_PYTHON
    assert command.index("--python") < command.index("--from"), "--python 是 uvx 的选项，写到 --from 的包后面就成了别的东西"


def test_the_uv_launcher_and_plain_configs_stay_unpinned(tmp_path: Path) -> None:
    assert "--python" not in _command("uv", tmp_path, vectors_on=True)  # uv run 由项目的 requires-python 决定
    assert "--python" not in _command("uvx-wheel", tmp_path, vectors_on=False)


def test_module_entry_keeps_the_extra(tmp_path: Path) -> None:
    command = _command("uvx-wheel", tmp_path, vectors_on=True, entry="module")
    assert command[command.index("--from") + 1].startswith("horosa-skill[vectors]@")
    assert command[-6:] == ["python", "-m", "horosa_skill", "serve", "--transport", "stdio"]


@pytest.mark.parametrize("launcher", ["uv", "uvx-wheel", "uvx-git", "uvx"])
def test_without_the_flag_no_launcher_mentions_vectors(tmp_path: Path, launcher: str) -> None:
    assert not any("vectors" in part for part in _command(launcher, tmp_path, vectors_on=False))


def test_printed_commands_quote_the_brackets() -> None:
    """未加引号的 `horosa-skill[vectors]@…` 粘进 zsh 是 `no matches found`（2026-11-06 实测）。"""
    printed = client_payload._format_cli_command(["uvx", "--from", "horosa-skill[vectors]@file:///x.whl", "horosa-skill"])
    assert '"horosa-skill[vectors]@file:///x.whl"' in printed


def test_openclaw_formats_say_they_do_not_carry_the_extra(tmp_path: Path) -> None:
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    payload, _command_line, _env = client_payload._build_client_config_payload(
        format_name="openclaw", skill_root=root, server_name="horosa", launcher="uv", surface="auto", vectors=True,
    )
    assert any("vectors" in item for item in payload["warnings"])


# ---- client check 要看得穿新写法


def _problems(args: list[str]) -> set[str]:
    entry = {"command": "/opt/uv/bin/uvx", "args": args}
    return {p["code"] for p in client_audit._audit_client_entry("horosa", entry, client="cursor")}


def test_audit_still_sees_a_missing_local_wheel_behind_the_extra(tmp_path: Path) -> None:
    gone = tmp_path / f"horosa_skill-{__version__}-py3-none-any.whl"
    plain = ["--from", str(gone), "horosa-skill", "serve", "--transport", "stdio"]
    assert "wheel_cache_missing" in _problems(plain)  # 负向对照：旧写法本来就报
    spec = ["--from", f"horosa-skill[vectors]@{gone.as_uri()}", "horosa-skill", "serve", "--transport", "stdio"]
    assert "wheel_cache_missing" in _problems(spec)


def test_audit_still_sees_version_drift_behind_the_extra(tmp_path: Path) -> None:
    old = tmp_path / "horosa_skill-0.1.0-py3-none-any.whl"
    old.write_bytes(b"x")
    spec = ["--from", f"horosa-skill[vectors]@{old.as_uri()}", "horosa-skill", "serve", "--transport", "stdio"]
    assert "launcher_version_drift" in _problems(spec)


def test_audit_knows_the_named_extra_still_needs_pypi() -> None:
    assert "pypi_not_published" in _problems(["--from", "horosa-skill[vectors]", "horosa-skill", "serve", "--transport", "stdio"])


# ---- setup 流程


def _setup(*args: str):
    return runner.invoke(app, ["setup", "--client", "cursor", "--skip-install", "--no-skill", *args])


def _stderr_json(result) -> dict:
    assert result.exit_code == 2, f"exit={result.exit_code}\nstdout={result.stdout}\nstderr={result.stderr}"
    return json.loads(result.stderr[result.stderr.index("{\n"):])


def _ready_status() -> dict:
    return {"model": vectors.MODEL_NAME, "ready": True, "enabled_by_env": True, "deps_installed": True, "model_present": True}


def _good_prepare(calls: list | None = None):
    def fake(*, command, env, cwd, timeout):
        if calls is not None:
            calls.append({"command": command, "env": env, "cwd": cwd})
        return {"ok": True, "engine": "fts5-bm25+vectors", "sync": {"vectors": 3}, "vectors": _ready_status()}
    return fake


def _probe(status: dict | None):
    def fake(**_kwargs):
        return {"ok": True, "tools": 12, "server_name": "horosa", "server_version": __version__,
                "runtime_status": {"knowledge_vectors": status} if status else {}, "stderr_tail": ""}
    return fake


def _claim_tool_count(monkeypatch: pytest.MonkeyPatch) -> None:
    real = setup_flow._build_client_config_payload

    def wrapped(**kwargs):
        payload, command, env = real(**kwargs)
        payload["tool_surface"]["tools"] = 12
        return payload, command, env
    monkeypatch.setattr(setup_flow, "_build_client_config_payload", wrapped)


def test_dry_run_plans_without_touching_anything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup_flow, "_vectors_prepare", lambda **_: pytest.fail("dry-run 不许起进程"))
    config = tmp_path / "mcp.json"
    result = _setup("--config", str(config), "--dry-run", "--vectors", "--launcher", "uv", "--skill-root", str(Path.cwd()))
    report = json.loads(result.stdout)
    step = report["steps"]["vectors"]
    assert step["ok"] and step["skipped"] and step["requested"] is True
    assert step["would_run"].endswith("knowledge index --vectors")
    assert not config.exists()
    assert "--extra" in report["steps"]["config"]["server_block"]["horosa"]["args"]


def test_not_requested_is_a_skipped_step_and_runs_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup_flow, "_vectors_prepare", lambda **_: pytest.fail("没要向量就不该准备"))
    result = _setup("--config", str(tmp_path / "mcp.json"), "--no-stdio-probe", "--launcher", "uv", "--skill-root", str(Path.cwd()))
    report = json.loads(result.stdout)
    assert report["steps"]["vectors"]["skipped"] is True and report["steps"]["vectors"]["requested"] is False
    assert "--extra" not in report["steps"]["config"]["server_block"]["horosa"]["args"]


def test_a_failed_prepare_leaves_the_config_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """🔴 配置写上 `[vectors]` 而依赖装不上 = server 根本起不来（比如没有 onnxruntime 轮子的平台），比没有向量糟得多。"""
    monkeypatch.setattr(setup_flow, "_vectors_prepare", lambda **_: {
        "ok": False, "failure": "deps", "message": "依赖装不上", "stderr_tail": "no wheel for this platform", "returncode": 1})
    config = tmp_path / "mcp.json"
    config.write_text('{"mcpServers": {"other": {"command": "x"}}}', encoding="utf-8")
    before = config.read_bytes()
    failure = _stderr_json(_setup("--config", str(config), "--vectors", "--no-stdio-probe", "--launcher", "uv", "--skill-root", str(Path.cwd())))
    assert failure["step"] == "vectors" and failure["code"] == "setup.vectors_failed"
    assert failure["config_untouched"] is True and config.read_bytes() == before
    assert "--no-vectors" in failure["retry_command"]
    assert failure["steps"]["vectors"]["ok"] is False


def test_success_runs_the_client_command_then_writes_the_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    order: list[str] = []
    monkeypatch.setattr(setup_flow, "_vectors_prepare", lambda **kw: (order.append("prepare"), _good_prepare(calls)(**kw))[1])
    real_merge = setup_flow._merge_client_config
    monkeypatch.setattr(setup_flow, "_merge_client_config", lambda *a: (order.append("write"), real_merge(*a))[1])
    _claim_tool_count(monkeypatch)
    monkeypatch.setattr(setup_flow, "_stdio_probe", _probe(_ready_status()))
    config = tmp_path / "mcp.json"
    result = _setup("--config", str(config), "--vectors", "--launcher", "uv", "--skill-root", str(Path.cwd()))
    assert result.exit_code == 0, result.stderr
    report = json.loads(result.stdout)
    assert order == ["prepare", "write"]
    run = calls[0]["command"]
    assert run[-3:] == ["knowledge", "index", "--vectors"] and "serve" not in run and "--extra" in run
    assert report["steps"]["vectors"]["ok"] is True and report["steps"]["vectors"]["embedded"] == 3
    written = json.loads(config.read_text(encoding="utf-8"))["mcpServers"]["horosa"]["args"]
    assert written[written.index("--extra") + 1] == "vectors"
    assert any("向量" in item for item in report["next_steps"])


@pytest.mark.parametrize("status", [None, {"ready": False, "deps_installed": False, "model_present": True}])
def test_the_server_itself_must_say_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: dict | None) -> None:
    """准备步骤过了不算：客户端形状的环境里（比如 Codex 只给最小环境）server 自己报 ready 才算开着。"""
    monkeypatch.setattr(setup_flow, "_vectors_prepare", _good_prepare())
    _claim_tool_count(monkeypatch)
    monkeypatch.setattr(setup_flow, "_stdio_probe", _probe(status))
    failure = _stderr_json(_setup("--config", str(tmp_path / "mcp.json"), "--vectors", "--launcher", "uv", "--skill-root", str(Path.cwd())))
    assert failure["step"] == "stdio_probe" and failure["code"] == "setup.stdio_probe_vectors_not_ready"
    assert failure["config_untouched"] is False


def test_rerunning_setup_keeps_vectors_when_the_model_is_there(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """升级靠重跑 setup；不带参数就把开关丢了，搜索质量会悄悄变差，还没人发现。"""
    monkeypatch.setattr(vectors, "model_ready", lambda _settings: True)
    monkeypatch.setattr(setup_flow, "_vectors_prepare", _good_prepare())
    result = _setup("--config", str(tmp_path / "mcp.json"), "--no-stdio-probe", "--launcher", "uv", "--skill-root", str(Path.cwd()))
    report = json.loads(result.stdout)
    assert report["steps"]["vectors"]["requested"] is True
    assert "--extra" in report["steps"]["config"]["server_block"]["horosa"]["args"]


def test_no_vectors_wins_over_a_present_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vectors, "model_ready", lambda _settings: True)
    monkeypatch.setattr(setup_flow, "_vectors_prepare", lambda **_: pytest.fail("--no-vectors 不该准备"))
    result = _setup("--config", str(tmp_path / "mcp.json"), "--no-vectors", "--no-stdio-probe", "--launcher", "uv", "--skill-root", str(Path.cwd()))
    assert "--extra" not in json.loads(result.stdout)["steps"]["config"]["server_block"]["horosa"]["args"]


def test_switched_off_by_env_does_not_auto_keep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOROSA_KNOWLEDGE_VECTORS", "0")
    monkeypatch.setattr(vectors, "model_ready", lambda _settings: True)
    monkeypatch.setattr(setup_flow, "_vectors_prepare", lambda **_: pytest.fail("用户明确关了"))
    result = _setup("--config", str(tmp_path / "mcp.json"), "--no-stdio-probe", "--launcher", "uv", "--skill-root", str(Path.cwd()))
    assert json.loads(result.stdout)["steps"]["vectors"]["requested"] is False


def test_client_config_takes_the_flag_but_never_probes_the_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`client config` 是纯生成器：输出不随磁盘状态变。"""
    monkeypatch.setattr(vectors, "model_ready", lambda _settings: True)
    args = ["client", "config", "--format", "cursor", "--launcher", "uv", "--skill-root", str(Path.cwd())]
    plain = json.loads(runner.invoke(app, args).stdout)
    assert "--extra" not in plain["mcpServers"]["horosa"]["args"]
    wanted = json.loads(runner.invoke(app, [*args, "--vectors"]).stdout)
    assert "--extra" in wanted["mcpServers"]["horosa"]["args"]


# ---- `_vectors_prepare`：真起子进程（假的「客户端命令」）


def _script(tmp_path: Path, body: str) -> list[str]:
    path = tmp_path / "fake_cli.py"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return [sys.executable, str(path)]


def test_prepare_passes_a_ready_report_through(tmp_path: Path) -> None:
    command = _script(tmp_path, """
        import json
        print(json.dumps({"ok": True, "engine": "fts5-bm25+vectors", "sync": {"vectors": 2},
                          "vectors": {"ready": True, "enabled_by_env": True, "deps_installed": True, "model_present": True}}))
    """)
    outcome = setup_flow._vectors_prepare(command=command, env=None, cwd=None, timeout=30)
    assert outcome["ok"] is True and outcome["sync"]["vectors"] == 2


@pytest.mark.parametrize(("body", "failure"), [
    # uv 在 server 启动前就退出：没有 JSON，只有 stderr
    ("import sys; print('error: no wheel', file=sys.stderr); sys.exit(1)", "deps"),
    # 我们自己的两种拒绝：JSON 在 stdout，退出码 2
    ("import json, sys; print(json.dumps({'ok': False, 'code': 'knowledge.vectors_missing_deps', 'vectors': {}})); sys.exit(2)", "deps"),
    ("import json, sys; print(json.dumps({'ok': False, 'code': 'knowledge.vectors_download_failed', 'message': 'timeout', 'vectors': {}})); sys.exit(2)", "download"),
    # 退出码 0 却没就绪（比如客户端环境把开关设成了 0）
    ("import json; print(json.dumps({'ok': True, 'vectors': {'ready': False, 'enabled_by_env': False, 'deps_installed': True, 'model_present': True}}))", "disabled"),
    ("import json; print(json.dumps({'ok': True, 'vectors': {'ready': False, 'enabled_by_env': True, 'deps_installed': False, 'model_present': True}}))", "deps"),
    ("print('not json')", "unreadable"),
])
def test_prepare_names_what_went_wrong(tmp_path: Path, body: str, failure: str) -> None:
    outcome = setup_flow._vectors_prepare(command=_script(tmp_path, body), env=None, cwd=None, timeout=30)
    assert outcome["ok"] is False and outcome["failure"] == failure, outcome
    assert outcome["message"]


def test_prepare_survives_a_timeout(tmp_path: Path) -> None:
    command = _script(tmp_path, "import time; time.sleep(30)")
    outcome = setup_flow._vectors_prepare(command=command, env=None, cwd=None, timeout=0.5)
    assert outcome["ok"] is False and outcome["failure"] == "timeout"


def test_prepare_survives_a_missing_program(tmp_path: Path) -> None:
    outcome = setup_flow._vectors_prepare(command=[str(tmp_path / "nope")], env=None, cwd=None, timeout=5)
    assert outcome["ok"] is False and outcome["failure"] == "deps"


# ---- 模型下载 / 状态


def _settings(tmp_path: Path) -> Settings:
    return Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt",
                    db_path=tmp_path / "data" / "m.db", output_dir=tmp_path / "data" / "runs", data_dir=tmp_path / "data")


class _Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self, _size: int):
        yield self.body


def _serve(monkeypatch: pytest.MonkeyPatch, handler) -> list[str]:
    import hashlib

    import httpx

    seen: list[str] = []
    files = {}
    for name in vectors.MODEL_FILES:
        files[name] = name.encode()
    monkeypatch.setattr(vectors, "MODEL_FILES", {name: hashlib.sha256(body).hexdigest() for name, body in files.items()})

    def fake(_method, url, **_kwargs):
        seen.append(url)
        name = next(n for n in files if url.endswith(n))
        return handler(url, name, files[name])
    monkeypatch.setattr(httpx, "stream", fake)
    return seen


def test_hf_endpoint_is_tried_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_ENDPOINT", "https://hf-mirror.example/")
    seen = _serve(monkeypatch, lambda _url, _name, body: _Response(body))
    vectors.download(_settings(tmp_path))
    assert all(url.startswith(f"https://hf-mirror.example/{vectors.MODEL_REPO}/resolve/{vectors.MODEL_COMMIT}/") for url in seen)
    assert len(seen) == 2


def test_a_lying_mirror_cannot_land_a_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """镜像是 sha256 钉住的：内容不对的不落盘，退回官方地址。"""
    monkeypatch.setenv("HF_ENDPOINT", "https://hf-mirror.example")

    def handler(url, _name, body):
        return _Response(b"tampered" if "hf-mirror" in url else body)
    seen = _serve(monkeypatch, handler)
    result = vectors.download(_settings(tmp_path))
    assert len(result["downloaded"]) == 2
    assert any("hf-mirror" in url for url in seen), "镜像根本没试过的话，这条测不到任何东西"
    assert any(url.startswith("https://huggingface.co/") for url in seen)
    assert vectors.model_ready(_settings(tmp_path)) is True


def test_when_every_source_fails_the_error_names_them(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_ENDPOINT", "https://hf-mirror.example")

    def handler(url, _name, _body):
        raise OSError(f"unreachable {url.split('/')[2]}")
    _serve(monkeypatch, handler)
    with pytest.raises(OSError) as caught:
        vectors.download(_settings(tmp_path))
    assert "hf-mirror.example" in str(caught.value) and "huggingface.co" in str(caught.value)
    assert not list((tmp_path / "data").rglob("*.part")), "失败不留临时文件"


def test_status_says_ready_and_points_at_setup(tmp_path: Path) -> None:
    status = vectors.status(_settings(tmp_path))
    assert status["ready"] is False
    assert "setup --client" in status["how_to_enable"] and "--vectors" in status["how_to_enable"]
    assert "pip install" not in status["how_to_enable"], "PyPI 未开通，pip install horosa-skill 是 404"


def test_a_broken_native_library_counts_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows 上 onnxruntime 的 DLL 载不进来可能抛 OSError；不能把 server 带崩，要退回 BM25。"""
    import builtins

    real = builtins.__import__

    def fake(name, *args, **kwargs):
        if name == "onnxruntime":
            raise OSError("DLL load failed")
        return real(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", fake)
    assert vectors.deps_available() is False


def test_runtime_status_resource_reports_vectors(tmp_path: Path) -> None:
    import asyncio

    from pydantic import AnyUrl

    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings = _settings(tmp_path)
    server = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
    contents = asyncio.run(server.read_resource(AnyUrl("horosa://runtime/status")))
    status = json.loads(next(iter(contents)).content)["knowledge_vectors"]
    assert status["ready"] is False and status["model"] == vectors.MODEL_NAME


def test_doctor_reports_vectors(tmp_path: Path) -> None:
    report = json.loads(runner.invoke(app, ["doctor"]).stdout)
    assert report["knowledge_vectors"]["ready"] is False
    assert report["knowledge_vectors"]["scope"]
