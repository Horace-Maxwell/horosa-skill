"""`horosa-skill install --engine-only` and the automatic engine-only install (v0.50.0-dev, E-02).

Before: a wheel / pip / Docker / gateway install on Linux or an Intel Mac had no JS engine at all — `install` died with
`runtime.install_missing_platform` and every local JS technique (BaZi / Ziwei / Qimen / Liuren / Heluo / Canping …) failed with
`js_engine.cli_missing`. Now the release carries a platform-independent `horosa-core-js` asset; these tests install it the way
users get it (a manifest + an HTTP download through the mirror logic, served from 127.0.0.1), and pin the refusals (tampered
digest, missing asset, wrong archive), the placement (`<runtime root>/core-js/`, never `current/`), the resolution order, the
Node advice, and that uninstall removes it and only it. All offline.
"""
from __future__ import annotations

import functools
import http.server
import json
import shutil
import socket
import threading
from pathlib import Path

import pytest
from typer.testing import CliRunner

from corejs_fixture import core_js_manifest_entry, make_core_js_archive
from skips import reason
from horosa_skill.config import Settings
from horosa_skill.engine import node_runtime
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.errors import RuntimeError as HorosaRuntimeError
from horosa_skill.errors import recovery_for
from horosa_skill.runtime import HorosaRuntimeManager, engine_asset
from horosa_skill.runtime.pidlock import release, try_pid_lock
from horosa_skill.surfaces import cli

PKG_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((PKG_ROOT / "contracts" / "release_platforms.json").read_text(encoding="utf-8"))
VERSION = "9.9.9"
ASSET = engine_asset.ENGINE_ASSET_TEMPLATE.format(version=VERSION)
PREFERRED_PORT = 18765


def _free_port() -> int:
    """18765 when nobody holds it (the agreed test port), otherwise an ephemeral loopback port — the check gates the bind."""
    for port in (PREFERRED_PORT, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return probe.getsockname()[1]
    pytest.skip(reason("host", "no free loopback port"))


@pytest.fixture
def server(tmp_path: Path):
    """A static HTTP server on 127.0.0.1 serving <tmp>/www; yields (base_url, www_dir)."""
    www = tmp_path / "www"
    www.mkdir()

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args, **kwargs) -> None:  # noqa: D401 - keep pytest output clean
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", _free_port()), functools.partial(Quiet, directory=str(www)))
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", www
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture(autouse=True)
def _no_engine_override(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HOROSA_CORE_JS_ROOT", "HOROSA_RUNTIME_MIRROR", "HOROSA_RUNTIME_MANIFEST_URL", "HOROSA_NODE_BIN"):
        monkeypatch.delenv(name, raising=False)
    node_runtime.clear_caches()


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
        data_dir=tmp_path / "data", db_path=tmp_path / "data" / "memory.db", output_dir=tmp_path / "data" / "runs",
        trace_dir=tmp_path / "data" / "traces", runtime_root=tmp_path / "rt",
    )


def _publish(www: Path, base: str, *, sha256: str | None = None, url: str | None = None, **archive_kwargs) -> tuple[str, dict]:
    """Put the asset at <www>/<ASSET> and a manifest (only darwin-arm64 + core_js) next to it; return (manifest file URI, info)."""
    info = make_core_js_archive(www / ASSET, VERSION, **archive_kwargs)
    entry = core_js_manifest_entry(info, url or f"{base}/{ASSET}", VERSION)
    if sha256 is not None:
        entry["sha256"] = sha256
    manifest = {"version": VERSION, "platforms": {"darwin-arm64": {"url": f"{base}/missing.tar.gz", "sha256": "0" * 64}},
                "core_js": entry}
    path = www / "runtime-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path.resolve().as_uri(), info


# ---------------------------------------------------------------- the installer's constants are the contract's


def test_installer_constants_match_the_release_contract() -> None:
    spec = CONTRACT["core_js"]
    assert engine_asset.ENGINE_ASSET_MANIFEST_KEY == spec["manifest_key"]
    assert engine_asset.ENGINE_ASSET_ROOT == spec["root"]
    assert engine_asset.ENGINE_ASSET_SINCE == spec["since"]
    assert engine_asset.ENGINE_ASSET_TEMPLATE == spec["asset"]
    assert list(engine_asset.ENGINE_ASSET_REQUIRED_ENTRIES) == spec["required_entries"]
    assert node_runtime.NODE_FLOOR_TEXT == spec["node_floor"]


# ---------------------------------------------------------------- install → resolve → reinstall → uninstall


def test_engine_only_install_downloads_verifies_places_and_is_found(tmp_path: Path, server) -> None:
    base, www = server
    manifest_uri, info = _publish(www, base)
    settings = _settings(tmp_path)
    manager = HorosaRuntimeManager(settings)

    result = manager.install(engine_only=True, manifest_url=manifest_uri)

    assert (result["ok"], result["mode"], result["reason"], result["changed"]) == (True, "engine_only", "requested", True)
    root = settings.runtime_root / "core-js" / "horosa-core-js"
    assert result["engine"]["root"] == str(root) and (root / "bin" / "cli.mjs").is_file()
    assert result["engine"]["sha256"] == info["sha256"] and result["engine"]["sha256_verified"] is True
    assert result["download"]["bytes"] == info["size"] and result["download"]["url"] == f"{base}/{ASSET}"
    assert not settings.runtime_current_dir.exists(), "engine-only never creates current/ (the runtime stays uninstalled)"
    record = json.loads((settings.runtime_root / "core-js" / "install.json").read_text(encoding="utf-8"))
    assert (record["version"], record["sha256"], record["reason"]) == (VERSION, info["sha256"], "requested")

    client = HorosaJsEngineClient(settings)
    roots = client._candidate_engine_roots()
    assert roots[0] == root, "the installed asset outranks the source checkout"
    diagnosis = client.diagnose()
    assert diagnosis["engine_source"] == "engine_asset" and diagnosis["engine_asset"]["installed"] is True
    assert {"source": "engine_asset", "path": str(root), "present": True} in diagnosis["searched"]

    again = manager.install(engine_only=True, manifest_url=manifest_uri)
    assert (again["changed"], again["skipped_download"]) == (False, True), "same sha256: no second download"


def test_download_goes_through_the_mirror_prefixes(tmp_path: Path, server, monkeypatch: pytest.MonkeyPatch) -> None:
    """The asset URL is a github.com release URL; HOROSA_RUNTIME_MIRROR rewrites it exactly like the runtime archives."""
    base, www = server
    github = f"https://github.com/o/r/releases/download/v{VERSION}/{ASSET}"
    mirrored = www / "mirror" / "o" / "r" / "releases" / "download" / f"v{VERSION}"
    mirrored.mkdir(parents=True)
    manifest_uri, info = _publish(www, base, url=github)
    shutil.copy(www / ASSET, mirrored / ASSET)
    monkeypatch.setenv("HOROSA_RUNTIME_MIRROR", f"{base}/mirror")

    result = HorosaRuntimeManager(_settings(tmp_path)).install(engine_only=True, manifest_url=manifest_uri)

    assert result["download"]["mirror_used"] is True
    assert result["download"]["url"] == f"{base}/mirror/o/r/releases/download/v{VERSION}/{ASSET}"
    assert result["engine"]["sha256"] == info["sha256"]


def test_uninstall_engine_only_removes_it_and_nothing_else(tmp_path: Path, server) -> None:
    base, www = server
    manifest_uri, _ = _publish(www, base)
    settings = _settings(tmp_path)
    manager = HorosaRuntimeManager(settings)
    manager.install(engine_only=True, manifest_url=manifest_uri)
    keep = [settings.runtime_current_dir / "runtime-manifest.json", settings.runtime_root / "downloads" / "x.part",
            settings.data_dir / "memory.db"]
    for path in keep:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("keep", encoding="utf-8")
    (settings.runtime_root / "core-js.previous").mkdir()

    plan = manager.uninstall(engine_only=True)
    assert plan["dry_run"] is True and sorted(plan["would_remove"]) == sorted(
        str(settings.runtime_root / name) for name in ("core-js", "core-js.previous"))
    assert (settings.runtime_root / "core-js").is_dir(), "dry run deletes nothing"

    done = manager.uninstall(engine_only=True, yes=True)
    assert done["removed"] == plan["would_remove"]
    assert not (settings.runtime_root / "core-js").exists() and not (settings.runtime_root / "core-js.previous").exists()
    assert all(path.read_text(encoding="utf-8") == "keep" for path in keep), "runtime, downloads and data are not the asset's"
    assert engine_asset.installed_engine_root(settings.runtime_root) is None


def test_full_uninstall_also_removes_the_engine_asset(tmp_path: Path, server, monkeypatch: pytest.MonkeyPatch) -> None:
    base, www = server
    manifest_uri, _ = _publish(www, base)
    settings = _settings(tmp_path)
    manager = HorosaRuntimeManager(settings)
    manager.install(engine_only=True, manifest_url=manifest_uri)
    monkeypatch.setattr(manager, "stop_local_services", lambda **_: {"ok": True})
    assert str(settings.runtime_root / "core-js") in manager.uninstall()["would_remove"]
    manager.uninstall(yes=True)
    assert not (settings.runtime_root / "core-js").exists()


def test_engine_only_uninstall_refuses_purge_flags(tmp_path: Path) -> None:
    with pytest.raises(HorosaRuntimeError) as excinfo:
        HorosaRuntimeManager(_settings(tmp_path)).uninstall(engine_only=True, purge_data=True, yes=True)
    assert excinfo.value.code == "runtime.uninstall_engine_only_conflict"


# ---------------------------------------------------------------- refusals leave what is installed alone


def test_a_tampered_asset_is_refused_and_the_installed_engine_survives(tmp_path: Path, server) -> None:
    base, www = server
    manifest_uri, good = _publish(www, base)
    settings = _settings(tmp_path)
    manager = HorosaRuntimeManager(settings)
    manager.install(engine_only=True, manifest_url=manifest_uri)

    tampered_uri, _ = _publish(www, base, sha256="ab" * 32)  # bytes on the server no longer match the manifest
    with pytest.raises(HorosaRuntimeError) as excinfo:
        manager.install(engine_only=True, manifest_url=tampered_uri, force=True)
    assert excinfo.value.code == "runtime.install_sha256_mismatch"
    record = engine_asset.read_record(settings.runtime_root)
    assert record and record["sha256"] == good["sha256"], "the good engine is still the installed one"
    assert not list(settings.runtime_root.glob(".hi-*")), "no temp tree left behind"


def test_a_pinned_digest_that_disagrees_with_the_manifest_is_refused_before_download(tmp_path: Path, server) -> None:
    base, www = server
    manifest_uri, _ = _publish(www, base)
    with pytest.raises(HorosaRuntimeError) as excinfo:
        HorosaRuntimeManager(_settings(tmp_path)).install(engine_only=True, manifest_url=manifest_uri, sha256="cd" * 32)
    assert excinfo.value.code == "runtime.install_sha256_mismatch"
    assert excinfo.value.details["asset"] == "core_js"


def test_a_manifest_without_the_asset_says_so(tmp_path: Path) -> None:
    manifest = tmp_path / "old-manifest.json"
    manifest.write_text(json.dumps({"version": "0.49.0", "platforms": {"darwin-arm64": {"url": "x", "sha256": "0" * 64}}}),
                        encoding="utf-8")
    with pytest.raises(HorosaRuntimeError) as excinfo:
        HorosaRuntimeManager(_settings(tmp_path)).install(engine_only=True, manifest_url=manifest.as_uri())
    error = excinfo.value
    assert error.code == "runtime.engine_asset_missing" and error.details["since"] == engine_asset.ENGINE_ASSET_SINCE
    assert "HOROSA_CORE_JS_ROOT" in str(error)
    assert "since" in recovery_for(error.code, error.details)["agent_recovery"]["prompt_to_user"]


def test_an_asset_missing_on_the_server_is_a_clear_download_failure(tmp_path: Path, server) -> None:
    base, www = server
    manifest_uri, _ = _publish(www, base)
    (www / ASSET).unlink()
    with pytest.raises(HorosaRuntimeError) as excinfo:
        HorosaRuntimeManager(_settings(tmp_path)).install(engine_only=True, manifest_url=manifest_uri)
    assert excinfo.value.code == "runtime.install_download_failed"
    assert any("HTTP 404" in failure for failure in excinfo.value.details["failures"])


@pytest.mark.parametrize("archive_kwargs, needle", [
    ({"omit": ("bin/cli.mjs",)}, "bin/cli.mjs"),
    ({"omit": ("node_modules/lunar-javascript/package.json",)}, "node_modules/lunar-javascript"),
    ({"root": "something-else"}, "top level"),
])
def test_an_archive_that_is_not_an_engine_is_refused(tmp_path: Path, server, archive_kwargs: dict, needle: str) -> None:
    base, www = server
    manifest_uri, _ = _publish(www, base, **archive_kwargs)
    settings = _settings(tmp_path)
    with pytest.raises(HorosaRuntimeError) as excinfo:
        HorosaRuntimeManager(settings).install(engine_only=True, manifest_url=manifest_uri)
    assert excinfo.value.code == "runtime.engine_asset_invalid"
    assert any(needle in problem for problem in excinfo.value.details["problems"])
    assert not (settings.runtime_root / "core-js").exists()


def test_a_traversing_member_is_refused(tmp_path: Path, server) -> None:
    base, www = server
    manifest_uri, _ = _publish(www, base, extra={"horosa-core-js/../../escape.js": b"x"})
    with pytest.raises(HorosaRuntimeError) as excinfo:
        HorosaRuntimeManager(_settings(tmp_path)).install(engine_only=True, manifest_url=manifest_uri)
    assert excinfo.value.code == "runtime.install_path_traversal"
    assert not (tmp_path / "escape.js").exists() and not (tmp_path / "rt" / "escape.js").exists()


def test_a_local_archive_with_a_pinned_digest_installs_offline(tmp_path: Path) -> None:
    info = make_core_js_archive(tmp_path / "dl" / ASSET, VERSION)
    manager = HorosaRuntimeManager(_settings(tmp_path))
    result = manager.install(engine_only=True, archive=str(info["path"]), sha256=info["sha256"])
    assert result["engine"]["sha256_verified"] is True and result["changed"] is True
    with pytest.raises(HorosaRuntimeError) as excinfo:
        manager.install(engine_only=True, archive=str(info["path"]), sha256="ef" * 32, force=True)
    assert excinfo.value.code == "runtime.install_sha256_mismatch"


def test_a_concurrent_engine_install_is_refused(tmp_path: Path, server) -> None:
    base, www = server
    manifest_uri, _ = _publish(www, base)
    settings = _settings(tmp_path)
    settings.runtime_root.mkdir(parents=True)
    lock = settings.runtime_root / engine_asset.ENGINE_LOCK_NAME
    assert try_pid_lock(lock, owner="other-install")
    try:
        with pytest.raises(HorosaRuntimeError) as excinfo:
            HorosaRuntimeManager(settings).install(engine_only=True, manifest_url=manifest_uri)
    finally:
        release(lock)
    assert excinfo.value.code == "runtime.engine_install_in_progress"


# ---------------------------------------------------------------- no runtime archive for this platform → engine-only


def test_install_on_a_platform_without_a_payload_installs_the_engine(tmp_path: Path, server) -> None:
    base, www = server
    manifest_uri, _ = _publish(www, base)
    settings = _settings(tmp_path)

    result = HorosaRuntimeManager(settings).install(manifest_url=manifest_uri, platform_key="linux-x64")

    assert (result["mode"], result["reason"], result["platform"]) == ("engine_only", "no_payload_for_platform", "linux-x64")
    codes = [warning["code"] for warning in result["warnings"]]
    assert "runtime.engine_only_installed" in codes, "say that only the engine was installed, and why"
    notice = next(w for w in result["warnings"] if w["code"] == "runtime.engine_only_installed")
    assert "HOROSA_SERVER_ROOT" in notice["message"], "the Java / chart techniques still need gateway mode"
    assert result["supported_platforms"] == ["darwin-arm64"]
    assert not settings.runtime_current_dir.exists()
    assert engine_asset.installed_engine_root(settings.runtime_root) is not None


def test_a_supported_platform_missing_from_the_manifest_is_called_an_incomplete_release(tmp_path: Path, server) -> None:
    """win32-x64 has a payload; a manifest without it is a half release, not «this platform has none»."""
    base, www = server
    manifest_uri, _ = _publish(www, base)
    result = HorosaRuntimeManager(_settings(tmp_path)).install(manifest_url=manifest_uri, platform_key="win32-x64")
    assert (result["mode"], result["reason"]) == ("engine_only", "manifest_lacks_platform")
    notice = next(w for w in result["warnings"] if w["code"] == "runtime.engine_only_installed")
    assert "--manifest-url" in notice["message"] and "没有离线 runtime 归档，只装了" not in notice["message"]


def test_without_the_asset_a_payloadless_platform_still_gets_the_old_dead_end(tmp_path: Path) -> None:
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"version": "0.49.0", "platforms": {"darwin-arm64": {"url": "x", "sha256": "0" * 64}}}),
                        encoding="utf-8")
    with pytest.raises(HorosaRuntimeError) as excinfo:
        HorosaRuntimeManager(_settings(tmp_path)).install(manifest_url=manifest.as_uri(), platform_key="linux-x64")
    assert excinfo.value.code == "runtime.install_missing_platform"


# ---------------------------------------------------------------- Node: the engine installs, the result says what is missing


def test_missing_node_is_reported_not_fatal(tmp_path: Path, server, monkeypatch: pytest.MonkeyPatch) -> None:
    base, www = server
    manifest_uri, _ = _publish(www, base)
    monkeypatch.setattr(node_runtime.shutil, "which", lambda name: None)
    result = HorosaRuntimeManager(_settings(tmp_path)).install(engine_only=True, manifest_url=manifest_uri)
    assert result["ok"] is True and result["ready"] is False and result["node"]["problem"] == "not_found"
    warning = next(w for w in result["warnings"] if w["code"] == "js_engine.node_unavailable")
    assert "20.10" in warning["message"] and "HOROSA_NODE_BIN" in warning["message"]


def test_too_old_node_is_reported_with_the_version_found(tmp_path: Path, server, monkeypatch: pytest.MonkeyPatch) -> None:
    base, www = server
    manifest_uri, _ = _publish(www, base)
    fake = tmp_path / "bin" / "node"
    fake.parent.mkdir()
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("HOROSA_NODE_BIN", str(fake))
    monkeypatch.setattr(node_runtime, "probe_version", lambda path: "v18.19.0")
    result = HorosaRuntimeManager(_settings(tmp_path)).install(engine_only=True, manifest_url=manifest_uri)
    warning = next(w for w in result["warnings"] if w["code"] == "js_engine.node_too_old")
    assert "v18.19.0" in warning["message"] and result["ready"] is False


# ---------------------------------------------------------------- CLI


def test_cli_install_and_uninstall_engine_only(tmp_path: Path, server, monkeypatch: pytest.MonkeyPatch) -> None:
    base, www = server
    manifest_uri, info = _publish(www, base)
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "rt"))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    runner = CliRunner()
    installed = runner.invoke(cli.app, ["install", "--engine-only", "--manifest-url", manifest_uri])
    assert installed.exit_code == 0, installed.stderr
    payload = json.loads(installed.stdout)
    assert payload["mode"] == "engine_only" and payload["engine"]["sha256"] == info["sha256"]
    removed = runner.invoke(cli.app, ["uninstall", "--engine-only", "--yes"])
    assert removed.exit_code == 0 and json.loads(removed.stdout)["removed"] == [str(tmp_path / "rt" / "core-js")]


# ---------------------------------------------------------------- the real asset really runs


def test_the_real_asset_installs_and_runs_a_js_technique(tmp_path: Path, server) -> None:
    """Build the release asset from this tree, install it over HTTP, and run JS tools from it with the node on PATH."""
    import importlib.util
    import sys

    core = PKG_ROOT / "horosa-core-js"
    package = json.loads((core / "package.json").read_text(encoding="utf-8"))
    if not all((core / "node_modules" / dep / "package.json").is_file() for dep in package["dependencies"]):
        pytest.skip(reason("host", "horosa-core-js/node_modules not installed (npm ci --omit=dev)"))
    choice = node_runtime.resolve_node(_settings(tmp_path), None)
    if choice.problem:
        pytest.skip(reason("host", f"no usable node on PATH ({choice.problem})"))
    spec = importlib.util.spec_from_file_location("build_core_js_asset", PKG_ROOT / "scripts" / "build_core_js_asset.py")
    builder = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = builder
    spec.loader.exec_module(builder)
    base, www = server
    built = builder.build(skill_root=PKG_ROOT, out_dir=www, allow_dirty=True)
    version = package["version"]
    manifest = {"version": version, "platforms": {}, "core_js": {
        "url": f"{base}/{built['name']}", "sha256": built["sha256"], "size": built["size"], "archive_type": "tar.gz",
        "version": version, "node_floor": built["node_floor"], "root": "horosa-core-js"}}
    (www / "runtime-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    settings = _settings(tmp_path)

    result = HorosaRuntimeManager(settings).install(engine_only=True, manifest_url=(www / "runtime-manifest.json").as_uri())
    assert result["ready"] is True

    client = HorosaJsEngineClient(settings)
    assert client.diagnose()["engine_source"] == "engine_asset"
    found = client.run("place_search", {"query": "上海", "date": "2028-04-06", "limit": 1})  # tz-lookup + the city library
    assert found["data"]["match"]["iana"] == "Asia/Shanghai"
    assert client.run("huangli", {"date": "2026-11-12", "time": "09:00:00", "zone": "+08:00"}) is not None  # lunar-javascript


# ---------------------------------------------------------------- doctor


@pytest.mark.parametrize("engine_ok", [True, False])
def test_doctor_on_a_payloadless_platform_speaks_about_the_engine(engine_ok: bool) -> None:
    from horosa_skill.surfaces.doctor import _doctor_summary

    report = {"deployment": "not_installed", "platform_supported": False, "issues": ["runtime:not_installed"],
              "js_engine": {"ok": engine_ok, "state": "ready" if engine_ok else "absent", "affects": "x / y", "fix": "f / g"}}
    summary = _doctor_summary(report)
    if engine_ok:
        assert "JS 引擎已就位" in summary["user_summary"]
        assert "install --engine-only" not in summary["user_summary"]
    else:
        assert "install --engine-only" in summary["user_summary"]
    assert "HOROSA_SERVER_ROOT" in summary["next_action"], "the rest still needs gateway mode"
