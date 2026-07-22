// 神数正传 · 铁算心易 —— 查询层（非推算引擎）。
//
// 🔴 本支古籍只出「部分口诀」与「部分图表」，未出起数入口：
//    由八字/玄机卦求各项之「声音」「卦气」「余数」之法全书无一字（作者自述此支暂不公开传授），
//    其命例亦只列结果而不示推导。故本层据实作查询器 —— 用户自择项目与声音/余数即出条文号，
//    不假装能由生辰自动推算。
//
// 🔴 条文正文亦未载：本支所出之条文号与本仓既有条文库号段虽同，正文全异（另一套库，
//    经二十一条逐条比对：号 21/21 命中而正文 21/21 皆不同，且体例一为直白断语、一为象喻诗谶）
//    → 绝不代入既有库之正文冒充本支条文。本层只出号。
//
// 数表见 data/zhengchuanXinyiTables.json（机读录入，附不变式自证：
//   八刻分命表 = 京房八宫卦序 64/64；性情下表[支] = 上表[冲支] 71/72（唯一破例已记 ambiguous）；
//   性情表 12 支 × 12 余数满格 144/144）。
import TABLES from './data/zhengchuanXinyiTables.json' with { type: 'json' };

export const XINYI_META = TABLES._meta || { gaps: [], ambiguous: [] };

export const XINYI_ITEMS = ['父母', '兄弟', '姻緣', '子孫', '官祿', '疾病'];
export const XINYI_SOUNDS_A = ['日', '月', '星', '辰', '水', '火', '土', '石'];
export const XINYI_SOUNDS_B = ['平', '上', '去', '入', '開', '發', '收', '閉'];
export const XINYI_KE = ['一刻', '二刻', '三刻', '四刻', '五刻', '六刻', '七刻', '八刻'];
export const XINYI_GONG = ['乾', '兌', '離', '震', '巽', '坎', '艮', '坤'];
const ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];

/** 八刻分命表：刻数 × 八宫 → 本命卦 */
export function lookupBake(ke, gong) {
	const row = (TABLES.bakeFenming || {})[ke];
	if (!row) return null;
	const i = XINYI_GONG.indexOf(gong);
	return i >= 0 ? row[i] : null;
}
export function bakeTable() {
	return XINYI_KE.map((ke) => ({ ke, guas: (TABLES.bakeFenming || {})[ke] || [] }));
}

/**
 * 六项条文秘数表：项目 × 声音 → 条文号。
 * 一格可含多号（皆取）；官禄项之数带 ×／●○ 标记（古籍未出注解，其命例为乾造而取 ●○ 之值
 * → 推定 ●○=乾造、×=坤造，仅此一例佐证，故并陈不独断）。
 */
export function lookupXiang(item, sound, gender) {
	const t = (TABLES.xiangTables || {})[item];
	if (!t) return null;
	const cell = (t.sounds || {})[sound];
	if (!cell) return null;
	const male = Number(gender) === 1;
	const nums = cell.map((x) => (typeof x === 'number' ? { num: x, mark: null } : x));
	const marked = nums.filter((x) => x.mark);
	let picked = nums;
	let pickNote = '';
	if (marked.length) {
		const want = male ? '●○' : '×';
		const hit = nums.filter((x) => x.mark === want);
		if (hit.length) { picked = hit; pickNote = `本格分标 ●○／×，按${male ? '乾' : '坤'}造取 ${want} 之值（此标之义古籍未注，详见存疑）`; }
	}
	return { item, sound, all: nums, picked, pickNote, bracketNote: t.bracketNote, bracketDefault: t.bracketDefault };
}
export function xiangTable(item) {
	const t = (TABLES.xiangTables || {})[item];
	if (!t) return null;
	return {
		item,
		rowsA: XINYI_SOUNDS_A.map((s) => ({ sound: s, cell: (t.sounds || {})[s] || [] })),
		rowsB: XINYI_SOUNDS_B.map((s) => ({ sound: s, cell: (t.sounds || {})[s] || [] })),
		bracketNote: t.bracketNote, bracketDefault: t.bracketDefault,
	};
}

/** 性情项条文秘数表：地支 × 余数(1..12) → 条文号 */
export function lookupXingqing(zhi, yushu) {
	const row = (TABLES.xingqing || {})[zhi];
	if (!row) return null;
	const nums = row[String(yushu)];
	if (!nums) return null;
	const amb = (XINYI_META.ambiguous || []).find((a) => (a.detail || '').indexOf(`下[${zhi}][${yushu}]`) >= 0);
	return { zhi, yushu, nums, ambiguous: amb ? amb.reading : null };
}
export function xingqingTable() {
	return ZHI.map((z) => ({ zhi: z, cells: Array.from({ length: 12 }, (_, i) => ((TABLES.xingqing || {})[z] || {})[String(i + 1)] || []) }));
}

/** 起日月声音表：卦气 → 日之宫位、余数 → 月之宫位 */
export function lookupQiRiYue({ guaqi, yushu }) {
	const t = TABLES.qiRiYue || {};
	const qi = t['卦氣'] || [];
	const ys = t['餘數'] || [];
	const gong = t['宮位'] || [];
	const out = {};
	if (guaqi) { const i = qi.indexOf(guaqi); out.riGong = i >= 0 ? gong[i] : null; }
	if (yushu) { const i = ys.indexOf(String(yushu)); out.yueGong = i >= 0 ? gong[i] : null; }
	return out;
}
export function qiRiYueTable() {
	const t = TABLES.qiRiYue || {};
	return (t['卦氣'] || []).map((q, i) => ({ guaqi: q, yushu: (t['餘數'] || [])[i], gong: (t['宮位'] || [])[i] }));
}

/** 铁算心法各时辰序列（演卦须秘咒定上卦，秘咒古籍未载 → 只供查阅，不作推算） */
export function xinFaTable() {
	return ZHI.map((z) => ({ zhi: z, seq: [] }));
}

export function calcXinyi(input) {
	const q = input || {};
	return {
		school: 'xinyi', input: q, isLookup: true,
		bake: q.ke && q.gong ? { ke: q.ke, gong: q.gong, gua: lookupBake(q.ke, q.gong) } : null,
		xiang: q.item && q.sound ? lookupXiang(q.item, q.sound, q.gender) : null,
		xingqing: q.xqZhi && q.xqYushu ? lookupXingqing(q.xqZhi, q.xqYushu) : null,
		qiRiYue: q.guaqi || q.qiYushu ? lookupQiRiYue({ guaqi: q.guaqi, yushu: q.qiYushu }) : null,
		meta: XINYI_META,
	};
}

export default calcXinyi;
