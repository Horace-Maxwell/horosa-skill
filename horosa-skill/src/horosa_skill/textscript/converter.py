"""简 → 繁（台湾 / 香港字形）与繁 → 简的字典转换器。

只用 OpenCC 1.4.2 的**文本字典**（`data/opencc/`，Apache-2.0）加本仓的术数词表（`data/horosa_s2t.txt`），
纯 Python，不依赖 `opencc` 包——官方包没有 Windows ARM64 轮子，装不上就等于这台机器用不了繁体。

算法 = OpenCC 的转换链：每一级是「词组字典 ∪ 单字字典」的最长正向匹配，前一级的输出喂给下一级。
s2tw / s2hk 两级：①（Horosa 词组表 ∪ STPhrases ∪ STCharacters）②（地区异体词组 ∪ 地区异体字），
最后按原文逐位重判术数用字（`horosa_char_rules.json`，与上游星阙界面简繁同一机制）。
省掉了 OpenCC 的 mmseg 预分词与兼容汉字归一化：2026-10-22 用官方 opencc 1.4.2 在 110 个技法的真实
输出（2 072 209 字）上逐字比对，未加术数词表时差异 0 字（tests/test_textscript.py 锁住了抽样）。

为什么术数字要逐位定、不能靠词组表：最长匹配先吃掉前一个字，「真实干支」切出「实干」→ 真實幹支、
「的历法」切出「的历」→ 的歷法——这类跨词错切补不完。逐位定字只看原文：该字落在白名单词里（冲击、克服、历史…）
取该词的写法，否则取术数缺省（沖 / 剋 / 曆 / 干 …）。白名单词自己也会跨词（「3 天后」「立春后土」），按左右邻字再判；
「克」「只」按上下文定（生克义作剋、量词作隻）。判据表与上游 hantRules.js 逐项相同（v3.13.0，测试比对）。
"""
from __future__ import annotations

import unicodedata
from functools import lru_cache
from importlib import resources

_DATA = "horosa_skill.textscript.data"


def _read(name: str) -> str:
    return resources.files(_DATA).joinpath(name).read_text(encoding="utf-8")


def _load(name: str) -> dict[str, str]:
    """`键\\t候选1 候选2…`：取第一个候选（OpenCC 的缺省）。`#` 开头与空行跳过。"""
    table: dict[str, str] = {}
    for line in _read(name).splitlines():
        if not line or line.startswith("#"):
            continue
        key, _, values = line.partition("\t")
        value = values.split("#", 1)[0].strip().split(" ")[0] if values else ""
        if key and value:
            table[key] = value
    return table


class _Stage:
    """一级转换：若干字典按优先级合并（靠前的覆盖靠后的同名键），再做最长正向匹配。"""

    __slots__ = ("table", "lengths")

    def __init__(self, *tables: dict[str, str]) -> None:
        merged: dict[str, str] = {}
        for table in reversed(tables):
            merged.update(table)
        lengths: dict[str, set[int]] = {}
        for key in merged:
            lengths.setdefault(key[0], set()).add(len(key))
        self.table = merged
        # 每个首字只试它真有的键长（多数字只有 1–3 种），比从最大键长逐一递减快一个数量级。
        self.lengths = {first: sorted(sizes, reverse=True) for first, sizes in lengths.items()}

    def apply(self, text: str) -> str:
        table, lengths = self.table, self.lengths
        out: list[str] = []
        i, n = 0, len(text)
        while i < n:
            sizes = lengths.get(text[i])
            if sizes is not None:
                for size in sizes:
                    if size <= n - i:
                        segment = text[i : i + size]
                        hit = table.get(segment)
                        if hit is not None:
                            out.append(hit)
                            i += size
                            break
                else:
                    out.append(text[i])
                    i += 1
            else:
                out.append(text[i])
                i += 1
        return "".join(out)


_VARIANTS = {
    "zh-Hant": ("TWVariantsPhrases.txt", "TWVariants.txt"),
    "zh-Hant-HK": ("HKVariantsPhrases.txt", "HKVariants.txt"),
}


@lru_cache(maxsize=1)
def _simplified_to_traditional() -> _Stage:
    return _Stage(_load("horosa_s2t.txt"), _load("opencc/STPhrases.txt"), _load("opencc/STCharacters.txt"))


@lru_cache(maxsize=2)
def _variants(script: str) -> _Stage:
    phrases, characters = _VARIANTS[script]
    return _Stage(_load(f"opencc/{phrases}"), _load(f"opencc/{characters}"))


@lru_cache(maxsize=1)
def _traditional_to_simplified() -> _Stage:
    return _Stage(_load("opencc/TSPhrases.txt"), _load("opencc/TSCharacters.txt"))


@lru_cache(maxsize=1)
def traditional_only_characters() -> frozenset[str]:
    """只出现在繁体里的字（是 TS 字典的键、又不是 ST 字典的键）。用来判断一段输入是不是繁体写的。"""
    traditional = set(_load("opencc/TSCharacters.txt"))
    return frozenset(traditional - set(_load("opencc/STCharacters.txt")))


def _has_cjk(text: str) -> bool:
    return any("㐀" <= ch <= "鿿" or "\U00020000" <= ch <= "\U0003134f" for ch in text)


# 引书的「云」（说）这类 quote 规则：后面紧跟冒号 / 引号时保持原字。
_QUOTE_FOLLOW = frozenset("：:「『“\"")
_BLANKS = frozenset(" \u3000\t")


def _is_boundary(ch: str) -> bool:
    """串首尾 / 标点 / 空白（上游 BOUNDARY_RE = /^[^\\p{L}\\p{N}]?$/u）。"""
    return not ch or unicodedata.category(ch)[0] not in "LN"


class _Rules:
    """`horosa_char_rules.json` 的预编译形态（与上游 hantRules.js 的 RULES / INDEX / *_GUARDS / *_CONTEXT 一一对应）。"""

    def __init__(self, doc: dict) -> None:
        self.rules: dict[str, dict] = doc["rules"]
        # 字 → [(词, 繁体写法, 该字在词中的位置)]，长词优先（同长保持 JSON 里的次序，与上游 INDEX 相同）
        self.index: dict[str, list[tuple[str, str, int]]] = {}
        for char, rule in self.rules.items():
            entries = [
                (word, traditional, offset)
                for word, traditional in rule["words"].items()
                if len(word) == len(traditional)
                for offset, letter in enumerate(word)
                if letter == char
            ]
            entries.sort(key=lambda item: -len(item[0]))
            self.index[char] = entries
        self.word_guards: dict[str, dict] = doc.get("word_guards", {})
        self.edge_guards: dict[str, dict] = doc.get("edge_guards", {})
        self.tail_guards: dict[str, dict] = doc.get("tail_guards", {})
        contexts = doc.get("contexts", {})
        ke = contexts.get("ke", {})
        self.ke_domain = frozenset(ke.get("domain", ""))
        self.ke_foreign = frozenset(ke.get("foreign", ""))
        self.ke_zhi_object = frozenset(ke.get("zhiObject", ""))
        self.zhi = {key: (frozenset(value) if isinstance(value, str) else tuple(value)) for key, value in contexts.get("zhi", {}).items()}
        place = doc.get("place_label", {})
        self.place_prefixes = tuple(place.get("prefixes", ()))
        self.place_keep = frozenset(place.get("keep", ""))

    def guards_of(self, char: str, word: str) -> list[dict]:
        """本词判据 / 词边字判据（以该字开头）/ 词尾字判据（以该字收尾）——都要通过才算命中。"""
        out = []
        if word in self.word_guards:
            out.append(self.word_guards[word])
        edge = self.edge_guards.get(char)
        if edge and word[0] == char and ("words" not in edge or word in edge["words"]):
            out.append(edge)
        tail = self.tail_guards.get(char)
        if tail and len(word) > 1 and word[-1] == char:
            out.append(tail)
        return out


@lru_cache(maxsize=1)
def _char_rules() -> _Rules:
    import json

    return _Rules(json.loads(_read("horosa_char_rules.json")))


def _neighbor(source: str, at: int, step: int) -> str:
    """跳过空白取邻字；出界回空串（不能用 Python 的负下标）。"""
    while 0 <= at < len(source) and source[at] in _BLANKS:
        at += step
    return source[at] if 0 <= at < len(source) else ""


def _at(source: str, index: int) -> str:
    return source[index] if 0 <= index < len(source) else ""


def _guard_allows(guard: dict, source: str, start: int, length: int) -> bool:
    left = _neighbor(source, start - 1, -1)
    right = _neighbor(source, start + length, 1)
    if guard.get("notLeft") and left and left in guard["notLeft"]:
        return False
    if guard.get("notRight") and right and right in guard["notRight"]:
        return False
    if guard.get("onlyLeft") and left and not _is_boundary(left) and left not in guard["onlyLeft"]:
        return False
    return not (guard.get("onlyLeftStrict") and (not left or left not in guard["onlyLeftStrict"]))


def _matches(source: str, start: int, word: str, traditional: str) -> bool:
    """白名单词逐字比：原文该位是简体写法或繁体写法都算（已转过的文字再转一次不变）。"""
    if start < 0 or start + len(word) > len(source):
        return False
    return all(source[start + k] in (word[k], traditional[k]) for k in range(len(word)))


def _ke_context(rules: _Rules, source: str, index: int) -> bool:
    """「克」属生克义：邻字属外文译名 / 地名 / 克 = 能 → 否；「克制」看「制」后一字；邻字属生克语境或单独成串 → 是。"""
    left, right = _at(source, index - 1), _at(source, index + 1)
    if left in rules.ke_foreign or right in rules.ke_foreign:
        return False
    if right == "制":
        return left in rules.ke_domain or _at(source, index + 2) in rules.ke_zhi_object
    if left in rules.ke_domain or right in rules.ke_domain:
        return True
    return _is_boundary(left) and _is_boundary(right)


def _zhi_left_chars(source: str, index: int, count: int) -> str:
    out: list[str] = []
    k = index - 1
    while k >= 0 and len(out) < count:
        if source[k] not in _BLANKS:
            out.insert(0, source[k])
        k -= 1
    return "".join(out)


def _zhi_noun_follows(rules: _Rules, source: str, k: int) -> bool:
    z = rules.zhi
    right, after = _at(source, k), _at(source, k + 1)
    if right + after in z["adverbRight2"]:
        return False
    if right in z["noun"]:
        return True
    return right in z["modifier"] and after != "" and after not in z["modifierNotNext"] and not _is_boundary(after)


def _zhi_is_classifier(rules: _Rules, source: str, index: int) -> bool:
    """「只」作量词「隻」：左邻是数词 / 量化 / 指示字（不计数的词、副词强搭配除外），或「是 / 有 / 牵…」+ 论「隻」的名词。"""
    z = rules.zhi
    left = _neighbor(source, index - 1, -1)
    if not left:
        return False
    k = index + 1
    while k < len(source) and source[k] in _BLANKS:
        k += 1
    right = _at(source, k)
    if left == "只":  # 一只只 / 两只只
        p = index - 1
        while p >= 0 and source[p] in _BLANKS:
            p -= 1
        return _zhi_is_classifier(rules, source, p)
    if left in z["nounOnly"]:
        return right != "" and not _is_boundary(right) and _zhi_noun_follows(rules, source, k)
    is_demo = left in z["demo"]
    if not is_demo and left not in z["num"]:
        return False
    lefts = _zhi_left_chars(source, index, 3)
    if left in z["demoAfterNum"] and (len(lefts) < 2 or lefts[-2] not in z["num"]):
        return False
    if any(lefts.endswith(w) for w in z["nonCountLeft"]) and not any(lefts.endswith(w) for w in z["nonCountNotLeft"]):
        return False
    if right == "" or _is_boundary(right):
        return True
    if right + _at(source, k + 1) in z["adverbRight2"]:
        return False
    if right in z["adverbNext"]:
        return False
    return not (is_demo and right in z["adverbNextDemo"])


_CONTEXTS = {"ke": _ke_context, "zhi": _zhi_is_classifier}


def _apply_char_rules(source: str, converted: str) -> str:
    """按**原文**逐位重判术数用字（与词典怎么切词无关）。与上游星阙 hantRules.js 的 applyHantDomainRules 同一算法：

    ① 串首是「出生地:」→ 整串音译地名，keep 里的字取原字；
    ② 白名单词命中（原文该位是简体或繁体写法都算）且左右邻判据都通过 → 取该词的写法；判据否决且带 alt → 取 alt；
    ③ 有上下文判定的字（克 / 只）按上下文；引书「云」后接冒号 / 引号保持；否则取缺省字（null = 随词典）。

    **唯一不跟的一步**：上游另有「原文已是繁体则不改」（某位左右紧邻繁体专用字 → 该位若是繁体通行字就照原文，
    对所有字生效），用来让已转过的文字再转一次不变。本仓不收（见 JSON 的 `algorithm_deviations`）：出口只转一次、
    原文永远是简体，用不着它；而引擎输出里有简繁混排的上游原文（「忙里偷閒，動里求靜」），它会把「里」留成简体写法。

    所有字典条目逐码点等长（测试锁），原文与译文按位对齐；万一不等长（字典升级），原样退回词典结果。
    """
    if len(source) != len(converted):
        return converted
    rules = _char_rules()
    place_label = bool(rules.place_prefixes) and source.startswith(rules.place_prefixes)
    if not place_label and not any(char in rules.rules for char in source):
        return converted
    out = list(converted)
    for index, char in enumerate(source):
        if place_label and char in rules.place_keep:
            out[index] = char
            continue
        rule = rules.rules.get(char)
        if rule is None:
            continue
        chosen: str | None = None
        vetoed: dict | None = None
        for word, traditional, offset in rules.index[char]:
            start = index - offset
            if not _matches(source, start, word, traditional):
                continue
            failed = next((g for g in rules.guards_of(char, word) if not _guard_allows(g, source, start, len(word))), None)
            if failed is not None:
                vetoed = vetoed or failed
                continue
            chosen = traditional[offset]
            break
        if chosen is None and vetoed is not None and vetoed.get("alt"):
            chosen = vetoed["alt"]
        if chosen is None:
            default, context = rule.get("default"), rule.get("ctx")
            if context and rule.get("ctxHit"):
                chosen = rule["ctxHit"] if _CONTEXTS[context](rules, source, index) else default
            elif context:
                chosen = default if _CONTEXTS[context](rules, source, index) else out[index]
            elif rule.get("quote") and _at(source, index + 1) in _QUOTE_FOLLOW:
                chosen = char
            else:
                chosen = out[index] if default is None else default
        out[index] = chosen
    return "".join(out)


@lru_cache(maxsize=512)
def to_traditional(text: str, script: str) -> str:
    if script not in _VARIANTS:
        raise ValueError(f"不支持的文字：{script} / unsupported script: {script}")
    if not _has_cjk(text):
        return text
    return _apply_char_rules(text, _variants(script).apply(_simplified_to_traditional().apply(text)))


@lru_cache(maxsize=512)
def to_simplified(text: str) -> str:
    if not _has_cjk(text):
        return text
    return _traditional_to_simplified().apply(text)
