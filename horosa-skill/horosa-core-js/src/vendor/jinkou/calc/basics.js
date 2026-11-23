// 取干支 / 节气 / 地分与四位(贵神、将神、人元)的底层工具,空亡与季节
// 从 JinKouCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import * as LRConst from '../../liureng/LRConst.js';
import { WuZiDunStart, DayTimeZi, JinKouGuiRuleLiuRenClassic, GuiReverseStartZi, JinKouGuiRuleLiuReng, JinKouGuiShenSeq, JinKouGuiShenZi, JinKouYueJiangByJieQi_JiaoJie, JinKouYueJiangByJieQi, JinKouYueJiangByMonthBranch, JinKouYueJiangName } from './tables.js';

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

export function containsVal(list, val){
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

export function getDayGan(liureng){
	if(!liureng || !liureng.nongli){
		return '';
	}
	return extractFromList(liureng.nongli.dayGanZi, LRConst.GanList);
}

export function getDayZi(liureng){
	if(!liureng || !liureng.nongli){
		return '';
	}
	return extractFromList(liureng.nongli.dayGanZi, LRConst.ZiList);
}

// 干支全串(真太岁/日建等需比对整柱，非单取干或支)。取不到时返回空串，下游判定自动跳过。
export function getDayGanZi(liureng){
	const gan = getDayGan(liureng);
	const zi = getDayZi(liureng);
	return (gan && zi) ? `${gan}${zi}` : '';
}

export function getYearGanZi(liureng){
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

export function getMonthZi(liureng){
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

export function getYearZi(liureng){
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

export function getTimeZi(liureng){
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

export function normalizeDiFen(diFen, fallback){
	const zi = extractFromList(diFen, LRConst.ZiList);
	if(zi){
		return zi;
	}
	if(containsVal(LRConst.ZiList, fallback)){
		return fallback;
	}
	return LRConst.ZiList[0];
}

export function getStemByWuZiDun(dayGan, zi){
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

export function getGuiShenAtDiFen(dayGan, timeZi, diFen, guirengType, isDiurnal, schoolOpts){
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
export function buildJinKouPlates(yuejiang, timeZi, guiCircle){
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

export function getYueJiang(liureng, monthZi, school){
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

export function getJiangZiAtDiFen(yuejiang, timeZi, diFen){
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

export function parseBranches(text){
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

export function calcSiDaKongWang(xunShou){
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

export function getElem(val){
	return LRConst.GanZiWuXing[val] ? LRConst.GanZiWuXing[val] : '';
}

export function shiftZi(zi, delta){
	const idx = LRConst.ZiList.indexOf(zi);
	if(idx < 0){
		return '';
	}
	const i = (idx + delta + 1200) % 12;
	return LRConst.ZiList[i];
}

export function getMonthIndexByZi(monthZi){
	const idx = LRConst.ZiList.indexOf(monthZi);
	if(idx < 0){
		return 0;
	}
	return ((idx - 2 + 12) % 12) + 1;
}

export function getSeasonByMonthZi(monthZi){
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

export function getYinYangSign(val){
	if(LRConst.YangGan.indexOf(val) >= 0 || LRConst.YangZi.indexOf(val) >= 0){
		return '+';
	}
	if(LRConst.YingGan.indexOf(val) >= 0 || LRConst.YingZi.indexOf(val) >= 0){
		return '-';
	}
	return '';
}

export function rowZhi(r){
	if(!r){ return ''; }
	if(r.branch){ return r.branch; }
	return LRConst.ZiList.indexOf(r.content) >= 0 ? r.content : '';
}
