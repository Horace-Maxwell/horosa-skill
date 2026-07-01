// 五行力量统计（通行示例方案，权重可配置、公式公开；学理见八字大全 §9.1.1「量化打分法」）。
// ⚠ 诚实：各家权重/阈值无统一标准（这是不同软件「自动喜用神」打架的根因），故默认给一组
//   透明的通行权重，opts.weights 可整组覆盖，面板与 AI 均附公式。纯展示派生，不改四柱/大运/神煞。
// 输入：buildLocalBaziResult().bazi.fourColumns（每柱 stem.element / stemInBranch[].element，
//   element 取值 Wood/Fire/Earth/Metal/Water，藏干按 本气→中气→余气 顺序）。

const EL_KEYS = ['Wood', 'Fire', 'Earth', 'Metal', 'Water'];
const EL_LABEL = { Wood: '木', Fire: '火', Earth: '土', Metal: '金', Water: '水' };
// 生我（印枭）：火←木、土←火、金←土、水←金、木←水
const GEN_BY = { Wood: 'Water', Fire: 'Wood', Earth: 'Fire', Metal: 'Earth', Water: 'Metal' };

const DEFAULT_WEIGHTS = {
	tianGan: 100,      // 透出天干各 +100
	cangBenQi: 100,    // 地支本气藏干 +100
	cangZhongQi: 60,   // 地支中气藏干 +60
	cangYuQi: 30,      // 地支余气藏干 +30
	monthMult: 1.5,    // 月令（得令）地支藏干 ×1.5（通行版：整月藏干均得令加权）
};

const PILLARS = ['year', 'month', 'day', 'time'];

// 返回 { scores:[{key,label,score,percent}](木火土金水序), total, dominant, weakest, dayMaster, weights, method, cangVersion }
// opt.cangVersion='fenye'（分野加权）+ opt.siLingGan（月令当前司令之干，取 fenYe.ruler.gan）：
//   月柱藏干不再整月匀加 monthMult，而是仅「当令司令」之干吃 monthMult（得令本气），
//   其余月支藏干退回基础位权（present 但未值令、不加月乘）。默认 'common' 与历史口径字节一致（零回归）。
export function computeWuxingStrength(four, options){
	if(!four){ return null; }
	const opt = options || {};
	const w = Object.assign({}, DEFAULT_WEIGHTS, opt.weights || {});
	const cangW = [w.cangBenQi, w.cangZhongQi, w.cangYuQi];
	const fenye = opt.cangVersion === 'fenye';
	const siLingGan = fenye ? (opt.siLingGan || '') : '';
	const raw = { Wood: 0, Fire: 0, Earth: 0, Metal: 0, Water: 0 };

	PILLARS.forEach((pk) => {
		const p = four[pk];
		if(!p){ return; }
		const stemEl = p.stem && p.stem.element;
		if(stemEl && raw[stemEl] != null){ raw[stemEl] += w.tianGan; }
		const isMonth = pk === 'month';
		const cang = p.stemInBranch || [];
		cang.forEach((s, idx) => {
			const e = s && s.element;
			if(!(e && raw[e] != null)){ return; }
			const base = cangW[idx] != null ? cangW[idx] : w.cangYuQi;
			let mult = isMonth ? w.monthMult : 1;
			if(isMonth && fenye){
				// 分野加权：仅司令之干得令（×monthMult），其余月支藏干不加月乘（×1）。
				// siLingGan 缺省（节气边缘 fenYe 算不出）时退回通行版整月加权，保证不塌成 0。
				mult = siLingGan ? ((s.cell === siLingGan) ? w.monthMult : 1) : w.monthMult;
			}
			raw[e] += base * mult;
		});
	});

	const total = EL_KEYS.reduce((a, e) => a + raw[e], 0) || 1;
	const r1 = (n) => Math.round(n * 10) / 10;
	const scores = EL_KEYS.map((e) => ({
		key: e,
		label: EL_LABEL[e],
		score: r1(raw[e]),
		percent: r1((raw[e] / total) * 100),
	}));
	const sorted = scores.slice().sort((a, b) => b.score - a.score);

	// 同党（印+比）/ 异党（食伤财官杀），相对日主
	const dayEl = four.day && four.day.stem && four.day.stem.element;
	let dayMaster = null;
	if(dayEl && raw[dayEl] != null){
		const yin = GEN_BY[dayEl]; // 生我=印枭
		const same = raw[yin] + raw[dayEl];
		const other = total - same;
		const ratio = same / total;
		const strongCut = opt.strongCut != null ? opt.strongCut : 0.55;
		const weakCut = opt.weakCut != null ? opt.weakCut : 0.45;
		let verdict = '中和';
		if(ratio > strongCut){ verdict = '身强'; }
		else if(ratio < weakCut){ verdict = '身弱'; }
		dayMaster = {
			element: EL_LABEL[dayEl],
			same: r1(same),
			other: r1(other),
			samePercent: r1(ratio * 100),
			verdict,
		};
	}

	return {
		scores,
		total: r1(total),
		dominant: sorted[0] ? sorted[0].label : '',
		weakest: sorted[sorted.length - 1] ? sorted[sorted.length - 1].label : '',
		dayMaster,
		weights: w,
		cangVersion: fenye ? 'fenye' : 'common',
		method: fenye ? '分野加权' : '通行示例',
	};
}

export default computeWuxingStrength;
