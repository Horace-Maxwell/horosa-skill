// divination/lifespan/lifespanData.js
// 古典寿命格局（Hyleg 生命主 / Alcocoden 寿主星 / 盘主体系）所需常量。
// 算法依据：Ptolemy《四部星经》、Dorotheus《Carmen》、Alcabitius《占星判断原理》、Bonatti。
// 与卜卦/择日同源，复用 divination/data 的尊贵表，确保口径一致。

// 行星寿数（年）：大限 greatest / 中限 mean / 小限 least。
// 标准值（多家一致；mean 取大小限半和的通行值）。
export const PLANETARY_YEARS = {
	saturn: { greatest: 57, mean: 43.5, least: 30 },
	jupiter: { greatest: 79, mean: 45.5, least: 12 },
	mars: { greatest: 66, mean: 40.5, least: 15 },
	sun: { greatest: 120, mean: 69.5, least: 19 },
	venus: { greatest: 82, mean: 45, least: 8 },
	mercury: { greatest: 76, mean: 48, least: 20 },
	moon: { greatest: 108, mean: 66.5, least: 25 },
};

// 各作者「释放位」（aphetic places）允许的宫位与权重。
// rank 越大越权威（用于多候选竞争与展示排序）。
export const APHETIC_RULES = {
	// 托勒密：仅 10 / 1 / 11 / 7 / 9，权重 10>1>11>7>9；地平下（除正升起）及 8、12 一律排除。
	ptolemy: {
		houses: { 10: 5, 1: 4, 11: 3, 7: 2, 9: 1 },
		useGenderQuadrant: false,
		fiveDegreeRule: false,
	},
	// 阿尔卡比修斯：10/11 任意星座；7/8/9 须阳性星座（昼）/阴性星座（夜，对月）；上升前 5° 视作入命；果宫(3/6/12)否。
	alcabitius: {
		houses: { 10: 5, 1: 4, 11: 3, 7: 2, 8: 1, 9: 1 },
		genderHouses: [7, 8, 9],      // 这些宫须星座性别与发光体宗派相符
		useGenderQuadrant: false,
		fiveDegreeRule: true,
	},
	// 多罗修斯：托勒密诸位 + 阴阳星座×阴阳象限双合；effeminatus（太阳落阴性星座+阴性象限）否；含降级查找。
	dorotheus: {
		houses: { 10: 5, 1: 4, 11: 3, 7: 2, 9: 1 },
		useGenderQuadrant: true,
		fiveDegreeRule: false,
		downgrade: true,            // 选中后若无寿主星则弃之顺位下移
	},
};

// 候选释放点的选取顺序（按宗派）。asc/fortune/syzygy 为点，其余为发光体。
export const HYLEG_CANDIDATE_ORDER = {
	day: ['sun', 'moon', 'asc', 'fortune', 'syzygy'],
	night: ['moon', 'sun', 'asc', 'fortune', 'syzygy'],
};

// 寿主星寿数修正：吉星/凶星与「寿主星」成相位时增减其「小限年数」。
// 通行口径（al-Biruni/Bonatti）：吉星加、凶星减；硬相位(合/刑/冲)加重凶性、柔相位(拱/六合)加重吉性。
// 实现：吉星 柔相位 +least、硬相位 +least/2；凶星 硬相位 −least、柔相位 −least/2。
export const SOFT_ASPECTS = [60, 120];
export const HARD_ASPECTS = [0, 90, 180];

// 宫位 → 寿数档（角宫=大限 / 续宫=中限 / 果宫=小限）。
export function yearsBandForAngularity(angularity){
	if(angularity === 'angular') return 'greatest';
	if(angularity === 'succedent') return 'mean';
	return 'least';
}

export default PLANETARY_YEARS;
