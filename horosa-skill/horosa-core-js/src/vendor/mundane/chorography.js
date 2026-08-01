// 世运盘 WP-7 地理分野 Chorography(§12.1 托勒密四象限 + §12.2 星座→地域对照)。
// 🔵 中性数据政策:此为传统占星「地域对应」学术参考,多源综合、各家有别,非任何现实地缘/政治断言。
//    现代国家/城市条目系 19–20 世纪占星家(Sepharial / Raphael / Carter)增补,与托勒密原文不同源。
// §12.4 ACG 星图线 = 已有独立页(占星地图),此处不做。

// §12.1 托勒密四象限(Tetrabiblos II.3):已知世界两线四分,每象限关联一个三方(元素),
// 三方主管行星统辖该象限;后世各家在此基础扩写,故「勿写死单一版本」——做成可切数据集。
// 四三方的地域取向由其三星座的 §12.2 条目归纳(非另造);主管行星沿用古典三分性主星(白天/夜间)。
export const MUNDANE_QUADRANTS = [
	{ key: 'fire', cn: '火三方', element: 'fire', signs: ['aries', 'leo', 'sagittarius'],
		rulers: { day: 'sun', night: 'jupiter', partner: 'saturn' }, region: '西欧·南欧(英·法·德·意·西)为主' },
	{ key: 'earth', cn: '土三方', element: 'earth', signs: ['taurus', 'virgo', 'capricorn'],
		rulers: { day: 'venus', night: 'moon', partner: 'mars' }, region: '近东·印度·中欧(波斯·希腊·印度)为主' },
	{ key: 'air', cn: '风三方', element: 'air', signs: ['gemini', 'libra', 'aquarius'],
		rulers: { day: 'saturn', night: 'mercury', partner: 'jupiter' }, region: '中欧·北方(比利时·奥地利·俄罗斯)为主' },
	{ key: 'water', cn: '水三方', element: 'water', signs: ['cancer', 'scorpio', 'pisces'],
		rulers: { day: 'venus', night: 'mars', partner: 'moon' }, region: '海洋·北方·北非(苏格兰·挪威·北非)为主' },
];

// §12.2 星座→代表性国家/地区 · 代表性城市(⚠️多源综合,逐字照录古籍,含「(现代)」等时代标注)。
// [G2 数据集真分叉] countries 拆两层:ptolemaic=古典-中世纪已见地域;modern=带「(现代)」
// 标注/新世界(美洲·澳洲·新西兰)等 19–20 世纪增补(拆层依据仅时代标注本身,不新增地名)。
// cities 古籍注明整体系后世增补 → 单层保存,由 describeChorography 按数据集档位门控显示。
export const SIGN_CHOROGRAPHY = {
	aries: { countries: { ptolemaic: ['英格兰', '法国(高卢)', '德国', '叙利亚', '巴勒斯坦', '丹麦'], modern: [] }, cities: ['Naples', 'Florence', 'Marseille', 'Birmingham'] },
	taurus: { countries: { ptolemaic: ['波斯(伊朗)', '爱尔兰', '塞浦路斯', '小亚细亚', '(波兰/俄南)'], modern: [] }, cities: ['Dublin', 'Mantua', 'Leipzig', 'St. Louis'] },
	gemini: { countries: { ptolemaic: ['比利时', '佛兰德', '埃及(下)', '亚美尼亚', '撒丁'], modern: ['美国(现代)'] }, cities: ['London', 'Versailles', 'Nuremberg', 'San Francisco'] },
	cancer: { countries: { ptolemaic: ['苏格兰', '荷兰', '北非(迦太基)', '(部分非洲)'], modern: ['新西兰'] }, cities: ['Amsterdam', 'Venice', 'Genoa', 'Manchester', 'New York(常引)'] },
	leo: { countries: { ptolemaic: ['意大利(罗马)', '西西里', '法国(部分)', '波希米亚', '阿尔卑斯'], modern: [] }, cities: ['Rome', 'Prague', 'Damascus', 'Chicago', 'Los Angeles'] },
	virgo: { countries: { ptolemaic: ['希腊', '两河/巴比伦', '亚述', '瑞士', '土耳其', '克里特', '西印度'], modern: [] }, cities: ['Paris', 'Boston', 'Heidelberg', 'Jerusalem(常引)'] },
	libra: { countries: { ptolemaic: ['奥地利', '西藏', '(埃及 Thebaid)'], modern: ['中国(现代常引)', '阿根廷'] }, cities: ['Vienna', 'Lisbon', 'Antwerp', 'Johannesburg'] },
	scorpio: { countries: { ptolemaic: ['摩洛哥', '挪威', '阿尔及利亚', '巴伐利亚', '加泰罗尼亚', '(犹地亚)'], modern: [] }, cities: ['Liverpool', 'Washington D.C.(常引)', 'New Orleans', 'Fez'] },
	sagittarius: { countries: { ptolemaic: ['西班牙', '匈牙利', '阿拉伯(Felix)', '托斯卡纳', '达尔马提亚'], modern: ['澳大利亚'] }, cities: ['Toledo', 'Cologne', 'Budapest', 'Sheffield', 'Naples(亦说)'] },
	capricorn: { countries: { ptolemaic: ['印度', '阿富汗', '马其顿', '色雷斯', '立陶宛', '(希腊部分)'], modern: ['墨西哥'] }, cities: ['Brussels', 'Oxford', 'Mexico City', 'Delhi', 'Brandenburg'] },
	aquarius: { countries: { ptolemaic: ['瑞典', '普鲁士', '阿拉伯', '埃塞俄比亚', '(波兰)'], modern: ['俄罗斯(现代)'] }, cities: ['Hamburg', 'Bremen', 'Salzburg', 'Moscow(现代常引)'] },
	pisces: { countries: { ptolemaic: ['葡萄牙', '加利西亚', '北非撒哈拉/尼罗', '斯堪的纳维亚', '卡拉布里亚'], modern: [] }, cities: ['Alexandria', 'Seville', 'Compostela', 'Regensburg'] },
};

export const CHOROGRAPHY_DISCLAIMER =
	'多源综合·各家有别:托勒密原文仅含古代地域,美洲/澳洲/现代国家系 19–20 世纪占星家(Sepharial·Raphael·Carter)增补,互有出入。此为传统占星学术参考,非现实地缘断言;严谨使用请回各自原典核对。';

// 数据集标签(随规则集 chorographyDataset 显示;古籍建议「可切数据集」,此处以标签+免责呈现多源性质)。
export const CHOROGRAPHY_DATASETS = {
	classical: { label: '托勒密古典', note: '托勒密 II.3 四象限三方框架;仅古代地域为本源,现代条目仅作参照。' },
	classical_medieval: { label: '古典+中世纪', note: '托勒密框架 + 中世纪阿拉伯/拉丁扩写;现代条目仅作参照。' },
	modern: { label: '现代综合', note: 'Sepharial / Raphael / Carter 等综合;含美洲·澳洲·现代国家(学术参考)。' },
};

const SIGN_ORDER = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces'];

// 给定盘 facts,取四轴(ASC/IC/DSC/MC)所落星座 → 对应分野(本年地理强调)。
// facts.meta.ascSign / facts.lons.{asc,mc};DSC=ASC 对宫、IC=MC 对宫。
export function describeChorography(facts, datasetKey) {
	if (!facts || !facts.meta) return null;
	const meta = facts.meta;
	const lons = facts.lons || {};
	const signOf = (lon) => (typeof lon === 'number') ? SIGN_ORDER[Math.floor((((lon % 360) + 360) % 360) / 30)] : null;
	const ascSign = meta.ascSign || signOf(lons.asc);
	if (!ascSign) return null;
	const opp = (k) => { const i = SIGN_ORDER.indexOf(k); return i < 0 ? null : SIGN_ORDER[(i + 6) % 12]; };
	const mcSign = signOf(lons.mc) || (meta.mcSign || null);
	const axes = [
		{ axis: 'ASC', cn: '上升(国民)', sign: ascSign },
		{ axis: 'MC', cn: '天顶(政府)', sign: mcSign },
		{ axis: 'DSC', cn: '下降(外邦)', sign: opp(ascSign) },
		{ axis: 'IC', cn: '天底(国土)', sign: mcSign ? opp(mcSign) : null },
	].filter((a) => a.sign && SIGN_CHOROGRAPHY[a.sign]);
	const dsKey = (datasetKey && CHOROGRAPHY_DATASETS[datasetKey]) ? datasetKey : 'modern';
	// [G2] 按数据集档位合成显示层(消费方接口不变,仍收 {countries:[],cities:[]} 平面数组):
	// classical / classical_medieval → 仅古典-中世纪地域层,城市(整体系后世增补)不列;
	// modern → 两层合并 + 城市全列。citiesOmitted 供 UI 出「城市条目系后世增补」注。
	const wantModern = dsKey === 'modern';
	const merged = axes.map((a) => {
		const raw = SIGN_CHOROGRAPHY[a.sign];
		const countries = wantModern ? raw.countries.ptolemaic.concat(raw.countries.modern) : raw.countries.ptolemaic.slice();
		return { ...a, regions: { countries, cities: wantModern ? raw.cities : [] } };
	});
	return { axes: merged, dataset: dsKey, datasetMeta: CHOROGRAPHY_DATASETS[dsKey], quadrants: MUNDANE_QUADRANTS, signOrder: SIGN_ORDER, citiesOmitted: !wantModern };
}

export { SIGN_ORDER as MUNDANE_SIGN_ORDER };
