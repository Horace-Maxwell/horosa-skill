// divination/engine/chartFacts.js
// 把 /chart 的 Result 规整成干净的 facts 对象，供卜卦/择日引擎使用。
// 后端已给：isDiurnal(宗派)、timerStar/dayerStar(时主/日主)、movedir(逆行)、lonspeed(速度)、
// aboveHorizon、isVOC、isPeregrining、dignities/selfDignity、antisciaPoint、aspects/receptions/mutuals/surround、nongli。
// 仅需前端派生：燃烧(与日距)、角续果(由 house 号)、月相盈亏(日月黄经差)。
import { angularityOf } from '../data/houseMeanings.js';
import { signOfLon } from '../data/signs.js';
import { norm360, angularDist, signedDelta, houseNumFromId, keyOfChartId, scoreSelfDignity } from './utils.js';

const COMBUST_CAZIMI = 17 / 60;   // 17′（1647 口径;16′含黄纬为中世纪档,1°为早期档——经 opts 可配）
const COMBUST_LIMIT = 8.5;        // 燃烧 8°30′（~8° 为中世纪档）
const UNDER_BEAMS_LIMIT = 17;     // 日光束下 17°（15° 为较古档）

function combustionState(planetLon, sunLon, orbs, mitigateSameSign){
	if(sunLon === null || sunLon === undefined || planetLon === null || planetLon === undefined) return null;
	const cz = (orbs && orbs.cazimiOrb > 0) ? orbs.cazimiOrb : COMBUST_CAZIMI;
	const cb = (orbs && orbs.combustOrb > 0) ? orbs.combustOrb : COMBUST_LIMIT;
	const ub = (orbs && orbs.underBeamsOrb > 0) ? orbs.underBeamsOrb : UNDER_BEAMS_LIMIT;
	const d = angularDist(planetLon, sunLon);
	// 燃烧限同座(combustMitigateSameSign,1647 主流口径;2026-08 死开关审计接线——此前 spec
	// default true 但从未实现):cazimi/combust 须与太阳同座,异座近日降级为日光束下
	// (under_beams 17° 本就不限座)。门=显式 true 才限:不传 opts 的调用方(世俗/寿限/返照)
	// 保持纯角距旧行为字节不变;卜卦/择日经 horaryJudgeOpts 携 spec 默认 true 生效。
	const sameSign = mitigateSameSign === true ? signOfLon(planetLon) === signOfLon(sunLon) : true;
	if(d <= cz) return sameSign ? 'cazimi' : (d < ub ? 'under_beams' : null);
	if(d < cb) return sameSign ? 'combust' : (d < ub ? 'under_beams' : null);
	if(d < ub) return 'under_beams';
	return null;
}

// oriental(东出/晨升)= 行星黄经在太阳之「后」(rises before sun) ; occidental(西入/夜落)= 在太阳之「前」
function orientalityOf(planetLon, sunLon){
	if(sunLon === null || planetLon === null) return null;
	const d = signedDelta(sunLon, planetLon); // planet − sun ∈ (−180,180]
	if(Math.abs(d) < 0.0001) return null;
	return d < 0 ? 'oriental' : 'occidental';
}

function moonPhase(moonLon, sunLon){
	if(moonLon === null || sunLon === null) return null;
	const elong = norm360(moonLon - sunLon); // 0..360
	const phase = elong < 180 ? 'waxing' : 'waning';
	const nearNew = elong < 12 || elong > 348;
	const nearFull = Math.abs(elong - 180) < 12;
	return { phase, elongation: elong, nearNew, nearFull };
}

function getObj(result, chartId){
	if(result.objectMap && result.objectMap[chartId]) return result.objectMap[chartId];
	const objs = (result.chart && result.chart.objects) || [];
	return objs.find((o) => o.id === chartId) || null;
}

const PLANET_CHART_IDS = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'North Node', 'South Node', 'Pars Fortuna'];

// opts（可选;不传=既有行为字节不变）：cazimiOrb/combustOrb/underBeamsOrb —— 太阳三态阈值（度）。
export function buildFacts(result, opts){
	if(!result || !result.chart) return null;
	const solarOrbs = opts && (opts.cazimiOrb || opts.combustOrb || opts.underBeamsOrb)
		? { cazimiOrb: opts.cazimiOrb, combustOrb: opts.combustOrb, underBeamsOrb: opts.underBeamsOrb } : null;
	const combustSameSignGate = !!(opts && opts.combustMitigateSameSign === true);
	const chart = result.chart;
	const sun = getObj(result, 'Sun');
	const moon = getObj(result, 'Moon');
	const sunLon = sun ? sun.lon : null;

	const planets = {};
	PLANET_CHART_IDS.forEach((cid) => {
		const o = getObj(result, cid);
		if(!o) return;
		const key = keyOfChartId(cid);
		const h = houseNumFromId(o.house);
		planets[key] = {
			key, chartId: cid,
			lon: o.lon, sign: o.sign ? String(o.sign).toLowerCase() : signOfLon(o.lon), signlon: o.signlon,
			house: h, angularity: h ? angularityOf(h) : null,
			retro: o.movedir === 'Retrograde', speed: o.lonspeed,
			aboveHorizon: !!o.aboveHorizon,
			peregrine: !!o.isPeregrining,
			isVOC: !!o.isVOC,
			selfDignity: o.selfDignity || [],
			dignities: o.dignities || {},
			dignityScore: scoreSelfDignity(o.selfDignity),
			antiscion: o.antisciaPoint || null,
			combustion: cid === 'Sun' ? null : combustionState(o.lon, sunLon, solarOrbs, combustSameSignGate),
			orientality: cid === 'Sun' ? null : orientalityOf(o.lon, sunLon),
			hayyiz: o.hayyiz,
			outOfBounds: !!o.outOfBounds,
			oobDelta: o.oobDelta != null ? o.oobDelta : null,
			phase: o.phase || null,
			phasisEvent: o.phasisEvent || null,
			joy: !!o.joy,
			ofSect: o.ofSect !== undefined ? !!o.ofSect : null,
			mansion: o.mansion || null,
			degreeGender: o.degreeGender || null,
			feral: !!o.feral,
			monomoiria: o.monomoiria || null,
			ninthPart: o.ninthPart || null,
			darijan: o.darijan || null,
			// [H4a 金矿纯增] 后端早已落盘、前端此前零消费的六字段(本包只映射零消费=零行为;
			// 消费面 H4b 按流派门控接入):stationState 留驻带('S'留/'D'回顺等)/decl 赤纬
			// (declParallel 平行相位料)/ruleHouses 统辖宫/degreeQuality 度性(光明暗黑烟雾亏空)/
			// specialDegree 特殊度/backendDignityScore 后端综合分。
			stationState: o.stationState || null,
			decl: o.decl != null ? o.decl : null,
			ruleHouses: o.ruleHouses || null,
			degreeQuality: o.degreeQuality || null,
			specialDegree: o.specialDegree || null,
			backendDignityScore: o.score != null ? o.score : null,
		};
	});

	const asc = getObj(result, 'Asc');
	const mc = getObj(result, 'MC');
	const desc = getObj(result, 'Desc');
	const ic = getObj(result, 'IC');

	// 宫位表（houseMap: 'House1'→{sign,lon,ruler,planets[]}）。
	// ⚠️ result.houseMap 是盘面组件(AstroHelper)渲染时的懒建缓存,不是后端字段——
	// 本命合参/AI 挂载再生等「裸 Result」路径没有它 → 缺失时按同法自 chart.houses 自建
	// (本地对象,不回写 result),否则宫主类判断(小限年主/宫主受克等)会静默落空。
	const houses = {};
	let hmap = result.houseMap;
	if(!hmap || !Object.keys(hmap).length){
		hmap = {};
		((result.chart && result.chart.houses) || []).forEach((h) => { if(h && h.id){ hmap[h.id] = h; } });
	}
	for(let i = 1; i <= 12; i++){
		const h = hmap['House' + i];
		if(h){
			houses[i] = {
				sign: h.sign ? String(h.sign).toLowerCase() : (h.lon !== undefined ? signOfLon(h.lon) : null),
				lon: h.lon,
				ruler: h.ruler ? keyOfChartId(h.ruler) : null,
				planets: (h.planets || []).map((p) => keyOfChartId(p)),
			};
		}
	}

	const lons = {};
	Object.keys(planets).forEach((k) => { lons[k] = planets[k].lon; });
	if(asc){ lons.asc = asc.lon; }
	if(mc){ lons.mc = mc.lon; }
	if(desc){ lons.desc = desc.lon; }
	if(ic){ lons.ic = ic.lon; }
	if(houses[8]){ lons.eighth = houses[8].lon; }

	return {
		opts: opts || null,   // [R5-P2] 判读口径随 facts 携带(择日 antiscia 门等模块级门读 facts.opts;不传=null 门恒开=零回归)
		meta: {
			isDiurnal: !!chart.isDiurnal,
			sect: chart.isDiurnal ? 'day' : 'night',
			hourRuler: chart.timerStar ? keyOfChartId(chart.timerStar) : null,
			dayRuler: chart.dayerStar ? keyOfChartId(chart.dayerStar) : null,
			ascLon: asc ? asc.lon : (houses[1] ? houses[1].lon : null),
			ascSign: asc ? String(asc.sign).toLowerCase() : (houses[1] ? houses[1].sign : null),
			ascDegree: asc ? asc.signlon : null,
			mcLon: mc ? mc.lon : null,
			moonPhase: moonPhase(moon ? moon.lon : null, sunLon),
			nongli: chart.nongli || null,
			dayOfWeek: chart.dayofweek,
		},
		planets,
		houses,
		lons,
		result, // 保留原始引用：aspects / receptions / mutuals / surround / antiscias 等
	};
}

export default buildFacts;
