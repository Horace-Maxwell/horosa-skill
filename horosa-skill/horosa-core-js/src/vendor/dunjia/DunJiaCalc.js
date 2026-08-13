import * as LRConst from '../liureng/LRConst.js';
import { Solar } from 'lunar-javascript';
import { buildQimenBaGongSnapshotLines, buildQimenBaGongKeYingSnapshotLines, buildQimenFuShiYiGua, buildQimenOverviewSummary } from './DunJiaBaGongRules.js';
import { buildFaQimenAnalysis } from './DunJiaFaCalc.js';
import { LUOSHU_NUM } from './DunJiaFaDoc.js';




export const SEX_OPTIONS = [
	{ value: 1, label: '男' },
	{ value: 0, label: '女' },
];

export const DATE_TYPE_OPTIONS = [
	{ value: 0, label: '公历' },
	{ value: 1, label: '农历' },
];

export const LEAP_MONTH_OPTIONS = [
	{ value: 0, label: '不闰月' },
	{ value: 1, label: '使用闰月' },
];

export const XUSHI_OPTIONS = [
	{ value: 0, label: '虚岁' },
	{ value: 1, label: '实岁' },
];

import { JINHAN_TABLE, JINHAN_DIRS, JINHAN_STAR_JI, JINHAN_DOOR_JI } from './jinhanRiJia.js';

export const JIEQI_OPTIONS = [
	{ value: 0, label: '节气按天' },
	{ value: 1, label: '节气按分' },
];

export const PAIPAN_OPTIONS = [
	{ value: 0, label: '年家奇门' },
	{ value: 1, label: '月家奇门' },
	{ value: 2, label: '日家奇门' },
	{ value: 3, label: '时家奇门' },
	{ value: 4, label: '刻家奇门' },   // [H-F] 十分局本地引擎(一时辰十刻,初局=时家局,逐刻阳顺阴逆推移)
	{ value: 6, label: '日家·古籍金函系' },   // [H-G] 六十干支占方全表(书表直录:八方星门+吉凶+喜神/吉时),独立体系不走局法
	// 综合(5):暂无确切算法,不暴露(引擎/后端分支保留,待校准后再开)。
];
// [H-F] 刻家分遁两档:zihou=子后阳午后阴(时支子~巳=阳遁、午~亥=阴遁,与节气无关,默认)/jieqi=冬至后阳夏至后阴(沿时家节气分遁)。
// [H-G] 古籍日家八门两档:book=书表直录(默认;阴阳盘各按原表);shun=全顺变体(休生伤杜景死惊开自北起顺布八方,星仍书表)。
export const JINHAN_MENPAI_OPTIONS = [
	{ value: 'book', label: '书表直录（默认）' },
	{ value: 'shun', label: '全顺变体（休门北起顺布）' },
];
export const KEJIA_FENDUN_OPTIONS = [
	{ value: 'zihou', label: '子后阳·午后阴（默认）' },
	{ value: 'jieqi', label: '按节气分遁（冬至后阳）' },
];
// [H-F] 日家定局粒度三档:yiyuan=六十日一局(现行经典,默认)/shitian=十日一局(逐旬按符头换元)/yitian=一日一局(至甲子起逐日推局,阳顺阴逆)。
export const DAYJIA_JU_OPTIONS = [
	{ value: 'yiyuan', label: '六十日一局（默认）' },
	{ value: 'shitian', label: '十日一局（逐旬换元）' },
	{ value: 'yitian', label: '一日一局（逐日推移）' },
];

export const ZHISHI_OPTIONS = [
	{ value: 0, label: '天禽值符-死门' },
	{ value: 1, label: '天禽值符-阴阳遁' },
	{ value: 2, label: '天禽值符-节气' },
];

export const YUEJIA_QIJU_OPTIONS = [
	{ value: 0, label: '年符头' },
	{ value: 1, label: '年支' },
	{ value: 2, label: '逐月换局（一月一局）' },
];

export const YEAR_GZ_OPTIONS = [
	{ value: 0, label: '年干支-正月初一' },
	{ value: 1, label: '年干支-立春当天' },
	{ value: 2, label: '年干支-立春交接' },
];

export const MONTH_GZ_OPTIONS = [
	{ value: 0, label: '月干支-节交接当天' },
	{ value: 1, label: '月干支-节交接时刻' },
];

export const DAY_GZ_OPTIONS = [
	{ value: 0, label: '日干支-晚子时按当天' },
	{ value: 1, label: '日干支-晚子时按明天' },
];

// 用户语义(拍板,字面直觉版):
//   after23NewDay=1「23点算第二天」= 23点起日柱进位次日(壬寅)
//   after23NewDay=0「24点算第二天」= 23点仍守今、24点才换日柱(辛丑)
export const DAY_SWITCH_OPTIONS = [
	{ value: 1, label: '23点算第二天' },
	{ value: 0, label: '24点算第二天' },
];

export const QIJU_METHOD_OPTIONS = [
	{ value: 'zhirun', label: '置闰' },
	{ value: 'chaibu', label: '拆补' },
	{ value: 'maoshan', label: '茅山' },
	{ value: 'wurun', label: '无闰' },
	{ value: 'shuzi', label: '阴盘' },   // 阴盘奇门:报数各位和%9(余0作9)定局(数字起局);原「阴盘」盘式归此(取数定局),与盘式正交
];

// 置闰天数(传本差异·设置面板可调):超神累计阈值,至点超神距(dgap=二至日−其前最近上元符头)
//   ≥该值即置闰。默认9=主流口径(满9天即闰)。修(2026-08-02 置闰事故复盘):旧实现三处检查点在
//   上年大雪/芒种/本年大雪各自量距且比较符不一(>=/>/>),与 kinqimen fork 的「至点锚」在节气
//   间距≠15天的年份差±1天,临界年整段错一节气块——现统一按至点锚判闰(见 buildYinyangdunMap)。
export const ZHIRUN_LEAP_OPTIONS = [
	{ value: 9, label: '置闰·超神满9天即闰（默认·主流）' },
	{ value: 8, label: '置闰·超神满8天即闰（从宽）' },
	{ value: 10, label: '置闰·超神满10天才闰（从严）' },   // [H-E] 第三口径:超神须超过 9 天(即≥10)才置闰
];

// [H-B] 暗干五法(通行诸法;默认关=零回归):
//   dipan=八门对应地盘干(每宫暗干=本宫之门「本位宫」的地盘干);
//   zhishi_fei=时干加值使宫,十干自然序洛书飞布(阳顺阴逆;时干与值使宫地盘干相同=伏吟,时干入中再飞);
//   zhishi_zhuan=同起点同序,改八卦轮转布(中宫不入);
//   manpan_fei=满盘旋转飞(自地盘戊所在宫起「甲」,十干自然序洛书飞满盘)。
export const ANGAN_MODE_OPTIONS = [
	{ value: 'off', label: '不用暗干（默认）' },
	{ value: 'dipan', label: '八门对应地盘干' },
	{ value: 'zhishi_fei', label: '时干加值使·飞布' },
	{ value: 'zhishi_zhuan', label: '时干加值使·转布' },
	{ value: 'manpan_fei', label: '满盘旋转飞' },
];
const TEN_GAN = '甲乙丙丁戊己庚辛壬癸'.split('');
const DOOR_HOME = { 休: '坎', 生: '艮', 伤: '震', 杜: '巽', 景: '离', 死: '坤', 惊: '兑', 开: '乾' };
const LUOSHU_GONG_SEQ = '坎坤震巽中乾兑艮离'.split('');   // 洛书 1-9 宫序(=EIGHT_GUA)
export function panAnGan(mode, ctx){
	const c = ctx || {};
	if(!mode || mode === 'off'){ return null; }
	const out = {};
	if(mode === 'dipan'){
		Object.keys(c.menGua || {}).forEach((g)=>{
			const door = String(c.menGua[g] || '').charAt(0);
			const home = DOOR_HOME[door];
			if(home && c.dipanGua && c.dipanGua[home]){ out[g] = c.dipanGua[home]; }
		});
		return out;
	}
	const isYang = c.yy === '阳';
	const step = isYang ? 1 : -1;
	if(mode === 'manpan_fei'){
		// 起宫=地盘戊所在宫;自「甲」起十干自然序,洛书飞满盘(含中),第十干与首宫重合成环。
		let startGong = '坎';
		Object.keys(c.dipanGua || {}).forEach((g)=>{ if(c.dipanGua[g] === '戊'){ startGong = g; } });
		const si = LUOSHU_GONG_SEQ.indexOf(startGong);
		for(let i = 0; i < 9; i++){
			const g = LUOSHU_GONG_SEQ[((si + step * i) % 9 + 9) % 9];
			out[g] = TEN_GAN[i % 10];
		}
		return out;
	}
	// zhishi_fei / zhishi_zhuan:时干加值使宫起,十干自然序续布
	const shiGan = String(c.shiGan || '').charAt(0);
	if(!shiGan){ return null; }
	let startGong = (c.zhishiGong && c.zhishiGong !== '中') ? c.zhishiGong : '中';
	// 伏吟判:值使宫地盘干===时干 → 时干入中宫再布
	if(c.dipanGua && c.dipanGua[startGong] === shiGan){ startGong = '中'; }
	const gi = TEN_GAN.indexOf(shiGan);
	if(mode === 'zhishi_fei'){
		const si = LUOSHU_GONG_SEQ.indexOf(startGong === '中' ? '中' : startGong);
		for(let i = 0; i < 9; i++){
			const g = LUOSHU_GONG_SEQ[((si + step * i) % 9 + 9) % 9];
			out[g] = TEN_GAN[(gi + i) % 10];
		}
		return out;
	}
	// 转布:八卦轮转(中不入);起宫若中则从寄宫起(ctx.jiGong,缺省坤=历史默认)
	const ring = isYang ? CLOCKWISE_EIGHTGUA : [...CLOCKWISE_EIGHTGUA].reverse();
	const ringStart = startGong === '中' ? (c.jiGong || '坤') : startGong;
	const seq = newList(ring, ringStart);
	for(let i = 0; i < 8; i++){ out[seq[i]] = TEN_GAN[(gi + i) % 10]; }
	return out;
}
// [H-B] 暗支:暗干在「时柱所在旬」内的配支(旬内干支一一对应,确定映射;甲=旬首支)。
export function anZhiOf(anGan, timeGz){
	const head = getXunHead(timeGz || '甲子');
	if(!head || !anGan){ return ''; }
	const GAN10 = TEN_GAN;
	const ZHI12 = '子丑寅卯辰巳午未申酉戌亥'.split('');
	const hz = ZHI12.indexOf(head.charAt(1));
	const gidx = GAN10.indexOf(String(anGan).charAt(0));
	if(hz < 0 || gidx < 0){ return ''; }
	return ZHI12[(hz + gidx) % 12];
}

// [H-B] 转盘八神预设:基串本为正统(阳遁勾陈朱雀/阴遁白虎玄武);现状默认=两遁恒虎玄(历史行为,零回归默认)。
export const GODS_PRESET_OPTIONS = [
	{ value: 'baihu_xuanwu', label: '两遁恒白虎玄武（默认）' },
	{ value: 'system', label: '按遁取神（阳勾陈朱雀·阴白虎玄武）' },
	{ value: 'gouchen_zhuque', label: '两遁恒勾陈朱雀' },
];
// 转盘八神名替换分派:baihu_xuanwu=勾雀→虎玄(默认=现状) / system=保基串(阳勾雀阴虎玄) / gouchen_zhuque=虎玄→勾雀。
export function applyGodsPreset(name, preset){
	const v = String(name || '');
	if(preset === 'system'){ return v; }
	if(preset === 'gouchen_zhuque'){ return v.replace(/虎/g, '勾').replace(/玄/g, '雀'); }
	return v.replace(/勾/g, '虎').replace(/雀/g, '玄');
}

// [H-C] 中宫寄宫五档:转盘系当值符/值使落中宫时,从寄宫起排(飞盘九星含中宫,不受辖)。
//   kun=恒寄坤二(历史默认,零回归) / yang_gen_yin_kun=阳遁寄艮八·阴遁寄坤二 / gen=恒寄艮八 /
//   siwei=按季寄四维(四立分界:立春起艮·立夏起巽·立秋起坤·立冬起乾,各领一季六气) /
//   bajie=按八节寄八宫(每节领三气:立春艮/春分震/立夏巽/夏至离/立秋坤/秋分兑/立冬乾/冬至坎)。
export const JIGONG_MODE_OPTIONS = [
	{ value: 'kun', label: '恒寄坤二宫（默认）' },
	{ value: 'yang_gen_yin_kun', label: '阳遁寄艮·阴遁寄坤' },
	{ value: 'gen', label: '恒寄艮八宫' },
	{ value: 'siwei', label: '按季寄四维（四立分界）' },
	{ value: 'bajie', label: '按八节寄八宫（一节三气）' },
];
const BAJIE_JIGONG = {
	立春: '艮', 雨水: '艮', 惊蛰: '艮',
	春分: '震', 清明: '震', 谷雨: '震',
	立夏: '巽', 小满: '巽', 芒种: '巽',
	夏至: '离', 小暑: '离', 大暑: '离',
	立秋: '坤', 处暑: '坤', 白露: '坤',
	秋分: '兑', 寒露: '兑', 霜降: '兑',
	立冬: '乾', 小雪: '乾', 大雪: '乾',
	冬至: '坎', 小寒: '坎', 大寒: '坎',
};
const SIWEI_JIGONG = {
	立春: '艮', 雨水: '艮', 惊蛰: '艮', 春分: '艮', 清明: '艮', 谷雨: '艮',
	立夏: '巽', 小满: '巽', 芒种: '巽', 夏至: '巽', 小暑: '巽', 大暑: '巽',
	立秋: '坤', 处暑: '坤', 白露: '坤', 秋分: '坤', 寒露: '坤', 霜降: '坤',
	立冬: '乾', 小雪: '乾', 大雪: '乾', 冬至: '乾', 小寒: '乾', 大寒: '乾',
};
// [H-E] 移星换宫后的值符/值使标记两档:follow=标记随几何平移(历史默认);recalc=移后盘视为新局重解(星门名+落宫)。
export const SHIFT_ZHIFU_OPTIONS = [
	{ value: 'follow', label: '随盘平移（默认）' },
	{ value: 'recalc', label: '移后重定值符值使' },
];
// 寄宫解析:未知模式/未知节气一律回落坤二(历史默认=诚实兜底,绝不臆造)。yy 收 '阳'/'阴'(或 '阳遁'/'阴遁')。
export function resolveJiGong(mode, yy, jieqi){
	if(mode === 'gen'){ return '艮'; }
	if(mode === 'yang_gen_yin_kun'){ return String(yy || '').charAt(0) === '阳' ? '艮' : '坤'; }
	if(mode === 'siwei'){ return SIWEI_JIGONG[normalizeJieqi(jieqi)] || '坤'; }
	if(mode === 'bajie'){ return BAJIE_JIGONG[normalizeJieqi(jieqi)] || '坤'; }
	return '坤';
}
function jiGongOf(ext, yy){
	return resolveJiGong(ext && ext.jiGongMode, yy, ext && ext.jieqi);
}

// WP-A 盘式(排盘法):转盘=排宫(八神,八卦轮转,默认) / 飞盘=飞宫(九神,洛书飞泊含中宫) / 飞转=混合(星转·门飞·九神)。
// 锚点规则三派一致(值符随时干、值使随时辰、神随值符、阳顺阴逆),差别只在转环 vs 飞宫 vs 飞转结合。
export const SCHOOL_OPTIONS = [
	{ value: '转盘', label: '转盘（排宫）' },
	{ value: '飞盘', label: '飞盘（飞宫）' },
	{ value: '混合', label: '飞转（混合）' },
];

// 混合(飞转结合,专题§4.2):九星=转盘排宫(星寄坤2不入中、天禽)、八门=飞盘飞宫(可入中5)、神=飞盘九神(含中宫)。
// 旧数据 school='阴盘' 已改作「起局·数字(报数)」→ 盘式归 转盘(阴盘排盘≈转盘);载入时另把 qijuMethod 迁为 shuzi。
function normalizeSchool(school){
	if(school === '飞盘' || school === '飛盤'){
		return '飞盘';
	}
	if(school === '混合' || school === '飞转' || school === '飛轉'){
		return '混合';
	}
	return '转盘';
}

export const KONG_MODE_OPTIONS = [
	{ value: 'day', label: '日空' },
	{ value: 'time', label: '时空' },
];

export const MA_MODE_OPTIONS = [
	{ value: 'day', label: '日马' },
	{ value: 'time', label: '时马' },
];

export const TIME_ALG_OPTIONS = [
	{ value: 0, label: '真太阳时' },
	{ value: 1, label: '直接时间' },
];

export const YIXING_OPTIONS = [
	{ value: 0, label: '原宫' },
	{ value: 1, label: '顺转一宫' },
	{ value: 2, label: '顺转二宫' },
	{ value: 3, label: '顺转三宫' },
	{ value: 4, label: '顺转四宫' },
	{ value: 5, label: '顺转五宫' },
	{ value: 6, label: '顺转六宫' },
	{ value: 7, label: '顺转七宫' },
];

// 命盘 / 事盘：保存去向。事盘→案例库 localCases（现状）；命盘→命盘库 localCharts（完整人命盘，跨技法自由使用，奇门设置存 payload.qimen）。
export const CHART_CATEGORY_OPTIONS = [
	{ value: 'shi', label: '事盘' },
	{ value: 'ming', label: '命盘' },
];

// 由出生时间求八字「年柱」天干（按立春分界，与奇门默认 yearGanZhiType=2 立春交接一致）。供左栏「相关人员」算各人生年干复用。按出生串缓存。
const YEAR_GAN_CACHE = {};
export function birthToYearGan(birth){
	if(!birth){
		return '';
	}
	const key = `${birth}`;
	if(YEAR_GAN_CACHE[key] !== undefined){
		return YEAR_GAN_CACHE[key];
	}
	let gan = '';
	try{
		const m = key.trim().match(/(-?\d{1,6})[-/](\d{1,2})[-/](\d{1,2})(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?/);
		if(m){
			const y = parseInt(m[1], 10);
			const mo = parseInt(m[2], 10);
			const d = parseInt(m[3], 10);
			const h = m[4] !== undefined ? parseInt(m[4], 10) : 12;
			const mi = m[5] !== undefined ? parseInt(m[5], 10) : 0;
			const s = m[6] !== undefined ? parseInt(m[6], 10) : 0;
			const solar = Solar.fromYmdHms(y, mo, d, h, mi, s);
			const lunar = solar.getLunar();
			const gz = lunar.getYearInGanZhiByLiChun ? lunar.getYearInGanZhiByLiChun() : lunar.getYearInGanZhi();
			gan = gz ? `${gz}`.charAt(0) : '';
		}
	}catch(e){
		gan = '';
	}
	YEAR_GAN_CACHE[key] = gan;
	return gan;
}

const GAN = '甲乙丙丁戊己庚辛壬癸'.split('');
const ZHI = '子丑寅卯辰巳午未申酉戌亥'.split('');
const JIAZI = [];
for(let i=0; i<60; i++){
	JIAZI.push(`${GAN[i % 10]}${ZHI[i % 12]}`);
}
const GANZHI_INDEX_MAP = JIAZI.reduce((mapObj, item, idx)=>{
	mapObj[item] = idx;
	return mapObj;
}, {});
const YINYANGDUN_CACHE = new Map();
const MAX_YINYANGDUN_CACHE = 24;

const XUN_HEADS = JIAZI.filter((_, idx)=>idx % 10 === 0);
const SAN_YUAN_FU_TOU = ['甲子', '甲午', '甲寅', '甲申', '甲辰', '甲戌', '己卯', '己酉', '己巳', '己亥', '己丑', '己未'];
const SAN_YUAN_FU_TOU_SET = new Set(SAN_YUAN_FU_TOU);
const CNUMBER = '一二三四五六七八九'.split('');
const EIGHT_GUA = '坎坤震巽中乾兑艮离'.split('');
const CLOCKWISE_EIGHTGUA = '坎艮震巽离坤兑乾'.split('');
const DOOR_R = '休生伤杜景死惊开'.split('');
const STAR_R = '蓬任冲辅英禽柱心'.split('');
const JIU_XING = '蓬芮冲辅禽心柱任英'.split('');

const JIEQI_NAME = '春分清明谷雨立夏小满芒种夏至小暑大暑立秋处暑白露秋分寒露霜降立冬小雪大雪冬至小寒大寒立春雨水惊蛰'.match(/../g);
const YANG_JIEQI = newList(JIEQI_NAME, '冬至').slice(0, 12);

const JJ = {
	甲子: '戊',
	甲戌: '己',
	甲申: '庚',
	甲午: '辛',
	甲辰: '壬',
	甲寅: '癸',
};

const JIEQI2JU = {
	冬至: '一七四阳',
	惊蛰: '一七四阳',
	小寒: '二八五阳',
	大寒: '三九六阳',
	春分: '三九六阳',
	雨水: '九六三阳',
	清明: '四一七阳',
	立夏: '四一七阳',
	立春: '八五二阳',
	谷雨: '五二八阳',
	小满: '五二八阳',
	芒种: '六三九阳',
	夏至: '九三六阴',
	白露: '九三六阴',
	小暑: '八二五阴',
	寒露: '六九三阴',
	立冬: '六九三阴',
	处暑: '一四七阴',
	霜降: '五八二阴',
	小雪: '五八二阴',
	大雪: '四七一阴',
	大暑: '七一四阴',
	秋分: '七一四阴',
	立秋: '二五八阴',
};

const JIEQI_CODE = {
	冬至: '一七四',
	惊蛰: '一七四',
	小寒: '二八五',
	大寒: '三九六',
	春分: '三九六',
	立春: '八五二',
	雨水: '九六三',
	清明: '四一七',
	立夏: '四一七',
	谷雨: '五二八',
	小满: '五二八',
	芒种: '六三九',
	夏至: '九三六',
	白露: '九三六',
	小暑: '八二五',
	大暑: '七一四',
	秋分: '七一四',
	立秋: '二五八',
	处暑: '一四七',
	寒露: '六九三',
	立冬: '六九三',
	霜降: '五八二',
	小雪: '五八二',
	大雪: '四七一',
};

const ZHISHI_BY_JIEQI = [
	{ list: ['冬至', '小寒', '大寒'], door: '休' },
	{ list: ['立春', '雨水', '惊蛰'], door: '生' },
	{ list: ['春分', '清明', '谷雨'], door: '伤' },
	{ list: ['立夏', '小满', '芒种'], door: '杜' },
	{ list: ['夏至', '小暑', '大暑'], door: '景' },
	{ list: ['立秋', '处暑', '白露'], door: '死' },
	{ list: ['秋分', '寒露', '霜降'], door: '惊' },
	{ list: ['立冬', '小雪', '大雪'], door: '开' },
];

const GUA_POS_MAP = {
	巽: 1,
	离: 2,
	坤: 3,
	震: 4,
	中: 5,
	兑: 6,
	艮: 7,
	坎: 8,
	乾: 9,
	干: 9,
};

const POS_GUA_MAP = {
	1: '巽',
	2: '离',
	3: '坤',
	4: '震',
	5: '中',
	6: '兑',
	7: '艮',
	8: '坎',
	9: '乾',
};

const BRANCH_TO_POS = {
	辰: 1,
	巳: 1,
	午: 2,
	未: 3,
	申: 3,
	卯: 4,
	酉: 6,
	寅: 7,
	丑: 7,
	子: 8,
	亥: 9,
	戌: 9,
};

const JIU_XING_NAME = {
	蓬: '天蓬',
	任: '天任',
	冲: '天冲',
	辅: '天辅',
	英: '天英',
	芮: '天芮',   // 飞盘值符=芮时显「天芮」(转盘走 zfStarDisp 已转内→天内,不经此)
	禽: '天禽',   // 飞盘值符=禽(中宫)时显「天禽」
	柱: '天柱',
	心: '天心',
	内: '天内',
};

const BA_MEN_NAME = {
	休: '休门',
	生: '生门',
	伤: '伤门',
	杜: '杜门',
	景: '景门',
	死: '死门',
	惊: '惊门',
	开: '开门',
};

// 旺相休囚死(§17.1):以月令五行定符号能量。各符号五行 + 月支→月令五行 + 旺衰口诀表。
const STAR_WUXING = { 蓬: '水', 任: '土', 冲: '木', 辅: '木', 英: '火', 芮: '土', 禽: '土', 内: '土', 柱: '金', 心: '金' };
const MEN_WUXING = { 休: '水', 生: '土', 伤: '木', 杜: '木', 景: '火', 死: '土', 惊: '金', 开: '金' };
const GAN_WUXING = { 甲: '木', 乙: '木', 丙: '火', 丁: '火', 戊: '土', 己: '土', 庚: '金', 辛: '金', 壬: '水', 癸: '水' };
// grid 宫位→卦五行(巽1木/离2火/坤3土/震4木/中5土/兑6金/艮7土/坎8水/乾9金)
const PALACE_GUA_WUXING = { 1: '木', 2: '火', 3: '土', 4: '木', 5: '土', 6: '金', 7: '土', 8: '水', 9: '金' };
const BRANCH_WUXING = { 寅: '木', 卯: '木', 巳: '火', 午: '火', 申: '金', 酉: '金', 亥: '水', 子: '水', 辰: '土', 戌: '土', 丑: '土', 未: '土' };
// 月令五行 → {旺,相,休,囚,死} 对应的五行(当令者旺、我生者相、生我者休、克我者囚、我克者死)。
const WANGSHUAI_BY_MONTH = {
	木: { 木: '旺', 火: '相', 水: '休', 金: '囚', 土: '死' },
	火: { 火: '旺', 土: '相', 木: '休', 水: '囚', 金: '死' },
	金: { 金: '旺', 水: '相', 土: '休', 火: '囚', 木: '死' },
	水: { 水: '旺', 木: '相', 金: '休', 土: '囚', 火: '死' },
	土: { 土: '旺', 金: '相', 火: '休', 木: '囚', 水: '死' },
};

function wangShuaiOf(elem, monthElem){
	if(!elem || !monthElem || !WANGSHUAI_BY_MONTH[monthElem]){
		return '';
	}
	return WANGSHUAI_BY_MONTH[monthElem][elem] || '';
}

// 输入排好的 pan,返回 月令五行 + 各宫 星/门/天盘干/地盘干 的旺相休囚死。纯派生(不改盘),供显示与 AI 断盘「看旺衰」步。
export function buildQimenWangShuai(pan){
	if(!pan || !pan.ganzhi){
		return null;
	}
	const monthBranch = `${pan.ganzhi.month || ''}`.substring(1, 2);
	const monthElem = BRANCH_WUXING[monthBranch] || '';
	const cells = Array.isArray(pan.cells) ? pan.cells : [];
	const palaces = cells.filter((c)=>!c.isCenter).map((c)=>{
		const starElem = STAR_WUXING[c.tianXing] || '';
		const menElem = MEN_WUXING[c.door] || '';
		const tianElem = GAN_WUXING[c.tianGan] || '';
		const diElem = GAN_WUXING[c.diGan] || '';
		const gongElem = PALACE_GUA_WUXING[c.palaceNum] || '';
		return {
			palaceNum: c.palaceNum,
			palaceName: c.palaceName,
			star: c.tianXing,
			starWuxing: starElem,
			starWangShuai: wangShuaiOf(starElem, monthElem),
			door: c.door,
			doorWuxing: menElem,
			doorWangShuai: wangShuaiOf(menElem, monthElem),
			tianGan: c.tianGan,
			tianGanWangShuai: wangShuaiOf(tianElem, monthElem),
			diGan: c.diGan,
			diGanWangShuai: wangShuaiOf(diElem, monthElem),
			gongWuxing: gongElem,
			gongWangShuai: wangShuaiOf(gongElem, monthElem),
		};
	});
	return { monthBranch, monthElem, palaces };
}

// 数字奇门/报数盘(§5.5 通则):所报之数除9取余(余0作9)→用神宫(洛书1-9)+卦/方位。
// ⚠️各家规则差异大(取数对象/是否含阴阳遁/余数映射),此为通则框架,精确依所宗课本。
const SHUZI_GONG_INFO = {
	1: ['坎', '正北'], 2: ['坤', '西南'], 3: ['震', '正东'], 4: ['巽', '东南'], 5: ['中', '中央'],
	6: ['乾', '西北'], 7: ['兑', '正西'], 8: ['艮', '东北'], 9: ['离', '正南'],
};
export function computeShuziYongShenGong(numStr){
	const digits = `${numStr || ''}`.replace(/[^0-9]/g, '');
	if(!digits){
		return null;
	}
	const sum = digits.split('').reduce((acc, d)=>acc + Number(d), 0);
	let gong = sum % 9;
	if(gong === 0){
		gong = 9;
	}
	const info = SHUZI_GONG_INFO[gong] || ['', ''];
	return { digits, sum, gong, gua: info[0], direction: info[1] };
}

export const GUXU = {
	甲子: '戌亥',
	甲戌: '申酉',
	甲申: '午未',
	甲午: '辰巳',
	甲辰: '寅卯',
	甲寅: '子丑',
};

const PALACE_GRID = [1, 2, 3, 4, 5, 6, 7, 8, 9];
const PALACE_NAME = {
	1: '巽',
	2: '离',
	3: '坤',
	4: '震',
	5: '中',
	6: '兑',
	7: '艮',
	8: '坎',
	9: '乾',
};
const OUTER_RING_CLOCKWISE = [1, 2, 3, 6, 9, 8, 7, 4];

const JI_XING_RULE = {
	1: '壬癸',
	2: '辛',
	3: '己',
	4: '戊',
	7: '庚',
};

const RU_MU_RULE = {
	1: '辛壬',
	3: '甲癸',
	7: '丁己庚',
	9: '乙丙戊',
};

const MEN_PO_RULE = {
	1: '开惊',
	2: '休',
	3: '伤杜',
	4: '开惊',
	6: '景',
	7: '伤杜',
	8: '生死',
	9: '景',
};

// 复用 Horosa-APP 的非八字神煞规则（奇门/六壬/六爻共用）
const QIMEN_SHENSHA_DAY_STEMS = {
	日禄: { 甲: ['寅'], 乙: ['卯'], 丙: ['巳'], 丁: ['午'], 戊: ['巳'], 己: ['午'], 庚: ['申'], 辛: ['酉'], 壬: ['亥'], 癸: ['子'] },
	日德: { 甲: ['寅'], 乙: ['申'], 丙: ['巳'], 丁: ['亥'], 戊: ['巳'], 己: ['寅'], 庚: ['申'], 辛: ['巳'], 壬: ['亥'], 癸: ['巳'] },
	文昌: { 甲: ['巳'], 乙: ['午'], 丙: ['申'], 丁: ['酉'], 戊: ['申'], 己: ['酉'], 庚: ['亥'], 辛: ['子'], 壬: ['寅'], 癸: ['卯'] },
	游都: { 甲: ['丑'], 乙: ['子'], 丙: ['寅'], 丁: ['巳'], 戊: ['申'], 己: ['丑'], 庚: ['子'], 辛: ['寅'], 壬: ['巳'], 癸: ['申'] },
};
const QIMEN_GUIREN_DAY_NIGHT = {
	甲: ['丑', '未'],
	乙: ['子', '申'],
	丙: ['亥', '酉'],
	丁: ['亥', '酉'],
	戊: ['丑', '未'],
	己: ['子', '申'],
	庚: ['丑', '未'],
	辛: ['午', '寅'],
	壬: ['卯', '巳'],
	癸: ['卯', '巳'],
};

const QIMEN_SHENSHA_DAY_BRANCH = {
	驿马: { 子: ['寅'], 丑: ['亥'], 寅: ['申'], 卯: ['巳'], 辰: ['寅'], 巳: ['亥'], 午: ['申'], 未: ['巳'], 申: ['寅'], 酉: ['亥'], 戌: ['申'], 亥: ['巳'] },
	日马: { 子: ['寅'], 丑: ['亥'], 寅: ['申'], 卯: ['巳'], 辰: ['寅'], 巳: ['亥'], 午: ['申'], 未: ['巳'], 申: ['寅'], 酉: ['亥'], 戌: ['申'], 亥: ['巳'] },
	桃花: { 子: ['酉'], 丑: ['午'], 寅: ['卯'], 卯: ['子'], 辰: ['酉'], 巳: ['午'], 午: ['卯'], 未: ['子'], 申: ['酉'], 酉: ['午'], 戌: ['卯'], 亥: ['子'] },
	破碎: { 子: ['巳'], 丑: ['丑'], 寅: ['酉'], 卯: ['巳'], 辰: ['丑'], 巳: ['酉'], 午: ['巳'], 未: ['丑'], 申: ['酉'], 酉: ['巳'], 戌: ['丑'], 亥: ['酉'] },
};

const QIMEN_SHENSHA_MONTH_BRANCH = {
	天马: { 子: ['寅'], 丑: ['辰'], 寅: ['午'], 卯: ['申'], 辰: ['戌'], 巳: ['子'], 午: ['寅'], 未: ['辰'], 申: ['午'], 酉: ['申'], 戌: ['戌'], 亥: ['子'] },
	医星: { 子: ['申', '寅'], 丑: ['酉', '卯'], 寅: ['戌', '辰'], 卯: ['亥', '巳'], 辰: ['子', '午'], 巳: ['丑', '未'], 午: ['寅', '申'], 未: ['卯', '酉'], 申: ['辰', '戌'], 酉: ['巳', '亥'], 戌: ['午', '子'], 亥: ['未', '丑'] },
	生气: { 子: ['戌'], 丑: ['亥'], 寅: ['子'], 卯: ['丑'], 辰: ['寅'], 巳: ['卯'], 午: ['辰'], 未: ['巳'], 申: ['午'], 酉: ['未'], 戌: ['申'], 亥: ['酉'] },
	死气: { 子: ['辰'], 丑: ['巳'], 寅: ['午'], 卯: ['未'], 辰: ['申'], 巳: ['酉'], 午: ['戌'], 未: ['亥'], 申: ['子'], 酉: ['丑'], 戌: ['寅'], 亥: ['卯'] },
	血支: { 子: ['亥'], 丑: ['子'], 寅: ['丑'], 卯: ['寅'], 辰: ['卯'], 巳: ['辰'], 午: ['巳'], 未: ['午'], 申: ['未'], 酉: ['申'], 戌: ['酉'], 亥: ['戌'] },
	成神: { 子: ['亥'], 丑: ['寅'], 寅: ['巳'], 卯: ['申'], 辰: ['亥'], 巳: ['寅'], 午: ['巳'], 未: ['申'], 申: ['亥'], 酉: ['寅'], 戌: ['巳'], 亥: ['申'] },
	会神: { 子: ['申'], 丑: ['辰'], 寅: ['未'], 卯: ['戌'], 辰: ['寅'], 巳: ['亥'], 午: ['酉'], 未: ['子'], 申: ['丑'], 酉: ['午'], 戌: ['巳'], 亥: ['卯'] },
	解神: { 子: ['午'], 丑: ['午'], 寅: ['申'], 卯: ['申'], 辰: ['戌'], 巳: ['戌'], 午: ['子'], 未: ['子'], 申: ['寅'], 酉: ['寅'], 戌: ['辰'], 亥: ['辰'] },
	天目: { 子: ['丑'], 丑: ['丑'], 寅: ['辰'], 卯: ['辰'], 辰: ['辰'], 巳: ['未'], 午: ['未'], 未: ['未'], 申: ['戌'], 酉: ['戌'], 戌: ['戌'], 亥: ['丑'] },
	月厌: { 子: ['子'], 丑: ['亥'], 寅: ['戌'], 卯: ['酉'], 辰: ['申'], 巳: ['未'], 午: ['午'], 未: ['巳'], 申: ['辰'], 酉: ['卯'], 戌: ['寅'], 亥: ['丑'] },
	月破: { 子: ['午'], 丑: ['未'], 寅: ['申'], 卯: ['酉'], 辰: ['戌'], 巳: ['亥'], 午: ['子'], 未: ['丑'], 申: ['寅'], 酉: ['卯'], 戌: ['辰'], 亥: ['巳'] },
	贼神: { 子: ['子'], 丑: ['子'], 寅: ['卯'], 卯: ['卯'], 辰: ['卯'], 巳: ['午'], 午: ['午'], 未: ['午'], 申: ['酉'], 酉: ['酉'], 戌: ['酉'], 亥: ['子'] },
	丧车: { 子: ['午'], 丑: ['午'], 寅: ['酉'], 卯: ['酉'], 辰: ['酉'], 巳: ['子'], 午: ['子'], 未: ['子'], 申: ['卯'], 酉: ['卯'], 戌: ['卯'], 亥: ['午'] },
};

const QIMEN_SHENSHA_YEAR_BRANCH = {
	年马: { 子: ['寅'], 丑: ['亥'], 寅: ['申'], 卯: ['巳'], 辰: ['寅'], 巳: ['亥'], 午: ['申'], 未: ['巳'], 申: ['寅'], 酉: ['亥'], 戌: ['申'], 亥: ['巳'] },
	病符: { 子: ['亥'], 丑: ['子'], 寅: ['丑'], 卯: ['寅'], 辰: ['卯'], 巳: ['辰'], 午: ['巳'], 未: ['午'], 申: ['未'], 酉: ['申'], 戌: ['酉'], 亥: ['戌'] },
	孤辰: { 子: ['寅'], 丑: ['寅'], 寅: ['巳'], 卯: ['巳'], 辰: ['巳'], 巳: ['申'], 午: ['申'], 未: ['申'], 申: ['亥'], 酉: ['亥'], 戌: ['亥'], 亥: ['寅'] },
	寡宿: { 子: ['戌'], 丑: ['戌'], 寅: ['丑'], 卯: ['丑'], 辰: ['丑'], 巳: ['辰'], 午: ['辰'], 未: ['辰'], 申: ['未'], 酉: ['未'], 戌: ['未'], 亥: ['戌'] },
	丧门: { 子: ['寅'], 丑: ['卯'], 寅: ['辰'], 卯: ['巳'], 辰: ['午'], 巳: ['未'], 午: ['申'], 未: ['酉'], 申: ['戌'], 酉: ['亥'], 戌: ['子'], 亥: ['丑'] },
	吊客: { 子: ['戌'], 丑: ['亥'], 寅: ['子'], 卯: ['丑'], 辰: ['寅'], 巳: ['卯'], 午: ['辰'], 未: ['巳'], 申: ['午'], 酉: ['未'], 戌: ['申'], 亥: ['酉'] },
};

function normalizeNum(v, defVal = 0){
	const n = parseInt(v, 10);
	return Number.isNaN(n) ? defVal : n;
}

function normalizeShiftPalace(v){
	const n = normalizeNum(v, 0);
	if(n < 0){
		return 0;
	}
	if(n > 7){
		return n % 8;
	}
	return n;
}

function normalizeTimeAlg(value){
	return value === 1 ? 1 : 0;
}

function getTimeAlgLabel(value){
	return normalizeTimeAlg(value) === 1 ? '直接时间' : '真太阳时';
}

function normalizeText(s){
	if(!s){
		return '';
	}
	return `${s}`
		.replace(/穀/g, '谷')
		.replace(/滿/g, '满')
		.replace(/種/g, '种')
		.replace(/蟄/g, '蛰')
		.replace(/驚/g, '惊')
		.replace(/時/g, '时')
		.replace(/盤/g, '盘')
		.replace(/門/g, '门')
		.replace(/節/g, '节')
		.replace(/氣/g, '气')
		.replace(/閏/g, '闰')
		.replace(/馬/g, '马')
		.replace(/飛/g, '飞')
		.replace(/長/g, '长')
		.replace(/運/g, '运')
		.replace(/處/g, '处')
		.replace(/陰/g, '阴')
		.replace(/陽/g, '阳')
		.replace(/傷/g, '伤')
		.replace(/開/g, '开')
		.replace(/沖/g, '冲')
		.replace(/輔/g, '辅')
		.replace(/離/g, '离')
		.replace(/兌/g, '兑')
		.replace(/乾/g, '乾')
		.trim();
}

function normalizeGanZhi(gz){
	const t = normalizeText(gz);
	return t.substring(0, 2);
}

function normalizeJieqi(jieqi){
	return normalizeText(jieqi).substring(0, 2);
}

function getOptionLabel(list, value){
	const one = list.find((item)=>item.value === value);
	// 缺省值兜底为空串:此前 `${undefined}` 字符串化成「undefined」脏字样直入快照(如「命式：undefined」),
	// 且 truthy 穿透一切 if 拦截——空串既能被 || 兜底又能被 if 拦。
	if(one){ return one.label; }
	return (value === undefined || value === null) ? '' : `${value}`;
}

function getGanzhiGan(gz){
	return normalizeGanZhi(gz).substring(0, 1);
}

function getGanzhiZhi(gz){
	return normalizeGanZhi(gz).substring(1, 2);
}

function parseDateTime(fields){
	if(!fields || !fields.date || !fields.time){
		return null;
	}
	const dateStr = fields.date.value.format('YYYY-MM-DD');
	const timeStr = fields.time.value.format('HH:mm:ss');
	const dparts = dateStr.split('-');
	const tparts = timeStr.split(':');
	if(dparts.length < 3 || tparts.length < 2){
		return null;
	}
	const year = normalizeNum(dparts[0], 0);
	const month = normalizeNum(dparts[1], 1);
	const day = normalizeNum(dparts[2], 1);
	const hour = normalizeNum(tparts[0], 0);
	const minute = normalizeNum(tparts[1], 0);
	const second = normalizeNum(tparts[2], 0);
	return {
		year,
		month,
		day,
		hour,
		minute,
		second,
		dateStr,
		timeStr,
	};
}

function parseDateTimeText(rawText){
	const text = normalizeText(rawText);
	if(!text){
		return null;
	}
	const normalized = text.replace('T', ' ').replace('Z', ' ').trim();
	const m = normalized.match(/([-+]?\d{1,6})[/-](\d{1,2})[/-](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?/);
	if(!m){
		return null;
	}
	return {
		year: normalizeNum(m[1], 0),
		month: normalizeNum(m[2], 1),
		day: normalizeNum(m[3], 1),
		hour: normalizeNum(m[4], 0),
		minute: normalizeNum(m[5], 0),
		second: normalizeNum(m[6], 0),
	};
}

function resolveCalcDateTime(dateParts, nongli, opts, context){
	if(normalizeTimeAlg(opts && opts.timeAlg) === 0){
		const solarParsed = parseDateTimeText(
			(nongli && nongli.birth) || (context && context.displaySolarTime) || ''
		);
		if(solarParsed){
			return {
				...dateParts,
				...solarParsed,
			};
		}
	}
	return dateParts;
}

function newList(list, start){
	const idx = list.indexOf(start);
	if(idx < 0){
		throw new Error(`start.not.found:${start}`);
	}
	return [...list.slice(idx), ...list.slice(0, idx)];
}

function newListR(list, start){
	const idx = list.indexOf(start);
	if(idx < 0){
		throw new Error(`start.not.found:${start}`);
	}
	const out = [];
	let p = idx;
	for(let i=0; i<list.length; i++){
		out.push(list[(p + list.length) % list.length]);
		p -= 1;
	}
	return out;
}

function zipToMap(keys, vals){
	const out = {};
	for(let i=0; i<keys.length; i++){
		out[keys[i]] = vals[i];
	}
	return out;
}

function invertMap(mapObj){
	const out = {};
	Object.keys(mapObj || {}).forEach((k)=>{
		out[mapObj[k]] = k;
	});
	return out;
}

function getGanzhiIndex(gz){
	const key = normalizeGanZhi(gz);
	const idx = GANZHI_INDEX_MAP[key];
	return idx >= 0 ? idx : 0;
}

export function getXunHead(gz){
	const idx = getGanzhiIndex(gz);
	return JIAZI[Math.floor(idx / 10) * 10] || '甲子';
}

function nextGanZhi(gz){
	const idx = getGanzhiIndex(gz);
	return JIAZI[(idx + 1) % 60];
}

function prevGanZhi(gz){
	const idx = getGanzhiIndex(gz);
	return JIAZI[(idx + 59) % 60];
}

function getHourBranch(hour){
	if(hour === 23 || hour === 0){
		return '子';
	}
	const idx = Math.floor((hour + 1) / 2) % 12;
	return ZHI[idx];
}

function getHourGanZhi(dayGanZhi, hour){
	const dayGan = normalizeGanZhi(dayGanZhi).substring(0, 1);
	const branch = getHourBranch(hour);
	const startGan = (function getStartGan(){
		if('甲己'.includes(dayGan)) return '甲';
		if('乙庚'.includes(dayGan)) return '丙';
		if('丙辛'.includes(dayGan)) return '戊';
		if('丁壬'.includes(dayGan)) return '庚';
		return '壬';
	})();
	const ganIdx = GAN.indexOf(startGan);
	const zhiIdx = ZHI.indexOf(branch);
	return `${GAN[(ganIdx + zhiIdx) % 10]}${branch}`;
}

function getCurrentJieqi(nongli){
	const jq = normalizeJieqi(nongli && nongli.jieqi ? nongli.jieqi : '');
	if(jq){
		return jq;
	}
	const delta = `${(nongli && nongli.jiedelta) || ''}`;
	const idxAfter = delta.indexOf('后第');
	if(idxAfter > 0){
		return normalizeJieqi(delta.substring(0, idxAfter));
	}
	const idxBefore = delta.indexOf('前第');
	if(idxBefore > 0){
		return normalizeJieqi(delta.substring(0, idxBefore));
	}
	return '';
}

function resolveFuTouByBacktrack(dayGanZhi){
	let current = normalizeGanZhi(dayGanZhi || '甲子');
	for(let i=0; i<60; i++){
		if(SAN_YUAN_FU_TOU_SET.has(current)){
			return current;
		}
		current = prevGanZhi(current);
	}
	return getXunHead(dayGanZhi || '甲子');
}

function findYuan(dayGanZhi){
	const idx = getGanzhiIndex(dayGanZhi) % 15;
	if(idx < 5){
		return '上元';
	}
	if(idx < 10){
		return '中元';
	}
	return '下元';
}

function qimenJuNameChaibu(jieqi, dayGanZhi){
	const jq = normalizeJieqi(jieqi);
	const yy = YANG_JIEQI.includes(jq) ? '阳遁' : '阴遁';
	const yuan = findYuan(dayGanZhi);
	const code = JIEQI_CODE[jq] || '一七四';
	const yuanIdx = yuan === '上元' ? 0 : (yuan === '中元' ? 1 : 2);
	return `${yy}${code[yuanIdx]}局${yuan}`;
}

function juNumberToCn(num){
	const idx = Math.min(9, Math.max(1, normalizeNum(num, 1))) - 1;
	return CNUMBER[idx];
}

function buildQmjuByMeta(yinYangDun, juShu, sanYuan){
	const yy = `${yinYangDun || ''}`.indexOf('阴') >= 0 ? '阴遁' : '阳遁';
	return `${yy}${juNumberToCn(juShu)}局${sanYuan || '上元'}`;
}

function isYangDunJieqi(jieqi){
	return YANG_JIEQI.indexOf(normalizeJieqi(jieqi)) >= 0;
}

// [H-I] 年家定局两档:sanyuan(默认)=六十年一元恒一局(上1/中4/下7,皆阴遁,历史行为);
//   yinian=逐年换局——三元甲子起元首局逐年逆退九局循环,与通行年游九星完全同构
//   (公域可核验锚:1984甲子=7、2025乙巳=2、2026丙午=1)。元名仍按六十年块显示。
export const YEARJIA_JU_OPTIONS = [
	{ value: 'sanyuan', label: '六十年一局（默认）' },
	{ value: 'yinian', label: '一年一局（逐年逆退）' },
];
function calcYearJiaMeta(year, yearJiaJu){
	if(year >= 0 && year <= 3){
		return { sanYuan: '中元', juShu: 4, yinYangDun: '阴遁' };
	}
	const cycle = ((Math.floor((year - 4) / 60) % 3) + 3) % 3;
	const FIRST = [7, 1, 4][cycle];
	const YUAN = ['下元', '上元', '中元'][cycle];
	if(yearJiaJu === 'yinian'){
		const n = (((year - 4) % 60) + 60) % 60;
		const ju = (((FIRST - 1 - n) % 9) + 9) % 9 + 1;
		return { sanYuan: YUAN, juShu: ju, yinYangDun: '阴遁' };
	}
	return { sanYuan: YUAN, juShu: FIRST, yinYangDun: '阴遁' };
}

// 月家奇门(经典「附月奇门·年干支定局法」/又法,五年一元):局由年柱「符头」(最近甲/己年)定,整个 5 年元块同一局,皆阴遁。
//   符头支 子午卯酉=上元阴七 / 寅申巳亥=中元阴一 / 辰戌丑未=下元阴四 ≡ 局=[7,1,4][符头60序÷5 mod3]。
//   月柱仅作值符值使锚点(值符随月干、值使随月支、寻月柱旬首,见 calcDunJia panGanzhi),不参与定局。
// 真值核验(用户 4 参考盘 + 课本非典型例):2026丙午/2025乙巳→符头甲辰(辰)→下元阴四 ✓✓;2048戊辰→符头甲子(子)→上元阴七 ✓;
//   2053癸酉→符头己巳(巳)→中元阴一 ✓;2003癸未→符头己卯(卯)→上元阴七 ✓(课本) = 5/5。
//   〔对比〕又一传本「逐10月递减(上7→6→…→2)」对 2026 给阴二,不符 → 弃用;故取年符头定局法。
// yueJiaQiJuType:0=年柱符头(正传,默认) / 1=年支直取(变体,不取符头,供对比)。
const MONTH_ZHI_JU = { 子: 7, 午: 7, 卯: 7, 酉: 7, 寅: 1, 申: 1, 巳: 1, 亥: 1, 辰: 4, 戌: 4, 丑: 4, 未: 4 };
const MONTH_JU_YUAN = { 7: '上元', 1: '中元', 4: '下元' };
// [H-I] 逐月换局(一月一局):正月入中局按年支组(仲年子午卯酉=8/孟年寅申巳亥=2/季年辰戌丑未=5),
//   逐月逆退九局循环——月家文献自载「孟年正月二黑、仲年八白、季年五黄,星顺月逆而布」,
//   与通行月游九星同构(公域可核验)。月序按月柱地支(寅=正月…丑=十二月),皆阴遁。
const MONTH_START_JU_MONTHLY = { 子: 8, 午: 8, 卯: 8, 酉: 8, 寅: 2, 申: 2, 巳: 2, 亥: 2, 辰: 5, 戌: 5, 丑: 5, 未: 5 };
function calcYueJiaMeta(ganzhi, yueJiaQiJuType){
	const t = normalizeNum(yueJiaQiJuType, 0);
	if(t === 2){
		const yearZhi = `${ganzhi.year || '甲子'}`.charAt(1);
		const monthZhi = `${ganzhi.month || '丙寅'}`.charAt(1);
		const first = MONTH_START_JU_MONTHLY[yearZhi] || 8;
		const zi = ZHI.indexOf(monthZhi);
		const m = zi >= 0 ? ((zi - 2 + 12) % 12) : 0;
		const ju = (((first - 1 - m) % 9) + 9) % 9 + 1;
		// qmju 显式给出(无元名尾)——否则 calcDunJia 兜底 buildQmjuByMeta 会拼上「上元」假元名进 juText
		return { sanYuan: '', juShu: ju, yinYangDun: '阴遁', qmju: `阴遁${juNumberToCn(ju)}局` };
	}
	const yearIdx = ((getGanzhiIndex(ganzhi.year || '甲子') % 60) + 60) % 60;
	// 符头 = 最近的甲/己年(60 序向下取到 5 的倍数);变体则直接用年支。
	const baseIdx = (t === 1) ? yearIdx : (yearIdx - (yearIdx % 5));
	const zhi = ZHI[baseIdx % 12];
	const juShu = MONTH_ZHI_JU[zhi] || 4;
	return { sanYuan: MONTH_JU_YUAN[juShu] || '下元', juShu, yinYangDun: '阴遁' };
}

// 日家奇门(经典「又法日奇门起例」/节气三元·六十日一局):冬至后第1/2/3甲子(各60日)=阳遁 1/7/4 局;
//   夏至后第1/2/3甲子(各60日)=阴遁 9/3/6 局。皆以其日旬首所值星为值符、门为值使;超接置闰如时奇(符头超30日即置闰)。
//   实现:阴阳遁由节气半年定;局由「距本半年起始『至甲子』的 60 日块数 mod3」定(至甲子=离冬/夏至最近之甲子日;超30日置闰取后一甲子)。
// 真值核验(用户 5 参考盘):2026乙丑=阳一(上块)/2053丁未=阳七(中块)/2025丁酉=阴六(下块)/2048壬寅=阴六(下块)/1964癸亥=阴三(中块) = 5/5。
//   ⚠️ 阴遁序列取 9·3·6(§10 节气三元),非又法原文「9·2·6」——1964癸亥落中块,真值阴三(9·2·6 会给阴二,证伪;传本有别,从真软件)。
//   〔对比弃用〕传本「日支定局(子午2·丑未6·寅申1·卯酉8·辰戌4·巳亥9)」对乙丑给阳六不符;「findYuan符头元(无置闰漂移)」对丁酉给阴九不符。
const DAY_BLOCK_JU = { 阳: [1, 7, 4], 阴: [9, 3, 6] };
const DAY_BLOCK_YUAN = ['上元', '中元', '下元'];
function dayJiaHalfYear(seeds, dateParts){
	// 以「至」定半年(非节令!):夏至≤date<本年末冬至 → 阴遁(至=夏至);本年末冬至后或本年夏至前 → 阳遁(至=最近冬至)。
	// 节令(nongli.jieqi)在至界会滞后(如06-22已过夏至仍报芒种)→ 必须用至日期判,否则阴阳遁错半年。
	if(!seeds){ return null; }
	const y = dateParts.year;
	const dU = keyToUtcDay(`${y}${`${dateParts.month}`.padStart(2, '0')}${`${dateParts.day}`.padStart(2, '0')}`);
	if(!Number.isFinite(dU)){ return null; }
	// ⚠️ 种子约定有两种:后端「年内至 seeds[y].冬至=Dec(y)」vs 本地 buildLocalJieqiYearSeed「上年至 seeds[y].冬至=Dec(y-1)」。
	//   故不按种子索引年取(会因约定不同错半年,曾致 12-22 退阴九),改按「至日实际年份」跨 y-1/y/y+1 三年定位——
	//   两种约定都能取到 Dec(y-1)/Dec(y)/Jun(y),彻底兼容。
	const pick = (term, yr)=>{
		let found = null;
		[y - 1, y, y + 1].forEach((yy)=>{
			const s = seeds[yy] && seeds[yy][term];
			if(s && s.dateKey && `${s.dateKey}`.slice(0, 4) === `${yr}`){ found = s; }
		});
		return found;
	};
	const xz = pick('夏至', y);            // 本年夏至(约 Jun y)
	const dzStart = pick('冬至', y - 1);    // 本年初冬至(约 Dec y-1),启动本年阳半年
	const dzEnd = pick('冬至', y);          // 本年末冬至(约 Dec y),阴→阳界
	if(!xz || !xz.dateKey){ return null; }
	const xzU = keyToUtcDay(xz.dateKey);
	if(dzEnd && dzEnd.dateKey && dU >= keyToUtcDay(dzEnd.dateKey)){ return { yang: true, zhiSeed: dzEnd }; }  // 本年末冬至后 → 阳遁
	if(dU >= xzU){ return { yang: false, zhiSeed: xz }; }                                                      // 本年夏至后 → 阴遁
	return { yang: true, zhiSeed: dzStart || null };                                                           // 夏至前 → 阳遁(至=上年冬至)
}
function calcDayJiaMeta(dateParts, dayGanZhi, jieqi, context, dayJiaJu){
	const seeds = context && context.jieqiYearSeeds ? context.jieqiYearSeeds : null;
	const half = dayJiaHalfYear(seeds, dateParts);
	const yang = half ? half.yang : isYangDunJieqi(jieqi);   // 有种子=至定半年(准);无种子退化用节气(可能滞后)
	const yy = yang ? '阳' : '阴';
	// [H-F] 十日一局:逐旬按符头换元(甲子甲午旬=上元/甲戌甲辰=中元/甲申甲寅=下元),局取该元经典局。
	if(dayJiaJu === 'shitian'){
		const block = ({ 上元: 0, 中元: 1, 下元: 2 })[findYuan(dayGanZhi)] || 0;
		return { sanYuan: DAY_BLOCK_YUAN[block], juShu: DAY_BLOCK_JU[yy][block], yinYangDun: yang ? '阳遁' : '阴遁' };
	}
	let block = null;
	let sinceJiazi = null;
	const zhiSeed = half ? half.zhiSeed : null;
	if(zhiSeed && zhiSeed.dateKey && zhiSeed.dayGanzhi){
		const dayUtc = keyToUtcDay(`${dateParts.year}${`${dateParts.month}`.padStart(2, '0')}${`${dateParts.day}`.padStart(2, '0')}`);
		const zhiUtc = keyToUtcDay(zhiSeed.dateKey);
		const z = ((getGanzhiIndex(zhiSeed.dayGanzhi) % 60) + 60) % 60;     // 至日柱 60 序
		const jiaziUtc = zhiUtc - z + (z > 30 ? 60 : 0);                     // 至甲子=最近甲子(超30日置闰取后一甲子)
		if(Number.isFinite(dayUtc) && Number.isFinite(jiaziUtc) && dayUtc >= jiaziUtc){
			block = Math.floor((dayUtc - jiaziUtc) / 60) % 3;
			sinceJiazi = dayUtc - jiaziUtc;
		}
	}
	if(block === null){
		// 无种子退化:符头元(findYuan)近似定块,占位不崩(非精确,传本有别)。
		block = { 上元: 0, 中元: 1, 下元: 2 }[findYuan(dayGanZhi)] || 0;
	}
	block = ((block % 3) + 3) % 3;
	// [H-F] 一日一局:自「至甲子」起逐日推局(阳:上元首局起顺进;阴:逆退);元仍按六十日块显示。
	//   无种子时退化用日柱 60 序近似(60≢0 mod 9,跨甲子有断点,如实近似不掩盖)。
	if(dayJiaJu === 'yitian'){
		const d = sinceJiazi !== null ? sinceJiazi : ((getGanzhiIndex(dayGanZhi) % 60) + 60) % 60;
		const startJu = DAY_BLOCK_JU[yy][0];
		const ju = yang ? ((startJu - 1 + d) % 9) + 1 : (((startJu - 1 - d) % 9) + 9) % 9 + 1;
		return { sanYuan: DAY_BLOCK_YUAN[block], juShu: ju, yinYangDun: yang ? '阳遁' : '阴遁' };
	}
	return { sanYuan: DAY_BLOCK_YUAN[block], juShu: DAY_BLOCK_JU[yy][block], yinYangDun: yang ? '阳遁' : '阴遁' };
}

function calcShiJiaMeta(dayGanZhi, jieqi){
	const sanYuan = findYuan(dayGanZhi);
	const code = JIEQI_CODE[normalizeJieqi(jieqi)] || '一七四';
	const yuanIdx = sanYuan === '上元' ? 0 : (sanYuan === '中元' ? 1 : 2);
	const juShu = CNUMBER.indexOf(code[yuanIdx]) + 1;
	return {
		sanYuan,
		juShu: juShu > 0 ? juShu : 1,
		yinYangDun: isYangDunJieqi(jieqi) ? '阳遁' : '阴遁',
	};
}

function normalizeQijuMethod(method){
	return ['zhirun', 'chaibu', 'maoshan', 'wurun', 'shuzi'].indexOf(method) >= 0 ? method : 'chaibu';
}

export function isKinqimenMode(paiPanType){
	const type = normalizeNum(paiPanType, 3);
	// 年(0)/月(1)/日(2)/刻(4)家走本地全盘(各家局法 + 各柱锚点;刻家=十分局本地引擎);时(3)/综合(5)走后端(时家保后端=转盘字节护栏)。
	return type === 3 || type === 5;
}

function getKinqimenMode(paiPanType){
	const type = normalizeNum(paiPanType, 3);
	if(type === 0){
		return 'year';
	}
	if(type === 4){
		return 'minute';
	}
	if(type === 2){
		return 'golden';
	}
	if(type === 5){
		return 'overall';
	}
	return 'hour';
}

function getRawValue(obj, keys, def = ''){
	for(let i=0; i<keys.length; i++){
		if(obj && obj[keys[i]] !== undefined && obj[keys[i]] !== null){
			return obj[keys[i]];
		}
	}
	return def;
}

function normalizeGuaName(gua){
	return normalizeText(gua)
		.replace(/離/g, '离')
		.replace(/兌/g, '兑')
		.replace(/乾/g, '乾');
}

function normalizeGuaMap(mapObj){
	const out = {};
	Object.keys(mapObj || {}).forEach((key)=>{
		const gua = normalizeGuaName(key);
		out[gua] = normalizeText(mapObj[key]);
	});
	return out;
}

function parseKinqimenGanzhi(rawText, fallbackGanzhi){
	const text = normalizeText(rawText || '');
	const match = text.match(/([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])年([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])月([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])日([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])时(?:([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])分)?/);
	if(!match){
		return fallbackGanzhi || {};
	}
	return {
		...(fallbackGanzhi || {}),
		year: match[1] || '',
		month: match[2] || '',
		day: match[3] || '',
		time: match[4] || '',
		minute: match[5] || '',
	};
}

function normalizeZhiFuZhiShi(zfzs){
	const zhiFuStar = getRawValue(zfzs, ['值符星宮', '值符星宫'], []);
	const zhiShiDoor = getRawValue(zfzs, ['值使門宮', '值使门宫'], []);
	const zhiFuGan = getRawValue(zfzs, ['值符天干'], '');
	return {
		zhiFuGan,
		zhiFuStar: Array.isArray(zhiFuStar) ? zhiFuStar.map((item)=>normalizeText(item)) : [],
		zhiShiDoor: Array.isArray(zhiShiDoor) ? zhiShiDoor.map((item)=>normalizeText(item)) : [],
	};
}

function normalizeBackendSections(sections){
	if(!Array.isArray(sections)){
		return [];
	}
	return sections.map((section)=>({
		title: normalizeText(section && section.title ? section.title : ''),
		rows: Array.isArray(section && section.rows) ? section.rows.map((row)=>({
			label: normalizeText(row && row.label ? row.label : ''),
			value: normalizeText(row && row.value ? row.value : '—') || '—',
		})) : [],
	})).filter((section)=>section.title || section.rows.length);
}

function mergeKinqimenMaps(raw, fallbackPan, opts){
	const shiftPalace = normalizeShiftPalace(opts && opts.shiftPalace);
	const tianpanRaw = normalizeGuaMap(getRawValue(raw, ['天盤', '天盘'], {}));
	const dipanRaw = normalizeGuaMap(getRawValue(raw, ['地盤', '地盘'], {}));
	const menRaw = normalizeGuaMap(getRawValue(raw, ['門', '门'], {}));
	const starRaw = normalizeGuaMap(getRawValue(raw, ['星'], {}));
	const shenRaw = normalizeGuaMap(getRawValue(raw, ['神'], {}));
	const diPanBase = Object.keys(dipanRaw).length ? convertGuaMapToPos(dipanRaw) : (fallbackPan.diPan || {});
	const tianPanBase = Object.keys(tianpanRaw).length ? convertGuaMapToPos(tianpanRaw) : (fallbackPan.tianPan || {});
	const menBase = Object.keys(menRaw).length ? convertGuaMapToPos(menRaw) : (fallbackPan.renPan || {});
	const starBase = Object.keys(starRaw).length ? convertGuaMapToPos(starRaw) : {};
	const shenBase = Object.keys(shenRaw).length ? convertGuaMapToPos(shenRaw) : (fallbackPan.shenPan || {});
	const diPan = rotateOuterMapByShift(diPanBase, shiftPalace);
	const tianPan = rotateOuterMapByShift(tianPanBase, shiftPalace);
	const renPan = rotateOuterMapByShift(menBase, shiftPalace);
	let tianXing = rotateOuterMapByShift(Object.keys(starBase).length ? starBase : (fallbackPan.tianXing || {}), shiftPalace);
	// 后端盘星名归一:转盘(8星)天禽寄芮、禽/芮/禽芮合一,统一显「内」(天内);飞盘(9星)含中宫禽,保「禽」不动(用户:内对芮讹)。
	if((opts && opts.school) !== '飞盘'){
		const convStar = {};
		Object.keys(tianXing).forEach((k)=>{ convStar[k] = String(tianXing[k] == null ? '' : tianXing[k]).replace(/[芮禽]+/g, '内'); });
		tianXing = convStar;
	}
	const shenPan = rotateOuterMapByShift(shenBase, shiftPalace);
	return { diPan, tianPan, renPan, tianXing, shenPan };
}

export function normalizeKinqimenData(backendPan, fallbackPan, options, nongli){
	if(!backendPan || !fallbackPan){
		return fallbackPan;
	}
	const raw = backendPan.selected || backendPan.raw || {};
	const opts = options || {};
	const maps = mergeKinqimenMaps(raw, fallbackPan, opts);
	const zfzs = normalizeZhiFuZhiShi(getRawValue(raw, ['值符值使'], {}));
	const zhiFuPalaceRaw = zfzs.zhiFuStar[1] || '';
	const zhiShiPalaceRaw = zfzs.zhiShiDoor[1] || '';
	const shiftPalace = normalizeShiftPalace(opts.shiftPalace);
	const zhiFuPalace = zhiFuPalaceRaw ? rotateOuterPalaceNum(GUA_POS_MAP[zhiFuPalaceRaw] || 5, shiftPalace) : fallbackPan.zhiFuPalace;
	const zhiShiPalace = zhiShiPalaceRaw ? rotateOuterPalaceNum(GUA_POS_MAP[zhiShiPalaceRaw] || 5, shiftPalace) : fallbackPan.zhiShiPalace;
	// 飞盘天禽有本位(中宫),值符星=禽 时不替芮;转盘禽寄芮照旧。
	const zhiFuShort = (opts.school === '飞盘') ? (zfzs.zhiFuStar[0] || '') : (zfzs.zhiFuStar[0] || '').replace(/[芮禽]+/g, '内');
	const zhiShiShort = zfzs.zhiShiDoor[0] || '';
	const xunkong = getRawValue(raw, ['旬空'], fallbackPan.xunkong || {});
	const kongWang = getKongByMode(opts.kongMode, {
		日空: normalizeText(xunkong && xunkong.日空 ? xunkong.日空 : ''),
		时空: normalizeText((xunkong && (xunkong.時空 || xunkong.时空)) || ''),
	}) || fallbackPan.kongWang;
	const kongWangMeta = resolveKongWangPalaces(kongWang);
	const horse = getRawValue(raw, ['馬星', '马星'], {});
	// 驿马按 yimaMode(日马=日支三合 / 时马=时支三合)自算,与本地 calcDunJia 同源(resolveYiMa);
	//   后端 馬星.驛馬 是单一值、不随 yimaMode 变,时家须自算,左栏「日马/时马」切换才会改盘+右栏(用户报障)。
	const yiMaMeta = resolveYiMa(opts.yimaMode, fallbackPan.ganzhi || {});
	const yiMaZhi = yiMaMeta.yimaZhi || normalizeText((horse && (horse.驛馬 || horse.驿马)) || '');
	const yiMaPalace = yiMaMeta.palace || BRANCH_TO_POS[yiMaZhi] || (fallbackPan.yiMa ? fallbackPan.yiMa.palace : 0);
	const yiMa = {
		...(fallbackPan.yiMa || {}),
		mode: opts.yimaMode,
		yimaZhi: yiMaZhi || (fallbackPan.yiMa ? fallbackPan.yiMa.yimaZhi : ''),
		palace: yiMaPalace,
		text: yiMaMeta.text || (yiMaPalace ? `驿马：${yiMaZhi}（${PALACE_NAME[yiMaPalace]}${LUOSHU_NUM[PALACE_NAME[yiMaPalace]]}宫）` : (fallbackPan.yiMa ? fallbackPan.yiMa.text : '驿马：无')),
		raw: horse,
	};
	const specials = resolveSpecials(maps.tianPan);
	const menPo = resolveMenPo(maps.renPan);
	const cells = buildCells(maps.diPan, maps.tianPan, maps.renPan, maps.shenPan, maps.tianXing, zhiFuPalace, zhiShiPalace, {
		jiXingPalaces: specials.jiXingPalaces,
		ruMuPalaces: specials.ruMuPalaces,
		menPoPalaces: menPo.palaces,
		kongWangPalaces: kongWangMeta.palaces,
		yimaPalace: yiMaPalace,
		school: opts.school,
	});
	const qimenModeLabel = normalizeText(backendPan.modeLabel || '');
	const juText = normalizeText(getRawValue(raw, ['排局', '局'], fallbackPan.juText));
	let ganzhi = parseKinqimenGanzhi(getRawValue(raw, ['干支'], ''), fallbackPan.ganzhi);
	// v2.2.1: 本地 buildGanzhiForQimen 是 lateZi 语义的唯一可信来源(覆盖 4 case 矩阵)。
	// 后端 kinqimen 引擎对 (after23=1 + lateZi=0 + hour==23) 不返回 戊子,而是仍按 shifted day 的壬给出 庚子;
	// 这里以本地 fallback 的时柱为准,保证用户看到的 4 柱与设置一致。
	if(fallbackPan && fallbackPan.ganzhi && fallbackPan.ganzhi.time && ganzhi.time !== fallbackPan.ganzhi.time){
		ganzhi = { ...ganzhi, time: fallbackPan.ganzhi.time };
	}
	return {
		...fallbackPan,
		source: 'kinqimen',
		backend: backendPan,
		raw,
		allRaw: backendPan.allRaw || {},
		sections: normalizeBackendSections(backendPan.sections),
		qimenMode: backendPan.mode || getKinqimenMode(opts.paiPanType),
		qimenModeLabel,
		qimenCapabilities: backendPan.capabilities || null,
		juText: juText || fallbackPan.juText,
		jieqiText: normalizeText(getRawValue(raw, ['節氣', '节气'], fallbackPan.jieqiText)) || fallbackPan.jieqiText,
		yinYangDun: juText.indexOf('阴遁') >= 0 ? '阴遁' : (juText.indexOf('阳遁') >= 0 ? '阳遁' : fallbackPan.yinYangDun),
		sanYuan: juText.indexOf('上元') >= 0 || juText.endsWith('上') ? '上元' : (juText.indexOf('中元') >= 0 || juText.endsWith('中') ? '中元' : (juText.indexOf('下元') >= 0 || juText.endsWith('下') ? '下元' : fallbackPan.sanYuan)),
		juShu: (juText.match(/[一二三四五六七八九]/) || [fallbackPan.juShu || ''])[0],
		ganzhi,
		xunShou: normalizeText(getRawValue(raw, ['旬首'], fallbackPan.xunShou)),
		fuTou: normalizeText(getRawValue(raw, ['旬首'], fallbackPan.fuTou)),
		xunkong,
		kongWang,
		zhiFu: zhiFuShort ? (JIU_XING_NAME[zhiFuShort] || zhiFuShort) : fallbackPan.zhiFu,
		zhiShi: zhiShiShort ? (BA_MEN_NAME[zhiShiShort] || `${zhiShiShort}门`) : fallbackPan.zhiShi,
		zhiFuPalace,
		zhiShiPalace,
		diPan: maps.diPan,
		tianPan: maps.tianPan,
		renPan: maps.renPan,
		shenPan: maps.shenPan,
		tianGan: maps.tianPan,
		tianXing: maps.tianXing,
		diPanList: mapListByPos(maps.diPan),
		tianPanList: mapListByPos(maps.tianPan),
		renPanList: mapListByPos(maps.renPan),
		shenPanList: mapListByPos(maps.shenPan),
		jiXingPalaces: specials.jiXingPalaces,
		ruMuPalaces: specials.ruMuPalaces,
		liuYiJiXing: specials.liuYi,
		qiYiRuMu: specials.ruMu,
		menPo,
		kongWangDesc: kongWangMeta.list,
		kongWangPalaces: kongWangMeta.palaces,
		yiMa,
		cells,
		options: {
			...(fallbackPan.options || {}),
			qimenEngineLabel: '',
			qimenModeLabel,
			paiPanLabel: getOptionLabel(PAIPAN_OPTIONS, opts.paiPanType),
			qijuMethodLabel: normalizeText(backendPan.qijuMethod) === 'zhirun' ? '置闰' : (normalizeText(getRawValue(raw, ['排盤方式', '排盘方式'], '')) || (fallbackPan.options ? fallbackPan.options.qijuMethodLabel : '')),
		},
		lunarText: fallbackPan.lunarText || (nongli ? `${nongli.year || ''}年${nongli.leap ? '闰' : ''}${nongli.month || ''}${nongli.day || ''}` : ''),
	};
}

// [H-F] 刻家十分局:一时辰(2h)分十刻(12min/刻),初局=本时辰时家局(沿当前起局法链),
//   逐刻推移:阳遁顺进一局、阴遁逆退一局(第k刻=初局±(k-1),九局循环)。
//   分遁 keJiaFenDun:zihou(默认)=子后阳午后阴(时支子~巳阳/午~亥阴,与节气无关)/jieqi=沿时家节气分遁。
//   keZiZhengHuanShi=子正换时:开=时辰界取偶数整点(子时 00:00 起),关(默认)=奇数整点(子时 23:00 起)。
function calcKeJiaMeta(opts, ganzhi, jieqi, dateParts, context){
	// 初局基准=时家局(拆掉刻家键后按当前 qijuMethod 走时家链)
	const base = resolvePaiPanMeta({ ...opts, paiPanType: 3 }, ganzhi, jieqi, dateParts, context);
	const zhengShift = (opts && opts.keZiZhengHuanShi) ? 0 : 1;
	const hour = dateParts && Number.isFinite(dateParts.hour) ? dateParts.hour : 0;
	const minute = dateParts && Number.isFinite(dateParts.minute) ? dateParts.minute : 0;
	const sinceStart = ((hour + zhengShift) % 2) * 60 + minute;      // 时辰内分钟数(0..119)
	const keIndex = Math.min(9, Math.floor(sinceStart / 12));        // 第 1..10 刻(0 基)
	let yang;
	if((opts && opts.keJiaFenDun) === 'jieqi'){
		yang = `${base.yinYangDun || ''}`.indexOf('阳') >= 0;
	}else{
		const zhi = `${ganzhi.time || ''}`.charAt(1);
		yang = '子丑寅卯辰巳'.indexOf(zhi) >= 0;
	}
	const baseJu = base.juShu || 1;
	const ju = yang ? ((baseJu - 1 + keIndex) % 9) + 1 : (((baseJu - 1 - keIndex) % 9) + 9) % 9 + 1;
	// 刻柱干支:时柱锚法——本时辰第 1 刻即时柱本身,此后逐刻按六十甲子序进一位
	// (刻为时之细分,首刻同时柱,与「初局=时家局」同构;口径于帮助文档如实说明)。
	let keGanZhi = '';
	{
		const ti = getGanzhiIndex(ganzhi.time || '');
		if(ti >= 0){
			const idx = ((ti + keIndex) % 60 + 60) % 60;
			keGanZhi = GAN[idx % 10] + ZHI[idx % 12];
		}
	}
	return {
		sanYuan: base.sanYuan,
		juShu: ju,
		yinYangDun: yang ? '阳遁' : '阴遁',
		qmju: buildQmjuByMeta(yang ? '阳遁' : '阴遁', ju, base.sanYuan),
		dingjuJieqi: base.dingjuJieqi,
		keIndex: keIndex + 1,
		keGanZhi,
	};
}

function resolvePaiPanMeta(opts, ganzhi, jieqi, dateParts, context){
	const paiPanType = normalizeNum(opts && opts.paiPanType, 3);
	if(paiPanType === 0){
		return calcYearJiaMeta(dateParts.year, opts && opts.yearJiaJu);
	}
	if(paiPanType === 1){
		return calcYueJiaMeta(ganzhi, opts && opts.yueJiaQiJuType);
	}
	if(paiPanType === 2){
		return calcDayJiaMeta(dateParts, ganzhi.day, jieqi, context, opts && opts.dayJiaJu);
	}
	if(paiPanType === 4){
		return calcKeJiaMeta(opts, ganzhi, jieqi, dateParts, context);
	}
	const base = calcShiJiaMeta(ganzhi.day, jieqi);
	const seeds = context && context.jieqiYearSeeds ? context.jieqiYearSeeds : {};
	const m = normalizeQijuMethod(opts && opts.qijuMethod);
	let qmju;
	// 定局节气:拆补/茅山/阴盘=曆法节气;置闰/无闰=超神接气链上的节气(超神时可≠曆法,口径同
	// Python 侧 config.dingju_jieqi)。展示/快照用它,免「局对节气错」自相矛盾(2026-08-02 缺陷②修)。
	let dingjuJieqi = jieqi;
	if(m === 'zhirun'){
		qmju = qimenJuNameZhirun(dateParts, ganzhi.day, seeds, jieqi, opts && opts.after23NewDay, false, opts && opts.zhirunLeapDays);
		dingjuJieqi = qimenDingjuJieqi(dateParts, seeds, opts && opts.after23NewDay, false, opts && opts.zhirunLeapDays) || jieqi;
	}else if(m === 'wurun'){
		qmju = qimenJuNameWurun(dateParts, ganzhi.day, seeds, jieqi, opts && opts.after23NewDay, opts && opts.zhirunLeapDays);
		dingjuJieqi = qimenDingjuJieqi(dateParts, seeds, opts && opts.after23NewDay, true, opts && opts.zhirunLeapDays) || jieqi;
	}else if(m === 'maoshan'){
		qmju = qimenJuNameMaoshan(dateParts, jieqi, seeds, ganzhi.day);
	}else{
		qmju = qimenJuNameChaibu(jieqi, ganzhi.day);
	}
	const parsed = parseQmju(qmju);
	return {
		sanYuan: parsed.yuan,
		juShu: CNUMBER.indexOf(parsed.kook) + 1,
		yinYangDun: parsed.yy === '阴' ? '阴遁' : '阳遁',
		qmju,
		dingjuJieqi,
	};
}

function resolveSpecialZhiShi(zhiShiType, yinYangDun, jieqi){
	const type = normalizeNum(zhiShiType, 0);
	if(type === 1){
		return yinYangDun === '阳遁' ? '生' : '死';
	}
	if(type === 2){
		const jq = normalizeJieqi(jieqi);
		for(let i=0; i<ZHISHI_BY_JIEQI.length; i++){
			if(ZHISHI_BY_JIEQI[i].list.indexOf(jq) >= 0){
				return ZHISHI_BY_JIEQI[i].door;
			}
		}
	}
	return '死';
}

function parseQmju(qmju){
	const text = normalizeText(qmju);
	const yy = text.includes('阴遁') ? '阴' : '阳';
	const kook = (text.match(/[一二三四五六七八九]/) || ['一'])[0];
	const yuan = text.includes('上元') ? '上元' : (text.includes('中元') ? '中元' : '下元');
	return { text, yy, kook, yuan };
}

function buildGanzhiForQimen(nongli, dateParts, opts, context){
	const bazi = nongli && nongli.bazi && nongli.bazi.fourColumns ? nongli.bazi.fourColumns : null;
	const calcDateTime = resolveCalcDateTime(dateParts, nongli, opts, context);
	let day = normalizeGanZhi(
		(bazi && bazi.day && bazi.day.ganzi)
		|| (nongli ? nongli.dayGanZi : '甲子')
	);
	// 日柱换日已由 nongli 来源(后端 /nongli/time 或本地 buildLocalBaziResult)按 after23NewDay 完成,此处不可再次进位。
	// 用户语义(拍板,字面直觉版):
	//   after23NewDay=1「23点算第二天」→ hour==23 时 day 已上移到次日(壬寅);
	//   after23NewDay=0「24点算第二天」→ hour==23 时 day 守今(辛丑)。
	// v2.2.1 第二全局开关 lateZiHourUseNextDay:
	//   lateZi=1(默认):时柱永远按"次日日干"起子时(同 lunar.js Exact)
	//   lateZi=0:时柱跟随日柱所在 cdate 的日干起子时(== 跟日柱一致)
	// 仅 hour==23 时影响时柱;其它 22 小时一律 NO-OP。
	const preciseTime = normalizeGanZhi(
		(bazi && bazi.time && bazi.time.ganzi)
		|| (nongli ? nongli.time : '')
	);
	const computedTime = getHourGanZhi(day, calcDateTime.hour);
	const isLateZi = calcDateTime.hour === 23;
	const dayShiftedByLateZi = isLateZi && !!(opts && opts.after23NewDay); // after23NewDay=1 → 进位
	const lateZiUseNextDay = opts && opts.lateZiHourUseNextDay !== undefined
		? (opts.lateZiHourUseNextDay !== 0 && opts.lateZiHourUseNextDay !== '0' && opts.lateZiHourUseNextDay !== false ? 1 : 0)
		: 1;
	const timeAlgIsTrueSolar = normalizeTimeAlg(opts && opts.timeAlg) === 0;
	let time;
	if(dayShiftedByLateZi){
		// after23=1 + hour==23: day 已 shift 到次日(壬寅)。
		// lateZi=1: 时柱用次日日干起子时 → getHourGanZhi(壬寅, 23) = 庚子
		// lateZi=0: 时柱用今日(=prevDay)日干起子时 → getHourGanZhi(辛丑, 23) = 戊子
		if(lateZiUseNextDay){
			time = computedTime || preciseTime;
		} else {
			const todayDay = prevGanZhi(day);
			time = getHourGanZhi(todayDay, calcDateTime.hour) || computedTime || preciseTime;
		}
	} else if(isLateZi){
		// after23=0 + hour==23: day 守今(辛丑)
		if(lateZiUseNextDay){
			// lateZi=1 默认:时柱按次日干起 → preciseTime = lunar.js Exact 现行结果(庚子)
			time = preciseTime || computedTime;
		} else {
			// lateZi=0:时柱跟日柱一致 → computedTime = getHourGanZhi(today_day, 23) = 戊子(核心新 case)
			time = computedTime || preciseTime;
		}
	} else if(timeAlgIsTrueSolar){
		time = computedTime || preciseTime;
	} else {
		time = preciseTime || computedTime;
	}
	return {
		year: normalizeGanZhi(
			(bazi && bazi.year && bazi.year.ganzi)
			|| (nongli ? (nongli.yearJieqi || nongli.year) : '')
		),
		month: normalizeGanZhi(
			(bazi && bazi.month && bazi.month.ganzi)
			|| (nongli ? nongli.monthGanZi : '')
		),
		day,
		time,
	};
}

function daykongShikong(dayGanZhi, hourGanZhi){
	const dk = getXunHead(dayGanZhi);
	const sk = getXunHead(hourGanZhi);
	return {
		日空: GUXU[dk] || '戌亥',
		时空: GUXU[sk] || '戌亥',
	};
}

function zhifuPai(qmju){
	const meta = parseQmju(qmju);
	const table = {
		阳: {
			一: '九八七一二三四五六',
			二: '一九八二三四五六七',
			三: '二一九三四五六七八',
			四: '三二一四五六七八九',
			五: '四三二五六七八九一',
			六: '五四三六七八九一二',
			七: '六五四七八九一二三',
			八: '七六五八九一二三四',
			九: '八七六九一二三四五',
		},
		阴: {
			九: '一二三九八七六五四',
			八: '九一二八七六五四三',
			七: '八九一七六五四三二',
			六: '七八九六五四三二一',
			五: '六七八五四三二一九',
			四: '五六七四三二一九八',
			三: '四五六三二一九八七',
			二: '三四五二一九八七六',
			一: '二三四一九八七六五',
		},
	};
	const pai = table[meta.yy][meta.kook];
	const yinlist = newListR(CNUMBER, meta.kook).slice(0, 6).map((x)=>x + pai);
	const yanglist = newList(CNUMBER, meta.kook).slice(0, 6).map((x)=>x + pai);
	return meta.yy === '阴' ? zipToMap(XUN_HEADS, yinlist) : zipToMap(XUN_HEADS, yanglist);
}

function zhishiPai(qmju){
	const meta = parseQmju(qmju);
	const newKook = newList(CNUMBER, meta.kook);
	const newRKook = newListR(CNUMBER, meta.kook);
	const yanglist = `${newKook.join('')}${newKook.join('')}${newKook.join('')}`;
	const yinlist = `${newRKook.join('')}${newRKook.join('')}${newRKook.join('')}`;
	const yinlist1 = newRKook.slice(0, 6).map((i)=>`${i}${yinlist.slice(yinlist.indexOf(i) + 1, yinlist.indexOf(i) + 12)}`);
	const yanglist1 = newKook.slice(0, 6).map((i)=>`${i}${yanglist.slice(yanglist.indexOf(i) + 1, yanglist.indexOf(i) + 12)}`);
	return meta.yy === '阴' ? zipToMap(XUN_HEADS, yinlist1) : zipToMap(XUN_HEADS, yanglist1);
}

function zhifuNZhishi(ganzhi, qmju, ext){
	const gongsCode = zipToMap(CNUMBER, EIGHT_GUA);
	const hgan = GAN.indexOf(ganzhi.time.substring(0, 1));
	const chour = getXunHead(ganzhi.time);
	const eg = '休死伤杜中开惊生景'.split('');
	const zspai = zhishiPai(qmju);
	const zfpai = zhifuPai(qmju);
	const zspaiKeys = Object.keys(zspai);
	const zspaiValues = Object.values(zspai);
	const zfKeys = Object.keys(zfpai);
	const zfValues = Object.values(zfpai);

	const a = zspaiValues.map((i)=>zipToMap(CNUMBER, eg)[i.substring(0, 1)]);
	const b = zfValues.map((i)=>zipToMap(CNUMBER, JIU_XING)[i.substring(0, 1)]);
	const c = zfValues.map((i)=>gongsCode[i.substring(hgan, hgan + 1)]);
	const d = zspaiValues.map((i)=>gongsCode[i.substring(hgan, hgan + 1)]);

	const star = zipToMap(zfKeys, b)[chour];
	const starGong = zipToMap(zfKeys, c)[chour];
	let door = zipToMap(zspaiKeys, a)[chour];
	// 仅“值符星=禽”时按天禽值符规则处理；值符落中宫并不等于天禽值符。
	const isTianQinAsZhiFu = star === '禽';
	if(isTianQinAsZhiFu){
		door = resolveSpecialZhiShi(ext && ext.zhiShiType, ext && ext.yinYangDun, ext && ext.jieqi);
	}else if(door === '中'){
		door = '死';
	}
	return {
		值符天干: [chour, JJ[chour]],
		值符星宫: [star, starGong],
		值使门宫: [door, zipToMap(zspaiKeys, d)[chour]],
	};
}

function panEarth(qmju){
	const meta = parseQmju(qmju);
	const palaces = newList(CNUMBER, meta.kook).map((x)=>zipToMap(CNUMBER, EIGHT_GUA)[x]);
	const vals = meta.yy === '阳' ? '戊己庚辛壬癸丁丙乙'.split('') : '戊乙丙丁癸壬辛庚己'.split('');
	return zipToMap(palaces, vals);
}

function panGod(ganzhi, qmju, ext){
	const zfzs = zhifuNZhishi(ganzhi, qmju, ext);
	const meta = parseQmju(qmju);
	const startingGong = zfzs.值符星宫[1];
	const rotate = meta.yy === '阳' ? CLOCKWISE_EIGHTGUA : [...CLOCKWISE_EIGHTGUA].reverse();
	const gongReorder = startingGong === '中' ? newList(rotate, jiGongOf(ext, meta.yy)) : newList(rotate, startingGong);
	const vals = (meta.yy === '阳' ? '符蛇阴合勾雀地天' : '符蛇阴合虎玄地天').split('');
	const out = zipToMap(gongReorder, vals);
	// [H-B] 八神名按预设分派(ext.godsPreset;缺省=历史默认恒虎玄)
	Object.keys(out).forEach((k)=>{
		out[k] = applyGodsPreset(out[k], ext && ext.godsPreset);
	});
	return out;
}

function panDoor(ganzhi, qmju, ext){
	const zfzs = zhifuNZhishi(ganzhi, qmju, ext);
	const meta = parseQmju(qmju);
	const startingDoor = zfzs.值使门宫[0];
	const startingGong = zfzs.值使门宫[1];
	const rotate = meta.yy === '阳' ? CLOCKWISE_EIGHTGUA : [...CLOCKWISE_EIGHTGUA].reverse();
	const gongReorder = startingGong === '中' ? newList(rotate, jiGongOf(ext, meta.yy)) : newList(rotate, startingGong);
	const yydoor = meta.yy === '阳' ? newList(DOOR_R, startingDoor) : newList([...DOOR_R].reverse(), startingDoor);
	return zipToMap(gongReorder, yydoor);
}

function panStar(ganzhi, qmju, ext){
	const zfzs = zhifuNZhishi(ganzhi, qmju, ext);
	const meta = parseQmju(qmju);
	const startingStar = zfzs.值符星宫[0].replace(/芮/g, '禽');
	const startingGong = zfzs.值符星宫[1];
	const rotate = meta.yy === '阳' ? CLOCKWISE_EIGHTGUA : [...CLOCKWISE_EIGHTGUA].reverse();
	const stars = meta.yy === '阳' ? newList(STAR_R, startingStar) : newList([...STAR_R].reverse(), startingStar);
	const gongReorder = startingGong === '中' ? newList(rotate, jiGongOf(ext, meta.yy)) : newList(rotate, startingGong);
	const out = zipToMap(gongReorder, stars);
	Object.keys(out).forEach((k)=>{
		out[k] = out[k].replace(/[芮禽]+/g, '内');   // 转盘(8星)天禽随中显「内」(天内);飞盘9星含中宫照显「禽」(用户:内对芮讹)
	});
	return out;
}

function panSky(ganzhi, qmju, ext){
	const meta = parseQmju(qmju);
	const rotate = meta.yy === '阳' ? CLOCKWISE_EIGHTGUA : [...CLOCKWISE_EIGHTGUA].reverse();
	const earth = panEarth(qmju);
	const earthR = invertMap(earth);
	const zfzs = zhifuNZhishi(ganzhi, qmju, ext);
	const fuHead = JJ[getXunHead(ganzhi.time)] || '戊';
	const ganHead = zfzs.值符天干[1];
	const starGong = zfzs.值符星宫[1];
	const earthOnRing = rotate.map((g)=>earth[g]);
	const jiGong = jiGongOf(ext, meta.yy);
	if(starGong === '中'){
		const gongReorder = newList(rotate, jiGong);
		let ganReorder;
		if(panGod(ganzhi, qmju, ext)[jiGong] !== '符'){
			ganReorder = newList(earthOnRing, earth[jiGong]);
		}else if(earth[jiGong] === ganHead){
			ganReorder = newList(earthOnRing, earthOnRing[earthOnRing.length - 1]);
		}else{
			try{
				ganReorder = newList(earthOnRing, ganHead);
			}catch(e){
				ganReorder = newList(earthOnRing, earth[jiGong]);
			}
		}
		const out = zipToMap(gongReorder, ganReorder);
		out.中 = earth.中;
		return out;
	}
	const timeGan = getGanzhiGan(ganzhi.time);
	const normalizeTianpanGong = (gong)=>gong === '中' ? jiGong : gong;
	const sourceGong = normalizeTianpanGong(earthR[fuHead]);
	const targetGong = normalizeTianpanGong(earthR[timeGan]);
	const safeSourceGong = rotate.indexOf(sourceGong) >= 0 ? sourceGong : rotate[0];
	const safeTargetGong = rotate.indexOf(targetGong) >= 0 ? targetGong : safeSourceGong;
	const ganReorder = newList(rotate, safeSourceGong).map((g)=>earth[g]);
	const gongReorder = newList(rotate, safeTargetGong);
	const out = zipToMap(gongReorder, ganReorder);
	out.中 = earth.中;
	return out;
}

// WP-A 飞盘排盘(资料 Step6-8 / 参考引擎 paipanCore 飞盘分支,已对 golden 逐宫核对)。
// 一次算齐 天/门/星/神 四盘(共用 Hv/P/Pu 锚点),输出洛书宫→卦名 map,下游 convertGuaMapToPos 零改。
// 中宫照常飞、九神含中宫、不做 禽→芮 / 勾→虎 / 雀→玄 替换(那些是转盘专有)。
// 九门归宫(含中5「中门」):飞盘八门其实是九门整体飞九宫——值符落中5(天禽值符)时,值使门即「中门」从中5起数,
//   非中宫值符时中门作为第9门随飞填满某宫(对齐参考实现:6-22中门@震3、02-04中门@坎1、时乙酉中门@艮8)。
const FEI_GATE_HOME = { 1: '休', 8: '生', 3: '伤', 4: '杜', 5: '中', 9: '景', 2: '死', 7: '惊', 6: '开' };
// 九神飞布:阳遁 值符螣蛇太阴六合勾陈太常朱雀九地九天;阴遁 值符螣蛇太阴六合白虎太常玄武九地九天(5白虎/7玄武)。
const FEI_GODS_YANG = '符蛇阴合勾常雀地天'.split('');
const FEI_GODS_YIN = '符蛇阴合虎常玄地天'.split('');
const lpFei = (n)=>((n - 1) % 9 + 9) % 9 + 1;

// [H-D] fopts 飞盘细项(全缺省=历史行为零回归):
//   feiXingShun/feiMenShun/feiShenShun=该层阴阳遁皆顺飞(只改飞布方向,值符/值使定位不动);
//   feiMenZhongCan=false 时门层按「八门跳中5」传派布(中宫永不布门,数飞跳中);
//   feiMenZhongShow=true 且中门不参与时,中宫标「中」字样(纯显示)。
export function panFeipan(ganzhi, qmju, fopts){
	const fo = fopts || {};
	const meta = parseQmju(qmju);
	const isY = meta.yy === '阳';
	const earthGua = panEarth(qmju);                                  // 卦→干
	const earthGong = {};
	for(let g = 1; g <= 9; g++){ earthGong[g] = earthGua[EIGHT_GUA[g - 1]]; }   // 洛书宫→干
	const xunHead = getXunHead(ganzhi.time);
	const dunYi = JJ[xunHead] || '戊';
	let Hv = 5;
	for(let g = 1; g <= 9; g++){ if(earthGong[g] === dunYi){ Hv = g; break; } } // 值符宫=旬首遁仪所在宫
	const timeGan = `${ganzhi.time || ''}`.substring(0, 1);
	let P = Hv;                                                       // 时干宫(甲→值符原地)
	if(timeGan !== '甲'){ for(let g = 1; g <= 9; g++){ if(earthGong[g] === timeGan){ P = g; break; } } }
	// 时干序(=时柱在旬内位次+1,旬首恒甲)。🔴 空时柱时 indexOf('')=-1 → xord=0,
	// 值使门整盘静默偏一宫;非法输入按旬首(xord=1)兜底,不再产出错位盘。
	const xord = Math.max(1, GAN.indexOf(timeGan) + 1);
	const step = isY ? 1 : -1;
	const stepXing = (isY || fo.feiXingShun) ? 1 : -1;
	const stepMen = (isY || fo.feiMenShun) ? 1 : -1;
	const stepShen = (isY || fo.feiShenShun) ? 1 : -1;
	// 值使门落宫:从值符宫(旬首遁仪宫,含中5)顺(阳)/逆(阴)数至时柱(参考实现门入中宫,Pu 可为中5)。
	const Pu = lpFei(Hv + step * (xord - 1));                         // 中宫值符(Hv=5)时值使=中门,亦从中5起数(6-22→震3、02-04→坎1 已对参考实现)
	const starG = {}, skyG = {}, gateG = {}, godG = {};
	// 九星:值符星(JIU_XING[Hv-1])落时干宫P,蓬芮冲辅禽心柱任英按号顺(阳)/逆(阴)飞九宫(含中5)。
	for(let n = 1; n <= 9; n++){ starG[lpFei(P + stepXing * (n - Hv))] = JIU_XING[n - 1]; }
	// 天盘(六仪三奇):地盘整体随值符平移(值符遁仪→时干宫,平移量 P-Hv),非随星逆飞——
	//   阴遁星逆飞但天盘是整体平移,故各宫天盘干须单独按平移算(对齐参考实现:坎1=庚/巽4=乙…)。
	const dPan = ((P - Hv) % 9 + 9) % 9;
	for(let q = 1; q <= 9; q++){ skyG[lpFei(q + dPan)] = earthGong[q]; }
	// 九门:值使门(FEI_GATE_HOME[Hv],中宫值符时=中门)落Pu,休死伤杜中开惊生景九门按九宫顺(阳)/逆(阴)整体飞——
	//   对齐参考实现(门入中宫:中门是第9门随飞,落中5者中宫得门),非书本「八门跳中5」传本(以本引擎为准)。
	if(fo.feiMenZhongCan === false){
		// [H-D] 跳中传派:八门(无中门)全程 8 宫环(洛书序跳中5),值使定位数宫亦跳中;值符宫=中5 时值使取死门、自死门本位起数。
		const RING8 = [1, 2, 3, 4, 6, 7, 8, 9];
		const DOORS8 = ['休', '死', '伤', '杜', '开', '惊', '生', '景'];   // 洛书本位序(1休2死3伤4杜6开7惊8生9景)
		let vDoor = FEI_GATE_HOME[`${Hv}`] || '死';
		if(vDoor === '中'){ vDoor = '死'; }
		const vHome = RING8[DOORS8.indexOf(vDoor)];
		const hv8 = Hv === 5 ? vHome : Hv;
		const pos8 = (g)=>RING8.indexOf(g);
		const pu8 = RING8[(((pos8(hv8) + step * (xord - 1)) % 8) + 8) % 8];
		const di = DOORS8.indexOf(vDoor);
		for(let k = 0; k < 8; k++){ gateG[RING8[(((pos8(pu8) + stepMen * k) % 8) + 8) % 8]] = DOORS8[(di + k) % 8]; }
		if(fo.feiMenZhongShow){ gateG[5] = '中'; }
	}else{
		Object.keys(FEI_GATE_HOME).forEach((hk)=>{ const h = Number(hk); const np = lpFei(Pu + stepMen * (h - Hv)); gateG[np] = FEI_GATE_HOME[hk]; });
	}
	// 九神:值符落时干宫P(同值符星),阳遁勾常雀顺、阴遁白玄逆,飞九宫(含中5)。
	(isY ? FEI_GODS_YANG : FEI_GODS_YIN).forEach((god, i)=>{ const np = lpFei(P + i * stepShen); godG[np] = god; });
	const toGua = (gongMap)=>{ const out = {}; for(let g = 1; g <= 9; g++){ out[EIGHT_GUA[g - 1]] = gongMap[g] || ''; } return out; };
	return {
		tianpanGua: toGua(skyG),
		menGua: toGua(gateG),
		starGua: toGua(starG),
		shenGua: toGua(godG),
		zfzs: {
			值符天干: [xunHead, dunYi],
			值符星宫: [JIU_XING[Hv - 1], EIGHT_GUA[lpFei(P) - 1]],
			值使门宫: (function(){
				if(fo.feiMenZhongCan === false){
					let vd = FEI_GATE_HOME[`${Hv}`] || '死';
					if(vd === '中'){ vd = '死'; }
					const gong = Object.keys(gateG).find((g)=>gateG[g] === vd);
					return [vd, EIGHT_GUA[(Number(gong) || 2) - 1]];
				}
				return [FEI_GATE_HOME[`${Hv}`] || '死', EIGHT_GUA[lpFei(Pu) - 1]];
			})(),
		},
	};
}

function convertGuaMapToPos(mapObj){
	const out = {};
	Object.keys(POS_GUA_MAP).forEach((k)=>{
		out[k] = '';
	});
	Object.keys(mapObj || {}).forEach((gua)=>{
		const pos = GUA_POS_MAP[gua];
		if(pos){
			out[pos] = mapObj[gua] || '';
		}
	});
	return out;
}

function getKongByMode(mode, dayShiKong){
	return mode === 'time' ? (dayShiKong.时空 || '') : (dayShiKong.日空 || '');
}

function resolveKongWangPalaces(kongWang){
	const list = [];
	const palaces = [];
	// [H-E] 逐字遍历(两字串=历史行为字节同;kongMarkBoth 并集串为四字,全标)
	String(kongWang || '').split('').forEach((zhi)=>{
		const pos = BRANCH_TO_POS[zhi];
		if(pos && palaces.indexOf(pos) < 0){
			palaces.push(pos);
			list.push(`${PALACE_NAME[pos]}${LUOSHU_NUM[PALACE_NAME[pos]]}宫空亡`);
		}
	});
	return { list, palaces };
}

function getYiMaZhi(sourceZhi){
	if('申子辰'.indexOf(sourceZhi) >= 0){
		return '寅';
	}
	if('寅午戌'.indexOf(sourceZhi) >= 0){
		return '申';
	}
	if('巳酉丑'.indexOf(sourceZhi) >= 0){
		return '亥';
	}
	if('亥卯未'.indexOf(sourceZhi) >= 0){
		return '巳';
	}
	return '';
}

function resolveYiMa(mode, ganzhi){
	const source = mode === 'time' ? (ganzhi.time || '') : (ganzhi.day || '');
	const sourceZhi = source.substring(1, 2);
	const yimaZhi = getYiMaZhi(sourceZhi);
	const palace = BRANCH_TO_POS[yimaZhi] || 0;
	return {
		mode,
		source,
		sourceZhi,
		yimaZhi,
		palace,
		text: palace ? `${mode === 'time' ? '时马' : '日马'}：${yimaZhi}（${PALACE_NAME[palace]}${LUOSHU_NUM[PALACE_NAME[palace]]}宫）` : `${mode === 'time' ? '时马' : '日马'}：无`,
	};
}

function resolveSpecials(tianPan){
	const liuYi = [];
	const ruMu = [];
	const jiXingSet = new Set();
	const ruMuSet = new Set();
	for(let i=1; i<=9; i++){
		const gan = tianPan[i] || '';
		const jiRule = JI_XING_RULE[i] || '';
		const ruRule = RU_MU_RULE[i] || '';
		if(gan && jiRule && jiRule.indexOf(gan) >= 0){
			jiXingSet.add(i);
			liuYi.push(`${gan}击刑（${PALACE_NAME[i]}${LUOSHU_NUM[PALACE_NAME[i]]}宫）`);
		}
		if(gan && ruRule && ruRule.indexOf(gan) >= 0){
			ruMuSet.add(i);
			ruMu.push(`${gan}入墓（${PALACE_NAME[i]}${LUOSHU_NUM[PALACE_NAME[i]]}宫）`);
		}
	}
	return {
		liuYi,
		ruMu,
		jiXingPalaces: [...jiXingSet],
		ruMuPalaces: [...ruMuSet],
	};
}

function resolveMenPo(men){
	const list = [];
	const palaces = [];
	Object.keys(MEN_PO_RULE).forEach((k)=>{
		const i = parseInt(k, 10);
		const door = men[i] || '';
		const head = door.substring(0, 1);
		if(head && MEN_PO_RULE[i].indexOf(head) >= 0){
			palaces.push(i);
			list.push(`${head}门迫（${PALACE_NAME[i]}${LUOSHU_NUM[PALACE_NAME[i]]}宫）`);
		}
	});
	return { list, palaces };
}

function mapListByPos(mapObj){
	const out = [];
	for(let i=1; i<=9; i++){
		out.push(mapObj[i] || '');
	}
	return out;
}

function rotateOuterMapByShift(mapObj, shiftPalace){
	const step = normalizeShiftPalace(shiftPalace);
	const out = {};
	for(let i=1; i<=9; i++){
		out[i] = mapObj && mapObj[i] ? mapObj[i] : '';
	}
	if(step === 0){
		return out;
	}
	for(let i=0; i<OUTER_RING_CLOCKWISE.length; i++){
		const srcPalace = OUTER_RING_CLOCKWISE[i];
		const destPalace = OUTER_RING_CLOCKWISE[(i + step) % OUTER_RING_CLOCKWISE.length];
		out[destPalace] = mapObj && mapObj[srcPalace] ? mapObj[srcPalace] : '';
	}
	out[5] = mapObj && mapObj[5] ? mapObj[5] : '';
	return out;
}

function rotateOuterPalaceNum(palaceNum, shiftPalace){
	const step = normalizeShiftPalace(shiftPalace);
	if(step === 0 || palaceNum === 5){
		return palaceNum;
	}
	const idx = OUTER_RING_CLOCKWISE.indexOf(palaceNum);
	if(idx < 0){
		return palaceNum;
	}
	return OUTER_RING_CLOCKWISE[(idx + step) % OUTER_RING_CLOCKWISE.length];
}

function buildCells(diPan, tianPan, men, shen, star, zhiFuPalace, zhiShiPalace, status){
	const jiXingSet = new Set(status && status.jiXingPalaces ? status.jiXingPalaces : []);
	const ruMuSet = new Set(status && status.ruMuPalaces ? status.ruMuPalaces : []);
	const menPoSet = new Set(status && status.menPoPalaces ? status.menPoPalaces : []);
	const kongSet = new Set(status && status.kongWangPalaces ? status.kongWangPalaces : []);
	const yimaPalace = status && status.yimaPalace ? status.yimaPalace : 0;

	return PALACE_GRID.map((palaceNum)=>({
		palaceNum,
		palaceName: PALACE_NAME[palaceNum] || `${palaceNum}`,
		diGan: diPan[palaceNum] || '',
		tianXing: star[palaceNum] || '',
		door: men[palaceNum] || '',
		god: (status && (status.school === '飞盘' || status.school === '混合')) ? String(shen[palaceNum] || '') : applyGodsPreset(String(shen[palaceNum] || ''), status && status.godsPreset),
		tianGan: tianPan[palaceNum] || '',
		isCenter: palaceNum === 5,
		isFeipan: !!(status && (status.school === '飞盘' || status.school === '混合')),   // 混合:门神飞泊可入中5,中宫按飞盘渲染(星仍转盘寄坤2)
		isZhiFu: palaceNum === zhiFuPalace,
		isZhiShi: palaceNum === zhiShiPalace,
		hasJiXing: jiXingSet.has(palaceNum),
		hasRuMu: ruMuSet.has(palaceNum),
		hasMenPo: menPoSet.has(palaceNum),
		hasKongWang: kongSet.has(palaceNum),
		isYiMa: palaceNum === yimaPalace,
		anGan: (status && status.anGanByNum && status.anGanByNum[palaceNum]) || '',   // [H-B] 暗干(off=空)
		anZhi: (status && status.anZhiByNum && status.anZhiByNum[palaceNum]) || '',   // [H-B] 暗支(随开关)
	}));
}

function parseDayFromTime(timeStr){
	if(!timeStr){
		return '';
	}
	const t = `${timeStr}`.trim();
	if(t.length < 10){
		return '';
	}
	return t.substring(0, 10).replace(/-/g, '');
}

function keyToUtcDay(key){
	if(!key || key.length !== 8){
		return NaN;
	}
	const y = normalizeNum(key.substring(0, 4), 0);
	const m = normalizeNum(key.substring(4, 6), 1);
	const d = normalizeNum(key.substring(6, 8), 1);
	return Math.floor(Date.UTC(y, m - 1, d) / 86400000);
}

function utcDayToKey(daynum){
	const dt = new Date(daynum * 86400000);
	const y = dt.getUTCFullYear();
	const m = `${dt.getUTCMonth() + 1}`.padStart(2, '0');
	const d = `${dt.getUTCDate()}`.padStart(2, '0');
	return `${y}${m}${d}`;
}

export function buildJieqiYearSeed(result){
	const seed = {};
	const list = result && result.jieqi24 ? result.jieqi24 : [];
	list.forEach((item)=>{
		const jq = normalizeJieqi(item && item.jieqi ? item.jieqi : '');
		if(!jq){
			return;
		}
		const time = item && item.time ? `${item.time}` : '';
		const dayGanzhi = normalizeGanZhi(item && item.bazi && item.bazi.fourColumns && item.bazi.fourColumns.day ? item.bazi.fourColumns.day.ganzi : '');
		seed[jq] = {
			term: jq,
			time,
			dateKey: parseDayFromTime(time),
			dayGanzhi,
		};
	});
	return seed;
}

function nextJieqi(name){
	const idx = JIEQI_NAME.indexOf(name);
	if(idx < 0){
		return '冬至';
	}
	return JIEQI_NAME[(idx + 1) % JIEQI_NAME.length];
}

function buildYinyangdunMap(year, yearSeeds, noLeap, leapThresholdDays){
	const prev = yearSeeds ? yearSeeds[year - 1] : null;
	const curr = yearSeeds ? yearSeeds[year] : null;
	if(!prev || !curr || !prev.大雪 || !curr.芒种 || !curr.大雪){
		return null;
	}
	const leapDays = normalizeNum(leapThresholdDays, 9);   // 置闰超神天数阈值(可配,默认9=现行口径,字节不漂)
	// WP-C 无闰法:同超神接气但永不置闰。noLeap/非默认 leapDays 进缓存键 → 默认(置闰·9日)路径键不变、字节不漂。
	// 至点种子直捡(2026-08-02 二次修):lunar-javascript 年表键「冬至」属上年12月(本年12月冬至
	// 在表里键作 'DONG_ZHI',种子未采)——不赌表语义,按「目标公历年+月份窗」从三年种子里直捡:
	// 冬至=目标年12月、夏至=目标年6月。捡不到(域外等)时各判定点回退旧法。
	const pickSolstice = (term, targetYear, monthWant)=>{
		for(let k=-1; k<=1; k++){
			const ys = yearSeeds ? yearSeeds[targetYear + k] : null;
			const s = ys && ys[term];
			if(s && s.dateKey && `${s.dateKey}`.slice(0, 4) === `${targetYear}` && parseInt(`${s.dateKey}`.slice(4, 6), 10) === monthWant){
				return s;
			}
		}
		return null;
	};
	const dzPrevSeed = pickSolstice('冬至', year - 1, 12);   // 上年12月冬至(管链首·上年大雪段)
	const xzSeed = pickSolstice('夏至', year, 6);            // 本年6月夏至(管芒种段)
	const dzCurrSeed = pickSolstice('冬至', year, 12);       // 本年12月冬至(管本年大雪段)
	const seedSig = [
		year,
		prev.大雪.dateKey || '',
		prev.大雪.dayGanzhi || '',
		curr.芒种.dateKey || '',
		curr.芒种.dayGanzhi || '',
		curr.大雪.dateKey || '',
		curr.大雪.dayGanzhi || '',
		/* 至点锚种子(2026-08-02 二次修)进缓存键:置闰判定改锚二至后,键必须随至点种子变 */
		(dzPrevSeed && dzPrevSeed.dateKey) || '',
		(dzPrevSeed && dzPrevSeed.dayGanzhi) || '',
		(xzSeed && xzSeed.dateKey) || '',
		(xzSeed && xzSeed.dayGanzhi) || '',
		(dzCurrSeed && dzCurrSeed.dateKey) || '',
		(dzCurrSeed && dzCurrSeed.dayGanzhi) || '',
	].join('|') + (noLeap ? '|noleap' : '') + (leapDays !== 9 ? `|leap${leapDays}` : '');
	if(YINYANGDUN_CACHE.has(seedSig)){
		return YINYANGDUN_CACHE.get(seedSig);
	}
	const ret = {};

	const daxueStart = prev.大雪.dateKey;
	const daxueRizhu = normalizeGanZhi(prev.大雪.dayGanzhi || '甲子');
	let daxueIndex = getGanzhiIndex(daxueRizhu);
	let futouIndex = Math.floor(daxueIndex / 15) * 15;
	let tday = keyToUtcDay(daxueStart);
	let rizhuIndex = daxueIndex;

	for(let i=daxueIndex; i<futouIndex + 15; i++){
		ret[utcDayToKey(tday)] = `大雪${JIAZI[rizhuIndex]}`;
		tday += 1;
		rizhuIndex = (rizhuIndex + 1) % 60;
	}

	// 至锚置闰(2026-08-02 二次修,对齐 kinqimen fork jieqi.py zhirun_jieqi 的「至点锚」框架):
	// dgap = 二至日 − 其前最近上元符头(严格在前;即至日日柱序%15,0 作 15);dgap≥阈值 → 该至前
	// 插入闰(重复大雪/芒种三元)。链上表现为:至的上元块起 = F*(至) + (闰?15:0),默认步进若未到位
	// 则补一块重复节气。旧法在上年大雪/芒种/本年大雪三点各自量距(且比较符 >=/>/> 不一),与至点
	// 锚在节气间距≠15天的年份差±1天:1996芒种类临界年漏闰(阴七/应阴八·客诉案),1950/1956 类
	// 临界年与 Python 真值整段错一节气块(全域平价扫描 720+ 差异)。三处判定必须永远同锚同阈。
	const solsticeAnchorStart = (seed)=>{
		if(!seed || !seed.dateKey || !seed.dayGanzhi){ return null; }
		const day = keyToUtcDay(seed.dateKey);
		if(!Number.isFinite(day)){ return null; }
		const off = getGanzhiIndex(normalizeGanZhi(seed.dayGanzhi)) % 15;
		const dgap = off === 0 ? 15 : off;
		return day - dgap + ((!noLeap && dgap >= leapDays) ? 15 : 0);
	};

	let jieqiCur = '冬至';
	const dzPrevStart = solsticeAnchorStart(dzPrevSeed);
	if(dzPrevStart !== null){
		if(!noLeap && tday < dzPrevStart){ jieqiCur = '大雪'; }
	}else if(!noLeap && daxueIndex - futouIndex >= leapDays){   // 冬至种子缺失时的旧法兜底
		jieqiCur = '大雪';
	}

	let jieqiDays = 0;
	let mangzhongDay = null;
	for(let i=0; i<300; i++){
		ret[utcDayToKey(tday)] = `${jieqiCur}${JIAZI[rizhuIndex]}`;
		tday += 1;
		rizhuIndex = (rizhuIndex + 1) % 60;
		jieqiDays += 1;
		if(jieqiDays === 15){
			jieqiDays = 0;
			jieqiCur = nextJieqi(jieqiCur);
			if(jieqiCur === '芒种'){
				mangzhongDay = tday;
				for(let j=0; j<15; j++){
					ret[utcDayToKey(tday)] = `${jieqiCur}${JIAZI[rizhuIndex]}`;
					tday += 1;
					rizhuIndex = (rizhuIndex + 1) % 60;
				}
				break;
			}
		}
	}

	jieqiCur = '夏至';
	const xzStart = solsticeAnchorStart(xzSeed);   // 至点锚:夏至上元块应起于此(2026-08-02 二次修)
	if(xzStart !== null){
		if(!noLeap && tday < xzStart){ jieqiCur = '芒种'; }
	}else{
		const mangzhongStartDay = keyToUtcDay(curr.芒种.dateKey);   // 夏至种子缺失时的旧法兜底
		if(!noLeap && Number.isFinite(mangzhongStartDay) && mangzhongDay !== null && mangzhongStartDay >= mangzhongDay + leapDays){
			jieqiCur = '芒种';
		}
	}

	jieqiDays = 0;
	let daxueDay = null;
	for(let i=0; i<300; i++){
		ret[utcDayToKey(tday)] = `${jieqiCur}${JIAZI[rizhuIndex]}`;
		tday += 1;
		rizhuIndex = (rizhuIndex + 1) % 60;
		jieqiDays += 1;
		if(jieqiDays === 15){
			jieqiDays = 0;
			jieqiCur = nextJieqi(jieqiCur);
			if(jieqiCur === '大雪'){
				daxueDay = tday;
				for(let j=0; j<15; j++){
					ret[utcDayToKey(tday)] = `${jieqiCur}${JIAZI[rizhuIndex]}`;
					tday += 1;
					rizhuIndex = (rizhuIndex + 1) % 60;
				}
				break;
			}
		}
	}

	jieqiCur = '冬至';
	const dzStart = solsticeAnchorStart(dzCurrSeed);   // 至点锚:本年冬至上元块应起于此(2026-08-02 二次修)
	if(dzStart !== null){
		if(!noLeap && tday < dzStart){ jieqiCur = '大雪'; }
	}else{
		const daxueStartDay = keyToUtcDay(curr.大雪.dateKey);   // 冬至种子缺失时的旧法兜底
		if(!noLeap && Number.isFinite(daxueStartDay) && daxueDay !== null && daxueStartDay >= daxueDay + leapDays){
			jieqiCur = '大雪';
		}
	}

	jieqiDays = 0;
	for(let i=0; i<300; i++){
		ret[utcDayToKey(tday)] = `${jieqiCur}${JIAZI[rizhuIndex]}`;
		tday += 1;
		rizhuIndex = (rizhuIndex + 1) % 60;
		jieqiDays += 1;
		if(jieqiDays === 15){
			jieqiDays = 0;
			jieqiCur = nextJieqi(jieqiCur);
			if(jieqiCur === '立春'){
				ret[utcDayToKey(tday)] = `${jieqiCur}${JIAZI[rizhuIndex]}`;
				break;
			}
		}
	}
	if(YINYANGDUN_CACHE.has(seedSig)){
		YINYANGDUN_CACHE.delete(seedSig);
	}
	YINYANGDUN_CACHE.set(seedSig, ret);
	if(YINYANGDUN_CACHE.size > MAX_YINYANGDUN_CACHE){
		const firstKey = YINYANGDUN_CACHE.keys().next().value;
		if(firstKey){
			YINYANGDUN_CACHE.delete(firstKey);
		}
	}
	return ret;
}

// 置闰/无闰查表单源:算 dkey(含 after23NewDay=1 的 23 时进位)→ 查 buildYinyangdunMap 逐日表,
// 返回「节气+日柱」标签(如「小暑己酉」)或 null。qimenJuNameZhirun 与 qimenDingjuJieqi 共用,
// 保证"定局所用节气"与"对外报的定局节气"永远同一次查表口径(2026-08-02 缺陷②修)。
function lookupYinyangdunLabel(dateParts, yearSeeds, after23NewDay, noLeap, leapThresholdDays){
	const yyd = buildYinyangdunMap(dateParts.year, yearSeeds, noLeap, leapThresholdDays);
	if(!yyd){
		return null;
	}
	let dkey = `${dateParts.year}${`${dateParts.month}`.padStart(2, '0')}${`${dateParts.day}`.padStart(2, '0')}`;
	// 用户语义(拍板,字面直觉版): after23NewDay=1「23点算第二天」时 hour==23 进位到次日;after23NewDay=0 守今。
	if(dateParts.hour === 23 && (after23NewDay === 1 || after23NewDay === '1' || after23NewDay === true)){
		dkey = utcDayToKey(keyToUtcDay(dkey) + 1);
	}
	const jqrz = yyd[dkey];
	if(!jqrz || jqrz.length < 4){
		return null;
	}
	return jqrz;
}

// 定局节气(置闰/无闰):超神时定局节气≠曆法节气,展示/快照必须用它,否则出现「阳遁七局中元+
// 大雪中元」式矛盾串(缺陷②)。查不到返回 ''(调用方回退曆法节气,与 qimenJuNameZhirun 退拆补对齐)。
function qimenDingjuJieqi(dateParts, yearSeeds, after23NewDay, noLeap, leapThresholdDays){
	const jqrz = lookupYinyangdunLabel(dateParts, yearSeeds, after23NewDay, noLeap, leapThresholdDays);
	return jqrz ? jqrz.substring(0, 2) : '';
}

function qimenJuNameZhirun(dateParts, dayGanzhi, yearSeeds, fallbackJieqi, after23NewDay, noLeap, leapThresholdDays){
	const jqrz = lookupYinyangdunLabel(dateParts, yearSeeds, after23NewDay, noLeap, leapThresholdDays);
	if(!jqrz){
		return qimenJuNameChaibu(fallbackJieqi || '', dayGanzhi);
	}
	const jieqi = jqrz.substring(0, 2);
	const yuan = findYuan(dayGanzhi);
	const yuanId = yuan === '上元' ? 0 : (yuan === '中元' ? 1 : 2);
	const code = JIEQI2JU[jieqi] || '一七四阳';
	const yy = code.substring(code.length - 1);
	return `${yy}遁${code.substring(yuanId, yuanId + 1)}局${yuan}`;
}

// WP-C 无闰法(资料§5.4):同超神接气但 noLeap=true 永不置闰(置闰天数对无闰无效,透传仅为签名一致)。
function qimenJuNameWurun(dateParts, dayGanzhi, yearSeeds, fallbackJieqi, after23NewDay, leapThresholdDays){
	return qimenJuNameZhirun(dateParts, dayGanzhi, yearSeeds, fallbackJieqi, after23NewDay, true, leapThresholdDays);
}

// WP-C 茅山布局法(资料§5.3):交节时刻为唯一锚点,足时辰顺推三元,不问符头、不置闰。
// shichen=floor((now−交节时刻)/2时);yuanIdx=min(floor((shichen mod180)/60),2)。缺交节种子→退拆补。
// WP-C 茅山布局法(专题§2.1):以「交节时刻」为唯一锚,何时交节即从该刻起用该节气上元,足60时辰(=5日)进一元,
//   满3元(下元足60时辰)即接下一节气上元(即便下一节气交节尚差零点几日也照接);不用符头、不置闰。
//   须任意节气的精确交节时刻——故扫全24种子取「≤now 的最晚节气」为当前节气(非用节令jq,否则中气如冬至取不到、退拆补)。
function qimenJuNameMaoshan(dateParts, jieqi, yearSeeds, dayGanzhi){
	if(yearSeeds && dateParts){
		const now = new Date(dateParts.year, normalizeNum(dateParts.month, 1) - 1, normalizeNum(dateParts.day, 1), normalizeNum(dateParts.hour, 0), normalizeNum(dateParts.minute, 0)).getTime();
		let bestJq = null;
		let bestTime = null;
		[dateParts.year - 1, dateParts.year, dateParts.year + 1].forEach((y)=>{
			const ys = yearSeeds[y];
			if(!ys){ return; }
			Object.keys(ys).forEach((term)=>{
				const s = ys[term];
				if(s && s.time){
					const t = new Date(`${s.time}`.replace(/-/g, '/')).getTime();
					if(Number.isFinite(t) && t <= now && (bestTime === null || t > bestTime)){
						bestTime = t;
						bestJq = term;
					}
				}
			});
		});
		if(bestJq !== null && bestTime !== null){
			const shichen = Math.floor((now - bestTime) / (2 * 60 * 60 * 1000));
			if(shichen >= 0){
				const yuanRaw = Math.floor(shichen / 60);          // 60时辰=5日=一元
				let jqCur = bestJq;
				let yuanIdx = yuanRaw;
				if(yuanRaw >= 3){ jqCur = nextJieqi(bestJq); yuanIdx = 0; }   // 满3元→进下一节气上元
				const yy = YANG_JIEQI.indexOf(jqCur) >= 0 ? '阳遁' : '阴遁';
				const code = JIEQI_CODE[jqCur] || '一七四';
				return `${yy}${code[yuanIdx]}局${['上元', '中元', '下元'][yuanIdx]}`;
			}
		}
	}
	return qimenJuNameChaibu(jieqi, dayGanzhi);
}

function joinList(list){
	if(!list || !list.length){
		return '无';
	}
	return list.join('、');
}

function getQimenShenShaValue(mapObj, name, key){
	if(!mapObj || !name || !key){
		return '';
	}
	const list = mapObj[name] && mapObj[name][key] ? mapObj[name][key] : [];
	return list.join('');
}

function resolveQimenGuiRen(dayGan, isDiurnal){
	const dayGui = LRConst.DayGuiDunJia[dayGan] || (QIMEN_GUIREN_DAY_NIGHT[dayGan] ? QIMEN_GUIREN_DAY_NIGHT[dayGan][0] : '');
	const nightGui = LRConst.NightGuiDunJia[dayGan] || (QIMEN_GUIREN_DAY_NIGHT[dayGan] ? QIMEN_GUIREN_DAY_NIGHT[dayGan][1] : '');
	if(!dayGui || !nightGui){
		return {
			dayGui,
			nightGui,
			trueGuiRen: '',
			muGuiRen: '',
			isDiurnal: null,
		};
	}
	const isDaytime = isDiurnal === true;
	const isNight = isDiurnal === false;
	const trueGuiRen = isDaytime ? dayGui : (isNight ? nightGui : '');
	const muGuiRen = isDaytime ? nightGui : (isNight ? dayGui : '');
	return {
		dayGui,
		nightGui,
		trueGuiRen,
		muGuiRen,
		isDiurnal,
	};
}

function buildQimenShenSha(ganzhi, isDiurnal){
	const dayGan = getGanzhiGan(ganzhi && ganzhi.day ? ganzhi.day : '');
	const dayZhi = getGanzhiZhi(ganzhi && ganzhi.day ? ganzhi.day : '');
	const monthZhi = getGanzhiZhi(ganzhi && ganzhi.month ? ganzhi.month : '');
	const yearZhi = getGanzhiZhi(ganzhi && ganzhi.year ? ganzhi.year : '');
	const timeZhi = getGanzhiZhi(ganzhi && ganzhi.time ? ganzhi.time : '');
	const guiren = resolveQimenGuiRen(dayGan, isDiurnal);
	const byName = {};

	const defs = [
		{ group: '日干', name: '日禄', map: QIMEN_SHENSHA_DAY_STEMS, key: dayGan },
		{ group: '日干', name: '日德', map: QIMEN_SHENSHA_DAY_STEMS, key: dayGan },
		{ group: '月支', name: '天马', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '日支', name: '日马', map: QIMEN_SHENSHA_DAY_BRANCH, key: dayZhi },
		{ group: '年支', name: '年马', map: QIMEN_SHENSHA_YEAR_BRANCH, key: yearZhi },
		{ group: '日支', name: '桃花', map: QIMEN_SHENSHA_DAY_BRANCH, key: dayZhi },
		{ group: '日支', name: '破碎', map: QIMEN_SHENSHA_DAY_BRANCH, key: dayZhi },
		{ group: '月支', name: '生气', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '死气', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '年支', name: '病符', map: QIMEN_SHENSHA_YEAR_BRANCH, key: yearZhi },
		{ group: '月支', name: '血支', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '年支', name: '孤辰', map: QIMEN_SHENSHA_YEAR_BRANCH, key: yearZhi },
		{ group: '年支', name: '寡宿', map: QIMEN_SHENSHA_YEAR_BRANCH, key: yearZhi },
		{ group: '年支', name: '丧门', map: QIMEN_SHENSHA_YEAR_BRANCH, key: yearZhi },
		{ group: '年支', name: '吊客', map: QIMEN_SHENSHA_YEAR_BRANCH, key: yearZhi },
		{ group: '月支', name: '成神', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '会神', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '解神', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '天目', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '医星', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '月厌', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '月破', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '贼神', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '日干', name: '贵人', value: guiren.trueGuiRen },
		{ group: '日干', name: '游都', map: QIMEN_SHENSHA_DAY_STEMS, key: dayGan },
		{ group: '日干', name: '文昌', map: QIMEN_SHENSHA_DAY_STEMS, key: dayGan },
		{ group: '月支', name: '丧车', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '日干', name: '幕贵', value: guiren.muGuiRen },
	];

	const allItems = defs.map((item)=>{
		const value = (item.value !== undefined ? item.value : getQimenShenShaValue(item.map, item.name, item.key)) || '—';
		const one = { group: item.group, name: item.name, value };
		byName[item.name] = one;
		return one;
	});

	const groups = ['日干', '日支', '月支', '年支'].map((group)=>({
		group,
		items: allItems.filter((item)=>item.group === group),
	}));

	const summaryNames = ['日禄', '日德', '天马', '日马', '年马'];
	const summary = summaryNames
		.map((name)=>byName[name])
		.filter((item)=>!!item);

	return {
		summary,
		groups,
		allItems,
		refs: {
			dayGan,
			dayZhi,
			monthZhi,
			yearZhi,
			timeZhi,
			dayGui: guiren.dayGui,
			nightGui: guiren.nightGui,
			isDiurnal: guiren.isDiurnal,
		},
	};
}

// [H-G] 日家·古籍金函系独立盘:不走局法/三盘,直接查六十干支占方全表。
//   阴阳盘=冬至后阳/夏至后阴(与日家同源 half-year 判定,书文「冬至节始为阳/夏至节始为阴」);
//   八方星门按表列序(北东北东东南南西南西西北)落到九宫格;中宫=本干支之星;吉凶着色按书定分类。
const JINHAN_DIR_TO_POS = { 北: 8, 东北: 7, 东: 4, 东南: 1, 南: 2, 西南: 3, 西: 6, 西北: 9 };
export function buildJinhanRiJiaPan(fields, nongli, opts, context){
	const dateParts = parseDateTime(fields);
	if(!dateParts){ return null; }
	// 🔴 四柱必须走 buildGanzhiForQimen 同源(年界档/晚子时/字段别名兜底全语义)——
	// 曾手写简版只读 nongli.yearGanZi,后端农历字段别名下年柱空(用户实机抓)。
	const ganzhi = buildGanzhiForQimen(nongli || {}, dateParts, opts || {}, context || {});
	const dayGz = ganzhi.day;
	const rec = JINHAN_TABLE[dayGz];
	if(!rec){ return null; }
	const jieqi = normalizeText(nongli && nongli.jieqi ? nongli.jieqi : '');
	const seeds = context && context.jieqiYearSeeds ? context.jieqiYearSeeds : null;
	const half = dayJiaHalfYear(seeds, dateParts);
	const yang = half ? half.yang : isYangDunJieqi(jieqi);
	const doorsBook = yang ? rec.yangDoors : rec.yinDoors;
	const stars = yang ? rec.yangStars : rec.yinStars;
	const menPai = (opts && opts.jinhanMenPai) === 'shun' ? 'shun' : 'book';
	const doors = menPai === 'shun' ? '休生伤杜景死惊开'.split('') : doorsBook;
	const daJi = yang ? rec.daJiYang : rec.daJiYin;
	const daJiNote = yang ? (rec.daJiYangNote || '') : (rec.daJiYinNote || '');
	const cells = PALACE_GRID.map((palaceNum)=>{
		if(palaceNum === 5){
			return {
				palaceNum, palaceName: '中', isCenter: true,
				diGan: '', tianGan: '', god: '',
				door: '', tianXing: rec.center,
				jinhanStarJi: JINHAN_STAR_JI[rec.center] || '',
				jinhanDoorJi: '',
				isJinhan: true,
			};
		}
		const dirIdx = JINHAN_DIRS.findIndex((d)=>JINHAN_DIR_TO_POS[d] === palaceNum);
		const dir = JINHAN_DIRS[dirIdx];
		const door = doors[dirIdx] || '';
		const star = stars[dirIdx] || '';
		return {
			palaceNum, palaceName: PALACE_NAME[palaceNum] || '', isCenter: false,
			diGan: '', tianGan: '', god: '',
			door, tianXing: star,
			jinhanDir: dir,
			jinhanDoorJi: JINHAN_DOOR_JI[door] || '',
			jinhanStarJi: JINHAN_STAR_JI[star] || '',
			isXiShen: rec.xiShen === dir,
			isDaJi: (daJi || []).indexOf(dir) >= 0,
			isJinhan: true,
		};
	});
	return {
		isJinhan: true,
		dateStr: dateParts.dateStr,
		timeStr: dateParts.timeStr,
		lunarText: nongli ? `${nongli.year || ''}年${nongli.leap ? '闰' : ''}${nongli.month || ''}${nongli.day || ''}` : '',
		ganzhi,
		cells,
		juText: `古籍日家·${yang ? '阳盘' : '阴盘'}`,
		jinhan: {
			dayGz,
			pantype: yang ? '阳' : '阴',
			menPai,
			center: rec.center,
			xiShen: rec.xiShen,
			jiShi: rec.jiShi,
			daJiFang: (daJi || []).join('、') + (daJiNote ? `（${daJiNote}）` : ''),
			shiText: rec.shiText,
		},
		options: {
			paiPanType: 6,
			paiPanLabel: '日家·古籍金函系',
			jinhanMenPai: menPai,
			jinhanMenPaiLabel: getOptionLabel(JINHAN_MENPAI_OPTIONS, menPai),
		},
	};
}

export function calcDunJia(fields, nongli, options, context){
	// [H-G] 日家·古籍金函系=独立体系(查表盘,无局法/三盘),早返专用构建器。
	if(normalizeNum(options && options.paiPanType, 3) === 6){
		return buildJinhanRiJiaPan(fields, nongli, options || {}, context);
	}
	const dateParts = parseDateTime(fields);
	if(!dateParts){
		return null;
	}
	const opts = {
		qijuMethod: 'zhirun',
		school: '转盘',
		kongMode: 'day',
		yimaMode: 'day',
		timeAlg: 0,
		shiftPalace: 0,
		after23NewDay: 0,
		fengJu: false,
		zhirunLeapDays: 9,
		...(options || {}),
	};
	// 旧数据迁移:阴盘曾为盘式(school='阴盘'),现为起局法(qijuMethod='shuzi')。须在 normalizeSchool(阴盘→转盘) 前判 raw school,
	// 保旧存盘(命盘/事盘/AI 快照)载入仍走报数定局。normalizeKenQimenOptions 已在 UI 层同迁,此为引擎兜底(覆盖任意直接调用方)。
	if(opts.school === '阴盘'){ opts.qijuMethod = 'shuzi'; }
	opts.qijuMethod = normalizeQijuMethod(opts.qijuMethod);
	opts.school = normalizeSchool(opts.school);
	opts.timeAlg = normalizeTimeAlg(opts.timeAlg);
	const shiftPalace = normalizeShiftPalace(opts.shiftPalace);

	const ganzhi = buildGanzhiForQimen(nongli || {}, dateParts, opts, context || {});
	const jieqi = getCurrentJieqi(nongli || {});
	const paiPanMeta = resolvePaiPanMeta(opts, ganzhi, jieqi, dateParts, context || {});
	let qmju = paiPanMeta.qmju || buildQmjuByMeta(paiPanMeta.yinYangDun, paiPanMeta.juShu, paiPanMeta.sanYuan);
	// 数字起盘(起局=数字·报数,§5.5 通则):报数各位求和除9(余0作9)定局数;阴阳遁仍按节气;元沿用节气符头元。
	// 与盘式(转/飞/混)正交——任意盘式选数字起局皆生效。报数空 → 退节气拆补(占位不崩)。报数→用神宫供右栏/快照。传本有别。
	let shuziInfo = null;
	if(normalizeQijuMethod(opts.qijuMethod) === 'shuzi'){
		const shuziDigits = String(opts.shuziReportNumber || '').replace(/[^0-9]/g, '');
		if(shuziDigits){
			shuziInfo = computeShuziYongShenGong(shuziDigits);
			const shuziSum = shuziDigits.split('').reduce((acc, ch)=>acc + Number(ch), 0);
			const shuziJu = (shuziSum % 9) === 0 ? 9 : (shuziSum % 9);
			qmju = buildQmjuByMeta(isYangDunJieqi(jieqi) ? '阳遁' : '阴遁', shuziJu, paiPanMeta.sanYuan);
		}
	}
	// WP-A 盘式分流:飞盘走 panFeipan(洛书飞,一次算齐天/门/星/神+值符值使);转盘走原五函数(字节零回归)。
	// 月家(§9):排盘锚点用月柱(值符随月干、值使随月支、寻月柱旬首)→ 给排盘函数传 time=月柱 的 panGanzhi;
	// 时家/刻家等 panGanzhi===ganzhi(字节零回归)。
	// 各家排盘锚点:年家用年柱、月家用月柱、日家用日柱(值符随该柱天干、值使随该柱地支、寻该柱旬首);
	// 时家/刻家/综合 panGanzhi===ganzhi(字节零回归)。
	let panGanzhi = ganzhi;
	if(ganzhi){
		if(opts.paiPanType === 0 && ganzhi.year){ panGanzhi = { ...ganzhi, time: ganzhi.year }; }
		else if(opts.paiPanType === 1 && ganzhi.month){ panGanzhi = { ...ganzhi, time: ganzhi.month }; }
		else if(opts.paiPanType === 2 && ganzhi.day){ panGanzhi = { ...ganzhi, time: ganzhi.day }; }
	}
	const isFeipan = opts.school === '飞盘';
	const isHuohe = opts.school === '混合';                          // 飞转混合:星转·门飞·九神(专题§4.2)
	const fei = (isFeipan || isHuohe) ? panFeipan(panGanzhi, qmju, {
		feiXingShun: !!opts.feiXingShun, feiMenShun: !!opts.feiMenShun, feiShenShun: !!opts.feiShenShun,
		feiMenZhongCan: opts.feiMenZhongCan !== false, feiMenZhongShow: !!opts.feiMenZhongShow,
	}) : null;
	// 转盘/混合 都需转盘值符值使(混合的值符星宫走转盘);飞盘走飞盘 zfzs。
	// 🔴 值符值使解算上下文:此前只有这一处传了 ext,而下面排八门的 panDoor 没传 →
	//    「值符星=禽」时 resolveSpecialZhiShi(undefined,…) 恒取 0 档,八门实际起排永远从死门起,
	//    与标题显示的值使门名自相矛盾(用户切「阴阳遁/节气」两档看不到盘面变化)。四处同源。
	const zfzsExt = {
		zhiShiType: opts.zhiShiType,
		yinYangDun: paiPanMeta.yinYangDun,
		jieqi,
		godsPreset: opts.godsPreset,   // [H-B] 八神预设透传(panGod 消费)
		jiGongMode: opts.jiGongMode,   // [H-C] 中宫寄宫档透传(panGod/panDoor/panStar/panSky 消费)
	};
	const zfzsZhuan = isFeipan ? null : zhifuNZhishi(panGanzhi, qmju, zfzsExt);
	// 混合:值符星宫=转盘(星轮转),值使门宫=飞盘(门飞泊);故取转盘 zfzs 但门宫换飞盘的。
	// [H-D] 混合盘四层自由装配(mixTian/mixXing/mixMen/mixShen ∈ ''|'zhuan'|'fei';全缺省=历史组合:天转·星转·门飞·神飞)。
	const mixOf = (key, dft)=>{ const v = opts[key]; return (v === 'fei' || v === 'zhuan') ? v : dft; };
	const mixTian = mixOf('mixTian', 'zhuan');
	const mixXing = mixOf('mixXing', 'zhuan');
	const mixMen = mixOf('mixMen', 'fei');
	const mixShen = mixOf('mixShen', 'fei');
	const zfzs = isFeipan ? fei.zfzs : (isHuohe ? {
		...zfzsZhuan,
		// 值符星宫随星层来源、值使门宫随门层来源(层取转则用转盘解算,取飞则用飞盘解算)
		值符星宫: (mixXing === 'fei' && fei && fei.zfzs) ? fei.zfzs.值符星宫 : zfzsZhuan.值符星宫,
		值使门宫: (mixMen === 'fei' && fei && fei.zfzs) ? fei.zfzs.值使门宫 : zfzsZhuan.值使门宫,
	} : zfzsZhuan);
	const dipanGua = panEarth(qmju);
	const tianpanGua = isFeipan ? fei.tianpanGua : (isHuohe && mixTian === 'fei' ? fei.tianpanGua : panSky(panGanzhi, qmju, zfzsExt));
	const menGua = isFeipan ? fei.menGua : (isHuohe ? (mixMen === 'fei' ? fei.menGua : panDoor(panGanzhi, qmju, zfzsExt)) : panDoor(panGanzhi, qmju, zfzsExt));
	const starGua = isFeipan ? fei.starGua : (isHuohe && mixXing === 'fei' ? fei.starGua : panStar(panGanzhi, qmju, zfzsExt));
	const shenGua = isFeipan ? fei.shenGua : (isHuohe ? (mixShen === 'fei' ? fei.shenGua : panGod(panGanzhi, qmju, zfzsExt)) : panGod(panGanzhi, qmju, zfzsExt));
	const xunkong = daykongShikong(ganzhi.day, ganzhi.time);

	const diPanBase = convertGuaMapToPos(dipanGua);
	const tianPanBase = convertGuaMapToPos(tianpanGua);
	const menBase = convertGuaMapToPos(menGua);
	const starBase = convertGuaMapToPos(starGua);
	const shenBase = convertGuaMapToPos(shenGua);
	const diPan = rotateOuterMapByShift(diPanBase, shiftPalace);
	const tianPan = rotateOuterMapByShift(tianPanBase, shiftPalace);
	const men = rotateOuterMapByShift(menBase, shiftPalace);
	const star = rotateOuterMapByShift(starBase, shiftPalace);
	const shen = rotateOuterMapByShift(shenBase, shiftPalace);
	// 转盘八神名按预设分派(默认=历史恒虎玄);飞盘/混合九神保真(含勾陈/太常/朱雀),不替换。
	if(!isFeipan && !isHuohe){
		Object.keys(shen).forEach((k)=>{ shen[k] = applyGodsPreset(String(shen[k] || ''), opts.godsPreset); });
	}

	// [H-B] 暗干层(默认 off=null 零回归):模式产每宫暗干;showAnZhi 开再配旬内暗支。
	// 🔴 ctx 必须传「卦名键」盘面(panAnGan 输出以卦名为键,cells 装配经 GUA_TO_NUM 反查):
	//   直接传 rotate 后的 men/diPan(宫号键)会产出数字键 → cells 全滤空(真机实抓的死链);
	//   故此处以 PALACE_NAME 把移星后的门/地盘归一回卦名键(暗干基于最终盘面,含移星)。
	const menByGua = {};
	const diByGua = {};
	for(let g = 1; g <= 9; g++){
		const guaName = PALACE_NAME[g];
		if(!guaName){ continue; }
		menByGua[guaName] = men[g] || '';
		diByGua[guaName] = diPan[g] || '';
	}
	const anGanMap = panAnGan(opts.anGanMode, {
		menGua: menByGua, dipanGua: diByGua, yy: paiPanMeta.yinYangDun,
		shiGan: (panGanzhi.time || '').charAt(0),
		zhishiGong: zfzs && zfzs.值使门宫 ? zfzs.值使门宫[1] : '',
		jiGong: resolveJiGong(opts.jiGongMode, paiPanMeta.yinYangDun, jieqi),
	});
	const anZhiMap = (anGanMap && opts.showAnZhi)
		? Object.keys(anGanMap).reduce((acc, g)=>{ acc[g] = anZhiOf(anGanMap[g], panGanzhi.time); return acc; }, {})
		: null;

	const specials = resolveSpecials(tianPan);
	const menPo = resolveMenPo(men);
	// [H-E] kongMarkBoth=同时标日空+时空(并集);默认关=单模式(现状字节稳)
	const kongWang = opts.kongMarkBoth ? `${xunkong.日空 || ''}${xunkong.时空 || ''}` : getKongByMode(opts.kongMode, xunkong);
	const kongWangMeta = resolveKongWangPalaces(kongWang);
	// [H-E] showAllKong=四柱空亡全览(纯附加信息,默认关=null 零回归)
	const allKong = opts.showAllKong ? {
		年空: GUXU[getXunHead(ganzhi.year)] || '',
		月空: GUXU[getXunHead(ganzhi.month)] || '',
		日空: xunkong.日空 || '',
		时空: xunkong.时空 || '',
	} : null;
	const yiMaMeta = resolveYiMa(opts.yimaMode, ganzhi);
	const isDiurnal = context && context.isDiurnal !== undefined && context.isDiurnal !== null
		? !!context.isDiurnal
		: (nongli && nongli.isDiurnal !== undefined && nongli.isDiurnal !== null ? !!nongli.isDiurnal : null);

	let zhiFuPalace = rotateOuterPalaceNum(GUA_POS_MAP[zfzs.值符星宫[1]] || 5, shiftPalace);
	let zhiShiPalace = rotateOuterPalaceNum(GUA_POS_MAP[zfzs.值使门宫[1]] || 5, shiftPalace);
	let zfStarRaw = (zfzs.值符星宫[0] || '');
	let zsDoorRaw = (zfzs.值使门宫[0] || '');
	// [H-E] 移星值符两档:follow(默认)=标记随几何平移;recalc=移后盘视为新局按标准定义重解——
	//   新值符星/值使门 = 移后地盘旬首遁仪所在宫的本位星/本位门(门为「中」依转盘传统取死门),
	//   标记宫 = 新星名/门名在移后星层/门层的实际落宫。仅移星≠0 时生效(=0 两档恒同,默认零回归)。
	if(opts.shiftZhiFuMode === 'recalc' && normalizeShiftPalace(shiftPalace) !== 0){
		const dunYi = JJ[getXunHead(panGanzhi.time)] || '戊';
		let dg = 0;
		for(let i = 1; i <= 9; i++){ if(String(diPan[i] || '') === dunYi){ dg = i; break; } }
		if(dg){
			const luoshu = LUOSHU_NUM[PALACE_NAME[dg]] || 5;
			const newStar = JIU_XING[luoshu - 1] || '';
			let newDoor = '休死伤杜中开惊生景'.charAt(luoshu - 1) || '';
			if(newDoor === '中' && !isFeipan){ newDoor = '死'; }
			const starMatch = (cellStar)=>{
				const cs = String(cellStar || '');
				if(!newStar){ return false; }
				if(cs.indexOf(newStar) >= 0){ return true; }
				return ('芮禽'.indexOf(newStar) >= 0) && cs.indexOf('内') >= 0;   // 转盘芮/禽归一显「内」
			};
			for(let i = 1; i <= 9; i++){ if(starMatch(star[i])){ zhiFuPalace = i; break; } }
			for(let i = 1; i <= 9; i++){ if(String(men[i] || '').charAt(0) === newDoor){ zhiShiPalace = i; break; } }
			zfStarRaw = newStar || zfStarRaw;
			zsDoorRaw = newDoor || zsDoorRaw;
		}
	}
	const zfStarDisp = isFeipan ? zfStarRaw : zfStarRaw.replace(/[芮禽]+/g, '内');   // 转盘值符=天禽(中宫禽/芮)时显「内」(天内),飞盘保「禽」
	const zhiFu = JIU_XING_NAME[zfStarDisp] || `${zfStarDisp}`;
	const zhiShi = BA_MEN_NAME[zsDoorRaw] || `${zsDoorRaw}门`;

	// [H-B] 暗干卦名键→宫号键(cells 以 palaceNum 索引)
	const GUA_TO_NUM = Object.keys(PALACE_NAME).reduce((acc, n)=>{ acc[PALACE_NAME[n]] = Number(n); return acc; }, {});
	const anGanByNum = anGanMap ? Object.keys(anGanMap).reduce((acc, gua)=>{ if(GUA_TO_NUM[gua]){ acc[GUA_TO_NUM[gua]] = anGanMap[gua]; } return acc; }, {}) : null;
	const anZhiByNum = anZhiMap ? Object.keys(anZhiMap).reduce((acc, gua)=>{ if(GUA_TO_NUM[gua]){ acc[GUA_TO_NUM[gua]] = anZhiMap[gua]; } return acc; }, {}) : null;
	const cells = buildCells(diPan, tianPan, men, shen, star, zhiFuPalace, zhiShiPalace, {
		jiXingPalaces: specials.jiXingPalaces,
		ruMuPalaces: specials.ruMuPalaces,
		menPoPalaces: menPo.palaces,
		kongWangPalaces: kongWangMeta.palaces,
		yimaPalace: yiMaMeta.palace,
		godsPreset: opts.godsPreset,
		anGanByNum,
		anZhiByNum,
		school: opts.school,
	});

	const qmjuMeta = parseQmju(qmju);

	return {
		anGan: anGanMap,   // [H-B] 每宫暗干(off=null);盘面/快照消费
		anZhi: anZhiMap,   // [H-B] 每宫暗支(showAnZhi 开时;随暗干)
		allKong,           // [H-E] 四柱空亡全览(showAllKong 开;默认 null)
		xunKong: xunkong,  // [H-E] {日空,时空}恒暴露(kongMarkBoth 显示层拆分消费)
		keIndex: paiPanMeta.keIndex || null,   // [H-F] 刻家第几刻(1..10;非刻家=null)
		keGanZhi: paiPanMeta.keGanZhi || '',   // [H-F] 刻柱干支(时柱锚法:首刻=时柱逐刻进一;非刻家='')
		dateStr: dateParts.dateStr,
		timeStr: dateParts.timeStr,
		realSunTime: (context && context.displaySolarTime) || (nongli ? (nongli.birth || '') : ''),
		lunarText: nongli ? `${nongli.year || ''}年${nongli.leap ? '闰' : ''}${nongli.month || ''}${nongli.day || ''}` : '',
		jiedelta: nongli ? (nongli.jiedelta || '') : '',
		ganzhi,
		fuTou: resolveFuTouByBacktrack(ganzhi.day),
		// 节气 chip/快照用「定局节气」——置闰超神时≠曆法节气,旧拼法(曆法节气+定局元)会出
		// 「阳遁七局中元+大雪中元」矛盾串(2026-08-02 缺陷②修);曆法节气另存 lifaJieqi 供参照。
		jieqiText: `${paiPanMeta.dingjuJieqi || jieqi || '未知节气'}${paiPanMeta.sanYuan !== undefined ? paiPanMeta.sanYuan : (qmjuMeta.yuan || '')}`,
		dingjuJieqi: paiPanMeta.dingjuJieqi || jieqi || '',
		lifaJieqi: jieqi || '',
		yinYangDun: paiPanMeta.yinYangDun || (qmjuMeta.yy === '阴' ? '阴遁' : '阳遁'),
		sanYuan: paiPanMeta.sanYuan !== undefined ? paiPanMeta.sanYuan : (qmjuMeta.yuan || ''),
		juShu: juNumberToCn(paiPanMeta.juShu || (CNUMBER.indexOf(qmjuMeta.kook) + 1)),
		juText: qmju,
		xunShou: getXunHead(ganzhi.day),
		kongWang,
		zhiFu,
		zhiShi,
		zhiFuPalace,
		zhiShiPalace,
		shiftPalace,
		fengJu: !!opts.fengJu,
		school: opts.school,
		shuziInfo,
		diPan,
		tianPan,
		renPan: men,
		shenPan: shen,
		tianGan: tianPan,
		diPanList: mapListByPos(diPan),
		tianPanList: mapListByPos(tianPan),
		renPanList: mapListByPos(men),
		shenPanList: mapListByPos(shen),
		jiXingPalaces: specials.jiXingPalaces,
		ruMuPalaces: specials.ruMuPalaces,
		liuYiJiXing: specials.liuYi,
		qiYiRuMu: specials.ruMu,
		menPo,
		kongWangDesc: kongWangMeta.list,
		kongWangPalaces: kongWangMeta.palaces,
		yiMa: yiMaMeta,
		shenSha: buildQimenShenSha(ganzhi, isDiurnal),
		cells,
		xunkong,
		options: {
			sexLabel: getOptionLabel(SEX_OPTIONS, opts.sex),
			dateTypeLabel: getOptionLabel(DATE_TYPE_OPTIONS, opts.dateType),
			leapLabel: getOptionLabel(LEAP_MONTH_OPTIONS, opts.leapMonthType),
			xuShiLabel: getOptionLabel(XUSHI_OPTIONS, opts.xuShiSuiType),
			jieQiLabel: getOptionLabel(JIEQI_OPTIONS, opts.jieQiType),
			paiPanLabel: getOptionLabel(PAIPAN_OPTIONS, opts.paiPanType),
			// 飞盘/混合档值使由飞宫定序直出,取法开关不参与 → 回显如实标注(勿谎报所选取法生效)
			zhiShiLabel: (isFeipan || isHuohe) ? '飞宫定序(取法不适用)' : getOptionLabel(ZHISHI_OPTIONS, opts.zhiShiType),
			yueJiaLabel: getOptionLabel(YUEJIA_QIJU_OPTIONS, opts.yueJiaQiJuType),
			yearLabel: getOptionLabel(YEAR_GZ_OPTIONS, opts.yearGanZhiType),
			monthLabel: getOptionLabel(MONTH_GZ_OPTIONS, opts.monthGanZhiType),
			dayLabel: getOptionLabel(DAY_GZ_OPTIONS, opts.dayGanZhiType),
			daySwitchLabel: getOptionLabel(DAY_SWITCH_OPTIONS, opts.after23NewDay),
			qijuMethodLabel: getOptionLabel(QIJU_METHOD_OPTIONS, opts.qijuMethod),
			schoolLabel: getOptionLabel(SCHOOL_OPTIONS, opts.school),
			godsPreset: opts.godsPreset || 'baihu_xuanwu',
			godsPresetLabel: getOptionLabel(GODS_PRESET_OPTIONS, opts.godsPreset || 'baihu_xuanwu'),
			jiGongMode: opts.jiGongMode || 'kun',
			jiGongModeLabel: getOptionLabel(JIGONG_MODE_OPTIONS, opts.jiGongMode || 'kun'),
			feiXingShun: !!opts.feiXingShun,
			feiMenShun: !!opts.feiMenShun,
			feiShenShun: !!opts.feiShenShun,
			feiMenZhongCan: opts.feiMenZhongCan !== false,
			feiMenZhongShow: !!opts.feiMenZhongShow,
			mixTian: (opts.mixTian === 'fei' || opts.mixTian === 'zhuan') ? opts.mixTian : '',
			mixXing: (opts.mixXing === 'fei' || opts.mixXing === 'zhuan') ? opts.mixXing : '',
			mixMen: (opts.mixMen === 'fei' || opts.mixMen === 'zhuan') ? opts.mixMen : '',
			mixShen: (opts.mixShen === 'fei' || opts.mixShen === 'zhuan') ? opts.mixShen : '',
			kongMarkBoth: !!opts.kongMarkBoth,
			showAllKong: !!opts.showAllKong,
			shiftZhiFuMode: opts.shiftZhiFuMode === 'recalc' ? 'recalc' : 'follow',
			dayJiaJu: opts.dayJiaJu || 'yiyuan',
			dayJiaJuLabel: getOptionLabel(DAYJIA_JU_OPTIONS, opts.dayJiaJu || 'yiyuan'),
			keJiaFenDun: opts.keJiaFenDun || 'zihou',
			keJiaFenDunLabel: getOptionLabel(KEJIA_FENDUN_OPTIONS, opts.keJiaFenDun || 'zihou'),
			keZiZhengHuanShi: !!opts.keZiZhengHuanShi,
			yearJiaJu: opts.yearJiaJu === 'yinian' ? 'yinian' : 'sanyuan',
			yearJiaJuLabel: getOptionLabel(YEARJIA_JU_OPTIONS, opts.yearJiaJu === 'yinian' ? 'yinian' : 'sanyuan'),
			anGanModeLabel: getOptionLabel(ANGAN_MODE_OPTIONS, opts.anGanMode || 'off'),
			fullNameTips: !!opts.fullNameTips,
			// 当前实际所用定局法:数字盘=报数定局;各家自有定局(年/月/日/刻);时家/综合用拆补/置闰/茅山/无闰选择。
			dingFaLabel: (opts.qijuMethod === 'shuzi' && shuziInfo) ? '阴盘·报数定局'
				: opts.paiPanType === 0 ? (opts.yearJiaJu === 'yinian' ? '逐年换局·皆阴遁' : '三元起宫·皆阴遁')
					: opts.paiPanType === 1 ? (normalizeNum(opts.yueJiaQiJuType, 0) === 2 ? '逐月换局·皆阴遁' : (normalizeNum(opts.yueJiaQiJuType, 0) === 1 ? '年支直取·皆阴遁' : '年符头定局·皆阴遁'))
						: opts.paiPanType === 2 ? '节气三元·六十日一局'
							: opts.paiPanType === 4 ? (opts.keJiaFenDun === 'jieqi' ? '十分局·节气分遁' : '十分局·子后阳午后阴')
								: getOptionLabel(QIJU_METHOD_OPTIONS, opts.qijuMethod),
			// 中间盘角标:X家（X盘）=排盘体例（定局法/盘式短名）。
			boardTag: (function(){
				const fam = String(getOptionLabel(PAIPAN_OPTIONS, opts.paiPanType) || '时家奇门').replace('奇门', '').replace('排盘', '');
				let method;
				if(opts.qijuMethod === 'shuzi' && shuziInfo){ method = '阴盘'; }
				else if(opts.paiPanType === 0){ method = (opts.yearJiaJu === 'yinian' ? '逐年' : '三元'); }
				else if(opts.paiPanType === 1){ method = (normalizeNum(opts.yueJiaQiJuType, 0) === 2 ? '逐月' : (normalizeNum(opts.yueJiaQiJuType, 0) === 1 ? '年支' : '符头')); }
				else if(opts.paiPanType === 2){ method = '节气'; }
				else if(opts.paiPanType === 4){ method = '十分局'; }
				else { method = getOptionLabel(QIJU_METHOD_OPTIONS, opts.qijuMethod); }
				const panShi = (opts.school === '飞盘') ? '飞盘' : (opts.school === '混合' ? '飞转' : '转盘');
				return fam + '·' + panShi + '（' + method + '）';
			})(),
			kongModeLabel: getOptionLabel(KONG_MODE_OPTIONS, opts.kongMode),
			yimaModeLabel: getOptionLabel(MA_MODE_OPTIONS, opts.yimaMode),
			timeAlgLabel: getTimeAlgLabel(opts.timeAlg),
			shiftLabel: getOptionLabel(YIXING_OPTIONS, shiftPalace),
			fengJuLabel: opts.fengJu ? '已封局' : '未封局',
		},
	};
}

// GFM 表化同构数据行(空 cell → —),供 AI 导出/挂载可读化;数据层零变化——表行可逆变换逐字复原旧格式行。
const MD_DASH = '—';
function pushMdRows(lines, header, rows){
	lines.push(`| ${header.join(' | ')} |`);
	lines.push(`| ${header.map(()=>'---').join(' | ')} |`);
	rows.forEach((cells)=>{
		lines.push(`| ${cells.map((c)=>(c === undefined || c === null || c === '' ? MD_DASH : `${c}`)).join(' | ')} |`);
	});
}

export function buildDunJiaSnapshotText(pan){
	// [H-G] 古籍金函系日家专段(独立体系,与常规盘快照结构不同)
	if(pan && pan.isJinhan && pan.jinhan){
		const L = [];
		L.push('【日家占方（古籍金函系）】');
		L.push(`日期：${pan.dateStr || ''} ${pan.timeStr || ''}（${pan.lunarText || ''}）`);
		L.push(`日干支：${pan.jinhan.dayGz}（${pan.jinhan.pantype}盘·冬至后为阳/夏至后为阴）`);
		L.push(`八门排法：${pan.options.jinhanMenPaiLabel || '书表直录'}`);
		L.push(`中宫星：${pan.jinhan.center}（${JINHAN_STAR_JI[pan.jinhan.center] || ''}）`);
		const parts = [];
		(pan.cells || []).forEach((c)=>{
			if(!c || c.isCenter){ return; }
			parts.push(`${c.jinhanDir}:${c.tianXing}(${c.jinhanStarJi})${c.door}门(${c.jinhanDoorJi})${c.isXiShen ? '·喜神' : ''}${c.isDaJi ? '·大吉' : ''}`);
		});
		L.push(`八方星门：${parts.join('；')}`);
		L.push(`喜神方：${pan.jinhan.xiShen}；大吉方：${pan.jinhan.daJiFang || '—'}`);
		L.push(`大吉时：${pan.jinhan.jiShi}`);
		L.push(`十二时辰黄黑道：${pan.jinhan.shiText}`);
		L.push('吉凶判则（书定）：门重于星；开休生=吉门，杜景=平，死惊伤=凶门；天乙太乙太阴青龙=吉星，轩辕招摇=平，摄提咸池天符=凶星。');
		return L.join('\n');
	}

	if(!pan){
		return '';
	}
	const timeAlgLabel = pan.options && pan.options.timeAlgLabel ? pan.options.timeAlgLabel : '真太阳时';
	const directDateTime = `${pan.dateStr || ''} ${pan.timeStr || ''}`.trim();
	const lines = [];
	lines.push('[起盘信息]');
	lines.push(`日期：${directDateTime}`);
	lines.push(`直接时间：${directDateTime || '—'}`);
	lines.push(`真太阳时：${pan.realSunTime || '—'}`);
	lines.push(`计算基准：${timeAlgLabel}`);
	if(pan.lunarText){
		lines.push(`农历：${pan.lunarText}`);
	}
	if(pan.jiedelta){
		lines.push(`${pan.jiedelta}`);
	}
	lines.push(`干支：年${pan.ganzhi.year || ''} 月${pan.ganzhi.month || ''} 日${pan.ganzhi.day || ''} 时${pan.ganzhi.time || ''}`);
	lines.push(`空亡：${pan.kongWang}`);
	lines.push(`旬首：${pan.xunShou}`);
	lines.push('');

	lines.push('[盘型]');
	lines.push(`奇门遁甲方盘（${pan.options.paiPanLabel}）`);
	// sexLabel 缺(直调链未传 sex)时不出此行——零信息优于「命式：undefined」脏行。
	if(pan.options.sexLabel){ lines.push(`命式：${pan.options.sexLabel}`); }
	lines.push(`移星：${pan.options.shiftLabel || '原宫'}`);
	lines.push(`奇门封局：${pan.options.fengJuLabel || (pan.fengJu ? '已封局' : '未封局')}`);
	lines.push(`换日：${pan.options.daySwitchLabel || '23点算第二天'}`);
	lines.push(`时间算法：${timeAlgLabel}`);
	lines.push(`节气：${pan.jieqiText}`);
	if(pan.lifaJieqi && pan.dingjuJieqi && pan.lifaJieqi !== pan.dingjuJieqi){
		lines.push(`历法节气：${pan.lifaJieqi}（置闰超神，定局取${pan.dingjuJieqi}）`);
	}
	lines.push(`局数：${pan.juText}`);
	lines.push(`定局法：${pan.options.dingFaLabel || pan.options.qijuMethodLabel}`);
	lines.push(`盘式：${pan.options.schoolLabel || '转盘（排宫）'}`);
	// [H-B] 非默认档才出注记(默认字节稳)
	if(pan.options.godsPresetLabel && (pan.options.godsPreset && pan.options.godsPreset !== 'baihu_xuanwu')){ lines.push(`八神取神：${pan.options.godsPresetLabel}`); }
	// [H-C] 中宫寄宫非默认档注记(默认恒坤=零注记字节稳)
	if(pan.options.jiGongModeLabel && pan.options.jiGongMode && pan.options.jiGongMode !== 'kun'){ lines.push(`中宫寄宫：${pan.options.jiGongModeLabel}`); }
	// [H-D] 飞盘细项/混合装配非默认注记(默认零注记字节稳)
	(function(){
		const o = pan.options;
		const shun = [o.feiXingShun ? '九星' : '', o.feiMenShun ? '九门' : '', o.feiShenShun ? '九神' : ''].filter(Boolean);
		if(shun.length){ lines.push(`飞宫顺飞：${shun.join('、')}（阴阳遁皆顺）`); }
		if(o.feiMenZhongCan === false){ lines.push(`门层跳中：八门不入中宫${o.feiMenZhongShow ? '（中宫标「中」）' : ''}`); }
		const mixParts = [];
		if(o.mixTian){ mixParts.push(`天盘${o.mixTian === 'fei' ? '飞' : '转'}`); }
		if(o.mixXing){ mixParts.push(`九星${o.mixXing === 'fei' ? '飞' : '转'}`); }
		if(o.mixMen){ mixParts.push(`八门${o.mixMen === 'fei' ? '飞' : '转'}`); }
		if(o.mixShen){ mixParts.push(`九神${o.mixShen === 'fei' ? '飞' : '转'}`); }
		if(mixParts.length){ lines.push(`混合装配：${mixParts.join('、')}`); }
		// [H-E]
		if(o.kongMarkBoth){ lines.push('空亡标注：日空＋时空并标'); }
		// [H-F]
		if(o.dayJiaJuLabel && o.dayJiaJu && o.dayJiaJu !== 'yiyuan'){ lines.push(`日家定局：${o.dayJiaJuLabel}`); }
		if(o.yearJiaJu === 'yinian'){ lines.push(`年家定局：${o.yearJiaJuLabel}`); }
		if(o.shiftZhiFuMode === 'recalc'){ lines.push('移星值符：移后重定值符值使'); }
	})();
	if(pan.allKong){
		lines.push(`四柱空亡：年空${pan.allKong.年空}、月空${pan.allKong.月空}、日空${pan.allKong.日空}、时空${pan.allKong.时空}`);
	}
	if(pan.keIndex){
		lines.push(`刻序：本时辰第${pan.keIndex}刻${pan.keGanZhi ? `（刻柱${pan.keGanZhi}）` : ''}（十二分钟一局，${pan.options.keJiaFenDunLabel || '子后阳·午后阴'}）`);
	}
	if(pan.anGan){
		lines.push(`暗干：${pan.options.anGanModeLabel || ''}`);
		const parts = [];
		'坎坤震巽中乾兑艮离'.split('').forEach((gua)=>{
			if(pan.anGan[gua]){ parts.push(`${gua}${pan.anGan[gua]}${pan.anZhi && pan.anZhi[gua] ? pan.anZhi[gua] : ''}`); }
		});
		if(parts.length){ lines.push(`暗干分布：${parts.join('、')}`); }
	}
	if(pan.shuziInfo){
		lines.push(`阴盘起局：报数 ${pan.shuziInfo.digits}，各位求和 ${pan.shuziInfo.sum}，除9(余0作9)定局数；用神宫 ${pan.shuziInfo.gong} 宫（${pan.shuziInfo.gua}·${pan.shuziInfo.direction}）。阴阳遁按节气、局已据报数置换；阴盘奇门取数与余数映射各家有别，断盘侧重用神宫象意。`);
	}
	if(pan.school === '飞盘'){
		lines.push('飞盘体系：洛书飞布九星九门九神（含中宫），九神为符蛇阴合勾常雀地天。');
	} else if(pan.school === '混合'){
		lines.push('飞转混合：九星=排宫(转盘·星寄坤2不入中、天禽)，八门=飞宫(飞盘·可入中5)，九神=飞泊(含中宫)。');
	}
	lines.push(`空亡方式：${pan.options.kongModeLabel}`);
	lines.push(`驿马方式：${pan.options.yimaModeLabel}`);
	lines.push(`值符：${pan.zhiFu}`);
	lines.push(`值使：${pan.zhiShi}`);
	lines.push('');

	// [全局速览]：九遁/三奇得使/吉凶格品级 + 命事局，一眼看全局格局（与概览页「全局速览」同源）。
	const overview = buildQimenOverviewSummary(pan);
	if(overview){
		const catText = pan.options && pan.options.chartCategory === 'ming' ? '命局（日干＝内心 / 时干＝外在）' : '事局（日干＝实质 / 时干＝表象）';
		const posShort = (it)=>(it && it.palace ? `${it.palaceName}${LUOSHU_NUM[it.palaceName]}宫·${it.dir}` : '未现');
		const patShort = (arr)=>(arr && arr.length ? arr.slice(0, 3).map((x)=>`${x.name}(${x.palaceName}${x.palace})`).join('、') + (arr.length > 3 ? ` 等${arr.length}例` : '') : '无');
		lines.push('[全局速览]');
		lines.push(`盘类：${catText}`);
		lines.push(`九遁：${overview.dun.length ? overview.dun.map((d)=>`${d.name}(${d.palaceName}${d.palace})`).join('、') : '无'}`);
		lines.push(`三奇得使：${overview.sanQiDeshi ? posShort(overview.sanQiDeshi) : '无'}`);
		lines.push(`吉格 ${overview.ji.length} 例：${patShort(overview.ji)}`);
		lines.push(`凶格 ${overview.xiong.length} 例：${patShort(overview.xiong)}`);
		const harm = overview.sixHarm;
		const harmCount = harm.jiXing.length + harm.ruMu.length + harm.menPo.length + harm.kongWang.length + harm.gengHu.length;
		lines.push(`六害分布：${harmCount ? `击刑${harm.jiXing.length}·入墓${harm.ruMu.length}·门迫${harm.menPo.length}·空亡${harm.kongWang.length}·庚虎${harm.gengHu.length}` : '本局未现'}`);
		lines.push(`值符落宫：${posShort(overview.zhiFu)}（${overview.zhiFu.star || '—'}）　值使落宫：${posShort(overview.zhiShi)}（${overview.zhiShi.door || '—'}）`);
		lines.push('');
	}

	lines.push('[盘面要素]');
	lines.push(`符头：${pan.fuTou}`);
	lines.push(`地盘：${pan.diPanList.join(' ')}`);
	lines.push(`天盘：${pan.tianPanList.join(' ')}`);
	lines.push(`人盘：${pan.renPanList.join(' ')}`);
	lines.push(`神盘：${pan.shenPanList.join(' ')}`);
	lines.push(`六仪击刑：${joinList(pan.liuYiJiXing)}`);
	lines.push(`奇仪入墓：${joinList(pan.qiYiRuMu)}`);
	lines.push(`门迫：${joinList(pan.menPo && pan.menPo.list ? pan.menPo.list : [])}`);
	lines.push(`空亡宫：${joinList(pan.kongWangDesc)}`);
	lines.push(`${pan.yiMa ? pan.yiMa.text : '日马：无'}`);
	if(pan.shenSha && pan.shenSha.summary && pan.shenSha.summary.length){
		lines.push(`神煞概览：${pan.shenSha.summary.map((item)=>`${item.name}-${item.value}`).join('  ')}`);
	}
	lines.push('');

	const fushiYiGua = buildQimenFuShiYiGua(pan);
	lines.push('[奇门演卦]');
	lines.push(`值符值使演卦：${fushiYiGua.text || '无'}`);
	lines.push('门方演卦：见[八宫详解]各宫“奇门演卦（门方）”。');
	lines.push('');

	const bagongLines = buildQimenBaGongSnapshotLines(pan);
	if(bagongLines && bagongLines.length){
		lines.push(...bagongLines);
		lines.push('');
	}

	// [八宫克应] doctrine 段(默认关段:builder 恒产,导出层按设置控)——克应/主应释义原文,可独立于[八宫详解]勾选。
	const bagongKeYingLines = buildQimenBaGongKeYingSnapshotLines(pan);
	if(bagongKeYingLines && bagongKeYingLines.length){
		lines.push(...bagongKeYingLines);
		lines.push('');
	}

	lines.push('[九宫方盘]');
	// 九宫 → GFM 表:宫/天干/神/门/天星/地干(空位源即 —,逐字保留)。
	pushMdRows(lines, ['宫', '天干', '神', '门', '天星', '地干'], pan.cells.map((cell)=>[
		`${cell.palaceName}${LUOSHU_NUM[cell.palaceName]}宫`, cell.tianGan || '—', cell.god || '—', cell.door || '—', cell.tianXing || '—', cell.diGan || '—',
	]));

	// 旺相休囚死(§17.1):以月令五行定各符号能量,供「看旺衰」断盘——旺相则吉力大凶有挡,休囚死则吉力弱凶更凶。
	const wangShuai = buildQimenWangShuai(pan);
	if(wangShuai && wangShuai.monthElem){
		lines.push('');
		lines.push('[旺相休囚死·月令能量]');
		lines.push(`月令：${wangShuai.monthBranch}（${wangShuai.monthElem}令）。当令者旺、我生者相、生我者休、克我者囚、我克者死；旺相有力，休囚死无力。`);
		// 各宫 → GFM 表:宫/星/星五行/星旺衰/门/门五行/门旺衰/宫五行/宫旺衰(空位源即 —)。
		pushMdRows(lines, ['宫', '星', '星五行', '星旺衰', '门', '门五行', '门旺衰', '宫五行', '宫旺衰'], wangShuai.palaces.map((p)=>[
			`${p.palaceName}${LUOSHU_NUM[p.palaceName]}宫`, p.star || '—', p.starWuxing || '—', p.starWangShuai || '—', p.door || '—', p.doorWuxing || '—', p.doorWangShuai || '—', p.gongWuxing || '—', p.gongWangShuai || '—',
		]));
	}

	// —— 法奇门叠加层（六害 / 化解 / 八门化气大阵 / 用神分论 / 七要 / 孤辰寡宿）；全量输出供 AI 导出·挂载·储存 ——
	const fa = buildFaQimenAnalysis(pan, { faceToFace: true, chartCategory: pan.options && pan.options.chartCategory });
	if(fa){
		const posTxt = (it)=>(it && it.palaceNum ? `${it.palaceName}${LUOSHU_NUM[it.palaceName]}宫` : '未现');
		lines.push('');
		lines.push('[六害总览]');
		if(fa.dangers.length){
			lines.push('危害递减：击刑＞入墓＞庚＞白虎＞门迫＞空亡；天干＞一切，先解击刑天干。');
			// 六害 → GFM 表:危害/宫位/符号。
			pushMdRows(lines, ['危害', '宫位', '符号'], fa.dangers.map((d)=>[d.type, `${d.palaceName}${LUOSHU_NUM[d.palaceName]}宫(${d.direction})`, d.symbol]));
		}else{
			lines.push('本局四纲八宫未现六害。');
		}
		if(fa.panType.type){ lines.push(`盘型：${fa.panType.type}局——${fa.panType.text}`); }

		lines.push('');
		lines.push('[化解方案]');
		if(fa.jieHua.length){
			// 化解 → GFM 表:宫位/危害/天盘干/化解(灭象·布阵·时机·备注合并;还原时补回 「：」后单空格)。
			pushMdRows(lines, ['宫位', '危害', '天盘干', '化解'], fa.jieHua.map((j)=>{
				const dz = j.dangers.map((x)=>x.type).join('+');
				const mieTxt = j.mie.length ? ' 灭象：' + j.mie.join(' ') : '';
				const buTxt = j.placements.length ? ' 布阵：' + j.placements.map((p)=>p.where + p.text).join('；') : '';
				const shiTxt = ` 时机:本宫${j.benZhi || ''}日/${j.ben || ''} 对宫${j.duiZhi || ''}日/${j.dui || ''}`;
				const notesTxt = j.notes.length ? '｜' + j.notes.join(' ') : '';
				return [`${j.palaceName}${LUOSHU_NUM[j.palaceName]}宫·${j.direction}`, dz, j.tianGan, `${mieTxt}${buTxt}${shiTxt}${notesTxt}`.trim()];
			}));
		}else{
			lines.push('无需化解。');
		}

		lines.push('');
		lines.push('[八门化气大阵]');
		// 八门保护 → GFM 表:门/落宫/状态。
		pushMdRows(lines, ['门', '落宫', '状态'], fa.protect.map((r)=>[
			`${r.label}${r.gan ? '(' + r.gan + ')' : ''}`, r.palaceNum ? r.palaceName + LUOSHU_NUM[r.palaceName] + '宫·' + r.direction : '未现', r.hazards.length ? '[' + r.hazards.join('/') + ']' : '[平稳]',
		]));

		lines.push('');
		lines.push('[用神分论]');
		if(fa.yongShen){
			lines.push(fa.yongShen.yongShenText);
			lines.push(`日干:${fa.yongShen.dayGan.symbol}(${posTxt(fa.yongShen.dayGan)})　时干:${fa.yongShen.timeGan.symbol}(${posTxt(fa.yongShen.timeGan)})${fa.yongShen.ganHe ? '　干合/配偶:' + fa.yongShen.ganHe.symbol + '(' + posTxt(fa.yongShen.ganHe) + ')' : ''}`);
			lines.push(`符使:值符${posTxt(fa.yongShen.zhiFu)}/值使${posTxt(fa.yongShen.zhiShi)}`);
			lines.push(`六亲:${fa.yongShen.liuQin.map((r)=>r.rel.split('·')[1] + r.symbol + posTxt(r)).join(' ')}`);
		}

		lines.push('');
		lines.push('[财富七要]');
		if(fa.wealth){
			// 财富用神 → GFM 表:用神/落宫/危害(无危害 → —)。月令/干财为汇总散文,保持原样。
			pushMdRows(lines, ['用神', '落宫', '危害'], fa.wealth.items.map((it)=>[it.name, posTxt(it), it.hazards && it.hazards.length ? '[' + it.hazards.join('/') + ']' : '']));
			lines.push(`月令:${fa.wealth.month.zhi}(${fa.wealth.month.wuxing}) ${fa.wealth.month.relation}`);
			if(fa.wealth.ganCai.length){ lines.push(`干财:${fa.wealth.ganCai.map((c)=>c.src + c.symbol + posTxt(c)).join(' ')}`); }
		}

		lines.push('');
		lines.push('[事业七要]');
		if(fa.career){
			// 事业用神 → GFM 表:用神/落宫/危害(无危害 → —)。符使/诸干/行业取象为汇总散文,保持原样。
			pushMdRows(lines, ['用神', '落宫', '危害'], fa.career.items.map((it)=>[it.name, posTxt(it), it.hazards && it.hazards.length ? '[' + it.hazards.join('/') + ']' : '']));
			lines.push(`符使:${fa.career.fuShi.map((r)=>r.rel + posTxt(r)).join(' ')}`);
			lines.push(`诸干:${fa.career.zhuGan.map((r)=>r.rel.split('·')[1] + r.symbol + posTxt(r)).join(' ')}`);
			if(fa.career.industryHint){ lines.push(fa.career.industryHint); }
		}

		lines.push('');
		lines.push('[恋爱姻缘]');
		if(fa.romance){
			fa.romance.zhengYuan.forEach((z)=>lines.push(`${z.name}:${z.symbol || ''}${posTxt(z)}`));
			lines.push(`三奇桃花:${fa.romance.taoHua.sanQi.map((s)=>s.gan + posTxt(s)).join(' ')}`);
			lines.push(`沐浴位:${fa.romance.taoHua.muYu.zhi}(${fa.romance.taoHua.muYu.palaceNum ? fa.romance.taoHua.muYu.palaceName + LUOSHU_NUM[fa.romance.taoHua.muYu.palaceName] + '宫' : '—'})`);
			if(fa.romance.trouble.length){ lines.push(`情感不顺:${fa.romance.trouble.join(' ')}`); }
			if(fa.romance.zhanTaoHua){ lines.push(fa.romance.zhanTaoHua); }
		}

		lines.push('');
		lines.push('[孤辰寡宿]');
		lines.push(fa.guGua.length ? fa.guGua.map((g)=>`${g.name}(${g.zhi}):${g.jie}`).join('；') : '无');
	}

	return lines.join('\n');
}
