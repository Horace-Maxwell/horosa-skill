// Headless vendor: 星阙 的网络 import（request/constants/kentang/chartFetch/dayBoundary）已剥离；
// buildJinKouData 在已取回的 liureng 数据上纯计算，fetchJinKouPan（网络）在 headless 路径不调用。
import * as LRConst from '../liureng/LRConst.js';
import {
	JINKOU_SHENSHA_DOC,
	JINKOU_RELATION_DOC,
	JINKOU_DIZHI_DOC,
	JINKOU_CATEGORY_RULES,
} from './JinKouDoc.js';

export const JinKouElementColor = {
	'木': '#2f9f68',
	'火': '#d64a35',
	'土': '#b7842f',
	'金': '#d6a64f',
	'水': '#4da3ff',
};

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
const GuiReverseStartZi = ['巳', '午', '未', '申', '酉'];
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

function resolveIsDay(timeZi, isDiurnal){
	if(isDiurnal === true){
		return true;
	}
	if(isDiurnal === false){
		return false;
	}
	return containsVal(DayTimeZi, timeZi);
}

function getGuiShenAtDiFen(dayGan, timeZi, diFen, guirengType, isDiurnal){
	const idx = guirengType === undefined || guirengType === null ? 0 : parseInt(guirengType + '', 10);
	const isDay = resolveIsDay(timeZi, isDiurnal);
	let startZi = '';
	let reverse = false;
	if(idx === 0 && JinKouGuiRuleLiuReng[dayGan]){
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
		};
	}
	const startIdx = LRConst.ZiList.indexOf(startZi);
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
	};
}

function getYueJiang(liureng, monthZi){
	const jieqi = resolveJieqiForYueJiang(liureng);
	if(jieqi && JinKouYueJiangByJieQi[jieqi]){
		return JinKouYueJiangByJieQi[jieqi];
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
	let txt = elem ? elem : '—';
	if(sign){
		txt += sign;
	}
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
	return out;
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

function buildJinKouYingQi(ctx){
	const yongRow = ctx.yongRow;
	if(!yongRow){ return null; }
	const yBranch = yongRow.branch || (LRConst.ZiList.indexOf(yongRow.content) >= 0 ? yongRow.content : '');
	const yGan = (yongRow.gan && yongRow.gan !== '-') ? yongRow.gan : (LRConst.GanList.indexOf(yongRow.content) >= 0 ? yongRow.content : '');
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
	return { scope: scope, text: text };
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
	const guiShen = getGuiShenAtDiFen(dayGan, timeZi, diFen, opt.guirengType, opt.isDiurnal);
	const guiZi = guiShen.zi;
	const guiGan = getStemByWuZiDun(dayGan, guiZi);
	// 月将（yueJiang）：默认按节气取；AI 挂载/主页面可指定具体地支（非 'auto' 且为合法支时覆盖）。
	const autoYueJiang = getYueJiang(liureng, monthZi);
	const yuejiang = (opt.yueJiang && opt.yueJiang !== 'auto' && containsVal(LRConst.ZiList, opt.yueJiang)) ? opt.yueJiang : autoYueJiang;
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

	// 解读层派生字段（确定性纯计算；五动/三动规则待底本，dong 预留空）
	const dayZi = getDayZi(liureng);
	const yearZi = getYearZi(liureng);
	const yongRow = yongYao && yongYao.label ? rows.find((r)=>r.label === yongYao.label) : null;
	const shenshaDoc = buildJinKouShenshaDoc(shenshaRows, yongYao ? yongYao.label : '');
	const jkRelations = buildJinKouRelations(rows);
	const jkBranchRelations = buildJinKouBranchRelations(rows, dayZi);
	const jkTaixuan = buildJinKouTaixuan(rows);
	const jkYongStrength = buildJinKouYongStrength(yongYao, rows, wangShuaiMap);
	const jkYingQi = buildJinKouYingQi({ yongRow: yongRow, dayGan: dayGan, dayZi: dayZi, timeZi: timeZi, yearZi: yearZi, guiGan: guiGan, guiZi: guiZi, wangShuaiMap: wangShuaiMap, xunKongBranches: xunKongBranches });

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
		branchRelations: jkBranchRelations,
		taixuan: jkTaixuan,
		yingQi: jkYingQi,
		shenshaDocRows: shenshaDoc.rows,
		relevantShensha: shenshaDoc.relevant,
		categoryRules: JINKOU_CATEGORY_RULES,
		dong: { san: [], wu: [] },
		topInfo: {
			diFen: diFen,
			xunKong: xunKongBranches.length ? xunKongBranches.join('') : '无',
			siDaKong: siDaKong ? siDaKong : '无',
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
	const d = dateStr.split('-').map((item)=>parseInt(item, 10));
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
	const sign = cleanDisplay(row && row.sign, '');
	const season = cleanDisplay(row && row.season, '');
	const label = cleanDisplay(row && row.label, fallbackRow ? fallbackRow.label : '');
	return {
		...(fallbackRow || {}),
		label: label,
		gan: cleanDisplay(row && row.gan, '-'),
		content: cleanDisplay(row && row.content, '—'),
		shenjiang: cleanDisplay(row && row.shenjiang, '-'),
		power: cleanDisplay(row && row.power, elem || sign || season ? `${elem}${sign}${season}` : '—'),
		kong: fallbackRow && fallbackRow.kong ? fallbackRow.kong : '—',
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
		branchRelations: buildJinKouBranchRelations(rows, fallback.dayZi),
		taixuan: buildJinKouTaixuan(rows),
		yongStrength: reYongRow ? buildJinKouYongStrength({ label: reYongRow.label }, rows, fallback.wangShuai) : fallback.yongStrength,
		yingQi: buildJinKouYingQi({ yongRow: reYongRow, dayGan: fallback.dayGan, dayZi: fallback.dayZi, timeZi: fallback.timeZi, yearZi: fallback.yearZi, guiGan: reGuiRow ? reGuiRow.gan : fallback.guiGan, guiZi: reGuiRow ? rowZhi(reGuiRow) : fallback.guiZi, wangShuaiMap: fallback.wangShuai, xunKongBranches: fallback.xunKongBranches }),
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

export async function fetchJinKouPan(fields, nongli, options){
	const opt = options || {};
	const dt = resolveCalculationDateTime(fields, nongli, opt);
	if(!dt){
		return null;
	}
	const payload = {
		...dt,
		zone: fields && fields.date && fields.date.value ? fields.date.value.zone : '',
		difen: opt.diFen || '子',
		yuejiang: opt.yueJiang && opt.yueJiang !== 'auto' ? opt.yueJiang : '',
		zhanshi: opt.zhanShi && opt.zhanShi !== 'auto' ? opt.zhanShi : '',
		timeBasis: opt.timeBasis || 'direct',
		realSunTime: nongli ? (nongli.birth || '') : '',
		jiedelta: nongli ? (nongli.jiedelta || '') : '',
		// v2.2.1: 两个全局开关从事盘(起课)fields 透传给后端 /jinkou/pan,后端已读取应用。
		after23NewDay: (fields && fields.after23NewDay && fields.after23NewDay.value !== undefined) ? fields.after23NewDay.value : defaultAfter23NewDay(),
		lateZiHourUseNextDay: (fields && fields.lateZiHourUseNextDay && fields.lateZiHourUseNextDay.value !== undefined) ? fields.lateZiHourUseNextDay.value : defaultLateZiHourUseNextDay(),
	};
	let rsp = null;
	try{
		const rawResponse = await fetchChartWithRetry(buildKentangEndpoint('jinkou', 'pan'), {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json; charset=UTF-8',
			},
			body: JSON.stringify(payload),
		});
		const rawText = await rawResponse.text();
		rsp = rawText ? JSON.parse(rawText) : null;
		if(!rsp || (rsp.ResultCode !== undefined && rsp.ResultCode !== 0)){
			throw new Error(rsp && rsp[ResultKey] ? `${rsp[ResultKey]}` : 'jinkou.local.fetch.failed');
		}
	}catch(e){
		rsp = await request(`${ServerRoot}/jinkou/pan`, {
			body: JSON.stringify(payload),
			silent: true,
			timeoutMs: 45000,
			retry: { retries: 2 },
		});
	}
	return rsp && rsp[ResultKey] ? rsp[ResultKey] : rsp;
}
