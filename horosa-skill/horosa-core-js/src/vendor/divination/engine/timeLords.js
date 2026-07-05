// 时主推运(time lords)纯函数:Profection 小限 / Firdaria 法达 / ZR(Zodiacal Releasing)L1。
// 传统时主推运术。择日与本命合参:当前年主星/运主星在事盘有力者尤佳。
// 范围口径:Firdaria 只到大运(子运不展开);ZR 只到 L1 大期(L2+ 不展开)——均在文案注明。
import { SIGNS, SIGN_ORDER } from '../data/signs.js';

// 'YYYY-MM-DD' → {y,m,d};失败 null
export function parseYmd(str){
	const m = /^\s*(-?\d{1,4})-(\d{1,2})-(\d{1,2})/.exec(String(str || ''));
	if(!m) return null;
	return { y: parseInt(m[1], 10), m: parseInt(m[2], 10), d: parseInt(m[3], 10) };
}

// 整数周岁(按公历生日是否已过)
export function ageAt(birthStr, onStr){
	const b = parseYmd(birthStr); const o = parseYmd(onStr);
	if(!b || !o) return null;
	let age = o.y - b.y;
	if(o.m < b.m || (o.m === b.m && o.d < b.d)) age -= 1;
	return age >= 0 ? age : null;
}

// Profection 小限:年宫 = (age mod 12)+1(自命宫顺数)
export function profectionHouse(age){
	return ((age % 12) + 12) % 12 + 1;
}

// Firdaria 75 年表:昼盘自太阳起,夜盘自月亮起(含二交点,合 75 年循环)
export const FIRDARIA_DAY = [
	['sun', 10], ['venus', 8], ['mercury', 13], ['moon', 9], ['saturn', 11],
	['jupiter', 12], ['mars', 7], ['north_node', 3], ['south_node', 2],
];
export const FIRDARIA_NIGHT = [
	['moon', 9], ['saturn', 11], ['jupiter', 12], ['mars', 7], ['north_node', 3],
	['south_node', 2], ['sun', 10], ['venus', 8], ['mercury', 13],
];

export function firdariaAt(age, isDiurnal){
	if(age === null || age === undefined || age < 0) return null;
	const seq = isDiurnal ? FIRDARIA_DAY : FIRDARIA_NIGHT;
	let t = age % 75;
	for(let i = 0; i < seq.length; i++){
		if(t < seq[i][1]){
			const from = age - t;
			return { lord: seq[i][0], years: seq[i][1], from, to: from + seq[i][1] };
		}
		t -= seq[i][1];
	}
	return null;
}

// ZR 小年表(黄道释放各座主星年数)
export const ZR_YEARS = {
	aries: 15, taurus: 8, gemini: 20, cancer: 25, leo: 19, virgo: 20,
	libra: 8, scorpio: 15, sagittarius: 12, capricorn: 27, aquarius: 30, pisces: 12,
};

// ZR L1:自幸运点星座起顺行连续期;返回 {sign, lord, from, to}
export function zrL1At(fortuneSign, age){
	if(!fortuneSign || !SIGNS[fortuneSign] || age === null || age === undefined || age < 0) return null;
	let idx = SIGN_ORDER.indexOf(fortuneSign);
	if(idx < 0) return null;
	let from = 0;
	for(let guard = 0; guard < 40; guard++){
		const sg = SIGN_ORDER[idx % 12];
		const span = ZR_YEARS[sg];
		if(age < from + span){
			return { sign: sg, lord: SIGNS[sg].domicile, from, to: from + span };
		}
		from += span;
		idx += 1;
	}
	return null;
}

export default { ageAt, profectionHouse, firdariaAt, zrL1At };
