// 日期字符串安全解析(全年份域公共件)。
//
// 背景:DateTime.format('YYYY-MM-DD') 对公元前输出带前导负号的年('-7040-07-19'),
// 下游 `split('-')` 首元素为空 → 年=NaN/0、月=100、日错位;五位年在 `substr(0,4)` 类
// 截半('16799'→'1679')。本件是唯一正确解析真源:负号与位数全域安全。
// 口径:天文年连续(BC1=0? 否——本仓 ad/year 体系 BC1 表示为 -1,无 0 年;
// parseDateParts 返回的 year 即带符号"显示年"(-7040 表示公元前 7040)。

/** 'YYYY-MM-DD'|'-YYYY-MM-DD'|'YYYY/MM/DD'|含时间尾巴 → {year(带符号),month,day} 或 null。 */
export function parseDateParts(str){
	if(str === undefined || str === null){
		return null;
	}
	const s = String(str).trim().split(' ')[0].replace(/\//g, '-');
	const m = /^(-?)(\d{1,5})-(\d{1,2})-(\d{1,2})$/.exec(s);
	if(!m){
		return null;
	}
	const year = (m[1] === '-' ? -1 : 1) * parseInt(m[2], 10);
	const month = parseInt(m[3], 10);
	const day = parseInt(m[4], 10);
	if(!Number.isFinite(year) || month < 1 || month > 12 || day < 1 || day > 31){
		return null;
	}
	return { year, month, day };
}

/** 带符号年 → 'YYYY-MM-DD'(BC 输出前导负号;不足 4 位补零,5 位原样)。 */
export function formatSignedDate(year, month, day){
	const y = Math.abs(year);
	const ys = (year < 0 ? '-' : '') + String(y).padStart(4, '0');
	return `${ys}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

/** 从日期串安全取带符号年(替代 substr(0,4)/slice(0,4)/parseInt(split('-')[0]) 全家)。 */
export function parseYearFromDateStr(str){
	const p = parseDateParts(str);
	return p ? p.year : NaN;
}

// 「显示年」算术(无公元 0 年:公元前 1 年之后即公元 1 年)。直接 y + n / b − a 在跨纪元时多出一个不存在的 0 年
// (公元前出生、行运跨到公元的盘:流年表出现「0 年」、其后公元年份整体错一年、按年份定位流年错一格)。
const toAstroYear = (y)=>(y < 0 ? y + 1 : y);
const fromAstroYear = (a)=>(a <= 0 ? a - 1 : a);

/** 显示年 year 往后(n<0 往前)数 n 年 → 显示年。 */
export function addDisplayYears(year, n){
	const y = Number(year);
	const k = Number(n);
	if(!Number.isFinite(y) || !Number.isFinite(k)){
		return NaN;
	}
	return fromAstroYear(toAstroYear(y) + k);
}

/** 显示年 a 到 b 相隔的年数(b − a,跨纪元不多算)。 */
export function displayYearDiff(a, b){
	const x = Number(a);
	const y = Number(b);
	if(!Number.isFinite(x) || !Number.isFinite(y)){
		return NaN;
	}
	return toAstroYear(y) - toAstroYear(x);
}

// ── 民用历法 ⇄ 儒略日序数(JDN,整数,正午起算的日序;与 DateTime.getOnlyDateNum / Python civil_calendar 同口径)──
// 民用历:1582-10-15 起格里历,此前儒略历(1582-10-04 的次日是 10-15);年份按显示年(公元前 1 年 = -1,无 0 年)。
// 凡「两个日期隔几天 / 几年」「某日往后数 N 天是哪天」一律在这条轴上算,不经 JS Date / moment(二者恒按外推格里历 + 天文年)。

// 整数日序与民用历换算的实现只有一份:utils/civilCalendar.js(与计算服务 civil_calendar 逐位同口径,用例表两侧同读);
// 这里转出给按日期串取用的老调用方,新代码直接从 civilCalendar 引。
import { civilJdnOfYmd, civilYmdOfJdn, gregJdnOfYmd, civilWallMs, civilYmdExists, civilPartsFromWallMs } from '../utils/civilCalendar.js';
import { parseDateTimeParts, parseDateTimeMs } from '../utils/dateTimeParse.js';
export { gregJdnOfYmd, civilJdnOfYmd, gregYmdOfJdn, civilYmdOfJdn } from '../utils/civilCalendar.js';

/** 日期串('YYYY-MM-DD' / '-YYYY/MM/DD' / 带时间尾巴)→ JDN;解析不了返回 NaN。 */
export function civilJdnOfDateStr(str){
	const p = parseDateParts(str);
	return p ? civilJdnOfYmd(p.year, p.month, p.day) : NaN;
}

/** JDN → 民用日期串(formatSignedDate 同形;sep 缺省 '-')。 */
export function civilDateStrOfJdn(jdn, sep){
	const p = civilYmdOfJdn(jdn);
	const s = formatSignedDate(p.year, p.month, p.day);
	return sep && sep !== '-' ? s.replace(/(\d)-/g, `$1${sep}`) : s;
}

/** 时间轴刻度标签:与前一刻度不同年 → 'YYYY-MM'(公元前前导负号、1–5 位年),同年 → 'MM-DD'。
 *  按日期串解析取年月日,不按「前 4 位是年」切片(公元前 / 五位年会切错位)。不可解析时原样返回。 */
export function dateAxisTickLabel(cur, prev){
	const c = parseDateParts(cur);
	if(!c){
		return `${cur}`;
	}
	const p = prev ? parseDateParts(prev) : null;
	const full = formatSignedDate(c.year, c.month, c.day);
	return (!p || p.year !== c.year) ? full.slice(0, full.lastIndexOf('-')) : full.slice(full.lastIndexOf('-') - 2);
}

/** 串首的带符号年('-0300-03-10' → -300、'12000/01/01' → 12000、'1776' → 1776);替代 slice(0, 4) 取年。取不到返回 NaN。 */
export function leadingYearOf(str){
	const m = /^\s*(-?\d{1,5})(?!\d)/.exec(`${str === undefined || str === null ? '' : str}`);
	return m ? parseInt(m[1], 10) : NaN;
}

/** 日期串 → 'YYYY-MM'(formatSignedDate 同形的年月前缀;替代 slice(0, 7))。不可解析时返回 ''。 */
export function yearMonthKey(str){
	const p = parseDateParts(str);
	if(!p){
		return '';
	}
	const s = formatSignedDate(p.year, p.month, p.day);
	return s.slice(0, s.lastIndexOf('-'));
}

/** 日期串 → 'MM-DD'(替代 slice(5) / slice(5, 10))。不可解析时原样返回。 */
export function monthDayLabel(str){
	const p = parseDateParts(str);
	return p ? `${String(p.month).padStart(2, '0')}-${String(p.day).padStart(2, '0')}` : `${str === undefined || str === null ? '' : str}`;
}

// ── 日期串取段 / 换分隔符 / 紧凑日期键(替代 slice(0, 10)、replace(/-/g, '/')、replace(/-/g, '') 全家)──
// 年份是带符号的 1–6 位数:按位置切会把公元前 / 五位年切错位,把所有 '-' 换掉会连公元前的前导负号一起换掉
// ('-0300-03-10' → '/0300/03/10' 或 '03000310',公元前 300 年与公元 300 年折叠成同一个日子)。

const DATE_HEAD_RE = /^\s*([+-]?\d{1,6}[-/]\d{1,2}[-/]\d{1,2})/;

/** 日期时刻串的日期段:'YYYY-MM-DD HH:mm:ss' / ISO 'YYYY-MM-DDTHH:mm…' / '-0300/03/10 …' → 日期段原样;认不出时退回前 10 个字符(旧口径)。 */
export function datePartOf(str){
	const s = `${str === undefined || str === null ? '' : str}`;
	const m = DATE_HEAD_RE.exec(s);
	return m ? m[1] : s.slice(0, 10);
}

/** 日期分隔符 '-' → '/',只换数字之间的那个(公元前前导负号保留);时刻段不受影响。 */
export function toSlashDate(str){
	return `${str === undefined || str === null ? '' : str}`.replace(/(\d)-(?=\d)/g, '$1/');
}

/** 带符号年月日 → 紧凑日期键:公元 1000–9999 年与旧写法 'YYYYMMDD' 逐字相同;公元前前导负号、年补到 4 位、五位年原样。 */
export function dateKeyOf(year, month, day){
	const y = Number(year);
	return `${y < 0 ? '-' : ''}${String(Math.abs(y)).padStart(4, '0')}${String(Number(month)).padStart(2, '0')}${String(Number(day)).padStart(2, '0')}`;
}

/** 日期串 → 紧凑日期键(dateKeyOf);认不出时返回 ''。 */
export function dateKeyOfStr(str){
	const p = parseDateParts(datePartOf(str));
	return p ? dateKeyOf(p.year, p.month, p.day) : '';
}

/** 紧凑日期键 → {year(带符号), month, day};认不出返回 null。 */
export function parseDateKey(key){
	const m = /^(-?)(\d{4,6})(\d{2})(\d{2})$/.exec(`${key === undefined || key === null ? '' : key}`.trim());
	if(!m){
		return null;
	}
	const year = (m[1] === '-' ? -1 : 1) * parseInt(m[2], 10);
	const month = parseInt(m[3], 10);
	const day = parseInt(m[4], 10);
	if(year === 0 || month < 1 || month > 12 || day < 1 || day > 31){
		return null;
	}
	return { year, month, day };
}

// 日序数 = 民用历墙钟毫秒 / 一日(civilCalendar 单源:1583 年起与 Math.floor(Date.UTC(…) / 86400000) 逐值相同)
const DAY_MS = 86400000;
const EPOCH_JDN = civilJdnOfYmd(1970, 1, 1);

/** 紧凑日期键 → 自 1970-01-01 起的民用日序数(1582 以前儒略历、公元前历史纪年);认不出返回 NaN。 */
export function dayNumOfDateKey(key){
	const p = parseDateKey(key);
	return p ? civilWallMs(p.year, p.month, p.day, 0, 0, 0) / DAY_MS : NaN;
}

/** 民用日序数 → 紧凑日期键(dayNumOfDateKey 的反函数)。 */
export function dateKeyOfDayNum(n){
	const p = civilYmdOfJdn(Math.floor(Number(n)) + EPOCH_JDN);
	return dateKeyOf(p.year, p.month, p.day);
}

/** 带符号显示年往后数 n 年的同月同日(无公元 0 年);目标年没有 2 月 29 日时落到 3 月 1 日(与 Date#setFullYear 同)。返回日期串。 */
export function addCivilYears(str, n){
	const p = parseDateParts(datePartOf(str));
	if(!p || !Number.isFinite(Number(n))){
		return `${str === undefined || str === null ? '' : str}`;
	}
	const y = addDisplayYears(p.year, Number(n));
	// 目标年有没有 2 月 29 日:由 civilCalendar 往返判(民用历闰法只有一份)
	if(p.month === 2 && p.day === 29 && civilYmdOfJdn(civilJdnOfYmd(y, 2, 29)).month !== 2){
		return formatSignedDate(y, 3, 1);
	}
	return formatSignedDate(y, p.month, p.day);
}

/** 毫秒时刻(UTC)所在那一天 → 民用历日期串(替代 new Date(ms).toISOString().slice(0, 10);现代日期逐字相同)。 */
export function civilDateStrOfMs(ms){
	const t = Number(ms);
	return Number.isFinite(t) ? civilDateStrOfJdn(Math.floor(t / DAY_MS) + EPOCH_JDN) : '';
}

/** 毫秒时刻 + 该时刻日期标签 → 按民用历修正后的毫秒:引擎把日期标签按外推格里历 + 天文年解释,
 *  这里补上「民用历同一标签」与之相差的整天数(1582-10-15 以后为 0,现代日期零变化)。 */
export function civilShiftMs(ms, str){
	const p = parseDateParts(datePartOf(str));
	if(!p || !Number.isFinite(Number(ms))){
		return Number(ms);
	}
	return Number(ms) + (civilJdnOfYmd(p.year, p.month, p.day) - gregJdnOfYmd(p.year, p.month, p.day)) * DAY_MS;
}

/** 民用日期时刻串(命盘 / 事盘上的日期,年份按历史纪年)→ 墙钟毫秒(civilCalendar.civilWallMs 同一条轴)。
 *  全程不经本地 Date:结果与系统时区无关(东八区与美东逐值相同),与 civilDateStrOfMs 配对往返原样。
 *  认的写法同 dateTimeParse.parseDateTimeParts(负年 / 1–6 位年 / 斜杠 / 不补零 / 带时刻);串里写了时区也按钟面读。
 *  年为 0、日期不存在(1582-10-05 … 10-14、平年 2 月 29 日)或认不出 → NaN。
 *  分工:dateTimeParse.parseDateTimeMs = 机器时间戳 / 本地时刻(年按天文年,与 ECMAScript 同);
 *  命盘日期算术(隔几天、往后数 N 天、年龄)一律走本函数或 civilJdnOfDateStr,不拿 parseDateTimeMs 的结果再修正。 */
export function civilWallMsOfStr(str){
	if(typeof str !== 'string'){ return NaN; }
	const p = parseDateTimeParts(str);
	if(!p || p.year === 0 || !civilYmdExists(p.year, p.month, p.day)){ return NaN; }
	return civilWallMs(p.year, p.month, p.day, p.hour, p.minute, p.second) + (p.ms || 0);
}

/** 两个民用日期串相隔的整天数(b − a;日期段经 datePartOf 取,1582 以前儒略历、公元前历史纪年)。认不出 → NaN。
 *  替代「两个 parseDateTimeMs 相减 ÷ 一日」:后者按外推格里历 + 天文年,跨 1582 差 10 天、公元前再差一年。 */
export function civilDayDiffOfStr(a, b){
	return civilJdnOfDateStr(datePartOf(b)) - civilJdnOfDateStr(datePartOf(a));
}

/** 民用日期时刻串 → 真实时刻毫秒(与 Date.now() 比先后 / 求年龄用):按 parseDateTimeMs 的口径读钟面
 *  (严格 ISO 纯日期 = UTC 0 点,其余 = 本地钟面),再补上民用历与外推格里历同一标签之差(1582 以前儒略历、
 *  公元前历史纪年;1582-10-15 以后为 0,现代逐值不变)。**不拿它取日期标签**(东经时区本地 0 点落在 UTC 前一日):
 *  日期算术 / 标签走 civilWallMsOfStr + civilDateStrOfMs。认不出 → NaN。 */
export function civilInstantMsOfStr(str){
	const s = `${str === undefined || str === null ? '' : str}`;
	return civilShiftMs(parseDateTimeMs(s), s);
}

/** 墙钟毫秒 → 民用日期时刻串 'YYYY-MM-DD HH:mm:ss'(formatSignedDate 同形;civilWallMsOfStr 的反函数)。不是有限数 → ''。 */
export function civilDateTimeStrOfWallMs(ms){
	const p = civilPartsFromWallMs(ms);
	if(!p){ return ''; }
	const pad = (n)=>String(n).padStart(2, '0');
	return `${formatSignedDate(p.year, p.month, p.day)} ${pad(p.hour)}:${pad(p.minute)}:${pad(p.second)}`;
}

/** 民用日期时刻串往后(负数往前)挪 deltaMs 毫秒 → 'YYYY-MM-DD HH:mm:ss'。在墙钟轴上挪(与系统时区 / 夏令时无关,
 *  1582 以前儒略历、公元前历史纪年)。替代「parseLocalDateTimeMs + 毫秒 → new Date → getFullYear / getMonth / getDate 拼串」。认不出 → ''。 */
export function civilShiftDateTimeStr(str, deltaMs){
	const ms = civilWallMsOfStr(`${str === undefined || str === null ? '' : str}`.trim());
	return Number.isFinite(ms) && Number.isFinite(Number(deltaMs)) ? civilDateTimeStrOfWallMs(ms + Number(deltaMs)) : '';
}
