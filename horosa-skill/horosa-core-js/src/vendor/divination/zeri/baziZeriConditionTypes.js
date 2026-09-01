// [Z2·八字择日] 条件注册表(时辰粒度)。判定单源:四柱=buildLocalNongliLite(八字主盘同引擎)、
// 神煞=calcFourPillarShenSha(八字页神煞面同函数)——主八字算法/神煞表修正,择日自动跟(制度层1)。
// spec 契约与 QIMEN/HUANGLI 逐字段同构:{category,label,defaults,fields[],validate,summary,
// evaluate(pan,params,ctx)→{pass,actual}};ctx=makeBaziZeriEvalCtx(pan,natal)(神煞惰性)。
// 本命上下文(用户定案13):natal 选填,选了才解锁「本命」组三类,未填时该组 evaluate 判假+
// actual 提示(工作台侧置灰另有防线)。一键一行 Tab 缩进(preflight 键集契约)。
import { calcFourPillarShenSha } from '../../bazi/baziShenShaLocal.js';
import { changShengOf, xunKongOf } from '../../bazi/baziLunarLocal.js';
import { GROUP_TYPES, JOINER_CN } from './conditionTypes.js';

export { GROUP_TYPES, JOINER_CN };

const GAN10 = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const ZHI12 = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const WUXING5 = ['金', '木', '水', '火', '土'];
const GAN_WX = { 甲: '木', 乙: '木', 丙: '火', 丁: '火', 戊: '土', 己: '土', 庚: '金', 辛: '金', 壬: '水', 癸: '水' };
const ZHI_WX = { 子: '水', 丑: '土', 寅: '木', 卯: '木', 辰: '土', 巳: '火', 午: '火', 未: '土', 申: '金', 酉: '金', 戌: '土', 亥: '水' };
// 地支六冲/六合/三合局/相刑(千年常量,硬编码合法——同黄历宿表理由)。
const ZHI_CHONG = { 子: '午', 丑: '未', 寅: '申', 卯: '酉', 辰: '戌', 巳: '亥', 午: '子', 未: '丑', 申: '寅', 酉: '卯', 戌: '辰', 亥: '巳' };
const ZHI_LIUHE = { 子: '丑', 丑: '子', 寅: '亥', 亥: '寅', 卯: '戌', 戌: '卯', 辰: '酉', 酉: '辰', 巳: '申', 申: '巳', 午: '未', 未: '午' };
const SANHE_JU = { 申子辰: '水', 亥卯未: '木', 寅午戌: '火', 巳酉丑: '金' };
const GAN_WUHE = { 甲: '己', 己: '甲', 乙: '庚', 庚: '乙', 丙: '辛', 辛: '丙', 丁: '壬', 壬: '丁', 戊: '癸', 癸: '戊' };
// 十二长生:恒走 baziLunarLocal.changShengOf 同源(八字页长生三档口径 phaseType 随扫描参数
// 透传——主口径改,择日自动跟;绝不本地重写第二份)。
const CS_NAMES = ['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养'];
const YANG_GAN = ['甲', '丙', '戊', '庚', '壬'];
// 常见神煞名(select 枚举;判定恒走 calcFourPillarShenSha 同源函数,此表只是 UI 选项)。
// [W4 全谱轮] 名单=SHENSHA_GROUP_TAGS 49 名全谱按 ji/xiong 分组(原 35 名手抄清单缺月令/流年系
// 且含五个死键:「三奇贵人」计算侧产名恒为「三奇」;天赦/飞刃/魁罡/空亡不在产名面(32 盘并集
// dump 实证表外产名=0)——选了永不命中,W4 全部斩杀/正名)。
const SHENSHA_GOOD = ['天乙贵人', '太极贵人', '文昌贵人', '国印贵人', '福星贵人', '天德贵人', '月德贵人', '天德合', '月德合', '德秀贵人', '天医', '地医', '天马', '天喜', '红鸾', '金舆', '三奇', '学堂', '词馆', '禄神', '暗禄', '驿马', '将星', '华盖'];
const SHENSHA_BAD = ['羊刃', '红艳', '流霞', '沐浴', '八专', '劫煞', '灾煞', '亡神', '桃花', '孤辰', '寡宿', '病符', '小耗', '大耗', '太岁', '丧门', '吊客', '破碎', '血支', '月厌', '月破', '阴差阳错', '十恶大败', '九丑', '四废'];

// [十四轮] keyDeps 位辅助:柱名→key 位;pillars 参数化类共用(空=全四柱)。
const _pil = (k)=>({ year: 'yearGz', month: 'monthGz', day: 'dayGz', time: 'timeGz' })[k] || 'timeGz';
const _pils = (arr)=>{ const out = []; (arr && arr.length ? arr : ['year', 'month', 'day', 'time']).forEach((k)=>{ const b = _pil(k); if(out.indexOf(b) < 0){ out.push(b); } }); return out; };

const opt = (arr)=>arr.map((v)=>({ value: v, label: v }));
// [W4] 刑/穿/破/三会常表(千年口径,与主页 ZiHeCong 同律):
// 刑=寅巳/巳申/申寅(无恩)、丑戌/戌未/未丑(恃势)、子卯(无礼)、辰午酉亥自刑。
const ZHI_XING_PAIRS = [['寅', '巳'], ['巳', '申'], ['申', '寅'], ['丑', '戌'], ['戌', '未'], ['未', '丑'], ['子', '卯'], ['辰', '辰'], ['午', '午'], ['酉', '酉'], ['亥', '亥']];
const ZHI_CHUAN = { 子: '未', 未: '子', 丑: '午', 午: '丑', 寅: '巳', 巳: '寅', 卯: '辰', 辰: '卯', 申: '亥', 亥: '申', 酉: '戌', 戌: '酉' };
const ZHI_PO = { 子: '酉', 酉: '子', 午: '卯', 卯: '午', 巳: '申', 申: '巳', 寅: '亥', 亥: '寅', 辰: '丑', 丑: '辰', 戌: '未', 未: '戌' };
const SANHUI_JU = ['寅卯辰', '巳午未', '申酉戌', '亥子丑'];
const MATCH_MODE_FIELD = { key: 'matchMode', kind: 'select', label: '匹配', options: [{ value: 'any', label: '任一命中' }, { value: 'all', label: '全部命中' }], hint: '多选值之间的组合方式' };
const PILLAR_FIELD = { key: 'pillars', kind: 'multiselect', label: '限定柱', options: [{ value: 'year', label: '年柱' }, { value: 'month', label: '月柱' }, { value: 'day', label: '日柱' }, { value: 'time', label: '时柱' }], hint: '空=任意柱' };
const needValues = (p)=>(!p.values || !p.values.length) ? '至少选择一项' : '';
const modeText = (p)=>(p.matchMode === 'all' ? '(全部)' : '');
const pillarText = (p)=>((p.pillars && p.pillars.length) ? `@${p.pillars.map((x)=>({ year: '年', month: '月', day: '日', time: '时' }[x] || x)).join('')}` : '');

const PILLARS = ['year', 'month', 'day', 'time'];
const gzOf = (pan, k)=>{
	const c = pan.four && pan.four[k];
	return (c && (c.ganzi || c.ganZhi)) || '';
};

// 惰性求值上下文(神煞查表惰性一次;natal=本命上下文或 null)。
export function makeBaziZeriEvalCtx(pan, natal){
	let shensha = null;
	return {
		natal: natal || null,
		shensha(){
			if(!shensha){
				try{
					shensha = calcFourPillarShenSha(pan.four, pan.godKeyPos) || {};
				}catch(e){
					shensha = {};
				}
			}
			return shensha;
		},
	};
}

const NATAL_MISSING = { pass: false, actual: '未设用事人本命(工作台「用事人本命」区填入后生效)' };

export const BAZI_CONDITION_TYPES = {
	day_ganzhi: {
		category: '四柱',
		keyDeps: ['dayGz'],
		label: '日柱干支',
		defaults: { values: ['甲子'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '干支', options: [...GAN10.map((g)=>({ value: g, label: `${g}(日干)` })), ...ZHI12.map((z)=>({ value: z, label: `${z}(日支)` })), ...GAN10.flatMap((g, gi)=>ZHI12.filter((z, zi)=>(gi % 2) === (zi % 2)).map((z)=>({ value: `${g}${z}`, label: `${g}${z}` })))], hint: '单字=判日干或日支;两字=判整日柱;任一命中即中' },
		],
		validate: needValues,
		summary(p){ return `日柱:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const gz = gzOf(pan, 'day');
			const pass = (p.values || []).some((v)=>(`${v}`.length === 1 ? (gz.charAt(0) === v || gz.charAt(1) === v) : gz === v));
			return { pass, actual: `日柱:${gz || '?'}` };
		},
	},
	hour_ganzhi: {
		category: '四柱',
		keyDeps: ['timeGz'],
		label: '时柱干支',
		defaults: { values: ['甲子'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '干支', options: [...GAN10.map((g)=>({ value: g, label: `${g}(时干)` })), ...ZHI12.map((z)=>({ value: z, label: `${z}(时支)` })), ...GAN10.flatMap((g, gi)=>ZHI12.filter((z, zi)=>(gi % 2) === (zi % 2)).map((z)=>({ value: `${g}${z}`, label: `${g}${z}` })))], hint: '单字=判时干或时支;两字=判整时柱' },
		],
		validate: needValues,
		summary(p){ return `时柱:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const gz = gzOf(pan, 'time');
			const pass = (p.values || []).some((v)=>(`${v}`.length === 1 ? (gz.charAt(0) === v || gz.charAt(1) === v) : gz === v));
			return { pass, actual: `时柱:${gz || '?'}` };
		},
	},
	month_year_gz: {
		category: '四柱',
		keyDeps: (p)=>[(p && p.pillar) === 'year' ? 'yearGz' : 'monthGz'],
		label: '年月柱干支',
		defaults: { pillar: 'month', values: ['寅'] },
		fields: [
			{ key: 'pillar', kind: 'select', label: '柱', options: [{ value: 'year', label: '年柱' }, { value: 'month', label: '月柱' }] },
			{ key: 'values', kind: 'multiselect', label: '干支', options: [...GAN10.map((g)=>({ value: g, label: `${g}(干)` })), ...ZHI12.map((z)=>({ value: z, label: `${z}(支)` }))], hint: '单字判干或支(月支=节气月令)' },
		],
		validate: needValues,
		summary(p){ return `${p.pillar === 'year' ? '年' : '月'}柱:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const gz = gzOf(pan, p.pillar === 'year' ? 'year' : 'month');
			const pass = (p.values || []).some((v)=>(gz.charAt(0) === v || gz.charAt(1) === v || gz === v));
			return { pass, actual: `${p.pillar === 'year' ? '年' : '月'}柱:${gz || '?'}` };
		},
	},
	zhi_relation: {
		category: '四柱',
		keyDeps: (p)=>_pils([(p && p.a) || 'day', (p && p.b) || 'time']),
		label: '支间关系',
		defaults: { a: 'day', b: 'time', rel: 'liuhe' },
		fields: [
			{ key: 'a', kind: 'select', label: '柱A', options: opt2(PILLARS) },
			{ key: 'b', kind: 'select', label: '柱B', options: opt2(PILLARS) },
			{ key: 'rel', kind: 'select', label: '关系', options: [{ value: 'liuhe', label: '六合' }, { value: 'chong', label: '相冲' }, { value: 'sanhe', label: '三合(半合)' }, { value: 'same', label: '相同(伏吟)' }, { value: 'xing', label: '相刑' }, { value: 'chuan', label: '相穿(害)' }, { value: 'po', label: '相破' }, { value: 'sanhui', label: '三会(半会)' }] },	// [W4] 刑穿破会四档(千年常表,与主页 ZiHeCong 同口径)
		],
		validate(p){ return p.a === p.b ? '两柱须不同' : ''; },
		summary(p){ return `${cnPillar(p.a)}${cnPillar(p.b)}支${({ liuhe: '六合', chong: '相冲', sanhe: '三合', same: '伏吟', xing: '相刑', chuan: '相穿', po: '相破', sanhui: '三会' })[p.rel] || p.rel}`; },
		evaluate(pan, p){
			const za = gzOf(pan, p.a).charAt(1);
			const zb = gzOf(pan, p.b).charAt(1);
			let pass = false;
			if(p.rel === 'liuhe'){ pass = ZHI_LIUHE[za] === zb; }
			else if(p.rel === 'chong'){ pass = ZHI_CHONG[za] === zb; }
			else if(p.rel === 'same'){ pass = !!za && za === zb; }
			else if(p.rel === 'sanhe'){ pass = Object.keys(SANHE_JU).some((ju)=>ju.includes(za) && ju.includes(zb) && za !== zb); }
			else if(p.rel === 'xing'){ pass = ZHI_XING_PAIRS.some(([x, y])=>(x === za && y === zb) || (x === zb && y === za)); }
			else if(p.rel === 'chuan'){ pass = ZHI_CHUAN[za] === zb; }
			else if(p.rel === 'po'){ pass = ZHI_PO[za] === zb; }
			else if(p.rel === 'sanhui'){ pass = SANHUI_JU.some((ju)=>ju.includes(za) && ju.includes(zb) && za !== zb); }
			return { pass, actual: `${cnPillar(p.a)}支${za || '?'}·${cnPillar(p.b)}支${zb || '?'}` };
		},
	},
	gan_wuhe: {
		category: '四柱',
		keyDeps: (p)=>_pils([(p && p.a) || 'day', (p && p.b) || 'time']),
		label: '天干五合',
		defaults: { a: 'day', b: 'time' },
		fields: [
			{ key: 'a', kind: 'select', label: '柱A', options: opt2(PILLARS) },
			{ key: 'b', kind: 'select', label: '柱B', options: opt2(PILLARS) },
		],
		validate(p){ return p.a === p.b ? '两柱须不同' : ''; },
		summary(p){ return `${cnPillar(p.a)}${cnPillar(p.b)}干五合`; },
		evaluate(pan, p){
			const ga = gzOf(pan, p.a).charAt(0);
			const gb = gzOf(pan, p.b).charAt(0);
			return { pass: !!ga && GAN_WUHE[ga] === gb, actual: `${cnPillar(p.a)}干${ga || '?'}·${cnPillar(p.b)}干${gb || '?'}` };
		},
	},
	sanhe_ju: {
		category: '四柱',
		keyDeps: ['yearGz', 'monthGz', 'dayGz', 'timeGz'],
		label: '地支三合局',
		defaults: { values: ['水'], full: false },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '合局', options: WUXING5.filter((w)=>w !== '土').map((w)=>({ value: w, label: `${w}局` })) },
			{ key: 'full', kind: 'toggle', label: '须三支全(缺省半合即中)' },
		],
		validate: needValues,
		summary(p){ return `三合${(p.values || []).join('/')}局${p.full ? '(全)' : ''}`; },
		evaluate(pan, p){
			const zhis = PILLARS.map((k)=>gzOf(pan, k).charAt(1)).filter(Boolean);
			const hits = [];
			Object.keys(SANHE_JU).forEach((ju)=>{
				const present = [...ju].filter((z)=>zhis.includes(z));
				const need = p.full ? 3 : 2;
				if(present.length >= need && (p.values || []).includes(SANHE_JU[ju])){ hits.push(`${SANHE_JU[ju]}局(${present.join('')})`); }
			});
			return { pass: hits.length > 0, actual: hits.length ? hits.join('、') : `四支:${zhis.join('')}` };
		},
	},
	shensha_has: {
		category: '神煞',
		keyDeps: ['yearGz', 'monthGz', 'dayGz', 'timeGz'],
		label: '吉神在柱',
		defaults: { values: ['天乙贵人'], pillars: [], matchMode: 'any' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '吉神', options: opt(SHENSHA_GOOD), hint: '判定=八字页神煞面同函数(calcFourPillarShenSha)' },
			PILLAR_FIELD,
			MATCH_MODE_FIELD,
		],
		validate: needValues,
		summary(p){ return `吉神:${(p.values || []).join('/')}${pillarText(p)}${modeText(p)}`; },
		evaluate(pan, p, ctx){
			return evalShensha(pan, p, ctx);
		},
	},
	shensha_not: {
		category: '神煞',
		keyDeps: ['yearGz', 'monthGz', 'dayGz', 'timeGz'],
		label: '凶煞回避',
		defaults: { values: ['羊刃', '劫煞'], pillars: [], mode: 'without' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '凶煞', options: opt(SHENSHA_BAD) },
			PILLAR_FIELD,
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'without', label: '全不出现(净)' }, { value: 'with', label: '出现任一' }] },
		],
		validate: needValues,
		summary(p){ return `${p.mode === 'with' ? '煞现' : '避煞'}:${(p.values || []).join('/')}${pillarText(p)}`; },
		evaluate(pan, p, ctx){
			const r = evalShensha(pan, { ...p, matchMode: 'any' }, ctx);
			return { pass: p.mode === 'with' ? r.pass : !r.pass, actual: r.actual };
		},
	},
	nayin_wuxing: {
		category: '纳音长生',
		keyDeps: (p)=>_pils(p && p.pillars),
		label: '柱纳音五行',
		defaults: { pillar: 'day', values: ['金'] },
		fields: [
			{ key: 'pillar', kind: 'select', label: '柱', options: opt2(PILLARS) },
			{ key: 'values', kind: 'multiselect', label: '五行', options: opt(WUXING5), hint: '按纳音名尾字判(海中金→金)' },
		],
		validate: needValues,
		summary(p){ return `${cnPillar(p.pillar)}纳音:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const c = pan.four && pan.four[p.pillar];
			const ny = (c && (c.naying || c.nayin)) || '';
			const el = ny.charAt(ny.length - 1);
			return { pass: (p.values || []).includes(el), actual: `${cnPillar(p.pillar)}纳音:${ny || '?'}` };
		},
	},
	changsheng: {
		category: '纳音长生',
		keyDeps: (p)=>_pils(['day', (p && p.at) || 'time']),
		label: '日干长生态',
		defaults: { at: 'time', values: ['长生', '临官', '帝旺'] },
		fields: [
			{ key: 'at', kind: 'select', label: '于', options: [{ value: 'time', label: '时支' }, { value: 'day', label: '日支(自坐)' }, { value: 'month', label: '月支(月令)' }] },
			{ key: 'values', kind: 'multiselect', label: '长生态', options: opt(CS_NAMES) },
		],
		validate: needValues,
		summary(p){ return `日干于${({ time: '时', day: '日', month: '月' })[p.at] || p.at}支:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const dg = gzOf(pan, 'day').charAt(0);
			const zhi = gzOf(pan, p.at || 'time').charAt(1);
			const cs = changShengOf(dg, zhi, pan.phaseType);	// 同源三档口径(baziLunarLocal)
			return { pass: (p.values || []).includes(cs), actual: `日干${dg || '?'}于${zhi || '?'}=${cs || '?'}` };
		},
	},
	xunkong: {
		category: '纳音长生',
		keyDeps: (p)=>_pils(['day', (p && p.pillar) || 'time']),
		label: '旬空',
		defaults: { pillar: 'time', mode: 'not' },
		fields: [
			{ key: 'pillar', kind: 'select', label: '柱', options: [{ value: 'time', label: '时支' }, { value: 'day', label: '日支' }] },
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'not', label: '不落空(实)' }, { value: 'is', label: '落旬空' }] },
		],
		summary(p){ return `${p.pillar === 'day' ? '日' : '时'}支${p.mode === 'is' ? '落空' : '不空'}`; },
		evaluate(pan, p){
			// 旬空以日柱起旬(择时通例);恒走 baziLunarLocal.xunKongOf 同源(lunar 单源)。
			const dayGz = gzOf(pan, 'day');
			const kong = `${xunKongOf(dayGz) || ''}`;
			const zhi = gzOf(pan, p.pillar || 'time').charAt(1);
			const isKong = !!zhi && kong.includes(zhi);
			return { pass: p.mode === 'is' ? isKong : !isKong, actual: `日柱${dayGz}旬空${kong || '?'};${p.pillar === 'day' ? '日' : '时'}支${zhi || '?'}${isKong ? '落空' : '不空'}` };
		},
	},
	wuxing_day: {
		category: '五行',
		keyDeps: ['dayGz'],
		label: '日主五行',
		defaults: { values: ['木'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '五行', options: opt(WUXING5) },
		],
		validate: needValues,
		summary(p){ return `日主:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const dg = gzOf(pan, 'day').charAt(0);
			return { pass: (p.values || []).includes(GAN_WX[dg]), actual: `日主${dg || '?'}(${GAN_WX[dg] || '?'})` };
		},
	},
	wuxing_presence: {
		category: '五行',
		keyDeps: ['yearGz', 'monthGz', 'dayGz', 'timeGz'],
		label: '五行齐缺',
		defaults: { mode: 'all5', values: [] },
		fields: [
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'all5', label: '五行俱全' }, { value: 'has', label: '含指定行' }, { value: 'lack', label: '缺指定行' }] },
			{ key: 'values', kind: 'multiselect', label: '五行', options: opt(WUXING5), hint: 'all5 档不用选' },
		],
		validate(p){ return (p.mode !== 'all5' && (!p.values || !p.values.length)) ? '选择五行' : ''; },
		summary(p){ return p.mode === 'all5' ? '五行俱全' : `${p.mode === 'lack' ? '缺' : '含'}${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const present = new Set();
			PILLARS.forEach((k)=>{
				const gz = gzOf(pan, k);
				if(GAN_WX[gz.charAt(0)]){ present.add(GAN_WX[gz.charAt(0)]); }
				if(ZHI_WX[gz.charAt(1)]){ present.add(ZHI_WX[gz.charAt(1)]); }
			});
			let pass;
			if(p.mode === 'all5'){ pass = present.size === 5; }
			else if(p.mode === 'lack'){ pass = (p.values || []).every((w)=>!present.has(w)); }
			else{ pass = (p.values || []).every((w)=>present.has(w)); }
			return { pass, actual: `显五行:${[...present].join('') || '?'}` };
		},
	},
	yinyang_day: {
		category: '历法',
		keyDeps: ['dayGz'],
		label: '阴阳日',
		defaults: { value: 'yang' },
		fields: [
			{ key: 'value', kind: 'select', label: '取', options: [{ value: 'yang', label: '阳日(阳干)' }, { value: 'yin', label: '阴日(阴干)' }] },
		],
		summary(p){ return p.value === 'yin' ? '阴日' : '阳日'; },
		evaluate(pan, p){
			const dg = gzOf(pan, 'day').charAt(0);
			const isYang = YANG_GAN.includes(dg);
			return { pass: p.value === 'yin' ? !isYang : isYang, actual: `日干${dg || '?'}(${isYang ? '阳' : '阴'})` };
		},
	},
	jieqi_month: {
		category: '历法',
		keyDeps: ['monthGz'],
		label: '节气月令',
		defaults: { values: ['寅'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '月支', options: ZHI12.map((z)=>({ value: z, label: `${z}月` })), hint: '按节气换月(与八字月柱同口径)' },
		],
		validate: needValues,
		summary(p){ return `月令:${(p.values || []).join('/')}月`; },
		evaluate(pan, p){
			const mz = gzOf(pan, 'month').charAt(1);
			return { pass: (p.values || []).includes(mz), actual: `月令:${mz || '?'}月` };
		},
	},
	bm_bu_chong: {
		category: '本命',
		keyDeps: ['dayGz', 'timeGz'],
		label: '不冲本命',
		defaults: { targets: ['yearZhi', 'dayZhi'] },
		fields: [
			{ key: 'targets', kind: 'multiselect', label: '护住', options: [{ value: 'yearZhi', label: '本命年支(属相)' }, { value: 'dayZhi', label: '本命日支' }], hint: '候选日支/时支均不冲所选本命支' },
		],
		validate(p){ return (!p.targets || !p.targets.length) ? '至少护一项' : ''; },
		summary(p){ return `不冲本命${(p.targets || []).map((t)=>(t === 'yearZhi' ? '年支' : '日支')).join('/')}`; },
		evaluate(pan, p, ctx){
			if(!ctx.natal){ return NATAL_MISSING; }
			const cands = [gzOf(pan, 'day').charAt(1), gzOf(pan, 'time').charAt(1)].filter(Boolean);
			const bad = [];
			(p.targets || []).forEach((t)=>{
				const bz = ctx.natal[t];
				if(bz && cands.some((z)=>ZHI_CHONG[z] === bz)){ bad.push(`${t === 'yearZhi' ? '年支' : '日支'}${bz}被冲`); }
			});
			return { pass: bad.length === 0, actual: bad.length ? bad.join('、') : `日时支${cands.join('')}不冲本命` };
		},
	},
	bm_xiyong: {
		category: '本命',
		keyDeps: (p)=>((p && p.scope) === 'dayhour' ? ['dayGz', 'timeGz'] : ['yearGz', 'monthGz', 'dayGz', 'timeGz']),
		label: '喜用相扶',
		defaults: { scope: 'day' },
		fields: [
			{ key: 'scope', kind: 'select', label: '取面', options: [{ value: 'day', label: '日干五行∈本命喜用' }, { value: 'dayhour', label: '日时干五行均∈喜用' }] },
		],
		summary(p){ return `喜用相扶(${p.scope === 'dayhour' ? '日时' : '日'})`; },
		evaluate(pan, p, ctx){
			if(!ctx.natal){ return NATAL_MISSING; }
			const xi = ctx.natal.xiyong || [];
			if(!xi.length){ return { pass: false, actual: '本命喜用未解出(生辰不全?)' }; }
			const gans = p.scope === 'dayhour'
				? [gzOf(pan, 'day').charAt(0), gzOf(pan, 'time').charAt(0)]
				: [gzOf(pan, 'day').charAt(0)];
			const pass = gans.every((g)=>xi.includes(GAN_WX[g]));
			return { pass, actual: `喜用${xi.join('')};候选${gans.map((g)=>`${g}(${GAN_WX[g] || '?'})`).join('/')}` };
		},
	},
	bm_he: {
		category: '本命',
		keyDeps: ['dayGz'],
		label: '与本命相合',
		defaults: { rel: 'zhi_liuhe' },
		fields: [
			{ key: 'rel', kind: 'select', label: '合法', options: [{ value: 'zhi_liuhe', label: '候选日支合本命日支(六合)' }, { value: 'zhi_sanhe', label: '候选日支会本命年支(三合)' }, { value: 'gan_wuhe', label: '候选日干合本命日干(五合)' }] },
		],
		summary(p){ return ({ zhi_liuhe: '日支六合本命', zhi_sanhe: '日支三合本命年', gan_wuhe: '日干五合本命' })[p.rel] || '与本命相合'; },
		evaluate(pan, p, ctx){
			if(!ctx.natal){ return NATAL_MISSING; }
			const dz = gzOf(pan, 'day').charAt(1);
			const dg = gzOf(pan, 'day').charAt(0);
			let pass = false;
			let why = '';
			if(p.rel === 'zhi_liuhe'){
				pass = !!dz && ZHI_LIUHE[dz] === ctx.natal.dayZhi;
				why = `候选日支${dz || '?'}·本命日支${ctx.natal.dayZhi || '?'}`;
			}else if(p.rel === 'zhi_sanhe'){
				pass = Object.keys(SANHE_JU).some((ju)=>ju.includes(dz) && ju.includes(ctx.natal.yearZhi) && dz !== ctx.natal.yearZhi);
				why = `候选日支${dz || '?'}·本命年支${ctx.natal.yearZhi || '?'}`;
			}else{
				pass = !!dg && GAN_WUHE[dg] === ctx.natal.dayGan;
				why = `候选日干${dg || '?'}·本命日干${ctx.natal.dayGan || '?'}`;
			}
			return { pass, actual: why };
		},
	},
	shishen_at: {
		category: '四柱',
		keyDeps: (p)=>_pils(['day'].concat((p && p.pillars) || [])),
		label: '十神在柱(干/支本气/藏干)',
		defaults: { layer: 'stem', gods: ['正官'], pillars: [], matchMode: 'any' },
		fields: [
			{ key: 'layer', kind: 'select', label: '判层', options: [{ value: 'stem', label: '天干十神' }, { value: 'branch', label: '支本气十神' }, { value: 'canggan', label: '藏干十神(任一藏)' }] },
			{ key: 'gods', kind: 'multiselect', label: '十神(任一)', options: opt(['比肩', '劫财', '食神', '伤官', '偏财', '正财', '七杀', '正官', '偏印', '正印']), hint: '相对日元;供数=pan.four[柱].stem/branch/stemInBranch 的 relative(主页四柱表同源)' },
			PILLAR_FIELD,
			MATCH_MODE_FIELD,
		],
		validate: (p)=>(!p.gods || !p.gods.length) ? '至少选择一项' : '',
		summary(p){ return `${({ stem: '干', branch: '支', canggan: '藏' })[p.layer] || '干'}十神:${(p.gods || []).join('/')}${pillarText(p)}${modeText(p)}`; },
		evaluate(pan, p){
			// relative 为简称(比/劫/食/伤/财/才/官/杀/印/枭——「才」=偏财「枭」=偏印,锚盘 dump 实抓);
			// 全名↔简称显式映射,禁模糊 indexOf(「偏财」含「财」会误中正财)。
			const FULL2SHORT = { 比肩: '比', 劫财: '劫', 食神: '食', 伤官: '伤', 正财: '财', 偏财: '才', 正官: '官', 七杀: '杀', 正印: '印', 偏印: '枭' };
			const pillars = (p.pillars && p.pillars.length) ? p.pillars : PILLARS;
			const per = pillars.map((k)=>{
				const c = (pan.four && pan.four[k]) || {};
				let rels = [];
				if(p.layer === 'branch'){ rels = [c.branch && c.branch.relative]; }
				else if(p.layer === 'canggan'){ rels = (c.stemInBranch || []).map((it)=>it && it.relative); }
				else{ rels = [c.stem && c.stem.relative]; }
				const set = rels.filter(Boolean).map((r)=>`${r}`);
				return { k, set, hit: (p.gods || []).some((g)=>set.includes(FULL2SHORT[g] || g)) };
			});
			const hits = per.filter((x)=>x.hit);
			const pass = p.matchMode === 'all' ? (per.length > 0 && hits.length === per.length) : hits.length > 0;
			return { pass, actual: per.map((x)=>`${({ year: '年', month: '月', day: '日', time: '时' })[x.k]}${x.set.join(',') || '—'}`).join(' ') };
		},
	},
	tai_ming_shen: {
		category: '四柱',
		keyDeps: (p)=>((p && p.who) === 'tai' ? ['monthGz'] : ['monthGz', 'timeGz']),
		label: '胎元/命宫/身宫柱',
		defaults: { who: 'ming', dim: 'ganzhi', values: ['甲子'] },
		fields: [
			{ key: 'who', kind: 'select', label: '柱', options: [{ value: 'tai', label: '胎元' }, { value: 'ming', label: '命宫' }, { value: 'shen', label: '身宫' }] },
			{ key: 'dim', kind: 'select', label: '判面', options: [{ value: 'ganzhi', label: '干支(单字=干或支)' }, { value: 'nayin', label: '纳音五行' }] },
			{ key: 'values', kind: 'multiselect', label: '取值(任一)', options: [...GAN10.map((g)=>({ value: g, label: `${g}(干)` })), ...ZHI12.map((z)=>({ value: z, label: `${z}(支)` })), ...opt(['金', '木', '水', '火', '土'])], hint: '三柱=makePillar 全套派生(主页同源);纳音判尾字五行' },
		],
		validate: needValues,
		summary(p){ return `${({ tai: '胎元', ming: '命宫', shen: '身宫' })[p.who] || '命宫'}·${p.dim === 'nayin' ? '纳音' : '干支'}:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const c = (pan.four && pan.four[p.who || 'ming']) || {};
			const gz = c.ganzi || c.ganZhi || '';
			if(p.dim === 'nayin'){
				const ny = `${c.naying || ''}`;
				const el = ny.slice(-1);
				return { pass: !!el && (p.values || []).includes(el), actual: `${({ tai: '胎元', ming: '命宫', shen: '身宫' })[p.who]}${gz}·${ny || '—'}` };
			}
			const pass = (p.values || []).some((v)=>(v.length >= 2 ? gz === v : gz.indexOf(v) >= 0));
			return { pass, actual: `${({ tai: '胎元', ming: '命宫', shen: '身宫' })[p.who]}:${gz || '—'}` };
		},
	},
	nayin_full: {
		category: '纳音长生',
		keyDeps: (p)=>_pils(p && p.pillars),
		label: '柱纳音(六十甲子全名)',
		defaults: { values: ['海中金'], pillars: [], matchMode: 'any' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '纳音(任一)', options: opt(['海中金', '炉中火', '大林木', '路旁土', '剑锋金', '山头火', '涧下水', '城头土', '白蜡金', '杨柳木', '泉中水', '屋上土', '霹雳火', '松柏木', '长流水', '沙中金', '山下火', '平地木', '壁上土', '金箔金', '覆灯火', '天河水', '大驿土', '钗钏金', '桑柘木', '大溪水', '沙中土', '天上火', '石榴木', '大海水']), hint: '三十纳音全名;既有 nayin_wuxing 只判尾字五行' },
			PILLAR_FIELD,
			MATCH_MODE_FIELD,
		],
		validate: needValues,
		summary(p){ return `纳音:${(p.values || []).join('/')}${pillarText(p)}${modeText(p)}`; },
		evaluate(pan, p){
			const pillars = (p.pillars && p.pillars.length) ? p.pillars : PILLARS;
			const per = pillars.map((k)=>{
				const ny = `${((pan.four && pan.four[k]) || {}).naying || ''}`;
				return { k, ny, hit: (p.values || []).some((v)=>ny.indexOf(v) >= 0) };
			});
			const hits = per.filter((x)=>x.hit);
			const pass = p.matchMode === 'all' ? (per.length > 0 && hits.length === per.length) : hits.length > 0;
			return { pass, actual: per.map((x)=>`${({ year: '年', month: '月', day: '日', time: '时' })[x.k]}${x.ny || '—'}`).join(' ') };
		},
	},
	zhu_phase: {
		category: '纳音长生',
		keyDeps: (p)=>_pils(['day'].concat((p && p.pillars) || [])),
		label: '逐柱星运(十二长生)',
		defaults: { phases: ['长生', '帝旺'], pillars: [], matchMode: 'any' },
		fields: [
			{ key: 'phases', kind: 'multiselect', label: '星运(任一)', options: opt(['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养']), hint: '日元于各柱支的十二长生;随工作台「长生」口径(phaseType)重算,不吃烘焙值' },
			PILLAR_FIELD,
			MATCH_MODE_FIELD,
		],
		validate: (p)=>(!p.phases || !p.phases.length) ? '至少选择一项' : '',
		summary(p){ return `星运:${(p.phases || []).join('/')}${pillarText(p)}${modeText(p)}`; },
		evaluate(pan, p){
			// 走 changShengOf(dayGan, 柱支, pan.phaseType) 重算——four[k].ganziPhase 是 lite 烘焙值
			// (恒 phaseType=2),直读会与工作台「长生」口径选择脱钩(侦察预警的烘焙坑)。
			const dayGan = gzOf(pan, 'day').charAt(0);
			const pillars = (p.pillars && p.pillars.length) ? p.pillars : PILLARS;
			const per = pillars.map((k)=>{
				const zhi = gzOf(pan, k).charAt(1);
				let ph = '';
				try{ ph = (dayGan && zhi) ? (changShengOf(dayGan, zhi, pan.phaseType !== undefined ? pan.phaseType : 2) || '') : ''; }catch(e){ ph = ''; }
				return { k, ph, hit: !!ph && (p.phases || []).includes(ph) };
			});
			const hits = per.filter((x)=>x.hit);
			const pass = p.matchMode === 'all' ? (per.length > 0 && hits.length === per.length) : hits.length > 0;
			return { pass, actual: per.map((x)=>`${({ year: '年', month: '月', day: '日', time: '时' })[x.k]}${x.ph || '—'}`).join(' ') };
		},
	},
	zhu_xunkong: {
		category: '纳音长生',
		keyDeps: (p)=>_pils(p && p.pillars),
		label: '逐柱旬空(各柱自起旬)',
		defaults: { pillars: ['day'], zhis: [] },
		fields: [
			{ key: 'pillars', kind: 'multiselect', label: '柱(任一柱空亡即中)', options: [{ value: 'year', label: '年柱' }, { value: 'month', label: '月柱' }, { value: 'day', label: '日柱' }, { value: 'time', label: '时柱' }] },
			{ key: 'zhis', kind: 'multiselect', label: '限定空亡支(空=任意)', options: opt(ZHI12), hint: '各柱按自身干支起旬的旬空(four[k].xunEmpty);既有 xunkong 类恒按日柱起旬' },
		],
		validate: (p)=>(!p.pillars || !p.pillars.length) ? '至少选择一项' : '',
		summary(p){ return `柱旬空:${(p.pillars || []).map((x)=>({ year: '年', month: '月', day: '日', time: '时' })[x] || x).join('/')}${(p.zhis && p.zhis.length) ? `含${p.zhis.join('/')}` : ''}`; },
		evaluate(pan, p){
			const per = (p.pillars || []).map((k)=>{
				const xe = `${((pan.four && pan.four[k]) || {}).xunEmpty || ''}`;
				const ok = !!xe && (!(p.zhis && p.zhis.length) || p.zhis.some((z)=>xe.indexOf(z) >= 0));
				return { k, xe, ok };
			});
			const pass = per.some((x)=>x.ok);
			return { pass, actual: per.map((x)=>`${({ year: '年', month: '月', day: '日', time: '时' })[x.k]}空${x.xe || '—'}`).join(' ') };
		},
	},
	canggan_has: {
		category: '五行',
		keyDeps: (p)=>_pils(p && p.pillars),
		label: '藏干存在性',
		defaults: { mode: 'has', gans: ['丁'], pillars: [] },
		fields: [
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'has', label: '藏有任一' }, { value: 'not', label: '全不藏(透藏皆无另用五行齐缺)' }] },
			{ key: 'gans', kind: 'multiselect', label: '天干(任一)', options: opt(GAN10), hint: '柱支藏干(stemInBranch);「时支藏丁」「四柱不藏庚」类' },
			PILLAR_FIELD,
		],
		validate: (p)=>(!p.gans || !p.gans.length) ? '至少选择一项' : '',
		summary(p){ return `${p.mode === 'not' ? '不藏' : '藏'}${(p.gans || []).join('/')}${pillarText(p)}`; },
		evaluate(pan, p){
			const pillars = (p.pillars && p.pillars.length) ? p.pillars : PILLARS;
			const all = [];
			pillars.forEach((k)=>{
				(((pan.four && pan.four[k]) || {}).stemInBranch || []).forEach((it)=>{ if(it && it.cell){ all.push(`${it.cell}`); } });
			});
			const hit = (p.gans || []).some((g)=>all.includes(g));
			const pass = p.mode === 'not' ? !hit : hit;
			return { pass, actual: `藏干:${all.join('') || '—'}` };
		},
	},
	lunar_date: {
		category: '历法',
		keyDeps: ['dayGz'],
		label: '农历日/月/闰月',
		defaults: { dim: 'day', values: ['1'] },
		fields: [
			{ key: 'dim', kind: 'select', label: '判面', options: [{ value: 'day', label: '农历日(1-30)' }, { value: 'month', label: '农历月(1-12)' }, { value: 'leap', label: '闰月' }] },
			{ key: 'values', kind: 'multiselect', label: '取值(任一)', options: [...Array.from({ length: 30 }, (_, i)=>({ value: `${i + 1}`, label: `${i + 1}` })), { value: 'leap_yes', label: '是闰月' }, { value: 'leap_no', label: '非闰月' }], showIf: (p)=>true, hint: 'nongli.monthNum/dayNum/leap(黄历同源);闰月档选 是/非' },
		],
		validate: needValues,
		summary(p){ return `${({ day: '农历日', month: '农历月', leap: '闰月' })[p.dim] || '农历日'}:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const n = pan.nongli || {};
			if(p.dim === 'leap'){
				const isLeap = !!n.leap;
				const want = (p.values || []).some((v)=>(v === 'leap_yes' ? isLeap : (v === 'leap_no' ? !isLeap : false)));
				return { pass: want, actual: `${n.month || '?'}月${isLeap ? '(闰)' : ''}` };
			}
			const v = p.dim === 'month' ? n.monthNum : n.dayNum;
			return { pass: (p.values || []).map(Number).includes(Number(v)), actual: `农历${n.month || '?'}月${n.day || '?'}(${n.monthNum || '?'}/${n.dayNum || '?'})` };
		},
	},
	jie_delta: {
		category: '历法',
		keyDeps: ['dayGz', 'monthGz'],
		label: '节后天数',
		defaults: { min: 0, max: 5 },
		fields: [
			{ key: 'min', kind: 'number', label: '≥天', min: 0, max: 40, step: 1 },
			{ key: 'max', kind: 'number', label: '≤天', min: 0, max: 40, step: 1 },
		],
		validate: (p)=>((Number(p.min) > Number(p.max)) ? '下限不可大于上限' : ''),
		summary(p){ return `节后${p.min}-${p.max}天`; },
		evaluate(pan, p){
			const m = `${(pan.nongli && pan.nongli.jiedelta) || ''}`.match(/(\d+)/);
			const d = m ? Number(m[1]) : null;
			const pass = d !== null && d >= Number(p.min || 0) && d <= Number(p.max === undefined ? 40 : p.max);
			return { pass, actual: `${(pan.nongli && pan.nongli.jieqi) || '?'}后第${d === null ? '?' : d}天` };
		},
	},
};

function opt2(pillars){
	return pillars.map((k)=>({ value: k, label: cnPillar(k) }));
}
function cnPillar(k){
	return ({ year: '年柱', month: '月柱', day: '日柱', time: '时柱' })[k] || k;
}
function evalShensha(pan, p, ctx){
	const acc = ctx.shensha();
	const scope = (p.pillars && p.pillars.length) ? p.pillars : PILLARS;
	const found = new Set();
	scope.forEach((k)=>{
		(acc[k] || []).forEach((n)=>found.add(n));
	});
	const vals = p.values || [];
	const hit = vals.filter((v)=>found.has(v));
	const pass = p.matchMode === 'all' ? hit.length === vals.length && vals.length > 0 : hit.length > 0;
	return { pass, actual: `${scope.map((k)=>cnPillar(k).charAt(0)).join('')}柱神煞:${[...found].slice(0, 12).join('、') || '无'}` };
}


// ── 树工厂/摘要/编译(与奇门/黄历同构;compile 产物喂 evaluateBaziTree) ──
export function newBaziLeaf(type, joiner){
	const spec = BAZI_CONDITION_TYPES[type];
	return {
		kind: 'leaf',
		type,
		negate: false,
		joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all',
		params: spec ? JSON.parse(JSON.stringify(spec.defaults)) : {},
	};
}
export function newBaziGroup(joiner){
	return { kind: 'group', negate: false, joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all', children: [] };
}

export function baziLeafSummary(leaf){
	const spec = leaf ? BAZI_CONDITION_TYPES[leaf.type] : null;
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
		const spec = BAZI_CONDITION_TYPES[node.type];
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
export function compileBaziTree(root){
	return compileSelf(root);
}
