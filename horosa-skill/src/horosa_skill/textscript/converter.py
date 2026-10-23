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
取该词的写法，否则取术数缺省（沖 / 剋 / 曆 / 干 …）。
"""
from __future__ import annotations

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


@lru_cache(maxsize=1)
def _char_rules() -> dict[str, tuple[str | None, bool, list[tuple[str, str, int]]]]:
    """术数用字逐位定字表：字 → (缺省, 是否引书规则, [(白名单词, 繁体写法, 该字在词中的位置)]，长词优先)。"""
    import json

    rules = json.loads(_read("horosa_char_rules.json"))["rules"]
    table: dict[str, tuple[str | None, bool, list[tuple[str, str, int]]]] = {}
    for char, rule in rules.items():
        words = [
            (word, traditional, offset)
            for word, traditional in rule["words"].items()
            for offset, letter in enumerate(word)
            if letter == char
        ]
        words.sort(key=lambda item: -len(item[0]))
        table[char] = (rule.get("default"), bool(rule.get("quote")), words)
    return table


def _apply_char_rules(source: str, converted: str) -> str:
    """按**原文**逐位重判术数用字（与词典怎么切词无关）：落在白名单词里取该词的写法，否则取缺省字。

    与上游星阙 hantRules.js 的 applyHantDomainRules 同一算法。所有字典条目逐码点等长（测试锁），原文与译文按位对齐；
    万一不等长（字典升级），原样退回词典结果。
    """
    rules = _char_rules()
    if len(source) != len(converted) or not any(char in rules for char in source):
        return converted
    out = list(converted)
    for index, char in enumerate(source):
        rule = rules.get(char)
        if rule is None:
            continue
        default, quote, words = rule
        chosen = out[index] if default is None else default
        hit = False
        for word, traditional, offset in words:
            start = index - offset
            if start >= 0 and source.startswith(word, start):
                chosen, hit = traditional[offset], True
                break
        if not hit and quote and index + 1 < len(source) and source[index + 1] in _QUOTE_FOLLOW:
            chosen = char
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
