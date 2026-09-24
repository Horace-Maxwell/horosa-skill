// 日子馆 AI 挂载/导出快照 builder（纯函数）。挂当事人八字 + 个性化吉日榜，供 AI 个性化择日报告。
import { EVENT_KEY_TO_CATEGORY } from './tongshuData.js';
import { hehunPair } from './riziEngine.js';
import { buildHuangliSnapshotByDate } from './huangliSnapshot.js';   // [Q-457/T-420] 所选吉日完整日课(候选段)

const ROLE_LABEL = { self: '本人', spouse: '配偶', family: '家人' };

export function buildRiziSnapshotText({ event, year, persons, result, selectedYmd }) {
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
		// [Q-457/T-420] 逐命主得分与「本命平和」中性态:页面详情区逐命主写「属X · 得分 N」,无理由时
		// 明写「本命平和·无冲无扶」;快照此前只在**有理由时**写一行理由 —— 中性命主整行省略,
		// AI 分不清某命主是「算过=中性」还是「根本没算」,也看不到各人得分权重。与页面同一口径逐人成行。
		(d.perPerson || []).forEach((pp)=>{
			const rs = (pp.reasons || []).map((r)=> r.text).join('、');
			const who = `${ROLE_LABEL[pp.role] || pp.role}${pp.name ? '(' + pp.name + ')' : ''}`;
			const head = `${who}${pp.shengxiao ? ' 属' + pp.shengxiao : ''}${pp.score !== undefined && pp.score !== null ? ' 得分' + pp.score : ''}`;
			lines.push(`　${head}：${rs || '本命平和·无冲无扶'}`);
		});
	});

	// [Q-457/T-420] 所选吉日的完整老黄历日课:页面详情区有「完整老黄历日课」卡,快照此前一字不带
	// (黄历聚合导出里的「老黄历」子源取的是老黄历页自身所选日期,与日子馆选中的吉日无关)→ AI 拿不到
	// 所选吉日的宜忌与时辰吉凶。按裁决作**默认关候选段**(段名已登记 preset 与 DEFAULT_OFF)。
	// 内层段头降为 ◆ 行,使本段在段切分下仍是单段。
	const selDay = selectedYmd || (result.list[0] ? result.list[0].ymd : '');
	const _dp = `${selDay}`.split('-').map((x)=> parseInt(x, 10));
	if (_dp.length === 3 && _dp.every((n)=> !isNaN(n))) {
		const dayTxt = `${buildHuangliSnapshotByDate(_dp[0], _dp[1], _dp[2]) || ''}`.trim();
		if (dayTxt) {
			lines.push('');
			lines.push('[所选吉日·完整日课]');
			lines.push(`日期：${selDay}`);
			dayTxt.split('\n').forEach((l)=>{
				const m = `${l}`.match(/^\[(.+)\]$/);
				lines.push(m ? `◆ ${m[1]}` : l);
			});
		}
	}

	lines.push('');
	lines.push('[方法说明]');
	lines.push('在通书基线（事项宜日+建除吉位+黄道-关键凶煞）之上，叠加各命主八字：冲本命年支者淘汰，日柱五行生扶用神者加分、属忌神者扣分；多命主取交集。须与老黄历完整日课合参。');
	return lines.join('\n');
}

export default buildRiziSnapshotText;
