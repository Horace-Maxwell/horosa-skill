// 日子馆 AI 挂载/导出快照 builder（纯函数）。挂当事人八字 + 个性化吉日榜，供 AI 个性化择日报告。
import { EVENT_KEY_TO_CATEGORY } from './tongshuData.js';
import { hehunPair } from './riziEngine.js';

const ROLE_LABEL = { self: '本人', spouse: '配偶', family: '家人' };

export function buildRiziSnapshotText({ event, year, persons, result }) {
	if (!result || !result.list) { return ''; }
	const cat = EVENT_KEY_TO_CATEGORY[event] || { label: event };
	const lines = [];
	lines.push('[日子馆·个性化择日]');
	lines.push(`事项：${cat.label}`);
	lines.push(`年份：${year}`);

	const valid = (persons || []).filter((p)=> p && p.bazi);
	if (valid.length) {
		lines.push('');
		lines.push('[当事人八字]');
		valid.forEach((p)=>{
			const b = p.bazi;
			lines.push(`${ROLE_LABEL[p.role] || p.role}${p.name ? '（' + p.name + '）' : ''}：${b.yearGZ}年 属${b.shengxiao}｜日主${b.dayGan}${b.dayGanWx}（${b.verdict}）｜喜用${(b.xi || []).join('')}｜忌${(b.ji || []).join('')}｜年纳音${b.nayinYear}`);
		});
		// 夫妻合婚（本人+配偶）。
		const self = valid.find((p)=> p.role === 'self');
		const spouse = valid.find((p)=> p.role === 'spouse');
		if (self && spouse) {
			const hh = hehunPair(self.bazi, spouse.bazi);
			if (hh) { lines.push(`合婚：本人×配偶 年命${hh.verdict}（纳音 ${hh.nayinA}／${hh.nayinB}）`); }
		}
	}

	lines.push('');
	lines.push(`[个性化吉日榜 Top ${result.list.length}／全年候选 ${result.count}]`);
	result.list.forEach((d, i)=>{
		lines.push(`${i + 1}. ${d.ymd} 星期${d.week} ${d.lunar} ${d.ganzhi}日 ${d.jianchu}·${d.huangdao}（综分${d.score}）`);
		const tong = (d.tongshuReasons || []).map((r)=> r.text).join('、');
		if (tong) { lines.push(`　通书：${tong}`); }
		(d.perPerson || []).forEach((pp)=>{
			const rs = (pp.reasons || []).map((r)=> r.text).join('、');
			if (rs) { lines.push(`　${ROLE_LABEL[pp.role] || pp.role}${pp.name ? '(' + pp.name + ')' : ''}：${rs}`); }
		});
	});

	lines.push('');
	lines.push('[方法说明]');
	lines.push('在通书基线（事项宜日+建除吉位+黄道-关键凶煞）之上，叠加各命主八字：冲本命年支者淘汰，日柱五行生扶用神者加分、属忌神者扣分；多命主取交集。须与老黄历完整日课合参。');
	return lines.join('\n');
}

export default buildRiziSnapshotText;
