// 征象条件 → glyph 摘要片段(纯函数;渲染层按 seg.glyph 决定 AstroFont/普通字体)。
// glyph 字符取 AstroText.AstroMsg(ywastro 字体编码,缺字回退 AstroMsgCN 中文文本)。
//
// dexter/sinister 单源定义(与 Python election_scan.py docstring 逐字同款,勿各表):
//   以施方 A 为基, d = wrap180(lonB - lonA) ∈ (-180, 180];
//   d < 0 = dexter(右旋光线,B 在 A 的逆黄道序方向), d > 0 = sinister(左旋)。
import { AstroMsg, AstroMsgCN } from '../../../constants/AstroText.js';
import {
	CONDITION_TYPES, SIGN_OPTIONS, DIGNITY_STATE_OPTIONS, CONSIDERATION_ITEM_OPTIONS,
	PATTERN_OPTIONS, SHAPE_OPTIONS, NUMERIC_FIELD_OPTIONS, ANGLE_ID_OPTIONS, RELATION_OPTIONS,
} from './conditionTypes.js';

const SIGN_KEYS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
	'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'];

function txt(text){
	return { glyph: false, text };
}

function bodySeg(id){
	const glyph = AstroMsg[id];
	if(glyph){
		return { glyph: true, text: glyph, title: AstroMsgCN[id] || id };
	}
	return { glyph: false, text: AstroMsgCN[id] || id };
}

function signSeg(idx){
	const key = SIGN_KEYS[Number(idx) % 12];
	const glyph = AstroMsg[key];
	const cn = (SIGN_OPTIONS[Number(idx) % 12] || {}).label || key;
	if(glyph){
		return { glyph: true, text: glyph, title: cn };
	}
	return { glyph: false, text: cn };
}

function aspectSeg(angle){
	const key = `Asp${Number(angle)}`;
	const glyph = AstroMsg[key];
	if(glyph && glyph !== `${angle}º`){
		return { glyph: true, text: glyph, title: `${angle}°` };
	}
	return { glyph: false, text: `${angle}°` };
}

function optLabel(options, value){
	const hit = (options || []).find((o) => o.value === value);
	return hit ? hit.label : `${value}`;
}

function joinSegs(items, mapFn, sep = '/'){
	const out = [];
	(items || []).forEach((x, i) => {
		if(i){ out.push(txt(sep)); }
		out.push(mapFn(x));
	});
	return out;
}

const MOTION_CN = { applying: '入相位', separating: '出相位', any: '' };
const SIDE_CN = { dexter: '右相位', sinister: '左相位', any: '' };
const PARTILE_CN = { off: '', same_degree: '正相位(同度)', le3: '正相位(≤3°)', le1: '正相位(≤1°)' };
const OP_CN = { gt: '>', gte: '≥', lt: '<', lte: '≤', eq: '=', between: '∈' };

/** 返回摘要片段数组 [{glyph, text, title?}],供 pill 按段选字体渲染。 */
export function conditionSummary(leaf){
	if(!leaf || leaf.kind === 'group'){
		return [txt('条件组')];
	}
	const p = leaf.params || {};
	const t = leaf.type;
	if(t === 'aspect'){
		const segs = [txt('查找 '), bodySeg(p.planetA), txt(' 在 '), bodySeg(p.planetB), txt(' 的 '), aspectSeg(p.angle), txt(' 相位')];
		const mods = [SIDE_CN[p.side], MOTION_CN[p.motion], PARTILE_CN[p.partile]].filter(Boolean);
		const tail = [...mods, `orb ${p.orb}°`].filter(Boolean).join('·');
		segs.push(txt(`(${tail})`));
		return segs;
	}
	if(t === 'in_sign'){
		return [txt('查找 '), bodySeg(p.planet), txt(' 在 '), ...joinSegs(p.signs, signSeg)];
	}
	if(t === 'in_house'){
		return [txt('查找 '), bodySeg(p.planet), txt(` 在 ${(p.houses || []).join('/')} 宫`)];
	}
	if(t === 'reception'){
		const lv = (p.levels || []).map((x) => optLabel([{ value: 'ruler', label: '庙' }, { value: 'exalt', label: '旺' }, { value: 'trip', label: '三分' }, { value: 'term', label: '界' }, { value: 'face', label: '面' }], x)).join('·');
		return [txt('查找 '), bodySeg(p.planetA), txt(' 接纳 '), bodySeg(p.planetB), txt(`(${lv}${p.requireAspect ? '·须相位' : ''})`)];
	}
	if(t === 'mutual_reception'){
		return [txt('查找 '), bodySeg(p.planetA), txt(' 与 '), bodySeg(p.planetB), txt(` 互容(${p.pairing === 'same_level' ? '同级' : '任意对'})`)];
	}
	if(t === 'rulership'){
		if(p.mode === 'rules'){
			return [txt('查找 '), bodySeg(p.planetA), txt(' 主宰 '), bodySeg(p.planetB)];
		}
		return [txt('查找 '), bodySeg(p.planetA), txt(' 的主宰星是 '), bodySeg(p.planetB)];
	}
	if(t === 'besieged'){
		return [txt('查找 '), bodySeg(p.target), txt(' 被 '), bodySeg(p.besiegerA), txt('、'), bodySeg(p.besiegerB),
			txt(` 围攻(${p.mode === 'ray' ? '光线' : '体围'}·前${p.orbLeft}°后${p.orbRight}°${p.rescueEnabled ? '·计救援' : ''})`)];
	}
	if(t === 'dignity_state'){
		const st = (p.states || []).map((s) => optLabel(DIGNITY_STATE_OPTIONS, s)).join('·');
		return [txt('查找 '), bodySeg(p.planet), txt(` ${st}(${p.require === 'any' ? '任一' : '全部'})`)];
	}
	if(t === 'considerations'){
		return [txt(`查找 ${optLabel(CONSIDERATION_ITEM_OPTIONS, p.item)}`)];
	}
	if(t === 'aspect_pattern'){
		const apex = p.apex && p.apex !== 'any' ? ['(顶点 ', bodySeg(p.apex), txt(')')] : null;
		const segs = [txt(`查找 ${optLabel(PATTERN_OPTIONS, p.pattern)}`)];
		if(apex){ segs.push(txt(apex[0]), apex[1], apex[2]); }
		segs.push(txt(` orb ${p.orb}°`));
		return segs;
	}
	if(t === 'point_relation'){
		let pointSeg;
		if(p.pointKind === 'planet'){
			pointSeg = bodySeg(p.pointId);
		}else if(p.pointKind === 'angle'){
			pointSeg = txt(optLabel(ANGLE_ID_OPTIONS, p.pointId));
		}else if(p.pointKind === 'lot'){
			pointSeg = bodySeg('Pars Fortuna');
		}else{
			pointSeg = txt(`黄经 ${p.pointLon}°`);
		}
		const rel = p.relation === 'angles'
			? `相位 ${(p.angles || []).join('/')}°`
			: optLabel(RELATION_OPTIONS, p.relation);
		return [txt('查找 '), bodySeg(p.planet), txt(' 与 '), pointSeg, txt(` ${rel}(orb ${p.orb}°)`)];
	}
	if(t === 'numeric'){
		const f = optLabel(NUMERIC_FIELD_OPTIONS, p.field);
		const rhs = p.op === 'between' ? `[${p.value}, ${p.value2}]` : `${p.value}`;
		return [txt('查找 '), bodySeg(p.planet), txt(` ${f} ${OP_CN[p.op] || p.op} ${rhs}`)];
	}
	if(t === 'chart_shape'){
		return [txt(`查找 盘形=${optLabel(SHAPE_OPTIONS, p.shape)}${p.includeOuter ? '' : '(仅七政)'}`)];
	}
	if(t === 'midpoint'){
		const segs = [txt('查找 '), bodySeg(p.a)];
		if(p.b !== p.a){ segs.push(txt('/'), bodySeg(p.b)); }
		segs.push(txt(` 中点 ${p.modulus}°盘 合 `));
		if(p.targetKind === 'midpoint'){
			segs.push(bodySeg(p.targetPairA), txt('/'), bodySeg(p.targetPairB), txt(' 中点'));
		}else if(p.targetKind === 'planet'){
			segs.push(bodySeg(p.targetId));
		}else if(p.targetKind === 'angle'){
			segs.push(txt(optLabel(ANGLE_ID_OPTIONS, p.targetId)));
		}else{
			segs.push(txt(`黄经 ${p.targetLon}°`));
		}
		segs.push(txt(`(orb ${p.orb}°)`));
		return segs;
	}
	if(t === 'day_window'){
		return [txt(`查找 每日 ${p.from} → ${p.to}${p.to < p.from ? '(跨午夜)' : ''}`)];
	}
	if(t === 'light_dynamics'){
		const itemCn = {
			translation: '传光', collection: '聚光', prohibition: '阻止', frustration: '挫败',
			refranation: '收回', aversion: '不合意', bending: '交点弯曲', void: '空亡',
		}[p.item] || p.item;
		const seg = (id) => (id && id !== 'any' ? [bodySeg(id)] : [txt('任')]);
		const segs = [txt(`查找 ${itemCn} `)];
		if(p.item === 'translation'){ segs.push(...seg(p.mover), txt(' 自 '), ...seg(p.from), txt(' 至 '), ...seg(p.to)); }
		else if(p.item === 'collection'){ segs.push(...seg(p.collector), txt(' 聚 '), ...seg(p.p1), txt(' 与 '), ...seg(p.p2)); }
		else if(p.item === 'prohibition'){ segs.push(...seg(p.blocker), txt(' 截 '), ...seg(p.between), txt(' → '), ...seg(p.to)); }
		else if(p.item === 'frustration'){ segs.push(...seg(p.frustrated), txt(' 经 '), ...seg(p.via), txt(' 落空于 '), ...seg(p.to)); }
		else if(p.item === 'refranation'){ segs.push(...seg(p.planet), txt(' 弃入相 '), ...seg(p.to)); }
		else if(p.item === 'aversion'){ segs.push(...seg(p.a), txt(' 与 '), ...seg(p.b)); }
		else if(p.item === 'bending'){ segs.push(...seg(p.planet), txt(p.which === 'north' ? '(北弯)' : (p.which === 'south' ? '(南弯)' : ''))); }
		else if(p.item === 'void'){ segs.push(bodySeg('Moon'), txt(p.voidClassical ? '(古典30°窗)' : '(本座义)')); }
		return segs;
	}
	if(t === 'royal_attendance'){
		const slotCn = { first_occidental: '第一西没', first_oriental: '第一东升', any_occidental: '西没侧', any_oriental: '东升侧' }[p.slot] || p.slot;
		return [txt('查找 '), bodySeg(p.ref), txt(` 的${slotCn} = `), bodySeg(p.companion)];
	}
	if(t === 'sect_joy'){
		if(p.item === 'diurnal'){ return [txt('查找 昼盘(日在地平上)')]; }
		const cn = { of_sect: '同宗 of-sect', hayyiz: `得时(${(p.hayyizLevels || []).join('/')})`, house_joy: '宫喜乐(整宫)', sign_joy: '座喜乐' }[p.item] || p.item;
		return [txt('查找 '), bodySeg(p.planet), txt(` ${cn}`)];
	}
	if(t === 'degree_state'){
		const cn = { mansion: `月站第${p.mansion}宿`, monomoiria: '单度主星', darijan: 'Darijan主', quality: { B: '明度', D: '暗度', E: '空度', S: '烟度' }[p.quality] || '度质', special: { pitted: '陷度', azemene: '慢病度', increasing_fortune: '增福度' }[p.special] || '特殊度' }[p.item] || p.item;
		const segs = [txt('查找 '), bodySeg(p.planet), txt(` 在${cn}`)];
		if(p.item === 'monomoiria' || p.item === 'darijan'){ segs.push(txt(' = '), bodySeg(p.ruler)); }
		return segs;
	}
	if(t === 'pattern_overview'){
		const cn = { dragon_embrace: '龙拥', dragon_intercept: '龙截', lone_moon: '孤月独明', apriori_power: '先验权力', eight_kill: '八杀朝天', strong_jupiter: '强吉木星', afflicted_ruler: '后天凶星', sentient_link: '有情联结' }[p.item] || p.item;
		const segs = [txt(`查找 ${cn}`)];
		// 参与星段对全 item 统一附加(勿被 item 专属尾注短路——真机实抓:有情联结选了月亮
		// 摘要却不显示,两条不同条件在列表里无法区分)。
		if(p.planet && p.planet !== 'any' && p.item !== 'strong_jupiter'){ segs.push(txt('·'), bodySeg(p.planet)); }
		if(p.item === 'strong_jupiter'){ segs.push(txt(`(照耀≥${p.minLit}星${p.requireStrong ? '·强吉' : ''})`)); }
		else if(p.item === 'sentient_link'){ const pu = { any_pure: '任一有情', mundane_pure: '世俗纯粹', eso_pure: '玄纯粹', eso_mundane: '玄谋世俗', insentient: '无情' }[p.purity]; segs.push(txt(`(${pu})`)); }
		if((p.item === 'apriori_power' || p.item === 'eight_kill') && p.which && p.which !== 'any'){ segs.push(txt(`(${p.which === '8_12' ? '8·12' : '8·1'})`)); }
		return segs;
	}
	if(t === 'dispositor_cycle'){
		const cn = { final_is: '终极主宰 = ', final_exists: '存在终极主宰', in_loop: '互容环含 ', loop_exists: '存在互容环' }[p.mode] || p.mode;
		const segs = [txt(`查找 ${cn}`)];
		if(p.mode === 'final_is' || p.mode === 'in_loop'){ segs.push(bodySeg(p.planet)); }
		return segs;
	}
	if(t === 'almuten_is'){
		const segs = [txt(p.scope === 'topic' ? `查找 第${p.house}宫题主星 = ` : '查找 盘主胜利星 = ')];
		segs.push(bodySeg(p.planet));
		return segs;
	}
	if(t === 'distribution_state'){
		const kcn = { Fire: '火象', Earth: '土象', Air: '风象', Water: '水象', Cardinal: '基本', Fixed: '固定', Mutable: '变动', east: '东半球', west: '西半球', above: '地平上', below: '地平下' }[p.key] || p.key;
		const ocn = p.op === 'max' ? '严格最多' : `${OP_CN[p.op] || p.op}${p.value}`;
		return [txt(`查找 分布·${kcn} ${ocn}${p.includeOuter ? '(十星)' : '(七政)'}`)];
	}
	if(t === 'temperament'){
		const vcn = { Choleric: '胆汁质', Melancholic: '抑郁质', Sanguine: '多血质', Phlegmatic: '黏液质', Hot: '热', Cold: '冷', Dry: '干', Humid: '湿' }[p.value] || p.value;
		return [txt(`查找 气质·${vcn} ${p.op === 'dominant' ? '主导' : `${OP_CN[p.op] || p.op}${p.count}`}`)];
	}
	if(t === 'accidental_score'){
		const segs = [txt('查找 '), bodySeg(p.planet), txt(` 偶然尊贵${p.op === 'top1' ? '全盘最高' : `${OP_CN[p.op] || p.op}${p.value}分`}`)];
		return segs;
	}
	if(t === 'classical_pattern'){
		if(p.pattern === 'overcoming'){
			const seg = (id) => (id && id !== 'any' ? [bodySeg(id)] : [txt('任')]);
			const acn = { any: '', trine: '·三分', square: '·四分', sextile: '·六分' }[p.aspectKind] || '';
			return [txt('查找 压制 '), ...seg(p.over), txt(' 凌 '), ...seg(p.under), txt(acn)];
		}
		const cn = p.pattern === 'doryphory' ? '持矛护卫' : '度数围攻';
		const segs = [txt(`查找 ${cn}`)];
		if(p.planet && p.planet !== 'any'){ segs.push(txt('·'), bodySeg(p.planet)); }
		return segs;
	}
	if(t === 'eminence_level'){
		const bcn = { eminent: '显赫', notable: '显著', ordinary: '平凡', obscure: '暗晦' }[p.band] || p.band;
		return [txt(`查找 显赫度 ${p.op === 'band' ? bcn : `${OP_CN[p.op] || p.op}${p.value}分`}`)];
	}
	if(t === 'antiscia'){
		const tgt = p.targetKind === 'angle' ? txt(optLabel(ANGLE_ID_OPTIONS, p.targetAngle)) : bodySeg(p.targetId);
		return [txt('查找 '), bodySeg(p.planet), txt(p.kind === 'contra' ? ' 反映点 合 ' : ' 映点 合 '), tgt, txt(`(orb ${p.orb}°)`)];
	}
	if(t === 'fixed_star'){
		const tgt = p.targetKind === 'angle' ? txt(optLabel(ANGLE_ID_OPTIONS, p.targetAngle)) : bodySeg(p.targetId);
		return [txt(`查找 恒星 ${p.star} 合 `), tgt, txt(`(orb ${p.orb}°)`)];
	}
	if(t === 'planetary_hour'){
		return [txt(`查找 ${p.kind === 'day_ruler' ? '值日星' : '值时星'} = `), bodySeg(p.planet)];
	}
	if(t === 'lifespan_state'){
		const mcn = { ptolemy: '托', alcabitius: '卡', dorotheus: '多' }[p.method] || '';
		if(p.item === 'medical_crisis'){ return [txt(`查找 生命主受克(${mcn}法)`)]; }
		const icn = { hyleg_is: '生命主', alcocoden_is: '寿主星', epikratetor_is: '占控星', oikodespotes_is: '家主星', kurios_is: '盘主星' }[p.item] || p.item;
		const segs = [txt(`查找 ${icn}(${mcn}法) = `)];
		if(p.item === 'hyleg_is' || p.item === 'epikratetor_is'){
			const pcn = { sun: '太阳', moon: '月亮', asc: '上升', fortune: '福点', syzygy: '朔望点', none: '无' }[p.point] || p.point;
			if(p.point === 'sun'){ segs.push(bodySeg('Sun')); } else if(p.point === 'moon'){ segs.push(bodySeg('Moon')); } else { segs.push(txt(pcn)); }
		}else{
			if(p.planet === 'none'){ segs.push(txt('无')); } else { segs.push(bodySeg(p.planet)); }
		}
		return segs;
	}
	if(t === 'decan_state'){
		if(p.mode === 'talisman'){ return [txt(`查找 护符择时(ASC/`), bodySeg('Moon'), txt(` 正当第${(p.decans || []).join('/')}旬)`)]; }
		if(p.mode === 'ruler_is'){ return [txt('查找 '), bodySeg(p.planet), txt(' 所落旬主 = '), bodySeg(p.ruler)]; }
		return [txt('查找 '), bodySeg(p.planet), txt(` 落第${(p.decans || []).join('/')}旬`)];
	}
	const spec = CONDITION_TYPES[t];
	return [txt(`查找 ${spec ? spec.label : t}`)];
}

/** 纯文本版(存档/日志用)。 */
export function conditionSummaryText(leaf){
	return conditionSummary(leaf).map((s) => (s.glyph && s.title ? s.title : s.text)).join('');
}
