"""下载与清单的完整性（docs/LESSONS.md v0.50.0-dev「断点按文件名续、清单没摘要就不校验」）。

  · C-15 / E-15：清单条目没有 sha256 时，走网络的下载此前**一声不吭地不校验**；现在拒绝，除非用户 `--sha256` 自己给摘要。
    清单与归档都在本机时放行，但结果里明说没校验。
  · E-09：断点按文件名存 —— 同名的另一份内容的半截会被续上；没有 If-Range；续出来不对就算源坏了；有进展的断线也吃重试次数；
    两个 install 同时下同一个文件互相踩。
  · E-15：本地清单不是 JSON 时是 JSONDecodeError traceback。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from test_runtime_manager import (  # noqa: F401 - _managed_mode 是 autouse fixture
    _managed_mode,
    create_runtime_archive,
)
from typer.testing import CliRunner

from horosa_skill.config import Settings
from horosa_skill.errors import (
    RuntimeInstallError,
    RuntimeValidationError,
    recovery_for,
)
from horosa_skill.runtime import HorosaRuntimeManager, pidlock

URL = "https://example.com/releases/download/v9/payload.tar.gz"
MANIFEST_URL = "https://example.com/releases/latest/download/runtime-manifest.json"
BODY = bytes(range(256)) * 400
BODY_SHA = hashlib.sha256(BODY).hexdigest()


def _manager(tmp_path: Path, **extra: Any) -> HorosaRuntimeManager:
    settings = Settings(runtime_root=tmp_path / "rt", data_dir=tmp_path / "data", runtime_platform="darwin-arm64",
                        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", **extra)
    manager = HorosaRuntimeManager(settings)
    manager._last_download = None
    return manager


def _transport(monkeypatch: pytest.MonkeyPatch, handler: Any) -> list[tuple[str, dict[str, str]]]:
    seen: list[tuple[str, dict[str, str]]] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), {k.lower(): v for k, v in request.headers.items()}))
        return handler(request)

    real_client = httpx.Client

    def patched(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(recording)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", patched)
    monkeypatch.setattr("horosa_skill.runtime.manager.time.sleep", lambda seconds: None)
    return seen


def _ranged(request: httpx.Request, body: bytes = BODY, etag: str = '"v1"') -> httpx.Response:
    header = request.headers.get("range")
    if not header:
        return httpx.Response(200, content=body, headers={"ETag": etag})
    if request.headers.get("if-range") not in (None, etag):
        return httpx.Response(200, content=body, headers={"ETag": etag})  # 资源变了：整份
    start = int(header.split("=")[1].rstrip("-"))
    if start >= len(body):
        return httpx.Response(416, headers={"Content-Range": f"bytes */{len(body)}"})
    return httpx.Response(206, content=body[start:], headers={"ETag": etag})


def _seed_partial(manager: HorosaRuntimeManager, data: bytes, *, sha: str | None = BODY_SHA, etag: str | None = '"v1"') -> Path:
    part, sidecar, _ = manager._partial_paths(URL, sha)
    part.parent.mkdir(parents=True, exist_ok=True)
    part.write_bytes(data)
    sidecar.write_text(json.dumps({"source": URL, "url": URL, "etag": etag, "last_modified": None,
                                   "length": len(BODY), "sha256": sha}), encoding="utf-8")
    return part


# ── C-15：没有摘要不装（走网络时）──────────────────────────────────────────────


def _remote_manifest(sha: str = "") -> dict[str, Any]:
    return {"version": "9.0.0", "platforms": {"darwin-arm64": {"url": URL, "sha256": sha, "archive_type": "tar.gz"}}}


def test_a_remote_manifest_without_a_digest_is_refused_before_downloading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _transport(monkeypatch, lambda request: httpx.Response(200, json=_remote_manifest()) if "manifest" in str(request.url) else _ranged(request))
    manager = _manager(tmp_path)

    with pytest.raises(RuntimeValidationError) as excinfo:
        manager.install(manifest_url=MANIFEST_URL)

    error = excinfo.value
    assert error.code == "runtime.install_sha256_missing" and error.details["asset_url"] == URL
    assert " / " in str(error) and "--sha256" in str(error)
    assert [url for url, _ in seen] == [MANIFEST_URL], "一个字节的归档都不该下"
    assert recovery_for(error.code, error.details)["agent_recovery"]["next_action"].startswith("pass_sha256")
    assert not manager.current_dir.exists()


def test_a_digest_the_user_vouches_for_lets_it_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = create_runtime_archive(tmp_path)
    payload, digest = archive.read_bytes(), hashlib.sha256(archive.read_bytes()).hexdigest()
    _transport(monkeypatch, lambda request: httpx.Response(200, json=_remote_manifest()) if "manifest" in str(request.url) else _ranged(request, payload))
    manager = _manager(tmp_path)
    monkeypatch.setattr(manager, "endpoint_identities", lambda endpoints=None: [])

    result = manager.install(manifest_url=MANIFEST_URL, sha256=digest)

    assert result["ok"] is True and result["sha256_verified"] is True and result["archive_sha256"] == digest


def test_a_local_manifest_and_archive_install_unverified_and_say_so(tmp_path: Path) -> None:
    archive = create_runtime_archive(tmp_path)
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"version": "1.2.3", "platforms": {"darwin-arm64": {
        "url": archive.resolve().as_uri(), "sha256": "", "archive_type": "tar.gz"}}}), encoding="utf-8")
    manager = _manager(tmp_path)

    result = manager.install(manifest_url=manifest.resolve().as_uri())

    assert result["ok"] is True and result["sha256_verified"] is False
    assert [w["code"] for w in result["warnings"]] == ["runtime.install_unverified"]
    again = manager.install(manifest_url=manifest.resolve().as_uri())
    assert again["skipped_download"] is True and again["warnings"] == [], "什么都不下载时没有东西要校验"


def test_a_local_manifest_pointing_at_the_network_is_still_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _transport(monkeypatch, _ranged)
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps(_remote_manifest()), encoding="utf-8")
    with pytest.raises(RuntimeValidationError) as excinfo:
        _manager(tmp_path).install(manifest_url=str(manifest))
    assert excinfo.value.code == "runtime.install_sha256_missing" and seen == []


# ── E-15：清单读不懂是一句话，不是 traceback ──────────────────────────────────


@pytest.mark.parametrize(("content", "reason_part"), [
    ("<html>login</html>", "HTML page"),
    ("", "empty"),
    ('{"message": "rate limited"}', "no `platforms`"),
    ("not json at all", "not JSON"),
])
def test_a_local_manifest_that_is_not_one_is_a_structured_error(tmp_path: Path, content: str, reason_part: str) -> None:
    manifest = tmp_path / "m.json"
    manifest.write_text(content, encoding="utf-8")
    with pytest.raises(RuntimeInstallError) as excinfo:
        _manager(tmp_path).install(manifest_url=manifest.resolve().as_uri())
    assert excinfo.value.code == "runtime.install_manifest_invalid"
    assert reason_part in excinfo.value.details["reason"] and " / " in str(excinfo.value)


def test_a_missing_local_manifest_is_a_structured_error(tmp_path: Path) -> None:
    with pytest.raises(RuntimeInstallError) as excinfo:
        _manager(tmp_path).install(manifest_url=str(tmp_path / "nope.json"))
    assert excinfo.value.code == "runtime.install_manifest_fetch_failed" and " / " in str(excinfo.value)


def test_cli_prints_the_manifest_error_not_a_traceback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill.surfaces import cli

    manifest = tmp_path / "m.json"
    manifest.write_text("<html>login</html>", encoding="utf-8")
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "rt"))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    result = CliRunner().invoke(cli.app, ["install", "--manifest-url", manifest.resolve().as_uri()])
    assert result.exit_code == 2 and "Traceback" not in result.stderr
    assert json.loads(result.stderr[result.stderr.index("{"):])["code"] == "runtime.install_manifest_invalid"


def test_a_remote_manifest_error_names_what_came_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _transport(monkeypatch, lambda request: httpx.Response(200, content=b"<html>hotel wifi</html>"))
    with pytest.raises(RuntimeInstallError) as excinfo:
        _manager(tmp_path)._read_json_location(MANIFEST_URL)
    assert excinfo.value.code == "runtime.install_manifest_fetch_failed"
    assert "HTML page" in str(excinfo.value) and "Expecting value" not in str(excinfo.value)


# ── E-09：断点按内容定名 ──────────────────────────────────────────────────────


def test_a_legacy_partial_with_the_same_file_name_is_not_resumed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """旧格式 `downloads/<文件名>.part`（别的版本 / 别的镜像留下的同名半截）：不续，顺手清掉。"""
    seen = _transport(monkeypatch, _ranged)
    manager = _manager(tmp_path)
    legacy = manager.runtime_root / "downloads" / "payload.tar.gz.part"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"x" * 5000)

    target = manager._download_with_resume(URL, tmp_path, expected_sha256=BODY_SHA)

    assert target.read_bytes() == BODY
    assert [headers.get("range") for _, headers in seen] == [None]
    assert not legacy.exists()


def test_a_partial_of_other_content_is_not_resumed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _transport(monkeypatch, _ranged)
    manager = _manager(tmp_path)
    other = "f" * 64
    part, sidecar, _ = manager._partial_paths(URL, BODY_SHA)
    part.parent.mkdir(parents=True)
    part.write_bytes(b"x" * 5000)
    sidecar.write_text(json.dumps({"source": URL, "sha256": other}), encoding="utf-8")  # 旁注说它是另一份内容

    assert manager._download_with_resume(URL, tmp_path, expected_sha256=BODY_SHA).read_bytes() == BODY
    assert [headers.get("range") for _, headers in seen] == [None]


def test_resume_sends_if_range_and_a_changed_resource_restarts_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _transport(monkeypatch, lambda request: _ranged(request, etag='"v2"'))
    manager = _manager(tmp_path)
    _seed_partial(manager, BODY[:1000], etag='"v1"')

    target = manager._download_with_resume(URL, tmp_path, expected_sha256=BODY_SHA)

    assert target.read_bytes() == BODY
    assert seen[0][1].get("range") == "bytes=1000-" and seen[0][1].get("if-range") == '"v1"'
    assert manager._last_download["bytes"] == len(BODY)


def test_a_resumed_file_that_fails_the_digest_gets_one_clean_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """续出来的不对，可能是前半截坏了（磁盘、上一次的镜像），不一定是源坏了：从头再下一次。"""
    seen = _transport(monkeypatch, _ranged)
    manager = _manager(tmp_path)
    _seed_partial(manager, b"\0" * 1000)  # 长度对、内容错

    target = manager._download_with_resume(URL, tmp_path, expected_sha256=BODY_SHA)

    assert target.read_bytes() == BODY
    assert [headers.get("range") for _, headers in seen] == ["bytes=1000-", None]


class _Drip(httpx.SyncByteStream):
    """给一段字节就断线。"""

    def __init__(self, data: bytes) -> None:
        self.data = data

    def __iter__(self):
        yield self.data
        raise httpx.RemoteProtocolError("peer closed connection")


def test_progressing_attempts_do_not_use_up_the_retries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """慢网上每次下一段就断：旧实现第三次断线就判失败，哪怕每次都在往前走。

    每段 > 1 MiB：下载按 1 MiB 一块落盘，断在一块之内的字节本来就会丢（真实归档 700 MB，无所谓）。"""
    body = bytes(range(256)) * (4096 * 6)  # 6 MiB
    digest = hashlib.sha256(body).hexdigest()
    step = len(body) // 5 + 1

    def handler(request: httpx.Request) -> httpx.Response:
        header = request.headers.get("range")
        start = int(header.split("=")[1].rstrip("-")) if header else 0
        status = 206 if start else 200
        if start + step >= len(body):
            return httpx.Response(status, content=body[start:], headers={"ETag": '"v1"'})
        return httpx.Response(status, stream=_Drip(body[start:start + step]), headers={"ETag": '"v1"'})

    seen = _transport(monkeypatch, handler)
    manager = _manager(tmp_path, runtime_download_attempts=2)

    target = manager._download_with_resume(URL, tmp_path, expected_sha256=digest)

    assert target.read_bytes() == body and len(seen) >= 4
    assert all(headers.get("range") for _, headers in seen[1:]), "每次都从断点接着下"


def test_fruitless_attempts_still_give_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    seen = _transport(monkeypatch, handler)
    with pytest.raises(RuntimeInstallError) as excinfo:
        _manager(tmp_path, runtime_download_attempts=2)._download_with_resume(URL, tmp_path, expected_sha256=BODY_SHA)
    assert excinfo.value.code == "runtime.install_download_failed" and len(seen) == 2


def test_a_second_download_of_the_same_content_waits_its_turn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """两个 install 同时下：旧实现后到的那个在挪文件时撞 FileNotFoundError（runtime.install_write_failed）。"""
    seen = _transport(monkeypatch, _ranged)
    manager = _manager(tmp_path)
    _part, _sidecar, lock = manager._partial_paths(URL, BODY_SHA)
    lock.parent.mkdir(parents=True)
    assert pidlock.try_pid_lock(lock, owner="runtime-download")  # 本进程持锁 = 一个活着的别的下载者
    try:
        with pytest.raises(RuntimeInstallError) as excinfo:
            manager._download_with_resume(URL, tmp_path, expected_sha256=BODY_SHA)
    finally:
        pidlock.release(lock)
    assert excinfo.value.code == "runtime.install_download_in_progress" and seen == []
    assert manager._download_with_resume(URL, tmp_path, expected_sha256=BODY_SHA).read_bytes() == BODY
    assert not lock.exists(), "下载完放锁"
