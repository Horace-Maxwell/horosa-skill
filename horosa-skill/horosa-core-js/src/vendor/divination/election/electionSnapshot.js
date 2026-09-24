// divination/election/electionSnapshot.js
// 择日判断 → AI 快照文本，供 saveModuleAISnapshot('election', ...)。
import { essentialMatrix, accidentalTable, receptionReport } from './dignityReport.js';
import { PLANETS } from '../data/planets.js';
import { judgeReturnFacts } from './returnCharts.js';   // [Q-445] 回归盘利钝(与右栏合参卡三同源)

const cnP = (k) => (PLANETS[k] || {}).cn || k;

// extra(页面侧按需拉取物,无头链无):{ returnSet:{solar,lunar}, pdHits:[...] } → [回归与主限] 段(与右栏合参卡三同源)。
export function buildElectionSnapshot(j, extra){
	if(!j) return '';
	const ex = extra || {};
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
			// [Q-445/T-408] 五重矩阵逐项(庙/旺/三分/界/面/陷/弱/外来)由「本质小计」还原为明细,与右栏矩阵同列;偶然合计保留。
			L.push('（庙5 旺4 三分3 界2 面1／陷−5 弱−4 外来−5；三分「共」=共治分）');
			L.push('| 星 | 落座 | 庙 | 旺 | 三分 | 界 | 面 | 陷 | 弱 | 外来 | 本质小计 | 偶然合计 |');
			L.push('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |');
			const dot = (v) => (v ? '●' : '');
			ess.forEach((r) => {
				L.push(`| ${r.cn} | ${r.signCn}${r.signlon !== undefined ? ' ' + Math.floor(r.signlon) + '°' : ''} | ${dot(r.domicile)} | ${dot(r.exaltation)} | ${r.triplicity ? '●' : (r.triplicityPart ? '共' : '')} | ${dot(r.term)} | ${dot(r.face)} | ${dot(r.detriment)} | ${dot(r.fall)} | ${dot(r.peregrine)} | ${r.score > 0 ? '+' : ''}${r.score} | ${accBy[r.key] !== undefined ? (accBy[r.key] > 0 ? '+' : '') + accBy[r.key] : '—'} |`);
			});
			const af = j.facts.almuten;
			if(af && af.winners && af.winners.length){
				// [Q-445/T-408] Almuten Figuris 逐点计分矩阵(命点×七曜 + 合计),此前只有胜利星一行。
				const AF_SEVEN = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
				if(Array.isArray(af.points) && af.points.length){
					L.push(`Almuten Figuris（${af.points.length === 5 ? '五' : '四'}命点逐点计分）：`);
					L.push(`| 命点 | ${AF_SEVEN.map(cnP).join(' | ')} |`);
					L.push(`| --- | ${AF_SEVEN.map(() => '---').join(' | ')} |`);
					af.points.forEach((pt) => {
						L.push(`| ${pt.label} | ${AF_SEVEN.map((k) => ((pt.scores || {})[k] || '')).join(' | ')} |`);
					});
					L.push(`| 合计 | ${AF_SEVEN.map((k) => ((af.totals || {})[k] || '')).join(' | ')} |`);
				}
				L.push(`胜利星：${af.winners.map(cnP).join('、')}（${af.best} 分·${af.points.length === 5 ? '五' : '四'}命点）${af.winners.length > 1 ? '——并列时以得派/近角/近区分光决胜' : ''}`);
				(af.caveats || []).forEach((c) => L.push(`注：${c}`));
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
		// [Q-445/T-408] 未命中项(✓)与提示项(·)一并列出(与右栏三组清单同构),此前只列命中(✗)→ AI 不知哪些考量已过关。
		c.lilly.concat(c.ramesey).concat(c.bonatti).forEach((it) => {
			const info = it.severity === 'info';
			const mark = info ? '·' : (it.hit ? '✗' : '✓');
			L.push(`- ${mark} ${it.title}${it.detail ? `（${it.detail}）` : ''}`);
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
	// [Q-445/T-408] 合参「回归盘与主限」卡(页面按需拉取物;有数据才产段)。
	try{
		const rs = ex.returnSet;
		const pd = ex.pdHits;
		const rows = [];
		if(rs && rs.solar){ rows.push(...judgeReturnFacts('日返', rs.solar)); }
		if(rs && rs.lunar){ rows.push(...judgeReturnFacts('月返', rs.lunar)); }
		if(rows.length || (Array.isArray(pd) && pd.length)){
			L.push('[回归与主限]');
			rows.forEach((n) => L.push(`- ${n.pol === 'positive' ? '▲' : (n.pol === 'negative' ? '▼' : '·')} ${n.text}`));
			if(Array.isArray(pd) && pd.length){
				L.push(`择日日期前后主限命中（±240 日内最近 ${pd.length} 条）：`);
				pd.forEach((h) => L.push(`- ${h.date}（${h.deltaDays >= 0 ? '+' : ''}${h.deltaDays} 日）：${h.significator} ← ${h.promissor}${h.method ? `（${h.method}）` : ''}`));
			}
		}
	}catch(e){ /* noop */ }
	if(j.mundane && j.mundane.available){
		L.push('[时势合参]');
		j.mundane.notes.forEach((n) => L.push(`- ${n.pol === 'positive' ? '✓' : (n.pol === 'negative' ? '✗' : '·')} ${n.text}`));
	}
	L.push('[建议]');
	j.recommendations.forEach((r) => L.push('- ' + r));
	return L.join('\n');
}

export default buildElectionSnapshot;
