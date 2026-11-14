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
