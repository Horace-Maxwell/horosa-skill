"""Windows 归属证据不经代码页（v0.38.1 A1）。

事故形状：Windows PowerShell 5.1 往管道写 **OEM 代码页**（en-US cp437 / zh-CN cp936），而 procs 按 UTF-8 解 ——
`C:\\Users\\张三\\…` 回来是 U+FFFD 或 `??`，与 Python 侧的 Unicode 路径永远不相等 → 用户名带中文/重音的
**健康**机器被判 `port_conflict_foreign` / `stop_refused_foreign`。修法：映像路径走 ctypes（无编码），
PowerShell 只搬 UTF-8 字节的 base64，tasklist 按 oem 解。
"""
from __future__ import annotations

import base64
import os

import pytest

from horosa_skill.runtime import identity, procs

CJK_ROOT = r"C:\Users\张三\AppData\Local\Horosa\runtime"
CJK_COMMAND = (
    f'"{CJK_ROOT}\\current\\runtime\\windows\\java\\bin\\java.exe" -Dhorosa.runtime.owner=horosa '
    f"-Dhorosa.runtime.root={CJK_ROOT} -jar app.jar"
)


def test_powershell_route_moves_utf8_bytes_as_base64(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run_text(cmd: list[str], timeout: float, *, encoding: str = "utf-8") -> str:
        seen["cmd"], seen["encoding"] = cmd, encoding
        return base64.b64encode(CJK_COMMAND.encode("utf-8")).decode("ascii")

    monkeypatch.setattr(procs, "_run_text", fake_run_text)
    assert procs._powershell_command_line(4242) == CJK_COMMAND
    script = str(seen["cmd"][-1])
    assert "ToBase64String" in script and "UTF8.GetBytes" in script, "PowerShell 只许搬字节，不许吐文本"
    assert seen["encoding"] == "ascii", "base64 是纯 ASCII，解码与控制台代码页彻底无关"
    assert identity._command_says_ours(CJK_COMMAND, CJK_ROOT)


def test_old_utf8_decoding_of_oem_bytes_could_never_match_the_root() -> None:
    """负向对照：旧实现（PowerShell 吐文本 → Python 按 UTF-8 解）在 zh-CN 与 en-US 两种 OEM 代码页下都判不出归属。"""
    zh_cn = CJK_COMMAND.encode("cp936").decode("utf-8", errors="replace")
    assert "\ufffd" in zh_cn
    assert not identity._command_says_ours(zh_cn, CJK_ROOT)
    en_us = CJK_COMMAND.encode("cp437", errors="replace").decode("utf-8", errors="replace")
    assert "??" in en_us
    assert not identity._command_says_ours(en_us, CJK_ROOT)


def test_tasklist_fallback_is_decoded_as_oem(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    class _Done:
        stdout = '"java.exe","4242","Console","1","123,456 K"\n'

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        seen.update(kwargs)
        return _Done()

    monkeypatch.setattr(procs.subprocess, "run", fake_run)
    assert procs._tasklist_image_name(4242) == "java.exe"
    assert seen["encoding"] == "oem" and seen["errors"] == "replace"


def test_run_text_treats_a_missing_codec_as_no_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """POSIX 没有 `oem` codec：LookupError 必须被吞成「查不到」，绝不炸进归属判定。"""

    def boom(*args, **kwargs):  # noqa: ANN001, ANN002
        raise LookupError("unknown encoding: oem")

    monkeypatch.setattr(procs.subprocess, "run", boom)
    assert procs._run_text(["tasklist"], 1.0, encoding="oem") == ""


@pytest.mark.skipif(os.name == "nt", reason="POSIX 上映像路径交给 ps -o command=")
def test_process_image_path_is_none_off_windows() -> None:
    assert procs.process_image_path(os.getpid()) is None


def test_image_under_the_runtime_root_is_strong_evidence() -> None:
    assert identity._image_says_ours("/r/current/runtime/mac/java/bin/java", "/r")
    assert identity._image_says_ours(r"C:\R\current\runtime\windows\java\bin\java.exe", r"C:\R")
    assert not identity._image_says_ours("/r2/current/java", "/r")
    assert not identity._image_says_ours("/r", "/r")
    assert not identity._image_says_ours(None, "/r")
    assert "process.image_under_runtime_root" in identity.EndpointIdentity._STRONG_EVIDENCE
    verdict = identity.EndpointIdentity("ours", "process.image_under_runtime_root", "http://127.0.0.1:9999")
    assert verdict.started_by_us is True


def test_windows_image_compare_ignores_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity.os, "name", "nt")
    assert identity._image_says_ours(r"c:\users\ZHANG\horosa\CURRENT\java.exe", r"C:\Users\zhang\Horosa")


def test_holder_evidence_asks_the_image_first_and_never_spawns_powershell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity, "process_image_path", lambda pid: "/r/current/runtime/mac/java/bin/java")

    def must_not_run(pid):  # noqa: ANN001
        raise AssertionError("process_command must not run when the image already answers")

    monkeypatch.setattr(identity, "process_command", must_not_run)
    evidence, image, command = identity._holder_evidence(7, "/r", need_name=True)
    assert evidence == "process.image_under_runtime_root" and image.endswith("java") and command is None


def test_holder_evidence_falls_back_to_the_command_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity, "process_image_path", lambda pid: None)
    monkeypatch.setattr(identity, "process_command", lambda pid: "java -Dhorosa.runtime.root=/r -jar app.jar")
    evidence, image, command = identity._holder_evidence(7, "/r", need_name=False)
    assert evidence == "process.command_matches_runtime_root" and image is None and command


def test_a_foreign_image_is_not_named_unless_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    """升级路径（need_name=False）只求强证据：映像不是我们的就到此为止，不为点名再起一次 PowerShell。"""
    monkeypatch.setattr(identity, "process_image_path", lambda pid: "/usr/bin/python3")

    def must_not_run(pid):  # noqa: ANN001
        raise AssertionError("no PowerShell when nobody asked for a name")

    monkeypatch.setattr(identity, "process_command", must_not_run)
    assert identity._holder_evidence(7, "/r", need_name=False) == (None, "/usr/bin/python3", None)


def test_classify_endpoint_promotes_image_evidence_to_stoppable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity, "probe_identity", lambda url: None)
    monkeypatch.setattr(identity, "listener_pids", lambda port: [77])
    monkeypatch.setattr(identity, "process_image_path", lambda pid: "/r/current/runtime/mac/python/bin/python3")

    def must_not_run(pid):  # noqa: ANN001
        raise AssertionError("image answered; no command-line lookup expected")

    monkeypatch.setattr(identity, "process_command", must_not_run)
    verdict = identity.classify_endpoint("http://127.0.0.1:8899", runtime_root="/r")
    assert (verdict.verdict, verdict.evidence, verdict.started_by_us) == ("ours", "process.image_under_runtime_root", True)
    assert verdict.holders[0]["image"].endswith("python3")


def test_classify_endpoint_names_a_stranger_by_its_image_when_the_command_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity, "probe_identity", lambda url: None)
    monkeypatch.setattr(identity, "listener_pids", lambda port: [78])
    monkeypatch.setattr(identity, "process_image_path", lambda pid: r"C:\Program Files\Other\other.exe")
    monkeypatch.setattr(identity, "process_command", lambda pid: None)
    verdict = identity.classify_endpoint("http://127.0.0.1:8899", runtime_root=r"C:\Users\me\Horosa")
    assert verdict.verdict == "foreign" and verdict.holders[0]["command"].endswith("other.exe")
