// divination/horary/horarySnapshot.js
// 把卜卦判断结果拼成 AI 快照文本（[小节标题] + markdown 列表），供 saveModuleAISnapshot('horary', ...)。
import { PLANETS } from '../data/planets.js';
import { SIGNS, signOfLon } from '../data/signs.js';
import { PLANETARY_HOURS } from '../data/planetaryHours.js';
import { CATEGORY_DEF } from './significators.js';
import { schoolOf } from './horarySchools.js';
import * as AstroText from '../../../constants/AstroText.js';
import { buildAntisciaTable } from './antisciaTable.js';
import { getQuestionGuide } from './questionGuide.js';
import { NATURAL_SIGNIFICATORS } from '../data/naturalSignificators.js';

function cn(k){ return (PLANETS[k] || {}).cn || k || '—'; }
const ASPECT_CN = { 0: '合相', 60: '六合', 90: '四分(刑)', 120: '三合', 180: '对分(冲)' };
const ANG_CN = { angular: '角宫·有力', succedent: '续宫·中等', cadent: '果宫·偏弱' };

// [征象力量] 单星状态行:与 HoraryJudgment.plainState 同构(同 facts.planets 取数,文案逐字一致);
// 不 import 组件文件(HoraryJudgment 已 import 本文件,反向引会成环)。
function planetPlainState(facts, k){
	const p = facts && facts.planets ? facts.planets[k] : null;
	if(!p) return '';
	const sgn = (SIGNS[p.sign] || {}).cn || p.sign;
	const ang = ANG_CN[p.angularity] || '';
	const dig = p.dignityScore >= 4 ? '入庙旺·有力' : (p.dignityScore <= -4 ? '落陷失势·无力' : (p.peregrine ? '游走·无尊贵' : '尊贵平平'));
	const extra = [];
	if(p.retro) extra.push('逆行');
	if(p.combustion === 'combust') extra.push('燃烧受灼');
	else if(p.combustion === 'cazimi') extra.push('居日心·极强');
	else if(p.combustion === 'under_beams') extra.push('日光束下');
	return `落 ${sgn}座 · 第${p.house || '?'}宫 · ${ang} · ${dig}${extra.length ? ' · ' + extra.join('/') : ''}`;
}

// [古典接纳] 行星/尊贵中文:chart.receptions/mutuals 的 id 是后端盘面 id(Sun/Moon…),
// 与「占星·古典」同源取中文(AstroMsgCN 全名优先);尊贵 token(ruler/exalt/term…)走 AstroMsg 中文表。
function clsPlanetCn(id){ return AstroText.AstroMsgCN[id] || AstroText.AstroTxtMsg[id] || id || '—'; }
function clsDignCn(ary){ return (ary || []).map((t) => AstroText.AstroMsg[t] || t).join('+'); }
function clsHasRefuse(tokens){ return (tokens || []).some((t) => t === 'exile' || t === 'fall'); }

// opts3（可选;批6）：{ questionText, castingCamp } —— 问句与阵营入 [定盘考量] 段;不传=不产该两行(零回归)。
export function buildHorarySnapshot(j, chart, opts3){
	if(!j) return '';
	const L = [];
	const sig = j.significators;
	const school = schoolOf(j.school);
	L.push('[起卦信息]');
	L.push(`问题类别：${(CATEGORY_DEF[j.category] && CATEGORY_DEF[j.category].quesitedLabel) || j.category}`);
	L.push(`判读流派：${school.cn}（${school.desc}）`);
	L.push(`时主星（活跃征象）：${cn(j.hourRuler)}`);
	L.push('[根本性]');
	L.push(j.radicality.suitable ? '适合判断。' : ('有警告（不阻断）：' + j.radicality.warnings.map((w) => w.text).join('；')));
	L.push('[征象星指派]');
	L.push(`问卜者 = 1宫主 ${cn(sig.querentKey)} ＋ 月亮`);
	// [复审P5] 法E almuten 拆分出的星不是宫主——标签如实标「宫头总管」。
	const qRole = (sig.sharedRuler && sig.sharedRuler.almutenSplit === sig.quesitedKey)
		? (sig.quesitedHouse ? sig.quesitedHouse + '宫头总管 ' : '宫头总管 ')
		: (sig.quesitedHouse ? sig.quesitedHouse + '宫主 ' : '');
	L.push(`${sig.quesitedLabel || '事项'} = ${qRole}${cn(sig.quesitedKey)}${sig.natural ? '（自然征象星 ' + cn(sig.natural) + '）' : ''}`);
	// [H5] 转宫/宫内驻星/自然征象升格——字段在场才产行(缺省档全空=零回归)。
	if(sig.turned){
		L.push(`转宫：第 ${sig.turned.personHouse} 宫人的第 ${sig.turned.radicalHouse} 宫事 → 本盘第 ${sig.turned.turnedHouse} 宫（引擎已自动转宫）`);
	}
	if(sig.coSignificators && sig.coSignificators.length){
		L.push(`用事宫内驻星（co-significator，低权参证）：${sig.coSignificators.map(cn).join('、')}`);
	}
	if(sig.naturalPromoted){
		L.push(`自然征象星升 co-quesited：${sig.naturalPromotionReason || ''}`);
	}
	L.push('[完成分析]');
	if(j.perfection){ j.perfection.detail.forEach((d) => L.push('- ' + d)); }
	L.push(`完成度三分：安全征象 ${j.thirds.count}/${j.thirds.total} → ${j.thirds.fraction}`);
	if(j.moonStory){
		L.push('[月亮的故事]');
		(j.moonStory.separating || []).slice(0, 2).forEach((a) => L.push(`- 月刚离开 ${cn(a.other)}（${ASPECT_CN[a.angle] || a.angle + '°'}，已过 ${a.orb.toFixed(1)}°）→ 事情来由/已过`));
		const app = j.moonStory.applying || [];
		if(app.length) app.slice(0, 3).forEach((a) => L.push(`- 月接下来会 ${cn(a.other)}（${ASPECT_CN[a.angle] || a.angle + '°'}，还差 ${a.orb.toFixed(1)}°）→ 事情走向/将发生`));
		else L.push('- 月亮接下来无主相位（空亡）');
	}
	if(j.allAspects && j.allAspects.length){
		L.push('[相位全览]');
		L.push('| 星A | 相位 | 星B | 状态 | 误差 |');
		L.push('| --- | --- | --- | --- | --- |');
		j.allAspects.forEach((a) => L.push(`| ${cn(a.a)} | ${ASPECT_CN[a.angle] || a.angle + '°'} | ${cn(a.b)} | ${a.applying ? '入相/将成' : '出相/已过'} | 差 ${a.orb.toFixed(1)}°${a.exact ? '·正相位' : ''} |`));
	}
	L.push('[裁决]');
	// [H7] v2 档判语带置信度五档(legacy 分支逐字保留=基线零变);单显规则:只按当前 profile 出一轨。
	if(j.verdict.profile === 'v2'){
		L.push(`裁决（全证词池）：${j.verdict.summary}`);
		if((j.verdict.conditions || []).length){ L.push('条件式结论：' + j.verdict.conditions.map((c) => c.text).join('；')); }
		if((j.verdict.guards || []).length){ L.push('结构护栏：完成法/破坏为结构性证词,数值分不越其界。'); }
	}else{
		L.push('倾向：' + j.verdict.summary);
	}
	if(j.verdict.positive.length) L.push('有利证词：' + j.verdict.positive.map((p) => p.text).join('；'));
	if(j.verdict.negative.length) L.push('不利证词：' + j.verdict.negative.map((n) => n.text).join('；'));
	L.push(`Query：①能否成事=${j.queries.canHappen.text} ②好坏=${j.queries.goodEvil.text} ③真假=${j.queries.reportTrue.text}`);
	L.push('[应期方位]');
	L.push((j.timing ? j.timing.text : '无准确相位，应期不定') + '；方位：' + (j.queries.where ? `${j.queries.where.dir}（${j.queries.where.terrain}），${j.queries.where.distance}` : '—'));
	if(j.lots){
		L.push(`阿拉伯点（${j.lots.convention}）：福点 ${j.lots.fortune.signCn}座 ${j.lots.fortune.signlon.toFixed(1)}°${j.lots.fortune.dispCn ? '·定位星' + j.lots.fortune.dispCn : ''}；精神点 ${j.lots.spirit.signCn}座 ${j.lots.spirit.signlon.toFixed(1)}°`);
	}
	if(j.topic){
		L.push(`[专题深化·${j.topic.title}]`);
		j.topic.lines.forEach((t) => L.push('- ' + t.text));
	}
	if(j.describe && j.describe.length){
		L.push('[描述]');
		j.describe.forEach((d) => L.push(`- ${d.role}：${d.title}${d.temper ? '（' + d.temper + '）' : ''} ${d.body}`));
	}
	L.push('（裁决只呈现证据与倾向，不替用户下命定结论。）');
	// ── 批6 增节(全部为「只加新段」:既有段字节不动;表化零变测试的比对域=基线纪元段) ──
	// [定盘考量] 19 条三态 + 时主一致双口径。
	const rad = j.radicality || {};
	if(rad.considerations && rad.considerations.items && rad.considerations.items.length){
		L.push('[定盘考量]');
		if(opts3 && opts3.questionText){ L.push(`所问之事：“${opts3.questionText}”`); }
		if(opts3 && opts3.castingCamp && opts3.castingCamp !== 'astrologer'){
			L.push(`起盘阵营：${opts3.castingCamp === 'querent' ? '问卜者中心（时地取问卜者）' : '时空中点（关系盘）'}`);
		}
		const ha = rad.hourAgreement;
		if(ha && ha.available){
			L.push(ha.agree ? ('时主与命主一致（正面根基确认）：' + ha.hits.map((h) => h.text).join('；')) : '时主与命主不合（仅失一佐证，不弃盘）。');
		}
		rad.considerations.items.forEach((c) => {
			const st = c.severity === 'unavailable' ? '不可用' : (c.hit ? (c.mitigated ? '命中·已救济' : '命中') : '未命中');
			L.push(`- ${c.idx}. ${c.text_zh}：${st}${c.hit && !c.mitigated && c.mitigable && (c.mitigatedBy || []).length ? `（可救济：${c.mitigatedBy.join('；')}）` : ''}`);
		});
	}
	// [Almuten] 逐度总管(命度/事项宫头)。
	if(j.almuten && (j.almuten.asc || j.almuten.quesitedCusp)){
		L.push('[Almuten]');
		if(j.almuten.asc){ L.push(`命度 almuten＝${j.almuten.asc.winners.map(cn).join('/')}（${Object.keys(j.almuten.asc.scores).map((k) => `${cn(k)}${j.almuten.asc.scores[k]}`).join('、')}）`); }
		if(j.almuten.quesitedCusp){ L.push(`事项宫头 almuten＝${j.almuten.quesitedCusp.winners.map(cn).join('/')}（${Object.keys(j.almuten.quesitedCusp.scores).map((k) => `${cn(k)}${j.almuten.quesitedCusp.scores[k]}`).join('、')}）`); }
		if(j.moonPromotion && j.moonPromotion.promote){ L.push(`月亮升格条件命中：${j.moonPromotion.reasons.join('、')}。`); }
	}
	// [映点对映点] 全盘表——[H8] 与 UI 同源(antisciaTable.js 单实现;orb 同吃 opts.antisciaOrb,缺省 1°=旧值)。
	if(j.facts && j.facts.planets){
		const aorb = (j.facts.opts && typeof j.facts.opts.antisciaOrb === 'number') ? j.facts.opts.antisciaOrb : 1;
		const rows = buildAntisciaTable(j.facts, aorb).map((r) => `- ${r.cn}：映点 ${r.antiText.replace(' ', '')}${r.antiHits.length ? '（命中 ' + r.antiHits.join('、') + '≈合）' : ''}；对映点 ${r.contraText.replace(' ', '')}${r.contraHits.length ? '（命中 ' + r.contraHits.join('、') + '≈冲）' : ''}`);
		if(rows.length){
			L.push('[映点对映点]');
			L.push(`映点=关于至点轴镜像(180°−λ)力≈合相;对映点(360°−λ)=映点之冲;命中≤${aorb}°计入判读。`);
			rows.forEach((r) => L.push(r));
		}
	}
	// [行星时] 日主/时主/象征。
	if(j.facts && (j.facts.meta.dayRuler || j.hourRuler)){
		L.push('[行星时]');
		L.push(`日主星＝${cn(j.facts.meta.dayRuler)}；当前时主星＝${cn(j.hourRuler)}${PLANETARY_HOURS[j.hourRuler] ? `；本时象征：${PLANETARY_HOURS[j.hourRuler].join(' / ')}` : ''}`);
		// [H9] 全表两行(迦勒底序,昼 12+夜 12;与 UI 行星时表同法)。
		if(j.facts.meta.dayRuler){
			const SEQ = ['saturn', 'jupiter', 'mars', 'sun', 'venus', 'mercury', 'moon'];
			const d0 = SEQ.indexOf(j.facts.meta.dayRuler);
			if(d0 >= 0){
				const row = (base) => Array.from({ length: 12 }, (_, i) => cn(SEQ[(d0 + base + i) % 7]).replace('星', '')).join(' ');
				L.push(`昼时序（日出起）：${row(0)}`);
				L.push(`夜时序（日落起）：${row(12)}`);
			}
		}
	}
	// [尊贵明细] 逐星必然尊贵 token+计分;lilly 满分表另段(仅该档)。
	if(j.facts && j.facts.planets){
		const SEVEN = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
		L.push('[尊贵明细]');
		SEVEN.filter((k) => j.facts.planets[k]).forEach((k) => {
			const p = j.facts.planets[k];
			L.push(`- ${cn(k)}：${(SIGNS[p.sign] || {}).cn || p.sign}${p.signlon !== undefined ? p.signlon.toFixed(1) + '°' : ''}，${(p.selfDignity && p.selfDignity.length) ? clsDignCn(p.selfDignity) : (p.peregrine ? '游走' : '无主尊贵')}，计分 ${p.dignityScore > 0 ? '+' : ''}${p.dignityScore}`);
		});
		const accKeys = Object.keys(j.conditions || {}).filter((k) => j.conditions[k] && j.conditions[k].accidental);
		if(accKeys.length){
			L.push('[偶然尊贵满分表]');
			accKeys.forEach((k) => {
				const a = j.conditions[k].accidental;
				L.push(`- ${cn(k)} 合计 ${a.total > 0 ? '+' : ''}${a.total}：${a.items.map((it) => it.text_zh).join('；')}`);
			});
		}
	}
	// ── [H9] 官方 gap 八项补齐(只加新段;段头同步登记 AI_EXPORT_PRESET_SECTIONS.horary) ──
	// [断法要点] 题型判断重点+典型吉凶徵。
	{
		const g = getQuestionGuide(j.category);
		if(g){
			L.push('[断法要点]');
			L.push(`${g.title}：${g.focus}`);
			L.push(`吉徵：${g.yes}；凶徵：${g.no}`);
		}
	}
	// [六类问法] Query I–VI 全量(此前主链只推 ①②③,④方位⑤应期⑥结局恒缺)。
	if(j.queries){
		const q = j.queries;
		L.push('[六类问法]');
		L.push(`① 能否成事：${q.canHappen ? q.canHappen.text : '—'}`);
		L.push(`② 事情好坏：${q.goodEvil ? q.goodEvil.text : '—'}`);
		L.push(`③ 消息真假：${q.reportTrue ? q.reportTrue.text : '—'}`);
		L.push(`④ 何处何向：${q.where ? `${q.where.dir}（${q.where.terrain}），${q.where.distance}` : '—'}`);
		L.push(`⑤ 何时：${q.when ? q.when.text : '—'}`);
		L.push(`⑥ 结局如何：${q.outcome ? q.outcome.text : '—'}`);
	}
	// [恒星会合] 前端精选表+后端实测(徵象星三键;两套口径并列)。
	if((j.fixedStars && j.fixedStars.length) || (j.backendStars && Object.keys(j.backendStars).length)){
		L.push('[恒星会合]');
		(j.fixedStars || []).forEach((s) => {
			L.push(`- ${s.point} 会合 ${s.star}（${s.meaning}）${s.royal ? '·王者' : ''}${s.nature === 'caution' ? '·凶性' : '·增益'}`);
		});
		if(j.backendStars && j.facts){
			const rows = [];
			[[sig.querentKey, '命主'], [sig.quesitedKey, '事项'], ['moon', '月亮']].forEach(([k, label]) => {
				const pp = k && j.facts.planets[k];
				const hit = pp && j.backendStars[pp.chartId];
				if(hit && hit.length){ rows.push(`${label}·${cn(k)}：${hit.map((s) => `${s.cn || s.star}（差${s.orb.toFixed(1)}°)`).join('、')}`); }
			});
			if(rows.length){ L.push('后端实测（星历全表口径）：' + rows.join('；')); }
		}
	}
	// [同主一星] 命主=事主时的五法裁决(A-E;C 真查容纳/E almuten 拆分)。
	if(sig.sharedRuler){
		L.push('[同主一星]');
		L.push(`共用星＝${cn(sig.sharedRuler.planet)}${sig.sharedRuler.method ? '（法' + sig.sharedRuler.method + '）' : '（未选裁决法）'}`);
		if(sig.sharedRuler.note){ L.push(sig.sharedRuler.note); }
		if(sig.sharedRuler.almutenSplit){ L.push(`almuten 拆分：事项改由 ${cn(sig.sharedRuler.almutenSplit)} 代表`); }
	}
	// [自然象征] 该事项自然征象星完整词条。
	if(sig.natural){
		const ns = NATURAL_SIGNIFICATORS[sig.natural];
		if(ns){
			L.push('[自然象征]');
			L.push(`${ns.cn} ${ns.glyph}：人物＝${(ns.persons || []).join('、')}`);
			L.push(`事物＝${(ns.things || []).join('、')}${ns.note ? '；' + ns.note : ''}`);
		}
	}
	// [盗窃研判] 11 步流程(theft 类才有)。
	if(j.theft && j.theft.steps && j.theft.steps.length){
		L.push('[盗窃研判]');
		L.push(`失主＝命主＋月亮；盗贼＝7宫主 ${cn(j.theft.thief)}；赃物＝2宫主 ${cn(j.theft.obj)}；藏匿地＝4宫。`);
		j.theft.steps.forEach((s) => L.push(`- ${s.label}：${s.text}`));
	}
	// [应期修正链] timingModifiers/secondLaw/换座副应期/留驻(有料才产段)。
	if(j.timing && (j.timing.modifiers || j.timing.secondLaw || j.timing.signChange || j.timing.stationNote)){
		L.push('[应期修正链]');
		(j.timing.modifiers || []).forEach((m) => L.push('- ' + m));
		if(j.timing.adjustedQuantity !== undefined){ L.push(`修正后数目：约 ${j.timing.adjustedQuantity} ${j.timing.unit}`); }
		if(j.timing.secondLaw){ L.push('- ' + j.timing.secondLaw.text); }
		if(j.timing.signChange){ L.push(`- 副应期（换座）：入相星距出本座 ${j.timing.signChange.deg}°，按当前速度约 ${j.timing.signChange.days} 天后换座（事态换阶段）`); }
		if(j.timing.stationNote){ L.push('- ' + j.timing.stationNote); }
	}
	// ── [H4a 金矿] 两新段(只加新段;段头已登记 AI_EXPORT_PRESET_SECTIONS.horary) ──
	// [围攻详断] 后端 surround.besiegement 十六式(凶围/围荣/围耀+协防+凶级);此前该表零消费。
	if(j.besiegement && j.besiegement.length){
		L.push('[围攻详断]');
		j.besiegement.forEach((b) => {
			const bs = (b.besiegers || []).map((x) => `${clsPlanetCn(x.id)}（${ASPECT_CN[Math.abs(x.aspect)] || (Math.abs(x.aspect) + '°')} 差${typeof x.delta === 'number' ? x.delta.toFixed(1) : '—'}°${x.retro ? '·逆' : ''}）`).join('＋');
			const df = (b.defense || []).map((d) => `${clsPlanetCn(d.id)}（${ASPECT_CN[Math.abs(d.aspect)] || (Math.abs(d.aspect) + '°')}解${clsPlanetCn(d.against)}侧${d.strong ? '·有力' : ''}）`).join('、');
			L.push(`- ${clsPlanetCn(b.target)} ${b.kind || '围攻'}（${b.nature || ''}${b.severe ? '·重' : ''}${b.targetRetro ? '·被围者逆行' : ''}）：${bs}${df ? '；协防：' + df : ''}`);
		});
	}
	// [月亮实测相位] 后端 immediateAsp 权威源(按紧密度排序)+月亮本座终局相位(真计算)。
	if((j.moonStory && j.moonStory.immediate && j.moonStory.immediate.length) || j.moonFinal){
		L.push('[月亮实测相位]');
		if(j.moonStory && j.moonStory.immediate && j.moonStory.immediate.length){
			L.push('后端实测紧密相位（按距精确度序·权威源）：' + j.moonStory.immediate.slice(0, 4).map((a) => `${cn(a.other)} ${ASPECT_CN[a.angle] || a.angle + '°'} 差${a.orb.toFixed(1)}°`).join('；'));
		}
		if(j.moonFinal){
			L.push(`月亮本座终局相位：与 ${cn(j.moonFinal.other)} 成${ASPECT_CN[j.moonFinal.angle] || j.moonFinal.angle + '°'}（约 ${j.moonFinal.tDays} 天后精确）→ 事之收尾${j.moonFinal.angle === 90 || j.moonFinal.angle === 180 ? '偏凶' : '偏吉'}。`);
		}
	}
	// 扩展点集(lots_set=core15 档才有;classical 默认无=零回归)。
	if(j.lots && j.lots.extended && j.lots.extended.length){
		L.push('[阿拉伯点全集]');
		j.lots.extended.forEach((l) => L.push(`- ${l.cn}：${l.signCn}座 ${l.signlon.toFixed(1)}°${l.dispCn ? '·定位星' + l.dispCn : ''}（${l.use}）`));
	}
	// [YA v42] +古典接纳:chart.receptions/chart.mutuals(古典 tab 已显示,与「占星·古典」同一套后端数据)
	// 此前被判词-only 快照丢弃。chart 为可选第二参:旧调用不传 → 不产段(零回归);
	// 传入处 = HoraryJudgment.saveSnap(props.chart) / aiAnalysisContext.regenerateHorarySnapshot(fetch 的 chart)。
	const recp = (chart && chart.receptions) || {};
	const mut = (chart && chart.mutuals) || {};
	const recNormal = recp.normal || [];
	const recAbnormal = recp.abnormal || [];
	const mutNormal = mut.normal || [];
	const mutAbnormal = mut.abnormal || [];
	if(recNormal.length || recAbnormal.length || mutNormal.length || mutAbnormal.length){
		L.push('[古典接纳]');
		if(recNormal.length || recAbnormal.length){
			L.push('◆ 接纳关系');
			recNormal.forEach((it) => L.push(`- 正接纳：${clsPlanetCn(it.beneficiary)} 被 ${clsPlanetCn(it.supplier)} 接纳（${clsDignCn(it.supplierRulerShip)}）${clsHasRefuse(it.supplierRulerShip) ? ' · 拒绝' : ''}`));
			recAbnormal.forEach((it) => L.push(`- 邪接纳（借次尊贵/弱位）：${clsPlanetCn(it.beneficiary)} 被 ${clsPlanetCn(it.supplier)} 接纳（${clsDignCn(it.supplierRulerShip)}）${clsHasRefuse(it.supplierRulerShip) ? ' · 拒绝' : ''}`));
		}
		if(mutNormal.length || mutAbnormal.length){
			L.push('◆ 互容');
			mutNormal.forEach((m) => L.push(`- 正互容：${clsPlanetCn((m.planetA || {}).id)}（${clsDignCn((m.planetA || {}).rulerShip)}） 与 ${clsPlanetCn((m.planetB || {}).id)}（${clsDignCn((m.planetB || {}).rulerShip)}） 互容`));
			mutAbnormal.forEach((m) => L.push(`- 邪互容：${clsPlanetCn((m.planetA || {}).id)}（${clsDignCn((m.planetA || {}).rulerShip)}） 与 ${clsPlanetCn((m.planetB || {}).id)}（${clsDignCn((m.planetB || {}).rulerShip)}） 互容`));
		}
		L.push(`三分制口径：${j.tripSystem === 'dorothean' ? '三主制（含参与主，水象日主取金星）' : '简约制（水象三分主取火星）'}`);
		L.push('正接纳＝居对方庙旺等强位可化解凶相；互容尤吉；供方落陷弱位标「拒绝」。');
	}
	// [YA v42] +征象力量:各征象星尊贵力量分(征象 tab 已显示:力量分/状态行/逐条证词)此前不入快照;
	// 取数与 UI 同源(j.conditions 的 score/findings.text_zh + facts.planets 状态)。
	const conds = j.conditions || {};
	const condKeys = Object.keys(conds);
	if(condKeys.length){
		L.push('[征象力量]');
		L.push('入庙旺=有力；落陷/游走/燃烧/逆行=无力或受损；角宫快而有力，果宫弱而拖延。');
		condKeys.forEach((k) => {
			const c = conds[k] || {};
			const role = k === sig.querentKey ? '（问卜者）' : (k === sig.quesitedKey ? '（' + (sig.quesitedLabel || '事项') + '）' : (k === 'moon' ? '（共同征象）' : ''));
			const score = c.score || 0;
			L.push(`◆ ${cn(k)}${role}：力量 ${score > 0 ? '+' : ''}${score}`);
			const state = planetPlainState(j.facts, k);
			if(state) L.push(state);
			(c.findings || []).forEach((f) => L.push('- ' + (f.text_zh || '')));
		});
	}
	return L.join('\n');
}

export default buildHorarySnapshot;
