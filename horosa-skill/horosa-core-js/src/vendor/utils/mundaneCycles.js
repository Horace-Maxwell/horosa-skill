// 世俗周期表:页面设置、请求字段与 AI 快照正文。算法在 astropy/astrostudy/mundane_cycles.py。
import * as AstroText from '../../constants/AstroText.js';
import { definePageSettings } from './pageSettingsStore.js';
import { starNameCn } from './starNamesCn.js';

export const MUNDANE_CYCLE_TABLES = [
	{ value: 'conjunctions', label: '大中小合', note: '木土、火土、火木的真实地心合,标出换三分性的一合', fields: ['conjKind', 'cycleVariant'], range: true },
	{ value: 'meanConjunctions', label: '平均大合', note: '古表的等差序列,周期和每合进度各表不同', fields: ['meanTable'], range: true },
	{ value: 'turns', label: '千年轮转', note: '每段 360 年,星座从巨蟹起,行星从土星起走迦勒底序', fields: ['flood', 'cycleYear'] },
	{ value: 'firdaria', label: '世运法达', note: '从盘面时刻起列周期,不按洪水对齐', fields: ['firdariaLevel', 'firdariaYears', 'cycleYear', 'cycleVariant'] },
	{ value: 'profections', label: '世俗小限', note: '从锚点逐座顺行,首行是锚点加一步', fields: ['profRate', 'profBase', 'cycleVariant'] },
	{ value: 'thousands', label: '千年表', note: '千年主、分度、转位、季摄,按洪水后年数推算', year: true },
	{ value: 'worldYears', label: '世界年表', note: '世界年的方向、小限、法达、大年、季摄与颤动', year: true },
	{ value: 'dawr', label: '周期年表', note: '360 年周期里的年座、年主、周度与四分主', fields: ['dawrStart'], year: true },
	{ value: 'era', label: '纪元小限', note: '上升、换组、大合三点每年进 30°,洪水点每年进 1°', fields: ['eraKind'], year: true },
	{ value: 'parts', label: '世俗希腊点', note: '不分昼夜,取当前盘', chart: true },
	{ value: 'revolution', label: '年度回归', note: '太阳到入点时五星的黄纬南北、顺逆与对日状态', fields: ['ingressPoint'], year: true },
	{ value: 'weather', label: '气象占', note: '从盘面日期起逐个朔望取关键度数(朔取合朔点,望取当时地平线上的发光体),它的埃及界主是天气主星;列主星的星座、与日十六相和条件,关键度数之后的第一个角及其座主,以及 1.6° 内亮星的行星性质。只给结构,不附判词', fields: ['weatherMonths', 'cycleVariant'], chart: true },
	{ value: 'lunations', label: '默冬月相族', zone: true, note: '以盘面日期附近的朔为中心,按默冬周期(235 个朔望月,约 19 年)前后各取两轮,共五轮;同一轮的朔、上弦、望、下弦,隔 19 年几乎落在同一日期与同一黄经;时间按盘面时区' },
	{ value: 'directions', label: '世俗主限', note: '当前盘的主限弧一度当一日,一年里走完 360°;弧按主限引擎缺省的方位法算,时间键把度换成日', fields: ['mpdKey'], chart: true },
];

export const MUNDANE_CYCLE_OPTIONS = {
	conjKind: [{ value: 'great', label: '大合(木土)' }, { value: 'middle', label: '中合(火土)' }, { value: 'lesser', label: '小合(火木)' }],
	meanTable: [['一', 7252.52], ['二', 7253.33], ['三', 7252.32], ['四', 7249.55], ['五', 7249.59], ['六', 7249.60], ['七', 7250.34], ['八', 7253.33]]
		.map(([name, days], i)=>({ value: `table${i + 1}`, label: `第${name}表(${days} 日)` })),
	flood: [{ value: 'a', label: '公元前 3381 年起' }, { value: 'b', label: '公元前 3102 年起' }],
	cycleYear: [{ value: 'sidereal', label: '恒星年' }, { value: 'solar', label: '回归年' }, { value: 'world', label: '世界年(365.2583 日)' }],
	firdariaLevel: [{ value: 'big', label: '大(按座)' }, { value: 'middle', label: '中(75 年)' }, { value: 'lesser', label: '小(小期)' }],
	firdariaYears: [{ value: 100, label: '列 100 年' }, { value: 200, label: '列 200 年' }, { value: 500, label: '列 500 年' }, { value: 1000, label: '列 1000 年' }],
	profRate: [{ value: 'big', label: '每座 100 年' }, { value: 'great', label: '每座 80 年' }, { value: 'qisma', label: '每座 30 年' }, { value: 'solar', label: '每座 30.44 年' },
		{ value: 'middle20', label: '每座 20 年' }, { value: 'middle', label: '每座 10 年' }, { value: 'monarchy', label: '每座 5 年' }, { value: 'malefic', label: '每座 2.5 年' },
		{ value: 'lesser20', label: '每座 20 个月' }, { value: 'lesser', label: '每座 1 年' }, { value: 'degree', label: '每座 1 个月' }],
	profBase: [{ value: 'greatSign', label: '大合所在座' }, { value: 'greatAsc', label: '大合年入白羊上升' }, { value: 'greatMc', label: '大合年入白羊天顶' }, { value: 'changeSign', label: '换组所在座' },
		{ value: 'changeAsc', label: '换组年入白羊上升' }, { value: 'changeMc', label: '换组年入白羊天顶' }, { value: 'ingress', label: '入白羊' }],
	dawrStart: [{ value: 'a', label: '1648 年起' }, { value: 'b', label: '1660 年起' }],
	eraKind: [{ value: 'hijra', label: '伊斯兰纪元' }, { value: 'change', label: '1980 年换组合' }],
	ingressPoint: [{ value: 0, label: '白羊' }, { value: 90, label: '巨蟹' }, { value: 180, label: '天秤' }, { value: 270, label: '摩羯' }],
	cycleVariant: [{ value: 'improved', label: '改进' }, { value: 'classic', label: '经典' }],
	weatherMonths: [{ value: 3, label: '列 3 个月' }, { value: 6, label: '列 6 个月' }, { value: 12, label: '列 12 个月' }],
	mpdKey: [{ value: 'Ptolemy', label: 'Ptolemy(1° = 1 日)' }, { value: 'Naibod', label: 'Naibod' }, { value: 'Cardano', label: 'Cardano' }, { value: 'Umar', label: 'Umar' }],
};

export const MUNDANE_CYCLE_DEFAULTS = {
	cycleTable: 'conjunctions', conjKind: 'great', meanTable: 'table1', flood: 'a', cycleYear: 'sidereal', firdariaLevel: 'big', firdariaYears: 200, profRate: 'great', profBase: 'greatSign',
	dawrStart: 'a', eraKind: 'hijra', ingressPoint: 0, cycleVariant: 'improved', mpdKey: 'Ptolemy', weatherMonths: 3,
};

const LABELS = { conjKind: '合', meanTable: '表', flood: '起点', cycleYear: '年长', firdariaLevel: '档', firdariaYears: '范围', profRate: '速率', profBase: '起点', dawrStart: '起点', eraKind: '纪元', ingressPoint: '入点', cycleVariant: '算法', mpdKey: '时间键', weatherMonths: '月数' };
export const mundaneCycleFieldLabel = (key)=>LABELS[key] || key;

const schema = { cycleTable: { label: '世俗周期表·当前表', def: MUNDANE_CYCLE_DEFAULTS.cycleTable, oneOf: MUNDANE_CYCLE_TABLES.map((item)=>item.value) } };
Object.keys(MUNDANE_CYCLE_OPTIONS).forEach((key)=>{
	schema[key] = { label: `世俗周期表·${LABELS[key]}`, def: MUNDANE_CYCLE_DEFAULTS[key], oneOf: MUNDANE_CYCLE_OPTIONS[key].map((item)=>item.value) };
});
export const MUNDANE_CYCLE_SETTINGS = definePageSettings('horosa.mundane.cycles.v1', schema);

export function mundaneCycleTable(value){
	return MUNDANE_CYCLE_TABLES.find((item)=>item.value === value) || MUNDANE_CYCLE_TABLES[0];
}

// 这张表起作用的选项。算法档只有大合、世运法达小档、世俗小限的非天顶起点有差别
export function mundaneCycleFields(settings){
	const s = settings || {};
	const def = mundaneCycleTable(s.cycleTable);
	const fields = def.fields || [];
	const noVariant = (def.value === 'firdaria' && s.firdariaLevel !== 'lesser')
		|| (def.value === 'conjunctions' && (s.conjKind || MUNDANE_CYCLE_DEFAULTS.conjKind) !== 'great')
		|| (def.value === 'profections' && /Mc$/.test(s.profBase || ''));
	return noVariant ? fields.filter((key)=>key !== 'cycleVariant') : fields;
}

export function mundaneCycleRequestFields(settings, years){
	const s = settings || {};
	const def = mundaneCycleTable(s.cycleTable);
	const fields = { table: def.value };
	mundaneCycleFields(s).forEach((key)=>{ fields[key === 'cycleVariant' ? 'variant' : key] = s[key]; });
	const y = years || {};
	if((def.range || def.year) && Number.isInteger(y.startYear)){ fields.startYear = y.startYear; }
	if(def.range && Number.isInteger(y.endYear)){ fields.endYear = y.endYear; }
	return fields;
}

const POINTS = { 'North Node': '北交', 'South Node': '南交' };
export function mundanePointName(id){
	return POINTS[id] || (AstroText.AstroTxtMsg && AstroText.AstroTxtMsg[id]) || `${id || '-'}`;
}

const SIGNS = ['白羊', '金牛', '双子', '巨蟹', '狮子', '处女', '天秤', '天蝎', '射手', '摩羯', '水瓶', '双鱼'];
export function mundaneSignName(index){ return SIGNS[index] || '-'; }

export function mundaneLon(lon){
	const value = Number(lon);
	if(!Number.isFinite(value)){ return '-'; }
	const sign = Math.floor(value / 30) % 12;
	return `${SIGNS[sign]} ${(value - sign * 30).toFixed(2)}°`;
}

export const RELATION_NAMES = { morning: '晨星', evening: '昏星', station: '留', beams: '光束下' };
export const WEATHER_CONDITION_NAMES = { SIGN: '所在星座', LAT_N: '黄纬北', LAT_S: '黄纬南', RETRO: '逆行', STATION: '留', SUB_RADIIS: '日光束下', MORNING: '晨星', EVENING: '昏星', ELONG: '近最大距角' };
export const WEATHER_ANGLE_NAMES = { Asc: '上升', MC: '天顶', IC: '天底', Desc: '下降' };
export const weatherStarText = (stars)=>(stars || []).map((x)=>`${starNameCn(x.star)}(${x.natures.map(mundanePointName).join('、')}性)`).join('、');

const MAX_TEXT_ROWS = 24;
const YEAR_FIELD = { thousands: 'year', worldYears: 'year', dawr: 'year', era: 'year' };
const dateOnly = (v)=>`${v || '-'}`.trim().split(' ')[0];

function rowText(table, row){
	if(table === 'conjunctions'){ return `${dateOnly(row.date)} ${mundaneLon(row.lon)}${row.shift ? ' 换三分性' : ''}${row.repeat ? ' 三重合' : ''}`; }
	if(table === 'meanConjunctions'){ return `${dateOnly(row.date)} ${mundaneLon(row.lon)}`; }
	if(table === 'turns'){ return `${dateOnly(row.date)} ${mundaneSignName(row.sign)} ${mundanePointName(row.lord)}`; }
	if(table === 'firdaria'){ return `${dateOnly(row.date)} ${row.lord ? mundanePointName(row.lord) : mundaneSignName(row.sign)} ${row.years} 年`; }
	if(table === 'profections'){ return `${dateOnly(row.date)} ${mundaneSignName(row.sign)}`; }
	if(table === 'thousands'){ return `${row.year} 千年主 ${mundanePointName(row.thousandLord)} 转主 ${mundanePointName(row.turnLord)} 季摄 ${mundanePointName(row.quarterLord)}`; }
	if(table === 'worldYears'){
		return `${row.year} 世界年 ${row.worldYear} 世主 ${mundanePointName(row.governor)} 方向 ${mundaneLon(row.dirYear)} 小限 ${mundaneLon(row.profYear)} 法达 ${mundanePointName(row.firdariaLord)} 中 ${mundanePointName(row.firdariaMiddle)} 小 ${mundanePointName(row.firdariaLesser)} 季摄 ${mundanePointName(row.quarterLord)} 颤动 ${Number(row.trepidation).toFixed(2)}°`;
	}
	if(table === 'dawr'){ return `${row.year} ${mundaneSignName(row.sign)} 年主 ${mundanePointName(row.lord)} 四分主 ${mundanePointName(row.quarterLord)}`; }
	if(table === 'era'){ return `${row.year} 上升 ${mundaneLon(row.asc)} 换组 ${mundaneLon(row.turn)} 大合 ${mundaneLon(row.conj)}`; }
	if(table === 'parts'){ return `${row.formula} ${mundaneLon(row.lon)}`; }
	if(table === 'weather'){
		const lord = row.lord || {};
		return `${row.date} ${row.kind === 'new' ? '朔' : `望(取${mundanePointName(row.luminary)})`} ${mundaneLon(row.lon)} 主星 ${mundanePointName(lord.planet)} ${mundaneSignName(lord.sign)} ${lord.phaseName || ''} ${(lord.conditions || []).filter((c)=>c !== 'SIGN').map((c)=>WEATHER_CONDITION_NAMES[c] || c).join('、')}`
			+ ` 后随角 ${WEATHER_ANGLE_NAMES[row.angle] || row.angle}(座主 ${mundanePointName(row.angleRuler)})${row.stars && row.stars.length ? ` 亮星 ${weatherStarText(row.stars)}` : ''}${row.season ? ` 季节朔望(入${mundaneSignName(Math.round(row.season.point / 30))} ${dateOnly(row.season.date)})` : ''}`;
	}
	if(table === 'lunations'){ return `${row.relative > 0 ? '+' : ''}${row.relative} 轮 朔 ${row.new} 上弦 ${dateOnly(row.firstQuarter)} 望 ${dateOnly(row.full)} 下弦 ${dateOnly(row.lastQuarter)}`; }
	if(table === 'directions'){ return `${dateOnly(row.date)} ${mundanePointName(row.promissor)}${row.aspect ? ` ${row.aspect}°${{ S: '左', D: '右' }[row.side] || ''}` : ''} → ${mundanePointName(row.significator)}(弧 ${Number(row.arc).toFixed(2)}°${row.converse ? ',逆向' : ''})`; }
	return `${mundanePointName(row.planet)} ${mundaneLon(row.lon)} ${row.north ? '北纬' : '南纬'}${row.retrograde ? ' 逆行' : ''} ${RELATION_NAMES[row.relation] || ''}`;
}

// 快照写明这张表的口径
// 结果键 → 选项键。接口没回带的(年长 cycleYear、周期年表起点 dawrStart)取发出这次请求的字段(req)
const ECHO = { conjunctions: { kind: 'conjKind' }, meanConjunctions: { meanTable: 'meanTable' }, turns: { flood: 'flood', cycleYear: 'cycleYear' }, firdaria: { level: 'firdariaLevel', cycleYear: 'cycleYear' },
	profections: { rate: 'profRate', base: 'profBase' }, dawr: { dawrStart: 'dawrStart' }, era: { eraKind: 'eraKind' }, revolution: { ingressPoint: 'ingressPoint' }, directions: { mpdKey: 'mpdKey' }, weather: { weatherMonths: 'weatherMonths' } };

// 气象占两档的差别(页面说明与快照同一句)
export const WEATHER_VARIANT_NOTES = {
	improved: '改进:近最大距角与本次视现期的大距比(水星各次大距 18°~28° 不等);亮星表在原 61 颗之外补《四书》写了性质的 14 颗亮星',
	classic: '经典:近最大距角按常数(水星 27.8°、金星 47.8°)的 97% 判;亮星表只用原 61 颗',
};

function echoLines(r, req){
	const echo = ECHO[r.table] || {};
	const q = req || {};
	const lines = [];
	Object.keys(echo).forEach((key)=>{
		const value = r[key] !== undefined ? r[key] : q[echo[key]];
		const hit = (MUNDANE_CYCLE_OPTIONS[echo[key]] || []).find((item)=>item.value === value);
		if(hit){ lines.push(`${LABELS[echo[key]]}：${hit.label}`); }
	});
	if(r.table === 'weather'){
		lines.push(`算法：${WEATHER_VARIANT_NOTES[r.variant === 'classic' ? 'classic' : 'improved']}`);
	}else if(r.variant === 'classic'){ lines.push('算法：经典'); }
	return lines;
}

// 行多时取目标年前后,不从表头截
// 世俗主限一年上千行:快照只取到四角、日月的合、刑、冲
const DIRECTION_KEY_POINTS = ['Asc', 'MC', 'Sun', 'Moon'];
const directionKeyRows = (r)=>r.rows.filter((row)=>DIRECTION_KEY_POINTS.includes(row.significator) && [0, 90, 180].includes(Number(row.aspect)));
function textWindow(r, table){
	if(table === 'directions'){
		// 一年里按月各取前两条,AI 能看到全年
		const perMonth = {};
		return directionKeyRows(r).filter((row)=>{
			const m = /^(-?\d+)-(\d+)/.exec(`${row.date || ''}`);      // 年可带负号(公元前),不按定宽切
			const month = m ? `${m[1]}-${m[2]}` : '';
			perMonth[month] = (perMonth[month] || 0) + 1;
			return perMonth[month] <= 2;
		}).slice(0, MAX_TEXT_ROWS);
	}
	const rows = r.rows;
	if(rows.length <= MAX_TEXT_ROWS){ return rows; }
	const year = (row)=>Number(YEAR_FIELD[table] ? row.year : `${row.date || ''}`.replace(/^(-?\d+).*$/, '$1'));
	const near = rows.findIndex((row)=>year(row) >= Number(r.targetYear));
	const start = Math.max(0, (near < 0 ? rows.length : near) - MAX_TEXT_ROWS / 2);
	return rows.slice(start, start + MAX_TEXT_ROWS);
}

// 结果 → 快照正文(段头登记在 aiExport preset)。req = 发出这次请求的字段(接口没回带的口径从这里取)
export function buildMundaneCycleText(r, req){
	if(!r || typeof r !== 'object' || r.err || !Array.isArray(r.rows) || !r.rows.length){ return ''; }
	const def = mundaneCycleTable(r.table);
	const lines = ['[世运周期表]', `表：${def.label}(${def.note})`, ...echoLines(r, req)];
	if(r.anchor){ lines.push(`锚点：${dateOnly(r.anchor)} ${mundaneLon(r.anchorLon)}`); }
	if(r.date){ lines.push(`回归时刻(世界时)：${r.date}`); }
	if(def.value === 'directions'){ lines.push('只列到上升、天顶、日、月的合、刑、冲,每月取前两条'); }
	const shown = textWindow(r, def.value);
	shown.forEach((row)=>{ lines.push(rowText(def.value, row)); });
	const total = def.value === 'directions' ? directionKeyRows(r).length : r.rows.length;
	if(total > shown.length){ lines.push(`其余 ${total - shown.length} 行略`); }
	return lines.join('\n');
}

// 千年表 / 世界年表各列的意思(界面列头悬浮说明、帮助页同一份)
export const THOUSANDS_COLUMN_NOTES = {
	year: '公元年(历史纪年);洪水后年 = 公元年 + 3392',
	thousandLord: '千年主:每 1000 个洪水后年换一星,按迦勒底序(土木火日金水月)轮',
	turnLord: '转主:每 360 年换一星,按迦勒底序轮(与「千年轮转」同一套 360 年)',
	quarterLord: '季摄:每 90 年换一星,按火、日、水、土四星轮',
	quarterYear: '季内年:本 90 年季摄期内的第几年(0 起)',
	division: '分度:黄道上的一个点,每 30 年进一座(30°),座内每年进 0.1°',
	turn: '转位:本 360 年转所在的座头黄经,从巨蟹 0°(90°)起,每 360 年进一座',
};
export const WORLD_YEAR_COLUMN_NOTES = {
	year: '公元年(历史纪年)',
	worldYear: '世界年 = 公元年 + 183101',
	governor: '世主:每 1000 个世界年换一星,按迦勒底序七星轮',
	governorNine: '九主:同上,但把北交、南交排在七星之后,九星轮',
	firdariaLord: '法达:每 360 年换一星的大期主(1939 年起为日),按迦勒底序',
	firdariaMiddle: '中:中期法达主,每 75 年换一星,按法达序(日月北交木水土南交火金),1849 年起',
	firdariaLesser: '小:75 年中期之内按小期年数(日 10、月 9、北交 3、木 12、水 13、土 11、南交 2、火 7、金 8)轮到的星',
	quarterLord: '季摄:每 90 年换一星,按火、日、水、土四星轮(1759 年起)',
	greatYear: '大年:1461 年大年里的第几年(1961 年为第 1 年)',
	dirYear: '年向:方向每世界年进 1°(取 0~360°)',
	profYear: '年限:小限每年进一座(30°)',
	trepidation: '颤动:640 年一轮,每 80 年 1°,从 0° 走到 8° 后归零(1745 年为 0°)',
	dirMillennium: '千向:方向每 1000 世界年进 1°',
	dirCentury: '百向:方向每 100 世界年进 1°',
	dirDecade: '十向:方向每 10 世界年进 1°',
	profMillennium: '千限:小限每 1000 年进一座',
	profCentury: '百限:小限每 100 年进一座',
	profDecade: '十限:小限每 10 年进一座',
	firdariaLon: '法达度:360 年大期法达折成黄道度数,每年 1/12°(1939 年在 300°)',
	firdariaBig: '大度:按座走的 78 年循环折成黄道度数,白羊 12 年、金牛 11 年……双鱼 1 年,座内按年均分(1759 年为白羊 0°)',
};
