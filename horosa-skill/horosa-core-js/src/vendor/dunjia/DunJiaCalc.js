import * as LRConst from '../liureng/LRConst.js';
import { buildQimenBaGongSnapshotLines, buildQimenFuShiYiGua } from './DunJiaBaGongRules.js';

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

export const JIEQI_OPTIONS = [
	{ value: 0, label: '节气按天' },
	{ value: 1, label: '节气按分' },
];

export const PAIPAN_OPTIONS = [
	{ value: 0, label: '年家奇门' },
	{ value: 1, label: '月家奇门' },
	{ value: 2, label: '日家奇门' },
	{ value: 3, label: '时家奇门' },
];

export const ZHISHI_OPTIONS = [
	{ value: 0, label: '天禽值符-死门' },
	{ value: 1, label: '天禽值符-阴阳遁' },
	{ value: 2, label: '天禽值符-节气' },
];

export const YUEJIA_QIJU_OPTIONS = [
	{ value: 0, label: '月家起局-年支' },
	{ value: 1, label: '月家起局-符头地支' },
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

export const DAY_SWITCH_OPTIONS = [
	{ value: 1, label: '子初换日' },
	{ value: 0, label: '子正换日' },
];

export const QIJU_METHOD_OPTIONS = [
	{ value: 'zhirun', label: '置润' },
	{ value: 'chaibu', label: '拆补' },
];

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
	芮: '芮禽',
	禽: '芮禽',
	柱: '天柱',
	心: '天心',
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

const GUXU = {
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
	return one ? one.label : `${value}`;
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

function getXunHead(gz){
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

function calcYearJiaMeta(year){
	if(year >= 0 && year <= 3){
		return { sanYuan: '中元', juShu: 4, yinYangDun: '阴遁' };
	}
	const cycle = ((Math.floor((year - 4) / 60) % 3) + 3) % 3;
	if(cycle === 0){
		return { sanYuan: '下元', juShu: 7, yinYangDun: '阴遁' };
	}
	if(cycle === 1){
		return { sanYuan: '上元', juShu: 1, yinYangDun: '阴遁' };
	}
	return { sanYuan: '中元', juShu: 4, yinYangDun: '阴遁' };
}

function calcYueJiaMeta(ganzhi, yueJiaQiJuType){
	let zhi = getGanzhiZhi(ganzhi.year || '');
	if(normalizeNum(yueJiaQiJuType, 1) === 1){
		zhi = getGanzhiZhi(getXunHead(ganzhi.year || '甲子'));
	}
	if('寅申巳亥'.indexOf(zhi) >= 0){
		return { sanYuan: '上元', juShu: 1, yinYangDun: '阴遁' };
	}
	if('子午卯酉'.indexOf(zhi) >= 0){
		return { sanYuan: '中元', juShu: 7, yinYangDun: '阴遁' };
	}
	return { sanYuan: '下元', juShu: 4, yinYangDun: '阴遁' };
}

function calcDayJiaMeta(dateParts, dayGanZhi, jieqi){
	const dayDate = new Date(dateParts.year, dateParts.month - 1, dateParts.day);
	const firstDate = new Date(dateParts.year, 0, 1);
	const dayOfYear = Math.floor((dayDate.getTime() - firstDate.getTime()) / 86400000) + 1;
	let juShu = 6;
	if(dayOfYear <= 60){
		juShu = 1;
	}else if(dayOfYear <= 120){
		juShu = 7;
	}else if(dayOfYear <= 180){
		juShu = 4;
	}else if(dayOfYear <= 240){
		juShu = 9;
	}else if(dayOfYear <= 300){
		juShu = 3;
	}
	return {
		sanYuan: findYuan(dayGanZhi),
		juShu,
		yinYangDun: isYangDunJieqi(jieqi) ? '阳遁' : '阴遁',
	};
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
	return method === 'zhirun' ? 'zhirun' : 'chaibu';
}

function resolvePaiPanMeta(opts, ganzhi, jieqi, dateParts, context){
	const paiPanType = normalizeNum(opts && opts.paiPanType, 3);
	if(paiPanType === 0){
		return calcYearJiaMeta(dateParts.year);
	}
	if(paiPanType === 1){
		return calcYueJiaMeta(ganzhi, opts && opts.yueJiaQiJuType);
	}
	if(paiPanType === 2){
		return calcDayJiaMeta(dateParts, ganzhi.day, jieqi);
	}
	const base = calcShiJiaMeta(ganzhi.day, jieqi);
	if(normalizeQijuMethod(opts && opts.qijuMethod) === 'zhirun'){
		const qmju = qimenJuNameZhirun(
			dateParts,
			ganzhi.day,
			context && context.jieqiYearSeeds ? context.jieqiYearSeeds : {},
			jieqi,
			opts && opts.after23NewDay
		);
		const parsed = parseQmju(qmju);
		return {
			sanYuan: parsed.yuan,
			juShu: CNUMBER.indexOf(parsed.kook) + 1,
			yinYangDun: parsed.yy === '阴' ? '阴遁' : '阳遁',
			qmju,
		};
	}
	const qmju = qimenJuNameChaibu(jieqi, ganzhi.day);
	const parsed = parseQmju(qmju);
	return {
		sanYuan: parsed.yuan,
		juShu: CNUMBER.indexOf(parsed.kook) + 1,
		yinYangDun: parsed.yy === '阴' ? '阴遁' : '阳遁',
		qmju,
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
	if(calcDateTime.hour === 23 && !!(opts && opts.after23NewDay)){
		day = nextGanZhi(day);
	}
	const preciseTime = normalizeGanZhi(
		(bazi && bazi.time && bazi.time.ganzi)
		|| (nongli ? nongli.time : '')
	);
	const computedTime = getHourGanZhi(day, calcDateTime.hour);
	const time = normalizeTimeAlg(opts && opts.timeAlg) === 0
		? (computedTime || preciseTime)
		: (preciseTime || computedTime);
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

function panGod(ganzhi, qmju){
	const zfzs = zhifuNZhishi(ganzhi, qmju);
	const meta = parseQmju(qmju);
	const startingGong = zfzs.值符星宫[1];
	const rotate = meta.yy === '阳' ? CLOCKWISE_EIGHTGUA : [...CLOCKWISE_EIGHTGUA].reverse();
	const gongReorder = startingGong === '中' ? newList(rotate, '坤') : newList(rotate, startingGong);
	const vals = (meta.yy === '阳' ? '符蛇阴合勾雀地天' : '符蛇阴合虎玄地天').split('');
	const out = zipToMap(gongReorder, vals);
	Object.keys(out).forEach((k)=>{
		out[k] = out[k].replace(/勾/g, '虎').replace(/雀/g, '玄');
	});
	return out;
}

function panDoor(ganzhi, qmju){
	const zfzs = zhifuNZhishi(ganzhi, qmju);
	const meta = parseQmju(qmju);
	const startingDoor = zfzs.值使门宫[0];
	const startingGong = zfzs.值使门宫[1];
	const rotate = meta.yy === '阳' ? CLOCKWISE_EIGHTGUA : [...CLOCKWISE_EIGHTGUA].reverse();
	const gongReorder = startingGong === '中' ? newList(rotate, '坤') : newList(rotate, startingGong);
	const yydoor = meta.yy === '阳' ? newList(DOOR_R, startingDoor) : newList([...DOOR_R].reverse(), startingDoor);
	return zipToMap(gongReorder, yydoor);
}

function panStar(ganzhi, qmju){
	const zfzs = zhifuNZhishi(ganzhi, qmju);
	const meta = parseQmju(qmju);
	const startingStar = zfzs.值符星宫[0].replace(/芮/g, '禽');
	const startingGong = zfzs.值符星宫[1];
	const rotate = meta.yy === '阳' ? CLOCKWISE_EIGHTGUA : [...CLOCKWISE_EIGHTGUA].reverse();
	const stars = meta.yy === '阳' ? newList(STAR_R, startingStar) : newList([...STAR_R].reverse(), startingStar);
	const gongReorder = startingGong === '中' ? newList(rotate, '坤') : newList(rotate, startingGong);
	const out = zipToMap(gongReorder, stars);
	Object.keys(out).forEach((k)=>{
		out[k] = out[k].replace(/禽/g, '芮');
	});
	return out;
}

function panSky(ganzhi, qmju){
	const meta = parseQmju(qmju);
	const rotate = meta.yy === '阳' ? CLOCKWISE_EIGHTGUA : [...CLOCKWISE_EIGHTGUA].reverse();
	const earth = panEarth(qmju);
	const earthR = invertMap(earth);
	const zfzs = zhifuNZhishi(ganzhi, qmju);
	const fuHead = JJ[getXunHead(ganzhi.time)] || '戊';
	const fuLocation = earthR[ganzhi.time.substring(0, 1)];
	const fuHeadLocation = zfzs.值符星宫[1];
	const fuHeadLocation2 = earthR[fuHead];
	const ganHead = zfzs.值符天干[1];
	const zhifu = zfzs.值符星宫[0].replace(/芮/g, '禽');

	let a = rotate.map((g)=>earth[g]);
	let startGong = fuHeadLocation === '中' ? '坤' : fuHeadLocation;
	if(startGong !== '坤' && rotate.indexOf(startGong) < 0){
		startGong = '坤';
	}
	let startGan = fuHead;
	if(a.indexOf(startGan) < 0){
		startGan = ganHead && a.indexOf(ganHead) >= 0 ? ganHead : earth[startGong];
	}

	if(fuHeadLocation !== '中' && zhifu !== '禽' && fuHeadLocation2 === '中'){
		startGan = earth[startGong] || startGan;
	}
	if(fuLocation === undefined || fuLocation === null){
		startGan = earth[startGong] || startGan;
	}

	const ganReorder = newList(a, startGan);
	const gongReorder = newList(rotate, startGong);
	const out = zipToMap(gongReorder, ganReorder);
	out.中 = earth.中;
	return out;
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
	const a = kongWang.substring(0, 1);
	const b = kongWang.substring(1, 2);
	[a, b].forEach((zhi)=>{
		const pos = BRANCH_TO_POS[zhi];
		if(pos && palaces.indexOf(pos) < 0){
			palaces.push(pos);
			list.push(`${PALACE_NAME[pos]}${pos}宫空亡`);
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
		text: palace ? `${mode === 'time' ? '时马' : '日马'}：${yimaZhi}（${PALACE_NAME[palace]}${palace}宫）` : `${mode === 'time' ? '时马' : '日马'}：无`,
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
			liuYi.push(`${gan}击刑（${PALACE_NAME[i]}${i}宫）`);
		}
		if(gan && ruRule && ruRule.indexOf(gan) >= 0){
			ruMuSet.add(i);
			ruMu.push(`${gan}入墓（${PALACE_NAME[i]}${i}宫）`);
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
			list.push(`${head}门迫（${PALACE_NAME[i]}${i}宫）`);
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
		god: shen[palaceNum] || '',
		tianGan: tianPan[palaceNum] || '',
		isCenter: palaceNum === 5,
		isZhiFu: palaceNum === zhiFuPalace,
		isZhiShi: palaceNum === zhiShiPalace,
		hasJiXing: jiXingSet.has(palaceNum),
		hasRuMu: ruMuSet.has(palaceNum),
		hasMenPo: menPoSet.has(palaceNum),
		hasKongWang: kongSet.has(palaceNum),
		isYiMa: palaceNum === yimaPalace,
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

function buildYinyangdunMap(year, yearSeeds){
	const prev = yearSeeds ? yearSeeds[year - 1] : null;
	const curr = yearSeeds ? yearSeeds[year] : null;
	if(!prev || !curr || !prev.大雪 || !curr.芒种 || !curr.大雪){
		return null;
	}
	const seedSig = [
		year,
		prev.大雪.dateKey || '',
		prev.大雪.dayGanzhi || '',
		curr.芒种.dateKey || '',
		curr.芒种.dayGanzhi || '',
		curr.大雪.dateKey || '',
		curr.大雪.dayGanzhi || '',
	].join('|');
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

	let jieqiCur = '冬至';
	if(daxueIndex - futouIndex >= 9){
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

	const mangzhongStartDay = keyToUtcDay(curr.芒种.dateKey);
	jieqiCur = '夏至';
	if(Number.isFinite(mangzhongStartDay) && mangzhongDay !== null && mangzhongStartDay > mangzhongDay + 9){
		jieqiCur = '芒种';
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

	const daxueStartDay = keyToUtcDay(curr.大雪.dateKey);
	jieqiCur = '冬至';
	if(Number.isFinite(daxueStartDay) && daxueDay !== null && daxueStartDay > daxueDay + 9){
		jieqiCur = '大雪';
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

function qimenJuNameZhirun(dateParts, dayGanzhi, yearSeeds, fallbackJieqi, after23NewDay){
	const yyd = buildYinyangdunMap(dateParts.year, yearSeeds);
	if(!yyd){
		return qimenJuNameChaibu(fallbackJieqi || '', dayGanzhi);
	}
	let dkey = `${dateParts.year}${`${dateParts.month}`.padStart(2, '0')}${`${dateParts.day}`.padStart(2, '0')}`;
	if(dateParts.hour === 23 && !!after23NewDay){
		dkey = utcDayToKey(keyToUtcDay(dkey) + 1);
	}
	const jqrz = yyd[dkey];
	if(!jqrz || jqrz.length < 4){
		return qimenJuNameChaibu(fallbackJieqi || '', dayGanzhi);
	}
	const jieqi = jqrz.substring(0, 2);
	const rizhu = jqrz.substring(2, 4);
	const idx = getGanzhiIndex(rizhu);
	const futou = Math.floor(idx / 15) * 15;
	const yuanId = Math.floor((idx - futou) / 5);
	const yuan = ['上元', '中元', '下元'][yuanId] || '上元';
	const code = JIEQI2JU[jieqi] || '一七四阳';
	const yy = code.substring(code.length - 1);
	return `${yy}遁${code.substring(yuanId, yuanId + 1)}局${yuan}`;
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

export function calcDunJia(fields, nongli, options, context){
	const dateParts = parseDateTime(fields);
	if(!dateParts){
		return null;
	}
	const opts = {
		qijuMethod: 'zhirun',
		kongMode: 'day',
		yimaMode: 'day',
		timeAlg: 0,
		shiftPalace: 0,
		after23NewDay: 1,
		fengJu: false,
		...(options || {}),
	};
	opts.qijuMethod = normalizeQijuMethod(opts.qijuMethod);
	opts.timeAlg = normalizeTimeAlg(opts.timeAlg);
	const shiftPalace = normalizeShiftPalace(opts.shiftPalace);

	const ganzhi = buildGanzhiForQimen(nongli || {}, dateParts, opts, context || {});
	const jieqi = getCurrentJieqi(nongli || {});
	const paiPanMeta = resolvePaiPanMeta(opts, ganzhi, jieqi, dateParts, context || {});
	const qmju = paiPanMeta.qmju || buildQmjuByMeta(paiPanMeta.yinYangDun, paiPanMeta.juShu, paiPanMeta.sanYuan);
	const zfzs = zhifuNZhishi(ganzhi, qmju, {
		zhiShiType: opts.zhiShiType,
		yinYangDun: paiPanMeta.yinYangDun,
		jieqi,
	});
	const dipanGua = panEarth(qmju);
	const tianpanGua = panSky(ganzhi, qmju);
	const menGua = panDoor(ganzhi, qmju);
	const starGua = panStar(ganzhi, qmju);
	const shenGua = panGod(ganzhi, qmju);
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

	const specials = resolveSpecials(tianPan);
	const menPo = resolveMenPo(men);
	const kongWang = getKongByMode(opts.kongMode, xunkong);
	const kongWangMeta = resolveKongWangPalaces(kongWang);
	const yiMaMeta = resolveYiMa(opts.yimaMode, ganzhi);
	const isDiurnal = context && context.isDiurnal !== undefined && context.isDiurnal !== null
		? !!context.isDiurnal
		: (nongli && nongli.isDiurnal !== undefined && nongli.isDiurnal !== null ? !!nongli.isDiurnal : null);

	const zhiFuPalace = rotateOuterPalaceNum(GUA_POS_MAP[zfzs.值符星宫[1]] || 5, shiftPalace);
	const zhiShiPalace = rotateOuterPalaceNum(GUA_POS_MAP[zfzs.值使门宫[1]] || 5, shiftPalace);
	let zhiFu = JIU_XING_NAME[(zfzs.值符星宫[0] || '').replace(/禽/g, '芮')] || `${(zfzs.值符星宫[0] || '').replace(/禽/g, '芮')}`;
	if((zfzs.值符星宫[0] || '') === '禽'){
		zhiFu = '天禽';
	}
	const zhiShi = BA_MEN_NAME[zfzs.值使门宫[0]] || `${zfzs.值使门宫[0]}门`;

	const cells = buildCells(diPan, tianPan, men, shen, star, zhiFuPalace, zhiShiPalace, {
		jiXingPalaces: specials.jiXingPalaces,
		ruMuPalaces: specials.ruMuPalaces,
		menPoPalaces: menPo.palaces,
		kongWangPalaces: kongWangMeta.palaces,
		yimaPalace: yiMaMeta.palace,
	});

	const qmjuMeta = parseQmju(qmju);

	return {
		dateStr: dateParts.dateStr,
		timeStr: dateParts.timeStr,
		realSunTime: (context && context.displaySolarTime) || (nongli ? (nongli.birth || '') : ''),
		lunarText: nongli ? `${nongli.year || ''}年${nongli.leap ? '闰' : ''}${nongli.month || ''}${nongli.day || ''}` : '',
		jiedelta: nongli ? (nongli.jiedelta || '') : '',
		ganzhi,
		fuTou: resolveFuTouByBacktrack(ganzhi.day),
		jieqiText: `${jieqi || '未知节气'}${paiPanMeta.sanYuan || qmjuMeta.yuan}`,
		yinYangDun: paiPanMeta.yinYangDun || (qmjuMeta.yy === '阴' ? '阴遁' : '阳遁'),
		sanYuan: paiPanMeta.sanYuan || qmjuMeta.yuan,
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
			zhiShiLabel: getOptionLabel(ZHISHI_OPTIONS, opts.zhiShiType),
			yueJiaLabel: getOptionLabel(YUEJIA_QIJU_OPTIONS, opts.yueJiaQiJuType),
			yearLabel: getOptionLabel(YEAR_GZ_OPTIONS, opts.yearGanZhiType),
			monthLabel: getOptionLabel(MONTH_GZ_OPTIONS, opts.monthGanZhiType),
			dayLabel: getOptionLabel(DAY_GZ_OPTIONS, opts.dayGanZhiType),
			daySwitchLabel: getOptionLabel(DAY_SWITCH_OPTIONS, opts.after23NewDay),
			qijuMethodLabel: getOptionLabel(QIJU_METHOD_OPTIONS, opts.qijuMethod),
			kongModeLabel: getOptionLabel(KONG_MODE_OPTIONS, opts.kongMode),
			yimaModeLabel: getOptionLabel(MA_MODE_OPTIONS, opts.yimaMode),
			timeAlgLabel: getTimeAlgLabel(opts.timeAlg),
			shiftLabel: getOptionLabel(YIXING_OPTIONS, shiftPalace),
			fengJuLabel: opts.fengJu ? '已封局' : '未封局',
		},
	};
}

export function buildDunJiaSnapshotText(pan){
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
	lines.push(`命式：${pan.options.sexLabel}`);
	lines.push(`移星：${pan.options.shiftLabel || '原宫'}`);
	lines.push(`奇门封局：${pan.options.fengJuLabel || (pan.fengJu ? '已封局' : '未封局')}`);
	lines.push(`换日：${pan.options.daySwitchLabel || '子初换日'}`);
	lines.push(`时间算法：${timeAlgLabel}`);
	lines.push(`节气：${pan.jieqiText}`);
	lines.push(`局数：${pan.juText}`);
	lines.push(`起局法：${pan.options.qijuMethodLabel}`);
	lines.push(`空亡方式：${pan.options.kongModeLabel}`);
	lines.push(`驿马方式：${pan.options.yimaModeLabel}`);
	lines.push(`值符：${pan.zhiFu}`);
	lines.push(`值使：${pan.zhiShi}`);
	lines.push('');

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

	lines.push('[九宫方盘]');
	pan.cells.forEach((cell)=>{
		lines.push(`${cell.palaceName}${cell.palaceNum}宫：${cell.tianGan || '—'} ${cell.god || '—'} ${cell.door || '—'} ${cell.tianXing || '—'} ${cell.diGan || '—'}`);
	});

	return lines.join('\n');
}
