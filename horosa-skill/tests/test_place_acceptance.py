"""地名接受规则（v0.50.0，horosa-core-js src/tools/placeResolve.js + service/api/place.py）。

上游 resolvePlaceOffline 的「high」会经拼音首字母 / 地区半截提示给错城市（NYC → 银川、HK → 海口、St. Petersburg →
佛州），上游字段的逐值对拍在 test_place_search.py；这里锁 skill 自己的规则：
- 语料：≥300 条查询（审计清单 + 冷客户端失败写法 + 繁体 / 拼音 / 限定词 / 旧称 / 错字），每条的期望结论；
- 全库性质：城市库每一条用「本名, 本地区」查都回到它自己（或同地区重名时歧义里有它），绝不解析到别处；
- 别名表每个目标在库里唯一；提示语里举的每个写法都真能解析；
- 门面 / 技法 / 档案入口的可见行为：坐标写进 place、只给地区、单候选措辞、错字建议、time 校验、limit 截断告知、
  place + 经纬度不给 zone、旧 runtime 的保守路径。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import RECOVERY_TABLE, ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.api.place import PLACE_EXAMPLES_EN, PLACE_EXAMPLES_ZH

PKG = Path(__file__).resolve().parents[1]
CORE_JS = PKG / "horosa-core-js"
PLACE_DATA = CORE_JS / "src" / "vendor" / "place" / "data"
ALIASES = CORE_JS / "src" / "tools" / "placeData" / "aliases.json"
CORPUS = Path(__file__).resolve().parent / "fixtures" / "place_corpus.json"
PROPERTY = Path(__file__).resolve().parent / "fixtures" / "place_search" / "library_property.mjs"
TZ_LOOKUP = CORE_JS / "node_modules" / "tz-lookup" / "tz.js"

requires_engine = pytest.mark.skipif(
    shutil.which("node") is None or not TZ_LOOKUP.is_file(),
    reason="node + horosa-core-js node_modules (npm ci --omit=dev) required",
)


def _service(tmp_path: Path, js_client: Any = None) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
    )
    return HorosaSkillService(settings, store=MemoryStore(settings), js_client=js_client)


def _refusal(service: HorosaSkillService, place: str, **extra: Any) -> ToolValidationError:
    with pytest.raises(ToolValidationError) as exc:
        service.resolve_place_fields({"date": "1988-07-01", "time": "08:00", "place": place, **extra}, tool_name="chart")
    return exc.value


# ── 语料与全库性质 ────────────────────────────────────────────────────────────────────────────────


def _outcome(verdict: dict[str, Any]) -> dict[str, Any]:
    """把一条 batch 裁决压成语料的比较形状（与 tests/fixtures/place_corpus.json 的行同构）。"""
    status = verdict["status"]
    row: dict[str, Any] = {"q": verdict["query"], "expect": status}
    if status in ("resolved", "confirm"):
        match = verdict["match"] or verdict["candidates"][0]
        row["place"] = f"{match['name']}|{match['region']}"
        if verdict.get("alias"):
            row["alias"] = verdict["alias"]["kind"]
        if verdict.get("caveats"):
            row["caveats"] = verdict["caveats"]
    elif status in ("ambiguous", "qualifier_mismatch"):
        row["candidates"] = sorted(f"{c['name']}|{c['region']}" for c in verdict["candidates"])
        row["total"] = verdict["total"]
    elif status == "not_found" and verdict.get("suggestions"):
        first = verdict["suggestions"][0]
        row["first_suggestion"] = f"{first['name']}|{first['region']}"
    return row


@requires_engine
def test_place_corpus_outcomes(tmp_path: Path) -> None:
    """负向对照（实跑过）：placeResolve.js 的精确键里加回拼音首字母（_pi）→ NYC / HK / BJ 等十几行变红；
    去掉「跨分隔符不粘连」→ 'León, ES' 一类在全库性质里变红。"""
    cases = json.loads(CORPUS.read_text(encoding="utf-8"))["cases"]
    assert len(cases) >= 300 and len({c["q"] for c in cases}) == len(cases)
    verdicts = _service(tmp_path).place_verdicts([c["q"] for c in cases])
    got = [{**_outcome(v), "q": case["q"]} for case, v in zip(cases, verdicts, strict=True)]
    wrong = [(case, g) for case, g in zip(cases, got, strict=True) if g != case]
    assert not wrong, "\n".join(f"{json.dumps(c, ensure_ascii=False)}\n  got {json.dumps(g, ensure_ascii=False)}" for c, g in wrong[:20])


@requires_engine
def test_every_library_entry_resolves_to_itself_with_its_own_region() -> None:
    """全库 50 077 条：「本名, 本地区」→ 它自己（resolved，或同地区有重名时 ambiguous 且候选里有它）；省 / 自治区 =
    too_broad（设计如此）。任何一条解析到别处 = 红。负向对照：readings() 不跳过「跨逗号粘连」→ 9 条红（León, ES →
    Leones AR、Tāl, IN → 塔林 …，实跑过）。"""
    completed = subprocess.run(
        ["node", str(PROPERTY), str(CORE_JS)], capture_output=True, text=True, encoding="utf-8", timeout=300, check=False,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    report = json.loads(completed.stdout)
    assert report["alias_problems"] == []
    assert report["counts"].get("offenders", 0) == 0, report["offenders"]
    counts = report["counts"]
    assert counts["resolved_self"] + counts["ambiguous_with_self"] + counts["too_broad_province"] == report["entries"]
    assert counts["resolved_self"] > 0.9 * report["entries"]


def test_every_alias_target_is_exactly_one_library_entry() -> None:
    """别名只指向库里的条目（坐标从条目来，别名表里没有坐标）：{name, region} 在小库 + 大库里恰好一条。
    负向对照：把「九龙城区」的 region 改成「九龙」→ 红。"""
    small = json.loads((PLACE_DATA / "cities.json").read_text(encoding="utf-8"))
    full = json.loads((PLACE_DATA / "citiesFull.json").read_text(encoding="utf-8"))
    rows = [(c["name"], c["region"]) for c in small] + [(c["n"], c["r"]) for c in full]
    data = json.loads(ALIASES.read_text(encoding="utf-8"))
    for alias in data["aliases"]:
        target = (alias["target"]["name"], alias["target"]["region"])
        assert rows.count(target) == 1, (alias["keys"], target)
        assert alias["kind"] in {"abbreviation", "exonym", "variant", "historical", "nickname", "approximate"}
        assert not re.search(r"\d+\.\d+", json.dumps(alias)), "no coordinates in the alias table"
    for item in data["unresolvable"]:
        assert item["zh"] and item["en"] and item["try"]


@requires_engine
def test_examples_in_prompts_really_resolve(tmp_path: Path) -> None:
    """提示语只举真能用的写法：place.py 的例子常量 + errors.py 里 place.* 的提示里每个「」/ '' 引起来的写法。
    负向对照：例子里放回旧提示的「辽宁朝阳市」式写法以外的不可解析写法（如「广东」）→ 红。"""
    quoted: set[str] = set()
    for code, entry in RECOVERY_TABLE.items():
        if code.startswith("place."):
            quoted.update(re.findall(r"「([^」]+)」", entry["prompt_to_user"]))
            quoted.update(re.findall(r"'([^']+)'", entry["prompt_to_user"]))
    examples = [*PLACE_EXAMPLES_ZH, *PLACE_EXAMPLES_EN, *sorted(quoted)]
    unsupported = json.loads(ALIASES.read_text(encoding="utf-8"))["unresolvable"]
    examples += [name for item in unsupported for name in item["try"]]
    verdicts = _service(tmp_path).place_verdicts(examples)
    assert [v["query"] for v in verdicts if v["status"] != "resolved"] == []


# ── P0：错城市不再 high ────────────────────────────────────────────────────────────────────────────


@requires_engine
def test_pinyin_initials_and_partial_region_hints_never_pick_a_city(tmp_path: Path) -> None:
    """PL-2：上游对 NYC / HK 给 high 银川 / 海口，对 St. Petersburg 给 high 佛州；skill 不再照收。
    负向对照：_resolve_one_spot 改回只看上游 resolved+high → 银川，红（实跑过）。"""
    service = _service(tmp_path)
    nyc = service.resolve_place_fields({"date": "1988-07-01", "time": "08:00", "place": "NYC"}, tool_name="chart")
    assert nyc["placeResolution"]["name"] == "纽约" and nyc["placeResolution"]["alias"] == {"text": "NYC", "kind": "abbreviation"}
    hk = service.resolve_place_fields({"date": "1988-07-01", "time": "08:00", "place": "HK"}, tool_name="chart")
    assert hk["placeResolution"]["name"] == "香港"
    spb = _refusal(service, "St. Petersburg")
    assert spb.code == "place.ambiguous" and spb.details["status"] == "ambiguous"
    assert {(c["name"], c["region"]) for c in spb.details["candidates"]} == {("圣彼得堡", "RU"), ("St. Petersburg", "US")}
    # 拼音首字母只给「最接近的名字」，不自动填。
    view = service.place_search({"query": "SH", "date": "1988-07-01"})
    assert view["resolved"] is False and view["status"] == "near" and view["upstream_confidence"] in (None, "high", "medium")


@requires_engine
def test_facade_reports_how_a_place_was_matched(tmp_path: Path) -> None:
    view = _service(tmp_path).place_search({"query": "NYC", "date": "1988-07-01"})
    assert view["resolved"] is True and view["confidence"] == "high" and view["match"]["name"] == "纽约"
    assert view["upstream_confidence"] == "high"  # 上游自己的结论（银川）照报，不再被当作接受依据
    assert view["matched"]["matched_by"] == "alias" and view["matched"]["policy"] == "skill-place-acceptance/1"
    assert view["match"]["where"] == ["美国"]


# ── 各种不能自动接受的情形 ───────────────────────────────────────────────────────────────────────


@requires_engine
def test_coordinates_typed_into_place_are_their_own_error(tmp_path: Path) -> None:
    for text in ("31.2,121.5", "121.47, 31.23", "31°13′N 121°28′E"):
        err = _refusal(_service(tmp_path), text)
        assert err.code == "place.looks_like_coordinates", text
        assert "lat" in err.details["agent_recovery"]["prompt_to_user"]


@requires_engine
def test_region_only_is_too_broad(tmp_path: Path) -> None:
    service = _service(tmp_path)
    for text in ("美国", "广东", "Texas", "UK"):
        err = _refusal(service, text)
        assert err.code == "place.too_broad", text
        assert err.details["regions"], text


@requires_engine
def test_one_candidate_is_never_called_ambiguous(tmp_path: Path) -> None:
    """单候选（限定词核对不了 / 只有一个近似名）措辞是「请确认」，不说「不止一个」。负向对照：_refusal_texts 对单候选
    也用 ambiguous 那句 → 红。"""
    service = _service(tmp_path)
    confirm = _refusal(service, "Saint Petersburg, FL")
    assert confirm.code == "place.ambiguous" and confirm.details["status"] == "confirm" and len(confirm.details["candidates"]) == 1
    near = _refusal(service, "Parris")
    assert near.details["status"] == "near" and len(near.details["candidates"]) == 1
    for err in (confirm, near):
        prompt = err.details["agent_recovery"]["prompt_to_user"]
        assert "不止一个" not in prompt and "more than one" not in prompt and "个不同地点" not in prompt


@requires_engine
def test_typos_get_nearest_name_suggestions(tmp_path: Path) -> None:
    service = _service(tmp_path)
    for text, expected in (("上诲", "上海"), ("shnaghai", "上海"), ("Londn", "伦敦")):
        err = _refusal(service, text)
        assert err.code == "place.not_found" and err.details["suggestions"][0]["name"] == expected, text
        assert expected in " ".join(err.details["ask_if_missing"][0]["options"])


@requires_engine
def test_unresolvable_area_says_what_works(tmp_path: Path) -> None:
    err = _refusal(_service(tmp_path), "新界")
    assert err.code == "place.not_found" and "沙田区" in err.details["agent_recovery"]["prompt_to_user"]


@requires_engine
def test_historical_name_resolves_with_a_caveat_naming_the_modern_city(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(tmp_path)
    monkeypatch.setattr(service, "_run_local_tool", lambda definition, payload: {"ok": True})
    envelope = service.run_tool("xiaoliuren", {"date": "1988-07-01", "time": "08:00", "place": "北平"}, save_result=False)
    assert any("北平" in w and "北京" in w and "旧称" in w for w in envelope.warnings), envelope.warnings
    assert envelope.data["technique_card"]["place_resolution"][0]["caveats"] == ["alias_historical"]


# ── PL-4：门面入参 ────────────────────────────────────────────────────────────────────────────────


@requires_engine
def test_facade_validates_time_and_says_when_limit_was_clamped(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(ToolValidationError) as bad:
        service.place_search({"query": "上海", "date": "1988-07-01", "time": "25:99:xx"})
    assert bad.value.code == "place.invalid_payload" and bad.value.details["field"] == "time"
    view = service.place_search({"query": "朝阳", "date": "1988-07-01", "limit": 50})
    assert len(view["candidates"]) <= 10 and any("limit=50" in w for w in view["warnings"])
    quiet = service.place_search({"query": "朝阳", "date": "1988-07-01", "limit": 3})
    assert not any("limit" in w for w in quiet["warnings"])


# ── place + 显式经纬度 ─────────────────────────────────────────────────────────────────────────────


@requires_engine
def test_place_with_coordinates_but_no_zone_derives_the_zone_from_the_coordinates(tmp_path: Path) -> None:
    """以前：place 被静默丢掉、zone 不补，再由校验层回头要 zone。现在按这组坐标 + 日期补（同一个上游 dstAwareZoneAt）。"""
    service = _service(tmp_path)
    out = service.resolve_place_fields(
        {"date": "1988-07-01", "time": "08:00", "lat": "31n13", "lon": "121e28", "place": "我家"}, tool_name="chart")
    assert out["zone"] == "+09:00" and "place" not in out
    record = out["placeResolution"]
    assert (record["status"], record["zone_source"], record["iana"]) == ("explicit_coordinates", "coordinates_and_date", "Asia/Shanghai")
    no_date = service.resolve_place_fields({"lat": "31n13", "lon": "121e28", "place": "我家"}, tool_name="chart")
    assert "zone" not in no_date and no_date["placeResolution"]["status"] == "explicit_coordinates"


def test_explicit_zone_and_coordinates_still_skip_the_engine(tmp_path: Path) -> None:
    class Boom:
        def run(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
            raise AssertionError("engine must not be called")

    out = _service(tmp_path, Boom()).resolve_place_fields(
        {"date": "1988-07-01", "lat": "31n13", "lon": "121e28", "zone": "+08:00", "place": "上海"}, tool_name="chart")
    assert out["zone"] == "+08:00" and out["placeResolution"]["status"] == "explicit_coordinates"


# ── 旧 runtime（回包没有 verdict）────────────────────────────────────────────────────────────────


class _UpstreamOnly:
    """v0.49 runtime 的 place_search 回包：只有上游字段。"""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def run(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "data": {"query": payload.get("query"), "date": payload.get("date"), "code": None, **self.data}}


def _upstream_place(name: str, en: str, region: str, lat: float, lon: float) -> dict[str, Any]:
    return {"name": name, "en": en, "region": region, "gpsLat": lat, "gpsLon": lon, "iana": "Asia/Shanghai",
            "geoZone": "Asia/Shanghai", "zone": "+08:00", "dst": False, "advisory": None}


def test_old_runtime_without_verdict_accepts_only_exact_names(tmp_path: Path) -> None:
    """负向对照：_fallback_verdict 只看上游 high → NYC 被填成银川，红。"""
    yinchuan = _upstream_place("银川", "Yinchuan", "中国·宁夏", 38.4872, 106.2309)
    stale = _service(tmp_path, _UpstreamOnly({"resolved": True, "confidence": "high", "match": yinchuan, "candidates": [yinchuan]}))
    err = _refusal(stale, "NYC")
    assert err.code == "place.ambiguous" and err.details["status"] == "near"
    shanghai = _upstream_place("上海", "Shanghai", "中国", 31.2304, 121.4737)
    ok = _service(tmp_path, _UpstreamOnly({"resolved": True, "confidence": "high", "match": shanghai, "candidates": [shanghai]}))
    view = ok.place_search({"query": "Shanghai", "date": "1988-07-01"})
    assert view["resolved"] is True and view["policy"] == "conservative-fallback"
    assert any("v0.50.0" in w for w in view["warnings"])
