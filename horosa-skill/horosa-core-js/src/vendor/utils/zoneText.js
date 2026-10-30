// 时区串 → 规范「±HH:MM」单一来源(精确历法桥与三式页同用;原先三式页有一份逐字相同的副本)。
// 认 ±HH[:MM] / UTC·GMT±HH[:MM] / 东西 N[:MM] 区 / 数字小时;认不出按 fallback,再不行东八区。
// 与 utils/zoneOffset(折成分钟、认不出 null)口径不同:这里多认 UTC·GMT 与东西区写法、且总给出一个时区 ——
// 两者在规范写法上逐值一致(见 zoneOffsetParity.test.js)。
function safe(v, d = ''){
	return v === undefined || v === null ? d : `${v}`;
}

export function parseZoneHour(zone){
	const text = safe(zone).trim();
	if(!text){
		return null;
	}
	const mStd = text.match(/^([+-])(\d{1,2})(?::?(\d{2}))?$/);
	if(mStd){
		const sign = mStd[1] === '-' ? -1 : 1;
		const hh = parseInt(mStd[2], 10);
		const mm = parseInt(mStd[3] || '0', 10);
		if(!Number.isNaN(hh) && !Number.isNaN(mm)){
			return sign * (hh + mm / 60);
		}
	}
	const mUtc = text.match(/^(?:UTC|GMT)\s*([+-])(\d{1,2})(?::?(\d{2}))?$/i);
	if(mUtc){
		const sign = mUtc[1] === '-' ? -1 : 1;
		const hh = parseInt(mUtc[2], 10);
		const mm = parseInt(mUtc[3] || '0', 10);
		if(!Number.isNaN(hh) && !Number.isNaN(mm)){
			return sign * (hh + mm / 60);
		}
	}
	const mCn = text.match(/^([东西])\s*(\d{1,2})(?:[:：]?(\d{1,2}))?\s*区?$/);
	if(mCn){
		const sign = mCn[1] === '西' ? -1 : 1;
		const hh = parseInt(mCn[2], 10);
		const mm = parseInt(mCn[3] || '0', 10);
		if(!Number.isNaN(hh) && !Number.isNaN(mm)){
			return sign * (hh + mm / 60);
		}
	}
	const numeric = Number(text);
	if(Number.isFinite(numeric)){
		return numeric;
	}
	return null;
}

export function formatZoneHour(hour){
	if(hour === null || hour === undefined || Number.isNaN(hour)){
		return '+08:00';
	}
	const sign = hour < 0 ? '-' : '+';
	const abs = Math.abs(hour);
	let hh = Math.floor(abs);
	let mm = Math.round((abs - hh) * 60);
	if(mm >= 60){
		hh += 1;
		mm -= 60;
	}
	return `${sign}${`${hh}`.padStart(2, '0')}:${`${mm}`.padStart(2, '0')}`;
}

export function normalizeZone(zone, fallback = '+08:00'){
	const parsed = parseZoneHour(zone);
	if(parsed !== null && !Number.isNaN(parsed)){
		return formatZoneHour(parsed);
	}
	const fb = parseZoneHour(fallback);
	return formatZoneHour((fb !== null && !Number.isNaN(fb)) ? fb : 8);
}
