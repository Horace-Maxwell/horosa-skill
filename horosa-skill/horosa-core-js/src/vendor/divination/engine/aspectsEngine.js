// divination/engine/aspectsEngine.js
// 读后端 aspects（normalAsp/immediateAsp），暴露入相/出相查询 + 映点。
// normalAsp 按 chartId(PascalCase) 键；每项 {Applicative[],Separative[],Exact[],None[],Obvious[]}，
// 元素 {id, asp, orb}。X.Applicative = X 正入相位这些星。
import { aspectByAngle } from '../data/aspects.js';
import { keyOfChartId, chartIdOfKey } from './utils.js';

function natureOf(angle){
	const a = aspectByAngle(angle);
	return a ? a.nature : 'neutral';
}

// 取某星全部相位（含 applying/separating/exact 标记）
export function aspectsOf(facts, key){
	const cid = chartIdOfKey(key) || key;
	const na = facts.result && facts.result.aspects && facts.result.aspects.normalAsp;
	if(!na || !na[cid]) return [];
	const entry = na[cid];
	const out = [];
	const push = (arr, flag) => {
		(arr || []).forEach((it) => {
			out.push({
				other: keyOfChartId(it.id), otherChartId: it.id,
				angle: it.asp, orb: it.orb,
				applying: flag === 'applying' || flag === 'exact',
				separating: flag === 'separating',
				exact: flag === 'exact',
				nature: natureOf(it.asp),
			});
		});
	};
	push(entry.Applicative, 'applying');
	push(entry.Exact, 'exact');
	push(entry.Separative, 'separating');
	return out;
}

export function applyingAspects(facts, key){ return aspectsOf(facts, key).filter((a) => a.applying); }
export function separatingAspects(facts, key){ return aspectsOf(facts, key).filter((a) => a.separating); }

// 两星之间的相位（任一方向）
export function aspectBetween(facts, a, b){
	const fromA = aspectsOf(facts, a).find((x) => x.other === b);
	if(fromA) return { ...fromA, from: a, to: b };
	const fromB = aspectsOf(facts, b).find((x) => x.other === a);
	if(fromB) return { ...fromB, from: b, to: a };
	return null;
}

// 映点相位（读 result.antiscias: [[id1,id2,orb],...]）
export function antiscionBetween(facts, a, b){
	const list = (facts.result && facts.result.antiscias) || [];
	const ca = chartIdOfKey(a) || a;
	const cb = chartIdOfKey(b) || b;
	const hit = list.find((x) => (x[0] === ca && x[1] === cb) || (x[0] === cb && x[1] === ca));
	return hit ? { a, b, orb: hit[2], type: 'antiscion' } : null;
}

export default aspectsOf;
