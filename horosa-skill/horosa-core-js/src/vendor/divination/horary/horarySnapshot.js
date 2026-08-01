// divination/horary/horarySnapshot.js
// 把卜卦判断结果拼成 AI 快照文本（[小节标题] + markdown 列表），供 saveModuleAISnapshot('horary', ...)。
import { PLANETS } from '../data/planets.js';
import { SIGNS, signOfLon } from '../data/signs.js';
import { PLANETARY_HOURS } from '../data/planetaryHours.js';
import { CATEGORY_DEF } from './significators.js';
import { schoolOf } from './horarySchools.js';
import * as AstroText from '../../../constants/AstroText.js';

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
	L.push(`${sig.quesitedLabel || '事项'} = ${sig.quesitedHouse ? sig.quesitedHouse + '宫主 ' : ''}${cn(sig.quesitedKey)}${sig.natural ? '（自然征象星 ' + cn(sig.natural) + '）' : ''}`);
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
	L.push('倾向：' + j.verdict.summary);
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
	// [映点对映点] 全盘表(映点=180−λ≈合;对映点=360−λ≈冲;命中≤1°标注)。
	if(j.facts && j.facts.planets){
		const SEVEN = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
		const f = j.facts;
		const dist = (a, b) => { const d = Math.abs(((a - b) % 360 + 360) % 360); return Math.min(d, 360 - d); };
		const rows = [];
		SEVEN.filter((k) => f.planets[k]).forEach((k) => {
			const lam = f.planets[k].lon;
			const anti = ((180 - lam) % 360 + 360) % 360;
			const contra = ((360 - lam) % 360 + 360) % 360;
			const hitOf = (lon) => {
				const hits = [];
				SEVEN.forEach((o) => { if(o !== k && f.planets[o] && dist(lon, f.planets[o].lon) <= 1) hits.push(cn(o)); });
				if(f.meta.ascLon != null && dist(lon, f.meta.ascLon) <= 1) hits.push('命度');
				if(f.meta.mcLon != null && dist(lon, f.meta.mcLon) <= 1) hits.push('天顶');
				return hits;
			};
			const fmt = (l) => `${(SIGNS[signOfLon(l)] || {}).cn || ''}${(((l % 30) + 30) % 30).toFixed(1)}°`;
			rows.push(`- ${cn(k)}：映点 ${fmt(anti)}${hitOf(anti).length ? '（命中 ' + hitOf(anti).join('、') + '≈合）' : ''}；对映点 ${fmt(contra)}${hitOf(contra).length ? '（命中 ' + hitOf(contra).join('、') + '≈冲）' : ''}`);
		});
		if(rows.length){
			L.push('[映点对映点]');
			L.push('映点=关于至点轴镜像(180°−λ)力≈合相;对映点(360°−λ)=映点之冲;命中≤1°计入判读。');
			rows.forEach((r) => L.push(r));
		}
	}
	// [行星时] 日主/时主/象征。
	if(j.facts && (j.facts.meta.dayRuler || j.hourRuler)){
		L.push('[行星时]');
		L.push(`日主星＝${cn(j.facts.meta.dayRuler)}；当前时主星＝${cn(j.hourRuler)}${PLANETARY_HOURS[j.hourRuler] ? `；本时象征：${PLANETARY_HOURS[j.hourRuler].join(' / ')}` : ''}`);
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
