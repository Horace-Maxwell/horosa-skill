// 事盘起课时刻串的写法判据与解析(单一出处,判据与解析同一个正则、同一次匹配):
// 年可带负号 / 补零,月日用「-」或「/」分隔;日期与时刻之间可以是 T 或空白(可多个),前后空白忽略;时刻可带秒。
// 认得出的写法,解析一定正确:各段越界(13 月、2 月 30 日、25 点、60 分)= 认不出。
// 只有日期没有时刻 = 认得出,按当天 12:00 起课(与载入一直以来的口径一致),载入时另给一条提示。
// 空串 / 缺 / 认不出 = 坏档(没有起课时间):载入按此刻起课并提示、从文件导入时跳过并列出。
import { parseDateTimeParts } from './dateTimeParse.js';

const CASE_DIV_TIME_RE = /^(-?\d{1,6})[-/](\d{1,2})[-/](\d{1,2})(?:(?:T|\s+)(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?$/;
const pad = (n, w)=>String(n).padStart(w, '0');

// → { year, month, day, hour, minute, second, hasTime, canonical } | null
// canonical:「YYYY-MM-DD HH:mm:ss」(负年带 -;只有日期时为 12:00:00)—— 喂给 DateTime.parse 的唯一写法
export function parseCaseDivTimeParts(text){
	if(typeof text !== 'string'){ return null; }
	const m = CASE_DIV_TIME_RE.exec(text.trim());
	if(!m){ return null; }
	const hasTime = m[4] !== undefined;
	// 越界判据走日期单源(按数字拆分,与引擎无关)
	const probe = `${m[1]}-${m[2]}-${m[3]}${hasTime ? ` ${m[4]}:${m[5]}:${m[6] !== undefined ? m[6] : '0'}` : ''}`;
	const p = parseDateTimeParts(probe);
	if(!p || p.hour === 24){ return null; }
	const year = parseInt(m[1], 10);
	const hour = hasTime ? p.hour : 12;
	const minute = hasTime ? p.minute : 0;
	const second = hasTime ? p.second : 0;
	const ys = year < 0 ? `-${pad(-year, 4)}` : pad(year, 4);
	const canonical = `${ys}-${pad(p.month, 2)}-${pad(p.day, 2)} ${pad(hour, 2)}:${pad(minute, 2)}:${pad(second, 2)}`;
	return { year, month: p.month, day: p.day, hour, minute, second, hasTime, canonical };
}

export function isCaseDivTimeText(text){
	return parseCaseDivTimeParts(text) !== null;
}

// 认得出、但只有日期没有时刻(载入按 12:00 起课并提示)
export function caseDivTimeDateOnly(text){
	const p = parseCaseDivTimeParts(text);
	return !!(p && !p.hasTime);
}
