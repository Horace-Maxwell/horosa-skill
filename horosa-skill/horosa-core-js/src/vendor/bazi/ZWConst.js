export const ZWChart_SangHe = 0;
export const ZWChart_SiHua = 1;
export const ZWChart_FeiXing = 2;

export const ZWChart = {
	chart: ZWChart_SiHua,
};

// ===== 四化表·多流派（P1-A） =====
// 默认 beipai＝现状（规格§7.3 纠正:此表实为「通用/飞星」口径——庚太阴科/天同忌、戊右弼科、壬左辅科;键名 beipai 历史沿用、不改值避免回归）。
// zhongzhou＝王亭之中州派，仅 戊/庚/壬 三个「化科」与现状不同（化禄/权/忌全派一致）。真·北派(庚天相忌)见下 beixiang。
// custom＝用户自定义，存 localStorage['ziweiSihuaCustom']。默认严格＝现状，零回归。
export const SiHuaTables = {
	beipai: {
		"甲": ["廉贞", "破军", "武曲", "太阳"],
		"乙": ["天机", "天梁", "紫微", "太阴"],
		"丙": ["天同", "天机", "文昌", "廉贞"],
		"丁": ["太阴", "天同", "天机", "巨门"],
		"戊": ["贪狼", "太阴", "右弼", "天机"],
		"己": ["武曲", "贪狼", "天梁", "文曲"],
		"庚": ["太阳", "武曲", "太阴", "天同"],
		"辛": ["巨门", "太阳", "文曲", "文昌"],
		"壬": ["天梁", "紫微", "左辅", "武曲"],
		"癸": ["破军", "巨门", "太阴", "贪狼"]
	}
};
function deriveSiHuaTable(overrides){
	return Object.assign({}, SiHuaTables.beipai, overrides || {});
}
SiHuaTables.zhongzhou = deriveSiHuaTable({
	"戊": ["贪狼", "太阴", "太阳", "天机"],   // 化科 右弼→太阳
	"庚": ["太阳", "武曲", "天府", "天同"],   // 化科 太阴→天府
	"壬": ["天梁", "紫微", "天府", "武曲"]    // 化科 左辅→天府
});
// 全书系（《全书》）：仅 庚/壬 与通用不同。庚＝阳武同阴(科天同·忌太阴，与通用对调)；壬＝天府化科。戊仍右弼化科(同通用)。
SiHuaTables.quanshu = deriveSiHuaTable({
	"庚": ["太阳", "武曲", "天同", "太阴"],   // 化科 太阴→天同、化忌 天同→太阴（与通用对调）
	"壬": ["天梁", "紫微", "天府", "武曲"]    // 化科 左辅→天府
});
// 北派（规格§7.3 真·北派）：仅 庚 不同＝阳武同相(天同化科·【天相化忌】，天相忌为北派独有)；戊/壬 同通用。
// 注：上方默认 beipai 表实为「通用/飞星」口径(庚太阴科/天同忌)，与本表(天相忌)不同，勿混。
SiHuaTables.beixiang = deriveSiHuaTable({
	"庚": ["太阳", "武曲", "天同", "天相"]    // 化科 太阴→天同、化忌 天同→天相（北派独有）
});

// 当前流派（可变单例，镜像 ZWChart；默认=现状）。
export const ZWSchool = { school: 'beipai' };

// 取当前流派的十干四化表；custom 读 localStorage，缺/坏一律回退 beipai（安全兜底）。
export function getActiveSiHuaGan(){
	const s = ZWSchool.school;
	if(s === 'custom'){
		try{
			const c = JSON.parse(localStorage.getItem('ziweiSihuaCustom'));
			if(c && typeof c === 'object'){ return c; }
		}catch(e){ /* 解析失败回退 */ }
		return SiHuaTables.beipai;
	}
	return SiHuaTables[s] || SiHuaTables.beipai;
}

// 兼容垫片：保留 SiHua.gan 旧引用（RuleSihua/ZWIndicator 等读它），切流派时刷新即可跟随。
export let SiHua = {
	hua: ["禄", "权", "科", "忌"],
	gan: SiHuaTables.beipai
};
export function refreshActiveSiHua(){
	SiHua.gan = getActiveSiHuaGan();
}

export const ZWColor = {
	Stroke: 'var(--horosa-text-soft, #3b3b3b)',
	SelectedBG: 'var(--horosa-ziwei-selected-bg, #cdeaf3)',
	SangHeBG: 'var(--horosa-ziwei-sanhe-bg, #fcebc4)',
	DuiGongBG: 'var(--horosa-ziwei-duigong-bg, #dbe8fb)',
	StarMainStroke: 'var(--horosa-ziwei-star-main, #9b6a2d)',
	StarAssistStroke: 'var(--horosa-ziwei-star-assist, #327f8d)',
	StarEvilStroke: 'var(--horosa-ziwei-star-evil, #a9473f)',
	StarOthersGoodStroke: 'var(--horosa-ziwei-star-assist, #327f8d)',
	StarOthersBadStroke: 'var(--horosa-ziwei-star-evil, #a9473f)',
	StarSmallStroke: 'var(--horosa-ziwei-house-muted, #8a8f95)',
	HouseLineStroke: 'var(--horosa-ziwei-house-line, rgba(184, 137, 63, 0.22))',
	HouseMetaStroke: 'var(--horosa-ziwei-house-meta, #7a8790)',
	HouseBranchStroke: 'var(--horosa-ziwei-house-branch, #b8893f)',
	HouseNameStroke: 'var(--horosa-ziwei-house-name, #d8ad63)',
	HouseAgeStroke: 'var(--horosa-ziwei-house-age, #8794a8)',

	'禄': {
		bg: '#c9912e',
		color: '#ffffff',
	},
	'权': {
		bg: '#2868d8',
		color: '#ffffff',
	},
	'科': {
		bg: '#1497a8',
		color: '#ffffff',
	},
	'忌': {
		bg: '#d44d43',
		color: '#ffffff',
	},
};

// ===== 运限层色（需求3/5）：流年小限/流月/流日/流时 各一色，全程一致；与四化禄/权/科/忌四色不撞。 =====
// 大限/本命/自化保持原四化色（不入此表）。明暗双值走 CSS 变量令牌（见 app.less 的 --horosa-ziwei-period-*）。
// key 与 luckSel 层 key 对齐（liunian=流年小限合并层、liuyue/liuri/liushi）。
export const ZWPeriodColor = {
	liunian: 'var(--horosa-ziwei-period-year, #7048e8)',   // 流年小限 紫
	liuyue: 'var(--horosa-ziwei-period-month, #2f9e44)',   // 流月 绿
	liuri: 'var(--horosa-ziwei-period-day, #e64980)',      // 流日 玫红
	liushi: 'var(--horosa-ziwei-period-hour, #e8590c)',    // 流时 橙
};
// 运限层前缀字（长生左侧标签 = 前缀 + 该宫在该层下的角色字，如「年命」「时兄」）。
export const ZWPeriodPrefix = {
	daxian: '运', liunian: '年', liuyue: '月', liuri: '日', liushi: '时',
};

export const Gans = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
export const HouseZi = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
export const HouseZiMap = new Map();

export const ZWHouses = ["命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫", "迁移宫", "交友宫", "官禄宫", "田宅宫", "福德宫", "父母宫"];

export const WuHuDun = {
	"甲": "丙",
	"乙": "戊",
	"丙": "庚",
	"丁": "壬",
	"戊": "甲",
	"己": "丙",
	"庚": "戊",
	"辛": "庚",
	"壬": "壬",
	"癸": "甲",
};

export const NaYin = {
	"甲子": "海中金", "乙丑": "海中金", "丙寅": "炉中火", "丁卯": "炉中火", "戊辰": "大林木", "己巳": "大林木", "庚午": "路旁土", "辛未": "路旁土", "壬申": "剑锋金", "癸酉": "剑锋金",
	"甲戌": "山头火", "乙亥": "山头火", "丙子": "涧下水", "丁丑": "涧下水", "戊寅": "城头土", "己卯": "城头土", "庚辰": "白蜡金", "辛巳": "白蜡金", "壬午": "杨柳木", "癸未": "杨柳木",
	"甲申": "井泉水", "乙酉": "井泉水", "丙戌": "屋上土", "丁亥": "屋上土", "戊子": "霹雳火", "己丑": "霹雳火", "庚寅": "松柏木", "辛卯": "松柏木", "壬辰": "长流水", "癸巳": "长流水",
	"甲午": "砂中金", "乙未": "砂中金", "丙申": "山下火", "丁酉": "山下火", "戊戌": "平地木", "己亥": "平地木", "庚子": "壁上土", "辛丑": "壁上土", "壬寅": "金箔金", "癸卯": "金箔金",
	"甲辰": "覆灯火", "乙巳": "覆灯火", "丙午": "天河水", "丁未": "天河水", "戊申": "大驿土", "己酉": "大驿土", "庚戌": "钗钏金", "辛亥": "钗钏金", "壬子": "桑柘木", "癸丑": "桑柘木",
	"甲寅": "大溪水", "乙卯": "大溪水", "丙辰": "砂中土", "丁巳": "砂中土", "戊午": "天上火", "己未": "天上火", "庚申": "石榴木", "辛酉": "石榴木", "壬戌": "大海水", "癸亥": "大海水"
};

export const SixtyJiaZi = [
	"甲子", "乙丑", "丙寅", "丁卯", "戊辰", "己巳", "庚午", "辛未", "壬申", "癸酉", 
	"甲戌", "乙亥", "丙子", "丁丑", "戊寅", "己卯", "庚辰", "辛巳", "壬午", "癸未", 
	"甲申", "乙酉", "丙戌", "丁亥", "戊子", "己丑", "庚寅", "辛卯", "壬辰", "癸巳", 
	"甲午", "乙未", "丙申", "丁酉", "戊戌", "己亥", "庚子", "辛丑", "壬寅", "癸卯", 
	"甲辰", "乙巳", "丙午", "丁未", "戊申", "己酉", "庚戌", "辛亥", "壬子", "癸丑", 
	"甲寅", "乙卯", "丙辰", "丁巳", "戊午", "己未", "庚申", "辛酉", "壬戌", "癸亥"
];

export const BaziMonthTime = {
	month: {
		"甲": ["丙寅", "丁卯", "戊辰", "己巳", "庚午", "辛未", "壬申", "癸酉", "甲戌", "乙亥", "丙子", "丁丑"],
		"己": ["丙寅", "丁卯", "戊辰", "己巳", "庚午", "辛未", "壬申", "癸酉", "甲戌", "乙亥", "丙子", "丁丑"],
		"乙": ["戊寅", "己卯", "庚辰", "辛巳", "壬午", "癸未", "甲申", "乙酉", "丙戌", "丁亥", "戊子", "己丑"],
		"庚": ["戊寅", "己卯", "庚辰", "辛巳", "壬午", "癸未", "甲申", "乙酉", "丙戌", "丁亥", "戊子", "己丑"],
		"丙": ["庚寅", "辛卯", "壬辰", "癸巳", "甲午", "乙未", "丙申", "丁酉", "戊戌", "己亥", "庚子", "辛丑"],
		"辛": ["庚寅", "辛卯", "壬辰", "癸巳", "甲午", "乙未", "丙申", "丁酉", "戊戌", "己亥", "庚子", "辛丑"],
		"丁": ["壬寅", "癸卯", "甲辰", "乙巳", "丙午", "丁未", "戊申", "己酉", "庚戌", "辛亥", "壬子", "癸丑"],
		"壬": ["壬寅", "癸卯", "甲辰", "乙巳", "丙午", "丁未", "戊申", "己酉", "庚戌", "辛亥", "壬子", "癸丑"],
		"戊": ["甲寅", "乙卯", "丙辰", "丁巳", "戊午", "己未", "庚申", "辛酉", "壬戌", "癸亥", "甲子", "乙丑"],
		"癸": ["甲寅", "乙卯", "丙辰", "丁巳", "戊午", "己未", "庚申", "辛酉", "壬戌", "癸亥", "甲子", "乙丑"]
	},
	
	time: {
		"甲": ["甲子", "乙丑", "丙寅", "丁卯", "戊辰", "己巳", "庚午", "辛未", "壬申", "癸酉", "甲戌", "乙亥", "丙子"],
		"己": ["甲子", "乙丑", "丙寅", "丁卯", "戊辰", "己巳", "庚午", "辛未", "壬申", "癸酉", "甲戌", "乙亥", "丙子"],
		"乙": ["丙子", "丁丑", "戊寅", "己卯", "庚辰", "辛巳", "壬午", "癸未", "甲申", "乙酉", "丙戌", "丁亥", "戊子"],
		"庚": ["丙子", "丁丑", "戊寅", "己卯", "庚辰", "辛巳", "壬午", "癸未", "甲申", "乙酉", "丙戌", "丁亥", "戊子"],
		"丙": ["戊子", "己丑", "庚寅", "辛卯", "壬辰", "癸巳", "甲午", "乙未", "丙申", "丁酉", "戊戌", "己亥", "庚子"],
		"辛": ["戊子", "己丑", "庚寅", "辛卯", "壬辰", "癸巳", "甲午", "乙未", "丙申", "丁酉", "戊戌", "己亥", "庚子"],
		"丁": ["庚子", "辛丑", "壬寅", "癸卯", "甲辰", "乙巳", "丙午", "丁未", "戊申", "己酉", "庚戌", "辛亥", "壬子"],
		"壬": ["庚子", "辛丑", "壬寅", "癸卯", "甲辰", "乙巳", "丙午", "丁未", "戊申", "己酉", "庚戌", "辛亥", "壬子"],
		"戊": ["壬子", "癸丑", "甲寅", "乙卯", "丙辰", "丁巳", "戊午", "己未", "庚申", "辛酉", "壬戌", "癸亥", "甲子"],
		"癸": ["壬子", "癸丑", "甲寅", "乙卯", "丙辰", "丁巳", "戊午", "己未", "庚申", "辛酉", "壬戌", "癸亥", "甲子"]
	}
};

export const SihuaColor = [];
SihuaColor[0] = {color: ZWColor[SiHua.hua[0]].bg};
SihuaColor[1] = {color: ZWColor[SiHua.hua[1]].bg};
SihuaColor[2] = {color: ZWColor[SiHua.hua[2]].bg};
SihuaColor[3] = {color: ZWColor[SiHua.hua[3]].bg};
SihuaColor['禄'] = SihuaColor[0];
SihuaColor['权'] = SihuaColor[1];
SihuaColor['科'] = SihuaColor[2];
SihuaColor['忌'] = SihuaColor[3];
