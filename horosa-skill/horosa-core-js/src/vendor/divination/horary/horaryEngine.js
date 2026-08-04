// divination/horary/horaryEngine.js
// 卜卦编排器：chart Result + 问题类别 → 完整结构化判断。
// 跑 根本性 → 征象星 → 完成法 → 月亮 → 单星状态 → Query I–VI → 应期方位 → 加权裁决。
import { buildFacts } from '../engine/chartFacts.js';
import { radicality } from '../engine/radicality.js';
import { analyzePerfection, completionThirds } from '../engine/perfection.js';
import { moonReport } from '../engine/moon.js';
import { planetCondition } from '../engine/conditions.js';
import { applyingAspects, separatingAspects, aspectsOf, aspectBetween } from '../engine/aspectsEngine.js';
import { almutenAt } from '../engine/almuten.js';
import { assignSignificators, moonPromotionCheck } from './significators.js';
import { timingFrom, directionFrom } from './timing.js';
import { describePerson, THIEF_BY_PLANET, DISEASE_BY_ELEMENT, DEATH_MODE } from './describe.js';
import { runTheft } from './theftModule.js';
import { buildTopicDeepening } from './topicModule.js';
import { PLANETS } from '../data/planets.js';
import { SIGNS, signOfLon } from '../data/signs.js';
import { FIXED_STARS, starLonAt, starOrbFor } from '../data/fixedStars.js';
import { lotDispositor, LOTS_SETS, computeLotsSet } from '../data/lots.js';
import { angularDist, norm360 } from '../engine/utils.js';

function cn(k){ return (PLANETS[k] || {}).cn || k; }
function signCn(s){ return (SIGNS[s] || {}).cn || s; }

// 阿拉伯点（福点/精神点）：按流派福点昼夜反转口径计算 + 落座 + 定位星（失物/财物关键征象）。
//  pofReversal=true(严谨/希腊化/中世纪)：夜盘反转公式；false(经典/现代)：恒用日盘式 ASC+Moon−Sun。
function buildLots(facts, opts){
	opts = opts || {};
	const asc = facts.meta.ascLon;
	const sun = facts.planets.sun ? facts.planets.sun.lon : null;
	const moon = facts.planets.moon ? facts.planets.moon.lon : null;
	if(asc == null || sun == null || moon == null){ return null; }
	const isDay = !!facts.meta.isDiurnal;
	const reverse = !!opts.pofReversal;
	const useNight = reverse && !isDay;   // 仅「反转档 + 夜盘」才翻公式
	const fortune = norm360(useNight ? (asc + sun - moon) : (asc + moon - sun));
	const spirit = norm360(useNight ? (asc + moon - sun) : (asc + sun - moon));
	const pack = (lon) => {
		const sign = signOfLon(lon);
		const disp = lotDispositor(lon);
		return { lon, sign, signCn: signCn(sign), signlon: ((lon % 30) + 30) % 30, disp, dispCn: disp ? cn(disp) : null };
	};
	const out = {
		reversalApplied: useNight,
		convention: reverse ? (isDay ? '反转档·日盘（同日式）' : '反转档·夜盘（翻公式）') : '不反转档（恒日式）',
		fortune: pack(fortune),
		spirit: pack(spirit),
	};
	// lots_set='core15'：高可靠核心集全量（福/精神按上方口径先算好注入,其余按各点 reverseBySect）。
	// 默认 'minimal' 不扩（零回归）。
	if(opts.lotsSet && opts.lotsSet !== 'minimal' && LOTS_SETS[opts.lotsSet]){
		const workLons = { ...facts.lons, fortune, spirit };
		out.extended = computeLotsSet(workLons, isDay, LOTS_SETS[opts.lotsSet])
			.map((it) => ({ ...it, ...pack(it.lon), id: it.id, cn: it.cn, use: it.use, house: it.house }));
	}
	return out;
}

// 取本盘公历年（恒星岁差修正）：读 /chart 回传 params.birth/date；缺则用中性年。
function chartYear(facts){
	try{
		const p = facts && facts.result && facts.result.params;
		const ds = p && (p.birth || p.date);
		if(ds){ const m = String(ds).match(/(-?\d{3,4})/); if(m){ return Number(m[1]); } }
	}catch(e){ /* noop */ }
	return 2000;
}

// D2 恒星会合：征象星/命度/天顶 会合精选恒星（容许度按流派取，默认 1°）。
function buildFixedStars(facts, sigs, opts){
	// 轨档：'school'(默认,平轨=既有行为字节不变) / 'byMagnitude'(Robson 按星等;王者封顶 5°)。
	const year = chartYear(facts);
	const out = [];
	const points = {};
	if(facts.meta.ascLon != null){ points['命度'] = facts.meta.ascLon; }
	if(facts.meta.mcLon != null){ points['天顶'] = facts.meta.mcLon; }
	[['命主', sigs.querentKey], ['事项', sigs.quesitedKey], ['月亮', 'moon']].forEach((pair) => {
		const label = pair[0]; const k = pair[1];
		if(k && facts.planets[k] && facts.planets[k].lon != null){ points[`${label}·${cn(k)}`] = facts.planets[k].lon; }
	});
	Object.keys(points).forEach((label) => {
		const lon = points[label];
		FIXED_STARS.forEach((st) => {
			const stLon = starLonAt(st.lon_1995, year);
			if(angularDist(lon, stLon) <= starOrbFor(st, opts)){
				// starLon/pointLon 为纯增字段(中栏叠层轮缘定位用);快照/右栏按显式字段格式化,零影响。
				out.push({ point: label, star: st.name_cn, meaning: st.meaning, nature: (st.election && st.election.avoid) ? 'caution' : 'boost', royal: !!st.isRoyal, starLon: stLon, pointLon: lon });
			}
		});
	});
	return out;
}

// D5 行星时佐证：时主星与命主/事项星一致 → 时辰与盘相合（根本性佐证）。
// opts.hourAgreementVariant:'either'(两口径任一,缺省)|'lilly'(行星统辖版:只认时主=命主星)|
// 'bonatti'(落座元素版:时主与上升座同元素也算合)。不传=既有行为字节不变。
function buildHourAgreement(facts, sigs, opts){
	opts = opts || {};
	const v = opts.hourAgreementVariant || 'either';
	const hr = facts.meta.hourRuler;
	if(!hr){ return null; }
	if(hr === sigs.querentKey){ return { agree: true, text: `时主星 ${cn(hr)} ＝ 命主：时辰与盘相合（根本性佐证）。` }; }
	if(v !== 'lilly' && hr === sigs.quesitedKey){ return { agree: true, text: `时主星 ${cn(hr)} ＝ 事项守护星：时辰与所问相合（佐证）。` }; }
	if(v === 'bonatti'){
		const ELEM = { aries: 'fire', leo: 'fire', sagittarius: 'fire', taurus: 'earth', virgo: 'earth', capricorn: 'earth', gemini: 'air', libra: 'air', aquarius: 'air', cancer: 'water', scorpio: 'water', pisces: 'water' };
		const ascSign = facts.houses && facts.houses[1] ? facts.houses[1].sign : null;
		const hrSign = facts.planets[hr] ? facts.planets[hr].sign : null;
		if(ascSign && hrSign && ELEM[ascSign] && ELEM[ascSign] === ELEM[hrSign]){
			return { agree: true, text: `时主星 ${cn(hr)} 落座与上升座同元素（落座元素版口径）：时辰与盘相合。` };
		}
	}
	if(v === 'lilly' && hr === sigs.quesitedKey){ return { agree: false, text: `时主星 ${cn(hr)} ＝ 事项守护星——行星统辖版口径只认命主一致，作一般参考。` }; }
	return { agree: false, text: `时主星 ${cn(hr)} 与命主/事项星不一致，作一般参考。` };
}

export const ASPECT_CN = { 0: '合相', 60: '六合', 90: '四分(刑)', 120: '三合', 180: '对分(冲)' };
const ASPECT_NATURE = { 0: 'neutral', 60: 'positive', 120: 'positive', 90: 'negative', 180: 'negative' };
const ALL_KEYS = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
const OUTER_KEYS = ['uranus', 'neptune', 'pluto'];
// [WP-F] includeOuter 真接线:全相位表/月亮叙事的星集门(默认 false=七政,现状零回归;
// 现代档 includeOuter:true → 三王星入表)。注:perfection 的干扰/传递/汇集候选历史即全星集,不动。
function judgeKeysFor(includeOuter){
	return includeOuter ? ALL_KEYS.concat(OUTER_KEYS) : ALL_KEYS;
}
// 古典卜卦只取托勒密五相位（合/六合/四分/三合/对分），不取 45°/30° 等次相位。
const PTOLEMAIC = [0, 60, 90, 120, 180];

// 全盘相位一览（判读星集两两，去重）——把所有可能用到的征象摆给用户自行判断
function buildAllAspects(facts, includeOuter){
	const KS = judgeKeysFor(includeOuter);
	const seen = {}; const out = [];
	KS.forEach((a) => {
		if(!facts.planets[a]) return;
		aspectsOf(facts, a).forEach((x) => {
			const b = x.other;
			if(KS.indexOf(b) < 0) return;
			if(PTOLEMAIC.indexOf(x.angle) < 0) return;
			const k = [a, b].sort().join('-') + ':' + x.angle;
			if(seen[k]) return; seen[k] = 1;
			out.push({ a, b, angle: x.angle, applying: !!x.applying, separating: !!x.separating, exact: !!x.exact, orb: x.orb, nature: ASPECT_NATURE[x.angle] || 'neutral' });
		});
	});
	out.sort((m, n) => ((m.exact ? 0 : 1) - (n.exact ? 0 : 1)) || (m.orb - n.orb));
	return out;
}

// 月亮的故事：刚离开（过去）→ 接下来要会（未来），卜卦核心线索
function buildMoonStory(facts, includeOuter){
	const KS = judgeKeysFor(includeOuter);
	const inSet = (x) => KS.indexOf(x.other) >= 0 && PTOLEMAIC.indexOf(x.angle) >= 0;
	return {
		separating: separatingAspects(facts, 'moon').filter(inSet).sort((a, b) => a.orb - b.orb),
		applying: applyingAspects(facts, 'moon').filter(inSet).sort((a, b) => a.orb - b.orb),
	};
}

function buildDescribe(facts, querentKey, quesitedKey, category, sigs){
	const out = [];
	if(querentKey && facts.planets[querentKey]){
		out.push({ role: '问卜者（命主）', ...describePerson(querentKey, facts.planets[querentKey].sign) });
	}
	if(quesitedKey && quesitedKey !== querentKey && facts.planets[quesitedKey]){
		out.push({ role: sigs.quesitedLabel || '对象', ...describePerson(quesitedKey, facts.planets[quesitedKey].sign) });
	}
	if(category === 'theft' && quesitedKey){
		out.push({ role: '小偷（7宫主/征象星）', title: `小偷（${cn(quesitedKey)}）`, body: THIEF_BY_PLANET[quesitedKey] || '（该行星无对应外貌条目）', temper: null });
	}
	if(category === 'health' && facts.planets.moon){
		const el = SIGNS[facts.planets.moon.sign] ? SIGNS[facts.planets.moon.sign].element : null;
		if(el) out.push({ role: '病因（月亮所落元素）', title: '疾病性质', body: DISEASE_BY_ELEMENT[el], temper: null });
	}
	if(category === 'death' && quesitedKey){
		out.push({ role: '死亡方式（8宫主）', title: `死亡方式（${cn(quesitedKey)}）`, body: DEATH_MODE[quesitedKey] || '—', temper: null });
	}
	return out;
}

function buildQueries(facts, ctx){
	const { quesitedKey, perf, moon, conds } = ctx;
	const q = {};
	// Query I 能否成事
	if(perf && perf.perfects && !perf.destroyed) q.canHappen = { verdict: 'yes', text: `能成（${methodCn(perf.method)}${perf.translator ? '，中间人=' + cn(perf.translator) : ''}${perf.collector ? '，汇集于=' + cn(perf.collector) : ''}）。` };
	else if(perf && perf.destroyed) q.canHappen = { verdict: 'no', text: `难成（${destrCn(perf.destruction)}）。` };
	else q.canHappen = { verdict: 'even', text: '未见明确完成法，多半不成或需另择时。' };
	// Query II 事情好坏
	const qc = quesitedKey && conds[quesitedKey];
	q.goodEvil = { verdict: qc && qc.score > 0 ? 'good' : (qc && qc.score < 0 ? 'bad' : 'neutral'), text: qc ? `事项守护星 ${cn(quesitedKey)} 状态分 ${qc.score}` : '事项守护星未定。' };
	// Query III 消息真假（月空按流派解算值，见 moonReport）
	const m = facts.planets.moon;
	const rVoc = ctx.moon ? !!ctx.moon.voc : (m && m.isVOC);
	const moonAngular = m && m.angularity === 'angular';
	q.reportTrue = { verdict: (moonAngular && !rVoc) ? 'true' : (m && (rVoc || m.combustion === 'combust') ? 'false' : 'uncertain'), text: m ? (rVoc ? '月空相 → 消息恐假/为时过早。' : (moonAngular ? '月在角宫且非空相 → 偏真。' : '月非角宫，参考其他。')) : '' };
	// Query IV 何处/方向
	q.where = quesitedKey ? directionFrom(facts, quesitedKey) : null;
	// Query V 何时（应期指针;与「时空」Tab 同源）
	q.when = ctx.timing ? { verdict: 'info', text: ctx.timing.text } : { verdict: 'uncertain', text: '无准确入相位可折算应期。' };
	// Query VI 结局如何（事情之终局:4宫主状态 + 月亮末相位口径）
	const l4 = facts.houses[4] && facts.houses[4].ruler;
	const c4 = l4 && conds && conds[l4] ? conds[l4] : null;
	q.outcome = {
		verdict: c4 ? (c4.score > 0 ? 'good' : (c4.score < 0 ? 'bad' : 'neutral')) : 'uncertain',
		text: l4 ? `事之结局看 4宫主 ${cn(l4)}${c4 ? `（状态分 ${c4.score}）` : ''}；月亮末次相位并参。` : '4宫主未定，结局待参月亮末相位。',
	};
	return q;
}

function methodCn(m){ return ({ application: '入相位', translation: '光线传递', collection: '光线汇集', position: '落位', antiscion: '映点' })[m] || m || ''; }
function destrCn(d){ return ({ no_reception_hard: '无接纳的刑/冲', combustion: '燃烧', separation: '出相位(事已过)', prohibition: '阻碍', frustration: '挫败', refranation: '撤回(临成自退)', abscission: '光线切断' })[d] || d || '受阻'; }

function buildVerdict(ctx){
	const { perf, moon, conds, thirds, querentKey, quesitedKey } = ctx;
	const positive = [];
	const negative = [];
	const push = (arr, text, weight, source) => arr.push({ text, weight: weight || 1, source });

	if(perf){
		if(perf.perfects && !perf.destroyed) push(positive, `完成法命中：${methodCn(perf.method)}${perf.ease === 'easy' ? '（轻松）' : (perf.ease === 'hard' ? '（艰难拖延）' : '')}`, 3, 'perfection');
		if(perf.destroyed) push(negative, `破坏：${destrCn(perf.destruction)}${perf.interferer ? '（' + cn(perf.interferer) + '）' : ''}`, 3, 'perfection');
		if(perf.refranationRisk) push(negative, '完成方逆行 → 恐折返（临成又退、事有反复）', 2, 'perfection');
	}
	// 完成度三分
	if(thirds){
		const fracText = { all: '三大征象皆安全 → 达成一切', '2/3': '两征象安全 → 约完成 2/3', '1/3': '一征象安全 → 约完成 1/3', none: '三征象皆不安全 → 难成/败坏' }[thirds.fraction];
		if(thirds.fraction === 'all' || thirds.fraction === '2/3') push(positive, `完成度：${fracText}`, 2, 'thirds');
		else push(negative, `完成度：${fracText}`, 2, 'thirds');
	}
	// 月亮
	(moon.findings || []).forEach((f) => {
		if(f.polarity === 'positive') push(positive, '月亮：' + f.text_zh, f.weight, 'moon');
		else if(f.polarity === 'negative') push(negative, '月亮：' + f.text_zh, f.weight, 'moon');
	});
	// 关键征象星状态
	[querentKey, quesitedKey].filter(Boolean).forEach((k) => {
		const c = conds[k]; if(!c) return;
		(c.findings || []).forEach((f) => {
			if(f.polarity === 'positive') push(positive, f.text_zh, f.weight, 'condition');
			else if(f.polarity === 'negative') push(negative, f.text_zh, f.weight, 'condition');
		});
	});

	const pos = positive.reduce((s, x) => s + x.weight, 0);
	const neg = negative.reduce((s, x) => s + x.weight, 0);
	let leaning = 'even';
	if(perf && perf.perfects && !perf.destroyed && pos >= neg) leaning = 'yes';
	else if(perf && perf.destroyed) leaning = 'no';
	else if(pos - neg >= 3) leaning = 'yes';
	else if(neg - pos >= 3) leaning = 'no';
	const summary = leaning === 'yes' ? '倾向：成（仍请结合实际，不下命定结论）'
		: leaning === 'no' ? '倾向：不成 / 受阻（建议另择时再问）'
			: '倾向：势均力敌 → 建议另择时再问';
	return { positive, negative, posScore: pos, negScore: neg, leaning, summary };
}

export function runHorary(result, category, opts){
	opts = opts || {};
	const facts = buildFacts(result, opts);
	if(!facts) return null;
	const sigs = assignSignificators(facts, category || 'general', opts);
	const querentKey = sigs.querentKey;
	let quesitedKey = sigs.quesitedKey;
	if(!quesitedKey){
		const app = applyingAspects(facts, 'moon').filter((a) => ['sun', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'].indexOf(a.other) >= 0);
		quesitedKey = app.length ? app[0].other : null;
	}
	const moon = moonReport(facts, opts);
	const rad = radicality(facts, { ...opts, category: category || 'general', moonVoc: moon.voc, sigs: { querentKey, quesitedKey } });
	const perf = (querentKey && quesitedKey) ? analyzePerfection(facts, querentKey, quesitedKey, { quesitedHouse: sigs.quesitedHouse, ...opts }) : null;
	const thirds = completionThirds(facts, [querentKey, 'moon', quesitedKey]);
	const conds = {};
	[querentKey, quesitedKey, sigs.natural, 'moon'].filter(Boolean).forEach((k) => { if(!conds[k]) conds[k] = planetCondition(k, facts, opts); });
	const timing = (perf && perf.aspect && perf.perfects)
		? timingFrom(facts, perf.aspect.from || querentKey, perf.aspect.orb, {
			...opts,
			appliedKey: perf.aspect.to || quesitedKey,
			otherKey: (perf.aspect.from === querentKey ? quesitedKey : querentKey),
		})
		: null;
	const queries = buildQueries(facts, { quesitedKey, perf, moon, conds, timing });
	const verdict = buildVerdict({ perf, moon, conds, thirds, querentKey, quesitedKey });
	// 考量14「吉凶势均力敌」：裁决后回填（|pos−neg|<2 且未有明确完成/破坏 → 命中）。
	if(rad && rad.considerations && rad.considerations.items){
		const even = rad.considerations.items.find((it) => it.key === 'balance_even');
		if(even){
			even.hit = Math.abs(verdict.posScore - verdict.negScore) < 2 && !(perf && (perf.perfects || perf.destroyed));
		}
	}
	// 月亮升格检查（05§4.1 四条件;注记性,不改变默认象征星指派）。
	const l1qAspect = (querentKey && quesitedKey) ? aspectBetween(facts, querentKey, quesitedKey) : null;
	const moonPromotion = moonPromotionCheck(facts, querentKey, quesitedKey, l1qAspect !== null);
	// 逐度 almuten（上升/事项宫头/日月福点由 UI 按需展开;此处给上升与事项宫头两处）。
	const almutenOpts = {
		isDiurnal: facts.meta.isDiurnal,
		termsVariant: opts.termsVariant !== undefined ? opts.termsVariant : 'ptolemaic',
		tripSystem: opts.tripSystem, geminiEmended: !!opts.geminiEmended, weights: opts.almutenWeights,
	};
	const almuten = {
		asc: facts.meta.ascLon != null ? almutenAt(facts.meta.ascLon, almutenOpts) : null,
		quesitedCusp: (sigs.quesitedHouse && facts.houses[sigs.quesitedHouse] && facts.houses[sigs.quesitedHouse].lon != null)
			? almutenAt(facts.houses[sigs.quesitedHouse].lon, almutenOpts) : null,
	};
	const describe = buildDescribe(facts, querentKey, quesitedKey, category || 'general', sigs);
	const theft = (category === 'theft') ? runTheft(facts) : null;
	return {
		facts, category: category || 'general', school: opts.school || 'classical',
		// sharedRuler 必须透传:significators.js 在命主=事主同星时写出五法(A-E)裁决对象,
		// 此处重组曾把它丢弃 → HoraryJudgment 的同主一星卡片恒不显示(2026-08 死开关审计抓出)。
		significators: { querentKey, quesitedKey, natural: sigs.natural, moon: 'moon', quesitedHouse: sigs.quesitedHouse, quesitedLabel: sigs.quesitedLabel, sharedRuler: sigs.sharedRuler || null },
		radicality: rad, moon, perfection: perf, thirds, conditions: conds, queries, timing, verdict, describe, theft,
		almuten, moonPromotion,
		allAspects: buildAllAspects(facts, !!opts.includeOuter), moonStory: buildMoonStory(facts, !!opts.includeOuter),
		hourRuler: facts.meta.hourRuler,
		fixedStars: buildFixedStars(facts, { querentKey, quesitedKey }, opts),
		hourAgreement: buildHourAgreement(facts, { querentKey, quesitedKey }, opts),
		lots: buildLots(facts, opts),
		tripSystem: opts.tripSystem || 'ptolemaic',
		topic: buildTopicDeepening(facts, category || 'general'),
	};
}

export default runHorary;
