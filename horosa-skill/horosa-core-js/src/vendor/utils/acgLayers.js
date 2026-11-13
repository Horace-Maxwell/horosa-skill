// 占星地图的两个参考图层:托勒密纬圈 / 七气候带,出生前后最近一次日食的路径。
// 纬圈按最长昼推纬度:半昼弧 H0 = 7.5° × 最长昼(时),cos H0 = −tan φ · tan ε,所以 tan φ = −cos H0 / tan ε。
// 经典档用托勒密的黄赤交角 23°51′20″;改进档用这张盘出生时刻的真黄赤交角。七气候带的中线取古典页同一张表(buildBands)。
import { buildBands } from './astroClassicalDerived.js';

export const PTOLEMY_OBLIQUITY = 23 + 51 / 60 + 20 / 3600;
export const CLIMES_MODES = ['off', 'klimata', 'parallels'];
export const CLIMES_OBLIQUITY = ['date', 'ptolemy'];
export const ECLIPSE_MODES = ['off', 'prenatal', 'postnatal'];
export const ECLIPSE_FILTERS = ['any', 'central'];

const DEG = Math.PI / 180;

export const ECLIPSE_TYPE_CN = { total: '全食', annular: '环食', hybrid: '全环食', partial: '偏食' };
export const ECLIPSE_WHICH_CN = { prenatal: '出生前最近一次', postnatal: '出生后最近一次' };

export function latitudeForLongestDay(hours, obliquity){
	const h = Number(hours);
	const eps = Number(obliquity);
	if(!Number.isFinite(h) || !Number.isFinite(eps) || h < 12 || h > 24 || eps <= 0){ return null; }
	const tanPhi = -Math.cos(7.5 * h * DEG) / Math.tan(eps * DEG);
	return Math.atan(tanPhi) / DEG;
}

// 托勒密纬圈(《至大论》卷二):最长昼 12¼ 到 18 时每 ¼ 时一条,18½ 到 20 时每 ½ 时一条,21 到 24 时每时一条(24 时即极圈);
// 赤道到极圈共 33 条
export function longestDaySteps(){
	const out = [];
	for(let q = 49; q <= 72; q += 1){ out.push(q / 4); }
	[18.5, 19, 19.5, 20].forEach((h)=>out.push(h));
	for(let h = 21; h <= 24; h += 1){ out.push(h); }
	return out;
}

export function climesObliquity(mode, chartObliquity){
	if(mode === 'ptolemy'){ return PTOLEMY_OBLIQUITY; }
	const v = Number(chartObliquity);
	return Number.isFinite(v) && v > 0 ? v : PTOLEMY_OBLIQUITY;
}

function hoursLabel(h){
	const whole = Math.floor(h);
	const frac = Math.round((h - whole) * 4);
	return `${whole}${['', '¼', '½', '¾'][frac] || ''} 时`;
}

/**
 * 纬线列表:{ lat, label, kind }。kind = center(气候带中线)/ edge(气候带边界,最长昼 ±¼ 时)/ parallel(纬圈)。
 * 纬圈两半球对称都画;七气候带是北半球的地名带,只画北边。
 */
export function climesLines(mode, obliquityMode, chartObliquity){
	if(mode !== 'klimata' && mode !== 'parallels'){ return []; }
	const eps = climesObliquity(obliquityMode, chartObliquity);
	if(mode === 'parallels'){
		const out = [];
		longestDaySteps().forEach((h)=>{
			const lat = latitudeForLongestDay(h, eps);
			if(lat === null){ return; }
			out.push({ lat, label: `最长昼 ${hoursLabel(h)}`, kind: 'parallel', hours: h });
			out.push({ lat: -lat, label: `最长昼 ${hoursLabel(h)}`, kind: 'parallel', hours: h });
		});
		return out;
	}
	const out = [];
	buildBands().forEach((band)=>{
		// 经典档用古表的纬度;改进档按出生时刻的黄赤交角由最长昼重推
		const recomputed = latitudeForLongestDay(band.longestDay, eps);
		const center = obliquityMode === 'ptolemy' || recomputed === null ? band.lat : recomputed;
		out.push({ lat: center, label: `第 ${band.n} 带 · ${band.cityCn}`, kind: 'center', hours: band.longestDay, band: band.n });
		[-0.25, 0.25].forEach((d)=>{
			const lat = latitudeForLongestDay(band.longestDay + d, eps);
			if(lat !== null){ out.push({ lat, label: `第 ${band.n} 带边界 · 最长昼 ${hoursLabel(band.longestDay + d)}`, kind: 'edge', hours: band.longestDay + d, band: band.n }); }
		});
	});
	return out;
}

function fmtLat(v){
	const n = Number(v);
	if(!Number.isFinite(n)){ return '—'; }
	return `${Math.abs(n).toFixed(2)}°${n >= 0 ? 'N' : 'S'}`;
}
function fmtLon(v){
	const n = Number(v);
	if(!Number.isFinite(n)){ return '—'; }
	return `${Math.abs(n).toFixed(2)}°${n >= 0 ? 'E' : 'W'}`;
}

const EARTH_RADIUS_KM = 6371.0088;

// 点 p 到多段路径线的最短地面距离(km)。每段在 p 处取局部等距平面(经度差 × cos 纬度),中低纬误差在 0.2 km 内;极区(纬度 80° 上下)平面近似偏小,可差到约 2%。
function distanceToPolylineKm(p, line){
	if(!p || !Array.isArray(line) || line.length < 2){ return null; }
	const k = Math.cos(Number(p.lat) * DEG);
	const wrap = (d)=>((d + 540) % 360) - 180;
	let best = null;
	for(let i = 0; i + 1 < line.length; i += 1){
		const a = line[i];
		const b = line[i + 1];
		const ax = wrap(a.lon - p.lon) * k;
		const ay = a.lat - p.lat;
		const bx = wrap(b.lon - p.lon) * k;
		const by = b.lat - p.lat;
		const dx = bx - ax;
		const dy = by - ay;
		const len = dx * dx + dy * dy;
		const t = len > 0 ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len)) : 0;
		const x = ax + t * dx;
		const y = ay + t * dy;
		const d = Math.sqrt(x * x + y * y) * DEG * EARTH_RADIUS_KM;
		if(Number.isFinite(d) && (best === null || d < best)){ best = d; }
	}
	return best;
}

/**
 * 食甚处的地面带宽:食甚点到北界、南界两条线的最短距离之和(北界 / 南界是影斑扫过地面的包络)。
 * 算不出(非中心食、边界缺一侧)返回 null。
 */
export function eclipseBandWidthKm(eclipse){
	if(!eclipse || !eclipse.central || !eclipse.greatest){ return null; }
	const north = distanceToPolylineKm(eclipse.greatest, eclipse.north);
	const south = distanceToPolylineKm(eclipse.greatest, eclipse.south);
	if(north === null || south === null){ return null; }
	return north + south;
}

// 日食路径的文字摘要(快照 / 页面说明共用):时刻、食型、食分、最大食位置、带宽、路径起止。
// 带宽报的是食甚处两侧边界之间的地面距离;后端的 widthKm 是本影在投影面(过地心、垂直于影轴的平面)上的直径,
// 太阳不在天顶时影斑斜落在地面上,地面带宽比它宽(2026-08-12 食甚在冰岛西边,投影面 132 km,地面约 300 km)。
// 时刻:local 是按出生盘的时区折算的,不是食甚地点的当地时间。
export function eclipseSummaryLines(eclipse){
	if(!eclipse || !eclipse.greatest){ return []; }
	const out = [];
	const days = Number(eclipse.daysFromBirth);
	const when = Number.isFinite(days) ? `${days < 0 ? '出生前' : '出生后'} ${Math.abs(days).toFixed(1)} 日` : '';
	out.push(`${ECLIPSE_WHICH_CN[eclipse.which] || ''}${eclipse.filter === 'central' ? '中心' : ''}日食:${ECLIPSE_TYPE_CN[eclipse.type] || eclipse.type},食甚 ${eclipse.local || ''}(出生地时区)/ ${eclipse.utc || ''}(UT),${when}`);
	const mag = Number(eclipse.magnitude);
	const band = eclipseBandWidthKm(eclipse);
	let width = '';
	if(band !== null){
		width = `,食甚处食带宽约 ${Math.round(band)} km(两侧边界之间的地面距离)`;
	}else if(eclipse.widthKm){
		width = `,本影直径 ${Math.round(eclipse.widthKm)} km(投影面上的量,不是地面带宽)`;
	}
	out.push(`食甚地点 ${fmtLat(eclipse.greatest.lat)} ${fmtLon(eclipse.greatest.lon)}${Number.isFinite(mag) ? `,食分 ${mag.toFixed(4)}` : ''}${width}`);
	const track = eclipse.track || [];
	if(track.length){
		const a = track[0];
		const b = track[track.length - 1];
		out.push(`${eclipse.central ? '中心线' : '最大食分点轨迹'}:${fmtLat(a.lat)} ${fmtLon(a.lon)} → ${fmtLat(b.lat)} ${fmtLon(b.lon)}`);
	}
	if(!eclipse.central){
		out.push(eclipse.type === 'partial'
			? '偏食没有中心线,地图上画的是每一刻食分最大的地点连成的线。'
			: '这次是非中心食(本影只扫过地球边缘,没有中心线),地图上画的是每一刻食分最大的地点连成的线。');
	}
	return out;
}

export function climesSummaryLines(mode, obliquityMode, chartObliquity){
	if(mode !== 'klimata' && mode !== 'parallels'){ return []; }
	const eps = climesObliquity(obliquityMode, chartObliquity);
	const head = `${mode === 'klimata' ? '七气候带' : '托勒密纬圈'}(黄赤交角 ${eps.toFixed(4)}°,${obliquityMode === 'ptolemy' ? '经典:托勒密值' : '改进:出生时刻的值'})`;
	const rows = climesLines(mode, obliquityMode, chartObliquity)
		.filter((row)=>row.lat >= 0 && row.kind !== 'edge')
		.map((row)=>`${row.label} ${fmtLat(row.lat)}`);
	return [head, rows.join(';')];
}
