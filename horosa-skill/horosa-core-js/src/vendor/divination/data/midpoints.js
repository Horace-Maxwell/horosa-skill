// divination/data/midpoints.js
// 中点（择日清单 §2.8）。A=B/C 表示 A 落 B、C 中点（结合三星之力，容许度 ≤3°，优先入相位）。
// 满足总则/分则后微调时令 Asc/MC 会合某吉中点。某点同时为 ≥4 星中点 → 极重要。

// 常用中点含义（节选；可扩充杨国正全表）
export const MIDPOINT_MEANINGS = {
	'sun/moon': { theme: '两性关系/阴阳平衡', supports: ['marriage'] },
	'sun/mercury': { theme: '心智/理解/知识/思想', supports: ['study'] },
	'sun/venus': { theme: '爱的感觉/美好/婚姻浪漫', supports: ['marriage'] },
	'sun/mars': { theme: '催贵/行动力', supports: ['career'] },
	'sun/jupiter': { theme: '幸运/成功/扩展', supports: ['career', 'marriage'] },
	'venus/jupiter': { theme: '喜悦/财富/和谐', supports: ['marriage', 'career'] },
	'mercury/jupiter': { theme: '良好判断/计划/合约', supports: ['business'] },
};

// 结婚吉中点（任一成立即加分）——以「行星图」记法表达，引擎按 Asc/MC/用事星命中判断。
export const MARRIAGE_MIDPOINTS = [
	'Venus = Mc/Sun', 'Venus = Mc/Jupiter',
	'Asc = Mc/Cupido', 'Venus = Sun/Cupido', 'Jupiter = Mc/Cupido',
	'Sun = Mc/Venus', 'Jupiter = Mc/Venus',
	'Asc = Sun/Mercury', 'Mercury = Sun/Mercury', 'Jupiter = Sun/Mercury',
	'Asc = Sun/Moon', 'NorthNode = Sun/Moon', 'Venus = Sun/Moon',
	'Mercury = Moon/Jupiter', 'Venus = Moon/Jupiter', 'Cupido = Moon/Jupiter',
];

// 创业吉中点
export const BUSINESS_MIDPOINTS = [
	'Moon = Mc/Aries', 'Jupiter = Mc/Aries', 'Apollon = Mc/Sun',
	'Sun = Jupiter/Aries', 'NorthNode = Jupiter/Mc',
	'Mc = Jupiter/Pluto', 'Sun = Jupiter/Moon (幸运的成功)',
	'Apollon = Sun/Jupiter', 'Mc = Aries/NorthNode',
];

// 两点经度求中点（近/远，相隔 180°）
export function midpointLon(a, b){
	const near = (((a + b) / 2) % 360 + 360) % 360;
	return [near, (near + 180) % 360];
}

export default MIDPOINT_MEANINGS;
