// 年龄推进点(Age Point)的四项口径 —— 页面、AI 挂载齿轮、AI 快照等各处共用这一份。
// 取值与后端 astropy/astrostudy/agepoint.py 的 METHODS / EVENTS / YEAR_DAYS / SPANS 逐个相同(测试逐个比对)。
// 请求键:apMethod / apEvents / apYear / apMaxAge(Java 代理白名单同名登记)。

export const AP_METHODS = [
	{ value: 'koch', label: 'Koch 宫（每宫 6 年，宫内匀速）' },
	{ value: 'equal5', label: '等速（自上升每年 5°）' },
];

export const AP_EVENTS = [
	{ value: 'full', label: '全部点 × 五种相位' },
	{ value: 'conj', label: '只报合七星' },
];

export const AP_YEARS = [
	{ value: 'tropical', label: '回归年（365.2422 日）', days: 365.2422 },
	{ value: 'sidereal', label: '恒星年（365.2564 日）', days: 365.256363 },
];

export const AP_SPANS = [72, 100, 120, 144];

export const AP_DEFAULTS = { apMethod: 'koch', apEvents: 'full', apYear: 'tropical', apMaxAge: 72 };

const valuesOf = (list) => list.map((o) => o.value);
const labelIn = (list, v) => { const hit = list.find((o) => o.value === v); return hit ? hit.label : `${v}`; };

// 只认合法值,其余回出厂值(与后端 normalize 同律)
export function normalizeApSettings(opts){
	const o = opts || {};
	const span = Number(o.apMaxAge);
	return {
		apMethod: valuesOf(AP_METHODS).indexOf(o.apMethod) >= 0 ? o.apMethod : AP_DEFAULTS.apMethod,
		apEvents: valuesOf(AP_EVENTS).indexOf(o.apEvents) >= 0 ? o.apEvents : AP_DEFAULTS.apEvents,
		apYear: valuesOf(AP_YEARS).indexOf(o.apYear) >= 0 ? o.apYear : AP_DEFAULTS.apYear,
		apMaxAge: AP_SPANS.indexOf(span) >= 0 ? span : AP_DEFAULTS.apMaxAge,
	};
}

// 请求体只带与出厂值不同的键:缺省请求与旧请求逐字节相同(缓存键不变)
export function apRequestParams(opts){
	const n = normalizeApSettings(opts);
	const out = {};
	Object.keys(AP_DEFAULTS).forEach((k) => { if(n[k] !== AP_DEFAULTS[k]){ out[k] = n[k]; } });
	return out;
}

export function apSettingsLine(opts){
	const n = normalizeApSettings(opts);
	return `推进方式=${labelIn(AP_METHODS, n.apMethod)}、事件=${labelIn(AP_EVENTS, n.apEvents)}、年长=${labelIn(AP_YEARS, n.apYear)}、年限=${n.apMaxAge} 岁`;
}

// 事件相位写法:合 / 六合 / 四分 / 三分 / 冲,六合四分三分带左右
const ASPECT_TXT = { 0: '合', 60: '六合', 90: '四分', 120: '三分', 180: '冲' };
export function apAspectText(aspect, side){
	const a = ASPECT_TXT[Number(aspect)] || `${aspect}°`;
	if(side === 'D'){ return `${a}·右`; }
	if(side === 'S'){ return `${a}·左`; }
	return a;
}
