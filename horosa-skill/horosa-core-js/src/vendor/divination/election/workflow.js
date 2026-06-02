// divination/election/workflow.js
// 消去法工作流（择日清单 §9）：在时间窗内生成候选时刻 → 逐一排盘评分 → 排名择优。
// 纯逻辑：候选生成 + 排名；实际排盘 fetch 在 ElectionMain 里做（它持有 fetchChart）。

function pad(n){ return n < 10 ? '0' + n : '' + n; }

// 生成候选 DateTime 列表。mode='hours'（同日逐时）| 'days'（逐日同时刻）。
export function generateCandidates(baseDt, mode, opts){
	opts = opts || {};
	const list = [];
	if(!baseDt || !baseDt.clone){ return list; }
	if(mode === 'days'){
		const n = opts.days || 14;
		for(let d = 0; d < n; d++){
			const dt = baseDt.clone();
			if(d > 0){ dt.addDate(d); }
			list.push({ dt, label: `${pad(dt.month)}/${pad(dt.date)} ${pad(dt.hour)}:${pad(dt.minute)}`, idx: d });
		}
	}else{
		const start = opts.startHour !== undefined ? opts.startHour : 7;
		const end = opts.endHour !== undefined ? opts.endHour : 22;
		const step = opts.stepHours || 1;
		let i = 0;
		for(let h = start; h <= end; h += step){
			const dt = baseDt.clone();
			dt.setTime(h, 0, 0);
			list.push({ dt, label: `${pad(h)}:00`, idx: i++ });
		}
	}
	return list;
}

// 排名：分高者先；同分时红线少者先（严重 > 较重），再按时间先后。
// （坏日子里各时刻常同被压到 0 分，用红线数作决胜，扫描仍有意义。）
export function rankResults(rows){
	return (rows || []).filter(Boolean).slice().sort((a, b) =>
		(b.score - a.score) || ((a.crit || 0) - (b.crit || 0)) || ((a.high || 0) - (b.high || 0)) || (a.idx - b.idx));
}

// 候选 → 推荐文案（取前几名 + 利弊）
export function buildScanRecommendation(ranked){
	if(!ranked || !ranked.length) return '未取得候选评分。';
	const best = ranked[0];
	return `窗口内较优：${best.label}（${best.score} 分 · ${best.grade}）${best.crit ? '；注意仍含严重红线' : (best.high ? '；尚有较重代价' : '')}。`;
}

export default generateCandidates;
