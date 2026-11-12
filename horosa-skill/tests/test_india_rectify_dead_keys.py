"""印度校时的死键 + 印度后端「数组被 str() 掉」的坑（v0.48.0）。

① india_rectify 曾在 tools/list 上广告问事 / 年盘 / 三旗 11 键（tripataki、prashna×6、tajakaYear、annualChartType、
varshaLat/Lon）。上游校时器把整套印度盘参数都发给 /india/rectify（IndiaChartMain.js:3721-3727），Java 共用 getParams 照转，
但 Python rectify_core 一个都不读——读它们的只有 /chart 那条路。现与宿占死键同一套：照收、不广告、不下发、技法卡不回显；
不同的是给了会在 warnings 说一声（广告过，调用方可能以为有效）。常量 schemas/tools/astro.INDIA_RECTIFY_DEAD_KEYS。

② webindiasrv 按 `str(x).split(',')` 读问事流派 prashnaSchools（_compute_prashna）与校时自定 RP rectifyCustomRp（rectify_core）：
传数组 ['kp'] 会被 str() 成 "['kp']"，切出来的流派一个都对不上，KP 问事整段**静默**不算。上游页面自己下发前 `arr.join(',')`；
skill 在边界并成逗号串（service/text/chart_family._india_comma_lists）。

上游对照用钉住的 Horosa-Public（HOROSA_SOURCE_ROOT），没设就跳过那几条。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools.astro import INDIA_RECTIFY_DEAD_KEYS, IndiaRectifyInput
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.text.chart_family import _india_chart_remote_payload
from horosa_skill.surfaces.mcp_schema import advertised_technique_schema
from horosa_skill.testing_payloads import build_sample_payloads

_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
_WEB = Path(_ROOT) / "Horosa-Web" if _ROOT else None
_INDIA_SRV = _WEB / "astropy" / "websrv" / "webindiasrv.py" if _WEB else None
requires_upstream = pytest.mark.skipif(
    _INDIA_SRV is None or not _INDIA_SRV.is_file(), reason="[upstream-checkout] HOROSA_SOURCE_ROOT (Horosa-Public checkout) not set"
)

# 每个死键一个非缺省值（形状照 india_chart 同名键）。
_DEAD_VALUES: dict[str, Any] = {
    "tripataki": True, "prashnaTime": "2026/11/08 10:00:00", "prashnaSchools": "kp,tajika", "prashnaMatter": "career",
    "prashnaNumber": 42, "prashnaCuspMode": "equal_from_asc", "prashnaPrimaryHouse": 10, "tajakaYear": 2026,
    "annualChartType": "tithi", "varshaLat": "51n30", "varshaLon": "0w07",
}


def _backend_schools(value: Any) -> list[str]:
    """webindiasrv._compute_prashna 读问事流派的原式（上游 :946，下面 test_upstream_still_splits_str 盯着它没变）。"""
    return [x for x in str(value or "kp").split(",") if x]


class _Recording(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[tuple[str, dict[str, Any]]] = []

    def call(self, endpoint: str, payload: dict) -> dict:
        self.sent.append((endpoint, dict(payload)))
        return super().call(endpoint, payload)


def _service(tmp_path: Path, client: FakeClient) -> HorosaSkillService:
    settings = Settings(db_path=tmp_path / "m.db", output_dir=tmp_path / "runs",
                        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9")
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())


# ─────────────────────────────── 上游对照 ───────────────────────────────

def _function_source(text: str, name: str) -> str:
    match = re.search(rf"^def {name}\(.*?(?=^def |^class |\Z)", text, re.DOTALL | re.MULTILINE)
    assert match is not None, name
    return match.group(0)


@requires_upstream
def test_upstream_rectify_core_reads_none_of_the_dead_keys_but_chart_does() -> None:
    text = _INDIA_SRV.read_text(encoding="utf-8")
    core = _function_source(text, "rectify_core")
    read_by_core = [k for k in INDIA_RECTIFY_DEAD_KEYS if re.search(rf"['\"]{k}['\"]", core)]
    assert read_by_core == [], f"上游 rectify_core 开始读这些键了，它们不再是死键：{read_by_core}"
    # 端点本身只把请求体交给 rectify_core（没有别的读取方）。
    handler = re.search(r"def rectify\(self\):.*?(?=\n    @|\n    def )", text, re.DOTALL)
    assert handler is not None and "rectify_core(data)" in handler.group(0)
    assert not [k for k in INDIA_RECTIFY_DEAD_KEYS if k in handler.group(0)]
    # 反向锚：每个死键在 /chart 那条路上确有读取方——表里不是拼错的名字。
    rest = text.replace(core, "")
    unread = [k for k in INDIA_RECTIFY_DEAD_KEYS if not re.search(rf"['\"]{k}['\"]", rest)]
    assert unread == [], unread
    # 内核（rectify_core 唯一转交请求体的地方）也不读。
    kernel = (_WEB / "astropy" / "astrostudy" / "india" / "india_chart_kernel.py").read_text(encoding="utf-8")
    assert not [k for k in INDIA_RECTIFY_DEAD_KEYS if re.search(rf"['\"]{k}['\"]", kernel)]


@requires_upstream
def test_upstream_still_splits_str_of_prashna_schools_and_custom_rp() -> None:
    """这两处原式不变，「数组得先并成逗号串」才成立；上游页面也是下发前 join。"""
    text = _INDIA_SRV.read_text(encoding="utf-8")
    assert "str(data.get('prashnaSchools') or 'kp').split(',')" in text
    assert "str(d.get('rectifyCustomRp') or '').split(',')" in text
    page = (_WEB / "astrostudyui" / "src" / "components" / "astro" / "IndiaChartMain.js").read_text(encoding="utf-8")
    assert "{ schools: arr.join(',') }" in page


# ─────────────────────────────── 死键：照收 / 不广告 / 不下发 / 有警告 / 卡片不回显 ───────────────────────────────

def test_dead_keys_are_accepted_but_not_advertised() -> None:
    assert set(_DEAD_VALUES) == set(INDIA_RECTIFY_DEAD_KEYS)
    dumped = IndiaRectifyInput.model_validate({**build_sample_payloads()["india_rectify"], **_DEAD_VALUES}).model_dump()
    assert {k: dumped[k] for k in _DEAD_VALUES} == _DEAD_VALUES
    schema = advertised_technique_schema(
        "india_rectify", TOOL_DEFINITIONS["india_rectify"].input_model.model_json_schema()
    )
    assert set(schema["properties"]) & set(INDIA_RECTIFY_DEAD_KEYS) == set()
    # 校时自己的键与印占口径键照常广告。
    assert {"rectifyWindowMinutes", "rectifyStepSeconds", "indiaHsys", "indiaAyanamsa"} <= set(schema["properties"])


def test_dead_keys_are_not_sent_and_the_caller_is_told(tmp_path: Path) -> None:
    client = _Recording()
    service = _service(tmp_path, client)
    payload = {**build_sample_payloads()["india_rectify"], **_DEAD_VALUES, "rectifyCustomRp": ["Saturn", " Jupiter "]}
    result = service.run_tool("india_rectify", payload, save_result=False)
    assert result.ok is True, result.error
    bodies = [body for endpoint, body in client.sent if endpoint == "/india/rectify"]
    assert len(bodies) == 1
    assert sorted(set(bodies[0]) & set(INDIA_RECTIFY_DEAD_KEYS)) == []
    # rectifyCustomRp：后端 str(x).split(',')，数组得先并成逗号串。
    assert bodies[0]["rectifyCustomRp"] == "Saturn,Jupiter"
    warning = next((w for w in result.warnings if "未转发后端" in w), None)
    assert warning is not None, result.warnings
    assert all(key in warning for key in INDIA_RECTIFY_DEAD_KEYS)


def test_no_warning_when_no_dead_key_is_given(tmp_path: Path) -> None:
    result = _service(tmp_path, _Recording()).run_tool("india_rectify", build_sample_payloads()["india_rectify"], save_result=False)
    assert result.ok is True, result.error
    assert not [w for w in result.warnings if "未转发后端" in w]


def test_card_does_not_echo_dead_keys_for_rectify(monkeypatch) -> None:
    from horosa_skill.reports import technique_card

    # 把死键塞进结果敏感表：证明挡住它们的是死键表，不是「敏感表本来就没收」。
    extra = tuple((key, key, None) for key in INDIA_RECTIFY_DEAD_KEYS)
    monkeypatch.setattr(technique_card, "_RESULT_SENSITIVE_FIELDS", technique_card._RESULT_SENSITIVE_FIELDS + extra)
    used = technique_card._settings_used(dict(_DEAD_VALUES), {}, "astro", "india_rectify")
    assert set(used) & set(INDIA_RECTIFY_DEAD_KEYS) == set()
    # india_chart 照常回显（死键表按工具收窄）。
    assert technique_card._settings_used(dict(_DEAD_VALUES), {}, "astro", "india_chart")["tajakaYear"]["value"] == 2026


# ─────────────────────────────── 数组 → 逗号串 ───────────────────────────────

def test_prashna_schools_array_reaches_the_backend_as_a_comma_string() -> None:
    """会抓住那次静默跳过：数组原样下发时，后端原式切出来的是 ["['kp'", " 'tajika']"]，'kp' 不在其中 → KP 问事整段不算。"""
    base = {**build_sample_payloads()["india_chart"], "prashnaTime": "2026/11/08 10:00:00"}
    for given, want in ((["kp", "tajika"], "kp,tajika"), (("kp",), "kp"), ([" parashari ", ""], "parashari"),
                        ("kp,parashari", "kp,parashari")):
        remote = _india_chart_remote_payload({**base, "prashnaSchools": given})
        assert remote["prashnaSchools"] == want, given
        schools = _backend_schools(remote["prashnaSchools"])
        assert schools == want.split(","), (given, schools)
    # 没起卦（无 prashnaTime）时问事族照旧不下发。
    assert "prashnaSchools" not in _india_chart_remote_payload({**build_sample_payloads()["india_chart"], "prashnaSchools": ["kp"]})


def test_prashna_schools_array_end_to_end_through_india_chart(tmp_path: Path) -> None:
    client = _Recording()
    service = _service(tmp_path, client)
    payload = {**build_sample_payloads()["india_chart"], "prashnaTime": "2026/11/08 10:00:00", "prashnaSchools": ["kp", "tajika"]}
    service.run_tool("india_chart", payload, save_result=False)
    bodies = [body for endpoint, body in client.sent if endpoint == "/india/chart" and "prashnaTime" in body]
    assert bodies, [endpoint for endpoint, _ in client.sent]
    assert {body["prashnaSchools"] for body in bodies} == {"kp,tajika"}
    assert "kp" in _backend_schools(bodies[0]["prashnaSchools"])
