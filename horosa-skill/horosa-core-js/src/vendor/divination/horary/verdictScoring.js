// divination/horary/verdictScoring.js
// [卜卦改进 H7] 裁决双轨:
//   'legacy'(缺省)=四源证词+阈值3 三值 leaning——从 horaryEngine.buildVerdict 逐字节搬家,
//     输出对象(positive/negative/posScore/negScore/leaning/summary)键序值全同=零回归;
//   'v2'=证词池扩容(互容/接纳分层/拒绝/时主/恒星/映点/almuten/围攻荣耀/月亮径/自然徵象/
//     宫内驻星/赤纬平行/feral/joy/hayyiz/regret 折减)+同源去重软封顶(择日 dedupedPenalty 范式)
//     +confidence 0-100+五档 band+结构性护栏+三值单调投影。
// 单显规则(UI/快照):一次只显一个权威结论(按 profile);两轨并示仅当一致(防 AI 吃矛盾证词)。
import { PLANETS } from '../data/planets.js';
import { mutualReceptionBetween, receives } from '../engine/reception.js';
import { antisciaPairsOf } from '../engine/resultShapes.js';
import { chartIdOfKey } from '../engine/utils.js';

function cn(k){ return (PLANETS[k] || {}).cn || k || ''; }
const methodCn = (m) => ({ application: '入相位', translation: '光线传递', collection: '光线汇集', position: '落位', antiscion: '映点', reception: '互容' })[m] || m || '';
const destrCn = (d) => ({ no_reception_hard: '无接纳的刑/冲', combustion: '燃烧', separation: '出相位(事已过)', prohibition: '阻碍', frustration: '挫败', refranation: '撤回(临成自退)', abscission: '光线切断' })[d] || d || '受阻';

// ── legacy:horaryEngine.buildVerdict 原文搬家(2026-08 前行为;勿改一字) ──
export function buildVerdictLegacy(ctx){
	const { perf, moon, conds, thirds, querentKey, quesitedKey } = ctx;
	const positive = [];
	const negative = [];
	const push = (arr, text, weight, source) => arr.push({ text, weight: weight || 1, source });

	if(perf){
		if(perf.perfects && !perf.destroyed) push(positive, `完成法命中：${methodCn(perf.method)}${perf.ease === 'easy' ? '（轻松）' : (perf.ease === 'hard' ? '（艰难拖延）' : '')}`, 3, 'perfection');
		if(perf.destroyed) push(negative, `破坏：${destrCn(perf.destruction)}${perf.interferer ? '（' + cn(perf.interferer) + '）' : ''}`, 3, 'perfection');
		if(perf.refranationRisk) push(negative, '完成方逆行 → 恐折返（临成又退、事有反复）', 2, 'perfection');
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

// ── v2:证词池扩容 ──
// 同源去重(择日 dedupedPenalty 范式):同 factor 键取最重全额,其余 30% 折算——
// 防「月亮受克」被空亡/燃烧/凶相三条重复计满。
function dedupedSum(items){
	const byFactor = {};
	items.forEach((it) => { (byFactor[it.factor || it.source] = byFactor[it.factor || it.source] || []).push(it); });
	let sum = 0;
	Object.keys(byFactor).forEach((f) => {
		const arr = byFactor[f].sort((a, b) => b.weight - a.weight);
		arr.forEach((it, i) => { sum += it.weight * (i === 0 ? 1 : 0.3); });
	});
	return sum;
}
// 软封顶(择日 saturate 范式):无穷证词渐近 cap,单侧永不爆表。
function saturate(x, cap){ return cap * (1 - Math.exp(-x / cap)); }

const BANDS = [
	{ key: 'strong_yes', min: 72, cn: '强成', proj: 'yes' },
	{ key: 'lean_yes', min: 58, cn: '倾向成', proj: 'yes' },
	{ key: 'uncertain', min: 42, cn: '未定', proj: 'even' },
	{ key: 'lean_no', min: 28, cn: '倾向不成', proj: 'no' },
	{ key: 'strong_no', min: 0, cn: '难成', proj: 'no' },
];
function bandOf(confidence){
	return BANDS.find((b) => confidence >= b.min) || BANDS[BANDS.length - 1];
}

// v2 证词收集:ctx 扩展面(facts/hourAgreement/fixedStars/almuten/moonPerfection/sigs 全量)。
export function collectTestimoniesV2(ctx){
	const { perf, moon, conds, thirds, querentKey, quesitedKey, facts, hourAgreement, fixedStars, almuten, moonPerfection, sigs } = ctx;
	const positive = [];
	const negative = [];
	const push = (arr, text, weight, source, factor) => arr.push({ text, weight: weight || 1, source, factor: factor || source });

	// ① 完成法(结构性证词,主权重;regret 折减:成而后悔 3→2)
	if(perf){
		if(perf.perfects && !perf.destroyed){
			const w = perf.regret ? 2 : 3;
			push(positive, `完成法命中：${methodCn(perf.method)}${perf.viaMoonPromotion ? '（月亮升格径）' : ''}${perf.ease === 'easy' ? '（轻松）' : (perf.ease === 'hard' ? '（艰难拖延）' : '')}${perf.regret ? '（成而复失折减）' : ''}`, w, 'perfection');
			if(perf.overrodeDestruction){ push(negative, `原判${destrCn(perf.overrodeDestruction)}经中介得救 → 成中带波折`, 1, 'perfection', 'rescue_scar'); }
		}
		if(perf.destroyed){
			push(negative, `破坏：${destrCn(perf.destruction)}${perf.interferer ? '（' + cn(perf.interferer) + '）' : ''}`, 3, 'perfection');
			if(perf.rescue){ push(positive, `盘面另见${perf.rescue.by ? cn(perf.rescue.by) + ' 的' : ''}${methodCn(perf.rescue.method)}可为中介（本档未改判）`, 1, 'perfection', 'rescue_hint'); }
		}
		if(perf.refranationRisk) push(negative, '完成方逆行/临留驻 → 恐折返（临成又退、事有反复）', 2, 'perfection', 'refranation');
	}
	// ② 完成度三分(同 legacy)
	if(thirds){
		const fracText = { all: '三大征象皆安全 → 达成一切', '2/3': '两征象安全 → 约完成 2/3', '1/3': '一征象安全 → 约完成 1/3', none: '三征象皆不安全 → 难成/败坏' }[thirds.fraction];
		if(thirds.fraction === 'all' || thirds.fraction === '2/3') push(positive, `完成度：${fracText}`, 2, 'thirds');
		else push(negative, `完成度：${fracText}`, 2, 'thirds');
	}
	// ③ 月亮(factor 按 finding key 去重:空亡/燃烧/受克同月不叠满)
	(moon.findings || []).forEach((f) => {
		if(f.polarity === 'positive') push(positive, '月亮：' + f.text_zh, f.weight, 'moon', 'moon_' + (f.key || 'g'));
		else if(f.polarity === 'negative') push(negative, '月亮：' + f.text_zh, f.weight, 'moon', 'moon_neg');
	});
	// ④ 两主单星状态(同 legacy;[复审P2] factor=per-planet×per-finding——燃烧/落陷/逆行是
	// 独立缺陷,各自全额;去重只防「同一现象多条描述」,不该把一颗星的不同病折成 30%)。
	[querentKey, quesitedKey].filter(Boolean).forEach((k) => {
		const c = conds[k]; if(!c) return;
		(c.findings || []).forEach((f) => {
			if(f.polarity === 'positive') push(positive, f.text_zh, f.weight, 'condition', `cond_${k}_${f.key || 'g'}`);
			else if(f.polarity === 'negative') push(negative, f.text_zh, f.weight, 'condition', `cond_${k}_${f.key || 'g'}`);
		});
	});
	// ⑤ 互容/接纳分层(契约层;拒绝=供方落陷弱位)
	if(facts && querentKey && quesitedKey && querentKey !== quesitedKey){
		const mu = mutualReceptionBetween(facts, querentKey, quesitedKey);
		if(mu){
			const strong = mu.some((x) => x.strong);
			push(positive, `两主互容（${strong ? '庙旺级' : '次尊贵级'}）→ 彼此接纳`, strong ? 2 : 0.5, 'reception', 'mutual');
		}else{
			const rAB = receives(facts, quesitedKey, querentKey);   // 事项主接纳问者
			const rBA = receives(facts, querentKey, quesitedKey);
			[rAB, rBA].filter(Boolean).forEach((r) => {
				const refuse = (r.supplierRulership || []).some((t) => t === 'exile' || t === 'fall');
				if(refuse){ push(negative, `${cn(r.supplier)} 于弱位接纳 ${cn(r.beneficiary)}（拒绝）`, 1, 'reception', 'refuse'); }
				else if(r.strong){ push(positive, `${cn(r.supplier)} 庙旺接纳 ${cn(r.beneficiary)}`, 1.5, 'reception', 'oneway'); }
				else { push(positive, `${cn(r.supplier)} 次尊贵接纳 ${cn(r.beneficiary)}`, 0.5, 'reception', 'oneway'); }
			});
		}
	}
	// ⑥ 时主一致(正面根基)
	if(hourAgreement && hourAgreement.agree){ push(positive, '时主与徵象相合（根基佐证）', 1, 'hour'); }
	// ⑦ 恒星(王者合徵象 +1;凶性恒星 −2)
	(fixedStars || []).forEach((s) => {
		if(s.nature === 'boost' && s.royal){ push(positive, `${s.point} 会合王者恒星 ${s.star}`, 1, 'star', 'star_royal'); }
		else if(s.nature === 'caution'){ push(negative, `${s.point} 会合凶性恒星 ${s.star}`, 2, 'star', 'star_bad'); }
	});
	// ⑧ 映点/反映点(两主隐合/隐冲)
	if(facts && querentKey && quesitedKey){
		const ca = chartIdOfKey(querentKey); const cb = chartIdOfKey(quesitedKey);
		antisciaPairsOf(facts.result).forEach((x) => {
			const hit = (x.a === ca && x.b === cb) || (x.a === cb && x.b === ca);
			if(!hit){ return; }
			if(x.kind === 'antiscia'){ push(positive, '两主成映点（隐合相助）', 1, 'antiscia', 'anti'); }
			else { push(negative, '两主成对映点（隐冲相违）', 1, 'antiscia', 'contra'); }
		});
	}
	// ⑨ almuten 有利(事项宫头逐度总管=问者星 → 事在问者掌中)
	if(almuten && almuten.quesitedCusp && querentKey && (almuten.quesitedCusp.winners || []).indexOf(querentKey) >= 0){
		push(positive, `事项宫头 almuten＝问者星 ${cn(querentKey)} → 事在问者掌中`, 1, 'almuten');
	}
	// ⑩ [复审P2 拍板] 围攻证词单一记账源=conds(isBesieged 凶围 w2+backendConditionNotes 档的
	// 围荣围耀)——此前本函数再读 besiegement 详断重复计分(凶围/围荣两处叠满)。详断表仍
	// 全量进 UI 卡与快照段,只是不再二次入天平。
	// ⑪ 月亮独立成事径(半个完成法)
	if(moonPerfection && moonPerfection.perfects && !moonPerfection.destroyed && !(perf && perf.perfects)){
		push(positive, `月亮径可成：${methodCn(moonPerfection.method)}（共同徵象星自行接通事项）`, 2, 'moon_path');
	}
	// ⑫ 自然徵象星状态
	if(sigs && sigs.natural && conds[sigs.natural]){
		const sc = conds[sigs.natural].score || 0;
		if(sc > 0){ push(positive, `自然徵象星 ${cn(sigs.natural)} 有力（+${sc}）`, 0.5, 'natural'); }
		else if(sc < 0){ push(negative, `自然徵象星 ${cn(sigs.natural)} 受损（${sc}）`, 0.5, 'natural'); }
	}
	// ⑬ 宫内驻星(低权:吉星护持/凶星盘踞)
	(sigs && sigs.coSignificators || []).forEach((k) => {
		if(k === 'venus' || k === 'jupiter'){ push(positive, `吉星 ${cn(k)} 驻用事宫`, 0.5, 'cosig', 'cosig_good'); }
		else if(k === 'mars' || k === 'saturn'){ push(negative, `凶星 ${cn(k)} 驻用事宫`, 0.5, 'cosig', 'cosig_bad'); }
	});
	// ⑭ 赤纬平行(两主 decl 同号近值=合相性质;H4a 映射)
	if(facts && querentKey && quesitedKey && querentKey !== quesitedKey){
		const pa = facts.planets[querentKey]; const pb = facts.planets[quesitedKey];
		if(pa && pb && pa.decl != null && pb.decl != null && (pa.decl * pb.decl > 0) && Math.abs(pa.decl - pb.decl) < 0.5){
			push(positive, '两主赤纬平行（力≈合相）', 1, 'decl');
		}
	}
	// ⑮ 月野逸/喜乐/得时(facts 旗)
	if(facts){
		const pm = facts.planets.moon;
		if(pm && pm.feral){ push(negative, '月亮野逸（无相位孤行）', 1, 'moon_flag', 'feral'); }
		[querentKey, quesitedKey].filter(Boolean).forEach((k) => {
			const p = facts.planets[k]; if(!p){ return; }
			if(p.joy){ push(positive, `${cn(k)} 入喜乐宫`, 0.5, 'flag', 'joy'); }
			if(p.hayyiz === 'Hayyiz'){ push(positive, `${cn(k)} 得时（hayz）`, 1, 'flag', 'hayyiz'); }
		});
	}
	return { positive, negative };
}

// v2 聚合:去重求和→软封顶→confidence→护栏→band→三值投影。
export function aggregateV2(pool, ctx){
	const posRaw = dedupedSum(pool.positive);
	const negRaw = dedupedSum(pool.negative);
	const pos = saturate(posRaw, 18);
	const neg = saturate(negRaw, 18);
	let confidence = Math.round(50 + (pos - neg) * 4.5);
	const guards = [];
	const perf = ctx.perf;
	// 结构性护栏:完成法是结构证词,不与数值混洗。
	if(perf && perf.perfects && !perf.destroyed && confidence < 58){
		confidence = 58; guards.push('perfection_floor');
	}
	// 天花板=41:BANDS 界含下限(42=uncertain),破坏无援必须压进 lean_no 档。
	if(perf && perf.destroyed && !perf.rescue && confidence > 41){
		confidence = 41; guards.push('destruction_ceiling');
	}
	// [复审P3] 破坏+有救径但本档未改判:上限 57(uncertain 顶)——不许产 lean_yes 与
	// Query I「难成」并行矛盾;有救径的确不该压满 41,留在未定带。
	if(perf && perf.destroyed && perf.rescue && confidence > 57){
		confidence = 57; guards.push('rescue_pending');
	}
	confidence = Math.max(2, Math.min(98, confidence));
	const band = bandOf(confidence);
	// 条件式结论(regret/byWhom/rescued/refranation/月亮升格径)——结构化独立行,UI/快照直接消费。
	const conditions = [];
	if(perf){
		if(perf.regret){ conditions.push({ key: 'regret', text: '成而复失之象：事可成但难持久/多反悔' }); }
		if(perf.byWhom === 'querent_effort'){ conditions.push({ key: 'byWhom', text: '靠问卜者主动努力促成' }); }
		else if(perf.byWhom === 'other_initiates'){ conditions.push({ key: 'byWhom', text: '由对方主动/自愿促成' }); }
		if(perf.rescue && !perf.perfects){ conditions.push({ key: 'rescued', text: `另见${perf.rescue.by ? cn(perf.rescue.by) + ' 的' : ''}${methodCn(perf.rescue.method)}中介之路（本档未改判）` }); }
		if(perf.overrodeDestruction){ conditions.push({ key: 'rescued', text: `破而得救（原判${destrCn(perf.overrodeDestruction)}）→ 可成但带波折` }); }
		if(perf.refranationRisk){ conditions.push({ key: 'refranation', text: '临成有折返之虞（完成方逆行/临留驻）' }); }
		if(perf.viaMoonPromotion){ conditions.push({ key: 'moonPromoted', text: '以月亮升格径成事（主径无完成）' }); }
	}
	return {
		conditions,
		positive: pool.positive, negative: pool.negative,
		posScore: Math.round(pos * 10) / 10, negScore: Math.round(neg * 10) / 10,
		confidence, band: band.key, bandCn: band.cn,
		leaning: band.proj,   // 三值投影(旧消费点单调兼容)
		guards,
		summary: `${band.cn}（置信度 ${confidence}/100）` + (band.proj === 'yes' ? '——仍请结合实际，不下命定结论' : (band.proj === 'no' ? '——建议另择时再问' : ' → 建议补充信息或另择时')),
		profile: 'v2',
	};
}

// 双轨入口:verdictProfile 'legacy'(缺省)|'v2'。
export function buildVerdictScored(ctx, opts){
	const profile = (opts && opts.verdictProfile) || 'legacy';
	if(profile === 'v2'){
		return aggregateV2(collectTestimoniesV2(ctx), ctx);
	}
	return buildVerdictLegacy(ctx);
}

export default buildVerdictScored;
