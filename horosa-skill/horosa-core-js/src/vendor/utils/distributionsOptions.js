// 界推运(分配法 / Distributions)的四项口径 —— 页面、AI 挂载齿轮、AI 快照等各处共用这一份。
// 取值与后端 astropy/astrostudy/distributions.py 的 RELEASERS / METHODS / YEAR_DAYS / SPANS 逐个相同(测试逐个比对)。
// 请求键:distReleaser / distMethod / distYear / distYears(Java 代理白名单同名登记)。

export const DIST_RELEASERS = [
	{ value: 'Asc', label: '上升' },
	{ value: 'MC', label: '天顶' },
	{ value: 'Desc', label: '下降' },
	{ value: 'IC', label: '天底' },
	{ value: 'Sun', label: '太阳' },
	{ value: 'Moon', label: '月亮' },
	{ value: 'Mercury', label: '水星' },
	{ value: 'Venus', label: '金星' },
	{ value: 'Mars', label: '火星' },
	{ value: 'Jupiter', label: '木星' },
	{ value: 'Saturn', label: '土星' },
	{ value: 'Uranus', label: '天王星' },
	{ value: 'Neptune', label: '海王星' },
	{ value: 'Pluto', label: '冥王星' },
	{ value: 'North Node', label: '北交点（随本盘真 / 平交点）' },
	{ value: 'Vertex', label: '宿命点' },
	{ value: 'Pars Fortuna', label: '福点' },
	{ value: 'Spirit', label: '精神点' },
	{ value: 'Syzygy', label: '产前朔望点' },
];

export const DIST_METHODS = [
	{ value: 'classical', label: '上升时间（星座内均匀，古典）' },
	{ value: 'exact', label: '斜升差（逐度精确）' },
	{ value: 'qisma', label: 'Qisma（每度 1 年）' },
];

export const DIST_YEARS = [
	{ value: 'tropical', label: '回归年（365.2422 日）', days: 365.2422 },
	{ value: 'egyptian', label: '埃及年（365 日）', days: 365 },
	{ value: 'julian', label: '儒略年（365.25 日）', days: 365.25 },
];

export const DIST_SPANS = [60, 80, 100, 120, 150];

export const DIST_DEFAULTS = { distReleaser: 'Asc', distMethod: 'classical', distYear: 'tropical', distYears: 100 };

const valuesOf = (list) => list.map((o) => o.value);
const labelIn = (list, v) => { const hit = list.find((o) => o.value === v); return hit ? hit.label : `${v}`; };

// 只认合法值,其余回出厂值(与后端 normalize 同律)
export function normalizeDistSettings(opts){
	const o = opts || {};
	const span = Number(o.distYears);
	return {
		distReleaser: valuesOf(DIST_RELEASERS).indexOf(o.distReleaser) >= 0 ? o.distReleaser : DIST_DEFAULTS.distReleaser,
		distMethod: valuesOf(DIST_METHODS).indexOf(o.distMethod) >= 0 ? o.distMethod : DIST_DEFAULTS.distMethod,
		distYear: valuesOf(DIST_YEARS).indexOf(o.distYear) >= 0 ? o.distYear : DIST_DEFAULTS.distYear,
		distYears: DIST_SPANS.indexOf(span) >= 0 ? span : DIST_DEFAULTS.distYears,
	};
}

// 请求体只带与出厂值不同的键:缺省请求与旧请求逐字节相同(缓存键不变)
export function distRequestParams(opts){
	const n = normalizeDistSettings(opts);
	const out = {};
	Object.keys(DIST_DEFAULTS).forEach((k) => { if(n[k] !== DIST_DEFAULTS[k]){ out[k] = n[k]; } });
	return out;
}

export function distSettingsLine(opts){
	const n = normalizeDistSettings(opts);
	return `发放点=${labelIn(DIST_RELEASERS, n.distReleaser)}、时间算法=${labelIn(DIST_METHODS, n.distMethod)}、年长=${labelIn(DIST_YEARS, n.distYear)}、年限=${n.distYears} 年`;
}

export const distReleaserLabel = (v) => labelIn(DIST_RELEASERS, v);

// 伙伴点的相位写法:本体 / 左右 60° 90° 120° / 冲
const ASPECT_TXT = { 0: '本体', 60: '六合', 90: '四分', 120: '三分', 180: '对冲' };
export function partnerAspectText(aspect, side){
	const a = ASPECT_TXT[Number(aspect)] || `${aspect}°`;
	if(side === 'D'){ return `${a}·右`; }
	if(side === 'S'){ return `${a}·左`; }
	return a;
}
