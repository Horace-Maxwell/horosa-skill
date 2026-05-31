// divination/lifespan/lifespanEngine.js
// 古典寿命格局引擎：生命主 Hyleg / 寿主星 Alcocoden+寿数 / 盘主体系(占控·家主·盘主) / 行星状态 / 医疗危机。
// 纯前端，跑在 chartFacts.buildFacts(result) 之上，复用 divination/data 尊贵表（与卜卦/择日同口径）。
// 算法依据：Ptolemy《四部星经》、Dorotheus《Carmen》、Alcabitius、Bonatti、al-Biruni（见各函数注释）。
import { SIGNS, signOfLon } from '../data/signs.js';
import { termRulerAt, faceAt, triplicityRulers } from '../data/dignities.js';
import { PLANETS, CLASSICAL_PLANETS, DIURNAL_SECT, NOCTURNAL_SECT } from '../data/planets.js';
import { signIndexOfLon, signedDelta, houseNumFromId } from '../engine/utils.js';
import {
	PLANETARY_YEARS, APHETIC_RULES, HYLEG_CANDIDATE_ORDER,
	HARD_ASPECTS, SOFT_ASPECTS, yearsBandForAngularity,
} from './lifespanData.js';

// ---- 几何/相位小工具（whole-sign beholding：古典 Hyleg/Alcocoden 标准用整宫相照）----
const SIGN_ASPECT = { 0: 0, 2: 60, 3: 90, 4: 120, 6: 180 }; // 整宫间隔→相位角；1/5=不相照(aversion)
const ASPECT_CN = { 0: '合', 60: '六合', 90: '刑', 120: '拱', 180: '冲' };
function round1(x){ return Math.round(x * 10) / 10; }
function signDistance(lonA, lonB){
	const a = signIndexOfLon(lonA), b = signIndexOfLon(lonB);
	const d = Math.abs(a - b);
	return Math.min(d, 12 - d);
}
function wholeSignAspect(lonA, lonB){
	if(lonA == null || lonB == null) return null;
	const d = signDistance(lonA, lonB);
	return Object.prototype.hasOwnProperty.call(SIGN_ASPECT, d) ? SIGN_ASPECT[d] : null;
}
function aspectName(deg){ return deg == null ? null : (ASPECT_CN[deg] || `${deg}°`); }
function angularityOfHouse(h){
	if([1, 4, 7, 10].indexOf(h) >= 0) return 'angular';
	if([2, 5, 8, 11].indexOf(h) >= 0) return 'succedent';
	return 'cadent';
}

// ---- 候选释放点 ----
// 从原始 /chart Result 取对象（syzygy 朔望点不在 facts.planets 时回退于此，避免改动共享 chartFacts → 卜卦/择日零影响）
function rawObj(facts, chartId){
	const r = facts.result;
	if(!r) return null;
	if(r.objectMap && r.objectMap[chartId]) return r.objectMap[chartId];
	const objs = (r.chart && r.chart.objects) || [];
	for(let i = 0; i < objs.length; i++){ if(objs[i].id === chartId) return objs[i]; }
	return null;
}
// 统一取点：sun/moon/fortune 来自 facts.planets；asc 来自 meta；syzygy 回退原始 Result。
function getPoint(facts, key){
	if(key === 'asc'){
		if(facts.meta && facts.meta.ascLon != null && facts.meta.ascSign){
			return { key: 'asc', lon: facts.meta.ascLon, sign: facts.meta.ascSign, signlon: facts.meta.ascDegree, house: 1 };
		}
		return null;
	}
	const p = facts.planets[key];
	if(p && p.lon != null && p.sign){ return { key, lon: p.lon, sign: p.sign, signlon: p.signlon, house: p.house }; }
	if(key === 'syzygy'){
		const o = rawObj(facts, 'Syzygy');
		if(o && o.lon != null){
			return { key: 'syzygy', lon: o.lon, sign: o.sign ? String(o.sign).toLowerCase() : signOfLon(o.lon), signlon: o.signlon, house: houseNumFromId(o.house) };
		}
	}
	return null;
}
function buildCandidates(facts){
	const c = {};
	['sun', 'moon', 'fortune', 'syzygy', 'asc'].forEach((k) => {
		const pt = getPoint(facts, k);
		if(pt) c[k] = pt;
	});
	return c;
}

// ---- 某点（星座+度）的五尊贵主星 ----
function dignityLordsAt(sign, lon, sect){
	const s = SIGNS[sign] || {};
	const trip = s.element ? triplicityRulers(s.element) : null;
	return {
		domicile: s.domicile || null,
		exaltation: s.exaltation ? s.exaltation.planet : null,
		triplicity: trip ? (sect === 'day' ? trip.day : trip.night) : null,
		term: termRulerAt(lon),
		face: faceAt(lon).ruler,
	};
}

// 发光体的星座性别偏好（昼太阳喜阳性座、夜月亮喜阴性座）；其余点无性别约束。
function genderPrefOf(key){
	if(key === 'sun') return 'masculine';
	if(key === 'moon') return 'feminine';
	return null;
}

// 阿尔卡比修斯 5° 规则：行星距下一宫头 5° 内，视作进入下一宫（需宫头经度，缺则跳过）。
function applyFiveDegreeRule(cand, facts, house){
	const cusps = facts.houses;
	if(!cusps || cand.lon == null || !house) return house;
	const nextH = (house % 12) + 1;
	const nc = cusps[nextH];
	if(nc && nc.lon != null){
		const d = signedDelta(cand.lon, nc.lon); // nextCusp − lon ∈ (−180,180]
		if(d > 0 && d <= 5) return nextH;
	}
	return house;
}

// 释放位判定（按作者）
function isAphetic(cand, method, facts){
	const rule = APHETIC_RULES[method] || APHETIC_RULES.ptolemy;
	let house = cand.house;
	if(rule.fiveDegreeRule) house = applyFiveDegreeRule(cand, facts, house);
	const allowed = rule.houses;
	if(house == null || !Object.prototype.hasOwnProperty.call(allowed, house)){
		return { aphetic: false, house, rank: null, reason: `第${house || '?'}宫非释放位` };
	}
	const rank = allowed[house];
	const g = (SIGNS[cand.sign] || {}).gender;
	// 阿尔卡比修斯：7/8/9 宫须星座性别与发光体宗派相符
	if(method === 'alcabitius' && rule.genderHouses && rule.genderHouses.indexOf(house) >= 0){
		const pref = genderPrefOf(cand.key);
		if(pref && g && g !== pref){
			return { aphetic: false, house, rank: null, reason: `第${house}宫须${pref === 'masculine' ? '阳性' : '阴性'}星座` };
		}
	}
	// 多罗修斯：阴阳匹配（太阳须阳性座、月亮须阴性座方为有效释放点；落反性别座=effeminatus 否决）
	if(rule.useGenderQuadrant){
		const pref = genderPrefOf(cand.key);
		if(pref && g && g !== pref){
			return { aphetic: false, house, rank: null, reason: `${cand.key === 'sun' ? '太阳落阴性座(effeminatus)' : '月亮落阳性座'}，多罗修斯否决` };
		}
	}
	return { aphetic: true, house, rank, reason: '释放位' };
}

// planet(key) 是否相照 hyleg（整宫相照）
function beholds(facts, planetKey, hyleg){
	const p = facts.planets[planetKey];
	if(!p) return false;
	return wholeSignAspect(p.lon, hyleg.lon) != null;
}

// ---- 寿主星 Alcocoden ----
function findAlcocoden(facts, hyleg, sect){
	if(!hyleg) return { alcocoden: null, viaDignity: null };
	const lords = dignityLordsAt(hyleg.sign, hyleg.lon, sect);
	const order = ['domicile', 'exaltation', 'term', 'triplicity', 'face']; // Bonatti 优先序
	for(let i = 0; i < order.length; i++){
		const dig = order[i];
		const planet = lords[dig];
		if(!planet) continue;
		if(beholds(facts, planet, hyleg)){
			const ap = facts.planets[planet] || null;
			const asp = ap ? wholeSignAspect(ap.lon, hyleg.lon) : null;
			return {
				alcocoden: planet,
				viaDignity: dig,
				aspectToHyleg: aspectName(asp),
				house: ap ? ap.house : null,
				angularity: ap && ap.house ? angularityOfHouse(ap.house) : null,
			};
		}
	}
	return { alcocoden: null, viaDignity: null };
}

// 寿数：基础(按宫位档) + 吉星加/凶星减(其小限,硬相位调整) + 焦伤封顶
function computeYears(facts, alc){
	if(!alc || !alc.alcocoden) return null;
	const py = PLANETARY_YEARS[alc.alcocoden];
	if(!py) return null;
	const band = yearsBandForAngularity(alc.angularity);
	let base = py[band];
	const modifiers = [];
	const ap = facts.planets[alc.alcocoden];
	CLASSICAL_PLANETS.forEach((pk) => {
		if(pk === alc.alcocoden || !ap) return;
		const pp = facts.planets[pk];
		if(!pp) return;
		const asp = wholeSignAspect(pp.lon, ap.lon);
		if(asp == null) return;
		const nat = PLANETS[pk] ? PLANETS[pk].nature : 'neutral';
		const least = PLANETARY_YEARS[pk] ? PLANETARY_YEARS[pk].least : 0;
		const soft = SOFT_ASPECTS.indexOf(asp) >= 0;   // 拱(120)/六合(60)
		const conj = asp === 0;
		if(nat === 'benefic'){
			const delta = (conj || soft) ? least : least / 2;   // 合/拱/六合 全加；刑/冲 半加
			base += delta; modifiers.push({ planet: pk, aspect: aspectName(asp), delta: round1(delta), kind: 'benefic' });
		} else if(nat === 'malefic'){
			if(soft) return;                                     // 凶星柔相位(拱/六合)从轻，不减
			base -= least; modifiers.push({ planet: pk, aspect: aspectName(asp), delta: -round1(least), kind: 'malefic' }); // 合/刑/冲 减全小限
		}
	});
	if(ap && ap.combustion === 'combust'){
		if(base > py.least){ base = py.least; modifiers.push({ planet: 'sun', aspect: '焦伤', delta: 0, kind: 'combust' }); }
	}
	return { band, baseYears: py[band], predictedYears: round1(base), modifiers };
}

// ---- 盘主体系 ----
const ALMUTEN_HYLEGIC = ['sun', 'moon', 'asc', 'fortune', 'syzygy'];
const HOUSE_SCORES = { 1: 12, 2: 6, 3: 3, 4: 9, 5: 7, 6: 1, 7: 10, 8: 4, 9: 5, 10: 11, 11: 8, 12: 2 };
const DIG_W = { domicile: 5, exaltation: 4, triplicity: 3, term: 2, face: 1 };
function computeAlmuten(facts){
	const sect = facts.meta.sect;
	const totals = {};
	CLASSICAL_PLANETS.forEach((p) => { totals[p] = 0; });
	const points = [];
	ALMUTEN_HYLEGIC.forEach((key) => {
		const pt = getPoint(facts, key);
		if(!pt || pt.lon == null || !pt.sign) return;
		const lon = pt.lon, sign = pt.sign;
		const lords = dignityLordsAt(sign, lon, sect);
		Object.keys(DIG_W).forEach((dig) => { const pl = lords[dig]; if(pl && totals[pl] != null) totals[pl] += DIG_W[dig]; });
		points.push(key);
	});
	CLASSICAL_PLANETS.forEach((p) => { const pp = facts.planets[p]; if(pp && pp.house && HOUSE_SCORES[pp.house]) totals[p] += HOUSE_SCORES[pp.house]; });
	let winner = null, max = -Infinity;
	CLASSICAL_PLANETS.forEach((p) => { if(totals[p] > max){ max = totals[p]; winner = p; } });
	return { totals, winner, points };
}

function rulersOfLife(facts, hyleg, almutenWinner){
	if(!hyleg) return null;
	const oikodespotes = (SIGNS[hyleg.sign] || {}).domicile || null;
	return {
		epikratetor: hyleg.key,                 // 占控星=选定的释放发光体/点
		oikodespotes,                            // 家主星=占控星座的本垣主（船主）
		kurios: almutenWinner,                   // 盘主星=综合 almuten 胜者（舵手）
		concordant: !!(oikodespotes && oikodespotes === almutenWinner),
		model: '船主(家主星)/舵手(盘主星)',
	};
}

// ---- 行星状态盘（纯聚合 facts.planets，无新天文）----
function planetStates(facts){
	const sect = facts.meta.sect;
	const surround = (facts.result && facts.result.surround) || null;
	const rows = CLASSICAL_PLANETS.map((pk) => {
		const p = facts.planets[pk];
		if(!p) return null;
		const inDay = DIURNAL_SECT.indexOf(pk) >= 0;
		const inNight = NOCTURNAL_SECT.indexOf(pk) >= 0;
		return {
			planet: pk,
			hayyiz: p.hayyiz || null,                 // 得时得地/得时不得地/失时
			sunState: p.combustion,                   // cazimi/combust/under_beams/null
			orient: p.orientality,                    // oriental/occidental
			motion: p.retro ? 'retro' : 'direct',     // 顺/逆
			sect: inDay ? 'diurnal' : (inNight ? 'nocturnal' : 'common'),
			inSect: (inDay && sect === 'day') || (inNight && sect === 'night'),
			house: p.house, sign: p.sign, dignityScore: p.dignityScore,
		};
	}).filter(Boolean);
	return { rows, sect, hasSurround: !!surround };
}

// ---- 医疗危机 v1（非宿命论；6宫+生命主受克+身体部位提示）----
function medicalCrisis(facts, hyleg, alc){
	const sixth = facts.houses[6] || null;
	const afflictions = [];
	if(hyleg){
		['mars', 'saturn'].forEach((mk) => {
			const p = facts.planets[mk];
			const asp = p ? wholeSignAspect(p.lon, hyleg.lon) : null;
			if(asp != null && HARD_ASPECTS.indexOf(asp) >= 0) afflictions.push({ planet: mk, aspect: aspectName(asp) });
		});
	}
	return {
		sixthSign: sixth ? sixth.sign : null,
		sixthRuler: sixth ? sixth.ruler : null,
		sixthOccupants: sixth ? (sixth.planets || []) : [],
		hylegAfflictions: afflictions,
		bodyHyleg: hyleg ? (SIGNS[hyleg.sign] || {}).body_parts || null : null,
		bodySixth: sixth && sixth.sign ? (SIGNS[sixth.sign] || {}).body_parts || null : null,
		alcocoden: alc ? alc.alcocoden : null,
		note: '医疗危机 v1：6 宫 + 生命主受凶星硬相位 + 身体部位提示；非宿命论判断，仅供研究参考。',
	};
}

// ---- 入口 ----
function selectHyleg(facts, method){
	const sect = facts.meta.sect;
	const cands = buildCandidates(facts);
	const order = HYLEG_CANDIDATE_ORDER[sect] || HYLEG_CANDIDATE_ORDER.day;
	const trace = [];
	const candidateRows = [];
	let chosen = null;
	const rule = APHETIC_RULES[method] || APHETIC_RULES.ptolemy;
	order.forEach((key) => {
		const c = cands[key];
		if(!c){ candidateRows.push({ key, aphetic: false, reason: '缺该点数据' }); return; }
		const test = isAphetic(c, method, facts);
		const row = {
			key, lon: c.lon, sign: c.sign, signlon: c.signlon, house: test.house,
			aphetic: test.aphetic, rank: test.rank, reason: test.reason,
			dignityLords: dignityLordsAt(c.sign, c.lon, sect),
		};
		candidateRows.push(row);
		if(test.aphetic && !chosen){
			if(rule.downgrade){
				const alc = findAlcocoden(facts, c, sect);
				if(!alc || !alc.alcocoden){ row.reason = '释放位但无寿主星 → 降级顺查'; trace.push(`${key}：释放位但无寿主星，降级`); return; }
			}
			chosen = c; row.reason = '选定为生命主'; trace.push(`${key}：命中释放位 → 生命主`);
		} else if(test.aphetic){
			trace.push(`${key}：亦为释放位（已选他者）`);
		} else {
			trace.push(`${key}：${test.reason}`);
		}
	});
	return { hyleg: chosen, candidates: candidateRows, trace };
}

export function runLifespan(facts, opts){
	opts = opts || {};
	const method = opts.method || 'ptolemy';
	if(!facts || !facts.meta) return null;
	const sect = facts.meta.sect;
	const hy = selectHyleg(facts, method);
	const alcBase = findAlcocoden(facts, hy.hyleg, sect);
	const years = computeYears(facts, alcBase);
	const almuten = computeAlmuten(facts);
	const rulers = rulersOfLife(facts, hy.hyleg, almuten.winner);
	const states = planetStates(facts);
	const medical = medicalCrisis(facts, hy.hyleg, alcBase);
	const mp = facts.meta.moonPhase;
	return {
		method, sect, isDiurnal: facts.meta.isDiurnal,
		birthType: mp ? (mp.phase === 'waxing' ? 'conjunctional' : 'preventional') : null,
		hyleg: hy.hyleg ? { key: hy.hyleg.key, lon: hy.hyleg.lon, sign: hy.hyleg.sign, signlon: hy.hyleg.signlon, house: hy.hyleg.house } : null,
		candidates: hy.candidates,
		trace: hy.trace,
		alcocoden: alcBase && alcBase.alcocoden ? Object.assign({}, alcBase, years || {}) : alcBase,
		almuten,
		rulers,
		states,
		medical,
	};
}

export { selectHyleg, findAlcocoden, computeYears, computeAlmuten, rulersOfLife, planetStates, medicalCrisis };
export default runLifespan;
