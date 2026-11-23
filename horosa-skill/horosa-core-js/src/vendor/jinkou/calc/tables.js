// 金口诀基础常量表(五行生克、月将、贵神起法、五子遁、神煞名序、五行配色)
// 从 JinKouCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。

// 五行配色统一对齐八字模块的品牌色板(--horosa-bazi-*)，全 app 一套色。
// 金口诀主盘走 SVG presentation 属性(attr fill)，CSS 变量在此不解析，故落为对应 hex；
// 主盘底色随暗黑模式翻深，浅色板的水/木/火会过暗不可读 → 按主题在 access 时取浅/深板(Proxy)，
// 主盘重绘时即解析当前主题，明暗皆可读。
const JINKOU_ELEMENT_COLOR_LIGHT = { '木': '#237a45', '火': '#c72d22', '土': '#7a4f2a', '金': '#ab5500', '水': '#275fc7' };   // 金 = --horosa-bazi-metal 亮色值(旧 #e0892a 亮底 2.4:1)

const JINKOU_ELEMENT_COLOR_DARK = { '木': '#66c486', '火': '#ff5f50', '土': '#c08a4c', '金': '#eda34a', '水': '#5f8fff' };

function jinKouElementPalette(){
	try {
		if(typeof document !== 'undefined' && document.documentElement && document.documentElement.getAttribute('data-horosa-appearance') === 'dark'){
			return JINKOU_ELEMENT_COLOR_DARK;
		}
	} catch(e){ /* 非浏览器环境(测试)走浅色板 */ }
	return JINKOU_ELEMENT_COLOR_LIGHT;
}

export const JinKouElementColor = new Proxy(JINKOU_ELEMENT_COLOR_LIGHT, {
	get: function(target, key){ return jinKouElementPalette()[key]; },
});

export const JinKouWuXingOrder = ['木', '火', '土', '金', '水'];

export const JinKouWuXingSheng = {
	'木': '火',
	'火': '土',
	'土': '金',
	'金': '水',
	'水': '木',
};

export const JinKouWuXingKe = {
	'木': '土',
	'火': '金',
	'土': '水',
	'金': '木',
	'水': '火',
};

export const JinKouYueJiangName = {
	'子': '神后',
	'丑': '大吉',
	'寅': '功曹',
	'卯': '太冲',
	'辰': '天罡',
	'巳': '太乙',
	'午': '胜光',
	'未': '小吉',
	'申': '传送',
	'酉': '从魁',
	'戌': '河魁',
	'亥': '登明',
};

export const JinKouGuiShenSeq = ['贵人', '螣蛇', '朱雀', '六合', '勾陈', '青龙', '天空', '白虎', '太常', '玄武', '太阴', '天后'];

export const JinKouGuiShenZi = {
	'贵人': '丑',
	'螣蛇': '巳',
	'朱雀': '午',
	'六合': '卯',
	'勾陈': '辰',
	'青龙': '寅',
	'天空': '戌',
	'白虎': '申',
	'太常': '未',
	'玄武': '子',
	'太阴': '酉',
	'天后': '亥',
};

export const JinKouYueJiangByMonthBranch = {
	'寅': '亥',
	'卯': '戌',
	'辰': '酉',
	'巳': '申',
	'午': '未',
	'未': '午',
	'申': '巳',
	'酉': '辰',
	'戌': '卯',
	'亥': '寅',
	'子': '丑',
	'丑': '子',
};

export const JinKouYueJiangByJieQi = {
	'雨水': '亥',
	'惊蛰': '亥',
	'春分': '戌',
	'清明': '戌',
	'谷雨': '酉',
	'立夏': '酉',
	'小满': '申',
	'芒种': '申',
	'夏至': '未',
	'小暑': '未',
	'大暑': '午',
	'立秋': '午',
	'处暑': '巳',
	'白露': '巳',
	'秋分': '辰',
	'寒露': '辰',
	'霜降': '卯',
	'立冬': '卯',
	'小雪': '寅',
	'大雪': '寅',
	'冬至': '丑',
	'小寒': '丑',
	'大寒': '子',
	'立春': '子',
};

// 交节即换口径（A1）：月将随月建六合，于「节」一交即变（立春→亥起，逐节顺退）。
// 24 节气全列：节起新值、随后中气保持，与中气表同形可直接替换。
export const JinKouYueJiangByJieQi_JiaoJie = {
	'立春': '亥', '雨水': '亥',
	'惊蛰': '戌', '春分': '戌',
	'清明': '酉', '谷雨': '酉',
	'立夏': '申', '小满': '申',
	'芒种': '未', '夏至': '未',
	'小暑': '午', '大暑': '午',
	'立秋': '巳', '处暑': '巳',
	'白露': '辰', '秋分': '辰',
	'寒露': '卯', '霜降': '卯',
	'立冬': '寅', '小雪': '寅',
	'大雪': '丑', '冬至': '丑',
	'小寒': '子', '大寒': '子',
};

export const JinKouGuiRuleLiuReng = {
	'甲': {
		day: { start: '丑', reverse: false },
		night: { start: '未', reverse: true },
	},
	'乙': {
		day: { start: '子', reverse: false },
		night: { start: '申', reverse: true },
	},
	'丙': {
		day: { start: '亥', reverse: false },
		night: { start: '酉', reverse: true },
	},
	'丁': {
		day: { start: '亥', reverse: false },
		night: { start: '酉', reverse: true },
	},
	'戊': {
		day: { start: '丑', reverse: false },
		night: { start: '未', reverse: true },
	},
	'己': {
		day: { start: '子', reverse: false },
		night: { start: '申', reverse: true },
	},
	'庚': {
		day: { start: '丑', reverse: false },
		night: { start: '未', reverse: true },
	},
	'辛': {
		day: { start: '午', reverse: true },
		night: { start: '寅', reverse: false },
	},
	'壬': {
		day: { start: '巳', reverse: true },
		night: { start: '卯', reverse: false },
	},
	'癸': {
		day: { start: '巳', reverse: true },
		night: { start: '卯', reverse: false },
	},
};

// 大六壬古法贵人表（A2）：严格按大六壬昼夜贵人歌取——
//   甲戊庚牛羊（昼丑·夜未）、乙己鼠猴乡（昼子·夜申）、丙丁猪鸡位（昼亥·夜酉）、
//   六辛逢马虎（昼午·夜寅）、壬癸兔蛇藏（昼卯·夜巳）。
// 与「实务派」的差异面只在壬癸两干（实务派此二干昼夜与歌诀相反）。
// 顺逆一律按贵人落支重判（巳午未申酉戌逆、亥子丑寅卯辰顺），故只存 start。
export const JinKouGuiRuleLiuRenClassic = {
	'甲': { day: { start: '丑' }, night: { start: '未' } },
	'乙': { day: { start: '子' }, night: { start: '申' } },
	'丙': { day: { start: '亥' }, night: { start: '酉' } },
	'丁': { day: { start: '亥' }, night: { start: '酉' } },
	'戊': { day: { start: '丑' }, night: { start: '未' } },
	'己': { day: { start: '子' }, night: { start: '申' } },
	'庚': { day: { start: '丑' }, night: { start: '未' } },
	'辛': { day: { start: '午' }, night: { start: '寅' } },
	'壬': { day: { start: '卯' }, night: { start: '巳' } },
	'癸': { day: { start: '卯' }, night: { start: '巳' } },
};

export const WuZiDunStart = {
	'甲': '甲',
	'己': '甲',
	'乙': '丙',
	'庚': '丙',
	'丙': '戊',
	'辛': '戊',
	'丁': '庚',
	'壬': '庚',
	'戊': '壬',
	'癸': '壬',
};

export const DayTimeZi = ['卯', '辰', '巳', '午', '未', '申'];

// B6 修正：贵人落「巳午未申酉戌」六支逆布（§3.4(4)），原缺「戌」。
// 实务派(idx=0)用表内 reverse 不受影响；古法表/idx≠0 按此判顺逆，戌不在实务派任何 start → 零回归。
export const GuiReverseStartZi = ['巳', '午', '未', '申', '酉', '戌'];

export const JinKouShenShaOrder = [
	'天德',
	'天德合',
	'月德',
	'月合',
	'天赦',
	'天喜',
	'天马',
	'驿马',
	'丧门',
	'吊客',
	'丧车',
	'截命灾杀',
	'三丘',
	'四墓',
	'病符',
	'官符',
	'六丁',
	'六甲',
	'飞廉',
	'劫煞',
	'地煞',
	'望门',
	'灭门',
	'天盗',
	'三刑',
	'六害',
	'生气',
	'天医',
	'地医',
	'五鬼',
	'月德合',
	'桃花',
	'禄倒',
	'马倒',
	'三奇',
	'四绝',
	'天罗',
	'地网',
	'关',
	'隔',
	'锁',
	'斩关',
	'毁隔',
	'破锁',
];

// 应期合德六法（§9.8）：天地合德/将干近合/三奇合/三合补字/支六合/旺相逢冲。
export const JINKOU_SANQI_SETS = [['甲', '戊', '庚'], ['乙', '丙', '丁'], ['壬', '癸', '辛']];
