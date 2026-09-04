"""回归（PR #17，@xipfs）：bazi_birth 性别恒为「未知」——根因是 BaZiBirthInput 缺 gender 字段声明，MCP 扁平面
把传入值丢掉。本文件锁定：gender 在 bazi 链上正确归一（含 bool）、声明与展示。"""
from __future__ import annotations

from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.schemas.tools import BaZiBirthInput, BaZiDirectInput
from horosa_skill.service import _gender_label

BASE = {"date": "1990-01-01", "time": "12:00:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}


def _normalized_gender(cls, payload):  # noqa: ANN001
    return cls.model_validate(normalize_request_payload(payload)).model_dump(exclude_none=True).get("gender")


def test_birth_input_normalizes_bool_to_backend_int() -> None:
    # Java 后端读 1/0；bool 直传会变成 JSON true/false
    assert _normalized_gender(BaZiBirthInput, {**BASE, "gender": True}) == 1
    assert _normalized_gender(BaZiBirthInput, {**BASE, "gender": False}) == 0


def test_birth_input_normalizes_cn_and_en_labels() -> None:
    assert _normalized_gender(BaZiBirthInput, {**BASE, "gender": "男"}) == 1
    assert _normalized_gender(BaZiBirthInput, {**BASE, "gender": "女"}) == 0
    assert _normalized_gender(BaZiBirthInput, {**BASE, "gender": "F"}) == 0


def test_birth_input_unspecified_omits_gender() -> None:
    assert "gender" not in BaZiBirthInput.model_validate(BASE).model_dump(exclude_none=True)


def test_direct_input_default_unchanged() -> None:
    # BaZiDirectInput 的既有默认不受本次改动影响
    assert BaZiDirectInput.model_validate(BASE).model_dump(exclude_none=True).get("gender") is True


def test_gender_label_maps_all_forms() -> None:
    assert _gender_label(True) == "男"
    assert _gender_label(False) == "女"
    assert _gender_label(1) == "男"
    assert _gender_label(0) == "女"
    assert _gender_label("1") == "男"
    assert _gender_label("男") == "男"
    assert _gender_label("女") == "女"
    assert _gender_label("Male") == "男"
    assert _gender_label("坤") == "女"


def test_gender_label_unknown_fallback() -> None:
    assert _gender_label(None) == "未知"
    assert _gender_label(-1) == "未知"
    assert _gender_label("非男非女") == "未知"
    assert _gender_label(None, unknown="—") == "—"
