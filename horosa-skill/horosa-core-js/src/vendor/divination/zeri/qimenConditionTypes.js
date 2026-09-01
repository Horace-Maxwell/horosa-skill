// [奇门择日] 找局条件注册表(纯前端单源,全程本地求值,无后端对)。
// ⚠ 与天星 conditionTypes.js 的关系:仅复用 GROUP_TYPES/JOINER_CN 与链式 joiner 树语义;
//   preflight[184] 的 sed 只咬 conditionTypes.js 的 `export const CONDITION_TYPES` —— 本表
//   必须独立文件+独立导出名(QIMEN_CONDITION_TYPES),两表绝不合并。
// 一键一行格式契约(preflight[186] 抓键):Tab 缩进 `\t键: {`;破格式=哨兵键抓取塌缩判红。
// 每类形状:{ category, label, defaults, fields[](ConditionParamsForm 按 kind 渲染),
//   validate(params)->''|错误文案, summary(params)->行摘要文本, evaluate(pan,params,ctx)->{pass,actual} }。
// 格局清单/门宫生克判定 import 自 DunJiaBaGongRules 加性导出 —— zeri 侧零手抄零复制,
// 与主盘格局判定同源同名(机械同源哨兵见 __tests__/qimenConditionTypes.test.js)。
// 🔴 宫位口径:cells 的 palaceNum 是 3×3 grid 位序(1巽2离3坤4震5中6兑7艮8坎9乾),非洛书号;
//   本表 palaces 字段的 value 一律用 grid 位序,label 拼「卦名+洛书号+方位」供用户按洛书认宫。
// [十一轮] keyDeps 合同(六壬同协议):每类显式声明所吃「可掩 plateKey 位」——值域
//   ['yearGz','monthGz','dayGz','timeGz','diurnal'] 子集;数组或 (params)=>数组(kong_all/
//   pillar_ganzhi 按参数维精掩)。cells/juText/值符使派生面=基础位不声明。面→位依据(逐面实核):
//   xunShou·fuTou=日柱 / allKong=各柱 / anGan·anZhi=时柱干+时旬 / wangShuai=月支五行 /
//   shenSha=四柱+isDiurnal(buildQimenShenSha 入参)/ ju_info 的 sanYuan 从 juText 解析=基础位。
//   缺 keyDeps 键=树掩码回退全位(qimenKeyMaskOf 保守兜底)+完备闸红。
import { GROUP_TYPES } from './conditionTypes.js';
import {
	BAGONG_PALACE_NAME,
	QIMEN_JI_PATTERN_NAMES,
	QIMEN_XIONG_PATTERN_NAMES,
	buildQimenOverviewSummary,
	getMenGongRelation,
} from '../../dunjia/DunJiaBaGongRules.js';
import { LUOSHU_NUM } from '../../dunjia/DunJiaFaDoc.js';
// [W3 全谱轮] 旺衰五路=主页「看旺衰」同函数(DunJiaCalc.buildQimenWangShuai);
// 伏反吟局=法奇门同函数(全盘级,≠宫级伏吟格)。
import { buildQimenWangShuai } from '../../dunjia/DunJiaCalc.js';
import { computePanType } from '../../dunjia/DunJiaFaCalc.js';

const opt = (arr)=>arr.map((v)=>({ value: v, label: v }));
const PALACE_DIR = { 1: '东南', 2: '正南', 3: '西南', 4: '正东', 5: '中宫', 6: '正西', 7: '东北', 8: '正北', 9: '西北' };
// 洛书 1..9 序 → grid 位序(坎1→8、坤2→3、震3→4、巽4→1、中5→5、乾6→9、兑7→6、艮8→7、离9→2)。
const GRID_BY_LUOSHU_ORDER = [8, 3, 4, 1, 5, 9, 6, 7, 2];

function palaceNameOf(gridNum){
	return gridNum === 5 ? '中' : (BAGONG_PALACE_NAME[gridNum] || `${gridNum}`);
}
export function qimenPalaceShort(gridNum){
	const name = palaceNameOf(gridNum);
	const luoshu = LUOSHU_NUM[name] || '';
	return `${name}${luoshu}宫`;
}
function palaceLabel(gridNum){
	return `${qimenPalaceShort(gridNum)}·${PALACE_DIR[gridNum] || ''}`;
}
export const QIMEN_PALACE_OPTIONS = GRID_BY_LUOSHU_ORDER.map((g)=>({ value: g, label: palaceLabel(g) }));
const OUTER_PALACE_OPTIONS = QIMEN_PALACE_OPTIONS.filter((o)=>o.value !== 5);

const NINE_GAN = ['乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const TEN_GAN = ['甲', ...NINE_GAN];
const TWELVE_ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const DOOR_OPTIONS = ['休', '生', '伤', '杜', '景', '死', '惊', '开'].map((d)=>({ value: d, label: `${d}门` }));
// 星值=单字;转盘八星轮上 芮/禽 归并显示为「内」(禽寄芮,DunJiaCalc panStar),匹配时 内 命中 芮 或 禽。
const STAR_OPTIONS = [
	{ value: '蓬', label: '天蓬' }, { value: '任', label: '天任' }, { value: '冲', label: '天冲' },
	{ value: '辅', label: '天辅' }, { value: '英', label: '天英' }, { value: '芮', label: '天芮(转盘显天内)' },
	{ value: '柱', label: '天柱' }, { value: '心', label: '天心' }, { value: '禽', label: '天禽(转盘寄芮显天内)' },
];
// 神值=单字;转盘已把 勾→虎/雀→玄 归一,勾/雀/常 仅飞盘·混合可命中(死开关裁剪:label 直标)。
const GOD_OPTIONS = [
	{ value: '符', label: '值符' }, { value: '蛇', label: '螣蛇' }, { value: '阴', label: '太阴' },
	{ value: '合', label: '六合' }, { value: '虎', label: '白虎' }, { value: '玄', label: '玄武' },
	{ value: '地', label: '九地' }, { value: '天', label: '九天' },
	{ value: '勾', label: '勾陈(仅飞盘/混合)' }, { value: '雀', label: '朱雀(仅飞盘/混合)' }, { value: '常', label: '太常(仅飞盘/混合)' },
];
const FLAG_OPTIONS = [
	{ value: 'kongWang', label: '空亡' }, { value: 'yima', label: '驿马' }, { value: 'gengHu', label: '庚/白虎' },
	{ value: 'jiXing', label: '六仪击刑' }, { value: 'ruMu', label: '奇仪入墓' }, { value: 'menPo', label: '门迫' },
];
const FLAG_CN = { kongWang: '空亡', yima: '驿马', jiXing: '击刑', ruMu: '入墓', menPo: '门迫', gengHu: '庚/虎' };	// [W3] overview.sixHarm 已算的第六害
const RELATION_OPTIONS = [
	{ value: 'sheng', label: '门生宫' }, { value: 'beisheng', label: '宫生门' },
	{ value: 'po', label: '门克宫(门迫)' }, { value: 'shouzhi', label: '宫克门(受制)' }, { value: 'bihe', label: '门宫比和' },
];
const RELATION_CN = { sheng: '门生宫', beisheng: '宫生门', po: '门克宫', shouzhi: '宫克门', bihe: '比和' };
const JU_NUM_OPTIONS = ['一', '二', '三', '四', '五', '六', '七', '八', '九'].map((n)=>({ value: n, label: `${n}局` }));
const SAN_YUAN_OPTIONS = ['上元', '中元', '下元'].map((v)=>({ value: v, label: v }));
const PILLAR_OPTIONS = [
	{ value: 'year', label: '年柱' }, { value: 'month', label: '月柱' }, { value: 'day', label: '日柱' }, { value: 'time', label: '时柱' },
];
const PILLAR_CN = { year: '年柱', month: '月柱', day: '日柱', time: '时柱' };
const MATCH_MODE_FIELD = {
	key: 'matchMode', kind: 'select', label: '要求',
	options: [{ value: 'any', label: '任一在场' }, { value: 'all', label: '全部在场' }],
};

function cellsOf(pan){
	return (pan && Array.isArray(pan.cells)) ? pan.cells : [];
}
function scopedCells(pan, palaces){
	const all = cellsOf(pan);
	if(!Array.isArray(palaces) || !palaces.length){
		return all;
	}
	const set = new Set(palaces.map(Number));
	return all.filter((c)=>c && set.has(c.palaceNum));
}
function scopeText(palaces){
	return (Array.isArray(palaces) && palaces.length) ? `@${palaces.map(qimenPalaceShort).join('/')}` : '';
}
function needValues(p){
	return (!p || !Array.isArray(p.values) || !p.values.length) ? '至少选择一个取值' : '';
}

// 通用「宫面取值」求值:getVals(cell)->该宫可命中的取值集;any=任一所选值在场,all=每个所选值均在场。
function evalCellValueCondition(pan, params, getVals, valueLabel){
	const scope = scopedCells(pan, params.palaces);
	const wanted = (params.values || []).slice();
	const cn = (v)=>(valueLabel ? valueLabel(v) : v);
	const perValue = wanted.map((v)=>scope.filter((cell)=>getVals(cell).indexOf(v) >= 0));
	const pass = params.matchMode === 'all' ? perValue.every((l)=>l.length > 0) : perValue.some((l)=>l.length > 0);
	const hitSegs = [];
	wanted.forEach((v, i)=>{
		if(perValue[i].length){
			hitSegs.push(`${cn(v)}@${perValue[i].map((cell)=>qimenPalaceShort(cell.palaceNum)).join('/')}`);
		}
	});
	let actual;
	if(hitSegs.length){
		actual = `命中 ${hitSegs.join('、')}${pass ? '' : '(未足全部在场)'}`;
	}else if(scope.length && scope.length <= 3){
		actual = scope.map((cell)=>`${qimenPalaceShort(cell.palaceNum)}=${getVals(cell).map(cn).join('') || '—'}`).join('、');
	}else{
		actual = '范围内未出现';
	}
	return { pass, actual };
}

// 格局求值:items 来自 buildQimenOverviewSummary(与主盘概览/AI 快照同源),按宫域过滤后逐名判在场。
function evalPatternCondition(items, params){
	const wanted = (params.names || []).slice();
	const set = (Array.isArray(params.palaces) && params.palaces.length) ? new Set(params.palaces.map(Number)) : null;
	const inScope = (items || []).filter((it)=>it && (!set || set.has(it.palace)));
	const perName = wanted.map((name)=>inScope.filter((it)=>it.name === name));
	const pass = params.matchMode === 'all' ? perName.every((l)=>l.length > 0) : perName.some((l)=>l.length > 0);
	const segs = wanted.map((name, i)=>(perName[i].length
		? `${name}@${perName[i].map((it)=>qimenPalaceShort(it.palace)).join('/')}`
		: `${name}:无`));
	return { pass, actual: segs.join('；') };
}

function starMatchSet(cell){
	const raw = `${cell && cell.tianXing ? cell.tianXing : ''}`;
	if(!raw){
		return [];
	}
	return raw === '内' ? ['芮', '禽'] : [raw];
}
function stripStarChar(starName){
	const text = `${starName || ''}`.replace(/^天/, '');
	return text ? text.charAt(0) : '';
}
function starNameMatches(actualStarName, wantedChars){
	const ch = stripStarChar(actualStarName);
	if(!ch || !Array.isArray(wantedChars) || !wantedChars.length){
		return false;
	}
	if(ch === '内'){
		return wantedChars.indexOf('芮') >= 0 || wantedChars.indexOf('禽') >= 0;
	}
	return wantedChars.indexOf(ch) >= 0;
}

export function makeQimenEvalCtx(pan){
	let overview;
	let overviewReady = false;
	let wangShuai;
	let panType;
	return {
		pan,
		overview(){
			if(!overviewReady){
				overview = buildQimenOverviewSummary(pan);
				overviewReady = true;
			}
			return overview;
		},
		// [W3 全谱轮] 旺衰五路(星/门/天干/地干/宫)一次惰性:主页「看旺衰」同函数。
		wangShuai(){
			if(wangShuai === undefined){
				try{ wangShuai = buildQimenWangShuai(pan) || null; }catch(e){ wangShuai = null; }
			}
			return wangShuai;
		},
		// 伏吟/反吟局(全盘级,法奇门同函数;≠宫级伏吟格)。
		panType(){
			if(panType === undefined){
				try{ panType = computePanType(pan) || { type: null, text: '' }; }catch(e){ panType = { type: null, text: '' }; }
			}
			return panType;
		},
	};
}

// ⚠ 一键一行(Tab 缩进 `\t键: {`),preflight[186] 依此抓键;新增类同时在 qimenScanEngine 的
// 求值链自动生效(evaluate 内聚,无第二处路由表)。
export const QIMEN_CONDITION_TYPES = {
	pattern_ji: {
		category: '格局',
		keyDeps: [],
		label: '吉格',
		defaults: { names: ['青龙回首'], palaces: [], matchMode: 'any' },
		fields: [
			{ key: 'names', kind: 'multiselect', label: '格局', options: QIMEN_JI_PATTERN_NAMES.map((n)=>({ value: n, label: n })) },
			{ key: 'palaces', kind: 'multiselect', label: '宫位', options: OUTER_PALACE_OPTIONS, hint: '空=任意宫;格局只判外八宫' },
			MATCH_MODE_FIELD,
		],
		validate(p){ return (!p.names || !p.names.length) ? '至少选择一个格局' : ''; },
		summary(p){ return `${(p.names || []).join('/')}${scopeText(p.palaces)}${p.matchMode === 'all' ? '(全部)' : ''}`; },
		evaluate(pan, p, ctx){
			const ov = ctx.overview();
			const items = ov ? [
				...ov.dun,
				...(ov.sanQiDeshi ? [{ name: '三奇得使', ...ov.sanQiDeshi }] : []),
				...ov.ji,
			] : [];
			return evalPatternCondition(items, p);
		},
	},
	pattern_xiong: {
		category: '格局',
		keyDeps: [],
		label: '凶格',
		defaults: { names: ['伏吟'], palaces: [], matchMode: 'any' },
		fields: [
			{ key: 'names', kind: 'multiselect', label: '格局', options: QIMEN_XIONG_PATTERN_NAMES.map((n)=>({ value: n, label: n })) },
			{ key: 'palaces', kind: 'multiselect', label: '宫位', options: OUTER_PALACE_OPTIONS, hint: '空=任意宫;格局只判外八宫' },
			MATCH_MODE_FIELD,
		],
		validate(p){ return (!p.names || !p.names.length) ? '至少选择一个格局' : ''; },
		summary(p){ return `${(p.names || []).join('/')}${scopeText(p.palaces)}${p.matchMode === 'all' ? '(全部)' : ''}`; },
		evaluate(pan, p, ctx){
			const ov = ctx.overview();
			return evalPatternCondition(ov ? ov.xiong : [], p);
		},
	},
	tian_gan: {
		category: '盘面',
		keyDeps: [],
		label: '天盘干',
		defaults: { values: ['丙'], palaces: [], matchMode: 'any' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '天盘', options: NINE_GAN.map((g)=>({ value: g, label: g })), hint: '甲为遁仪永不上盘,故不列' },
			{ key: 'palaces', kind: 'multiselect', label: '宫位', options: QIMEN_PALACE_OPTIONS, hint: '空=任意宫' },
			MATCH_MODE_FIELD,
		],
		validate: needValues,
		summary(p){ return `${(p.values || []).join('/')}${scopeText(p.palaces)}${p.matchMode === 'all' ? '(全部)' : ''}`; },
		evaluate(pan, p){
			return evalCellValueCondition(pan, p, (cell)=>(cell && cell.tianGan ? [cell.tianGan] : []));
		},
	},
	di_gan: {
		category: '盘面',
		keyDeps: [],
		label: '地盘干',
		defaults: { values: ['戊'], palaces: [], matchMode: 'any' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '地盘', options: NINE_GAN.map((g)=>({ value: g, label: g })), hint: '甲为遁仪永不上盘,故不列' },
			{ key: 'palaces', kind: 'multiselect', label: '宫位', options: QIMEN_PALACE_OPTIONS, hint: '空=任意宫' },
			MATCH_MODE_FIELD,
		],
		validate: needValues,
		summary(p){ return `${(p.values || []).join('/')}${scopeText(p.palaces)}${p.matchMode === 'all' ? '(全部)' : ''}`; },
		evaluate(pan, p){
			return evalCellValueCondition(pan, p, (cell)=>(cell && cell.diGan ? [cell.diGan] : []));
		},
	},
	door: {
		category: '盘面',
		keyDeps: [],
		label: '八门',
		defaults: { values: ['开'], palaces: [], matchMode: 'any' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '门', options: DOOR_OPTIONS },
			{ key: 'palaces', kind: 'multiselect', label: '宫位', options: QIMEN_PALACE_OPTIONS, hint: '空=任意宫;转盘中宫无门' },
			MATCH_MODE_FIELD,
		],
		validate: needValues,
		summary(p){ return `${(p.values || []).map((v)=>`${v}门`).join('/')}${scopeText(p.palaces)}${p.matchMode === 'all' ? '(全部)' : ''}`; },
		evaluate(pan, p){
			return evalCellValueCondition(pan, p, (cell)=>(cell && cell.door ? [cell.door] : []), (v)=>`${v}门`);
		},
	},
	star: {
		category: '盘面',
		keyDeps: [],
		label: '九星',
		defaults: { values: ['辅'], palaces: [], matchMode: 'any' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '星', options: STAR_OPTIONS },
			{ key: 'palaces', kind: 'multiselect', label: '宫位', options: QIMEN_PALACE_OPTIONS, hint: '空=任意宫;转盘中宫无星' },
			MATCH_MODE_FIELD,
		],
		validate: needValues,
		summary(p){ return `${(p.values || []).map((v)=>`天${v}`).join('/')}${scopeText(p.palaces)}${p.matchMode === 'all' ? '(全部)' : ''}`; },
		evaluate(pan, p){
			return evalCellValueCondition(pan, p, starMatchSet, (v)=>`天${v}`);
		},
	},
	god: {
		category: '盘面',
		keyDeps: [],
		label: '八神',
		defaults: { values: ['符'], palaces: [], matchMode: 'any' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '神', options: GOD_OPTIONS },
			{ key: 'palaces', kind: 'multiselect', label: '宫位', options: QIMEN_PALACE_OPTIONS, hint: '空=任意宫;转盘勾/雀已归虎/玄' },
			MATCH_MODE_FIELD,
		],
		validate: needValues,
		summary(p){ return `${(p.values || []).join('/')}${scopeText(p.palaces)}${p.matchMode === 'all' ? '(全部)' : ''}`; },
		evaluate(pan, p){
			return evalCellValueCondition(pan, p, (cell)=>(cell && cell.god ? [`${cell.god}`.charAt(0)] : []));
		},
	},
	palace_flag: {
		category: '盘面',
		keyDeps: [],
		label: '宫位标记',
		defaults: { values: ['kongWang'], palaces: [], matchMode: 'any' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '标记', options: FLAG_OPTIONS },
			{ key: 'palaces', kind: 'multiselect', label: '宫位', options: QIMEN_PALACE_OPTIONS, hint: '空=任意宫' },
			MATCH_MODE_FIELD,
		],
		validate: needValues,
		summary(p){ return `${(p.values || []).map((v)=>FLAG_CN[v] || v).join('/')}${scopeText(p.palaces)}${p.matchMode === 'all' ? '(全部)' : ''}`; },
		evaluate(pan, p){
			const flagsOf = (cell)=>{
				if(!cell){ return []; }
				const out = [];
				if(cell.hasKongWang){ out.push('kongWang'); }
				if(cell.isYiMa){ out.push('yima'); }
				if(cell.hasJiXing){ out.push('jiXing'); }
				if(cell.hasRuMu){ out.push('ruMu'); }
				if(cell.hasMenPo){ out.push('menPo'); }
				if((cell.tianGan === '庚') || `${cell.god || ''}`.indexOf('虎') >= 0){ out.push('gengHu'); }	// [W3] 同 overview gengHu 判据(god 为简称「虎」/全名双形)
				return out;
			};
			return evalCellValueCondition(pan, p, flagsOf, (v)=>FLAG_CN[v] || v);
		},
	},
	men_gong_relation: {
		category: '盘面',
		keyDeps: [],
		label: '门宫生克',
		defaults: { values: ['sheng'], palaces: [], matchMode: 'any' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '关系', options: RELATION_OPTIONS },
			{ key: 'palaces', kind: 'multiselect', label: '宫位', options: OUTER_PALACE_OPTIONS, hint: '空=任意宫;中宫无门不参与' },
			MATCH_MODE_FIELD,
		],
		validate: needValues,
		summary(p){ return `${(p.values || []).map((v)=>RELATION_CN[v] || v).join('/')}${scopeText(p.palaces)}${p.matchMode === 'all' ? '(全部)' : ''}`; },
		evaluate(pan, p){
			const relOf = (cell)=>{
				const rel = cell ? getMenGongRelation(cell.door, cell.palaceNum) : '';
				return rel ? [rel] : [];
			};
			return evalCellValueCondition(pan, p, relOf, (v)=>RELATION_CN[v] || v);
		},
	},
	zhifu: {
		category: '纲要',
		keyDeps: [],
		label: '值符',
		defaults: { stars: [], palaces: [9] },
		fields: [
			{ key: 'stars', kind: 'multiselect', label: '星', options: STAR_OPTIONS, hint: '空=任意星' },
			{ key: 'palaces', kind: 'multiselect', label: '落宫', options: QIMEN_PALACE_OPTIONS, hint: '空=任意宫' },
		],
		validate(p){
			const noStar = !p.stars || !p.stars.length;
			const noPalace = !p.palaces || !p.palaces.length;
			return (noStar && noPalace) ? '至少限定星或落宫之一' : '';
		},
		summary(p){
			const stars = (p.stars && p.stars.length) ? p.stars.map((v)=>`天${v}`).join('/') : '任意星';
			const where = (p.palaces && p.palaces.length) ? p.palaces.map(qimenPalaceShort).join('/') : '任意宫';
			return `${stars}落${where}`;
		},
		evaluate(pan, p, ctx){
			const ov = ctx.overview();
			const zf = ov && ov.zhiFu ? ov.zhiFu : null;
			if(!zf || !zf.palace){
				return { pass: false, actual: '值符落宫不可判(无盘)' };
			}
			const starOk = (!p.stars || !p.stars.length) || starNameMatches(zf.star, p.stars);
			const palaceOk = (!p.palaces || !p.palaces.length) || p.palaces.map(Number).indexOf(zf.palace) >= 0;
			return { pass: starOk && palaceOk, actual: `值符${zf.star || '—'}落${qimenPalaceShort(zf.palace)}(${zf.dir || '—'})` };
		},
	},
	zhishi: {
		category: '纲要',
		keyDeps: [],
		label: '值使',
		defaults: { doors: ['开'], palaces: [] },
		fields: [
			{ key: 'doors', kind: 'multiselect', label: '门', options: DOOR_OPTIONS, hint: '空=任意门' },
			{ key: 'palaces', kind: 'multiselect', label: '落宫', options: QIMEN_PALACE_OPTIONS, hint: '空=任意宫' },
		],
		validate(p){
			const noDoor = !p.doors || !p.doors.length;
			const noPalace = !p.palaces || !p.palaces.length;
			return (noDoor && noPalace) ? '至少限定门或落宫之一' : '';
		},
		summary(p){
			const doors = (p.doors && p.doors.length) ? p.doors.map((v)=>`${v}门`).join('/') : '任意门';
			const where = (p.palaces && p.palaces.length) ? p.palaces.map(qimenPalaceShort).join('/') : '任意宫';
			return `${doors}落${where}`;
		},
		evaluate(pan, p, ctx){
			const ov = ctx.overview();
			const zs = ov && ov.zhiShi ? ov.zhiShi : null;
			if(!zs || !zs.palace){
				return { pass: false, actual: '值使落宫不可判(无盘)' };
			}
			const doorChar = `${zs.door || ''}`.replace(/门$/, '');
			const doorOk = (!p.doors || !p.doors.length) || p.doors.indexOf(doorChar) >= 0;
			const palaceOk = (!p.palaces || !p.palaces.length) || p.palaces.map(Number).indexOf(zs.palace) >= 0;
			return { pass: doorOk && palaceOk, actual: `值使${zs.door || '—'}落${qimenPalaceShort(zs.palace)}(${zs.dir || '—'})` };
		},
	},
	ju_info: {
		category: '纲要',
		keyDeps: [],
		label: '局象',
		defaults: { dun: '阳遁', juShu: [], sanYuan: [] },
		fields: [
			{ key: 'dun', kind: 'select', label: '遁', options: [{ value: '', label: '任意' }, { value: '阳遁', label: '阳遁' }, { value: '阴遁', label: '阴遁' }] },
			{ key: 'juShu', kind: 'multiselect', label: '局数', options: JU_NUM_OPTIONS, hint: '空=任意局数' },
			{ key: 'sanYuan', kind: 'multiselect', label: '三元', options: SAN_YUAN_OPTIONS, hint: '空=任意元' },
		],
		validate(p){
			const empty = !p.dun && (!p.juShu || !p.juShu.length) && (!p.sanYuan || !p.sanYuan.length);
			return empty ? '至少限定 遁/局数/三元 之一' : '';
		},
		summary(p){
			const segs = [];
			if(p.dun){ segs.push(p.dun); }
			if(p.juShu && p.juShu.length){ segs.push(p.juShu.map((n)=>`${n}局`).join('/')); }
			if(p.sanYuan && p.sanYuan.length){ segs.push(p.sanYuan.join('/')); }
			return segs.join('·') || '任意';
		},
		evaluate(pan, p){
			const dunOk = !p.dun || pan.yinYangDun === p.dun;
			const juOk = (!p.juShu || !p.juShu.length) || p.juShu.indexOf(pan.juShu) >= 0;
			const yuanOk = (!p.sanYuan || !p.sanYuan.length) || p.sanYuan.indexOf(pan.sanYuan) >= 0;
			return { pass: dunOk && juOk && yuanOk, actual: pan.juText || `${pan.yinYangDun || ''}${pan.juShu || ''}局${pan.sanYuan || ''}` };
		},
	},
	pillar_ganzhi: {
		category: '四柱',
		keyDeps: (p)=>({ year: ['yearGz'], month: ['monthGz'], day: ['dayGz'], time: ['timeGz'] })[(p && p.pillar) || 'time'] || ['yearGz', 'monthGz', 'dayGz', 'timeGz'],
		label: '四柱干支',
		defaults: { pillar: 'time', gans: [], zhis: ['子'] },
		fields: [
			{ key: 'pillar', kind: 'select', label: '柱', options: PILLAR_OPTIONS },
			{ key: 'gans', kind: 'multiselect', label: '干', options: TEN_GAN.map((g)=>({ value: g, label: g })), hint: '空=不限干' },
			{ key: 'zhis', kind: 'multiselect', label: '支', options: TWELVE_ZHI.map((z)=>({ value: z, label: z })), hint: '空=不限支;时支即时辰筛选' },
		],
		validate(p){
			const empty = (!p.gans || !p.gans.length) && (!p.zhis || !p.zhis.length);
			return empty ? '至少限定干或支之一' : '';
		},
		summary(p){
			const segs = [];
			if(p.gans && p.gans.length){ segs.push(`干${p.gans.join('/')}`); }
			if(p.zhis && p.zhis.length){ segs.push(`支${p.zhis.join('/')}`); }
			return `${PILLAR_CN[p.pillar] || p.pillar}·${segs.join('·')}`;
		},
		evaluate(pan, p){
			const gz = `${(pan.ganzhi && pan.ganzhi[p.pillar]) || ''}`;
			if(gz.length < 2){
				return { pass: false, actual: `${PILLAR_CN[p.pillar] || p.pillar}缺失` };
			}
			const gan = gz.charAt(0);
			const zhi = gz.charAt(1);
			const ganOk = (!p.gans || !p.gans.length) || p.gans.indexOf(gan) >= 0;
			const zhiOk = (!p.zhis || !p.zhis.length) || p.zhis.indexOf(zhi) >= 0;
			return { pass: ganOk && zhiOk, actual: `${PILLAR_CN[p.pillar] || p.pillar}=${gz}` };
		},
	},
	wang_shuai: {
		category: '盘面',
		keyDeps: ['monthGz'],
		label: '旺衰(星门干宫·旺相休囚死)',
		defaults: { road: 'door', states: ['旺', '相'], palaces: [], matchMode: 'any' },
		fields: [
			{ key: 'road', kind: 'select', label: '判路', options: [{ value: 'star', label: '九星' }, { value: 'door', label: '八门' }, { value: 'tianGan', label: '天盘干' }, { value: 'diGan', label: '地盘干' }, { value: 'gong', label: '宫' }] },
			{ key: 'states', kind: 'multiselect', label: '旺衰态(任一)', options: opt(['旺', '相', '休', '囚', '死']), hint: '月令五行定态;判定=主页「看旺衰」buildQimenWangShuai 同函数' },
			{ key: 'palaces', kind: 'multiselect', label: '宫位', options: QIMEN_PALACE_OPTIONS, hint: '空=任意宫' },
			MATCH_MODE_FIELD,
		],
		validate: (p)=>(!p.states || !p.states.length) ? '至少选择一项' : '',
		summary(p){ return `${({ star: '星', door: '门', tianGan: '天干', diGan: '地干', gong: '宫' })[p.road] || '门'}旺衰:${(p.states || []).join('/')}${scopeText(p.palaces)}${p.matchMode === 'all' ? '(全部)' : ''}`; },
		evaluate(pan, p, ctx){
			const ws = ctx.wangShuai();
			if(!ws){ return { pass: false, actual: '旺衰:—' }; }
			const KEY = { star: 'starWangShuai', door: 'doorWangShuai', tianGan: 'tianGanWangShuai', diGan: 'diGanWangShuai', gong: 'gongWangShuai' };
			const k = KEY[p.road || 'door'];
			const scope = (p.palaces && p.palaces.length) ? ws.palaces.filter((c)=>p.palaces.includes(`${c.palaceNum}`)) : ws.palaces;
			const hits = scope.filter((c)=>(p.states || []).includes(c[k]));
			const pass = p.matchMode === 'all' ? (scope.length > 0 && hits.length === scope.length) : hits.length > 0;
			return { pass, actual: `月令${ws.monthElem}·${scope.map((c)=>`${c.palaceName}${c[k] || '—'}`).join(' ')}` };
		},
	},
	qm_shensha: {
		category: '神煞',
		keyDeps: ['yearGz', 'monthGz', 'dayGz', 'timeGz', 'diurnal'],
		label: '神煞值支(日禄天马桃花…)',
		defaults: { name: '日禄', values: ['午'] },
		fields: [
			{ key: 'name', kind: 'select', label: '神煞', options: opt(['日禄', '日德', '天马', '日马', '年马', '桃花', '破碎', '生气', '死气', '病符', '血支', '孤辰', '寡宿', '丧门', '吊客', '成神', '会神', '解神', '天目', '医星', '月厌', '月破', '贼神', '贵人', '游都', '文昌', '丧车', '幕贵']), hint: '判定=盘顶层 shenSha(buildQimenShenSha 同源 28 名)' },
			{ key: 'values', kind: 'multiselect', label: '值支(任一)', options: opt(['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']) },
		],
		validate: needValues,
		summary(p){ return `${p.name || '日禄'}值${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const items = (pan.shenSha && pan.shenSha.allItems) || [];
			const row = items.find((it)=>it.name === (p.name || '日禄'));
			const v = row ? `${row.value || ''}` : '';
			// 贵人类 value 可能是「午/申」双值文本——按包含判。
			const pass = !!v && v !== '—' && (p.values || []).some((z)=>v.indexOf(z) >= 0);
			return { pass, actual: `${p.name || '日禄'}:${v || '—'}` };
		},
	},
	fuyin_ju: {
		category: '格局',
		keyDeps: [],
		label: '伏吟/反吟局(全盘)',
		defaults: { value: 'none' },
		fields: [
			{ key: 'value', kind: 'select', label: '局态', options: [{ value: 'none', label: '非伏非反(正局)' }, { value: '伏吟', label: '天地伏吟局' }, { value: '反吟', label: '反吟局' }], hint: '全盘级(computePanType 法奇门同函数);与宫级「伏吟格」不同判面' },
		],
		validate: ()=>'',	// 奇门契约:每类必有 validate(单选类恒过)
		summary(p){ return ({ none: '正局(非伏反)', 伏吟: '伏吟局', 反吟: '反吟局' })[p.value] || p.value; },
		evaluate(pan, p, ctx){
			const t = ctx.panType();
			const cur = t && t.type ? t.type : 'none';
			return { pass: cur === (p.value || 'none'), actual: `盘局:${cur === 'none' ? '正局' : cur}` };
		},
	},
	kong_all: {
		category: '纲要',
		keyDeps: (p)=>({ rikong: ['dayGz'], shikong: ['timeGz'], year: ['yearGz'], month: ['monthGz'], day: ['dayGz'], time: ['timeGz'] })[(p && p.dim) || 'shikong'] || ['yearGz', 'monthGz', 'dayGz', 'timeGz'],
		label: '空亡细判(日空/时空/柱空)',
		defaults: { dim: 'shikong', values: ['子'] },
		fields: [
			{ key: 'dim', kind: 'select', label: '判面', options: [{ value: 'rikong', label: '日空(旬空)' }, { value: 'shikong', label: '时空' }, { value: 'year', label: '年柱空亡' }, { value: 'month', label: '月柱空亡' }, { value: 'day', label: '日柱空亡' }, { value: 'time', label: '时柱空亡' }] },
			{ key: 'values', kind: 'multiselect', label: '空亡支(任一)', options: opt(['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']), hint: 'pan.xunkong{日空,时空}+allKong 四柱全览同源;palace_flag 只判宫是否空亡,此类判空亡支本身' },
		],
		validate: needValues,
		summary(p){ return `${({ rikong: '日空', shikong: '时空', year: '年柱空', month: '月柱空', day: '日柱空', time: '时柱空' })[p.dim] || '时空'}:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const dim = p.dim || 'shikong';
			let txt = '';
			if(dim === 'rikong'){ txt = `${(pan.xunkong && pan.xunkong['日空']) || pan.kongWang || ''}`; }
			else if(dim === 'shikong'){ txt = `${(pan.xunkong && pan.xunkong['时空']) || ''}`; }
			else{
				const ak = pan.allKong || {};
				txt = `${ak[({ year: '年空', month: '月空', day: '日空', time: '时空' })[dim]] || ''}`;	// 真键=中文「X空」(dump 实抓)
			}
			const pass = !!txt && (p.values || []).some((z)=>txt.indexOf(z) >= 0);
			return { pass, actual: `${({ rikong: '日空', shikong: '时空', year: '年柱空', month: '月柱空', day: '日柱空', time: '时柱空' })[dim]}:${txt || '—'}` };
		},
	},
	xun_shou: {
		category: '纲要',
		keyDeps: ['dayGz'],
		label: '旬首/符头',
		defaults: { dim: 'xunShou', values: ['甲子'] },
		fields: [
			{ key: 'dim', kind: 'select', label: '判面', options: [{ value: 'xunShou', label: '旬首' }, { value: 'fuTou', label: '符头' }] },
			{ key: 'values', kind: 'multiselect', label: '取值(任一;含判)', options: opt(['甲子', '甲戌', '甲申', '甲午', '甲辰', '甲寅', '戊', '己', '庚', '辛', '壬', '癸']), hint: '旬首=六甲;符头文本可含六仪(按包含匹配)' },
		],
		validate: needValues,
		summary(p){ return `${p.dim === 'fuTou' ? '符头' : '旬首'}:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const txt = `${pan[p.dim || 'xunShou'] || ''}`;
			const pass = !!txt && (p.values || []).some((v)=>txt.indexOf(v) >= 0);
			return { pass, actual: `旬首${pan.xunShou || '—'}·符头${pan.fuTou || '—'}` };
		},
	},
	an_ganzhi: {
		category: '盘面',
		keyDeps: ['timeGz'],
		label: '暗干/暗支',
		defaults: { dim: 'anGan', values: ['甲'], palaces: [], matchMode: 'any' },
		fields: [
			{ key: 'dim', kind: 'select', label: '判面', options: [{ value: 'anGan', label: '暗干' }, { value: 'anZhi', label: '暗支' }] },
			{ key: 'values', kind: 'multiselect', label: '取值(任一)', options: opt(['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸', '子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']), hint: '暗干随 anGanMode 开关产出;未开启则各宫为空恒不命中' },
			{ key: 'palaces', kind: 'multiselect', label: '宫位', options: QIMEN_PALACE_OPTIONS, hint: '空=任意宫' },
			MATCH_MODE_FIELD,
		],
		validate: needValues,
		summary(p){ return `${p.dim === 'anZhi' ? '暗支' : '暗干'}:${(p.values || []).join('/')}${scopeText(p.palaces)}${p.matchMode === 'all' ? '(全部)' : ''}`; },
		evaluate(pan, p){
			const dim = p.dim || 'anGan';
			return evalCellValueCondition(pan, p, (cell)=>(cell && cell[dim] ? [cell[dim]] : []));
		},
	},
};

// ── UI 条件树(链式 joiner,与天星工作台同语义) ──
// 组节点无 op;兄弟第 2 个起各带 joiner(all/any/xor)表「本行与上方结果的连接门」。
export function newQimenLeaf(type, joiner){
	const spec = QIMEN_CONDITION_TYPES[type];
	return {
		kind: 'leaf',
		type,
		negate: false,
		joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all',
		params: spec ? JSON.parse(JSON.stringify(spec.defaults)) : {},
	};
}
export function newQimenGroup(joiner){
	return { kind: 'group', negate: false, joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all', children: [] };
}

export function qimenLeafSummary(leaf){
	const spec = leaf ? QIMEN_CONDITION_TYPES[leaf.type] : null;
	if(!spec){
		return '未知条件';
	}
	let body = '';
	try{
		body = spec.summary(leaf.params || {});
	}catch(e){
		body = '';
	}
	return `${leaf.negate ? '非·' : ''}${spec.label}·${body}`;
}

function compileSelf(node){
	let compiled;
	if(node.kind === 'group' || Array.isArray(node.children)){
		compiled = compileChain(node.children);
	}else{
		const spec = QIMEN_CONDITION_TYPES[node.type];
		if(!spec){
			throw new Error(`未知条件类型:${node.type}`);
		}
		const msg = spec.validate ? spec.validate(node.params || {}) : '';
		if(msg){
			throw new Error(`「${spec.label}」条件:${msg}`);
		}
		compiled = { type: node.type, params: JSON.parse(JSON.stringify(node.params || {})) };
	}
	return node.negate ? { type: 'not', conditions: [compiled] } : compiled;
}
// 行链 → 求值树:第 2 行起按各自 joiner 左折叠;连续同门扁平为多元组(与天星 compileTree 同构)。
function compileChain(children){
	const list = Array.isArray(children) ? children : [];
	if(!list.length){
		throw new Error('条件列表为空');
	}
	let acc = compileSelf(list[0]);
	for(let i = 1; i < list.length; i++){
		const joiner = GROUP_TYPES.indexOf(list[i].joiner) >= 0 ? list[i].joiner : 'all';
		const rhs = compileSelf(list[i]);
		if(acc.type === joiner && Array.isArray(acc.conditions)){
			acc = { type: joiner, conditions: [...acc.conditions, rhs] };
		}else{
			acc = { type: joiner, conditions: [acc, rhs] };
		}
	}
	return acc;
}
export function compileQimenTree(root){
	return compileSelf(root);
}
