// 紫微「传本/流派」排盘开关（可变单例，镜像 ZWConst.ZWSchool 模式；默认＝现状零回归）。
// 任一项非默认 → ZiWeiMain.requestZiWei 走本地 ZiweiCalc 引擎(Java 不支持这些开关);全默认 → 仍走 Java(字节零回归)。
export const ZWEngineOptions = {
	daxianSpan: 10,        // 10=三合10年(默认) / 'ju'=钦天局数年
	tianmaBasis: 'month',  // month=现状月马(默认) / year=年支三合马
	starSet: 'full',       // full=全星(默认) / north18=精简18星(河洛)
	sanPan: 'tian',        // tian=天盘(默认) / di=地盘 / ren=人盘(中州三盘观察法)
	shangShi: 'fixed',     // fixed=天伤交友/天使疾厄(默认) / yinyang=中州派阴阳互换(仅阴男阳女对调,古法§6)
	leapMonth: 'mid_split',// 闰月归月:mid_split 十五分界(默认=现状) / next 整月归下月 / prev 整月归上月(§1.5)
	lateZi: 'global',      // 晚子时:global 跟随全局设置(默认) / zi_chu 强制子初换日 / midnight_split 夜子折中 / zi_zheng 子正换日(§1.3)
	yearBoundary: 'lichun',// 定年界线:lichun 立春(默认=现状) / lunar_1_1 正月初一(§1.6)
	huoling: 'sanhe',      // 火铃:sanhe 三合通行(默认=现状,年支+生时顺数) / nanpai 南派(忽略生时·固定子)(§1.6)
	kongNaming: 'modern',  // 空劫命名:modern 地空地劫(默认) / book 时系逆行星作天空(古本《全书》,互斥去年支独立天空)(§5)
	brightnessSource: 'zi_jian', // 亮度源:zi_jian 自建(默认=现状,=中州五档) / quanshu《全书》煞星改订 / quanshu_full《全书》七档全表(§4.5/A.7)
	lifeMasterBy: 'year_branch', // 命主取法:year_branch 生年支(默认=现状=Java 同源) / ming_branch 命宫支(经典法)。纯派生标量,不进 needsLocalEngine(见下 ⚠️)
	liunianSihuaGan: 'year_gan', // 流年四化取干:year_gan 流年干支之干(默认=现状) / ming_gong_gan 流年命宫宫干(飞星系用法)。运限推演层,不进 needsLocalEngine
	liuYueBasis: 'doujun',       // 流月起法:doujun 斗君宫起正月(默认=现状,三合/四化主流) / taisui 太岁宫起正月。运限推演层,不进 needsLocalEngine
	kuiYue: 'jia_wu_geng',       // 魁钺歌诀:jia_wu_geng 甲戊庚牛羊(默认=现表,庚→丑未) / geng_ma_hu 庚辛逢马虎(庚→午寅)。真移星,进 needsLocalEngine
	kongwangStyle: 'double',     // 截空旬空:double 正副双星(默认=现状) / single 只安正空支(正名无副)。改安星,进 needsLocalEngine
	xiaoxianMode: '0',     // [B15] 小限顺逆:'0'=男顺女逆(默认) / '1'=阳男阴女顺(中州)。[B15b] 进 FORWARD(本地引擎 smallDirection 同口径);不进 needsLocalEngine(渲染层 xiaoxianAgesOf 单源现算,绝不为它翻引擎)
	changshengDirection: 'yinyang', // 长生十二神顺逆:yinyang 阳男阴女顺/阴男阳女逆(默认=现状) / always_forward 全顺行。仅动 phase 环,进 needsLocalEngine
	changshengStart: 'shui_tu',  // 长生十二神起法:shui_tu 水土同宫(默认=现状,土五起申) / huo_tu 火土同宫(土五起寅)。phase 烙盘,进 needsLocalEngine
	// ── 显示层 overlay 开关(纯后处理,不改安星,故【不】进 ziweiNeedsLocalEngine;默认全关=零回归) ──
	childLimit: false,     // 童限:上大限前逐岁本命宫(命财疾妻福官),右栏运限顶轴显示(§8.6)
	zhongxian: false,      // 沈氏三限:大限细分4段中限各2.5年(沈氏派)(§9.14)
	huoPan: false,         // 活盘:点任意宫为太极点重排人事宫名(透派/占验)(§9.9/9.11)
	qishuWei: false,       // 河洛气数位:官禄宫干四化回照+一六共宗(河洛派)(§9.10)
	borrowPalace: false,   // 中州借宫:空宫借对宫十四正曜(中州派)(§9.2.4)
	taiSuiRuGua: false,    // 紫云太岁入卦:关系人生肖落同支宫(紫云派)(§9.3)
	flowShenshaOnChart: false,   // [D3] 流年神煞上盘:选中流年时宫内将前/岁前十二神换流年版(绘制期替换,零触数据)。默认关
	flowHuoLing: false,    // 流年火铃:运限流曜追加两颗(流年支代年支+生时,本命火铃内核同式)。默认关=快照/基线字节稳
	flowLuanXi: false,     // 流鸾流喜:运限流曜追加两颗(支系,与本命红鸾天喜同公式)。默认关=快照/基线字节稳(P3d)
	taiSuiRelatives: [],   // 紫云关系人列表 [{branch,role,sex}](随盘存)
};

// 🔴 引擎键转发单一真值表:UI→ZWEngineOptions→ZiWeiMain opts→calcZiwei ctx 的三跳链
//    曾因「三处手抄清单」漏抄断线(changshengStart/kuiYue 真机死开关,金标全走 assembleNatalChart
//    绕过断点没抓到)——此后三消费点全部 spread 此表,新增引擎键只改这一处。
//    显式豁免(不进表,各层自消费):lateZi/yearBoundary(calcZiwei 层自读 options)、
//    ziweiLunarBasis(对拍兼容档)、sanPan(deriveSanPan 后处理)。
export const ZW_ENGINE_FORWARD_KEYS = ['daxianSpan', 'tianmaBasis', 'starSet', 'shangShi', 'leapMonth',
	'huoling', 'kongNaming', 'lifeMasterBy', 'changshengStart', 'changshengDirection', 'kuiYue', 'kongwangStyle',
	'xiaoxianMode'];   // [B15b] 本地引擎 (16) 段消费(smallDirection 口径);不触发 needsLocalEngine
export function collectEngineOpts(src){
	const out = {};
	ZW_ENGINE_FORWARD_KEYS.forEach((k)=>{ out[k] = src[k]; });
	return out;
}

// 是否需要走本地引擎(任一开关非默认,或流派 preset 非现状)。四化版(beipai/zhongzhou/quanshu)单独走 getActiveSiHuaGan，
// 不在此触发本地(四化是前端 getSiHua 渲染层，转/Java 盘皆可)。
export function ziweiNeedsLocalEngine(){
	return ZWEngineOptions.daxianSpan !== 10
		|| ZWEngineOptions.tianmaBasis !== 'month'
		|| ZWEngineOptions.starSet !== 'full'
		|| ZWEngineOptions.sanPan !== 'tian'
		|| ZWEngineOptions.shangShi !== 'fixed'
		|| ZWEngineOptions.leapMonth !== 'mid_split'
		|| ZWEngineOptions.lateZi !== 'global'
		|| ZWEngineOptions.yearBoundary !== 'lichun'
		|| ZWEngineOptions.huoling !== 'sanhe'
		|| ZWEngineOptions.kongNaming !== 'modern'
		|| ZWEngineOptions.changshengStart !== 'shui_tu'
		|| ZWEngineOptions.kuiYue !== 'jia_wu_geng'
		|| ZWEngineOptions.changshengDirection !== 'yinyang'
		|| ZWEngineOptions.kongwangStyle !== 'double';
	// ⚠️ brightnessSource 不进此判据:亮度是纯显示层(庙旺 delta 覆盖,ZWCommHouse.effStarLight),
	//    绝不触发本地引擎重排——否则会连带把命主等按本地口径重算,切亮度竟改命主(实测坑)。
	// ⚠️ lifeMasterBy 同理不进:命主是纯派生标量(LIFE_MASTER[支],两输入 Java 盘上都有),为一个
	//    标签翻整台引擎会连带换年柱/晚子时口径(同类坑);Java 路径由 applyLifeMasterOption 后处理。
}

// 选项常量(左栏下拉用)
export const DAXIAN_SPAN_OPTIONS = [
	{ value: 10, label: '10 年(三合·默认)' },
	{ value: 'ju', label: '局数年(钦天)' },
];
// 天马依据:两表逐支同位、本是同一颗星。选年支三合马时,年支系的「年马」会自动跳过
// (否则同盘出现两颗马星)。默认保持 month 以守既有盘与前后端字节一致;正统紫微多用年支三合马。
export const TIANMA_BASIS_OPTIONS = [
	{ value: 'month', label: '月马(默认·沿用现状)' },
	{ value: 'year', label: '年支三合马(紫微通行)' },
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
	{ value: 'split_days', label: '前后半分割(按实际天数取中点)' },
	{ value: 'solar_term', label: '按节气分界(过节归下月)' },
	{ value: 'split_star_month', label: '命身下月·月系上月' },
];
export const LATE_ZI_OPTIONS = [
	{ value: 'global', label: '跟随全局设置(默认)' },
	{ value: 'zi_chu', label: '子初换日(强制)' },
	{ value: 'midnight_split', label: '夜子时折中' },
	{ value: 'zi_zheng', label: '子正换日' },
	{ value: 'dual', label: '双盘(当日/次日各一)' },
];
// 定年界线:紫微斗数是五术里的例外——**正月初一换年是紫微正统**,立春换年是八字口径。
// 生辰落在春节↔立春之间者两口径不同年,会连带改掉十二宫干(五虎遁)/生年四化/年干支系诸星/
// 小限起宫/身主/旬空/大限顺逆。默认仍保 lichun 以守既有盘与前后端字节一致,按需自行切换。
export const YEAR_BOUNDARY_OPTIONS = [
	{ value: 'lichun', label: '立春换年(默认·八字口径)' },
	{ value: 'lunar_1_1', label: '正月初一换年(紫微正统)' },
];
export const HUOLING_OPTIONS = [
	{ value: 'sanhe', label: '三合通行(默认·年支+生时)' },
	{ value: 'nanpai', label: '南派(只按年支·忽略生时)' },
];
export const KONG_NAMING_OPTIONS = [
	{ value: 'modern', label: '地空/地劫(默认)' },
	{ value: 'book', label: '天空/地劫(古本《全书》)' },
];
export const LIUNIAN_SIHUA_GAN_OPTIONS = [
	{ value: 'year_gan', label: '依流年天干(默认)' },
	{ value: 'ming_gong_gan', label: '依流年命宫天干' },
];
export const LIU_YUE_BASIS_OPTIONS = [
	{ value: 'doujun', label: '斗君宫起正月(默认)' },
	{ value: 'taisui', label: '太岁宫起正月' },
];
export const KUIYUE_OPTIONS = [
	{ value: 'jia_wu_geng', label: '甲戊庚牛羊·六辛逢马虎(默认)' },
	{ value: 'geng_ma_hu', label: '庚辛逢马虎(庚随辛→魁午钺寅)' },
	{ value: 'liu_xin_hu_ma', label: '六辛逢虎马(辛→魁寅钺午)' },
	{ value: 'geng_xin_hu_ma', label: '庚辛逢虎马(庚辛→魁寅钺午)' },
];
export const KONGWANG_STYLE_OPTIONS = [
	{ value: 'double', label: '正副双星(默认)' },
	{ value: 'single', label: '只安正空(单星)' },
];
export const CHANGSHENG_DIRECTION_OPTIONS = [
	{ value: 'yinyang', label: '分阴阳顺逆(默认)' },
	{ value: 'always_forward', label: '一律顺行(不分阴阳)' },
];
export const CHANGSHENG_START_OPTIONS = [
	{ value: 'shui_tu', label: '水土同宫(默认·土五起申)' },
	{ value: 'huo_tu', label: '火土同宫(土五起寅)' },
];
export const LIFE_MASTER_BY_OPTIONS = [
	{ value: 'year_branch', label: '生年支(默认)' },
	{ value: 'ming_branch', label: '命宫支(经典法)' },
];
export const BRIGHTNESS_SOURCE_OPTIONS = [
	{ value: 'zi_jian', label: '自建亮度(默认·中州五档)' },
	{ value: 'quanshu', label: '《全书》煞星改订(擎羊子酉旺/铃星独立表)' },
	{ value: 'quanshu_full', label: '《全书》七档全表(庙旺得利平不陷)' },
	{ value: 'custom', label: '自定义(逐格编辑,32星×12支)' },
];
