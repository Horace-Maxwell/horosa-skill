// divination/election/electionSnapshot.js
// 择日判断 → AI 快照文本，供 saveModuleAISnapshot('election', ...)。
export function buildElectionSnapshot(j){
	if(!j) return '';
	const L = [];
	L.push('[起盘信息]');
	L.push(`用事类型：${j.topic.cn}`);
	L.push(`起盘时刻：${j.castMoment}`);
	L.push('[总评]');
	L.push(`${j.overall.score}/100　${j.overall.gradeCn}`);
	L.push(j.overall.headline);
	L.push(j.overall.no_perfect_chart_note);
	L.push('[红线]');
	if(j.hard_flags.length){ j.hard_flags.forEach((f) => L.push(`- [${f.severity}] ${f.message}`)); }
	else L.push('无红线命中。');
	L.push('[分项]');
	j.sections.forEach((s) => {
		L.push(`${s.title}（${s.score}/100）`);
		(s.findings || []).forEach((f) => L.push('  · ' + (f.text_zh || f.message)));
	});
	if(j.topicPack && j.topicPack.items && j.topicPack.items.length){
		L.push(`[用事专属]（满足 ${j.topicPack.passed}/${j.topicPack.total}）`);
		j.topicPack.items.forEach((it) => L.push(`- ${it.pass ? '✓' : '✗'} ${it.kind === 'avoid' ? '忌' : '宜'}：${it.label}`));
		if(j.topicPack.notes) L.push('注：' + j.topicPack.notes);
	}
	L.push('[建议]');
	j.recommendations.forEach((r) => L.push('- ' + r));
	return L.join('\n');
}

export default buildElectionSnapshot;
