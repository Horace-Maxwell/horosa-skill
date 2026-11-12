"""调用方写的 Markdown → 一棵块树；PDF 与 DOCX 画同一棵树（v0.50.0，评审 R-07）。

此前两个渲染器各自逐行认 Markdown（`_md_lines` + 两个正则）：斜体、删除线、链接、`<br>`、代码块、嵌套 / 有序列表都原样印成符号，
「Note: …」这类句子被当成键值行排进对照表，调用方写的小数也被四舍五入。现在调用方的文字（核心结论、摘要、解读正文、建议、
所问）用 CommonMark 解析（markdown-it-py，GFM 表格与删除线），引擎导出段仍走渲染器原来的逐行规则（键值对照表、长小数取 4 位
只对引擎原文）。

规矩：
- 单个换行就是换行（`breaks`）：AI 写的「起盘依据：…\\n日主：…」是一行一条，不是一段话。
- 原始 HTML 不解释（`html: False`），按字面印；只有 `<br>` 认作换行。
- 链接只留 http / https / mailto（markdown-it 本身已拒 javascript: 等），其余印成文字。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Union

_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_SAFE_HREF = ("http://", "https://", "mailto:")


@dataclass(frozen=True)
class Span:
    """一段同样式的行内文字。`text == "\\n"` 且 `brk` 为真时是换行。"""

    text: str
    bold: bool = False
    italic: bool = False
    strike: bool = False
    code: bool = False
    href: str | None = None
    brk: bool = False


Inline = list[Span]


@dataclass
class Paragraph:
    spans: Inline


@dataclass
class Heading:
    level: int
    spans: Inline


@dataclass
class ListBlock:
    ordered: bool
    start: int
    items: list[list[Block]] = field(default_factory=list)


@dataclass
class Quote:
    children: list[Block] = field(default_factory=list)


@dataclass
class Code:
    text: str
    info: str = ""


@dataclass
class Table:
    header: list[Inline]
    rows: list[list[Inline]]
    aligns: list[str]


@dataclass
class Rule:
    pass


Block = Union[Paragraph, Heading, ListBlock, Quote, Code, Table, Rule]


@lru_cache(maxsize=1)
def _parser() -> Any:
    from markdown_it import MarkdownIt

    return MarkdownIt("commonmark", {"html": False, "breaks": True}).enable(["table", "strikethrough"])


def parse(text: str) -> list[Block]:
    """Markdown 文本 → 块树。空文本 → []。"""
    if not str(text or "").strip():
        return []
    tokens = _parser().parse(str(text))
    blocks, _ = _blocks(tokens, 0, None)
    return blocks


def _blocks(tokens: list[Any], index: int, closing: str | None) -> tuple[list[Block], int]:
    out: list[Block] = []
    while index < len(tokens):
        token = tokens[index]
        kind = token.type
        if closing is not None and kind == closing:
            return out, index + 1
        if kind == "paragraph_open":
            out.append(Paragraph(inline(tokens[index + 1])))
            index += 3
        elif kind == "heading_open":
            out.append(Heading(int(token.tag[1:]), inline(tokens[index + 1])))
            index += 3
        elif kind in {"bullet_list_open", "ordered_list_open"}:
            ordered = kind == "ordered_list_open"
            start = int(token.attrGet("start") or 1) if ordered else 1
            block = ListBlock(ordered, start)
            index += 1
            close = kind.replace("_open", "_close")
            while tokens[index].type != close:
                item, index = _blocks(tokens, index + 1, "list_item_close")  # list_item_open → 内容 → list_item_close
                block.items.append(item)
            out.append(block)
            index += 1
        elif kind == "blockquote_open":
            children, index = _blocks(tokens, index + 1, "blockquote_close")
            out.append(Quote(children))
        elif kind in {"fence", "code_block"}:
            out.append(Code(token.content.rstrip("\n"), (token.info or "").strip()))
            index += 1
        elif kind == "hr":
            out.append(Rule())
            index += 1
        elif kind == "table_open":
            table, index = _table(tokens, index + 1)
            out.append(table)
        elif kind == "html_block":  # html 关着时不会出现；留着防御
            out.append(Paragraph([Span(token.content.strip())]))
            index += 1
        else:
            index += 1
    return out, index


def _table(tokens: list[Any], index: int) -> tuple[Table, int]:
    header: list[Inline] = []
    rows: list[list[Inline]] = []
    aligns: list[str] = []
    row: list[Inline] = []
    in_head = False
    while tokens[index].type != "table_close":
        token = tokens[index]
        if token.type == "thead_open":
            in_head = True
        elif token.type == "thead_close":
            in_head = False
        elif token.type == "tr_open":
            row = []
        elif token.type == "tr_close":
            if in_head:
                header = row
            else:
                rows.append(row)
        elif token.type in {"th_open", "td_open"}:
            style = str(token.attrGet("style") or "")
            if in_head:
                aligns.append(style.removeprefix("text-align:") if style else "")
        elif token.type == "inline":
            row.append(inline(token))
        index += 1
    width = len(header)
    rows = [(cells + [[] for _ in range(width - len(cells))])[:width] for cells in rows]
    return Table(header, rows, aligns), index + 1


def inline(token: Any) -> Inline:
    spans: Inline = []
    bold = italic = strike = 0
    href: list[str | None] = []
    for child in token.children or []:
        kind = child.type
        if kind == "text":
            _text(spans, child.content, bold > 0, italic > 0, strike > 0, href[-1] if href else None)
        elif kind == "code_inline":
            spans.append(Span(child.content, bold > 0, italic > 0, strike > 0, True, href[-1] if href else None))
        elif kind in {"softbreak", "hardbreak"}:
            spans.append(Span("\n", brk=True))
        elif kind == "strong_open":
            bold += 1
        elif kind == "strong_close":
            bold -= 1
        elif kind == "em_open":
            italic += 1
        elif kind == "em_close":
            italic -= 1
        elif kind == "s_open":
            strike += 1
        elif kind == "s_close":
            strike -= 1
        elif kind == "link_open":
            target = str(child.attrGet("href") or "")
            href.append(target if target.lower().startswith(_SAFE_HREF) else None)
        elif kind == "link_close":
            if href:
                href.pop()
        elif kind == "image":  # 不嵌外链图：印替代文字
            _text(spans, child.content or str(child.attrGet("alt") or ""), bold > 0, italic > 0, strike > 0, None)
        elif kind == "html_inline":
            _text(spans, child.content, bold > 0, italic > 0, strike > 0, href[-1] if href else None)
    return spans


# CommonMark 的「左右侧定界」规则对中文不友好：`**结论：**今年宜守` 的收尾 ** 前是标点、后是汉字，不算右侧定界，整段原样留成
# 文字（CommonMark 规范的已知问题）。AI 写中文常这样用，旧渲染器按正则也一直认。所以在同一段文字里，CommonMark 没认下的成对
# ** / ~~ 再按「成对就算」补认一次；单个 * 不补（乘号、星号列表残留太多）。
_LEFTOVER_PAIR_RE = re.compile(r"(\*\*|~~)(?=\S)(.+?)(?<=\S)\1")


def _text(spans: Inline, text: str, bold: bool, italic: bool, strike: bool, href: str | None) -> None:
    for index, piece in enumerate(_BR_RE.split(text)):
        if index:
            spans.append(Span("\n", brk=True))
        if piece:
            _leftover_pairs(spans, piece, bold, italic, strike, href)


def _leftover_pairs(spans: Inline, text: str, bold: bool, italic: bool, strike: bool, href: str | None) -> None:
    position = 0
    for match in _LEFTOVER_PAIR_RE.finditer(text):
        if match.start() > position:
            spans.append(Span(text[position:match.start()], bold, italic, strike, False, href))
        marker = match.group(1)
        _leftover_pairs(spans, match.group(2), bold or marker == "**", italic, strike or marker == "~~", href)
        position = match.end()
    if position < len(text):
        spans.append(Span(text[position:], bold, italic, strike, False, href))


def plain(spans: Inline) -> str:
    return "".join(span.text for span in spans)


# ───────────────────────────── 核心结论：第一句真话 ─────────────────────────────

_SENTENCE_END = "。！？!?；;"
_CONCLUSION_SOFT_LIMIT = 120
_CONCLUSION_HARD_LIMIT = 240
_CONCLUSION_LABEL = re.compile(
    r"^\s*(?:核心|总体|最终|直接)?(?:结论|总结|回答|答复|结果|一句话)\s*[：:]\s*|^\s*(?:conclusion|summary|answer|tl;?dr)\s*:\s*",
    re.IGNORECASE,
)


def _is_pseudo_heading(block: Paragraph) -> bool:
    """「**总体结论**」「结论：」这种自成一段的标签不是结论本身。"""
    text = plain(block.spans).strip()
    if not text:
        return True
    if text.endswith(("：", ":")) and len(text) <= 40:
        return True
    words = [span for span in block.spans if span.text.strip() and not span.brk]
    return bool(words) and all(span.bold for span in words) and len(text) <= 40 and not text.endswith(tuple(_SENTENCE_END))


def _paragraphs_in_reading_order(blocks: list[Block]) -> list[Paragraph]:
    out: list[Paragraph] = []
    for block in blocks:
        if isinstance(block, Paragraph):
            out.append(block)
        elif isinstance(block, ListBlock):
            for item in block.items:
                out.extend(_paragraphs_in_reading_order(item))
        elif isinstance(block, Quote):
            out.extend(_paragraphs_in_reading_order(block.children))
    return out


def _sentences(text: str) -> list[str]:
    pieces, current = [], ""
    for char in text:
        current += char
        if char in _SENTENCE_END:
            pieces.append(current)
            current = ""
    if current.strip():
        pieces.append(current)
    return [piece.strip() for piece in pieces if piece.strip()]


def first_statement(text: str) -> str:
    """解读正文里的第一句真话（核心结论卡用）：跳过标题、分隔线、表格、代码与自成一段的标签，取第一段正文的开头几句
    （至少一句、约 120 字内、封顶 240 字）。没有这样的句子回 ""——那时不印结论卡，不拿标题凑数。"""
    for block in _paragraphs_in_reading_order(parse(text)):
        if _is_pseudo_heading(block):
            continue
        # 只看这一段的第一行（单个换行就是换行，下一行是另一条）；删除线里的字是作者划掉的，不算。
        # 段首「结论：」这种与卡片标题重复的标签去掉（「日主甲木：身弱」的冒号前是内容，不动）。
        kept = "".join(span.text for span in block.spans if not span.strike)
        body = next((part.strip() for part in kept.split("\n") if part.strip()), "")
        label = _CONCLUSION_LABEL.match(body)
        if label and len(body) > label.end():
            body = body[label.end():]
        sentences = _sentences(body)
        if not sentences:
            continue
        picked = sentences[0]
        for sentence in sentences[1:]:
            if len(picked) + len(sentence) > _CONCLUSION_SOFT_LIMIT:
                break
            picked += sentence
        if len(picked) > _CONCLUSION_HARD_LIMIT:
            picked = picked[: _CONCLUSION_HARD_LIMIT - 1].rstrip() + "…"
        return picked
    return ""
