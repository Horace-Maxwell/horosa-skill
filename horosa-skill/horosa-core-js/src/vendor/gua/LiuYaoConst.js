// 六爻纳甲断卦常量底座(WP-B/C/D/E/F/H)。移植自《六爻纳甲完整复原手册》liuyao_engine.py,纯数据、确定性。
// 分歧点(土长生水土/火土同宫、月破口径等)做成可切换设置而非替代(见 LiuYaoEngine + GuaZhanMain.settings)。

import { randomNum } from './guaHelper.js';

export const DIZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
export const TIANGAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];

export const ZHI_WUXING = { 子: '水', 丑: '土', 寅: '木', 卯: '木', 辰: '土', 巳: '火', 午: '火', 未: '土', 申: '金', 酉: '金', 戌: '土', 亥: '水' };
export const ZHI_YINYANG = { 子: '阳', 丑: '阴', 寅: '阳', 卯: '阴', 辰: '阳', 巳: '阴', 午: '阳', 未: '阴', 申: '阳', 酉: '阴', 戌: '阳', 亥: '阴' };
export const GAN_WUXING = { 甲: '木', 乙: '木', 丙: '火', 丁: '火', 戊: '土', 己: '土', 庚: '金', 辛: '金', 壬: '水', 癸: '水' };

export const WUXING_SHENG = { 木: '火', 火: '土', 土: '金', 金: '水', 水: '木' }; // 键生值
export const WUXING_KE = { 木: '土', 土: '水', 水: '火', 火: '金', 金: '木' };     // 键克值

// 地支关系
export const LIUCHONG = { 子: '午', 午: '子', 丑: '未', 未: '丑', 寅: '申', 申: '寅', 卯: '酉', 酉: '卯', 辰: '戌', 戌: '辰', 巳: '亥', 亥: '巳' };
export const LIUHE = { 子: '丑', 丑: '子', 寅: '亥', 亥: '寅', 卯: '戌', 戌: '卯', 辰: '酉', 酉: '辰', 巳: '申', 申: '巳', 午: '未', 未: '午' };
export const SANHE = { 申子辰: '水', 亥卯未: '木', 寅午戌: '火', 巳酉丑: '金' };
export const SANHUI = { 寅卯辰: '木', 巳午未: '火', 申酉戌: '金', 亥子丑: '水' };
export const HAI = { 子: '未', 未: '子', 丑: '午', 午: '丑', 寅: '巳', 巳: '寅', 卯: '辰', 辰: '卯', 申: '亥', 亥: '申', 酉: '戌', 戌: '酉' };
export const PO = { 子: '酉', 酉: '子', 午: '卯', 卯: '午', 寅: '亥', 亥: '寅', 申: '巳', 巳: '申', 辰: '丑', 丑: '辰', 戌: '未', 未: '戌' };
// 三刑:无礼(子卯)/恃势(寅巳申)/无恩(丑戌未)/自刑(辰午酉亥)
export const SANXING = { 子: '卯', 卯: '子', 寅: '巳', 巳: '申', 申: '寅', 丑: '戌', 戌: '未', 未: '丑', 辰: '辰', 午: '午', 酉: '酉', 亥: '亥' };
export function isXing(a, b){ return !!a && !!b && (SANXING[a] === b || SANXING[b] === a); }

// 十二长生
export const CHANGSHENG_STAGES = ['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养'];
export const CHANGSHENG_START = { 金: '巳', 木: '亥', 水: '申', 火: '寅', 土: '申' };       // 主流:水土同宫(申)
export const CHANGSHENG_START_ALT = { 金: '巳', 木: '亥', 水: '申', 火: '寅', 土: '寅' };   // 异说:火土同宫(寅)

// 卦五行 / 卦→后天九宫(显示用)
export const GUA_WUXING = { 乾: '金', 兑: '金', 离: '火', 震: '木', 巽: '木', 坎: '水', 艮: '土', 坤: '土' };
export const GUA_HOUTIAN = { 坎: 1, 坤: 2, 震: 3, 巽: 4, 乾: 6, 兑: 7, 艮: 8, 离: 9 };

// 京房八宫·卦序类型 + 世/应爻位(1-6,自下而上)。moving=相对本宫首卦的变爻集(用于 XOR 掩码匹配)。
export const PALACE_TYPES = [
	{ type: '本宫', moving: [], shi: 6, ying: 3 },
	{ type: '一世', moving: [1], shi: 1, ying: 4 },
	{ type: '二世', moving: [1, 2], shi: 2, ying: 5 },
	{ type: '三世', moving: [1, 2, 3], shi: 3, ying: 6 },
	{ type: '四世', moving: [1, 2, 3, 4], shi: 4, ying: 1 },
	{ type: '五世', moving: [1, 2, 3, 4, 5], shi: 5, ying: 2 },
	{ type: '游魂', moving: [1, 2, 3, 5], shi: 4, ying: 1 },
	{ type: '归魂', moving: [5], shi: 3, ying: 6 },
];

// 六神(按日干起)
export const LIUSHEN_CYCLE = ['青龙', '朱雀', '勾陈', '螣蛇', '白虎', '玄武'];
export const LIUSHEN_START = { 甲: '青龙', 乙: '青龙', 丙: '朱雀', 丁: '朱雀', 戊: '勾陈', 己: '螣蛇', 庚: '白虎', 辛: '白虎', 壬: '玄武', 癸: '玄武' };

// ── 大衍蓍草起卦(WP-I):一爻概率 老阳3/少阳5/少阴7/老阴1(共16);老阳老阴为动爻(异于三钱 老阳老阴各1/8) ──
export function yarrowYaoFromRoll(r){
	const n = ((r % 16) + 16) % 16;
	if(n < 3){ return { value: 1, change: true }; }   // 老阳(9)
	if(n < 8){ return { value: 1, change: false }; }  // 少阳(7)
	if(n < 15){ return { value: 0, change: false }; } // 少阴(8)
	return { value: 0, change: true };                // 老阴(6)
}
export function yarrowYao(){ return yarrowYaoFromRoll(randomNum() % 16); }

// 工具
export function wuxingOf(zhi){ return ZHI_WUXING[zhi] || ''; }
// a 对 b 的生克关系:'生'(a生b)/'泄'(b生a,a泄气)/'克'(a克b)/'耗'(b克a,a受克)/'同'(比和)/''
export function shengKe(a, b){
	if(!a || !b){ return ''; }
	if(a === b){ return '同'; }
	if(WUXING_SHENG[a] === b){ return '生'; }
	if(WUXING_SHENG[b] === a){ return '泄'; }
	if(WUXING_KE[a] === b){ return '克'; }
	if(WUXING_KE[b] === a){ return '耗'; }
	return '';
}
// 十二长生:某五行在某地支的长生阶段(土两说由 tuMode 决定:'water'水土同宫/'fire'火土同宫/'off'不标)
export function changshengStage(wuxing, zhi, tuMode){
	if(!wuxing || !zhi || tuMode === 'off'){ return ''; }
	const startMap = (tuMode === 'fire') ? CHANGSHENG_START_ALT : CHANGSHENG_START;
	const start = startMap[wuxing];
	if(!start){ return ''; }
	const s = DIZHI.indexOf(start), z = DIZHI.indexOf(zhi);
	if(s < 0 || z < 0){ return ''; }
	// 阳顺阴逆?六爻通用阳干顺行十二长生;此处按五行阳为主顺行(主流)
	return CHANGSHENG_STAGES[((z - s) % 12 + 12) % 12];
}
