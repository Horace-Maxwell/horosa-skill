// 六壬页 · 参考匹配:参考上下文、大格 / 小局匹配、参考汇总与快照参考段(毕法检索与概览参考在 referenceOverview)。
// 只被 components/lrzhan/LiuRengMain.js 与同目录 main/ 下的兄弟模块引用。
import * as AstroConst from '../../../constants/AstroConst.js';
import * as LRConst from '../../liureng/LRConst.js';
import { resolveLiuRengTwelvePanStyle } from '../../liureng/LRPanStyle.js';
import { extractGanZi } from './birthRunYear.js';
import {
	MONTH_BRANCH_SEQUENCE, JIU_CHOU_DAYS, GAN_DE_GAN, GAN_QI_BRANCH, XUN_QI_BY_XUN_HEAD, TIANHE_PAIR_RULES,
	normalizeTianJiangName, uniqueStrings, extractSingleBranch, extractSingleGan, extractBranches,
	ERFAN_SU_TO_BRANCH, getPlanetBranch, getPlanetSuName, getPlanetErfanBranch, safeRestrain, safeOppose,
	safeBrother, safeAccrue, getBranchIndex, shiftBranch, getPrevJiaZi, matchMapValueByKey, hasAny,
	resolveSeasonByMonthBranch, getSeasonStateForBranch, isWangXiangState, isXiuQiuState, getMengZhongJiType,
	buildXunGanMap, containsJieQi, createReferenceItem, collectTianHeEvidence,
} from './ganzhiHelpers.js';
import { buildLiuRengLayout } from './castLayout.js';
import { buildKeData, buildSanChuanData } from './panData.js';
import { DA_GE_META, COURSE_TO_DAGE_KEY } from './referenceDaGe.js';
import { XIAO_JU_META, XIAO_JU_ALWAYS_REFERENCE_KEYS } from './referenceXiaoJu.js';
import { GU_CHEN_GUA_SU_BY_SEASON, TIANJIANG_JI, TIANJIANG_XIONG, buildReferenceDocumentText, matchLiuRengOverviewReferences } from './referenceOverview.js';

export function buildLiuRengReferenceContext(liureng, chartObj, guirengType, runyear, castOverride, extraOpts){
	// extraOpts.prebuilt={layout,keData,sanChuan}:扫描侧已用同函数起过课,
	// 直供跳过重算(不传=原路径,主页零波及)。
	const pb = extraOpts && extraOpts.prebuilt ? extraOpts.prebuilt : null;
	const layout = pb && pb.layout ? pb.layout : buildLiuRengLayout(chartObj, guirengType, castOverride);
	const keData = pb && pb.keData ? pb.keData : buildKeData(layout, chartObj);
	const sanChuan = pb && pb.sanChuan ? pb.sanChuan : buildSanChuanData(layout, keData.raw, chartObj, castOverride);
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
		// 🔴 上面 filter(Boolean) 会在某传无遁干时删掉空位，使 gans 整体上移、与 branches 错位 —— 右栏取象 mini 与
		// 初/中/末 gan 因而把「辛」错配给戌、「癸」错配给未（与中盘真三传天干不符）。故按支位「保位重建」（不 filter）
		// 供所有「按位取用」者；上面带 filter 的版本仍留给下方神煞/格局「合干池」（那里要干清单、空位本就该剔）。
		const sanChuanGansAligned = sanChuanGz.map((item)=>extractSingleGan(item));
		const sanChuanBranchesAligned = sanChuanGz.map((item)=>extractSingleBranch(item));
	const sanChuanGods = (sanChuan && sanChuan.tianJiang ? sanChuan.tianJiang : []).map((item)=>normalizeTianJiangName(item));
	const keUp = keRaw.map((item)=>extractSingleBranch(item[1])).filter(Boolean);
	// 🔴 保位重建(勿 filter):第一课的「下」是**日干**不是地支,extractSingleBranch 判空后
	// 被 filter 剔掉 → 整条数组前移一位,取象角色标注把二课下标成「1课下」…「4课下」恒不出现
	// (与上方 sanChuanGansAligned 刚修的同型漂移,当时漏了这行)。首位取日干寄宫。
	const keDown = keRaw.map((item, i)=>(i === 0
		? (extractSingleBranch(item[2]) || dayGanBranch)
		: extractSingleBranch(item[2])));
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
		// 本命支:空亡/年命上神两处早已按 benMingBranch 取用,此前 context 从不产出 → 「本命上神」一位恒不触发。
		benMingBranch: (extraOpts && extraOpts.benMingBranch && LRConst.ZiList.indexOf(extraOpts.benMingBranch) >= 0) ? extraOpts.benMingBranch : '',
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
		sanChuanBranches: sanChuanBranchesAligned,
		sanChuanGans: sanChuanGansAligned,
		sanChuanGods,
		firstBranch: sanChuanBranchesAligned[0] || '',
		midBranch: sanChuanBranchesAligned[1] || '',
		lastBranch: sanChuanBranchesAligned[2] || '',
		firstGan: sanChuanGansAligned[0] || '',
		midGan: sanChuanGansAligned[1] || '',
		lastGan: sanChuanGansAligned[2] || '',
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

export function matchDaGeReferences(context){
	if(!context){
		return [];
	}
	let key = context.courseName ? COURSE_TO_DAGE_KEY[context.courseName] : '';
	if(!key){
		if(context.allKeShe){
			key = 'yuanshou';
		}else if(context.allKeZei){
			key = 'chongshen';
		}
	}
	if(!key || !DA_GE_META[key]){
		return [];
	}
	const meta = DA_GE_META[key];
	return [createReferenceItem(meta, [
		context.courseName ? `当前课式：${context.courseName}` : '',
		context.sanChuanText ? `三传：${context.sanChuanText}` : '',
		context.dayGanZi ? `日干支：${context.dayGanZi}` : '',
	])];
}

export function matchXiaoJuReferences(context){
	if(!context){
		return [];
	}
	const refs = [];
	const added = {};
	const add = (key, evidence, extra = {})=>{
		if(!XIAO_JU_META[key]){
			return;
		}
		const uniqEvidence = uniqueStrings(evidence || []);
		if(added[key] !== undefined){
			const existed = refs[added[key]];
			if(!existed){
				return;
			}
			existed.evidence = uniqueStrings([...(existed.evidence || []), ...uniqEvidence]);
			Object.keys(extra || {}).forEach((k)=>{
				if(existed[k] === undefined || existed[k] === null || existed[k] === ''){
					existed[k] = extra[k];
				}
			});
			return;
		}
		const one = createReferenceItem(XIAO_JU_META[key], uniqEvidence, extra);
		refs.push(one);
		added[key] = refs.length - 1;
	};
	const findGodBranch = (godName)=>{
		if(!context.branchGodMap || !godName){
			return '';
		}
		const keys = Object.keys(context.branchGodMap);
		for(let i=0; i<keys.length; i++){
			const key = keys[i];
			if(context.branchGodMap[key] === godName){
				return key;
			}
		}
		return '';
	};
	const isBranchBeforeDayGan = (branch)=>{
		if(!branch || !context.dayGanBranch){
			return false;
		}
		const base = getBranchIndex(context.dayGanBranch);
		const idx = getBranchIndex(branch);
		if(base < 0 || idx < 0){
			return false;
		}
		const delta = (idx - base + 12) % 12;
		return delta > 0 && delta <= 5;
	};
	const isBranchBeforeGuiren = (branch)=>{
		if(!branch || !context.guizi || !context.guirenForward){
			return false;
		}
		const base = getBranchIndex(context.guizi);
		const idx = getBranchIndex(branch);
		if(base < 0 || idx < 0){
			return false;
		}
		const delta = (idx - base + 12) % 12;
		return delta > 0 && delta <= 5;
	};

	const hasPortalBranch = context.sanChuanBranches.some((item)=>item === '卯' || item === '酉');
	if(context.firstGod === '天后' && context.lastGod === '六合' && context.firstBranch && context.lastBranch){
		add('yinv', [
			`神将序列：${context.sanChuanGodText || '—'}`,
			context.sanChuanText ? `三传：${context.sanChuanText}` : '',
			hasPortalBranch ? '课传带卯酉门户' : '课传未见卯酉门户',
		]);
	}
	if(context.firstGod === '六合' && context.lastGod === '天后' && context.firstBranch && context.lastBranch){
		add('jiaotong', [
			`神将序列：${context.sanChuanGodText || '—'}`,
			context.sanChuanText ? `三传：${context.sanChuanText}` : '',
			hasPortalBranch ? '课传带卯酉门户' : '课传未见卯酉门户',
		]);
	}
	if(context.sanChuanBranches.length === 3 && context.sanChuanBranches.every((item)=>LRConst.ZiMeng.indexOf(item) >= 0)){
		add('yuantai', [
			`三传地支：${context.sanChuanBranchText || '—'}`,
		]);
	}
	const dayTopAreZhong = LRConst.ZiZong.indexOf(context.ke1Up) >= 0
		&& LRConst.ZiZong.indexOf(context.ke3Up) >= 0;
	const sanjiaoCond = context.sanChuanBranches.length === 3
		&& context.sanChuanBranches.every((item)=>LRConst.ZiZong.indexOf(item) >= 0)
		&& dayTopAreZhong
		&& context.sanChuanGods.indexOf('太阴') >= 0
		&& context.sanChuanGods.indexOf('六合') >= 0;
	if(sanjiaoCond){
		add('sanjiao', [
			`三传地支：${context.sanChuanBranchText || '—'}`,
			`三传神将：${context.sanChuanGodText || '—'}`,
			`日干/日支上神（四仲）：${context.ke1Up || '—'} / ${context.ke3Up || '—'}`,
		]);
	}
	if(['辰', '戌'].indexOf(context.ke1Up) >= 0 || ['辰', '戌'].indexOf(context.ke3Up) >= 0){
		add('zhanguan', [
			`日干上神：${context.ke1Up || '—'}；日支上神：${context.ke3Up || '—'}`,
		]);
	}
	const hasYiMaInCourse = context.yiMaBranches.length > 0
		&& context.yiMaBranches.some((item)=>context.courseBranches.indexOf(item) >= 0);
	const hasDingHorseInCourse = context.dingHorseBranches.length > 0
		&& context.dingHorseBranches.some((item)=>context.courseBranches.indexOf(item) >= 0);
	const allJi = context.sanChuanBranches.length === 3
		&& context.sanChuanBranches.every((item)=>LRConst.ZiJi.indexOf(item) >= 0);
	if(allJi && (hasYiMaInCourse || hasDingHorseInCourse)){
		add('youzi', [
			`三传地支：${context.sanChuanBranchText || '—'}`,
			`驿马入课传：${hasYiMaInCourse ? '是' : '否'}（${context.yiMaBranches.join('、') || '—'}）`,
			`丁马入课传：${hasDingHorseInCourse ? '是' : '否'}（${context.dingHorseBranches.join('、') || '—'}）`,
		]);
	}
	const headGod = context.xunHeadBranch ? context.branchGodMap[context.xunHeadBranch] : '';
	const headUp = context.xunHeadBranch ? context.branchUpMap[context.xunHeadBranch] : '';
	if(context.xunHeadBranch && context.xunTailBranch
		&& headGod === '玄武'
		&& headUp === context.xunTailBranch
		&& context.firstBranch === context.xunTailBranch){
		add('bikou', [
			`旬首：${context.xunHeadBranch}（乘${headGod}）`,
			`旬尾：${context.xunTailBranch}（发用）`,
		]);
	}
	const jieliCore = safeRestrain(context.dayGan, context.ke3Up) && safeRestrain(context.dayZhi, context.ke1Up);
	const jieliOppose = safeOppose(context.ke1Up, context.ke3Up);
	if(jieliCore){
		add('jieli', [
			`日干克日支上神：${context.dayGan || '—'}克${context.ke3Up || '—'}`,
			`日支克日干上神：${context.dayZhi || '—'}克${context.ke1Up || '—'}`,
			jieliOppose ? `上神相冲：${context.ke1Up || '—'}↔${context.ke3Up || '—'}` : '上神未冲（按两人法仍可取解离）',
		]);
	}
	const luanshouA = context.ke1Up && context.ke1Up === context.dayZhi && safeRestrain(context.dayZhi, context.dayGan);
	const luanshouB = context.ke3Up && context.dayGanBranch && context.ke3Up === context.dayGanBranch && safeRestrain(context.dayZhi, context.dayGan);
	if(luanshouA){
		add('luanshou', [
			`法二：日支临日干（日干上神${context.ke1Up || '—'} = 日支${context.dayZhi || '—'}）`,
			`法二：日支克日干（${context.dayZhi || '—'}克${context.dayGan || '—'}）`,
		]);
	}
	if(luanshouB){
		add('luanshou', [
			`法一：日干临日支（日支上神${context.ke3Up || '—'} = 日干寄支${context.dayGanBranch || '—'}）`,
			`法一：日支克日干（${context.dayZhi || '—'}克${context.dayGan || '—'}）`,
		]);
	}
	if(context.allKeShe){
		add('juesi', [
			'四课皆上克下（摄）',
			context.courseName ? `当前课式：${context.courseName}` : '',
		]);
	}
	if(context.allKeZei){
		add('wulu', [
			'四课皆下克上（贼）',
			context.courseName ? `当前课式：${context.courseName}` : '',
		]);
	}
	const hasGuChen = context.guChenBranch && context.courseBranches.indexOf(context.guChenBranch) >= 0;
	const hasGuaSu = context.guaSuBranch && context.courseBranches.indexOf(context.guaSuBranch) >= 0;
	const hasXunKong = context.xunKongBranches.length > 0
		&& context.courseBranches.some((item)=>context.xunKongBranches.indexOf(item) >= 0);
	if(hasGuChen && hasGuaSu && hasXunKong){
		add('gugua', [
			`孤辰/寡宿：${context.guChenBranch || '—'} / ${context.guaSuBranch || '—'}`,
			`旬空：${context.xunKongBranches.join('、') || '—'}`,
		]);
	}
	const longzhanDay = context.dayZhi === '卯' || context.dayZhi === '酉';
	const longzhanYong = context.firstBranch === '卯' || context.firstBranch === '酉';
	const longzhanRunYear = context.runYearBranch === '卯' || context.runYearBranch === '酉';
	if(longzhanDay && longzhanYong && longzhanRunYear){
		add('longzhan', [
			`日支：${context.dayZhi || '—'}；发用：${context.firstBranch || '—'}；行年：${context.runYearBranch || '—'}`,
		]);
	}
	if(context.guizi === '卯' || context.guizi === '酉'){
		add('lide', [
			`贵人临门：${context.guizi}`,
		]);
	}
	const zhuixuCondA = context.ke1Up && context.ke1Up === context.dayZhi && safeRestrain(context.dayGan, context.dayZhi);
	const zhuixuCondB = context.ke3Up && context.dayGanBranch && context.ke3Up === context.dayGanBranch && safeRestrain(context.dayGan, context.dayZhi);
	if(zhuixuCondA){
		add('zhuixu', [
			`法二：日支临日干（日干上神${context.ke1Up || '—'} = 日支${context.dayZhi || '—'}）`,
			`法二：日干克日支（${context.dayGan || '—'}克${context.dayZhi || '—'}）`,
		]);
	}
	if(zhuixuCondB){
		add('zhuixu', [
			`法一：日干临日支（日支上神${context.ke3Up || '—'} = 日干寄支${context.dayGanBranch || '—'}）`,
			`法一：日干克日支（${context.dayGan || '—'}克${context.dayZhi || '—'}）`,
		]);
	}
	const deGan = context.dayGan ? GAN_DE_GAN[context.dayGan] : '';
	const deBranch = deGan ? (LRConst.GanJiZi[deGan] || '') : '';
	const deElemByDayGan = {
		'甲': '木', '己': '木',
		'乙': '金', '庚': '金',
		'丙': '火', '辛': '火',
		'丁': '水', '壬': '水',
		'戊': '土', '癸': '土',
	};
	const xingElemByDayZhi = {
		'寅': '火', '午': '火', '戌': '火',
		'申': '木', '子': '木', '辰': '木',
		'巳': '金', '酉': '金', '丑': '金',
		'亥': '水', '卯': '水', '未': '水',
	};
	const wuXingKe = {
		'木': '土',
		'火': '金',
		'土': '水',
		'金': '木',
		'水': '火',
	};
	const wuXingSheng = {
		'木': '火',
		'火': '土',
		'土': '金',
		'金': '水',
		'水': '木',
	};
	const deElem = deElemByDayGan[context.dayGan] || '';
	const xingElem = xingElemByDayZhi[context.dayZhi] || '';
	const xingdeResult = (()=> {
		if(!deElem || !xingElem){
			return '';
		}
		if(deElem === xingElem){
			return '德刑同位';
		}
		if(wuXingKe[xingElem] === deElem){
			return '刑胜德';
		}
		if(wuXingKe[deElem] === xingElem){
			return '德胜刑';
		}
		if(wuXingSheng[deElem] === xingElem){
			return '刑胜德（受生）';
		}
		if(wuXingSheng[xingElem] === deElem){
			return '德胜刑（受生）';
		}
		return '';
	})();
	let xingBranches = [];
	if(['寅', '午', '戌'].indexOf(context.dayZhi) >= 0){
		xingBranches = ['寅', '午', '戌'];
	}else if(['申', '子', '辰'].indexOf(context.dayZhi) >= 0){
		xingBranches = ['申', '子', '辰'];
	}else if(['巳', '酉', '丑'].indexOf(context.dayZhi) >= 0){
		xingBranches = ['巳', '酉', '丑'];
	}else if(['亥', '卯', '未'].indexOf(context.dayZhi) >= 0){
		xingBranches = ['亥', '卯', '未'];
	}
	if(deBranch && xingBranches.length && context.courseBranches.indexOf(deBranch) >= 0
		&& hasAny(context.courseBranches, xingBranches)){
		add('xingde', [
			`日干：${context.dayGan || '—'}；德干：${deGan || '—'}；德寄支：${deBranch || '—'}`,
			`日支：${context.dayZhi || '—'}；刑支系：${xingBranches.join('、')}`,
			xingdeResult ? `德刑五行：德${deElem || '—'} / 刑${xingElem || '—'}；${xingdeResult}` : '',
		]);
	}
	const firstWuXing = context.firstBranch ? (LRConst.GanZiWuXing[context.firstBranch] || '') : '';
	if(firstWuXing && context.dayGanWuXing && firstWuXing === context.dayGanWuXing){
		add('wuqi', [
			`发用：${context.firstBranch || '—'}（${firstWuXing}）`,
			`日干：${context.dayGan || '—'}（${context.dayGanWuXing || '—'}）`,
		]);
	}
	const firstIsNew = context.firstBranch && (LRConst.ZiMeng.indexOf(context.firstBranch) >= 0 || LRConst.YangZi.indexOf(context.firstBranch) >= 0);
	const firstIsOld = context.firstBranch && (LRConst.ZiJi.indexOf(context.firstBranch) >= 0 || LRConst.YingZi.indexOf(context.firstBranch) >= 0);
	const lastIsNew = context.lastBranch && (LRConst.ZiMeng.indexOf(context.lastBranch) >= 0 || LRConst.YangZi.indexOf(context.lastBranch) >= 0);
	const lastIsOld = context.lastBranch && (LRConst.ZiJi.indexOf(context.lastBranch) >= 0 || LRConst.YingZi.indexOf(context.lastBranch) >= 0);
	if((firstIsNew && lastIsOld) || (firstIsOld && lastIsNew)){
		add('xingu', [
			`初传：${context.firstBranch || '—'}；末传：${context.lastBranch || '—'}`,
			firstIsNew && lastIsOld ? '由新趋旧' : '由旧转新',
		]);
	}
	let tunCount = 0;
	let fuCount = 0;
	if(context.firstGod && TIANJIANG_XIONG.indexOf(context.firstGod) >= 0){
		tunCount += 1;
	}
	if(context.firstGod && TIANJIANG_JI.indexOf(context.firstGod) >= 0){
		fuCount += 1;
	}
	if(context.firstBranch && (safeRestrain(context.dayGan, context.firstBranch) || safeRestrain(context.dayZhi, context.firstBranch))){
		tunCount += 1;
	}
	if(context.firstBranch && (safeAccrue(context.dayGan, context.firstBranch) || safeBrother(context.dayGan, context.firstBranch))){
		fuCount += 1;
	}
	if(context.firstBranch && safeOppose(context.dayZhi, context.firstBranch)){
		tunCount += 1;
	}
	if(context.firstBranch && context.xunKongBranches.indexOf(context.firstBranch) >= 0){
		tunCount += 1;
	}
	if(tunCount >= 2 || fuCount >= 2){
		add('tunfu', [
			`发用：${context.firstBranch || '—'}；贵神：${context.firstGod || '—'}`,
			`迍数：${tunCount}；福数：${fuCount}`,
		]);
	}
	if(context.firstGod && context.lastGod){
		const firstGood = TIANJIANG_JI.indexOf(context.firstGod) >= 0;
		const lastGood = TIANJIANG_JI.indexOf(context.lastGod) >= 0;
		const firstBad = TIANJIANG_XIONG.indexOf(context.firstGod) >= 0;
		const lastBad = TIANJIANG_XIONG.indexOf(context.lastGod) >= 0;
		if((firstGood && lastBad) || (firstBad && lastGood)){
			add('shizhong', [
				`初传：${context.firstBranch || '—'}（${context.firstGod || '—'}）`,
				`末传：${context.lastBranch || '—'}（${context.lastGod || '—'}）`,
			]);
		}
	}
	if(JIU_CHOU_DAYS.indexOf(context.dayGanZi) >= 0 && context.ke3Up === '丑'){
		add('jiuchou', [
			`日干支：${context.dayGanZi || '—'}`,
			`日支上神：${context.ke3Up || '—'}`,
		]);
	}
	const erfanSunBranch = context.sunSuName && ERFAN_SU_TO_BRANCH[context.sunSuName]
		? ERFAN_SU_TO_BRANCH[context.sunSuName]
		: '';
	const erfanMoonBranch = context.moonSuName && ERFAN_SU_TO_BRANCH[context.moonSuName]
		? ERFAN_SU_TO_BRANCH[context.moonSuName]
		: '';
	const erfanSunZhong = erfanSunBranch && LRConst.ZiZong.indexOf(erfanSunBranch) >= 0;
	const erfanMoonZhong = erfanMoonBranch && LRConst.ZiZong.indexOf(erfanMoonBranch) >= 0;
	const douGangToChouWei = (context.branchUpMap && context.branchUpMap['丑'] === '辰')
		|| (context.branchUpMap && context.branchUpMap['未'] === '辰');
	if(erfanSunZhong && erfanMoonZhong && douGangToChouWei){
		add('erfan', [
			`宿盘日月临仲：太阳${context.sunSuName || '—'}→${erfanSunBranch || '—'}；太阴${context.moonSuName || '—'}→${erfanMoonBranch || '—'}`,
			`斗罡加丑未：${context.branchUpMap['丑'] === '辰' ? '丑' : ''}${context.branchUpMap['未'] === '辰' ? ' 未' : ''}`.trim() || '否',
		]);
	}
	const isSiLi = containsJieQi(context.jieqi, ['立春', '立夏', '立秋', '立冬']);
	const tianHuoLinkedToPrev = [context.ke1Up, context.ke3Up, context.firstBranch, context.lastBranch]
		.some((item)=>item && (item === context.prevDayGanBranch || item === context.prevDayZhi));
	if(isSiLi && tianHuoLinkedToPrev){
		add('tianhuo', [
			`节气：${context.jieqi || '—'}`,
			`昨日日辰：${context.prevDayGanZi || '—'}；课传临值：${context.prevDayGanBranch || '—'} / ${context.prevDayZhi || '—'}`,
		]);
	}
	const isFenZhi = containsJieQi(context.jieqi, ['春分', '夏至', '秋分', '冬至']);
	if(isFenZhi && context.moonBranch && context.prevDayZhi && context.moonBranch === context.prevDayZhi){
		add('tiankou', [
			`节气：${context.jieqi || '—'}`,
			`太阴临昨支：月支${context.moonBranch || '—'} = 昨日日支${context.prevDayZhi || '—'}`,
		]);
	}
	if(context.timeBranch && context.firstBranch && safeRestrain(context.timeBranch, context.dayGan) && safeRestrain(context.firstBranch, context.dayGan)){
		add('tianwang', [
			`时支：${context.timeBranch || '—'}克${context.dayGan || '—'}`,
			`初传：${context.firstBranch || '—'}克${context.dayGan || '—'}`,
		]);
	}
	const youHunBranch = shiftBranch(context.monthBranch, -3);
	const coreTargets = uniqueStrings([context.runYearBranch, context.dayGanBranch, context.dayZhi]);
	if(youHunBranch && coreTargets.indexOf(youHunBranch) >= 0){
		add('feihun', [
			`月建：${context.monthBranch || '—'}；游魂：${youHunBranch || '—'}`,
			`命中位：${coreTargets.join('、') || '—'}`,
		]);
	}
	const sangmenBranch = extractSingleBranch(matchMapValueByKey(context.dayGodMap.year, '丧门'));
	if(sangmenBranch && coreTargets.indexOf(sangmenBranch) >= 0){
		add('sangmen', [
			`丧门：${sangmenBranch || '—'}`,
			context.firstGod === '白虎' ? '发用乘白虎，凶势更急' : '',
		]);
	}
	const monthSeqIdx = MONTH_BRANCH_SEQUENCE.indexOf(context.monthBranch);
	const tianGuiBranch = monthSeqIdx >= 0 ? ['酉', '午', '卯', '子'][monthSeqIdx % 4] : '';
	if(tianGuiBranch && coreTargets.indexOf(tianGuiBranch) >= 0){
		add('fuyang', [
			`月建：${context.monthBranch || '—'}；天鬼：${tianGuiBranch || '—'}`,
			`命中位：${coreTargets.join('、') || '—'}`,
		]);
	}
	const tianLuoBranch = shiftBranch(context.dayGanBranch, 1);
	const diWangBranch = tianLuoBranch ? shiftBranch(tianLuoBranch, 6) : '';
	const runYearUp = context.runYearBranch && context.branchUpMap ? (context.branchUpMap[context.runYearBranch] || '') : '';
	const coreUpTargets = uniqueStrings([context.ke1Up, context.ke3Up, runYearUp]);
	const luoWangBranches = uniqueStrings([tianLuoBranch, diWangBranch]);
	const luoWangCoreHits = luoWangBranches.filter((item)=>item && coreTargets.indexOf(item) >= 0);
	const luoWangUpHits = luoWangBranches.filter((item)=>item && coreUpTargets.indexOf(item) >= 0);
	if(luoWangCoreHits.length > 0 || luoWangUpHits.length > 0){
		add('luowang', [
			`日干寄支：${context.dayGanBranch || '—'}；天罗：${tianLuoBranch || '—'}；地网：${diWangBranch || '—'}`,
			`命中地位：${luoWangCoreHits.join('、') || '无'}（行年/日干寄支/日支：${coreTargets.join('、') || '—'}）`,
			`命中上神：${luoWangUpHits.join('、') || '无'}（行年/日干/日支上神：${coreUpTargets.join('、') || '—'}）`,
		]);
	}
	const dayGanChangSheng = extractSingleBranch(matchMapValueByKey(context.dayGodMap.gan, '长生'));
	const douGangOnChangSheng = dayGanChangSheng && context.branchUpMap && context.branchUpMap[dayGanChangSheng] === '辰';
	const firstState = getSeasonStateForBranch(context.seasonMap, context.firstBranch);
	const firstDownBranch = context.upDownMap ? (context.upDownMap[context.firstBranch] || '') : '';
	const firstWeak = isXiuQiuState(firstState)
		|| LRConst.ZiJi.indexOf(context.firstBranch) >= 0
		|| (firstDownBranch && safeRestrain(firstDownBranch, context.firstBranch));
	if(douGangOnChangSheng && firstWeak){
		add('tianyu', [
			`日干长生：${dayGanChangSheng || '—'}；罡加长生：辰临${dayGanChangSheng || '—'}`,
			`初传：${context.firstBranch || '—'}（${firstState || '—'}）${firstDownBranch ? `；下神：${firstDownBranch}` : ''}`,
		]);
	}
	const siqiHasDou = [context.firstBranch, context.ke1Up, context.ke3Up].some((item)=>item === '辰');
	const siqiSunInCore = context.sunBranch
		&& [context.dayGanBranch, context.dayZhi, context.runYearBranch].indexOf(context.sunBranch) >= 0;
	const siqiMoonInCore = context.moonBranch
		&& [context.dayGanBranch, context.dayZhi, context.runYearBranch].indexOf(context.moonBranch) >= 0;
	if(siqiHasDou && (siqiSunInCore || siqiMoonInCore)){
		add('siqi', [
			`斗罡入局：${context.firstBranch === '辰' ? '发用' : `课位(${context.ke1Up === '辰' ? '日干上神' : '日支上神'})`}`,
			`日月入主位：太阳${context.sunBranch || '—'}；太阴${context.moonBranch || '—'}`,
		]);
	}
	const deadGodBranch = monthSeqIdx >= 0 ? shiftBranch('巳', monthSeqIdx) : '';
	const whiteTigerTargets = uniqueStrings([
		context.dayGanBranch,
		context.dayZhi,
		context.runYearBranch,
	]).filter((item)=>item && context.branchGodMap[item] === '白虎');
	const whiteTigerCarryDead = deadGodBranch && context.branchGodMap[deadGodBranch] === '白虎';
	if(whiteTigerCarryDead && whiteTigerTargets.length){
		add('pohua', [
			`死神：${deadGodBranch || '—'}；白虎同位：是`,
			`白虎临：${whiteTigerTargets.join('、') || '—'}${context.firstGod === '白虎' ? '；并见发用白虎' : ''}`,
		]);
	}
	const dayGanState = getSeasonStateForBranch(context.seasonMap, context.dayGan);
	const dayZhiState = getSeasonStateForBranch(context.seasonMap, context.dayZhi);
	const sanChuanAllJi = context.sanChuanGods.length === 3
		&& context.sanChuanGods.every((item)=>TIANJIANG_JI.indexOf(item) >= 0);
	const sanGuangWangXiang = !!(context.firstBranch
		&& isWangXiangState(dayGanState)
		&& isWangXiangState(dayZhiState)
		&& isWangXiangState(firstState));
	if(sanGuangWangXiang && sanChuanAllJi){
		add('sanguang', [
			`三传贵神：${context.sanChuanGodText || '—'}`,
			`旺相：日干${context.dayGan || '—'}(${dayGanState || '—'})、日支${context.dayZhi || '—'}(${dayZhiState || '—'})、初传${context.firstBranch || '—'}(${firstState || '—'})`,
			`吉神判定：${context.sanChuanGods.join('→') || '—'}（全为吉神）`,
		]);
	}
	const sanyangCore = context.guirenForward
		&& context.firstBranch
		&& isWangXiangState(dayGanState)
		&& isWangXiangState(dayZhiState)
		&& isWangXiangState(firstState)
		&& isBranchBeforeGuiren(context.dayGanBranch)
		&& isBranchBeforeGuiren(context.dayZhi);
	if(sanyangCore){
		add('sanyang', [
			`贵人顺治：是；贵人位：${context.guizi || '—'}`,
			`日干/日支在贵人之前：${context.dayGanBranch || '—'} / ${context.dayZhi || '—'}`,
			`旺相：日干${context.dayGan || '—'}(${dayGanState || '—'})、日支${context.dayZhi || '—'}(${dayZhiState || '—'})、初传${context.firstBranch || '—'}(${firstState || '—'})`,
		]);
	}
	const xuanwuBranch = findGodBranch('玄武');
	const baihuBranch = findGodBranch('白虎');
	const lastState = getSeasonStateForBranch(context.seasonMap, context.lastBranch);
	const sanYinCond = !context.guirenForward
		&& isBranchBeforeDayGan(xuanwuBranch)
		&& isBranchBeforeDayGan(baihuBranch)
		&& isXiuQiuState(firstState)
		&& isXiuQiuState(lastState)
		&& context.timeBranch
		&& context.runYearBranch
		&& safeRestrain(context.timeBranch, context.runYearBranch);
	if(sanYinCond){
		add('sanyin', [
			`贵人逆治：是；元武/白虎在日前：${xuanwuBranch || '—'} / ${baihuBranch || '—'}`,
			`初末休囚：${context.firstBranch || '—'}(${firstState || '—'})、${context.lastBranch || '—'}(${lastState || '—'})；时支克行年：${context.timeBranch}克${context.runYearBranch}`,
		]);
	}
	const guirenCarrier = context.guizi ? (context.branchUpMap[context.guizi] || '') : '';
	const guirenCarrierState = getSeasonStateForBranch(context.seasonMap, guirenCarrier);
	const guirenOnCore = [context.dayGanBranch, context.dayZhi, context.runYearBranch].indexOf(context.guizi) >= 0;
	const sanChuanStates = [context.firstBranch, context.midBranch, context.lastBranch].map((item)=>getSeasonStateForBranch(context.seasonMap, item));
	const sanChuanAllWang = sanChuanStates.length === 3 && sanChuanStates.every((item)=>isWangXiangState(item));
	if(isWangXiangState(guirenCarrierState) && guirenOnCore && sanChuanAllWang){
		add('fugui', [
			`贵人临：${context.guizi || '—'}（命中日辰行年）`,
			`贵人所乘：${guirenCarrier || '—'}（${guirenCarrierState || '—'}）；三传生旺：是`,
		]);
	}
	const xunQiBranch = XUN_QI_BY_XUN_HEAD[extractGanZi(context.xunHeadGanZi)] || '';
	const ganQiBranch = context.dayGan ? (GAN_QI_BRANCH[context.dayGan] || '') : '';
	if((xunQiBranch && context.courseBranches.indexOf(xunQiBranch) >= 0)
		|| (ganQiBranch && context.courseBranches.indexOf(ganQiBranch) >= 0)){
		add('sanqi', [
			`旬首：${context.xunHeadGanZi || '—'}；旬奇：${xunQiBranch || '—'}`,
			`日干：${context.dayGan || '—'}；干奇：${ganQiBranch || '—'}`,
		]);
	}
	const xunYiBranch = context.xunHeadBranch;
	const dayIdx = getBranchIndex(context.dayZhi);
	const zhiYiBranch = dayIdx >= 0 ? LRConst.ZiList[(6 - dayIdx + 12) % 12] : '';
	if((xunYiBranch && context.courseBranches.indexOf(xunYiBranch) >= 0)
		|| (zhiYiBranch && context.courseBranches.indexOf(zhiYiBranch) >= 0)){
		add('liuyi', [
			`旬仪：${xunYiBranch || '—'}`,
			`支仪：${zhiYiBranch || '—'}`,
		]);
	}
	if(context.firstBranch === '戌' && context.firstGod === '太常' && hasYiMaInCourse){
		add('guanjue', [
			`发用：${context.firstBranch || '—'}（${context.firstGod || '—'}）`,
			`驿马：${context.yiMaBranches.join('、') || '—'}`,
		]);
	}
	const hasZiMaoWu = ['子', '卯', '午'].every((item)=>context.sanChuanBranches.indexOf(item) >= 0);
	if(hasZiMaoWu && ['寅', '申'].indexOf(context.monthBranch) >= 0){
		add('xuangai', [
			`三传地支：${context.sanChuanBranchText || '—'}`,
			`月建：${context.monthBranch || '—'}`,
		]);
	}
	if(context.branchUpMap && context.branchUpMap['申'] === '卯'){
		add('zhuolun', [
			`地盘申 -> 天盘${context.branchUpMap['申'] || '—'}`,
		]);
	}
	if(['巳', '戌', '卯'].every((item)=>context.sanChuanBranches.indexOf(item) >= 0)){
		add('zhuyin', [
			`三传地支：${context.sanChuanBranchText || '—'}`,
		]);
	}
	const yearGod = context.yearBranch ? context.branchGodMap[context.yearBranch] : '';
	const yueGod = context.yueGeneralBranch ? context.branchGodMap[context.yueGeneralBranch] : '';
	if(yearGod === '贵人' && yueGod === '贵人' && context.firstGod === '贵人'){
		add('longde', [
			`年支：${context.yearBranch || '—'}乘${yearGod || '—'}`,
			`月将：${context.yueGeneralBranch || '—'}乘${yueGod || '—'}；发用：${context.firstBranch || '—'}乘${context.firstGod || '—'}`,
		]);
	}
	const scIdx = context.sanChuanBranches.map((item)=>getBranchIndex(item));
	if(scIdx.length === 3 && scIdx.every((idx)=>idx >= 0)){
		const forward = scIdx[1] === (scIdx[0] + 1) % 12 && scIdx[2] === (scIdx[1] + 1) % 12;
		const backward = scIdx[1] === (scIdx[0] + 11) % 12 && scIdx[2] === (scIdx[1] + 11) % 12;
		if(forward || backward){
			add('lianzhu', [
				`三传地支：${context.sanChuanBranchText || '—'}`,
				forward ? '进连珠' : '退连珠',
			]);
		}
		const jianForward = scIdx[1] === (scIdx[0] + 2) % 12 && scIdx[2] === (scIdx[1] + 2) % 12;
		const jianBackward = scIdx[1] === (scIdx[0] + 10) % 12 && scIdx[2] === (scIdx[1] + 10) % 12;
		if(jianForward || jianBackward){
			add('jianchuan', [
				`三传地支：${context.sanChuanBranchText || '—'}`,
				jianForward ? '顺间传，跳跃前行' : '逆间传，跳跃后退',
			]);
		}
	}
	const liuchunAllYang = context.courseBranches.length > 0 && context.courseBranches.every((item)=>LRConst.YangZi.indexOf(item) >= 0);
	const liuchunAllYin = context.courseBranches.length > 0 && context.courseBranches.every((item)=>LRConst.YingZi.indexOf(item) >= 0);
	if(liuchunAllYang || liuchunAllYin){
		add('liuchun', [liuchunAllYang ? '四课三传地支全阳（六阳），利公开主动' : '四课三传地支全阴（六阴），利私谋隐晦']);
	}
	if(context.sanChuanBranches.length === 3 && Array.isArray(context.keUpBranches) && context.sanChuanBranches.every((item)=>context.keUpBranches.indexOf(item) >= 0)){
		add('panzhu', [`三传${context.sanChuanBranchText || '—'}尽入四课上神，事在目前`]);
	}
	if(context.sanChuanBranches.length === 3 && context.sanChuanBranches.every((item)=>['寅', '午', '戌'].indexOf(item) >= 0)){
		add('yanshang', [`三传地支：${context.sanChuanBranchText || '—'}`]);
	}
	if(context.sanChuanBranches.length === 3 && context.sanChuanBranches.every((item)=>['亥', '卯', '未'].indexOf(item) >= 0)){
		add('quzhi', [`三传地支：${context.sanChuanBranchText || '—'}`]);
	}
	if(context.sanChuanBranches.length === 3 && context.sanChuanBranches.every((item)=>['辰', '戌', '丑', '未'].indexOf(item) >= 0)){
		add('jiase', [`三传地支：${context.sanChuanBranchText || '—'}`]);
	}
	if(context.sanChuanBranches.length === 3 && context.sanChuanBranches.every((item)=>['巳', '酉', '丑'].indexOf(item) >= 0)){
		add('congge', [`三传地支：${context.sanChuanBranchText || '—'}`]);
	}
	if(context.sanChuanBranches.length === 3 && context.sanChuanBranches.every((item)=>['申', '子', '辰'].indexOf(item) >= 0)){
		add('runxia', [`三传地支：${context.sanChuanBranchText || '—'}`]);
	}
	TIANHE_PAIR_RULES.forEach((rule)=>{
		const evidence = collectTianHeEvidence(context, rule.a, rule.b);
		if(evidence.length){
			add(rule.key, [
				`课传天干池：${(context.tianHeGanPool || []).join('、') || '—'}`,
				`命中天合：${rule.label}`,
				...evidence,
			]);
		}
	});
	const jianggongDown = context.upDownMap ? (context.upDownMap['亥'] || '') : '';
	const mingtangDown = context.upDownMap ? (context.upDownMap['子'] || '') : '';
	const yutangDown = context.upDownMap ? (context.upDownMap['丑'] || '') : '';
	const isJianggongshi = jianggongDown && LRConst.ZiZong.indexOf(jianggongDown) >= 0;
	const isMingtangshi = mingtangDown && LRConst.ZiZong.indexOf(mingtangDown) >= 0;
	const isYutangshi = yutangDown && LRConst.ZiZong.indexOf(yutangDown) >= 0;
	if(isJianggongshi){
		add('jianggongshi', [
			`天盘登明（亥）加临地盘：${jianggongDown || '—'}（四仲）`,
			'判定：登明（亥）加四仲（子午卯酉）',
		]);
	}
	if(isMingtangshi){
		add('mingtangshi', [
			`天盘神后（子）加临地盘：${mingtangDown || '—'}（四仲）`,
			'判定：神后（子）加四仲（子午卯酉）',
		]);
	}
	if(isYutangshi){
		add('yutangshi', [
			`天盘大吉（丑）加临地盘：${yutangDown || '—'}（四仲）`,
			'判定：大吉（丑）加四仲（子午卯酉）',
		]);
	}
	const douBaseBranch = context.upDownMap ? (context.upDownMap['辰'] || '') : '';
	const douBaseType = getMengZhongJiType(douBaseBranch);
	if(douBaseType === 'meng'){
		add('doumeng', [
			`斗罡加临：辰临${douBaseBranch || '—'}（孟）`,
		]);
	}
	if(douBaseType === 'zhong'){
		add('douzhong', [
			`斗罡加临：辰临${douBaseBranch || '—'}（仲）`,
		]);
	}
	if(douBaseType === 'ji'){
		add('douji', [
			`斗罡加临：辰临${douBaseBranch || '—'}（季）`,
		]);
	}
	XIAO_JU_ALWAYS_REFERENCE_KEYS.forEach((key)=>{
		if(!added[key]){
			add(key, [
				'参考常驻：此局按局义作长期参照，不以单一局式硬触发。',
			], {
				source: '参考常驻',
			});
		}
	});

	return refs.sort((a, b)=>{
		const pa = Number.isFinite(a.priority) ? a.priority : 0;
		const pb = Number.isFinite(b.priority) ? b.priority : 0;
		return pb - pa;
	});
}

export function buildLiuRengReferenceBundle(liureng, chartObj, guirengType, runyear, castOverride, extraOpts){
	const context = buildLiuRengReferenceContext(liureng, chartObj, guirengType, runyear, castOverride, extraOpts);
	const dage = matchDaGeReferences(context);
	const xiaoju = matchXiaoJuReferences(context);
	const overview = matchLiuRengOverviewReferences(context);
	return {
		context,
		layout: context.layout,
		keData: context.keData,
		sanChuan: context.sanChuan,
		dage,
		xiaoju,
		overview,
	};
}

export function appendReferenceSnapshotSection(lines, title, refs, type = 'common'){
	lines.push(`[${title}]`);
	if(!refs || refs.length === 0){
		lines.push('无');
		lines.push('');
		return;
	}
	refs.forEach((item, idx)=>{
		lines.push(`${idx + 1}. ${item.name}`);
		const docText = buildReferenceDocumentText(item, type);
		if(docText){
			docText.split('\n').forEach((line)=>{
				lines.push(line);
			});
		}
		if(item.evidence && item.evidence.length){
			lines.push(`依据：${item.evidence.join('；')}`);
		}
		lines.push('');
	});
}
