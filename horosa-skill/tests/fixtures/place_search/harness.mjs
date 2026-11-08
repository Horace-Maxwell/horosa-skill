// 地名检索对拍夹具（tests/test_place_search.py）：同一段脚本分别跑「上游源本身」与 vendored 副本，输出必须逐字节相同。
// argv[2] = 配置 JSON 文件路径：{ hooks?, hookData?, modules: {cityMatch, cities, full, fold, place, timezone}, cases }。
// 上游源是 bundler 写法（相对 import 无扩展名、JSON 无 import 属性、.js 无 "type": "module"），由 upstream_hooks.mjs 在加载期补齐；
// vendored 副本已由 revendor 变换成原生 ESM，直接 import。值全部出自被测代码本身，这里不算任何东西。
import { readFileSync } from 'node:fs';
import { register } from 'node:module';

const cfg = JSON.parse(readFileSync(process.argv[2], 'utf8'));
if (cfg.hooks) {
	register(cfg.hooks, { data: cfg.hookData });
}
const m = cfg.modules;
const json = async (url) => (await import(url, { with: { type: 'json' } })).default;
const cityMatch = await import(m.cityMatch);
const place = await import(m.place);
const tz = await import(m.timezone);
const lists = [await json(m.cities), await json(m.full)];
const fold = await json(m.fold);

const out = { search: {}, resolve: {}, zones: [], offsets: [] };
for (const query of cfg.cases.search) {
	out.search[query] = cityMatch
		.searchCitiesScored(query, lists, fold, 40)
		.map((hit) => [hit.c._name, hit.c._region, hit.c._en, hit.c._lat, hit.c._lng, hit.score]);
}
for (const query of cfg.cases.resolve) {
	out.resolve[query] = await place.resolvePlaceOffline(query, { dateStr: cfg.cases.resolveDate, limit: 10 });
}
for (const [query, date] of cfg.cases.zones) {
	const result = await place.resolvePlaceOffline(query, { dateStr: date });
	const picked = result.place || null;
	out.zones.push({
		query,
		date,
		confidence: result.confidence,
		place: picked,
		dstAware: picked ? tz.dstAwareZoneAt(picked.gpsLat, picked.gpsLon, date) : null,
	});
}
for (const [zone, date] of cfg.cases.offsets) {
	out.offsets.push([zone, date, tz.offsetForZoneAtDate(zone, date), tz.isDstActiveAt(zone, date)]);
}
process.stdout.write(JSON.stringify(out));
