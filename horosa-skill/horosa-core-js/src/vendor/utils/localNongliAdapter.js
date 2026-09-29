import { Solar } from 'lunar-javascript';
import { isLunarJsYearReliable } from '../bazi/lunarDomainGuard.js';
import { bjShiftMinutes, shiftSolarMinutes } from './beijingTimeShift.js';

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

export function getOnlyDateNum(year, month, day){
	let a = Math.floor((14 - month) / 12);
	let y = year + 4800 - a;
	let m = month + 12 * a - 3;
	// 🔴 1582-10-15 儒略→格里切换:此前恒用格里公式(-32045),对 1582 前(尤其公元前)与真实儒略历
	// 日序偏差数十日 → 日柱错(远程农历桥 getDayGanZhi 所有域外技法 BC 日柱偏,如神数正传日柱辛亥
	// 应己卯)。year 为天文年(公元前为负);含切换后与后端 extreme_pillars/_jdn 逐日同轴。
	const isGreg = year > 1582 || (year === 1582 && (month > 10 || (month === 10 && day >= 15)));
	if(isGreg){
		return day + Math.floor((153 * m + 2) / 5) + 365 * y + Math.floor(y / 4) - Math.floor(y / 100) + Math.floor(y / 400) - 32045;
	}
	return day + Math.floor((153 * m + 2) / 5) + 365 * y + Math.floor(y / 4) - 32083;
}

export function getDayGanZhi(year, month, day){
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

export function buildLocalJieqiYearSeed(year, zone){
	const y = parseInt(year, 10);
	if(Number.isNaN(y)){
		return null;
	}
	// lunar-javascript 可靠域外(AD1~9999 之外)节气表静默错位 → 返 null 走后端实算,绝不出错种子
	if(!isLunarJsYearReliable(y)){
		return null;
	}
	const seed = {};
	let table = null;
	try{
		table = Solar.fromYmd(y, 7, 1).getLunar().getJieQiTable();
	}catch(e){
		table = null;
	}
	// 节气表按北京时间编;非东八区把交节时刻折成当地钟表、交节日干支按当地日期(与后端 /jieqi/year 同口径)。
	// 使用方(奇门当前节气 / 节气页本地回退 / 奇门择日扫描 / AI 挂载)都拿它与当地钟表比较。东八区平移 0 → 逐字节不变。
	const toLocal = -bjShiftMinutes(zone);
	for(let i=0; i<JIEQI_STD.length; i++){
		const term = JIEQI_STD[i];
		const bjSolar = table && table[term] ? table[term] : null;
		if(!bjSolar || !bjSolar.toYmdHms){
			continue;
		}
		const solar = toLocal ? shiftSolarMinutes(bjSolar, toLocal) : bjSolar;
		const time = solar.toYmdHms();
		const date = solar.toYmd ? solar.toYmd() : time.substring(0, 10);
		seed[term] = {
			term,
			time,
			dateKey: date.replace(/-/g, ''),
			dayGanzhi: getDayGanZhi(solar.getYear(), solar.getMonth(), solar.getDay()),
		};
	}
	return Object.keys(seed).length ? seed : null;
}
