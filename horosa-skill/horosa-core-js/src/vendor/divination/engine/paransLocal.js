// 恒星交映(parans,Brady 口径)·固定地点版。Brady 口径:
//   paran = 二天体同日各踞一轴(升/中天/落/天底),小容许度内重合;
//   地平接触 cos H₀ = −tanφ·tanδ;子午接触 RA = RAMC。
// 择日盘为固定时刻+固定地点 → 直接以「轴恒星时角之差」判交映:
//   各天体四轴 LST(度):升 = α−H₀ / 落 = α+H₀ / 中天 = α / 天底 = α+180。
//   差 ≤ orbDeg(默认 2° ≈ 8 分钟,Brady「数分钟」档)→ 成交映。
// 行星赤经赤纬:由黄经按 β≈0 转换(七曜黄纬小,≤1.5° 内误差可忽;月亮 β 至 5°,
//   detail 明示近似口径);恒星:表存 λ/δ,β 由球面三角闭式反解后求 α。
import { norm360 } from './utils.js';

const OBLIQUITY = 23.4367; // J2000 平黄赤交角(度)
const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;

// 黄道(λ,β) → 赤道(α,δ)
export function eclToEq(lonDeg, latDeg){
	const l = lonDeg * D2R; const b = (latDeg || 0) * D2R; const e = OBLIQUITY * D2R;
	const sinDec = Math.sin(b) * Math.cos(e) + Math.cos(b) * Math.sin(e) * Math.sin(l);
	const dec = Math.asin(Math.max(-1, Math.min(1, sinDec)));
	const y = Math.sin(l) * Math.cos(e) - Math.tan(b) * Math.sin(e);
	const x = Math.cos(l);
	const ra = Math.atan2(y, x);
	return { ra: norm360(ra * R2D), dec: dec * R2D };
}

// 已知黄经 λ 与赤纬 δ(恒星表存法)→ 反解黄纬 β,再求赤经 α。
// sinδ = sinβ·cosε + cosβ·sinε·sinλ = R·sin(β+φ₀),R=√(cos²ε+sin²ε·sin²λ),φ₀=atan2(sinε·sinλ, cosε)
export function starEq(lonDeg, decDeg){
	const l = lonDeg * D2R; const e = OBLIQUITY * D2R; const d = decDeg * D2R;
	const A = Math.cos(e); const B = Math.sin(e) * Math.sin(l);
	const R = Math.sqrt(A * A + B * B);
	const phi0 = Math.atan2(B, A);
	const s = Math.max(-1, Math.min(1, Math.sin(d) / R));
	const beta = Math.asin(s) - phi0;
	return eclToEq(lonDeg, beta * R2D);
}

// 升落半日弧时角 H₀(度);|tanφ·tanδ|>1 → 拱极/永不升(null)。
export function riseHourAngle(latDeg, decDeg){
	const c = -Math.tan(latDeg * D2R) * Math.tan(decDeg * D2R);
	if(c < -1 || c > 1) return null;
	return Math.acos(c) * R2D;
}

// 四轴 LST(度)。拱极天体只有中天/天底。
export function axisLstDeg(ra, dec, latDeg){
	const h0 = riseHourAngle(latDeg, dec);
	const out = { mc: norm360(ra), ic: norm360(ra + 180) };
	if(h0 !== null){
		out.rise = norm360(ra - h0);
		out.set = norm360(ra + h0);
	}
	return out;
}

const AXIS_CN = { rise: '升', set: '落', mc: '中天', ic: '天底' };

// 固定地点交映:bodies=[{key,cn,lon,lat?}],stars=[{name_cn,lon,dec,avoid,meaning}]。
// 返回 [{star,body,starAxis,bodyAxis,diffDeg,diffMin,avoid,meaning}],按差升序。
export function paransAt(latDeg, bodies, stars, orbDeg){
	const orb = orbDeg === undefined ? 2 : orbDeg;
	const out = [];
	const bodyAx = bodies.map((b) => {
		const eq = eclToEq(b.lon, b.lat || 0);
		return { ...b, axes: axisLstDeg(eq.ra, eq.dec, latDeg) };
	});
	stars.forEach((st) => {
		const eq = starEq(st.lon, st.dec);
		const sAx = axisLstDeg(eq.ra, eq.dec, latDeg);
		bodyAx.forEach((b) => {
			Object.keys(sAx).forEach((se) => {
				Object.keys(b.axes).forEach((be) => {
					// 中天-天底同对互斥无意义组合不滤(Brady 允许交叉轴);仅去同值重复。
					let d = Math.abs(sAx[se] - b.axes[be]);
					if(d > 180) d = 360 - d;
					if(d <= orb){
						out.push({
							star: st.name_cn, body: b.key, bodyCn: b.cn,
							starAxis: AXIS_CN[se], bodyAxis: AXIS_CN[be],
							diffDeg: d, diffMin: Math.round(d * 4 * 10) / 10,
							avoid: !!st.avoid, meaning: st.meaning || '', conditional: st.conditional || null,
						});
					}
				});
			});
		});
	});
	return out.sort((a, b) => a.diffDeg - b.diffDeg);
}

export default paransAt;
