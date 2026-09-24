// 老黄历日课 AI 挂载/导出快照 builder（纯函数，jest 直测）。
// 「显示什么就导出什么」：全字段取自 buildHuangliDay 返回的 day 对象，不在此重算。
import { buildHuangliDay } from './huangliDay.js';
import { wutuForDate } from '../tongshu/wutu.js';   // [Q-458/T-421] 乌兔九星值日(与 lunar 的「九星值日」非同一体系)
import { buildYearAuspicious } from './yearAuspicious.js';   // [Q-458/T-421] 年度吉日榜(候选段,开过面板才产)
import { EVENT_CATEGORIES } from './tongshuData.js';

function joinArr(arr, sep = '、') {
	return (Array.isArray(arr) ? arr : []).filter(Boolean).join(sep);
}

// [Q-458/T-421] opts.yearTop:{ year } —— 「年度吉日榜」候选段。按本文件开头的契约「显示什么就导出什么」,
// 只有用户真开过该面板才产此段(HuangLiMain 记一个 sticky 标志);未开过=页面也没显示过 → 不产,
// 同时也避免每次存快照都白跑一趟全年扫描(buildYearAuspicious 按年 memo,开过才付一次)。
export function buildHuangliSnapshotText(day, opts) {
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
	// [Q-458/T-421] 建除吉凶括注:日课卡按 jianchu.jx 着色(吉/凶/中),快照此前只写「建除十二神:X日」→
	// AI 拿不到这一日是吉建还是凶建。与卡片同源 day.jianchu.jx。
	lines.push(`建除十二神：${day.jianchu.name}日${day.jianchu.jx ? `（${day.jianchu.jx}）` : ''}`);
	lines.push(`黄黑道值神：${day.tianshen.name}（${day.tianshen.type}·${day.tianshen.luck}）`);
	lines.push(`二十八宿：${day.xiu.name}${day.xiu.zheng || ''}${day.xiu.animal || ''}（${day.xiu.xiang}·${day.xiu.luck}）`);
	if (day.nineStar) { lines.push(`九星值日：${day.nineStar.name}`); }
	// [Q-458/T-421] 乌兔九星值日:月历每格早已叠画(太阳/太阴另加标记、吉凶着色),而快照里的「九星值日」
	// 是 lunar 口径的另一套体系 —— 两者不可互推,此前 AI 只看到后者。与网格同源 wutuForDate。
	try{
		const _ymd = `${(day.solar && day.solar.ymd) || ''}`.split('-').map((x)=> parseInt(x, 10));
		const _wt = (_ymd.length === 3 && _ymd.every((n)=> !isNaN(n))) ? wutuForDate({ y: _ymd[0], m: _ymd[1], d: _ymd[2] }) : null;
		if (_wt && _wt.star) {
			lines.push(`乌兔九星：${_wt.star}（${_wt.gong}宫·${_wt.jx === 'good' ? '吉' : '凶'}${_wt.isSun ? '·太阳日' : (_wt.isMoon ? '·太阴日' : '')}）`);
		}
	}catch(e){ /* 乌兔取不到不阻断整段(月朔/朔前卯日越域) */ }
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

	// [Q-458/T-421] 年度吉日榜(候选段):按事项列当年 Top 吉日,与面板同一函数、同一缺省(非敏感事项 + Top12)。
	if (opts && opts.yearTop && opts.yearTop.year) {
		try{
			const _keys = EVENT_CATEGORIES.filter((c)=> !c.sensitive).map((c)=> c.key);
			const buckets = buildYearAuspicious(opts.yearTop.year, { events: _keys, topN: 12 }) || {};
			const _rows = [];
			Object.keys(buckets).forEach((k)=>{
				const b = buckets[k];
				const list = (b && b.list) || [];
				if (list.length) {
					_rows.push(`${b.label}：${list.map((x)=> `${x.ymd}(${x.score})`).join('、')}`);
				}
			});
			if (_rows.length) {
				lines.push('');
				lines.push('[年度吉日榜]');
				lines.push(`年份：${opts.yearTop.year}　口径：非敏感事项各取 Top 12（与页面面板缺省同）`);
				_rows.forEach((l)=> lines.push(l));
			}
		}catch(e){ /* 全年扫描失败不阻断日课快照 */ }
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
