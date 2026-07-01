// 六爻神煞(WP-F·表H):日干起(天乙贵人/禄神/羊刃/文昌)+ 三合局起(驿马/桃花/将星/华盖/劫煞/亡神)。
// 精简 9 种为默认集 + 文昌备选;可勾选;日起/年起可切(base)。神煞只作吉凶色彩微调,不越用神生克主干。

// ── 日干起 ──
const GUIREN = { 甲: '丑未', 乙: '子申', 丙: '亥酉', 丁: '亥酉', 戊: '丑未', 己: '子申', 庚: '丑未', 辛: '寅午', 壬: '卯巳', 癸: '卯巳' };
const LU = { 甲: '寅', 乙: '卯', 丙: '巳', 丁: '午', 戊: '巳', 己: '午', 庚: '申', 辛: '酉', 壬: '亥', 癸: '子' };
const YANGREN = { 甲: '卯', 丙: '午', 戊: '午', 庚: '酉', 壬: '子' }; // 阳干;阴干有异说,默认不取
const WENCHANG = { 甲: '巳', 乙: '午', 丙: '申', 丁: '酉', 戊: '申', 己: '酉', 庚: '亥', 辛: '子', 壬: '寅', 癸: '卯' };

// ── 三合局起(日支/年支所属三合局 → 各神煞支) ──
const SANHE_GROUP = { 申: 'A', 子: 'A', 辰: 'A', 寅: 'B', 午: 'B', 戌: 'B', 巳: 'C', 酉: 'C', 丑: 'C', 亥: 'D', 卯: 'D', 未: 'D' };
const DRIVE = {
	A: { 驿马: '寅', 桃花: '酉', 将星: '子', 华盖: '辰', 劫煞: '巳', 亡神: '亥' }, // 申子辰
	B: { 驿马: '申', 桃花: '卯', 将星: '午', 华盖: '戌', 劫煞: '亥', 亡神: '巳' }, // 寅午戌
	C: { 驿马: '亥', 桃花: '午', 将星: '酉', 华盖: '丑', 劫煞: '寅', 亡神: '申' }, // 巳酉丑
	D: { 驿马: '巳', 桃花: '子', 将星: '卯', 华盖: '未', 劫煞: '申', 亡神: '寅' }, // 亥卯未
};

// 神煞元数据:source 'gan'(干起)/'zhi'(三合支起);meaning 简注
export const SHENSHA_META = [
	{ name: '天乙贵人', key: 'guiren', source: 'gan', meaning: '逢凶化吉、贵助' },
	{ name: '禄神', key: 'lu', source: 'gan', meaning: '俸禄、衣食' },
	{ name: '羊刃', key: 'yangren', source: 'gan', meaning: '刚烈、刑伤' },
	{ name: '驿马', key: 'yima', source: 'zhi', meaning: '走动、出行、变迁' },
	{ name: '桃花', key: 'taohua', source: 'zhi', meaning: '情色、魅力' },
	{ name: '将星', key: 'jiangxing', source: 'zhi', meaning: '权位、统御' },
	{ name: '华盖', key: 'huagai', source: 'zhi', meaning: '孤高、艺术宗教' },
	{ name: '劫煞', key: 'jiesha', source: 'zhi', meaning: '劫夺、意外' },
	{ name: '亡神', key: 'wangshen', source: 'zhi', meaning: '失脱、虚耗' },
	{ name: '文昌', key: 'wenchang', source: 'gan', meaning: '文采、考试' }, // 备选(非默认9)
];
// 默认精简 9 种(不含文昌)
export const DEFAULT_SHENSHA_SET = ['天乙贵人', '禄神', '羊刃', '驿马', '桃花', '将星', '华盖', '劫煞', '亡神'];

function ganSha(name, gan){
	if(!gan){ return ''; }
	if(name === '天乙贵人'){ return GUIREN[gan] || ''; }
	if(name === '禄神'){ return LU[gan] || ''; }
	if(name === '羊刃'){ return YANGREN[gan] || ''; }
	if(name === '文昌'){ return WENCHANG[gan] || ''; }
	return '';
}
function zhiSha(name, zhi){
	const g = SANHE_GROUP[zhi];
	if(!g){ return ''; }
	return (DRIVE[g] && DRIVE[g][name]) || '';
}

// ── 计算启用神煞各自落支。ctx:{dayGan,dayZhi,yearGan,yearZhi};opts:{base:'day'|'year', set:[names]} ──
export function computeShenSha(ctx, opts){
	const c = ctx || {}, o = opts || {};
	const base = o.base === 'year' ? 'year' : 'day';
	const gan = base === 'year' ? c.yearGan : c.dayGan;
	const zhi = base === 'year' ? c.yearZhi : c.dayZhi;
	const set = o.set || DEFAULT_SHENSHA_SET;
	const res = {}; // name → [支...]
	SHENSHA_META.forEach((m) => {
		if(set.indexOf(m.name) < 0){ return; }
		const raw = m.source === 'gan' ? ganSha(m.name, gan) : zhiSha(m.name, zhi);
		if(raw){ res[m.name] = raw.split(''); }
	});
	return res;
}

// 某爻支所带神煞名列表
export function shenShaOnZhi(yaoZhi, shaMap){
	if(!yaoZhi || !shaMap){ return []; }
	return Object.keys(shaMap).filter((name) => shaMap[name].indexOf(yaoZhi) >= 0);
}

// 逐爻标注神煞(供中右栏 + AI 快照)。yaos 为 analyzeGua().yaos
export function annotateShenSha(yaos, ctx, opts){
	const shaMap = computeShenSha(ctx, opts);
	const perYao = (yaos || []).map((y) => ({ pos: y.pos, zhi: y.zhi, shensha: shenShaOnZhi(y.zhi, shaMap) }));
	return { shaMap, perYao };
}
