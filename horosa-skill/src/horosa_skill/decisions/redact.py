"""一档（meta）状态的本地脱敏：用户原话离机前，凡是可能是出生数据 / 身份 / 地点的写法一律换成带类型的占位符，再按长度截断。

设计（2026-11-11 深审 J1）：此前是一张「日期长什么样」的正则清单——「一九九〇年五月三日辰时」「May 3, 1990」
「农历庚午年四月初九」「北纬31度」「Shanghai」「我叫王小明」都原样离机。现在按**构造**保证，而不是靠清单补漏：

  1. **任何一串数字**（ASCII、全角、其他文字的数字）最后一律变 `<数字>`——不管它像不像日期；能认出类型的先按类型换
     （日期 / 时刻 / 坐标 / 电话 / 证件号 / 年龄），认不出的也不会以原值离机。
  2. 汉字数字的年月日时（一九九〇年、五月初三、八点半、十二时）、干支（庚午、甲子日）、时辰（辰时、子时）、生肖（属马）。
  3. 英文月份日期与钟点（May 3、3rd of May、8:15pm、8am）。
  4. 坐标（31n14、31.2304, 121.4737、北纬31度14分、lat 31.2）。
  5. 星阙地名库里的**每一个**地名（中文名 / 英文名 / 拼音 / 连写拼音，繁简都认）与本机命主档案的名字 / 别名 / 地点标签。
  6. 「我叫 / 名叫 / 姓名 / my name is」之类引出的人名、「我姓王」。
  7. 邮箱、手机号、身份证号；带门牌号的街道。

认不出的（如实写进 README 隐私表）：不经上面引导词、单独出现的人名（「我老公李雷」）；不带门牌号的街道、小区、单位名；
地名库里没有、也不带 省/市/县/区/镇/乡/村 后缀的小地名；「三十五」这类不带单位的汉字数字。

复杂度：每一步都是线性扫描（量词都有上界；空白先压成一个空格；词库按「首字 → 长度」查表），并且先把输入截到
MAX_INPUT_CHARS——此前 `\\s*` 前缀的模式在 8 万个空格上要 43 秒（C-21）。
幂等：占位符所在的片段不再处理；整条流程跑到不动点（最多三遍）。
"""

from __future__ import annotations

import json
import os
import re
import threading
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

MAX_STATE_CHARS = 1200
# 截断在脱敏之后做；之前先按这个长度截一刀，保证任何输入的工作量都有上界。数字一律会被换掉，截在一个日期中间也不漏。
MAX_INPUT_CHARS = 8 * MAX_STATE_CHARS
_TRUNCATION_MARK = "…<截断>"

_PLACEHOLDER = {
    "email": "<邮箱>",
    "id_number": "<证件号>",
    "phone": "<电话>",
    "coordinate": "<坐标>",
    "date": "<日期>",
    "time": "<时刻>",
    "age": "<年龄>",
    "ganzhi": "<干支>",
    "shichen": "<时辰>",
    "zodiac": "<生肖>",
    "place": "<地点>",
    "address": "<地址>",
    "profile": "<档案>",
    "name": "<姓名>",
    "number": "<数字>",
}
# 英文引导词引出的人名：先于地名库（「name Alice Wang」里的 Alice 也是地名，先按地名换掉就认不出后面的姓了）。
_LATIN_NAME: _Rule = ("name", re.compile(
    r"((?i:(?<![A-Za-z])(?:my name is|my name's|name is|named|call me|i am called|i'm called|name)) ?[:：]? ?)"
    r"[A-Z][A-Za-z'\-]{0,30}(?: [A-Z][A-Za-z'\-]{0,30}){0,2}"), lambda match: match.group(1) + _PLACEHOLDER["name"])
# 本模块自己产的占位符（再跑一次时原样跳过）。只认这几个：用户自己写的「<妈妈>」照样脱敏。
_PLACEHOLDER_RE = re.compile("|".join(re.escape(token) for token in (*_PLACEHOLDER.values(), "<截断>")))
# 全角数字 / 字母 / 全角空格折成半角（「１９９０」与「1990」同样处理）；全角标点（，。：）原样保留，问题文本不必要的字节不变。
_WIDE = {code: code - 0xFEE0 for start, end in ((0xFF10, 0xFF19), (0xFF21, 0xFF3A), (0xFF41, 0xFF5A)) for code in range(start, end + 1)}
_WIDE[0x3000] = 0x20
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACE = re.compile(r"\s+")

# ───────────────────────────── 模式（量词全有上界；空白已压成单个空格，所以只写 ` ?`） ─────────────────────────────

_CJK = r"\u3400-\u9fff\uf900-\ufaff"
_HAN_DIGIT = "〇零○一二三四五六七八九十百千两壹贰叁肆伍陆柒捌玖拾廿卅"
_N = f"[{_HAN_DIGIT}]"
_STEM, _BRANCH = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
_DAYPART = r"(?:凌晨|清晨|早上|早晨|上午|中午|下午|傍晚|晚上|夜里|夜间|半夜|深夜|早|晚)"
_MONTH = (r"(?:January|February|March|April|June|July|August|September|October|November|December"
          r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec|May)\.?")
_ORD = r"(?:st|nd|rd|th)?"
_AMPM = r"(?:[ap]\.?m\.?|o'?clock)"
_A0, _A1 = r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9])"  # 拉丁词边界：`\b` 在「我是May」里不成立（汉字也算 \w）
_KIN = "我|他|她|老公|老婆|丈夫|妻子|爱人|孩子|儿子|女儿|妈妈|爸爸|母亲|父亲|朋友|男友|女友|对象|同事|客户"


def _rx(pattern: str, flags: int = 0) -> re.Pattern[str]:
    return re.compile(pattern, flags)


# (类型, 模式, 替换)。替换是占位符，或一个保留引导词、只换掉值的函数。顺序有意义：先认带类型的，最后数字兜底。
_Rule = tuple[str, re.Pattern[str], Callable[[re.Match[str]], str] | None]


def _keep_lead(kind: str) -> Callable[[re.Match[str]], str]:
    return lambda match: match.group(1) + _PLACEHOLDER[kind]


_RULES: tuple[_Rule, ...] = (
    ("email", _rx(r"[^\s@<>]{1,64}@[^\s@<>]{1,253}"), None),
    ("id_number", _rx(r"(?<!\d)\d{17}[\dXx](?![\dA-Za-z])|(?<!\d)\d{15}(?!\d)"), None),
    ("phone", _rx(r"(?:\+ ?\d{1,3}[ -]?)?(?<!\d)1[3-9]\d[ -]?\d{4}[ -]?\d{4}(?!\d)"), None),
    ("phone", _rx(r"\+ ?\d{1,3}(?:[ -]?\d{2,4}){2,4}(?!\d)"), None),
    # 坐标
    ("coordinate", _rx(r"(?<![A-Za-z0-9])\d{1,3}(?:\.\d{1,8})? ?[nNsSeEwW] ?\d{1,2}(?:\.\d{1,8})?(?![A-Za-z0-9])"), None),
    ("coordinate", _rx(r"[-+]?\d{1,3}\.\d{2,8}(?: ?[°º])?(?: ?[NSEWnsew](?![A-Za-z]))? ?[,，] ?[-+]?\d{1,3}\.\d{2,8}(?: ?[°º])?(?: ?[NSEWnsew](?![A-Za-z]))?"), None),
    ("coordinate", _rx(rf"(?:北纬|南纬|东经|西经|北緯|南緯|東經|西經) ?[\d{_HAN_DIGIT}.]{{1,10}} ?[度°]?"
                       rf"(?: ?[\d{_HAN_DIGIT}.]{{1,8}} ?[分′'])?(?: ?[\d{_HAN_DIGIT}.]{{1,8}} ?[秒″\"])?"), None),
    ("coordinate", _rx(r"(?i:\b(?:latitude|longitude|lat|lon|lng))\b ?[:=]? ?[-+]?\d{1,3}(?:\.\d{1,8})?(?: ?[°º])?(?: ?[NSEWnsew](?![A-Za-z]))?"), None),
    # 阿拉伯数字的日期 / 时刻 / 年龄
    ("date", _rx(r"\d{2,4} ?[-/年.] ?\d{1,2} ?[-/月.] ?\d{1,2}(?: ?[日号號])?"), None),
    ("date", _rx(r"(?<!\d)\d{1,2} ?[-/.] ?\d{1,2} ?[-/.] ?\d{2,4}(?!\d)"), None),
    ("date", _rx(r"(?<!\d)\d{1,2} ?月 ?\d{1,2}(?: ?[日号號])?"), None),
    ("date", _rx(r"(?<!\d)\d{2,4} ?年(?: ?\d{1,2} ?月)?"), None),
    ("date", _rx(rf"(?i:{_A0}{_MONTH} ?\d{{1,2}}{_ORD}(?:,? ?\d{{2,4}})?{_A1})"), None),
    ("date", _rx(rf"(?i:(?<!\d)\d{{1,2}}{_ORD} ?(?:of )?{_MONTH}(?:,? ?\d{{2,4}})?{_A1})"), None),
    ("date", _rx(rf"(?i:{_A0}{_MONTH},? ?\d{{4}}{_A1})"), None),
    ("time", _rx(rf"(?i:(?<!\d)\d{{1,2}} ?[:：] ?\d{{2}}(?: ?[:：] ?\d{{2}})?(?: ?{_AMPM})?)"), None),
    ("time", _rx(rf"(?i:(?<!\d)\d{{1,2}} ?{_AMPM})"), None),
    ("time", _rx(rf"{_DAYPART}? ?(?<!\d)\d{{1,2}} ?[点點时時] ?(?: ?(?:半|一刻|三刻|整|钟|鐘|\d{{1,2}} ?分?))?(?!辰)"), None),
    ("age", _rx(r"(?<!\d)\d{1,3} ?(?:岁|歲|周岁|週歲|years? old)"), None),
    # 汉字数字的日期 / 时刻 / 年龄
    ("date", _rx(rf"{_N}{{2,6}} ?年"), None),
    ("date", _rx(rf"(?:闰|閏)? ?(?:{_N}{{1,3}}|正|冬|腊|臘) ?月(?: ?(?:初|廿|卅)?{_N}{{0,3}} ?[日号號]?)?"), None),
    ("date", _rx(rf"初{_N}{{1,2}}|{_N}{{1,3}} ?[日号號](?![本子常])"), None),
    ("time", _rx(rf"{_DAYPART}? ?{_N}{{1,3}} ?[点點](?: ?(?:半|一刻|三刻|整|钟|鐘|{_N}{{1,3}} ?分?))?"), None),
    ("time", _rx(rf"{_N}{{1,3}} ?[时時](?![辰间間候])(?: ?{_N}{{1,3}} ?分)?"), None),
    ("age", _rx(rf"{_N}{{1,4}} ?(?:岁|歲)"), None),
    # 干支、时辰、生肖
    ("ganzhi", _rx(rf"[{_STEM}][{_BRANCH}](?: ?[年月日时時柱])?"), None),
    ("shichen", _rx(rf"(?<![孩儿兒妻弟男女])[早晚]?[{_BRANCH}] ?[时時](?![候间間])(?:[初正])?"), None),
    ("zodiac", _rx(r"(属|屬)[鼠牛虎兔龙龍蛇马馬羊猴鸡雞狗猪豬]"), _keep_lead("zodiac")),
    # 引导词引出的人名
    ("name", _rx(rf"((?:我的名字是|我名叫|名字叫|名字是|姓名(?:是|为|為)?|名叫|(?:{_KIN})叫|叫我) ?[:：]? ?)[{_CJK}·]{{2,4}}"),
     _keep_lead("name")),
    ("name", _rx(r"(我姓|姓氏(?:是)?)[\u3400-\u9fff]{1,2}"), _keep_lead("name")),
    # 带门牌号的街道；不带地名库地名的「XX市 / XX区」
    ("address", _rx(rf"[{_CJK}]{{1,8}}(?:路|街|大道|大街|巷|弄|胡同|里) ?[\d{_HAN_DIGIT}]{{1,5}} ?[号號弄栋棟]"), None),
    # 后缀前的字排除了「城市 / 股市 / 小区 / 误区 / 家乡 / 农村 / 反省」这类普通词。
    ("place", _rx(rf"[{_CJK}]{{2,7}}(?:特别行政区|特別行政區|自治区|自治區|自治州|自治县|自治縣|(?<![节節反不])省"
                  rf"|(?<![城股超都夜上菜门門开開黑闹鬧集早])市|(?<![城])[县縣]|(?<![地社小误誤景禁园園专專山郊市城灾災校营營辖轄])[区區]"
                  rf"|(?<![城])[镇鎮]|(?<![家老故他下城])[乡鄉]|(?<![农農乡鄉山渔漁])村)"), None),
    # 兜底：剩下的任何一串数字（含全角、其他文字的数字）与三位以上的汉字数字串
    ("number", _rx(r"\d+"), None),
    ("number", _rx("[〇零○一二三四五六七八九]{3,}"), None),
)

# ───────────────────────────── 词库：地名库 + 本机档案名（按「首字 → 长度」查表，线性） ─────────────────────────────

# 地名库里与本仓技法词撞车的英文 / 拼音词：它们在技法描述里是术语而不是地点，不换（tests 守：新撞车必须在这里或下一张表里表态）。
PLACE_TERM_EXEMPT = frozenset({
    "asia", "babylon", "bake", "best", "bradley", "converse", "date", "fortuna", "hard", "hope", "jupiter", "long",
    "natal", "rain", "reading", "real", "roman", "same", "side", "split", "sunrise", "tara", "time",
    "guiren", "panshi", "sanhe", "sanyuan", "shiji", "suan", "wangji", "wuhe", "xiaoxian", "zhongxian",
})
# 只取省 / 市一级的词干：县、区、镇的词干多是普通词（平安、吉利、万年、朝阳），换掉它们只会把问题打碎。
_ADMIN_SUFFIX = re.compile("(?:特别行政区|特別行政區|自治区|自治區|地区|地區|省|市)$")
_MIN_LATIN = 3  # 少于三个字母的不换（国家代码等认不出人，只会把英文句子打碎）；正好三个字母的只认原样大小写
_MAX_TERM = 80


def _fold_char(char: str) -> str:
    folded = _fold_one(char)
    return folded if len(folded) == 1 else char


@lru_cache(maxsize=8192)
def _fold_one(char: str) -> str:
    from horosa_skill.textscript import to_simplified

    lowered = char.lower()
    if len(lowered) != 1:
        lowered = char
    simplified = to_simplified(lowered) if "\u3400" <= lowered <= "\u9fff" else lowered
    return simplified if len(simplified) == 1 else lowered


def _fold(text: str) -> str:
    """逐字折叠（繁→简、大小写），长度不变：在折叠后的文本里找到的位置就是原文的位置。"""
    return "".join(_fold_char(char) for char in text)


def _is_word_char(char: str) -> bool:
    return char.isascii() and char.isalnum() or (char.isalpha() and ord(char) < 0x2000)


class Lexicon:
    """一组字面词（折叠后），按首字分桶、桶里记有哪些长度：扫描时每个位置只查几次集合。

    case_sensitive=True 只折繁简、不折大小写（三个字母的拉丁地名只认原样大写的写法：「Shu」是地名，「shu」多半是拼音）。"""

    def __init__(self, terms: Iterable[str], *, case_sensitive: bool = False) -> None:
        self.case_sensitive = case_sensitive
        self.terms: set[str] = set()
        lengths: dict[str, set[int]] = {}
        for raw in terms:
            term = self.fold(unicodedata.normalize("NFKC", str(raw or "")).strip())
            term = _SPACE.sub(" ", term)
            if not term or len(term) > _MAX_TERM:
                continue
            self.terms.add(term)
            lengths.setdefault(term[0], set()).add(len(term))
        self.lengths = {head: sorted(found, reverse=True) for head, found in lengths.items()}

    def __bool__(self) -> bool:
        return bool(self.terms)

    def fold(self, text: str) -> str:
        return "".join(char if char.isascii() else _fold_char(char) for char in text) if self.case_sensitive else _fold(text)

    def longest_at(self, folded: str, index: int) -> int:
        """folded[index:] 开头最长的一个词有多长（0 = 没有）。拉丁词两头必须是词边界。"""
        size = len(folded)
        for length in self.lengths.get(folded[index], ()):
            if index + length > size:
                continue
            piece = folded[index : index + length]
            if piece not in self.terms:
                continue
            if _is_word_char(piece[0]) and index > 0 and _is_word_char(folded[index - 1]):
                continue
            if _is_word_char(piece[-1]) and index + length < size and _is_word_char(folded[index + length]):
                continue
            return length
        return 0

    def replace(self, text: str, placeholder: str, *, protect: Lexicon | None = None) -> tuple[str, int]:
        """最长匹配换成占位符。`protect` 里的词（技法术语，如「印度占星」「汉堡学派」「万年历」）在同一位置一样长或更长时
        整体跳过：术语里碰巧含着地名，不是用户在说地点。"""
        if not self.terms:
            return text, 0
        folded = self.fold(text)
        guard = protect.fold(text) if protect else ""
        out: list[str] = []
        hits, index, last, size = 0, 0, 0, len(text)
        while index < size:
            kept = protect.longest_at(guard, index) if protect else 0
            matched = self.longest_at(folded, index)
            if kept and kept >= matched:
                index += kept
                continue
            if matched:
                out.append(text[last:index])
                out.append(placeholder)
                hits += 1
                index += matched
                last = index
            else:
                index += 1
        out.append(text[last:])
        return "".join(out), hits


class PlaceLibraryUnavailable(RuntimeError):
    """找不到星阙地名库：不能保证地名不离机，决策层这一问不发（调用方的 _decision_guard 关闭式回落确定性路径）。"""


_PLACE_FILES = ("cities.json", "citiesFull.json")
_PLACE_DIR = Path("src") / "vendor" / "place" / "data"
_PLACE_LOCK = threading.Lock()
_PLACE_CACHE: dict[str, Lexicon] = {}


def place_library_dir() -> Path:
    """星阙地名库所在目录：与 JS 引擎找 horosa-core-js 同一套候选（HOROSA_CORE_JS_ROOT → 已装 runtime → 源码树）。"""
    candidates: list[Path] = []
    override = os.environ.get("HOROSA_PLACE_LIBRARY_DIR")
    if override:
        candidates.append(Path(override).expanduser())
    try:
        from horosa_skill.config import Settings
        from horosa_skill.engine.js_client import HorosaJsEngineClient

        candidates.extend(root / _PLACE_DIR for root in HorosaJsEngineClient(Settings.from_env())._candidate_engine_roots())
    except Exception:  # noqa: BLE001 - 配置读不了也照样试源码树
        pass
    candidates.append(Path(__file__).resolve().parents[3] / "horosa-core-js" / _PLACE_DIR)
    for candidate in candidates:
        if all((candidate / name).is_file() for name in _PLACE_FILES):
            return candidate
    raise PlaceLibraryUnavailable(
        "找不到星阙地名库（horosa-core-js/src/vendor/place/data），无法保证地名不离机：这一问不发给决策层。 / "
        "The Horosa place library (horosa-core-js/src/vendor/place/data) was not found, so place names cannot be kept "
        "local: the decision layer is not asked."
    )


def place_terms(directory: Path | None = None) -> set[str]:
    """地名库里的全部写法：中文名、所属地区名、英文名、拼音（带空格与连写）。去掉豁免词与过短的拉丁词。"""
    directory = directory or place_library_dir()
    terms: set[str] = set()
    for name in _PLACE_FILES:
        rows = json.loads((directory / name).read_text(encoding="utf-8"))
        for row in rows:
            for key in ("n", "r", "e", "p", "name", "region", "en"):
                value = str(row.get(key) or "").strip()
                if value:
                    terms.add(value)
            pinyin = str(row.get("p") or "").strip()
            if pinyin:
                terms.add(pinyin.replace(" ", ""))
            for key in ("n", "r", "name", "region"):
                # 「台中市」「朝阳区」口语里常省掉后缀：去掉行政后缀的词干（两个字以上）也算地名。
                stem = _ADMIN_SUFFIX.sub("", str(row.get(key) or "").strip())
                if len(stem) >= 2 and stem != str(row.get(key) or "").strip():
                    terms.add(stem)
    kept = set()
    for term in terms:
        folded = _fold(unicodedata.normalize("NFKC", term))
        if folded in PLACE_TERM_EXEMPT:
            continue
        if folded.isascii() and len(folded) < _MIN_LATIN:  # 两个字母的（国家代码等）不换
            continue
        if not folded.isascii() and len(folded) < 2:
            continue
        kept.add(term)
    return kept


def _protected_terms() -> set[str]:
    """技法术语（决策层路由题自己的门类描述切出来的词 + 知识库的标题 / 小节名 / 加粗词）：里面碰巧含地名的不换。"""
    from horosa_skill.decisions.surfaces.routing import FAMILIES

    terms: set[str] = set()
    for description, _tools in FAMILIES.values():
        terms.update(part.strip() for part in re.split(r"[：:、，,；;/()（）\s]+|等", description) if len(part.strip()) >= 2)
    try:
        from horosa_skill.knowledge.store import search_vocabulary
    except ImportError:  # 知识库词表是可选的增强
        return terms
    terms.update(search_vocabulary())
    return terms


def place_lexicon() -> tuple[Lexicon, Lexicon, Lexicon]:
    """(不分大小写的地名, 三个字母的拉丁地名（分大小写）, 受保护的技法术语)。术语本身就是地名的（「上海」）不受保护。"""
    directory = place_library_dir()
    key = str(directory.resolve())
    with _PLACE_LOCK:
        if key not in _PLACE_CACHE:
            terms = place_terms(directory)
            short = {term for term in terms if term.isascii() and len(term) <= _MIN_LATIN}
            main = Lexicon(terms - short)
            every = main.terms | {_fold(term) for term in short}
            protected = Lexicon(term for term in _protected_terms() if _fold(term) not in every)
            _PLACE_CACHE[key] = (main, Lexicon(short, case_sensitive=True), protected)
        return _PLACE_CACHE[key]


# ───────────────────────────── 流程 ─────────────────────────────


@dataclass
class Redaction:
    text: str
    counts: dict[str, int] = field(default_factory=dict)
    truncated: bool = False
    original_chars: int = 0

    def as_dict(self) -> dict[str, object]:
        return {"counts": dict(self.counts), "truncated": self.truncated, "original_chars": self.original_chars}


def _outside_placeholders(text: str, fn: Callable[[str], tuple[str, int]]) -> tuple[str, int]:
    """只处理占位符之间的片段：已经换掉的不再碰（幂等），片段之间也拼不出新词。"""
    pieces: list[str] = []
    hits, last = 0, 0
    for match in [*_PLACEHOLDER_RE.finditer(text), None]:
        end = match.start() if match is not None else len(text)
        segment, found = fn(text[last:end])
        hits += found
        pieces.append(segment)
        if match is not None:
            pieces.append(match.group(0))
            last = match.end()
    return "".join(pieces), hits


def _apply_rule(text: str, rule: _Rule) -> tuple[str, int]:
    kind, pattern, replace = rule
    return pattern.subn(replace or _PLACEHOLDER[kind], text)


def _scrub(text: str, profile: Lexicon, places: tuple[Lexicon, Lexicon, Lexicon] | None, counts: dict[str, int]) -> str:
    def count(kind: str, hits: int) -> None:
        if hits:
            counts[kind] = counts.get(kind, 0) + hits

    out = _SPACE.sub(" ", _CONTROL.sub("", text))
    out, hits = _outside_placeholders(out, lambda part: _apply_rule(part, _RULES[0]))  # 邮箱先换：里面的名字和数字整体走
    count("email", hits)
    out, hits = _outside_placeholders(out, lambda part: profile.replace(part, _PLACEHOLDER["profile"]))
    count("profile", hits)
    out, hits = _outside_placeholders(out, lambda part: _apply_rule(part, _LATIN_NAME))
    count("name", hits)
    if places is not None:
        # 地名库先于日期规则：「6th of October City」是地名，不能先被日期规则切开。
        main, short, protected = places
        for lexicon in (main, short):
            out, hits = _outside_placeholders(
                out, lambda part, lexicon=lexicon: lexicon.replace(part, _PLACEHOLDER["place"], protect=protected))
            count("place", hits)
    for rule in _RULES[1:]:
        out, hits = _outside_placeholders(out, lambda part, rule=rule: _apply_rule(part, rule))
        count(rule[0], hits)
    return _SPACE.sub(" ", out).strip()


def redact_text(
    text: str,
    *,
    max_chars: int = MAX_STATE_CHARS,
    private_terms: Iterable[str] = (),
    places: bool = True,
) -> Redaction:
    """脱敏 + 截断；幂等（对已脱敏文本再跑一次不变）。

    `private_terms`：本机专有词（命主档案名 / 别名 / 地点标签），先于通用规则替换。`places=False` 只给测试与离线评测用：
    不读地名库（找不到地名库时默认会抛 PlaceLibraryUnavailable——宁可这一问不发，也不让地名离机）。"""
    raw = unicodedata.normalize("NFC", str(text or "")).translate(_WIDE)
    original_chars = len(raw)
    raw = raw[:MAX_INPUT_CHARS]
    profile = Lexicon(private_terms)
    library = place_lexicon() if places else None
    counts: dict[str, int] = {}
    out = _scrub(raw, profile, library, counts)
    for _ in range(2):  # 跑到不动点：替换偶尔让相邻两段拼出新的匹配
        again = _scrub(out, profile, library, counts)
        if again == out:
            break
        out = again
    truncated = original_chars > MAX_INPUT_CHARS
    if len(out) > max_chars:
        out = out[: max(0, max_chars - len(_TRUNCATION_MARK))].rstrip() + _TRUNCATION_MARK
        truncated = True
    return Redaction(text=out, counts=counts, truncated=truncated, original_chars=original_chars)


def build_meta_state(
    query: str,
    *,
    technique_names: list[str] | None = None,
    known_setting_keys: list[str] | None = None,
    private_terms: Iterable[str] = (),
    places: bool = True,
) -> tuple[dict[str, object], Redaction]:
    """一档状态：脱敏问题文本 + 技法名 + 已知设置键名（只有键名，没有值）。这就是决策层一档能看到的全部。"""
    redaction = redact_text(query, private_terms=private_terms, places=places)
    state: dict[str, object] = {"user_request": redaction.text}
    if technique_names:
        state["technique_names"] = list(technique_names)
    if known_setting_keys:
        state["known_setting_keys"] = sorted(known_setting_keys)
    return state, redaction
