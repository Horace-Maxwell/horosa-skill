import moment from 'moment';
// 民用历日期 ⇄ moment 单一来源(全年份域)。
//
// 两个历法口径在这里收口:命盘上的日期是民用历(1582-10-15 以前儒略历、显示年无 0 年,年份 1–5 位带符号),
// moment 恒按外推格里历 + 天文年。所以先把民用日期换成儒略日序数,再取「同一天」的外推格里历年月日交给 moment ——
// 得到的 moment 表示正确的那一天,按天加减、求差、与「此刻」比都对(跨 1582、跨公元元年也对);
// **它的 format 不是民用历标签**,要显示 / 拼请求串一律经 civilDateOfMoment(1582-10-15 以后两者逐字相同,现代日期零变化)。
//
// 不许用 moment(串, 'YYYY-MM-DD …') 读命盘日期:moment 的格式解析把公元前 '-300-03-10' 读成公元 300 年、
// 两位年 '50-03-10' 读成 2050 年、五位年 '12000-01-01' 截成 1200 年,编译运行都不报错(护栏 momentOfFieldValueGuard)。
import { gregJdnOfYmd, gregYmdOfJdn, civilJdnOfYmd, civilYmdExists } from './civilCalendar.js';
import { civilDateStrOfJdn } from '../bazi/dateStrSafe.js';
import { parseDateTimeParts } from './dateTimeParse.js';
import { zoneOffsetMinutesOf } from './zoneOffset.js';

/** 儒略日序数(+ 钟面时分秒)→ 本地钟面的 moment(表示民用历那一天);jdn 不是数 → invalid。 */
export function momentOfCivilJdn(jdn, hour, minute, second){
	if(!Number.isFinite(jdn)){ return moment.invalid(); }
	const g = gregYmdOfJdn(jdn);
	const mm = moment({ year: g.astroYear, month: g.month - 1, date: g.day, hour: Number(hour || 0), minute: Number(minute || 0), second: Number(second || 0) });
	return mm.isValid() ? mm : moment.invalid();
}

/** moment(外推格里历)所在那一天 → 儒略日序数。 */
export function civilJdnOfMoment(m){
	if(!m || typeof m.year !== 'function' || (typeof m.isValid === 'function' && !m.isValid())){ return NaN; }
	return gregJdnOfYmd(m.year(), m.month() + 1, m.date());
}

/** moment 所在那一天 → 民用历日期串('YYYY-MM-DD',sep 可换 '/';公元前前导负号、历史纪年)。 */
export function civilDateOfMoment(m, sep){
	const j = civilJdnOfMoment(m);
	return Number.isFinite(j) ? civilDateStrOfJdn(j, sep) : 'Invalid date';
}

/** 民用日期时刻串('YYYY-MM-DD HH:mm:ss' / 斜杠 / 负年 / 不补零 / 五位年 / 只有日期)→ 本地钟面 moment;认不出 → invalid。
 *  替代 moment(串, 'YYYY-MM-DD HH:mm:ss')。1582-10-15 以后与 moment(串, 格式) 逐值相同。 */
export function momentOfCivilDateTimeStr(str){
	const p = typeof str === 'string' ? parseDateTimeParts(str.trim()) : null;
	if(!p || p.year === 0){ return momentOfCivilJdn(NaN); }
	return momentOfCivilJdn(civilJdnOfYmd(p.year, p.month, p.day), p.hour, p.minute, p.second);
}

// 时区串 → 分钟:单一来源在 zoneOffset.js(这里转出,老调用方照旧从 civilMoment 取)
export { zoneOffsetMinutesOf };

/** 民用日期时刻串 + 时区 → 固定在该时区偏移上的 moment(表示民用历那一刻;显示字面 = 该地钟面)。
 *  UTC 构造再换偏移:不经本机时区,本机夏令时空档不会把钟面挪一小时。日子不存在(2 月 30 日、儒略历 1500-02-29 之外的格里独有日)→ invalid。
 *  时区认不出 → 退回本机钟面(momentOfCivilDateTimeStr)。1582-10-15 以后与 moment.parseZone(串 + 时区, 'YYYY-MM-DD HH:mm:ss Z') 逐值相同。 */
export function zonedMomentOfCivilDateTimeStr(str, zone){
	const p = typeof str === 'string' ? parseDateTimeParts(str.trim()) : null;
	if(!p || p.year === 0 || !civilYmdExists(p.year, p.month, p.day)){ return moment.invalid(); }
	const zoneMin = zoneOffsetMinutesOf(zone);
	if(zoneMin === null){ return momentOfCivilDateTimeStr(str); }
	const g = gregYmdOfJdn(civilJdnOfYmd(p.year, p.month, p.day));
	const m = moment.utc({ year: g.astroYear, month: g.month - 1, date: g.day, hour: Number(p.hour || 0), minute: Number(p.minute || 0), second: Number(p.second || 0) });
	return m.isValid() ? m.utcOffset(zoneMin, true) : moment.invalid();
}

/** 盘对象的出生时刻,落在出生时区上(params.birth,或 params.date + params.time;params.zone,缺省 defaultZone)→ moment;
 *  缺 / 认不出 → invalid。按出生地钟面推时间线、与「此刻」比先后的助手用它(不各写一份 parseBirth)。 */
export function zonedBirthMomentOfChart(chartObj, defaultZone = '+08:00'){
	const p = (chartObj && chartObj.params) ? chartObj.params : {};
	const birth = `${p.birth || ''}`.trim();
	const str = birth || `${`${p.date || ''}`.trim()} ${`${p.time || ''}`.trim()}`.trim();
	const zone = (p.zone === undefined || p.zone === null || `${p.zone}`.trim() === '') ? defaultZone : p.zone;
	return zonedMomentOfCivilDateTimeStr(str, zone);
}

/** 盘对象的出生时刻(params.birth)→ moment;缺 / 认不出 → null。年龄 / 时间线类助手共用(不各写一份 parseBirth)。 */
export function birthMomentOfChart(chartObj){
	const p = (chartObj && chartObj.params) ? chartObj.params : {};
	const birth = `${p.birth || ''}`.trim();
	if(!birth){ return null; }
	const m = momentOfCivilDateTimeStr(birth);
	return m.isValid() ? m : null;
}

/** 出生 moment 往后数 days 天(四舍五入到整天)那一天的民用历日期串;birth 缺 → ''。 */
export function civilDateAfterDays(birth, days){
	if(!birth || (typeof birth.isValid === 'function' && !birth.isValid())){ return ''; }
	const j = civilJdnOfMoment(birth);
	return Number.isFinite(j) ? civilDateStrOfJdn(j + Math.round(Number(days))) : '';
}

/** 民用日期(时刻)串 → 「标签 moment」:年月日时分秒原样装进 moment(不换历;年 = 历史纪年的数),
 *  只给日期控件显示、再原样 format('YYYY/MM/DD') 回写同一标签用(本仓日期控件的值都是这种标签 moment)。
 *  算天数差、与此刻比先后一律用 momentOfCivilDateTimeStr(那是真实那一天)。替代 moment(串) 交给引擎解析。认不出 / 年为 0 → invalid;
 *  moment 按外推格里历校验,儒略独有的日子(1500-02-29 这类)装不进标签 moment,同样 invalid(调用方据此跳过,不静默挪日)。 */
export function labelMomentOfCivilDateStr(str){
	const p = typeof str === 'string' ? parseDateTimeParts(str.trim()) : null;
	if(!p || p.year === 0){ return moment.invalid(); }
	const m = moment({ year: p.year, month: p.month - 1, date: p.day, hour: p.hour, minute: p.minute, second: p.second });
	return m.isValid() ? m : moment.invalid();
}

/** 标签 moment 往后数 n 个月(显示年无 0 年:公元前 1 年 12 月的下一个月是公元 1 年 1 月)。 */
export function addLabelMonths(m, n){
	const k = Math.trunc(Number(n));
	if(!m || (typeof m.isValid === 'function' && !m.isValid()) || !Number.isFinite(k)){ return m; }
	const y = m.year();
	const astro = y < 0 ? y + 1 : y;
	const total = astro * 12 + m.month() + k;
	const ny = Math.floor(total / 12);
	const out = m.clone();
	out.date(1);
	out.year(ny <= 0 ? ny - 1 : ny);
	out.month(total - ny * 12);
	const last = out.daysInMonth();
	out.date(Math.min(m.date(), last));
	return out;
}
