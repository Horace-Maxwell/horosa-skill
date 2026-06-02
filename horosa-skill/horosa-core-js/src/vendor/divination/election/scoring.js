// divination/election/scoring.js
// 透明加权评分（择日清单 §5）。组件分各 0–100，按优先级权重合成，红线罚分后降级。
export const WEIGHTS = {
	moon: 0.22, asc_ruler: 0.18, ascendant: 0.12, topic_significators: 0.16,
	angles: 0.14, topic_house: 0.06, sun: 0.05, aspect_patterns: 0.04,
	reception_fixedstar_midpoint: 0.03,
};

const PENALTY = { critical: 40, high: 15, medium: 8, low: 3 };

export function scoreReport(sections, flags){
	let base = 0; let wsum = 0;
	sections.forEach((s) => {
		const w = WEIGHTS[s.key];
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
