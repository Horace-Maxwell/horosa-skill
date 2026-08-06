import {
	TAIYI_STYLE_OPTIONS,
	TAIYI_ACCUM_OPTIONS,
	calcTaiyiPanFromKintaiyi,
	buildTaiyiSnapshotLines,
	getTaiyiStyleLabel,
	getTaiyiAccumLabel,
} from './core/TaiYiCore.js';




import buildLocalBaziResult from '../bazi/baziLunarLocal.js';

import { parseDateParts } from '../bazi/dateStrSafe.js';

export const STYLE_OPTIONS = [
	...TAIYI_STYLE_OPTIONS.slice(),
	{ value: 5, label: '太乙命法' },
];

export const ACCUM_OPTIONS = TAIYI_ACCUM_OPTIONS.slice();
export const METHOD_OPTIONS = ACCUM_OPTIONS;
export const METHOD_SOURCE_OPTIONS = [
	{ value: 0, source: '《太乙統宗寶鑑》' },
	{ value: 1, source: '《太乙金鏡式經》' },
	{ value: 2, source: '《太乙淘金歌》' },
	{ value: 3, source: '《太乙局》' },
];

export const TENCHING_OPTIONS = [
	{ value: 0, label: '無' },
	{ value: 1, label: '有' },
];

export const SEX_OPTIONS = [
	{ value: '男', label: '男' },
	{ value: '女', label: '女' },
];

export const ROTATION_OPTIONS = [
	{ value: '固定', label: '固定' },
	{ value: '轉動', label: '轉動' },
];

export const TIME_BASIS_OPTIONS = [
	{ value: 'direct', label: '直接时间' },
	{ value: 'trueSolar', label: '真太阳时' },
];

// 用户语义(拍板,字面直觉版): after23NewDay=1「23点算第二天」=日柱进位次日(壬寅)；=0「24点算第二天」=日柱守今(辛丑)。
export const DAY_SWITCH_OPTIONS = [
	{ value: 1, label: '23点算第二天' },
	{ value: 0, label: '24点算第二天' },
];


export const GAME_THEORY_OPTIONS = [
	{ value: 0, label: '关闭' },
	{ value: 1, label: '开启' },
];

const PALACE_ORDER = ['巽', '巳', '午', '未', '坤', '申', '酉', '戌', '乾', '亥', '子', '丑', '艮', '寅', '卯', '辰'];

function normalizePalaces(palace16){
	const map = {};
	PALACE_ORDER.forEach((palace)=>{
		map[palace] = [];
	});
	(palace16 || []).forEach((item)=>{
		if(!item || !item.palace || !map[item.palace]){
			return;
		}
		map[item.palace] = Array.isArray(item.items) ? item.items.slice(0) : [];
	});
	return PALACE_ORDER.map((palace)=>({
		palace,
		items: map[palace],
	}));
}

function buildOptions(opt, pan){
	const options = opt || {};
	const style = options.style !== undefined ? options.style : (pan ? pan.style : 3);
	const isLifeStyle = style === 5;
	const tn = pan && pan.tnForPan !== undefined ? pan.tnForPan : (options.tn !== undefined ? options.tn : 0);
	const methodLabel = isLifeStyle ? '命法不适用' : getMethodLabel(tn);
	const methodSource = isLifeStyle ? '命法不适用' : getMethodSource(tn);
	return {
		styleLabel: getStyleLabel(style),
		methodLabel,
		methodSource,
		accumLabel: methodLabel,
		tenchingLabel: options.tenching === 1 ? '有' : '无',
		sexLabel: options.sex || (pan && pan.sex) || '男',
		rotationLabel: options.rotation || '固定',
		timeBasisLabel: options.timeBasis === 'trueSolar' ? '真太阳时' : '直接时间',
		daySwitchLabel: options.after23NewDay === 1 ? '23点算第二天' : '24点算第二天',
		gameTheoryLabel: options.gameTheory === 1 ? '开启' : '关闭',
	};
}

function safeText(value){
	return value === undefined || value === null ? '' : `${value}`;
}

function formatNongliText(nongli){
	if(!nongli){
		return '';
	}
	const year = safeText(nongli.year);
	const leap = nongli.leap ? '闰' : '';
	const month = safeText(nongli.month);
	const day = safeText(nongli.day);
	return `${year ? `${year}年` : ''}${leap}${month}${day}`.trim();
}

function pickPillar(nongli, key, flatKey){
	if(!nongli){
		return '';
	}
	const flat = safeText(nongli[flatKey]);
	if(flat){
		return flat;
	}
	const four = nongli.bazi && nongli.bazi.fourColumns ? nongli.bazi.fourColumns : null;
	const item = four && four[key] ? four[key] : null;
	return safeText((item && (item.ganzi || item.ganZhi || item.text)) || '');
}

function pillarFromFourColumns(four, key){
	const item = four && four[key] ? four[key] : null;
	return safeText((item && (item.ganzi || item.ganZhi || item.text)) || '');
}

function buildTaiyiBaziLocal(fields, options){
	if(!fields || !fields.date || !fields.time){
		return null;
	}
	try{
		return buildLocalBaziResult({
			date: fields.date.value.format('YYYY-MM-DD'),
			time: fields.time.value.format('HH:mm:ss'),
			zone: fields.zone ? fields.zone.value : undefined,
			lon: fields.lon ? fields.lon.value : undefined,
			lat: fields.lat ? fields.lat.value : undefined,
			gpsLat: fields.gpsLat ? fields.gpsLat.value : undefined,
			gpsLon: fields.gpsLon ? fields.gpsLon.value : undefined,
			gender: fields.gender ? fields.gender.value : 1,
			timeAlg: options && options.timeBasis === 'trueSolar' ? 0 : 1,
			after23NewDay: options ? options.after23NewDay : undefined,
			// v2.2.1: 太乙也要把时柱开关透传给 buildLocalBaziResult,否则 hour==23 + lateZi=0 时太乙的时柱会算错。
			lateZiHourUseNextDay: options ? options.lateZiHourUseNextDay : undefined,
		});
	}catch(e){
		return null;
	}
}

function applyNongliDisplay(pan, nongli, baziLocal){
	if(!pan || (!nongli && !baziLocal)){
		return pan;
	}
	const baziNongli = baziLocal && baziLocal.bazi ? baziLocal.bazi.nongli : null;
	const four = baziLocal && baziLocal.bazi && baziLocal.bazi.fourColumns ? baziLocal.bazi.fourColumns : null;
	return {
		...pan,
		lunarText: (nongli && formatNongliText(nongli)) || pan.lunarText,
		// 真太阳时 与 直接时间 都稳定显示(与所选时间基准无关);随基准变的只是四柱/计算基准 —— 和八字一致
		realSunTime: (baziNongli && safeText(baziNongli.solarTime)) || (nongli && safeText(nongli.birth)) || pan.realSunTime,
		clockTime: (baziNongli && safeText(baziNongli.clockTime)) || pan.clockTime,
		jiedelta: (nongli && safeText(nongli.jiedelta)) || pan.jiedelta,
		ganzhi: {
			year: pillarFromFourColumns(four, 'year') || pickPillar(nongli, 'year', 'yearGanZi') || (pan.ganzhi && pan.ganzhi.year) || '',
			month: pillarFromFourColumns(four, 'month') || pickPillar(nongli, 'month', 'monthGanZi') || (pan.ganzhi && pan.ganzhi.month) || '',
			day: pillarFromFourColumns(four, 'day') || pickPillar(nongli, 'day', 'dayGanZi') || (pan.ganzhi && pan.ganzhi.day) || '',
			time: pillarFromFourColumns(four, 'time') || pickPillar(nongli, 'time', 'timeGanZi') || (nongli && safeText(nongli.time)) || (pan.ganzhi && pan.ganzhi.time) || '',
			minute: (pan.ganzhi && pan.ganzhi.minute) || '',
		},
	};
}

export function calcTaiyi(fields, nongli, options){
	const opt = options || {};
	const pan = calcTaiyiPanFromKintaiyi(fields, nongli, opt);
	if(!pan){
		return null;
	}
	const baziLocal = buildTaiyiBaziLocal(fields, opt);
	// 直接时间=用户输入的钟表时,恒可自 fields 直出;极端年(lunar-js 域外 baziLocal 缺席、
	// 后端 pan 无 clockTime)也不许显示「—」。
	const clockFallback = (fields && fields.date && fields.date.value && fields.time && fields.time.value)
		? `${fields.date.value.format('YYYY-MM-DD')} ${fields.time.value.format('HH:mm:ss')}`
		: '';
	return applyNongliDisplay({
		...pan,
		clockTime: pan.clockTime || clockFallback,
		tenching: opt.tenching !== undefined ? opt.tenching : 0,
		rotation: opt.rotation || '固定',
		options: buildOptions(opt, pan),
		palaces: normalizePalaces(pan.palace16),
	}, nongli, baziLocal);
}

function parseFieldsDateTime(fields){
	if(!fields || !fields.date || !fields.time){
		return null;
	}
	const dateStr = fields.date.value.format('YYYY-MM-DD');
	const timeStr = fields.time.value.format('HH:mm:ss');
	// BC 安全解析:'-7040-07-19' 裸 split('-') 会撕成 [NaN,7040,7,19](年 NaN 静默传播)
	const _dp = parseDateParts(dateStr);
	const d = _dp ? [_dp.year, _dp.month, _dp.day] : [];
	const t = timeStr.split(':').map((item)=>parseInt(item, 10));
	if(d.length < 3 || t.length < 2){
		return null;
	}
	return {
		year: d[0],
		month: d[1],
		day: d[2],
		hour: t[0],
		minute: t[1],
		second: t[2] || 0,
		date: dateStr,
		time: timeStr,
	};
}

function parseDateTimeText(text){
	const raw = safeText(text).trim();
	const match = raw.match(/^(-?\d{1,6})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?/);
	if(!match){
		return null;
	}
	return {
		year: parseInt(match[1], 10),
		month: parseInt(match[2], 10),
		day: parseInt(match[3], 10),
		hour: parseInt(match[4], 10),
		minute: parseInt(match[5], 10),
		second: parseInt(match[6] || '0', 10),
		date: `${match[1].padStart(4, '0')}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}`,
		time: `${match[4].padStart(2, '0')}:${match[5].padStart(2, '0')}:${(match[6] || '0').padStart(2, '0')}`,
	};
}

function resolveCalculationDateTime(fields, nongli, options){
	const direct = parseFieldsDateTime(fields);
	if(options && options.timeBasis === 'trueSolar'){
		return parseDateTimeText(nongli && nongli.birth) || direct;
	}
	return direct;
}

export function normalizeBackendPan(pan, options, nongli, baziLocal){
	if(!pan){
		return null;
	}
	const opt = options || {};
	return applyNongliDisplay({
		...pan,
		tenching: opt.tenching !== undefined ? opt.tenching : 0,
		rotation: opt.rotation || '固定',
		options: buildOptions(opt, pan),
		palaces: normalizePalaces(pan.palace16),
	}, nongli, baziLocal);
}

export function buildTaiyiSnapshotText(pan){
	if(!pan){
		return '';
	}
	const lines = [];
	lines.push('[起盘信息]');
	lines.push(`日期：${pan.dateStr} ${pan.timeStr}`);
	if(pan.realSunTime){
		lines.push(`真太阳时：${pan.realSunTime}`);
	}
	if(pan.lunarText){
		lines.push(`农历：${pan.lunarText}`);
	}
	if(pan.jiedelta){
		lines.push(`${pan.jiedelta}`);
	}
	lines.push(`干支：年${pan.ganzhi.year || ''} 月${pan.ganzhi.month || ''} 日${pan.ganzhi.day || ''} 时${pan.ganzhi.time || ''}`);
	lines.push(`命式：${pan.zhao}`);
	lines.push(`起盘方式：${pan.options ? pan.options.styleLabel : ''}`);
	lines.push(`古法公式：${pan.options ? (pan.options.methodLabel || pan.options.accumLabel) : ''}`);
	if(pan.options && pan.options.methodSource && pan.options.methodSource !== '命法不适用'){
		lines.push(`古法出处：${pan.options.methodSource}`);
	}
	lines.push(`时间基准：${pan.options ? pan.options.timeBasisLabel : ''}`);
	lines.push(`换日：${pan.options ? pan.options.daySwitchLabel : ''}`);
	if(pan.reignYear){
		lines.push(`历史年号：${pan.reignYear}`);
	}
	if(pan.calendarEra || pan.jiyuan){
		lines.push(`太乙纪元：${pan.calendarEra || pan.jiyuan}`);
	}
	lines.push(`命法：${pan.options ? pan.options.sexLabel : ''}`);
	lines.push(`博弈分析：${pan.options ? pan.options.gameTheoryLabel : ''}`);
	lines.push('');
	lines.push('[太乙盘]');
	buildTaiyiSnapshotLines(pan).forEach((line)=>lines.push(line));
	if(pan.sections && pan.sections.length){
		pan.sections.forEach((section)=>{
			lines.push('');
			lines.push(`[${section.title}]`);
			(section.rows || []).forEach((row)=>{
				lines.push(`${row.label}：${formatSnapshotValue(row.value)}`);
			});
		});
	}
	lines.push('');
	lines.push('[十六宫标记]');
	(pan.palace16 || []).forEach((item)=>{
		const txt = item.items && item.items.length > 0 ? item.items.join('、') : '—';
		lines.push(`${item.palace}：${txt}`);
	});
	return lines.join('\n');
}

function formatSnapshotValue(value){
	if(value === undefined || value === null || value === ''){
		return '—';
	}
	if(Array.isArray(value)){
		return value.map((item)=>formatSnapshotValue(item)).filter((item)=>item && item !== '—').join('、') || '—';
	}
	if(typeof value === 'object'){
		return Object.keys(value).map((key)=>{
			const item = formatSnapshotValue(value[key]);
			if(!item || item === '—'){
				return '';
			}
			return `${key}：${item}`;
		}).filter(Boolean).join('；') || '—';
	}
	return `${value}`.replace(/得None/g, '未得').replace(/None/g, '未得');
}

export function getStyleLabel(value){
	if(value === 5){
		return '太乙命法';
	}
	return getTaiyiStyleLabel(value);
}

export function getAccumLabel(value){
	return getTaiyiAccumLabel(value);
}

export function getMethodLabel(value){
	return getTaiyiAccumLabel(value);
}

export function getMethodSource(value){
	const one = METHOD_SOURCE_OPTIONS.find((item)=>item.value === value);
	return one ? one.source : '';
}
