// divination/election/scoring.js
// 透明加权评分（择日清单 §5）。组件分各 0–100，按优先级权重合成，红线罚分后降级。
export const WEIGHTS = {
	moon: 0.22, asc_ruler: 0.18, ascendant: 0.12, topic_significators: 0.16,
	angles: 0.14, topic_house: 0.06, sun: 0.05, aspect_patterns: 0.04,
	reception_fixedstar_midpoint: 0.03, fixed_stars: 0.03,
};

const PENALTY = { critical: 40, high: 15, medium: 8, low: 3 };

// school:西方子流派档(可缺省)。三个真消费面:
//   extraWeights —— 「新增分析模块→权重」表(默认现代主流 extraWeights={} → 新模块仅展示不进总分,
//                   总分构成与既往字节不变;宗派强调档给真实权重,wsum 归一自动摊薄);
//   sectWeight  —— 宗派模块权重的权威字段(定义时压过 extraWeights.sect,两处同值=行为不变);
//   moduleSet   —— 核心模块评分白名单(缺省=全部核心;白名单外的核心模块仅展示不进总分)。
export function scoreReport(sections, flags, school){
	const extraW = (school && school.extraWeights) || {};
	const coreAllowed = (school && Array.isArray(school.moduleSet)) ? school.moduleSet : null;
	let base = 0; let wsum = 0;
	sections.forEach((s) => {
		if(coreAllowed && WEIGHTS[s.key] !== undefined && coreAllowed.indexOf(s.key) < 0){ return; }
		let w = WEIGHTS[s.key] !== undefined ? WEIGHTS[s.key] : extraW[s.key];
		if(s.key === 'sect' && school && typeof school.sectWeight === 'number'){ w = school.sectWeight; }
		if(w !== undefined && s.score !== undefined && s.score !== null){ base += s.score * w; wsum += w; }
	});
	base = wsum > 0 ? base / wsum : 50;
	const penalty = (flags || []).reduce((p, f) => p + (PENALTY[f.severity] || 0), 0);
	const score = Math.max(0, Math.min(100, Math.round(base - penalty)));
	const hasCritical = (flags || []).some((f) => f.severity === 'critical');
	let grade;
	if(hasCritical || score < 40) grade = 'disqualified';
	else if(score >= 85) grade = 'excellent';
	else if(score >= 70) grade = 'good';
	else if(score >= 55) grade = 'fair';
	else grade = 'poor';
	return { score, grade, penalty, base: Math.round(base) };
}

export const GRADE_CN = { excellent: '极佳', good: '不错', fair: '中等', poor: '欠佳', disqualified: '不宜（含红线）' };

export default scoreReport;
