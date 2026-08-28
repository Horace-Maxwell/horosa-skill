// divination/data/dignities.js
// 必备尊贵：界(埃及界)、三分(Dorothean 昼/夜/共)、面(Chaldean decan)。
// 庙/旺/陷/弱 在 signs.js。后端 /chart 已给每星 obj.dignities，本表供 describe/timing/topic
// 对「任意点/界主星/三分主星」的查询（如 §4.4 失物材质=月亮所落界主星）。
import { SIGN_ORDER, signOfLon } from './signs.js';
import * as __req0 from '../../utils/customCalibreStores.js';

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

// 界（托勒密界·经典传本 / Ptolemaic terms, textus receptus 1647）：每座 5 段 [planet, from, to]。
// 与埃及界并列为古典两大界系；世运盘「托勒密古典」可选切换此表（默认仍埃及界，零回归）。
// 与 constants/AstroConst.LILLY_TERMS、后端 flatlib LILLY_TERMS 三方同源镜像（termsVariant=2），
// 逐格锁于 __tests__/termsTablesDoc.test.js；勿单独改本表——三处必须 lockstep。
// 【2026-07-23 勘误】双鱼界4/5 曾误录 ♂20–26/♄26–30（仅 Paraphrase 手稿次选项）；经 Tetrabiblos I.21
// 原典+传承专论终校，经典传本/批判本/Hephaestio 三谱系一致为 ♂20–25/♄25–30，已改正并与另两处对齐。
export const PTOLEMAIC_TERMS = {
	aries: [['jupiter', 0, 6], ['venus', 6, 14], ['mercury', 14, 21], ['mars', 21, 26], ['saturn', 26, 30]],
	taurus: [['venus', 0, 8], ['mercury', 8, 15], ['jupiter', 15, 22], ['saturn', 22, 26], ['mars', 26, 30]],
	gemini: [['mercury', 0, 7], ['jupiter', 7, 14], ['venus', 14, 21], ['saturn', 21, 25], ['mars', 25, 30]],
	cancer: [['mars', 0, 6], ['jupiter', 6, 13], ['mercury', 13, 20], ['venus', 20, 27], ['saturn', 27, 30]],
	leo: [['saturn', 0, 6], ['mercury', 6, 13], ['venus', 13, 19], ['jupiter', 19, 25], ['mars', 25, 30]],
	virgo: [['mercury', 0, 7], ['venus', 7, 13], ['jupiter', 13, 18], ['saturn', 18, 24], ['mars', 24, 30]],
	libra: [['saturn', 0, 6], ['venus', 6, 11], ['jupiter', 11, 19], ['mercury', 19, 24], ['mars', 24, 30]],
	scorpio: [['mars', 0, 6], ['jupiter', 6, 14], ['venus', 14, 21], ['mercury', 21, 27], ['saturn', 27, 30]],
	sagittarius: [['jupiter', 0, 8], ['venus', 8, 14], ['mercury', 14, 19], ['saturn', 19, 25], ['mars', 25, 30]],
	capricorn: [['venus', 0, 6], ['mercury', 6, 12], ['jupiter', 12, 19], ['mars', 19, 25], ['saturn', 25, 30]],
	aquarius: [['saturn', 0, 6], ['mercury', 6, 12], ['venus', 12, 20], ['jupiter', 20, 25], ['mars', 25, 30]],
	pisces: [['venus', 0, 8], ['jupiter', 8, 14], ['mercury', 14, 20], ['mars', 20, 25], ['saturn', 25, 30]],
};

// 界（托勒密界·校勘本 / Tetrabiblos 批判本）：termsVariant=1 的判读侧镜像
// （=AstroConst.TETRABIBLOS_TERMS/后端 flatlib TETRABIBLOS_TERMS，三方 lockstep）。
// 与经典传本的分歧全部出自抄本传承（双子 7/13/20/26、天秤 ☿11–16/♃16–24、狮子 ☿先♀后、
// 金牛 ♄22–24、摩羯 ♄19–25 等），供「校勘本」口径下的界主/almuten 查询。
export const TETRABIBLOS_TERMS = {
	aries: [['jupiter', 0, 6], ['venus', 6, 14], ['mercury', 14, 21], ['mars', 21, 26], ['saturn', 26, 30]],
	taurus: [['venus', 0, 8], ['mercury', 8, 15], ['jupiter', 15, 22], ['saturn', 22, 24], ['mars', 24, 30]],
	gemini: [['mercury', 0, 7], ['jupiter', 7, 13], ['venus', 13, 20], ['mars', 20, 26], ['saturn', 26, 30]],
	cancer: [['mars', 0, 6], ['jupiter', 6, 13], ['mercury', 13, 20], ['venus', 20, 27], ['saturn', 27, 30]],
	leo: [['jupiter', 0, 6], ['mercury', 6, 13], ['saturn', 13, 19], ['venus', 19, 25], ['mars', 25, 30]],
	virgo: [['mercury', 0, 7], ['venus', 7, 13], ['jupiter', 13, 18], ['saturn', 18, 24], ['mars', 24, 30]],
	libra: [['saturn', 0, 6], ['venus', 6, 11], ['mercury', 11, 16], ['jupiter', 16, 24], ['mars', 24, 30]],
	scorpio: [['mars', 0, 6], ['venus', 6, 13], ['jupiter', 13, 21], ['mercury', 21, 27], ['saturn', 27, 30]],
	sagittarius: [['jupiter', 0, 8], ['venus', 8, 14], ['mercury', 14, 19], ['saturn', 19, 25], ['mars', 25, 30]],
	capricorn: [['venus', 0, 6], ['mercury', 6, 12], ['jupiter', 12, 19], ['saturn', 19, 25], ['mars', 25, 30]],
	aquarius: [['saturn', 0, 6], ['mercury', 6, 12], ['venus', 12, 20], ['jupiter', 20, 25], ['mars', 25, 30]],
	pisces: [['venus', 0, 8], ['jupiter', 8, 14], ['mercury', 14, 20], ['mars', 20, 25], ['saturn', 25, 30]],
};

// 经典传本·双子界4/5 的「校勘对调」口径（原书 ♄21–25/♂25–30 → 校勘 ♂21–25/♄25–30）。
// 仅这一行不同；由 gemini_terms_variant='emended' 时替换（默认 'received'=忠原书，零回归）。
export const PTOLEMAIC_GEMINI_EMENDED_ROW = [['mercury', 0, 7], ['jupiter', 7, 14], ['venus', 14, 21], ['mars', 21, 25], ['saturn', 25, 30]];

// 三分性（托勒密 / Ptolemaic）：托勒密水象昼夜均火星主、不另设共用主星（与多罗修斯有别）。
// 世运盘可选切换此表（默认仍多罗修斯，零回归）。
export const PTOLEMAIC_TRIPLICITY = {
	fire: { day: 'sun', night: 'jupiter', participating: null },
	earth: { day: 'venus', night: 'moon', participating: null },
	air: { day: 'saturn', night: 'mercury', participating: null },
	water: { day: 'mars', night: 'mars', participating: null },
};

// 界系表选择：'ptolemaic'=托勒密界·经典传本；'tetrabiblos'=托勒密界·校勘本；
// 其它/缺省 → 埃及界（默认，零回归）。迦勒底界（termsVariant=3）为昼夜双表、按 sect 取用，
// 由 hellenisticData.CHALDEAN_TERMS_DAY/NIGHT 提供（键为英文首字母大写座名），本模块不重复建表。
function termsTableFor(variant, opts){
	if(variant === 'ptolemaic') return PTOLEMAIC_TERMS;
	if(variant === 'tetrabiblos') return TETRABIBLOS_TERMS;
	// [F5] custom=自定义界表(昼表;判读引擎无昼夜上下文,取昼表与后端主口径一致);无合法表回落埃及。
	// [R2-3] opts.customTermsDay=随盘/回显表体优先,与计算同表。
	if(variant === 'custom'){
		try{
			// [R4-P2] 昼夜从 opts 读(缺省 true=昼表,与既往行为同);夜盘配独立夜表时与后端同表。
			const t = __req0.customTermsDisplayTables(
				!(opts && opts.isDiurnal === false), opts && opts.customTermsDay, opts && opts.customTermsNight);
			if(t && t.lower){ return t.lower; }
		}catch(e){ /* 回落埃及 */ }
	}
	return EGYPTIAN_TERMS;
}

// 后端 termsVariant 数字键 → 本模块字符串变体（与 AstroConst.TERMS_TABLES_BY_VARIANT 同序）：
// 0=埃及 / 1=托勒密·校勘本(tetrabiblos) / 2=托勒密·经典传本(ptolemaic) / 3=迦勒底(chaldean,昼夜另取)。
export function termsVariantKey(n){
	const v = Number(n) || 0;
	return ['egyptian', 'tetrabiblos', 'ptolemaic', 'chaldean', 'custom'][v] || 'egyptian';
}

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

// 经度 → 界主星。variant 缺省='egyptian'(埃及界,默认零回归);='ptolemaic' 经典传本/'tetrabiblos' 校勘本。
// opts.geminiEmended：仅对经典传本的双子生效（界4/5 ♄♂ 对调为校勘口径），缺省 false=忠原书零回归。
export function termRulerAt(lon, variant, opts){
	const sign = signOfLon(lon);
	const deg = ((lon % 360) + 360) % 360 % 30;
	let terms = termsTableFor(variant, opts)[sign] || [];
	if(opts && opts.geminiEmended && variant === 'ptolemaic' && sign === 'gemini'){
		terms = PTOLEMAIC_GEMINI_EMENDED_ROW;
	}
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

// 三分主星（按昼夜取主用/次用/共用）。variant 缺省='dorothean'(默认零回归);='ptolemaic' 用托勒密三分。
export function triplicityRulers(element, variant){
	const table = variant === 'ptolemaic' ? PTOLEMAIC_TRIPLICITY : TRIPLICITY;
	return table[element] || null;
}

// 必备尊贵打分（庙+5/旺+4/三分+3/界+2/面+1/陷−5/落−4）。dignitiesAt 由 conditions.js 调用。
export const DIGNITY_SCORE = { domicile: 5, exaltation: 4, triplicity: 3, term: 2, face: 1, detriment: -5, fall: -4 };

export { SIGN_ORDER };
export default EGYPTIAN_TERMS;
