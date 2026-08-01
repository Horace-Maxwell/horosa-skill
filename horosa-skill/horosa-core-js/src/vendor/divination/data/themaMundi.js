// divination/data/themaMundi.js
// Thema Mundi「世界诞生盘」——教学构造盘(非生辰):巨蟹上升,七曜各居己庙 15°。
// 相位之性由盘几何导出:冲←土(疏离对峙)/四分←火(摩擦行动)/三分←木(丰盈和合)/六合←金(顺遂和谐)。
export const THEMA_MUNDI = [
	{ pos: 1, sign: 'cancer', signCn: '巨蟹', planet: 'moon', cn: '月亮', note: '上升·月之庙' },
	{ pos: 2, sign: 'leo', signCn: '狮子', planet: 'sun', cn: '太阳', note: '日之庙' },
	{ pos: 3, sign: 'virgo', signCn: '室女', planet: 'mercury', cn: '水星', note: '水庙之一' },
	{ pos: 4, sign: 'libra', signCn: '天秤', planet: 'venus', cn: '金星', note: '金庙之一' },
	{ pos: 5, sign: 'scorpio', signCn: '天蝎', planet: 'mars', cn: '火星', note: '火庙之一' },
	{ pos: 6, sign: 'sagittarius', signCn: '人马', planet: 'jupiter', cn: '木星', note: '木庙之一' },
	{ pos: 7, sign: 'capricorn', signCn: '摩羯', planet: 'saturn', cn: '土星', note: '土庙之一' },
];

export const THEMA_MUNDI_ASPECT_LESSONS = [
	'冲 180°：土星（摩羯15°）正冲月亮（巨蟹15°）→ 冲带土性——疏离、对峙、分隔。',
	'四分 90°：火星自白羊/天蝎各以 90° 照月与日 → 四分带火性——摩擦、行动。',
	'三分 120°：木星自人马三分日、自双鱼三分月 → 三分带木性——丰盈、和合。',
	'六合 60°：金星之庙（天秤/金牛）距二发光体各 60° → 六合带金性——顺遂、和谐。',
	'即「凶星授硬相位、吉星授柔相位」由盘几何导出，非任意规定。',
];

export const THEMA_MUNDI_NOTES = [
	'各星皆置座中 15°（少数传本作上升 1° 巨蟹，主流教学版取 15°）。',
	'庙位之序：自二发光体之庙（月巨蟹/日狮子）向两侧依行星速序授水、金、火、木、土。',
	'昼夜区分之基：日侧为昼半球、月侧为夜半球，巨蟹/狮子相邻为门户。',
];

export default THEMA_MUNDI;
