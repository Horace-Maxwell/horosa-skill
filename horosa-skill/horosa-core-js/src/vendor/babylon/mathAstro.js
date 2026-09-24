// divination/babylon/mathAstro.js —— System A(阶梯/分带)与 System B(锯齿)数理引擎。
// System A:黄道分带、带内会合弧恒值,越界部分按两带弧值之比缩放(可连跨两界——水星常见);
// System B:在 m/M 间以定差 d 增减、极值反射的线性锯齿。
// 日期:Δt(tithi,超整月基数部分)= Δλ(度)+ c(各行星常数)。

import { sexParse, norm360 } from './units.js';
import { SYSTEM_A, SYSTEM_B, DATE_CONSTANTS, LUNAR, SAROS } from '../divination/data/babylonianData.js';

const S = sexParse;

// ── 锯齿(zigzag)────────────────────────────────────────────────────
// 反射式:v 在 [m, M] 间以 ±d 行进,触界反射(标准 ACT 规则:超出部分折回)。
export function zigzagNext(v, dir, m, M, d){
	let nv = v + dir * d;
	let ndir = dir;
	if(nv > M){ nv = 2 * M - nv; ndir = -1; }
	else if(nv < m){ nv = 2 * m - nv; ndir = 1; }
	return { v: nv, dir: ndir };
}
export function zigzagSeq(v0, dir0, count, params){
	const m = S(params.m), M = S(params.M), d = S(params.d);
	const out = [];
	let v = v0, dir = dir0;
	for(let i = 0; i < count; i++){
		out.push(v);
		const nx = zigzagNext(v, dir, m, M, d);
		v = nx.v; dir = nx.dir;
	}
	return out;
}

// ── 阶梯(step)带表工具 ─────────────────────────────────────────────
// zones: [{from, to, w}](黄经度;from>to 表示跨 0°;w 六十进制字符串或数)
function inZone(lam, z){
	const L = norm360(lam);
	const a = norm360(z.from), b = norm360(z.to);
	if(a < b){ return L >= a && L < b; }
	return L >= a || L < b;   // 跨 0°
}
export function zoneOf(lam, zones){
	for(let i = 0; i < zones.length; i++){ if(inZone(lam, zones[i])){ return i; } }
	return 0;
}
function distToBoundary(lam, z){
	// 自 lam 顺行到带终点 to 的弧长
	return norm360(norm360(z.to) - norm360(lam)) || 360;
}

// System A 单步:自 lam 前进本带弧 w,越界部分按 w_next/w_cur 缩放(循环处理,支持连跨多界)。
export function stepAdvance(lam, zones){
	let L = norm360(lam);
	let zi = zoneOf(L, zones);
	let w = S(zones[zi].w);
	const w0 = w;
	let guard = 0;
	while(guard++ < 8){
		const db = distToBoundary(L, zones[zi]);
		if(Math.abs(w) < db - 1e-9){
			return { lon: norm360(L + w), w: w0, zone: zi };
		}
		// 走到界,余量换带缩放
		const rest = w - Math.sign(w) * db;
		L = norm360(zones[zi].to);
		const nz = (zi + 1) % zones.length;
		const scale = S(zones[nz].w) / S(zones[zi].w);
		w = rest * scale;
		zi = nz;
	}
	return { lon: norm360(L + w), w: w0, zone: zi };
}

// 生成 System A 现象序列:[{lon, w}] × count
export function synodicSeriesA(lam0, zones, count){
	const out = [];
	let L = norm360(lam0);
	for(let i = 0; i < count; i++){
		out.push({ lon: L });
		const nx = stepAdvance(L, zones);
		out[out.length - 1].w = nx.w;
		L = nx.lon;
	}
	return out;
}

// 生成 System B 现象序列(会合弧锯齿):初弧 w0/方向 dir0
export function synodicSeriesB(lam0, w0, dir0, count, params){
	const m = S(params.m), M = S(params.M), d = S(params.d);
	const out = [];
	let L = norm360(lam0), w = w0, dir = dir0;
	for(let i = 0; i < count; i++){
		out.push({ lon: L, w });
		L = norm360(L + w);
		const nx = zigzagNext(w, dir, m, M, d);
		w = nx.v; dir = nx.dir;
	}
	return out;
}

// 附日期:Δt = Δλ + c(tithi,超整月基数);返回 [{lon, w, months, tithi}]
export function withDates(series, planetKey){
	const dc = DATE_CONSTANTS.find((x) => x.planet === planetKey);
	const c = dc ? S(dc.c) : 0;
	const base = dc ? dc.baseMonths : 12;
	return series.map((row) => {
		if(row.w === undefined){ return row; }
		let months = base;
		// Δt(tithi)= Δλ + c,超出 30 的整月进位到 months。
		// 各星 w 的存法已统一为「参与日期公式的那个弧」:金星存超 360 余量、水星存全程会合弧,
		// 故此处无须任何 >180 归一化(历史上那行归一化会把金星 215° 误折成负值,已删)。
		let tithi = row.w + c;
		while(tithi >= 30){ tithi -= 30; months += 1; }
		while(tithi < 0){ tithi += 30; months -= 1; }
		return { ...row, months, tithi };
	});
}

// ── 各行星便捷入口 ──────────────────────────────────────────────────
export function jupiterSeriesA(lam0, count, variant){
	const t = variant === 'A1' ? SYSTEM_A.jupiterA1 : SYSTEM_A.jupiter;
	return withDates(synodicSeriesA(lam0, t.zones, count), 'jupiter');
}
export function saturnSeriesA(lam0, count){
	return withDates(synodicSeriesA(lam0, SYSTEM_A.saturn.zones, count), 'saturn');
}
export function marsSeriesA(lam0, count){
	return withDates(synodicSeriesA(lam0, SYSTEM_A.mars.zones, count), 'mars');
}
// 金星:各现象带表(值=超出 360° 部分;真跳 = 360 + w)
export function venusSeriesA(lam0, phenom, count){
	let zones;
	if(phenom === 'el'){ zones = [{ from: 0, to: 0, w: SYSTEM_A.venus.el.const }]; }
	else { zones = SYSTEM_A.venus[phenom]; }
	const out = [];
	let L = norm360(lam0);
	for(let i = 0; i < count; i++){
		const zi = zones.length === 1 ? 0 : zoneOf(L, zones);
		const w = S(zones[zi].w);
		out.push({ lon: L, w });
		L = norm360(L + w);   // 360+w ≡ w (mod 360)
	}
	return withDates(out, 'venus');
}
// 水星:phase ∈ mf/ef/ml/el(单会合步),或 threeSynarc(3-synarc 步)
export function mercurySeriesA(lam0, phase, count){
	const t = SYSTEM_A.mercury[phase];
	return withDates(synodicSeriesA(lam0, t.zones, count), 'mercury');
}
export function mercuryA3Series(lam0, count){
	// 3-synarc 两带(每步 = 3 会合;弧 = 360×3 + w,w 为负缩减)
	const zones = SYSTEM_A.mercury.a3.zones;
	const out = [];
	let L = norm360(lam0);
	for(let i = 0; i < count; i++){
		const nx = stepAdvance(L, zones);
		out.push({ lon: L, w: nx.w });
		L = nx.lon;
	}
	return out;
}
export function jupiterSeriesB(lam0, count){
	const p = SYSTEM_B.jupiter;
	// 初弧取均值、升向(锚定文献步进方式;首值可由用户观测锚替换)
	return withDates(synodicSeriesB(lam0, S(p.mu), 1, count, p), 'jupiter');
}

// ── 会合弧细分:木星梯形法(速度线性递减 → 位置为二次) ────────────────
// 由两梯形面积(首 60 日 10;45°、日 60–120 5;30°)解 v0 与斜率 k:
//   60v0 − 1800k = 10;45,60v0 − 5400k = 5;30 → k = 5;15/3600,v0 = 0;13,22,30 /日
export const TRAPEZOID = (() => {
	const A1 = S('10;45'), A2 = S('5;30');
	const k = (A1 - A2) / 3600;
	const v0 = (A1 + 1800 * k) / 60;
	// 等面积二分:v0τ − kτ²/2 = A1/2 的较小根
	const half = A1 / 2;
	const disc = Math.sqrt(v0 * v0 - 2 * k * half);
	const tau = (v0 - disc) / k;
	return {
		v0, k, tau,
		posAt(t){ return v0 * t - k * t * t / 2; },
		veloAt(t){ return v0 - k * t; },
	};
})();

// 外行星「推」细分(带符号子弧;示例=木星文献值)
export const JUPITER_PUSHES = [
	{ seg: 'Ω→Γ', note: '不可见期(偕日没→偕日升)' },
	{ seg: 'Γ→Φ', arc: null, note: '顺行加速段' },
	{ seg: 'Φ→Θ', arc: S('−4;25'.replace('−', '-')), note: '逆行前半' },
	{ seg: 'Θ→Ψ', arc: S('-5;35'), note: '逆行后半' },
	{ seg: 'Φ→Ψ 全逆行', arc: S('-10;0') },
	{ seg: 'Ω→Φ(跨升)', arc: S('22;15'), time: '2,30 tithi' },
];
export const ACT817_RULE = { s1: 1 / 3, ar: 1 / 2, s2: 2 / 3 };

// ── 月亮列(可真算部分)───────────────────────────────────────────────
export const LUNAR_PHI = { m: '1,57;47,57,46,40', M: '2,17;4,48,53,20', d: '2;45,55,33,20', mu: '2,7;26,26,40' };
export function lunarPhiSeq(count, v0, dir0){
	const start = v0 === undefined ? S(LUNAR_PHI.mu) : v0;
	return zigzagSeq(start, dir0 === undefined ? 1 : dir0, count, LUNAR_PHI);
}
// 月 B 列:太阳月速两带阶梯(快 30 处女13°→双鱼27°;慢 28;7,30)
export const LUNAR_SOLAR_ZONES = [
	{ from: 163, to: 357, w: '30;0' },
	{ from: 357, to: 163, w: '28;7,30' },
];
export function lunarBSeq(lon0, count){
	return synodicSeriesA(lon0, LUNAR_SOLAR_ZONES, count);
}
// System B 太阳速度锯齿(A 列)
export const LUNAR_SOLAR_B = { m: '28;10,39,40', M: '30;1,59,20', d: null, mu: '29;6,19,20' };
// 昼长 C(UŠ):四锚线性锯齿(A 规范分至在基本宫 10°;3:2 比 216/144/180)
export function dayLengthC(lonSun, solsticeDeg){
	const sd = solsticeDeg === undefined ? 10 : solsticeDeg;
	const anchors = [
		{ L: 0 + sd, v: 180 },     // 春分(白羊 sd)
		{ L: 90 + sd, v: 216 },    // 夏至
		{ L: 180 + sd, v: 180 },   // 秋分
		{ L: 270 + sd, v: 144 },   // 冬至
	];
	const L = norm360(lonSun);
	for(let i = 0; i < 4; i++){
		const a = anchors[i], b = anchors[(i + 1) % 4];
		const span = norm360(b.L - a.L) || 90;
		const off = norm360(L - a.L);
		if(off < span){ return a.v + (b.v - a.v) * off / span; }
	}
	return 180;
}
export function cPrime(cPrev, cCur){ return (cPrev - cCur) / 2; }
// F 列(月日速):System A 锯齿(极值由 μ/d/周期派生,非原校——UI 标注)
export const LUNAR_F_A = (() => {
	const mu = S('13;30,30'), d = S('0;42');
	const P = 6247 / 448;                  // 周期(月/周)
	const delta = P * d / 2;
	return { mu, d, m: mu - delta, M: mu + delta, P, derived: true };
})();
export function lunarFSeqA(count, v0, dir0){
	return zigzagSeq(v0 === undefined ? LUNAR_F_A.mu : v0, dir0 === undefined ? 1 : dir0, count,
		{ m: LUNAR_F_A.m, M: LUNAR_F_A.M, d: LUNAR_F_A.d });
}
export const LUNAR_J_SLOW = S('0;57,3,45');
export const LUNAR_K_MEAN_DAYS = S('0;31,50,8,20');

// ── Saros 食可能模式(38 = 33×6 + 5×5;5 组 8,7,8,7,8)──────────────────
export function sarosPattern(){
	const groups = [8, 7, 8, 7, 8];
	const out = [];
	let m = 0;
	for(let g = 0; g < groups.length; g++){
		for(let i = 0; i < groups[g]; i++){
			out.push(m);
			m += 6;
		}
		m -= 6; m += 5;   // 组间一步 5 月
	}
	return out;   // 38 项;末 + 5 = 223
}
export function sarosInfo(){ return SAROS; }

// 由锚食月号(自某朔望起算的月序)铺 38 格食可能(前后各一 Saros 范围)
export function eclipsePossibilities(anchorMonthIndex, monthsSpan){
	const pat = sarosPattern();
	const out = [];
	for(let saros = -2; saros <= 2; saros++){
		for(let i = 0; i < pat.length; i++){
			const m = anchorMonthIndex + saros * 223 + pat[i];
			if(Math.abs(m - anchorMonthIndex) <= monthsSpan){ out.push(m); }
		}
	}
	return out.sort((a, b) => a - b).filter((v, i, arr) => i === 0 || v !== arr[i - 1]);
}

// 验证辅助:周期恒等(供 jest 与自检面板)
export function verifyPeriods(){
	const checks = [];
	// 火星:133 × 48;43,18 = 18 × 360
	checks.push({ name: 'mars', ok: Math.abs(133 * S('48;43,18') - 18 * 360) < 0.05, val: 133 * S('48;43,18') });
	// 木星:36 × 360 / 391 = 33;8,45
	checks.push({ name: 'jupiter', ok: Math.abs(36 * 360 / 391 - S('33;8,45')) < 0.001, val: 36 * 360 / 391 });
	// 土星:9 × 360 / 256 = 12;39,22,30
	checks.push({ name: 'saturn', ok: Math.abs(9 * 360 / 256 - S('12;39,22,30')) < 0.001, val: 9 * 360 / 256 });
	// 木星 B:(M+m)/2 = μ
	checks.push({ name: 'jupiterB', ok: Math.abs((S('38;2') + S('28;15,30')) / 2 - S('33;8,45')) < 0.001 });
	// 升时总和 360
	return checks;
}
