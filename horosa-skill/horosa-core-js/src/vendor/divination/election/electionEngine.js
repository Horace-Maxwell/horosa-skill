// divination/election/electionEngine.js
// 择日编排器：chart Result + topicId → ElectionReport（择日清单 §1.2）。
import { buildFacts } from '../engine/chartFacts.js';
import { evalHardFlags } from './hardFlags.js';
import { scoreReport, GRADE_CN } from './scoring.js';
import { runModules } from './modules.js';
import { evaluateTopicPack } from './rulePacks.js';
import { TOPIC_MASTER } from '../data/topicMaster.js';
import { castMoment } from '../data/castMoments.js';

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

export function runElection(result, topicId){
	const facts = buildFacts(result);
	if(!facts) return null;
	const topic = TOPIC_MASTER[topicId] || TOPIC_MASTER.marriage;
	const sections = runModules(facts, topic);
	const flags = evalHardFlags(facts, topic);
	const topicPack = evaluateTopicPack(facts, topic);
	const scored = scoreReport(sections, flags);
	return {
		facts, topic,
		overall: {
			score: scored.score, grade: scored.grade, gradeCn: GRADE_CN[scored.grade],
			headline: buildHeadline(topic, scored, flags),
			no_perfect_chart_note: NO_PERFECT,
		},
		hard_flags: flags,
		sections,
		topicPack,
		recommendations: buildRecommendations(facts, topic, sections, flags, scored),
		castMoment: castMoment(topicId),
		penalty: scored.penalty, base: scored.base,
	};
}

export default runElection;
