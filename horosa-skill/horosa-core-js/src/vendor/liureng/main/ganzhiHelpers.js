// 六壬页 · 干支与七政辅助:月建序、旬奇 / 干德 / 干奇 / 天合表、地支 / 天干提取、七政星曜取支与条目、生克冲合、旺相休囚、孟仲季、天合证据。
// 只被 components/lrzhan/LiuRengMain.js 与同目录 main/ 下的兄弟模块引用。
import * as AstroConst from '../../../constants/AstroConst.js';
import * as LRConst from '../../liureng/LRConst.js';
import { cleanKey, extractGanZi, JiaZiList } from './birthRunYear.js';

const SEASON_BRANCH_GROUP = {
	spring: ['寅', '卯', '辰'],
	summer: ['巳', '午', '未'],
	autumn: ['申', '酉', '戌'],
	winter: ['亥', '子', '丑'],
};

export const MONTH_BRANCH_SEQUENCE = ['寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥', '子', '丑'];
export const JIU_CHOU_DAYS = ['乙卯', '己卯', '辛卯', '乙酉', '己酉', '辛酉', '戊子', '壬子', '戊午', '壬午'];
export const GAN_DE_GAN = {
	'甲': '甲',
	'乙': '庚',
	'丙': '丙',
	'丁': '壬',
	'戊': '戊',
	'己': '甲',
	'庚': '庚',
	'辛': '丙',
	'壬': '壬',
	'癸': '戊',
};
export const GAN_QI_BRANCH = {
	'甲': '午',
	'乙': '巳',
	'丙': '辰',
	'丁': '卯',
	'戊': '寅',
	'己': '丑',
	'庚': '未',
	'辛': '申',
	'壬': '酉',
	'癸': '戌',
};
export const XUN_QI_BY_XUN_HEAD = {
	'甲午': '子',
	'甲申': '子',
	'甲寅': '亥',
	'甲辰': '亥',
	'甲子': '丑',
	'甲戌': '丑',
};
export const TIANHE_PAIR_RULES = [
	{ key: 'jiaji', a: '甲', b: '己', label: '甲己' },
	{ key: 'yigeng', a: '乙', b: '庚', label: '乙庚' },
	{ key: 'bingxin', a: '丙', b: '辛', label: '丙辛' },
	{ key: 'dingren', a: '丁', b: '壬', label: '丁壬' },
	{ key: 'wugui', a: '戊', b: '癸', label: '戊癸' },
];

export function normalizeTianJiangName(name){
	const txt = `${name || ''}`.replace(/\s+/g, '');
	if(!txt){
		return '';
	}
	if(txt === '腾蛇'){
		return '螣蛇';
	}
	return txt;
}

export function uniqueStrings(values){
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

export function extractSingleBranch(raw){
	const txt = `${raw || ''}`;
	for(let i=txt.length - 1; i>=0; i--){
		const ch = txt.substr(i, 1);
		if(LRConst.ZiList.indexOf(ch) >= 0){
			return ch;
		}
	}
	return '';
}

export function extractSingleGan(raw){
	const txt = `${raw || ''}`;
	for(let i=0; i<txt.length; i++){
		const ch = txt.substr(i, 1);
		if(LRConst.GanList.indexOf(ch) >= 0){
			return ch;
		}
	}
	return '';
}

export function extractBranches(raw){
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

export const ERFAN_SU_TO_BRANCH = {
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

export function getPlanetObject(chartObj, planetId){
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

export function getPlanetBranch(chartObj, planetId){
	const obj = getPlanetObject(chartObj, planetId);
	if(!obj){
		return '';
	}
	return LRConst.getSignZi(obj.sign) || '';
}

const QIZHENG_DEFS = [
	{ id: AstroConst.SUN, name: '日' },
	{ id: AstroConst.MOON, name: '月' },
	{ id: AstroConst.MERCURY, name: '水' },
	{ id: AstroConst.VENUS, name: '金' },
	{ id: AstroConst.MARS, name: '火' },
	{ id: AstroConst.JUPITER, name: '木' },
	{ id: AstroConst.SATURN, name: '土' },
];

// 七政星曜色:主题语义色(亮 / 暗各一份,layouts/app/01-base.less 的 --horosa-planet-*;兜底 = 暗色取值)。
// 此前固定为暗底挑的浅色:「月」#cfd2d6 在宣纸底 1.3:1、「日」#e0a93b 2.1:1。
export const QIZHENG_PLANET_COLOR = {
	'日': 'var(--horosa-planet-sun, #e0a93b)',
	'月': 'var(--horosa-planet-moon, #cfd2d6)',
	'水': 'var(--horosa-planet-mercury, #5fb3c9)',
	'金': 'var(--horosa-planet-venus, #d98fb0)',
	'火': 'var(--horosa-planet-mars, #c9483e)',
	'木': 'var(--horosa-planet-jupiter, #73b36b)',
	'土': 'var(--horosa-planet-saturn, #c19a57)',
};

// 五行语义色：与六壬盘面 RengChart.getBranchColor 同口径（CSS 变量 + hex fallback）。
export const QIZHENG_WUXING_COLOR = {
	'木': 'var(--horosa-liureng-stem-wood, #73b36b)',
	'火': 'var(--horosa-liureng-stem-fire, #c9483e)',
	'土': 'var(--horosa-liureng-stem-earth, #c19a57)',
	'金': 'var(--horosa-liureng-stem-metal, #d8d2c7)',
	'水': 'var(--horosa-liureng-stem-water, #8f9694)',
};

// 七政：复用现成 getPlanetObject + getSignZi；顺逆按 lonspeed<0（与主星盘一致，见 AstroHelper）。
export function buildQiZhengItems(chartObj){
	if(!chartObj || !chartObj.objects){
		return [];
	}
	const sunBranch = getPlanetBranch(chartObj, AstroConst.SUN);
	const items = [];
	for(let i=0; i<QIZHENG_DEFS.length; i++){
		const def = QIZHENG_DEFS[i];
		const obj = getPlanetObject(chartObj, def.id);
		if(!obj){
			continue;
		}
		const branch = LRConst.getSignZi(obj.sign) || '';
		let deg = null;
		if(typeof obj.lon === 'number' && isFinite(obj.lon)){
			deg = ((obj.lon % 30) + 30) % 30;
		}
		items.push({
			key: def.id,
			name: def.name,
			branch,
			wx: branch ? (LRConst.GanZiWuXing[branch] || '') : '',
			deg,
			retro: typeof obj.lonspeed === 'number' && obj.lonspeed < 0,
			isYue: !!branch && branch === sunBranch,
		});
	}
	return items;
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

export function getPlanetSuName(chartObj, planetId){
	const obj = getPlanetObject(chartObj, planetId);
	if(!obj){
		return '';
	}
	return extractSuName(obj.su28 || '');
}

export function getPlanetErfanBranch(chartObj, planetId){
	const suName = getPlanetSuName(chartObj, planetId);
	if(suName && ERFAN_SU_TO_BRANCH[suName]){
		return ERFAN_SU_TO_BRANCH[suName];
	}
	return '';
}

export function safeRestrain(a, b){
	if(!a || !b){
		return false;
	}
	const list = LRConst.GanZiRestrain[a];
	return !!(list && list.indexOf(b) >= 0);
}

export function safeOppose(a, b){
	if(!a || !b){
		return false;
	}
	return LRConst.ZiCong[a] === b || LRConst.ZiCong[b] === a;
}

export function safeBrother(a, b){
	if(!a || !b){
		return false;
	}
	const list = LRConst.GanZiBrother[a];
	return !!(list && list.indexOf(b) >= 0);
}

export function safeAccrue(a, b){
	if(!a || !b){
		return false;
	}
	const list = LRConst.GanZiAccrue[a];
	return !!(list && list.indexOf(b) >= 0);
}

export function getBranchIndex(branch){
	return branch ? LRConst.ZiList.indexOf(branch) : -1;
}

export function shiftBranch(branch, delta){
	const idx = getBranchIndex(branch);
	if(idx < 0){
		return '';
	}
	return LRConst.ZiList[(idx + delta + 1200) % 12];
}

export function getPrevJiaZi(ganzi){
	const idx = JiaZiList.indexOf(extractGanZi(ganzi));
	if(idx < 0){
		return '';
	}
	return JiaZiList[(idx + 59) % 60];
}

export function matchMapValueByKey(obj, key){
	if(!obj || !key){
		return null;
	}
	if(obj[key] !== undefined){
		return obj[key];
	}
	const target = cleanKey(key);
	const keys = Object.keys(obj);
	for(let i=0; i<keys.length; i++){
		const k = keys[i];
		if(cleanKey(k) === target){
			return obj[k];
		}
	}
	return null;
}

export function hasAny(values, targets){
	if(!values || !targets || !values.length || !targets.length){
		return false;
	}
	return values.some((item)=>targets.indexOf(item) >= 0);
}

export function resolveSeasonByMonthBranch(branch){
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

export function getSeasonStateForBranch(seasonMap, branch){
	if(!seasonMap || !branch){
		return '';
	}
	const elem = LRConst.GanZiWuXing[branch];
	if(!elem){
		return '';
	}
	const state = matchMapValueByKey(seasonMap, elem);
	return `${state || ''}`;
}

export function isWangXiangState(state){
	const txt = `${state || ''}`;
	if(!txt){
		return false;
	}
	return txt.indexOf('王') >= 0 || txt.indexOf('旺') >= 0 || txt.indexOf('相') >= 0;
}

export function isXiuQiuState(state){
	const txt = `${state || ''}`;
	if(!txt){
		return false;
	}
	return txt.indexOf('休') >= 0 || txt.indexOf('囚') >= 0 || txt.indexOf('死') >= 0;
}

export function getMengZhongJiType(branch){
	if(LRConst.ZiMeng.indexOf(branch) >= 0){
		return 'meng';
	}
	if(LRConst.ZiZong.indexOf(branch) >= 0){
		return 'zhong';
	}
	if(LRConst.ZiJi.indexOf(branch) >= 0){
		return 'ji';
	}
	return '';
}

export function buildXunGanMap(dayGan, dayZhi){
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

export function containsJieQi(jieqi, names){
	const txt = `${jieqi || ''}`.trim();
	if(!txt || !names || !names.length){
		return false;
	}
	return names.some((name)=>txt.indexOf(name) >= 0);
}

export function createReferenceItem(meta, evidence, extra){
	return {
		...(meta || {}),
		evidence: uniqueStrings(evidence || []),
		...(extra || {}),
	};
}

function isMatchedTianHePair(g1, g2, a, b){
	if(!g1 || !g2 || !a || !b){
		return false;
	}
	return (g1 === a && g2 === b) || (g1 === b && g2 === a);
}

export function collectTianHeEvidence(context, a, b){
	const evidence = [];
	const kePairs = context && context.kePairGanTuples ? context.kePairGanTuples : [];
	kePairs.forEach((item)=>{
		if(isMatchedTianHePair(item.upGan, item.downGan, a, b)){
			evidence.push(`同课上下相合：第${item.index}课 ${item.upBranch || '—'}(${item.upGan || '空'}) ↔ ${item.downBranch || '—'}(${item.downGan || '空'})`);
		}
	});
	const sanChuanItems = [
		{ name: '初传', branch: context ? context.firstBranch : '', gan: context ? context.firstGan : '' },
		{ name: '中传', branch: context ? context.midBranch : '', gan: context ? context.midGan : '' },
		{ name: '末传', branch: context ? context.lastBranch : '', gan: context ? context.lastGan : '' },
	];
	for(let i=0; i<sanChuanItems.length; i++){
		for(let j=i + 1; j<sanChuanItems.length; j++){
			const left = sanChuanItems[i];
			const right = sanChuanItems[j];
			if(isMatchedTianHePair(left.gan, right.gan, a, b)){
				evidence.push(`三传有合：${left.name}${left.branch || '—'}(${left.gan || '空'}) ↔ ${right.name}${right.branch || '—'}(${right.gan || '空'})`);
			}
		}
	}
	if(isMatchedTianHePair(context ? context.dayGan : '', context ? context.ke3UpGan : '', a, b)){
		evidence.push(`日干与日支上神有合：日干${context ? context.dayGan || '—' : '—'} ↔ 日支上神天干${context ? context.ke3UpGan || '—' : '—'}（${context ? context.ke3Up || '—' : '—'}）`);
	}
	if(isMatchedTianHePair(context ? context.dayZhiGan : '', context ? context.ke1UpGan : '', a, b)){
		evidence.push(`日支与日干上神有合：日支天干${context ? context.dayZhiGan || '—' : '—'}（${context ? context.dayZhi || '—' : '—'}） ↔ 日干上神天干${context ? context.ke1UpGan || '—' : '—'}（${context ? context.ke1Up || '—' : '—'}）`);
	}
	return uniqueStrings(evidence);
}
