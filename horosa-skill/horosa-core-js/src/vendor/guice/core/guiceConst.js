// 皇极轨策 · 常量层 —— 全整数、零浮点、零星历依赖。
//
// 术数出《皇极经世》一脉：以八卦正数配策数(阳36/阴24)、轨数(阳128/阴112)，
// 由本卦与动爻演出策数与轨数，除万取千百十零，立于元会运世之下断之。
//
// 🔴 本层只出常量，凡可由规则派生者一律派生、不硬编（如大定卦策 = 120 + 先天数×6）——
//    硬编即失去「规则自证」，古籍印本之误将随之固化（诸表已见此类：某卦策印本与规则相左）。
import { Gua8 } from '../../gua/GuaConst.js';

// ── 八卦正数 ─────────────────────────────────────────────
// 先天正数 = Gua8 之序 +1（Gua8 本为先天序且 bottom-first，故零适配）
export const XIANTIAN_NUM = Gua8.reduce((m, g, i) => { m[g.name] = i + 1; return m; }, {});
// 后天正数：坎1 坤2 震3 巽4 [5=寄宫] 乾6 兑7 艮8 离9 [10=寄宫]
// 五与十无卦可配 → 为寄宫之槽，其所寄之卦有异说，见 JI_GONG_MODES。
export const HOUTIAN_NUM = { 坎: 1, 坤: 2, 震: 3, 巽: 4, 乾: 6, 兑: 7, 艮: 8, 离: 9 };
export const JI_GONG_SLOTS = [5, 10];

// ── 策数与轨数 ───────────────────────────────────────────
export const CE_YANG = 36;
export const CE_YIN = 24;
export const GUI_YANG = 128;
export const GUI_YIN = 112;
/** 单卦原策/原轨：由爻之阴阳派生（阳爻取阳策、阴爻取阴策，三爻之和） */
const triSum = (name, ya, yi) => Gua8.find((g) => g.name === name).value.reduce((s, b) => s + (b ? ya : yi), 0);
export const DAN_GUA_CE = Gua8.reduce((m, g) => { m[g.name] = triSum(g.name, CE_YANG, CE_YIN); return m; }, {});
export const DAN_GUA_GUI = Gua8.reduce((m, g) => { m[g.name] = triSum(g.name, GUI_YANG, GUI_YIN); return m; }, {});

// ── 五行生成数（先天）：一六坎水 二七离火 三震八巽木 四兑九乾金 五坤十艮土 ──
export const WUXING_SHENGCHENG = {
	1: { gua: '坎', wuxing: '水' }, 6: { gua: '坎', wuxing: '水' },
	2: { gua: '离', wuxing: '火' }, 7: { gua: '离', wuxing: '火' },
	3: { gua: '震', wuxing: '木' }, 8: { gua: '巽', wuxing: '木' },
	4: { gua: '兑', wuxing: '金' }, 9: { gua: '乾', wuxing: '金' },
	5: { gua: '坤', wuxing: '土' }, 10: { gua: '艮', wuxing: '土' },
};

// ── 九畴数（大定用）：一艮二兑崇，三坎四离同，五震六巽位，八坤九干逢，
//    非惟七借巽，十亦借艮宫 ── 七与十无本卦 → 借位（借之所在由口诀自载，非推定）
export const JIUCHOU_NUM = { 艮: 1, 兑: 2, 坎: 3, 离: 4, 震: 5, 巽: 6, 坤: 8, 乾: 9 };
export const JIUCHOU_BY_DIGIT = { 1: '艮', 2: '兑', 3: '坎', 4: '离', 5: '震', 6: '巽', 7: '巽', 8: '坤', 9: '乾', 10: '艮' };
export const JIUCHOU_BORROWED = { 7: '巽', 10: '艮' };   // 七借巽、十借艮

// ── 五与十之寄宫：三法并存（两部古籍所载正相反，故不自裁）──────────
// 刚日=阳日(甲丙戊庚壬)、柔日=阴日(乙丁己辛癸)。默认取动态法：两书卷末均载之。
// 🔴 仅影响「数字→卦」，不影响策数与轨数。
export const JI_GONG_MODES = {
	ganrou: { label: '刚柔日动态（默认）', desc: '刚日五寄艮、十寄坤；柔日五寄坤、十寄艮' },
	wuGen: { label: '五寄艮·十寄坤', desc: '' },
	wuKun: { label: '五寄坤·十寄艮', desc: '' },
};
export const GANG_GAN = ['甲', '丙', '戊', '庚', '壬'];

// ── 四位取象：千=元 百=会 十=运 零=世 ───────────────────
export const SIWEI_XIANG = [
	{ wei: '千', yhys: '元', shi: '春', xiang: '性', qu: '来历', ren: '祖宗根基' },
	{ wei: '百', yhys: '会', shi: '夏', xiang: '情', qu: '内·左·后', ren: '父兄师友' },
	{ wei: '十', yhys: '运', shi: '秋', xiang: '形体', qu: '主本·事意', ren: '己身妻妾' },
	{ wei: '零', yhys: '世', shi: '冬', xiang: '气·性情', qu: '右·前', ren: '子孙奴仆' },
];
// 隔位相借：无千则借十，无百则借零，无十则借千，无零则借百
export const JIEWEI_XIANGJIE = { 千: '十', 百: '零', 十: '千', 零: '百' };

// ── 元会运世：1元=12会=360运=4320世=129600年 ────────────
export const YUAN_HUI_YUN_SHI = { hui: 12, yun: 360, shi: 4320, nian: 129600 };

// ── 卦气旺衰（三处所载一致）────────────────────────────
export const GUA_QI_WANG = {
	春: ['震', '巽'], 夏: ['离'], 秋: ['乾', '兑'], 冬: ['坎'], 四季: ['坤', '艮'],
};
export const GUA_QI_SHUAI = {
	春: ['坤', '艮'], 夏: ['乾', '兑'], 秋: ['震', '巽'], 冬: ['离'], 四季: ['坎'],
};
export const SIJI_ZHI = ['辰', '戌', '丑', '未'];   // 四季月（坤艮旺、坎衰）

// ── 大定卦策：120 + 先天数×6（由规则派生 —— 印本某卦之数与此规则相左，
//    而余七卦皆合 → 以规则为准，不硬编印本之数）─────────────
export const DADING_GUA_CE = Gua8.reduce((m, g, i) => { m[g.name] = 120 + (i + 1) * 6; return m; }, {});

// ── 大定阴阳策 ─────────────────────────────────────────
export const YINYANG_CE = {
	老阳: ['子', '寅', '辰'], 老阴: ['未', '酉', '亥'],
	少阳: ['午', '申', '戌'], 少阴: ['丑', '卯', '巳'],
};
export const YINYANG_CE_JIA = { 老胜: 720, 少胜: 360, 相等: 720 };   // 相等则从阳

// ── 大定克岁数（以九畴数除之）─────────────────────────
export const KE_SUI_SHU = [
	{ gan: ['甲', '乙'], gua: ['乾', '兑'], num: 11 },
	{ gan: ['丙', '丁'], gua: ['坎'], num: 3 },
	{ gan: ['戊', '己'], gua: ['震', '巽'], num: 11 },
	{ gan: ['庚', '辛'], gua: ['离'], num: 4 },
	{ gan: ['壬', '癸'], gua: ['坤', '艮'], num: 9 },
];

// ── 十二辟卦（消息卦）─────────────────────────────────
export const SHIER_BIGUA = [
	{ zhi: '子', gua: '复', xiao: '一阳生' }, { zhi: '丑', gua: '临', xiao: '二阳' },
	{ zhi: '寅', gua: '泰', xiao: '三阳' }, { zhi: '卯', gua: '大壮', xiao: '四阳' },
	{ zhi: '辰', gua: '夬', xiao: '五阳' }, { zhi: '巳', gua: '乾', xiao: '六阳' },
	{ zhi: '午', gua: '姤', xiao: '一阴生' }, { zhi: '未', gua: '遁', xiao: '二阴' },
	{ zhi: '申', gua: '否', xiao: '三阴' }, { zhi: '酉', gua: '观', xiao: '四阴' },
	{ zhi: '戌', gua: '剥', xiao: '五阴' }, { zhi: '亥', gua: '坤', xiao: '六阴' },
];

// ── 体用生克 ───────────────────────────────────────────
export const TIYONG_SHENGKE = {
	用生体: { label: '用生体', duan: '助力', ji: 2 },
	体克用: { label: '体克用', duan: '阻力，费力可成', ji: 1 },
	比和: { label: '比和', duan: '吉', ji: 2 },
	体生用: { label: '体生用', duan: '耗损无成', ji: -1 },
	用克体: { label: '用克体', duan: '破败大凶', ji: -2 },
};

// ── 体用四诀之「轻重次序」：用最紧 > 互次之 > 变又次之 ──────
export const TIYONG_QINGZHONG = [
	{ key: 'yong', label: '用卦', ying: '即应', zhong: 3 },
	{ key: 'hu', label: '互卦', ying: '中间之应', zhong: 2 },
	{ key: 'bian', label: '变卦', ying: '终应', zhong: 1 },
];

// ── 三要十应：三套名目并存（所载不同，故可切）──────────
export const SHIYING_SETS = {
	xinyifawei: {
		label: '心易发微版（默认）',
		items: [
			{ key: 'zheng', label: '正应', auto: true }, { key: 'hu', label: '互应', auto: true },
			{ key: 'bian', label: '变应', auto: true }, { key: 'fang', label: '方应' },
			{ key: 'ri', label: '日应' }, { key: 'wai', label: '外应' },
			{ key: 'wu', label: '物应' }, { key: 'tianwen', label: '天文' },
			{ key: 'dili', label: '地理' }, { key: 'renshi', label: '人事' },
		],
	},
	meihua: {
		label: '梅花原书版',
		note: '以体卦为主，内外卦参看：内不吉而外吉可解、内吉而外不吉反破',
		items: [
			{ key: 'tianshi', label: '天时' }, { key: 'dili', label: '地理' },
			{ key: 'renshi', label: '人事' }, { key: 'shiling', label: '时令' },
			{ key: 'fanggua', label: '方卦' }, { key: 'dongwu', label: '动物' },
			{ key: 'jingwu', label: '静物' }, { key: 'yanyu', label: '言语' },
			{ key: 'shengyin', label: '声音' }, { key: 'wuse', label: '五色' },
		],
	},
	rizhen: {
		label: '论事十大应·日辰秘文版',
		items: [
			{ key: 'xing', label: '行' }, { key: 'li', label: '立' }, { key: 'zuo', label: '坐' },
			{ key: 'wo', label: '卧' }, { key: 'yu', label: '语' }, { key: 'mo', label: '默' },
			{ key: 'xi', label: '喜' }, { key: 'nu', label: '怒' },
			{ key: 'de', label: '得' }, { key: 'shi', label: '失' },
		],
	},
};

// ── 六十甲子天地立成定数：两表并存（所载完全不同，故可切）────
// 默认取心易发微表 —— 唯一完整占例之演算实取此表（用另一表其数与书中演算对不上）。
export { LIUSHIJIAZI_DINGSHU } from './guiceJiaziShu.js';

// ── 动静（体用四诀之一）────────────────────────────────
export const DONGJING = {
	静: ['体卦', '互卦', '中方应', '天时', '地理'],
	动: ['用卦', '变卦', '人事', '器物'],
	应期: { 坐: '应迟', 行: '应速', 立: '半迟半速' },
	qiGuaYaoQiu: '起卦须一动一静方成卦',
};

export default {
	XIANTIAN_NUM, HOUTIAN_NUM, DAN_GUA_CE, DAN_GUA_GUI, WUXING_SHENGCHENG,
	JIUCHOU_NUM, SIWEI_XIANG, JIEWEI_XIANGJIE, YUAN_HUI_YUN_SHI, SHIER_BIGUA,
};
