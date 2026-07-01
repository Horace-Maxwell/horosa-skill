// 大六壬 间传二十四格 + 三合全局五局 + 三会方(§17)。
// 三传步长:连茹(连珠)=±1(已由 LRPanStyle 识别);间传=±2(隔一位);三合=成局;三会=同方三支。
// 象义忠于《六壬大全》课经体例(公版)重述。

const ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const zi = (z) => ZHI.indexOf(`${z || ''}`.trim().substring(0, 1));

// 间传 24 格(三传支串 → 名/象义)。顺间(递增2)+ 逆间(递减2)。
export const JIANCHUAN_24 = {
	// —— 顺间(地支递增,隔一位)——
	'寅辰午': { name: '出阳', dir: '顺', luck: 'bad', text: '出三阳;病讼皆凶' },
	'辰午申': { name: '登三天', dir: '顺', luck: 'good', text: '龙登天位,主升迁、久旱得雨(顺间最吉)' },
	'午申戌': { name: '出三天', dir: '顺', luck: 'neutral', text: '亢龙有悔、事属高远;行人愆期' },
	'申戌子': { name: '涉三渊', dir: '顺', luck: 'bad', text: '龙涉渊不雨、目前阻隔、占官不吉' },
	'子寅辰': { name: '向阳', dir: '顺', luck: 'good', text: '自暗向明、先凶后吉(大吉)' },
	'丑卯巳': { name: '出户', dir: '顺', luck: 'good', text: '人出户、行人出、利干望(最吉)' },
	'卯巳未': { name: '盈阳', dir: '顺', luck: 'neutral', text: '阳气盈满' },
	'巳未酉': { name: '变盈', dir: '顺', luck: 'neutral', text: '阳极将衰、由盈转亏' },
	'未酉亥': { name: '入冥', dir: '顺', luck: 'bad', text: '自明入暗、渐入幽冥' },
	'酉亥丑': { name: '凝阴', dir: '顺', luck: 'bad', text: '阴气凝结、多主淫盗、事不明' },
	'亥丑卯': { name: '溟蒙', dir: '顺', luck: 'neutral', text: '事体不真、进退未决' },
	// —— 逆间(地支递减,隔一位)——
	'午辰寅': { name: '顾祖', dir: '逆', luck: 'good', text: '子回顾母、复旧庐、占官大吉(逆间最吉)' },
	'辰寅子': { name: '涉疑', dir: '逆', luck: 'bad', text: '自明退暗、涉历疑难' },
	'寅子戌': { name: '冥阴', dir: '逆', luck: 'bad', text: '阳退入阴、凶事先伏' },
	'子戌申': { name: '偃蹇', dir: '逆', luck: 'bad', text: '屡遇荆棘、举动昏昧' },
	'戌申午': { name: '悖戾', dir: '逆', luck: 'bad', text: '勉强退步、举动招灾' },
	'申午辰': { name: '凝阳', dir: '逆', luck: 'bad', text: '祸患滞留、谋望迟延' },
	'酉未巳': { name: '励明', dir: '逆', luck: 'good', text: '历阴暗后得明、由勉强而后成(勿与「励德」混)' },
	'未巳卯': { name: '回明', dir: '逆', luck: 'good', text: '缺月渐回、宜迟进、吉渐成(大吉)' },
	'巳卯丑': { name: '转悖', dir: '逆', luck: 'bad', text: '避明向暗、舍正返邪' },
	'卯丑亥': { name: '断涧', dir: '逆', luck: 'bad', text: '渐入深涧、暗长明消' },
	'丑亥酉': { name: '极阴', dir: '逆', luck: 'bad', text: '极阴、月隐西山' },
	'亥酉未': { name: '时遁', dir: '逆', luck: 'bad', text: '不得出而潜藏' },
};

// 三合全局五局(三传成三合局,§17.3)
export const SANHE_JU = {
	'亥卯未': { name: '曲直格', wuxing: '木', text: '动则如意、先屈后伸' },
	'寅午戌': { name: '炎上格', wuxing: '火', text: '事急速;一说虚浮不久' },
	'巳酉丑': { name: '从革格', wuxing: '金', text: '变动、革故从新、刑伤' },
	'申子辰': { name: '润下格', wuxing: '水', text: '浮游不安、宜施惠' },
};
// 三会方(§17.4)
export const SANHUI_FANG = {
	'寅卯辰': { name: '三会木方', wuxing: '木', text: '同方专气、木势会聚' },
	'巳午未': { name: '三会火方', wuxing: '火', text: '同方专气、火势会聚' },
	'申酉戌': { name: '三会金方', wuxing: '金', text: '同方专气、金势会聚' },
	'亥子丑': { name: '三会水方', wuxing: '水', text: '同方专气、水势会聚' },
};
const TU4 = new Set(['辰', '戌', '丑', '未']);

// 检测三传结构格(全局>三会>间传)。sanChuan=[初,中,末] 地支数组。返回 {kind,name,text,...} 或 null。
export function detectJianChuan(sanChuan){
	const b = (sanChuan || []).map((x) => `${x || ''}`.trim().substring(0, 1)).filter((x) => zi(x) >= 0);
	if(b.length !== 3){ return null; }
	const sortedKey = b.slice().sort().join('');
	// 三合全局(任意顺序成三合)
	const sanheKey = Object.keys(SANHE_JU).find((k) => k.split('').slice().sort().join('') === sortedKey);
	if(sanheKey){ return { kind: '全局', ...SANHE_JU[sanheKey] }; }
	// 稼穑(三传皆土)
	if(b.every((x) => TU4.has(x))){ return { kind: '全局', name: '稼穑格', wuxing: '土', text: '三传见三土、沉滞迟缓(稼穑·五局唯一不稳定者)' }; }
	// 三会方(任意顺序)
	const huiKey = Object.keys(SANHUI_FANG).find((k) => k.split('').slice().sort().join('') === sortedKey);
	if(huiKey){ return { kind: '三会', ...SANHUI_FANG[huiKey] }; }
	// 间传(严格按发用顺序的支串)
	const seq = b.join('');
	if(JIANCHUAN_24[seq]){ return { kind: '间传', ...JIANCHUAN_24[seq] }; }
	// 泛间传(步长±2 但非具名格)
	const d1 = ((zi(b[1]) - zi(b[0])) % 12 + 12) % 12;
	const d2 = ((zi(b[2]) - zi(b[1])) % 12 + 12) % 12;
	if(d1 === 2 && d2 === 2){ return { kind: '间传', name: '顺间传', dir: '顺', luck: 'neutral', text: '三传隔位顺连、跳跃间歇、占者事顺' }; }
	if(d1 === 10 && d2 === 10){ return { kind: '间传', name: '逆间传', dir: '逆', luck: 'neutral', text: '三传隔位逆连、跳跃间歇、占者事逆' }; }
	return null;
}
