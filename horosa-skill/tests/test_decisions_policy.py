"""决策层策略：缺省 off = 零对象；配置不合法整体关闭并说明；doctor 视图永不含 key。"""

from __future__ import annotations

from horosa_skill.decisions.policy import (
    DEFAULT_MODEL,
    DEFAULT_SURFACES,
    Policy,
    enforce_allowed,
    load_policy,
    resolve_tau,
)

KEY = "sk-test-0123456789abcdef0123456789abcdef"


def test_default_is_off_and_problem_free() -> None:
    policy = load_policy({})
    assert policy.mode == "off" and not policy.enabled
    assert policy.problems == ()
    assert policy.surfaces == frozenset(DEFAULT_SURFACES)
    assert policy.model == DEFAULT_MODEL
    assert policy.key_present is False


def test_shadow_requires_a_key_or_stays_off() -> None:
    policy = load_policy({"HOROSA_JEV": "shadow"})
    assert policy.mode == "off" and policy.requested_mode == "shadow"
    assert any("no API key" in problem for problem in policy.problems)
    policy = load_policy({"HOROSA_JEV": "shadow", "HOROSA_JEV_API_KEY": KEY})
    assert policy.mode == "shadow" and policy.key_present and policy.problems == ()


def test_fallback_key_env_is_honoured() -> None:
    policy = load_policy({"HOROSA_JEV": "shadow", "TYPESAFE_API_KEY": KEY})
    assert policy.mode == "shadow" and policy.key_present


def test_invalid_mode_scope_surface_or_url_turns_the_layer_off() -> None:
    base = {"HOROSA_JEV_API_KEY": KEY}
    assert load_policy({**base, "HOROSA_JEV": "on"}).mode == "off"
    assert load_policy({**base, "HOROSA_JEV": "shadow", "HOROSA_JEV_SCOPE": "everything"}).mode == "off"
    assert load_policy({**base, "HOROSA_JEV": "shadow", "HOROSA_JEV_SURFACES": "dispatch,telepathy"}).mode == "off"
    http = load_policy({**base, "HOROSA_JEV": "shadow", "HOROSA_JEV_BASE_URL": "http://api.typesafe.ai"})
    assert http.mode == "off" and any("https" in problem for problem in http.problems)
    # 回环 http 允许（测试桩服务器）。
    assert load_policy({**base, "HOROSA_JEV": "shadow", "HOROSA_JEV_BASE_URL": "http://127.0.0.1:9"}).mode == "shadow"


def test_jev_latest_alias_cannot_be_enforced() -> None:
    policy = load_policy({"HOROSA_JEV": "enforce", "HOROSA_JEV_API_KEY": KEY, "HOROSA_JEV_MODEL": "jev-latest"})
    assert policy.mode == "shadow"
    assert any("jev-latest" in problem for problem in policy.problems)


def test_snapshot_surfaces_need_snapshot_scope() -> None:
    meta = load_policy({"HOROSA_JEV": "shadow", "HOROSA_JEV_API_KEY": KEY, "HOROSA_JEV_SURFACES": "dispatch,faithfulness"})
    assert meta.surface_enabled("dispatch") and not meta.surface_enabled("faithfulness")
    snap = load_policy({**{"HOROSA_JEV": "shadow", "HOROSA_JEV_API_KEY": KEY, "HOROSA_JEV_SURFACES": "faithfulness"}, "HOROSA_JEV_SCOPE": "snapshot"})
    assert snap.surface_enabled("faithfulness")


def test_timeout_is_clamped_and_bad_values_reported() -> None:
    assert load_policy({"HOROSA_JEV_TIMEOUT_MS": "50"}).timeout_s == 0.2
    assert load_policy({"HOROSA_JEV_TIMEOUT_MS": "999999"}).timeout_s == 30.0
    policy = load_policy({"HOROSA_JEV_TIMEOUT_MS": "fast"})
    assert policy.timeout_s == 3.0 and any("TIMEOUT" in problem for problem in policy.problems)


def test_doctor_view_never_carries_the_key() -> None:
    policy = load_policy({"HOROSA_JEV": "shadow", "HOROSA_JEV_API_KEY": KEY})
    view = policy.doctor_view(None)
    assert KEY not in repr(view)
    assert view["key_present"] is True and view["data_leaves_machine"] is True
    assert view["thresholds_lock"] == {"present": False, "model": None, "promoted_surfaces": []}
    off = load_policy({}).doctor_view(None)
    assert off["data_leaves_machine"] is False


def test_enforce_needs_a_matching_promoted_lock() -> None:
    policy = Policy(
        mode="enforce", scope="meta", surfaces=frozenset({"dispatch"}), model="jev-1.13.0",
        base_url="https://api.typesafe.ai", timeout_s=3.0, ledger=False, key_present=True, requested_mode="enforce",
    )
    assert enforce_allowed(policy, "dispatch", None) == (False, "no thresholds lock (contracts/jev_thresholds.json)")
    wrong_model = {"model": "jev-1.12.0", "surfaces": {"dispatch": {"tau": 0.7, "promoted": True}}}
    assert enforce_allowed(policy, "dispatch", wrong_model)[0] is False
    not_promoted = {"model": "jev-1.13.0", "surfaces": {"dispatch": {"tau": 0.7, "promoted": False}}}
    assert enforce_allowed(policy, "dispatch", not_promoted)[0] is False
    promoted = {"model": "jev-1.13.0", "surfaces": {"dispatch": {"tau": 0.82, "promoted": True}}}
    assert enforce_allowed(policy, "dispatch", promoted) == (True, "promoted")
    assert resolve_tau("dispatch", promoted) == (0.82, "thresholds_lock")
    assert resolve_tau("dispatch", None) == (0.70, "shadow_default")
