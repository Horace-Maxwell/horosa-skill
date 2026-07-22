// 皇极轨策 · AI 快照（v2 呈现层：[段头] + GFM 表）。
// 🔴 段头须与 aiExport 之段表逐字一致，否则严格切片零命中 → 整盘兜底（名实不符）。
const T = (head, rows) => (rows && rows.length ? `${head}\n${rows.join('\n')}` : '');
const tbl = (cols, rows) => [
	`| ${cols.join(' | ')} |`,
	`| ${cols.map(() => '---').join(' | ')} |`,
	...rows.map((r) => `| ${r.map((x) => (x === null || x === undefined || x === '' ? '—' : x)).join(' | ')} |`),
];

export function buildGuiceSnapshotText(pan, opts) {
	if (!pan || !pan.gua) return '';
	const out = [];
	const timeLines = (opts && opts.timeLines) || [];
	const { gua, yan, bian, duan, ying, lishi, dading, settings, askEvent } = pan;
	const fang = pan.shiFang;

	out.push(T('[占事直断]', tbl(['项', '值'], [
		['占事', askEvent || '（未录）'],
		['起卦法', gua.fa || '—'],
		['本卦', `${gua.name || `${gua.up}上${gua.lo}下`}　${gua.dongYao} 爻动`],
		['变卦', pan.bianName || '—'],
		['体用', duan && duan.tiYong ? `体 ${duan.tiYong.tiGua}／用 ${duan.tiYong.yongGua} —— ${duan.tiYong.key}：${duan.tiYong.duan}` : '—'],
		['演数', `${settings.yanshuFa === 'gui' ? '轨数' : '策数'} ${yan.value}`],
		['流派', settings.school],
	])));

	if (gua.steps && gua.steps.length) {
		out.push(T('[起卦]', [...timeLines, ...tbl(['步骤', '依据', '所得'], gua.steps.map((s) => [s.label, s.detail, s.value]))]));
	}

	out.push(T('[演数]', tbl(['项', '值'], [
		['身数', yan.body],
		['算式', yan.formula],
		['所得', yan.value],
		['除万取四位', `千${yan.parts.qian} 百${yan.parts.bai} 十${yan.parts.shi} 零${yan.parts.ling}`],
	])));
	out.push(T('[四位]', tbl(['位', '数', '卦', '取象', '借'], yan.siwei.map((x) => [
		x.wei, x.value, x.gua, x.wuxing || '', [x.borrowed, x.guaBorrow].filter(Boolean).join('／'),
	]))));

	if (bian && bian.hu) {
		out.push(T('[卦变]', tbl(['项', '卦'], [
			['本卦', gua.name || `${gua.up}／${gua.lo}`],
			['体卦', bian.hu.tiGua], ['用卦', bian.hu.yongGua],
			['体互', bian.hu.tiHu], ['用互', bian.hu.yongHu],
			...(bian.hu.fromBian ? [['互之所出', '乾坤无互，互其变卦']] : []),
			['变卦', pan.bianName || `${bian.bian.up}／${bian.bian.lo}`],
			['错卦', `${bian.cuo.up}／${bian.cuo.lo}`],
			['综卦', `${bian.zong.up}／${bian.zong.lo}`],
		])));
	}

	if (duan) {
		const rows = [];
		if (duan.qingZhong) {
			duan.qingZhong.rows.forEach((r) => rows.push([`${r.label}（${r.ying}）`, r.gua, r.key, r.duan]));
			rows.push(['终应', '—', '—', duan.qingZhong.zhongYing]);
		}
		if (duan.guaQi && duan.guaQi.ti) rows.push(['体卦之气', duan.guaQi.ti.gua, duan.guaQi.ti.qi, duan.guaQi.ti.jie || '']);
		if (duan.guaQi && duan.guaQi.yong) rows.push(['用卦之气', duan.guaQi.yong.gua, duan.guaQi.yong.qi, duan.guaQi.yong.jie || '']);
		if (duan.zhuKe) rows.push(['主算／客算', `${duan.zhuKe.zhuSuan}／${duan.zhuKe.keSuan}`, duan.zhuKe.sheng, duan.zhuKe.ze]);
		if (duan.kongQue) rows.push(['数全空缺', '—', duan.kongQue.quan, duan.kongQue.items.map((i) => `${i.wei}(${i.xiang})`).join('、')]);
		out.push(T('[断法]', tbl(['项', '卦', '判', '说'], rows)));
	}

	if (fang) {
		out.push(T('[时方]', tbl(['项', '值'], [
			['所参之路', settings.shuXi === 'meihua' ? '梅花（不用时方）' : '周易数（参时方）'],
			['方应', fang.ying
				? `${fang.ying.fang}（${fang.ying.gua}）对体卦 ${fang.ying.ti}：${fang.ying.key} —— ${fang.ying.duan}`
				: '（未录占者所坐立之方 —— 古籍以体为主、看来占之人所在之方，非机可代）'],
			...(fang.shenSha ? [['时方神煞', `${fang.shenSha.names.join('、')}（${fang.shenSha.note}）`]] : []),
		])));
	}

	if (ying) {
		out.push(T('[三要十应]', tbl(['应', '所出', '值', '断'], ying.items.map((x) => [
			x.label, x.from, x.missing ? '（未录）' : (x.gua || x.value), x.duan || (x.missing ? x.note : ''),
		]))));
	}

	if (lishi && (lishi.zhiNian || lishi.biGua)) {
		out.push(T('[元会运世]', tbl(['项', '值'], [
			...(lishi.zhiNian ? [['值年卦', `${lishi.zhiNian.year} 年 ${lishi.zhiNian.gua}`]] : []),
			...(lishi.zhiNian && lishi.zhiNian.shiGua ? [['世卦', `${lishi.zhiNian.shiGua.gua}（${lishi.zhiNian.shiGua.from}–${lishi.zhiNian.shiGua.to}）`]] : []),
			...(lishi.biGua ? [['月建辟卦', `${lishi.biGua.zhi}月 ${lishi.biGua.gua}（${lishi.biGua.xiao}）`]] : []),
			['元会运世', '1元 = 12会 = 360运 = 4320世 = 129600年'],
		])));
	}

	if (dading) {
		out.push(T('[大定起数]', tbl(['步骤', '算式', '得数'], dading.steps.map((s) => [s.label, s.detail, s.value]))));
	}

	return out.filter(Boolean).join('\n\n');
}

export default buildGuiceSnapshotText;
