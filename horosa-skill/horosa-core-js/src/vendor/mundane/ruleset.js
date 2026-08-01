// 世运盘 多流派规则集(§1.3 / §15.5)。每派归一化为开关对象,供 renderRight / buildAiSnapshot /
// describe 按 (规则集 × 盘式 × 子选项) 取用。默认 modern = 现状(含外行星、按相位 orb),零回归。
//
// 联动开关含义:
//   bodies            星体集合 classical(七曜+北交+恒星) / medieval(+阿拉伯点·尊贵) / modern(+♅♆♇) / barbault(5慢星为主)
//   ingressRule       入境主管 quarterly(季度递归) / aries_annual(全年)
//   eclipseTiming     食应期 ptolemy_hours(小时→年/月,主法) / none
//   orbScheme         容许度 moiety(古典 moiety) / by_aspect(现代按相位)
//   termsVariant      界 egyptian / ptolemaic;triplicityVariant 三分 dorothean / ptolemaic
//   chorographyDataset 分野 classical(四象限框架) / classical_medieval / modern(综合学术参考)
//   showOuterPlanets  是否显外行星;showOuterCycles 外行星周期;showBarbault Barbault 指数

// short = 左栏成对(半宽)下拉的**收起态**显示名;label 仍是展开列表与他处的全称,二者不可互换。
export const MUNDANE_RULESETS = [
	{ key: 'ptolemaic', label: '托勒密古典', short: '托勒密', note: '七曜+北交+恒星(无外行星);季度递归入境;moiety 容许度;古典四象限分野。' },
	{ key: 'medieval', label: '中世纪(Lilly)', short: '中世纪', note: '七曜+阿拉伯点·尊贵重;季度递归;moiety 容许度;古典+中世纪分野。' },
	{ key: 'modern', label: '现代(Carter–Campion)', short: '现代', note: '含 ♅♆♇(可选交点/Lilith);全年入境;按相位容许度;综合分野(学术参考)。' },
	{ key: 'barbault', label: 'Barbault 周期', short: 'Barbault', note: '五慢星为主;Barbault 行星周期指数;外行星会合周期。' },
];

export const MUNDANE_RULESET_DEFAULT = 'modern';

const CONFIGS = {
	ptolemaic: {
		// 托勒密古典:三分主用托勒密三分(Tetrabiblos),非多罗修斯。原四档全 dorothean → 托勒密三分(含水象表)永不可达=死选项;
		// 此档放开后托勒密三分经 describe.js→dignities.js(PTOLEMAIC 表)生效。默认档为 modern,本改不影响默认=零回归。
		bodies: 'classical', ingressRule: 'quarterly', eclipseTiming: 'ptolemy_hours',
		orbScheme: 'moiety', termsVariant: 'egyptian', triplicityVariant: 'ptolemaic',
		chorographyDataset: 'classical', showOuterPlanets: false, showOuterCycles: false, showBarbault: false,
	},
	medieval: {
		// 中世纪传统惯用托勒密界;三分仍多罗修斯。切此档 → 界主换表,年主/盘主据之重算。
		bodies: 'medieval', ingressRule: 'quarterly', eclipseTiming: 'ptolemy_hours',
		orbScheme: 'moiety', termsVariant: 'ptolemaic', triplicityVariant: 'dorothean',
		chorographyDataset: 'classical_medieval', showOuterPlanets: false, showOuterCycles: false, showBarbault: false,
	},
	modern: {
		bodies: 'modern', ingressRule: 'aries_annual', eclipseTiming: 'ptolemy_hours',
		orbScheme: 'by_aspect', termsVariant: 'egyptian', triplicityVariant: 'dorothean',
		chorographyDataset: 'modern', showOuterPlanets: true, showOuterCycles: true, showBarbault: true,
	},
	barbault: {
		bodies: 'barbault', ingressRule: 'aries_annual', eclipseTiming: 'none',
		orbScheme: 'by_aspect', termsVariant: 'egyptian', triplicityVariant: 'dorothean',
		chorographyDataset: 'modern', showOuterPlanets: true, showOuterCycles: true, showBarbault: true,
	},
};

// 归一化:未知/缺省 → 默认 modern(零回归)。返回 {key,label,note,...开关}。
export function rulesetConfig(key){
	const k = (key && CONFIGS[key]) ? key : MUNDANE_RULESET_DEFAULT;
	const meta = MUNDANE_RULESETS.find((r) => r.key === k) || MUNDANE_RULESETS[2];
	return Object.assign({ key: k, label: meta.label, note: meta.note }, CONFIGS[k]);
}

// 中盘渲染隐藏集(bodies 死字段就此激活为渲染白名单单源):古典/中世纪派中盘不绘 ♅♆♇
// glyph 及其相位线(纯前端渲染过滤,盘仍按引擎全量算,AstroChart hideBodies prop 消费;
// AstroChartCircle 的 glyph 与相位线同吃一个 planetDisplay Set → 剔除即两者齐隐)。
// modern/barbault 返回 null=不隐藏(默认档渲染路径逐字节一致,零回归锚)。
const OUTER_BODY_IDS = ['Uranus', 'Neptune', 'Pluto'];

export function hiddenBodiesFor(rulesetKey){
	const cfg = rulesetConfig(rulesetKey);
	return cfg.showOuterPlanets === false ? OUTER_BODY_IDS : null;
}

// 每派应绘天体键集说明(供帮助/流派卡「生效项」徽章;显示用,非过滤源)。
export const RULESET_BODY_LABEL = {
	classical: '七曜+北交+恒星',
	medieval: '七曜+阿拉伯点',
	modern: '含 ♅♆♇ 全体',
	barbault: '五慢星为主',
};
