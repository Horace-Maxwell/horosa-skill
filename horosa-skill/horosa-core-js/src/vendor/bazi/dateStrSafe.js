// 日期字符串安全解析(全年份域公共件)。
//
// 背景:DateTime.format('YYYY-MM-DD') 对公元前输出带前导负号的年('-7040-07-19'),
// 下游 `split('-')` 首元素为空 → 年=NaN/0、月=100、日错位;五位年在 `substr(0,4)` 类
// 截半('16799'→'1679')。本件是唯一正确解析真源:负号与位数全域安全。
// 口径:天文年连续(BC1=0? 否——本仓 ad/year 体系 BC1 表示为 -1,无 0 年;
// parseDateParts 返回的 year 即带符号"显示年"(-7040 表示公元前 7040)。

/** 'YYYY-MM-DD'|'-YYYY-MM-DD'|'YYYY/MM/DD'|含时间尾巴 → {year(带符号),month,day} 或 null。 */
export function parseDateParts(str){
	if(str === undefined || str === null){
		return null;
	}
	const s = String(str).trim().split(' ')[0].replace(/\//g, '-');
	const m = /^(-?)(\d{1,5})-(\d{1,2})-(\d{1,2})$/.exec(s);
	if(!m){
		return null;
	}
	const year = (m[1] === '-' ? -1 : 1) * parseInt(m[2], 10);
	const month = parseInt(m[3], 10);
	const day = parseInt(m[4], 10);
	if(!Number.isFinite(year) || month < 1 || month > 12 || day < 1 || day > 31){
		return null;
	}
	return { year, month, day };
}

/** 带符号年 → 'YYYY-MM-DD'(BC 输出前导负号;不足 4 位补零,5 位原样)。 */
export function formatSignedDate(year, month, day){
	const y = Math.abs(year);
	const ys = (year < 0 ? '-' : '') + String(y).padStart(4, '0');
	return `${ys}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

/** 从日期串安全取带符号年(替代 substr(0,4)/slice(0,4)/parseInt(split('-')[0]) 全家)。 */
export function parseYearFromDateStr(str){
	const p = parseDateParts(str);
	return p ? p.year : NaN;
}

// 「显示年」算术(无公元 0 年:公元前 1 年之后即公元 1 年)。直接 y + n / b − a 在跨纪元时多出一个不存在的 0 年
// (公元前出生、行运跨到公元的盘:流年表出现「0 年」、其后公元年份整体错一年、按年份定位流年错一格)。
const toAstroYear = (y)=>(y < 0 ? y + 1 : y);
const fromAstroYear = (a)=>(a <= 0 ? a - 1 : a);

/** 显示年 year 往后(n<0 往前)数 n 年 → 显示年。 */
export function addDisplayYears(year, n){
	const y = Number(year);
	const k = Number(n);
	if(!Number.isFinite(y) || !Number.isFinite(k)){
		return NaN;
	}
	return fromAstroYear(toAstroYear(y) + k);
}

/** 显示年 a 到 b 相隔的年数(b − a,跨纪元不多算)。 */
export function displayYearDiff(a, b){
	const x = Number(a);
	const y = Number(b);
	if(!Number.isFinite(x) || !Number.isFinite(y)){
		return NaN;
	}
	return toAstroYear(y) - toAstroYear(x);
}
