// divination/horary/antisciaTable.js
// [H8 两套合一] 全盘映点/对映点表——此前 UI(HoraryJudgment)与快照(horarySnapshot)各写一份:
// UI 版吃 opts.antisciaOrb、快照版写死 ≤1° ——同盘两处命中集可不同。收编为单一实现,
// 两处 import,orb 同源 opts.antisciaOrb(缺省 1°=快照旧值,快照迁移零回归)。
import { PLANETS } from '../data/planets.js';
import { SIGNS, signOfLon } from '../data/signs.js';

export function buildAntisciaTable(facts, orb){
	const o = (typeof orb === 'number' && orb > 0) ? orb : 1;
	const keys = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
	const points = [];
	keys.forEach((k) => { if(facts.planets[k]) points.push({ label: (PLANETS[k] || {}).cn || k, lon: facts.planets[k].lon, key: k }); });
	if(facts.meta.ascLon != null) points.push({ label: '命度', lon: facts.meta.ascLon, key: 'asc' });
	if(facts.meta.mcLon != null) points.push({ label: '天顶', lon: facts.meta.mcLon, key: 'mc' });
	const cuspTargets = [];
	Object.keys(facts.houses || {}).forEach((h) => { const c = facts.houses[h]; if(c && c.lon != null) cuspTargets.push({ label: `${h}宫头`, lon: c.lon }); });
	const dist = (a, b) => { const d = Math.abs(((a - b) % 360 + 360) % 360); return Math.min(d, 360 - d); };
	const hitsOf = (lon, selfKey) => {
		const hits = [];
		points.forEach((p) => { if(p.key !== selfKey && dist(lon, p.lon) <= o) hits.push(p.label); });
		cuspTargets.forEach((c) => { if(dist(lon, c.lon) <= o) hits.push(c.label); });
		return hits;
	};
	return keys.filter((k) => facts.planets[k]).map((k) => {
		const lam = facts.planets[k].lon;
		const anti = ((180 - lam) % 360 + 360) % 360;
		const contra = ((360 - lam) % 360 + 360) % 360;
		const fmt = (l) => `${(SIGNS[signOfLon(l)] || {}).cn || ''} ${(((l % 30) + 30) % 30).toFixed(1)}°`;
		return {
			key: k, cn: (PLANETS[k] || {}).cn || k,
			anti, antiText: fmt(anti), antiHits: hitsOf(anti, k),
			contra, contraText: fmt(contra), contraHits: hitsOf(contra, k),
		};
	});
}

export default buildAntisciaTable;
