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
};

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
