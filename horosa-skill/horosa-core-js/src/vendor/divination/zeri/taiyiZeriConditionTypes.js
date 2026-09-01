// [Z3·太乙择日] 条件注册表(时辰粒度)。判定单源:盘=calcTaiyi(太乙页同一本地引擎,parity
// 五锚金标看守)、格局=computeGeju、主客胜负=computeVictory(太乙页断法面同函数)——
// 主太乙算法/格局表修正,择日自动跟(制度层1)。spec 契约与 QIMEN/HUANGLI/BAZI 逐字段同构;
// ctx=makeTaiyiZeriEvalCtx(pan)(格局/胜负惰性一次)。一键一行 Tab 缩进(preflight 键集契约)。
import { computeGeju } from '../../taiyi/core/taiyiGeju.js';
import { computeVictory, computeEhui, computeShiJing, computeShenSuan, computeFenye, computeSanyuan, computeWuziyuan, TAIYI_GONG_INFO } from '../../taiyi/core/taiyiDuanfa.js';
import { computeTaiyiShuli } from '../../taiyi/core/taiyiShuli.js';
import { computeTaiyiNayin } from '../../taiyi/core/taiyiNayin.js';
import { GROUP_TYPES, JOINER_CN } from './conditionTypes.js';

export { GROUP_TYPES, JOINER_CN };

// 十六宫环(太乙盘位序;千年常量)。
export const GONG16 = ['子', '丑', '艮', '寅', '卯', '辰', '巽', '巳', '午', '未', '坤', '申', '酉', '戌', '乾', '亥'];
const GONG9 = ['1', '2', '3', '4', '5', '6', '7', '8', '9'];
// 格局 kind→中文(computeGeju 的 kind 集;名文本同源自其 name 字段,此表只作 UI 选项)。
export const TAIYI_GEJU_KINDS = [
	{ value: 'yan', label: '掩(掩太乙)' },
	{ value: 'po', label: '迫(迫太乙)' },
	{ value: 'guan', label: '关(算长而和)' },
	{ value: 'qiu', label: '囚(主将同太乙)' },
	{ value: 'ge', label: '格(主将对太乙)' },
	{ value: 'dui', label: '对(始击相对)' },
	{ value: 'ti', label: '提(二目提太乙)' },
	{ value: 'xie', label: '挟(二目夹太乙)' },
	{ value: 'ji', label: '击(击太乙)' },
];

const opt = (arr)=>arr.map((v)=>({ value: v, label: v }));
const needValues = (p)=>(!p.values || !p.values.length) ? '至少选择一项' : '';

// 惰性求值上下文(格局/胜负各算一次)。
export function makeTaiyiZeriEvalCtx(pan){
	let geju = null;
	let victory = null;
	let shuli;
	let shensuan;
	let shijing;
	return {
		geju(){
			if(!geju){
				try{
					geju = computeGeju(pan) || [];
				}catch(e){
					geju = [];
				}
			}
			return geju;
		},
		victory(){
			if(victory === null){
				try{
					victory = computeVictory(pan, this.geju()) || null;
				}catch(e){
					victory = null;
				}
			}
			return victory;
		},
		// [W1 全谱轮] 数理/诸算/十精 惰性一次(断法面同函数;异常兜空=该叶判否不炸树)
		shuli(){
			if(shuli === undefined){
				try{ shuli = computeTaiyiShuli(pan) || null; }catch(e){ shuli = null; }
			}
			return shuli;
		},
		shensuan(){
			if(shensuan === undefined){
				try{ shensuan = computeShenSuan(pan) || null; }catch(e){ shensuan = null; }
			}
			return shensuan;
		},
		shijing(){
			if(shijing === undefined){
				try{ shijing = computeShiJing(pan) || null; }catch(e){ shijing = null; }
			}
			return shijing;
		},
	};
}

const numIn = (v, values)=>(values || []).map(Number).includes(Number(v));

export const TAIYI_CONDITION_TYPES = {
	yinyang_ju: {
		category: '局式',
		label: '阴阳遁',
		defaults: { value: '阳' },
		fields: [
			{ key: 'value', kind: 'select', label: '遁', options: [{ value: '阳', label: '阳遁' }, { value: '阴', label: '阴遁' }] },
		],
		summary(p){ return `${p.value || '阳'}遁`; },
		evaluate(pan, p){
			const text = (pan.kook && pan.kook.text) || '';
			const isYang = text.indexOf('阳') >= 0 || text.indexOf('陽') >= 0;
			return { pass: p.value === '阴' ? !isYang : isYang, actual: `局:${text || '?'}` };
		},
	},
	ju_num: {
		category: '局式',
		label: '局数',
		defaults: { values: ['1'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '局数(1-72)', options: Array.from({ length: 72 }, (_, i)=>({ value: `${i + 1}`, label: `${i + 1}局` })) },
		],
		validate: needValues,
		summary(p){ return `局数:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const n = pan.kook && pan.kook.num;
			return { pass: numIn(n, p.values), actual: `局:${(pan.kook && pan.kook.text) || '?'}` };
		},
	},
	taiyi_gong: {
		category: '落宫',
		label: '太乙落宫',
		defaults: { values: ['子'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '宫', options: opt(GONG16) },
		],
		validate: needValues,
		summary(p){ return `太乙:${(p.values || []).join('/')}宫`; },
		evaluate(pan, p){
			return { pass: (p.values || []).includes(pan.taiyiPalace), actual: `太乙落${pan.taiyiPalace || '?'}宫(数${pan.taiyiNum || '?'})` };
		},
	},
	wenchang_gong: {
		category: '落宫',
		label: '文昌(天目)落宫',
		defaults: { values: ['巽'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '宫', options: opt(GONG16) },
		],
		validate: needValues,
		summary(p){ return `文昌:${(p.values || []).join('/')}宫`; },
		evaluate(pan, p){
			return { pass: (p.values || []).includes(pan.skyeyes), actual: `文昌落${pan.skyeyes || '?'}宫` };
		},
	},
	shiji_gong: {
		category: '落宫',
		label: '始击落宫',
		defaults: { values: ['子'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '宫', options: opt(GONG16) },
		],
		validate: needValues,
		summary(p){ return `始击:${(p.values || []).join('/')}宫`; },
		evaluate(pan, p){
			return { pass: (p.values || []).includes(pan.sf), actual: `始击落${pan.sf || '?'}宫` };
		},
	},
	jishen_gong: {
		category: '落宫',
		label: '计神/合神落宫',
		defaults: { who: 'jigod', values: ['寅'] },
		fields: [
			{ key: 'who', kind: 'select', label: '神', options: [{ value: 'jigod', label: '计神' }, { value: 'hegod', label: '合神' }] },
			{ key: 'values', kind: 'multiselect', label: '宫', options: opt(GONG16) },
		],
		validate: needValues,
		summary(p){ return `${p.who === 'hegod' ? '合神' : '计神'}:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const v = p.who === 'hegod' ? pan.hegod : pan.jigod;
			return { pass: (p.values || []).includes(v), actual: `计神${pan.jigod || '?'}·合神${pan.hegod || '?'}` };
		},
	},
	youshen_gong: {
		category: '落宫',
		label: '游神落宫(五福/大游/小游)',
		defaults: { who: 'wufuNum', values: ['1'] },
		fields: [
			{ key: 'who', kind: 'select', label: '游神', options: [{ value: 'wufuNum', label: '五福' }, { value: 'bigyoNum', label: '大游' }, { value: 'smyoNum', label: '小游' }, { value: 'threewindNum', label: '三风' }, { value: 'fivewindNum', label: '五风' }, { value: 'eightwindNum', label: '八风' }] },	// [W1] 风三游=同数形 pan 键,纯扩档
			{ key: 'values', kind: 'multiselect', label: '宫数(1-9)', options: opt(GONG9) },
		],
		validate: needValues,
		summary(p){ return `${({ wufuNum: '五福', bigyoNum: '大游', smyoNum: '小游', threewindNum: '三风', fivewindNum: '五风', eightwindNum: '八风' })[p.who] || p.who}:${(p.values || []).join('/')}宫`; },
		evaluate(pan, p){
			const v = pan[p.who || 'wufuNum'];
			return { pass: numIn(v, p.values), actual: `五福${pan.wufuNum || '?'}·大游${pan.bigyoNum || '?'}·小游${pan.smyoNum || '?'}` };
		},
	},
	geju_kind: {
		category: '格局',
		label: '格局(掩迫关囚格对提挟击)',
		defaults: { values: ['yan'], mode: 'with' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '格局类', options: TAIYI_GEJU_KINDS, hint: '判定=太乙页断法面 computeGeju 同函数' },
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'with', label: '出现任一' }, { value: 'without', label: '全不出现(净局)' }] },
		],
		validate: needValues,
		summary(p){ return `${p.mode === 'without' ? '避' : ''}格局:${(p.values || []).map((v)=>{ const hit = TAIYI_GEJU_KINDS.find((k)=>k.value === v); return hit ? hit.label.charAt(0) : v; }).join('/')}`; },
		evaluate(pan, p, ctx){
			const list = ctx.geju();
			const kinds = new Set(list.map((g)=>g.kind));
			const hit = (p.values || []).filter((v)=>kinds.has(v));
			const pass = p.mode === 'without' ? hit.length === 0 : hit.length > 0;
			return { pass, actual: `格局:${list.length ? list.map((g)=>g.name).join('、') : '无'}` };
		},
	},
	victory_side: {
		category: '格局',
		label: '主客胜负',
		defaults: { value: 'home' },
		fields: [
			{ key: 'value', kind: 'select', label: '利', options: [{ value: 'home', label: '利主(主胜)' }, { value: 'away', label: '利客(客胜)' }] },
		],
		summary(p){ return p.value === 'away' ? '利客' : '利主'; },
		evaluate(pan, p, ctx){
			const v = ctx.victory();
			const text = v ? `${v.summary || v.text || v.side || ''}` : '';
			const homeWin = /主(胜|勝|利|吉)/.test(text) || v === 'home' || (v && v.side === 'home');
			const awayWin = /客(胜|勝|利|吉)/.test(text) || v === 'away' || (v && v.side === 'away');
			const pass = p.value === 'away' ? awayWin : homeWin;
			return { pass, actual: `胜负:${text || '未判'}` };
		},
	},
	suan_range: {
		category: '算数',
		label: '主客算区间',
		defaults: { who: 'homeCal', min: 1, max: 40 },
		fields: [
			{ key: 'who', kind: 'select', label: '算', options: [{ value: 'homeCal', label: '主算' }, { value: 'awayCal', label: '客算' }, { value: 'setCal', label: '定算' }] },
			{ key: 'min', kind: 'number', label: '≥', min: 1, max: 40 },
			{ key: 'max', kind: 'number', label: '≤', min: 1, max: 40 },
		],
		summary(p){ return `${({ homeCal: '主', awayCal: '客', setCal: '定' })[p.who] || ''}算 ${p.min || 1}~${p.max || 40}`; },
		evaluate(pan, p){
			const v = Number(pan[p.who || 'homeCal']);
			const lo = Number(p.min) || 1;
			const hi = Number(p.max) || 40;
			return { pass: Number.isFinite(v) && v >= lo && v <= hi, actual: `主${pan.homeCal}·客${pan.awayCal}·定${pan.setCal}` };
		},
	},
	suan_parity: {
		category: '算数',
		label: '算数阴阳(奇偶)',
		defaults: { who: 'homeCal', value: 'odd' },
		fields: [
			{ key: 'who', kind: 'select', label: '算', options: [{ value: 'homeCal', label: '主算' }, { value: 'awayCal', label: '客算' }, { value: 'setCal', label: '定算' }] },
			{ key: 'value', kind: 'select', label: '取', options: [{ value: 'odd', label: '奇(阳数)' }, { value: 'even', label: '偶(阴数)' }] },
		],
		summary(p){ return `${({ homeCal: '主', awayCal: '客', setCal: '定' })[p.who] || ''}算${p.value === 'even' ? '偶' : '奇'}`; },
		evaluate(pan, p){
			const v = Number(pan[p.who || 'homeCal']);
			const isOdd = Number.isFinite(v) && v % 2 === 1;
			return { pass: p.value === 'even' ? !isOdd : isOdd, actual: `${({ homeCal: '主', awayCal: '客', setCal: '定' })[p.who] || ''}算=${v}` };
		},
	},
	dajiang_gong: {
		category: '大将',
		label: '主客大将宫',
		defaults: { who: 'homeGeneral', values: ['1'] },
		fields: [
			{ key: 'who', kind: 'select', label: '将', options: [{ value: 'homeGeneral', label: '主大将' }, { value: 'awayGeneral', label: '客大将' }, { value: 'setGeneral', label: '定大将' }, { value: 'homeVGen', label: '主参将' }, { value: 'awayVGen', label: '客参将' }, { value: 'setVGen', label: '定参将' }] },	// [W1] 参将三席=pan 现成数键,纯遗漏补齐
			{ key: 'values', kind: 'multiselect', label: '宫数(1-9)', options: opt(GONG9) },
		],
		validate: needValues,
		summary(p){ return `${({ homeGeneral: '主将', awayGeneral: '客将', setGeneral: '定将', homeVGen: '主参', awayVGen: '客参', setVGen: '定参' })[p.who] || ''}:${(p.values || []).join('/')}宫`; },
		evaluate(pan, p){
			const v = pan[p.who || 'homeGeneral'];
			return { pass: numIn(v, p.values), actual: `主将${pan.homeGeneral}·客将${pan.awayGeneral}·定将${pan.setGeneral || '?'}` };
		},
	},
	dajiang_same: {
		category: '大将',
		label: '将算同宫关系',
		defaults: { rel: 'zhu_ke_same' },
		fields: [
			{ key: 'rel', kind: 'select', label: '关系', options: [{ value: 'zhu_ke_same', label: '主客大将同宫' }, { value: 'zhu_taiyi_same', label: '主将同太乙(囚象)' }, { value: 'ke_taiyi_same', label: '客将同太乙' }] },
		],
		summary(p){ return ({ zhu_ke_same: '主客将同宫', zhu_taiyi_same: '主将同太乙', ke_taiyi_same: '客将同太乙' })[p.rel] || p.rel; },
		evaluate(pan, p){
			const tn = Number(pan.taiyiNum);
			let pass = false;
			if(p.rel === 'zhu_ke_same'){ pass = Number(pan.homeGeneral) === Number(pan.awayGeneral); }
			else if(p.rel === 'zhu_taiyi_same'){ pass = Number(pan.homeGeneral) === tn; }
			else{ pass = Number(pan.awayGeneral) === tn; }
			return { pass, actual: `主将${pan.homeGeneral}·客将${pan.awayGeneral}·太乙数${pan.taiyiNum}` };
		},
	},
	gong16_has: {
		category: '十六宫',
		label: '宫内布神',
		defaults: { board: 'gong16', gong: '子', names: [] },
		fields: [
			{ key: 'board', kind: 'select', label: '盘面', options: [{ value: 'gong16', label: '十六宫' }, { value: 'branch12', label: '十二支位' }], hint: 'buildPalaceMarks 同产两套布神,原仅暴露十六宫' },	// [W1] branch12 档
			{ key: 'gong', kind: 'select', label: '宫', options: opt(GONG16).map((o)=>({ ...o })) },
			{ key: 'names', kind: 'multiselect', label: '神名(空=宫内有任一神)', options: opt(['太乙', '文昌', '太岁', '合神', '计神', '始击', '定目', '君基', '臣基', '民基', '四神', '天乙', '地乙', '直符', '飞符', '主大', '主参', '客大', '客参', '五福', '帝符', '太尊', '飞鸟', '三风', '五风', '八风', '大游', '小游']) },	// buildPalaceMarks 28 神全集同源
		],
		summary(p){ return `${p.gong}宫${(p.names && p.names.length) ? `有${p.names.join('/')}` : '有神'}`; },
		evaluate(pan, p){
			const cells = (p.board === 'branch12')
				? (pan.branch12 || []).map((c)=>({ palace: c.branch, items: c.items }))
				: (pan.palace16 || pan.palaces || []);
			const cell = cells.find((c)=>c && c.palace === p.gong);
			const items = ((cell && cell.items) || []).map((it)=>`${it.name || it}`);
			let pass;
			if(p.names && p.names.length){
				pass = p.names.some((n)=>items.some((x)=>x.indexOf(n) >= 0));
			}else{
				pass = items.length > 0;
			}
			return { pass, actual: `${p.gong}宫:${items.join('、') || '空'}` };
		},
	},
	sanji_men: {
		category: '门户',
		label: '太乙所临(门/绝气)',
		defaults: { mode: 'men', values: [] },
		fields: [
			{ key: 'mode', kind: 'select', label: '判面', options: [{ value: 'men', label: '临门户宫(艮巽坤乾)' }, { value: 'zheng', label: '临正宫(子卯午酉)' }, { value: 'jian', label: '临间神宫(其余)' }] },
			{ key: 'values', kind: 'multiselect', label: '限定宫(空=该类任意)', options: opt(GONG16) },
		],
		summary(p){ return `太乙临${({ men: '门户', zheng: '正宫', jian: '间神' })[p.mode] || p.mode}${(p.values && p.values.length) ? `(${p.values.join('/')})` : ''}`; },
		evaluate(pan, p){
			const MEN = ['艮', '巽', '坤', '乾'];
			const ZHENG = ['子', '卯', '午', '酉'];
			const g = pan.taiyiPalace;
			let cls;
			if(MEN.includes(g)){ cls = 'men'; }
			else if(ZHENG.includes(g)){ cls = 'zheng'; }
			else{ cls = 'jian'; }
			const clsOk = cls === (p.mode || 'men');
			const gongOk = !(p.values && p.values.length) || p.values.includes(g);
			return { pass: clsOk && gongOk, actual: `太乙临${g || '?'}(${({ men: '门户', zheng: '正宫', jian: '间神' })[cls]})` };
		},
	},
	wenchang_taiyi_rel: {
		category: '格局',
		label: '文昌/始击与太乙位置关系',
		defaults: { who: 'skyeyes', rel: 'same' },
		fields: [
			{ key: 'who', kind: 'select', label: '谁', options: [{ value: 'skyeyes', label: '文昌' }, { value: 'sf', label: '始击' }] },
			{ key: 'rel', kind: 'select', label: '关系', options: [{ value: 'same', label: '同宫' }, { value: 'opposite', label: '对宫(环对冲)' }, { value: 'adjacent', label: '邻宫(掩迫象)' }] },
		],
		summary(p){ return `${p.who === 'sf' ? '始击' : '文昌'}${({ same: '同', opposite: '对', adjacent: '邻' })[p.rel] || ''}太乙`; },
		evaluate(pan, p){
			const who = p.who === 'sf' ? pan.sf : pan.skyeyes;
			const ty = pan.taiyiPalace;
			const i1 = GONG16.indexOf(who);
			const i2 = GONG16.indexOf(ty);
			let pass = false;
			if(i1 >= 0 && i2 >= 0){
				if(p.rel === 'same'){ pass = i1 === i2; }
				else if(p.rel === 'opposite'){ pass = Math.abs(i1 - i2) === 8; }
				else{ pass = Math.abs(i1 - i2) === 1 || Math.abs(i1 - i2) === 15; }
			}
			return { pass, actual: `${p.who === 'sf' ? '始击' : '文昌'}${who || '?'}·太乙${ty || '?'}` };
		},
	},
	shuli_kind: {
		category: '算数',
		label: '数理类(重阳重阴和数无门…)',
		defaults: { suan: 'home', kinds: ['重阳数'] },
		fields: [
			{ key: 'suan', kind: 'select', label: '算', options: [{ value: 'home', label: '主算' }, { value: 'away', label: '客算' }, { value: 'set', label: '定算' }] },
			{ key: 'kinds', kind: 'multiselect', label: '数理类(任一命中)', options: opt(['重阳数', '重阴数', '上和数', '次和数', '下和数', '无门', '无天', '长数', '无人', '无地', '阴中重阳', '阳中重阴', '不和', '平']), hint: '判定=太乙页断法面 computeTaiyiShuli 同函数;前缀匹配(「重阳数」不误中「阴中重阳」)' },
		],
		validate: (p)=>(!p.kinds || !p.kinds.length) ? '至少选择一项' : '',
		summary(p){ return `${({ home: '主算', away: '客算', set: '定算' })[p.suan] || '主算'}:${(p.kinds || []).join('/')}`; },
		evaluate(pan, p, ctx){
			const sl = ctx.shuli();
			const tags = (sl && sl[p.suan || 'home']) || [];
			// 前缀匹配:标签形如「重阳数(主火·亢旱)」「无门·主大灾」;「阴中重阳」含「重阳」子串,
			// 锚 indexOf===0 才不互相误中(shuliTone 同款坑,断法面注释在案)。
			const pass = (p.kinds || []).some((k)=>tags.some((t)=>String(t).indexOf(k) === 0));
			return { pass, actual: `${({ home: '主算', away: '客算', set: '定算' })[p.suan] || '主算'}数理:${tags.join('、') || '—'}` };
		},
	},
	ehui_has: {
		category: '算数',
		label: '厄会(重阳/重阴/无门厄)',
		defaults: { suan: 'any', kinds: ['重阳厄', '重阴厄', '无门厄'] },
		fields: [
			{ key: 'suan', kind: 'select', label: '限定算', options: [{ value: 'any', label: '任一算' }, { value: '主算', label: '主算' }, { value: '客算', label: '客算' }, { value: '定算', label: '定算' }] },
			{ key: 'kinds', kind: 'multiselect', label: '厄种(任一命中;配取反=避厄)', options: opt(['重阳厄', '重阴厄', '无门厄']), hint: '判定=断法面 computeEhui 同函数;择日避厄=本叶配「取反 NOT」' },
		],
		validate: (p)=>(!p.kinds || !p.kinds.length) ? '至少选择一项' : '',
		summary(p){ return `厄会:${p.suan === 'any' ? '' : `${p.suan}·`}${(p.kinds || []).join('/')}`; },
		evaluate(pan, p){
			let list = [];
			try{ list = computeEhui(pan) || []; }catch(e){ list = []; }
			const scoped = p.suan === 'any' || !p.suan ? list : list.filter((x)=>String(x).indexOf(p.suan) === 0);
			const pass = (p.kinds || []).some((k)=>scoped.some((x)=>String(x).indexOf(k) >= 0));
			return { pass, actual: `厄会:${list.join('、') || '无'}` };
		},
	},
	shijing_gong: {
		category: '落宫',
		label: '十精落位(二目八将三基)',
		defaults: { who: '文昌', values: ['巳'] },
		fields: [
			{ key: 'who', kind: 'select', label: '十精', options: opt(['文昌', '始击', '计神', '主大将', '主参将', '客大将', '客参将', '君基', '臣基', '民基']) },
			{ key: 'values', kind: 'multiselect', label: '落支(含中宫)', options: opt(GONG16.concat(['中'])) },
		],
		validate: needValues,
		summary(p){ return `${p.who || '文昌'}:${(p.values || []).join('/')}`; },
		evaluate(pan, p, ctx){
			// 今义十精=断法面 computeShiJing 同序;将席取 *Palace 支位(数席另有 dajiang_gong)。
			const KEYMAP = { 文昌: 'skyeyes', 始击: 'sf', 计神: 'jigod', 主大将: 'homeGeneralPalace', 主参将: 'homeVGenPalace', 客大将: 'awayGeneralPalace', 客参将: 'awayVGenPalace', 君基: 'kingbase', 臣基: 'officerbase', 民基: 'pplbase' };
			const v = pan[KEYMAP[p.who || '文昌']];
			const items = ctx.shijing() || [];
			const row = items.find((it)=>it.name === (p.who || '文昌'));
			return { pass: (p.values || []).includes(String(v || '')), actual: `${p.who || '文昌'}:${(row && row.at) || v || '—'}` };
		},
	},
	shensuan_kind: {
		category: '算数',
		label: '诸神之算(君臣民基/五福/始击)',
		defaults: { who: '君基算', kinds: ['上和数'] },
		fields: [
			{ key: 'who', kind: 'select', label: '算', options: opt(['君基算', '臣基算', '民基算', '五福算', '始击算']) },
			{ key: 'kinds', kind: 'multiselect', label: '数理类(任一命中)', options: opt(['重阳数', '重阴数', '上和数', '次和数', '下和数', '无门', '无天', '长数', '无人', '无地', '阴中重阳', '阳中重阴', '不和', '平']) },
		],
		validate: (p)=>(!p.kinds || !p.kinds.length) ? '至少选择一项' : '',
		summary(p){ return `${p.who || '君基算'}:${(p.kinds || []).join('/')}`; },
		evaluate(pan, p, ctx){
			const all = ctx.shensuan();
			const row = all && all[p.who || '君基算'];
			if(!row){ return { pass: false, actual: `${p.who || '君基算'}:该盘无此算` }; }
			const pass = (p.kinds || []).some((k)=>(row.tags || []).some((t)=>String(t).indexOf(k) === 0));
			return { pass, actual: `${p.who || '君基算'}=${row.value}(${(row.tags || []).join('、') || '平'})` };
		},
	},
	fenye_info: {
		category: '门户',
		label: '九州分野(卦/门/州/气)',
		defaults: { who: 'taiyi', dim: 'gua', values: ['乾'] },
		fields: [
			{ key: 'who', kind: 'select', label: '主体', options: [{ value: 'taiyi', label: '太乙' }, { value: 'shiji', label: '始击(正宫时)' }] },
			{ key: 'dim', kind: 'select', label: '判面', options: [{ value: 'gua', label: '卦' }, { value: 'men', label: '门' }, { value: 'zhou', label: '州' }, { value: 'qi', label: '气' }] },
			{ key: 'values', kind: 'multiselect', label: '取值(任一)', options: opt(['乾', '离', '艮', '震', '中', '兑', '坤', '坎', '巽', '天门', '火门', '鬼门', '日门', '中枢', '月门', '人门', '水门', '风门', '冀州', '荆州', '青州', '徐州', '中原', '雍州', '益州', '兖州', '扬州', '绝阳', '易气', '和', '绝气', '枢纽', '绝阴']), hint: '值域=TAIYI_GONG_INFO 九宫全表(卦8+中/门9/州9/气6);跨面选值不命中即判否' },
		],
		validate: needValues,
		summary(p){ return `${p.who === 'shiji' ? '始击' : '太乙'}分野·${({ gua: '卦', men: '门', zhou: '州', qi: '气' })[p.dim] || '卦'}:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			let fy = null;
			try{ fy = computeFenye(pan); }catch(e){ fy = null; }
			const row = fy && fy[p.who || 'taiyi'];
			if(!row){ return { pass: false, actual: `${p.who === 'shiji' ? '始击' : '太乙'}:非正宫,无分野` }; }
			const v = row[p.dim || 'gua'];
			return { pass: (p.values || []).includes(v), actual: `${p.who === 'shiji' ? '始击' : '太乙'}${row.gong}宫:${row.gua}卦·${row.men}·${row.zhou}·${row.qi}气` };
		},
	},
	sanyuan_wuziyuan: {
		category: '局式',
		label: '三元/五子元',
		defaults: { dim: 'sanyuan', sy: ['上元'], wz: ['甲子元'] },
		fields: [
			{ key: 'dim', kind: 'select', label: '判面', options: [{ value: 'sanyuan', label: '三元(纪元推)' }, { value: 'wuziyuan', label: '五子元(积年推)' }] },
			{ key: 'sy', kind: 'multiselect', label: '三元', options: opt(['上元', '中元', '下元']), showIf: (p)=>p.dim !== 'wuziyuan' },
			{ key: 'wz', kind: 'multiselect', label: '五子元', options: opt(['甲子元', '丙子元', '戊子元', '庚子元', '壬子元']), showIf: (p)=>p.dim === 'wuziyuan' },
		],
		validate: (p)=>((p.dim === 'wuziyuan' ? (p.wz || []) : (p.sy || [])).length ? '' : '至少选择一项'),
		summary(p){ return p.dim === 'wuziyuan' ? `五子元:${(p.wz || []).join('/')}` : `三元:${(p.sy || []).join('/')}`; },
		evaluate(pan, p){
			if(p.dim === 'wuziyuan'){
				let v = '';
				try{ v = computeWuziyuan(pan) || ''; }catch(e){ v = ''; }
				return { pass: !!v && (p.wz || []).includes(v), actual: `五子元:${v || '—'}(积${pan.accNum || '?'})` };
			}
			let v = '';
			try{ v = computeSanyuan(pan) || ''; }catch(e){ v = ''; }
			return { pass: !!v && (p.sy || []).includes(v), actual: `三元:${v || '—'}(${pan.jiyuan || '?'})` };
		},
	},
	nayin_taiyi: {
		category: '局式',
		label: '主柱纳音五行',
		defaults: { values: ['金'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '纳音五行(任一)', options: opt(['金', '木', '水', '火', '土']), hint: '主柱随计法(时计=时柱…);判定=概览面 computeTaiyiNayin 同函数' },
		],
		validate: needValues,
		summary(p){ return `纳音:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			let r = null;
			try{ r = computeTaiyiNayin(pan); }catch(e){ r = null; }
			if(!r){ return { pass: false, actual: '纳音:—' }; }
			return { pass: (p.values || []).includes(r.element), actual: `${r.pillar}柱${r.ganzhi}·${r.nayin}(${r.element})` };
		},
	},
	god_gong: {
		category: '落宫',
		label: '诸神落位(定目太岁基符…)',
		defaults: { who: 'se', values: ['子'] },
		fields: [
			{ key: 'who', kind: 'select', label: '神', options: [{ value: 'se', label: '定目' }, { value: 'taishui', label: '太岁' }, { value: 'kingbase', label: '君基' }, { value: 'officerbase', label: '臣基' }, { value: 'pplbase', label: '民基' }, { value: 'fgd', label: '四神' }, { value: 'skyyi', label: '天乙' }, { value: 'earthyi', label: '地乙' }, { value: 'zhifu', label: '直符' }, { value: 'flyfu', label: '飞符' }, { value: 'kingfu', label: '帝符' }, { value: 'taijun', label: '太尊' }, { value: 'flybird', label: '飞鸟' }] },
			{ key: 'values', kind: 'multiselect', label: '落支(含中宫)', options: opt(GONG16.concat(['中'])) },
		],
		validate: needValues,
		summary(p){ const L = { se: '定目', taishui: '太岁', kingbase: '君基', officerbase: '臣基', pplbase: '民基', fgd: '四神', skyyi: '天乙', earthyi: '地乙', zhifu: '直符', flyfu: '飞符', kingfu: '帝符', taijun: '太尊', flybird: '飞鸟' }; return `${L[p.who] || p.who}:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const L = { se: '定目', taishui: '太岁', kingbase: '君基', officerbase: '臣基', pplbase: '民基', fgd: '四神', skyyi: '天乙', earthyi: '地乙', zhifu: '直符', flyfu: '飞符', kingfu: '帝符', taijun: '太尊', flybird: '飞鸟' };
			const v = String(pan[p.who || 'se'] || '');
			return { pass: !!v && (p.values || []).includes(v), actual: `${L[p.who] || p.who}落${v || '—'}` };
		},
	},
};

// ── 树工厂/摘要/编译(与奇门/黄历/八字同构) ──
export function newTaiyiLeaf(type, joiner){
	const spec = TAIYI_CONDITION_TYPES[type];
	return {
		kind: 'leaf',
		type,
		negate: false,
		joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all',
		params: spec ? JSON.parse(JSON.stringify(spec.defaults)) : {},
	};
}
export function newTaiyiGroup(joiner){
	return { kind: 'group', negate: false, joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all', children: [] };
}

export function taiyiLeafSummary(leaf){
	const spec = leaf ? TAIYI_CONDITION_TYPES[leaf.type] : null;
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
		const spec = TAIYI_CONDITION_TYPES[node.type];
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
export function compileTaiyiTree(root){
	return compileSelf(root);
}
