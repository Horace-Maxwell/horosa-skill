// Skill-side place acceptance rule (skill-authored, NOT upstream; AGENTS §10 上游镜像注记 records the deviation).
//
// Upstream resolvePlaceOffline (vendor/place/place.js) is kept verbatim and still runs — its fields stay in the
// place_search reply unchanged. What this module adds is the decision *when to trust a match*, because upstream's
// own "high" confidence is reached through paths that pick the wrong city with full confidence:
//   - pinyin initials count as an exact match (cityMatch.js `c._pi === q`): NYC → 银川 (Yin Chuan), HK → 海口;
//   - the head/tail fallback takes `exact[0]` once any head substring appears in a region/name/English field
//     ("St. Petersburg" → Florida, a partial Latin region hint);
//   - prefix / substring hits become "medium" picks.
// Rule: a pick is auto-resolved only when an entry's own name, English name, full pinyin, its administrative stem
// (朝阳区 → 朝阳, 北京城区 → 北京) or a skill alias equals the normalised query — script-, case-, spacing- and
// punctuation-insensitive — optionally narrowed by qualifiers the library can check (country, Chinese admin
// ancestry). A name that several distinct places share stays ambiguous: there is deliberately NO "prefer the bigger
// city" rule (held for the maintainer). Nothing here edits or re-ranks the library; coordinates always come from
// the library entry that was matched.
import CITIES from '../vendor/place/data/cities.json' with { type: 'json' };
import CITY_TRAD_SIMP from '../vendor/place/data/cityTradSimpMap.json' with { type: 'json' };
import { enrichCity, foldAscii, foldTrad } from '../vendor/place/cityMatch.js';
import ALIASES from './placeData/aliases.json' with { type: 'json' };
import REGIONS from './placeData/regions.json' with { type: 'json' };

export const POLICY = 'skill-place-acceptance/1';
const NEAR_DEG = 0.25; // same proximity upstream place.js uses to merge one city's rows across the two libraries
const CN_ROOT = '中华人民共和国';
const ISO = /^[A-Z]{2}$/;
const CJK = /[㐀-鿿豈-﫿]/;
const SEPARATORS = /[,，、;；/|·・()（）\[\]【】「」]+/;

// ---------------------------------------------------------------- keys

// One normalised form for queries, names, aliases and qualifiers: NFKC (full-width → ASCII), upstream's own
// Traditional→Simplified city-character map, lower case, upstream's accent fold, St./Mt./Ft. spelled out, then
// everything that is not a letter or digit dropped ("Xi'an" = "xian", "New York" = "newyork", "臺北" = "台北").
const PLAIN_ASCII = /^[A-Za-z0-9 ]*$/;
const ABBREVIATED = /\b(st|ste|mt|ft)\b/i;
export function placeKey(text) {
	const raw = `${text ?? ''}`;
	// Fast path (most of the 50 000 library names): plain ASCII words, no St./Mt./Ft. to spell out.
	if (PLAIN_ASCII.test(raw) && !ABBREVIATED.test(raw)) return raw.toLowerCase().replace(/ +/g, '');
	let t = raw.normalize('NFKC');
	t = foldTrad(t, CITY_TRAD_SIMP).toLowerCase();
	t = foldAscii(t);
	t = t.replace(/\b(st|ste)\.?\s+/g, (m, w) => (w === 'st' ? 'saint ' : 'sainte '))
		.replace(/\bmt\.?\s+/g, 'mount ')
		.replace(/\bft\.?\s+/g, 'fort ');
	return t.replace(/[^\p{L}\p{N}]+/gu, '');
}

const ETHNIC = ['维吾尔', '蒙古', '藏', '回', '壮', '苗', '彝', '布依', '朝鲜', '满', '侗', '瑶', '白', '土家', '哈尼', '哈萨克',
	'傣', '黎', '傈僳', '佤', '畲', '拉祜', '水', '东乡', '纳西', '景颇', '柯尔克孜', '土', '达斡尔', '仫佬', '羌', '布朗', '撒拉',
	'毛南', '仡佬', '锡伯', '普米', '塔吉克', '怒', '鄂温克', '保安', '裕固', '独龙', '鄂伦春', '各族'];
const ADMIN_SUFFIX = /(特别行政区|自治区|自治州|自治县|自治旗|地区|新区|林区|矿区|街道|省|市|区|县|旗|盟|镇|乡)$/;

// Administrative stem of a Chinese admin name, or null: 朝阳区 → 朝阳, 新疆维吾尔自治区 → 新疆, 浦东新区 → 浦东,
// 北京城区 (parent 北京市) → 北京. Keeps at least two characters (内蒙古自治区 → 内蒙古, not 内).
export function adminStem(name, parent) {
	const m = `${name}`.match(ADMIN_SUFFIX);
	if (!m) return null;
	let stem = name.slice(0, name.length - m[1].length);
	if (m[1].startsWith('自治')) {
		let changed = true;
		while (changed) {
			changed = false;
			for (const e of ETHNIC) {
				for (const tail of [`${e}族`, e.length >= 2 ? e : null]) {
					if (tail && stem.endsWith(tail) && stem.length - tail.length >= 2) {
						stem = stem.slice(0, stem.length - tail.length);
						changed = true;
					}
				}
			}
		}
	}
	if (m[1] === '区' && stem.endsWith('城') && parent && parent === `${stem.slice(0, -1)}市` && stem.length >= 3) {
		stem = stem.slice(0, -1); // 北京城区 → 北京 (the library's urban core of a municipality)
	}
	return stem.length >= 2 && stem !== name ? stem : null;
}

// ---------------------------------------------------------------- index

let INDEX = null;
let INDEX_LOADING = null;

async function loadFull() {
	const m = await import('../vendor/place/data/citiesFull.json', { with: { type: 'json' } });
	return Array.isArray(m) ? m : (m && m.default) || [];
}

function addKey(map, key, value) {
	if (!key) return;
	let list = map.get(key);
	if (!list) map.set(key, (list = []));
	if (!list.includes(value)) list.push(value);
}

function regionKeyAnchors(qualifiers, text) {
	return qualifiers.get(placeKey(text)) || [];
}

async function buildIndex() {
	const full = await loadFull();
	const entries = [];
	const push = (raw, lib) => {
		const c = enrichCity(raw);
		const e = {
			id: entries.length, lib, c,
			name: c._name, en: c._en, region: c._region,
			lat: Number(c._lat), lng: Number(c._lng),
			code: lib === 'F' && ISO.test(c._region) ? c._region : null,
			admin: lib === 'F' && !ISO.test(c._region),
		};
		entries.push(e);
		return e;
	};
	for (const c of CITIES) push(c, 'S');
	for (const c of full) push(c, 'F');

	// Chinese admin tree (citiesFull rows whose r is a parent name, not an ISO code).
	const adminByName = new Map();
	for (const e of entries) if (e.admin) addKey(adminByName, e.name, e);
	const parentOf = (e) => (e.admin && e.region !== CN_ROOT ? adminByName.get(e.region) || [] : []);
	const depthMemo = new Map();
	const depth = (e, guard = 0) => {
		if (!e.admin) return 0;
		if (depthMemo.has(e.id)) return depthMemo.get(e.id);
		let d = 1;
		if (e.region !== CN_ROOT) {
			const ps = parentOf(e);
			d = ps.length && guard < 8 ? 1 + Math.min(...ps.map((p) => depth(p, guard + 1))) : 9;
		}
		depthMemo.set(e.id, d);
		return d;
	};
	const ancestors = (e) => {
		const out = [];
		const seen = new Set();
		let frontier = parentOf(e);
		while (frontier.length) {
			const next = [];
			for (const p of frontier) {
				if (seen.has(p.id)) continue;
				seen.add(p.id);
				out.push(p);
				next.push(...parentOf(p));
			}
			frontier = next;
		}
		return out;
	};

	const places = new Map(); // key -> [{e, via}]
	const addPlace = (key, e, via) => {
		if (!key) return;
		let list = places.get(key);
		if (!list) places.set(key, (list = []));
		if (!list.some((h) => h.e === e)) list.push({ e, via });
	};
	for (const e of entries) {
		e.depth = depth(e);
		e.stem = e.admin ? adminStem(e.name, e.region) : null;
		e.nameKey = placeKey(e.name);
		addPlace(e.nameKey, e, 'name');
		if (e.en) addPlace(placeKey(e.en), e, 'english');
		if (e.c._pf) addPlace(e.c._pf, e, 'pinyin'); // full pinyin only — never initials (_pi)
		if (e.stem) {
			addPlace(placeKey(e.stem), e, 'stem');
			const syllables = `${e.c.p || ''}`.trim().split(/\s+/);
			const cut = [...e.name].length - [...e.stem].length;
			if (syllables.length === [...e.name].length && cut > 0) addPlace(syllables.slice(0, -cut).join(''), e, 'stem');
		}
	}

	// Qualifiers: key -> anchors. 'C:XX' country, 'S:XX' a subdivision of XX (unverifiable), 'A:<id>' an admin unit,
	// 'K:<key>' the raw text of a curated region part ("印尼") so it can at least match itself.
	const qualifiers = new Map();
	for (const [code, names] of Object.entries(REGIONS.countries)) {
		addKey(qualifiers, code.toLowerCase(), `C:${code}`);
		for (const n of names) addKey(qualifiers, placeKey(n), `C:${code}`);
	}
	for (const [country, subs] of Object.entries(REGIONS.subdivisions)) {
		for (const [code, ...names] of subs) {
			addKey(qualifiers, code.toLowerCase(), `S:${country}`);
			for (const n of names) addKey(qualifiers, placeKey(n), `S:${country}`);
		}
	}
	addKey(qualifiers, placeKey('中国'), 'C:CN');
	addKey(qualifiers, placeKey(CN_ROOT), 'C:CN');
	const adminCode = REGIONS.cn_admin_codes || {};
	for (const e of entries) {
		if (!e.admin) continue;
		const a = `A:${e.id}`;
		addKey(qualifiers, e.nameKey, a);
		if (e.stem) addKey(qualifiers, placeKey(e.stem), a);
		if (e.c._pf) addKey(qualifiers, e.c._pf, a);
		const syllables = `${e.c.p || ''}`.trim().split(/\s+/);
		const cut = e.stem ? [...e.name].length - [...e.stem].length : 0;
		if (cut > 0 && syllables.length === [...e.name].length) addKey(qualifiers, syllables.slice(0, -cut).join(''), a);
		if (adminCode[e.name] && e.region === CN_ROOT) addKey(qualifiers, adminCode[e.name].toLowerCase(), a);
	}
	for (const [alias, target] of Object.entries(REGIONS.cn_admin_aliases || {})) {
		for (const e of adminByName.get(target) || []) addKey(qualifiers, placeKey(alias), `A:${e.id}`);
	}

	// Anchors each entry satisfies (its ancestors / its country) and its "where" chain: computed on first use (only
	// pool members ever need them; building them for all 50 000 rows up front doubled every place call's start-up).
	const buildAnchors = (e) => {
		const anchors = new Set();
		const addAdmin = (a) => {
			anchors.add(`A:${a.id}`);
			if (a.region === CN_ROOT && adminCode[a.name]) anchors.add(`C:${adminCode[a.name]}`);
		};
		if (e.code) {
			anchors.add(`C:${e.code}`);
			if (['HK', 'MO', 'TW'].includes(e.code)) anchors.add('C:CN');
		} else if (e.admin) {
			anchors.add('C:CN');
			for (const a of ancestors(e)) addAdmin(a);
		} else {
			for (const part of `${e.region}`.split(/[·・]/).filter(Boolean)) {
				anchors.add(`K:${placeKey(part)}`);
				for (const q of regionKeyAnchors(qualifiers, part)) {
					if (q.startsWith('S:')) continue;
					if (q.startsWith('A:')) {
						const a = entries[Number(q.slice(2))];
						if (a.depth !== 1) continue; // curated regions name provinces, never a same-named county
						addAdmin(a);
						for (const up of ancestors(a)) addAdmin(up);
						anchors.add('C:CN');
					} else {
						anchors.add(q);
					}
				}
			}
		}
		return anchors;
	};
	LAZY.anchorsOf = buildAnchors;
	LAZY.whereOf = (e) => whereChain(e, ancestors);
	for (const e of CURATED_ROWS(entries)) {
		for (const part of `${e.region}`.split(/[·・]/).filter(Boolean)) addKey(qualifiers, placeKey(part), `K:${placeKey(part)}`);
	}

	// Aliases (skill data) -> library entries.
	const aliases = new Map();
	const aliasProblems = [];
	for (const a of ALIASES.aliases || []) {
		const targets = entries.filter((e) => e.name === a.target.name && e.region === a.target.region);
		if (targets.length !== 1) {
			aliasProblems.push({ target: a.target, found: targets.length });
			continue;
		}
		for (const k of a.keys) addKey(aliases, placeKey(k), { e: targets[0], alias: { text: k, kind: a.kind, target: a.target } });
	}
	const unresolvable = new Map();
	for (const u of ALIASES.unresolvable || []) for (const k of u.keys) unresolvable.set(placeKey(k), u);

	return { entries, places, qualifiers, aliases, aliasProblems, unresolvable, adminByName };
}

const CURATED_ROWS = (entries) => entries.filter((e) => !e.admin && !e.code);
// Per-entry facts computed on first use (set by buildIndex). Only pool members ever need them.
const LAZY = { anchorsOf: null, whereOf: null };
const anchorsOf = (e) => (e._anchors ??= LAZY.anchorsOf(e));
const whereOf = (e) => (e._where ??= LAZY.whereOf(e));

function whereChain(e, ancestors) {
	if (e.code) {
		const names = REGIONS.countries[e.code] || [];
		return [names.find((n) => CJK.test(n)) || names[0] || e.code];
	}
	if (e.admin) return ancestors(e).map((a) => a.name);
	return `${e.region}`.split(/[·・]/).filter(Boolean).reverse();
}

export async function placeIndex() {
	if (INDEX) return INDEX;
	if (!INDEX_LOADING) INDEX_LOADING = buildIndex().then((ix) => (INDEX = ix));
	return INDEX_LOADING;
}

// ---------------------------------------------------------------- pools

const isProvince = (e) => e.admin && e.depth === 1 && /(省|自治区)$/.test(e.name);
const isCityLevel = (e) => !e.admin || e.depth <= 2 || /市$/.test(e.name);

function rank(a, b) {
	return (a.tier - b.tier)
		|| ((a.e.lib === 'S' ? 0 : 1) - (b.e.lib === 'S' ? 0 : 1))
		|| ((a.e.admin ? a.e.depth : 0) - (b.e.admin ? b.e.depth : 0))
		|| (a.e.name.length - b.e.name.length)
		|| (`${a.e.c._pf}`.length - `${b.e.c._pf}`.length)
		|| (a.e.id - b.e.id);
}

// Every entry a place phrase can mean, before qualifiers: T1 own name / English / full pinyin / alias,
// T2 administrative stem. District- and county-level stems only compete when no curated (small-library) city
// already carries the exact name: 西安 is the curated 西安, not also 辽源市西安区; 朝阳 (no curated city) is every 朝阳.
function poolFor(ix, key) {
	if (!key) return [];
	const t1 = [];
	const t2 = [];
	for (const h of ix.places.get(key) || []) (h.via === 'stem' ? t2 : t1).push({ e: h.e, via: h.via, tier: 1 });
	for (const h of ix.aliases.get(key) || []) t1.push({ e: h.e, via: 'alias', alias: h.alias, tier: 1 });
	for (const h of t2) h.tier = 2;
	const curated = t1.filter((h) => h.e.lib === 'S');
	// A curated city and the library's own admin row for it (天津 / 天津市, whose centroids are 0.3° apart) are one
	// place: the admin row whose stem is the curated name, within 1°, is not a rival.
	const sameCity = (h) => curated.some((s) => s.e.nameKey === placeKey(h.e.stem || '') && Math.abs(s.e.lat - h.e.lat) <= 1 && Math.abs(s.e.lng - h.e.lng) <= 1);
	const keep2 = t1.length ? t2.filter((h) => (isCityLevel(h.e) || !curated.length) && !sameCity(h)) : t2;
	const all = [...t1, ...keep2].sort(rank);
	// The same entry reached twice (name and alias) keeps its best reading.
	const seen = new Set();
	return all.filter((h) => (seen.has(h.e.id) ? false : (seen.add(h.e.id), true)));
}

// Collapse rows that are one place: within NEAR_DEG of a better-ranked row (upstream distinctByName's rule — the
// curated 北京, citiesFull 北京市 and Beijing are one city), or an admin parent/child pair where the parent is a
// city (朝阳市 ⊃ 朝阳县 → 朝阳市) or a prefecture whose only city row is named the same (喀什地区 ⊃ 喀什市 → 喀什市).
function distinct(ix, hits) {
	const kept = [];
	for (const h of hits) {
		const dup = kept.find((k) => Math.abs(k.e.lat - h.e.lat) <= NEAR_DEG && Math.abs(k.e.lng - h.e.lng) <= NEAR_DEG);
		if (dup) {
			if (!dup.alias && h.alias && dup.e.id !== h.e.id) dup.sameAs = h; // keep the real entry; remember the alias led here too
			continue;
		}
		kept.push(h);
	}
	if (kept.length > 1 && kept.every((h) => h.e.admin)) {
		const isAncestor = (a, d) => anchorsOf(d.e).has(`A:${a.e.id}`);
		for (const top of kept) {
			const others = kept.filter((h) => h !== top);
			if (!others.every((h) => isAncestor(top, h))) continue;
			if (/市$/.test(top.e.name)) return [top];
			if (/(地区|自治州|盟)$/.test(top.e.name)) {
				const cities = others.filter((h) => /市$/.test(h.e.name));
				if (cities.length === 1) return cities;
			}
		}
	}
	return kept;
}

// ---------------------------------------------------------------- query parsing

function tokenize(query) {
	const out = [];
	for (const seg of `${query}`.normalize('NFKC').split(SEPARATORS)) {
		for (const t of seg.trim().split(/\s+/)) if (t) out.push(t);
	}
	return out.slice(0, 12);
}

// Split a run of tokens into known qualifier phrases (each 1–4 tokens; a CJK token may also split into several
// qualifiers by characters: 广东省深圳市 → 广东省 + 深圳市). Returns a list of {text, anchors} or null.
function segmentQualifiers(ix, tokens) {
	if (!tokens.length) return [];
	const n = tokens.length;
	const best = new Array(n + 1).fill(null);
	best[0] = [];
	for (let i = 0; i < n; i++) {
		if (!best[i]) continue;
		for (let j = i + 1; j <= Math.min(n, i + 4); j++) {
			const text = tokens.slice(i, j).join(' ');
			const anchors = ix.qualifiers.get(placeKey(text));
			if (anchors && !best[j]) best[j] = [...best[i], { text, anchors }];
		}
		if (CJK.test(tokens[i])) {
			const parts = segmentCjk(ix, tokens[i]);
			if (parts && !best[i + 1]) best[i + 1] = [...best[i], ...parts];
		}
	}
	return best[n];
}

function segmentCjk(ix, text) {
	const chars = [...text];
	const n = chars.length;
	const best = new Array(n + 1).fill(null);
	best[0] = [];
	for (let i = 0; i < n; i++) {
		if (!best[i]) continue;
		for (let j = n; j >= i + 2; j--) {
			const piece = chars.slice(i, j).join('');
			const anchors = ix.qualifiers.get(placeKey(piece));
			if (anchors && !best[j]) best[j] = [...best[i], { text: piece, anchors }];
		}
	}
	return best[n];
}

// Apply qualifiers to a pool. Every qualifier must be satisfied by the candidate's anchors; a subdivision
// (US state …) is satisfied by the country but marked unverified.
function applyQualifiers(pool, quals) {
	if (!quals.length) return { hits: pool, unverified: [] };
	const unverified = [];
	const hits = pool.filter((h) => quals.every((q) => q.anchors.some((a) => (a.startsWith('S:') ? anchorsOf(h.e).has(`C:${a.slice(2)}`) : anchorsOf(h.e).has(a)))));
	for (const q of quals) {
		const verified = q.anchors.some((a) => !a.startsWith('S:') && hits.some((h) => anchorsOf(h.e).has(a)));
		if (!verified) unverified.push(q.text);
	}
	return { hits, unverified };
}

// All readings of the query: [{phrase, quals}] — whole query first, then every contiguous token range as the place
// with the rest as qualifiers, then (for an unseparated CJK token) every head|tail split with the head as qualifiers.
function readings(ix, query) {
	// The whole query glued into one key ("New York" = "newyork") — but not across a separator the user typed:
	// "León, ES" glued is "leones" (= Leones, Argentina) and "Tāl, IN" is "talin" (= 塔林 Tallinn). Across a comma only
	// a skill alias may match the whole text ("Washington, D.C.").
	const out = [{ phrase: query, quals: [], aliasOnly: SEPARATORS.test(query) }];
	const tokens = tokenize(query);
	const n = tokens.length;
	for (let i = 0; i < n; i++) {
		for (let j = i + 1; j <= n; j++) {
			const left = segmentQualifiers(ix, tokens.slice(0, i));
			const right = segmentQualifiers(ix, tokens.slice(j));
			if (!left || !right) continue;
			const phraseTokens = tokens.slice(i, j);
			if (i > 0 || j < n) out.push({ phrase: phraseTokens.join(' '), quals: [...left, ...right] });
			if (j - i === 1 && CJK.test(phraseTokens[0])) {
				const chars = [...phraseTokens[0]];
				for (let k = chars.length - 2; k >= 1; k--) {
					const head = segmentCjk(ix, chars.slice(0, k).join(''));
					if (head) out.push({ phrase: chars.slice(k).join(''), quals: [...left, ...head, ...right] });
				}
			}
		}
	}
	return out;
}

// Query-side suffix: 台北市 / 高雄市 / "Tainan City" → also try the bare name when the full form names nothing.
function phrasePool(ix, phrase, aliasOnly = false) {
	const key = placeKey(phrase);
	if (aliasOnly) return (ix.aliases.get(key) || []).map((h) => ({ e: h.e, via: 'alias', alias: h.alias, tier: 1 }));
	let pool = poolFor(ix, key);
	if (!pool.length && CJK.test(phrase)) {
		const m = phrase.match(/(市|县|區|区|縣)$/);
		if (m && [...phrase].length >= 3) pool = poolFor(ix, placeKey(phrase.slice(0, -1)));
	}
	if (!pool.length && /\s(city|shi)$/i.test(phrase.trim())) pool = poolFor(ix, placeKey(phrase.trim().replace(/\s(city|shi)$/i, '')));
	return pool;
}

// ---------------------------------------------------------------- suggestions (typos)

function osa(a, b, max) {
	const n = a.length, m = b.length;
	if (Math.abs(n - m) > max) return max + 1;
	let prev2 = null, prev = Array.from({ length: m + 1 }, (_, j) => j);
	for (let i = 1; i <= n; i++) {
		const cur = [i];
		let rowMin = i;
		for (let j = 1; j <= m; j++) {
			let v = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
			if (prev2 && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) v = Math.min(v, prev2[j - 2] + 1);
			cur.push(v);
			if (v < rowMin) rowMin = v;
		}
		if (rowMin > max) return max + 1;
		prev2 = prev;
		prev = cur;
	}
	return prev[m];
}

function suggestions(ix, key, limit) {
	const chars = [...key];
	if (!chars.length) return [];
	const cjk = CJK.test(key);
	const max = cjk ? 1 : chars.length >= 6 ? 2 : 1;
	if (chars.length < (cjk ? 2 : 4)) return [];
	const found = [];
	const consider = (k, hits) => {
		const kc = [...k];
		if (CJK.test(k) !== cjk || Math.abs(kc.length - chars.length) > max) return;
		const d = osa(chars, kc, max);
		if (d <= max) for (const h of hits) found.push({ d, e: h.e, tier: h.via === 'stem' ? 2 : 1, via: h.via });
	};
	for (const [k, hits] of ix.places) consider(k, hits);
	for (const [k, hits] of ix.aliases) consider(k, hits);
	found.sort((a, b) => (a.d - b.d) || rank(a, b));
	const out = [];
	for (const f of found) {
		if (out.some((o) => Math.abs(o.e.lat - f.e.lat) <= NEAR_DEG && Math.abs(o.e.lng - f.e.lng) <= NEAR_DEG)) continue;
		out.push(f);
		if (out.length >= limit) break;
	}
	return out;
}

// ---------------------------------------------------------------- verdict

function view(h) {
	return { name: h.e.name, region: h.e.region, en: h.e.en, gpsLat: h.e.lat, gpsLon: h.e.lng, where: whereOf(h.e), library: h.e.lib === 'S' ? 'cities' : 'citiesFull' };
}

function upstreamView(c) {
	return { name: c.name, region: c.region || '', en: c.en || '', gpsLat: c.gpsLat, gpsLon: c.gpsLon, where: null, library: null };
}

// The query is nothing but region qualifiers (countries, states, provinces) → the names they were read as, else null.
function regionOnly(ix, query) {
	const tokens = tokenize(query);
	if (!tokens.length) return null;
	const quals = segmentQualifiers(ix, tokens);
	if (!quals || !quals.length) return null;
	const names = [];
	for (const q of quals) {
		for (const a of q.anchors) {
			if (a.startsWith('A:')) {
				const e = ix.entries[Number(a.slice(2))];
				if (!isProvince(e)) return null;
				names.push(e.name);
			} else if (a.startsWith('C:')) {
				const all = REGIONS.countries[a.slice(2)] || [];
				names.push(`${all.find((n) => CJK.test(n)) || a.slice(2)} ${all[0] || ''}`.trim());
			} else if (a.startsWith('S:')) {
				names.push(`${q.text} (${a.slice(2)})`);
			}
		}
	}
	return [...new Set(names)];
}

const COORDINATES = /^\s*[-+]?\d{1,3}(?:[.,]\d+)?\s*°?\s*[NSnsEeWw北南东西]?\s*[,，;；\s/]\s*[-+]?\d{1,3}(?:[.,]\d+)?\s*°?\s*[NSnsEeWw北南东西]?\s*$|^\s*\d{1,3}\s*°\s*\d{1,2}\s*['′]/;

// Decide. `upstream` is resolvePlaceOffline's own result for the same query (its candidates are the "closest
// matches" offered when the rule accepts nothing).
export async function decidePlace(query, { upstream = null, limit = 5, allCandidates = false } = {}) {
	const ix = await placeIndex();
	// allCandidates: the whole-library property test needs every candidate, not the 10 a client is shown.
	const cap = allCandidates ? Infinity : Math.max(1, Math.min(10, Number(limit) || 5));
	const raw = `${query ?? ''}`.trim();
	const base = { policy: POLICY, query: raw, key: placeKey(raw) };
	if (!base.key) return { ...base, status: 'not_found', candidates: [], total: 0, suggestions: [] };
	// "31.2,121.5" / "31°13′N 121°28′E": coordinates typed as a place. Which number is latitude is not guessed.
	if (COORDINATES.test(raw) || /^\s*\d{1,3}[nsNS]\d{1,2}\s*[,，\s]\s*\d{1,3}[ewEW]\d{1,2}\s*$/.test(raw)) {
		return { ...base, status: 'coordinates', candidates: [], total: 0, suggestions: [] };
	}

	const special = ix.unresolvable.get(base.key);
	if (special) {
		return { ...base, status: 'not_found', unsupported: { zh: special.zh, en: special.en, try: special.try }, candidates: [], total: 0, suggestions: [] };
	}

	const results = [];
	const mismatched = [];
	for (const r of readings(ix, raw)) {
		const pool = phrasePool(ix, r.phrase, r.aliasOnly);
		if (!pool.length) continue;
		const { hits, unverified } = applyQualifiers(pool, r.quals);
		if (!hits.length) { mismatched.push({ ...r, pool }); continue; }
		const kept = distinct(ix, hits);
		const unfiltered = r.quals.length ? distinct(ix, pool) : kept;
		results.push({ ...r, pool: kept, unverified, unfiltered });
		if (r.quals.length === 0 && r.phrase === raw) break; // the whole query names something: no re-reading
	}

	if (!results.length) {
		const regions = regionOnly(ix, raw);
		if (regions) {
			// "美国" / "Texas" / "BJ" (= Benin's ISO code): a region, not a place. Upstream's closest names ride along
			// so the client can ask "did you mean …" (BJ → 北京 through pinyin initials) without the skill guessing.
			const near = (upstream && Array.isArray(upstream.candidates) ? upstream.candidates : []).slice(0, cap);
			return { ...base, status: 'too_broad', regions, candidates: near.map(upstreamView), total: near.length, suggestions: [] };
		}
		if (mismatched.length) {
			const pool = distinct(ix, mismatched[0].pool);
			return { ...base, status: 'qualifier_mismatch', qualifiers: mismatched[0].quals.map((q) => q.text), candidates: pool.slice(0, cap).map(view), total: pool.length, suggestions: [] };
		}
		const near = (upstream && Array.isArray(upstream.candidates) ? upstream.candidates : []).slice(0, cap);
		if (near.length) {
			return { ...base, status: 'near', candidates: near.map(upstreamView), total: near.length, suggestions: [] };
		}
		const sugg = suggestions(ix, base.key, cap);
		return { ...base, status: 'not_found', candidates: [], total: 0, suggestions: sugg.map(view) };
	}

	// Readings that each resolve to one place agree → that place; otherwise everything they found is the choice.
	const singles = results.filter((r) => r.pool.length === 1);
	const sameAll = singles.length === results.length && singles.every((r) => r.pool[0].e.id === singles[0].pool[0].e.id || near(r.pool[0].e, singles[0].pool[0].e));
	if (sameAll) {
		const r = singles.find((x) => x.quals.length === 0) || singles[0];
		const h = r.pool[0];
		if (isProvince(h.e)) return { ...base, status: 'too_broad', regions: [h.e.name], candidates: [view(h)], total: 1, suggestions: [] };
		const caveats = [];
		if (h.alias && ['historical', 'nickname', 'approximate'].includes(h.alias.kind)) caveats.push({ code: `alias_${h.alias.kind}`, alias: h.alias.text, used: h.e.name });
		if (r.unverified.length) caveats.push({ code: 'qualifier_unverified', qualifiers: r.unverified });
		const qualifierNeeded = r.quals.length > 0 && r.unfiltered.length > 1;
		const out = {
			...base,
			status: qualifierNeeded && r.unverified.length && h.e.lib !== 'S' ? 'confirm' : 'resolved',
			matched_by: h.via,
			alias: h.alias ? { text: h.alias.text, kind: h.alias.kind } : null,
			phrase: r.phrase,
			qualifiers: r.quals.map((q) => ({ text: q.text, verified: !r.unverified.includes(q.text) })),
			caveats,
			match: view(h),
			candidates: [view(h)],
			total: 1,
			suggestions: [],
		};
		return out;
	}
	const union = [];
	for (const r of results) for (const h of r.pool) if (!union.some((u) => u.e.id === h.e.id || near(u.e, h.e))) union.push(h);
	union.sort(rank);
	return { ...base, status: 'ambiguous', candidates: union.slice(0, cap).map(view), total: union.length, suggestions: [] };
}

function near(a, b) {
	return Math.abs(a.lat - b.lat) <= NEAR_DEG && Math.abs(a.lng - b.lng) <= NEAR_DEG;
}
