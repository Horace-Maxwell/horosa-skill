const GAN = '甲乙丙丁戊己庚辛壬癸'.split('');
const ZHI = '子丑寅卯辰巳午未申酉戌亥'.split('');
const JIAZI = [];
for(let i=0; i<60; i++){
	JIAZI.push(`${GAN[i % 10]}${ZHI[i % 12]}`);
}

const MONTH_MAP = {
	正月: 1,
	二月: 2,
	三月: 3,
	四月: 4,
	五月: 5,
	六月: 6,
	七月: 7,
	八月: 8,
	九月: 9,
	十月: 10,
	冬月: 11,
	腊月: 12,
};

const DAY_MAP = {
	初一: 1, 初二: 2, 初三: 3, 初四: 4, 初五: 5,
	初六: 6, 初七: 7, 初八: 8, 初九: 9, 初十: 10,
	十一: 11, 十二: 12, 十三: 13, 十四: 14, 十五: 15,
	十六: 16, 十七: 17, 十八: 18, 十九: 19, 二十: 20,
	廿一: 21, 廿二: 22, 廿三: 23, 廿四: 24, 廿五: 25,
	廿六: 26, 廿七: 27, 廿八: 28, 廿九: 29, 三十: 30,
};

const JIEQI_STD = [
	'小寒', '大寒', '立春', '雨水', '惊蛰', '春分',
	'清明', '谷雨', '立夏', '小满', '芒种', '夏至',
	'小暑', '大暑', '立秋', '处暑', '白露', '秋分',
	'寒露', '霜降', '立冬', '小雪', '大雪', '冬至',
];

// 标准“定气”近似算法常量（1900-2100 范围内常用）
const S_TERM_INFO = [
	0, 21208, 42467, 63836, 85337, 107014,
	128867, 150921, 173149, 195551, 218072, 240693,
	263343, 285989, 308563, 331033, 353350, 375494,
	397447, 419210, 440795, 462224, 483532, 504758,
];

function safe(v, d = ''){
	return v === undefined || v === null ? d : v;
}

function cloneJson(obj){
	if(!obj || typeof obj !== 'object'){
		return obj;
	}
	try{
		return JSON.parse(JSON.stringify(obj));
	}catch(e){
		return { ...obj };
	}
}

function parseZoneMinutes(zone){
	const txt = `${safe(zone, '+08:00')}`;
	const m = txt.match(/^([+-]?)(\d{1,2})(?::?(\d{2}))?$/);
	if(!m){
		return 8 * 60;
	}
	const sign = m[1] === '-' ? -1 : 1;
	const hh = parseInt(m[2], 10);
	const mm = parseInt(m[3] || '0', 10);
	if(Number.isNaN(hh) || Number.isNaN(mm)){
		return 8 * 60;
	}
	return sign * (hh * 60 + mm);
}

function toZonedDate(date, zoneMinutes){
	return new Date(date.getTime() + zoneMinutes * 60000);
}

function formatYmdHms(date, zoneMinutes){
	const zdt = toZonedDate(date, zoneMinutes);
	const y = zdt.getUTCFullYear();
	const m = `${zdt.getUTCMonth() + 1}`.padStart(2, '0');
	const d = `${zdt.getUTCDate()}`.padStart(2, '0');
	const hh = `${zdt.getUTCHours()}`.padStart(2, '0');
	const mm = `${zdt.getUTCMinutes()}`.padStart(2, '0');
	const ss = `${zdt.getUTCSeconds()}`.padStart(2, '0');
	return {
		date: `${y}-${m}-${d}`,
		time: `${hh}:${mm}:${ss}`,
		year: y,
		month: parseInt(m, 10),
		day: parseInt(d, 10),
	};
}

function getOnlyDateNum(year, month, day){
	let a = Math.floor((14 - month) / 12);
	let y = year + 4800 - a;
	let m = month + 12 * a - 3;
	return day + Math.floor((153 * m + 2) / 5) + 365 * y + Math.floor(y / 4) - Math.floor(y / 100) + Math.floor(y / 400) - 32045;
}

function getDayGanZhi(year, month, day){
	const jdn = getOnlyDateNum(year, month, day);
	let idx = (jdn + 49) % 60;
	if(idx < 0){
		idx += 60;
	}
	return JIAZI[idx];
}

function parseChineseMonthInt(txt){
	return MONTH_MAP[safe(txt)] || null;
}

function parseChineseDayInt(txt){
	return DAY_MAP[safe(txt)] || null;
}

function getTimeGanZhiFromDay(dayGanZi, hour){
	const dayGan = `${safe(dayGanZi)}`.substring(0, 1);
	const hourBranch = (function getHourBranch(){
		if(hour === 23 || hour === 0){
			return '子';
		}
		const idx = Math.floor((hour + 1) / 2) % 12;
		return ZHI[idx];
	})();
	const startGan = (function getStartGan(){
		if('甲己'.includes(dayGan)) return '甲';
		if('乙庚'.includes(dayGan)) return '丙';
		if('丙辛'.includes(dayGan)) return '戊';
		if('丁壬'.includes(dayGan)) return '庚';
		return '壬';
	})();
	const ganIdx = GAN.indexOf(startGan);
	const zhiIdx = ZHI.indexOf(hourBranch);
	return `${GAN[(ganIdx + zhiIdx) % 10]}${hourBranch}`;
}

function buildBirthFallback(fields){
	if(!fields || !fields.date || !fields.time || !fields.date.value || !fields.time.value){
		return '';
	}
	try{
		return `${fields.date.value.format('YYYY-MM-DD')} ${fields.time.value.format('HH:mm:ss')}`;
	}catch(e){
		return '';
	}
}

function normalizeNongli(raw, fields){
	if(!raw || typeof raw !== 'object'){
		return null;
	}
	const out = cloneJson(raw) || {};
	if(!out.year){
		out.year = out.yearGanZi || out.yearJieqi || '';
	}
	if(!out.yearGanZi){
		out.yearGanZi = out.yearJieqi || out.year || '';
	}
	if(!out.yearJieqi){
		out.yearJieqi = out.yearGanZi || out.year || '';
	}
	if(!out.monthInt){
		out.monthInt = parseChineseMonthInt(out.month);
	}
	if(!out.dayInt){
		out.dayInt = parseChineseDayInt(out.day);
	}
	if(!out.time){
		out.time = out.timeGanZi || '';
	}
	if(!out.birth){
		out.birth = buildBirthFallback(fields);
	}
	if(!out.jiedelta && out.jieqi){
		out.jiedelta = `${out.jieqi}后第0天`;
	}
	if(!out.dayGanZi && fields && fields.date && fields.time && fields.date.value && fields.time.value){
		const y = parseInt(fields.date.value.format('YYYY'), 10);
		const m = parseInt(fields.date.value.format('MM'), 10);
		const d = parseInt(fields.date.value.format('DD'), 10);
		out.dayGanZi = getDayGanZhi(y, m, d);
	}
	if(!out.time && out.dayGanZi && fields && fields.time && fields.time.value){
		const hh = parseInt(fields.time.value.format('HH'), 10);
		out.time = getTimeGanZhiFromDay(out.dayGanZi, hh);
	}
	return out;
}

export function extractNongliFromChartWrap(chartWrap, fields){
	const chart = chartWrap && chartWrap.chart ? chartWrap.chart : chartWrap;
	const nongli = chart && chart.nongli ? chart.nongli : null;
	return normalizeNongli(nongli, fields);
}

function buildJieqiDate(year, termIndex){
	const baseUtcMs = Date.UTC(1900, 0, 6, 2, 5, 0);
	const ms = 31556925974.7 * (year - 1900) + S_TERM_INFO[termIndex] * 60000 + baseUtcMs;
	return new Date(ms);
}

export function buildLocalJieqiYearSeed(year, zone){
	const y = parseInt(year, 10);
	if(Number.isNaN(y)){
		return null;
	}
	const zoneMinutes = parseZoneMinutes(zone);
	const seed = {};
	for(let i=0; i<JIEQI_STD.length; i++){
		const term = JIEQI_STD[i];
		const dt = buildJieqiDate(y, i);
		const local = formatYmdHms(dt, zoneMinutes);
		seed[term] = {
			term,
			time: `${local.date} ${local.time}`,
			dateKey: local.date.replace(/-/g, ''),
			dayGanzhi: getDayGanZhi(local.year, local.month, local.day),
		};
	}
	return seed;
}

