// divination/horary/horaryEngine.js
// 卜卦编排器：chart Result + 问题类别 → 完整结构化判断。
// 跑 根本性 → 征象星 → 完成法 → 月亮 → 单星状态 → Query I–VI → 应期方位 → 加权裁决。
import { buildFacts } from '../engine/chartFacts.js';
import { radicality, hourAgreementTest } from '../engine/radicality.js';
import { analyzePerfection, completionThirds } from '../engine/perfection.js';
import { moonReport } from '../engine/moon.js';
import { planetCondition } from '../engine/conditions.js';
import { applyingAspects, separatingAspects, aspectsOf, aspectBetween } from '../engine/aspectsEngine.js';
import { almutenAt } from '../engine/almuten.js';
import { assignSignificators, moonPromotionCheck } from './significators.js';
import { timingFrom, directionFrom } from './timing.js';
import { describePerson, THIEF_BY_PLANET, DISEASE_BY_ELEMENT, DEATH_MODE } from './describe.js';
import { runTheft } from './theftModule.js';
import { buildTopicDeepening } from './topicModule.js';
import { PLANETS } from '../data/planets.js';
import { SIGNS, signOfLon } from '../data/signs.js';
import { FIXED_STARS, starLonAt, starOrbFor } from '../data/fixedStars.js';
import { lotDispositor, LOTS_SETS, computeLotsSet } from '../data/lots.js';
import { angularDist, norm360 } from '../engine/utils.js';
import { besiegementOf, backendStarsOf } from '../engine/resultShapes.js';
import { buildVerdictScored } from './verdictScoring.js';
import { immediateAspOf } from '../engine/resultShapes.js';
import { keyOfChartId } from '../engine/utils.js';
import { signedDelta } from '../engine/utils.js';
import { receptionsOf } from '../engine/reception.js';

function cn(k){ return (PLANETS[k] || {}).cn || k; }
function signCn(s){ return (SIGNS[s] || {}).cn || s; }

// 阿拉伯点（福点/精神点）：按流派福点昼夜反转口径计算 + 落座 + 定位星（失物/财物关键征象）。
//  pofReversal=true(严谨/希腊化/中世纪)：夜盘反转公式；false(经典/现代)：恒用日盘式 ASC+Moon−Sun。
function buildLots(facts, opts){
	opts = opts || {};
	const asc = facts.meta.ascLon;
	const sun = facts.planets.sun ? facts.planets.sun.lon : null;
	const moon = facts.planets.moon ? facts.planets.moon.lon : null;
	if(asc == null || sun == null || moon == null){ return null; }
	const isDay = !!facts.meta.isDiurnal;
	const reverse = !!opts.pofReversal;
	const useNight = reverse && !isDay;   // 仅「反转档 + 夜盘」才翻公式
	const fortune = norm360(useNight ? (asc + sun - moon) : (asc + moon - sun));
	const spirit = norm360(useNight ? (asc + moon - sun) : (asc + sun - moon));
	const pack = (lon) => {
		const sign = signOfLon(lon);
		const disp = lotDispositor(lon);
		return { lon, sign, signCn: signCn(sign), signlon: ((lon % 30) + 30) % 30, disp, dispCn: disp ? cn(disp) : null };
	};
	const out = {
		reversalApplied: useNight,
		convention: reverse ? (isDay ? '反转档·日盘（同日式）' : '反转档·夜盘（翻公式）') : '不反转档（恒日式）',
		fortune: pack(fortune),
		spirit: pack(spirit),
	};
	// lots_set='core15'：高可靠核心集全量（福/精神按上方口径先算好注入,其余按各点 reverseBySect）。
	// 默认 'minimal' 不扩（零回归）。
	if(opts.lotsSet && opts.lotsSet !== 'minimal' && LOTS_SETS[opts.lotsSet]){
		const workLons = { ...facts.lons, fortune, spirit };
		out.extended = computeLotsSet(workLons, isDay, LOTS_SETS[opts.lotsSet])
			.map((it) => ({ ...it, ...pack(it.lon), id: it.id, cn: it.cn, use: it.use, house: it.house }));
	}
	return out;
}

// 取本盘公历年（恒星岁差修正）：读 /chart 回传 params.birth/date；缺则用中性年。
function chartYear(facts){
	try{
		const p = facts && facts.result && facts.result.params;
		const ds = p && (p.birth || p.date);
		if(ds){ const m = String(ds).match(/(-?\d{3,4})/); if(m){ return Number(m[1]); } }
	}catch(e){ /* noop */ }
	return 2000;
}

// D2 恒星会合：征象星/命度/天顶 会合精选恒星（容许度按流派取，默认 1°）。
function buildFixedStars(facts, sigs, opts){
	// 轨档：'school'(默认,平轨=既有行为字节不变) / 'byMagnitude'(Robson 按星等;王者封顶 5°)。
	const year = chartYear(facts);
	const out = [];
	const points = {};
	if(facts.meta.ascLon != null){ points['命度'] = facts.meta.ascLon; }
	if(facts.meta.mcLon != null){ points['天顶'] = facts.meta.mcLon; }
	[['命主', sigs.querentKey], ['事项', sigs.quesitedKey], ['月亮', 'moon']].forEach((pair) => {
		const label = pair[0]; const k = pair[1];
		if(k && facts.planets[k] && facts.planets[k].lon != null){ points[`${label}·${cn(k)}`] = facts.planets[k].lon; }
	});
	Object.keys(points).forEach((label) => {
		const lon = points[label];
		FIXED_STARS.forEach((st) => {
			const stLon = starLonAt(st.lon_1995, year);
			if(angularDist(lon, stLon) <= starOrbFor(st, opts)){
				// starLon/pointLon 为纯增字段(中栏叠层轮缘定位用);快照/右栏按显式字段格式化,零影响。
				out.push({ point: label, star: st.name_cn, meaning: st.meaning, nature: (st.election && st.election.avoid) ? 'caution' : 'boost', royal: !!st.isRoyal, starLon: stLon, pointLon: lon });
			}
		});
	});
	return out;
}

// D5 行星时佐证：时主星与命主/事项星一致 → 时辰与盘相合（根本性佐证）。
// opts.hourAgreementVariant:'either'(两口径任一,缺省)|'lilly'(行星统辖版:只认时主=命主星)|
// 'bonatti'(落座元素版)。不传=既有行为字节不变。
// [H3 单源化] 学理判定唯一实现=radicality.hourAgreementTest;本函数降级为其上的
// 「徵象星匹配」视图(时主=命主/事项星的直接注记)。旧版 bonatti 分支自算且参照物取
// **上升座**元素,与权威实现的**命主星落座**元素(文献口径)不同,边缘盘两处结论相反
// ——bonatti 支改转发权威实现(medieval 档输出小幅重锚);either/lilly 支不涉学理自算,字节不变。
function buildHourAgreement(facts, sigs, opts){
	opts = opts || {};
	const v = opts.hourAgreementVariant || 'either';
	const hr = facts.meta.hourRuler;
	if(!hr){ return null; }
	if(hr === sigs.querentKey){ return { agree: true, text: `时主星 ${cn(hr)} ＝ 命主：时辰与盘相合（根本性佐证）。` }; }
	if(v !== 'lilly' && hr === sigs.quesitedKey){ return { agree: true, text: `时主星 ${cn(hr)} ＝ 事项守护星：时辰与所问相合（佐证）。` }; }
	if(v === 'bonatti'){
		const core = hourAgreementTest(facts, opts);
		const hit = core && core.hits && core.hits.find((h) => h.key === 'triplicity_bonatti');
		if(hit){
			return { agree: true, text: `时主星 ${cn(hr)} 落座与命主星落座同元素（落座元素版口径）：时辰与盘相合。`, via: hit.key };
		}
	}
	if(v === 'lilly' && hr === sigs.quesitedKey){ return { agree: false, text: `时主星 ${cn(hr)} ＝ 事项守护星——行星统辖版口径只认命主一致，作一般参考。` }; }
	return { agree: false, text: `时主星 ${cn(hr)} 与命主/事项星不一致，作一般参考。` };
}

export const ASPECT_CN = { 0: '合相', 60: '六合', 90: '四分(刑)', 120: '三合', 180: '对分(冲)' };
const ASPECT_NATURE = { 0: 'neutral', 60: 'positive', 120: 'positive', 90: 'negative', 180: 'negative' };
const ALL_KEYS = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
const OUTER_KEYS = ['uranus', 'neptune', 'pluto'];
// [WP-F] includeOuter 真接线:全相位表/月亮叙事的星集门(默认 false=七政,现状零回归;
// 现代档 includeOuter:true → 三王星入表)。注:perfection 的干扰/传递/汇集候选历史即全星集,不动。
function judgeKeysFor(includeOuter){
	return includeOuter ? ALL_KEYS.concat(OUTER_KEYS) : ALL_KEYS;
}
// 古典卜卦只取托勒密五相位（合/六合/四分/三合/对分），不取 45°/30° 等次相位。
const PTOLEMAIC = [0, 60, 90, 120, 180];

// 全盘相位一览（判读星集两两，去重）——把所有可能用到的征象摆给用户自行判断
function buildAllAspects(facts, includeOuter){
	const KS = judgeKeysFor(includeOuter);
	const seen = {}; const out = [];
	KS.forEach((a) => {
		if(!facts.planets[a]) return;
		aspectsOf(facts, a).forEach((x) => {
			const b = x.other;
			if(KS.indexOf(b) < 0) return;
			if(PTOLEMAIC.indexOf(x.angle) < 0) return;
			const k = [a, b].sort().join('-') + ':' + x.angle;
			if(seen[k]) return; seen[k] = 1;
			out.push({ a, b, angle: x.angle, applying: !!x.applying, separating: !!x.separating, exact: !!x.exact, orb: x.orb, nature: ASPECT_NATURE[x.angle] || 'neutral' });
		});
	});
	out.sort((m, n) => ((m.exact ? 0 : 1) - (n.exact ? 0 : 1)) || (m.orb - n.orb));
	return out;
}

// 月亮的故事：刚离开（过去）→ 接下来要会（未来），卜卦核心线索
function buildMoonStory(facts, includeOuter){
	const KS = judgeKeysFor(includeOuter);
	const inSet = (x) => KS.indexOf(x.other) >= 0 && PTOLEMAIC.indexOf(x.angle) >= 0;
	const out = {
		separating: separatingAspects(facts, 'moon').filter(inSet).sort((a, b) => a.orb - b.orb),
		applying: applyingAspects(facts, 'moon').filter(inSet).sort((a, b) => a.orb - b.orb),
	};
	// [H4a 金矿] 后端权威源附加行:aspects.immediateAsp 是后端按 orb 排好序的每星紧密相位表
	// (末相位/下一相位的权威判据;前端 normalAsp 自滤自排是近似)。纯增字段不替换上两列——
	// UI/快照把它作「实测」对照行,两源分歧时以此为准。
	out.immediate = immediateAspOf(facts.result, 'Moon')
		.map((x) => ({ other: keyOfChartId(x.id), angle: x.asp, orb: x.orb }))
		.filter((x) => KS.indexOf(x.other) >= 0 && PTOLEMAIC.indexOf(x.angle) >= 0);
	return out;
}

// [H4a] 月亮出本座前的最后一个精确相位=「事之终局」(Query VI 口径的另一半;此前只有
// 4 宫主一半)。线性外推:月亮以当前速度在本座剩余弧内,与各星最后走到精确的托勒密相位。
function moonFinalAspect(facts, includeOuter){
	const m = facts.planets.moon;
	if(!m || m.signlon === undefined || !m.speed || m.lon === undefined){ return null; }
	const KS = judgeKeysFor(includeOuter).filter((k) => k !== 'moon');
	let last = null;
	KS.forEach((k) => {
		const p = facts.planets[k];
		if(!p || p.lon === undefined){ return; }
		const rel = (m.speed || 0) - (p.speed || 0);
		if(Math.abs(rel) < 1e-6){ return; }
		PTOLEMAIC.forEach((A) => {
			const targets = A === 0 ? [0] : (A === 180 ? [180, -180] : [A, -A]);
			targets.forEach((T) => {
				for(let cyc = -1; cyc <= 1; cyc++){
					const t = (T - signedDelta(p.lon, m.lon) + 360 * cyc) / rel;
					if(t > 1e-6){
						const mEnd = m.signlon + m.speed * t;
						if(mEnd >= 0 && mEnd < 30){
							if(!last || t > last.tDays){ last = { other: k, angle: A, tDays: Math.round(t * 10) / 10 }; }
						}
					}
				}
			});
		});
	});
	return last;
}

function buildDescribe(facts, querentKey, quesitedKey, category, sigs){
	const out = [];
	if(querentKey && facts.planets[querentKey]){
		out.push({ role: '问卜者（命主）', ...describePerson(querentKey, facts.planets[querentKey].sign) });
	}
	if(quesitedKey && quesitedKey !== querentKey && facts.planets[quesitedKey]){
		out.push({ role: sigs.quesitedLabel || '对象', ...describePerson(quesitedKey, facts.planets[quesitedKey].sign) });
	}
	if(category === 'theft' && quesitedKey){
		out.push({ role: '小偷（7宫主/征象星）', title: `小偷（${cn(quesitedKey)}）`, body: THIEF_BY_PLANET[quesitedKey] || '（该行星无对应外貌条目）', temper: null });
	}
	if(category === 'health' && facts.planets.moon){
		const el = SIGNS[facts.planets.moon.sign] ? SIGNS[facts.planets.moon.sign].element : null;
		if(el) out.push({ role: '病因（月亮所落元素）', title: '疾病性质', body: DISEASE_BY_ELEMENT[el], temper: null });
	}
	if(category === 'death' && quesitedKey){
		out.push({ role: '死亡方式（8宫主）', title: `死亡方式（${cn(quesitedKey)}）`, body: DEATH_MODE[quesitedKey] || '—', temper: null });
	}
	return out;
}

function buildQueries(facts, ctx){
	const { quesitedKey, perf, moon, conds } = ctx;
	const q = {};
	// Query I 能否成事
	if(perf && perf.perfects && !perf.destroyed) q.canHappen = { verdict: 'yes', text: `能成（${methodCn(perf.method)}${perf.translator ? '，中间人=' + cn(perf.translator) : ''}${perf.collector ? '，汇集于=' + cn(perf.collector) : ''}）。` };
	else if(perf && perf.destroyed) q.canHappen = { verdict: 'no', text: `难成（${destrCn(perf.destruction)}）。` };
	else q.canHappen = { verdict: 'even', text: '未见明确完成法，多半不成或需另择时。' };
	// Query II 事情好坏
	const qc = quesitedKey && conds[quesitedKey];
	q.goodEvil = { verdict: qc && qc.score > 0 ? 'good' : (qc && qc.score < 0 ? 'bad' : 'neutral'), text: qc ? `事项守护星 ${cn(quesitedKey)} 状态分 ${qc.score}` : '事项守护星未定。' };
	// Query III 消息真假（月空按流派解算值，见 moonReport）
	const m = facts.planets.moon;
	const rVoc = ctx.moon ? !!ctx.moon.voc : (m && m.isVOC);
	const moonAngular = m && m.angularity === 'angular';
	q.reportTrue = { verdict: (moonAngular && !rVoc) ? 'true' : (m && (rVoc || m.combustion === 'combust') ? 'false' : 'uncertain'), text: m ? (rVoc ? '月空相 → 消息恐假/为时过早。' : (moonAngular ? '月在角宫且非空相 → 偏真。' : '月非角宫，参考其他。')) : '' };
	// Query IV 何处/方向
	q.where = quesitedKey ? directionFrom(facts, quesitedKey) : null;
	// Query V 何时（应期指针;与「时空」Tab 同源）
	q.when = ctx.timing ? { verdict: 'info', text: ctx.timing.text } : { verdict: 'uncertain', text: '无准确入相位可折算应期。' };
	// Query VI 结局如何（事情之终局:4宫主状态 + 月亮末相位口径）
	// [H4a] 「月亮出本座前最后相位」从「并参」空话变真计算(moonFinal 线性外推);无解=本座内再无精确相位。
	const l4 = facts.houses[4] && facts.houses[4].ruler;
	const c4 = l4 && conds && conds[l4] ? conds[l4] : null;
	const mf = ctx.moonFinal;
	const mfText = mf
		? `月亮本座终局相位＝与 ${cn(mf.other)} 成${ASPECT_CN[mf.angle] || mf.angle + '°'}（约 ${mf.tDays} 天后精确，${mf.angle === 90 || mf.angle === 180 ? '偏凶' : '偏吉'}收尾）`
		: '月亮本座内已无将成的精确相位（终局随现势）';
	q.outcome = {
		verdict: c4 ? (c4.score > 0 ? 'good' : (c4.score < 0 ? 'bad' : 'neutral')) : 'uncertain',
		moonFinal: mf || null,
		text: l4 ? `事之结局看 4宫主 ${cn(l4)}${c4 ? `（状态分 ${c4.score}）` : ''}；${mfText}。` : `4宫主未定；${mfText}。`,
	};
	return q;
}

function methodCn(m){ return ({ application: '入相位', translation: '光线传递', collection: '光线汇集', position: '落位', antiscion: '映点', reception: '互容' })[m] || m || ''; }
function destrCn(d){ return ({ no_reception_hard: '无接纳的刑/冲', combustion: '燃烧', separation: '出相位(事已过)', prohibition: '阻碍', frustration: '挫败', refranation: '撤回(临成自退)', abscission: '光线切断' })[d] || d || '受阻'; }

// [H7] buildVerdict 已搬家至 verdictScoring.js(legacy 路径逐字节保留+v2 证词池双轨)。

// [H3] runHorary memo:同 result 引用+同 category+同 opts(按值) → 复用上次产出。
// 页面 render/中栏 overlay/AI 快照曾各自全链重跑 2-3 次;runHorary 纯函数,重复纯浪费。
// WeakMap 按 result 引用分槽:页面+overlay 共享同一 result 引用=命中;AI 自 fetch 的新对象
// 各得其槽(免单槽 thrash);盘释放时槽随 GC 走。副键=category+全量 opts 排序序列化——
// 三调用点每次新建 opts 对象,必须按值比对;全键序列化宁多算不漏算(undefined 键剔除)。
// ⚠️ 返回值因此是共享对象:消费方绝不可原地改写(deep-freeze 测试看守)。
let _horaryMemo = new WeakMap();
export function __resetHoraryMemoForTest(){ _horaryMemo = new WeakMap(); }
function horaryMemoKey(category, opts){
	const o = opts || {};
	const ks = Object.keys(o).sort();
	const parts = [];
	for(let i = 0; i < ks.length; i++){
		if(o[ks[i]] === undefined){ continue; }
		let sv;
		try{ sv = JSON.stringify(o[ks[i]]); }catch(e){ sv = String(o[ks[i]]); }
		parts.push(ks[i] + ':' + sv);
	}
	return String(category || 'general') + '|' + parts.join(',');
}
export function runHorary(result, category, opts){
	if(result && typeof result === 'object'){
		const key = horaryMemoKey(category, opts);
		const slot = _horaryMemo.get(result);
		if(slot && slot.key === key){ return slot.value; }
		const value = computeHorary(result, category, opts);
		_horaryMemo.set(result, { key, value });
		return value;
	}
	return computeHorary(result, category, opts);
}

function computeHorary(result, category, opts){
	opts = opts || {};
	const facts = buildFacts(result, opts);
	if(!facts) return null;
	const sigs = assignSignificators(facts, category || 'general', opts);
	const querentKey = sigs.querentKey;
	let quesitedKey = sigs.quesitedKey;
	if(!quesitedKey){
		// [H4a bug 修] 兜底事项主=月亮下一入相星:旧码取后端表原序首项——normalAsp 的
		// Applicative 数组不保证 orb 升序,「下一个」可能拿到较远的星。补 orb 升序。
		const app = applyingAspects(facts, 'moon')
			.filter((a) => ['sun', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'].indexOf(a.other) >= 0)
			.sort((a, b) => a.orb - b.orb);
		quesitedKey = app.length ? app[0].other : null;
	}
	const moon = moonReport(facts, opts);
	// [H5] almutenOpts 前移:同主一星法E(almuten 拆分)须在完成法之前改写事项象征星。
	const almutenOpts = {
		isDiurnal: facts.meta.isDiurnal,
		termsVariant: opts.termsVariant !== undefined ? opts.termsVariant : 'ptolemaic',
		tripSystem: opts.tripSystem, geminiEmended: !!opts.geminiEmended, weights: opts.almutenWeights,
	};
	// [H5] 同主一星真执行:法E=以事项宫头 almuten 拆出另一象征星(此前仅注记「见 almuten 行」半死);
	// 法C=真查共用星被谁容纳(此前仅口播判据不查)。缺省(未选法)零触发=现状。
	if(sigs.sharedRuler && sigs.sharedRuler.method === 'E'
		&& sigs.quesitedHouse && facts.houses[sigs.quesitedHouse] && facts.houses[sigs.quesitedHouse].lon != null){
		const am = almutenAt(facts.houses[sigs.quesitedHouse].lon, almutenOpts);
		const w = am && am.winners && am.winners.find((x) => x !== querentKey && facts.planets[x]);
		if(w){
			quesitedKey = w;
			sigs.sharedRuler.almutenSplit = w;
			sigs.sharedRuler.note = `同主一星（法E·已拆分）：事项改由宫头 almuten ${cn(w)} 代表，问者仍由共用星代表。`;
		}
	}
	if(sigs.sharedRuler && sigs.sharedRuler.method === 'C'){
		const recs = receptionsOf(facts, sigs.sharedRuler.planet).filter((r) => r.beneficiary === sigs.sharedRuler.planet);
		sigs.sharedRuler.received = recs.length > 0;
		sigs.sharedRuler.receivedBy = recs.map((r) => r.supplier);
		sigs.sharedRuler.note = recs.length
			? `同主一星（法C·已查）：共用星被 ${recs.map((r) => cn(r.supplier)).join('、')} 容纳 → 偏成（不受克则成）。`
			: '同主一星（法C·已查）：共用星未被任何星容纳 → 偏不成。';
	}
	const rad = radicality(facts, { ...opts, category: category || 'general', moonVoc: moon.voc, sigs: { querentKey, quesitedKey, quesitedHouse: sigs.quesitedHouse } });
	let perf = (querentKey && quesitedKey) ? analyzePerfection(facts, querentKey, quesitedKey, { quesitedHouse: sigs.quesitedHouse, ...opts }) : null;
	// [H5] 月亮升格前移(apply 档要在应期之前改写完成法主径;'note' 缺省=纯注记零回归)。
	// [复审P1] 升格判据「命主与事项主无相位」与完成法同口径:非托勒密角(45° 等)不算有相位。
	let l1qAspect = (querentKey && quesitedKey) ? aspectBetween(facts, querentKey, quesitedKey) : null;
	if(l1qAspect && PTOLEMAIC.indexOf(l1qAspect.angle) < 0){ l1qAspect = null; }
	const moonPromotion = moonPromotionCheck(facts, querentKey, quesitedKey, l1qAspect !== null);
	const moonPerfection = (querentKey && quesitedKey && querentKey !== 'moon' && quesitedKey !== 'moon')
		? analyzePerfection(facts, 'moon', quesitedKey, { quesitedHouse: sigs.quesitedHouse, ...opts })
		: null;
	let perfQuerent = querentKey;   // 应期 otherKey 推导的「问方星」——升格采月径后=moon
	if(opts.moonPromotion === 'apply' && moonPromotion.promote
		&& perf && !perf.perfects && !perf.destroyed
		&& moonPerfection && moonPerfection.perfects && !moonPerfection.destroyed){
		perf = {
			...moonPerfection, viaMoonPromotion: true,
			detail: [`月亮升格生效（${moonPromotion.reasons.join('、')}）：主径无完成，以月亮为主象征续判——`].concat(moonPerfection.detail),
		};
		perfQuerent = 'moon';
	}
	const thirds = completionThirds(facts, [querentKey, 'moon', quesitedKey]);
	const conds = {};
	[querentKey, quesitedKey, sigs.natural, 'moon'].filter(Boolean).forEach((k) => { if(!conds[k]) conds[k] = planetCondition(k, facts, opts); });
	// [H2 应期修复] 按完成法取真实「成事腿」:入相位完成用两征象星腿(现状);传递完成用
	// T→target 腿、汇集用双腿较大 orb(perfection.timingLeg)——旧码这两类完成应期恒缺,
	// 或(残留出相位时)误拿出相 orb 折算。落位/映点/互容完成无入相腿=不折算(Query V 如实说)。
	let timing = null;
	if(perf && perf.perfects){
		if(perf.aspect && perf.method === 'application'){
			timing = timingFrom(facts, perf.aspect.from || perfQuerent, perf.aspect.orb, {
				...opts,
				appliedKey: perf.aspect.to || quesitedKey,
				otherKey: (perf.aspect.from === perfQuerent ? quesitedKey : perfQuerent),
			});
		}else if(perf.timingLeg){
			timing = timingFrom(facts, perf.timingLeg.mover, perf.timingLeg.orb, {
				...opts, appliedKey: perf.timingLeg.target, otherKey: perf.timingLeg.target,
			});
			if(timing){
				timing.leg = { method: perf.method, mover: perf.timingLeg.mover, target: perf.timingLeg.target };
				timing.text = `${timing.text}（按${perf.method === 'translation' ? '传递腿：' + cn(perf.timingLeg.mover) + '→' + cn(perf.timingLeg.target) : '汇集较慢腿：' + cn(perf.timingLeg.mover) + '→' + cn(perf.timingLeg.target)}折算）`;
			}
		}
	}
	const moonFinal = moonFinalAspect(facts, !!opts.includeOuter);
	const queries = buildQueries(facts, { quesitedKey, perf, moon, conds, timing, moonFinal });
	// [H7] v2 证词池的扩展源(恒星/时主/almuten/围攻)前移到裁决前;legacy 档不读它们=字节不变。
	const fixedStarsV = buildFixedStars(facts, { querentKey, quesitedKey }, opts);
	const hourAgreementV = buildHourAgreement(facts, { querentKey, quesitedKey }, opts);
	const besiegementV = besiegementOf(result);
	const almuten = {
		asc: facts.meta.ascLon != null ? almutenAt(facts.meta.ascLon, almutenOpts) : null,
		quesitedCusp: (sigs.quesitedHouse && facts.houses[sigs.quesitedHouse] && facts.houses[sigs.quesitedHouse].lon != null)
			? almutenAt(facts.houses[sigs.quesitedHouse].lon, almutenOpts) : null,
	};
	const verdict = buildVerdictScored({
		perf, moon, conds, thirds, querentKey, quesitedKey,
		facts, hourAgreement: hourAgreementV, fixedStars: fixedStarsV,
		almuten, moonPerfection, besiegement: besiegementV, sigs,
	}, opts);
	// 考量14「吉凶势均力敌」：裁决后回填（|pos−neg|<2 且未有明确完成/破坏 → 命中）。
	if(rad && rad.considerations && rad.considerations.items){
		const even = rad.considerations.items.find((it) => it.key === 'balance_even');
		if(even){
			even.hit = Math.abs(verdict.posScore - verdict.negScore) < 2 && !(perf && (perf.perfects || perf.destroyed));
		}
	}
	const describe = buildDescribe(facts, querentKey, quesitedKey, category || 'general', sigs);
	const theft = (category === 'theft') ? runTheft(facts) : null;
	return {
		facts, category: category || 'general', school: opts.school || 'classical',
		// sharedRuler 必须透传:significators.js 在命主=事主同星时写出五法(A-E)裁决对象,
		// 此处重组曾把它丢弃 → HoraryJudgment 的同主一星卡片恒不显示(2026-08 死开关审计抓出)。
		significators: {
			querentKey, quesitedKey, natural: sigs.natural, moon: 'moon', quesitedHouse: sigs.quesitedHouse, quesitedLabel: sigs.quesitedLabel, sharedRuler: sigs.sharedRuler || null,
			// [H5] 转宫人称档/宫内 co-significator/自然征象升格——纯增透传(UI 表+H7 天平消费)。
			turned: sigs.turned || null, coSignificators: sigs.coSignificators || null,
			naturalPromoted: !!sigs.naturalPromoted, naturalPromotionReason: sigs.naturalPromotionReason || null,
		},
		radicality: rad, moon, perfection: perf, thirds, conditions: conds, queries, timing, verdict, describe, theft,
		almuten, moonPromotion, moonPerfection,
		allAspects: buildAllAspects(facts, !!opts.includeOuter), moonStory: buildMoonStory(facts, !!opts.includeOuter),
		hourRuler: facts.meta.hourRuler,
		fixedStars: fixedStarsV,
		hourAgreement: hourAgreementV,
		lots: buildLots(facts, opts),
		tripSystem: opts.tripSystem || 'ptolemaic',
		topic: buildTopicDeepening(facts, category || 'general', opts),
		// [H4a 金矿纯增] 后端围攻十六式详断/后端恒星命中表/月亮终局——读契约层,消费在快照与 UI 卡。
		besiegement: besiegementV,
		backendStars: backendStarsOf(result),
		moonFinal,
	};
}

export default runHorary;
