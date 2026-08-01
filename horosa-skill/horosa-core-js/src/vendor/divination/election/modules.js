// divination/election/modules.js
// 21 个分析模块（择日清单 §3 + 西方深化 WP + R2 流派口径/阿拉伯点/吉化凶化），按优先级=UI 顺序。
// 每模块产 section{key,title,verdict,score,findings,detail}。
// 流派口径 eff 经 electionEngine 挂到 facts.eff 单点注入（缺省 null = 内建默认,行为字节不变）。
import { planetCondition } from '../engine/conditions.js';
import { moonReport } from '../engine/moon.js';
import { aspectsOf } from '../engine/aspectsEngine.js';
import { receptionsOf } from '../engine/reception.js';
import { SIGNS } from '../data/signs.js';
import { PLANETS } from '../data/planets.js';
import { FIXED_STARS, starLonAt, starOrbFor } from '../data/fixedStars.js';
import { angularDist, norm360 } from '../engine/utils.js';
import { PLANETARY_HOURS, DAY_RULERS } from '../data/planetaryHours.js';
import { mansionOf, MANSION_ELECTION_SETS, TOPIC_MANSION_MAP } from '../data/lunarMansions.js';
import { paransAt } from '../engine/paransLocal.js';
import { radicality, viaCombustaRange } from '../engine/radicality.js';
import { termRulerAt, faceAt, triplicityRulers } from '../data/dignities.js';
import { termRulerForVariant, almutenFiguris } from '../engine/almuten.js';
import { filterAspects } from './orbPolicy.js';
import { bonificationReport } from './dignityReport.js';

function cn(k){ return (PLANETS[k] || {}).cn || k; }
// 流派口径读取（facts.eff 由 electionEngine 注入;直接调 runModules 的旧路径无此键 → 全默认）。
function effOf(facts){ return (facts && facts.eff) || null; }
// 按口径过滤后的相位组（'modern'/缺省 = 后端表原样,零回归）。
function aspOf(facts, key){
	const eff = effOf(facts);
	return filterAspects(aspectsOf(facts, key), key, facts, eff && eff.orbProfile);
}
// 空亡/月亮类口径 opts（全默认时与不传 opts 字节等价）。
function vocOptsOf(facts){
	const eff = effOf(facts);
	if(!eff) return undefined;
	return {
		vocMode: eff.vocMode, vocIncludeOuter: !!eff.vocIncludeOuter,
		vocMitigateSigns: !!eff.vocMitigateSigns, viaCombustaVariant: eff.viaCombustaVariant,
	};
}
// 判读层界主（随 eff.termsVariant;0=埃及=既有默认）。
function termRulerEff(facts, lon){
	const eff = effOf(facts);
	const v = eff ? eff.termsVariant : 0;
	if(!v) return termRulerAt(lon);
	return termRulerForVariant(lon, { termsVariant: v, isDiurnal: !!(facts.meta && facts.meta.isDiurnal) });
}
function clamp(x){ return Math.max(0, Math.min(100, Math.round(x))); }
function verdictOf(s){ return s >= 70 ? 'good' : (s >= 52 ? 'neutral' : (s >= 38 ? 'caution' : 'bad')); }
function scoreFromFindings(findings, baseSeed){
	let s = baseSeed === undefined ? 60 : baseSeed;
	findings.forEach((f) => { s += (f.polarity === 'positive' ? 1 : (f.polarity === 'negative' ? -1 : 0)) * (f.weight || 1) * 6; });
	return clamp(s);
}
function lord1Of(facts){ const sg = facts.meta.ascSign; return SIGNS[sg] ? SIGNS[sg].domicile : null; }
const BENEFICS = ['jupiter', 'venus'];
const MALEFICS = ['mars', 'saturn'];

function mkFinding(polarity, message, weight){ return { polarity, message, text_zh: message, weight: weight || 1 }; }

function normLon(x){ return ((Number(x) % 360) + 360) % 360; }
// 取本盘公历年（用于恒星岁差修正）：优先读 /chart 回传的 params.birth/date；缺则用中性年（岁差差异 <1° 可忽略）。
function getChartYear(facts){
	try{
		const p = facts && facts.result && facts.result.params;
		const ds = p && (p.birth || p.date);
		if(ds){ const m = String(ds).match(/(-?\d{3,4})/); if(m){ return Number(m[1]); } }
	}catch(e){ /* noop */ }
	return 2000;
}
// 两点的短弧中点（落入两点夹角较小一侧）。
function shortMidpoint(a, b){
	const m1 = normLon((Number(a) + Number(b)) / 2);
	const m2 = normLon(m1 + 180);
	return angularDist(m1, a) <= 90 ? m1 : m2;
}

function moonModule(facts){
	const r = moonReport(facts, vocOptsOf(facts));
	const findings = r.findings.map((f) => ({ ...f, message: f.text_zh }));
	const score = scoreFromFindings(findings, 64);
	// 口径注记:仅当空亡/火道口径偏离内建默认时追加(默认档 detail 与既往逐字一致)。
	const eff = effOf(facts);
	let calibreNote = '';
	if(eff && (eff.vocMode !== 'classic' || eff.viaCombustaVariant !== 'standard')){
		const vc = viaCombustaRange(eff.viaCombustaVariant);
		calibreNote = `（本档口径:空亡=${eff.vocMode}·火道 ${vc[0]}°–${vc[1]}°）`;
	}
	return { key: 'moon', title: '月亮（第一考量）', verdict: verdictOf(score), score, findings, detail_md: `月落 ${SIGNS[facts.planets.moon.sign] ? SIGNS[facts.planets.moon.sign].cn : ''}，${r.phase === 'waxing' ? '盈' : '亏'}。${calibreNote}` };
}

function ascRulerModule(facts){
	const l = lord1Of(facts);
	const findings = [];
	if(l && facts.planets[l]){
		const p = facts.planets[l];
		if(p.retro) findings.push(mkFinding('negative', `命主星 ${cn(l)} 逆行（命主不可逆行）`, 3));
		if(p.dignityScore >= 4) findings.push(mkFinding('positive', `命主星 ${cn(l)} 有力（+${p.dignityScore}）`, 2));
		else if(p.dignityScore <= -4) findings.push(mkFinding('negative', `命主星 ${cn(l)} 落陷/弱`, 2));
		if(p.angularity === 'angular' || p.angularity === 'succedent') findings.push(mkFinding('positive', `命主星入${p.angularity === 'angular' ? '角' : '续'}宫`, 1));
		else if([3, 6, 9, 12].indexOf(p.house) >= 0) findings.push(mkFinding('negative', `命主星入弱宫(${p.house})`, 1));
	}
	const score = scoreFromFindings(findings, 60);
	return { key: 'asc_ruler', title: '命主星（第二考量）', verdict: verdictOf(score), score, findings, detail_md: l ? `命主星 = ${cn(l)}` : '命主星未定' };
}

function ascendantModule(facts, topic){
	const findings = [];
	const sg = facts.meta.ascSign;
	const mod = SIGNS[sg] ? SIGNS[sg].modality : null;
	const pref = (topic.preferred_asc_modality) || [];
	if(mod && pref.length){
		if(pref.indexOf(mod) >= 0) findings.push(mkFinding('positive', `命宫三方四正(${mod})匹配本用事偏好`, 2));
		else if(mod === 'mutable' && (topic.topic_id === 'marriage' || topic.topic_id === 'business')) findings.push(mkFinding('negative', '变动宫坐命（婚姻/事业忌）', 2));
	}
	const ad = facts.meta.ascDegree;
	if(ad !== null && ad !== undefined){
		if(ad > 28) findings.push(mkFinding('negative', `命度 ${ad.toFixed(1)}°>28°（变动气质）`, 1));
		else if(ad >= 1 && ad <= 5) findings.push(mkFinding('positive', `命度 ${ad.toFixed(1)}°（1–5°，固定性强）`, 1));
	}
	const score = scoreFromFindings(findings, 60);
	return { key: 'ascendant', title: '命度/上升（第三考量）', verdict: verdictOf(score), score, findings, detail_md: `上升 ${SIGNS[sg] ? SIGNS[sg].cn : ''} ${ad !== null ? ad.toFixed(1) + '°' : ''}` };
}

function sunModule(facts){
	const findings = [];
	const s = facts.planets.sun;
	if(s){
		if([12].indexOf(s.house) >= 0) findings.push(mkFinding('negative', '太阳落 12 宫（出版/魅力类用事尤忌）', 1));
		const asp = aspOf(facts, 'sun').filter((a) => [60, 120].indexOf(a.angle) >= 0 && BENEFICS.indexOf(a.other) >= 0);
		if(asp.length) findings.push(mkFinding('positive', `太阳与吉星${asp[0].angle}°`, 1));
	}
	const score = scoreFromFindings(findings, 60);
	return { key: 'sun', title: '太阳', verdict: verdictOf(score), score, findings, detail_md: '' };
}

function anglesModule(facts){
	const findings = [];
	[1, 4, 7, 10].forEach(() => {});
	const eff = effOf(facts);
	const sevenOnly = !!(eff && eff.bodySet === 'classical7');
	Object.keys(facts.planets).forEach((k) => {
		const p = facts.planets[k];
		if(p.angularity !== 'angular') return;
		if(BENEFICS.indexOf(k) >= 0 && p.dignityScore >= 0) findings.push(mkFinding('positive', `吉星 ${cn(k)} 入角宫`, 2));
		if(MALEFICS.indexOf(k) >= 0 && (p.dignityScore <= 0 || p.retro)) findings.push(mkFinding('negative', `凶星 ${cn(k)} 受剋入角宫`, 2));
		// 七曜档(classical7)不出三王星条目(红线层仍按流派 annotate 降级另行注记)。
		if(!sevenOnly && k === 'uranus' && (p.house === 1 || p.house === 7)) findings.push(mkFinding('negative', '天王星在 1/7 宫（变动/分离）', 2));
	});
	const score = scoreFromFindings(findings, 60);
	return { key: 'angles', title: '角宫吉凶分布（纳吉排凶）', verdict: verdictOf(score), score, findings, detail_md: '' };
}

function maleficHandlingModule(facts){
	const findings = [];
	MALEFICS.forEach((k) => {
		const p = facts.planets[k]; if(!p) return;
		const hardNoHelp = aspOf(facts, k).filter((a) => [90, 180].indexOf(a.angle) >= 0);
		const benefHelp = aspOf(facts, k).filter((a) => [60, 120].indexOf(a.angle) >= 0 && BENEFICS.indexOf(a.other) >= 0);
		if(hardNoHelp.length && !benefHelp.length) findings.push(mkFinding('negative', `${cn(k)} 凶相无吉相援助`, 2));
		else if(benefHelp.length) findings.push(mkFinding('positive', `${cn(k)} 有吉相援助（化解）`, 1));
	});
	const score = scoreFromFindings(findings, 62);
	return { key: 'malefic_handling', title: '凶星处理', verdict: verdictOf(score), score, findings, detail_md: '' };
}

function topicSigModule(facts, topic){
	const findings = [];
	(topic.natural_significators || []).forEach((k) => {
		const p = facts.planets[k]; if(!p) return;
		const c = planetCondition(k, facts);
		if(c.score > 0) findings.push(mkFinding('positive', `自然徵象星 ${cn(k)} 有力(+${c.score})`, 2));
		else if(c.score < 0) findings.push(mkFinding('negative', `自然徵象星 ${cn(k)} 受剋(${c.score})`, 2));
		if(p.retro) findings.push(mkFinding('negative', `自然徵象星 ${cn(k)} 逆行`, 2));
	});
	(topic.key_houses || []).slice(0, 2).forEach((hn) => {
		const lord = facts.houses[hn] && facts.houses[hn].ruler;
		if(lord && facts.planets[lord]){
			const c = planetCondition(lord, facts);
			if(c.score < 0) findings.push(mkFinding('negative', `${hn}宫主 ${cn(lord)} 受剋`, 1));
			else if(c.score > 0) findings.push(mkFinding('positive', `${hn}宫主 ${cn(lord)} 有力`, 1));
		}
	});
	const score = scoreFromFindings(findings, 60);
	return { key: 'topic_significators', title: '徵象星（自然+宫主）', verdict: verdictOf(score), score, findings, detail_md: '' };
}

function topicHouseModule(facts, topic){
	const findings = [];
	const hn = (topic.key_houses || [])[0];
	if(hn && facts.houses[hn]){
		(facts.houses[hn].planets || []).forEach((k) => {
			if(BENEFICS.indexOf(k) >= 0) findings.push(mkFinding('positive', `吉星 ${cn(k)} 在用事宫(${hn})`, 1));
			if(MALEFICS.indexOf(k) >= 0) findings.push(mkFinding('negative', `凶星 ${cn(k)} 在用事宫(${hn})`, 1));
		});
	}
	const score = scoreFromFindings(findings, 60);
	return { key: 'topic_house', title: '用事宫本身', verdict: verdictOf(score), score, findings, detail_md: hn ? `用事宫 = ${hn} 宫` : '' };
}

function aspectPatternsModule(facts){
	// 检测：大三角 / 风筝 / 三刑会沖(T) / 大十字 / 星聚。择日喜大三角·风筝·小三角·矩形，忌 T·大十字。
	const findings = [];
	const ps = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'].filter((k) => facts.planets[k]);
	const has = (a, b, ang) => aspOf(facts, a).some((x) => x.other === b && x.angle === ang);
	// 大三角：三星两两 120°
	let grandTrine = null;
	for(let i = 0; i < ps.length && !grandTrine; i++){
		for(let j = i + 1; j < ps.length && !grandTrine; j++){
			for(let k = j + 1; k < ps.length && !grandTrine; k++){
				if(has(ps[i], ps[j], 120) && has(ps[j], ps[k], 120) && has(ps[i], ps[k], 120)){ grandTrine = [ps[i], ps[j], ps[k]]; }
			}
		}
	}
	if(grandTrine){
		findings.push(mkFinding('positive', `大三角格局（${grandTrine.map(cn).join('·')}，能量和谐·吉）`, 2));
		// 风筝：第四星对冲大三角某顶点
		let kite = false;
		grandTrine.forEach((v) => { if(!kite){ const opp = ps.find((p) => grandTrine.indexOf(p) < 0 && has(v, p, 180)); if(opp){ kite = true; } } });
		if(kite){ findings.push(mkFinding('positive', '风筝格局（大三角 + 对冲焦点，聚力·吉）', 1)); }
	}
	// 三刑会沖 T：两星对冲 + 皆 90° 第三星
	let tsquare = null;
	for(let i = 0; i < ps.length && !tsquare; i++){
		for(let j = i + 1; j < ps.length && !tsquare; j++){
			if(has(ps[i], ps[j], 180)){
				const apex = ps.find((p) => p !== ps[i] && p !== ps[j] && has(p, ps[i], 90) && has(p, ps[j], 90));
				if(apex){ tsquare = [ps[i], ps[j], apex]; }
			}
		}
	}
	if(tsquare){ findings.push(mkFinding('negative', `三刑会沖 T 格局（${tsquare.map(cn).join('·')}，张力·避）`, 2)); }
	// 大十字：≥2 组对冲
	const oppPairs = [];
	for(let i = 0; i < ps.length; i++){ for(let j = i + 1; j < ps.length; j++){ if(has(ps[i], ps[j], 180)){ oppPairs.push([ps[i], ps[j]]); } } }
	if(oppPairs.length >= 2){ findings.push(mkFinding('negative', '疑似大十字（两组对冲交织，巨张力·避）', 2)); }
	// 星聚：≥3 星同座
	const bySign = {};
	ps.forEach((k) => { const s = facts.planets[k].sign; if(s){ (bySign[s] = bySign[s] || []).push(k); } });
	Object.keys(bySign).forEach((s) => { if(bySign[s].length >= 3){ findings.push(mkFinding('neutral', `星聚 ${SIGNS[s] ? SIGNS[s].cn : s}（${bySign[s].map(cn).join('·')}，能量集中）`, 1)); } });
	const score = scoreFromFindings(findings, 60);
	return { key: 'aspect_patterns', title: '相位格局', verdict: verdictOf(score), score, findings, detail_md: '大三角 / 风筝 / 三刑会沖 / 大十字 / 星聚' };
}

function receptionModule(facts, topic){
	const findings = [];
	const recs = receptionsOf(facts, 'moon').filter((r) => r.strong);
	if(recs.length) findings.push(mkFinding('positive', '存在强接纳（可救援用事星）', 1));
	// 日月中点：吉/凶星合日月短弧中点（婚庆/合作类用事尤重）。
	const sun = facts.planets.sun; const moon = facts.planets.moon;
	if(sun && moon && sun.lon != null && moon.lon != null){
		const mid = shortMidpoint(sun.lon, moon.lon);
		['venus', 'jupiter', 'mars', 'saturn'].forEach((k) => {
			const p = facts.planets[k]; if(!p || p.lon == null) return;
			if(angularDist(p.lon, mid) <= 1.5){
				if(BENEFICS.indexOf(k) >= 0) findings.push(mkFinding('positive', `${cn(k)} 合日月中点（和合·吉）`, 1));
				else findings.push(mkFinding('negative', `${cn(k)} 合日月中点（扰动·忌）`, 1));
			}
		});
	}
	const score = scoreFromFindings(findings, 60);
	return { key: 'reception_fixedstar_midpoint', title: '接纳 / 日月中点', verdict: verdictOf(score), score, findings, detail_md: '强接纳救援 + 吉凶星合日月中点（≤1.5°）' };
}

function fixedStarsModule(facts, topic){
	const findings = [];
	const year = getChartYear(facts);
	const points = { 命度: facts.meta.ascLon, 天顶: facts.meta.mcLon, 太阳: facts.planets.sun && facts.planets.sun.lon, 月亮: facts.planets.moon && facts.planets.moon.lon };
	// 命主星
	const l1 = lord1Of(facts);
	if(l1 && facts.planets[l1]){ points[`命主星(${cn(l1)})`] = facts.planets[l1].lon; }
	// 用事自然徵象星
	(topic && topic.natural_significators || []).forEach((k) => { const p = facts.planets[k]; if(p && p.lon != null){ points[`用事星(${cn(k)})`] = p.lon; } });
	// 容许度:默认平轨 1°(零回归);全局仓改「恒星容许度/按星等」后随动(starOrbFor 单一真值)。
	const eff = effOf(facts);
	const starOpts = eff ? { fixedStarOrb: eff.fixedStarOrb, fixedStarOrbMode: eff.fixedStarOrbMode } : {};
	Object.keys(points).forEach((label) => {
		const lon = points[label]; if(lon === null || lon === undefined) return;
		FIXED_STARS.forEach((st) => {
			if(angularDist(lon, starLonAt(st.lon_1995, year)) <= starOrbFor(st, starOpts)){
				// 四王者星命中额外注守望方位(仅王者命中时追加,不动既有文案)。
				const royalNote = st.royal ? `（四王者·${st.royal.watcher}方守望）` : '';
				if(st.election && st.election.avoid) findings.push(mkFinding('negative', `${label} 会合凶恒星 ${st.name_cn}（${st.meaning}）${royalNote}`, 2));
				else findings.push(mkFinding('positive', `${label} 会合吉恒星 ${st.name_cn}（${st.meaning}）${royalNote}`, 2));
			}
		});
	});
	const score = scoreFromFindings(findings, 60);
	const orbNote = (!eff || (eff.fixedStarOrbMode !== 'byMagnitude' && (eff.fixedStarOrb === undefined || eff.fixedStarOrb === 1)))
		? '≤1° 会合关键点才计' : (eff.fixedStarOrbMode === 'byMagnitude' ? '按星等取轨（1等7°30′…王者≤5°）' : `≤${eff.fixedStarOrb}° 会合关键点才计`);
	return { key: 'fixed_stars', title: '恒星会合', verdict: verdictOf(score), score, findings, detail_md: `${orbNote}（岁差修正至 ${year} 年）` };
}

// ===== WP-1 宗派(sect)深化:昼夜派/得派吉凶星/hayz·halb/喜乐宫 =====
// 消费后端既有字段:meta.isDiurnal、p.ofSect(日木土昼/月金火夜/水按晨昏)、
// p.hayyiz('None'|'Hayyiz'|'DemiHayyiz'|'InWrongPos')、p.joy、p.aboveHorizon。
const SECT_SEVEN = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
function sectModule(facts){
	const findings = [];
	const day = !!facts.meta.isDiurnal;
	const sectBenefic = day ? 'jupiter' : 'venus';    // 得派吉星=本盘首席吉星
	const outMalefic = day ? 'mars' : 'saturn';       // 离派凶星=本盘最须提防
	const inMalefic = day ? 'saturn' : 'mars';        // 得派凶星=凶性缓和

	findings.push(mkFinding('neutral', `${day ? '昼' : '夜'}盘：得派吉星为${cn(sectBenefic)}（首席吉星），离派凶星为${cn(outMalefic)}（凶性最烈）`, 1));

	const sb = facts.planets[sectBenefic];
	if(sb){
		if(sb.dignityScore >= 2 && !sb.retro) findings.push(mkFinding('positive', `得派吉星 ${cn(sectBenefic)} 有力顺行，可堪重用`, 2));
		if(sb.angularity === 'angular') findings.push(mkFinding('positive', `得派吉星 ${cn(sectBenefic)} 临角宫，助力直接`, 2));
	}
	const om = facts.planets[outMalefic];
	if(om){
		if(om.angularity === 'angular') findings.push(mkFinding('negative', `离派凶星 ${cn(outMalefic)} 临角宫：本盘最烈之凶落显位`, 3));
		else if(om.house && [3, 6, 9, 12].indexOf(om.house) >= 0) findings.push(mkFinding('positive', `离派凶星 ${cn(outMalefic)} 落果宫(${om.house})，凶性被边缘化`, 1));
	}
	const im = facts.planets[inMalefic];
	if(im && im.angularity === 'angular') findings.push(mkFinding('neutral', `得派凶星 ${cn(inMalefic)} 临角宫：虽凶但得派，凶性有节制`, 1));

	SECT_SEVEN.forEach((k) => {
		const p = facts.planets[k];
		if(!p) return;
		if(p.hayyiz === 'Hayyiz') findings.push(mkFinding('positive', `${cn(k)} 得时(hayz)：宗派/半球/阴阳座三者皆合，如人得志`, 2));
		else if(p.hayyiz === 'DemiHayyiz') findings.push(mkFinding('positive', `${cn(k)} 半得时(halb)，状态偏佳`, 1));
		else if(p.hayyiz === 'InWrongPos') findings.push(mkFinding('negative', `${cn(k)} 失时(逆其宗派之位)，如人失所`, 1));
		if(p.joy) findings.push(mkFinding('positive', `${cn(k)} 入喜乐宫，自得其乐`, 1));
	});

	const score = scoreFromFindings(findings, 60);
	return { key: 'sect', title: '宗派（昼夜派）', verdict: verdictOf(score), score, findings, detail_md: `${day ? '昼' : '夜'}盘。得时=宗派+半球+阴阳座三合；喜乐宫=水1月3金5火6日9木11土12。` };
}

// ===== WP-2 月相机制全集:传光/收光/阻碍/挫败/回避风险/围攻/野逸 =====
// 数据源=后端相位表(入相/出相+orb)+速度/逆行;凡涉「未来完成序」者按 orb 大小保守推断并明示口径。
const MOON_MECH_BENEFICS = ['jupiter', 'venus'];
const MOON_MECH_MALEFICS = ['mars', 'saturn'];
function isBen(k){ return MOON_MECH_BENEFICS.indexOf(k) >= 0; }
function isMal(k){ return MOON_MECH_MALEFICS.indexOf(k) >= 0; }
function moonMechanicsModule(facts){
	const findings = [];
	const moon = facts.planets.moon;
	if(!moon) return { key: 'moon_mechanics', title: '月相机制', verdict: 'neutral', score: 60, findings, detail_md: '' };
	// 全模块仅论七曜:传光/收光/阻碍/挫败为古典机制,不涉三王星;
	// 且三王星常年近守留速度,纳入会量产伪「挫败/回避」噪音。
	const ma = aspOf(facts, 'moon').filter((a) => SECT_SEVEN.indexOf(a.other) >= 0);
	const app = ma.filter((a) => a.applying);
	const sep = ma.filter((a) => a.separating);

	// 传光 translation of light:月刚离 A、正入 B → 把 A 之光传递给 B(连接两事)。
	sep.forEach((s) => {
		app.forEach((a) => {
			if(s.other === a.other) return;
			const pol = isMal(a.other) ? 'negative' : (isBen(a.other) ? 'positive' : 'neutral');
			findings.push(mkFinding(pol, `传光：月离 ${cn(s.other)}（${s.angle}°）转而入相 ${cn(a.other)}（${a.angle}°，差 ${a.orb != null ? Number(a.orb).toFixed(1) : '-'}°）——将前者之事引渡给后者${isMal(a.other) ? '，所托非人' : (isBen(a.other) ? '，善果可期' : '')}`, isMal(a.other) || isBen(a.other) ? 2 : 1));
		});
	});

	// 收光 collection of light:A、B 同时入相更慢的 X → X 汇集双方(第三方促成)。
	SECT_SEVEN.forEach((x) => {
		if(x === 'moon') return;
		const collectors = [];
		SECT_SEVEN.forEach((k) => {
			if(k === x) return;
			const ka = aspOf(facts, k).filter((a) => a.applying && a.other === x);
			if(ka.length) collectors.push(k);
		});
		const px = facts.planets[x];
		const slower = px && px.speed != null && collectors.every((k) => {
			const pk = facts.planets[k];
			return pk && pk.speed != null && Math.abs(px.speed) < Math.abs(pk.speed);
		});
		if(collectors.length >= 2 && slower){
			const pol = isMal(x) ? 'negative' : (isBen(x) ? 'positive' : 'neutral');
			findings.push(mkFinding(pol, `收光：${collectors.map(cn).join('、')} 同入相更慢的 ${cn(x)}——由${isMal(x) ? '凶星' : (isBen(x) ? '吉星' : '第三方')}居间汇集促成`, 2));
		}
	});

	// 阻碍 prohibition:月入相 B,另一七曜 C 亦入相 B 且差更小(先成相截走)。
	// 同一目标只报「最先成相」的一位阻碍者(其余更远者无实义,徒增噪音)。
	app.forEach((a) => {
		let best = null;
		SECT_SEVEN.forEach((c) => {
			if(c === 'moon' || c === a.other) return;
			aspOf(facts, c).forEach((x) => {
				if(x.applying && x.other === a.other && x.orb != null && a.orb != null && x.orb < a.orb){
					if(!best || x.orb < best.orb) best = { c, orb: x.orb };
				}
			});
		});
		if(best){
			findings.push(mkFinding('negative', `阻碍：${cn(best.c)} 先于月与 ${cn(a.other)} 成相（${Number(best.orb).toFixed(1)}° < ${Number(a.orb).toFixed(1)}°），月之所求被截走`, 2));
		}
	});

	// 挫败 frustration:月入相 B,而 B 自身先与他曜成相(入相差更小)→ B 无暇受月。
	// B 只会「先赴最紧一约」,故仅报其中差最小者。
	app.forEach((a) => {
		let best = null;
		aspOf(facts, a.other).forEach((x) => {
			if(x.applying && x.other !== 'moon' && SECT_SEVEN.indexOf(x.other) >= 0
				&& x.orb != null && a.orb != null && x.orb < a.orb){
				if(!best || x.orb < best.orb) best = x;
			}
		});
		if(best){
			findings.push(mkFinding('negative', `挫败：${cn(a.other)} 先赴与 ${cn(best.other)} 之约（${Number(best.orb).toFixed(1)}°），月的入相落空`, 1));
		}
	});

	// 回避风险 refranation:月正入相之星临守留/逆行(可能在成相前转向退出)。
	app.forEach((a) => {
		const p = facts.planets[a.other];
		if(p && ((p.speed != null && Math.abs(p.speed) < 0.05) || p.retro)){
			findings.push(mkFinding('negative', `回避风险：${cn(a.other)} ${p.retro ? '逆行' : '守留'}中，月入相恐未成先退（按现速推断）`, 1));
		}
	});

	// 围攻 besiegement:光线围攻(出相凶+入相凶)与体围攻(黄经两侧 7° 内被火土夹)。
	['moon', 'venus', 'jupiter', 'sun', 'mercury'].forEach((k) => {
		const p = facts.planets[k];
		if(!p) return;
		const ka = aspOf(facts, k);
		const sepMal = ka.some((a) => a.separating && isMal(a.other));
		const appMal = ka.some((a) => a.applying && isMal(a.other));
		if(sepMal && appMal){
			findings.push(mkFinding('negative', `光线围攻：${cn(k)} 离一凶复入一凶（火/土前后夹击），腹背受敌`, 2));
		}
		const mars = facts.planets.mars; const sat = facts.planets.saturn;
		if(mars && sat && p.lon != null){
			const dM = angularDist(p.lon, mars.lon); const dS = angularDist(p.lon, sat.lon);
			if(dM <= 7 && dS <= 7){
				findings.push(mkFinding('negative', `体围攻：${cn(k)} 黄经两侧 7° 内被火土同夹，处境艰险`, 2));
			}
		}
	});

	// 野逸 feral:全无托勒密相位(后端已判)。
	if(moon.feral) findings.push(mkFinding('negative', '月亮野逸（与七政全无主相位）：如野马无缰，行事无援', 2));

	if(!findings.length) findings.push(mkFinding('neutral', '月相机制平顺：无传光/收光/阻碍/挫败/围攻诸象', 1));
	const score = scoreFromFindings(findings, 60);
	return { key: 'moon_mechanics', title: '月相机制（传光·收光·围攻）', verdict: verdictOf(score), score, findings, detail_md: '中世纪择日核心:月为万事之引线;凡涉先后成相者按现盘入相差推断。' };
}


// ===== WP-3 行星时/值日星:后端 timerStar/dayerStar 已算,此处判用事匹配与时主状态 =====
function planetaryHourModule(facts, topic){
	const findings = [];
	const hr = facts.meta.hourRuler;
	const dr = facts.meta.dayRuler;
	const sigs = (topic && topic.natural_significators) || [];
	if(!hr){
		findings.push(mkFinding('neutral', '本盘未回传行星时主星', 1));
		const score0 = scoreFromFindings(findings, 60);
		return { key: 'planetary_hours', title: '行星时（时主/日主）', verdict: verdictOf(score0), score: score0, findings, detail_md: '' };
	}
	const themes = PLANETARY_HOURS[hr];
	findings.push(mkFinding('neutral', `现值 ${cn(hr)} 之时、${dr ? cn(dr) : '—'} 之日${themes ? `；此时主题：${themes.join(' / ')}` : ''}`, 1));
	if(sigs.indexOf(hr) >= 0) findings.push(mkFinding('positive', `用事星 ${cn(hr)} 正当其时（首选:择事项主星之行星时）`, 2));
	if(dr && sigs.indexOf(dr) >= 0){
		findings.push(mkFinding('positive', `值日星 ${cn(dr)} 即用事星`, 1));
		if(dr === hr) findings.push(mkFinding('positive', '日时合一：值日星与时主同星，其力尤强', 2));
	}
	const hp = facts.planets[hr];
	if(hp){
		if(hp.dignityScore >= 2 && !hp.retro && !hp.combustion) findings.push(mkFinding('positive', `时主 ${cn(hr)} 有尊贵、顺行、免燃烧`, 1));
		if(hp.retro) findings.push(mkFinding('negative', `时主 ${cn(hr)} 逆行`, 1));
		if(hp.combustion === 'combust') findings.push(mkFinding('negative', `时主 ${cn(hr)} 燃烧`, 1));
		if(hp.angularity === 'angular') findings.push(mkFinding('positive', `时主 ${cn(hr)} 临角宫`, 1));
	}
	if((hr === 'mars' || hr === 'saturn') && sigs.indexOf(hr) < 0) findings.push(mkFinding('negative', `凶星 ${cn(hr)} 之时（非其所辖用事宜避）`, 1));
	const score = scoreFromFindings(findings, 60);
	return { key: 'planetary_hours', title: '行星时（时主/日主）', verdict: verdictOf(score), score, findings, detail_md: '值日星序:日月火水木金土(周日起);行星时按迦勒底序自日出轮转。' };
}

// ===== WP-4 月宿(西方28宿·Agrippa 白羊0°均分) =====
function mansionModule(facts, topic){
	const findings = [];
	const moon = facts.planets.moon;
	if(!moon || moon.lon == null){
		return { key: 'mansions', title: '月宿（西方28宿）', verdict: 'neutral', score: 60, findings, detail_md: '' };
	}
	const eff = effOf(facts);
	const anchor = (eff && eff.mansionAnchor) || 'equal_aries0';
	const m = mansionOf(moon.lon, anchor, getChartYear(facts));
	findings.push(mkFinding('neutral', `月在第 ${m.n} 宿 ${m.name}（${m.alt}）：${m.nature}。用途：${m.use}`, 1));
	const map = TOPIC_MANSION_MAP[topic && topic.topic_id];
	if(map){
		const goodSet = map.good ? MANSION_ELECTION_SETS[map.good] : null;
		const badSet = map.bad ? MANSION_ELECTION_SETS[map.bad] : null;
		if(goodSet && goodSet.indexOf(m.n) >= 0) findings.push(mkFinding('positive', `本宿正宜此用事（速查${map.good === 'travel_good' ? '·旅' : map.good === 'love' ? '·爱/婚姻' : map.good === 'gain' ? '·收益' : '·疗愈'}集）`, 2));
		else if(badSet && badSet.indexOf(m.n) >= 0) findings.push(mkFinding('negative', `本宿忌此用事（${map.bad === 'travel_bad' ? '阻旅行' : '毁灭/不和/分离'}集，专此意者除外）`, 2));
	}else if(m.good === false){
		findings.push(mkFinding('negative', '本宿性凶（毁灭/不和类），一般用事宜避', 1));
	}
	// 通则:月增光+不受克 于吉宿则善用
	const mp = facts.meta.moonPhase;
	if(m.good === true && mp && mp.phase === 'waxing' && !moon.combustion) findings.push(mkFinding('positive', '月增光、免燃烧而入吉宿：可乘其力', 1));
	if(moon.combustion === 'combust') findings.push(mkFinding('negative', '月燃烧：宿力难用（通则尤忌）', 1));
	const score = scoreFromFindings(findings, 60);
	const anchorNote = anchor === 'sheratan'
		? '实星锚（宿1起于 Sheratan 当年岁差实位）12°51′26″/宿'
		: 'Agrippa 白羊0°均分 12°51′26″/宿';
	return { key: 'mansions', title: '月宿（西方28宿）', verdict: verdictOf(score), score, findings, detail_md: `${anchorNote}；通则:择月入所选宿、增光不受克、不空亡。` };
}

// ===== WP-5 映点隐合/隐冲(≤1°):映点=关于巨蟹0°轴对称(180−λ);反映点=关于白羊0°轴(360−λ) =====
const ANTISCIA_KEYS = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
function antisciaModule(facts){
	const findings = [];
	const pts = [];
	ANTISCIA_KEYS.forEach((k) => { const p = facts.planets[k]; if(p && p.lon != null) pts.push({ k, lon: p.lon }); });
	if(facts.meta.ascLon != null) pts.push({ k: 'asc', lon: facts.meta.ascLon, isPoint: true });
	const nameOf = (o) => (o.k === 'asc' ? '命度' : cn(o.k));
	// 接触容许度:默认 1°(零回归);全局「映点接触容许度」改后随动。
	const effA = effOf(facts);
	const antiOrb = (effA && typeof effA.antisciaOrb === 'number' && effA.antisciaOrb > 0) ? effA.antisciaOrb : 1;
	for(let i = 0; i < pts.length; i++){
		for(let j = 0; j < pts.length; j++){
			if(i === j) continue;
			const a = pts[i]; const b = pts[j];
			if(a.isPoint) continue; // 映点只从行星投出,命度仅作受点
			const anti = norm360(180 - a.lon);
			const contra = norm360(360 - a.lon);
			const dA = angularDist(anti, b.lon);
			const dC = angularDist(contra, b.lon);
			if(i < j || b.isPoint){ // 行星对去重(i<j);受点=命度恒报
				if(dA <= antiOrb){
					const mal = isMal(a.k) || isMal(b.k);
					findings.push(mkFinding(mal ? 'negative' : (isBen(a.k) || isBen(b.k) ? 'positive' : 'neutral'), `映点隐合：${nameOf(a)} 映点（${anti.toFixed(1)}°）合 ${nameOf(b)}（差 ${dA.toFixed(1)}°）——如暗中合相${mal ? '，凶星者尤须防暗损' : ''}`, 2));
				}
				if(dC <= antiOrb){
					findings.push(mkFinding('negative', `反映点隐冲：${nameOf(a)} 反映点（${contra.toFixed(1)}°）冲 ${nameOf(b)}（差 ${dC.toFixed(1)}°）——如暗中对分`, 1));
				}
			}
		}
	}
	const orbTxt = antiOrb === 1 ? '≤1°' : `≤${antiOrb}°`;
	if(!findings.length) findings.push(mkFinding('neutral', `无 ${orbTxt} 映点隐合/隐冲`, 1));
	const score = scoreFromFindings(findings, 60);
	return { key: 'antiscia', title: '映点（隐合/隐冲）', verdict: verdictOf(score), score, findings, detail_md: `映点=关于巨蟹0°—摩羯0°轴对称;反映点=关于白羊0°—天秤0°轴。仅 ${orbTxt} 计。` };
}

// ===== WP-6 恒星交映(parans·Brady 口径·固定地点) =====
function paransModule(facts, topic){
	const findings = [];
	const params = (facts.result && facts.result.params) || {};
	// 空串防御:Number('')===0 会把「缺失」误当赤道 —— 非空才数值化。
	const lat = (params.gpsLat != null && params.gpsLat !== '') ? Number(params.gpsLat) : null;
	if(lat === null || !Number.isFinite(lat)){
		findings.push(mkFinding('neutral', '缺地理纬度，无法计算恒星交映', 1));
		return { key: 'parans', title: '恒星交映（parans）', verdict: 'neutral', score: 60, findings, detail_md: '' };
	}
	const year = getChartYear(facts);
	const stars = FIXED_STARS.slice(0, 10).map((st) => ({
		name_cn: st.name_cn, lon: starLonAt(st.lon_1995, year), dec: st.declination,
		avoid: !!(st.election && st.election.avoid), meaning: st.meaning,
		conditional: (st.election && st.election.conditional) || null,
	}));
	const bodies = [];
	ANTISCIA_KEYS.forEach((k) => { const p = facts.planets[k]; if(p && p.lon != null) bodies.push({ key: k, cn: cn(k), lon: p.lon }); });
	const hits = paransAt(lat, bodies, stars, 2);
	// 同星同曜多轴命中只取最紧一对
	const seen = {};
	const sigs = (topic && topic.natural_significators) || [];
	hits.forEach((h) => {
		const kk = h.star + '|' + h.body;
		if(seen[kk]) return;
		seen[kk] = 1;
		const key = h.body === 'sun' || h.body === 'moon' || sigs.indexOf(h.body) >= 0;
		// 带条件限定的星(如「利事业不利婚姻」)不径直给正号:降 neutral 并附条件原文。
		const pol = h.avoid ? (key ? 'negative' : 'neutral') : (key && !h.conditional ? 'positive' : 'neutral');
		findings.push(mkFinding(pol, `${h.star} ${h.starAxis} 与 ${h.bodyCn} ${h.bodyAxis} 交映（差 ${h.diffMin} 分钟）——${h.meaning}${h.avoid && key ? '；凶星交映日/月/用事星须防' : ''}${h.conditional ? `（${h.conditional}）` : ''}`, h.avoid && key ? 2 : 1));
	});
	if(!Object.keys(seen).length) findings.push(mkFinding('neutral', '本时刻本地无紧恒星交映（≤8 分钟）', 1));
	const score = scoreFromFindings(findings, 60);
	return { key: 'parans', title: '恒星交映（parans）', verdict: verdictOf(score), score, findings, detail_md: '固定地点:恒星与七曜四轴（升/中天/落/天底）恒星时差 ≤8 分钟判交映;行星按黄纬≈0 近似;主用 10 星。' };
}


// ===== WP-10a 可判性(radicality·Lilly 口径):这张盘本身可靠吗 =====
function radicalityModule(facts){
	const findings = [];
	let r = null;
	const eff = effOf(facts);
	try{ r = radicality(facts, eff ? { viaCombustaVariant: eff.viaCombustaVariant } : undefined); }catch(e){ r = null; }
	if(r){
		(r.ok || []).forEach((t) => findings.push(mkFinding('positive', t, 1)));
		(r.warnings || []).forEach((w) => findings.push(mkFinding('negative', w.text, 1)));
	}
	if(!findings.length) findings.push(mkFinding('neutral', '无可判性警告', 1));
	const score = scoreFromFindings(findings, 62);
	return { key: 'radicality', title: '可判性（盘之可靠）', verdict: verdictOf(score), score, findings, detail_md: '命度过早/过晚、月空/月燃、土星落一宫等——提示这一时刻的盘是否「可托付判断」,警告不阻断。' };
}

// ===== WP-10b→R2 胜利星(Almuten Figuris·五命点权威实现,与寿命/卜卦共用 engine/almuten) =====
// 五命点=日/月/上升/福点/产前朔望(后端 Syzygy 对象;缺则按四点计并注明,不臆造)。
// 计分:庙5 旺4 三分3(按昼夜取主,Dorothean 另计共主) 界2 面1——界/三分随流派口径。
function syzygyLonOf(facts){
	const r = facts.result || {};
	let o = (r.objectMap && r.objectMap.Syzygy) || null;
	if(!o){
		const objs = (r.chart && r.chart.objects) || [];
		for(let i = 0; i < objs.length; i++){ if(objs[i].id === 'Syzygy'){ o = objs[i]; break; } }
	}
	return o && o.lon !== undefined && o.lon !== null ? o.lon : null;
}
function almutenModule(facts){
	const findings = [];
	const eff = effOf(facts);
	const fortune = facts.planets.fortune;
	const af = almutenFiguris(facts, { fortune: fortune && fortune.lon != null ? { lon: fortune.lon } : null }, {
		termsVariant: eff ? eff.termsVariant : 0,
		tripSystem: (eff && eff.tripSystem === 'ptolemaic') ? 'ptolemaic' : 'dorothean',
		tripIncludeParticipating: !(eff && eff.tripSystem === 'ptolemaic'),
		syzygyLon: syzygyLonOf(facts),
	});
	facts.almuten = af;   // 供「尊贵强弱」页矩阵展示(五点逐点计分)
	if(!af.winners.length){
		findings.push(mkFinding('neutral', '命点不足，无法计算胜利星', 1));
	}else{
		const nPts = af.points.length;
		findings.push(mkFinding('neutral', `胜利星（Almuten Figuris）：${af.winners.map(cn).join('、')}（${af.best} 分；按${nPts === 5 ? '五' : '四'}命点计${nPts < 5 ? '，事盘无产前朔望' : '，含产前朔望'}）`, 1));
		const top = af.winners[0];
		const p = facts.planets[top];
		if(p){
			if(p.dignityScore >= 2 && !p.retro) findings.push(mkFinding('positive', `胜利星 ${cn(top)} 在盘中有力顺行——全盘有主心骨`, 2));
			else if(p.retro || p.combustion === 'combust' || p.dignityScore <= -4) findings.push(mkFinding('negative', `胜利星 ${cn(top)} 受克（逆行/燃烧/落陷）——全盘乏主`, 2));
			if(p.angularity === 'angular') findings.push(mkFinding('positive', `胜利星 ${cn(top)} 临角宫`, 1));
		}
		const ranked = Object.keys(af.totals).sort((a, b) => af.totals[b] - af.totals[a]);
		const runner = ranked.filter((k) => af.winners.indexOf(k) < 0).slice(0, 2);
		if(runner.length) findings.push(mkFinding('neutral', `次位：${runner.map((k) => `${cn(k)}(${af.totals[k]})`).join('、')}`, 1));
	}
	const score = scoreFromFindings(findings, 60);
	return { key: 'almuten', title: '胜利星（Almuten Figuris）', verdict: verdictOf(score), score, findings, detail_md: '五命点(日/月/上升/福点/产前朔望)逐点五尊贵计分:庙5旺4三分3界2面1,跨点累计最高者为全盘胜利星;界/三分随流派口径。' };
}

// ===== R2 吉化/凶化模块(engine 与「尊贵强弱」页共用 dignityReport.bonificationReport) =====
function bonificationModule(facts){
	const items = bonificationReport(facts);
	const findings = items.map((it) => mkFinding(it.polarity, it.text, it.kind === 'maltreat' ? 2 : 1));
	if(!findings.length) findings.push(mkFinding('neutral', '无吉化/凶化条件命中（凌制/围合/背离/执矛/日心均未见）', 1));
	const score = scoreFromFindings(findings, 60);
	return { key: 'bonification', title: '吉化 / 凶化（凌制·围合·背离）', verdict: verdictOf(score), score, findings, detail_md: '吉化=3°内入相合吉星/优位四分三分凌制/吉围合/执矛/日心;凶化=凶星同度/优位凌制/围攻/背离其定位星。凌制取整宫口径,黄道在先者为主。' };
}

// 黄经 → 星座 key(供 almuten 用)
function signKeyOfLon(lon){
	const idx = Math.floor(normLon(lon) / 30);
	return ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces'][idx];
}

// ===== R2 阿拉伯点模块:福/精神状态 + 用事关联分科点(facts.lots 由 electionEngine 组装) =====
const LOT_CONTACT_ORB = 3;   // 点为虚点,取紧合/冲/刑接触判受照(±3°)
function lotContacts(facts, lon){
	const hits = [];
	['jupiter', 'venus', 'mars', 'saturn'].forEach((k) => {
		const p = facts.planets[k];
		if(!p || p.lon === null || p.lon === undefined) return;
		[[0, '合'], [90, '刑'], [180, '冲'], [120, '拱'], [60, '六合']].forEach(([ang, label]) => {
			const target = normLon(lon + ang);
			const target2 = normLon(lon - ang);
			if(angularDist(p.lon, target) <= LOT_CONTACT_ORB || (ang !== 0 && ang !== 180 && angularDist(p.lon, target2) <= LOT_CONTACT_ORB)){
				hits.push({ planet: k, angle: ang, label, benefic: BENEFICS.indexOf(k) >= 0 });
			}
		});
	});
	return hits;
}
function lotsModule(facts, topic){
	const findings = [];
	const lots = facts.lots;
	if(!lots || (!lots.hermetic.length && !lots.topical.length)){
		return { key: 'lots', title: '阿拉伯点', verdict: 'neutral', score: 60, findings: [mkFinding('neutral', '缺上升/福点数据，无法组装阿拉伯点', 1)], detail_md: '' };
	}
	const judge = (row, weightBase) => {
		if(!row) return;
		const contacts = lotContacts(facts, row.lon);
		const good = contacts.filter((c) => c.benefic && (c.angle === 0 || c.angle === 120 || c.angle === 60));
		const bad = contacts.filter((c) => !c.benefic && (c.angle === 0 || c.angle === 90 || c.angle === 180));
		let text = `${row.cn} 落 ${row.signCn} ${row.signlon}°${row.house ? `·第 ${row.house} 宫` : ''}（定位星 ${row.dispositorCn}）`;
		if(good.length) text += `；受吉星${good.map((c) => `${cn(c.planet)}${c.label}`).join('、')}`;
		if(bad.length) text += `；受凶星${bad.map((c) => `${cn(c.planet)}${c.label}`).join('、')}`;
		const pol = bad.length && !good.length ? 'negative' : (good.length && !bad.length ? 'positive' : 'neutral');
		findings.push(mkFinding(pol, text, (good.length || bad.length) ? weightBase : 1));
	};
	judge(lots.byId.fortune, 2);
	judge(lots.byId.spirit, 2);
	// 用事关联分科点(topicMaster.topic_lots;marriageAuto/erosAuto 已由引擎按口径落点)
	(facts.topicLotIds || []).forEach((id) => {
		if(id === 'fortune' || id === 'spirit') return;
		judge(lots.byId[id], 2);
	});
	if(!findings.length) findings.push(mkFinding('neutral', '福/精神点无紧密受照，状态平平', 1));
	const score = scoreFromFindings(findings, 60);
	return { key: 'lots', title: '阿拉伯点（福·精神·分科）', verdict: verdictOf(score), score, findings, detail_md: '福点=后端盘面同源;精神点=福点关于上升之镜像;受照按 ±3° 紧接触计。全谱见右栏「阿拉伯点」页。' };
}

// school:westernSchools 五档之一(红线/权重/口径的流派载体;缺省=modern_main 行为)。
// 口径细化值经 facts.eff(electionEngine 注入)读取——本签名保住「runModules 必须接 school」的护栏语义。
export function runModules(facts, topic, school){
	return [
		moonModule(facts),
		ascRulerModule(facts),
		ascendantModule(facts, topic),
		topicSigModule(facts, topic),
		anglesModule(facts),
		topicHouseModule(facts, topic),
		sunModule(facts),
		maleficHandlingModule(facts),
		aspectPatternsModule(facts),
		receptionModule(facts, topic),
		fixedStarsModule(facts, topic),
		sectModule(facts),
		moonMechanicsModule(facts),
		planetaryHourModule(facts, topic),
		mansionModule(facts, topic),
		antisciaModule(facts),
		paransModule(facts, topic),
		radicalityModule(facts),
		almutenModule(facts),
		lotsModule(facts, topic),
		bonificationModule(facts),
	];
}

export default runModules;
