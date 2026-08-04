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

// ── 三维分列(得令/得地/得势)数据表 —— 学理见八字大全 §9.1;全部只供新增 dimensions 字段,
//    不参与 scores/percent/verdict 计算(零回归)。 ──
// 月支 → 季(三会);四库月对土日主特判「四季土旺」(土旺四季通行口径),非土日主仍按所属季。
const BRANCH_SEASON = {
	寅: 'spring', 卯: 'spring', 辰: 'spring',
	巳: 'summer', 午: 'summer', 未: 'summer',
	申: 'autumn', 酉: 'autumn', 戌: 'autumn',
	亥: 'winter', 子: 'winter', 丑: 'winter',
};
// 季 → 各五行 旺/相/休/囚/死(§1.4 表:当令旺·我生相·生我休·克我囚·我克死)。
const SEASON_STATE = {
	spring: { Wood: '旺', Fire: '相', Water: '休', Metal: '囚', Earth: '死' },
	summer: { Fire: '旺', Earth: '相', Wood: '休', Water: '囚', Metal: '死' },
	autumn: { Metal: '旺', Water: '相', Earth: '休', Fire: '囚', Wood: '死' },
	winter: { Water: '旺', Wood: '相', Metal: '休', Earth: '囚', Fire: '死' },
	siji:   { Earth: '旺', Metal: '相', Fire: '休', Wood: '囚', Water: '死' },
};
const STATE_SCORE = { 旺: 40, 相: 30, 休: -10, 囚: -20, 死: -30 };
// 十干禄(临官)支与阳刃(阳干帝旺)支;十干长生支(通行十二长生,水土之干各从其表)。
const LU_ZHI = { 甲: '寅', 乙: '卯', 丙: '巳', 丁: '午', 戊: '巳', 己: '午', 庚: '申', 辛: '酉', 壬: '亥', 癸: '子' };
const REN_ZHI = { 甲: '卯', 丙: '午', 戊: '午', 庚: '酉', 壬: '子' };
const CHANG_SHENG_ZHI = { 甲: '亥', 乙: '午', 丙: '寅', 丁: '酉', 戊: '寅', 己: '酉', 庚: '巳', 辛: '子', 壬: '申', 癸: '卯' };
const KU_ZHI = new Set(['辰', '戌', '丑', '未']);
// 通根分级分值(禄刃 > 本气/本气库 > 长生 > 中气 > 余气;月支根加倍,§9.1.1)。
const ROOT_SCORE = { 禄刃: 30, 本气库: 25, 本气: 20, 长生: 15, 中气: 10, 余气: 6 };
const PILLAR_CN = { year: '年支', month: '月支', day: '日支', time: '时支' };

// 三维分列:得令(月令旺衰) / 得地(通根分级) / 得势(透干印比)。纯新增,输入同主函数。
function computeDimensions(four, dayEl, dayGan){
	if(!dayEl || !dayGan){ return null; }
	// 得令:月支定季(土日主逢四库月按「四季土」行)。
	const monZhi = four.month && four.month.branch ? four.month.branch.cell : '';
	let deLing = null;
	if(monZhi && BRANCH_SEASON[monZhi]){
		const season = (dayEl === 'Earth' && KU_ZHI.has(monZhi)) ? 'siji' : BRANCH_SEASON[monZhi];
		const state = SEASON_STATE[season][dayEl] || '休';
		deLing = { state, score: STATE_SCORE[state] || 0, got: state === '旺' || state === '相' };
	}
	// 得地:四支通根分级(藏干含日主五行者记根;禄刃支 > 本气(库) > 长生支中余气 > 中气 > 余气)。
	const roots = [];
	let deDiScore = 0;
	PILLARS.forEach((pk) => {
		const p = four[pk];
		const zhi = p && p.branch ? p.branch.cell : '';
		const cang = (p && p.stemInBranch) || [];
		const idx = cang.findIndex((c) => c && c.element === dayEl);
		if(idx < 0 || !zhi){ return; }
		let type;
		if(LU_ZHI[dayGan] === zhi || REN_ZHI[dayGan] === zhi){ type = '禄刃'; }
		else if(idx === 0){ type = KU_ZHI.has(zhi) ? '本气库' : '本气'; }
		else if(CHANG_SHENG_ZHI[dayGan] === zhi){ type = '长生'; }
		else { type = idx === 1 ? '中气' : '余气'; }
		const base = ROOT_SCORE[type] || 6;
		const score = pk === 'month' ? base * 2 : base;
		deDiScore += score;
		roots.push({ pillar: PILLAR_CN[pk], branch: zhi, type, score });
	});
	// 得势:年/月/时透干中的 印(印枭)与 比劫 计数与力量。
	const helpers = [];
	['year', 'month', 'time'].forEach((pk) => {
		const st = four[pk] && four[pk].stem;
		const rel = st && st.relative ? st.relative : '';
		if(rel === '印' || rel === '枭' || rel === '比' || rel === '劫'){
			helpers.push({ pillar: PILLAR_CN[pk].replace('支', '干'), gan: st.cell, rel });
		}
	});
	const deShi = { count: helpers.length, stems: helpers, score: helpers.length * 20 };
	const parts = [];
	if(deLing){ parts.push(deLing.got ? `得令(${deLing.state})` : `失令(${deLing.state})`); }
	parts.push(roots.length ? `得地(${roots.length}根)` : '不得地');
	parts.push(deShi.count ? `得势(${deShi.count}透)` : '不得势');
	return { deLing, deDi: { roots, score: Math.round(deDiScore) }, deShi, summary: parts.join('·') };
}

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
		// 三维分列(得令/得地/得势)——纯新增展示派生;上面全部既有字段的取值路径未变。
		dimensions: computeDimensions(four, dayEl, four.day && four.day.stem ? four.day.stem.cell : ''),
		weights: w,
		cangVersion: fenye ? 'fenye' : 'common',
		method: fenye ? '分野加权' : '通行示例',
	};
}

export default computeWuxingStrength;
