// 起盘 fields(date / time 两个 DateTime 包装)→ 年月日时分秒的拆解,及「YYYY-MM-DD HH:mm[:ss]」文本拆解。
// 太乙 / 金口诀的取时、五兆 / 皇极等页的起盘参数原先各抄一份、逐字相同,收成单一来源。
// 年份走 parseDateParts(BC 安全:'-7040-07-19' 裸 split('-') 会撕成 [NaN,7040,7,19],年 NaN 静默传播)。
import { parseDateParts, formatSignedDate } from '../bazi/dateStrSafe.js';
import { defaultAfter23NewDay, defaultLateZiHourUseNextDay } from '../bazi/dayBoundary.js';

// fields → { year, month, day, hour, minute, second, date, time };缺 date / time 回 null。
export function parseFieldsDateTime(fields){
	if(!fields || !fields.date || !fields.time){
		return null;
	}
	const dateStr = fields.date.value.format('YYYY-MM-DD');
	const timeStr = fields.time.value.format('HH:mm:ss');
	const _dp = parseDateParts(dateStr);
	const d = _dp ? [_dp.year, _dp.month, _dp.day] : [];
	const t = timeStr.split(':').map((item)=>parseInt(item, 10));
	if(d.length < 3 || t.length < 2){
		return null;
	}
	return {
		year: d[0],
		month: d[1],
		day: d[2],
		hour: t[0],
		minute: t[1],
		second: t[2] || 0,
		date: dateStr,
		time: timeStr,
	};
}

// 同上,另带时区与全局日界 / 晚子时缺省(起盘请求参数用);date / time 的值缺也回 null。
export function parseFieldsDateTimeWithDayBoundary(fields){
	if(!fields || !fields.date || !fields.time || !fields.date.value || !fields.time.value){
		return null;
	}
	const dateStr = fields.date.value.format('YYYY-MM-DD');
	const timeStr = fields.time.value.format('HH:mm:ss');
	const _dp = parseDateParts(dateStr);
	const d = _dp ? [_dp.year, _dp.month, _dp.day] : [];
	const t = timeStr.split(':').map((item)=>parseInt(item, 10));
	if(d.length < 3 || t.length < 2){
		return null;
	}
	return {
		year: d[0],
		month: d[1],
		day: d[2],
		hour: t[0],
		minute: t[1],
		second: t[2] || 0,
		date: dateStr,
		time: timeStr,
		zone: fields.zone && fields.zone.value ? fields.zone.value : '',
		after23NewDay: defaultAfter23NewDay(),
		lateZiHourUseNextDay: defaultLateZiHourUseNextDay(),
	};
}

// 'YYYY-MM-DD HH:mm[:ss]'(年可带负号、1–6 位)→ 同形对象;对不上回 null。
export function parseDateTimeText(text){
	const raw = (text === undefined || text === null ? '' : `${text}`).trim();
	const match = raw.match(/^(-?\d{1,6})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?/);
	if(!match){
		return null;
	}
	const year = parseInt(match[1], 10);
	const month = parseInt(match[2], 10);
	const day = parseInt(match[3], 10);
	return {
		year,
		month,
		day,
		hour: parseInt(match[4], 10),
		minute: parseInt(match[5], 10),
		second: parseInt(match[6] || '0', 10),
		// 日期串走带符号年的单源格式(公元前保前导负号、数字部分补足 4 位):此前对带负号的年串直接补零,
		// '-50' 拼成 '0-50'(显示「0-50-07-19」)
		date: formatSignedDate(year, month, day),
		time: `${match[4].padStart(2, '0')}:${match[5].padStart(2, '0')}:${(match[6] || '0').padStart(2, '0')}`,
	};
}
