// 神煞逐行起例
// 从 JinKouCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import * as LRConst from '../../liureng/LRConst.js';
import { JinKouWuXingKe, JINKOU_SANQI_SETS, JinKouShenShaOrder, JinKouElementColor } from './tables.js';
import { getElem, getDayGan, getDayZi, getMonthZi, getYearZi, getMonthIndexByZi, getSeasonByMonthZi, shiftZi } from './basics.js';
import { buildPowerText } from './wangShuai.js';

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

export function calcJinKouShenShaRows(liureng, rows, ext){
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

export function buildRow(option){
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
