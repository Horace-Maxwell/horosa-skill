// 六壬毕法 reference-context 引擎（星阙 v2.5.x 六壬 Phase 4，verbatim 抽取自 LiuRengMain.js）。
// buildLiuRengReferenceContext(liureng, chartObj, guirengType, runyear, castOverride) → ~75 字段 context，
// 喂 LRBiFaDoc.matchBiFa 出「毕法（已命中）」。纯函数闭包(20 fns + 5 consts)，零 React/this。
import * as LRConst from './LRConst.js';
import { resolveLiuRengTwelvePanStyle } from './LRPanStyle.js';
import ChuangChart from './ChuangChart.js';

// AstroConst 仅用到日月 id（flatlib：'Sun'/'Moon'），用极简 shim 避开 1128 行 AstroConst。
const AstroConst = { SUN: 'Sun', MOON: 'Moon' };

const JiaZiList = (()=>{
	const list = [];
	for(let i=0; i<60; i++){
		list.push(`${LRConst.GanList[i % 10]}${LRConst.ZiList[i % 12]}`);
	}
	return list;
})();

const ERFAN_SU_TO_BRANCH = {
	'女': '子',
	'虚': '子',
	'危': '子',
	'柳': '午',
	'星': '午',
	'张': '午',
	'氐': '卯',
	'房': '卯',
	'心': '卯',
	'胃': '酉',
	'昴': '酉',
	'毕': '酉',
};

const GU_CHEN_GUA_SU_BY_SEASON = {
	spring: { guchen: '巳', guasu: '丑' },
	summer: { guchen: '申', guasu: '辰' },
	autumn: { guchen: '亥', guasu: '未' },
	winter: { guchen: '寅', guasu: '戌' },
};

const SEASON_BRANCH_GROUP = {
	spring: ['寅', '卯', '辰'],
	summer: ['巳', '午', '未'],
	autumn: ['申', '酉', '戌'],
	winter: ['亥', '子', '丑'],
};

const FOUR_SEASON_BRANCHES = ['辰', '戌', '丑', '未'];

function extractSingleGan(raw){
	const txt = `${raw || ''}`;
	for(let i=0; i<txt.length; i++){
		const ch = txt.substr(i, 1);
		if(LRConst.GanList.indexOf(ch) >= 0){
			return ch;
		}
	}
	return '';
}


function extractSingleBranch(raw){
	const txt = `${raw || ''}`;
	for(let i=txt.length - 1; i>=0; i--){
		const ch = txt.substr(i, 1);
		if(LRConst.ZiList.indexOf(ch) >= 0){
			return ch;
		}
	}
	return '';
}


function extractBranches(raw){
	if(raw === undefined || raw === null){
		return [];
	}
	if(raw instanceof Array){
		let arr = [];
		raw.forEach((item)=>{
			arr = arr.concat(extractBranches(item));
		});
		return uniqueStrings(arr);
	}
	const txt = `${raw}`;
	const arr = [];
	for(let i=0; i<txt.length; i++){
		const ch = txt.substr(i, 1);
		if(LRConst.ZiList.indexOf(ch) >= 0){
			arr.push(ch);
		}
	}
	return uniqueStrings(arr);
}


function extractGanZi(text){
	const raw = `${text || ''}`.trim();
	if(raw.length < 2){
		return '';
	}
	if(LRConst.GanList.indexOf(raw.substr(0, 1)) >= 0 && LRConst.ZiList.indexOf(raw.substr(1, 1)) >= 0){
		return raw.substr(0, 2);
	}
	for(let i=0; i<raw.length - 1; i++){
		const gan = raw.substr(i, 1);
		const zi = raw.substr(i + 1, 1);
		if(LRConst.GanList.indexOf(gan) >= 0 && LRConst.ZiList.indexOf(zi) >= 0){
			return gan + zi;
		}
	}
	return '';
}


function extractSuName(raw){
	const txt = `${raw || ''}`;
	for(let i=0; i<txt.length; i++){
		const ch = txt.substr(i, 1);
		if(ERFAN_SU_TO_BRANCH[ch]){
			return ch;
		}
	}
	return '';
}


function getPrevJiaZi(ganzi){
	const idx = JiaZiList.indexOf(extractGanZi(ganzi));
	if(idx < 0){
		return '';
	}
	return JiaZiList[(idx + 59) % 60];
}


function uniqueStrings(values){
	const out = [];
	const seen = {};
	(values || []).forEach((item)=>{
		const txt = `${item || ''}`.trim();
		if(!txt || seen[txt]){
			return;
		}
		seen[txt] = true;
		out.push(txt);
	});
	return out;
}


function safeRestrain(a, b){
	if(!a || !b){
		return false;
	}
	const list = LRConst.GanZiRestrain[a];
	return !!(list && list.indexOf(b) >= 0);
}


function normalizeTianJiangName(name){
	const txt = `${name || ''}`.replace(/\s+/g, '');
	if(!txt){
		return '';
	}
	if(txt === '腾蛇'){
		return '螣蛇';
	}
	return txt;
}


function resolveSeasonByMonthBranch(branch){
	if(SEASON_BRANCH_GROUP.spring.indexOf(branch) >= 0){
		return 'spring';
	}
	if(SEASON_BRANCH_GROUP.summer.indexOf(branch) >= 0){
		return 'summer';
	}
	if(SEASON_BRANCH_GROUP.autumn.indexOf(branch) >= 0){
		return 'autumn';
	}
	if(SEASON_BRANCH_GROUP.winter.indexOf(branch) >= 0){
		return 'winter';
	}
	return '';
}


function buildXunGanMap(dayGan, dayZhi){
	const map = {};
	if(!dayGan || !dayZhi){
		return map;
	}
	const xun = LRConst.getXun(dayGan, dayZhi);
	for(let i=0; i<xun.length && i<LRConst.GanList.length; i++){
		map[xun[i]] = LRConst.GanList[i];
	}
	return map;
}


function getPlanetObject(chartObj, planetId){
	if(!chartObj || !chartObj.objects || !planetId){
		return null;
	}
	for(let i=0; i<chartObj.objects.length; i++){
		const obj = chartObj.objects[i];
		if(obj && obj.id === planetId){
			return obj;
		}
	}
	return null;
}


function getPlanetBranch(chartObj, planetId){
	const obj = getPlanetObject(chartObj, planetId);
	if(!obj){
		return '';
	}
	return LRConst.getSignZi(obj.sign) || '';
}


function getPlanetSuName(chartObj, planetId){
	const obj = getPlanetObject(chartObj, planetId);
	if(!obj){
		return '';
	}
	return extractSuName(obj.su28 || '');
}


function getPlanetErfanBranch(chartObj, planetId){
	const suName = getPlanetSuName(chartObj, planetId);
	if(suName && ERFAN_SU_TO_BRANCH[suName]){
		return ERFAN_SU_TO_BRANCH[suName];
	}
	return '';
}


function getChartYue(chartObj){
	if(!chartObj || !chartObj.objects){
		return '';
	}
	for(let i=0; i<chartObj.objects.length; i++){
		const obj = chartObj.objects[i];
		if(obj.id === AstroConst.SUN){
			return LRConst.getSignZi(obj.sign);
		}
	}
	return '';
}

// 起课法：正时正将(第一客) + 十二客②–⑫ + 加时四法(太岁/月建/行年/本命加时) + 次客·一/二/三筹 + 四柱对齐 + 选时 + 演数。
// 古法：每法＝一对「天盘起支 X 加于 地盘临位 Y」；天干用寄宫(GanJiZi)；对齐/本命/行年取对应地支。
// 次客(cikeN)：自月将本位起，阳支「后三前五」/阴支「前三后五」取「第 N 筹」天盘地支，再以该支「加时」(放占时)重排上下盘——与其它加时法同理(见 liurengChouBranch + computeQiXY)。
// 起课法 25 法（AI 挂载齿轮 schema 复用此常量映射，杜绝手写错值/漂移——见 techniqueMountSettings.LIURENG_FIELDS）。

function buildLiuRengLayout(chartObj, guirengType, castOverride){
	if(!chartObj || !chartObj.nongli || !chartObj.nongli.time){
		return null;
	}
	// 起课法/换将：月将(yue=天盘起支) 与 临位(timezi=地盘临位) 可被 castOverride 覆盖；缺省=正时正将(现状)。
	const yue = (castOverride && castOverride.yue) || getChartYue(chartObj);
	if(!yue){
		return null;
	}
	const downZi = LRConst.ZiList.slice(0);
	const upZi = LRConst.ZiList.slice(0);
	const yueIndexs = [];
	const timezi = (castOverride && castOverride.timeZhi) || chartObj.nongli.time.substr(1);
	const yueIdx = LRConst.ZiList.indexOf(yue);
	const tmIdx = LRConst.ZiList.indexOf(timezi);
	if(yueIdx < 0 || tmIdx < 0){
		return null;
	}
	const delta = yueIdx - tmIdx;
	for(let i=0; i<12; i++){
		const idx = (i + delta + 12) % 12;
		yueIndexs[i] = idx;
		upZi[i] = LRConst.ZiList[idx];
	}

	const houseTianJiang = LRConst.TianJiang.slice(0);
	const guizi = LRConst.getGuiZi(chartObj, guirengType, castOverride ? castOverride.isDiurnal : undefined);
	let houseidx = 0;
	for(let i=0; i<12; i++){
		const zi = LRConst.ZiList[yueIndexs[i]];
		if(zi === guizi){
			houseidx = i;
			break;
		}
	}
	const housezi = LRConst.ZiList[houseidx];
	const guirenForward = LRConst.SummerZiList.indexOf(housezi) < 0;
	if(!guirenForward){
		for(let i=0; i<12; i++){
			const idx = (houseidx - i + 12) % 12;
			houseTianJiang[i] = LRConst.TianJiang[idx];
		}
	}else{
		for(let i=0; i<12; i++){
			const idx = (i - houseidx + 12) % 12;
			houseTianJiang[i] = LRConst.TianJiang[idx];
		}
	}

	return {
		yue,
		timezi,
		guizi,
		guirenForward,
		downZi,
		upZi,
		houseTianJiang,
		actualYue: (castOverride && castOverride.actualYue) || yue, // 真实月将(高亮/盘式用);yue 仅作上下盘对齐的天盘起支
	};
}


function buildKeData(layout, chartObj){
	const result = {
		raw: [],
		lines: [],
	};
	if(!layout || !chartObj || !chartObj.nongli || !chartObj.nongli.dayGanZi){
		return result;
	}
	const dayGanZi = chartObj.nongli.dayGanZi;
	const daygan = dayGanZi.substr(0, 1);
	const dayzi = dayGanZi.substr(1, 1);

	const idx1 = layout.downZi.indexOf(LRConst.GanJiZi[daygan]);
	if(idx1 < 0){
		return result;
	}
	const ke1zi = layout.upZi[idx1];
	const ke1 = [layout.houseTianJiang[idx1], ke1zi, daygan];

	const idx2 = layout.downZi.indexOf(ke1zi);
	const ke2zi = idx2 >= 0 ? layout.upZi[idx2] : '';
	const ke2 = [idx2 >= 0 ? layout.houseTianJiang[idx2] : '', ke2zi, ke1zi];

	const idx3 = layout.downZi.indexOf(dayzi);
	const ke3zi = idx3 >= 0 ? layout.upZi[idx3] : '';
	const ke3 = [idx3 >= 0 ? layout.houseTianJiang[idx3] : '', ke3zi, dayzi];

	const idx4 = layout.downZi.indexOf(ke3zi);
	const ke4zi = idx4 >= 0 ? layout.upZi[idx4] : '';
	const ke4 = [idx4 >= 0 ? layout.houseTianJiang[idx4] : '', ke4zi, ke3zi];

	const all = [ke1, ke2, ke3, ke4];
	const names = ['一课', '二课', '三课', '四课'];
	all.forEach((item, idx)=>{
		result.lines.push(`${names[idx]}：地盘=${item[2]}，天盘=${item[1]}，贵神=${item[0]}`);
	});
	result.raw = all;
	return result;
}


function buildSanChuanData(layout, keRaw, chartObj){
	if(!layout || !keRaw || keRaw.length !== 4 || !chartObj || !chartObj.nongli){
		return null;
	}
	try{
		const helper = new ChuangChart({
			owner: null,
			chartObj: chartObj,
			nongli: chartObj.nongli,
			ke: keRaw,
			liuRengChart: {
				upZi: layout.upZi,
				downZi: layout.downZi,
				houseTianJiang: layout.houseTianJiang,
			},
			x: 0,
			y: 0,
			width: 0,
			height: 0,
		});
		helper.genCuangs();
		return helper.cuangs || null;
	}catch(e){
		return null;
	}
}


function buildLiuRengReferenceContext(liureng, chartObj, guirengType, runyear, castOverride){
	const layout = buildLiuRengLayout(chartObj, guirengType, castOverride);
	const keData = buildKeData(layout, chartObj);
	const sanChuan = buildSanChuanData(layout, keData.raw, chartObj);
	const nongli = chartObj && chartObj.nongli ? chartObj.nongli : {};
	const dayGanZi = nongli && nongli.dayGanZi ? nongli.dayGanZi : '';
	const dayGan = dayGanZi.substr(0, 1);
	const dayZhi = dayGanZi.substr(1, 1);
	const dayGanBranch = LRConst.GanJiZi[dayGan] ? LRConst.GanJiZi[dayGan] : '';
	const prevDayGanZi = getPrevJiaZi(dayGanZi);
	const prevDayGan = extractSingleGan(prevDayGanZi);
	const prevDayZhi = extractSingleBranch(prevDayGanZi);
	const prevDayGanBranch = prevDayGan ? (LRConst.GanJiZi[prevDayGan] || '') : '';
	const monthGanZi = nongli && nongli.monthGanZi ? nongli.monthGanZi : '';
	const monthBranch = extractSingleBranch(monthGanZi);
	const jieqi = nongli && nongli.jieqi ? `${nongli.jieqi}` : '';
	const fourColumns = liureng && liureng.fourColumns ? liureng.fourColumns : {};
	const yearBranch = extractSingleBranch(fourColumns && fourColumns.year ? (fourColumns.year.ganzi || (fourColumns.year.branch ? fourColumns.year.branch.cell : '')) : '');
	const timeBranch = extractSingleBranch(fourColumns && fourColumns.time ? (fourColumns.time.ganzi || (fourColumns.time.branch ? fourColumns.time.branch.cell : '')) : '');
	// 月将高亮/盘式以「真实月将」为准(layout.actualYue);layout.yue 是起课法的天盘起支(仅用于上下盘对齐),非起课法下二者相等。
	const yueGeneralBranch = layout ? (layout.actualYue || layout.yue) : '';
	const occupyTimeBranch = timeBranch || (layout ? layout.timezi : '');
	const panStyle = resolveLiuRengTwelvePanStyle(yueGeneralBranch, occupyTimeBranch);
	const runYearGanZi = runyear && runyear.year ? extractGanZi(runyear.year) : '';
	const runYearGan = extractSingleGan(runYearGanZi);
	const runYearBranch = extractSingleBranch(runYearGanZi || (runyear && runyear.year ? runyear.year : ''));
	const season = resolveSeasonByMonthBranch(monthBranch);
	const guChenGuaSu = season ? GU_CHEN_GUA_SU_BY_SEASON[season] : null;
	const seasonMap = liureng && liureng.season ? liureng.season : {};
	const keRaw = keData && keData.raw ? keData.raw : [];
	const sanChuanGz = sanChuan && sanChuan.cuang ? sanChuan.cuang : [];
	const sanChuanGans = sanChuanGz.map((item)=>extractSingleGan(item)).filter(Boolean);
	const sanChuanBranches = sanChuanGz.map((item)=>extractSingleBranch(item)).filter(Boolean);
	const sanChuanGods = (sanChuan && sanChuan.tianJiang ? sanChuan.tianJiang : []).map((item)=>normalizeTianJiangName(item));
	const keUp = keRaw.map((item)=>extractSingleBranch(item[1])).filter(Boolean);
	const keDown = keRaw.map((item)=>extractSingleBranch(item[2])).filter(Boolean);
	const branchGodMap = {};
	const branchUpMap = {};
	const upDownMap = {};
	if(layout && layout.downZi){
		layout.downZi.forEach((branch, idx)=>{
			const up = layout.upZi && layout.upZi[idx] ? layout.upZi[idx] : '';
			branchGodMap[branch] = normalizeTianJiangName(layout.houseTianJiang && layout.houseTianJiang[idx] ? layout.houseTianJiang[idx] : '');
			branchUpMap[branch] = up;
			if(up && !upDownMap[up]){
				upDownMap[up] = branch;
			}
		});
	}
	const xun = liureng && liureng.xun ? liureng.xun : {};
	const xunHeadGanZi = xun['旬首'] ? `${xun['旬首']}` : '';
	const xunHeadBranch = extractSingleBranch(xun['旬首']);
	const xunTailBranch = extractSingleBranch(xun['旬尾']);
	const xunKongBranches = extractBranches(xun['旬空']);
	const yiMaBranches = uniqueStrings(extractBranches(liureng && liureng.gods ? liureng.gods['驿马'] : null));
	const dingHorseBranches = uniqueStrings([
		...extractBranches(xun['遁丁']),
		...extractBranches(xun['旬丁']),
	]);
	const horseBranches = uniqueStrings([
		...yiMaBranches,
		...dingHorseBranches,
	]);
	const xunGanMap = buildXunGanMap(dayGan, dayZhi);
	const ke1UpGan = xunGanMap[keUp[0]] || '';
	const ke3UpGan = xunGanMap[keUp[2]] || '';
	const dayZhiGan = xunGanMap[dayZhi] || '';
	const kePairGanTuples = keRaw.map((item, idx)=>{
		const upBranch = extractSingleBranch(item[1]);
		const downBranch = extractSingleBranch(item[2]);
		return {
			index: idx + 1,
			upBranch,
			downBranch,
			upGan: upBranch ? (xunGanMap[upBranch] || '') : '',
			downGan: downBranch ? (xunGanMap[downBranch] || '') : '',
		};
	});
	const tianHeGanPool = uniqueStrings([
		dayGan,
		dayZhiGan,
		ke1UpGan,
		ke3UpGan,
		...kePairGanTuples.map((item)=>item.upGan),
		...kePairGanTuples.map((item)=>item.downGan),
		...sanChuanGans,
	]);
	const courseGans = uniqueStrings([
		dayGan,
		ke1UpGan,
		ke3UpGan,
		...sanChuanGans,
	]);
	const courseBranches = uniqueStrings([
		...sanChuanBranches,
		...keUp,
		...keDown,
	]);
	const sunBranch = getPlanetBranch(chartObj, AstroConst.SUN);
	const moonBranch = getPlanetBranch(chartObj, AstroConst.MOON);
	const sunSuName = getPlanetSuName(chartObj, AstroConst.SUN);
	const moonSuName = getPlanetSuName(chartObj, AstroConst.MOON);
	const sunErfanBranch = getPlanetErfanBranch(chartObj, AstroConst.SUN);
	const moonErfanBranch = getPlanetErfanBranch(chartObj, AstroConst.MOON);
	const allKeShe = keRaw.length === 4 && keRaw.every((item)=>safeRestrain(item[1], item[2]));
	const allKeZei = keRaw.length === 4 && keRaw.every((item)=>safeRestrain(item[2], item[1]));
	const dayGodMap = {
		base: liureng && liureng.gods ? liureng.gods : {},
		gan: liureng && liureng.godsGan ? liureng.godsGan : {},
		month: liureng && liureng.godsMonth ? liureng.godsMonth : {},
		zi: liureng && liureng.godsZi ? liureng.godsZi : {},
		year: liureng && liureng.godsYear && liureng.godsYear.taisui1 ? liureng.godsYear.taisui1 : {},
	};
	// 昼/夜两贵的地盘位 + 当前用昼或夜（供毕法贵人类法 3/45/46/49/50）。
	const guiObj = LRConst.GuiRengs[guirengType] || LRConst.GuiRengs[2];
	const dayGuiBranch = guiObj && guiObj.day ? (guiObj.day[dayGan] || '') : '';
	const nightGuiBranch = guiObj && guiObj.night ? (guiObj.night[dayGan] || '') : '';
	const dayNight = (layout && layout.guizi === dayGuiBranch) ? '昼' : '夜';
	return {
		layout,
		keData,
		sanChuan,
		courseName: sanChuan && sanChuan.name ? `${sanChuan.name}` : '',
		dayGanZi,
		dayGan,
		dayZhi,
		dayGanBranch,
		yearBranch,
		timeBranch: occupyTimeBranch,
		runYearGanZi,
		runYearGan,
		runYearBranch,
		monthBranch,
		season,
		jieqi,
		sunBranch,
		moonBranch,
		sunSuName,
		moonSuName,
		sunErfanBranch,
		moonErfanBranch,
		prevDayGanZi,
		prevDayGan,
		prevDayZhi,
		prevDayGanBranch,
		guChenBranch: guChenGuaSu ? guChenGuaSu.guchen : '',
		guaSuBranch: guChenGuaSu ? guChenGuaSu.guasu : '',
		keRaw,
		keUpBranches: keUp,
		keDownBranches: keDown,
		ke1UpGan,
		ke3UpGan,
		dayZhiGan,
		kePairGanTuples,
		tianHeGanPool,
		ke1Up: keUp[0] || '',
		ke3Up: keUp[2] || '',
		courseGans,
		sanChuanBranches,
		sanChuanGans,
		sanChuanGods,
		firstBranch: sanChuanBranches[0] || '',
		midBranch: sanChuanBranches[1] || '',
		lastBranch: sanChuanBranches[2] || '',
		firstGan: sanChuanGans[0] || '',
		midGan: sanChuanGans[1] || '',
		lastGan: sanChuanGans[2] || '',
		firstGod: sanChuanGods[0] || '',
		midGod: sanChuanGods[1] || '',
		lastGod: sanChuanGods[2] || '',
		branchGodMap,
		branchUpMap,
		upDownMap,
		xunGanMap,
		guirenForward: !!(layout && layout.guirenForward),
		yueGeneralBranch,
		panStyle,
		xunHeadBranch,
		xunHeadGanZi,
		xunTailBranch,
		xunKongBranches,
		yiMaBranches,
		dingHorseBranches,
		horseBranches,
		courseBranches,
		allKeShe,
		allKeZei,
		dayGodMap,
		seasonMap,
		dayGanWuXing: LRConst.GanZiWuXing[dayGan] || '',
		dayZhiWuXing: LRConst.GanZiWuXing[dayZhi] || '',
		sanChuanText: sanChuanGz.length ? sanChuanGz.join(' / ') : '',
		sanChuanBranchText: sanChuanBranches.length ? sanChuanBranches.join('→') : '',
		sanChuanGodText: sanChuanGods.length ? sanChuanGods.join('→') : '',
		guizi: layout && layout.guizi ? layout.guizi : '',
		dayGuiBranch,
		nightGuiBranch,
		dayNight,
	};
}


export { buildLiuRengReferenceContext, buildLiuRengLayout, buildKeData, buildSanChuanData };
