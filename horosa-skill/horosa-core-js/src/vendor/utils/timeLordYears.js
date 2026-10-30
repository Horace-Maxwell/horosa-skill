// 时主类星运(129 年系统 / Balbillus)共用的年长:一期的天数 = 年数 × 年长。
// 键名沿用旧保存值(solar / hellenistic),新加的四档按传统名称取值。
export const TIME_LORD_YEAR_TYPES = {
	solar: { days: 365.242199, label: '回归年（365.2422 日）' },
	sidereal: { days: 365.256363, label: '恒星年（365.2564 日）' },
	hellenistic: { days: 360, label: '埃及 / 希腊化年（360 日）' },
	abumashar: { days: 365.25833, label: 'Abu Ma\'shar 年（365.2583 日）' },
	mashaallah: { days: 365.259028, label: 'Masha\'allah 年（365.2590 日）' },
	bija: { days: 366.256399, label: 'Bija 修正年（366.2564 日）' },
};
export const DEFAULT_TIME_LORD_YEAR = 'solar';

export function timeLordYearDays(key){
	return (TIME_LORD_YEAR_TYPES[key] || TIME_LORD_YEAR_TYPES[DEFAULT_TIME_LORD_YEAR]).days;
}
