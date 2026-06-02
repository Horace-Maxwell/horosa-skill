// divination/horary/timing.js
// 应期（构建清单 §5.1）：时间单位 = 征象星角续果 × 星座模式；数值 = 距准确相位的度数。
import { SIGNS } from '../data/signs.js';
import { DIR_BY_ELEMENT } from '../data/directions.js';

const UNIT_TABLE = {
	angular: { cardinal: '天', fixed: '月', mutable: '周' },
	succedent: { cardinal: '月', fixed: '几乎无望', mutable: '年' },
	cadent: { cardinal: '几乎无望/充满忧虑', fixed: '几乎无望', mutable: '几乎无望' },
};

export function timingFrom(facts, sigKey, orbDeg){
	const p = facts.planets[sigKey];
	if(!p) return null;
	const sign = SIGNS[p.sign];
	const mod = sign ? sign.modality : 'cardinal';
	const unit = ((UNIT_TABLE[p.angularity] || {})[mod]) || '不定';
	const qty = (orbDeg !== null && orbDeg !== undefined) ? Math.round(orbDeg * 10) / 10 : null;
	return {
		unit, quantity: qty,
		text: qty !== null
			? `约 ${qty} ${unit}（征象星距准确相位 ${qty}°；南纬延长、北纬缩短）`
			: `时间单位：${unit}（需有准确相位才能定数值）`,
	};
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
