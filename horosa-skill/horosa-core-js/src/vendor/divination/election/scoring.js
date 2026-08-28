// divination/election/scoring.js
// 透明加权评分（择日清单 §5）。组件分各 0–100，按优先级权重合成，红线罚分后降级。
// [2026-08 重标定] 旧标定四层叠压致随机时刻期望分 ≈35(恒不及格):模块天花板 60 附近 ×
// 罚分线性无封顶(普通时刻 −20~40) × 及格线 55 × 空亡(每 2-3 天一轮)无差别一票否决。
// 新标定三件套(判据零动,只改分数合成):同源去重+软封顶 / critical 按用事分流 / 档位线下调。
// 目标分布(分布回归闸 __tests__/scoringDistribution.test.js 实测锁带):及格率 35~60%,
// 「不错」以上 12~30%,「极佳」≤10%,「不宜」2~25%(带宽含 7 天窗统计波动)。
export const WEIGHTS = {
	moon: 0.22, asc_ruler: 0.18, ascendant: 0.12, topic_significators: 0.16,
	angles: 0.14, topic_house: 0.06, sun: 0.05, aspect_patterns: 0.04,
	reception_fixedstar_midpoint: 0.03, fixed_stars: 0.03,
};

// [重标定] 罚分表整体下调(旧 40/15/8/3——critical 一条即砸穿 base 的 2/3)。
const PENALTY = { critical: 22, high: 10, medium: 5, low: 2 };
const SEV_RANK = { critical: 3, high: 2, medium: 1, low: 0 };

// [重标定] 同源去重:同一 factor(同一颗星/同一因素)的多条红线,只按最重一条全额计罚,
// 其余按 30% 计入——月亮一颗星旧制可叠扣 30+ 分(逢刑+晚度+速慢+近朔望+落陷),
// 不合择日学理(同一因素不重复致命);病多仍更差(30% 残额保单调),但不再互相踩踏。
const DUP_FACTOR_RATE = 0.3;

// [重标定] 软封顶:总罚分过饱和曲线,上限 35——罚分恒单调(扫描排序语义不变),
// 但「病灶清单长」不再把一切砸到地板(旧制线性累加动辄 −40 以上)。
const PENALTY_CAP = 35;
function saturate(p){ return p <= 0 ? 0 : PENALTY_CAP * (1 - Math.exp(-p / PENALTY_CAP)); }

function dedupedPenalty(flags){
	const byFactor = {};
	(flags || []).forEach((f) => {
		if(f.severity === 'info' || !PENALTY[f.severity]) return;
		const k = f.factor || f.id || '_';
		(byFactor[k] = byFactor[k] || []).push(f);
	});
	let total = 0;
	Object.keys(byFactor).forEach((k) => {
		const list = byFactor[k].slice().sort((a, b) => (SEV_RANK[b.severity] || 0) - (SEV_RANK[a.severity] || 0));
		list.forEach((f, i) => { total += PENALTY[f.severity] * (i === 0 ? 1 : DUP_FACTOR_RATE); });
	});
	return total;
}

// school:西方子流派档(可缺省)。三个真消费面:
//   extraWeights —— 「新增分析模块→权重」表(默认现代主流 extraWeights={} → 新模块仅展示不进总分,
//                   总分构成与既往字节不变;宗派强调档给真实权重,wsum 归一自动摊薄);
//   sectWeight  —— 宗派模块权重的权威字段(定义时压过 extraWeights.sect,两处同值=行为不变);
//   moduleSet   —— 核心模块评分白名单(缺省=全部核心;白名单外的核心模块仅展示不进总分)。
// topic(可缺省):当前用事——critical 红线仅在 topic.must_avoid 命中其 id 时一票否决
// (重大缔结型用事的硬禁忌,如婚盘空亡);其余 critical 降为重罚+headline 警示。
// 不传 topic=无一票否决(仅按分数分档),兼容旧调用。
export function scoreReport(sections, flags, school, topic){
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
	// [重标定·校准③] 不对称信号拉伸:模块加权分天然聚在 50~70 窄带(①轮 median=47 及格 32%
	// 「不错+」恒 0%;②轮对称 ×1.4 → 及格 62% 溢出且不宜 1.2% 触底)。上行 ×1.6 打开
	// 「不错/极佳」天花板(65→74,70→82),下行 ×1.15 保住「不宜」区分度(42→40.8);单调保序。
	base = base >= 50 ? 50 + (base - 50) * 1.6 : 50 + (base - 50) * 1.15;
	base = Math.max(0, Math.min(100, base));   // 拉伸后夹取:base 是回传/显示字段,不越 0-100
	const penaltyRaw = dedupedPenalty(flags);
	const penalty = Math.round(saturate(penaltyRaw));
	const score = Math.max(0, Math.min(100, Math.round(base - penalty)));
	// critical 分流:仅当前用事 must_avoid 命中的 critical 才否决(topicMaster 已为重大缔结型
	// 用事登记 moon_void_of_course);其余 critical 已按最重罚分计入,不再无差别否决。
	const mustAvoid = (topic && topic.must_avoid) || [];
	const hasVetoCritical = (flags || []).some((f) => f.severity === 'critical' && mustAvoid.indexOf(f.id) >= 0);
	// [重标定·校准⑤定版] 档位线按 84 时刻(2026-09 上旬×每 2h)实测分布分位数定(峰 50s/中枢 57):
	// 极佳 ≥70(P97)/不错 ≥66(P76)/及格 ≥57(P48)/不宜 <44(P8)。实测落带:及格 52.4%/
	// 不错+ 23.8%/极佳 2.4%/不宜 8.3%(旧线 85/70/55/40 在旧罚分体系下及格率≈0=用户实报根因)。
	// 分布回归闸=__tests__/scoringDistribution.test.js(:8899 在线才跑,带宽含 7 天窗统计波动)。
	let grade;
	if(hasVetoCritical || score < 44) grade = 'disqualified';
	else if(score >= 70) grade = 'excellent';
	else if(score >= 66) grade = 'good';
	else if(score >= 57) grade = 'fair';
	else grade = 'poor';
	return { score, grade, penalty, base: Math.round(base) };
}

export const GRADE_CN = { excellent: '极佳', good: '不错', fair: '中等', poor: '欠佳', disqualified: '不宜（含红线）' };

// [重标定] 单源工具导出:压测/流派计权等测试的「手算核对」必须消费这两个函数——
// 测试内复制公式=第二实现,重标定一次就漂移一次(校准③全站 8 红的根因之一)。
export function computePenalty(flags){ return Math.round(saturate(dedupedPenalty(flags))); }
export function stretchBase(b){ const s = b >= 50 ? 50 + (b - 50) * 1.6 : 50 + (b - 50) * 1.15; return Math.max(0, Math.min(100, s)); }

export default scoreReport;
