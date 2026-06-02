// divination/horary/horaryEngine.js
// 卜卦编排器：chart Result + 问题类别 → 完整结构化判断。
// 跑 根本性 → 征象星 → 完成法 → 月亮 → 单星状态 → Query I–VI → 应期方位 → 加权裁决。
import { buildFacts } from '../engine/chartFacts.js';
import { radicality } from '../engine/radicality.js';
import { analyzePerfection, completionThirds } from '../engine/perfection.js';
import { moonReport } from '../engine/moon.js';
import { planetCondition } from '../engine/conditions.js';
import { applyingAspects, separatingAspects, aspectsOf } from '../engine/aspectsEngine.js';
import { assignSignificators } from './significators.js';
import { timingFrom, directionFrom } from './timing.js';
import { describePerson, THIEF_BY_PLANET, DISEASE_BY_ELEMENT, DEATH_MODE } from './describe.js';
import { runTheft } from './theftModule.js';
import { PLANETS } from '../data/planets.js';
import { SIGNS } from '../data/signs.js';

function cn(k){ return (PLANETS[k] || {}).cn || k; }

export const ASPECT_CN = { 0: '合相', 60: '六合', 90: '四分(刑)', 120: '三合', 180: '对分(冲)' };
const ASPECT_NATURE = { 0: 'neutral', 60: 'positive', 120: 'positive', 90: 'negative', 180: 'negative' };
const ALL_KEYS = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
// 古典卜卦只取托勒密五相位（合/六合/四分/三合/对分），不取 45°/30° 等次相位。
const PTOLEMAIC = [0, 60, 90, 120, 180];

// 全盘相位一览（古典七政两两，去重）——把所有可能用到的征象摆给用户自行判断
function buildAllAspects(facts){
	const seen = {}; const out = [];
	ALL_KEYS.forEach((a) => {
		if(!facts.planets[a]) return;
		aspectsOf(facts, a).forEach((x) => {
			const b = x.other;
			if(ALL_KEYS.indexOf(b) < 0) return;
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
function buildMoonStory(facts){
	const inSet = (x) => ALL_KEYS.indexOf(x.other) >= 0 && PTOLEMAIC.indexOf(x.angle) >= 0;
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
	// Query III 消息真假
	const m = facts.planets.moon;
	const moonAngular = m && m.angularity === 'angular';
	q.reportTrue = { verdict: (moonAngular && !m.isVOC) ? 'true' : (m && (m.isVOC || m.combustion === 'combust') ? 'false' : 'uncertain'), text: m ? (m.isVOC ? '月空相 → 消息恐假/为时过早。' : (moonAngular ? '月在角宫且非空相 → 偏真。' : '月非角宫，参考其他。')) : '' };
	// Query IV 何处/方向
	q.where = quesitedKey ? directionFrom(facts, quesitedKey) : null;
	return q;
}

function methodCn(m){ return ({ application: '入相位', translation: '光线传递', collection: '光线汇集', position: '落位', antiscion: '映点' })[m] || m || ''; }
function destrCn(d){ return ({ no_reception_hard: '无接纳的刑/冲', combustion: '燃烧', separation: '出相位(事已过)', prohibition: '阻碍', frustration: '挫败', refranation: '折返' })[d] || d || '受阻'; }

function buildVerdict(ctx){
	const { perf, moon, conds, thirds, querentKey, quesitedKey } = ctx;
	const positive = [];
	const negative = [];
	const push = (arr, text, weight, source) => arr.push({ text, weight: weight || 1, source });

	if(perf){
		if(perf.perfects && !perf.destroyed) push(positive, `完成法命中：${methodCn(perf.method)}${perf.ease === 'easy' ? '（轻松）' : (perf.ease === 'hard' ? '（艰难拖延）' : '')}`, 3, 'perfection');
		if(perf.destroyed) push(negative, `破坏：${destrCn(perf.destruction)}`, 3, 'perfection');
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

export function runHorary(result, category){
	const facts = buildFacts(result);
	if(!facts) return null;
	const sigs = assignSignificators(facts, category || 'general');
	const querentKey = sigs.querentKey;
	let quesitedKey = sigs.quesitedKey;
	if(!quesitedKey){
		const app = applyingAspects(facts, 'moon').filter((a) => ['sun', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'].indexOf(a.other) >= 0);
		quesitedKey = app.length ? app[0].other : null;
	}
	const rad = radicality(facts);
	const moon = moonReport(facts);
	const perf = (querentKey && quesitedKey) ? analyzePerfection(facts, querentKey, quesitedKey, { quesitedHouse: sigs.quesitedHouse }) : null;
	const thirds = completionThirds(facts, [querentKey, 'moon', quesitedKey]);
	const conds = {};
	[querentKey, quesitedKey, sigs.natural, 'moon'].filter(Boolean).forEach((k) => { if(!conds[k]) conds[k] = planetCondition(k, facts); });
	const queries = buildQueries(facts, { quesitedKey, perf, moon, conds });
	const timing = (perf && perf.aspect && perf.perfects) ? timingFrom(facts, perf.aspect.from || querentKey, perf.aspect.orb) : null;
	const verdict = buildVerdict({ perf, moon, conds, thirds, querentKey, quesitedKey });
	const describe = buildDescribe(facts, querentKey, quesitedKey, category || 'general', sigs);
	const theft = (category === 'theft') ? runTheft(facts) : null;
	return {
		facts, category: category || 'general',
		significators: { querentKey, quesitedKey, natural: sigs.natural, moon: 'moon', quesitedHouse: sigs.quesitedHouse, quesitedLabel: sigs.quesitedLabel },
		radicality: rad, moon, perfection: perf, thirds, conditions: conds, queries, timing, verdict, describe, theft,
		allAspects: buildAllAspects(facts), moonStory: buildMoonStory(facts),
		hourRuler: facts.meta.hourRuler,
	};
}

export default runHorary;
