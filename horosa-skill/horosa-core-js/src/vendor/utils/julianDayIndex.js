// 连续儒略日序(整数,含 1582-10-15 儒略→格里切换),供日干支/日序 60/28 循环使用。
//
// 🔴 JS `Date.UTC` / `new Date(y,m,d)` 是 proleptic Gregorian(格里高利历向古无限外推),对 1582
// 年前(尤其公元前)与真实历法(儒略历)日序偏差可达数十日 → 60 甲子日干支、28 宿全错。本函数与
// 后端权威 extreme_pillars / getOnlyDateNum 同轴(1582 前儒略、之后格里),使 BC/远古盘的流日、
// 大运、流月日干支与主盘四柱口径完全一致(杜绝「主盘己卯、流日面板算成别的」跨面板矛盾)。
//
// year = 带符号显示年(公元前为负、无 0 年);内部转天文年(BC1=0)。现代域(1582 后)与旧 Date.UTC
// 相差一个常数,做「相对差」(日序循环 mod 60/28)时逐日等价 → 零回归。
export function julianDayIndex(year, month, day){
	const ay = year < 0 ? year + 1 : year;
	const a = Math.floor((14 - month) / 12);
	const y = ay + 4800 - a;
	const m = month + 12 * a - 3;
	const isGreg = year > 1582 || (year === 1582 && (month > 10 || (month === 10 && day >= 15)));
	if(isGreg){
		return day + Math.floor((153 * m + 2) / 5) + 365 * y + Math.floor(y / 4) - Math.floor(y / 100) + Math.floor(y / 400) - 32045;
	}
	return day + Math.floor((153 * m + 2) / 5) + 365 * y + Math.floor(y / 4) - 32083;
}

// 便捷:从 JS Date 取(带符号)年月日算日序。⚠️ JS Date 对 BC 用负年、月 0-based,此处 +1 归一。
export function julianDayIndexOfDate(date){
	return julianDayIndex(date.getFullYear(), date.getMonth() + 1, date.getDate());
}

export default julianDayIndex;
