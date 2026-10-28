"""带标签的 PDF（PDF/UA-1）：画的时候打标记内容，存盘时用 reportlab 自己的对象模型写结构树。不加新依赖。

为什么这么做（2026-10 调研，docs/LESSONS.md v0.45.1-dev）：
- 开源 reportlab 没有打标签（结构树只在商业版 rlextra）；catalog 却允许 StructTreeRoot / MarkInfo / Metadata 这些键。
- 调研里「reportlab 画时打标记 + pikepdf 事后建树」过了 veraPDF PDF/UA-1；但 pikepdf 新版的 macOS 轮子要 macOS 14/15，
  而本仓承诺 macOS 11 起——做成硬依赖会让老 Mac 装不上。所以树也在 reportlab 里写：画的时候记下
  （页, MCID, 父节点, 标签），canvas.save() 前拼成 StructTreeRoot / ParentTree / OBJR。
- 画面上一切内容要么在标签里，要么标成 Artifact（页眉页脚、底色、表格框线）；数据表的格子是 TH / TD，格子里的
  段落不再自己打标签（标记内容不能嵌套 MCID）；版式用的表（标题条、卡片、封面）只把底色 / 线标成 Artifact，
  格子里的段落照常是 P / H。
- 标题按 H1–H6，且**不跳级**（上一个是 H1，下一个最多 H2）。
- 中文字体退回不嵌入的 CID 字体时（本机找不到 TTF）照样打标签，但不在元数据里声称 PDF/UA（规则 7.21.4 要求嵌入）。
"""
from __future__ import annotations

from typing import Any, ClassVar

from reportlab.pdfbase import pdfdoc
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Flowable, Paragraph, Table
from reportlab.platypus.flowables import HRFlowable

TRUE = b"true"


class TaggedLinkAnnotation(pdfdoc.LinkAnnotation):
    """链接注释多带一个 /StructParent（PDF/UA 7.18.5：链接要进结构树，经 OBJR 指回注释）。"""

    permitted = pdfdoc.LinkAnnotation.permitted + ("StructParent",)


class TaggingCanvas(Canvas):
    """记录标记内容；save() 时写结构树。dest_labels：书签名 → 链接的替代文字（读屏念的「跳到哪」）。"""

    ua_claim = True  # 渲染器在字体退回 CID 时置 False
    dest_labels: ClassVar[dict[str, str]] = {}  # 渲染器每次渲染换成自己的字典（子类属性）

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._elems: list[dict[str, Any]] = []
        self._mcid: dict[int, int] = {}
        self._suppress = 0
        self._links: list[dict[str, Any]] = []
        self._last_heading = 0

    # ── 画的时候 ──────────────────────────────────────────────────────────

    def _page_index(self) -> int:
        return self.getPageNumber() - 1

    def tag_group(self, tag: str, parent: dict[str, Any] | None = None) -> dict[str, Any]:
        elem = {"id": len(self._elems), "tag": tag, "parent": None if parent is None else parent["id"], "page": None, "mcid": None}
        self._elems.append(elem)
        return elem

    def tag_begin(self, tag: str, parent: dict[str, Any] | None = None, **attrs: Any) -> dict[str, Any]:
        if tag.startswith("H") and tag[1:].isdigit():
            level = min(int(tag[1:]), self._last_heading + 1, 6)  # 不跳级
            self._last_heading = level
            tag = f"H{level}"
        page = self._page_index()
        mcid = self._mcid.get(page, 0)
        self._mcid[page] = mcid + 1
        self._code.append(f"/{tag} <</MCID {mcid}>> BDC")
        elem = {"id": len(self._elems), "tag": tag, "parent": None if parent is None else parent["id"],
                "page": page, "mcid": mcid, **attrs}
        self._elems.append(elem)
        return elem

    def tag_end(self) -> None:
        self._code.append("EMC")

    def artifact_begin(self, kind: str = "") -> None:
        self._code.append(f"/Artifact <</Type /{kind}>> BDC" if kind else "/Artifact BMC")

    def artifact_end(self) -> None:
        self._code.append("EMC")

    def linkRect(self, contents: Any, destinationname: Any, Rect: Any = None, addtopage: int = 1, name: Any = None,
                 relative: int = 1, thickness: Any = 0, color: Any = None, dashArray: Any = None, **kw: Any) -> Any:
        from reportlab.pdfgen.canvas import _annFormat

        destination = self._bookmarkReference(destinationname)
        kw["Rect"] = self._absRect(Rect, relative)
        kw["Contents"] = contents or self.dest_labels.get(str(destinationname)) or f"跳转：{destinationname}"
        kw["Destination"] = destination
        _annFormat(kw, color, thickness, dashArray)
        annotation = TaggedLinkAnnotation(**kw)
        self._links.append({"annotation": annotation, "page": self._page_index()})
        return self._addAnnotation(annotation, name, addtopage)

    # ── 存盘时 ────────────────────────────────────────────────────────────

    def save(self) -> None:
        if self._elems:
            self._write_structure()
        super().save()

    def _write_structure(self) -> None:
        doc = self._doc
        ref = pdfdoc.PDFObjectReference
        names = [f"HorosaSE{e['id']}" for e in self._elems]
        root_name, doc_name = "HorosaStructTreeRoot", "HorosaStructDocument"

        def page_ref(index: int) -> Any:
            return ref(f"Page{index + 1}")  # reportlab 的页对象名（PDFDocument.thisPageName）

        children: dict[Any, list[Any]] = {}
        for elem in self._elems:
            children.setdefault(elem["parent"], []).append(elem)
        per_page: dict[int, dict[int, str]] = {}
        for elem, name in zip(self._elems, names):
            entries: dict[str, Any] = {"Type": pdfdoc.PDFName("StructElem"), "S": pdfdoc.PDFName(elem["tag"]),
                                       "P": ref(doc_name if elem["parent"] is None else names[elem["parent"]])}
            if elem["page"] is not None:
                entries["Pg"] = page_ref(elem["page"])
                entries["K"] = elem["mcid"]
                per_page.setdefault(elem["page"], {})[elem["mcid"]] = name
            else:
                entries["K"] = pdfdoc.PDFArray([ref(names[c["id"]]) for c in children.get(elem["id"], [])])
            if elem.get("alt"):
                entries["Alt"] = pdfdoc.PDFString(str(elem["alt"]))
            if elem.get("scope"):
                entries["A"] = pdfdoc.PDFDictionary({"O": pdfdoc.PDFName("Table"), "Scope": pdfdoc.PDFName(elem["scope"])})
            doc.Reference(pdfdoc.PDFDictionary(entries), name)

        top = [ref(names[e["id"]]) for e in children.get(None, [])]
        nums: list[Any] = []
        for index in sorted(per_page):
            marks = per_page[index]
            array_name = f"HorosaParentTree{index}"
            doc.Reference(pdfdoc.PDFArray([ref(marks[m]) for m in range(len(marks))]), array_name)
            nums += [index, ref(array_name)]
        next_key = len(doc.Pages.pages)
        for offset, link in enumerate(self._links):
            key = next_key + offset
            link["annotation"].otherkw["StructParent"] = key
            link_name = f"HorosaLink{offset}"
            objr = pdfdoc.PDFDictionary({"Type": pdfdoc.PDFName("OBJR"), "Obj": doc.Reference(link["annotation"]),
                                         "Pg": page_ref(link["page"])})
            doc.Reference(pdfdoc.PDFDictionary({"Type": pdfdoc.PDFName("StructElem"), "S": pdfdoc.PDFName("Link"),
                                                "P": ref(doc_name), "Pg": page_ref(link["page"]),
                                                "K": pdfdoc.PDFArray([objr])}), link_name)
            top.append(ref(link_name))
            nums += [key, ref(link_name)]
        doc.Reference(pdfdoc.PDFDictionary({"Type": pdfdoc.PDFName("StructElem"), "S": pdfdoc.PDFName("Document"),
                                            "P": ref(root_name), "K": pdfdoc.PDFArray(top)}), doc_name)
        doc.Reference(pdfdoc.PDFDictionary({"Nums": pdfdoc.PDFArray(nums)}), "HorosaParentTree")
        doc.Reference(pdfdoc.PDFDictionary({"Type": pdfdoc.PDFName("StructTreeRoot"), "K": ref(doc_name),
                                            "ParentTree": ref("HorosaParentTree"),
                                            "ParentTreeNextKey": next_key + len(self._links)}), root_name)
        for index, page in enumerate(doc.Pages.pages):
            page.__NoDefault__ = [*pdfdoc.PDFPage.__NoDefault__, "StructParents", "Tabs"]
            page.StructParents = index
            page.Tabs = pdfdoc.PDFName("S")  # Tab 键顺序 = 结构顺序（PDF/UA 7.18.3）
        catalog = doc.Catalog
        catalog.StructTreeRoot = ref(root_name)
        catalog.MarkInfo = pdfdoc.PDFDictionary({"Marked": TRUE})
        self.setViewerPreference("DisplayDocTitle", "true")
        metadata = pdfdoc.PDFStream(pdfdoc.PDFDictionary({"Type": pdfdoc.PDFName("Metadata"),
                                                          "Subtype": pdfdoc.PDFName("XML")}),
                                    _xmp(doc.info.title or "", ua=self.ua_claim).encode("utf-8"), filters=[])
        doc.Reference(metadata, "HorosaXMP")
        catalog.Metadata = ref("HorosaXMP")


def _xmp(title: str, *, ua: bool) -> str:
    from xml.sax.saxutils import escape

    ua_part = '<rdf:Description rdf:about="" xmlns:pdfuaid="http://www.aiim.org/pdfua/ns/id/"><pdfuaid:part>1</pdfuaid:part></rdf:Description>' if ua else ""
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:title><rdf:Alt><rdf:li xml:lang="x-default">{escape(title)}</rdf:li></rdf:Alt></dc:title>'
        '</rdf:Description>'
        f'{ua_part}'
        '</rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
    )


# ── flowable 侧：段落、表格、图 ─────────────────────────────────────────────


class TaggedParagraph(Paragraph):
    """段落自己打 P / H 标签（tag 由渲染器按样式定）；在数据表格子里时不打（格子已是 TD）。"""

    pdf_tag = "P"

    def drawOn(self, canvas: Any, x: float, y: float, _sW: float = 0) -> None:
        tagging = isinstance(canvas, TaggingCanvas) and canvas._suppress == 0
        if tagging:
            canvas.tag_begin(self.pdf_tag)
        super().drawOn(canvas, x, y, _sW)
        if tagging:
            canvas.tag_end()

    def split(self, availWidth: float, availHeight: float) -> list[Any]:
        # reportlab 按 self.__class__ 造两段；标签只给第一段，跨页的后半段记 P（标题拆开时后半不算新标题）。
        parts = super().split(availWidth, availHeight)
        for index, part in enumerate(parts):
            if isinstance(part, TaggedParagraph):
                part.pdf_tag = self.pdf_tag if index == 0 else "P"
        return parts


class _TableTagger:
    """表格的 renderCB：底色与框线标 Artifact；数据表另把格子标 TH / TD（表头行 / 表头列 TH）。"""

    def __init__(self, *, data: bool, header_rows: int = 0, header_cols: int = 0) -> None:
        self.data = data
        self.header_rows = header_rows
        self.header_cols = header_cols

    def __call__(self, table: Any, event: str, *args: Any) -> None:
        canvas = table.canv
        if not isinstance(canvas, TaggingCanvas):
            return
        if event in ("startBG", "startLines"):
            canvas.artifact_begin()
        elif event in ("endBG", "endLines"):
            canvas.artifact_end()
        elif not self.data:
            return
        elif event == "startTable":
            self.table = canvas.tag_group("Table")
        elif event == "startRow":
            self.row = canvas.tag_group("TR", parent=self.table)
            self.row_no = args[0] if args else 0
        elif event == "startCell":
            col = args[1] if len(args) > 1 else 0
            header = self.row_no < self.header_rows or col < self.header_cols
            scope = ("Column" if self.row_no < self.header_rows else "Row") if header else None
            canvas.tag_begin("TH" if header else "TD", parent=self.row, **({"scope": scope} if scope else {}))
            canvas._suppress += 1
        elif event == "endCell":
            canvas._suppress -= 1
            canvas.tag_end()


def layout_table(*args: Any, **kwargs: Any) -> Any:
    """版式用的表（标题条、卡片、封面、目录）：底色 / 框线是 Artifact，格子里的段落自己打标签。"""
    return Table(*args, renderCB=_TableTagger(data=False), **kwargs)


def data_table(*args: Any, header_rows: int = 1, header_cols: int = 0, **kwargs: Any) -> Any:
    """数据表：TH（表头行 Column / 表头列 Row）+ TD；跨页重复的表头行同样是 TH。"""
    return Table(*args, renderCB=_TableTagger(data=True, header_rows=header_rows, header_cols=header_cols), **kwargs)


class TaggedFigure(Flowable):
    """把一张矢量盘图包成 Figure（带替代文字：图名 + 图例，只描述结构不做解读）。"""

    def __init__(self, drawing: Any, alt: str) -> None:
        super().__init__()
        self.drawing = drawing
        self.alt = alt
        self.hAlign = getattr(drawing, "hAlign", "CENTER")

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        self.width, self.height = self.drawing.wrap(availWidth, availHeight)
        return self.width, self.height

    def draw(self) -> None:
        canvas = self.canv
        tagging = isinstance(canvas, TaggingCanvas) and canvas._suppress == 0
        if tagging:
            canvas.tag_begin("Figure", alt=self.alt, bbox=None)
        self.drawing.drawOn(canvas, 0, 0)
        if tagging:
            canvas.tag_end()


class ArtifactHR(HRFlowable):
    """分隔线是装饰，不是内容：标 Artifact。"""

    def draw(self) -> None:
        tagging = isinstance(self.canv, TaggingCanvas)
        if tagging:
            self.canv.artifact_begin()
        super().draw()
        if tagging:
            self.canv.artifact_end()


def artifact(draw: Any, kind: str = "Pagination") -> Any:
    """页眉页脚 / 底色这类 onPage 回调：整段标 Artifact。"""

    def wrapped(canvas: Any, doc: Any) -> None:
        if isinstance(canvas, TaggingCanvas):
            canvas.artifact_begin(kind)
        draw(canvas, doc)
        if isinstance(canvas, TaggingCanvas):
            canvas.artifact_end()

    return wrapped
