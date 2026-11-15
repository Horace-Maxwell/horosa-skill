// 地名 → 坐标 + 时区（skill 胶水；门面 horosa_place_search 与技法载荷的 `place` 键共用这一条）。
//
// 算法全部是 vendored 上游星阙的，这里不排序、不换算、不兜底：
//   - place/place.js resolvePlaceOffline：上游 AI 助手的离线地名解析（小库 + 大库 citiesFull，cityMatch 四档评分，
//     同城 0.25° 去重，exact 唯一 = high / 前缀唯一最优 = medium），候选顺序即上游顺序；
//   （十进制 → 罗盘串 31n13 不在这里出：技法载荷的一般十进制入参本来就在 Python 换算，地名解析与它共用同一个
//    input_normalization._format_compact_coordinate——上游 AstroHelper.convertLatToStr 的逐步移植，金标锁住；一个换算、不是两个）
//   - utils/timezone.js dstAwareZoneAt：tz-lookup → IANA → 中国大陆统一北京时间 → Intl 当日偏移（含 TZ_RULE_OVERRIDES）。
// 上游北京时间统一的 kill-switch 是浏览器 localStorage（'horosa.tz.cnUnified'='0'）；headless 没有它，调用方以
// cnUnified=false 显式关闭，等价于上游「回到纯地理时区」：偏移改按 geoZone 用同一组 offsetForZoneAtDate / isDstActiveAt 求。
//
// 何时信一个匹配 = skill 自己的规则（placeResolve.js decidePlace，AGENTS §10 上游镜像注记）：上游字段原样保留在
// resolved / confidence / code / match / candidates（tests/test_place_search.py 对着上游源逐值核对），skill 的裁决
// 另放 `verdict`——Python 只按 verdict 决定填不填坐标。另两种模式：
//   - `queries: [...]`：批量只出裁决（语料测试一次 node 进程跑几百条）；
//   - `point: {gpsLat, gpsLon}` + date：只算这组坐标在该日的时区（`place` 同时给了 lat/lon 却没给 zone 时用）。
import { resolvePlaceOffline } from '../vendor/place/place.js';
import { dstAwareZoneAt, isDstActiveAt, offsetForZoneAtDate } from '../vendor/utils/timezone.js';
import { decidePlace, placeKey, POLICY } from './placeResolve.js';

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
	const gpsLat = Number(item.gpsLat);
	const gpsLon = Number(item.gpsLon);
	return {
		name: item.name,
		region: item.region || '',
		en: item.en || '',
		gpsLat: Number.isFinite(gpsLat) ? gpsLat : null,
		gpsLon: Number.isFinite(gpsLon) ? gpsLon : null,
		...zoneFor(item.gpsLat, item.gpsLon, dateStr, cnUnified),
	};
}

function withZones(verdict, dateStr, cnUnified) {
	const zoned = (item) => (item ? { ...item, ...describe(item, dateStr, cnUnified) } : item);
	return {
		...verdict,
		match: verdict.match ? zoned(verdict.match) : null,
		candidates: (verdict.candidates || []).map(zoned),
		suggestions: (verdict.suggestions || []).map(zoned),
	};
}

// Decide once; when the raw text decides nothing and the caller sent a script-folded twin (Python textscript
// fold_to_simplified — wider than upstream's city-character map), decide the twin too.
async function decide(query, folded, dateStr, limit) {
	const upstream = await resolvePlaceOffline(query, { dateStr, limit });
	let verdict = await decidePlace(query, { upstream, limit });
	if (verdict.status !== 'resolved' && folded && placeKey(folded) !== placeKey(query)) {
		const second = await decidePlace(folded, { upstream: await resolvePlaceOffline(folded, { dateStr, limit }), limit });
		if (second.status === 'resolved') verdict = { ...second, query, folded_from: folded };
	}
	if (verdict.status === 'not_found') {
		const shorter = await addressFallback(query, dateStr, limit);
		if (shorter) verdict = shorter;
	}
	return { upstream, verdict };
}

// 长地址 / 医院 / 机场（审计 F18）：「广东省深圳市南山区粤海街道」「北京协和医院」「上海浦东机场」「北京附近」以前一律 not_found、零建议。
// 从右往左逐段去掉末尾的街道 / 路 / 号 / 医院 / 机场 / 学校 / 「附近」，取第一个能唯一解析的前缀：resolved + caveat 写明丢了哪段、按哪一级取坐标。
// 只在原样查不到时才走；坐标仍只来自库里的条目。
const ADDRESS_TAIL = /(?:街道|大道|路|街|巷|弄|号|號|栋|棟|楼|樓|室|医院|醫院|机场|機場|火车站|車站|车站|大学|大學|学院|學院|中学|中學|小学|小學|村|社区|社區|附近|一带|一帶|周边|周邊|地区|地區)$/u;
async function addressFallback(query, dateStr, limit) {
	const text = `${query}`.trim();
	const tail = ADDRESS_TAIL.exec(text);
	if (!tail) return null;
	// 从紧挨末尾关键词的那一处往前逐字试前缀（「北京协和医院」→「北京协和」→「北京」）：第一个能唯一解析的就用；
	// 碰到歧义 / 太宽的前缀就停（「南山区粤海街道」截出的「南山区」不止一个，不替用户选）。
	const words = [...text];
	const cut = words.length - [...tail[0]].length;
	for (let i = cut; i >= 1; i -= 1) {
		const prefix = words.slice(0, i).join('').replace(/[,，、\s]+$/u, '');
		if (!prefix) continue;
		const v = await decidePlace(prefix, { upstream: await resolvePlaceOffline(prefix, { dateStr, limit }), limit });
		if (v.status === 'resolved') {
			return { ...v, query, phrase: prefix, caveats: [...(v.caveats || []), { code: 'address_truncated', dropped: words.slice(i).join(''), used: prefix }] };
		}
		if (v.status !== 'not_found' && v.status !== 'near') return null;
	}
	return null;
}

function brief(v) {
	const short = (c) => ({ name: c.name, region: c.region, gpsLat: c.gpsLat, gpsLon: c.gpsLon });
	return {
		query: v.query, status: v.status, matched_by: v.matched_by ?? null, alias: v.alias ?? null,
		caveats: (v.caveats || []).map((c) => c.code), match: v.match ? short(v.match) : null,
		candidates: (v.candidates || []).map(short), total: v.total ?? 0, suggestions: (v.suggestions || []).map(short),
		unsupported: Boolean(v.unsupported),
	};
}

export async function runPlaceSearch(payload = {}) {
	const query = `${payload.query ?? ''}`;
	const dateStr = typeof payload.date === 'string' && payload.date ? payload.date : undefined;
	const limit = Number.isFinite(Number(payload.limit)) && Number(payload.limit) > 0 ? Number(payload.limit) : undefined;
	const cnUnified = payload.cnUnified !== false;
	if (Array.isArray(payload.queries)) {
		const batch = [];
		for (const q of payload.queries) {
			const item = typeof q === 'object' && q ? q : { query: q };
			const { verdict } = await decide(`${item.query ?? ''}`, item.folded, dateStr, limit);
			batch.push(brief(verdict));
		}
		return { data: { policy: POLICY, batch } };
	}
	if (payload.point && typeof payload.point === 'object') {
		const gpsLat = Number(payload.point.gpsLat);
		const gpsLon = Number(payload.point.gpsLon);
		if (!Number.isFinite(gpsLat) || !Number.isFinite(gpsLon)) {
			throw Object.assign(new Error('point needs numeric gpsLat / gpsLon'), { code: 'place.invalid_payload' });
		}
		return { data: { policy: POLICY, date: dateStr ?? null, point: { gpsLat, gpsLon, ...zoneFor(gpsLat, gpsLon, dateStr, cnUnified) } } };
	}
	const { upstream: result, verdict } = await decide(query, typeof payload.folded === 'string' ? payload.folded : undefined, dateStr, limit);
	const picked = result.resolved && result.place ? result.place : null;
	return {
		data: {
			query,
			date: dateStr ?? null,
			resolved: Boolean(result.resolved),
			confidence: result.confidence ?? null,
			code: result.code ?? null,
			// 坐标与时区 = 上游 toPlace 同一组输入（gpsLat/gpsLon + dstAwareZoneAt）；tests/test_place_search.py 对着上游源逐值核对。
			match: picked ? describe(picked, dateStr, cnUnified) : null,
			candidates: (result.candidates || []).map((item) => describe(item, dateStr, cnUnified)),
			// skill 的接受规则裁决（Python 只看它决定填不填坐标）。
			verdict: withZones(verdict, dateStr, cnUnified),
		},
	};
}
