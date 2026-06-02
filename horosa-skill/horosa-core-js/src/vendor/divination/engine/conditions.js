// divination/engine/conditions.js
// 单星状态 → 统一结构 {key,value,polarity,weight,text_zh}（构建清单 §2.1）。
import { PLANETS } from '../data/planets.js';
import { angularDist } from './utils.js';

function cn(key){ return (PLANETS[key] || {}).cn || key; }

// 速度评估：月亮 <12°/日 偏慢；内行星明显慢于均速=事缓。
function speedNote(p){
	if(p.key === 'moon'){
		if(p.speed !== undefined && p.speed !== null && Math.abs(p.speed) < 12){
			return { polarity: 'negative', weight: 1, key: 'slow', text_zh: `${cn(p.key)} 行度缓慢（<12°/日），事缓力弱` };
		}
	}
	return null;
}

// 被夹（surround.attacks 含该星 chartId）
export function isBesieged(key, facts){
	const sur = facts && facts.result && facts.result.surround;
	if(!sur) return false;
	const cid = (facts.planets[key] || {}).chartId;
	const inList = (arr) => Array.isArray(arr) && arr.some((x) => x === cid || (x && (x.id === cid || x.planet === cid || x.target === cid)));
	if(inList(sur.attacks)) return true;
	if(sur.planets && inList(sur.planets.attacks)) return true;
	return false;
}

export function planetCondition(key, facts){
	const p = facts.planets[key];
	if(!p) return { key, findings: [], score: 0 };
	const f = [];
	const name = cn(key);

	// 必备尊贵
	if(p.dignityScore >= 4){
		f.push({ key: 'dignity', value: p.dignityScore, polarity: 'positive', weight: 2, text_zh: `${name} 必备尊贵有力（+${p.dignityScore}）` });
	}else if(p.dignityScore <= -4){
		f.push({ key: 'dignity', value: p.dignityScore, polarity: 'negative', weight: 2, text_zh: `${name} 落陷/失势（${p.dignityScore}）` });
	}else if(p.peregrine){
		f.push({ key: 'peregrine', value: true, polarity: 'negative', weight: 1, text_zh: `${name} 游走（无任何必备尊贵），缺乏力量` });
	}

	// 燃烧 / 日心 / 光束下
	if(p.combustion === 'cazimi'){
		f.push({ key: 'cazimi', value: true, polarity: 'positive', weight: 2, text_zh: `${name} 居日心（cazimi），如登王座，力量极强` });
	}else if(p.combustion === 'combust'){
		f.push({ key: 'combust', value: true, polarity: 'negative', weight: 3, text_zh: `${name} 燃烧（与日 <8.5°），最严重受克` });
	}else if(p.combustion === 'under_beams'){
		f.push({ key: 'under_beams', value: true, polarity: 'negative', weight: 1, text_zh: `${name} 在日光束下，力量受限` });
	}

	// 逆行
	if(p.retro){
		f.push({ key: 'retrograde', value: true, polarity: 'negative', weight: 2, text_zh: `${name} 逆行，力弱/乖气（主管命宫或用事宫则标红）` });
	}

	// 角续果
	if(p.angularity === 'angular'){
		f.push({ key: 'angular', value: true, polarity: 'positive', weight: 1, text_zh: `${name} 落角宫，有力、应事快` });
	}else if(p.angularity === 'cadent'){
		f.push({ key: 'cadent', value: true, polarity: 'negative', weight: 1, text_zh: `${name} 落果宫，力弱、拖延` });
	}

	// 被夹
	if(isBesieged(key, facts)){
		f.push({ key: 'besieged', value: true, polarity: 'negative', weight: 2, text_zh: `${name} 被双凶夹击（besieged）` });
	}

	const sp = speedNote(p);
	if(sp) f.push(sp);

	const score = f.reduce((s, x) => s + (x.polarity === 'positive' ? x.weight : (x.polarity === 'negative' ? -x.weight : 0)), 0);
	return { key, name, findings: f, score };
}

export default planetCondition;
