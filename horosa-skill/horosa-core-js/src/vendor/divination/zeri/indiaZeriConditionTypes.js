// [Z8·印度择日] 条件注册表(远端判定形:判定在 astropy india_election_scan,pytest 金标
// 看守;工作台构树发 /indiaelectionscan)。Muhurta 为纲(定案14):Panchanga 五肢+Lagna+
// 曜落座+日凶段+本命组(Tara/Chandra Bala);Dasha 归本命分析面(coverage exempt 明示)。
// 🔴 类型键与后端 CONDITION_TYPES 逐键成对(indiaZeriEngine 金标 py 直读对拍);
// 27 宿名与 IndiaChartMain.NAKSHATRAS 同序同名(值=1..27 序号,后端同语义)。
import { GROUP_TYPES, JOINER_CN } from './conditionTypes.js';

export { GROUP_TYPES, JOINER_CN };

export const IN_NAK27 = ['Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra', 'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni', 'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha', 'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta', 'Shatabhisha', 'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati'];
export const IN_SIGNS = ['白羊', '金牛', '双子', '巨蟹', '狮子', '室女', '天秤', '天蝎', '人马', '摩羯', '宝瓶', '双鱼'];
export const IN_VARA = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
export const IN_BODIES = [
	{ value: 'Sun', label: '日' }, { value: 'Moon', label: '月' }, { value: 'Mercury', label: '水' },
	{ value: 'Venus', label: '金' }, { value: 'Mars', label: '火' }, { value: 'Jupiter', label: '木' },
	{ value: 'Saturn', label: '土' }, { value: 'Rahu', label: '罗睺' }, { value: 'Ketu', label: '计都' },
];
const KARANA = ['Bava', 'Balava', 'Kaulava', 'Taitila', 'Garaja', 'Vanija', 'Vishti', 'Shakuni', 'Chatushpada', 'Naga', 'Kimstughna'];

const numOpt = (n, labelOf)=>Array.from({ length: n }, (_, i)=>({ value: i + 1, label: labelOf ? labelOf(i + 1) : `${i + 1}` }));
const needValues = (p)=>(!p.values || !p.values.length) ? '至少选择一项' : '';

export const INDIA_CONDITION_TYPES = {
	tithi: {
		category: '五肢',
		label: 'Tithi(月相日)',
		defaults: { values: [2, 3, 5, 7, 10, 11, 13] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: 'Tithi(1-30;16-30=下弦)', options: numOpt(30) },
		],
		validate: needValues,
		summary(p){ return `Tithi:${(p.values || []).join('/')}`; },
	},
	vara: {
		category: '五肢',
		label: 'Vara(曜日·日出界)',
		defaults: { values: [4] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '曜日(按当地日出换日)', options: IN_VARA.map((l, i)=>({ value: i, label: l })) },
		],
		validate: needValues,
		summary(p){ return `Vara:${(p.values || []).map((v)=>IN_VARA[v] || v).join('/')}`; },
	},
	nakshatra: {
		category: '五肢',
		label: 'Nakshatra(月宿)',
		defaults: { body: 'Moon', values: [4] },
		fields: [
			{ key: 'body', kind: 'select', label: '曜', options: IN_BODIES },
			{ key: 'values', kind: 'multiselect', label: '宿(27)', options: numOpt(27, (i)=>`${i}.${IN_NAK27[i - 1]}`) },
		],
		validate: needValues,
		summary(p){ return `${(IN_BODIES.find((b)=>b.value === p.body) || {}).label || p.body}宿:${(p.values || []).map((v)=>IN_NAK27[v - 1] || v).join('/')}`; },
	},
	yoga: {
		category: '五肢',
		label: 'Yoga(日月合行)',
		defaults: { values: [23] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: 'Yoga(1-27)', options: numOpt(27) },
		],
		validate: needValues,
		summary(p){ return `Yoga:${(p.values || []).join('/')}`; },
	},
	karana: {
		category: '五肢',
		label: 'Karana(半日)',
		defaults: { values: ['Bava', 'Balava'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: 'Karana(11;Vishti=凶)', options: KARANA.map((k)=>({ value: k, label: k })) },
		],
		validate: needValues,
		summary(p){ return `Karana:${(p.values || []).join('/')}`; },
	},
	lagna: {
		category: '上升',
		label: 'Lagna(上升星座)',
		defaults: { values: [1] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '座(恒星制)', options: numOpt(12, (i)=>`${i}.${IN_SIGNS[i - 1]}`) },
		],
		validate: needValues,
		summary(p){ return `Lagna:${(p.values || []).map((v)=>IN_SIGNS[v - 1] || v).join('/')}`; },
	},
	planet_sign: {
		category: '曜位',
		label: '曜落星座',
		defaults: { body: 'Jupiter', values: [1] },
		fields: [
			{ key: 'body', kind: 'select', label: '曜', options: IN_BODIES },
			{ key: 'values', kind: 'multiselect', label: '座', options: numOpt(12, (i)=>`${i}.${IN_SIGNS[i - 1]}`) },
		],
		validate: needValues,
		summary(p){ return `${(IN_BODIES.find((b)=>b.value === p.body) || {}).label || p.body}在${(p.values || []).map((v)=>IN_SIGNS[v - 1] || v).join('/')}`; },
	},
	retro: {
		category: '曜位',
		label: '曜顺逆',
		defaults: { body: 'Mercury', state: 'direct' },
		fields: [
			{ key: 'body', kind: 'select', label: '曜', options: IN_BODIES.filter((b)=>['Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn'].includes(b.value)) },
			{ key: 'state', kind: 'select', label: '态', options: [{ value: 'direct', label: '顺行' }, { value: 'retro', label: '逆行' }] },
		],
		summary(p){ return `${(IN_BODIES.find((b)=>b.value === p.body) || {}).label || p.body}${p.state === 'retro' ? '逆' : '顺'}`; },
	},
	day_kalam: {
		category: '日段',
		label: '日凶段(Rahu Kalam 类)',
		defaults: { kind: 'rahu', mode: 'avoid' },
		fields: [
			{ key: 'kind', kind: 'select', label: '段', options: [{ value: 'rahu', label: 'Rahu Kalam' }, { value: 'yama', label: 'Yama Ganda' }, { value: 'gulika', label: 'Gulika Kalam' }] },
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'avoid', label: '避开该段' }, { value: 'in', label: '落在该段' }], hint: '日出~日落八分,段序随曜日;真日出制(随日长伸缩)' },
		],
		summary(p){ return `${({ rahu: 'Rahu Kalam', yama: 'Yama Ganda', gulika: 'Gulika' })[p.kind] || p.kind}${p.mode === 'in' ? '内' : '避开'}`; },
	},
	tara_bala: {
		category: '本命',
		label: 'Tara Bala(宿力)',
		// 默认=经典主流五吉(2/4/6/8/9);Janma(1) 主流计凶避用,不入默认(后端同值)
		defaults: { values: [2, 4, 6, 8, 9] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '吉 Tara(1-9;默认吉五)', options: numOpt(9) },
		],
		validate: needValues,
		summary(p){ return `Tara:${(p.values || []).join('/')}`; },
	},
	chandra_bala: {
		category: '本命',
		label: 'Chandra Bala(月力)',
		defaults: { values: [1, 3, 6, 7, 10, 11] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '吉位(候选月座自本命月座起 1-12)', options: numOpt(12) },
		],
		validate: needValues,
		summary(p){ return `Chandra:${(p.values || []).join('/')}`; },
	},
	muhurta_seg: {
		category: '日段',
		label: '三十须臾(Muhurta/Abhijit)',
		defaults: { pick: 'grade', grades: ['auspicious'] },
		fields: [
			{ key: 'pick', kind: 'select', label: '取段', options: [{ value: 'grade', label: '按吉凶档' }, { value: 'abhijit', label: 'Abhijit(昼第8·至吉)' }] },
			{ key: 'grades', kind: 'multiselect', label: '吉凶档(任一)', options: [{ value: 'auspicious', label: '吉须臾' }, { value: 'mixed', label: '中性' }, { value: 'inauspicious', label: '凶须臾' }], showIf: (p)=>p.pick !== 'abhijit', hint: '昼15+夜15(muhurta_day 权威表;日出界均分)' },
		],
		validate: (p)=>((p.pick === 'abhijit' || (p.grades && p.grades.length)) ? '' : '至少选择一档'),
		summary(p){ return p.pick === 'abhijit' ? 'Abhijit 须臾' : `须臾:${(p.grades || []).map((g)=>({ auspicious: '吉', mixed: '中', inauspicious: '凶' })[g] || g).join('/')}`; },
	},
	choghadia: {
		category: '日段',
		label: 'Choghadia 八段',
		defaults: { natures: ['good'], values: [] },
		fields: [
			{ key: 'natures', kind: 'multiselect', label: '吉凶(任一)', options: [{ value: 'good', label: '吉段(甘露/吉/利/动)' }, { value: 'bad', label: '凶段(病/时/扰)' }] },
			{ key: 'values', kind: 'multiselect', label: '细选段名(可空)', options: [{ value: 'Amrit', label: '甘露 Amrit' }, { value: 'Shubh', label: '吉 Shubh' }, { value: 'Labh', label: '利 Labh' }, { value: 'Char', label: '动 Char' }, { value: 'Rog', label: '病 Rog' }, { value: 'Kaal', label: '时 Kaal' }, { value: 'Udveg', label: '扰 Udveg' }], hint: '昼夜各8段轮值(jyotish_engine 同表同起排);细选与档任一命中' },
		],
		validate: (p)=>(((p.natures && p.natures.length) || (p.values && p.values.length)) ? '' : '至少选择一档'),
		summary(p){ return `Choghadia:${[...(p.natures || []).map((n)=>(n === 'good' ? '吉' : '凶')), ...(p.values || [])].join('/')}`; },
	},
	hora_vedic: {
		category: '日段',
		label: '行星时(Hora)',
		defaults: { values: ['木'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '主曜(任一)', options: [{ value: '日', label: '太阳时' }, { value: '月', label: '太阴时' }, { value: '火', label: '火星时' }, { value: '水', label: '水星时' }, { value: '木', label: '木星时' }, { value: '金', label: '金星时' }, { value: '土', label: '土星时' }], hint: '昼12+夜12(日出界;Chaldean 序,shadbala hora 同源)' },
		],
		validate: needValues,
		summary(p){ return `Hora:${(p.values || []).join('/')}时`; },
	},
	panchaka: {
		category: '五肢',
		label: 'Panchaka 五忌',
		defaults: { mode: 'avoid', values: [] },
		fields: [
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'avoid', label: '避开五忌段(推荐)' }, { value: 'in', label: '处于五忌段' }] },
			{ key: 'values', kind: 'multiselect', label: '细选忌种(空=全部)', options: [{ value: 'Mrityu', label: '死忌' }, { value: 'Agni', label: '火忌' }, { value: 'Raja', label: '王忌' }, { value: 'Chora', label: '盗忌' }, { value: 'Roga', label: '病忌' }], hint: '((Tithi+Vara+Nak+Lagna)×2)%9(与主印度盘同公式);含 Lagna 变率,细步扫描' },
		],
		validate: ()=>'',
		summary(p){ return `${p.mode === 'in' ? '处于' : '避'}五忌${(p.values && p.values.length) ? `(${p.values.length}种)` : ''}`; },
	},
	nak_pada: {
		category: '五肢',
		label: '月宿分足(Pada 1-4)',
		defaults: { body: 'Moon', values: ['1'] },
		fields: [
			{ key: 'body', kind: 'select', label: '曜', options: [{ value: 'Moon', label: '月' }, { value: 'Sun', label: '日' }] },
			{ key: 'values', kind: 'multiselect', label: '分足(任一)', options: [{ value: '1', label: '第1足' }, { value: '2', label: '第2足' }, { value: '3', label: '第3足' }, { value: '4', label: '第4足' }], hint: 'NAK_SIZE/4;Vimshottari/Muhurta 标准细分' },
		],
		validate: needValues,
		summary(p){ return `${p.body === 'Sun' ? '日' : '月'}宿足:${(p.values || []).join('/')}`; },
	},
	bhava_from_lagna: {
		category: '曜位',
		label: '曜落宫(自 Lagna 整宫)',
		defaults: { body: 'Jupiter', group: 'kendra', values: [] },
		fields: [
			{ key: 'body', kind: 'select', label: '曜', options: [{ value: 'Sun', label: '日' }, { value: 'Moon', label: '月' }, { value: 'Mars', label: '火' }, { value: 'Mercury', label: '水' }, { value: 'Jupiter', label: '木' }, { value: 'Venus', label: '金' }, { value: 'Saturn', label: '土' }, { value: 'Rahu', label: '罗睺' }, { value: 'Ketu', label: '计都' }] },
			{ key: 'group', kind: 'select', label: '宫组', options: [{ value: 'kendra', label: 'Kendra(1/4/7/10)' }, { value: 'trikona', label: 'Trikona(1/5/9)' }, { value: 'dusthana', label: 'Dusthana(6/8/12)' }, { value: 'custom', label: '自选宫位' }] },
			{ key: 'values', kind: 'multiselect', label: '自选宫(1-12)', options: Array.from({ length: 12 }, (_, i)=>({ value: `${i + 1}`, label: `第${i + 1}宫` })), showIf: (p)=>p.group === 'custom' },
		],
		validate: (p)=>((p.group === 'custom' && !(p.values && p.values.length)) ? '自选宫至少一项' : ''),
		summary(p){ return `${p.body}落${p.group === 'custom' ? `第${(p.values || []).join('/')}宫` : ({ kendra: 'Kendra', trikona: 'Trikona', dusthana: 'Dusthana' })[p.group]}`; },
	},
	day_night_in: {
		category: '日段',
		label: '昼/夜(日出界)',
		defaults: { value: 'day' },
		fields: [
			{ key: 'value', kind: 'select', label: '段', options: [{ value: 'day', label: '昼(日出→日没)' }, { value: 'night', label: '夜(日没→次日出)' }] },
		],
		validate: ()=>'',
		summary(p){ return p.value === 'night' ? '夜段' : '昼段'; },
	},
};

// ── 树工厂/摘要/编译(与其它择日技法同构) ──
export function newIndiaLeaf(type, joiner){
	const spec = INDIA_CONDITION_TYPES[type];
	return {
		kind: 'leaf',
		type,
		negate: false,
		joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all',
		params: spec ? JSON.parse(JSON.stringify(spec.defaults)) : {},
	};
}
export function newIndiaGroup(joiner){
	return { kind: 'group', negate: false, joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all', children: [] };
}

export function indiaLeafSummary(leaf){
	const spec = leaf ? INDIA_CONDITION_TYPES[leaf.type] : null;
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
		const spec = INDIA_CONDITION_TYPES[node.type];
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
export function compileIndiaTree(root){
	return compileSelf(root);
}
