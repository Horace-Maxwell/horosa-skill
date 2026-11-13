"""一档脱敏：出生日期 / 时刻 / 坐标 / 地名 / 号码不以原值离机；存在性保留；幂等；截断。"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path

import pytest

from horosa_skill.decisions import redact
from horosa_skill.decisions.redact import MAX_STATE_CHARS, build_meta_state, redact_text


def test_birth_data_is_replaced_by_typed_placeholders() -> None:
    text = "我老婆1990年3月5日早上8点半在上海市浦东新区出生，坐标31n13 121e28，手机13812345678，帮她排八字看看今年财运"
    result = redact_text(text)
    for leaked in ("1990", "3月5日", "8点半", "上海市", "浦东新区", "31n13", "121e28", "13812345678"):
        assert leaked not in result.text, leaked
    assert "<日期>" in result.text and "<时刻>" in result.text and "<地点>" in result.text and "<坐标>" in result.text and "<电话>" in result.text
    # 存在性与语义保留：主体、技法、问题都还在。
    for kept in ("我老婆", "出生", "排八字", "财运"):
        assert kept in result.text
    # 「上海市浦东新区」作为一个连续地址被整体吞成一个 <地点>（更少泄漏，不是更多）。
    assert result.counts["date"] >= 1 and result.counts["time"] >= 1 and result.counts["place"] >= 1


def test_iso_and_clock_formats_and_lunar_dates() -> None:
    result = redact_text("生于1988-12-01 23:30，农历十一月初三，2001/7/9 07:05:00")
    assert "1988" not in result.text and "23:30" not in result.text and "07:05" not in result.text
    assert "农历" not in result.text or "<日期>" in result.text
    assert result.counts["date"] >= 2


def test_redaction_is_idempotent_and_strips_control_chars() -> None:
    once = redact_text("1990年3月5日\x07出生的男的\t八字")
    twice = redact_text(once.text)
    assert twice.text == once.text and "\x07" not in once.text and "\t" not in once.text


def test_truncation_keeps_a_marker() -> None:
    result = redact_text("问" * (MAX_STATE_CHARS + 500))
    assert result.truncated and len(result.text) <= MAX_STATE_CHARS and result.text.endswith("<截断>")
    assert result.original_chars == MAX_STATE_CHARS + 500


def test_meta_state_carries_only_names_and_keys() -> None:
    state, redaction = build_meta_state("2000年1月1日 12:00 北京市 排紫微", technique_names=["ziwei_birth"], known_setting_keys=["zone", "date"])
    assert state["technique_names"] == ["ziwei_birth"] and state["known_setting_keys"] == ["date", "zone"]
    assert "2000" not in state["user_request"] and "北京市" not in state["user_request"]
    assert redaction.counts["date"] == 1


# ── 2026-11-11 深审 J1：按构造脱敏（语料、地名库全集、生成的日期时刻写法、线性时间） ─────────────────────────────


CORPUS = json.loads((Path(__file__).parent / "fixtures" / "redaction_corpus.json").read_text(encoding="utf-8"))
_PLACEHOLDERS = re.compile("|".join(re.escape(token) for token in (*redact._PLACEHOLDER.values(), "<截断>")))


def _fold(text: str) -> str:
    return redact._fold(unicodedata.normalize("NFKC", text))


def test_the_corpus_is_big_enough_and_keeps_the_auditors_strings() -> None:
    sources = [case["source"] for case in CORPUS["cases"]]
    assert sources.count("auditor") == 17 and sources.count("added") >= 80


@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda case: case["text"][:24])
def test_no_birth_date_time_coordinate_place_or_profile_name_survives(case: dict) -> None:
    out = redact_text(case["text"], private_terms=CORPUS["private_terms"]).text
    folded = _fold(out)
    for leak in case["leaks"]:
        assert _fold(leak) not in folded, (leak, out)
    assert not re.search(r"\d", out), f"数字一律不离机：{out}"
    for term in CORPUS["private_terms"]:
        assert _fold(term) not in folded, (term, out)
    assert redact_text(out, private_terms=CORPUS["private_terms"]).text == out, "幂等"


def _no_letters_left(piece: str) -> bool:
    return not re.search(r"[^\W\d_]", _PLACEHOLDERS.sub("", piece))


def test_every_name_in_the_place_library_is_replaced() -> None:
    """地名库全集（中文名、地区名、英文名、拼音、连写拼音、省市词干）：每一个单独出现时都只剩占位符。"""
    main, short, protected = redact.place_lexicon()
    terms = sorted(redact.place_terms())
    assert len(terms) > 50_000
    sep = " ; "
    for start in range(0, len(terms), 4000):
        batch = terms[start : start + 4000]
        out = redact._scrub(sep.join(batch), redact.Lexicon(()), (main, short, protected), {})
        pieces = out.split(";")
        assert len(pieces) == len(batch), "分隔符被吃掉了：没法逐个核对"
        left = [(term, piece) for term, piece in zip(batch, pieces, strict=True) if not _no_letters_left(piece)]
        assert not left, left[:20]


def test_place_names_written_in_traditional_characters_are_replaced_too() -> None:
    from horosa_skill.textscript import convert

    for simplified in ("上海", "广州", "台北", "哈尔滨", "乌鲁木齐", "香港", "澳门", "深圳市", "苏州"):
        traditional = convert(simplified, "zh-Hant")
        out = redact_text(f"我出生在{traditional}，想看看").text
        assert "<地点>" in out and _fold(traditional) not in _fold(out), (traditional, out)


def test_technique_terms_that_happen_to_contain_a_place_name_are_kept() -> None:
    out = redact_text("想看印度占星和占星地图，顺便查万年历").text
    assert out == "想看印度占星和占星地图，顺便查万年历", out
    out = redact_text("帮我排一下紫微斗数，看看十二宫和四化，孩子时候身体不好，去哪个城市发展").text
    assert "<" not in out, out


def test_latin_place_terms_that_collide_with_technique_vocabulary_are_decided_one_by_one() -> None:
    """地名库里的英文 / 拼音词与技法术语撞车（Jupiter、Natal、Sanhe…）：每一个都要在豁免表里表态；表里的必须真是地名库的词。"""
    from horosa_skill.decisions.surfaces.routing import FAMILIES
    from horosa_skill.engine.registry import TOOL_DEFINITIONS

    vocabulary = _fold(" ".join([*(d.description for d in TOOL_DEFINITIONS.values()), *(desc for desc, _ in FAMILIES.values())]))
    words = set(re.findall(r"[a-z][a-z'\-]+", vocabulary))
    raw = set()
    directory = redact.place_library_dir()
    for name in redact._PLACE_FILES:
        for row in json.loads((directory / name).read_text(encoding="utf-8")):
            raw.update(_fold(str(row.get(key) or "")) for key in ("e", "en", "p"))
            raw.add(_fold(str(row.get("p") or "").replace(" ", "")))
    assert redact.PLACE_TERM_EXEMPT <= raw, sorted(redact.PLACE_TERM_EXEMPT - raw)
    still_redacted = {"shanghai", "tokyo", "urumqi", "kong", "shaoyang", "wenchang", "xinyi", "beijing", "london", "paris", "berlin"}
    undecided = sorted(w for w in words & raw if len(w) >= 4 and w not in redact.PLACE_TERM_EXEMPT and w not in still_redacted)
    assert not undecided, f"新的撞车词，在 PLACE_TERM_EXEMPT 或 still_redacted 里表态：{undecided}"


_HAN = "〇一二三四五六七八九"
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


def _han_number(number: int) -> str:
    if number < 10:
        return _HAN[number]
    tens, ones = divmod(number, 10)
    return ("" if tens == 1 else _HAN[tens]) + "十" + (_HAN[ones] if ones else "")


def _date_time_forms(year: int, month: int, day: int, hour: int, minute: int) -> list[str]:
    han_year = "".join(_HAN[int(c)] for c in str(year))
    wide = str.maketrans("0123456789", "０１２３４５６７８９")
    english = _MONTHS[month - 1]
    forms = [
        f"{year}年{month}月{day}日{hour}点{minute}分", f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}",
        f"{year}/{month}/{day} {hour}:{minute:02d}", f"{year}.{month}.{day}", f"{month}/{day}/{year}", f"{day}.{month}.{year}",
        f"{han_year}年{_han_number(month)}月{_han_number(day)}日", f"{han_year[-2:]}年{_han_number(month)}月{_han_number(day)}号",
        f"农历{_han_number(month)}月初{_HAN[day % 9 + 1]}", f"{_han_number(hour % 12 + 1)}点{_han_number(minute % 59 + 1)}分",
        f"晚上{_han_number(hour % 12 + 1)}点半", f"{hour}时{minute}分", f"{year}年{month}月{day}日{hour}:{minute:02d}".translate(wide),
        f"{english} {day}, {year} at {hour % 12 + 1}:{minute:02d} pm", f"{day} {english} {year}, {hour % 12 + 1}am",
        f"{day}th of {english} {year}", f"{english[:3]} {day} {year}", f"born {year}, {english}",
        f"{_HAN[hour % 10]}{_HAN[minute % 10]}年", f"今年{hour + 10}岁", f"{_han_number(hour + 10)}岁",
    ]
    return forms


def test_generated_date_and_time_forms_leave_no_value_behind() -> None:
    survivors = []
    for year, month, day, hour, minute in [(1900 + i * 7, i % 12 + 1, i % 28 + 1, i % 24, (i * 13) % 60) for i in range(18)]:
        for form in _date_time_forms(year, month, day, hour, minute):
            out = redact_text(f"我是{form}出生的，帮我排盘").text
            leftovers = re.findall(r"\d|[〇零一二三四五六七八九十]{1,4}[年月日号点时分岁]|初[一二三四五六七八九十]", out)
            month_left = re.search(rf"(?i)\b(?:{'|'.join(_MONTHS)}|{'|'.join(m[:3] for m in _MONTHS)})\b", out)
            if leftovers or month_left:
                survivors.append((form, out))
    assert not survivors, survivors[:10]


@pytest.mark.parametrize("pattern", [" ", "\t\n", "a", "1", "1 ", "a@", "1.", "一二", "北纬1", "五月", "我叫", "name is ", "Shanghai "])
def test_scrubbing_is_linear_on_adversarial_input(pattern: str) -> None:
    """C-21：旧实现在 8 万个空格上 43.7 s（`\\s*` 前缀模式逐位置回扫）。这里绕过输入截断直接跑 8 万字：线性实现 < 1 s。"""
    places = redact.place_lexicon()
    text = pattern * (80_000 // len(pattern))
    started = time.perf_counter()
    redact._scrub(text, redact.Lexicon(["妈妈"]), places, {})
    # 上限 10 s：要拦的是旧实现的 43.7 s（平方级）；线性实现在维护机 < 1 s，但 Windows ARM 仿真 lane 上要 ~2.1 s（v0.50.1 发版矩阵在 2 s 线上红过）。
    assert time.perf_counter() - started < 10.0


def test_public_entry_point_has_bounded_work_for_any_input_size() -> None:
    redact.place_lexicon()
    started = time.perf_counter()
    result = redact_text("1990年5月3日 " + " " * 1_000_000 + "上海")
    assert time.perf_counter() - started < 1.0
    assert result.truncated is True and result.original_chars > redact.MAX_INPUT_CHARS and not re.search(r"\d", result.text)


def test_without_the_place_library_the_question_is_not_sent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """地名库找不到就保证不了地名不离机：抛出，调用方关闭式回落（不发请求）。"""
    monkeypatch.setattr(redact, "_PLACE_CACHE", {})
    monkeypatch.setattr(redact, "place_library_dir", lambda: (_ for _ in ()).throw(redact.PlaceLibraryUnavailable("x / y")))
    with pytest.raises(redact.PlaceLibraryUnavailable):
        build_meta_state("我在上海出生")
    assert build_meta_state("我在上海出生", places=False)[0]["user_request"] == "我在上海出生"
