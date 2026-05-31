// divination/engine/chartFacts.js
// 把 /chart 的 Result 规整成干净的 facts 对象，供卜卦/择日引擎使用。
// 后端已给：isDiurnal(宗派)、timerStar/dayerStar(时主/日主)、movedir(逆行)、lonspeed(速度)、
// aboveHorizon、isVOC、isPeregrining、dignities/selfDignity、antisciaPoint、aspects/receptions/mutuals/surround、nongli。
// 仅需前端派生：燃烧(与日距)、角续果(由 house 号)、月相盈亏(日月黄经差)。
import { angularityOf } from '../data/houseMeanings.js';
import { signOfLon } from '../data/signs.js';
import { norm360, angularDist, signedDelta, houseNumFromId, keyOfChartId, scoreSelfDignity } from './utils.js';

const COMBUST_CAZIMI = 17 / 60;   // 17′
const COMBUST_LIMIT = 8.5;        // 燃烧
const UNDER_BEAMS_LIMIT = 17;     // 日光束下

function combustionState(planetLon, sunLon){
	if(sunLon === null || sunLon === undefined || planetLon === null || planetLon === undefined) return null;
	const d = angularDist(planetLon, sunLon);
	if(d <= COMBUST_CAZIMI) return 'cazimi';
	if(d < COMBUST_LIMIT) return 'combust';
	if(d < UNDER_BEAMS_LIMIT) return 'under_beams';
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

export function buildFacts(result){
	if(!result || !result.chart) return null;
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
			combustion: cid === 'Sun' ? null : combustionState(o.lon, sunLon),
			orientality: cid === 'Sun' ? null : orientalityOf(o.lon, sunLon),
			hayyiz: o.hayyiz,
		};
	});

	const asc = getObj(result, 'Asc');
	const mc = getObj(result, 'MC');
	const desc = getObj(result, 'Desc');
	const ic = getObj(result, 'IC');

	// 宫位表（houseMap: 'House1'→{sign,lon,ruler,planets[]}）
	const houses = {};
	const hmap = result.houseMap || {};
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
