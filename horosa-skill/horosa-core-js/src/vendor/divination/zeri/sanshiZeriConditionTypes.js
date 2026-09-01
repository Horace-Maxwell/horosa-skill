// [Z6·三式择日] 条件注册表=六壬/奇门/太乙三家**程序化合并**(定案2:跨三式合参条件一棵树
// 混排,每样本起三盘)。零手抄:键=`lr_*/qm_*/ty_*` 前缀,label/category 加「六壬·」等家名
// 前缀(工作台 OptGroup 按 category 自动分组);evaluate 分派到 `spec.evaluate(pan[fam],
// params, ctx[fam])`——三家 spec 契约逐字段同构(Z0 统一契约)是零适配合并的前提。
// 🔴 freeze 断言:合并层浅拷 spec 绝不 mutate 三源注册表(金标钉);某家起盘失败时该家
// 全部叶判 {pass:false, actual:'该家起盘失败'} 注记,勿静默吞(定案)。
import { LIURENG_CONDITION_TYPES, makeLiurengZeriEvalCtx } from './liurengZeriConditionTypes.js';
import { QIMEN_CONDITION_TYPES, makeQimenEvalCtx } from './qimenConditionTypes.js';
import { TAIYI_CONDITION_TYPES, makeTaiyiZeriEvalCtx } from './taiyiZeriConditionTypes.js';
import { GROUP_TYPES, JOINER_CN } from './conditionTypes.js';

export { GROUP_TYPES, JOINER_CN };

export const SANSHI_FAMILIES = [
	{ prefix: 'lr', famKey: 'liureng', cn: '六壬', types: LIURENG_CONDITION_TYPES, makeCtx: makeLiurengZeriEvalCtx },
	{ prefix: 'qm', famKey: 'qimen', cn: '奇门', types: QIMEN_CONDITION_TYPES, makeCtx: makeQimenEvalCtx },
	{ prefix: 'ty', famKey: 'taiyi', cn: '太乙', types: TAIYI_CONDITION_TYPES, makeCtx: makeTaiyiZeriEvalCtx },
];

// 惰性三家 ctx(每家首个叶求值时建;某家盘 null 则 ctx 为 null)。
export function makeSanshiZeriEvalCtx(pan){
	const cache = {};
	return {
		famCtx(famKey){
			if(cache[famKey] !== undefined){ return cache[famKey]; }
			const fam = SANSHI_FAMILIES.find((f)=>f.famKey === famKey);
			const famPan = pan ? pan[famKey] : null;
			cache[famKey] = (fam && famPan) ? fam.makeCtx(famPan) : null;
			return cache[famKey];
		},
	};
}

function mergeFamilies(){
	const out = {};
	SANSHI_FAMILIES.forEach(({ prefix, famKey, cn, types })=>{
		Object.keys(types).forEach((key)=>{
			const spec = types[key];
			out[`${prefix}_${key}`] = {
				category: `${cn}·${spec.category}`,
				label: `${cn}·${spec.label}`,
				defaults: spec.defaults,
				fields: spec.fields,
				validate: spec.validate,
				summary: spec.summary,
				famKey,
				evaluate(sanshiPan, params, sanshiCtx){
					const famPan = sanshiPan ? sanshiPan[famKey] : null;
					if(!famPan){
						const fail = sanshiPan && sanshiPan._famFail && sanshiPan._famFail[famKey];
						return { pass: false, actual: `${cn}盘起盘失败${fail ? `:${fail}` : ''}(该家条件判否)` };
					}
					const ctx = sanshiCtx && typeof sanshiCtx.famCtx === 'function' ? sanshiCtx.famCtx(famKey) : null;
					return spec.evaluate(famPan, params, ctx);
				},
			};
		});
	});
	return Object.freeze(out);
}

export const SANSHI_CONDITION_TYPES = mergeFamilies();

// ── 树工厂/摘要/编译(与其它择日技法同构) ──
export function newSanshiLeaf(type, joiner){
	const spec = SANSHI_CONDITION_TYPES[type];
	return {
		kind: 'leaf',
		type,
		negate: false,
		joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all',
		params: spec ? JSON.parse(JSON.stringify(spec.defaults)) : {},
	};
}
export function newSanshiGroup(joiner){
	return { kind: 'group', negate: false, joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all', children: [] };
}

export function sanshiLeafSummary(leaf){
	const spec = leaf ? SANSHI_CONDITION_TYPES[leaf.type] : null;
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
		const spec = SANSHI_CONDITION_TYPES[node.type];
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
export function compileSanshiTree(root){
	return compileSelf(root);
}
