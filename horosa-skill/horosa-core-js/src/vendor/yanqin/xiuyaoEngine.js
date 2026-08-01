// 演禽 · 宿曜道 / 三九秘法 独立子系统(WP-21)。纯函数,与 28 宿演禽并存不混。
// 古籍(宿曜经·三九秘法):27 宿(去牛)、本命宿朔日法、三九业胎、人际相性 729 通。密教星宿系,断相性与择直日。

// —— 27 宿序(去牛,昴起)✅ 古籍 ——:昴毕觜参井鬼柳星张翼轸角亢氐房心尾箕斗女虚危室壁奎娄胃。
// (= 28 宿标准序自昴 rotate、去牛;1685 改历后才改回含牛 28 宿。)
export const XIUYAO_27 = [
	'昴', '毕', '觜', '参', '井', '鬼', '柳', '星', '张', '翼', '轸', '角', '亢',
	'氐', '房', '心', '尾', '箕', '斗', '女', '虚', '危', '室', '壁', '奎', '娄', '胃',
];
export const XIUYAO_IDX = XIUYAO_27.reduce((m, h, i) => { m[h] = i; return m; }, {});

// —— 三九秘法(业/胎)✅ 古籍 ——:以本命宿为「命」,每 9 宿取一 → 第 9 宿=业(前世)、第 18 宿=胎(来世)。
// 三段各 9 宿覆盖 27(对应三世因缘)。benMingHead=本命宿单字首字。
export function sanjiu(benMingHead) {
	const i = XIUYAO_IDX[benMingHead];
	if (i === undefined) { return null; }
	return {
		ming: XIUYAO_27[i],
		ye: XIUYAO_27[(i + 9) % 27],   // 业·前世
		tai: XIUYAO_27[(i + 18) % 27], // 胎·来世
	};
}

// —— 人际相性(十一字)◐ 古籍 ——:栄親=大吉、友=吉、安=吉(己占优)、衰=平、壊=凶(对方占优·最需警惕)、
// 危/成=凶;命/業/胎 三者=难遇强缘(不受距离影响)。总组合 27×27=729 通。
export const XIANGXING_MEANING = {
	栄: '大吉', 親: '大吉', 友: '吉', 安: '吉(己占优)', 衰: '平',
	壊: '凶(对方占优·最警惕)', 危: '凶', 成: '凶', 命: '难遇强缘', 業: '难遇强缘', 胎: '难遇强缘',
};

// 两命本命宿之相性(a 视 b)。三九位(命/业/胎)先判;余位精确「距离→相性字」对应表须原典(宿曜经·三九秘宿)核。
// 返回 { distance, key(命/業/胎 或 null待校), meaning }。避臆造:非三九位仅给距离,相性字标待校。
export function xiangXing(aHead, bHead) {
	const ai = XIUYAO_IDX[aHead];
	const bi = XIUYAO_IDX[bHead];
	if (ai === undefined || bi === undefined) { return null; }
	const d = ((bi - ai) % 27 + 27) % 27;
	if (d === 0) { return { distance: 0, key: '命', meaning: XIANGXING_MEANING['命'] }; }
	if (d === 9) { return { distance: 9, key: '業', meaning: XIANGXING_MEANING['業'] }; }
	if (d === 18) { return { distance: 18, key: '胎', meaning: XIANGXING_MEANING['胎'] }; }
	return { distance: d, key: null, meaning: '相性字(栄親友衰安壊危成)按距离精确对应表待纸本《宿曜经》核' };
}

// ⚠️ 本命宿(朔日宿法):公历生日→旧历→取该旧历月朔日所对宿→自朔日宿按旧历日数前进——需朔日值宿锚,
// 逐字锚表待纸本核 → 本子系统不自算本命宿,由调用方传入(或用户择宿),仅算三九/相性。
export const BENMING_XIU_NOTE = '本命宿=旧历月朔日之宿顺数生日数;朔日值宿锚表待纸本《宿曜经》,本期由用户指定本命宿再算三九/相性。';
