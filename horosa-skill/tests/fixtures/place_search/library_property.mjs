// Whole-library property of the skill's place acceptance rule (tests/test_place_acceptance.py runs this):
// every library entry, queried by its own name plus its own region qualifier ("朝阳区, 北京城区", "Paris, US",
// "广州, 中国·广东"), must come back as itself — resolved to that entry (or a row within 0.25° of it, the same
// proximity merge upstream uses), or ambiguous with itself among the candidates when the library holds a namesake
// in the same region. It must never resolve to a different place. Provinces (广东省…) are "too broad" by design.
//
//   node tests/fixtures/place_search/library_property.mjs <horosa-core-js root>
// Prints one JSON object: counts per outcome + the first offenders.
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const root = process.argv[2];
const { decidePlace, placeIndex } = await import(pathToFileURL(path.join(root, 'src/tools/placeResolve.js')).href);
const ix = await placeIndex();
const NEAR = 0.25;
const counts = { resolved_self: 0, ambiguous_with_self: 0, too_broad_province: 0 };
const offenders = [];
const near = (a, b) => Math.abs(a.gpsLat - b.lat) <= NEAR && Math.abs(a.gpsLon - b.lng) <= NEAR;
const t0 = Date.now();
for (const e of ix.entries) {
	const query = `${e.name}, ${e.region}`;
	const v = await decidePlace(query, { allCandidates: true });
	if (v.status === 'resolved' && v.match && near(v.match, e)) { counts.resolved_self++; continue; }
	if (v.status === 'ambiguous' && (v.candidates || []).some((c) => near(c, e))) { counts.ambiguous_with_self++; continue; }
	if (v.status === 'too_broad' && e.admin && e.depth === 1 && /(省|自治区)$/.test(e.name)) { counts.too_broad_province++; continue; }
	if (offenders.length < 40) offenders.push({ query, status: v.status, got: v.match ? `${v.match.name}|${v.match.region}` : (v.candidates || []).slice(0, 3).map((c) => `${c.name}|${c.region}`) });
	counts.offenders = (counts.offenders || 0) + 1;
}
console.log(JSON.stringify({ entries: ix.entries.length, counts, offenders, alias_problems: ix.aliasProblems, ms: Date.now() - t0 }));
