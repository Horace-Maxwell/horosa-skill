// divination/election/lotsEngine.js
// 择日阿拉伯点全谱组装：七赫尔墨斯点 + 分科点 + 特殊构造点（荣誉/根基/水路/受焰替式）。
// 单一真值：福点=后端 Pars Fortuna（与盘面一致,不受前端反转口径分叉）;
// 精神点=福点关于上升的镜像（spirit = 2·ASC − fortune,恒满足 ASC−福 = 精神−ASC）。
// 口径消费（facts.eff）：erosConstruction(paulus 金/水式 ↔ valens 福-精神对式)、
// marriageTradition × querentGender（金土式/金日·火月式 四路）、
// lotsReversal（'schmidt'=五行星型点外层不反转,内嵌福/精神仍随区分）。
import { LOTS, computeLot, lotDispositor, computeHonores, computeBasis } from '../data/lots.js';
import { SIGNS, signOfLon, SIGN_ORDER } from '../data/signs.js';
import { PLANETS } from '../data/planets.js';
import { norm360 } from '../engine/utils.js';

const HERMETIC_PLANETARY = ['eros', 'erosAlt', 'erosValens', 'necessity', 'necessityValens', 'courage', 'victory', 'nemesis'];

function houseOfLon(facts, lon){
	if(lon === null || lon === undefined || !facts.houses) return null;
	const cusps = [];
	for(let i = 1; i <= 12; i++){
		const h = facts.houses[i];
		if(!h || h.lon === undefined || h.lon === null) return null;
		cusps.push(norm360(h.lon));
	}
	const L = norm360(lon);
	for(let i = 0; i < 12; i++){
		const a = cusps[i]; const b = cusps[(i + 1) % 12];
		const span = norm360(b - a);
		const off = norm360(L - a);
		if(span > 0 && off < span) return i + 1;
	}
	return null;
}

function rowOf(facts, def, lon, group, note){
	if(lon === null || lon === undefined) return null;
	const sign = signOfLon(lon);
	return {
		id: def.id, cn: def.cn, use: def.use || '', group,
		lon: Math.round(lon * 100) / 100,
		sign, signCn: SIGNS[sign] ? SIGNS[sign].cn : sign,
		signlon: Math.round((norm360(lon) % 30) * 10) / 10,
		house: houseOfLon(facts, lon),
		dispositor: lotDispositor(lon),
		dispositorCn: (PLANETS[lotDispositor(lon)] || {}).cn || lotDispositor(lon) || '—',
		note: note || null,
	};
}

// 依 reversal 口径取公式：schmidt=行星型点外层恒用昼式(不随区分对调);其余点不受此口径影响。
function formulaFor(def, isDiurnal, lotsReversal){
	if(!def.reverseBySect) return def.day;
	if(lotsReversal === 'schmidt' && HERMETIC_PLANETARY.indexOf(def.id) >= 0) return def.day;
	return isDiurnal ? def.day : def.night;
}

// 主入口：返回 { hermetic: rows[], topical: rows[], byId: {} }。
export function computeElectionLots(facts, eff){
	if(!facts || !facts.meta) return { hermetic: [], topical: [], byId: {} };
	const isDay = !!facts.meta.isDiurnal;
	const asc = facts.meta.ascLon;
	const fortune = facts.planets.fortune ? facts.planets.fortune.lon : null;
	if(asc === null || asc === undefined || fortune === null || fortune === undefined){
		return { hermetic: [], topical: [], byId: {} };
	}
	const spirit = norm360(2 * asc - fortune);

	// 富化黄经表：七政 + 上升 + 福/精神 + 宫头/宫主(2/8/9/12) + 巨蟹15°常点。
	const lons = { asc, fortune, spirit, cancer15: 105 };
	['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'].forEach((k) => {
		if(facts.planets[k] && facts.planets[k].lon !== undefined) lons[k] = facts.planets[k].lon;
	});
	const cuspRuler = (n, cuspKey, rulerKey) => {
		const h = facts.houses[n];
		if(!h || h.lon === undefined || h.lon === null) return;
		lons[cuspKey] = h.lon;
		const rp = h.ruler && facts.planets[h.ruler];
		if(rp && rp.lon !== undefined) lons[rulerKey] = rp.lon;
	};
	cuspRuler(2, 'second', 'secondRuler');
	cuspRuler(8, 'eighth', 'eighthRuler');   // eighth 已被死亡点用作首元
	cuspRuler(9, 'ninth', 'ninthRuler');
	cuspRuler(12, 'twelfth', 'twelfthRuler');

	const out = { hermetic: [], topical: [], byId: {} };
	// 闭包式 push:eff/facts/lons 恒在作用域,杜绝参数漏传。
	const push = (arr, id, group, note) => {
		const def = LOTS[id];
		if(!def) return;
		const lon = computeLot(formulaFor(def, isDay, eff && eff.lotsReversal), lons);
		const row = rowOf(facts, def, lon, group, note);
		if(row) arr.push(row);
	};

	// ── 七赫尔墨斯点 ─────────────────────────────────────────────
	out.hermetic.push(rowOf(facts, LOTS.fortune, fortune, 'hermetic'));
	out.hermetic.push(rowOf(facts, LOTS.spirit, spirit, 'hermetic'));
	const erosId = (eff && eff.erosConstruction === 'valens') ? 'erosValens' : 'erosAlt';
	const necId = (eff && eff.erosConstruction === 'valens') ? 'necessityValens' : 'necessity';
	push(out.hermetic, erosId, 'hermetic');
	push(out.hermetic, necId, 'hermetic');
	push(out.hermetic, 'courage', 'hermetic');
	push(out.hermetic, 'victory', 'hermetic');
	push(out.hermetic, 'nemesis', 'hermetic');

	// ── 婚姻点（传统 × 视角四路）──────────────────────────────────
	const female = !!(eff && eff.querentGender === 'female');
	if(eff && eff.marriageTradition === 'paulus'){
		push(out.topical, female ? 'marriagePaulusWomen' : 'marriagePaulusMen', 'topical');
	}else{
		push(out.topical, female ? 'marriageWomen' : 'marriageMen', 'topical');
	}

	// ── 分科点 ───────────────────────────────────────────────────
	// 父点:土在日光束下(燃烧/日下光)改「木−火」替式(昼夜不反,古法专置)。
	const sat = facts.planets.saturn;
	if(sat && (sat.combustion === 'combust' || sat.combustion === 'under_beams' || sat.combustion === 'cazimi')){
		push(out.topical, 'fatherFire', 'topical', '土在日光束下 → 用替式');
	}else{
		push(out.topical, 'father', 'topical');
	}
	['mother', 'brethren', 'childrenDor', 'sickness', 'surgeryLot', 'death',
		'travelLot', 'waterTravel', 'substance', 'friends', 'enemies', 'realEstate'].forEach((id) => {
		push(out.topical, id, 'topical');
	});

	// ── 特殊构造 ─────────────────────────────────────────────────
	const honores = computeHonores(asc, lons.sun, lons.moon, isDay);
	if(honores !== null){
		out.topical.push(rowOf(facts, { id: 'honores', cn: '荣誉点', use: `显赫·尊位(${isDay ? '昼投日旺白羊19°' : '夜投月旺金牛3°'})` }, honores, 'topical'));
	}
	const basis = computeBasis(asc, fortune, spirit);
	if(basis !== null){
		out.topical.push(rowOf(facts, { id: 'basis', cn: '根基点', use: '根基·支撑(福-精神较短弧加于上升)' }, basis, 'topical'));
	}

	out.hermetic = out.hermetic.filter(Boolean);
	out.topical = out.topical.filter(Boolean);
	out.hermetic.concat(out.topical).forEach((r) => { out.byId[r.id] = r; });
	return out;
}

// 「Lot 作上升」派生整宫：自该点所在星座起顺数,返回行星→派生宫位号表。
export function lotDerivedHouses(facts, lotLon){
	if(lotLon === null || lotLon === undefined) return null;
	const baseIdx = SIGN_ORDER.indexOf(signOfLon(lotLon));
	if(baseIdx < 0) return null;
	const out = {};
	Object.keys(facts.planets).forEach((k) => {
		const p = facts.planets[k];
		if(!p || !p.sign) return;
		const idx = SIGN_ORDER.indexOf(p.sign);
		if(idx < 0) return;
		out[k] = ((idx - baseIdx + 12) % 12) + 1;
	});
	return out;
}

// 用事关联点解析:topicMaster.topic_lots 里的 'marriageAuto'/'erosAuto' 按口径落到具体点。
export function resolveTopicLots(topic, eff){
	const ids = (topic && topic.topic_lots) || [];
	const female = !!(eff && eff.querentGender === 'female');
	return ids.map((id) => {
		if(id === 'marriageAuto'){
			if(eff && eff.marriageTradition === 'paulus') return female ? 'marriagePaulusWomen' : 'marriagePaulusMen';
			return female ? 'marriageWomen' : 'marriageMen';
		}
		if(id === 'erosAuto') return (eff && eff.erosConstruction === 'valens') ? 'erosValens' : 'erosAlt';
		return id;
	});
}

export default computeElectionLots;
