// [Z5·六壬择日] 条件注册表(时辰粒度)。判定单源:排盘=LiuRengMain 加性导出的同一函数族
// (buildLiuRengLayout/buildKeData/buildSanChuanData→ChuangChart 涉害 byte-perfect 核),
// 神煞=liurengLocal fillLrGods(表与 Java gods.json 机械同源,liurengGodsParity 看守),
// 天将环=LRConst.TianJiang 同源 import。spec 契约与 QIMEN/HUANGLI/BAZI/TAIYI/ZIWEI
// 逐字段同构;ctx=makeLiurengZeriEvalCtx(pan) 惰性。一键一行 Tab 缩进(preflight 键集契约)。
// [十一轮] keyDeps 合同:每类必须显式声明所吃的「可掩 plateKey 位」——值域
// ['diurnal','yearZhi','monthZhi','candY'] 子集(day/timeZhi/yue 三基础位全类恒吃,不声明)。
// 面→位映射依据(2026-08-31 逐类 evaluate 消费键机械 dump 定谳,勿凭类名猜):
//   sanChuan.tianJiang / layout.gods / ctx.jiangAt / pan.diurnal / refs 的 sanChuanGods·guizi → diurnal
//   lrGods.godsMonth → monthZhi;lrGods.godsYear(年柱支起环)→ yearZhi;ctx.xingnian(pan._candY 行年)→ candY
//   lrGods.gods/godsZi/godsGan、ke/sanChuan.name·cuang·liuQin、fourColumns、xun、yue → 基础位,不声明
// 声明漏/滥由类级判别测试机械抓(liurengZeriEngine.test.js「keyDeps 判别网」);缺 keyDeps 键=完备闸红。
import { TianJiang, ZiList } from '../../liureng/LRConst.js';
import { GROUP_TYPES, JOINER_CN } from './conditionTypes.js';
// [W2 全谱轮] 小局/大格判定单源=主页右栏同函数(prebuilt 直供跳重算;涉日月宿位的局无星历不判)。
import { buildLiuRengReferenceContext, matchXiaoJuReferences, matchDaGeReferences, XIAO_JU_META, DA_GE_META } from '../../liureng/LiuRengMain.js';
import { changShengOf } from '../../bazi/baziLunarLocal.js';
import { GanJiZi } from '../../liureng/LRConst.js';

export { GROUP_TYPES, JOINER_CN };

// 🔴 课名集=ChuangChart res.name 实产 22 名+四族长名(伏吟/返吟/昴星/别责——引擎只产
// 成员名,选族长经 LR_KE_FAMILY 匹配全成员;曾按名恒等匹配=四族长永不命中,审查实抓)。
// 「始入课」默认档并入重审(seHaiOpts.shiRuKe 不入择日参数面,恒不产)——死开关律删出选项。
export const LR_KE_FAMILY = {
	伏吟课: ['自任课', '自信课', '杜传课'],
	返吟课: ['无依课', '无亲课'],
	昴星课: ['虎视课', '掩目课'],
	别责课: ['不备课', '芜淫课'],	// ChuangChart 别责两名:刚日=不备/柔日=芜淫
};
export const LR_KE_NAMES = ['元首课', '重审课', '知一课', '比用课', '涉害课', '见机课', '察微课', '缀瑕课', '蒿矢课', '弹射课', '八专课', '别责课', '不备课', '芜淫课', '昴星课', '虎视课', '掩目课', '伏吟课', '自任课', '自信课', '杜传课', '不虞课', '返吟课', '无依课', '无亲课'];
export const LR_LIUQIN = ['父母', '兄弟', '子孙', '妻财', '官鬼'];
const ZHI12 = ZiList;
const GAN10 = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
// 五行生克(支):贼克判定用(下贼上=下克上)。
const ZHI_WX = { 子: '水', 亥: '水', 寅: '木', 卯: '木', 巳: '火', 午: '火', 申: '金', 酉: '金', 辰: '土', 戌: '土', 丑: '土', 未: '土' };
const WX_KE = { 木: '土', 土: '水', 水: '火', 火: '金', 金: '木' };
const ZHI_CHONG = (z)=>ZHI12[(ZHI12.indexOf(z) + 6) % 12];
const SANHE = [['申', '子', '辰', '水'], ['亥', '卯', '未', '木'], ['寅', '午', '戌', '火'], ['巳', '酉', '丑', '金']];

const opt = (arr)=>arr.map((v)=>({ value: v, label: v }));
const needValues = (p)=>(!p.values || !p.values.length) ? '至少选择一项' : '';
const stripKong = (c)=>`${c || ''}`.replace(/^空/, '').slice(-1);	// 'X'/'空X'/'干支' 尾字=支

// 惰性求值上下文。pan={layout,ke,sanChuan,lrGods,xun,fourColumns,yue,diurnal,_natal,_candY}
export function makeLiurengZeriEvalCtx(pan){
	return {
		natal: (pan && pan._natal) || null,
		// 🔴 行年支按**候选年**现算(虚岁=候选年-生年+1;男一岁起寅顺、女起申逆)。
		// 曾在 resolveNatal 按系统年冻结——跨年扫描整支错位(审查实抓)。
		// 兼容:旧方案存档 natal 无 bornYear 时回落其冻结 xingnianZhi。
		xingnian(){
			const n = (pan && pan._natal) || null;
			if(!n){ return ''; }
			const candY = Number(pan && pan._candY);
			if(!n.bornYear || !candY){ return n.xingnianZhi || ''; }
			const age = Math.max(1, candY - n.bornYear + 1);
			const start = n.male ? 2 : 8;	// 寅/申
			return n.male ? ZHI12[(start + age - 1) % 12] : ZHI12[((start - (age - 1)) % 12 + 12) % 12];
		},
		chuanZhi(){
			const c = (pan.sanChuan && pan.sanChuan.cuang) || [];
			return c.map(stripKong);
		},
		chuanRaw(){
			return (pan.sanChuan && pan.sanChuan.cuang) || [];
		},
		tianAt(dizhi){
			const i = ZHI12.indexOf(dizhi);
			return i >= 0 && pan.layout ? pan.layout.upZi[i] : '';
		},
		jiangAt(dizhi){
			const i = ZHI12.indexOf(dizhi);
			return i >= 0 && pan.layout ? pan.layout.houseTianJiang[i] : '';
		},
		// [W2] 参考面(小局65/大格10)惰性一次:主页 buildLiuRengReferenceContext 同函数,
		// prebuilt 直供扫描已起的 layout/ke/sanChuan(跳重算);liureng 形按主页 requestGods
		// 消费面装配(fourColumns/xun/gods);无星历 objects——涉日月宿位的局静默不判。
		refs(){
			if(this._refs !== undefined){ return this._refs; }
			try{
				const liureng = {
					fourColumns: pan.fourColumns || {},
					xun: pan.xun || {},
					gods: (pan.lrGods && pan.lrGods.gods) || {},
					season: (pan.lrGods && pan.lrGods.season) || {},
				};
				const ctx = buildLiuRengReferenceContext(liureng, pan.chartLite || null, pan.guirengType || 0, null, pan.castOverride || null, {
					prebuilt: { layout: pan.layout, keData: pan.ke, sanChuan: pan.sanChuan },
				});
				this._refs = {
					xiaoJu: matchXiaoJuReferences(ctx) || [],
					daGe: matchDaGeReferences(ctx) || [],
				};
			}catch(e){
				this._refs = { xiaoJu: [], daGe: [] };
			}
			return this._refs;
		},
	};
}

export const LIURENG_CONDITION_TYPES = {
	ke_name: {
		category: '课体',
		keyDeps: [],
		label: '课名(九宗门)',
		defaults: { values: ['元首课'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '课名', options: opt(LR_KE_NAMES), hint: '判定=主六壬页三传引擎同函数(涉害 byte-perfect 核);伏吟/返吟/昴星/别责为族名,匹配其成员课(自任·自信·杜传/无依·无亲/虎视·掩目/不备·芜淫);始入课默认并入重审' },
		],
		validate: needValues,
		summary(p){ return `课名:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const nm = (pan.sanChuan && pan.sanChuan.name) || '';
			const pass = (p.values || []).some((v)=>{
				if(nm === v){
					return true;
				}
				const fam = LR_KE_FAMILY[v];
				if(fam){
					return fam.indexOf(nm) >= 0;	// 族长名:引擎只产成员名,恒等匹配永假(实抓)
				}
				return nm.indexOf(`${v}`.replace('课', '')) >= 0;
			});
			return { pass, actual: `课名:${nm || '?'}` };
		},
	},
	chuan_zhi: {
		category: '三传',
		keyDeps: [],
		label: '三传含支',
		defaults: { pos: 'any', values: ['子'] },
		fields: [
			{ key: 'pos', kind: 'select', label: '位', options: [{ value: 'any', label: '任一传' }, { value: '0', label: '初传' }, { value: '1', label: '中传' }, { value: '2', label: '末传' }] },
			{ key: 'values', kind: 'multiselect', label: '支', options: opt(ZHI12) },
		],
		validate: needValues,
		summary(p){ return `${({ any: '三传', 0: '初传', 1: '中传', 2: '末传' })[p.pos] || ''}含${(p.values || []).join('/')}`; },
		evaluate(pan, p, ctx){
			const zs = ctx.chuanZhi();
			const targets = p.pos === 'any' ? zs : [zs[Number(p.pos)]];
			const pass = targets.some((z)=>(p.values || []).includes(z));
			return { pass, actual: `三传:${ctx.chuanRaw().join('→') || '?'}` };
		},
	},
	chuan_jiang: {
		category: '三传',
		keyDeps: ['diurnal'],
		label: '三传天将',
		defaults: { pos: 'any', values: ['贵人'] },
		fields: [
			{ key: 'pos', kind: 'select', label: '位', options: [{ value: 'any', label: '任一传' }, { value: '0', label: '初传' }, { value: '1', label: '中传' }, { value: '2', label: '末传' }] },
			{ key: 'values', kind: 'multiselect', label: '天将', options: opt(TianJiang) },
		],
		validate: needValues,
		summary(p){ return `${({ any: '三传', 0: '初传', 1: '中传', 2: '末传' })[p.pos] || ''}乘${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const tj = (pan.sanChuan && pan.sanChuan.tianJiang) || [];
			const targets = p.pos === 'any' ? tj : [tj[Number(p.pos)]];
			const pass = targets.some((j)=>(p.values || []).includes(j));
			return { pass, actual: `三传天将:${tj.join('、') || '?'}` };
		},
	},
	chuan_liuqin: {
		category: '三传',
		keyDeps: [],
		label: '三传六亲',
		defaults: { pos: '0', values: ['妻财'] },
		fields: [
			{ key: 'pos', kind: 'select', label: '位', options: [{ value: 'any', label: '任一传' }, { value: '0', label: '初传' }, { value: '1', label: '中传' }, { value: '2', label: '末传' }] },
			{ key: 'values', kind: 'multiselect', label: '六亲', options: opt(LR_LIUQIN) },
		],
		validate: needValues,
		summary(p){ return `${({ any: '三传', 0: '初传', 1: '中传', 2: '末传' })[p.pos] || ''}为${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const lq = (pan.sanChuan && pan.sanChuan.liuQin) || [];
			const targets = p.pos === 'any' ? lq : [lq[Number(p.pos)]];
			const pass = targets.some((q)=>(p.values || []).includes(q));
			return { pass, actual: `三传六亲:${lq.join('、') || '?'}` };
		},
	},
	chuan_kong: {
		category: '三传',
		keyDeps: [],
		label: '三传旬空',
		defaults: { mode: 'none' },
		fields: [
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'none', label: '三传不犯空(净)' }, { value: 'has', label: '有传犯空' }, { value: 'first', label: '初传空(空发用)' }] },
		],
		summary(p){ return ({ none: '三传净空', has: '传中犯空', first: '初传落空' })[p.mode] || p.mode; },
		evaluate(pan, p, ctx){
			const raw = ctx.chuanRaw();
			const kongs = raw.map((c)=>`${c}`.indexOf('空') >= 0);
			let pass;
			if(p.mode === 'has'){ pass = kongs.some(Boolean); }
			else if(p.mode === 'first'){ pass = !!kongs[0]; }
			else{ pass = !kongs.some(Boolean); }
			return { pass, actual: `三传:${raw.join('→')}(空标${kongs.filter(Boolean).length}处)` };
		},
	},
	chuan_ju: {
		category: '三传',
		keyDeps: [],
		label: '三传合局',
		defaults: { values: ['水', '木', '火', '金'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '局', options: opt(['水', '木', '火', '金']), hint: '三传恰成申子辰/亥卯未/寅午戌/巳酉丑三合局' },
		],
		validate: needValues,
		summary(p){ return `三传成${(p.values || []).join('/')}局`; },
		evaluate(pan, p, ctx){
			const zs = ctx.chuanZhi();
			const hit = SANHE.find(([a, b, c])=>zs.length === 3 && [a, b, c].every((z)=>zs.includes(z)));
			const pass = !!hit && (p.values || []).includes(hit[3]);
			return { pass, actual: hit ? `三传成${hit[3]}局(${zs.join('')})` : `三传${zs.join('')}不成局` };
		},
	},
	fa_yong: {
		category: '发用',
		keyDeps: [],
		label: '发用(初传)神煞',
		defaults: { who: '驿马' },
		fields: [
			{ key: 'who', kind: 'select', label: '神', options: opt(['驿马', '日德', '禄勋', '咸池', '劫煞', '亡神', '华盖', '金神', '支将', '日破', '游都', '遁丁']), hint: '初传支=该神所值支(神煞表与 Java gods.json 机械同源)' },
		],
		summary(p){ return `${p.who}发用`; },
		evaluate(pan, p, ctx){
			const first = ctx.chuanZhi()[0];
			let vals = [];
			if(p.who === '遁丁'){
				vals = pan.xun && pan.xun['遁丁'] ? [pan.xun['遁丁']] : [];
			}else{
				const g = pan.lrGods || {};
				const all = { ...(g.gods || {}), ...(g.godsZi || {}), ...(g.godsGan || {}) };
				vals = all[p.who] || [];
			}
			const pass = !!first && vals.includes(first);
			return { pass, actual: `初传${first || '?'};${p.who}值${(vals || []).join('/') || '?'}` };
		},
	},
	tianpan_at: {
		category: '盘式',
		keyDeps: [],
		label: '天盘乘临',
		defaults: { di: '子', values: ['丑'] },
		fields: [
			{ key: 'di', kind: 'select', label: '地盘', options: opt(ZHI12) },
			{ key: 'values', kind: 'multiselect', label: '上乘天盘支', options: opt(ZHI12) },
		],
		validate: needValues,
		summary(p){ return `${p.di}上见${(p.values || []).join('/')}`; },
		evaluate(pan, p, ctx){
			const up = ctx.tianAt(p.di);
			return { pass: (p.values || []).includes(up), actual: `地盘${p.di}上乘${up || '?'}` };
		},
	},
	guiren_pos: {
		category: '盘式',
		keyDeps: ['diurnal'],
		label: '贵人临支·顺逆',
		defaults: { values: [], dir: 'any' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '贵人临地盘支(空=不限)', options: opt(ZHI12) },
			{ key: 'dir', kind: 'select', label: '行度', options: [{ value: 'any', label: '不限' }, { value: 'forward', label: '顺行(贵人升殿区)' }, { value: 'reverse', label: '逆行' }] },
		],
		summary(p){ return `贵人${(p.values && p.values.length) ? `临${p.values.join('/')}` : ''}${({ forward: '·顺', reverse: '·逆' })[p.dir] || ''}`; },
		evaluate(pan, p){
			const lay = pan.layout || {};
			const tj = lay.houseTianJiang || [];
			const gi = tj.indexOf('贵人');
			const zhi = gi >= 0 ? ZHI12[gi] : '';
			const fwd = !!lay.guirenForward;
			const zhiOk = !(p.values && p.values.length) || p.values.includes(zhi);
			const dirOk = p.dir === 'forward' ? fwd : p.dir === 'reverse' ? !fwd : true;
			return { pass: zhiOk && dirOk, actual: `贵人临${zhi || '?'}·${fwd ? '顺' : '逆'}行` };
		},
	},
	jiang_at: {
		category: '盘式',
		keyDeps: ['diurnal'],
		label: '天将临支',
		defaults: { jiang: '青龙', values: ['寅'] },
		fields: [
			{ key: 'jiang', kind: 'select', label: '天将', options: opt(TianJiang) },
			{ key: 'values', kind: 'multiselect', label: '临地盘支', options: opt(ZHI12) },
		],
		validate: needValues,
		summary(p){ return `${p.jiang}临${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const tj = (pan.layout && pan.layout.houseTianJiang) || [];
			const i = tj.indexOf(p.jiang);
			const zhi = i >= 0 ? ZHI12[i] : '';
			return { pass: (p.values || []).includes(zhi), actual: `${p.jiang}临${zhi || '?'}` };
		},
	},
	yue_jiang_is: {
		category: '盘式',
		keyDeps: [],
		label: '月将',
		defaults: { values: ['子'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '将', options: opt(ZHI12) },
		],
		validate: needValues,
		summary(p){ return `月将:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			return { pass: (p.values || []).includes(pan.yue), actual: `月将${pan.yue || '?'}` };
		},
	},
	zhou_ye: {
		category: '盘式',
		keyDeps: ['diurnal'],
		label: '昼占/夜占',
		defaults: { value: 'day' },
		fields: [
			{ key: 'value', kind: 'select', label: '取', options: [{ value: 'day', label: '昼占(日出后)' }, { value: 'night', label: '夜占' }] },
		],
		summary(p){ return p.value === 'night' ? '夜占' : '昼占'; },
		evaluate(pan, p){
			const pass = p.value === 'night' ? !pan.diurnal : !!pan.diurnal;
			return { pass, actual: pan.diurnal ? '昼(用昼贵)' : '夜(用夜贵)' };
		},
	},
	ke_shang: {
		category: '四课',
		keyDeps: [],
		label: '四课上神',
		defaults: { pos: '0', values: ['子'] },
		fields: [
			{ key: 'pos', kind: 'select', label: '课', options: [{ value: '0', label: '一课(日阳)' }, { value: '1', label: '二课(日阴)' }, { value: '2', label: '三课(辰阳)' }, { value: '3', label: '四课(辰阴)' }, { value: 'any', label: '任一课' }] },
			{ key: 'values', kind: 'multiselect', label: '上神支', options: opt(ZHI12) },
		],
		validate: needValues,
		summary(p){ return `${({ 0: '一课', 1: '二课', 2: '三课', 3: '四课', any: '四课' })[p.pos] || ''}上见${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const raw = (pan.ke && pan.ke.raw) || [];
			const ups = raw.map((k)=>stripKong(k[1]));
			const targets = p.pos === 'any' ? ups : [ups[Number(p.pos)]];
			const pass = targets.some((z)=>(p.values || []).includes(z));
			return { pass, actual: `四课上神:${ups.join('、') || '?'}` };
		},
	},
	ke_zei: {
		category: '四课',
		keyDeps: [],
		label: '贼克数',
		defaults: { kind: 'zei', min: 0, max: 0 },
		fields: [
			{ key: 'kind', kind: 'select', label: '类', options: [{ value: 'zei', label: '下贼上' }, { value: 'ke', label: '上克下' }] },
			{ key: 'min', kind: 'number', label: '≥', min: 0, max: 4 },
			{ key: 'max', kind: 'number', label: '≤', min: 0, max: 4 },
		],
		summary(p){ return `${p.kind === 'ke' ? '上克下' : '下贼上'} ${p.min}~${p.max}课`; },
		evaluate(pan, p){
			const raw = (pan.ke && pan.ke.raw) || [];
			let n = 0;
			raw.forEach((k)=>{
				const up = stripKong(k[1]);
				const downCell = `${k[2] || ''}`.slice(-1);
				const upWx = ZHI_WX[up];
				const downWx = ZHI_WX[downCell] || ({ 甲: '木', 乙: '木', 丙: '火', 丁: '火', 戊: '土', 己: '土', 庚: '金', 辛: '金', 壬: '水', 癸: '水' })[downCell];
				if(!upWx || !downWx){ return; }
				if(p.kind === 'ke' ? WX_KE[upWx] === downWx : WX_KE[downWx] === upWx){ n++; }
			});
			const lo = Number(p.min) || 0;
			const hi = Number(p.max);
			const hiv = Number.isFinite(hi) ? hi : 4;
			return { pass: n >= lo && n <= hiv, actual: `${p.kind === 'ke' ? '上克下' : '下贼上'}${n}课` };
		},
	},
	day_ganzhi: {
		category: '日时',
		keyDeps: [],
		label: '日柱干支',
		defaults: { values: ['甲子'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '干支/干/支', options: opt([...GAN10, ...ZHI12, ...Array.from({ length: 60 }, (_, i)=>`${GAN10[i % 10]}${ZHI12[i % 12]}`)]) },
		],
		validate: needValues,
		summary(p){ return `日柱:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const gz = ((pan.fourColumns || {}).day || {}).ganzi || ((pan.fourColumns || {}).day || {}).ganZhi || '';
			const pass = (p.values || []).some((v)=>v.length === 2 ? gz === v : gz.indexOf(v) >= 0);
			return { pass, actual: `日柱${gz || '?'}` };
		},
	},
	hour_zhi: {
		category: '日时',
		keyDeps: [],
		label: '占时地支',
		defaults: { values: ['午'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '支', options: opt(ZHI12) },
		],
		validate: needValues,
		summary(p){ return `占时:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const gz = ((pan.fourColumns || {}).time || {}).ganzi || ((pan.fourColumns || {}).time || {}).ganZhi || '';
			return { pass: (p.values || []).includes(gz.charAt(1)), actual: `占时${gz || '?'}` };
		},
	},
	shensha_at: {
		category: '神煞',
		keyDeps: ['monthZhi'],
		label: '神煞值支',
		defaults: { who: '日德', values: ['寅'] },
		fields: [
			{ key: 'who', kind: 'select', label: '神', options: opt(['日德', '禄勋', '驿马', '咸池', '劫煞', '亡神', '华盖', '金神', '支将', '日破', '游都', '长生(水土同)', '干墓(水土同)', '天德', '月德', '月破']) },
			{ key: 'values', kind: 'multiselect', label: '值', options: opt([...ZHI12, ...GAN10]), hint: '天德或值干(表源同 Java gods.json)' },
		],
		validate: needValues,
		summary(p){ return `${p.who}值${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const g = pan.lrGods || {};
			const all = { ...(g.gods || {}), ...(g.godsZi || {}), ...(g.godsGan || {}), ...(g.godsMonth || {}) };
			const vals = all[p.who] || [];
			const pass = (vals || []).some((v)=>(p.values || []).includes(v));
			return { pass, actual: `${p.who}:${(vals || []).join('/') || '(无值)'}` };
		},
	},
	taisui_god_at: {
		category: '神煞',
		keyDeps: ['yearZhi'],
		label: '太岁十二神值支',
		defaults: { who: '岁驾', values: ['子'] },
		fields: [
			{ key: 'who', kind: 'select', label: '神', options: opt(['岁驾', '天空', '丧门', '贯索', '官符', '死符', '岁破', '暴败', '白虎', '天德', '吊客', '病符', '剑锋', '地雌', '钩神', '五鬼', '小耗', '阑干', '天厄', '天雄', '绞杀', '天狗', '蓦越', '伏尸', '孝服', '飞符', '月德', '大耗', '卷舌']), hint: '三环全谱(gods1/2/3;判定本就并三环读值,原选项仅列一环=纯遗漏)' },	// [W2] 二三环 17 名补齐
			{ key: 'values', kind: 'multiselect', label: '值支', options: opt(ZHI12) },
		],
		validate: needValues,
		summary(p){ return `${p.who}在${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const t = ((pan.lrGods || {}).godsYear || {});
			const all = { ...(t.taisui1 || {}), ...(t.taisui2 || {}), ...(t.taisui3 || {}) };
			const zhi = all[p.who] || '';
			return { pass: (p.values || []).includes(zhi), actual: `${p.who}在${zhi || '?'}` };
		},
	},
	xun_ding: {
		category: '神煞',
		keyDeps: [],
		label: '遁丁/旬空',
		defaults: { who: 'ding', values: ['丑'] },
		fields: [
			{ key: 'who', kind: 'select', label: '取', options: [{ value: 'ding', label: '遁丁(旬内丁支)' }, { value: 'kong', label: '旬空支' }] },
			{ key: 'values', kind: 'multiselect', label: '支', options: opt(ZHI12) },
		],
		validate: needValues,
		summary(p){ return `${p.who === 'kong' ? '旬空' : '遁丁'}:${(p.values || []).join('/')}`; },
		evaluate(pan, p){
			const x = pan.xun || {};
			const vals = p.who === 'kong' ? `${x['旬空'] || ''}`.split('') : [x['遁丁'] || ''];
			const pass = vals.some((v)=>(p.values || []).includes(v));
			return { pass, actual: `旬${x['旬首'] || '?'}·遁丁${x['遁丁'] || '?'}·空${x['旬空'] || '?'}` };
		},
	},
	bm_in_chuan: {
		category: '本命',
		keyDeps: ['candY'],
		label: '本命/行年入传',
		defaults: { who: 'ming', mode: 'in' },
		fields: [
			{ key: 'who', kind: 'select', label: '取', options: [{ value: 'ming', label: '本命支' }, { value: 'xingnian', label: '行年支' }] },
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'in', label: '入三传' }, { value: 'not_in', label: '不入三传' }, { value: 'fayong', label: '发用(为初传)' }] },
		],
		summary(p){ return `${p.who === 'xingnian' ? '行年' : '本命'}${({ in: '入传', not_in: '不入传', fayong: '发用' })[p.mode] || ''}`; },
		evaluate(pan, p, ctx){
			const n = ctx.natal;
			if(!n || !(n.mingZhi || n.bornYear || n.xingnianZhi)){ return { pass: false, actual: '未设用事人本命(本命支/行年支)' }; }
			const z = p.who === 'xingnian' ? ctx.xingnian() : n.mingZhi;
			if(!z){ return { pass: false, actual: `未设${p.who === 'xingnian' ? '行年' : '本命'}支` }; }
			const zs = ctx.chuanZhi();
			let pass;
			if(p.mode === 'fayong'){ pass = zs[0] === z; }
			else if(p.mode === 'not_in'){ pass = !zs.includes(z); }
			else{ pass = zs.includes(z); }
			return { pass, actual: `${p.who === 'xingnian' ? '行年' : '本命'}${z};三传${zs.join('')}` };
		},
	},
	bm_shang_jiang: {
		category: '本命',
		keyDeps: ['diurnal', 'candY'],
		label: '本命/行年上神天将',
		defaults: { who: 'ming', values: ['贵人', '青龙', '六合', '太常', '天后'] },
		fields: [
			{ key: 'who', kind: 'select', label: '取', options: [{ value: 'ming', label: '本命支上' }, { value: 'xingnian', label: '行年支上' }] },
			{ key: 'values', kind: 'multiselect', label: '所乘天将', options: opt(TianJiang) },
		],
		validate: needValues,
		summary(p){ return `${p.who === 'xingnian' ? '行年' : '本命'}乘${(p.values || []).join('/')}`; },
		evaluate(pan, p, ctx){
			const n = ctx.natal;
			if(!n || !(n.mingZhi || n.bornYear || n.xingnianZhi)){ return { pass: false, actual: '未设用事人本命(本命支/行年支)' }; }
			const z = p.who === 'xingnian' ? ctx.xingnian() : n.mingZhi;
			if(!z){ return { pass: false, actual: `未设${p.who === 'xingnian' ? '行年' : '本命'}支` }; }
			const j = ctx.jiangAt(z);
			return { pass: (p.values || []).includes(j), actual: `${z}上乘${j || '?'}` };
		},
	},
	chuan_chong_ri: {
		category: '发用',
		keyDeps: [],
		label: '发用与日辰关系',
		defaults: { rel: 'not_chong' },
		fields: [
			{ key: 'rel', kind: 'select', label: '关系', options: [{ value: 'not_chong', label: '初传不冲日支(避)' }, { value: 'chong', label: '初传冲日支' }, { value: 'same', label: '初传即日支(伏吟象)' }, { value: 'he', label: '初传三合日支' }] },
		],
		summary(p){ return ({ not_chong: '发用不冲日', chong: '发用冲日', same: '发用即日支', he: '发用合日' })[p.rel] || p.rel; },
		evaluate(pan, p, ctx){
			const first = ctx.chuanZhi()[0] || '';
			const dayZhi = (((pan.fourColumns || {}).day || {}).ganzi || ((pan.fourColumns || {}).day || {}).ganZhi || '').charAt(1);
			if(!first || !dayZhi){ return { pass: false, actual: '发用/日支缺' }; }
			const chong = ZHI_CHONG(dayZhi) === first;
			const same = first === dayZhi;
			const he = SANHE.some(([a, b, c])=>[a, b, c].includes(first) && [a, b, c].includes(dayZhi)) && !same;
			let pass;
			if(p.rel === 'chong'){ pass = chong; }
			else if(p.rel === 'same'){ pass = same; }
			else if(p.rel === 'he'){ pass = he; }
			else{ pass = !chong; }
			return { pass, actual: `初传${first}·日支${dayZhi}(${chong ? '冲' : same ? '同' : he ? '合' : '平'})` };
		},
	},
	chuan_dungan: {
		category: '三传',
		keyDeps: [],
		label: '三传遁干',
		defaults: { pos: 'any', values: ['丁'] },
		fields: [
			{ key: 'pos', kind: 'select', label: '传位', options: [{ value: 'any', label: '任一传' }, { value: '0', label: '初传' }, { value: '1', label: '中传' }, { value: '2', label: '末传' }] },
			{ key: 'values', kind: 'multiselect', label: '遁干(任一)', options: opt(['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']), hint: '旬内遁干已随三传产出(cuang 首字);空亡传无遁干不判' },
		],
		validate: needValues,
		summary(p){ return `${({ any: '三传', 0: '初传', 1: '中传', 2: '末传' })[p.pos] || '三传'}遁${(p.values || []).join('/')}`; },
		evaluate(pan, p, ctx){
			const raw = ctx.chuanRaw();
			// cuang 形='遁干+支' 或 '空+支':首字∈十干才是遁干(「空」不是)。
			const gans = raw.map((c)=>{ const h = `${c || ''}`.charAt(0); return '甲乙丙丁戊己庚辛壬癸'.indexOf(h) >= 0 ? h : ''; });
			const scope = p.pos === 'any' || p.pos === undefined ? gans : [gans[Number(p.pos)] || ''];
			const pass = (p.values || []).some((v)=>scope.includes(v));
			return { pass, actual: `三传遁干:${gans.map((g, i)=>`${['初', '中', '末'][i]}${g || '—'}`).join(' ')}` };
		},
	},
	xiaoju_hit: {
		category: '课体',
		keyDeps: ['diurnal'],
		label: '小局(泆女狡童元胎…)',
		defaults: { mode: 'with', values: ['yinv'] },
		fields: [
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'with', label: '命中任一' }, { value: 'without', label: '全不命中(避局)' }] },
			{ key: 'values', kind: 'multiselect', label: '小局(65 类)', options: Object.keys(XIAO_JU_META).map((k)=>({ value: k, label: XIAO_JU_META[k].name })), hint: '判定=主页右栏小局面同函数;涉日月宿位的局在扫描侧无星历供数不判(恒不命中)' },
		],
		validate: needValues,
		summary(p){ return `${p.mode === 'without' ? '避' : ''}小局:${(p.values || []).map((v)=>(XIAO_JU_META[v] ? XIAO_JU_META[v].name : v)).join('/')}`; },
		evaluate(pan, p, ctx){
			const hits = ctx.refs().xiaoJu.map((r)=>r.key);
			const sel = new Set(p.values || []);
			const got = hits.filter((k)=>sel.has(k));
			const pass = p.mode === 'without' ? got.length === 0 : got.length > 0;
			return { pass, actual: `小局:${hits.length ? hits.map((k)=>(XIAO_JU_META[k] ? XIAO_JU_META[k].name : k)).join('、') : '无'}` };
		},
	},
	dage_hit: {
		category: '课体',
		keyDeps: [],
		label: '大格(元首重审知一…)',
		defaults: { mode: 'with', values: ['yuanshou'] },
		fields: [
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'with', label: '命中任一' }, { value: 'without', label: '全不命中(避格)' }] },
			{ key: 'values', kind: 'multiselect', label: '大格(10 类)', options: Object.keys(DA_GE_META).map((k)=>({ value: k, label: DA_GE_META[k].name })), hint: '判定=主页右栏大格面同函数(含结构判,非仅课名映射)' },
		],
		validate: needValues,
		summary(p){ return `${p.mode === 'without' ? '避' : ''}大格:${(p.values || []).map((v)=>(DA_GE_META[v] ? DA_GE_META[v].name : v)).join('/')}`; },
		evaluate(pan, p, ctx){
			const hits = ctx.refs().daGe.map((r)=>r.key);
			const sel = new Set(p.values || []);
			const got = hits.filter((k)=>sel.has(k));
			const pass = p.mode === 'without' ? got.length === 0 : got.length > 0;
			return { pass, actual: `大格:${hits.length ? hits.map((k)=>(DA_GE_META[k] ? DA_GE_META[k].name : k)).join('、') : '无'}` };
		},
	},
	ke_pos_zei: {
		category: '四课',
		keyDeps: [],
		label: '贼克位置(第N课上下)',
		defaults: { pos: '1', rel: 'shang_ke_xia' },
		fields: [
			{ key: 'pos', kind: 'select', label: '课位', options: [{ value: '1', label: '一课' }, { value: '2', label: '二课' }, { value: '3', label: '三课' }, { value: '4', label: '四课' }] },
			{ key: 'rel', kind: 'select', label: '关系', options: [{ value: 'shang_ke_xia', label: '上克下' }, { value: 'xia_zei_shang', label: '下贼上' }, { value: 'sheng', label: '上下相生' }, { value: 'bi', label: '上下比和' }] },
		],
		summary(p){ return `${p.pos || '1'}课${({ shang_ke_xia: '上克下', xia_zei_shang: '下贼上', sheng: '相生', bi: '比和' })[p.rel] || ''}`; },
		evaluate(pan, p){
			const raw = (pan.ke && pan.ke.raw) || [];
			const i = Math.max(0, Math.min(3, Number(p.pos || '1') - 1));
			const k = raw[i] || [];
			const up = stripKong(k[1]);
			// 一课的「下」是日干(主页 keDown 同口径)——干→寄宫支再论五行(正锚实抓 ke1 下='乙');
			// 寄宫单源=LRConst.GanJiZi(勿手抄表)。
			const rawDown = stripKong(k[2]);
			const down = GanJiZi[rawDown] || rawDown;
			const uw = ZHI_WX[up];
			const dw = ZHI_WX[down];
			if(!uw || !dw){ return { pass: false, actual: `${i + 1}课:${up || '?'}/${down || '?'}` }; }
			const SHENG = { 木: '火', 火: '土', 土: '金', 金: '水', 水: '木' };
			let pass = false;
			if(p.rel === 'shang_ke_xia'){ pass = WX_KE[uw] === dw; }
			else if(p.rel === 'xia_zei_shang'){ pass = WX_KE[dw] === uw; }
			else if(p.rel === 'sheng'){ pass = SHENG[uw] === dw || SHENG[dw] === uw; }
			else{ pass = uw === dw; }
			return { pass, actual: `${i + 1}课上${up}(${uw})下${rawDown}${GanJiZi[rawDown] ? `寄${down}` : ''}(${dw})` };
		},
	},
	zhu_wangshuai: {
		category: '三传',
		keyDeps: [],
		label: '传/干十二长生(旺衰)',
		defaults: { who: 'fa_yong', phases: ['长生', '帝旺'] },
		fields: [
			{ key: 'who', kind: 'select', label: '主体', options: [{ value: 'fa_yong', label: '发用(初传)' }, { value: 'zhong', label: '中传' }, { value: 'mo', label: '末传' }, { value: 'ri_gan', label: '日干(于占时支)' }] },
			{ key: 'phases', kind: 'multiselect', label: '长生态(任一)', options: opt(['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养']), hint: '日干于该支的十二长生(八字同源 changShengOf;阳顺阴逆)' },
		],
		validate: (p)=>(!p.phases || !p.phases.length) ? '至少选择一项' : '',
		summary(p){ return `${({ fa_yong: '发用', zhong: '中传', mo: '末传', ri_gan: '日干' })[p.who] || '发用'}:${(p.phases || []).join('/')}`; },
		evaluate(pan, p, ctx){
			const dayGz = (pan.fourColumns && pan.fourColumns.day && (pan.fourColumns.day.ganzi || pan.fourColumns.day.ganZhi)) || '';
			const gan = `${dayGz}`.charAt(0);
			let zhi = '';
			if(p.who === 'ri_gan'){
				const tGz = (pan.fourColumns && pan.fourColumns.time && (pan.fourColumns.time.ganzi || pan.fourColumns.time.ganZhi)) || '';
				zhi = `${tGz}`.charAt(1);
			}else{
				const idx = ({ fa_yong: 0, zhong: 1, mo: 2 })[p.who || 'fa_yong'] || 0;
				zhi = ctx.chuanZhi()[idx] || '';
			}
			if(!gan || !zhi){ return { pass: false, actual: '旺衰:—' }; }
			let ph = '';
			try{ ph = changShengOf(gan, zhi, 2) || ''; }catch(e){ ph = ''; }
			return { pass: !!ph && (p.phases || []).includes(ph), actual: `${gan}于${zhi}=${ph || '—'}` };
		},
	},
};

// ── 树工厂/摘要/编译(与其它择日技法同构) ──
export function newLiurengLeaf(type, joiner){
	const spec = LIURENG_CONDITION_TYPES[type];
	return {
		kind: 'leaf',
		type,
		negate: false,
		joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all',
		params: spec ? JSON.parse(JSON.stringify(spec.defaults)) : {},
	};
}
export function newLiurengGroup(joiner){
	return { kind: 'group', negate: false, joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all', children: [] };
}

export function liurengLeafSummary(leaf){
	const spec = leaf ? LIURENG_CONDITION_TYPES[leaf.type] : null;
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
		const spec = LIURENG_CONDITION_TYPES[node.type];
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
export function compileLiurengTree(root){
	return compileSelf(root);
}
