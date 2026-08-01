// 老黄历日课 AI 挂载/导出快照 builder（纯函数，jest 直测）。
// 「显示什么就导出什么」：全字段取自 buildHuangliDay 返回的 day 对象，不在此重算。
import { buildHuangliDay } from './huangliDay.js';

function joinArr(arr, sep = '、') {
	return (Array.isArray(arr) ? arr : []).filter(Boolean).join(sep);
}

export function buildHuangliSnapshotText(day) {
	if (!day || !day.lunar) { return ''; }
	const lines = [];

	lines.push('[起盘信息]');
	lines.push(`公历：${day.solar.ymd} 星期${day.solar.week}`);
	lines.push(`农历：${day.lunar.text}`);
	lines.push(`干支：${day.lunar.yearGZ}年 ${day.lunar.monthGZ}月 ${day.lunar.dayGZ}日`);
	lines.push(`生肖：${day.lunar.shengxiao}`);
	if (day.lunar.jieqi) { lines.push(`节气：${day.lunar.jieqi}${day.lunar.jieqiTime ? `（交节 ${day.lunar.jieqiTime}）` : '（当日交节）'}`); }
	if (joinArr(day.solar.festivals)) { lines.push(`节日：${joinArr(day.solar.festivals)}`); }

	lines.push('');
	lines.push('[今日宜忌]');
	lines.push(`宜：${joinArr(day.yi) || '（无）'}`);
	lines.push(`忌：${joinArr(day.ji) || '（无）'}`);

	lines.push('');
	lines.push('[值神值宿]');
	lines.push(`建除十二神：${day.jianchu.name}日`);
	lines.push(`黄黑道值神：${day.tianshen.name}（${day.tianshen.type}·${day.tianshen.luck}）`);
	lines.push(`二十八宿：${day.xiu.name}${day.xiu.zheng || ''}${day.xiu.animal || ''}（${day.xiu.xiang}·${day.xiu.luck}）`);
	if (day.nineStar) { lines.push(`九星值日：${day.nineStar.name}`); }
	lines.push(`纳音：${day.nayin}`);

	lines.push('');
	lines.push('[彭祖百忌]');
	lines.push(`${day.pengzu.gan}；${day.pengzu.zhi}`);

	lines.push('');
	lines.push('[吉神凶煞]');
	lines.push(`吉神宜趋：${joinArr(day.jishen) || '（无）'}`);
	lines.push(`凶煞宜忌：${joinArr(day.xiongsha) || '（无）'}`);

	lines.push('');
	lines.push('[冲煞·胎神·方位]');
	lines.push(`冲煞：冲${day.chong.shengxiao}（${day.chong.desc}）煞${day.chong.sha}`);
	lines.push(`胎神占方：${day.tai}`);
	lines.push(`喜神：${day.positions.xi}　福神：${day.positions.fu}　财神：${day.positions.cai}`);
	lines.push(`阳贵：${day.positions.yangGui}　阴贵：${day.positions.yinGui}`);
	if (day.lu) { lines.push(`日禄：${day.lu}`); }

	// 时辰吉凶（取原 13 段，早/晚子时合并为「子时」展示不影响真值）。
	if (Array.isArray(day.times) && day.times.length) {
		lines.push('');
		lines.push('[时辰吉凶]');
		lines.push('| 时辰 | 时段 | 吉凶 | 宜 |');
		lines.push('| --- | --- | --- | --- |');
		day.times.forEach((t)=>{
			lines.push(`| ${t.ganzhi} | ${t.range} | ${t.luck || ''} | ${joinArr(t.yi.slice(0, 4)) || '—'} |`);
		});
	}

	const extra = [];
	if (day.hou) { extra.push(`物候：${day.hou}`); }
	if (day.liuyao) { extra.push(`六曜：${day.liuyao}`); }
	if (day.yuexiang) { extra.push(`月相：${day.yuexiang}`); }
	if (day.shujiu) { extra.push(`数九：${day.shujiu}`); }
	if (day.fu) { extra.push(`三伏：${day.fu}`); }
	if (extra.length) {
		lines.push('');
		lines.push('[物候·六曜·数九三伏]');
		lines.push(extra.join('　'));
	}

	// 年神方位（内部 zeri.yearGods）。
	const yg = day.yearGods;
	if (yg && yg.taisui) {
		lines.push('');
		lines.push('[流年年神方位]');
		lines.push(`太岁：${yg.taisui.dir}（${yg.taisui.zhi}）　岁破：${yg.suipo.dir}（${yg.suipo.zhi}）`);
		lines.push(`三煞：${(yg.sansha.list || []).map((s)=>`${s.name}${s.dir || ''}`).join('、')}（${yg.sansha.ju}）`);
		if (yg.wuHuang && yg.wuHuang.dir) { lines.push(`五黄：${yg.wuHuang.dir}`); }
		if (Array.isArray(yg.jiDongDirs) && yg.jiDongDirs.length) { lines.push(`忌动土方：${joinArr(yg.jiDongDirs)}`); }
	}

	lines.push('');
	lines.push('[方法说明]');
	lines.push('日课宜忌/彭祖百忌/吉神凶煞/胎神/吉神方位/时辰宜忌/物候/六曜/数九三伏 由本地历算引擎推得（纯前端）。');
	lines.push('建除十二神/黄黑道值神/二十八宿值日/年家凶煞方位 与择日通书体系一致。宜忌须与坐向、主事年命合参，忌逢关键凶煞。');

	return lines.join('\n');
}

// 便捷：直接由 (y,m,d,hour) 生成快照文本。
export function buildHuangliSnapshotByDate(y, m, d, hour = 12) {
	return buildHuangliSnapshotText(buildHuangliDay(y, m, d, hour));
}

export default buildHuangliSnapshotText;
