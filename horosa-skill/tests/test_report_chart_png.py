"""报告 format=png（v0.48.0，reports/chart_png.py）：盘图本身画成 PNG、一张盘一个文件；MCP 结果按上限内嵌 image 内容块。

平台无关：CI 的 Linux 没有中文 TrueType、Windows 有微软雅黑、macOS 有宋体。和 test_pdf_tagged 一样钉字体候选表
（renderers._PDF_FONT_CANDIDATES）：
- 落盘 / 尺寸 / 多文件 / 内嵌这些机制用例钉 reportlab 自带的 Vera（每个平台都有），再把缺字检查换掉——Vera 只有拉丁字，
  缺字闸自己另有用例（钉 Vera、不换检查 → 必拒）；
- 「本机字体」那一条按本机实际情况断言：有中文 TTF 就必须画成且不缺字，没有就必须拒绝。
MCP 内嵌用例不画盘：直接造 PNG 文件，只测结果里的 image / resource_link 块与上限。
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import os
from pathlib import Path

import pytest
import reportlab
from fakes import FakeClient, FakeJsClient
from PIL import Image

from horosa_skill.config import Settings
from horosa_skill.errors import RECOVERY_TABLE, ToolValidationError, classify_code, recovery_for
from horosa_skill.memory.store import MemoryStore
from horosa_skill.reports import chart_png, renderers
from horosa_skill.reports.figures import extract_figures, grid_position
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads
from horosa_skill.textscript import SIMPLIFIED
from horosa_skill.textscript.localize import unclassified_text_paths

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
VERA = Path(reportlab.__file__).parent / "fonts"
GRIDS = json.loads((Path(__file__).parent / "fixtures" / "chart_png_live.json").read_text(encoding="utf-8"))["cases"]


@pytest.fixture
def latin_font(monkeypatch: pytest.MonkeyPatch) -> None:
    pair = (str(VERA / "Vera.ttf"), None, str(VERA / "VeraBd.ttf"), None)
    monkeypatch.setattr(renderers, "_PDF_FONT_CANDIDATES", {"sc": [pair], "tc": [pair]})


@pytest.fixture
def glyphs_ok(monkeypatch: pytest.MonkeyPatch, latin_font: None) -> None:
    monkeypatch.setattr(chart_png, "missing_glyphs", lambda texts: [])


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt", data_dir=tmp_path / "data")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _run(service: HorosaSkillService, tool: str) -> str:
    env = service.run_tool(tool, build_sample_payloads()[tool], save_result=True)
    assert env.ok and env.memory_ref
    return env.memory_ref.run_id


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data.startswith(PNG_SIGNATURE)
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == "PNG"
        return image.size


def test_one_png_per_figure_with_a_valid_signature_dimensions_and_file_cards(tmp_path: Path, glyphs_ok: None) -> None:
    service = _service(tmp_path)
    run_id = _run(service, "solarreturn")  # 返照盘 + 本命盘 = 两张
    result = service.report_render({"run_id": run_id, "format": "png", "output_path": "sr.png"})
    paths = [Path(card["path"]) for card in result["files"]]
    assert [p.name for p in paths] == ["sr_1.png", "sr_2.png"] and result["file"] == result["files"][0]
    assert [f["title"] for f in result["figures"]] == ["太阳返照盘", "本命盘"]
    for card, figure in zip(result["files"], result["figures"]):
        width, height = _png_size(Path(card["path"]))
        assert (width, height) == (figure["width"], figure["height"]) and max(width, height) <= chart_png.PNG_LONG_EDGE_MAX
        assert min(width, height) >= 600  # 不是缩略图
        assert card["mime"] == "image/png" and card["sha256"] == hashlib.sha256(Path(card["path"]).read_bytes()).hexdigest()
    assert result["kind"] == "report_png" and result["summary"][0].startswith("已生成 PNG 盘图 2 张")
    stored = service.store.query_runs(run_id=run_id, include_payload=False, limit=1)[0]["artifacts"]
    assert sum(1 for a in stored if a.get("kind") == "report_png") == 2
    assert unclassified_text_paths(result) == []


def test_png_obeys_the_output_path_guard(tmp_path: Path, glyphs_ok: None) -> None:
    service = _service(tmp_path)
    run_id = _run(service, "solarreturn")
    outside = tmp_path / "elsewhere" / "chart.png"
    with pytest.raises(ToolValidationError) as refused:
        service.report_render({"run_id": run_id, "format": "png", "output_path": str(outside)})
    assert refused.value.code == "report.output_path_not_allowed"
    assert not outside.parent.exists() and not list((tmp_path / "runs").rglob("*.png"))


def test_png_figures_are_the_chart_report_figures(tmp_path: Path) -> None:
    """PNG 与 PDF 排盘报告画的是同一组规格：chart_source / build_figures 与 build_document(style=chart) 不许各算各的。"""
    service = _service(tmp_path)
    for tool in ("chart", "solarreturn", "germany"):
        run, source = service._load_report_source(_run(service, tool), None)  # noqa: SLF001
        document = service.report_builder.build_document(run=run, source_artifact=source, language="zh-CN", style="chart")
        assert service.report_builder.build_figures(run=run, source_artifact=source) == document["figures"] != []


def test_png_refuses_a_run_without_a_figure_and_writes_nothing(tmp_path: Path, glyphs_ok: None) -> None:
    service = _service(tmp_path)
    run_id = _run(service, "nongli_time")  # 农历换算没有盘式
    with pytest.raises(ToolValidationError) as refused:
        service.report_render({"run_id": run_id, "format": "png"})
    assert refused.value.code == "report.no_chart_content" and refused.value.details["format"] == "png"
    assert not list((tmp_path / "runs").rglob("*.png"))
    # 八字自 v0.49.0 起有盘（只有 app 画法）。这里的假 JS 引擎画不了它：此前那张图被悄悄丢掉，PNG 回「这个技法没有盘式」；
    # 现在说的是哪张图、为什么没画出来（v0.50.0，report.chart_figure_unavailable）。
    with pytest.raises(ToolValidationError) as undrawn:
        service.report_render({"run_id": _run(service, "bazi_birth"), "format": "png"})
    assert undrawn.value.code == "report.chart_figure_unavailable" and "八字命盘没有画出" in str(undrawn.value)
    assert not list((tmp_path / "runs").rglob("*.png"))
    # 同一个码的 prompt_to_user 此前只讲「这个工具没有盘面，对八字等起盘类技法出」——八字 PNG 被拒时自相矛盾。
    prompt = RECOVERY_TABLE["report.no_chart_content"]["prompt_to_user"]
    assert "PNG" in prompt and "PDF" in prompt


def test_png_refuses_without_a_cjk_truetype_font(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """没有可用的 TrueType（只剩 reportlab 内置 CID 字体，CI 的 Linux 就是这样）：拒绝，不画方块，不写文件。"""
    monkeypatch.setattr(renderers, "_PDF_FONT_CANDIDATES", {"sc": [], "tc": []})
    service = _service(tmp_path)
    run_id = _run(service, "chart")
    with pytest.raises(ToolValidationError) as refused:
        service.report_render({"run_id": run_id, "format": "png"})
    assert refused.value.code == "report.png_font_unavailable" and refused.value.details["fallback_format"] == "pdf"
    assert refused.value.details["missing_characters"] == []  # 是「没有字体」，不是「字体缺字」（两道闸各报各的原因）
    assert not list((tmp_path / "runs").rglob("*.png"))
    assert classify_code("report.png_font_unavailable") == ("environment", "exact")
    assert recovery_for("report.png_font_unavailable", {})["agent_recovery"]["next_action"] == "render_pdf_or_install_cjk_font"


def test_png_refuses_when_the_font_lacks_the_charts_glyphs(tmp_path: Path, latin_font: None) -> None:
    """有 TrueType 但缺字（Vera 只有拉丁字）：同样拒绝并列出缺的字——画出来就是方块。"""
    service = _service(tmp_path)
    run_id = _run(service, "chart")
    with pytest.raises(ToolValidationError) as refused:
        service.report_render({"run_id": run_id, "format": "png"})
    assert refused.value.code == "report.png_font_unavailable"
    missing = refused.value.details["missing_characters"]
    assert "上" in missing and "交" in missing  # 「上升」「北交」：中文盘名（列表按码位排、最多 40 个）
    assert missing and all(ord(ch) > 0x7F for ch in missing)  # 拉丁字 Vera 都有
    assert not list((tmp_path / "runs").rglob("*.png"))


def test_png_with_this_machines_fonts_draws_without_tofu_or_refuses(tmp_path: Path) -> None:
    """本机真实字体：有中文 TTF（macOS 宋体 / Windows 雅黑 / 装了 Noto CJK 的 Linux）→ 画成且零缺字；没有 → 拒绝。"""
    service = _service(tmp_path)
    run_id = _run(service, "chart")
    if renderers._drawing_font_files(SIMPLIFIED) is None:  # noqa: SLF001
        with pytest.raises(ToolValidationError) as refused:
            service.report_render({"run_id": run_id, "format": "png"})
        assert refused.value.code == "report.png_font_unavailable"
        return
    run, source = service._load_report_source(run_id, None)  # noqa: SLF001
    figures = service.report_builder.build_figures(run=run, source_artifact=source)
    fonts = renderers._drawing_font_files(SIMPLIFIED)  # noqa: SLF001
    from reportlab.lib import colors

    drawing = chart_png._figure_drawing(figures[0], *fonts["names"], colors)  # noqa: SLF001
    assert chart_png.missing_glyphs(chart_png._drawing_texts(drawing)) == []  # noqa: SLF001
    result = service.report_render({"run_id": run_id, "format": "png"})
    assert Path(result["artifact_path"]).read_bytes().startswith(PNG_SIGNATURE)


def test_png_titles_follow_the_output_script(tmp_path: Path, glyphs_ok: None) -> None:
    service = _service(tmp_path)
    run_id = _run(service, "chart")
    result = service.report_render({"run_id": run_id, "format": "png", "language": "zh-TW"})
    assert result["figures"][0]["title"] == "星盤"


def test_ai_report_is_not_used_or_written_back_for_png(tmp_path: Path, glyphs_ok: None) -> None:
    service = _service(tmp_path)
    run_id = _run(service, "chart")
    result = service.report_render({"run_id": run_id, "format": "png", "ai_answer_text": "盘面很好"})
    assert result["answer_writeback"] is None and "没有写回记忆" in result["warnings"][-1]
    assert not service.store.query_runs(run_id=run_id, limit=1)[0].get("ai_answer_text")


@pytest.mark.parametrize("tool", sorted(GRIDS))
def test_grid_charts_put_every_palace_in_its_branch_or_gua_cell(tool: str, latin_font: None) -> None:
    """十二宫 / 九宫格子图：每格的标题画在 grid_position 给的格位里（与 PDF / DOCX 同一张格位表，不自己排）。"""
    from reportlab.graphics.shapes import String
    from reportlab.lib import colors

    (spec,) = extract_figures(tool, GRIDS[tool], tool)
    fonts = renderers._drawing_font_files(SIMPLIFIED)  # noqa: SLF001
    drawing = chart_png.grid_drawing(spec, 560.0, *fonts["names"], colors)
    n = 4 if spec["kind"] == "grid12" else 3
    rects = sorted({(round(s.x, 3), round(s.y, 3), round(s.width, 3), round(s.height, 3)) for s in drawing.contents
                    if type(s).__name__ == "Rect"})
    strings = [s for s in drawing.contents if isinstance(s, String)]
    cell_w = 560.0 / n
    for cell in spec["cells"]:
        row, col = grid_position(spec, cell)
        hits = [s for s in strings if s.text == cell["title"]]
        assert len(hits) == 1, cell["title"]
        x, y = hits[0].x, hits[0].y
        box = [r for r in rects if r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3] and abs(r[2] - cell_w) < 0.01]
        assert len(box) == 1, cell["title"]
        assert round((box[0][0] - 1.5) / cell_w) == col
        rows_from_top = sorted({r[1] + r[3] for r in rects if abs(r[2] - cell_w) < 0.01}, reverse=True)
        assert rows_from_top.index(box[0][1] + box[0][3]) == row
    if n == 4:  # 中宫标题画在中间 2×2
        center = [s for s in strings if s.text == spec["center"]["title"]]
        assert center and cell_w < center[0].x < 3 * cell_w


# ── MCP：image 内容块与上限 ─────────────────────────────────────────────────


def _server(tmp_path: Path):
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt", data_dir=tmp_path / "data")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    return create_mcp_server(service, settings), service


def _png_file(path: Path, size: int = 64, noise: bool = False) -> Path:
    image = Image.frombytes("RGB", (size, size), os.urandom(size * size * 3)) if noise else Image.new("RGB", (size, size), "white")
    image.save(path, format="PNG")
    return path


def _png_result(paths: list[Path]) -> dict:
    from horosa_skill.service.api.reports import _file_card

    cards = [_file_card(p, "png") for p in paths]
    return {"ok": True, "format": "png", "artifact_path": str(paths[0]), "file": cards[0], "files": cards,
            "summary": ["已生成 PNG 盘图"]}


def _call(tmp_path: Path, result: dict):
    from mcp.client import Client

    mcp, service = _server(tmp_path)
    service.report_render = lambda payload: result  # type: ignore[method-assign]

    async def run():
        async with Client(mcp) as client:
            return await client.call_tool("horosa_report_render", {"run_id": "x", "format": "png"})

    out = asyncio.run(run())
    return out, json.loads(out.content[0].text)


def test_png_result_carries_the_image_inline_and_a_resource_link(tmp_path: Path) -> None:
    path = _png_file(tmp_path / "chart.png")
    out, body = _call(tmp_path, _png_result([path]))
    images = [b for b in out.content if b.type == "image"]
    links = [b for b in out.content if b.type == "resource_link"]
    assert len(images) == 1 and images[0].mime_type == "image/png"
    assert base64.b64decode(images[0].data) == path.read_bytes()
    assert len(links) == 1 and links[0].mime_type == "image/png"
    assert body["inline_images"] == {"shown": 1, "total": 1}
    assert images[0].data[:64] not in out.content[0].text  # base64 不进 JSON 正文（不占 AI 的文字上下文）


def test_an_image_over_the_size_cap_is_linked_not_inlined_and_the_result_says_so(tmp_path: Path) -> None:
    big = _png_file(tmp_path / "big.png", size=600, noise=True)
    from horosa_skill.surfaces import mcp_runner

    assert big.stat().st_size > mcp_runner.PNG_INLINE_MAX_BYTES
    out, body = _call(tmp_path, _png_result([big]))
    assert [b.type for b in out.content].count("image") == 0
    assert [b.type for b in out.content].count("resource_link") == 1
    assert body["inline_images"]["shown"] == 0 and body["inline_images"]["omitted"][0]["reason"] == "image_too_large"
    assert "没有内嵌显示" in body["summary"][-1] and str(big) in body["summary"][-1]


def test_images_stop_at_the_wire_budget_and_the_count_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill.surfaces import mcp_runner

    paths = [_png_file(tmp_path / f"c{i}.png", size=120, noise=True) for i in range(6)]
    out, body = _call(tmp_path, _png_result(paths))
    reasons = [item["reason"] for item in body["inline_images"]["omitted"]]
    assert body["inline_images"]["shown"] == mcp_runner.PNG_INLINE_MAX_IMAGES == 4 and reasons == ["too_many_images"] * 2
    assert len([b for b in out.content if b.type == "resource_link"]) == 6  # 每个文件都有链接
    one = len(base64.b64encode(paths[0].read_bytes()))
    monkeypatch.setattr(mcp_runner, "MCP_RESULT_WIRE_BUDGET", 2 * one + 9_000)  # 只放得下前一两张
    out, body = _call(tmp_path, _png_result(paths[:3]))
    shown = body["inline_images"]["shown"]
    assert 1 <= shown < 3 and {item["reason"] for item in body["inline_images"]["omitted"]} == {"result_size_cap"}
    assert sum(len(b.data) for b in out.content if b.type == "image") <= mcp_runner.MCP_RESULT_WIRE_BUDGET


def test_a_png_changed_after_rendering_is_not_inlined(tmp_path: Path) -> None:
    path = _png_file(tmp_path / "chart.png")
    result = _png_result([path])
    _png_file(path, size=65)  # 落盘后被改过：与文件卡的 sha256 不符
    out, body = _call(tmp_path, result)
    assert not [b for b in out.content if b.type == "image"]
    assert body["inline_images"]["omitted"][0]["reason"] == "file_unreadable"


def test_non_png_results_get_no_image_blocks(tmp_path: Path) -> None:
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF-1.7 fake")
    from horosa_skill.service.api.reports import _file_card

    out, body = _call(tmp_path, {"ok": True, "format": "pdf", "artifact_path": str(pdf), "file": _file_card(pdf, "pdf")})
    assert [b.type for b in out.content] == ["text", "resource_link"] and "inline_images" not in body
