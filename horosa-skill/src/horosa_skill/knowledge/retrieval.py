"""检索的共用部件：归一、切词、计数、BM25、倒数排名融合、零命中改写。

内置知识（store.py）和自备知识库（index.py）是两个语料源，打分规则只有这一份。此前各写一套，同一个概念两边
行为不同（西文一边按词一边按子串，字段权重一边有一边没有），问题就出在这种漂移上（docs/LESSONS.md v0.47.2-dev）。

这个模块不依赖 store / index / user：依赖方向是它们指向这里。
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

_HAN = r"㐀-䶿一-鿿豈-﫿\U00020000-\U0003134f"
CJK_RUN = re.compile(f"[{_HAN}]+")
TOKEN = re.compile(f"[{_HAN}]+|[0-9a-z_]+")

BM25_K1, BM25_B = 1.2, 0.75
RRF_K = 60  # Cormack, Clarke & Büttcher 2009；Elasticsearch / FastGPT / Cherry Studio 同值
FIELD_WEIGHTS = {"title": 4.0, "heading": 3.0, "tags": 3.0, "body": 1.0}
# 同一个术语的不同写法。查询时两边都搜：改的是查询，不是索引（改 normalize 要重建全部用户索引，也会动摘要定位）。
SPELLING_VARIANTS = (("羊刃", "阳刃"), ("螣蛇", "腾蛇"), ("玄武", "元武"), ("七杀", "七煞"), ("调候", "调侯"))
_VARIANT_OF = {spelling: other for pair in SPELLING_VARIANTS for spelling, other in (pair, pair[::-1])}


def normalize(text: str) -> str:
    """建索引与查询共用：NFKC（全角→半角）→ 繁→简 → casefold。"""
    from horosa_skill.textscript import fold_to_simplified

    return fold_to_simplified(unicodedata.normalize("NFKC", text)).casefold()


def run_grams(run: str) -> list[str]:
    return [run] if len(run) == 1 else [run[i : i + 2] for i in range(len(run) - 1)]


def grams(text: str) -> list[str]:
    """归一后的切词：汉字段 → 相邻双字（单字段保留单字），西文 / 数字 → 整词。"""
    out: list[str] = []
    for match in TOKEN.finditer(normalize(text)):
        token = match.group(0)
        out.extend(run_grams(token) if CJK_RUN.fullmatch(token) else [token])
    return out


@dataclass(frozen=True)
class Query:
    phrases: tuple[tuple[str, ...], ...]  # 每个词的双字序列（给 FTS）
    singles: tuple[str, ...]  # 单个汉字的词：FTS 里没有对应的双字，走子串回退
    terms: tuple[str, ...]  # 归一后的原词（做摘要定位、子串回退用）
    phrase_tokens: tuple[tuple[str, ...], ...] = ()  # 与 phrases 对齐的原词切分：数原文里出现几次靠它

    @property
    def empty(self) -> bool:
        return not (self.phrases or self.singles)

    @property
    def scored(self) -> tuple[tuple[str, ...], ...]:
        """参与计分的全部词（单字也算），每个词是 term_count 要的 tokens。"""
        return (*self.phrase_tokens, *((single,) for single in self.singles))

    def fts(self) -> str:
        # 只有引号里的双字 / [0-9a-z_] 词进 MATCH：查询文本里的 FTS 语法字符（* ^ : NEAR）一律到不了解析器。
        return " OR ".join('"' + " ".join(phrase) + '"' for phrase in self.phrases)


def parse_query(query: str) -> Query:
    phrases: list[tuple[str, ...]] = []
    tokens_of: list[tuple[str, ...]] = []
    singles: list[str] = []
    terms: list[str] = []
    words = re.split(r"[\s,，、;；|/]+", str(query or ""))
    words += [_VARIANT_OF[word] for word in map(normalize, words) if word in _VARIANT_OF]
    for raw in words:
        term = normalize(raw)
        tokens = TOKEN.findall(term)
        if not tokens:
            continue
        joined = "".join(tokens)
        if joined in terms:
            continue
        terms.append(joined)
        if len(tokens) == 1 and CJK_RUN.fullmatch(tokens[0]) and len(tokens[0]) == 1:
            singles.append(tokens[0])
            continue
        phrase: list[str] = []
        for token in tokens:
            phrase.extend(run_grams(token) if CJK_RUN.fullmatch(token) else [token])
        phrases.append(tuple(phrase))
        tokens_of.append(tuple(tokens))
    return Query(tuple(phrases), tuple(singles), tuple(terms), tuple(tokens_of))


@lru_cache(maxsize=512)
def _term_pattern(tokens: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"(?<![0-9a-z_])" + r"\W*".join(map(re.escape, tokens)) + r"(?![0-9a-z_])")


def term_count(text: str, tokens: tuple[str, ...]) -> int:
    """词在归一文本里出现几次。纯中文按子串；含西文按词（`sun` 不算 `sunshine` 里的）。

    不许把双字序列拼起来当子串数：「紫微 微斗 斗数」拼成「紫微微斗斗数」，这串字不可能出现在任何文本里，
    于是三字以上的中文词一律 0 分（2026-11-06 审计抓到，排序全靠 FTS5 的先后）。
    """
    if len(tokens) == 1 and CJK_RUN.fullmatch(tokens[0]):
        return text.count(tokens[0])
    return len(_term_pattern(tokens).findall(text))


def bm25(tf: float, df: int, n_docs: int, length: int, avg_len: float) -> float:
    """Lucene 的 IDF（恒为正）+ 标准 BM25 饱和。`tf` 可以是字段加权后的。"""
    if not tf:
        return 0.0
    idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
    return idf * tf * (BM25_K1 + 1) / (tf + BM25_K1 * (1 - BM25_B + BM25_B * length / avg_len))


def rrf(rankings: Sequence[Iterable[Any]], *, key: Callable[[Any], Any] = lambda item: item) -> list[tuple[Any, float]]:
    """倒数排名融合：只看名次不看分数（不同来源的分数不同尺度）。同分按各榜名次依次决胜，再按首次出现的先后，结果确定。

    调研里同分靠插入顺序决胜就排错过一次。返回 [(条目, 融合分)]，融合分没有归一。
    """
    slots: dict[Any, list[Any]] = {}
    for position, ranking in enumerate(rankings):
        for rank, item in enumerate(ranking):
            identity = key(item)
            slot = slots.setdefault(identity, [0.0, [float("inf")] * len(rankings), item, len(slots)])
            slot[0] += 1 / (RRF_K + rank + 1)
            slot[1][position] = min(slot[1][position], rank)
    ordered = sorted(slots.values(), key=lambda slot: (-slot[0], *slot[1], slot[3]))
    return [(slot[2], slot[0]) for slot in ordered]


# ───────────────────────────── 零命中改写 ─────────────────────────────

# 问句外壳：长的在前。只在整句零命中时才用，不影响正常查询。
_QUESTION_WORDS = (
    "是什么意思", "什么意思", "是什么", "什么是", "什么叫", "是怎么算的", "怎么算的", "怎么解读", "怎么看", "怎样看", "怎么样",
    "怎么办", "怎么", "怎样", "如何",
    "为什么", "为何", "有什么", "有哪些", "哪些", "哪个", "能不能", "可不可以", "有没有", "代表什么", "代表", "意味着",
    "的意思", "的含义", "含义", "意思", "请问", "请解释一下", "请解释", "解释一下", "解释", "帮我看看", "帮我看", "看看", "区别",
    "有什么不同", "什么不同", "在哪里看", "在哪里", "在哪儿", "哪里", "哪一天", "哪天", "一下",
    # 「我想了解一下比较盘」「我笔记里关于七杀的内容」：说的是去哪儿找、找什么，不是要找的词（2026-11-11 深审 K-1 / N3）
    "我想了解一下", "我想了解", "想了解一下", "了解一下", "我想知道", "想知道", "告诉我", "我的笔记里", "我笔记里", "笔记里",
    "笔记中", "相关的内容", "相关内容", "的内容", "关于", "有关",
)
_QUESTION_SHELL = tuple(sorted(_QUESTION_WORDS, key=len, reverse=True))  # 长的先剥：「有什么不同」不能先被「有什么」切掉
# 虚词：跳过它们几乎不算代价，也不算「没覆盖的字」。「里」「这」「个」此前不在表里，「八字里的用神」就被切成「八 / 字里 / 用神」。
_PARTICLES = frozenset("的和与及或跟吗呢吧啊呀了是在有要会能我你他她它里这那些个么把被给从于该")
_NEVER_INSIDE_A_TERM = frozenset("的吗呢吧啊呀了")  # 「斗数的四化」在语料里连着出现过，但它不是一个词
_MAX_SEGMENT = 6
_MAX_RUN = 48
_COMMON_SHARE = 0.4  # 语料里四成以上的文档都有的词，不算线索
_MIN_DOCS_FOR_COMMON = 20  # 语料太小时比例没有意义（五条笔记里两条都写的词照样是线索）


_VOCAB_PIECE, _ATTESTED_PIECE = 1.0, 1.75  # 语料自己标出来的词（标题 / 小节名 / 加粗）比「碰巧连着出现过」的字串便宜


def _segment(run: str, attested: Callable[[str], bool], vocabulary: frozenset[str] | None = None) -> list[str]:
    """把无空格的一串字切成语料里确实出现过的词：代价最小者胜，长词优先。

    不用 jieba：它的词典是现代汉语，古籍里的「伤官见官」切不对。这里的词典就是语料本身：`vocabulary` 是语料自己标出来的词
    （条目名、小节名、加粗词），一段 1；只是在语料里连着出现过的字串一段 1.75（没给词表时也是 1）；跳过虚词 0.5，跳过别的字 2。
    「八字里的用神」：「八字 / 里 / 的 / 用神」= 3，比「八 / 字里 / 的 / 用神」= 5.25 便宜——此前两种切法同价，切错了。
    """
    n = len(run)
    attested_cost = _ATTESTED_PIECE if vocabulary is not None else _VOCAB_PIECE
    best: list[tuple[float, list[str]]] = [(0.0, [])] + [(math.inf, []) for _ in range(n)]
    for i in range(n):
        cost, path = best[i]
        if cost == math.inf:
            continue
        skipped = cost + (0.5 if run[i] in _PARTICLES else 2.0)
        if skipped < best[i + 1][0]:
            best[i + 1] = (skipped, path)
        for size in range(min(_MAX_SEGMENT, n - i), 1, -1):
            piece = run[i : i + size]
            if not _NEVER_INSIDE_A_TERM.isdisjoint(piece):
                continue
            price = _VOCAB_PIECE if vocabulary is not None and piece in vocabulary else attested_cost
            if cost + price < best[i + size][0] and attested(piece):
                best[i + size] = (cost + price, [*path, piece])
    return best[n][1]


def cached(function: Callable[[str], int]) -> Callable[[str], int]:
    """改写要反复问同一批词的 df：一次改写内记住。"""
    seen: dict[str, int] = {}

    def lookup(term: str) -> int:
        if term not in seen:
            seen[term] = function(term)
        return seen[term]
    return lookup


def expand_query(query: str, df: Callable[[str], int], n_docs: int, vocabulary: frozenset[str] | None = None) -> str | None:
    """整句零命中时改写：去掉问句外壳，把连在一起的词切开，返回用空格分好的查询；改写不可靠就 None。

    「什么是空亡」→「空亡」，「太阳天蝎」→「太阳 天蝎」。`df(词)` = 语料里有几个文档含这个词。

    可靠 = 查询几乎每个字都落在语料里出现过的词上（最多剩一个字，长句剩四分之一；带问句外壳时剩一半：
    「塔罗怎么读牌」明确在问塔罗，「读牌」没出现过不妨碍）。语料有十几万字，「今天天气真好」里总能凑出「今天」「天气」；
    没有这条线，胡乱的查询会换来一堆看着像答案的噪音，比零命中更糟。

    `vocabulary`（2026-11-11 深审 K-1）：语料自己的词表，切词时优先；不给就只按「出现过没有」切（旧行为）。
    问句里没落在词上的字：连着两个以上的才留作单字弱线索（「塔罗怎么读牌」的「读」「牌」），孤零零一个的（「怎么选」的「选」）丢掉。
    """
    text = normalize(query)
    stripped = text
    for word in _QUESTION_SHELL:
        stripped = stripped.replace(word, " ")
    asked = stripped != text
    pieces: list[str] = []
    loose: list[str] = []
    wanted = covered = 0
    common = _COMMON_SHARE * n_docs if n_docs >= _MIN_DOCS_FOR_COMMON else math.inf
    for token in TOKEN.findall(stripped):
        if not CJK_RUN.fullmatch(token):
            wanted += len(token)
            if df(token) > 0:
                pieces.append(token)
                covered += len(token)
            continue
        wanted += sum(1 for char in token if char not in _PARTICLES)
        found = _segment(token[:_MAX_RUN], lambda term: df(term) > 0, vocabulary)
        for piece in found:
            solid = sum(1 for char in piece if char not in _PARTICLES)
            covered += solid
            if solid and df(piece) <= common and piece not in pieces:
                pieces.append(piece)
        if asked:  # 问句里没落在词上、连着两个以上的字留作弱线索：「塔罗怎么读牌」的「读」「牌」能把读牌那一节带上来
            loose.extend(_loose_runs(token, found))
    if not pieces or wanted - covered > max(1, wanted // (2 if asked else 4)):
        return None
    pieces.extend(char for char in dict.fromkeys(loose) if df(char) > 0)
    rewritten = " ".join(pieces)
    return rewritten if rewritten != normalize(query).strip() else None


def _loose_runs(token: str, found: list[str]) -> list[str]:
    """token 里没被切进任何词、也不是虚词的字，只取连着两个以上的那几段（逐字）。"""
    covered = [False] * len(token)
    start = 0
    for piece in found:
        at = token.find(piece, start)
        if at < 0:
            continue
        covered[at : at + len(piece)] = [True] * len(piece)
        start = at + len(piece)
    out: list[str] = []
    run: list[str] = []
    for char, inside in [*zip(token, covered, strict=True), ("", True)]:
        if inside or char in _PARTICLES:
            if len(run) >= 2:
                out.extend(run)
            run = []
        else:
            run.append(char)
    return out


# 英文问句外壳（只在查询全是拉丁字母时剥）：语料是中文写的，「what is a solar arc」里有用的只有 solar arc。
_ENGLISH_SHELL = frozenset({
    "what", "whats", "what's", "is", "are", "was", "a", "an", "the", "how", "to", "do", "does", "did", "i", "my", "me", "of", "in",
    "on", "for", "about", "mean", "means", "meaning", "explain", "define", "definition", "read", "reading", "interpret", "please",
    "tell", "chart", "charts", "work", "works", "use", "can", "you", "show", "find",
})


def apply_aliases(query: str, aliases: dict[str, str]) -> tuple[str, list[tuple[str, str]]]:
    """查询里出现的英文术语换成语料里的中文词（最长匹配、整词），全英文的查询再剥掉问句外壳。

    返回 (改写后的查询, [(英文, 中文)…])；什么都没换就原样返回、列表为空。别名表只收语料自己中英对照过的词
    （store.TERM_ALIASES，测试守），不替语料没有的词编译名。"""
    text = normalize(query).strip()
    if not re.search(r"[a-z]", text):
        return query, []
    used: list[tuple[str, str]] = []
    for english in sorted(aliases, key=len, reverse=True):
        pattern = re.compile(r"(?<![0-9a-z])" + re.escape(english).replace(r"\ ", r"[\s\-]+") + r"(?![0-9a-z])")
        if pattern.search(text):
            text = pattern.sub(f" {aliases[english]} ", text)
            used.append((english, aliases[english]))
    if not CJK_RUN.search(normalize(query)):
        words = text.split()
        kept = [word for word in words if word not in _ENGLISH_SHELL]
        if kept and len(kept) < len(words):
            text = " ".join(kept)
            used.append(("(question words)", ""))
    text = " ".join(text.split())
    return (text, used) if used and text != normalize(query).strip() else (query, [])


def snippet(text: str, terms: Iterable[str], width: int = 160) -> str:
    """命中词附近的一段原文（不是归一后的文本）。"""
    position = _locate(text, terms)
    start = max(position - width // 4, 0) if position >= 0 else 0
    piece = " ".join(text[start : start + width].split())
    return ("…" if start else "") + piece + ("…" if start + width < len(text) else "")


def _locate(text: str, terms: Iterable[str]) -> int:
    """词在**原文**里的位置。NFKC 会把「…」展开成三个点，归一文本的下标不能直接用在原文上。"""
    folded = normalize(text)
    found = next((at for at in (folded.find(term) for term in terms) if at >= 0), -1)
    if found < 0 or len(folded) == len(text):
        return found
    offset = 0
    for index, char in enumerate(text):
        offset += len(normalize(char))
        if offset > found:
            return index
    return -1
