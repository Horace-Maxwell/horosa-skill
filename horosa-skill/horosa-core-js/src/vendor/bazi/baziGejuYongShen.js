import { computeTiaoHou } from './baziTiaoHou.js';
import { computeZaGe } from './baziZaGe.js';

// 八字「定格 + 取用神」解读层（公共，非 private）。学理：八字大全 §9.2.1 月令定格、§9.5 取用神决策。
// ⚠ 诚实：取用神各派路径不同（格局派/扶抑派/调候派/通关），结果可异。本模块给：
//   ① 正格（月令定格，机械规则，争议小）；② 扶抑派用神（身强抑、身弱扶，由日主旺衰直接派生）。
//   调候/格局派用神为后续；面板与 AI 均标注「扶抑派」以免冒充唯一答案。
// 纯展示派生，输入 = buildLocalBaziResult().bazi.fourColumns + bazi.wuxingStat（日主旺衰）。

const EL_LABEL = { Wood: '木', Fire: '火', Earth: '土', Metal: '金', Water: '水' };
// 相对日主五行：我生=食伤、生我=印枭、我克=财、克我=官杀、同我=比劫
const GEN = { Wood: 'Fire', Fire: 'Earth', Earth: 'Metal', Metal: 'Water', Water: 'Wood' };
const GEN_BY = { Wood: 'Water', Fire: 'Wood', Earth: 'Fire', Metal: 'Earth', Water: 'Metal' };
const KE = { Wood: 'Earth', Fire: 'Metal', Earth: 'Water', Metal: 'Wood', Water: 'Fire' };
const KE_BY = { Wood: 'Metal', Fire: 'Water', Earth: 'Wood', Metal: 'Fire', Water: 'Earth' };

// 十神短名 → 正格名（§9.2.2）；比/劫 另起建禄/阳刃（§9.2.1 末条）
const GE_NAME = {
	官: '正官格', 杀: '七杀格', 财: '正财格', 才: '偏财格',
	印: '正印格', 枭: '偏印格', 食: '食神格', 伤: '伤官格',
};

function stemCellsExceptDay(four){
	return ['year', 'month', 'time']
		.map((k) => four[k] && four[k].stem ? four[k].stem.cell : '')
		.filter(Boolean);
}

// 正格定格（§9.2.1 优先级）：本气透干→本气十神；本气不透而中/余气透→透出者；皆不透→本气（暗）；本气比劫→建禄/阳刃
function computeGeju(four){
	const monthCang = (four.month && four.month.stemInBranch) || [];
	if(!monthCang.length){ return null; }
	const benqi = monthCang[0];
	const benqiRel = benqi && benqi.relative ? benqi.relative : '';

	// §9.2.1 末条优先：月令本气为比/劫 → 建禄/阳刃格（不以比劫为格，不再看透干）
	if(benqiRel === '比'){ return { name: '建禄格', tenGod: '比', gan: benqi.cell, via: '月令本气' }; }
	if(benqiRel === '劫'){ return { name: '阳刃格', tenGod: '劫', gan: benqi.cell, via: '月令本气' }; }

	// 否则按透干优先：本气透→本气；本气不透而中/余气透→透出者；皆不透→本气（暗藏）
	const touStems = stemCellsExceptDay(four);
	const benqiTou = benqi && touStems.indexOf(benqi.cell) >= 0;
	let source = benqi;
	let via = benqiTou ? '本气透干' : '本气暗藏';
	if(benqi && !benqiTou){
		const touIdx = monthCang.findIndex((c, i) => i > 0 && touStems.indexOf(c.cell) >= 0);
		if(touIdx > 0){
			source = monthCang[touIdx];
			via = (touIdx === monthCang.length - 1 ? '余气透干' : '中气透干');
		}
	}
	const rel = source && source.relative ? source.relative : '';
	const name = GE_NAME[rel] || (rel ? `${rel}格` : '未定');
	return { name, tenGod: rel, gan: source && source.cell ? source.cell : '', via };
}

// 扶抑派用神（§9.5）：身强抑（喜食伤·财·官杀，忌印·比劫）；身弱扶（喜印·比劫，忌食伤·财·官杀）
function computeFuyiYongShen(four, wuxingStat){
	const dayEl = four.day && four.day.stem ? four.day.stem.element : '';
	if(!dayEl || !wuxingStat || !wuxingStat.dayMaster){ return null; }
	const verdict = wuxingStat.dayMaster.verdict;
	const yin = GEN_BY[dayEl], bi = dayEl, shi = GEN[dayEl], cai = KE[dayEl], guan = KE_BY[dayEl];
	const uniq = (arr) => Array.from(new Set(arr)).map((e) => EL_LABEL[e]);
	let xi = [], ji = [], note;
	if(verdict === '身强'){
		xi = uniq([shi, cai, guan]); ji = uniq([yin, bi]);
		note = '身强宜泄耗克：喜食伤泄、财耗、官杀克；忌印生、比劫助。';
	}else if(verdict === '身弱'){
		xi = uniq([yin, bi]); ji = uniq([shi, cai, guan]);
		note = '身弱宜生扶：喜印生、比劫助；忌食伤泄、财耗、官杀克。';
	}else{
		xi = uniq([shi]); ji = [];
		note = '中和近衡：宜流通（食伤泄秀／通关），或从格局、调候定用。';
	}
	return { school: '扶抑派', verdict, xi, ji, note };
}

// 五合化神（element）：甲己化土、乙庚化金、丙辛化水、丁壬化木、戊癸化火
const WU_HE = { 甲己: 'Earth', 己甲: 'Earth', 乙庚: 'Metal', 庚乙: 'Metal', 丙辛: 'Water', 辛丙: 'Water', 丁壬: 'Wood', 壬丁: 'Wood', 戊癸: 'Fire', 癸戊: 'Fire' };
// 专旺/一行得气格名 by 日主 element（§9.3.2）
const ZHUAN_WANG = { Wood: '曲直格', Fire: '炎上格', Earth: '稼穑格', Metal: '从革格', Water: '润下格' };

function dayHasBenQiRoot(four, dayEl){
	return ['year', 'month', 'day', 'time'].some((k) => {
		const c = four[k] && four[k].stemInBranch && four[k].stemInBranch[0];
		return c && c.element === dayEl;
	});
}

// 变格检测（§9.3，量化近似 + 结构判定；只「提示候选」并附真假复核说明，不覆盖扶抑用神以免误判）
function computeBianGe(four, wuxingStat){
	const dm = wuxingStat && wuxingStat.dayMaster;
	const dayStem = four.day && four.day.stem;
	if(!dm || !dayStem || !dayStem.element){ return null; }
	const dayEl = dayStem.element;
	const dayGan = dayStem.cell;
	const same = dm.samePercent;
	const scoreOf = {};
	(wuxingStat.scores || []).forEach((s) => { scoreOf[s.key] = s.percent; });
	const hasRoot = dayHasBenQiRoot(four, dayEl);
	const out = [];

	if(same >= 85 && hasRoot){
		out.push({
			type: '专旺/从强', name: ZHUAN_WANG[dayEl],
			cond: `同党${same}%·日主成势`, yong: '顺势（印·比·食伤泄秀）', bei: '官杀（逆势引战）',
			note: '须地支会方/会局、无克破方为真专旺，请复核。',
		});
	}else if(same <= 12 && !hasRoot){
		const shi = GEN[dayEl], cai = KE[dayEl], guan = KE_BY[dayEl];
		const trio = [[shi, scoreOf[shi] || 0], [cai, scoreOf[cai] || 0], [guan, scoreOf[guan] || 0]];
		const mx = Math.max(trio[0][1], trio[1][1], trio[2][1]);
		const mn = Math.min(trio[0][1], trio[1][1], trio[2][1]);
		// 从势格（§9.3.1）：财官食三势均旺、无一独大、日主无依 → 顺三势，以财通关；先于从儿/从财/从杀判。
		if(mn >= 15 && mx - mn <= 12){
			out.push({
				type: '从势', name: '从势格',
				cond: `同党${same}%·食${trio[0][1]}%财${trio[1][1]}%官杀${trio[2][1]}%三势均停`,
				yong: `顺三势·以${EL_LABEL[cai]}(财)通关（食伤生财、财生官杀）`, bei: '印·比劫（破从）',
				note: '从势须三势均旺无一独大；若一势独旺则依从儿/从财/从杀论，请复核。',
			});
		}else{
			const cand = [['从儿格', shi], ['从财格', cai], ['从杀格', guan]]
				.sort((a, b) => (scoreOf[b[1]] || 0) - (scoreOf[a[1]] || 0))[0];
			out.push({
				type: '从弱', name: cand[0],
				cond: `同党${same}%·日主无本气根`, yong: `顺${EL_LABEL[cand[1]]}之势`, bei: '印·比劫（破从）',
				note: '真从须印比无根不现；尚有微根为假从，逢帮身运败，请复核。',
			});
		}
	}

	// 两神成象（§9.3.4）：全局只见两行、各占其半（余行近无、日主居其一）。
	// 相生两象喜两行流通；相克（相成）两象须通关之神；均忌第三行破象。
	const desc = ['Wood', 'Fire', 'Earth', 'Metal', 'Water']
		.map((e) => ({ e, p: scoreOf[e] || 0 })).sort((a, b) => b.p - a.p);
	const t1 = desc[0], t2 = desc[1], t3 = desc[2];
	if(t1 && t2 && t2.p >= 35 && t1.p + t2.p >= 85 && (!t3 || t3.p <= 8) && (dayEl === t1.e || dayEl === t2.e)){
		const la = EL_LABEL[t1.e], lb = EL_LABEL[t2.e];
		if(GEN[t1.e] === t2.e || GEN[t2.e] === t1.e){
			const mu = GEN[t1.e] === t2.e ? t1.e : t2.e; // 母(生方)
			const zi = GEN[mu];
			out.push({
				type: '两神成象', name: `${EL_LABEL[mu]}${EL_LABEL[zi]}相生两象`,
				cond: `${la}${t1.p}%·${lb}${t2.p}%·余行近无`,
				yong: '两行流通为用（顺其气势）', bei: '第三行破象（尤忌克泄交加）',
				note: '相生两象贵在纯粹流通；行运引出第三行即破象，请复核。',
			});
		}else{
			const gong = KE[t1.e] === t2.e ? t1.e : t2.e; // 攻方(克者)
			const tgEl = GEN[gong]; // 通关之神：攻方所生、又生受方（GEN[GEN[A]]===KE[A]）
			out.push({
				type: '两神成象', name: `${la}${lb}相成两象`,
				cond: `${la}${t1.p}%·${lb}${t2.p}%·两行相战`,
				yong: `取${EL_LABEL[tgEl]}通关（${EL_LABEL[gong]}生${EL_LABEL[tgEl]}生${EL_LABEL[KE[gong]]}）`,
				bei: '无通关而两行交战',
				note: '相克两象须食伤或印通关成象；通关神被夺即破，请复核。',
			});
		}
	}

	[['月干', four.month && four.month.stem && four.month.stem.cell], ['时干', four.time && four.time.stem && four.time.stem.cell]].forEach((pair) => {
		const pos = pair[0];
		const g = pair[1];
		if(!g){ return; }
		const huaEl = WU_HE[dayGan + g];
		if(huaEl){
			const monBen = four.month && four.month.stemInBranch && four.month.stemInBranch[0];
			const deLing = !!(monBen && monBen.element === huaEl);
			out.push({
				type: '化气', name: `${dayGan}${g}合化${EL_LABEL[huaEl]}`,
				cond: `日干合${pos}·${deLing ? '化神当令' : '化神未必得令'}`,
				yong: `生扶${EL_LABEL[huaEl]}`, bei: `克泄${EL_LABEL[huaEl]}`,
				note: deLing ? '化神当令近真化；须无争合、无克破方成。' : '化神未得令恐假化，待运补化神，请复核。',
			});
		}
	});
	return out.length ? out : null;
}

function scoreMap(wuxingStat){
	const m = {};
	((wuxingStat && wuxingStat.scores) || []).forEach((s) => { m[s.key] = s.percent; });
	return m;
}

// 病药派用神（§9.5 / §6.7 神峰通考）：忌神最旺者为「病」，取克病之神为「药」。
function computeBingYao(four, wuxingStat){
	const dm = wuxingStat && wuxingStat.dayMaster;
	const dayEl = four.day && four.day.stem ? four.day.stem.element : '';
	if(!dm || !dayEl){ return null; }
	const score = scoreMap(wuxingStat);
	const yin = GEN_BY[dayEl], bi = dayEl, shi = GEN[dayEl], cai = KE[dayEl], guan = KE_BY[dayEl];
	let jiEls;
	if(dm.verdict === '身强'){ jiEls = [yin, bi]; }
	else if(dm.verdict === '身弱'){ jiEls = [shi, cai, guan]; }
	else { return null; }
	jiEls = Array.from(new Set(jiEls));
	let bing = null, bScore = -1;
	jiEls.forEach((e) => { const s = score[e] || 0; if(s > bScore){ bScore = s; bing = e; } });
	if(!bing || bScore < 15){ return null; }
	const yao = KE_BY[bing];
	return {
		school: '病药派',
		xi: [EL_LABEL[yao]],
		ji: [EL_LABEL[bing]],
		note: `局病在${EL_LABEL[bing]}(${bScore}%${dm.verdict === '身强' ? '·助身太过' : '·克泄耗太过'})，取${EL_LABEL[yao]}制病为药。`,
	};
}

// 通关派用神（§9.5）：两强相争(A克B 皆旺且僵持) → 取生化中介之神(A生C生B)通关。
function computeTongGuan(four, wuxingStat){
	if(!wuxingStat || !Array.isArray(wuxingStat.scores)){ return null; }
	const score = scoreMap(wuxingStat);
	const els = ['Wood', 'Fire', 'Earth', 'Metal', 'Water'];
	let best = null;
	els.forEach((A) => {
		const B = KE[A];
		const guan = GEN[A]; // A生guan、guan生B（GEN[GEN[A]]===KE[A]）
		const sa = score[A] || 0, sb = score[B] || 0, sg = score[guan] || 0;
		if(sa >= 18 && sb >= 18 && Math.abs(sa - sb) <= 18 && sg < Math.min(sa, sb)){
			const need = Math.min(sa, sb) - sg;
			if(!best || need > best.need){ best = { need, a: A, b: B, guan, sa, sb }; }
		}
	});
	if(!best){ return null; }
	return {
		school: '通关派',
		xi: [EL_LABEL[best.guan]],
		// 忌=克通关之神者：通关神被夺则两强复战（与两神成象「通关神被夺即破」同口径）。
		ji: [EL_LABEL[KE_BY[best.guan]]],
		note: `${EL_LABEL[best.a]}${EL_LABEL[best.b]}交战(${best.sa}%/${best.sb}%)，取${EL_LABEL[best.guan]}通关（${EL_LABEL[best.a]}生${EL_LABEL[best.guan]}生${EL_LABEL[best.b]}）；忌${EL_LABEL[KE_BY[best.guan]]}夺通关。`,
	};
}

// 格局派相神（§9.2.2）：顺用格生护、逆用格制化，相对日主取相神五行。
// ji=坏格忌神之五行（与成败救应 GE_JI 十神口径同源转译）——此前恒空致对照表「忌」列无据。
function computeGejuYong(four, geju){
	const dayEl = four.day && four.day.stem ? four.day.stem.element : '';
	if(!geju || !geju.tenGod || !dayEl){ return null; }
	const yin = GEN_BY[dayEl], bi = dayEl, shi = GEN[dayEl], cai = KE[dayEl], guan = KE_BY[dayEl];
	const MAP = {
		官: { xi: [cai, yin], ji: [shi], note: '正官格顺用：财生官、印护身；忌伤官见官、刑冲。' },
		杀: { xi: [shi, yin], ji: [cai], note: '七杀格逆用：食神制杀、印化杀；忌财党生杀攻身。' },
		财: { xi: [shi, guan], ji: [bi], note: '财格顺用：食伤生财、官护财；忌比劫夺财。' },
		才: { xi: [shi, guan], ji: [bi], note: '偏财格顺用：食伤生财、官护财；忌比劫夺财。' },
		印: { xi: [guan], ji: [cai], note: '正印格顺用：官杀生印；忌财坏印。' },
		枭: { xi: [cai], ji: [yin], note: '偏印格逆用：财制枭；忌枭夺食。' },
		食: { xi: [cai], ji: [yin], note: '食神格顺用：财泄食、身旺有气；忌枭印夺食。' },
		伤: { xi: [yin, cai], ji: [guan], note: '伤官格逆用：伤官配印、伤官生财；忌伤官见官。' },
		比: { xi: [guan, shi, cai], ji: [bi], note: '建禄格无格：另取官杀/食伤/财为用；忌比劫再成群。' },
		劫: { xi: [guan, shi], ji: [bi], note: '阳刃格逆用：官杀制刃、食伤泄秀；忌群刃无制。' },
	};
	const m = MAP[geju.tenGod];
	if(!m){ return null; }
	const xi = Array.from(new Set(m.xi)).map((e) => EL_LABEL[e]);
	const ji = Array.from(new Set(m.ji || [])).map((e) => EL_LABEL[e]).filter((l) => xi.indexOf(l) < 0);
	return { school: '格局派', xi, ji, note: `${geju.name}·相神 ${xi.join('·')}。${m.note}` };
}

// ── 成败救应（§9.2.2）小数据表：六冲对/三刑组/天干五合对/各格破格忌神(十神短名) ──
const ZHI_CHONG = { 子: '午', 午: '子', 丑: '未', 未: '丑', 寅: '申', 申: '寅', 卯: '酉', 酉: '卯', 辰: '戌', 戌: '辰', 巳: '亥', 亥: '巳' };
const ZHI_XING = { 寅: ['巳', '申'], 巳: ['寅', '申'], 申: ['寅', '巳'], 丑: ['戌', '未'], 戌: ['丑', '未'], 未: ['丑', '戌'], 子: ['卯'], 卯: ['子'], 辰: ['辰'], 午: ['午'], 酉: ['酉'], 亥: ['亥'] };
const GAN_HE_PAIR = { 甲: '己', 己: '甲', 乙: '庚', 庚: '乙', 丙: '辛', 辛: '丙', 丁: '壬', 壬: '丁', 戊: '癸', 癸: '戊' };
const GE_JI = {
	官: { rels: ['伤'], why: '伤官见官' },
	财: { rels: ['比', '劫'], why: '比劫夺财' },
	才: { rels: ['比', '劫'], why: '比劫夺财' },
	印: { rels: ['财', '才'], why: '财星坏印' },
	食: { rels: ['枭'], why: '枭神夺食' },
	伤: { rels: ['官'], why: '伤官见官' },
	枭: { rels: ['食'], why: '枭夺食伤局' },
};

// 成败救应判定（§9.2.2）：相神得力→成格；忌神坏相/月令刑冲→破格；忌神被合去/克制→败中复成。
// 只依「透干十神 + 四支本气 + 月支刑冲」的机械判据，量化近似必带请复核提示；纯新增字段。
function computeChengBai(four, geju, gejuYong){
	if(!geju || !geju.tenGod){ return null; }
	const tou = ['year', 'month', 'time']
		.map((k) => four[k] && four[k].stem ? four[k].stem : null)
		.filter((s) => s && s.cell);
	const benqiEls = ['year', 'month', 'day', 'time']
		.map((k) => four[k] && four[k].stemInBranch && four[k].stemInBranch[0] ? four[k].stemInBranch[0].element : '')
		.filter(Boolean);
	const relOf = (s) => (s && s.relative ? s.relative : '');
	const CN2EL = { 木: 'Wood', 火: 'Fire', 土: 'Earth', 金: 'Metal', 水: 'Water' };

	// ① 忌神坏格：查各格忌神透干（杀格=财党无制、阳刃=刃旺无制、建禄=群比无依 另判）
	const breaks = [];
	const g = GE_JI[geju.tenGod];
	if(g){
		tou.forEach((s) => { if(g.rels.indexOf(relOf(s)) >= 0){ breaks.push({ gan: s.cell, el: s.element, why: g.why }); } });
	}
	if(geju.tenGod === '杀'){
		const caiTou = tou.filter((s) => relOf(s) === '财' || relOf(s) === '才');
		const hasShi = tou.some((s) => relOf(s) === '食' || relOf(s) === '伤');
		if(caiTou.length && !hasShi){ caiTou.forEach((s) => breaks.push({ gan: s.cell, el: s.element, why: '财党生杀攻身（无食制）' })); }
	}
	if(geju.tenGod === '劫'){
		const hasZhi = tou.some((s) => ['官', '杀', '食', '伤'].indexOf(relOf(s)) >= 0)
			|| benqiEls.indexOf(KE_BY[four.day.stem.element]) >= 0;
		if(!hasZhi){ breaks.push({ gan: '', el: '', why: '刃旺无制（官杀食伤俱缺）' }); }
	}
	if(geju.tenGod === '比'){
		const biCnt = tou.filter((s) => relOf(s) === '比' || relOf(s) === '劫').length;
		const hasYong = tou.some((s) => ['官', '杀', '财', '才', '食', '伤'].indexOf(relOf(s)) >= 0);
		if(biCnt >= 2 && !hasYong){ breaks.push({ gan: '', el: '', why: '比劫成群无泄无克' }); }
	}
	// ② 月令刑冲动摇格基
	const monZhi = four.month && four.month.branch ? four.month.branch.cell : '';
	const others = ['year', 'day', 'time'].map((k) => four[k] && four[k].branch ? four[k].branch.cell : '').filter(Boolean);
	if(monZhi){
		if(others.indexOf(ZHI_CHONG[monZhi]) >= 0){ breaks.push({ gan: '', el: '', why: `月令${monZhi}逢冲` }); }
		else if((ZHI_XING[monZhi] || []).some((x) => others.indexOf(x) >= 0)){ breaks.push({ gan: '', el: '', why: `月令${monZhi}逢刑` }); }
	}
	// ③ 相神得力：格局派相神五行 透干或四支本气藏之
	const xiEls = ((gejuYong && gejuYong.xi) || []).map((cn) => CN2EL[cn]).filter(Boolean);
	let xiang = null;
	tou.forEach((s) => { if(!xiang && xiEls.indexOf(s.element) >= 0){ xiang = { how: '透干', gan: s.cell, el: EL_LABEL[s.element] }; } });
	if(!xiang){
		const hitEl = xiEls.find((e) => benqiEls.indexOf(e) >= 0);
		if(hitEl){ xiang = { how: '本气藏支', gan: '', el: EL_LABEL[hitEl] }; }
	}
	// ④ 救应：忌神干被五合（余三干或日干合之）或被透干克制 → 败中复成
	const allGans = ['year', 'month', 'day', 'time'].map((k) => four[k] && four[k].stem ? four[k].stem.cell : '').filter(Boolean);
	const rescues = [];
	breaks.forEach((b) => {
		if(!b.gan){ return; }
		if(allGans.some((x) => x !== b.gan && GAN_HE_PAIR[b.gan] === x)){ rescues.push(`${b.gan}被${GAN_HE_PAIR[b.gan]}合去`); return; }
		const keSrc = tou.find((s) => s.element && b.el && KE[s.element] === b.el && s.cell !== b.gan);
		if(keSrc){ rescues.push(`${keSrc.cell}(${EL_LABEL[keSrc.element]})克制${b.gan}`); }
	});

	let verdict, reason;
	if(breaks.length){
		const whys = breaks.map((b) => b.why).join('、');
		if(rescues.length){ verdict = '败中复成'; reason = `${whys}；幸 ${rescues.join('、')}，破而有救。`; }
		else { verdict = '破格'; reason = `${whys}，忌神坏格无救。`; }
	}else if(xiang){
		verdict = '成格';
		reason = `相神${xiang.el}${xiang.how}${xiang.gan ? `(${xiang.gan})` : ''}得力，格局有成。`;
	}else{
		verdict = '待复核';
		reason = '无明显破格忌神，然相神不透不藏、得力与否待参旺衰。';
	}
	return { verdict, reason, breaks: breaks.map((b) => b.why), rescues, xiang,
		note: '按透干十神/月令刑冲机械判定，会合牵制之细致变化请人工复核。' };
}

export function computeGejuYongShen(four, wuxingStat){
	if(!four){ return null; }
	const geju = computeGeju(four);
	const fuyi = computeFuyiYongShen(four, wuxingStat);
	const tiaohou = computeTiaoHou(four);
	const bingyao = computeBingYao(four, wuxingStat);
	const tongguan = computeTongGuan(four, wuxingStat);
	const gejuYong = computeGejuYong(four, geju);
	// 多派对照（§7.2：同盘各派可取不同用神，常驻对照、勿冒充唯一答案）
	const schools = [];
	if(fuyi){ schools.push(fuyi); }
	if(gejuYong){ schools.push(gejuYong); }
	// 调候派源表只给用神干、不设忌口径（学理：调候以急缓论、不单列忌）——ji 恒空、注明缘由，不臆造。
	if(tiaohou){ schools.push({ school: '调候派', xi: tiaohou.yong, ji: [], note: `${tiaohou.climate}；${tiaohou.school}·${tiaohou.version}调候用神。调候以寒暖燥湿论急缓，本派不单列忌神。` }); }
	if(bingyao){ schools.push(bingyao); }
	if(tongguan){ schools.push(tongguan); }
	return {
		geju,
		chengBai: computeChengBai(four, geju, gejuYong),
		yongshen: fuyi,
		tiaohou,
		bianGe: computeBianGe(four, wuxingStat),
		zaGe: computeZaGe(four),
		bingyao,
		tongguan,
		gejuYong,
		schools,
	};
}

export default computeGejuYongShen;
