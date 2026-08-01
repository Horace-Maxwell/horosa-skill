// 紫微「传本/流派」排盘开关（可变单例，镜像 ZWConst.ZWSchool 模式；默认＝现状零回归）。
// 任一项非默认 → ZiWeiMain.requestZiWei 走本地 ZiweiCalc 引擎(Java 不支持这些开关);全默认 → 仍走 Java(字节零回归)。
export const ZWEngineOptions = {
	daxianSpan: 10,        // 10=三合10年(默认) / 'ju'=钦天局数年
	tianmaBasis: 'month',  // month=现状月马(默认) / year=年支三合马
	starSet: 'full',       // full=全星(默认) / north18=精简18星(河洛)
	sanPan: 'tian',        // tian=天盘(默认) / di=地盘 / ren=人盘(中州三盘观察法)
	shangShi: 'fixed',     // fixed=天伤交友/天使疾厄(默认) / yinyang=中州派阴阳互换(仅阴男阳女对调,古法§6)
	leapMonth: 'mid_split',// 闰月归月:mid_split 十五分界(默认=现状) / next 整月归下月 / prev 整月归上月(§1.5)
	lateZi: 'zi_chu',      // 晚子时:zi_chu 子初换日(默认) / midnight_split 夜子折中 / zi_zheng 子正换日(§1.3)
	yearBoundary: 'lichun',// 定年界线:lichun 立春(默认=现状) / lunar_1_1 正月初一(§1.6)
	huoling: 'sanhe',      // 火铃:sanhe 三合通行(默认=现状,年支+生时顺数) / nanpai 南派(忽略生时·固定子)(§1.6)
	kongNaming: 'modern',  // 空劫命名:modern 地空地劫(默认) / book 时系逆行星作天空(古本《全书》,互斥去年支独立天空)(§5)
	brightnessSource: 'zi_jian', // 亮度源:zi_jian 自建(默认=现状,≈通行) / quanshu《全书》delta 覆盖(擎羊子酉旺/铃星独立表/亥卯未火星得)(§4.5/A.7)
	// ── 显示层 overlay 开关(纯后处理,不改安星,故【不】进 ziweiNeedsLocalEngine;默认全关=零回归) ──
	childLimit: false,     // 童限:上大限前逐岁本命宫(命财疾妻福官),右栏运限顶轴显示(§8.6)
	zhongxian: false,      // 沈氏三限:大限细分4段中限各2.5年(沈氏派)(§9.14)
	huoPan: false,         // 活盘:点任意宫为太极点重排人事宫名(透派/占验)(§9.9/9.11)
	qishuWei: false,       // 河洛气数位:官禄宫干四化回照+一六共宗(河洛派)(§9.10)
	borrowPalace: false,   // 中州借宫:空宫借对宫十四正曜(中州派)(§9.2.4)
	taiSuiRuGua: false,    // 紫云太岁入卦:关系人生肖落同支宫(紫云派)(§9.3)
	taiSuiRelatives: [],   // 紫云关系人列表 [{branch,role,sex}](随盘存)
};

// 是否需要走本地引擎(任一开关非默认,或流派 preset 非现状)。四化版(beipai/zhongzhou/quanshu)单独走 getActiveSiHuaGan，
// 不在此触发本地(四化是前端 getSiHua 渲染层，转/Java 盘皆可)。
export function ziweiNeedsLocalEngine(){
	return ZWEngineOptions.daxianSpan !== 10
		|| ZWEngineOptions.tianmaBasis !== 'month'
		|| ZWEngineOptions.starSet !== 'full'
		|| ZWEngineOptions.sanPan !== 'tian'
		|| ZWEngineOptions.shangShi !== 'fixed'
		|| ZWEngineOptions.leapMonth !== 'mid_split'
		|| ZWEngineOptions.lateZi !== 'zi_chu'
		|| ZWEngineOptions.yearBoundary !== 'lichun'
		|| ZWEngineOptions.huoling !== 'sanhe'
		|| ZWEngineOptions.kongNaming !== 'modern';
	// ⚠️ brightnessSource 不进此判据:亮度是纯显示层(庙旺 delta 覆盖,ZWCommHouse.effStarLight),
	//    绝不触发本地引擎重排——否则会连带把命主等按本地口径重算,切亮度竟改命主(实测坑)。
}

// 选项常量(左栏下拉用)
export const DAXIAN_SPAN_OPTIONS = [
	{ value: 10, label: '10 年(三合·默认)' },
	{ value: 'ju', label: '局数年(钦天)' },
];
export const TIANMA_BASIS_OPTIONS = [
	{ value: 'month', label: '月马(现状)' },
	{ value: 'year', label: '年支三合马' },
];
export const STAR_SET_OPTIONS = [
	{ value: 'full', label: '全星系(默认)' },
	{ value: 'north18', label: '精简18星(河洛)' },
];
export const SANPAN_OPTIONS = [
	{ value: 'tian', label: '天盘(本命)' },
	{ value: 'di', label: '地盘(身宫起)' },
	{ value: 'ren', label: '人盘(福德起)' },
];
export const SHANGSHI_OPTIONS = [
	{ value: 'fixed', label: '固定(天伤交友/天使疾厄)' },
	{ value: 'yinyang', label: '阴阳互换(中州·阴男阳女对调)' },
];
export const LEAP_MONTH_OPTIONS = [
	{ value: 'mid_split', label: '十五分界(默认·中州)' },
	{ value: 'next', label: '整月归下月' },
	{ value: 'prev', label: '整月归上月' },
	{ value: 'split_days', label: '前后半分割(日本主流)' },
	{ value: 'split_star_month', label: '命身下月·月系上月' },
];
export const LATE_ZI_OPTIONS = [
	{ value: 'zi_chu', label: '子初换日(默认)' },
	{ value: 'midnight_split', label: '夜子时折中' },
	{ value: 'zi_zheng', label: '子正换日' },
	{ value: 'dual', label: '双盘(当日/次日各一)' },
];
export const YEAR_BOUNDARY_OPTIONS = [
	{ value: 'lichun', label: '立春换年(默认)' },
	{ value: 'lunar_1_1', label: '正月初一换年' },
];
export const HUOLING_OPTIONS = [
	{ value: 'sanhe', label: '三合通行(默认·年支+生时)' },
	{ value: 'nanpai', label: '南派(只按年支·忽略生时)' },
];
export const KONG_NAMING_OPTIONS = [
	{ value: 'modern', label: '地空/地劫(默认)' },
	{ value: 'book', label: '天空/地劫(古本《全书》)' },
];
export const BRIGHTNESS_SOURCE_OPTIONS = [
	{ value: 'zi_jian', label: '自建亮度(默认·通行)' },
	{ value: 'quanshu', label: '《全书》版(擎羊子酉旺/铃星独立表)' },
];
