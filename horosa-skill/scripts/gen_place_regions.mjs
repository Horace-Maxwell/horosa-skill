// Generate horosa-core-js/src/tools/placeData/regions.json — the qualifier table the skill's place
// acceptance rule (src/tools/placeResolve.js) uses to read "London, UK" / "美国纽约" / "Chicago, IL".
//
//   node scripts/gen_place_regions.mjs            # rewrite the file
//   node scripts/gen_place_regions.mjs --check    # exit 1 when the committed file differs
//
// Country names come from CLDR through Node's own ICU (Intl.DisplayNames, en / zh / zh-Hant, long + short),
// for every ISO 3166-1 alpha-2 code the vendored city library actually uses (citiesFull.json `r`). The
// hand-written part is only *names*: English/Chinese aliases CLDR does not list (USA, UK, Holland, 南韩 …)
// and the first-level subdivisions people type as qualifiers (US states, Canadian provinces, Australian
// states, the UK's four countries). Subdivisions are never verified against the library — its GeoNames
// rows carry a country code only — so placeResolve.js treats them as "same country, state unchecked".
// No coordinate is written here: a qualifier only filters library entries, it never places anything.
//
// The output depends on the CLDR version of the Node that runs this script (recorded in the file), so
// --check is a maintainer tool, not a CI gate: a different Node may spell a country differently.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CORE = path.join(HERE, '..', 'horosa-core-js', 'src');
const OUT = path.join(CORE, 'tools', 'placeData', 'regions.json');
const FULL = JSON.parse(fs.readFileSync(path.join(CORE, 'vendor', 'place', 'data', 'citiesFull.json'), 'utf8'));

const codes = [...new Set(FULL.map((c) => c.r).filter((r) => /^[A-Z]{2}$/.test(r)))].sort();

// Aliases CLDR's long/short display names do not produce. Names only.
const COUNTRY_ALIASES = {
	US: ['USA', 'U.S.', 'U.S.A.', 'America', 'United States of America', '美利坚合众国', '美利坚'],
	GB: ['UK', 'U.K.', 'Britain', 'Great Britain', '大不列颠', '英伦'],
	CN: ['PRC', "People's Republic of China", 'Mainland China', '中华人民共和国', '中國大陸', '中国大陆', '大陆'],
	HK: ['Hong Kong', 'Hong Kong SAR', 'HKSAR', '香港', '香港特区', '香港特别行政区'],
	MO: ['Macau', 'Macao', 'Macau SAR', 'Macao SAR', '澳门', '澳门特区', '澳门特别行政区'],
	TW: ['Taiwan', 'ROC', '台湾', '臺灣', '台灣'],
	KR: ['Korea', 'Republic of Korea', 'ROK', '南韩', '南朝鲜', '大韩民国'],
	KP: ['North Korea', 'DPRK', '朝鲜', '北朝鲜'],
	RU: ['Russian Federation', '俄国'],
	CZ: ['Czech Republic'],
	TR: ['Turkey'],
	MM: ['Burma'],
	NL: ['Holland', 'The Netherlands'],
	AE: ['UAE', 'U.A.E.', 'Emirates', '阿联酋'],
	CI: ['Ivory Coast'],
	VN: ['Viet Nam'],
	JP: ['日本国'],
	DE: ['Deutschland'],
	FR: ['France'],
	IT: ['Italia'],
	ES: ['España', 'Espana'],
	CH: ['Schweiz', 'Suisse'],
	AT: ['Österreich'],
	NZ: ['Aotearoa'],
	SA: ['KSA'],
	ZA: ['RSA'],
	PH: ['Philippine Islands'],
	VA: ['Vatican', 'Holy See'],
};

// First-level subdivisions people type as qualifiers. [ISO 3166-2 code suffix, English name, ...other names]
const SUBDIVISIONS = {
	US: [
		['AL', 'Alabama', '阿拉巴马'], ['AK', 'Alaska', '阿拉斯加'], ['AZ', 'Arizona', '亚利桑那'], ['AR', 'Arkansas', '阿肯色'],
		['CA', 'California', 'Calif', '加州', '加利福尼亚', '加利福尼亚州'], ['CO', 'Colorado', '科罗拉多'],
		['CT', 'Connecticut', '康涅狄格'], ['DE', 'Delaware', '特拉华'], ['DC', 'District of Columbia', '哥伦比亚特区'],
		['FL', 'Florida', '佛罗里达', '佛州'], ['GA', 'Georgia', '佐治亚', '乔治亚州'], ['HI', 'Hawaii', '夏威夷'],
		['ID', 'Idaho', '爱达荷'], ['IL', 'Illinois', '伊利诺伊', '伊利诺伊州'], ['IN', 'Indiana', '印第安纳'],
		['IA', 'Iowa', '艾奥瓦', '爱荷华'], ['KS', 'Kansas', '堪萨斯'], ['KY', 'Kentucky', '肯塔基'],
		['LA', 'Louisiana', '路易斯安那'], ['ME', 'Maine', '缅因'], ['MD', 'Maryland', '马里兰'],
		['MA', 'Massachusetts', 'Mass', '马萨诸塞', '麻省'], ['MI', 'Michigan', '密歇根'], ['MN', 'Minnesota', '明尼苏达'],
		['MS', 'Mississippi', '密西西比'], ['MO', 'Missouri', '密苏里'], ['MT', 'Montana', '蒙大拿'],
		['NE', 'Nebraska', '内布拉斯加'], ['NV', 'Nevada', '内华达'], ['NH', 'New Hampshire', '新罕布什尔'],
		['NJ', 'New Jersey', '新泽西'], ['NM', 'New Mexico', '新墨西哥'], ['NY', 'New York', 'New York State', '纽约州'],
		['NC', 'North Carolina', '北卡罗来纳', '北卡'], ['ND', 'North Dakota', '北达科他'], ['OH', 'Ohio', '俄亥俄'],
		['OK', 'Oklahoma', '俄克拉何马'], ['OR', 'Oregon', '俄勒冈'], ['PA', 'Pennsylvania', '宾夕法尼亚', '宾州'],
		['RI', 'Rhode Island', '罗德岛'], ['SC', 'South Carolina', '南卡罗来纳', '南卡'], ['SD', 'South Dakota', '南达科他'],
		['TN', 'Tennessee', '田纳西'], ['TX', 'Texas', '得克萨斯', '德克萨斯', '德州'], ['UT', 'Utah', '犹他'],
		['VT', 'Vermont', '佛蒙特'], ['VA', 'Virginia', '弗吉尼亚'], ['WA', 'Washington', 'Washington State', '华盛顿州'],
		['WV', 'West Virginia', '西弗吉尼亚'], ['WI', 'Wisconsin', '威斯康星'], ['WY', 'Wyoming', '怀俄明'],
		['PR', 'Puerto Rico', '波多黎各'],
	],
	CA: [
		['AB', 'Alberta', '阿尔伯塔'], ['BC', 'British Columbia', '不列颠哥伦比亚', '卑诗省'], ['MB', 'Manitoba', '曼尼托巴'],
		['NB', 'New Brunswick', '新不伦瑞克'], ['NL', 'Newfoundland and Labrador', 'Newfoundland', '纽芬兰'],
		['NS', 'Nova Scotia', '新斯科舍'], ['ON', 'Ontario', '安大略', '安大略省'], ['PE', 'Prince Edward Island', '爱德华王子岛'],
		['QC', 'Quebec', 'Québec', '魁北克'], ['SK', 'Saskatchewan', '萨斯喀彻温'], ['NT', 'Northwest Territories'],
		['NU', 'Nunavut'], ['YT', 'Yukon'],
	],
	AU: [
		['NSW', 'New South Wales', '新南威尔士'], ['VIC', 'Victoria', 'Victoria State', '维多利亚州'], ['QLD', 'Queensland', '昆士兰'],
		['WA', 'Western Australia', '西澳'], ['SA', 'South Australia', '南澳'], ['TAS', 'Tasmania', '塔斯马尼亚'],
		['ACT', 'Australian Capital Territory'], ['NT', 'Northern Territory'],
	],
	GB: [
		['ENG', 'England', '英格兰'], ['SCT', 'Scotland', '苏格兰'], ['WLS', 'Wales', '威尔士'],
		['NIR', 'Northern Ireland', '北爱尔兰'],
	],
};

// Chinese provinces whose library pinyin cannot be typed back (陕西 = "shan xi" = 山西) or whose usual
// English name is not pinyin. Values are the library's own admin entry names (citiesFull `n`).
const CN_ADMIN_ALIASES = {
	'Inner Mongolia': '内蒙古自治区',
	Tibet: '西藏自治区',
	Shaanxi: '陕西省',
	'Hong Kong': '香港特别行政区',
	'Hong Kong SAR': '香港特别行政区',
	Macau: '澳门特别行政区',
	Macao: '澳门特别行政区',
	Taiwan: '台湾省',
};
// Admin units the library files under 中华人民共和国 while its GeoNames rows use their own ISO code.
const CN_ADMIN_CODES = { 香港特别行政区: 'HK', 澳门特别行政区: 'MO', 台湾省: 'TW' };

const dn = (locale, style) => new Intl.DisplayNames([locale], { type: 'region', style });
const namers = [dn('en', 'long'), dn('en', 'short'), dn('zh', 'long'), dn('zh', 'short'), dn('zh-Hant', 'long'), dn('zh-Hant', 'short')];
const countries = {};
for (const code of codes) {
	const names = new Set();
	for (const n of namers) {
		const v = n.of(code);
		if (v && v !== code) names.add(v);
	}
	for (const a of COUNTRY_ALIASES[code] || []) names.add(a);
	countries[code] = [...names];
}
for (const code of Object.keys(COUNTRY_ALIASES)) {
	if (!countries[code]) throw new Error(`alias for ${code}, which the library does not use`);
}
for (const n of Object.keys(CN_ADMIN_CODES)) {
	if (!FULL.some((c) => c.n === n && c.r === '中华人民共和国')) throw new Error(`no admin entry ${n}`);
}
for (const n of Object.values(CN_ADMIN_ALIASES)) {
	if (FULL.filter((c) => c.n === n && !/^[A-Z]{2}$/.test(c.r)).length !== 1) throw new Error(`admin alias target ${n} is not unique`);
}

const out = {
	_provenance: {
		countries: `CLDR ${process.versions.cldr} via Node ${process.version} Intl.DisplayNames (en/zh/zh-Hant, long+short) for every ISO 3166-1 code in citiesFull.json; plus hand-written aliases (names only).`,
		subdivisions: 'ISO 3166-2 first-level codes + common English/Chinese names, hand-written (names only, no coordinates). Not verifiable against the library: its GeoNames rows carry a country code only.',
		generator: 'horosa-skill/scripts/gen_place_regions.mjs',
	},
	countries,
	subdivisions: SUBDIVISIONS,
	cn_admin_aliases: CN_ADMIN_ALIASES,
	cn_admin_codes: CN_ADMIN_CODES,
};
const text = `${JSON.stringify(out, null, '\t')}\n`;
if (process.argv.includes('--check')) {
	const now = fs.existsSync(OUT) ? fs.readFileSync(OUT, 'utf8') : '';
	if (now !== text) {
		console.error(`${path.relative(process.cwd(), OUT)} is out of date (or this Node has a different CLDR); rerun without --check`);
		process.exit(1);
	}
	console.log('regions.json up to date');
} else {
	fs.writeFileSync(OUT, text);
	console.log(`wrote ${OUT}: ${codes.length} countries, ${Object.values(SUBDIVISIONS).flat().length} subdivisions`);
}
