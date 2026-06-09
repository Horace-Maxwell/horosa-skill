import * as AstroConst from '../../constants/AstroConst.js';
import * as AstroText from '../../constants/AstroText.js';

// headless 守卫：SZConst 在模块加载时读 localStorage 取「盘形/起宫制」偏好。skill 的 JS 恒在 headless
// node 跑（无浏览器持久化），且 node 实验性全局 localStorage 无 --localstorage-file 会抛 → 一律用空
// shim 回退默认（方盘 / 八字起宫）。仅影响 UI 偏好，不影响政余格局闭包用到的纯数据表。
const localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };

export const SZChart_NoExternChart = 0;
export const SZChart_SignChart = 1;
export const SZChart_BaGuaChart = 2;
export const SZChart_DunJiaChart = 3;
export const SZChart_TaiYiChart = 4;
export const SZChart_FangWeiChart = 5;
export const SZChart_FengYeChart = 6;
export const SZChart_NiXiangChart = 7;

const DefaultFillColor = 'var(--horosa-suzhan-fill, #fefeef)';

export const SZChart_Circle = 0;
export const SZChart_Square = 1;
export const SZHouseStart_Bazi = 0;
export const SZHouseStart_ASC = 1;

let chartshape = localStorage.getItem('suzhanChartShape');
if(chartshape === undefined || chartshape === null){
	chartshape = SZChart_Square;
}else{
	try{
		chartshape = parseInt(chartshape);
	}catch(e){
		chartshape = SZChart_Square;
	}
}

let houseStartMode = localStorage.getItem('suzhanHouseStartMode');
if(houseStartMode === undefined || houseStartMode === null){
	houseStartMode = SZHouseStart_Bazi;
}else{
	try{
		houseStartMode = parseInt(houseStartMode, 10);
	}catch(e){
		houseStartMode = SZHouseStart_Bazi;
	}
}
if(houseStartMode !== SZHouseStart_ASC){
	houseStartMode = SZHouseStart_Bazi;
}

export const SZChart = {
	chart: SZChart_SignChart,
	shape: chartshape,
	houseStartMode: houseStartMode,
};

export const SZFengYe = [
	['鲁', '·', '徐', '州', AstroText.AstroMsg[AstroConst.ARIES]], 
	['赵', '·', '冀', '州', AstroText.AstroMsg[AstroConst.TAURUS]], 
	['魏', '·', '司', '州', AstroText.AstroMsg[AstroConst.GEMINI]], 
	['秦', '·', '雍', '州', AstroText.AstroMsg[AstroConst.CANCER]], 
	['周', '·', '三', '河', AstroText.AstroMsg[AstroConst.LEO]], 
	['楚', '·', '荆', '州', AstroText.AstroMsg[AstroConst.VIRGO]], 
	['郑', '·', '兖', '州', AstroText.AstroMsg[AstroConst.LIBRA]], 
	['宋', '·', '豫', '州', AstroText.AstroMsg[AstroConst.SCORPIO]], 
	['燕', '·', '幽', '州', AstroText.AstroMsg[AstroConst.SAGITTARIUS]], 
	['吴', '越·', '扬', '州', AstroText.AstroMsg[AstroConst.CAPRICORN]], 
	['齐', '·', '青', '州', AstroText.AstroMsg[AstroConst.AQUARIUS]], 
	['魏', '·', '并', '州', AstroText.AstroMsg[AstroConst.PISCES]]
];

export const SZSigns = [
	['降', '娄', '|', '戌', AstroText.AstroMsg[AstroConst.ARIES]], 
	['大', '梁', '|', '酉', AstroText.AstroMsg[AstroConst.TAURUS]], 
	['实', '沉', '|', '申', AstroText.AstroMsg[AstroConst.GEMINI]], 
	['鹑', '首', '--', '未', AstroText.AstroMsg[AstroConst.CANCER]], 
	['鹑', '火', '--', '午', AstroText.AstroMsg[AstroConst.LEO]], 
	['鹑', '尾', '--', '巳', AstroText.AstroMsg[AstroConst.VIRGO]], 
	['寿', '星', '|', '辰', AstroText.AstroMsg[AstroConst.LIBRA]], 
	['大', '火', '|', '卯', AstroText.AstroMsg[AstroConst.SCORPIO]], 
	['析', '木', '|', '寅', AstroText.AstroMsg[AstroConst.SAGITTARIUS]], 
	['星', '纪', '--', '丑', AstroText.AstroMsg[AstroConst.CAPRICORN]], 
	['玄', '枵', '--', '子', AstroText.AstroMsg[AstroConst.AQUARIUS]], 
	['娵', '訾', '--', '亥', AstroText.AstroMsg[AstroConst.PISCES]]
];

export const SZFengYeCircle = [
	['鲁', '徐', '州', AstroText.AstroMsg[AstroConst.ARIES]], 
	['赵', '冀', '州', AstroText.AstroMsg[AstroConst.TAURUS]], 
	['魏', '司', '州', AstroText.AstroMsg[AstroConst.GEMINI]], 
	['秦', '雍', '州', AstroText.AstroMsg[AstroConst.CANCER]], 
	['周', '三', '河', AstroText.AstroMsg[AstroConst.LEO]], 
	['楚', '荆', '州', AstroText.AstroMsg[AstroConst.VIRGO]], 
	['郑', '兖', '州', AstroText.AstroMsg[AstroConst.LIBRA]], 
	['宋', '豫', '州', AstroText.AstroMsg[AstroConst.SCORPIO]], 
	['燕', '幽', '州', AstroText.AstroMsg[AstroConst.SAGITTARIUS]], 
	['吴越', '扬', '州', AstroText.AstroMsg[AstroConst.CAPRICORN]], 
	['齐', '青', '州', AstroText.AstroMsg[AstroConst.AQUARIUS]], 
	['魏', '并', '州', AstroText.AstroMsg[AstroConst.PISCES]]
];

export const SZFengYeBySu = {
	'Aries': {name: ['鲁', '徐', '州'], su: ['奎', '娄'], next: '胃', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Taurus': {name: ['赵', '冀', '州'], su: ['胃', '昴', '毕'], next: '觜', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Gemini': {name: ['魏', '司', '州'], su: ['觜', '参'], next: '井', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Cancer': {name: ['秦', '雍', '州'], su: ['井', '鬼'], next: '柳', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Leo': {name: ['周', '三', '河'], su: ['柳', '星', '张'], next: '翼', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Virgo': {name: ['楚', '荆', '州'], su: ['翼', '轸'], next: '角', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Libra': {name: ['郑', '兖', '州'], su: ['角', '亢'], next: '氐', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Scorpio': {name: ['宋', '豫', '州'], su: ['氐', '房', '心'], next: '尾', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Sagittarius': {name: ['燕', '幽', '州'], su: ['尾', '箕'], next: '斗', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Capricorn': {name: ['吴', '越', '扬', '州'], su: ['斗', '牛'], next: '女', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Aquarius': {name: ['齐', '青', '州'], su: ['女', '虚', '危'], next: '室', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Pisces': {name: ['魏', '并', '州'], su: ['室', '壁'], next: '奎', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
};

export const SZSignsCircle = [
	['戌', '降', '娄', AstroText.AstroMsg[AstroConst.ARIES]], 
	['酉', '大', '梁', AstroText.AstroMsg[AstroConst.TAURUS]], 
	['申', '实', '沉', AstroText.AstroMsg[AstroConst.GEMINI]], 
	['未', '鹑', '首', AstroText.AstroMsg[AstroConst.CANCER]], 
	['午', '鹑', '火', AstroText.AstroMsg[AstroConst.LEO]], 
	['巳', '鹑', '尾', AstroText.AstroMsg[AstroConst.VIRGO]], 
	['辰', '寿', '星', AstroText.AstroMsg[AstroConst.LIBRA]], 
	['卯', '大', '火', AstroText.AstroMsg[AstroConst.SCORPIO]], 
	['寅', '析', '木', AstroText.AstroMsg[AstroConst.SAGITTARIUS]], 
	['丑', '星', '纪', AstroText.AstroMsg[AstroConst.CAPRICORN]], 
	['子', '玄', '枵', AstroText.AstroMsg[AstroConst.AQUARIUS]], 
	['亥', '娵', '訾', AstroText.AstroMsg[AstroConst.PISCES]]
];

export const SZDirectCircle = [
	['西', '之', '北', AstroText.AstroMsg[AstroConst.ARIES]], 
	['正', '西', ' ', AstroText.AstroMsg[AstroConst.TAURUS]], 
	['西', '之', '南', AstroText.AstroMsg[AstroConst.GEMINI]], 
	['南', '之', '西', AstroText.AstroMsg[AstroConst.CANCER]], 
	['正', '南', ' ', AstroText.AstroMsg[AstroConst.LEO]], 
	['南', '之', '东', AstroText.AstroMsg[AstroConst.VIRGO]], 
	['东', '之', '南', AstroText.AstroMsg[AstroConst.LIBRA]], 
	['正', '东', ' ', AstroText.AstroMsg[AstroConst.SCORPIO]], 
	['东', '之', '北', AstroText.AstroMsg[AstroConst.SAGITTARIUS]], 
	['北', '之', '东', AstroText.AstroMsg[AstroConst.CAPRICORN]], 
	['正', '北', ' ', AstroText.AstroMsg[AstroConst.AQUARIUS]], 
	['北', '之', '西', AstroText.AstroMsg[AstroConst.PISCES]]
];

export const SZInverseDirectCircle = [
	['东', '之', '南', AstroText.AstroMsg[AstroConst.ARIES]], 
	['正', '东', ' ', AstroText.AstroMsg[AstroConst.TAURUS]], 
	['东', '之', '北', AstroText.AstroMsg[AstroConst.GEMINI]], 
	['北', '之', '东', AstroText.AstroMsg[AstroConst.CANCER]], 
	['正', '北', ' ', AstroText.AstroMsg[AstroConst.LEO]], 
	['北', '之', '西', AstroText.AstroMsg[AstroConst.VIRGO]], 
	['西', '之', '北', AstroText.AstroMsg[AstroConst.LIBRA]], 
	['正', '西', ' ', AstroText.AstroMsg[AstroConst.SCORPIO]], 
	['西', '之', '南', AstroText.AstroMsg[AstroConst.SAGITTARIUS]], 
	['南', '之', '西', AstroText.AstroMsg[AstroConst.CAPRICORN]], 
	['正', '南', ' ', AstroText.AstroMsg[AstroConst.AQUARIUS]], 
	['南', '之', '东', AstroText.AstroMsg[AstroConst.PISCES]]
];

export const SZDirectBySu = {
	'Aries': {name: ['西', '之', '北'], su: ['奎', '娄', '胃'], next: '昴', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Taurus': {name: ['西'], su: ['昴'], next: '毕', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Gemini': {name: ['西', '之', '南'], su: ['毕', '觜', '参'], next: '井', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Cancer': {name: ['南', '之', '西'], su: ['井', '鬼', '柳'], next: '星', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Leo': {name: ['南'], su: ['星'], next: '张', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Virgo': {name: ['南', '之', '东'], su: ['张', '翼', '轸'], next: '角', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Libra': {name: ['东', '之', '南'], su: ['角', '亢', '氐'], next: '房', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Scorpio': {name: ['东'], su: ['房'], next: '心', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Sagittarius': {name: ['东', '之', '北'], su: ['心', '尾', '箕'], next: '斗', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Capricorn': {name: ['北', '之', '东'], su: ['斗', '牛', '女'], next: '虚', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Aquarius': {name: ['北'], su: ['虚', '危'], next: '危', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Pisces': {name: ['北', '之', '西'], su: ['危', '室', '壁'], next: '奎', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
};

export const SZInverseDirectBySu = {
	'Aries': {name: ['东', '之', '南'], su: ['奎', '娄', '胃'], next: '昴', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Taurus': {name: ['东'], su: ['昴'], next: '毕', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Gemini': {name: ['东', '之', '北'], su: ['毕', '觜', '参'], next: '井', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Cancer': {name: ['北', '之', '东'], su: ['井', '鬼', '柳'], next: '星', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Leo': {name: ['北'], su: ['星'], next: '张', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Virgo': {name: ['北', '之', '西'], su: ['张', '翼', '轸'], next: '角', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Libra': {name: ['西', '之', '北'], su: ['角', '亢', '氐'], next: '房', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Scorpio': {name: ['西'], su: ['房'], next: '心', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Sagittarius': {name: ['西', '之', '南'], su: ['心', '尾', '箕'], next: '斗', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Capricorn': {name: ['南', '之', '西'], su: ['斗', '牛', '女'], next: '虚', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Aquarius': {name: ['南'], su: ['虚', '危'], next: '危', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'Pisces': {name: ['南', '之', '东'], su: ['危', '室', '壁'], next: '奎', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
};

export const SZBaGuaSu = {
	'乾': {su: ['室', '壁', '奎', '娄'], next: '胃', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'兑': {su: ['胃', '昴', '毕'], next: '觜', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'坤': {su: ['觜', '参', '井', '鬼'], next: '柳', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'离': {su: ['柳', '星', '张'], next: '翼', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'巽': {su: ['翼', '轸', '角', '亢'], next: '氐', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'震': {su: ['氐', '房', '心'], next: '尾', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'艮': {su: ['尾', '箕', '斗', '牛'], next: '女', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'坎': {su: ['女', '虚', '危'], next: '室', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
};

export const SZDunJiaSu = {
	'开': {su: ['室', '壁', '奎', '娄'], next: '胃', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'惊': {su: ['胃', '昴', '毕'], next: '觜', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'死': {su: ['觜', '参', '井', '鬼'], next: '柳', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'景': {su: ['柳', '星', '张'], next: '翼', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'杜': {su: ['翼', '轸', '角', '亢'], next: '氐', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'伤': {su: ['氐', '房', '心'], next: '尾', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'生': {su: ['尾', '箕', '斗', '牛'], next: '女', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'休': {su: ['女', '虚', '危'], next: '室', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
};

export const SZTaiYiSu = {
	'乾': {su: ['壁', '奎'], next: '娄', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'戌': {su: ['娄', '胃'], next: '昴', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'酉': {su: ['昴'], next: '毕', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'申': {su: ['毕', '觜'], next: '参', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'坤': {su: ['参', '井'], next: '鬼', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'未': {su: ['鬼', '柳'], next: '星', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'午': {su: ['星'], next: '张', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'巳': {su: ['张', '翼'], next: '轸', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'巽': {su: ['轸', '角'], next: '亢', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'辰': {su: ['亢', '氐'], next: '房', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'卯': {su: ['房'], next: '心', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'寅': {su: ['心', '尾'], next: '箕', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'艮': {su: ['箕', '斗'], next: '牛', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'丑': {su: ['牛', '女'], next: '虚', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'子': {su: ['虚'], next: '危', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
	'亥': {su: ['危', '室'], next: '壁', color: AstroConst.AstroColor.Stroke, fillColor: DefaultFillColor},
};

export const SZSignsColor = [
	AstroConst.AstroColor['Aries'],
	AstroConst.AstroColor['Taurus'],
	AstroConst.AstroColor['Gemini'],
	AstroConst.AstroColor['Cancer'],
	AstroConst.AstroColor['Leo'],
	AstroConst.AstroColor['Virgo'],
	AstroConst.AstroColor['Libra'],
	AstroConst.AstroColor['Scorpio'],
	AstroConst.AstroColor['Sagittarius'],
	AstroConst.AstroColor['Capricorn'],
	AstroConst.AstroColor['Aquarius'],
	AstroConst.AstroColor['Pisces']
];

export const BaGua = [
	['乾'], ['坎'], ['艮'], ['震'], 
	['巽'], ['离'], ['坤'], ['兑']
];

export const DunJia = [
	['开', '门'], ['休', '门'], ['生', '门'], ['伤', '门'], 
	['杜', '门'], ['景', '门'], ['死', '门'], ['惊', '门']
];

export const TaiYi = [
	['乾'], ['亥'], ['子'], ['丑'], 
	['艮'], ['寅'], ['卯'], ['辰'],  
	['巽'], ['巳'], ['午'], ['未'], 
	['坤'], ['申'], ['酉'], ['戌']
];

export const FangWei = [
	['西', '之', '北'], ['西'], ['西', '之', '南'], 
	['南', '之', '西'], ['南'], ['南', '之', '东'], 
	['东', '之', '南'], ['东'], ['东', '之', '北'],
	['北', '之', '东'], ['北'], ['北', '之', '西'] 
];

export const NiXiang = [
	['东', '之', '南'], ['东'], ['东', '之', '北'],
	['北', '之', '东'], ['北'], ['北', '之', '西'], 
	['西', '之', '北'], ['西'], ['西', '之', '南'], 
	['南', '之', '西'], ['南'], ['南', '之', '东'], 
];

export const ZiSign = {
	'子': AstroConst.AQUARIUS,
	'丑': AstroConst.CAPRICORN,
	'寅': AstroConst.SAGITTARIUS,
	'卯': AstroConst.SCORPIO,
	'辰': AstroConst.LIBRA,
	'巳': AstroConst.VIRGO,
	'午': AstroConst.LEO,
	'未': AstroConst.CANCER,
	'申': AstroConst.GEMINI,
	'酉': AstroConst.TAURUS,
	'戌': AstroConst.ARIES,
	'亥': AstroConst.PISCES,
};

export const SignZi = {};
SignZi[AstroConst.AQUARIUS] = '子';
SignZi[AstroConst.CAPRICORN] = '丑';
SignZi[AstroConst.SAGITTARIUS] = '寅';
SignZi[AstroConst.SCORPIO] = '卯';
SignZi[AstroConst.LIBRA] = '辰';
SignZi[AstroConst.VIRGO] = '巳';
SignZi[AstroConst.LEO] = '午';
SignZi[AstroConst.CANCER] = '未';
SignZi[AstroConst.GEMINI] = '申';
SignZi[AstroConst.TAURUS] = '酉';
SignZi[AstroConst.ARIES] = '戌';
SignZi[AstroConst.PISCES] = '亥';

export function getHouseColor(i){
	let sig = AstroConst.LIST_SIGNS[i];
	return AstroConst.AstroColor.SignFill[sig];
}

export function getSigColor(i){
	let sig = AstroConst.LIST_SIGNS[i];
	return AstroConst.AstroColor[sig];
}
