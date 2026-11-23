// 三式合一页:常量表与左栏选项(地支 / 天干序、盘环布局、奇门 / 六壬 / 太乙选项、页面设置登记、重算键、尺寸与延迟)。
// 从 SanShiUnitedMain.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import * as AstroConst from '../sanshiAstroConst.js';
import { migrateLegacyQimenSchool, TUIYAN_VIEW_OPTIONS, TUIYAN_GONG_OPTIONS, PAIPAN_OPTIONS, ZHISHI_OPTIONS, YUEJIA_QIJU_OPTIONS, QIJU_METHOD_OPTIONS, SCHOOL_OPTIONS, KONG_MODE_OPTIONS, MA_MODE_OPTIONS, ZHIRUN_LEAP_OPTIONS, GODS_PRESET_OPTIONS, JIGONG_MODE_OPTIONS, ANGAN_MODE_OPTIONS, SHIFT_ZHIFU_OPTIONS, YEARJIA_JU_OPTIONS, DAYJIA_JU_OPTIONS, KEJIA_FENDUN_OPTIONS, JINHAN_MENPAI_OPTIONS } from '../../dunjia/DunJiaCalc.js';
import { definePageSettings } from '../../utils/pageSettingsStore.js';
import { TAIYI_STYLE_OPTIONS, TAIYI_ACCUM_OPTIONS } from '../../taiyi/core/TaiYiCore.js';
import { TIME_BASIS_OPTIONS as TAIYI_TIME_BASIS_OPTIONS } from '../../taiyi/TaiYiCalc.js';
import { DEFAULT_TAIYI_SCHOOL, TAIYI_SCHOOL_OPTIONS } from '../../taiyi/core/taiyiSchool.js';
import { ASC_RA_MODE_DEFAULT, ASC_RA_MODE_OPTIONS } from '../../utils/ascRaMode.js';

export const BRANCH_ORDER = '子丑寅卯辰巳午未申酉戌亥'.split('');

export const STEM_ORDER = '甲乙丙丁戊己庚辛壬癸'.split('');

export const BRANCH_ZODIAC_MAP = {
	子: '水瓶座',
	丑: '摩羯座',
	寅: '射手座',
	卯: '天蝎座',
	辰: '天秤座',
	巳: '处女座',
	午: '狮子座',
	未: '巨蟹座',
	申: '双子座',
	酉: '金牛座',
	戌: '白羊座',
	亥: '双鱼座',
};

export const BRANCH_SIGN_ID_MAP = {
	子: AstroConst.AQUARIUS,
	丑: AstroConst.CAPRICORN,
	寅: AstroConst.SAGITTARIUS,
	卯: AstroConst.SCORPIO,
	辰: AstroConst.LIBRA,
	巳: AstroConst.VIRGO,
	午: AstroConst.LEO,
	未: AstroConst.CANCER,
	申: AstroConst.GEMINI,
	酉: AstroConst.TAURUS,
	戌: AstroConst.ARIES,
	亥: AstroConst.PISCES,
};

export function normalizeKenQimenOptions(options){
	const next = {
		...(options || {}),
	};
	// 旧数据迁移(对齐独立 DunJiaMain,单源 migrateLegacyQimenSchool):阴盘曾为「盘式」(school='阴盘'),现为「起局法」(qijuMethod='shuzi',报数定局)。
	return migrateLegacyQimenSchool(next);
}

export const SANSHI_PALACE_EXPORT_ORDER = [
	{ title: '正北坎宫', palaceNum: 8, branches: ['子'] },
	{ title: '东北艮宫', palaceNum: 7, branches: ['丑', '寅'] },
	{ title: '正东震宫', palaceNum: 4, branches: ['卯'] },
	{ title: '东南巽宫', palaceNum: 1, branches: ['辰', '巳'] },
	{ title: '正南离宫', palaceNum: 2, branches: ['午'] },
	{ title: '西南坤宫', palaceNum: 3, branches: ['未', '申'] },
	{ title: '正西兑宫', palaceNum: 6, branches: ['酉'] },
	{ title: '西北乾宫', palaceNum: 9, branches: ['戌', '亥'] },
];

export const QIMEN_OPTIONS = {
	sex: 1,
	dateType: 0,
	leapMonthType: 0,
	xuShiSuiType: 0,
	jieQiType: 1,
	paiPanType: 3,
	zhiShiType: 0,
	yueJiaQiJuType: 0,
	yearGanZhiType: 2,
	monthGanZhiType: 1,
	dayGanZhiType: 0,
	qijuMethod: 'zhirun',
	kongMode: 'day',
	yimaMode: 'day',
	shiftPalace: 0,
	fengJu: false,
	school: '转盘',
	shuziReportNumber: '',
	zhirunLeapDays: 9,
	chartCategory: 'shi',   // 盘类(事局/命局):此前三式完全缺失,挂载齿轮却经 reTagSanshi 暴露=调了不消费
	faRelatedPeople: '',    // 相关人员(法奇门必护天干消费):此前三式缺失
	godsPreset: 'baihu_xuanwu',   // 八神预设
	anGanMode: 'off',             // 暗干六法
	showAnZhi: false,
	showJiGan: false,             // 寄干显示(中五干寄宫)
	showTianQin: false,           // 天禽显示(随寄宫之星)
	tuiYanView: 'off',            // 推演显示:翻宫 / 转宫(纯显示)
	tuiYanGong: 'shigan',         // 推演用神宫
	showJianChu: false,           // 十二建星(建除十二神):盘外圈地支旁 + 右栏卡
	jiGongMode: 'kun',
	feiXingShun: false,
	feiMenShun: false,
	feiShenShun: false,
	feiMenZhongCan: true,
	feiMenZhongShow: false,
	mixTian: '',
	mixXing: '',
	mixMen: '',
	mixShen: '',
	kongMarkBoth: false,
	showAllKong: false,
	shiftZhiFuMode: 'follow',
	dayJiaJu: 'yiyuan',
	keJiaFenDun: 'zihou',
	keZiZhengHuanShi: false,
	jinhanMenPai: 'book',
	yearJiaJu: 'sanyuan',
};

export const OUTER_RING_LAYOUT = [
	{ branch: '巳', side: 'top', x0: 11.1, x1: 33.33, y0: 0, y1: 11.1 },
	{ branch: '午', side: 'top', x0: 33.33, x1: 66.67, y0: 0, y1: 11.1 },
	{ branch: '未', side: 'top', x0: 66.67, x1: 88.9, y0: 0, y1: 11.1 },
	{ branch: '申', side: 'right', x0: 88.9, x1: 100, y0: 11.1, y1: 33.33 },
	{ branch: '酉', side: 'right', x0: 88.9, x1: 100, y0: 33.33, y1: 66.67 },
	{ branch: '戌', side: 'right', x0: 88.9, x1: 100, y0: 66.67, y1: 88.9 },
	{ branch: '亥', side: 'bottom', x0: 66.67, x1: 88.9, y0: 88.9, y1: 100 },
	{ branch: '子', side: 'bottom', x0: 33.33, x1: 66.67, y0: 88.9, y1: 100 },
	{ branch: '丑', side: 'bottom', x0: 11.1, x1: 33.33, y0: 88.9, y1: 100 },
	{ branch: '寅', side: 'left', x0: 0, x1: 11.1, y0: 66.67, y1: 88.9 },
	{ branch: '卯', side: 'left', x0: 0, x1: 11.1, y0: 33.33, y1: 66.67 },
	{ branch: '辰', side: 'left', x0: 0, x1: 11.1, y0: 11.1, y1: 33.33 },
];

// 虚实红绿点逐宫定位:贴各地支宫格「朝盘心」一侧——上边内侧=下、下边内侧=上、左边内侧=右、右边内侧=左;
// 每边的中宫(午/子/卯/酉)居中,两侧夹角宫朝该边中心收拢(与用户口径一致)。值为单元格内 CSS 绝对定位。
export const WEAK_SOLID_POS = {
	// 上边(内侧=下):巳→右下、午→居中、未→左下
	'巳': { bottom: 2, right: 3 },
	'午': { bottom: 2, left: '50%', transform: 'translateX(-50%)' },
	'未': { bottom: 2, left: 3 },
	// 右边(内侧=左):申→左下、酉→居中、戌→左上
	'申': { left: 2, bottom: 3 },
	'酉': { left: 2, top: '50%', transform: 'translateY(-50%)' },
	'戌': { left: 2, top: 3 },
	// 下边(内侧=上):亥→左上、子→居中、丑→右上
	'亥': { top: 2, left: 3 },
	'子': { top: 2, left: '50%', transform: 'translateX(-50%)' },
	'丑': { top: 2, right: 3 },
	// 左边(内侧=右):辰→右下、卯→居中、寅→右上
	'寅': { right: 2, top: 3 },
	'卯': { right: 2, top: '50%', transform: 'translateY(-50%)' },
	'辰': { right: 2, bottom: 3 },
};

export const LIURENG_RING_LAYOUT = {
	// 四正位：放在六壬环四边中央（合并后的主宫位）
	午: { left: '50%', top: '27.8%', kind: 'cardinal' },
	酉: { left: '72.2%', top: '50%', kind: 'cardinal' },
	子: { left: '50%', top: '72.2%', kind: 'cardinal' },
	卯: { left: '27.8%', top: '50%', kind: 'cardinal' },

	// 四角八三角：落点使用各三角形重心，确保文字在三角区域内
	巳: { left: '29.6%', top: '25.9%', kind: 'corner' }, // 西北角-上三角
	辰: { left: '25.9%', top: '29.6%', kind: 'corner' }, // 西北角-下三角

	未: { left: '70.4%', top: '25.9%', kind: 'corner' }, // 东北角-上三角
	申: { left: '74.1%', top: '29.6%', kind: 'corner' }, // 东北角-下三角

	戌: { left: '74.1%', top: '70.4%', kind: 'corner' }, // 东南角-上三角
	亥: { left: '70.4%', top: '74.1%', kind: 'corner' }, // 东南角-下三角

	丑: { left: '29.6%', top: '74.1%', kind: 'corner' }, // 西南角-下三角
	寅: { left: '25.9%', top: '70.4%', kind: 'corner' }, // 西南角-上三角
};

// needJieqiYearSeed 已收编到 DunJiaCalc(独立页/三式/择日单源;此前三式只认「时家+置闰」→ 日家/金函/飞混茅山无闰/刻家不取种子局错)。

export const QIMEN_RING_POSITIONS = {
	1: { left: '16.7%', top: '16.7%' },
	2: { left: '50%', top: '16.7%' },
	3: { left: '83.3%', top: '16.7%' },
	4: { left: '16.7%', top: '50%' },
	6: { left: '83.3%', top: '50%' },
	7: { left: '16.7%', top: '83.3%' },
	8: { left: '50%', top: '83.3%' },
	9: { left: '83.3%', top: '83.3%' },
};

export const QIMEN_CORNER_PALACES = new Set([1, 3, 7, 9]);

export const MAIN_STAR_IDS = new Set([
	AstroConst.SUN,
	AstroConst.MOON,
	AstroConst.MERCURY,
	AstroConst.VENUS,
	AstroConst.MARS,
	AstroConst.JUPITER,
	AstroConst.SATURN,
	AstroConst.URANUS,
	AstroConst.NEPTUNE,
	AstroConst.PLUTO,
	AstroConst.ASC,
	AstroConst.MC,
]);

export const GAME_TYPE_OPTIONS = [
	{ value: 'ming', label: '命局' },
	{ value: 'shi', label: '事局' },
];

export const TIME_ALG_OPTIONS = [
	{ value: 0, label: '真太阳时' },
	{ value: 1, label: '直接时间' },
];

export const SEX_OPTIONS = [
	{ value: 1, label: '男' },
	{ value: 0, label: '女' },
];

export const GUIRENG_OPTIONS = [
	{ value: 0, label: '六壬法贵人' },
	{ value: 1, label: '遁甲法贵人' },
	{ value: 2, label: '星占法贵人' },
	{ value: 3, label: '甲戊兼牛羊' },
	{ value: 4, label: '干合阳阴贵' },
];

// 大六壬流派(对齐独立 lrzhan/LiuRengMain 的「断卦设置」;默认值=现行行为,零回归)。
// 换将三派/分昼夜三派/涉害取舍·起讫·始入(默认法)/年神排序/昼夜阳阴归属/土旺衰。
export const LR_YUEJIANG_OPTIONS = [
	{ value: 'zhongqi', label: '中气过宫（默认）' },
	{ value: 'jieqi', label: '节气换将' },
	{ value: 'richan', label: '太阳过宫·日躔（含岁差）', short: '日躔（含岁差）' },
];

export const LR_FENZHOUYE_OPTIONS = [
	{ value: 'chenhun', label: '晨昏分昼夜（默认）' },
	{ value: 'maoyou', label: '卯酉分昼夜' },
	{ value: 'yinshen', label: '寅申分昼夜' },
];

export const LR_SEHAI_METHOD_OPTIONS = [
	{ value: 'app', label: '仅下贼上(默认)' },
	{ value: 'standard', label: '标准深浅两向' },
	{ value: 'mengzhongji', label: '直取孟仲季' },
];

export const LR_SEHAI_BOUNDARY_OPTIONS = [
	{ value: 'app', label: '计起点不计本家(默认)' },
	{ value: 'both', label: '两端皆计' },
	{ value: 'neither', label: '皆不计' },
];

export const LR_SHIRUKE_OPTIONS = [
	{ value: 0, label: '并入重审(默认)' },
	{ value: 1, label: '单列·九法变十法' },
];

export const LR_YEAR_SHENSHA_OPTIONS = [
	{ value: 'sanyuan', label: '四利三元序(默认)' },
	{ value: 'suigui', label: '太岁排轮(太阴异)' },
];

export const LR_YINYANG_SYSTEM_OPTIONS = [
	{ value: 'danmu', label: '旦暮系(默认)' },
	{ value: 'yinyang', label: '星历阳阴系' },
];

export const LR_TUWANG_OPTIONS = [
	{ value: 'siji', label: '四季月土旺(默认)' },
	{ value: 'huotu', label: '火土同宫(土随火)' },
];

// 奇门封局(对齐独立 dunjia/DunJiaMain;默认未封局=零回归)。
export const QIMEN_FENGJU_OPTIONS = [
	{ value: 0, label: '未封局' },
	{ value: 1, label: '已封局' },
];

// 排盘设置跨会话保留(用户实报:排盘设置改了之后每次重开软件都要重设)。三式合一与独立六壬 / 奇门 / 太乙同改(三式同步铁律):
// 奇门层、太乙层、六壬层的口径 / 流派 / 显示偏好全收。不进的:模式与盘类(这盘是命局还是事局,逐盘)、性别(随命主)、
// 报数 / 法奇门相关人(每课输入)、移星 / 封局(逐盘操作)、23 点换日 / 晚子时(归全局设置管)、黄道 / 分宫制(跨页共享的星盘字段)。
// 「时间算法」没保存过时照旧跟随共享字段现值(loadSaved 只给确实保存过的键)。
// 只在用户亲手改控件时落盘:事盘回灌 / 宿主下发 / 全局广播都不落盘。
// 🔴 只有**独立三式页**读写这份保存值;三式择日里内嵌的那份既不读也不写(见 usesSavedSettings):择日工作台只下发它自己定义过的键、
// 其余按扫描引擎缺省判,内嵌盘若继承了独立页保存的盘式 / 排盘 / 太乙盘式 / 涉害口径,点选命中行看到的盘就不是扫描判定的那一盘。
const optVals = (list)=>list.map((o)=>o.value);

export const SANSHI_PAGE_SETTINGS = definePageSettings('horosa.sanshi.settings.v1', {
	timeAlg: { def: 0, oneOf: optVals(TIME_ALG_OPTIONS) },
	guireng: { def: 2, oneOf: optVals(GUIRENG_OPTIONS) },
	// 奇门层
	paiPanType: { def: 3, oneOf: optVals(PAIPAN_OPTIONS) },
	zhiShiType: { def: 0, oneOf: optVals(ZHISHI_OPTIONS) },
	yueJiaQiJuType: { def: 0, oneOf: optVals(YUEJIA_QIJU_OPTIONS) },
	// 候选随排盘体例增减(时家 / 刻家 5 档,其余 2 档),全集固定。阴盘(报数定局)离不开每一课的报数,不进候选(与奇门页同):
	// 选了照常用,只是不记 —— 否则重开后标签写阴盘、报数是空的,实际按拆补起局
	qijuMethod: { def: 'zhirun', oneOf: optVals(QIJU_METHOD_OPTIONS).filter((v)=>v !== 'shuzi') },
	school: { def: '转盘', oneOf: optVals(SCHOOL_OPTIONS) },
	kongMode: { def: 'day', oneOf: optVals(KONG_MODE_OPTIONS) },
	yimaMode: { def: 'day', oneOf: optVals(MA_MODE_OPTIONS) },
	zhirunLeapDays: { def: 9, oneOf: optVals(ZHIRUN_LEAP_OPTIONS) },
	godsPreset: { def: 'baihu_xuanwu', oneOf: optVals(GODS_PRESET_OPTIONS) },
	jiGongMode: { def: 'kun', oneOf: optVals(JIGONG_MODE_OPTIONS) },
	anGanMode: { def: 'off', oneOf: optVals(ANGAN_MODE_OPTIONS) },
	shiftZhiFuMode: { def: 'follow', oneOf: optVals(SHIFT_ZHIFU_OPTIONS) },
	yearJiaJu: { def: 'sanyuan', oneOf: optVals(YEARJIA_JU_OPTIONS) },
	dayJiaJu: { def: 'yiyuan', oneOf: optVals(DAYJIA_JU_OPTIONS) },
	keJiaFenDun: { def: 'zihou', oneOf: optVals(KEJIA_FENDUN_OPTIONS) },
	jinhanMenPai: { def: 'book', oneOf: optVals(JINHAN_MENPAI_OPTIONS) },
	mixTian: { def: '', oneOf: ['', 'zhuan', 'fei'] },
	mixXing: { def: '', oneOf: ['', 'zhuan', 'fei'] },
	mixMen: { def: '', oneOf: ['', 'zhuan', 'fei'] },
	mixShen: { def: '', oneOf: ['', 'zhuan', 'fei'] },
	feiXingShun: { def: false },
	feiMenShun: { def: false },
	feiShenShun: { def: false },
	feiMenZhongCan: { def: true },
	feiMenZhongShow: { def: false },
	kongMarkBoth: { def: false },
	showAllKong: { def: false },
	keZiZhengHuanShi: { def: false },
	showAnZhi: { def: false },
	showJiGan: { def: false },
	showTianQin: { def: false },
	tuiYanView: { def: 'off', oneOf: TUIYAN_VIEW_OPTIONS.map((o)=>o.value) },
	tuiYanGong: { def: 'shigan', oneOf: TUIYAN_GONG_OPTIONS.map((o)=>o.value) },
	showJianChu: { def: false },
	// 太乙层
	taiyiStyle: { def: 3, oneOf: optVals(TAIYI_STYLE_OPTIONS) },
	taiyiAccum: { def: 0, oneOf: optVals(TAIYI_ACCUM_OPTIONS) },
	taiyiTimeBasis: { def: 'direct', oneOf: optVals(TAIYI_TIME_BASIS_OPTIONS) },
	gameTheory: { def: 0, oneOf: [0, 1] },
	taiyiSchool: { type: 'map', keys: Object.keys(DEFAULT_TAIYI_SCHOOL).reduce((acc, k)=>{
		acc[k] = { def: DEFAULT_TAIYI_SCHOOL[k], oneOf: (TAIYI_SCHOOL_OPTIONS[k] || []).map((o)=>o.value) };
		return acc;
	}, {}) },
	// 六壬层
	yueJiangMethod: { def: 'zhongqi', oneOf: optVals(LR_YUEJIANG_OPTIONS) },
	fenZhouYe: { def: 'chenhun', oneOf: optVals(LR_FENZHOUYE_OPTIONS) },
	seHaiMethod: { def: 'app', oneOf: optVals(LR_SEHAI_METHOD_OPTIONS) },
	seHaiBoundary: { def: 'app', oneOf: optVals(LR_SEHAI_BOUNDARY_OPTIONS) },
	shiRuKe: { def: false },
	yearShenShaSort: { def: 'sanyuan', oneOf: optVals(LR_YEAR_SHENSHA_OPTIONS) },
	yinyangSystem: { def: 'danmu', oneOf: optVals(LR_YINYANG_SYSTEM_OPTIONS) },
	tuWangShuai: { def: 'siji', oneOf: optVals(LR_TUWANG_OPTIONS) },
	// 外圈两项不在 options 里,是组件自己的 state(控件直接绑 this.state.X)
	outerCoord: { label: '外圈', def: 'ecliptic', oneOf: ['ecliptic', 'equatorial'] },
	showWeakSolid: { label: '虚实', def: true },
	// 外圈赤道分宫时上升点取哪一个赤经(改进 = 真赤经 / 经典 = 旧版取的东点黄经);只在外圈 = 赤道时起作用、才显示
	ascRaMode: { label: '上升取法', def: ASC_RA_MODE_DEFAULT, oneOf: ASC_RA_MODE_OPTIONS.map((o)=>o.value) },
});

// 🔴 改值即强制重算的「计算型」option key 全集(三式合一各子盘的盘面计算输入)。
// 这些 key 都已被 recalcSignature(performRecalcByNongli)消费(经 getQimenOptions / getKintaiyiPan / 六壬 castOverride),
// 但 refreshAll 的轻量 lastKey 不含它们 → 必须在 onOptionChange 显式 refreshAll(force) 才会真重算重画。
// after23NewDay/lateZiHourUseNextDay 已在上方单独处理(还要 prefetch),故不入本集;mode(命局/事局)只管保存去向(命盘/事盘),不改盘,亦不入。
export const SANSHI_RECALC_OPTION_KEYS = new Set([
	// 奇门(经 getQimenOptions + fetchQimenPan/calcDunJia)
	'paiPanType', 'zhiShiType', 'yueJiaQiJuType', 'qijuMethod', 'kongMode', 'yimaMode', 'shiftPalace',
	'school', 'shuziReportNumber', 'fengJu', 'zhirunLeapDays', 'chartCategory', 'faRelatedPeople',
	'godsPreset', 'anGanMode', 'showAnZhi', 'jiGongMode', 'showJiGan', 'showTianQin', 'tuiYanView', 'tuiYanGong',
	'feiXingShun', 'feiMenShun', 'feiShenShun', 'feiMenZhongCan', 'feiMenZhongShow',
	'mixTian', 'mixXing', 'mixMen', 'mixShen',
	'kongMarkBoth', 'showAllKong', 'shiftZhiFuMode',
	'dayJiaJu', 'keJiaFenDun', 'keZiZhengHuanShi',
	'jinhanMenPai',
	'yearJiaJu',
	// 太乙(经 getKintaiyiPan + applyTaiyiSchool)
	'taiyiStyle', 'taiyiAccum', 'taiyiSchool', 'gameTheory', 'taiyiTimeBasis',   // 太乙时间基准(与独立太乙页同源选项)
	// 大六壬(经 guirengType + buildSanshiLiuRengCastOverride)
	'guireng', 'yueJiangMethod', 'fenZhouYe', 'seHaiMethod', 'seHaiBoundary', 'shiRuKe',
	'yearShenShaSort', 'yinyangSystem', 'tuWangShuai',
	// 十二建星(盘外圈地支旁 + 右栏卡):不改任何子盘,但随开关进 AI 快照 → 改值也走一次重算以重存快照(否则快照停在旧值)
	'showJianChu',
]);

// 用户语义(拍板,字面直觉版): after23NewDay=1「23点算第二天」=日柱进位次日(壬寅)；=0「24点算第二天」=日柱守今(辛丑)。
export const DAY_SWITCH_OPTIONS = [
	{ value: 1, label: '23点算第二天' },
	{ value: 0, label: '24点算第二天' },
];

export const SANSHI_BOARD_MIN = 380;

export const SANSHI_BOARD_MAX = 820;

// 盘面可读底线(CSS px):放大档 × 高度不够时,盘宁可让中栏纵向滚,也不压到这个边长以下(只要栏宽放得下)。
// 380 的视觉底线在 1.8 档只剩 211 CSS px,格内字号不随盘缩 → 宫格字叠成一团;常规档盘远大于它,零变化。
export const SANSHI_BOARD_READABLE_MIN = 360;

export const SANSHI_FAST_BUDGET_MS = 2200;

// 参照盘(/chart 底盘)是别的起课时刻的时,最多等这一刻的参照盘这么久;等不到就不用参照盘落这一课(月将 / 外圈留空)
export const SANSHI_CAST_CHART_WAIT_MS = 1500;

// performRecalcByNongli 的「这一课先不落、等这一刻的参照盘」返回值(调用方据此不收加载态)
export const SANSHI_RECALC_HELD = 'held';

export const SANSHI_RECALC_DEFER_MS = 28;

export const SANSHI_SNAPSHOT_DEFER_MS = 120;

export const AI_EXPORT_PLANET_INFO = {
	showHouse: 1,
	showRuler: 1,
};
