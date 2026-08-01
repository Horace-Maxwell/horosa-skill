// 量化盘 8 虚星(海外因子)参考数据 —— 纯数据 + 纯函数,零副作用。
// 组别中性标签:第一组(前四星)/第二组(后四星)。三套轨道周期并列收录、不合并:
//   数据集甲 · 经典周期值(含年运动)   —— 旧版教学通行值;
//   数据集乙 · 现代精算值(当前计算口径)—— 本软件位置计算即此口径(星历内置根数),含距日 AU;
//   数据集丙 · 原始估值               —— 仅后四星有(其中第八星 745 年与甲/乙分歧最大)。
// ⚠️ 面板展示必须携带 TNP_CALIBRE_NOTE 口径说明;甲/丙仅供参考,不影响任何落点计算。
// 字形描述只述形状构造(供 UranianGlyphs 绘制与 hover 说明),不署人名与出处。
import * as AstroConst from '../constants/AstroConst.js';
import { FACTOR_MEANINGS } from './uranianMeanings.js';

// 组别标签(中性)。
export const TNP_GROUP_LABEL = { first: '第一组(前四星)', second: '第二组(后四星)' };

// 三套数据集标签(中性;b 即当前计算口径)。
export const TNP_DATASET_LABELS = {
	a: '数据集甲 · 经典周期值',
	b: '数据集乙 · 现代精算值(当前计算口径)',
	c: '数据集丙 · 原始估值',
};

// 口径提示(面板顶部固定一行)。
export const TNP_CALIBRE_NOTE = '位置计算采用现代精算值(数据集乙);甲/丙并列仅供参考,不合并、不影响落点。';

// 每颗:periodA/B/C=三套轨道周期(年;C 仅后四星);motionA=甲组年运动;au=距日(仅乙有);
// glyphDesc=字形构造描述。keyword 不物理复制,经 tnpReference() 从 FACTOR_MEANINGS 引用。
export const TNP_REFERENCE = {
	[AstroConst.CUPIDO]: {
		id: AstroConst.CUPIDO, label: '丘比特', group: 'first',
		glyphDesc: '木星与金星复合,金星"挂"于木星之内("超级金星")',
		periodA: 262, periodB: 262.5, periodC: null, motionA: '1°23′', au: 41.0,
	},
	[AstroConst.HADES]: {
		id: AstroConst.HADES, label: '哈迪斯', group: 'first',
		glyphDesc: '十字加左倾下弦月,月之下角与十字下横相交',
		periodA: 360, periodB: 360.6, periodC: null, motionA: '1°01′', au: 50.7,
	},
	[AstroConst.ZEUS]: {
		id: AstroConst.ZEUS, label: '宙斯', group: 'first',
		glyphDesc: '火箭状(已装填并瞄准)',
		periodA: 455, periodB: 455.6, periodC: null, motionA: '0°48.2′', au: 59.2,
	},
	[AstroConst.KRONOS]: {
		id: AstroConst.KRONOS, label: '克洛诺斯', group: 'first',
		glyphDesc: '尖顶/王冠状(喻"高处")',
		periodA: 521, periodB: 521.8, periodC: null, motionA: '0°48.1′', au: 64.8,
	},
	[AstroConst.APOLLON]: {
		id: AstroConst.APOLLON, label: '阿波罗', group: 'second',
		glyphDesc: '木星与双子座记号复合("超级木星/多木星")',
		periodA: 576, periodB: 589.4, periodC: 576, motionA: '0°37′', au: 70.4,
	},
	[AstroConst.ADMETOS]: {
		id: AstroConst.ADMETOS, label: '阿德墨托斯', group: 'second',
		glyphDesc: '金牛座亲缘记号加底线(铁砧状,喻不动)',
		periodA: 617, periodB: 631.7, periodC: 617, motionA: '0°35′', au: 73.7,
	},
	[AstroConst.VULCANUS]: {
		id: AstroConst.VULCANUS, label: '伏尔甘', group: 'second',
		glyphDesc: '锤状',
		periodA: 663, periodB: 679.0, periodC: 663, motionA: '0°32′', au: 77.4,
	},
	[AstroConst.POSEIDON]: {
		id: AstroConst.POSEIDON, label: '波塞冬', group: 'second',
		glyphDesc: '两枚相背新月由横杠相连(双鱼亲缘;与海王星记号须明显区分)',
		periodA: 720, periodB: 765.3, periodC: 745, motionA: '0°29′', au: 83.5,
	},
};

// 权威排序 = AstroConst.LIST_URANIAN(由近及远,第一组四星→第二组四星)。
export const TNP_ORDER = AstroConst.LIST_URANIAN.slice();

// 单星参考条目(附 keyword 引用,零重复文案);未知 id 返回 null。
export function tnpReference(id){
	const base = TNP_REFERENCE[id];
	if (!base) return null;
	const f = FACTOR_MEANINGS[id];
	return { ...base, keyword: f && f.keyword ? f.keyword : '' };
}

// 全表(按权威排序,供 B2 面板直接 map)。
export function tnpReferenceList(){
	return TNP_ORDER.map((id) => tnpReference(id)).filter(Boolean);
}

export default TNP_REFERENCE;
