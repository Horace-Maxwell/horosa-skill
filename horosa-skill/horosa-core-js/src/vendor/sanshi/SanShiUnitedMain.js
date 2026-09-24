
import {
	parseSnapshotSections,
	SANSHI_TAIYI_SECTION_TITLES,
	SANSHI_QIMEN_EXTRA_SECTIONS,
	SANSHI_LIURENG_DUANGUA_SECTIONS,
} from './sanshiSnapshotSections.js';
// headless stub：shellZoom 直接量 fixed 铺满元素的布局高（DOM），只服务组件构造期的 getViewportHeight；headless 无视口。
// 定义同名函数让 stub 审计看到「已知且不可达」，真被调到时抛明确错误而不是 ReferenceError。
function getLayoutViewportHeight(){ throw new Error('headless stub: utils/shellZoom is not vendored'); }




import * as AstroConst from './sanshiAstroConst.js';
import * as AstroText from './sanshiAstroText.js';
import { splitDegree, convertLatToStr, convertLonToStr } from './sanshiAstroHelper.js';




import * as LRConst from '../liureng/LRConst.js';
import ChuangChart from '../liureng/ChuangChart.js';
import { sanChuanRelationSnapshotLines } from '../liureng/LRSanChuanRelationMini.js';   // [Q-450/T-413] 三传递生递克/徽记单源(三式同步)
import {
	PAIPAN_OPTIONS,
	ZHISHI_OPTIONS,
	YUEJIA_QIJU_OPTIONS,
	QIJU_METHOD_OPTIONS,
	qijuMethodOptionsFor,
	qijuMethodSelectValue,   // [Q-161/T-79] 起局下拉单一真值源(与独立奇门页同源)
	KONG_MODE_OPTIONS,
	MA_MODE_OPTIONS,
	YIXING_OPTIONS,
	SCHOOL_OPTIONS,
	ZHIRUN_LEAP_OPTIONS,
	calcDunJia,
	normalizeKinqimenData,
	getXunHead,
	GUXU,
	isQimenLocalRoute,
	needJieqiYearSeed,
	jieqiSeedYears,
	jieqiSeedSignature,
	buildDunJiaSnapshotText,
	CHART_CATEGORY_OPTIONS,
	GODS_PRESET_OPTIONS,
	ANGAN_MODE_OPTIONS,
	JIGONG_MODE_OPTIONS,
	SHIFT_ZHIFU_OPTIONS,
	DAYJIA_JU_OPTIONS,
	KEJIA_FENDUN_OPTIONS,
	JINHAN_MENPAI_OPTIONS,
	YEARJIA_JU_OPTIONS,
} from '../dunjia/DunJiaCalc.js';

import { buildSanShiZiweiSihuaSnapshotLines } from './SanShiZiWeiSihua.js';









import {
	TAIYI_STYLE_OPTIONS,
	TAIYI_ACCUM_OPTIONS,
	buildTaiyiSnapshotLines,
} from '../taiyi/core/TaiYiCore.js';
import { buildTaiyiSnapshotText, TIME_BASIS_OPTIONS as TAIYI_TIME_BASIS_OPTIONS } from '../taiyi/TaiYiCalc.js';   // [Q-107 A] 时间基准选项与独立太乙页同源




import { applyTaiyiSchool, DEFAULT_TAIYI_SCHOOL, TAIYI_SCHOOL_OPTIONS, normalizeTaiyiSchool } from '../taiyi/core/taiyiSchool.js';
import { definePageSettings } from '../utils/pageSettingsStore.js';
import { appendPlanetHouseInfo, } from '../utils/planetHouseInfo.js';



// [Q-385/T-366] 年神排序 / 土旺衰两档此前在合一页只经 pickSanshiLiurengCastOpts 进 AI 快照,
// 页面无任何落点(帮助却称「与独立页同名同义」「改年神在右栏的排列起点」)。补右栏落点,与独立页同源同函数。





import {
	buildLiuRengReferenceBundle,
	buildReferenceDocumentText,
	buildOverviewReferenceText,
	buildLiuRengSnapshotText,
	getYueJiangByMethod,
	XIAO_JU_REFERENCE_TAB_KEYS,
	buildQiZhengItems,
	QIZHENG_PLANET_COLOR,
	QIZHENG_WUXING_COLOR,
} from '../liureng/LiuRengMain.js';
import {
	BAGONG_PALACE_ORDER,
	BAGONG_PALACE_NAME,
	buildQimenBaGongPanelData,
	XUN_SHOU_TO_LIUYI,
} from '../dunjia/DunJiaBaGongRules.js';
// 遁甲「用神 / 化解」子tab静态显示所需的派生函数与速查数据(对齐独立遁甲页同源)。








const BRANCH_ORDER = '子丑寅卯辰巳午未申酉戌亥'.split('');
const STEM_ORDER = '甲乙丙丁戊己庚辛壬癸'.split('');
const BRANCH_ZODIAC_MAP = {
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
const BRANCH_SIGN_ID_MAP = {
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
function normalizeKenQimenOptions(options){
	const next = {
		...(options || {}),
	};
	// 旧数据迁移(对齐独立 DunJiaMain):阴盘曾为「盘式」(school='阴盘'),现为「起局法」(qijuMethod='shuzi',报数定局)。
	if(next.school === '阴盘'){
		next.school = '转盘';
		next.qijuMethod = 'shuzi';
	}
	return next;
}
const SANSHI_PALACE_EXPORT_ORDER = [
	{ title: '正北坎宫', palaceNum: 8, branches: ['子'] },
	{ title: '东北艮宫', palaceNum: 7, branches: ['丑', '寅'] },
	{ title: '正东震宫', palaceNum: 4, branches: ['卯'] },
	{ title: '东南巽宫', palaceNum: 1, branches: ['辰', '巳'] },
	{ title: '正南离宫', palaceNum: 2, branches: ['午'] },
	{ title: '西南坤宫', palaceNum: 3, branches: ['未', '申'] },
	{ title: '正西兑宫', palaceNum: 6, branches: ['酉'] },
	{ title: '西北乾宫', palaceNum: 9, branches: ['戌', '亥'] },
];
const PALACE_GRID = {
	1: { row: 2, col: 2 },
	2: { row: 2, col: 3 },
	3: { row: 2, col: 4 },
	4: { row: 3, col: 2 },
	5: { row: 3, col: 3 },
	6: { row: 3, col: 4 },
	7: { row: 4, col: 2 },
	8: { row: 4, col: 3 },
	9: { row: 4, col: 4 },
};

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
	chartCategory: 'shi',   // [H-A] 盘类(事局/命局):此前三式完全缺失,挂载齿轮却经 reTagSanshi 暴露=调了不消费
	faRelatedPeople: '',    // [H-A] 相关人员(法奇门必护天干消费):此前三式缺失
	godsPreset: 'baihu_xuanwu',   // [H-B] 八神预设
	anGanMode: 'off',             // [H-B] 暗干五法
	showAnZhi: false,
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

// needJieqiYearSeed 已收编到 DunJiaCalc(独立页/三式/择日单源;[Q-155] 此前三式只认「时家+置闰」→ 日家/金函/飞混茅山无闰/刻家不取种子局错)。

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

const MAIN_STAR_IDS = new Set([
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

const GAME_TYPE_OPTIONS = [
	{ value: 'ming', label: '命局' },
	{ value: 'shi', label: '事局' },
];

const TIME_ALG_OPTIONS = [
	{ value: 0, label: '真太阳时' },
	{ value: 1, label: '直接时间' },
];

const SEX_OPTIONS = [
	{ value: 1, label: '男' },
	{ value: 0, label: '女' },
];

const GUIRENG_OPTIONS = [
	{ value: 0, label: '六壬法贵人' },
	{ value: 1, label: '遁甲法贵人' },
	{ value: 2, label: '星占法贵人' },
	{ value: 3, label: '甲戊兼牛羊' },
	{ value: 4, label: '干合阳阴贵' },
];

// 大六壬流派(对齐独立 lrzhan/LiuRengMain 的「断卦设置」;默认值=现行行为,零回归)。
// 换将三派/分昼夜三派/涉害取舍·起讫·始入(默认法)/年神排序/昼夜阳阴归属/土旺衰。
const LR_YUEJIANG_OPTIONS = [
	{ value: 'zhongqi', label: '中气过宫（默认）' },
	{ value: 'jieqi', label: '节气换将' },
	{ value: 'richan', label: '太阳过宫·日躔（含岁差）' },
];
const LR_FENZHOUYE_OPTIONS = [
	{ value: 'chenhun', label: '晨昏分昼夜（默认）' },
	{ value: 'maoyou', label: '卯酉分昼夜' },
	{ value: 'yinshen', label: '寅申分昼夜' },
];
const LR_SEHAI_METHOD_OPTIONS = [
	{ value: 'app', label: '仅下贼上(默认)' },
	{ value: 'standard', label: '标准深浅两向' },
	{ value: 'mengzhongji', label: '直取孟仲季' },
];
const LR_SEHAI_BOUNDARY_OPTIONS = [
	{ value: 'app', label: '计起点不计本家(默认)' },
	{ value: 'both', label: '两端皆计' },
	{ value: 'neither', label: '皆不计' },
];
const LR_SHIRUKE_OPTIONS = [
	{ value: 0, label: '并入重审(默认)' },
	{ value: 1, label: '单列·九法变十法' },
];
const LR_YEAR_SHENSHA_OPTIONS = [
	{ value: 'sanyuan', label: '四利三元序(默认)' },
	{ value: 'suigui', label: '太岁排轮(太阴异)' },
];
const LR_YINYANG_SYSTEM_OPTIONS = [
	{ value: 'danmu', label: '旦暮系(默认)' },
	{ value: 'yinyang', label: '星历阳阴系' },
];
const LR_TUWANG_OPTIONS = [
	{ value: 'siji', label: '四季月土旺(默认)' },
	{ value: 'huotu', label: '火土同宫(土随火)' },
];

// 奇门封局(对齐独立 dunjia/DunJiaMain;默认未封局=零回归)。
const QIMEN_FENGJU_OPTIONS = [
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
	qijuMethod: { def: 'zhirun', oneOf: optVals(QIJU_METHOD_OPTIONS) },   // 候选随排盘体例增减(时家 / 刻家 5 档,其余 2 档),全集固定
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
	outerCoord: { def: 'ecliptic', oneOf: ['ecliptic', 'equatorial'] },
	showWeakSolid: { def: true },
});

// 🔴 改值即强制重算的「计算型」option key 全集(三式合一各子盘的盘面计算输入)。
// 这些 key 都已被 recalcSignature(performRecalcByNongli)消费(经 getQimenOptions / getKintaiyiPan / 六壬 castOverride),
// 但 refreshAll 的轻量 lastKey 不含它们 → 必须在 onOptionChange 显式 refreshAll(force) 才会真重算重画。
// after23NewDay/lateZiHourUseNextDay 已在上方单独处理(还要 prefetch),故不入本集;mode(命局/事局)只管保存去向(命盘/事盘),不改盘,亦不入。[Q-164/T-90·SS-22⑥]
const SANSHI_RECALC_OPTION_KEYS = new Set([
	// 奇门(经 getQimenOptions + fetchQimenPan/calcDunJia)
	'paiPanType', 'zhiShiType', 'yueJiaQiJuType', 'qijuMethod', 'kongMode', 'yimaMode', 'shiftPalace',
	'school', 'shuziReportNumber', 'fengJu', 'zhirunLeapDays', 'chartCategory', 'faRelatedPeople',
	'godsPreset', 'anGanMode', 'showAnZhi', 'jiGongMode',
	'feiXingShun', 'feiMenShun', 'feiShenShun', 'feiMenZhongCan', 'feiMenZhongShow',
	'mixTian', 'mixXing', 'mixMen', 'mixShen',
	'kongMarkBoth', 'showAllKong', 'shiftZhiFuMode',
	'dayJiaJu', 'keJiaFenDun', 'keZiZhengHuanShi',
	'jinhanMenPai',
	'yearJiaJu',
	// 太乙(经 getKintaiyiPan + applyTaiyiSchool)
	'taiyiStyle', 'taiyiAccum', 'taiyiSchool', 'gameTheory', 'taiyiTimeBasis',   // [Q-107 A] 太乙时间基准(与独立太乙页同源选项)
	// 大六壬(经 guirengType + buildSanshiLiuRengCastOverride)
	'guireng', 'yueJiangMethod', 'fenZhouYe', 'seHaiMethod', 'seHaiBoundary', 'shiRuKe',
	'yearShenShaSort', 'yinyangSystem', 'tuWangShuai',
]);

// 用户语义(拍板,字面直觉版): after23NewDay=1「23点算第二天」=日柱进位次日(壬寅)；=0「24点算第二天」=日柱守今(辛丑)。
const DAY_SWITCH_OPTIONS = [
	{ value: 1, label: '23点算第二天' },
	{ value: 0, label: '24点算第二天' },
];


const SANSHI_BOARD_MIN = 380;
const SANSHI_BOARD_MAX = 820;
const SANSHI_FAST_BUDGET_MS = 2200;
const SANSHI_RECALC_DEFER_MS = 28;
const SANSHI_SNAPSHOT_DEFER_MS = 120;
const AI_EXPORT_PLANET_INFO = {
	showHouse: 1,
	showRuler: 1,
};

export function clamp(val, min, max){
	return Math.max(min, Math.min(max, val));
}

function getViewportHeight(){
	// 🔴 innerHeight/documentElement.clientHeight 恒报物理域;壳缩放≠1 时当布局高用会
	// 把整页配矮(底部死带)。走 getLayoutViewportHeight —— 它**直接量** fixed 铺满元素,
	// 不做任何缩放换算,故与引擎的 zoom 语义无关(2026-08-27 根修,见 zoomDomain)。
	if(typeof window !== 'undefined' && Number.isFinite(window.innerHeight) && window.innerHeight > 0){
		return getLayoutViewportHeight();
	}
	if(typeof document !== 'undefined' && document.documentElement){
		return document.documentElement.clientHeight || 900;
	}
	return 900;
}

export function safe(v, d = ''){
	return v === undefined || v === null ? d : v;
}

function normalizeTimeAlg(value){
	return value === 1 ? 1 : 0;
}

function getTimeAlgLabel(value){
	return normalizeTimeAlg(value) === 1 ? '直接时间' : '真太阳时';
}

function parseZoneOffsetHour(zone){
	const text = `${safe(zone, '')}`.trim();
	if(!text){
		return null;
	}
	const mStd = text.match(/^([+-])(\d{1,2})(?::?(\d{2}))?$/);
	if(mStd){
		const sign = mStd[1] === '-' ? -1 : 1;
		const hh = parseInt(mStd[2], 10);
		const mm = parseInt(mStd[3] || '0', 10);
		if(!Number.isNaN(hh) && !Number.isNaN(mm)){
			return sign * (hh + mm / 60);
		}
	}
	const mUtc = text.match(/^(?:UTC|GMT)\s*([+-])(\d{1,2})(?::?(\d{2}))?$/i);
	if(mUtc){
		const sign = mUtc[1] === '-' ? -1 : 1;
		const hh = parseInt(mUtc[2], 10);
		const mm = parseInt(mUtc[3] || '0', 10);
		if(!Number.isNaN(hh) && !Number.isNaN(mm)){
			return sign * (hh + mm / 60);
		}
	}
	const mCn = text.match(/^([东西])\s*(\d{1,2})(?:[:：]?(\d{1,2}))?\s*区?$/);
	if(mCn){
		const sign = mCn[1] === '西' ? -1 : 1;
		const hh = parseInt(mCn[2], 10);
		const mm = parseInt(mCn[3] || '0', 10);
		if(!Number.isNaN(hh) && !Number.isNaN(mm)){
			return sign * (hh + mm / 60);
		}
	}
	const numeric = Number(text);
	if(Number.isFinite(numeric)){
		return numeric;
	}
	return null;
}

function formatZoneOffset(zoneHour){
	if(zoneHour === undefined || zoneHour === null || Number.isNaN(zoneHour)){
		return '+08:00';
	}
	const sign = zoneHour < 0 ? '-' : '+';
	const abs = Math.abs(zoneHour);
	let hh = Math.floor(abs);
	let mm = Math.round((abs - hh) * 60);
	if(mm >= 60){
		hh += 1;
		mm -= 60;
	}
	return `${sign}${`${hh}`.padStart(2, '0')}:${`${mm}`.padStart(2, '0')}`;
}

function normalizeZoneOffset(zone, fallback = '+08:00'){
	const parsed = parseZoneOffsetHour(zone);
	if(parsed === null || Number.isNaN(parsed)){
		const fbParsed = parseZoneOffsetHour(fallback);
		return formatZoneOffset(fbParsed === null || Number.isNaN(fbParsed) ? 8 : fbParsed);
	}
	return formatZoneOffset(parsed);
}

function normalizeAdValue(ad, fallback = 1){
	const text = `${safe(ad, '')}`.trim().toUpperCase();
	if(text === 'BC' || text === 'BCE'){
		return -1;
	}
	if(text === 'AD' || text === 'CE'){
		return 1;
	}
	const n = parseInt(text, 10);
	if(!Number.isNaN(n) && n !== 0){
		return n > 0 ? 1 : -1;
	}
	return fallback === -1 ? -1 : 1;
}

function resolveCalcGeo(fields, options){
	const lon = safe(fields && fields.lon && fields.lon.value, '');
	const lat = safe(fields && fields.lat && fields.lat.value, '');
	const gpsLon = safe(fields && fields.gpsLon && fields.gpsLon.value, '');
	const gpsLat = safe(fields && fields.gpsLat && fields.gpsLat.value, '');
	// timeAlg 仅用于“计算基准”切换，不应改写显示真太阳时所依赖的地理位置。
	return { lon, lat, gpsLon, gpsLat };
}

function buildDisplaySolarParams(params){
	if(!params){
		return null;
	}
	return {
		...params,
		timeAlg: 0,
	};
}

function timeoutResolve(ms, value = null){
	return new Promise((resolve)=>{
		setTimeout(()=>resolve(value), ms);
	});
}

const TIANJIANG_SHORT_MAP = {
	贵人: '贵',
	螣蛇: '蛇',
	腾蛇: '蛇',
	朱雀: '朱',
	六合: '合',
	勾陈: '勾',
	青龙: '龙',
	天空: '空',
	白虎: '虎',
	太常: '常',
	玄武: '玄',
	太阴: '阴',
	天后: '后',
};

export function shortTianJiang(name){
	const text = `${safe(name, '')}`.trim();
	if(!text){
		return '—';
	}
	if(TIANJIANG_SHORT_MAP[text]){
		return TIANJIANG_SHORT_MAP[text];
	}
	if(text.length === 1){
		return text;
	}
	if(text.startsWith('天') || text.startsWith('太')){
		return text.substring(text.length - 1);
	}
	return text.substring(0, 1);
}

export function splitGanZhi(gz){
	const text = `${safe(gz, '')}`.trim();
	if(!text){
		return { gan: '', zhi: '—' };
	}
	const chars = text.split('');
	const first = chars[0] || '';
	const last = chars[chars.length - 1] || '';
	const hasGan = LRConst.GanList.indexOf(first) >= 0;
	return {
		gan: hasGan ? first : '',
		zhi: last || '—',
	};
}

export function getGanzhiParts(gz){
	return {
		gan: (gz || '').substring(0, 1) || ' ',
		zhi: (gz || '').substring(1, 2) || ' ',
	};
}

function parseSolarDateTime(rawText){
	const text = `${safe(rawText, '')}`.trim();
	if(!text){
		return null;
	}
	const normalized = text.replace('T', ' ').replace('Z', '').trim();
	const m = normalized.match(/([-+]?\d{1,6})[/-](\d{1,2})[/-](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?/);
	if(!m){
		return {
			date: text,
			hm: '',
			hms: '',
			raw: text,
			isSolar: true,
		};
	}
	const yyyy = m[1];
	const mm = `${m[2]}`.padStart(2, '0');
	const dd = `${m[3]}`.padStart(2, '0');
	const hh = `${m[4]}`.padStart(2, '0');
	const ss = `${m[6] || '00'}`.padStart(2, '0');
	return {
		date: `${yyyy}-${mm}-${dd}`,
		hm: `${hh}:${m[5]}`,
		hms: `${hh}:${m[5]}:${ss}`,
		raw: text,
		isSolar: true,
	};
}

export function fmtDirect(fields){
	if(!fields || !fields.date || !fields.time){
		return { date: '', hm: '', hms: '' };
	}
	return {
		date: fields.date.value.format('YYYY-MM-DD'),
		hm: fields.time.value.format('HH:mm'),
		hms: fields.time.value.format('HH:mm:ss'),
	};
}

export function fmtSolar(fields, pan, nongli, displaySolarTime){
	const solarParsed = parseSolarDateTime(
		safe(displaySolarTime, '') || safe(pan && pan.realSunTime, '') || safe(nongli && nongli.birth, '')
	);
	if(solarParsed){
		return solarParsed;
	}
	const direct = fmtDirect(fields);
	return {
		date: direct.date,
		hm: direct.hm,
		hms: direct.hms,
		raw: '',
		isSolar: false,
	};
}

export function fmtLunar(nongli){
	if(!nongli){
		return '';
	}
	return `农历${safe(nongli.month)}${safe(nongli.day)}`;
}

function msg(key){
	return AstroText.AstroMsgCN[key] || key || '';
}

function shortMainStarLabel(name){
	const text = `${safe(name, '')}`.trim();
	if(!text){
		return '';
	}
	if(text === '太阳'){
		return '日';
	}
	if(text === '上升'){
		return '升';
	}
	if(text === '天顶' || text === '中天'){
		return '顶';
	}
	return text.substring(0, 1);
}

function getFieldKey(fields){
	if(!fields || !fields.date || !fields.time){
		return '';
	}
	return [
		fields.date.value.format('YYYY-MM-DD'),
		fields.time.value.format('HH:mm:ss'),
		safe(fields.zone && fields.zone.value),
		safe(fields.lon && fields.lon.value),
		safe(fields.lat && fields.lat.value),
		safe(fields.ad && fields.ad.value),
	].join('|');
}

function getFieldSyncKey(fields){
	if(!fields){
		return '';
	}
	return [
		getFieldKey(fields),
		safe(fields.cid && fields.cid.value),
		safe(fields.name && fields.name.value),
		safe(fields.gender && fields.gender.value),
		safe(fields.zodiacal && fields.zodiacal.value),
		safe(fields.hsys && fields.hsys.value),
		safe(fields.timeAlg && fields.timeAlg.value),
	].join('|');
}

function getNongliKey(nongli){
	if(!nongli){
		return '';
	}
	return [
		safe(nongli.yearGanZi),
		safe(nongli.monthGanZi),
		safe(nongli.dayGanZi),
		safe(nongli.time),
		safe(nongli.jieqi),
		safe(nongli.runyear),
	].join('|');
}

function getQimenOptionsKey(options){
	if(!options){
		return '';
	}
	return [
		safe(options.sex),
		safe(options.dateType),
		safe(options.leapMonthType),
		safe(options.xuShiSuiType),
		safe(options.jieQiType),
		safe(options.paiPanType),
		safe(options.zhiShiType),
		safe(options.yueJiaQiJuType),
		safe(options.yearGanZhiType),
		safe(options.monthGanZhiType),
		safe(options.dayGanZhiType),
		safe(options.after23NewDay),
		safe(options.lateZiHourUseNextDay),
		safe(options.qijuMethod),
		safe(options.kongMode),
		safe(options.yimaMode),
		safe(options.shiftPalace),
		options.fengJu ? 1 : 0,
		safe(options.school),
		safe(options.shuziReportNumber),
		safe(options.zhirunLeapDays),
		// [H-H] 🔴 同独立页:缓存键维度完备,新引擎键全入(漏=三式改档死开关)。哨兵测试守。
		safe(options.godsPreset),
		safe(options.jiGongMode),
		safe(options.anGanMode),
		options.showAnZhi ? 1 : 0,
		options.fullNameTips ? 1 : 0,
		options.feiXingShun ? 1 : 0,
		options.feiMenShun ? 1 : 0,
		options.feiShenShun ? 1 : 0,
		options.feiMenZhongCan === false ? 0 : 1,
		options.feiMenZhongShow ? 1 : 0,
		safe(options.mixTian),
		safe(options.mixXing),
		safe(options.mixMen),
		safe(options.mixShen),
		options.kongMarkBoth ? 1 : 0,
		options.showAllKong ? 1 : 0,
		safe(options.shiftZhiFuMode),
		safe(options.dayJiaJu),
		safe(options.keJiaFenDun),
		options.keZiZhengHuanShi ? 1 : 0,
		safe(options.jinhanMenPai),
		safe(options.yearJiaJu),
	].join('|');
}

export function extractIsDiurnalFromChartWrap(chartWrap){
	if(!chartWrap){
		return null;
	}
	const chart = chartWrap.chart ? chartWrap.chart : chartWrap;
	if(chart && chart.isDiurnal !== undefined && chart.isDiurnal !== null){
		return !!chart.isDiurnal;
	}
	return null;
}

export function getChartYue(chartObj){
	if(!chartObj || !chartObj.objects){
		return '';
	}
	for(let i=0; i<chartObj.objects.length; i++){
		const obj = chartObj.objects[i];
		if(obj.id === AstroConst.SUN){
			return LRConst.getSignZi(obj.sign);
		}
	}
	return '';
}

export function getOuterChartKey(chartWrap){
	if(!chartWrap){
		return '';
	}
	const chart = chartWrap.chart ? chartWrap.chart : chartWrap;
	if(!chart){
		return '';
	}
	// 🔴 **绝不纳入 chartId**:它是 model 里 `Result.chartId = randomStr(8)` 每次取盘现生成的随机值,
	// 拿它当「盘内容是否变化」的判据两头不讨好——同一时刻重复回流也判「变了」(每次都全量重算,
	// 含 /qimen/pan 与 /taiyi/pan,性能白掉),而真正该判变的维度反而没被表征。
	// 内容判据用下面几项就够且稳:ASC/SUN 的 sign|signlon|lon(逐分钟即变,四分钟步进必变)
	// + 日干支 + 时辰 + 天体数。配合 componentDidUpdate 里去掉 awaitingChartSync 闸门,才形成
	// 「chartObj 一变就校正、没实质变就 no-op」的闭环(horosa_sanshi_outer_follow_time_v1)。
	const objs = chart.objects || [];
	let ascKey = '';
	let sunKey = '';
	for(let i=0; i<objs.length; i++){
		const obj = objs[i];
		if(!obj){
			continue;
		}
		if(!ascKey && obj.id === AstroConst.ASC){
			ascKey = `${safe(obj.sign)}|${safe(obj.signlon)}|${safe(obj.lon)}`;
		}
		if(!sunKey && obj.id === AstroConst.SUN){
			sunKey = `${safe(obj.sign)}|${safe(obj.signlon)}|${safe(obj.lon)}`;
		}
		if(ascKey && sunKey){
			break;
		}
	}
	return [
		ascKey,
		sunKey,
		safe(chart.nongli && chart.nongli.dayGanZi),
		safe(chart.nongli && chart.nongli.time),
		`${objs.length}`,
	].join('|');
}

function computeSanshiFenZhouYe(fenZhouYe, chartObj){
	if(fenZhouYe !== 'maoyou' && fenZhouYe !== 'yinshen'){
		return undefined;
	}
	if(!chartObj || !chartObj.nongli || !chartObj.nongli.time){
		return undefined;
	}
	const timezi = chartObj.nongli.time.substr(1);
	const dayBranches = fenZhouYe === 'maoyou'
		? ['卯', '辰', '巳', '午', '未', '申']
		: ['寅', '卯', '辰', '巳', '午', '未'];
	return dayBranches.indexOf(timezi) >= 0;
}

// 汇总 大六壬流派(换将/分昼夜/涉害取舍/昼夜阳阴归属)→ castOverride;全默认返回 null(零回归)。
// 与独立 lrzhan/buildLiuRengCastOverride 同款语义(三式合一只支持「正时正将」起课法,不含 25 起课变体)。
// [挂载自检 三式 P0] 三式合一 → 六壬断卦层的 castOpts 形态(与 buildLiuRengSnapshotText 第 8 参同键;三式锁正时正将)。
export function pickSanshiLiurengCastOpts(opts, nongli){
	const o = opts && typeof opts === 'object' ? opts : {};
	const solarYear = Number(o.solarYear) || (nongli && Number(nongli.solarYear)) || undefined;
	return {
		castMethod: 'zheng',
		yueJiangMethod: o.yueJiangMethod,
		fenZhouYe: o.fenZhouYe,
		seHaiMethod: o.seHaiMethod,
		seHaiBoundary: o.seHaiBoundary,
		shiRuKe: o.shiRuKe,
		yinyangSystem: o.yinyangSystem,
		yearShenShaSort: o.yearShenShaSort,
		tuWangShuai: o.tuWangShuai,
		zhanCategory: o.zhanCategory,
		...(solarYear ? { solarYear } : {}),
	};
}

export function buildSanshiLiuRengCastOverride(chartObj, opts){
	opts = opts || {};
	if(!chartObj || !chartObj.nongli){
		return null;
	}
	const yueJiangMethod = opts.yueJiangMethod || 'zhongqi';
	const fenZhouYe = opts.fenZhouYe || 'chenhun';
	const isDiurnal = computeSanshiFenZhouYe(fenZhouYe, chartObj);
	const seHaiOpts = {
		method: opts.seHaiMethod || 'app',
		boundary: opts.seHaiBoundary || 'app',
		shiRuKe: !!opts.shiRuKe,
	};
	const seHaiDefault = seHaiOpts.method === 'app' && seHaiOpts.boundary === 'app' && !seHaiOpts.shiRuKe;
	const yinyangSystem = opts.yinyangSystem === 'yinyang' ? 'yinyang' : 'danmu';
	const yearShenShaSort = opts.yearShenShaSort || 'sanyuan'; // 年神排序(默认四利三元序);三式合一原 override 漏传→六壬子盘 AI 快照年神恒默认
	const tuWangShuai = opts.tuWangShuai || 'siji'; // 三传旺衰(默认四季月土旺)
	const allDefault = yueJiangMethod !== 'jieqi' && yueJiangMethod !== 'richan'
		&& isDiurnal === undefined && seHaiDefault && yinyangSystem === 'danmu'
		&& yearShenShaSort === 'sanyuan' && tuWangShuai === 'siji';
	if(allDefault){
		return null;
	}
	const solarYear = Number(opts.solarYear) || (chartObj.nongli && Number(chartObj.nongli.solarYear)) || undefined;
	const yueEff = getYueJiangByMethod(chartObj, yueJiangMethod, solarYear);
	return { yue: yueEff, isDiurnal, seHaiOpts, yinyangSystem, yearShenShaSort, tuWangShuai };
}

export function buildLiuRengLayout(chartObj, guirengType, castOverride){
	if(!chartObj || !chartObj.nongli || !chartObj.nongli.time){
		return null;
	}
	const yue = (castOverride && castOverride.yue) || getChartYue(chartObj);
	if(!yue){
		return null;
	}
	const downZi = LRConst.ZiList.slice(0);
	const upZi = LRConst.ZiList.slice(0);
	const yueIndexs = [];
	const timezi = chartObj.nongli.time.substr(1);
	const yueIdx = LRConst.ZiList.indexOf(yue);
	const tmIdx = LRConst.ZiList.indexOf(timezi);
	if(yueIdx < 0 || tmIdx < 0){
		return null;
	}
	const delta = yueIdx - tmIdx;
	for(let i=0; i<12; i++){
		const idx = (i + delta + 12) % 12;
		yueIndexs[i] = idx;
		upZi[i] = LRConst.ZiList[idx];
	}

	const houseTianJiang = LRConst.TianJiang.slice(0);
	const guizi = LRConst.getGuiZi(
		chartObj,
		guirengType === undefined ? 2 : guirengType,
		castOverride ? castOverride.isDiurnal : undefined,
		castOverride ? castOverride.yinyangSystem : undefined
	);
	let houseidx = 0;
	for(let i=0; i<12; i++){
		const zi = LRConst.ZiList[yueIndexs[i]];
		if(zi === guizi){
			houseidx = i;
			break;
		}
	}
	const housezi = LRConst.ZiList[houseidx];
	if(LRConst.SummerZiList.indexOf(housezi) >= 0){
		for(let i=0; i<12; i++){
			const idx = (houseidx - i + 12) % 12;
			houseTianJiang[i] = LRConst.TianJiang[idx];
		}
	}else{
		for(let i=0; i<12; i++){
			const idx = (i - houseidx + 12) % 12;
			houseTianJiang[i] = LRConst.TianJiang[idx];
		}
	}
	return { yue, timezi, guizi, downZi, upZi, houseTianJiang };
}

export function buildLrNongli(nongli, dunjia){
	const dayGanZi = dunjia && dunjia.ganzhi ? (dunjia.ganzhi.day || '') : '';
	const timeGanZi = dunjia && dunjia.ganzhi ? (dunjia.ganzhi.time || '') : '';
	return {
		...(nongli || {}),
		dayGanZi: dayGanZi || (nongli && nongli.dayGanZi ? nongli.dayGanZi : ''),
		time: timeGanZi || (nongli && nongli.time ? nongli.time : ''),
	};
}

export function buildKeData(layout, chartObj){
	const result = { raw: [], lines: [] };
	if(!layout || !chartObj || !chartObj.nongli || !chartObj.nongli.dayGanZi){
		return result;
	}
	const dayGanZi = chartObj.nongli.dayGanZi;
	const daygan = dayGanZi.substr(0, 1);
	const dayzi = dayGanZi.substr(1, 1);

	const idx1 = layout.downZi.indexOf(LRConst.GanJiZi[daygan]);
	if(idx1 < 0){
		return result;
	}
	const ke1zi = layout.upZi[idx1];
	const ke1 = [layout.houseTianJiang[idx1], ke1zi, daygan];

	const idx2 = layout.downZi.indexOf(ke1zi);
	const ke2zi = idx2 >= 0 ? layout.upZi[idx2] : '';
	const ke2 = [idx2 >= 0 ? layout.houseTianJiang[idx2] : '', ke2zi, ke1zi];

	const idx3 = layout.downZi.indexOf(dayzi);
	const ke3zi = idx3 >= 0 ? layout.upZi[idx3] : '';
	const ke3 = [idx3 >= 0 ? layout.houseTianJiang[idx3] : '', ke3zi, dayzi];

	const idx4 = layout.downZi.indexOf(ke3zi);
	const ke4zi = idx4 >= 0 ? layout.upZi[idx4] : '';
	const ke4 = [idx4 >= 0 ? layout.houseTianJiang[idx4] : '', ke4zi, ke3zi];

	result.raw = [ke1, ke2, ke3, ke4];
	// [Q-153] 标签与 raw 同序(ke1=一课 日干上神 … ke4=四课);此前 四→一 反标(无消费方,顺手对齐防再被引用)。
	result.lines = [
		`一课 ${ke1[2]}${ke1[1]}${ke1[0]}`,
		`二课 ${ke2[2]}${ke2[1]}${ke2[0]}`,
		`三课 ${ke3[2]}${ke3[1]}${ke3[0]}`,
		`四课 ${ke4[2]}${ke4[1]}${ke4[0]}`,
	];
	return result;
}

export function buildSanChuan(layout, keRaw, chartObj, castOverride){
	if(!layout || !keRaw || keRaw.length !== 4 || !chartObj || !chartObj.nongli){
		return null;
	}
	try{
		const helper = new ChuangChart({
			owner: null,
			chartObj: chartObj,
			nongli: chartObj.nongli,
			ke: keRaw,
			// 涉害取舍流派(默认 null=仅下贼上,已固定,零回归);非默认时携 seHaiOpts 影响涉害课取用。
			seHaiOpts: castOverride ? castOverride.seHaiOpts : null,
			liuRengChart: {
				upZi: layout.upZi,
				downZi: layout.downZi,
				houseTianJiang: layout.houseTianJiang,
			},
			x: 0,
			y: 0,
			width: 0,
			height: 0,
		});
		helper.genCuangs();
		return helper.cuangs || null;
	}catch(e){
		return null;
	}
}

function normalizeLon(v){
	let lon = parseFloat(v);
	if(Number.isNaN(lon)){
		return null;
	}
	lon = ((lon % 360) + 360) % 360;
	return lon;
}

function lonToBranch(lon){
	const nlon = normalizeLon(lon);
	if(nlon === null){
		return '';
	}
	// 星座-地支固定映射：
	// 水瓶-子、摩羯-丑、射手-寅、天蝎-卯、天秤-辰、处女-巳、
	// 狮子-午、巨蟹-未、双子-申、金牛-酉、白羊-戌、双鱼-亥
	const signIdx = Math.floor(nlon / 30) % 12; // 白羊=0 ... 双鱼=11
	const branchIdx = (10 - signIdx + 12) % 12;
	return BRANCH_ORDER[branchIdx];
}

// 赤经(RA)→地支:与 lonToBranch 同口径(RA 0°=白羊点,对齐黄经 0°),供「外圈赤道分宫」复用 obj.ra。
function raToBranch(ra){
	const nra = normalizeLon(ra);
	if(nra === null){
		return '';
	}
	const signIdx = Math.floor(nra / 30) % 12;
	const branchIdx = (10 - signIdx + 12) % 12;
	return BRANCH_ORDER[branchIdx];
}

function signToBranch(sign){
	if(!sign){
		return '';
	}
	try{
		return LRConst.getSignZi(sign) || '';
	}catch(e){
		return '';
	}
}

function resolveObjBranch(obj, coord){
	if(!obj){
		return '';
	}
	// 赤道模式:按赤经(obj.ra)分入地支;缺赤经则回退黄道避免空。默认(ecliptic/未传)逐字现状。
	if(coord === 'equatorial'){
		const ra = obj.ra;
		if(ra !== undefined && ra !== null && !Number.isNaN(parseFloat(ra))){
			return raToBranch(ra);
		}
	}
	const bySign = signToBranch(obj.sign);
	if(bySign){
		return bySign;
	}
	return lonToBranch(obj.lon);
}

function parseHouseNum(houseId){
	if(!houseId){
		return '';
	}
	const m = `${houseId}`.match(/\d+/);
	return m ? m[0] : '';
}

// 单柱「虚支」:与后端七政四余 Moira(MoiraPropRuleEngine.computeWeakHouse)逐字一致——
// 旬空二支按 60 甲子位次奇偶仅取其一(偶位取前支/奇位取后支),非整对旬空。
// i = 干序 g + 10*旬序;index = 10 - 2*旬序,i 奇(即 g 奇)则 +1,取 BRANCH_ORDER[index]。
function computeMoiraWeakZhi(ganzhi){
	if(!ganzhi || ganzhi.length < 2){ return ''; }
	const g = STEM_ORDER.indexOf(ganzhi.charAt(0));
	const z = BRANCH_ORDER.indexOf(ganzhi.charAt(1));
	if(g < 0 || z < 0){ return ''; }
	const xun = ((((g - z) % 12) + 12) % 12) / 2; // 旬序 0..5(= 60甲子位次 i 的 i/10)
	let index = 10 - 2 * xun;
	if(g % 2 === 1){ index++; } // i 奇 ⇔ g 奇(i = g + 10*旬序)
	return BRANCH_ORDER[(((index % 12) + 12) % 12)] || '';
}

// 三式外圈「虚实」红绿点 八字源,与七政四余 Moira 红绿点逐宫一致:
//  实宫=年月日时【四柱地支】各自定实;虚宫=四柱各自 computeMoiraWeakZhi(每柱仅一支)推虚。
// pan.ganzhi = 起课四柱(年/月/日/时干支)。返回 { 地支: {solid,weak,solidPillars,weakPillars} }。
export function buildSanshiWeakSolid(pan){
	const map = {};
	BRANCH_ORDER.forEach((b)=>{ map[b] = { solid: false, weak: false, solidPillars: [], weakPillars: [] }; });
	const gz = (pan && pan.ganzhi) || {};
	const pillars = [
		{ label: '年', gz: gz.year || '' },
		{ label: '月', gz: gz.month || '' },
		{ label: '日', gz: gz.day || '' },
		{ label: '时', gz: gz.time || '' },
	];
	// 实宫:四柱地支各自定实。
	pillars.forEach((p)=>{
		const zhi = (p.gz || '').charAt(1);
		if(zhi && map[zhi]){
			map[zhi].solid = true;
			if(map[zhi].solidPillars.indexOf(p.label) < 0){
				map[zhi].solidPillars.push(p.label);
			}
		}
	});
	// 虚宫:四柱各自取 Moira 虚支(每柱一支)推虚。
	pillars.forEach((p)=>{
		const wz = computeMoiraWeakZhi(p.gz);
		if(wz && map[wz]){
			map[wz].weak = true;
			if(map[wz].weakPillars.indexOf(p.label) < 0){
				map[wz].weakPillars.push(p.label);
			}
		}
	});
	return map;
}

// 三式「旬」统一口径(时家奇门;概览/盘底/快照单一来源,杜绝与后端 xunShou/fuTou(=六仪)及繁简键漂移):
//  旬首=时柱所在旬之甲(该时辰旬首,如癸巳→甲申);旬仪=旬首所遁六仪(甲申→庚,显示甲申庚);
//  本旬=日柱所在旬之甲(本日之旬);旬空=日柱旬空(日空);时空=时柱旬空。
// 旬首(甲X)展开为「甲X丁Y癸Z」:旬首(第一日甲)+旬丁(第四日丁=丁马)+旬尾(第十日癸);
// 丁在旬首后第 3 位、癸在第 9 位(地支同步推移)。例:甲子→甲子丁卯癸酉;甲辰→甲辰丁未癸丑。
function expandXunPillars(head){
	if(!head || head.length < 2){ return head || ''; }
	const z = BRANCH_ORDER.indexOf(head.charAt(1));
	if(z < 0){ return head; }
	const ding = `丁${BRANCH_ORDER[(z + 3) % 12]}`; // 第四日(丁) + 地支
	const gui = `癸${BRANCH_ORDER[(z + 9) % 12]}`; // 第十日(癸) + 地支
	return `${head}${ding}${gui}`;
}

export function computeSanshiXun(pan){
	const gz = (pan && pan.ganzhi) || {};
	const dayHead = gz.day ? getXunHead(gz.day) : '';
	const timeHead = gz.time ? getXunHead(gz.time) : '';
	const xunShou = timeHead || safe(pan && pan.xunShou, '—');
	const xunYi = timeHead ? `${timeHead}${XUN_SHOU_TO_LIUYI[timeHead] || ''}` : safe(pan && pan.fuTou, '—');
	// 本旬=日柱所在旬,展开旬首/旬丁/旬尾(甲X丁Y癸Z),与参考样张一致。
	const benXun = dayHead ? expandXunPillars(dayHead) : safe(pan && pan.xunShou, '—');
	const riKong = (dayHead && GUXU[dayHead]) || safe(pan && pan.xunkong && pan.xunkong.日空, '—');
	const shiKong = (timeHead && GUXU[timeHead]) || safe(pan && pan.xunkong && (pan.xunkong.时空 || pan.xunkong.時空), '—');
	return { xunShou, xunYi, benXun, riKong, shiKong };
}

export function buildOuterData(chartObj, coord){
	const housesByBranch = {};
	const starsByBranch = {};
	const starsByBranchFull = {};
	const starsByBranchMeta = {};
	BRANCH_ORDER.forEach((b)=>{
		housesByBranch[b] = [];
		starsByBranch[b] = [];
		starsByBranchFull[b] = [];
		starsByBranchMeta[b] = [];
	});
	if(!chartObj){
		return { housesByBranch, starsByBranch, starsByBranchFull, starsByBranchMeta };
	}
	const objs = chartObj.objects || [];
	let ascBranch = '';
	for(let i=0; i<objs.length; i++){
		const obj = objs[i];
		if(obj && obj.id === AstroConst.ASC){
			ascBranch = resolveObjBranch(obj, coord);
			break;
		}
	}
	const ascIdx = BRANCH_ORDER.indexOf(ascBranch);
	if(ascIdx >= 0){
		// 人事宫位：从上升1宫开始，逆时针排布
		for(let houseNo = 1; houseNo <= 12; houseNo++){
			const idx = (ascIdx - (houseNo - 1) + 12) % 12;
			housesByBranch[BRANCH_ORDER[idx]].push(`${houseNo}`);
		}
	}else{
		// 兜底：若ASC缺失则回退到按宫头经度映射
		const houses = chartObj.houses || [];
		houses.forEach((h)=>{
			const b = (coord === 'equatorial' && h && h.ra !== undefined && h.ra !== null && !Number.isNaN(parseFloat(h.ra)))
				? raToBranch(h.ra)
				: (signToBranch(h.sign) || lonToBranch(h.lon));
			if(!b){
				return;
			}
			const txt = parseHouseNum(h.id);
			if(txt && housesByBranch[b].indexOf(txt) < 0){
				housesByBranch[b].push(txt);
			}
		});
	}

	const starsByBranchRaw = {};
	BRANCH_ORDER.forEach((b)=>{ starsByBranchRaw[b] = []; });
	objs.forEach((obj)=>{
		if(!MAIN_STAR_IDS.has(obj.id)){
			return;
		}
		const b = resolveObjBranch(obj, coord);
		if(!b){
			return;
		}
		// 度数随坐标口径切换:赤道按赤经(ra)宫内度;黄道按 signlon(黄经宫内度)。
		// 否则切赤道仅地支重映射、度数/悬浮纹丝不动。
		const useEqua = coord === 'equatorial' && obj.ra !== undefined && obj.ra !== null && !Number.isNaN(parseFloat(obj.ra));
		const inSegDeg = useEqua ? (normalizeLon(obj.ra) % 30) : (obj.signlon || 0);
		const deg = splitDegree(inSegDeg);
		const retro = obj.lonspeed < 0 ? 'R' : '';
		const shortTxt = `${shortMainStarLabel(msg(obj.id))}${safe(deg[0], 0)}${retro}`;
		const starName = safe(appendPlanetHouseInfo(msg(obj.id), obj, AI_EXPORT_PLANET_INFO), '未知星曜');
		const minTxt = `${safe(deg[1], 0)}`.padStart(2, '0');
		const fullTxt = `${starName}${safe(deg[0], 0)}°${minTxt}${retro}${useEqua ? '（赤经）' : ''}`;
		starsByBranchRaw[b].push({
			shortTxt,
			fullTxt,
			deg: Number(inSegDeg) || 0,
			objId: obj.id,
		});
	});
	BRANCH_ORDER.forEach((b)=>{
		const sorted = starsByBranchRaw[b].sort((a, c)=>a.deg - c.deg);
		starsByBranch[b] = sorted.map((item)=>item.shortTxt);
		starsByBranchFull[b] = sorted.map((item)=>item.fullTxt);
		starsByBranchMeta[b] = sorted.map((item)=>({
			shortTxt: item.shortTxt,
			fullTxt: item.fullTxt,
			objId: item.objId,
		}));
	});
	return { housesByBranch, starsByBranch, starsByBranchFull, starsByBranchMeta };
}

export function buildShenShaMap(dunjia){
	const map = {};
	if(!dunjia || !dunjia.shenSha || !dunjia.shenSha.allItems){
		return map;
	}
	dunjia.shenSha.allItems.forEach((item)=>{
		map[item.name] = item.value;
	});
	// 兼容不同命名写法，避免取值缺失。
	if(!map.幕贵 && map.墓贵){
		map.幕贵 = map.墓贵;
	}
	if(!map.墓贵 && map.幕贵){
		map.墓贵 = map.幕贵;
	}
	return map;
}

function appendSection(lines, title, bodyLines){
	lines.push(`【${title}】`);
	(bodyLines || []).forEach((line)=>{
		lines.push(`${line}`);
	});
	lines.push('');
}

function buildLiuRengBranchMap(lrLayout){
	const map = {};
	if(!lrLayout || !Array.isArray(lrLayout.downZi)){
		return map;
	}
	lrLayout.downZi.forEach((branch, idx)=>{
		map[branch] = {
			up: safe(lrLayout.upZi && lrLayout.upZi[idx], '—'),
			god: safe(lrLayout.houseTianJiang && lrLayout.houseTianJiang[idx], '—'),
		};
	});
	return map;
}

// 单一真值源:把独立技法 builder 产出的整篇快照(段头形如 [X])解析成「段名 → 正文行数组」的 Map,
// 供三式合一按需挑段并以 appendSection(【X】)重发。这样段内容 100% 来自独立 builder(零平行实现),
// 三式合一只做「选段 + 改前缀」。段头识别与 parseSectionTitleLine 同口径:整行 [X] 才算段头。
// 把独立 builder 整篇里的指定段,以「前缀 + 段名」重发到三式合一快照(单一真值源:正文照搬)。
// 仅在该段存在且有正文时输出(条件段天然豁免;空段不污染导出与导出设置勾选面)。
function appendPickedSections(lines, sectionMap, titles, prefix){
	(titles || []).forEach((title)=>{
		const body = sectionMap[title];
		if(!body || !body.length){
			return;
		}
		appendSection(lines, `${prefix || ''}${title}`, body);
	});
}



export function buildSanShiUnitedSnapshotText(data){
	const {
		fields,
		options,
		nongli,
		displaySolarTime,
		liureng,
		dunjia,
		taiyi,
		keData,
		sanChuan,
		lrLayout,
		liurengRefBundle,
		outerData,
		// 六壬断卦层(复用独立 buildLiuRengSnapshotText)所需的原始入参;缺任一则跳过断卦层(零回归)。
		guirengType,
		liurengChartForLr,
		lrCastOverride,
		lrCastOpts,
		liurengRunYear,
		// [YA v42] 紫微四化 tab 上报的 {chart,daxianIdx,liunianIdx};缺省(旧调用/tab 未开)不产段。
		ziweiSihua,
	} = data || {};
	if(!dunjia || !keData || !sanChuan || !lrLayout){
		return '';
	}
	const lines = [];
	const timeAlg = normalizeTimeAlg(options && options.timeAlg);
	const timeAlgLabel = getTimeAlgLabel(timeAlg);
	const direct = fmtDirect(fields);
	const solar = fmtSolar(fields, dunjia, nongli, displaySolarTime);
	const directText = `${safe(direct.date, '—')} ${safe(direct.hm, '—')}`.trim();
	const solarText = `${safe(solar.date, '—')} ${safe(solar.hm, '—')}`.trim();
	const lunarText = safe(dunjia.lunarText, fmtLunar(nongli) || '—');
	const pillars = dunjia.ganzhi || {};
	const yuejiang = safe((liureng && liureng.yue) || (lrLayout && lrLayout.yue), '—');
	const nianming = safe(
		liureng && liureng.nianMing,
		(pillars.year && pillars.year.length > 1) ? pillars.year.substring(1, 2) : '—'
	);
	const daySwitchLabel = options && options.after23NewDay === 1 ? '23点算第二天' : '24点算第二天';
	appendSection(lines, '起盘信息', [
		`农历：${lunarText || '—'}`,
		`直接时间：${directText || '—'}`,
		`真太阳时：${solarText || '—'}`,
		`四柱：${safe(pillars.year, '—')}年/${safe(pillars.month, '—')}月/${safe(pillars.day, '—')}日/${safe(pillars.time, '—')}时`,
		`时间算法：${timeAlgLabel}`,
		`换日：${daySwitchLabel}`,
		`月将：${yuejiang}`,
		`年命：${nianming}`,
	]);
	// 旬:与盘面 renderBottom / 概览同源(computeSanshiXun):旬首=时柱旬首 / 旬仪=时柱旬首+六仪 /
	// 本旬=日柱旬首 / 旬空=日空 / 时空=时柱旬空,避免旧 xunShou/fuTou(=六仪)/繁简键失配错值。
	const _xun = computeSanshiXun(dunjia);
	appendSection(lines, '概览', [
		`局数：${safe(dunjia.juText, '—')}`,
		`旬首：${_xun.xunShou}`,
		`旬仪：${_xun.xunYi}`,
		`值符：${safe(dunjia.zhiFu, '—')}`,
		`值使：${safe(dunjia.zhiShi, '—')}`,
		`本旬：${_xun.benXun}`,
		`旬空：${_xun.riKong}`,
		`时空：${_xun.shiKong}`,
		// [Q-319/T-316] yiMa.text 本身已带「日马:」/「时马:」前缀(驿马取法可选日马/时马),此处再加一层
		// → 快照与导出出现「日马:日马:申(坤二宫)」,选时马时更成「日马:时马:…」自相矛盾。直接用其自带前缀。
		`${dunjia.yiMa && dunjia.yiMa.text ? dunjia.yiMa.text : '日马：无'}`,
		`阴阳遁：${safe(dunjia.yinYangDun, '—')}`,
		`月将：${yuejiang}`,
		// [Q-160/T-78] 封局 / 四柱空亡随开关入快照(缺省关=不产行,字节不变)
		...(dunjia.fengJu ? ['奇门封局：已封局'] : []),
		...(dunjia.allKong ? [`四柱空亡：年空${safe(dunjia.allKong.年空, '—')}、月空${safe(dunjia.allKong.月空, '—')}、日空${safe(dunjia.allKong.日空, '—')}、时空${safe(dunjia.allKong.时空, '—')}`] : []),
	]);
	if(taiyi){
		appendSection(lines, '太乙', buildTaiyiSnapshotLines(taiyi));
		// 太乙动态派生段(主客定算/八门与宿曜/断法/七大兵法/博弈/命法/命宫行限):复用独立 buildTaiyiSnapshotText,
		// 切其按 pan.sections 产出的段(单一真值源,同 formatSnapshotValue 口径),以「太乙」前缀重发(三式合一缺这些 → 导出/挂载贫)。
		const taiyiSectionTitles = Array.isArray(taiyi.sections)
			? SANSHI_TAIYI_SECTION_TITLES.filter((title)=>taiyi.sections.some((section)=>section && section.title === title))
			: [];
		if(taiyiSectionTitles.length){
			const taiyiSectionMap = parseSnapshotSections(buildTaiyiSnapshotText(taiyi));
			appendPickedSections(lines, taiyiSectionMap, taiyiSectionTitles, '太乙');
		}
		appendSection(lines, '太乙十六宫', (taiyi.palace16 || []).map((item)=>{
			const txt = item.items && item.items.length ? item.items.join('、') : '—';
			return `${item.palace}：${txt}`;
		}));
	}
	const keRaw = keData && Array.isArray(keData.raw) ? keData.raw : [];
	const formatKe = (idx)=>{ 
		const item = keRaw[idx] || [];
		return `${safe(item[2], '—')}${safe(item[1], '—')}${safe(item[0], '—')}`;
	};
	const formatChuan = (idx)=>{
		const gz = safe(sanChuan && sanChuan.cuang && sanChuan.cuang[idx], '—');
		const god = safe(sanChuan && sanChuan.tianJiang && sanChuan.tianJiang[idx], '');
		return god ? `${gz}（${god}）` : gz;
	};
	// [Q-153/T-70] raw[0]=一课(日干上神)…raw[3]=四课,与盘面 SanshiUnitedBoard、独立六壬页、帮助文同序(此前 3→0 颠倒)。
	// [Q-450/T-413] 三传递生递克 + 逐传空/禄/马徽记(与独立六壬页、右栏小图同一纯函数;三式同步铁律)。
	const _ssCtx = (liurengRefBundle && liurengRefBundle.context) || null;
	const _ssRelLines = (_ssCtx && Array.isArray(_ssCtx.sanChuanBranches) && _ssCtx.sanChuanBranches.length >= 3)
		? sanChuanRelationSnapshotLines({
			branches: _ssCtx.sanChuanBranches,
			gans: _ssCtx.sanChuanGans || [],
			dayGan: _ssCtx.dayGan || '',
			dayZhi: _ssCtx.dayZhi || '',
			xunKong: _ssCtx.xunKongBranches || [],
		})
		: [];
	appendSection(lines, '大六壬', [
		`一课：${formatKe(0)}`,
		`二课：${formatKe(1)}`,
		`三课：${formatKe(2)}`,
		`四课：${formatKe(3)}`,
		'',
		`初传：${formatChuan(0)}`,
		`中传：${formatChuan(1)}`,
		`末传：${formatChuan(2)}`,
		..._ssRelLines,
	]);
	const refBundle = liurengRefBundle || {};
	const xiaojuAllItems = Array.isArray(refBundle.xiaoju) ? refBundle.xiaoju : [];
	const xiaojuMainItems = xiaojuAllItems.filter((item)=>!XIAO_JU_REFERENCE_TAB_KEYS.has(item.key));
	const xiaojuReferenceItems = xiaojuAllItems.filter((item)=>XIAO_JU_REFERENCE_TAB_KEYS.has(item.key));
	const appendRefSection = (title, items, type)=>{
		if(!items || !items.length){
			appendSection(lines, title, ['无']);
			return;
		}
		const body = [];
		items.forEach((item, idx)=>{
			body.push(`${idx + 1}. ${safe(item.name, '未命名')}`);
			const docText = type === 'overview'
				? buildOverviewReferenceText(item)
				: buildReferenceDocumentText(item, type);
			if(docText){
				docText.split('\n').forEach((line)=>body.push(line));
			}
			if(item.evidence && item.evidence.length){
				body.push(`依据：${item.evidence.join('；')}`);
			}
			body.push('');
		});
		if(body.length && body[body.length - 1] === ''){
			body.pop();
		}
		appendSection(lines, title, body);
	};
	appendRefSection('六壬大格', refBundle.dage || [], 'dage');
	appendRefSection('六壬小局', xiaojuMainItems, 'xiaoju');
	appendRefSection('六壬参考', xiaojuReferenceItems, 'xiaoju');
	appendRefSection('六壬概览', refBundle.overview || [], 'overview');
	// 六壬断卦层(十二盘式/常用神煞/年月神煞/课体结构/三传旺衰/空亡真假/旬空落点/陷空/遁干特殊/年命上神/毕法/占断向导):
	// 复用独立 buildLiuRengSnapshotText(单一真值源),用三式合一同源入参重跑后切断卦段——独立页有、三式合一此前缺。
	// 入参齐备才跑(零回归);params=null 跳过起盘信息行,zhangshengElem='' 不影响断卦层(其只依赖 refs.context)。
	if(liureng && liurengChartForLr){
		let liurengFull = '';
		try{
			liurengFull = buildLiuRengSnapshotText(
				null,
				liureng,
				liurengRunYear || null,
				liurengChartForLr,
				guirengType,
				'',
				options && options.sex,
				{ ...(lrCastOpts || {}), castOverride: lrCastOverride || undefined }
			);
		}catch(e){
			liurengFull = '';
		}
		if(liurengFull){
			const liurengSectionMap = parseSnapshotSections(liurengFull);
			// [Q-451/T-414] 段单补「七政」:独立六壬快照有 [七政] 段、三式合一也有「七政」页签,此前挑段单漏它 → 该段被丢
			appendPickedSections(lines, liurengSectionMap, SANSHI_LIURENG_DUANGUA_SECTIONS, '');
		}
	}
	const qimenMap = {};
	if(Array.isArray(dunjia.cells)){
		dunjia.cells.forEach((cell)=>{
			qimenMap[cell.palaceNum] = cell;
		});
	}
	const lrBranchMap = buildLiuRengBranchMap(lrLayout);
	// [Q-451/T-414] 与盘面同源:外圈虚实点按 buildSanshiWeakSolid(四柱地支定实 / 四柱旬空推虚)
	const weakSolidMap = (()=>{ try{ return buildSanshiWeakSolid(dunjia); }catch(e){ return null; } })();
	const starsByBranch = outerData && outerData.starsByBranchFull ? outerData.starsByBranchFull
		: (outerData && outerData.starsByBranch ? outerData.starsByBranch : {});
	SANSHI_PALACE_EXPORT_ORDER.forEach((palace)=>{
		const qimenCell = qimenMap[palace.palaceNum] || {};
		const body = [
			`遁甲：天盘干：${safe(qimenCell.tianGan, '—')}；八神：${safe(qimenCell.god, '—')}；九星：${safe(qimenCell.tianXing, '—')}；地盘干：${safe(qimenCell.diGan, '—')}`,
			'',
		];
		palace.branches.forEach((branch, idx)=>{
			const lr = lrBranchMap[branch] || {};
			const stars = Array.isArray(starsByBranch[branch]) ? starsByBranch[branch] : [];
			body.push(`「${branch}-${safe(BRANCH_ZODIAC_MAP[branch], '未知星座')}」`);
			// [Q-451/T-414] 盘面外圈画了「人事宫位号」与「虚实红绿点」(四柱地支定实 / 旬空推虚),快照此前两样都没有 →
			//   AI 看不到盘上最显眼的两层标注。此处逐支补齐(无数据不产行,缺省字节零变化)。
			const houseNos = outerData && outerData.housesByBranch && Array.isArray(outerData.housesByBranch[branch]) ? outerData.housesByBranch[branch] : [];
			if(houseNos.length){ body.push(`人事宫位：第 ${houseNos.join('、')} 宫`); }
			const ws = weakSolidMap ? weakSolidMap[branch] : null;
			if(ws && (ws.solid || ws.weak)){
				const parts = [];
				if(ws.solid){ parts.push(`实（${(ws.solidPillars || []).join('') || '四柱'}柱地支）`); }
				if(ws.weak){ parts.push(`虚（${(ws.weakPillars || []).join('') || '旬空'}旬空）`); }
				body.push(`虚实：${parts.join('；')}`);
			}
			body.push(`六壬：天盘：${safe(lr.up, '—')}；神将：${safe(lr.god, '—')}`);
			body.push(`星盘：${stars.length ? stars.join('；') : '无'}`);
			if(idx < palace.branches.length - 1){
				body.push('');
			}
		});
		appendSection(lines, palace.title, body);
	});
	const shenshaItems = dunjia.shenSha && Array.isArray(dunjia.shenSha.allItems) ? dunjia.shenSha.allItems : [];
	appendSection(lines, '神煞', shenshaItems.length
		? shenshaItems.map((item)=>`${item.name}：${item.value}`)
		: ['暂无神煞']);
	const bagongLines = [];
	BAGONG_PALACE_ORDER.forEach((palaceNum)=>{
		const item = buildQimenBaGongPanelData(dunjia, palaceNum);
		const palaceName = item.palaceName || BAGONG_PALACE_NAME[palaceNum] || '';
		bagongLines.push(`${palaceName}宫：`);
		if(item.jiPatternDetails && item.jiPatternDetails.length){
			bagongLines.push('奇门吉格：');
			item.jiPatternDetails.forEach((txt)=>bagongLines.push(`- ${txt}`));
		}else{
			bagongLines.push('奇门吉格：无');
		}
		if(item.xiongPatternDetails && item.xiongPatternDetails.length){
			bagongLines.push('奇门凶格：');
			item.xiongPatternDetails.forEach((txt)=>bagongLines.push(`- ${txt}`));
		}else{
			bagongLines.push('奇门凶格：无');
		}
		bagongLines.push(`十干克应（天${item.tianGan || '—'}加地${item.diGan || '—'}）：${item.tenGanText}`);
		bagongLines.push(`八门克应（人${item.renDoor || '—'}加地${item.baseDoor || '—'}）：${item.doorBaseText}`);
		bagongLines.push(`奇仪主应（人${item.renDoor || '—'}加天${item.tianGan || '—'}）：${item.doorTianText}`);
		bagongLines.push(`八神加八门（${item.godFull || '—'}加${item.renDoor || '—'}门）：${item.godDoorText}`);
		bagongLines.push(`奇门演卦（门方）：${item.menFangYiGuaText || '无'}`);
		bagongLines.push('');
	});
	if(bagongLines.length && bagongLines[bagongLines.length - 1] === ''){
		bagongLines.pop();
	}
	appendSection(lines, '八宫详解', bagongLines);
	// 奇门派生/法奇门段(九宫方盘/旺相休囚死·月令能量/六害总览/化解方案/八门化气大阵/用神分论/财富七要/事业七要/
	// 恋爱姻缘/孤辰寡宿):复用独立 buildDunJiaSnapshotText(单一真值源),切其对应段以「奇门」前缀重发
	// (避免与六壬「概览」等碰撞)——独立遁甲页有、三式合一此前缺这 ~9 段。
	const qimenSectionMap = parseSnapshotSections(buildDunJiaSnapshotText(dunjia));
	appendPickedSections(lines, qimenSectionMap, SANSHI_QIMEN_EXTRA_SECTIONS, '奇门');
	// [YA v42] A 类硬缺:紫微四化叠加 tab(SanShiZiWeiSihua 独立计算)显示了却不入快照。
	// 复用该组件导出的同源纯函数取数(单一真值源,与 tab 同一套 getLayerSihua/ZWLuckPanel 计算);
	// 无盘/无四化不产段(零回归——旧调用不带 ziweiSihua 时输出与此前逐字节一致)。
	if(ziweiSihua && ziweiSihua.chart){
		const ziweiSihuaLines = buildSanShiZiweiSihuaSnapshotLines(ziweiSihua.chart, ziweiSihua.daxianIdx, ziweiSihua.liunianIdx);
		if(ziweiSihuaLines.length){
			appendSection(lines, '紫微四化', ziweiSihuaLines);
		}
	}
	return lines.join('\n').trim();
}
