import * as LRConst from '../liureng/LRConst.js';





import {

	JINKOU_SHENSHA_DOC,
	JINKOU_RELATION_DOC,
	JINKOU_BIHE_DOC,
	JINKOU_DIZHI_DOC,
	JINKOU_CATEGORY_RULES,
	JINKOU_DONG_DOC,
	JINKOU_GEJU_DOC,
	JINKOU_GUISHEN_XIANGYI,
	JINKOU_YUEJIANG_DOC,
	JINKOU_SIXIANG_SHU,
	JINKOU_SIXIANG_WUXING,
	JINKOU_TIANQI_TEXT,
	JINKOU_LIUSHEN_DOC,
	JINKOU_LIUQIN_DOC,
	JINKOU_ZHAI_NEIJING,
	JINKOU_ZHAI_NOTES,
	JINKOU_DAJING_SHUIZHI,
	JINKOU_DAJING_NOTES,
	JINKOU_BANZHI_BUWEI,
	JINKOU_BANZHI_GAN,
	JINKOU_BANZHI_NOTES,
	JINKOU_GUIJIAN_JUE,
	JINKOU_XINGNIAN_GE,
} from './JinKouDoc.js';

import { parseDateParts } from '../bazi/dateStrSafe.js';
// 五行配色统一对齐八字模块的品牌色板(--horosa-bazi-*)，全 app 一套色。
// 金口诀主盘走 SVG presentation 属性(attr fill)，CSS 变量在此不解析，故落为对应 hex；
// 主盘底色随暗黑模式翻深，浅色板的水/木/火会过暗不可读 → 按主题在 access 时取浅/深板(Proxy)，
// 主盘重绘时即解析当前主题，明暗皆可读。
const JINKOU_ELEMENT_COLOR_LIGHT = { '木': '#237a45', '火': '#c72d22', '土': '#805526', '金': '#e0892a', '水': '#275fc7' };
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

const JinKouWuXingOrder = ['木', '火', '土', '金', '水'];
const JinKouWuXingSheng = {
	'木': '火',
	'火': '土',
	'土': '金',
	'金': '水',
	'水': '木',
};
const JinKouWuXingKe = {
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

const JinKouGuiShenSeq = ['贵人', '螣蛇', '朱雀', '六合', '勾陈', '青龙', '天空', '白虎', '太常', '玄武', '太阴', '天后'];
const JinKouGuiShenZi = {
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
const JinKouYueJiangByMonthBranch = {
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
const JinKouYueJiangByJieQi = {
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
const JinKouYueJiangByJieQi_JiaoJie = {
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
const JinKouGuiRuleLiuReng = {
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
const JinKouGuiRuleLiuRenClassic = {
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
const WuZiDunStart = {
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
const DayTimeZi = ['卯', '辰', '巳', '午', '未', '申'];
// B6 修正：贵人落「巳午未申酉戌」六支逆布（§3.4(4)），原缺「戌」。
// 实务派(idx=0)用表内 reverse 不受影响；古法表/idx≠0 按此判顺逆，戌不在实务派任何 start → 零回归。
const GuiReverseStartZi = ['巳', '午', '未', '申', '酉', '戌'];
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

function uniq(arr){
	const map = {};
	const out = [];
	for(let i=0; i<arr.length; i++){
		const val = arr[i];
		if(!val || map[val]){
			continue;
		}
		map[val] = true;
		out.push(val);
	}
	return out;
}

function containsVal(list, val){
	return list.indexOf(val) >= 0;
}

function extractFromList(text, list){
	const txt = `${text || ''}`;
	for(let i=0; i<txt.length; i++){
		const one = txt.substr(i, 1);
		if(list.indexOf(one) >= 0){
			return one;
		}
	}
	return '';
}

function getDayGan(liureng){
	if(!liureng || !liureng.nongli){
		return '';
	}
	return extractFromList(liureng.nongli.dayGanZi, LRConst.GanList);
}

function getDayZi(liureng){
	if(!liureng || !liureng.nongli){
		return '';
	}
	return extractFromList(liureng.nongli.dayGanZi, LRConst.ZiList);
}

// 干支全串(真太岁/日建等需比对整柱，非单取干或支)。取不到时返回空串，下游判定自动跳过。
function getDayGanZi(liureng){
	const gan = getDayGan(liureng);
	const zi = getDayZi(liureng);
	return (gan && zi) ? `${gan}${zi}` : '';
}

function getYearGanZi(liureng){
	if(!liureng){ return ''; }
	if(liureng.fourColumns && liureng.fourColumns.year && liureng.fourColumns.year.ganzi){
		const gz = `${liureng.fourColumns.year.ganzi}`;
		const gan = extractFromList(gz, LRConst.GanList);
		const zi = extractFromList(gz, LRConst.ZiList);
		if(gan && zi){ return `${gan}${zi}`; }
	}
	if(liureng.nongli && liureng.nongli.yearGanZi){
		const gan = extractFromList(liureng.nongli.yearGanZi, LRConst.GanList);
		const zi = extractFromList(liureng.nongli.yearGanZi, LRConst.ZiList);
		if(gan && zi){ return `${gan}${zi}`; }
	}
	return '';
}

function getMonthZi(liureng){
	if(!liureng){
		return '';
	}
	if(liureng.fourColumns && liureng.fourColumns.month && liureng.fourColumns.month.ganzi){
		const zi = extractFromList(liureng.fourColumns.month.ganzi, LRConst.ZiList);
		if(zi){
			return zi;
		}
	}
	if(liureng.nongli){
		return extractFromList(liureng.nongli.monthGanZi, LRConst.ZiList);
	}
	return '';
}

function getYearZi(liureng){
	if(!liureng){
		return '';
	}
	if(liureng.fourColumns && liureng.fourColumns.year && liureng.fourColumns.year.ganzi){
		const zi = extractFromList(liureng.fourColumns.year.ganzi, LRConst.ZiList);
		if(zi){
			return zi;
		}
	}
	if(liureng.nongli && liureng.nongli.yearGanZi){
		return extractFromList(liureng.nongli.yearGanZi, LRConst.ZiList);
	}
	if(liureng.nongli && liureng.nongli.year){
		return extractFromList(liureng.nongli.year, LRConst.ZiList);
	}
	return '';
}

function getTimeZi(liureng){
	if(!liureng || !liureng.nongli){
		return '';
	}
	return extractFromList(liureng.nongli.time, LRConst.ZiList);
}

function normalizeJieqiName(jieqi){
	const map = {
		'驚蟄': '惊蛰',
		'穀雨': '谷雨',
		'處暑': '处暑',
		'白露節': '白露',
	};
	const txt = `${jieqi || ''}`.trim();
	if(txt === ''){
		return '';
	}
	const normalized = map[txt] ? map[txt] : txt;
	return normalized.substring(0, 2);
}

function resolveJieqiForYueJiang(liureng){
	if(!liureng || !liureng.nongli){
		return '';
	}
	const nongli = liureng.nongli;
	const direct = normalizeJieqiName(nongli.jieqi);
	if(direct){
		return direct;
	}
	const deltaTxt = `${nongli.jiedelta || ''}`.trim();
	if(deltaTxt){
		return normalizeJieqiName(deltaTxt);
	}
	return '';
}

function normalizeDiFen(diFen, fallback){
	const zi = extractFromList(diFen, LRConst.ZiList);
	if(zi){
		return zi;
	}
	if(containsVal(LRConst.ZiList, fallback)){
		return fallback;
	}
	return LRConst.ZiList[0];
}

function getStemByWuZiDun(dayGan, zi){
	const start = WuZiDunStart[dayGan];
	const zIdx = LRConst.ZiList.indexOf(zi);
	const gIdx = LRConst.GanList.indexOf(start);
	if(!start || zIdx < 0 || gIdx < 0){
		return '';
	}
	return LRConst.GanList[(gIdx + zIdx) % LRConst.GanList.length];
}

// 昼夜判定（B6·P2）：真实地平优先——后端起盘算得的 chart.isDiurnal（日在地平上=昼，
// 已含真太阳时与当地日出日落，阴天不影响天文时刻）；无盘可依时才回落时支粗判卯-申。
// 两法在近日出/日落一小时内常不一致，故把所依据的口径一并回报，供右栏与快照标注。
function resolveIsDayInfo(timeZi, isDiurnal){
	if(isDiurnal === true || isDiurnal === false){
		return { isDay: isDiurnal, basis: 'horizon', basisText: '真实地平·日出日落' };
	}
	return { isDay: containsVal(DayTimeZi, timeZi), basis: 'branch', basisText: '时支粗判·卯至申为昼' };
}
function resolveIsDay(timeZi, isDiurnal){
	return resolveIsDayInfo(timeZi, isDiurnal).isDay;
}

function getGuiShenAtDiFen(dayGan, timeZi, diFen, guirengType, isDiurnal, schoolOpts){
	const so = schoolOpts || {};
	const guiTable = so.guiTable || 'shiwu';
	const guiPan = so.guiPan || 'di';
	const idx = guirengType === undefined || guirengType === null ? 0 : parseInt(guirengType + '', 10);
	const dayInfo = resolveIsDayInfo(timeZi, isDiurnal);
	const isDay = dayInfo.isDay;
	let startZi = '';
	let reverse = false;
	if(guiTable === 'liuren' && JinKouGuiRuleLiuRenClassic[dayGan]){
		// A2 大六壬古法贵人表：起例(start)按古法表，顺逆按贵人落支重判。
		const cfg = JinKouGuiRuleLiuRenClassic[dayGan][isDay ? 'day' : 'night'];
		startZi = cfg ? cfg.start : '';
		reverse = containsVal(GuiReverseStartZi, startZi);
	}else if(idx === 0 && JinKouGuiRuleLiuReng[dayGan]){
		const mode = isDay ? 'day' : 'night';
		const cfg = JinKouGuiRuleLiuReng[dayGan][mode];
		startZi = cfg ? cfg.start : '';
		reverse = cfg ? !!cfg.reverse : false;
	}else{
		const guireng = LRConst.GuiRengs[idx] ? LRConst.GuiRengs[idx] : LRConst.GuiRengs[0];
		startZi = isDay ? guireng.day[dayGan] : guireng.night[dayGan];
		reverse = containsVal(GuiReverseStartZi, startZi);
	}
	if(!startZi){
		return {
			name: '',
			zi: '',
			startZi: '',
			isDay: isDay,
			dayBasis: dayInfo.basis,
			dayBasisText: dayInfo.basisText,
		};
	}
	// A3 起贵神盘：di=地盘(贵人直坐落支)、tian=天盘(贵人落支在天盘上方之地盘位起布，§3.4(5))。
	let startIdx = LRConst.ZiList.indexOf(startZi);
	if(guiPan === 'tian' && so.yuejiang){
		const yjIdx = LRConst.ZiList.indexOf(so.yuejiang);
		const tIdx = LRConst.ZiList.indexOf(timeZi);
		const sIdx = LRConst.ZiList.indexOf(startZi);
		if(yjIdx >= 0 && tIdx >= 0 && sIdx >= 0){
			// 天盘[地盘位 di] = (月将+di-时)%12；解 tianPan[di*]=startZi → di* 为贵人落支上方的地盘位。
			startIdx = (sIdx - yjIdx + tIdx + 24) % 12;
		}
	}
	const map = {};
	for(let i=0; i<JinKouGuiShenSeq.length; i++){
		const idxVal = reverse ? (startIdx - i + 12) % 12 : (startIdx + i) % 12;
		const key = LRConst.ZiList[idxVal];
		map[key] = JinKouGuiShenSeq[i];
	}
	const name = map[diFen] ? map[diFen] : '';
	return {
		name: name,
		zi: JinKouGuiShenZi[name] ? JinKouGuiShenZi[name] : '',
		startZi: startZi,
		isDay: isDay,
		dayBasis: dayInfo.basis,
		dayBasisText: dayInfo.basisText,
		// 整圈回报：本地三盘环直接复用这张圈，杜绝「贵神起例两份实现」。
		circle: map,
	};
}

// —— 本地三盘环（G21）——
// 与后端 /jinkou/pan 的 plates 同形：{index, di, tian, jiang, shen, gui}。
//   天盘[di] = 月将加占时后落于该地盘位之支（= getJiangZiAtDiFen 同一式）
//   将名     = 天盘支的十二将名
//   贵神     = 贵神圈在该地盘位之神名；神盘 = 该贵神所属之支
// 流派一偏离默认，后端环即失真（后端不解流派），故此处按当前流派现算，替代「待续」占位。
function buildJinKouPlates(yuejiang, timeZi, guiCircle){
	if(!yuejiang || !timeZi){ return []; }
	return LRConst.ZiList.map((di, i)=>{
		const j = getJiangZiAtDiFen(yuejiang, timeZi, di);
		const gui = (guiCircle && guiCircle[di]) ? guiCircle[di] : '';
		return {
			index: i + 1,
			di: di,
			tian: j.zi || '',
			jiang: j.name || '',
			shen: gui ? (JinKouGuiShenZi[gui] || '') : '',
			gui: gui,
		};
	});
}

function getYueJiang(liureng, monthZi, school){
	const jieqi = resolveJieqiForYueJiang(liureng);
	// A1 月将换将流派：jiaojie=交节即换、否则中气换将(默认)。节气名缺失时两派均 fallback 月支六合。
	const table = school === 'jiaojie' ? JinKouYueJiangByJieQi_JiaoJie : JinKouYueJiangByJieQi;
	if(jieqi && table[jieqi]){
		return table[jieqi];
	}
	const explicitYue = extractFromList(liureng && liureng.yue ? liureng.yue : '', LRConst.ZiList);
	if(explicitYue){
		return explicitYue;
	}
	return JinKouYueJiangByMonthBranch[monthZi] ? JinKouYueJiangByMonthBranch[monthZi] : LRConst.ZiHe[monthZi];
}

function getJiangZiAtDiFen(yuejiang, timeZi, diFen){
	if(!yuejiang){
		return {
			yuejiang: '',
			zi: '',
			name: '',
		};
	}
	const monthIdx = LRConst.ZiList.indexOf(yuejiang);
	const timeIdx = LRConst.ZiList.indexOf(timeZi);
	const diFenIdx = LRConst.ZiList.indexOf(diFen);
	if(monthIdx < 0 || timeIdx < 0 || diFenIdx < 0){
		return {
			yuejiang: yuejiang,
			zi: '',
			name: '',
		};
	}
	const idx = (monthIdx + diFenIdx - timeIdx + 120) % 12;
	const zi = LRConst.ZiList[idx];
	return {
		yuejiang: yuejiang,
		zi: zi,
		name: JinKouYueJiangName[zi] ? JinKouYueJiangName[zi] : '',
	};
}

function parseBranches(text){
	const txt = `${text || ''}`;
	const res = [];
	for(let i=0; i<txt.length; i++){
		const one = txt.substr(i, 1);
		if(LRConst.ZiList.indexOf(one) >= 0){
			res.push(one);
		}
	}
	return uniq(res);
}

function calcSiDaKongWang(xunShou){
	const gan = extractFromList(xunShou, LRConst.GanList);
	const zi = extractFromList(xunShou, LRConst.ZiList);
	if(gan && gan !== '甲'){
		return '';
	}
	if(zi === '子' || zi === '午'){
		return '水';
	}
	if(zi === '寅' || zi === '申'){
		return '金';
	}
	return '';
}

function getElem(val){
	return LRConst.GanZiWuXing[val] ? LRConst.GanZiWuXing[val] : '';
}

function shiftZi(zi, delta){
	const idx = LRConst.ZiList.indexOf(zi);
	if(idx < 0){
		return '';
	}
	const i = (idx + delta + 1200) % 12;
	return LRConst.ZiList[i];
}

function getMonthIndexByZi(monthZi){
	const idx = LRConst.ZiList.indexOf(monthZi);
	if(idx < 0){
		return 0;
	}
	return ((idx - 2 + 12) % 12) + 1;
}

function getSeasonByMonthZi(monthZi){
	const idx = getMonthIndexByZi(monthZi);
	if(idx >= 1 && idx <= 3){
		return '春';
	}
	if(idx >= 4 && idx <= 6){
		return '夏';
	}
	if(idx >= 7 && idx <= 9){
		return '秋';
	}
	if(idx >= 10 && idx <= 12){
		return '冬';
	}
	return '';
}

function getYinYangSign(val){
	if(LRConst.YangGan.indexOf(val) >= 0 || LRConst.YangZi.indexOf(val) >= 0){
		return '+';
	}
	if(LRConst.YingGan.indexOf(val) >= 0 || LRConst.YingZi.indexOf(val) >= 0){
		return '-';
	}
	return '';
}

function resolveYongYao(lineSigns){
	const lines = lineSigns instanceof Array ? lineSigns : [];
	let yangCount = 0;
	let yinCount = 0;
	let yangLine = null;
	let yinLine = null;
	for(let i=0; i<lines.length; i++){
		const one = lines[i];
		if(one.sign === '+'){
			yangCount += 1;
			yangLine = one;
		}else if(one.sign === '-'){
			yinCount += 1;
			yinLine = one;
		}
	}

	if(yangCount === 1 && yinCount === 3){
		return {
			label: yangLine ? yangLine.label : '',
			sign: '+',
			reason: '三阴一阳，以阳为用',
			theme: '男子',
		};
	}
	if(yangCount === 3 && yinCount === 1){
		return {
			label: yinLine ? yinLine.label : '',
			sign: '-',
			reason: '三阳一阴，以阴为用',
			theme: '女子',
		};
	}
	if(yangCount === 2 && yinCount === 2){
		const jiang = lines.find((item)=>item.label === '将神');
		return {
			label: jiang ? jiang.label : '将神',
			sign: jiang ? jiang.sign : '',
			reason: '二阴二阳，以将为用',
			theme: jiang && jiang.sign === '+' ? '男子' : '女子',
		};
	}
	if(yangCount === 0 && yinCount === 4){
		return {
			label: '人元',
			sign: '+',
			reason: '纯阴反阳，以阳为用',
			theme: '男子',
		};
	}
	if(yangCount === 4 && yinCount === 0){
		return {
			label: '贵神',
			sign: '-',
			reason: '纯阳反阴，以星为用',
			theme: '女子',
		};
	}
	const fallback = lines.find((item)=>item.label === '将神');
	return {
		label: fallback ? fallback.label : '',
		sign: fallback ? fallback.sign : '',
		reason: '按将神为用',
		theme: '',
	};
}

function getSeason(liureng, elem){
	if(!liureng || !liureng.season || !elem){
		return '';
	}
	const map = liureng.season;
	if(map[elem]){
		return map[elem];
	}
	const keys = Object.keys(map);
	for(let i=0; i<keys.length; i++){
		const key = keys[i];
		if(key.indexOf(elem) >= 0){
			return map[key];
		}
	}
	return '';
}

function buildPowerText(elem, sign, season){
	// 旺衰文本仅「五行+旺衰」(如 金相/土旺)；阴阳(+/-)另列单独显示，避免与旺衰连写「金-相」误解。
	let txt = elem ? elem : '—';
	if(season){
		txt += season;
	}
	return txt;
}

function normalizeElements(elements){
	const vals = elements instanceof Array ? elements : [];
	const out = [];
	for(let i=0; i<vals.length; i++){
		const elem = `${vals[i] || ''}`;
		if(JinKouWuXingKe[elem]){
			out.push(elem);
		}
	}
	return out;
}

function countElements(elements){
	const map = {};
	for(let i=0; i<elements.length; i++){
		const elem = elements[i];
		map[elem] = map[elem] ? map[elem] + 1 : 1;
	}
	return map;
}

function rankElements(keys, counts, scores){
	const ary = keys.slice(0);
	ary.sort((a, b)=>{
		const scoreA = scores && scores[a] !== undefined ? scores[a] : 0;
		const scoreB = scores && scores[b] !== undefined ? scores[b] : 0;
		if(scoreA !== scoreB){
			return scoreB - scoreA;
		}
		const cntA = counts && counts[a] !== undefined ? counts[a] : 0;
		const cntB = counts && counts[b] !== undefined ? counts[b] : 0;
		if(cntA !== cntB){
			return cntB - cntA;
		}
		return JinKouWuXingOrder.indexOf(a) - JinKouWuXingOrder.indexOf(b);
	});
	return ary;
}

export function calcJinKouWangElem(elements){
	const vals = normalizeElements(elements);
	if(vals.length === 0){
		return '';
	}
	const counts = countElements(vals);
	const keys = Object.keys(counts);
	if(keys.length === 1){
		return keys[0];
	}

	let maxCount = 0;
	for(let i=0; i<keys.length; i++){
		const cnt = counts[keys[i]];
		if(cnt > maxCount){
			maxCount = cnt;
		}
	}
	if(maxCount >= 3){
		return rankElements(keys, counts)[0];
	}

	if(keys.length === 4){
		let missing = '';
		for(let i=0; i<JinKouWuXingOrder.length; i++){
			const elem = JinKouWuXingOrder[i];
			if(!counts[elem]){
				missing = elem;
				break;
			}
		}
		if(missing && JinKouWuXingKe[missing]){
			return JinKouWuXingKe[missing];
		}
		return rankElements(keys, counts)[0];
	}

	if(keys.length === 2){
		const a = keys[0];
		const b = keys[1];
		if(counts[a] !== counts[b]){
			return counts[a] > counts[b] ? a : b;
		}
		if(JinKouWuXingKe[a] === b){
			return a;
		}
		if(JinKouWuXingKe[b] === a){
			return b;
		}
		if(JinKouWuXingSheng[a] === b){
			return b;
		}
		if(JinKouWuXingSheng[b] === a){
			return a;
		}
		return rankElements(keys, counts)[0];
	}

	let pairElem = '';
	const singles = [];
	for(let i=0; i<keys.length; i++){
		const elem = keys[i];
		if(counts[elem] >= 2){
			pairElem = elem;
		}else{
			singles.push(elem);
		}
	}
	if(pairElem){
		for(let i=0; i<keys.length; i++){
			const target = keys[i];
			if(target !== pairElem && JinKouWuXingKe[pairElem] === target){
				return pairElem;
			}
		}
		for(let i=0; i<singles.length; i++){
			if(JinKouWuXingKe[singles[i]] === pairElem){
				return singles[i];
			}
		}
		for(let i=0; i<singles.length; i++){
			for(let j=0; j<singles.length; j++){
				if(i !== j && JinKouWuXingKe[singles[i]] === singles[j]){
					return singles[i];
				}
			}
		}
	}

	const score = {};
	for(let i=0; i<keys.length; i++){
		const one = keys[i];
		score[one] = 0;
		for(let j=0; j<keys.length; j++){
			const target = keys[j];
			if(one !== target && JinKouWuXingKe[one] === target){
				score[one] += counts[target];
			}
		}
	}
	return rankElements(keys, counts, score)[0];
}

export function buildJinKouWangShuaiMap(wangElem){
	const map = {};
	if(!wangElem || !JinKouWuXingKe[wangElem]){
		return map;
	}
	map[wangElem] = '旺';
	map[JinKouWuXingSheng[wangElem]] = '相';
	map[JinKouWuXingKe[wangElem]] = '死';
	const keys = Object.keys(JinKouWuXingSheng);
	for(let i=0; i<keys.length; i++){
		const elem = keys[i];
		if(JinKouWuXingSheng[elem] === wangElem){
			map[elem] = '休';
			break;
		}
	}
	const ctrlKeys = Object.keys(JinKouWuXingKe);
	for(let i=0; i<ctrlKeys.length; i++){
		const elem = ctrlKeys[i];
		if(JinKouWuXingKe[elem] === wangElem){
			map[elem] = '囚';
			break;
		}
	}
	return map;
}

function valueContainsAny(val, tokens){
	if(val === undefined || val === null){
		return false;
	}
	if(val instanceof Array){
		for(let i=0; i<val.length; i++){
			if(valueContainsAny(val[i], tokens)){
				return true;
			}
		}
		return false;
	}
	const txt = `${val}`;
	for(let i=0; i<tokens.length; i++){
		if(tokens[i] && txt.indexOf(tokens[i]) >= 0){
			return true;
		}
	}
	return false;
}

function collectShenSha(liureng, tokens){
	if(!liureng || !tokens || tokens.length === 0){
		return [];
	}
	const maps = [
		liureng.gods,
		liureng.godsGan,
		liureng.godsMonth,
		liureng.godsZi,
		liureng.godsYear && liureng.godsYear.taisui1 ? liureng.godsYear.taisui1 : null,
	];
	const res = [];
	for(let i=0; i<maps.length; i++){
		const one = maps[i];
		if(!one){
			continue;
		}
		const keys = Object.keys(one);
		for(let j=0; j<keys.length; j++){
			const key = keys[j];
			if(valueContainsAny(one[key], tokens)){
				res.push(key);
			}
		}
	}
	return uniq(res);
}

function rowStem(row){
	if(!row){
		return '';
	}
	if(LRConst.GanList.indexOf(row.gan) >= 0){
		return row.gan;
	}
	if(LRConst.GanList.indexOf(row.content) >= 0){
		return row.content;
	}
	return '';
}

function rowBranch(row){
	if(!row){
		return '';
	}
	if(LRConst.ZiList.indexOf(row.content) >= 0){
		return row.content;
	}
	return '';
}

function addRowGod(godMap, label, god){
	if(!godMap[label]){
		godMap[label] = {};
	}
	godMap[label][god] = true;
}

function addGodByStems(rows, godMap, god, stems){
	const list = stems instanceof Array ? stems : [];
	if(list.length === 0){
		return;
	}
	for(let i=0; i<rows.length; i++){
		const row = rows[i];
		const stem = rowStem(row);
		if(stem && list.indexOf(stem) >= 0){
			addRowGod(godMap, row.label, god);
		}
	}
}

function addGodByBranches(rows, godMap, god, branches){
	const list = branches instanceof Array ? branches : [];
	if(list.length === 0){
		return;
	}
	for(let i=0; i<rows.length; i++){
		const row = rows[i];
		const zi = rowBranch(row);
		if(zi && list.indexOf(zi) >= 0){
			addRowGod(godMap, row.label, god);
		}
	}
}

// 支对类神煞（牢禁关锁/四绝）：判据为「甲支上见乙支」，即课中同见此二支方成。
// 命中时二位皆标（用法铁律：地支类神煞须用爻临之才取用，取用过滤在 buildJinKouShenshaDoc 之后）。
function addGodByBranchPair(rows, godMap, god, pairs){
	const list = pairs instanceof Array ? pairs : [];
	if(list.length === 0){ return; }
	const byBranch = {};
	for(let i=0; i<rows.length; i++){
		const zi = rowBranch(rows[i]);
		if(zi){
			if(!byBranch[zi]){ byBranch[zi] = []; }
			byBranch[zi].push(rows[i].label);
		}
	}
	list.forEach((pair)=>{
		const base = pair[0];
		const over = pair[1];
		if(!byBranch[base] || !byBranch[over]){ return; }
		byBranch[base].forEach((label)=>addRowGod(godMap, label, god));
		byBranch[over].forEach((label)=>addRowGod(godMap, label, god));
	});
}

function addGodByGanZi(rows, godMap, god, ganzi){
	if(!ganzi || ganzi.length < 2){
		return;
	}
	const gan = ganzi.substr(0, 1);
	const zi = ganzi.substr(1, 1);
	for(let i=0; i<rows.length; i++){
		const row = rows[i];
		if(rowStem(row) === gan && rowBranch(row) === zi){
			addRowGod(godMap, row.label, god);
		}
	}
}

function getJieShaByZi(zi){
	if(!zi){
		return '';
	}
	const group = {
		'申': '巳',
		'子': '巳',
		'辰': '巳',
		'亥': '申',
		'卯': '申',
		'未': '申',
		'寅': '亥',
		'午': '亥',
		'戌': '亥',
		'巳': '寅',
		'酉': '寅',
		'丑': '寅',
	};
	return group[zi] ? group[zi] : '';
}

function inverseKeElem(elem){
	const keys = Object.keys(JinKouWuXingKe);
	for(let i=0; i<keys.length; i++){
		const one = keys[i];
		if(JinKouWuXingKe[one] === elem){
			return one;
		}
	}
	return '';
}

function getBranchesByElem(elem){
	const res = [];
	for(let i=0; i<LRConst.ZiList.length; i++){
		const zi = LRConst.ZiList[i];
		if(getElem(zi) === elem){
			res.push(zi);
		}
	}
	return res;
}

// §9 起例补全用表（标准三合沐浴/驿马后位/临官后位，与既有 getJieShaByZi 解耦，独立标准表）
const JINKOU_TAOHUA_BY_ZI = { '申': '酉', '子': '酉', '辰': '酉', '寅': '卯', '午': '卯', '戌': '卯', '巳': '午', '酉': '午', '丑': '午', '亥': '子', '卯': '子', '未': '子' };
const JINKOU_MADAO_BY_ZI = { '申': '卯', '子': '卯', '辰': '卯', '寅': '酉', '午': '酉', '戌': '酉', '巳': '子', '酉': '子', '丑': '子', '亥': '午', '卯': '午', '未': '午' };
const JINKOU_LUDAO_BY_GAN = { '甲': '卯', '乙': '辰', '丙': '午', '丁': '未', '戊': '午', '己': '未', '庚': '酉', '辛': '戌', '壬': '子', '癸': '丑' };

function calcJinKouShenShaRows(liureng, rows, ext){
	const godMap = {};
	for(let i=0; i<rows.length; i++){
		godMap[rows[i].label] = {};
	}
	const dayGan = getDayGan(liureng);
	const dayZi = getDayZi(liureng);
	const monthZi = getMonthZi(liureng);
	const yearZi = getYearZi(liureng);
	const monthIdx = getMonthIndexByZi(monthZi);
	const season = getSeasonByMonthZi(monthZi);
	const tianDeTokens = [
		['丁'],
		['申', '庚'],
		['壬'],
		['辛'],
		['亥', '壬'],
		['甲'],
		['癸'],
		['寅', '甲'],
		['丙'],
		['乙'],
		['巳', '丙'],
		['庚'],
	];
	const tianDeHeStems = ['壬', '乙', '丁', '丙', '丁', '己', '戊', '己', '辛', '庚', '辛', '乙'];
	const yueDeStems = ['丙', '甲', '壬', '庚', '丙', '甲', '壬', '庚', '丙', '甲', '壬', '庚'];
	const yueHeStems = ['辛', '己', '丁', '乙', '辛', '己', '丁', '乙', '辛', '己', '丁', '乙'];
	const tianMaByMonth = ['', '午', '申', '戌', '子', '寅', '辰', '午', '申', '戌', '子', '寅', '辰'];
	const feiLianByMonth = ['', '戌', '巳', '午', '未', '申', '酉', '辰', '亥', '子', '丑', '寅', '卯'];
	const tianYiByMonth = ['', '戌', '亥', '子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉'];
	const shengQiByMonth = [
		[],
		['子', '午'],
		['丑', '未'],
		['寅', '申'],
		['卯', '酉'],
		['辰', '戌'],
		['巳', '亥'],
		['子', '午'],
		['丑', '未'],
		['寅', '申'],
		['卯', '酉'],
		['辰', '戌'],
		['巳', '亥'],
	];

	if(monthIdx > 0){
		addGodByStems(rows, godMap, '天德', tianDeTokens[monthIdx - 1].filter((txt)=>LRConst.GanList.indexOf(txt) >= 0));
		addGodByBranches(rows, godMap, '天德', tianDeTokens[monthIdx - 1].filter((txt)=>LRConst.ZiList.indexOf(txt) >= 0));
		addGodByStems(rows, godMap, '天德合', [tianDeHeStems[monthIdx - 1]]);
		addGodByStems(rows, godMap, '月德', [yueDeStems[monthIdx - 1]]);
		addGodByStems(rows, godMap, '月合', [yueHeStems[monthIdx - 1]]);
		// 月德合(月德之干五合)——§9 起例补全
		if(LRConst.GanHe[yueDeStems[monthIdx - 1]]){ addGodByStems(rows, godMap, '月德合', [LRConst.GanHe[yueDeStems[monthIdx - 1]]]); }
		addGodByBranches(rows, godMap, '天马', [tianMaByMonth[monthIdx]]);
		addGodByBranches(rows, godMap, '飞廉', [feiLianByMonth[monthIdx]]);
		addGodByBranches(rows, godMap, '生气', shengQiByMonth[monthIdx]);
		addGodByBranches(rows, godMap, '天医', [tianYiByMonth[monthIdx]]);
		addGodByBranches(rows, godMap, '地医', [shiftZi(tianYiByMonth[monthIdx], 6)]);
		if(monthIdx % 2 === 0){
			addGodByBranches(rows, godMap, '灭门', [shiftZi(monthZi, 3)]);
		}else{
			addGodByBranches(rows, godMap, '灭门', [shiftZi(monthZi, -3)]);
		}
	}

	if(season === '春'){
		addGodByGanZi(rows, godMap, '天赦', '戊寅');
		addGodByBranches(rows, godMap, '天喜', ['戌', '亥', '子']);
		addGodByBranches(rows, godMap, '丧车', ['酉']);
		addGodByBranches(rows, godMap, '三丘', ['丑']);
		addGodByBranches(rows, godMap, '四墓', ['未']);
	}else if(season === '夏'){
		addGodByGanZi(rows, godMap, '天赦', '甲午');
		addGodByBranches(rows, godMap, '天喜', ['丑', '寅', '卯']);
		addGodByBranches(rows, godMap, '丧车', ['子']);
		addGodByBranches(rows, godMap, '三丘', ['辰']);
		addGodByBranches(rows, godMap, '四墓', ['戌']);
	}else if(season === '秋'){
		addGodByGanZi(rows, godMap, '天赦', '戊申');
		addGodByBranches(rows, godMap, '天喜', ['辰', '巳', '午']);
		addGodByBranches(rows, godMap, '丧车', ['卯']);
		addGodByBranches(rows, godMap, '三丘', ['未']);
		addGodByBranches(rows, godMap, '四墓', ['丑']);
	}else if(season === '冬'){
		addGodByGanZi(rows, godMap, '天赦', '甲子');
		addGodByBranches(rows, godMap, '天喜', ['未', '申', '酉']);
		addGodByBranches(rows, godMap, '丧车', ['午']);
		addGodByBranches(rows, godMap, '三丘', ['戌']);
		addGodByBranches(rows, godMap, '四墓', ['辰']);
	}

	if(dayZi){
		const yiMaByDay = getJieShaByZi(dayZi);
		addGodByBranches(rows, godMap, '劫煞', [yiMaByDay]);
		addGodByBranches(rows, godMap, '地煞', [shiftZi(yiMaByDay, 5)]);
		addGodByBranches(rows, godMap, '望门', [shiftZi(yiMaByDay, 6)]);
		// 桃花(日支三合沐浴)、马倒(日支驿马后一位)——§9 起例补全
		if(JINKOU_TAOHUA_BY_ZI[dayZi]){ addGodByBranches(rows, godMap, '桃花', [JINKOU_TAOHUA_BY_ZI[dayZi]]); }
		if(JINKOU_MADAO_BY_ZI[dayZi]){ addGodByBranches(rows, godMap, '马倒', [JINKOU_MADAO_BY_ZI[dayZi]]); }
	}
	if(monthZi){
		addGodByBranches(rows, godMap, '驿马', [getJieShaByZi(monthZi), getJieShaByZi(dayZi)]);
	}

	if(yearZi){
		addGodByBranches(rows, godMap, '丧门', [shiftZi(yearZi, 2)]);
		addGodByBranches(rows, godMap, '吊客', [shiftZi(yearZi, -2)]);
		addGodByBranches(rows, godMap, '病符', [shiftZi(yearZi, -1)]);
	}

	if(dayGan){
		const jieMing = {
			'甲': ['申', '酉'],
			'己': ['申', '酉'],
			'乙': ['午', '未'],
			'庚': ['午', '未'],
			'丙': ['辰', '巳'],
			'辛': ['辰', '巳'],
			'丁': ['寅', '卯'],
			'壬': ['寅', '卯'],
			'戊': ['子', '丑'],
			'癸': ['子', '丑'],
		};
		const wuGui = {
			'甲': ['巳', '午'],
			'己': ['巳', '午'],
			'乙': ['寅', '卯'],
			'庚': ['寅', '卯'],
			'丙': ['子', '丑'],
			'辛': ['子', '丑'],
			'丁': ['戌', '亥'],
			'壬': ['戌', '亥'],
			'戊': ['申', '酉'],
			'癸': ['未'],
		};
		addGodByBranches(rows, godMap, '截命灾杀', jieMing[dayGan] ? jieMing[dayGan] : []);
		addGodByBranches(rows, godMap, '五鬼', wuGui[dayGan] ? wuGui[dayGan] : []);
		// 禄倒(日干临官后一位)——§9 起例补全
		if(JINKOU_LUDAO_BY_GAN[dayGan]){ addGodByBranches(rows, godMap, '禄倒', [JINKOU_LUDAO_BY_GAN[dayGan]]); }
		if(dayGan === '丁'){
			addRowGod(godMap, '人元', '六丁');
		}
		if(dayGan === '甲'){
			addRowGod(godMap, '人元', '六甲');
		}
	}

	if(ext && ext.renYuanGan === '丁'){
		addRowGod(godMap, '人元', '六丁');
	}
	if(ext && ext.renYuanGan === '甲'){
		addRowGod(godMap, '人元', '六甲');
	}

	// —— 牢禁关锁类（§9.4）：地支相对成煞，须用爻临之方取用 ——
	// 关＝酉上见寅（关节不通）；隔＝卯上见戌；锁＝卯上见申；
	// 斩关＝申上见卯 / 卯上见酉；毁隔＝寅上见辰 / 辰上见卯；破锁＝午上见申 / 申上见卯。
	addGodByBranchPair(rows, godMap, '关', [['酉', '寅']]);
	addGodByBranchPair(rows, godMap, '隔', [['卯', '戌']]);
	addGodByBranchPair(rows, godMap, '锁', [['卯', '申']]);
	addGodByBranchPair(rows, godMap, '斩关', [['申', '卯'], ['卯', '酉']]);
	addGodByBranchPair(rows, godMap, '毁隔', [['寅', '辰'], ['辰', '卯']]);
	addGodByBranchPair(rows, godMap, '破锁', [['午', '申'], ['申', '卯']]);
	// 四绝（§9.3）：寅见酉金绝、卯见申木绝、午见亥水绝、子见巳火绝。
	addGodByBranchPair(rows, godMap, '四绝', [['寅', '酉'], ['卯', '申'], ['午', '亥'], ['子', '巳']]);
	// 天罗地网（§9.4）：日支前一辰为天罗、其对冲为地网（常见戌亥、辰巳）。
	if(dayZi){
		const tianLuo = shiftZi(dayZi, 1);
		const diWang = shiftZi(tianLuo, 6);
		addGodByBranches(rows, godMap, '天罗', [tianLuo]);
		addGodByBranches(rows, godMap, '地网', [diWang]);
	}
	// 三奇（§9.1）：天三奇甲戊庚 / 地三奇乙丙丁 / 人三奇壬癸辛——四位天干见齐方取。
	const fourStemsForQi = [];
	for(let i=0; i<rows.length; i++){
		const st = rowStem(rows[i]);
		if(st){ fourStemsForQi.push(st); }
	}
	JINKOU_SANQI_SETS.forEach((set)=>{
		if(!set.every((g)=>fourStemsForQi.indexOf(g) >= 0)){ return; }
		addGodByStems(rows, godMap, '三奇', set);
	});

	if(ext && ext.guiZi){
		addGodByBranches(rows, godMap, '官符', [shiftZi(ext.guiZi, 6)]);
	}
	if(ext && ext.jiangElem){
		const tianDaoElem = inverseKeElem(ext.jiangElem);
		addGodByBranches(rows, godMap, '天盗', getBranchesByElem(tianDaoElem));
	}

	const branches = [];
	const branchCount = {};
	for(let i=0; i<rows.length; i++){
		const zi = rowBranch(rows[i]);
		if(!zi){
			continue;
		}
		branches.push({ label: rows[i].label, zi: zi });
		branchCount[zi] = branchCount[zi] ? branchCount[zi] + 1 : 1;
	}
	const hasBranch = (zi)=>branches.some((item)=>item.zi === zi);
	for(let i=0; i<branches.length; i++){
		const one = branches[i];
		const zi = one.zi;
		let hitSanXing = false;
		if((zi === '寅' && (hasBranch('巳') || hasBranch('申'))) ||
			(zi === '巳' && (hasBranch('寅') || hasBranch('申'))) ||
			(zi === '申' && (hasBranch('寅') || hasBranch('巳'))) ||
			(zi === '子' && hasBranch('卯')) ||
			(zi === '卯' && hasBranch('子')) ||
			(zi === '丑' && (hasBranch('戌') || hasBranch('未'))) ||
			(zi === '戌' && (hasBranch('丑') || hasBranch('未'))) ||
			(zi === '未' && (hasBranch('丑') || hasBranch('戌'))) ||
			((zi === '辰' || zi === '午' || zi === '酉' || zi === '亥') && branchCount[zi] >= 2)){
			hitSanXing = true;
		}
		if(hitSanXing){
			addRowGod(godMap, one.label, '三刑');
		}
		const liuHaiPair = {
			'子': '未',
			'未': '子',
			'丑': '午',
			'午': '丑',
			'寅': '巳',
			'巳': '寅',
			'卯': '辰',
			'辰': '卯',
			'申': '亥',
			'亥': '申',
			'酉': '戌',
			'戌': '酉',
		};
		if(liuHaiPair[zi] && hasBranch(liuHaiPair[zi])){
			addRowGod(godMap, one.label, '六害');
		}
	}

	const orderIdx = {};
	for(let i=0; i<JinKouShenShaOrder.length; i++){
		orderIdx[JinKouShenShaOrder[i]] = i;
	}
	const res = [];
	for(let i=0; i<rows.length; i++){
		const label = rows[i].label;
		const names = Object.keys(godMap[label] ? godMap[label] : {});
		names.sort((a, b)=>{
			const ia = orderIdx[a] !== undefined ? orderIdx[a] : 9999;
			const ib = orderIdx[b] !== undefined ? orderIdx[b] : 9999;
			if(ia !== ib){
				return ia - ib;
			}
			return a.localeCompare(b, 'zh-Hans-CN');
		});
		res.push({
			label: `${label}神煞`,
			value: names.length ? names.join('、') : '无',
		});
	}
	return res;
}

function calcKongFlag(option){
	const flags = [];
	if(option.branch && option.emptyBranches.indexOf(option.branch) >= 0){
		flags.push('空亡');
	}
	let hitSiDa = false;
	if(option.siDaKong){
		if(option.elem && option.elem === option.siDaKong){
			hitSiDa = true;
		}
		if(option.ganElem && option.ganElem === option.siDaKong){
			hitSiDa = true;
		}
	}
	if(hitSiDa){
		flags.push('四大空亡');
	}
	return flags.length ? flags.join(' / ') : '—';
}

function buildRow(option){
	const elem = option.elem ? option.elem : '';
	const sign = option.sign ? option.sign : '';
	const season = option.season ? option.season : '';
	const ganElem = option.ganElem ? option.ganElem : '';
	const powerColor = JinKouElementColor[elem] ? JinKouElementColor[elem] : '#262626';
	return {
		label: option.label,
		gan: option.gan ? option.gan : '-',
		content: option.content ? option.content : '—',
		shenjiang: option.shenjiang ? option.shenjiang : '-',
		power: buildPowerText(elem, sign, season),
		kong: calcKongFlag({
			branch: option.branch,
			elem: elem,
			ganElem: ganElem,
			emptyBranches: option.emptyBranches ? option.emptyBranches : [],
			siDaKong: option.siDaKong ? option.siDaKong : '',
		}),
		elem: elem,
		sign: sign,
		season: season,
		contentColor: JinKouElementColor[elem] ? JinKouElementColor[elem] : '#262626',
		ganColor: JinKouElementColor[ganElem] ? JinKouElementColor[ganElem] : '#262626',
		powerColor: powerColor,
	};
}

// —— 解读层：五行生克 / 地支关系 / 四位生克 / 太玄数 / 用神强弱 / 应期 / 神煞判语 ——
function wuxingRelation(a, b){
	if(!a || !b){ return ''; }
	if(a === b){ return '比和'; }
	if(JinKouWuXingSheng[a] === b){ return '生'; }
	if(JinKouWuXingSheng[b] === a){ return '被生'; }
	if(JinKouWuXingKe[a] === b){ return '克'; }
	if(JinKouWuXingKe[b] === a){ return '被克'; }
	return '';
}

function branchRelTypes(a, b){
	if(!a || !b){ return []; }
	const res = [];
	const both = (map)=>map && (map[a] === b || map[b] === a);
	const bothArr = (map)=>map && ((map[a] && map[a].indexOf(b) >= 0) || (map[b] && map[b].indexOf(a) >= 0));
	if(both(LRConst.ZiCong)){ res.push('冲'); }
	if(both(LRConst.ZiHe)){ res.push('合'); }
	if(bothArr(LRConst.ZiSangHe)){ res.push('三合'); }
	if(both(LRConst.ZiHai)){ res.push('害'); }
	if(both(LRConst.ZiPo)){ res.push('破'); }
	if(both(LRConst.ZiXing)){ res.push('刑'); }
	return res;
}

function buildJinKouRelations(rows){
	const byLabel = {};
	rows.forEach((r)=>{ byLabel[r.label] = r; });
	const pairs = [['贵神', '人元'], ['将神', '贵神'], ['地分', '将神'], ['地分', '人元'], ['地分', '贵神'], ['将神', '人元']];
	const out = [];
	pairs.forEach((pair)=>{
		const a = byLabel[pair[0]];
		const b = byLabel[pair[1]];
		if(!a || !b || !a.elem || !b.elem){ return; }
		const rel = wuxingRelation(a.elem, b.elem);
		if(!rel){ return; }
		const key = `${pair[0]}_${rel}_${pair[1]}`;
		const text = JINKOU_RELATION_DOC[key] || JINKOU_RELATION_DOC[`_${rel}_`] || '';
		out.push({ from: pair[0], to: pair[1], rel: rel, fromElem: a.elem, toElem: b.elem, text: text });
	});
	// 干元类（§10.3）：神干(贵神之遁干) ↔ 将干(将神之遁干)，先判天干五合（合局），否则按五行生克。
	const shenRow = byLabel['贵神'], jiangRow = byLabel['将神'];
	if(shenRow && jiangRow && shenRow.gan && jiangRow.gan && shenRow.gan !== '-' && jiangRow.gan !== '-' && shenRow.ganElem && jiangRow.ganElem){
		const rel = (LRConst.GanHe[shenRow.gan] === jiangRow.gan) ? '合' : wuxingRelation(shenRow.ganElem, jiangRow.ganElem);
		if(rel){
			const key = `神干_${rel}_将干`;
			const text = JINKOU_RELATION_DOC[key] || JINKOU_RELATION_DOC[`_${rel}_`] || '';
			out.push({ from: '神干', to: '将干', rel: rel, fromElem: shenRow.ganElem, toElem: jiangRow.ganElem, text: text });
		}
	}
	return out;
}

// 五比同类（§10.4）：四位两两五行同气定名；四位全同气优先取「合比」。
export function buildJinKouBihe(rows){
	const byLabel = {};
	rows.forEach((r)=>{ byLabel[r.label] = r; });
	const elemOf = (label)=>{ const r = byLabel[label]; return r && r.elem ? r.elem : ''; };
	const out = [];
	const elems = ['人元', '贵神', '将神', '地分'].map(elemOf);
	if(elems[0] && elems.every((e)=>e === elems[0])){
		out.push({ name: '合比', text: JINKOU_BIHE_DOC['合比'].text });
		return out;
	}
	['正比', '近比', '远比', '次比'].forEach((name)=>{
		const def = JINKOU_BIHE_DOC[name];
		const ea = elemOf(def.pair[0]);
		const eb = elemOf(def.pair[1]);
		if(ea && eb && ea === eb){
			out.push({ name: name, text: def.text });
		}
	});
	return out;
}

// 象意（§4.7/§4.8）：当前贵神(断事之性质) + 将神月将(断经过/媒介)的象意。
function buildJinKouXiangyi(guiName, jiangName){
	const gs = guiName && JINKOU_GUISHEN_XIANGYI[guiName] ? Object.assign({ name: guiName }, JINKOU_GUISHEN_XIANGYI[guiName]) : null;
	const yj = jiangName && JINKOU_YUEJIANG_DOC[jiangName] ? { name: jiangName, desc: JINKOU_YUEJIANG_DOC[jiangName].desc } : null;
	return { guishen: gs, yuejiang: yj };
}

// 太岁月建系统（§9.9）：据年/月/日支算各项落支，命中四位者高亮。
const JINKOU_NIANYUERI_DEFS = [
	{ name: '岁君', text: '太岁所临，神将与之相生主当年迁进吉庆、受克主尊长灾困、仕人利见大人。' },
	{ name: '真太岁', text: '课中干支与太岁干支相同（伏吟），主君长领导宠用；临门户日辰年命之上，反主尊长有凶。', kind: 'ganzi' },
	{ name: '岁破', text: '太岁对冲，主道路音信、财物破散、家宅损耗、人事阻隔。' },
	{ name: '岁宅', text: '岁前五辰为宅神，主田宅争讼、家族兴衰；宅神受制则人口灾忧。' },
	{ name: '月建', text: '当月之支，旺则物盛数多、谋望有成、吉凶力壮、动则立应。' },
	{ name: '月破', text: '冲破月建，主器破忧散、病败财空、孕育不顺，反可解凶神。' },
	{ name: '月厌', text: '正戌逆行之位，主咒诅冤仇、厌恶不明之事，占病连绵。' },
	{ name: '日建', text: '将神与日辰相同，主一日之事：吉则先凶后吉、凶则先吉后凶。', kind: 'jiangDay' },
	{ name: '日冲', text: '课被日辰冲破，主器物破坏、望事难成、人情不和；旺相逢冲即发、休囚逢破则空。' },
];
// extras（可选）：{ yearGanZi, dayGanZi, jiangZi } —— 真太岁比对整柱干支、日建比对将神与日辰，
// 二者判据非「四位含某支」，故单列 kind 分支；不传 extras 时该两项自动跳过（旧调用零回归）。
function buildJinKouNianYueRi(yearZi, monthZi, monthIdx, dayZi, fourBranches, extras){
	const four = fourBranches || [];
	const ex = extras || {};
	const zhiMap = {
		'岁君': yearZi || '',
		'岁破': yearZi ? shiftZi(yearZi, 6) : '',
		'岁宅': yearZi ? shiftZi(yearZi, 5) : '',
		'月建': monthZi || '',
		'月破': monthZi ? shiftZi(monthZi, 6) : '',
		'月厌': monthIdx > 0 ? shiftZi('戌', -(monthIdx - 1)) : '',
		'日冲': dayZi ? shiftZi(dayZi, 6) : '',
	};
	const out = [];
	JINKOU_NIANYUERI_DEFS.forEach((d)=>{
		if(d.kind === 'ganzi'){
			// 真太岁：四位所见干支柱与太岁整柱相同（贵神/将神带干支，故比对其干支串）。
			const cols = ex.fourGanZi || [];
			if(!ex.yearGanZi || !cols.length){ return; }
			const hit = cols.indexOf(ex.yearGanZi) >= 0;
			out.push({ name: d.name, zhi: ex.yearGanZi, hit: hit, text: d.text });
			return;
		}
		if(d.kind === 'jiangDay'){
			// 日建：将神与日辰同支即成（古法以将神落日辰为一日之主）。
			if(!ex.jiangZi || !dayZi){ return; }
			out.push({ name: d.name, zhi: dayZi, hit: ex.jiangZi === dayZi, text: d.text });
			return;
		}
		const zhi = zhiMap[d.name];
		if(!zhi){ return; }
		out.push({ name: d.name, zhi: zhi, hit: four.indexOf(zhi) >= 0, text: d.text });
	});
	return out;
}

// 断课避讳忌时（§10.7）：月三合局忌时(=局沐浴时) + 日干忌时；命中占时则准确率偏低。
const JINKOU_JISHI_BY_YUE = { '寅': '卯', '午': '卯', '戌': '卯', '亥': '子', '卯': '子', '未': '子', '申': '酉', '子': '酉', '辰': '酉', '巳': '午', '酉': '午', '丑': '午' };
const JINKOU_JISHI_BY_GAN = { '甲': '酉', '乙': '酉', '丙': '子', '丁': '子', '戊': '卯', '己': '卯', '庚': '午', '辛': '午', '壬': '未', '癸': '未' };
function buildJinKouJishi(monthZi, dayGan, timeZi){
	const byYue = JINKOU_JISHI_BY_YUE[monthZi] || '';
	const byGan = JINKOU_JISHI_BY_GAN[dayGan] || '';
	const hit = !!(timeZi && (timeZi === byYue || timeZi === byGan));
	return { byYue: byYue, byGan: byGan, timeZi: timeZi || '', hit: hit, text: hit ? '当前占时为断课忌时，准确率偏低，宜另择时辰或多重印证。' : '' };
}

// 五动三动（§4.4/§10.1/§10.2）：以四位两两生克定门户。干=人元、神=贵神、将=将神、方=地分。
//   五动(克)：妻=干克方、官=神克干、贼=神克将、财=将克神、鬼=方克干。
//   三动(生·同)：父母=方生干、子孙=干生方、兄弟=干方同气。逢空(关键位地支落旬空)则减断。
function buildJinKouDong(rows, xunKongBranches, yongLabel){
	const byLabel = {};
	rows.forEach((r)=>{ byLabel[r.label] = r; });
	const gan = byLabel['人元'], shen = byLabel['贵神'], jiang = byLabel['将神'], fang = byLabel['地分'];
	if(!gan || !shen || !jiang || !fang){ return { wu: [], san: [] }; }
	const kongSet = {};
	(xunKongBranches || []).forEach((z)=>{ kongSet[z] = true; });
	const zhiOf = (r)=>rowZhi(r);
	const isKong = (...rs)=>rs.some((r)=>{ const z = zhiOf(r); return z && kongSet[z]; });
	const mk = (type, fromR, toR)=>({
		type: type,
		from: fromR.label,
		to: toR.label,
		kong: isKong(fromR, toR),
		yong: yongLabel === fromR.label || yongLabel === toR.label,
		text: JINKOU_DONG_DOC[type] || '',
	});
	const rel = (a, b)=>wuxingRelation(a && a.elem, b && b.elem);
	const wu = [];
	if(rel(gan, fang) === '克'){ wu.push(mk('妻', gan, fang)); }
	if(rel(shen, gan) === '克'){ wu.push(mk('官', shen, gan)); }
	if(rel(shen, jiang) === '克'){ wu.push(mk('贼', shen, jiang)); }
	if(rel(jiang, shen) === '克'){ wu.push(mk('财', jiang, shen)); }
	if(rel(fang, gan) === '克'){ wu.push(mk('鬼', fang, gan)); }
	const san = [];
	if(rel(fang, gan) === '生'){ san.push(mk('父母', fang, gan)); }
	if(rel(gan, fang) === '生'){ san.push(mk('子孙', gan, fang)); }
	if(gan.elem && fang.elem && gan.elem === fang.elem){ san.push(mk('兄弟', gan, fang)); }
	return { wu: wu, san: san };
}

// ══ 专题起式引擎（定局法）：定地分辅助取法 / 二遁人元 / 次客法 / 测年月日 / 七专题 ══
// 起式法多只改「定地分」或「加临之位」，其余三位仍按常规法；本组统一产出 {rows-like 四位, 说明}。

// —— 定地分辅助取法 ——
// 取数法：报数/笔画 ÷12 取余（余 1 子…余 11 戌，整除取亥）。
export function jinKouZiByNumber(num){
	const n = Math.floor(Math.abs(Number(num) || 0));
	if(!n){ return ''; }
	const r = n % 12;
	return LRConst.ZiList[(r + 11) % 12];
}
// 颜色法：青绿木寅卯、赤红火巳午、黄土辰戌丑未、白金申酉、黑蓝水亥子（取该色首支）。
const JINKOU_COLOR_ZI = {
	'青': '寅', '绿': '卯', '碧': '寅', '红': '午', '赤': '巳', '朱': '午',
	'黄': '辰', '土黄': '丑', '白': '申', '金': '酉', '银': '酉',
	'黑': '亥', '蓝': '子', '灰': '戌',
};
export function jinKouZiByColor(color){
	const c = `${color || ''}`;
	const keys = Object.keys(JINKOU_COLOR_ZI);
	for(let i = 0; i < keys.length; i++){
		if(c.indexOf(keys[i]) >= 0){ return JINKOU_COLOR_ZI[keys[i]]; }
	}
	return '';
}
// 本命法：属相 → 地支。
const JINKOU_SHENGXIAO_ZI = { '鼠': '子', '牛': '丑', '虎': '寅', '兔': '卯', '龙': '辰', '蛇': '巳', '马': '午', '羊': '未', '猴': '申', '鸡': '酉', '狗': '戌', '猪': '亥' };
export function jinKouZiByShengXiao(name){
	const t = `${name || ''}`;
	const keys = Object.keys(JINKOU_SHENGXIAO_ZI);
	for(let i = 0; i < keys.length; i++){
		if(t.indexOf(keys[i]) >= 0){ return JINKOU_SHENGXIAO_ZI[keys[i]]; }
	}
	return LRConst.ZiList.indexOf(t) >= 0 ? t : '';
}
// 统一入口：按取法与输入求地分（翻书法＝页数/字数走取数法）。
export function resolveDiFenBySource(method, input){
	if(method === 'number' || method === 'stroke' || method === 'book'){ return jinKouZiByNumber(input); }
	if(method === 'color'){ return jinKouZiByColor(input); }
	if(method === 'shengxiao'){ return jinKouZiByShengXiao(input); }
	return LRConst.ZiList.indexOf(`${input || ''}`) >= 0 ? `${input}` : '';
}

// —— 二遁人元法：以原人元为新日干，五鼠遁到原地分即得；可再遁第三层 ——
const JINKOU_YIWU_SE = { '甲': '青', '乙': '蓝', '丙': '大红', '丁': '浅红', '戊': '素黄', '己': '紫·土黄', '庚': '太白', '辛': '葱白', '壬': '黑绿', '癸': '明绿' };
const JINKOU_ERDUN_XIANG = { '甲': '树木', '乙': '树木', '丙': '高岭', '丁': '高岭', '戊': '坟陇', '己': '坟陇', '庚': '斜道', '辛': '斜道', '壬': '沟渠水泽', '癸': '沟渠水泽' };
export function buildJinKouErDun(renYuanGan, diFen){
	if(!renYuanGan || !diFen){ return null; }
	const second = getStemByWuZiDun(renYuanGan, diFen);
	const third = second ? getStemByWuZiDun(second, diFen) : '';
	return {
		yuan: renYuanGan,
		gan: second,
		thirdGan: third,
		se: JINKOU_YIWU_SE[second] || '',
		xiang: JINKOU_ERDUN_XIANG[second] || '',
		note: '二遁人元＝以原人元为日干、五鼠遁至原地分之干；用于测衣色、住宅物象等细象。',
	};
}

// —— 次客法（同一时辰同一地分立多课）——
// 移神法：只换贵神，依十二贵神序逐课取；换将法：阳将后三前五、阴将前三后五（换将不换神）；
// 换日辰法：逐日换日干；用爻支合法：取用爻地支六合处作新地分；用爻干合法：用爻天干五合之支；
// 月将加日：以月将加日支（非时支）寻将神。
const JINKOU_ZHI_LIUHE = { '子': '丑', '丑': '子', '寅': '亥', '亥': '寅', '卯': '戌', '戌': '卯', '辰': '酉', '酉': '辰', '巳': '申', '申': '巳', '午': '未', '未': '午' };
const JINKOU_GAN_WUHE = { '甲': '己', '己': '甲', '乙': '庚', '庚': '乙', '丙': '辛', '辛': '丙', '丁': '壬', '壬': '丁', '戊': '癸', '癸': '戊' };
const JINKOU_GAN_LU = { '甲': '寅', '乙': '卯', '丙': '巳', '丁': '午', '戊': '巳', '己': '午', '庚': '申', '辛': '酉', '壬': '亥', '癸': '子' };
const JINKOU_YANG_ZI = ['子', '寅', '辰', '午', '申', '戌'];
export function buildJinKouCiKe(ctx){
	const { yuejiang, timeZi, diFen, dayGan, guiName, yongZhi, yongGan, dayZi } = ctx || {};
	const out = [];
	const push = (method, note, patch)=>{ out.push({ method: method, note: note, ...patch }); };
	// ① 移神法：贵神依序推次课（十二课一轮）
	if(guiName){
		const idx = JinKouGuiShenSeq.indexOf(guiName);
		if(idx >= 0){
			const next = JinKouGuiShenSeq[(idx + 1) % 12];
			push('移神法', '只换贵神、不换月将，十二贵神依序逐课取（一时辰一方位可立十二课）。', { guiName: next });
		}
	}
	// ② 换将法：阳将后三前五 / 阴将前三后五（换将不换神）
	if(yuejiang && timeZi){
		const isYang = JINKOU_YANG_ZI.indexOf(yuejiang) >= 0;
		const second = shiftZi(timeZi, isYang ? -3 : 3);
		const third = shiftZi(timeZi, isYang ? 5 : -5);
		push('换将法', `${isYang ? '阳将后三前五' : '阴将前三后五'}：另取代时之支再起将神，地分贵神不变。`, { altTimeZi: [second, third] });
	}
	// ③ 换日辰法：前一日/后一日之日干另起贵神
	if(dayGan){
		const gi = LRConst.GanList.indexOf(dayGan);
		if(gi >= 0){
			push('换日辰法', '地分月将不变，逐日换日干求贵神与人元（十课一轮）。', {
				altDayGan: [LRConst.GanList[(gi + 9) % 10], LRConst.GanList[(gi + 1) % 10]],
			});
		}
	}
	// ④ 用爻支合法：用爻地支之六合处为新地分
	if(yongZhi && JINKOU_ZHI_LIUHE[yongZhi]){
		push('用爻支合法', '取用爻地支之六合处作新地分再起一课。', { altDiFen: JINKOU_ZHI_LIUHE[yongZhi] });
	}
	// ⑤ 用爻干合法：用爻天干五合之干，取其禄支为新地分
	if(yongGan && JINKOU_GAN_WUHE[yongGan]){
		const heGan = JINKOU_GAN_WUHE[yongGan];
		push('用爻干合法', '取用爻天干五合之干，以其所临之支作新地分再起一课。', { heGan: heGan, altDiFen: JINKOU_GAN_LU[heGan] || '' });
	}
	// ⑥ 月将加日：以日支代时支寻将神（多用于测当日天气、出行、日内吉凶）
	if(dayZi && yuejiang && diFen){
		push('月将加日', '以月将加日支（非占时）寻将神，贵神人元法不变；多用于测当日吉凶。', {
			jiangZi: getJiangZiAtDiFen(yuejiang, dayZi, diFen).zi,
		});
	}
	return out;
}

// —— 移星换将：换星法（贵神改用邻日日干起）——
export function buildJinKouYiXing(dayGan){
	if(!dayGan){ return null; }
	const gi = LRConst.GanList.indexOf(dayGan);
	if(gi < 0){ return null; }
	return {
		prevDayGan: LRConst.GanList[(gi + 9) % 10],
		nextDayGan: LRConst.GanList[(gi + 1) % 10],
		note: '换星法：以前一日或后一日之日干另起贵神（其余三位不变），得参考式与原式互验；切忌主次不分。',
	};
}

// —— 测年 / 测月 / 测日三式：月将加在不同「时间支」上，再数到本相/地分 ——
// 测年＝月将加太岁宫、数到属相；测月＝月将加月支、数到属相；测日＝月将加属相、以日支为地分。
export function buildJinKouShiJian(kind, ctx){
	const { yuejiang, yearZi, monthZi, dayZi, benMing } = ctx || {};
	if(!yuejiang){ return null; }
	if(kind === 'year'){
		if(!yearZi || !benMing){ return null; }
		const j = getJiangZiAtDiFen(yuejiang, yearZi, benMing);
		return { kind: 'year', title: '测一年吉凶', addAt: yearZi, diFen: benMing, jiangZi: j.zi, jiangName: j.name, note: '月将加临太岁宫，数至本相（属相）看吉凶。' };
	}
	if(kind === 'month'){
		if(!monthZi || !benMing){ return null; }
		const j = getJiangZiAtDiFen(yuejiang, monthZi, benMing);
		return { kind: 'month', title: '测一月吉凶', addAt: monthZi, diFen: benMing, jiangZi: j.zi, jiangName: j.name, note: '月将加于月支，数至本位（属相）而断。' };
	}
	if(kind === 'day'){
		if(!dayZi || !benMing){ return null; }
		const j = getJiangZiAtDiFen(yuejiang, benMing, dayZi);
		return { kind: 'day', title: '测一日吉凶', addAt: benMing, diFen: dayZi, jiangZi: j.zi, jiangName: j.name, note: '月将加临本相之上，以当日日支为地分；星座克日则有凶来。' };
	}
	return null;
}

// —— 七专题起式（各只改定地分或加临之位）——
const JINKOU_TOPIC_DEFS = {
	yunyu: { title: '测孕育', need: ['benMing'], note: '太乙将（巳）加孕妇属相，数到地分得将神；将神阳支主男、阴支主女。' },
	xuntiangang: { title: '寻天罡·失物作案', need: [], note: '天罡（辰将）落于何地盘位，即以该位为新地分另起一式，新式用爻即作案人/盗者。' },
	jiazhai: { title: '测家宅', need: [], note: '取太岁（或本命）前五辰为宅神作地分另起宅课。' },
	guijian: { title: '测人贵贱', need: [], note: '取行年方位，月将加于人元所处，辨其旺相坐中而言，配十二贵神断贵贱。' },
	banzhi: { title: '测瘢痣', need: [], note: '人元二遁至命宫定部位，再起人元之干定痣色痕质。' },
	dajing: { title: '测打井', need: [], note: '写十二地支任抽一张作地分，常规起式；孟咸仲甘、四季泉少。' },
	fujiashi: { title: '复加时·十二方位', need: [], note: '月将复加于占时之上，沿十二方位各立一课，扫描宅院四周物象。' },
};
export function buildJinKouTopic(topicKey, ctx){
	const def = JINKOU_TOPIC_DEFS[topicKey];
	if(!def){ return null; }
	const { yuejiang, timeZi, diFen, yearZi, benMing, renYuanGan, dayGan } = ctx || {};
	const base = { key: topicKey, title: def.title, note: def.note };
	if(topicKey === 'yunyu'){
		if(!benMing){ return { ...base, ready: false, needText: '需填孕妇属相' }; }
		// 太乙巳将加孕妇属相 → 数到地分
		const j = getJiangZiAtDiFen('巳', benMing, diFen);
		const isYang = JINKOU_YANG_ZI.indexOf(j.zi) >= 0;
		return { ...base, ready: true, addAt: benMing, diFen: diFen, jiangZi: j.zi, jiangName: j.name, result: `将神${j.zi}（${j.name}）为${isYang ? '阳' : '阴'}支，主${isYang ? '男' : '女'}。` };
	}
	if(topicKey === 'xuntiangang'){
		if(!yuejiang || !timeZi){ return { ...base, ready: false, needText: '需月将与占时' }; }
		// 天罡辰将落地盘位：月将加时后，天盘辰落于地盘之支 = 辰 −(月将−时)
		const newDiFen = shiftZi('辰', -((LRConst.ZiList.indexOf(yuejiang) - LRConst.ZiList.indexOf(timeZi) + 12) % 12));
		return { ...base, ready: true, newDiFen: newDiFen, result: `天罡（辰将）落地盘${newDiFen}位，即以${newDiFen}为新地分另起一式，其用爻为作案人。` };
	}
	if(topicKey === 'jiazhai'){
		const anchor = yearZi || benMing;
		if(!anchor){ return { ...base, ready: false, needText: '需太岁或本命' }; }
		const zhaiZi = shiftZi(anchor, 5);
		return { ...base, ready: true, newDiFen: zhaiZi, result: `${anchor}前五辰为${zhaiZi}，以${zhaiZi}为宅神作地分起宅课。` };
	}
	if(topicKey === 'guijian'){
		if(!yuejiang || !renYuanGan){ return { ...base, ready: false, needText: '需月将与人元' }; }
		// 月将加于人元所临之支（人元居地分之上，故以地分为其处）
		const j = getJiangZiAtDiFen(yuejiang, diFen, diFen);
		return { ...base, ready: true, addAt: diFen, jiangZi: j.zi, jiangName: j.name, result: `月将加于人元所处（${diFen}），得${j.zi}（${j.name}），辨其旺相与所乘贵神断贵贱。` };
	}
	if(topicKey === 'banzhi'){
		if(!renYuanGan || !benMing){ return { ...base, ready: false, needText: '需人元与命宫（属相）' }; }
		const erdun = getStemByWuZiDun(renYuanGan, benMing);
		return { ...base, ready: true, erDunGan: erdun, result: `人元${renYuanGan}二遁至命宫${benMing}得${erdun}，以其部位与痕质定瘢痣所在。` };
	}
	if(topicKey === 'dajing'){
		return { ...base, ready: true, newDiFen: diFen, result: `以所抽之支（现取${diFen}）为地分常规起式，按孟仲季断水质。` };
	}
	if(topicKey === 'fujiashi'){
		if(!yuejiang || !timeZi){ return { ...base, ready: false, needText: '需月将与占时' }; }
		const list = LRConst.ZiList.map((zi)=>{
			const j = getJiangZiAtDiFen(yuejiang, timeZi, zi);
			return { fang: zi, jiangZi: j.zi, jiangName: j.name, gan: dayGan ? getStemByWuZiDun(dayGan, j.zi) : '' };
		});
		return { ...base, ready: true, rows: list, result: '沿十二方位各立一课，逐位读将神以断该方物象。' };
	}
	return { ...base, ready: false };
}
export const JINKOU_TOPIC_KEYS = Object.keys(JINKOU_TOPIC_DEFS);

// —— 专题断诀取数（数据在 JinKouDoc，此处只做「按当前课取值」）——
export function buildJinKouTopicJue(topicKey, ctx){
	const { diFen, jiangZi, guiName, erDunGan, rows } = ctx || {};
	if(topicKey === 'jiazhai' || topicKey === 'fujiashi'){
		const items = (rows || []).map((r)=>{
			const zhi = rowZhi(r);
			return zhi ? { wei: r.label, zhi: zhi, xiang: JINKOU_ZHAI_NEIJING[zhi] || '' } : null;
		}).filter(Boolean);
		return { kind: '宅内景', items: items, notes: JINKOU_ZHAI_NOTES };
	}
	if(topicKey === 'dajing'){
		const keys = Object.keys(JINKOU_DAJING_SHUIZHI);
		const hit = keys.find((k)=>JINKOU_DAJING_SHUIZHI[k].zhis.indexOf(diFen) >= 0);
		return {
			kind: '水质',
			items: hit ? [{ wei: '地分', zhi: diFen, xiang: JINKOU_DAJING_SHUIZHI[hit].text }] : [],
			notes: JINKOU_DAJING_NOTES,
		};
	}
	if(topicKey === 'banzhi'){
		const items = [];
		if(erDunGan){
			items.push({ wei: '二遁人元', zhi: erDunGan, xiang: JINKOU_BANZHI_GAN[erDunGan] || '' });
		}
		[diFen, jiangZi].filter(Boolean).forEach((z)=>{
			if(JINKOU_BANZHI_BUWEI[z]){ items.push({ wei: '所临之支', zhi: z, xiang: JINKOU_BANZHI_BUWEI[z] }); }
		});
		return { kind: '瘢痣部位', items: items, notes: JINKOU_BANZHI_NOTES };
	}
	if(topicKey === 'guijian'){
		return {
			kind: '贵贱',
			items: guiName ? [{ wei: '所乘贵神', zhi: guiName, xiang: JINKOU_GUIJIAN_JUE[guiName] || '' }] : [],
			notes: ['行年方位＋月将加人元处起式，按用爻所乘贵神断贵贱。'],
		};
	}
	return null;
}

// —— 行年旬法（按生年所在旬起一岁干支，男顺女逆，每岁进一位）——
// 六旬起例：甲子旬男丙寅女壬申、甲戌旬男丙子女壬午、甲申旬男丙戌女壬辰、
//           甲午旬男丙申女壬寅、甲辰旬男丙午女壬子、甲寅旬男丙辰女壬戌。
const JINKOU_XINGNIAN_START = {
	'甲子': { male: '丙寅', female: '壬申' },
	'甲戌': { male: '丙子', female: '壬午' },
	'甲申': { male: '丙戌', female: '壬辰' },
	'甲午': { male: '丙申', female: '壬寅' },
	'甲辰': { male: '丙午', female: '壬子' },
	'甲寅': { male: '丙辰', female: '壬戌' },
};
// 六十甲子序：由干支求序，供顺逆进位。
function ganZhiIndex(gz){
	const gan = `${gz || ''}`.charAt(0);
	const zhi = `${gz || ''}`.charAt(1);
	const gi = LRConst.GanList.indexOf(gan);
	const zi = LRConst.ZiList.indexOf(zhi);
	if(gi < 0 || zi < 0){ return -1; }
	for(let n = 0; n < 60; n++){
		if(n % 10 === gi && n % 12 === zi){ return n; }
	}
	return -1;
}
function ganZhiAt(n){
	const i = ((n % 60) + 60) % 60;
	return `${LRConst.GanList[i % 10]}${LRConst.ZiList[i % 12]}`;
}
// 生年干支 → 所在旬首（甲子/甲戌/…）。
function xunHeadOf(birthGanZi){
	const idx = ganZhiIndex(birthGanZi);
	if(idx < 0){ return ''; }
	return ganZhiAt(idx - (idx % 10));
}
export function buildJinKouXingNian(birthGanZi, gender, age){
	const head = xunHeadOf(birthGanZi);
	const start = JINKOU_XINGNIAN_START[head];
	const n = Math.floor(Number(age) || 0);
	if(!start || n < 1){ return null; }
	// gender：1/男 顺行，0/女 逆行（与全站 gender 口径一致）。
	const isMale = !(gender === 0 || gender === '0' || gender === '女');
	const startGz = isMale ? start.male : start.female;
	const si = ganZhiIndex(startGz);
	if(si < 0){ return null; }
	const cur = ganZhiAt(si + (isMale ? (n - 1) : -(n - 1)));
	const zhi = cur.charAt(1);
	return {
		birthGanZi: birthGanZi,
		xunHead: head,
		gender: isMale ? '男' : '女',
		age: n,
		startGanZi: startGz,
		ganZhi: cur,
		zhi: zhi,
		ge: JINKOU_XINGNIAN_GE[zhi] || '',
		note: `生年${birthGanZi}属${head}旬，${isMale ? '男顺行' : '女逆行'}，一岁起${startGz}，每岁进一位；取行年地支为地分可另立一课断该年灾福。`,
	};
}

// ══ 阴盘（旺衰派）公共框架：六神 / 六亲 / 旺衰量化 ══
// 只实现公开可复原的公共方法论；精细私传分值不臆造，分值表自定但前后一致，UI 明示。

// 六神（六兽）起例：按日干起第一位，自四位之下而上顺布 青龙→朱雀→勾陈→螣蛇→白虎→玄武。
const JINKOU_LIUSHEN_ORDER = ['青龙', '朱雀', '勾陈', '螣蛇', '白虎', '玄武'];
const JINKOU_LIUSHEN_START = { '甲': '青龙', '乙': '青龙', '丙': '朱雀', '丁': '朱雀', '戊': '勾陈', '己': '螣蛇', '庚': '白虎', '辛': '白虎', '壬': '玄武', '癸': '玄武' };
function buildJinKouLiuShen(rows, dayGan){
	const start = JINKOU_LIUSHEN_START[dayGan];
	if(!start){ return []; }
	const base = JINKOU_LIUSHEN_ORDER.indexOf(start);
	// 爻位自下而上：地分→将神→贵神→人元（rows 是自上而下，故反序取位次）。
	const bottomUp = (rows || []).slice().reverse();
	const out = bottomUp.map((r, i)=>{
		const name = JINKOU_LIUSHEN_ORDER[(base + i) % 6];
		return { wei: r.label, name: name, desc: JINKOU_LIUSHEN_DOC[name] || '' };
	});
	// 回到自上而下的四位序，与其余卡片一致。
	return out.reverse();
}

// 六亲：以日干为「我」（阴盘派常用口径），按五行生克给四位贴六亲标签。
function buildJinKouLiuQin(rows, selfElem){
	if(!selfElem){ return []; }
	return (rows || []).map((r)=>{
		const e = r.elem || '';
		let qin = '';
		if(!e){ qin = ''; }
		else if(e === selfElem){ qin = '兄弟'; }
		else if(wuxingRelation(e, selfElem) === '生'){ qin = '父母'; }      // 生我者父母
		else if(wuxingRelation(selfElem, e) === '生'){ qin = '子孙'; }      // 我生者子孙
		else if(wuxingRelation(e, selfElem) === '克'){ qin = '官鬼'; }      // 克我者官鬼
		else if(wuxingRelation(selfElem, e) === '克'){ qin = '妻财'; }      // 我克者妻财
		return { wei: r.label, elem: e, qin: qin, zhu: JINKOU_LIUQIN_DOC[qin] || '' };
	});
}

// 旺衰量化：月令旺相休囚死 + 十二长生宫 + 课内生克，三项合一打分。
// ⚠ 分值为公共框架下自定的一致表（非私传精细值），三项权重固定、全模块单一引用。
const JINKOU_WANGSCORE_TABLE = {
	season: { '旺': 4, '相': 2, '休': -1, '囚': -2, '死': -3 },
	changsheng: { '长生': 2, '沐浴': 0, '冠带': 2, '临官': 3, '帝旺': 3, '衰': -1, '病': -1, '死': -2, '墓': -2, '绝': -3, '胎': 0, '养': 1 },
	inner: { '受生': 1, '受克': -2, '同气': 1 },
	levels: [
		{ min: 5, level: '旺' },
		{ min: 2, level: '相' },
		{ min: -1, level: '平' },
		{ min: -4, level: '衰' },
		{ min: -99, level: '绝' },
	],
};
// 十二长生宫：五行寄十二宫（土从水，多数派「土长生在申」；寅长生为少数派，Batch 6 开关）。
const JINKOU_CHANGSHENG_ORDER = ['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养'];
const JINKOU_CHANGSHENG_START = { '木': '亥', '火': '寅', '金': '巳', '水': '申', '土': '申' };

// —— 土之十二长生两派（B6·P2）——
// 「水土同宫」（默认 shen）：土随水，长生在申；「火土同宫」（少数派 yin）：土随火，长生在寅。
// 仅作用于金口诀页的十二长生表与阴盘长生打分；共用的 LRZhangSheng.wxphase 一字不动
// （六壬/演禽等页读同一张表，改它即改别页 → 违「加新功能别改坏旧功能」）。
export const JINKOU_SOIL_PHASE_START = { shen: '申', yin: '寅' };
export function jinKouSoilStart(mode){
	return JINKOU_SOIL_PHASE_START[mode] || JINKOU_SOIL_PHASE_START.shen;
}
// 某五行的十二长生落支表 {长生:'申', 沐浴:'酉', …}；土随流派，其余四行恒定。
export function jinKouPhaseTable(elem, soilMode){
	// 五行取值非法（外部传了错值/空值）时回落默认「土」，而不是吐一张空表 ——
	// 空表会让右栏十二长生整列变「—」、快照 [十二长生] 段全为「无」，是静默降级。
	const key = JINKOU_CHANGSHENG_START[elem] !== undefined || elem === '土' ? elem : '土';
	const start = key === '土' ? jinKouSoilStart(soilMode) : JINKOU_CHANGSHENG_START[key];
	const s = LRConst.ZiList.indexOf(start);
	const out = {};
	if(s < 0){ return out; }
	JINKOU_CHANGSHENG_ORDER.forEach((name, i)=>{
		out[name] = LRConst.ZiList[(s + i) % 12];
	});
	return out;
}

function jinKouChangShengPhase(elem, zhi, soilMode){
	const start = elem === '土' ? jinKouSoilStart(soilMode) : JINKOU_CHANGSHENG_START[elem];
	if(!start || !zhi){ return ''; }
	const si = LRConst.ZiList.indexOf(start);
	const zi = LRConst.ZiList.indexOf(zhi);
	if(si < 0 || zi < 0){ return ''; }
	return JINKOU_CHANGSHENG_ORDER[(zi - si + 12) % 12];
}
function buildJinKouWangScore(rows, seasonMap, soilMode){
	const T = JINKOU_WANGSCORE_TABLE;
	// 逐行同下标遍历(不 filter)——先前用 filter(Boolean) 压缩过的数组去索引 rows，
	// 只要有一行 elem 为空，其后各行下标即整体前移，「排除自己」就排到了别人头上。
	const list = rows || [];
	return list.map((r)=>{
		const elem = r.elem || '';
		if(!elem){ return { wei: r.label, elem: '', score: 0, level: '', detail: [] }; }
		const detail = [];
		let score = 0;
		// ① 月令旺相休囚死（沿用后端 season 表，与右栏旺衰卡同源）
		const sea = seasonMap && seasonMap[elem] ? seasonMap[elem] : '';
		if(sea && T.season[sea] !== undefined){ score += T.season[sea]; detail.push(`月令${sea} ${T.season[sea] > 0 ? '+' : ''}${T.season[sea]}`); }
		// ② 十二长生宫（以本位地支论；人元无支则跳过）
		const zhi = rowZhi(r);
		const phase = zhi ? jinKouChangShengPhase(elem, zhi, soilMode) : '';
		if(phase && T.changsheng[phase] !== undefined){ score += T.changsheng[phase]; detail.push(`坐${phase} ${T.changsheng[phase] > 0 ? '+' : ''}${T.changsheng[phase]}`); }
		// ③ 课内生克：他位对本位的生/克/同气累计
		let inner = 0;
		list.forEach((otherRow)=>{
			if(otherRow === r){ return; }
			const other = otherRow.elem || '';
			if(!other){ return; }
			if(other === elem){ inner += T.inner['同气']; return; }
			if(wuxingRelation(other, elem) === '生'){ inner += T.inner['受生']; }
			else if(wuxingRelation(other, elem) === '克'){ inner += T.inner['受克']; }
		});
		if(inner){ score += inner; detail.push(`课内生克 ${inner > 0 ? '+' : ''}${inner}`); }
		const hit = T.levels.find((lv)=>score >= lv.min);
		return { wei: r.label, elem: elem, score: score, level: hit ? hit.level : '平', detail: detail };
	});
}

// 阴盘断法三层聚合（panShi==='yin' 时产出；阳盘恒 null，零回归）。
function buildJinKouYinPan(rows, dayGan, seasonMap, soilMode){
	const selfElem = getElem(dayGan);
	return {
		self: dayGan || '',
		selfElem: selfElem,
		liushen: buildJinKouLiuShen(rows, dayGan),
		liuqin: buildJinKouLiuQin(rows, selfElem),
		wangScore: buildJinKouWangScore(rows, seasonMap, soilMode),
		scoreNote: '分值为公共框架下自定的一致表（月令＋十二长生＋课内生克三项合一），非某家私传精细值；用于横向比较四位强弱，不作绝对判据。',
	};
}

// 课分内外（§3.9）：四位以中线分内外——贴地分一侧为内（自身、近、家内），
// 贴人元一侧为外（他人、远、外出）；将神贵神分居其间，用以断事在内在外、宜主宜客。
function buildJinKouNeiWai(rows, yongLabel){
	const order = ['人元', '贵神', '将神', '地分'];
	const side = { '人元': '外', '贵神': '外', '将神': '内', '地分': '内' };
	const list = order.map((label)=>{
		const row = (rows || []).find((r)=>r.label === label);
		return {
			label: label,
			side: side[label],
			yong: yongLabel === label,
			content: row ? `${row.gan && row.gan !== '-' ? row.gan : ''}${row.content && row.content !== '—' ? row.content : ''}` : '',
		};
	});
	const yongSide = yongLabel ? side[yongLabel] : '';
	const text = yongSide === '内'
		? '用爻居内（近地分一侧）：事在自身、家内、近处，宜主不宜客、宜守不宜远行。'
		: (yongSide === '外'
			? '用爻居外（近人元一侧）：事在他人、外部、远处，宜客不宜主，谋事须向外求。'
			: '');
	return { rows: list, yongSide: yongSide, text: text };
}

// 合占·扣题直断（§10.8 界定范围 + §10.9 八步收束）：
//   ① 取事分类——问财取财爻(将神)、问官取贵神、其余取用爻；
//   ② 时间范围——问日时以日时干支为参、问年以年干支为参；
//   ③ 汇聚已算之五动三动/相关神煞/用爻旺衰/内外，串成一条结论链。
// askKey 取自分类用神的 key（起课时所问事项），缺省走「用爻为主」的通则。
export const JINKOU_HEZHAN_FOCUS = {
	qiucai: { label: '财', position: '将神', note: '问财以财爻为主，财爻多在将神，地分为副财。' },
	guantu: { label: '官', position: '贵神', note: '问官以贵神为主，看其旺衰与日月生克。' },
	guansi: { label: '官司', position: '贵神', note: '问官司以贵神为我方之主、人元为对方之客。' },
	xueye: { label: '功名', position: '贵神', note: '问功名以贵神为禄位之主，人元为外部环境。' },
	jibing: { label: '病', position: '', note: '问病以受克之位定病所：人元头、贵神胸、将神腹、地分腿足。' },
	hunyue: { label: '婚', position: '将神', note: '问婚以将神定男女（阳支主男、阴支主女），看六合刑冲。' },
	huaiyun: { label: '孕', position: '将神', note: '问孕以将神（相爻）阳支主男、阴支主女。' },
};
export const JINKOU_HEZHAN_TIME = {
	day: { label: '日内', note: '问当日成否，以用爻结合日、时干支断，不取年月。' },
	year: { label: '一年', note: '问一年之事，以用爻结合太岁年干支断。' },
	default: { label: '常规', note: '未限定时段者，以用爻结合日辰为主、旁参月建太岁。' },
};
function buildJinKouHezhan(ctx){
	const rows = ctx.rows || [];
	const yongLabel = ctx.yongLabel || '';
	const askKey = ctx.askKey || '';
	const timeScope = ctx.timeScope || 'default';
	const focus = JINKOU_HEZHAN_FOCUS[askKey] || null;
	// 取用位：扣题优先（问财→将神/问官→贵神），无扣题则回落用爻位。
	const usePosition = (focus && focus.position) ? focus.position : yongLabel;
	const useRow = rows.find((r)=>r.label === usePosition) || null;
	const timeDef = JINKOU_HEZHAN_TIME[timeScope] || JINKOU_HEZHAN_TIME.default;
	// 与取用位相关的五动三动（扣题第 4 步：问什么答什么）。
	const dong = ctx.dong || { wu: [], san: [] };
	const relatedDong = [].concat(dong.wu || [], dong.san || [])
		.filter((d)=>!usePosition || d.from === usePosition || d.to === usePosition);
	// 与取用位相关的神煞（地支类神煞须用爻临之，此处按位过滤即同一口径）。
	const relatedGods = (ctx.relevantShensha || []).filter((g)=>!usePosition || g.position === usePosition);
	const chain = [];
	if(focus){ chain.push(`取事：${focus.note}`); }
	else if(yongLabel){ chain.push(`取事：未限定类别，以用爻（${yongLabel}）为事之主体。`); }
	chain.push(`时段：${timeDef.note}`);
	if(useRow){
		const power = useRow.power ? `（${useRow.power}）` : '';
		chain.push(`取用：${usePosition}${useRow.content && useRow.content !== '—' ? ` ${useRow.gan && useRow.gan !== '-' ? useRow.gan : ''}${useRow.content}` : ''}${power}${useRow.kong ? '，落空亡' : ''}。`);
	}
	if(relatedDong.length){
		chain.push(`动象：${relatedDong.map((d)=>`${d.type}动（${d.from}→${d.to}${d.kong ? '·落空' : ''}）`).join('、')}。`);
	}else{
		chain.push('动象：取用之位无五动三动直接牵动，事体平缓、须待外引。');
	}
	if(relatedGods.length){
		chain.push(`神煞：${relatedGods.slice(0, 6).map((g)=>g.name).join('、')}临之。`);
	}
	if(ctx.neiwai && ctx.neiwai.text){ chain.push(`内外：${ctx.neiwai.text}`); }
	return {
		askKey: askKey,
		askLabel: focus ? focus.label : '',
		usePosition: usePosition,
		useRow: useRow ? { label: useRow.label, content: useRow.content, gan: useRow.gan, power: useRow.power, kong: useRow.kong } : null,
		timeScope: timeScope,
		timeLabel: timeDef.label,
		relatedDong: relatedDong,
		relatedGods: relatedGods.slice(0, 8),
		chain: chain,
	};
}

// 方位类神煞（§9.7）：飞天八方五鬼与喜神方位，按日干取八卦之位。
// 不入四位行（无支可临），单列一组；出行趋避用。
const JINKOU_BAGUA_FANGWEI = { '巽': '东南', '艮': '东北', '乾': '西北', '坎': '正北', '坤': '西南', '离': '正南', '震': '正东', '兑': '正西' };
const JINKOU_WUGUI_FANG = { '甲': '巽', '己': '巽', '乙': '艮', '庚': '艮', '丙': '乾', '辛': '乾', '丁': '坎', '壬': '坎', '戊': '坤', '癸': '坤' };
const JINKOU_XISHEN_FANG = { '甲': '艮', '己': '艮', '乙': '乾', '庚': '乾', '丙': '坤', '辛': '坤', '丁': '离', '壬': '离', '戊': '巽', '癸': '巽' };
function buildJinKouFangWei(dayGan){
	if(!dayGan){ return []; }
	const out = [];
	const wg = JINKOU_WUGUI_FANG[dayGan];
	const xs = JINKOU_XISHEN_FANG[dayGan];
	if(wg){
		out.push({ name: '飞天五鬼', gua: wg, fang: JINKOU_BAGUA_FANGWEI[wg] || '', jx: 'xiong', text: '飞天八方五鬼所在，出行主损财损车、多口舌是非，宜避其方。' });
	}
	if(xs){
		out.push({ name: '喜神', gua: xs, fang: JINKOU_BAGUA_FANGWEI[xs] || '', jx: 'ji', text: '喜神所在之方，出行谒贵、求谋议事宜向此方，主逢喜遇助。' });
	}
	return out;
}

// 四象所属图：把静态四位所属(亲属/君臣主客/天地/官禄财/内外/身体)与当前四位实况并排，
// 供右栏 6 列表与分类用神引用——四位类象自此单一取数，勿在文案里重复硬写。
function buildJinKouSixiangShu(rows){
	return (rows || []).map((r)=>{
		const attr = JINKOU_SIXIANG_SHU[r.label] || {};
		const zhi = rowZhi(r);
		return {
			label: r.label,
			// 干支实况：人元只有干、地分只有支、将神贵神干支俱全。
			ganzhi: `${r.gan && r.gan !== '-' ? r.gan : ''}${zhi || (r.content && r.content !== '—' ? r.content : '')}`,
			shenjiang: r.shenjiang && r.shenjiang !== '-' ? r.shenjiang : '',
			elem: r.elem || '',
			power: r.power || '',
			qinshu: attr.qinshu || '—',
			junchen: attr.junchen || '—',
			tiandi: attr.tiandi || '—',
			guanlucai: attr.guanlucai || '—',
			neiwai: attr.neiwai || '—',
			shenti: attr.shenti || '—',
		};
	});
}

// 四象五行取象：四位五行各取天时/地理/人事/病源之象，并以课中「旺」之五行为主象
// (旺之五行沿用课内旺衰 calcJinKouWangElem 的结果，不另立判据)。逢空破者标注象变。
function buildJinKouSixiangWuxing(rows, wangElem){
	const list = (rows || []).map((r)=>{
		const elem = r.elem || '';
		const doc = JINKOU_SIXIANG_WUXING[elem] || {};
		const kong = !!(r.kong && `${r.kong}`.indexOf('空') >= 0);
		return {
			label: r.label,
			elem: elem,
			kong: kong,
			tianshi: doc.tianshi || '—',
			dili: doc.dili || '—',
			renshi: doc.renshi || '—',
			bingyuan: doc.bingyuan || '—',
		};
	});
	const mainElem = wangElem || '';
	const tianqiText = mainElem && JINKOU_TIANQI_TEXT[mainElem] ? JINKOU_TIANQI_TEXT[mainElem] : '';
	// 病源以受克之位为患处(与分类用神「人体疾病」同口径)，此处只据四位五行给病源象与虚实。
	const bingList = list.filter((it)=>it.elem && it.bingyuan !== '—');
	const bingText = bingList.length
		? bingList.map((it)=>`${it.label}${it.elem}主${it.bingyuan}`).join('；')
		: '';
	return {
		rows: list,
		mainElem: mainElem,
		tianqiText: tianqiText,
		bingText: bingText,
		hasKong: list.some((it)=>it.kong),
	};
}

// 格局判定（§9.5）：由四位地支/五行结构判连茹/三合全身/四位俱比/四墓(清晰可判者)。
const JINKOU_SANHE_JU = [['申', '子', '辰', '水'], ['寅', '午', '戌', '火'], ['巳', '酉', '丑', '金'], ['亥', '卯', '未', '木']];
const JINKOU_MU_ZHI = ['辰', '戌', '丑', '未'];
function buildJinKouGeju(rows){
	const zhis = rows.map((r)=>rowZhi(r)).filter(Boolean);
	const elems = rows.map((r)=>r.elem).filter(Boolean);
	const zhiSet = {};
	zhis.forEach((z)=>{ zhiSet[z] = true; });
	const out = [];
	// 四位俱比：四位五行俱同
	if(elems.length === 4 && elems.every((e)=>e === elems[0])){
		out.push({ name: `四位俱比·${elems[0]}`, kind: '俱比', jx: 'zhong', text: JINKOU_GEJU_DOC['俱比'] });
	}
	// 三合全身：四位含某三合局三支
	JINKOU_SANHE_JU.forEach((ju)=>{
		if(ju[0] && zhiSet[ju[0]] && zhiSet[ju[1]] && zhiSet[ju[2]]){
			out.push({ name: `三合全身·${ju[3]}局`, kind: '三合', jx: 'ji', text: JINKOU_GEJU_DOC['三合全身'] });
		}
	});
	// 连茹：去重地支中存在 3 支于地支环上前后相连
	const idxSet = {};
	zhis.forEach((z)=>{ const i = LRConst.ZiList.indexOf(z); if(i >= 0){ idxSet[i] = true; } });
	let lianru = false;
	for(let i = 0; i < 12; i++){
		if(idxSet[i] && idxSet[(i + 1) % 12] && idxSet[(i + 2) % 12]){ lianru = true; break; }
	}
	if(lianru){ out.push({ name: '连茹', kind: '连茹', jx: 'zhong', text: JINKOU_GEJU_DOC['连茹'] }); }
	// 三支(贵神/将神/地分)皆临墓库 → 墓库格(四位干无支，故以三地支判)
	if(zhis.length >= 3 && zhis.every((z)=>JINKOU_MU_ZHI.indexOf(z) >= 0)){
		out.push({ name: '墓库格', kind: '墓库', jx: 'xiong', text: JINKOU_GEJU_DOC['四墓'] });
	}
	// 一类朝元：某天干见其本属之支重叠（甲见寅、乙见卯…戊见辰戌、己见未丑）。
	// 古法以「一干见三支」为格；金口诀四位仅三地支，故以「课中所见地支全为该干本属」为判据
	// （与四位俱比同一处理原则），并在断辞标明支数。
	const gans = (rows || []).map((r)=>(r.gan && r.gan !== '-' ? r.gan : (r.label === '人元' ? r.content : ''))).filter(Boolean);
	Object.keys(JINKOU_CHAOYUAN_ZHI).forEach((gan)=>{
		if(gans.indexOf(gan) < 0){ return; }
		const own = JINKOU_CHAOYUAN_ZHI[gan];
		const hits = zhis.filter((z)=>own.indexOf(z) >= 0);
		if(hits.length >= 3){
			out.push({ name: `一类朝元·${gan}`, kind: '朝元', jx: 'zhong', text: JINKOU_GEJU_DOC['一类朝元'] });
		}
	});
	return out;
}
// 十干本属之支（一类朝元用）：土干各辖二库支。
const JINKOU_CHAOYUAN_ZHI = {
	'甲': ['寅'], '乙': ['卯'], '丙': ['午'], '丁': ['巳'], '戊': ['辰', '戌'],
	'己': ['未', '丑'], '庚': ['申'], '辛': ['酉'], '壬': ['子'], '癸': ['亥'],
};
// 四丘（季支）：春丑、夏辰、秋未、冬戌 —— 主争田土坟地、丧事争讼病死，问病主凶。
const JINKOU_SIQIU_BY_SEASON = { '春': '丑', '夏': '辰', '秋': '未', '冬': '戌' };
function buildJinKouSiQiu(rows, seasonName){
	const zhi = JINKOU_SIQIU_BY_SEASON[seasonName] || '';
	if(!zhi){ return null; }
	const hitRow = (rows || []).find((r)=>rowZhi(r) === zhi);
	if(!hitRow){ return null; }
	return { name: '四丘', kind: '四丘', jx: 'xiong', zhi: zhi, position: hitRow.label, text: JINKOU_GEJU_DOC['四丘'] };
}

function rowZhi(r){
	if(!r){ return ''; }
	if(r.branch){ return r.branch; }
	return LRConst.ZiList.indexOf(r.content) >= 0 ? r.content : '';
}

function buildJinKouBranchRelations(rows, dayZi){
	const points = [];
	rows.forEach((r)=>{ const zhi = rowZhi(r); if(zhi){ points.push({ label: r.label, branch: zhi }); } });
	if(dayZi){ points.push({ label: '日辰', branch: dayZi }); }
	const out = [];
	const seen = {};
	for(let i=0; i<points.length; i++){
		for(let j=i + 1; j<points.length; j++){
			const types = branchRelTypes(points[i].branch, points[j].branch);
			types.forEach((type)=>{
				const k = `${type}_${points[i].branch}_${points[j].branch}`;
				if(seen[k]){ return; }
				seen[k] = true;
				out.push({ type: type, a: points[i].branch, b: points[j].branch, aLabel: points[i].label, bLabel: points[j].label, desc: JINKOU_DIZHI_DOC[type] || '' });
			});
		}
	}
	return out;
}

function buildJinKouTaixuan(rows){
	return rows.map((r)=>{
		const tokens = [];
		if(r.gan && r.gan !== '-' && LRConst.TaiXuanNum[r.gan] !== undefined){ tokens.push(r.gan); }
		if(r.content && LRConst.TaiXuanNum[r.content] !== undefined && tokens.indexOf(r.content) < 0){ tokens.push(r.content); }
		const nums = tokens.map((t)=>LRConst.TaiXuanNum[t]);
		const sum = nums.reduce((s, n)=>s + n, 0);
		return { label: r.label, tokens: tokens.join(''), nums: nums, num: sum };
	});
}

function buildJinKouYongStrength(yongYao, rows, wangShuaiMap){
	if(!yongYao || !yongYao.label){ return null; }
	const row = rows.find((r)=>r.label === yongYao.label);
	const elem = row ? row.elem : '';
	const state = elem && wangShuaiMap ? wangShuaiMap[elem] : '';
	let level = '中';
	if(state === '旺' || state === '相'){ level = '强'; }
	else if(state === '囚' || state === '死'){ level = '弱'; }
	const tail = level === '强' ? '所谋易成' : (level === '弱' ? '力弱难成' : '平平');
	const text = `用神${yongYao.label}（${elem || '—'}）当令${state || '—'}，主${tail}。`;
	return { label: yongYao.label, elem: elem, state: state, level: level, text: text };
}

// 应期合德六法（§9.8）：天地合德/将干近合/三奇合/三合补字/支六合/旺相逢冲。
const JINKOU_SANQI_SETS = [['甲', '戊', '庚'], ['乙', '丙', '丁'], ['壬', '癸', '辛']];
function buildJinKouYingQi(ctx){
	const yongRow = ctx.yongRow;
	if(!yongRow){ return null; }
	const yBranch = yongRow.branch || (LRConst.ZiList.indexOf(yongRow.content) >= 0 ? yongRow.content : '');
	const yGan = (yongRow.gan && yongRow.gan !== '-') ? yongRow.gan : (LRConst.GanList.indexOf(yongRow.content) >= 0 ? yongRow.content : '');
	// —— 基础口径（临日/月/时/年 + 旺衰 + 空）——
	let scope = '月内';
	if(yGan && yGan === ctx.dayGan){ scope = '旬内'; }
	else if(yBranch && yBranch === ctx.dayZi){ scope = '月内'; }
	else if(yBranch && yBranch === ctx.timeZi){ scope = '即刻'; }
	else if(yBranch && yBranch === ctx.yearZi){ scope = '年内'; }
	if(ctx.guiGan && ctx.guiZi && ctx.guiGan === ctx.dayGan && ctx.guiZi === ctx.dayZi){ scope = '即日'; }
	const state = ctx.wangShuaiMap && yongRow.elem ? ctx.wangShuaiMap[yongRow.elem] : '';
	const empty = yBranch && ctx.xunKongBranches && ctx.xunKongBranches.indexOf(yBranch) >= 0;
	let text = scope === '即日' ? '贵神与日柱相同，可即日得验。' : `用神所临，约主${scope}应。`;
	if(state === '旺' || state === '相'){ text += '用神旺相，应之宜速（取近）。'; }
	else if(state === '休' || state === '囚' || state === '死'){ text += '用神休囚，应之多迟（取远）。'; }
	if(empty){ scope = '出空后'; text += '用神逢空，须俟出空之日方应。'; }

	// —— 合德六法 ——
	const rows = ctx.rows || [];
	const fourBranches = rows.map((r)=>rowZhi(r)).filter(Boolean);
	const fourGans = rows.map((r)=>((r.gan && r.gan !== '-') ? r.gan : (LRConst.GanList.indexOf(r.content) >= 0 ? r.content : ''))).filter(Boolean);
	const jiangRow = rows.find((r)=>r.label === '将神');
	const jiangGan = jiangRow && jiangRow.gan && jiangRow.gan !== '-' ? jiangRow.gan : '';
	const fast = (state === '旺' || state === '相');
	const methods = [];
	// 1 天地合德：用爻干支之干合+支合俱全
	if(yGan && yBranch && LRConst.GanHe[yGan] && LRConst.ZiHe[yBranch]){
		methods.push({ fa: '天地合德', when: `${LRConst.GanHe[yGan]}${LRConst.ZiHe[yBranch]}`, text: `用爻(${yGan}${yBranch})干合支合俱全者，逢「${LRConst.GanHe[yGan]}${LRConst.ZiHe[yBranch]}」之期应（合处为妙）。` });
	}
	// 2 将干近合：将干五合之日
	if(jiangGan && LRConst.GanHe[jiangGan]){
		methods.push({ fa: '将干近合', when: `${LRConst.GanHe[jiangGan]}日`, text: `取将干(${jiangGan})之五合，逢「${LRConst.GanHe[jiangGan]}」日为应。` });
	}
	// 3 三奇合：课中三奇缺一字，逢所缺之干日时应
	JINKOU_SANQI_SETS.forEach((set)=>{
		const present = set.filter((g)=>fourGans.indexOf(g) >= 0);
		const missing = set.filter((g)=>fourGans.indexOf(g) < 0);
		if(present.length === 2 && missing.length === 1){
			methods.push({ fa: '三奇合', when: `${missing[0]}日`, text: `课见三奇(${set.join('')})之${present.join('')}，缺「${missing[0]}」，逢之日时为应。` });
		}
	});
	// 4 三合补字：用爻三合局缺一字，逢虚字透出为应
	if(yBranch && LRConst.ZiSangHe[yBranch]){
		const group = [yBranch].concat(LRConst.ZiSangHe[yBranch]);
		const present = group.filter((z)=>fourBranches.indexOf(z) >= 0);
		const missing = group.filter((z)=>fourBranches.indexOf(z) < 0);
		if(present.length >= 2 && missing.length === 1){
			methods.push({ fa: '三合补字', when: `${missing[0]}`, text: `三合局(${group.join('')})已见${present.join('')}，缺「${missing[0]}」，逢之透出为应。` });
		}
	}
	// 5 支六合：用爻六合之支
	if(yBranch && LRConst.ZiHe[yBranch]){
		methods.push({ fa: '支六合', when: `${LRConst.ZiHe[yBranch]}`, text: `取用爻(${yBranch})之六合，逢「${LRConst.ZiHe[yBranch]}」之期应。` });
	}
	// 6 旺相逢冲：用爻逢冲为动（旺相远应年月、休囚近应日时）
	if(yBranch && LRConst.ZiCong[yBranch]){
		methods.push({ fa: '旺相逢冲', when: `${LRConst.ZiCong[yBranch]}`, text: `用爻逢冲(${LRConst.ZiCong[yBranch]})为动，${fast ? '旺相远应年月' : '休囚近应日时'}（冲为动、合为止）。` });
	}
	return { scope: scope, text: text, methods: methods };
}

function buildJinKouShenshaDoc(shenshaRows, yongLabel){
	const rows = [];
	const relevant = [];
	(shenshaRows || []).forEach((r)=>{
		const position = `${r.label || ''}`.replace(/神煞$/, '');
		const names = `${r.value || ''}`.split(/[、，,\s]+/).filter((n)=>n && n !== '无');
		const items = names.map((name)=>{
			const doc = JINKOU_SHENSHA_DOC[name];
			return { name: name, jx: doc ? doc.jx : 'zhong', desc: doc ? doc.desc : '' };
		});
		rows.push({ label: r.label, position: position, items: items });
		items.forEach((it)=>relevant.push({ name: it.name, jx: it.jx, desc: it.desc, position: position }));
	});
	if(yongLabel){
		relevant.sort((a, b)=>(a.position === yongLabel ? 0 : 1) - (b.position === yongLabel ? 0 : 1));
	}
	return { rows: rows, relevant: relevant };
}

export function buildJinKouData(liureng, options){
	const opt = options ? options : {};
	if(!liureng || !liureng.nongli){
		return {
			ready: false,
			diFen: '子',
			timeZi: '',
			rows: [],
			shenshaRows: [],
			xunKongBranches: [],
			siDaKong: '',
		};
	}

	const dayGan = getDayGan(liureng);
	const monthZi = getMonthZi(liureng);
	// 占时（zhanShi）：默认取八字时支；AI 挂载/主页面可指定具体地支（非 'auto' 且为合法支时覆盖）。
	const autoTimeZi = getTimeZi(liureng);
	const timeZi = (opt.zhanShi && opt.zhanShi !== 'auto' && containsVal(LRConst.ZiList, opt.zhanShi)) ? opt.zhanShi : autoTimeZi;
	const diFen = normalizeDiFen(opt.diFen, timeZi);
	const renYuanGan = getStemByWuZiDun(dayGan, diFen);
	// 排盘流派(P0-1)：月将换将(中气/交节)、贵人昼夜表(实务/古法)、起贵神盘(地盘/天盘)、盘式(阳/阴占位)。
	const schoolYueJiang = opt.schoolYueJiang === 'jiaojie' ? 'jiaojie' : 'zhongqi';
	const schoolGuiTable = opt.schoolGuiTable === 'liuren' ? 'liuren' : 'shiwu';
	const schoolGuiPan = opt.schoolGuiPan === 'tian' ? 'tian' : 'di';
	const panShi = opt.panShi === 'yin' ? 'yin' : 'yang';
	// 土之十二长生：默认「水土同宫」(申)，少数派「火土同宫」(寅)；默认值即现状，零回归。
	const soilChangSheng = opt.soilChangSheng === 'yin' ? 'yin' : 'shen';
	// 月将（yueJiang）先算(天盘起贵神依赖月将)：默认按节气取；可手动覆盖。
	const autoYueJiang = getYueJiang(liureng, monthZi, schoolYueJiang);
	const yuejiang = (opt.yueJiang && opt.yueJiang !== 'auto' && containsVal(LRConst.ZiList, opt.yueJiang)) ? opt.yueJiang : autoYueJiang;
	const guiShen = getGuiShenAtDiFen(dayGan, timeZi, diFen, opt.guirengType, opt.isDiurnal, { guiTable: schoolGuiTable, guiPan: schoolGuiPan, yuejiang: yuejiang });
	const guiZi = guiShen.zi;
	const guiGan = getStemByWuZiDun(dayGan, guiZi);
	const jiang = getJiangZiAtDiFen(yuejiang, timeZi, diFen);
	const jiangZi = jiang.zi;
	const jiangGan = getStemByWuZiDun(dayGan, jiangZi);

	const xunKongBranches = parseBranches(liureng.xun ? liureng.xun['旬空'] : '');
	const siDaKong = calcSiDaKongWang(liureng.xun ? liureng.xun['旬首'] : '');

	const renElem = getElem(renYuanGan);
	const guiElem = getElem(guiZi);
	const jiangElem = getElem(jiangZi);
	const diElem = getElem(diFen);

	const renSign = getYinYangSign(renYuanGan);
	const guiSign = getYinYangSign(guiZi);
	const jiangSign = getYinYangSign(jiangZi);
	const diSign = getYinYangSign(diFen);
	const lineSigns = [{
		label: '人元',
		sign: renSign,
	}, {
		label: '贵神',
		sign: guiSign,
	}, {
		label: '将神',
		sign: jiangSign,
	}, {
		label: '地分',
		sign: diSign,
	}];
	const yongYao = resolveYongYao(lineSigns);

	const wangElem = calcJinKouWangElem([renElem, guiElem, jiangElem, diElem]);
	const wangShuaiMap = buildJinKouWangShuaiMap(wangElem);
	const getJinKouSeason = (elem)=>{
		if(elem && wangShuaiMap[elem]){
			return wangShuaiMap[elem];
		}
		return getSeason(liureng, elem);
	};

	const rows = [
		buildRow({
			label: '人元',
			gan: '-',
			content: renYuanGan,
			shenjiang: '-',
			elem: renElem,
			ganElem: renElem,
			sign: renSign,
			season: getJinKouSeason(renElem),
			branch: '',
			emptyBranches: xunKongBranches,
			siDaKong: siDaKong,
		}),
		buildRow({
			label: '贵神',
			gan: guiGan,
			content: guiZi,
			shenjiang: guiShen.name,
			elem: guiElem,
			ganElem: getElem(guiGan),
			sign: guiSign,
			season: getJinKouSeason(guiElem),
			branch: guiZi,
			emptyBranches: xunKongBranches,
			siDaKong: siDaKong,
		}),
		buildRow({
			label: '将神',
			gan: jiangGan,
			content: jiangZi,
			shenjiang: jiang.name,
			elem: jiangElem,
			ganElem: getElem(jiangGan),
			sign: jiangSign,
			season: getJinKouSeason(jiangElem),
			branch: jiangZi,
			emptyBranches: xunKongBranches,
			siDaKong: siDaKong,
		}),
		buildRow({
			label: '地分',
			gan: '-',
			content: diFen,
			shenjiang: '-',
			elem: diElem,
			ganElem: diElem,
			sign: diSign,
			season: getJinKouSeason(diElem),
			branch: diFen,
			emptyBranches: xunKongBranches,
			siDaKong: siDaKong,
		}),
	];

	const shenshaRows = calcJinKouShenShaRows(liureng, rows, {
		renYuanGan: renYuanGan,
		guiZi: guiZi,
		jiangElem: jiangElem,
	});

	// 解读层派生字段（全部确定性纯计算：生克关系/五动三动/格局/应期/神煞判语/四象取象/合占直断）
	const dayZi = getDayZi(liureng);
	const yearZi = getYearZi(liureng);
	const yongRow = yongYao && yongYao.label ? rows.find((r)=>r.label === yongYao.label) : null;
	const shenshaDoc = buildJinKouShenshaDoc(shenshaRows, yongYao ? yongYao.label : '');
	const jkRelations = buildJinKouRelations(rows);
	const jkBihe = buildJinKouBihe(rows);
	const jkBranchRelations = buildJinKouBranchRelations(rows, dayZi);
	const jkTaixuan = buildJinKouTaixuan(rows);
	const jkYongStrength = buildJinKouYongStrength(yongYao, rows, wangShuaiMap);
	const jkYingQi = buildJinKouYingQi({ yongRow: yongRow, rows: rows, dayGan: dayGan, dayZi: dayZi, timeZi: timeZi, yearZi: yearZi, guiGan: guiGan, guiZi: guiZi, wangShuaiMap: wangShuaiMap, xunKongBranches: xunKongBranches });
	const jkDong = buildJinKouDong(rows, xunKongBranches, yongYao ? yongYao.label : '');
	const jkGeju = buildJinKouGeju(rows);
	// 四丘按季支另判（需月令季节，与四位结构类格局分开算后并入同一列表）。
	const jkSiQiu = buildJinKouSiQiu(rows, getSeasonByMonthZi(monthZi));
	if(jkSiQiu){ jkGeju.push(jkSiQiu); }
	const jkFourBranches = rows.map((r)=>rowZhi(r)).filter(Boolean);
	// 四位带干之柱(贵神=神干+本家支、将神=将干+将神支)——真太岁比对整柱用。
	const jkFourGanZi = [`${guiGan}${guiZi}`, `${jiangGan}${jiangZi}`].filter((s)=>s && s.length === 2);
	const jkNianYueRi = buildJinKouNianYueRi(yearZi, monthZi, getMonthIndexByZi(monthZi), dayZi, jkFourBranches, {
		yearGanZi: getYearGanZi(liureng),
		dayGanZi: getDayGanZi(liureng),
		fourGanZi: jkFourGanZi,
		jiangZi: jiangZi,
	});
	const jkJishi = buildJinKouJishi(monthZi, dayGan, timeZi);
	const jkSixiangShu = buildJinKouSixiangShu(rows);
	const jkSixiangWuxing = buildJinKouSixiangWuxing(rows, wangElem);
	const jkFangWei = buildJinKouFangWei(dayGan);
	// 专题起式（定局法）：二遁人元恒算（细象常用）；次客/移星换将为参考式；
	// 测年月日与七专题按 opt.topicKey / opt.benMing 产出，未选则为 null（零额外开销）。
	const jkErDun = buildJinKouErDun(renYuanGan, diFen);
	const jkCiKe = buildJinKouCiKe({
		yuejiang: yuejiang, timeZi: timeZi, diFen: diFen, dayGan: dayGan, dayZi: dayZi,
		guiName: guiShen.name,
		yongZhi: yongRow ? rowZhi(yongRow) : '',
		yongGan: yongRow && yongRow.gan && yongRow.gan !== '-' ? yongRow.gan : (yongYao && yongYao.label === '人元' ? renYuanGan : ''),
	});
	const jkYiXing = buildJinKouYiXing(dayGan);
	const topicCtx = {
		yuejiang: yuejiang, timeZi: timeZi, diFen: diFen, yearZi: yearZi,
		benMing: opt.benMing || '', renYuanGan: renYuanGan, dayGan: dayGan,
	};
	const jkTopic = opt.topicKey ? buildJinKouTopic(opt.topicKey, topicCtx) : null;
	const jkTopicJue = opt.topicKey ? buildJinKouTopicJue(opt.topicKey, {
		diFen: diFen, jiangZi: jiangZi, guiName: guiShen.name,
		erDunGan: jkErDun ? jkErDun.gan : '', rows: rows,
	}) : null;
	// 金口诀行年（旬法）：与既有干支流年并存，不替换 runyear。
	const jkXingNian = (opt.birthGanZi && opt.age) ? buildJinKouXingNian(opt.birthGanZi, opt.gender, opt.age) : null;
	const jkShiJian = opt.shiJianKind ? buildJinKouShiJian(opt.shiJianKind, {
		yuejiang: yuejiang, yearZi: yearZi, monthZi: monthZi, dayZi: dayZi, benMing: opt.benMing || '',
	}) : null;
	// 阴盘三层仅在盘式=阴盘时产出（阳盘恒 null → 断法主线与既有输出零回归）。
	const jkYinPan = panShi === 'yin' ? buildJinKouYinPan(rows, dayGan, liureng.season, soilChangSheng) : null;
	const jkNeiWai = buildJinKouNeiWai(rows, yongYao ? yongYao.label : '');
	const jkHezhan = buildJinKouHezhan({
		rows: rows,
		yongLabel: yongYao ? yongYao.label : '',
		askKey: opt.askKey || '',
		timeScope: opt.timeScope || 'default',
		dong: jkDong,
		relevantShensha: shenshaDoc.relevant,
		neiwai: jkNeiWai,
	});

	return {
		ready: true,
		diFen: diFen,
		timeZi: timeZi,
		monthZi: monthZi,
		dayGan: dayGan,
		renYuanGan: renYuanGan,
		guiName: guiShen.name,
		guiZi: guiZi,
		guiGan: guiGan,
		guiStartZi: guiShen.startZi,
		isDay: guiShen.isDay,
		dayBasis: guiShen.dayBasis || 'branch',
		dayBasisText: guiShen.dayBasisText || '时支粗判·卯至申为昼',
		jiangZi: jiangZi,
		jiangName: jiang.name,
		jiangGan: jiangGan,
		yuejiang: jiang.yuejiang,
		xunKongBranches: xunKongBranches,
		siDaKong: siDaKong,
		wangElem: wangElem,
		wangShuai: wangShuaiMap,
		lineSigns: lineSigns,
		yongYao: yongYao,
		rows: rows,
		shenshaRows: shenshaRows,
		dayZi: dayZi,
		yearZi: yearZi,
		yongStrength: jkYongStrength,
		relations: jkRelations,
		bihe: jkBihe,
		xiangyi: buildJinKouXiangyi(guiShen.name, jiang.name),
		nianYueRi: jkNianYueRi,
		jishi: jkJishi,
		branchRelations: jkBranchRelations,
		taixuan: jkTaixuan,
		yingQi: jkYingQi,
		shenshaDocRows: shenshaDoc.rows,
		relevantShensha: shenshaDoc.relevant,
		categoryRules: JINKOU_CATEGORY_RULES,
		schools: { yueJiang: schoolYueJiang, guiTable: schoolGuiTable, guiPan: schoolGuiPan, panShi: panShi, soilChangSheng: soilChangSheng },
		// 三盘环按当前流派现算（G21）：默认流派下与后端环一致，偏离时不再退化成「待续」占位。
		plates: buildJinKouPlates(yuejiang, timeZi, guiShen.circle),
		// 十二长生落支表（土随流派，其余四行恒定）：右栏长生卡与快照据此，勿再各自查表。
		phaseTable: jinKouPhaseTable(opt.wuxing || '土', soilChangSheng),
		dong: jkDong,
		geju: jkGeju,
		sixiangShu: jkSixiangShu,
		sixiangWuxing: jkSixiangWuxing,
		fangWeiShensha: jkFangWei,
		neiwai: jkNeiWai,
		hezhan: jkHezhan,
		yinPan: jkYinPan,
		erDun: jkErDun,
		cike: jkCiKe,
		yiXing: jkYiXing,
		topic: jkTopic,
		topicJue: jkTopicJue,
		shiJian: jkShiJian,
		xingNian: jkXingNian,
		topInfo: {
			diFen: diFen,
			xunKong: xunKongBranches.length ? xunKongBranches.join('') : '无',
			siDaKong: siDaKong ? siDaKong : '无',
			// [X1·P2-13] 月将/占时补齐:此前本地(非默认流派)路径中栏顶行画「—」、课情行显「无」。
			yuejiang: jiangZi ? `${jiangZi}${jiang && jiang.name ? `·${jiang.name}` : ''}` : '',
			zhanshi: timeZi || '',
		},
	};
}

function safeText(value){
	return value === undefined || value === null ? '' : `${value}`;
}

function parseFieldsDateTime(fields){
	if(!fields || !fields.date || !fields.time){
		return null;
	}
	const dateStr = fields.date.value.format('YYYY-MM-DD');
	const timeStr = fields.time.value.format('HH:mm:ss');
	// BC 安全解析:'-7040-07-19' 裸 split('-') 会撕成 [NaN,7040,7,19](年 NaN 静默传播)
	const _dp = parseDateParts(dateStr);
	const d = _dp ? [_dp.year, _dp.month, _dp.day] : [];
	const t = timeStr.split(':').map((item)=>parseInt(item, 10));
	if(d.length < 3 || t.length < 2){
		return null;
	}
	return {
		year: d[0],
		month: d[1],
		day: d[2],
		hour: t[0],
		minute: t[1],
		second: t[2] || 0,
		date: dateStr,
		time: timeStr,
	};
}

function parseDateTimeText(text){
	const raw = safeText(text).trim();
	const match = raw.match(/^(-?\d{1,6})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?/);
	if(!match){
		return null;
	}
	return {
		year: parseInt(match[1], 10),
		month: parseInt(match[2], 10),
		day: parseInt(match[3], 10),
		hour: parseInt(match[4], 10),
		minute: parseInt(match[5], 10),
		second: parseInt(match[6] || '0', 10),
		date: `${match[1].padStart(4, '0')}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}`,
		time: `${match[4].padStart(2, '0')}:${match[5].padStart(2, '0')}:${(match[6] || '0').padStart(2, '0')}`,
	};
}

function resolveCalculationDateTime(fields, nongli, options){
	if(options && options.timeBasis === 'trueSolar'){
		return parseDateTimeText(nongli && nongli.birth) || parseFieldsDateTime(fields);
	}
	return parseFieldsDateTime(fields);
}

function cleanDisplay(value, def = '—'){
	const text = safeText(value).trim();
	if(!text || text === 'None'){
		return def;
	}
	return text;
}

function normalizeBackendRow(row, fallbackRow){
	const elem = cleanDisplay(row && row.element, '');
	const content = cleanDisplay(row && row.content, '—');
	// 阴阳列：后端有给则用后端，否则由四位定位干支(人元=天干、贵神/将神/地分=地支)现算，
	// 保证中间盘四位旁 +/- 列四行齐全(零回归：后端给值时不动)。
	const sign = cleanDisplay(row && row.sign, '') || getYinYangSign(content) || (fallbackRow ? cleanDisplay(fallbackRow.sign, '') : '');
	const season = cleanDisplay(row && row.season, '');
	const label = cleanDisplay(row && row.label, fallbackRow ? fallbackRow.label : '');
	return {
		...(fallbackRow || {}),
		label: label,
		gan: cleanDisplay(row && row.gan, '-'),
		content: content,
		shenjiang: cleanDisplay(row && row.shenjiang, '-'),
		// 力量列去掉阴阳符号(+/-)，阴阳改由中间盘四位旁的独立 +/- 列承担，避免「金-相」误读为减号
		power: cleanDisplay(row && row.power, elem || sign || season ? `${elem}${sign}${season}` : '—').replace(/[+\-−]/g, ''),
		// 先认后端本行的空亡，再回落本地 fallback —— 原先只认 fallback，
		// 无 liureng（只有后端盘）时四位空亡列恒「—」，后端算了也白算。
		kong: cleanDisplay(row && row.kong, '') || (fallbackRow && fallbackRow.kong ? fallbackRow.kong : '—'),
		elem: elem,
		sign: sign,
		season: season,
		nayin: cleanDisplay(row && row.nayin, ''),
		ganZhi: cleanDisplay(row && row.ganZhi, ''),
		branch: cleanDisplay(row && row.branch, ''),
		isYong: !!(row && row.isYong),
		contentColor: JinKouElementColor[elem] ? JinKouElementColor[elem] : '#262626',
		ganColor: JinKouElementColor[elem] ? JinKouElementColor[elem] : (fallbackRow ? fallbackRow.ganColor : '#262626'),
		powerColor: JinKouElementColor[elem] ? JinKouElementColor[elem] : '#262626',
	};
}

export function normalizeKinjinkouData(backendPan, fallbackData){
	if(!backendPan || !backendPan.rows){
		return fallbackData;
	}
	const fallback = fallbackData || {};
	const fallbackRows = fallback.rows || [];
	const rows = backendPan.rows.map((row, idx)=>normalizeBackendRow(row, fallbackRows[idx]));
	const yongRow = rows.find((row)=>row.isYong);
	// 解读层随「显示行(后端)」重算，避免与本地 fallback 行（月将/将神可能不同）不一致
	const reYongLabel = (yongRow && yongRow.label) || (backendPan.yongYao && backendPan.yongYao.label) || (fallback.yongYao && fallback.yongYao.label) || '';
	const reYongRow = reYongLabel ? rows.find((row)=>row.label === reYongLabel) : null;
	const reGuiRow = rows.find((row)=>row.label === '贵神');
	const reJiangRow = rows.find((row)=>row.label === '将神');
	const reJiangZhi = reJiangRow ? rowZhi(reJiangRow) : '';
	return {
		...fallback,
		ready: true,
		source: 'kinjinkou',
		backend: backendPan,
		diFen: cleanDisplay(backendPan.difen, fallback.diFen || '子'),
		timeZi: cleanDisplay(backendPan.zhanshi, fallback.timeZi || ''),
		yuejiang: cleanDisplay(backendPan.yuejiang, fallback.yuejiang || ''),
		xunKongBranches: fallback.xunKongBranches || [],
		siDaKong: cleanDisplay(backendPan.siDaKong, fallback.siDaKong || '无'),
		yongYao: {
			...(fallback.yongYao || {}),
			...(backendPan.yongYao || {}),
			label: yongRow ? yongRow.label : (backendPan.yongYao ? backendPan.yongYao.label : ''),
			sign: yongRow ? yongRow.sign : (backendPan.yongYao ? backendPan.yongYao.sign : ''),
		},
		rows: rows,
		relations: buildJinKouRelations(rows),
		bihe: buildJinKouBihe(rows),
		xiangyi: buildJinKouXiangyi(reGuiRow ? reGuiRow.shenjiang : '', JinKouYueJiangName[reJiangZhi] || ''),
		branchRelations: buildJinKouBranchRelations(rows, fallback.dayZi),
		dong: buildJinKouDong(rows, fallback.xunKongBranches, reYongLabel),
		geju: buildJinKouGeju(rows),
		taixuan: buildJinKouTaixuan(rows),
		yongStrength: reYongRow ? buildJinKouYongStrength({ label: reYongRow.label }, rows, fallback.wangShuai) : fallback.yongStrength,
		yingQi: buildJinKouYingQi({ yongRow: reYongRow, rows: rows, dayGan: fallback.dayGan, dayZi: fallback.dayZi, timeZi: fallback.timeZi, yearZi: fallback.yearZi, guiGan: reGuiRow ? reGuiRow.gan : fallback.guiGan, guiZi: reGuiRow ? rowZhi(reGuiRow) : fallback.guiZi, wangShuaiMap: fallback.wangShuai, xunKongBranches: fallback.xunKongBranches }),
		plates: backendPan.plates || [],
		sections: backendPan.sections || [],
		shenshaRows: fallback.shenshaRows || [],
		topInfo: {
			...(fallback.topInfo || {}),
			diFen: cleanDisplay(backendPan.difen, fallback.topInfo ? fallback.topInfo.diFen : '子'),
			xunKong: cleanDisplay(backendPan.xunKong, fallback.topInfo ? fallback.topInfo.xunKong : '无'),
			siDaKong: cleanDisplay(backendPan.siDaKong, fallback.topInfo ? fallback.topInfo.siDaKong : '无'),
			yuejiang: cleanDisplay(backendPan.yuejiang, ''),
			zhanshi: cleanDisplay(backendPan.zhanshi, ''),
		},
	};
}

