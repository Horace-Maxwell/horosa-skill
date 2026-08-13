// 灵棋经 AI 快照(纯函数,零 UI 依赖)。
// 🔴 段头七段与 aiExport.js AI_EXPORT_PRESET_SECTIONS.lingqi 逐字一致,且恒出全段头
//    (开关只影响段内文本,段集恒定 —— parityAll 双向哨兵口径)。
// 🔴 快照恒简体输出(lingqiToSimp;AI 输入稳定,不随「原文/简体」显示档漂移)。
// 🔴 卦=冻结值:headless 一律自 payload.counts 复排,绝不重掷(「不可再擲」古法+全站事盘纪律)。
import { findLingqiGua, lingqiOrdinalCn } from './data/lingqiJing.js';
import { lingqiToSimp } from './data/lingqiT2S.js';
import { sanCaiOf, splitVerse } from './core/lingqiCast.js';

export const LINGQI_CATEGORY_OPTIONS = [
	{ value: 'general', label: '通用' },
	{ value: 'career', label: '仕途' },
	{ value: 'wealth', label: '求财' },
	{ value: 'marriage', label: '婚姻' },
	{ value: 'health', label: '疾病' },
	{ value: 'travel', label: '行人' },
	{ value: 'lawsuit', label: '官讼' },
	{ value: 'home', label: '家宅' },
];

// 问类关键词(注文高亮辅助;词取自注文实际用语的简体形,只做视觉/提示引导,不构成判读)。
export const LINGQI_CATEGORY_KEYWORDS = {
	general: [],
	career: ['求官', '仕', '禄位', '爵', '高迁', '迁官', '功名', '临官'],
	wealth: ['求财', '市贾', '田蚕', '财', '货', '渔猎'],
	marriage: ['婚姻', '婚', '嫁', '娶'],
	health: ['病', '疾', '医', '药', '瘥'],
	travel: ['行人', '远行', '出行', '行者', '未还', '当至', '未至'],
	lawsuit: ['官事', '讼', '狱', '囚', '系者', '刑'],
	home: ['家宅', '居家', '居宅', '宅', '移徙', '起造', '门户'],
};

export function lingqiCategoryLabel(value) {
	const hit = LINGQI_CATEGORY_OPTIONS.find((o) => o.value === value);
	return hit ? hit.label : '通用';
}

export const LINGQI_ZHU_META = [
	{ key: 'yan', label: '颜曰', source: '颜幼明注', era: '晋' },
	{ key: 'he', label: '何曰', source: '何承天注', era: '宋' },
	{ key: 'chen', label: '陈曰', source: '陈师凯解', era: '元' },
	{ key: 'liu', label: '刘曰', source: '刘基注', era: '明' },
];

export const DEFAULT_LINGQI_ZHU_VISIBLE = { yan: true, he: true, chen: true, liu: true, ke: true, shi: true };

// counts([上,中,下] 各 0-4)→ 中文棋数句;纯阴镘特述。
export function lingqiCountsText(counts) {
	const cs = Array.isArray(counts) ? counts : [];
	if (cs.length !== 3) { return ''; }
	if (cs[0] === 0 && cs[1] === 0 && cs[2] === 0) { return '十二棋皆覆'; }
	const CNN = ['〇', '一', '二', '三', '四'];
	return `${CNN[cs[0]]}上${CNN[cs[1]]}中${CNN[cs[2]]}下`;
}

// 卦题一行:「第一 · 大通卦(一上一中一下)· 升腾之象」;纯阴镘=「纯阴镘卦(十二棋皆覆,不入一百二十四卦之数)· 无形之象」。
export function lingqiGuaTitle(gua) {
	if (!gua) { return ''; }
	if (gua.id === 125) { return `${lingqiToSimp(gua.name)}卦(十二棋皆覆,不入一百二十四卦之数)· ${lingqiToSimp(gua.xiang)}之象`; }
	return `${lingqiOrdinalCn(gua.id)} · ${lingqiToSimp(gua.name)}卦(${lingqiCountsText(gua.counts)})· ${lingqiToSimp(gua.xiang)}之象`;
}

/**
 * 七段快照。st:{ counts, question, category, zhuVisible, wuDay, timeLines }。
 * 段头恒出;zhuVisible 只控段内行(所见即所得);全文简体。
 */
export function buildLingqiSnapshotText(st) {
	const s = st || {};
	const counts = Array.isArray(s.counts) && s.counts.length === 3 ? s.counts : null;
	if (!counts) { return ''; }
	const gua = findLingqiGua(counts[0], counts[1], counts[2]);
	if (!gua) { return ''; }
	const vis = { ...DEFAULT_LINGQI_ZHU_VISIBLE, ...(s.zhuVisible || {}) };
	const t = lingqiToSimp;
	const out = [];

	out.push('[起盘信息]');
	out.push(s.question ? `所问:${s.question}(问类:${lingqiCategoryLabel(s.category)})` : `(未录问事;问类:${lingqiCategoryLabel(s.category)})`);
	(s.timeLines || []).forEach((l) => out.push(l));
	if (s.wuDay) { out.push('古法提示:占时日干为戊 ——《灵棋经》卷首「六戊日不宜占卜」(仅提示,不碍成卦)。'); }
	out.push('');

	out.push('[棋势]');
	const sc = sanCaiOf(counts);
	sc.layers.forEach((ly) => {
		out.push(`${ly.label}位:${ly.value} 枚(${t(ly.xing)})—— ${ly.role}·${ly.realm}`);
	});
	const rels = sc.relations.filter((r) => r.kind);
	if (rels.length) {
		rels.forEach((r) => out.push(`层际:${r.between}为${t(r.label)}(${t(r.gloss)})`));
	} else {
		out.push('层际:无耦敌明文(耦=少阳配少阴,敌=太阳配老阴;本卦各层不成此两对)。');
	}
	out.push(`阴阳:阳数 ${sc.yang} 层、阴数 ${sc.yin} 层${sc.tendency ? `(${t(sc.tendency)})` : ''}`);
	if (gua.attr) { out.push(`格局:${t(gua.attr)}`); }
	out.push('');

	out.push('[卦象]');
	out.push(lingqiGuaTitle(gua));
	if (gua.note) { out.push(`(原书小注:${t(gua.note)})`); }
	out.push('');

	out.push('[繇辞]');
	out.push(`象曰:${t(gua.yao)}`);
	out.push('');

	out.push('[诸家注]');
	let zhuAny = false;
	LINGQI_ZHU_META.forEach((zm) => {
		if (!vis[zm.key]) { return; }
		const body = gua.zhu[zm.key];
		zhuAny = true;
		out.push(body ? `${zm.label}(${zm.source}):${t(body)}` : `${zm.label}(${zm.source}):本卦原书无此家注。`);
	});
	if (!zhuAny) { out.push('(注家显示已全部关闭)'); }
	out.push('');

	out.push('[课断]');
	if (!vis.ke) { out.push('(课断显示已关闭)'); }
	else { out.push(gua.ke ? `此课:${t(gua.ke)}` : '本卦原书无「此课」总断(或已并入他家注文)。'); }
	out.push('');

	out.push('[断诗]');
	if (!vis.shi) { out.push('(断诗显示已关闭)'); }
	else {
		out.push(`诗曰:${splitVerse(t(gua.shi)).join(' / ')}`);
		if (gua.shiEx) { out.push(`又曰:${splitVerse(t(gua.shiEx)).join(' / ')}`); }
	}
	return out.join('\n').trim();
}

/** 无头重算(AI 挂载「按设置重算」):卦=冻结 counts 自 payload 取,绝不重掷;齿轮 opts 可覆盖显示口径。 */
export function buildLingqiSnapshotForCase(payload, opts) {
	try {
		const p = payload && typeof payload === 'object' ? payload : {};
		const counts = Array.isArray(p.counts) && p.counts.length === 3 ? p.counts : null;
		if (!counts) { return ''; }
		const o = p.options && typeof p.options === 'object' ? p.options : {};
		const g = opts && typeof opts === 'object' ? opts : {};
		// 齿轮三态归一:''/undefined=随档;1/'1'/true=显;0/'0'/false=隐(挂载设置 select 型口径)。
		const baseVis = { ...DEFAULT_LINGQI_ZHU_VISIBLE, ...(o.zhuVisible || {}) };
		['yan', 'he', 'chen', 'liu', 'ke', 'shi'].forEach((k) => {
			const v = g[`zhu_${k}`];
			if (v === undefined || v === null || v === '') { return; }
			baseVis[k] = (v === 1 || v === '1' || v === true);
		});
		return buildLingqiSnapshotText({
			counts,
			question: (g.question !== undefined && g.question !== '') ? g.question : (o.question || ''),
			category: (g.category !== undefined && g.category !== null && g.category !== '') ? g.category : (o.category || 'general'),
			zhuVisible: baseVis,
			wuDay: !!o.wuDay,
			timeLines: Array.isArray(o.timeLines) ? o.timeLines : [],
		});
	} catch (e) { return ''; }
}
