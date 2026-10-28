"""带标签 PDF（v0.45.1，reports/pdf_tagging.py）：报告 PDF 有结构树、语言、PDF/UA 标识，页面上一切内容要么在标签里要么是 Artifact。

结构检查在每台机器上跑（解开内容流数运算符）；veraPDF 的 PDF/UA-1 全量校验要 Java，`HOROSA_VERAPDF` 指向 veraPDF 可执行文件时才跑。
2026-10-27 在本机用 veraPDF 1.30.3 跑过：分析报告与排盘报告都 PASS ua1（docs/LESSONS.md v0.45.1-dev）。
"""
from __future__ import annotations

import base64
import os
import re
import subprocess
import zlib
from pathlib import Path

import pytest
from test_report_structure import _ai_report, _produced_cites
from test_user_knowledge_and_chart_report import _chart_run, _service

_PAINT = re.compile(rb"(?:^|\s)(Tj|TJ|'|\"|f\*?|S|B\*?|b\*?|Do|sh)(?=\s|$)")
_MARK_OPEN = re.compile(rb"\b(BDC|BMC)\b")


def _report(tmp_path: Path, **extra) -> bytes:
    service = _service(tmp_path)
    run = _chart_run(service)
    (first, _), (second, _) = _produced_cites(run)[:2]
    rendered = service.report_render({"run_id": run.memory_ref.run_id, "tool_name": "chart", "format": "pdf",
                                      "ai_report": _ai_report(first, second), **extra})
    return Path(rendered["artifact_path"]).read_bytes()


def _content_streams(pdf: bytes) -> list[bytes]:
    out = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\n?endstream", pdf, re.DOTALL):
        raw = match.group(1)
        if raw.rstrip().endswith(b"~>"):  # reportlab 页内容：ASCII85 套 Flate
            try:
                raw = base64.a85decode(raw.rstrip()[:-2].replace(b"\n", b""))
            except ValueError:
                continue
        try:
            data = zlib.decompress(raw)
        except zlib.error:
            data = raw
        # 页面内容流是纯 ASCII 运算符；字体等二进制流里碰巧也有「BT」字节，排除掉。
        if data.isascii() and (b" BDC" in data or b"BT" in data or b" re " in data):
            out.append(data)
    return out


def _untagged_paint(stream: bytes) -> list[bytes]:
    """标记内容之外的绘制运算符（文字 / 填充 / 描边 / 图像）。字符串里的括号内容先抹掉，免得把正文当运算符。"""
    cleaned = re.sub(rb"\((?:\\.|[^\\)])*\)", b"()", stream)
    depth, bad = 0, []
    for line in cleaned.split(b"\n"):
        for token in re.findall(rb"\S+", line):
            if token in (b"BDC", b"BMC"):
                depth += 1
            elif token == b"EMC":
                depth -= 1
            elif depth == 0 and _PAINT.fullmatch(b" " + token):
                bad.append(line[:80])
    return bad


def test_report_pdf_has_a_structure_tree_language_and_ua_identifier(tmp_path: Path) -> None:
    pdf = _report(tmp_path)
    assert b"/StructTreeRoot" in pdf and b"/MarkInfo" in pdf and b"/Marked true" in pdf
    assert b"/Lang (zh-CN)" in pdf and b"/DisplayDocTitle true" in pdf
    # 嵌入了 TrueType 字体才声称 PDF/UA-1；CI 的 Linux 镜像没有中文 TTF，走 CID 退回那一支（下一个测试两支都钉住）。
    assert (b"<pdfuaid:part>1</pdfuaid:part>" in pdf) == (b"/FontFile2" in pdf)
    for tag in (b"/S /Document", b"/S /H1", b"/S /P", b"/S /Table", b"/S /TH", b"/S /TD", b"/S /Figure", b"/S /Link"):
        assert tag in pdf, tag
    assert b"/Alt (" in pdf or b"/Alt <" in pdf  # 盘图有替代文字
    assert b"/StructParent " in pdf and b"/OBJR" in pdf  # 链接注释进了结构树


def test_cid_fallback_keeps_the_tags_but_drops_the_ua_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """没有可嵌入的中文 TTF（如 CI 的 Ubuntu）→ 退回不嵌入的 CID 字体：结构树照写，但不能声称 PDF/UA-1（UA 要求字体嵌入）。"""
    from horosa_skill.reports import renderers

    monkeypatch.setattr(renderers, "_PDF_FONT_CANDIDATES", {"sc": [], "tc": []})
    pdf = _report(tmp_path)
    assert b"/STSong-Light" in pdf and b"/FontFile2" not in pdf
    assert b"/StructTreeRoot" in pdf and b"/Lang (zh-CN)" in pdf
    assert b"pdfuaid" not in pdf


def test_every_painted_thing_is_tagged_or_an_artifact(tmp_path: Path) -> None:
    streams = _content_streams(_report(tmp_path))
    assert streams
    offenders = [line for stream in streams for line in _untagged_paint(stream)]
    assert offenders == [], offenders[:5]
    for stream in streams:  # 标记成对
        assert len(_MARK_OPEN.findall(stream)) == stream.count(b"EMC")


@pytest.mark.skipif(not os.environ.get("HOROSA_VERAPDF"), reason="HOROSA_VERAPDF 未指向 veraPDF（需要 Java）")
def test_verapdf_says_pdf_ua_1(tmp_path: Path) -> None:
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(_report(tmp_path / "work"))
    result = subprocess.run([os.environ["HOROSA_VERAPDF"], "-f", "ua1", "--format", "text", str(pdf)],
                            capture_output=True, text=True, timeout=300, check=False)
    assert result.stdout.startswith("PASS"), result.stdout + result.stderr
