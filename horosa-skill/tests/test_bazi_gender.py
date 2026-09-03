# -*- coding: utf-8 -*-
"""回归：星阙客户端发现 bazi_birth 性别恒为「未知」——根因是 BaZiBirthInput 缺 gender 字段声明，
传入值被 schema 丢弃。本文件锁定：gender 在 bazi 链上正确传递、归一化与展示。"""

from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.schemas.tools import BaZiBirthInput, BaZiDirectInput
from horosa_skill.service import _gender_label

BASE = {"date": "1995-06-03", "time": "05:30", "zone": "+08:00", "lat": "31n14", "lon": "121e28"}


def _normalized_gender(cls, payload):
    return cls.model_validate(normalize_request_payload(payload)).model_dump(exclude_none=True).get("gender")


def test_birth_input_accepts_gender_bool():
    assert _normalized_gender(BaZiBirthInput, {**BASE, "gender": True}) is True
    assert _normalized_gender(BaZiBirthInput, {**BASE, "gender": False}) is False


def test_birth_input_normalizes_cn_labels():
    assert _normalized_gender(BaZiBirthInput, {**BASE, "gender": "男"}) is True
    assert _normalized_gender(BaZiBirthInput, {**BASE, "gender": "女"}) is False


def test_birth_input_unspecified_omits_gender():
    assert "gender" not in BaZiBirthInput.model_validate(BASE).model_dump(exclude_none=True)


def test_direct_input_defaults_male():
    assert BaZiDirectInput.model_validate(BASE).model_dump(exclude_none=True).get("gender") is True


def test_gender_label_maps_all_forms():
    assert _gender_label(True) == "男"
    assert _gender_label(False) == "女"
    assert _gender_label(1) == "男"
    assert _gender_label(0) == "女"
    assert _gender_label("男") == "男"
    assert _gender_label("女") == "女"
    assert _gender_label("Male") == "男"


def test_gender_label_unknown_fallback():
    assert _gender_label(None) == "未知"
    assert _gender_label("非男非女") == "未知"