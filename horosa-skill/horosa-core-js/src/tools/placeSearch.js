// 地名 → 坐标 + 时区（skill 胶水；门面 horosa_place_search 与技法载荷的 `place` 键共用这一条）。
//
// 算法全部是 vendored 上游星阙的，这里不排序、不换算、不兜底：
//   - place/place.js resolvePlaceOffline：上游 AI 助手的离线地名解析（小库 + 大库 citiesFull，cityMatch 四档评分，
//     同城 0.25° 去重，exact 唯一 = high / 前缀唯一最优 = medium），候选顺序即上游顺序；
//   - place/geoCompass.js geoPairToRecordFields：十进制 → 存档罗盘串（31n13 / 121e28，与 AstroHelper convertLatToStr 同构）；
//   - utils/timezone.js dstAwareZoneAt：tz-lookup → IANA → 中国大陆统一北京时间 → Intl 当日偏移（含 TZ_RULE_OVERRIDES）。
// 上游北京时间统一的 kill-switch 是浏览器 localStorage（'horosa.tz.cnUnified'='0'）；headless 没有它，调用方以
// cnUnified=false 显式关闭，等价于上游「回到纯地理时区」：偏移改按 geoZone 用同一组 offsetForZoneAtDate / isDstActiveAt 求。
import { resolvePlaceOffline } from '../vendor/place/place.js';
import { geoPairToRecordFields } from '../vendor/place/geoCompass.js';
import { dstAwareZoneAt, isDstActiveAt, offsetForZoneAtDate } from '../vendor/utils/timezone.js';

function zoneFor(gpsLat, gpsLon, dateStr, cnUnified) {
	const info = dateStr ? dstAwareZoneAt(gpsLat, gpsLon, dateStr) : null;
	if (!info) {
		return { iana: null, geoZone: null, zone: null, dst: null, advisory: null };
	}
	if (cnUnified === false && info.advisory) {
		return {
			iana: info.geoZone,
			geoZone: info.geoZone,
			zone: offsetForZoneAtDate(info.geoZone, dateStr),
			dst: isDstActiveAt(info.geoZone, dateStr),
			advisory: null,
		};
	}
	return { iana: info.zone, geoZone: info.geoZone, zone: info.offset, dst: info.dst, advisory: info.advisory };
}

function describe(item, dateStr, cnUnified) {
	const geo = geoPairToRecordFields(item.gpsLat, item.gpsLon) || {};
	return {
		name: item.name,
		region: item.region || '',
		en: item.en || '',
		lat: geo.lat ?? null,
		lon: geo.lon ?? null,
		gpsLat: geo.gpsLat ?? null,
		gpsLon: geo.gpsLon ?? null,
		...zoneFor(item.gpsLat, item.gpsLon, dateStr, cnUnified),
	};
}

export async function runPlaceSearch(payload = {}) {
	const query = `${payload.query ?? ''}`;
	const dateStr = typeof payload.date === 'string' && payload.date ? payload.date : undefined;
	const limit = Number.isFinite(Number(payload.limit)) && Number(payload.limit) > 0 ? Number(payload.limit) : undefined;
	const cnUnified = payload.cnUnified !== false;
	const result = await resolvePlaceOffline(query, { dateStr, limit });
	const picked = result.resolved && result.place ? result.place : null;
	return {
		data: {
			query,
			date: dateStr ?? null,
			resolved: Boolean(result.resolved),
			confidence: result.confidence ?? null,
			code: result.code ?? null,
			// 与上游 toPlace 同一组调用（geoPairToRecordFields + dstAwareZoneAt）；tests/test_place_search.py 对着上游源逐值核对。
			match: picked ? describe(picked, dateStr, cnUnified) : null,
			candidates: (result.candidates || []).map((item) => describe(item, dateStr, cnUnified)),
		},
	};
}
