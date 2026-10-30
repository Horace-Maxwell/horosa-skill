import { Solar } from 'lunar-javascript';
import { isLunarJsYearReliable } from '../bazi/lunarDomainGuard.js';
import { bjShiftMinutes, shiftSolarMinutes } from './beijingTimeShift.js';
import { datePartOf, dateKeyOfStr } from '../bazi/dateStrSafe.js';

const GAN = '甲乙丙丁戊己庚辛壬癸'.split('');
const ZHI = '子丑寅卯辰巳午未申酉戌亥'.split('');
const JIAZI = [];
for(let i=0; i<60; i++){
	JIAZI.push(`${GAN[i % 10]}${ZHI[i % 12]}`);
}

const JIEQI_STD = [
	'小寒', '大寒', '立春', '雨水', '惊蛰', '春分',
	'清明', '谷雨', '立夏', '小满', '芒种', '夏至',
	'小暑', '大暑', '立秋', '处暑', '白露', '秋分',
	'寒露', '霜降', '立冬', '小雪', '大雪', '冬至',
];

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
		const date = solar.toYmd ? solar.toYmd() : datePartOf(time);
		seed[term] = {
			term,
			time,
			dateKey: dateKeyOfStr(date),
			dayGanzhi: getDayGanZhi(solar.getYear(), solar.getMonth(), solar.getDay()),
		};
	}
	return Object.keys(seed).length ? seed : null;
}
