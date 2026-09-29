import { Solar } from 'lunar-javascript';

// lunar-javascript 的节气表与农历表按北京时间(UTC+8)编算。非东八区拿当地钟表去比交节,交节在当地钟表上偏「8 − 时区」小时;
// 凡要拿当地时刻 / 日期去比节气的地方,先用这里的工具在北京时间与当地钟表之间折算。东八区平移量为 0 → 逐字节不变。

// 时区串(+08:00 / -05:00 / +0530 / 数字小时)→ 小时;缺时区按东八区。
export function parseZoneHours(zone){
	if(zone === undefined || zone === null || zone === ''){
		return 8;
	}
	if(typeof zone === 'number'){
		return zone;
	}
	const text = `${zone}`;
	const match = text.match(/^([+-]?)(\d{1,2})(?::?(\d{2}))?/);
	if(match){
		const sign = match[1] === '-' ? -1 : 1;
		const hour = Number(match[2]);
		const minute = Number(match[3] || 0);
		return sign * (hour + minute / 60);
	}
	const n = Number(text);
	return Number.isFinite(n) ? n : 8;
}

// 当地钟表 → 北京时间要加的分钟数(北京时间 → 当地钟表则减去它);东八区与缺时区为 0。
export function bjShiftMinutes(zone){
	const h = parseZoneHours(zone);
	return Number.isFinite(h) ? Math.round((8 - h) * 60) : 0;
}

// 按 lunar-javascript 自己的历法(1582 年前儒略历)平移分钟:日期走 Solar.next,时分秒整数进退,不经浮点儒略日。
export function shiftSolarMinutes(solar, minutes){
	let secs = solar.getHour() * 3600 + solar.getMinute() * 60 + solar.getSecond() + minutes * 60;
	const dayShift = Math.floor(secs / 86400);
	secs -= dayShift * 86400;
	const d = dayShift === 0 ? solar : solar.next(dayShift);
	return Solar.fromYmdHms(d.getYear(), d.getMonth(), d.getDay(), Math.floor(secs / 3600), Math.floor((secs % 3600) / 60), secs % 60);
}
