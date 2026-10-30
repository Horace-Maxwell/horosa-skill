// 日期时刻串 → 毫秒(全站单一出处)。按数字拆分、自己换算,不经引擎的 Date.parse / new Date(串)。
//
// 为什么不用引擎:ISO 8601 以外的写法(空格分隔「YYYY-MM-DD HH:mm:ss」、斜杠、只换了一半的「YYYY/MM-DD」、
// 负年「-0500-03-04」、不补零)怎么解析由各引擎自定 —— V8(jest / node)几乎都认,WebKit(桌面壳)对「YYYY/MM-DD …」
// 回 NaN,旧版 JavaScriptCore 对空格分隔的本地时刻历来不稳。用引擎解析 = 测试绿、真机坏。
// 源码合同 dateTimeParseSingleSource.test.js:src 下 Date.parse( 只许出现在本文件,new Date(…) 不许直接吃字符串。
//
// 认的写法(前后空白忽略):
//   年:1–6 位数字,可带 + / - 号(扩展年「+002026」「-000500」与「-0500」都认;年份 0–99 不按 19xx 换算)
//   日期:年-月-日 / 年/月/日(月日 1–2 位;分隔符可混用)、年-月、四位年
//   时刻:与日期之间用 T 或空白(可多个);时:分[:秒[.小数]];24:00(:00) 认作次日 0 点
//   时区:Z / ±HH:MM / ±HHMM / ±HH(写了就按它;没写见下)
// 没写时区时的口径(两个入口不同):
//   parseDateTimeMs —— 与 ECMAScript 规定一致:严格 ISO 的纯日期(「YYYY-MM-DD」「YYYY-MM」「YYYY」)按 UTC 0 点,其余(带时刻 / 斜杠 / 不补零)按本地钟面。
//                      用于机器写的时间戳(toISOString)与各页沿用 ISO 纯日期的日期轴,结果与 V8 原先的 Date.parse 逐值相同。
//   parseLocalDateTimeMs —— 一律按本地钟面(纯日期 = 本地 0 点)。用于记录上的本地时刻(出生 / 起课 / 更新时间 / 删除时间)。
// 月 / 日 / 时 / 分 / 秒越界(13 月、2 月 30 日、4 月 31 日、25 点、60 分)= 认不出(NaN),不滚到下一个月;2 月 29 日不论哪年都认(儒略历闰年)。
// 数字原样返回(有限才算);Date 取 getTime()(valueOf 回数的对象同);其余一律 NaN(调用方照旧用 Number.isFinite / `|| 0` 判)。

const DATE_TIME_RE = /^([+-]?\d{1,6})(?:([-/])(\d{1,2})(?:([-/])(\d{1,2}))?)?(?:(?:T|\s+)(\d{1,2}):(\d{1,2})(?::(\d{1,2})(?:[.,](\d+))?)?)?\s*(Z|z|[+-]\d{2}(?::?\d{2})?)?$/;

function daysInMonth(y, m){
	const d = new Date(0);
	d.setUTCFullYear(y, m, 0);
	return d.getUTCDate();
}

// 拆出各段(认不出 = null)。返回 { year, month, day, hour, minute, second, ms, hasTime, isoDateOnly, offsetMin }
// offsetMin:写了时区才有(UTC 偏移分钟数,东正西负),没写为 null。
export function parseDateTimeParts(text){
	if(typeof text !== 'string'){ return null; }
	const s = text.trim();
	if(!s){ return null; }
	const m = DATE_TIME_RE.exec(s);
	if(!m){ return null; }
	const [, ys, sep1, ms1, sep2, ds, hs, mis, ss, frac, zone] = m;
	// 只有年:只认四位年或带符号的扩展年(防「5」「1792857600000」这类数字串被当成年份)
	if(sep1 === undefined && !/^(?:\d{4}|[+-]\d{4,6})$/.test(ys)){ return null; }
	const year = parseInt(ys, 10);
	if(!Number.isFinite(year)){ return null; }
	const month = ms1 !== undefined ? parseInt(ms1, 10) : 1;
	const day = ds !== undefined ? parseInt(ds, 10) : 1;
	if(month < 1 || month > 12){ return null; }
	// 2 月 29 日一律认(儒略历每四年一闰,1582 年前的 1500-02-29 这类是真日期;换算毫秒时按公历外推落到 3 月 1 日,与 V8 一致)
	if(day < 1 || (day > daysInMonth(year, month) && !(month === 2 && day === 29))){ return null; }
	const hasTime = hs !== undefined;
	const hour = hasTime ? parseInt(hs, 10) : 0;
	const minute = hasTime ? parseInt(mis, 10) : 0;
	const second = ss !== undefined ? parseInt(ss, 10) : 0;
	const msec = frac !== undefined ? parseInt(`${frac}00`.slice(0, 3), 10) : 0;
	if(hour > 24 || minute > 59 || second > 59){ return null; }
	if(hour === 24 && (minute || second || msec)){ return null; }
	let offsetMin = null;
	if(zone){
		if(zone === 'Z' || zone === 'z'){
			offsetMin = 0;
		}else{
			const zm = /^([+-])(\d{2}):?(\d{2})?$/.exec(zone);
			const zh = parseInt(zm[2], 10);
			const zmin = zm[3] !== undefined ? parseInt(zm[3], 10) : 0;
			if(zh > 23 || zmin > 59){ return null; }
			offsetMin = (zm[1] === '-' ? -1 : 1) * (zh * 60 + zmin);
		}
	}
	// 严格 ISO 的纯日期:「YYYY」「YYYY-MM」「YYYY-MM-DD」(四位或带号扩展年、两位月日、只用「-」)
	const isoDateOnly = !hasTime && sep1 !== '/' && sep2 !== '/'
		&& /^(?:\d{4}|[+-]\d{6})$/.test(ys)
		&& (ms1 === undefined || ms1.length === 2)
		&& (ds === undefined || ds.length === 2);
	return { year, month, day, hour, minute, second, ms: msec, hasTime, isoDateOnly, offsetMin };
}

function partsToMs(p, utc){
	const d = new Date(0);
	if(utc){
		d.setUTCFullYear(p.year, p.month - 1, p.day);
		d.setUTCHours(p.hour, p.minute, p.second, p.ms);
	}else{
		d.setFullYear(p.year, p.month - 1, p.day);
		d.setHours(p.hour, p.minute, p.second, p.ms);
	}
	return d.getTime();
}

function toMs(v, dateOnlyUtc){
	if(typeof v === 'number'){ return Number.isFinite(v) ? v : NaN; }
	if(v instanceof Date){ return v.getTime(); }
	// moment / DateTime 一类(valueOf 回毫秒数)
	if(v && typeof v === 'object' && typeof v.valueOf === 'function'){
		const n = v.valueOf();
		if(typeof n === 'number'){ return Number.isFinite(n) ? n : NaN; }
	}
	const p = parseDateTimeParts(v);
	if(!p){ return NaN; }
	if(p.offsetMin !== null){ return partsToMs(p, true) - p.offsetMin * 60000; }
	return partsToMs(p, dateOnlyUtc && p.isoDateOnly);
}

// 与 ECMAScript 口径一致(严格 ISO 纯日期 = UTC 0 点;其余没写时区 = 本地钟面),引擎无关
export function parseDateTimeMs(v){
	return toMs(v, true);
}

// 本地钟面口径(纯日期 = 本地 0 点):记录上的出生 / 起课 / 更新 / 删除时刻
export function parseLocalDateTimeMs(v){
	return toMs(v, false);
}

// 认不出 = null(给需要 Date 对象的调用方:new Date(串) 的替代)
export function toDateOrNull(v, opts){
	const t = opts && opts.local ? parseLocalDateTimeMs(v) : parseDateTimeMs(v);
	return Number.isFinite(t) ? new Date(t) : null;
}
