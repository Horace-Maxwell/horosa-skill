// divination/data/egyptianParans.js
// 共升星(paranatellonta):与某黄道度「同时升 / 同时中天 / 同时落」的恒星。
//
// 这是埃及旬星体系的技术内核 —— 旬本就是靠「某星与日同升」来标记的;把它算准,
// 旬名录才不只是一张查得的表。故此处不查表、不臆造,而是按古典斜升法实算:
//
//   ① 恒星表给的是某历元黄经 + 赤纬。黄纬 β 在岁差下近似不变 → 先由(λ₀, δ₀, ε₀)反解 β,
//      再把 λ 岁差到盘的年份,以不变的 β 重算该年的 (α, δ)。只精到显示所需,不进任何金标链。
//   ② 赤经差 AD = asin(tanφ · tanδ);东地平斜升 OA = α − AD、西地平斜降 OD = α + AD。
//      |tanφ·tanδ| > 1 → 该星在此纬度拱极或永不升起(照实标注,不当成 0 处理)。
//   ③ 黄道度 λe 的同名量同法可算(β=0)。OA 相等 ⇒ 同升;α 相等 ⇒ 同中天;OD 相等 ⇒ 同落。
//
// 全部为纯函数,零后端、零请求;恒星表复用既有 FIXED_STARS(含 lon_1995 与 declination)。

import { FIXED_STARS, PRECESSION_ARCSEC_PER_YEAR } from './fixedStars.js';

const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;
const norm360 = (x) => ((x % 360) + 360) % 360;
// 角差取最短弧(−180,180]
export function angDiff(a, b){
	let d = norm360(a) - norm360(b);
	if(d > 180){ d -= 360; }
	if(d <= -180){ d += 360; }
	return d;
}

/** 平黄赤交角(度)。year 为公历年(小数年即可);只求显示精度。 */
export function obliquity(year){
	const T = ((Number(year) || 2000) - 2000) / 100;
	return 23.4392911 - 0.0130042 * T - 0.00000016 * T * T + 0.000000504 * T * T * T;
}

/** 恒星表历元(黄经栏所注年份)。 */
export const STAR_CATALOG_EPOCH = 1995;

/** 岁差:把历元黄经推到目标年(仅黄经匀速项,黄纬视为不变)。 */
export function precessLon(lon1995, year){
	const dy = (Number(year) || STAR_CATALOG_EPOCH) - STAR_CATALOG_EPOCH;
	return norm360(Number(lon1995) + (PRECESSION_ARCSEC_PER_YEAR / 3600) * dy);
}

/**
 * 由(黄经 λ, 赤纬 δ, 交角 ε)反解黄纬 β。
 * sinδ = sinβ·cosε + cosβ·sinε·sinλ = R·sin(β + p),R=√(cos²ε + sin²ε sin²λ)、tan p = (sinε sinλ)/cosε
 * → β = asin(sinδ / R) − p。δ 超出该 λ 上的可达范围时钳到边界(返回 clamped 标记)。
 */
export function eclLatFrom(lonDeg, decDeg, epsDeg){
	const A = Math.sin(epsDeg * D2R) * Math.sin(lonDeg * D2R);
	const B = Math.cos(epsDeg * D2R);
	const R = Math.hypot(A, B);
	const p = Math.atan2(A, B);
	let s = Math.sin(decDeg * D2R) / R;
	let clamped = false;
	if(s > 1){ s = 1; clamped = true; }
	if(s < -1){ s = -1; clamped = true; }
	return { beta: (Math.asin(s) - p) * R2D, clamped };
}

/** 黄道坐标 → 赤道坐标。 */
export function eclToEq(lonDeg, latDeg, epsDeg){
	const l = lonDeg * D2R; const b = latDeg * D2R; const e = epsDeg * D2R;
	const sinDec = Math.sin(b) * Math.cos(e) + Math.cos(b) * Math.sin(e) * Math.sin(l);
	const dec = Math.asin(Math.max(-1, Math.min(1, sinDec)));
	const y = Math.sin(l) * Math.cos(e) - Math.tan(b) * Math.sin(e);
	const ra = Math.atan2(y, Math.cos(l));
	return { ra: norm360(ra * R2D), dec: dec * R2D };
}

/**
 * 赤经差与斜升/斜降。
 * @returns {{ad, oa, od, circumpolar:boolean, neverRises:boolean}}
 *   circumpolar/neverRises 时 ad 为 null —— 该星在此纬度不存在地平升落,OA/OD 无定义。
 */
export function obliqueAscension(raDeg, decDeg, latDeg){
	const t = Math.tan(latDeg * D2R) * Math.tan(decDeg * D2R);
	if(!Number.isFinite(t) || Math.abs(t) > 1){
		// tanφ·tanδ 同号且超界 = 常显(拱极);异号超界 = 常隐
		const north = (latDeg >= 0) === (decDeg >= 0);
		return { ad: null, oa: null, od: null, circumpolar: north, neverRises: !north };
	}
	const ad = Math.asin(t) * R2D;
	return { ad, oa: norm360(raDeg - ad), od: norm360(raDeg + ad), circumpolar: false, neverRises: false };
}

/** 黄道上某度(β=0)的赤道量与斜升/斜降。 */
export function eclipticDegreeFrames(lonDeg, latDeg, epsDeg){
	const eq = eclToEq(lonDeg, 0, epsDeg);
	const oa = obliqueAscension(eq.ra, eq.dec, latDeg);
	return { ...eq, ...oa };
}

/** 恒星在目标年、目标纬度下的全套定位量。 */
export function starFrames(star, year, latDeg){
	const eps0 = obliquity(STAR_CATALOG_EPOCH);
	const { beta, clamped } = eclLatFrom(Number(star.lon_1995), Number(star.declination), eps0);
	const eps = obliquity(year);
	const lon = precessLon(star.lon_1995, year);
	const eq = eclToEq(lon, beta, eps);
	const oa = obliqueAscension(eq.ra, eq.dec, latDeg);
	return {
		name_cn: star.name_cn, name_en: star.name_en, magnitude: star.magnitude,
		isRoyal: !!star.isRoyal, nature: star.nature || [],
		lon, beta, betaClamped: clamped, ...eq, ...oa,
	};
}

export const PARAN_KINDS = [
	{ key: 'rise', label: '同升', note: '与该度同时自东方地平升起。' },
	{ key: 'culminate', label: '同中天', note: '与该度同时上中天(过子午线最高处)。' },
	{ key: 'set', label: '同落', note: '与该度同时自西方地平沉落。' },
	{ key: 'lowerCulminate', label: '同下中天', note: '与该度同时下中天(过子午线最低处)。' },
];

export const PARAN_ORB_DEFAULT = 1.5;   // 度(赤经/斜升面)

/**
 * 求与给定黄道度共升/共中天/共落/共下中天的恒星。
 * @param {number} lonDeg   目标黄道度(如上升度、日月所在度)
 * @param {number} latDeg   地理纬度(北正)
 * @param {number} year     公历年(定岁差与交角)
 * @param {number} orb      容许度(赤经面),默认 1.5°
 * @param {Array}  catalog  恒星表(默认本仓 FIXED_STARS)
 * @returns {Array<{star, kind, delta}>} 按 |delta| 升序
 */
export function paransForDegree(lonDeg, latDeg, year, orb = PARAN_ORB_DEFAULT, catalog = FIXED_STARS){
	const lon = Number(lonDeg); const lat = Number(latDeg);
	if(!Number.isFinite(lon) || !Number.isFinite(lat)){ return []; }
	const eps = obliquity(year);
	const target = eclipticDegreeFrames(lon, lat, eps);
	const out = [];
	(catalog || []).forEach((s) => {
		if(!s || s.lon_1995 == null || s.declination == null){ return; }
		const f = starFrames(s, year, lat);
		const push = (kind, a, b) => {
			if(a == null || b == null){ return; }
			const d = angDiff(a, b);
			if(Math.abs(d) <= orb){ out.push({ star: f, kind, delta: d }); }
		};
		push('rise', f.oa, target.oa);
		push('set', f.od, target.od);
		push('culminate', f.ra, target.ra);
		push('lowerCulminate', norm360(f.ra + 180), target.ra);
	});
	out.sort((a, b) => Math.abs(a.delta) - Math.abs(b.delta));
	return out;
}

/** 该纬度下永不升起 / 常显不落的星(照实列出,不混进共升结果)。 */
export function circumpolarSplit(latDeg, year, catalog = FIXED_STARS){
	const lat = Number(latDeg);
	const always = []; const never = [];
	if(!Number.isFinite(lat)){ return { always, never }; }
	(catalog || []).forEach((s) => {
		if(!s || s.lon_1995 == null || s.declination == null){ return; }
		const f = starFrames(s, year, lat);
		if(f.circumpolar){ always.push(f); }
		else if(f.neverRises){ never.push(f); }
	});
	return { always, never };
}

export const PARAN_NOTE = '共升星按古典斜升法实算:恒星表的历元黄经先岁差到本盘年份(黄纬视为不变),'
	+ '再由赤经差 AD=asin(tanφ·tanδ)得东地平斜升 OA 与西地平斜降 OD;与目标度的同名量相等即为共起。'
	+ '故结果随出生地纬度与年代真实变化,不是一张固定对照表。高纬度下部分恒星拱极常显或永不升起,单独列出。';
