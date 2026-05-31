// divination/data/dignities.js
// 必备尊贵：界(埃及界)、三分(Dorothean 昼/夜/共)、面(Chaldean decan)。
// 庙/旺/陷/弱 在 signs.js。后端 /chart 已给每星 obj.dignities，本表供 describe/timing/topic
// 对「任意点/界主星/三分主星」的查询（如 §4.4 失物材质=月亮所落界主星）。
import { SIGN_ORDER, signOfLon } from './signs.js';

// 埃及界（Egyptian terms / bounds）：每座 5 段 [planet, from, to]
export const EGYPTIAN_TERMS = {
	aries: [['jupiter', 0, 6], ['venus', 6, 12], ['mercury', 12, 20], ['mars', 20, 25], ['saturn', 25, 30]],
	taurus: [['venus', 0, 8], ['mercury', 8, 14], ['jupiter', 14, 22], ['saturn', 22, 27], ['mars', 27, 30]],
	gemini: [['mercury', 0, 6], ['jupiter', 6, 12], ['venus', 12, 17], ['mars', 17, 24], ['saturn', 24, 30]],
	cancer: [['mars', 0, 7], ['venus', 7, 13], ['mercury', 13, 19], ['jupiter', 19, 26], ['saturn', 26, 30]],
	leo: [['jupiter', 0, 6], ['venus', 6, 11], ['saturn', 11, 18], ['mercury', 18, 24], ['mars', 24, 30]],
	virgo: [['mercury', 0, 7], ['venus', 7, 17], ['jupiter', 17, 21], ['mars', 21, 28], ['saturn', 28, 30]],
	libra: [['saturn', 0, 6], ['mercury', 6, 14], ['jupiter', 14, 21], ['venus', 21, 28], ['mars', 28, 30]],
	scorpio: [['mars', 0, 7], ['venus', 7, 11], ['mercury', 11, 19], ['jupiter', 19, 24], ['saturn', 24, 30]],
	sagittarius: [['jupiter', 0, 12], ['venus', 12, 17], ['mercury', 17, 21], ['saturn', 21, 26], ['mars', 26, 30]],
	capricorn: [['mercury', 0, 7], ['jupiter', 7, 14], ['venus', 14, 22], ['saturn', 22, 26], ['mars', 26, 30]],
	aquarius: [['mercury', 0, 7], ['venus', 7, 13], ['jupiter', 13, 20], ['mars', 20, 25], ['saturn', 25, 30]],
	pisces: [['venus', 0, 12], ['jupiter', 12, 16], ['mercury', 16, 19], ['mars', 19, 28], ['saturn', 28, 30]],
};

// 三分性（Dorothean）：element → {day, night, participating}
export const TRIPLICITY = {
	fire: { day: 'sun', night: 'jupiter', participating: 'saturn' },
	earth: { day: 'venus', night: 'moon', participating: 'mars' },
	air: { day: 'saturn', night: 'mercury', participating: 'jupiter' },
	water: { day: 'venus', night: 'mars', participating: 'moon' },
};

// 面（Chaldean decans）：每座 3 个面，按迦勒底序，自白羊 0° 起火星
export const FACES = {
	aries: ['mars', 'sun', 'venus'],
	taurus: ['mercury', 'moon', 'saturn'],
	gemini: ['jupiter', 'mars', 'sun'],
	cancer: ['venus', 'mercury', 'moon'],
	leo: ['saturn', 'jupiter', 'mars'],
	virgo: ['sun', 'venus', 'mercury'],
	libra: ['moon', 'saturn', 'jupiter'],
	scorpio: ['mars', 'sun', 'venus'],
	sagittarius: ['mercury', 'moon', 'saturn'],
	capricorn: ['jupiter', 'mars', 'sun'],
	aquarius: ['venus', 'mercury', 'moon'],
	pisces: ['saturn', 'jupiter', 'mars'],
};

// 经度 → 界主星
export function termRulerAt(lon){
	const sign = signOfLon(lon);
	const deg = ((lon % 360) + 360) % 360 % 30;
	const terms = EGYPTIAN_TERMS[sign] || [];
	for(let i = 0; i < terms.length; i++){
		if(deg >= terms[i][1] && deg < terms[i][2]){
			return terms[i][0];
		}
	}
	return terms.length ? terms[terms.length - 1][0] : null;
}

// 经度 → 面/十分度（0/1/2）及其主星
export function faceAt(lon){
	const sign = signOfLon(lon);
	const deg = ((lon % 360) + 360) % 360 % 30;
	const idx = Math.min(2, Math.floor(deg / 10));
	return { faceIndex: idx, ruler: (FACES[sign] || [])[idx] || null };
}

// 三分主星（按昼夜取主用/次用/共用）
export function triplicityRulers(element){
	return TRIPLICITY[element] || null;
}

// 必备尊贵打分（庙+5/旺+4/三分+3/界+2/面+1/陷−5/落−4）。dignitiesAt 由 conditions.js 调用。
export const DIGNITY_SCORE = { domicile: 5, exaltation: 4, triplicity: 3, term: 2, face: 1, detriment: -5, fall: -4 };

export { SIGN_ORDER };
export default EGYPTIAN_TERMS;
