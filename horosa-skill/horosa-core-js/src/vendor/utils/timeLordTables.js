// 时主轮转(轮主 / 轨主 / 年度分配 / 月相四分 / 月亮单度主 / 月亮九年 / 九分主 / 匀速点 / 发展年龄 / 周日象限 / 对数时标 / 月亮日)的单一来源:
// 缺省设置、选项、名称,以及「结果 → AI 快照正文」。页面、AI 挂载重算、AI 导出共用这里。
// 计算全在后端 astrostudy/timelord_tables.py(/astroextra/timelords),本文件只做口径与排版。
import * as AstroConst from '../../constants/AstroConst.js';
import * as AstroText from '../../constants/AstroText.js';
import { DEFAULT_TIME_LORD_YEAR, TIME_LORD_YEAR_TYPES } from './timeLordYears.js';

export const TIMELORD_METHODS = [
	{ value: 'turn', label: '轮主', note: '一年一段,沿所选次序循环' },
	{ value: 'orb', label: '轨主', note: '从出生时的行星时主起,一年一段' },
	{ value: 'annual', label: '年度分配', note: '每个太阳返照一段,年主 = 当年小限主,子段按天数表分' },
	{ value: 'quarters', label: '月相四分', note: '段长 = 小年 × 90 日,沿黄经序走,每轮起点后移三位' },
	{ value: 'monomoiria', label: '月亮单度主', note: '从月亮所在度的单度主起,年数 = 迦勒底序位,合 28 年一轮' },
	{ value: 'moonnine', label: '月亮九年', note: '从月亮所在座起逐座,每座 9 年' },
	{ value: 'nineparts', label: '九分主', note: '上升点每走 1°06′40″ 换一段,段主取九分度主与三分子主' },
	{ value: 'moving', label: '匀速点', note: '一个点从起始位置按黄道匀速前进,走到各点的相位位置记一件事' },
	{ value: 'devages', label: '发展年龄', note: '十二段依次 2 到 13 年,合 90 年,把盘上各点换成年龄' },
	{ value: 'diurnal', label: '周日象限', note: '移动点从上升起顺时针走,依次过 12、11 … 1 宫' },
	{ value: 'lifetime', label: '对数时标', note: '盘面一周按对数时标换成一生,越早的年份占的弧越大;上升是起点,天顶与各星、宫头、座首为目标,同一位置只列一行' },
	{ value: 'moondays', label: '月亮日', note: '第 3、7、40 日:月亮到达本命月加 30°、90°、180° 的时刻。改进档取离该日最近的那次到达(第 40 日约在生后第 41 天,是第二次到冲),经典档取第一次到达' },
];

export const TIMELORD_DEFAULTS = {
	method: 'turn', yearType: DEFAULT_TIME_LORD_YEAR, movingYear: 'sidereal', turnStart: 'asc', turnOrder: 'zodiac', orbMode: 'single',
	annualDays: 'tableA', annualOrder: 'natal', releaser: AstroConst.MOON, variant: 'improved', nineTime: 'degree', nineReverse: false,
	rateKind: 'condition', movingStart: 'Asc', devBasis: 'sign', diurnalMode: 'five',
};

const SEVEN = [AstroConst.SUN, AstroConst.MOON, AstroConst.MERCURY, AstroConst.VENUS, AstroConst.MARS, AstroConst.JUPITER, AstroConst.SATURN];
const POINT_NAMES = { Asc: '上升', MC: '天顶', 'North Node': '北交', 'South Node': '南交', 'Pars Fortuna': '福点', 'Pars Spirit': '灵点', Syzygy: '产前朔望' };

export function timeLordPointName(id){
	if(POINT_NAMES[id]){ return POINT_NAMES[id]; }
	const house = /^House(\d+)$/.exec(`${id}`);
	if(house){ return `第 ${house[1]} 宫头`; }
	const sign = /^sign:(\d+)$/.exec(`${id}`);
	if(sign){ return `${timeLordSignName(Number(sign[1]))}头`; }
	return (AstroText.AstroTxtMsg && AstroText.AstroTxtMsg[id]) || id || '-';
}

export function timeLordSignName(index){
	const id = AstroConst.LIST_SIGNS[index];
	return (AstroText.AstroTxtMsg && AstroText.AstroTxtMsg[id]) || id || '-';
}

export const TIMELORD_OPTIONS = {
	yearType: Object.keys(TIME_LORD_YEAR_TYPES).map((value)=>({ value, label: TIME_LORD_YEAR_TYPES[value].label })),
	turnStart: [{ value: 'asc', label: '上升主' }, { value: 'hour', label: '行星时主' }],
	turnOrder: [{ value: 'zodiac', label: '本命黄经序' }, { value: 'astronomical', label: '天文序' }, { value: 'chaldean', label: '迦勒底序' }, { value: 'house', label: '宫主序' }],
	orbMode: [{ value: 'single', label: '单轮(十二年)' }, { value: 'cycle', label: '循环(二十四年)' }],
	annualDays: [{ value: 'tableA', label: '甲表(金 22、火 42、木 34)' }, { value: 'tableB', label: '乙表(金 33、火 36、木 30)' }],
	annualOrder: [{ value: 'natal', label: '本命黄经序' }, { value: 'return', label: '当年返照盘黄经序' }],
	releaser: SEVEN.concat(['Pars Fortuna', 'Pars Spirit', 'Syzygy']).map((value)=>({ value, label: timeLordPointName(value) })),
	variant: [{ value: 'improved', label: '改进' }, { value: 'classic', label: '经典' }],
	nineTime: [{ value: 'degree', label: '度数(1° = 1 年)' }, { value: 'ascension', label: '上升时' }],
	nineReverse: [{ value: false, label: '不反转' }, { value: true, label: '首段子主反转' }],
	rateKind: [{ value: 'condition', label: '30°/年' }, { value: 'quadrant28', label: '28 年一周' }, { value: 'age72', label: '72 年一周' }],
	movingStart: ['Asc', 'MC'].concat(SEVEN, ['Syzygy']).map((value)=>({ value, label: timeLordPointName(value) })),
	devBasis: [{ value: 'sign', label: '按星座' }, { value: 'house', label: '按宫位' }],
	diurnalMode: [{ value: 'five', label: '每宫 5 年' }, { value: 'seven', label: '每宫 7 年' }, { value: 'quadrant', label: '四象限 90 年' }],
};

// 每法用到哪些设置;yearField = 这一法读哪个年长(年度分配、对数时标、月亮日不用年长)
export const TIMELORD_METHOD_FIELDS = {
	turn: { fields: ['turnStart', 'turnOrder'], yearField: 'yearType' },
	orb: { fields: ['orbMode'], yearField: 'yearType' },
	annual: { fields: ['annualDays', 'annualOrder'] },
	quarters: { fields: ['releaser'], yearField: 'yearType' },
	monomoiria: { fields: [], yearField: 'yearType' },
	moonnine: { fields: ['variant'], yearField: 'yearType' },
	nineparts: { fields: ['nineTime', 'nineReverse', 'variant'], yearField: 'yearType' },
	moving: { fields: ['rateKind', 'movingStart'], yearField: 'movingYear' },
	devages: { fields: ['devBasis', 'variant'], yearField: 'yearType' },
	diurnal: { fields: ['diurnalMode', 'variant'], yearField: 'yearType' },
	lifetime: { fields: [] },
	moondays: { fields: ['variant'] },
};

export const TIMELORD_FIELD_LABELS = {
	yearType: '年长', movingYear: '年长', turnStart: '起始星', turnOrder: '次序', orbMode: '走法', annualDays: '子段天数', annualOrder: '子段次序',
	releaser: '释放星', variant: '算法', nineTime: '时间', nineReverse: '子主', rateKind: '速率', movingStart: '起点', devBasis: '分段', diurnalMode: '速率',
};

// 当前真正起作用的设置:发展年龄按星座分段时两档算法结果相同,不显示也不发
export function timeLordFields(opts){
	const o = opts || {};
	const fields = (TIMELORD_METHOD_FIELDS[o.method] || TIMELORD_METHOD_FIELDS[TIMELORD_DEFAULTS.method]).fields;
	return o.method === 'devages' && o.devBasis !== 'house' ? fields.filter((key)=>key !== 'variant') : fields;
}

// 某项设置在这组设置下是否起作用(挂载齿轮只显示起作用的项)
export function timeLordFieldShown(key, opts){
	const o = opts || {};
	const method = TIMELORD_METHOD_FIELDS[o.method] ? o.method : TIMELORD_DEFAULTS.method;
	if(key === 'method'){ return true; }
	if(key === 'yearType' || key === 'movingYear'){ return TIMELORD_METHOD_FIELDS[method].yearField === key; }
	return timeLordFields({ ...o, method }).includes(key);
}

export function timeLordMethod(value){
	return TIMELORD_METHODS.find((m)=>m.value === value) || TIMELORD_METHODS[0];
}

// 设置值规整:选项里没有的值回落缺省,旧存档或手改存储都不会发出后端不认的参数
export function normalizeTimeLordOpts(opts){
	const o = opts && typeof opts === 'object' ? opts : {};
	const out = {};
	Object.keys(TIMELORD_DEFAULTS).forEach((key)=>{
		const list = key === 'method' ? TIMELORD_METHODS : (TIMELORD_OPTIONS[key === 'movingYear' ? 'yearType' : key] || []);
		const hit = list.find((item)=>item.value === o[key] || (key === 'nineReverse' && item.value === (o[key] === true || o[key] === 1 || o[key] === '1' || o[key] === 'true')));
		out[key] = hit ? hit.value : TIMELORD_DEFAULTS[key];
	});
	return out;
}

export function timeLordRequestFields(opts){
	const o = normalizeTimeLordOpts(opts);
	const spec = TIMELORD_METHOD_FIELDS[o.method];
	const fields = { method: o.method };
	if(spec.yearField){ fields.yearType = o[spec.yearField]; }
	timeLordFields(o).forEach((key)=>{ fields[key] = key === 'nineReverse' ? (o[key] ? 1 : 0) : o[key]; });
	return fields;
}

function n(v, d){
	const x = Number(v);
	return Number.isFinite(x) ? x.toFixed(d) : '-';
}
const dateOnly = (v)=>`${v || '-'}`.trim().split(/[ T]/)[0];

export function timeLordRowLord(row){
	if(row.sign !== undefined && row.sign !== null){ return `${timeLordSignName(row.sign)}(${timeLordPointName(row.lord)})`; }
	if(row.sub){ return `${timeLordPointName(row.lord)} / ${timeLordPointName(row.sub)}`; }
	return timeLordPointName(row.lord);
}

export function timeLordAspectText(row){
	if(row.aspect === undefined || row.aspect === null){ return ''; }
	const name = { 0: '合', 60: '六合', 90: '刑', 120: '拱', 180: '冲' }[row.aspect] || `${row.aspect}°`;
	return row.side ? `${name}(${row.side === 'S' ? '左' : '右'})` : name;
}

const NEXT_ROWS = 8;

export const TIMELORD_POLAR_NOTE = '极圈内斜升不单调,上升时档不成立,已改按度数';

// 结果回显的键 → 设置字段,快照里写明这张表按什么口径算的
const ECHO_FIELDS = {
	turn: { order: 'turnOrder' }, orb: { mode: 'orbMode' }, annual: { dayTable: 'annualDays', order: 'annualOrder' }, quarters: { releaser: 'releaser' },
	moonnine: { variant: 'variant' }, nineparts: { time: 'nineTime', reverse: 'nineReverse', variant: 'variant' },
	moving: { rateKind: 'rateKind', startPoint: 'movingStart' }, devages: { basis: 'devBasis', variant: 'variant' }, diurnal: { mode: 'diurnalMode', variant: 'variant' },
	moondays: { variant: 'variant' },
};

function echoLines(r){
	const lines = [];
	const spec = TIMELORD_METHOD_FIELDS[r.method];
	if(spec && spec.yearField){
		const year = TIMELORD_OPTIONS.yearType.find((item)=>item.value === r.yearType);
		if(year){ lines.push(`年长：${year.label}`); }
	}
	const echo = ECHO_FIELDS[r.method] || {};
	const shown = timeLordFields({ method: r.method, devBasis: r.basis });
	Object.keys(echo).filter((key)=>shown.includes(echo[key])).forEach((key)=>{
		const hit = (TIMELORD_OPTIONS[echo[key]] || []).find((item)=>item.value === r[key]);
		if(hit){ lines.push(`${TIMELORD_FIELD_LABELS[echo[key]]}：${hit.label}`); }
	});
	if(r.polar){ lines.push(TIMELORD_POLAR_NOTE); }
	return lines;
}

// 事件行的名字:月亮日没有目标点,用第几日
export function timeLordEventName(row){
	if(row.day !== undefined && row.day !== null){ return `第 ${row.day} 日(本命月 + ${row.arc}°)`; }
	return `${timeLordPointName(row.point)} ${timeLordAspectText(row)}`.trim();
}

// 结果 → 快照正文(段头登记在 aiExport preset)
export function buildTimeLordText(r){
	if(!r || typeof r !== 'object' || r.err || !Array.isArray(r.rows) || !r.rows.length){ return ''; }
	const method = timeLordMethod(r.method);
	const moonDays = r.method === 'moondays';      // 月亮日是出生后头四十来天的三个时刻,不看目标时刻
	const lines = ['[时主轮转]', `方法：${method.label}(${method.note})`];
	if(!moonDays){ lines.push(`目标时刻：${r.target || '-'}`); }
	lines.push(...echoLines(r));
	if(r.startLord){ lines.push(`起始星：${timeLordPointName(r.startLord)}`); }
	if(r.hourLord){ lines.push(`出生行星时主(不等时)：${timeLordPointName(r.hourLord)}`); }
	lines.push('');
	const index = Number.isInteger(r.currentIndex) ? r.currentIndex : -1;
	if(r.kind === 'periods'){
		lines.push('[当前时段]');
		const row = index >= 0 ? r.rows[index] : null;
		if(row){
			lines.push(`${timeLordRowLord(row)},${n(row.startAge, 2)} 至 ${n(row.endAge, 2)} 岁,${dateOnly(row.start)} 至 ${dateOnly(row.end)}`);
			const subs = row.children || [];
			if(subs.length){ lines.push(`子段：${subs.map((c)=>`${timeLordRowLord(c)} ${dateOnly(c.start)} 起`).join(';')}`); }
		}else{ lines.push('目标时刻不在列表范围内'); }
		lines.push('');
		lines.push('[后续]');
		(r.pastEnd ? [] : r.rows.slice(index + 1, index + 1 + NEXT_ROWS)).forEach((next)=>{ lines.push(`${timeLordRowLord(next)}:${dateOnly(next.start)} 起,${n(next.startAge, 2)} 岁`); });
	}else if(moonDays){
		lines.push('三个时刻:');
		r.rows.forEach((row)=>{
			const days = Number.isFinite(Number(row.afterDays)) ? Number(row.afterDays) : Number(row.age) * 365.2422;
			lines.push(`第 ${row.day} 日:月亮到本命月加 ${row.arc}°,生后 ${n(days, 2)} 天,${dateOnly(row.date)}`);
		});
	}else{
		lines.push('[当前时段]');
		const last = index > 0 ? r.rows[index - 1] : (index < 0 ? r.rows[r.rows.length - 1] : null);
		lines.push(last ? `最近一件：${timeLordEventName(last)} ${n(last.age, 2)} 岁,${dateOnly(last.date)}` : '目标时刻之前没有事件');
		lines.push('');
		lines.push('[后续]');
		(index < 0 ? [] : r.rows.slice(index, index + NEXT_ROWS)).forEach((next)=>{ lines.push(`${timeLordEventName(next)}:${n(next.age, 2)} 岁,${dateOnly(next.date)}`); });
	}
	return lines.join('\n');
}
