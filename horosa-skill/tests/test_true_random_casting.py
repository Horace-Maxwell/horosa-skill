"""真随机起卦（v0.53.0，星阙 v3.15.0「随机起卦一律真随机」）。

用户定（2026-11-23）：skill 的随机起卦与上游同口径——取系统随机源，不再只走确定性的时间 / 生辰种子。每次把真随机记录
（tr1-<hex>）或掷出的结果随结果回传，传回即原样重开；时间 / 生辰 / 手动种子 / 报数是可选的确定性档。
负向对照：v3.14 的 skill 缺省是时间 / 生辰种子 —— 同一请求两次结果相同、seed 不是 tr1- 记录，本文件的「每次不同」与「记录长度」断言全红。
"""
from __future__ import annotations

import re

import pytest
from skips import needs_upstream, upstream_path, upstream_source
from test_sync311_divination_w3 import SIX, _ok
from test_sync311_divination_w3 import _service as _w3_service
from test_sync311_shenshu import GEO, TAROT, _run, _service

from horosa_skill.true_random import (
    ENTROPY_BYTES,
    is_entropy_seed,
    new_entropy_seed,
    seed_display_text,
)

UI = "Horosa-Web/astrostudyui/src"


@needs_upstream(f"{UI}/components/tarot/engine/shuffle.js")
def test_record_lengths_are_the_upstream_constants() -> None:
    """记录长度 = 上游各页常量（读上游源）：长度不对，引擎读到头就要 SHA-256 续接，与桌面版同一记录起出的卦不同。"""
    def const(rel: str, name: str) -> int:
        return int(re.search(rf"const {name} = (\d+);", upstream_source(upstream_path(f"{UI}/{rel}"))).group(1))

    assert ENTROPY_BYTES == {
        "tarot": const("components/tarot/engine/shuffle.js", "FULL_ENTROPY_BYTES"),
        "lingqi": const("components/lingqi/core/lingqiCast.js", "LINGQI_ENTROPY_BYTES"),
        "geomancy": const("components/geomancy/main/cast.js", "GEOMANCY_ENTROPY_BYTES"),
        "wuzhao": const("components/wuzhao/WuZhaoMain.js", "CAST_ENTROPY_BYTES"),
        "jingjue": const("components/jingjue/JingJueMain.js", "CAST_ENTROPY_BYTES"),
        "taixuan": const("components/taixuan/TaiXuanMain.js", "CAST_ENTROPY_BYTES"),
    }


def test_entropy_seed_format_and_display() -> None:
    seed = new_entropy_seed(32)
    assert is_entropy_seed(seed) and len(seed) == 4 + 64 and seed != new_entropy_seed(32)
    assert seed_display_text(seed) == f"真随机 {seed[4:12]}…" and seed_display_text(12345) == "12345"
    assert seed_display_text("tr1-abcd") == "真随机 abcd"


# ── 塔罗 ─────────────────────────────────────────────────────────────────────────────────────────────


def test_tarot_defaults_to_a_true_random_record_and_replays_it(tmp_path) -> None:
    service, _, js = _service(tmp_path)
    a, b = _run(service, "tarot", TAROT).data, _run(service, "tarot", TAROT).data
    assert a["cast_method"] == "random" and is_entropy_seed(a["seed"]) and len(a["seed"]) == 4 + 2 * ENTROPY_BYTES["tarot"]
    assert a["seed"] != b["seed"]
    assert a["cast"] == {"method": "random", "random": True, "source": "system", "replay": {"seed": a["seed"]}}   # 插件读的固定字段
    assert a["seed_display"] == seed_display_text(a["seed"])
    replay = _run(service, "tarot", {**TAROT, "seed": a["seed"]}).data
    assert replay["cast_method"] == "seed" and replay["seed"] == a["seed"] and replay["cast"]["random"] is False
    assert [p["seed"] for t, p in js.calls if t == "tarot"][-1] == a["seed"]   # 引擎收到的就是那条记录


def test_tarot_true_random_draws_differ_and_replay_is_byte_identical(tmp_path) -> None:
    """真 JS 引擎（非桩）：缺省两次抽牌不同，传回记录逐字节同一副牌；快照种子行写短指纹（上游 seedDisplayText）。"""
    svc = _w3_service(tmp_path)
    base = {**SIX, "agent_confirmed_settings": True}
    base.pop("lines", None)
    base.pop("castMethod", None)
    first, second = _ok(svc, "tarot", base).data, _ok(svc, "tarot", base).data
    assert first["snapshot_text"] != second["snapshot_text"]
    assert f"(种子:{seed_display_text(first['seed'])})" in first["snapshot_text"]
    assert _ok(svc, "tarot", {**base, "seed": first["seed"]}).data["snapshot_text"] == first["snapshot_text"]


# ── 灵棋 ─────────────────────────────────────────────────────────────────────────────────────────────


def test_lingqi_defaults_to_true_random_and_replays_by_seed_or_counts(tmp_path) -> None:
    svc = _w3_service(tmp_path)
    base = {**SIX, "agent_confirmed_settings": True}
    base.pop("lines", None)
    base.pop("castMethod", None)
    runs = [_ok(svc, "lingqi", base).data for _ in range(12)]
    assert all(r["cast_method"] == "random" and is_entropy_seed(r["seed"]) and len(r["seed"]) == 4 + 2 * ENTROPY_BYTES["lingqi"] for r in runs)
    assert len({tuple(r["counts"]) for r in runs}) > 1, "十二次真随机掷棋不该全同一卦"
    first = runs[0]
    assert first["cast"] == {"method": "random", "random": True, "source": "system", "replay": {"seed": first["seed"]}}
    assert _ok(svc, "lingqi", {**base, "seed": first["seed"]}).data["counts"] == first["counts"]
    assert _ok(svc, "lingqi", {**base, "counts": first["counts"]}).data["snapshot_text"] == first["snapshot_text"]
    timed = [_ok(svc, "lingqi", {**base, "seedMode": "time_seed"}).data for _ in range(2)]
    assert timed[0]["counts"] == timed[1]["counts"] and timed[0]["cast_method"] == "time"


# ── 地占 ─────────────────────────────────────────────────────────────────────────────────────────────


def test_geomancy_defaults_to_true_random_and_replays_the_record(tmp_path) -> None:
    """上游 clickCast：随机档 seedMode random + 192 字节记录（不发 timeSeed）；皮肤四法 castMethod 如实；手动档原样回放。"""
    service, client, _ = _service(tmp_path)
    data = _run(service, "geomancy", GEO).data
    sent = client.sent("/geomancy/reading")[-1]
    assert sent["seedMode"] == "random" and is_entropy_seed(sent["seed"]) and len(sent["seed"]) == 4 + 2 * ENTROPY_BYTES["geomancy"]
    assert "timeSeed" not in sent and "castMethod" not in sent
    assert data["cast_method"] == "random" and data["cast"] == {"method": "random", "random": True, "source": "system", "replay": {"seed": sent["seed"]}}
    _run(service, "geomancy", {**GEO, "seedMode": "coins"})
    coins = client.sent("/geomancy/reading")[-1]
    assert coins["castMethod"] == "coins" and coins["seedMode"] == "random" and is_entropy_seed(coins["seed"]) and coins["seed"] != sent["seed"]
    _run(service, "geomancy", {**GEO, "seed": sent["seed"]})
    replay = client.sent("/geomancy/reading")[-1]
    assert replay["seedMode"] == "manual" and replay["seed"] == sent["seed"] and "timeSeed" not in replay
    _run(service, "geomancy", {**GEO, "seed": "42"})
    assert client.sent("/geomancy/reading")[-1]["seed"] == 42


def test_geomancy_rejects_an_unusable_manual_seed(tmp_path) -> None:
    service, client, _ = _service(tmp_path)
    env = _run(service, "geomancy", {**GEO, "seed": "not-a-seed"})
    assert env.ok is False and "geomancy" in env.error.code and not client.sent("/geomancy/reading")   # 拒收、不悄悄改成随机


# ── 荆诀 / 太玄 ──────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("tool", ["jingjue", "taixuan"])
def test_jingjue_taixuan_default_to_a_32_byte_record_and_replay_it(tmp_path, tool: str) -> None:
    """上游页面 defaultSeed = newEntropySeed(32)：后端逐位读记录定分策、原样回传。显式记录 / 整数原样下发；time_seed 档同刻同卦。"""
    from test_sync311_shenshu import BASE, SEED_19980220_2048

    service, client, _ = _service(tmp_path)
    first = _run(service, tool, BASE)
    sent = client.sent(f"/{tool}/pan")[-1]["seed"]
    assert first.ok and is_entropy_seed(sent) and len(sent) == 4 + 2 * ENTROPY_BYTES[tool]
    assert first.data["seed"] == sent and first.data["cast"] == {"method": "random", "random": True, "source": "system", "replay": {"options": {"seed": sent}}}
    assert first.data["technique_card"]["settings"]["seed"]["value"] == seed_display_text(sent)
    _run(service, tool, BASE)
    assert client.sent(f"/{tool}/pan")[-1]["seed"] != sent, "每次新起一卦"
    replay = _run(service, tool, {**BASE, "options": {"seed": sent}})
    assert replay.ok and client.sent(f"/{tool}/pan")[-1]["seed"] == sent and replay.data["cast"]["random"] is False
    _run(service, tool, {**BASE, "options": {"seedMode": "time_seed"}})
    assert client.sent(f"/{tool}/pan")[-1]["seed"] == SEED_19980220_2048


# ── 小成图 / 六爻 / 骰子 ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fa", ["dayan", "yaoqian"])
def test_xiaochengtu_dayan_and_yaoqian_cast_true_random_and_replay_by_counts(tmp_path, fa: str) -> None:
    """负向对照：v3.14 skill 不给 seed 就拒收 dayan（tool.xiaochengtu_dayan_seed_required），yaoqian 根本不认。"""
    svc = _w3_service(tmp_path)
    runs = [_ok(svc, "xiaochengtu", {"qiguaFa": fa, "agent_confirmed_settings": True}).data for _ in range(8)]
    assert len({tuple(r["xiaochengtu"]["counts"]) for r in runs}) > 1
    first = runs[0]
    assert first["cast"] == {"method": fa, "random": True, "source": "system", "replay": {"qiguaFa": fa, "manualCounts": first["xiaochengtu"]["counts"]}}
    replay = _ok(svc, "xiaochengtu", {"qiguaFa": fa, "manualCounts": first["xiaochengtu"]["counts"], "agent_confirmed_settings": True}).data
    assert replay["snapshot_text"] == first["snapshot_text"] and replay["cast"]["random"] is False


@pytest.mark.parametrize("method", [None, "coins"])
def test_sixyao_without_lines_is_a_true_random_cast_replayable_by_lines(tmp_path, method) -> None:
    """不给 lines / gua_code：缺省大衍蓍草（上游 castRandomCase 代摇缺省）/ coins 三钱，逐爻系统随机；castMethod=time 才以时起卦。
    负向对照：v3.14 skill 此时恒以时起卦 —— 同一占时六次同一卦。"""
    svc = _w3_service(tmp_path)
    base = {**{k: v for k, v in SIX.items() if k != "castMethod"}, "agent_confirmed_settings": True, **({"castMethod": method} if method else {})}
    base.pop("lines", None)
    runs = [_ok(svc, "sixyao", base).data for _ in range(8)]
    assert all(r["cast_method"] == (method or "yarrow") for r in runs)
    assert len({r["current_code"] + r["changed_code"] for r in runs}) > 1
    first = runs[0]
    assert first["cast"]["random"] is True and first["cast"]["source"] == "system"
    assert first["cast"]["replay"]["lines"] == [{"value": x["value"], "change": x["change"]} for x in first["lines"]]
    replay = _ok(svc, "sixyao", {**base, **first["cast"]["replay"]}).data   # 无状态调用方：data.cast.replay 原样传回
    assert (replay["current_code"], replay["changed_code"], replay["cast_method"]) == (first["current_code"], first["changed_code"], "manual")
    timed = [_ok(svc, "sixyao", {**base, "castMethod": "time"}).data for _ in range(2)]
    assert timed[0]["current_code"] == timed[1]["current_code"] and timed[0]["cast_method"] == "time"


def test_dice_rolls_whatever_was_not_given(tmp_path) -> None:
    from horosa_skill.service.runners.cn_divination import _DICE_ALL_PLANETS, _DICE_SIGNS, _DICE_TRAD_PLANETS

    service, client, _ = _service(tmp_path)
    from test_sync311_shenshu import BASE, PLACE

    BASE = {**BASE, **PLACE}
    rolls = [_run(service, "otherbu", BASE).data for _ in range(10)]
    assert all(r["cast"]["method"] == "roll" and r["cast"]["random"] and r["cast"]["replay"] == r["dice"] for r in rolls)
    assert len({(r["dice"]["planet"], r["dice"]["sign"], r["dice"]["house"]) for r in rolls}) > 1
    assert all(r["dice"]["planet"] in _DICE_ALL_PLANETS and r["dice"]["sign"] in _DICE_SIGNS and 0 <= r["dice"]["house"] < 12 for r in rolls)
    trad = _run(service, "otherbu", {**BASE, "tradition": True}).data
    assert trad["dice"]["planet"] in _DICE_TRAD_PLANETS
    fixed = _run(service, "otherbu", {**BASE, "planet": "Mars", "sign": "Leo", "house": 3}).data
    assert fixed["dice"] == {"planet": "Mars", "sign": "Leo", "house": 3} and fixed["cast"]["method"] == "given" and not fixed["cast"]["random"]
    sent = client.sent("/predict/dice")[-1]
    assert (sent["planet"], sent["sign"], sent["house"]) == ("Mars", "Leo", 3)


@needs_upstream(f"{UI}/components/dice/DiceMain.js")
def test_dice_pools_are_the_upstream_lists() -> None:
    from horosa_skill.service.runners.cn_divination import _DICE_ALL_PLANETS, _DICE_SIGNS, _DICE_TRAD_PLANETS

    consts = dict(re.findall(r"^export const (\w+) = '([^']*)'", upstream_source(upstream_path(f"{UI}/constants/AstroConst.js")), re.M))
    dice = upstream_source(upstream_path(f"{UI}/components/dice/DiceMain.js"))
    def pool(name: str) -> tuple[str, ...]:
        body = re.search(rf"const {name} = \[(.*?)\];", dice, re.S).group(1)
        return tuple(consts[x.split(".")[1].strip()] for x in body.split(",") if x.strip())
    assert pool("ALL_PLANETS") == _DICE_ALL_PLANETS and pool("TRAD_PLANETS") == _DICE_TRAD_PLANETS
    signs = re.search(r"export const LIST_SIGNS = \[(.*?)\]", upstream_source(upstream_path(f"{UI}/constants/AstroConst.js")), re.S).group(1)
    assert tuple(consts[x.strip()] for x in signs.split(",") if x.strip()) == _DICE_SIGNS


def test_huangji_random_history_year(tmp_path) -> None:
    """上游 HuangJiMain.randomHistoryYear = 1900 + randomInt(201)：historyYear="random" 由软件以系统随机源掷，掷出的年随结果回传。"""
    from test_sync311_shenshu import BASE

    service, client, _ = _service(tmp_path)
    years = set()
    for _ in range(12):
        result = _run(service, "wangji", {**BASE, "options": {"historyYear": "random"}})
        assert result.ok, result.error
        year = client.sent("/wangji/pan")[-1]["historyYear"]
        assert 1900 <= year <= 2100 and result.data["cast"]["replay"] == {"options": {"historyYear": year}}
        years.add(year)
    assert len(years) > 1
    fixed = _run(service, "wangji", {**BASE, "options": {"historyYear": 1999}})
    assert fixed.ok and client.sent("/wangji/pan")[-1]["historyYear"] == 1999
