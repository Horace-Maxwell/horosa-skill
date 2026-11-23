// 奇门基础常量表(干支 / 节气 / 八卦九宫 / 星门神 / 五行旺衰 / 神煞查表)与旺衰、数字用神
// 从 DunJiaCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { Solar } from 'lunar-javascript';
import { scriptWordAttrs } from '../../utils/scriptMode.js';

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

export const GAN = '甲乙丙丁戊己庚辛壬癸'.split('');

export const ZHI = '子丑寅卯辰巳午未申酉戌亥'.split('');

export const JIAZI = Array.from({ length: 60 }, (_, i)=>`${GAN[i % 10]}${ZHI[i % 12]}`);

export const GANZHI_INDEX_MAP = JIAZI.reduce((mapObj, item, idx)=>{
	mapObj[item] = idx;
	return mapObj;
}, {});

export const YINYANGDUN_CACHE = new Map();

export const MAX_YINYANGDUN_CACHE = 24;

export const XUN_HEADS = JIAZI.filter((_, idx)=>idx % 10 === 0);

const SAN_YUAN_FU_TOU = ['甲子', '甲午', '甲寅', '甲申', '甲辰', '甲戌', '己卯', '己酉', '己巳', '己亥', '己丑', '己未'];

export const SAN_YUAN_FU_TOU_SET = new Set(SAN_YUAN_FU_TOU);

export const CNUMBER = '一二三四五六七八九'.split('');

export const EIGHT_GUA = '坎坤震巽中乾兑艮离'.split('');

export const CLOCKWISE_EIGHTGUA = '坎艮震巽离坤兑乾'.split('');

export const DOOR_R = '休生伤杜景死惊开'.split('');

export const STAR_R = '蓬任冲辅英禽柱心'.split('');

export const JIU_XING = '蓬芮冲辅禽心柱任英'.split('');

export const JIEQI_NAME = '春分清明谷雨立夏小满芒种夏至小暑大暑立秋处暑白露秋分寒露霜降立冬小雪大雪冬至小寒大寒立春雨水惊蛰'.match(/../g);

export const YANG_JIEQI = newList(JIEQI_NAME, '冬至').slice(0, 12);

export const JJ = {
	甲子: '戊',
	甲戌: '己',
	甲申: '庚',
	甲午: '辛',
	甲辰: '壬',
	甲寅: '癸',
};

export const JIEQI2JU = {
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

export const JIEQI_CODE = {
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

export const ZHISHI_BY_JIEQI = [
	{ list: ['冬至', '小寒', '大寒'], door: '休' },
	{ list: ['立春', '雨水', '惊蛰'], door: '生' },
	{ list: ['春分', '清明', '谷雨'], door: '伤' },
	{ list: ['立夏', '小满', '芒种'], door: '杜' },
	{ list: ['夏至', '小暑', '大暑'], door: '景' },
	{ list: ['立秋', '处暑', '白露'], door: '死' },
	{ list: ['秋分', '寒露', '霜降'], door: '惊' },
	{ list: ['立冬', '小雪', '大雪'], door: '开' },
];

export const GUA_POS_MAP = {
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

export const POS_GUA_MAP = {
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

export const BRANCH_TO_POS = {
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

export const JIU_XING_NAME = {
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

export const BA_MEN_NAME = {
	休: '休门',
	生: '生门',
	伤: '伤门',
	杜: '杜门',
	景: '景门',
	死: '死门',
	惊: '惊门',
	开: '开门',
};

// 盘格里单字画的九星 / 八门(「冲」「伤」…):界面简繁按全名定字(单字「冲」缺省作「沖」,全名「天冲」作「天衝」,
// 同一颗星两种写法)。返回挂到该字节点上的整词属性;不是单字九星 / 八门返回 {}。奇门盘与三式合一盘同用。
export function qimenGlyphScriptAttrs(type, text){
	const t = `${text === undefined || text === null ? '' : text}`.trim();
	if(Array.from(t).length !== 1){ return {}; }
	const full = type === 'star' ? JIU_XING_NAME[t] : (type === 'door' ? BA_MEN_NAME[t] : '');
	return full ? scriptWordAttrs(full, Array.from(full).indexOf(t)) : {};
}

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

export const PALACE_GRID = [1, 2, 3, 4, 5, 6, 7, 8, 9];

export const PALACE_NAME = {
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

export const OUTER_RING_CLOCKWISE = [1, 2, 3, 6, 9, 8, 7, 4];

// 十干五合(甲己/乙庚/丙辛/丁壬/戊癸)——盘面每宫中位注记(DunJiaBoard)与快照 [盘面要素] 同源单表。
export const QIMEN_WU_HE = {
	甲: '己', 乙: '庚', 丙: '辛', 丁: '壬', 戊: '癸',
	己: '甲', 庚: '乙', 辛: '丙', 壬: '丁', 癸: '戊',
};

export const JI_XING_RULE = {
	1: '壬癸',
	2: '辛',
	3: '己',
	4: '戊',
	7: '庚',
};

export const RU_MU_RULE = {
	1: '辛壬',
	3: '甲癸',
	7: '丁己庚',
	9: '乙丙戊',
};

export const MEN_PO_RULE = {
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
export const QIMEN_SHENSHA_DAY_STEMS = {
	日禄: { 甲: ['寅'], 乙: ['卯'], 丙: ['巳'], 丁: ['午'], 戊: ['巳'], 己: ['午'], 庚: ['申'], 辛: ['酉'], 壬: ['亥'], 癸: ['子'] },
	日德: { 甲: ['寅'], 乙: ['申'], 丙: ['巳'], 丁: ['亥'], 戊: ['巳'], 己: ['寅'], 庚: ['申'], 辛: ['巳'], 壬: ['亥'], 癸: ['巳'] },
	文昌: { 甲: ['巳'], 乙: ['午'], 丙: ['申'], 丁: ['酉'], 戊: ['申'], 己: ['酉'], 庚: ['亥'], 辛: ['子'], 壬: ['寅'], 癸: ['卯'] },
	游都: { 甲: ['丑'], 乙: ['子'], 丙: ['寅'], 丁: ['巳'], 戊: ['申'], 己: ['丑'], 庚: ['子'], 辛: ['寅'], 壬: ['巳'], 癸: ['申'] },
};

export const QIMEN_GUIREN_DAY_NIGHT = {
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

export const QIMEN_SHENSHA_DAY_BRANCH = {
	驿马: { 子: ['寅'], 丑: ['亥'], 寅: ['申'], 卯: ['巳'], 辰: ['寅'], 巳: ['亥'], 午: ['申'], 未: ['巳'], 申: ['寅'], 酉: ['亥'], 戌: ['申'], 亥: ['巳'] },
	日马: { 子: ['寅'], 丑: ['亥'], 寅: ['申'], 卯: ['巳'], 辰: ['寅'], 巳: ['亥'], 午: ['申'], 未: ['巳'], 申: ['寅'], 酉: ['亥'], 戌: ['申'], 亥: ['巳'] },
	桃花: { 子: ['酉'], 丑: ['午'], 寅: ['卯'], 卯: ['子'], 辰: ['酉'], 巳: ['午'], 午: ['卯'], 未: ['子'], 申: ['酉'], 酉: ['午'], 戌: ['卯'], 亥: ['子'] },
	破碎: { 子: ['巳'], 丑: ['丑'], 寅: ['酉'], 卯: ['巳'], 辰: ['丑'], 巳: ['酉'], 午: ['巳'], 未: ['丑'], 申: ['酉'], 酉: ['巳'], 戌: ['丑'], 亥: ['酉'] },
};

export const QIMEN_SHENSHA_MONTH_BRANCH = {
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

export const QIMEN_SHENSHA_YEAR_BRANCH = {
	年马: { 子: ['寅'], 丑: ['亥'], 寅: ['申'], 卯: ['巳'], 辰: ['寅'], 巳: ['亥'], 午: ['申'], 未: ['巳'], 申: ['寅'], 酉: ['亥'], 戌: ['申'], 亥: ['巳'] },
	病符: { 子: ['亥'], 丑: ['子'], 寅: ['丑'], 卯: ['寅'], 辰: ['卯'], 巳: ['辰'], 午: ['巳'], 未: ['午'], 申: ['未'], 酉: ['申'], 戌: ['酉'], 亥: ['戌'] },
	孤辰: { 子: ['寅'], 丑: ['寅'], 寅: ['巳'], 卯: ['巳'], 辰: ['巳'], 巳: ['申'], 午: ['申'], 未: ['申'], 申: ['亥'], 酉: ['亥'], 戌: ['亥'], 亥: ['寅'] },
	寡宿: { 子: ['戌'], 丑: ['戌'], 寅: ['丑'], 卯: ['丑'], 辰: ['丑'], 巳: ['辰'], 午: ['辰'], 未: ['辰'], 申: ['未'], 酉: ['未'], 戌: ['未'], 亥: ['戌'] },
	丧门: { 子: ['寅'], 丑: ['卯'], 寅: ['辰'], 卯: ['巳'], 辰: ['午'], 巳: ['未'], 午: ['申'], 未: ['酉'], 申: ['戌'], 酉: ['亥'], 戌: ['子'], 亥: ['丑'] },
	吊客: { 子: ['戌'], 丑: ['亥'], 寅: ['子'], 卯: ['丑'], 辰: ['寅'], 巳: ['卯'], 午: ['辰'], 未: ['巳'], 申: ['午'], 酉: ['未'], 戌: ['申'], 亥: ['酉'] },
};

export function newList(list, start){
	const idx = list.indexOf(start);
	if(idx < 0){
		throw new Error(`start.not.found:${start}`);
	}
	return [...list.slice(idx), ...list.slice(0, idx)];
}

export function newListR(list, start){
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

export function zipToMap(keys, vals){
	const out = {};
	for(let i=0; i<keys.length; i++){
		out[keys[i]] = vals[i];
	}
	return out;
}

export function invertMap(mapObj){
	const out = {};
	Object.keys(mapObj || {}).forEach((k)=>{
		out[mapObj[k]] = k;
	});
	return out;
}
