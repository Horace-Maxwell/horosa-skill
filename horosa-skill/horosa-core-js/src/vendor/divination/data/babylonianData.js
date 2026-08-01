// divination/data/babylonianData.js —— 巴比伦数据表具名导出 + 派生 helper(JSON 存真值)。
import raw from './babylonianData.json' with { type: 'json' };

export const BABYLON_SIGNS = raw.signs;
export const BABYLON_NORMAL_STARS = raw.normalStars;
export const BABYLON_ZIQPU = raw.ziqpu;
export const BABYLON_ZIQPU_MULAPIN = raw.ziqpuMulapin;
export const BABYLON_PLANETS = raw.planets;
export const GOD_NUMBERS = raw.godNumbers;
export const BABYLON_EXALTATIONS = raw.exaltations;
export const BABYLON_TRIPLICITIES = raw.triplicities;
export const BABYLON_TERMS_ARIES = raw.termsAries;
export const FOUR_LANDS = raw.fourLands;
export const BABYLON_COLORS = raw.colors;
export const GOAL_YEAR = raw.goalYear;
export const MULAPIN = raw.mulapin;
export const EAE = raw.eae;
export const SYSTEM_A = raw.systemA;
export const SYSTEM_B = raw.systemB;
export const DATE_CONSTANTS = raw.dateConstants;
export const PERIOD_RELATIONS = raw.periods;
export const SUBDIVISION = raw.subdivision;
export const LUNAR = raw.lunar;
export const LUNAR_SIX = raw.lunarSix;
export const SAROS = raw.saros;
export const RISING_TIMES = raw.risingTimes;
export const HOROSCOPE_META = raw.horoscope;
export const HEMEROLOGY = raw.hemerology;
export const KALENDERTEXT_GOLDEN = raw.kalendertextGolden;
export const MICROZODIAC_EXTRA = raw.microzodiacExtra;
export const BABYLON_CONSTANTS = raw.constants;
export const NOTES = {
	melothesia: raw.melothesiaCaveat,
	normalStars: raw.normalStarsNote,
	ziqpu: raw.ziqpuNote,
	exaltation: raw.exaltationCaveat,
	triplicity: raw.triplicityCaveat,
	terms: raw.termsNote,
	fourLands: raw.fourLandsRule,
	lunarSix: raw.lunarSixNote,
};

// ── 索引 helper ─────────────────────────────────────────────────────
const signByN = {};
BABYLON_SIGNS.forEach((s) => { signByN[s.n] = s; });
export function babylonSign(n){ return signByN[((n - 1) % 12 + 12) % 12 + 1] || null; }

const planetByKey = {};
BABYLON_PLANETS.forEach((p) => { planetByKey[p.key] = p; });
export function babylonPlanet(key){ return planetByKey[key] || null; }

const exaltByPlanet = {};
BABYLON_EXALTATIONS.forEach((e) => { exaltByPlanet[e.planet] = e; });
export function exaltationOf(planetKey){ return exaltByPlanet[planetKey] || null; }

// 宫 → 三分组
const tripBySign = {};
BABYLON_TRIPLICITIES.forEach((t) => { t.signs.forEach((s) => { tripBySign[s] = t; }); });
export function triplicityOfSign(sign){ return tripBySign[sign] || null; }

// 月号 → 三分组(月 M 归入含宫 M 的组;分至月方案用)
export function triplicityOfMonth(m){ return triplicityOfSign(((m - 1) % 12 + 12) % 12 + 1); }

// 宫内度 → 界主(全宫同构:首段=三分主;白羊结构 1–5/6–12/13–20/21–25/26–30)
export function termLordOfDeg(deg){
	const d = Math.max(0, Math.min(29.999, deg));
	for(let i = 0; i < BABYLON_TERMS_ARIES.length; i++){
		const t = BABYLON_TERMS_ARIES[i];
		if(d + 1 >= t.from && d + 1 <= t.to + 0.999){ return t; }
	}
	return BABYLON_TERMS_ARIES[BABYLON_TERMS_ARIES.length - 1];
}

// 生日(1–30)→ 日段主(与界同构)
export function daySegmentLord(day){
	for(let i = 0; i < BABYLON_TERMS_ARIES.length; i++){
		const t = BABYLON_TERMS_ARIES[i];
		if(day >= t.from && day <= t.to){ return t; }
	}
	return null;
}

// 月份 → 所主之国(月食地理)
export function landOfMonth(m){
	const mm = ((m - 1) % 12 + 12) % 12 + 1;
	return FOUR_LANDS.find((l) => l.months.indexOf(mm) >= 0) || null;
}

// 升时:宫 n 的升时(UŠ)与自白羊 0° 至黄经 L 的累积升时
const RT = {};
RISING_TIMES.systemA.forEach((r) => { RT[r.sign] = r.us; });
export function risingTimeOfSign(sign){ return RT[((sign - 1) % 12 + 12) % 12 + 1] || 30; }
export function cumulativeRisingTime(lon){
	const L = ((lon % 360) + 360) % 360;
	const sign = Math.floor(L / 30) + 1;
	let acc = 0;
	for(let s = 1; s < sign; s++){ acc += risingTimeOfSign(s); }
	return acc + risingTimeOfSign(sign) * (L % 30) / 30;
}
