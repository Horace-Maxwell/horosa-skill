// [Z4·紫微择日] 条件注册表(时辰粒度)。判定单源:盘=calcZiweiFromLite(与主紫微页
// calcZiwei 同一 buildChartFromBazi 组装体,主安星逻辑修正择日自动跟;golden 56 例+
// ziweiLocalParity 24 例 Java 网格看守)。星名值域同源 ziweiTables 表 keys(辅杂煞小)+
// 十四正曜/六吉六煞千年常量。spec 契约与 QIMEN/HUANGLI/BAZI/TAIYI 逐字段同构;
// ctx=makeZiweiZeriEvalCtx(chart)(星落宫索引惰性一次)。一键一行 Tab 缩进(preflight 键集契约)。
import {
	STARS_YEAR_GAN, STARS_YEAR_ZI, STARS_MONTH, STARS_TIME_ZI,
	LIFE_MASTER, BODY_MASTER,
} from '../../ziwei/data/ziweiTables.js';
import { GROUP_TYPES, JOINER_CN } from './conditionTypes.js';
// [W5 全谱轮] 格局=主页格局 tab 同函数(detectPatterns/ziweige 51 格);宫干四化=ZWConst 活表。
import { detectPatterns } from '../../ziwei/ziweiPatterns.js';
import GE_PATTERNS from '../../ziwei/data/tables/ziweige.json' with { type: 'json' };
import { getActiveSiHuaGan } from '../../bazi/ZWConst.js';

export { GROUP_TYPES, JOINER_CN };

export const ZHI12 = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
// 十四正曜/六吉/六煞:千年常量(与 ZiweiCalc MAIN14 同表;它未导出,此处为 UI 值域层)。
export const ZW_MAIN14 = ['紫微', '天机', '太阳', '武曲', '天同', '廉贞', '天府', '太阴', '贪狼', '巨门', '天相', '天梁', '七杀', '破军'];
export const ZW_LIUJI = ['左辅', '右弼', '文昌', '文曲', '天魁', '天钺'];
export const ZW_LIUSHA = ['擎羊', '陀罗', '火星', '铃星', '地空', '地劫'];
export const ZW_HOUSE_NAMES = ['命宫', '兄弟宫', '夫妻宫', '子女宫', '财帛宫', '疾厄宫', '迁移宫', '交友宫', '官禄宫', '田宅宫', '福德宫', '父母宫'];
export const CHANGSHENG12 = ['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养'];
// 全星清单(选项值域):正曜+年干系/年支系/月系/时系表 keys+火铃(表按年支嵌套,手列)。
const tableStars = (tbl)=>Object.keys(tbl || {});
export const ZW_ALL_STARS = Array.from(new Set([
	...ZW_MAIN14,
	...tableStars(STARS_YEAR_GAN), ...tableStars(STARS_YEAR_ZI), ...tableStars(STARS_MONTH), ...tableStars(STARS_TIME_ZI),
	'火星', '铃星',
]));
export const ZW_LIFE_MASTERS = Array.from(new Set(Object.values(LIFE_MASTER)));
export const ZW_BODY_MASTERS = Array.from(new Set(Object.values(BODY_MASTER)));
// 🔴 值域=zi_jian 基表实际取值(14 正曜机器穷举:庙旺地平闲陷,GRADES 序)。曾照九档
// 全谱抄「得/利/不」= 基表从不产出的死选项,同时漏掉盘上真出现的「闲/地」(审查实抓;
// 「得/利/不」只存在于《全书》显示层 delta,s.starlight 恒存基表值)。
const BRIGHT_LEVELS = ['庙', '旺', '地', '平', '闲', '陷'];
const ZHI_LIUHE = { 子: '丑', 丑: '子', 寅: '亥', 亥: '寅', 卯: '戌', 戌: '卯', 辰: '酉', 酉: '辰', 巳: '申', 申: '巳', 午: '未', 未: '午' };
const SANHE_GROUPS = [['申', '子', '辰'], ['亥', '卯', '未'], ['寅', '午', '戌'], ['巳', '酉', '丑']];

const opt = (arr)=>arr.map((v)=>({ value: v, label: v }));
const needValues = (p)=>(!p.values || !p.values.length) ? '至少选择一项' : '';

// 惰性求值上下文:星落宫索引(全六层星组一遍)+宫名索引。
export function makeZiweiZeriEvalCtx(chart, natal){
	let starMap = null;
	let gongMap = null;
	const build = ()=>{
		starMap = {};
		gongMap = {};
		(chart.houses || []).forEach((h, i)=>{
			if(h && h.name){ gongMap[h.name.replace('宫', '')] = i; }
			['starsMain', 'starsAssist', 'starsEvil', 'starsOthersGood', 'starsOthersBad', 'starsSmall'].forEach((f)=>{
				(h && h[f] ? h[f] : []).forEach((s)=>{
					const nm = s && s.name;
					if(!nm){ return; }
					(starMap[nm] = starMap[nm] || []).push({ idx: i, sihua: s.sihua || '', light: s.starlight || '' });
				});
			});
		});
	};
	let geju;
	return {
		natal: natal || null,
		stars(){ if(!starMap){ build(); } return starMap; },
		// [W5] 格局惰性一次(主页格局 tab 同函数;异常兜空)
		geju(){
			if(geju === undefined){
				try{ geju = detectPatterns(chart) || []; }catch(e){ geju = []; }
			}
			return geju;
		},
		gongIdx(name){ if(!gongMap){ build(); } const k = `${name || ''}`.replace('宫', ''); return gongMap[k] !== undefined ? gongMap[k] : -1; },
		sanfang(idx){ return [idx, (idx + 4) % 12, (idx + 8) % 12, (idx + 6) % 12]; },
	};
}

const houseOf = (chart, idx)=>(chart.houses && chart.houses[idx]) || null;
const mainNamesAt = (chart, idx)=>{
	const h = houseOf(chart, idx);
	return h ? (h.starsMain || []).map((s)=>s.name) : [];
};
const starIdxList = (ctx, name)=>(ctx.stars()[name] || []).map((e)=>e.idx);
const gongNameAt = (chart, idx)=>{
	const h = houseOf(chart, idx);
	return (h && h.name) || '?';
};

// [十四轮] keyDeps 合同(全家统一「树不涉之面不劈行」):值域=安星六位
// ['yearGan','yearZi','anchorM','anchorLeap','anchorD','timeZi']。紫微安星链几乎全类吃
// 全元组(命宫=f(月,时)、紫微落宫=f(局,日)、星布局=f(全部)),故绝大多数类=显式全位;
// 收益类=年干四化族(sihua_star/bm_ji_bu_chong 只吃 yearGan → 该树行=整年粒度)。
// sihua_in_gong/dui_ming 吃四化星落宫=全位。缺 keyDeps=掩码回退全位+完备闸红。

export const ZIWEI_CONDITION_TYPES = {
	wuxing_ju: {
		category: '局式',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '五行局',
		defaults: { values: ['3'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '局', options: [{ value: '2', label: '水二局' }, { value: '3', label: '木三局' }, { value: '4', label: '金四局' }, { value: '5', label: '土五局' }, { value: '6', label: '火六局' }] },
		],
		validate: needValues,
		summary(p){ return `五行局:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			return { pass: (p.values || []).map(Number).includes(Number(pan.wuxingJu)), actual: `${pan.wuxingJuText || pan.wuxingJu || '?'}` };
		},
	},
	ming_gong_zhi: {
		category: '命身',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '命宫地支',
		defaults: { values: ['子'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '支', options: opt(ZHI12) },
		],
		validate: needValues,
		summary(p){ return `命宫:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const z = ZHI12[pan.lifeHouseIndex];
			return { pass: (p.values || []).includes(z), actual: `命宫在${z}(${gongNameAt(pan, pan.lifeHouseIndex)})` };
		},
	},
	ming_zhu_xing: {
		category: '命身',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '命宫正曜',
		defaults: { mode: 'has', values: ['紫微'] },
		fields: [
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'has', label: '含任一' }, { value: 'empty', label: '空宫(无正曜)' }] },
			{ key: 'values', kind: 'multiselect', label: '正曜', options: opt(ZW_MAIN14) },
		],
		validate: (p)=>(p.mode === 'empty' ? '' : needValues(p)),
		summary(p){ return p.mode === 'empty' ? '命宫空宫' : `命宫有:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const names = mainNamesAt(pan, pan.lifeHouseIndex);
			const pass = p.mode === 'empty' ? names.length === 0 : (p.values || []).some((v)=>names.includes(v));
			return { pass, actual: `命宫正曜:${names.join('、') || '空'}` };
		},
	},
	shen_zhu_xing: {
		category: '命身',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '身宫正曜',
		defaults: { mode: 'has', values: ['天府'] },
		fields: [
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'has', label: '含任一' }, { value: 'empty', label: '空宫(无正曜)' }] },
			{ key: 'values', kind: 'multiselect', label: '正曜', options: opt(ZW_MAIN14) },
		],
		validate: (p)=>(p.mode === 'empty' ? '' : needValues(p)),
		summary(p){ return p.mode === 'empty' ? '身宫空宫' : `身宫有:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const names = mainNamesAt(pan, pan.bodyHouseIndex);
			const pass = p.mode === 'empty' ? names.length === 0 : (p.values || []).some((v)=>names.includes(v));
			return { pass, actual: `身宫(${ZHI12[pan.bodyHouseIndex]})正曜:${names.join('、') || '空'}` };
		},
	},
	ming_changsheng: {
		category: '命身',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '命宫长生态',
		defaults: { values: ['长生', '帝旺', '临官'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '态', options: opt(CHANGSHENG12) },
		],
		validate: needValues,
		summary(p){ return `命宫长生:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const h = houseOf(pan, pan.lifeHouseIndex);
			const ph = (h && h.phase) || '?';
			return { pass: (p.values || []).includes(ph), actual: `命宫十二长生:${ph}` };
		},
	},
	star_in_gong: {
		category: '安星',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '星落宫名',
		defaults: { star: '紫微', gongs: ['官禄宫'] },
		fields: [
			{ key: 'star', kind: 'select', label: '星', options: opt(ZW_ALL_STARS) },
			{ key: 'gongs', kind: 'multiselect', label: '宫名', options: opt(ZW_HOUSE_NAMES) },
		],
		validate: (p)=>((!p.gongs || !p.gongs.length) ? '至少选择一宫' : ''),
		summary(p){ return `${p.star}在${(p.gongs || []).join('/')}`; },
		evaluate(pan, p, ctx){
			const idxs = starIdxList(ctx, p.star);
			const names = idxs.map((i)=>gongNameAt(pan, i));
			const want = (p.gongs || []).map((g)=>`${g}`.replace('宫', ''));
			const pass = names.some((n)=>want.includes(`${n}`.replace('宫', '')));
			return { pass, actual: `${p.star}落${names.join('、') || '(未安)'}` };
		},
	},
	star_in_zhi: {
		category: '安星',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '星落地支',
		defaults: { star: '紫微', values: ['午'] },
		fields: [
			{ key: 'star', kind: 'select', label: '星', options: opt(ZW_ALL_STARS) },
			{ key: 'values', kind: 'multiselect', label: '支', options: opt(ZHI12) },
		],
		validate: needValues,
		summary(p){ return `${p.star}在${(p.values || []).join('/')}`; },
		evaluate(pan, p, ctx){
			const idxs = starIdxList(ctx, p.star);
			const zhis = idxs.map((i)=>ZHI12[i]);
			const pass = zhis.some((z)=>(p.values || []).includes(z));
			return { pass, actual: `${p.star}落${zhis.join('、') || '(未安)'}` };
		},
	},
	star_tong_gong: {
		category: '安星',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '两星同宫',
		defaults: { starA: '禄存', starB: '天马' },
		fields: [
			{ key: 'starA', kind: 'select', label: '星A', options: opt(ZW_ALL_STARS) },
			{ key: 'starB', kind: 'select', label: '星B', options: opt(ZW_ALL_STARS) },
		],
		summary(p){ return `${p.starA}同宫${p.starB}`; },
		evaluate(pan, p, ctx){
			const a = starIdxList(ctx, p.starA);
			const b = new Set(starIdxList(ctx, p.starB));
			const hit = a.filter((i)=>b.has(i));
			return { pass: hit.length > 0, actual: hit.length ? `${p.starA}·${p.starB}同在${hit.map((i)=>ZHI12[i]).join('、')}` : `${p.starA}(${a.map((i)=>ZHI12[i]).join(',') || '未安'})·${p.starB}(${[...b].map((i)=>ZHI12[i]).join(',') || '未安'})不同宫` };
		},
	},
	sihua_star: {
		category: '四化',
		keyDeps: ['yearGan'],
		label: '生年四化为星',
		defaults: { hua: '禄', values: ['武曲'] },
		fields: [
			{ key: 'hua', kind: 'select', label: '化', options: opt(['禄', '权', '科', '忌']) },
			{ key: 'values', kind: 'multiselect', label: '星', options: opt(ZW_MAIN14.concat(['左辅', '右弼', '文昌', '文曲'])) },
		],
		validate: needValues,
		summary(p){ return `化${p.hua}=${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const s = (pan.birthSihua || {})[p.hua] || '';
			return { pass: (p.values || []).includes(s), actual: `生年化${p.hua}:${s || '?'}` };
		},
	},
	sihua_in_gong: {
		category: '四化',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '生年四化入宫',
		defaults: { hua: '禄', gongs: ['财帛宫'] },
		fields: [
			{ key: 'hua', kind: 'select', label: '化', options: opt(['禄', '权', '科', '忌']) },
			{ key: 'gongs', kind: 'multiselect', label: '宫名', options: opt(ZW_HOUSE_NAMES) },
		],
		validate: (p)=>((!p.gongs || !p.gongs.length) ? '至少选择一宫' : ''),
		summary(p){ return `化${p.hua}入${(p.gongs || []).join('/')}`; },
		evaluate(pan, p, ctx){
			const s = (pan.birthSihua || {})[p.hua] || '';
			const idxs = starIdxList(ctx, s);
			const names = idxs.map((i)=>gongNameAt(pan, i));
			const want = (p.gongs || []).map((g)=>`${g}`.replace('宫', ''));
			const pass = names.some((n)=>want.includes(`${n}`.replace('宫', '')));
			return { pass, actual: `化${p.hua}(${s || '?'})落${names.join('、') || '?'}` };
		},
	},
	sihua_dui_ming: {
		category: '四化',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '四化会命宫(同宫/对照)',
		defaults: { hua: '忌', rel: 'not_in' },
		fields: [
			{ key: 'hua', kind: 'select', label: '化', options: opt(['禄', '权', '科', '忌']) },
			{ key: 'rel', kind: 'select', label: '关系', options: [{ value: 'in', label: '坐命宫' }, { value: 'opposite', label: '对照(迁移位)' }, { value: 'not_in', label: '不坐命不对照(避)' }] },
		],
		summary(p){ return `化${p.hua}${({ in: '坐命', opposite: '照命', not_in: '不犯命' })[p.rel] || p.rel}`; },
		evaluate(pan, p, ctx){
			const s = (pan.birthSihua || {})[p.hua] || '';
			const idxs = new Set(starIdxList(ctx, s));
			const life = pan.lifeHouseIndex;
			const opp = (life + 6) % 12;
			const inLife = idxs.has(life);
			const inOpp = idxs.has(opp);
			let pass;
			if(p.rel === 'in'){ pass = inLife; }
			else if(p.rel === 'opposite'){ pass = inOpp; }
			else{ pass = !inLife && !inOpp; }
			return { pass, actual: `化${p.hua}(${s})落${[...idxs].map((i)=>ZHI12[i]).join('、') || '?'};命宫${ZHI12[life]}` };
		},
	},
	star_brightness: {
		category: '亮度',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '星曜亮度',
		defaults: { star: '紫微', values: ['庙', '旺'] },
		fields: [
			{ key: 'star', kind: 'select', label: '星', options: opt([...ZW_MAIN14, '左辅', '右弼', '文昌', '文曲', '天魁', '天钺', '禄存', '天马', '擎羊', '陀罗', '火星', '铃星', '地空', '地劫']), hint2: '' },	// [W5] 扩六吉六煞禄马空劫(亮度基表有值面)
			{ key: 'values', kind: 'multiselect', label: '亮度(庙旺地平闲陷)', options: opt(BRIGHT_LEVELS), hint: '基础亮度(中州基表口径,主页默认盘同源;《全书》亮度源为显示层覆盖,不入扫描)' },
		],
		validate: needValues,
		summary(p){ return `${p.star}${(p.values || []).join('/')}`; },
		evaluate(pan, p, ctx){
			const list = ctx.stars()[p.star] || [];
			const lights = list.map((e)=>e.light).filter(Boolean);
			const pass = lights.some((l)=>(p.values || []).includes(l));
			return { pass, actual: `${p.star}亮度:${lights.join('、') || '(无值)'}` };
		},
	},
	life_master: {
		category: '主宰',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '命主',
		defaults: { values: ['贪狼'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '星', options: opt(ZW_LIFE_MASTERS) },
		],
		validate: needValues,
		summary(p){ return `命主:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			return { pass: (p.values || []).includes(pan.lifeMaster), actual: `命主:${pan.lifeMaster || '?'}` };
		},
	},
	body_master: {
		category: '主宰',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '身主',
		defaults: { values: ['文昌'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '星', options: opt(ZW_BODY_MASTERS) },
		],
		validate: needValues,
		summary(p){ return `身主:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			return { pass: (p.values || []).includes(pan.bodyMaster), actual: `身主:${pan.bodyMaster || '?'}` };
		},
	},
	doujun_zhi: {
		category: '主宰',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '斗君落支',
		defaults: { values: ['寅'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '支', options: opt(ZHI12) },
		],
		validate: needValues,
		summary(p){ return `斗君:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			return { pass: (p.values || []).includes(pan.doujun), actual: `斗君在${pan.doujun || '?'}` };
		},
	},
	sanfang_has: {
		category: '会照',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '宫三方四正会星',
		defaults: { gong: '命宫', stars: ['左辅', '右弼'], mode: 'all' },
		fields: [
			{ key: 'gong', kind: 'select', label: '本宫', options: opt(ZW_HOUSE_NAMES) },
			{ key: 'stars', kind: 'multiselect', label: '星集', options: opt(ZW_ALL_STARS) },
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'all', label: '会齐全部' }, { value: 'any', label: '会任一' }, { value: 'none', label: '全不会(避)' }] },
		],
		validate: (p)=>((!p.stars || !p.stars.length) ? '至少选择一星' : ''),
		summary(p){ return `${p.gong}三方${({ all: '会齐', any: '会', none: '不会' })[p.mode] || ''}${(p.stars || []).join('/')}`; },
		evaluate(pan, p, ctx){
			const base = ctx.gongIdx(p.gong);
			if(base < 0){ return { pass: false, actual: `${p.gong}未定位` }; }
			const zone = new Set(ctx.sanfang(base));
			const hit = (p.stars || []).filter((st)=>starIdxList(ctx, st).some((i)=>zone.has(i)));
			let pass;
			if(p.mode === 'any'){ pass = hit.length > 0; }
			else if(p.mode === 'none'){ pass = hit.length === 0; }
			else{ pass = hit.length === (p.stars || []).length; }
			return { pass, actual: `${p.gong}三方四正会:${hit.join('、') || '无'}` };
		},
	},
	liuji_count: {
		category: '会照',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '三方四正六吉数',
		defaults: { gong: '命宫', min: 2 },
		fields: [
			{ key: 'gong', kind: 'select', label: '本宫', options: opt(ZW_HOUSE_NAMES) },
			{ key: 'min', kind: 'number', label: '≥颗', min: 0, max: 6 },
		],
		summary(p){ return `${p.gong}三方六吉≥${p.min}`; },
		evaluate(pan, p, ctx){
			const base = ctx.gongIdx(p.gong);
			if(base < 0){ return { pass: false, actual: `${p.gong}未定位` }; }
			const zone = new Set(ctx.sanfang(base));
			const hit = ZW_LIUJI.filter((st)=>starIdxList(ctx, st).some((i)=>zone.has(i)));
			return { pass: hit.length >= (Number(p.min) || 0), actual: `${p.gong}三方六吉:${hit.join('、') || '无'}(${hit.length}颗)` };
		},
	},
	liusha_count: {
		category: '会照',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '三方四正六煞数',
		defaults: { gong: '命宫', max: 1 },
		fields: [
			{ key: 'gong', kind: 'select', label: '本宫', options: opt(ZW_HOUSE_NAMES) },
			{ key: 'max', kind: 'number', label: '≤颗', min: 0, max: 6 },
		],
		summary(p){ return `${p.gong}三方六煞≤${p.max}`; },
		evaluate(pan, p, ctx){
			const base = ctx.gongIdx(p.gong);
			if(base < 0){ return { pass: false, actual: `${p.gong}未定位` }; }
			const zone = new Set(ctx.sanfang(base));
			const hit = ZW_LIUSHA.filter((st)=>starIdxList(ctx, st).some((i)=>zone.has(i)));
			return { pass: hit.length <= (Number(p.max) === 0 ? 0 : (Number(p.max) || 6)), actual: `${p.gong}三方六煞:${hit.join('、') || '无'}(${hit.length}颗)` };
		},
	},
	kong_jie_ming: {
		category: '会照',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '空劫犯命',
		defaults: { rel: 'avoid' },
		fields: [
			{ key: 'rel', kind: 'select', label: '判法', options: [{ value: 'avoid', label: '空劫不坐命不照命(避)' }, { value: 'tong', label: '空劫坐命宫' }, { value: 'hui', label: '空劫会命(三方四正)' }] },
		],
		summary(p){ return ({ avoid: '空劫不犯命', tong: '空劫坐命', hui: '空劫会命' })[p.rel] || p.rel; },
		evaluate(pan, p, ctx){
			const life = pan.lifeHouseIndex;
			const zone = new Set(ctx.sanfang(life));
			// 🔴 空劫真身按盘自判(勿硬列天空):modern 档时系空星名「地空」、年支杂曜
			// 「天空」恒在盘上另有其星——硬含天空=把无辜年支天空当空劫(审查实抓,
			// 默认档 ~1/3 时刻误判)。book 档时系星改名「天空」且年支天空已移除:
			// 盘上有「地空」⇔ modern(时系星必落宫,恒真),无 ⇔ book。
			const kj = starIdxList(ctx, '地空').length ? ['地空', '地劫'] : ['天空', '地劫'];
			const at = kj.flatMap((st)=>starIdxList(ctx, st));
			const inLife = at.includes(life);
			const inZone = at.some((i)=>zone.has(i));
			let pass;
			if(p.rel === 'tong'){ pass = inLife; }
			else if(p.rel === 'hui'){ pass = inZone; }
			else{ pass = !inZone; }
			return { pass, actual: `空劫落:${at.map((i)=>ZHI12[i]).join('、') || '无'};命宫${ZHI12[life]}` };
		},
	},
	bm_ji_bu_chong: {
		category: '本命',
		keyDeps: ['yearGan'],
		label: '年忌不犯本命命宫',
		defaults: {},
		fields: [],
		summary(){ return '候选年忌不坐/不冲本命命宫'; },
		evaluate(pan, p, ctx){
			const n = ctx.natal;
			if(!n || !n.mingZhi){ return { pass: false, actual: '未设用事人本命(命宫地支)' }; }
			const ji = (pan.birthSihua || {})['忌'] || '';
			const idxs = starIdxList(ctx, ji).map((i)=>ZHI12[i]);
			const chong = ZHI12[(ZHI12.indexOf(n.mingZhi) + 6) % 12];
			const bad = idxs.includes(n.mingZhi) || idxs.includes(chong);
			return { pass: !bad, actual: `候选年忌(${ji})落${idxs.join('、') || '?'};本命命宫${n.mingZhi}(冲${chong})` };
		},
	},
	bm_ming_he: {
		category: '本命',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '候选命宫合本命命宫',
		defaults: { rel: 'any_he' },
		fields: [
			{ key: 'rel', kind: 'select', label: '关系', options: [{ value: 'any_he', label: '六合或三合' }, { value: 'liuhe', label: '六合' }, { value: 'sanhe', label: '三合' }, { value: 'same', label: '同支' }] },
		],
		summary(p){ return `候选命宫${({ any_he: '合', liuhe: '六合', sanhe: '三合', same: '同' })[p.rel] || ''}本命命宫`; },
		evaluate(pan, p, ctx){
			const n = ctx.natal;
			if(!n || !n.mingZhi){ return { pass: false, actual: '未设用事人本命(命宫地支)' }; }
			const cz = ZHI12[pan.lifeHouseIndex];
			const liuhe = ZHI_LIUHE[cz] === n.mingZhi;
			const sanhe = SANHE_GROUPS.some((g)=>g.includes(cz) && g.includes(n.mingZhi)) && cz !== n.mingZhi;
			const same = cz === n.mingZhi;
			let pass;
			if(p.rel === 'liuhe'){ pass = liuhe; }
			else if(p.rel === 'sanhe'){ pass = sanhe; }
			else if(p.rel === 'same'){ pass = same; }
			else{ pass = liuhe || sanhe; }
			return { pass, actual: `候选命宫${cz}·本命命宫${n.mingZhi}(${liuhe ? '六合' : sanhe ? '三合' : same ? '同支' : '无合'})` };
		},
	},
	geju_hit: {
		category: '格局',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '格局命中(51 格)',
		defaults: { mode: 'with', broken: 'any', values: ['紫府同宫'] },
		fields: [
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'with', label: '命中任一' }, { value: 'without', label: '全不命中(避格)' }] },
			{ key: 'broken', kind: 'select', label: '破格档', options: [{ value: 'any', label: '不论破格' }, { value: 'intact', label: '仅算不破之格' }, { value: 'broken', label: '仅算已破之格' }], showIf: (p)=>p.mode !== 'without' },
			{ key: 'values', kind: 'multiselect', label: '格局(任一)', options: Object.keys(GE_PATTERNS).map((n)=>({ value: n, label: n })), hint: '判定=主页格局 tab detectPatterns 同函数(ziweige 全表);破格档按 broken 字段过滤' },
		],
		validate: needValues,
		summary(p){ return `${p.mode === 'without' ? '避' : ''}格局:${(p.values || []).slice(0, 3).join('/')}${(p.values || []).length > 3 ? '…' : ''}${p.mode !== 'without' && p.broken === 'intact' ? '(不破)' : (p.mode !== 'without' && p.broken === 'broken' ? '(已破)' : '')}`; },
		evaluate(pan, p, ctx){
			const all = ctx.geju();
			const scoped = p.mode === 'without' || p.broken === 'any' || !p.broken
				? all
				: all.filter((g)=>(p.broken === 'broken' ? g.broken : !g.broken));
			const names = new Set(scoped.map((g)=>g.name));
			const got = (p.values || []).filter((v)=>names.has(v));
			const pass = p.mode === 'without' ? got.length === 0 : got.length > 0;
			return { pass, actual: `格局:${all.length ? all.map((g)=>`${g.name}${g.broken ? '(破)' : ''}`).join('、') : '无'}` };
		},
	},
	gong_gan_sihua: {
		category: '四化',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '宫干四化(飞化/自化)',
		defaults: { gong: '命宫', hua: '禄', mode: 'self' },
		fields: [
			{ key: 'gong', kind: 'select', label: '宫', options: opt(['命宫', '兄弟', '夫妻', '子女', '财帛', '疾厄', '迁移', '交友', '官禄', '田宅', '福德', '父母']) },
			{ key: 'hua', kind: 'select', label: '四化', options: opt(['禄', '权', '科', '忌']) },
			{ key: 'mode', kind: 'select', label: '判面', options: [{ value: 'self', label: '自化(化星在本宫)' }, { value: 'to_ming', label: '飞入命宫' }], hint: '按该宫宫干起四化(活流派表 getActiveSiHuaGan——切四化流派自动跟随)' },
		],
		summary(p){ return `${p.gong}干化${p.hua}${p.mode === 'to_ming' ? '入命' : '自化'}`; },
		evaluate(pan, p, ctx){
			const gi = ctx.gongIdx(p.gong || '命宫');
			if(gi < 0){ return { pass: false, actual: `${p.gong}:未找到` }; }
			const h = (pan.houses || [])[gi];
			const gan = `${(h && h.ganzi) || ''}`.charAt(0);
			let table = null;
			try{ table = getActiveSiHuaGan(); }catch(e){ table = null; }
			const row = table && table[gan];
			const star = row ? row[({ 禄: 0, 权: 1, 科: 2, 忌: 3 })[p.hua || '禄']] : '';
			if(!star){ return { pass: false, actual: `${p.gong}干${gan || '?'}:四化表缺` }; }
			const list = ctx.stars()[star] || [];
			const target = p.mode === 'to_ming' ? (pan.lifeHouseIndex !== undefined ? pan.lifeHouseIndex : -1) : gi;
			const pass = list.some((e)=>e.idx === target);
			return { pass, actual: `${p.gong}干${gan}化${p.hua}=${star}(落${list.map((e)=>gongNameAt(pan, e.idx)).join('/') || '?'})` };
		},
	},
	shen_gong_pos: {
		category: '命身',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '身宫落位(宫名/地支)',
		defaults: { values: ['迁移'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '落位(宫名或地支,任一)', options: [...opt(['命宫', '夫妻', '财帛', '迁移', '官禄', '福德']), ...opt(ZHI12)], hint: '身宫只落六宫之一(千年结构);地支档判身宫干支' },
		],
		validate: needValues,
		summary(p){ return `身宫:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const bi = pan.bodyHouseIndex;
			if(bi === undefined || bi < 0){ return { pass: false, actual: '身宫:—' }; }
			const h = (pan.houses || [])[bi] || {};
			const nm = `${h.name || ''}`.replace('宫', '');
			const zhi = `${h.ganzi || ''}`.charAt(1);
			const pass = (p.values || []).some((v)=>{
				const vv = `${v}`.replace('宫', '');
				return vv === nm || v === zhi;
			});
			return { pass, actual: `身宫=${h.name || '?'}(${h.ganzi || '?'})` };
		},
	},
	gong_changsheng: {
		category: '命身',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '任意宫长生态',
		defaults: { gong: '命宫', phases: ['长生', '帝旺'] },
		fields: [
			{ key: 'gong', kind: 'select', label: '宫', options: opt(['命宫', '兄弟', '夫妻', '子女', '财帛', '疾厄', '迁移', '交友', '官禄', '田宅', '福德', '父母']) },
			{ key: 'phases', kind: 'multiselect', label: '长生态(任一)', options: opt(['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养']), hint: '宫 phase=五行局长生环(houses[i].phase);既有 ming_changsheng 只判命宫' },
		],
		validate: (p)=>(!p.phases || !p.phases.length) ? '至少选择一项' : '',
		summary(p){ return `${p.gong}:${(p.phases || []).join('/')}`; },
		evaluate(pan, p, ctx){
			const gi = ctx.gongIdx(p.gong || '命宫');
			const h = gi >= 0 ? (pan.houses || [])[gi] : null;
			const ph = (h && h.phase) || '';
			return { pass: !!ph && (p.phases || []).includes(ph), actual: `${p.gong}=${ph || '—'}` };
		},
	},
	laiyin_gong: {
		category: '四化',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '来因宫(生年干落宫)',
		defaults: { values: ['命宫'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '来因宫(任一)', options: opt(['命宫', '兄弟', '夫妻', '子女', '财帛', '疾厄', '迁移', '交友', '官禄', '田宅', '福德', '父母']), hint: '宫干=生年干的宫(千年定义;candidate 年干×宫干匹配)' },
		],
		validate: needValues,
		summary(p){ return `来因:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const yg = pan.yearGan || '';
			if(!yg){ return { pass: false, actual: '来因:—(无年干)' }; }
			const hit = (pan.houses || []).map((h, i)=>({ h, i })).filter((x)=>`${(x.h && x.h.ganzi) || ''}`.charAt(0) === yg);
			const names = hit.map((x)=>`${x.h.name || ''}`.replace('宫', ''));
			const pass = (p.values || []).some((v)=>names.includes(`${v}`.replace('宫', '')));
			return { pass, actual: `来因宫:${names.join('/') || '—'}(年干${yg})` };
		},
	},
	gong_empty: {
		category: '安星',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '任意宫空宫(无主星)',
		defaults: { gong: '命宫', want: 'empty' },
		fields: [
			{ key: 'gong', kind: 'select', label: '宫', options: opt(['命宫', '兄弟', '夫妻', '子女', '财帛', '疾厄', '迁移', '交友', '官禄', '田宅', '福德', '父母']) },
			{ key: 'want', kind: 'select', label: '判态', options: [{ value: 'empty', label: '空宫(无十四正曜)' }, { value: 'filled', label: '有正曜' }] },
		],
		summary(p){ return `${p.gong}${p.want === 'filled' ? '有正曜' : '空宫'}`; },
		evaluate(pan, p, ctx){
			const gi = ctx.gongIdx(p.gong || '命宫');
			const h = gi >= 0 ? (pan.houses || [])[gi] : null;
			const n = h ? (h.starsMain || []).length : -1;
			if(n < 0){ return { pass: false, actual: `${p.gong}:未找到` }; }
			const pass = p.want === 'filled' ? n > 0 : n === 0;
			return { pass, actual: `${p.gong}正曜${n}枚` };
		},
	},
	gong_zhi_name: {
		category: '安星',
		keyDeps: ['yearGan', 'yearZi', 'anchorM', 'anchorLeap', 'anchorD', 'timeZi'],
		label: '宫名落地支',
		defaults: { gong: '财帛', values: ['寅'] },
		fields: [
			{ key: 'gong', kind: 'select', label: '宫', options: opt(['命宫', '兄弟', '夫妻', '子女', '财帛', '疾厄', '迁移', '交友', '官禄', '田宅', '福德', '父母']) },
			{ key: 'values', kind: 'multiselect', label: '地支(任一)', options: opt(ZHI12), hint: '「财帛宫在寅」类;既有类只能从星出发' },
		],
		validate: needValues,
		summary(p){ return `${p.gong}在${(p.values || []).join('/')}`; },
		evaluate(pan, p, ctx){
			const gi = ctx.gongIdx(p.gong || '财帛');
			const h = gi >= 0 ? (pan.houses || [])[gi] : null;
			const zhi = `${(h && h.ganzi) || ''}`.charAt(1);
			return { pass: !!zhi && (p.values || []).includes(zhi), actual: `${p.gong}在${zhi || '?'}(${(h && h.ganzi) || '?'})` };
		},
	},
};

// ── 树工厂/摘要/编译(与奇门/黄历/八字/太乙同构) ──
export function newZiweiLeaf(type, joiner){
	const spec = ZIWEI_CONDITION_TYPES[type];
	return {
		kind: 'leaf',
		type,
		negate: false,
		joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all',
		params: spec ? JSON.parse(JSON.stringify(spec.defaults)) : {},
	};
}
export function newZiweiGroup(joiner){
	return { kind: 'group', negate: false, joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all', children: [] };
}

export function ziweiLeafSummary(leaf){
	const spec = leaf ? ZIWEI_CONDITION_TYPES[leaf.type] : null;
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
		const spec = ZIWEI_CONDITION_TYPES[node.type];
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
export function compileZiweiTree(root){
	return compileSelf(root);
}
