// 干支年基准（立春界）单一真值源。
//
// 🔴 病灶（2026-07-31 用户实测·河洛理数流年整体错一年）：术数技法的「第 N 岁流年」必须
// 以**干支年**为基准，而不是出生的**公历年**。二者只在立春后才重合——立春前出生者，
// 公历年已跨到新年、干支年还没跨，直接拿 `parseYearFromDateStr(生日)` 当 base 就整体错一位
// （2026-01-31 出生：公历 2026、干支年却是乙巳＝2025；流年首年给成丙午而非乙巳）。
// 同一条旧公式 `(y-4)%10` 早在 reportPipeline 被钉死过（reportTimeAnchor.test.js），
// 但河洛/参评这两条链没吃到那次修。
//
// 口径：不自己判立春——**从八字引擎已算好的年柱反推**。年柱出自 lunar-javascript 的
// `getYearInGanZhiExact()`（立春**交节时刻**界，比"按日期查立春"更严），且已过真太阳时
// (timeAlg) 校正，是全仓最可信的干支年真值；本件只做「干支 → 公历年」的一步映射。

const GANS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const ZHIS = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];

/** 公历年 → 该年（立春后）的年干支。注意：反向用途才安全，勿拿生日公历年当干支年。 */
export function ganzhiOfSolarYear(year){
	const y = Number(year);
	if(!Number.isFinite(y)){ return ''; }
	return GANS[((y - 4) % 10 + 10) % 10] + ZHIS[((y - 4) % 12 + 12) % 12];
}

/**
 * 干支年基准：由「出生公历年 + 已算好的年柱」定出该干支年对应的公历年。
 * 立春后出生 → 返回 approxYear 自身；立春前出生 → 返回 approxYear - 1。
 * 年柱缺失/异常时原样返回 approxYear（宁可退回旧行为，绝不抛）。
 *
 * @param {number} approxYear 出生公历年（parseYearFromDateStr 的产物）
 * @param {string} yearPillar 年柱干支（如 '乙巳'），须来自八字引擎
 * @returns {number} 干支年基准（公历年数）
 */
export function ganzhiYearBase(approxYear, yearPillar){
	const base = Number(approxYear);
	if(!Number.isFinite(base) || !base){ return base || 0; }
	const gz = String(yearPillar || '').trim();
	if(gz.length < 2){ return base; }
	// 立春界最多差一年：本年 → 前一年 → 后一年（后者防未来口径变动，仍恒等收敛）
	for(const delta of [0, -1, 1]){
		if(ganzhiOfSolarYear(base + delta) === gz){ return base + delta; }
	}
	return base;
}

export default ganzhiYearBase;
