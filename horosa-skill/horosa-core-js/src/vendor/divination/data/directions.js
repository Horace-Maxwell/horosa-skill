// divination/data/directions.js
// 方位三套并存（卜卦构建清单 §1.7 + Dorotheus Ch36）：
//  1) 按宫位（事业方位）  2) 按星座元素（走失方向）  3) 按月亮所落四轴（逃跑方向）

// 1) 按宫位：1宫正东 → 10宫正南（顺数 12→10 向 MC 转南）
export const DIR_BY_HOUSE = {
	1: '东', 2: '东偏北', 3: '北偏东', 4: '北', 5: '北偏西', 6: '西偏北',
	7: '西', 8: '西偏南', 9: '南偏西', 10: '南', 11: '南偏东', 12: '东偏南',
};

// 2) 按星座元素：火=东/平野，风=西/高地，土=南/树林，水=北/潮湿
export const DIR_BY_ELEMENT = {
	fire: { dir: '东', terrain: '平野/高处干燥地' },
	air: { dir: '西', terrain: '高地/通风处' },
	earth: { dir: '南', terrain: '树林/田野/低地' },
	water: { dir: '北', terrain: '近水/潮湿处' },
};

// 3) 按月亮所落四轴象限（Dorotheus Ch36）：ASC–MC=东，MC–DSC=南，DSC–IC=西，IC–ASC=北
export function dirByMoonQuadrant(moonHouse){
	if(moonHouse >= 10 || moonHouse < 1) return '东';      // ASC..MC (10,11,12,1 区间近 ASC)
	if(moonHouse >= 7) return '南';                         // MC..DSC
	if(moonHouse >= 4) return '西';                         // DSC..IC
	return '北';                                            // IC..ASC
}

export default DIR_BY_ELEMENT;
