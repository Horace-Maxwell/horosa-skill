"""一级行政区包围盒（审计 F13 / S-15）：「Portland, OR」「Springfield, IL」以前消不了歧，候选之间只有坐标不同。

包围盒是手写的近似值（placeData/subdivision_boxes.json）：这里拿城市库自己核——每个州 / 省 / 领地挑一座库里唯一的城市，必须落在它的盒里。
负向对照（实跑过）：applyQualifiers 里 S: 锚点退回「只看国家」→ 第二条红；盒表里把 OR 的经度写反 → 第一条红。
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

CORE = Path(__file__).resolve().parents[1] / "horosa-core-js"
BOXES = json.loads((CORE / "src" / "tools" / "placeData" / "subdivision_boxes.json").read_text(encoding="utf-8"))
FULL = json.loads((CORE / "src" / "vendor" / "place" / "data" / "citiesFull.json").read_text(encoding="utf-8"))
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")

# 每个州 / 省先试的几座城（取第一座在该国库里唯一的）
PROBES = {
    "US": {"AL": ["Montgomery", "Birmingham"], "AK": ["Juneau", "Anchorage"], "AZ": ["Phoenix"], "AR": ["Little Rock"], "CA": ["Sacramento"],
           "CO": ["Denver"], "CT": ["Hartford"], "DE": ["Dover", "Wilmington"], "DC": ["Washington, D.C.", "Washington"], "FL": ["Tallahassee"],
           "GA": ["Atlanta"], "HI": ["Honolulu"], "ID": ["Boise"], "IL": ["Chicago"], "IN": ["Indianapolis"], "IA": ["Des Moines"],
           "KS": ["Topeka", "Wichita"], "KY": ["Frankfort", "Louisville"], "LA": ["Baton Rouge"], "ME": ["Bangor", "Augusta"], "MD": ["Annapolis", "Baltimore"],
           "MA": ["Worcester", "Lowell", "Boston"], "MI": ["Lansing", "Detroit"], "MN": ["Saint Paul", "Minneapolis"], "MS": ["Gulfport", "Jackson"],
           "MO": ["Jefferson City", "Kansas City"], "MT": ["Helena", "Billings"], "NE": ["Lincoln", "Omaha"], "NV": ["Carson City", "Reno"],
           "NH": ["Nashua", "Manchester"], "NJ": ["Trenton", "Newark"], "NM": ["Santa Fe", "Albuquerque"], "NY": ["Buffalo", "Albany"],
           "NC": ["Raleigh"], "ND": ["Bismarck", "Fargo"], "OH": ["Cleveland", "Columbus"], "OK": ["Oklahoma City", "Tulsa"], "OR": ["Eugene", "Salem"],
           "PA": ["Harrisburg", "Pittsburgh"], "RI": ["Providence"], "SC": ["Spartanburg", "Columbia"], "SD": ["Pierre", "Sioux Falls"],
           "TN": ["Nashville", "Memphis"], "TX": ["Houston"], "UT": ["Salt Lake City"], "VT": ["Montpelier", "Burlington"], "VA": ["Norfolk", "Richmond"],
           "WA": ["Olympia", "Spokane"], "WV": ["Morgantown", "Charleston"], "WI": ["Milwaukee", "Madison"], "WY": ["Cheyenne", "Casper"]},   # 波多黎各在库里是独立国家码 PR
    "CA": {"AB": ["Edmonton", "Calgary"], "BC": ["Vancouver"], "MB": ["Winnipeg"], "NB": ["Fredericton"], "NL": ["St. John's"], "NS": ["Halifax"],
           "ON": ["Toronto"], "PE": ["Charlottetown"], "QC": ["Québec", "Quebec", "Montréal"], "SK": ["Regina"], "NT": ["Yellowknife"], "NU": ["Iqaluit"],
           "YT": ["Whitehorse"]},
    "AU": {"NSW": ["Sydney"], "VIC": ["Melbourne"], "QLD": ["Brisbane"], "WA": ["Perth"], "SA": ["Adelaide"], "TAS": ["Hobart"], "ACT": ["Canberra"],
           "NT": ["Darwin"]},
}


def _inside(box: list[float], lat: float, lon: float) -> bool:
    return box[0] <= lat <= box[1] and box[2] <= lon <= box[3]


def test_every_box_holds_a_unique_library_city_of_its_own() -> None:
    checked, problems = 0, []
    for country, states in PROBES.items():
        assert set(states) == set(BOXES[country]), country
        for code, names in states.items():
            for name in names:
                rows = [r for r in FULL if r["r"] == country and name in (r.get("e"), r.get("n"))]
                if len(rows) == 1:
                    checked += 1
                    if not _inside(BOXES[country][code], rows[0]["y"], rows[0]["x"]):
                        problems.append((country, code, name, rows[0]["y"], rows[0]["x"]))
                    break
    assert problems == [] and checked >= 58, (problems, checked)


@requires_node
def test_state_qualifiers_narrow_and_labels_show_the_state(tmp_path: Path) -> None:
    from node_esm import run_node_esm

    script = """
const { decidePlace } = await import(process.argv[1]);
const { resolvePlaceOffline } = await import(process.argv[2]);
const out = {};
for (const q of ['Portland, OR', 'Portland, ME', 'Springfield, IL', 'Springfield, MO', 'Windsor, CA', 'Bath, England']) {
  const r = await decidePlace(q, { upstream: await resolvePlaceOffline(q, { limit: 10 }), limit: 10 });
  out[q] = { status: r.status, lat: r.match ? r.match.gpsLat : null, sub: r.match && r.match.subdivision ? r.match.subdivision.code : null };
}
console.log(JSON.stringify(out));
"""
    out = json.loads(run_node_esm(script, CORE / "src" / "tools" / "placeResolve.js", CORE / "src" / "vendor" / "place" / "place.js", cwd=CORE))
    assert out["Portland, OR"]["status"] == "resolved" and round(out["Portland, OR"]["lat"]) == 46
    assert out["Portland, ME"]["status"] == "resolved" and out["Portland, ME"]["sub"] == "ME"
    assert out["Springfield, IL"]["status"] == "resolved" and round(out["Springfield, IL"]["lat"]) == 40
    assert out["Springfield, MO"]["status"] == "resolved" and out["Springfield, MO"]["sub"] == "MO"
    assert out["Windsor, CA"]["status"] == "ambiguous"        # CA 也是加拿大的国家码：两边都留
    assert out["Bath, England"]["status"] == "confirm"        # 英国四部没有包围盒：照旧请确认


@requires_node
def test_long_addresses_fall_back_to_the_level_the_library_has() -> None:
    """审计 F18：身份证式地址、出生医院、机场、「附近」以前一律 not_found、零建议；截短后歧义的不替用户选。
    西贡等旧称进别名表：西贡既是香港西贡区也是胡志明市旧称 → 歧义请用户选。负向对照（实跑过）：decide 不走 addressFallback → 红。"""
    from node_esm import run_node_esm

    script = """
const { runPlaceSearch } = await import(process.argv[1]);
const out = {};
for (const q of ['广东省深圳市南山区粤海街道', '北京协和医院', '上海浦东机场', '北京附近', '南山区粤海街道', '西贡', 'Stalingrad', '中国', 'Japan']) {
  const v = (await runPlaceSearch({ query: q, date: '1990-05-03' })).data.verdict;
  out[q] = { status: v.status, name: v.match ? v.match.name : null, caveats: (v.caveats || []).map((c) => c.code), n: (v.candidates || []).length };
}
console.log(JSON.stringify(out));
"""
    out = json.loads(run_node_esm(script, CORE / "src" / "tools" / "placeSearch.js", cwd=CORE))
    assert {k: out["广东省深圳市南山区粤海街道"][k] for k in ("status", "name", "caveats")} == {"status": "resolved", "name": "南山区", "caveats": ["address_truncated"]}
    assert out["北京协和医院"]["name"] == "北京" and out["上海浦东机场"]["name"] == "浦东新区" and out["北京附近"]["name"] == "北京"
    assert out["南山区粤海街道"]["status"] == "not_found"
    assert out["西贡"]["status"] == "ambiguous" and out["Stalingrad"]["caveats"] == ["alias_historical"]
    # 审计 F32：只给国家时不列子串命中的「候选」（中国 → 西安、拉萨；Japan → Pajapan）
    assert out["中国"]["status"] == out["Japan"]["status"] == "too_broad" and out["中国"]["n"] == out["Japan"]["n"] == 0


@requires_node
def test_bare_name_takes_the_one_curated_city_and_says_so(tmp_path: Path) -> None:
    """待决项 5：光写 London → 伦敦（英国），披露；没有精选城市的同名（Dublin / Springfield）、同音的中国城市（Suzhou）、
    经旧称别名到达的（Canton）照旧问。负向对照（实跑过）：placeResolve.js 里 prominence 分支的条件改成 false → 红。"""
    from node_esm import run_node_esm

    script = """
const { decidePlace } = await import(process.argv[1]);
const out = {};
for (const q of ['London', 'Dublin', 'Springfield', 'Suzhou', 'Canton']) {
  const r = await decidePlace(q, { limit: 10 });
  out[q] = { status: r.status, by: r.matched_by || null, name: r.match ? r.match.name : null, caveats: (r.caveats || []).map((c) => c.code) };
}
console.log(JSON.stringify(out));
"""
    out = json.loads(run_node_esm(script, CORE / "src" / "tools" / "placeResolve.js", cwd=CORE))
    assert out["London"] == {"status": "resolved", "by": "prominence", "name": "伦敦", "caveats": ["prominence_default"]}
    assert {out[q]["status"] for q in ("Dublin", "Springfield", "Suzhou", "Canton")} == {"ambiguous"}
