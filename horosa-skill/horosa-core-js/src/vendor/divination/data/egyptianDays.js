// 埃及凶日(Dies Aegyptiaci)·中世纪历书传统 24 日表(每月两日,公历月/日)。
// 低严重度:历书类禁忌,现代实务仅作提醒,不与盘面因素同权。
export const EGYPTIAN_DAYS = {
	1: [1, 25], 2: [4, 26], 3: [1, 28], 4: [10, 20], 5: [3, 25], 6: [10, 16],
	7: [13, 22], 8: [1, 30], 9: [3, 21], 10: [3, 22], 11: [5, 28], 12: [7, 22],
};

// dateStr 'YYYY-MM-DD' → 是否埃及凶日
export function isEgyptianDay(dateStr){
	const m = /^\s*-?\d{1,4}-(\d{1,2})-(\d{1,2})/.exec(String(dateStr || ''));
	if(!m) return false;
	const mo = parseInt(m[1], 10); const d = parseInt(m[2], 10);
	const days = EGYPTIAN_DAYS[mo];
	return !!(days && days.indexOf(d) >= 0);
}

export default EGYPTIAN_DAYS;
