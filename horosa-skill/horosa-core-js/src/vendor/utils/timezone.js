// 时区 / 夏令时(DST)工具
// 成熟方案:经纬度 → IANA 时区名(离线 tz-lookup) + 浏览器原生 Intl 求含夏令时的 UTC 偏移。
// 全程离线、零网络依赖,适配桌面端断网场景。

import { parseDateTimeMs } from './dateTimeParse.js';
import tzLookup from 'tz-lookup';
import { leadingYearOf, datePartOf, civilJdnOfDateStr } from '../bazi/dateStrSafe.js';

// 经纬度 → IANA 时区名(离线 tz-lookup)。无效/越界坐标返回 null。
export function ianaTimezoneAt(lat, lng){
	const la = Number(lat);
	const ln = Number(lng);
	if(!Number.isFinite(la) || !Number.isFinite(ln)){
		return null;
	}
	if(la < -90 || la > 90 || ln < -180 || ln > 180){
		return null;
	}
	// (0,0) 海面无意义,视作未选地点
	if(la === 0 && ln === 0){
		return null;
	}
	try{
		return tzLookup(la, ln);
	}catch(e){
		return null;
	}
}

// IANA tzdb 新版规则先于系统 ICU 落地时的前瞻覆盖表(系统 ICU 跟上后覆盖值与 Intl 一致,自然冗余无害)。
// 每条:zone → [{ since:'YYYY-MM-DD'(当日起恒定), offset:'+HH:mm' }];仅收「永久废除夏令时」类已立法规则。
// 来源:IANA tzdb NEWS 2026b/2026c(实测 macOS WebView ICU 尚未包含,未来日期会差 1 小时)。
const TZ_RULE_OVERRIDES = {
	// 2026c:Alberta 永久 -06(法定 2026-06-18;模型化=取消 2026-11-01 02:00 回落)
	'America/Edmonton': [{ since: '2026-11-01', offset: '-06:00' }],
	// 2026b:British Columbia 永久 -07(模型化=取消 2026-11-01 02:00 回落)
	'America/Vancouver': [{ since: '2026-11-01', offset: '-07:00' }],
	// 2026c:摩洛哥+西撒哈拉 2026-09-20 02:00 起永久 +00
	'Africa/Casablanca': [{ since: '2026-09-20', offset: '+00:00' }],
	'Africa/El_Aaiun': [{ since: '2026-09-20', offset: '+00:00' }],
};

function overrideOffsetFor(zone, dateStr){
	const rules = TZ_RULE_OVERRIDES[zone];
	// 按民用历日序数比先后(年带符号、1–5 位都对;不按字符串比:'12000-…' < '2026-…'、公元前串认不出)
	const jdn = rules ? civilJdnOfDateStr(datePartOf(dateStr || '')) : NaN;
	if(!rules || !Number.isFinite(jdn)){
		return null;
	}
	for(let i = 0; i < rules.length; i++){
		if(jdn >= civilJdnOfDateStr(rules[i].since)){
			return rules[i].offset;
		}
	}
	return null;
}

// IANA 时区 + 日期(YYYY-MM-DD) → 含夏令时的 UTC 偏移字符串 "+HH:mm"。
// 用浏览器原生 Intl(内置完整 IANA tz 历史库,含 1918 等历史夏令时规则),无需任何 tz 数据库依赖;
// 新近立法而 ICU 未及收录的规则走 TZ_RULE_OVERRIDES 前瞻覆盖。
export function offsetForZoneAtDate(zone, dateStr){
	if(!zone || !dateStr){
		return null;
	}
	const ov = overrideOffsetFor(zone, dateStr);
	if(ov){
		return ov;
	}
	try{
		// 取当日正午 UTC 作判定锚点,避开 DST 切换瞬间(凌晨)的歧义
		const d = new Date(parseDateTimeMs(`${dateStr}T12:00:00Z`));
		if(isNaN(d.getTime())){
			return null;
		}
		const parts = new Intl.DateTimeFormat('en-US', {
			timeZone: zone,
			timeZoneName: 'longOffset',
		}).formatToParts(d);
		const tn = parts.find((p) => p.type === 'timeZoneName');
		if(!tn || !tn.value){
			return null;
		}
		const m = /GMT\s*([+-])(\d{1,2})(?::?(\d{2}))?/.exec(tn.value);
		if(!m){
			return /GMT/i.test(tn.value) ? '+00:00' : null; // 纯 "GMT" = UTC
		}
		const sign = m[1];
		const hh = m[2].padStart(2, '0');
		const mm = (m[3] || '00').padStart(2, '0');
		return `${sign}${hh}:${mm}`;
	}catch(e){
		return null;
	}
}

// 偏移字符串 "+HH:mm" → 分钟数(用于比较)。失败返回 null。
function offsetToMinutes(s){
	const m = /([+-])(\d{2}):(\d{2})/.exec(s || '');
	if(!m){
		return null;
	}
	return (m[1] === '-' ? -1 : 1) * (parseInt(m[2], 10) * 60 + parseInt(m[3], 10));
}

// 某时区某日期是否处于夏令时(与同年 1 月 / 7 月偏移对比)。
// 夏令时 = 更靠东(更大)的那个偏移;两者相等 = 该地不实行夏令时。南北半球皆成立。
export function isDstActiveAt(zone, dateStr){
	try{
		const o = offsetForZoneAtDate(zone, dateStr);
		if(!o){
			return false;
		}
		const yr = leadingYearOf(dateStr);
		const oJan = offsetForZoneAtDate(zone, `${yr}-01-15`);
		const oJul = offsetForZoneAtDate(zone, `${yr}-07-15`);
		if(!oJan || !oJul || oJan === oJul){
			return false;
		}
		const cur = offsetToMinutes(o);
		const mx = Math.max(offsetToMinutes(oJan), offsetToMinutes(oJul));
		return cur !== null && cur === mx;
	}catch(e){
		return false;
	}
}

// 中国大陆统一北京时间口径(horosa_tz_cn_unified_v1):IANA 地理时区把新疆划为 Asia/Urumqi(+06:00,
// 民间「新疆时间」),而出生证/户籍/医院记录一律按法定北京时间;选点预览、存档推断、AI 建档三条路径
// 同源于本函数,故在此**只做 IANA 名归并、不写死偏移**:统一时间起点之后 Asia/Urumqi → Asia/Shanghai,
// 偏移仍由 Intl 按日期算(1986–1991 夏令时照常得 +09:00;统一前的新疆出生仍按 +06:00)。
// 结果带 geoZone(原地理时区)与 advisory('cn-unified')供 UI/AI 提示「官方 +08:00 · 当地惯用 +06:00」;
// kill-switch:localStorage 'horosa.tz.cnUnified' = '0' 回到纯地理时区。已存档的 zone 走 resolveGeoZone 优先沿用,零回归。
export const CN_UNIFIED_ZONE_SINCE = '1949-10-01';
const CN_UNIFY = Object.freeze({ 'Asia/Urumqi': 'Asia/Shanghai' });

function cnUnifiedEnabled(){
	try{
		if(typeof window !== 'undefined' && window.localStorage){
			return window.localStorage.getItem('horosa.tz.cnUnified') !== '0';
		}
	}catch(e){ /* 无存储环境=默认开 */ }
	return true;
}

export function unifyCnZone(zone, dateStr){
	if(!zone || !CN_UNIFY[zone] || !cnUnifiedEnabled()){
		return { zone: zone, advisory: null };
	}
	// 统一北京时间以前(含公元前 / 公元 1–999 年)保留当地时区:按民用历日序数比,不按四位年字符串比
	const jdn = civilJdnOfDateStr(datePartOf(`${dateStr || ''}`));
	if(Number.isFinite(jdn) && jdn < civilJdnOfDateStr(CN_UNIFIED_ZONE_SINCE)){
		return { zone: zone, advisory: null };
	}
	return { zone: CN_UNIFY[zone], advisory: 'cn-unified' };
}

// 一站式:经纬度 + 日期 → { zone, offset, dst, geoZone, advisory } 或 null(坐标无效/无法解析)。
export function dstAwareZoneAt(lat, lng, dateStr){
	const geoZone = ianaTimezoneAt(lat, lng);
	if(!geoZone){
		return null;
	}
	const unified = unifyCnZone(geoZone, dateStr);
	const zone = unified.zone;
	const offset = offsetForZoneAtDate(zone, dateStr);
	if(!offset){
		return null;
	}
	return {
		zone: zone,
		offset: offset,
		dst: isDstActiveAt(zone, dateStr),
		geoZone: geoZone,
		advisory: unified.advisory,
	};
}

// 表单里「日期/时间」字段的兼容取值:ChartFormData=date、ChartData=birth、CaseData=divTime。
export function dstDateField(flds){
	if(!flds){
		return null;
	}
	return flds.date || flds.birth || flds.divTime || null;
}

// 依表单经纬度 + 日期回填含夏令时的时区偏移(保留本地钟点,仅改偏移)。
// 三类表单通吃(date/birth/divTime + 可选 time)。返回 { zone, offset, dst } 或 null。
// 注:直接 mutate flds(原地写 zone + 换 DateTime 新引用),调用方随后 setState 即可。
export function applyDstToFields(flds){
	const df = dstDateField(flds);
	if(!flds || !flds.zone || !df || !df.value || !df.value.format){
		return null;
	}
	const dateStr = df.value.format('YYYY-MM-DD');
	const gpsLat = flds.gpsLat ? flds.gpsLat.value : null;
	const gpsLon = flds.gpsLon ? flds.gpsLon.value : null;
	const info = dstAwareZoneAt(gpsLat, gpsLon, dateStr);
	if(!info){
		return null;
	}
	flds.zone.value = info.offset;
	// 换新 DateTime 引用(克隆 + setZone),触发 DateTimeSelector 从 props 重新同步时区显示
	if(df.value.clone){
		const d = df.value.clone();
		d.setZone(info.offset);
		df.value = d;
	}
	if(flds.time && flds.time.value && flds.time.value.clone){
		const t = flds.time.value.clone();
		t.setZone(info.offset);
		flds.time.value = t;
	}
	return info;
}

// 选地点(各技法页 changeGeo)时求时区偏移的单一真源:
//   - 手动改过时区(rec.zone,来自 GeoCoordSelector.withZone)→ 直接沿用;
//   - 否则按新坐标 + 当前盘日期推断含夏令时的 UTC 偏移。
// 只决定时区「标签」(配合 DateTime.setZone 保留输入的钟面时刻),不做真太阳时经度校正
//(后者在后端按 timeAlg 控,直接时间盘不应被经度移位)。无法判定返回 null。
export function resolveGeoZone(rec, dateStr){
	if(!rec){
		return null;
	}
	if(rec.zone){
		return rec.zone;
	}
	try{
		let ds = dateStr;
		if(!ds){
			// 取不到盘期时兜底「今天」作 DST 判定锚点(选点多在当前时段,偏差仅限夏令时切换日附近)
			const now = new Date();
			ds = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
		}
		const info = dstAwareZoneAt(rec.gpsLat, rec.gpsLng, ds);
		return info && info.offset ? info.offset : null;
	}catch(e){
		return null;
	}
}
