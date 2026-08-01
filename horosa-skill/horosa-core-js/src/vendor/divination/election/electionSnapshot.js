// divination/election/electionSnapshot.js
// 择日判断 → AI 快照文本，供 saveModuleAISnapshot('election', ...)。
import { essentialMatrix, accidentalTable, receptionReport } from './dignityReport.js';
import { PLANETS } from '../data/planets.js';

const cnP = (k) => (PLANETS[k] || {}).cn || k;

export function buildElectionSnapshot(j){
	if(!j) return '';
	const L = [];
	L.push('[起盘信息]');
	L.push(`用事类型：${j.topic.cn}`);
	// 西方子流派:仅非默认档写入(默认现代主流=快照文本与既往逐字一致)。
	if(j.westSchool && j.westSchool.id && j.westSchool.id !== 'modern_main'){
		L.push(`西方流派：${j.westSchool.cn}`);
	}
	L.push(`起盘时刻：${j.castMoment}`);
	// 流派口径(界/三分/orb/空亡/用星/宿锚/点法)——使 AI 判读有据。
	if(j.calibre && j.calibre.summary && j.calibre.summary.length){
		L.push('[流派口径]');
		j.calibre.summary.forEach((s) => L.push('- ' + s));
	}
	L.push('[总评]');
	L.push(`${j.overall.score}/100　${j.overall.gradeCn}`);
	L.push(j.overall.headline);
	L.push(j.overall.no_perfect_chart_note);
	L.push('[红线]');
	if(j.hard_flags.length){ j.hard_flags.forEach((f) => L.push(`- [${f.severity}] ${f.message}`)); }
	else L.push('无红线命中。');
	L.push('[分项]');
	L.push('| 项 | 分 | 要点 |');
	L.push('| --- | --- | --- |');
	j.sections.forEach((s) => {
		const pts = (s.findings || []).map((f) => f.text_zh || f.message).join('；') || '—';
		L.push(`| ${s.title} | ${s.score}/100 | ${pts} |`);
	});
	if(j.topicPack && j.topicPack.items && j.topicPack.items.length){
		L.push('[用事专属]');
		L.push(`（满足 ${j.topicPack.passed}/${j.topicPack.total}）`);
		j.topicPack.items.forEach((it) => L.push(`- ${it.pass ? '✓' : '✗'} ${it.kind === 'avoid' ? '忌' : '宜'}：${it.label}`));
		if(j.topicPack.notes) L.push('注：' + j.topicPack.notes);
	}
	// 尊贵强弱(本质小计+偶然合计+胜利星+接纳)——与右栏「尊贵强弱」页同源。
	if(j.facts){
		try{
			const eff = j.calibre && j.calibre.eff;
			const ess = essentialMatrix(j.facts, eff);
			const acc = accidentalTable(j.facts, eff);
			const accBy = {}; acc.forEach((r) => { accBy[r.key] = r.total; });
			L.push('[尊贵强弱]');
			L.push('| 星 | 落座 | 本质小计 | 偶然合计 |');
			L.push('| --- | --- | --- | --- |');
			ess.forEach((r) => {
				L.push(`| ${r.cn} | ${r.signCn} | ${r.score > 0 ? '+' : ''}${r.score} | ${accBy[r.key] !== undefined ? (accBy[r.key] > 0 ? '+' : '') + accBy[r.key] : '—'} |`);
			});
			const af = j.facts.almuten;
			if(af && af.winners && af.winners.length){
				L.push(`胜利星：${af.winners.map(cnP).join('、')}（${af.best} 分·${af.points.length === 5 ? '五' : '四'}命点）`);
			}
			receptionReport(j.facts).forEach((r) => L.push(`- 接纳：${r.text}`));
		}catch(e){ /* noop */ }
	}
	// 阿拉伯点全谱(福/精神+分科;用事关联点标注)。
	if(j.facts && j.facts.lots && (j.facts.lots.hermetic.length || j.facts.lots.topical.length)){
		const topicIds = j.facts.topicLotIds || [];
		L.push('[阿拉伯点]');
		L.push('| 点 | 位置 | 宫 | 定位星 |');
		L.push('| --- | --- | --- | --- |');
		j.facts.lots.hermetic.concat(j.facts.lots.topical).forEach((r) => {
			L.push(`| ${r.cn}${topicIds.indexOf(r.id) >= 0 ? '（本用事）' : ''} | ${r.signCn} ${r.signlon}° | ${r.house || '—'} | ${r.dispositorCn} |`);
		});
	}
	// 择前考量(命中项+可判性)。
	if(j.considerations){
		const c = j.considerations;
		L.push('[择前考量]');
		L.push(`可判性：${c.verdictCn}（命中 ${c.hitCount} 条）`);
		c.lilly.concat(c.ramesey).concat(c.bonatti).forEach((it) => {
			if(it.hit && it.severity !== 'info') L.push(`- ✗ ${it.title}${it.detail ? `（${it.detail}）` : ''}`);
		});
		if(c.astrologer7th.length) L.push('⚠ 第 7 宫＝占星师受扰：判读可靠性存疑（不计入择吉分）。');
	}
	if(j.crisis && j.crisis.text){
		L.push('[危象日参照]');
		L.push(j.crisis.text);
	}
	L.push('[应期]');
	if(j.timing && j.timing.length){
		L.push('| 月相 | 目标 | 误差 |');
		L.push('| --- | --- | --- |');
		j.timing.forEach((t) => L.push(`| 月亮 ${t.angle}° | ${t.otherCn} | 误差 ${t.orb != null ? Number(t.orb).toFixed(1) : '-'}°，越紧越近发动 |`));
	}else{
		L.push('月亮无紧密相位，应期不显。');
	}
	if(j.natal && j.natal.available){
		L.push('[本命合参]');
		j.natal.notes.forEach((n) => L.push(`- ${n.pol === 'positive' ? '✓' : (n.pol === 'negative' ? '✗' : '·')} ${n.text}`));
	}
	if(j.mundane && j.mundane.available){
		L.push('[时势合参]');
		j.mundane.notes.forEach((n) => L.push(`- ${n.pol === 'positive' ? '✓' : (n.pol === 'negative' ? '✗' : '·')} ${n.text}`));
	}
	L.push('[建议]');
	j.recommendations.forEach((r) => L.push('- ' + r));
	return L.join('\n');
}

export default buildElectionSnapshot;
