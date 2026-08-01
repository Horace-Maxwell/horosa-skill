// divination/data/lots.js
// 阿拉伯点公式（含昼/夜反转）+ 定位星查询。来源：卜卦构建清单 §1.5。
// 公式以经度计算：lon = (a + b - c + 360k) % 360。
import { SIGNS, signOfLon } from './signs.js';

// 各点：{ id, cn, day:[a,b,c], night:[a,b,c] } —— 取 asc/moon/sun/... 的经度相加减。
// 标记位：asc, moon, sun, mercury, venus, mars, jupiter, saturn, lordX(宫主) 等由引擎传入经度表。
export const LOTS = {
	fortune: {
		id: 'fortune', cn: '福点', use: '财富·失物·方位·身体',
		day: ['asc', 'moon', 'sun'],   // ASC + Moon − Sun
		night: ['asc', 'sun', 'moon'], // 夜反转：ASC + Sun − Moon
	},
	spirit: {
		id: 'spirit', cn: '精神点', use: '心智·事业·名望',
		day: ['asc', 'sun', 'moon'],
		night: ['asc', 'moon', 'sun'],
	},
	marriage: {
		id: 'marriage', cn: '婚姻点', use: '婚姻（七宫问题）',
		// Hermes/常用：日间 ASC + 第七宫头(desc) − 金星；此处用 ASC + Venus − Saturn（男）/ ASC + Saturn − Venus（女）可按问者性别切换，默认通用式
		day: ['asc', 'venus', 'saturn'],
		night: ['asc', 'saturn', 'venus'],
	},
	children: {
		id: 'children', cn: '子女点', use: '子嗣（五宫）',
		day: ['asc', 'jupiter', 'saturn'],
		night: ['asc', 'saturn', 'jupiter'],
	},
	death: {
		id: 'death', cn: '死亡点', use: '八宫·危难',
		day: ['eighth', 'saturn', 'moon'],
		night: ['eighth', 'saturn', 'moon'],
	},
	// ── 核心可靠集扩充（卜卦 04§7.2/7.3，2026-07 补齐）──────────────────────────
	// reverseBySect: 夜盘是否对调 X/Y（福点例外：由 pofReversal 单独控制，见引擎 buildLots）。
	// 依赖点：eros/necessity/courage/victory/nemesis 公式含 fortune/spirit——由 computeLotsSet
	// 先解出福/精神注入 lons 再算（fortune/spirit 键）。
	eros: {
		id: 'eros', cn: '爱欲点(主流式)', use: '欲望·恋慕(五/七宫)', house: 5, reverseBySect: true,
		day: ['asc', 'spirit', 'fortune'],
		night: ['asc', 'fortune', 'spirit'],
	},
	erosAlt: {
		id: 'erosAlt', cn: '爱欲点(异说式)', use: '欲望(变体公式)', house: 5, reverseBySect: true,
		day: ['asc', 'venus', 'spirit'],
		night: ['asc', 'spirit', 'venus'],
	},
	necessity: {
		id: 'necessity', cn: '必然点', use: '强制·约束·争讼', house: 3, reverseBySect: true,
		day: ['asc', 'fortune', 'mercury'],
		night: ['asc', 'mercury', 'fortune'],
	},
	courage: {
		id: 'courage', cn: '勇气点', use: '胆略·行动(火星系)', house: 1, reverseBySect: true,
		day: ['asc', 'fortune', 'mars'],
		night: ['asc', 'mars', 'fortune'],
	},
	victory: {
		id: 'victory', cn: '胜利点', use: '成事·胜诉(木星系)', house: 10, reverseBySect: true,
		day: ['asc', 'spirit', 'jupiter'],
		night: ['asc', 'jupiter', 'spirit'],
	},
	nemesis: {
		id: 'nemesis', cn: '报应点', use: '宿业·迟滞(土星系)', house: 12, reverseBySect: true,
		day: ['asc', 'fortune', 'saturn'],
		night: ['asc', 'saturn', 'fortune'],
	},
	marriageMen: {
		id: 'marriageMen', cn: '婚姻点(男问)', use: '婚姻(男方视角)', house: 7, reverseBySect: true,
		day: ['asc', 'venus', 'saturn'],
		night: ['asc', 'saturn', 'venus'],
	},
	marriageWomen: {
		id: 'marriageWomen', cn: '婚姻点(女问)', use: '婚姻(女方视角)', house: 7, reverseBySect: true,
		day: ['asc', 'saturn', 'venus'],
		night: ['asc', 'venus', 'saturn'],
	},
	childrenDor: {
		id: 'childrenDor', cn: '子女点(通行式)', use: '子嗣(五宫,昼夜同式)', house: 5, reverseBySect: false,
		day: ['asc', 'saturn', 'jupiter'],
		night: ['asc', 'saturn', 'jupiter'],
	},
	sickness: {
		id: 'sickness', cn: '疾病点', use: '疾病(六宫)', house: 6, reverseBySect: false,
		day: ['asc', 'mars', 'saturn'],
		night: ['asc', 'mars', 'saturn'],
	},
	brethren: {
		id: 'brethren', cn: '兄弟点', use: '手足(三宫)', house: 3, reverseBySect: false,
		day: ['asc', 'jupiter', 'saturn'],
		night: ['asc', 'jupiter', 'saturn'],
	},
	father: {
		id: 'father', cn: '父亲点', use: '父(四宫)', house: 4, reverseBySect: true,
		day: ['asc', 'sun', 'saturn'],
		night: ['asc', 'saturn', 'sun'],
	},
	mother: {
		id: 'mother', cn: '母亲点', use: '母(四/十宫)', house: 4, reverseBySect: true,
		day: ['asc', 'moon', 'venus'],
		night: ['asc', 'venus', 'moon'],
	},
	// ── 择日全谱扩充（2026-07 R2;源:Paulus/Valens/Dorotheus/Bonatti/al-Biruni/Robson 公开古籍）──
	// 宫头系点须引擎注入 second/ninth/twelfth(宫头)与 *Ruler(宫主星黄经)——见 election/lotsEngine。
	travelLot: {
		id: 'travelLot', cn: '旅行点', use: '旅程·远行(九宫)', house: 9, reverseBySect: true,
		day: ['asc', 'ninth', 'ninthRuler'],
		night: ['asc', 'ninthRuler', 'ninth'],
	},
	waterTravel: {
		id: 'waterTravel', cn: '水路旅行点', use: '航海·水上行(专用式:巨蟹15°−土)', house: 9, reverseBySect: false,
		day: ['asc', 'cancer15', 'saturn'],
		night: ['asc', 'cancer15', 'saturn'],
	},
	substance: {
		id: 'substance', cn: '财货点', use: '钱财·动产(二宫)', house: 2, reverseBySect: true,
		day: ['asc', 'second', 'secondRuler'],
		night: ['asc', 'secondRuler', 'second'],
	},
	friends: {
		id: 'friends', cn: '朋友点', use: '友谊·望(十一宫)', house: 11, reverseBySect: true,
		day: ['asc', 'moon', 'mercury'],
		night: ['asc', 'mercury', 'moon'],
	},
	enemies: {
		id: 'enemies', cn: '仇敌点', use: '隐敌·暗害(十二宫)', house: 12, reverseBySect: true,
		day: ['asc', 'twelfth', 'twelfthRuler'],
		night: ['asc', 'twelfthRuler', 'twelfth'],
	},
	realEstate: {
		id: 'realEstate', cn: '地产点', use: '不动产·土地(四宫;昼夜方向诸家有互倒,此从土星主不动产式)', house: 4, reverseBySect: true,
		day: ['asc', 'saturn', 'moon'],
		night: ['asc', 'moon', 'saturn'],
	},
	surgeryLot: {
		id: 'surgeryLot', cn: '手术点', use: '开刀·刀刃(与疾病点互镜)', house: 6, reverseBySect: false,
		day: ['asc', 'saturn', 'mars'],
		night: ['asc', 'saturn', 'mars'],
	},
	fatherFire: {
		id: 'fatherFire', cn: '父亲点(受焰替式)', use: '父(土在日光束下时改木−火式,昼夜不反)', house: 4, reverseBySect: false,
		day: ['asc', 'jupiter', 'mars'],
		night: ['asc', 'jupiter', 'mars'],
	},
	marriagePaulusMen: {
		id: 'marriagePaulusMen', cn: '婚姻点(男·金日式)', use: '婚姻(男方·金日传统,昼夜不反)', house: 7, reverseBySect: false,
		day: ['asc', 'venus', 'sun'],
		night: ['asc', 'venus', 'sun'],
	},
	marriagePaulusWomen: {
		id: 'marriagePaulusWomen', cn: '婚姻点(女·火月式)', use: '婚姻(女方·火月传统,昼夜不反)', house: 7, reverseBySect: false,
		day: ['asc', 'mars', 'moon'],
		night: ['asc', 'mars', 'moon'],
	},
	erosValens: {
		id: 'erosValens', cn: '爱欲点(福-精神对式)', use: '欲望·恋慕(以福-精神对构造)', house: 5, reverseBySect: true,
		day: ['asc', 'fortune', 'spirit'],
		night: ['asc', 'spirit', 'fortune'],
	},
	necessityValens: {
		id: 'necessityValens', cn: '必然点(福-精神对式)', use: '约束·命定(爱欲对式之逆)', house: 3, reverseBySect: true,
		day: ['asc', 'spirit', 'fortune'],
		night: ['asc', 'fortune', 'spirit'],
	},
};

// ── 特殊构造点（非 ASC+X−Y 三元式）─────────────────────────────────────
// 荣誉点(Exaltation/Honores):昼投「日之旺度」白羊19°、夜投「月之旺度」金牛3°——
// 不对称反转:交换的是所投发光体旺度,非 X/Y 对调。
export function computeHonores(ascLon, sunLon, moonLon, isDiurnal){
	if(ascLon === null || ascLon === undefined) return null;
	if(isDiurnal){
		if(sunLon === null || sunLon === undefined) return null;
		return ((ascLon + 19 - sunLon) % 360 + 360) % 360;
	}
	if(moonLon === null || moonLon === undefined) return null;
	return ((ascLon + 33 - moonLon) % 360 + 360) % 360;
}

// 根基点(Basis):取福点与精神点之间「较短弧」加于上升(昼夜同式,非 A−B 反转)。
export function computeBasis(ascLon, fortuneLon, spiritLon){
	if([ascLon, fortuneLon, spiritLon].some((v) => v === null || v === undefined)) return null;
	let d = Math.abs(((fortuneLon - spiritLon) % 360 + 360) % 360);
	if(d > 180) d = 360 - d;
	return ((ascLon + d) % 360 + 360) % 360;
}

// 点集档（流派可配 lots_set）：minimal=现行为(福+精神,引擎自算) / core15=高可靠核心集全量。
export const LOTS_SETS = {
	minimal: ['fortune', 'spirit'],
	core15: ['fortune', 'spirit', 'eros', 'erosAlt', 'necessity', 'courage', 'victory', 'nemesis',
		'marriageMen', 'marriageWomen', 'childrenDor', 'sickness', 'death', 'brethren', 'father', 'mother'],
};

// 批算一组点：lons 须已含 asc/七政/eighth 与（由引擎按 pofReversal 口径先算好的）fortune/spirit。
// 其余点按各自 reverseBySect 取昼/夜公式。返回 [{id, cn, use, house, lon}]（缺输入的点跳过）。
export function computeLotsSet(lons, isDiurnal, keys){
	const out = [];
	(keys || []).forEach((k) => {
		const def = LOTS[k];
		if(!def) return;
		if(k === 'fortune' || k === 'spirit'){
			if(lons && lons[k] !== undefined && lons[k] !== null){
				out.push({ id: k, cn: def.cn, use: def.use, house: def.house || null, lon: lons[k] });
			}
			return;
		}
		const useNight = !!def.reverseBySect && !isDiurnal;
		const lon = computeLot(useNight ? def.night : def.day, lons);
		if(lon !== null){ out.push({ id: k, cn: def.cn, use: def.use, house: def.house || null, lon }); }
	});
	return out;
}

// 经度相加减求点位
export function computeLot(formula, lons){
	if(!formula) return null;
	const get = (k) => (lons && lons[k] !== undefined && lons[k] !== null ? lons[k] : null);
	const a = get(formula[0]); const b = get(formula[1]); const c = get(formula[2]);
	if(a === null || b === null || c === null) return null;
	return ((a + b - c) % 360 + 360) % 360;
}

// 点的定位星（dispositor）= 点所落星座的庙主（§Query IV / 失物用）
export function lotDispositor(lotLon){
	const sign = signOfLon(lotLon);
	return (SIGNS[sign] || {}).domicile || null;
}

// 取某点（按昼夜选公式）
export function lotPosition(lotId, lons, isDiurnal){
	const def = LOTS[lotId];
	if(!def) return null;
	return computeLot(isDiurnal ? def.day : def.night, lons);
}

export default LOTS;
