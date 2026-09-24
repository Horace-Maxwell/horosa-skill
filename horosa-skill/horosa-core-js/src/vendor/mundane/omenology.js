// 天象占(古籍天象篇)。可算部分:食盘四象限→四方(由四轴分割);其余为查表判读参考
// (色→行星效应/彗星/大气天象/条件式占辞结构)。显示层零章节号、来源中性。

export const ECLIPSE_COLOR_OMEN = [
	{ color: '黑 / 铅灰', planet: 'saturn', cn: '土', effect: '寒、歉、迟滞、艰难' },
	{ color: '白', planet: 'jupiter', cn: '木', effect: '相对温和、扩张之性' },
	{ color: '赤红', planet: 'mars', cn: '火', effect: '战、旱、火、酷烈' },
	{ color: '黄', planet: 'venus', cn: '金', effect: '和缓、丰饶之性' },
	{ color: '杂色', planet: 'mercury', cn: '水', effect: '多变、风、商旅之扰' },
];
export const ECLIPSE_COLOR_NOTE = '色覆全体 → 全国受影响;仅一部 → 仅相应区域。';

export const COMET_OMEN = {
	nature: '彗星本质生火与水星之效——战争、酷热、动荡。',
	rules: [
		'以彗头所在黄道部 + 彗尾所指,定受影响地域。',
		'以头之形定事件类别;以存续时长定持续期。',
		'东出 → 事速至;西没 → 事缓来。',
	],
};

export const WEATHER_OMENS = [
	{ key: 'sunrise', cn: '日出没', text: '日洁净稳 → 晴;杂色/偏赤、单侧幻日云/长芒 → 大风;暗铅灰带云/单侧晕/双侧幻日云 → 风雨。' },
	{ key: 'moon3d', cn: '月（朔望弦三日内）', text: '薄而洁 → 晴;薄而赤、暗面可见且乱 → 风;暗/苍/厚 → 风雨。' },
	{ key: 'halo', cn: '月晕', text: '一重渐散 → 晴;二三重 → 暴;黄而破 → 暴+大风;厚雾状 → 雪暴;越多越烈。' },
	{ key: 'cluster', cn: '恒星与星团', text: '异常明大 → 其方位来风;鬼宿星团晴空中变浊 → 大雨,清而闪 → 大风。' },
	{ key: 'meteor', cn: '流星', text: '自一方 → 该方来风;自对向两方 → 风乱;自四方 → 各种风暴(雷电等)。' },
	{ key: 'rainbow', cn: '虹', text: '晴雨交替之兆。彗星在天气义上 → 旱或风。' },
];

// 条件式占辞传统(结构参考,非逐条辞书):
export const OMEN_STRUCTURE_NOTE = '早期两河天象占为条件式「若(天象)…则(应验)…」结构,应验对象皆为王/朝/国/收成/战/灾——纯国家层面占卜;并有以月份+夜更细分之食占与消灾仪轨传统。';

// 四象限→四方(可算):以四轴把黄道分四段,食点落段定受灾方位;
// 传统以四方国框架读(此处输出方位,不预置现代国家对应——中性政策)。
const norm360 = (x) => (((x % 360) + 360) % 360);
export const QUADRANT_NATIONS = [
	{ key: 'east', cn: '东方', span: 'ASC→IC 段' },
	{ key: 'south', cn: '南方', span: 'IC→DSC 段' },
	{ key: 'west', cn: '西方', span: 'DSC→MC 段' },
	{ key: 'north', cn: '北方', span: 'MC→ASC 段' },
];

export function describeQuadrantNations(facts, eclipseLon){
	if(!facts || !facts.meta || facts.meta.ascLon == null || facts.meta.mcLon == null){ return null; }
	const asc = facts.meta.ascLon;
	const mc = facts.meta.mcLon;
	const ic = norm360(mc + 180);
	const dsc = norm360(asc + 180);
	const lon = eclipseLon != null ? eclipseLon : (facts.planets && facts.planets.sun ? facts.planets.sun.lon : null);
	if(lon == null){ return null; }
	const inArc = (x, from, to) => {
		const span = norm360(to - from);
		return norm360(x - from) < span;
	};
	let hit = null;
	if(inArc(lon, asc, ic)){ hit = 'east'; }
	else if(inArc(lon, ic, dsc)){ hit = 'south'; }
	else if(inArc(lon, dsc, mc)){ hit = 'west'; }
	else{ hit = 'north'; }
	const q = QUADRANT_NATIONS.find((x) => x.key === hit);
	return { quadrant: hit, cn: q.cn, span: q.span, note: '食落象限 → 该方受灾之传统框架;结合分野与可见带定具体地域。' };
}

export default { ECLIPSE_COLOR_OMEN, COMET_OMEN, WEATHER_OMENS, QUADRANT_NATIONS, describeQuadrantNations };
