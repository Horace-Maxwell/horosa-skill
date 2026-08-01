// divination/babylon/babylonSchools.js —— 巴比伦占星两条流派轴(文类×派系)。
// 镜像 horarySchools 的 backend/judge 分离范式:
//   backend = 影响位置计算的参数(星历源/分至规范;null=不联动);
//   judge   = 前端解读/显示口径(微段变体/cubit/纪元)。
// 默认 swissA10 = 零回归基线(现代实位 + Aldebaran 锚 + A 规范)。

export const PRODUCTS = [
	{ key: 'horoscope', cn: '个人星盘', hint: '七曜清单·Lunar Three·分至天狼·食(无宫位/相位/上升)' },
	{ key: 'ephemeris', cn: '数理星历', hint: '五星会合现象表 + 月亮列(阶梯/锯齿)' },
	{ key: 'mulapin', cn: '图式天文', hint: '三道星表·偕日升·ziqpu·置闰(约前一千年汇编)' },
	{ key: 'microzodiac', cn: '微黄道', hint: '144 微段·×13/×277 历表映射' },
	{ key: 'melothesia', cn: '医疗占星', hint: '黄道-身体·配料·巫术·吉日' },
	{ key: 'eae', cn: '天象预兆', hint: '大预兆系列:前件→后件·四国地理·颜色' },
	{ key: 'almanac', cn: '年历预测', hint: '目标年周期法·年度摘要' },
	{ key: 'hemerology', cn: '吉日历', hint: '月宜忌·逐日吉凶体系' },
];

export const BABYLON_SCHEMES = {
	swissA10: {
		id: 'swissA10', cn: '现代实位·A 规范',
		desc: '现代天文实位(恒星黄道,毕宿锚)+ 分至在基本宫 10°(阶梯系统规范)。默认基线。',
		backend: { ephemerisSource: 'swiss', siderealAyanamsa: 'aldebaran_15tau', solstice: 'A10' },
		judge: { dodecaVariant: 'B', cubitDeg: 2.2, era: 'seleucid' },
	},
	systemA: {
		id: 'systemA', cn: '数理复原·阶梯(System A)',
		desc: '阶梯/分带算术:黄道分带、带内会合弧恒值、越界按比缩放;分至白羊 10°。',
		backend: { ephemerisSource: 'systemA', siderealAyanamsa: 'aldebaran_15tau', solstice: 'A10' },
		judge: { dodecaVariant: 'B', cubitDeg: 2.2, era: 'seleucid' },
	},
	systemB: {
		id: 'systemB', cn: '数理复原·锯齿(System B)',
		desc: '锯齿/线性算术:会合弧在极值间等差往返;分至白羊 8°。',
		backend: { ephemerisSource: 'systemB', siderealAyanamsa: 'aldebaran_15tau', solstice: 'B8' },
		judge: { dodecaVariant: 'B', cubitDeg: 2.2, era: 'seleucid' },
	},
};
export const SCHEME_ORDER = ['swissA10', 'systemA', 'systemB'];

export function schemeOf(id){
	return BABYLON_SCHEMES[id] || BABYLON_SCHEMES.swissA10;
}
// 仅非默认才下发(零回归:默认组合请求体字节不变)
export function backendFields(id, overrides){
	const sc = schemeOf(id);
	const eff = { ...sc.backend, ...(overrides || {}) };
	const out = {};
	if(eff.ephemerisSource && eff.ephemerisSource !== 'swiss'){ out.ephemerisSource = eff.ephemerisSource; }
	if(eff.solstice && eff.solstice !== 'A10'){ out.solstice = eff.solstice; }
	return out;
}
export function judgeOpts(id, overrides){
	const sc = schemeOf(id);
	return { ...sc.judge, ...(overrides || {}) };
}
export function presetOf(fields){
	const src = fields && fields.ephemerisSource;
	const sol = fields && fields.solstice;
	if(src === 'systemA'){ return 'systemA'; }
	if(src === 'systemB'){ return 'systemB'; }
	if(sol === 'B8'){ return 'systemB'; }
	return 'swissA10';
}
export function selectOptions(){
	return SCHEME_ORDER.map((id) => ({ value: id, label: BABYLON_SCHEMES[id].cn }));
}

// 派系设置项(渲染于模块设置面板;solstice 联动 scheme 但可显式覆盖)
export const BABYLON_PARAM_SPEC = [
	{ key: 'ephemerisSource', label: '位置源', type: 'select', appliesTo: ['horoscope', 'ephemeris', 'microzodiac'],
		options: [
			{ value: 'swiss', label: '现代实位' },
			{ value: 'systemA', label: '阶梯复原(A)' },
			{ value: 'systemB', label: '锯齿复原(B)' },
		], default: 'swiss' },
	{ key: 'solstice', label: '分至规范', type: 'select', appliesTo: ['horoscope', 'ephemeris', 'microzodiac'],
		options: [
			{ value: 'A10', label: '春分白羊 10°(A 规范)' },
			{ value: 'B8', label: '春分白羊 8°(B 规范)' },
		], default: 'A10', hint: '两规范几乎同时出现且长期并用;随位置源联动,可显式覆盖。' },
	{ key: 'dodecaVariant', label: '十二分变体', type: 'select', appliesTo: ['microzodiac'],
		options: [
			{ value: 'B', label: '加于点本身(楔文/古典)' },
			{ value: 'A', label: '加于宫起点' },
		], default: 'B', hint: '两变体结果黄经可差约 29°;楔文方案表行如前者。' },
	// cubitDeg(距星 cubit 度值)不设开关:肘读数只出现在占星页的参照星定位(/astroextra/analysis
	// 后端 _BABYLON_CUBIT_DEG=2.2 统计最佳),本技法页从不显示 —— 挂在这里就是死选择器(选了无处生效)。
	// era 只在「个人星盘」页被读取(BabylonHoroscope);数理星历/年历/吉日历三页不消费,
	// 声明进去=三页死下拉,故 appliesTo 收窄到真消费页。
	{ key: 'era', label: '纪元显示', type: 'select', appliesTo: ['horoscope'],
		options: [
			{ value: 'seleucid', label: '塞琉古纪元(S.E.)' },
			{ value: 'arsacid', label: '安息纪元(= S.E.−64)' },
		], default: 'seleucid' },
];
