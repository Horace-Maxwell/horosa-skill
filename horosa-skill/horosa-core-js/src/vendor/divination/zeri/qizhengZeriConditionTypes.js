// [Z7·七政择日] 条件注册表(远端判定形:spec 契约与其它择日技法同构,但 evaluate 缺省——
// 判定在 astropy qizheng_election_scan(swisseph 直连分钟粒度),工作台构树发 /qizhengelectionscan;
// 值域同源 import guolaoData(SU28/庙旺态/化曜档与后端 guolao_const 成对,两侧 golden 看守)。
// 🔴 类型键与后端 CONDITION_TYPES 逐键成对(qizhengZeriEngine 金标经 conditiontypes 自检口
// 对拍;后端加叶前端未接=红)。首版宿制两档(回归今宿/回归古制)——主页其余七档为显示制,
// 扫描 gap 帮助明示(死开关律:不支持档不入工作台)。
import { SU28, SIGN_STATUS_SEQ } from '../../guolao/guolaoData.js';
import { GROUP_TYPES, JOINER_CN } from './conditionTypes.js';

export { GROUP_TYPES, JOINER_CN };

export const QZ_BODIES = ['日', '月', '金', '木', '水', '火', '土', '罗睺', '计都', '月孛', '紫炁'];
export const QZ_GONG12 = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
export const QZ_DIGNITY = ['庙', '旺', '平', '落', '陷'];

const opt = (arr)=>arr.map((v)=>({ value: v, label: v }));
const needValues = (p)=>(!p.values || !p.values.length) ? '至少选择一项' : '';

export const QIZHENG_CONDITION_TYPES = {
	body_in_gong: {
		category: '落宫',
		label: '曜落地支宫',
		defaults: { body: '月', values: ['午'] },
		fields: [
			{ key: 'body', kind: 'select', label: '曜', options: opt(QZ_BODIES) },
			{ key: 'values', kind: 'multiselect', label: '宫', options: opt(QZ_GONG12) },
		],
		validate: needValues,
		summary(p){ return `${p.body}在${(p.values || []).join('/')}宫`; },
	},
	body_in_xiu: {
		category: '落宿',
		label: '曜落二十八宿',
		defaults: { body: '月', values: ['角'] },
		fields: [
			{ key: 'body', kind: 'select', label: '曜', options: opt(QZ_BODIES) },
			{ key: 'values', kind: 'multiselect', label: '宿', options: opt(SU28) },
		],
		validate: needValues,
		summary(p){ return `${p.body}宿${(p.values || []).join('/')}`; },
	},
	dignity: {
		category: '庙旺',
		label: '曜庙旺状态',
		defaults: { body: '木', values: ['庙', '旺'] },
		fields: [
			{ key: 'body', kind: 'select', label: '曜', options: opt(['日', '月', '金', '木', '水', '火', '土']) },
			{ key: 'values', kind: 'multiselect', label: '态(庙旺平落陷)', options: opt(QZ_DIGNITY), hint: '判定=guolao_const 庙旺表(与主七政页 guolaoData 成对同源)' },
		],
		validate: needValues,
		summary(p){ return `${p.body}${(p.values || []).join('/')}`; },
	},
	dignity_seven: {
		category: '庙旺',
		label: '曜七态(殿垣庙旺乐喜怒)',
		defaults: { body: '木', values: ['垣', '庙'] },
		fields: [
			{ key: 'body', kind: 'select', label: '曜', options: opt(['日', '月', '金', '木', '水', '火', '土', '计', '罗', '炁', '孛']) },
			{ key: 'values', kind: 'multiselect', label: '七态(任一)', options: opt(['垣', '庙', '旺', '乐', '喜', '怒']), hint: '判定=py QIZHENG_SIGN_STATUS_RAW(js SIGN_STATUS_RAW 镜像,jest diff 锚);升殿峰值档为显示层专属不入扫描' },
		],
		validate: needValues,
		summary(p){ return `${p.body}七态:${(p.values || []).join('/')}`; },
	},
	deg_lord: {
		category: '落宿',
		label: '所在宿度主',
		defaults: { body: '月', values: ['木'] },
		fields: [
			{ key: 'body', kind: 'select', label: '曜', options: opt(QZ_BODIES) },
			{ key: 'values', kind: 'multiselect', label: '度主(七曜循环)', options: opt(['日', '月', '木', '金', '土', '火', '水']) },
		],
		validate: needValues,
		summary(p){ return `${p.body}居${(p.values || []).join('/')}度`; },
	},
	speed_state: {
		category: '行度',
		label: '曜行度态',
		defaults: { body: '水', state: 'retro' },
		fields: [
			{ key: 'body', kind: 'select', label: '曜', options: opt(['水', '金', '火', '木', '土', '月孛', '紫炁']) },
			{ key: 'state', kind: 'select', label: '态', options: [{ value: 'retro', label: '逆行' }, { value: 'direct', label: '顺行' }, { value: 'stationary', label: '留' }, { value: 'slow', label: '迟(仅五星)' }, { value: 'fast', label: '速(仅五星)' }] },
		],
		summary(p){ return `${p.body}${({ retro: '逆', direct: '顺', stationary: '留' })[p.state] || ''}`; },
	},
	combust: {
		category: '伏焦',
		label: '合日伏焦',
		defaults: { body: '水', mode: 'free' },
		fields: [
			{ key: 'body', kind: 'select', label: '曜', options: opt(['月', '水', '金', '火', '木', '土']) },
			{ key: 'mode', kind: 'select', label: '判法', options: [{ value: 'free', label: '不伏不焦(避)' }, { value: 'combust', label: '焦(8°内)' }, { value: 'fu', label: '伏(3°内)' }], hint: '双口径与主页同默认(8°焦/3°伏)' },
		],
		summary(p){ return `${p.body}${({ free: '离日', combust: '焦', fu: '伏' })[p.mode] || ''}`; },
	},
	day_night: {
		category: '昼夜',
		label: '昼占/夜占',
		defaults: { value: 'day' },
		fields: [
			{ key: 'value', kind: 'select', label: '取', options: [{ value: 'day', label: '昼(日在地平上)' }, { value: 'night', label: '夜' }] },
		],
		summary(p){ return p.value === 'night' ? '夜占' : '昼占'; },
	},
	asc_gong: {
		category: '命宫',
		label: '命宫(上升)落支',
		defaults: { values: ['子'] },
		fields: [
			{ key: 'values', kind: 'multiselect', label: '宫', options: opt(QZ_GONG12), hint: '候选时刻上升点所落地支宫(lifeMode=asc 档)' },
		],
		validate: needValues,
		summary(p){ return `命宫:${(p.values || []).join('/')}`; },
	},
	body_rel: {
		category: '会照',
		label: '两曜宫位关系',
		defaults: { bodyA: '木', bodyB: '月', rel: 'same' },
		fields: [
			{ key: 'bodyA', kind: 'select', label: '曜A', options: opt(QZ_BODIES) },
			{ key: 'bodyB', kind: 'select', label: '曜B', options: opt(QZ_BODIES) },
			{ key: 'rel', kind: 'select', label: '关系', options: [{ value: 'same', label: '同宫' }, { value: 'opposite', label: '对照' }, { value: 'trine', label: '三合' }] },
		],
		summary(p){ return `${p.bodyA}${({ same: '同宫', opposite: '对照', trine: '三合' })[p.rel] || ''}${p.bodyB}`; },
	},
	hua_lu: {
		category: '化曜',
		label: '化曜(年干禄主)落处',
		defaults: { where: 'gong', values: ['午'] },
		fields: [
			{ key: 'where', kind: 'select', label: '判面', options: [{ value: 'gong', label: '落宫' }, { value: 'xiu', label: '落宿' }] },
			{ key: 'values', kind: 'multiselect', label: '值', options: opt([...QZ_GONG12, ...SU28]), hint: '候选年干(立春界)化曜诀取禄主曜,判其落处' },
		],
		validate: needValues,
		summary(p){ return `禄主${p.where === 'xiu' ? '宿' : '宫'}:${(p.values || []).slice(0, 4).join('/')}${(p.values || []).length > 4 ? '…' : ''}`; },
	},
};

// SIGN_STATUS_SEQ 引用保留(殿垣庙旺乐喜怒七态=另一状态系,首版未建叶——coverage gap 注记)。
export const QZ_SIGN_STATUS_SEQ = SIGN_STATUS_SEQ;

// ── 树工厂/摘要/编译(与其它择日技法同构;编译产物直发后端 conditions) ──
export function newQizhengLeaf(type, joiner){
	const spec = QIZHENG_CONDITION_TYPES[type];
	return {
		kind: 'leaf',
		type,
		negate: false,
		joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all',
		params: spec ? JSON.parse(JSON.stringify(spec.defaults)) : {},
	};
}
export function newQizhengGroup(joiner){
	return { kind: 'group', negate: false, joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all', children: [] };
}

export function qizhengLeafSummary(leaf){
	const spec = leaf ? QIZHENG_CONDITION_TYPES[leaf.type] : null;
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
		const spec = QIZHENG_CONDITION_TYPES[node.type];
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
export function compileQizhengTree(root){
	return compileSelf(root);
}
