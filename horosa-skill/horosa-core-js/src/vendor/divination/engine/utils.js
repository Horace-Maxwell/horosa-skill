// divination/engine/utils.js
// 几何/工具函数（卜卦+择日共用）。

export function norm360(x){ return ((x % 360) + 360) % 360; }

// 两黄经最小夹角 0–180
export function angularDist(a, b){
	const d = Math.abs(norm360(a) - norm360(b));
	return Math.min(d, 360 - d);
}

// 有符号差 b−a，归一到 (−180,180]
export function signedDelta(a, b){
	let d = norm360(b) - norm360(a);
	if(d > 180) d -= 360;
	if(d <= -180) d += 360;
	return d;
}

export function signIndexOfLon(lon){ return Math.floor(norm360(lon) / 30); }
export function degInSign(lon){ return norm360(lon) % 30; }

// 'House7' → 7
export function houseNumFromId(id){
	const m = /House\s*(\d+)/i.exec(String(id || ''));
	return m ? parseInt(m[1], 10) : null;
}

// Sahl 奇偶计数：从 a 所在座到 b 所在座的星座数（含两端，1–12）。偶/奇 用于件数/军队大小。
export function signsBetween(aLon, bLon){
	const ai = signIndexOfLon(aLon);
	const bi = signIndexOfLon(bLon);
	const diff = ((bi - ai) % 12 + 12) % 12;
	return diff + 1;
}

export function isEven(n){ return n % 2 === 0; }

// 行星 chartId(PascalCase, 含空格) ↔ 数据层 key(lowercase)
export const CHART_ID_TO_KEY = {
	Sun: 'sun', Moon: 'moon', Mercury: 'mercury', Venus: 'venus', Mars: 'mars',
	Jupiter: 'jupiter', Saturn: 'saturn', Uranus: 'uranus', Neptune: 'neptune', Pluto: 'pluto',
	'North Node': 'north_node', 'South Node': 'south_node', 'Pars Fortuna': 'fortune',
};
export const KEY_TO_CHART_ID = Object.keys(CHART_ID_TO_KEY).reduce((m, k) => { m[CHART_ID_TO_KEY[k]] = k; return m; }, {});

export function keyOfChartId(id){ return CHART_ID_TO_KEY[id] || (id ? String(id).toLowerCase() : null); }
export function chartIdOfKey(key){ return KEY_TO_CHART_ID[key] || null; }

// 尊贵 token 打分（selfDignity 数组求和）。exile=detriment。
const DIGNITY_TOKEN_SCORE = {
	ruler: 5, exalt: 4, dayTrip: 3, nightTrip: 3, partTrip: 3, term: 2, face: 1, exile: -5, fall: -4,
};
export function scoreSelfDignity(selfDignity){
	if(!Array.isArray(selfDignity)) return 0;
	return selfDignity.reduce((s, t) => s + (DIGNITY_TOKEN_SCORE[t] || 0), 0);
}
export function dignityTokenScore(token){ return DIGNITY_TOKEN_SCORE[token] || 0; }
