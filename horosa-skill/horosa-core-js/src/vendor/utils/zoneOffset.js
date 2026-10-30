// 时区串 → 偏移分钟 单一来源。
// 认三种写法:'±HH[:MM]' / '±HHMM' / '±H'(前后空白忽略);其余按小时数读('5.5' → 330);数字即小时数。认不出 → null。
// 用在「按出生时区落时刻」的地方(大运段界、十年大运出生时刻…)。
// 节气折算北京时间用的 beijingTimeShift.parseZoneHours 另有宽松口径(缺省东八区、前缀匹配),见该文件注释,不走这里。
const ZONE_RE = /^([+-]?)(\d{1,2})(?::?(\d{2}))?$/;

export function zoneOffsetMinutesOf(zone){
	if(zone === undefined || zone === null || zone === ''){ return null; }
	if(typeof zone === 'number'){ return Number.isFinite(zone) ? Math.round(zone * 60) : null; }
	const m = ZONE_RE.exec(`${zone}`.trim());
	if(!m){
		const n = Number(zone);
		return Number.isFinite(n) ? Math.round(n * 60) : null;
	}
	return (m[1] === '-' ? -1 : 1) * (Number(m[2]) * 60 + Number(m[3] || 0));
}
