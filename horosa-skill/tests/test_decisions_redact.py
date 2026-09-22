"""一档脱敏：出生日期 / 时刻 / 坐标 / 地名 / 号码不以原值离机；存在性保留；幂等；截断。"""

from __future__ import annotations

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
