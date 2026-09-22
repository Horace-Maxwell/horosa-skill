"""决策层接进 service 的三个面：off = 零字节变化；shadow 不改行为只自陈；enforce 只在规定处采纳。

桩：FakeClient / FakeJsClient（既有）+ FakeJev（决策层）。所有用例离线。
"""

from __future__ import annotations

from pathlib import Path

from test_service import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.decisions.errors import JevError
from horosa_skill.decisions.fake import FailingJev, FakeJev, choice_answer
from horosa_skill.decisions.layer import DecisionLayer
from horosa_skill.decisions.policy import Policy
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

LOCK = {
    "model": "jev-1.13.0",
    "surfaces": {
        "dispatch": {"tau": 0.7, "promoted": True},
        "extract": {"tau": 0.9, "promoted": True},
        "zhancat": {"tau": 0.7, "promoted": True},
    },
}
COMBO_QUERY = "请用奇门和六壬综合分析"
BIRTH = {"date": "2028/04/06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}


class RecordingJs(FakeJsClient):
    def __init__(self) -> None:
        super().__init__()
        self.payloads: list[tuple[str, dict]] = []

    def run(self, tool_name: str, payload: dict) -> dict:  # type: ignore[override]
        self.payloads.append((tool_name, dict(payload)))
        return super().run(tool_name, payload)


def _policy(mode: str, surfaces: tuple[str, ...] = ("dispatch", "extract", "zhancat")) -> Policy:
    return Policy(
        mode=mode, scope="meta", surfaces=frozenset(surfaces), model="jev-1.13.0", base_url="https://api.typesafe.ai",
        timeout_s=3.0, ledger=False, key_present=True, requested_mode=mode,
    )


def _service(tmp_path: Path, layer: DecisionLayer | None, js: FakeJsClient | None = None) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=js or FakeJsClient(), decision_layer=layer)


def _behaviour(envelope) -> dict:
    return {
        "ok": envelope.ok,
        "selected": list(envelope.selected_tools),
        "inputs": envelope.normalized_inputs,
        "exports": {name: (result.data.get("export_snapshot") or {}).get("export_text") for name, result in envelope.results.items()},
        "codes": envelope.code,
    }


def _routing_script(family: str, tool: str, *, conf: float = 0.95) -> dict:
    return {"family": choice_answer(family, confidence=conf), f"tool__{family}": choice_answer(tool, confidence=conf)}


# ---- off：零字节变化 -----------------------------------------------------------------------------


def test_off_state_carries_no_decision_fields(tmp_path: Path, monkeypatch) -> None:
    for key in ("HOROSA_JEV", "HOROSA_JEV_API_KEY", "TYPESAFE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    service = _service(tmp_path, None)
    assert service.decision_layer is None
    result = service.dispatch({"query": COMBO_QUERY, "birth": BIRTH, "save_result": False, "agent_confirmed_settings": True})
    assert result.ok and result.decision_layer is None
    assert "decision_layer" not in result.model_dump(exclude_none=True)
    for envelope in result.results.values():
        assert "decisions" not in (envelope.data.get("technique_card") or {})


# ---- S1 路由 --------------------------------------------------------------------------------------


def test_shadow_routing_never_changes_behaviour_but_self_reports(tmp_path: Path) -> None:
    baseline = _service(tmp_path / "a", None).dispatch({"query": COMBO_QUERY, "birth": BIRTH, "save_result": False, "agent_confirmed_settings": True})
    fake = FakeJev(_routing_script("bazi", "bazi_birth"))  # 与确定性路由（qimen + liureng_gods）刻意不一致
    shadow = _service(tmp_path / "b", DecisionLayer(_policy("shadow"), fake)).dispatch(
        {"query": COMBO_QUERY, "birth": BIRTH, "save_result": False, "agent_confirmed_settings": True}
    )
    assert _behaviour(shadow) == _behaviour(baseline), "shadow invariance: selected tools / inputs / export text identical"
    layer_view = shadow.decision_layer
    assert layer_view["provider"] == "typesafe_jev" and layer_view["mode"] == "shadow"
    routing = [record for record in layer_view["records"] if record["surface"] == "dispatch"]
    assert len(routing) == 1 and routing[0]["adopted"] is False and routing[0]["mode"] == "shadow"
    assert routing[0]["decision"]["tool"] == "bazi_birth" and routing[0]["decision"]["agree"] is False
    assert routing[0]["decision"]["deterministic"] == ["liureng_gods", "qimen"]
    assert "user_request" not in str(routing[0]) and routing[0]["state_sha256"], "record carries a digest, not the text"


def test_enforce_routing_only_fills_a_no_match_and_deterministic_match_stays_authoritative(tmp_path: Path) -> None:
    # 兜底目标选一个不需要出生数据的技法（xuanshi：玄史知识库）——无 birth 的请求才会真的无解
    # （给了 birth 确定性路由会兜底成 chart），而无 birth 的载荷只有免出生数据的工具能跑通。
    fake = FakeJev(_routing_script("reference_data", "xuanshi"))
    layer = DecisionLayer(_policy("enforce"), fake, thresholds=LOCK)
    service = _service(tmp_path, layer)
    # 确定性路由命中 → 不采纳，哪怕 Jev 自信满满。
    matched = service.dispatch({"query": COMBO_QUERY, "birth": BIRTH, "save_result": False, "agent_confirmed_settings": True})
    assert matched.selected_tools == ["liureng_gods", "qimen"]
    record = next(r for r in matched.decision_layer["records"] if r["surface"] == "dispatch")
    assert record["adopted"] is False and record["mode"] == "enforce" and "deterministic router matched" in record["reason"]
    # 确定性路由无解 → 采纳兜底。
    unmatched = service.dispatch({"query": "历史上有没有记载过类似这次的天象", "save_result": False, "agent_confirmed_settings": True})
    assert unmatched.selected_tools == ["xuanshi"] and "xuanshi" in unmatched.results
    record = next(r for r in unmatched.decision_layer["records"] if r["surface"] == "dispatch")
    assert record["adopted"] is True and record["decision"]["tool"] == "xuanshi" and record["decision"]["family"] == "reference_data"


def test_enforce_routing_respects_abstention_and_tau(tmp_path: Path) -> None:
    low = FakeJev(_routing_script("yijing_divination", "sixyao", conf=0.4))
    service = _service(tmp_path / "low", DecisionLayer(_policy("enforce"), low, thresholds=LOCK))
    result = service.dispatch({"query": "帮我看看这段感情最后能不能成", "save_result": False, "agent_confirmed_settings": True})
    assert not result.ok and result.code == "dispatch.no_matching_tool"
    record = result.decision_layer["records"][0]
    assert record["adopted"] is False and "tau" in record["decision"]["reason"]

    abstain = FakeJev({"family": choice_answer("unknown", confidence=0.99)})
    service = _service(tmp_path / "abstain", DecisionLayer(_policy("enforce"), abstain, thresholds=LOCK))
    result = service.dispatch({"query": "帮我看看这段感情最后能不能成", "save_result": False, "agent_confirmed_settings": True})
    assert not result.ok and result.decision_layer["records"][0]["decision"]["abstained"] is True


def test_shadow_routing_on_a_no_match_keeps_the_error_and_records(tmp_path: Path) -> None:
    fake = FakeJev(_routing_script("yijing_divination", "sixyao"))
    service = _service(tmp_path, DecisionLayer(_policy("shadow"), fake))
    result = service.dispatch({"query": "帮我看看这段感情最后能不能成", "save_result": False, "agent_confirmed_settings": True})
    assert not result.ok and result.code == "dispatch.no_matching_tool"
    assert result.decision_layer["records"][0]["adopted"] is False and result.decision_layer["records"][0]["decision"]["tool"] == "sixyao"


def test_provider_failure_degrades_closed_with_a_visible_warning(tmp_path: Path) -> None:
    notes: list[str] = []
    layer = DecisionLayer(_policy("enforce"), FailingJev(JevError("boom", code="jev.timeout")), thresholds=LOCK, degrade=notes.append)
    service = _service(tmp_path, layer)
    result = service.dispatch({"query": COMBO_QUERY, "birth": BIRTH, "save_result": False, "agent_confirmed_settings": True})
    assert result.ok and result.selected_tools == ["liureng_gods", "qimen"], "deterministic path ran"
    assert notes and "jev.timeout" in notes[0]
    assert result.decision_layer["records"] == [], "nothing adopted, nothing to self-report beyond the warning"


# ---- S2 性别抽取 --------------------------------------------------------------------------------


def test_gender_is_filled_only_with_lexicon_and_jev_agreeing_in_enforce(tmp_path: Path) -> None:
    query = "帮我老婆排紫微斗数看看事业"
    fake = FakeJev({"subject_gender": choice_answer("female", confidence=0.97), **_routing_script("ziwei", "ziwei_birth")})
    enforce = _service(tmp_path / "e", DecisionLayer(_policy("enforce"), fake, thresholds=LOCK))
    result = enforce.dispatch({"query": query, "birth": BIRTH, "save_result": False, "agent_confirmed_settings": True})
    assert result.selected_tools == ["ziwei_birth"]
    assert result.normalized_inputs["ziwei_birth"]["gender"] == "女"
    assert "决策层自用户原话抽取" in result.normalized_inputs["ziwei_birth"]["clarification_notes"]
    assert result.results["ziwei_birth"].input_normalized["gender"] == 0, "label normalised to the tool's 0/1 convention"
    record = next(r for r in result.decision_layer["records"] if r["surface"] == "extract")
    assert record["adopted"] is True and record["decision"]["evidence"] == ["老婆"] and record["decision"]["value"] == "女"

    shadow = _service(tmp_path / "s", DecisionLayer(_policy("shadow"), FakeJev({"subject_gender": choice_answer("female", confidence=0.97)})))
    result = shadow.dispatch({"query": query, "birth": BIRTH, "save_result": False, "agent_confirmed_settings": True})
    assert "gender" not in result.normalized_inputs["ziwei_birth"]
    record = next(r for r in result.decision_layer["records"] if r["surface"] == "extract")
    assert record["adopted"] is False and record["reason"] == "shadow"


def test_gender_double_key_blocks_jev_without_lexicon_evidence_and_never_asks_without_candidates(tmp_path: Path) -> None:
    fake = FakeJev({"subject_gender": choice_answer("male", confidence=0.99)})
    service = _service(tmp_path, DecisionLayer(_policy("enforce", ("extract",)), fake, thresholds=LOCK))
    # 原话说的是「老婆」（女性词表），Jev 却选 male → 双钥不齐，不填。
    result = service.dispatch({"query": "帮我老婆排紫微斗数", "birth": BIRTH, "save_result": False, "agent_confirmed_settings": True})
    assert "gender" not in result.normalized_inputs["ziwei_birth"]
    record = next(r for r in result.decision_layer["records"] if r["surface"] == "extract")
    assert record["adopted"] is False and "double-key" in record["reason"]
    # 原话没有任何性别词 → 连问都不问（零调用、零 PII）。
    calls_before = len(fake.calls)
    result = service.dispatch({"query": "帮我排紫微斗数", "birth": BIRTH, "save_result": False, "agent_confirmed_settings": True})
    assert len(fake.calls) == calls_before and not [r for r in result.decision_layer["records"] if r["surface"] == "extract"]
    # 用户已经给了 gender → 不问不改。
    result = service.dispatch({"query": "帮我老婆排紫微斗数", "birth": {**BIRTH, "gender": 1}, "save_result": False, "agent_confirmed_settings": True})
    assert len(fake.calls) == calls_before and result.normalized_inputs["ziwei_birth"]["gender"] == 1


# ---- S3 六壬门类 ---------------------------------------------------------------------------------


def test_zhan_category_is_filled_in_enforce_and_only_reported_in_shadow(tmp_path: Path) -> None:
    js = RecordingJs()
    fake = FakeJev({"zhan_category": choice_answer("caiyun", confidence=0.88)})
    enforce = _service(tmp_path / "e", DecisionLayer(_policy("enforce", ("zhancat",)), fake, thresholds=LOCK), js)
    result = enforce.dispatch({"query": "六壬起课问下个月生意能不能赚钱", "birth": BIRTH, "save_result": False, "agent_confirmed_settings": True})
    assert result.selected_tools == ["liureng_gods"] and result.ok
    payload = next(p for name, p in js.payloads if name == "liureng")
    assert payload["zhanCategory"] == "caiyun"
    decisions = result.results["liureng_gods"].data["technique_card"]["decisions"]
    assert decisions[0]["surface"] == "zhancat" and decisions[0]["adopted"] is True and decisions[0]["decision"]["value"] == "caiyun"

    js2 = RecordingJs()
    shadow = _service(tmp_path / "s", DecisionLayer(_policy("shadow", ("zhancat",)), FakeJev({"zhan_category": choice_answer("caiyun", confidence=0.88)})), js2)
    result = shadow.dispatch({"query": "六壬起课问下个月生意能不能赚钱", "birth": BIRTH, "save_result": False, "agent_confirmed_settings": True})
    payload = next(p for name, p in js2.payloads if name == "liureng")
    assert "zhanCategory" not in payload or payload["zhanCategory"] is None
    decisions = result.results["liureng_gods"].data["technique_card"]["decisions"]
    assert decisions[0]["adopted"] is False and decisions[0]["reason"] == "shadow"


def test_a_bug_in_the_decision_surface_degrades_instead_of_failing_the_technique(tmp_path: Path, monkeypatch) -> None:
    """负向对照（v0.39.0 开发期真事故）：问题构造抛 QuestionSpecError 曾把 liureng_gods 打成 tool.internal_error。"""
    import horosa_skill.service as service_module

    def boom() -> None:
        raise ValueError("bad question spec")

    monkeypatch.setattr(service_module, "build_zhan_question", boom)
    service = _service(tmp_path, DecisionLayer(_policy("enforce", ("zhancat",)), FakeJev({}), thresholds=LOCK), RecordingJs())
    result = service.dispatch({"query": "六壬起课问下个月生意能不能赚钱", "birth": BIRTH, "save_result": False, "agent_confirmed_settings": True})
    envelope = result.results["liureng_gods"]
    assert envelope.ok, envelope.message
    assert any("决策层" in note and "ValueError" in note for note in envelope.warnings), envelope.warnings


def test_zhan_category_respects_user_value_and_general(tmp_path: Path) -> None:
    js = RecordingJs()
    fake = FakeJev({"zhan_category": choice_answer("general", confidence=0.95)})
    service = _service(tmp_path, DecisionLayer(_policy("enforce", ("zhancat",)), fake, thresholds=LOCK), js)
    result = service.dispatch({"query": "六壬起课看看最近运势", "birth": BIRTH, "save_result": False, "agent_confirmed_settings": True})
    payload = next(p for name, p in js.payloads if name == "liureng")
    assert not payload.get("zhanCategory"), "general → leave unset"
    assert result.results["liureng_gods"].data["technique_card"]["decisions"][0]["adopted"] is False
    calls = len(fake.calls)
    service.run_tool("liureng_gods", {**BIRTH, "zhanCategory": "hunyin", "agent_confirmed_settings": True}, save_result=False)
    assert len(fake.calls) == calls, "user-provided zhanCategory → no call"
    payload = next(p for name, p in reversed(js.payloads) if name == "liureng")
    assert payload["zhanCategory"] == "hunyin"
