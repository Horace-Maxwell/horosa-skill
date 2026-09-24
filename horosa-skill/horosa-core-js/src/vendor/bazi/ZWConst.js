// 四化单一真值源＝components/ziwei/ziweiSchools.js(SIHUA_BASE+SIHUA_OVERRIDES);本文件仅派生对外契约键。
import { SIHUA_BASE as ZW_SIHUA_BASE, sihuaTable as zwSihuaTable } from '../ziwei/ziweiSchools.js';

export const ZWChart_SangHe = 0;
export const ZWChart_SiHua = 1;
export const ZWChart_FeiXing = 2;

export const ZWChart = {
	chart: ZWChart_SiHua,
};

// ===== 四化表·多流派（P1-A；单一真值源＝ziweiSchools.SIHUA_BASE+SIHUA_OVERRIDES，此处仅派生对外契约键，零回归） =====
// ⚠️ 键 `beipai` ＝【通用/飞星】口径(庚太阴科/天同忌、戊右弼科、壬左辅科)＝ziweiSchools.SIHUA_BASE。
//    键名 beipai 历史沿用(ZWSchool.school 默认值、localStorage、preset 皆用之，改则回归)——⚠️注意 ziweiSchools 同名 `beipai` 却是「天相忌」，勿混。
// zhongzhou＝王亭之中州派(仅戊/庚/壬化科异);quanshu＝全书系(庚壬异);beixiang＝真·北派天相忌(＝ziweiSchools 的 beixiang_tianxiang)。
// custom＝用户自定义，存 localStorage['ziweiSihuaCustom']。
export const SiHuaTables = {
	beipai: Object.assign({}, ZW_SIHUA_BASE),      // 通用/飞星口径(＝SIHUA_BASE)
	zhongzhou: zwSihuaTable('zhongzhou'),
	quanshu: zwSihuaTable('quanshu'),
	beixiang: zwSihuaTable('beixiang_tianxiang'),  // 真·北派:天同科·天相忌
};

// 当前流派（可变单例，镜像 ZWChart；默认=现状）。
export const ZWSchool = { school: 'beipai' };

// [A4] 挂载/导出侧临时注入的自定义四化表(可变单例;非 null 时 custom 档优先于 localStorage)。
// 挂载 builder set → 用毕 finally 清 null,绝不写 LS ——崩溃残留也不会污染用户本机偏好。
export const ZWSihuaCustom = { override: null };

// 自定义四化表归一/校验:接受对象或 JSON 字符串,形状={干:[禄,权,科,忌]}(每干 4 星名)。
// 至少一干合法即返归一表(缺干=该干回落通用表);全坏/空返 null(调用侧不注入=零行为)。
export function normalizeSihuaCustomTable(raw){
	let obj = raw;
	if(typeof raw === 'string'){
		if(!raw.trim()){ return null; }
		try{ obj = JSON.parse(raw); }catch(e){ return null; }
	}
	if(!obj || typeof obj !== 'object' || Array.isArray(obj)){ return null; }
	const out = {};
	'甲乙丙丁戊己庚辛壬癸'.split('').forEach((g)=>{
		const row = obj[g];
		if(Array.isArray(row) && row.length === 4 && row.every((x)=>typeof x === 'string' && x.trim())){
			out[g] = row.map((x)=>x.trim());
		}
	});
	return Object.keys(out).length ? Object.assign({}, SiHuaTables.beipai, out) : null;
}

// 取当前流派的十干四化表；custom 先查注入单例(挂载侧)再读 localStorage，缺/坏一律回退 beipai（安全兜底）。
export function getActiveSiHuaGan(){
	const s = ZWSchool.school;
	if(s === 'custom'){
		if(ZWSihuaCustom.override && typeof ZWSihuaCustom.override === 'object'){ return ZWSihuaCustom.override; }
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
	// [D0] 杂曜吉/凶独立 token(三主题区已定义,当前值=assist/evil 同值→零视觉变化;语义拆分后可独立调)。
	StarOthersGoodStroke: 'var(--horosa-ziwei-star-others-good, #327f8d)',
	StarOthersBadStroke: 'var(--horosa-ziwei-star-others-bad, #a9473f)',
	// [D1] 六煞黑字档色(三主题区各有定义;传统「六煞书黑」高对比中性色)
	StarSixEvilStroke: 'var(--horosa-ziwei-star-sixevil, #2b2b2b)',
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
	xiaoxian: 'var(--horosa-ziwei-period-xiaoxian, #9775fa)',   // [D3] 小限叠宫层 浅紫(独立 token,三主题区定义)
	liuyue: 'var(--horosa-ziwei-period-month, #2f9e44)',   // 流月 绿
	liuri: 'var(--horosa-ziwei-period-day, #e64980)',      // 流日 玫红
	liushi: 'var(--horosa-ziwei-period-hour, #e8590c)',    // 流时 橙
};
// 运限层前缀字（长生左侧标签 = 前缀 + 该宫在该层下的角色字，如「年命」「时兄」）。
export const ZWPeriodPrefix = {
	daxian: '运', liunian: '年', xiaoxian: '限', liuyue: '月', liuri: '日', liushi: '时',
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
