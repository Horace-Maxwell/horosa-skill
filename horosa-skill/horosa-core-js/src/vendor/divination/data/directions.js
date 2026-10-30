// divination/data/directions.js
// 方位两套并存（卜卦构建清单 §1.7 + Dorotheus Ch36）：
//  1) 按星座元素（走失方向）  2) 按月亮所落四轴（逃跑方向）

// 1) 按星座元素：火=东/平野，风=西/高地，土=南/树林，水=北/潮湿
export const DIR_BY_ELEMENT = {
	fire: { dir: '东', terrain: '平野/高处干燥地' },
	air: { dir: '西', terrain: '高地/通风处' },
	earth: { dir: '南', terrain: '树林/田野/低地' },
	water: { dir: '北', terrain: '近水/潮湿处' },
};

// 2) 按月亮所落四轴象限（Dorotheus Ch36）：ASC–MC=东，MC–DSC=南，DSC–IC=西，IC–ASC=北
export function dirByMoonQuadrant(moonHouse){
	if(moonHouse >= 10 || moonHouse < 1) return '东';      // ASC..MC (10,11,12,1 区间近 ASC)
	if(moonHouse >= 7) return '南';                         // MC..DSC
	if(moonHouse >= 4) return '西';                         // DSC..IC
	return '北';                                            // IC..ASC
}

export default DIR_BY_ELEMENT;
