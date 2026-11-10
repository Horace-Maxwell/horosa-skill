"""塔罗牌阵图（reports/app_charts.py + horosa-core-js/app-charts/adapters/tarot.js + 随包牌面图 data/tarot-art/）。

What must hold:
- the figure lays out the reading the engine wrote up (core-js tarot.js board_context), never a re-draw;
- each card face is the shipped picture the app's own cardImageUrl names, turned 180° when reversed, the 凯尔特 crossing card
  turned 90°; a card the install has no picture for falls back to the app's symbol face with the card's name;
- a card the app's deck tables do not know is refused (no figure) rather than drawn as some other card;
- only shipped pictures are ever read and embedded; PDF / DOCX / PNG all carry the faces;
- the shipped pictures are exactly the manifest (and the manifest is every file cardImageUrl can name).
"""
from __future__ import annotations

import gzip
import io
import json
import re
import shutil
import zipfile
import zlib
from pathlib import Path

import pytest

from horosa_skill.reports import app_charts
from horosa_skill.reports.figures import drawing_to_png, extract_figures

PKG_ROOT = Path(__file__).resolve().parents[1]
CORE_JS = PKG_ROOT / "horosa-core-js"
FIXTURE = json.loads(gzip.decompress((PKG_ROOT / "tests" / "fixtures" / "app_charts_live.json.gz").read_bytes()))

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")


class _Client:
    def render_app_charts(self, figures):
        from horosa_skill.config import Settings
        from horosa_skill.engine.js_client import HorosaJsEngineClient

        client = HorosaJsEngineClient(Settings.from_env())
        client._candidate_engine_roots = lambda: [CORE_JS]  # type: ignore[method-assign]
        return client.render_app_charts(figures)


def _figure(data: dict) -> dict:
    figures = app_charts.attach_app_svgs(extract_figures("tarot", data, "塔罗"), "tarot", data, _Client())
    assert len(figures) <= 1
    return figures[0] if figures else {}


def _node(script: str, *args: object) -> str:
    from node_esm import run_node_esm

    return run_node_esm(script, *args, cwd=CORE_JS)


def _expected_hrefs(board: dict) -> list[str | None]:
    """The app's cardImageUrl for each drawn card (vendored copy of the same file), card looked up by id."""
    script = (
        "const [reg, art] = await Promise.all([import(process.argv[1]), import(process.argv[2])]);"
        "const b = JSON.parse(process.argv[3]); const cards = reg.getDeckCards(b.deckId);"
        "process.stdout.write(JSON.stringify(b.draws.map((d) => art.cardImageUrl(b.deckId, cards.find((c) => c.id === d.cardId)))));"
    )
    vendor = CORE_JS / "src" / "vendor" / "tarot" / "engine"
    return json.loads(_node(script, vendor / "deckRegistry.js", vendor / "cardArt.js", json.dumps(board)))


@needs_node
def test_board_context_is_the_reading_the_text_was_written_from() -> None:
    """core-js 工具把产出正文的同一个 reading 交出来（牌 id / sid / 朝向 / 牌位），不另抽；横置牌带 crossed。"""
    script = (
        "const [t, r] = await Promise.all([import(process.argv[1]), import(process.argv[2])]);"
        "const out = t.runTarot({ seed: 'horosa', spread: 'celtic', deck: 'rws' });"
        "const ref = r.buildReading('rws', 'celtic', 'horosa', { question: '' });"
        "process.stdout.write(JSON.stringify({ b: out.data.board_context, text: out.snapshot_text,"
        " ref: ref.draws.map((d) => [d.position.i, d.card.id, d.card.sid, !!d.isReversed, !!d.crossed]) }));"
    )
    out = json.loads(_node(script, CORE_JS / "src" / "tools" / "tarot.js", CORE_JS / "src" / "vendor" / "tarot" / "engine" / "reading.js"))
    board = out["b"]
    assert board["deckId"] == "rws" and board["spreadType"] == "celtic" and len(board["draws"]) == 10
    assert [[d["position"]["i"], d["cardId"], d["sid"], d["isReversed"], bool(d.get("crossed"))] for d in board["draws"]] == out["ref"]
    assert board["draws"][1]["crossed"] is True
    assert all(d["position"]["label"] in out["text"] for d in board["draws"]), "the text names every position the board shows"
    assert all("card" not in d for d in board["draws"]), "cards travel as id + sid, not ~600-byte card objects"


@needs_node
def test_spread_shows_the_shipped_face_the_app_names_for_each_drawn_card() -> None:
    data = FIXTURE["tarot"]
    spec = _figure(data)
    assert spec.get("renderer") == "app" and spec["app_kind"] == "tarot" and spec["title"] == "塔罗牌阵"
    svg = spec["app_svg"]
    hrefs = re.findall(r'<image href="([^"]+)"', svg)
    expected = _expected_hrefs(data["board_context"])
    assert hrefs == expected and all(hrefs), "one picture per drawn card, in draw order, named by the app's cardImageUrl"
    assert all((app_charts.TAROT_ART_DIR / h.removeprefix("tarot-art/")).is_file() for h in hrefs)
    assert "凯尔特十字" in svg and "var(" not in svg
    # 逆位：牌面（图 + 牌名）整体转 180°；凯尔特第 2 张（交叉牌）整张横置 90°
    reversed_ids = [h for h, d in zip(hrefs, data["board_context"]["draws"]) if d["isReversed"]]
    for href in reversed_ids:
        assert re.search(r'rotate\(180\) translate\([^)]*\)"><image href="' + re.escape(href), svg), href
    crossing = data["board_context"]["draws"][1]
    assert re.search(r'rotate\(90\)[^>]*>(?:(?!</g>).)*' + re.escape(hrefs[1]), svg), "crossing card must lie across the first"
    assert crossing["crossed"]


@needs_node
def test_cards_without_a_picture_fall_back_to_the_named_symbol_face() -> None:
    """托特牌组上游没有牌面图；这次安装缺某张图时同样回落（app 的 <img onError> 回退）：符号 + 牌名，不留空框。"""
    thoth = _figure(FIXTURE["tarot_thoth"])
    assert thoth.get("renderer") == "app" and "<image" not in thoth["app_svg"]
    assert thoth["app_svg"].count(f'font-family="{app_charts.OPTIONAL_GLYPH_SVG_FAMILY}"') >= len(FIXTURE["tarot_thoth"]["board_context"]["draws"])
    # RWS 缺一张图：只有那张退回符号牌面，其余照常
    data = FIXTURE["tarot"]
    hrefs = _expected_hrefs(data["board_context"])
    missing = hrefs[0]
    art = {k: v for k, v in app_charts.tarot_art_sizes().items() if k != missing}
    result = _Client().render_app_charts([{"kind": "tarot", "data": {"board_context": data["board_context"]}, "options": {"art": art}}])[0]
    assert result["ok"]
    assert re.findall(r'<image href="([^"]+)"', result["svg"]) == hrefs[1:]
    assert "环绕(现状)" in result["svg"] and f'font-family="{app_charts.OPTIONAL_GLYPH_SVG_FAMILY}"' in result["svg"]


@needs_node
def test_a_card_the_app_deck_does_not_know_is_refused_not_redrawn() -> None:
    data = json.loads(json.dumps(FIXTURE["tarot"]))
    data["board_context"]["draws"][0]["sid"] = "the_unknown"
    assert _figure(data) == {}, "sid mismatch → no figure (kind=app has no builtin drawing), never another card's face"


def test_only_shipped_pictures_are_read_and_embedded() -> None:
    shipped = next(iter(app_charts.tarot_art_sizes()))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><image href="{shipped}" width="1" height="1"/>'
           '<image href="tarot-art/rws/../../../../pyproject.jpg" width="1" height="1"/>'
           '<image href="tarot-art/rws/zz99.jpg" width="1" height="1"/>'
           '<image href="data:image/png;base64,AAAA" width="1" height="1"/></svg>')
    out = app_charts.embed_images(svg)
    assert out.count("data:image/jpeg;base64,") == 1, "the shipped picture is inlined"
    assert "pyproject" not in out and "zz99" not in out, "unknown / traversal hrefs are dropped, never read"
    assert 'href="data:image/png;base64,AAAA"' in out, "other images are left alone"


def test_decorative_symbols_no_font_can_print_are_dropped_not_boxed() -> None:
    from reportlab.graphics.shapes import String

    from horosa_skill.reports.renderers import SIMPLIFIED, _drawing_font_files

    fonts = _drawing_font_files(SIMPLIFIED)
    if not fonts:
        pytest.skip("no CJK TrueType font on this machine")
    regular, bold = fonts["names"]
    fam = app_charts.OPTIONAL_GLYPH_SVG_FAMILY
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="40"><text x="5" y="20" font-family="{fam}">\U0010fffd</text>'
           f'<text x="40" y="20" font-family="{fam}">心</text><text x="70" y="20">\U0010fffd</text></svg>')
    drawing = app_charts.svg_drawing(svg, 100, text_font=regular, bold_font=bold)
    texts: list[str] = []

    def walk(node):
        for child in getattr(node, "contents", None) or []:
            texts.append(child.text) if isinstance(child, String) else walk(child)

    walk(drawing)
    assert texts.count("\U0010fffd") == 1, "the optional symbol goes; ordinary text is never silently dropped"
    assert "心" in texts


def test_card_pictures_turn_with_the_card_in_bitmaps() -> None:
    """DOCX / PNG 的位图：图片跟着组变换走（逆位 180°）。上红下蓝的图转 180° 后，上方应是蓝。"""
    from PIL import Image as PILImage
    from reportlab.graphics.shapes import Drawing, Group
    from reportlab.graphics.shapes import Image as BitmapShape

    picture = PILImage.new("RGB", (10, 20), (255, 0, 0))
    picture.paste((0, 0, 255), (0, 10, 10, 20))
    drawing = Drawing(40, 40)
    turned = Group(BitmapShape(10, 0, 20, 40, picture))
    turned.translate(20, 20)
    turned.rotate(180)
    turned.translate(-20, -20)
    drawing.add(turned)
    png = drawing_to_png(drawing, {}, scale=1.0)
    with PILImage.open(io.BytesIO(png)) as image:
        top, bottom = image.convert("RGB").getpixel((20, 5)), image.convert("RGB").getpixel((20, 35))
    assert top[2] > 200 and top[0] < 60, f"top should be blue after 180°, got {top}"
    assert bottom[0] > 200 and bottom[2] < 60, f"bottom should be red after 180°, got {bottom}"
    assert drawing_to_png(drawing, {}, scale=1.0, photo_jpeg=True).startswith(b"\xff\xd8"), "photos in Word go as JPEG"


def test_shipped_pictures_match_the_manifest_and_cover_every_card_the_app_names() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("sync_tarot_art", PKG_ROOT / "scripts" / "sync_tarot_art.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    assert module.check_package() == []
    manifest = json.loads((app_charts.TAROT_ART_DIR / "manifest.json").read_text(encoding="utf-8"))
    bundle = json.loads((PKG_ROOT / "contracts" / "app_charts_bundle.json").read_text(encoding="utf-8"))
    assert manifest["upstream_commit"] == bundle["upstream_commit"], "pictures and chart code come from the same upstream pin"
    if shutil.which("node") is None:
        return
    script = (
        "const [reg, art] = await Promise.all([import(process.argv[1]), import(process.argv[2])]); const out = new Set();"
        "for (const id of reg.listDeckIds()) for (const c of reg.getDeckCards(id)) { const u = art.cardImageUrl(id, c); if (u) out.add(u); }"
        "process.stdout.write(JSON.stringify([...out].sort()));"
    )
    vendor = CORE_JS / "src" / "vendor" / "tarot" / "engine"
    named = json.loads(_node(script, vendor / "deckRegistry.js", vendor / "cardArt.js"))
    assert named == sorted(f"tarot-art/{rel}" for rel in manifest["files"]), "every picture the app can show is shipped, nothing else"


def _inflate(data: bytes) -> bytes:
    """reportlab 的内容流：Flate，或 ASCII85 + Flate（页面流）；别的流原样返回。"""
    import base64

    for decode in (lambda d: zlib.decompress(d), lambda d: zlib.decompress(base64.a85decode(d.strip().removesuffix(b"~>")))):
        try:
            return decode(data)
        except (zlib.error, ValueError):
            continue
    return b""


@needs_node
def test_pdf_docx_and_png_reports_carry_the_card_faces(tmp_path: Path) -> None:
    from fakes import FakeClient

    from horosa_skill.config import Settings
    from horosa_skill.engine.js_client import HorosaJsEngineClient
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.reports.renderers import SIMPLIFIED, _drawing_font_files
    from horosa_skill.service import HorosaSkillService
    from horosa_skill.testing_payloads import build_sample_payloads

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt", data_dir=tmp_path / "data")
    js = HorosaJsEngineClient(settings)
    js._candidate_engine_roots = lambda: [CORE_JS]  # type: ignore[method-assign]
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=js)
    env = service.run_tool("tarot", build_sample_payloads()["tarot"], save_result=True)
    assert env.ok and env.memory_ref
    run_id = env.memory_ref.run_id
    cards = len(env.data["board_context"]["draws"])
    pdf = Path(service.report_render({"run_id": run_id, "format": "pdf", "style": "chart", "output_path": "t.pdf"})["file"]["path"])
    streams = [_inflate(m.group(1).strip()) for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf.read_bytes(), re.S)]
    inline_jpegs = sum(len(re.findall(rb"BI /W \d+ /H 300 /BPC 8 /CS /DeviceRGB /F \[(?:/A85 )?/DCT\] ID", s)) for s in streams)
    assert inline_jpegs == cards, f"each drawn card is embedded as its JPEG (DCT passthrough), got {inline_jpegs} / {cards}"
    docx = Path(service.report_render({"run_id": run_id, "format": "docx", "style": "chart", "output_path": "t.docx"})["file"]["path"])
    with zipfile.ZipFile(docx) as archive:
        media = [archive.read(n) for n in archive.namelist() if n.startswith("word/media/")]
    assert any(m.startswith(b"\xff\xd8") for m in media), "the spread is rasterised with its pictures (JPEG = bitmaps were drawn)"
    if _drawing_font_files(SIMPLIFIED) is None:
        return  # CI Linux: no CJK TrueType → PNG is refused by design (test_report_chart_png covers that)
    from PIL import Image

    png = Path(service.report_render({"run_id": run_id, "format": "png", "output_path": "t.png"})["file"]["path"])
    with Image.open(png) as image:
        hsv = image.convert("RGB").resize((200, 120)).convert("HSV")
        _h, sat, val = hsv.split()
        vivid = sum(1 for s, v in zip(sat.tobytes(), val.tobytes()) if s > 120 and v > 60)
    assert vivid > 200 * 120 * 0.03, f"the PNG must show the painted card faces, only {vivid} vivid pixels"
