// [Z1·黄历择日] 条件注册表(日粒度)。判定单源=components/calendar/huangliDay.buildHuangliDay
// (老黄历卡片/吉日榜/日子馆/AI 快照同一函数)——主黄历算法修正,择日自动跟(制度层1)。
// 值域枚举同源 import(lunar-javascript LunarUtil + TONGSHU_TERMS),零手抄:词表/神名变更自动跟随。
// spec 契约与 QIMEN_CONDITION_TYPES 逐字段同构:{category,label,defaults,fields[],validate,
// summary,evaluate(day,params,ctx)→{pass,actual}};ctx=makeHuangliZeriEvalCtx(day)。
// 一键一行 Tab 缩进(preflight 键集契约)。
import { LunarUtil } from 'lunar-javascript';
import { TONGSHU_TERMS, YONGSHI_YIJI_SYN, yongshiVerdict } from '../../calendar/tongshuData.js';
// [W6 全谱轮] 通书五流派判定=通书页同函数(直调,主表修正择日自动跟);玄空 mingYear 缺省=天地判。
import donggongDay from '../../tongshu/donggong.js';
import { wutuForDate } from '../../tongshu/wutu.js';
import { qimenDieShuDay } from '../../tongshu/qimenDieShu.js';
import { sanyuanLiexiuDay } from '../../tongshu/sanyuanLiexiu.js';
import { xuankongDay } from '../../tongshu/xuankong.js';
import { GROUP_TYPES, JOINER_CN } from './conditionTypes.js';

export { GROUP_TYPES, JOINER_CN };

// ── 同源值域 ──
const uniq = (arr)=>[...new Set(arr.filter(Boolean))];
// 用事词表:TONGSHU_TERMS 分类展开(婚姻/营建/…);lunar 宜忌词与其高度重合,另留自由输入。
// [Q-480/T-442] 同一用事名可跨两类出现(如「启钻」既在营建又在丧葬):按 value 去重并把类名合并进 label,
// 否则下拉里会并存两个同 value 的选项(antd 按 value 作 key → 选一项两项同亮),四类条件全中招。
export const HUANGLI_TERM_OPTIONS = (()=>{
	const order = [];
	const byName = new Map();
	Object.keys(TONGSHU_TERMS).forEach((cat)=>{
		(TONGSHU_TERMS[cat] || []).forEach((t)=>{
			if(!t || !t.name){ return; }
			if(!byName.has(t.name)){ byName.set(t.name, []); order.push(t.name); }
			const cats = byName.get(t.name);
			if(cats.indexOf(cat) < 0){ cats.push(cat); }
		});
	});
	return order.map((name)=>({ value: name, label: `${name}(${byName.get(name).join('·')})` }));
})();
export const JIANCHU_NAMES = uniq(LunarUtil.ZHI_XING || []);            // 建除十二神
export const TIANSHEN_NAMES = uniq(LunarUtil.TIAN_SHEN || []);          // 黄黑道十二值神
// 廿八宿=千年不变常量(LunarUtil.XIU 是「支+周」映射表,值域含 56 组合项不适取);硬编码合法。
export const XIU_NAMES = ['角', '亢', '氐', '房', '心', '尾', '箕', '斗', '牛', '女', '虚', '危', '室', '壁', '奎', '娄', '胃', '昴', '毕', '觜', '参', '井', '鬼', '柳', '星', '张', '翼', '轸'];
export const LIUYAO_NAMES = uniq(LunarUtil.LIU_YAO || []);              // 六曜
export const SHENGXIAO_NAMES = uniq(LunarUtil.SHENGXIAO || []);         // 十二生肖
const GAN10 = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const ZHI12 = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const WUXING5 = ['金', '木', '水', '火', '土'];
const LUNAR_DAY_CN = ['初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十', '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十', '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十'];
const WEEK_CN = ['一', '二', '三', '四', '五', '六', '日'];
const JIEQI_24 = ['立春', '雨水', '惊蛰', '春分', '清明', '谷雨', '立夏', '小满', '芒种', '夏至', '小暑', '大暑', '立秋', '处暑', '白露', '秋分', '寒露', '霜降', '立冬', '小雪', '大雪', '冬至', '小寒', '大寒'];

const opt = (arr)=>arr.map((v)=>({ value: v, label: v }));
const MATCH_MODE_FIELD = { key: 'matchMode', kind: 'select', label: '匹配', options: [{ value: 'any', label: '任一命中' }, { value: 'all', label: '全部命中' }], hint: '多选值之间的组合方式' };
const needValues = (p)=>(!p.values || !p.values.length) ? '至少选择一项' : '';
const listHit = (list, values, mode)=>{
	const set = new Set(list || []);
	const vals = values || [];
	const hit = vals.filter((v)=>set.has(v));
	return { pass: mode === 'all' ? hit.length === vals.length && vals.length > 0 : hit.length > 0, hit };
};
// [Q-271/ZC-18] 用事词命中经同义展开(与通书「用事裁决」yongshiVerdict 同一张 YONGSHI_YIJI_SYN):通书用事词表里
// 开山 / 平整 / 立向 / 立契 / 造舟船 / 设醮 / 剃头 / 迁徙 在日宜忌表以异名出现(动土·起基 / 平治道涂 / 竖柱·上梁 / 立券 /
// 造船 / 斋醮 / 理发 / 移徙),此前按字面命中 → 宜含恒假、忌不含恒真。酝酿在日宜忌表无同义条目(仍按字面)。
const expandTerm = (v)=>uniq([v].concat(YONGSHI_YIJI_SYN[v] || []));
const termListHit = (list, values, mode)=>{
	const set = new Set(list || []);
	const vals = values || [];
	const hit = vals.filter((v)=>expandTerm(v).some((w)=>set.has(w)));
	return { pass: mode === 'all' ? hit.length === vals.length && vals.length > 0 : hit.length > 0, hit };
};
const modeText = (p)=>(p.matchMode === 'all' ? '(全部)' : '');

// 惰性求值上下文(签名同构 makeQimenEvalCtx;day 为 buildHuangliDay 全算好的纯对象,直挂即可)。
export function makeHuangliZeriEvalCtx(day){
	return { day };
}

export const HUANGLI_CONDITION_TYPES = {
	yi_has: {
		category: '用事',
		label: '宜含事项',
		defaults: { values: ['嫁娶'], matchMode: 'any' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '事项', options: HUANGLI_TERM_OPTIONS, hint: '通书用事词表(同源);当日「宜」列表须含所选(异名按同义表展开:开山→动土/起基、立向→竖柱/上梁、立契→立券、剃头→理发、迁徙→移徙…)' },
			MATCH_MODE_FIELD,
		],
		validate: needValues,
		summary(p){ return `宜:${(p.values || []).join('/')}${modeText(p)}`; },
		evaluate(day, p){
			const { pass, hit } = termListHit(day.yi, p.values, p.matchMode);
			return { pass, actual: `宜:${(day.yi || []).join('、') || '无'}${hit.length ? `(中:${hit.join('/')})` : ''}` };
		},
	},
	ji_not: {
		category: '用事',
		label: '忌避事项',
		defaults: { values: ['嫁娶'], mode: 'without' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '事项', options: HUANGLI_TERM_OPTIONS },
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'without', label: '忌中不含(可办)' }, { value: 'with', label: '忌中含(避开日)' }] },
		],
		validate: needValues,
		summary(p){ return `${p.mode === 'with' ? '忌含' : '忌不含'}:${(p.values || []).join('/')}`; },
		evaluate(day, p){
			const { hit } = termListHit(day.ji, p.values, 'any');
			const pass = p.mode === 'with' ? hit.length > 0 : hit.length === 0;
			return { pass, actual: `忌:${(day.ji || []).join('、') || '无'}` };
		},
	},
	jianchu: {
		category: '神煞',
		label: '建除十二神',
		defaults: { values: ['成'], matchMode: 'any' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '值神', options: opt(JIANCHU_NAMES), hint: '建除满平定执破危成收开闭' },
		],
		validate: needValues,
		summary(p){ return `建除:${(p.values || []).join('/')}`; },
		evaluate(day, p){
			const name = day.jianchu && day.jianchu.name;
			return { pass: (p.values || []).includes(name), actual: `建除:${name || '?'}(${day.jianchu && day.jianchu.jx === 'good' ? '吉' : day.jianchu && day.jianchu.jx === 'bad' ? '凶' : '平'})` };
		},
	},
	tianshen_dao: {
		category: '神煞',
		label: '黄黑道',
		defaults: { dao: '黄道', values: [] },
		fields: [
			{ key: 'dao', kind: 'select', label: '道', options: [{ value: '黄道', label: '黄道(吉)' }, { value: '黑道', label: '黑道(凶)' }, { value: '', label: '不限' }] },
			{ key: 'values', kind: 'multiselect', label: '值神', options: opt(TIANSHEN_NAMES), hint: '空=不限值神;青龙明堂金匮天德玉堂司命为黄道六神' },
		],
		validate(p){ return (!p.dao && (!p.values || !p.values.length)) ? '道与值神至少择一' : ''; },
		summary(p){ return `${p.dao || ''}${(p.values || []).length ? `:${p.values.join('/')}` : ''}` || '黄黑道'; },
		evaluate(day, p){
			const ts = day.tianshen || {};
			const daoOk = !p.dao || ts.type === p.dao;
			const nameOk = !(p.values && p.values.length) || p.values.includes(ts.name);
			return { pass: daoOk && nameOk, actual: `${ts.type || '?'}·${ts.name || '?'}(${ts.luck || '?'})` };
		},
	},
	zhixiu: {
		category: '神煞',
		label: '值宿(廿八宿)',
		defaults: { values: [], luck: '' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '宿', options: opt(XIU_NAMES), hint: '空=不限宿名' },
			{ key: 'luck', kind: 'select', label: '吉凶', options: [{ value: '', label: '不限' }, { value: '吉', label: '吉宿' }, { value: '凶', label: '凶宿' }] },
		],
		validate(p){ return ((!p.values || !p.values.length) && !p.luck) ? '宿名与吉凶至少择一' : ''; },
		summary(p){ return `宿:${(p.values || []).join('/') || '任意'}${p.luck ? `·${p.luck}` : ''}`; },
		evaluate(day, p){
			const x = day.xiu || {};
			const nameOk = !(p.values && p.values.length) || p.values.includes(x.name);
			const luckOk = !p.luck || x.luck === p.luck;
			return { pass: nameOk && luckOk, actual: `${x.name || '?'}宿(${x.luck || '?'})` };
		},
	},
	jishen_has: {
		category: '神煞',
		label: '吉神宜趋',
		defaults: { values: ['天德'], matchMode: 'any' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '吉神', options: opt(uniq(['天德', '月德', '天德合', '月德合', '天赦', '天愿', '月恩', '四相', '时德', '三合', '六合', '天喜', '天医', '玉堂', '司命', '青龙', '明堂', '金匮', '不将', '阳德', '阴德', '福生', '天巫', '解神', '普护', '圣心', '益后', '续世', '母仓', '五富', '生气', '临日', '敬安', '除神', '鸣吠'])), hint: '当日吉神列表须含所选(lunar 词表常见项)' },
			MATCH_MODE_FIELD,
		],
		validate: needValues,
		summary(p){ return `吉神:${(p.values || []).join('/')}${modeText(p)}`; },
		evaluate(day, p){
			const { pass, hit } = listHit(day.jishen, p.values, p.matchMode);
			return { pass, actual: `吉神:${(day.jishen || []).join('、') || '无'}${hit.length ? `(中:${hit.join('/')})` : ''}` };
		},
	},
	xiongsha_not: {
		category: '神煞',
		label: '凶煞回避',
		// [Q-271/ZC-19] 库内实名「致死」(lunar 神煞词表无「受死」;yearAuspicious 已同名对齐):缺省与选项同改,否则该项恒不命中。
		defaults: { values: ['月破', '致死', '四废'], mode: 'without' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '凶煞', options: opt(uniq(['月破', '大耗', '致死', '四废', '五墓', '灾煞', '天火', '月煞', '月虚', '月刑', '月害', '劫煞', '天罡', '死神', '往亡', '归忌', '血支', '血忌', '五离', '八专', '触水龙', '天贼', '五虚', '土符', '大时', '大败', '咸池', '小耗', '四击', '四耗', '四忌', '四穷', '九坎', '九焦', '重日', '复日'])), hint: '当日凶煞列表' },
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'without', label: '全不出现(净日)' }, { value: 'with', label: '出现任一(排查日)' }] },
		],
		validate: needValues,
		summary(p){ return `${p.mode === 'with' ? '凶煞含' : '避凶煞'}:${(p.values || []).join('/')}`; },
		evaluate(day, p){
			const { hit } = listHit(day.xiongsha, p.values, 'any');
			const pass = p.mode === 'with' ? hit.length > 0 : hit.length === 0;
			return { pass, actual: `凶煞:${(day.xiongsha || []).join('、') || '无'}` };
		},
	},
	nine_star: {
		category: '神煞',
		label: '九星值日',
		defaults: { values: ['一'], matchMode: 'any' },
		fields: [
			// 锚实抓:lunar getDayNineStar().getNumber() 返回**中文数字**(如「三」),value 必须同域。
			{ key: 'values', kind: 'multiselect', label: '九星', options: [{ value: '一', label: '一白水' }, { value: '二', label: '二黑土' }, { value: '三', label: '三碧木' }, { value: '四', label: '四绿木' }, { value: '五', label: '五黄土' }, { value: '六', label: '六白金' }, { value: '七', label: '七赤金' }, { value: '八', label: '八白土' }, { value: '九', label: '九紫火' }] },
		],
		validate: needValues,
		summary(p){ return `九星:${(p.values || []).join('/')}`; },
		evaluate(day, p){
			const ns = day.nineStar || {};
			return { pass: (p.values || []).includes(`${ns.number}`), actual: `九星:${ns.name || '?'}` };
		},
	},
	chong_shengxiao: {
		category: '神煞',
		label: '冲煞生肖',
		defaults: { values: [], mode: 'without' },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '生肖', options: opt(SHENGXIAO_NAMES), hint: '用事人生肖:选「不冲」保本命不犯冲' },
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'without', label: '不冲所选肖' }, { value: 'with', label: '冲所选肖' }] },
		],
		validate: needValues,
		summary(p){ return `${p.mode === 'with' ? '冲' : '不冲'}:${(p.values || []).join('/')}`; },
		evaluate(day, p){
			const sx = day.chong && day.chong.shengxiao;
			const hitChong = (p.values || []).includes(sx);
			const pass = p.mode === 'with' ? hitChong : !hitChong;
			return { pass, actual: `冲${sx || '?'}(${(day.chong && day.chong.desc) || ''}) 煞${(day.chong && day.chong.sha) || '?'}` };
		},
	},
	day_ganzhi: {
		category: '历法',
		label: '日干支',
		defaults: { values: ['甲子'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '干支', options: [...GAN10.map((g)=>({ value: g, label: `${g}(日干)` })), ...ZHI12.map((z)=>({ value: z, label: `${z}(日支)` })), ...GAN10.flatMap((g, gi)=>ZHI12.filter((z, zi)=>(gi % 2) === (zi % 2)).map((z)=>({ value: `${g}${z}`, label: `${g}${z}` })))], hint: '单字=判日干或日支;两字=判整日柱(六十甲子);任一命中即中' },
		],
		validate: needValues,
		summary(p){ return `日柱:${(p.values || []).join('/')}`; },
		evaluate(day, p){
			const gz = (day.lunar && day.lunar.dayGZ) || '';
			const pass = (p.values || []).some((v)=>(`${v}`.length === 1 ? (gz.charAt(0) === v || gz.charAt(1) === v) : gz === v));
			return { pass, actual: `日柱:${gz || '?'}` };
		},
	},
	nayin_wuxing: {
		category: '历法',
		label: '日纳音五行',
		defaults: { values: ['金'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '五行', options: opt(WUXING5), hint: '按纳音名尾字判(如 海中金→金)' },
		],
		validate: needValues,
		summary(p){ return `纳音:${(p.values || []).join('/')}行`; },
		evaluate(day, p){
			const ny = day.nayin || '';
			const el = ny.charAt(ny.length - 1);
			return { pass: (p.values || []).includes(el), actual: `纳音:${ny || '?'}` };
		},
	},
	liuyao: {
		category: '历法',
		label: '六曜',
		defaults: { values: ['大安'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '六曜', options: opt(LIUYAO_NAMES) },
		],
		validate: needValues,
		summary(p){ return `六曜:${(p.values || []).join('/')}`; },
		evaluate(day, p){
			return { pass: (p.values || []).includes(day.liuyao), actual: `六曜:${day.liuyao || '?'}` };
		},
	},
	yuexiang: {
		category: '历法',
		label: '月相',
		defaults: { values: ['望'] },
		fields: [
			// 值域=LunarUtil.YUE_XIANG 同源去重(锚实抓「渐盈凸」类现代名,常用七相不覆盖)。
			{ key: 'values', kind: 'multiselect', label: '月相', options: opt(uniq(LunarUtil.YUE_XIANG || [])), hint: '按 lunar 月相名精确匹配(同源全域)' },
		],
		validate: needValues,
		summary(p){ return `月相:${(p.values || []).join('/')}`; },
		evaluate(day, p){
			return { pass: (p.values || []).includes(day.yuexiang), actual: `月相:${day.yuexiang || '?'}` };
		},
	},
	lunar_day: {
		category: '历法',
		label: '农历日',
		defaults: { values: ['初一', '十五'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '农历日', options: opt(LUNAR_DAY_CN) },
		],
		validate: needValues,
		summary(p){ return `农历:${(p.values || []).join('/')}`; },
		evaluate(day, p){
			const cn = day.lunar && day.lunar.dayCn;
			return { pass: (p.values || []).includes(cn), actual: `农历${(day.lunar && day.lunar.monthCn) || ''}月${cn || '?'}` };
		},
	},
	jieqi_day: {
		category: '历法',
		label: '节气日',
		defaults: { mode: 'is', values: [] },
		fields: [
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'is', label: '当日交节' }, { value: 'not', label: '非交节日' }] },
			// [Q-271/ZC-25] 非交节日判法只看「无交节」,限定节气不参与 → 仅当日交节时显示
			{ key: 'values', kind: 'multiselect', label: '限定节气', options: opt(JIEQI_24), hint: '空=任意节气', showIf: (p)=>p.mode !== 'not' },
		],
		summary(p){ return p.mode === 'not' ? '非节气日' : `节气日${(p.values || []).length ? `:${p.values.join('/')}` : ''}`; },
		evaluate(day, p){
			const name = day.lunar && day.lunar.jieqi;
			const isJq = !!name && (!(p.values && p.values.length) || p.values.includes(name));
			const pass = p.mode === 'not' ? !name : isJq;
			return { pass, actual: name ? `交节:${name}(${(day.lunar && day.lunar.jieqiTime) || ''})` : '非交节日' };
		},
	},
	week_day: {
		category: '历法',
		label: '星期',
		defaults: { values: ['六', '日'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '星期', options: opt(WEEK_CN), hint: '如周末择日选 六+日' },
		],
		validate: needValues,
		summary(p){ return `星期:${(p.values || []).join('/')}`; },
		evaluate(day, p){
			const w = day.solar && day.solar.week;
			return { pass: (p.values || []).includes(w), actual: `星期${w || '?'}${(day.solar && day.solar.festivals && day.solar.festivals.length) ? `·${day.solar.festivals.join('/')}` : ''}` };
		},
	},
	good_hour: {
		category: '时辰',
		label: '当日吉时',
		defaults: { zhis: [], minCount: 1 },
		fields: [
			{ key: 'zhis', kind: 'multiselect', label: '限定时支', options: opt(ZHI12), hint: '空=任意时辰;选支=该时辰须为黄道吉时' },
			// [Q-271/ZC-25] 每日 13 条时辰(子时早晚各一)中黄道吉时恒 6 或 7 条:上限 7(8–13 恒假);子时双计已注明。
			{ key: 'minCount', kind: 'number', label: '吉时数≥', min: 1, max: 7, hint: '当日黄道吉时总数下限(每日恒 6 或 7 条,早晚子时各计一条;限定时支时=命中支数下限)' },
		],
		summary(p){ return (p.zhis && p.zhis.length) ? `吉时含:${p.zhis.join('/')}` : `吉时≥${p.minCount || 1}`; },
		evaluate(day, p){
			const times = day.times || [];
			const goodZhis = times.filter((t)=>t.luck === '吉').map((t)=>`${t.ganzhi || ''}`.charAt(1)).filter(Boolean);
			const min = Math.max(1, Number(p.minCount) || 1);
			let pass;
			if(p.zhis && p.zhis.length){
				const hit = p.zhis.filter((z)=>goodZhis.includes(z));
				pass = hit.length >= Math.min(min, p.zhis.length);
			}else{
				pass = goodZhis.length >= min;
			}
			return { pass, actual: `吉时:${[...new Set(goodZhis)].join('、') || '无'}(${goodZhis.length}个)` };
		},
	},
	// times[] 无 zhi 键(normalizeTimes 只产 ganzhi)——时支=干支尾字(锚日 dump 实抓)。
	// eslint-disable-next-line
	hour_yiji: {
		category: '时辰',
		label: '时辰宜忌(逐时)',
		defaults: { mode: 'yi', terms: ['祭祀'], hours: [] },
		fields: [
			// [Q-479/T-441 2026-09-18] 两面都是「出现即命中(判真)」:此前括注「命中即判否面」按同表词法(判否=判假)会读成反义;
			//   要表达「无时辰犯忌」请对本条件取反,与日级「忌中含(避开日)」同一写法。
			{ key: 'mode', kind: 'select', label: '判面', options: [{ value: 'yi', label: '时宜含(某时辰宜中含该事项即命中)' }, { value: 'ji', label: '时忌含(某时辰忌中含该事项即命中;要「无忌」请取反)' }] },
			{ key: 'terms', kind: 'multiselect', label: '事项(任一)', options: HUANGLI_TERM_OPTIONS, hint: 'times[].yi/ji 逐时辰宜忌(黄历页时辰卡同源);限定时辰空=任一时辰;两面均为「出现即命中」' },
			{ key: 'hours', kind: 'multiselect', label: '限定时辰(空=任一)', options: ZHI12.map((z)=>({ value: z, label: `${z}时` })) },
		],
		validate: (p)=>(!p.terms || !p.terms.length) ? '至少选择一项' : '',
		summary(p){ return `时${p.mode === 'ji' ? '忌含' : '宜含'}:${(p.terms || []).slice(0, 3).join('/')}${(p.hours && p.hours.length) ? `@${p.hours.join('')}` : ''}`; },
		evaluate(day, p){
			const times = day.times || [];
			const zhiOf = (t)=>`${t.ganzhi || ''}`.slice(-1);
			const scope = (p.hours && p.hours.length) ? times.filter((t)=>p.hours.includes(zhiOf(t))) : times;
			const key = p.mode === 'ji' ? 'ji' : 'yi';
			const hitHours = scope.filter((t)=>((t[key] || []).some((x)=>(p.terms || []).includes(x))));
			// yi 面=有任一时辰宜;ji 面=选定范围内出现该忌(常配 NOT 用「无时辰犯忌」)
			const pass = hitHours.length > 0;
			return { pass, actual: `${p.mode === 'ji' ? '时忌' : '时宜'}命中:${hitHours.map((t)=>`${zhiOf(t)}时`).join('/') || '无'}` };
		},
	},
	hour_shen: {
		category: '时辰',
		label: '时辰值神/时冲/时煞',
		defaults: { dim: 'tianshen', values: ['青龙'], hours: [] },
		fields: [
			{ key: 'dim', kind: 'select', label: '判面', options: [{ value: 'tianshen', label: '时辰值神' }, { value: 'chong', label: '时冲生肖' }, { value: 'sha', label: '时煞方' }] },
			{ key: 'values', kind: 'multiselect', label: '取值(任一)', options: [...opt(['青龙', '明堂', '金匮', '天德', '玉堂', '司命', '天刑', '朱雀', '白虎', '天牢', '玄武', '勾陈']), ...opt(['鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪']), ...opt(['煞东', '煞南', '煞西', '煞北'])], hint: '跨面选值不命中即判否;times[].tianshen/chong/sha(时辰卡同源)' },
			{ key: 'hours', kind: 'multiselect', label: '限定时辰(空=任一)', options: ZHI12.map((z)=>({ value: z, label: `${z}时` })) },
		],
		validate: (p)=>(!p.values || !p.values.length) ? '至少选择一项' : '',
		summary(p){ return `时${({ tianshen: '值神', chong: '冲', sha: '煞' })[p.dim] || '值神'}:${(p.values || []).join('/')}${(p.hours && p.hours.length) ? `@${p.hours.join('')}` : ''}`; },
		evaluate(day, p){
			const times = day.times || [];
			const zhiOf = (t)=>`${t.ganzhi || ''}`.slice(-1);
			const scope = (p.hours && p.hours.length) ? times.filter((t)=>p.hours.includes(zhiOf(t))) : times;
			const dim = p.dim || 'tianshen';
			// [Q-269/T-257] 时冲判面:选项是生肖,数据 times[].chong 是地支(dump 实抓「子」)→ 生肖映射到地支后再含判;
			// 值本身已是地支/含地支的旧存档照旧;sha 值无「煞」前缀(dump 实抓「西」)——统一含判+煞前缀剥离。
			const SX2ZHI = { 鼠: '子', 牛: '丑', 虎: '寅', 兔: '卯', 龙: '辰', 蛇: '巳', 马: '午', 羊: '未', 猴: '申', 鸡: '酉', 狗: '戌', 猪: '亥' };
			const hit = scope.filter((t)=>{
				const v = `${t[dim] || ''}`;
				return !!v && (p.values || []).some((x)=>{
					const raw = `${x}`.replace('煞', '');
					if(dim === 'chong'){ const z = SX2ZHI[raw]; return v.indexOf(raw) >= 0 || (!!z && v.indexOf(z) >= 0); }
					return v.indexOf(raw) >= 0;
				});
			});
			return { pass: hit.length > 0, actual: hit.length ? hit.map((t)=>`${zhiOf(t)}时${t[dim]}`).join(' ') : `无命中(${dim})` };
		},
	},
	tongshu_verdict: {
		category: '通书',
		label: '通书流派日判(董公/乌兔)',
		defaults: { school: 'donggong', want: ['good'] },
		fields: [
			{ key: 'school', kind: 'select', label: '流派', options: [{ value: 'donggong', label: '董公择日' }, { value: 'wutu', label: '天元乌兔' }] },
			{ key: 'want', kind: 'multiselect', label: '判级(任一)', options: [{ value: 'good', label: '吉(董公三吉星/乌兔吉星)' }, { value: 'bad', label: '凶(金神七煞/乌兔凶星)' }, { value: 'neutral', label: '平(仅董公)' }], hint: '判定=通书页同函数(donggongDay.verdict/wutuForDate.jx)' },
		],
		validate: (p)=>(!p.want || !p.want.length) ? '至少选择一项' : '',
		summary(p){ return `${p.school === 'wutu' ? '乌兔' : '董公'}:${(p.want || []).map((w)=>({ good: '吉', bad: '凶', neutral: '平' })[w] || w).join('/')}`; },
		evaluate(day, p){
			const ymd = `${(day.solar && day.solar.ymd) || ''}`.split('-').map(Number);
			if(ymd.length < 3 || !ymd[0]){ return { pass: false, actual: '通书:—' }; }
			const args = { y: ymd[0], m: ymd[1], d: ymd[2] };
			try{
				if(p.school === 'wutu'){
					const r = wutuForDate(args);
					return { pass: (p.want || []).includes(r.jx), actual: `乌兔:${r.star}(${r.jx === 'good' ? '吉' : '凶'})` };
				}
				const r = donggongDay(args);
				const lv = (r.verdict && r.verdict.level) || 'neutral';
				return { pass: (p.want || []).includes(lv), actual: `董公:${(r.verdict && r.verdict.text) || '—'}` };
			}catch(e){
				return { pass: false, actual: '通书:计算异常' };
			}
		},
	},
	tongshu_star: {
		category: '通书',
		label: '通书值星(三吉星/列宿)',
		defaults: { school: 'donggong', names: ['煞贡'] },
		fields: [
			{ key: 'school', kind: 'select', label: '流派', options: [{ value: 'donggong', label: '董公三吉星' }, { value: 'sanyuan', label: '三垣列宿加临' }] },
			// [Q-271/ZC-25] 三垣派只有「任意」有意义(煞贡/直星/人专是董公三吉星名,三垣下恒假);留空=全判(与 validate 同口径)。
			{ key: 'names', kind: 'multiselect', label: '星名(任一;三垣派选「任意」或留空=有列宿加临即命中)', options: opt(['煞贡', '直星', '人专', '任意']), hint: '董公=煞贡/直星/人专(或「任意」);三垣=当日有列宿加临即命中,只认「任意」或留空' },
		],
		validate: (p)=>((p.school !== 'sanyuan' && (!p.names || !p.names.length)) ? '至少选择一项' : ''),
		summary(p){ return `${p.school === 'sanyuan' ? '三垣列宿' : '董公吉星'}:${(p.names || []).join('/')}`; },
		evaluate(day, p){
			const ymd = `${(day.solar && day.solar.ymd) || ''}`.split('-').map(Number);
			if(ymd.length < 3 || !ymd[0]){ return { pass: false, actual: '通书:—' }; }
			const args = { y: ymd[0], m: ymd[1], d: ymd[2] };
			try{
				if(p.school === 'sanyuan'){
					const r = sanyuanLiexiuDay(args);
					const names = (r.hitStars || []).map((x)=>x.name);
					const pass = names.length > 0 && (!(p.names || []).length || (p.names || []).includes('任意') || (p.names || []).some((n)=>names.includes(n)));
					return { pass, actual: `列宿加临:${names.join('/') || '无'}` };
				}
				const r = donggongDay(args);
				const pass = !!r.sanxing && ((p.names || []).includes('任意') || (p.names || []).includes(r.sanxing));
				return { pass, actual: `董公值星:${r.sanxing || '无'}` };
			}catch(e){
				return { pass: false, actual: '通书:计算异常' };
			}
		},
	},
	tongshu_hours: {
		category: '通书',
		label: '通书吉时在(叠数/玄空)',
		defaults: { school: 'xuankong' },   // [Q-474/T-436] 缺省换成真能判别的玄空档
		fields: [
			// [Q-474/T-436] 叠数吉时只由日干、日支、时支决定,六十甲子每一天都有 6/8/10 个吉时 →
			// 「有吉时」逐日恒真,不是条件。档留着(旧方案不破),但置灰不许再选,并在档名里说清;
			// 玄空档有 541/4383 天为空,能判别,保持可选。
			{ key: 'school', kind: 'select', label: '流派', options: [
				{ value: 'dieshu', label: '奇门叠数(每日恒有吉时·不判别)', disabled: true, hint: '叠数吉时由日干/日支/时支决定,每日恒有 6/8/10 个 → 该档逐日恒真;要判具体时辰请用「时辰」组条件' },
				{ value: 'xuankong', label: '玄空大卦(有上吉时)' },
			], hint: '当日 bestHours 非空;玄空天人判需本命,择日按天地判(通书页同缺省)' },
		],
		validate: ()=>'',
		summary(p){ return `${p.school === 'xuankong' ? '玄空' : '叠数'}有吉时`; },
		evaluate(day, p){
			const ymd = `${(day.solar && day.solar.ymd) || ''}`.split('-').map(Number);
			if(ymd.length < 3 || !ymd[0]){ return { pass: false, actual: '通书:—' }; }
			const args = { y: ymd[0], m: ymd[1], d: ymd[2] };
			try{
				const r = p.school === 'xuankong' ? xuankongDay(args, undefined) : qimenDieShuDay(args);
				const best = r.bestHours || [];
				return { pass: best.length > 0, actual: `${p.school === 'xuankong' ? '玄空' : '叠数'}吉时:${best.join('、') || '无'}` };
			}catch(e){
				return { pass: false, actual: '通书:计算异常' };
			}
		},
	},
	yongshi_verdict: {
		category: '用事',
		label: '用事裁决(宜/忌/冲突)',
		defaults: { event: '嫁娶', want: ['yi'] },
		fields: [
			{ key: 'event', kind: 'select', label: '用事', options: HUANGLI_TERM_OPTIONS },
			{ key: 'want', kind: 'multiselect', label: '裁决(任一)', options: [{ value: 'yi', label: '宜' }, { value: 'ji', label: '忌' }, { value: 'conflict', label: '宜忌冲突' }, { value: 'neutral', label: '无断' }], hint: '判定=通书页 yongshiVerdict 同函数(同义词组归并;冲突=凶优先展示)' },
		],
		validate: (p)=>(!p.want || !p.want.length) ? '至少选择一项' : '',
		summary(p){ return `${p.event}:${(p.want || []).map((w)=>({ yi: '宜', ji: '忌', conflict: '冲突', neutral: '无断' })[w] || w).join('/')}`; },
		evaluate(day, p){
			const r = yongshiVerdict(day, p.event || '');
			return { pass: (p.want || []).includes(r.level), actual: `${p.event}:${({ yi: '宜', ji: '忌', conflict: '宜忌冲突', neutral: '无断' })[r.level] || r.level}${(r.hits && r.hits.length) ? `(${r.hits.join('/')})` : ''}` };
		},
	},
	month_year_info: {
		category: '历法',
		label: '月/年干支·生肖',
		defaults: { dim: 'monthgz', values: ['寅'] },
		fields: [
			{ key: 'dim', kind: 'select', label: '判面', options: [{ value: 'monthgz', label: '月干支(单字=干或支)' }, { value: 'yeargz', label: '年干支(单字=干或支)' }, { value: 'shengxiao', label: '年生肖' }] },
			{ key: 'values', kind: 'multiselect', label: '取值(任一)', options: [...opt(['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']), ...opt(ZHI12), ...opt(['鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪'])], hint: 'lunar.monthGZ/yearGZ/shengxiao;月家神煞按月支起——月建条件即此' },
		],
		validate: (p)=>(!p.values || !p.values.length) ? '至少选择一项' : '',
		summary(p){ return `${({ monthgz: '月柱', yeargz: '年柱', shengxiao: '生肖' })[p.dim] || '月柱'}:${(p.values || []).join('/')}`; },
		evaluate(day, p){
			const l = day.lunar || {};
			if(p.dim === 'shengxiao'){
				const sx = `${l.shengxiao || ''}`;
				return { pass: !!sx && (p.values || []).includes(sx), actual: `年生肖:${sx || '—'}` };
			}
			const gz = `${p.dim === 'yeargz' ? (l.yearGZ || '') : (l.monthGZ || '')}`;
			const pass = (p.values || []).some((v)=>(v.length >= 2 ? gz === v : gz.indexOf(v) >= 0));
			return { pass, actual: `${p.dim === 'yeargz' ? '年柱' : '月柱'}:${gz || '—'}` };
		},
	},
	xiu_detail: {
		category: '神煞',
		label: '值宿细面(四象/七政/禽)',
		// [Q-271/ZC-19] 四象实值/选项皆「东青龙」等三字形,缺省曾写「东方青龙」→ 含判双向皆不成立、新加即恒假。
		defaults: { dim: 'xiang', values: ['东青龙'] },
		fields: [
			{ key: 'dim', kind: 'select', label: '判面', options: [{ value: 'xiang', label: '四象方' }, { value: 'zheng', label: '七政值日' }, { value: 'animal', label: '值禽' }] },
			{ key: 'values', kind: 'multiselect', label: '取值(任一;含判)', options: [...opt(['东青龙', '北玄武', '西白虎', '南朱雀']), ...opt(['日', '月', '火', '水', '木', '金', '土']), ...opt(['蛟', '龙', '貉', '兔', '狐', '虎', '豹', '獬', '牛', '蝠', '鼠', '燕', '猪', '獝', '狼', '狗', '彘', '鸡', '乌', '猴', '猿', '犴', '羊', '獐', '马', '鹿', '蛇', '蚓'])], hint: 'xiu.xiang/zheng/animal(黄历页宿卡同源;四象实值形「南朱雀」dump 实抓);跨面选值不命中即判否' },
		],
		validate: (p)=>(!p.values || !p.values.length) ? '至少选择一项' : '',
		summary(p){ return `宿${({ xiang: '四象', zheng: '七政', animal: '值禽' })[p.dim] || '四象'}:${(p.values || []).join('/')}`; },
		evaluate(day, p){
			const x = day.xiu || {};
			const v = `${x[p.dim || 'xiang'] || ''}`;
			const pass = !!v && (p.values || []).some((w)=>v.indexOf(w) >= 0 || `${w}`.indexOf(v) >= 0);
			return { pass, actual: `${x.name || '?'}宿·${x.xiang || '—'}·${x.zheng || '—'}值·禽${x.animal || '—'}` };
		},
	},
	sha_fang_pengzu: {
		category: '神煞',
		label: '煞方/彭祖百忌',
		defaults: { dim: 'sha', values: ['煞南'] },
		fields: [
			{ key: 'dim', kind: 'select', label: '判面', options: [{ value: 'sha', label: '煞方' }, { value: 'pengzu_gan', label: '彭祖干忌(含字)' }, { value: 'pengzu_zhi', label: '彭祖支忌(含字)' }] },
			{ key: 'values', kind: 'multiselect', label: '取值(任一;百忌按含字匹配)', options: [...opt(['煞东', '煞南', '煞西', '煞北']), ...opt(['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']), ...opt(ZHI12)], hint: '煞方=chong.sha;百忌=pengzu.gan/zhi 口诀文本(选干/支字判首字)' },
		],
		validate: (p)=>(!p.values || !p.values.length) ? '至少选择一项' : '',
		summary(p){ return `${({ sha: '煞方', pengzu_gan: '彭祖干', pengzu_zhi: '彭祖支' })[p.dim] || '煞方'}:${(p.values || []).join('/')}`; },
		evaluate(day, p){
			if(p.dim === 'sha'){
				const v = `${(day.chong && day.chong.sha) || ''}`;
				return { pass: !!v && (p.values || []).some((w)=>v.indexOf(`${w}`.replace('煞', '')) >= 0 || v === w), actual: `煞方:${v || '—'}` };
			}
			const pz = `${(day.pengzu && day.pengzu[p.dim === 'pengzu_zhi' ? 'zhi' : 'gan']) || ''}`;
			const pass = !!pz && (p.values || []).some((w)=>pz.indexOf(w) >= 0);
			return { pass, actual: `百忌:${pz || '—'}` };
		},
	},
};

// ── 树工厂/摘要/编译(与奇门同构;compile 产物喂 evaluateHuangliTree) ──
export function newHuangliLeaf(type, joiner){
	const spec = HUANGLI_CONDITION_TYPES[type];
	return {
		kind: 'leaf',
		type,
		negate: false,
		joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all',
		params: spec ? JSON.parse(JSON.stringify(spec.defaults)) : {},
	};
}
export function newHuangliGroup(joiner){
	return { kind: 'group', negate: false, joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all', children: [] };
}

export function huangliLeafSummary(leaf){
	const spec = leaf ? HUANGLI_CONDITION_TYPES[leaf.type] : null;
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
		const spec = HUANGLI_CONDITION_TYPES[node.type];
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
// 行链 → 求值树:第 2 行起按各自 joiner 左折叠;连续同门扁平为多元组(与天星/奇门 compile 同构)。
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
export function compileHuangliTree(root){
	return compileSelf(root);
}
