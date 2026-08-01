// divination/engine/radicality.js
// 卜卦根本性门禁（构建清单 §2.6）+ Hephaistion 一般禁忌（2/8 宫）+ 痣验证（可选）
// + 判断前考量 19 条全表（05§3.1，含救济层与时主-命主双口径）。
// 警告不阻断，交用户决定；19 条为加法式新字段（considerations），既有 warnings 字节不变。
import { SIGNS, signOfLon } from '../data/signs.js';
import { PLANETS } from '../data/planets.js';
import { triplicityRulers } from '../data/dignities.js';
import { FIXED_STARS, starLonAt } from '../data/fixedStars.js';
import { bodyPartsOf, degreePosition, moleSide, moleFrontBack } from '../data/bodyParts.js';
import { aspectBetween, aspectsOf } from './aspectsEngine.js';
import { isBesieged } from './conditions.js';
import { norm360, angularDist } from './utils.js';

function cn(k){ return (PLANETS[k] || {}).cn || k; }

export function ascRulerKey(facts){
	const s = facts.meta.ascSign;
	return s && SIGNS[s] ? SIGNS[s].domicile : null;
}

// opts（卜卦流派可选；不传 = 择日/既有调用，行为字节不变）：
//   ascEarlyDeg/ascLateDeg —— 命度过早/过晚阈值（默认 3/27）
//   considerationsMode —— 'ignore' 略去「判断前考量」(命度早晚 + 月与七宫主刑冲)；'strict' 追加土星落七宫/七宫主受损
//   category —— 供 strict 判断七宫是否为事项宫(婚姻/诉讼/盗窃)以免误套「七宫=占星师」考量
export function radicality(facts, opts){
	opts = opts || {};
	const warnings = [];
	const ok = [];
	const meta = facts.meta;
	const ascRuler = ascRulerKey(facts);
	const lord1 = ascRuler;
	const earlyDeg = (typeof opts.ascEarlyDeg === 'number') ? opts.ascEarlyDeg : 3;
	const lateDeg = (typeof opts.ascLateDeg === 'number') ? opts.ascLateDeg : 27;
	const ignoreConsider = opts.considerationsMode === 'ignore';

	// 适合判断
	if(meta.hourRuler && lord1){
		const hr = PLANETS[meta.hourRuler]; const l1 = PLANETS[lord1];
		if(hr && l1 && (meta.hourRuler === lord1 || hr.sect === l1.sect)){
			ok.push('上升定位星与时主星同性质/同宗派 → 适合判断。');
		}
	}

	// 警告（§2.6）
	const ad = meta.ascDegree;
	if(ad !== null && ad !== undefined && !ignoreConsider){
		if(ad < earlyDeg) warnings.push({ key: 'asc_early', text: `上升落星座极早（${ad.toFixed(1)}°<${earlyDeg}°）：恐为时过早/无赖捏造，慎判。` });
		else if(ad > lateDeg) warnings.push({ key: 'asc_late', text: `上升落星座极晚（${ad.toFixed(1)}°>${lateDeg}°）：事已成定局/问者已知答案，慎判。` });
	}
	const moon = facts.planets.moon;
	const resolvedMoonVoc = (typeof opts.moonVoc === 'boolean') ? opts.moonVoc : (moon && moon.isVOC);
	if(moon){
		if(resolvedMoonVoc) warnings.push({ key: 'moon_voc', text: '月亮空相：问题可能不真或无果。' });
		if(moon.combustion === 'combust') warnings.push({ key: 'moon_combust', text: '月亮燃烧：受克严重，慎判。' });
		// 月与七宫主刑冲
		const l7 = facts.houses[7] && facts.houses[7].ruler;
		if(l7 && !ignoreConsider){
			const a = aspectBetween(facts, 'moon', l7);
			if(a && (a.angle === 90 || a.angle === 180)) warnings.push({ key: 'moon_l7_hard', text: `月亮与七宫主（${cn(l7)}）${a.angle === 90 ? '四分' : '对分'}：传统视为不宜判断。` });
		}
	}
	const sat = facts.planets.saturn;
	if(sat && sat.house === 1 && (sat.retro || sat.combustion === 'combust' || sat.dignityScore <= -4)){
		warnings.push({ key: 'saturn_asc', text: '土星落上升且受克：占星师/判断本身受阻。' });
	}
	// strict 口径：追加「判断前考量」——土星落七宫 / 七宫主受损（七宫为事项宫的类别不套用，避免与事项征象混淆）。
	if(opts.considerationsMode === 'strict'){
		const seventhIsQuesited = ['marriage', 'lawsuit', 'theft'].indexOf(opts.category) >= 0;
		if(sat && sat.house === 7) warnings.push({ key: 'saturn_7th', text: '土星落七宫：传统视为占星师/判断本身受扰，宜格外慎断。' });
		if(!seventhIsQuesited){
			const l7k = facts.houses[7] && facts.houses[7].ruler;
			const p7 = l7k && facts.planets[l7k];
			if(p7 && (p7.retro || p7.combustion === 'combust' || p7.dignityScore <= -4)){
				warnings.push({ key: 'l7_afflicted', text: `七宫主（${cn(l7k)}）逆行/燃烧/落陷：占星师征象星受损，慎断。` });
			}
		}
	}
	if(lord1 && facts.planets[lord1]){
		const lp = facts.planets[lord1];
		if(lp.combustion === 'combust') warnings.push({ key: 'l1_combust', text: `上升定位星（${cn(lord1)}）燃烧：问卜者状态受灼。` });
		if(lp.retro) warnings.push({ key: 'l1_retro', text: `上升定位星（${cn(lord1)}）逆行：事态反复。` });
		// Hephaistion 2/8 禁忌
		if(lp.house === 2 || lp.house === 8) warnings.push({ key: 'l1_in_2_8', text: `上升主落 ${lp.house} 宫（Hephaistion 忌 2/8 宫）。` });
	}

	const suitable = warnings.length === 0;
	const out = { suitable, warnings, ok, ascRuler, moleHints: moleHints(facts) };
	// 19 条考量全表（加法式；opts.considerations===false 可关）。
	if(opts.considerations !== false){
		out.considerations = considerations19(facts, opts);
		out.hourAgreement = hourAgreementTest(facts, opts);
	}
	return out;
}

// ── 燃烧之路边界三变体（04§2.3）：standard=天秤15°–天蝎15°;scorpioFull=天秤后15°+天蝎全宫;
//    bothFull=天秤+天蝎全段。──
export function viaCombustaRange(variant){
	if(variant === 'scorpioFull') return [195, 240];
	if(variant === 'bothFull') return [180, 240];
	if(variant === 'narrow') return [208, 217];   // 后端旧硬编码窄口径(2026-07 归正后作历史变体保留)
	return [195, 225];
}

function starLonNow(nameEn, facts){
	const st = FIXED_STARS.find((s) => s.name_en === nameEn);
	if(!st) return null;
	let year = 2000;
	try{
		const p = facts && facts.result && facts.result.params;
		const ds = p && (p.birth || p.date);
		if(ds){ const m = String(ds).match(/(-?\d{3,4})/); if(m){ year = Number(m[1]); } }
	}catch(e){ /* noop */ }
	return starLonAt(st.lon_1995, year);
}

// ── 时主-命主一致（正面根基确认，05§3.3/3.4）：
//  ① 同星；② 同三分（Lilly 版=时主是上升星座三方主之一 / Bonatti 版=时主落座与命主落座同元素）；
//  ③ 同性质（行星体液相同）。variant：'lilly'|'bonatti'|'either'(默认)。不一致不弃盘。──
const HUMOURS = { saturn: '冷干', jupiter: '热湿', mars: '热干', sun: '热干', venus: '冷湿', mercury: '冷干', moon: '冷湿' };
export function hourAgreementTest(facts, opts){
	opts = opts || {};
	const variant = opts.hourAgreementVariant || 'either';
	const hour = facts.meta.hourRuler;
	const lord1 = ascRulerKey(facts);
	if(!hour || !lord1) return { available: false, agree: false, hits: [], variant };
	const hits = [];
	if(hour === lord1) hits.push({ key: 'same_planet', text: '时主星＝命主星（同星）' });
	// ② 同三分
	const ascSign = SIGNS[facts.meta.ascSign] || {};
	const tripP = triplicityRulers(ascSign.element, 'ptolemaic') || {};
	const tripD = triplicityRulers(ascSign.element) || {};
	const lillyTrip = [tripP.day, tripP.night, tripD.day, tripD.night, tripD.participating].filter(Boolean);
	if((variant === 'lilly' || variant === 'either') && lillyTrip.indexOf(hour) >= 0){
		hits.push({ key: 'triplicity_lilly', text: '时主星是上升星座三方主之一（行星-星座统辖口径）' });
	}
	if(variant === 'bonatti' || variant === 'either'){
		const hp = facts.planets[hour]; const lp = facts.planets[lord1];
		const he = hp && SIGNS[hp.sign] ? SIGNS[hp.sign].element : null;
		const le = lp && SIGNS[lp.sign] ? SIGNS[lp.sign].element : null;
		if(he && le && he === le) hits.push({ key: 'triplicity_bonatti', text: '时主星与命主星落座同元素（两星落点口径）' });
	}
	if(HUMOURS[hour] && HUMOURS[hour] === HUMOURS[lord1]) hits.push({ key: 'same_nature', text: `时主星与命主星同性质（${HUMOURS[hour]}）` });
	return { available: true, agree: hits.length > 0, hits, variant, hourRuler: hour, lord1 };
}

// ── 判断前考量 19 条全表（05§3.1）。每条：
//  { idx, key, hit, severity('warn'|'info'|'unavailable'), mitigable, mitigatedBy[], mitigated, text_zh }
//  balance_even(14) 由引擎在裁决后回填（needsVerdict 占位）；蚀点(15)无蚀数据时降级 unavailable 不误报。──
export function considerations19(facts, opts){
	opts = opts || {};
	const meta = facts.meta;
	const list = [];
	const lord1 = ascRulerKey(facts);
	const lp = lord1 && facts.planets[lord1];
	const moon = facts.planets.moon;
	const sigKeys = (opts.sigs && [opts.sigs.querentKey, opts.sigs.quesitedKey].filter(Boolean)) || (lord1 ? [lord1] : []);
	const earlyDeg = (typeof opts.ascEarlyDeg === 'number') ? opts.ascEarlyDeg : 3;
	const lateDeg = (typeof opts.ascLateDeg === 'number') ? opts.ascLateDeg : 27;
	const add = (idx, key, hit, o) => list.push({ idx, key, hit: !!hit, severity: 'warn', mitigable: false, mitigatedBy: [], mitigated: false, ...(o || {}) });

	// 1/2 上升过早/过晚（救济：过早=问卜者年轻体貌相合[自评]；过晚=事件盘）
	const ad = meta.ascDegree;
	add(1, 'asc_early', ad !== null && ad !== undefined && ad < earlyDeg, {
		mitigable: true, mitigatedBy: ['问卜者年轻且体貌合上升星座（自评确认）'],
		mitigated: !!opts.confirmYouthMatch,
		text_zh: `上升过早（<${earlyDeg}°）：事情尚未成熟`,
	});
	add(2, 'asc_late', ad !== null && ad !== undefined && ad > lateDeg, {
		mitigable: true, mitigatedBy: ['事件盘（有确定客观时刻）不受此限'],
		mitigated: !!opts.isEventChart,
		text_zh: `上升过晚（>${lateDeg}°）：事已定局/已问过他人`,
	});
	// 3 月空（救济：金牛/巨蟹/射手/双鱼 或 主要象征星极强）
	const vocHit = (typeof opts.moonVoc === 'boolean') ? opts.moonVoc : !!(moon && moon.isVOC);
	const strongSig = sigKeys.some((k) => facts.planets[k] && facts.planets[k].dignityScore >= 4);
	const exemptSign = moon && ['taurus', 'cancer', 'sagittarius', 'pisces'].indexOf(moon.sign) >= 0;
	add(3, 'moon_voc', vocHit, {
		mitigable: true, mitigatedBy: ['月在金牛/巨蟹/射手/双鱼', '主要象征星极强（尊贵≥+4）'],
		mitigated: vocHit && (exemptSign || strongSig),
		text_zh: '月亮空亡：诸事难成',
	});
	// 4 燃烧之路（救济：合 Spica/Arcturus 当年实位）
	const vc = viaCombustaRange(opts.viaCombustaVariant);
	const inVC = moon && norm360(moon.lon) >= vc[0] && norm360(moon.lon) <= vc[1];
	const spica = starLonNow('Spica', facts); const arct = starLonNow('Arcturus', facts);
	const vcSaved = inVC && ((spica !== null && angularDist(moon.lon, spica) <= 1.5) || (arct !== null && angularDist(moon.lon, arct) <= 1.5));
	add(4, 'via_combusta', inVC, {
		mitigable: true, mitigatedBy: ['月合角宿一/大角星（按当年岁差实位，≤1.5°）'],
		mitigated: !!vcSaved,
		text_zh: `月在燃烧之路（${vc[0]}°–${vc[1]}°）：结果不可预测`,
	});
	// 5a/5b 土星一宫（逆更甚）/七宫
	const sat = facts.planets.saturn;
	add(5, 'saturn_1st', sat && sat.house === 1, { text_zh: `土星在第 1 宫${sat && sat.retro ? '（且逆行，更甚）' : ''}：事不兴/拖延` });
	add(6, 'saturn_7th', sat && sat.house === 7, { text_zh: '土星在第 7 宫：占星师判断易受蚀（替人判时）' });
	// 6→7 七宫主受克（问题不涉七宫时）
	const seventhIsQuesited = ['marriage', 'lawsuit', 'theft'].indexOf(opts.category) >= 0;
	const l7k = facts.houses[7] && facts.houses[7].ruler;
	const p7 = l7k && facts.planets[l7k];
	add(7, 'l7_afflicted', !seventhIsQuesited && p7 && (p7.retro || p7.combustion === 'combust' || p7.dignityScore <= -4), {
		text_zh: `七宫主受克（${l7k ? cn(l7k) : '—'}）：占星师难给可靠判断`,
	});
	// 8 命主焦伤（救济：cazimi / 互容）
	const l1Combust = lp && lp.combustion === 'combust';
	add(8, 'l1_combust', l1Combust, {
		mitigable: true, mitigatedBy: ['居日心 cazimi 反为大吉', '与太阳互容'],
		mitigated: !!(lp && lp.combustion === 'cazimi'),
		text_zh: '命主星焦伤：问不成立/问者失控',
	});
	// 9 命主或月合龙首/龙尾（发光体 12°，余星取合轨 ~3°）
	const nn = facts.planets.north_node; const sn = facts.planets.south_node;
	const nodeHit = (k) => {
		const p = facts.planets[k];
		if(!p) return false;
		const orb = (k === 'moon' || k === 'sun') ? 12 : 3;
		const nlon = nn ? nn.lon : (sn ? norm360(sn.lon + 180) : null);
		if(nlon === null) return false;
		return angularDist(p.lon, nlon) <= orb || angularDist(p.lon, norm360(nlon + 180)) <= orb;
	};
	add(9, 'node_conj', (lord1 && nodeHit(lord1)) || nodeHit('moon'), { text_zh: '命主或月亮合龙首/龙尾：厄兆（所在宫指其性质）' });
	// 10 象征星冲日
	const oppSun = sigKeys.some((k) => {
		if(k === 'sun') return false;
		const hit = aspectsOf(facts, k).find((x) => x.other === 'sun' && x.angle === 180);
		return !!hit;
	});
	add(10, 'sig_opp_sun', oppSun, { text_zh: '象征星冲日：对此事无表示/被灼' });
	// 11 象征星被围攻
	add(11, 'sig_besieged', sigKeys.some((k) => isBesieged(k, facts)), { text_zh: '象征星被土火围攻：腹背受敌' });
	// 12 象征星/月在星座末度（≥29°；月≥28°沿用既有口径）
	const lateDeg29 = sigKeys.some((k) => facts.planets[k] && facts.planets[k].signlon !== undefined && facts.planets[k].signlon >= 29);
	add(12, 'sig_late_degree', lateDeg29 || (moon && moon.signlon >= 28), { text_zh: '象征星/月亮在星座末度：气质已移，事将他属' });
	// 13 凶星/南交在 10 宫
	const mal10 = ['saturn', 'mars'].some((k) => facts.planets[k] && facts.planets[k].house === 10 && (facts.planets[k].dignityScore <= -4 || facts.planets[k].peregrine));
	const sn10 = sn && sn.house === 10;
	add(13, 'malefic_10th', mal10 || sn10, { text_zh: '受损凶星/南交在 10 宫：占星师难获声誉（判断折损）' });
	// 14 吉凶势均力敌（由引擎在裁决后回填 hit）
	add(14, 'balance_even', false, { severity: 'info', needsVerdict: true, text_zh: '吉凶证据势均力敌：难判走向，宜改日另问' });
	// 15 蚀点（无近期蚀数据 → 降级不可用，绝不误报）
	add(15, 'eclipse_degree', false, { severity: 'unavailable', text_zh: '上升/象征星临近期蚀点：暗损（本盘无近期蚀数据，条目不可用）' });
	// 16 月受阻总评（月焦伤/落陷/被围）
	add(16, 'moon_afflicted', moon && (moon.combustion === 'combust' || moon.sign === 'scorpio' || isBesieged('moon', facts)), { text_zh: '月亮总体受克（焦伤/落陷/被围）：鲜有善终' });
	// 17 土星一宫且受克（al-Kindi 加重条）
	add(17, 'saturn_1st_afflicted', sat && sat.house === 1 && (sat.retro || sat.combustion === 'combust' || sat.dignityScore <= -4), { text_zh: '土星一宫且受克：判断本身受蚀' });
	// 18 琐碎/无诚意问题（用户自评：sincerityConfirmed===false 才命中）
	add(18, 'insincere', opts.sincerityConfirmed === false, {
		mitigable: true, mitigatedBy: ['「我确认问题真诚」勾选'], mitigated: opts.sincerityConfirmed === true,
		text_zh: '琐碎/无诚意问题：未生根，占星师被试探',
	});
	// 19 技术性误差（现代精确时钟消解 → 恒 info 不命中）
	add(19, 'technical_error', false, { severity: 'info', text_zh: '起盘数据误差（现代精确时钟与星历下已消解）' });

	return { mode: opts.considerationsMode || 'warn', items: list };
}

// 痣验证（可选增强）：列出对应身体部位 + 颜色 + 左右 + 前后 + 上中下
export function moleHints(facts){
	const hints = [];
	const add = (label, key) => {
		const p = facts.planets[key];
		const sign = p ? p.sign : null;
		if(!sign) return;
		const sgn = SIGNS[sign];
		const parts = bodyPartsOf(sign);
		hints.push({
			source: label,
			sign,
			parts,
			side: sgn ? moleSide(sgn.gender) : null,
			frontBack: p ? moleFrontBack(p.aboveHorizon) : null,
			updown: p && p.signlon !== undefined ? degreePosition(p.signlon) : null,
		});
	};
	const ascRuler = ascRulerKey(facts);
	const ascSign = facts.meta.ascSign;
	if(ascSign){ const parts = bodyPartsOf(ascSign); hints.push({ source: '上升座', sign: ascSign, parts }); }
	if(ascRuler) add('上升定位星所落座', ascRuler);
	const l6 = facts.houses[6] && facts.houses[6].ruler;
	if(facts.houses[6]) hints.push({ source: '六宫头座', sign: facts.houses[6].sign, parts: bodyPartsOf(facts.houses[6].sign) });
	if(l6) add('六宫主所落座', l6);
	add('月亮所落座', 'moon');
	return hints;
}

export default radicality;
