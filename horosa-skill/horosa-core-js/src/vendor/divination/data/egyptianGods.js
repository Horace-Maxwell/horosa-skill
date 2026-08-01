// divination/data/egyptianGods.js
// 现代流行「埃及众神星座」数据与算法(纯数据 + 纯函数,零副作用)。
//
// ⚠️ 性质声明(必须随内容一并呈现,不得当古史陈列)：
//   本体系是 20 世纪欧美通俗读物创造的分类法 —— 把 12 位埃及神祇按公历生日区段分派。
//   它与古埃及的实际信仰与占卜实践**没有史料关系**：古埃及并不以「出生日期→守护神」论命。
//   收录它，只因今天大众最常以此名指称「埃及占星」。
//
// 与西方 12 星座「每座一段连续日期」不同，本体系每位神祇对应 2–4 段**不连续**日期，
// 全年共 28 段。段界各家读物略有出入，故按「版本」组织(见 EGYPT_GOD_EDITIONS)。
//
// 默认版本 = 无缺口自洽版：28 段并集恰好覆盖 1/1–12/31（含 2/29）无缺、无叠。

/* ============================================================
 * 12 神祇：名 / 中译 / 关键词
 * ============================================================ */

export const EGYPT_GODS = [
	{ key: 'Nile',   name: 'The Nile', cn: '尼罗',   keywords: ['丰沛', '务实', '能量源', '和平'], note: '十二者中唯一非神祇的符号，取尼罗河本身为象。' },
	{ key: 'AmunRa', name: 'Amun-Ra',  cn: '阿蒙-拉', keywords: ['王者', '自信', '领导', '乐观'], note: '亦作 Amon。' },
	{ key: 'Mut',    name: 'Mut',      cn: '穆特',   keywords: ['母性', '敏感', '忠诚', '守护'], note: '' },
	{ key: 'Geb',    name: 'Geb',      cn: '盖布',   keywords: ['大地', '情感', '直觉', '敏锐'], note: '' },
	{ key: 'Osiris', name: 'Osiris',   cn: '奥西里斯', keywords: ['重生', '智识', '独立', '强自我'], note: '' },
	{ key: 'Isis',   name: 'Isis',     cn: '伊西斯', keywords: ['魔法', '诚实', '幽默', '热爱生活'], note: '' },
	{ key: 'Thoth',  name: 'Thoth',    cn: '透特',   keywords: ['智慧', '学习', '外交', '上进'], note: '' },
	{ key: 'Horus',  name: 'Horus',    cn: '荷鲁斯', keywords: ['天空', '勇敢', '乐观', '勤奋'], note: '' },
	{ key: 'Anubis', name: 'Anubis',   cn: '阿努比斯', keywords: ['内省', '自信', '神秘', '洞察'], note: '' },
	{ key: 'Seth',   name: 'Seth',     cn: '塞特',   keywords: ['混沌', '变动', '领袖欲', '不安分'], note: '' },
	{ key: 'Bastet', name: 'Bastet',   cn: '巴斯特', keywords: ['平衡', '魅力', '避冲突', '直觉'], note: '' },
	{ key: 'Sekhmet', name: 'Sekhmet', cn: '塞赫麦特', keywords: ['战与愈双面', '纪律', '冒险', '正义'], note: '' },
];

export const EGYPT_GOD_BY_KEY = EGYPT_GODS.reduce((acc, g)=>{ acc[g.key] = g; return acc; }, {});

/* ============================================================
 * 日期段(28 段) —— 版本组织
 * 段记为 [神, 起月, 起日, 止月, 止日]，闭区间，按 month*100+day 比较。
 * ============================================================ */

// 主线：无缺口自洽版
const RANGES_SEAMLESS = [
	['Nile', 1, 1, 1, 7], ['AmunRa', 1, 8, 1, 21], ['Mut', 1, 22, 1, 31],
	['AmunRa', 2, 1, 2, 11], ['Geb', 2, 12, 2, 29],
	['Osiris', 3, 1, 3, 10], ['Isis', 3, 11, 3, 31],
	['Thoth', 4, 1, 4, 19], ['Horus', 4, 20, 5, 7],
	['Anubis', 5, 8, 5, 27], ['Seth', 5, 28, 6, 18],
	['Nile', 6, 19, 6, 28], ['Anubis', 6, 29, 7, 13],
	['Bastet', 7, 14, 7, 28], ['Sekhmet', 7, 29, 8, 11],
	['Horus', 8, 12, 8, 19], ['Geb', 8, 20, 8, 31],
	['Nile', 9, 1, 9, 7], ['Mut', 9, 8, 9, 22], ['Bastet', 9, 23, 9, 27],
	['Seth', 9, 28, 10, 2], ['Bastet', 10, 3, 10, 17], ['Isis', 10, 18, 10, 29],
	['Sekhmet', 10, 30, 11, 7], ['Thoth', 11, 8, 11, 17], ['Nile', 11, 18, 11, 26],
	['Osiris', 11, 27, 12, 18], ['Isis', 12, 19, 12, 31],
];

// 变体：部分读物把尼罗六月段作 6/12–6/18、Amun-Ra 首段作 1/8–1/12。
// 该版本会在 1/13–1/21 与 6/19–6/28 留下无归属日 —— 属来源排版差错，此处照实标注为「有缺口」，
// 不替其补洞（补洞即等于我们替来源做主张）。
const RANGES_VARIANT = RANGES_SEAMLESS
	.map((r)=>{
		if(r[0] === 'Nile' && r[1] === 6){ return ['Nile', 6, 12, 6, 18]; }
		if(r[0] === 'AmunRa' && r[1] === 1){ return ['AmunRa', 1, 8, 1, 12]; }
		return r;
	});

export const EGYPT_GOD_EDITIONS = {
	seamless: {
		key: 'seamless',
		label: '无缺口自洽版',
		ranges: RANGES_SEAMLESS,
		note: '28 段并集覆盖全年无缺无叠（含 2/29）。尼罗六月段取 6/19–6/28、阿蒙-拉首段取 1/8–1/21。',
	},
	variant: {
		key: 'variant',
		label: '通行变体',
		ranges: RANGES_VARIANT,
		note: '尼罗六月段作 6/12–6/18、阿蒙-拉首段作 1/8–1/12。此版在 1/13–1/21 与 6/19–6/28 留有无归属日（来源排版所致，未代为补洞）。',
	},
};
export const EGYPT_GOD_EDITION_DEFAULT = 'seamless';

/* ============================================================
 * 算法：日期 → 守护神
 * ============================================================ */

export function egyptianGodRanges(edition){
	const e = EGYPT_GOD_EDITIONS[edition] || EGYPT_GOD_EDITIONS[EGYPT_GOD_EDITION_DEFAULT];
	return e.ranges;
}

// month 1..12、day 1..31；落段返回神 key，未落段返回 ''（变体版的缺口日会走到这里）
export function egyptianGodSign(month, day, edition){
	const m = Number(month);
	const d = Number(day);
	if(!Number.isFinite(m) || !Number.isFinite(d)){ return ''; }
	if(m < 1 || m > 12 || d < 1 || d > 31){ return ''; }
	const key = m * 100 + d;
	const ranges = egyptianGodRanges(edition);
	for(let i = 0; i < ranges.length; i++){
		const [god, m1, d1, m2, d2] = ranges[i];
		if(m1 * 100 + d1 <= key && key <= m2 * 100 + d2){ return god; }
	}
	return '';
}

// 某神在该版本下的全部日期段（供卡片展开显示）
export function egyptianGodSegments(godKey, edition){
	return egyptianGodRanges(edition)
		.filter((r)=>r[0] === godKey)
		.map(([, m1, d1, m2, d2])=>({ from: `${m1}/${d1}`, to: `${m2}/${d2}`, m1, d1, m2, d2 }));
}

// 段的可读串（如 "1/1–1/7、6/19–6/28"）
export function egyptianGodSegmentText(godKey, edition){
	return egyptianGodSegments(godKey, edition).map((s)=>`${s.from}–${s.to}`).join('、');
}

// 性质声明（显示层必须随内容呈现）
export const EGYPT_GODS_DISCLAIMER = '此体系为 20 世纪欧美通俗读物的分类法，与古埃及信仰与占卜实践无史料关系；古埃及并不以出生日期定守护神。列此仅因今日大众多以此名指称「埃及占星」。';
