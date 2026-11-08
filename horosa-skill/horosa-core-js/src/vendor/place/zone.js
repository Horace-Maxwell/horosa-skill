// AI 助手·时区解析优先级:用户明说 > 按经纬+日期推断(含夏令时) > '+08:00'(回退,必进 assumptions)。
import { resolveGeoZone, ianaTimezoneAt, dstAwareZoneAt } from '../utils/timezone.js';

export const ZONE_PATTERN = /^[+-]\d{2}:\d{2}$/;
// 用户明说的时区可带秒(地方平时 ±HH:MM:SS,与命盘记录同一写法);按经纬度推出来的仍只认 ±HH:MM(推算结果的口径不变)
export const USER_ZONE_PATTERN = /^[+-]\d{2}:\d{2}(:\d{2})?$/;
export const FALLBACK_ZONE = '+08:00';

export function resolveZone({ userZone, gpsLat, gpsLon, dateStr }){
	if(userZone && USER_ZONE_PATTERN.test(`${userZone}`)){
		return { zone: `${userZone}`, source: 'user', iana: null };
	}
	let zone = null;
	let iana = null;
	let advisory = null;
	try{
		if(Number.isFinite(Number(gpsLat)) && Number.isFinite(Number(gpsLon))){
			zone = resolveGeoZone({ gpsLat: Number(gpsLat), gpsLng: Number(gpsLon) }, dateStr || undefined);
			try{ iana = ianaTimezoneAt(Number(gpsLat), Number(gpsLon)) || null; }catch(e){ iana = null; }
			// 中国大陆统一北京时间归并(timezone.js 单点):advisory 透给建档 assumptions 与选点提示
			try{
				const info = dstAwareZoneAt(Number(gpsLat), Number(gpsLon), dateStr || undefined);
				advisory = info && info.advisory ? info.advisory : null;
			}catch(e){ advisory = null; }
		}
	}catch(e){
		zone = null;
	}
	if(zone && ZONE_PATTERN.test(`${zone}`)){
		return advisory ? { zone: `${zone}`, source: 'dst-aware', iana, advisory } : { zone: `${zone}`, source: 'dst-aware', iana };
	}
	return { zone: FALLBACK_ZONE, source: 'fallback', iana: null };
}
