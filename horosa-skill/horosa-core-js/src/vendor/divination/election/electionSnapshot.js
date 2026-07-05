// divination/election/electionSnapshot.js
// 择日判断 → AI 快照文本，供 saveModuleAISnapshot('election', ...)。
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
		L.push('[用事专属]');
		L.push(`（满足 ${j.topicPack.passed}/${j.topicPack.total}）`);
		j.topicPack.items.forEach((it) => L.push(`- ${it.pass ? '✓' : '✗'} ${it.kind === 'avoid' ? '忌' : '宜'}：${it.label}`));
		if(j.topicPack.notes) L.push('注：' + j.topicPack.notes);
	}
	if(j.crisis && j.crisis.text){
		L.push('[危象日参照]');
		L.push(j.crisis.text);
	}
	L.push('[应期]');
	if(j.timing && j.timing.length){
		j.timing.forEach((t) => L.push(`- 月亮 ${t.angle}° ${t.otherCn}（误差 ${t.orb != null ? Number(t.orb).toFixed(1) : '-'}°，越紧越近发动）`));
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
