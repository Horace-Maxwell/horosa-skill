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
		const cand = [['从儿格', shi], ['从财格', cai], ['从杀格', guan]]
			.sort((a, b) => (scoreOf[b[1]] || 0) - (scoreOf[a[1]] || 0))[0];
		out.push({
			type: '从弱', name: cand[0],
			cond: `同党${same}%·日主无本气根`, yong: `顺${EL_LABEL[cand[1]]}之势`, bei: '印·比劫（破从）',
			note: '真从须印比无根不现；尚有微根为假从，逢帮身运败，请复核。',
		});
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
		ji: [],
		note: `${EL_LABEL[best.a]}${EL_LABEL[best.b]}交战(${best.sa}%/${best.sb}%)，取${EL_LABEL[best.guan]}通关（${EL_LABEL[best.a]}生${EL_LABEL[best.guan]}生${EL_LABEL[best.b]}）。`,
	};
}

// 格局派相神（§9.2.2）：顺用格生护、逆用格制化，相对日主取相神五行。
function computeGejuYong(four, geju){
	const dayEl = four.day && four.day.stem ? four.day.stem.element : '';
	if(!geju || !geju.tenGod || !dayEl){ return null; }
	const yin = GEN_BY[dayEl], shi = GEN[dayEl], cai = KE[dayEl], guan = KE_BY[dayEl];
	const MAP = {
		官: { xi: [cai, yin], note: '正官格顺用：财生官、印护身；忌伤官见官、刑冲。' },
		杀: { xi: [shi, yin], note: '七杀格逆用：食神制杀、印化杀；忌财党生杀攻身。' },
		财: { xi: [shi, guan], note: '财格顺用：食伤生财、官护财；忌比劫夺财。' },
		才: { xi: [shi, guan], note: '偏财格顺用：食伤生财、官护财；忌比劫夺财。' },
		印: { xi: [guan], note: '正印格顺用：官杀生印；忌财坏印。' },
		枭: { xi: [cai], note: '偏印格逆用：财制枭；忌枭夺食。' },
		食: { xi: [cai], note: '食神格顺用：财泄食、身旺有气；忌枭印夺食。' },
		伤: { xi: [yin, cai], note: '伤官格逆用：伤官配印、伤官生财；忌伤官见官。' },
		比: { xi: [guan, shi, cai], note: '建禄格无格：另取官杀/食伤/财为用。' },
		劫: { xi: [guan, shi], note: '阳刃格逆用：官杀制刃、食伤泄秀；忌群刃无制。' },
	};
	const m = MAP[geju.tenGod];
	if(!m){ return null; }
	const xi = Array.from(new Set(m.xi)).map((e) => EL_LABEL[e]);
	return { school: '格局派', xi, ji: [], note: `${geju.name}·相神 ${xi.join('·')}。${m.note}` };
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
	if(tiaohou){ schools.push({ school: '调候派', xi: tiaohou.yong, ji: [], note: `${tiaohou.climate}；${tiaohou.school}·${tiaohou.version}调候用神。` }); }
	if(bingyao){ schools.push(bingyao); }
	if(tongguan){ schools.push(tongguan); }
	return {
		geju,
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
