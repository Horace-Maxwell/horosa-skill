// divination/horary/timing.js
// 应期（构建清单 §5.1）：时间单位 = 征象星角续果 × 星座模式；数值 = 距准确相位的度数。
import { SIGNS } from '../data/signs.js';
import { DIR_BY_ELEMENT } from '../data/directions.js';
import { MEAN_DAILY_MOTION } from '../data/planets.js';

const UNIT_TABLE = {
	angular: { cardinal: '天', fixed: '月', mutable: '周' },
	succedent: { cardinal: '月', fixed: '几乎无望', mutable: '年' },
	cadent: { cardinal: '几乎无望/充满忧虑', fixed: '几乎无望', mutable: '几乎无望' },
};

// 双体（变动）座主「变慢」注记的星座集合。
const DOUBLE_BODIED = ['gemini', 'virgo', 'sagittarius', 'pisces'];

// opts（可选;不传=既有输出字节不变）：
//   timingVariant —— 'applier'(默认,看入相星=现行) | 'applied'(看被入相星,9c 口径) | 'byHouse'(皆果→天/皆续→周/皆角→月)
//   appliedKey/otherKey —— 被入相星键（applied/byHouse 变体所需）
//   timingModifiers —— true 时输出修正链（速度缩放只改数目不改单位/双体变慢/逆行互入相更早/角宫意志）
//   timingSecondLaw —— true 时输出实时凌犯参考（t=Δ/|相对速度| 折算天数;仅供枝节参考）
export function timingFrom(facts, sigKey, orbDeg, opts){
	opts = opts || {};
	const variant = opts.timingVariant || 'applier';
	let baseKey = sigKey;
	if(variant === 'applied' && opts.appliedKey && facts.planets[opts.appliedKey]){ baseKey = opts.appliedKey; }
	const p = facts.planets[baseKey];
	if(!p) return null;
	const sign = SIGNS[p.sign];
	const mod = sign ? sign.modality : 'cardinal';
	let unit = ((UNIT_TABLE[p.angularity] || {})[mod]) || '不定';
	// byHouse 变体（Bonatti 口径）：两星宫类一致时以宫类直接定单位。
	if(variant === 'byHouse'){
		const q = opts.otherKey && facts.planets[opts.otherKey];
		const both = (band) => p.angularity === band && q && q.angularity === band;
		if(both('cadent')) unit = '天';
		else if(both('succedent')) unit = '周';
		else if(both('angular')) unit = '月';
	}
	const qty = (orbDeg !== null && orbDeg !== undefined) ? Math.round(orbDeg * 10) / 10 : null;
	const out = {
		unit, quantity: qty,
		text: qty !== null
			? `约 ${qty} ${unit}（征象星距准确相位 ${qty}°；南纬延长、北纬缩短）`
			: `时间单位：${unit}（需有准确相位才能定数值）`,
	};
	if(variant !== 'applier'){ out.variant = variant; out.baseKey = baseKey; }
	// —— 修正链（只出注记与修正后数目,单位种类不变;门控）——
	if(opts.timingModifiers && qty !== null){
		const mods = [];
		let adj = qty;
		const mean = MEAN_DAILY_MOTION[baseKey];
		if(mean !== undefined && p.speed !== undefined && p.speed !== null){
			if(Math.abs(p.speed) > mean){ adj = adj * 0.8; mods.push('入相星行度迅疾 → 应期酌短（×0.8，只改数目不改单位）'); }
			else if(Math.abs(p.speed) < mean){ adj = adj * 1.25; mods.push('入相星行度迟缓 → 应期酌延（×1.25）'); }
		}
		if(DOUBLE_BODIED.indexOf(p.sign) >= 0){ mods.push('入相星落双体星座 → 事有反复，应期偏慢'); }
		const other = opts.otherKey && facts.planets[opts.otherKey];
		if(p.retro || (other && other.retro)){ mods.push('存在逆行的相互入相 → 事可能比度数所示更早（以原数为上限）'); }
		if(p.angularity === 'angular'){
			mods.push(p.dignityScore >= 4 ? '角宫且有力 → 有意愿即行动，取快值' : '角宫但无力 → 行动力打折，取慢值');
		}
		out.modifiers = mods;
		out.adjustedQuantity = Math.round(adj * 10) / 10;
	}
	// —— 第二法：实时凌犯折算（门控;t=Δ/|相对速度|,只作枝节参考绝不替代主法）——
	if(opts.timingSecondLaw && qty !== null && opts.otherKey && facts.planets[opts.otherKey]){
		const rel = Math.abs((p.speed || 0) - (facts.planets[opts.otherKey].speed || 0));
		if(rel > 1e-6){
			out.secondLaw = {
				days: Math.round((orbDeg / rel) * 10) / 10,
				text: `实时凌犯参考：按当前相对速度折算约 ${Math.round((orbDeg / rel) * 10) / 10} 天后相位真实精确（仅供枝节参考，勿直接当事发日）。`,
			};
		}
	}
	return out;
}

// 方位（§Query IV）：以征象星所在星座元素定方向，角续果定距离
export function directionFrom(facts, sigKey){
	const p = facts.planets[sigKey];
	if(!p) return null;
	const sign = SIGNS[p.sign];
	const el = sign ? sign.element : null;
	const d = el ? DIR_BY_ELEMENT[el] : null;
	const dist = p.angularity === 'angular' ? '很近' : (p.angularity === 'succedent' ? '较远' : '很远/难寻');
	return d ? { dir: d.dir, terrain: d.terrain, distance: dist } : null;
}

export default timingFrom;
