// 时主推运(time lords)纯函数:Profection 小限(年/月/日) / Firdaria 法达(大运+子运,夜序两制) /
// ZR(Zodiacal Releasing)L1+L2(含解结与峰期)。传统时主推运术。
// 择日与本命合参:当前年主星/运主星在事盘有力者尤佳。
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

// ── R2 扩展:月限/日限、法达子期与夜序两制、ZR L2+解结+峰期、回归常数 ─────────────

// 公历 → JDN(整数;现代日期域;不走 Date.UTC 以避 proleptic 口径坑)
export function gregorianJdn(y, m, d){
	const a = Math.floor((14 - m) / 12);
	const yy = y + 4800 - a;
	const mm = m + 12 * a - 3;
	return d + Math.floor((153 * mm + 2) / 5) + 365 * yy + Math.floor(yy / 4) - Math.floor(yy / 100) + Math.floor(yy / 400) - 32045;
}
export function jdnOfYmd(str){
	const p = parseYmd(str);
	return p ? gregorianJdn(p.y, p.m, p.d) : null;
}
// 分数年龄(回归年 365.2425);无效/倒挂返回 null
export function fractionalAge(birthStr, onStr){
	const a = jdnOfYmd(birthStr); const b = jdnOfYmd(onStr);
	if(a === null || b === null || b < a) return null;
	return (b - a) / 365.2425;
}

// 月限/日限:自年限宫起每月(≈30.44日)进一宫;日限≈2.5日/宫(月限宫内细分)。
// 返回 {annual, monthly, daily, monthsSinceBirthday};无效返回 null。
export function profectionMD(birthStr, onStr){
	const b = parseYmd(birthStr); const o = parseYmd(onStr);
	const age = ageAt(birthStr, onStr);
	if(!b || !o || age === null) return null;
	const annual = profectionHouse(age);
	// 最近一次生日(年限起点)
	let by = o.y;
	if(o.m < b.m || (o.m === b.m && o.d < b.d)) by -= 1;
	const days = jdnOfYmd(onStr) - gregorianJdn(by, b.m, Math.min(b.d, 28));
	if(days === null || days < 0) return null;
	const months = Math.max(0, Math.min(11, Math.floor(days / 30.4375)));
	const monthly = ((annual - 1 + months) % 12) + 1;
	const daysIntoMonth = days - months * 30.4375;
	const daily = ((monthly - 1 + Math.max(0, Math.floor(daysIntoMonth / 2.5))) % 12) + 1;
	return { annual, monthly, daily, monthsSinceBirthday: months };
}

// 法达夜序两制:现行表 FIRDARIA_NIGHT=交点承火星之后;另一制=二交点缀于七曜之末。
export const FIRDARIA_NIGHT_NODES_END = [
	['moon', 9], ['saturn', 11], ['jupiter', 12], ['mars', 7], ['sun', 10],
	['venus', 8], ['mercury', 13], ['north_node', 3], ['south_node', 2],
];
// 子期环=迦勒底降序(自日起表即是):主期均分七段,自主期主星起循环;交点期不分子期。
const FIRDARIA_SUB_RING = ['sun', 'venus', 'mercury', 'moon', 'saturn', 'jupiter', 'mars'];
export function firdariaSubAt(ageF, isDiurnal, nightOrder){
	if(ageF === null || ageF === undefined || ageF < 0) return null;
	const seq = isDiurnal ? FIRDARIA_DAY : (nightOrder === 'nodes_end' ? FIRDARIA_NIGHT_NODES_END : FIRDARIA_NIGHT);
	let t = ageF % 75;
	let from = ageF - t;
	for(let i = 0; i < seq.length; i++){
		if(t < seq[i][1]){
			const major = { lord: seq[i][0], years: seq[i][1], from, to: from + seq[i][1] };
			if(major.lord === 'north_node' || major.lord === 'south_node'){
				return { major, sub: null };   // 交点期不分子期(通行)
			}
			const subLen = major.years / 7;
			const idx = Math.max(0, Math.min(6, Math.floor((ageF - from) / subLen)));
			const start = FIRDARIA_SUB_RING.indexOf(major.lord);
			return {
				major,
				sub: {
					lord: FIRDARIA_SUB_RING[(start + idx) % 7], idx: idx + 1, years: subLen,
					from: from + idx * subLen, to: from + (idx + 1) * subLen,
				},
			};
		}
		t -= seq[i][1];
		from += seq[i][1];
	}
	return null;
}

// ZR:L1(分数年)+L2(月;各座年数改读为月)+解结(某级跑满一周回起座→跳对座)+峰期
// (释放所至之座为「点」之角座——本座或其 4/7/10 座;lotSign 即点之座)。
export function zrL1AtF(lotSign, ageF){
	if(!lotSign || !SIGNS[lotSign] || ageF === null || ageF === undefined || ageF < 0) return null;
	let idx = SIGN_ORDER.indexOf(lotSign);
	if(idx < 0) return null;
	let from = 0;
	for(let guard = 0; guard < 40; guard++){
		const sg = SIGN_ORDER[idx % 12];
		const span = ZR_YEARS[sg];
		if(ageF < from + span){ return { sign: sg, lord: SIGNS[sg].domicile, from, to: from + span }; }
		from += span;
		idx += 1;
	}
	return null;
}
export function zrL2At(lotSign, ageF){
	const l1 = zrL1AtF(lotSign, ageF);
	if(!l1) return null;
	const startIdx = SIGN_ORDER.indexOf(l1.sign);
	const monthsInto = (ageF - l1.from) * 12;
	let cur = startIdx;
	let acc = 0;
	let loosedBond = false;
	let steps = 0;
	for(let guard = 0; guard < 60; guard++){
		const sg = SIGN_ORDER[cur % 12];
		const span = ZR_YEARS[sg];   // 月
		if(monthsInto < acc + span){
			const lotIdx = SIGN_ORDER.indexOf(lotSign);
			const offL2 = ((cur % 12) - lotIdx + 12) % 12;
			const offL1 = (startIdx - lotIdx + 12) % 12;
			return {
				l1,
				l2: { sign: sg, lord: SIGNS[sg].domicile, fromMonths: acc, toMonths: acc + span },
				loosedBond,
				l1Peak: offL1 % 3 === 0,
				l2Peak: offL2 % 3 === 0,
			};
		}
		acc += span;
		steps += 1;
		let next = (cur + 1) % 12;
		if(steps >= 12 && next === startIdx){
			// 解结:跑满一周将回起座 → 跳至对座续行
			next = (startIdx + 6) % 12;
			loosedBond = true;
			steps = 0;
		}
		cur = next;
	}
	return null;
}

// 回归周期常数(择日合参用):日返≈365.25 日;月返=27.3 恒星月(还度),勿与 29.5 朔望月混。
export const SOLAR_RETURN_DAYS = 365.25;
export const LUNAR_RETURN_DAYS = 27.321661;

export default { ageAt, profectionHouse, firdariaAt, zrL1At, profectionMD, firdariaSubAt, zrL2At };
