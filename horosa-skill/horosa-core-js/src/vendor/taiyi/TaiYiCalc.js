import {
	TAIYI_STYLE_OPTIONS,
	TAIYI_ACCUM_OPTIONS,
	calcTaiyiPanFromKintaiyi,
	buildTaiyiSnapshotLines,
	getTaiyiStyleLabel,
	getTaiyiAccumLabel,
} from './core/TaiYiCore.js';

export const STYLE_OPTIONS = [
	...TAIYI_STYLE_OPTIONS.slice(),
	{ value: 5, label: '太乙命法' },
];

export const ACCUM_OPTIONS = TAIYI_ACCUM_OPTIONS.slice();

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
	const tn = pan && pan.tnForPan !== undefined ? pan.tnForPan : (options.tn !== undefined ? options.tn : 0);
	return {
		styleLabel: getStyleLabel(options.style !== undefined ? options.style : (pan ? pan.style : 3)),
		accumLabel: getAccumLabel(tn),
		tenchingLabel: options.tenching === 1 ? '有' : '无',
		sexLabel: options.sex || (pan && pan.sex) || '男',
		rotationLabel: options.rotation || '固定',
	};
}

export function calcTaiyi(fields, nongli, options){
	const opt = options || {};
	const pan = calcTaiyiPanFromKintaiyi(fields, nongli, opt);
	if(!pan){
		return null;
	}
	return {
		...pan,
		tenching: opt.tenching !== undefined ? opt.tenching : 0,
		rotation: opt.rotation || '固定',
		options: buildOptions(opt, pan),
		palaces: normalizePalaces(pan.palace16),
	};
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
	lines.push(`积年方式：${pan.options ? pan.options.accumLabel : ''}`);
	lines.push(`十精：${pan.options ? pan.options.tenchingLabel : ''}`);
	lines.push(`命法：${pan.options ? pan.options.sexLabel : ''}`);
	lines.push(`盘体：${pan.options ? pan.options.rotationLabel : ''}`);
	lines.push('');
	lines.push('[太乙盘]');
	buildTaiyiSnapshotLines(pan).forEach((line)=>lines.push(line));
	lines.push('');
	lines.push('[十六宫标记]');
	(pan.palace16 || []).forEach((item)=>{
		const txt = item.items && item.items.length > 0 ? item.items.join('、') : '—';
		lines.push(`${item.palace}：${txt}`);
	});
	return lines.join('\n');
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
