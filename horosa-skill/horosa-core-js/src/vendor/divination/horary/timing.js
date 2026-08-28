// divination/horary/timing.js
// 应期（构建清单 §5.1）：时间单位 = 征象星角续果 × 星座模式；数值 = 距准确相位的度数。
import { SIGNS } from '../data/signs.js';
import { DIR_BY_ELEMENT } from '../data/directions.js';
import { MEAN_DAILY_MOTION } from '../data/planets.js';

// [H2 应期修复] 九格表补全:传统口径为**单调递进**(角=最快带,续=中带,果=最慢带;
// 座内 动<变<固)。旧表五格塌成「几乎无望」且当单位拼进数字产出「约 3.2 几乎无望」畸形串。
// 果×固保留「极久(难期)」附注语义——由 hopeless 标记驱动文案分叉,不再作可拼数的单位。
const UNIT_TABLE = {
	angular: { cardinal: '天', mutable: '周', fixed: '月' },
	succedent: { cardinal: '周', mutable: '月', fixed: '年' },
	cadent: { cardinal: '月', mutable: '年', fixed: '年' },
};
const HOPELESS_CELL = { cadent: { fixed: true } };   // 果×固=极久且难期(数目仅供参考)

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
	let byHouseOverride = false;
	if(variant === 'byHouse'){
		const q = opts.otherKey && facts.planets[opts.otherKey];
		const both = (band) => p.angularity === band && q && q.angularity === band;
		if(both('cadent')){ unit = '天'; byHouseOverride = true; }
		else if(both('succedent')){ unit = '周'; byHouseOverride = true; }
		else if(both('angular')){ unit = '月'; byHouseOverride = true; }
	}
	const qty = (orbDeg !== null && orbDeg !== undefined) ? Math.round(orbDeg * 10) / 10 : null;
	// [复审C4] byHouse 真覆盖单位时抑制 hopeless 附注——否则「约 2.0 天…应期极久难期」自相矛盾。
	const hopeless = !byHouseOverride && !!((HOPELESS_CELL[p.angularity] || {})[mod]);
	const out = {
		unit, quantity: qty, hopeless,
		text: qty !== null
			? (hopeless
				? `约 ${qty} ${unit}，且征象星居果宫固定座 → 应期极久、事多迁延难期（数目仅供参考）`
				: `约 ${qty} ${unit}（征象星距准确相位 ${qty}°；南纬延长、北纬缩短）`)
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
	// [H2] 副应期:征象星/月亮换座(距 30° 的度数按当前速度折算天数)——传统「换座=事态换阶段」。
	if(qty !== null && p.signlon !== undefined && p.speed){
		const remain = 30 - p.signlon;
		const spd = Math.abs(p.speed);
		if(spd > 1e-6){
			out.signChange = { deg: Math.round(remain * 10) / 10, days: Math.round((remain / spd) * 10) / 10 };
		}
	}
	// [H2] 留驻修正(timingStationAware 门控,default 关=零回归):后端 stationState('S'留/'D'回顺)
	// 在场时,留驻星主导的应期附「临留驻,事有停滞/转折」注记。
	if(opts.timingStationAware && p.stationState){
		out.stationNote = p.stationState === 'S' ? '入相星临留驻(将转向)→ 事有停滞,应期常另起算' : '入相星刚回顺 → 停滞方过,事渐启动';
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
