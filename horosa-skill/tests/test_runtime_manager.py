from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
import threading
import time
import zipfile
from pathlib import Path
from types import MethodType

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import RuntimeInstallError, RuntimeValidationError
from horosa_skill.runtime import HorosaRuntimeManager


@pytest.fixture(autouse=True)
def _managed_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """本文件全部用例测的是 **managed** 模式（本机 runtime 由我们启停）。

    🔴 v0.37.0 起 `HOROSA_SERVER_ROOT` / `HOROSA_CHART_SERVER_ROOT` 指向别处会切进 **external**
    模式（只探不起不停）。而 AGENTS §8 记的「复现 CI 形状」recipe 恰恰要求把这两个变量指到不可达
    地址 —— 维护机上照那条 recipe 跑，这一整个文件会集体红，且报错完全指不到「模式不对」。
    每个用例自己清一遍太容易漏，autouse 一次清干净。真要测 external 的用例自己 setenv 覆盖。
    """
    monkeypatch.delenv("HOROSA_SERVER_ROOT", raising=False)
    monkeypatch.delenv("HOROSA_CHART_SERVER_ROOT", raising=False)
    monkeypatch.delenv("HOROSA_PORTS", raising=False)
    monkeypatch.delenv("HOROSA_RUNTIME_TRUST_PORTS", raising=False)

    # 🔴 归属判定也要钉住。本文件的用例几乎都只 stub `_service_status`（返回 reachable=True），
    # 而 `endpoint_identities` 会拿那个 URL 去**真的**跑 classify_endpoint：CI 上 9999/8899 没人监听
    # → unknown → `runtime.port_conflict_unknown_holder`，整批 start 用例红。
    # 而在维护机上它们**全绿**，因为本机 9999/8899 正跑着真 runtime，identity 回 ours ——
    # 「因为错误的原因通过」的又一例：本机的环境替测试补了一个它没声明的前提。
    # 想测归属的用例自己覆盖 endpoint_identities（如 test_start_refuses_when_a_foreign_process_holds_the_port）。
    from horosa_skill.runtime.identity import EndpointIdentity

    monkeypatch.setattr(
        "horosa_skill.runtime.manager.classify_endpoint",
        lambda url, **kwargs: EndpointIdentity("ours", "identity.nonce_match", url),
    )


def create_runtime_archive(tmp_path: Path) -> Path:
    payload_root = tmp_path / "runtime-payload"
    (payload_root / "Horosa-Web/astropy").mkdir(parents=True, exist_ok=True)
    (payload_root / "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles").mkdir(parents=True, exist_ok=True)
    (payload_root / "horosa-core-js/bin").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/mac/java/bin").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/mac/python/bin").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/mac/node/bin").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/mac/bundle").mkdir(parents=True, exist_ok=True)
    (payload_root / "Horosa-Web/start_horosa_local.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (payload_root / "Horosa-Web/stop_horosa_local.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (payload_root / "horosa-core-js/bin/cli.mjs").write_text("export {};\n", encoding="utf-8")
    (payload_root / "runtime/mac/java/bin/java").write_text("", encoding="utf-8")
    (payload_root / "runtime/mac/python/bin/python3").write_text("", encoding="utf-8")
    (payload_root / "runtime/mac/node/bin/node").write_text("", encoding="utf-8")
    (payload_root / "runtime/mac/bundle/astrostudyboot.jar").write_text("", encoding="utf-8")
    (payload_root / "runtime-manifest.json").write_text(json.dumps({"version": "1.2.3"}), encoding="utf-8")
    archive_path = tmp_path / "runtime-payload.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(payload_root, arcname="runtime-payload")
    return archive_path


def create_windows_runtime_archive(tmp_path: Path) -> Path:
    payload_root = tmp_path / "runtime-payload"
    (payload_root / "Horosa-Web/astropy").mkdir(parents=True, exist_ok=True)
    (payload_root / "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles").mkdir(parents=True, exist_ok=True)
    (payload_root / "horosa-core-js/bin").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/windows/java/bin").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/windows/python").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/windows/node").mkdir(parents=True, exist_ok=True)
    (payload_root / "runtime/windows/bundle").mkdir(parents=True, exist_ok=True)
    (payload_root / "Horosa-Web/start_horosa_local.ps1").write_text("Write-Host 'old start'\n", encoding="utf-8")
    (payload_root / "Horosa-Web/stop_horosa_local.ps1").write_text("Write-Host 'old stop'\n", encoding="utf-8")
    (payload_root / "runtime/windows/java/bin/java.exe").write_text("", encoding="utf-8")
    (payload_root / "runtime/windows/python/python.exe").write_text("", encoding="utf-8")
    (payload_root / "runtime/windows/node/node.exe").write_text("", encoding="utf-8")
    boot_jar = payload_root / "runtime/windows/bundle/astrostudyboot.jar"
    with zipfile.ZipFile(boot_jar, "w") as archive:
        archive.writestr(
            "BOOT-INF/classes/conf/properties/cache/caches.json",
            json.dumps(
                {
                    "needlocalmemcache": False,
                    "needcompress": False,
                    "needhystrix": False,
                    "cachefactoryclass": [
                        {
                            "default": True,
                            "name": "comm",
                            "class": "boundless.types.cache.RedisCacheFactory",
                            "config": "classpath:conf/properties/cache/rediscomm.properties",
                        },
                        {
                            "name": "clientapps",
                            "class": "boundless.types.cache.MongoCacheFactory",
                            "config": "classpath:conf/properties/cache/clientapps.properties",
                        },
                    ],
                }
            ),
        )
        archive.writestr(
            "BOOT-INF/classes/conf/properties/param/webparams.properties",
            "webencrypt.rsaparam.class=spacex.astrostudy.helper.RsaParamHelper\n",
        )
        archive.writestr(
            "BOOT-INF/classes/log4j2.xml",
            '<Configuration><Properties><Property name="basedir">${env:HOME}/.horosa-logs/astrostudyboot</Property></Properties></Configuration>\n',
        )
        archive.writestr("BOOT-INF/lib/boundless-1.2.1.2.jar", b"boundless")
    (payload_root / "runtime-manifest.json").write_text(
        json.dumps(
            {
                "version": "1.2.3",
                "platform": "win32-x64",
                "services": {
                    "start_script": "Horosa-Web/start_horosa_local.ps1",
                    "stop_script": "Horosa-Web/stop_horosa_local.ps1",
                },
                "runtimes": {
                    "python": "runtime/windows/python/python.exe",
                    "java": "runtime/windows/java/bin/java.exe",
                    "node": "runtime/windows/node/node.exe",
                },
                "artifacts": {
                    "horosa_web_root": "Horosa-Web",
                    "astropy_root": "Horosa-Web/astropy",
                    "flatlib_root": "Horosa-Web/flatlib-ctrad2/flatlib",
                    "swefiles_root": "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles",
                    "boot_jar": "runtime/windows/bundle/astrostudyboot.jar",
                    "horosa_core_js_root": "horosa-core-js",
                },
            }
        ),
        encoding="utf-8",
    )
    archive_path = tmp_path / "runtime-payload.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for path in payload_root.rglob("*"):
            archive.write(path, path.relative_to(payload_root.parent))
    return archive_path


def test_install_runtime_from_local_archive(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)

    result = manager.install(archive=str(archive))

    assert result["ok"] is True
    assert result["manifest"]["version"] == "1.2.3"
    assert result["manifest"]["runtime_payload_version"] == "1.2.3"
    assert result["manifest"]["schema_version"] == 1
    assert result["manifest"]["services"]["start_script"] == str(
        manager._platform_path("Horosa-Web/start_horosa_local.sh", "Horosa-Web/start_horosa_local.ps1")
    )
    assert (settings.runtime_current_dir / "runtime-manifest.json").is_file()


def test_install_missing_local_archive_raises_structured_error(tmp_path: Path) -> None:
    # 归档不存在 → 结构化 RuntimeInstallError（带 code，CLI 能干净接住出 {ok:false}），
    # 而非内置 RuntimeError 冒泡成 traceback。
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    with pytest.raises(RuntimeInstallError) as excinfo:
        manager.install(archive=str(tmp_path / "does-not-exist.tar.gz"))
    assert excinfo.value.code == "runtime.install_archive_missing"


def test_install_temp_dir_is_under_runtime_root(tmp_path: Path) -> None:
    # 提取临时目录须落在 runtime_root 同卷（最终 move 为原子 rename）。以真实安装验证：
    # 安装成功且 current 落位，runtime_root 下不残留 .horosa-install-* 临时目录。
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    result = manager.install(archive=str(archive))
    assert result["ok"] is True
    assert settings.runtime_current_dir.is_dir()
    leftovers = list((tmp_path / "runtime-root").glob(".horosa-install-*"))
    assert leftovers == []


def test_install_runtime_binds_service_urls_to_current_settings(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        server_root="http://127.0.0.1:34528",
        chart_server_root="http://127.0.0.1:34529",
    )
    manager = HorosaRuntimeManager(settings)

    result = manager.install(archive=str(archive))
    installed_manifest = json.loads((settings.runtime_current_dir / "runtime-manifest.json").read_text(encoding="utf-8"))

    assert result["manifest"]["services"]["backend_url"] == "http://127.0.0.1:34528"
    assert result["manifest"]["services"]["chart_url"] == "http://127.0.0.1:34529"
    assert installed_manifest["services"]["backend_url"] == "http://127.0.0.1:34528"
    assert installed_manifest["services"]["chart_url"] == "http://127.0.0.1:34529"


def test_doctor_reports_installed_runtime(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    report = manager.doctor()

    assert report["installed"] is True
    assert report["manifest_version"] == "1.2.3"
    assert report["runtime_payload_version"] == "1.2.3"
    assert report["manifest"]["version"] == "1.2.3"
    assert any(item["label"] == "java_runtime" for item in report["files"])
    assert any(item["label"] == "python_runtime" for item in report["files"])
    assert any(item["label"] == "node_runtime" for item in report["files"])
    assert any(item["label"] == "horosa_core_js_root" for item in report["files"])


def test_service_status_prefers_explicit_env_urls_over_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        server_root="http://127.0.0.1:34528",
        chart_server_root="http://127.0.0.1:34529",
    )
    manager = HorosaRuntimeManager(settings)
    seen: dict[str, str] = {}

    monkeypatch.setenv("HOROSA_SERVER_ROOT", "http://127.0.0.1:34528")
    monkeypatch.setenv("HOROSA_CHART_SERVER_ROOT", "http://127.0.0.1:34529")
    monkeypatch.setattr(manager, "_backend_reachable", lambda url: seen.setdefault("backend", url) or True)
    monkeypatch.setattr(manager, "_http_reachable", lambda url: seen.setdefault("chart", url) or True)

    manager._service_status(
        {
            "services": {
                "backend_url": "http://127.0.0.1:9999",
                "chart_url": "http://127.0.0.1:8899",
            }
        }
    )

    assert seen["backend"] == "http://127.0.0.1:34528/common/time"
    assert seen["chart"] == "http://127.0.0.1:34529"


def _stub_popen(monkeypatch, *, seen: dict, returncode=None, writes: bytes = b""):
    """把 subprocess.Popen 换成一个不真起进程的替身；returncode=None 表示「还在跑」。"""
    class _FakeProc:
        def __init__(self, **kwargs):
            self.pid = 4242
            self._rc = returncode

        def poll(self):
            return self._rc

    def fake_popen(command, **kwargs):
        seen.update(kwargs)
        seen["command"] = command
        handle = kwargs.get("stdout")
        if writes and hasattr(handle, "write"):
            handle.write(writes)
        return _FakeProc(**kwargs)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)


def test_run_start_command_spawns_the_launcher_detached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """启动器必须**分离**着跑，输出写进一份追加日志。

    旧实现是 `subprocess.run(...)`，而启动脚本自己会一直阻塞到服务就绪或 STARTUP_TIMEOUT
    （首次运行含解压 + CDS 训练，实测 300–900 秒）——全都发生在一次 MCP 请求内部。旧断言锁的
    正是那个形状（`capture_output=True` / 文件句柄 + `subprocess.run`），所以它**永远不会**为
    「一次工具调用卡了五分钟」变红：那是被断言保护起来的行为，不是被检查的行为。
    """
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    script = tmp_path / "Horosa-Web" / "start_horosa_local.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")

    monkeypatch.setattr("horosa_skill.runtime.manager.os.name", "posix", raising=False)
    monkeypatch.setattr(
        manager,
        "_service_status",
        lambda manifest: [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
        ],
    )
    seen: dict[str, object] = {}
    _stub_popen(monkeypatch, seen=seen, returncode=0, writes=b"services are ready.\n")

    completed, readiness = manager._run_start_command(
        command=["/bin/bash", str(script)],
        script=script,
        env={"HOME": str(tmp_path)},
        manifest=None,
    )

    assert seen.get("start_new_session") is True, "POSIX 上必须开新会话，否则父进程一退启动器跟着死"
    assert seen.get("stdin") is subprocess.DEVNULL
    assert seen.get("stderr") is subprocess.STDOUT, "stderr 必须并进同一份日志，两个句柄会交叉截断"
    assert getattr(seen.get("stdout"), "name", "").endswith("launcher.log")
    assert readiness["ready"] is True
    assert "services are ready." in completed.stdout
    assert (settings.runtime_root / "launcher.log").is_file()


def test_run_start_command_uses_detached_process_group_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows 上要 DETACHED_PROCESS + 新进程组，否则 Ctrl-C 会连带打断 runtime。"""
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_platform="win32-x64",
    )
    manager = HorosaRuntimeManager(settings)
    script = tmp_path / "Horosa-Web" / "start_horosa_local.ps1"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("Write-Host 'start'\n", encoding="utf-8")

    monkeypatch.setattr("horosa_skill.runtime.manager.os.name", "nt", raising=False)
    monkeypatch.setattr(
        manager,
        "_service_status",
        lambda manifest: [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
        ],
    )
    seen: dict[str, object] = {}
    _stub_popen(monkeypatch, seen=seen, returncode=0, writes=b"ok\n")

    completed, readiness = manager._run_start_command(
        command=["powershell", "-File", str(script)],
        script=script,
        env={"HOME": str(tmp_path)},
        manifest=None,
    )

    assert "creationflags" in seen
    assert "start_new_session" not in seen
    assert readiness["ready"] is True
    assert completed.stdout.strip() == "ok"


def test_run_start_command_returns_starting_instead_of_blocking(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """启动器还在跑而预算用尽 → 回 starting，不把调用方按在这儿等几分钟。

    这条是 `runtime.starting` 整条恢复链的源头：没有它，第一次调用某个技法会在一次 MCP 请求内
    卡到客户端自己的工具超时（Codex 默认 60 秒），用户看到「工具无响应」，而 runtime 其实
    正常启动中。
    """
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    script = tmp_path / "Horosa-Web" / "start_horosa_local.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/usr/bin/env bash\nsleep 600\n", encoding="utf-8")

    monkeypatch.setattr("horosa_skill.runtime.manager.os.name", "posix", raising=False)
    monkeypatch.setattr(
        manager,
        "_service_status",
        lambda manifest: [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": False},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
        ],
    )
    seen: dict[str, object] = {}
    _stub_popen(monkeypatch, seen=seen, returncode=None)   # 还在跑

    started = time.monotonic()
    _completed, readiness = manager._run_start_command(
        command=["/bin/bash", str(script)],
        script=script,
        env={"HOME": str(tmp_path)},
        manifest=None,
        wait_seconds=0.5,
    )
    elapsed = time.monotonic() - started

    assert readiness["ready"] is False
    assert readiness["starting"] is True
    assert readiness["launcher_pid"] == 4242
    assert elapsed < 3.0, f"预算 0.5s 却阻塞了 {elapsed:.1f}s"
    # 启动器 pid 记进注册表，别的进程据此知道「已经有人在启动了」。
    state = manager.load_runtime_state() or {}
    assert (state.get("launcher") or {}).get("pid") == 4242


def test_install_runtime_from_manifest_file_url(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    manifest = tmp_path / "runtime-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "1.2.3",
                "platforms": {
                    "darwin-arm64": {
                        "url": archive.resolve().as_uri(),
                        "sha256": "",
                        "archive_type": "tar.gz",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_platform="darwin-arm64",
    )
    manager = HorosaRuntimeManager(settings)

    result = manager.install(manifest_url=manifest.resolve().as_uri())

    assert result["ok"] is True
    assert result["manifest"]["version"] == "1.2.3"
    assert (settings.runtime_current_dir / "runtime-manifest.json").is_file()


def _install_fake_spawn(manager, *, returncode=0, output: str = "", pid=4242, on_spawn=None):
    """替掉真启动器。`on_spawn` 让用例在「启动器已起」这一刻翻转自己的服务状态。"""
    from pathlib import Path as _Path

    class _FakeProc:
        def __init__(self):
            self.pid = pid

        def poll(self):
            return returncode

    def fake_spawn(*, command, script, env):
        if on_spawn is not None:
            on_spawn()
        log_path = manager.runtime_root / manager.LAUNCHER_LOG_NAME
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "ab") as handle:
            handle.write(output.encode("utf-8"))
        return _FakeProc(), log_path

    manager._spawn_start_command = fake_spawn



def test_start_and_stop_runtime_updates_state(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))
    service_state = {"running": False}

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        reachable = service_state["running"]
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": reachable},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": reachable},
        ]

    def fake_wait_for_service_state(
        self: HorosaRuntimeManager,
        *,
        expected_reachable: bool,
        timeout_seconds: float,
        manifest: dict | None,
    ) -> dict[str, object]:
        service_state["running"] = expected_reachable
        return {
            "ready": True,
            "endpoints": [
                {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": expected_reachable},
                {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": expected_reachable},
            ],
        }

    manager._service_status = MethodType(fake_service_status, manager)
    manager._wait_for_service_state = MethodType(fake_wait_for_service_state, manager)
    # 启动器一起来，服务就可达（新实现在 _run_start_command 内部自己轮询 _service_status）。
    _install_fake_spawn(manager, output="services are ready.\n",
                        on_spawn=lambda: service_state.__setitem__("running", True))

    started = manager.start_local_services()

    assert started["ok"] is True
    assert started["already_running"] is False
    assert settings.runtime_state_path.is_file()
    # 启动锁必须已经释放（成功路径），否则下一次启动会被自己挡住。
    assert not (settings.runtime_root / ".runtime-start.lock").exists()

    service_state["running"] = True
    stopped = manager.stop_local_services(force=True)

    assert stopped["ok"] is True
    assert stopped["already_stopped"] is False
    assert not settings.runtime_state_path.exists()
def test_doctor_reports_invalid_manifest_and_runtime_state_without_crashing(tmp_path: Path) -> None:
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    settings.runtime_current_dir.mkdir(parents=True, exist_ok=True)
    (settings.runtime_current_dir / "runtime-manifest.json").write_text("{bad json", encoding="utf-8")
    settings.runtime_state_path.parent.mkdir(parents=True, exist_ok=True)
    settings.runtime_state_path.write_text("[1, 2, 3]", encoding="utf-8")

    report = manager.doctor()

    assert report["installed"] is True
    assert report["ok"] is False
    assert report["manifest"] is None
    assert report["manifest_issue"]["code"] == "runtime.manifest_invalid"
    assert report["runtime_state"] is None
    assert report["runtime_state_issue"]["code"] == "runtime.state_invalid"
    assert "runtime.manifest_invalid" in report["issues"]
    assert "runtime.state_invalid" in report["issues"]


def test_start_runtime_raises_for_invalid_installed_manifest(tmp_path: Path) -> None:
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    settings.runtime_current_dir.mkdir(parents=True, exist_ok=True)
    (settings.runtime_current_dir / "runtime-manifest.json").write_text("{bad json", encoding="utf-8")

    with pytest.raises(RuntimeValidationError, match="Installed runtime manifest is invalid"):
        manager.start_local_services()


def test_start_runtime_does_not_treat_partial_service_state_as_already_running(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    service_states = iter(
        [
            [
                {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
                {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
            ],
            [
                {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
                {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
            ],
        ]
    )

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return next(service_states)

    def fake_wait_for_service_state(
        self: HorosaRuntimeManager,
        *,
        expected_reachable: bool,
        timeout_seconds: float,
        manifest: dict | None,
    ) -> dict[str, object]:
        return {
            "ready": True,
            "endpoints": [
                {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": expected_reachable},
                {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": expected_reachable},
            ],
        }

    manager._service_status = MethodType(fake_service_status, manager)
    manager._wait_for_service_state = MethodType(fake_wait_for_service_state, manager)

    started = manager.start_local_services()

    assert started["ok"] is True
    assert started["already_running"] is False


def test_doctor_marks_partial_service_state_as_not_running(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
        ]

    manager._service_status = MethodType(fake_service_status, manager)

    report = manager.doctor()

    assert report["ok"] is False
    # Partial state is still an issue — but named per-half now (issue #14): java up + chart down.
    assert "services:chart_not_running" in report["issues"]
    assert report["degraded"] is None


def test_start_runtime_succeeds_when_script_returns_nonzero_but_services_become_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))
    reachable = {"value": False}

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": reachable["value"]},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": reachable["value"]},
        ]

    manager._service_status = MethodType(fake_service_status, manager)
    _install_fake_spawn(
        manager, returncode=1, output="partial startup\npid warning\n",
        on_spawn=lambda: reachable.__setitem__("value", True),
    )

    started = manager.start_local_services()

    assert started["ok"] is True
    assert started["warning"]["code"] == "runtime.start_nonzero_but_ready"
    assert manager.load_runtime_state()["status"] == "running_with_warnings"
def test_start_runtime_does_not_stop_the_healthy_half_before_relaunching(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """部分可达时**不许**先 stop 一遍。

    🔴 旧实现（本用例的旧版就是在锁那个行为）在「一半可达」时先调 stop_local_services 再全量
    重启 —— Java 起不来的机器上，每一次碰 Java 的调用都要顺手弄死正常的 chart 服务，再赌一次
    全量启动。启动脚本本身是幂等的，缺哪半边补哪半边即可。旧断言写的是 `stop_calls == ["stop"]`，
    也就是把这个 bug 当成了契约，所以它永远不会为此变红。
    """
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))
    chart_up = {"value": False}

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": chart_up["value"]},
        ]

    # java 可达那半边是我们自己的，冲突检查必须放行。
    manager._service_status = MethodType(fake_service_status, manager)
    monkeypatch.setattr(manager, "endpoint_identities", lambda manifest, endpoints=None: [
        {**item, "identity": {"verdict": "ours", "evidence": "identity.nonce_match", "started_by_us": True}}
        for item in fake_service_status(manager, manifest)
    ])

    stop_calls: list[str] = []

    def fake_stop_local_services(*, force: bool = False) -> dict[str, object]:
        stop_calls.append("stop")
        return {"ok": True, "already_stopped": False}

    monkeypatch.setattr(manager, "stop_local_services", fake_stop_local_services)
    _install_fake_spawn(manager, output="services are ready.\n",
                        on_spawn=lambda: chart_up.__setitem__("value", True))

    started = manager.start_local_services()

    assert started["ok"] is True
    assert stop_calls == [], "部分可达不该触发 stop —— 那会把健康的那半边也停掉"
def test_start_runtime_retries_after_failed_launch_with_stale_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": False},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
        ]

    run_results = iter(
        [
            (
                subprocess.CompletedProcess(args=["bash"], returncode=1, stdout="pid files already exist", stderr=""),
                {
                    "ready": False,
                    "endpoints": [
                        {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
                        {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
                    ],
                },
            ),
            (
                subprocess.CompletedProcess(args=["bash"], returncode=0, stdout="ok", stderr=""),
                {
                    "ready": True,
                    "endpoints": [
                        {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
                        {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
                    ],
                },
            ),
        ]
    )

    def fake_run_start_command(
        self: HorosaRuntimeManager,
        *,
        command: list[str],
        script: Path,
        env: dict[str, str],
        manifest: dict | None,
        wait_seconds: float | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        return next(run_results)

    stop_calls: list[str] = []

    def fake_stop_local_services(*, force: bool = False) -> dict[str, object]:
        stop_calls.append("stop")
        return {"ok": True, "already_stopped": False}

    manager._service_status = MethodType(fake_service_status, manager)
    manager._run_start_command = MethodType(fake_run_start_command, manager)
    monkeypatch.setattr(manager, "stop_local_services", fake_stop_local_services)

    started = manager.start_local_services()

    assert started["ok"] is True
    assert started["recovered_partial_state"] is True
    assert stop_calls == ["stop"]


def test_install_patches_windows_runtime_templates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = create_windows_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_platform="win32-x64",
    )
    manager = HorosaRuntimeManager(settings)
    monkeypatch.setattr(
        manager,
        "_compile_windows_runtime_patch_classes",
        lambda manifest, jar_path: {
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory.class": b"class-bytes",
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory$LocalCache.class": b"class-bytes",
        },
    )

    manager.install(archive=str(archive))
    manifest = manager.load_installed_manifest(strict=True)
    monkeypatch.setattr("horosa_skill.runtime.manager.os.name", "nt", raising=False)
    monkeypatch.setattr(manager, "_runtime_template_root", lambda: tmp_path / "template-root")
    monkeypatch.setenv("HOME", r"C:\Users\maxwe")
    monkeypatch.setenv("USERPROFILE", r"C:\Users\maxwe")
    windows_template_root = manager._runtime_template_root() / "windows"
    windows_template_root.mkdir(parents=True, exist_ok=True)
    (windows_template_root / "start_horosa_local.ps1").write_text(
        'Start-Process -RedirectStandardOutput "a" -RedirectStandardError "b"\n',
        encoding="utf-8",
    )
    (windows_template_root / "stop_horosa_local.ps1").write_text(
        'Write-Host "stop requested"\n',
        encoding="utf-8",
    )
    manager._apply_runtime_overrides(manifest)

    start_script = settings.runtime_current_dir / "Horosa-Web/start_horosa_local.ps1"
    stop_script = settings.runtime_current_dir / "Horosa-Web/stop_horosa_local.ps1"
    boot_jar = settings.runtime_current_dir / "runtime/windows/bundle/astrostudyboot.jar"
    assert "RedirectStandardOutput" in start_script.read_text(encoding="utf-8")
    assert "Write-Host \"stop requested\"" in stop_script.read_text(encoding="utf-8")
    with zipfile.ZipFile(boot_jar) as archive:
        cache_config = json.loads(archive.read("BOOT-INF/classes/conf/properties/cache/caches.json"))
        assert all(entry["class"] == "horosa.offline.LocalCacheFactory" for entry in cache_config["cachefactoryclass"])
        assert archive.read("BOOT-INF/classes/conf/properties/param/webparams.properties").decode("utf-8").strip().endswith(
            "webencrypt.rsaparam.class="
        )
        assert (
            archive.read("BOOT-INF/classes/log4j2.xml").decode("utf-8")
            == '<Configuration><Properties><Property name="basedir">C:/Users/maxwe/.horosa-logs/astrostudyboot</Property></Properties></Configuration>\n'
        )
        assert archive.read("BOOT-INF/classes/horosa/offline/LocalCacheFactory.class") == b"class-bytes"
        assert archive.read("BOOT-INF/classes/horosa/offline/LocalCacheFactory$LocalCache.class") == b"class-bytes"


def test_posix_runtime_overrides_patch_boot_jar_without_windows_scripts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_platform="darwin-arm64",
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))
    manifest = manager.load_installed_manifest(strict=True)
    manifest["artifacts"]["boot_jar"] = "runtime/mac/bundle/astrostudyboot.jar"
    boot_jar = settings.runtime_current_dir / "runtime/mac/bundle/astrostudyboot.jar"
    with zipfile.ZipFile(boot_jar, "w") as archive_file:
        archive_file.writestr(
            "BOOT-INF/classes/conf/properties/cache/caches.json",
            json.dumps(
                {
                    "needlocalmemcache": False,
                    "needcompress": False,
                    "needhystrix": False,
                    "cachefactoryclass": [
                        {
                            "default": True,
                            "name": "comm",
                            "class": "boundless.types.cache.RedisCacheFactory",
                            "config": "classpath:conf/properties/cache/rediscomm.properties",
                        },
                        {
                            "name": "clientapps",
                            "class": "boundless.types.cache.MongoCacheFactory",
                            "config": "classpath:conf/properties/cache/clientapps.properties",
                        },
                    ],
                }
            ),
        )
        archive_file.writestr(
            "BOOT-INF/classes/log4j2.xml",
            '<Configuration><Properties><Property name="basedir">${env:HOME}/.horosa-logs/astrostudyboot</Property></Properties></Configuration>\n',
        )
        archive_file.writestr("BOOT-INF/lib/boundless-1.2.1.2.jar", b"boundless")

    monkeypatch.setattr("horosa_skill.runtime.manager.os.name", "posix", raising=False)
    monkeypatch.setattr(
        manager,
        "_compile_windows_runtime_patch_classes",
        lambda manifest, jar_path: {
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory.class": b"class-bytes",
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory$LocalCache.class": b"class-bytes",
        },
    )
    monkeypatch.setenv("HOME", "/Users/horacedong")

    patched = manager._apply_runtime_overrides(manifest)

    assert patched == [str(boot_jar)]
    with zipfile.ZipFile(boot_jar) as archive_file:
        cache_config = json.loads(archive_file.read("BOOT-INF/classes/conf/properties/cache/caches.json"))
        assert all(entry["class"] == "horosa.offline.LocalCacheFactory" for entry in cache_config["cachefactoryclass"])
        assert (
            archive_file.read("BOOT-INF/classes/log4j2.xml").decode("utf-8")
            == '<Configuration><Properties><Property name="basedir">/Users/horacedong/.horosa-logs/astrostudyboot</Property></Properties></Configuration>\n'
        )
        assert archive_file.read("BOOT-INF/classes/horosa/offline/LocalCacheFactory.class") == b"class-bytes"
        assert archive_file.read("BOOT-INF/classes/horosa/offline/LocalCacheFactory$LocalCache.class") == b"class-bytes"


def test_start_runtime_reports_patched_files_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = create_windows_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_platform="win32-x64",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    monkeypatch.setattr(
        manager,
        "_compile_windows_runtime_patch_classes",
        lambda manifest, jar_path: {
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory.class": b"class-bytes",
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory$LocalCache.class": b"class-bytes",
        },
    )
    manager.install(archive=str(archive))
    monkeypatch.setattr("horosa_skill.runtime.manager.os.name", "nt", raising=False)
    monkeypatch.setattr(manager, "_runtime_template_root", lambda: tmp_path / "template-root")
    windows_template_root = manager._runtime_template_root() / "windows"
    windows_template_root.mkdir(parents=True, exist_ok=True)
    (windows_template_root / "start_horosa_local.ps1").write_text(
        'Start-Process -RedirectStandardOutput "a" -RedirectStandardError "b"\n',
        encoding="utf-8",
    )
    (windows_template_root / "stop_horosa_local.ps1").write_text(
        'Write-Host "stop requested"\n',
        encoding="utf-8",
    )

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": False},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
        ]

    def fake_wait_for_service_state(
        self: HorosaRuntimeManager,
        *,
        expected_reachable: bool,
        timeout_seconds: float,
        manifest: dict | None,
    ) -> dict[str, object]:
        return {
            "ready": True,
            "endpoints": [
                {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": expected_reachable},
                {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": expected_reachable},
            ],
        }

    reachable = {"value": False}

    def flipping_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": reachable["value"]},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": reachable["value"]},
        ]

    manager._service_status = MethodType(flipping_service_status, manager)
    manager._wait_for_service_state = MethodType(fake_wait_for_service_state, manager)
    _install_fake_spawn(manager, output="ok\n",
                        on_spawn=lambda: reachable.__setitem__("value", True))

    started = manager.start_local_services()

    assert started["ok"] is True
    assert len(started["patched_files"]) == 3
    assert any(path.endswith("astrostudyboot.jar") for path in started["patched_files"])


def test_start_runtime_skips_windows_jar_patch_when_services_are_already_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = create_windows_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_platform="win32-x64",
    )
    manager = HorosaRuntimeManager(settings)
    monkeypatch.setattr(
        manager,
        "_compile_windows_runtime_patch_classes",
        lambda manifest, jar_path: {
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory.class": b"class-bytes",
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory$LocalCache.class": b"class-bytes",
        },
    )
    manager.install(archive=str(archive))
    monkeypatch.setattr("horosa_skill.runtime.manager.os.name", "nt", raising=False)

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
        ]

    manager._service_status = MethodType(fake_service_status, manager)
    monkeypatch.setattr(
        manager,
        "_apply_runtime_overrides",
        lambda manifest: (_ for _ in ()).throw(AssertionError("should not patch a running runtime")),
    )

    started = manager.start_local_services()

    assert started["ok"] is True
    assert started["already_running"] is True


def test_start_runtime_sets_windows_home_env_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = create_windows_runtime_archive(tmp_path)
    home_root = tmp_path / "isolated-home"
    settings = Settings(
        data_dir=home_root / ".horosa-skill",
        runtime_root=home_root / ".horosa" / "runtime",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_platform="win32-x64",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    monkeypatch.setattr(
        manager,
        "_compile_windows_runtime_patch_classes",
        lambda manifest, jar_path: {
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory.class": b"class-bytes",
            "BOOT-INF/classes/horosa/offline/LocalCacheFactory$LocalCache.class": b"class-bytes",
        },
    )
    manager.install(archive=str(archive))

    monkeypatch.setattr("horosa_skill.runtime.manager.os.name", "nt", raising=False)
    monkeypatch.setattr(manager, "_apply_runtime_overrides", lambda manifest: [])
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": False},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
        ]

    captured_env: dict[str, str] = {}

    def fake_run_start_command(
        self: HorosaRuntimeManager,
        *,
        command: list[str],
        script: Path,
        env: dict[str, str],
        manifest: dict | None,
        wait_seconds: float | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        captured_env.update(env)
        return (
            subprocess.CompletedProcess(args=command, returncode=0, stdout="ok", stderr=""),
            {
                "ready": True,
                "endpoints": [
                    {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
                    {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
                ],
            },
        )

    manager._service_status = MethodType(fake_service_status, manager)
    manager._run_start_command = MethodType(fake_run_start_command, manager)

    started = manager.start_local_services()

    assert started["ok"] is True
    assert captured_env["HOME"] == str(home_root)
    assert captured_env["USERPROFILE"] == str(home_root)


def test_start_runtime_serializes_concurrent_calls(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    service_state = {"running": False}
    entered = threading.Event()
    release = threading.Event()
    run_start_calls: list[str] = []

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": service_state["running"]},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": service_state["running"]},
        ]

    def fake_run_start_command(
        self: HorosaRuntimeManager,
        *,
        command: list[str],
        script: Path,
        env: dict[str, str],
        manifest: dict | None,
        wait_seconds: float | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        run_start_calls.append("start")
        entered.set()
        release.wait(timeout=2)
        service_state["running"] = True
        return (
            subprocess.CompletedProcess(args=command, returncode=0, stdout="ok", stderr=""),
            {
                "ready": True,
                "endpoints": [
                    {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": True},
                    {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
                ],
            },
        )

    manager._service_status = MethodType(fake_service_status, manager)
    manager._run_start_command = MethodType(fake_run_start_command, manager)

    background_result: dict[str, object] = {}

    def _background_start() -> None:
        background_result.update(manager.start_local_services())

    thread = threading.Thread(target=_background_start)
    thread.start()
    assert entered.wait(timeout=1)

    foreground_done = threading.Event()
    foreground_result: dict[str, object] = {}

    def _foreground_start() -> None:
        foreground_result.update(manager.start_local_services())
        foreground_done.set()

    waiter = threading.Thread(target=_foreground_start)
    waiter.start()
    assert not foreground_done.wait(timeout=0.1)

    release.set()
    thread.join(timeout=2)
    waiter.join(timeout=2)

    assert background_result["ok"] is True
    assert foreground_result["ok"] is True
    assert foreground_result["already_running"] is True
    assert run_start_calls == ["start"]


def test_repo_windows_start_template_bootstraps_python_paths() -> None:
    template = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "runtime_templates"
        / "windows"
        / "start_horosa_local.ps1"
    )

    content = template.read_text(encoding="utf-8")

    assert "runpy.run_path" in content
    assert 'Set-Content -LiteralPath $PyBootstrapPath' in content
    assert "-ArgumentList ('\"{0}\"' -f $PyBootstrapPath)" in content  # quoted: spaced user names (v0.38.0 B1)
    assert "$env:HOME" in content
    assert "$env:USERPROFILE" in content
    assert "PYTHONIOENCODING" in content
    assert '-ArgumentList "-c", $PyBootCode' not in content


def test_repo_windows_runtime_java_template_exists() -> None:
    template = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "runtime_templates"
        / "windows"
        / "java"
        / "horosa"
        / "offline"
        / "LocalCacheFactory.java"
    )

    content = template.read_text(encoding="utf-8")

    assert "class LocalCacheFactory" in content
    assert "needMemCache" in content


def _manifest_file(tmp_path: Path, archive: Path, version: str = "1.2.3") -> Path:
    manifest = tmp_path / f"runtime-manifest-{version}.json"
    manifest.write_text(
        json.dumps(
            {
                "version": version,
                "platforms": {
                    "darwin-arm64": {"url": archive.resolve().as_uri(), "sha256": "", "archive_type": "tar.gz"}
                },
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_install_skips_download_when_version_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 版本短路：同版本非 --force 时下载前直接返回 skipped_download，不再取大包。
    archive = create_runtime_archive(tmp_path)
    manifest = _manifest_file(tmp_path, archive)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_platform="darwin-arm64",
    )
    manager = HorosaRuntimeManager(settings)
    first = manager.install(manifest_url=manifest.resolve().as_uri())
    assert first["changed"] is True

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("同版本不应触发归档下载")

    monkeypatch.setattr(manager, "_materialize_archive", _boom)
    second = manager.install(manifest_url=manifest.resolve().as_uri())
    assert second["changed"] is False and second["skipped_download"] is True

    # --force 恢复真实安装路径（会再次走 materialize）。
    monkeypatch.undo()
    # v0.38.1 R3 起换目录前会探端口归属；这里钉成「不可达」让用例不依赖本机 9999/8899 上跑着什么。
    monkeypatch.setattr(manager, "endpoint_identities", lambda manifest=None, endpoints=None: _endpoints(verdict="ours", reachable=False))
    forced = manager.install(manifest_url=manifest.resolve().as_uri(), force=True)
    assert forced["ok"] is True and forced["changed"] is True


def test_uninstall_dry_run_then_execute(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    manifest = _manifest_file(tmp_path, archive)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "memory.db",
        output_dir=tmp_path / "data" / "runs",
        runtime_platform="darwin-arm64",
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(manifest_url=manifest.resolve().as_uri())
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    dry = manager.uninstall()
    assert dry["dry_run"] is True
    assert any("current" in item for item in dry["would_remove"])
    assert settings.runtime_current_dir.exists()  # dry-run 不删

    done = manager.uninstall(yes=True)
    assert done["dry_run"] is False
    assert not settings.runtime_current_dir.exists()
    assert settings.data_dir.exists()  # 用户数据默认保留

    manager.install(manifest_url=manifest.resolve().as_uri())
    purge = manager.uninstall(yes=True, purge_data=True)
    assert purge["ok"] is True
    assert not settings.data_dir.exists()


def test_mirror_candidates_module_function_matches_the_manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """v0.38.0 B3：真身抽到 runtime/mirrors.py（客户端配置生成器给 wheel URL 用同一套改写）；manager 只委托。"""
    from horosa_skill.runtime.mirrors import mirror_candidates, preferred_mirror_url

    manager = HorosaRuntimeManager(Settings(runtime_root=tmp_path / "runtime-root", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs"))
    url = "https://github.com/o/r/releases/download/v1/horosa_skill-1-py3-none-any.whl"
    monkeypatch.setenv("HOROSA_RUNTIME_MIRROR", "https://mirror.example.com/github,https://m2.example.org")
    assert manager._mirror_candidates(url) == mirror_candidates(url)
    assert preferred_mirror_url(url) == "https://mirror.example.com/github/o/r/releases/download/v1/horosa_skill-1-py3-none-any.whl"
    assert mirror_candidates("file:///tmp/x.whl") == ["file:///tmp/x.whl"]
    monkeypatch.delenv("HOROSA_RUNTIME_MIRROR")
    assert preferred_mirror_url(url) == url


def test_mirror_candidates_rewrite_github_urls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    url = "https://github.com/o/r/releases/download/v1/x.tar.gz"
    assert manager._mirror_candidates(url) == [url]  # 无镜像=原样
    monkeypatch.setenv("HOROSA_RUNTIME_MIRROR", "https://mirror.example.com/github,https://m2.example.org")
    candidates = manager._mirror_candidates(url)
    assert candidates == [
        "https://mirror.example.com/github/o/r/releases/download/v1/x.tar.gz",
        "https://m2.example.org/o/r/releases/download/v1/x.tar.gz",
        url,
    ]
    # 非 github URL 不改写。
    other = "https://example.com/a.tar.gz"
    assert manager._mirror_candidates(other) == [other]


def test_download_with_resume_sends_range_and_appends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 断点续传：.part 存在时请求带 Range；206 响应续写完成整文件。
    import httpx

    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    settings.runtime_root.mkdir(parents=True, exist_ok=True)
    manager = HorosaRuntimeManager(settings)
    payload = b"0123456789" * 100
    half = len(payload) // 2
    downloads = settings.runtime_root / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    (downloads / "blob.bin.part").write_bytes(payload[:half])

    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        range_header = request.headers.get("range")
        if range_header:
            offset = int(range_header.split("=")[1].rstrip("-"))
            return httpx.Response(
                206,
                content=payload[offset:],
                headers={"Content-Length": str(len(payload) - offset)},
            )
        return httpx.Response(200, content=payload, headers={"Content-Length": str(len(payload))})

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def _patched_client(*args, **kwargs):  # noqa: ANN002, ANN003
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", _patched_client)
    progress_points: list[tuple[int, int | None]] = []
    target = manager._download_with_resume(
        "https://example.com/blob.bin", tmp_path, progress=lambda done, total: progress_points.append((done, total))
    )
    assert target.read_bytes() == payload
    assert captured_headers.get("range") == f"bytes={half}-"
    assert progress_points and progress_points[-1][0] == len(payload)


def _chart_only_endpoints() -> list[dict[str, object]]:
    return [
        {"label": "java_backend", "url": "http://127.0.0.1:9999/common/time", "reachable": False},
        {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
    ]


def test_run_start_command_accepts_chart_only_as_degraded(tmp_path: Path) -> None:
    # Issue #14: java 死 (WFP 拦 JDK-17 loopback) 时 chart-only 必须算降级成功，不再判整体失败。
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.3,
    )
    manager = HorosaRuntimeManager(settings)
    manager._service_status = MethodType(
        lambda self, manifest: _chart_only_endpoints(), manager
    )
    _install_fake_spawn(manager, returncode=0, output="java backend process exited (exit code 1)\n")
    script = tmp_path / "start.fake"
    script.write_text("", encoding="utf-8")

    completed, readiness = manager._run_start_command(
        command=["/bin/true"],
        script=script,
        env=os.environ.copy(),
        manifest=None,
    )
    assert completed.returncode == 0
    assert readiness["ready"] is True
    assert readiness["degraded"] is True
def test_start_local_services_reports_degraded_chart_only(tmp_path: Path) -> None:
    # 降级启动：ok=True + warning=runtime.start_degraded_chart_only + 状态文件 degraded_chart_only；
    # 不触发破坏性 stop+重试（readiness.ready=True 使旧的 partial-state 分支不进入）。
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.3,
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    stop_calls: list[bool] = []
    real_stop = manager.stop_local_services

    def spy_stop(self: HorosaRuntimeManager) -> dict[str, object]:
        stop_calls.append(True)
        return real_stop()

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999/common/time", "reachable": False},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": False},
        ]

    def fake_run_start(
        self: HorosaRuntimeManager,
        *,
        command: list[str],
        script: Path,
        env: dict[str, str],
        manifest: dict | None,
        wait_seconds: float | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        completed = subprocess.CompletedProcess(args=command, returncode=1, stdout="java backend process exited (exit code 1)", stderr="")
        return completed, {"ready": True, "degraded": True, "endpoints": _chart_only_endpoints()}

    manager._service_status = MethodType(fake_service_status, manager)
    manager._run_start_command = MethodType(fake_run_start, manager)
    manager.stop_local_services = MethodType(spy_stop, manager)

    started = manager.start_local_services()

    assert started["ok"] is True
    assert started["degraded"] is True
    assert started["warning"]["code"] == "runtime.start_degraded_chart_only"
    assert not stop_calls, "degraded start must not trigger the destructive stop+retry path"
    state = json.loads(settings.runtime_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "degraded_chart_only"


def test_doctor_names_dead_java_and_surfaces_boot_excerpt(tmp_path: Path) -> None:
    # doctor 在 chart 活/java 死时给专属 issue + degraded 标记 + 从启动器日志提取的 Java 崩溃摘录。
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    log_dir = settings.runtime_current_dir / "Horosa-Web" / ".horosa-local-logs" / "20260722_000000"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "astrostudyboot.stderr.log").write_text(
        "\n".join(
            [
                "2026-07-20 10:00:00 ERROR o.s.boot.SpringApplication - Application run failed",
                "org.springframework.beans.BeanInstantiationException: Failed to instantiate AIAnalysisProxyService",
                "Caused by: java.io.IOException: Unable to establish loopback connection",
                "Caused by: java.net.SocketException: Invalid argument: connect",
            ]
        ),
        encoding="utf-8",
    )

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return _chart_only_endpoints()

    manager._service_status = MethodType(fake_service_status, manager)
    report = manager.doctor()

    assert "services:java_backend_not_running" in report["issues"]
    assert "services:not_running" not in report["issues"]
    assert report["degraded"] == "chart_only"
    diagnostics = report["java_diagnostics"]
    assert diagnostics is not None
    assert any("SocketException" in line for line in diagnostics["excerpt"])
    assert any("Application run failed" in line for line in diagnostics["excerpt"])


def test_start_local_services_skips_restart_during_java_cooldown(tmp_path: Path) -> None:
    # v0.36.0 A5：Java 挂、chart 健康、冷却期内 → 直接返回 degraded，不 stop 任何服务、不跑启动脚本。
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.5,
        runtime_java_retry_cooldown_seconds=120.0,
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))

    def fake_service_status(self: HorosaRuntimeManager, manifest: dict | None) -> list[dict[str, object]]:
        return [
            {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": False},
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True},
        ]

    def forbidden(self: HorosaRuntimeManager, *args: object, **kwargs: object) -> None:
        raise AssertionError("a healthy chart service must not be stopped or restarted during the Java cooldown")

    manager._service_status = MethodType(fake_service_status, manager)
    manager.stop_local_services = MethodType(forbidden, manager)  # type: ignore[method-assign]
    manager._run_start_command = MethodType(forbidden, manager)  # type: ignore[method-assign]

    manager._last_degraded_start_at = time.monotonic()
    started = manager.start_local_services()
    assert started["ok"] is True and started["degraded"] is True and started["skipped_restart"] is True
    assert 0 < started["cooldown_remaining_seconds"] <= 120

    # 冷却过期 → 归零（真正的重启路径由既有 start 测试覆盖）
    manager._last_degraded_start_at = time.monotonic() - 1000
    assert manager.java_backend_cooldown_remaining() == 0.0

    # 新进程：从 runtime state 文件回读 degraded_chart_only 的时间戳；状态回到 running 即归零
    fresh = HorosaRuntimeManager(settings)
    fresh._write_runtime_state({"managed": True, "status": "degraded_chart_only", "updated_at": fresh._utc_now()})
    assert fresh.java_backend_cooldown_remaining() > 100
    fresh._write_runtime_state({"managed": True, "status": "running", "updated_at": fresh._utc_now()})
    assert fresh.java_backend_cooldown_remaining() == 0.0

    # 冷却设 0 = 关闭
    off = HorosaRuntimeManager(Settings(**{**settings.model_dump(), "runtime_java_retry_cooldown_seconds": 0.0}))
    off._last_degraded_start_at = time.monotonic()
    assert off.java_backend_cooldown_remaining() == 0.0


# ======================================================================================
# v0.37.0 B3–B5：端口归属、启动锁、有界启动
# ======================================================================================

def _manager_with_runtime(tmp_path: Path) -> HorosaRuntimeManager:
    archive = create_runtime_archive(tmp_path)
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(archive))
    return manager


def _endpoints(*, verdict: str, reachable: bool = True) -> list[dict[str, object]]:
    identity = {
        "verdict": verdict,
        "evidence": "identity.nonce_match" if verdict == "ours" else "process.command_is_not_ours",
        "started_by_us": verdict == "ours",
        "port": 8899,
        "holders": [{"pid": 4242, "command": "python -m http.server 8899"}],
    }
    return [
        {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": reachable,
         "identity": dict(identity) if reachable else None},
        {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": reachable,
         "identity": dict(identity) if reachable else None},
    ]


def test_start_refuses_when_a_foreign_process_holds_the_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """端口上是别人的服务 → 报冲突退出，绝不采用、绝不代为终止。

    🔴 旧实现只看 HTTP 响应码 < 500，任何应答者都会被静默采用为后端（症状：排盘失败但
    statusCode 200），部分可达时还会先跑一遍停脚本 —— 那会按端口关掉用户自己开着的星阙桌面端。
    既有测试只在 reachable True/False 上打转，对「可达的是谁」一无所问，所以全绿。
    """
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities",
                        lambda manifest, endpoints=None: _endpoints(verdict="foreign"))
    spawned: list[str] = []
    monkeypatch.setattr(manager, "_spawn_start_command",
                        lambda **kw: spawned.append("spawn"))

    with pytest.raises(RuntimeInstallError) as excinfo:
        manager.start_local_services(wait_seconds=0.2)

    assert excinfo.value.code == "runtime.port_conflict_foreign"
    assert excinfo.value.details["conflicts"]
    assert "不会终止" in excinfo.value.details["will_not_kill"]
    assert spawned == [], "报冲突时不该还去起启动器"


def test_start_refuses_an_unidentifiable_holder_unless_trusted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities",
                        lambda manifest, endpoints=None: _endpoints(verdict="unknown"))

    with pytest.raises(RuntimeInstallError) as excinfo:
        manager.start_local_services(wait_seconds=0.2)
    assert excinfo.value.code == "runtime.port_conflict_unknown_holder"

    # 用户明示信任后放行（此时全部可达 → already_running）
    monkeypatch.setenv("HOROSA_RUNTIME_TRUST_PORTS", "1")
    result = manager.start_local_services(wait_seconds=0.2)
    assert result["already_running"] is True


def test_stop_passes_the_same_ports_as_start_to_the_stop_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """🔴 停脚本按 `.horosa_py.<CHART_PORT>.pid` 找进程：端口不一致 = 找不到 pid 文件 = 服务永远停不掉。

    v0.38.0 A5 真机 lane 首跑（HOROSA_LOCAL_*_PORT=19999/18899）抓到：`runtime stop` 退出 0、状态卡 stop_requested、
    两个端口照样在听——停脚本拿到的是裸 os.environ，去找 8899/9999 的 pid 文件。负向对照：旧代码下本用例必红。
    """
    manager = _manager_with_runtime(tmp_path)
    manager.settings.local_backend_port = 19999
    manager.settings.local_chart_port = 18899
    monkeypatch.delenv("HOROSA_SERVER_PORT", raising=False)
    monkeypatch.delenv("HOROSA_CHART_PORT", raising=False)
    monkeypatch.setattr(manager, "endpoint_identities", lambda manifest, endpoints=None: _endpoints(verdict="ours", reachable=True))
    monkeypatch.setattr(manager, "_wait_for_service_state", lambda **kw: {"ready": True, "endpoints": _endpoints(verdict="ours", reachable=False)})
    seen: dict[str, object] = {}

    class _Done:
        returncode = 0
        stdout = "stopped"
        stderr = ""

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["env"] = kwargs.get("env") or {}
        return _Done()

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = manager.stop_local_services()

    assert result["ok"] is True
    assert seen["env"]["HOROSA_SERVER_PORT"] == "19999" and seen["env"]["HOROSA_CHART_PORT"] == "18899"
    assert seen["env"].get("HOME"), "停脚本与启动器同一个 HOME（pid 文件与日志目录都在它下面）"


def test_stop_refuses_services_we_did_not_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """只有 app 标记不算「我们的」—— 停下去可能关掉用户正在用的星阙桌面端。"""
    manager = _manager_with_runtime(tmp_path)
    weak = _endpoints(verdict="ours")
    for entry in weak:
        entry["identity"]["evidence"] = "identity.app_marker"
        entry["identity"]["started_by_us"] = False
    monkeypatch.setattr(manager, "endpoint_identities", lambda manifest, endpoints=None: weak)
    ran: list[str] = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: ran.append("stop"))

    result = manager.stop_local_services()

    assert result["refused"] is True
    assert result["code"] == "runtime.stop_refused_foreign"
    assert ran == [], "拒绝时绝不能已经跑过停脚本"


def test_external_mode_never_starts_or_stops_a_local_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """地址指到别处时只探不起不停。

    docker-compose 把 HOROSA_SERVER_ROOT 指到 host.docker.internal:9999；旧实现探不到就去跑
    **本机**的启动脚本，等于替用户在网关容器里装一整套 runtime。
    """
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setenv("HOROSA_SERVER_ROOT", "http://198.51.100.7:9999")
    assert manager.runtime_mode() == "external"
    monkeypatch.setattr(manager, "endpoint_identities",
                        lambda manifest, endpoints=None: _endpoints(verdict="unknown", reachable=False))
    spawned: list[str] = []
    monkeypatch.setattr(manager, "_spawn_start_command", lambda **kw: spawned.append("spawn"))

    with pytest.raises(RuntimeInstallError) as excinfo:
        manager.start_local_services(wait_seconds=0.2)
    assert excinfo.value.code == "runtime.external_unreachable"
    assert spawned == []

    stopped = manager.stop_local_services()
    assert stopped["refused"] is True and stopped["reason"] == "external_mode"


def test_pointing_at_our_own_local_ports_stays_managed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """把地址显式写成本机 runtime 自己的端口是正常用法，不能被误判成 external。"""
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setenv("HOROSA_SERVER_ROOT", "http://localhost:9999")
    monkeypatch.setenv("HOROSA_CHART_SERVER_ROOT", "http://127.0.0.1:8899")
    assert manager.runtime_mode() == "managed"


def test_second_process_does_not_launch_while_a_start_is_in_flight(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """跨进程启动锁：已有人在启动时，第二个调用只轮询，零 spawn。

    🔴 `self._service_lock` 只是**进程内**的锁。两个 MCP 客户端同时冷启动会各起一个启动器：
    抢同一个端口、互相覆盖 pid 文件，后到的看见「pid files already exist」就先 stop 再 start，
    把先到的那个刚起好的服务停掉。
    """
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities",
                        lambda manifest, endpoints=None: _endpoints(verdict="ours", reachable=False))
    monkeypatch.setattr(manager, "_service_status", lambda manifest: _endpoints(verdict="ours", reachable=False))
    spawned: list[str] = []
    monkeypatch.setattr(manager, "_spawn_start_command", lambda **kw: spawned.append("spawn"))

    # 假装另一个**活着的**进程正持锁（用本进程 pid 冒充）
    lock_path = manager.runtime_root / ".runtime-start.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps({"pid": os.getpid(), "owner": "runtime-start",
                                     "created_at": "2026-01-01T00:00:00+00:00"}), encoding="utf-8")

    result = manager.start_local_services(wait_seconds=0.3)

    assert result["starting"] is True
    assert result["started_by_other_process"] is True
    assert spawned == [], "已有人在启动时不该再起第二个启动器"


def test_start_lock_is_released_when_the_start_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """失败路径也必须释放锁 —— 否则本进程（一个长命的 serve）会把后续所有启动永久挡死。"""
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities",
                        lambda manifest, endpoints=None: _endpoints(verdict="ours", reachable=False))
    monkeypatch.setattr(manager, "_service_status", lambda manifest: _endpoints(verdict="ours", reachable=False))

    def boom(**_kw):
        raise RuntimeInstallError("nope", code="runtime.start_failed", details={})

    monkeypatch.setattr(manager, "_spawn_start_command", boom)

    with pytest.raises(RuntimeInstallError):
        manager.start_local_services(wait_seconds=0.2)

    assert not (manager.runtime_root / ".runtime-start.lock").exists()


def test_ci_shape_recipe_is_documented_and_the_fixture_covers_it() -> None:
    """🔴 维护机与 CI 的差别不止「装没装 runtime」，还有「默认端口上有没有活服务」。

    v0.37.0 引入归属判定后，只 stub `_service_status`（返回 reachable=True）的用例会拿那个 URL
    去**真的**跑 classify_endpoint。维护机的 9999/8899 上正跑着真 runtime → 判成 ours → 全绿；
    CI 上没人监听 → unknown → `runtime.port_conflict_unknown_holder` → 四条用例红。
    本机的环境替测试补了一个它没声明的前提，这是「因为错误的原因通过」的典型形状。

    本机复现 CI 条件（AGENTS §8 recipe 之外还要这一条）：
        创建一个 autouse fixture 把 `probe_identity` 打成返回 None、`listener_pids` 打成返回 []，
        用 `pytest -p <plugin>` 挂上去；不打 `_managed_mode` 里那个 classify_endpoint 桩时必红。
    """
    import inspect

    source = inspect.getsource(_managed_mode)
    assert "classify_endpoint" in source, (
        "_managed_mode 必须钉住归属判定 —— 否则这批用例在维护机上绿、在 CI 上红，"
        "而红的原因是「端口上没人应答」，与用例想测的东西毫无关系"
    )
    for name in ("HOROSA_SERVER_ROOT", "HOROSA_CHART_SERVER_ROOT"):
        assert name in source, f"_managed_mode 必须清 {name}（否则切进 external 模式）"

def test_windows_launcher_spawn_never_uses_detached_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows 启动器**不许**用 DETACHED_PROCESS 起。

    DETACHED_PROCESS 让子进程完全没有控制台，而启动器是 `powershell -File …`：无控制台的
    PowerShell 主机立刻 exit 0 且**一个字节都不写**。实测（真 Windows + 真 runtime）：12 秒内
    poll()==0、launcher.log 0 字节、服务一个没起，manager 只看到「已退出且未就绪」→ 报
    runtime.start_timeout 并建议跑 doctor/install，而启动器从未运行 —— install/selfcheck/serve
    在 Windows 上都起不了 runtime，且没有任何诊断留痕。
    CREATE_NO_WINDOW 有控制台、只是不弹窗；Windows 子进程本就不随父进程终止（实测父进程退出后
    启动器照旧把 chart 服务拉起来），所以 DETACHED 提供的「活过父进程」本来就不需要。
    """
    settings = Settings(
        runtime_root=tmp_path / "runtime-root",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
    )
    manager = HorosaRuntimeManager(settings)
    script = tmp_path / "start_horosa_local.ps1"
    script.write_text("", encoding="utf-8")
    captured: dict[str, object] = {}

    class _FakeProc:
        pid = 4242

        def poll(self):  # noqa: ANN201
            return None

    def fake_popen(command, **kwargs):  # noqa: ANN001, ANN003
        captured.update(kwargs)
        return _FakeProc()

    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False)
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0x8000000, raising=False)
    monkeypatch.setattr(subprocess, "DETACHED_PROCESS", 0x8, raising=False)

    manager._spawn_start_command(command=["powershell", "-File", str(script)], script=script, env={})

    flags = int(captured["creationflags"])  # type: ignore[arg-type]
    assert not flags & 0x8, "DETACHED_PROCESS kills the PowerShell launcher outright"
    assert flags & 0x8000000, "CREATE_NO_WINDOW is what keeps it console-backed but silent"
    assert flags & 0x200, "keep the new process group (Ctrl+C isolation)"


# ---------------------------------------------------------------- v0.38.1 A5 / A12


def test_start_is_blocked_before_spawn_when_mac_binaries_are_quarantined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """带 com.apple.quarantine 的 python/java 一被 exec 就被 Gatekeeper SIGKILL，没有任何输出；此前用户要等满整个
    就绪预算才拿到一个指不到任何地方的 start_timeout。"""
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "_host_is_darwin", lambda: True)
    flagged = {"checked": ["/r/python3"], "flagged": ["/r/python3"], "fix": 'xattr -dr com.apple.quarantine "/r"'}
    monkeypatch.setattr(manager, "_quarantine_report", lambda manifest: flagged)
    seen: dict[str, object] = {}
    _stub_popen(monkeypatch, seen=seen)
    with pytest.raises(RuntimeInstallError) as excinfo:
        manager.start_local_services()
    assert excinfo.value.code == "runtime.start_blocked_quarantine"
    assert excinfo.value.details["quarantine"] == flagged and "xattr -dr" in excinfo.value.details["next_action"]
    assert "command" not in seen, "flagged 时绝不 spawn 启动器"


def test_start_failure_context_attaches_quarantine_and_the_launcher_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager_with_runtime(tmp_path)
    manifest = manager.load_installed_manifest()
    monkeypatch.setattr(manager, "_host_is_darwin", lambda: False)
    off_mac = manager._start_failure_context(manifest)
    assert "launcher_log" in off_mac and "quarantine" not in off_mac
    monkeypatch.setattr(manager, "_host_is_darwin", lambda: True)
    monkeypatch.setattr(manager, "_quarantine_report", lambda m: {"checked": [], "flagged": ["x"], "fix": "xattr -dr …"})
    on_mac = manager._start_failure_context(manifest)
    assert on_mac["quarantine"]["flagged"] == ["x"]

    def boom(manifest):  # noqa: ANN001
        raise OSError("xattr exploded")

    monkeypatch.setattr(manager, "_quarantine_report", boom)
    assert "quarantine" not in manager._start_failure_context(manifest), "附加现场绝不能把原错误换成别的错误"


def test_stop_reports_a_timeout_with_the_survivors_instead_of_hanging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """停脚本此前没有 timeout：它多等一轮，`uninstall --yes` / `runtime stop` 就无限期挂住。"""
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda manifest=None: _endpoints(verdict="ours"))
    seen: dict[str, object] = {}

    def fake_run(command, **kwargs):  # noqa: ANN001
        seen["timeout"] = kwargs.get("timeout")
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout") or 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("horosa_skill.runtime.manager.port_holders", lambda port: [{"pid": 4242, "command": "java -jar app.jar"}])
    result = manager.stop_local_services()
    assert seen["timeout"] == 30.0, "max(30, runtime_start_timeout) 且 ≤ 180"
    assert result["ok"] is False and result["code"] == "runtime.stop_timeout"
    assert [entry["port"] for entry in result["survivors"]] == [manager.settings.local_backend_port, manager.settings.local_chart_port]
    assert result["survivors"][0]["holders"][0]["pid"] == 4242
    assert manager.load_runtime_state()["status"] == "stop_requested"


def test_launcher_patch_write_failure_is_a_structured_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """v0.38.1 A15：runtime 目录只读 / 属于别的用户时，补丁写入失败此前是裸 PermissionError traceback。"""
    manager = _manager_with_runtime(tmp_path)
    script = tmp_path / "start_horosa_local.sh"
    script.write_text(
        '#!/usr/bin/env bash\n'
        'ROOT="$(cd "$(dirname "$0")" && pwd)"\n'
        'reclaim_stale_port() {\n'
        '  case "x" in\n'
        '    y)\n'
        '        kill -9 "${pid}" >/dev/null 2>&1 && killed=1 ;;\n'
        '  esac\n'
        '}\n'
        'java -Dhorosa.runtime.owner=horosa-skill -jar app.jar\n',
        encoding="utf-8",
    )
    original = script.read_text(encoding="utf-8")
    real_write_text = Path.write_text

    def failing_write_text(self, *args, **kwargs):  # noqa: ANN001, ANN002
        if self == script:
            raise PermissionError(13, "Permission denied", str(self))
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", failing_write_text)
    with pytest.raises(RuntimeInstallError) as excinfo:
        manager._patch_mac_launcher(script)
    assert excinfo.value.code == "runtime.launcher_patch_write_failed"
    assert excinfo.value.details["path"] == str(script) and "PermissionError" in excinfo.value.details["error"]
    assert script.read_text(encoding="utf-8") == original
    monkeypatch.undo()
    assert manager._patch_mac_launcher(script) is True, "同一脚本在可写时必须能打上补丁（证明合成脚本满足全部锚点）"


# ---------------------------------------------------------------- v0.38.1 R3：升级就地


def _archive_of(tmp_path: Path) -> str:
    return str(tmp_path / "runtime-payload.tar.gz")


def test_install_over_a_running_runtime_stops_swaps_and_restarts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """旧 install() 的顺序是 ["swap"]：直接 replace + rmtree —— Windows 上 WinError 32/5，macOS 上旧进程继续从
    已删路径服务、新载荷永远不启动。新顺序必须是 stop → swap → start。"""
    manager = _manager_with_runtime(tmp_path)
    order: list[str] = []
    monkeypatch.setattr(manager, "endpoint_identities", lambda manifest=None, endpoints=None: _endpoints(verdict="ours"))
    monkeypatch.setattr(manager, "stop_local_services", lambda force=False, **kwargs: (order.append("stop"), {"ok": True})[1])
    real_apply = manager._apply_runtime_overrides

    def apply(manifest):  # noqa: ANN001
        order.append("swap")
        return real_apply(manifest)

    monkeypatch.setattr(manager, "_apply_runtime_overrides", apply)
    monkeypatch.setattr(manager, "start_local_services", lambda wait_seconds=None: (order.append("start"), {"ok": True, "already_running": False})[1])
    result = manager.install(archive=_archive_of(tmp_path), force=True)
    assert order == ["stop", "swap", "start"]
    assert result["ok"] and result["changed"] and result["stopped_before_swap"] is True
    assert result["restarted"] == {"ok": True, "starting": False, "already_running": False}


def test_install_over_a_stopped_runtime_neither_stops_nor_restarts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda manifest=None, endpoints=None: _endpoints(verdict="ours", reachable=False))

    def must_not(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("nothing was running; stop/start must not be called")

    monkeypatch.setattr(manager, "stop_local_services", must_not)
    monkeypatch.setattr(manager, "start_local_services", must_not)
    result = manager.install(archive=_archive_of(tmp_path), force=True)
    assert result["stopped_before_swap"] is False and result["restarted"] is None


def test_install_refuses_to_replace_a_runtime_someone_else_is_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """可达但不是我们起的（用户的桌面端 / 另一实例 / 只有 app 标记）→ 拒绝；`--force` 不得覆盖。"""
    manager = _manager_with_runtime(tmp_path)
    marker = manager.current_dir / "MARKER"
    marker.write_text("keep", encoding="utf-8")
    # 让已装清单与归档清单不相等，否则 force=False 会在归属检查之前就以「未变化」返回。
    manifest_path = manager.current_dir / "runtime-manifest.json"
    installed = json.loads(manifest_path.read_text(encoding="utf-8"))
    installed["version"] = "1.0.0"
    manifest_path.write_text(json.dumps(installed), encoding="utf-8")
    monkeypatch.setattr(manager, "endpoint_identities", lambda manifest=None, endpoints=None: _endpoints(verdict="foreign"))

    def must_not_stop(force=False):  # noqa: ANN001
        raise AssertionError("must never stop a stranger")

    monkeypatch.setattr(manager, "stop_local_services", must_not_stop)
    for force in (False, True):
        with pytest.raises(RuntimeInstallError) as excinfo:
            manager.install(archive=_archive_of(tmp_path), force=force)
        assert excinfo.value.code == "runtime.install_refused_running_foreign", force
        assert excinfo.value.details["force_ignored"] is True
        assert "HOROSA_PORTS=auto" in excinfo.value.details["next_action"]
    assert marker.read_text(encoding="utf-8") == "keep", "current/ 必须一字不动"
    assert not (manager.runtime_root / "previous").exists()


def test_install_stop_failure_leaves_current_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager_with_runtime(tmp_path)
    marker = manager.current_dir / "MARKER"
    marker.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(manager, "endpoint_identities", lambda manifest=None, endpoints=None: _endpoints(verdict="ours"))
    monkeypatch.setattr(manager, "stop_local_services", lambda force=False, **kwargs: {"ok": False, "code": "runtime.stop_timeout", "survivors": []})
    with pytest.raises(RuntimeInstallError) as excinfo:
        manager.install(archive=_archive_of(tmp_path), force=True)
    assert excinfo.value.code == "runtime.install_stop_failed"
    assert excinfo.value.details["stop"]["code"] == "runtime.stop_timeout"
    assert marker.exists()


def test_previous_dir_cleanup_failure_is_a_warning_not_a_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows 常见：句柄未释放时旧目录删不掉。新载荷已就位 → ok + warning，不回滚、不报错。"""
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda manifest=None, endpoints=None: _endpoints(verdict="ours", reachable=False))

    def locked_rmtree(path: Path) -> None:
        raise PermissionError(32, "The process cannot access the file because it is being used by another process", str(path))

    monkeypatch.setattr("horosa_skill.runtime.manager._rmtree_force", locked_rmtree)
    result = manager.install(archive=_archive_of(tmp_path), force=True)
    assert result["ok"] is True and result["changed"] is True
    assert [w["code"] for w in result["warnings"]] == ["runtime.previous_cleanup_deferred"]
    assert (manager.runtime_root / "previous").exists() and manager.current_dir.exists()
    assert manager.doctor()["previous_dir"] == str(manager.runtime_root / "previous")


def test_locked_previous_dir_aborts_before_touching_current(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager_with_runtime(tmp_path)
    stale = manager.runtime_root / "previous" / "stale.txt"
    stale.parent.mkdir()
    stale.write_text("old", encoding="utf-8")
    marker = manager.current_dir / "MARKER"
    marker.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(manager, "endpoint_identities", lambda manifest=None, endpoints=None: _endpoints(verdict="ours", reachable=False))
    monkeypatch.setattr("horosa_skill.runtime.manager._rmtree_force", lambda path: (_ for _ in ()).throw(PermissionError(5, "Access is denied", str(path))))
    monkeypatch.setattr("horosa_skill.runtime.manager.port_holders", lambda port: [{"pid": 7, "command": "java"}])
    with pytest.raises(RuntimeInstallError) as excinfo:
        manager.install(archive=_archive_of(tmp_path), force=True)
    assert excinfo.value.code == "runtime.install_previous_locked"
    assert excinfo.value.details["holders"][0]["holders"][0]["pid"] == 7
    assert marker.exists() and stale.exists()


def test_rmtree_force_clears_read_only_bits(tmp_path: Path) -> None:
    import stat

    from horosa_skill.runtime.manager import _rmtree_force

    victim = tmp_path / "ro"
    victim.mkdir()
    file = victim / "f.txt"
    file.write_text("x", encoding="utf-8")
    file.chmod(stat.S_IREAD)
    _rmtree_force(victim)
    assert not victim.exists()


def test_restart_failure_after_a_successful_swap_is_a_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda manifest=None, endpoints=None: _endpoints(verdict="ours"))
    monkeypatch.setattr(manager, "stop_local_services", lambda force=False, **kwargs: {"ok": True})

    def failing_start(wait_seconds=None):  # noqa: ANN001
        raise RuntimeInstallError("port taken", code="runtime.port_conflict_foreign", details={})

    monkeypatch.setattr(manager, "start_local_services", failing_start)
    result = manager.install(archive=_archive_of(tmp_path), force=True)
    assert result["ok"] is True and result["restarted"]["ok"] is False and result["restarted"]["code"] == "runtime.port_conflict_foreign"
    assert [w["code"] for w in result["warnings"]] == ["runtime.restart_after_upgrade_failed"]


# ---------------------------------------------------------------- v0.38.1 B3：R1 下载证据 / R14 挂着客户端不停


def _serve_directory(directory: Path):
    import http.server
    import threading

    handler = type("_Quiet", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a, **k: None})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: handler(*a, directory=str(directory), **k))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_install_over_http_records_the_real_download(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    server = _serve_directory(archive.parent)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/{archive.name}"
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({"version": "1.2.3", "platforms": {"darwin-arm64": {"url": url, "sha256": "", "archive_type": "tar.gz"}}}), encoding="utf-8")
        settings = Settings(runtime_root=tmp_path / "rt", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_platform="darwin-arm64")
        result = HorosaRuntimeManager(settings).install(manifest_url=manifest.resolve().as_uri())
    finally:
        server.shutdown()
    download = result["download"]
    assert download["bytes"] == archive.stat().st_size and download["url"] == url
    assert download["mirror_used"] is False and download["resumed_from"] == 0 and download["seconds"] >= 0
    assert (result["asset"] or {}).get("url") == url


def test_install_from_a_local_archive_records_no_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda manifest=None, endpoints=None: _endpoints(verdict="ours", reachable=False))
    assert manager.install(archive=str(tmp_path / "runtime-payload.tar.gz"), force=True)["download"] is None


def test_stop_is_refused_while_another_client_is_attached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R14：别的 MCP 客户端还挂着 → `runtime stop` 拒绝；`--force` / `ignore_clients`（restart、升级换目录）才停；死掉的登记不拦。"""
    import sys

    from horosa_skill.runtime import registry

    manager = _manager_with_runtime(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda manifest=None, endpoints=None: _endpoints(verdict="ours"))
    client = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        registry.attach_client(manager.settings.runtime_state_path, pid=client.pid, transport="stdio")

        def must_not_run(*args, **kwargs):  # noqa: ANN002, ANN003
            raise AssertionError("the stop script must not run while a live client is attached")

        monkeypatch.setattr(subprocess, "run", must_not_run)
        refused = manager.stop_local_services()
        assert refused["refused"] is True and refused["code"] == "runtime.stop_refused_clients_attached"
        assert str(client.pid) in refused["clients"] and "--force" in refused["next_action"]

        class _Done:
            returncode = 0
            stdout = ""
            stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Done())
        monkeypatch.setattr(manager, "_wait_for_service_state", lambda **kwargs: {"ready": True, "endpoints": []})
        assert manager.stop_local_services(force=True)["ok"] is True
        assert manager.stop_local_services(ignore_clients=True)["ok"] is True
    finally:
        client.kill()
        client.wait(timeout=30)
    # 客户端死了 → 登记不算数 → 不再拒绝
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Done())
    assert manager.stop_local_services().get("refused") is not True
