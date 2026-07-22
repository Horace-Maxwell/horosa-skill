// 神数正传 · AI 快照（v2 呈现层：[段头] + GFM 表）。
// 段头须与 aiExport 的段表逐字一致，否则严格切片零命中 → 整盘兜底（名实不符）。
const T = (head, rows) => (rows && rows.length ? `${head}\n${rows.join('\n')}` : '');
const tbl = (cols, rows) => [
	`| ${cols.join(' | ')} |`,
	`| ${cols.map(() => '---').join(' | ')} |`,
	...rows.map((r) => `| ${r.map((x) => (x === null || x === undefined || x === '' ? '—' : x)).join(' | ')} |`),
];

function stepsTable(steps) {
	return tbl(['步骤', '取值', '依据'], steps.map((s) => [s.label, s.output !== undefined ? s.output : s.value, s.table || s.detail || '']));
}

/** 铁板神数 */
export function buildTiebanSnapshot(r, verses = {}) {
	if (!r || !r.benming) return '';
	const b = r.benming;
	const out = [];
	out.push(T('[起盘信息]', tbl(['项', '值'], [
		['流派', '铁板神数'], ['四柱', (r.input.pillars || []).join(' ')],
		['性别', r.input.gender], ['农历', `${r.input.lunarMonth}月${r.input.lunarDay}日${r.input.isLeapMonth ? '（闰）' : ''}`],
		['求测时辰', r.input.askGz],
	])));
	out.push(T('[起数]', stepsTable(b.steps)));
	const items = [];
	Object.keys(b.items || {}).forEach((k) => {
		const it = b.items[k];
		if (it.skipped) items.push([k, '—', it.reason]);
		else (it.nums || []).forEach((n) => items.push([k, n, verses[String(n)] || '']));
	});
	out.push(T('[本命条文]', tbl(['项目', '条文号', '条文'], items)));
	if (r.liunian && r.liunian.rows.length) {
		out.push(T('[流年条文]', tbl(['虚岁', '干支', '天四声', '标记', '字母', '条文号', '条文'],
			r.liunian.rows.map((x) => [x.age, x.gz, x.tianSiSheng, x.mark, x.letter,
				x.missing ? '古籍原缺' : x.num, x.missing ? '' : (verses[String(x.num)] || '')]))));
	}
	return out.filter(Boolean).join('\n\n');
}

/** 邵子神数 */
export function buildShaoziSnapshot(r, verses = {}) {
	if (!r || !r.xianTian) return '';
	const out = [];
	out.push(T('[起盘信息]', tbl(['项', '值'], [
		['流派', '邵子神数'], ['四柱', (r.input.pillars || []).join(' ')],
		['性别', r.input.gender], ['农历', `${r.input.lunarMonth}月${r.input.lunarDay}日${r.input.isLeapMonth ? '（闰）' : ''}`],
		['父生我时年龄', r.input.fatherAge], ['母生我时年龄', r.input.motherAge],
	])));
	const xt = r.xianTian;
	out.push(T('[五基础数据]', tbl(['项', '推导', '结果'], [
		['天数', `奇数和 ${xt.tian} → 余 ${xt.tianRem}`, xt.tianGua],
		['地数', `偶数和 ${xt.di} → 余 ${xt.diRem}`, xt.diGua],
		['先天命卦', `${xt.groupA ? '阳男阴女 天上地下' : '阴男阳女 天下地上'}`, xt.gua && xt.gua.name],
		['天命数', `父${r.input.fatherAge} → 商${r.tianMing.q} 余${r.tianMing.r}${r.tianMing.special ? '（整除特例）' : ''}`, r.tianMing.num],
		['地命数', `母${r.input.motherAge} → 商${r.diMing.q} 余${r.diMing.r}${r.diMing.special ? '（整除特例）' : ''}`, r.diMing.num],
		['人命数', `${r.renMing.gua}${r.renMing.guaNum} + ${r.renMing.sound}${r.renMing.qiNum}`, r.renMing.num],
		['后天命卦', r.houTian ? `${r.houTian.tianCalc.sum}÷9余${r.houTian.tianCalc.rem}→${r.houTian.tianCalc.gua}／${r.houTian.diCalc.sum}÷9余${r.houTian.diCalc.rem}→${r.houTian.diCalc.gua}` : '', r.houTian && r.houTian.gua && r.houTian.gua.name],
		['动爻／变卦', r.houTian ? `人命数四位和 ${r.houTian.dongCalc.digits}÷6余${r.houTian.dongCalc.rem}` : '', r.houTian ? `${r.houTian.dongYao}爻动 → ${r.houTian.bianGua && r.houTian.bianGua.name}` : ''],
	])));
	if (r.dress) {
		out.push(T('[装卦]', tbl(['爻', '纳甲', '五行', '六亲', '世应'],
			r.dress.yaos.slice().reverse().map((y) => [y.pos, y.gz, y.wuxing, y.liuqin, y.shiYing || '']))));
	}
	if (r.benming) {
		const rows = [];
		[['性情', r.benming.性情], ['祖业', r.benming.祖业], ['财运', r.benming.财运], ['职业', r.benming.职业]].forEach(([k, v]) => {
			if (!v) return;
			rows.push([k, v.gua || '', v.sound || '', v.num || '—', v.num ? (verses[String(v.num)] || '') : '']);
		});
		out.push(T('[断本命]', tbl(['项目', '卦位', '声音', '条文号', '条文'], rows)));
	}
	return out.filter(Boolean).join('\n\n');
}

/** 大定神数 */
export function buildDadingSnapshot(r) {
	if (!r || !r.year) return '';
	const out = [];
	// 🔴 三运与虚岁须【连其出处一并出】—— 只写「大运丁酉」，AI 无从知其为哪一年之运,
	//    更分不清是自流年推得、还是用户手订。故摊明所推之年与未起运之实。
	const d = r.derived || {};
	out.push(T('[起盘信息]', tbl(['项', '值'], [
		['流派', '大定神数'], ['四柱', (r.input.pillars || []).join(' ')],
		['所推之年', d.year ? `${d.year}` : '（未择 —— 三运且取本命月/时/年柱代之）'],
		['大运／小运／岁君', `${r.input.dayun} ／ ${r.input.xiaoyun} ／ ${r.input.suijun}`],
		['虚岁', r.input.age],
		...(d.beforeQiYun ? [['大运之注', `${d.year} 年其时未行大运（起运之前只行小运），故取月柱代之`]] : []),
	])));
	out.push(T('[策数]', tbl(['柱', '干', '支', '纳音', '本数', '策'],
		r.year.items.map((x) => [x.gz, x.gan, x.zhi, x.nayin, x.ben, x.ce]))));
	out.push(T('[起数]', tbl(['步骤', '算式', '得数'], r.year.steps.map((s) => [s.label, s.detail, s.value]))));
	if (r.month && r.month.hit) {
		out.push(T('[死月]', tbl(['步骤', '算式', '得数'], r.month.hit.steps.map((s) => [s.label, s.detail, s.value]))));
	}
	return out.filter(Boolean).join('\n\n');
}

/** 六亲属相姓氏断 */
export function buildLiuqinSnapshot(r) {
	if (!r || !r.shengxiao) return '';
	const out = [];
	out.push(T('[起盘信息]', tbl(['项', '值'], [
		['流派', '六亲属相姓氏断'], ['四柱', (r.input.pillars || []).join(' ')],
		['性别', Number(r.input.gender) === 1 ? '乾造' : '坤造'],
		['农历', `${r.input.lunarMonth}月${r.input.lunarDay}日${r.input.isLeapMonth ? '（闰）' : ''}`],
	])));
	const sx = r.shengxiao;
	out.push(T('[十二宫与六亲宫]', stepsTable(sx.steps)));
	out.push(T('[六亲属相]', tbl(['六亲', '宫', '宫干支', '旬遁之链', '所得', '属相'],
		['spouse', 'parent'].map((k) => {
			const it = sx.items[k]; const d = it && it.dun;
			return [k === 'spouse' ? '夫妻' : '父母', it.gong, it.gz,
				d ? `${d.ganUsed} 居 ${d.p0Gua}${d.p0} → 起 ${d.xunShou} 顺数 ${d.k} 位落 ${d.pGua}${d.p} → ${d.dunGan}` : '',
				d ? d.hitGz : '', d ? d.shengxiao : ''];
		}))));
	const xs = r.xingshi;
	if (xs) {
		out.push(T('[妻室姓氏]', xs.missing
			? tbl(['项', '值'], [['本格不推', xs.missing]])
			: tbl(['步骤', '取值', '依据'], [
				...xs.steps.map((x) => [x.label, x.value, x.detail]),
				['所得姓氏', (xs.candidates || []).map((c) => `${c.name}（${c.zhi} 栏）`).join('、') || '此格无合者', ''],
				['条文号', '不推', xs.chengShuNote],
			])));
	}
	if (r.xuanji) out.push(T('[玄机卦动爻]', stepsTable(r.xuanji.steps)));
	const gaps = (r.meta && r.meta.gaps) || [];
	if (gaps.length) out.push(T('[古籍未载之格]', tbl(['项', '说明'], gaps.map((g) => [g.item, g.reason]))));
	return out.filter(Boolean).join('\n\n');
}

/** 铁算心易（查询层，非推算） */
export function buildXinyiSnapshot(r) {
	if (!r) return '';
	const out = [];
	out.push(T('[起盘信息]', tbl(['项', '值'], [
		['流派', '铁算心易（查询层）'],
		['体例', '古籍只出部分口诀与部分图表，未出起数入口 → 自择项目与声音即出条文号，不作自动推算'],
		['条文正文', '本支条文库古籍未载，仅存秘数表 → 只出条文号'],
	])));
	if (r.bake) out.push(T('[八刻分命]', tbl(['刻数', '八宫', '本命卦'], [[r.bake.ke, r.bake.gong, r.bake.gua || '—']])));
	if (r.xiang) {
		out.push(T('[条文秘数查询]', tbl(['项目', '声音', '条文号', '本格全数', '备注'], [[
			r.xiang.item, r.xiang.sound, r.xiang.picked.map((x) => x.num).join('、'),
			r.xiang.all.map((x) => `${x.mark ? `${x.mark} ` : ''}${x.num}`).join('、'),
			[r.xiang.pickNote, r.xiang.bracketNote].filter(Boolean).join('；'),
		]])));
	}
	if (r.xingqing) {
		out.push(T('[性情项查询]', tbl(['地支', '余数', '条文号', '备注'], [[
			r.xingqing.zhi, r.xingqing.yushu, r.xingqing.nums.join('、'), r.xingqing.ambiguous || '',
		]])));
	}
	const gaps = (r.meta && r.meta.gaps) || [];
	if (gaps.length) out.push(T('[古籍未载之格]', tbl(['项', '说明'], gaps.map((g) => [g.item, g.reason]))));
	return out.filter(Boolean).join('\n\n');
}

export function buildZhengChuanSnapshotText(model, verses = {}) {
	if (!model) return '';
	if (model.school === 'tieban') return buildTiebanSnapshot(model, verses);
	if (model.school === 'shaozi') return buildShaoziSnapshot(model, verses);
	if (model.school === 'dading') return buildDadingSnapshot(model);
	if (model.school === 'liuqin') return buildLiuqinSnapshot(model);
	if (model.school === 'xinyi') return buildXinyiSnapshot(model);
	return '';
}

export default buildZhengChuanSnapshotText;
