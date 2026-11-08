// AI 助手·离线地名解析:内置城市库(小库静态 + 大库懒加载 + 繁简折叠表)→ 候选/唯一解 + 时区。
// 全程不联网、不做 GCJ-02 转换(城市库即 WGS84;高德在线选点才需要 gcj02ToGps)。
import CITIES from './data/cities.json' with { type: 'json' };
import CITY_TRAD_SIMP from './data/cityTradSimpMap.json' with { type: 'json' };
import { searchCitiesScored, toCityItem } from './cityMatch.js';
import { geoPairToRecordFields } from './geoCompass.js';
import { resolveZone } from './zone.js';

let fullLib = null;
let fullLoading = null;
function loadFullLib(){
	if(fullLib){ return Promise.resolve(fullLib); }
	if(!fullLoading){
		fullLoading = import('./data/citiesFull.json', { with: { type: 'json' } })
			.then((m)=>{ fullLib = Array.isArray(m) ? m : (m && m.default) || []; return fullLib; })
			.catch(()=>{ fullLoading = null; return []; });   // 失败不缓存成「空库」:本次退小库,下次再试大库
	}
	return fullLoading;
}

// 同城在小库/大库各有条目(北京/Beijing/北京市…)——按坐标邻近(0.25°≈25km)合并为一处,
// 保留评分更优/更靠前(小库优先)的那条,否则「北京」会被判成三个候选的假歧义。
const NEAR_DEG = 0.25;
function distinctByName(hits){
	const kept = [];
	for(const h of hits){
		const la = Number(h.c._lat), lo = Number(h.c._lng);
		const dup = kept.some((k)=>Math.abs(Number(k.c._lat) - la) <= NEAR_DEG && Math.abs(Number(k.c._lng) - lo) <= NEAR_DEG && k.score <= h.score);
		if(!dup){ kept.push(h); }
	}
	return kept;
}

function toPlace(item, dateStr){
	const geo = geoPairToRecordFields(item.lat, item.lng);
	const z = resolveZone({ gpsLat: item.lat, gpsLon: item.lng, dateStr });
	return {
		name: item.name, en: item.en, region: item.region,
		gpsLat: geo.gpsLat, gpsLon: geo.gpsLon, lat: geo.lat, lon: geo.lon,
		zone: z.zone, zoneSource: z.source, iana: z.iana,
		...(z.advisory ? { advisory: z.advisory } : {}),
	};
}

// 返回 { resolved, confidence:'high'|'medium'|null, place?, candidates:[{name,en,region,gpsLat,gpsLon}], code? }
export async function resolvePlaceOffline(rawQuery, { dateStr, limit = 5 } = {}){
	const query = `${rawQuery || ''}`.trim();
	if(!query){
		return { resolved: false, confidence: null, candidates: [], code: 'E_PLACE_NOT_FOUND' };
	}
	const full = await loadFullLib();
	const lists = [CITIES, full];
	const cap = Math.max(1, Math.min(10, limit || 5));
	let hits = distinctByName(searchCitiesScored(query, lists, CITY_TRAD_SIMP, 40));
	let regionHint = '';
	if(!hits.length && query.length >= 3){
		// 「辽宁朝阳」式:尾段为城市、前段为地区提示
		for(let k = 2; k <= Math.min(4, query.length - 1) && !hits.length; k++){
			const tail = query.slice(query.length - k);
			const head = query.slice(0, query.length - k);
			const sub = distinctByName(searchCitiesScored(tail, lists, CITY_TRAD_SIMP, 40))
				.filter((h)=>h.c._region.indexOf(head) >= 0 || h.c._name.indexOf(head) >= 0 || h.c._en.indexOf(head.toLowerCase()) >= 0);
			if(sub.length){ hits = sub; regionHint = head; }
		}
	}
	if(!hits.length){
		return { resolved: false, confidence: null, candidates: [], code: 'E_PLACE_NOT_FOUND' };
	}
	const exact = hits.filter((h)=>h.score === 0);
	let picked = null;
	let confidence = null;
	if(exact.length === 1){
		picked = exact[0]; confidence = 'high';
	}else if(exact.length > 1){
		const byRegion = exact.filter((h)=>h.c._region && query.indexOf(h.c._region) >= 0);
		if(byRegion.length === 1){ picked = byRegion[0]; confidence = 'high'; }
		else if(regionHint){ picked = exact[0]; confidence = 'high'; }
	}else if(hits[0].score <= 2 && (hits.length === 1 || hits[1].score > hits[0].score)){
		picked = hits[0]; confidence = 'medium';
	}
	const candidates = hits.slice(0, cap).map((h)=>{
		const it = toCityItem(h.c);
		return { name: it.name, en: it.en, region: it.region, gpsLat: it.lat, gpsLon: it.lng };
	});
	if(!picked){
		return { resolved: false, confidence: null, candidates };
	}
	return { resolved: true, confidence, place: toPlace(toCityItem(picked.c), dateStr), candidates };
}
