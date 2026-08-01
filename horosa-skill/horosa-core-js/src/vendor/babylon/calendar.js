// divination/babylon/calendar.js —— 巴比伦阴阳历(算术复原)与 Uruk 分至/天狼星图式方案。
//
// 口径说明(显示层同步标注):
//  - 真实巴比伦历按新月牙首见定月始;本模块用「算术历」复原:以塞琉古纪元锚 + 平均朔望月递推,
//    与逐月实历可差 ±1–2 日(与楔文数理文类以 tithi 记日的口径一致)。
//  - 19 年 7 闰:周期第 3,6,8,11,14,17,19 年;第 17 年闰第二 Ulūlu(VI₂),余闰第二 Addaru(XII₂)。
//    (勿用希腊 Metonic 枚举 1,3,4,…——纪元约定不同。)
//  - 纪元:S.E.(塞琉古)= 前 311 春起算;Arsacid = S.E. − 64;19 年周期年 1 = S.E.1。
//  - 分至/天狼星按 Uruk 图式方案:夏至步进 12 月 + 11;3,10 tithi;三季各 +3 月 3 tithi;
//    天狼星偕日没 = 春分 + 1 月 18 tithi(= 偕日升 + 10 月 6 tithi)。锚取周期起点年的天文夏至
//    (低精度太阳公式,图式方案本身即拟合真实分至),UI 标「图式」。

import { MEAN_SYNODIC_MONTH, sexParse, norm360 } from './units.js';

export const MONTHS = [
	{ n: 1, akk: 'Nisannu', cune: 'BÁR', cn: '一月' },
	{ n: 2, akk: 'Ayyaru', cune: 'GU₄', cn: '二月' },
	{ n: 3, akk: 'Simanu', cune: 'SIG₄', cn: '三月' },
	{ n: 4, akk: 'Duʾūzu', cune: 'ŠU', cn: '四月' },
	{ n: 5, akk: 'Abu', cune: 'NE', cn: '五月' },
	{ n: 6, akk: 'Ulūlu', cune: 'KIN', cn: '六月' },
	{ n: 7, akk: 'Tašrītu', cune: 'DU₆', cn: '七月' },
	{ n: 8, akk: 'Araḫsamnu', cune: 'APIN', cn: '八月' },
	{ n: 9, akk: 'Kislīmu', cune: 'GAN', cn: '九月' },
	{ n: 10, akk: 'Ṭebētu', cune: 'AB', cn: '十月' },
	{ n: 11, akk: 'Šabaṭu', cune: 'ZÍZ', cn: '十一月' },
	{ n: 12, akk: 'Addaru', cune: 'ŠE', cn: '十二月' },
];

export const LEAP_YEARS_IN_CYCLE = [3, 6, 8, 11, 14, 17, 19];

// S.E. 年 → 19 年周期内年序(1–19;周期年 1 = S.E.1;对 0/负 S.E. 数学连续)
export function cycleYearOf(seYear){
	return ((((seYear - 1) % 19) + 19) % 19) + 1;
}
export function isLeapSeYear(seYear){
	return LEAP_YEARS_IN_CYCLE.indexOf(cycleYearOf(seYear)) >= 0;
}
// 闰月类型:'VI2'(第 17 年) | 'XII2'(其余闰年) | null
export function leapMonthType(seYear){
	if(!isLeapSeYear(seYear)){ return null; }
	return cycleYearOf(seYear) === 17 ? 'VI2' : 'XII2';
}

// 该 S.E. 年的月序列(对象 {n, akk, cune, leap})
export function monthsOfSeYear(seYear){
	const t = leapMonthType(seYear);
	const out = [];
	for(let i = 0; i < 12; i++){
		out.push({ ...MONTHS[i], leap: false });
		if(t === 'VI2' && MONTHS[i].n === 6){
			out.push({ n: 6.5, akk: 'Ulūlu II', cune: 'KIN.2.KAM', cn: '闰六月', leap: true });
		}
	}
	if(t === 'XII2'){
		out.push({ n: 12.5, akk: 'Addaru II', cune: 'ŠE.2.KAM', cn: '闰十二月', leap: true });
	}
	return out;
}

// ── 儒略历 ↔ JDN(支持负年/天文年号)────────────────────────────────
export function julianToJdn(year, month, day){
	// 儒略历(proleptic)→ JDN(正午起算的整数 JDN,取日为整)
	let a = Math.floor((14 - month) / 12);
	let y = year + 4800 - a;
	let m = month + 12 * a - 3;
	return day + Math.floor((153 * m + 2) / 5) + 365 * y + Math.floor(y / 4) - 32083;
}
export function jdnToJulian(jdn){
	let c = jdn + 32082;
	let d = Math.floor((4 * c + 3) / 1461);
	let e = c - Math.floor(1461 * d / 4);
	let m = Math.floor((5 * e + 2) / 153);
	const day = e - Math.floor((153 * m + 2) / 5) + 1;
	const month = m + 3 - 12 * Math.floor(m / 10);
	const year = d - 4800 + Math.floor(m / 10);
	return { year, month, day };
}

// JDN → proleptic 格里历(供后端星历请求的日期串;现代域与系统历一致)
export function jdnToGregorian(jdn){
	const a = jdn + 32044;
	const b = Math.floor((4 * a + 3) / 146097);
	const c = a - Math.floor(146097 * b / 4);
	const d = Math.floor((4 * c + 3) / 1461);
	const e = c - Math.floor(1461 * d / 4);
	const m = Math.floor((5 * e + 2) / 153);
	const day = e - Math.floor((153 * m + 2) / 5) + 1;
	const month = m + 3 - 12 * Math.floor(m / 10);
	const year = 100 * b + d - 4800 + Math.floor(m / 10);
	return { year, month, day };
}
export function jdnToDateStr(jdn){
	const g = jdnToGregorian(jdn);
	const p2 = (n) => (n < 10 ? '0' + n : '' + n);
	return `${g.year}/${p2(g.month)}/${p2(g.day)}`;
}

// 历法锚:S.E.1 Nisannu 1 = 儒略 前311 年 4 月 3 日(标准编年表口径)
export const SE1_NISANNU1_JDN = julianToJdn(-310, 4, 3);

// 自 S.E.1 Nisannu 起的「第 k 个朔望月」起始 JDN(算术历)
export function monthStartJdn(k){
	return Math.round(SE1_NISANNU1_JDN + k * MEAN_SYNODIC_MONTH);
}

// S.E. 年 y 的 Nisannu 之前累计月数(自 S.E.1 Nisannu 起)
export function monthsBeforeSeYear(seYear){
	let k = 0;
	if(seYear >= 1){
		for(let y = 1; y < seYear; y++){ k += isLeapSeYear(y) ? 13 : 12; }
	}else{
		for(let y = seYear; y < 1; y++){ k -= isLeapSeYear(y) ? 13 : 12; }
	}
	return k;
}

// (S.E.年, 月序idx[0基于该年月序列], 日1–30) → JDN
export function babylonianToJdn(seYear, monthIdx, day){
	const k = monthsBeforeSeYear(seYear) + monthIdx;
	return monthStartJdn(k) + (day - 1);
}

// JDN → 巴比伦历 {seYear, monthIdx, month(对象), day, cycleYear}
export function jdnToBabylonian(jdn){
	// 估算月号再局部校正
	let k = Math.floor((jdn - SE1_NISANNU1_JDN) / MEAN_SYNODIC_MONTH);
	while(monthStartJdn(k + 1) <= jdn){ k++; }
	while(monthStartJdn(k) > jdn){ k--; }
	// 月号 k → 年:先估年再校正
	let seYear = Math.floor(k / 12.368) + 1;
	while(monthsBeforeSeYear(seYear + 1) <= k){ seYear++; }
	while(monthsBeforeSeYear(seYear) > k){ seYear--; }
	const monthIdx = k - monthsBeforeSeYear(seYear);
	const months = monthsOfSeYear(seYear);
	const day = jdn - monthStartJdn(k) + 1;
	return {
		seYear,
		monthIdx,
		month: months[monthIdx] || MONTHS[0],
		day,
		cycleYear: cycleYearOf(seYear),
		monthLen: monthStartJdn(k + 1) - monthStartJdn(k),
	};
}

// 公历(格里/儒略混合之 JDN 由外部供给,如 utils/julianDayIndex)→ 此处仅做巴比伦侧。
export function arsacidOf(seYear){ return seYear - 64; }

export function formatBabylonianDate(bd){
	if(!bd){ return ''; }
	const m = bd.month || {};
	return `S.E.${bd.seYear} 年 ${m.akk || ''}(${m.cn || ''})${bd.day} 日`;
}

// ── 低精度太阳黄经与分至(锚定 Uruk 图式用;误差 ≲0.5°/半日,图式方案本身 ±1–2 日)──
export function solarLongitudeApprox(jd){
	const n = jd - 2451545.0;
	const L = 280.460 + 0.9856474 * n;
	const g = (357.528 + 0.9856003 * n) * Math.PI / 180;
	return norm360(L + 1.915 * Math.sin(g) + 0.020 * Math.sin(2 * g));
}
// 天文年 year 的分至 JD(which: 0 春分/90 夏至/180 秋分/270 冬至)
export function solsticeEquinoxJd(year, targetLon){
	// 粗定日期:春分~3/23,夏至~6/26,秋分~9/26,冬至~12/24(儒略历远古偏移由迭代吸收)
	let guess = julianToJdn(year, 1, 1) + 79 + targetLon / 360 * 365.25;
	for(let i = 0; i < 8; i++){
		const lon = solarLongitudeApprox(guess);
		let diff = ((targetLon - lon + 540) % 360) - 180;
		guess += diff / 0.9856;
		if(Math.abs(diff) < 0.001){ break; }
	}
	return guess;
}

// ── Uruk 分至/天狼星方案(图式)────────────────────────────────────────
// 以 tithi 当历日数(方案原生口径),锚 = 该 19 年周期起点年的天文夏至历日。
const SS_STEP_TITHI = sexParse('11;3,10');      // 相邻夏至:12 月 + 11;3,10 tithi
const SEASON_STEP_TITHI = 3;                    // 三季各 +3 月 3 tithi

function addSchematic(md, months, tithi){
	// {m(1基月号), t(日/tithi)} + 月数 + tithi;月内 30 tithi 进位
	let m = md.m - 1 + months;
	let t = md.t + tithi;
	while(t > 30){ t -= 30; m += 1; }
	while(t <= 0){ t += 30; m -= 1; }
	return { m: ((m % 12) + 12) % 12 + 1, t };
}

// 给定 S.E. 年,返回该年图式分至/天狼星历日(月号+tithi 日)
export function urukSchemeOf(seYear){
	const cy = cycleYearOf(seYear);
	// 周期起点年(cycle year 1)的天文夏至 → 巴比伦历日(锚)
	const cycleStartSe = seYear - (cy - 1);
	const astYearOfCycleStart = cycleStartSe - 311;      // S.E.1 = 天文年 −310
	const ssJd = solsticeEquinoxJd(astYearOfCycleStart, 90);
	const bd = jdnToBabylonian(Math.round(ssJd));
	let ss = { m: Math.floor(bd.month.n), t: bd.day };
	// 逐年步进 +12 月 + 11;3,10 tithi(12 月在 mod 12 下不动月号)
	for(let y = 1; y < cy; y++){ ss = addSchematic(ss, 0, SS_STEP_TITHI); }
	const ae = addSchematic(ss, 3, SEASON_STEP_TITHI);   // 秋分
	const ws = addSchematic(ae, 3, SEASON_STEP_TITHI);   // 冬至
	const ve = addSchematic(ws, 3, SEASON_STEP_TITHI);   // 次年春分(方案环)
	// 天狼星:偕日没 = 春分 + 1 月 18 tithi;偕日升 = 没 − 10 月 − 6 tithi
	const siriusSet = addSchematic(ve, 1, 18);
	const siriusRise = addSchematic(siriusSet, -10, -6);
	return {
		cycleYear: cy,
		summerSolstice: ss, autumnEquinox: ae, winterSolstice: ws, vernalEquinox: ve,
		siriusSet, siriusRise,
	};
}

export function formatSchematic(md){
	if(!md){ return ''; }
	const m = MONTHS[(md.m - 1) % 12] || {};
	return `${m.akk}(${m.cn})${Math.round(md.t)} 日`;
}
