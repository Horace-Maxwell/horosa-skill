// divination/election/electionEngine.js
// 择日编排器：chart Result + topicId → ElectionReport（择日清单 §1.2）。
import { buildFacts } from '../engine/chartFacts.js';
import { evalHardFlags } from './hardFlags.js';
import { scoreReport, GRADE_CN } from './scoring.js';
import { runModules } from './modules.js';
import { evaluateTopicPack } from './rulePacks.js';
import { TOPIC_MASTER } from '../data/topicMaster.js';
import { castMoment } from '../data/castMoments.js';
import { aspectsOf } from '../engine/aspectsEngine.js';
import { PLANETS } from '../data/planets.js';
import { natalIntegration } from './natalIntegration.js';
import { mundaneIntegration } from './mundaneIntegration.js';
import { schoolOf } from './westernSchools.js';
import { norm360 } from '../engine/utils.js';

// WP-8 危象日(crisis days):自病始时刻月位行进 45°/90°/180°/270° 前后为危象期(~7 日律)。
// 传统文献未给统一判定容许度 → 纯陈述不设 orb 不扣分:报已行度数与最近危象点距离,由用户裁量。
// 仅手术/用药用事产出(危象=病程七日律,他事无义);切走用事后 extra 里的病始输入保留、此处门控不显示。
function buildCrisis(facts, opts, topic){
	if(!topic || topic.topic_id !== 'surgery') return null;
	const base = opts && opts.crisisBase;
	if(!base || base.moonLon == null || !Number.isFinite(Number(base.moonLon))) return null;
	const moon = facts.planets.moon;
	if(!moon || moon.lon == null) return null;
	const elapsed = norm360(moon.lon - Number(base.moonLon));
	const marks = [45, 90, 180, 270];
	let nearest = null;
	marks.forEach((m) => {
		const d = Math.abs(elapsed - m);
		if(nearest === null || d < nearest.dist) nearest = { mark: m, dist: d };
	});
	return {
		baseDate: base.date || '',
		elapsedDeg: Math.round(elapsed * 10) / 10,
		nearestMark: nearest.mark,
		distToMark: Math.round(nearest.dist * 10) / 10,
		text: `自病始（${base.date || '—'}）月已行 ${Math.round(elapsed * 10) / 10}°；最近危象点 ${nearest.mark}°（45/90/180/270° 为危象期，~7 日律），相距 ${Math.round(nearest.dist * 10) / 10}°。`,
	};
}

// 应期参考：月亮临近相位（按误差升序，越紧越近发动）。
function buildTiming(facts){
	const ma = aspectsOf(facts, 'moon') || [];
	return ma.slice().sort((a, b) => (a.orb == null ? 99 : a.orb) - (b.orb == null ? 99 : b.orb)).slice(0, 3)
		.map((a) => ({ otherCn: (PLANETS[a.other] || {}).cn || a.other, angle: a.angle, orb: a.orb }));
}

const NO_PERFECT = '没有完美的择日盘：本结果是在你给定时间窗内、以消去法挑出的较优解，仅供参考。择日是助力/润滑油，能强化本命吉兆、缓和（不能完全化解）凶兆——事在人为 + 本命盘 > 择日盘。';

function buildHeadline(topic, scored, flags){
	const crit = flags.filter((f) => f.severity === 'critical');
	const high = flags.filter((f) => f.severity === 'high');
	let head = `${topic.cn}择日：${GRADE_CN[scored.grade]}（${scored.score} 分）。`;
	if(crit.length) head += `命中红线：${crit.map((f) => f.message.split('：')[0]).join('、')}。`;
	else if(high.length) head += `主要代价：${high.slice(0, 2).map((f) => f.message.split('：')[0]).join('、')}。`;
	return head;
}

function buildRecommendations(facts, topic, sections, flags, scored){
	const recs = [];
	if(flags.some((f) => f.id === 'moon_square')) recs.push('月亮逢刑是择日大忌：优先微调到月亮无 90° 的时刻。');
	if(flags.some((f) => f.id === 'moon_void_of_course')) recs.push('月亮空亡：换一个月亮离座前仍有主相位的时刻。');
	if(flags.some((f) => f.id === 'saturn_on_angle')) recs.push('土星近角点：微调命度（4 分钟≈1°）使土星离开角宫，或确保土星有吉相。');
	const ad = facts.meta.ascDegree;
	if(ad !== null && ad > 28) recs.push('命度已在 28° 后：稍提前/延后使命度落固定宫前段（1–5°）以增稳定性。');
	if(!recs.length) recs.push('本盘无明显红线，可在窗口内据各分项进一步择优；最终以消去法对多个候选并排比较。');
	return recs;
}

// opts.westSchool:西方子流派档(westernSchools.js 五档;缺省 modern_main=现状行为)。
export function runElection(result, topicId, natalFacts, mundaneSet, opts){
	const facts = buildFacts(result);
	if(!facts) return null;
	const school = schoolOf(opts && opts.westSchool);
	const topic = TOPIC_MASTER[topicId] || TOPIC_MASTER.marriage;
	const sections = runModules(facts, topic, school);
	const flags = evalHardFlags(facts, topic, school);
	const topicPack = evaluateTopicPack(facts, topic, opts);
	const scored = scoreReport(sections, flags, school);
	const natal = natalFacts ? natalIntegration(natalFacts, facts) : null;
	const mundane = mundaneSet ? mundaneIntegration(facts, mundaneSet) : null;
	return {
		facts, topic,
		westSchool: { id: school.id, cn: school.cn },
		overall: {
			score: scored.score, grade: scored.grade, gradeCn: GRADE_CN[scored.grade],
			headline: buildHeadline(topic, scored, flags),
			no_perfect_chart_note: NO_PERFECT,
		},
		hard_flags: flags,
		sections,
		topicPack,
		natal,
		mundane,
		crisis: buildCrisis(facts, opts, topic),
		timing: buildTiming(facts),
		recommendations: buildRecommendations(facts, topic, sections, flags, scored),
		castMoment: castMoment(topicId),
		penalty: scored.penalty, base: scored.base,
	};
}

export default runElection;
