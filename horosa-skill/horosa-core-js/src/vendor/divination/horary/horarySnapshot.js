// divination/horary/horarySnapshot.js
// 把卜卦判断结果拼成 AI 快照文本（[小节标题] + markdown 列表），供 saveModuleAISnapshot('horary', ...)。
import { PLANETS } from '../data/planets.js';
import { CATEGORY_DEF } from './significators.js';

function cn(k){ return (PLANETS[k] || {}).cn || k || '—'; }
const ASPECT_CN = { 0: '合相', 60: '六合', 90: '四分(刑)', 120: '三合', 180: '对分(冲)' };

export function buildHorarySnapshot(j){
	if(!j) return '';
	const L = [];
	const sig = j.significators;
	L.push('[起卦信息]');
	L.push(`问题类别：${(CATEGORY_DEF[j.category] && CATEGORY_DEF[j.category].quesitedLabel) || j.category}`);
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
		j.allAspects.forEach((a) => L.push(`- ${cn(a.a)} ${ASPECT_CN[a.angle] || a.angle + '°'} ${cn(a.b)}（${a.applying ? '入相/将成' : '出相/已过'}，差 ${a.orb.toFixed(1)}°${a.exact ? '·正相位' : ''}）`));
	}
	L.push('[裁决]');
	L.push('倾向：' + j.verdict.summary);
	if(j.verdict.positive.length) L.push('有利证词：' + j.verdict.positive.map((p) => p.text).join('；'));
	if(j.verdict.negative.length) L.push('不利证词：' + j.verdict.negative.map((n) => n.text).join('；'));
	L.push(`Query：①能否成事=${j.queries.canHappen.text} ②好坏=${j.queries.goodEvil.text} ③真假=${j.queries.reportTrue.text}`);
	L.push('[应期方位]');
	L.push((j.timing ? j.timing.text : '无准确相位，应期不定') + '；方位：' + (j.queries.where ? `${j.queries.where.dir}（${j.queries.where.terrain}），${j.queries.where.distance}` : '—'));
	if(j.describe && j.describe.length){
		L.push('[描述]');
		j.describe.forEach((d) => L.push(`- ${d.role}：${d.title}${d.temper ? '（' + d.temper + '）' : ''} ${d.body}`));
	}
	L.push('（裁决只呈现证据与倾向，不替用户下命定结论。）');
	return L.join('\n');
}

export default buildHorarySnapshot;
